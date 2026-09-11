"""`hobbes gate` (calvin-m0-gate §2.2, WP-18): every blocking class fires on a synthetic Go diff; on Python the name and form classes
fire and the Go world classes do not; the complement split routes a name-absence NULL in a blind spot to `unknown` and leaves the
source-read classes standing; the partition check blocks an outside write and exempts test support; `new` is routed and never
blocks; a defective map is refused; the record is byte-identical on rerun — on a synthetic ledger over a temporary git repo, as the
grounder's own tests are."""
import json
import subprocess

import pytest

from hobbes import cli
from hobbes.derive import gate as gt
from hobbes.derive import ground as G
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
GO_MOD = "module example.com/x\n\ngo 1.22\n"
OTHER = "package other\n\n// V is a value.\nvar V = 1\n"
PARTITION = ["cmd/main.go", "internal/app/app.go", "pkg/core.py", "pkg/use.py"]
MAP = {"partition": ["cmd/main.go", "internal/app/app.go"],
       "files": [{"path": "cmd/main.go", "captured": True, "reason": None, "detail": ""},
                 {"path": "internal/app/app.go", "captured": False, "reason": "uncaptured-file", "detail": "C-26"}],
       "symbols": [{"id": "cmd/main.main", "path": "cmd/main.go", "start": 5, "end": 7, "captured": True, "reason": None, "detail": ""},
                   {"id": "cmd/main.runGoRTA", "path": "cmd/main.go", "start": 9, "end": 11, "captured": False, "reason": "dynamic-dispatch", "detail": "C-2"}],
       "sites": [{"path": "cmd/main.go", "line": None, "count": 3, "class": "attr-call", "reason": "dynamic-dispatch", "detail": "C-2"}],
       "partition_lines": 29, "uncaptured_lines": 21, "fraction_uncaptured": 0.72, "source": {"graph": "graph.json", "built_by": "hobbes test"}}


def _git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def _graph(sha):
    ev = lambda p, l: [{"lane": "scip", "line": l, "path": p}]
    return {
        "sha": sha, "schema_version": 4, "built_by": {"sha": "abc"}, "containment": {"all_contained": True},
        "nodes": [{"id": "internal/app/app", "kind": "module", "path": "internal/app/app.go"}, {"id": "cmd/main", "kind": "module", "path": "cmd/main.go"},
                  {"id": "pkg", "kind": "package", "path": "pkg/__init__.py"}, {"id": "pkg.core", "kind": "module", "path": "pkg/core.py"},
                  {"id": "pkg.use", "kind": "module", "path": "pkg/use.py"}],
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
        ],
        "symbol_edges": [
            {"from": "cmd/main.main", "to": "cmd/main.runGoRTA", "type": "calls", "tier": "semantic", "evidence": ev("cmd/main.go", 6)},
            {"from": "cmd/main.runGoRTA", "to": "internal/app/app.Run", "type": "calls", "tier": "semantic", "evidence": ev("cmd/main.go", 10)},
            {"from": "internal/app/app.helper", "to": "internal/app/app.Run", "type": "calls", "tier": "semantic", "evidence": ev("internal/app/app.go", 17)},
        ],
        "module_edges": [],
    }


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    files = {"internal/app/app.go": APP, "cmd/main.go": MAIN, "go.mod": GO_MOD, "pkg/__init__.py": INIT, "pkg/core.py": CORE, "pkg/use.py": USE,
             "docs/notes.md": "notes\n", "testdata/x.toml": "a = 1\n", "internal/other/other.go": OTHER}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "one")
    sha = _git(root, "rev-parse", "HEAD").strip()
    graph = _graph(sha)
    (tmp_path / "graph.json").write_text(json.dumps(graph))
    return root, sha, T.Ledger(graph, {"tests": []}), tmp_path / "graph.json"


