package grade

import (
	"bytes"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
)

const fixtures = "../../../../pipeline/tests/fixtures"

func cell(t *testing.T, repo, module, graph string) *Report {
	t.Helper()
	h, err := export.FromFile("../../testdata/"+graph, module)
	if err != nil {
		t.Fatal(err)
	}
	o, err := gorta.Run(gorta.Options{Repo: fixtures + "/" + repo, Module: module})
	if err != nil {
		t.Fatal(err)
	}
	return Grade(h, o)
}

// O1's exit: every fixture edge confirmed, zero contradicted, and the
// one dynamic miss where the hand truth puts it.
func TestMinigoAllConfirmed(t *testing.T) {
	r := cell(t, "minigo", ".", "minigo.graph.json")
	if r.Total != (TierCounts{Confirmed: 5}) {
		t.Fatalf("minigo buckets: %+v", r.Total)
	}
	if r.Precision == nil || *r.Precision != 1 || r.Recall == nil || *r.Recall != 1 || r.RecallHits != 5 || r.OraclePairs != 5 {
		t.Fatalf("minigo: precision %v recall %v (%d/%d)", r.Precision, r.Recall, r.RecallHits, r.OraclePairs)
	}
	if r.Roots != 2 {
		t.Fatalf("recall must carry its root count: %d", r.Roots)
	}
	if r.ByTier["semantic"].Confirmed != 5 {
		t.Fatalf("tier split lost: %+v", r.ByTier)
	}
}

func TestTwomodAppAllConfirmed(t *testing.T) {
	r := cell(t, "twomod", "app", "twomod.graph.json")
	if r.Total != (TierCounts{Confirmed: 3}) || r.RecallHits != 3 || r.OraclePairs != 3 {
		t.Fatalf("app: %+v recall %d/%d", r.Total, r.RecallHits, r.OraclePairs)
	}
	if r.Tolerance == 0 {
		t.Fatal("banner(lib.Greet()) puts two oracle sites on one line; the tolerance must be logged")
	}
}

// The interface call is Hobbes' first graded miss: no edge at all at
// lib.go:28 (not even to Store.Get), so it is a dynamic recall miss and
// nothing is contradicted.
func TestTwomodLibDynamicMiss(t *testing.T) {
	r := cell(t, "twomod", "lib", "twomod.graph.json")
	if r.Total != (TierCounts{Confirmed: 2}) {
		t.Fatalf("lib buckets: %+v", r.Total)
	}
	if r.RecallBy["static→named"] != (Fraction{Hits: 2, Pairs: 2}) || r.RecallBy["interface→named"] != (Fraction{Hits: 0, Pairs: 1}) {
		t.Fatalf("recall by class: %v", r.RecallBy)
	}
	if r.OraclePairs != 3 || r.RecallHits != 2 || r.MissBy["interface→named"] != 1 || len(r.Misses) != 1 {
		t.Fatalf("lib recall: %d/%d misses %v", r.RecallHits, r.OraclePairs, r.MissBy)
	}
	if m := r.Misses[0]; m.Site.Key() != "lib/lib.go:28" || m.Target.Pos.Key() != "lib/lib.go:21" {
		t.Fatalf("miss should be Lookup -> MemStore.Get: %+v", m)
	}
	var buf bytes.Buffer
	Print(&buf, r)
	out := buf.String()
	for _, want := range []string{"recall 66.7% (2/3", "at 1 roots", "recall[static→named      ] 100.0% (2/2)", "recall[interface→named   ]   0.0% (0/1)  misses 1 = 100.0% of all misses", "missed       lib/lib.go:28"} {
		if !strings.Contains(out, want) {
			t.Errorf("report lacks %q:\n%s", want, out)
		}
	}
}

// Bucket semantics on synthetic inputs: contradicted, abstract, and the
// three silent reasons.
func TestBuckets(t *testing.T) {
	site := edges.Pos{Path: "a.go", Line: 10}
	iface := edges.Pos{Path: "a.go", Line: 3}
	concrete := edges.Pos{Path: "a.go", Line: 20}
	o := &edges.OracleExport{
		Oracle: "go-rta", Kind: "reachability", Roots: []string{"m"},
		Files: []string{"a.go", "b.go"},
		Sites: []edges.Site{
			{Pos: site, Mode: "dynamic", Interface: &edges.Target{Pos: iface}, Targets: []edges.Target{{Pos: concrete}}},
			{Pos: edges.Pos{Path: "b.go", Line: 5}, Mode: "dynamic"},
		},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: site, Target: concrete, Tier: "semantic"},                              // confirmed
		{Site: site, Target: iface, Tier: "semantic"},                                 // abstract
		{Site: site, Target: edges.Pos{Path: "a.go", Line: 99}, Tier: "syntactic"},    // contradicted
		{Site: edges.Pos{Path: "b.go", Line: 5}, Target: concrete, Tier: "syntactic"}, // silent: no-targets
		{Site: edges.Pos{Path: "b.go", Line: 7}, Target: concrete, Tier: "syntactic"}, // silent: unreachable
		{Site: edges.Pos{Path: "c.go", Line: 1}, Target: concrete, Tier: "syntactic"}, // silent: not-loaded
	}}
	r := Grade(h, o)
	if r.Total != (TierCounts{Confirmed: 1, Contradicted: 1, Abstract: 1, Silent: 3}) {
		t.Fatalf("buckets: %+v", r.Total)
	}
	if r.SilentBy["no-targets"] != 1 || r.SilentBy["unreachable"] != 1 || r.SilentBy["not-loaded"] != 1 {
		t.Fatalf("silent reasons: %v", r.SilentBy)
	}
	if r.ByTier["syntactic"].Contradicted != 1 || r.ByTier["semantic"].Abstract != 1 {
		t.Fatalf("tier split: %+v", r.ByTier)
	}
	if *r.Precision != 0.5 {
		t.Fatalf("precision excludes abstract and silent: %v", *r.Precision)
	}
	if r.OraclePairs != 1 || r.RecallHits != 1 {
		t.Fatalf("recall counts the concrete pair once: %d/%d", r.RecallHits, r.OraclePairs)
	}
}

func TestExternalPairsStayOutOfRecall(t *testing.T) {
	site := edges.Pos{Path: "a.go", Line: 1}
	o := &edges.OracleExport{Files: []string{"a.go"}, Sites: []edges.Site{{Pos: site, Mode: "static", Targets: []edges.Target{{Pos: edges.Pos{Path: "/goroot/fmt/print.go", Line: 1}, External: true}}}}}
	r := Grade(&edges.HobbesExport{}, o)
	if r.OraclePairs != 0 || r.OracleExternal != 1 || r.Recall != nil {
		t.Fatalf("external pairs: %d in-repo, %d external, recall %v", r.OraclePairs, r.OracleExternal, r.Recall)
	}
}
