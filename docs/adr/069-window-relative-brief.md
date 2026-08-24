# ADR-069 — The brief is sized to the model's window and filled by priority

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-058's
brief limit (C-45), ADR-062's protected interior (unchanged).

## Context

The brief limit was an absolute 60,000 characters (ADR-058), chosen
for the 32k window and never tied to it. Measured on the 5-fresh re-run
(C-46, 2026-08-22): a brief tokenizes to up to 16,750 of 32,768 tokens,
82 % of it sections the unit cannot change (Neighborhood 11.1k,
Guarding tests 10.2k, Contracts 6.4k chars mean; the Interior averages
171 chars), and the limiter cut the unprotected sections to *equal*
shares — a 300-test guard list and the neighborhood got the same room
regardless of which the unit needed. Max's two thoughts on reading it:
the next rung has a much larger window, and the harness context should
scale with the window rather than be a constant. Both are right; the
second is the harness's to build.

## Decision

- **`endpoint_window()`** (`run/parallel.py`) reads `max_model_len`
  from `GET /models` (vLLM reports it); a server that does not answers
  `None` with the reason, never a guess.
- **`brief_limit_for_window(window, share)`** = `share × window ×
  CHARS_PER_TOKEN`, with `CHARS_PER_TOKEN = 3.3` (measured: 55,553
  chars ↔ 16,750 tokens) and `BRIEF_WINDOW_SHARE = 0.35` — the rest of
  the window is the model's working memory. Both declared guesses,
  pinned in `run/agents.py`. At 32k that is 37,847 chars (down from
  60,000); at 128k, 151k.
- **`hobbes bench run --brief-limit`** defaults to **auto**: sized to
  the endpoint's window, `--brief-window-share` tunes the share, an
  explicit integer is the owner's call, `0` is no limit, and an
  unknown window falls back to the old 60,000 *saying so*. The
  resolution is printed in the banner and recorded in `run.json`
  (`brief_limit`, `brief_window`, `brief_reason`).
- **`limit_context` fills by priority** instead of equal shares:
  `CUT_PRIORITY` = Short-term context → Guarding tests → Neighborhood
  → Module docs; each section takes what it needs in that order from
  what the protected sections leave, **no single section more than
  `CUT_SECTION_MAX_SHARE` (0.6) of it**, so the guard list cannot
  starve the neighborhood. Protected sections (ADR-062) are unchanged;
  every cut is still stated; the limit is a guarantee (`len ≤ limit`).

## Consequences

- The harness context now scales with the rung: the same code sizes a
  7B brief at 32k and a 27B brief at whatever window it is served with.
- A smaller 7B brief means more room for the reads ADR-067 now forces
  — the pairing is deliberate, and `calls_saturated` (ADR-068) will
  say whether it was enough.
- The share and the priority order are guesses stated before the run
  (P11); the benchmark's error stream is what adjusts them (C-35's
  loop). C-45 amended.
- `hobbes run --brief-limit` (the non-benchmark path) keeps its
  explicit-or-none semantics; it has no endpoint to ask.

**Tests:** `TestWindowRelativeBrief` in `tests/test_run.py` (the limit
formula, priority fill + cap, `endpoint_window`). 851 pytest.
