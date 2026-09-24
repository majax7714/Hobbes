"""The task format (`calvin-experiments.md` §5.2): one JSON-able record per cell.

The rule the programme runs on is that the graph fills every field it can and the parser fills only
what the graph cannot hold (ADR-151). This module is the first half of that: everything derivable from
the files — the name, the signature, where it sits in the grid, the slots it is reached through, its
axis neighbours, the C-0 context above it, the helpers and macros it may call — is filled here,
deterministically. The fields the graph and the teacher own are present and `null`:

| field | filled by | unit |
|---|---|---|
| `callees` | the graph, from the target's ingest | the unit after this one |
| `contract`, `edge_cases`, `like` | the general model, parsing a request (K-1) | later |

A record never carries the target's path: `file` is relative to the target's root, and the checkout a
record was built from is not part of the task. Two checkouts of the same SHA must give the same bytes.
"""

from __future__ import annotations

import json

from .cells import Cell, Lattice

__all__ = ["SCHEMA", "build", "dumps"]

#: the record's version. A field added or a meaning changed bumps it.
SCHEMA = "lattice-task/1"


def build(lattice: Lattice, cell: Cell) -> dict:
    """The task record for one cell."""
    source = lattice.sources[cell.isa]
    helpers = [
        {"name": fn.name, "signature": fn.signature}
        for fn in source.scanned.functions
        if fn.static and fn.signature_span.start < cell.signature_span.start
    ]
    return {
        "schema": SCHEMA,
        "cell": cell.id,
        "name": cell.name,
        "file": cell.file,
        "isa": cell.isa,
        "type": cell.type,
        "metric": cell.metric,
        "kind": cell.kind,
        "static": cell.static,
        "signature": cell.signature,
        "slots": [list(slot) for slot in cell.slots],
        "graded_via": [list(slot) for slot in cell.graded_via],
        "neighbours": [neighbour.id for neighbour in lattice.neighbours(cell)],
        "prelude": source.text[: cell.signature_span.start],
        "helpers": helpers,
        "macros": list(source.scanned.defines),
        "callees": None,
        "contract": None,
        "edge_cases": None,
        "like": None,
    }


def dumps(record: dict) -> str:
    """The record as JSON, sorted and indented — the same bytes for the same cell, every time."""
    return json.dumps(record, sort_keys=True, indent=2)
