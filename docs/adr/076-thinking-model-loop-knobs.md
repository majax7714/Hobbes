# ADR-076 — The loop-discipline knobs are exposed per run, for a thinking rung

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-058 (the
pipeline-discipline stall/nudge), ADR-074 (the thinking rung).

## Context

The owned loop stops a session after `--stall-after` dry (no-edit) turns
and nudges after `--nudge-after` (ADR-058). Both defaults (6 and 3) were
cut against the 7B, whose failure mode was a model that wrote a prose plan
and never edited — so a short leash was right. A thinking model
(Qwen3.8-27B, ADR-074) has the opposite shape: it searches, range-reads,
and reasons across several turns *before* its first edit. The
`five-fresh-27b` run made the cost concrete on the pure arm, where no proxy
was involved: **sphinx pure was stopped at turn 12, six dry turns into a
correct investigation** (search → ranged reads toward the fix), the stall
rule mistaking investigation for a stall. The defaults cannot serve both
model shapes.

## Decision

`hobbes bench run` gains `--stall-after` and `--nudge-after`, carried on
**both arms** through `bench.Runtime` (the loop flags the sampling already
rides, ADR-074). Unset leaves the loop's own defaults, so every 7B record
stands unchanged; a thinking-rung run raises them. The knobs are the run's,
recorded in `run.json` via `Runtime.describe`.

The pure arm's wall is the existing `--timeout` (sklearn pure hit the
3600 s default at turn 40 doing real work); a thinking-rung run raises it
rather than reading a timeout as a model failure.

## Consequences

- The 7B ladder is untouched: no run set these, so the loop defaults (6/3)
  and the 3600 s timeout still apply to that record.
- A run's discipline is on its record, so a solve or a stall can be read
  against the leash it ran under, not a hidden default.
- Test: `test_stall_and_nudge_knobs_reach_both_arms` (both arms' argv; unset
  leaves the default off).
