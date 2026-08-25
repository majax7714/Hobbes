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
