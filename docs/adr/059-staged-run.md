# ADR-059 — The staged run: single-use derived-context agents, one at a time, job = short memory

**Date:** 2026-08-22
**Status:** accepted — built (phases 2–3 of the harness restructure,
`docs/harness-restructure-plan.md`), exercised by the stand-in session;
no live benchmark run yet.
**Amends:** `docs/hobbes-architecture.md` (§6.1 gains the staged
execution); `docs/agent-mapping.md` (the phases §2 named are now the
run's stages); `docs/constraints/README.md` (C-47, C-48); `docs/future_additions.md`
(the D2 remainder shrinks).

## Context

The first live benchmark run's harness patches overlapped the gold
files in **zero** places on both astropy instances (the restructure
plan records the trace). The lexical seeds (C-36) made the impact set
the whole repository and the unit cap fused it into one unit. Phase 0
fixed the seeding's worst cases deterministically and made the cap
*select* rather than merge; phase 1 made `planner`/`reviewer`/`verifier`
first-class read-only roles. This ADR is phase 2: the execution shape
the owner named (2026-08-21).

> the structure is still single use agents. it is just single use
> **derived context** agents… sandbox is spawned with role specific
> policy that is then fed its roles context which is a combination of
> its standing and short memory. were not having 10 agents sit in a
> room and look at eachothers work. were having one do its job then
> send to the next. the job is the short memory. — Max

## Decision

`hobbes run --from-proposal "<text>"` (and the bench harness arm with
`--stages`) runs a proposal through **stages**, one single-use session
alive at a time, each agent's job arriving as its short-term memory
(`inbox.jsonl`) — the previous agent's **handoff**. The stages
(`pipeline/src/hobbes/run/stages.py`):

1. **plan** — a `planner` session (read-only worktree) reads the repo
   under a graph-derived **standing** context (the module map, the
   capture line, the blind-spot denominator — not the source) and
   hands off the files, symbols and tests the change touches. This is
   the generative layer C-36 always said would sit *above* the lexical
   seeds, never inside them (P5): the handoff's files/symbols resolve
   **tolerantly** to seeds (`impact.resolve_terms` — a miss is
   recorded, never raised or guessed).
2. **(derive)** — `hobbes plan` runs deterministically on the
   planner's seeds. `seed_source` records `planner`, or
   `lexical-fallback` when the planner resolved nothing (the run never
   fails for a rambling planner — the deterministic seeds stand and
   the record says so), or `explicit`.
3. **review** (opt-in) — a `reviewer` session judges the change-spec;
   its `verdict` (`approve`/`amend`) is recorded.
4. **implement** — one `implementer` per unit, in contract order, each
   session cloned at the **current** `hobbes/<task>` head (passed as
   the head **commit**, since a `--local` clone exposes other branches
   only as `origin/*`) so a consumer sees its owner's commit; the
   branch is integrated **immediately** after harvest, a conflict
   recorded at the cut. The planner's handoff is the first message in
   every implementer's inbox.
5. **verify** — a `verifier` session (read-only, at the integrated
   head) runs the planner's named tests through `exec` and hands off
   `pass`/`fail`. A failure whose cause is the read-only mount
   (`Read-only file system`/EROFS) is reclassified `verifier-env` — the
   harness's limit, not a real fail (C-48).
6. **rework** (opt-in) — on `fail`, one implementer redoes the unit(s)
   the verifier named (inbox = the verifier's handoff), then verify
   once more. Bounded by `--max-rework` (default 1).

A **handoff** is one reflection sent with `kind: handoff`
(ADR-054's `reflect` gained the kind in phase 0); `run.handoff.parse`
reads the fixed shape (`files:`, `symbols:`, `tests:`, `approach:`,
`risks:`, `verdict:`, `units:`, `reason:`) tolerantly — bullets,
backticks, quotes, a JSON object — and never infers a file that was
not named. A `verdict` found only in prose is marked `inferred`, not
asserted.

## What this is and is not

- **Still single-use agents.** Each session is started once and ends
  with the stage; the only shared state between them is the pinned
  contracts and the handoffs — no agent reads another's transcript
  (agent-mapping §8). "One does its job then sends to the next" is the
  inbox; "some agents' whole job is to feed the next" is the planner
  and the verifier.
- **Agent count is still the partition's output.** The planner's seeds
  feed the same D1 partition; the implementer count is what the
  partition yields under those seeds, capped by `--max-units` with the
  lowest-impact units deferred (C-44).
- **Not parallel.** Sessions run one at a time, in contract order —
  the owner's "only if the flow makes sense" is deferred; parallel
  implementers are a scheduler change over the same chained-worktree
  mechanism, parked in `future_additions.md`.
- **Not a new sandbox boundary.** The stages reuse `hobbes-session`,
  the policy chain, the proxy and the mounts unchanged; a read-only
  role's worktree is ro and runs python with bytecode writes off
  (phase 1).

## Consequences

- `hobbes run` gains `--from-proposal`, `--stages`, `--max-units`; the
  per-unit path (`hobbes run <task>`) is unchanged. `hobbes bench run
  --stages` selects the staged harness arm; without it the per-unit
  arm runs as before.
- The partition record gains `stages` (each with role, session, exit,
  handoff, verdict + `verdict_source`), `seed_source`,
  `planner_unresolved`, `units_deferred`, `verify` and `rework`. The
  harness record's `detail` carries the same — the error stream
  ADR-052 asked for, one layer richer.
- **C-47** registered (surfaced): the planner's seeds are a model
  opinion, so a staged change-spec is not byte-reproducible; the spec
  records the seeds and `seed_source`, and the deterministic fallback
  is always available.
- **C-48** registered (surfaced): the verifier reads a ro worktree and
  has no shell but `exec`, so it cannot write a fresh repro script and
  a ro-mount test failure is the harness's; both are stated in the
  verifier's brief and the `verifier-env` classification.
- Tests: pytest +7 (`test_run.py::TestStagedRun` ×4 driving the staged
  loop with a role-aware stand-in — planner seeds drive the plan,
  lexical fallback, rework on a verifier fail, dry run; and
  `TestHandoffParsing` ×3), plus the handoff parser's own cases. Go
  unchanged from phase 1. 815 pytest / Go green.
- **Phase 3 (2026-08-22, the harness adapter) amends this ADR.** Every
  stage — implementers included — is now an entry in the stage log
  with a wall time measured around the spawn and its own session log
  (a per-session copy, since a rework reuses the unit's agent dir);
  the bench record sums every stage's meter and carries `seed_source`,
  per-stage wall times and the planner's named files; `results.py`
  scores `planner_files ∩ gold_files` post hoc from the gold patch no
  session saw, and `hobbes bench report` splits the staged harness by
  `seed_source` with the planner hit-rate beside the solve rate
  (**C-49**: a proxy against one solution). Building the adapter found
  a phase-2 bug: `_integrate_one` ran `git branch -f target HEAD` in
  the repo (whose HEAD is the user's checkout) instead of the detached
  worktree, so the integration branch never advanced — `merged` was
  recorded, chained implementers started at base, and the verifier
  verified base. Fixed and pinned by a diff assertion in the staged-run
  test. 818 pytest / Go green.
- No live run. The first staged run is the restructure plan's phase 4:
  planner-only on the two astropy instances first, checking the
  planner's files against gold, before the 45-set.
