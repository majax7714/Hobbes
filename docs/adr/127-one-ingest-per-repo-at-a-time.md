# ADR-127 — One ingest of a repo at a time

**Date:** 2026-09-17 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-17 ("handle the two ingests of one repo issue, or if no solution doc as a constraint"); found by use the same day (the 2026-09-17 BUILDLOG entry, the duplicate dispatch).

Amends architecture **§3.6**. Changes no artifact's content.

## Context

On 2026-09-17 a chained shell command ran two `hobbes ingest`s of this
repo at once. The graph the second one left had several lane B units
failed with "wrote no facts file", each recorded in
`extraction_errors`. Nothing refused the second ingest, and nothing
said the two had met.

The mechanism, read from the tree:
- **The stage is shared by construction.** `staging.stage_path` is
  derived from the resolved repo root, the SHA and the staged files'
  stats (it is deterministic so removal is idempotent, ADR-027). Two
  ingests of one repo at one commit stage every unit at the same path.
  `build_stage` removes the `.partial` and the final tree before it
  builds, and each unit's run removes the stage when it is done. Either
  run deletes the tree the other is copying into or indexing, so the
  helper writes no facts file.
- **The artifacts are written in place.** `emit.write_artifacts` writes
  `graph.json`, `tests.json` and `interfaces.json` one after another
  with `write_text`. Two writers can interleave (a `graph.json` from one
  run beside a `tests.json` from the other), and a reader — the
  knowledge server, `hobbes review` — can read a half-written file.

The index cache (ADR-122) already stores by `.partial` + rename, and a
worktree of the same repo has its own root, stage and `derived/`, so
neither needs anything here.

## Decision

**1. An ingest holds an exclusive lock on its repo, and a second one is
refused, not queued.**
- The lock file is `.hobbes/derived/.ingest.lock` under the resolved
  repo root. It is gitignored in both postures (ADR-012), it is the same
  file for every path that resolves to the repo (a symlink, a relative
  path), and it does not depend on `HOBBES_CACHE_DIR` or `$HOME`, which
  two processes may set differently.
- `fcntl.flock(LOCK_EX | LOCK_NB)`, taken first in `extract.ingest()`
  and held until the artifacts are written. The kernel drops it when
  the process exits, however it exits, so there is no stale lock to
  clear. The holder writes its pid into the file for the message.
- Contention raises `IngestBusy` (its own type, P10), naming the repo
  and the holder's pid. `hobbes ingest` (and `hobbes up`, through it)
  prints it and exits 1 **before** anything is staged, indexed or
  written. Refusing, not waiting: a wait would hang a CI job or a
  dispatch's pre-ingest silently behind a run nobody knows about.
- Every caller of `ingest()` gets it (the CLI, `hobbes up`,
  `bench/arms.py`); nothing calls `extract_repo` to write artifacts
  outside it.

**2. Artifacts are written atomically.** Each file is written to a
sibling temporary name in `derived/` and `os.replace`d over the target.
A reader sees the old file or the new one, never part of either. Bytes
are unchanged (P1).

**3. Where the lock cannot be taken, say so and go on.** A filesystem
without `flock` support (`OSError` other than contention) is not a
reason to refuse every ingest. The run proceeds unlocked and prints a
warning naming **C-159**.

## Consequences

- Two ingests of one repo can no longer break each other when both are
  this version or later; the second exits 1 with a message that names
  the first.
- **C-159 registered (surfaced)**, the residuals: an ingest by a Hobbes
  build before 0.2.39-beta takes no lock, and a filesystem without
  `flock` runs unlocked (the warning). Neither is detected across the
  two processes beyond that.
- The order of writes across the three files is not a transaction: a
  process killed between two replaces leaves a `graph.json` from the new
  run beside a `tests.json` from the old. Over an unchanged tree the two
  runs write the same bytes (P1); over a changed one the files' stamps
  differ, and nothing compares them today. Not addressed here.
- Version: 0.2.39-beta (what the layer refuses).

## Alternatives considered

- **Wait for the lock (`LOCK_EX` blocking).** Rejected: a silent hang,
  and a waiting run re-does work the first just finished.
- **A per-process stage path (pid or random in the key).** Rejected as
  the fix: it stops the lane B collision but leaves the artifact race,
  and it gives up the idempotent removal ADR-027 relies on.
- **The lock under the Hobbes cache root.** Rejected: two processes with
  different `HOBBES_CACHE_DIR` would take different locks and still
  share `derived/`.
- **A constraint entry only.** Rejected: the fix is small and the
  failure is a wrong graph written without a refusal.