def diff_of(root, changes: dict) -> str:
    """The working tree changed as *changes* says (None deletes), as `git diff`, then restored."""
    for rel, text in changes.items():
        if text is None:
            (root / rel).unlink()
        else:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text)
    _git(root, "add", "-A")
    d = _git(root, "diff", "--cached", "--no-color")
    _git(root, "reset", "-q", "--hard", "HEAD")
    _git(root, "clean", "-fdq")
    return d


def run_gate(repo, diff, *, partition=PARTITION, bmap=None, rule=None):
    """The gate over *diff*; *rule* None leaves the gate's own default partition rule (`reach`)."""
    root, sha, L, gpath = repo
    return gt.gate(diff, sha, root, L, inputs=gt.input_hashes(diff, gpath, None, partition, bmap), partition=partition,
                   partition_source="list", bmap=bmap, **({} if rule is None else {"partition_rule": rule}))


def main_with(body: str) -> str:
    return MAIN.replace('\tapp.Run(app.Options{Repo: "."})', body)


def use_with(body: str) -> str:
    return USE.replace('    return derive(core.TABLE.get("a"))', body)


GO_CASES = {
    "invented": {"cmd/main.go": main_with("\tapp.Frobnicate()")},
    "near-miss": {"cmd/main.go": main_with("\tapp.Rnu(app.Options{})")},
    "arity": {"cmd/main.go": main_with("\tapp.Run(app.Options{}, 1)")},
    "undeclared-type": {"cmd/main.go": main_with("\tvar x app.NoSuchType\n\t_ = x")},
    "import-outside": {"cmd/main.go": main_with("\tmod.Do()").replace('import "example.com/x/internal/app"',
                                                                        'import (\n\t"example.com/x/internal/app"\n\t"github.com/other/mod"\n)')},
    "unimported": {"cmd/main.go": main_with('\tstrings.ToUpper("x")')},
    "malformed": {"cmd/main.go": MAIN + "12  x := 1\n13  y := 2\n"},
    "partition": {"internal/other/other.go": OTHER.replace("var V = 1", "var V = 2")},  # seeded (ii)'s shape: an existing code file elsewhere
}


def test_the_cases_cover_every_blocking_class():
    assert set(GO_CASES) == set(gt.BLOCKING) and gt.GATE_CLASSES == gt.BLOCKING + ("unknown", "new")


@pytest.mark.parametrize("cls", sorted(GO_CASES))
def test_each_blocking_class_fires_on_a_synthetic_go_diff(repo, cls):
    rec = run_gate(repo, diff_of(repo[0], GO_CASES[cls]))
    assert rec["verdict"] == "blocked" and rec["blocking"] == [cls], rec["rows"]
    row = next(r for r in rec["rows"] if r["class"] == cls)
    assert row["path"] == ("internal/other/other.go" if cls == "partition" else "cmd/main.go")
    if cls not in ("malformed", "partition"):
        assert row["grounder_class"] == cls and row["line"] > 0 and row["site"] is None, "no map given: every class stands, no site read"
    assert rec["integrity"]["applies"] is True and rec["integrity"]["post_agrees"] is True


def test_a_clean_diff_clears_an_empty_one_clears_and_one_that_does_not_apply_is_malformed(repo):
    root = repo[0]
    clean = diff_of(root, {"cmd/main.go": main_with("\tapp.Run(app.Options{})")})
    rec = run_gate(repo, clean)
    assert rec["verdict"] == "clear" and rec["rows"] == [] and rec["ground"]["hsr"] == 0.0 and rec["integrity"]["post_agrees"] is True
    empty = run_gate(repo, "")
    assert empty["verdict"] == "clear" and empty["integrity"]["empty"] is True and empty["integrity"]["applies"] is None
    bad = run_gate(repo, clean.replace('-\tapp.Run(app.Options{Repo: "."})', "-\tapp.Run(nothing)"))
    assert bad["blocking"] == ["malformed"] and bad["integrity"]["applies"] is False
    row = next(r for r in bad["rows"] if r["class"] == "malformed")
    assert row["kind"] == "diff" and row["reason"].startswith(f"the diff does not apply at {repo[1][:12]}")


