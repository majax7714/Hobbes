"""The local harness (Calvin M0 step 5): test selection from the testmap, per-framework commands and parsers, the baseline classes, `verify` end to end against a faked container, the environment binding, and arm O's brief, policy, session command and patch grounding — no podman, no model."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from hobbes.derive import harness as H
from hobbes.derive import template as T
from hobbes.extract import containment

CORE = "import os\n\n\ndef derive(x):\n    return os.sep + str(x)\n\n\ndef other():\n    return 2\n"
TEST_CORE = "from pkg.core import derive\n\n\ndef test_derive():\n    assert derive(1).endswith('1')\n\n\nclass TestOther:\n    def test_two(self):\n        assert True\n"
APP = "package app\n\nfunc Run() int { return 1 }\n"
APP_TEST = "package app\n\nimport \"testing\"\n\nfunc TestRun(t *testing.T) {\n\tif Run() != 1 {\n\t\tt.Fatal()\n\t}\n}\n"
LIB = "export function helper() { return 1 }\n"
LIB_TEST = "import test from 'node:test'\ntest('helper works', () => {})\n"
LIB_SPEC = "describe('lib', () => { it('helper', () => {}) })\n"


def _git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def test_the_session_repo_holds_the_base_and_its_ancestors_and_nothing_else(tmp_path):
    """calvin-m0-gate D-x: WP-21's key 1 read its own gold with `git show` — the session repo was a clone of the owned clone's full
    history. The cut repo holds the parent and its ancestors: the gold commit, a later tag, a stash and a later branch are absent at
    the object level, there is no remote, no alternates file and no path back to the owned clone; the session's branch comes back to
    the owned clone after it. The repair turn's repo, cut at O's harvested commit, holds O's work and the parent's ancestry — never gold."""
    owned = tmp_path / "owned"
    owned.mkdir()
    _git(owned, "init", "-q")
    for name, text in (("old", "a\n"), ("parent", "b\n"), ("gold", "c\n")):
        (owned / "f.txt").write_text(text)
        _git(owned, "add", ".")
        _git(owned, "commit", "-q", "-m", name)
    c0, c1, gold = (_git(owned, "rev-parse", f"HEAD~{i}").strip() for i in (2, 1, 0))
    _git(owned, "tag", "v9")
    _git(owned, "checkout", "-q", "-b", "later")
    (owned / "f.txt").write_text("d\n")
    _git(owned, "commit", "-q", "-am", "later")
    later = _git(owned, "rev-parse", "HEAD").strip()
    (owned / "f.txt").write_text("e\n")
    _git(owned, "stash", "-q")
    stash = _git(owned, "rev-parse", "stash@{0}").strip()
    _git(owned, "checkout", "-q", "--detach", c1)
    assert H.session_repo_errors(owned, c1), "the owned clone itself breaks the rule: gold, later and the stash are in it"
    cut = H.session_repo(owned, c1, tmp_path / "S.repo", "S")

    def git(repo, *a):
        return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
    for sha in (gold, later, stash):
        assert git(cut, "cat-file", "-e", sha).returncode != 0, sha
    assert set(git(cut, "rev-list", "--all").stdout.split()) == {c0, c1} and git(cut, "log", "--all", "--format=%s").stdout.split() == ["parent", "old"]
    assert git(cut, "remote").stdout == "" and git(cut, "tag").stdout == "" and not (cut / ".git" / "objects" / "info" / "alternates").exists()
    assert H.session_repo_errors(cut, c1, owned) == [] and H.session_repo_record(cut, c1)["commits"] == 2
    # a session commits on its branch; hobbes-session's harvest lands it in the cut repo, and it comes back to the owned clone
    _git(cut, "checkout", "-q", "-b", "hobbes/S")
    (cut / "f.txt").write_text("o\n")
    _git(cut, "commit", "-q", "-am", "o")
    o_sha = _git(cut, "rev-parse", "HEAD").strip()
    assert H.harvest_back(cut, owned, "S") and _git(owned, "rev-parse", "hobbes/S").strip() == o_sha
    assert not H.harvest_back(cut, owned, "no-such-session")
    # the repair turn's repo: O's harvested commit and the parent's ancestry, still no gold
    rr = H.session_repo(owned, o_sha, tmp_path / "S-repair1.repo", "S-repair1")
    assert git(rr, "cat-file", "-e", gold).returncode != 0 and git(rr, "cat-file", "-e", later).returncode != 0
    assert set(git(rr, "rev-list", "--all").stdout.split()) == {c0, c1, o_sha} and git(rr, "remote").stdout == ""
    assert H.session_repo_errors(rr, o_sha, owned) == [] and not (rr / ".git" / "objects" / "info" / "alternates").exists()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "repo"
    files = {"pyproject.toml": "[project]\nname='x'\n[tool.pytest.ini_options]\ntestpaths=['tests']\n", "src/pkg/__init__.py": "", "src/pkg/core.py": CORE,
             "tests/test_core.py": TEST_CORE, "go.mod": "module example.com/x\n\ngo 1.22\n", "internal/app/app.go": APP, "internal/app/app_test.go": APP_TEST,
             "web/package.json": '{"name": "w", "scripts": {"test": "node --test"}}\n', "web/lib.mjs": LIB, "web/lib.test.mjs": LIB_TEST, "web/lib.spec.ts": LIB_SPEC}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "one")
    sha = _git(root, "rev-parse", "HEAD").strip()
    source = tmp_path / "source"
    (source / ".venv" / "bin").mkdir(parents=True)
    (source / ".venv" / "bin" / "python3").write_text("#!/bin/sh\n")
    (source / "web" / "node_modules" / ".bin").mkdir(parents=True)
    return root, sha, source


def ledger(sha):
    graph = {"sha": sha, "schema_version": 4, "built_by": {"sha": "abc"}, "containment": {"all_contained": True},
             "nodes": [{"id": "pkg", "kind": "package", "path": "src/pkg/__init__.py"}, {"id": "pkg.core", "kind": "module", "path": "src/pkg/core.py"},
                       {"id": "tests.test_core", "kind": "module", "path": "tests/test_core.py"},
                       {"id": "internal/app/app", "kind": "module", "path": "internal/app/app.go"}, {"id": "web/lib", "kind": "module", "path": "web/lib.mjs"}],
             "symbols": [{"id": "pkg.core.derive", "module": "pkg.core", "name": "derive", "qualname": "derive", "kind": "function", "line": 4, "end_line": 5},
                         {"id": "pkg.core.other", "module": "pkg.core", "name": "other", "qualname": "other", "kind": "function", "line": 8, "end_line": 9},
                         {"id": "internal/app/app.Run", "module": "internal/app/app", "name": "Run", "qualname": "Run", "kind": "function", "line": 3, "end_line": 3},
                         {"id": "web/lib.helper", "module": "web/lib", "name": "helper", "qualname": "helper", "kind": "function", "line": 1, "end_line": 1}],
             "symbol_edges": [], "module_edges": []}
    tests = {"sha": sha, "schema_version": 4, "tests": [
        {"id": "tests/test_core.py::test_derive", "file": "tests/test_core.py", "framework": "pytest", "line": 4, "reaches": ["pkg.core.derive"], "reaches_modules": ["pkg.core"], "symbol": "tests.test_core.test_derive"},
        {"id": "tests/test_core.py::TestOther::test_two", "file": "tests/test_core.py", "framework": "pytest", "line": 9, "reaches": [], "reaches_modules": [], "symbol": "tests.test_core.TestOther.test_two"},
        {"id": "internal/app/app_test.go::TestRun", "file": "internal/app/app_test.go", "framework": "go-test", "line": 5, "reaches": ["internal/app/app.Run"], "reaches_modules": ["internal/app/app"], "symbol": "internal/app/app_test.TestRun"},
        {"id": "web/lib.test.mjs::helper works", "file": "web/lib.test.mjs", "framework": "node:test", "line": 2, "reaches": ["web/lib.helper"], "reaches_modules": ["web/lib"], "symbol": "web/lib.test.helper works"},
        {"id": "web/lib.spec.ts::lib > helper", "file": "web/lib.spec.ts", "framework": "vitest", "line": 1, "reaches": ["web/lib.helper"], "reaches_modules": ["web/lib"], "symbol": "web/lib.spec.lib > helper"},
    ]}
    return T.Ledger(graph, tests)


def diff_for(root, edits: dict[str, str]) -> str:
    """A git-made diff of *edits* (path → new content) against the checkout, the tree restored after."""
    for rel, text in edits.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
        _git(root, "add", "-N", rel)
    out = _git(root, "diff", "--no-color")
    _git(root, "reset", "-q", "--hard")
    _git(root, "clean", "-qfd")
    return out


def diffs(root):
    return {
        "derive": diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", 'str(x) + "!"')}),
        "import": diff_for(root, {"src/pkg/core.py": CORE.replace("import os\n", "import os\nimport sys\n")}),
        "testfile": diff_for(root, {"tests/test_core.py": TEST_CORE + "\n    def test_three(self):\n        assert True\n"}),
        "new": diff_for(root, {"docs/new.md": "hello\n"}),
        "three": diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", 'str(x) + "!"'), "internal/app/app.go": APP.replace("return 1 }", "return 1 } // x"), "web/lib.mjs": LIB + "// x\n"}),
        "go": diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", 'str(x) + "!"'), "internal/app/app.go": APP.replace("return 1 }", "return 1 } // x")}),
        "helper": diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", "str(x) + helper(x)")}),
    }


def test_split_patch_and_pre_ranges(repo):
    root, _, _ = repo
    d = diffs(root)
    both = d["derive"] + d["new"] + d["import"]
    assert [p for p, _ in H.split_patch(both)] == ["src/pkg/core.py", "docs/new.md", "src/pkg/core.py"]
    ranges, created = H.pre_ranges(both)
    assert ranges["src/pkg/core.py"] == [(5, 5), (1, 2)] and created == {"docs/new.md"} and ranges["docs/new.md"] == []  # the changed lines, not git's context
    ins, _ = H.pre_ranges("diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -7,0 +8,2 @@\n+x\n+y\n")
    assert ins["f"] == [(7, 8)], "a pure insertion after line 7 touches 7 and 8"
    mixed, _ = H.pre_ranges("diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -10,7 +10,7 @@\n a\n b\n c\n-d\n+D\n e\n f\n g\n@@ -30,3 +30,2 @@\n x\n-y\n-z\n+Y\n")
    assert mixed["f"] == [(13, 13), (31, 32)]
    assert H.is_test_path("tests/test_core.py") and H.is_test_path("internal/app/app_test.go") and H.is_test_path("web/lib.spec.ts") and H.is_test_path("scip/test/index.test.mjs")
    assert not H.is_test_path("src/pkg/core.py") and not H.is_test_path("web/lib.mjs")


def test_select_tests_symbol_module_and_touched_grains(repo):
    _, sha, _ = repo
    L = ledger(sha)
    d = diffs(repo[0])
    s = H.select_tests(L, d["derive"])
    assert s.edited_symbols == ["pkg.core.derive"] and s.edited_modules == [] and [t["id"] for t in s.tests] == ["tests/test_core.py::test_derive"]
    assert s.tests[0]["grain"] == "symbol" and s.tests[0]["origin"] == "guard"
    s = H.select_tests(L, "diff --git a/src/pkg/core.py b/src/pkg/core.py\n--- a/src/pkg/core.py\n+++ b/src/pkg/core.py\n@@ -1,1 +1,2 @@\n import os\n+import sys\n")  # the import block is outside every span → module grain
    assert s.edited_symbols == [] and s.edited_modules == ["pkg.core"] and [t["grain"] for t in s.tests] == ["module"]
    L2 = H.T.Ledger({**L.graph, "module_edges": [{"from": "tests.test_core", "to": "pkg.core", "type": "imports", "tier": "syntactic", "evidence": []}]}, {"tests": L.tests})
    s = H.select_tests(L2, d["derive"])  # step 6: a test whose module imports the edited module is a guard too, at import grain
    assert sorted((t["id"], t["grain"]) for t in s.tests) == [("tests/test_core.py::TestOther::test_two", "import"), ("tests/test_core.py::test_derive", "symbol")]
    s = H.select_tests(L, d["testfile"])  # a touched test file runs whole, every test in it
    assert s.touched_test_files == ["tests/test_core.py"] and {t["origin"] for t in s.tests} == {"touched"} and len(s.tests) == 2
    s = H.select_tests(L, d["new"])  # a file the graph lacks reaches nothing
    assert s.created_files == ["docs/new.md"] and s.tests == []
    assert s.record()["by_origin"] == {}


def test_commands_per_framework(repo):
    root, sha, source = repo
    L = ledger(sha)
    s = H.select_tests(L, diffs(root)["three"])
    assert sorted(t["framework"] for t in s.tests) == ["go-test", "node:test", "pytest", "vitest"]
    env = H.environment(source, root)
    cmds = H.commands(s, root, env, root / "reports")
    by = {c.framework: c for c in cmds}
    assert by["pytest"].cwd == "" and by["pytest"].argv[:3] == [".venv/bin/python3", "-m", "pytest"] and by["pytest"].argv[-1] == "tests/test_core.py::test_derive" and by["pytest"].report.endswith(".xml")
    assert by["go-test"].argv == ["go", "test", "-json", "-count=1", "-run", "^(TestRun)$", "./internal/app/"] and by["go-test"].ids == ["internal/app/app_test.go::TestRun"]
    assert by["go-test"].list_argv == ["go", "test", "-list", "^(TestRun)$", "./internal/app/"] and by["go-test"].grain == "symbol"
    assert by["node:test"].cwd == "web" and by["node:test"].argv == ["node", "--test", "--test-reporter=tap", "lib.test.mjs"]
    assert by["vitest"].cwd == "web" and by["vitest"].argv[:3] == ["./node_modules/.bin/vitest", "run", "--no-cache"] and by["vitest"].argv[-1] == "lib.spec.ts"
    assert "--no-cache" in by["vitest"].argv, "vitest's cache must not land in the read-only node_modules"
    # a touched test file runs whole: the file, not the ids
    s2 = H.select_tests(L, diffs(root)["testfile"])
    c = H.commands(s2, root, env, root / "reports")[0]
    assert c.argv[-1] == "tests/test_core.py" and len(c.ids) == 2


def test_parsers(repo):
    root, _, _ = repo
    junit = ('<testsuites><testsuite><testcase classname="tests.test_core" name="test_derive"/>'
             '<testcase classname="tests.test_core.TestOther" name="test_two"><failure message="no"/></testcase>'
             '<testcase classname="tests.test_core" name="test_skip"><skipped/></testcase></testsuite></testsuites>')
    assert H.parse_junit(junit, root, "") == {"tests/test_core.py::test_derive": "pass", "tests/test_core.py::TestOther::test_two": "fail", "tests/test_core.py::test_skip": "skip"}
    assert H.parse_junit("not xml", root, "") == {}
    params = ('<testsuites><testsuite><testcase classname="tests.test_core" name="test_p[a]"/><testcase classname="tests.test_core" name="test_p[b]"><failure/></testcase>'
              '<testcase classname="tests.test_core" name="test_q[x-y]"><skipped/></testcase><testcase classname="tests.test_core" name="test_q[z]"/></testsuite></testsuites>')
    assert H.parse_junit(params, root, "") == {"tests/test_core.py::test_p": "fail", "tests/test_core.py::test_q": "pass"}, "parametrized cases fold into their test, the worst outcome winning"
    gojson = "\n".join(json.dumps(r) for r in [{"Action": "run", "Test": "TestRun"}, {"Action": "pass", "Test": "TestRun"}, {"Action": "fail", "Test": "TestRun/sub"}, {"Action": "pass", "Package": "p"}])
    assert H.parse_go_json(gojson, root, "", "internal/app") == {"internal/app/app_test.go::TestRun": "pass"}
    assert H.parse_go_json("# example.com/x/internal/app [build failed]\nFAIL\n", root, "", "internal/app") == {"__build__": "error"}
    tap = "TAP version 13\n# Subtest: helper works\nok 1 - helper works\n    ---\n    duration_ms: 1\n    ...\nnot ok 2 - broken\nok 3 - later # SKIP\n# tests 3\n"
    assert H.parse_tap(tap, "web/lib.test.mjs") == {"web/lib.test.mjs::helper works": "pass", "web/lib.test.mjs::broken": "fail", "web/lib.test.mjs::later": "skip"}
    vit = json.dumps({"testResults": [{"name": str(root / "web" / "lib.spec.ts"), "assertionResults": [{"ancestorTitles": ["lib"], "title": "helper", "status": "passed"}, {"ancestorTitles": ["lib"], "title": "x", "status": "failed"}]}]})
    assert H.parse_vitest_json(vit, root) == {"web/lib.spec.ts::lib > helper": "pass", "web/lib.spec.ts::lib > x": "fail"}


def test_classify_table():
    assert H.classify("pass", "pass") == "P2P" and H.classify("pass", "fail") == "F2P" and H.classify("fail", "pass") == "P2F" and H.classify("fail", "fail") == "F2F"
    assert H.classify("pass", None) == "new-pass" and H.classify("fail", "not-run") == "new-fail" and H.classify("skip", "pass") == "skip"
    assert H.classify("error", "pass") == "error" and H.classify("not-run", "pass") == "removed" and H.classify("not-run", None) == "not-run"
    assert H.classify("unsupported", None) == "unsupported" and H.classify("uncollected", None) == "uncollected"
    # the verdict reads what the diff did; an F2F is a fault of the environment, a removed test the diff's own renaming
    rec = {"tests": [{"id": "a", "candidate": "fail", "baseline": "fail", "origin": "guard"}, {"id": "b", "candidate": "not-run", "baseline": "pass", "origin": "guard"},
                      {"id": "c", "candidate": "pass", "baseline": "pass", "origin": "guard"}], "baseline": True}
    assert H.score(rec)["verdict"] == "pass" and rec["faults"] == ["a"] and rec["summary"] == {"F2F": 1, "removed": 1, "P2P": 1}
    assert rec["guarding_tests_executed"] == {"count": 2, "ids": ["a", "c"]}, "a fails and it is still a guard executing, not skipped or uncollected"
    rec["tests"].append({"id": "d", "candidate": "fail", "baseline": "pass"})
    assert H.score(rec)["verdict"] == "fail" and rec["regressions"] == ["d"]
    assert H.score({"tests": [], "verdict": "empty-diff"})["verdict"] == "empty-diff"


class FakePodman:
    """Answers `containment.run` from the argv: pytest writes a JUnit report (a test fails on the baseline tree, passes on the candidate's), go prints its JSON."""

    def __init__(self):
        self.plans = []

    def __call__(self, p, *, timeout):
        self.plans.append(p)
        cwd = Path(p.cwd)
        argv = list(p.command)
        candidate = "\"!\"" in (cwd / "src" / "pkg" / "core.py").read_text()
        stdout = ""
        if argv[1:3] == ["-m", "pytest"]:
            rep = next(a for a in argv if a.startswith("--junit-xml="))[len("--junit-xml="):]
            Path(rep).parent.mkdir(parents=True, exist_ok=True)
            Path(rep).write_text('<testsuites><testsuite><testcase classname="tests.test_core" name="test_derive"%s</testsuite></testsuites>'
                                 % ("/>" if candidate else "><failure/></testcase>"))
        elif argv[:3] == ["go", "test", "-list"]:
            stdout = "TestRun\nok  \texample.com/x/internal/app\t0.001s\n"
        elif argv[:2] == ["go", "test"]:
            stdout = json.dumps({"Action": "pass", "Test": "TestRun"}) + "\n"
        containment.LEDGER.append({"step": p.profile.step, "contained": True})
        return containment.Outcome(subprocess.CompletedProcess(argv, 0, stdout, ""), True)


def test_verify_end_to_end_with_a_faked_container(repo, monkeypatch):
    root, sha, source = repo
    L = ledger(sha)
    fake = FakePodman()
    monkeypatch.setattr(containment, "run", fake)
    d = diffs(root)
    rec = H.verify(root, sha, d["go"], L, source, out=root / "out" / "v.json")
    assert rec["applies"] and rec["verdict"] == "pass" and rec["summary"] == {"F2P": 1, "P2P": 1} and rec["regressions"] == []
    rows = {r["id"]: r for r in rec["tests"]}
    assert rows["tests/test_core.py::test_derive"]["class"] == "F2P" and rows["internal/app/app_test.go::TestRun"]["class"] == "P2P"
    # per tree: go build, go vet (the Go tree steps: app.go moves the Go build), go test -list, go test, pytest
    assert rec["containment"] == {"steps": [{"step": "verify", "contained": True}] * 10, "all_contained": True}
    assert [p.profile.step for p in fake.plans] == ["verify"] * 10 and all(p.profile.network == "none" for p in fake.plans)
    assert [list(p.command[:2]) for p in fake.plans[:4]] == [["go", "build"], ["go", "vet"], ["go", "test"], ["go", "test"]]
    assert rec["build_summary"] == {"P2P": 2} and rec["build_failures"] == [] and [b["kind"] for b in rec["build"]] == ["build", "vet"]
    assert all(str(source / ".venv") in p.ro for p in fake.plans), "the source's venv rides read-only"
    assert rec["environment"]["links"][0] == [".venv", str(source / ".venv")] and any(kv.startswith("PYTHONPATH=") for kv in rec["environment"]["env"])
    assert json.loads((root / "out" / "v.json").read_text())["verdict"] == "pass"
    assert not (Path(os.environ["HOBBES_CACHE_DIR"]) / "verify").exists() or not any((Path(os.environ["HOBBES_CACHE_DIR"]) / "verify").iterdir()), "scratch cleaned"
    # a diff that does not apply is a verdict, not an exception
    bad = d["derive"].replace("-    return os.sep + str(x)\n", "-    return nothing\n")
    rec2 = H.verify(root, sha, bad, L, source)
    assert rec2["verdict"] == "not-applied" and not rec2["applies"] and "apply_error" in rec2
    # nothing reached → no-tests
    rec3 = H.verify(root, sha, d["new"], L, source)
    assert rec3["verdict"] == "no-tests" and rec3["tests"] == []
    # an empty diff is its own verdict (arm T with nothing changed), not a failed apply
    assert H.verify(root, sha, "", L, source)["verdict"] == "empty-diff"
    # a ledger at another SHA is refused
    with pytest.raises(ValueError):
        H.verify(root, "0" * 40, d["derive"], L, source)


def test_an_id_pytest_cannot_collect_is_dropped_and_the_rest_rerun(repo, monkeypatch):
    # the testmap listed a fixture as a test (the 2026-09-04 calibration): one bad id aborts pytest (rc 4), so the harness drops it and reruns
    root, sha, source = repo
    L = ledger(sha)
    L.tests.append({"id": "tests/test_core.py::tests_fixture", "file": "tests/test_core.py", "framework": "pytest", "line": 1, "reaches": ["pkg.core.derive"], "reaches_modules": [], "symbol": "tests.test_core.tests_fixture"})
    calls = []

    def fake(p, *, timeout):
        argv = list(p.command)
        calls.append(argv)
        if any(a.endswith("::tests_fixture") for a in argv):
            return containment.Outcome(subprocess.CompletedProcess(argv, 4, "", f"ERROR: not found: {p.cwd}/tests/test_core.py::tests_fixture\n(no match in any of [<Module test_core.py>])\n"), True)
        rep = next(a for a in argv if a.startswith("--junit-xml="))[len("--junit-xml="):]
        Path(rep).parent.mkdir(parents=True, exist_ok=True)
        Path(rep).write_text('<testsuites><testsuite><testcase classname="tests.test_core" name="test_derive"/></testsuite></testsuites>')
        return containment.Outcome(subprocess.CompletedProcess(argv, 0, "", ""), True)
    monkeypatch.setattr(containment, "run", fake)
    rec = H.verify(root, sha, diffs(root)["derive"], L, source)
    rows = {r["id"]: r for r in rec["tests"]}
    assert rec["verdict"] == "pass" and rows["tests/test_core.py::test_derive"]["class"] == "P2P" and rows["tests/test_core.py::tests_fixture"]["class"] == "uncollected"
    assert "could not collect" in rows["tests/test_core.py::tests_fixture"]["note"] and rec["commands"][0]["dropped"] == ["tests/test_core.py::tests_fixture"]
    assert len(calls) == 4 and "tests/test_core.py::tests_fixture" not in calls[1], "dropped on the rerun, on both trees"


def test_a_test_file_the_diff_creates_is_not_asked_of_the_baseline(repo, monkeypatch):
    # the first calibration: the baseline command named a created test file, pytest refused the whole command, every baseline read as error → 552 false F2P
    root, sha, source = repo
    L = ledger(sha)
    d = diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", 'str(x) + "!"'), "tests/test_new.py": "def test_new():\n    assert True\n"})
    calls = []

    def fake(p, *, timeout):
        argv = list(p.command)
        calls.append(argv)
        assert not any(a.startswith("tests/test_new.py") for a in argv) or (Path(p.cwd) / "tests" / "test_new.py").exists(), "a missing file must not be asked for"
        rep = next(a for a in argv if a.startswith("--junit-xml="))[len("--junit-xml="):]
        Path(rep).parent.mkdir(parents=True, exist_ok=True)
        cases = '<testcase classname="tests.test_core" name="test_derive"/>' + ('<testcase classname="tests.test_new" name="test_new"/>' if any(a.startswith("tests/test_new.py") for a in argv) else "")
        Path(rep).write_text(f"<testsuites><testsuite>{cases}</testsuite></testsuites>")
        return containment.Outcome(subprocess.CompletedProcess(argv, 0, "", ""), True)
    monkeypatch.setattr(containment, "run", fake)
    rec = H.verify(root, sha, d, L, source)
    rows = {r["id"]: r for r in rec["tests"]}
    assert rec["verdict"] == "pass" and rows["tests/test_core.py::test_derive"]["class"] == "P2P" and rows["tests/test_new.py::test_new"]["class"] == "new-pass"
    assert len(calls) == 2 and "tests/test_new.py" in calls[0] and "tests/test_new.py" not in calls[1]


def test_a_refusal_never_falls_back_to_the_host(repo, monkeypatch):
    root, sha, source = repo
    L = ledger(sha)

    def refuse(p, *, timeout):
        raise containment.ContainmentRefusal("verify refused: repo code never executes on the host")
    monkeypatch.setattr(containment, "run", refuse)
    with pytest.raises(containment.ContainmentRefusal):
        H.verify(root, sha, diffs(root)["derive"], L, source)


def test_environment_links_mounts_and_pre_command(repo):
    root, _, source = repo
    env = H.environment(source, root, container_root="/work", gocache="/sessions/S/go-build")
    assert env.links == [(".venv", str(source / ".venv")), ("web/node_modules", str(source / "web" / "node_modules"))]
    assert set(env.ro) == {str(source / ".venv"), str(source / "web" / "node_modules")}
    assert "GOCACHE=/sessions/S/go-build" in env.env and "GOPROXY=off" in env.env and "PYTHONPATH=/work/src:/work" in env.env
    assert env.env.count("PYTHONDONTWRITEBYTECODE=1") == 1 and "GIT_COMMITTER_EMAIL=verify@hobbes.local" in env.env
    assert env.python == {"": ".venv/bin/python3"}
    assert H.pre_command(env) == (f"printf '%s\\n' .venv web/node_modules >> /work/.git/info/exclude && ln -sfn {source / '.venv'} /work/.venv && "
                                  f"ln -sfn {source / 'web' / 'node_modules'} /work/web/node_modules")
    assert H.pre_command(H.Environment(source="s")) == "true"
    H.link_deps(env, root)
    assert (root / ".venv").is_symlink() and os.readlink(root / "web" / "node_modules") == str(source / "web" / "node_modules")
    H.link_deps(env, root)  # idempotent
    assert H.environment(source, root).links == env.links, "a linked tree is not walked as a manifest dir"


def test_arm_o_brief_policy_command_and_patch_grounding(repo, tmp_path):
    root, sha, source = repo
    L = ledger(sha)
    brief = H.o_brief("Fix derive.", None, "SeedError: nothing", "repo", sha)
    assert "## Task" in brief and "resolved nothing specific" in brief and "an aid, not a boundary" in brief and "## Environment" not in brief
    env0 = H.environment(source, root, container_root="/work")
    assert env0.notes and "read-only" in env0.notes[0] and any("vitest" in n for n in env0.notes) and any("python -m pytest" in n for n in env0.notes)
    assert "## Environment (the harness's, not the task's)" in H.o_brief("Fix derive.", None, "x", "repo", sha, env=env0)
    agent = H.o_agent_dir(None, L, tmp_path / "agent")
    pol = (agent / "policy.yaml").read_text()
    assert "git push*" in pol and "scope: agent" in pol and json.loads((agent / "context.json").read_text())["interior"] == []
    env = H.environment(source, root, container_root="/work", gocache="/sessions/S-1/go-build")
    cmd = H.session_command("/bin/hobbes-session", root, sha, tmp_path / "b.md", agent, env, base_url="https://llm/v1", model="m", session_id="S-1", sessions_root=tmp_path / "s")
    joined = " ".join(cmd)
    assert cmd[:2] == ["/bin/hobbes-session", "start"] and "--ref " + sha in joined and "--box " + str(H.CALVIN_BOX) in joined
    assert "--loop-arg=--mcp-tools=exec" in cmd and "--network pasta" in joined and "--commit-on-exit" in cmd and "--escalation-timeout 5s" in joined
    assert f"--loop-arg=--token-budget={H.O_TOKEN_BUDGET}" in cmd, "step 6: the per-session token ceiling rides the argv"
    assert cmd.count("--mount") == len(env.ro) and f"--mount {source / '.venv'}" in joined and "--pre printf" in joined and "&& ln -sfn" in joined
    assert "--mcp-tools" not in " ".join(H.session_command("/bin/hobbes-session", root, sha, tmp_path / "b.md", agent, env, base_url="u", model="m", session_id="S-2", sessions_root=tmp_path, knowledge=True))
    assert H.CALVIN_BOX.exists() and "node --test*" in H.CALVIN_BOX.read_text()
    # a session's patch through the grounder: the raw-diff route, HSR over call sites
    t = T.build_template("Change `derive`.", L, root, None)
    g = H.ground_patch(t, diffs(root)["helper"], L, root)
    assert g["references"]["NULL"] == 1 and g["null"][0]["term"] == "helper" and g["fills_attribution"]
    # dry run: the plan is derived at the SHA from the task text, the brief and agent dir written, nothing launched
    (tmp_path / "g").mkdir()
    (tmp_path / "g" / "graph.json").write_text(json.dumps(L.graph))
    (tmp_path / "g" / "tests.json").write_text(json.dumps({"sha": sha, "schema_version": 4, "tests": L.tests}))
    rec = H.run_o(root, sha, "Change `derive` in src/pkg/core.py so it appends a bang.", L, source, (tmp_path / "g" / "graph.json", tmp_path / "g" / "tests.json"),
                  session_bin="/bin/hobbes-session", base_url="u", model="m", session_id="S-3", sessions_root=tmp_path / "s", out_dir=tmp_path / "o", dry_run=True)
    assert rec["arm"] == "O" and rec["command"][0] == "/bin/hobbes-session" and (tmp_path / "o" / "S-3.brief.md").exists() and (tmp_path / "o" / "S-3.agent" / "policy.yaml").exists()
    assert (root / ".hobbes" / "derived" / "graph.json").exists() and rec["brief_chars"] > 0
    # D-x: the session is launched from the cut repo, never the owned clone, with the parent's graph beside it
    cut = rec["command"][rec["command"].index("--repo") + 1]
    assert cut == str(tmp_path / "o" / "S-3.repo") and rec["session_repo"]["errors"] == [] and rec["session_repo"]["base"] == sha
    assert (Path(cut) / ".hobbes" / "derived" / "graph.json").exists()
    assert rec["plan"]["refusal"] is None or "Error" in rec["plan"]["refusal"]


def test_hobbes_verify_cli(repo, monkeypatch, capsys):
    from hobbes import cli
    root, sha, source = repo
    L = ledger(sha)
    d = diffs(root)  # before the derived dir: diff_for cleans untracked files
    (root / ".hobbes" / "derived").mkdir(parents=True)
    (root / ".hobbes" / "derived" / "graph.json").write_text(json.dumps(L.graph))
    (root / ".hobbes" / "derived" / "tests.json").write_text(json.dumps({"sha": sha, "schema_version": 4, "tests": L.tests}))
    (root / "cand.diff").write_text(d["go"])
    monkeypatch.setattr(containment, "run", FakePodman())
    assert cli.main(["verify", str(root / "cand.diff"), "--repo", str(root), "--source", str(source), "--out", str(root / "v.json")]) == 0
    err = capsys.readouterr().err
    assert "pass" in err and "'F2P': 1" in err and json.loads((root / "v.json").read_text())["verdict"] == "pass"
    (root / "bad.diff").write_text(d["derive"].replace("-    return os.sep + str(x)\n", "-    return nothing\n"))
    assert cli.main(["verify", str(root / "bad.diff"), "--repo", str(root), "--source", str(source)]) == 1
    assert cli.main(["verify", str(root / "missing.diff"), "--repo", str(root)]) == 2

    def refuse(p, *, timeout):
        raise containment.ContainmentRefusal("no image")
    monkeypatch.setattr(containment, "run", refuse)
    assert cli.main(["verify", str(root / "cand.diff"), "--repo", str(root), "--source", str(source)]) == 3


# ------------------------------------------------------------------ Go (calvin-m0-go §2.3)

GO_CALC = "package calc\n\nvar Base = 1\n\nfunc Add(a, b int) int { return a + b + Base - 1 }\n\nfunc Sub(a, b int) int { return a - b }\n"
GO_CALC_TEST = "package calc\n\nimport \"testing\"\n\nfunc TestAdd(t *testing.T) {}\n\nfunc TestSub(t *testing.T) {}\n"
GO_GEN = "package main\n\nimport \"example.com/g/calc\"\n\n//go:generate go run . ../../data/out.txt\n\nfunc main() { _ = calc.Add }\n"


@pytest.fixture
def gorepo(tmp_path, monkeypatch):
    """A Go module with a generator whose output the repo commits (gitleaks' shape: `cmd/generate/config` → `config/gitleaks.toml`)."""
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "gorepo"
    files = {"go.mod": "module example.com/g\n\ngo 1.22\n", "calc/calc.go": GO_CALC, "calc/calc_test.go": GO_CALC_TEST,
             "cmd/gen/main.go": GO_GEN, "data/out.txt": "v1\n", "README.md": "g\n", "other/doc.txt": "x\n"}
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "one")
    sha = _git(root, "rev-parse", "HEAD").strip()
    graph = {"sha": sha, "schema_version": 4, "built_by": {"sha": "abc"}, "containment": {"all_contained": True},
             "nodes": [{"id": "calc/calc", "kind": "module", "path": "calc/calc.go"}, {"id": "calc/calc_test", "kind": "module", "path": "calc/calc_test.go"},
                       {"id": "cmd/gen/main", "kind": "module", "path": "cmd/gen/main.go"}],
             "symbols": [{"id": "calc/calc.Add", "module": "calc/calc", "name": "Add", "qualname": "Add", "kind": "function", "line": 5, "end_line": 5},
                         {"id": "calc/calc.Sub", "module": "calc/calc", "name": "Sub", "qualname": "Sub", "kind": "function", "line": 7, "end_line": 7},
                         {"id": "cmd/gen/main.main", "module": "cmd/gen/main", "name": "main", "qualname": "main", "kind": "function", "line": 7, "end_line": 7}],
             "symbol_edges": [], "module_edges": []}
    tests = {"sha": sha, "tests": [
        {"id": "calc/calc_test.go::TestAdd", "file": "calc/calc_test.go", "framework": "go-test", "line": 5, "reaches": ["calc/calc.Add"], "reaches_modules": []},
        {"id": "calc/calc_test.go::TestGone", "file": "calc/calc_test.go", "framework": "go-test", "line": 9, "reaches": ["calc/calc.Add"], "reaches_modules": []},
        {"id": "calc/calc_test.go::TestSub", "file": "calc/calc_test.go", "framework": "go-test", "line": 7, "reaches": ["calc/calc.Sub"], "reaches_modules": []}]}
    return root, sha, T.Ledger(graph, tests)


