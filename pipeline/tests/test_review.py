"""`hobbes review`: the concept-level PR review (M8, ADR-025)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from hobbes.extract.testmap import runner_excluded_trees
from hobbes.review import (
    FIXED,
    REGRESSED,
    STILL_FAILING,
    UNCHANGED,
    build_review,
    format_review,
    judge_soft,
    review_to_dict,
)

def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def write(repo: Path, rel: str, body: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A tiny Python repo: a parser that may import tree_sitter, a core
    module that may not, and one test guarding core."""
    repo = tmp_path
    git(repo, "init", "-q")
    write(repo, "pyproject.toml", '[project]\nname = "app"\nversion = "0"\n')
    write(repo, "src/app/__init__.py", "")
    write(repo, "src/app/parser.py", "import tree_sitter\n\n\ndef parse():\n    return 1\n")
    write(repo, "src/app/core.py", "def run():\n    return 2\n")
    write(repo, "tests/test_core.py", "from app import core\n\n\ndef test_run():\n    assert core.run() == 2\n")

    record = {
        "id": "I-1",
        "statement": "Only the parser parses source.",
        "scope": "src",
        "status": "confirmed",
        "check": "graph",
        "rule": {
            "kind": "forbidden-import",
            "importers": ["*"],
            "except": ["app.parser"],
            "imported": ["ext:tree_sitter"],
        },
        "guarded_by": [],
    }
    write(repo, ".hobbes/invariants/I-1.yaml", yaml.safe_dump(record, sort_keys=False))

    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    return repo


def test_each_pytest_config_governs_its_own_directory(tmp_path):
    """ADR-114: patterns match directory basenames below the config's own
    directory (its testpaths when it names some), and nowhere else."""
    write(tmp_path, "sub/pytest.ini", "[pytest]\nnorecursedirs = fix* data\n")
    write(tmp_path, "top/setup.cfg", "[metadata]\nname = x\n")  # no pytest section: states nothing
    paths = ["sub/fixtures/a.py", "sub/pkg/data/b.py", "sub/pkg/c.py", "other/fixtures/d.py", "top/fixtures/e.py"]
    for path in paths:
        write(tmp_path, path, "")
    assert runner_excluded_trees(tmp_path, paths) == (
        {"path": "sub/fixtures", "by": "pytest norecursedirs 'fix*' in sub/pytest.ini"},
        {"path": "sub/pkg/data", "by": "pytest norecursedirs 'data' in sub/pytest.ini"},
    )


def add_violation(repo: Path) -> None:
    """core.py starts importing tree_sitter — a forbidden import."""
    write(repo, "src/app/core.py", "import tree_sitter\n\n\ndef run():\n    return 2\n")


class TestInvariantMovement:
    def test_clean_range_needs_no_attention(self, repo):
        write(repo, "src/app/core.py", "def run():\n    return 3\n")
        git(repo, "commit", "-qam", "tweak")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert [i.movement for i in review.invariants] == [UNCHANGED]
        assert not review.needs_attention

    def test_a_new_violation_is_a_regression(self, repo):
        add_violation(repo)
        git(repo, "commit", "-qam", "break it")
        review = build_review(repo, "HEAD~1", "HEAD")
        (item,) = review.invariants
        assert item.movement == REGRESSED
        assert item.head.result == "fail"
        assert review.needs_attention
        assert [v.cite() for v in item.head.violations] == [
            "app.core -> ext:tree_sitter [src/app/core.py:1]"
        ]

    def test_pre_existing_breakage_is_not_this_changes_fault(self, repo):
        # The violation lands first, then an unrelated commit is reviewed.
        add_violation(repo)
        git(repo, "commit", "-qam", "break it")
        write(repo, "src/app/other.py", "def other():\n    return 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "unrelated")

        review = build_review(repo, "HEAD~1", "HEAD")
        (item,) = review.invariants
        # Still failing, but not a regression — this is the distinction
        # that keeps a review worth reading.
        assert item.movement == STILL_FAILING
        assert item.head.result == "fail"
        assert review.regressions == []

    def test_repairing_a_violation_reads_as_fixed(self, repo):
        add_violation(repo)
        git(repo, "commit", "-qam", "break it")
        write(repo, "src/app/core.py", "def run():\n    return 2\n")
        git(repo, "commit", "-qam", "fix it")

        review = build_review(repo, "HEAD~1", "HEAD")
        (item,) = review.invariants
        assert item.movement == FIXED
        assert item.head.result == "pass"
        assert not review.regressions

    def test_regressions_sort_first(self, repo):
        second = {
            "id": "I-2",
            "statement": "Something soft.",
            "scope": ".",
            "status": "confirmed",
            "check": "soft",
            "guarded_by": [],
        }
        write(repo, ".hobbes/invariants/I-2.yaml", yaml.safe_dump(second, sort_keys=False))
        add_violation(repo)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "break it")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.invariants[0].invariant.id == "I-1"
        assert review.invariants[0].movement == REGRESSED


