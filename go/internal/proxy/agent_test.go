package proxy

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	schema "github.com/majax7714/Hobbes/go/internal/derived"
	"github.com/majax7714/Hobbes/go/internal/knowledge"
	"github.com/majax7714/Hobbes/go/internal/recorder"
)

// agentServer builds a proxy with an agent dir holding the given files.
func agentServer(t *testing.T, repo string, files map[string]string) (*Server, string, string) {
	t.Helper()
	agentDir := t.TempDir()
	for name, content := range files {
		if err := os.WriteFile(filepath.Join(agentDir, name), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	sessionDir := t.TempDir()
	logPath := filepath.Join(sessionDir, "flight.jsonl")
	rec, err := recorder.Open(logPath)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { rec.Close() })
	s, err := New(Config{
		Session: "S-agent", Role: "implementer", RepoRoot: repo,
		SessionDir: sessionDir, EscalationTimeout: 400 * time.Millisecond,
		Rec: rec, AgentDir: agentDir,
	})
	if err != nil {
		t.Fatal(err)
	}
	return s, logPath, sessionDir
}

func writeGraph(t *testing.T, repo string) {
	t.Helper()
	derived := filepath.Join(repo, ".hobbes", "derived")
	if err := os.MkdirAll(derived, 0o755); err != nil {
		t.Fatal(err)
	}
	graph := fmt.Sprintf(`{"schema_version":%d,"sha":%q,"dirty":false,
		"nodes":[{"id":"app.a","kind":"module","path":"a.py"},{"id":"app.b","kind":"module","path":"b.py"},
		         {"id":"app.c","kind":"module","path":"c.py"}],
		"module_edges":[{"from":"app.a","to":"app.b","type":"imports","tier":"syntactic",
			"evidence":[{"path":"a.py","line":1,"lane":"tree-sitter"}]}],
		"symbols":[],"symbol_edges":[]}`, schema.Current, git(t, repo, "rev-parse", "HEAD"))
	if err := os.WriteFile(filepath.Join(derived, "graph.json"), []byte(graph), 0o644); err != nil {
		t.Fatal(err)
	}
}

const manifestJSON = `{"unit":"U1","interior":["app.a"],"boundary":["app.b"],"neighborhood":[],"paths":["a.py"]}`

func TestKnowledgeQueryOutsideManifestIsServedAndTaggedAFault(t *testing.T) {
	repo := testRepo(t)
	writeGraph(t, repo)
	s, logPath, _ := agentServer(t, repo, map[string]string{"context.json": manifestJSON})
	store := knowledge.Open(repo)

	s.answer("graph_neighborhood", "app.a", store.Neighborhood) // interior
	s.answer("graph_neighborhood", "app.b", store.Neighborhood) // boundary
	s.answer("tests_guarding", "a.py", store.TestsGuarding)     // interior path
	out := s.answer("graph_neighborhood", "app.c", store.Neighborhood)
	if out.IsError {
		t.Fatalf("faulting query must still be served: %s", text(out))
	}
	s.answer("list_blind_spots", ".", store.ListBlindSpots) // scope query, never faults

	evs := events(t, logPath)
	want := []bool{false, false, false, true, false}
	for i, w := range want {
		if evs[i].ContextFault != w {
			t.Errorf("event %d (%s %v) context_fault = %v, want %v", i, evs[i].Tool, evs[i].Argv, evs[i].ContextFault, w)
		}
	}
}

func TestNoManifestMeansNoFaults(t *testing.T) {
	repo := testRepo(t)
	writeGraph(t, repo)
	s, logPath, _ := agentServer(t, repo, map[string]string{}) // agent dir, no context.json
	s.answer("graph_neighborhood", "app.c", knowledge.Open(repo).Neighborhood)
	if evs := events(t, logPath); evs[0].ContextFault {
		t.Errorf("fault tagged without a manifest: %+v", evs[0])
	}
}

func TestManifestCoverage(t *testing.T) {
	m := &contextManifest{Interior: []string{"app.a"}, Boundary: []string{"app.b"},
		Neighborhood: []string{"lib.x"}, Paths: []string{"src/app/a.py"}}
	for q, want := range map[string]bool{
		"app.a": true, "app.a.run": true, "app.b": true, "lib.x.Y": true,
		"src/app/a.py": true, "src/app": true, "src/app/a.py::x": true,
		// a bare word is a node id, never a path prefix: "src" is not in scope
		"app.c": false, "app.ab": false, "src/other": false, "appx": false, "src": false,
	} {
		if got := m.covers(q); got != want {
			t.Errorf("covers(%q) = %v, want %v", q, got, want)
		}
	}
}

func TestReflectAppendsMailAndLogs(t *testing.T) {
	repo := testRepo(t)
	s, logPath, sessionDir := agentServer(t, repo, map[string]string{})

	if out := s.reflect("  ", ""); !out.IsError {
		t.Errorf("empty reflect accepted")
	}
	if out := s.reflect("x", "verdict"); !out.IsError {
		t.Errorf("unknown reflect kind accepted")
	}
	s.reflect("K1 pins a site that moved", "")
	out := s.reflect("done: 2 commits", ReflectHandoff)
	if out.IsError || !strings.Contains(text(out), "handoff (#2)") {
		t.Errorf("second reflect = %q", text(out))
	}
	data, err := os.ReadFile(filepath.Join(sessionDir, "mail.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if len(lines) != 2 || !strings.Contains(lines[0], `"seq":1`) || !strings.Contains(lines[0], `"kind":"progress"`) ||
		!strings.Contains(lines[1], `"seq":2`) || !strings.Contains(lines[1], `"kind":"handoff"`) ||
		!strings.Contains(lines[1], `"role":"implementer"`) || !strings.Contains(lines[1], "done: 2 commits") {
		t.Errorf("mail.jsonl = %q", string(data))
	}
	evs := events(t, logPath)
	if len(evs) != 2 || evs[0].Tool != "reflect" || evs[0].PolicyRule != "builtin:mail" || evs[0].Argv[1] != "K1 pins a site that moved" {
		t.Errorf("reflect events = %+v", evs)
	}
}

func TestAgentPolicyNarrowsExec(t *testing.T) {
	repo := testRepo(t) // repo policy allows "echo *"
	s, logPath, _ := agentServer(t, repo, map[string]string{
		"policy.yaml": "version: 1\nscope: agent\nrules:\n  - pattern: \"echo *\"\n    decision: deny\n    reason: \"outside this unit\"\n",
	})
	res := callExec(t, s, ExecArgs{Command: "echo hi"})
	if !res.IsError || !strings.Contains(text(res), "NOT run") {
		t.Errorf("agent deny did not refuse: %q", text(res))
	}
	ev := events(t, logPath)[0]
	if ev.Decision != "deny" || !strings.Contains(ev.PolicyRule, "policy.yaml") {
		t.Errorf("event = %+v", ev)
	}
}

func TestMissingAgentPolicyRefusesExec(t *testing.T) {
	repo := testRepo(t)
	s, _, _ := agentServer(t, repo, map[string]string{})
	res := callExec(t, s, ExecArgs{Command: "echo hi"})
	if !res.IsError || !strings.Contains(text(res), "does not exist") {
		t.Errorf("exec with an agent dir but no policy.yaml ran: %q", text(res))
	}
}