class GoFake:
    """Answers `containment.run` for the go tool from the tree it is pointed at: generate rewrites data/out.txt from calc.go, `list -deps` names the generator's closure, build fails on a `BROKEN` mark, `test -list` and `test` read calc_test.go."""

    def __init__(self, flakes: int = 0):
        self.plans = []
        self.flakes = flakes  # the first *flakes* generations fail as a random draw would

    def __call__(self, p, *, timeout):
        self.plans.append(p)
        argv, cwd = list(p.command), Path(p.cwd)
        calc = (cwd / "calc" / "calc.go").read_text()
        names = re.findall(r"(?m)^func (Test\w+)\(", (cwd / "calc" / "calc_test.go").read_text())
        out, rc = "", 0
        if argv[:2] == ["go", "generate"]:
            if self.flakes or "NOVALID" in calc:  # a validation that fails: exits before it writes, as gitleaks' log.Fatal does
                self.flakes = max(self.flakes - 1, 0)
                containment.LEDGER.append({"step": p.profile.step, "contained": True})
                return containment.Outcome(subprocess.CompletedProcess(argv, 1, "", "FTL Failed to Validate. True positive was not detected by regex.\n"), True)
            (cwd / "data" / "out.txt").write_text("base=2\n" if "Base = 2" in calc else "v1\n")
        elif argv[:3] == ["go", "list", "-deps"]:
            out = f"/usr/local/go/src/fmt\n{cwd / 'calc'}\n{cwd / 'cmd' / 'gen'}\n"
        elif argv[:2] == ["go", "build"]:
            rc = 1 if "BROKEN" in calc else 0
        elif argv[:3] == ["go", "test", "-list"]:
            out = "".join(n + "\n" for n in names if re.search(argv[3], n)) + "ok  \texample.com/g/calc\t0.01s\n"
        elif argv[:2] == ["go", "test"]:
            pat = argv[argv.index("-run") + 1] if "-run" in argv else "."
            out = "".join(json.dumps({"Action": "pass", "Test": n}) + "\n" for n in names if re.search(pat, n))
        containment.LEDGER.append({"step": p.profile.step, "contained": True})
        return containment.Outcome(subprocess.CompletedProcess(argv, rc, out, ""), True)


