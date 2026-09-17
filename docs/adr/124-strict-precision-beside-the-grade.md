# ADR-124 — A strict precision beside every grade: the rows the key declined to judge, counted against the tool

**Date:** 2026-09-17 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-17 ("go with your order, write up first"), the route recommended that day for the open call "whether the lane should print a judged-as-before companion number on any cell where `line-unresolved > 0`", honesty first.

Amends ADR-089 (the oracle lane's report) and ADR-102 (the rendered
comparison). `bench/` and docs only: no version move (ADR-103).

## Context

H-30's rule (D-O4, 2026-09-16) puts an edge in `silent / line-unresolved`
when one of the key's sites on its line carries no targets: judging it
against the other sites' targets read the key's silence as a verdict.
The rule is right about the key and indiscriminate about the edge. On
fmt it silenced 6 of C-153's 10 rows, where Hobbes' edge is genuinely
wrong, and it raised every competitor cell it touched.

The record answers with "like-for-like": the rows the *previous* grade
judged. That number exists only relative to an earlier grade, so a new
cell, a new tool or a reader with only the report cannot recompute it,
and the public docs quote it as if they could.

Measured before writing this, from the printed reports alone: 14 stored
records carry `line-unresolved > 0` (fmt 13; repowise fmt 319;
CodeGraphContext zod 771, fmt 90, fzf 61; the rest ≤ 33). fmt's rows are
not all wrong edges: several are gmock and `scan.h` edges the key simply
could not speak to.

## Decision

**1. The grader computes `precision_strict`** = confirmed / (confirmed +
contradicted + `line-unresolved`), in the report JSON beside
`precision_against_oracle`, for every resolution/reachability cell and
every tool alike. Printed on its own line under the standing one
whenever the two differ:
`precision-strict 99.5% (3269/3286): the 13 line-unresolved rows counted as contradicted — a lower bound under the lower bound (ADR-124)`.
Trace cells print neither (C-60).

**2. The standing grade keeps its place; the strict number never leaves
its side.** Neither is the truth: the standing number trusts H-30's
silence, the strict one counts edges the key could not judge as wrong.
Wherever a precision is quoted — cell records, `tables.md`, `cells.json`,
the graphics' hover titles and captions, README, the comparative claim
page, `field.md` — and the two differ, both appear, standing first.

**3. The renderer computes it from what every record already prints**
(the silent map on the `hobbes edges` line), so no cell is regraded and
the drift test holds the docs to it.

**4. "Like-for-like" retires from the public docs.** It stays in the
records where it was written, with its date; it is not quoted again.
fmt reads **99.88% (strict 99.48%)**.

## Consequences

- fmt's public figure gets a lower companion than the one it replaces
  (99.69% → 99.48%), because strict also counts the rows that are
  H-30's legitimate silences. That is the point of a lower bound.
- The competitor rows get the same companion, so the comparison stays on
  one basis.
- C-153's entry and the claim page quote the strict figure.

## Alternatives considered

- **Print "judged-as-before"** (the handoff's wording). Rejected: not
  recomputable from one report.
- **Revert H-30.** Rejected: the rows it silences on mixed lines include
  real oracle silence (H-30 was a defect of the key's reading).
- **Lead with the strict number.** Rejected for now: it is a statement
  about the key's reach as much as about the graph, and ADR-089's
  headline is the judged one; Max can reverse this in one line.
