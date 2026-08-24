package web

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// --- fixtures ---------------------------------------------------------------

// fixture is a served repo plus its session-state root.
type fixture struct {
	repo   string
	logDir string
	srv    *Server
}

func gitIn(t *testing.T, repo string, args ...string) string {
	t.Helper()
	// gc.auto=0: background maintenance writing into a t.TempDir() repo
	// races its cleanup and fails the test for no reason.
	full := append([]string{
		"-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "gc.auto=0",
	}, args...)
	out, err := exec.Command("git", full...).Output()
	if err != nil {
		t.Fatalf("git %v: %v", args, err)
	}
	return strings.TrimSpace(string(out))
}

func writeFile(t *testing.T, path, body string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func writeJSONFile(t *testing.T, path string, doc any) {
	t.Helper()
	data, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	writeFile(t, path, string(data))
}

// blobSHA is the working-tree blob hash of a repo file — what ADR-019
// stamps, so a fixture artifact can be made fresh on purpose.
func blobSHA(t *testing.T, repo, rel string) string {
	t.Helper()
	return gitIn(t, repo, "hash-object", rel)
}

// newFixture builds an ingested, narrated repo: two modules, one test,
// one module doc (fresh), one test doc (stale by construction).
func newFixture(t *testing.T) *fixture {
	t.Helper()
	repo := t.TempDir()
	logDir := t.TempDir()

	gitIn(t, repo, "init", "-q")
	writeFile(t, filepath.Join(repo, "src", "app", "core.py"), "def run():\n    return 1\n")
	writeFile(t, filepath.Join(repo, "src", "app", "api.py"), "from app import core\n\n\ndef handler():\n    return core.run()\n")
	writeFile(t, filepath.Join(repo, "tests", "test_core.py"), "def test_run():\n    assert True\n")
	gitIn(t, repo, "add", "-A")
	gitIn(t, repo, "commit", "-qm", "base")
	sha := gitIn(t, repo, "rev-parse", "HEAD")

	derived := filepath.Join(repo, ".hobbes", "derived")
	writeJSONFile(t, filepath.Join(derived, "graph.json"), map[string]any{
		"schema_version": 3, "sha": sha, "dirty": false,
		"languages": []string{"python"},
		"verification_base": map[string]any{
			"python": map[string]any{"repos": 3, "depth": "multi-repo",
				"note": "verified on 3 repos: this repo (dogfood, continuous), private-repo-A, qwen-pathology"},
		},
		"nodes": []map[string]any{
			{"id": "app.core", "kind": "module", "path": "src/app/core.py"},
			{"id": "app.api", "kind": "module", "path": "src/app/api.py"},
			{"id": "ext:requests", "kind": "external"},
		},
		"module_edges": []map[string]any{
			{"from": "app.api", "to": "app.core", "type": "imports",
				"evidence": []map[string]any{{"path": "src/app/api.py", "line": 1}}},
		},
		"symbols": []map[string]any{
			{"id": "app.core.run", "module": "app.core", "kind": "function", "line": 1},
		},
		"symbol_edges": []map[string]any{},
	})
	writeJSONFile(t, filepath.Join(derived, "tests.json"), map[string]any{
		"schema_version": 3, "sha": sha, "dirty": false,
		"tests": []map[string]any{
			{"id": "tests/test_core.py::test_run", "file": "tests/test_core.py",
				"line": 1, "framework": "pytest",
				"reaches": []string{"app.core.run"}, "reaches_modules": []string{"app.core"}},
		},
	})
	// Stamped like the other two: `hobbes ingest` writes the same header
	// onto all three artifacts, and the version gate (ADR-028) refuses one
	// that carries none — this fixture used to omit it.
	writeJSONFile(t, filepath.Join(derived, "interfaces.json"), map[string]any{
		"schema_version": 3, "sha": sha, "dirty": false,
		"routes": []any{}, "cli_entry_points": []any{},
	})

	// A fresh module doc: sources stamped with the real current blob.
	writeJSONFile(t, filepath.Join(derived, "docs", "modules", "app.core.json"), map[string]any{
		"schema_version": 1, "kind": "module-doc", "id": "app.core",
		"path": "src/app/core.py", "sha": sha, "dirty": false,
		"sources": []map[string]any{
			{"path": "src/app/core.py", "blob_sha": blobSHA(t, repo, "src/app/core.py")},
		},
		"purpose": map[string]any{
			"text": "runs the thing",
			"pins": []map[string]any{{"path": "src/app/core.py", "line": 1}},
		},
		"responsibilities": []any{},
		"gotchas":          []any{},
	})
	// A stale test doc: the stamp is a hash the file never had.
	writeJSONFile(t, filepath.Join(derived, "docs", "tests", "tests.test_core.json"), map[string]any{
		"schema_version": 1, "kind": "test-doc", "id": "tests.test_core",
		"path": "tests/test_core.py", "sha": sha, "dirty": false,
		"sources": []map[string]any{
			{"path": "tests/test_core.py", "blob_sha": "0000000000000000000000000000000000000000"},
		},
		"behaviors": []map[string]any{
			{"test": "tests/test_core.py::test_run", "text": "run returns truthy",
				"pins": []map[string]any{{"path": "tests/test_core.py", "line": 2}}},
		},
	})

	srv, err := New(Config{RepoRoot: repo, LogDir: logDir})
	if err != nil {
		t.Fatal(err)
	}
	return &fixture{repo: repo, logDir: logDir, srv: srv}
}

// get issues a loopback request and returns the recorder.
func (f *fixture) get(t *testing.T, target string) *httptest.ResponseRecorder {
	t.Helper()
	return f.do(t, http.MethodGet, target)
}

func (f *fixture) do(t *testing.T, method, target string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, target, nil)
	req.Host = "127.0.0.1:7777"
	rec := httptest.NewRecorder()
	f.srv.Handler().ServeHTTP(rec, req)
	return rec
}

