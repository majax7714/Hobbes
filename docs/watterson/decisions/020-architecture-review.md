# 020: An architecture review beside the code map, from the graph alone

- Status: accepted; slices 1 and 2 built (see notes)
- Date: 2026-10-17
- Builds on: DEC-018 (the review page), DEC-019 (its renderer); open-work
  item 4. Pauses DEC-019's slice 2.

## Context
The review page (DEC-018/019) shows the repo folder by folder. The user
(2026-10-17): it "still takes deciphering to tell what each folder holds and
what each connection is to"; they want "architectural levels instead of by
folder", the easy-to-take-in picture understand-anything gives and
hobbes-public's pipeline diagrams draw, transformed from the knowledge
graph. The folder view stays: it is good for entry points and tests.
Survey: `research/architecture-review.md`.

## Decision
The user chose (2026-10-17) a tab in the same page, system and component
views first, from the graph alone:
1. **Two tabs, one file.** The review page gets an **Architecture** tab
   (shown first) beside the **Code map** (the DEC-018 views). Same stamp,
   file name and launch. Built by a new glue module, `hobbes.architecture`,
   from the same inputs as `hobbes.levels`.
2. **System view:** the repo's top-level parts (as the code map's repo
   view groups them), their entry points above them (commands, routes), and
   the outside systems they reach below them (processes, network, storage,
   files, environment, infrastructure), classed by a fixed table of
   external names.
3. **Component view**, one per part and per component big enough to split:
   - components are folders, splitting the biggest until at most
     `MAX_COMPONENTS` boxes (about 9; folders are the strong baseline);
   - widely used modules with few dependencies of their own (fan-in in
     the top 5%, fan-out at most 2, used from 3 or more components) are
     pulled into one **shared** box;
   - layered by ELK (users above what they use); components in a cycle
     are drawn inside one frame;
   - each card: a role tag, a one-line summary, size, tests, the outside
     systems it touches; arrows keep direction, kind and count;
   - each component links to its folder's code-map view.
4. **Roles by fixed rules**, each explained in the page's key: `entry`
   (holds an entry point's target), `adapter` (a third or more of its
   modules import process, network or storage libraries), `foundation`
   (2 or more components use it; Martin's instability, uses over uses plus
   users, at most 1/3), `coordinator` (it uses 2 or more; instability at
   least 2/3), `standalone` (no links either way).
5. **Summaries from the code's own words:** the folder's `__init__.py`
   docstring, else its README's first paragraph, else a Go package comment,
   else the docstring of its only module. Read from the working tree at
   review time (the graph drops them); the page says so when HEAD has moved
   past the graph's commit. No summary is better than a guessed one.
6. **Graph only.** No LLM, no overrides file yet. What the graph cannot
   say (files passed between stages, links between languages, a
   subprocess's command) is stated on the page, not guessed. The map file
   (DEC-014 decision 5) and file-I/O facts in hobbes-public stay the ways
   to fill it later.
7. **Slices:** (1) the system and component views; (2) a pipeline view per
   command: the components its flow reaches, in call order. Later, not
   decided: an overrides file, optional LLM naming.

## Consequences
- The page holds a second, small document (`architecture`) beside the
  level views; the bundle gains a tab, card fields and frames, not a new
  library.
- Summaries depend on the repo's docstrings: a repo without them gets
  cards without summaries.
- Roles and thresholds are heuristics; their rules are on the page so a
  reader can judge them. Thresholds may move after looking at more repos.
- DEC-019 slice 2 (folders opening in place, portal nodes) waits; its
  container drawing is first used here for cycles.

### Note, 2026-10-17: slice 1 built
- `hobbes.architecture` builds the document; `levels.build` adds it as
  `architecture` (level schema 5), so `hobbes review`, `/review` and
  `hobbes levels --format json` carry it. The page (`review/src/`) has the
  two tabs (`#a=` and `#v=` in the hash), architecture cards (role chips,
  summary, size, tests, what they reach) and an architecture side panel;
  the code map links to a folder's architecture view and back.
- **Changed while building**, after looking at hobbes-public:
  - **Cycles are links against the layers, not frames.** In `pipeline`, 8
    of 11 components sat in one cycle, so a frame would have held nearly
    everything. A weighted greedy feedback arc set (Eades, Lin and Smyth)
    picks the light links that close cycles; layers are computed without
    them, ELK keeps that order (cycle breaking by model order), and they
    are drawn dashed red and listed. hobbes-public's `pipeline` reads
    top to bottom: CLI files and scripts; bench, ttt; run; derive;
    narrate; extract, agent, invariants; six links (1 to 10 references
    each) run against the layers.
  - **`adapter` needs half of a box's modules, not a third**: at a third,
    7 of 11 components qualified, mostly by one module running `git`.
  - **Outside links stay out of the layout** and show when a part is
    focused; with them, every part sat in one wide layer. Outside systems
    are placed in a row below.
  - A folder's own files are one box; with fewer than 4 boxes they break
    into filename groups (3 or more, e.g. `*source`), the most-linked
    modules, and "+N more". Files and "+N more" boxes open a view of their
    files. Roles are explained in the page's key, not in each view's notes.
- Size: the bundle is 1.86 MB; the hobbes-public page 6.3 MB (12
  architecture views). The architecture document takes about 0.1 s more
  in `levels.build` there.
- Checked in headless Firefox (light and dark) on hobbes-public at
  `2089e22`: the system view, `pipeline`, `extract`, `go`, a "+N more"
  view, selection and focus. Not checked: keys in the new tab, a real
  browser, other repos.

### Note, 2026-10-17: slice 2 built
- `_Pipelines` in `hobbes.architecture`. A part's entry-points box opens
  a list of its commands and routes (`arch:runs:<part>`); each opens its
  pipeline (`arch:run:<symbol>`): the components of the part's component
  view, numbered in the order a depth-first walk of calls, in call-site
  order, first enters them, with each step's entering call, the functions
  reached there, and the calls between steps (a call back to an earlier
  step dashed red).
- **Dispatch by reference** (added in this slice): the graph records a
  function named without being called (a handler table, `set_defaults(
  func=...)`) as a semantic `uses` edge with its line. A function with 3
  or more such references to plain functions is a dispatcher: its
  handlers get a list (`arch:dispatch:<symbol>`) and pipelines of their
  own; fewer references are followed like calls and counted as `refs`.
  hobbes-public's `hobbes` CLI, whose flow stopped after 3 functions at
  its dispatch (extraction gap 3), now opens 21 handler pipelines
  (`_cmd_ingest`, `_cmd_review`, …); `atlas0`'s CLI is found the same way.
  The code map's flows do not follow references yet.
- **Drill-down:** a step with a component view of its own opens the same
  walk inside it, down to two levels below the entry's own; there, the
  modules the flow reaches most in a "+N more" box are shown as they fit.
  `_cmd_ingest` inside `extract`: `__init__.py`, `containment.py`, shared,
  `graph.py`, the `*source` parsers, `evidence.py`, `packs/`, ….
- hobbes-public: 112 pipeline views; its page is 10.8 MB. Routes whose
  handler is not recorded (gap 4) stay cut, listed with the reason.
- Checked in headless Firefox: an entry-points list, `hobbes-proxy`, the
  `hobbes` dispatcher and its handlers, `_cmd_bench`, `_cmd_ingest` inside
  `extract` with a step selected. Drill-down views of 12 steps are busy.
  Not checked: a real browser, other repos.
