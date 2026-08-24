// Package recorder implements the Hobbes flight recorder: an append-only
// JSONL audit log, one file per agent session, one line per proxied tool
// call (architecture §9, ADR-015). The recorder only ever appends — it
// never reads, rewrites, or truncates — and fsyncs every event, because
// the log is the audit trail for commands that may have mutated the repo.
package recorder

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// EscalationRef ties a flight line to an escalation record (ADR-016).
// A park line carries only ID; the resolution line adds the human's
// verdict and, for approve/deny, who gave it.
type EscalationRef struct {
	ID         string `json:"id"`
	Resolution string `json:"resolution,omitempty"` // approved | denied | expired
	Approver   string `json:"approver,omitempty"`
}

// Event is one flight-recorder line. The field set is fixed by
// architecture §9 and ADR-015; widening it is a doc change first
// (the escalation field was added by ADR-016 for §9's "approvals log
// the approver").
type Event struct {
	// TS is the event time, RFC3339Nano UTC. Record fills it when empty.
	TS string `json:"ts"`
	// Session and Role identify the agent session the proxy serves.
	Session string `json:"session"`
	Role    string `json:"role"`
	// Tool is the MCP tool that produced the event (e.g. "exec").
	Tool string `json:"tool"`
	// Argv is the literal execve vector that ran — or, for a refusal,
	// would have run.
	Argv []string `json:"argv"`
	// PolicyRule is "<source>: <pattern>" of the decisive rule, or
	// "default:<source>" / "default:engine" when a default applied.
	PolicyRule string `json:"policy_rule"`
	// Decision is the policy outcome: allow, deny, or escalate.
	Decision string `json:"decision"`
	// Exit is the process exit code; nil when nothing ran.
	Exit *int `json:"exit"`
	// SHA is the repo HEAD at event time.
	SHA string `json:"sha"`
	// Escalation is set on the two lines of a parked command (ADR-016).
	Escalation *EscalationRef `json:"escalation,omitempty"`
	// ContextFault is set on a knowledge query for a node outside the
	// session's context manifest (agent-mapping §4, ADR-054): the
	// allocator predicted this agent would not need it, and it did. The
	// query is served anyway; the flag is the partition's error signal.
	ContextFault bool `json:"context_fault,omitempty"`
}

// Recorder appends events to one session's flight log. Safe for
// concurrent use.
type Recorder struct {
	mu   sync.Mutex
	file *os.File
}

// Open opens (creating parents as needed) the flight log at path for
// appending. The file is created 0600: session logs are personal
// (ADR-012) and may quote sensitive command lines.
func Open(path string) (*Recorder, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, fmt.Errorf("flight recorder: %w", err)
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, fmt.Errorf("flight recorder: %w", err)
	}
	return &Recorder{file: f}, nil
}

// Record appends one event as a single JSON line and fsyncs. An empty
// TS is filled with the current time.
func (r *Recorder) Record(ev Event) error {
	if ev.TS == "" {
		ev.TS = time.Now().UTC().Format(time.RFC3339Nano)
	}
	line, err := json.Marshal(ev)
	if err != nil {
		return fmt.Errorf("flight recorder: %w", err)
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, err := r.file.Write(append(line, '\n')); err != nil {
		return fmt.Errorf("flight recorder: %w", err)
	}
	if err := r.file.Sync(); err != nil {
		return fmt.Errorf("flight recorder: %w", err)
	}
	return nil
}

// Close closes the underlying file.
func (r *Recorder) Close() error {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.file.Close()
}
