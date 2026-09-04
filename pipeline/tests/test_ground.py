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


def test_fill_shapes_widened_for_the_grounder():
    f = {"id": "f1", "type": "FREEFORM", "fill_schema": holes.FILL_SHAPES["FREEFORM"]}
    assert holes.validate_fill(f, [{"code": "x", "span": {"path": "a", "start": 3, "end": 2}}]) == []
    assert holes.validate_fill(f, [{"code": "x", "span": {"path": "a", "start": 3, "end": 1}}]) and holes.validate_fill(f, []) and holes.validate_fill(f, [{"code": "x"}])
    assert holes.validate_fill(f, {"code": "x", "span": {"path": "a", "start": 1, "end": 0}}) == []
