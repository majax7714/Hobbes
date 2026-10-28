# 014: Graph views are tiered levels, grouped by folder, computed by `hobbes levels`

- Status: accepted; levels 0-4 built (see notes)
- Date: 2026-10-16
- Narrows: open-work item 4 (graph abstraction for devs); DEC-011's graph
  view
- Research: `docs/research/level-model.md`, `docs/research/extraction-gaps.md`

## Context
One diagram of a whole repo is useless past a few dozen modules (hobbes-public
has 631). The user wants tiers instead: a chart of the few big pieces and
how they connect, where selecting a piece opens its own chart, down to the
code, with a fitting diagram at each level. Mermaid was only the user's
habit, not a requirement. Folders are the default grouping (the user,
2026-10-16).

The survey found folders work inside one language root but not across
roots: extraction records no links between languages, so a multi-language
repo's top level is unconnected boxes. It also found test fixtures
ingested as code, flat folders that folders cannot split, and gaps that
cut flows short (listed in `extraction-gaps.md`, kept in this repo for now).

## Decision
1. **A level model**, computed deterministically from `graph.json` (plus
   `tests.json` and `interfaces.json` when present) by `hobbes levels`.
   It is glue in this repo: it only reads Hobbes's outputs, and can move to
   hobbes-public later. It is a document of **views**, one per folder that
   has a chart, each with at most about 12 boxes and the rolled-up edges
   between them; selecting a box opens the view of its folder.
2. **Levels:**
   - **0, system:** the language roots (folders with their own manifest),
     plus what comes in (CLI entry points, routes) and what goes out
     (externals, environment variables, infrastructure). With one root, its
     top groups are shown directly.
   - **1-2, groups and components:** the folders inside a root, then inside
     a group, down to modules.
   - **3, module** (symbols and calls, tests guarding) and **4, flow**
     (calls from an entry point, as a sequence) come in later slices.
3. **Folders by default, with these rules:** group by `path`; drop test
   fixtures (`fixtures/`, `testdata/`) and their entry points; collapse a
   folder that only wraps one folder; keep test modules out of the boxes and
   count each test on the box it reaches most; split a folder with too many
   entries by filename prefix, then fold the rest into "+N more". No
   clustering library for now.
4. **Edges** keep separate counts (imports, calls, uses) and a few sample
   `path:line`s. Cycles are detected per view and their edges marked; layers
   follow dependency direction. Edges leaving a view become stubs named by
   the sibling folder they reach.
5. **Links between language roots** (the user, 2026-10-16): shown as
   unconnected boxes with a note saying why for now; a map file will let
   the user declare them, marked "declared", not "extracted"; extracting
   them is hobbes-public's job (gap 2).
6. **Outputs:** the JSON document, a text outline, and a Mermaid flowchart
   per view (merman can draw small views in the TUI). The TUI graph panel,
   D2 and C4 exports come later.

## Consequences
- The TUI graph view becomes "show view X, open box Y", not one diagram.
- Group ids are folder paths, so they stay stable across commits until a
  folder moves.
- A repo with flat folders gets prefix groups, which can be crude; a map
  file (open) or clustering would improve them.
- Flows (level 4) wait on the extraction gaps 3-5 or show where they break.

### Note, 2026-10-16: first slice built
- `hobbes.levels` and `hobbes levels [--repo DIR] [--view ID]
  [--format text|mermaid|json] [--list]`. Views are computed on demand
  from `.hobbes/derived/`; nothing new is stored.
- Two changes from the plan above, found on hobbes-public's ingest:
  - **The views follow the folder tree from the repo, and language roots
    are marked on their folder boxes**, rather than being a layer of their
    own: manifests sit at several depths (the repo root, `pipeline/`, `go/`,
    each `bench/*` project). Collapsing a wrapper folder stops at a root, so
    a root keeps its box.
  - **Flat folders group by the filename start or ending most files
    share** (`*source` for the 8 per-language extractors), not only by
    underscore prefix: `extract/`'s names share endings. Greedy, at least 4
    characters, ties broken by length then name.
- On hobbes-public at `2089e22` (lane A): 85 views in about 0.2 s, never
  more than 12 boxes; 169 fixture and 201 test modules kept out; the
  `bench` ↔ `derive` ↔ `run` cycle found; `cli.py` at the top level of
  `pipeline/src/hobbes`.