def test_go_selection_package_grain_and_commands(gorepo):
    root, sha, L = gorepo
    env = H.environment(root, root)
    body = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1", "a + b")})
    s = H.select_tests(L, body)  # inside Add's span: symbol grain, the testmap's ids by name
    assert [(t["id"], t["grain"]) for t in s.tests] == [("calc/calc_test.go::TestAdd", "symbol"), ("calc/calc_test.go::TestGone", "symbol")]
    c, = H.commands(s, root, env, root / "r")
    assert c.argv == ["go", "test", "-json", "-count=1", "-run", "^(TestAdd|TestGone)$", "./calc/"] and c.grain == "symbol"
    assert c.list_argv == ["go", "test", "-list", "^(TestAdd|TestGone)$", "./calc/"]
    var = diff_for(root, {"calc/calc.go": GO_CALC.replace("Base = 1", "Base = 2")})
    s = H.select_tests(L, var)  # a package-level var, outside every span: the package's tests, whole
    assert {t["grain"] for t in s.tests} == {"package"} and len(s.tests) == 3
    c, = H.commands(s, root, env, root / "r")
    assert c.argv == ["go", "test", "-json", "-count=1", "./calc/"] and c.list_argv[3] == "." and c.grain == "package"
    new = diff_for(root, {"calc/extra.go": "package calc\n\nfunc Mul(a, b int) int { return a * b }\n"})
    assert {t["grain"] for t in H.select_tests(L, new).tests} == {"package"}, "a created file shares its package's tests"
    assert H.select_tests(L, diff_for(root, {"README.md": "h\n"})).tests == []
    # the tree steps' reach: a path moves the Go build if it is Go, a module file, or sits beside Go files
    assert H.go_roots(root, ["calc/calc.go"]) == [""] and H.go_roots(root, ["calc/new.go", "go.sum"]) == [""]
    assert H.go_roots(root, ["README.md", "other/doc.txt", "data/out.txt"]) == [], "no Go file beside them"
    assert H.go_directives(root, "") == {"cmd/gen": "cmd/gen/main.go"}
    assert H._go_target("cmd/gen", "") == "./cmd/gen/" and H._go_target("", "") == "." and H._go_target("sub/x", "sub") == "./x/"
    (Path(os.environ["HOBBES_CACHE_DIR"]) / "go" / "mod").mkdir(parents=True)
    env = H.environment(root, root)
    assert env.ro_cache == [str(Path(os.environ["HOBBES_CACHE_DIR"]) / "go" / "mod")] and "GOFLAGS=-mod=mod -buildvcs=false" in env.env
    assert any("module cache is mounted read-only" in n for n in env.notes) and env.record()["ro_cache"] == env.ro_cache


