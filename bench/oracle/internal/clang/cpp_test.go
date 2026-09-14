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
	if !haveTool("clang++") {
		t.Skip("clang++ not on PATH")
	}
	repo, err := filepath.Abs("../../testdata/cppclang")
	if err != nil {
		t.Fatal(err)
	}
	unit := func(src string) CompdbEntry {
		return CompdbEntry{Directory: repo, File: src, Arguments: []string{"c++", "-Wall", "-I.", "-c", src}}
	}
	out := t.TempDir()
	compdb := filepath.Join(out, "compile_commands.json")
	writeCompdb(t, compdb, []CompdbEntry{unit("main.cpp"), unit("shapes.cpp"), unit("tool.cpp"), unit("shapes.cpp")})
	if err := RunUnits(Options{Repo: repo, Lang: "cpp", Compdb: compdb, Out: out}); err != nil {
		t.Fatalf("RunUnits: %v", err)
	}
	shards, err := LoadShards(filepath.Join(out, "clang-shards"))
	if err != nil {
		t.Fatal(err)
	}
	for i, s := range shards {
		if s.Failed {
			t.Fatalf("unit %d: clang++ rejected it: %s", i, s.Stderr)
		}
		if !s.CXX {
			t.Errorf("unit %d: a .cpp entry must run the C++ binary", i)
		}
	}
	return shards
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
		// O10 builds no class hierarchy over it.
		{"main.cpp", 25, 10, "virtual", "main", "shapes.cpp:13", "method"},
		// The same rule inside the header's inline method (this->area()).
		{"shapes.h", 9, 32, "virtual", "Shape::twice", "shapes.cpp:13", "method"},
		// Circle::area does not repeat the `virtual` keyword, and the
		// dump prints only what was written: the call reads as an
		// ordinary member call. The target is the same method either way.
		{"main.cpp", 28, 10, "static", "main", "shapes.cpp:23", "method"},
		{"main.cpp", 29, 10, "static", "main", "shapes.cpp:23", "method"},
		// The operator applied by symbol is the free operator function.
		{"main.cpp", 32, 25, "operator", "main", "shapes.cpp:27", "function"},
		// A method and a `this->` call, both inside an unnamed namespace,
		// and the method the dump declares below the body that calls it.
		{"main.cpp", 35, 10, "static", "main", "main.cpp:6", "method"},
		{"main.cpp", 6, 24, "static", "Runner::run", "main.cpp:7", "method"},
		{"main.cpp", 36, 10, "static", "main", "main.cpp:12", "function"},
		// The unnamed namespace's helper and the file-static one resolve
		// in their own unit, as C's statics do.
		{"shapes.cpp", 14, 12, "static", "Shape::area", "shapes.cpp:5", "function"},
		{"shapes.cpp", 18, 12, "static", "Shape::units", "shapes.cpp:9", "function"},
		// tool.cpp is the second program: the same header, the same
		// inline method, the same free function.
		{"tool.cpp", 5, 12, "static", "main", "shapes.h:9", "method"},
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
	inline := get("main.cpp", 26, 10, "static")
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
