"""Tests for between-turn session graphs (DEC-006).

``TestRefresher`` drives the scheduling with a gated fake extract, so the
"one running, one pending" rule is checked step by step. ``TestStore``
and ``TestSession`` run the real ``hobbes ingest`` (lane A) on the
``miniapp`` fixture in a subprocess; ``TestSession`` drives turns through
the fake ACP agent, which edits files in the repo. Every store lives under
tmp_path (``HOBBES_CACHE_DIR`` too, so the subprocess's timings log does).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hobbes.watterson.freshness import GraphStatus, check_freshness
from hobbes.watterson.providers import AgentSession, AgentSpec, TurnEnded, allow_all
from hobbes.watterson.session_graph import (
    GraphLabel,
    GraphStore,
    Refresher,
)
from hobbes.watterson.snapshot import REF_PREFIX, take_snapshot

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_AGENT = FIXTURES / "fake_acp_agent.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch) -> Path:
    cache = tmp_path / "cache"
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(cache))
    return cache


@pytest.fixture
def repo(tmp_path) -> Path:
    """The miniapp fixture as a git repo with one commit."""
    root = (tmp_path / "miniapp").resolve()
    shutil.copytree(FIXTURES / "miniapp", root)
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-qm", "fixture")
    return root


def edit(repo: Path, name: str = "extra.py", text: str = "def extra():\n    return 1\n") -> None:
    (repo / name).write_text(text)


class FakeExtract:
    """Records each extract; each one waits for ``release()`` and then
    publishes a stamped graph in the store, as the real one would."""

    def __init__(self, store: GraphStore, fail: set[str] | None = None) -> None:
        self.store = store
        self.calls: list[str] = []
        self.fail = fail or set()
        self._gate = asyncio.Event()

    def release(self) -> None:
        self._gate.set()

    async def __call__(self, sha: str, base: str):
        self.calls.append(sha)
        await self._gate.wait()
        self._gate.clear()
        if sha in self.fail:
            raise RuntimeError("boom")
        out = self.store.graphs / sha
        out.mkdir(parents=True, exist_ok=True)
        for name in ("graph", "tests", "interfaces"):
            (out / f"{name}.json").write_text(json.dumps({"sha": sha, "dirty": False}))
        return self.store._publish(sha, base)


async def until(cond, timeout: float = 5.0) -> None:
    """Yield to the loop until *cond()* holds (pin runs in a thread)."""
    async with asyncio.timeout(timeout):
        while not cond():
            await asyncio.sleep(0.01)


class TestRefresher:
    def test_one_running_one_pending_and_the_newest_wins(self, repo):
        async def go():
            store = GraphStore(repo)
            fake = FakeExtract(store)
            async with Refresher(repo, store=store, extract=fake, session="s") as r:
                edit(repo, text="a = 1\n")
                first = await r.turn_ended()
                await until(lambda: len(fake.calls) == 1)
                edit(repo, text="a = 2\n")
                await r.turn_ended()  # pending
                edit(repo, text="a = 3\n")
                third = await r.turn_ended()  # replaces the pending one
                assert fake.calls == [first] and r.busy
                fake.release()
                await until(lambda: len(fake.calls) == 2)
                assert fake.calls == [first, third]
                fake.release()
                await r.wait_idle()
                assert store.current().sha == third
                assert git(repo, "rev-parse", f"{REF_PREFIX}s") == third
            return fake

        fake = asyncio.run(go())
        assert len(fake.calls) == 2
        assert not git(repo, "for-each-ref", REF_PREFIX)  # aclose unpinned

    def test_an_unchanged_turn_runs_nothing(self, repo):
        async def go():
            store = GraphStore(repo)
            fake = FakeExtract(store)
            async with Refresher(repo, store=store, extract=fake) as r:
                fake.release()
                assert await r.turn_ended() is not None
                await r.wait_idle()
                fake.release()
                assert await r.turn_ended() is None
            return fake.calls

        assert len(asyncio.run(go())) == 1

    def test_a_tree_back_at_the_running_snapshot_drops_the_pending_one(self, repo):
        async def go():
            store = GraphStore(repo)
            fake = FakeExtract(store)
            async with Refresher(repo, store=store, extract=fake) as r:
                edit(repo, text="a = 1\n")
                first = await r.turn_ended()
                await until(lambda: len(fake.calls) == 1)
                edit(repo, text="a = 2\n")
                await r.turn_ended()
                edit(repo, text="a = 1\n")
                assert await r.turn_ended() == first
                fake.release()
                await r.wait_idle()
            return fake.calls, first

        calls, first = asyncio.run(go())
        assert calls == [first]

    def test_a_failure_is_kept_and_the_last_good_graph_stays(self, repo):
        async def go():
            store = GraphStore(repo)
            edit(repo, text="bad = 1\n")
            bad = take_snapshot(repo).sha
            fake = FakeExtract(store, fail={bad})
            async with Refresher(repo, store=store, extract=fake) as r:
                fake.release()
                await r.turn_ended()
                await r.wait_idle()
                assert r.errors == [f"extract {bad[:7]}: boom"]
                assert store.current() is None
                edit(repo, text="good = 1\n")
                fake.release()
                good = await r.turn_ended()
                await r.wait_idle()
                assert store.current().sha == good

        asyncio.run(go())

    def test_close_cancels_the_running_one_and_drops_the_pending_one(self, repo):
        async def go():
            store = GraphStore(repo)
            fake = FakeExtract(store)
            r = Refresher(repo, store=store, extract=fake)
            edit(repo, text="a = 1\n")
            await r.turn_ended()
            await until(lambda: len(fake.calls) == 1)
            edit(repo, text="a = 2\n")
            await r.turn_ended()
            await r.aclose()
            assert not r.busy and await r.turn_ended() is None
            return fake.calls

        assert len(asyncio.run(go())) == 1

    def test_the_label(self, repo):
        async def go():
            store = GraphStore(repo)
            fake = FakeExtract(store)
            async with Refresher(repo, store=store, extract=fake) as r:
                assert str(await r.label()) == "no session graph yet"
                fake.release()
                sha = await r.turn_ended()
                await r.wait_idle()
                base = git(repo, "rev-parse", "HEAD")
                assert str(await r.label()) == (
                    f"graph @ {sha[:7]} (snapshot of {base[:7]}, lane A only); changed since: none"
                )
                edit(repo, "late.py", "x = 1\n")
                (repo / "src" / "miniapp" / "util.py").unlink()
                label = await r.label()
                assert label.changed == ("late.py", "src/miniapp/util.py")
                assert str(label).endswith("changed since: late.py, src/miniapp/util.py")

        asyncio.run(go())


def test_label_refreshing():
    assert str(GraphLabel(None, refreshing=True)) == "no session graph yet; extracting"


class TestStore:
    def test_extracts_a_snapshot_without_touching_the_user(self, repo, _cache):
        edit(repo)
        before = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
        snap = take_snapshot(repo)
        store = GraphStore(repo)
        graph = asyncio.run(store.extract(snap.sha, snap.base))

        assert store.dir.is_relative_to(_cache / "sessions")
        assert graph == store.current() and graph.sha == snap.sha
        doc = json.loads((graph.path / "graph.json").read_text())
        assert doc["sha"] == snap.sha and doc["dirty"] is False
        assert {"id": "extra", "kind": "module", "path": "extra.py"} in doc["nodes"]  # the untracked edit
        assert git(repo, "status", "--porcelain=v1", "--untracked-files=all") == before
        assert not (repo / ".hobbes" / "derived").exists()  # the repo's own graph is not written
        check = check_freshness(repo, derived=graph.path)
        assert check.status is GraphStatus.FRESH

    def test_reuses_the_worktree_and_keeps_the_newest_graphs(self, repo, monkeypatch):
        monkeypatch.setattr("hobbes.watterson.session_graph.KEEP_GRAPHS", 2)
        store = GraphStore(repo)
        shas = []
        for i in range(3):
            edit(repo, text=f"v = {i}\n")
            snap = take_snapshot(repo)
            asyncio.run(store.extract(snap.sha, snap.base))
            shas.append(snap.sha)
        assert git(store.worktree, "rev-parse", "HEAD") == shas[-1]
        assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 2
        kept = sorted(p.name for p in store.graphs.iterdir())
        assert kept == sorted(shas[1:])
        # The tree back at a kept snapshot: published from the cache, no ingest.
        store.log.unlink()
        edit(repo, text="v = 1\n")
        asyncio.run(store.extract(shas[1], take_snapshot(repo).base))
        assert store.current().sha == shas[1] and not store.log.exists()

    def test_a_failed_ingest_raises_with_the_logs_tail(self, repo, monkeypatch):
        monkeypatch.setattr("hobbes.watterson.session_graph.sys.executable", shutil.which("false"))  # /usr/bin/false on macOS
        from hobbes.watterson.session_graph import ExtractError

        snap = take_snapshot(repo)
        with pytest.raises(ExtractError, match="ingest exited 1"):
            asyncio.run(GraphStore(repo).extract(snap.sha, snap.base))



class TestSession:
    def test_turns_through_the_fake_agent_refresh_the_graph(self, repo):
        spec = AgentSpec("fake", (sys.executable, str(FAKE_AGENT)))

        async def turn(session, refresher, prompt: str) -> None:
            async with contextlib.aclosing(session.prompt(prompt)) as events:
                async for event in events:
                    if isinstance(event, TurnEnded):
                        await refresher.turn_ended()

        async def go():
            async with Refresher(repo) as refresher, \
                    AgentSession(spec, cwd=str(repo), on_permission=allow_all) as session:
                await turn(session, refresher, "write first.py def first(): return 1")
                await refresher.wait_idle()
                one = refresher.store.current()
                assert "first.py" in git(repo, "ls-tree", "-r", "--name-only", one.sha)
                assert (await refresher.label()).changed == ()

                await turn(session, refresher, "write second.py def second(): return 2")
                assert (await refresher.label()).changed == ("second.py",)  # before the refresh lands
                await refresher.wait_idle()
                two = refresher.store.current()
                assert two.sha != one.sha and (await refresher.label()).changed == ()
                assert not refresher.errors
            assert check_freshness(repo, derived=two.path).status is GraphStatus.FRESH

        asyncio.run(go())
