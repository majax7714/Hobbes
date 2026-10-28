# The review page's renderer: understand-anything and the alternatives

Survey for DEC-019, which narrows DEC-018's drawing (open-work item 4).
Two subagent surveys on 2026-10-16; the licenses and versions below were
re-checked against the npm registry, and the understand-anything claims
against a shallow clone (read only, nothing installed or run).

## 1. understand-anything

`Egonex-AI/Understand-Anything` (moved from `Lum1104/`), commit
`f2d0164f72fe678805c34245a6df36acededfebd` (2026-10-12), **MIT**. A pnpm
monorepo; the UI is `understand-anything-plugin/packages/dashboard`.

- **Stack** (`dashboard/package.json`): React 19, Vite 6, zustand, Tailwind
  v4; `@xyflow/react` ^12 (React Flow) with its Background, Controls and
  MiniMap; `elkjs` ^0.9.3 (layered, direction DOWN, orthogonal routing,
  `src/utils/layout.ts:75-84`); d3-force for its knowledge view;
  graphology + Louvain for clustering; prism for code; fuse.js for search.
- **View:** two levels (`store.ts:13`, `"overview" | "layer-detail"`). The
  overview is one node per layer with edges between layers summed
  (`utils/edgeAggregation.ts`); a layer shows its files in collapsible
  containers by folder, or Louvain "Cluster A…" when folders are
  degenerate (`utils/containers.ts`). Edges to other layers become
  clickable **portal** nodes (`PortalNode.tsx`). Layout is two-stage ELK:
  containers as blocks, then inside an opened container, then a relayout
  (`GraphView.tsx:690-885`). Card nodes: name, type badge, complexity,
  "tested" pill, summary (`CustomNode.tsx`).
- **Extras:** side panel (`NodeInfo.tsx`), code viewer marking the node's
  lines (needs its local server, `CodeViewer.tsx:30`), guided tour with
  fit-view per step (`LearnPanel.tsx`), fuzzy search (its "semantic" mode
  is a stub, `store.ts:540-543`), edge-type filters, diff overlay
  (`diff-overlay.json`), path finder, SVG/PNG export.
- **Data:** `core/src/types.ts:54-115`: nodes (27 kinds) with an LLM
  `summary`, `tags`, `complexity`; edges (38 kinds) with a fixed `weight`;
  `layers[]` partitions file ids; `tour[]`. Tree-sitter gives symbols,
  imports and line ranges; the LLM writes the graph JSON, including
  calls, inheritance and `tested_by` edges, and a script repairs it
  (`merge-batch-graphs.py`). Edge weights are prompt constants, not counts.
- **Delivery:** a multi-file static build served by a small Node server
  (`packages/viewer/bin/viewer.mjs`) with a per-run token; fonts from
  Google Fonts; no `prefers-color-scheme`.
- **Reuse:** the dashboard reads only JSON and is separable, but its model
  is two levels around LLM fields, it needs a server, and most of the view
  is one 1,603-line component (`GraphView.tsx`). The ideas port easily:
  folder containers, two-stage ELK, portals, summed edges, tour fit-view.

## 2. Libraries

| Library | License | Version (npm) | min+gz (unverified unless noted) | Nested groups | Notes |
|---|---|---|---|---|---|
| `@xyflow/react` | MIT | 12.12.0 | ~59 KB + React ~60 KB | sub-flows (`parentId`); collapse is ours | needs a bundler (React 19 has no UMD); DOM nodes, so rich cards are easy |
| `cytoscape` | MIT | 3.34.4 | ~133 KB | native compound nodes; `cytoscape-expand-collapse` 4.1.1 (MIT) | plain UMD, canvas; Nx and CodeBoarding use it |
| `elkjs` | **EPL-2.0 OR GPL-3.0+** | 0.12.0 | ~456 KB (`elk.bundled.js`) | best hierarchical layout | weak copyleft: ship its notice |
| `@dagrejs/dagre` | MIT | 3.1.1 | ~15 KB | clusters buggy | quick, decent |
| `sigma` + `graphology` | MIT | 4.0.3 | ~113 KB | none | WebGL, 10k+ nodes; overview only |
| AntV G6 v5 | MIT | 5.1.1 | ~380 KB | combos with collapse | docs Chinese-first |
| Mermaid | MIT | 12.2.0 | ~1.5 MB | subgraphs, no collapse | too heavy for an interactive surface |

d3-dag has no compound nodes; vis-network's hierarchical layout is weak.

## 3. Other tools, and ideas worth taking

Nx graph (Cytoscape): folder groups that expand in place or "focus".
Sourcetrail: members nested in classes, bundled edges labelled with counts.
dependency-cruiser and madge (Graphviz): folder clusters, cycles in red.
CodeCharta: delta mode between two versions. CodeBoarding (Cytoscape):
component diagrams that drill into sub-diagrams. GitNexus (Sigma) is
PolyForm Noncommercial and Swark is AGPL: their code is out.

Common ideas that fit Hobbes: containers that open in place, edges labelled
with counts, cycles in red, hover or focus highlighting, search that zooms
to a node, a minimap, a diff overlay between stamps.

## 4. Fit with our constraints

Our views hold at most 12 boxes (`levels.MAX_BOXES`), so React Flow's DOM
cost and ELK's layout time do not bite; laying out each view in the browser
when it opens is cheap. A bundle step is the main new cost; the repo already
runs Node 24 for `tsextract/`.