def test_on_python_the_name_and_form_classes_fire_and_the_go_world_classes_do_not(repo):
    """§0b: the world and signature classes are Go's; on a Python diff invented, near-miss, malformed and partition fire."""
    root = repo[0]
    assert run_gate(repo, diff_of(root, {"pkg/use.py": use_with("    return frobnicate(1)")}))["blocking"] == ["invented"]
    assert run_gate(repo, diff_of(root, {"pkg/use.py": use_with("    return derivee(1)")}))["blocking"] == ["near-miss"]
    assert run_gate(repo, diff_of(root, {"pkg/use.py": USE + "12  a = 1\n13  b = 2\n"}))["blocking"] == ["malformed"]
    assert run_gate(repo, diff_of(root, {"tools/new.py": "def f():\n    return 1\n"}))["blocking"] == ["partition"]
    # no arity on Python, and an import outside the repo is external, never import-outside or unimported
    assert run_gate(repo, diff_of(root, {"pkg/use.py": use_with("    return derive(1, 2, 3)")}))["verdict"] == "clear"
    rec = run_gate(repo, diff_of(root, {"pkg/use.py": "import nosuchmod\n" + use_with("    return nosuchmod.f(os.sep)")}))
    assert rec["verdict"] == "clear" and rec["ground"]["world"] == {}


def test_the_split_routes_a_name_absence_in_a_blind_spot_to_unknown_and_leaves_the_rest_standing(repo):
    root = repo[0]
    part = MAP["partition"]
    # invented inside runGoRTA, a dynamic-dispatch blind spot: unknown, advisory, the verdict clear
    rec = run_gate(repo, diff_of(root, GO_CASES["invented"]), partition=part, bmap=MAP)
    assert rec["verdict"] == "clear" and rec["advisory"] == ["unknown"] and rec["counts"]["unknown"] == 1
    row = rec["rows"][0]
    assert (row["class"], row["grounder_class"], row["site"]["grain"], row["site"]["id"], row["site"]["reason"], row["site"]["detail"]) == \
        ("unknown", "invented", "symbol", "cmd/main.runGoRTA", "dynamic-dispatch", "C-2")
    assert row["site"]["anchor"] == ["replace", 10] and rec["split"]["invented"] == {"stands": 0, "unknown": 1}
    assert rec["unknown_reasons"] == {"dynamic-dispatch": 1} and rec["map"]["partition_agrees"] is True
    # the same invention inside main, a captured symbol: it stands and blocks
    rec = run_gate(repo, diff_of(root, {"cmd/main.go": MAIN.replace("\trunGoRTA()", "\tfrobnicate()")}), partition=part, bmap=MAP)
    assert rec["blocking"] == ["invented"] and rec["rows"][0]["site"]["id"] == "cmd/main.main" and rec["rows"][0]["site"]["captured"] is True
    # arity is read from the callee's own declaration, which a blind spot does not hide: it stands there
    rec = run_gate(repo, diff_of(root, GO_CASES["arity"]), partition=part, bmap=MAP)
    assert rec["blocking"] == ["arity"] and rec["rows"][0]["site"]["captured"] is False
    # an uncaptured file: unknown by its file entry
    rec = run_gate(repo, diff_of(root, {"internal/app/app.go": APP.replace('\tfmt.Println("go-rta", o.Repo)', "\tfrobnicate()")}), partition=part, bmap=MAP)
    assert rec["verdict"] == "clear" and rec["rows"][0]["site"]["grain"] == "file" and rec["unknown_reasons"] == {"uncaptured-file": 1}
    # a file the map does not list (outside the partition): unmapped, unknown — and the partition row blocks it
    rec = run_gate(repo, diff_of(root, {"pkg/use.py": use_with("    return frobnicate(1)")}), partition=part, bmap=MAP)
    assert rec["blocking"] == ["partition"] and [r["class"] for r in rec["rows"]] == ["partition", "unknown"]
    assert rec["rows"][1]["site"]["reason"] == gt.UNMAPPED


