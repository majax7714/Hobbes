# ADR-093 — Lexical evidence is not a plan and not work: D5 and D6 closed

**Date:** 2026-08-28 · **Status:** accepted — built, validated with no model · **Owner:** Max · **Source:** defects D5 and D6 of the ADR-085 validation run (`docs/adr085-validation-run.md`), held 2026-08-27, reopened 2026-08-28

## Context

Two defects from the 2026-08-24 validation pair were held as one shape
call: *how much evidence must the mapping have before it treats
something as work?* Both were the lexical layer (C-36) standing in for
evidence it does not carry.

- **D5.** A planner whose handoff resolved to no file (django, sklearn —
  both rambled) dropped to the lexical seeds and the run spawned
  implementers under the pre-ADR-085 proposal brief with **no coverage
  check**, inside a `--coverage strict` run. The record read
  `lexical-fallback` and nothing stopped. Worse than the label: the
  fallback path `break`-ed out of the plan loop, so a rambling planner
  never got the one re-plan an *uncovered* planner gets. The removal
  A/B was confounded by it — two of five arms were not the treatment.
- **D6.** The token `astype` in sklearn's issue matched a symbol in
  `sklearn.utils._array_api`, a module 2,543 tests reach. ADR-083's hub
  rule ("a non-seed hub is context, not work") did not apply because
  **a seed was always work**, whatever named it. The unit's interior was
  a hub; its guards were a quarter of the suite.

The three sources of a seed carry very different evidence: a human's
`--seed` (named on purpose, never rejected — C-36); the planner's
handoff (a model's localisation, resolved tolerantly, ADR-059); and a
proposal-text match (a word that equals a symbol name, the weakest
evidence the mapping has, stopword-guarded, not solved — C-36). The
guarantees in ADR-083 and ADR-085 were written for the first two and
the code let the third through on both.

## Decision

**Lexical evidence neither satisfies the coverage guarantee nor makes a
hub work.** Two rules, one principle.

### D5 — under `strict`, the lexical fallback is a plan error, after the one re-plan

`run/stages.py`: a planner whose handoff resolves to nothing is treated
like a planner whose requirements are uncovered — it is re-planned
**once** with `fallback_note` as its short memory (the names it gave,
"none found", name real paths). If the second handoff resolves, the
run continues on the planner path and coverage is checked as before.
If it still resolves nothing, `--coverage strict` (the default) raises
`PlanCoverageError(status=lexical-fallback)` at plan cost: the
partition record is written with `coverage.planner_unresolved`,
`replanned: true`, `units: []`, and no implementer is spent.
`--coverage assign` keeps the old shape — it runs on the lexical seeds
and the record says `lexical-fallback` — because `assign` is the
explicitly lenient mode (C-57). Dry runs and aided mode are unchanged.

The strict guard's three statuses are now `uncovered`,
`no-requirements`, `lexical-fallback`; the bench arm already classes a
`PlanCoverageError` as `plan-error`, so the outcome is counted, not
silent — the E-number ADR-084 asked for ("how often does strict stop
the run") now includes the planner that could not name a file.

*Declined:* deriving requirements lexically from the proposal's
imperatives on the fallback (`coverage.imperatives()`) so a check could
still run — that puts the coverage guarantee on C-36 matching, the
thing ADR-085 moved it off, and would say `covered` of a plan nobody
understood. *Declined:* a label only (`bypassed-fallback`) — honest,
but leaves `strict` meaning "strict when the planner cooperates", the
P10 shape a general degrade must not absorb.

### D6 — a lexical seed does not override the hub rule

`derive/impact.py`: `ImpactSet.seeds_lexical` records which seeds came
from the proposal's text alone (no `--seed`; the staged run's planner
seeds arrive as explicit values, so a planner-named hub stays work,
per ADR-083). `derive/partition.py`: `unit_modules` drops a lexical
seed that is a **hub** (fan-in ≥ `HUB_FANIN`); `context_seeds` names
each with its reason; the spec carries them as `seeds_context` and
`hobbes plan` prints "seed is context, not work: … name it with
--seed if it is the change". The seed still expands — its
neighborhood is in the impact set and reaches every unit as context.
Only the **hub** half of ADR-083's rule applies to lexical seeds: the
package-root half is a heuristic on the id's shape (dotless) that
names every top-level module of a small repo, and a real `package`
node is already set aside by `filter_seeds` rule 1.

When every seed is a lexical hub, `derive_plan` refuses with
`SeedError` naming the fix (`--seed`) — the same treatment as an empty
seed set. What would remain is the hub's neighbourhood: units with no
seed in them, a plan built from context.

*Declined:* the parked C-36 weighting (score a prose-shaped hit below
1.0) — reaches the same result on sklearn through a new magic number
(C-35) and changes every lexical expansion; the register says those
adjustments wait for verdicts. *Declined:* refusing bare lowercase
symbol-name matches as seeds at all — too blunt; the requests probe's
gold hits came partly through such words, and it would move the
gold-coverage metric, which ADR-083 reserved for Max.

## Consequences

- **The removal A/B is un-confounded on the D5 axis.** Its re-run still
  needs a cleared 7B run with n large enough for O4's planner
  variance; nothing here changes the standing policy (experiments
  parked).
- The strict stop-rate on the 7B will rise — a rambling planner is now
  a counted plan error, not a run. That is the number, not a
  regression.
- `unit_modules(graph, scores)` without `lexical_seeds` behaves exactly
  as before (ADR-083); the one product caller passes it.
- Validated hermetically: a stubbed rambling planner → one re-plan
  with the note → strict raises with the record written / `assign`
  runs and says so / a recovering second handoff continues; a
  thirty-importer hub seeded by one word is context, by `--seed` is
  work, and alone is a `SeedError`. No model, no GPU.
- Register: C-36 and C-57 amended; D5 and D6 flipped to fixed in
  `adr085-validation-run.md`; architecture §6 no longer carries the
  D5 carve-out.
