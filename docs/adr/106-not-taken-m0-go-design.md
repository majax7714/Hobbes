# ADR-106 — Not taken: the number held for Calvin M0-Go's design

**Date:** 2026-09-14 · **Status:** not taken — the number is closed, so the sequence has no hole and it is never reused · **Owner:** Max · **Source:** the handoff's open call "whether ADR-106 stays held", carried since 2026-09-12; Max, 2026-09-14: "writ the not taken note to the adr".

## Context

Calvin M0-Go's design (`docs/calvin/calvin-m0-go.md`, "takes the next
number when moved from handoff to accepted"; `calvin-m0-gate.md` §9,
"ADR-106 is held for M0-Go") was to take this number on Max's
*accepted*. ADR-107 (2026-09-12) closed the keyed rounds — M0, M0-Go,
M0-Gate — as an approach and opened the dispatch harness in their
place, and ADR-107 itself says "ADR-106 stays held for M0-Go's design,
as the handoff has it." Nothing will now move M0-Go's design to
*accepted*, so the hold would have stood forever.

## Decision

The number is **not taken**. This page is the record that stands in
its place: no design is accepted under it, and no later decision may
reuse it. M0-Go's design and its runs are history, recorded where they
were written — `docs/calvin/calvin-m0-go.md` and
`calvin-m0-go-r2.md`, their cells under `docs/calvin/cells/`, the
register entries they made (C-102–C-123, with the ones ADR-043's
2026-09-13 amendment superseded or folded), and the BUILDLOG entries
of 2026-09-10 to 2026-09-12. What the rounds taught carried into
ADR-107 (the harness) and ADR-100's amendments (the local harness).

## Consequences

- ADR numbering stays contiguous: 105, 106 (this page), 107.
- CLAUDE.md's convention line no longer says a number is held.
- The references to "ADR-106 is held" in `calvin-m0-gate.md` and
  ADR-107 stand as they were written; this page is what they now
  resolve to.
