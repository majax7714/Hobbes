# ADR-073 — The knowledge tools accept a path as well as an id

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-017
(`graph_neighborhood`).

## Context

The ADR-072 map lists modules as `` `id` — path ``. sklearn's planner in
the `five-fresh-7b-adr072` run called `graph_neighborhood` three times
with the **path** (`sklearn/utils/_set_output.py`) and got "no node in
the graph" three times — the tool matched ids only. The first planner
to use the knowledge tools at all was refused by their spelling.

## Decision

`Store.Neighborhood` resolves its argument by id, then by **path**
(exact; a trailing `/` tolerated; a path carried by more than one node
resolves to none — ambiguity is not guessed). The edges are then read
under the resolved id. `get_module_doc` is unchanged (its argument is a
document name).

## Consequences

- Proxy binaries rebuilt (static + the sandbox copy).
- Test: `TestNeighborhoodAcceptsTheNodePath` — by path equals by id; an
  unknown path still says "no node".
