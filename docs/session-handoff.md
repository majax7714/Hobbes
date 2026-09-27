# Session handoff — the single resume point

**Reviewed 2026-09-27 (twentieth session); Hobbes 0.2.71-beta on `main`.**
Max pushed through the eighteenth session's last commit (`ea6cb28`,
0.2.70-beta); the nineteenth and twentieth sessions' commits (0.2.71-beta, the E3/E4/D-11 bench work and docs)
are on `main`, unpushed. The image and the proxy are at 0.2.71-beta and this repo
is ingested at that release. A new
session's knowledge server is a new container from the current image
(`sandbox/knowledge-serve` runs `podman run --rm`), so it is fresh;
the restart after a rebuild is the closing session's last step, never a
line carried here.
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.71-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask); **a
  constraint's fix is a patch even when structural** (Max, 2026-09-13;
  confirmed for ADR-129 on 2026-09-17). **A minor is for a feature added
  to Hobbes** (Max, 2026-09-20): the harness earned 0.2.0, the dev
  environment would earn 0.3.0 and is not being worked on; an extraction
  change is a patch even when it moves the symbol floor.
- **Where work happens:** on `main`; publishing belongs to Max.

The history of 2026-09-17 to 2026-09-19 (ADR-131 to ADR-140,
0.2.42–0.2.55-beta) is in those days' BUILDLOG entries and the
CHANGELOG; this file keeps only what the next session needs, and the
drivers' paths below.

## ⇢ START HERE NEXT SESSION (written 2026-09-27, twentieth session)

**Max's direction (2026-09-20): extraction first — "the most annoying work to do but
the most important for hobbes"; "we never sacrifice honesty for higher recall".**

**Two tracks are open.**
- **The Calvin experiments: D-12 is run and read, and D-13 waits for Max** (twentieth session;
  `calvin-experiments.md` §6 "D-11's record" and "D-12's record", §9 D-13).
  - **D-12** (about $0.67; runner unit `7e20`, merged with two review fixes to `available.parse`):
    - **S-3h** is S-2h plus a block giving, for each intrinsic and sibling-file name the unit's shots use,
      whether this file has it and its form here. Availability is read as the grader meets it
      (`lattice available`, in the image; the record is `d12/available-record.json`).
    - **Null:** S-3h − S-2h is +0.011 pooled (p 0.59).
    - On sse2, 132 of 194 invented intrinsics are the renames the block said have no form here. The student
      renames the shot itself and disregards the negative.
    - The init passes 1.00 on all three files, where the block maps the other files' names.

    Records: `~/.hobbes/bench/calvin-lattice/d12/` (`PREREG.md`, `avail.py`, `probe.py`, `classes.py`,
    `run-isa.sh`, `run-7b-<isa>/`, `report-*`, `pool-7b*`).
  - **D-13** (recommended a): the facts in the loop. One iterate round for E4: a failed unit goes back once
    with the grader's diagnostic and the block's line for each invented name. It is a no-spend runner unit,
    then about $0.3–0.5. Or b: S-3h on the 32B (about $1.7). Or c: close E4's line.
  - **D-11** (about $2.11 of $5; runner `e735`):
    - rule W, the width family (26 of 31 helpers);
    - S-2h − S-2 on helpers +0.261 pooled (p 0.0001), with sse2 unmoved;
    - the 32B +0.13 on cells and +0.30 on helpers over the 7B, at about $0.58 a file.

    Records: `d11/`.
  - **Costs, learned:**
    - The runner's estimate assumes every answer runs to `max_tokens`, 4 to 6 times the real figure. Size a
      file's ceiling at the estimate; the Modal timeout bounds the real spend.
    - A network cut (twice this session) costs the call so far and returns nothing. `lattice e4 run <dir>` resumes in place, with the
      ceiling cumulative per run dir.
  - Earlier: E4 (`e4/`, about $1.25 of $8), where the ISA-axis shots gave +0.21 to +0.26 and the parser's fields
    hurt. E3 (`e3/`, about $5.55 of $25), the 300-step pair, with its gain gone on opaque names.
- **Extraction, shipped in the nineteenth session (0.2.71-beta, D-8):**
  - one file's depth never ends an ingest (C-171);
  - C's unread-region record (C-172);
  - C and C++ lane A time grows about 8× per doubling of chain depth, which is a measured-fix candidate.
- **The comparative programme reads JavaScript** (`fbf6198`, `8292c98`): CodeGraphContext and repowise on the five
  JS keys. repowise's converter@5 fixed a `__module__` drop that had cost every repowise cell its top-level calls,
  and all 22 published cells were regraded. C-94 has the chain-line residual. Drivers:
  `~/.hobbes/bench/comparative/run-js-cell.sh`, `<tool>-<repo>/`, `at5/` in each repowise cell. repowise 0.53.0 is
  out; the cells stay on 0.49.0 until Max says otherwise.
