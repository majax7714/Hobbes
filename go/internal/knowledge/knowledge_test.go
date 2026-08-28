package knowledge

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/go/internal/derived"
)

// fixtureRepo builds a git repo with hand-written derived artifacts.
func fixtureRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	git := func(args ...string) string {
		full := append([]string{"-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"}, args...)
		out, err := exec.Command("git", full...).Output()
		if err != nil {
			t.Fatalf("git %v: %v", args, err)
		}
		return strings.TrimSpace(string(out))
	}
	git("init", "-q")
	git("commit", "-qm", "base", "--allow-empty")
	sha := git("rev-parse", "HEAD")

	graph := map[string]any{
		"schema_version": derived.Current,
		"sha":            sha, "dirty": false,
		"nodes": []map[string]any{
			{"id": "app.core", "kind": "module", "path": "src/app/core.py"},
			{"id": "app.api", "kind": "module", "path": "src/app/api.py"},
			{"id": "ext:requests", "kind": "external"},
			{"id": "env:APP_MODE", "kind": "env", "name": "APP_MODE"},
		},
		"module_edges": []map[string]any{
			{"from": "app.api", "to": "app.core", "type": "imports", "tier": "syntactic",
				"evidence": []map[string]any{{"path": "src/app/api.py", "line": 3, "lane": "tree-sitter"}}},
			{"from": "app.core", "to": "ext:requests", "type": "imports", "tier": "syntactic",
				"evidence": []map[string]any{{"path": "src/app/core.py", "line": 1, "lane": "tree-sitter"}}},
			{"from": "app.core", "to": "env:APP_MODE", "type": "env-read", "tier": "syntactic",
				"evidence": []map[string]any{{"path": "src/app/core.py", "line": 9, "lane": "tree-sitter"}}},
		},
		"symbols": []map[string]any{
			{"id": "app.core.run", "module": "app.core", "kind": "function", "line": 5},
			{"id": "app.api.handler", "module": "app.api", "kind": "function", "line": 7},
			{"id": "app.api.Config", "module": "app.api", "kind": "class", "line": 12},
		},
		"symbol_edges": []map[string]any{
			{"from": "app.api.handler", "to": "app.core.run", "type": "calls", "tier": "syntactic",
				"evidence": []map[string]any{{"path": "src/app/api.py", "line": 9, "lane": "tree-sitter"}}},
			// A resolution no call site claimed (ADR-029): names the symbol,
			// does not call it. V2.M2 introduced the type; V2.M3 stopped
			// consumers counting it as a call.
			{"from": "app.api.Config", "to": "app.core.run", "type": "uses", "tier": "semantic",
				"evidence": []map[string]any{{"path": "src/app/api.py", "line": 14, "lane": "scip"}}},
		},
	}
	tests := map[string]any{
		"schema_version": derived.Current,
		"sha":            sha, "dirty": false,
		"tests": []map[string]any{
			{"id": "tests/test_core.py::test_run", "file": "tests/test_core.py",
				"line": 4, "reaches": []string{"app.core.run"},
				"reaches_modules": []string{"app.core"}},
			{"id": "tests/test_api.py::test_handler", "file": "tests/test_api.py",
				"line": 8, "reaches": []string{"app.api.handler"},
				"reaches_modules": []string{"app.api"}},
		},
	}
	derived := filepath.Join(repo, ".hobbes", "derived")
	if err := os.MkdirAll(derived, 0o755); err != nil {
		t.Fatal(err)
	}
	for name, doc := range map[string]any{"graph.json": graph, "tests.json": tests} {
		data, err := json.Marshal(doc)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(derived, name), data, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return repo
}

func TestNeighborhoodListsBothDirectionsWithProvenance(t *testing.T) {
	s := Open(fixtureRepo(t))
	out, err := s.Neighborhood("app.core")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"app.core (module, src/app/core.py)",
		"-imports-> ext:requests",
		"-env-read-> env:APP_MODE",
		"<-imports- app.api",
		"[src/app/api.py:3]",
	} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %q in:\n%s", want, out)
		}
	}
	if strings.Contains(out, "WARNING") {
		t.Errorf("fresh artifacts flagged stale:\n%s", out)
	}
}

