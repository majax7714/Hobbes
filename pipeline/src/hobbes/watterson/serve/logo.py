"""The app's home-screen logo: pixel art the TUI plugin draws over opencode's (DEC-017).

``payload()`` is what RPC ``hobbes.logo`` returns: ``letters``, the word
"hobbes" in this module's own block font, and ``art``, the user's own
picture from ``~/.watterson/logo.txt`` when that file exists (it is kept
out of the repo: the art there may be derived from drawings that are not
ours to publish). The plugin shows ``art`` when the terminal is big
enough, else ``letters``.

A picture is a pixel grid, two pixels to a terminal cell. The file holds
palette lines (``O e8892b``: a character and its hex colour), a blank
line, then the grid rows. ``.`` is transparent; ``T`` and ``t`` take the
theme's text and muted colours, so letters follow the theme. Lines
starting with ``#`` are comments.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

#: The block font: 8 x 12 pixels, rows 0-3 the ascender.
GLYPHS = {
    "h": ["##......"] * 4 + ["#######.", "########"] + ["##....##"] * 6,
    "o": ["........"] * 4 + [".######.", "########"] + ["##....##"] * 4 + ["########", ".######."],
    "b": ["##......"] * 4 + ["#######.", "########"] + ["##....##"] * 4 + ["########", "#######."],
    "e": ["........"] * 4 + [".######.", "########", "##....##", "########", "########", "##......",
                             "########", ".#######"],
    "s": ["........"] * 4 + [".#######", "########", "##......", "#######.", ".#######", "......##",
                             "########", "#######."],
}
GAP = 2
_COLOUR = re.compile(r"^(\S)\s+#?([0-9a-fA-F]{6})$")


def logo_path(env=os.environ) -> Path:
    return Path(env.get("HOBBES_LOGO") or "~/.watterson/logo.txt").expanduser()


def letters(word: str = "hobbes") -> dict[str, Any]:
    """*word* in the block font, in the theme's text colour."""
    rows = [""] * 12
    for i, ch in enumerate(word):
        for y, line in enumerate(GLYPHS[ch]):
            rows[y] += ("." * GAP if i else "") + line.replace("#", "T")
    return {"rows": rows, "palette": {}}


def parse(text: str) -> dict[str, Any]:
    """A picture file's palette and rows; raises ValueError when malformed."""
    palette: dict[str, str] = {}
    rows: list[str] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if line.startswith("#") or (not line and not rows):
            continue
        match = _COLOUR.match(line) if not rows else None
        if match and match.group(1) not in ".Tt":
            palette[match.group(1)] = "#" + match.group(2).lower()
        elif line:
            rows.append(line)
        else:
            raise ValueError(f"line {number}: blank line inside the grid")
    if not rows:
        raise ValueError("no grid rows")
    width = max(len(r) for r in rows)
    rows = [r.ljust(width, ".") for r in rows]
    if len(rows) % 2:
        rows.append("." * width)
    unknown = sorted({ch for r in rows for ch in r} - set(palette) - {".", "T", "t"})
    if unknown:
        raise ValueError(f"characters with no colour: {''.join(unknown)}")
    return {"rows": rows, "palette": palette}


def payload(path: Path | None = None) -> dict[str, Any]:
    """The plugin's logo data: ``letters`` always, ``art`` from the file when
    it reads, and ``error`` when it exists but does not."""
    path = logo_path() if path is None else path
    out: dict[str, Any] = {"letters": letters(), "art": None}
    try:
        out["art"] = parse(path.read_text())
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        out["error"] = f"{path}: {exc}"
    return out
