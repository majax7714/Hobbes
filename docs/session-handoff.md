# Session handoff — the single resume point

**Reviewed 2026-09-16 (night, latest); Hobbes 0.2.35-beta on `main`.** ADR-114's base
rule runs first on the next push: check the graph job's "base ref" step
says it reviewed from the last green run. The knowledge server serves
the image it started from until it is restarted (C-65): **restart it**
— the image was rebuilt at 0.2.35-beta at the end of this session.
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.35-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask); **a
  constraint's fix is a patch even when structural** (Max, 2026-09-13).
- **Where work happens:** on `main`; publishing belongs to Max.

The latest session's record is the 2026-09-16 "lane B reads an
unchanged unit from its index cache" BUILDLOG entry (ADR-122,
0.2.35-beta). Before it, the same day: "no call in an unevaluated
operand" (ADR-121, 0.2.33-beta and 0.2.34-beta), "the override set is
drawn" (ADR-120, 0.2.32-beta), the "top-level review" entry (the drift fix,
ADR-118, ADR-119, the review page), ADR-117 (C-156 surfaced), O10's four
defects fixed, and the 2026-09-15 "foreign C++ cells" entry. Earlier sessions' detail
lives in their own BUILDLOG entries; this file keeps only what the next
session needs.

## ⇢ START HERE NEXT SESSION