// getJSON asserts 200 and decodes the body.
func (f *fixture) getJSON(t *testing.T, target string) map[string]any {
	t.Helper()
	rec := f.get(t, target)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET %s = %d, want 200 (body %s)", target, rec.Code, rec.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("GET %s: %v (body %s)", target, err, rec.Body.String())
	}
	return body
}

// --- server basics ----------------------------------------------------------

func TestNewRejectsMissingRepo(t *testing.T) {
	if _, err := New(Config{RepoRoot: filepath.Join(t.TempDir(), "nope")}); err == nil {
		t.Fatal("want error for a repo root that does not exist")
	}
	if _, err := New(Config{}); err == nil {
		t.Fatal("want error for an empty repo root")
	}
}

func TestLoopbackAddr(t *testing.T) {
	for _, ok := range []string{"127.0.0.1:7777", "localhost:0", "[::1]:8080"} {
		if err := LoopbackAddr(ok); err != nil {
			t.Errorf("LoopbackAddr(%q) = %v, want nil", ok, err)
		}
	}
	// An empty host binds every interface; a routable one is remote
	// access, which ADR-022 refuses rather than defaults away.
	for _, bad := range []string{":7777", "0.0.0.0:7777", "192.168.1.10:7777", "example.com:80", "7777"} {
		if err := LoopbackAddr(bad); err == nil {
			t.Errorf("LoopbackAddr(%q) = nil, want refusal", bad)
		}
	}
}

func TestNonLoopbackHostIsRefused(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "/api/overview", nil)
	req.Host = "hobbes.example.com"
	rec := httptest.NewRecorder()
	f.srv.Handler().ServeHTTP(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("non-loopback Host = %d, want 403", rec.Code)
	}
}

// --- artifacts --------------------------------------------------------------

