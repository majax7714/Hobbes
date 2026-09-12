package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"path/filepath"
	"strings"

	"github.com/majax7714/Hobbes/go/internal/recorder"
	"github.com/majax7714/Hobbes/go/internal/sandbox"
)

// maxHookInput caps the PostToolUse hook payload this command reads.
// Claude Code's own edit tools do not send anything close to this; the
// cap is a guard against a malformed or hostile hook invocation, not a
// realistic ceiling.
const maxHookInput = 64 << 20 // 64 MiB

// hookInput is the subset of Claude Code's PostToolUse hook payload this
// command decodes. Every other field the hook sends — old_string,
// new_string, content, edits, tool_response — carries the edit's own
// text and is deliberately absent here: ADR-107's retention rule is that
// the flight line keeps a tool's name and path, never its content.
type hookInput struct {
	ToolName  string `json:"tool_name"`
	ToolInput struct {
		FilePath     string `json:"file_path"`
		NotebookPath string `json:"notebook_path"`
	} `json:"tool_input"`
}

// runRecordEdit is `hobbes-proxy record-edit` (ADR-107, the progress
// hook): a Claude Code PostToolUse hook, run for Edit, Write, MultiEdit
// and NotebookEdit, that reads the hook's JSON on stdin and appends one
// flight-recorder line naming the edited tool and path — never the
// edit's content. It always exits 0: a hook's failure must never stop
// the doer, so every fault (bad flags, unreadable or malformed stdin, no
// tool_name, no path, an unopenable log) is a stderr line and nothing
// recorded, rather than a non-zero exit.
func runRecordEdit(args []string, stdin io.Reader, stderr io.Writer) int {
	fs := flag.NewFlagSet("record-edit", flag.ContinueOnError)
	fs.SetOutput(stderr)
	logFlag := fs.String("log", "", "flight log to append to (required)")
	sessionFlag := fs.String("session", "", "session id (required)")
	roleFlag := fs.String("role", "", "session role (required)")
	workFlag := fs.String("work", sandbox.WorkDir, "the worktree root a path is made relative to")
	if err := fs.Parse(args); err != nil {
		return exitOK
	}
	if *logFlag == "" || *sessionFlag == "" || *roleFlag == "" {
		fmt.Fprintln(stderr, "hobbes-proxy record-edit: --log, --session and --role are required")
		return exitOK
	}

	data, err := io.ReadAll(io.LimitReader(stdin, maxHookInput))
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy record-edit: reading stdin: %v\n", err)
		return exitOK
	}
	var in hookInput
	if err := json.Unmarshal(data, &in); err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy record-edit: malformed hook input: %v\n", err)
		return exitOK
	}
	if in.ToolName == "" {
		fmt.Fprintln(stderr, "hobbes-proxy record-edit: no tool_name in the hook input")
		return exitOK
	}
	path := in.ToolInput.FilePath
	if path == "" {
		path = in.ToolInput.NotebookPath
	}
	if path == "" {
		fmt.Fprintln(stderr, "hobbes-proxy record-edit: no file_path or notebook_path in the hook input")
		return exitOK
	}

	rec, err := recorder.Open(*logFlag)
	if err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy record-edit: %v\n", err)
		return exitOK
	}
	defer rec.Close()
	if err := rec.Record(recorder.Event{
		Session: *sessionFlag,
		Role:    *roleFlag,
		Tool:    in.ToolName,
		Path:    relativeToWork(path, *workFlag),
	}); err != nil {
		fmt.Fprintf(stderr, "hobbes-proxy record-edit: %v\n", err)
	}
	return exitOK
}

// relativeToWork rewrites path relative to work, slash-separated, when
// it lies under work; a path outside it (or one Rel cannot compute) is
// kept exactly as the hook gave it.
func relativeToWork(path, work string) string {
	rel, err := filepath.Rel(work, path)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return path
	}
	return filepath.ToSlash(rel)
}
