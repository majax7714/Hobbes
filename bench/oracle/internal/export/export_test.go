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
