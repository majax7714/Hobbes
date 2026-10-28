"""Keep an active session's Hobbes graph current between turns (DEC-006).

Re-extracting the live tree would race the agent's edits, so a session
extracts **snapshots** (``hobbes.watterson.snapshot``) instead, and only between
turns:

- ``GraphStore`` keeps one repo's session graphs in the cache, under
  ``$HOBBES_CACHE_DIR/sessions/<repo>-<hash>/`` (default
  ``~/.watterson/cache``): one reused linked worktree (``worktree/``,
  detached at the snapshot being extracted, so a new snapshot is a
  checkout of only what changed), each graph under ``graphs/<sha>/``,
  and ``current.json`` naming the graph in use. A graph directory is
  complete before it is renamed into place and ``current.json`` is
  replaced by rename, so a reader sees the old graph or the new one. The
  last ``KEEP_GRAPHS`` graphs stay; older ones are deleted. The repo's own
  ``.hobbes/derived/`` stays the HEAD graph that ``hobbes ingest`` writes.
- Extraction is ``hobbes ingest`` run on the worktree in a subprocess,
  **lane A only** (``HOBBES_SCIP=0``): about 16 s on hobbes-public, where
  lane B is unmeasured. The label says so. One extraction per repo at a
  time (a ``flock`` on the store), across sessions.
- ``Refresher`` is driven by the session: call ``turn_ended()`` at each
  turn end. It snapshots the tree and allows **at most one running and one
  pending** extraction; a newer snapshot replaces the pending one. Since a
  snapshot's SHA depends only on tree and HEAD, a turn that changed
  nothing needs no run. A published snapshot is pinned under
  ``refs/hobbes/snapshot/<session>`` until ``aclose()``; older snapshots
  are left for ``git gc``.
- ``label()`` says what a graph answer is grounded on:
  ``graph @ <snapshot> (…); changed since: <files>``, from a fresh
  snapshot diffed against the graph's, so the model knows which files to
  read directly.

Nothing here calls the extractor in-process or changes ``hobbes.extract``.
Wired into ``hobbes chat`` by ``hobbes.watterson.live_session`` (DEC-009), which
shows the graph to the knowledge proxy and puts the label on each prompt.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from hobbes.watterson.freshness import DERIVED_FILES
from hobbes.watterson.snapshot import (
    SnapshotError,
    changed_files,
    pin,
    repo_root,
    take_snapshot,
    unpin,
)

#: The cache root when ``HOBBES_CACHE_DIR`` is unset (the CLI's default too).
DEFAULT_CACHE_DIR = "~/.watterson/cache"
#: Graphs kept per repo, the current one included.
KEEP_GRAPHS = 5
#: Session graphs are lane A only; the label names it.
LANES = "lane A only"
_LOCK_POLL = 0.1
_SHORT = 7
_GIT_TIMEOUT = 120.0


class ExtractError(RuntimeError):
    """A snapshot could not be extracted; the message carries the log's tail."""


def cache_dir() -> Path:
    return Path(os.environ.get("HOBBES_CACHE_DIR") or DEFAULT_CACHE_DIR).expanduser().resolve()


@dataclass(frozen=True)
class SessionGraph:
    """A published session graph: snapshot ``sha`` of commit ``base``."""

    sha: str
    base: str
    lanes: str
    path: Path


