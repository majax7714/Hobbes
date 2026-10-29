# ADR-183 — Every wall-clock cap is named where it bites

**Date:** 2026-10-28 · **Status:** accepted (Max, 2026-10-28: "good to go with the first 3", route 1 of the
speed and memory review) · **Owner:** Max · **Source:** the review of the pipeline's speed and memory
(2026-10-28): three read-only passes over the code and its timing logs, and a scip-clang probe in the image.

Registers **C-196**. Registers and lifts **C-197** the same day.

## What is missing

The ingest puts a wall-clock cap on every step that runs a helper, and no register entry names one:

| Where | Cap | What the user met |
|---|---|---|
| `tssource.run_helper` (lane A, TS/JS) | 300 s | `tsextract helper timed out on <repo>`; the ingest stops |
| `scip/index.mjs` `runStep` (each indexer step, in the container) | 600 s | `<bin> <arg> exited null: …`: the word *timeout* never appears, and the unit falls back to lane A |
| `containment.run` (each lane B unit's container) | 900 s; Java 1,800 s | `<step> timed out after Ns in its container` |
| `scipsource._fetch` (a registry fetch) | 600 s | the same words, as the fetch's failure |
| `scipsource.ts_zone_map` | 300 s | `tsextract zone map unavailable: …` |
| `scipsource.venv_environment` | 60 s | nothing; the listing is `None`, and only dependency coverage moves |
| scip-clang's worker wait (its own `--receive-timeout-seconds`) | 300 s per translation unit | **nothing** (C-197 below) |

The inner cap (600 s) sits under the container's (900 s; Java 1,800 s), so for a Java unit the inner one
fires first and says the least. dagger's Java unit is already measured at about 500 s.

Probe (2026-10-28, scip-clang 0.4.0 in `hobbes-session:local`, two translation units,
`--receive-timeout-seconds=0`): scip-clang logs `terminating worker N … due to worker timeout` on stderr,
prints `Finished indexing 0 translation units … num errored TUs: 2` on stdout, **exits 0**, and writes a
well-formed index of 150 bytes holding no document. The helper's per-unit count (`readUnitIndexes`) counts a
unit as indexed when its index is well-formed, so a unit scip-clang timed out or errored on was counted as
indexed. Its sites fell to lane A's fallback all the same, so no edge was wrong; what was missing was the
record that said they had.

## Decision

1. **One table.** Every cap above lives in `hobbes.extract.caps`, with its seconds and the step it bounds.
   `HOBBES_TIMEOUT_SCALE` (a positive number, default 1) multiplies every cap, so a user who meets one can
   raise it without editing code. Nothing about the scale is stamped: it moves the graph only where a cap
   fires, and a cap that fires is recorded.
2. **Every timeout says the same four things:** what ran out of time, the cap in seconds, C-196, and the
   knob. The words are made in one place for the Python side (`caps.timed_out`) and in one for the helper.
3. **The inner indexer cap follows the unit's.** The helper reads its step cap from the unit's config
   (`stepTimeoutSeconds`, `helperTimeoutSeconds` since the amendment below): the unit's cap less 30 s, so the helper's named error fires before podman kills
   the container. A step that times out carries `indexerExit`, so the Python side records it as the
   indexer's failure, never as a missing helper. This *raises* the inner cap from 600 s to 870 s (Java:
   1,770 s); a unit that used to time out at 600 s may now finish and draw.
4. **scip-clang's wait comes from the table too** (`clangUnitTimeoutSeconds`, 300 s × scale), passed as
   `--receive-timeout-seconds`. At scale 1 the argument is scip-clang's own default, so nothing moves.
5. **C-197: a unit counts as indexed only when scip-clang says it indexed.** Each per-unit run's output is
   written beside its index (`NNNN.log`) as well as passed through. `readUnitIndexes` reads scip-clang's
   summary line (`num errored TUs: K`) and counts a unit failed when K > 0, or when no summary line was
   written (scip-clang did not finish, so its count cannot be read). A whole-database run reads the same line
   from its own output. The record says how many of the failed units timed out (`due to worker timeout`).
   The index itself is decoded as before: a timed-out unit's holds no document, so nothing it draws moves.
6. **What does not change:** the TS/JS lane A helper still stops the ingest when it outruns its cap,
   rather than drawing a graph without TS/JS. Failing one zone at a time needs the helper run once per zone;
   that split is route 2's (the parallel lane A), and the C-196 entry names this as its residual. C-150 (the
   Python side killed by the kernel, with no record) is not touched: it stays parked on Max's word.

## Determinism

