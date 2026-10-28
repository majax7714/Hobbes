# An architecture review from the Hobbes graph

Survey for DEC-020: what an "architecture review" could show beside the
folder-by-folder review page (DEC-018/019), using only Hobbes's graph.
Four subagent surveys on 2026-10-17 plus a throwaway prototype; the
claims about our extractor and about understand-anything were spot-checked
against the code (paths below).

## 1. What the user asked for

The folder views are "better than blank code but it still takes
deciphering to tell what each folder holds and what each connection is
to". Wanted: the easy-to-take-in architectural picture understand-anything
gives, in the spirit of hobbes-public's pipeline diagrams, derived from the
knowledge graph; the folder review stays as the base (good for entry
points and tests).

## 2. hobbes-public's diagrams (at `2089e22`)

Seven hand-written Mermaid blocks and three ASCII diagrams, e.g. the
extraction pipeline (`README.md:109`), the system overview (`README.md:61`),
the layered component view (`docs/hobbes-architecture.md:286`).

- A box is a **role**, often a CLI verb plus mechanism ("hobbes ingest ·
  tree-sitter + SCIP → one join"), never a file name. Subgraphs are layers
  or boundaries titled by a property ("in the sandbox image, no network").
- **Artifacts are nodes between stages** (`graph.json · schema v4` as a
  cylinder); arrows run producer → consumer, the way data moves. The code
  graph's arrows run caller → callee, so they are not these arrows.
- About half of each diagram is derivable from code: stages (entry points,
  packages), outside tools, grouping. The rest is either not in the graph
  (files read and written, commands run) or human wording (conditions,
  constraints, trust boundaries).
- The one generated diagram, `hobbes render` (ADR-008), is a module
  dependency map labelled by ids, not a pipeline view.

## 3. understand-anything's architecture side (at `f2d0164`)

Paths under `understand-anything-plugin/`.

- The overview is 3–10 **layers**, one card each (name, one-sentence
  description, file count, complexity badge); an LLM assigns every file
  to a layer (`agents/architecture-analyzer.md:14`). Cross-layer edges are
  a raw count of all file-level edges, undirected and of every kind mixed
  (`dashboard/src/utils/edgeAggregation.ts:21-67`).
- What structures the picture is deterministic or nearly so: directory
  groups, a folder-name → role table (`architecture-analyzer.md:107-166`:
  `api`, `services`, `models`, `utils`…), fan-in/fan-out, Louvain when
  folders are degenerate (`utils/containers.ts:79-150`), entry-point
  scoring for the tour (`agents/tour-builder.md:62-77`). An unused
  heuristic layer detector exists (`core/src/analyzer/layer-detector.ts`).
- The LLM writes the prose: summaries, layer names and descriptions, the
  tour's narrative, and the whole business-domain view.

## 4. Published methods

From Garcia et al. (ASE 2013), Lutellier et al. (TSE 2018, read in full)
and Le et al. (MSR 2015, read in full), plus the clustering and layering
literature:

- **Folders are a strong baseline.** On two of Lutellier's systems the
  directory structure beat every clustering algorithm; of the algorithms,
  only ACDC was consistently at least as good as K-means. Bunch, WCA,
  LIMBO and ARC are slow, vary between runs or fall below the baseline.
  Module granularity runs in seconds.
- **Pull out omnipresent modules** (high fan-in, low fan-out) before
  grouping, and show them as one shared box; hubs are what glues groups
  into one blob.
- **Layers:** cycle condensation (Tarjan) then longest-path levels
  (Lakos; Structure101 and Lattix's levelization). Layer the *component*
  graph, not the module graph; one big cycle flattens everything, so show
  cycles as such.
- **Roles from structure:** entry (main, CLI, route), adapter (imports
  network, database or process libraries), foundation (many depend on it),
  coordinator (depends on many); Martin's instability `Ce/(Ca+Ce)`.
- **Readability:** 5–9 boxes per view with drill-down; keep a group's
  identity stable across commits by anchoring it to its folder.
- Pipeline views in other tools come from declared DAGs (DVC, Kedro) or an
  LLM (CodeBoarding); deriving "stage → artifact → stage" needs file I/O
  facts.

## 5. What the Hobbes graph offers

Checked against `pipeline/src/hobbes/extract/` and hobbes-public's
derived files.

- Usable: module imports and symbol calls/uses with `path:line` evidence;
  external nodes `ext:<name>` (Python's top-level package, Go's import
  path, TS's specifier); env nodes; CLI entry points and routes
  (`interfaces.json`); tests and what they reach.
- **Module docstrings are parsed but not emitted**
  (`pysource.py:687-689`, `ParsedFile.docstring`); the review can read
  them from source (`ast.get_docstring`, well under a second for 600
  files). The working tree may have moved past the graph's commit.
- Not in the graph: files read or written, which commands a subprocess
  runs, URLs, types passed between stages, stdlib vs third-party (gap 6),
  links between languages (gap 2). So hobbes-public's Python pipeline and
  its Go services look unconnected: what joins them is `graph.json`.

## 6. The prototype

A throwaway script over hobbes-public's graph (folders split until about
nine components, hubs pulled out, Lakos levels on the component graph,
externals classed by a small table, docstrings from source; 0.5 s):

- `pipeline/src/hobbes` came out as ten components (`extract` 43 modules,
  `derive`, `run`, `bench`, `ttt`, `narrate`, `invariants`, the CLI files,
  a shared box, a leftover) with what each touches (processes, network,
  files) and weighted directed links (derive → extract, 38).
- Five of them depend on each other in one cycle, which collapses the
  layers: cycles need to be drawn as a group.
- The most-used module's docstring is a poor summary of a folder
  (`extract` got "Repo discovery…"); the folder's own `__init__.py`
  docstring or README is better.
- At the repo level the parts (pipeline, Go services, web UI, bench) have
  no recorded links between them (gap 2).