0. **0.2.35-beta (ADR-122): lane B reads an unchanged unit from its
   index cache.** The review's next speed item, done and measured.
   - **Measured first:** python's 26 s is the index container (the venv
     listing 0.24 s, staging 0.02 s, the decode 0.08 s); two helper runs
     write byte-identical facts files (python and 8 Go modules). The
     review's premise — "the stage key, already a content hash" — was
     wrong: `stage_key` is stat-based. The cache keys by content.
   - **Built:** `extract/indexcache.py` and one hook in
     `scipsource.run_helper`, so every unit of six languages gets it.
     Key: helper source + lockfile, image id, config (stage path
     tokenised, `facts` dropped), sidecar files by bytes, the stage tree
     file by file, links by target + top-level stat + installer marker,
     ro mounts, env; the root left out. A hit is `read_facts` over the
     stored file; one that no longer reads is dropped and the unit
     indexed. Only a contained successful run is stored;
     `HOBBES_INDEX_CACHE=0` indexes afresh. Store
     `~/.hobbes/cache/index/`, a 30-day sweep at the next write. The
     summary prints one line under the timings; the log line carries
     `index_cache`; nothing enters an artifact.
   - **This repo:** 54.0 s → 8.9 s; lane B 49.2 → 4.1 s; keys 0.04 s;
     `graph.json` and `tests.json` sha256-identical to an uncached
     ingest. What remains on a hit is the fetch passes before the helper
     (java's resolve 2.3 s, go 0.8, rust 0.5, the venv listing 0.4); the
     key is computable before a fetch, so skipping them is a small
     follow-on if wanted.
   - **C-158 registered (surfaced):** linked trees and venvs
     fingerprinted by surface, not files; a lockfile-less manifest keeps
     its first resolution. 18 tests in `test_indexcache.py`, one through
     the image.
   - **Found by use, not fixed:** `~/.hobbes/cache/stage/` holds 38
     86-byte `.scip` files from 2026-08-22 and two old stage
     directories; `staging.sweep_stale` has no caller in the ingest.
   - The binaries, the static proxy and the image are rebuilt at
     0.2.35-beta and this repo re-ingested at HEAD (the first ingest
     after a rebuild misses everywhere — the image id is in the key);
     **restart the knowledge server** (C-65).

1. **0.2.33-beta and 0.2.34-beta (ADR-121): no call in an unevaluated
   operand — C-155 lifted the day it was registered, on both sides of
   the grade.** The review's third item, and the next undone one.
   - **Measured first:** the grammar (`noexcept(..)`/`typeid(..)` parse
     as a call of a bare identifier); fmt's and args' sites under those
     nodes; and clang's own dump in the image, which keeps a call under
     `sizeof`/`noexcept`/`typeid` and never holds a `decltype` operand —
     so the oracle carried half the defect (**H-32**, RC-11).
   - **Three units, all gate right-clear, merged no-ff:** `d95c` (lane A
     C++: `cppsource._unevaluated`, `typeid`'s operand kept), `5261`
     (O10's reader drops and counts, `sites_unevaluated`; verified in
     the image), `367f` (lane A C: `sizeof`/`_Alignof`, the VLA residual
     — the oracle unit's doer found the reader's rule reaches C).
   - **The join and the tail did not move**, against the review's
     sketch: lane B's occurrence at such a site stands as a `uses` edge
     (a true dependency, not a call), and there is no tail class. If
     Max wants the review's version (claim it; class `unevaluated`), it
     is a small change on top.
   - **fmt: 99.85% → 99.88%** (3,269/3,273; like-for-like 99.69%),
     contradicted 5 → 4, all C-153's; export 3,525 → 3,499, every
     removed row a `decltype` operand; args identical. Keys re-run after
     H-32: args identical, fmt 6 `sizeof` sites gone, no judgement
     moved.
   - **My pre-measurement was wrong** (49 sites / 1 edge; truth 299 /
     26): it skipped the headers C++ claims and matched by name. §10.10
     records P52, P54 and P56 as missed on the counts, met on the
     judgement; ADR-121 carries the dated correction. Next time: the
     provider's file list, and positions.
   - **Where things are:** `~/.hobbes/bench/uneval-drivers/` (the three
     task files and partitions, `ingest-cell.sh`, `grade-cell.sh`,
     `regrade/{fmt,args}/` the fresh exports and grades against the
     standing keys, `keys/{fmt,args}/` the re-run keys and
     `final-report.json`).
   - The binaries, the static proxy and the image are rebuilt at
     0.2.34-beta and this repo re-ingested at HEAD; **restart the
     knowledge server** (C-65).

2. **0.2.32-beta (ADR-120): SCIP `relationships` measured, then drawn
   as `implements` edges.** The review's first recall item, in Max's
   order (measure first).
   - **The measurement:** five of six indexers state `is_implementation`
     pairs on the implementor — scip-clang (49,912 on ScummVM), scip-go
     (method pairs to the interface's method *spec*), scip-typescript,
     scip-python, scip-java (and the reverse row on an abstract method);
     **rust-analyzer states none** → **C-157**, surfaced on every Rust
     run. ADR-120's table; probes and outputs in
     `~/.hobbes/bench/relationships-probe/` (`keep_probe.py` runs an
     ingest through `helper-keep-index.mjs`, which keeps the raw `.scip`;
     `measure_relationships.mjs` and `pairs.mjs` read them — a helper
     copy's `node_modules` must be a real tree, `cp -a`).
   - **Built:** helper version 5 decodes `Document.symbols[].relationships`
     and emits `implements` rows (deduplicated, sorted, scip-java's
     mutual rows oriented by the type level transitively or dropped and
     counted); the facts' fourth row kind; `IMPLEMENTS` sites; the join
     draws `implements` at semantic tier; `project` takes both ends as
     the symbol starting at the line and counts an end below lane A's
     floor; the summary, `who_calls` ("implemented or overridden by"),
     `hobbes diff`, `hobbes plan` (0.8) know the type.
   - **This repo:** 18 edges (twomod's `MemStore → Store` among them), 7
     pairs below the floor — all Go's interface method specs, which lane A
     does not declare — 83 to the stdlib.
   - **C-58 narrowed**, not lifted: the set is drawn; the dispatch is not.
   - **Open, ADR-120 §7 (Max's call):** expanding a call to an interface
     method into its overrides as a labelled step. It changes what reach
     means (ADR-007) and needs the oracle question first — the RTA and
     CHA keys judge a call by its concrete targets, so an expanded edge
     is either confirmed by them or the graph's first inferred edge.
     Deferred with it: Go's interface method specs as lane A symbols
     (lands the 7, but turns every resolved call to a spec into a `calls`
     edge and moves Go's cells); a cross-unit match for outside pairs.
   - The binaries, the static proxy and the image are rebuilt at
     0.2.32-beta and this repo re-ingested at HEAD; **restart the
     knowledge server** (C-65).

3. **The 2026-09-16 top-level review, and its two patches.** Max asked
   for a review of the top-level docs, the architecture and the
   register for anything that would raise recall, speed, cut memory or
   knock out constraints. The write-up is a Claude Docs page,
   <https://claude.ai/code/artifact/2cd3c181-444a-42f5-a81e-c3a62928eb28>;
   the BUILDLOG entry carries the substance. Done the same day:
   - five drifted numbers across README and the architecture fixed
     (`ed56089`);
   - **0.2.30-beta (ADR-118):** the knowledge store decodes an artifact
     once per version of its file and indexes edges by endpoint; every
     tool call used to re-decode the whole of `graph.json`;
   - **0.2.31-beta (ADR-119):** every ingest step timed, printed, and
     logged to `~/.hobbes/cache/timings/<key>.jsonl`, never in an
     artifact;
   - the binaries, the static proxy and the image are rebuilt at
     0.2.31-beta and this repo re-ingested at HEAD; **restart the
     knowledge server** (C-65).
   Its recommendations not started, in the review's order (the first
   three — the `relationships` measurement with the `implements` edge,
   C-155's lift, and the lane B index cache — are done: items 2, 1 and
   0): **lane A's file cache, measured with the timing block** (next);
   the fetch passes skipped on a cache hit, if their 4.1 s warrant it
   (item 0); pytest fixtures as edges (C-4); the compile
   database's `-I` path at lane A (C-133, C-142); a distinct `hobbes
   lanes` exit for registered shapes (C-70, C++); the docs restructure
   (the register's history to its own file, §3.8 per language, one
   tally held by a test).

4. **0.2.29-beta (2026-09-16 evening, ADR-117): C-156 registered and
   surfaced.** Test reach follows `calls` only (ADR-007), so a module
   of values alone (`go/internal/version`) reads unguarded. Max chose
   route (a): `tests_guarding` and `hobbes review` now say why, citing
   C-156, and the module stays listed. The rule is
   `testmap.value_only_modules` and Go's `valueOnly`. Also that evening:
   pytest's four warnings closed (the `testmap_fixture` helper renamed,
   two class fixtures moved to module level). The binaries, the static
   proxy and the image are rebuilt; **restart the knowledge server**
   (C-65).

5. **O10's defects (2026-09-16, bench only, no version move): all four
   fixed, everything regraded twice.**
   - **H-31 traced and fixed the same day** as `S-20260916T165315Z-16f4`
     (merged `db20845`): a callee whose qualifier a macro body supplied
     (`#define FMT_SYSTEM(call) ::call`) was keyed on the `#define`'s own
     line — in fmt another file — so six real `os.cc` calls sat where
     nobody wrote them. Traced on the cell's key, not a synthetic; my
     first probe missed it because it spliced macros but never a
     *qualifier*. **Regraded: all six confirmed**, fmt **99.85%**
     (3,269/3,274), and **fmt's triage ratio is now `hobbes-wrong 5 :
     oracle-wrong 0`** — the oracle's share of that cell is zero.
   - **Its seventh row was never the oracle's:** `compile-test.cc:127`
     draws `fmt::arg` inside an unevaluated `decltype`, which the
     compiler never calls. Registered **C-155** (unsurfaced), and fmt's
     ratio corrected against us from 4:7 to 5:6 before this fix.
   - **P50 missed:** I predicted all four foreign C++ cells would rise as
     they did under H-30; three did not move and the fourth moved one
     row. A fix to the key's *position* reaches a tool only where it had
     already drawn there, unlike H-30's *silence* rule.
   - Tracker **34 of 40**. The earlier three fixes and the first
     three-tier regrade are below.
6. **The first three (2026-09-16): H-28, H-29, H-30.**
   - **H-28** (a member call keyed at its object's start) and **H-29**
     (an unmangled declaration keyed by its bare name) fixed as
     `S-20260916T153010Z-8170`, merged `eec8141`; **H-30** (a line the
     key left unresolved still contradicting) as
     `S-20260916T155426Z-8d48`, merged `f747aef`. Both gate-clear,
     verify-pass, merged not squashed. Tracker **33 of 40**.
   - Each cause was **probed in the image before the ADR was written**,
     which overturned two wrong hypotheses. H-31's `os.cc` half never
     reproduced, so it stays open by design.
   - **The regrade (§10.8, P36–P45):** fmt 99.1% → **99.7%**, args
     unmoved, **38 own cells unmoved**, **13 of 44 foreign cells moved**
     (all contradicted → silent). The four foreign C++ cells were
     regraded against the new key.
   - **The costs, all recorded:** 6 of C-153's 10 wrong rows are now
     *unjudged*, so fmt is **99.48% like-for-like**; the poison
     instrument covers fewer sites; and the rule raised every moved
     **competitor** cell while moving none of ours. **P36, P37, P38
     missed**, all flattering, recorded as misses.
   - **Where things are:** `~/.hobbes/bench/oracle-defect-drivers/`
     (task files, partitions, `rerun-cpp-key.sh`, `regrade-stored.sh`,
     `regrade-foreign.sh`, `foreign-pairs.tsv`) and its `regrade-out/`.
   - **Open for Max:** whether the lane should print a
     "judged-as-before" companion number on any cell with
     `line-unresolved > 0`; C-153's status, now 4 judged : 6 unjudged;
     and C-155. Nothing in the oracle's own log is open.
   - Found by use: `calvin_tracker.py` pinned `gate v2, grounder v3`, so
     the first session at grounder v4 could not be parsed; fixed with a
     test red on the old pattern (`ce43e5a`).
7. **The foreign C++ cells (2026-09-15, no version move): C++ is closed
   out on the comparative page too.**
   - Pre-registered first (`oracle-grading.md` §10.7, P32–P35,
     `ac5f7c8`), then both tools on fmt and args, host-run, graded by
     the Hobbes cells' stored clang keys:
     - CodeGraphContext fmt 844/975 (86.6%), recall 11.8%. Its args
       cell graded nothing: it reads no `.cc`, `.cxx` or `.hxx` file.
     - repowise fmt 2,414/5,343 (45.2%), recall 13.9%; args 815/937
       (87.0%), recall 23.3%.
     - Hobbes is ahead on both axes on both rows. P32–P34 met where
       decidable; P35 missed (no tool's fmt recall passes 14.5%).
   - The triage (60 rows, seeded) found two converter defects (C-94).
     converter@4 (ADR-101 amended) reads `#  define` and advances a
     C/C++ split head. Re-converting all 52 foreign dumps moved only
     repowise's two C++ cells, regraded with signed direction lines.
   - Graphics regenerated: 90 cells, 22 same-key rows; `render.py
     check` and the report test green.
   - **Where things are:** `~/.hobbes/bench/comparative/{codegraphcontext,repowise}-{fmt,args}/`;
     the drivers `run-cpp-cell.sh` and `regrade-cpp-cell.sh`; the
     triage files `triage-cpp-{codegraphcontext,repowise}.json`.
     CodeGraphContext left a `.cgcignore` in each C++ clone (`field.md`
     §2).
   - **Parked (Max, 2026-09-15):** CodeGraphContext's optional SCIP
     path for C/C++ (`SCIP_INDEXER=true` over a compile database) goes
     into a full-version comparative retest, one item in
     `future_additions.md`. C++ is closed out for now.
8. **Lane B's facts arrive as a stream (2026-09-15, 0.2.26-beta,
   ADR-116).** C-150's remainder, Max's route A of three:
   - the helper writes `<stage>.facts.ndjson` — a header, one JSON line
     per document, a trailer that counts them; helper version 4 — and
     prints nothing; `scipsource.read_facts` reads it into slotted,
     interned resolution `Site`s and rows, and refuses a short file;
   - found first: at 0.2.25-beta ScummVM's facts (699 MB of JSON) were
     longer than V8's longest string, so the helper threw and the
     record read "install Node". C-150 corrected, and moved to
     *partial*: a kill on the Python side leaves no record;
   - measured: the helper 3.29 GB resident at the image's default heap,
     `read_facts` 0.99 GB (1.36 GB with the buckets), every row the
     same as the one-document form's; this repo's graph identical under
     `aaffca6`'s code and this change's;
   - **ScummVM end to end:** exit 0 in 8 min 57 s, contained, 7.72 GB
     peak on the Python side; 941,498 semantic symbol edges, its C/C++
     sites 61.3% accounted where they were 0.0%. Its graph is in
     `~/.hobbes/bench/cpp-cells/scummvm-cost/.hobbes/derived/`;
   - **Where things are:** ScummVM's index and unit list in
     `~/.hobbes/cache/stage/b7bc0819382fd513.scip.units/`; the probes in
     `~/.hobbes/bench/cpp-drivers/probes/` — ADR-115's `decode_equiv.mjs`
     and `stream_probe.mjs`, and this session's `facts_probe.mjs` (the
     V8 string check, and a line file), `helper_facts_probe.mjs`
     (`writeFacts` in the image) and `py_facts_probe.py` (the Python
     read, by route; `join` as the third argument adds the join). Run
     the `.mjs` from `scip/`, the `.py` with `uv run --project pipeline
     python`.
   - **Next on C-150, its own decision:** the 7.72 GB peak is lane A,
     the read and the join (4.6 GB mid-join), then the graph built from
     them. A slotted `Resolved` takes part of it; measure the graph
     build's share before choosing. **Parked** (Max, 2026-09-15: the
     memory patches are for a huge repo; "fine for now").
   - **Then 0.2.27-beta:** a C or Java unit's own record sits at its
     root, not `root/root` (the caller re-roots first, then appends, as
     the TS zone did); two tests, each red on 0.2.26-beta's code.
   - The binaries, the static proxy and the image were at 0.2.29-beta; see item 1.
9. **C++ is closed out (2026-09-15): supported, 0.2.23-beta.** ADR-113's
   units are complete.
   - **The cells** (records in `docs/oracle/cells/`, host-run and
     contained):
     - fmtlib/fmt, chosen: 96.1% at 0.2.21-beta, **99.1%** (3,254/3,282)
       at 0.2.22-beta;
     - Taywee/args, the draw: 99.8%, then **100%** (1,995/1,995).
   - **The fix between them**, Max's route "Fix both, then row": ADR-113
     §2's third amendment, one unit (`8302`, 77 turns, $6.48, gate
     right-clear). Two rules:
     - a C++ site whose references name several overloads abstains
       (C-151);
     - a C++ file lane B compiled draws no fallback edge (C-152).
   - **The row:** `VERIFICATION_BASE["cpp"]`, §3.8, the evidence log,
     and C-132 narrowed again.
   - **fmt was graded before its pre-registration existed**; §10.6 says
     so, and args was graded after it.
   - **Where things are:**
     - cells, regrades, clones and the static `oracle`:
       `~/.hobbes/bench/cpp-cells/{fmt,args}-cell/` and
       `{fmt,args}-regrade/`, beside the clones, with `oracle` in
       `fmt-cell/`;
     - the task file: `~/.hobbes/bench/cpp-drivers/closeout-task.md`;
     - the triage probes: `~/.hobbes/bench/cpp-drivers/probes/`.
   - **The probes:**
     - `capture_join.py` wraps `evidence.join` during an ingest and
       dumps what lane B handed the join;
     - `probe_helper.py` runs an ingest through a patched helper copy,
       mounted where `helper_dir()` points (`helper-probe.patch`: the
       `PROBE-*` stderr lines);
     - run both with `uv run --project pipeline python <script> <repo>
       <out> [<helper-dir>]`.
   - **Restart the knowledge server** the next session opens with
     (C-65).
10. **Done: the gate's arrow-parameter fix** (C-91, 0.2.28-beta). C-91
   was amended first (`342c5d1`), then the unit was dispatched as
   `2b26` (27 turns, $1.57, gate right-clear) and merged no-ff
   (`3526be2`). The harness's one false block is closed. The task and
   partition files are in `~/.hobbes/bench/gate-drivers/`, a pattern
   for the next brief.
11. **Open for Max (no spend):**
   - **Nothing in the oracle's defect log is open.** H-28–H-32 were all
     fixed on 2026-09-16; what is left on fmt is C-153 alone.
   - **ADR-121 §2's choice** (item 00): lane B's occurrence at an
     unevaluated site stands as a `uses` edge and there is no tail
     class; the review had sketched claiming it and a class
     `unevaluated`. Yours to keep or reverse.
   - **The reporting call H-30's fix forces:** the rule silences 6 of
     C-153's 10 rows, where Hobbes' edge is genuinely wrong, lifting fmt
     from 99.66% like-for-like to a reported 99.85%. Whether the lane
     should print a "judged-as-before" companion number on any cell with
     `line-unresolved > 0` is yours, not a regrade's to settle.
   - **C-153 is unsurfaced** (debt): scip-clang's single answer at a
     call in a template can name the wrong declaration (10 of fmt's
     3,395 judged semantic edges). Nothing at the site can detect it.
     Whether to accept it as documented-only is Max's.
   - **`hobbes lanes` exits 1 on fmt**: 316 disagreements where lane A
     guesses, none drawn (read against the key in fmt's record). This
     repo's graph has 0 C++ disagreements, so CI is unaffected. The two
     routes: compare C++ only where the fallback could draw, or keep it
     as the self-test's report.
   - **C-150's remainder** (large repos, every language): the join's
     output and the graph built from it, after ADR-115 and ADR-116 took
     the decode's and the read's share. Parked (Max: "fine for now").
   - Carried: C-139's finer extent (only if a cell shows the recall
     cost); the tracker's area for a test-only session (row 17, `—`);
     C-140's remainder (ADR-112's route 2); C-133's unit 2 (the `-I`
     read), deferred until a graded cell shows the cost.