def test_go_verify_regenerates_guards_and_builds(gorepo, monkeypatch):
    root, sha, L = gorepo
    (Path(os.environ["HOBBES_CACHE_DIR"]) / "go" / "mod").mkdir(parents=True)
    fake = GoFake()
    monkeypatch.setattr(containment, "run", fake)
    var = diff_for(root, {"calc/calc.go": GO_CALC.replace("Base = 1", "Base = 2")})
    rec = H.verify(root, sha, var, L, root)
    rows = {r["id"]: r for r in rec["tests"]}
    assert rec["verdict"] == "pass" and rec["harness_version"] == 2 and rec["containment"]["all_contained"]
    assert rows["calc/calc_test.go::TestAdd"]["class"] == "P2P" and rows["calc/calc_test.go::TestSub"]["class"] == "P2P"
    assert rows["calc/calc_test.go::TestGone"]["class"] == "uncollected" and "go test -list" in rows["calc/calc_test.go::TestGone"]["note"]
    gen = rows["cmd/gen/main.go::go:generate"]  # the generator's closure holds calc/: its run guards the edit
    assert (gen["framework"], gen["origin"], gen["grain"], gen["class"]) == ("go-generate", "generate", "deps", "P2P")
    assert [b["id"] for b in rec["build"]] == [".::go build ./...", ".::go vet ./..."] and rec["build_summary"] == {"P2P": 2}
    g = rec["go"]["generated"]
    assert g["candidate"][0]["changed"] == ["data/out.txt"] and "+base=2" in g["candidate"][0]["diff"] and g["baseline"][0]["changed"] == []
    assert g["candidate"][0]["deps"] == ["calc", "cmd/gen"], "the closure inside the worktree; the stdlib's dirs dropped"
    cand = [list(p.command[:3]) for p in fake.plans[:6]]
    assert cand == [["go", "generate", "./cmd/gen/"], ["go", "list", "-deps"], ["go", "build", "./..."], ["go", "vet", "./..."], ["go", "test", "-list"], ["go", "test", "-json"]]
    cache = os.environ["HOBBES_CACHE_DIR"]
    assert all(p.ro_cache == (f"{cache}/go/mod",) for p in fake.plans), "the module cache rides read-only on every step (C-92)"
    # a diff that does not compile is build-fail, not a test failure
    broke = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1 }", "a + b + Base - 1 } // BROKEN")})
    rec = H.verify(root, sha, broke, L, root)
    assert rec["verdict"] == "build-fail" and rec["build_failures"] == [".::go build ./..."] and rec["regressions"] == []
    # a test the diff deletes is removed, not uncollected; a testmap id absent on both trees stays uncollected
    gone = diff_for(root, {"calc/calc_test.go": GO_CALC_TEST.replace("\nfunc TestSub(t *testing.T) {}\n", "")})
    rec = H.verify(root, sha, gone, L, root)
    rows = {r["id"]: r for r in rec["tests"]}
    assert rec["verdict"] == "pass" and rows["calc/calc_test.go::TestSub"]["class"] == "removed" and rows["calc/calc_test.go::TestGone"]["class"] == "uncollected"
    assert rows["calc/calc_test.go::TestAdd"]["grain"] == "file" and "cmd/gen/main.go::go:generate" in rows
    # a generation whose closure the diff does not reach is a build row, and guards nothing
    other = diff_for(root, {"other/other.go": "package other\n"})
    rec = H.verify(root, sha, other, L, root)
    assert rec["verdict"] == "no-tests" and rec["tests"] == [] and [b["kind"] for b in rec["build"]] == ["build", "vet", "generate"]


