# ADR-063 — Implementers run in waves over the contract DAG; parallelism is gated on a batching endpoint

**Date:** 2026-08-22
**Status:** accepted — built at the owner's direction ("shouldn't mess
with anything except increase speed; note it as a vLLM restriction, or
fall back when vLLM isn't present").
**Amends:** `docs/hobbes-architecture.md` (§6, staged execution — "one
alive at a time" becomes "one *wave* at a time"); `docs/constraints.md`
(**C-51**); `docs/harness-restructure-plan.md` (parallel implementers
leave "deliberately not in this plan").

## Context

Measured on the phase-4 probe (2026-08-22): every implementer's
`wall_seconds` equals its loop `duration_ms` to within a second — the
harness's own per-unit overhead (podman start, `--local` clone, artifact
copy, harvest, scoped integration) is **~1 s**. Of the loop's time,
**85–90 % is the model decoding** at ~28 tok/s (the Modal 7B answers a
short prompt in 2.5 s, prefills 30k tokens in 12.9 s cold / 1.1 s with
the prefix cache, and emits 512 tokens in 20 s). Ten units one after
another is therefore ten serial decode streams against an engine that
batches — vLLM on the rung's single A10G, `max_inputs=32` on the Modal
side — while nine of them, under ADR-062, say "nothing named is mine"
in two turns. The implement stage ran 1,523–2,148 s per instance; plan
and verify ran ~10 s each.

The sequential order existed for one guarantee: a **consumer starts at
the integration head that already holds its owner's commit**
(ADR-059). Units with no contract between them were never promised each
other's commits — contracts are the only interface between units
(architecture §6) — so running them together concedes nothing the
design relied on. ADR-061's scoped cut makes concurrent units unable to
clobber each other even when they stray.

## Decision

1. **Waves over the contract DAG.** `run/parallel.py` derives
   `unit → owners it consumes from` (the same edges `order_units` sorts
   by). The implement stage keeps a pool of `workers` sessions: every
   pending unit whose owners are integrated may start, in plan order;
   each finishes on the orchestrator's thread — harvest, fold-back,
   scoped integration are **serial** — and may free the next wave. A
   cycle is broken as `order_units` breaks it (first pending by order).
   Human-first units count as done for their consumers. `workers == 1`
   is exactly the previous chained order.
2. **Integration is against the merge-base, not the tip.** A parallel
   unit's clone is older than the target by the time it lands;
   `_integrate_one` diffs from `merge-base(target, branch)` so a
   neighbour's landed change never reads as this unit's (reverse)
   edit or as a drop. The scoped patch touches only the unit's own
   files, so it applies onto the advanced tip; a failure is a real
   conflict at the cut — two units guarded by the **same test file**
   both editing it is the one way that happens, and it is recorded
   under `integration.failed`, not merged.
3. **Gated on an endpoint that batches.** `hobbes bench run --parallel
   auto` (default) asks the endpoint's `/models` for `owned_by`; `vllm`
   → `DEFAULT_WORKERS` (4); anything else, or no answer, → sequential
   with the reason printed in the banner and written to the run
   manifest. An integer is the owner's call and is not second-guessed.
   `hobbes run --from-proposal --parallel N` defaults to 1.
4. **The clock is measured from outside.** The record carries
   `implement_wall_seconds` (stage start → end) and `parallel.waves`;
   the bench's `stage_wall.implement` is that clock and
   `implement_units_sum` keeps the per-unit sum, so H3 reads wall time
   as the wall saw it and token totals are unchanged.

## Consequences

- Expected: the implement stage falls toward the longest *chain* of
  dependent units rather than the sum of all units. Real concurrency on
  the 7B rung is bounded by the A10G's KV budget for 32k contexts;
  `DEFAULT_WORKERS = 4` is a declared guess, to be read off
  `implement_wall_seconds` vs `implement_units_sum` on the next run.
- A unit no longer sees commits from units it has no contract with
  (**C-51**). Under the architecture that was never promised, but the
  sequential run delivered it incidentally; a unit that *relied* on a
  non-contract neighbour's edit now sees the base instead, and a
  verifier failure is where that shows.
- The pure arm is untouched; both arms still differ in Hobbes and
  nothing else. Parallelism applies only to the staged harness arm and
  `hobbes run --from-proposal`; the per-unit `hobbes run <task>` path
  (ADR-054) stays sequential.
- Tests: `tests/test_parallel.py` — endpoint check against a local
  stand-in (vLLM / other / unreachable), DAG readiness and the cycle
  case, and a 3-worker staged run asserting the same merged set and
  integration diff as the sequential run, every owner in an earlier
  wave than its consumer, and the outside clock ≤ the units' sum.
