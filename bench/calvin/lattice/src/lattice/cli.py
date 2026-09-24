"""`lattice` — read a target's kernel lattice from the command line.

    lattice map   <target> [--json]   the cells per ISA: counts by kind, slots, and what did not fit
    lattice task  <target> <cell-id>  the task record for one cell, as JSON
    lattice punch <target> <cell-id>  that cell's file with its body replaced by the hole

Nothing here compiles or runs the target: the graders are their own module, and they run in the image
(ADR-092, C-64). `<target>` is a checkout's root — the directory holding `src/distance-*.c`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import holes, task
from .cells import ISAS, Lattice, UnknownCell, build

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code: 0, or 2 for a cell id no lattice has."""
    parser = argparse.ArgumentParser(prog="lattice", description="sqlite-vector's kernel lattice, its cells and its holes")
    verbs = parser.add_subparsers(dest="verb", required=True)

    mapper = verbs.add_parser("map", help="the cells per ISA")
    mapper.add_argument("target", type=Path)
    mapper.add_argument("--json", action="store_true", help="the map as JSON rather than a table")

    tasker = verbs.add_parser("task", help="one cell's task record, as JSON")
    tasker.add_argument("target", type=Path)
    tasker.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")

    puncher = verbs.add_parser("punch", help="one cell's file with its body punched out")
    puncher.add_argument("target", type=Path)
    puncher.add_argument("cell", help="a cell id, <isa>/<type>/<metric>")

    args = parser.parse_args(argv)
    lattice = build(args.target)

    if args.verb == "map":
        print(json.dumps(_map(lattice), indent=2) if args.json else _table(lattice))
        return 0

    try:
        cell = lattice.get(args.cell)
    except UnknownCell:
        print(f"lattice: no cell {args.cell!r}; try `lattice map {args.target}`", file=sys.stderr)
        return 2

    if args.verb == "task":
        print(task.dumps(task.build(lattice, cell)))
    else:
        print(holes.punch(lattice.text(cell), cell), end="")
    return 0


def _map(lattice: Lattice) -> dict:
    return {
        "root": str(lattice.root),
        "isas": [_row(lattice, isa) for isa in ISAS if isa in lattice.sources],
        "unmatched": [
            {"name": u.name, "file": u.file, "line": u.line, "reason": u.reason} for u in lattice.unmatched
        ],
    }


def _row(lattice: Lattice, isa: str) -> dict:
    cells = lattice.by_isa(isa)
    return {
        "isa": isa,
        "file": lattice.sources[isa].file,
        "native": cells[0].native if cells else isa in {"sse2", "avx2", "avx512"},
        "cells": len(cells),
        "impl": sum(1 for c in cells if c.kind == "impl"),
        "wrapper": sum(1 for c in cells if c.kind == "wrapper"),
        "body": sum(1 for c in cells if c.kind == "body"),
        "slots": sum(len(c.slots) for c in cells),
    }


def _table(lattice: Lattice) -> str:
    header = f"{'isa':<8}{'native':<8}{'cells':>6}{'impl':>6}{'wrapper':>9}{'body':>6}{'slots':>7}  file"
    lines = [f"lattice of {lattice.root}", header, "-" * len(header)]
    for row in _map(lattice)["isas"]:
        lines.append(
            f"{row['isa']:<8}{'yes' if row['native'] else 'no':<8}{row['cells']:>6}{row['impl']:>6}"
            f"{row['wrapper']:>9}{row['body']:>6}{row['slots']:>7}  {row['file']}"
        )
    if lattice.unmatched:
        lines.append("")
        lines.append("unmatched:")
        lines += [f"  {u.file}:{u.line} {u.name} — {u.reason}" for u in lattice.unmatched]
    else:
        lines.append("")
        lines.append("unmatched: none")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - the console script is the entry point
    raise SystemExit(main())
