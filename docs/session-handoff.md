# Session handoff — the single resume point

**Reviewed 2026-09-18; Hobbes 0.2.48-beta on `main`.** CI is green on
`d1f52a1` (0.2.47-beta, pushed 2026-09-18; run 35377779488); everything
since — the `lane-a-symbol-near` read, ScummVM's scale read, ADR-136,
unit `e78d`, 0.2.48-beta — is unpushed. The proxy and
the image were rebuilt at 0.2.48-beta and the repo re-ingested at the end
of this session; the knowledge server serves the image it started from
until it is restarted (C-65): **restart it.**
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.48-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask); **a
  constraint's fix is a patch even when structural** (Max, 2026-09-13;
  confirmed for ADR-129 on 2026-09-17).
- **Where work happens:** on `main`; publishing belongs to Max.

The latest session's records are the five 2026-09-18 (late night) BUILDLOG
entries — the third ("the `lane-a-symbol-near` rows read"), the fourth
("ScummVM as a scale read", ADR-136 proposed) and the fifth (ADR-136
built, 0.2.48-beta) — and before them: "C-164's wrong callers counted key-free and simulated" (ADR-135
proposed) and "a lane A symbol the index contradicts, built" (ADR-135
accepted, 0.2.47-beta). Before them, the four 2026-09-18 entries (ADR-133
proposed and built, ADR-134 proposed and built), and 2026-09-17's.
Earlier sessions' detail lives in their own BUILDLOG entries; this file
keeps only what the next session needs.

## ⇢ START HERE NEXT SESSION (written 2026-09-18, night)

Max's standing direction: **honesty and accuracy come before a recall
number on the extraction lane** — weigh every extraction decision
against them first. Max approved Route A (C++ recall) on 2026-09-17;
its list is below, each item measured before it is designed.

**ADR-136 is built (0.2.48-beta, Max: route a):** the mint reads a
definition row at a line R1 vacated even in a file that parsed clean.
ScummVM: 260 symbols in 19 files exactly as predicted, 255 with an
extent, 30 of 30 sampled names right, byte-identical twice; the four
graded cells and click row-identical. Unit `e78d` (77 turns, $6.60),
gate right-clear, verify pass; tracker 54 of 40. P130 missed by two and
P131 was worded wrongly (a re-home changes an edge's `from`; compare
evidence rows). Records: §10.21, ADR-136's *Built*, the fifth late-night
BUILDLOG entry. Drivers: `~/.hobbes/bench/scummvm-scale/` (`vacated.py`,
`sample.py`, `regrade/` the five cells, `units/` the brief and log; its worktree
was removed).

**Not waiting on Max:** the review's remaining items (pytest fixtures as
edges, C-4; the compile database's `-I` path at lane A; the docs
restructure), each measured first.

Closed on 2026-09-18 with nothing built: the `lane-a-symbol-near` item
(19 rows on four cells: 10 defaulted or deleted constructors beside an
overload, 8 the other arm of an `#if`, 1 `typedef struct` line
convention; every one refused by the next rule anyway — driver
`~/.hobbes/bench/lane-a-symbol-near/probe.py`); **ScummVM's scale read**
(`~/.hobbes/bench/scummvm-scale/`: cold 9 min 04 s, warm 2 min 20 s and
byte-identical; `contradicted` 3.7 s, mint 1.9 s, rehome 0.8 s; lane A's
cold C++ walk 228 s against 135 s at ADR-128, 23.6 s warm; R1's 401
names read, no false flag; `vacated.py` the finding); and the caller
probe's naming grain (`c145-extent/probe.py`: `agree-friend`,
`agree-nested`; fmt wrong-caller 32 → 3, the old probe kept as
`probe-v1.py`).

Small and no-spend, any time, optional: a `lane_b` end-to-end case for ADR-135 (the unit's
ingest test feeds lane B's facts by hand; it needs a fixture
tree-sitter-cpp misreads *and* scip-clang compiles — an annotation macro
after a declarator, in `minicpp` or a fixture of its own, without moving
the lines other tests pin).

### What landed on 2026-09-18, late night (merged no-ff; tracker 53 of 40)

