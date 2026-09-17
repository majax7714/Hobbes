"""Tests for the one-ingest-at-a-time lock (hobbes.extract.ingestlock, ADR-127)."""

import contextlib
import errno
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hobbes.extract import ingest, ingestlock
from hobbes.extract.emit import DERIVED_DIR
from hobbes.extract.ingestlock import IngestBusy, LOCK_NAME, hold

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"

# A holder in another process: it takes the lock the way ingest does, says
# so, and keeps it until its stdin closes. The kernel drops it at exit.
HOLDER = """
import fcntl, os, sys
from pathlib import Path
path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
handle = open(path, "a+")
fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
handle.seek(0); handle.truncate(); handle.write(f"{os.getpid()}\\n"); handle.flush()
sys.stdout.write("held\\n"); sys.stdout.flush()
sys.stdin.readline()
"""


@contextlib.contextmanager
def held_by_subprocess(repo_root):
    """Another process holding *repo_root*'s ingest lock for the block."""
    path = Path(repo_root).resolve() / DERIVED_DIR / LOCK_NAME
    proc = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout.readline() == "held\n"
    try:
        yield proc
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)


@pytest.fixture
def git_fixture(tmp_path):
    """The miniapp fixture as a real git repo with one commit."""
    repo = tmp_path / "miniapp"
    shutil.copytree(FIXTURE, repo)
    (repo / ".gitignore").write_text(".hobbes/\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
    return repo


class TestHold:
    def test_a_second_hold_of_one_repo_is_refused_naming_the_holder(self, tmp_path):
        with hold(tmp_path):
            with pytest.raises(IngestBusy) as caught:
                with hold(tmp_path):
                    pytest.fail("the second hold took the lock")
        message = str(caught.value)
        assert str(tmp_path.resolve()) in message
        assert f"pid {os.getpid()}" in message
        assert "ADR-127" in message

    def test_the_same_repo_through_a_symlink_is_the_same_lock(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        link = tmp_path / "link"
        link.symlink_to(repo)
        with hold(repo):
            with pytest.raises(IngestBusy):
                with hold(link):
                    pytest.fail("a symlinked path took a second lock")

    def test_two_repos_do_not_conflict(self, tmp_path):
        with hold(tmp_path / "one"), hold(tmp_path / "two"):
            pass  # each repo has its own lock; neither waits on the other

    def test_the_lock_is_released_when_the_block_exits(self, tmp_path):
        with hold(tmp_path):
            pass
        with hold(tmp_path):
            pass  # no stale lock to clear

    def test_the_lock_file_stays_and_holds_the_holders_pid(self, tmp_path):
        path = tmp_path / DERIVED_DIR / LOCK_NAME
        with hold(tmp_path):
            assert path.read_text() == f"{os.getpid()}\n"
        # Left in place: deleting it would race a process that already
        # opened it.
        assert path.is_file()

    def test_a_filesystem_without_flock_runs_unlocked_and_says_so(
        self, tmp_path, monkeypatch, capsys
    ):
        def no_locks(fd, operation):
            raise OSError(errno.ENOLCK, "no locks available")

        monkeypatch.setattr(ingestlock.fcntl, "flock", no_locks)
        ran = False
        with hold(tmp_path):
            ran = True
        assert ran  # the run proceeds: no flock is not a reason to refuse
        err = capsys.readouterr().err
        assert "running unlocked" in err and "C-159" in err
        assert "no locks available" in err


class TestIngestUnderContention:
    def test_a_held_lock_refuses_ingest_before_anything_is_written(self, git_fixture):
        graph = git_fixture / DERIVED_DIR / "graph.json"
        with held_by_subprocess(git_fixture) as proc:
            with pytest.raises(IngestBusy, match=f"pid {proc.pid}"):
                ingest(git_fixture)
        assert not graph.exists()  # nothing staged, indexed or written

    def test_a_refused_ingest_leaves_the_existing_graph_untouched(self, git_fixture):
        graph = git_fixture / DERIVED_DIR / "graph.json"
        ingest(git_fixture)
        before = graph.read_bytes()
        with held_by_subprocess(git_fixture):
            with pytest.raises(IngestBusy):
                ingest(git_fixture)
        assert graph.read_bytes() == before