def test_a_file_grain_site_row_never_routes_and_a_line_grain_one_does(repo):
    """The orchestrator's pin on WP-17's maps: a `sites` row with `line: null` is the file's unresolved count, context only — a NULL in
    that file stays invented and blocks; a row whose line is the NULL's parent line routes it to unknown."""
    root = repo[0]
    m = json.loads(json.dumps(MAP))
    m["symbols"][1].update(captured=True, reason=None)  # runGoRTA captured: only the file-grain site row speaks for cmd/main.go
    rec = run_gate(repo, diff_of(root, GO_CASES["invented"]), partition=m["partition"], bmap=m)
    assert rec["blocking"] == ["invented"] and rec["rows"][0]["site"]["grain"] == "symbol" and rec["rows"][0]["site"]["captured"] is True
    assert rec["map"]["unresolved_by_file"] == {"cmd/main.go": {"attr-call": 3}}
    m["sites"].append({"path": "cmd/main.go", "line": 10, "class": "attr-call", "reason": "dynamic-dispatch", "detail": "C-2"})
    rec = run_gate(repo, diff_of(root, GO_CASES["invented"]), partition=m["partition"], bmap=m)
    assert rec["verdict"] == "clear" and (rec["rows"][0]["site"]["grain"], rec["rows"][0]["site"]["id"]) == ("site", "cmd/main.go:10")
    m["sites"][-1]["reason"] = None
    assert any("line-grain site" in e for e in gt.validate_map(m))


#: Trimmed from calvin-gate WP-17's fzf unit 7b16e44f5343: a real map's shape — file-grain `sites`, the extra `grain` field.
WP17_MAP = {
    "partition": ["src/algo/algo_test.go", "src/algo/fastpath_equiv_test.go"],
    "files": [{"path": "src/algo/algo_test.go", "captured": True, "reason": None, "detail": ""},
              {"path": "src/algo/fastpath_equiv_test.go", "captured": True, "reason": None, "detail": ""}],
    "symbols": [{"id": "src/algo/algo_test.init", "path": "src/algo/algo_test.go", "start": 12, "end": 14, "captured": True, "reason": None, "detail": ""},
                {"id": "src/algo/algo_test.assertMatch", "path": "src/algo/algo_test.go", "start": 16, "end": 18, "captured": True, "reason": None, "detail": ""}],
    "sites": [{"path": "src/algo/algo_test.go", "line": None, "count": 9, "class": "local-binding", "reason": "oracle-miss:closure",
               "detail": "tail local-binding: parameter/local/nested def (C-9); oracle class static→closure / func-value→closure"}],
    "partition_lines": 13010, "uncaptured_lines": 0, "fraction_uncaptured": 0.0,
    "source": {"graph": "graphs/fzf/9dfdba41f5dc1b5f712529fa923bdcf67eb09c30.json", "built_by": "hobbes 0.1.17-beta @ 3f5e47dd6690"},
    "grain": {"partition": "file", "sites": "file (path, tail class, count; line null)"},
}


def test_a_real_wp17_map_reads_and_its_file_grain_sites_do_not_route():
    assert gt.validate_map(WP17_MAP) == []
    index = lambda rows: {p: [r for r in rows if r["path"] == p] for p in {r["path"] for r in rows}}
    files = {f["path"]: f for f in WP17_MAP["files"]}
    s = gt.site_of("src/algo/algo_test.go", 13, {13: ("replace", 13)}, files, index(WP17_MAP["symbols"]), False, index(WP17_MAP["sites"]))
    assert (s["grain"], s["id"], s["captured"]) == ("symbol", "src/algo/algo_test.init", True)
    s = gt.site_of("src/algo/algo_test.go", 40, {40: ("replace", 40)}, files, index(WP17_MAP["symbols"]), False, index(WP17_MAP["sites"]))
    assert (s["grain"], s["captured"]) == ("file", True), "the file's nine closure sites are context, not a blind spot"


