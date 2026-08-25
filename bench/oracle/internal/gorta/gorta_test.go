package gorta

import (
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

const fixtures = "../../../../pipeline/tests/fixtures"

// inRepo flattens a cell to its in-repo "site -> target" pairs at line
// grain (two sites on one line are two pairs).
func inRepo(o *edges.OracleExport) map[string]bool {
	out := map[string]bool{}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if !tg.External {
				out[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
		}
	}
	return out
}

func assertPairs(t *testing.T, got map[string]bool, want ...string) {
	t.Helper()
	for _, w := range want {
		if !got[w] {
			t.Errorf("missing %s", w)
		}
		delete(got, w)
	}
	for extra := range got {
		t.Errorf("unexpected in-repo edge %s", extra)
	}
}

// The minigo truth by hand: two handlers into policy, Resolve into the
// pointer-receiver method through Go's auto-address, two tests into
// Resolve. Roots: the binary and the policy test main.
func TestMinigoExact(t *testing.T) {
	o, err := Run(Options{Repo: fixtures + "/minigo", Module: "."})
	if err != nil {
		t.Fatal(err)
	}
	if len(o.Roots) != 2 {
		t.Fatalf("roots: want 2 (binary + test main), got %v", o.Roots)
	}
	assertPairs(t, inRepo(o),
		"cmd/mini/main.go:12 -> internal/policy/policy.go:26",
		"cmd/mini/main.go:16 -> internal/policy/policy.go:36",
		"internal/policy/policy.go:28 -> internal/policy/policy.go:21",
		"internal/policy/policy_test.go:7 -> internal/policy/policy.go:26",
		"internal/policy/policy_test.go:13 -> internal/policy/policy.go:26",
	)
	for _, s := range o.Sites {
		if s.Mode != "static" {
			t.Errorf("minigo has no dynamic call, got %s at %s", s.Mode, s.Pos.Key())
		}
	}
}

// twomod/app: the replaced lib module is inside the program, so the
// cross-module targets are graded; sites stay inside the cell.
func TestTwomodAppExact(t *testing.T) {
	o, err := Run(Options{Repo: fixtures + "/twomod", Module: "app"})
	if err != nil {
		t.Fatal(err)
	}
	if len(o.Roots) != 1 || o.Roots[0] != "example.com/app/cmd/app" {
		t.Fatalf("roots: %v", o.Roots)
	}
	assertPairs(t, inRepo(o),
		"app/cmd/app/main.go:16 -> app/cmd/app/main.go:11",
		"app/cmd/app/main.go:16 -> lib/lib.go:8",
		"app/cmd/app/main.go:17 -> lib/lib.go:27",
	)
}

// A line with two in-repo calls (banner(lib.Greet(...))) is two oracle
// sites at different columns — the tolerance the matcher logs.
func TestTwomodAppTwoSitesOneLine(t *testing.T) {
	o, err := Run(Options{Repo: fixtures + "/twomod", Module: "app"})
	if err != nil {
		t.Fatal(err)
	}
	var targets []string
	for _, s := range o.Sites {
		if s.Pos.Key() == "app/cmd/app/main.go:16" {
			for _, tg := range s.Targets {
				if !tg.External {
					targets = append(targets, tg.Pos.Key())
				}
			}
		}
	}
	if len(targets) != 2 {
		t.Fatalf("want banner and Greet on line 16, got %v", targets)
	}
	for _, f := range o.Files {
		if f[:4] != "app/" {
			t.Errorf("file outside the cell reported: %s", f)
		}
	}
}

// twomod/lib through its test main: the interface call is dynamic, its
// one concrete target is MemStore.Get, and the interface method is named
// so the matcher can bucket a Hobbes edge to it as abstract.
func TestTwomodLibDynamic(t *testing.T) {
	o, err := Run(Options{Repo: fixtures + "/twomod", Module: "lib"})
	if err != nil {
		t.Fatal(err)
	}
	if len(o.Roots) != 1 || o.Roots[0] != "example.com/lib.test" {
		t.Fatalf("a library cell roots at its test main, got %v", o.Roots)
	}
	assertPairs(t, inRepo(o),
		"lib/lib.go:28 -> lib/lib.go:21",
		"lib/lib_test.go:6 -> lib/lib.go:8",
		"lib/lib_test.go:12 -> lib/lib.go:27",
	)
	var dyn *edges.Site
	for i := range o.Sites {
		if o.Sites[i].Pos.Key() == "lib/lib.go:28" {
			dyn = &o.Sites[i]
		}
	}
	if dyn == nil || dyn.Mode != "dynamic" {
		t.Fatalf("lib.go:28 should be a dynamic site: %+v", dyn)
	}
	if dyn.Interface == nil || dyn.Interface.Pos.Key() != "lib/lib.go:14" {
		t.Fatalf("interface method should be Store.Get at lib/lib.go:14: %+v", dyn.Interface)
	}
}

func TestNoRootsIsAnError(t *testing.T) {
	if _, err := Run(Options{Repo: fixtures + "/twomod", Module: "lib/nonexistent"}); err == nil {
		t.Fatal("a module directory that does not exist must fail loudly")
	}
}

// A generic instantiation is the source function, not a wrapper to see
// through: the call to sortedKeys[string] grades against sortedKeys at
// its declaration, never against the sort.Strings inside its body (the
// O2 match-defect).
func TestGenericInstantiationFoldsToOrigin(t *testing.T) {
	o, err := Run(Options{Repo: "../../testdata/generic", Module: "."})
	if err != nil {
		t.Fatal(err)
	}
	assertPairs(t, inRepo(o), "main.go:15 -> main.go:5")
	for _, s := range o.Sites {
		if s.Pos.Key() == "main.go:15" {
			for _, tg := range s.Targets {
				if tg.External {
					t.Errorf("sort.Strings leaked to the caller's site: %s", tg.Name)
				}
			}
		}
	}
}