func TestNeighborhoodUnknownNodeSuggests(t *testing.T) {
	s := Open(fixtureRepo(t))
	out, err := s.Neighborhood("core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, `no node "core"`) || !strings.Contains(out, "app.core") {
		t.Errorf("want near-miss suggestion:\n%s", out)
	}
}

func TestWhoCallsWithEvidence(t *testing.T) {
	s := Open(fixtureRepo(t))
	out, err := s.WhoCalls("app.core.run")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "app.api.handler") || !strings.Contains(out, "[src/app/api.py:9]") {
		t.Errorf("caller with provenance missing:\n%s", out)
	}
}

// who_calls must answer who *calls*, not who names. Since V2.M2 the symbol
// layer carries `uses` edges too (ADR-029), and nothing filtered on type —
// so type annotations and except clauses read as callers, which is the
// exact failure ADR-029 was written to prevent, arriving by another route.
func TestWhoCallsSeparatesUsesFromCalls(t *testing.T) {
	s := Open(fixtureRepo(t))
	out, err := s.WhoCalls("app.core.run")
	if err != nil {
		t.Fatal(err)
	}
	callers, _, found := strings.Cut(out, "references app.core.run without calling it")
	if !found {
		t.Fatalf("uses edges not reported under their own heading:\n%s", out)
	}
	if strings.Contains(callers, "app.api.Config") {
		t.Errorf("a `uses` edge is being counted as a caller:\n%s", out)
	}
	if !strings.Contains(callers, "app.api.handler") {
		t.Errorf("the real caller is missing:\n%s", out)
	}
	// Dropping the uses edge would be its own dishonesty (P8) — it is true,
	// just not a call.
	if !strings.Contains(out, "app.api.Config") {
		t.Errorf("the `uses` edge was discarded rather than relabelled:\n%s", out)
	}
}

// Tier is the graph's trust signal (§3.4); a syntactic call edge is lane
// A's own resolution and can be wrong (C-7), so an agent must see that.
func TestWhoCallsMarksApproximateEdges(t *testing.T) {
	s := Open(fixtureRepo(t))
	out, err := s.WhoCalls("app.core.run")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "syntactic") {
		t.Errorf("a syntactic-tier caller is presented as proven:\n%s", out)
	}
}

func TestWhoCallsKnownSymbolWithoutCallers(t *testing.T) {
	s := Open(fixtureRepo(t))
	out, err := s.WhoCalls("app.api.handler")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "no recorded callers") {
		t.Errorf("want the static-edges caveat, got:\n%s", out)
	}
}

