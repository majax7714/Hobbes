package grade

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
	"github.com/majax7714/Hobbes/bench/oracle/internal/pytrace"
	"github.com/majax7714/Hobbes/bench/oracle/internal/rustmir"
)

// The fixtures prove true edges confirm. These prove wrong edges do not:
// every fixture export is poisoned — each edge re-targeted to another
// declaration the oracle never resolved that site to — and the grader
// must refuse every one. A matcher that falsely confirms passes every
// other test in this package.

func assertPoisonRefused(t *testing.T, h *edges.HobbesExport, o *edges.OracleExport, allowUnjudged bool) {
	t.Helper()
	c := CheckPoison(h, o)
	if c.Seeded == 0 || c.Seeded != len(h.Edges) {
		t.Fatalf("poison must seed one wrong edge per edge: seeded %d of %d", c.Seeded, len(h.Edges))
	}
	if c.Confirmed != 0 || !c.Passed {
		t.Fatalf("falsely confirmed %d seeded wrong edges: %+v", c.Confirmed, c.Falsely)
	}
	if !allowUnjudged && c.Refused != c.Seeded {
		t.Fatalf("a resolution/reachability oracle spoke at every confirmed site, so every poisoned edge must be refused: refused %d unjudged %d of %d", c.Refused, c.Unjudged, c.Seeded)
	}
}

func TestPoisonRetargetsEveryEdge(t *testing.T) {
	h, _ := export.FromFile("../../testdata/minigo.graph.json", ".", "go")
	o, err := gorta.Run(gorta.Options{Repo: fixtures + "/minigo", Module: "."})
	if err != nil {
		t.Fatal(err)
	}
	p := Poison(h, o)
	if len(p.Edges) != len(h.Edges) {
		t.Fatalf("poisoned %d of %d", len(p.Edges), len(h.Edges))
	}
	for i, e := range p.Edges {
		if e.Target == h.Edges[i].Target || e.Site != h.Edges[i].Site || e.TargetID != "poison:"+h.Edges[i].TargetID {
			t.Errorf("edge %d not poisoned in place: %+v vs %+v", i, e, h.Edges[i])
		}
	}
}

func TestGoFixturesRefuseEveryPoisonedEdge(t *testing.T) {
	for _, c := range []struct{ repo, module, graph string }{
		{"minigo", ".", "minigo.graph.json"}, {"twomod", "app", "twomod.graph.json"}, {"twomod", "lib", "twomod.graph.json"},
	} {
		h, err := export.FromFile("../../testdata/"+c.graph, c.module, "go")
		if err != nil {
			t.Fatal(err)
		}
		o, err := gorta.Run(gorta.Options{Repo: fixtures + "/" + c.repo, Module: c.module})
		if err != nil {
			t.Fatal(err)
		}
		assertPoisonRefused(t, h, o, false)
	}
}

func TestTSFixtureRefusesEveryPoisonedEdge(t *testing.T) {
	if _, err := exec.LookPath("node"); err != nil {
		t.Skip("node not on PATH")
	}
	out := filepath.Join(t.TempDir(), "oracle.json")
	cmd := exec.Command("node", "../../ts/tsc-oracle.mjs", "--repo", fixtures+"/minits", "--zone", ".", "--out", out)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("tsc oracle: %v\n%s", err, b)
	}
	o := readOracle(t, out)
	h, err := export.FromFile("../../testdata/minits.graph.json", ".", "ts")
	if err != nil {
		t.Fatal(err)
	}
	assertPoisonRefused(t, h, o, false)
}

func TestPythonFixtureRefusesEveryPoisonedEdge(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	python := filepath.Join(pipeline, ".venv", "bin", "python")
	if _, err := os.Stat(python); err != nil {
		t.Skip("pipeline venv not built (uv sync)")
	}
	o, err := pytrace.Run(pytrace.Options{
		Repo: fixtures + "/miniapp", Module: ".", Runs: 1, SysPath: []string{"src"}, Out: filepath.Join(t.TempDir(), "oracle.json"),
		Python: []string{python},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	h, _ := export.FromFile("../../testdata/miniapp.graph.json", ".", "py")
	// A trace never contradicts: a poisoned edge at an executed line is
	// suspect (refused) or line-mixed / not-loaded (unjudged); never confirmed.
	assertPoisonRefused(t, h, o, true)
	c := CheckPoison(h, o)
	if c.Refused == 0 {
		t.Fatalf("the executed sites must refuse their poisoned edges as suspect: %+v", c)
	}
}

func TestRustFixtureRefusesEveryPoisonedEdge(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	if _, err := exec.LookPath("cargo"); err != nil {
		t.Skip("cargo not on PATH")
	}
	driver, _ := filepath.Abs("../../rust/target/release/mir-oracle")
	if _, err := exec.Command("test", "-x", driver).Output(); err != nil {
		t.Skip("mir-oracle driver not built")
	}
	repo, _ := filepath.Abs(fixtures + "/minirust")
	o, err := rustmir.Run(rustmir.Options{Repo: repo, Module: ".", Driver: driver, Out: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	h, _ := export.FromFile("../../testdata/minirust.graph.json", ".", "rust")
	assertPoisonRefused(t, h, o, false)
}

func readOracle(t *testing.T, path string) *edges.OracleExport {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var o edges.OracleExport
	if err := json.Unmarshal(raw, &o); err != nil {
		t.Fatal(err)
	}
	return &o
}
