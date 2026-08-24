"""Lane B's staging trees, and the safety contract they exist to keep.

These cases are deliberately adversarial. The failure they guard against
is not "staging is broken" — it is "staging quietly touched, or quietly
deleted, something in a repo Hobbes does not own" (ADR-027).
"""

import os
import subprocess
from pathlib import Path

import pytest

from hobbes.extract import staging


@pytest.fixture
def cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(root))
    return root


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src" / "pkg").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "src" / "pkg" / "mod.py").write_text("VALUE = 1\n")
    (r / "tests" / "test_mod.py").write_text("import mod\n")
    (r / "README.md").write_text("not python\n")
    return r


FILES = ["src/pkg/mod.py", "tests/test_mod.py"]


class TestNeverTouchesTheRepo:
    def test_staging_writes_nothing_into_the_repo(self, repo, cache):
        before = {p: p.stat().st_mtime_ns for p in repo.rglob("*") if p.is_file()}
        staging.build_stage(repo, FILES, config={"extraPaths": ["src"]}, sha="abc")
        after = {p: p.stat().st_mtime_ns for p in repo.rglob("*") if p.is_file()}
        assert before == after, "staging modified or added files in the repo"

    def test_the_config_lands_in_the_stage_not_the_repo(self, repo, cache):
        stage = staging.build_stage(repo, FILES, config={"extraPaths": ["src"]}, sha="abc")
        assert (stage / "pyrightconfig.json").is_file()
        assert not (repo / "pyrightconfig.json").exists()

    def test_a_git_repo_stays_clean(self, repo, cache):
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git[:3], "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "base"], check=True)
        staging.build_stage(repo, FILES, config={"extraPaths": ["src"]}, sha="abc")
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert status == "", f"staging dirtied the repo: {status!r}"


class TestCopiesNeverLinks:
    def test_staged_files_are_independent_copies(self, repo, cache):
        stage = staging.build_stage(repo, FILES, sha="abc")
        source = repo / "src" / "pkg" / "mod.py"
        staged = stage / "src" / "pkg" / "mod.py"
        assert staged.read_text() == source.read_text()
        # The hazard: chmod through a hardlink changes the *original*
        # file's mode, so a linked stage is a live handle into the repo.
        assert staged.stat().st_ino != source.stat().st_ino
        assert source.stat().st_nlink == 1

    def test_writing_to_the_stage_cannot_reach_the_repo(self, repo, cache):
        stage = staging.build_stage(repo, FILES, sha="abc")
        (stage / "src" / "pkg" / "mod.py").write_text("CLOBBERED\n")
        assert (repo / "src" / "pkg" / "mod.py").read_text() == "VALUE = 1\n"

    def test_only_the_named_files_are_staged(self, repo, cache):
        # Lane A's discovered set, nothing else — README.md is not Python.
        stage = staging.build_stage(repo, FILES, sha="abc")
        staged = {
            p.relative_to(stage).as_posix()
            for p in stage.rglob("*")
            if p.is_file()
        }
        assert staged == set(FILES)


class TestThePathIsDerived:
    def test_same_inputs_give_the_same_path(self, repo, cache):
        a = staging.stage_path(repo, "abc", FILES)
        b = staging.stage_path(repo, "abc", FILES)
        assert a == b

    def test_a_different_commit_gives_a_different_path(self, repo, cache):
        assert staging.stage_path(repo, "abc", FILES) != staging.stage_path(
            repo, "def", FILES
        )

    def test_an_edited_file_gives_a_different_path(self, repo, cache):
        before = staging.stage_path(repo, "abc", FILES)
        # A dirty tree keeps its SHA, so the key must notice the content.
        (repo / "src" / "pkg" / "mod.py").write_text("VALUE = 2\n")
        os.utime(repo / "src" / "pkg" / "mod.py", (1, 1))
        assert staging.stage_path(repo, "abc", FILES) != before

    def test_it_lands_under_the_cache_root(self, repo, cache):
        stage = staging.build_stage(repo, FILES, sha="abc")
        assert cache.resolve() in stage.resolve().parents


