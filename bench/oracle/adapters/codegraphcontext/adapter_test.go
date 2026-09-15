// Package codegraphcontext holds the CodeGraphContext converter
// (adapter.py) and its hand-read fixture: the tool's own dump of the
// minigo fixture, read by hand against the conversion (ADR-101). The
// tests need python3 only; the dump stage needs the tool.
package codegraphcontext

import (
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/foreign"
	"github.com/majax7714/Hobbes/bench/oracle/internal/gorta"
	"github.com/majax7714/Hobbes/bench/oracle/internal/grade"
)

const fixtures = "../../../../pipeline/tests/fixtures"

// The hand truth: CodeGraphContext 0.6.13 on minigo (kuzudb backend)
// stored five CALLS rows, every one a true pair of the fixture — read
// from testdata/minigo.raw.json by hand — three INFERRED and two
// EXTRACTED by its own label. The conversion must reproduce exactly that.
var truth = map[string][2]string{
	"cmd/mini/main.go:12":               {"internal/policy/policy.go:26", "INFERRED"},
	"cmd/mini/main.go:16":               {"internal/policy/policy.go:36", "INFERRED"},
	"internal/policy/policy.go:28":      {"internal/policy/policy.go:21", "INFERRED"},
	"internal/policy/policy_test.go:7":  {"internal/policy/policy.go:26", "EXTRACTED"},
	"internal/policy/policy_test.go:13": {"internal/policy/policy.go:26", "EXTRACTED"},
}

func convert(t *testing.T) string {
	t.Helper()
	out := filepath.Join(t.TempDir(), "edges.json")
	cmd := exec.Command("python3", "adapter.py", "convert", "--raw", "testdata/minigo.raw.json", "--repo", "/repo/minigo", "--sha", "fixture", "--version", "0.6.13", "--out", out)
	if b, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("convert: %v\n%s", err, b)
	}
	return out
}

func convertCclang(t *testing.T) string {
	t.Helper()
	out := filepath.Join(t.TempDir(), "edges.json")
	cmd := exec.Command("python3", "adapter.py", "convert", "--raw", "testdata/cclang.raw.json", "--repo", "../../testdata/cclang", "--sha", "fixture", "--version", "0.6.13", "--out", out)
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
	if f.Tool != "codegraphcontext" || f.Version != "0.6.13" || f.Converter == "" {
		t.Fatalf("header: %+v", f)
	}
	if len(h.Edges) != len(truth) {
		t.Fatalf("want %d edges, got %d", len(truth), len(h.Edges))
	}
	for _, e := range h.Edges {
		want := truth[e.Site.Key()]
		if want[0] != e.Target.Key() || e.Tier != "codegraphcontext:"+want[1] {
			t.Errorf("%s -> %s (%s) is not the hand read %v", e.Site.Key(), e.Target.Key(), e.Tier, want)
		}
		if e.TargetKind != "function" && e.TargetKind != "method" {
			t.Errorf("kind lost: %+v", e)
		}
	}
}

// Graded against the fixture's RTA key the five convert to five
// confirmed, and the poison twin is refused in full.
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
	if r.Total != (grade.TierCounts{Confirmed: 5}) || r.RecallHits != 5 || r.OraclePairs != 5 {
		t.Fatalf("codegraphcontext on minigo: %+v recall %d/%d", r.Total, r.RecallHits, r.OraclePairs)
	}
	if c := grade.CheckPoison(h, o); !c.Passed || c.Confirmed != 0 || c.Refused != 5 {
		t.Fatalf("poison: %+v", c)
	}
}

// converter@3 (ADR-101's 2026-09-14 (later) amendment): a callee whose
// declared line begins with #define reads as kind macro, so the row to
// api.h:10 (CALL_SUM) is excluded and the row to lib.c:11 (lib_sum)
// grades alone.
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
// the #) and reads as macro, so its row is excluded; pick's node starts at
// its `template` line (7) and lands on the name's line (9); plain (11)
// stays where it is.
func TestCppGrainSpacedDefineAndSplitHead(t *testing.T) {
	out := filepath.Join(t.TempDir(), "edges.json")
	cmd := exec.Command("python3", "adapter.py", "convert", "--raw", "testdata/cppgrain.raw.json", "--repo", "../../testdata/cppgrain", "--sha", "fixture", "--version", "0.6.13", "--out", out)
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
