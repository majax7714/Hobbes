"""Tests for the graph freshness check and the session-start policy (DEC-005).

Repos are real git repos built in tmp_path; the derived files are written
by hand with the stamp ingest uses (top-level ``sha`` and ``dirty``), so
only ``TestRealIngest`` runs the extractor. The session-start policy runs
with a fake ingest and a faked prompt. The CLI side is in
``test_cli_freshness.py``.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes.watterson.freshness import (
    GraphStatus,
    RefreshPolicy,
    check_freshness,
    dirty_count,
    exit_code,
    on_session_start,
)
from hobbes.watterson.snapshot import take_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
DERIVED = (".hobbes", "derived")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def commit(repo: Path, name: str = "a.txt", text: str | None = None) -> str:
    path = repo / name
    path.write_text(text if text is not None else (path.read_text() if path.exists() else "") + "x\n")
    git(repo, "add", name)
    git(repo, "commit", "-qm", f"change {name}")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Path:
    """A git repo with one commit and no graph."""
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    commit(root)
    return root


def stamp(repo: Path, sha: str | None = None, *, dirty: bool = False, **per_file: str) -> None:
    """Write the three derived files stamped at *sha* (default HEAD)."""
    sha = sha or git(repo, "rev-parse", "HEAD")
    derived = repo.joinpath(*DERIVED)
    derived.mkdir(parents=True, exist_ok=True)
    for name in ("graph", "tests", "interfaces"):
        body = {"schema_version": 4, "sha": per_file.get(name, sha), "dirty": dirty}
        (derived / f"{name}.json").write_text(json.dumps(body))


class TestCheck:
    def test_fresh(self, repo):
        stamp(repo)
        check = check_freshness(repo)
        head = git(repo, "rev-parse", "HEAD")
        assert check.status is GraphStatus.FRESH
        assert check.freshness.pinned == check.freshness.current == head
        assert check.dirty_files == 0 and exit_code(check) == 0
        assert check.summary() == f"graph @ {head[:7]} · HEAD {head[:7]} · fresh"

    def test_stale_n_commits_behind(self, repo):
        stamp(repo)
        old = git(repo, "rev-parse", "HEAD")
        commit(repo)
        commit(repo)
        head = commit(repo)
        check = check_freshness(repo)
        assert check.status is GraphStatus.STALE and exit_code(check) == 1
        assert check.freshness.behind_by == "3 commits behind"
        assert check.freshness.suggested == head
        assert check.summary() == f"graph @ {old[:7]} · HEAD {head[:7]} · stale (3 commits behind)"

    def test_diverged(self, repo):
        git(repo, "checkout", "-qb", "side")
        side = commit(repo, "b.txt")
        stamp(repo)
        git(repo, "checkout", "-q", "main")
        commit(repo)
        commit(repo)
        check = check_freshness(repo)
        assert check.freshness.pinned == side
        assert check.status is GraphStatus.STALE
        assert check.freshness.behind_by == "diverged: 2 behind, 1 not on HEAD"

    def test_stamp_not_in_history(self, repo):
        stamp(repo, "0123456789abcdef0123456789abcdef01234567")
        check = check_freshness(repo)
        assert check.status is GraphStatus.STALE
        assert check.freshness.behind_by == "stamp not in history"

    def test_missing(self, repo):
        check = check_freshness(repo)
        assert check.status is GraphStatus.MISSING and exit_code(check) == 1
        assert check.summary().startswith("no graph · HEAD ")
        assert "missing (no .hobbes/derived/graph.json)" in check.summary()

    def test_a_corrupt_graph_is_unreadable(self, repo):
        stamp(repo)
        repo.joinpath(*DERIVED, "graph.json").write_text('{"sha": "abc')
        check = check_freshness(repo)
        assert check.status is GraphStatus.UNREADABLE and exit_code(check) == 1
        assert "graph.json unreadable: JSONDecodeError" in check.freshness.error

    def test_a_partial_graph_is_unreadable(self, repo):
        stamp(repo)
        repo.joinpath(*DERIVED, "tests.json").unlink()
        repo.joinpath(*DERIVED, "interfaces.json").write_text("{}")
        check = check_freshness(repo)
        assert check.status is GraphStatus.UNREADABLE
        assert check.freshness.error == (
            "tests.json missing; interfaces.json has no stamp (top-level 'sha')"
        )

    def test_stamps_that_disagree_are_flagged_and_stale(self, repo):
        old = git(repo, "rev-parse", "HEAD")
        head = commit(repo)
        stamp(repo, tests=old)
        check = check_freshness(repo)
        assert check.status is GraphStatus.STALE
        assert check.freshness.behind_by == "stamps disagree"
        assert check.freshness.notes == (
            f"stamps disagree: graph.json @ {head[:7]}, tests.json @ {old[:7]}, "
            f"interfaces.json @ {head[:7]}",
        )

    def test_a_graph_from_a_dirty_tree_is_noted_not_stale(self, repo):
        stamp(repo, dirty=True)
        check = check_freshness(repo)
        assert check.status is GraphStatus.FRESH
        assert check.freshness.notes == ("the graph was extracted from a dirty tree",)

    def test_not_a_repo(self, tmp_path):
        check = check_freshness(tmp_path)
        assert check.status is GraphStatus.NOT_A_REPO and exit_code(check) == 2
        assert check.summary() == f"{tmp_path.resolve()} is not a git repo"
        missing = check_freshness(tmp_path / "nope")
        assert missing.status is GraphStatus.NOT_A_REPO
        assert "is not a directory" in missing.summary()

    def test_no_commits(self, tmp_path):
        git(tmp_path, "init", "-q")
        check = check_freshness(tmp_path)
        assert check.status is GraphStatus.NO_COMMITS and exit_code(check) == 2
        assert check.summary() == f"{tmp_path.resolve()} has no commits yet"

    def test_a_subdirectory_checks_its_repo(self, repo):
        stamp(repo)
        (repo / "sub").mkdir()
        check = check_freshness(repo / "sub")
        assert check.root == repo and check.status is GraphStatus.FRESH


class TestDirty:
    def test_counts_changed_and_untracked_files_but_not_hobbes(self, repo):
        stamp(repo)  # .hobbes/ is not in any exclude file here
        assert git(repo, "status", "--porcelain").startswith("?? .hobbes/")
        assert dirty_count(repo) == 0
        (repo / "a.txt").write_text("edited\n")
        (repo / "new").mkdir()
        (repo / "new" / "one.py").write_text("")
        (repo / "new" / "two.py").write_text("")
        commit(repo, "b.txt")
        git(repo, "mv", "b.txt", "c.txt")
        assert dirty_count(repo) == 4  # edit, two untracked files, one rename
        check = check_freshness(repo)
        assert check.status is GraphStatus.STALE  # the commit, not the edits
        assert check.dirty_files == 4
        assert check.summary().endswith(" · dirty (4 files)")

    def test_a_dirty_tree_never_makes_the_graph_stale(self, repo):
        stamp(repo)
        (repo / "a.txt").write_text("edited\n")
        check = check_freshness(repo)
        assert check.status is GraphStatus.FRESH and exit_code(check) == 0
        assert check.summary().endswith(" · fresh · dirty (1 file)")


class TestSnapshotStamp:
    """A graph extracted from a snapshot (DEC-006) is compared through its HEAD."""

    def test_a_snapshot_of_head_is_fresh(self, repo, tmp_path):
        (repo / "a.txt").write_text("edited\n")
        snap = take_snapshot(repo)
        elsewhere = tmp_path / "graphs" / snap.sha
        stamp_dir(elsewhere, snap.sha)
        check = check_freshness(repo, derived=elsewhere)
        assert check.status is GraphStatus.FRESH and exit_code(check) == 0
        assert check.freshness.pinned == snap.sha
        assert f"the graph is a snapshot of {snap.base[:7]} with uncommitted changes" in check.freshness.notes

    def test_a_snapshot_of_an_older_commit_is_behind_by_its_base(self, repo, tmp_path):
        snap = take_snapshot(repo)
        stamp_dir(tmp_path / "g", snap.sha)
        commit(repo)
        commit(repo)
        check = check_freshness(repo, derived=tmp_path / "g")
        assert check.status is GraphStatus.STALE
        assert check.freshness.behind_by == "2 commits behind"

    def test_derived_defaults_to_the_repo_and_missing_names_the_dir(self, repo, tmp_path):
        stamp(repo)
        assert check_freshness(repo).status is GraphStatus.FRESH
        check = check_freshness(repo, derived=tmp_path / "nowhere")
        assert check.status is GraphStatus.MISSING
        assert check.freshness.error == f"no {tmp_path / 'nowhere' / 'graph.json'}"


def stamp_dir(derived: Path, sha: str) -> None:
    """The three derived files stamped at *sha*, in *derived*."""
    derived.mkdir(parents=True, exist_ok=True)
    for name in ("graph", "tests", "interfaces"):
        (derived / f"{name}.json").write_text(json.dumps({"schema_version": 4, "sha": sha, "dirty": False}))


class FakeIngest:
    """Stamps the repo at HEAD, as a real ingest would, and records the call."""

    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.calls: list[Path] = []

    def __call__(self, root: Path) -> int:
        self.calls.append(root)
        if self.code == 0:
            stamp(root)
        return self.code


def answering(reply: str):
    asked: list[str] = []

    def ask(question: str) -> str:
        asked.append(question)
        return reply

    ask.asked = asked  # type: ignore[attr-defined]
    return ask


class TestSessionStart:
    def start(self, repo, *, interactive=True, policy=RefreshPolicy.ASK, reply="", code=0):
        ingest, ask, out = FakeIngest(code), answering(reply), io.StringIO()
        result = on_session_start(
            repo, interactive=interactive, policy=policy, ingest=ingest, ask=ask, out=out
        )
        return result, ingest, ask.asked, out.getvalue()

    def stale(self, repo) -> None:
        stamp(repo)
        commit(repo)
        commit(repo)

    def test_fresh_prints_one_note_and_never_asks(self, repo):
        stamp(repo)
        head = git(repo, "rev-parse", "HEAD")
        result, ingest, asked, out = self.start(repo)
        assert out == f"hobbes: graph fresh @ {head[:7]} (HEAD)\n"
        assert asked == [] and ingest.calls == [] and not result.ingested

    def test_stale_on_a_tty_asks_and_yes_reingests(self, repo):
        self.stale(repo)
        result, ingest, asked, out = self.start(repo, reply="y\n")
        assert asked == ["Hobbes graph is stale (2 commits behind). Re-extract now? [y/N] "]
        assert ingest.calls == [repo]
        assert result.ingested and result.ingest_exit == 0
        assert result.before.status is GraphStatus.STALE
        assert result.check.status is GraphStatus.FRESH
        assert out.startswith("hobbes: re-extracted: graph @ ")

    def test_no_or_enter_or_eof_continues_without_ingest(self, repo):
        self.stale(repo)
        for reply in ("n\n", "\n", ""):
            result, ingest, asked, out = self.start(repo, reply=reply)
            assert len(asked) == 1 and ingest.calls == [] and not result.ingested
            assert result.check.status is GraphStatus.STALE
            assert out == ""

    def test_missing_on_a_tty_asks(self, repo):
        result, ingest, asked, _ = self.start(repo, reply="yes\n")
        assert asked == [
            "Hobbes graph is missing (no .hobbes/derived/graph.json). Re-extract now? [y/N] "
        ]
        assert result.ingested

    def test_non_tty_warns_and_continues(self, repo):
        self.stale(repo)
        result, ingest, asked, out = self.start(repo, interactive=False, reply="y\n")
        assert asked == [] and ingest.calls == []
        assert out == (
            "hobbes: warning: Hobbes graph is stale (2 commits behind); continuing without "
            "re-extracting (run `hobbes ingest`, or pass --refresh)\n"
        )
        assert result.check.status is GraphStatus.STALE

    def test_refresh_ingests_without_asking(self, repo):
        for interactive in (True, False):
            self.stale(repo)
            result, ingest, asked, out = self.start(
                repo, interactive=interactive, policy=RefreshPolicy.REFRESH
            )
            assert asked == [] and ingest.calls == [repo] and result.ingested
            assert out.startswith("hobbes: Hobbes graph is stale (2 commits behind); "
                                  "re-extracting (--refresh)\n")

    def test_refresh_leaves_a_fresh_graph_alone(self, repo):
        stamp(repo)
        result, ingest, _, _ = self.start(repo, policy=RefreshPolicy.REFRESH)
        assert ingest.calls == [] and result.check.status is GraphStatus.FRESH

    def test_no_refresh_skips_the_check(self, repo):
        self.stale(repo)
        (repo / "a.txt").write_text("edited\n")
        result, ingest, asked, out = self.start(repo, policy=RefreshPolicy.SKIP)
        assert result.check is None and asked == [] and ingest.calls == [] and out == ""

    def test_a_failed_ingest_warns_and_continues(self, repo):
        self.stale(repo)
        result, ingest, _, out = self.start(repo, policy=RefreshPolicy.REFRESH, code=1)
        assert ingest.calls == [repo] and not result.ingested and result.ingest_exit == 1
        assert "hobbes: warning: re-extract failed (exit 1); continuing" in out

    def test_the_dirty_tag_is_always_shown_and_never_asks(self, repo):
        stamp(repo)
        (repo / "a.txt").write_text("edited\n")
        (repo / "b.txt").write_text("")
        _, ingest, asked, out = self.start(repo)
        assert out.endswith("hobbes: session started dirty (2 files changed)\n")
        assert asked == [] and ingest.calls == []
        self.stale(repo)
        (repo / "a.txt").write_text("edited again\n")
        _, _, _, out = self.start(repo, interactive=False)
        assert out.endswith("hobbes: session started dirty (2 files changed)\n")

    def test_not_a_repo_is_one_note(self, tmp_path):
        result, ingest, asked, out = self.start(tmp_path)
        assert out == f"hobbes: graph freshness not checked: {tmp_path.resolve()} is not a git repo\n"
        assert result.check.status is GraphStatus.NOT_A_REPO and ingest.calls == [] and asked == []


class TestRealIngest:
    def test_refresh_runs_the_ingest_code_path_and_the_graph_is_fresh(self, tmp_path, capsys):
        repo = (tmp_path / "miniapp").resolve()
        shutil.copytree(FIXTURES / "miniapp", repo)
        git(repo, "init", "-q")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "fixture")
        assert check_freshness(repo).status is GraphStatus.MISSING
        result = on_session_start(repo, interactive=False, policy=RefreshPolicy.REFRESH)
        assert result.ingested and result.check.status is GraphStatus.FRESH
        captured = capsys.readouterr()
        assert captured.out == ""  # ingest progress goes to stderr, not the session's stdout
        assert "ingested " in captured.err and "hobbes: re-extracted: graph @ " in captured.err
        assert dirty_count(repo) == 0  # ingest's .hobbes/ stays out of the dirty count