func TestTestsGuardingByModuleAndByPath(t *testing.T) {
	s := Open(fixtureRepo(t))
	byModule, err := s.TestsGuarding("app.core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(byModule, "tests/test_core.py::test_run") ||
		strings.Contains(byModule, "test_api") {
		t.Errorf("module query wrong:\n%s", byModule)
	}
	byPath, err := s.TestsGuarding("src/app")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(byPath, "test_run") || !strings.Contains(byPath, "test_handler") {
		t.Errorf("path-prefix query should span both modules:\n%s", byPath)
	}
}

func TestTestsGuardingUnguardedModuleSaysSo(t *testing.T) {
	repo := fixtureRepo(t)
	// Drop the core test so app.core is unguarded.
	path := filepath.Join(repo, ".hobbes", "derived", "tests.json")
	data, _ := os.ReadFile(path)
	var doc map[string]any
	json.Unmarshal(data, &doc)
	doc["tests"] = []any{}
	out, _ := json.Marshal(doc)
	os.WriteFile(path, out, 0o644)

	s := Open(repo)
	answer, err := s.TestsGuarding("app.core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(answer, "unguarded") {
		t.Errorf("want the unguarded warning:\n%s", answer)
	}
}

func TestStaleArtifactsWarn(t *testing.T) {
	repo := fixtureRepo(t)
	git := append([]string{"-C", repo, "-c", "user.name=t", "-c", "user.email=t@t"},
		"commit", "-qm", "moved on", "--allow-empty")
	if err := exec.Command("git", git...).Run(); err != nil {
		t.Fatal(err)
	}
	out, err := Open(repo).Neighborhood("app.core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "WARNING") || !strings.Contains(out, "stale") {
		t.Errorf("moved HEAD must flag staleness:\n%s", out)
	}
}

func TestMissingArtifactsSayRunIngest(t *testing.T) {
	repo := t.TempDir()
	_, err := Open(repo).Neighborhood("x")
	if err == nil || !strings.Contains(err.Error(), "hobbes ingest") {
		t.Errorf("err = %v, want run-ingest hint", err)
	}
}

// --- module docs (ADR-019) -------------------------------------------------

// writeModuleDoc files a narrative module-doc artifact for app.core whose
// sources stamp the *current* working-tree blob of src/app/core.py.
func writeModuleDoc(t *testing.T, repo string) {
	t.Helper()
	src := filepath.Join(repo, "src", "app")
	if err := os.MkdirAll(src, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(src, "core.py"), []byte("def run():\n    return 1\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command("git", "-C", repo, "hash-object", "--", "src/app/core.py").Output()
	if err != nil {
		t.Fatal(err)
	}
	doc := map[string]any{
		"schema_version": 1, "kind": "module-doc",
		"id": "app.core", "path": "src/app/core.py",
		"sha": "c0ffee0000000000000000000000000000000000", "dirty": false,
		"sources": []map[string]any{
			{"path": "src/app/core.py", "blob_sha": strings.TrimSpace(string(out))},
		},
		"purpose": map[string]any{
			"text": "runs the core computation",
			"pins": []map[string]any{{"path": "src/app/core.py", "line": 1}},
		},
		"responsibilities": []map[string]any{
			{"text": "returns the answer",
				"pins": []map[string]any{{"path": "src/app/core.py", "line": 2}}},
		},
		"gotchas": []map[string]any{},
	}
	dir := filepath.Join(repo, ".hobbes", "derived", "docs", "modules")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "app.core.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestModuleDocRendersPinnedClaims(t *testing.T) {
	repo := fixtureRepo(t)
	writeModuleDoc(t, repo)
	out, err := Open(repo).ModuleDoc("app.core")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"knowledge from narrate @ c0ffee000000",
		"module app.core (src/app/core.py)",
		"purpose: runs the core computation  [src/app/core.py:1]",
		"responsibilities:",
		"- returns the answer  [src/app/core.py:2]",
	} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %q in:\n%s", want, out)
		}
	}
	if strings.Contains(out, "STALE") || strings.Contains(out, "gotchas") {
		t.Errorf("fresh doc with no gotchas rendered wrong:\n%s", out)
	}
}

func TestModuleDocBlobStaleWarns(t *testing.T) {
	repo := fixtureRepo(t)
	writeModuleDoc(t, repo)
	// An uncommitted edit to a cited file must flip the badge (ADR-019).
	if err := os.WriteFile(filepath.Join(repo, "src", "app", "core.py"), []byte("edited = True\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	out, err := Open(repo).ModuleDoc("app.core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "WARNING: STALE") || !strings.Contains(out, "src/app/core.py") ||
		!strings.Contains(out, "hobbes narrate") {
		t.Errorf("want blob-level stale warning naming the file:\n%s", out)
	}
}

func TestModuleDocDeletedSourceIsStale(t *testing.T) {
	repo := fixtureRepo(t)
	writeModuleDoc(t, repo)
	if err := os.Remove(filepath.Join(repo, "src", "app", "core.py")); err != nil {
		t.Fatal(err)
	}
	out, err := Open(repo).ModuleDoc("app.core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "WARNING: STALE") {
		t.Errorf("deleted source should read stale:\n%s", out)
	}
}

func TestModuleDocUnknownIdSuggests(t *testing.T) {
	repo := fixtureRepo(t)
	writeModuleDoc(t, repo)
	out, err := Open(repo).ModuleDoc("core")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, `no module doc for "core"`) || !strings.Contains(out, "app.core") {
		t.Errorf("want near-miss suggestion:\n%s", out)
	}
}

