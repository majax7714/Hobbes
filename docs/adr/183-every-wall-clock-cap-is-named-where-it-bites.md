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
   (`stepTimeoutSeconds`): the unit's cap less 30 s, so the helper's named error fires before podman kills
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
