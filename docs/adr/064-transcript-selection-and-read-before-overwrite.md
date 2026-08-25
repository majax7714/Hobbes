# ADR-064 — Persist the transcript, select only units with planner work, and read before overwriting

**Date:** 2026-08-22
**Status:** accepted — three changes Max directed after reading the
ADR-062 re-probe trace ("transcript persistence for sure; instead of
telling each agent 'you have no work' just don't bring them in at all;
the read-before-overwrite rule is also good").
**Amends:** `docs/constraints/README.md` (**C-52**); `docs/hobbes-architecture.md`
(§6, staged execution — selection and the loop's write discipline).

## Context

The re-probe (0/2, recorded in `benchmark-hypotheses.md`) was traced by
hand and three things were confirmed, not one:

1. The owned loop keeps only the `[turn N]` tool-call lines and the
   final envelope. A trace of *why* a unit did what it did stops at the
   tool call — the model's own words in the turn are gone.
2. Units the planner named nothing in were spawned anyway, told "nothing
   named is yours", and spent a whole session returning a prose plan to
   edit **another** unit's file. A session that exists to do nothing is
   pure cost (one alive at a time, ~28 tok/s).
3. The 7B, once aimed at the right file, called `write_file` on it
   **without reading it** — 13579's U10 replaced a 308-line module with
   a 36-line stub; 13398's U2/U7/U9 overwrote modules they never read.
   `write_file` was documented "create or overwrite" with nothing
   between the model and a destructive whole-file replacement.

## Decision

**Transcript.** The loop takes `--transcript PATH` and writes the full
message list (system, user, every assistant turn with its tool calls,
every tool result) as JSONL on exit — in the `finally`, so a crash
still leaves it. `hobbes-session`'s `RuntimeCommand` passes
`<session-home>/transcript.jsonl`, which persists after the clone is
cleaned. Both arms, since the loop is identical.

**Selection.** On the planner path (`seed_source == "planner"`), a unit
for which `unit_has_planner_work` is false — the planner named no file
or symbol that resolves to, or path-matches, one of its interior files
— is **not spawned**. It is recorded (`reason` = task-tailored
selection; `units_not_selected` on the record) and counted `done` so a
consumer still becomes ready, exactly as a human-first unit is. On the
lexical fallback there is no per-unit naming, so every unit stays. This
is the first cut of the parked "task-tailored unit selection": the cap
is a ceiling, the planner's naming is the selector.

**Read before overwrite.** In the loop, `write_file` onto a path that
already exists and that the session has not `read_file`'d is refused,
pointing at `read_file`+`edit_file` (or a full read then write). A new
file is allowed; a write after a read of the same path is allowed;
`edit_file` is unaffected (it must already see the file). Both arms.

## Consequences

- A planner miss now means a unit is **not tried at all**, where before
  it was tried and did nothing useful. The planner is a one-shot 7B
  opinion (C-47), so this concedes any change the planner failed to
  name — registered as **C-52**, surfaced in the banner, the manifest
  and the record. `--parallel 1` and the lexical fallback are the
  escape hatches; the verifier is the check that a needed unit was
  dropped.
- The write rule changes what a mis-aimed model *can* do, never what a
  correctly-aimed one writes: it cannot silently shrink a file it has
  not looked at. It does not force a good edit — a model that reads then
  overwrites badly is still free to. That is the boundary between this
  (a tool-discipline guard, the exec-repeat family) and the model's
  competence, which the next run measures.
- The transcript is the observability the trace lacked; the next
  re-probe's `write_file`-without-read events (if the rule leaks) are
  now readable turn by turn.
- Tests: `test_write_file_must_read_an_existing_file_first`,
  `test_transcript_is_written_when_asked` (loop);
  `test_unit_selection_keeps_named_units_and_drops_the_rest` and the
  wiring assertion (staged run); the Go `RuntimeCommand` test asserts
  `--transcript`.