- **The doc review first:** one drift (the handoff's push line),
  corrected; `c145-extent/wt` removed after checking its three modified
  files were `main`'s.
- **C-164 counted key-free, then Max: route (a) for ADR-135.** 18
  misnamed lane A symbols and 2 swallowing extents, all on fmt; the
  index's definition row does **not** separate them, a lane B reference
  at exactly the symbol's name token does (18 of 18, no false flag; read
  loosely it flags `Base::KickOut` beside `Options::KickOut`).
- **ADR-135 built (C-164 unsurfaced → partial, 0.2.47-beta):**
  `name_col` on lane A's C++ functions and methods (`lanea-cpp v5`);
  `minted.contradicted` before the mint — R1 removes the symbol and its
  facts take the module's scope, R2 re-reads a swallowing extent from
  the braces; `graph.json`'s `lane_a_contradicted` and one summary line.
- **The brief's premises were read in the tree first** (ADR-135,
  *Accepted*: the identifier node's column, 0-based as lane B's; where
  the resolutions and definition rows are; the counts in a graph block,
  not the `parse` record) — and the first real ingest matched.
- **Checked, not graded (§10.20):** every graded number ±0 on fmt, args,
  cJSON, sqlite-vector; click identical. fmt 18 refused (13 + 5), 1
  extent re-read, **wrong-caller 105 → 32, 18 right, 55 lost, no right
  row moved**; `holds-a-definition` 19 → 13; two definitions newly
  minted on vacated lines (the simulation did not model them: agree and
  lost each missed by one row beyond ± 2). One test's borrowed reach
  returned.
- Unit `c2cc` (68 turns, $6.61), gate right-clear, verify pass.
- Drivers: `~/.hobbes/bench/c164-wrong-callers/` (`findstream.py` a
  clone's cached facts stream; `shapes.py`, `nameref.py` step 0;
  `simulate.py` + `PREREG-sim.md`; `inspect_r1.py`; `regrade.sh` with
  `ROOT=`/`OUT=`, which borrows `c145-extent`'s `oracle`, `probe.py` and
  `compare.py`; `regrade/` the five cells; `units/` the brief and log;
  its worktree was removed). Run the probes with `uv run --project
  pipeline python`.

### What landed on 2026-09-18, night (tracker 52 of 40)

- **Top-level drift fixed first** (`1f10357`): the handoff's CI line and
  the workstreams header.
- **Max: route (a) for ADR-134.** Before the brief, refusal 3 was
  measured (`simulate_r3.py`) and **fired 19 times on fmt** where the
  ADR said "not seen": 13 macro-generated methods whose brace match
  borrowed the next function's body — a wrong *node* no moved row showed
  — and 6 true bodies holding a C-164 symbol. Built in its simplest
  form: refused where any other function or method starts inside.
- **ADR-134 built (C-145 narrowed again, 0.2.46-beta):** a minted
  function or method gets `end_line` from a brace match on the blanked
  text and says `extent: "braces"`; refusals `no-body`, `runs-off`,
  `conditional-inside`, `holds-a-definition` in `graph.json`'s
  `minted.extents` with `read` and `rehomed`; `minted.rehome` after the
  mint moves a `calls`/`uses` fact whose scope is the module's id, empty,
  or a lane A symbol starting before the extent; the ingest summary and
  `who_calls` say which minted symbols are scopes.
- **The brief was wrong, and the real ingest said so:** it claimed a
  file-scope site has an empty scope; lane A's C and C++ sites carry the
  module's id. First run: 2 of 16 rows moved on args. The fix and the
  `extent` mark (a one-line body re-homes, a refusal does not: 56 fmt
  rows) are the developer's commit after the merge, with a `lane_b`
  end-to-end case.
- **Checked, not graded (§10.19):** every graded number ±0 on fmt, args,
  cJSON, sqlite-vector; click identical. fmt 1,346 extents, 34 + 19
  refused, 1,290 `calls` + 760 `uses` rows re-homed, agreeing 6,392 →
  7,610, **lost 1,436 → 188, no right row moved**, reach pairs 3,183 →
  6,131. args lost 15 → 0. P116's lost count missed (188, not 165: the
  prediction's arithmetic).
