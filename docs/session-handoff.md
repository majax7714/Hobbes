# Session handoff — the single resume point

**Reviewed 2026-09-15; Hobbes 0.2.25-beta on `main`.** ADR-114's base
rule runs first on the next push: check the graph job's "base ref" step
says it reviewed from the last green run. The knowledge server of the
session that opens next serves the 0.2.24-beta build until it is
restarted (C-65).
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.25-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask); **a
  constraint's fix is a patch even when structural** (Max, 2026-09-13).
- **Where work happens:** on `main`; publishing belongs to Max.

The session's record is the 2026-09-15 "ADR-115" BUILDLOG entry (the
helper's decode streams); C++'s close-out is the "(later) C++ closed
out" entry of the same day. Earlier sessions' detail lives in their own BUILDLOG entries; this
file keeps only what the next session needs.

## ⇢ START HERE NEXT SESSION

0. **The helper's decode streams (2026-09-15, 0.2.25-beta, ADR-115).**
   C-150's assessment, Max's route "streaming decode is best route":
   - the helper reads SCIP's wire format one document at a time
     (`streamDocuments`, `indexFiles`; `decode` walks its source twice
     through `documentsOf`); the generated reader and its typed-range
     monkeypatch are gone;
   - ScummVM's whole index (387 MB, 11,265 documents) decodes under the
     default heap at 3.4 GB resident, 33 s, with facts identical to the
     old reader's by digest (old: 9.7 GB, 38 s at a 14 GB heap);
   - a killed helper (137 / -9) names C-150 instead of "install Node";
   - C-150 narrowed and retitled to the facts' size on the Python side
     (about 2.1 GB parsed for ScummVM beside lane A's 1.5 GB); C-149's
     bound stays for the references the per-unit route holds, not the
     merge's memory. Its lift is the per-site rules on arrival.
   - **Where things are:** ScummVM's index and its unit list stayed in
     `~/.hobbes/cache/stage/b7bc0819382fd513.scip.units/` (`whole.scip`,
     `whole.json`), the staged copy beside it; the two probes are
     `~/.hobbes/bench/cpp-drivers/probes/decode_equiv.mjs` (a helper
     module against an index, digests every row; `old` as the third
     argument uses the generated reader) and `stream_probe.mjs`. Run
     them from `scip/` so the imports resolve.
   - **Not done, its own decision:** the Python side reads the facts
     whole (`run_helper`: one JSON document on stdout). Streaming them
     is a facts-format change (helper version 4). No end-to-end ScummVM
     ingest at 0.2.25-beta is recorded; the estimate is 8 GB free.
   - The binaries, the static proxy and the image are at 0.2.25-beta.
0b. **C++ is closed out (2026-09-15): supported, 0.2.23-beta.** ADR-113's
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
1. **Next, no spend: the gate's arrow-parameter fix** (C-91, the
   harness's one false block, `f3c1`), as a small unit.
   `ground._TS_PARAMS` needs a word character or `function` before the
   `(`, so `= (check) =>` never reads `check` as a local. Decide it in
   C-91's entry or a short amendment first, then dispatch.
2. **Open for Max (no spend):**
   - **O10's four defects, H-28–H-31** (`oracle-defects.md`): recorded
     open by Max's call. They are the 18 oracle-side rows on fmt: a
     member call keyed at its object's start; a template pattern's
     members merged by bare name; dynamic sites judged against their
     line's other calls; calls the key does not hold. A bench unit
     would fix them, with no version move.
   - **C-153 is unsurfaced** (debt): scip-clang's single answer at a
     call in a template can name the wrong declaration (10 of fmt's
     3,395 judged semantic edges). Nothing at the site can detect it.
     Whether to accept it as documented-only is Max's.
   - **`hobbes lanes` exits 1 on fmt**: 316 disagreements where lane A
     guesses, none drawn (read against the key in fmt's record). This
     repo's graph has 0 C++ disagreements, so CI is unaffected. The two
     routes: compare C++ only where the fallback could draw, or keep it
     as the self-test's report.
   - **C-150's remainder** (large repos, every language): the facts
     held whole on the Python side, after ADR-115 took the decode's
     share. A facts-format change; Max's call whether and when.
   - Carried: C-139's finer extent (only if a cell shows the recall
     cost); the tracker's area for a test-only session (row 17, `—`);
     C-140's remainder (ADR-112's route 2); C-133's unit 2 (the `-I`
     read), deferred until a graded cell shows the cost.
