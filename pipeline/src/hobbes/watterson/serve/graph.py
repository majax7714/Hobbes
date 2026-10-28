"""The graph panel's data: views of ``hobbes levels`` shaped for the TUI (DEC-015).

The plugin in ``tui/plugins/graph`` asks for one view at a time over
opencode's RPC call (``POST /api/rpc/hobbes/view``). ``GraphViews`` builds
the level document from the repo's ``.hobbes/derived/`` (DEC-014), builds it
again when ``graph.json`` changes, and turns a view into display rows, so
the plugin only draws them. ``changed`` tells the server when to push
``rpc.hobbes.changed``.
"""

from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Any

from hobbes import artifacts
from hobbes.watterson import levels
from hobbes.watterson.levels import _counts, describe


class GraphViews:
    """The level document of one repo, rebuilt when its graph changes."""

    def __init__(self, repo: str | Path) -> None:
        self.repo = Path(repo)
        self._doc: dict[str, Any] | None = None
        self._built: tuple[int, int] | None = None
        self._seen = self._stamp()

    def _stamp(self) -> tuple[int, int] | None:
        try:
            info = artifacts.artifact_path(self.repo, "graph.json").stat()
        except OSError:
            return None
        return info.st_mtime_ns, info.st_size

    def changed(self) -> bool:
        """Whether ``graph.json`` changed (or appeared) since the last call."""
        stamp = self._stamp()
        if stamp == self._seen:
            return False
        self._seen = stamp
        return True

    def document(self) -> dict[str, Any]:
        """The level document; raises ``artifacts.ArtifactError`` with no graph."""
        stamp = self._stamp()
        if self._doc is None or stamp != self._built:
            graph = artifacts.load_graph(self.repo)
            extras = {}
            for name in ("tests", "interfaces"):
                try:
                    extras[name] = artifacts.load(self.repo, f"{name}.json")
                except artifacts.ArtifactError:
                    extras[name] = None
            self._doc = levels.build(graph, self.repo, extras["tests"], extras["interfaces"])
            self._built = stamp
        return self._doc

    def view(self, view_id: str | None = None) -> dict[str, Any]:
        """One view as the panel shows it, or ``{"error": …}``."""
        try:
            doc = self.document()
        except artifacts.ArtifactError as exc:
            return {"error": f"No graph for this repo: {exc}"}
        view_id = doc["root_view"] if view_id is None else view_id.rstrip("/")
        view = doc["views"].get(view_id)
        if view is None:
            return {"error": f"No view {view_id!r} in the graph."}
        return shape(doc, view)


def shape(doc: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """A level-model view as display rows: boxes in dependency order (a
    flow's in call order), each with what it holds, the view it opens and
    its links within the view."""
    labels = {b["id"]: b["label"] for b in view["boxes"]}
    parent = view["parent"]
    boxes = []
    ordered = view.get("kind") in levels.ORDERED
    for box in view["boxes"] if ordered else sorted(view["boxes"], key=lambda b: (-b["level"], b["id"])):
        opens = box.get("view")
        links = [f"→ {labels[e['to']]}  {_counts(e)}" + ("  (cycle)" if e.get("cycle") else "")
                 for e in view["edges"] if e["from"] == box["id"]]
        links += [f"← {labels[e['from']]}  {_counts(e)}" + ("  (cycle)" if e.get("cycle") else "")
                  for e in view["edges"] if e["to"] == box["id"]]
        label = f"{box['order']}. {box['label']}" if "order" in box else box["label"]
        boxes.append({"id": box["id"], "label": label, "detail": describe(box), "opens": opens,
                      "root": bool(box.get("root")), "links": links, "tests": [_short_test(t) for t in box.get("test_samples", [])]})
    outside = []
    for stub in view["stubs"]:
        arrows = [f"out {_counts(stub['out'])}" if stub["out"] else "",
                  f"in {_counts(stub['in'])}" if stub["in"] else ""]
        outside.append(f"{stub['id']}  " + "; ".join(a for a in arrows if a))
    return {
        "id": view["id"], "kind": view.get("kind", "folder"), "title": view["title"], "level": view["level"],
        "parent": parent,
        "parentTitle": None if parent is None else doc["views"][parent]["title"],
        "sha": (doc.get("sha") or "")[:7], "dirty": bool(doc.get("dirty")),
        "notes": (doc["notes"] if view["id"] == doc["root_view"] else []) + view.get("notes", []),
        "boxes": boxes, "outside": outside,
        "cycles": [" <-> ".join(labels[c] for c in cycle) for cycle in view["cycles"]],
    }


def _short_test(test_id: str) -> str:
    """A test id with its file's folders dropped: ``test_cli.py::TestX::test_y``."""
    file, sep, rest = test_id.partition("::")
    return posixpath.basename(file) + sep + rest
