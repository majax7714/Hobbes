# ADR 023: Interactive graph conventions (Cytoscape)

Date: 2026-08-11
Status: accepted

## Context

D3 gives the web surface an interactive graph via Cytoscape.js, and
architecture §7 makes Graph the first tab — the one a concept-level
review starts from. ADR-008 fixed the conventions for the *export*
renderer (Mermaid, module level, shape-by-kind); the interactive view
consumes `graph.json` directly (ADR-008's closing note) and needs its
own, because interaction changes what the conventions are for: an
export optimizes for a legible static picture, a view optimizes for
finding a node and answering a question about it.

Real repos set the bar: kbet is 104 nodes / 358 module edges, private-repo-A
207 / 602. A default view that draws every node is unreadable at that
size, and layout quality — not fidelity — is what decides whether the
tab is usable.

## Decision

**Module level only**, as ADR-008 — the symbol layer feeds the node
inspector, never the canvas (§10: store symbol-level, render
module-level).

- **Kind styling by shape and color**, extending ADR-008's vocabulary to
  the node kinds M3 and M6 added: internal `module` rounded rectangle;
  `ext:` external dependency hexagon; `env:` variable ellipse; `tf:`
  infrastructure (resource / data / tf-module) diamond. Kind is also the
  filter axis — each kind toggles off in one click, and **externals
  start hidden**, because a repo's dependency fan-out is the single
  largest source of unreadable layout and is rarely what a review is
  about.
- **Edge styling by type**, as ADR-008: `imports` solid, `env-read` /
  `env-set` dashed, `references` (Terraform) dotted, anything else solid
  and labeled with its type — an unstyled new edge type must be visible,
  never invisible.
- **Package grouping is a filter, not a container.** ADR-008 clusters
  into subgraphs; here the top-level package (the id's first segment, so
  root-disambiguated ids like `pipeline:tests` stay whole) drives node
  color-tinting and a package filter. Compound nodes were rejected: they
  fight force layouts at these sizes and make edge endpoints ambiguous.
- **Layout is built-in only** — Cytoscape's `cose` for the general view,
  `breadthfirst` when a single node is focused (a dependency chain reads
  as layers). No layout-extension dependency until a real repo proves
  the built-ins insufficient.
- **Focus mode is the answer to size.** Selecting a node reveals its
  neighborhood to a depth the user sets (1–3) and dims the rest — the
  interactive form of the `graph_neighborhood` tool (ADR-017), which is
  how the graph is actually read at 600 edges.
- **Selection drives one inspector**, joining what the artifacts already
  separate: the node's kind and path, its symbols (from `graph.json`),
  its narrative purpose with a stale badge (ADR-019), the tests guarding
  it (`tests.json`, the `tests_guarding` inverse index), and its typed
  in/out edges — each edge citing the `file:line` evidence the extractor
  recorded. Every citation is a provenance link into the source view.
- **Deterministic input, non-deterministic layout.** Nodes and edges are
  built in sorted order so the same graph gives the same model; the
  force layout's pixel positions are not reproducible and are not meant
  to be. Reproducibility lives in the Mermaid export (ADR-008).

## Alternatives considered

- **Rendering the symbol graph on demand** — 537 symbols / 657 call
  edges on the dogfood repo alone; the inspector and `who_calls` answer
  symbol questions better than a canvas can.
- **Compound nodes for packages** — rejected above; revisit if a repo
  arrives whose packages are few and large.
- **`cytoscape-dagre` / `fcose`** — better layered layouts, but a
  dependency added before a repo has demonstrated the need. The
  breadthfirst-on-focus rule covers the case dagre would serve.
- **Drawing every node by default** — honest, unreadable. Hiding
  externals by default is a visible, one-click-reversible filter, not a
  silent omission.

## Consequences

- The Graph tab is usable at real-repo scale without paging or
  server-side query, because filtering and focus happen client-side over
  an artifact that is a few hundred KB.
- Graph conventions now exist in two places for two renderers; adding a
  node or edge type means touching both, and both fall back to "render
  it visibly, labeled" so an untouched renderer degrades loudly.
- M8's PR mode has a natural home: a graph diff colors added/removed
  edges over this same view rather than introducing a second graph
  surface.