class BenchGoFake(GoFake):
    """As `GoFake`, but ``go test -list`` also reports a ``Benchmark*`` function (real ``go test -list`` matches
    Test/Benchmark/Example/Fuzz names alike) while ``go test`` itself (no ``-bench``) never executes it — the pre-existing
    guard D-p found: listed (not ``uncollected``), never run (``not-run`` on both trees)."""

    def __call__(self, p, *, timeout):
        argv = list(p.command)
        if argv[:3] == ["go", "test", "-list"]:
            self.plans.append(p)
            cwd = Path(p.cwd)
            names = re.findall(r"(?m)^func (Test\w+)\(", (cwd / "calc" / "calc_test.go").read_text())
            bench = re.findall(r"(?m)^func (Benchmark\w+)\(", (cwd / "calc" / "calc_test.go").read_text())
            out = "".join(n + "\n" for n in names + bench if re.search(argv[3], n)) + "ok  \texample.com/g/calc\t0.01s\n"
            containment.LEDGER.append({"step": p.profile.step, "contained": True})
            return containment.Outcome(subprocess.CompletedProcess(argv, 0, out, ""), True)
        return super().__call__(p, timeout=timeout)


def test_a_benchmark_guard_that_plain_go_test_never_runs_decides_nothing(gorepo, monkeypatch):
    """D-p (calvin-m0-go-r2, WP-14; found by WP-13 on `d22371873bd8`): a pre-existing ``Benchmark*`` the testmap names as a
    guard (`reaches` an edited symbol) is listed by ``go test -list`` (so not ``uncollected``) but never executed by plain
    ``go test`` on either tree — it reads ``not-run``/``not-run``. Before the fix, `classify` folded that pair into the
    `not-run` class and `FAILING` named that class, so `score` read `fail` before the vacuous/`gold_tests` question was ever
    reached, though nothing about this diff was known to be wrong. After the fix the row decides nothing either way: the
    other guard (which does run and pass) still carries the verdict to `pass`, and the benchmark row is not `executed`."""
    root, sha, L = gorepo
    (root / "calc" / "calc_test.go").write_text(GO_CALC_TEST.rstrip("\n") + "\n\nfunc BenchmarkAdd(b *testing.B) {}\n")
    _git(root, "commit", "-aqm", "a pre-existing benchmark, unrelated to this diff")
    sha2 = _git(root, "rev-parse", "HEAD").strip()
    L2 = T.Ledger({**L.graph, "sha": sha2}, {"tests": L.tests + [{"id": "calc/calc_test.go::BenchmarkAdd", "file": "calc/calc_test.go",
                  "framework": "go-test", "line": 11, "reaches": ["calc/calc.Add"], "reaches_modules": []}]})
    fake = BenchGoFake()
    monkeypatch.setattr(containment, "run", fake)
    var = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1", "a + b")})
    rec = H.verify(root, sha2, var, L2, root)
    rows = {r["id"]: r for r in rec["tests"]}
    bench = rows["calc/calc_test.go::BenchmarkAdd"]
    assert (bench["candidate"], bench["baseline"], bench["class"]) == ("not-run", "not-run", "not-run"), "listed, never run: neither tree executed it"
    assert H.classify("not-run", "not-run") == "not-run" and "not-run" not in H.FAILING
    assert rec["verdict"] == "pass" and rec["guarding_tests_executed"]["count"] == 1, "TestAdd (P2P) alone carries pass; the benchmark is not executed"
    assert "calc/calc_test.go::BenchmarkAdd" not in rec["guarding_tests_executed"]["ids"]
    assert rec["regressions"] == [] and "calc/calc_test.go::BenchmarkAdd" not in rec.get("faults", [])


