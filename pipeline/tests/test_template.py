"""`hobbes template` (Calvin M0 step 2): the anchor pass's matchers, the structure pass's holes, round 1, pruning, the two scorers, and byte-identity — on a synthetic ledger over a temporary git repo."""
import json
import subprocess
from pathlib import Path

import pytest

from hobbes.derive import holes
from hobbes.derive import template as T

SRC = """// Package app is the app.
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

func helper() int { return 1 }
"""
MAIN = """package main

func main() {
\tswitch os.Args[1] {
\tcase "go-rta":
\t\trunGoRTA()
\t}
}

func runGoRTA() {
\tapp.Run(app.Options{Repo: "."})
}
"""
TEST = """package app

func TestRun(t *testing.T) {
\tRun(Options{})
}
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "internal/app").mkdir(parents=True)
    (tmp_path / "cmd").mkdir()
    (tmp_path / "internal/app/app.go").write_text(SRC)
    (tmp_path / "internal/app/app_test.go").write_text(TEST)
    (tmp_path / "cmd/main.go").write_text(MAIN)
    for c in (["git", "init", "-q"], ["git", "add", "."], ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "one"]):
        subprocess.run(c, cwd=tmp_path, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    return tmp_path, sha


def ledger(sha):
    ev = lambda p, l: [{"lane": "scip", "line": l, "path": p}]
    graph = {
        "sha": sha, "schema_version": 4, "built_by": {"sha": "abc"}, "containment": {"all_contained": True},
        "nodes": [{"id": "internal/app/app", "kind": "module", "path": "internal/app/app.go"},
                  {"id": "internal/app/app_test", "kind": "module", "path": "internal/app/app_test.go"},
                  {"id": "cmd/main", "kind": "module", "path": "cmd/main.go"}],
        "symbols": [
            {"id": "internal/app/app.Options", "module": "internal/app/app", "name": "Options", "kind": "type", "line": 7, "end_line": 9},
            {"id": "internal/app/app.Run", "module": "internal/app/app", "name": "Run", "kind": "function", "line": 12, "end_line": 15},
            {"id": "internal/app/app.helper", "module": "internal/app/app", "name": "helper", "kind": "function", "line": 17, "end_line": 17},
            {"id": "internal/app/app_test.TestRun", "module": "internal/app/app_test", "name": "TestRun", "kind": "function", "line": 3, "end_line": 5},
            {"id": "cmd/main.main", "module": "cmd/main", "name": "main", "kind": "function", "line": 3, "end_line": 8},
            {"id": "cmd/main.runGoRTA", "module": "cmd/main", "name": "runGoRTA", "kind": "function", "line": 10, "end_line": 12},
        ],
        "symbol_edges": [
            {"from": "cmd/main.main", "to": "cmd/main.runGoRTA", "type": "calls", "tier": "semantic", "evidence": ev("cmd/main.go", 6)},
            {"from": "cmd/main.runGoRTA", "to": "internal/app/app.Run", "type": "calls", "tier": "semantic", "evidence": ev("cmd/main.go", 11)},
            {"from": "cmd/main.runGoRTA", "to": "internal/app/app.Options", "type": "uses", "tier": "semantic", "evidence": ev("cmd/main.go", 11)},
            {"from": "internal/app/app.Run", "to": "internal/app/app.Options", "type": "uses", "tier": "semantic", "evidence": ev("internal/app/app.go", 12)},
            {"from": "internal/app/app_test.TestRun", "to": "internal/app/app.Run", "type": "calls", "tier": "semantic", "evidence": ev("internal/app/app_test.go", 4)},
        ],
        "module_edges": [],
    }
    tests = {"tests": [{"id": "internal/app/app_test.go::TestRun", "file": "internal/app/app_test.go", "line": 3, "symbol": "internal/app/app_test.TestRun",
                        "reaches": ["internal/app/app.Run"], "framework": "go-test"}]}
    return T.Ledger(graph, tests)


def test_anchor_pass_matchers_in_order(repo):
    root, sha = repo
    L = ledger(sha)
    task = ("Fix `Run` and `internal/app/app.go`; see internal/app/app_test.go::TestRun and the trace at cmd/main.go:11; "
            'the message "go-rta" is printed; also helper, and mergeRanges is new.')
    anchors, unresolved, _ = T.anchor_pass(L, task, root)
    by = {(a["term"], a["matcher"]): a["nodes"] for a in anchors}
    assert by[("Run", "backtick")] == ["internal/app/app.Run"]
    assert by[("internal/app/app.go", "path")] == ["internal/app/app"]
    assert by[("internal/app/app_test.go::TestRun", "test-id")] == ["internal/app/app_test.TestRun"]
    assert by[("cmd/main.go:11", "stack-trace")] == ["cmd/main.runGoRTA"]
    assert by[("go-rta", "literal")] == ["cmd/main.main", "internal/app/app.Run"], "hits inside spans only"
    assert by[("helper", "bare-identifier")] == ["internal/app/app.helper"]
    assert [u["term"] for u in unresolved] == ["go-rta", "mergeRanges"] and unresolved[1]["nearest"], "a literal-only term stays unresolved as a name"


def test_backticked_non_identifier_is_a_literal_and_stays_unresolved(repo):
    root, sha = repo
    L = ledger(sha)
    anchors, unresolved, _ = T.anchor_pass(L, "Add a flag to `app go-rta`.", root)
    assert [(a["term"], a["matcher"]) for a in anchors] == [("app go-rta", "literal"), ("go-rta", "literal")] or \
        [(a["term"], a["matcher"]) for a in anchors] == [("go-rta", "literal")]
    assert "go-rta" in [u["term"] for u in unresolved], "as a name it is unbound"


def test_structure_pass_holes_and_partition(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `runGoRTA`.", L, root, None)
    assert holes.validate_template(t) == []
    by_type = {}
    for h in t["holes"]:
        by_type.setdefault(h["type"], []).append(h)
    bodies = {h["provenance"]["symbol"] for h in by_type["BODY"]}
    assert bodies == {"cmd/main.runGoRTA", "internal/app/app.Run", "internal/app/app.Options"}, "anchor + callee + the type it uses in an anchored file"
    assert t["constraints"]["write_partition"] == ["cmd/main.go", "internal/app/app.go", "internal/app/app_test.go"]
    callers = {h["provenance"]["edge"].split(" ")[0]: h for h in by_type["CALLER_UPDATE"]}
    assert set(callers) == {"cmd/main.main", "internal/app/app_test.TestRun"} and all(h.get("closed") is None for h in callers.values())
    assert [h["provenance"]["test"] for h in by_type["TEST_EXPECTATION"]] == ["internal/app/app_test.go::TestRun"]
    regions = [(h["span"]["path"], h["span"]["start"], h["span"]["end"], h["provenance"]["kind"]) for h in by_type["MODULE_REGION"]]
    assert ("internal/app/app.go", 1, 6, "head") in regions and ("internal/app/app.go", 10, 11, "gap") in regions and ("internal/app/app.go", 16, 16, "gap") in regions
    assert ("cmd/main.go", 1, 2, "head") in regions and ("cmd/main.go", 9, 9, "gap") in regions
    assert not any(r[0].endswith("_test.go") for r in regions), "regions for interior files only"
    assert by_type["FREEFORM"] and "COCHANGE_TOUCH" not in by_type


def test_bare_identifier_waits_for_confirmation_then_joins(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Something about helper.", L, root, None)
    assert [h["type"] for h in t["holes"]] == ["ANCHOR_CONFIRM", "FREEFORM"], "no structure until confirmed"
    t2 = T.apply_round1("Something about helper.", L, root, None, t, {"c1": {"confirm": True}})
    assert {h["provenance"]["symbol"] for h in t2["holes"] if h["type"] == "BODY"} == {"internal/app/app.helper"}
    t3 = T.apply_round1("Something about helper.", L, root, None, t, {"c1": {"confirm": False}})
    assert [h["type"] for h in t3["holes"]] == ["ANCHOR", "FREEFORM"], "nothing left names structure: ask"


def test_round1_refers_and_new(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Add a --dry-run flag to `app go-rta`.", L, root, None)
    u = next(h for h in t["holes"] if h["type"] == "UNRESOLVED")
    fills = {u["id"]: {"classes": {"go-rta": "refers", "dry-run": "new"}, "refers_to": {"go-rta": "cmd/main.runGoRTA"}}}
    t2 = T.apply_round1("Add a --dry-run flag to `app go-rta`.", L, root, None, t, fills)
    assert any(h["type"] == "NEW_SYMBOL" and "dry-run" in h["ask"] for h in t2["holes"])
    assert "cmd/main.runGoRTA" in {h["provenance"]["symbol"] for h in t2["holes"] if h["type"] == "BODY"}


def test_zero_anchor_task_gets_one_anchor_hole_with_candidates(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Make it faster.", L, root, None)
    assert [h["type"] for h in t["holes"]] == ["ANCHOR", "FREEFORM"]
    c = t["holes"][0]["candidates"]
    assert c["lexical"] == [] and c["nearest"] == [], "nothing in the task names the repo; the candidates say so rather than guess"
    assert c["files"]["n"] == len(L.mod_path) and set(c["files"]["by_dir"]) == {p.split("/", 1)[0] for p in L.mod_path.values()}
    text = holes.render(t, root)
    assert "Candidates from Hobbes" in text and "`internal/`: " in text and "app/app.go" in text
    assert not holes.validate_template(t)


def test_anchor_candidates_carry_lexical_seeds_and_nearest_names(repo):
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and the runGoRTAx helper."
    _, unresolved, _ = T.anchor_pass(L, task, root)
    c = T.anchor_candidates(L, task, unresolved, refused={"runGoRTA"})
    lex = {r["node"]: r for r in c["lexical"]}
    assert any(r["term"] == "runGoRTA" and r.get("refused") for r in lex.values()), "a word round 1 refused is still listed, marked refused"
    assert all(r["path"] for r in lex.values())
    near = {r["term"]: r for r in c["nearest"]}
    assert "runGoRTAx" in near and any(n["name"] == "runGoRTA" and n["nodes"] for n in near["runGoRTAx"]["names"])
    big = T.Ledger({**L.graph, "nodes": L.graph["nodes"] + [{"id": f"x/m{i}", "kind": "module", "path": f"x/d{i % 7}/m{i}.py"} for i in range(T.CANDIDATE_FILES_MAX + 1)]}, {"tests": L.tests})
    c2 = T.anchor_candidates(big, task, unresolved)
    assert not c2["files"]["by_dir"] and c2["files"]["dirs"]["x/d0"] >= 200 and c2["files"]["n"] > T.CANDIDATE_FILES_MAX
    assert "too many to list" in "\n".join(holes._render_candidates(c2))


def test_prune_is_for_function_signatures_only(repo):
    root, sha = repo
    t = T.build_template("Change `Run` and `Options`.", ledger(sha), root, None)
    sig = {h["provenance"]["symbol"]: h["id"] for h in t["holes"] if h["type"] == "SIGNATURE"}
    closed = T.prune(t, {sig["internal/app/app.Run"]: "unchanged", sig["internal/app/app.Options"]: "unchanged"})
    callers = {(h["provenance"]["callee"], h["provenance"]["edge"].split(" ")[0]): h for h in t["holes"] if h["type"] == "CALLER_UPDATE"}
    run_by_test = callers[("internal/app/app.Run", "internal/app/app_test.TestRun")]
    assert run_by_test["closed"]["reason"].startswith("signature of") and closed == [run_by_test["id"]]
    for (callee, _), h in callers.items():  # a type's callers change when its fields do: never closed by the signature rule
        if callee == "internal/app/app.Options":
            assert not (h.get("closed") or {}).get("reason", "").startswith("signature of")


def test_scorers_use_the_pre_image(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `Run`.", L, root, None)
    gold = [("internal/app/app.go", "--- a\n+++ b\n@@ -8,1 +8,2 @@\n+\tX int\n@@ -13,0 +14,1 @@\n+\tz()\n@@ -4,0 +4,1 @@\n+import \"os\"\n"),
            ("cmd/new.go", "new file mode 100644\n@@ -0,0 +1,3 @@\n+x\n")]
    assert T.score_coverage(t, gold) == {"symbol": 2, "region": 1, "new_file": 1, "outside": 0, "hunks": 4}
    an = T.score_anchors(t, L, gold)
    assert an["files"] == {"tp": 1, "anchored": 1, "gold": 2} and an["symbols"]["tp"] == 1 and an["per_matcher"]["backtick"]["symbol_hits"] == 1


def test_byte_identical_and_keyed(repo):
    root, sha = repo
    L = ledger(sha)
    a = T.build_template("Change `Run`.", L, root, None)
    b = T.build_template("Change `Run`.", L, root, None)
    assert json.dumps(a) == json.dumps(b) and a["template_hash"] == b["template_hash"]
    assert a["key"] == {"parent_sha": sha, "task_hash": T.task_hash("Change `Run`."), "template_version": holes.TEMPLATE_VERSION}
    assert holes.render(a, root).count("### ") == sum(1 for h in a["holes"] if "fill" not in h and h.get("closed") is None)


def test_literal_cap_and_directory_matcher(repo, monkeypatch):
    root, sha = repo
    L = ledger(sha)
    monkeypatch.setattr(T, "LITERAL_MAX_NODES", 1)
    anchors, unresolved, dropped = T.anchor_pass(L, 'The message "go-rta"; also `cmd` and `app`.', root)
    assert not any(a["term"] == "go-rta" for a in anchors) and dropped[0]["term"] == "go-rta" and "too common" in dropped[0]["note"]
    by = {a["term"]: (a["matcher"], a["nodes"]) for a in anchors}
    assert by["cmd"] == ("path", ["cmd/main"]) and by["app"] == ("path", ["internal/app/app", "internal/app/app_test"]), "a directory names the modules directly in it"
    assert "go-rta" in [u["term"] for u in unresolved]
