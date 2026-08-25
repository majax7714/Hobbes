# Oracle lane — pre-registered predictions (design §10)

**Committed 2026-08-25, before O2 ran.** Each prediction is graded in
`extraction-evidence.md` when its cell lands, including the ones that
miss. This is the dry run for the habit the harness benchmark needs:
numbers written down before the run, so results cannot re-scope them.

## Priors

Every hand-check to date is 100% at n=20–33 (95% lower bound ~83–89%).
Lane agreement on this repo is 0 disagreements at 3,085 sites; on dagger
258 of 36,703, 126 of them build-tag and 131 line-convention. The O1
fixtures showed the semantic lane draws **no edge at all** for an
interface-method call.

## Predictions

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P1 | O2 (this repo, `go/`) | precision-against-oracle for **semantic** edges ≥ 95% | met if the semantic-tier number, after triage removes match-defects only, is ≥ 95% |
| P2 | O2 | contradictions concentrate in the **syntactic** tier: syntactic precision < semantic precision, and ≥ half of all contradicted rows are syntactic (this repo's graph carries only 3 syntactic edges, so this may be undecidable — recorded as such if so) | met if both hold; undecidable if syntactic edges < 10 |
| P3 | O2 | recall gap is dominated by **dynamic dispatch**: `dynamic` + `dynamic-closure` ≥ 60% of misses | met if the miss decomposition says so |
| P4 | O2 | in-repo recall between **60% and 85%** at the cell's root count (binaries + test mains) | met if in band |
| P5 | O2 | oracle-silent ≤ 15% of Hobbes edges, `unreachable` the largest silent reason (test-only helpers and unused exported functions) | met if both hold |
| P6 | O2 | the ADR-037 hand-check cannot be reproduced by identity (its 20 edges were never listed); the whole semantic set stands in for it | recorded as a finding regardless |
| P7 | O3 (kbet TS) | precision-against-oracle ≥ 95% semantic; overload-set membership needed for ≥ 1 confirmed edge | graded at O3 |
| P8 | O4 (dagger Go) | the 126 build-tag lane disagreements grade **oracle-silent (`not-loaded`)**, not contradicted | graded at O4 |
| P9 | O4 | precision-against-oracle for the 7,322 core/integration → `sdk/go` edges (C-33's lift) ≥ 95% | graded at O4 |

## What would falsify the lane's usefulness

If O2 produces a contradiction rate above ~10% that triage attributes
mostly to **match-defect**, the conventions (D-O4) are wrong and the
lane is measuring its own normalisation; fix before any real number is
quoted. If triage attributes them mostly to **oracle-unsound**, RTA is
the wrong oracle for this code shape and VTA (D-O1's optional arm)
runs next.

## Phase 2 — committed 2026-08-25, before O6 / O7 ran

Priors: Python has **no edge-accuracy evidence at all** beyond lane
agreement (1,789 sites / 0 disagreements on this repo) and the M5
narrative sample; the SWE-bench workspaces' 53–72% capture is a
detection number, not an accuracy one. Rust has ADR-040's 33/33
hand-check on `rust_proj` (95% lower bound ~89%). The phase-1 lesson
(H-3, H-5, H-6, H-7): the first pass of a new oracle is usually the
oracle being right at a different grain, so every phase-2 prediction is
graded **after** match-defect triage, never on the first pass.

O6's first cell is this repo's Python zone (`pipeline/`, under its own
pytest suite, `HOBBES_SCIP=0` as the suite runs by default); xarray was
in the design but **no SWE-bench workspace exists on this box any
more**, so that cell is recorded *not run* rather than predicted.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P10 | O6 (this repo, `pipeline/`) | **recall-against-executed** over in-repo observed pairs to *named* declarations (functions, methods, classes) ≥ 90%; over *all* observed in-repo pairs (nested functions, lambdas included) between **70% and 92%** | met if both hold after match-defect triage |
| P11 | O6 | the **suspect rate** (suspect / (confirmed + suspect)) ≤ 2%, and triage attributes the suspects mostly to *not-exercised* or *match-defect* (decorators, `functools.wraps` wrappers, `__call__`), not *hobbes-wrong* | met if the rate holds and ≥ half the triaged suspects are not hobbes-wrong |
| P12 | O6 | the suite exercises ≥ 60% of Hobbes' call sites under `pipeline/src`; the unobserved bucket is dominated by `line-not-called` (never executed), not `line-mixed` (executed, but only C or out-of-repo callees seen there) | met if both hold |
| P13 | O6 | misses concentrate in **closures**: pairs whose target is a nested function or lambda (`observed→closure`) ≥ 50% of all in-repo misses; the runner-up is calls dispatched through a callable object or bound value Hobbes cannot name statically | met if the miss decomposition says so |
| P14 | O6 | at least one **harness defect** in the oracle-right-at-a-different-grain class (decorator line vs identifier line, wrapper vs wrapped) is found by the miniapp fixture or the first triage, before any number is quoted | recorded as a finding regardless |
| P15 | O7 (`rust_proj`) | the MIR resolution oracle **confirms all 33** of ADR-040's hand-checked edges; any divergence is a harness finding first (design §7) | met if 33/33 after match-defect triage |
| P16 | O7 (`rust_proj`, then dagger's Rust if the driver holds) | precision-against-oracle ≥ 95% on the semantic tier; misses concentrate in **trait dispatch** (`dyn` and generic-bound calls, oracle-silent or dynamic) and closures, ≥ 60% of misses | graded per cell reached; dagger rust is recorded *not reached* if the driver does not get there |

**What would falsify phase 2's usefulness.** If O6's coverage line is
below ~30% of Hobbes' sites, the executed slice is too thin for any
recall claim and the cell is recorded as a coverage measurement only.
If O7's driver cannot be pinned to a nightly that builds `rustc_private`
on this box inside the time box, the Rust lane is recorded *not built*
with the toolchain reason, and ADR-040's hand-check stays the only Rust
evidence — said so, in the row.
