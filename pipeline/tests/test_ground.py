"""Grounder v0 (Calvin M0 step 3): placement of every fill shape, the refusals, exact-or-NULL resolution by class in Go / Python / JS, the re-export and module-value rules, a diff as fills round-tripping to the commit, and determinism — on a synthetic ledger over a temporary git repo."""
import json
import shutil
import subprocess

import pytest

from hobbes.derive import ground as G
from hobbes.derive import holes
from hobbes.derive import template as T

APP = """// Package app is the app.
package app

import "fmt"

// Options selects one run.
type Options struct {
\tRepo string
}

// Run runs one cell.
func Run(o Options) error {
\tfmt.Println("go-rta", o.Repo)
\treturn nil
}

func helper() int { Run(Options{}); return 1 }
"""
MAIN = """package main

import "example.com/x/internal/app"

func main() {
\trunGoRTA()
}

func runGoRTA() {
\tapp.Run(app.Options{Repo: "."})
}
"""
CORE = '''"""core"""
TABLE = {"a": 1}


class Base:
    def ping(self):
        return 1


def derive(x):
    return x
'''
INIT = "from .core import derive\n"
USE = '''from pkg import derive
from pkg import core


def go():
    return derive(core.TABLE.get("a"))
'''
LIB = "export function helper() { return 1 }\n"
GO_MOD = "module example.com/x\n\ngo 1.22\n"


def _git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    for rel, text in {"internal/app/app.go": APP, "cmd/main.go": MAIN, "go.mod": GO_MOD, "pkg/__init__.py": INIT, "pkg/core.py": CORE, "pkg/use.py": USE, "web/lib.mjs": LIB}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "one")
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD").strip()


def ledger(sha):
    ev = lambda p, l: [{"lane": "scip", "line": l, "path": p}]
    graph = {
        "sha": sha, "schema_version": 4, "built_by": {"sha": "abc"}, "containment": {"all_contained": True},
        "nodes": [{"id": "internal/app/app", "kind": "module", "path": "internal/app/app.go"},
                  {"id": "cmd/main", "kind": "module", "path": "cmd/main.go"},
                  {"id": "pkg", "kind": "package", "path": "pkg/__init__.py"},
                  {"id": "pkg.core", "kind": "module", "path": "pkg/core.py"},
                  {"id": "pkg.use", "kind": "module", "path": "pkg/use.py"},
                  {"id": "web/lib", "kind": "module", "path": "web/lib.mjs"}],
        "symbols": [
            {"id": "internal/app/app.Options", "module": "internal/app/app", "name": "Options", "qualname": "Options", "kind": "type", "line": 7, "end_line": 9},
            {"id": "internal/app/app.Run", "module": "internal/app/app", "name": "Run", "qualname": "Run", "kind": "function", "line": 12, "end_line": 15},
            {"id": "internal/app/app.helper", "module": "internal/app/app", "name": "helper", "qualname": "helper", "kind": "function", "line": 17, "end_line": 17},
            {"id": "cmd/main.main", "module": "cmd/main", "name": "main", "qualname": "main", "kind": "function", "line": 5, "end_line": 7},
            {"id": "cmd/main.runGoRTA", "module": "cmd/main", "name": "runGoRTA", "qualname": "runGoRTA", "kind": "function", "line": 9, "end_line": 11},
            {"id": "pkg.core.Base", "module": "pkg.core", "name": "Base", "qualname": "Base", "kind": "class", "line": 5, "end_line": 7},
            {"id": "pkg.core.Base.ping", "module": "pkg.core", "name": "ping", "qualname": "Base.ping", "kind": "method", "line": 6, "end_line": 7},
            {"id": "pkg.core.derive", "module": "pkg.core", "name": "derive", "qualname": "derive", "kind": "function", "line": 10, "end_line": 11},
            {"id": "pkg.use.go", "module": "pkg.use", "name": "go", "qualname": "go", "kind": "function", "line": 5, "end_line": 6},
            {"id": "web/lib.helper", "module": "web/lib", "name": "helper", "qualname": "helper", "kind": "function", "line": 1, "end_line": 1},
        ],
        "symbol_edges": [
            {"from": "cmd/main.main", "to": "cmd/main.runGoRTA", "type": "calls", "tier": "semantic", "evidence": ev("cmd/main.go", 6)},
            {"from": "cmd/main.runGoRTA", "to": "internal/app/app.Run", "type": "calls", "tier": "semantic", "evidence": ev("cmd/main.go", 10)},
            {"from": "internal/app/app.helper", "to": "internal/app/app.Run", "type": "calls", "tier": "semantic", "evidence": ev("internal/app/app.go", 17)},
        ],
        "module_edges": [],
    }
    return T.Ledger(graph, {"tests": []})