func TestOverviewReportsCountsAndBadges(t *testing.T) {
	f := newFixture(t)
	body := f.getJSON(t, "/api/overview")

	if body["ingested"] != true || body["narrated"] != true {
		t.Fatalf("overview = %v, want ingested and narrated", body)
	}
	if body["behind"] != false {
		t.Errorf("behind = %v, want false (artifact stamped at HEAD)", body["behind"])
	}
	// C-31: the verification base rides beside the language list.
	base, _ := body["verification_base"].(map[string]any)
	py, _ := base["python"].(map[string]any)
	if py["repos"] != float64(3) || !strings.HasPrefix(py["note"].(string), "verified on 3 repos") {
		t.Errorf("verification_base = %v, want python's §3.8 row", body["verification_base"])
	}
	counts, _ := body["counts"].(map[string]any)
	for field, want := range map[string]float64{
		"nodes": 3, "modules": 2, "module_edges": 1, "tests": 1,
		"docs": 2, "docs_stale": 1,
	} {
		if counts[field] != want {
			t.Errorf("counts[%s] = %v, want %v", field, counts[field], want)
		}
	}
}

func TestOverviewOnUningestedRepoGivesTheCommand(t *testing.T) {
	repo := t.TempDir()
	gitIn(t, repo, "init", "-q")
	srv, err := New(Config{RepoRoot: repo, LogDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	f := &fixture{repo: repo, logDir: "", srv: srv}
	body := f.getJSON(t, "/api/overview")
	if body["ingested"] != false {
		t.Fatalf("ingested = %v, want false", body["ingested"])
	}
	if !strings.Contains(body["hint"].(string), "hobbes ingest") {
		t.Errorf("hint = %q, want the ingest command", body["hint"])
	}
}

func TestArtifactsPassThroughUnchanged(t *testing.T) {
	f := newFixture(t)
	for _, tc := range []struct{ route, file string }{
		{"/api/graph", "graph.json"},
		{"/api/tests", "tests.json"},
		{"/api/interfaces", "interfaces.json"},
	} {
		rec := f.get(t, tc.route)
		if rec.Code != http.StatusOK {
			t.Fatalf("GET %s = %d", tc.route, rec.Code)
		}
		want, err := os.ReadFile(filepath.Join(f.repo, ".hobbes", "derived", tc.file))
		if err != nil {
			t.Fatal(err)
		}
		if rec.Body.String() != string(want) {
			t.Errorf("GET %s did not pass %s through byte-for-byte", tc.route, tc.file)
		}
	}
}

func TestMissingArtifactIs404WithHint(t *testing.T) {
	f := newFixture(t)
	if err := os.Remove(filepath.Join(f.repo, ".hobbes", "derived", "graph.json")); err != nil {
		t.Fatal(err)
	}
	rec := f.get(t, "/api/graph")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("GET /api/graph = %d, want 404", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "hobbes ingest") {
		t.Errorf("body = %s, want the ingest command", rec.Body)
	}
}

func TestDocsIndexBadgesFreshAndStale(t *testing.T) {
	f := newFixture(t)
	body := f.getJSON(t, "/api/docs")
	artifacts, _ := body["artifacts"].([]any)
	if len(artifacts) != 2 {
		t.Fatalf("got %d artifacts, want 2", len(artifacts))
	}
	status := map[string]string{}
	for _, a := range artifacts {
		m := a.(map[string]any)
		status[m["id"].(string)] = m["status"].(string)
	}
	if status["app.core"] != "fresh" {
		t.Errorf("app.core = %q, want fresh", status["app.core"])
	}
	if status["tests.test_core"] != "stale" {
		t.Errorf("tests.test_core = %q, want stale", status["tests.test_core"])
	}
}

func TestEditingASourceFlipsItsBadge(t *testing.T) {
	f := newFixture(t)
	if got := f.getJSON(t, "/api/docs/module/app.core")["status"]; got != "fresh" {
		t.Fatalf("status = %v, want fresh before the edit", got)
	}
	// An uncommitted edit is enough: staleness hashes the working tree
	// (ADR-019), so the badge flips before anything is committed.
	writeFile(t, filepath.Join(f.repo, "src", "app", "core.py"), "def run():\n    return 2\n")
	body := f.getJSON(t, "/api/docs/module/app.core")
	if body["status"] != "stale" {
		t.Fatalf("status = %v, want stale after the edit", body["status"])
	}
	changed, _ := body["changed"].([]any)
	if len(changed) != 1 || changed[0] != "src/app/core.py" {
		t.Errorf("changed = %v, want [src/app/core.py]", changed)
	}
	// The other artifact's badge must not move — the M5 exit criterion,
	// restated at the web surface.
	if got := f.getJSON(t, "/api/docs/test/tests.test_core")["status"]; got != "stale" {
		t.Errorf("test doc = %v, want its own (already stale) badge unchanged", got)
	}
}

func TestModuleDocRejectsTraversal(t *testing.T) {
	f := newFixture(t)
	// Slash-bearing ids are legal (ADR-021 path ids); traversal is not.
	for _, id := range []string{"../../../etc/passwd", "..", "a/../../b"} {
		rec := f.get(t, "/api/docs/module/"+id)
		if rec.Code == http.StatusOK {
			t.Errorf("GET /api/docs/module/%s = 200, want refusal", id)
		}
	}
}

func TestNestedModuleDocIDResolves(t *testing.T) {
	f := newFixture(t)
	// TS/JS ids are repo-relative paths and nest on disk (ADR-021).
	writeJSONFile(t, filepath.Join(f.repo, ".hobbes", "derived", "docs", "modules", "src", "flow.json"),
		map[string]any{
			"kind": "module-doc", "id": "src/flow", "path": "src/flow.ts",
			"sources": []any{},
			"purpose": map[string]any{"text": "flow", "pins": []any{}},
		})
	body := f.getJSON(t, "/api/docs/module/src/flow")
	if body["id"] != "src/flow" {
		t.Fatalf("id = %v, want src/flow", body["id"])
	}
}

func TestInvariantsRenderFromYAML(t *testing.T) {
	f := newFixture(t)
	writeFile(t, filepath.Join(f.repo, ".hobbes", "derived", "docs", "invariants.inferred.yaml"),
		"schema_version: 1\nkind: inferred-invariants\nsha: abc\ndirty: false\n"+
			"sources:\n- blob_sha: "+blobSHA(t, f.repo, "src/app/core.py")+"\n  path: src/app/core.py\n"+
			"invariants:\n- id: INF-1\n  statement: only core runs\n  scope: .\n  status: inferred\n"+
			"  evidence:\n  - path: src/app/core.py\n    line: 1\n")
	body := f.getJSON(t, "/api/docs/invariants")
	if body["status"] != "fresh" {
		t.Errorf("status = %v, want fresh", body["status"])
	}
	invs, _ := body["invariants"].([]any)
	if len(invs) != 1 {
		t.Fatalf("got %d invariants, want 1", len(invs))
	}
	first := invs[0].(map[string]any)
	if first["id"] != "INF-1" || first["statement"] != "only core runs" {
		t.Errorf("invariant = %v", first)
	}
	if ev, _ := first["evidence"].([]any); len(ev) != 1 {
		t.Errorf("evidence = %v, want one pin", first["evidence"])
	}
}

// --- source and diff --------------------------------------------------------

func TestSourceServesRepoFile(t *testing.T) {
	f := newFixture(t)
	body := f.getJSON(t, "/api/source?path=src/app/core.py")
	lines, _ := body["lines"].([]any)
	if len(lines) != 2 || lines[0] != "def run():" {
		t.Fatalf("lines = %v", lines)
	}
}

func TestSourceRefusesEscapes(t *testing.T) {
	f := newFixture(t)
	for _, p := range []string{
		"../../../etc/passwd", "/etc/passwd", "src/../../escape", "",
	} {
		rec := f.get(t, "/api/source?path="+p)
		if rec.Code == http.StatusOK {
			t.Errorf("GET /api/source?path=%q = 200, want refusal", p)
		}
	}
}

func TestSourceRefusesTFState(t *testing.T) {
	f := newFixture(t)
	writeFile(t, filepath.Join(f.repo, "infra", "terraform.tfstate"), `{"secret":1}`)
	writeFile(t, filepath.Join(f.repo, "infra", "terraform.tfstate.backup"), `{"secret":1}`)
	for _, p := range []string{"infra/terraform.tfstate", "infra/terraform.tfstate.backup"} {
		rec := f.get(t, "/api/source?path="+p)
		if rec.Code != http.StatusForbidden {
			t.Errorf("GET /api/source?path=%s = %d, want 403", p, rec.Code)
		}
		if strings.Contains(rec.Body.String(), "secret") {
			t.Fatalf("tfstate contents leaked in the refusal body")
		}
	}
}

func TestSourceRefusesBinary(t *testing.T) {
	f := newFixture(t)
	if err := os.WriteFile(filepath.Join(f.repo, "blob.bin"), []byte{0x1, 0x0, 0x2}, 0o644); err != nil {
		t.Fatal(err)
	}
	if rec := f.get(t, "/api/source?path=blob.bin"); rec.Code != http.StatusUnsupportedMediaType {
		t.Fatalf("binary file = %d, want 415", rec.Code)
	}
}

func TestDiffDefaultsToWorkingTree(t *testing.T) {
	f := newFixture(t)
	writeFile(t, filepath.Join(f.repo, "src", "app", "core.py"), "def run():\n    return 2\n")
	body := f.getJSON(t, "/api/diff")
	if body["mode"] != "working-tree" {
		t.Fatalf("mode = %v, want working-tree", body["mode"])
	}
	if !strings.Contains(body["patch"].(string), "return 2") {
		t.Errorf("patch missing the edit: %v", body["patch"])
	}
	files, _ := body["files"].([]any)
	if len(files) != 1 {
		t.Fatalf("files = %v, want one", files)
	}
	if first := files[0].(map[string]any); first["path"] != "src/app/core.py" {
		t.Errorf("file = %v", first)
	}
}

func TestDiffRangeAndBadRefs(t *testing.T) {
	f := newFixture(t)
	base := gitIn(t, f.repo, "rev-parse", "HEAD")
	writeFile(t, filepath.Join(f.repo, "src", "app", "core.py"), "def run():\n    return 3\n")
	gitIn(t, f.repo, "commit", "-qam", "change")
	head := gitIn(t, f.repo, "rev-parse", "HEAD")

	body := f.getJSON(t, "/api/diff?base="+base+"&head="+head)
	if body["mode"] != "range" {
		t.Fatalf("mode = %v, want range", body["mode"])
	}
	if !strings.Contains(body["patch"].(string), "return 3") {
		t.Errorf("patch = %v", body["patch"])
	}

	// A ref-shaped flag must not reach git as an option.
	for _, bad := range []string{"--output=/tmp/pwned", "nope-not-a-ref"} {
		rec := f.get(t, "/api/diff?base="+bad+"&head="+head)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("GET /api/diff base=%q = %d, want 400", bad, rec.Code)
		}
	}
}

func TestRefsListsBranchesAndCommits(t *testing.T) {
	f := newFixture(t)
	body := f.getJSON(t, "/api/refs")
	refs, _ := body["refs"].([]any)
	if len(refs) == 0 {
		t.Fatal("want at least the current branch and one commit")
	}
	kinds := map[string]bool{}
	for _, r := range refs {
		kinds[r.(map[string]any)["kind"].(string)] = true
	}
	if !kinds["branch"] || !kinds["commit"] {
		t.Errorf("kinds = %v, want branch and commit", kinds)
	}
}

// --- app assets -------------------------------------------------------------

func TestUnknownPathServesTheApp(t *testing.T) {
	f := newFixture(t)
	rec := f.get(t, "/graph")
	// Unbuilt binaries serve the stub; either way the response is HTML
	// naming hobbes-web, never a bare 404 page.
	if !strings.Contains(rec.Header().Get("Content-Type"), "text/html") {
		t.Fatalf("content-type = %q, want html", rec.Header().Get("Content-Type"))
	}
	if !strings.Contains(strings.ToLower(rec.Body.String()), "hobbes") {
		t.Errorf("body does not look like the app: %s", rec.Body.String())
	}
}

// TestAppIsBuiltIntoThisBinary is a build-state check, not a behaviour
// one: it is skipped on a tree that has never run `npm run build`, and
// asserts the real app is served when it has.
func TestAppIsBuiltIntoThisBinary(t *testing.T) {
	if !Built() {
		t.Skip("web app not built; run `cd web && npm run build`")
	}
	f := newFixture(t)
	rec := f.get(t, "/app.js")
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /app.js = %d, want the bundled app", rec.Code)
	}
	if !strings.Contains(f.get(t, "/").Body.String(), "app.js") {
		t.Error("index.html does not reference the bundle")
	}
}

