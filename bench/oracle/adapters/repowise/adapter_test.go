// Package repowise holds the repowise converter (adapter.py) and its
// hand-read fixture: the tool's own wiki.db rows for the minigo fixture,
// read by hand against the conversion (ADR-101). python3 only.
package repowise

import (
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/foreign"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
	"github.com/majax7714/Hobbes/bench/oracle/internal/grade"
)

const fixtures = "../../../../pipeline/tests/fixtures"

// The hand truth: repowise 0.49.0 (`init --no-prose -y`) on minigo stored
// five `calls` rows. Four are true pairs of the fixture. The fifth,
// `Resolve` at policy.go:32 → the type `Decision` (policy.go:10), is the
// conversion `Decision(DefaultDecision)` drawn as a call — the tool's
// edge, carried as it stands; the converter's job is fidelity, and the
// oracle judges it (no call exists on that line, so RTA is silent there
// — the O4 conversion shape). `rule.Matches(cmd)` at policy.go:28 is
// not in the tool's graph.
var truth = map[string][3]string{
	"cmd/mini/main.go:12":               {"internal/policy/policy.go:26", "package_alias", "function"},
	"cmd/mini/main.go:16":               {"internal/policy/policy.go:36", "package_alias", "function"},
	"internal/policy/policy.go:32":      {"internal/policy/policy.go:10", "same_file", "type_alias"},
	"internal/policy/policy_test.go:7":  {"internal/policy/policy.go:26", "same_package", "function"},
	"internal/policy/policy_test.go:13": {"internal/policy/policy.go:26", "same_package", "function"},
}

func convert(t *testing.T) string {
	t.Helper()
	out := filepath.Join(t.TempDir(), "edges.json")
	cmd := exec.Command("python3", "adapter.py", "convert", "--raw", "testdata/minigo.raw.json", "--sha", "fixture", "--version", "0.49.0", "--out", out)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("convert: %v\n%s", err, b)
	}
	return out
}

func convertCclang(t *testing.T) string {
	t.Helper()
	out := filepath.Join(t.TempDir(), "edges.json")
	cmd := exec.Command("python3", "adapter.py", "convert", "--raw", "testdata/cclang.raw.json", "--repo", "../../testdata/cclang", "--sha", "fixture", "--version", "0.49.0", "--out", out)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("convert: %v\n%s", err, b)
	}
	return out
}

func TestConversionMatchesTheHandRead(t *testing.T) {
	h, f, err := foreign.FromFile(convert(t), ".", "go")
	if err != nil {
		t.Fatal(err)
	}
	if f.Tool != "repowise" || f.Version != "0.49.0" || f.Converter == "" {
		t.Fatalf("header: %+v", f)
	}
	if len(h.Edges) != len(truth) {
		t.Fatalf("want %d edges, got %d", len(truth), len(h.Edges))
	}
	for _, e := range h.Edges {
		want := truth[e.Site.Key()]
		if want[0] != e.Target.Key() || e.Tier != "repowise:"+want[1] || e.TargetKind != want[2] {
			t.Errorf("%s -> %s (%s, %s) is not the hand read %v", e.Site.Key(), e.Target.Key(), e.Tier, e.TargetKind, want)
		}
	}
}

// Against the fixture's RTA key: four confirmed, the conversion edge
// oracle-silent (no call on that line), nothing contradicted; the
// poison twin refused wherever the oracle speaks.
func TestGradesAgainstMinigo(t *testing.T) {
	h, _, err := foreign.FromFile(convert(t), ".", "go")
	if err != nil {
		t.Fatal(err)
	}
	o, err := gorta.Run(gorta.Options{Repo: fixtures + "/minigo", Module: "."})
	if err != nil {
		t.Skip("minigo oracle:", err)
	}
	r := grade.Grade(h, o)
	if r.Total != (grade.TierCounts{Confirmed: 4, Silent: 1}) || r.RecallHits != 4 || r.OraclePairs != 5 {
		t.Fatalf("repowise on minigo: %+v recall %d/%d silent %v", r.Total, r.RecallHits, r.OraclePairs, r.SilentBy)
	}
	if c := grade.CheckPoison(h, o); !c.Passed || c.Confirmed != 0 || c.Refused != 4 || c.Unjudged != 1 {
		t.Fatalf("poison: %+v", c)
	}
}

// converter@3 (ADR-101's 2026-09-14 (later) amendment): the tool stores
// CALL_SUM (api.h:10, a #define) as kind function — the finding — but
// the declared line reads as macro, so that row is excluded and the row
// to lib_sum (lib.c:11) grades alone.
func TestCclangMacroRowIsExcluded(t *testing.T) {
	out := convertCclang(t)
	h, f, err := foreign.FromFile(out, ".", "c")
	if err != nil {
		t.Fatal(err)
	}
	kinds := map[string]string{}
	for _, e := range f.Edges {
		kinds[e.Site] = e.Kind
	}
	if kinds["main.c:18"] != "macro" {
		t.Errorf("main.c:18 kind = %q, want macro", kinds["main.c:18"])
	}
	if kinds["main.c:19"] != "function" {
		t.Errorf("main.c:19 kind = %q, want function", kinds["main.c:19"])
	}
	if len(h.Edges) != 1 || h.Edges[0].Site.Key() != "main.c:19" || h.Edges[0].Target.Key() != "lib.c:11" {
		t.Fatalf("graded edges: %+v", h.Edges)
	}
	if h.Excluded["macro"] != 1 {
		t.Fatalf("Excluded[macro] = %d, want 1", h.Excluded["macro"])
	}
}

// converter@4 (ADR-101's 2026-09-15 amendment), read by hand from
// testdata/cppgrain/grain.h: TWICE is `#  define`d at line 4 (spaces after
// the #) and reads as macro, so its row is excluded; pick's start_line is
// its return-type line (8), as the tool stored ToString in args.hxx, and
// lands on the name's line (9); plain (11) stays where it is.
func TestCppGrainSpacedDefineAndSplitHead(t *testing.T) {
	out := filepath.Join(t.TempDir(), "edges.json")
	cmd := exec.Command("python3", "adapter.py", "convert", "--raw", "testdata/cppgrain.raw.json", "--repo", "../../testdata/cppgrain", "--sha", "fixture", "--version", "0.49.0", "--out", out)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("convert: %v\n%s", err, b)
	}
	h, _, err := foreign.FromFile(out, ".", "cpp")
	if err != nil {
		t.Fatal(err)
	}
	got := map[string]string{}
	for _, e := range h.Edges {
		got[e.Target.Key()] = e.Site.Key()
	}
	want := map[string]string{"grain.h:11": "grain.h:14", "grain.h:9": "grain.h:17"}
	if len(got) != len(want) {
		t.Fatalf("graded edges: %+v", h.Edges)
	}
	for callee, site := range want {
		if got[callee] != site {
			t.Errorf("callee %s: site %q, want %q", callee, got[callee], site)
		}
	}
	if h.Excluded["macro"] != 1 {
		t.Fatalf("Excluded[macro] = %d, want 1", h.Excluded["macro"])
	}
}
