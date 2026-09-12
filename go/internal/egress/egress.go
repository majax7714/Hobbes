// Package egress is a live session's one route out (ADR-107): an HTTP
// CONNECT proxy that tunnels to the hosts an allowlist names and answers
// 403 to every other destination, writing each decision as one JSONL line.
//
// It runs in its own container on two podman networks — the session's
// `--internal` network, which has no route off the box, and a custom egress
// bridge — so the session reaches the model endpoint through it and nothing
// else. A host the list does not name is unreachable from the session
// container: it is not an agent's good manners that keep it away (C-41,
// C-124). The shape was measured before it was built (ADR-097: rootless
// podman 5.8, netavark + pasta; an internal network has no egress and no
// outside DNS, while its containers reach each other by name).
//
// Only CONNECT leaves: a plain-HTTP request through the proxy is refused,
// so every allowed byte is a TLS tunnel to a named host:port, and the log
// records the host the client asked for, not an address it resolved.
package egress

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// DefaultPort is the port an allowlist entry without one names: every
// endpoint a session talks to is HTTPS.
const DefaultPort = "443"

// Allowlist is the set of host:port pairs a session may open a tunnel to.
// Matching is exact on the lowercased host, with a trailing dot dropped:
// no wildcard, no suffix match, no IP range — a list entry names one place.
type Allowlist struct {
	entries map[string]bool
}

// ParseAllowlist reads entries of the form "host" or "host:port"; an item
// may hold several separated by commas. It refuses an empty list, a
// wildcard, a URL scheme or path, and a port outside 1–65535, so a typo
// fails the launch instead of widening the route.
func ParseAllowlist(items []string) (Allowlist, error) {
	a := Allowlist{entries: map[string]bool{}}
	for _, item := range items {
		for _, raw := range strings.Split(item, ",") {
			e := strings.TrimSpace(raw)
			if e == "" {
				continue
			}
			hp, err := normalize(e, true)
			if err != nil {
				return Allowlist{}, err
			}
			a.entries[hp] = true
		}
	}
	if len(a.entries) == 0 {
		return Allowlist{}, errors.New("egress: the allowlist is empty; name at least one host")
	}
	return a, nil
}

// normalize turns an entry or a CONNECT target into "host:port". An entry
// may omit the port (DefaultPort); a target must carry one.
func normalize(s string, entry bool) (string, error) {
	if strings.Contains(s, "://") || strings.ContainsAny(s, "/?#@ ") {
		return "", fmt.Errorf("egress: %q is not a host or host:port", s)
	}
	if strings.ContainsAny(s, "*") {
		return "", fmt.Errorf("egress: %q: wildcards are not allowed; name each host", s)
	}
	host, port, err := net.SplitHostPort(s)
	if err != nil {
		if !entry {
			return "", fmt.Errorf("egress: target %q has no port", s)
		}
		host, port = s, DefaultPort
	}
	host = strings.TrimSuffix(strings.ToLower(host), ".")
	if host == "" {
		return "", fmt.Errorf("egress: %q has no host", s)
	}
	n, err := strconv.Atoi(port)
	if err != nil || n < 1 || n > 65535 {
		return "", fmt.Errorf("egress: %q: port %q is not in 1-65535", s, port)
	}
	return net.JoinHostPort(host, strconv.Itoa(n)), nil
}

// Allows reports whether a CONNECT target ("host:port") is on the list.
func (a Allowlist) Allows(target string) bool {
	hp, err := normalize(target, false)
	return err == nil && a.entries[hp]
}

// Entries is the list, sorted, as the launch and the log print it.
func (a Allowlist) Entries() []string {
	out := make([]string, 0, len(a.entries))
	for e := range a.entries {
		out = append(out, e)
	}
	sort.Strings(out)
	return out
}

// Record is one line of the egress log. Event is "listen" (the proxy is
// up; Addr and Allow set), "connect" (a tunnel opened), "close" (a tunnel
// ended; the byte counts and duration set) or "refuse" (403, nothing
// dialled). Target is the host:port the client asked for, verbatim.
type Record struct {
	TS        string   `json:"ts"`
	Event     string   `json:"event"`
	Method    string   `json:"method,omitempty"`
	Target    string   `json:"target,omitempty"`
	Reason    string   `json:"reason,omitempty"`
	BytesUp   int64    `json:"bytes_up,omitempty"`
	BytesDown int64    `json:"bytes_down,omitempty"`
	MS        int64    `json:"ms,omitempty"`
	Error     string   `json:"error,omitempty"`
	Addr      string   `json:"addr,omitempty"`
	Allow     []string `json:"allow,omitempty"`
}

// Log writes Records as JSONL, one line per record, safe for concurrent
// tunnels. A write error is dropped rather than failing a tunnel: the
// session's work must not depend on the audit disk, and the launcher
// reads the log back to report it.
type Log struct {
	mu  sync.Mutex
	w   io.Writer
	now func() time.Time
}

// NewLog returns a Log writing to w.
func NewLog(w io.Writer) *Log {
	return &Log{w: w, now: time.Now}
}

