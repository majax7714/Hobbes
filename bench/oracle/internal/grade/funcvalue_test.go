package grade

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// A call through a function-valued variable: Hobbes names the binding,
// the oracle the function the value holds. Abstract, not contradicted
// (D-O4, 2026-08-28 — mux's RegexpCompileFunc, cheerio's `const parse =
// getParse(..)`; 47 rows over two cells). A function target that the
// oracle disagrees with stays contradicted.
func TestFuncValueBindingIsAbstract(t *testing.T) {
	site := edges.Pos{Path: "mux.go", Line: 595}
	binding := edges.Pos{Path: "mux.go", Line: 26}
	held := edges.Pos{Path: "regexp.go", Line: 130}
	h := &edges.HobbesExport{SHA: "x", Edges: []edges.HobbesEdge{
		{Site: site, Target: binding, TargetID: "mux.RegexpCompileFunc", TargetKind: "var", Tier: "semantic"},
		{Site: edges.Pos{Path: "mux.go", Line: 600}, Target: binding, TargetID: "mux.Other", TargetKind: "function", Tier: "semantic"},
	}}
	o := &edges.OracleExport{Kind: "reachability", Files: []string{"mux.go", "regexp.go"}, Roots: []string{"r"}, Sites: []edges.Site{
		{Pos: site, Mode: "dynamic", Targets: []edges.Target{{Pos: held, Name: "regexp.Compile", Kind: "function"}}},
		{Pos: edges.Pos{Path: "mux.go", Line: 600}, Mode: "static", Targets: []edges.Target{{Pos: held, Name: "regexp.Compile", Kind: "function"}}},
	}}
	r := Grade(h, o)
	if r.Total.Abstract != 1 || r.Total.Contradicted != 1 {
		t.Fatalf("buckets %+v", r.Total)
	}
	for _, row := range r.Rows {
		if row.Bucket == "abstract" && row.Reason != "func-value" {
			t.Fatalf("abstract row must say why: %+v", row)
		}
	}
}

// `@overload` stubs and the implementation are one declaration: the
// tracer anchors the implementation's first line at the first stub's def
// line, where the graph keeps the symbol (D-O4, 2026-08-28; click's 47).
// Runs the tracer's index over a snippet with the host python3 — our
// own fixture, no repo code.
func TestOverloadStubsAnchorTheImplementation(t *testing.T) {
	py, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("python3 not on PATH")
	}
	dir := t.TempDir()
	src := strings.Join([]string{
		"import typing as t",
		"",
		"@t.overload",
		"def f(x: int) -> int: ...",
		"@t.overload",
		"def f(x: str) -> str: ...",
		"def f(x):",
		"    return x",
		"",
		"@t.overload",
		"def g(x: int) -> int: ...",
		"@staticmethod",
		"def g(x):",
		"    return x",
		"",
		"def h():",
		"    return 1",
		"",
	}, "\n")
	os.WriteFile(filepath.Join(dir, "m.py"), []byte(src), 0o644)
	script, _ := filepath.Abs("../../py")
	probe := "import sys; sys.path.insert(0, '" + script + "'); import trace_oracle as o; from pathlib import Path; " +
		"i = o.DeclIndex(Path('" + dir + "')).file('m.py'); print(i['first_to_def'][7], i['first_to_def'][12], i['first_to_def'][16], i['qual']['f'][0])"
	out, err := exec.Command(py, "-c", probe).CombinedOutput()
	if err != nil {
		t.Fatalf("%v: %s", err, out)
	}
	if got := strings.TrimSpace(string(out)); got != "4 11 16 4" {
		t.Fatalf("anchors: got %q, want implementation f→4, decorated g→11, plain h→16, qual f→4", got)
	}
}