func TestModuleDocNoneGeneratedSaysRunNarrate(t *testing.T) {
	repo := fixtureRepo(t)
	_, err := Open(repo).ModuleDoc("app.core")
	if err == nil || !strings.Contains(err.Error(), "hobbes narrate") {
		t.Errorf("want run-narrate error, got %v", err)
	}
}

func TestModuleDocRejectsTraversalIds(t *testing.T) {
	repo := fixtureRepo(t)
	// "/"-bearing ids are legal (TS/JS path ids, ADR-021); traversal is not.
	for _, id := range []string{"../evil", "..", "x/../y", "/abs", `a\b`, "a//b", "a/./b", ""} {
		if _, err := Open(repo).ModuleDoc(id); err == nil {
			t.Errorf("id %q should be rejected", id)
		}
	}
}

func TestModuleDocNestedTsId(t *testing.T) {
	repo := fixtureRepo(t)
	writeModuleDoc(t, repo) // creates docs/modules/app.core.json too
	doc := map[string]any{
		"schema_version": 1, "kind": "module-doc",
		"id": "src/flow", "path": "src/flow.js",
		"sha": "beef000000000000000000000000000000000000", "dirty": false,
		"sources": []map[string]any{},
		"purpose": map[string]any{
			"text": "pure auth-flow logic",
			"pins": []map[string]any{{"path": "src/app/core.py", "line": 1}},
		},
		"responsibilities": []map[string]any{},
		"gotchas":          []map[string]any{},
	}
	dir := filepath.Join(repo, ".hobbes", "derived", "docs", "modules", "src")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	data, _ := json.Marshal(doc)
	if err := os.WriteFile(filepath.Join(dir, "flow.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
	out, err := Open(repo).ModuleDoc("src/flow")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "module src/flow (src/flow.js)") {
		t.Errorf("nested id not rendered:\n%s", out)
	}
	// The nested id shows up in near-miss suggestions too.
	miss, err := Open(repo).ModuleDoc("flow")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(miss, "src/flow") {
		t.Errorf("nested id missing from suggestions:\n%s", miss)
	}
}

// --- list_invariants (ADR-024, ADR-017's fifth tool) ------------------------

// writeInvariant drops one record into .hobbes/invariants/.
func writeInvariant(t *testing.T, repo, name, body string) {
	t.Helper()
	dir := filepath.Join(repo, ".hobbes", "invariants")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

const confirmedRecord = `id: I-1
statement: Only the parser parses source.
scope: src/app
status: confirmed
compile:
  target: import-linter
  rule:
    kind: forbidden-import
    importers: ["*"]
    imported: [ext:tree_sitter]
guarded_by: [tests/test_parser.py::test_parses]
`

func TestListInvariantsWithoutADirectory(t *testing.T) {
	repo := fixtureRepo(t)
	out, err := Open(repo).ListInvariants(".")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "none have been confirmed") {
		t.Errorf("answer = %q, want a plain 'none confirmed'", out)
	}
}

func TestListInvariantsReportsHowEachIsChecked(t *testing.T) {
	repo := fixtureRepo(t)
	writeInvariant(t, repo, "I-1.yaml", confirmedRecord)
	out, err := Open(repo).ListInvariants(".")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"I-1", "Only the parser parses source.", "scope src/app",
		"import-linter", "tests/test_parser.py::test_parses",
	} {
		if !strings.Contains(out, want) {
			t.Errorf("answer missing %q:\n%s", want, out)
		}
	}
}

