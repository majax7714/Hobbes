# Tiered graph views: data, prior art, conventions (item 4)

Survey, 2026-10-16. The user's framing: a monolith with five big pieces; a
chart shows how they connect; selecting a piece shows its own chart; and
so on down the levels, with a useful diagram at each level. Decided before
this survey: the top-level grouping defaults to folders.

Data: a lane-A ingest of a scratch clone of `hobbes_public@2089e22`. Gaps
found on the way are in `extraction-gaps.md`.

## What the graph gives each level

- **Module nodes carry `path`**; group by path, never by id (ids are dotted
  for Python, path-like for Go/TS/C, and root-prefixed on clashes).
- **`symbols[].module`** ties symbols to modules; `symbol_edges` (calls,
  uses) roll up to module pairs: 14,187 of 20,685 cross a module boundary.
- **`tests.json`**: each test lists `reaches_modules` (about 6.6 on
  average), so a test can be attached to the group it reaches most.
- **`interfaces.json`**: `cli_entry_points` and `routes`, the inbound
  context of the system view (with gaps 1, 4, 5).

## Folders as the default grouping, measured

| Scope | Groups | Edge pairs | Cycles |
|---|---|---|---|
| repo top level (raw) | 7 (352/188/57/22/8/2/2 modules) | 0 | — |
| `pipeline/src/hobbes` | 16, 8 of them single files | 43 | `bench` ↔ `derive` ↔ `run` |
| `go/internal` | 11 | 12 | none |
| `web/src` | 8 | 18 | none |
| `pipeline/src/hobbes/extract` | flat: 37 files | — | 4 modules |

So folders need: dropping fixtures; one box per language root (a folder
with its own manifest); collapsing single-child folders (`src/`); tests
attached rather than boxed; and a fallback for flat folders. Louvain on
`extract/` gave 4 sensible clusters but moved with its seed (Rand index
0.87-1.0 over seeds 0-5); grouping by filename prefix is deterministic.

## Prior art

- **C4 model** (c4model.com): Context, Containers, Components, Code, plus a
  Dynamic view; one abstraction level per view, labelled arrows, a legend.
- **Structurizr** (Apache-2.0): generatable DSL; exports Mermaid, PlantUML.
- **LikeC4** (MIT): `view of X` drill-down; `likec4 gen mermaid|d2|dot`.
  Best generate-then-export target, needs Node.
- **D2** (MPL-2.0): `layers`/`scenarios` boards give drill-down in one
  file; ASCII output since v0.7.1 (alpha).
- **Dependency structure matrices** (Lattix, NDepend): collapse cycles,
  order by levels (a unit's level is one more than the highest it uses);
  scale to hundreds of modules.
- **dependency-cruiser**: `--collapse <depth|regex>` folder roll-ups, the
  closest match to folders-by-default. **import-linter** `layers` contracts:
  a candidate format for a declared top level. **DependaCharta** (BSD-3):
  tree-sitter, levelization, hierarchy navigation; the closest open
  analogue to levels 1-3.
- Clustering (Bunch, ACDC) is non-deterministic in practice (Lutellier et
  al., ICSE 2015); ACDC is unsuited below 100 files.

URLs and licences are from the survey's sources, not re-fetched.

## Conventions taken

- At most about 12 boxes per view; overflow folds into "+N more"; loose
  single files gather into one box.
- Rolled-up edges keep separate counts (imports, calls, uses) and a few
  sample `path:line`s.
- Cycles are condensed for layering (longest path), and their edges marked.
- Edges leaving a view become stubs named by the sibling folder they reach.

## Terminal rendering (opencode v2)

merman can render a flowchart programmatically
(`merman/src/flowchart/render.ts:5`, not in its package exports), caps a
canvas at 250,000 cells and folds layouts wider than 120 columns to
top-down. It has no map from cells back to node ids; layout returns a
`bounds` map that could build one. A ≤12-node view fits easily. A
`session.panel` plugin gets a name, width, focus and fullscreen; the diff
viewer is the model to follow.
