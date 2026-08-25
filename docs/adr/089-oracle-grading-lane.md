# ADR-089 — An oracle-grading lane for the call graph, and its build decisions

**Date:** 2026-08-25 · **Status:** proposed — awaiting Max's decisions on D-O1–D-O6 · **Owner:** Max · **Design:** `docs/oracle-grading.md`

## Context

Every correctness number Hobbes has for its call graph is a small
self-selected hand-check (n=20–33, all 100%, 95% lower bound ~83–89%) or
lane agreement (two of our own methods agreeing). The largest measurement
(dagger, 161k edges) has zero graded edges. Hobbes has never had a recall
number of any kind. The bench needs an answer key it does not control.

## Decision

Add an **oracle-grading lane** to the bench tooling — no product change.
An oracle is independent of Hobbes, grounded in the language's own
authority, and regenerable by anyone with the toolchain (resolution,
reachability, or runtime-trace kinds; peer static analyzers never
qualify). Phase 1 grades Go (RTA) and TypeScript (`tsc`) on the cells
O1–O4; phase 2 (designed, not gated on phase 1) adds Python runtime
traces and a Rust MIR oracle. Metrics, bucket semantics, the four
reporting rules, the trace-asymmetry rule, and the triage protocol are
as `docs/oracle-grading.md` §3, §3.1, §8 state; they become `C-n`
entries when the lane lands.

## The six build decisions

Each is recorded here with the design's recommendation. **None is taken
until Max marks it.** Status column: *proposed* → *decided (date)*.

| # | Decision | Recommendation | Status |
|---|---|---|---|
| D-O1 | Go algorithm | RTA now; VTA as an optional second arm on O2 only, to price the choice | proposed |
| D-O2 | Harness home | `bench/oracle/` as its own module(s), product stays pure; not a `hobbes oracle` subcommand | proposed |
| D-O3 | Dispatch and external scoring | Multi-target oracle sites: Hobbes' target confirmed on set membership; recall counts every oracle pair. External targets out of the in-repo recall denominator, external-confirmation rate reported separately | proposed |
| D-O4 | Position/overload conventions | Declaration position = identifier start, 1-based line; overload = set membership. Written as normative in the harness README; both product lanes measured against them | proposed |
| D-O5 | Python trace mechanics (phase 2) | `sys.monitoring` at site grain; the repo's own test suite; module-body calls in/out decided once at O6 | proposed |
| D-O6 | Rust path (phase 2) | MIR resolution oracle first; Rupta as a time-boxed reference lane, dropped without ceremony if the nightly pin fights | proposed |

## Gates

- O1 does not start until D-O1–D-O4 are decided.
- Pre-registration (design §10) is its own commit before O2 runs.
- Every cell's evidence row lands in `extraction-evidence.md` in the same
  commit as the run; §3.8 gains only what the run licenses (P11).
- Phase 1 exits for Max's review at O4 (design §14).

## Consequences

- The evidence file gains a new kind of Verified content
  ("compiler-graded", "trace-graded"), never to be read as hand-checked.
- Recall is reported per cell with its root count or coverage line and is
  never pooled — a rule the register will carry.
- Rerunning a cell must be one command, cheap enough to follow every
  resolver change; the O2 cell becomes a standing post-change check.
- The O1 fixture `twomod` (two Go modules) does not exist yet and is part
  of O1's scope.
