package grade

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
)

const fixtures = "../../../../pipeline/tests/fixtures"

func cell(t *testing.T, repo, module, graph string) *Report {
	t.Helper()
	h, err := export.FromFile("../../testdata/"+graph, module, "go")
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

// H-30 (D-O4, 2026-09-16): a line carrying an unresolved site — a
// dependent call in a template pattern the key holds as `dynamic` —
// cannot contradict, because judging the edge against the *other*
// sites' targets reads the key's silence as a verdict (RC-4). The
// dependent call's declaration is the one the source names; the row is
// silent, and out of the precision denominator.
func TestUnresolvedSiteOnTheLineSilencesTheEdge(t *testing.T) {
	line := edges.Pos{Path: "format.h", Line: 40}
	resolved := edges.Pos{Path: "format.h", Line: 10}
	dependent := edges.Pos{Path: "format.h", Line: 20}
	o := &edges.OracleExport{
		Oracle: "c-clang", Kind: "resolution", Files: []string{"format.h"},
		Sites: []edges.Site{
			{Pos: line, Mode: "static", Targets: []edges.Target{{Pos: resolved}}},
			{Pos: line, Mode: "dynamic"},
		},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{{Site: line, Target: dependent, Tier: "syntactic"}}}
	r := Grade(h, o)
	if r.Total != (TierCounts{Silent: 1}) || r.SilentBy["line-unresolved"] != 1 {
		t.Fatalf("the dependent call must be silent, not contradicted: %+v %v", r.Total, r.SilentBy)
	}
	if r.Precision != nil {
		t.Fatalf("a silent row is outside the precision denominator: %v", *r.Precision)
	}
	// ADR-124: the strict number counts it against the tool.
	if r.PrecisionStrict == nil || *r.PrecisionStrict != 0 || r.StrictGraded != 1 {
		t.Fatalf("strict precision must count the silenced row as contradicted: %v %d", r.PrecisionStrict, r.StrictGraded)
	}
}

// ADR-124: strict precision sits beside the standing number, counts the
// line-unresolved rows in its denominator only, prints on its own line,
// and is absent when no row was silenced that way.
func TestStrictPrecisionCountsLineUnresolvedRowsAsContradicted(t *testing.T) {
	line := edges.Pos{Path: "format.h", Line: 40}
	ok := edges.Pos{Path: "format.h", Line: 50}
	resolved := edges.Pos{Path: "format.h", Line: 10}
	o := &edges.OracleExport{
		Oracle: "c-clang", Kind: "resolution", Files: []string{"format.h"},
		Sites: []edges.Site{
			{Pos: line, Mode: "static", Targets: []edges.Target{{Pos: resolved}}},
			{Pos: line, Mode: "dynamic"},
			{Pos: ok, Mode: "static", Targets: []edges.Target{{Pos: resolved}}},
		},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: line, Target: edges.Pos{Path: "format.h", Line: 20}, Tier: "semantic"},
		{Site: ok, Target: resolved, Tier: "semantic"},
	}}
	r := Grade(h, o)
	if r.Precision == nil || *r.Precision != 1 {
		t.Fatalf("the standing number judges only the confirmed row: %v", r.Precision)
	}
	if r.PrecisionStrict == nil || *r.PrecisionStrict != 0.5 || r.StrictGraded != 2 {
		t.Fatalf("strict must be 1/2: %v %d", r.PrecisionStrict, r.StrictGraded)
	}
	var b strings.Builder
	Print(&b, r)
	if !strings.Contains(b.String(), "precision-against-oracle 100.0% (1/1)\nprecision-strict 50.0% (1/2): the 1 line-unresolved rows counted as contradicted") {
		t.Fatalf("the strict line must print under the standing one:\n%s", b.String())
	}

	clean := Grade(&edges.HobbesExport{Edges: h.Edges[1:]}, o)
	if clean.PrecisionStrict != nil {
		t.Fatalf("no line-unresolved row, no strict number: %v", *clean.PrecisionStrict)
	}
	b.Reset()
	Print(&b, clean)
	if strings.Contains(b.String(), "precision-strict") {
		t.Fatalf("no strict line without line-unresolved rows:\n%s", b.String())
	}
}

// The rule silences only what the key did not resolve: an edge matching
// the resolved neighbour on the same line still confirms.
func TestResolvedNeighbourOnAnUnresolvedLineStillConfirms(t *testing.T) {
	line := edges.Pos{Path: "format.h", Line: 40}
	resolved := edges.Pos{Path: "format.h", Line: 10}
	o := &edges.OracleExport{
		Oracle: "c-clang", Kind: "resolution", Files: []string{"format.h"},
		Sites: []edges.Site{
			{Pos: line, Mode: "static", Targets: []edges.Target{{Pos: resolved}}},
			{Pos: line, Mode: "dynamic"},
		},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{{Site: line, Target: resolved, Tier: "semantic"}}}
	r := Grade(h, o)
	if r.Total != (TierCounts{Confirmed: 1}) {
		t.Fatalf("a resolved neighbour still confirms: %+v", r.Total)
	}
}

