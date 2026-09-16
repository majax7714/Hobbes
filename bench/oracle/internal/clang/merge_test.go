package clang

import (
	"testing"

	"github.com/majax7714/Hobbes/bench/oracle/internal/edges"
)

func siteAt(t *testing.T, out *edges.OracleExport, path string, line int) edges.Site {
	t.Helper()
	for _, s := range out.Sites {
		if s.Pos.Path == path && s.Pos.Line == line {
			return s
		}
	}
	t.Fatalf("no site at %s:%d among %+v", path, line, out.Sites)
	return edges.Site{}
}

func hasPos(targets []edges.Target, p edges.Pos) bool {
	for _, t := range targets {
		if t.Pos == p {
			return true
		}
	}
	return false
}

// TestMergeSeveralExternalDefs covers rule 6's external join: several
// units defining a name resolve to the calling unit's own definition
// when it has one, and to no targets ("link-ambiguous") when it does
// not.
func TestMergeSeveralExternalDefs(t *testing.T) {
	c := &Shard{File: "c.c", Files: []string{"c.c"},
		Decls: []Decl{{Name: "multi", Body: true, InRepo: true, Pos: edges.Pos{Path: "c.c", Line: 1}}},
		Calls: []Call{{Site: edges.Pos{Path: "c.c", Line: 2}, Col: 3, Spell: edges.Pos{Path: "c.c", Line: 2}, SpellCol: 3, Caller: "cf", Mode: "static", Callee: "multi"}},
	}
	d := &Shard{File: "d.c", Files: []string{"d.c"},
		Decls: []Decl{{Name: "multi", Body: true, InRepo: true, Pos: edges.Pos{Path: "d.c", Line: 1}}},
	}
	e := &Shard{File: "e.c", Files: []string{"e.c"},
		Calls: []Call{{Site: edges.Pos{Path: "e.c", Line: 5}, Col: 1, Spell: edges.Pos{Path: "e.c", Line: 5}, SpellCol: 1, Caller: "ef", Mode: "static", Callee: "multi"}},
	}
	out := Merge([]*Shard{c, d, e}, "")

	cSite := siteAt(t, out, "c.c", 2)
	if len(cSite.Targets) != 1 || !hasPos(cSite.Targets, edges.Pos{Path: "c.c", Line: 1}) {
		t.Errorf("c.c:2 should resolve to its own definition: %+v", cSite.Targets)
	}
	eSite := siteAt(t, out, "e.c", 5)
	if len(eSite.Targets) != 0 {
		t.Errorf("e.c:5 has no own definition among several: want link-ambiguous, got %+v", eSite.Targets)
	}
	if out.Coverage["sites_link_ambiguous"] != 1 {
		t.Errorf("coverage: %v", out.Coverage)
	}
}

// TestMergeKeysOverloadsByMangledName covers ADR-113's join key: two C++
// declarations sharing a name are one entity each, told apart by their
// mangled names, so a call resolves to its own overload's definition and
// never to both (which C's name join would have called link-ambiguous).
func TestMergeKeysOverloadsByMangledName(t *testing.T) {
	decl := func(mangled string, line int) Decl {
		return Decl{Name: "f", Mangled: mangled, Kind: "function", Body: true, InRepo: true,
			Pos: edges.Pos{Path: "over.cpp", Line: line}}
	}
	call := func(mangled string, line int) Call {
		return Call{Site: edges.Pos{Path: "over.cpp", Line: line}, Col: 5,
			Spell: edges.Pos{Path: "over.cpp", Line: line}, SpellCol: 5,
			Caller: "use", Mode: "static", Callee: mangled, CalleeName: "f"}
	}
	s := &Shard{File: "over.cpp", Files: []string{"over.cpp"},
		Decls: []Decl{decl("_Z1fi", 1), decl("_Z1fd", 2)},
		Calls: []Call{call("_Z1fi", 10), call("_Z1fd", 11)},
	}
	out := Merge([]*Shard{s}, "")

	for line, want := range map[int]edges.Pos{10: {Path: "over.cpp", Line: 1}, 11: {Path: "over.cpp", Line: 2}} {
		site := siteAt(t, out, "over.cpp", line)
		if len(site.Targets) != 1 || !hasPos(site.Targets, want) {
			t.Errorf("over.cpp:%d should resolve to %s alone: %+v", line, want.Key(), site.Targets)
		}
		if len(site.Targets) == 1 && site.Targets[0].Name != "f" {
			t.Errorf("over.cpp:%d: a target reports the name as written, not the mangling: %+v", line, site.Targets[0])
		}
	}
	if out.Coverage["sites_static"] != 2 || out.Coverage["sites_link_ambiguous"] != 0 {
		t.Errorf("coverage: %v", out.Coverage)
	}
}