A wall-clock cap makes the graph depend on the box: the same commit can draw a unit on a fast machine and
fall back to lane A on a slow one. That was already true and unnamed; C-196 names it, and the record that a
cap fired is what lets two graphs be told apart. At scale 1, no cap's seconds move except the inner
indexer cap's (decision 3).

## Predicted

On every standing cell, nothing drawn moves: no cap fires on any of them. The index cache misses once for
every lane B unit, because the helper and its config change. The degraded records change only where a cap
fires or a scip-clang unit errored.

## Measured

Built 2026-10-28 (0.3.1-beta). Arms in `~/.hobbes/bench/caps-adr183-2026-10-28/` (`arms.sh`,
`fmt-repeat.sh`): each cell ingested by a worktree of `main` at `71a28c3` (before) and by the branch
(after), one pass at a time, every lane B unit indexed fresh in both.

- **cJSON (C), toml (Go), jsoup (Java):** `graph.json`, `tests.json` and `interfaces.json` are identical but
  for `built_by` (the checkout's path and its dirty flag).
- **fmt (C++):** the same, but for one tail site in `test/xchar-test.cc` (`external` 51/50 against
  `builtin-name` 4/5). Three runs of each arm with the index cache off: it flips *within* each arm
  (before 51, 50, 51; after 50, 51, 50), and everything else is identical across all six. That is C-149's
  registered residual (scip-clang records a few external type references inconsistently), not this change.
- **The real scip-clang, the new per-unit shell, in the image** (two units): at a 0 s wait, 2 of 2 counted
  failed and timed out (`units_failed` 0 before C-197's fix); at 5 s, 0 of 2.
- Suites: pytest green, `lane_b` 29 of 29 on the host (4 of them run scip-clang), scip node 102 of 102.

As predicted, nothing drawn moved, and no cap fired on any cell.

## Amended 2026-10-29 (0.3.4-beta): the review of PR #4

The review of this ADR's PR found the places where a cap still went unnamed, or fired in the wrong place:

- **Decision 3, amended: one budget for the helper's steps, not one cap per step.** A C build root runs a
  build step (CMake, bear over make) and then the index step. With 870 s each, a 500 s build left podman's
  900 s cap to kill the index step, and the record was the container's generic timeout, not the step's. The
  config's key is now `helperTimeoutSeconds`: the unit's cap less 30 s, for all the plan's steps together.
  Each step gets what is left of it, and a step that starts with less than a second left is stopped before
  it runs. The timeout names the budget: "… did not finish within the helper's N s cap on its steps".
- **A step says what it runs.** The shell-driven steps (scip-clang over the units, bear over make, the
  Gradle build) carry a label. Before, a timeout or a failure read `sh -c …`.
- **A step killed by a signal says so.** A step stopped by a signal with no exit code read "exited null",
  the shape decision 3 fixed for timeouts. It now names the signal, and SIGKILL names the OOM killer or the
  container's memory limit (C-150). Output past the helper's 64 MB buffer is named too.
- **A run whose units met the `clang-unit` cap is not stored in the index cache.** The key holds the caps,
  not how busy the box was, so a hit would replay a timeout a loaded box caused on an idle one. The facts now
  carry `units_timed_out`, and the ingest stores nothing when it is above zero. (A venv listing that timed
  out needs no such rule: its empty listing is in the key, so a listing that succeeds later misses.)
- **Decision 5, refined.** A unit whose index is readable but whose run wrote no summary is now *uncounted*,
  not failed. What its index holds is drawn, and the record says that whether it indexed whole cannot be
  read. Before, the record said its sites fell to lane A, though lane B drew whatever it held. A root whose
  every unit failed says the root has no lane B answer, not "the others stand". A timeout count is named
  even when no summary was written.
- **podman's own probes are in the table** (`podman-probe`, 60 s: whether the image is built, and its id).
  A probe past its cap refuses containment for the run, as before, and now says the cap, C-196 and the knob.
- **Registered, not fixed: an uncontained step's children can outlive its cap.** When the helper stops a
  step at its cap, it signals only the step's own process. In a container the rest end with the container.
  On the host (no container runtime, or the escape hatch), a C index step's `xargs` and scip-clang runs keep
  going until they finish. Killing the process group needs the step detached, and a detached step no longer
  receives the terminal's Ctrl-C, which trades one stray process for another. Nothing they write is read:
  the helper has already removed their directory. Recorded in C-196.

Tests: scip node 105 (3 new: the budget across steps, a signal, a root with no unit indexed), pytest
`test_caps.py` 25 (the cache store, the podman probe).
