# ADR-125 — C-153: measure a rule that recognises scip-clang's wrong specialisation, then abstain where it holds and surface the rest

**Date:** 2026-09-17 · **Status:** accepted (the measurement and its decision rule; the build follows the grade) · **Owner:** Max · **Source:** Max, 2026-09-17 ("go with your order, write up first"), the route recommended that day for "C-153 is unsurfaced; accept it as documented-only?" — honesty and accuracy first on the extraction lane.

Pre-registered in `oracle-grading.md` §10.11 before anything is measured.

## Context

C-153: scip-clang indexes a template's pattern once, and where it gives
a single reference at a call in a template the graph takes it. On fmt
that answer is wrong at 10 of the 3,395 judged semantic edges, in three
shapes (the entry): a specialisation's own member drawn where the source
calls another specialisation's (4), an explicit specialisation's member
drawn for the one the call names (4, `test_format<0>::format`), and one
overload of two (2). Since H-30 only 4 of the 10 are judged.

The entry is **unsurfaced**: nothing at the site says so. Documented-only
is not acceptable for a wrong edge (P8; "a flagged gap is a defect"), and
a wrong edge is worse than an absent one because it is believed. But
abstaining on every call in a template would remove thousands of right
edges to remove ten wrong ones, which is not accuracy either; it is
silence presented as caution.

## Decision

**1. The candidate rule is one the source text can check.** *R-qual*: a
C++ semantic `calls` edge whose callee is written with a qualifier
carrying template arguments (`formatter<int>::format(..)`,
`test_format<40>::format(..)`), where the resolved declaration's owner
carries **different** template arguments (or none, for a specialisation
the text names). The source and the index then disagree about which
class is meant, so lane B's one answer is contradicted by the program
text itself. The comparison is textual after whitespace normalisation;
where the owner's arguments cannot be read (an alias, a dependent
`typename`), the rule does not fire.

Measured beside it, so the choice is visible: *R-self*, a C++ semantic
edge whose target is its own caller (the shape of the four self rows,
without the text check).

**2. The measurement** (no spend, from the stored artifacts where they
suffice): fmt and args, the standing exports graded against the standing
keys, every edge each rule matches listed with its bucket, and every
matched edge that is not `contradicted` or `line-unresolved` read by hand
against the source.

**3. The decision rule, fixed now.** R-qual becomes a lane A/join
abstention — the edge not drawn, the site counted in a tail class
`qualifier-mismatch` (so the recall cost is a number, not a silence),
C-153 narrowed — **only if, on each cell, the edges it removes that the
key confirms are no more than the wrong edges it removes.** Otherwise it
is not built, and step 4 alone applies. R-self is not built whatever it
measures unless it passes the same rule *and* its matched confirmed rows
are read to be genuine recursion no text could tell apart.

**4. The rest is surfaced either way.** A C++ semantic edge whose site
lies inside a class or function template body carries the C-153 note in
`who_calls` ("a call in a template pattern: scip-clang's one answer may
name another specialisation's declaration"), and the ingest writes one
`cpp-template-sites` degradation record with the count, so
`list_blind_spots` names it. C-153 moves to **partial**: the note marks
the region where the error can occur, not the edges that are wrong.

**5. Version.** The abstention (if built) and the surfacing are each a
patch.

## Consequences

- fmt's standing precision can only rise if R-qual is built, and its
  recall falls by the confirmed edges the rule removes; both are
  printed with signed direction lines, and the strict companion
  (ADR-124) with them.
- If R-qual fails the rule, the cell and C-153 say so, and the
  surfacing is the whole response.

## Alternatives considered

- **Accept as documented-only.** Rejected: an unsurfaced wrong edge.
- **Abstain on every call in a template pattern.** Rejected: most such
  edges are right; the cost would be unmeasured caution.
- **Abstain by R-self alone.** Rejected unless measured safe: a
  specialisation's method can genuinely call itself.
