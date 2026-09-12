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
// TestKnowledgeOnlyBannerScopesTheGuarantee: the deployment statement
// names what Hobbes guarantees and what it does not (P11, ADR-092).
func TestKnowledgeOnlyBannerScopesTheGuarantee(t *testing.T) {
	for _, want := range []string{"knowledge-only", "no model", "never execute this repo on the host", "outside that guarantee"} {
		if !strings.Contains(KnowledgeOnlyBanner, want) {
			t.Errorf("banner lacks %q", want)
		}
	}
}

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

// TestScopeArgsAcceptPathAlias: list_invariants and list_blind_spots take
// `path` as an alias for `scope` (ADR-087 follow-up (a)) — an agent that
// guesses the argument name must still reach the tool, not lose it to a
// schema rejection.
func TestScopeArgsAcceptPathAlias(t *testing.T) {
	repo := testRepo(t)
	writeGraph(t, repo) // list_blind_spots needs graph.json to answer at all
	s, _ := newServer(t, repo, 0)
	session := connect(t, s)
	ctx := context.Background()

	for _, tool := range []string{"list_invariants", "list_blind_spots"} {
		viaScope, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name: tool, Arguments: map[string]any{"scope": "."},
		})
		if err != nil {
			t.Fatal(err)
		}
		viaPath, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name: tool, Arguments: map[string]any{"path": "."},
		})
		if err != nil {
			t.Fatal(err)
		}
		viaNeither, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name: tool, Arguments: map[string]any{},
		})
		if err != nil {
			t.Fatal(err)
		}
		if viaScope.IsError || viaPath.IsError || viaNeither.IsError {
			t.Fatalf("%s: unexpected error scope=%+v path=%+v neither=%+v",
				tool, viaScope, viaPath, viaNeither)
		}
		if text(viaPath) != text(viaScope) {
			t.Errorf("%s: path alias answered differently from scope:\npath:  %s\nscope: %s",
				tool, text(viaPath), text(viaScope))
		}
		if text(viaNeither) != text(viaScope) {
			t.Errorf("%s: no argument did not cover the whole repo like scope=\".\":\nneither: %s\nscope:   %s",
				tool, text(viaNeither), text(viaScope))
		}

		conflict, err := session.CallTool(ctx, &mcp.CallToolParams{
			Name: tool, Arguments: map[string]any{"scope": "a", "path": "b"},
		})
		if err != nil {
			t.Fatal(err)
		}
		if !conflict.IsError || !strings.Contains(text(conflict), `"a"`) || !strings.Contains(text(conflict), `"b"`) {
			t.Errorf("%s: differing scope/path should be refused naming both, got isError=%v text=%q",
				tool, conflict.IsError, text(conflict))
		}
	}
}

// TestScopeToolSchemaListsBothAndRequiresNeither: the MCP input schema is
// what an agent sees before it ever calls the tool — it must advertise
// both spellings and require neither, or a strict client refuses to try
// `path` at all.
func TestScopeToolSchemaListsBothAndRequiresNeither(t *testing.T) {
	s, _ := newServer(t, testRepo(t), 0)
	session := connect(t, s)
	tools, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	checked := 0
	for _, tool := range tools.Tools {
		if tool.Name != "list_invariants" && tool.Name != "list_blind_spots" {
			continue
		}
		checked++
		schema, ok := tool.InputSchema.(map[string]any)
		if !ok {
			t.Fatalf("%s: input schema is %T, want a JSON object", tool.Name, tool.InputSchema)
		}
		props, _ := schema["properties"].(map[string]any)
		for _, want := range []string{"scope", "path"} {
			if _, ok := props[want]; !ok {
				t.Errorf("%s: schema properties missing %q: %v", tool.Name, want, props)
			}
		}
		if required, ok := schema["required"]; ok {
			if arr, _ := required.([]any); len(arr) != 0 {
				t.Errorf("%s: schema requires %v, want neither scope nor path required", tool.Name, arr)
			}
		}
	}
	if checked != 2 {
		t.Fatalf("expected to check 2 scope-taking tools, checked %d", checked)
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
