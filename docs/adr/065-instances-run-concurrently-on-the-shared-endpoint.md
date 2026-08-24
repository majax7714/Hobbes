# ADR-065 — Instances run concurrently on the shared endpoint

**Date:** 2026-08-22
**Status:** accepted — Max's call ("since we're using Modal and not a
physical box, can we run all 5 in parallel and review by finishing
time"). Built with the honest caveat stated below.
**Amends:** `docs/hobbes-architecture.md` (§7, the harness); no new
constraint (this is a scheduler change, not a concession).

## Context

`hobbes bench run` ran instances one at a time. On the 7B ladder the
model is served from Modal (vLLM, `@modal.concurrent(max_inputs=32)`) —
not a single local box — so nothing about one instance's session ties
up the endpoint the way a local GPU would. The harness arm is
I/O-bound on the endpoint's decode (ADR-063 measured ~85–90 % of a
unit's wall as one decode stream), and the endpoint can batch many
streams. Running instances sequentially left that batching unused: five
instances waited in line for a server that could take them together.

## Decision

`hobbes bench run --instance-workers N` (default 1) runs up to N
instances concurrently in a thread pool. Each instance runs end to end
on its own thread — pull image, checkout, both arms, append record — so
finished instances land as they complete ("queue by finishing time").
Beneath each, the intra-instance unit pool (ADR-063) still runs, so
peak concurrency is `instance_workers × workers` requests against the
endpoint (5 × 4 = 20 for the complex set, under Modal's 32).

Two correctness points:

- **Session dirs are namespaced per instance.** Session names derive
  from the proposal hash; two instances that shared a proposal would
  collide under a pool, so each instance gets `sessions_root/<id>/`.
- **Record appends are locked** and one instance's failure is caught
  and logged, not allowed to sink the pool — the run stays resumable,
  so a re-run picks up any instance the pool dropped.

## Consequences

- **The speedup is endpoint-throughput-bound, not N×.** All instances
  hit one A10G; vLLM batches concurrent sequences up to its KV budget
  for 32k contexts, then preempts and recomputes. Aggregate throughput
  rises sublinearly — expect ~2–3× on five instances, not 5×. The wins
  are real (overlapped I/O, one server kept busy) but the GPU is the
  ceiling; more instance workers past the KV limit trade latency for
  no throughput.
- Local resources bound the other side: each instance runs its own
  swebench container(s), so peak container count is
  `instance_workers × (concurrent units)`. On the box (12 cores, ~19 GB
  free) five instances are comfortable; a larger fan-out would need the
  RAM checked first.
- `--instance-workers 1` is byte-for-byte the old sequential path.
- Test: `test_instance_workers_run_concurrently_with_the_same_records`
  — three instances, both arms, pooled; identical records to the
  sequential run, all six patches written, the JSONL intact under
  concurrent appends.