def test_go_generation_retries_a_random_draw_and_fails_a_real_one(gorepo, monkeypatch):
    # gitleaks' generator validates each rule on true positives reggen draws with a clock seed: one failure can be the draw's
    root, sha, L = gorepo
    fake = GoFake(flakes=1)
    monkeypatch.setattr(containment, "run", fake)
    var = diff_for(root, {"calc/calc.go": GO_CALC.replace("Base = 1", "Base = 2")})
    rec = H.verify(root, sha, var, L, root)
    gen = rec["go"]["steps"]["candidate"]["cmd/gen/main.go::go:generate"]
    assert gen["attempts"] == ["fail", "pass"] and gen["flaky"] and "not detected" in gen["failures"][0]
    assert rec["go"]["generated"]["candidate"][0]["changed"] == ["data/out.txt"], "the passing attempt's output is the tree's"
    assert rec["verdict"] == "pass" and {r["id"]: r for r in rec["tests"]}["cmd/gen/main.go::go:generate"]["class"] == "P2P"
    assert rec["go"]["steps"]["baseline"]["cmd/gen/main.go::go:generate"]["attempts"] == ["pass"] and not rec["go"]["steps"]["baseline"]["cmd/gen/main.go::go:generate"]["flaky"]
    # a validation the diff breaks fails every attempt: a regression of the guard, not a flake
    fake = GoFake()
    monkeypatch.setattr(containment, "run", fake)
    bad = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1 }", "a + b + Base - 1 } // NOVALID")})
    rec = H.verify(root, sha, bad, L, root)
    gen = rec["go"]["steps"]["candidate"]["cmd/gen/main.go::go:generate"]
    assert gen["attempts"] == ["fail"] * H.GENERATE_ATTEMPTS and not gen["flaky"] and len(gen["failures"]) == H.GENERATE_ATTEMPTS
    assert rec["verdict"] == "fail" and rec["regressions"] == ["cmd/gen/main.go::go:generate"]
    assert sum(list(p.command[:2]) == ["go", "generate"] for p in fake.plans) == H.GENERATE_ATTEMPTS + 1, "three on the candidate, one on the baseline"


