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
