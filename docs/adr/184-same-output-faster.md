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

## Amended 2026-10-29 (0.3.4-beta): the review of PR #5

- **The gate could pass a failed ingest.** `run.sh` copied whatever artifacts the cell held after a pass, so
  a pass that crashed was compared as the previous pass's output. `compare.py` also compared parsed JSON
  while the rule says bytes. Now each pass's artifacts are cleared first and its exit kept. A failed pass
  fails the comparison. `graph.json` is compared as bytes with `built_by`'s value masked, and the same JSON
  in other bytes differs. **Every gate run above was re-checked under the new comparison:** every pass
  exited 0, and every cell called identical is identical bytes. The measured results stand.
- **A zone cap past setTimeout's limit** (2³¹−1 ms, about 24.8 days, reached by a large
  `HOBBES_TIMEOUT_SCALE`) made Node fire at once and stopped every zone. Past that limit a zone now has no cap
  of its own, and the whole run's backstop holds.
- **A zone timeout says how many zones ran beside it.** A zone near its cap can finish alone and not beside
  others, so the facts can depend on `HOBBES_TS_JOBS`. The `zone-timeout` record names the parallelism and
  the knob (C-196).
- **A failed zone stops the dispatch.** No lane starts another zone after one has failed the run.
- **Each lane B language keeps the peaks its own run ended with.** They were sampled at the merge, after
  every language had finished, so each row showed the last peak. A language beside another still shares
  its process's peak (ADR-119's amendment says so).
- **An interrupt starts no lane B language that has not started.** The pool's queued languages are
  cancelled. A running one ends with its container, which the terminal's Ctrl-C reaches too.
- **Not changed:** each zone still starts a fresh worker, which re-imports TypeScript and copies the file
  set. That is measured fine at this repo's 27 zones. Keeping `jobs` long-lived workers is the shape for a
  repo with hundreds of zones, and it waits for one that measures it.

## Amended 2026-11-02: long-lived zone workers, one walk per file, the TS helper beside the Python parse

The "not changed" item above, measured. All of it is a speed or memory change under the byte-identity gate:
no draw, refusal or record changes, so no version bump.

- **Zone workers live for the run** (`extractRepoParallelJson`). A worker takes zone after zone; the first
  also plans the repo, so the CLI's main thread never loads TypeScript. A worker whose heap is past 300 MB
  after a zone is retired and the lane's next zone gets a fresh one, so a large zone's garbage is not carried
  into the next zone's peak. A zone's cap now runs from when the zone is handed to a worker that has loaded
  the compiler, not from the worker's start, so a fresh worker and a reused one time a zone alike (the
  review's fix below). Each file's record is serialized in the worker and the document spliced from those strings, exactly
  as `JSON.stringify` writes it.
- **One walk per file.** The seven `forEachDescendant` walks (imports, literal members, calls, constructions,
  env reads, routes, tests) read one pre-order walk over the compiler's nodes, each stage handed its kinds in
  the order its own walk met them and wrapped only when read, so the checker is asked the same questions in
  the same order. Each file's wrappers are forgotten once its record is built.
- **Line numbers by search.** ts-morph counts newlines from the file's start for every line number;
  `StringUtils.getLineNumberAtPos` is replaced, in the helper's process only, by a binary search over newline
  offsets with the same answer and range check (a test holds it to the count it replaced, CRLF and lone CR).
- **The helper starts first** (`tssource.start_ts`) and runs beside Python's discover, parse and graph steps;
  it is waited for before Go's lane A, so Go, Rust, Java, C++ and C still run after it. `lane A [ts]` now
  times the wait left.
- **pysource reads a definition's scope facts once per parse** (`_scope_fact`): `_own_definitions`, the
  `global`/`nonlocal` names, the lambda/comprehension binds and `_local_aliases`' refusals, shared by both
  binders. Same values; the parse's wall time did not move measurably, so this one is housekeeping.

**Measured** (this repo at `d1a4e73`, 2 cores, 7 GB, lane B unavailable on the box: no podman, so every
lane B step was refused in both arms; `HOBBES_TS_JOBS` default, 1 here; cache off; quiet box, two runs each):

| | before | after |
|---|---|---|
| ingest wall | 96.2 s, 95.6 s | 56.5 s, 57.1 s |
| TS helper alone | 63.1 s | 42–44 s |
| peak RSS, largest child (the TS helper) | 629, 654 MB | 575, 576 MB |
| peak RSS, the ingest's own process | 381 MB | 395 MB |

**Identity:** this repo (control: the before checkout run again agrees with the after run), zod and click:
`graph.json` identical but for `built_by`, `tests.json` and `interfaces.json` identical bytes. The TS helper's
facts on this repo are byte-identical to the before helper's. Not gated here: the other ADR-184 cells, lane B
on, and `HOBBES_TS_JOBS` > 1 on a large box (the jobs tests cover 1, 2, 3 and 8 for identity, not for peaks).

**What did not halve, and why.** The helper's peak is one zone's live program: the largest zone here
(`tui/opencode/packages/tui`, 471 files, 3.8 MB of source) holds about 320 MB live with its program and
checker, on top of the compiler's own code. Lowering that changes what the checker sees. Keeping one warm
worker for every zone ran in about 38 s but peaked at 0.8–1.1 GB; collecting or retiring workers more often
cost back most of the time, so 300 MB is the trade chosen.

**Review (2026-11-09).** Merged after Max's review with four fixes, none of which moves a byte of the facts
(re-checked: the helper's facts on this repo, zod and paseo at `--jobs` 1 and 4, and this repo's ingest with
lane B off). The text above first said the helper also ran beside the other languages' lane A; it does not,
and now says so. As first written, a zone's cap started when the zone was posted, so a fresh worker loaded
TypeScript inside it and a reused one did not: whether a zone near its cap timed out depended on which lane
took it. A fresh worker now says it is ready once the compiler is loaded and the cap starts after that; a
worker that hangs while loading is left to the whole run's backstop. `@ts-morph/common`, which the line-number
change imports, is declared rather than reached by npm's hoisting. Not changed: the helper is not stopped if
the Python steps raise before the ingest waits for it, and the other languages' lane A could also run beside
it (both in `currently-open.md`).
