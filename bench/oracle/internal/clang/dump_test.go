package clang

import (
	"strings"
	"testing"
)

func readCalls(t *testing.T, doc string) []Call {
	t.Helper()
	s, err := ReadDump(strings.NewReader(doc), "/fx", "/fx")
	if err != nil {
		t.Fatalf("ReadDump: %v", err)
	}
	return s.Calls
}

func callByName(t *testing.T, calls []Call, name string) Call {
	t.Helper()
	for _, c := range calls {
		if c.Callee == name {
			return c
		}
	}
	t.Fatalf("no call to %q among %+v", name, calls)
	return Call{}
}

// TestLocationCarry exercises the dumper's omission rule on hand-built
// JSON: a location that omits "file", one that also omits "line", and
// one whose "includedFrom" must not move either — three calls hung off
// one FunctionDecl whose own "loc" seeds the carried state.
func TestLocationCarry(t *testing.T) {
	const doc = `{
	  "kind": "FunctionDecl", "name": "f",
	  "loc": {"offset": 1, "file": "main.c", "line": 5, "col": 1},
	  "inner": [
	    {"kind": "CompoundStmt", "inner": [
	      {"kind": "CallExpr", "inner": [
	        {"kind": "DeclRefExpr", "range": {"begin": {"offset": 10, "line": 6, "col": 3}},
	         "referencedDecl": {"kind": "FunctionDecl", "name": "g"}}
	      ]},
	      {"kind": "CallExpr", "inner": [
	        {"kind": "DeclRefExpr", "range": {"begin": {"offset": 20, "col": 9}},
	         "referencedDecl": {"kind": "FunctionDecl", "name": "h"}}
	      ]},
	      {"kind": "CallExpr", "inner": [
	        {"kind": "DeclRefExpr", "range": {"begin": {"offset": 30, "col": 12, "includedFrom": {"file": "other.c"}}},
	         "referencedDecl": {"kind": "FunctionDecl", "name": "i"}}
	      ]}
	    ]}
	  ]
	}`
	calls := readCalls(t, doc)

	// g's location omits "file": it must carry main.c from f's own loc.
	g := callByName(t, calls, "g")
	if g.Site.Path != "main.c" || g.Site.Line != 6 || g.Col != 3 {
		t.Errorf("g (omitted file): %+v", g)
	}

	// h's location omits both "file" and "line": both carry forward
	// from g's update (main.c, line 6).
	h := callByName(t, calls, "h")
	if h.Site.Path != "main.c" || h.Site.Line != 6 || h.Col != 9 {
		t.Errorf("h (omitted line): %+v", h)
	}

	// i's location omits "file" and carries an "includedFrom" pointing
	// elsewhere: that must not move the carried file away from main.c.
	i := callByName(t, calls, "i")
	if i.Site.Path != "main.c" || i.Site.Line != 6 || i.Col != 12 {
		t.Errorf("i (includedFrom must not move state): %+v", i)
	}
}

// TestMacroSpellingVersusExpansion covers rule 4: a callee written as a
// macro argument sits at its spelling (mode "static"); one written in a
// macro's body sits at the expansion (mode "macro"), and its spelling
// (used for site identity) is tracked separately.
func TestMacroSpellingVersusExpansion(t *testing.T) {
	const doc = `{
	  "kind": "FunctionDecl", "name": "f",
	  "loc": {"offset": 1, "file": "main.c", "line": 1, "col": 1},
	  "inner": [
	    {"kind": "CompoundStmt", "inner": [
	      {"kind": "CallExpr", "inner": [
	        {"kind": "DeclRefExpr", "range": {"begin": {
	            "spellingLoc": {"offset": 5, "file": "main.c", "line": 7, "col": 5},
	            "expansionLoc": {"offset": 6, "file": "main.c", "line": 8, "col": 1, "isMacroArgExpansion": true}
	          }},
	         "referencedDecl": {"kind": "FunctionDecl", "name": "argcall"}}
	      ]},
	      {"kind": "CallExpr", "inner": [
	        {"kind": "DeclRefExpr", "range": {"begin": {
	            "spellingLoc": {"offset": 7, "file": "hdr.h", "line": 2, "col": 3},
	            "expansionLoc": {"offset": 8, "file": "main.c", "line": 9, "col": 2}
	          }},
	         "referencedDecl": {"kind": "FunctionDecl", "name": "bodycall"}}
	      ]}
	    ]}
	  ]
	}`
	calls := readCalls(t, doc)

	arg := callByName(t, calls, "argcall")
	if arg.Mode != "static" || arg.Site.Path != "main.c" || arg.Site.Line != 7 || arg.Col != 5 {
		t.Errorf("macro argument call: %+v", arg)
	}
	if arg.Spell.Path != "main.c" || arg.Spell.Line != 7 || arg.SpellCol != 5 {
		t.Errorf("macro argument call's spelling should equal its site: %+v", arg)
	}

	body := callByName(t, calls, "bodycall")
	if body.Mode != "macro" || body.Site.Path != "main.c" || body.Site.Line != 9 || body.Col != 2 {
		t.Errorf("macro body call: %+v", body)
	}
	if body.Spell.Path != "hdr.h" || body.Spell.Line != 2 || body.SpellCol != 3 {
		t.Errorf("macro body call's spelling should be tracked separately: %+v", body)
	}
}

