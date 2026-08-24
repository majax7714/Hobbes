# ADR-082 — A Hobbes test decomposes, or it is not a Hobbes test (P12)

**Date:** 2026-08-23 · **Status:** accepted · **Retracts as Hobbes
evidence:** every Pier result under ADR-078..081, and `five-fresh-7b-aided-fix`
(ADR-077). **Amends:** architecture "Design principles" (adds P12),
`docs/benchmark-hypotheses.md` (reading rule), ADR-077 (the aided mode is
a *repair* for fragmentation, not a test shape).

## Context

Hobbes breaks work up and derives context **in order to** (1) reduce the
context window a large task needs, (2) improve the accuracy of what the
agent recalls, and (3) improve implementation through specialised,
sandboxed roles. Every hypothesis in `docs/benchmark-hypotheses.md` rests
on that decomposition. Between 2026-08-22 and 2026-08-23 it slipped out
in two steps and nobody — builder or method — caught it:

- ADR-077 removed the split (one implementer on the whole worktree) in
  response to module-grain units fragmenting co-changing files.
- ADR-078 removed the planner (a deterministic aid, C-55) to get DeepSWE
  running on Pier.

From then on the "Hobbes arm" was **one agent, the whole task, a larger
prompt** — the exact shape Hobbes exists to prevent. It forgoes role
assignment, per-role sandboxes, and the smaller window; it gives one
agent several jobs; and it *adds* reading. The data said so immediately
(the arm read more, wrote more, overflowed first) and the reports still
called it a Hobbes test. Four 27B pairs (~12 A100-hours) were spent
comparing agent against agent with a hint. Max (2026-08-23): "without
breaking up a task, Hobbes by nature will fail on all of those accounts —
this does not need to be observed but already has."

The structural failure is that nothing in the method refused the label.
Each ADR was locally justified; their sum inverted the premise. That is
P10's lesson at the level of the programme: a general convenience (one
agent is simpler to run) absorbed the specific guarantee (the
decomposition is the product).

## Decision

**P12 — A Hobbes test decomposes, or it is not a Hobbes test.** A run may
be reported as a Hobbes arm only if (a) a planner stage defined the units,
(b) the task was split into more than one single-use agent with distinct
roles, and (c) **every implementer's window was smaller than the task's** —
its own facts and spans, not the whole task plus an aid. A run that fails
any of the three is reported as *model + prompt*, never as Hobbes, and its
scores go in the table under that label. `hobbes bench report` and the
Pier runner must print the shape (`planner`/`units`/`max_unit_window`) on
every record, and refuse the `hobbes` arm label when the shape is absent.

**Retracted as Hobbes evidence:** ADR-078..081's Pier pairs (7B, 27B ×3)
and `five-fresh-7b-aided-fix`. They remain valid as harness wiring,
instrument development, and *model + prompt* observations (the familiarity
probe, the shape diff, the read-volume metric all stand).

**ADR-077 is re-scoped:** the aided brief is the *content* of an
implementer's context (task + what Hobbes can see + what it cannot), not
a licence to run one implementer on the whole task. The fragmentation it
answered is a unit-grain problem — to be solved by planner-defined,
change-grain units that keep a co-change set together — not by removing
the split.

## Consequences

- The next phase is what the handoff already says — inspection and deep
  thinking, no runs — with P12 as its constraint: the shape to design is
  planner → change-grain units → per-unit windows smaller than the task →
  specialised roles → integration; on Pier that means several agent
  sessions per task in one container with a commit per unit, which Pier
  does not do natively and we must build or drive.
- The 27B unit-mode record (`five-fresh-27b-adr075`: per-unit implementers
  at 0.8–1.6 M tokens) is the real open problem P12 points at — units that
  multiply the work instead of dividing it — and the place the thinking
  starts.
- `docs/benchmark-hypotheses.md` gains P12 as a reading rule above the
  results, and the Pier tables are relabelled.
