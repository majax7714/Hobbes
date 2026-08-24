# ADR-086 — An aided run refuses the Hobbes label mechanically

**Date:** 2026-08-24 · **Status:** accepted (Max's call, with the ADR-083
lever-2 deferral decided the same day) · **Realises:** P12 (ADR-082) —
"the method, not a person, must refuse the label." · **Amends:**
`docs/hobbes-architecture.md` (§6.2), ADR-077's scope note.

## Context

`--implement-mode aided` (ADR-077) spawns one implementer on the
planner's task, free on the whole worktree — a useful *model + prompt*
baseline arm, and by P12 never a Hobbes test. After ADR-082 the deepswe
script refuses the `hobbes` arm name mechanically, but the owned
harness's aided path enforced nothing: its records carried
`arm="harness"`, and only a help-text warning (2026-08-24) stood between
an aided run and a mislabelled report — the exact human-discipline
failure P12 was written against.

## Decision

The machinery labels the run, a person never gets to. In
`bench/arms._run_staged_arm`, `implement_mode == "aided"` sets the arm
label to **`model+prompt`** on **every** return path (patch, no-seed,
plan-error, run-error), and `detail.implement_mode` rides the record.
`bench/run.py` resumes, names patch files, and reports env/checkout
errors under the same recorded arm, so the evaluator's predictions and
the report's groups all say what the run actually was. The report's
notes state the rule; an aided run **enters no H1 harness slot** — it
appears as its own `model+prompt/<model>` group beside `pure` and
`harness`.

The mode itself stays: it is the in-harness *model + prompt* baseline
ADR-077/082 re-scoped and kept. Removing it was considered and declined
— the baseline is worth having, mislabelling it is what had to die.

## The same day's second call — ADR-083 lever 2 is deferred to run records

Max's decision (2026-08-24): lever 2 (pulling the seed's git co-change
set into its interior) is **not built now and not rejected** — it is
decided from the 7B validation run's strict-coverage records, where a
co-change file the planner did not name now surfaces as an uncovered
requirement's missing owner (ADR-085). The 7B validation run does not
depend on it (sympy 1/1 and sphinx 2/2 are fully seed-covered).
ADR-083's status line carries the dated deferral.

## Consequences

- A future session cannot report an aided run as a Hobbes test without
  editing this mechanism — which is the point.
- `verdict.model_name` yields `hobbes-model+prompt-<model>` for aided
  predictions; the evaluator's report is named accordingly.
- Resume keys changed shape for aided runs only (`(id, model+prompt,
  model)`); no stored run used aided mode under the old key, so nothing
  re-runs.
- No register entry: nothing is conceded — a label became enforceable.