- **Extraction:** the next candidate is **route c** (below), measured first.

- **Next candidate — route c (ADR-150), measured first:** lane A drawing a bare-name call
  to the one def of that name in the enclosing function's own body, `syntactic`. Its
  ceiling on the keys is the seven sites (flask 237, 251, 281, 296, 310; click 1836,
  1888), each at its own right def. Measure how many sites the rule would draw in every
  Python cell, and whether any is wrong (a name rebound between def and call), before an
  ADR.
- **What click still misses** (806 on r3): 460 closures — callbacks reached through
  attributes and parameters (`self.callback(…)`, `callback(*args)`, monkeypatched doubles:
  values, C-58), `@cli.command("sdist")` (10, a method factory with a positional —
  `method-positional`), `make_pass_decorator` applied bare (7), decorators held in variables
  — 215 methods (79 a subclass override of a base method drawn — ADR-126 §3's question; 90
  duck-typed receivers and test doubles), 81 lambdas, 37 classes, 13 functions. **No
  decorator-line shape with more than 10 rows is left**; none of the rest has a syntactic rule
  ready. This repo's 450: 195 functions (values in tables and records), 154 lambdas, 76
  closures, 22 methods.
- **Also found:** `src/flask/sansio/` has no `__init__.py` (a PEP 420 namespace dir):
  lane A names its modules `app`, `scaffold`, and the `implements` join places `App →
  Scaffold` but not `Flask → App` (`graph["implements"]["outside"]` 79 on flask). Why is
  not read; whether lane A's module ids for a namespace package are a constraint to
  register is Max's.
- **A harness finding (session `54cf`'s review):** verify's `classify` returns `error`
  for a row that errors on *both* trees, and `FAILING` holds `error`, so a fixture repo's
  own test the testmap names as a guard (`minifixval/tests/test_runner.py`, uncollectable
  from `pipeline/` under `norecursedirs`) failed the verdict with 0 regressions — where
  the fail/fail twin, F2F, is a fault. A route for Max, not changed.
- **Other extraction candidates, each measured first:** the TS symbol floor's
  class-property functions (zod 1,029 collapsed pairs — off the table since
  2026-09-10 "with the constructor grain settled before `new`", which ADR-142 since
  settled: **re-ask Max**, do not start); the CJS literal member (cue 49, Express 46).


Max's standing direction: **honesty and accuracy come before a recall
number on the extraction lane** — weigh every extraction decision
against them first.

**Where JavaScript stands (ADR-140 to ADR-144; §10.28, 0.2.62-beta).**
Five graded repos (`oracle-grading.md` §10.22–§10.28): Express
**998/998** (recall 65.7%), Preact **2,447/2,447** (28.6%), xmpp.js
**705/705** (84.6%), cypress-io/github-action **154/154** (89.0%),
Blueturboguy07/cue **1,005/1,005** (61.8%) — 100%
precision each, 0 contradicted, poison PASS. **Max's three JavaScript
constraints are done:** C-167 (ADR-141), C-168 (ADR-142), and C-165 —
the provisioned cell was drawn and graded with its tree and without, the
rows and the graph identical, so the entry was **corrected**: Hobbes
draws no symbol edge into a package (JS or TS), a third-party call is
stated at module grain and no key grades it. Two JS cells of five have
their tree: a thin one and cue (881 rows, identical without it). Drivers: `~/.hobbes/bench/js-cells/` (`grade.sh`,
`regrade.sh`, `cells/`, `regrade/h34/` the standing keys,
`fixture/minijs`, `oracle-trees/preact`; `c165/` — `DRAW-RULE.md`,
`draw.py`, `walk.sh`, `draw-log.md`, `RESULTS.md`, `withheld-tree/`),
`~/.hobbes/bench/c167-reexport/`, `~/.hobbes/bench/c168-construction/`.

**Measured on JavaScript, not yet constraints or decisions:**
- **Done (ADR-143, 0.2.59-beta, unit `061a`, 71 turns, $5.87):** a callee
  whose site name is not its definition's is matched at its own column
  where both lanes name one definition; 134 tiers raised on seven TS/JS
  cells, nothing added or lost (§10.25). Left, and rightly: xmpp.js's 3
  namespace-member sites. Drivers `~/.hobbes/bench/adr141-name-mismatch/`
  (`PREREG.md`, `count.py`, `RESULTS.md`; `probe_join.py`;
  `PREREG-sim.md`, `ingest_rule.py`, `sim.sh`, `sim/`; `real.sh`, `real/`;
  `lang-cells.tsv`, `lang-regrade.sh`, `lang/` — a pre/post driver over
  one cell per language, reusable; `units/`; `wt/` a worktree, removable).
- **Done (0.2.60-beta, unit `d2de`, 19 turns, $0.95):** hono's two
  yarn-v1 zones failed to provision because the argv carried the *host's*
  `corepack` path into the image — a defect, not C-23's. Contained, the
  argv now names `corepack`. On hono: provisioned, three extraction
  errors gone, dependency coverage 0 → 9 of 47, no edge moved. dagger's
  docs snippet zones had the same failure and were **not** re-ingested.
  Drivers `~/.hobbes/bench/corepack-path/` (`units/`, `hono/` the clone,
  `hono-ingest-after.log`; its worktree was removed).
- Preact's test-file misses (closures in `it` bodies, calls through
  `.d.ts` interface members, hook setters in locals) — C-58's shapes.