def template(L, root, task="Change `runGoRTA`."):
    return T.build_template(task, L, root, None)


def hole(t, typ, path=None):
    return next(h for h in t["holes"] if h["type"] == typ and (path is None or (h.get("span") or {}).get("path") == path))


def applies(root, sha, diff):
    _git(root, "checkout", "-q", "--force", sha)
    return subprocess.run(["git", "apply", "--check", "-"], cwd=root, input=diff, capture_output=True, text=True).returncode == 0


def test_placement_span_insertion_deletion_new_file_and_diff_applies(repo):
    root, sha = repo
    L = ledger(sha)
    t = template(L, root)
    body = hole(t, "BODY", "cmd/main.go")
    assert body["provenance"]["symbol"] == "cmd/main.runGoRTA"
    unchanged = {h["id"]: "unchanged" for h in t["holes"] if h["type"] in ("SIGNATURE", "BODY")}
    fills = {"fills": {
        **unchanged,
        body["id"]: {"code": "func runGoRTA() {\n\tapp.Run(app.Options{Repo: \"x\"})\n}\n"},
        hole(t, "FREEFORM")["id"]: [
            {"code": "// a comment before main\n", "span": {"path": "cmd/main.go", "start": 5, "end": 4}},   # insertion before line 5
            {"code": "", "span": {"path": "internal/app/app.go", "start": 17, "end": 17}},                 # a pure deletion: no lines
            {"code": "package other\n", "span": {"path": "cmd/other.go", "start": 1, "end": 0}},          # a new file
        ]}, "patterns": {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}}
    g = G.ground(t, fills, L, root)
    assert g["unfilled"] == [] and g["refused"] == []
    assert g["post"]["cmd/main.go"].splitlines()[4] == "// a comment before main" and 'Repo: "x"' in g["post"]["cmd/main.go"]
    assert "helper" not in g["post"]["internal/app/app.go"] and g["post"]["internal/app/app.go"].count("\n") == APP.count("\n") - 1
    assert g["post"]["cmd/other.go"] == "package other\n" and next(f for f in g["files"] if f["path"] == "cmd/other.go")["created"]
    assert "new file mode 100644" in g["diff"] and applies(root, sha, g["diff"])
    assert {e["placement"] for e in g["edits"]} == {"span", "freeform span"}
    assert g["outside_partition"] == 1, "the new file is outside the partition; the write is advisory in M0 and counted"


