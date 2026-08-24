# ADR-072 — The planner's map is ranked by the proposal, not the alphabet

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-059 (the
planner brief), C-47.

## Context

Max asked the real Hobbes question about the sphinx planner: was it
*given* the right place and named `domains/*` anyway? It was not given
it. `repo_context` listed the **first 60 modules alphabetically by
path** and stopped — sphinx has 608 modules, and `sphinx/ext/autodoc`
sorts after the cut. Checked across the five planner briefs of the
ADR-070 run: the gold module was in the brief for **1 of 5** instances
(django's `contrib/admin/filters.py`, by alphabet). Every planner made
exactly one tool call — its `reflect`. So the planner localised from
the issue text plus sixty irrelevant names, and its hits (xarray 2/2,
sympy 1/1, sklearn 1/2, django 1/3) came from the model's prior
knowledge of these repositories (C-39), not from derived context. The
harness's "planner hit rate" was measuring contamination.

## Decision

`repo_context(graph, proposal)` now carries:

- **Modules related to the proposal by name** — every module scored by
  lexical overlap between the proposal's tokens and the module's
  id/path tokens *and its symbol names* (from `graph["symbols"]`, so
  `polylog` reaches `zeta_functions`); each term weighted by rarity
  across modules (`1/(1+ln df)`), a path hit counting double; a
  module's score is its best `MAP_TOP_TERMS` (5) weights in full plus
  `MAP_REST_WEIGHT` (0.25) of the rest, so breadth cannot beat one
  specific name. The top `MAP_RELATED` (80) are listed **with the terms
  that matched**, under a heading that says it is a lexical hint
  (C-36), not a location.
- **The package tree** — every directory holding modules, to depth 3,
  with counts (capped at 400 lines, the cut stated) — so the whole
  repo's shape is present whatever its size (django: 2,674 modules).
- A closing line telling the planner to confirm with `search_file` /
  `read_file` / the knowledge tools before naming.

Measured on the five real graphs: gold ranks django 1/38/44, xarray
7/5, sklearn 71/44, sphinx 2/9, sympy 40 — every gold file in the map
(before: 1 of 5 instances). Map size 9–27k chars, inside the
ADR-069 budget. The three numbers are declared guesses pinned in
`stages.py`; the measurement that chose them is in the constants'
comments.

## Consequences

- The planner hit rate now has a chance of measuring Hobbes. C-47 is
  amended to say what it measured before.
- A lexical map is still C-36: a proposal with no code-shaped words
  lists "none" and leans on the tree; the planner has `search_file`.
- Tests: `TestPlannerMapIsRelevant` (gold first by path and by symbol;
  no-match says so; the alphabetical shape is gone). 859 pytest.
