"""The local harness (Calvin M0 step 5): test selection from the testmap, per-framework commands and parsers, the baseline classes, `verify` end to end against a faked container, the environment binding, and arm O's brief, policy, session command and patch grounding — no podman, no model."""
import json
import os
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
    assert by["go-test"].argv == ["go", "test", "-json", "-count=1", "./internal/app/"] and by["go-test"].ids == ["internal/app/app_test.go::TestRun"]
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
    rec = {"tests": [{"id": "a", "candidate": "fail", "baseline": "fail"}, {"id": "b", "candidate": "not-run", "baseline": "pass"}, {"id": "c", "candidate": "pass", "baseline": "pass"}], "baseline": True}
    assert H.score(rec)["verdict"] == "pass" and rec["faults"] == ["a"] and rec["summary"] == {"F2F": 1, "removed": 1, "P2P": 1}
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
    assert rec["containment"] == {"steps": [{"step": "verify", "contained": True}] * 4, "all_contained": True}
    assert [p.profile.step for p in fake.plans] == ["verify"] * 4 and all(p.profile.network == "none" for p in fake.plans)
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
