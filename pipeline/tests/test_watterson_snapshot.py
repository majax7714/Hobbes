"""Tests for working-tree snapshots (DEC-006).

Real git repos in tmp_path. Each test checks that the user's side (HEAD,
branch, index, working files) is exactly as it was before the snapshot.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hobbes.watterson.snapshot import (
    REF_PREFIX,
    SnapshotError,
    changed_files,
    pin,
    snapshot_base,
    take_snapshot,
    unpin,
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "a.py").write_text("a = 1\n")
    (root / "gone.py").write_text("g = 1\n")
    (root / ".gitignore").write_text("ignored.txt\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return root


def user_state(repo: Path) -> tuple[str, ...]:
    return (
        git(repo, "rev-parse", "HEAD"),
        git(repo, "symbolic-ref", "HEAD"),
        git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        git(repo, "diff", "--cached", "--name-only"),
    )


class TestTakeSnapshot:
    def test_captures_edits_untracked_and_deletions_without_touching_the_user(self, repo):
        (repo / "a.py").write_text("a = 2\n")
        (repo / "new.py").write_text("n = 1\n")
        (repo / "gone.py").unlink()
        (repo / "ignored.txt").write_text("secret\n")
        (repo / ".hobbes").mkdir()
        (repo / ".hobbes" / "x.json").write_text("{}")
        before = user_state(repo)

        snap = take_snapshot(repo)

        assert user_state(repo) == before
        assert snap.base == git(repo, "rev-parse", "HEAD")
        files = git(repo, "ls-tree", "-r", "--name-only", snap.sha).splitlines()
        assert sorted(files) == [".gitignore", "a.py", "new.py"]
        assert git(repo, "show", f"{snap.sha}:a.py") == "a = 2"
        assert git(repo, "show", "-s", "--format=%P", snap.sha) == snap.base
        assert not git(repo, "branch", "--contains", snap.sha)

    def test_staged_changes_are_kept_staged(self, repo):
        (repo / "a.py").write_text("a = 3\n")
        git(repo, "add", "a.py")
        (repo / "a.py").write_text("a = 4\n")
        before = user_state(repo)
        snap = take_snapshot(repo)
        assert user_state(repo) == before
        assert git(repo, "show", ":a.py") == "a = 3"  # the user's index
        assert git(repo, "show", f"{snap.sha}:a.py") == "a = 4"  # the working file

    def test_same_tree_same_sha(self, repo):
        (repo / "a.py").write_text("a = 2\n")
        first = take_snapshot(repo)
        assert take_snapshot(repo) == first
        (repo / "a.py").write_text("a = 3\n")
        assert take_snapshot(repo).sha != first.sha

    def test_a_clean_tree_snapshots_to_heads_tree(self, repo):
        snap = take_snapshot(repo)
        assert snap.tree == git(repo, "rev-parse", "HEAD^{tree}")

    @pytest.mark.parametrize("ignored", [False, True])
    def test_hobbes_output_is_left_out_whether_or_not_git_ignores_it(self, repo, ignored):
        # `hobbes ingest` puts `.hobbes/` in info/exclude; naming an ignored
        # path in the exclude pathspec used to make `git add` fail.
        if ignored:
            (repo / ".git" / "info" / "exclude").write_text(".hobbes/\n")
        (repo / ".hobbes" / "derived").mkdir(parents=True)
        (repo / ".hobbes" / "derived" / "graph.json").write_text("{}")
        snap = take_snapshot(repo)
        assert snap.tree == git(repo, "rev-parse", "HEAD^{tree}")

    def test_from_a_subdirectory(self, repo):
        (repo / "sub").mkdir()
        (repo / "sub" / "b.py").write_text("b = 1\n")
        snap = take_snapshot(repo / "sub")
        assert "sub/b.py" in git(repo, "ls-tree", "-r", "--name-only", snap.sha).splitlines()

    def test_no_commits_and_not_a_repo_raise(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(SnapshotError, match="not a git repo|rev-parse"):
            take_snapshot(empty)
        git(empty, "init", "-q")
        with pytest.raises(SnapshotError, match="no commits"):
            take_snapshot(empty)


class TestSnapshotBase:
    def test_a_snapshot_names_its_head(self, repo):
        snap = take_snapshot(repo)
        assert snapshot_base(repo, snap.sha) == snap.base

    def test_an_ordinary_commit_or_junk_is_not_a_snapshot(self, repo):
        assert snapshot_base(repo, git(repo, "rev-parse", "HEAD")) is None
        assert snapshot_base(repo, "0" * 40) is None


class TestChangedFiles:
    def test_between_two_snapshots_includes_untracked_both_ways(self, repo):
        (repo / "early.py").write_text("e = 1\n")
        first = take_snapshot(repo)
        (repo / "early.py").unlink()
        (repo / "late.py").write_text("l = 1\n")
        (repo / "a.py").write_text("a = 9\n")
        second = take_snapshot(repo)
        assert changed_files(repo, first.sha, second.sha) == ["a.py", "early.py", "late.py"]
        assert changed_files(repo, second.sha, second.sha) == []


class TestPin:
    def test_pin_and_unpin(self, repo):
        snap = take_snapshot(repo)
        pin(repo, "s1", snap.sha)
        assert git(repo, "rev-parse", f"{REF_PREFIX}s1") == snap.sha
        assert git(repo, "branch", "--list") == "* main"  # a private ref, not a branch
        unpin(repo, "s1")
        assert not git(repo, "for-each-ref", REF_PREFIX)
