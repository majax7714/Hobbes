package recorder

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func readLines(t *testing.T, path string) []Event {
	t.Helper()
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	var events []Event
	scanner := bufio.NewScanner(f)
	scanner.Buffer(make([]byte, 1024*1024), 1024*1024)
	for scanner.Scan() {
		var ev Event
		if err := json.Unmarshal(scanner.Bytes(), &ev); err != nil {
			t.Fatalf("line %d is not valid JSON: %v", len(events)+1, err)
		}
		events = append(events, ev)
	}
	if err := scanner.Err(); err != nil {
		t.Fatal(err)
	}
	return events
}

func TestOpenCreatesParentsAndRestrictsMode(t *testing.T) {
	path := filepath.Join(t.TempDir(), "sessions", "S-1", "flight.jsonl")
	r, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if perm := info.Mode().Perm(); perm != 0o600 {
		t.Errorf("log file mode = %o, want 600", perm)
	}
}

func TestRecordRoundTripsFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "flight.jsonl")
	r, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	exit := 0
	ev := Event{
		Session:    "S-1",
		Role:       "implementer",
		Tool:       "exec",
		Argv:       []string{"/bin/sh", "-c", "echo hi"},
		PolicyRule: "repo.policy: echo *",
		Decision:   "allow",
		Exit:       &exit,
		SHA:        "abc123",
	}
	if err := r.Record(ev); err != nil {
		t.Fatal(err)
	}

	events := readLines(t, path)
	if len(events) != 1 {
		t.Fatalf("got %d events, want 1", len(events))
	}
	got := events[0]
	if got.Session != "S-1" || got.Role != "implementer" || got.Tool != "exec" {
		t.Errorf("identity fields mangled: %+v", got)
	}
	if len(got.Argv) != 3 || got.Argv[2] != "echo hi" {
		t.Errorf("argv mangled: %v", got.Argv)
	}
	if got.Exit == nil || *got.Exit != 0 {
		t.Errorf("exit mangled: %v", got.Exit)
	}
	if _, err := time.Parse(time.RFC3339Nano, got.TS); err != nil {
		t.Errorf("auto-filled ts %q is not RFC3339Nano: %v", got.TS, err)
	}
}

func TestNilExitSerializesAsNull(t *testing.T) {
	path := filepath.Join(t.TempDir(), "flight.jsonl")
	r, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	if err := r.Record(Event{Decision: "deny"}); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var loose map[string]any
	if err := json.Unmarshal(raw, &loose); err != nil {
		t.Fatal(err)
	}
	val, present := loose["exit"]
	if !present || val != nil {
		t.Errorf(`want explicit "exit": null for a refusal, got %v (present=%v)`, val, present)
	}
}

func TestEscalationFieldOmittedUnlessSet(t *testing.T) {
	path := filepath.Join(t.TempDir(), "flight.jsonl")
	r, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()
	if err := r.Record(Event{Decision: "allow"}); err != nil {
		t.Fatal(err)
	}
	if err := r.Record(Event{
		Decision:   "escalate",
		Escalation: &EscalationRef{ID: "E-1", Resolution: "approved", Approver: "max"},
	}); err != nil {
		t.Fatal(err)
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	if strings.Contains(lines[0], "escalation") {
		t.Errorf("plain event must omit the escalation field: %s", lines[0])
	}
	got := readLines(t, path)[1]
	if got.Escalation == nil || got.Escalation.Approver != "max" ||
		got.Escalation.Resolution != "approved" {
		t.Errorf("escalation ref mangled: %+v", got.Escalation)
	}
}

func TestReopenAppendsRatherThanTruncates(t *testing.T) {
	path := filepath.Join(t.TempDir(), "flight.jsonl")
	for i := 0; i < 2; i++ {
		r, err := Open(path)
		if err != nil {
			t.Fatal(err)
		}
		if err := r.Record(Event{Session: "S-1", Decision: "allow"}); err != nil {
			t.Fatal(err)
		}
		if err := r.Close(); err != nil {
			t.Fatal(err)
		}
	}
	if events := readLines(t, path); len(events) != 2 {
		t.Fatalf("got %d events after two open/record/close cycles, want 2", len(events))
	}
}

func TestConcurrentRecordsDoNotInterleave(t *testing.T) {
	path := filepath.Join(t.TempDir(), "flight.jsonl")
	r, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer r.Close()

	const n = 50
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = r.Record(Event{Session: "S-1", Tool: "exec", Decision: "allow"})
		}()
	}
	wg.Wait()

	// readLines fails the test on any malformed (interleaved) line.
	if events := readLines(t, path); len(events) != n {
		t.Fatalf("got %d events, want %d", len(events), n)
	}
}
