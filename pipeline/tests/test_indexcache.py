"""ADR-122: lane B's index cache — the helper's facts file kept under the
hash of everything that produced it, read back by the same reader, so a
hit is byte-identical to a miss and nothing uncontained is ever kept."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from hobbes.extract import containment, indexcache, scipsource, staging

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(root))
    # The key names the image the indexers live in; the tests do not
    # need one built, only a fixed id.
    monkeypatch.setattr(containment, "image_id", lambda: "sha256:test-image")
    monkeypatch.setattr(containment, "helper_dir", lambda: tmp_path / "helper")
    (tmp_path / "helper").mkdir()
    (tmp_path / "helper" / "index.mjs").write_text("// helper v5\n")
    (tmp_path / "helper" / "package-lock.json").write_text("{}\n")
    indexcache.reset_ledger()
    containment.reset_ledger()
    indexcache._swept.clear()
    return root


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("def f():\n    return g()\n\ndef g():\n    return 1\n")
    (root / "b.py").write_text("from a import f\n")
    return root


def facts_lines(language: str = "python") -> str:
    """A valid helper facts file: header, one document, trailer (ADR-116)."""
    header = {"helper_version": scipsource.HELPER_VERSION, "language": language}
    document = {
        "file": "a.py",
        "references": [{"line": 2, "col": 11, "name": "g", "def_file": "a.py", "def_line": 4}],
        "implements": [],
        "definitions": [{"symbol": "a.f", "line": 1}, {"symbol": "a.g", "line": 4}],
        "external_refs": [],
    }
    trailer = {
        "end": True,
        "documents": 1,
        "definitions": 2,
        "references": 1,
        "external_refs": 0,
        "implements": 0,
        "packages": {},
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }
    return "\n".join(json.dumps(r) for r in (header, document, trailer)) + "\n"


class FakeHelper:
    """Stands in for :func:`containment.run`: writes the facts file the
    config names, and counts how often the helper "ran"."""

    def __init__(self, monkeypatch, contained: bool = True, text: str | None = None):
        self.runs = 0
        self.contained = contained
        self.text = text if text is not None else facts_lines()

        def run(plan, *, timeout):
            self.runs += 1
            config = json.loads(Path(plan.command[-1]).read_text())
            Path(config["facts"]).write_text(self.text)
            proc = subprocess.CompletedProcess(plan.command, 0, stdout="", stderr="")
            if contained:
                containment.LEDGER.append({"step": plan.profile.step, "contained": True})
                return containment.Outcome(proc, True)
            containment.LEDGER.append({"step": plan.profile.step, "contained": False, "reason": "no podman"})
            return containment.Outcome(proc, False, host_reason="no podman")

        monkeypatch.setattr(containment, "run", run)


def index(repo: Path, sha: str = "", **extra) -> dict:
    """Stage the repo and run the helper over it, as a language would."""
    files = sorted(p.name for p in repo.glob("*.py"))
    stage = staging.build_stage(repo, files, config={"extraPaths": ["."]}, sha=sha)
    config = {
        "stage": str(stage),
        "language": "python",
        "projectName": "repo",
        "projectVersion": "0",
        "output": str(stage.parent / f"{stage.name}.scip"),
        "declaredDeps": [],
        **extra,
    }
    try:
        return scipsource.run_helper(config)
    finally:
        staging.remove_stage(stage)


def hits() -> list[bool]:
    return [e["hit"] for e in indexcache.LEDGER]


class TestAHitIsTheSameAnswer:
    def test_a_second_run_of_the_same_unit_is_read_not_indexed(self, cache, repo, monkeypatch):
        helper = FakeHelper(monkeypatch)
        first = index(repo)
        second = index(repo)
        assert helper.runs == 1
        assert hits() == [False, True]
        assert second == first
        assert [s.file for s in second["references"]] == ["a.py"]
        # One entry, named by the key, under the cache — nowhere else.
        entries = list((cache / "index").glob("*.facts.ndjson"))
        assert len(entries) == 1 and entries[0].name.startswith(indexcache.LEDGER[0]["key"])
        # The containment stamp is the same on the hit as on the miss: the
        # stored run was contained, and the artifact says where the facts
        # came from (P1: byte-identical either way).
        assert containment.LEDGER == [
            {"step": "index-python", "contained": True},
            {"step": "index-python", "contained": True},
        ]

    def test_two_stages_of_one_content_share_a_key(self, cache, repo, monkeypatch):
        # The stage's own name folds in sizes and mtimes; the key does not.
        helper = FakeHelper(monkeypatch)
        index(repo, sha="one")
        index(repo, sha="two")
        assert helper.runs == 1
        assert hits() == [False, True]
        assert len({e["key"] for e in indexcache.LEDGER}) == 1

    def test_a_hit_touches_the_entry(self, cache, repo, monkeypatch):
        FakeHelper(monkeypatch)
        index(repo)
        entry = next((cache / "index").glob("*.facts.ndjson"))
        old = time.time() - 10 * 86400
        os.utime(entry, (old, old))
        index(repo)
        assert entry.stat().st_mtime > old + 86400


class TestTheKeySeesEveryInput:
    def test_a_changed_staged_file_is_a_miss(self, cache, repo, monkeypatch):
        helper = FakeHelper(monkeypatch)
        index(repo)
        (repo / "a.py").write_text("def f():\n    return 2\n")
        index(repo)
        assert helper.runs == 2 and hits() == [False, False]

    def test_a_changed_config_is_a_miss(self, cache, repo, monkeypatch):
        helper = FakeHelper(monkeypatch)
        index(repo)
        index(repo, declaredDeps=["requests"])
        assert helper.runs == 2

    def test_a_sidecar_file_is_hashed_by_its_bytes(self, cache, repo, monkeypatch):
        # The venv listing the config names under the cache is the
        # helper's input; its path changes with every stage, its bytes
        # are what matter.
        helper = FakeHelper(monkeypatch)
        listing = cache / "stage" / "env.json"
        listing.parent.mkdir(parents=True, exist_ok=True)
        listing.write_text('[{"name": "requests", "version": "2.0"}]')
        index(repo, environment=str(listing))
        index(repo, environment=str(listing))
        assert helper.runs == 1
        listing.write_text('[{"name": "requests", "version": "2.1"}]')
        index(repo, environment=str(listing))
        assert helper.runs == 2

    def test_a_linked_tree_is_fingerprinted_by_its_installer_marker(self, cache, repo, monkeypatch, tmp_path):
        helper = FakeHelper(monkeypatch)
        tree = tmp_path / "node_modules"
        tree.mkdir()
        (tree / ".package-lock.json").write_text("{}")
        files = ["a.py", "b.py"]

        def run():
            stage = staging.build_stage(repo, files, sha="", links={"node_modules": str(tree)})
            try:
                return scipsource.run_helper({
                    "stage": str(stage), "language": "python", "projectName": "repo",
                    "projectVersion": "0", "output": str(stage.parent / f"{stage.name}.scip"),
                    "declaredDeps": [],
                })
            finally:
                staging.remove_stage(stage)

        run()
        run()
        assert helper.runs == 1
        marker = tree / ".package-lock.json"
        marker.write_text('{"name": "x"}')
        run()
        assert helper.runs == 2

    def test_the_helper_and_the_image_are_part_of_the_key(self, cache, repo, monkeypatch, tmp_path):
        helper = FakeHelper(monkeypatch)
        index(repo)
        (tmp_path / "helper" / "index.mjs").write_text("// helper v6\n")
        index(repo)
        assert helper.runs == 2
        monkeypatch.setattr(containment, "image_id", lambda: "sha256:rebuilt")
        index(repo)
        assert helper.runs == 3

    def test_the_root_is_not_part_of_the_key(self, cache, repo, monkeypatch):
        # The stored file holds stage-relative paths; the root is put in
        # front at read time, so one entry serves any root.
        helper = FakeHelper(monkeypatch)
        files = ["a.py", "b.py"]
        stage = staging.build_stage(repo, files, sha="")
        config = lambda: {
            "stage": str(stage), "language": "python", "projectName": "repo",
            "projectVersion": "0", "output": str(stage.parent / f"{stage.name}.scip"),
            "declaredDeps": [],
        }
        try:
            scipsource.run_helper(config(), root="pkg")
            facts = scipsource.run_helper(config(), root="other")
        finally:
            staging.remove_stage(stage)
        assert helper.runs == 1
        assert facts["references"][0].file == "other/a.py"


class TestNothingUnsafeIsKept:
    def test_a_host_run_is_never_cached(self, cache, repo, monkeypatch):
        helper = FakeHelper(monkeypatch, contained=False)
        index(repo)
        index(repo)
        assert helper.runs == 2
        # The store directory exists (containment.plan creates it to lay it
        # read-only, ADR-128 §1); nothing was stored in it.
        assert not any((cache / "index").iterdir())
        assert hits() == [False, False]

    def test_no_image_means_no_cache(self, cache, repo, monkeypatch):
        monkeypatch.setattr(containment, "image_id", lambda: None)
        helper = FakeHelper(monkeypatch)
        index(repo)
        index(repo)
        assert helper.runs == 2 and indexcache.LEDGER == []

    def test_the_env_switch_indexes_afresh(self, cache, repo, monkeypatch):
        monkeypatch.setenv(indexcache.ENABLE_ENV, "0")
        helper = FakeHelper(monkeypatch)
        index(repo)
        index(repo)
        assert helper.runs == 2 and indexcache.LEDGER == []

    def test_a_failed_run_stores_nothing(self, cache, repo, monkeypatch):
        FakeHelper(monkeypatch, text="")  # exit 0, empty facts: a ScipError
        with pytest.raises(scipsource.ScipError):
            index(repo)
        assert not list((cache / "index").glob("*.facts.ndjson")) if (cache / "index").exists() else True

    def test_an_entry_that_no_longer_reads_is_dropped_and_the_unit_indexed(self, cache, repo, monkeypatch):
        helper = FakeHelper(monkeypatch)
        index(repo)
        entry = next((cache / "index").glob("*.facts.ndjson"))
        # A short file is never a smaller answer (ADR-116): the reader
        # refuses it, the entry goes, the unit is indexed again.
        entry.write_text(entry.read_text().splitlines()[0] + "\n")
        facts = index(repo)
        assert helper.runs == 2 and hits() == [False, False]
        assert len(facts["references"]) == 1
        assert entry.read_text() == facts_lines()

    def test_a_stage_outside_the_cache_is_not_cached(self, cache, repo, monkeypatch, tmp_path):
        helper = FakeHelper(monkeypatch)
        stage = tmp_path / "elsewhere"
        stage.mkdir()
        config = lambda: {"stage": str(stage), "language": "python", "projectName": "repo",
                          "projectVersion": "0", "output": str(stage / "out.scip"), "declaredDeps": []}
        scipsource.run_helper(config())
        scipsource.run_helper(config())
        assert helper.runs == 2 and indexcache.LEDGER == []


class TestTheStoreIsBounded:
    def test_old_entries_and_partials_are_swept_at_the_next_write(self, cache, repo, monkeypatch):
        store = cache / "index"
        store.mkdir(parents=True)
        old = store / ("0" * 24 + ".facts.ndjson")
        old.write_text("x")
        stale = time.time() - (indexcache.KEEP_DAYS + 1) * 86400
        os.utime(old, (stale, stale))
        recent = store / ("1" * 24 + ".facts.ndjson")
        recent.write_text("x")
        partial = store / ("2" * 24 + ".facts.ndjson.partial")
        partial.write_text("x")
        FakeHelper(monkeypatch)
        index(repo)
        assert not old.exists() and not partial.exists() and recent.exists()

    def test_the_summary_counts_the_ledger(self, cache, repo, monkeypatch):
        assert indexcache.summary() is None
        FakeHelper(monkeypatch)
        index(repo)
        index(repo)
        summary = indexcache.summary()
        assert summary["hits"] == 1 and summary["misses"] == 1
        assert summary["key_seconds"] >= 0 and summary["store"] == str(cache / "index")


@pytest.mark.lane_b
class TestThroughTheImage:
    def test_a_re_ingest_is_read_from_the_cache_and_byte_identical(self, tmp_path, monkeypatch):
        """The real helper in the real image: ingest a fixture twice; the
        second lane B is every unit a hit, the artifact byte-identical,
        and nothing about the cache in it."""
        import shutil

        from hobbes.extract import ingest

        why = containment.unavailable_reason()
        if why is not None:
            pytest.skip(f"containment unavailable here: {why}")
        monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        root = tmp_path / "minigo"
        shutil.copytree(FIXTURES / "minigo", root)
        git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-qm", "fixture"], check=True)

        paths = ingest(root)
        graph = next(p for p in paths if p.name == "graph.json")
        first = graph.read_bytes()
        first_ledger = list(indexcache.LEDGER)
        assert first_ledger and all(not e["hit"] for e in first_ledger)
        paths = ingest(root)
        assert graph.read_bytes() == first
        assert indexcache.LEDGER and all(e["hit"] for e in indexcache.LEDGER)
        assert b"index_cache" not in first