- Limits: affix groups can be crude (`*ases`), and what they leave folds
  into "+N more" (16 modules in `extract/`); grouping by coupling would do
  better. Externals mix the standard library and third parties
  (extraction gap 6). No map file yet. Module (3) and flow (4) views and
  the TUI panel come next.

### Note, 2026-10-16: module views (level 3)
- A module box with symbols opens its **module view**, id = the module's
  path (stable like folder ids; document `schema` 2). Its boxes are the
  module's top-level symbols: a class with its methods, a function with its
  nested ones, each with its kind, line span and member count.
- More than 12 boxes: grouped by name affix, as files are, but cut only at
  word boundaries (`_` and camelCase: `_collect_*`, `*_chain`), then the
  smallest folded into "+N more"; each group opens its own view.
- Edges are calls and uses between the boxes, with cycles and levels as in
  folder views. Stubs are the other modules the symbols call or are called
  from, plus the module's own imports (named by path); inside a group's
  view, symbols of the same module outside it are stubs too.
- **Tests guarding** a box: tests that reach one of its symbols from a test
  file that imports the module or sits in its folder (Go's same-package
  tests). `tests.json`'s `reaches` is transitive, so every test that
  reaches it is kept apart as `reached_by`; on hobbes-public most of the
  suite reaches most of `extract/`. Limit: with no record of which symbol
  a test calls directly, an extractor module's helpers all show the same
  guarding count (628 on `pysource.py`'s groups).
- On hobbes-public at `2089e22`: 805 views (87 folder, 718 module and
  symbol-group) in 0.66 s, none over 12 boxes; the JSON grows from about
  340 KB to 4.5 MB, mostly member lists. The TUI panel (DEC-015) shows
  module views with no plugin change beyond the "module" tag and a
  box's "tested by" samples; checked live.

### Note, 2026-10-16: flow views (level 4)
- The user chose (2026-10-16): flows as drill-down steps, not one bounded
  sequence; resolve entry targets the graph does not link, tagged so;
  argparse dispatch only noted, never guessed; entry points only as
  starts (a flow from any function would be built on demand, later).
- An **"entry points" box** on the repo view (which keeps room for it
  within 12) opens view `flow:`: the CLI entry points and routes outside
  fixtures, split by kind past 12, then "+N more". An entry opens
  `flow:<symbol id>`: **the calls that function makes, ordered by first
  call site** in its file, at most 12, the rest in `flow:<id>@N` views.
  A step shows its call line and sites, its module when another, and its
  guarding tests; it opens the callee's flow, or is marked "ends: no calls
  recorded" or "leaves: test or fixture code". Edges link steps that call
  each other. One flow view per function, its parent the view it was
  first reached from (breadth first), so going up may not retrace a path.
- **Cuts and resolutions:** a file target (gap 5) takes the file's only
  `main()`, tagged "main() of the file"; a handler id that is no symbol
  (gap 4) takes the one symbol with its name in the registering file's
  folder, tagged "matched by name"; empty, missing or shared names are
  cut. A Python CLI whose module imports `argparse` notes that the flow
  may stop early (gap 3). The flows view notes that an end may be dispatch
  the graph does not record (gap 8).
- **Outputs:** text lists steps in order; Mermaid is a `sequenceDiagram`
  with modules as participants, each step followed by the first 3 calls of
  its own flow. The panel lists flows with no new layout: numbered steps
  in call order and the view's notes; its header now shows the view kind.
  Document `schema` 3.
- On hobbes-public at `2089e22` (lane A): 31 entry points (9 CLI, 22
  routes); all 6 Go and Rust CLIs resolve by file; 16 routes match by
  name and 6 are cut (empty handlers); `hobbes.cli:main` has 1 step,
  `build_parser` (gap 3); lattice's `main` has 32. 1,122 views (392 of
  them flows and entry lists) in 0.64 s; the JSON grows from 4.5 to 5.4 MB.
- Limits: call order is first call site, not control flow (branches and
  loops look alike); with modules as participants, nested self-calls read
  flat in the diagram. The panel change is not checked live yet.
