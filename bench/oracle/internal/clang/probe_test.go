package clang

import (
	"os"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// TestProbeFixture is ADR-110's review probe: clang 18.1.3's own dump of
// testdata/cclang-probe/probe.c (compiled with /p as both dir and repo),
// asserting the four defects review found in unit A are fixed:
//
//  1. clang's pseudo-buffers ("<scratch space>") are never files and a
//     chosen position that lies in one takes the expansion instead —
//     probe.c:13's token-pasted callee (ARGCALL(PASTE(do_, one)())).
//  2. a callee that is itself a call (probe.c:12's get_fn()(2)) is two
//     sites: the inner static call and the outer dynamic one, sharing
//     one (site, spelling) position.
//  3. a static function defined outside the repo (probe.c:10's
//     bswap_16, which expands to the header's `static inline`
//     __bswap_16) is external, not link-ambiguous.
//  4. Files holds only probe.c: neither the header nor a pseudo-buffer
//     ever entered it.
func TestProbeFixture(t *testing.T) {
	f, err := os.Open("../../testdata/cclang-probe/probe.json")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	shard, err := ReadDump(f, "/p", "/p")
	if err != nil {
		t.Fatalf("ReadDump: %v", err)
	}

	out := Merge([]*Shard{shard}, "")

	if got, want := out.Files, []string{"probe.c"}; !equalStrings(got, want) {
		t.Fatalf("files: %v, want %v", got, want)
	}

	wantCoverage := map[string]int{
		"units": 1, "units_failed": 0,
		"sites_static": 1, "sites_macro": 2, "sites_dynamic": 1,
		"sites_external": 1, "sites_link_ambiguous": 0, "sites_undefined": 0, "sites_tu_split": 0,
	}
	for k, v := range wantCoverage {
		if out.Coverage[k] != v {
			t.Errorf("coverage[%s] = %d, want %d (full: %v)", k, out.Coverage[k], v, out.Coverage)
		}
	}

	sitesAtLine := func(line int) []edges.Site {
		var got []edges.Site
		for _, s := range out.Sites {
			if s.Pos.Path == "probe.c" && s.Pos.Line == line {
				got = append(got, s)
			}
		}
		return got
	}

	// probe.c:10 — bswap_16 expands to __bswap_16, a system header's
	// `static inline`: external, mode macro (defect 3, and defect 1's
	// pseudo rule does not fire here — the spelling is a real header
	// location, not a pseudo-buffer).
	line10 := sitesAtLine(10)
	if len(line10) != 1 {
		t.Fatalf("probe.c:10: want 1 site, got %+v", line10)
	}
	if s := line10[0]; s.Mode != "macro" || len(s.Targets) != 1 || !s.Targets[0].External || s.Targets[0].Name != "__bswap_16" {
		t.Errorf("probe.c:10: %+v", s)
	}

	// probe.c:11 — CALLP(one) pastes to do_one() in "<scratch space>";
	// the chosen (non-arg-expansion) position is already the expansion,
	// unaffected by the pseudo rule, and resolves to do_one's definition.
	line11 := sitesAtLine(11)
	if len(line11) != 1 {
		t.Fatalf("probe.c:11: want 1 site, got %+v", line11)
	}
	if s := line11[0]; s.Mode != "macro" || len(s.Targets) != 1 || s.Targets[0].Pos != (edges.Pos{Path: "probe.c", Line: 5}) {
		t.Errorf("probe.c:11: %+v", s)
	}

	// probe.c:12 — get_fn()(2): two sites sharing one position (defect
	// 2), the inner static call to get_fn's definition and the outer
	// dynamic call through its result.
	line12 := sitesAtLine(12)
	if len(line12) != 2 {
		t.Fatalf("probe.c:12: want 2 sites, got %+v", line12)
	}
	var gotStatic, gotDynamic bool
	for _, s := range line12 {
		switch s.Mode {
		case "static":
			gotStatic = true
			if len(s.Targets) != 1 || s.Targets[0].Pos != (edges.Pos{Path: "probe.c", Line: 8}) || s.Targets[0].Name != "get_fn" {
				t.Errorf("probe.c:12 static: %+v", s)
			}
		case "dynamic":
			gotDynamic = true
			if len(s.Targets) != 0 {
				t.Errorf("probe.c:12 dynamic: %+v", s)
			}
		default:
			t.Errorf("probe.c:12 unexpected mode: %+v", s)
		}
	}
	if !gotStatic || !gotDynamic {
		t.Errorf("probe.c:12: want one static and one dynamic site, got %+v", line12)
	}

	// probe.c:13 — ARGCALL(PASTE(do_, one)()): the argument-expansion
	// spelling lies in "<scratch space>" (a pasted token with no real
	// location), so the pseudo rule (defect 1) redirects to the
	// expansion, mode macro, resolving as line 11 does.
	line13 := sitesAtLine(13)
	if len(line13) != 1 {
		t.Fatalf("probe.c:13: want 1 site, got %+v", line13)
	}
	if s := line13[0]; s.Mode != "macro" || len(s.Targets) != 1 || s.Targets[0].Pos != (edges.Pos{Path: "probe.c", Line: 5}) {
		t.Errorf("probe.c:13: %+v", s)
	}
}
