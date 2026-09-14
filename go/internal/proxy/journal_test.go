package proxy

import (
	"context"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
	"github.com/majax7714/Hobbes/go/internal/sink"
)

// newServerOverSink builds a proxy whose journal is a *sink.Client
// against an in-process sink.Serve — the same wire ADR-112 puts between
// a doer's container and its records. Returns the server, the sink's
// flight log path, and the session dir the sink writes under (where
// escalations park, same layout FileJournal uses).
func newServerOverSink(t *testing.T, repo string, timeout, escTimeout time.Duration) (*Server, string, string) {
	t.Helper()
	dir := t.TempDir()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- sink.Serve(ctx, ln, sink.Config{Dir: dir, Session: "S-test", Role: "implementer"})
	}()
	t.Cleanup(func() {
		cancel()
		if err := <-done; err != nil {
			t.Errorf("sink.Serve: %v", err)
		}
	})

	client := dialSinkWhenReady(t, ln.Addr().String())
	t.Cleanup(func() { client.Close() })

	s, err := New(Config{
		Session: "S-test", Role: "implementer", RepoRoot: repo,
		Timeout: timeout, EscalationTimeout: escTimeout, Journal: client,
	})
	if err != nil {
		t.Fatal(err)
	}
	return s, filepath.Join(dir, "flight.jsonl"), dir
}

// dialSinkWhenReady retries Dial for a moment: the sink's listener is
// live as soon as net.Listen returns, but Serve's own setup (opening the
// flight log, writing "listening") runs a beat behind it.
func dialSinkWhenReady(t *testing.T, addr string) *sink.Client {
	t.Helper()
	var lastErr error
	for i := 0; i < 100; i++ {
		c, err := sink.Dial(addr)
		if err == nil {
			return c
		}
		lastErr = err
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("could not dial sink at %s: %v", addr, lastErr)
	return nil
}

// nonSinkEvents drops the sink's own bookkeeping lines (listening,
// stream_opened, stream_closed) so a sink-backed test can assert the
// same event counts as the file-journal original.
func nonSinkEvents(evs []recorder.Event) []recorder.Event {
	out := make([]recorder.Event, 0, len(evs))
	for _, ev := range evs {
		if ev.Tool != "sink" {
			out = append(out, ev)
		}
	}
	return out
}

func TestApprovedEscalationRunsAndLogsApproverOverSink(t *testing.T) {
	repo := testRepo(t)
	s, logPath, dir := newServerOverSink(t, repo, 0, 10*time.Second)

	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, _, _ := s.handleExec(context.Background(), nil,
			ExecArgs{Command: "git push origin main"})
		done <- res
	}()

	path := pendingEscalation(t, dir)
	if _, err := escalation.Resolve(path, escalation.Approved, "max", time.Now()); err != nil {
		t.Fatal(err)
	}

	res := <-done
	out := text(res)
	if !strings.Contains(out, "approved by max") {
		t.Errorf("result should name the approver: %q", out)
	}
	if !strings.Contains(out, "exit ") {
		t.Errorf("approved command did not run: %q", out)
	}

	evs := nonSinkEvents(events(t, logPath))
	if len(evs) != 2 {
		t.Fatalf("want park + resolution lines, got %d: %+v", len(evs), evs)
	}
	park, resl := evs[0], evs[1]
	if park.Escalation == nil || park.Escalation.Resolution != "" {
		t.Errorf("park line = %+v", park)
	}
	if resl.Escalation == nil || resl.Escalation.Resolution != "approved" ||
		resl.Escalation.Approver != "max" {
		t.Errorf("resolution line = %+v", resl)
	}
	if park.Escalation.ID != resl.Escalation.ID {
		t.Error("park and resolution lines must share the escalation id")
	}
}