func TestListInvariantsSaysHowSoftIsJudged(t *testing.T) {
	repo := fixtureRepo(t)
	writeInvariant(t, repo, "I-2.yaml", `id: I-2
statement: Something a tool cannot see.
scope: .
status: confirmed
compile:
  target: soft
`)
	out, _ := Open(repo).ListInvariants(".")
	if !strings.Contains(out, "a reviewer judges it") {
		t.Errorf("a soft record must say who judges it:\n%s", out)
	}
}

func TestListInvariantsOnlyBindsWithConfirmedRecords(t *testing.T) {
	repo := fixtureRepo(t)
	writeInvariant(t, repo, "I-1.yaml", confirmedRecord)
	writeInvariant(t, repo, "I-9.yaml", `id: I-9
statement: Not yet promoted.
scope: .
status: inferred
compile:
  target: soft
`)
	out, _ := Open(repo).ListInvariants(".")
	if strings.Contains(out, "Not yet promoted") {
		t.Error("an inferred record must not read as binding")
	}
	if !strings.Contains(out, "1 record(s) not confirmed") {
		t.Errorf("the skipped record should still be counted:\n%s", out)
	}
}

func TestListInvariantsScopeOverlapsBothWays(t *testing.T) {
	repo := fixtureRepo(t)
	writeInvariant(t, repo, "I-1.yaml", confirmedRecord) // scope src/app

	// Asking about a file inside the scope finds the rule.
	if out, _ := Open(repo).ListInvariants("src/app/core.py"); !strings.Contains(out, "I-1") {
		t.Errorf("a path inside the scope should be bound:\n%s", out)
	}
	// Asking about a directory that contains the scope finds it too —
	// otherwise a rule can hide inside the tree you asked about.
	if out, _ := Open(repo).ListInvariants("src"); !strings.Contains(out, "I-1") {
		t.Errorf("a parent of the scope should still see it:\n%s", out)
	}
	// An unrelated tree does not.
	if out, _ := Open(repo).ListInvariants("infra"); strings.Contains(out, "I-1") {
		t.Errorf("an unrelated scope must not match:\n%s", out)
	}
}

func TestListInvariantsSkipsUnreadableRecords(t *testing.T) {
	repo := fixtureRepo(t)
	writeInvariant(t, repo, "I-1.yaml", confirmedRecord)
	writeInvariant(t, repo, "torn.yaml", "id: [unclosed\n")
	out, err := Open(repo).ListInvariants(".")
	if err != nil {
		t.Fatalf("one torn record must not fail the listing: %v", err)
	}
	if !strings.Contains(out, "I-1") {
		t.Errorf("the readable record should still list:\n%s", out)
	}
}

// The knowledge tools cite file:line at agents, so a half-read graph
// would produce confident wrong provenance. Refuse instead (ADR-028).
func TestUnknownSchemaVersionIsRefused(t *testing.T) {
	repo := fixtureRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	doc["schema_version"] = derived.Current + 1
	out, _ := json.Marshal(doc)
	if err := os.WriteFile(path, out, 0o644); err != nil {
		t.Fatal(err)
	}

	for _, q := range []struct {
		name string
		run  func() (string, error)
	}{
		{"Neighborhood", func() (string, error) { return Open(repo).Neighborhood("app.core") }},
		{"WhoCalls", func() (string, error) { return Open(repo).WhoCalls("app.core.run") }},
		{"TestsGuarding", func() (string, error) { return Open(repo).TestsGuarding("app.core") }},
	} {
		t.Run(q.name, func(t *testing.T) {
			answer, err := q.run()
			if err == nil {
				t.Fatalf("expected a refusal, got answer %q", answer)
			}
			if !strings.Contains(err.Error(), "schema v") {
				t.Errorf("refusal should name the version: %v", err)
			}
		})
	}
}

