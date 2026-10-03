"""The agent entry docs stay small, and say where everything else went.

``CLAUDE.md`` is the entry point (``AGENTS.md`` is its byte-for-byte copy)
and ``docs/session-handoff.md`` is the resume point. Both are read whole
at the start of every session, so their length is spent on every session.
The caps are hard; the targets (about 200 and about 100 lines) are the
docs' own business. Open items live in ``docs/currently-open.md``,
procedures in ``docs/runbook.md``, and every doc the entry docs point
to must exist."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

CAPS = {"CLAUDE.md": 250, "docs/session-handoff.md": 150}


def lines(path: str) -> int:
    return len((ROOT / path).read_text().splitlines())


def test_the_entry_docs_are_under_their_caps():
    over = {path: lines(path) for path, cap in CAPS.items() if lines(path) > cap}
    assert not over, f"over the cap (move a section into its own doc): {over}"


def test_agents_md_is_claude_md():
    assert (ROOT / "AGENTS.md").read_bytes() == (ROOT / "CLAUDE.md").read_bytes()


def test_the_entry_docs_point_at_the_open_items_and_the_runbook():
    for path in CAPS:
        text = (ROOT / path).read_text()
        assert "currently-open.md" in text, path
    assert "runbook.md" in (ROOT / "CLAUDE.md").read_text()


def test_every_doc_the_entry_docs_name_exists():
    """A bare name (``field.md``, after ``docs/comparative/README.md``) is
    read relative to the cell it sits in, so it need only exist under docs/."""
    names = {p.name for p in (ROOT / "docs").rglob("*.md")}
    missing = []
    for path in CAPS:
        base = (ROOT / path).parent
        for ref in re.findall(r"`((?:docs/|bench/)?[\w./-]+\.md)`|\]\(([\w./-]+\.md)\)", (ROOT / path).read_text()):
            name = ref[0] or ref[1]
            if "NNN" in name:
                continue
            if "/" not in name and name in names:
                continue
            if not any(p.exists() for p in (ROOT / name, base / name, ROOT / "docs" / name)):
                missing.append(f"{path}: {name}")
    assert not missing, missing
