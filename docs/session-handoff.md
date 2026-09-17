# Session handoff — the single resume point

**Reviewed 2026-09-17; Hobbes 0.2.40-beta on `main`.** ADR-114's base
rule runs first on the next push: check the graph job's "base ref" step
says it reviewed from the last green run. The knowledge server serves
the image it started from until it is restarted (C-65): **restart it**
— the image was rebuilt at 0.2.40-beta at the end of this session.
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.40-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask); **a
  constraint's fix is a patch even when structural** (Max, 2026-09-13).
- **Where work happens:** on `main`; publishing belongs to Max.

The latest session's record is the 2026-09-17 "Top-level docs drift and
two found-by-use items" BUILDLOG entry (no version move). Before it, the
same day: "Top-level docs reviewed at 0.2.38-beta; one ingest of a repo at
a time" (ADR-127, 0.2.39-beta, and its later section, ADR-128,
0.2.40-beta), and "Top-level docs reviewed at 0.2.35-beta" (ADR-123–126,
0.2.36–0.2.38-beta). Earlier sessions' detail lives in their own BUILDLOG
entries; this file keeps only what the next session needs.

## ⇢ START HERE NEXT SESSION (2026-09-17)

Max's standing direction: **honesty and accuracy come before a recall
number on the extraction lane** — weigh every extraction decision
against them first. **Next** is NEXT item 1.

### What landed on 2026-09-17 (all merged no-ff; tracker 44 of 40)

- **0.2.36-beta, ADR-123:** `hobbes lanes` shapes a disagreement
  `same-line-pair` (C-70) or `cpp-withheld` (C-152) and exits 3 when
  every row is shaped (quic-go 17/17, fmt 316/316); CI passes on 3.
- **ADR-124 (bench):** strict precision beside every grade and every
  quoted figure, for every tool; "like-for-like" retired.
- **0.2.37-beta, ADR-125 R-qual:** a C++ call whose written
  specialisation contradicts lane B's `template <>` owner draws nothing
  (`qualifier-mismatch`). fmt **100%** (3,269/3,269), strict 99.73%,
  recall unchanged; args identical.
- **0.2.38-beta, ADR-125 §4:** `who_calls` marks semantic C++ calls from
  a template pattern; one `cpp-template-sites` record. C-153 unsurfaced
  → partial.
- **ADR-126 measured, nothing drawn:** the override set is javac's
  (97.4% CHA recall), but 106 of jsoup's 2,944 expanded pairs (3.6%) sit
  at calls that do not dispatch (`super.`, private, final).
- **0.2.39-beta, ADR-127:** a second ingest of a repo is refused while
  one runs (`flock` on `.hobbes/derived/.ingest.lock`, `IngestBusy`,
  exit 1, before anything is staged); artifacts written through a
  temporary and a rename, keeping their mode. Dispatched as `d238`
  (gate right-clear); the mode fix is the developer's. **C-159
  registered (surfaced).**
- **0.2.40-beta, ADR-128 (C++ lane A measured, made exact-faster, cached
  per file; the trusted stores read-only):** measured first — lane A
  passes 2 s on no timed repo but ScummVM (C++ 242 s of 258 s, Python
  around the parse, not tree-sitter). Three units, merged no-ff: `9943`
  (the index and lane A stores ride read-only in every contained step, a
  NOTE when repo code ran; C-161), `1ef9` (iterative walk,
  `HeaderIndex`, string-test pre-filter), `6956` (the JSON per-file
  cache, `HOBBES_LANEA_CACHE`; C-160). ScummVM lane A 261 s → 154 s
  every ingest, 39.5 s warm, **each step byte-identical by `cmp`**
  (217 MB); store 318 MB. All three gate right-clear; **`9943`'s verify
  read fail** (2 regressions): both tests sat outside its partition
  (`test_indexcache.py`, `test_harness.py` asserted the old mount set),
  the doer named them and the one-line fixes, applied on top (`230102e`).
