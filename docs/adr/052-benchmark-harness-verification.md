# ADR-052 — Verification by benchmark harness; hypotheses preregistered

**Date:** 2026-08-19
**Status:** accepted (direction and preregistration only — no run is
started by this ADR)
**Amends:** `docs/hobbes-architecture.md` ("Where this is going"; §8's
derivation-programme status)

## Context

D1 (ADR-051) built the plan derivation, and C-35 says plainly that its
quality is a number nothing has measured. Dogfooding and the sanctioned
repos verify *mechanisms* — they cannot produce a solve-rate curve, a
cost curve, or a large comparison pool. Max's direction (2026-08-19):
verify a large part of Hobbes by **using it as a harness under known
benchmarks** — the errors it produces become the adjustment signal, and
known benchmarks supply a large pure-model baseline pool. Testing is
deliberately **not** introduced today; what is introduced is the
discipline around it.

## Decision

1. **The verification method for the derivation programme is a
   benchmark harness**: benchmark instance in → `ingest` → `plan` →
   per-unit sandboxed execution → verify → patch out, compared against
   the same models run pure on the same instances. End-to-end runs
   require D2 (nothing consumes a change-spec yet); that dependency is
   stated, not worked around.
2. **Hypotheses are preregistered before any run**, in
   [`benchmark-hypotheses.md`](../benchmark-hypotheses.md), each with
   the metric that decides it and what falsifies it:
   - **H1** — derived context substitutes for model size: harnessed
     smaller models perform to the degree of, if not better than,
     larger pure models.
   - **H2** — depth stops costing accuracy: per-unit regenerated
     context flattens the accuracy-vs-depth curve that accumulating
     context produces.
   - **H3** — cheaper and quicker as a byproduct: fewer tokens
     consumed and produced per *solved* instance, at equal or better
     solve rate — with the multi-unit coordination counter-pressure
     stated up front.
3. **Results land in that document beside their hypothesis**, dated,
   naming benchmark, instance set, models, and numbers — the
   `extraction-evidence.md` pattern. P11 scopes every claim to its
   sample: a result on one benchmark licenses that benchmark's shape.

Why preregistration is the load-bearing part: a hypothesis written
after the results can be re-scoped to fit them. Writing the falsifiers
first is the same honesty mechanism as the register — the system's
claims about itself are constrained before the evidence exists, so the
evidence can actually bear on them. "Under the current build this
should arguably be the case. however that is what testing is for"
(Max) is the doc's stance line, verbatim.

## Consequences

- The architecture's "Where this is going" names the verification
  path, and §8's derivation-programme status carries the benchmark
  milestone as *preregistered, not started* — it opens only when Max
  names it, after D1's review, and end-to-end only after D2.
- The benchmark error stream is the planned data source for C-35's
  loss loop (agent-mapping §6): rework, contract failures, and
  context-fault rates per instance are exactly the terms the recorder
  milestone defines.
- Predicted first friction is C-36 (prose issues, lexical seeds); the
  miss rate on real instances is itself a number to record, and the
  parked generative seed layer is the expected response.
- No new constraints: nothing here concedes information — it schedules
  the measurement of concessions already registered (C-35, C-36).
