# Bench drivers — where each measurement's scripts are

The probes, simulations and regrade scripts behind each extraction
decision live off the tree, under `~/.hobbes/bench/`. This file is the
index: one line per driver directory, newest first. What each run found
is its ADR's, the CHANGELOG's and the BUILDLOG entry of its date. The
resume point is [`session-handoff.md`](session-handoff.md).

Run the probes with `uv run --project pipeline python`. Every worktree
named below was removed unless it says otherwise.

## Reusable drivers

- **A TS/JS before/after over every keyed cell:**
  `c177-tagged-template/run.sh` with `cells.tsv` (every keyed TS/JS cell
  and its H-34 key).
- **One cell per language, before and after:**
  `adr141-name-mismatch/lang-regrade.sh` with `lang-cells.tsv`
  (`cjs-namespace/` and `c4-returned-value/` carry copies).
- **Many cells against stored keys:** `adr111-drivers/regrade3.sh` over
  a `cells.tsv` (`ROOT=<worktree>`).
- **The five TS cells' stored exports, oracle in the image:**
  `h33-regrade/regrade.sh <label> <tsc-oracle.mjs> <oracle>`.
- **A probe over a cell's own graph:** `c4-local-value/probe_worded.py`.
- **In-repo `external_ref`s grouped by descriptor:**
  `cjs-namespace/inrepo_ext.py`; a ten-line fixture's raw SCIP with
  `cjs-namespace/mini/dump.mjs` or `c168-remainder/mini/`.
- **The standing Python keys:** `oracle/rich-py-r2/`,
  `oracle/flask-py-r2/` and `oracle/click-py-r4/` (regenerated with the
  oracle's H-37). The clones are under `oracle/repos/` with their venvs: rich's pins
  pygments and markdown-it-py to its `poetry.lock`; flask's is
  `uv sync --group tests --python 3.12`.

## 2026-10-03 — the open-items batch (0.2.91–0.2.96-beta) and the icalendar cell

- ADR-166: `c183-go-inits/` (`before/dagger-graph.json`, `after-dagger-graph.json`, `compare.py <before>
  <after>`: Go-file evidence rows moved, by path, line, lane, type and target).
- ADR-154's amendment: `c173-platform-raise/run.sh` with `ROOT=`: rich re-ingested and graded; before is
  `c181-stdlib-import/after/rich`.
- ADR-165's amendment: `c182-residual/` (`regrade3.sh after cells.tsv`, memchr; the graph is copied to
  `after/memchr-rust/graph.after.json` by hand: the driver does not keep it).
- The `cls(…)` unit: `cls-classmethod/step0.py <repo> <key> <graph>` (each `cls(…)` site in a classmethod
  against the key's observed targets and the graph's edges; `<repo>-rows.json`).
