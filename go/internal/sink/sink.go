// Package sink implements the session's records sink (ADR-112): the
// flight log, the escalation queue and the mail file, all written by one
// process outside the doer's container. It speaks one small
// newline-delimited JSON protocol over TCP — one request per line, one
// reply per request, in order — and is the only writer of
// <dir>/flight.jsonl, <dir>/escalations/ and <dir>/mail.jsonl.
//
// The sink accepts exactly one long-lived connection as the flight
// stream, ever: whichever connection sends the first open. That is a
// deliberate boundary, not an accident of the wire shape — a TCP socket
// cannot be reopened through /proc/<pid>/fd (the kernel answers ENXIO,
// ADR-112's fourth measurement), so a shell in the doer's container that
// wanted to forge or replay flight lines has no way to take over the
// connection the proxy already holds. A second open is refused and the
// attempt is itself recorded.
package sink

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// DefaultPort is the port a session's sidecar listens on for the flight
// stream (ADR-112).
const DefaultPort = "3129"

// otherConnDeadline bounds a read on any connection that has not (or
// will never) become the flight stream: an edit line, an open attempt
// that loses the race, or a client that never sends anything.
const otherConnDeadline = 5 * time.Second

// Config identifies the session dir the sink writes under, and the
// session and role it stamps on every line it writes. Never trust a
// message for these: a doer's container can say anything on the wire,
// but it cannot make the sink lie about whose session this is.
type Config struct {
	Dir     string
	Session string
	Role    string
}

// MailLine is one line of <dir>/mail.jsonl — the reflect tool's inbox
// (ADR-054), moved here from proxy/agent.go's mailLine so the sink and
// the file journal share one shape. Seq is not part of it: AppendMail
// computes it from the file, as it always has.
type MailLine struct {
	TS      string `json:"ts"`
	Session string `json:"session"`
	Role    string `json:"role"`
	Kind    string `json:"kind"`
	Text    string `json:"text"`
}

// wireMailLine is the shape actually written to mail.jsonl (and read by
// run/mail.py): MailLine plus the sequence number AppendMail computes.
type wireMailLine struct {
	Seq     int    `json:"seq"`
	TS      string `json:"ts"`
	Session string `json:"session"`
	Role    string `json:"role"`
	Kind    string `json:"kind"`
	Text    string `json:"text"`
}

// AppendMail appends line to path with seq = existing non-blank lines +
// 1, and returns the seq. The file is created 0600, like the flight log
// (ADR-012). Moved from proxy/agent.go's appendMail; the same semantics.
func AppendMail(path string, line MailLine) (int, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return 0, err
	}
	seq := 1
	if f, err := os.Open(path); err == nil {
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			if len(bytes.TrimSpace(sc.Bytes())) != 0 {
				seq++
			}
		}
		f.Close()
	}
	data, err := json.Marshal(wireMailLine{
		Seq: seq, TS: line.TS, Session: line.Session, Role: line.Role,
		Kind: line.Kind, Text: line.Text,
	})
	if err != nil {
		return 0, err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return 0, err
	}
	defer f.Close()
	if _, err := f.Write(append(data, '\n')); err != nil {
		return 0, err
	}
	return seq, nil
}

// request is one line a client sends. Kind selects which fields matter;
// the rest are ignored.
type request struct {
	Kind   string             `json:"kind"`
	Event  *recorder.Event    `json:"event,omitempty"`
	Record *escalation.Record `json:"record,omitempty"`
	ID     string             `json:"id,omitempty"`
	Line   *MailLine          `json:"line,omitempty"`
}

// response is one line the sink sends back, one per request, in order.
type response struct {
	OK     bool               `json:"ok"`
	Error  string             `json:"error,omitempty"`
	Record *escalation.Record `json:"record,omitempty"`
	Seq    int                `json:"seq,omitempty"`
}

// validEditTools are the only tools an edit request may name (ADR-107's
// retention rule, carried into ADR-112): a progress hook records a
// tool's name and path, never anything that could be read as an exec
// decision.
var validEditTools = map[string]bool{"Edit": true, "Write": true, "MultiEdit": true, "NotebookEdit": true}

// sink is the server state shared by every connection: the flight log
// and whether the one stream has been claimed.
type sink struct {
	cfg Config
	rec *recorder.Recorder

	mu      sync.Mutex
	claimed bool
}

// Serve runs the sink on ln until ctx ends, like egress.Serve. It opens
// the flight log, writes the "listening" line the launcher waits for —
// the session cannot reach the sidecar's internal network from the host,
// so this line is how the caller knows the sink is up — and then accepts
// connections until ctx is done.
func Serve(ctx context.Context, ln net.Listener, cfg Config) error {
	rec, err := recorder.Open(filepath.Join(cfg.Dir, "flight.jsonl"))
	if err != nil {
		return fmt.Errorf("sink: %w", err)
	}
	defer rec.Close()

	s := &sink{cfg: cfg, rec: rec}
	if err := s.writeSinkLine("listening"); err != nil {
		return fmt.Errorf("sink: %w", err)
	}

	errc := make(chan error, 1)
	go func() {
		for {
			conn, err := ln.Accept()
			if err != nil {
				errc <- err
				return
			}
			go s.handleConn(conn)
		}
	}()

	select {
	case <-ctx.Done():
		_ = ln.Close()
		return nil
	case err := <-errc:
		if errors.Is(err, net.ErrClosed) {
			return nil
		}
		return err
	}
}