// TestNormalizePaths covers rule 3: a clang-spelled file is joined
// against the compile entry's directory (or taken as absolute), cleaned,
// and kept only if it lies under the repo.
func TestNormalizePaths(t *testing.T) {
	cases := []struct {
		name           string
		raw, dir, repo string
		wantRel        string
		wantInRepo     bool
	}{
		{"dot-relative", "./api.h", "/fx", "/fx", "api.h", true},
		{"escapes the repo", "../outside.h", "/fx", "/fx", "", false},
		{"absolute inside repo", "/fx/src/a.h", "/fx", "/fx", "src/a.h", true},
		{"absolute outside repo", "/etc/a.h", "/fx", "/fx", "", false},
		{"relative under a build subdir", "../src/main.c", "/fx/build", "/fx", "src/main.c", true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			rel, ok := normalize(c.raw, c.dir, c.repo)
			if ok != c.wantInRepo || (ok && rel != c.wantRel) {
				t.Errorf("normalize(%q, %q, %q) = (%q, %v), want (%q, %v)", c.raw, c.dir, c.repo, rel, ok, c.wantRel, c.wantInRepo)
			}
		})
	}
}

// TestPseudoBufferRedirectsToExpansion covers defect 1: a chosen
// position (here, a macro-argument expansion's spelling) that lies in a
// clang pseudo-buffer — the synthetic result of token pasting, never a
// real file — is never usable, so the rule falls back to the expansion,
// mode "macro"; the pseudo path never enters Files.
func TestPseudoBufferRedirectsToExpansion(t *testing.T) {
	const doc = `{
	  "kind": "FunctionDecl", "name": "f",
	  "loc": {"offset": 1, "file": "main.c", "line": 1, "col": 1},
	  "inner": [
	    {"kind": "CompoundStmt", "inner": [
	      {"kind": "CallExpr", "inner": [
	        {"kind": "DeclRefExpr", "range": {"begin": {
	            "spellingLoc": {"offset": 5, "file": "<scratch space>", "line": 9, "col": 1},
	            "expansionLoc": {"offset": 6, "file": "main.c", "line": 4, "col": 10, "isMacroArgExpansion": true}
	          }},
	         "referencedDecl": {"kind": "FunctionDecl", "name": "pasted"}}
	      ]}
	    ]}
	  ]
	}`
	s, err := ReadDump(strings.NewReader(doc), "/fx", "/fx")
	if err != nil {
		t.Fatalf("ReadDump: %v", err)
	}
	c := callByName(t, s.Calls, "pasted")
	if c.Mode != "macro" || c.Site.Path != "main.c" || c.Site.Line != 4 || c.Col != 10 {
		t.Errorf("pseudo-buffer spelling should redirect to the expansion: %+v", c)
	}
	for _, f := range s.Files {
		if strings.HasPrefix(f, "<") {
			t.Errorf("a pseudo-buffer must never enter Files: %v", s.Files)
		}
	}
}

// TestCalleeThatIsItselfACallIsRecorded covers defect 2: a callee that
// is itself a call (`get_fn()(2)`) is two sites — the inner call,
// recorded in its own right rather than dropped mid-peel, and the outer
// call through its result, dynamic — both attributed to the enclosing
// function.
func TestCalleeThatIsItselfACallIsRecorded(t *testing.T) {
	const doc = `{
	  "kind": "FunctionDecl", "name": "use",
	  "loc": {"offset": 1, "file": "main.c", "line": 1, "col": 1},
	  "inner": [
	    {"kind": "CompoundStmt", "inner": [
	      {"kind": "CallExpr", "range": {"begin": {"offset": 10, "line": 5, "col": 3}}, "inner": [
	        {"kind": "CallExpr", "range": {"begin": {"offset": 10, "col": 3}}, "inner": [
	          {"kind": "DeclRefExpr", "range": {"begin": {"offset": 10, "col": 3}},
	           "referencedDecl": {"kind": "FunctionDecl", "name": "get_fn"}}
	        ]},
	        {"kind": "IntegerLiteral", "range": {"begin": {"offset": 20, "col": 12}}}
	      ]}
	    ]}
	  ]
	}`
	s, err := ReadDump(strings.NewReader(doc), "/fx", "/fx")
	if err != nil {
		t.Fatalf("ReadDump: %v", err)
	}
	if len(s.Calls) != 2 {
		t.Fatalf("want 2 calls (inner static, outer dynamic), got %+v", s.Calls)
	}
	inner := callByName(t, s.Calls, "get_fn")
	if inner.Mode != "static" || inner.Caller != "use" || inner.Site.Line != 5 || inner.Col != 3 {
		t.Errorf("inner call: %+v", inner)
	}
	var outer Call
	found := false
	for _, c := range s.Calls {
		if c.Mode == "dynamic" {
			outer, found = c, true
		}
	}
	if !found {
		t.Fatalf("outer call (through get_fn's result) not recorded: %+v", s.Calls)
	}
	if outer.Caller != "use" || outer.Site != inner.Site || outer.Col != inner.Col {
		t.Errorf("outer call should share the inner's (site, spelling) position: %+v vs %+v", outer, inner)
	}
}

// TestReadDumpMalformedReturnsError: a dump that does not parse returns
// an error, never a partial shard.
func TestReadDumpMalformedReturnsError(t *testing.T) {
	const truncated = `{"kind": "FunctionDecl", "name": "f", "inner": [`
	s, err := ReadDump(strings.NewReader(truncated), "/fx", "/fx")
	if err == nil {
		t.Fatalf("want an error on truncated JSON, got shard %+v", s)
	}
	if s != nil {
		t.Fatalf("want a nil shard on error, got %+v", s)
	}
}
