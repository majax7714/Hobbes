# ADR-077 — Aided implement mode: Hobbes aids the model, it does not fence it

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-059 (staged
run), ADR-064 (task-tailored selection), and the write-scope model
(ADR-061/C-38). Relates to C-52.

## Context

The first clean 27B comparison (`five-fresh-27b-adr075`, benchmark-
hypotheses.md Results) was **pure 4/5, harness 1/5** — and the harness
losses were traced, per instance, to the **multi-unit decomposition**, not
the proxy and not localisation. Inspected on django: the fix spanned three
co-changing files (`filters.py`, `db/models/fields/__init__.py`,
`reverse_related.py`); the partition scattered them across units U4, U1,
and *no unit at all*; the planner named only the first, so C-52 spawned
only U4; and U4's **write scope excluded the other two files** — so the
coherent fix was structurally impossible inside the unit boundary,
regardless of comprehension. The pure single agent, with no fence, edited
all three and solved. xarray was the same shape (1 of 2 files). The
planner's own *approach prose* named the mechanism in the unnamed files
(`get_choices`, `Dataset.integrate`) — the pipeline had the information and
discarded it.

Max's framing: **Hobbes should aid the model, not override it.** It secures
a *fraction* of understanding through derived context and hands it over —
"here is your task, what we can see, and what we cannot see around it" —
giving the model a clearer start. It must not narrow the model below what
the task needs. The pure arm proves the model comprehends the whole task;
the harness was removing that comprehension.

## Decision

A new staged implement mode, `hobbes bench run --implement-mode aided`
(and `run_staged(implement_mode="aided")`), default still `unit`:

- The **planner stage is unchanged** (it localises well — 80% hit).
- **No partition, no per-unit write scope.** One implementer runs on the
  **whole worktree**, and its **entire diff** is the candidate patch
  (`_integrate_one(allowed=None)`).
- Its brief (`aided_brief`) is exactly the three-part shape: the **task**;
  **what Hobbes can see** (the planner's files/symbols/approach/tests plus
  the graph neighborhood — callers/callees — around the named symbols, the
  likely co-change sites); and **what Hobbes cannot confirm** — stated
  outright that the named files are where the change *starts*, not every
  file it touches, and that the agent is **free to read and edit any file**
  the fix requires. Derived context is "a head start on understanding, not
  a boundary on your work."
- `read_branch` still **measures** how far the agent ranged beyond the
  planner's files (`rework_files`) — a signal, never a fence.

## Consequences

- The write-scope guarantee (C-38) does not apply in aided mode — and does
  not need to: there is one agent, so there is no cross-unit clobber to
  prevent. The partition's isolation was protecting against a fragmentation
  the aided mode does not create.
- This is the first realisation of the harness pivot's principle inside our
  own harness, and the natural bridge to the mini-swe single-agent path
  (`docs/harness-mini-swe-integration.md`): both give one agent the whole
  task aided by derived context.
- Open question it sets up (to observe on the 7B, where the flow is
  legible): does the aid-not-fence brief actually reach a free agent and
  produce the coherent multi-file change the unit mode could not? Prompt
  inspection + flow, per Max.
- Test: `test_aided_mode_is_one_free_implementer_not_a_partition` (one
  `impl` unit, whole diff merged, no contracts, brief carries "an aid, not
  a boundary" / "edit ANY file" and no "write scope").
