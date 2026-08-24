package proxy

// Protocol-level tests: a real MCP client and server wired over the SDK's
// in-memory transport pair — the same code path Claude Code exercises over
// stdio (ADR-013), minus the pipes.

import (
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/majax7714/Hobbes/go/internal/escalation"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

func connect(t *testing.T, s *Server) *mcp.ClientSession {
	t.Helper()
	ctx := context.Background()
	clientT, serverT := mcp.NewInMemoryTransports()
	if _, err := s.MCP().Connect(ctx, serverT, nil); err != nil {
		t.Fatal(err)
	}
	client := mcp.NewClient(&mcp.Implementation{Name: "test-client", Version: "0.0.0"}, nil)
	session, err := client.Connect(ctx, clientT, nil)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { session.Close() })
	return session
}

func TestSessionToolSurface(t *testing.T) {
	s, _ := newServer(t, testRepo(t), 0)
	session := connect(t, s)
	tools, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	names := map[string]string{}
	for _, tool := range tools.Tools {
		names[tool.Name] = tool.Description
	}
	// exec plus the knowledge tools architecture §6 names —
	// list_invariants joined at M8, when its data arrived, and
	// list_blind_spots at ADR-047, when the tail view gave it data:
	// the captured fraction's tools plus the one that serves its
	// boundary. reflect (ADR-054) is the short-term channel back to the
	// orchestrator.
	want := []string{
		"exec", "graph_neighborhood", "who_calls", "tests_guarding",
		"get_module_doc", "list_invariants", "list_blind_spots", "reflect",
	}
	for _, name := range want {
		if _, ok := names[name]; !ok {
			t.Errorf("tool %s missing from %v", name, names)
		}
	}
	if len(tools.Tools) != len(want) {
		t.Errorf("unexpected extra tools: %v", names)
	}
	if !strings.Contains(names["exec"], "policy") {
		t.Error("exec description should warn the agent about policy gating")
	}
}

// TestKnowledgeOnlySurface: with KnowledgeOnly the mutating tools are
// absent from the list, not present-and-refusing (ADR-087; the sandbox
// rule that a forbidden command is absent, applied to a host session).
func TestKnowledgeOnlySurface(t *testing.T) {
	repo := testRepo(t)
	sessionDir := t.TempDir()
	rec, err := recorder.Open(filepath.Join(sessionDir, "flight.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { rec.Close() })
	s, err := New(Config{Session: "S-k", Role: "developer", RepoRoot: repo,
		SessionDir: sessionDir, Rec: rec, KnowledgeOnly: true})
	if err != nil {
		t.Fatal(err)
	}
	session := connect(t, s)
	tools, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]bool{}
	for _, tool := range tools.Tools {
		got[tool.Name] = true
	}
	for _, name := range []string{"graph_neighborhood", "who_calls", "tests_guarding",
		"get_module_doc", "list_invariants", "list_blind_spots"} {
		if !got[name] {
			t.Errorf("knowledge tool %s missing from %v", name, got)
		}
	}
	for _, name := range []string{"exec", "reflect"} {
		if got[name] {
			t.Errorf("%s must be absent in knowledge-only mode, got %v", name, got)
		}
	}
	if len(tools.Tools) != 6 {
		t.Errorf("want exactly 6 tools, got %d", len(tools.Tools))
	}
}

func TestRoundTripAllowAndDenyAreLogged(t *testing.T) {
	s, logPath := newServer(t, testRepo(t), 0)
	session := connect(t, s)
	ctx := context.Background()

	allowed, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "exec",
		Arguments: map[string]any{"command": "echo over-the-wire"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if allowed.IsError || !strings.Contains(text(allowed), "over-the-wire") {
		t.Errorf("allowed call: isError=%v text=%q", allowed.IsError, text(allowed))
	}

	denied, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      "exec",
		Arguments: map[string]any{"command": "rm -rf /"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if !denied.IsError || !strings.Contains(text(denied), "policy denied") {
		t.Errorf("denied call: isError=%v text=%q", denied.IsError, text(denied))
	}

	evs := events(t, logPath)
	if len(evs) != 2 || evs[0].Decision != "allow" || evs[1].Decision != "deny" {
		t.Fatalf("flight log = %+v, want allow then deny", evs)
	}
}

func TestRoundTripEscalationApproval(t *testing.T) {
	// The M4 exit slice, over the wire: an escalated command parks, is
	// approved (as the CLI would), and runs inside the original call.
	s, _, sessionDir := newServerFull(t, testRepo(t), 0, 10*time.Second)
	session := connect(t, s)

	done := make(chan *mcp.CallToolResult, 1)
	go func() {
		res, err := session.CallTool(context.Background(), &mcp.CallToolParams{
			Name:      "exec",
			Arguments: map[string]any{"command": "git push origin main"},
		})
		if err != nil {
			t.Error(err)
			done <- nil
			return
		}
		done <- res
	}()

	path := pendingEscalation(t, sessionDir)
	if _, err := escalation.Resolve(path, escalation.Approved, "max", time.Now()); err != nil {
		t.Fatal(err)
	}
	res := <-done
	if res == nil || !strings.Contains(text(res), "approved by max") {
		t.Fatalf("approved escalation over the wire: %+v", res)
	}
}