- **C-168's remainder: read, the entry corrected a second time, nothing
  built** (Max: route a; `oracle-grading.md` §10.26). The index emits
  nothing at `super` and names the class, never the constructor, at a
  JSX tag. Preact's 570 rows are one `.d.ts` class that *is* a symbol;
  the index names the merged interface beside it, and the 377 JSX tags
  name test-body locals. **Measured, undecided:** an `extends`-chain
  walk reads 104 rows at 0 contradicted (ajv 18, hono 8, xmpp.js 2, zod
  about 76), 0 on Preact — a chain of lane B hops would be a new kind of
  rule, for under a point a cell. Drivers `~/.hobbes/bench/c168-remainder/`.
- **`npm ci` refused three of the four lockfile-bearing JS repos the
  draws met** (xmpp.js and tileserver-gl: lockfile out of sync with the
  manifest; hack-chat: a tarball unpublished). Counted under C-23 in
  C-165's entry; whether "pinned or declined" should fall back to
  anything is Max's, and nothing is proposed.
- **Done (0.2.61-beta, §10.27): the larger provisioned cell.**
  Blueturboguy07/cue (position 41), 881/881, recall 54.3%, the same 881
  rows with its 276-package tree and without. The `javascript` row reads
  five repos, two with their tree. `npm ci` refused four of eight
  lockfile-bearing candidates. Drivers: `c165/DRAW-RULE-2.md`,
  `walk2.sh` (resumes at `walk2.sh 41`), `RESULTS-2.md`, `withheld-cue/`,
  `../cells/cue-{provisioned,withheld}/`.
- **Done (ADR-144, 0.2.62-beta, unit `12ad`, 53 turns, $3.53):** cue's
  untraced shape. `m.f()` on a namespace `require` over `module.exports =
  { f }`: the index names the literal's *property* at the site and the
  function at that property's one range, so the helper's decode files
  the reference under the function. cue 1,005/1,005 (61.8%), xmpp.js
  705/705 (84.6%), fourteen other cells row-identical (§10.28). Left,
  refused and unmeasured: a value property (`delta: alpha`); no symbol
  at all: a member written *in* a literal (cue 49, C-9/C-58). Drivers
  `~/.hobbes/bench/cjs-namespace/` (`classify.py`, `inrepo_ext.py`,
  `mini/` with a raw-SCIP `dump.mjs`, `PREREG-sim.md`, `sim.sh`,
  `real.sh`, `lang-regrade.sh` + `lang-cells.tsv`, `sim/`, `real/`,
  `lang/`, `units/`; its worktree was removed).

**Older candidates, each measured first** (none started): C-142's
remainder — the 273 headers nothing includes (ADR-138's route b, a
content read, not taken); ADR-126 §3 once Max decides it; C's residue
(W1). Small and no-spend, optional: a `lane_b` end-to-end case for
ADR-135 (a fixture tree-sitter-cpp misreads *and* scip-clang compiles —
an annotation macro after a declarator — without moving the lines other
tests pin).

**What stays from C++ recall (Max's Route A, 2026-09-17; items 1–4
built or closed, ADR-132 to ADR-136):** constructions' remainder is
C-162 (the macro class, templates, untokened conversions); a lost
definition's refused extents are C-145; C-164's remainder is its own
entry; operators at a macro's name (3,011 references on fmt) are the
macro class's (C-131, parked); TS's floor shapes stay off the table
(Max, 2026-09-10). The 2026-09-16 review's list is done but for §3.8's
paragraph cells as per-language pages (Max: "dont split for now").

