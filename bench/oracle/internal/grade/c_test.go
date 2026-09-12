package grade

import (
	"bytes"
	"os"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/clang"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// cclangOracle reads the committed cclang dumps (ADR-110's fixture) and
// merges them, exactly as unit B's cell will, minus the container: no
// clang runs here, the dumps are committed test data.
func cclangOracle(t *testing.T) *edges.OracleExport {
	t.Helper()
	names := []string{"0-main.c.json", "1-lib.c.json", "2-tool.c.json", "3-lib.c.json"}
	var shards []*clang.Shard
	for _, n := range names {
		f, err := os.Open("../../testdata/cclang-ast/" + n)
		if err != nil {
			t.Fatal(err)
		}
		s, err := clang.ReadDump(f, "/fx", "/fx")
		f.Close()
		if err != nil {
			t.Fatalf("%s: %v", n, err)
		}
		shards = append(shards, s)
	}
	o := clang.Merge(shards, "")
	o.Oracle = "clang 18.1.3"
	o.Roots = []string{"cclang-ast"}
	return o
}

// TestCGrade grades a hand-built HobbesExport against the merged cclang
// fixture oracle: a confirmed edge, a contradicted one, a silent
// not-loaded row (orphan.c, which no compile entry touches), a silent
// no-targets row (lib.c:23's undefined `missing`), the external pair
// (__builtin_abs) staying outside the recall denominator, the
// coverage: line, and the poison check passing with nothing falsely
// confirmed.
func TestCGrade(t *testing.T) {
	o := cclangOracle(t)

	h := &edges.HobbesExport{
		SHA: "deadbeef", Module: "",
		Edges: []edges.HobbesEdge{
			// confirmed: main.c:20 col-agnostic sq() -> api.h:15
			{Site: edges.Pos{Path: "main.c", Line: 20}, Target: edges.Pos{Path: "api.h", Line: 15}, TargetID: "sq", Caller: "main", Tier: "semantic", Lanes: []string{"lane-a"}},
			// contradicted: main.c:21's lib_mul() call, wrong target
			{Site: edges.Pos{Path: "main.c", Line: 21}, Target: edges.Pos{Path: "api.h", Line: 16}, TargetID: "wrong", Caller: "main", Tier: "semantic", Lanes: []string{"lane-a"}},
			// silent, not-loaded: orphan.c is in no compile entry
			{Site: edges.Pos{Path: "orphan.c", Line: 5}, Target: edges.Pos{Path: "lib.c", Line: 11}, TargetID: "lib_sum", Caller: "orphan", Tier: "semantic", Lanes: []string{"lane-a"}},
			// silent, no-targets: lib.c:23's missing() is undefined
			{Site: edges.Pos{Path: "lib.c", Line: 23}, Target: edges.Pos{Path: "api.h", Line: 7}, TargetID: "missing", Caller: "lib_run", Tier: "semantic", Lanes: []string{"lane-a"}},
		},
	}

	r := Grade(h, o)
	if r.Total.Confirmed != 1 {
		t.Errorf("confirmed: %+v", r.Total)
	}
	if r.Total.Contradicted != 1 {
		t.Errorf("contradicted: %+v", r.Total)
	}
	if r.Total.Silent != 2 || r.SilentBy["not-loaded"] != 1 || r.SilentBy["no-targets"] != 1 {
		t.Errorf("silent: %+v silentBy %v", r.Total, r.SilentBy)
	}

	// __builtin_abs is external: it must sit outside the in-repo recall
	// denominator, counted on its own line (D-O3).
	if r.OracleExternal != 1 {
		t.Errorf("external pairs: %d, want 1", r.OracleExternal)
	}
	if r.OraclePairs != 17 {
		t.Errorf("in-repo oracle pairs: %d, want 17 (ADR-110's fixture truth)", r.OraclePairs)
	}

	if len(r.Coverage) == 0 {
		t.Fatal("a resolution oracle's non-empty Coverage must ride into the report")
	}
	if r.Coverage["sites_tu_split"] != 1 || r.Coverage["units"] != 4 {
		t.Errorf("coverage: %v", r.Coverage)
	}

	var buf bytes.Buffer
	Print(&buf, r)
	out := buf.String()
	if !strings.Contains(out, "coverage:") || !strings.Contains(out, "sites_tu_split:1") {
		t.Errorf("report lacks the coverage line:\n%s", out)
	}

	poison := CheckPoison(h, o)
	r.Poison = poison
	if !poison.Passed || poison.Confirmed != 0 {
		t.Fatalf("poison check should pass with nothing falsely confirmed: %+v", poison)
	}
}
