# ADR-085 — Requirement coverage: the planner hands off requirements with owners, and the run refuses a plan that leaves one unowned

**Date:** 2026-08-23 · **Status:** accepted, built (Max's go, 2026-08-23:
"proceed to the planner and mapping fix") · **Realises:** ADR-084 (the
frame) — fixes A and B of the session handoff. **Amends:** ADR-059 (the
planner's handoff shape), ADR-062 (the projected handoff), ADR-064 (unit
selection), the verifier brief. Registers **C-57**.

## Context

ADR-084 named the defect: the planner did *localization* (request →
files) and not *requirement decomposition* (request → what must become
true → an owning unit each). sympy-13852's value-eval requirement was
stated in the issue, verbatim, and had no owner in any handoff; no
implementer could have done it, and the 7B — handed the full proposal
*and* the lossy handoff — trusted the handoff. The frame's four
decisions: the planner is the requirement-decomposer; coverage (⋃
handoffs ⊇ requirements) is its guarantee; each handoff is complete for
its implementer (the measurable test: the implementer succeeds with the
proposal removed); the weight belongs to the planner. This ADR is the
mechanism for each.

## Decision

1. **The handoff carries `requirements:`.** One line per requirement,
   `R1: <what must become true, in the proposal's words> -> <owning
   file>`. The planner brief asks for it first, says the planner is the
   *only* agent that reads the whole request, and raises the handoff
   bound to 30 lines (ADR-070's limit was for a file list). The parser
   (`run/handoff.py`) splits this field on lines only — a requirement
   is a sentence and carries commas — and does **not** inline-split it
   (an owner clause `-> files: a.py` would otherwise migrate into
   `files:` and leave the requirement ownerless). A requirement's files
   are seeds like the planner's `files:` — a requirement's owner is
   where the change goes.

2. **Ownership is by named file, never by meaning** (`run/coverage.py`).
   A requirement is a unit's when one of its files resolves to the
   unit's interior (module id) or path-matches an interior file — the
   same tolerant rule as `planner_slice` (ADR-062). A requirement that
   names no file is owned only when every file the planner named lies
   in **one** unit (a contained change has one possible owner,
   `source: contained`). Otherwise it is **uncovered**. Nothing is
   inferred from the requirement's prose; that inference is the
   planner's job and the model's opinion (C-47).

3. **An uncovered requirement is a plan error at plan cost.** The run
   derives, assigns, and on `uncovered` or `no-requirements` re-spawns
   the planner **once** (`planner-2`) with the orchestrator's note as
   its short memory — the uncovered requirements by id, the files it
   named that were not found. Then, by `--coverage`:
   - `strict` (default): the partition record is written with the
     coverage and `error: plan coverage failed`, and `PlanCoverageError`
     (a `RunError`) stops the run — no implementer session is spent on
     a plan that cannot be implemented. The bench arm classes it
     **`plan-error`** (not `run-error`) with the coverage on the record.
   - `assign`: leftovers go to the **seed unit** (the unit holding the
     planner's first resolved file) and every such requirement is
     marked `source: assigned` in the record and in the unit's brief —
     the orchestrator's fallback, not the planner's guarantee (C-57).
     With no requirements at all, `assign` runs the pre-085 shape (the
     proposal in every brief) and records `no-requirements`.
   A dry run records the coverage and judges nothing. The lexical
   fallback (the planner resolved nothing) records `lexical-fallback`
   and is never a coverage error — there is no planner to hold to it.

4. **Owned requirements are the implementer's task; the proposal leaves
   the brief.** On `covered`/`assigned`, `render_brief(task=…)` puts
   `## Your task (the planner's handoff — the requirements this unit
   owns)` where `## Proposal` was, says the full request is absent by
   design, and that a requirement the implementer believes missing is a
   `reflect`, not an edit. The projected planner note (ADR-062) leads
   with "you own *n* of the plan's *m* requirement(s)". `brief_task:
   requirements|proposal` is on the record. `--proposal-in-brief`
   restores the old shape — the **control arm of the removal test**
   (ADR-084 §3), not a default. Unit selection (ADR-064) keeps a unit
   that owns a requirement even when the planner's `files:` named
   nothing in it. The verifier's brief lists the requirements as a
   checklist and may hand back the ids it saw unmet.

5. **The weight can move to the planner.** `--planner-arg` (run and
   bench) passes `hobbes-session` flags to the planner session alone,
   *after* the run's, so `--planner-arg=--max-turns=80` or a larger
   `--max-tokens` raises the one comprehension role's budget without
   touching the implementers. No default is changed here — the budget
   is a run's declaration, pre-registered like the sampling (ADR-074).

6. **The cheap precursor ships** (`imperatives_unmentioned`): the
   proposal's imperative sentences (a pinned verb list or a modal; code
   blocks and interpreter transcripts stripped first) whose content
   tokens — crudely stemmed — appear less than half in the planner's
   handoff text. Recorded per plan stage as `imperatives_unmentioned`
   and summed in `hobbes bench report`. It is lexical (C-57): a
   measure of the gap, not a verdict, and never gates anything.

## Validation (no model — the standing policy)

- 906 pytest green; 20 new cases (`tests/test_coverage.py` + the bench
  plan-error case): the parser's shapes, the ownership rule, the three
  outcomes end to end on the stand-in session (covered → requirements
  are the task, proposal absent from the brief, verifier checklist;
  uncovered → `planner-2` spawned with the note, then strict stops with
  no implementer brief written / assign runs with the leftover on the
  seed unit and `C-57` in its brief; no requirements → strict error /
  assign's old brief), the removal-test control, dry run, a bad mode.
- **Replay over stored handoffs** (`~/.hobbes/bench/*/work/*/harness-*`,
  `verified.jsonl`): the precursor flags "Add evaluation for polylog" as
  dropped in **every 7B sympy handoff** (tier1-grain, adr072, clean —
  the BUILDLOG seventy-sixth defect) and keeps it for the **27B's**,
  whose approach carried the value case. django's one imperative is
  kept in both rungs. xarray's three are flagged in every rung — they
  are discursive ("IMO it doesn't make sense…") and share few tokens
  with any handoff; that is the lexical limit, stated in C-57, not a
  finding about the planner.

## Consequences

- A 7B planner that does not write `requirements:` now fails at plan
  cost under `strict`. That is the measurement ADR-084 asked for
  ("measures the gap before closing it"); `--coverage assign` is the
  knob for a run that must produce a patch regardless, and the record
  says which was used. **No run is scheduled** — experiments stay
  parked (standing policy).
- The planner hit-rate (C-49) stays; the new per-record fields
  (`coverage.status`, `brief_task`, `imperatives_unmentioned`) sit
  beside it in the report. The removal test is now runnable as an A/B
  (`--proposal-in-brief` vs default) whenever runs are cleared.
- ADR-083 lever 2 (co-change into the interior) stays pending under
  this design: a co-change file the planner did not name is now
  visible as an *uncovered requirement's* missing owner rather than a
  silent gap, which is the evidence that decision needs.
- Not built: requirement-level verification (the verifier's
  `requirements:` hand-back is read but drives no rework selection);
  a semantic coverage check (by design — C-57).