**Lessons the last sessions paid for:**
- **Read every suspect of a new key, row by row.** A trace key never contradicts, so a
  wrong edge sits in the suspect queue beside C-60's asymmetry: three of flask's 18 were
  Hobbes-wrong, and "suspect rate 1.6%" said nothing about them.
- **A fixture repo's new file can move another fixture's module id.** `flask-excerpt/
  conftest.py` made ADR-006 root-prefix `minifixval`'s conftest too; check the whole
  repo's `discover_modules` ids when a brief adds a package-less fixture file.
- **Read the factory from its real source, not a trimmed one.** ADR-148's unit tested
  every shape on untyped, trimmed signatures and simulated the fold on hand-built
  digests; click annotates every factory (`**attrs: t.Any`), which the grammar wraps in a
  `typed_parameter`, and the first build folded nothing. One `parse_source` over the real
  file on the host showed it in a minute. Put a real-source case in the brief.
- **"Exactly as X does" in a brief copies X's assumptions.** ADR-145's callers are
  never modules; ADR-147's usually are. The hand-built-graph tests could not see it;
  the host's `lane_b` run did. Name the caller kinds in the brief, and give the append
  step its own lane A test.
- **A probe's premise can be the docs' error.** `oracle-misses.md` said Python nested
  defs are not symbols; the export said otherwise in one grep for a nested name. Read
  the export's `target_id`s before sizing a "missing symbol" rule.
- **Read a doer's idiom against the grammar, not only its tests.** `children[-1]` passed
  eleven cases and lost every commented decorator; a three-line parse on the host found
  it, and the same line had been wrong in the digest since it was written.
- **`-v -q` cancel.** A fixture key collected that way hides every `_…` fixture
  and the *built* lookup reads thousands "wrong" (missy: 26,474). `-v` alone.
- **A code search's hit is not the repo's use.** `pytestmark = …usefixtures(` hits
  are mostly strings pytest's own suite writes, and docstrings; read the clone
  with `ast` (`c4-pytestmark/scan.py`) before judging a candidate.
- **A deny in a session log was new** (unit `1527`): a multi-line command split
  the Policy line and the tracker had no `denied` clause. Both fixed; if the
  tracker refuses a log again, read the log's line before the parser.
- **The architecture's §8 header is a seventh version copy no test
  holds** — bump it by hand (missed at 0.2.51-beta).
- **A fixture key is collected with `-v`:** without it pytest prints no
  fixture whose name starts with `_`. flask also needs `-p
  no:hypothesispytest`, and the mounts need `--security-opt
  label=disable` on this box.
- **Collecting a foreign Python suite in the image:** `uv pip install
  --target deps --python-version 3.12 --only-binary :all: pytest <its
  deps>` on the host, then `podman run --network none -v <clone>:/work:ro
  -v deps:/deps:ro --env PYTHONPATH=/deps:/work/src … python3 -m pytest
  --fixtures-per-test -q tests`. pytest prints a test one line past its
  first line, a fixture at its first decorator line, and one row per
  fixture name.
- **Read a brief's premises in the tree before dispatch** (ADR-134's
  brief was wrong about a site's scope), and run the real cell before
  merging; a doer may narrow a brief's wording rightly (unit `5587`
  kept H-33's row).
- **A write partition is a file list, at file grain.** A directory entry
  (`tests/fixtures/new/`) matches nothing and every code file created
  under it is a `partition` row: unit `b444` was blocked that way and
  the fault was the brief's. Spell a new fixture's files out, one path
  per line. `not-code` files (a `package.json`) pass on the `reach`
  rule; code files do not.
- **An in-repo `external_ref` is the index speaking, not silence.** Its
  moniker says what was named; ADR-144's whole shape sat there unread.
  `inrepo_ext.py` groups them by descriptor — run it on a new cell.
- **Ask what the index emits at a token before counting a shape as a
  rule's** — a ten-line fixture indexed in the image answered `super`
  and JSX in a minute (`c168-remainder/mini/`, with a `dump.mjs` over
  `streamDocuments`).
- **Read a register entry's rows before building on it.** C-168 named
  the wrong shape *and* the wrong numbers, and a row-by-row read of the
  key (not the miss-class totals) was what caught it. C-165 named an
  edge that is never drawn; checking the TS cells' rows for a
  `node_modules` target, before the draw, was what caught it.
- The hobbes-go cell cannot be regraded on its stored key, nor hobbes-py on its
  old ones (a fresh hobbes-py key at `2c915a8` is in `oracle-defect-drivers/h36/`):
  their clone (`adr111-before/hobbes-wt`) is gone; a full regrade needs
  a worktree at the key's sha or fresh keys.
