# ADR-081 — Three instruments for C-56: the familiarity probe, the observation-shaped aid, the solution-shape diff

**Date:** 2026-08-22 · **Status:** accepted (built; first use on the httpx
re-run) · **Realises:** C-56's candidate instruments. Relates to C-39,
ADR-078..080.

## Context

C-56: the pure arm mixes repo recall with reasoning, and the aided arm's
prompt is off-distribution, so a pure-vs-aided table is not a like-for-like.
Max's call was to stop the spans re-run three minutes in and apply the
candidates first, so the next pair is read with them in hand.

## Decision

1. **Familiarity probe** — `scripts/deepswe_familiarity.py`. No tools;
   the model is asked to reproduce K functions of the ingested repo
   verbatim (the task's named symbols first, then the longest functions,
   deterministic) and is scored against the checkout: exact match,
   difflib line ratio, verbatim-line fraction, `UNKNOWN` count. The summary
   line is the caveat column beside every pure score for that
   (model, repo) — C-39's xarray check made routine at the repo grain.
2. **Observation-shaped aid** — `hobbesmini` 0.3.0,
   `agent.hobbes_context_shape: observation`. The aid template wraps the
   aid in `<<<HOBBES_CONTEXT>>>…<<<END_HOBBES_CONTEXT>>>`; the agent strips
   it from the task and re-inserts it as the agent's **own first tool
   exchange** — an assistant turn calling `hobbes context --task .` and its
   tool result carrying the aid (native tool-call messages, or mini's
   text-based action format). Same bytes, in-distribution shape. `prompt`
   keeps the old placement with the markers stripped; the shape used is
   recorded in `model_stats.hobbes_context_shape`. The baseline arm is
   untouched (no markers → nothing happens).
3. **Solution-shape diff** — `scripts/deepswe_solution_shape.py`: pairwise
   difflib ratio and verbatim non-trivial-line overlap between patches and
   reference implementations. First reading, on the ADR-080 pair:
   baseline↔hobbes 0.16 ratio / 0.10–0.12 line overlap; either vs
   `requests_toolbelt.multipart.decoder` and `email.feedparser` ≤ 0.06 /
   ≤ 0.002 — two independent constructions, no library recall.

## Consequences

- Every results table from here carries the familiarity line and the
  aid shape; the spans re-run is superseded by the observation-shaped
  re-run (`-obs`) on the same task.
- The observation shape is a new variable in its own right: if `-obs`
  diverges from the prompt-shaped ADR-080 pair on the read-volume metric,
  the shape mattered — which is the C-56 test, not a Hobbes result.
- Not addressed: recall the familiarity probe cannot see (idioms,
  layout), and the cost of one extra synthetic turn in the aided arm's
  context (~1.7 k chars).
