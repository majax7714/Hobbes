# ADR-091 — Loop discipline under window saturation, and the handoff nudge

**Date:** 2026-08-27 · **Status:** accepted · **Owner:** Max · **Source:** the ADR-085 validation run's defect register (`docs/adr085-validation-run.md`, D1–D4, D7, D8)

## Context

The ADR-085 validation pair (2026-08-24, 7B) was judged on the
machinery's behaviour, and the register it produced names eight
defects. Five are the agent loop losing its discipline exactly when the
context window binds — the general mechanism (window fitting, elision)
hollowing out the specific guarantees (read-before-edit, ADR-064/067)
underneath it, the P10 shape ADR-036 names. One is a Python decode
degradation wearing Rust's wording and riding every brief. D5 and D6
are shape decisions; Max holds them (2026-08-27) — the harness's shape
is not the current focus — and they stay documented in the register.

## Decision

All in `pipeline/src/hobbes/agent/loop.py` unless stated.

- **D1 — one fit per elide cycle.** `Endpoint.chat` treats the input
  count an overflow error reports as a *lower bound*: after one fitted
  retry in a cycle, a second overflow elides rather than refits. vLLM's
  "at least N input tokens" is `window − max_tokens + 1`, so refitting
  from it shrinks the room 17 tokens a try; one sklearn call absorbed
  450 400s. Endpoints that report true sizes keep the single-retry
  behaviour unchanged.
- **D2 — action memory is never elided.** `elide_oldest_tool_result`
  skips results from `MUTATING_TOOLS` and any result shorter than
  `ELIDE_FLOOR` (2× the placeholder). It now returns the elided message
  (or `None`) so the loop can revoke what that result had earned.
- **D3 — an elided read revokes the ticket.** `Endpoint.on_elide`
  hands the elided message to the loop; when it was the last visible
  `read_file` of path P, P leaves `read_paths` and the next
  `write_file`/`edit_file` on P is refused (`ELIDED_READ_REFUSAL`)
  until P is read again. The repeat guard also forgets the elided
  call's signature, so that re-read is not refused as a repeat.
- **D4 — no edit in the turn a path was first read.** `read_turn`
  records the turn each path's ticket was earned; an edit or write on
  that path in the same turn is refused (`SAME_TURN_REFUSAL`) — the
  anchor was authored before the read's result existed. A re-read of
  an already-ticketed path does not re-arm the guard.
- **D8 — the handoff nudge and `handoff:` on the record.** An
  implementer that edited, has a `reflect` tool on offer, and ends in
  prose without a handoff gets one bounded `NUDGE_HANDOFF` (mirroring
  `NUDGE_READ_ONLY`); the envelope carries `handoff_nudged`. Every
  unit record gains `handoff: handoff | reflection-only | missing`
  (`run/orchestrate.py::handoff_status`, set at every harvest).
- **D7 — the duplicate-symbol record is scoped and worded per lane**
  (`scip/index.mjs`, `extract/scipsource.py`). `decode` returns
  `ambiguous_files`; the `scip-decode` record's `path` is the files'
  deepest common directory, so `derive/manifests.py`'s existing filter
  keeps it out of briefs whose interior lies elsewhere; the wording is
  per language (`DUPLICATE_SHAPES`). TS zone records are rebased with
  the zone's other paths.

## The D7 correction

The register diagnosed the sklearn row as *foreign environment
residue*. It was not: `exercise_01_language_train_model.py` lives in
sklearn's own tree twice — `doc/tutorial/text_analytics/skeletons/`
and `…/solutions/` — a legitimate in-repo C-28 duplicate. The defects
that remain were the wording and the whole-repo `path: "."`, which is
what this ADR fixes. The register carries the correction.

## Consequences

- Worst-case absorbed 400s per call fall from ~75 per elide cycle to
  one; the fit counters in `calls.jsonl` keep their meaning.
- A saturated session may now exhaust elidable results sooner (short
  and mutating results are off the table) and fail honestly with the
  overflow instead of forgetting what it did. That is the intended
  trade: a wrong graph is worse than no graph, and a repeated failed
  edit is the loop's version of a wrong graph.
- Validated with no model: 46 loop tests, replayable against the
  stored `calls.jsonl` arithmetic. Not yet re-run on the 7B —
  experiments stay parked.
- D5/D6 remain open in the register, by decision, not by omission.