def test_score_reads_build_rows():
    rec = {"tests": [{"id": "t", "candidate": "pass", "baseline": "pass", "origin": "guard"}], "build": [{"id": "b", "candidate": "fail", "baseline": "fail"}], "baseline": True}
    assert H.score(rec)["verdict"] == "pass" and rec["faults"] == ["b"] and rec["build_summary"] == {"F2F": 1}, "a build broken on both trees is the environment's"
    rec["build"][0]["baseline"] = "pass"
    assert H.score(rec)["verdict"] == "build-fail" and rec["build_failures"] == ["b"]
    assert H.score({"tests": [], "build": [{"id": "b", "candidate": "fail", "baseline": None}], "baseline": False})["verdict"] == "build-fail"
    old = H.score({"tests": [{"id": "t", "candidate": "pass", "baseline": "pass", "origin": "guard"}], "baseline": True})
    assert "build_summary" not in old and "build_failures" not in old, "a record from before the Go steps rescores unchanged"


def test_guarding_tests_executed_and_vacuous_pass():
    # calvin-m0-go-r2 §2.3: a build-clean row that reaches no *executed* guarding test is `vacuous`, not `pass` —
    # unless `gold_tests` (computed separately, since it takes its own `verify` run) itself reads `pass`.
    rec = {"tests": [{"id": "g", "candidate": "pass", "baseline": "pass", "origin": "guard"},
                      {"id": "u", "candidate": "uncollected", "baseline": "uncollected", "origin": "guard"},
                      {"id": "touch", "candidate": "pass", "baseline": None, "origin": "touched"}], "baseline": True}
    scored = H.score(rec)
    assert scored["verdict"] == "pass" and scored["guarding_tests_executed"] == {"count": 2, "ids": ["g", "touch"]}, "a touched test file's own tests guard too; uncollected did not execute"
    novacuous = {"tests": [{"id": "gen", "candidate": "pass", "baseline": "pass", "origin": "generate"}], "baseline": True}
    assert H.score(novacuous)["verdict"] == "vacuous" and novacuous["guarding_tests_executed"] == {"count": 0, "ids": []}
    assert H.score(dict(novacuous), gold_tests={"verdict": "n/a", "ids": []})["verdict"] == "vacuous", "gold changed no test file: no second door"
    assert H.score(dict(novacuous), gold_tests={"verdict": "conflict", "ids": []})["verdict"] == "vacuous"
    assert H.score(dict(novacuous), gold_tests={"verdict": "fail", "ids": ["x"]})["verdict"] == "vacuous"
    rescued = H.score(dict(novacuous), gold_tests={"verdict": "pass", "ids": ["x_test.go::TestX"]})
    assert rescued["verdict"] == "pass" and rescued["gold_tests"]["verdict"] == "pass", "gold's own test changes carry the row"
    # a row a build breaks never reaches the vacuous question: build-fail outranks it, though the count is still recorded
    broken = H.score({"tests": [], "build": [{"id": "b", "candidate": "fail", "baseline": "pass"}], "baseline": True})
    assert broken["verdict"] == "build-fail" and broken["guarding_tests_executed"] == {"count": 0, "ids": []}


def test_gold_test_hunks_splits_test_files_from_a_diff(repo):
    root, sha, source = repo
    d = diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", 'str(x) + "!"'), "tests/test_core.py": TEST_CORE + "\ndef test_new():\n    assert True\n"})
    hunks = H.gold_test_hunks(d)
    assert [p for p, _ in H.split_patch(hunks)] == ["tests/test_core.py"] and "src/pkg/core.py" not in hunks and "def test_new" in hunks
    assert H.gold_test_hunks(diff_for(root, {"src/pkg/core.py": CORE.replace("str(x)", 'str(x) + "!"')})) == "", "a gold diff touching no test file yields no hunks"
    assert H.gold_non_test_hunks(d) + hunks == d or set(p for p, _ in H.split_patch(H.gold_non_test_hunks(d) + hunks)) == set(p for p, _ in H.split_patch(d))


