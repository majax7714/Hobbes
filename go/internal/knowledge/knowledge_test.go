package knowledge

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

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
		"built_by": map[string]any{"version": "0.1.4-beta", "checkout": "/opt/hobbes", "sha": strings.Repeat("b", 40), "dirty": true},
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
	callers, _, found := strings.Cut(out, "references app.core.run where no call site was detected")
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

// ADR-120: the override set. An `implements` edge into a symbol is what
// the index states implements or overrides it — reported under its own
// heading, neither counted as a caller nor dropped (P8), and the heading
// says a call to the symbol may reach any of them (C-58).
func TestWhoCallsListsImplementors(t *testing.T) {
	repo := fixtureRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	data, _ := os.ReadFile(path)
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	doc["symbols"] = append(doc["symbols"].([]any),
		map[string]any{"id": "app.api.Shape.area", "module": "app.api", "kind": "method", "line": 20},
		map[string]any{"id": "app.api.Circle.area", "module": "app.api", "kind": "method", "line": 30})
	doc["symbol_edges"] = append(doc["symbol_edges"].([]any),
		map[string]any{"from": "app.api.Circle.area", "to": "app.api.Shape.area", "type": "implements", "tier": "semantic",
			"evidence": []map[string]any{{"path": "src/app/api.py", "line": 30, "lane": "scip"}}})
	out, _ := json.Marshal(doc)
	if err := os.WriteFile(path, out, 0o644); err != nil {
		t.Fatal(err)
	}

	s := Open(repo)
	got, err := s.WhoCalls("app.api.Shape.area")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(got, "no callers of app.api.Shape.area") {
		t.Errorf("an implementor is not a caller:\n%s", got)
	}
	heading, rest, found := strings.Cut(got, "implemented or overridden by")
	if !found || !strings.Contains(rest, "C-58") || !strings.Contains(rest, "app.api.Circle.area") {
		t.Errorf("want the implementor under its own heading with C-58's caveat:\n%s", got)
	}
	if strings.Contains(heading, "app.api.Circle.area") {
		t.Errorf("the implementor is listed above its heading:\n%s", got)
	}
	if strings.Contains(got, "no recorded callers") {
		t.Errorf("a symbol with implementors is not answered as if nothing touched it:\n%s", got)
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

// ADR-125 §4: C-153's region, surfaced where a user meets the edge. A
// semantic caller that is a C++ template pattern carries the note — the
// pattern is indexed once, so scip-clang's one answer inside it can name
// another specialisation's declaration. It marks the region, not the wrong
// edge: an unmarked caller and a syntactic edge out of a pattern say
// nothing, since neither is an answer that can be wrong that way.
func TestWhoCallsMarksCallersInACppTemplatePattern(t *testing.T) {
	const note = "C-153: from a C++ template pattern"
	repo := fixtureRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	data, _ := os.ReadFile(path)
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	doc["cpp_template_patterns"] = []any{"src/tpl.pattern", "src/tpl.guessing"}
	doc["symbols"] = append(doc["symbols"].([]any),
		map[string]any{"id": "src/lib.h.f", "module": "src/lib.h", "kind": "function", "line": 1})
	doc["symbol_edges"] = append(doc["symbol_edges"].([]any),
		map[string]any{"from": "src/tpl.pattern", "to": "src/lib.h.f", "type": "calls", "tier": "semantic",
			"evidence": []map[string]any{{"path": "src/tpl.cpp", "line": 3, "lane": "scip"}}},
		map[string]any{"from": "src/tpl.plainfn", "to": "src/lib.h.f", "type": "calls", "tier": "semantic",
			"evidence": []map[string]any{{"path": "src/tpl.cpp", "line": 5, "lane": "scip"}}},
		// A pattern lane B never answered in: lane A's guess, which
		// qualify() already marks approximate.
		map[string]any{"from": "src/tpl.guessing", "to": "src/lib.h.f", "type": "calls", "tier": "syntactic",
			"evidence": []map[string]any{{"path": "src/tpl.cpp", "line": 7, "lane": "tree-sitter"}}})
	out, _ := json.Marshal(doc)
	if err := os.WriteFile(path, out, 0o644); err != nil {
		t.Fatal(err)
	}

	got, err := Open(repo).WhoCalls("src/lib.h.f")
	if err != nil {
		t.Fatal(err)
	}
	for _, line := range strings.Split(got, "\n") {
		switch {
		case strings.Contains(line, "src/tpl.pattern"):
			if !strings.Contains(line, note) {
				t.Errorf("a semantic caller in a template pattern is unmarked: %q", line)
			}
		case strings.Contains(line, "src/tpl.plainfn"), strings.Contains(line, "src/tpl.guessing"):
			if strings.Contains(line, note) {
				t.Errorf("C-153 claimed where it cannot occur: %q", line)
			}
		}
	}
	if !strings.Contains(got, "src/tpl.guessing") || !strings.Contains(got, "syntactic") {
		t.Errorf("the syntactic caller lost its own qualifier:\n%s", got)
	}
}

// An artifact built before ADR-125 carries no such key, and neither does a
// repo without C++. Both must read exactly as they did.
func TestWhoCallsWithoutTemplatePatternsRendersUnchanged(t *testing.T) {
	got, err := Open(fixtureRepo(t)).WhoCalls("app.core.run")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(got, "C-153") {
		t.Errorf("a graph without cpp_template_patterns gained a note:\n%s", got)
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

// C-156: a module of values alone is unguarded by construction, and the
// answer says why; an ordinary unguarded module gets no such reason.
func TestTestsGuardingNamesAValueOnlyModule(t *testing.T) {
	repo := fixtureRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	data, _ := os.ReadFile(path)
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	doc["nodes"] = append(doc["nodes"].([]any),
		map[string]any{"id": "app.settings", "kind": "module", "path": "src/app/settings.py"},
		map[string]any{"id": "app.arrows", "kind": "module", "path": "src/app/arrows.ts"})
	doc["symbols"] = append(doc["symbols"].([]any),
		map[string]any{"id": "app.settings.LIMIT", "module": "app.settings", "kind": "const", "line": 1},
		map[string]any{"id": "app.arrows.f", "module": "app.arrows", "kind": "const", "line": 1})
	doc["symbol_edges"] = append(doc["symbol_edges"].([]any),
		map[string]any{"from": "app.core.run", "to": "app.settings.LIMIT", "type": "uses", "tier": "semantic"},
		map[string]any{"from": "app.core.run", "to": "app.arrows.f", "type": "calls", "tier": "semantic"})
	out, _ := json.Marshal(doc)
	if err := os.WriteFile(path, out, 0o644); err != nil {
		t.Fatal(err)
	}

	s := Open(repo)
	settings, err := s.TestsGuarding("app.settings")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(settings, "unguarded") ||
		!strings.Contains(settings, "app.settings declares no function and no call targets it") ||
		!strings.Contains(settings, "(C-156)") {
		t.Errorf("want the unguarded warning with C-156's reason:\n%s", settings)
	}
	arrows, err := s.TestsGuarding("app.arrows")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(arrows, "unguarded") || strings.Contains(arrows, "C-156") {
		t.Errorf("a const a call targets is callable; no C-156 reason:\n%s", arrows)
	}
	guarded, _ := s.TestsGuarding("app.core")
	if strings.Contains(guarded, "C-156") {
		t.Errorf("a guarded module needs no reason:\n%s", guarded)
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
		// An identity per command: a CI runner has no global git config,
		// and `git commit` dies with exit 128 without one (2026-09-06).
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
		"built_by": map[string]any{"checkout": "/opt/hobbes", "sha": strings.Repeat("b", 40), "dirty": true},
		"nodes":    []map[string]any{}, "module_edges": []map[string]any{},
		"symbols": []map[string]any{}, "symbol_edges": []map[string]any{},
		"resolution_coverage": []map[string]any{
			{"file": "src/app/core.py", "sites": 20, "resolved": 12, "external": 3,
				"unresolved": 5, "tail": map[string]int{"builtin-name": 3, "attr-call": 2, "below-floor": 2}},
			{"file": "src/app/api.py", "sites": 10, "resolved": 10, "external": 0,
				"unresolved": 0},
			{"file": "web/main.ts", "sites": 9, "resolved": 2, "external": 0,
				"unresolved": 7, "tail": map[string]int{"local-binding": 4, "expr-callee": 1, "union-member": 1, "unclassified": 1}},
		},
		"dependency_coverage": []map[string]any{
			{"declared": 6, "resolved": 4, "missing": []string{"boto3", "psycopg"}},
		},
		"extraction_errors": []map[string]any{
			{"path": "scripts", "stage": "go-modules", "message": "orphan directory"},
		},
		"tail_classes_available": map[string][]string{
			"python": {"fallback-resolved", "local-binding", "import-binding",
				"builtin-name", "attr-call", "expr-callee", "unclassified", "below-floor"},
			"ts/js": {"fallback-resolved", "local-binding", "nested-decl",
				"external-origin", "attr-call", "expr-callee", "union-member", "unclassified", "below-floor"},
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

// TestBlindSpotsNameAnArityMismatch: ADR-130's abstention is a counted
// class like every other, so the view names the file it happened in and
// glosses what it means — a site that draws no edge, with the rule that
// removed it, rather than a silence (C-153).
func TestBlindSpotsNameAnArityMismatch(t *testing.T) {
	repo := blindSpotRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	raw, _ := os.ReadFile(path)
	var g map[string]any
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	g["resolution_coverage"] = append(g["resolution_coverage"].([]any), map[string]any{
		"file": "src/fmt.cc", "sites": 6, "resolved": 5, "external": 0,
		"unresolved": 1, "tail": map[string]int{"arity-mismatch": 1},
	})
	data, _ := json.Marshal(g)
	os.WriteFile(path, data, 0o644)
	out, err := Open(repo).ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"src/fmt.cc — 1 of 6 sites unresolved (arity-mismatch 1)",
		"arity-mismatch — a C++ call written with more arguments than the declaration the index resolved it to can take",
		"(C-153), so no edge is drawn (ADR-130)",
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
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
		"capture [ts/js]: 22.2% of 9 detected call sites accounted",
		// C-77: `below-floor` (C-58) is in the rollup, the per-file line
		// and the glossary — the one class the view used to omit.
		"seen, not modelled by design: 5 (builtin-name 3, below-floor 2)",
		"cannot resolve: 2 (attr-call 2)",
		"environment gap: 4/6 declared packages resolved; missing: boto3, psycopg",
		"degraded: scripts: go-modules: orphan directory",
		"src/app/core.py — 5 of 20 sites unresolved (builtin-name 3, attr-call 2, below-floor 2)",
		"below-floor — resolved by the semantic lane to a declaration below the symbol floor",
		// the always-on denominator honesty, C-1/C-4/C-5:
		"not over the repo",
		// meanings appear only for classes present, with their C-refs:
		"attr-call — an attribute call whose receiver no static provider could type",
		// C-63 (surfaced 2026-09-05): a callee that is an expression is a
		// counted site with its own class and gloss.
		"web/main.ts — 7 of 9 sites unresolved (local-binding 4, expr-callee 1, union-member 1, unclassified 1)",
		"expr-callee — the callee is itself an expression",
		// ADR-104 / C-97: a union receiver's member, abstained on, with its gloss.
		"union-member — a member call on a union-typed receiver",
		"unclassified — no observation applies",
		// C-32: what the lane could not have said, beside what it did say:
		// `qualifier-mismatch` (ADR-125) and `arity-mismatch` (ADR-130)
		// close both lists: C++ alone can report either, so every other
		// lane names both as absent.
		"classes this lane cannot report: nested-decl, external-origin, union-member, path-call, overload-set, inherited-member, build-tag-set, qualifier-mismatch, arity-mismatch (C-32)",
		"classes this lane cannot report: import-binding, builtin-name, path-call, overload-set, inherited-member, build-tag-set, qualifier-mismatch, arity-mismatch (C-32)",
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

// TestBlindSpotsNameCAsUnverified: C is wired at lane A only and
// unverified on any repo (ADR-108, 0.2.1-beta). langByExt and
// artifactLangBucket used to carry neither ".c"/".h" nor "c" — so a
// C-scoped answer showed only the per-file remainder row and never said
// the language was unverified or gave it a capture line.
func TestBlindSpotsNameCAsUnverified(t *testing.T) {
	repo := blindSpotRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var g map[string]any
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	rows := g["resolution_coverage"].([]any)
	rows = append(rows, map[string]any{
		"file": "src/lib/parse.c", "sites": 4, "resolved": 3, "external": 0,
		"unresolved": 1, "tail": map[string]int{"builtin-name": 1},
	})
	g["resolution_coverage"] = rows
	tca := g["tail_classes_available"].(map[string]any)
	tca["c"] = []string{"fallback-resolved", "local-binding", "builtin-name", "attr-call", "unclassified"}
	g["tail_classes_available"] = tca
	vb := g["verification_base"].(map[string]any)
	vb["c"] = map[string]any{"repos": 0, "note": "not verified on any repo"}
	g["verification_base"] = vb
	data, err := json.Marshal(g)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}

	out, err := Open(repo).ListBlindSpots("src/lib/parse.c")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "c: not verified on any repo") {
		t.Fatalf("verification base is missing the c row:\n%s", out)
	}
	if !strings.Contains(out, "capture [c]") {
		t.Fatalf("a C-scoped answer needs a capture line:\n%s", out)
	}
}

// TestBlindSpotsMtsBucketsAsTsJs: .mts/.cts have mapped to ts/js in the
// pipeline's tail since C-100, but langByExt did not carry them.
func TestBlindSpotsMtsBucketsAsTsJs(t *testing.T) {
	repo := blindSpotRepo(t)
	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var g map[string]any
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	rows := g["resolution_coverage"].([]any)
	rows = append(rows, map[string]any{
		"file": "scripts/fetch.mts", "sites": 4, "resolved": 4, "external": 0,
		"unresolved": 0,
	})
	g["resolution_coverage"] = rows
	data, err := json.Marshal(g)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatal(err)
	}

	out, err := Open(repo).ListBlindSpots("scripts/fetch.mts")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "capture [ts/js]: 100.0% of 4 detected call sites accounted") {
		t.Fatalf(".mts file did not bucket as ts/js:\n%s", out)
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

// --- the directory rollup (a port of tail.rollup_directories / cli.py's
// _print_directory_view, per docs/future_additions.md's ADR-048 entry) ---

// dirRollupRepo writes a graph carrying only the resolution_coverage
// rows a directory-rollup test needs — the whole-repo/per-language
// sections above are exercised by blindSpotRepo already.
func dirRollupRepo(t *testing.T, rows []map[string]any) string {
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
		"nodes": []map[string]any{}, "module_edges": []map[string]any{},
		"symbols": []map[string]any{}, "symbol_edges": []map[string]any{},
		"resolution_coverage": rows,
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

// TestBlindSpotsDirectoryRollupWholeRepo checks the header and a
// hand-computed row against blindSpotRepo's fixture: src/app/core.py
// and src/app/api.py share the "src/app" [python] bucket (30 sites, 2
// cannot-resolve, 3 by design), web/main.ts is its own [ts/js] bucket
// (9 sites, 3 cannot-resolve, 4 by design) — worse, so it ranks first.
func TestBlindSpotsDirectoryRollupWholeRepo(t *testing.T) {
	s := Open(blindSpotRepo(t))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "by directory (depth 2, worst 2 of 2 with unresolvable sites; 0 without):") {
		t.Fatalf("missing directory-rollup header:\n%s", out)
	}
	wantWeb := "  web [ts/js]: 22.2% of 9 sites, 4 by design — cannot resolve 3 (expr-callee 1, unclassified 1, union-member 1)"
	wantApp := "  src/app [python]: 83.3% of 30 sites, 3 by design — cannot resolve 2 (attr-call 2)"
	if !strings.Contains(out, wantWeb) {
		t.Fatalf("missing %q in:\n%s", wantWeb, out)
	}
	if !strings.Contains(out, wantApp) {
		t.Fatalf("missing %q in:\n%s", wantApp, out)
	}
	if strings.Index(out, wantWeb) > strings.Index(out, wantApp) {
		t.Fatalf("worse directory (web, sum 3) must rank before src/app (sum 2):\n%s", out)
	}
}

// TestBlindSpotsDirectoryRollupRanksWorstFirstThenName: four single-file
// directories with cannot-resolve sums 5, 2, 1, 1 — the descending sum
// ranks high before low, and the tied pair breaks on directory name.
func TestBlindSpotsDirectoryRollupRanksWorstFirstThenName(t *testing.T) {
	rows := []map[string]any{
		{"file": "high/a.py", "sites": 10, "unresolved": 5, "tail": map[string]int{"attr-call": 5}},
		{"file": "low/a.py", "sites": 10, "unresolved": 2, "tail": map[string]int{"attr-call": 2}},
		{"file": "tie2/a.py", "sites": 10, "unresolved": 1, "tail": map[string]int{"attr-call": 1}},
		{"file": "tie1/a.py", "sites": 10, "unresolved": 1, "tail": map[string]int{"attr-call": 1}},
	}
	s := Open(dirRollupRepo(t, rows))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "by directory (depth 2, worst 4 of 4 with unresolvable sites; 0 without):") {
		t.Fatalf("missing directory-rollup header:\n%s", out)
	}
	high := "  high [python]: 50.0% of 10 sites — cannot resolve 5 (attr-call 5)"
	low := "  low [python]: 80.0% of 10 sites — cannot resolve 2 (attr-call 2)"
	tie1 := "  tie1 [python]: 90.0% of 10 sites — cannot resolve 1 (attr-call 1)"
	tie2 := "  tie2 [python]: 90.0% of 10 sites — cannot resolve 1 (attr-call 1)"
	for _, want := range []string{high, low, tie1, tie2} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
	if !(strings.Index(out, high) < strings.Index(out, low) &&
		strings.Index(out, low) < strings.Index(out, tie1) &&
		strings.Index(out, tie1) < strings.Index(out, tie2)) {
		t.Fatalf("wrong rank order (want high, low, tie1, tie2):\n%s", out)
	}
}

// TestBlindSpotsDirectoryRollupByDesignOnlyIsNotListed: a directory
// whose tail is entirely by-design (builtin-name here) has nothing to
// verify, so it drops out of the ranked rows and is counted only in the
// "without" remainder — not printed as its own line.
func TestBlindSpotsDirectoryRollupByDesignOnlyIsNotListed(t *testing.T) {
	rows := []map[string]any{
		{"file": "onlydesign/a.py", "sites": 10, "unresolved": 3, "tail": map[string]int{"builtin-name": 3}},
		{"file": "real/a.py", "sites": 10, "unresolved": 2, "tail": map[string]int{"attr-call": 2}},
	}
	s := Open(dirRollupRepo(t, rows))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "by directory (depth 2, worst 1 of 1 with unresolvable sites; 1 without):") {
		t.Fatalf("missing directory-rollup header:\n%s", out)
	}
	if strings.Contains(out, "onlydesign [") {
		t.Fatalf("a by-design-only directory must not be listed:\n%s", out)
	}
	if !strings.Contains(out, "  real [python]: 80.0% of 10 sites — cannot resolve 2 (attr-call 2)") {
		t.Fatalf("the real miss must still be listed:\n%s", out)
	}
}

// TestBlindSpotsDirectoryRollupAllByDesignPrintsNoSection: when every
// directory in scope resolves everything it fails to resolve by design,
// the section prints nothing at all — not even a header with zero rows.
func TestBlindSpotsDirectoryRollupAllByDesignPrintsNoSection(t *testing.T) {
	rows := []map[string]any{
		{"file": "a/x.py", "sites": 10, "unresolved": 3, "tail": map[string]int{"builtin-name": 3}},
		{"file": "b/y.py", "sites": 10, "unresolved": 2, "tail": map[string]int{"local-binding": 2}},
	}
	s := Open(dirRollupRepo(t, rows))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(out, "by directory") {
		t.Fatalf("no directory should list an unresolvable class:\n%s", out)
	}
}

// TestBlindSpotsDirectoryRollupRootAndDeepFiles: a root-level file
// buckets as ".", and a.py.py three levels deep buckets to its first
// two segments — directory_of's own contract (tail.py).
func TestBlindSpotsDirectoryRollupRootAndDeepFiles(t *testing.T) {
	rows := []map[string]any{
		{"file": "d.py", "sites": 5, "unresolved": 1, "tail": map[string]int{"attr-call": 1}},
		{"file": "a/b/c/x.py", "sites": 5, "unresolved": 1, "tail": map[string]int{"attr-call": 1}},
	}
	s := Open(dirRollupRepo(t, rows))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{
		"  . [python]: 80.0% of 5 sites — cannot resolve 1 (attr-call 1)",
		"  a/b [python]: 80.0% of 5 sites — cannot resolve 1 (attr-call 1)",
	} {
		if !strings.Contains(out, want) {
			t.Fatalf("missing %q in:\n%s", want, out)
		}
	}
}

// TestBlindSpotsDirectoryRollupCapsAtTenRows: eleven miss-bearing
// directories give ten rows and a remainder line naming both how many
// more directories there are and how many unresolvable sites they hold.
func TestBlindSpotsDirectoryRollupCapsAtTenRows(t *testing.T) {
	var rows []map[string]any
	for i := 0; i < 11; i++ {
		sum := 11 - i
		rows = append(rows, map[string]any{
			"file": fmt.Sprintf("d%02d/a.py", i), "sites": 100, "unresolved": sum,
			"tail": map[string]int{"attr-call": sum},
		})
	}
	s := Open(dirRollupRepo(t, rows))
	out, err := s.ListBlindSpots(".")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "by directory (depth 2, worst 10 of 11 with unresolvable sites; 0 without):") {
		t.Fatalf("missing directory-rollup header:\n%s", out)
	}
	if !strings.Contains(out, "  … and 1 more directories (1 unresolvable) — per-file rows in graph.json resolution_coverage") {
		t.Fatalf("missing the capped remainder line:\n%s", out)
	}
	if strings.Contains(out, "d10 [") {
		t.Fatalf("the eleventh (worst-ranked-last) directory must not get its own row:\n%s", out)
	}
}

// TestBlindSpotsDirectoryRollupScoped: a scoped answer rolls up only the
// rows under the scope, same as the per-language section above it.
func TestBlindSpotsDirectoryRollupScoped(t *testing.T) {
	s := Open(blindSpotRepo(t))
	out, err := s.ListBlindSpots("web/")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "by directory (depth 2, worst 1 of 1 with unresolvable sites; 0 without):") {
		t.Fatalf("missing scoped directory-rollup header:\n%s", out)
	}
	if strings.Contains(out, "src/app") {
		t.Fatalf("python rows leaked into the web/ scoped rollup:\n%s", out)
	}
	if !strings.Contains(out, "  web [ts/js]: 22.2% of 9 sites, 4 by design — cannot resolve 3 (expr-callee 1, unclassified 1, union-member 1)") {
		t.Fatalf("missing the scoped web row:\n%s", out)
	}
}

func TestEveryGraphAnswerNamesWhichHobbesBuiltIt(t *testing.T) {
	// ADR-094: the artifact carries built_by and the header repeats it;
	// a tests.json answer has no such stamp and says nothing about it.
	s := Open(fixtureRepo(t))
	out, err := s.Neighborhood("app.core")
	if err != nil {
		t.Fatal(err)
	}
	first := strings.SplitN(out, "\n", 2)[0]
	if !strings.Contains(first, "built by hobbes 0.1.4-beta @ bbbbbbbbbbbb (dirty) from /opt/hobbes") {
		t.Errorf("header must name the builder:\n%s", first)
	}
	guard, err := s.TestsGuarding("app.core")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(strings.SplitN(guard, "\n", 2)[0], "built by") {
		t.Errorf("tests.json carries no builder stamp; header must not invent one:\n%s", guard)
	}
}

// ADR-118: an artifact is decoded once per version of its file. Four
// answers read graph.json once; a rewrite (what a re-ingest does) is
// read on the next answer and reflected in it.
func TestArtifactsDecodeOncePerFileVersion(t *testing.T) {
	repo := fixtureRepo(t)
	reads := 0
	orig := readArtifact
	readArtifact = func(p string) ([]byte, error) { reads++; return orig(p) }
	defer func() { readArtifact = orig }()

	s := Open(repo)
	for i := 0; i < 3; i++ {
		if _, err := s.WhoCalls("app.core.run"); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := s.Neighborhood("app.core"); err != nil {
		t.Fatal(err)
	}
	if reads != 1 {
		t.Fatalf("graph.json read %d times for four answers; want 1", reads)
	}

	path := filepath.Join(repo, ".hobbes", "derived", "graph.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(data, &doc); err != nil {
		t.Fatal(err)
	}
	doc["symbol_edges"] = append(doc["symbol_edges"].([]any), map[string]any{
		"from": "app.api.Config", "to": "app.core.run", "type": "calls", "tier": "semantic",
		"evidence": []any{map[string]any{"path": "src/app/api.py", "line": 20}},
	})
	out, _ := json.Marshal(doc)
	if err := os.WriteFile(path, out, 0o644); err != nil {
		t.Fatal(err)
	}
	later := time.Now().Add(2 * time.Second)
	if err := os.Chtimes(path, later, later); err != nil {
		t.Fatal(err)
	}
	answer, err := s.WhoCalls("app.core.run")
	if err != nil {
		t.Fatal(err)
	}
	if reads != 2 {
		t.Fatalf("graph.json read %d times after a rewrite; want 2", reads)
	}
	if !strings.Contains(answer, "app.api.Config  [src/app/api.py:20]") {
		t.Fatalf("the rewritten artifact's new edge is not in the answer:\n%s", answer)
	}
	if _, err := s.TestsGuarding("app.core"); err != nil {
		t.Fatal(err)
	}
	if reads != 3 {
		t.Fatalf("tests.json should have been read once more (reads=%d)", reads)
	}
}

// A removed artifact is reported, never served from memory.
func TestARemovedArtifactIsNotServedFromMemory(t *testing.T) {
	repo := fixtureRepo(t)
	s := Open(repo)
	if _, err := s.WhoCalls("app.core.run"); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(filepath.Join(repo, ".hobbes", "derived", "graph.json")); err != nil {
		t.Fatal(err)
	}
	_, err := s.WhoCalls("app.core.run")
	if err == nil || !strings.Contains(err.Error(), "run `hobbes ingest`") {
		t.Fatalf("a removed graph.json should say to ingest; got %v", err)
	}
}
