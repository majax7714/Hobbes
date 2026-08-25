package export

import "testing"

func TestMinigoExport(t *testing.T) {
	h, err := FromFile("../../testdata/minigo.graph.json", ".", "go")
	if err != nil {
		t.Fatal(err)
	}
	if len(h.Edges) != 5 {
		t.Fatalf("minigo has 5 graded call edges, got %d", len(h.Edges))
	}
	want := map[string]string{
		"cmd/mini/main.go:12":               "internal/policy/policy.go:26",
		"cmd/mini/main.go:16":               "internal/policy/policy.go:36",
		"internal/policy/policy.go:28":      "internal/policy/policy.go:21",
		"internal/policy/policy_test.go:7":  "internal/policy/policy.go:26",
		"internal/policy/policy_test.go:13": "internal/policy/policy.go:26",
	}
	for _, e := range h.Edges {
		if want[e.Site.Key()] != e.Target.Key() {
			t.Errorf("%s -> %s not in the hand truth", e.Site.Key(), e.Target.Key())
		}
		if e.Tier != "semantic" || len(e.Lanes) != 1 || e.Lanes[0] != "scip" {
			t.Errorf("tier/lane lost: %+v", e)
		}
	}
}

// The cell filter keeps sites under the module and targets anywhere.
func TestTwomodCells(t *testing.T) {
	app, err := FromFile("../../testdata/twomod.graph.json", "app", "go")
	if err != nil {
		t.Fatal(err)
	}
	if len(app.Edges) != 3 {
		t.Fatalf("app cell: want 3 edges, got %d", len(app.Edges))
	}
	cross := 0
	for _, e := range app.Edges {
		if e.Site.Path[:4] != "app/" {
			t.Errorf("site outside cell: %s", e.Site.Key())
		}
		if e.Target.Path[:4] == "lib/" {
			cross++
		}
	}
	if cross != 2 {
		t.Errorf("want 2 cross-module targets (Greet, Lookup), got %d", cross)
	}
	lib, err := FromFile("../../testdata/twomod.graph.json", "lib", "go")
	if err != nil {
		t.Fatal(err)
	}
	if len(lib.Edges) != 2 {
		t.Fatalf("lib cell: want 2 edges (the two tests), got %d", len(lib.Edges))
	}
}

// miniapp (Python): ten scip-resolved calls, one of them a constructor —
// an edge to the class symbol, which the trace oracle confirms as a call
// of the class.
func TestMiniappPyExport(t *testing.T) {
	h, err := FromFile("../../testdata/miniapp.graph.json", ".", "py")
	if err != nil {
		t.Fatal(err)
	}
	if len(h.Edges) != 10 {
		t.Fatalf("miniapp has 10 graded call edges, got %d", len(h.Edges))
	}
	ctor := false
	for _, e := range h.Edges {
		if e.Site.Key() == "src/miniapp/core.py:24" && e.Target.Key() == "src/miniapp/core.py:10" {
			ctor = true
		}
	}
	if !ctor {
		t.Error("Engine(10) at core.py:24 must export as an edge to the class declaration at core.py:10")
	}
	if _, err := FromFile("../../testdata/miniapp.graph.json", ".", "rb"); err == nil {
		t.Error("unknown lang must be refused")
	}
}

// minirust (Rust): ten scip-resolved calls, one of them a macro
// invocation (`twice!`) — expanded by the compiler, not called, so it is
// excluded from the graded set and counted.
func TestMinirustExportExcludesMacros(t *testing.T) {
	h, err := FromFile("../../testdata/minirust.graph.json", ".", "rust")
	if err != nil {
		t.Fatal(err)
	}
	if len(h.Edges) != 9 || h.Excluded["macro"] != 1 {
		t.Fatalf("minirust: want 9 graded edges + 1 macro excluded, got %d + %v", len(h.Edges), h.Excluded)
	}
	for _, e := range h.Edges {
		if e.Target.Key() == "src/lib.rs:3" {
			t.Errorf("the macro at lib.rs:3 must not be a graded target: %+v", e)
		}
	}
}

// A Python package's symbols live in its __init__.py, a "package" node
// (H-12: dropping them silently lost 113 edges on the first O6 pass).
func TestPackageNodesAreTargets(t *testing.T) {
	g := &graph{}
	g.Nodes = append(g.Nodes, struct {
		ID   string `json:"id"`
		Kind string `json:"kind"`
		Path string `json:"path"`
	}{"app", "package", "src/app/__init__.py"}, struct {
		ID   string `json:"id"`
		Kind string `json:"kind"`
		Path string `json:"path"`
	}{"app.cli", "module", "src/app/cli.py"})
	g.Symbols = append(g.Symbols, struct {
		ID     string `json:"id"`
		Module string `json:"module"`
		Line   int    `json:"line"`
		Kind   string `json:"kind"`
	}{"app.run", "app", 7, "function"})
	g.SymbolEdges = append(g.SymbolEdges, struct {
		From     string `json:"from"`
		To       string `json:"to"`
		Type     string `json:"type"`
		Tier     string `json:"tier"`
		Evidence []struct {
			Lane string `json:"lane"`
			Path string `json:"path"`
			Line int    `json:"line"`
		} `json:"evidence"`
	}{From: "app.cli.main", To: "app.run", Type: "calls", Tier: "semantic", Evidence: []struct {
		Lane string `json:"lane"`
		Path string `json:"path"`
		Line int    `json:"line"`
	}{{"scip", "src/app/cli.py", 3}}})
	h, err := From(g, ".", "py")
	if err != nil {
		t.Fatal(err)
	}
	if len(h.Edges) != 1 || h.Edges[0].Target.Key() != "src/app/__init__.py:7" {
		t.Fatalf("package target lost: %+v", h.Edges)
	}
}
