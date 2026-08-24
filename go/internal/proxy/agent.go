// The agent dir's two runtime inputs (ADR-054): the context manifest a
// session's knowledge queries are judged against, and the reflect tool —
// the short-term channel back to the orchestrator.
package proxy

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// contextManifest is <agent-dir>/context.json: the slice of the graph a
// unit's agent was allocated (agent-mapping §4). Ids are graph node ids;
// Paths are the repo-relative files of the interior.
type contextManifest struct {
	Unit         string   `json:"unit"`
	Interior     []string `json:"interior"`
	Boundary     []string `json:"boundary"`
	Neighborhood []string `json:"neighborhood"`
	Paths        []string `json:"paths"`
}

// loadManifest reads a context manifest; a missing file is nil, not an
// error (an agent dir may carry only a policy).
func loadManifest(path string) (*contextManifest, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var m contextManifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return &m, nil
}

// covers reports whether a knowledge query lies inside the manifest: an
// id in interior, boundary, or neighborhood; a symbol under one of those
// modules (<id>.name); or a path inside (or enclosing) an interior file.
func (m *contextManifest) covers(query string) bool {
	for _, ids := range [][]string{m.Interior, m.Boundary, m.Neighborhood} {
		for _, id := range ids {
			if query == id || strings.HasPrefix(query, id+".") {
				return true
			}
		}
	}
	if strings.ContainsAny(query, "/.") {
		q := strings.TrimSuffix(query, "/")
		for _, p := range m.Paths {
			if p == q || strings.HasPrefix(p, q+"/") || strings.HasPrefix(q, p) {
				return true
			}
		}
	}
	return false
}

// ReflectArgs is the reflect tool's input schema.
type ReflectArgs struct {
	Text string `json:"text" jsonschema:"a message back to the orchestrator: a blocked contract, a needed specific, or a result summary — this is the short-term channel; it lands in the orchestrator's inbox and is recorded"`
	Kind string `json:"kind,omitempty" jsonschema:"progress (default) or handoff — send exactly one handoff when your job is done; only the handoff is forwarded to the next agent, progress lines stay in the record"`
}

// Reflection kinds. A handoff is the one message the next agent's short
// memory receives; everything else is progress, kept in the record.
const (
	ReflectProgress = "progress"
	ReflectHandoff  = "handoff"
)

// mailLine is one line of <session-dir>/mail.jsonl.
type mailLine struct {
	Seq     int    `json:"seq"`
	TS      string `json:"ts"`
	Session string `json:"session"`
	Role    string `json:"role"`
	Kind    string `json:"kind"`
	Text    string `json:"text"`
}

// addReflectTool registers reflect: the session's only outbound channel
// besides its commits. Agents never talk to each other (agent-mapping
// §8); they reflect to the orchestrator, which reads the session's
// mail.jsonl after the run.
func (s *Server) addReflectTool(srv *mcp.Server) {
	mcp.AddTool(srv, &mcp.Tool{
		Name: "reflect",
		Description: "Send a message back to the orchestrator — a blocked or " +
			"wrong contract, a specific you need that your context lacks, or a " +
			"summary of what you did. This is the short-term channel (the " +
			"orchestrator's inbox); commits are the standing one. Recorded.",
	}, func(ctx context.Context, _ *mcp.CallToolRequest, args ReflectArgs) (*mcp.CallToolResult, any, error) {
		return s.reflect(args.Text, args.Kind), nil, nil
	})
}

// reflect appends one mail line and logs the event.
func (s *Server) reflect(textArg, kind string) *mcp.CallToolResult {
	switch kind {
	case "", ReflectProgress:
		kind = ReflectProgress
	case ReflectHandoff:
	default:
		return errResult("reflect: kind must be %q or %q", ReflectProgress, ReflectHandoff)
	}
	ev := recorder.Event{
		Session:    s.cfg.Session,
		Role:       s.cfg.Role,
		Tool:       "reflect",
		Argv:       []string{kind, textArg},
		PolicyRule: "builtin:mail",
		Decision:   "allow",
		SHA:        headSHA(s.cfg.RepoRoot),
	}
	if strings.TrimSpace(textArg) == "" {
		return errResult("reflect: empty message")
	}
	seq, err := appendMail(filepath.Join(s.cfg.SessionDir, "mail.jsonl"), mailLine{
		TS: time.Now().UTC().Format(time.RFC3339Nano), Session: s.cfg.Session,
		Role: s.cfg.Role, Kind: kind, Text: textArg,
	})
	if err != nil {
		return s.record(ev, errResult("reflect: %v", err))
	}
	return s.record(ev, &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("reflected %s (#%d) to the orchestrator's inbox", kind, seq)}},
	})
}

// appendMail appends line to path with seq = existing lines + 1; returns
// the seq. The file is 0600 like the flight log (ADR-012).
func appendMail(path string, line mailLine) (int, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return 0, err
	}
	seq := 1
	if f, err := os.Open(path); err == nil {
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			if strings.TrimSpace(sc.Text()) != "" {
				seq++
			}
		}
		f.Close()
	}
	line.Seq = seq
	data, err := json.Marshal(line)
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