// blindSpotRepo writes a graph carrying the ADR-045 honesty surface.
func blindSpotRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	git := func(args ...string) string {
		full := append([]string{"-C", repo}, args...)
		out, err := exec.Command("git", full...).Output()
		if err != nil {
			t.Fatalf("git %v: %v", args, err)
		}
		return strings.TrimSpace(string(out))
	}
	git("init", "-q")
	git("commit", "-qm", "base", "--allow-empty")
	sha := git("rev-parse", "HEAD")
	graph := map[string]any{
		"schema_version": derived.Current,
		"sha":            sha, "dirty": false,
		"nodes": []map[string]any{}, "module_edges": []map[string]any{},
		"symbols": []map[string]any{}, "symbol_edges": []map[string]any{},
		"resolution_coverage": []map[string]any{
			{"file": "src/app/core.py", "sites": 20, "resolved": 12, "external": 3,
				"unresolved": 5, "tail": map[string]int{"builtin-name": 3, "attr-call": 2}},
			{"file": "src/app/api.py", "sites": 10, "resolved": 10, "external": 0,
				"unresolved": 0},
			{"file": "web/main.ts", "sites": 8, "resolved": 2, "external": 0,
				"unresolved": 6, "tail": map[string]int{"local-binding": 4, "unclassified": 2}},
		},
		"dependency_coverage": []map[string]any{
			{"declared": 6, "resolved": 4, "missing": []string{"boto3", "psycopg"}},
		},
		"extraction_errors": []map[string]any{
			{"path": "scripts", "stage": "go-modules", "message": "orphan directory"},
		},
		"tail_classes_available": map[string][]string{
			"python": {"fallback-resolved", "local-binding", "import-binding",
				"builtin-name", "attr-call", "unclassified"},
			"ts/js": {"fallback-resolved", "local-binding", "nested-decl",
				"external-origin", "attr-call", "unclassified"},
		},
		"verification_base": map[string]any{
			"python": map[string]any{"repos": 3, "note": "verified on 3 repos: this repo (dogfood, continuous), private-repo-A, qwen-pathology"},
			"go":     map[string]any{"repos": 1, "note": "verified on 1 repo: one repo — this one"},
		},
	}
	derivedDir := filepath.Join(repo, ".hobbes", "derived")
	if err := os.MkdirAll(derivedDir, 0o755); err != nil {
		t.Fatal(err)
	}
	data, err := json.Marshal(graph)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(derivedDir, "graph.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
	return repo
}

// TestBlindSpotsNameAnUncontainedArtifact: an artifact whose lane B ran
// on the host (ADR-092's escape hatch, or a box without the image) says
// so where the boundary is read (C-64); one built contained says nothing
// — the guarantee holding is the default.
func TestBlindSpotsNameAnUncontainedArtifact(t *testing.T) {
	repo := blindSpotRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	raw, _ := os.ReadFile(path)
	var g map[string]any
	json.Unmarshal(raw, &g)
	g["containment"] = map[string]any{
		"steps": []map[string]any{
			{"step": "index-python", "contained": true},
			{"step": "index-rust", "contained": false, "reason": "HOBBES_UNCONTAINED is set"},
		},
		"all_contained": false, "escape_hatch": true,
	}
	data, _ := json.Marshal(g)
	os.WriteFile(path, data, 0o644)
	out, err := Open(repo).ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "containment: 1 of 2 lane B step(s) ran on the host (HOBBES_UNCONTAINED is set)") || !strings.Contains(out, "C-64") {
		t.Fatalf("uncontained artifact not named:\n%s", out)
	}
	g["containment"] = map[string]any{"steps": []map[string]any{{"step": "index-python", "contained": true}}, "all_contained": true, "escape_hatch": false}
	data, _ = json.Marshal(g)
	os.WriteFile(path, data, 0o644)
	out, _ = Open(repo).ListBlindSpots(".")
	if strings.Contains(out, "containment:") {
		t.Fatalf("a contained artifact needs no banner:\n%s", out)
	}
}