class TestRemovalRefusesWhatItDidNotCreate:
    @pytest.mark.parametrize("victim", ["repo", "home", "tmpfile"])
    def test_paths_outside_the_cache_are_refused(self, repo, cache, tmp_path, victim):
        target = {
            "repo": repo,
            "home": tmp_path,
            "tmpfile": tmp_path / "loose",
        }[victim]
        if victim == "tmpfile":
            target.mkdir()
        with pytest.raises(staging.StagingError, match="refusing to remove"):
            staging.remove_stage(target)
        assert target.exists(), "a refused removal must not have removed anything"

    def test_the_cache_root_itself_is_refused(self, cache):
        cache.mkdir(parents=True)
        with pytest.raises(staging.StagingError, match="cache root"):
            staging.remove_stage(cache)
        assert cache.exists()

    def test_a_symlink_out_of_the_cache_is_refused(self, repo, cache):
        # The escape hatch worth closing: a link inside the cache pointing
        # at the repo would otherwise make rmtree follow it out.
        (cache / "stage").mkdir(parents=True)
        escape = cache / "stage" / "escape"
        escape.symlink_to(repo)
        with pytest.raises(staging.StagingError):
            staging.remove_stage(escape)
        assert (repo / "src" / "pkg" / "mod.py").exists()

    def test_removing_a_real_stage_works(self, repo, cache):
        stage = staging.build_stage(repo, FILES, sha="abc")
        staging.remove_stage(stage)
        assert not stage.exists()

    def test_removal_is_idempotent(self, repo, cache):
        stage = staging.build_stage(repo, FILES, sha="abc")
        staging.remove_stage(stage)
        staging.remove_stage(stage)  # must not raise


class TestCrashSafety:
    def test_a_half_built_stage_is_never_mistaken_for_a_complete_one(
        self, repo, cache
    ):
        # Simulate an interrupted run: a .partial tree left on disk.
        final = staging.stage_path(repo, "abc", FILES)
        partial = final.with_name(final.name + ".partial")
        partial.mkdir(parents=True)
        (partial / "junk.py").write_text("half written\n")

        stage = staging.build_stage(repo, FILES, sha="abc")
        assert stage == final
        assert not (stage / "junk.py").exists()
        assert not partial.exists()

    def test_rebuilding_replaces_rather_than_merges(self, repo, cache):
        stage = staging.build_stage(repo, FILES, sha="abc")
        (stage / "stray.py").write_text("left over\n")
        again = staging.build_stage(repo, FILES, sha="abc")
        assert not (again / "stray.py").exists()

    def test_sweep_clears_leftovers_but_can_keep_one(self, repo, cache):
        keep = staging.build_stage(repo, FILES, sha="abc")
        staging.build_stage(repo, FILES, sha="other")
        assert staging.sweep_stale(keep=keep) == 1
        assert keep.exists()
        assert staging.sweep_stale() == 1
        assert not keep.exists()


class TestLinkedDependencyTrees:
    """ADR-032: `node_modules` is symlinked, because copying 222 MB per
    zone is not viable and the alternative loses 6.4% of the semantics.

    Clause 2 still forbids linking *authored source*. What these cases
    pin is the pair of properties that make the exception safe, both of
    which fail silently and one of which fails destructively (C-22).
    """

    @pytest.fixture
    def deps(self, tmp_path):
        tree = tmp_path / "repo" / "node_modules"
        (tree / "left-pad").mkdir(parents=True)
        (tree / "left-pad" / "index.js").write_text("module.exports = 1;\n")
        return tree

    def test_dependency_tree_is_linked_not_copied(self, repo, cache, deps):
        stage = staging.build_stage(
            repo, FILES, sha="abc", links={"node_modules": str(deps)}
        )
        linked = stage / "node_modules"
        assert linked.is_symlink()
        assert linked.resolve() == deps.resolve()
        # and it is usable: the indexer resolves through it
        assert (linked / "left-pad" / "index.js").read_text().startswith("module")

    def test_removing_a_stage_never_follows_the_link(self, repo, cache, deps):
        """The expensive mistake: rmtree recursing into the user's tree.

        Guarded today only by a stdlib implementation detail — rmtree
        unlinks a symlinked directory rather than descending — so it gets
        an assertion rather than a comment. Getting this wrong deletes
        hundreds of megabytes the user has to reinstall.
        """
        stage = staging.build_stage(
            repo, FILES, sha="abc", links={"node_modules": str(deps)}
        )
        staging.remove_stage(stage)
        assert not stage.exists()
        assert deps.is_dir()
        assert (deps / "left-pad" / "index.js").is_file()

    def test_sweep_never_follows_the_link_either(self, repo, cache, deps):
        staging.build_stage(repo, FILES, sha="abc", links={"node_modules": str(deps)})
        assert staging.sweep_stale() == 1
        assert (deps / "left-pad" / "index.js").is_file()

    def test_rebuilding_over_a_link_leaves_the_target_intact(
        self, repo, cache, deps
    ):
        """Rebuild removes the previous stage — including its link."""
        staging.build_stage(repo, FILES, sha="abc", links={"node_modules": str(deps)})
        staging.build_stage(repo, FILES, sha="abc", links={"node_modules": str(deps)})
        assert (deps / "left-pad" / "index.js").is_file()

    def test_per_zone_configs_land_where_the_indexer_looks(self, repo, cache):
        stage = staging.build_stage(
            repo,
            FILES,
            sha="abc",
            configs={"src/pkg/tsconfig.json": {"compilerOptions": {"allowJs": True}}},
        )
        import json as _json

        written = _json.loads((stage / "src" / "pkg" / "tsconfig.json").read_text())
        assert written["compilerOptions"]["allowJs"] is True