def test_overlap_unfilled_and_closed_are_reported_not_merged(repo):
    root, sha = repo
    L = ledger(sha)
    t = template(L, root)
    body = hole(t, "BODY", "cmd/main.go")
    sp = body["span"]
    ff = hole(t, "FREEFORM")["id"]
    fills = {"fills": {ff: {"code": "x\n", "span": {"path": sp["path"], "start": sp["start"] + 1, "end": sp["start"] + 1}},
                       body["id"]: {"code": "func runGoRTA() {}\n"}}}
    g = G.ground(t, fills, L, root)
    assert [r["hole"] for r in g["refused"]] == [f"{ff}[0]"] and "overlaps" in g["refused"][0]["reason"]
    assert set(g["unfilled"]) >= {h["id"] for h in t["holes"] if h["type"] == "MODULE_REGION" and h.get("closed") is None}, "silence on a site is a defect (I4), not an answer"
    # a function SIGNATURE = unchanged closes its CALLER_UPDATEs; a fill for one is ignored and reported
    t2 = template(L, root, "Change `Run`.")
    sig = next(h for h in t2["holes"] if h["type"] == "SIGNATURE" and h["provenance"]["symbol"] == "internal/app/app.Run")
    callers = [h for h in t2["holes"] if h["type"] == "CALLER_UPDATE" and h["provenance"]["callee"] == "internal/app/app.Run"]
    outside = next(h for h in callers if h["span"]["path"] == "cmd/main.go")
    assert outside["closed"]["reason"].startswith("partition"), "a caller outside the write partition arrives closed"
    caller = next(h for h in callers if h["span"]["path"] == "internal/app/app.go")
    g2 = G.ground(t2, {"fills": {sig["id"]: "unchanged", caller["id"]: {"decision": "yes", "reason": "r", "body": "func helper() int { return 2 }\n"}}}, L, root)
    assert caller["id"] in g2["closed_by_prune"] and g2["ignored_closed"][0]["hole"] == caller["id"]
    assert g2["edits"] == []