func TestBlindSpotsWholeRepoRollsUpPerLanguage(t *testing.T) {
	s := Open(blindSpotRepo(t))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"capture [python]: 83.3% of 30 detected call sites accounted",
		"capture [ts/js]: 25.0% of 8 detected call sites accounted",
		"seen, not modelled by design: 3 (builtin-name 3)",
		"cannot resolve: 2 (attr-call 2)",
		"environment gap: 4/6 declared packages resolved; missing: boto3, psycopg",
		"degraded: scripts: go-modules: orphan directory",
		"src/app/core.py — 5 of 20 sites unresolved (builtin-name 3, attr-call 2)",
		// the always-on denominator honesty, C-1/C-4/C-5:
		"not over the repo",
		// meanings appear only for classes present, with their C-refs:
		"attr-call — an attribute call whose receiver no static provider could type",
		"unclassified — no observation applies",
		// C-32: what the lane could not have said, beside what it did say:
		"classes this lane cannot report: nested-decl, external-origin, path-call (C-32)",
		"classes this lane cannot report: import-binding, builtin-name, path-call (C-32)",
		// C-31: the verification base, stated before any percentage:
		"verification base — a sample, not the language (C-31",
		"go: verified on 1 repo: one repo — this one",
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
	if strings.Contains(out, "path-call —") {
		t.Fatalf("meaning printed for a class not present:\n%s", out)
	}
}

func TestBlindSpotsScopeFiltersByPathPrefix(t *testing.T) {
	s := Open(blindSpotRepo(t))
	out, err := s.ListBlindSpots("web/")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out, "python") {
		t.Fatalf("python rows leaked into web/ scope:\n%s", out)
	}
	if !strings.Contains(out, "capture [ts/js]") {
		t.Fatalf("ts rows missing under web/ scope:\n%s", out)
	}
	// The verification base is scoped too: go has no sites under web/,
	// and neither python nor go may be vouched for there.
	if strings.Contains(out, "verification base") {
		t.Fatalf("verification rows for languages absent from the scope:\n%s", out)
	}
}

func TestBlindSpotsUnknownScopeSaysHow(t *testing.T) {
	s := Open(blindSpotRepo(t))
	if _, err := s.ListBlindSpots("nope/"); err == nil ||
		!strings.Contains(err.Error(), "repo-relative path prefix") {
		t.Fatalf("want scope guidance, got %v", err)
	}
}

func TestBlindSpotsCleanScopeSaysAccounted(t *testing.T) {
	s := Open(blindSpotRepo(t))
	out, err := s.ListBlindSpots("src/app/api.py")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "every detected call site under this scope is accounted for") {
		t.Fatalf("clean scope should say so:\n%s", out)
	}
}

func TestBlindSpotsOnAnOlderArtifactOmitsTheNotes(t *testing.T) {
	repo := blindSpotRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	var doc map[string]any
	data, _ := os.ReadFile(path)
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	delete(doc, "tail_classes_available")
	delete(doc, "verification_base")
	data, _ = json.Marshal(doc)
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}
	out, err := Open(repo).ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	for _, absent := range []string{"cannot report", "verification base"} {
		if strings.Contains(out, absent) {
			t.Fatalf("%q printed without the artifact carrying it:\n%s", absent, out)
		}
	}
}

func TestNeighborhoodAcceptsTheNodePath(t *testing.T) {
	// ADR-073: the map shows "`id` — path" and the 7B passes the path.
	s := Open(fixtureRepo(t))
	byID, err := s.Neighborhood("app.core")
	if err != nil {
		t.Fatal(err)
	}
	var g graphDoc
	if err := s.loadInto("graph.json", &g); err != nil {
		t.Fatal(err)
	}
	var p string
	for _, n := range g.Nodes {
		if n.ID == "app.core" {
			p = n.Path
		}
	}
	if p == "" {
		t.Skip("fixture node app.core has no path")
	}
	byPath, err := s.Neighborhood(p)
	if err != nil {
		t.Fatal(err)
	}
	if byPath != byID {
		t.Fatalf("by path differs from by id:\n%s\n---\n%s", byPath, byID)
	}
	if out, _ := s.Neighborhood("no/such/path.py"); !strings.Contains(out, "no node") {
		t.Fatalf("unknown path should still say no node: %s", out)
	}
}
