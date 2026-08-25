package grade

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/rustmir"
)

// The Rust MIR oracle on the minirust fixture (O7's self-test). Hand
// truth across lib, bin, the bin's #[cfg(test)] module and the
// integration test: compute (from the lib's own macro body, from main
// across the crate boundary, from the integration test), greet,
// from_sub, extra_fn, double (test only), Counter::new, Counter::incr —
// nine in-repo pairs; every std/core call external; the test harness's
// generated calls dropped and counted. Needs the pinned nightly with
// rustc-dev and a built driver; skipped without.
func TestMinirustMIR(t *testing.T) {
	if _, err := exec.LookPath("cargo"); err != nil {
		t.Skip("cargo not on PATH")
	}
	if err := exec.Command("rustc", "+nightly", "--version").Run(); err != nil {
		t.Skip("no nightly toolchain")
	}
	driver, _ := filepath.Abs("../../rust/target/release/mir-oracle")
	if _, err := os.Stat(driver); err != nil {
		t.Skip("mir-oracle driver not built: cd bench/oracle/rust && cargo +nightly build --release")
	}
	repo, _ := filepath.Abs(fixtures + "/minirust")
	o, err := rustmir.Run(rustmir.Options{Repo: repo, Module: ".", Driver: driver, Out: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if o.Kind != "resolution" || len(o.Roots) != 5 || o.Excluded["generated"] == 0 {
		t.Fatalf("header: kind %s roots %v excluded %v", o.Kind, o.Roots, o.Excluded)
	}
	pairs := map[string]bool{}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if !tg.External {
				pairs[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
		}
	}
	want := []string{
		"src/lib.rs:14 -> src/lib.rs:9",
		"src/main.rs:10 -> src/helpers.rs:1",
		"src/main.rs:11 -> src/sub/mod.rs:1",
		"src/main.rs:12 -> src/deep/extra.rs:1",
		"src/main.rs:13 -> src/lib.rs:9",
		"src/main.rs:26 -> src/main.rs:16",
		"tests/integration.rs:5 -> src/lib.rs:9",
		"tests/integration.rs:6 -> src/lib.rs:22",
		"tests/integration.rs:7 -> src/lib.rs:26",
	}
	for _, w := range want {
		if !pairs[w] {
			t.Errorf("missing %s", w)
		}
		delete(pairs, w)
	}
	for extra := range pairs {
		t.Errorf("unexpected in-repo pair %s", extra)
	}
	h, err := export.FromFile("../../testdata/minirust.graph.json", ".", "rust")
	if err != nil {
		t.Fatal(err)
	}
	r := Grade(h, o)
	if r.Total != (TierCounts{Confirmed: 9}) || r.RecallHits != 9 || r.OraclePairs != 9 {
		t.Fatalf("minirust: %+v recall %d/%d misses %v", r.Total, r.RecallHits, r.OraclePairs, r.MissBy)
	}
}