func TestDeniedEscalationRefusesWithDenierOverSink(t *testing.T) {
	repo := testRepo(t)
	s, logPath, dir := newServerOverSink(t, repo, 0, 10*time.Second)

	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, _, _ := s.handleExec(context.Background(), nil,
			ExecArgs{Command: "git push origin main"})
		done <- res
	}()
	path := pendingEscalation(t, dir)
	if _, err := escalation.Resolve(path, escalation.Denied, "max", time.Now()); err != nil {
		t.Fatal(err)
	}

	res := <-done
	if !res.IsError || !strings.Contains(text(res), "denied by max") {
		t.Errorf("want denial naming the denier, got %q", text(res))
	}
	evs := nonSinkEvents(events(t, logPath))
	if len(evs) != 2 || evs[1].Escalation.Resolution != "denied" || evs[1].Exit != nil {
		t.Errorf("flight lines = %+v", evs)
	}
}

func TestUnansweredEscalationExpiresToDenyOverSink(t *testing.T) {
	repo := testRepo(t)
	s, logPath, dir := newServerOverSink(t, repo, 0, 300*time.Millisecond)

	start := time.Now()
	res := callExec(t, s, ExecArgs{Command: "git push origin main"})
	if elapsed := time.Since(start); elapsed > 3*time.Second {
		t.Fatalf("expiry took %s", elapsed)
	}
	if !res.IsError || !strings.Contains(text(res), "expired") {
		t.Errorf("want expiry refusal, got %q", text(res))
	}

	record, err := escalation.Load(pendingEscalation(t, dir))
	if err != nil {
		t.Fatal(err)
	}
	if record.Status != escalation.Expired {
		t.Errorf("record status = %q, want expired", record.Status)
	}
	evs := nonSinkEvents(events(t, logPath))
	if len(evs) != 2 || evs[1].Escalation.Resolution != "expired" ||
		evs[1].Escalation.Approver != "" {
		t.Errorf("flight lines = %+v", evs)
	}
}

func TestDisconnectWhileParkedSettlesRecordOverSink(t *testing.T) {
	repo := testRepo(t)
	s, logPath, dir := newServerOverSink(t, repo, 0, 10*time.Second)

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, _, _ := s.handleExec(ctx, nil, ExecArgs{Command: "git push origin main"})
		done <- res
	}()
	path := pendingEscalation(t, dir)
	cancel()

	res := <-done
	if !res.IsError || !strings.Contains(text(res), "session ended") {
		t.Errorf("want disconnect refusal, got %q", text(res))
	}
	record, err := escalation.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if record.Status != escalation.Expired {
		t.Errorf("record left %q; a dead session must not leave approvable commands", record.Status)
	}
	evs := nonSinkEvents(events(t, logPath))
	if len(evs) != 2 || evs[1].Escalation.Resolution != "expired" {
		t.Errorf("flight lines = %+v", evs)
	}
}

func TestReflectOverSink(t *testing.T) {
	repo := testRepo(t)
	s, logPath, dir := newServerOverSink(t, repo, 0, 400*time.Millisecond)

	if out := s.reflect("  ", ""); !out.IsError {
		t.Errorf("empty reflect accepted")
	}
	s.reflect("K1 pins a site that moved", "")
	out := s.reflect("done: 2 commits", ReflectHandoff)
	if out.IsError || !strings.Contains(text(out), "handoff (#2)") {
		t.Errorf("second reflect = %q", text(out))
	}

	data, err := os.ReadFile(filepath.Join(dir, "mail.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if len(lines) != 2 || !strings.Contains(lines[0], `"seq":1`) || !strings.Contains(lines[0], `"kind":"progress"`) ||
		!strings.Contains(lines[1], `"seq":2`) || !strings.Contains(lines[1], `"kind":"handoff"`) ||
		!strings.Contains(lines[1], `"role":"implementer"`) || !strings.Contains(lines[1], "done: 2 commits") {
		t.Errorf("mail.jsonl = %q", string(data))
	}

	evs := nonSinkEvents(events(t, logPath))
	if len(evs) != 2 || evs[0].Tool != "reflect" || evs[0].PolicyRule != "builtin:mail" ||
		evs[0].Argv[1] != "K1 pins a site that moved" {
		t.Errorf("reflect events = %+v", evs)
	}
}