class GraphStore:
    """One repo's session graphs in the cache; see the module doc."""

    def __init__(self, repo: str | Path, root: Path | None = None) -> None:
        self.repo = repo_root(repo)
        digest = hashlib.sha256(str(self.repo).encode()).hexdigest()[:12]
        self.dir = (root or cache_dir()) / "sessions" / f"{self.repo.name}-{digest}"
        self.worktree = self.dir / "worktree"
        self.graphs = self.dir / "graphs"
        self.log = self.dir / "ingest.log"

    def current(self) -> SessionGraph | None:
        """The graph in use, or None before the first one is published."""
        try:
            doc = json.loads((self.dir / "current.json").read_text())
            sha = doc["sha"]
            graph = SessionGraph(sha, doc["base"], doc["lanes"], self.graphs / sha)
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return graph if graph.path.is_dir() else None

    def has(self, sha: str) -> bool:
        return (self.graphs / sha / "graph.json").is_file()

    async def extract(self, sha: str, base: str) -> SessionGraph:
        """Extract snapshot *sha* (taken on *base*) unless already kept, then publish it."""
        self.dir.mkdir(parents=True, exist_ok=True)
        async with self._locked():
            if not self.has(sha):
                self._checkout(sha)
                await self._ingest()
                self._keep(sha)
            return self._publish(sha, base)

    @contextlib.asynccontextmanager
    async def _locked(self):
        with open(self.dir / ".lock", "w") as handle:
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    await asyncio.sleep(_LOCK_POLL)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _git(self, cwd: Path, *args: str) -> None:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True, text=True, check=False, timeout=_GIT_TIMEOUT,
        )
        if out.returncode != 0:
            raise ExtractError(f"git {args[0]} failed: {out.stderr.strip()}")

    def _checkout(self, sha: str) -> None:
        """Move the reused worktree to *sha*, creating it the first time."""
        if (self.worktree / ".git").is_file():
            self._git(self.worktree, "checkout", "-q", "-f", "--detach", sha)
            return
        shutil.rmtree(self.worktree, ignore_errors=True)
        self._git(self.repo, "worktree", "prune")
        self._git(self.repo, "worktree", "add", "-q", "-f", "--detach", str(self.worktree), sha)

    async def _ingest(self) -> None:
        """``hobbes ingest`` on the worktree, lane A only, output to ``ingest.log``."""
        env = {**os.environ, "HOBBES_SCIP": "0"}
        with open(self.log, "wb") as log:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "hobbes.watterson.cli", "ingest", "--repo", str(self.worktree),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env,
            )
            try:
                code = await proc.wait()
            except asyncio.CancelledError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()
                raise
        if code != 0:
            tail = self.log.read_text(errors="replace").strip().splitlines()[-5:]
            raise ExtractError(f"ingest exited {code}: " + " | ".join(tail))

    def _keep(self, sha: str) -> None:
        """Copy the worktree's artifacts to ``graphs/<sha>``, renamed in whole."""
        source = self.worktree / ".hobbes" / "derived"
        for name in DERIVED_FILES:
            stamped = json.loads((source / name).read_text()).get("sha")
            if stamped != sha:
                raise ExtractError(f"{name} is stamped {stamped}, expected {sha}")
        self.graphs.mkdir(parents=True, exist_ok=True)
        staging = self.graphs / f".tmp-{sha}"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        for name in DERIVED_FILES:
            shutil.copy2(source / name, staging / name)
        shutil.rmtree(self.graphs / sha, ignore_errors=True)  # a partial leftover; has() said no
        staging.rename(self.graphs / sha)

    def _publish(self, sha: str, base: str) -> SessionGraph:
        tmp = self.dir / "current.json.tmp"
        tmp.write_text(json.dumps({"sha": sha, "base": base, "lanes": LANES}, indent=2) + "\n")
        os.replace(tmp, self.dir / "current.json")
        os.utime(self.graphs / sha)  # most recently used, for pruning
        self._prune(keep=sha)
        return SessionGraph(sha, base, LANES, self.graphs / sha)

    def _prune(self, keep: str) -> None:
        kept = sorted(
            (p for p in self.graphs.iterdir() if p.is_dir() and not p.name.startswith(".")),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        for old in kept[KEEP_GRAPHS:]:
            if old.name != keep:
                shutil.rmtree(old, ignore_errors=True)


@dataclass(frozen=True)
class GraphLabel:
    """What a graph answer is grounded on, and which files to distrust."""

    graph: SessionGraph | None
    changed: tuple[str, ...] = ()
    refreshing: bool = False

    def __str__(self) -> str:
        if self.graph is None:
            return "no session graph yet" + ("; extracting" if self.refreshing else "")
        g = self.graph
        head = f"graph @ {g.sha[:_SHORT]} (snapshot of {g.base[:_SHORT]}, {g.lanes})"
        changed = ", ".join(self.changed) if self.changed else "none"
        tail = "; refresh running" if self.refreshing else ""
        return f"{head}; changed since: {changed}{tail}"


class Refresher:
    """Re-extract a session's graph between turns; see the module doc.

    ``extract(sha, base)`` is injectable for tests; by default it is the
    store's. Failures are kept in ``errors`` and never raised into the
    session; the last good graph stays current.
    """

    def __init__(self, repo: str | Path, *, store: GraphStore | None = None,
                 extract=None, session: str | None = None) -> None:
        self.store = store or GraphStore(repo)
        self.repo = self.store.repo
        self.session = session or uuid.uuid4().hex[:12]
        self._extract = extract or self.store.extract
        self._running: asyncio.Task | None = None
        self._running_sha: str | None = None
        self._pending: tuple[str, str] | None = None
        self._closed = False
        self.errors: list[str] = []

    @property
    def busy(self) -> bool:
        return self._running is not None

    async def turn_ended(self) -> str | None:
        """Snapshot the tree and schedule its extraction; the snapshot SHA,
        or None when nothing needs to run (or the snapshot failed)."""
        if self._closed:
            return None
        try:
            snap = await asyncio.to_thread(take_snapshot, self.repo)
        except SnapshotError as exc:
            self.errors.append(f"snapshot: {exc}")
            return None
        if self._running is None:
            current = self.store.current()
            if current is not None and current.sha == snap.sha:
                return None
            self._start(snap.sha, snap.base)
        elif snap.sha == self._running_sha:
            self._pending = None  # the tree is back to what is being extracted
        else:
            self._pending = (snap.sha, snap.base)  # replaces any older pending one
        return snap.sha

    def _start(self, sha: str, base: str) -> None:
        self._running_sha = sha
        self._running = asyncio.create_task(self._run(sha, base))

    async def _run(self, sha: str, base: str) -> None:
        try:
            await self._extract(sha, base)
            await asyncio.to_thread(pin, self.repo, self.session, sha)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the session goes on with the last good graph
            self.errors.append(f"extract {sha[:_SHORT]}: {exc}")
        finally:
            self._running = self._running_sha = None
            nxt, self._pending = self._pending, None
            if nxt and not self._closed:
                self._start(*nxt)

    async def wait_idle(self) -> None:
        """Return once nothing is running or pending."""
        while self._running is not None:
            await asyncio.wait([self._running])

    async def label(self) -> GraphLabel:
        """The current graph, the files changed since its snapshot, and
        whether a refresh is under way."""
        graph = self.store.current()
        changed: tuple[str, ...] = ()
        if graph is not None:
            try:
                now = await asyncio.to_thread(take_snapshot, self.repo)
                changed = tuple(await asyncio.to_thread(changed_files, self.repo, graph.sha, now.sha))
            except SnapshotError as exc:
                self.errors.append(f"label: {exc}")
        return GraphLabel(graph, changed, self.busy)

    async def aclose(self) -> None:
        """Drop the pending run, stop the running one, unpin the session's ref."""
        self._closed = True
        self._pending = None
        task = self._running
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        with contextlib.suppress(SnapshotError):
            await asyncio.to_thread(unpin, self.repo, self.session)

    async def __aenter__(self) -> Refresher:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()
