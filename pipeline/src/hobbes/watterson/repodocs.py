"""The repo's own documentation, for the review page's Docs tab (DEC-021).

``collect`` lists the Markdown files git tracks or would track (``git
ls-files --cached --others --exclude-standard``; a walk of the tree when git
is unavailable), without test fixtures and ``node_modules``, and embeds each
one gzipped and base64-encoded, for the page to unpack when it is opened.
Files over ``MAX_DOC_BYTES`` are listed without their text. Files are read
from the working tree; the result says when HEAD has moved past the graph's
commit.

Reads the repo's files only. Glue outside ``hobbes.extract``.
"""

from __future__ import annotations

import base64
import gzip
import os
import posixpath
import re
import subprocess
from pathlib import Path
from typing import Any

from hobbes.watterson import levels

SUFFIXES = (".md", ".markdown", ".mdx")
MAX_DOC_BYTES = 2 * 1024 * 1024
SKIP_DIRS = frozenset({".git", ".hobbes", "node_modules", ".venv", "venv", "__pycache__", ".tox", "dist", "build"})
STALE_NOTE = "Read from the working tree at {head}, not from the graph's commit {sha}."
_HEADING = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.M)


def _git_files(repo: Path) -> list[str] | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [p for p in out.stdout.decode(errors="replace").split("\0") if p]


def _walk(repo: Path) -> list[str]:
    found = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        rel = Path(root).relative_to(repo).as_posix()
        found += [posixpath.join(rel, f) if rel != "." else f for f in files]
    return found


def _kept(path: str) -> bool:
    parts = path.split("/")
    return (path.lower().endswith(SUFFIXES) and not levels.is_fixture(path)
            and not any(p in SKIP_DIRS for p in parts[:-1]))


def _order(path: str) -> tuple:
    """The repo's top level first, then folder by folder; a folder's README
    before its other files."""
    folder, name = posixpath.split(path.lower())
    return (folder != "", folder, not name.startswith("readme"), name)


def title(text: str, path: str) -> str:
    """A document's first ``#`` heading, else its file name."""
    found = _HEADING.search(text)
    return re.sub(r"[*_`]", "", found.group(1)).strip() if found else posixpath.basename(path)


def collect(repo: str | Path, sha: str | None = None, head: str | None = None) -> dict[str, Any]:
    """The docs listing: ``files`` (path, title, bytes, and ``gz``, the
    gzipped text in base64, or ``skipped``) and ``notes``."""
    repo = Path(repo)
    paths = _git_files(repo)
    if paths is None:
        paths = _walk(repo)
    files = []
    for path in sorted({p for p in paths if _kept(p)}, key=_order):
        try:
            raw = (repo / path).read_bytes()
        except OSError:
            continue
        entry: dict[str, Any] = {"path": path, "bytes": len(raw)}
        if len(raw) > MAX_DOC_BYTES:
            entry.update(title=posixpath.basename(path), skipped=f"over {MAX_DOC_BYTES // (1024 * 1024)} MB")
        else:
            entry.update(title=title(raw.decode(errors="replace"), path),
                         gz=base64.b64encode(gzip.compress(raw, 9, mtime=0)).decode())
        files.append(entry)
    notes = []
    if head and sha and head != sha:
        notes.append(STALE_NOTE.format(head=head[:7], sha=sha[:7]))
    return {"files": files, "notes": notes}
