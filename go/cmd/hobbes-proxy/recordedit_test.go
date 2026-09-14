package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/majax7714/Hobbes/go/internal/recorder"
	"github.com/majax7714/Hobbes/go/internal/sink"
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

func waitForSinkListening(t *testing.T, flightLog string) {
	t.Helper()
	for i := 0; i < 200; i++ {
		if data, err := os.ReadFile(flightLog); err == nil && len(strings.TrimSpace(string(data))) > 0 {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("sink never wrote %s", flightLog)
}

func TestRecordEditSinkLandsTheLine(t *testing.T) {
	dir := t.TempDir()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- sink.Serve(ctx, ln, sink.Config{Dir: dir, Session: "S-1", Role: "implementer"}) }()
	defer func() {
		cancel()
		if err := <-done; err != nil {
			t.Errorf("sink.Serve: %v", err)
		}
	}()
	flightLog := filepath.Join(dir, "flight.jsonl")
	waitForSinkListening(t, flightLog)

	stdin := strings.NewReader(`{"tool_name":"Edit","tool_input":{"file_path":"/work/pkg/use.py"}}`)
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--sink", ln.Addr().String(), "--session", "S-1", "--role", "implementer"}, stdin, &stderr)
	if code != exitOK {
		t.Fatalf("code = %d, stderr = %q", code, stderr.String())
	}

	var events []recorder.Event
	for i := 0; i < 200; i++ {
		events = readFlight(t, flightLog)
		if len(events) >= 2 {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	found := false
	for _, ev := range events {
		if ev.Tool == "Edit" && ev.Path == "pkg/use.py" {
			found = true
		}
	}
	if !found {
		t.Errorf("edit line missing from the sink's flight log: %+v", events)
	}
}

func TestRecordEditSinkUnreachableExitsZero(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := ln.Addr().String()
	ln.Close()

	stdin := strings.NewReader(`{"tool_name":"Edit","tool_input":{"file_path":"/work/x.py"}}`)
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--sink", addr, "--session", "S-1", "--role", "implementer"}, stdin, &stderr)
	if code != exitOK {
		t.Errorf("code = %d, want %d", code, exitOK)
	}
	if stderr.Len() == 0 {
		t.Error("a diagnostic should have been printed")
	}
}

func TestRecordEditRequiresExactlyOneOfLogOrSink(t *testing.T) {
	var stderr bytes.Buffer
	code := runRecordEdit([]string{"--session", "S-1", "--role", "implementer"},
		strings.NewReader(`{"tool_name":"Edit","tool_input":{"file_path":"/work/x.py"}}`), &stderr)
	if code != exitOK || stderr.Len() == 0 {
		t.Errorf("neither --log nor --sink: code=%d stderr=%q", code, stderr.String())
	}

	stderr.Reset()
	code = runRecordEdit([]string{"--log", filepath.Join(t.TempDir(), "f.jsonl"), "--sink", "127.0.0.1:1",
		"--session", "S-1", "--role", "implementer"},
		strings.NewReader(`{"tool_name":"Edit","tool_input":{"file_path":"/work/x.py"}}`), &stderr)
	if code != exitOK || stderr.Len() == 0 {
		t.Errorf("both --log and --sink: code=%d stderr=%q", code, stderr.String())
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
