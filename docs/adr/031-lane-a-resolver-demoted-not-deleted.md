# ADR 031: Lane A's resolver is demoted to fallback, not deleted

Date: 2026-08-15
Status: accepted

Milestone V2.M3. Amends architecture v2 §3.1 and §7's V2.M3 line. Registers
constraint **C-8**.

## Context

Both source documents say lane A stops resolving symbols at M3. The build
plan is specific about the code: delete `_resolve_call`, `_SymbolTable`,
and the symbol-edge production from `extract/graph.py` — ADR-007 rules 1–4,
roughly 110 of that file's 256 lines — and the matching symbol layer from
`tssource.py`.

ADR-029 had already narrowed what that means. Lane A keeps call-site
*detection*, because SCIP cannot answer "is this a call", and loses call
*resolution*. What survived unexamined is the second row of ADR-029's join
table:

| tree-sitter saw | SCIP resolved | result | tier |
|---|---|---|---|
| a call | no | `calls` edge, **lane A's own resolution or dropped** | `syntactic` |

"Or dropped" was written as an open choice. Deleting the resolver is what
picks *dropped*, and reading the code before writing any showed what that
costs.

**On this repo, the fallback arm is 131 edges** — calls SCIP could not
resolve, lane A could, and which today appear correctly labelled as
guesses rather than vanishing (1,202 semantic / 131 syntactic / 392 `uses`
at `1ff397c`).

**The larger cost is the floor.** `_run_lane_b` returns `None` when the
indexer is absent, when it crashes, when `HOBBES_SCIP=0`, and for every
language lane B has not reached. In all those cases lane A's edges are
currently the entire call graph. Delete the resolver and *no indexer means
no call graph at all*: `who_calls` empty, `tests_guarding` empty,
`hobbes review`'s unguarded-new-code verdict blind — on any box without
`scip/` installed, and on every language v2 has yet to wire.

Two smaller consequences point the same way. The pytest suite runs
`HOBBES_SCIP=0` by default (an autouse fixture, added at M2 when lane B
took the suite from 3.5s to 48s), so every lane-A call-graph test would be
asserting against an empty list. And P6 — "when a semantic indexer fails,
the graph still exists at syntactic confidence and says so" — is not
satisfiable for the symbol layer if the only thing that could produce a
syntactic symbol edge has been removed.

## Decision

**Lane A's resolvers stop being edge producers. They do not stop existing.**

- `extract/graph.py` no longer emits `symbol_edges`. `_resolve_call` and
  `_SymbolTable` survive, and their sole consumer becomes the fallback
  table the range join already consults (`_lane_a_fallback`).
- `tssource.py` is symmetric: ts-morph's checker-resolved call targets stop
  being edges and become fallback input, alongside the call sites the TS
  syntax provider now emits.
- The join stays the only thing that produces a symbol edge, for every
  language, and remains the only place that decides a tier.

So the architecture's intent holds exactly: **there is one resolver of
record, and it is lane B.** What is retained is not a second opinion
competing with it — the join never consults the fallback for a site SCIP
resolved. It is a *labelled floor* beneath it, consulted only where the
semantic provider returned nothing, and stamped `syntactic` when it is.

This is the honest reading of §3.1 rather than its literal one, in the same
way ADR-029 was. §3.1 and §7's V2.M3 line are patched in this commit.

## What it concedes, and where that is written down

Registered as **C-8** in `docs/constraints/README.md` (P8, ADR-030): *with no
working indexer, the entire symbol layer is approximate.* That was already
true before this ADR — it is the floor P6 promises — but demotion is what
makes it a permanent, designed property rather than a transitional state
that M3 was expected to remove. A property nobody wrote down is exactly the
fake-honest case P8 exists to prevent.

Surfacing is already built and this ADR adds none: `tier: syntactic` on
every fallback edge, drawn thinner, dimmer and dashed in the graph
(ADR-023 styling, M2), plus `extraction_errors` and an ingest WARNING when
a lane degrades. C-7 covers the related admission that these edges can be
wrong — the M2 measurement found a real false positive, a local variable
named `write` bound to a module-level function.

## Alternatives considered

- **Delete outright, as the build plan says.** Purest reading, and it
  trades a working degradation path for an architectural tidiness that no
  consumer benefits from. It also makes the test suite's default mode
  produce a call-graph-free artifact, which would have been discovered as
  a wave of failing assertions rather than as a decision.
- **Delete, and make lane B mandatory.** Coherent, and it would mean
  Hobbes cannot ingest a repo whose language has no indexer — surrendering
  P6 and P7's whole promise that a new language degrades gracefully rather
  than failing.
- **Keep lane A's edges as first-class alongside lane B's.** What M2's
  first cut did, superseded by ADR-029: two disagreeing answers to one
  question with no way to prefer one. Demotion is precisely the fix —
  there is a preference order, and it is total.

## Consequences

- M3's deletion shrinks again, and for the second time the reason is that
  lane A knows something lane B does not. ADR-029 found it for *callness*;
  this ADR finds it for *availability*.
- The lane-agreement report (§3.4, this milestone) gets its input for free:
  the fallback table is lane A's resolution for a site, so comparing it
  against SCIP's on sites where *both* resolved is a dictionary lookup, not
  a second extraction pass. Today the fallback is consulted only on a miss;
  the report consults it always.
- `graph.py` keeps `_Index`, `_NameEnv`, and module-level import
  resolution, unchanged and still first-class — §3.1 keeps approximate
  module edges in lane A on purpose, and they are what the agreement report
  compares.
- The pytest suite continues to exercise the resolver in its default
  lane-A-only mode, so the floor stays tested rather than becoming code
  that only runs when something has gone wrong.
