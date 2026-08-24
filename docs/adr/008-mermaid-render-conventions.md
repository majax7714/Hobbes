# ADR 008: Mermaid render conventions for the module graph

Date: 2026-08-10
Status: accepted

## Context

Architecture §4.1 requires diagrams generated from the graph, never drawn
by hand, with Mermaid as the markdown/export renderer (D3 gives the *web*
surface to Cytoscape.js at M7). The build plan's M2 asks for a module-level
Mermaid export but fixes neither the diagram dialect nor how graph.json
maps onto it.

## Decision

`hobbes render` reads `.hobbes/derived/graph.json` (the ingest artifact —
render is a view over derived data, not a second extraction) and prints a
**`flowchart LR`** document to stdout:

- **Module level only.** The symbol layer is never rendered here — §10:
  store symbol-level, render module-level.
- **Node ids are synthetic** (`n0`, `n1`, … in sorted-node-id order) with
  the real id as the label — graph ids contain `.` and `:` which Mermaid
  ids can't safely carry.
- **Clustering:** internal modules are grouped into a `subgraph` per
  top-level package (everything before the first `.` of the node id, which
  keeps root-disambiguated ids like `pipeline:tests` intact as their own
  group). A group with a single member is left ungrouped — one-node boxes
  are noise.
- **Kind styling by shape:** modules/packages `n["…"]`, external
  dependencies `n[["…"]]`, environment variables `n(["…"])`.
- **Edge styling by type:** `imports` renders `-->`; `env-read` renders
  `-.->`; any future module-edge type renders labeled (`--"type"-->`) so
  new types are visible before they get bespoke styling.
- **Deterministic:** nodes and edges emitted in sorted order; same
  graph.json → byte-identical Mermaid.

## Alternatives considered

- **D2 / Graphviz** — the architecture names Mermaid for the
  markdown/export path; Mermaid renders natively in GitHub and most
  markdown viewers, which is exactly where this export lands.
- **Emitting graph.mmd during ingest** — makes ingest's output surface
  wider for no consumer; render-on-demand keeps derived/ minimal and the
  view always in sync with the artifact it reads.
- **Raw ids as Mermaid ids** — breaks on `ext:yaml` and quoting rules;
  synthetic ids cost nothing since labels carry the truth.

## Consequences

- `hobbes render > graph.mmd` is the whole export story; M7's interactive
  graph consumes graph.json directly and ignores this path.
- C4-style level separation (context/container/component) is deferred until
  there is more than one level worth of data — the module flowchart *is*
  the component level today.
