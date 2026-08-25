package grade

import (
	"bytes"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/pytrace"
)

// The Python trace oracle on the miniapp fixture (O6's self-test). Hand
// truth under its two tests: top_level, Engine(...), run, check,
// normalize (twice), helper — seven observed in-repo pairs, all seven
// drawn by Hobbes; api.py and cli.py never import, so their three edges
// are unobserved as not-loaded; nothing is suspect. Runs under the
// pipeline venv (CPython 3.12, pytest) via uv; skipped without it.
func TestMiniappTrace(t *testing.T) {
	if _, err := exec.LookPath("uv"); err != nil {
		t.Skip("uv not on PATH")
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	out := filepath.Join(t.TempDir(), "oracle.json")
	o, err := pytrace.Run(pytrace.Options{
		Repo: fixtures + "/miniapp", Module: ".", Runs: 2, SysPath: []string{"src"}, Out: out,
		Python: []string{"uv", "run", "--project", pipeline, "python"},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if o.Kind != "trace" || o.Runs != 2 || o.Coverage["files_loaded"] != 4 || o.Coverage["files_in_module"] != 8 {
		t.Fatalf("trace export header: kind %s runs %d coverage %v", o.Kind, o.Runs, o.Coverage)
	}
	pairs := map[string]bool{}
	for _, s := range o.Sites {
		if s.Mode != "observed" {
			t.Errorf("trace sites are observed, got %s", s.Mode)
		}
		for _, tg := range s.Targets {
			if !tg.External {
				pairs[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
		}
	}
	want := []string{
		"tests/test_core.py:12 -> src/miniapp/core.py:23",
		"src/miniapp/core.py:24 -> src/miniapp/core.py:10",
		"src/miniapp/core.py:25 -> src/miniapp/core.py:14",
		"src/miniapp/core.py:15 -> src/miniapp/core.py:18",
		"src/miniapp/core.py:16 -> src/miniapp/util.py:6",
		"tests/test_core.py:8 -> src/miniapp/util.py:6",
		"tests/test_core.py:17 -> tests/test_core.py:7",
	}
	for _, w := range want {
		if !pairs[w] {
			t.Errorf("missing observed pair %s", w)
		}
		delete(pairs, w)
	}
	for extra := range pairs {
		t.Errorf("unexpected in-repo pair %s", extra)
	}
	h, err := export.FromFile("../../testdata/miniapp.graph.json", ".", "py")
	if err != nil {
		t.Fatal(err)
	}
	r := Grade(h, o)
	if r.Total.Confirmed != 7 || r.Total.Suspect != 0 || r.Total.Unobserved != 3 || r.SilentBy["not-loaded"] != 3 {
		t.Fatalf("miniapp buckets: %+v %v", r.Total, r.SilentBy)
	}
	if r.Precision != nil {
		t.Fatal("a trace cell never reports precision")
	}
	if r.Recall == nil || *r.Recall != 1 || r.OraclePairs != 7 || r.SitesObserved != 7 || r.SitesTotal != 10 {
		t.Fatalf("miniapp recall %v (%d/%d) sites %d/%d", r.Recall, r.RecallHits, r.OraclePairs, r.SitesObserved, r.SitesTotal)
	}
	var buf bytes.Buffer
	Print(&buf, r)
	txt := buf.String()
	for _, must := range []string{"recall-against-executed 100.0% (7/7", "over 2 run(s)", "coverage: hobbes sites observed 7/10", "not precision"} {
		if !strings.Contains(txt, must) {
			t.Errorf("report must say %q:\n%s", must, txt)
		}
	}
	if strings.Contains(txt, "precision-against-oracle") {
		t.Errorf("trace report must not print a precision line:\n%s", txt)
	}
}

// The §3.1 buckets on synthetic data: a wrong target on a line whose
// only observed callees are in-repo is suspect; the same on a line that
// also called C is line-mixed (charged to nobody); a line that never
// called is line-not-called; a file that never ran is not-loaded.
func TestTraceBuckets(t *testing.T) {
	pos := func(p string, l int) edges.Pos { return edges.Pos{Path: p, Line: l} }
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: pos("a.py", 1), Target: pos("b.py", 10), Tier: "semantic"},
		{Site: pos("a.py", 2), Target: pos("b.py", 10), Tier: "semantic"},
		{Site: pos("a.py", 3), Target: pos("b.py", 10), Tier: "syntactic"},
		{Site: pos("a.py", 4), Target: pos("b.py", 10), Tier: "semantic"},
		{Site: pos("z.py", 1), Target: pos("b.py", 10), Tier: "semantic"},
	}}
	o := &edges.OracleExport{Kind: "trace", Runs: 1, Files: []string{"a.py", "b.py"}, Sites: []edges.Site{
		{Pos: pos("a.py", 1), Mode: "observed", Targets: []edges.Target{{Pos: pos("b.py", 10), Name: "f", Kind: "function"}}},
		{Pos: pos("a.py", 2), Mode: "observed", Targets: []edges.Target{{Pos: pos("b.py", 20), Name: "g", Kind: "function"}}},
		{Pos: pos("a.py", 3), Mode: "observed", CCallees: 1, Targets: []edges.Target{{Pos: pos("b.py", 20), Name: "g", Kind: "function"}}},
	}}
	r := Grade(h, o)
	got := map[string]string{}
	for _, row := range r.Rows {
		got[row.Edge.Site.Key()] = row.Bucket + "/" + row.Reason
	}
	want := map[string]string{
		"a.py:1": "confirmed/", "a.py:2": "suspect/", "a.py:3": "unobserved/line-mixed",
		"a.py:4": "unobserved/line-not-called", "z.py:1": "unobserved/not-loaded",
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s: want %s got %s", k, v, got[k])
		}
	}
	if r.Total.Contradicted != 0 || r.Precision != nil {
		t.Error("a trace never contradicts")
	}
	if r.SuspectRate == nil || *r.SuspectRate != 0.5 {
		t.Errorf("suspect rate 1/(1+1): %v", r.SuspectRate)
	}
	// Recall: three observed in-repo pairs, one drawn.
	if r.OraclePairs != 3 || r.RecallHits != 1 || r.MissBy["observed→function"] != 2 {
		t.Errorf("recall %d/%d misses %v", r.RecallHits, r.OraclePairs, r.MissBy)
	}
	if r.ByTier["syntactic"].Unobserved != 1 {
		t.Errorf("tier split lost: %+v", r.ByTier)
	}
}
