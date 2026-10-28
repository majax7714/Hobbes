"""Tests for the app's Hobbes layer: off until started, then on (DEC-016).

Repos are real git repos in a temp dir; ``hobbes ingest`` is faked except
in the last test, a tiny real run.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from hobbes.watterson.serve.layer import Layer


def git_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.py").write_text("x = 1\n")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
        subprocess.run(["git", "-C", str(root), *args], check=True)
    return root


def layer(repo: Path, tmp_path: Path, ingest) -> tuple[Layer, list[dict]]:
    seen: list[dict] = []
    return Layer(repo, tmp_path / "ingest.log", notify=seen.append, ingest=ingest), seen


async def no_ingest(repo, log):
    raise AssertionError("no ingest expected")


def states(seen: list[dict]) -> list[str]:
    return [s["state"] for s in seen]


def test_a_folder_that_is_not_a_repo_is_unavailable(tmp_path):
    (tmp_path / "plain").mkdir()
    lay, seen = layer(tmp_path / "plain", tmp_path, no_ingest)

    async def go():
        return lay.start(), await lay.stop()

    started, stopped = asyncio.run(go())
    assert started["state"] == stopped["state"] == "unavailable" and seen == []
    assert "git repo" in started["detail"]


def test_start_extracts_a_missing_graph_then_is_on(tmp_path):
    repo = git_repo(tmp_path / "repo")
    calls = []

    async def ingest(root, log):
        calls.append((root, log))
        return 0

    lay, seen = layer(repo, tmp_path, ingest)

    async def go():
        first = lay.start()
        assert lay.start()["state"] == "starting"  # a second start while starting does nothing
        await lay._task
        return first

    assert asyncio.run(go())["state"] == "starting"
    assert calls == [(repo.resolve(), tmp_path / "ingest.log")]
    assert states(seen) == ["starting", "starting", "on"] and lay.on
    assert seen[1]["detail"].startswith("extracting the graph (missing") and seen[1]["since"]


def test_a_failed_ingest_can_be_retried(tmp_path):
    repo = git_repo(tmp_path / "repo")
    codes = [3, 0]

    async def ingest(root, log):
        return codes.pop(0)

    lay, seen = layer(repo, tmp_path, ingest)

    async def go():
        lay.start()
        await lay._task
        failed = lay.status()
        lay.start()
        await lay._task
        return failed

    failed = asyncio.run(go())
    assert failed["state"] == "failed" and "exited 3" in failed["detail"] and str(tmp_path / "ingest.log") in failed["detail"]
    assert lay.on


def test_stop_cancels_a_start_in_progress(tmp_path):
    repo = git_repo(tmp_path / "repo")
    cancelled = []

    async def ingest(root, log):
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return 0

    lay, seen = layer(repo, tmp_path, ingest)

    async def go():
        lay.start()
        while lay.detail == "checking the graph":
            await asyncio.sleep(0.01)
        return await lay.stop()

    assert asyncio.run(go())["state"] == "off" and cancelled == [True]
    assert states(seen)[-1] == "off"


def test_the_real_ingest_runs_hobbes_in_a_child_process(tmp_path, monkeypatch):
    """``run_ingest`` writes the child's output to the log (a tiny real ingest)."""
    from hobbes.watterson.serve.layer import run_ingest

    repo = git_repo(tmp_path / "repo")
    monkeypatch.setenv("HOBBES_SCIP", "0")
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    code = asyncio.run(run_ingest(repo, tmp_path / "logs" / "ingest.log"))
    log = (tmp_path / "logs" / "ingest.log").read_text()
    assert code == 0 and "hobbes ingest --repo" in log and "ingested" in log
    assert (repo / ".hobbes" / "derived" / "graph.json").is_file()
