# ADR-126 — Reach through dispatch is measured, not drawn

**Date:** 2026-09-17 · **Status:** accepted (no expansion edge; the measurement) · **Owner:** Max · **Source:** Max, 2026-09-17 ("go with your order, write up first"), the route recommended that day for ADR-120 §7 — honesty and accuracy first on the extraction lane.

Answers ADR-120 §7's open question in part; ADR-007 (reach follows
`calls`) stands. Pre-registered in `oracle-grading.md` §10.12.

## Context

ADR-120 drew the override set as `implements` edges and left open
expanding a call to an interface or virtual method into its overrides.
The expansion is a recall lever. It is also an inference: a call to
`Store.Get` does not prove that `MemStore.Get` runs, and every edge in
the graph today is one a tool proved. Leaving it alone has an honesty
cost of its own: `tests_guarding` reads an override "unguarded" when a
test reaches it only through the interface, and that silence reads as a
fact.

What the keys can say about it (read 2026-09-17, file:line in the
BUILDLOG entry):

| language | the key at a dispatch site | Hobbes' base edge | measurable |
|---|---|---|---|
| Java (javac) | declared method + **CHA** override set | yes | the override *set*, not dispatch |
| Python (trace) | callees a run took | yes | observed pairs, coverage-limited |
| Go (RTA) | concrete callees | **no** (the method spec is below the floor, C-58) | not without a floor change |
| C++ (clang) | declared method only | yes | no — every override pair is unjudged by construction |
| TS (tsc) | declared (overload set) | classes yes | no |
| Rust (MIR) | declared, empty targets | partly | no — no override set (C-157) |

A CHA key confirms an expanded pair by the same approximation the
expansion makes. It can say whether Hobbes' override set is the
compiler's; it cannot say that a call reaches an override.

## Decision

**1. No expansion edge is drawn.** Not as `calls`, not under an
"inferred" tier. A labelled second kind of edge in the same graph is
still a guess in a graph whose promise is that edges are proven, and
every consumer that counts edges would have to learn to skip it.

**2. Measure the two things the keys can answer, and name what they
cannot:**
- **The override set's accuracy (Java, jsoup):** for each `calls` edge
  whose target has overrides, the pairs (site → each override, through
  `implements` transitively), graded against the standing jsoup key's
  CHA set: set precision and set recall. jsoup is re-ingested at the
  current version (no stored graph has `implements`; the export carries
  only `calls`, so the measurement reads `graph.json`).
- **How often an expanded pair is taken (Python, click's trace):** the
  observed share, coverage-limited; an unobserved pair is never a
  contradiction.
- **Control (C++, args, stored):** the pairs counted and reported as
  unjudged by construction, never graded as contradicted.
- Go, TS and Rust: recorded as not measurable, with the reason.

**3. What the measurement decides, and what it does not.** It decides
the wording and whether a surface is worth building: a query-time
section in `tests_guarding` and `hobbes review`, "may reach through
dispatch (not traced)", computed from `calls` + `implements` when asked,
never counted as reach, never exported, never graded, carrying the
measured set precision and the languages it does not cover. Building
that section is Max's call on the measured numbers, in an amendment
here.

## Measured 2026-09-17 (§10.12)

- **The override set is the compiler's.** On jsoup, 2,837 of the 2,944
  expanded pairs are in javac's CHA set. Recall of that set is 97.4%, and
  the one pair outside it is a bridge-method override the key's
  erased-parameter rule misses.
- **A naive expansion is wrong on 3.6% of pairs.** All 106 unjudged pairs
  sit where javac resolved the call statically (`super.clone()` at
  `CDataNode.java:37`, private and final methods). No dispatch happens
  there, and one listed override is the caller itself.
- **click:** 27.5% of its 360 pairs ran under the suite (coverage-limited).
- **args:** 353 pairs, unjudged by construction.
- **Median fan-out is 1 on jsoup** (maximum 41), not the ≥ 2 predicted.

**What a surface would have to do,** if Max decides to build §3's
section:
- exclude, by syntax, every call the language does not dispatch: Java
  `super.`, private, static and final methods, Python `super()`, and a
  C++ call qualified with a class name;
- print the measured set agreement and the excluded share;
- say that no key confirms reach.

Until that decision, nothing is built.

## Consequences

- The graph and every grade are unchanged by this ADR.
- If the override set's precision on jsoup is poor, that is a finding
  against ADR-120's `implements` edges themselves, fixed before any
  surface is built on them.

## Alternatives considered

- **Expand into `calls`.** Rejected: it breaks "a tool proved it".
- **An `inferred` tier.** Rejected above.
- **Do nothing.** Rejected: the false "unguarded" stays.
- **Go's method specs as lane A symbols first** (ADR-120's deferred
  item). Not rejected; not part of this. It moves Go's cells and is its
  own decision.