def test_go_resolution_classes_exact_or_null(repo):
    root, sha = repo
    L = ledger(sha)
    t = template(L, root, "Change `Run`.")
    body = next(h for h in t["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "internal/app/app.Run")
    code = """func Run(o Options) error {
\tn := len(o.Repo)
\tfmt.Println("go-rta", n)
\thelper()
\tfresh()
\tf := func() {}
\tf()
\to.Repo.Len()
\thelpr()
\tzqxFrobnicate()
\treturn nil
}

func fresh() {}
"""
    g = G.ground(t, {"fills": {body["id"]: {"code": code}}}, L, root)
    s0 = body["span"]["start"]
    by = {(r["term"], r["line"] - s0 + 1): r["class"] for r in g["refs"]}
    assert by[("len", 2)] == "builtin" and by[("fmt.Println", 3)] == "external"
    assert by[("helper", 4)] == "in-graph" and by[("fresh", 5)] == "gensym" and by[("f", 7)] == "local"
    assert by[("<expr>.Len", 8)] == "expr"
    assert [(n["term"], n["null_class"]) for n in g["null"]] == [("helpr", "near-miss"), ("zqxFrobnicate", "invented")]
    assert g["null"][0]["nearest"][0] == "helper" and g["null"][0]["declared"] is False
    assert "fresh" in g["gensyms"] and g["hsr"] == round(2 / (1 + 2), 4)
    # a declared new term resolves as a gensym class `new`, never as invented
    u = next(h for h in t["holes"] if h["type"] == "UNRESOLVED") if any(h["type"] == "UNRESOLVED" for h in t["holes"]) else None
    g2 = G.ground(t, {"fills": {body["id"]: {"code": code}, **({u["id"]: {"classes": {x["term"]: "new" for x in u["terms"]}}} if u else {})}}, L, root)
    assert g2["references"]["NULL"] == 2
    # an import-qualified call into a repo package resolves through go.mod, exactly
    g3 = G.ground(template(L, root, "Change `Run`."), {"fills": {hole(t, "FREEFORM")["id"]: {"code": "func runGoRTA() {\n\tapp.Run(app.Options{})\n\tapp.Rnu()\n}\n", "span": {"path": "cmd/main.go", "start": 9, "end": 11}}}}, L, root)
    got = {r["term"]: r["class"] for r in g3["refs"]}
    assert got["app.Run"] == "in-graph" and got["app.Rnu"] == "NULL"
    assert any(r["op"] == "import" and r["key"] == "example.com/x/internal/app" and r["result"] == "internal/app" for r in g3["trace"]), "the read-trace shows the go.mod lookup"


def test_null_rows_name_the_scope_a_declaration_would_bind_in(repo):
    """M0-Go WP-7a: a NULL row names where a declaration of the name would have to sit for the call to bind — the package directory of
    a bare or package-qualified Go name, the directory and type of a member on a typed receiver (adapter protocol v0.4 reads it)."""
    root, sha = repo
    L = ledger(sha)
    t = template(L, root)
    body = hole(t, "BODY", "cmd/main.go")
    code = "func runGoRTA() {\n\tlaunchAll()\n\tapp.Launch()\n\tvar o app.Options\n\to.Validate()\n}\n"
    g = G.ground(t, {"fills": {body["id"]: {"code": code}}}, L, root)
    assert {n["term"]: (n["null_class"], n["scope"]) for n in g["null"]} == {
        "launchAll": ("invented", {"dir": "cmd"}), "app.Launch": ("invented", {"dir": "internal/app"}),
        "o.Validate": ("invented", {"dir": "internal/app", "type": "Options"})}


def test_python_reexport_module_value_self_and_null(repo):
    root, sha = repo
    L = ledger(sha)
    t = template(L, root, "Change `go`.")
    body = next(h for h in t["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "pkg.use.go")
    code = '''def go():
    x = derive(1)
    core.TABLE.get("a")
    core.derive(2)
    core.derived(3)
    print(len(x))
    y = lambda: 1
    y()
    core.Base().ping()
    return x
'''
    g = G.ground(t, {"fills": {body["id"]: {"code": code}}}, L, root)
    by = {r["term"]: (r["class"], r["target"]) for r in g["refs"]}
    assert by["derive"] == ("in-graph", "pkg.core.derive"), "from pkg import derive follows the package's re-export to the symbol"
    assert any(r["op"] == "re-export" for r in g["trace"])
    assert by["core.TABLE.get"][0] == "unknown-receiver", "a module-level value lane A does not model: abstain, not NULL"
    assert by["core.derive"] == ("in-graph", "pkg.core.derive")
    assert by["core.derived"][0] == "NULL" and g["null"][0]["null_class"] == "near-miss"
    assert by["print"][0] == "builtin" and by["len"][0] == "builtin" and by["y"][0] == "local"
    assert by["<expr>.ping"][0] == "expr"
    # self.method inside the class resolves to the declared method
    t2 = template(L, root, "Change `Base`.")
    bb = next(h for h in t2["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "pkg.core.Base")
    g2 = G.ground(t2, {"fills": {bb["id"]: {"code": "class Base:\n    def ping(self):\n        return self.pong() + self.ping()\n\n    def pong(self):\n        return 2\n"}}}, L, root)
    by2 = {r["term"]: r["class"] for r in g2["refs"]}
    assert by2["self.ping"] == "in-graph" and by2["self.pong"] == "gensym" and g2["null"] == []


@pytest.mark.skipif(shutil.which("node") is None, reason="the tsextract helper needs node")
def test_js_import_builtin_and_null(repo):
    root, sha = repo
    L = ledger(sha)
    t = template(L, root, "Change `helper`.")
    fills = {"fills": {hole(t, "FREEFORM")["id"]: {"code": "import { helper } from './lib.mjs'\nexport function use() {\n  setTimeout(() => helper(), 1)\n  return helpr()\n}\n",
                                                   "span": {"path": "web/use.mjs", "start": 1, "end": 0}}}}
    g = G.ground(t, fills, L, root)
    by = {r["term"]: r["class"] for r in g["refs"]}
    assert by["helper"] == "in-graph" and by["setTimeout"] == "builtin" and by["helpr"] == "NULL"
    assert g["null"][0]["null_class"] == "near-miss"


def test_new_symbol_placements_and_covered_by(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `Run`; add mergeRanges.", L, root, None, new_terms=["mergeRanges"])
    n = hole(t, "NEW_SYMBOL")
    region = next(h for h in t["holes"] if h["type"] == "MODULE_REGION" and h["provenance"]["kind"] == "head")
    for fill, where, line in (
        ({"name": "mergeRanges", "file": "internal/app/app.go", "after_symbol": "internal/app/app.Run", "body": "func mergeRanges() {}\n"}, "after internal/app/app.Run", 17),
        ({"name": "mergeRanges", "file": "internal/app/app.go", "region": region["id"], "body": "func mergeRanges() {}\n"}, f"end of region {region['id']}", region["span"]["end"] + 1),
        ({"name": "mergeRanges", "file": "internal/app/app.go", "region": "eof", "body": "func mergeRanges() {}\n"}, "end of file", APP.count("\n") + 2),
        ({"name": "mergeRanges", "file": "internal/app/new.go", "region": "eof", "body": "package app\n\nfunc mergeRanges() {}\n"}, "end of file", 1),
    ):
        g = G.ground(json.loads(json.dumps(t)), {"fills": {n["id"]: fill}}, L, root)
        e = next(e for e in g["edits"] if e["hole"] == n["id"])
        assert e["placement"] == where, fill
        assert "func mergeRanges() {}" in g["post"][fill["file"]].splitlines()[line - 1: line + 2], fill
        assert "mergeRanges" in g["gensyms"] and g["null"] == []
    g = G.ground(json.loads(json.dumps(t)), {"fills": {n["id"]: {"name": "mergeRanges", "file": "internal/app/app.go", "after_symbol": "internal/app/app.Nope", "body": "x\n"}}}, L, root)
    assert g["refused"][0]["hole"] == n["id"] and "not in the ledger" in g["refused"][0]["errors"][0]
    g = G.ground(json.loads(json.dumps(t)), {"fills": {n["id"]: {"covered_by": [hole(t, "BODY", "internal/app/app.go")["id"]]}}}, L, root)
    assert g["edits"] == [] and g["notes"] and "carries no code" in g["notes"][0]


def test_fills_from_diff_round_trips_to_the_commit(repo):
    root, sha = repo
    L = ledger(sha)
    (root / "internal/app/app.go").write_text(APP.replace('\tfmt.Println("go-rta", o.Repo)\n', '\tfmt.Println("go-rta", o.Repo)\n\tfmt.Println("twice")\n').replace("// Package app is the app.\n", "// Package app is the app.\n// More.\n"))
    (root / "cmd/new.go").write_text("package main\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "two")
    child = _git(root, "rev-parse", "HEAD").strip()
    gold = [(p, _git(root, "show", "--format=", child, "--", p)) for p in ("internal/app/app.go", "cmd/new.go")]
    t = template(L, root, "Change `Run`.")
    doc, counts = G.fills_from_diff(t, gold, root)
    assert holes.validate_fills(t, doc) == {h["id"]: ["missing"] for h in t["holes"] if h["type"] in ("UNRESOLVED", "ANCHOR_CONFIRM")} or holes.validate_fills(t, doc) == {}
    assert counts["in_hole"] == 2 and counts["filled_BODY"] == 1 and counts["filled_MODULE_REGION"] == 1 and counts["new_file"] == 1 and "freeform" not in counts, \
        (counts, "the comment lands in the head region, the call in Run's body, the new file is its own entry")
    body = next(h for h in t["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "internal/app/app.Run")
    assert "twice" in doc["fills"][body["id"]]["code"]
    g = G.ground(template(L, root, "Change `Run`."), doc, L, root)
    for p, _ in gold:
        assert g["post"][p] == _git(root, "show", f"{child}:{p}"), p
    assert g["null"] == [] and applies(root, sha, g["diff"])


def test_deterministic_and_keyed(repo):
    root, sha = repo
    L = ledger(sha)
    t = template(L, root)
    body = hole(t, "BODY", "cmd/main.go")
    doc = {"fills": {body["id"]: {"code": "func runGoRTA() {\n\tapp.Run(app.Options{})\n}\n"}}}
    a = G.ground(json.loads(json.dumps(t)), doc, L, root)
    b = G.ground(json.loads(json.dumps(t)), doc, L, root)
    assert a["output_hash"] == b["output_hash"] and a["trace"] == b["trace"]
    assert a["key"] == {**t["key"], "grounder_version": G.GROUNDER_VERSION}


def test_an_expression_callee_is_no_reference():
    """C-63's shape: `handlers[0]()` names nothing to bind — the grounder
    reads no reference from it, while `f().m()` still yields `f` and `m`
    (the latter on the `<expr>` receiver)."""
    parsed = G._parse_python("def go(handlers, f):\n    handlers[0]()\n    f().m()\n")
    assert sorted((r.name, r.receiver) for r in parsed.refs) == [("f", None), ("m", G.EXPR)]


KINDS = """package app

import "io"

// Base is embedded.
type Base struct{}

// Ping pings.
func (b *Base) Ping() int { return 1 }

// Box embeds Base and a writer, and holds a callback.
type Box struct {
\tBase
\tio.Writer
\tName   string
\tOnDone func() int
}

// Open opens.
func (x *Box) Open() error { return nil }

// Source yields fragments.
type Source interface {
\tFragments() error
}

// Mode is a defined basic type.
type Mode int

// Label names the mode.
func (m Mode) Label() string { return "" }

var defaultBox = &Box{}
"""
USE_GO = """package app

import (
\t"fmt"
\t"io"
\tst "strings"
)

func use[T fmt.Stringer](b *Box, s Source, t T, w io.Writer, err error) {
\tb.Open()
\tb.Ping()
\tb.Write(nil)
\tb.OnDone()
\tb.Opne()
\ts.Fragments()
\tt.String()
\tw.Write(nil)
\terr.Error()
\tvar m Mode
\tm.Label()
\tm.zqxFrobnicate()
\tx := &Box{}
\tx.Open()
\ty := new(Base)
\ty.Ping()
\ty.Pnig()
\tz := makeBox()
\tz.Open()
\tdefaultBox.Open()
\tvar sb st.Builder
\tsb.Len()
\tPing()
\t_ = any(1)
}

func makeBox() *Box { return &Box{} }

func shadow() {
\tio := &Box{}
\tio.Open()
}
"""


def _at(text, needle):
    return next(i for i, line in enumerate(text.split("\n"), 1) if needle in line)


def go_ledger(root, sha):
    """The synthetic ledger plus internal/app/kinds.go — types, methods, an interface, a package-level var — committed at a new SHA."""
    (root / "internal/app/kinds.go").write_text(KINDS)
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "kinds")
    sha2 = _git(root, "rev-parse", "HEAD").strip()
    L = ledger(sha2)
    g = L.graph
    g["nodes"].append({"id": "internal/app/kinds", "kind": "module", "path": "internal/app/kinds.go"})
    k = "internal/app/kinds"
    for name, qual, kind, a, b in (("Base", "Base", "type", "type Base", "type Base"), ("Ping", "Base.Ping", "method", ") Ping()", ") Ping()"),
                                   ("Box", "Box", "type", "type Box", "\tOnDone"), ("Open", "Box.Open", "method", ") Open()", ") Open()"),
                                   ("Source", "Source", "type", "type Source", "\tFragments"), ("Mode", "Mode", "type", "type Mode", "type Mode"),
                                   ("Label", "Mode.Label", "method", ") Label()", ") Label()"), ("defaultBox", "defaultBox", "var", "var defaultBox", "var defaultBox")):
        g["symbols"].append({"id": f"{k}.{qual}", "module": k, "name": name, "qualname": qual, "kind": kind, "line": _at(KINDS, a), "end_line": _at(KINDS, b) + (1 if kind == "type" and a != b else 0)})
    ev = [{"lane": "scip", "line": 1, "path": "internal/app/app.go"}]
    for src in ("cmd/main.main", "cmd/main.runGoRTA", "internal/app/app.helper", "internal/app/app.Run"):
        g["symbol_edges"].append({"from": src, "to": f"{k}.Box.Open", "type": "calls", "tier": "semantic", "evidence": ev})
    g["symbol_edges"].append({"from": "internal/app/app.Run", "to": f"{k}.Base.Ping", "type": "calls", "tier": "semantic", "evidence": ev})
    return T.Ledger(g, {"tests": []}), sha2


def test_go_universe_is_pinned_whole():
    from hobbes.extract.tail import GO_BUILTINS
    assert len(G.GO_PREDECLARED) == 44 and G.GO_PREDECLARED >= GO_BUILTINS
    assert G.GO_PREDECLARED - GO_BUILTINS == {"any", "comparable", "false", "iota", "nil", "true"}, "go1.26.5's types.Universe, less the tail's callable list"


def test_go_rule1_typed_receivers_rule2_interfaces_and_density(repo):
    root, sha = repo
    L, sha2 = go_ledger(root, sha)
    t = template(L, root, "Change `Run`.")
    rta = {"source": "a test key", "sites": {"example.com/x/internal/app.Source.Fragments": ["(*example.com/x/internal/app.File).Fragments"]}}
    fills = {"fills": {hole(t, "FREEFORM")["id"]: {"code": USE_GO, "span": {"path": "internal/app/use.go", "start": 1, "end": 0}}}}
    g = G.ground(t, fills, L, root, rta=rta)
    by = collections_by(g["refs"])
    k = "internal/app/kinds"
    assert by["b.Open"] == ("in-graph", f"{k}.Box.Open") and by["x.Open"] == ("in-graph", f"{k}.Box.Open"), "rule 1: a parameter, &T{…}"
    assert by["y.Ping"] == ("in-graph", f"{k}.Base.Ping") and by["b.Ping"] == ("in-graph", f"{k}.Base.Ping"), "new(T); promoted through an embedded repo type"
    assert by["m.Label"] == ("in-graph", f"{k}.Mode.Label") and by["defaultBox.Open"] == ("in-graph", f"{k}.Box.Open"), "var x T; a package-level var = &T{}"
    assert by["io.Open"] == ("in-graph", f"{k}.Box.Open"), "a local declared before the call shadows the package name"
    assert by["b.Write"] == ("external", "io") and by["w.Write"] == ("external", "io") and by["sb.Len"] == ("external", "strings"), "promoted from, or typed by, a package outside the repo"
    assert by["b.OnDone"][0] == "field" and by["err.Error"][0] == "builtin" and by["any"][0] == "builtin"
    assert by["t.String"][0] == "local" and by["z.Open"][0] == "local", "a type parameter and a binding the syntax does not type abstain"
    assert by["makeBox"][0] == "gensym"
    assert by["s.Fragments"] == ("interface", f"{k}.Source.Fragments"), "rule 2: the interface method, not an implementer"
    row = next(r for r in g["refs"] if r["term"] == "s.Fragments")
    assert row["implementers"] == ["(*example.com/x/internal/app.File).Fragments"] and row["rta_key"] == "example.com/x/internal/app.Source.Fragments"
    assert [(n["term"], n["null_class"]) for n in g["null"]] == [("m.zqxFrobnicate", "invented"), ("y.Pnig", "near-miss"), ("Ping", "near-miss")], \
        "a missing method on a graph type is NULL (a defined basic type carries its declared methods only); a bare name never binds a method"
    assert by["b.Opne"] == ("external", "io"), "Box embeds io.Writer: a member the repo does not declare may be promoted from outside it — abstain, never NULL"
    assert g["hsr"] == round(3 / (by_count(g, "in-graph") + 1 + 3), 4)
    assert any(r["op"] == "type-decl" and r["key"] == "internal/app:Box" for r in g["trace"]) and any(r["op"] == "var-type" for r in g["trace"])
    # density: every judged reference carries it, from the parent graph's k; nothing outside the graph does
    D = G.density_table(L.graph)
    for r in g["refs"]:
        if r["class"] == "in-graph":
            deg = D["degree"][r["target"]]
            assert (r["density"], r["refs_in"]) == ("dense" if deg >= D["k"] else "sparse", deg), r
        elif r["class"] in ("NULL", "gensym"):
            assert r["density"] == "absent"
        elif r["class"] == "interface":
            assert r["density"] in ("dense", "sparse") and r["refs_in"] == D["degree"][f"{k}.Source"]
        else:
            assert r["density"] is None, r
    assert D["k"] == 1 and g["density"]["k"] == 1, "18 symbols, the third's in-degree 0: k floors at 1"
    assert by_row(g, "b.Open")["density"] == "dense" and by_row(g, "y.Ping")["density"] == "dense" and by_row(g, "m.Label")["density"] == "sparse"
    assert sum(g["density"]["counts"].values()) == sum(by_count(g, c) for c in G.DENSITY_CLASSES)
    # an interface method the diff itself declares is new: a gensym, not rule 2
    src = hole(t, "FREEFORM")["id"]
    a, b = _at(KINDS, "type Source"), _at(KINDS, "type Source") + 2
    g2 = G.ground(template(L, root, "Change `Run`."), {"fills": {src: [
        {"code": "type Source interface {\n\tFragments() error\n\tClose() error\n}\n", "span": {"path": "internal/app/kinds.go", "start": a, "end": b}},
        {"code": "package app\n\nfunc use2(s Source) {\n\ts.Close()\n\ts.Fragments()\n}\n", "span": {"path": "internal/app/use2.go", "start": 1, "end": 0}}]}}, L, root)
    by2 = collections_by(g2["refs"])
    assert by2["s.Close"] == ("gensym", "Source.Close") and by2["s.Fragments"][0] == "interface" and g2["null"] == []
    assert next(r for r in g2["refs"] if r["term"] == "s.Fragments")["implementers"] is None, "no key given: nothing recorded, nothing bound"


def collections_by(refs):
    return {r["term"]: (r["class"], r["target"]) for r in refs}


def by_row(g, term):
    return next(r for r in g["refs"] if r["term"] == term)


def by_count(g, cls):
    return sum(1 for r in g["refs"] if r["class"] == cls)


def test_density_table_k_rule_ties_never_split():
    def graph(degs):
        return {"symbols": [{"id": f"s{i}"} for i in range(len(degs))],
                "symbol_edges": [{"from": f"c{i}_{j}", "to": f"s{i}", "type": "calls"} for i, n in enumerate(degs) for j in range(n)]}
    t = G.density_table(graph([3, 3, 2, 1, 0, 0]))
    assert (t["k"], t["cap"], t["dense_in_population"]) == (3, 2, 2)
    t = G.density_table(graph([3, 2, 2, 2, 0, 0]))
    assert (t["k"], t["dense_in_population"]) == (3, 1), "the tie at 2 straddles the third: all of it sparse, never split"
    t = G.density_table(graph([5, 4, 0, 0, 0, 0]))
    assert (t["k"], t["dense_in_population"]) == (1, 2), "k >= 1: a symbol nothing references is never dense"
    g = {"symbols": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
         "symbol_edges": [{"from": "a", "to": "a", "type": "calls"}, {"from": "b", "to": "a", "type": "uses"}, {"from": "b", "to": "a", "type": "calls"}, {"from": "c", "to": "a", "type": "imports"}]}
    assert G.density_table(g)["degree"] == {"a": 1, "b": 0, "c": 0}, "distinct referencing symbols over calls and uses; self-edges and imports dropped"


def test_fill_shapes_widened_for_the_grounder():
    f = {"id": "f1", "type": "FREEFORM", "fill_schema": holes.FILL_SHAPES["FREEFORM"]}
    assert holes.validate_fill(f, [{"code": "x", "span": {"path": "a", "start": 3, "end": 2}}]) == []
    assert holes.validate_fill(f, [{"code": "x", "span": {"path": "a", "start": 3, "end": 1}}]) and holes.validate_fill(f, []) and holes.validate_fill(f, [{"code": "x"}])
    assert holes.validate_fill(f, {"code": "x", "span": {"path": "a", "start": 1, "end": 0}}) == []
