# ADR-080 — Commit-on-exit rides into the referenced harness too

**Date:** 2026-08-22 · **Status:** accepted · **Relates to:** ADR-058 (our
harness's `--commit-on-exit`), ADR-078/079 (DeepSWE on Pier, the repeat
guard), C-46.

## Context

The first 27B pair on Pier (`httpx-multipart-response-parsing`, native
tool calls, repeat guard on) ended **both arms with a complete
implementation in the working tree and an empty patch**:

- baseline — 65 calls, parser + `iter_multipart`/`aiter_multipart` + a
  new test file + docs + CHANGELOG, ruff/mypy clean; spent its last turns
  on two full-suite runs (`timeout 900 pytest tests/`) and hit Pier's
  90-minute `AgentTimeoutError` before committing.
- hobbes — 73 calls, the same shape; `git add -A` was its last action and
  the next completion was a 131 k-window `ContextWindowExceededError`.

DeepSWE's collect hook is `git diff --binary <base> HEAD`: only commits
count. The 7B never reached this wall; the 27B does real work and reaches
it on the first task. It is the exact failure ADR-058 fixed in our own
harness ("the 7B edited but never committed — commit-only harvest saw
nothing"), now in the referenced one.

## Decision

1. **`hobbesmini.RepeatGuardAgent.run()` commits on exit.** Whatever ends
   mini's loop — submission, `LimitsExceeded`, a context-window 400, a
   format error — a `finally` runs `git add -A && git commit` in `/app`
   with a fixed identity and the exit status in the message, and records
   `COMMITTED` / `NOTHING_TO_COMMIT` / the failure as
   `model_stats.commit_on_exit` in the trajectory. The reason is sanitised
   to `[A-Za-z0-9_-]` before it enters the command. Both arms, like the
   guard: hygiene, not context. A hard kill from outside (Pier's agent
   timeout) cannot be caught — hence 2.
2. **Agent timeout ×2** (`--agent-timeout-multiplier 2`, `TIMEOUT_MULT` in
   `deepswe_run_arm.sh`): DeepSWE's 5 400 s assumes a faster model than a
   27B decoding at ~30 tok/s on one A100; the baseline was finishing, not
   looping, when it was killed.
3. **Still not ported: window-fit.** The Hobbes arm filled 131 k tokens in
   73 calls because mini keeps every observation (full `git diff` outputs
   included) and never elides. C-46's elision remains a second variable we
   do not add; the 27B's window is the lever if this recurs.

## Consequences

- A run that ends in `ContextWindowExceededError` now still hands the
  verifier its work; the exit status and `commit_on_exit` together say
  whether the patch is a finished submission or a cut-off one.
- The two lost 27B implementations are not recoverable (Pier removes the
  container; only the trajectories' echoed diffs remain). `--no-delete`
  is the knob if a future read needs the tree.
- hobbesmini is 0.2.0; the wheel URL in the runner follows the version.
