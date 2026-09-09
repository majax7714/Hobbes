package foreign

import (
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
	"github.com/majax7714/Hobbes/bench/oracle/internal/grade"
)

const fixtures = "../../../../pipeline/tests/fixtures"

// The hand-read fixture: minigo's five true call edges as a converter
// would write them, plus one duplicate and two rows in files outside
// the language. The conversion must equal the hand truth exactly —
// this is the check every adapter's fixture repeats for its own tool.
var minigoTruth = map[string]string{
	"cmd/mini/main.go:12":               "internal/policy/policy.go:26",
	"cmd/mini/main.go:16":               "internal/policy/policy.go:36",
	"internal/policy/policy.go:28":      "internal/policy/policy.go:21",
	"internal/policy/policy_test.go:7":  "internal/policy/policy.go:26",
	"internal/policy/policy_test.go:13": "internal/policy/policy.go:26",
}

func TestMinigoFixtureConvertsToTheHandTruth(t *testing.T) {
	h, f, err := FromFile("../../testdata/foreign/minigo.edges.json", ".", "go")
	if err != nil {
		t.Fatal(err)
	}
	if f.Tool != "handread" || f.Converter != "hand@2026-09-09" {
		t.Fatalf("file header lost: %+v", f)
	}
	if len(h.Edges) != 5 {
		t.Fatalf("want 5 graded edges, got %d (%+v)", len(h.Edges), h.Excluded)
	}
	for _, e := range h.Edges {
		if minigoTruth[e.Site.Key()] != e.Target.Key() {
			t.Errorf("%s -> %s not in the hand truth", e.Site.Key(), e.Target.Key())
		}
		if len(e.Lanes) != 1 || e.Lanes[0] != "handread" || !strings.HasPrefix(e.TargetID, "handread:") {
			t.Errorf("provenance lost: %+v", e)
		}
	}
	if h.Excluded["duplicate"] != 1 || h.Excluded["other-language"] != 2 {
		t.Errorf("excluded counts: %v", h.Excluded)
	}
	// The tool's label is the tier, so the report splits by its ladder.
	tiers := map[string]int{}
	for _, e := range h.Edges {
		tiers[e.Tier]++
	}
	if tiers["handread"] != 4 || tiers["handread:high"] != 1 {
		t.Errorf("tier by label: %v", tiers)
	}
}

// The converted graph grades exactly as Hobbes' own fixture graph does:
// five confirmed against RTA, and the poison check refuses every seeded
// wrong edge. Skips where the fixture module cannot be loaded.
func TestMinigoFixtureGradesAndPoisonRefuses(t *testing.T) {
	h, _, err := FromFile("../../testdata/foreign/minigo.edges.json", ".", "go")
	if err != nil {
		t.Fatal(err)
	}
	o, err := gorta.Run(gorta.Options{Repo: fixtures + "/minigo", Module: "."})
	if err != nil {
		t.Skip("minigo oracle:", err)
	}
	r := grade.Grade(h, o)
	if r.Total != (grade.TierCounts{Confirmed: 5}) || r.RecallHits != 5 {
		t.Fatalf("foreign minigo: %+v recall %d/%d", r.Total, r.RecallHits, r.OraclePairs)
	}
	if r.ByTier["handread"].Confirmed != 4 || r.ByTier["handread:high"].Confirmed != 1 {
		t.Fatalf("per-label split: %+v", r.ByTier)
	}
	c := grade.CheckPoison(h, o)
	if c.Seeded != 5 || c.Confirmed != 0 || !c.Passed || c.Refused != 5 {
		t.Fatalf("poison on a foreign graph: %+v", c)
	}
	// And a wrong edge the tool might draw is contradicted, not confirmed.
	wrong := *h
	wrong.Edges = append([]edges.HobbesEdge{}, h.Edges...)
	wrong.Edges[0].Target = edges.Pos{Path: "internal/policy/policy.go", Line: 36}
	r = grade.Grade(&wrong, o)
	if r.Total.Contradicted != 1 || r.Total.Confirmed != 4 {
		t.Fatalf("a wrong foreign edge must be contradicted: %+v", r.Total)
	}
}

// A malformed position is a converter defect and refuses the whole
// file; it must never grade as a silently smaller graph (C-94).
func TestMalformedPositionRefusesTheFile(t *testing.T) {
	f := &File{Tool: "t", Edges: []Edge{
		{Site: "a.go:1", Callee: "b.go:2"},
		{Site: "a.go", Callee: "b.go:2"},
		{Site: "a.go:0", Callee: "b.go:2"},
		{Site: "/abs/a.go:1", Callee: "b.go:2"},
		{Site: "a.go:1", Callee: "../b.go:2"},
	}}
	_, err := Convert(f, ".", "go")
	if err == nil || !strings.Contains(err.Error(), "C-94") {
		t.Fatalf("want a converter-defect error, got %v", err)
	}
	if _, err := Convert(&File{Edges: nil}, ".", "go"); err == nil {
		t.Fatal("a file naming no tool must be refused")
	}
	if _, err := Convert(&File{Tool: "t"}, ".", "cobol"); err == nil {
		t.Fatal("an unknown language must be refused")
	}
}

// Cell membership is the lane's own predicate: sites under the module,
// nested modules excluded, targets anywhere; Windows separators and a
// leading ./ normalise.
func TestCellMembershipAndNormalisation(t *testing.T) {
	f := &File{Tool: "t", Edges: []Edge{
		{Site: "./app/main.go:3", Callee: "lib\\lib.go:9"},
		{Site: "lib/lib.go:4", Callee: "lib/lib.go:9"},
		{Site: "app/nested/x.go:1", Callee: "lib/lib.go:9"},
	}}
	h, err := Convert(f, "app", "go", "app/nested")
	if err != nil {
		t.Fatal(err)
	}
	if len(h.Edges) != 1 || h.Edges[0].Site.Key() != "app/main.go:3" || h.Edges[0].Target.Key() != "lib/lib.go:9" {
		t.Fatalf("edges: %+v", h.Edges)
	}
	if h.Excluded["outside-cell"] != 2 {
		t.Fatalf("excluded: %v", h.Excluded)
	}
}

// The two Hobbes-metadata tolerances fire only on a supplied kind: a
// callee kind of `var` makes a call through a function value abstract
// (D-O4), and `macro` drops the edge before grading; with no kind the
// same edge is contradicted, which the cell record must say (C-95).
func TestKindDrivesTheMetadataTolerances(t *testing.T) {
	o := &edges.OracleExport{Kind: "reachability", Files: []string{"a.go"}, Sites: []edges.Site{{
		Pos: edges.Pos{Path: "a.go", Line: 5}, Mode: "dynamic",
		Targets: []edges.Target{{Pos: edges.Pos{Path: "a.go", Line: 20}, Name: "held"}},
	}}}
	conv := func(kind string) *edges.HobbesExport {
		h, err := Convert(&File{Tool: "t", Edges: []Edge{{Site: "a.go:5", Callee: "a.go:2", Kind: kind}}}, ".", "go")
		if err != nil {
			t.Fatal(err)
		}
		return h
	}
	if r := grade.Grade(conv(""), o); r.Total.Contradicted != 1 {
		t.Fatalf("no kind: want contradicted, got %+v", r.Total)
	}
	if r := grade.Grade(conv("var"), o); r.Total.Abstract != 1 {
		t.Fatalf("kind var: want abstract, got %+v", r.Total)
	}
	if h := conv("macro"); len(h.Edges) != 0 || h.Excluded["macro"] != 1 {
		t.Fatalf("kind macro: want excluded, got %+v %v", h.Edges, h.Excluded)
	}
}