func TestBehaviorsJoinEveryTestDoc(t *testing.T) {
	f := newFixture(t)
	body := f.getJSON(t, "/api/behaviors")
	behaviors, _ := body["behaviors"].([]any)
	if len(behaviors) != 1 {
		t.Fatalf("got %d behaviors, want 1", len(behaviors))
	}
	b := behaviors[0].(map[string]any)
	if b["test"] != "tests/test_core.py::test_run" {
		t.Errorf("test = %v", b["test"])
	}
	if b["text"] != "run returns truthy" {
		t.Errorf("text = %v", b["text"])
	}
	// The badge of the artifact the line came from travels with it, so
	// the Tests tab can show a stale summary as stale.
	if b["status"] != "stale" {
		t.Errorf("status = %v, want stale (the fixture's test doc is)", b["status"])
	}
	if b["doc_id"] != "tests.test_core" {
		t.Errorf("doc_id = %v", b["doc_id"])
	}
}

func TestBehaviorsWithoutNarrateGivesTheCommand(t *testing.T) {
	f := newFixture(t)
	if err := os.RemoveAll(filepath.Join(f.repo, ".hobbes", "derived", "docs", "tests")); err != nil {
		t.Fatal(err)
	}
	body := f.getJSON(t, "/api/behaviors")
	if got, _ := body["behaviors"].([]any); len(got) != 0 {
		t.Fatalf("behaviors = %v, want empty", got)
	}
	if !strings.Contains(body["hint"].(string), "hobbes narrate") {
		t.Errorf("hint = %v", body["hint"])
	}
}