- The held-out icalendar cell: `heldout-icalendar/` (`PREREG.md`, `run.log`) and `oracle/icalendar-py/`.
- ADR-171, an instance's `__call__`: `instance-call/step0.py <repo> <key> <graph>` (each `C(…)(…)` and once-bound
  `x = C(…); x(…)` through the build's own class and method helpers, against the key; `<repo>-rows.json`);
  `instance-call/run.sh` (ROOT=…; the after arm, six cells); `instance-call/compare.py cell=<before dir> …`
  (totals, recall, the rule's added rows by bucket, any non-rule row change).
- The held-out structlog cell: `heldout-structlog/` (`PREREG.md`, `run.log`) and `oracle/structlog-py/`.

## 2026-10-03 — C-182 registered (0.2.89-beta)

- ADR-165: `c182-rust-cfg-twins/`. It holds:
  - `measure_twins.py <graph.json> <repo>`: lane disagreements whose two answers are two defs of one
    same-header repeat. It is the step 0 probe, by header alone; the gated rule is `rustsource.cfg_twins`;
  - `regrade3.sh` (ADR-163's) and `cells.tsv` (memchr; before is ADR-163's after report);
  - `after/` (`summary.tsv`, `memchr-rust/graph.after.json` and the graded report). Compare it with
    `c180-rust-impl-qualnames/after/memchr-rust/graph.after.json` for the byte-identity check.

## 2026-10-03 — C-181 registered (0.2.88-beta)

- ADR-164: `c181-stdlib-import/`. This directory was first written as `c180-stdlib-local/` and renamed,
  because C-180 went to the Rust collision. It holds:
  - `index.sh <clone> <name>` and `dump.mjs`: raw scip-python in the image, `local` symbols kept;
  - `idx/` (rich, flask, click and pyparsing raw dumps) and the fixtures `fxc`, `fxd` and `fxe` with
    `*-idx/`;
  - `probe.py`, `probe.txt`: syntax-only reach over the raw dumps;
  - `run.sh <arm>` with `ROOT=`: the rich, flask, click and pyparsing regrade plus this repo's ingest;
  - `compare.py <repo>…`, `compare.txt`: tail per class, with edges, symbols and grade lines compared;
  - `sites.py <repo>`, `sites-<repo>.txt`: each `stdlib-import` site with the raw answer;
  - `causes.py`: each site's cause;
  - `before/` (HEAD `4c54a89`) and `after/`.

## 2026-10-03 — C-180 contained (0.2.87-beta)

- ADR-163: `c180-rust-impl-qualnames/` (`measure.py <repo> <graph.json>` the colliding Rust ids by impl
  header, written to `<repo>-collided.json`; `narrow.py <report.json> <collided.json> <graph.json>` the wide
  and narrow routes over a graded report; `rows.py` a report's rows at colliding ids; `diff.py <cell>
  <collided.json>` before/after figures, nodes and every removed evidence row; `regrade3.sh` over
  `cells.tsv`, the memchr and dagger-rust cells, `before/` and `after/` with each graph copied beside its report).
  The dagger ingest takes about 14 minutes.

## 2026-10-02 — C-178 contained (0.2.86-beta)

- ADR-161: `c178-star-reexport/` (`RESULTS.md`, `PREREG.md`; `index.sh <clone> <name>` raw scip-python in
  the image with `dump.mjs`; `mismatch.py`, `mismatch2.py <repo> <occ.ndjson> [--rows f]` — token against the
  named symbol, UTF-16 columns, classed by receiver, reusable on any Python cell; fixtures `v1`–`v6` and `fx`
  the ten-line reproductions; `rich/`, `flask/`, `click/`, `hobbes/` raw indexes; `run.sh <arm>` with `ROOT=`
  and `compare.py`, the five-repo before/after; `before/`, `after/`, `units/`; `wt/` removable).

## 2026-10-02 — the local alias and the pyparsing held-out cell (0.2.84–0.2.85-beta)

- ADR-160, C-9: `c9-local-alias/` (`RESULTS.md`; `probe.py` the exact `ast` read and simulation, `count.py`
  and `count_cls.py` the graph-free counts, `run.sh <arm>` the rich/flask/click before/after driver with
  `ROOT=`, `before/`, `after/` (pyparsing's after arm too), `probe/`, `units/` the brief and partition,
  `candidates/` twelve shallow clones counted for a held-out pick, `pp-index/` raw scip-python over
  pyparsing (`index.sh`, `dump.mjs`, `emptyenv/occ.ndjson`) — C-178's evidence; `wt/` the unit's worktree,
  removable).
- The pyparsing held-out cell: `heldout-pyparsing/` (`PREREG.md`, `lanes.txt`) and `oracle/pyparsing-py/`
  (key, report, and the held-out `graph.json` kept beside it); the clone is `oracle/repos/pyparsing` with
  its venv (`uv pip install -e '.[diagrams]' pytest`; the suite is `tests examples/tiny/tests`).

## 2026-10-01 — the honesty audit and its fixes (0.2.80–0.2.83-beta)

- ADR-159, C-177: `c177-tagged-template/` (`PREREG.md`, `RESULTS.md`,
  `count.mjs`, `join.py`, `predict.py`, `run.sh`, `compare.py`,
  `cells.tsv`, `before/`, `after/`).
- ADR-158, C-176: `c176-ts-scope/`.
- ADR-157, C-175: `c175-cpp-defs/`.
- The audit: `honesty-audit/RESULTS.md` (one fixture per language, the
  table of what each shape drew, the two counting scripts).
- The held-out rich cell: `heldout-rich/` (`PREREG.md`) and
  `oracle/rich-py/`; cell record `docs/oracle/cells/rich-py-2026-10-01.md`.
- ADR-156 and the oracle's H-37: `with-stmt/` (`RESULTS.md`, `probe.py`,
  `factory.py`, `sim.py`, `rekey.sh`, `regrade.sh`, `after/`, `units/`).
- The gate's decorator false block (C-91, 0.2.76-beta): `gate-decorator/`
  (`units/u1.md`, the brief).

## 2026-09-20 to 2026-09-30 — Python recall

- ADR-155: `py-samescope/` (`RESULTS.md`, `probe.py`, `callers.py`,
  `sim.py`, `sim74-*.json` the predictions, `before/`, `after/`, `units/`).
- ADR-154, C-173: `py-platform/`.
- ADR-150, C-170: `py-multidef/` (`index.sh` raw scip-python in the
  image, `dump.mjs`, `classify.py` — **filter out parameter monikers**,
  the `(x)` descriptors, before reading it — `rows.py`, `cells.tsv`,
  `probe/`, `built/`, `RESULTS.md`, `units/`; `wt/` removable). The flask
  and click clones' `.hobbes/derived/` hold the built branch's graph.
- ADR-145 amended (flask keyed): `c4-local-value/` (`PREREG-worded.md`,
  `probe_worded.py`, `simulate_local.py`, `real/`, `units/`).
- ADR-149: `py-factory-chain/` (`probe_chain.py`, `click_real.py`,
  `real149/`).
- ADR-148: `py-optparens/` (`probe.py --new-only --emit
  --method-positional`, `real148/click/`).
- ADR-146/147: `py-nested-defs/` (`probe.py`, `probe_b.py --show`,
  `real147/click/`).
- H-36: `oracle-defect-drivers/h36/` (`trace-hobbes-py.sh`; `hobbes-py/`
  holds a usable fresh hobbes-py key, `post-oracle.json` at `2c915a8`).
- ADR-145: `c4-returned-value/` (`simulate_real.py`'s `own_nodes` enters
  a nested def written at a body's top level — fix it before reusing it).
- ADR-139 amended: `c4-pytestmark/` (`scan.py`, `probe.py`, `missy/`,
  `missy-key-v.txt`; `try/` removable).
- Fixture reach (ADR-137, ADR-139): `c4-fixtures/` (`probe.py`,
  `probe-v1.py`, `compare.py`, `compare-v1.py`, `lookup.py`, `heldout/`
  flask and attrs, `deps/`, `units/`) and `c4-remainder/` (`probe.py`,
  `PREREG.md`, `compare.py`, `lookup.py`, `*-key-v.txt` the three verbose
  keys, `<repo>-{base,use,auto,both,built}.json`, `units/`).

## 2026-09-19 to 2026-09-26 — JavaScript (ADR-140 to ADR-144)

- The five JS cells: `js-cells/` (`grade.sh`, `regrade.sh`, `cells/`,
  `regrade/h34/` the standing keys, `fixture/minijs`,
  `oracle-trees/preact`; `c165/` — `DRAW-RULE.md`, `draw.py`, `walk.sh`,
  `draw-log.md`, `RESULTS.md`, `withheld-tree/`; the second draw's
  `DRAW-RULE-2.md`, `walk2.sh` (resumes at `walk2.sh 41`),
  `RESULTS-2.md`, `withheld-cue/`, `../cells/cue-{provisioned,withheld}/`).
- ADR-144: `cjs-namespace/` (`classify.py`, `inrepo_ext.py`, `mini/`,
  `PREREG-sim.md`, `sim.sh`, `real.sh`, `lang-regrade.sh`,
  `lang-cells.tsv`, `sim/`, `real/`, `lang/`, `units/`).
- ADR-143: `adr141-name-mismatch/` (`PREREG.md`, `count.py`, `RESULTS.md`,
  `probe_join.py`, `PREREG-sim.md`, `ingest_rule.py`, `sim.sh`, `sim/`,
  `real.sh`, `real/`, `lang-cells.tsv`, `lang-regrade.sh`, `lang/`,
  `units/`; `wt/` removable).
- C-168's remainder: `c168-remainder/`. ADR-142: `c168-construction/`.
  ADR-141: `c167-reexport/`.
- hono's `corepack` path (0.2.60-beta): `corepack-path/` (`units/`,
  `hono/` the clone, `hono-ingest-after.log`).
- H-33 to H-35: `h33-regrade/` (`before/`, `after/`, `compare.txt`,
  `h34/`). The five TS/JS cells' reports:
  `v018/{kbet-ts,ajv-ts,cheerio-ts,zod,hono-build}/report.json`.
- The comparative JS cells: `comparative/run-js-cell.sh`,
  `comparative/<tool>-<repo>/`, `at5/` in each repowise cell.

## 2026-09-15 to 2026-09-19 — C and C++

- Headers (ADR-138): `c133-include-path/` (`claim.py`, `place.py`,
  `regrade/` the five cells, `scummvm-ingest.log`, `units/`).
- ScummVM and the vacated line (ADR-136): `scummvm-scale/` (`vacated.py`,
  `sample.py`, `regrade/`, `units/`); `lane-a-symbol-near/probe.py`.
- C-164's wrong callers (ADR-135): `c164-wrong-callers/` (`findstream.py`
  a clone's cached facts stream; `shapes.py`, `nameref.py`;
  `simulate.py` + `PREREG-sim.md`; `inspect_r1.py`; `regrade.sh` with
  `ROOT=`/`OUT=`, which borrows `c145-extent`'s `oracle`, `probe.py` and
  `compare.py`; `regrade/`; `units/`).
- A lost definition's extent (ADR-134): `c145-extent/` (`probe.py` —
  `probe-v1.py` its first form — `simulate.py`, `simulate_r3.py`,
  `regrade.sh`, `regrade/`, `units/` with `u1-fix.patch`; `oracle` the
  binary built from the tree).
- The join's claim (ADR-133): `join-claim/` (`probe.py` step 0,
  `run-all.sh` and `out/` the 24 clones; `ingest_bypos.py` the in-memory
  rule, `sim.sh` + `sim-cells.tsv` + `diff.py`, `PREREG-sim.md`, `sim/`;
  `regrade.sh` + `regrade-cells.tsv` + `compare.py`, `PREREG-regrade.md`,
  `regrade/` the 44 cells before and after, `final/fmt-cpp/`; `units/`).
- Constructions (ADR-132): `cpp-constructions/` (step 0: `probe.py`,
  `classes.py`, `PREREG-args.md`, `fmt-out/`, `args-out/`; step 1:
  `simulate.py` — `simulate-v1.py` its first form — `grade.sh`,
  `buckets.py`, `tokenpos.py`, `PREREG-args-sim.md`, `fmt-sim2/`,
  `args-sim2/`; `regrade.sh`; `final/` the 0.2.44-beta grades; `units/`;
  `wt/` removable). Run as `probe.py <clone> <facts.ndjson> <report.json>
  <out-dir>`; the facts stream is the cell's newest
  `~/.hobbes/cache/index/*.facts.ndjson`.
- Operator `uses` withheld (ADR-131 amended): `c153-operator-uses/`
  (`ingest_withheld.py`, `diff.py`, `before/`, `after/`, `regrade.sh`,
  `final/` the 0.2.43-beta grades, `units/`; `wt/` removable).
- Operators (ADR-131): `c146-operators/` (`probe.py`, `match.py`,
  `exact.py`; `simulate.py`, five variants; `template_split.py`,
  `tokencheck.py`, `count_tokens.py`; `PREREG-args.md`; `regrade.sh`;
  `final/` the 0.2.42-beta grades; `units/`).
- C++ recall (ADR-129, ADR-130): `c145-recovery/` (`probe.py`,
  `analyze.py`, `arity.py`; `PREREG-args.md`; `regrade.sh`;
  `ingest_no_arity.py` the rule-off wrapper; `p84-named-rows.json`;
  `final/` the 0.2.41-beta grades; `units/`; `wt/` removable).
- Lane A's C++ cache (ADR-128): `laneA-cache/` (`equiv.py`, `split.py`,
  `cacheproto.py`, `scummvm-tree.json`, `units/`).
- C++ close-out and the facts stream (ADR-113, ADR-115/116):
  `cpp-cells/{fmt,args}-cell/`, `cpp-cells/scummvm-cost/` (the large
  clone; sweep it if space is needed), `cpp-drivers/closeout-task.md` and
  `probes/` (`decode_equiv.mjs`, `py_facts_probe.py`, `capture_join.py`,
  `probe_helper.py`).
- The foreign C++ cells: `comparative/{codegraphcontext,repowise}-{fmt,args}/`,
  with `run-cpp-cell.sh` and `regrade-cpp-cell.sh`.

## Earlier (ADR-120 to ADR-127, the oracle's defects)

- The ingest lock (ADR-127): `ingest-lock/`.
- ADR-123 to ADR-126: `lanes-shape-drivers/`, `c153-rule/`
  (`measure.py`, `regrade.sh`, the briefs), `dispatch-reach/`
  (`measure.py`, jsoup/click/args JSON).
- The index cache (ADR-122): the store `~/.hobbes/cache/index/` (30-day
  sweep at the next write); timings `~/.hobbes/cache/timings/<key>.jsonl`.
- Unevaluated operands (ADR-121): `uneval-drivers/`.
- The override set (ADR-120): `relationships-probe/`.
- O10's defects: `oracle-defect-drivers/` (task files, partitions,
  `rerun-cpp-key.sh`, `regrade-stored.sh`, `regrade-foreign.sh`,
  `foreign-pairs.tsv`) and its `regrade-out/`.
- The gate's arrow-parameter fix (C-91): `gate-drivers/`, a pattern for
  a brief.

## Experiments (held or closed)

- Calvin's lattice (closed on sqlite-vector, 2026-09-29):
  `calvin-lattice/` (`e1/`, `e2/` — `lattice e1 report <dir>`,
  `lattice e2 compare <orig> <shadow>…` — `shadows/`, `units/`,
  `selftest/`, `facts/intrinsics-clang18.json`, `ages.py`, the full
  history clone `sqlite-vector-full/`; `route1-s1/` with `PREREG.md`,
  `PREREG-s2.md` and their `RESULTS`). The ledger is the target's
  `.hobbes/derived/graph.json` (ingested at 0.2.70-beta),
  `oracle/sqlite-vector-c/oracle.json` and the intrinsics index.
- Atlas-0: `bench/atlas0/scripts/modal_atlas0.py` (in the tree);
  `modal_atlas0.py mech` for checkpoint checks.
- TTT: the 3,000-step adapter on the Modal volume at
  `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/cc9e99c14215`.

## Not usable as stored

- The hobbes-go cell cannot be regraded on its stored key, nor hobbes-py
  on its old ones: their clone (`adr111-before/hobbes-wt`) is gone. A full
  regrade needs a worktree at the key's sha or fresh keys (a fresh
  hobbes-py key is in `oracle-defect-drivers/h36/`).
- `~/.hobbes/cache/stage/` holds small leftover `.scip` outputs.