def test_post_anchors_and_the_insertion_point_rule():
    text = ("diff --git a/f.go b/f.go\n--- a/f.go\n+++ b/f.go\n@@ -3,4 +3,5 @@\n ctx\n-old1\n-old2\n+new1\n+new2\n+new3\n ctx2\n"
            "@@ -10,0 +12,1 @@\n+ins\n")
    assert gt.post_anchors(text) == {4: ("replace", 4), 5: ("replace", 5), 6: ("replace", 5), 12: ("insert", 11)}
    syms = {"f.go": [{"id": "A", "path": "f.go", "start": 1, "end": 10, "captured": False, "reason": "laneb-miss"},
                     {"id": "B", "path": "f.go", "start": 11, "end": 20, "captured": True},
                     {"id": "A.inner", "path": "f.go", "start": 3, "end": 6, "captured": True}]}
    files = {"f.go": {"path": "f.go", "captured": True}}
    at = lambda anchor: gt.site_of("f.go", 1, {1: anchor}, files, syms, False)
    assert at(("replace", 4))["id"] == "A.inner", "the innermost symbol holding the anchor"
    assert at(("insert", 5))["id"] == "A.inner" and at(("insert", 8))["id"] == "A"
    assert at(("insert", 11))["grain"] == "file", "between two symbols: neither holds both neighbours"
    assert gt.site_of("f.go", 1, {1: ("replace", 4)}, files, syms, True)["grain"] == "file", "a created or renamed file reads its file entry"


def test_partition_blocks_an_outside_write_names_created_and_deleted_and_exempts_test_support(repo):
    root = repo[0]
    fixture = diff_of(root, {"testdata/x.toml": "a = 2\n"})
    rec = run_gate(repo, fixture)
    assert rec["verdict"] == "clear" and rec["partition"]["exempt"] == ["testdata/x.toml"] and rec["partition"]["outside"] == []
    assert run_gate(repo, fixture, rule="strict")["blocking"] == ["partition"] and rec["partition"]["rule"] == "reach"
    rec = run_gate(repo, diff_of(root, {"internal/app/extra.go": "package app\n\nfunc Extra() int { return 1 }\n", "docs/notes.md": None}), rule="exempt")
    assert [(r["path"], r["reason"]) for r in rec["rows"] if r["class"] == "partition"] == [
        ("docs/notes.md", "outside the unit's write partition (deleted)"), ("internal/app/extra.go", "outside the unit's write partition (created)")]
    rec = run_gate(repo, diff_of(root, {"docs/notes.md": "y\n"}), partition=None)
    assert rec["verdict"] == "clear" and rec["partition"]["checked"] is False and rec["inputs"]["partition"] is None


def test_the_reach_rule_allows_not_code_and_a_code_file_created_beside_the_partition(repo):
    """WP-18's finding on WP-17's fzf golds: 11 of 20 write docs, man pages, Ruby tests, a Makefile or new files the file-grain partition
    lacks. `reach` is the stated reading that allows the not-code ones and a code file created beside a partition file — never a code
    file in a directory the partition does not reach."""
    root = repo[0]
    d = diff_of(root, {"docs/notes.md": "x\n", "cmd/extra.go": "package main\n\nfunc extra() {}\n", "tools/gen.go": "package tools\n"})
    assert run_gate(repo, d, rule="exempt")["partition"]["outside"] == ["cmd/extra.go", "docs/notes.md", "tools/gen.go"]
    rec = run_gate(repo, d)
    assert rec["partition"]["rule"] == "reach" and rec["blocking"] == ["partition"]
    assert rec["partition"]["outside"] == ["tools/gen.go"] and rec["partition"]["reached"] == ["cmd/extra.go", "docs/notes.md"]
    assert {f["path"]: f["reach"] for f in rec["partition"]["files"]} == {"cmd/extra.go": "beside-partition", "docs/notes.md": "not-code", "tools/gen.go": None}
    with pytest.raises(ValueError, match="partition rule"):
        run_gate(repo, d, rule="loose")
    # a code file created beside the partition reads its directory's partition files: an invention there stands where that
    # directory is captured, and is unknown where it is a blind spot — never `unmapped` by default
    rec = run_gate(repo, diff_of(root, {"cmd/extra.go": "package main\n\nfunc extra() { frobnicate() }\n"}), partition=MAP["partition"], bmap=MAP)
    assert rec["blocking"] == ["invented"] and rec["partition"]["reached"] == ["cmd/extra.go"]
    assert (rec["rows"][0]["site"]["grain"], rec["rows"][0]["site"]["captured"]) == ("file", True)
    rec = run_gate(repo, diff_of(root, {"internal/app/extra.go": "package app\n\nfunc extra() { frobnicate() }\n"}), partition=MAP["partition"], bmap=MAP)
    assert rec["verdict"] == "clear" and rec["unknown_reasons"] == {"uncaptured-file": 1}


