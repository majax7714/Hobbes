# ADR-068 — Every call logged as it went; the pure arm gets a transcript

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-064
(transcript), C-46's surfacing.

## Context

Max read the Modal vLLM logs for the first time and saw calls running a
minute, returning a context-length 400, and then "a 200, fine" — the
window saturating far more often than the envelope's `context_fitted`
/ `context_elided` counts suggested. He was right about the mechanism
and the counters were right about what they count: C-46's fit turns an
overflow into a 200 with `max_tokens` shrunk to whatever room is left,
and a prompt at 30k of 32k tokens that *happens* to fit under the cap
never errors at all. Neither is visible anywhere but a provider's log.
Reconstructing the 5-fresh re-run's per-call prompt sizes took
tokenizing 221 message prefixes on the endpoint — and the pure arm
could not be reconstructed at all, because it wrote no transcript
(ADR-064 said "both arms"; the pure-arm command never passed
`--transcript`).

## Decision

- `Endpoint.chat` records the last call as it actually went —
  `max_tokens_sent` (after any fit), `prompt_tokens`,
  `completion_tokens`, `finish_reason`, `fitted`/`elided` events on the
  way, the window the endpoint reported, `wall_ms`. The loop appends one
  record per call (cut retries marked) and writes **`calls.jsonl` beside
  the transcript** in the same `finally`.
- The envelope gains **`prompt_tokens_max`**, **`calls`**, and
  **`calls_saturated`** (calls that needed a fit or an elision to go
  through at all). A run can now state how much of its wall was spent
  at the window without a provider's log.
- **The pure arm passes `--transcript`** (`<workspace>/.hobbes/
  transcript.jsonl`, both the podman and host variants); the loop
  creates the parent directory.

## Consequences

- C-46's "You find out" now points at `calls.jsonl` and the two envelope
  fields; the register entry is amended.
- The validated reconstruction of the re-run (hypotheses doc) is the
  last one that has to be done by hand.
- `bench report` does not yet aggregate `calls_saturated`/
  `prompt_tokens_max`; a per-run window summary is the natural next
  report row (parked in `future_additions.md` — small).

**Tests:** `TestPerCallLog`, the pure-arm test asserts the transcript
and call log exist. 848 pytest.
