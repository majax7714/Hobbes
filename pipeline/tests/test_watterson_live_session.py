"""Tests for live chat sessions on a swapped graph view (DEC-009).

The repo's HEAD graph is a stamped stand-in (only ``sha`` is read here),
and extraction is faked to publish at once, so no ingest runs; the real
extract path is covered by ``test_session_graph.py``. ``chat`` runs against
the fake ACP agent, which echoes the label it is sent as ``label: …``.
"""

from __future__ import annotations

import asyncio
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hobbes.watterson import cli
from hobbes.watterson.live_session import MAX_LISTED, GraphView, turn_label
from hobbes.watterson.session_graph import GraphStore
from hobbes.watterson.snapshot import take_snapshot

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"
DERIVED = ("graph.json", "tests.json", "interfaces.json")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def stamp(derived: Path, sha: str) -> None:
    derived.mkdir(parents=True, exist_ok=True)
    for name in DERIVED:
        (derived / name).write_text(json.dumps({"sha": sha, "dirty": False}))


@pytest.fixture(autouse=True)
def _cache(tmp_path, monkeypatch) -> Path:
    cache = tmp_path / "cache"
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(cache))
    return cache


@pytest.fixture
def repo(tmp_path) -> Path:
    """A one-commit repo with a HEAD graph, ``.hobbes/`` excluded as ingest does."""
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    (root / "app.py").write_text("def main():\n    return 0\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    (root / ".git" / "info" / "exclude").write_text(".hobbes/\n")
    stamp(root / ".hobbes" / "derived", git(root, "rev-parse", "HEAD"))
    return root


def publish(store: GraphStore, sha: str, base: str) -> None:
    """What a finished extract leaves in the store."""
    stamp(store.graphs / sha, sha)
    store._publish(sha, base)


class TestGraphView:
    def test_starts_at_the_head_graph_and_swaps_to_a_newly_published_one(self, repo):
        store = GraphStore(repo)
        view = GraphView(store, "s1")
        link = view.dir / ".hobbes" / "derived"
        assert link.resolve() == repo / ".hobbes" / "derived"
        assert view.env == {"GIT_CEILING_DIRECTORIES": str(store.dir / "views")}
        assert view.turn_start() is False
        snap = take_snapshot(repo)
        publish(store, snap.sha, snap.base)
        assert view.turn_start() is True and view.graph.sha == snap.sha
        assert link.resolve() == store.graphs / snap.sha
        assert view.turn_start() is False
        view.close()
        assert not view.dir.exists()

    def test_a_graph_published_before_the_view_is_not_swapped_in(self, repo):
        store = GraphStore(repo)
        snap = take_snapshot(repo)
        publish(store, snap.sha, snap.base)
        view = GraphView(store, "s2")
        assert view.turn_start() is False and view.graph is None


class TestTurnLabel:
    def label(self, view, **kw) -> str:
        return asyncio.run(turn_label(view, **kw))

    def test_head_graph_clean_then_edited(self, repo):
        view = GraphView(GraphStore(repo), "s")
        head = git(repo, "rev-parse", "HEAD")[:7]
        assert self.label(view) == (
            f"[hobbes] knowledge graph @ {head} (the repo's ingest); changed since: none. "
            "The hobbes tools answer from that graph; read changed files directly."
        )
        (repo / "app.py").write_text("def main():\n    return 1\n")
        (repo / "new.py").write_text("x = 1\n")
        assert "changed since: app.py, new.py." in self.label(view)
        assert self.label(view, refreshing=True).endswith(
            "changed since: app.py, new.py; a refresh is running. "
            "The hobbes tools answer from that graph; read changed files directly."
        )

    def test_a_session_graph_names_its_snapshot(self, repo):
        store = GraphStore(repo)
        view = GraphView(store, "s")
        (repo / "new.py").write_text("x = 1\n")
        snap = take_snapshot(repo)
        publish(store, snap.sha, snap.base)
        view.turn_start()
        assert (f"@ {snap.sha[:7]} (snapshot of the working tree on top of {snap.base[:7]}, lane A only); "
                "changed since: none."
                in self.label(view))

    def test_long_lists_are_cut(self, repo):
        view = GraphView(GraphStore(repo), "s")
        for i in range(MAX_LISTED + 3):
            (repo / f"f{i:02}.py").write_text("")
        assert self.label(view).count(".py") == MAX_LISTED and "(+3 more)" in self.label(view)

    def test_no_graph_yet(self, repo):
        shutil.rmtree(repo / ".hobbes")
        view = GraphView(GraphStore(repo), "s")
        assert self.label(view) == "[hobbes] no knowledge graph yet: run `hobbes ingest` on the repo"


class TestChat:
    @pytest.fixture(autouse=True)
    def agents_file(self, tmp_path, monkeypatch):
        path = tmp_path / "agents.toml"
        path.write_text(f"[agents.fake]\ncommand = {json.dumps([sys.executable, str(FAKE_AGENT)])}\n")
        monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))

    @pytest.fixture
    def proxy(self, tmp_path, monkeypatch) -> Path:
        path = tmp_path / "hobbes-proxy"
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
        monkeypatch.setenv("HOBBES_PROXY", str(path))
        return path

    @pytest.fixture
    def instant_extract(self, monkeypatch):
        async def extract(store, sha, base):
            publish(store, sha, base)

        monkeypatch.setattr(GraphStore, "extract", extract)

    def chat(self, monkeypatch, lines: str, *argv: str) -> int:
        monkeypatch.setattr(sys, "stdin", io.StringIO(lines))
        return cli.main(["chat", "--agent", "fake", "--no-refresh", *argv])

    def test_each_line_is_a_turn_on_one_session(self, monkeypatch, capsys):
        assert self.chat(monkeypatch, "hi\n\nthere you\n") == 0
        captured = capsys.readouterr()
        assert captured.out == "hi [permission: denied]\nthere you [permission: denied]\n"
        assert "knowledge tools" not in captured.err and "[hobbes]" not in captured.err

    def test_label_then_refresh_then_swapped_graph(self, repo, proxy, instant_extract, monkeypatch, capsys):
        head = git(repo, "rev-parse", "HEAD")
        assert self.chat(monkeypatch, "write new.py x = 1\nmcp?\n", "--repo", str(repo)) == 0
        out = capsys.readouterr().out.splitlines()
        assert out[0] == (
            f"label: [hobbes] knowledge graph @ {head[:7]} (the repo's ingest); changed since: none. "
            "The hobbes tools answer from that graph; read changed files directly."
        )
        assert out[1] == "wrote new.py"
        store = GraphStore(repo)
        snap = store.current()
        assert snap is not None and snap.base == head
        assert out[2].startswith(
            f"label: [hobbes] knowledge graph @ {snap.sha[:7]} "
            f"(snapshot of the working tree on top of {head[:7]}, lane A only); "
            "changed since: none"  # "; a refresh is running" while the published snapshot is pinned
        )
        (server,) = json.loads(out[3])
        view_dir = server["args"][server["args"].index("--repo") + 1]
        assert Path(view_dir).parent == store.dir / "views"
        assert server["env"] == [{"name": "GIT_CEILING_DIRECTORIES", "value": str(store.dir / "views")}]
        assert not Path(view_dir).exists()  # removed when the session ended
        assert not git(repo, "for-each-ref", "refs/hobbes/")  # the session's pin is dropped

    def test_refresh_errors_are_reported_and_the_session_goes_on(self, repo, proxy, monkeypatch, capsys):
        async def extract(store, sha, base):
            raise RuntimeError("boom")

        monkeypatch.setattr(GraphStore, "extract", extract)
        assert self.chat(monkeypatch, "write a.py 1\nwrite b.py 2\n", "--repo", str(repo)) == 0
        captured = capsys.readouterr()
        assert captured.out.count("wrote ") == 2
        assert "hobbes: graph refresh failed: extract" in captured.err and "boom" in captured.err
