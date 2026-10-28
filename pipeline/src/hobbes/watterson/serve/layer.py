"""The Hobbes layer of one app's repo: off until started (DEC-016).

``Layer`` holds whether Hobbes is on for the repo the app opened on, and
starts it: a graph freshness check (DEC-005), then, when the graph is
stale or missing, ``hobbes ingest`` in a child process so the server keeps
answering. Its output goes to ``log_path``; the app shows the elapsed time.
States: ``unavailable`` (not a git repo, or no commits; never changes),
``off``, ``starting``, ``on`` and ``failed``. Every change calls
``notify`` with the new ``status()``, which the server pushes to the TUI
as ``rpc.hobbes.status``.

What "on" switches on so far: the graph panel. Knowledge tools and
between-turn refresh come in DEC-016's slice 3.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from hobbes.watterson.freshness import CANNOT_CHECK, check_freshness

#: ``ingest(repo, log_path) -> exit code``.
Ingest = Callable[[Path, Path], Awaitable[int]]


async def run_ingest(repo: Path, log_path: Path) -> int:
    """``hobbes ingest --repo repo`` in a child process, output appended to *log_path*."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        log.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} hobbes ingest --repo {repo}\n".encode())
        log.flush()
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "hobbes.watterson.cli", "ingest", "--repo", str(repo),
            stdin=asyncio.subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            return await proc.wait()
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            await proc.wait()
            raise


class Layer:
    """Whether Hobbes is on for *repo*, and starting or stopping it."""

    def __init__(self, repo: str | Path, log_path: Path, *, notify: Callable[[dict[str, Any]], None],
                 ingest: Ingest = run_ingest) -> None:
        self.repo = Path(repo)
        self.log_path = log_path
        self.notify = notify
        self._ingest = ingest
        self._task: asyncio.Task[None] | None = None
        self.since: float | None = None
        check = check_freshness(self.repo)
        if check.status in CANNOT_CHECK:
            self.state, self.detail = "unavailable", "Hobbes needs a git repo with a commit."
        else:
            self.state, self.detail = "off", ""
            self.repo = check.root

    @property
    def on(self) -> bool:
        return self.state == "on"

    def status(self) -> dict[str, Any]:
        return {"state": self.state, "detail": self.detail, "repo": str(self.repo),
                "since": None if self.since is None else int(self.since * 1000)}

    def _set(self, state: str, detail: str = "") -> None:
        self.state, self.detail = state, detail
        self.since = time.time() if state == "starting" else None
        self.notify(self.status())

    def start(self) -> dict[str, Any]:
        """Begin starting (no-op unless off or failed); returns the status."""
        if self.state in ("off", "failed"):
            self._set("starting", "checking the graph")
            self._task = asyncio.get_running_loop().create_task(self._start())
        return self.status()

    async def _start(self) -> None:
        try:
            check = await asyncio.to_thread(check_freshness, self.repo)
            if check.needs_ingest:
                self._set("starting", f"extracting the graph ({check.describe()})")
                code = await self._ingest(self.repo, self.log_path)
                if code != 0:
                    self._set("failed", f"hobbes ingest exited {code}; see {self.log_path}")
                    return
            self._set("on")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - shown in the app, not raised into the loop
            self._set("failed", f"{type(exc).__name__}: {exc}")

    async def started(self) -> bool:
        """Wait for a start in progress to end; True when Hobbes is on."""
        if self.state == "starting" and self._task is not None and not self._task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.shield(self._task)
        return self.on

    async def stop(self) -> dict[str, Any]:
        """Turn Hobbes off, cancelling a start in progress."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self.state != "unavailable":
            self._set("off")
        return self.status()

    async def close(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