12. **Running a session** (`calvin-harness.md` §5):
   - Keep the token in the key file, and ingest at HEAD.
   - The doer's model is the checkout's: `HOBBES_DISPATCH_MODEL` in
     `.claude/settings.local.json` (this box: `claude-opus-5`); `--model`
     beats it.
   - Decide the design in an ADR or an amendment **before** the
     dispatch.
   - Name one small unit: `hobbes dispatch --task-file … --partition …
     --secrets "$HOBBES_SECRETS"`, with `--dry-run` first. Check that the
     argv carries `--settings` (the hook) and the model.
   - **Launch a dispatch detached** (`setsid nohup sh -c '… hobbes
     dispatch …; echo "exit $?"' > log 2>&1 < /dev/null &`), never as the
     assistant's background Bash, which is capped at ten minutes. A
     short background waiter over the log (`until grep -q '^exit '`) is
     fine; killing it does not touch the dispatch.
   - Review the session file and the diff. Merge with `git merge --no-ff`,
     never squash. **After filling the review block, re-render the
     tracker** (`pipeline/scripts/calvin_tracker.py render`).
   - **Run every live and `lane_b` test on the host before merging**:
     they skip in the sandbox. `8302`'s blind `lane_b` assertion was red
     on the host, as live tests had been after `2aa9`, `3ebb` and
     `de81`.
   - **Testing a branch on the host:** `git worktree add` it, copy
     `scip/node_modules` and `tsextract/node_modules` as real trees, `uv
     sync` in its `pipeline/`. Node 22 prints `ℹ pass N`, not `# pass N`.
   - Do not rebuild `go/bin` while a dispatch runs; do not re-ingest
     while one is gating.
   - Clean up a killed session with `podman rm -f -t 0
     hobbes-side-<id>` and `podman network rm -f hobbes-int-<id>`.
   - **Toward 40 across three areas:** the tracker reads 37 of 40, 4
     areas, 1 false block (`f3c1`, closed at 0.2.28-beta), 0 missed.
