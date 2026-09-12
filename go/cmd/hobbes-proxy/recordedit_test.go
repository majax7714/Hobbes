package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/go/internal/recorder"
)

func readFlight(t *testing.T, path string) []recorder.Event {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var events []recorder.Event
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		if line == "" {
			continue
		}
		var ev recorder.Event
		if err := json.Unmarshal([]byte(line), &ev); err != nil {
			t.Fatalf("line %q is not valid JSON: %v", line, err)
		}
		events = append(events, ev)
	}
	return events
}

func TestRecordEditWritesToolAndRelativePathNeverEditText(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "flight.jsonl")
	stdin := strings.NewReader(`{"tool_name":"Edit","tool_input":{"file_path":"/work/pkg/use.py",` +
		`"old_string":"return derive(1)","new_string":"return derive(1) * 2"},"tool_response":{"filePath":"/work/pkg/use.py"}}`)
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", logPath, "--session", "S-1", "--role", "implementer"}, stdin, &stderr)
	if code != exitOK {
		t.Fatalf("code = %d, stderr = %q", code, stderr.String())
	}

	raw, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "derive") {
		t.Errorf("the edit's text leaked into the flight log:\n%s", raw)
	}
	events := readFlight(t, logPath)
	if len(events) != 1 {
		t.Fatalf("got %d events, want 1", len(events))
	}
	ev := events[0]
	if ev.Tool != "Edit" || ev.Path != "pkg/use.py" || ev.Session != "S-1" || ev.Role != "implementer" {
		t.Errorf("event mangled: %+v", ev)
	}
	if ev.Argv != nil || ev.PolicyRule != "" || ev.Decision != "" || ev.Exit != nil {
		t.Errorf("an edit line must carry no argv, rule, decision or exit: %+v", ev)
	}
}

func TestRecordEditNotebookEditTakesNotebookPath(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "flight.jsonl")
	stdin := strings.NewReader(`{"tool_name":"NotebookEdit","tool_input":{"notebook_path":"/work/nb.ipynb","cell_id":"1"}}`)
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", logPath, "--session", "S-1", "--role", "implementer"}, stdin, &stderr)
	if code != exitOK {
		t.Fatalf("code = %d, stderr = %q", code, stderr.String())
	}
	events := readFlight(t, logPath)
	if len(events) != 1 || events[0].Path != "nb.ipynb" || events[0].Tool != "NotebookEdit" {
		t.Errorf("events = %+v", events)
	}
}

func TestRecordEditKeepsAPathOutsideWorkAsGiven(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "flight.jsonl")
	stdin := strings.NewReader(`{"tool_name":"Write","tool_input":{"file_path":"/etc/passwd"}}`)
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", logPath, "--session", "S-1", "--role", "implementer", "--work", "/work"}, stdin, &stderr)
	if code != exitOK {
		t.Fatalf("code = %d, stderr = %q", code, stderr.String())
	}
	events := readFlight(t, logPath)
	if len(events) != 1 || events[0].Path != "/etc/passwd" {
		t.Errorf("events = %+v", events)
	}
}

func TestRecordEditMalformedJSONExitsZeroAndWritesNothing(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "flight.jsonl")
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", logPath, "--session", "S-1", "--role", "implementer"},
		strings.NewReader("not json"), &stderr)
	if code != exitOK {
		t.Errorf("code = %d, want %d", code, exitOK)
	}
	if _, err := os.Stat(logPath); !os.IsNotExist(err) {
		t.Errorf("a log should not have been created: %v", err)
	}
	if stderr.Len() == 0 {
		t.Error("a diagnostic should have been printed")
	}
}

func TestRecordEditNoToolNameExitsZeroAndWritesNothing(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "flight.jsonl")
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", logPath, "--session", "S-1", "--role", "implementer"},
		strings.NewReader(`{"tool_input":{"file_path":"/work/x.py"}}`), &stderr)
	if code != exitOK {
		t.Errorf("code = %d, want %d", code, exitOK)
	}
	if _, err := os.Stat(logPath); !os.IsNotExist(err) {
		t.Errorf("a log should not have been created: %v", err)
	}
}

func TestRecordEditNoPathExitsZeroAndWritesNothing(t *testing.T) {
	logPath := filepath.Join(t.TempDir(), "flight.jsonl")
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", logPath, "--session", "S-1", "--role", "implementer"},
		strings.NewReader(`{"tool_name":"Edit","tool_input":{}}`), &stderr)
	if code != exitOK {
		t.Errorf("code = %d, want %d", code, exitOK)
	}
	if _, err := os.Stat(logPath); !os.IsNotExist(err) {
		t.Errorf("a log should not have been created: %v", err)
	}
}

func TestRecordEditUnopenableLogExitsZero(t *testing.T) {
	// A directory can never be opened as the flight log.
	dir := t.TempDir()
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--log", dir, "--session", "S-1", "--role", "implementer"},
		strings.NewReader(`{"tool_name":"Edit","tool_input":{"file_path":"/work/x.py"}}`), &stderr)
	if code != exitOK {
		t.Errorf("code = %d, want %d", code, exitOK)
	}
	if stderr.Len() == 0 {
		t.Error("a diagnostic should have been printed")
	}
}