// TestDeclKeySpelling covers ADR-113 §3's key, as the amendment spells
// it: the mangled name where the front end gives one, else the name
// qualified by the declaration's class (a class template's pattern
// members, which carry no mangling), else the bare name (`extern "C"`,
// `main`).
func TestDeclKeySpelling(t *testing.T) {
	cases := []struct {
		what string
		d    Decl
		want string
	}{
		{"a pattern member of A", Decl{Name: "format_as", Class: "A", Kind: "method"}, "A::format_as"},
		{"a pattern member of B", Decl{Name: "format_as", Class: "B", Kind: "method"}, "B::format_as"},
		{"its specialisation", Decl{Name: "format_as", Class: "A", Mangled: "_ZN1AIiE9format_asEi"}, "_ZN1AIiE9format_asEi"},
		{"an extern \"C\" function", Decl{Name: "shared_entry"}, "shared_entry"},
		{"main", Decl{Name: "main"}, "main"},
	}
	for _, c := range cases {
		if got := declKey(c.d); got != c.want {
			t.Errorf("%s: declKey = %q, want %q", c.what, got, c.want)
		}
	}
	if declKey(cases[0].d) == declKey(cases[1].d) {
		t.Errorf("two classes' same-named members must not share a key: %q", declKey(cases[0].d))
	}
}

// TestMergeUndefinedVersusExternal covers the two "no definition" cases:
// declared in the repo (undefined) versus declared only implicitly
// (external, ADR-110's builtin case).
func TestMergeUndefinedVersusExternal(t *testing.T) {
	s := &Shard{File: "a.c", Files: []string{"a.c", "a.h"},
		Decls: []Decl{
			{Name: "missing", Body: false, InRepo: true, Implicit: false, Pos: edges.Pos{Path: "a.h", Line: 1}},
			{Name: "__builtin_x", Body: false, InRepo: true, Implicit: true, Pos: edges.Pos{Path: "a.c", Line: 9}},
		},
		Calls: []Call{
			{Site: edges.Pos{Path: "a.c", Line: 10}, Col: 1, Spell: edges.Pos{Path: "a.c", Line: 10}, SpellCol: 1, Mode: "static", Callee: "missing"},
			{Site: edges.Pos{Path: "a.c", Line: 11}, Col: 1, Spell: edges.Pos{Path: "a.c", Line: 11}, SpellCol: 1, Mode: "static", Callee: "__builtin_x"},
		},
	}
	out := Merge([]*Shard{s}, "")

	miss := siteAt(t, out, "a.c", 10)
	if len(miss.Targets) != 0 {
		t.Errorf("declared-in-repo, no definition: want undefined (no targets), got %+v", miss.Targets)
	}
	bi := siteAt(t, out, "a.c", 11)
	if len(bi.Targets) != 1 || !bi.Targets[0].External || bi.Targets[0].Name != "__builtin_x" {
		t.Errorf("implicit-only declaration: want one external target, got %+v", bi.Targets)
	}
	if out.Coverage["sites_undefined"] != 1 || out.Coverage["sites_external"] != 1 {
		t.Errorf("coverage: %v", out.Coverage)
	}
}