3. **Running a session** (`calvin-harness.md` §5):
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
   - **Toward 40 across three areas:** the tracker reads 30 of 40, 4
     areas, 1 false block (`f3c1`), 0 missed.
4. **A regrade against stored keys:**
   - For one cell: re-ingest, `oracle export`, then `oracle grade
     --poison` against the cell's saved `oracle.json` (as the C++
     regrades did).
   - For many: `~/.hobbes/bench/adr111-drivers/regrade3.sh` over a
     `cells.tsv` (ROOT=<worktree>); run a pre pass only when ingest code
     changed; never two passes over one clone at once.
   - A regrade after a fix carries signed direction-of-fix lines in its
     record.
5. **Carried:**
   - **The ingest's `.gitignore` edit.** Register it as a constraint or
     change it, on Max's reading.
   - **pytest's 4 warnings:** a helper named `testmap_fixture` in
     `test_ttt_corpus.py` and `test_ttt_units.py` is collected as a test.
   - **`stringer` is not in the image.**
   - **The Gradle attach route's residuals** (C-67); `recall-collapsed`
     and H-23; ADR-105/P13; the C-98 residuals.
   - **The comparative queue:** the two SQLite tools in `field.md`
     (converters first); syft's keys on a bigger box. No foreign C++
     cells exist yet.
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

## WHERE THINGS STAND (2026-09-15)

- **Languages:** Python, TS/JS, Go, Rust, Java, C and C++ supported, each
  as far as its §3.8 row (P11); Terraform/HCL structure.
- **The Calvin harness** (ADR-107, ADR-112): each session's state is
  under `~/.hobbes/sessions/<id>/`, written by its sidecar
  `hobbes-side-<id>`; the doer mounts only `in/`, read-only, and its HOME
  is a tmpfs. Thirty log files under `docs/calvin/sessions/`.
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 84 cells; `render.py check` green.
- **Atlas-0** (`bench/atlas0/`, 84 tests) and **TTT** (Modal apps
  deployed and idle): held.
- **Register:** 153 entries: 110 active (85 surfaced, 20 partial, 4
  unsurfaced — C-19, C-20, C-112, C-153 — 1 n/a), 26 lifted, 11
  superseded, 6 folded. This session: C-151, C-152 (surfaced), C-153
  (unsurfaced, P9); C-132 narrowed again.
- **Oracle defect log:** H-28–H-31 open (O10); RC-8 shaped.
- **Suites** at 0.2.23-beta: 1,613 pytest (host, `lane_b` included); 71
  scip node; Go 386 `--- PASS`/`SKIP` lines (385 pass, 1 skip), not
  re-run beyond the version test since no Go code moved; oracle-lane Go
  95 pass / 5 skip; 52 vitest, 36 tsextract, 84 atlas0 not re-run.
- **Disk:** `~/.hobbes` is about 50 GB plus the C++ cells (ScummVM's
  cost clone at `cpp-cells/scummvm-cost` is the large one; sweep it if
  space is needed).

## NEXT (in order; no API spend)

1. The gate's arrow-parameter fix (item 1 above).
2. **Keep dispatching named no-spend work through the harness,** one
   unit per brief, toward 40: C's residue (W1); W1/W3's no-spend items
   (the decorated-declaration line convention, the C-15 namespacing ADR,
   `fetch-java` on the egress proxy); the comparative queue's next tools
   if named; pytest's `testmap_fixture` warnings.
3. **W0's remainder:** `go/internal/version`'s missing guard; the
   registry-pulled image and the drift audit, when named. (The
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