13. **A regrade against stored keys:**
   - For one cell: re-ingest, `oracle export`, then `oracle grade
     --poison` against the cell's saved `oracle.json` (as the C++
     regrades did).
   - For many: `~/.hobbes/bench/adr111-drivers/regrade3.sh` over a
     `cells.tsv` (ROOT=<worktree>); run a pre pass only when ingest code
     changed; never two passes over one clone at once.
   - A regrade after a fix carries signed direction-of-fix lines in its
     record.
14. **Carried:**
   - **The ingest's `.gitignore` edit.** Register it as a constraint or
     change it, on Max's reading.
   - **`stringer` is not in the image.**
   - **The Gradle attach route's residuals** (C-67); `recall-collapsed`
     and H-23; ADR-105/P13; the C-98 residuals.
   - **The comparative queue:** the two SQLite tools in `field.md`
     (converters first); syft's keys on a bigger box. The foreign C++
     cells are done (item 5).
   - **C's residue:** C-134's remainder, C-135's autotools, Meson and
     Bazel roots, C-133's unit 2 and its macro half; the macro gap is
     parked (C-131).
   - **`build-logic/`** is recorded, not built (ADR-097).
   - `~/.hobbes/cache/stage/` holds small leftover `.scip` outputs.

## Atlas-0 — held from 2026-09-07: Max reads the B4 record; then the T that carries the abstention act, and T_v2

