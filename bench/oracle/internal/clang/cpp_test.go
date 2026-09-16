package clang

import (
	"path/filepath"
	"strconv"
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

// loadCppFixtureShards runs clang++ over the cppclang fixture the way its
// Makefile's compile database would — two programs, so shapes.cpp is two
// units and shapes.h is in all four — and loads the shards RunUnits
// wrote. The C fixture's dumps are committed and read back; C++'s are
// not, because a C++ dump is the front end's own mangling and reading it
// from a stored file would freeze the very thing under test.
func loadCppFixtureShards(t *testing.T) []*Shard {
	t.Helper()
	shards := loadCppUnits(t, []string{"main.cpp", "shapes.cpp", "tool.cpp", "shapes.cpp"})
	for i, s := range shards {
		if !s.CXX {
			t.Errorf("unit %d: a .cpp entry must run the C++ binary", i)
		}
	}
	return shards
}

// loadCppUnits compiles the named cppclang sources, one unit each in the
// order given and each with extra on its own command line, and loads the
// shards RunUnits wrote. A defect's own test names its own sources, so
// the fixture's hand-keyed table below stands on exactly the four it has
// always stood on.
func loadCppUnits(t *testing.T, srcs []string, extra ...string) []*Shard {
	t.Helper()
	if !haveTool("clang++") {
		t.Skip("clang++ not on PATH")
	}
	repo, err := filepath.Abs("../../testdata/cppclang")
	if err != nil {
		t.Fatal(err)
	}
	entries := make([]CompdbEntry, 0, len(srcs))
	for _, src := range srcs {
		cc := "c++"
		if !isCPPExt(src) {
			cc = "cc"
		}
		args := append([]string{cc, "-Wall", "-I."}, extra...)
		entries = append(entries, CompdbEntry{Directory: repo, File: src, Arguments: append(args, "-c", src)})
	}
	out := t.TempDir()
	compdb := filepath.Join(out, "compile_commands.json")
	writeCompdb(t, compdb, entries)
	if err := RunUnits(Options{Repo: repo, Lang: "cpp", Compdb: compdb, Out: out}); err != nil {
		t.Fatalf("RunUnits: %v", err)
	}
	shards, err := LoadShards(filepath.Join(out, "clang-shards"))
	if err != nil {
		t.Fatal(err)
	}
	for i, s := range shards {
		if s.Failed {
			t.Fatalf("unit %d (%s): the front end rejected it: %s", i, srcs[i], s.Stderr)
		}
	}
	return shards
}

// sitesAt is every site at one exact position: a call written inside a
// class template is two sites there, the pattern's and the
// instantiation's, keyed apart by what each one's declaration is keyed
// by.
func sitesAt(out *edges.OracleExport, path string, line, col int) []edges.Site {
	var got []edges.Site
	for _, s := range out.Sites {
		if s.Pos.Path == path && s.Pos.Line == line && s.Col == col {
			got = append(got, s)
		}
	}
	return got
}

// TestCppclangFixture is O10's own evidence (ADR-113 §3): every pair the
// cppclang fixture makes, hand-computed from its four sources, read
// through clang++, the reader and Merge.
func TestCppclangFixture(t *testing.T) {
	out := Merge(loadCppFixtureShards(t), "")

	if got, want := out.Files, []string{"main.cpp", "shapes.cpp", "shapes.h", "tool.cpp"}; !equalStrings(got, want) {
		t.Fatalf("files: %v, want %v", got, want)
	}

	wantCoverage := map[string]int{
		"units": 4, "units_failed": 0, "units_cpp": 4,
		"sites_static": 15, "sites_macro": 1, "sites_dynamic": 2,
		"sites_virtual": 2, "sites_operator": 1, "sites_constructor": 4,
		"sites_external": 0, "sites_link_ambiguous": 0, "sites_undefined": 0, "sites_tu_split": 0,
	}
	for k, v := range wantCoverage {
		if out.Coverage[k] != v {
			t.Errorf("coverage[%s] = %d, want %d (full: %v)", k, out.Coverage[k], v, out.Coverage)
		}
	}

	byKey := map[string][]edges.Site{}
	for _, s := range out.Sites {
		k := s.Pos.Key() + "@" + strconv.Itoa(s.Col)
		byKey[k] = append(byKey[k], s)
	}
	get := func(path string, line, col int, mode string) edges.Site {
		t.Helper()
		for _, s := range byKey[path+":"+strconv.Itoa(line)+"@"+strconv.Itoa(col)] {
			if s.Mode == mode {
				return s
			}
		}
		t.Fatalf("no %s site at %s:%d col %d", mode, path, line, col)
		return edges.Site{}
	}

	// Every in-repo pair, by hand: `shapes.cpp:21` is Circle's
	// constructor, `:13` Shape::area, `:23` Circle::area, `:17`
	// Shape::units, `:27` operator+, `:33`/`:35` the overload pair,
	// `:37` plain, `:5` the anonymous namespace's hidden, `:9` the
	// static local; `shapes.h:9` the inline method, `:27` the template.
	cases := []struct {
		path         string
		line, col    int
		mode, caller string
		target       string
		kind         string
	}{
		// A free function, a static member function through a qualified
		// name (a CallExpr, not a member call), and the macro's body.
		{"main.cpp", 17, 13, "static", "main", "shapes.cpp:37", "function"},
		{"main.cpp", 18, 10, "static", "main", "shapes.cpp:17", "method"},
		{"main.cpp", 19, 10, "macro", "main", "shapes.cpp:37", "function"},
		// The template's specialisation sits at the template's own line.
		{"main.cpp", 20, 10, "static", "main", "shapes.h:27", "function"},
		// The overload pair: one name, two mangled names, two lines.
		{"main.cpp", 21, 10, "static", "main", "shapes.cpp:33", "function"},
		{"main.cpp", 22, 10, "static", "main", "shapes.cpp:35", "function"},
		// Construction three ways — a variable, a new expression and a
		// temporary — all to the constructor's own definition.
		{"main.cpp", 23, 20, "constructor", "main", "shapes.cpp:21", "constructor"},
		{"main.cpp", 27, 32, "constructor", "main", "shapes.cpp:21", "constructor"},
		{"main.cpp", 29, 10, "constructor", "main", "shapes.cpp:21", "constructor"},
		{"tool.cpp", 4, 20, "constructor", "main", "shapes.cpp:21", "constructor"},
		// A virtual call through a base pointer to a derived object is
		// the base's method: the front end names the static type's, and
		// O10 builds no class hierarchy over it. Every member call below
		// is keyed at the member's own token, not at its object's first
		// (H-28): `p->area()` at the `area`, column 13.
		{"main.cpp", 25, 13, "virtual", "main", "shapes.cpp:13", "method"},
		// The same rule inside the header's inline method (this->area()).
		// An implicit `this` is written nowhere, so the object and the
		// member begin at one column.
		{"shapes.h", 9, 32, "virtual", "Shape::twice", "shapes.cpp:13", "method"},
		// Circle::area does not repeat the `virtual` keyword, and the
		// dump prints only what was written: the call reads as an
		// ordinary member call. The target is the same method either way.
		{"main.cpp", 28, 16, "static", "main", "shapes.cpp:23", "method"},
		{"main.cpp", 29, 28, "static", "main", "shapes.cpp:23", "method"},
		// The operator applied by symbol is the free operator function.
		{"main.cpp", 32, 25, "operator", "main", "shapes.cpp:27", "function"},
		// A method and a `this->` call, both inside an unnamed namespace,
		// and the method the dump declares below the body that calls it.
		{"main.cpp", 35, 17, "static", "main", "main.cpp:6", "method"},
		{"main.cpp", 6, 30, "static", "Runner::run", "main.cpp:7", "method"},
		{"main.cpp", 36, 10, "static", "main", "main.cpp:12", "function"},
		// The unnamed namespace's helper and the file-static one resolve
		// in their own unit, as C's statics do.
		{"shapes.cpp", 14, 12, "static", "Shape::area", "shapes.cpp:5", "function"},
		{"shapes.cpp", 18, 12, "static", "Shape::units", "shapes.cpp:9", "function"},
		// tool.cpp is the second program: the same header, the same
		// inline method, the same free function.
		{"tool.cpp", 5, 14, "static", "main", "shapes.h:9", "method"},
		{"tool.cpp", 5, 24, "static", "main", "shapes.cpp:37", "function"},
	}
	for _, c := range cases {
		s := get(c.path, c.line, c.col, c.mode)
		if s.Caller != c.caller {
			t.Errorf("%s:%d col %d: caller=%s, want %s", c.path, c.line, c.col, s.Caller, c.caller)
		}
		if len(s.Targets) != 1 {
			t.Errorf("%s:%d col %d: targets %+v, want one (%s)", c.path, c.line, c.col, s.Targets, c.target)
			continue
		}
		if got := s.Targets[0]; got.Pos.Key() != c.target || got.Kind != c.kind {
			t.Errorf("%s:%d col %d: target %s kind %s, want %s kind %s",
				c.path, c.line, c.col, got.Pos.Key(), got.Kind, c.target, c.kind)
		}
	}

	// The header's inline method is one entity across the two units that
	// call it — both compile their own copy, at one position — so its
	// site keeps one target and never counts tu-split.
	inline := get("main.cpp", 26, 12, "static")
	if len(inline.Targets) != 1 || inline.Targets[0].Pos.Key() != "shapes.h:9" {
		t.Errorf("c.twice(): %+v, want the header's own line, once", inline.Targets)
	}

	// The implicit copy constructor (main.cpp:33, `Point copy = s;`) and
	// the implicit default one (main.cpp:34, `Runner runner;`) are never
	// targets, and the sites that would name them are not sites.
	for _, line := range []int{33, 34} {
		for _, s := range out.Sites {
			if s.Pos.Path == "main.cpp" && s.Pos.Line == line {
				t.Errorf("main.cpp:%d constructs through a compiler-written constructor: %+v", line, s)
			}
		}
	}

	// Dynamic, no targets: a call through a function pointer, and the
	// template pattern's own `v + v`, which the front end writes as an
	// operator call to a lookup it has not resolved yet.
	for _, c := range []struct {
		path      string
		line, col int
	}{{"main.cpp", 13, 12}, {"shapes.h", 28, 14}} {
		s := get(c.path, c.line, c.col, "dynamic")
		if len(s.Targets) != 0 {
			t.Errorf("%s:%d col %d: %+v", c.path, c.line, c.col, s.Targets)
		}
	}

	if len(out.Sites) != 25 {
		t.Errorf("total distinct sites: %d, want 25", len(out.Sites))
	}
}

// TestCppMemberCallSitsAtItsMemberToken is H-28's evidence: a member
// call whose object expression is written across two lines sits at the
// member's own token, on the line the member is on. member.cpp's chain
// keyed both of its calls at the object's opening `(`, line 25 column
// 12, before the reader read a MemberExpr's range end (ADR-113 §3).
func TestCppMemberCallSitsAtItsMemberToken(t *testing.T) {
	out := Merge(loadCppUnits(t, []string{"member.cpp"}), "")

	// `(m << 1` opens on line 25 and `<< 2).str().get()` closes it on
	// line 26: `str` at column 21, `get` at 27, each resolving to its own
	// method's definition.
	for _, c := range []struct {
		col    int
		target string
	}{{21, "member.cpp:20"}, {27, "member.cpp:11"}} {
		got := sitesAt(out, "member.cpp", 26, c.col)
		if len(got) != 1 {
			t.Errorf("member.cpp:26 col %d: %d sites, want the one member call: %+v", c.col, len(got), got)
			continue
		}
		s := got[0]
		if s.Mode != "static" || s.Caller != "build" {
			t.Errorf("member.cpp:26 col %d: mode=%s caller=%s, want static build", c.col, s.Mode, s.Caller)
		}
		if len(s.Targets) != 1 || s.Targets[0].Pos.Key() != c.target {
			t.Errorf("member.cpp:26 col %d: targets %+v, want %s alone", c.col, s.Targets, c.target)
		}
	}

	// Line 25 carries the first `<<` and nothing else: the object's own
	// start is not a call site.
	for _, s := range out.Sites {
		if s.Pos.Line == 25 && s.Mode != "operator" {
			t.Errorf("member.cpp:25 is the object's line, not a member call's: %+v", s)
		}
	}
	// Two operator calls, at their own tokens, and the two member calls.
	if len(out.Sites) != 4 {
		t.Errorf("total distinct sites: %d, want 4: %+v", len(out.Sites), out.Sites)
	}
}

// TestCppMacroQualifiedCallSitsAtTheNameTheAuthorWrote is H-31's
// evidence: a call whose qualifier comes from a macro body (`#define
// SYS(call) ::call`, fmt's FMT_SYSTEM) and whose name comes from the
// macro's argument sits at the name the author wrote. Before the reader
// read the callee's range end, macroqual.cpp:32's `g` keyed on the
// `#define` line 28 and macroqual.cpp:40's on its own `SYS` token — the
// two halves that put fmt's six `os.cc` calls on `include/fmt/os.h:57`
// and `:62`, lines in another file altogether.
func TestCppMacroQualifiedCallSitsAtTheNameTheAuthorWrote(t *testing.T) {
	out := Merge(loadCppUnits(t, []string{"macroqual.cpp"}), "")

	// `return RETRY(SYS(g(s.c_str())));` on line 32, the `g` at column 22
	// and its own argument's `c_str` at 26; `return SYS(g(s.c_str()));`
	// on line 40, at 16 and 20. The `c_str` of each is a pure
	// macro-argument call, always keyed right and right still — which is
	// what made the loss invisible in fmt, where `src/os.cc:176` held
	// `c_str` and `__errno_location` but never `fopen`.
	for _, c := range []struct {
		line, col int
		target    string
		callee    string
		caller    string
	}{
		{32, 22, "macroqual.cpp:14", "g", "run"},
		{32, 26, "macroqual.cpp:11", "c_str", "run"},
		{40, 16, "macroqual.cpp:14", "g", "once"},
		{40, 20, "macroqual.cpp:11", "c_str", "once"},
	} {
		got := sitesAt(out, "macroqual.cpp", c.line, c.col)
		if len(got) != 1 {
			t.Errorf("macroqual.cpp:%d col %d (%s): %d sites, want the one call: %+v",
				c.line, c.col, c.callee, len(got), got)
			continue
		}
		s := got[0]
		if s.Mode != "static" || s.Caller != c.caller {
			t.Errorf("macroqual.cpp:%d col %d (%s): mode=%s caller=%s, want static %s",
				c.line, c.col, c.callee, s.Mode, s.Caller, c.caller)
		}
		if len(s.Targets) != 1 || s.Targets[0].Pos.Key() != c.target {
			t.Errorf("macroqual.cpp:%d col %d (%s): targets %+v, want %s alone",
				c.line, c.col, c.callee, s.Targets, c.target)
		}
	}

	// The two `#define` lines carry no call: line 28 is where `run`'s `g`
	// sat, and `once`'s sat at the `SYS` token of its own line, column 12.
	for _, s := range out.Sites {
		if s.Pos.Line == 28 || s.Pos.Line == 29 || (s.Pos.Line == 40 && s.Col == 12) {
			t.Errorf("macroqual.cpp:%d col %d is the macro's position, not the call's: %+v",
				s.Pos.Line, s.Col, s)
		}
	}
	// Two `g`s, two `c_str`s and the controls' three, and nothing else.
	if len(out.Sites) != 7 {
		t.Errorf("total distinct sites: %d, want 7: %+v", len(out.Sites), out.Sites)
	}
}

// TestCppQualifiedCallKeepsItsQualifiersColumn is H-31's control: a
// qualified call the author wrote whole keys where it always has, at the
// qualifier's own token, whether or not a macro carried it. The naive
// form of the fix — always take the callee's range end — would move all
// three of these onto the name, and with them the cppclang fixture's
// hand-keyed columns.
func TestCppQualifiedCallKeepsItsQualifiersColumn(t *testing.T) {
	out := Merge(loadCppUnits(t, []string{"macroqual.cpp"}), "")

	// `return ns::h(1) + ns::t<int>(2);` on line 45: the first `ns` at
	// column 12, the second at 23. `return RETRY(ns::h(2));` on line 53:
	// the `ns` at 18, inside the macro's argument, where clang flags the
	// call's two ends exactly as it flags the H-31 shape's.
	for _, c := range []struct {
		line, col int
		target    string
		caller    string
	}{
		{45, 12, "macroqual.cpp:18", "plain"},
		{45, 23, "macroqual.cpp:21", "plain"},
		{53, 18, "macroqual.cpp:18", "wrapped"},
	} {
		got := sitesAt(out, "macroqual.cpp", c.line, c.col)
		if len(got) != 1 {
			t.Errorf("macroqual.cpp:%d col %d: %d sites, want the one call: %+v", c.line, c.col, len(got), got)
			continue
		}
		s := got[0]
		if s.Mode != "static" || s.Caller != c.caller {
			t.Errorf("macroqual.cpp:%d col %d: mode=%s caller=%s, want static %s",
				c.line, c.col, s.Mode, s.Caller, c.caller)
		}
		if len(s.Targets) != 1 || s.Targets[0].Pos.Key() != c.target {
			t.Errorf("macroqual.cpp:%d col %d: targets %+v, want %s alone", c.line, c.col, s.Targets, c.target)
		}
	}
}

// TestCppTemplatePatternsKeyByTheirClass is H-29's evidence: two class
// templates with a same-named static member are two entities, so each
// template's call answers its own class's member. Both patterns keyed as
// the bare `format_as` before declKey fell back to the class, and the
// merge answered whichever of the two it had kept.
func TestCppTemplatePatternsKeyByTheirClass(t *testing.T) {
	shards := loadCppUnits(t, []string{"tmpl.cpp"})

	// The front end's own half of the defect: a pattern member carries
	// its class and no mangled name at all, where the instantiation it
	// stands for carries one and keys by it.
	patterns := map[string]string{}
	for _, d := range shards[0].Decls {
		if d.Name != "format_as" {
			continue
		}
		if d.Mangled == "" {
			patterns[d.Class] = declKey(d)
			continue
		}
		if declKey(d) != d.Mangled {
			t.Errorf("a specialisation keys by its mangled name: %q, want %q", declKey(d), d.Mangled)
		}
	}
	if patterns["A"] != "A::format_as" || patterns["B"] != "B::format_as" {
		t.Errorf("the two patterns' keys are %v, want A::format_as and B::format_as", patterns)
	}

	out := Merge(shards, "")

	// `format_as(…)` is written at column 30 of both line 9 and line 15,
	// and each line is a member function of its own class: A's call
	// answers tmpl.cpp:8 and B's tmpl.cpp:14, never the other's. Each
	// position holds two sites — the pattern's and the A<int>/B<int>
	// instantiation's — and both name the one definition.
	for _, c := range []struct {
		line   int
		target string
	}{{9, "tmpl.cpp:8"}, {15, "tmpl.cpp:14"}} {
		got := sitesAt(out, "tmpl.cpp", c.line, 30)
		if len(got) != 2 {
			t.Errorf("tmpl.cpp:%d col 30: %d sites, want the pattern's and the instantiation's: %+v", c.line, len(got), got)
		}
		for _, s := range got {
			if len(s.Targets) != 1 || s.Targets[0].Pos.Key() != c.target {
				t.Errorf("tmpl.cpp:%d col 30: targets %+v, want %s alone", c.line, s.Targets, c.target)
			}
		}
	}

	// And the two member calls that instantiate them, at their own member
	// tokens (H-28), each to its own class's `use`.
	for _, c := range []struct {
		col    int
		target string
	}{{14, "tmpl.cpp:9"}, {24, "tmpl.cpp:15"}} {
		got := sitesAt(out, "tmpl.cpp", 21, c.col)
		if len(got) != 1 || len(got[0].Targets) != 1 || got[0].Targets[0].Pos.Key() != c.target {
			t.Errorf("tmpl.cpp:21 col %d: %+v, want %s alone", c.col, got, c.target)
		}
	}
}

// TestCppBareNameKeysJoinAcrossUnits covers what H-29's fallback leaves
// alone: `extern "C"` and `main` are the names the front end does not
// decorate, so their key is the bare name whichever branch declKey
// takes, and a declaration in one unit still joins the definition in
// another — ADR-110's C join, unchanged. extc.c and extc2.c compile
// under either front end, so both are run.
func TestCppBareNameKeysJoinAcrossUnits(t *testing.T) {
	for _, lang := range []struct {
		name  string
		extra []string
	}{
		{"as c", nil},
		{"as c++", []string{"-x", "c++"}},
	} {
		t.Run(lang.name, func(t *testing.T) {
			out := Merge(loadCppUnits(t, []string{"extc.c", "extc2.c"}, lang.extra...), "")

			// extc.c calls what extc2.c defines; extc2.c calls the `main`
			// extc.c defines.
			for _, c := range []struct {
				path      string
				line, col int
				name      string
				target    string
			}{
				{"extc.c", 17, 12, "shared_entry", "extc2.c:16"},
				{"extc2.c", 21, 12, "main", "extc.c:16"},
			} {
				got := sitesAt(out, c.path, c.line, c.col)
				if len(got) != 1 {
					t.Errorf("%s:%d col %d: %d sites, want one: %+v", c.path, c.line, c.col, len(got), got)
					continue
				}
				if ts := got[0].Targets; len(ts) != 1 || ts[0].Pos.Key() != c.target || ts[0].Name != c.name {
					t.Errorf("%s:%d col %d: targets %+v, want %s (%s) alone", c.path, c.line, c.col, ts, c.target, c.name)
				}
			}
		})
	}
}

// TestCppUnitsPickTheirOwnFrontEnd covers the runner's rule: the entry's
// own extension decides the binary, so a mixed build root is one root.
func TestCppUnitsPickTheirOwnFrontEnd(t *testing.T) {
	cases := []struct {
		entry CompdbEntry
		want  bool
	}{
		{CompdbEntry{File: "a.cpp"}, true},
		{CompdbEntry{File: "a.cc"}, true},
		{CompdbEntry{File: "a.cxx"}, true},
		{CompdbEntry{File: "a.c++"}, true},
		{CompdbEntry{File: "a.C"}, true},
		{CompdbEntry{File: "a.c"}, false},
		{CompdbEntry{File: "a.h"}, false},
		{CompdbEntry{Command: "g++ -I. -c src/b.cc -o b.o"}, true},
		{CompdbEntry{Command: "cc -I. -c src/b.c -o b.o"}, false},
	}
	for _, c := range cases {
		if got := isCPPUnit(c.entry); got != c.want {
			t.Errorf("isCPPUnit(%+v) = %v, want %v", c.entry, got, c.want)
		}
	}
}