class TestCoverageDelta:
    def test_new_code_no_test_reaches_is_the_finding(self, repo):
        write(repo, "src/app/billing.py", "def charge():\n    return 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add billing")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == ["app.billing"]
        assert review.needs_attention

    def test_new_code_with_a_test_is_clean(self, repo):
        write(repo, "src/app/billing.py", "def charge():\n    return 1\n")
        write(
            repo,
            "tests/test_billing.py",
            "from app import billing\n\n\ndef test_charge():\n    assert billing.charge() == 1\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add billing with a test")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == []
        assert not review.needs_attention

    def test_a_new_test_file_is_not_unguarded_code(self, repo):
        # Listing every new test as unguarded new code is the noise that
        # makes a coverage metric ignorable.
        write(
            repo,
            "tests/test_extra.py",
            "from app import core\n\n\ndef test_again():\n    assert core.run() == 2\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "another test")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == []

    def test_a_tree_pytest_is_told_to_skip_is_not_own_code(self, repo):
        # ADR-114: a fixture is a test's input; the tree comes from the
        # repo's stated norecursedirs, and the review says what it skipped.
        write(
            repo,
            "pyproject.toml",
            '[project]\nname = "app"\nversion = "0"\n\n'
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\nnorecursedirs = ["fixtures"]\n',
        )
        write(repo, "tests/fixtures/demo/lib.py", "def helper():\n    return 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a fixture")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == []
        assert review.coverage.fixture_trees == [
            {"path": "tests/fixtures", "by": "pytest norecursedirs 'fixtures' in pyproject.toml", "modules": 1}
        ]
        assert not review.needs_attention
        assert "fixture tree, not asked for a guard (C-154): tests/fixtures" in format_review(review)
        assert review_to_dict(review)["coverage"]["fixture_trees"] == review.coverage.fixture_trees

    def test_testdata_is_a_fixture_tree_only_inside_a_go_module(self, repo):
        write(repo, "pkg/testdata/gen.py", "def gen():\n    return 1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "testdata, no go.mod")
        review = build_review(repo, "HEAD~1", "HEAD")
        # Outside a Go module the name means nothing: it is own code.
        assert len(review.coverage.new_unguarded) == 1
        assert review.coverage.fixture_trees == []

        write(repo, "go.mod", "module example.com/app\n\ngo 1.22\n")
        write(repo, "pkg/testdata/more.py", "def more():\n    return 2\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a go module around it")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == []
        assert review.coverage.fixture_trees == [
            {"path": "pkg/testdata", "by": "go: testdata inside the module at go.mod", "modules": 2}
        ]

    def test_a_value_only_module_is_listed_with_its_reason(self, repo):
        # C-156: reach follows calls, so a test that reads a constant
        # guards nothing. The review still lists the module, and says why.
        write(repo, "src/app/settings.py", "LIMIT = 3\n")
        write(repo, "src/app/billing.py", "def charge():\n    return 1\n")
        write(
            repo,
            "tests/test_settings.py",
            "from app import settings\n\n\ndef test_limit():\n    assert settings.LIMIT == 3\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a constant and a function")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == ["app.billing", "app.settings"]
        assert review.coverage.value_only == ["app.settings"]
        assert review.needs_attention
        text = format_review(review)
        assert "      app.settings — declares no function and no call targets it; reach follows calls only (C-156)" in text
        assert "      app.billing\n" in text
        assert review_to_dict(review)["coverage"]["value_only"] == ["app.settings"]

    def test_new_code_reached_only_through_a_fixture_is_guarded_and_said(self, repo):
        # ADR-137: pytest calls the fixture on the test's behalf, so the
        # module it sets up is guarded — and the review says which kind of
        # guard it is, beside a module a test calls.
        write(repo, "src/app/store.py", "def open_store():\n    return {}\n")
        write(repo, "src/app/billing.py", "def charge():\n    return 1\n")
        write(
            repo,
            "tests/test_store.py",
            "import pytest\nfrom app import billing, store\n\n\n"
            "@pytest.fixture\ndef opened():\n    return store.open_store()\n\n\n"
            "def test_charge(opened):\n    assert billing.charge() == 1\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a store behind a fixture")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == []
        assert review.coverage.fixture_only == ["app.store"]
        assert not review.coverage.needs_attention
        text = format_review(review)
        assert "new code reached only through a pytest fixture (1; guarded, ADR-137):\n      app.store\n" in text
        assert "      app.billing\n" not in text  # called by the test: no label
        assert review_to_dict(review)["coverage"]["fixture_only"] == ["app.store"]

    def test_new_code_reached_only_through_an_autouse_fixture_is_said_apart(self, repo):
        # ADR-139: an autouse fixture no test names still runs the code, so
        # the module is not "unguarded" — and it is the thinnest reach there
        # is, so it gets its own line, never the named-fixture one.
        write(repo, "src/app/store.py", "def open_store():\n    return {}\n")
        write(repo, "src/app/clock.py", "def reset():\n    return 0\n")
        write(
            repo,
            "tests/test_store.py",
            "import pytest\nfrom app import clock, store\n\n\n"
            "@pytest.fixture(autouse=True)\ndef _clock():\n    clock.reset()\n\n\n"
            "@pytest.fixture\ndef opened():\n    return store.open_store()\n\n\n"
            "def test_open(opened):\n    assert opened == {}\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a clock behind an autouse fixture")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.new_unguarded == []
        assert review.coverage.fixture_only == ["app.store"]
        assert review.coverage.autouse_only == ["app.clock"]
        assert not review.coverage.needs_attention
        text = format_review(review)
        assert "new code reached only through an autouse fixture (1;" in text
        assert "ADR-139):\n      app.clock\n" in text
        assert review_to_dict(review)["coverage"]["autouse_only"] == ["app.clock"]

    def test_losing_every_guarding_test_is_reported(self, repo):
        (repo / "tests" / "test_core.py").unlink()
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "drop the test")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.lost_guards == ["app.core"]
        assert review.needs_attention

    def test_a_guard_that_no_longer_exists_is_reported(self, repo):
        record = yaml.safe_load((repo / ".hobbes/invariants/I-1.yaml").read_text())
        record["guarded_by"] = ["tests/test_core.py::test_gone"]
        write(repo, ".hobbes/invariants/I-1.yaml", yaml.safe_dump(record, sort_keys=False))
        write(repo, "src/app/core.py", "def run():\n    return 4\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "change")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.broken_guards == {
            "I-1": ["tests/test_core.py::test_gone"]
        }
        assert review.needs_attention

    def test_counts_both_ends(self, repo):
        write(repo, "src/app/billing.py", "def charge():\n    return 1\n")
        write(
            repo,
            "tests/test_billing.py",
            "from app import billing\n\n\ndef test_charge():\n    assert billing.charge() == 1\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "more")
        review = build_review(repo, "HEAD~1", "HEAD")
        assert review.coverage.base_tests == 1
        assert review.coverage.head_tests == 2


class TestSoftInvariants:
    def _soft_repo(self, repo: Path) -> Path:
        record = {
            "id": "I-2",
            "statement": "Core stays free of side effects.",
            "scope": "src/app",
            "status": "confirmed",
            "check": "soft",
            "guarded_by": [],
        }
        write(repo, ".hobbes/invariants/I-2.yaml", yaml.safe_dump(record, sort_keys=False))
        (repo / ".hobbes/invariants/I-1.yaml").unlink()
        return repo

    def test_a_session_runs_only_for_in_scope_records(self, repo):
        self._soft_repo(repo)
        # A change outside src/app must not spend quota on this record.
        write(repo, "README.md", "hello\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "docs only")

        calls = []

        def runner(prompt: str) -> str:
            calls.append(prompt)
            return "VERDICT: holds"

        review = build_review(repo, "HEAD~1", "HEAD", with_soft=True, runner=runner)
        assert review.soft == []
        assert calls == []

    def test_an_in_scope_change_gets_judged_with_evidence(self, repo):
        self._soft_repo(repo)
        write(repo, "src/app/core.py", "import os\n\n\ndef run():\n    os.environ['X'] = '1'\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "side effect")

        prompts = []

        def runner(prompt: str) -> str:
            prompts.append(prompt)
            return "VERDICT: violated\nWHY: core now mutates the environment\nEVIDENCE: src/app/core.py:5"

        review = build_review(repo, "HEAD~1", "HEAD", with_soft=True, runner=runner)
        (answer,) = review.soft
        assert answer["id"] == "I-2"
        assert "violated" in answer["answer"]
        assert answer["scope_hits"] == ["src/app/core.py"]
        # The prompt must carry the record and the delta, or the session
        # is guessing.
        assert "Core stays free of side effects." in prompts[0]
        assert "architecture delta" in prompts[0]

    def test_a_failed_session_does_not_fail_the_review(self, repo):
        self._soft_repo(repo)
        write(repo, "src/app/core.py", "def run():\n    return 9\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "change")

        def runner(prompt: str) -> str:
            raise RuntimeError("claude timed out")

        review = build_review(repo, "HEAD~1", "HEAD", with_soft=True, runner=runner)
        (answer,) = review.soft
        assert "timed out" in answer["error"]

    def test_soft_records_are_skipped_by_default(self, repo):
        self._soft_repo(repo)
        write(repo, "src/app/core.py", "def run():\n    return 9\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "change")

        def runner(prompt: str) -> str:  # pragma: no cover - must not run
            raise AssertionError("no session should run without --soft")

        review = build_review(repo, "HEAD~1", "HEAD", runner=runner)
        assert review.soft == []
        assert judge_soft(review, [], runner=runner) == []

    def test_the_prompt_is_source_based(self, repo):
        # V2.M6 (C-18 lifted): the session runs in a read-only checkout
        # and the prompt carries the diff hunks, not just a file list.
        self._soft_repo(repo)
        write(repo, "src/app/core.py", "import os\n\n\ndef run():\n    os.environ['X'] = '1'\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "side effect")

        prompts = []

        def runner(prompt: str) -> str:
            prompts.append(prompt)
            return "VERDICT: holds"

        build_review(repo, "HEAD~1", "HEAD", with_soft=True, runner=runner)
        (prompt,) = prompts
        assert "read-only checkout" in prompt
        assert "diff hunks" in prompt
        assert "os.environ['X'] = '1'" in prompt  # the actual change
        assert "who_calls" in prompt  # the knowledge tools are named

    def test_a_missing_sandbox_is_an_error_not_a_silent_fallback(
        self, repo, monkeypatch
    ):
        # Falling back to the delta-based prompt would quietly recreate
        # C-18; the answer must carry the error instead.
        from hobbes import review as review_mod

        self._soft_repo(repo)
        write(repo, "src/app/core.py", "def run():\n    return 3\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "change")
        monkeypatch.setenv(review_mod.SESSION_BIN_ENV, "/nonexistent/hobbes-session")

        review = build_review(repo, "HEAD~1", "HEAD", with_soft=True)
        (answer,) = review.soft
        assert answer["id"] == "I-2"
        assert "error" in answer and "answer" not in answer

    def test_the_diff_excerpt_is_bounded(self, repo):
        from hobbes.review import _DIFF_LIMIT, _diff_excerpt

        self._soft_repo(repo)
        write(repo, "src/app/core.py", "\n".join(f"x{i} = {i}" for i in range(600)) + "\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "big change")
        review = build_review(repo, "HEAD~1", "HEAD")
        excerpt = _diff_excerpt(repo, review, ["src/app/core.py"])
        assert len(excerpt.splitlines()) == _DIFF_LIMIT + 1
        assert "omitted" in excerpt.splitlines()[-1]


class TestSuspectMovement:
    def test_pass_to_suspect_is_a_regression(self):
        from hobbes.invariants.schema import Invariant
        from hobbes.invariants.verdict import FAIL, PASS, SUSPECT, Verdict
        from hobbes.review import REGRESSED, STILL_FAILING, _movement

        inv = Invariant(
            id="I-1", statement="s", scope=".", status="confirmed",
            check="graph", target="",
            rule={"kind": "forbidden-import", "importers": ["*"], "imported": ["a.b"]},
            guarded_by=[], source="x",
        )
        assert _movement(Verdict(inv, PASS), Verdict(inv, SUSPECT)) == REGRESSED
        # fail <-> suspect is a tier change inside the red family, not a
        # fix-and-regress pair.
        assert _movement(Verdict(inv, FAIL), Verdict(inv, SUSPECT)) == STILL_FAILING


class TestOutput:
    def test_human_output_follows_the_review_order(self, repo):
        add_violation(repo)
        git(repo, "commit", "-qam", "break it")
        text = format_review(build_review(repo, "HEAD~1", "HEAD"))
        assert text.index("1. architecture delta") < text.index("2. invariants")
        assert text.index("2. invariants") < text.index("3. behavioral coverage")
        assert "REGRESSED" in text
        assert "needs attention" in text

    def test_a_clean_review_says_so(self, repo):
        write(repo, "README.md", "hi\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "docs")
        text = format_review(build_review(repo, "HEAD~1", "HEAD"))
        assert "nothing needs attention" in text

    def test_json_carries_the_whole_review(self, repo):
        add_violation(repo)
        git(repo, "commit", "-qam", "break it")
        payload = review_to_dict(build_review(repo, "HEAD~1", "HEAD"))
        assert payload["needs_attention"] is True
        assert payload["invariants"][0]["movement"] == REGRESSED
        assert payload["invariants"][0]["head"]["violations"][0]["line"] == 1
        # Both ends are present, so a consumer can render the movement.
        assert payload["invariants"][0]["base"]["result"] == "pass"
        assert "delta" in payload and "coverage" in payload
        json.dumps(payload)  # must be serialisable


class TestCli:
    def test_exit_one_when_something_needs_attention(self, repo, capsys):
        from hobbes import cli

        add_violation(repo)
        git(repo, "commit", "-qam", "break it")
        assert cli.main(["review", "HEAD~1..HEAD", "--repo", str(repo)]) == 1
        assert "REGRESSED" in capsys.readouterr().out

    def test_exit_zero_on_a_clean_range(self, repo, capsys):
        from hobbes import cli

        write(repo, "README.md", "hi\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "docs")
        assert cli.main(["review", "HEAD~1..HEAD", "--repo", str(repo)]) == 0

    def test_exit_two_on_a_bad_ref(self, repo, capsys):
        from hobbes import cli

        assert cli.main(["review", "nope..HEAD", "--repo", str(repo)]) == 2
        assert "hobbes review" in capsys.readouterr().err

    def test_exit_two_on_invalid_records(self, repo, capsys):
        from hobbes import cli

        write(repo, ".hobbes/invariants/bad.yaml", "id: I-9\ncompile:\n  target: nope\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "bad record")
        assert cli.main(["review", "HEAD~1..HEAD", "--repo", str(repo)]) == 2
        assert "invalid invariant records" in capsys.readouterr().err
