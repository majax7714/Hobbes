"""ADR-119: the ingest says where its time went — in the summary and in
an append-only log under the Hobbes cache — and never in an artifact."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes import cli
from hobbes.extract import extract_repo, ingest
from hobbes.extract.timings import Timings, timings_log

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    root = tmp_path / "miniapp"
    shutil.copytree(FIXTURES / "miniapp", root)
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
    return root


def test_every_step_is_timed_in_run_order(repo):
    timings = Timings()
    extraction = extract_repo(repo, timings=timings)
    names = [s["step"] for s in timings.steps]
    for expected in ("discover [python]", "parse [python]", "graph [python]",
                     "lane A [ts]", "packs", "lane A sites", "join", "project",
                     "lane agreement", "tail", "tests", "fixture trees"):
        assert expected in names, (expected, names)
    assert names.index("parse [python]") < names.index("join") < names.index("tests")
    assert all(s["seconds"] >= 0 for s in timings.steps)
    assert timings.total >= max(s["seconds"] for s in timings.steps)
    # Never in an artifact: two ingests of one commit stay byte-identical.
    assert "timings" not in extraction.graph
    assert "timings" not in extraction.tests


def test_a_step_that_raises_is_still_recorded():
    timings = Timings()
    with pytest.raises(RuntimeError):
        with timings.step("boom"):
            raise RuntimeError("x")
    assert [s["step"] for s in timings.steps] == ["boom"]


def test_ingest_times_the_write_and_the_artifact_carries_none(repo):
    timings = Timings()
    paths = ingest(repo, timings=timings)
    assert timings.steps[-1]["step"] == "write"
    graph = json.loads(next(p for p in paths if p.name == "graph.json").read_text())
    assert "timings" not in graph


def test_cli_prints_the_block_and_appends_one_log_line(repo, capsys):
    assert cli.main(["ingest", "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "timings:" in out and " steps" in out
    assert "parse [python]" in out and "write" in out
    log = timings_log(repo)
    assert f"logged to {log}" in out
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["repo"] == str(repo.resolve())
    assert len(row["sha"]) == 40
    assert row["hobbes"]  # the version the artifact carries
    assert [s["step"] for s in row["steps"]][-1] == "write"
    assert cli.main(["ingest", "--repo", str(repo)]) == 0
    assert len(log.read_text().splitlines()) == 2