// writeSinkLine appends one of the sink's own flight lines: tool "sink",
// an empty (never nil) argv, policy_rule "sink", and decision one of
// listening, stream_opened, stream_closed, stream_refused.
func (s *sink) writeSinkLine(decision string) error {
	return s.rec.Record(recorder.Event{
		Session:    s.cfg.Session,
		Role:       s.cfg.Role,
		Tool:       "sink",
		Argv:       []string{},
		PolicyRule: "sink",
		Decision:   decision,
	})
}

// claimStream accepts the first open, ever, and refuses every other one
// — including a later one after the first connection has closed.
func (s *sink) claimStream() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.claimed {
		return false
	}
	s.claimed = true
	return true
}

// escalationPath is where id's queue record lives under the session dir.
func (s *sink) escalationPath(id string) string {
	return filepath.Join(s.cfg.Dir, "escalations", id+".json")
}

// handleConn reads request lines and answers them in order. Every
// connection but the accepted flight stream reads under a deadline: only
// the stream is meant to sit open for a session's life.
func (s *sink) handleConn(conn net.Conn) {
	defer conn.Close()
	r := bufio.NewReader(conn)
	isStream := false

	for {
		if isStream {
			_ = conn.SetReadDeadline(time.Time{})
		} else {
			_ = conn.SetReadDeadline(time.Now().Add(otherConnDeadline))
		}
		line, err := r.ReadBytes('\n')
		if err != nil {
			if isStream {
				_ = s.writeSinkLine("stream_closed")
			}
			return
		}
		var req request
		if err := json.Unmarshal(bytes.TrimSpace(line), &req); err != nil {
			s.reply(conn, response{OK: false, Error: "sink: malformed request: " + err.Error()})
			continue
		}

		switch req.Kind {
		case "open":
			if s.claimStream() {
				isStream = true
				_ = s.writeSinkLine("stream_opened")
				s.reply(conn, response{OK: true})
			} else {
				_ = s.writeSinkLine("stream_refused")
				s.reply(conn, response{OK: false, Error: "the flight stream is taken"})
				return
			}

		case "event":
			if !isStream {
				s.reply(conn, response{OK: false, Error: "event: the flight stream is not open on this connection"})
				return
			}
			ev := recorder.Event{}
			if req.Event != nil {
				ev = *req.Event
			}
			ev.Session, ev.Role = s.cfg.Session, s.cfg.Role
			if err := s.rec.Record(ev); err != nil {
				s.reply(conn, response{OK: false, Error: err.Error()})
				continue
			}
			s.reply(conn, response{OK: true})

		case "park":
			if !isStream {
				s.reply(conn, response{OK: false, Error: "park: the flight stream is not open on this connection"})
				return
			}
			if req.Record == nil {
				s.reply(conn, response{OK: false, Error: "park: no record"})
				continue
			}
			if _, err := escalation.Create(filepath.Join(s.cfg.Dir, "escalations"), req.Record); err != nil {
				s.reply(conn, response{OK: false, Error: err.Error()})
				continue
			}
			s.reply(conn, response{OK: true})

		case "poll":
			if !isStream {
				s.reply(conn, response{OK: false, Error: "poll: the flight stream is not open on this connection"})
				return
			}
			rec, err := escalation.Load(s.escalationPath(req.ID))
			if err != nil {
				s.reply(conn, response{OK: false, Error: err.Error()})
				continue
			}
			s.reply(conn, response{OK: true, Record: rec})

		case "expire":
			if !isStream {
				s.reply(conn, response{OK: false, Error: "expire: the flight stream is not open on this connection"})
				return
			}
			rec, err := escalation.MarkExpired(s.escalationPath(req.ID), time.Now())
			if err != nil {
				s.reply(conn, response{OK: false, Error: err.Error()})
				continue
			}
			s.reply(conn, response{OK: true, Record: rec})

		case "mail":
			if !isStream {
				s.reply(conn, response{OK: false, Error: "mail: the flight stream is not open on this connection"})
				return
			}
			if req.Line == nil {
				s.reply(conn, response{OK: false, Error: "mail: no line"})
				continue
			}
			line := *req.Line
			line.Session, line.Role = s.cfg.Session, s.cfg.Role
			seq, err := AppendMail(filepath.Join(s.cfg.Dir, "mail.jsonl"), line)
			if err != nil {
				s.reply(conn, response{OK: false, Error: err.Error()})
				continue
			}
			s.reply(conn, response{OK: true, Seq: seq})

		case "edit":
			// Accepted on any connection: the edit line is not the flight
			// stream's to guard, since a doer's own hook process sends it
			// once and disconnects. Only tool and path survive.
			ev := recorder.Event{}
			if req.Event != nil {
				ev = *req.Event
			}
			if !validEditTools[ev.Tool] || ev.Path == "" {
				s.reply(conn, response{OK: false, Error: "edit: tool must be Edit, Write, MultiEdit or NotebookEdit, with a non-empty path"})
				return
			}
			clean := recorder.Event{Session: s.cfg.Session, Role: s.cfg.Role, Tool: ev.Tool, Path: ev.Path}
			if err := s.rec.Record(clean); err != nil {
				s.reply(conn, response{OK: false, Error: err.Error()})
				return
			}
			s.reply(conn, response{OK: true})
			return

		default:
			s.reply(conn, response{OK: false, Error: "sink: unknown request kind " + req.Kind})
		}
	}
}

// reply marshals and writes one response line. A write failure is
// dropped: the caller learns of a dead connection on its next read or
// write, same as any other TCP peer.
func (s *sink) reply(conn net.Conn, r response) {
	b, err := json.Marshal(r)
	if err != nil {
		return
	}
	_, _ = conn.Write(append(b, '\n'))
}
