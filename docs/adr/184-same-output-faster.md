# ADR-184 — Same output, faster: the byte-identity gate and the first three levers

**Date:** 2026-10-28 · **Status:** accepted (Max, 2026-10-28: "good to go with the first 3", route 2 of the
speed and memory review) · **Owner:** Max · **Source:** the review of the pipeline's speed and memory
(2026-10-28) and the measurements below, in `~/.hobbes/bench/speed-route2-2026-10-28/`.

## The rule this rests on

A change that makes the ingest faster or lighter **and leaves every artifact byte-identical** draws,
refuses and says nothing new. It needs no regrade and no tier question, and it carries no version bump of
its own (ADR-103 moves the patch for a change to what the layer draws, refuses or says). Byte-identity is
its whole proof, so it is checked, not argued:

- **The gate** is `bench/identity/`: each cell is ingested by a checkout before the change and by one
  after it, one pass at a time, with the index cache off in both (a fresh index is what a version bump
  sees). The three artifacts must be identical but for `built_by`. A registered nondeterminism (C-149's fmt
  tail site) is shown by running the *before* arm twice, never assumed.
- **The cells** span the lanes: this repo at a fixed commit (Python, TS/JS at scale, Go, Rust, Java, C,
  C++), cJSON, fmt, toml, jsoup, memchr, click and zod.
- A lever that cannot pass the gate is not a speed change; it is a draw change, and it goes through its
  own ADR.

## Measured (this repo at `71a28c3`, 0.3.0-beta, warm lane B: 130.5 s, 3.49 GB peak)

- **Lane A TS, 99.5 s:** 27 tsconfig zones, run one after another in one Node process. The largest is
  22.7 s (`tui/opencode/packages/core`, 758 files), and the zones sum to 99.1 s. The helper's peak RSS is
  3.5 GB, which is also the ingest's peak: GNU time's figure is the largest process's.
- **Python parse, 12.1 s:** tree-sitter's own parse is 0.51 s of it (447 files, 7.0 MB). The rest is
  pysource's walks. `_own_body` (a definition's own body, stopping at nested scopes) is called 12.0
  million times for 447 files: about a dozen callers each re-walk the same body.
- **Lane B, cold:** one language after another, one unit after another; TS 122 s and Python 44 s here,
  Java about 500 s on dagger.

## Decision: the levers, in the order they land

1. **pysource walks a definition's own body once per parse.** `_own_body` is memoized per parse, keyed by
   the node's byte span and type, and returns the same nodes in the same order. Every caller reads it
   unchanged.
2. **Lane A TS runs its zones on worker threads.** The helper hands each zone to a pool of
   `worker_threads` (`HOBBES_TS_JOBS`, default `min(4, cores / 2)`). The main thread merges and sorts
   exactly as it does today, so the facts are the same bytes. Each zone has its own cap (`tsextract-zone`,
   300 s, ADR-183's table). A zone past it is terminated and recorded (`tsextract-zone-timeout`: its files,
   the cap, C-196) instead of stopping the ingest. **This lifts C-196's residual for lane A TS.** The
   whole-run cap stays as a backstop for a hung helper, raised to 3,600 s, since a zone that outruns its own
   cap no longer reaches it. The zone record is a change to what the layer says, so this commit bumps the
   patch. Every zone that finishes is byte-identical.
3. **Lane B runs its languages concurrently** (`HOBBES_LANE_B_JOBS`, default `min(3, cores / 4)`). Units
   within one language stay serial, so one tool cache is never written by two containers at once. Each
   language's facts, records, containment ledger entries and timings are collected and then merged in
   today's order, so the artifact cannot depend on which finished first.

Each lands as its own commit, through the gate, with the memory peak (ADR-119's amendment) and the wall time
before and after.

## Memory

Parallelism trades memory for time: four TS zones held at once can hold four checkers. Each lever's commit
states its peak on this repo before and after, and the default parallelism is set so that peak stays under
a third of this box's 30 GB. Each knob set to 1 gives today's serial run.

## Not in this ADR

- **A TS lane A cache.** A zone's facts depend on every file its checker reads, including `node_modules`
  `.d.ts` files and resolutions that failed. A key that misses one of them serves stale facts silently,
  which is a correctness question before it is a speed one. It gets its own ADR, with a read-set key and a
  hit-equals-fresh test.
- **A process pool for Python lane A, and tree-sitter queries in place of walks.** Measure after lever 1;
  the walks may no longer be worth it.
- **Units within one lane B language in parallel.** That needs the tool caches' concurrency checked
  (npm, cargo, Go, Gradle).

## Measured, as built

Gate runs in `~/.hobbes/bench/speed-route2-2026-10-28/gate-lever{1,2,3}/`, each cell cold (index cache off),
both arms frozen worktrees. Wall times are from a box running other work at the same time, so they are
indicative only; the identity results are not affected by load.

- **Lever 1** (`1c3ccad`): cJSON, toml, jsoup, memchr, click, zod identical. The hobbes cell and fmt each
  differed by one C/C++ tail count (`distance-avx512.c`, `printf.h`). pysource reads no C. The control arm
  was added to the gate after this run; lever 2's control showed the same shape run to run. The Python parse
  over this repo: 10.54 → 9.06 s.
- **Lever 2** (`15a2c9b`), with the control: six cells identical, control identical. The hobbes cell and fmt
  differ in tail counts of the same C/C++ files in the control (before against before) as in the change
  (`sqlite-vector-kernels/src/distance-*.c`; fmt `test/unicode-test.cc`, the same row both ways). That is
  C-149, amended with the size seen. The helper's facts alone are byte-identical to the original at jobs 1
  and 4 on the hobbes cell. Hobbes cell, cold ingest: 325 s and 308 s (before, control) → 251 s; peak RSS
  3.5 → 6.3 GB.
- **Lever 3** (`a77d140`), with the control: six cells identical, control identical; the hobbes cell and fmt
  again differ only in C/C++ tail counts that the control shows differing too (the `sqlite-vector-kernels`
  files; fmt `printf.h`). `graph.json`'s `containment` steps are identical: the ledger merge holds. Hobbes
  cell, cold ingest: 251 s (before and control) → 195 s; peak 6.4 → 6.3 GB. The single-language cells do not
  move, as expected.

**End to end, quiet box** (`final-timing.sh`; the hobbes cell; `main` at `71a28c3` against the branch at
`a77d140`, nothing else running):

| | `main` | branch |
|---|---|---|
| cold (index cache off) | 305 s | 194 s |
| warm (second run, cache on) | 129 s | 69 s |
| lane A TS | 98 s | 42 s |
| Python parse | 12.0 s | 10.5 s |
| peak RSS (GNU time) | 3.6 GB | 6.3–6.4 GB |

The peak is the TS helper's, four zones at once; the ingest's own process peaks at 989 MB (ADR-119's
amendment). `HOBBES_TS_JOBS=1` gives back the serial helper's 3.5 GB.