// TestMergeStaticWithNoInRepoTraceIsExternal covers defect 3: a static
// function with no in-repo definition and no in-repo declaration (a
// system header's `static inline`, ADR-110's __bswap_16 example) is
// external, not link-ambiguous — distinct from a static function the
// repo does declare but never define, which is undefined.
func TestMergeStaticWithNoInRepoTraceIsExternal(t *testing.T) {
	s := &Shard{File: "a.c", Files: []string{"a.c"},
		Decls: []Decl{
			// __bswap_16: static, its only decl/def is the header, out of repo.
			{Name: "__bswap_16", Static: true, Body: true, InRepo: false, Pos: edges.Pos{Path: "byteswap.h", Line: 32}},
			// helper: static, declared in the repo (a prototype) but never defined.
			{Name: "helper", Static: true, Body: false, InRepo: true, Pos: edges.Pos{Path: "a.h", Line: 2}},
		},
		Calls: []Call{
			{Site: edges.Pos{Path: "a.c", Line: 10}, Col: 1, Spell: edges.Pos{Path: "a.c", Line: 10}, SpellCol: 1, Mode: "macro", Callee: "__bswap_16"},
			{Site: edges.Pos{Path: "a.c", Line: 11}, Col: 1, Spell: edges.Pos{Path: "a.c", Line: 11}, SpellCol: 1, Mode: "static", Callee: "helper"},
		},
	}
	out := Merge([]*Shard{s}, "")

	ext := siteAt(t, out, "a.c", 10)
	if len(ext.Targets) != 1 || !ext.Targets[0].External || ext.Targets[0].Name != "__bswap_16" {
		t.Errorf("static, no in-repo trace: want one external target, got %+v", ext.Targets)
	}
	undef := siteAt(t, out, "a.c", 11)
	if len(undef.Targets) != 0 {
		t.Errorf("static, declared in repo but never defined: want undefined (no targets), got %+v", undef.Targets)
	}
	if out.Coverage["sites_external"] != 1 || out.Coverage["sites_undefined"] != 1 || out.Coverage["sites_link_ambiguous"] != 0 {
		t.Errorf("coverage: %v", out.Coverage)
	}
}

// TestSiteIdentityAddsModeAndCallee covers defect 2's identity rule: two
// calls sharing one (site, spelling) position — a callee that is itself
// a call, and the call through its result — stay distinct sites because
// identity also keys on mode and callee name.
func TestSiteIdentityAddsModeAndCallee(t *testing.T) {
	pos := edges.Pos{Path: "a.c", Line: 12}
	s := &Shard{File: "a.c", Files: []string{"a.c"},
		Decls: []Decl{{Name: "get_fn", Body: true, InRepo: true, Pos: edges.Pos{Path: "a.c", Line: 8}}},
		Calls: []Call{
			{Site: pos, Col: 13, Spell: pos, SpellCol: 13, Caller: "use", Mode: "static", Callee: "get_fn"},
			{Site: pos, Col: 13, Spell: pos, SpellCol: 13, Caller: "use", Mode: "dynamic"},
		},
	}
	out := Merge([]*Shard{s}, "")

	var got []edges.Site
	for _, site := range out.Sites {
		if site.Pos == pos && site.Col == 13 {
			got = append(got, site)
		}
	}
	if len(got) != 2 {
		t.Fatalf("want 2 distinct sites at the shared position, got %d: %+v", len(got), got)
	}
	modes := map[string]bool{got[0].Mode: true, got[1].Mode: true}
	if !modes["static"] || !modes["dynamic"] {
		t.Errorf("want one static and one dynamic site, got %+v", got)
	}
}

// TestMergeTUSplit covers a site two units resolve differently: a
// header's internal-linkage function, included by two units that each
// define their own — the same call site keeps every target and counts
// tu-split, never picking one arbitrarily.
func TestMergeTUSplit(t *testing.T) {
	shared := edges.Pos{Path: "shared.h", Line: 3}
	f := &Shard{File: "f.c", Files: []string{"f.c", "shared.h"},
		Decls: []Decl{{Name: "choose", Static: true, Body: true, InRepo: true, Pos: edges.Pos{Path: "f.c", Line: 1}}},
		Calls: []Call{{Site: shared, Col: 5, Spell: shared, SpellCol: 5, Caller: "pick", Mode: "static", Callee: "choose"}},
	}
	g := &Shard{File: "g.c", Files: []string{"g.c", "shared.h"},
		Decls: []Decl{{Name: "choose", Static: true, Body: true, InRepo: true, Pos: edges.Pos{Path: "g.c", Line: 1}}},
		Calls: []Call{{Site: shared, Col: 5, Spell: shared, SpellCol: 5, Caller: "pick", Mode: "static", Callee: "choose"}},
	}
	out := Merge([]*Shard{f, g}, "")

	if len(out.Sites) != 1 {
		t.Fatalf("f.c and g.c share one physical call site: want 1 merged site, got %d: %+v", len(out.Sites), out.Sites)
	}
	s := out.Sites[0]
	if len(s.Targets) != 2 || !hasPos(s.Targets, edges.Pos{Path: "f.c", Line: 1}) || !hasPos(s.Targets, edges.Pos{Path: "g.c", Line: 1}) {
		t.Errorf("tu-split should keep both units' own definitions: %+v", s.Targets)
	}
	if out.Coverage["sites_tu_split"] != 1 || out.Coverage["sites_static"] != 0 {
		t.Errorf("coverage: %v", out.Coverage)
	}
}