// Write appends r, stamped with the current UTC time.
func (l *Log) Write(r Record) {
	if l == nil {
		return
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	r.TS = l.now().UTC().Format(time.RFC3339Nano)
	b, err := json.Marshal(r)
	if err != nil {
		return
	}
	_, _ = l.w.Write(append(b, '\n'))
}

// Proxy is the CONNECT handler. Dial opens the upstream connection; nil
// means a net.Dialer with a ten-second timeout.
type Proxy struct {
	Allow Allowlist
	Log   *Log
	Dial  func(ctx context.Context, network, addr string) (net.Conn, error)
}

// Refusal reasons, stated in the log and in the 403 body.
const (
	ReasonNotConnect  = "only CONNECT tunnels leave a session"
	ReasonNotListed   = "not on the session's egress allowlist"
	ReasonMalformed   = "the CONNECT target is not host:port"
	statusEstablished = "HTTP/1.1 200 Connection Established\r\n\r\n"
)

// ServeHTTP tunnels an allowed CONNECT and refuses everything else.
func (p *Proxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodConnect {
		p.refuse(w, r.Method, r.Host, ReasonNotConnect)
		return
	}
	target := r.Host
	if _, err := normalize(target, false); err != nil {
		p.refuse(w, r.Method, target, ReasonMalformed)
		return
	}
	if !p.Allow.Allows(target) {
		p.refuse(w, r.Method, target, ReasonNotListed)
		return
	}
	dial := p.Dial
	if dial == nil {
		dial = (&net.Dialer{Timeout: 10 * time.Second}).DialContext
	}
	up, err := dial(r.Context(), "tcp", target)
	if err != nil {
		p.Log.Write(Record{Event: "close", Method: r.Method, Target: target, Error: "dial: " + err.Error()})
		http.Error(w, "egress: upstream unreachable", http.StatusBadGateway)
		return
	}
	hj, ok := w.(http.Hijacker)
	if !ok {
		up.Close()
		http.Error(w, "egress: tunnel unsupported", http.StatusInternalServerError)
		return
	}
	client, buf, err := hj.Hijack()
	if err != nil {
		up.Close()
		return
	}
	start := time.Now()
	if _, err := client.Write([]byte(statusEstablished)); err != nil {
		client.Close()
		up.Close()
		return
	}
	p.Log.Write(Record{Event: "connect", Method: r.Method, Target: target})
	upBytes, downBytes := splice(client, buf.Reader, up)
	p.Log.Write(Record{Event: "close", Method: r.Method, Target: target, BytesUp: upBytes, BytesDown: downBytes,
		MS: time.Since(start).Milliseconds()})
}

func (p *Proxy) refuse(w http.ResponseWriter, method, target, reason string) {
	p.Log.Write(Record{Event: "refuse", Method: method, Target: target, Reason: reason})
	http.Error(w, "egress: "+reason, http.StatusForbidden)
}

// splice copies both directions until each side is done and closes both.
// The client side reads through the hijack's buffered reader, so bytes the
// client sent right behind its CONNECT (a pipelined TLS hello) are not lost.
func splice(client net.Conn, clientR *bufio.Reader, up net.Conn) (int64, int64) {
	var wg sync.WaitGroup
	var upBytes, downBytes int64
	wg.Add(2)
	go func() {
		defer wg.Done()
		upBytes, _ = io.Copy(up, clientR)
		closeWrite(up)
	}()
	go func() {
		defer wg.Done()
		downBytes, _ = io.Copy(client, up)
		closeWrite(client)
	}()
	wg.Wait()
	client.Close()
	up.Close()
	return upBytes, downBytes
}

func closeWrite(c net.Conn) {
	if cw, ok := c.(interface{ CloseWrite() error }); ok {
		_ = cw.CloseWrite()
		return
	}
	_ = c.Close()
}

// Serve runs the proxy on ln until ctx ends, first writing the "listen"
// record the launcher waits for before it starts the session.
func Serve(ctx context.Context, ln net.Listener, p *Proxy) error {
	p.Log.Write(Record{Event: "listen", Addr: ln.Addr().String(), Allow: p.Allow.Entries()})
	srv := &http.Server{Handler: p, ReadHeaderTimeout: 10 * time.Second}
	errc := make(chan error, 1)
	go func() { errc <- srv.Serve(ln) }()
	select {
	case <-ctx.Done():
		shut, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		_ = srv.Shutdown(shut)
		return nil
	case err := <-errc:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}

// Summary is what a finished session's egress log says, for the launcher's
// last line and the dispatch record: tunnels opened per target, refusals
// per target, and whether the proxy ever listened.
type Summary struct {
	Listened bool           `json:"listened"`
	Allow    []string       `json:"allow"`
	Opened   map[string]int `json:"opened"`
	Refused  map[string]int `json:"refused"`
	Errors   int            `json:"errors"`
}

// Summarize reads an egress log. A malformed line is counted in Errors,
// never skipped silently.
func Summarize(r io.Reader) Summary {
	s := Summary{Opened: map[string]int{}, Refused: map[string]int{}}
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64*1024), 1<<20)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var rec Record
		if err := json.Unmarshal([]byte(line), &rec); err != nil {
			s.Errors++
			continue
		}
		switch rec.Event {
		case "listen":
			s.Listened = true
			s.Allow = rec.Allow
		case "connect":
			s.Opened[rec.Target]++
		case "refuse":
			s.Refused[rec.Target]++
		case "close":
			if rec.Error != "" {
				s.Errors++
			}
		}
	}
	return s
}

// String is the one-line form the launcher prints.
func (s Summary) String() string {
	if !s.Listened {
		return "egress: the proxy never listened"
	}
	return fmt.Sprintf("egress: allow %s; opened %s; refused %s", strings.Join(s.Allow, ","), counts(s.Opened), counts(s.Refused))
}

func counts(m map[string]int) string {
	if len(m) == 0 {
		return "none"
	}
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parts := make([]string, len(keys))
	for i, k := range keys {
		parts[i] = fmt.Sprintf("%s×%d", k, m[k])
	}
	return strings.Join(parts, ", ")
}
