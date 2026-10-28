"""opencode file diffs from a tool call's ACP diff blocks (DEC-013).

The TUI draws an edit, in the transcript and in its permission prompt, from
a unified patch of the whole file, the way opencode's own edit tool builds
one (``createTwoFilesPatch``, ``core/src/tool/plugin/file-diff.ts`` at
v2.0.29). Harnesses often send only the edited snippet, so the patch is
built against the file on disk when the snippet can be placed in it: before
the edit is applied its old text is there exactly once, after it its new
text is. Otherwise the patch shows the snippet alone, numbered from line 1.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

from hobbes.watterson.providers.events import FileDiff

#: Files larger than this are not read; their patch is the snippet alone.
MAX_BYTES = 1_000_000


def file_diffs(diffs: tuple[FileDiff, ...], root: Path, *, applied: bool) -> list[dict[str, Any]]:
    """One opencode ``FileDiff`` per file the blocks name, in order.
    ``applied`` says whether the file on disk already holds the edit."""
    by_path: dict[str, list[FileDiff]] = {}
    for diff in diffs:
        by_path.setdefault(diff.path, []).append(diff)
    return [_file_diff(path, items, root, applied) for path, items in by_path.items()]


def _file_diff(path: str, items: list[FileDiff], root: Path, applied: bool) -> dict[str, Any]:
    before, after = _texts(_read(path), items, applied)
    shown = _relative(path, root)
    lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(), shown, shown, lineterm=""))
    body = lines[2:]
    return {
        "file": shown,
        "filePath": path,
        "patch": "\n".join(lines) + "\n" if lines else "",
        "status": "added" if all(d.old_text is None for d in items) else "modified",
        "additions": sum(line.startswith("+") for line in body),
        "deletions": sum(line.startswith("-") for line in body),
    }


def _texts(current: str | None, items: list[FileDiff], applied: bool) -> tuple[str, str]:
    """The file before and after the edit, or the snippets when they cannot be placed."""
    olds = [d.old_text or "" for d in items]
    news = [d.new_text for d in items]
    if current is not None and all(d.old_text is not None for d in items):
        found, put = (news, olds) if applied else (olds, news)
        if all(text and current.count(text) == 1 for text in found):
            other = current
            for a, b in zip(found, put):
                other = other.replace(a, b, 1)
            return (other, current) if applied else (current, other)
    return "\n".join(olds), "\n".join(news)


def _read(path: str) -> str | None:
    try:
        file = Path(path)
        if file.stat().st_size > MAX_BYTES:
            return None
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _relative(path: str, root: Path) -> str:
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return path
    return path if rel.startswith("..") else rel