- scip-clang 0.4.0 emits no `enclosing_range` (checked in the image).

## Where earlier sessions' drivers are (their records are the BUILDLOG's)

The resume points of 2026-09-15 to 2026-09-19 were folded into their
BUILDLOG entries; only the paths a next session reaches for stay here.
Run the probes with `uv run --project pipeline python`; every worktree
named below was removed unless it says otherwise.

- **Python recall, 2026-09-20 to 2026-09-24 (ADR-139 amended, ADR-145 to ADR-150, H-36):**
  their records are the BUILDLOG's, the CHANGELOG's and `oracle-grading.md` §10.29–§10.36; the
  worktrees were removed.
  - ADR-150 (C-170): `~/.hobbes/bench/py-multidef/` (`index.sh` raw scip-python in the image,
    `dump.mjs`, `classify.py` — **filter out parameter monikers** (`(x)` descriptors) before reading
    it — `rows.py`, `cells.tsv`, `probe/`, `built/`, `RESULTS.md`, `units/`; `wt/` removable). **The
    flask and click clones' `.hobbes/derived/` hold the built branch's graph.**
  - ADR-145 amended (flask keyed): `~/.hobbes/bench/c4-local-value/` (`PREREG-worded.md`,
    `probe_worded.py` over a cell's own graph, reusable; `simulate_local.py`, `real/`, `units/`). The
    key and the clone: `~/.hobbes/bench/oracle/flask-py/`, `~/.hobbes/bench/oracle/repos/flask` (its
    `.venv` from `uv sync --group tests --python 3.12`).
  - ADR-149: `~/.hobbes/bench/py-factory-chain/` (`probe_chain.py`, `click_real.py`, `real149/`).
    ADR-148: `~/.hobbes/bench/py-optparens/` (`probe.py --new-only --emit --method-positional`,
    `real148/click/`). ADR-146/147: `~/.hobbes/bench/py-nested-defs/` (`probe.py`, `probe_b.py
    --show`, `real147/click/`).
  - H-36: `~/.hobbes/bench/oracle-defect-drivers/h36/` (`trace-hobbes-py.sh`; `hobbes-py/` holds
    **a usable fresh hobbes-py key**, `post-oracle.json` @ `2c915a8`). click's standing key is
    `click-py-r3`.
  - ADR-145: `~/.hobbes/bench/c4-returned-value/` (`simulate_real.py`'s `own_nodes` enters a nested
    def written at a body's top level — fix it before reusing it; `lang-regrade.sh` +
    `lang-cells.tsv`). ADR-139 amended: `~/.hobbes/bench/c4-pytestmark/` (`scan.py`, `probe.py`,
    `missy/`, `missy-key-v.txt`; `try/` removable).
  - C-4 keeps: a fixture value that is not a construction, an inherited method, a non-literal
    `autouse=`, a class-body or annotated `pytestmark`, and the abstentions.
- **JavaScript (ADR-140):** `~/.hobbes/bench/js-cells/` (above);
  `~/.hobbes/bench/h33-regrade/` (`regrade.sh <label> <tsc-oracle.mjs>
  <oracle>` runs the oracle in the image over the five TS cells' stored
  exports; `before/`, `after/`, `compare.txt`, `h34/`); the five TS/JS
  cells' reports at `~/.hobbes/bench/v018/{kbet-ts,ajv-ts,cheerio-ts,zod,hono-build}/report.json`.
- **Fixture reach (ADR-137, ADR-139):** `~/.hobbes/bench/c4-fixtures/`
  (`probe.py` and `probe-v1.py`, `compare.py`, `compare-v1.py`,
  `lookup.py`, `heldout/` flask, attrs, `deps/` and their lists,
  `units/`) and `~/.hobbes/bench/c4-remainder/` (`probe.py`,
  `PREREG.md`, `compare.py`, `lookup.py`, `*-key-v.txt` the three
  verbose keys, `<repo>-{base,use,auto,both,built}.json`, `units/`).
- **Headers (ADR-138):** `~/.hobbes/bench/c133-include-path/`
  (`claim.py`, `place.py`, `regrade/` the five cells,
  `scummvm-ingest.log`, `units/`).
- **ScummVM and the vacated line (ADR-136):**
  `~/.hobbes/bench/scummvm-scale/` (`vacated.py`, `sample.py`,
  `regrade/`, `units/`); `~/.hobbes/bench/lane-a-symbol-near/probe.py`.
- **C-164's wrong callers (ADR-135):** `~/.hobbes/bench/c164-wrong-callers/`
  (`findstream.py` a clone's cached facts stream; `shapes.py`,
  `nameref.py`; `simulate.py` + `PREREG-sim.md`; `inspect_r1.py`;
  `regrade.sh` with `ROOT=`/`OUT=`, which borrows `c145-extent`'s
  `oracle`, `probe.py` and `compare.py`; `regrade/`; `units/`).
- **A lost definition's extent (ADR-134):** `~/.hobbes/bench/c145-extent/`
  (`probe.py` — `probe-v1.py` its first form — `simulate.py`,
  `simulate_r3.py`, `regrade.sh` with `ROOT=`/`OUT=`, `regrade/`,
  `units/` with `u1-fix.patch`; `oracle` the binary built from the tree).
- **The join's claim (ADR-133):** `~/.hobbes/bench/join-claim/`
  (`probe.py` step 0, `run-all.sh` and `out/` the 24 clones;
  `ingest_bypos.py` the in-memory rule, `sim.sh` + `sim-cells.tsv` +
  `diff.py`, `PREREG-sim.md`, `sim/` the stock and by-position graphs,
  exports and reports; `regrade.sh` + `regrade-cells.tsv` +
  `compare.py`, `PREREG-regrade.md`, `regrade/` the 44 cells before and
  after, `final/fmt-cpp/`; `units/` the brief).
- **Constructions (ADR-132):** `~/.hobbes/bench/cpp-constructions/`
  (step 0: `probe.py` the per-pair read, `classes.py` the six classes,
  `PREREG-args.md`, `fmt-out/`, `args-out/`; step 1: `simulate.py` the
  exports a rule would produce — `simulate-v1.py` its first form —
  `grade.sh`, `buckets.py` bucket × token class, `tokenpos.py`,
  `PREREG-args-sim.md`, `fmt-sim2/` and `args-sim2/` the probe exports;
  `regrade.sh` with `OUT=`/`ROOT=`, which compares against 0.2.43-beta's
  export and the probe's; `final/` the 0.2.44-beta grades; `units/` the
  brief; `wt/` a worktree, removable). Run as `uv run --project pipeline python probe.py <clone>
  <facts.ndjson> <report.json> <out-dir>`; the facts stream is the
  cell's newest `~/.hobbes/cache/index/*.facts.ndjson`.
- **Operator `uses` withheld (ADR-131 amended):**
  `~/.hobbes/bench/c153-operator-uses/` (`ingest_withheld.py` the scratch
  wrapper, `diff.py`, `before/` and `after/` the graphs, `regrade.sh`
  with `OUT=`/`ROOT=`, which compares the export with 0.2.42-beta's and
  the graph with both; `final/` the 0.2.43-beta grades; `units/` the
  brief; `wt/` a worktree, removable).
- **Operators (ADR-131):** `~/.hobbes/bench/c146-operators/` (`probe.py`,
  `match.py`, `exact.py` the first reads; `simulate.py` the export a
  rule would produce, five variants; `template_split.py`,
  `tokencheck.py`, `count_tokens.py`; `PREREG-args.md`; `regrade.sh`
  with `OUT=`/`ROOT=`, which also compares against the probe's export;
  `final/` the 0.2.42-beta grades; `units/` the brief).
- **C++ recall (ADR-129, ADR-130):** `~/.hobbes/bench/c145-recovery/`
  (`probe.py`, `analyze.py`, `arity.py` the step-0 probes; `PREREG-args.md`;
  `regrade.sh` with `OUT=`/`ROOT=`; `ingest_no_arity.py` the rule-off
  wrapper; `p84-named-rows.json`; `final/` the 0.2.41-beta grades;
  `units/` the three briefs; `wt/` a worktree, removable).
- **Lane A's C++ cache (ADR-128):** `~/.hobbes/bench/laneA-cache/`
  (`equiv.py`, `split.py`, `cacheproto.py`, `scummvm-tree.json` the
  reference output, `units/` the briefs).
- **The ingest lock (ADR-127):** `~/.hobbes/bench/ingest-lock/`.
- **ADR-123–126:** `~/.hobbes/bench/lanes-shape-drivers/`, `c153-rule/`
  (measure.py, regrade.sh, the briefs), `dispatch-reach/` (measure.py,
  jsoup/click/args JSON).
- **The index cache (ADR-122):** the store `~/.hobbes/cache/index/`
  (30-day sweep at the next write); the timings logs
  `~/.hobbes/cache/timings/<key>.jsonl`.
- **Unevaluated operands (ADR-121):** `~/.hobbes/bench/uneval-drivers/`
  (the task files and partitions, `ingest-cell.sh`, `grade-cell.sh`).
- **The override set (ADR-120):** `~/.hobbes/bench/relationships-probe/`.
- **O10's defects:** `~/.hobbes/bench/oracle-defect-drivers/` (task
  files, partitions, `rerun-cpp-key.sh`, `regrade-stored.sh`,
  `regrade-foreign.sh`, `foreign-pairs.tsv`) and its `regrade-out/`.
