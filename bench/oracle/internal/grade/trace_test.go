package grade

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/contain"
	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
	"github.com/majax7714/Hobbes/bench/oracle/internal/export"
	"github.com/majax7714/Hobbes/bench/oracle/internal/pytrace"
)

// The Python trace oracle on the miniapp fixture (O6's self-test). Hand
// truth under its two tests: top_level, Engine(...), run, check,
// normalize (twice), helper — seven observed in-repo pairs, all seven
// drawn by Hobbes; api.py and cli.py never import, so their three edges
// are unobserved as not-loaded; nothing is suspect. Runs under the
// pipeline venv's own interpreter (CPython 3.12, pytest), inside the
// sandbox image (ADR-092 phase 2); skipped without containment.
func TestMiniappTrace(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	python := filepath.Join(pipeline, ".venv", "bin", "python")
	if _, err := os.Stat(python); err != nil {
		t.Skip("pipeline venv not built (uv sync)")
	}
	out := filepath.Join(t.TempDir(), "oracle.json")
	o, err := pytrace.Run(pytrace.Options{
		Repo: fixtures + "/miniapp", Module: ".", Runs: 2, SysPath: []string{"src"}, Out: out,
		Python: []string{python},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if o.Kind != "trace" || o.Runs != 2 || o.Coverage["files_loaded"] != 4 || o.Coverage["files_in_module"] != 8 {
		t.Fatalf("trace export header: kind %s runs %d coverage %v", o.Kind, o.Runs, o.Coverage)
	}
	pairs := map[string]bool{}
	for _, s := range o.Sites {
		if s.Mode != "observed" {
			t.Errorf("trace sites are observed, got %s", s.Mode)
		}
		for _, tg := range s.Targets {
			if !tg.External {
				pairs[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
		}
	}
	want := []string{
		"tests/test_core.py:12 -> src/miniapp/core.py:23",
		"src/miniapp/core.py:24 -> src/miniapp/core.py:10",
		"src/miniapp/core.py:25 -> src/miniapp/core.py:14",
		"src/miniapp/core.py:15 -> src/miniapp/core.py:18",
		"src/miniapp/core.py:16 -> src/miniapp/util.py:6",
		"tests/test_core.py:8 -> src/miniapp/util.py:6",
		"tests/test_core.py:17 -> tests/test_core.py:7",
	}
	for _, w := range want {
		if !pairs[w] {
			t.Errorf("missing observed pair %s", w)
		}
		delete(pairs, w)
	}
	for extra := range pairs {
		t.Errorf("unexpected in-repo pair %s", extra)
	}
	h, err := export.FromFile("../../testdata/miniapp.graph.json", ".", "py")
	if err != nil {
		t.Fatal(err)
	}
	r := Grade(h, o)
	if r.Total.Confirmed != 7 || r.Total.Suspect != 0 || r.Total.Unobserved != 3 || r.SilentBy["not-loaded"] != 3 {
		t.Fatalf("miniapp buckets: %+v %v", r.Total, r.SilentBy)
	}
	if r.Precision != nil {
		t.Fatal("a trace cell never reports precision")
	}
	if r.Recall == nil || *r.Recall != 1 || r.OraclePairs != 7 || r.SitesObserved != 7 || r.SitesTotal != 10 {
		t.Fatalf("miniapp recall %v (%d/%d) sites %d/%d", r.Recall, r.RecallHits, r.OraclePairs, r.SitesObserved, r.SitesTotal)
	}
	var buf bytes.Buffer
	Print(&buf, r)
	txt := buf.String()
	for _, must := range []string{"recall-against-executed 100.0% (7/7", "over 2 run(s)", "coverage: hobbes sites observed 7/10", "not precision"} {
		if !strings.Contains(txt, must) {
			t.Errorf("report must say %q:\n%s", must, txt)
		}
	}
	if strings.Contains(txt, "precision-against-oracle") {
		t.Errorf("trace report must not print a precision line:\n%s", txt)
	}
}

// H-36 (root RC-2): a comprehension's frame entry is a call the compiler
// wrote at the expression's own line — dropped and counted, never a
// target. On testdata/pygen, hand truth on CPython 3.12+: core.py:21 and
// core.py:25 each make one dropped `<genexpr>` entry; the calls written
// inside a comprehension (`double` from total's genexpr body at 21, from
// squares' inlined listcomp at 29) survive; `firsts` at 25 keeps its site
// through `tuple` (an external callee) but names no in-repo target; and the
// lambda `apply` binds is a function value someone does call, so it is
// still a target at 34. Run exactly as TestMiniappTrace is.
func TestComprehensionFramesAreExcluded(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	python := filepath.Join(pipeline, ".venv", "bin", "python")
	if _, err := os.Stat(python); err != nil {
		t.Skip("pipeline venv not built (uv sync)")
	}
	out := filepath.Join(t.TempDir(), "oracle.json")
	o, err := pytrace.Run(pytrace.Options{
		Repo: "../../testdata/pygen", Module: ".", Runs: 1, SysPath: []string{"src"}, Out: out,
		Python: []string{python},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if o.Excluded["generated"] <= 0 {
		t.Errorf("the dropped comprehension frames must be counted: excluded %v", o.Excluded)
	}
	pairs := map[string]bool{}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			for _, gen := range []string{"<genexpr>", "<listcomp>", "<setcomp>", "<dictcomp>"} {
				if strings.HasSuffix(tg.Name, gen) {
					t.Errorf("a comprehension is not a callee: %s -> %s (%s)", s.Pos.Key(), tg.Name, tg.Pos.Key())
				}
			}
			if !tg.External {
				pairs[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
			if s.Pos.Line == 34 && strings.HasSuffix(tg.Name, "<lambda>") {
				if !tg.Closure || tg.Pos.Line != 33 {
					t.Errorf("apply's lambda: closure %v at %s, want closure at core.py:33", tg.Closure, tg.Pos.Key())
				}
			}
		}
		if s.Pos.Path == "src/pygen/core.py" && s.Pos.Line == 25 {
			for _, tg := range s.Targets {
				if !tg.External {
					t.Errorf("firsts' line names an in-repo target: %s (%s)", tg.Name, tg.Pos.Key())
				}
			}
		}
	}
	for _, w := range []string{
		"src/pygen/core.py:21 -> src/pygen/core.py:16", // total's genexpr body calls double
		"src/pygen/core.py:29 -> src/pygen/core.py:16", // squares' comprehension calls double
		"src/pygen/core.py:34 -> src/pygen/core.py:33", // apply calls the lambda
	} {
		if !pairs[w] {
			t.Errorf("missing observed pair %s (have %v)", w, pairs)
		}
	}
}

// H-37: a `with` statement's `__enter__` (from BEFORE_WITH) and its
// exception-path `__exit__` (from WITH_EXCEPT_START) make no CALL event;
// the tracer reads them at the callee's PY_START, keyed at the `with` line
// as the normal-path `__exit__` already is. Hand truth in
// testdata/pywith/src/pywith/core.py's docstring; every line number is
// found in the fixture's text, not written here. Run exactly as
// TestComprehensionFramesAreExcluded is.
func TestWithStatementImplicitCalls(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	python := filepath.Join(pipeline, ".venv", "bin", "python")
	if _, err := os.Stat(python); err != nil {
		t.Skip("pipeline venv not built (uv sync)")
	}
	src, err := os.ReadFile("../../testdata/pywith/src/pywith/core.py")
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(string(src), "\n")
	// lineOf is the 1-based line of the first line at or after `from`
	// whose trimmed text starts with `prefix`.
	lineOf := func(from int, prefix string) int {
		t.Helper()
		for i := from; i < len(lines); i++ {
			if strings.HasPrefix(strings.TrimSpace(lines[i]), prefix) {
				return i + 1
			}
		}
		t.Fatalf("core.py has no line starting %q after line %d", prefix, from)
		return 0
	}
	const core = "src/pywith/core.py"
	at := func(line int) string { return core + ":" + strconv.Itoa(line) }
	var (
		base, cm, own = lineOf(0, "class Base:"), lineOf(0, "class CM(Base):"), lineOf(0, "class Own:")
		baseExit      = lineOf(base, "def __exit__")
		cmEnter       = lineOf(cm, "def __enter__")
		ownEnter      = lineOf(own, "def __enter__")
		ownExit       = lineOf(own, "def __exit__")
		makeDef       = lineOf(0, "def make() -> CM:")
		withPlain     = lineOf(lineOf(0, "def plain():"), "with CM():")
		withRaising   = lineOf(lineOf(0, "def raising():"), "with Own():")
		withTwo       = lineOf(0, "with CM(), Own():")
		withMake      = lineOf(0, "with make():")
		withGen       = lineOf(0, "with gen():")
	)

	out := filepath.Join(t.TempDir(), "oracle.json")
	o, err := pytrace.Run(pytrace.Options{
		Repo: "../../testdata/pywith", Module: ".", Runs: 1, SysPath: []string{"src"}, Out: out,
		Python: []string{python},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	pairs := map[string]bool{}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if strings.HasSuffix(tg.Name, ".__enter__") && tg.Via != "with" {
				t.Errorf("%s -> %s: an __enter__ is read at PY_START, via %q, want \"with\"", s.Pos.Key(), tg.Name, tg.Via)
			}
			if s.Pos.Path == core && s.Pos.Line == withRaising && tg.Name == "Own.__exit__" && tg.Via != "with" {
				t.Errorf("raising's exception-path __exit__: via %q, want \"with\"", tg.Via)
			}
			if s.Pos.Path == core && s.Pos.Line == withGen && tg.Via == "with" && !tg.External {
				t.Errorf("contextlib's __enter__/__exit__ are external, got in-repo %s (%s)", tg.Name, tg.Pos.Key())
			}
			if !tg.External {
				pairs[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
			}
		}
	}
	for _, w := range [][2]int{
		{withPlain, cmEnter}, {withPlain, baseExit}, {withPlain, cm},
		{withRaising, ownEnter}, {withRaising, ownExit}, {withRaising, own},
		{withTwo, cmEnter}, {withTwo, baseExit}, {withTwo, ownEnter}, {withTwo, ownExit}, {withTwo, cm}, {withTwo, own},
		{withMake, makeDef}, {withMake, cmEnter}, {withMake, baseExit}, {makeDef, cm},
	} {
		if p := at(w[0]) + " -> " + at(w[1]); !pairs[p] {
			t.Errorf("missing observed pair %s (have %v)", p, pairs)
		}
	}
}

// H-37 needs no grader change: a target the tracer read at PY_START is an
// ordinary target, matched on its declaration's position, so a Hobbes edge
// to the `__enter__` the line observed is confirmed, not suspect.
func TestWithTargetIsConfirmed(t *testing.T) {
	pos := func(p string, l int) edges.Pos { return edges.Pos{Path: p, Line: l} }
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: pos("a.py", 5), Target: pos("b.py", 30), Tier: "semantic"},
	}}
	o := &edges.OracleExport{Kind: "trace", Runs: 1, Files: []string{"a.py", "b.py"}, Sites: []edges.Site{
		{Pos: pos("a.py", 5), Mode: "observed", Targets: []edges.Target{
			{Pos: pos("b.py", 20), Name: "CM", Kind: "class"},
			{Pos: pos("b.py", 30), Name: "CM.__enter__", Kind: "method", Via: "with"},
		}},
	}}
	r := Grade(h, o)
	if len(r.Rows) != 1 || r.Rows[0].Bucket != "confirmed" {
		t.Fatalf("an __enter__ edge on a line that observed it: %+v", r.Rows)
	}
	if r.Total.Suspect != 0 || r.OraclePairs != 2 || r.RecallHits != 1 {
		t.Errorf("buckets %+v, recall %d/%d", r.Total, r.RecallHits, r.OraclePairs)
	}
}

// The §3.1 buckets on synthetic data: a wrong target on a line whose
// only observed callees are in-repo is suspect; the same on a line that
// also called C is line-mixed (charged to nobody); a line that never
// called is line-not-called; a file that never ran is not-loaded.
func TestTraceBuckets(t *testing.T) {
	pos := func(p string, l int) edges.Pos { return edges.Pos{Path: p, Line: l} }
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: pos("a.py", 1), Target: pos("b.py", 10), Tier: "semantic"},
		{Site: pos("a.py", 2), Target: pos("b.py", 10), Tier: "semantic"},
		{Site: pos("a.py", 3), Target: pos("b.py", 10), Tier: "syntactic"},
		{Site: pos("a.py", 4), Target: pos("b.py", 10), Tier: "semantic"},
		{Site: pos("z.py", 1), Target: pos("b.py", 10), Tier: "semantic"},
	}}
	o := &edges.OracleExport{Kind: "trace", Runs: 1, Files: []string{"a.py", "b.py"}, Sites: []edges.Site{
		{Pos: pos("a.py", 1), Mode: "observed", Targets: []edges.Target{{Pos: pos("b.py", 10), Name: "f", Kind: "function"}}},
		{Pos: pos("a.py", 2), Mode: "observed", Targets: []edges.Target{{Pos: pos("b.py", 20), Name: "g", Kind: "function"}}},
		{Pos: pos("a.py", 3), Mode: "observed", CCallees: 1, Targets: []edges.Target{{Pos: pos("b.py", 20), Name: "g", Kind: "function"}}},
	}}
	r := Grade(h, o)
	got := map[string]string{}
	for _, row := range r.Rows {
		got[row.Edge.Site.Key()] = row.Bucket + "/" + row.Reason
	}
	want := map[string]string{
		"a.py:1": "confirmed/", "a.py:2": "suspect/", "a.py:3": "unobserved/line-mixed",
		"a.py:4": "unobserved/line-not-called", "z.py:1": "unobserved/not-loaded",
	}
	for k, v := range want {
		if got[k] != v {
			t.Errorf("%s: want %s got %s", k, v, got[k])
		}
	}
	if r.Total.Contradicted != 0 || r.Precision != nil {
		t.Error("a trace never contradicts")
	}
	if r.SuspectRate == nil || *r.SuspectRate != 0.5 {
		t.Errorf("suspect rate 1/(1+1): %v", r.SuspectRate)
	}
	// Recall: three observed in-repo pairs, one drawn.
	if r.OraclePairs != 3 || r.RecallHits != 1 || r.MissBy["observed→function"] != 2 {
		t.Errorf("recall %d/%d misses %v", r.RecallHits, r.OraclePairs, r.MissBy)
	}
	if r.ByTier["syntactic"].Unobserved != 1 {
		t.Errorf("tier split lost: %+v", r.ByTier)
	}

	// The resolution oracle's `coverage: <map>` line (ADR-110's C row) is
	// for resolution oracles only: a trace report prints its own
	// coverage line (§3.1's "hobbes sites observed ..."), and the former
	// must never leak into it.
	var buf bytes.Buffer
	Print(&buf, r)
	txt := buf.String()
	if strings.Contains(txt, "coverage: map[") {
		t.Errorf("a resolution oracle's coverage line must not leak into a trace report:\n%s", txt)
	}
	if !strings.Contains(txt, "coverage: hobbes sites observed") {
		t.Errorf("a trace report must print its own coverage line:\n%s", txt)
	}
}

// H-38: the tracer reads a callable's `__code__`, `__func__` and
// `__wrapped__` without running the repo's code. testdata/pygetattr's
// `__getattr__` answers every name and records it; its test asserts the
// record is empty, so a tracer that asks it fails the suite under trace
// only. The three unwindings it must still make are its docstring's hand
// truth; every line number is found in the fixture's text.
func TestTracerRunsNoRepoCode(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	python := filepath.Join(pipeline, ".venv", "bin", "python")
	if _, err := os.Stat(python); err != nil {
		t.Skip("pipeline venv not built (uv sync)")
	}
	src, err := os.ReadFile("../../testdata/pygetattr/src/pygetattr/core.py")
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(string(src), "\n")
	lineOf := func(from int, prefix string) int {
		t.Helper()
		for i := from; i < len(lines); i++ {
			if strings.HasPrefix(strings.TrimSpace(lines[i]), prefix) {
				return i + 1
			}
		}
		t.Fatalf("core.py has no line starting %q after line %d", prefix, from)
		return 0
	}
	const core = "src/pygetattr/core.py"
	at := func(line int) string { return core + ":" + strconv.Itoa(line) }
	var (
		anyCls  = lineOf(0, "class Anything:")
		callDef = lineOf(anyCls, "def __call__")
		ping    = lineOf(lineOf(0, "class Bound(Anything):"), "def ping")
		plain   = lineOf(0, "def plain(x):")
		aCall   = lineOf(lineOf(0, "def call_instance():"), "return a()")
		logged  = lineOf(lineOf(0, "def call_wrapped():"), "return logged(1)")
		bPing   = lineOf(lineOf(0, "def call_method():"), "return b.ping()")
	)
	out := filepath.Join(t.TempDir(), "oracle.json")
	o, err := pytrace.Run(pytrace.Options{
		Repo: "../../testdata/pygetattr", Module: ".", Runs: 1, SysPath: []string{"src"}, Out: out,
		Python: []string{python},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(o.SuiteExitCodes) != 1 || o.SuiteExitCodes[0] != 0 {
		t.Fatalf("the suite under trace exited %v, want [0]: the tracer ran the repo's __getattr__", o.SuiteExitCodes)
	}
	via := map[string]string{}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if !tg.External {
				via[s.Pos.Key()+" -> "+tg.Pos.Key()] = tg.Via
			}
		}
	}
	for _, w := range []struct {
		site, target int
		via          string
	}{{aCall, callDef, "__call__"}, {logged, plain, "wrapped"}, {bPing, ping, ""}} {
		p := at(w.site) + " -> " + at(w.target)
		if got, ok := via[p]; !ok {
			t.Errorf("missing observed pair %s (have %v)", p, via)
		} else if got != w.via {
			t.Errorf("%s: via %q, want %q", p, got, w.via)
		}
	}
}

// ADR-187: a trace key's implicit list moves no bucket, rate or standing
// recall; it adds only the companion recall beside the standing one. The
// rich shape that motivated it: an edge on a line where the key observed
// nothing but an implicit call stays `unobserved`, never `suspect`.
func TestImplicitListJudgesNothingAndAddsACompanionRecall(t *testing.T) {
	pos := func(p string, l int) edges.Pos { return edges.Pos{Path: p, Line: l} }
	h := &edges.HobbesExport{Edges: []edges.HobbesEdge{
		{Site: pos("a.py", 5), Target: pos("b.py", 30), Tier: "semantic"},   // confirmed by a standing site
		{Site: pos("a.py", 9), Target: pos("b.py", 40), Tier: "semantic"},   // a line only an implicit row speaks about
		{Site: pos("a.py", 12), Target: pos("b.py", 50), Tier: "syntactic"}, // drawn to a getter the trace keyed implicit
	}}
	standing := []edges.Site{
		{Pos: pos("a.py", 5), Mode: "observed", Targets: []edges.Target{
			{Pos: pos("b.py", 30), Name: "f", Kind: "function"},
			{Pos: pos("b.py", 31), Name: "g", Kind: "function"},
		}},
	}
	implicit := []edges.ImplicitSite{
		{Pos: pos("a.py", 9), Targets: []edges.ImplicitTarget{
			{Target: edges.Target{Pos: pos("b.py", 60), Name: "C.p", Kind: "method", Via: "implicit"}, Families: []string{"attribute"}},
		}},
		{Pos: pos("a.py", 12), Targets: []edges.ImplicitTarget{
			{Target: edges.Target{Pos: pos("b.py", 50), Name: "C.q", Kind: "method", Via: "implicit"}, Families: []string{"operator", "attribute"}},
			{Target: edges.Target{Name: "X.__eq__", External: true, Via: "implicit"}, Families: []string{"operator"}},
		}},
	}
	o := &edges.OracleExport{Kind: "trace", Runs: 1, Files: []string{"a.py", "b.py"}, Sites: standing}
	base := Grade(h, o)
	o.Implicit = implicit
	r := Grade(h, o)
	for i := range base.Rows {
		if base.Rows[i].Bucket != r.Rows[i].Bucket {
			t.Errorf("row %d: %s without the list, %s with it", i, base.Rows[i].Bucket, r.Rows[i].Bucket)
		}
	}
	if r.Rows[1].Bucket != "unobserved" {
		t.Errorf("a line only an implicit row speaks about: %s, want unobserved", r.Rows[1].Bucket)
	}
	if r.Total != base.Total || r.RecallHits != 1 || r.OraclePairs != 2 || *r.Recall != *base.Recall {
		t.Errorf("standing grade moved: %+v recall %d/%d, was %+v %d/%d", r.Total, r.RecallHits, r.OraclePairs, base.Total, base.RecallHits, base.OraclePairs)
	}
	if base.RecallWithImplicit != nil || base.ImplicitBy != nil {
		t.Errorf("a key without the list printed a companion: %v %v", base.RecallWithImplicit, base.ImplicitBy)
	}
	if r.ImplicitPairs != 2 || r.ImplicitHits != 1 || r.RecallWithImplicit == nil || *r.RecallWithImplicit != 0.5 {
		t.Errorf("companion: %d/%d implicit, recall_with_implicit %v; want 1/2 and 2/4", r.ImplicitHits, r.ImplicitPairs, r.RecallWithImplicit)
	}
	want := map[string]Fraction{"attribute": {Pairs: 1}, "attribute+operator": {Hits: 1, Pairs: 1}}
	if fmt.Sprint(r.ImplicitBy) != fmt.Sprint(want) {
		t.Errorf("by family %v, want %v (external rows are out, families sorted)", r.ImplicitBy, want)
	}
	var b bytes.Buffer
	Print(&b, r)
	if !strings.Contains(b.String(), "recall-with-implicit 50.0% (2/4") {
		t.Errorf("printed report lacks the companion line:\n%s", b.String())
	}
}

// ADR-187: the tracer keys calls with no call token into the export's
// implicit list, never into sites. Hand truth is testdata/pyimplicit's
// own comments: a `# implicit: <def>` line keys that def there, a
// `# not implicit` line keys nothing implicit. Run as the other fixtures.
func TestTracerKeysImplicitCallsApart(t *testing.T) {
	if why := contain.UnavailableReason(); why != "" && !contain.Uncontained() {
		t.Skip("containment unavailable: " + why)
	}
	pipeline, _ := filepath.Abs("../../../../pipeline")
	python := filepath.Join(pipeline, ".venv", "bin", "python")
	if _, err := os.Stat(python); err != nil {
		t.Skip("pipeline venv not built (uv sync)")
	}
	src, err := os.ReadFile("../../testdata/pyimplicit/src/pyimplicit/core.py")
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(string(src), "\n")
	const core = "src/pyimplicit/core.py"
	at := func(line int) string { return core + ":" + strconv.Itoa(line) }
	// defLine is the def a `# implicit:` name means: `p.setter` the def
	// after `@p.setter`, any other name its own `def <name>(`.
	defLine := func(name string) int {
		t.Helper()
		after := ""
		if base, ok := strings.CutSuffix(name, ".setter"); ok {
			after, name = "@"+base+".setter", base
		}
		armed := after == ""
		for i, l := range lines {
			l = strings.TrimSpace(l)
			if !armed && l == after {
				armed = true
			} else if armed && strings.HasPrefix(l, "def "+name+"(") {
				return i + 1
			}
		}
		t.Fatalf("core.py declares no %q", name)
		return 0
	}
	want, quiet := map[string]bool{}, map[int]bool{}
	body := -1
	for i, l := range lines {
		if strings.HasPrefix(l, "def body():") {
			body = i
		}
		if body < 0 {
			continue // the docstring spells the markers too
		}
		if _, name, ok := strings.Cut(l, "# implicit: "); ok {
			want[at(i+1)+" -> "+at(defLine(strings.TrimSpace(name)))] = true
		} else if strings.HasSuffix(l, "# not implicit") {
			quiet[i+1] = true
		}
	}
	if len(want) != 10 || len(quiet) != 5 {
		t.Fatalf("the fixture's hand truth reads %d implicit and %d quiet lines, want 10 and 5", len(want), len(quiet))
	}
	out := filepath.Join(t.TempDir(), "oracle.json")
	o, err := pytrace.Run(pytrace.Options{
		Repo: "../../testdata/pyimplicit", Module: ".", Runs: 1, SysPath: []string{"src"}, Out: out,
		Python: []string{python},
		Pytest: []string{"-q", "-p", "no:cacheprovider", "-c", "pyproject.toml", "--rootdir", ".", "--import-mode=importlib", "tests"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(o.SuiteExitCodes) != 1 || o.SuiteExitCodes[0] != 0 {
		t.Fatalf("the suite under trace exited %v, want [0]", o.SuiteExitCodes)
	}
	for _, s := range o.Sites {
		for _, tg := range s.Targets {
			if tg.Via == "implicit" {
				t.Errorf("sites holds an implicit target: %s -> %s", s.Pos.Key(), tg.Name)
			}
		}
	}
	got := map[string]bool{}
	for _, s := range o.Implicit {
		for _, tg := range s.Targets {
			if tg.External {
				continue
			}
			if tg.Via != "implicit" || len(tg.Opcodes) == 0 || len(tg.Families) == 0 {
				t.Errorf("%s -> %s: via %q, opcodes %v, families %v", s.Pos.Key(), tg.Name, tg.Via, tg.Opcodes, tg.Families)
			}
			if s.Pos.Path == core && quiet[s.Pos.Line] {
				t.Errorf("a `not implicit` line keyed %s implicit at %s", tg.Name, s.Pos.Key())
			}
			got[s.Pos.Key()+" -> "+tg.Pos.Key()] = true
		}
	}
	for p := range want {
		if !got[p] {
			t.Errorf("missing implicit pair %s (have %v)", p, got)
		}
	}
	for p := range got {
		if strings.HasPrefix(p, core+":") && !want[p] {
			t.Errorf("an implicit pair the hand truth does not name: %s", p)
		}
	}
}
