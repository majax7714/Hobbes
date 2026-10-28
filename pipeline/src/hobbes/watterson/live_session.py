"""Wire DEC-006's session graphs into a live chat session (DEC-009).

hobbes-proxy reads only ``<repo>/.hobbes/derived/`` (DEC-008), so a chat
session's proxy is pointed at a **view**:
``$HOBBES_CACHE_DIR/sessions/<repo>-<hash>/views/<session>/``, whose
``.hobbes/derived`` is a symlink. It starts at the repo's own
``.hobbes/derived`` (the HEAD graph) and ``GraphView.turn_start`` swaps it,
by rename, to the store's current graph once one was published after the
view was made. The proxy re-reads on every call, so the next answer comes
from the new graph. The view is not a git repo, and ``env`` sets
``GIT_CEILING_DIRECTORIES`` so git never finds one above it; the proxy's
HEAD-based stale warning stays off, and the label says what is stale.

``turn_label`` is the one-line prefix for each turn's prompt (DEC-009
replaces DEC-006's "graph answers carry it"): the graph in the view, and the
files changed since it, from a fresh snapshot diffed against the graph's
commit. The view swaps only at turn start, so label and graph agree for the
whole turn.

Glue outside ``hobbes.extract``; the engine is ``hobbes.watterson.session_graph``.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

from hobbes.watterson.session_graph import GraphStore, SessionGraph
from hobbes.watterson.snapshot import SnapshotError, changed_files, take_snapshot

_SHORT = 7
#: Changed files named in a label before the rest are counted.
MAX_LISTED = 20


class GraphView:
    """One session's view dir; see the module doc."""

    def __init__(self, store: GraphStore, session: str) -> None:
        self.store = store
        self.dir = store.dir / "views" / session
        self.head_graph = store.repo / ".hobbes" / "derived"
        #: The session graph the view shows; None while it shows the HEAD graph.
        self.graph: SessionGraph | None = None
        baseline = store.current()
        self._baseline = baseline.sha if baseline else None
        (self.dir / ".hobbes").mkdir(parents=True, exist_ok=True)
        self._point(self.head_graph)

    @property
    def env(self) -> dict[str, str]:
        """For the proxy: stop git at the views dir, so the view is no repo."""
        return {"GIT_CEILING_DIRECTORIES": str(self.dir.parent)}

    @property
    def target(self) -> Path:
        return self.graph.path if self.graph else self.head_graph

    def turn_start(self) -> bool:
        """Swap to the store's current graph if a newer one was published;
        True when the view changed."""
        current = self.store.current()
        if current is None or current.sha == self._baseline:
            return False
        if self.graph is not None and current.sha == self.graph.sha:
            return False
        self.graph = current
        self._point(current.path)
        return True

    def close(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def _point(self, target: Path) -> None:
        link = self.dir / ".hobbes" / "derived"
        tmp = link.with_name("derived.tmp")
        tmp.unlink(missing_ok=True)
        os.symlink(target, tmp)
        os.replace(tmp, link)


def _stamp(derived: Path) -> str | None:
    try:
        sha = json.loads((derived / "graph.json").read_text()).get("sha")
    except (OSError, ValueError, AttributeError):
        return None
    return sha if isinstance(sha, str) and sha else None


async def turn_label(view: GraphView, *, refreshing: bool = False) -> str:
    """The prefix line for the next turn's prompt."""
    if view.graph is not None:
        g = view.graph
        # "snapshot of <base>" read as "a copy of that commit" to a model in
        # the live check; say it is the working tree.
        sha, what = g.sha, f"snapshot of the working tree on top of {g.base[:_SHORT]}, {g.lanes}"
    else:
        sha, what = _stamp(view.head_graph), "the repo's ingest"
    if sha is None:
        return "[hobbes] no knowledge graph yet: run `hobbes ingest` on the repo"
    try:
        now = await asyncio.to_thread(take_snapshot, view.store.repo)
        changed = await asyncio.to_thread(changed_files, view.store.repo, sha, now.sha)
        listed = ", ".join(changed[:MAX_LISTED]) or "none"
        if len(changed) > MAX_LISTED:
            listed += f" (+{len(changed) - MAX_LISTED} more)"
    except SnapshotError:
        listed = "unknown"
    tail = "; a refresh is running" if refreshing else ""
    return (
        f"[hobbes] knowledge graph @ {sha[:_SHORT]} ({what}); changed since: {listed}{tail}. "
        "The hobbes tools answer from that graph; read changed files directly."
    )
