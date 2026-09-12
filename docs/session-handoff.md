# Session handoff — the single resume point

**Reviewed 2026-09-11; Hobbes 0.1.20-beta on `main`** (0.1.8-beta is
tagged `v0.1.8-beta`; 0.1.9-beta to 0.1.20-beta are **untagged — tags
are Max's call**). **Numbering (Max; ADR-103's third amendment): the
layer stays on 0.1.x, patch by patch.** Work remains on `main`;
publishing belongs to Max. The session's record is the 2026-09-11
BUILDLOG entry.

## ⇢ START HERE NEXT SESSION: Calvin M0-Gate ran through WP-21 on ten keys — the floor holds as a safety property, not a helper; widening and the repair turn's design are Max's

1. **The round (2026-09-11).**
   - **The record:** [`docs/calvin/calvin-m0-gate.md`](calvin/calvin-m0-gate.md) (§0b the orchestrator's pins, §10 the results and every ruling, dated); the rows in [`docs/calvin/cells/calvin-m0-gate-2026-09-11.md`](calvin/cells/calvin-m0-gate-2026-09-11.md); each package's artifacts and `report.md` under `~/.hobbes/bench/calvin-gate/wp-17` … `wp-21` (and `wp-18b`/`c`/`d`).
   - **The idea:** keep the world, move the agent. O (the file-tools agent loop, Haiku 4.5, A0) works once per key; `hobbes gate` judges its finished diff at the parent; arms O, O+gate (post hoc) and O+gate+repair (one bounded turn on blocked rows). T-as-form is retired from measurement.
   - **WP-17:** fzf (pin `f7ae439ff5b2`), 20 readable post-cutoff keys stratified by shape (7/5/5/3), W 1.0; Hobbes' own repo reads 26 of 28 beside it.
   - **WP-18 → 0.1.18-beta:** `hobbes gate`; D-s (gold 9/20 at the template partition) fixed by `reach` as the default. **WP-19:** the controls hold (gold 20/20 clear; seeded invented / partition / arity 20/20 each; *unknown* 9/9; 89/89 byte-identical).
   - **WP-20:** $14.0 expected for 20 keys; the pre-flight on a scripted endpoint found D-u, D-v, D-w → **WP-18b, 0.1.19-beta** (gate v2's message).
   - **Max at the spend gate:** 10 keys "for now", the manifest withheld, WP-20's brake; the hard cap $11 set by the orchestrator (Max named no dollar figure).
   - **D-x (the round's finding):** at key 1 O ran `git show` on its key commit in its own clone and copied gold. Four of rounds 1–2's ten O sessions had done the same — round 1's two "recalled" keys, round 2's `ed65b65095eb` pass (round 2's O now reads **1 of 3**). **WP-18c, 0.1.20-beta:** O's repo is cut at the parent; one sessions root per session. Both rounds amended beside their originals. Max: key 1 re-run clean (a §0 exception), then continue.
   - **WP-21 (10 keys, $5.03 of $11):** O pass 7 / fail 1 / empty 2; O+gate pass 6 / blocked 2 / empty 2; the repair raised no pass (0 of 2). Blocks: `a650900edac4` `[partition]` (O's pass there not a solve — gold's tests do not build over it) and `12e24d368c90` `[unimported]` (a real compile error, which the build also caught). Invented 0, *unknown* 0. Every O session hit the 30-turn cap. **§5's second reading (provisional, n = 10): the floor exists as a safety property, not a helper — `hobbes gate` ships as a detector.** D-y (a no-edit repair scored as an empty diff) fixed after the run (WP-18d, driver only).
2. **The next step — named, not built, held (Max's):**
   - **Widening** to keys 11–20 (≈ 8 more fit under the $11 cap at $0.46 a key; the block rate's interval is [0.0, 0.5]).
   - **The repair turn's design:** both repairs spent their one call on a read — the flagged lines and the import block in the message, or one read plus one edit.
   - **§7 step 1, O+world;** an **egress allowlist** for C-124 (the network channel is open: the policy allows `python`/`pip`).
   - The design's ADR takes its number on Max's *accepted* (ADR-106 is held for M0-Go).
3. **Findings for Max from this round:**
   - **D-x** and the rounds 1–2 amendments (above). **The pass metric:** O's 7 passes carry `gold_tests` pass on 2, n/a or not applying on 4, build-fail on 1 — pass means "builds and breaks no guarding test", not "solves".
   - **D-r (open, instrument):** on a Python key, `hobbes verify`'s `--shared` clone makes `git` fail in the container and `built_by()` falls back.
   - **The blind-spot map's sites are file-grain** (C-123); **`stringer` is not in the image** (`go:generate` fails on both trees in every fzf verify; no verdict moves).
   - **Round 1's findings stand:** `hobbes ingest` edits the target's `.gitignore`; the harness's `isolation: worktree` cuts from a stale commit; M0's Sonnet 5 pricing reads $3 / $15 against on-box $2 / $10; Calvin runs take `--key-name anthropic_key`.

4. **Still waiting on Max from 2026-09-10 (untouched this session):**
   - **The Gradle attach route (0.1.10-beta; C-67 narrowed, ADR-096
     amended):** a Gradle unit gets scip-java's javac plugin from
     Hobbes's own init script (the oracle's route), runs the wrapper
     offline and aggregates with `scip-java aggregate`. Severed-Chains:
     capture 0.0% → 100.0%, recall 23.5% → 60.8% at 100% precision;
     spring-petclinic's Gradle route matches its Maven route. To look at:
     C-67's three residuals (a build that replaces `compilerArgs` after
     configuration; Gradle external symbols with no artifact name, the
     coverage line read from the build's `dependencies.txt`; Kotlin not
     compiled under the plugin). Every Hobbes cell was then regraded on
     0.1.10-beta (`~/.hobbes/bench/v0110/`, 41 cells, every one to the
     digit).
   - **The `recall-collapsed` line (ADR-089 amended) and H-23** (the
     Java key's member-bare names, now owner-qualified; the four Java
     keys re-merged with every position unchanged; `oracle-defects.md`).
   - **ADR-105 / P13, the C-98 residuals, the hono record's fourth
     block**, as listed in the 2026-09-10 BUILDLOG.
   - **The comparative queue's item 4:** the next converters
     (codebase-memory-mcp, colbymchenry/codegraph), and whether the
     competitor cells run under the sandbox image (C-96 narrowed).
5. **Recorded, not built — `build-logic/` (ADR-097, C-66):** keyed on
   the settings file's `pluginManagement { includeBuild(..) }` when a
   real repo degrades on one, never on the name. **Off the table for
   now (Max):** the three floor shapes and the Jelly key grain
   (`oracle-misses.md`, W1).
6. **W0 remains open:** the graph CI job forgets earlier red reviews;
   `go/internal/version` and the union fixture's ownership treatment
   still need resolution; the registry-pulled image and the drift audit
   open when named. Then the no-spend queue (NEXT).
7. **Practical — restart the knowledge server first.** The image is at
   0.1.20-beta (rebuilt after `05246b6`), and this session's server
   started on an older image; a server keeps the image it started on
   (C-65). Restart `.mcp.json` → `sandbox/knowledge-serve` before
   trusting a count. This repo was re-ingested at 0.1.20-beta.

---

## Calvin M0 (Python) — held since the spend rule, unchanged from 2026-09-04

The design is `docs/calvin/calvin-potential.md` (M0 v2, run on four
keys; §10 the results, §8 the step record; the charter
`docs/calvin/calvin-charter.md`); the per-task record is
`docs/calvin/cells/calvin-m0-probe-2026-09-03.md` (its seventh and
eighth addenda); every number is reproduced by
`pipeline/scripts/calvin_probe.py` from `~/.hobbes/bench/calvin/`. Step
6 on Sonnet 5 read T pass 1 of 4 at $6 and O 1 of 4 at $17. The four
no-spend fixes (template v1, importer tests as guards at tier `import`,
the box policy, O's `--token-budget`) are in and exercised with no
model; the import tier's test holes are the next cost door (named, not
built). Held: the wider run (a stated ceiling, four keys first; order
$30–60 for 28 keys × three arms). M0-Go's §7 step 3 (these 28 keys under
the Go-round protocol) waited on a floor that was not established.
Still open: Max's review of ADR-100, the step-6 record and the
2026-09-03 lifts (C-72–C-80, C-85); M0's design takes the next free ADR
number on *accepted* (M0-Go's is 106). Practical: arm O runs with
`--nudge-after 15 --stall-after 20`; Sonnet 5 rejects `temperature`
(`--sampling model-default`).

## Atlas-0 — held from 2026-09-07: Max reads the B4 record; then the T that carries the abstention act, and T_v2

**Done 2026-09-07** (BUILDLOG; `docs/atlas0/atlas-0.md` § Addendum):
the §A.1 checks on saved weights (B1 reads through eight heads in
layers 2/4/5 and stores in the FFNs of layers 2–7; B2's refusal is a
linear direction in the row, not a norm; B3's copy circuit is seven
heads of layer 0 plus L4H3); B4, typed attention (K = 1 is B1 to the
digit; a cell $0.18, 3× the estimate); the λ sweep on seed 1 (the
pressure decides the route; half the layers collapse to identity
operators); the grid at λ = 0, one run per seed (`runs/v2-b4-grid`, 30
cells, $3.38): B4 = B1 on storing and the sibling pull, the copy route
weaker in every arm without separating, and **`UNDEFINED` 0.00 in both
phrase arms** — the reading regime does not learn the act; §A.7 branch
3 (B4-given: typing given, not learned) is what the results select.
$22.28 assumed of $25.

**What needs Max:**

1. **The T that carries the abstention act.** §A.5.3 (does refusal
   travel) cannot be read at T_v2: no block refuses anything. Either
   the memorising T (3,500 steps, batch 64 — where v0/v1 read refusal;
   the reading route is then gone) or §A.7 branch 2's computed target
   (`NO_EDGE` from the typed signal), in a B4-given block if branch 3
   is taken. Each is a design choice; the grid at either is ~$3.5–4 (B4
   cells at $0.18) plus B1's.
2. **The grid's second run** (§6.6's union): ~$3.8, taking the item to
   ~$8.5 and the programme to ~$26 against the $25 ceiling; nothing in
   the tables suggests the copy-route difference would separate.
3. **T_v2 for the v2 grid proper** (open since 2026-09-06): at 3,100
   the storing plateau is seed-variable (B1/none dense-real 0.26–0.82
   over five seeds). A per-cell stop at target, a longer cap, or the
   reading read at 2,200 alone.
4. **The corrected item-1 section and §6.6 as amended**; the ADR number
   for the design and its addendum on *accepted*.

**Practical (Atlas-0):** a `for` loop over checkpoints on CPU is an
hour per B1 check — use `modal_atlas0.py mech` (a minute each, ~$0.02);
`Path.with_suffix` eats a dotted name's tail (`b4-lam0.01` → `b4-lam0`),
so the drivers build paths by string; `modal volume ls` shows a cell's
`ckpt/` early while the logs stay buffered; the grid's B4 cells run 4
at a time at ~14 min each.

## TTT — held

1. **The 10,000-step point** (≈ 6 A100-hours) and **the 3,000-step
   adapter under the primary cell** (~0.7 A100-hour; the adapter is on
   the volume at
   `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/cc9e99c14215`;
   `TTT_APP=hobbes-ttt-cell … deploy` with it registered, then
   `ttt_cell.py run … --arm A2=<name> --arm A3=<name>` into the same
   cell dir; name the arms A2_3000 / A3_3000 and add them to
   `cell.ARMS`). Records: `docs/ttt/olmo3-ttt-results.md` §1 amended,
   §9, §9b, §10; `docs/ttt/cells/hobbes-olmo3-7b-2026-09-03-review.md`;
   standing in `benchmark-hypotheses.md` § H-TTT.
2. **The cell's defect register** (record § Item 9, D-1–D-5) — which to
   fix before the next cell.
3. **ADR-092's four embedded decisions.** Nothing blocks on them.

## WHERE THINGS STAND (2026-09-11)

- **Calvin M0-Go** (`docs/calvin/calvin-m0-go.md`, round 2
  `docs/calvin/calvin-m0-go-r2.md`; ADR-100 amended for its Go verifier):
  round 1 closed, round 2 run through WP-16.
  - **Artifacts:** under `~/.hobbes/bench/calvin-go/` (`wp-0` … `wp-16`:
    units and parent graphs, templates, gold groundings, the audits,
    every row).
  - **In the tree:**
    - grounder v3 (`ground.py`: the world check, `arity`,
      `undeclared-type`, `malformed`);
    - adapter protocol v0.6 (`adapter.py`);
    - template v2, opt-in;
    - the Go verifier with `vacuous` and `gold_tests` (`hobbes verify`);
    - `calvin_probe.py t-units | o-units`, with `--budget`,
      `--verify-build` and `recall` on every row.
  - **Worktrees and branches:** the package worktrees under
    `~/.hobbes/bench/calvin-go/<wp>/` were kept; the `calvin-go/wp-*`
    branches are merged.
- **Calvin M0-Gate** (`docs/calvin/calvin-m0-gate.md`; cell `docs/calvin/cells/calvin-m0-gate-2026-09-11.md`):
  run through WP-21 on ten keys. Artifacts under `~/.hobbes/bench/calvin-gate/`. In the tree: `hobbes gate`
  (`derive/gate.py`, gate v2), `o-units --gate --gate-repair --withhold-manifest --recall-upper`, and the cut
  session repo in `harness.run_o`. The `calvin-gate/wp-18*` branches are merged; the package worktree
  `~/.hobbes/bench/calvin-gate/wp-18/worktree` is kept.
- **Calvin M0** (`docs/calvin/calvin-potential.md`): held; artifacts
  under `~/.hobbes/bench/calvin/`.
- **Atlas-0** (`docs/atlas0/atlas-0.md`; `bench/atlas0/`, 84 tests):
  held; worlds and runs under `~/.hobbes/bench/atlas0/` and on the
  volume `hobbes-atlas0`.
- **Register:** **124 entries, 98 active, 24 lifted, 2 superseded** on
  2026-09-11 (C-121–C-124 from M0-Gate). The
  count is checked against the segment headings, not a summary line.
- **Suites:** 1,358 pytest (4 of them `lane_b`), 304 Go; the rest as CLAUDE.md
  states.
- **TTT instruments (ADR-099 + amendments):** `hobbes derive-corpus`,
  `hobbes.ttt.{units,score,report,probe,cell}`, the `ttt_*` and
  `modal_ttt.py` scripts; local mirrors under
  `~/.hobbes/bench/ttt/{runs,units,cell-hobbes}/`. **Modal** (as of
  2026-09-07): the apps `hobbes-ttt` and `hobbes-ttt-cell` deployed and
  idle (scale to zero); the volume `hobbes-ttt` holds the eight
  adapters, corpora, units and runs.
- **Disk (2026-09-11, Max's request):** `~/.hobbes` is 50 GB, down from
  119 GB. The `work/` clones of 22 SWE-bench-era runs were deleted after
  each arm's records were archived into `<run>/work-records.tar.zst`;
  `v017` and dagger-rust's `cargo-target` went too. The Atlas-0
  checkpoints and the session worktrees were kept.

## NEXT (in order; no spend)

**First: START HERE above.** Then:

1. **W0's remainder** (item 6 above).
2. **W1 / W3 items that spend nothing:** the decorated-declaration line
   convention (131 of dagger's 258 lane disagreements), the C-15
   namespacing ADR, the directory rollup in `list_blind_spots`; the
   decomposed DeepSWE protocol as design only; the Java follow-ups
   (W1); collaborator onboarding (`docs/workstreams.md`).
3. **The ingest `.gitignore` edit** — registered as a constraint or
   changed, on Max's reading of the finding (START HERE 3).

**Held, with all spend (not cleared, not scheduled):**
- Calvin M0-Gate's next steps: widening, the repair turn's design, O+world (START HERE 2).
- The wider Calvin M0 run.
- The Atlas-0 T items.
- The TTT 3,000-step adapter under the cell, and the 10,000-step point.
- The removal A/B re-run on the 7B.
- A second unseen repo through the cell.
- `hobbes narrate` on this repo.
**Held, with all spend (not cleared, not scheduled):** M0-Gate's next steps (START HERE 2); the wider
Calvin M0 run; the Atlas-0 T items; the TTT 3,000-step adapter under the
cell and the 10,000-step point; the removal A/B re-run on the 7B; a
second unseen repo through the cell; `hobbes narrate` on this repo.

## STANDING POLICY (Max) — read before doing anything

0. **API spend and Modal compute are off the table** (Max, 2026-09-04)
   unless Max names a run and its ceiling. Since then he has named:
   - Atlas-0 on Modal ($25);
   - Calvin M0-Go ($30, closed at $18.93);
   - M0-Go round 2 ($12, cleared at its spend gate on 2026-09-11; WP-16
     spent $3.10).
   - Calvin M0-Gate WP-21 (10 keys "for now"; Max named no dollar figure —
     the orchestrator set a hard cap of $11 below the ceilings offered; spent $5.03).

   No remainder carries to another run.
1. **Experiments are PARKED** except what Max clears by name.
2. **The 7B is the instrument, by speed not capability.** GPU-hours
   stated first; ≥15 min of evaluation before any run over 30 min.
3. **P12 (ADR-082):** every TTT arm is *model + prompt* and is labelled so.
4. **The 27B is untouched** until the mapping fixes are validated on
   the 7B, and only on a decontaminated set.

## PRACTICAL NOTES

- **After an image rebuild, restart the knowledge server** the session
  opened with (`.mcp.json` → `sandbox/knowledge-serve`): it runs the
  image's proxy, and an old build drops a tail class it does not know
  from every count it prints — no error, a smaller number (C-65). The
  ingest summary on the terminal is the check.
- **A model run: state the total dollar ceiling and run a few units
  first**, then compare the cost to the estimate before widening
  (M0-Go's WP-5 read 0.60× on five keys before WP-6). Kill by PID and
  `podman kill` the session containers; the per-unit records already
  written survive.
- **Worktrees for sub-agents:** the harness's `isolation: worktree` cuts
  from the session's first commit, not `main` — make one with `git
  worktree add` from `main` and check the base is an ancestor. A
  worktree lacks the gitignored build outputs (`go/bin/*`,
  `sandbox/hobbes-proxy`, `*/node_modules`, `pipeline/.venv`): `npm ci`
  in `scip/` and `tsextract/` before the Node-helper tests pass.
  Sub-agents cannot write report files; the orchestrator saves each
  reply as the package's `report.md`.
- **Sub-agents park on runs they launch detached.** Round 2 saw three
  stalls: twice WP-11a, once WP-16, the second WP-11a stall after an
  explicit warning. The agent ends its turn to "wait for a notification",
  and nothing wakes it. Watch the PID from the orchestrator (a background
  `while ps -p <pid>; do sleep 20; done`), then resume the agent with
  SendMessage, giving it the run's result.
- **An agent's repo must hold no future (D-x, 0.1.20-beta).** An O session
  and its repair launch from a repo cut at the key's parent (`harness.run_o`);
  any new driver that hands an agent a history clone must go through it. The
  network channel stays open (C-124): scan each session's flight log.
- **`pgrep -f` / `pkill -f` match your own waiting shell too**; wait on
  a log line and kill by PID (`ps | grep "[l]oop.py"`). Long RTA keys
  run detached (`setsid nohup`), never under a background command with a
  ten-minute cap.
- **Always `uv run --project pipeline hobbes … --repo <target>` from
  this checkout** (ADR-094) — and never `cd` into a target repo that has
  a `pyproject.toml` and `uv run` there: uv treats it as the project and
  creates a `.venv` inside it.
- **The oracle lane:** the `oracle` binary is built from the tree (`go
  build ./cmd/oracle` in `bench/oracle` before a regrade); the drift
  test answers `(cached)` after a record changes (`go test -count=1
  ./report/`); a regrade's report goes to a file with `>`, never through
  `tee | head`; a record's last verbatim block is its standing grade;
  the exception note lives in `bench/oracle/report/cells.meta.json`. A
  foreign record is regenerated from its artifacts (`foreign_record.py`),
  so put prose into `--triage-note` / `--fix-note`, not the record. A
  Gradle unit's index pass writes its init script and targetroot beside
  the `.scip` under the staging dir and removes both.
- **A baseline under an older helper is cheap:** copy the clone (with
  `.git`), swap `tsextract/extract.mjs` from `git show HEAD:…` for the
  run, restore it, `hobbes lanes` both.
- **Olmo 3 on vLLM has no tool-call parser here:** send no `tools` field
  (`loop.py --tool-choice none`). An A10G holds one adapter at 16k
  (`SERVE_GPU=A100-80GB` for a multi-adapter serve; `--max-loras` is
  capped at four). `modal run`'s remote prints are buffered — read
  `modal app list` / `modal app logs`, and stop an ephemeral app with
  `modal app stop -y <id>`. Never rescore in place (`ttt_rescore.py
  --out` a new file).
- **The key file is off the tree:** Max keeps it in a local folder
  outside the repo; never write its path into repo prose. `hobbes bench
  run --secrets <path>` and `calvin_probe.py` (`--secrets`,
  `--key-name`) read it. Keys it holds include `modal_key_id`,
  `modal_key_secret`, `llm_key`, `anthropic_key`, `HF_token`,
  `daytona_key`; Calvin runs take `--key-name anthropic_key`.

## Housekeeping

Commit to `main`; never `git push` (Max publishes). One ADR per design
decision; one BUILDLOG entry per session; every concession a `C-n` in
its segment file under `docs/constraints/`. Rewrite this doc; do not
append to it.