func TestUnmatchedAPIPathIs404JSONNotTheApp(t *testing.T) {
	f := newFixture(t)
	// Without an /api/ floor the SPA catch-all answers 200 with HTML, so
	// a typo'd route or a wrong method reads as success.
	for _, target := range []string{"/api/nope", "/api/docs/modules", "/api/graph/extra"} {
		rec := f.get(t, target)
		if rec.Code != http.StatusNotFound {
			t.Errorf("GET %s = %d, want 404", target, rec.Code)
		}
		if ct := rec.Header().Get("Content-Type"); !strings.Contains(ct, "json") {
			t.Errorf("GET %s content-type = %q, want json", target, ct)
		}
	}
}

func TestAppRefusesWrites(t *testing.T) {
	f := newFixture(t)
	if rec := f.do(t, http.MethodPost, "/"); rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("POST / = %d, want 405 — escalation verdicts are the only writes", rec.Code)
	}
}

// The surface restates the artifact schema in types.ts, so serving a
// version it cannot render would surface as a blank tab rather than as
// the mismatch it is (ADR-028). Both the byte-for-byte pass-through and
// the parsed overview must refuse it.
func TestArtifactVersionIsGated(t *testing.T) {
	f := newFixture(t)
	derived := filepath.Join(f.repo, ".hobbes", "derived")
	writeJSONFile(t, filepath.Join(derived, "graph.json"), map[string]any{
		"schema_version": 99, "sha": "abc", "nodes": []any{}, "module_edges": []any{},
	})

	res := f.get(t, "/api/graph")
	if res.Code != http.StatusConflict {
		t.Errorf("GET /api/graph on an unknown version = %d, want 409", res.Code)
	}
	if !strings.Contains(res.Body.String(), "schema v99") {
		t.Errorf("the refusal should name the version found: %s", res.Body.String())
	}

	// The overview parses rather than passing through, and must not report
	// a repo as ingested off an artifact it could not read.
	var out map[string]any
	res = f.get(t, "/api/overview")
	if err := json.Unmarshal(res.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out["ingested"] == true {
		t.Error("overview claimed ingested from a refused artifact")
	}
}
