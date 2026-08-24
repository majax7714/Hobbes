# ADR 030: A conceded fact is a registered constraint, with a place it surfaces

Date: 2026-08-15
Status: accepted

Milestone V2.M3. Adds principle **P8** to architecture v2 §1 and creates
`docs/constraints.md`. Applies to the whole project, not to one milestone.

## Context

V2.M3's plan opened with a proposal to demote rather than delete lane A's
call resolver, because deleting it would leave a repo with no working
indexer holding no call graph at all. Max approved the demotion and then
generalised past it:

> if we ever have to concede needed information we need to document
> heavily as a constraint. hobbes is unusable if its a known liar, even
> less usable if its fake honest.

That is a sharper statement than P6 and it is not the same statement.

**P6 covers the run that broke.** An indexer crashed, an environment is
not installed, a language is unwired — the graph stands at syntactic tier
and says so, through `extraction_errors` and an ingest WARNING. It is a
runtime signal about *this* invocation.

**Nothing covered what was never knowable.** Pytest fixtures are invisible
to reach (ADR-007). Stdlib imports are dropped entirely (ADR-007). JS test
reach is per file, so it *over*-reports guarding (ADR-021). Each of those
was decided deliberately, written down honestly in the ADR that made it,
and then became invisible — because an ADR is read once, by the person
who wrote it, and never again by the person reading a coverage number two
milestones later.

That is the failure mode the second half of Max's sentence names. A system
that fails loudly is merely limited. A system that presents a confident,
complete-looking artifact over a gap it knows about is *fake honest*, and
it is worse, because it spends the trust it has not earned. ADR-029
already ran this experiment: 403 unaccounted call sites were correctly
described in an ADR and completely invisible in the product, until a
question exposed them and the coverage denominator got built.

## Decision

### P8 — A concession is a registered constraint

Added to architecture v2 §1:

> **P8 — Every concession is a registered constraint.** (new) When Hobbes
> cannot recover information — a limit of static analysis, a deliberate
> filter, a deferred sharpening — the gap is entered in
> `docs/constraints.md` together with the place a user meets it. P6 covers
> the run that failed; P8 covers what was never knowable. A constraint
> whose only surfacing is a document is recorded as *unsurfaced*, because
> a confident artifact concealing a known gap costs more trust than one
> that fails loudly.

### An entry is not done when it is written

Every entry carries a **surfacing status**: `surfaced` (a mechanism tells
the user where they are standing), `partial` (something says it, but not
at the point of use), or `unsurfaced` (documented only). `unsurfaced` is
**debt, not a decision** — it names a bug that a later milestone pays off.

This is the clause that keeps the register from becoming the very thing it
guards against. A caveats page nobody reads is fake honesty with extra
steps; the register earns its keep only by carrying the surfacing question
next to every admission and refusing to score prose as a solution.

### The register is seeded complete, or not at all

`docs/constraints.md` opens with **21 entries** harvested from ADR-007,
ADR-019, ADR-021, ADR-026, ADR-027, ADR-029, and the M6/M8 session
records — not only from V2.M3. A half-seeded honesty register is itself
fake honest: a reader would take absence as evidence, and be wrong.

The seeding produced the number that justifies the mechanism: **nine of
twenty-one entries are unsurfaced**, and two of those nine mislead
*actively* rather than staying quiet — C-11 (JS test reach is per file, so
`tests_guarding` over-reports on TS repos, and a JS row is
indistinguishable from a precise pytest row) and C-16 (the
dependency-degradation check reads only the repo root's manifest, so on
this repo it appears to run and reports nothing). Neither was knowable
before the register existed. Both were, individually, honestly documented.

### Relationship to `future_additions.md`

`future_additions.md` parks deferred **work**. `docs/constraints.md`
registers conceded **information**. A deferral that loses information
belongs in both and the entries cross-reference. The distinction is worth
keeping because the two answer different questions: "what might we build"
versus "what must a user not assume".

## Alternatives considered

- **A `caveats` section per ADR.** Where the information already was.
  It failed, and C-11/C-16 are the proof: both were documented at the
  moment of decision and both went on to mislead.
- **Surface every limit in the artifacts and skip the document.** The
  right end state and not reachable in one step — nine entries need a
  surfacing mechanism built, several of them milestone-sized. The register
  is what makes that backlog visible and ordered rather than discovered.
- **Fold it into P6.** Conflates "this run degraded" with "this is not
  knowable". The first is a transient condition a rerun can clear; the
  second is a property of the design. A user needs to act differently on
  each.

## Consequences

- Any ADR that drops, approximates, or filters information now lands a
  `C-n` entry in the same commit — the same discipline the conventions
  already apply to ADRs and BUILDLOG entries.
- The register generates a backlog with a natural priority order: actively
  misleading, then unsurfaced, then partial.
- V2.M3 lands C-8 (with no working indexer the symbol layer is wholly
  approximate) as the demotion's registered cost, and expects at least one
  more from the TypeScript staging spike.
- Constraint ids are stable and never reused. A constraint that stops
  being true is marked **lifted** with the commit that lifted it, because
  "we used to be unable to tell you this" is itself worth knowing.