- **Housekeeping:** the duplicate dispatch branch
  `hobbes/S-20260917T132013Z-e1c6` and its session directory deleted.

### Closed by the last session (no version move)

- **The top-level docs' drift:** README's status (0.2.35 → 0.2.40, ADRs
  to 128, the register and tracker counts), this file's tracker count,
  and the 2026-09-15/16 resume points folded to a paths list below.
- **The suite no longer writes the developer's timings log:**
  `tests/conftest.py` sends `hobbes.extract.timings`' log to the run's
  basetemp unless a test sets `HOBBES_CACHE_DIR` itself;
  `test_timings.py` holds it.
- **"The index key includes the mounts" was a misreading, corrected, not
  built:** the key's `ro` is the caller's list; ADR-128 §1's trusted
  stores are added in `containment.plan`, outside it. This repo's timings
  log shows the whole-miss ingests (19 of 19) only at a version bump,
  0.2.39 and 0.2.40 alike: a bump rebuilds the image (C-65), and the
  image id is in the key (ADR-122, by design), as is the helper's
  lockfile, whose root carries the version. One miss per bump is the
  key being true, not a defect.

## Where earlier sessions' drivers are (their records are the BUILDLOG's)

The 2026-09-15 and 2026-09-16 resume points were folded into their
BUILDLOG entries on 2026-09-17; only the paths a next session reaches for
stay here.

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
   - **Settled 2026-09-17 (routes Max approved):** the judged-as-before
     companion (ADR-124: strict precision instead); C-153 (ADR-125:
     withheld where the source contradicts, the rest surfaced as
     partial); `hobbes lanes` on fmt (ADR-123: exit 3).
   - **New, ADR-126 §3:** whether to build the "may reach through
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
   - **The validating 40 are done:** the tracker reads 44 of 40, 4
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

## WHERE THINGS STAND (2026-09-17)

- **Languages:** Python, TS/JS, Go, Rust, Java, C and C++ supported, each
  as far as its §3.8 row (P11); Terraform/HCL structure.
- **The Calvin harness** (ADR-107, ADR-112): each session's state is
  under `~/.hobbes/sessions/<id>/`, written by its sidecar
  `hobbes-side-<id>`; the doer mounts only `in/`, read-only, and its HOME
  is a tmpfs. Forty-four log files under `docs/calvin/sessions/`; the tracker reads 44 of 40 (4 areas, 1 false block, 0 missed).
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 90 cells (22 same-key rows, C++'s two among them); `render.py
  check` green.
- **Atlas-0** (`bench/atlas0/`, 84 tests) and **TTT** (Modal apps
  deployed and idle): held.
- **Register:** 161 entries: 117 active (91 surfaced, 22 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 27 lifted, 11 superseded, 6
  folded. Latest: C-160 and C-161 registered (ADR-128, 0.2.40-beta);
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
- **Suites** at 0.2.40-beta (2026-09-17, all pass on the host): 1,752
  pytest (`lane_b` 8 of them, run at 0.2.40-beta), Go `./...` 392 with
  subtests (391 pass / 1 skip), 87 scip node, 36 tsextract, 52 vitest,
  84 atlas0; oracle-lane Go 116 with subtests, 104 pass / 12 skip on
  this host, which has no clang++ or cmake (the five C++ fixture tests
  run and pass in the image; counted 2026-09-16).
- **Disk:** `~/.hobbes` is about 50 GB plus the C++ cells (ScummVM's
  cost clone at `cpp-cells/scummvm-cost` is the large one; sweep it if
  space is needed).

## NEXT (in order; no API spend)

1. **Keep dispatching named no-spend work through the harness,** one
   unit per brief (the validating 40 are done; the harness stays the way
   work is done): the rest of the
   review's list in the 2026-09-16 item 3's order; ADR-126's surface once
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
