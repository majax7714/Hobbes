package egress

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestParseAllowlistDefaultsThePortAndLowercases(t *testing.T) {
	a, err := ParseAllowlist([]string{"API.Anthropic.com", "example.test:8443, other.test."})
	if err != nil {
		t.Fatal(err)
	}
	got := strings.Join(a.Entries(), " ")
	if got != "api.anthropic.com:443 example.test:8443 other.test:443" {
		t.Errorf("entries = %q", got)
	}
	for target, want := range map[string]bool{
		"api.anthropic.com:443":   true,
		"API.ANTHROPIC.COM:443":   true,
		"api.anthropic.com.:443":  true,
		"api.anthropic.com:80":    false,
		"example.test:443":        false,
		"example.test:8443":       true,
		"anthropic.com:443":       false, // no suffix match
		"x.api.anthropic.com:443": false,
		"api.anthropic.com":       false, // a CONNECT target carries a port
	} {
		if a.Allows(target) != want {
			t.Errorf("Allows(%q) = %v, want %v", target, !want, want)
		}
	}
}

func TestParseAllowlistRefusesWhatWouldWidenTheRoute(t *testing.T) {
	for _, bad := range [][]string{
		nil,
		{""},
		{" , "},
		{"*.anthropic.com"},
		{"*"},
		{"https://api.anthropic.com"},
		{"api.anthropic.com/v1"},
		{"api.anthropic.com:0"},
		{"api.anthropic.com:99999"},
		{"api.anthropic.com:https"},
		{"user@host"},
	} {
		if _, err := ParseAllowlist(bad); err == nil {
			t.Errorf("ParseAllowlist(%q) accepted", bad)
		}
	}
}

// echoServer accepts one connection and echoes what it reads.
func echoServer(t *testing.T) net.Listener {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go func() { io.Copy(c, c); c.Close() }()
		}
	}()
	t.Cleanup(func() { ln.Close() })
	return ln
}

// proxyUnderTest starts a Proxy whose dialer maps every allowed name onto
// the echo server and records what it was asked to dial.
func proxyUnderTest(t *testing.T, allow []string, upstream string) (addr string, logBuf *syncBuffer, dialed *[]string) {
	t.Helper()
	a, err := ParseAllowlist(allow)
	if err != nil {
		t.Fatal(err)
	}
	logBuf = &syncBuffer{}
	var mu sync.Mutex
	dialed = &[]string{}
	p := &Proxy{Allow: a, Log: NewLog(logBuf), Dial: func(ctx context.Context, network, target string) (net.Conn, error) {
		mu.Lock()
		*dialed = append(*dialed, target)
		mu.Unlock()
		return (&net.Dialer{}).DialContext(ctx, network, upstream)
	}}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() { Serve(ctx, ln, p); close(done) }()
	t.Cleanup(func() { cancel(); <-done })
	return ln.Addr().String(), logBuf, dialed
}

type syncBuffer struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.Write(p)
}

func (s *syncBuffer) String() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.String()
}

// connect sends a CONNECT for target and returns the status line and the
// connection positioned after the response headers.
func connect(t *testing.T, proxyAddr, target string) (string, net.Conn, *bufio.Reader) {
	t.Helper()
	c, err := net.Dial("tcp", proxyAddr)
	if err != nil {
		t.Fatal(err)
	}
	fmt.Fprintf(c, "CONNECT %s HTTP/1.1\r\nHost: %s\r\n\r\n", target, target)
	br := bufio.NewReader(c)
	resp, err := http.ReadResponse(br, &http.Request{Method: http.MethodConnect})
	if err != nil {
		t.Fatal(err)
	}
	return resp.Status, c, br
}

func TestProxyTunnelsAnAllowedHost(t *testing.T) {
	up := echoServer(t)
	addr, logBuf, dialed := proxyUnderTest(t, []string{"allowed.test"}, up.Addr().String())

	status, c, br := connect(t, addr, "allowed.test:443")
	if !strings.HasPrefix(status, "200") {
		t.Fatalf("status = %q, want 200", status)
	}
	fmt.Fprint(c, "ping\n")
	line, err := br.ReadString('\n')
	if err != nil || line != "ping\n" {
		t.Fatalf("echo through the tunnel = %q, %v", line, err)
	}
	c.Close()
	if len(*dialed) != 1 || (*dialed)[0] != "allowed.test:443" {
		t.Errorf("dialed %v, want [allowed.test:443]", *dialed)
	}
	deadline := time.Now().Add(2 * time.Second)
	for !strings.Contains(logBuf.String(), `"event":"close"`) && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	s := Summarize(strings.NewReader(logBuf.String()))
	if !s.Listened || s.Opened["allowed.test:443"] != 1 || len(s.Refused) != 0 {
		t.Errorf("summary = %+v\nlog:\n%s", s, logBuf.String())
	}
	if !strings.Contains(logBuf.String(), `"bytes_up":5`) {
		t.Errorf("the close record should count the 5 bytes sent:\n%s", logBuf.String())
	}
}

func TestProxyRefusesEveryOtherDestinationWithoutDialling(t *testing.T) {
	up := echoServer(t)
	addr, logBuf, dialed := proxyUnderTest(t, []string{"allowed.test"}, up.Addr().String())

	for _, target := range []string{"other.test:443", "allowed.test:80", "sub.allowed.test:443"} {
		status, c, _ := connect(t, addr, target)
		c.Close()
		if !strings.HasPrefix(status, "403") {
			t.Errorf("CONNECT %s: status %q, want 403", target, status)
		}
	}
	if len(*dialed) != 0 {
		t.Errorf("a refused target must never be dialled; dialed %v", *dialed)
	}
	s := Summarize(strings.NewReader(logBuf.String()))
	if s.Refused["other.test:443"] != 1 || s.Refused["allowed.test:80"] != 1 || s.Refused["sub.allowed.test:443"] != 1 {
		t.Errorf("refusals not logged per target: %+v", s.Refused)
	}
	if !strings.Contains(logBuf.String(), ReasonNotListed) {
		t.Errorf("the log should state the reason:\n%s", logBuf.String())
	}
}

func TestProxyRefusesPlainHTTPEvenToAnAllowedHost(t *testing.T) {
	up := echoServer(t)
	addr, logBuf, dialed := proxyUnderTest(t, []string{"allowed.test:80"}, up.Addr().String())

	c, err := net.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	fmt.Fprint(c, "GET http://allowed.test/ HTTP/1.1\r\nHost: allowed.test\r\n\r\n")
	resp, err := http.ReadResponse(bufio.NewReader(c), nil)
	if err != nil {
		t.Fatal(err)
	}
	if resp.StatusCode != http.StatusForbidden || len(*dialed) != 0 {
		t.Errorf("plain HTTP: status %d, dialed %v; want 403 and nothing dialled", resp.StatusCode, *dialed)
	}
	if !strings.Contains(logBuf.String(), ReasonNotConnect) {
		t.Errorf("the log should state the reason:\n%s", logBuf.String())
	}
}

func TestSummarizeCountsMalformedLinesAndSaysWhenTheProxyNeverListened(t *testing.T) {
	s := Summarize(strings.NewReader("not json\n\n"))
	if s.Listened || s.Errors != 1 {
		t.Errorf("summary = %+v", s)
	}
	if !strings.Contains(s.String(), "never listened") {
		t.Errorf("String() = %q", s.String())
	}
}
