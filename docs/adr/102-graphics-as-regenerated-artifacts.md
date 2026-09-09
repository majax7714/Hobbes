# ADR-102 — The comparative graphics are regenerated artifacts, read from the cell records, never typed

**Date:** 2026-09-09 · **Status:** accepted — built (`bench/oracle/report/render.py`), four graphics committed, the drift check in the oracle lane's Go suite · **Owner:** Max · **Source:** Max's brief of 2026-09-09, Workstream C

Companion to ADR-101. Amends nothing in the architecture; adds a rule
to the oracle lane's evidence discipline (`docs/oracle-grading.md` §11).

## Context

A picture is believed more readily than a table, so a picture that
drifts from its cells is a P8 violation with a picture on it. The
three graphics Max asked for — the one number, the precision × recall
scatter, a before/after on one repo — each print numbers that already
live in `docs/oracle-cells/` and in two `graph.json` artifacts. The
only honest way to keep them true is to make the records the source
and the picture a build product.

## Decision

1. **Every number in a graphic is read, not typed.** `render.py cells`
   parses the verbatim `report.txt` blocks every cell record quotes
   (the last block in a file is the standing grade; a regrade appends)
   and, for the dagger Go record, its per-module "after" table, into
   `docs/comparative/data/cells.json`. `render.py capture` reads two
   `graph.json` artifacts (same repo, same commit, two Hobbes builds)
   into a per-directory capture file computed exactly as `hobbes
   ingest` prints it (accounted = sites − unresolved, depth 2). The
   only hand-written input is `cells.meta.json` — language, where the
   cell ran, how the repo was chosen, a label and a note — and it holds
   no numbers.
2. **`render.py check` fails on drift**, and `bench/oracle/report/
   report_test.go` runs it in the lane's Go suite, so CI goes red when
   a cell is regraded without the graphics being regenerated. The
   committed SVGs are byte-for-byte what the records render to.
3. **Static SVG, stdlib only.** Cytoscape is the surface's; a graphic
   that regenerates from a script with no dependencies is easier to
   keep truthful. Hover text on every dot carries the cell's miss
   classes with counts. No timestamps in the output, so an unchanged
   record renders an unchanged file.
4. **The one number** is *0 falsely confirmed of N seeded wrong edges
   across K compiler-graded cells*, N and K summed from the poison
   lines; the cell count is printed beside it, the cells not in the
   sum are named (graded before the check existed; a record that
   quotes the check per module without summing it), and the
   trace-graded cells' poison is printed on its own line because a
   trace refusal is 'suspect', never a contradiction (C-60). The
   sibling line prints every compiler-graded cell below 100% with its
   fraction; the exceptions are what make the number believable. The
   caption says *precision-against-oracle is a lower bound* in the
   graphic itself.
5. **The scatter** is one dot per cell, x = recall, y =
   precision-against-oracle, **language as the panel, not a colour**:
   the reference palette validates three hues all-pairs and there are
   five languages, and the panel also makes "never compared across
   cells" visible. The y axis starts where the lowest cell sits (never
   above 80) and says so, so 99.6% and 100% are told apart. Trace cells
   sit in a **separate panel** on their own axes (confirmation rate,
   recall-against-executed), never on the compiler-graded footing.
   A foreign cell (ADR-101) is a hollow square in the same panel as
   its language. dagger's nineteen modules are nineteen dots with one
   shared label. Severed-Chains is labelled *no semantic lane: the
   syntactic floor*. Recall is stated as a range, never averaged.
6. **The before/after** is date-fns (TS, pnpm workspace — the shape
   every workspace-aware tool meets), rendered as the per-directory
   capture view (the view that named the fix), naming C-74 and C-90 on
   the graphic. The *before* artifact was regenerated 2026-09-09 by
   the Hobbes commit before the lift (`a60777f^` = 55622713) on the
   same clone at the same commit, contained, and reproduced the
   record's numbers (TS6053 on every zone, capture 0.1% of 24,827);
   the *after* is the clone's standing artifact (80.1%). Both are kept
   under `~/.hobbes/bench/comparative/`. dagger's
   `core/integration` (59.3% → 96.3%, ADR-049) stays in the doc as the
   larger measurement; its pre-join artifact is not on the box, so it
   is quoted from the evidence log, not drawn.

7. **The comparison itself** (added later on 2026-09-09, after the
   foreign cells existed): `same-key.svg` — one row per cell that has
   a foreign graph graded on the same key, three markers on a
   precision axis and three on a recall axis, **one hue per tool** —
   blue dot Hobbes, orange square CodeGraphContext, green diamond
   repowise, the reference palette's first three slots, validated
   all-pairs (CVD ΔE ≥ 9) with the shape as the second encoding and
   every marker filled (the first cut drew both foreign tools as hollow
   orange shapes and did not read at a glance; changed the same day on
   Max's review) — a grey line
   spanning the three, grouped by language with repowise-bench's draws
   as their own band and the trace-graded Python cell labelled by its
   confirmation rate. Two axes rather than one scatter so a row can be
   read on its own; nothing pooled; the caption carries the lower
   bound, the grain (C-94, C-95), the triage sample's ratio and why
   syft is absent. A tool whose cell stored no call edge prints
   *undefined* in the row rather than a marker at 0.

## Consequences

- Regrading a cell is three commands: edit the record, `render.py
  cells`, `render.py render`; the test enforces the last two.
- A new cell needs a line in `cells.meta.json`, or `cells` refuses
  with the file's name — a graphic never silently omits a record.
- The graphics say what the records say and nothing more; a reader
  who wants the basis of any dot has the record's file name in
  `cells.json`.