def test_is_test_support_path_and_a_fixture_travels_only_beside_a_test_hunk(repo):
    # WP-11a-1: a testdata/-shaped path is test-support even though it is not itself a test file — but only
    # when a real test-file hunk is present too; a fixture with no test change beside it is not "gold's own
    # test changes" (§2.3), so `gold_test_hunks` stays empty for it, as it does for no test file at all.
    assert H.is_test_support_path("testdata/config/extend_rule_allowlist.toml") and not H.is_test_path("testdata/config/extend_rule_allowlist.toml")
    assert H.is_test_support_path("calc/testdata/greeting.txt") and H.is_test_support_path("web/__snapshots__/a.snap")
    assert not H.is_test_support_path("config/config.go"), "a production path is never named testdata/"
    root, sha, source = repo
    fixture_alone = diff_for(root, {"testdata/config/x.toml": "id = 1\n"})
    assert H.gold_test_hunks(fixture_alone) == "", "a fixture with no test hunk beside it is not gold's own test changes"
    with_test = diff_for(root, {"tests/test_core.py": TEST_CORE + "\ndef test_new():\n    assert True\n", "testdata/config/x.toml": "id = 1\n"})
    hunks = H.gold_test_hunks(with_test)
    assert {p for p, _ in H.split_patch(hunks)} == {"tests/test_core.py", "testdata/config/x.toml"}


def test_gold_tests_verdict_build_fail_reads_undefined_symbols(gorepo, monkeypatch):
    # WP-11a §3: a `gold_tests` build-fail names how many of them are gold's test naming a symbol the arm
    # named differently or never created, read off Go's own "undefined: X" in the failing build's stderr.
    root, sha, L = gorepo

    def fake(p, *, timeout):
        argv, cwd = list(p.command), Path(p.cwd)
        test_src = (cwd / "calc" / "calc_test.go").read_text()
        out, rc, err = "", 0, ""
        if argv[:3] == ["go", "list", "-deps"]:
            out = f"{cwd / 'calc'}\n"
        elif argv[:2] == ["go", "build"]:
            if "UsesUndeclaredHelper" in test_src:
                rc, err = 1, "./calc/calc_test.go:9:9: undefined: UsesUndeclaredHelper\n"
        elif argv[:3] == ["go", "test", "-list"]:
            names = re.findall(r"(?m)^func (Test\w+)\(", test_src)
            out = "".join(n + "\n" for n in names if re.search(argv[3], n))
        elif argv[:2] == ["go", "test"]:
            names = re.findall(r"(?m)^func (Test\w+)\(", test_src)
            pat = argv[argv.index("-run") + 1] if "-run" in argv else "."
            out = "".join(json.dumps({"Action": "pass", "Test": n}) + "\n" for n in names if re.search(pat, n))
        containment.LEDGER.append({"step": p.profile.step, "contained": True})
        return containment.Outcome(subprocess.CompletedProcess(argv, rc, out, err), True)
    monkeypatch.setattr(containment, "run", fake)
    arm = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1 }", "a + b + Base - 1 } // fixed")})
    gold_test = diff_for(root, {"calc/calc_test.go": GO_CALC_TEST + "\nfunc TestMul(t *testing.T) { UsesUndeclaredHelper() }\n"})
    r = H.gold_tests_verdict(root, sha, arm, gold_test, L, root)
    assert r["verdict"] == "build-fail" and r["undefined_symbols"] == ["UsesUndeclaredHelper"]


def test_gold_test_hunks_carries_a_testdata_fixture_a_test_needs(gorepo, monkeypatch):
    # the fixture-repo control (WP-11a-1): gitleaks' TestTranslate reads `testdata/config/extend_rule_allowlist.toml`,
    # a file gold's own diff adds beside `config_test.go` and is not itself a `_test.go` file; any arm — even a
    # perfect one that never touches testdata/ itself, since that is gold's fixture, not production code — must
    # still see it, or the test reads a stale fixture and fails for a reason that says nothing about the arm.
    root, sha, L = gorepo

    def fake(p, *, timeout):
        argv, cwd = list(p.command), Path(p.cwd)
        test_src = (cwd / "calc" / "calc_test.go").read_text()
        out, rc = "", 0
        if argv[:3] == ["go", "list", "-deps"]:
            out = f"{cwd / 'calc'}\n"
        elif argv[:3] == ["go", "test", "-list"]:
            names = re.findall(r"(?m)^func (Test\w+)\(", test_src)
            out = "".join(n + "\n" for n in names if re.search(argv[3], n))
        elif argv[:2] == ["go", "test"]:
            names = re.findall(r"(?m)^func (Test\w+)\(", test_src)
            pat = argv[argv.index("-run") + 1] if "-run" in argv else "."
            fixture = cwd / "calc" / "testdata" / "greeting.txt"
            ok = fixture.exists() and fixture.read_text() == "hi\n"
            out = "".join(json.dumps({"Action": "pass" if (n != "TestGreeting" or ok) else "fail", "Test": n}) + "\n" for n in names if re.search(pat, n))
        containment.LEDGER.append({"step": p.profile.step, "contained": True})
        return containment.Outcome(subprocess.CompletedProcess(argv, rc, out, ""), True)
    monkeypatch.setattr(containment, "run", fake)
    gold = diff_for(root, {"calc/calc_test.go": GO_CALC_TEST + "\nfunc TestGreeting(t *testing.T) {}\n", "calc/testdata/greeting.txt": "hi\n"})
    arm = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1 }", "a + b + Base - 1 } // fixed")})  # never touches testdata/ itself
    r = H.gold_tests_verdict(root, sha, arm, gold, L, root)
    assert r["verdict"] == "pass" and "calc/calc_test.go::TestGreeting" in r["ids"], "the fixture rode along with the test hunk"
    # THE CONTROL: gold's own non-test hunks, standing in for a perfect arm, must themselves read pass
    perfect = H.gold_non_test_hunks(gold)
    r2 = H.gold_tests_verdict(root, sha, perfect, gold, L, root)
    assert r2["verdict"] == "pass"


def test_gold_tests_verdict_end_to_end(gorepo, monkeypatch):
    root, sha, L = gorepo
    fake = GoFake()
    monkeypatch.setattr(containment, "run", fake)
    arm = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1 }", "a + b + Base - 1 } // fixed")})
    # the gold diff touches no test file: n/a, no run at all
    gold_notest = diff_for(root, {"calc/calc.go": GO_CALC.replace("Base = 1", "Base = 2")})
    assert H.gold_tests_verdict(root, sha, arm, gold_notest, L, root) == {"verdict": "n/a", "ids": []}
    assert fake.plans == [], "n/a is read off the diff alone, no verify"
    # the gold's own new test, applied on top of the arm's diff, runs and passes
    gold_test = diff_for(root, {"calc/calc_test.go": GO_CALC_TEST + "\nfunc TestMul(t *testing.T) {}\n"})
    r = H.gold_tests_verdict(root, sha, arm, gold_test, L, root)
    assert r["verdict"] == "pass" and "calc/calc_test.go::TestMul" in r["ids"] and r.get("failing", []) == []
    # the arm's own diff already rewrote the exact line the gold's test hunk needs as context: a conflict, not a fail
    arm_same_line = diff_for(root, {"calc/calc_test.go": GO_CALC_TEST.replace("func TestSub(t *testing.T) {}", "func TestSub(t *testing.T) { t.Log(1) }")})
    r2 = H.gold_tests_verdict(root, sha, arm_same_line, gold_test, L, root)
    assert r2["verdict"] == "conflict" and "apply_error" in r2
    # a diff that does not build at all cannot run the gold's tests either: its own verdict, `build-fail`, not `fail` or `conflict`
    broke = diff_for(root, {"calc/calc.go": GO_CALC.replace("a + b + Base - 1 }", "a + b + Base - 1 } // BROKEN")})
    r3 = H.gold_tests_verdict(root, sha, broke, gold_test, L, root)
    assert r3["verdict"] == "build-fail" and r3["build_failures"] == [".::go build ./..."] and r3["undefined_symbols"] == []
    assert H.classify("uncollected", "pass") == "removed" and H.classify("uncollected", "uncollected") == "uncollected"