def test_reach_is_the_default_an_existing_code_file_elsewhere_blocks_and_a_not_code_write_is_listed(repo):
    """D-s: `reach` is the default — the gate judges the world Hobbes has, which is ingested code. A hunk written into an existing Go
    file of another package outside the partition (seeded variant (ii)'s shape) still blocks; a write no lane-A provider reads is
    listed in `partition.reached` as `not-code` and blocks nothing."""
    import inspect
    assert inspect.signature(gt.gate).parameters["partition_rule"].default == "reach"
    root = repo[0]
    rec = run_gate(repo, diff_of(root, GO_CASES["partition"]))
    assert rec["partition"]["rule"] == "reach" and rec["blocking"] == ["partition"] and rec["partition"]["reached"] == []
    assert rec["partition"]["files"] == [{"path": "internal/other/other.go", "in_partition": False, "exempt": False, "reach": None,
                                          "created": False, "deleted": False}]
    rec = run_gate(repo, diff_of(root, {"docs/notes.md": "changed\n", "Makefile": "all:\n\ttrue\n"}))
    assert rec["verdict"] == "clear" and rec["rows"] == [] and rec["partition"]["outside"] == []
    assert rec["partition"]["reached"] == ["Makefile", "docs/notes.md"]
    assert {f["path"]: f["reach"] for f in rec["partition"]["files"]} == {"Makefile": "not-code", "docs/notes.md": "not-code"}


def test_new_is_routed_never_blocking_and_a_name_the_diff_declares_grounds_as_a_gensym(repo, monkeypatch):
    diff = diff_of(repo[0], {"cmd/main.go": main_with("\tnewHelper()") + "\nfunc newHelper() {}\n"})
    rec = run_gate(repo, diff)
    assert rec["verdict"] == "clear" and rec["counts"]["new"] == 0 and rec["ground"]["references"]["gensym"] == 1
    real = G.ground

    def with_new(*a, **k):  # the gate's reading declares nothing; a `new` row reaching it is a defect to route, never a verdict
        g = real(*a, **k)
        g["null"].append({"hole": "F1[0]", "path": "cmd/main.go", "line": 10, "term": "planned", "null_class": "new", "nearest": [], "scope": None})
        return g
    monkeypatch.setattr(G, "ground", with_new)
    rec = run_gate(repo, diff, bmap=MAP, partition=MAP["partition"])
    assert rec["verdict"] == "clear" and rec["routed"] == ["new"] and rec["route"] is True and rec["counts"]["new"] == 1
    assert rec["rows"][0]["class"] == "new", "never split to unknown, never dropped"


def test_a_map_that_breaks_the_schema_is_refused(repo):
    assert gt.validate_map(MAP) == []
    ok = json.loads(json.dumps(MAP))
    ok["symbols"][1]["reason"] = "oracle-miss:closure"
    assert gt.validate_map(ok) == []
    assert any("cover every partition file" in e for e in gt.validate_map({**MAP, "files": MAP["files"][:1]}))
    bad = json.loads(json.dumps(MAP))
    bad["symbols"][1]["reason"] = "a hunch"
    assert gt.validate_map(bad) and gt.validate_map([]) == ["the map is not a JSON object"]
    with pytest.raises(ValueError, match="refused"):
        run_gate(repo, diff_of(repo[0], GO_CASES["invented"]), bmap=bad)