- Unit `368a` (59 turns, $5.88), gate right-clear, verify pass.
- Drivers: `~/.hobbes/bench/c145-extent/` (`probe.py`, `simulate.py`,
  `simulate_r3.py`, `regrade.sh` with `ROOT=`/`OUT=` — before/after on
  the same clones, grades, probe and `compare.py`; `regrade/` the five
  cells; `units/` the brief, the log and `u1-fix.patch`; `oracle` the binary
  built from this tree; its worktree was removed 2026-09-18).
- scip-clang 0.4.0 emits no `enclosing_range` (checked in the image).

### What landed on 2026-09-18 (merged no-ff; tracker 51 of 40)

- **Max's two calls:** constructions inside a template stay `uses`
  (closed); the join's by-name claim measured, then built (route a).
- **ADR-133, the join claims by position (C-163 registered and lifted,
  C-162 narrowed, 0.2.45-beta):** the claim's key is the matched
  resolution's `(file, line, name, col)`. Another column's resolution
  goes through the unclaimed loop (operator rule, construction rule,
  else `uses`); the matched occurrence's own column stays hidden
  (ADR-104, an override's alternate); a columnless **site** keeps the
  by-name claim.
- **Measured first** (`~/.hobbes/bench/join-claim/`): 7,308 resolutions
  hidden on 25 clones, 1,158 at the matched column, the rest true facts —
  Java's declared type beside `new`, a TS interface beside its function,
  a Go return type beside a method call, fmt's 19 constructions.
- **The grades, 44 stored-key cells, before and after on the same
  clones (§10.18, P108–P113 met):** fmt **6,993 → 7,012, 0 contradicted,
  strict 99.62%, 30.3% → 30.4%**; 43 cells row-identical; 1,785 `uses` +
  11 `calls` symbol edges added, none removed; two module edges, both
  read true. No key judges a `uses` edge.
- Unit `3569` (26 turns, $1.78), gate right-clear, verify pass.
- The hobbes-py and hobbes-go cells could not be regraded: their clone
  (`adr111-before/hobbes-wt`) is gone. A next full regrade needs a
  worktree at the key's sha or fresh keys.

### What landed on 2026-09-17 (merged no-ff; tracker 50 of 40)

- **ADR-132, constructions (C-162 registered and narrowed):** lane A's
  C++ walk records construction *tokens* (the declared name of
  `T x(args)` / `T x{…}` / `T x;` in a declaration that names a type and
  sits directly in a block or at namespace scope, a member initialiser's
  name, the `{` of a braced argument or return, the `=` of a defaulted
  parameter, the type's start in `T{…}` / `new T(…)`), packed beside the
  operator tokens. The join draws a semantic `calls` fact where a lane B
  reference **onto a constructor** (`minted.constructor_lines`: the
  definition row's moniker ends `T#T(…)`) sits at exactly that token,
  outside a template; inside one it stays `uses` and is counted
  (`graph.json`'s `constructions` block, one line in the ingest summary).
  Cache format `lanea-cpp v4`.
- **Measured first** (`~/.hobbes/bench/cpp-constructions/`): fmt's 8,047
  missed pairs are 80% the macro class (C-131), 7% gtest's
  `new TestClass`, 10% no lane B reference, 152 drawable; args (held out)
  383 of 889 drawable, 484 implicit `EitherFlag` conversions the index
  does not emit. Drawn naively on fmt: 95 contradicted. One wrong class
  found by the hand read and excluded before args ran (a constructor's
  own declaration under a macro-broken class head).
- **The grades, stored keys, 0.2.44-beta:** args **2,198 → 2,567
  confirmed, 0 contradicted, 62.5% → 72.9%**, the probe's export row for
  row; fmt **6,901 → 6,993, 0 contradicted, 30.1% → 30.3%, strict
  99.62%**; cJSON and sqlite-vector identical. P103–P107 met.
- **Recorded misses:** P102's count (fmt 6,993 where 7,012 ± 3 was
  predicted — item 2 above); step 0's P-c1 and P-c3 on args; P-s5 by one
  row.
- **ADR-131 amended (Max: route a), C-153 narrowed a third time
  (0.2.43-beta):** a lane B reference named `operator…` at exactly an
  operator token inside a template draws nothing — no `calls`, no `uses`.
  fmt −156 `uses` symbol edges, args −24, every graded number ±0; the one
  module edge gone on each cell was wrong. The price: 175 key-confirmed
  in-template rows on fmt were true dependencies.
- Units: `4033` (36 turns, $1.78) and `4834` (84 turns, $8.57), both gate
  right-clear, verify pass.
- **Housekeeping:** seven merged worktrees removed (branches kept);
  `ttt/hobbes-base` stays. `cpp-constructions/wt` is this session's,
  removable.

### C++ recall — what is next, in order, each measured first

1. **Constructions: built (ADR-132).** What is left is registered in
   C-162: the macro class, templates, untokened conversions and
   references the index does not emit. The using-declaration claim
   closed with ADR-133.
2. **A lost definition's extent: built (ADR-134, 0.2.46-beta).** What
   is left is in C-145: the refused extents (34 conditionals, 19 holding
   a definition on fmt) and definitions nothing names.
2a. **C-164's wrong callers: built (ADR-135, 0.2.47-beta).** What is
   left is in C-164: no index, uncompiled code, other recovery shapes,
   and the swallowed tests, which are still not symbols (Route B,
   blanking known-empty macros, is the macro class's — C-131, parked).
3. **The `lane-a-symbol-near` rows: read, nothing to build**
   (2026-09-18): no line-convention class; each row is refused by the
   next rule anyway.
4. **ScummVM as a scale read: done** (2026-09-18, BUILDLOG; it found
   ADR-136's remainder, built at 0.2.48-beta). As the item was written: symbols minted, edges gained,
   the mint's seconds, **and the operator walk's cost** —
   `_unevaluated` and `_in_template` each climb to the root per token,
   about 3.2 million tokens there (a 600-file sample: 2.09 tokens per
   call expression). The lane A cache pays it once per file.
5. **Operators at a macro's name** (3,011 references on fmt) are the
   macro class's question (C-131, parked): the position is the
   invocation's, and the key contradicts 73 of them.
6. TS's floor shapes stay off the table (Max, 2026-09-10); Claude's read
   on 2026-09-17 was not to reopen them before C++ is done
   (class-property functions are 6.2% of one cell).

## Where earlier sessions' drivers are (their records are the BUILDLOG's)

The 2026-09-15 and 2026-09-16 resume points were folded into their
BUILDLOG entries on 2026-09-17; only the paths a next session reaches for
stay here.

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
   - **Settled 2026-09-18:** ADR-136's route (a) — built (0.2.48-beta);
     ADR-135's route (a) — built (0.2.47-beta);
     ADR-134's route (a) — built (0.2.46-beta);
     the join's claim by position — built (ADR-133, 0.2.45-beta);
     constructions inside a template stay `uses`.
   - **Settled 2026-09-17 (Max: "go with recommended"):** constructions —
     the token rule (ADR-132, 0.2.44-beta); C-162 registered.
   - **Settled 2026-09-17 (Max: route a):** the wrong `uses` edges at
     dependent operators — withheld (ADR-131 amended, 0.2.43-beta).
   - **Settled 2026-09-17 (routes Max approved):** the judged-as-before
     companion (ADR-124: strict precision instead); C-153 (ADR-125:
     withheld where the source contradicts, the rest surfaced as
     partial); `hobbes lanes` on fmt (ADR-123: exit 3).
   - **ADR-126 §3:** whether to build the "may reach through
     dispatch (not traced)" section in `tests_guarding` and `hobbes
     review` on §10.12's numbers. It would need a syntax exclusion for
     every non-dispatched call (Java `super.`/private/static/final,
     Python `super()`, C++ class-qualified) and would say no key confirms
     reach. Nothing is drawn until then.
   - **Nothing in the oracle's defect log is open.** H-28–H-32 were all
     fixed on 2026-09-16; fmt has no contradiction left.
   - **ADR-121 §2's choice — kept** (Max approved the routes 2026-09-17):
     lane B's occurrence at an unevaluated site stays a `uses` edge, a
     true dependency; nothing to build.
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
   - **The validating 40 are done:** the tracker reads 54 of 40, 4
     areas, 1 false block (`f3c1`, closed at 0.2.28-beta), 0 missed.
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
     cells are done (item 7).
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

## WHERE THINGS STAND (2026-09-18)

- **Languages:** Python, TS/JS, Go, Rust, Java, C and C++ supported, each
  as far as its §3.8 row (P11); Terraform/HCL structure.
- **The Calvin harness** (ADR-107, ADR-112): each session's state is
  under `~/.hobbes/sessions/<id>/`, written by its sidecar
  `hobbes-side-<id>`; the doer mounts only `in/`, read-only, and its HOME
  is a tmpfs. Fifty-four log files under `docs/calvin/sessions/`; the tracker reads 54 of 40 (4 areas, 1 false block, 0 missed).
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 90 cells (22 same-key rows, C++'s two among them); `render.py
  check` green.
- **Atlas-0** (`bench/atlas0/`, 84 tests) and **TTT** (Modal apps
  deployed and idle): held.
- **Register:** 164 entries: 119 active (92 surfaced, 23 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 28 lifted, 11 superseded, 6
  folded. Latest: C-164 narrowed again (ADR-136, 0.2.48-beta; no entry added);
  C-164 narrowed and partial (ADR-135, 0.2.47-beta; no
  entry added); C-145 narrowed again (ADR-134, 0.2.46-beta; no entry
  added); C-164 registered unsurfaced (2026-09-18); C-163 registered and lifted, C-162 narrowed (ADR-133,
  0.2.45-beta); C-162 registered and narrowed (ADR-132, 0.2.44-beta);
  C-153 narrowed a third time (ADR-131 amended,
  0.2.43-beta; no entry added); C-146 narrowed (ADR-131, 0.2.42-beta; no entry added);
  C-145 narrowed and C-153 narrowed a second time
  (ADR-129, ADR-130, 0.2.41-beta; no entry added); C-160 and C-161 registered (ADR-128, 0.2.40-beta);
  C-159 registered (ADR-127, 0.2.39-beta); C-153 narrowed then partial (ADR-125, 0.2.37/0.2.38-beta);
  C-152 amended and C-70 settled (ADR-123, 0.2.36-beta); C-158
  registered (ADR-122, 0.2.35-beta).
- **Oracle defect log: nothing open.** H-28–H-32 all fixed 2026-09-16
  (H-32, the key's site in an unevaluated operand, opened RC-11).
  RC-2 gained its sixth sighting and closed with H-31 (macro-carried
  code keeps getting the wrong position); RC-3 and RC-8 closed-policy
  (D-O4 gained the member-call bullet; the C reader's key is
  owner-qualified as javac's is); RC-4 closed for H-30 and carrying its
  price — silencing is indiscriminate, and it hides 6 of C-153's rows.
- **Suites** at 0.2.48-beta (2026-09-18, all pass on the host): 1,977
  pytest (`lane_b` 10 of them, run at 0.2.48-beta), Go `./...` 396 with
  subtests (395 pass / 1 skip), 87 scip node, 36 tsextract, 52 vitest,
  84 atlas0; oracle-lane Go 116 with subtests, 104 pass / 12 skip on
  this host, which has no clang++ or cmake (the five C++ fixture tests
  run and pass in the image; counted 2026-09-16).
- **Disk:** `~/.hobbes` is about 50 GB plus the C++ cells (ScummVM's
  cost clone at `cpp-cells/scummvm-cost` is the large one; sweep it if
  space is needed).

## NEXT (in order; no API spend)

1. **Keep dispatching named no-spend work through the harness,** one
   unit per brief (the validating 40 are done; the harness stays the way
   work is done): **the C++ recall list under START HERE first**; then
   the review's remaining items (pytest fixtures as edges, C-4; the
   compile database's `-I` path at lane A; the docs restructure);
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
