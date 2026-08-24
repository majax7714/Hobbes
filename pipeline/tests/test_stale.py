"""Blob-level staleness (ADR-019): hobbes.narrate.stale."""

import subprocess

import pytest

from hobbes.narrate.stale import blob_shas, changed_sources, is_stale, stamp_sources


def git_hash(repo, path):
    return subprocess.run(
        ["git", "-C", str(repo), "hash-object", "--", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class TestBlobShas:
    def test_matches_git_hash_object(self, git_repo):
        assert blob_shas(git_repo, ["app.py"]) == {"app.py": git_hash(git_repo, "app.py")}

    def test_missing_file_is_none(self, git_repo):
        shas = blob_shas(git_repo, ["app.py", "gone.py"])
        assert shas["gone.py"] is None
        assert shas["app.py"] is not None

    def test_hashes_working_tree_not_head(self, git_repo):
        committed = git_hash(git_repo, "app.py")
        (git_repo / "app.py").write_text("changed = True\n")
        assert blob_shas(git_repo, ["app.py"])["app.py"] != committed


class TestStampSources:
    def test_sorted_and_deduped(self, git_repo):
        (git_repo / "other.py").write_text("x = 1\n")
        sources = stamp_sources(git_repo, ["other.py", "app.py", "app.py"])
        assert [s["path"] for s in sources] == ["app.py", "other.py"]
        assert all(s["blob_sha"] for s in sources)

    def test_missing_file_raises(self, git_repo):
        with pytest.raises(FileNotFoundError, match="gone.py"):
            stamp_sources(git_repo, ["app.py", "gone.py"])


class TestChangedSources:
    def test_fresh_tree_reports_nothing(self, git_repo):
        sources = stamp_sources(git_repo, ["app.py"])
        assert changed_sources(git_repo, sources) == []
        assert not is_stale(git_repo, {"sources": sources})

    def test_uncommitted_edit_flips(self, git_repo):
        sources = stamp_sources(git_repo, ["app.py"])
        (git_repo / "app.py").write_text("edited = True\n")
        assert changed_sources(git_repo, sources) == ["app.py"]
        assert is_stale(git_repo, {"sources": sources})

    def test_deleted_file_flips(self, git_repo):
        sources = stamp_sources(git_repo, ["app.py"])
        (git_repo / "app.py").unlink()
        assert changed_sources(git_repo, sources) == ["app.py"]

    def test_only_the_changed_path_is_named(self, git_repo):
        (git_repo / "other.py").write_text("x = 1\n")
        sources = stamp_sources(git_repo, ["app.py", "other.py"])
        (git_repo / "other.py").write_text("x = 2\n")
        assert changed_sources(git_repo, sources) == ["other.py"]

    def test_artifact_without_sources_is_fresh(self, git_repo):
        assert not is_stale(git_repo, {})