- **The foreign C++ cells:** `~/.hobbes/bench/comparative/{codegraphcontext,repowise}-{fmt,args}/`,
  with `run-cpp-cell.sh` and `regrade-cpp-cell.sh`.
- **C++ close-out and the facts stream (ADR-113, ADR-115/116):**
  `~/.hobbes/bench/cpp-cells/{fmt,args}-cell/`,
  `~/.hobbes/bench/cpp-cells/scummvm-cost/` (the large clone; sweep it
  if space is needed), `~/.hobbes/bench/cpp-drivers/closeout-task.md`
  and `probes/` (`decode_equiv.mjs`, `py_facts_probe.py`,
  `capture_join.py`, `probe_helper.py`).
- **The gate's arrow-parameter fix (C-91):** `~/.hobbes/bench/gate-drivers/`,
  a pattern for the next brief.

## Standing items (carried)

1. **Open for Max (no spend):**
   - **The Calvin experiments programme** ([`calvin/calvin-experiments.md`](calvin/calvin-experiments.md),
     ADR-151; D-1 to D-4 taken 2026-09-24): a model that writes C, from sqlite-vector's SIMD kernel lattice.
     E0 built and accepted; E1 run on both 7Bs ($6.59 of $10); **E2 run on Qwen's two shadows ($1.89 of $3,
     2026-09-26; runner unit `157a`, routes E2-a to E2-g)**. E3 run (≈ $5.55 of $25) and E4 run on all three native files (≈ $1.25 of $8), nineteenth session; D-11 (≈ $2.11 of $5) and D-12 (≈ $0.67) run, twentieth session; next: D-13 (START HERE). Drivers:
     `~/.hobbes/bench/calvin-lattice/` (`e1/`, `e2/` — `lattice e1 report <dir>`, `lattice e2 compare <orig>
     <shadow>…` — `shadows/`, `units/`, `selftest/`, `facts/intrinsics-clang18.json`, `ages.py`, the full
     history clone `sqlite-vector-full/`). The target was re-ingested at 0.2.70-beta; the ledger is its
     `.hobbes/derived/graph.json`, `~/.hobbes/bench/oracle/sqlite-vector-c/oracle.json` and the intrinsics index.
   - **A gate false block, three times (`9326`, `c141`, `66c5`): a newly added
     decorator that names a module-level value (`@needs_x` where
     `needs_x = pytest.mark.skipif(...)`) reads `invented`.** Since
     ADR-146, lane A reads a decorator as a call, and the grounder
     (`derive/ground.py`'s `_parse_python`) resolves calls against
     symbols and local bindings only, never module-level assignments.
     A 14-line reproduction is in `c141`'s parent session notes
     (`9326`). The fix belongs to the grounder (a patch). It is not built;
     it is for Max to name.
   - Every route Max settled from 2026-09-17 to 2026-09-20 (ADR-123 to
     ADR-144) is built; each ADR carries his word. Standing from them:
     constructions inside a template stay `uses`; §3.8's paragraphs stay
     in the architecture ("dont split for now", again 2026-09-20).
   - **ADR-126 §3:** whether to build the "may reach through
     dispatch (not traced)" section in `tests_guarding` and `hobbes
     review` on §10.12's numbers. It would need a syntax exclusion for
     every non-dispatched call (Java `super.`/private/static/final,
     Python `super()`, C++ class-qualified) and would say no key confirms
     reach. Nothing is drawn until then.
   - **C-150's remainder** (large repos, every language): the join's
     output and the graph built from it, after ADR-115 and ADR-116 took
     the decode's and the read's share. Parked (Max: "fine for now").
   - Carried: C-139's finer extent (only if a cell shows the recall
     cost); the tracker's area for a test-only session (row 17, `—`);
     C-140's remainder (ADR-112's route 2); C-133's unit 2 (the `-I`
     read), deferred until a graded cell shows the cost.
2. **Running a session** (`calvin-harness.md` §5):
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
   - **The validating 40 are done:** the tracker reads 89 of 40, 4
     areas, 4 false blocks (`f3c1`, closed at 0.2.28-beta; `9326`, `c141`,
     `66c5`, the decorator case, open), 0 missed.
3. **A regrade against stored keys:**
   - For one cell: re-ingest, `oracle export`, then `oracle grade
     --poison` against the cell's saved `oracle.json` (as the C++
     regrades did).
   - For many: `~/.hobbes/bench/adr111-drivers/regrade3.sh` over a
     `cells.tsv` (ROOT=<worktree>); run a pre pass only when ingest code
     changed; never two passes over one clone at once.
   - A regrade after a fix carries signed direction-of-fix lines in its
     record.
4. **Carried:**
   - **The ingest's `.gitignore` edit.** Register it as a constraint or
     change it, on Max's reading.
   - **`stringer` is not in the image.**
   - **The Gradle attach route's residuals** (C-67); `recall-collapsed`
     and H-23; ADR-105/P13; the C-98 residuals.
   - **The comparative queue:** the two SQLite tools in `field.md`
     (converters first); syft's keys on a bigger box. The foreign C++
     cells are done, and the JS cells (2026-09-26). repowise's chain-line
     residual (C-94) would need a source-reading heuristic: not built.
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

## WHERE THINGS STAND (2026-09-27)

- **Languages:** Python, TypeScript, Go, Rust, Java, C and C++ supported,
  each as far as its §3.8 row (P11); Terraform/HCL structure. JavaScript
  is drawn through TypeScript's lanes and graded on five repos of its
  own (ADR-140), two with their dependencies installed (C-165). A TS/JS
  construction is drawn `calls` since 0.2.57-beta (ADR-142).
- **The Calvin harness** (ADR-107, ADR-112): each session's state is
  under `~/.hobbes/sessions/<id>/`, written by its sidecar
  `hobbes-side-<id>`; the doer mounts only `in/`, read-only, and its HOME
  is a tmpfs. Eighty-nine log files under `docs/calvin/sessions/`; the tracker reads 89 of 40 (4 areas, 4 false blocks, 0 missed; 1 deny).
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 96 cells (22 same-key rows, C++'s two among them; flask's new
  cell at 0.2.68-beta's figures); `render.py
  check` green.
- **Atlas-0** (`bench/atlas0/`, 84 tests) and **TTT** (Modal apps
  deployed and idle): held.
- **Register:** 172 entries: 126 active (98 surfaced, 24 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 29 lifted, 11 superseded, 6
  folded. Its dated notes are `docs/constraints/HISTORY.md`.
- **Oracle defect log: nothing open** (H-36, a `<genexpr>` frame keyed as a call,
  found and fixed 2026-09-20; H-33–H-35 fixed 2026-09-19,
  H-28–H-32 on 2026-09-16; `docs/oracle/oracle-defects.md`). RC-4 still
  carries its price: silencing is indiscriminate, and it hides 6 of
  C-153's rows.
- **Suites** at 0.2.71-beta (2026-09-26, every suite re-run on the host): 2,412 pytest
  (`lane_b` 17 of them, run in the rebuilt image at 0.2.71-beta), Go `./...` 399 with
  subtests (398 pass / 1 skip), 97 scip node, 47 tsextract, 52 vitest, 84 atlas0, 625
  lattice (593 pass / 32 skip without clang, after D-12's unit); oracle-lane Go 129 with subtests, 117 pass /
  12 skip on this host, which has no clang++ or cmake (the C++ fixture tests run and pass
  in the image).
- **Disk:** `~/.hobbes` is about 50 GB plus the C++ cells (ScummVM's
  cost clone at `cpp-cells/scummvm-cost` is the large one; sweep it if
  space is needed).

## NEXT (in order; no API spend)

1. **Keep dispatching named no-spend work through the harness,** one
   unit per brief (the validating 40 are done; the harness stays the way
   work is done): **the candidates under START HERE once named**;
   ADR-126's surface once
   Max decides it;
   C's residue (W1); W1/W3's no-spend items
   (the decorated-declaration line convention, the C-15 namespacing ADR,
   `fetch-java` on the egress proxy); the comparative queue's next tools
   if named.
2. **W0's remainder:** the registry-pulled image and the drift audit, when named. (The
   forgotten red review and the fixtures closed with ADR-114.)

**Held, with all spend:** the Atlas-0 T items; the TTT adapter points;
the removal A/B re-run on the 7B; a second unseen repo through the cell;
DeepSWE's decomposed protocol; `hobbes narrate` on this repo; the Calvin
experiments past E2 (`calvin-experiments.md`; E1 and E2 are run, each next run on Max's word and ceiling). The keyed Calvin runs are closed, not
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
- **After an image rebuild, restart the knowledge server** (C-65) —
  inside the session that rebuilt it, as its last step (`/mcp`
  reconnect, or stop the server's container). Do not hand it on: the
  next session starts its own container from the current image, and
  the version that opens every answer is the check.
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
