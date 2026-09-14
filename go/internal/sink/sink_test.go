package sink

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// startSink runs Serve on a loopback listener in the background, waits
// for its "listening" line, and returns its address and dir. The server
// is stopped and its exit checked when the test ends.
func startSink(t *testing.T, cfg Config) (addr, dir string) {
	t.Helper()
	if cfg.Dir == "" {
		cfg.Dir = t.TempDir()
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- Serve(ctx, ln, cfg) }()
	t.Cleanup(func() {
		cancel()
		if err := <-done; err != nil {
			t.Errorf("sink.Serve: %v", err)
		}
	})
	waitForLines(t, filepath.Join(cfg.Dir, "flight.jsonl"), 1)
	return ln.Addr().String(), cfg.Dir
}

func flightLines(t *testing.T, path string) []recorder.Event {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		t.Fatal(err)
	}
	var evs []recorder.Event
	for _, line := range bytes.Split(bytes.TrimSpace(data), []byte("\n")) {
		if len(line) == 0 {
			continue
		}
		var ev recorder.Event
		if err := json.Unmarshal(line, &ev); err != nil {
			t.Fatalf("bad flight line %q: %v", line, err)
		}
		evs = append(evs, ev)
	}
	return evs
}

func waitForLines(t *testing.T, path string, n int) []recorder.Event {
	t.Helper()
	for i := 0; i < 200; i++ {
		if evs := flightLines(t, path); len(evs) >= n {
			return evs
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %d lines in %s", n, path)
	return nil
}

func TestListeningIsTheFirstLine(t *testing.T) {
	_, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	evs := waitForLines(t, filepath.Join(dir, "flight.jsonl"), 1)
	ev := evs[0]
	if ev.Tool != "sink" || ev.Decision != "listening" || ev.PolicyRule != "sink" {
		t.Errorf("first line = %+v", ev)
	}
	if ev.Session != "S-1" || ev.Role != "implementer" {
		t.Errorf("first line not stamped from config: %+v", ev)
	}
	if ev.Argv == nil {
		t.Error("argv should be an empty slice, not nil")
	}
}

func TestOneStreamEverASecondOpenIsRefused(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	first, err := Dial(addr)
	if err != nil {
		t.Fatalf("first open: %v", err)
	}
	defer first.Close()

	_, err = Dial(addr)
	if err == nil {
		t.Fatal("second open should have been refused")
	}
	if !bytes.Contains([]byte(err.Error()), []byte("taken")) {
		t.Errorf("refusal error = %q, want it to mention the stream is taken", err)
	}

	evs := waitForLines(t, filepath.Join(dir, "flight.jsonl"), 3)
	var sawRefused bool
	for _, ev := range evs {
		if ev.Tool == "sink" && ev.Decision == "stream_refused" {
			sawRefused = true
		}
	}
	if !sawRefused {
		t.Errorf("no stream_refused line recorded: %+v", evs)
	}
}

func TestBracketOrderingAndEventStamping(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	c, err := Dial(addr)
	if err != nil {
		t.Fatal(err)
	}
	ts := "2020-01-01T00:00:00Z"
	if err := c.Record(recorder.Event{
		TS: ts, Session: "forged-session", Role: "forged-role",
		Tool: "exec", Decision: "allow",
	}); err != nil {
		t.Fatal(err)
	}
	if err := c.Close(); err != nil {
		t.Fatal(err)
	}

	evs := waitForLines(t, filepath.Join(dir, "flight.jsonl"), 4)
	if len(evs) != 4 {
		t.Fatalf("got %d lines, want 4: %+v", len(evs), evs)
	}
	if evs[0].Decision != "listening" {
		t.Errorf("line 0 = %+v, want listening", evs[0])
	}
	if evs[1].Decision != "stream_opened" {
		t.Errorf("line 1 = %+v, want stream_opened", evs[1])
	}
	event := evs[2]
	if event.Tool != "exec" || event.Decision != "allow" {
		t.Errorf("line 2 = %+v, want the recorded event", event)
	}
	if event.TS != ts {
		t.Errorf("ts = %q, want it kept as sent: %q", event.TS, ts)
	}
	if event.Session != "S-1" || event.Role != "implementer" {
		t.Errorf("event stamped from the message, not the sink's config: %+v", event)
	}
	if evs[3].Decision != "stream_closed" {
		t.Errorf("line 3 = %+v, want stream_closed", evs[3])
	}
}

func dialRaw(t *testing.T, addr string) (net.Conn, *bufio.Reader) {
	t.Helper()
	conn, err := net.Dial("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	return conn, bufio.NewReader(conn)
}

func sendLine(t *testing.T, conn net.Conn, v any) {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Write(append(b, '\n')); err != nil {
		t.Fatal(err)
	}
}

func readReply(t *testing.T, r *bufio.Reader) response {
	t.Helper()
	line, err := r.ReadBytes('\n')
	if err != nil {
		t.Fatal(err)
	}
	var resp response
	if err := json.Unmarshal(bytes.TrimSpace(line), &resp); err != nil {
		t.Fatal(err)
	}
	return resp
}

func TestRequestBeforeOpenIsRefusedAndClosed(t *testing.T) {
	addr, _ := startSink(t, Config{Session: "S-1", Role: "implementer"})
	conn, r := dialRaw(t, addr)
	defer conn.Close()
	sendLine(t, conn, map[string]any{"kind": "event", "event": map[string]any{"tool": "exec"}})
	resp := readReply(t, r)
	if resp.OK {
		t.Fatal("a request before open should be refused")
	}
	conn.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := r.ReadByte(); err == nil {
		t.Error("connection should have been closed after the refusal")
	}
}

func TestEditRequestsKeepOnlyToolAndPath(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	flightPath := filepath.Join(dir, "flight.jsonl")

	// A well-formed edit keeps tool and path only.
	conn, r := dialRaw(t, addr)
	sendLine(t, conn, map[string]any{"kind": "edit", "event": map[string]any{"tool": "Edit", "path": "pkg/x.py"}})
	if resp := readReply(t, r); !resp.OK {
		t.Fatalf("good edit refused: %+v", resp)
	}
	conn.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := r.ReadByte(); err == nil {
		t.Error("connection should be closed after an edit reply")
	}
	conn.Close()

	evs := waitForLines(t, flightPath, 2)
	last := evs[len(evs)-1]
	if last.Tool != "Edit" || last.Path != "pkg/x.py" {
		t.Errorf("edit line = %+v", last)
	}

	// An exec-shaped edit is stripped to tool and path.
	conn2, r2 := dialRaw(t, addr)
	exit := 1
	sendLine(t, conn2, map[string]any{"kind": "edit", "event": map[string]any{
		"tool": "Write", "path": "pkg/y.py", "argv": []string{"/bin/sh", "-c", "rm -rf /"},
		"decision": "allow", "policy_rule": "repo.policy: rm *", "exit": exit,
	}})
	if resp := readReply(t, r2); !resp.OK {
		t.Fatalf("exec-shaped edit refused: %+v", resp)
	}
	conn2.Close()

	evs = waitForLines(t, flightPath, 3)
	last = evs[len(evs)-1]
	if last.Tool != "Write" || last.Path != "pkg/y.py" {
		t.Errorf("stripped edit line = %+v", last)
	}
	if len(last.Argv) != 0 || last.PolicyRule != "" || last.Decision != "" || last.Exit != nil {
		t.Errorf("edit line must clear every non tool/path field: %+v", last)
	}

	before := len(waitForLines(t, flightPath, 3))

	// A tool outside the four is refused with nothing written.
	conn3, r3 := dialRaw(t, addr)
	sendLine(t, conn3, map[string]any{"kind": "edit", "event": map[string]any{"tool": "Exec", "path": "pkg/z.py"}})
	if resp := readReply(t, r3); resp.OK {
		t.Fatal("edit with a disallowed tool should be refused")
	}
	conn3.SetReadDeadline(time.Now().Add(time.Second))
	if _, err := r3.ReadByte(); err == nil {
		t.Error("connection should be closed after a refused edit")
	}
	conn3.Close()

	// An empty path is refused with nothing written.
	conn4, r4 := dialRaw(t, addr)
	sendLine(t, conn4, map[string]any{"kind": "edit", "event": map[string]any{"tool": "Edit", "path": ""}})
	if resp := readReply(t, r4); resp.OK {
		t.Fatal("edit with an empty path should be refused")
	}
	conn4.Close()

	time.Sleep(50 * time.Millisecond)
	if got := len(flightLines(t, flightPath)); got != before {
		t.Errorf("refused edits should write nothing, flight log grew from %d to %d", before, got)
	}
}

func TestParkPollExpireRoundTrip(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	c, err := Dial(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	rec, err := escalation.NewRecord("S-1", "implementer", "/repo", "git push origin main",
		"", "repo.policy: git push*", "pushes need a human", time.Now(), 10*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Park(rec); err != nil {
		t.Fatal(err)
	}
	got, err := c.Poll(rec.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != escalation.Pending {
		t.Errorf("status = %q, want pending", got.Status)
	}

	path := filepath.Join(dir, "escalations", rec.ID+".json")
	if _, err := escalation.Resolve(path, escalation.Approved, "max", time.Now()); err != nil {
		t.Fatal(err)
	}
	got, err = c.Poll(rec.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != escalation.Approved || got.Approver != "max" {
		t.Errorf("polled record after host resolve = %+v", got)
	}

	rec2, err := escalation.NewRecord("S-1", "implementer", "/repo", "git push origin main",
		"", "repo.policy: git push*", "pushes need a human", time.Now(), 10*time.Minute)
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Park(rec2); err != nil {
		t.Fatal(err)
	}
	expired, err := c.Expire(rec2.ID)
	if err != nil {
		t.Fatal(err)
	}
	if expired.Status != escalation.Expired {
		t.Errorf("expired record = %+v", expired)
	}
}

func TestMailSequencing(t *testing.T) {
	addr, dir := startSink(t, Config{Session: "S-1", Role: "implementer"})
	c, err := Dial(addr)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	seq1, err := c.Mail(MailLine{TS: "t1", Kind: "progress", Text: "first"})
	if err != nil {
		t.Fatal(err)
	}
	if seq1 != 1 {
		t.Errorf("seq1 = %d, want 1", seq1)
	}
	seq2, err := c.Mail(MailLine{TS: "t2", Kind: "handoff", Text: "second"})
	if err != nil {
		t.Fatal(err)
	}
	if seq2 != 2 {
		t.Errorf("seq2 = %d, want 2", seq2)
	}

	data, err := os.ReadFile(filepath.Join(dir, "mail.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	lines := bytes.Split(bytes.TrimSpace(data), []byte("\n"))
	if len(lines) != 2 {
		t.Fatalf("mail.jsonl has %d lines, want 2: %s", len(lines), data)
	}
}