// A line where *every* site is targetless keeps its own reason: the new
// rule is about a mixed line, and no-targets must not be renamed by it.
func TestAllTargetlessLineKeepsNoTargets(t *testing.T) {
	line := edges.Pos{Path: "format.h", Line: 40}
	o := &edges.OracleExport{
		Oracle: "c-clang", Kind: "resolution", Files: []string{"format.h"},
		Sites: []edges.Site{{Pos: line, Mode: "dynamic"}, {Pos: line, Mode: "dynamic"}},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{{Site: line, Target: edges.Pos{Path: "format.h", Line: 10}}}}
	r := Grade(h, o)
	if r.Total != (TierCounts{Silent: 1}) || r.SilentBy["no-targets"] != 1 || r.SilentBy["line-unresolved"] != 0 {
		t.Fatalf("an all-targetless line stays no-targets: %+v %v", r.Total, r.SilentBy)
	}
}

// The fix must not silence real disagreement: where every site on the
// line resolved, an edge matching none of them still contradicts (this
// is also H-31's shape — a call the key holds nowhere at all leaves the
// line fully resolved, so the rule does not reach it).
func TestFullyResolvedLineStillContradicts(t *testing.T) {
	line := edges.Pos{Path: "format.h", Line: 40}
	o := &edges.OracleExport{
		Oracle: "c-clang", Kind: "resolution", Files: []string{"format.h"},
		Sites: []edges.Site{
			{Pos: line, Mode: "static", Targets: []edges.Target{{Pos: edges.Pos{Path: "format.h", Line: 10}}}},
			{Pos: line, Mode: "static", Targets: []edges.Target{{Pos: edges.Pos{Path: "format.h", Line: 11}}}},
		},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{{Site: line, Target: edges.Pos{Path: "format.h", Line: 99}}}}
	r := Grade(h, o)
	if r.Total != (TierCounts{Contradicted: 1}) || r.Precision == nil || *r.Precision != 0 {
		t.Fatalf("a fully resolved line still contradicts: %+v precision %v", r.Total, r.Precision)
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

// The TypeScript oracle on the minits fixture (hand truth: four calls
// to util.normalize — from the Nest controller, server.js, and two
// node:test cases; decorators and vitest globals unresolved without
// node_modules, so oracle-silent). Plus the three element-access shapes
// of src/lookup.ts (A-4 / H-17): the literal key `table["norm"](s)`
// resolves to util.normalize — an in-repo pair Hobbes draws no edge for
// (lane A does not count `obj[key]()` as a site: C-62), so recall is
// 4/5 with one static→function miss; `xs[Symbol.iterator]()` resolves
// to lib.es2015's Array member (external); the computed `table[k](s)`
// is oracle-silent as computed-key. Since 2026-09-09 (ADR-104) the
// fixture's src/union.ts adds three in-repo pairs: `label -> Base.tag`
// (one inherited declaration; drawn and confirmed) and two member calls
// on `Alpha | Beta` where both members override `render` — the oracle
// names Alpha.render, tsc's first-member pick, and Hobbes abstains by
// design (C-97), so those two are static→method misses, not edges.
// Recall is therefore 5/8. The stored graph is a contained lane-B
// ingest of the fixture (0.1.4-beta). Needs node; skipped without it.
func TestMinitsTSAllConfirmed(t *testing.T) {
	if _, err := exec.LookPath("node"); err != nil {
		t.Skip("node not on PATH")
	}
	out := filepath.Join(t.TempDir(), "oracle.json")
	cmd := exec.Command("node", "../../ts/tsc-oracle.mjs", "--repo", fixtures+"/minits", "--zone", ".", "--out", out)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("tsc-oracle: %v\n%s", err, b)
	}
	raw, err := os.ReadFile(out)
	if err != nil {
		t.Fatal(err)
	}
	var o edges.OracleExport
	if err := json.Unmarshal(raw, &o); err != nil {
		t.Fatal(err)
	}
	h, err := export.FromFile("../../testdata/minits.graph.json", ".", "ts")
	if err != nil {
		t.Fatal(err)
	}
	r := Grade(h, &o)
	if r.Total != (TierCounts{Confirmed: 5}) || r.RecallHits != 5 || r.OraclePairs != 8 || r.MissBy["static→function"] != 1 || r.MissBy["static→method"] != 2 {
		t.Fatalf("minits: %+v recall %d/%d misses %v", r.Total, r.RecallHits, r.OraclePairs, r.MissBy)
	}
	shapes := map[int]string{}
	for _, s := range o.Sites {
		if s.Pos.Path == "src/lookup.ts" {
			shapes[s.Pos.Line] = fmt.Sprintf("%s/%d", s.Mode, len(s.Targets))
		}
	}
	if shapes[12] != "static/1" || shapes[16] != "static/1" || shapes[20] != "dynamic/0" {
		t.Fatalf("element-access shapes (line → mode/targets): %v", shapes)
	}
	if o.Kind != "resolution" {
		t.Fatalf("kind: %s", o.Kind)
	}
	silent := 0
	for _, s := range o.Sites {
		if len(s.Targets) == 0 {
			silent++
		}
	}
	if silent < 4 {
		t.Fatalf("decorators and vitest globals should be unresolved without node_modules; %d silent sites", silent)
	}
}

// The report prints the no-roots state as its own line and the JSON
// says [] for an empty misses list, never null (A-1, A-3).
func TestNoRootsPrintsAsItsOwnStateAndEmptyIsBrackets(t *testing.T) {
	h := &edges.HobbesExport{}
	o := &edges.OracleExport{Oracle: "go-rta", Kind: "reachability", Module: ".", Roots: []string{}, State: edges.StateNoRoots}
	r := Grade(h, o)
	var buf bytes.Buffer
	Print(&buf, r)
	if !strings.Contains(buf.String(), "NOT GRADED — no roots exist") {
		t.Fatalf("report:\n%s", buf.String())
	}
	raw, _ := json.Marshal(r)
	// precision/recall are pointers and null when undefined; the lists
	// are never null.
	for _, k := range []string{`"misses":[]`, `"rows":[]`, `"tags":[]`, `"root_names":[]`} {
		if !strings.Contains(string(raw), k) {
			t.Fatalf("json lacks %s: %s", k, raw)
		}
	}
	if false {
		t.Fatalf("json: %s", raw)
	}
}

// The collapsed recall line (Max, 2026-09-10; H-22's identity): one pair
// per (site line, target file, target name as the key spells it). A tsc
// key lists both overload signatures of `attr` as targets at one site —
// two per-signature pairs, one collapsed; a same-named method of another
// class (`A.run` / `B.run`, checker-qualified) stays two pairs; a hit is
// by the target at the confirmed row's exact position, and external
// targets never enter. Trace oracles print no such line.
func TestCollapsedRecallRemovesTheOverloadGrainOnly(t *testing.T) {
	site1 := edges.Pos{Path: "a.ts", Line: 10}
	site2 := edges.Pos{Path: "a.ts", Line: 11}
	o := &edges.OracleExport{
		Oracle: "tsc 5.9.3", Kind: "resolution", Files: []string{"a.ts", "b.ts"},
		Sites: []edges.Site{
			{Pos: site1, Mode: "static", Targets: []edges.Target{
				{Pos: edges.Pos{Path: "b.ts", Line: 20}, Name: `"/r/b".attr`, Kind: "function"},
				{Pos: edges.Pos{Path: "b.ts", Line: 24}, Name: `"/r/b".attr`, Kind: "function"},
				{Pos: edges.Pos{Path: "/r/node_modules/x/index.d.ts", Line: 1}, Name: "x", External: true},
			}},
			{Pos: site2, Mode: "static", Targets: []edges.Target{
				{Pos: edges.Pos{Path: "b.ts", Line: 40}, Name: "A.run", Kind: "method"},
				{Pos: edges.Pos{Path: "b.ts", Line: 50}, Name: "B.run", Kind: "method"},
			}},
		},
	}
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: site1, Target: edges.Pos{Path: "b.ts", Line: 20}, Tier: "semantic"}, // one signature of attr
		{Site: site2, Target: edges.Pos{Path: "b.ts", Line: 40}, Tier: "semantic"}, // A.run
	}}
	r := Grade(h, o)
	if r.OraclePairs != 4 || r.RecallHits != 2 {
		t.Fatalf("per-signature recall: %d/%d", r.RecallHits, r.OraclePairs)
	}
	if r.CollapsedPairs != 3 || r.CollapsedHits != 2 || r.RecallCollapsed == nil || *r.RecallCollapsed < 0.666 || *r.RecallCollapsed > 0.667 {
		t.Fatalf("collapsed recall: %d/%d %v", r.CollapsedHits, r.CollapsedPairs, r.RecallCollapsed)
	}
	var buf bytes.Buffer
	Print(&buf, r)
	out := buf.String()
	for _, want := range []string{"recall 50.0% (2/4 in-repo oracle pairs)", "recall-collapsed 66.7% (2/3 pairs at site-line × target-file × target-name grain"} {
		if !strings.Contains(out, want) {
			t.Errorf("report lacks %q:\n%s", want, out)
		}
	}
	raw, _ := json.Marshal(r)
	for _, k := range []string{`"collapsed_pairs":3`, `"collapsed_hits":2`, `"recall_collapsed":0.66`} {
		if !strings.Contains(string(raw), k) {
			t.Errorf("json lacks %s", k)
		}
	}
	// A trace oracle has no signatures to collapse: nothing computed, nothing printed.
	tr := Grade(h, &edges.OracleExport{Oracle: "py-trace", Kind: "trace", Files: []string{"a.ts"}, Sites: o.Sites})
	buf.Reset()
	Print(&buf, tr)
	if tr.RecallCollapsed != nil || strings.Contains(buf.String(), "recall-collapsed") {
		t.Fatalf("trace oracle must not print a collapsed line:\n%s", buf.String())
	}
}