**Done 2026-09-07** (`docs/atlas0/atlas-0.md` § Addendum), $22.28
assumed of $25: the §A.1 checks on saved weights (B1 reads through
eight heads and stores in six FFNs; B2's refusal is a linear direction;
B3's copy circuit is layer 0), B4 (typed attention), the λ sweep, and
the grid at λ = 0 (§A.7 branch 3, B4-given, is what the results select).

**What needs Max:**
1. **The T that carries the abstention act:** the memorising T (3,500
   steps, batch 64) or §A.7 branch 2's computed `NO_EDGE` target in a
   B4-given block. About $3.5–4 plus B1's cells.
2. **The grid's second run:** about $3.8 (the programme to about $26
   against its $25 ceiling).
3. **T_v2 for the v2 grid:** the plateau at 3,100 is seed-variable.
4. **The corrected item-1 section and §6.6 as amended**, and the ADR
   number on *accepted*.

Practical: `modal_atlas0.py mech` for checkpoint checks (about a minute
each); the drivers build paths by string (`Path.with_suffix` eats a
dotted name's tail); the grid's B4 cells run four at a time, about 14
min each.

## TTT — held

1. **The 10,000-step point** (about 6 A100-hours), and **the 3,000-step
   adapter under the primary cell** (about 0.7 A100-hour). The adapter is
   on the volume at
   `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/cc9e99c14215`;
   deploy with `TTT_APP=hobbes-ttt-cell … deploy`, then `ttt_cell.py run
   … --arm A2=<name> --arm A3=<name>` (arms A2_3000 and A3_3000, added to
   `cell.ARMS`). Records: `docs/ttt/olmo3-ttt-results.md` §9–§10.
2. **The cell's defect register** (D-1–D-5): which to fix first.
3. **ADR-092's four embedded decisions.** Nothing blocks on them.

## WHERE THINGS STAND (2026-09-16)

- **Languages:** Python, TS/JS, Go, Rust, Java, C and C++ supported, each
  as far as its §3.8 row (P11); Terraform/HCL structure.
- **The Calvin harness** (ADR-107, ADR-112): each session's state is
  under `~/.hobbes/sessions/<id>/`, written by its sidecar
  `hobbes-side-<id>`; the doer mounts only `in/`, read-only, and its HOME
  is a tmpfs. Thirty-seven log files under `docs/calvin/sessions/`.
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 90 cells (22 same-key rows, C++'s two among them); `render.py
  check` green.
- **Atlas-0** (`bench/atlas0/`, 84 tests) and **TTT** (Modal apps
  deployed and idle): held.
- **Register:** 157 entries: 113 active (87 surfaced, 21 partial, 4
  unsurfaced — C-19, C-20, C-112, C-153 — 1 n/a), 27 lifted, 11
  superseded, 6 folded. Latest: C-155 lifted (ADR-121, 0.2.33-beta);
  C-157 registered and surfaced, C-58 narrowed (0.2.32-beta, ADR-120).
- **Oracle defect log: nothing open.** H-28–H-32 all fixed 2026-09-16
  (H-32, the key's site in an unevaluated operand, opened RC-11).
  RC-2 gained its sixth sighting and closed with H-31 (macro-carried
  code keeps getting the wrong position); RC-3 and RC-8 closed-policy
  (D-O4 gained the member-call bullet; the C reader's key is
  owner-qualified as javac's is); RC-4 closed for H-30 and carrying its
  price — silencing is indiscriminate, and it hides 6 of C-153's rows.
- **Suites** at 0.2.34-beta: 1,655 pytest, 0 warnings, and Go 390
  (389 pass, 1 skip) against the rebuilt image (2026-09-16); 87 scip node
  (2026-09-16);
  oracle-lane Go 116 with subtests, 104 pass / 12 skip on this host,
  which has no clang++ or cmake (the five C++ fixture tests run and
  pass in the image; counted by `go test -json`, 2026-09-16); 52 vitest, 36 tsextract, 84 atlas0
  not re-run.
- **Disk:** `~/.hobbes` is about 50 GB plus the C++ cells (ScummVM's
  cost clone at `cpp-cells/scummvm-cost` is the large one; sweep it if
  space is needed).

## NEXT (in order; no API spend)

1. **Keep dispatching named no-spend work through the harness,** one
   unit per brief, toward 40 (three to go): the review's index cache
   (item 1: lane B by stage key, then lane A's file cache, measured with
   the timing block); ADR-120 §7's expansion once Max decides it
   (item 0);
   C's residue (W1); W1/W3's no-spend items
   (the decorated-declaration line convention, the C-15 namespacing ADR,
   `fetch-java` on the egress proxy); the comparative queue's next tools
   if named.
2. **W0's remainder:** the registry-pulled image and the drift audit, when named. (The
   forgotten red review and the fixtures closed with ADR-114.)

**Held, with all spend:** the Atlas-0 T items; the TTT adapter points;
the removal A/B re-run on the 7B; a second unseen repo through the cell;
DeepSWE's decomposed protocol; `hobbes narrate` on this repo. The keyed Calvin runs are closed, not
held.

## STANDING POLICY (Max) — read before doing anything

0. **API spend and Modal compute are off the table** (Max, 2026-09-04)
   unless Max names a run and its ceiling. No remainder carries to
   another run. **A `hobbes dispatch`** spends the owner's Claude Code
   subscription, not API dollars.
1. **Experiments are PARKED** except what Max clears by name.
2. **The 7B is the instrument, by speed not capability.** GPU-hours
   stated first; ≥15 min of evaluation before any run over 30 min.
3. **P12 (ADR-082):** every TTT arm is *model + prompt* and is labelled
   so.
4. **The 27B is untouched** until the mapping fixes are validated on
   the 7B, and only on a decontaminated set.

## PRACTICAL NOTES

- **Two sessions may share this checkout.** Before assuming `main`'s
  state or a file's content, read `git reflog` and the file itself.
- **Pre-register before grading a new cell.** Check
  `oracle-grading.md` §10 for the language's section first; fmt was
  graded before its section existed (2026-09-15).
- **A session sees only its own `in/`** (0.2.14-beta, ADR-112); an
  explicit `--network` is the old file world (C-140 in full).
- **The sidecar and the route:** every session gets `hobbes-int-<id>`
  and `hobbes-side-<id>`; `hobbes-egress` is a shared bridge. Name every
  probe container before removing by name.
- **A no-spend route check:** `CLAUDE_CODE_OAUTH_TOKEN=invalid
  go/bin/hobbes-session start --repo <a tiny repo> --role implementer
  --egress api.anthropic.com --task "Reply ok." --max-turns 1`: expect a
  401, tunnels to `api.anthropic.com:443`, no refusals.
- **After an image rebuild, restart the knowledge server** (C-65).
- **The comparative graphics** are rendered by
  `bench/oracle/report/render.py` (`cells`, `render`, `check`); a
  caption that names cells reads them from `cells.json`.
- **A model run:** state the total dollar ceiling, run a few units
  first, compare the cost to the estimate before widening.
- **Worktrees for sub-agents:** make one with `git worktree add` from
  `main`; a worktree lacks the gitignored build outputs.
- **`pgrep -f` / `pkill -f` match your own waiting shell too.** Wait on
  a log line and kill by PID.
- **Always `uv run --project pipeline hobbes … --repo <target>` from
  this checkout** (ADR-094).
- **The oracle lane:** build `oracle` from the tree before a regrade;
  `go test -count=1 ./report/` after a record changes; send a regrade's
  report to a file; `run-cell.sh --lang cpp` runs O10 (`77cbd44`).
- **Olmo 3 on vLLM has no tool-call parser:** send no `tools`.
- **The key file is off the tree.** Never write its path into repo
  prose. It holds `anthropic_key` and `claude_oauth_token` (the
  harness's default `--key-name`).

## Housekeeping

- Commit to `main`; never `git push` (Max publishes).
- One ADR per design decision; one BUILDLOG entry per session.
- Every concession gets a `C-n` in its segment file under
  `docs/constraints/`.
- Rewrite this doc; do not append to it.
