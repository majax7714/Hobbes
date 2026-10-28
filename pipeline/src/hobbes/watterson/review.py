"""The review page: a repo's level views as one stamped HTML file (DEC-018).

``write`` turns the level document (``hobbes.watterson.levels``, DEC-014) into a
self-contained page, ``review.html`` with the data inlined, and saves it as
``<review dir>/<repo>@<sha7>[-dirty].html``. The drawing is the bundle
built in ``review/`` (React Flow and ELK, DEC-019), inlined too: it lays out
each view (boxes in dependency layers, flows as numbered steps), opens a
box's view on click, and links files and ``path:line`` samples into VS
Code. The page needs no server, network or install, and opens without Hobbes.

The page has four tabs: the architecture views (``hobbes.watterson.architecture``,
DEC-020), shown first, the code map (the level views), the repo's own
documentation (``hobbes.watterson.repodocs``, DEC-021), compressed, and its agent
mapping as it stands (``hobbes.watterson.mapper.describe``, DEC-023). The embedded
data drops the boxes' member lists, which are most of the document's size
and which the page does not show.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from hobbes import __version__
from hobbes.watterson import architecture, levels, repodocs

TEMPLATE = Path(__file__).with_name("review.html")
APP_DIR = Path(__file__).resolve().parents[4] / "review" / "dist"
BUILD = "cd review && npm ci && npm run build"
_SLOT = "/*__HOBBES_DATA__*/null"
_APP_SLOTS = {"/*__HOBBES_CSS__*/": "review.css", "/*__HOBBES_APP__*/": "review.js"}
_DROP = frozenset({"members"})


class AppMissing(RuntimeError):
    """The page's bundle is not built."""


def review_dir(env=os.environ) -> Path:
    return Path(env.get("HOBBES_REVIEW_DIR") or "~/.watterson/review").expanduser()


def file_name(repo: Path, sha: str | None, dirty: bool | None) -> str:
    stamp = (sha or "nosha")[:7] + ("-dirty" if dirty else "")
    return f"{repo.name or 'repo'}@{stamp}.html"


def page_data(doc: dict[str, Any], repo: Path, generated: float | None = None,
              docs: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the page embeds: the views without member lists, each box with
    its description, the architecture views, the repo's docs (collected
    unless *docs* is given), its agent mapping (DEC-023's Agents tab; None
    when it has none) and the stamp."""
    from hobbes.watterson import mapper

    views = {}
    for view_id, view in doc["views"].items():
        boxes = []
        for box in view["boxes"]:
            slim = {k: v for k, v in box.items() if k not in _DROP}
            slim["detail"] = levels.describe(box)
            boxes.append(slim)
        views[view_id] = {**view, "boxes": boxes}
    return {
        "stamp": {
            "repo": repo.name, "path": str(repo), "sha": doc.get("sha"), "dirty": bool(doc.get("dirty")),
            "generated": time.strftime("%Y-%m-%d %H:%M", time.localtime(generated)),
            "hobbes": __version__, "schema": doc.get("schema"),
        },
        "root": doc["root_view"], "notes": doc.get("notes", []), "omitted": doc.get("omitted", {}),
        "context": doc.get("context", {}), "views": views,
        "architecture": _slim_architecture(doc.get("architecture")),
        "docs": docs if docs is not None else repodocs.collect(repo, doc.get("sha"), architecture._head(repo)),
        "agents": mapper.describe(repo),
    }


def _slim_architecture(arch: dict[str, Any] | None) -> dict[str, Any] | None:
    """The architecture views (DEC-020) without member lists."""
    if not arch:
        return None
    views = {vid: {**view, "boxes": [{k: v for k, v in box.items() if k not in _DROP} for box in view["boxes"]]}
             for vid, view in arch["views"].items()}
    return {**arch, "views": views}


def render(data: dict[str, Any], app_dir: Path | None = None) -> str:
    """The page with the bundle and *data* inlined. ``</`` is escaped in the
    data so no string ends the script; the bundle goes in first, so nothing
    in the data can fill its slots."""
    app_dir = APP_DIR if app_dir is None else app_dir
    page = TEMPLATE.read_text()
    for slot, name in _APP_SLOTS.items():
        try:
            text = (app_dir / name).read_text()
        except FileNotFoundError:
            raise AppMissing(f"the review page is not built ({app_dir / name} is missing): run `{BUILD}`") from None
        if slot not in page:
            raise RuntimeError(f"{TEMPLATE} has no {slot} slot")
        page = page.replace(slot, re.sub(r"</(script|style)", r"<\\/\1", text, flags=re.I), 1)
    if _SLOT not in page:
        raise RuntimeError(f"{TEMPLATE} has no data slot")
    return page.replace(_SLOT, json.dumps(data, separators=(",", ":")).replace("</", "<\\/"), 1)


def write(doc: dict[str, Any], repo: str | Path, out_dir: Path | None = None) -> Path:
    """Save the page for *doc* and return its path."""
    repo = Path(repo).resolve()
    out_dir = review_dir() if out_dir is None else out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / file_name(repo, doc.get("sha"), doc.get("dirty"))
    path.write_text(render(page_data(doc, repo)))
    return path