def test_record_is_byte_identical_on_rerun_and_the_cli_writes_it_beside_the_diff(repo, tmp_path, capsys):
    root, sha, L, gpath = repo
    d = diff_of(root, GO_CASES["invented"])
    a = gt.dumps(run_gate(repo, d, partition=MAP["partition"], bmap=MAP))
    assert a == gt.dumps(run_gate(repo, d, partition=MAP["partition"], bmap=MAP))
    rec = json.loads(a)
    assert set(rec["inputs"]) == {"diff", "graph", "tests", "partition", "map"} and rec["inputs"]["tests"] is None and rec["inputs"]["map"]
    assert (rec["gate_version"], rec["grounder_version"]) == (gt.GATE_VERSION, G.GROUNDER_VERSION) and str(tmp_path) not in a, "no machine path"
    assert run_gate(repo, d)["record_hash"] != rec["record_hash"], "another input, another record"
    (tmp_path / "cand.diff").write_text(d)
    (tmp_path / "map.json").write_text(json.dumps(MAP))
    (tmp_path / "part.txt").write_text("\n".join(PARTITION) + "\n")
    base = ["gate", "--diff", str(tmp_path / "cand.diff"), "--parent", sha, "--repo", str(root), "--graph", str(gpath)]
    assert cli.main(base + ["--partition", str(tmp_path / "part.txt")]) == 1
    first = (tmp_path / "cand.diff.gate.json").read_bytes()
    assert cli.main(base + ["--partition", str(tmp_path / "part.txt")]) == 1 and (tmp_path / "cand.diff.gate.json").read_bytes() == first
    assert json.loads(first)["partition"]["source"] == "lines" and json.loads(first)["partition"]["rule"] == "reach", "the CLI's default rule"
    capsys.readouterr()
    assert cli.main(base + ["--partition", str(tmp_path / "part.txt"), "--message", "--out", str(tmp_path / "m.json")]) == 1
    assert "blocked it: invented (1)." in capsys.readouterr().out
    assert cli.main(base + ["--map", str(tmp_path / "map.json")]) == 0, "the map's partition; the invention sits in a blind spot"
    assert json.loads((tmp_path / "cand.diff.gate.json").read_text())["partition"]["source"] == "map"
    assert cli.main(base[:4] + ["deadbeef"] + base[5:]) == 2
    (tmp_path / "bad.json").write_text(json.dumps({**MAP, "files": []}))
    assert cli.main(base + ["--map", str(tmp_path / "bad.json")]) == 2
    other = tmp_path / "other.json"
    other.write_text(json.dumps({**_graph("0" * 40)}))
    assert cli.main(base[:-1] + [str(other)]) == 2, "a graph at another SHA"


def test_repair_message_names_the_classes_the_sites_the_files_outside_and_a_declaration_form(repo):
    root = repo[0]
    rec = run_gate(repo, diff_of(root, {**GO_CASES["invented"], **GO_CASES["partition"]}))
    assert rec["blocking"] == ["invented", "partition"]
    msg = gt.repair_message(rec)
    assert msg.startswith(f"Hobbes checked your change against the repository at its parent commit {repo[1][:12]} and blocked it: invented (1), partition (1).")
    assert "- cmd/main.go:10 `app.Frobnicate`" in msg and "- internal/other/other.go\n" in msg and "one turn to repair it" in msg
    assert rec["siblings"][0]["symbol"] == "internal/app/app.Run" and "func Run(o Options) error {" in msg and "directory `internal/app/`" in msg
    assert msg == gt.repair_message(json.loads(gt.dumps(rec))), "the message is the record's, deterministic"
    with pytest.raises(ValueError):
        gt.repair_message(run_gate(repo, diff_of(root, {"cmd/main.go": main_with("\tapp.Run(app.Options{})")})))
