# Session handoff — the single resume point

**Reviewed 2026-09-14; Hobbes 0.2.17-beta on `main`.**
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta and 0.2.11-beta to
  0.2.17-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask); **a
  constraint's fix is a patch even when structural** (Max, 2026-09-13,
  on C-140: "its a constraint not a direct feature advancement").
- **Where work happens:** on `main`; publishing belongs to Max.

The session's record is the 2026-09-14 BUILDLOG entry.

## ⇢ START HERE NEXT SESSION: Max's open calls; then keep dispatching toward 40

0. **Latest (2026-09-14, last): the doer's model named per checkout —
   ADR-107 amended, 0.2.17-beta.** Max: "proceed with the staleness
   fixes and re-ingest, also id like to setup this space where
   dispatching tasks uses opus 5 instead of fable". The review's three
   stale lines fixed first (`f09b371`: the CHANGELOG's untagged range,
   the handoff's leftover tracker count, the workstreams header), the
   ingest at HEAD. **The finding:** all twenty-three sessions on record
   ran on "model the default" — `--model` reached Claude Code but
   nothing set it, and the doer's container has no user settings — so
   the model was never the owner's choice nor recorded. Decided in
   ADR-107's 2026-09-14 amendment (`acf093c`), then one unit through
   the harness:
   - **`cd8e`** (22 of 60 turns, 76 s, $1.11, run with `--model
     claude-opus-5` said explicitly — the first session whose Doer line
     names its model; no egress refusal, five execs all allowed):
     `MODEL_ENV` and `default_model()` in `dispatch.py`, `args.model or
     dp.default_model()` and the help text in `cli.py`, three tests
     through the fake session's `argv.json`. Gate clear, verify pass
     (388 tests, 3 new). Merged `1f5790a`, not squashed.
   - **Fixed on the host after the merge:** the tracker's Doer pattern
     knew only `model the default` and refused the first named model;
     it now takes a name, with a test.
   - **This box's setting:** `HOBBES_DISPATCH_MODEL=claude-opus-5` in
     `.claude/settings.local.json`'s `env` block (gitignored, beside
     `HOBBES_SECRETS`). It reaches a shell started after the setting,
     so the session that opened before it passed the flag by hand;
     from the next session on, a bare `hobbes dispatch` runs on Opus 5
     and the log says so.
   - Task files: `~/.hobbes/bench/dispatch-model-drivers/model-task.md`
     with its partition beside it. **The tracker** reads 24 of 40, 4
     areas, 0 false blocks, 0 missed, $50.88 reported. Binaries and the
     image rebuilt at 0.2.17-beta; **restart the knowledge server** the
     next session opens with (C-65).
0d. **Before it (2026-09-14, later still): `oracle import --lang c` —
   ADR-101 amended; no version move.** Max: "review top level
   documentation, then proceed with most tackable item using harness".
   The review found no drift. The pick, read first: the foreign
   converter reads `export.Exts`, which has carried `c` since ADR-110,
   so a C edge file already converted, but the flag helps, the
   refusal, the usage block, `grade-foreign.sh`, the README and
   `foreign_record.py` all spelled the set without it, and no fixture
   proved it. Decided in ADR-101's amendment (`7abfdcd`), then one
   unit through the harness:
   - **`d2e3`** (40 of 60 turns, 4.7 min, $1.04): `c` spelled in every
     one of those places; `testdata/foreign/cclang.edges.json`
     (twelve rows: eight graded, two across a header; a macro row, a
     duplicate, two other-language rows); two tests beside the minigo
     pair, the second grading against a hand-built key with the poison
     check. Gate clear, verify pass (11 tests, 2 new). Merged
     `109c15b`. One egress refusal, `static.rust-lang.org`, from the
     Rust driver tests under the doer's `go test ./...`; they skip.
   - **Fixed on the host after the merge:** a tautological check in
     the conversion test (the truth map read against itself); it now
     asserts the two header pairs were converted.
   - **Nothing under `bench/` moves the version** (ADR-103), so the
     layer stays 0.2.16-beta; the image and binaries are current.
   - **Then the foreign C cells themselves (Max: "continue with the
     next item"), host-run, no spend:** both tools re-installed at
     their pins from uv's cache (`~/.hobbes/bench/comparative/tools/`),
     the driver `run-c-cell.sh` beside them, four cells under the
     clang keys, records in `docs/oracle/cells/`, every contradiction
     read. CodeGraphContext 1,179/1,179 (recall 61.5%) on cJSON and
     851/863 (100%) on sqlite-vector; repowise 1,073/1,637 (56.0%) and
     780/879 (93.3%). **The finding:** repowise stores a function-like
     macro as `function`, so the macro exclusion (which fires on a
     `macro` kind alone) never applies to it: 562 of its 564 cJSON
     contradictions and all 99 on sqlite-vector are `#define` targets;
     with those excluded as Hobbes' own are it would read 99.8% and
     100% (stated in the records, not graded; C-95 amended with the
     C face). CodeGraphContext's twelve are nine API names drawn into
     the vendored amalgamation and the three `strcasestr` shim rows
     (C-138's shape). Poison: 0 falsely confirmed of 27,925 seeded
     across the four. Graphics and `tables.md` regenerated (84 cells),
     `check` green, the report test green.
   - **Then (Max: "proceed with the recommendation"): converter@3.**
     ADR-101's second amendment of the day (`d16c978`), then one unit
     through the harness — **`3c41`** (45 of 80 turns, 3.2 min, $1.10,
     gate right-clear, no egress refusal): `declared_kind` in both
     adapters (a leading `#define` at the declared line is `macro`),
     `VERSION` at `@3`, a hand-made C raw fixture and
     `TestCclangMacroRowIsExcluded` per adapter, the record tooling
     signing the converter pair. Merged `d575428`. Regraded from the
     stored dumps (`regrade-c-cell.sh`, the `@2` grade kept as
     `*.v1.*`): repowise cJSON 1,073/1,075 (699 macro edges excluded;
     the two left are `setUp`/`tearDown` in a dead `#if` arm),
     sqlite-vector 780/780 (607 excluded); CodeGraphContext unmoved
     (no edge to a `#define`). Records, graphics and tables
     regenerated; C-95 narrowed; the claim page restated. **The
     tracker** reads 23 of 40, 4 areas, 0 false blocks, 0 missed.
   - Task files: `~/.hobbes/bench/c-import-drivers/import-task.md` and
     `macro-task.md`, each with its partition beside it. **The tracker**
     reads 23 of 40, 4 areas, 0 false blocks, 0 missed, $49.77 reported.
0c. **Before it (2026-09-14, last of the release day): C-135's measured gap closed — ADR-109
   amended, 0.2.16-beta.** Max: "proceed with the recommended". Read
   first, no spend: on bpftop, under bear, `cargo build` records 45
   compiles, all libbpf-sys's vendored libbpf and vsprintf under cargo's
   registry, none under the root; libbpf's make fails in the image for
   want of `libelf.h`, so cargo stops before bpftop's own build script
   compiles its BPF program. Decided in ADR-109's amendment, then one
   unit through the harness:
   - **`1ae3`** (17 of 100 turns, 94 s, $0.45): `compdbCheck` takes the
     root and refuses before scip-clang when a non-empty database has
     no entry under it, naming where they lie, the capped last words
     and C-135. Merged `fc7bf3d`. bpftop's record moved from the
     generic `scip-index` line to the `scip-c` record with the cause.
   - **What verify could not see:** a check's refusal exited the helper
     with the generic code, so Python labelled it "the SCIP helper is
     unusable — install Node"; the empty-database case had the same
     mislabel since 0.2.4-beta. Fixed on the host (`indexerExit`; both
     tests assert the exit code). The scip node suite is 47.
   - **C-135** stays *partial*: autotools, Meson and Bazel roots; a
     database with root entries that still indexes nothing (not seen);
     a dependency's build the image cannot complete (libelf is not in
     the image — adding it is an image decision, not owed).
   - Task files: `~/.hobbes/bench/c135-drivers/compdb-task.md` and its
     partition. **The tracker** reads 21 of 40, 4 areas, 0 false
     blocks, 0 missed. The image and binaries are at 0.2.16-beta; the
     helper is mounted from the checkout, not baked in. **Restart the
     knowledge server** the next session opens with (C-65).
   - Housekeeping seen, not done: `~/.hobbes/cache/stage/` holds 34
     small leftover `.scip` outputs (116 KB) from earlier runs.
0b. **Before it (2026-09-14, later): C-133 narrowed — ADR-108 amended,
   0.2.15-beta.** Max: "continue tackling your recommended item" (the
   top-level review's pick: the register's one unsurfaced C entry).
   Decided in ADR-108's 2026-09-14 amendment before the dispatch, then
   one unit through the harness:
   - **`47f7`, unit 1** (25 of 100 turns, 4.3 min, $0.79): an include
     decision 4's three steps cannot place draws one `c-includes`
     record per directory (unmatched quoted; ambiguous of either
     spelling; an angle include that matches nothing stays `ext:<p>`).
     Edges unchanged. Merged `a7ab3f6`. Measured on the merged code:
     cJSON 6 records over 305 include edges unchanged; sqlite-vector 1
     over 163 unchanged.
   - **What verify could not see:** the tracker's drift test, red on
     the host because its Policy pattern predated the stream bracket
     0.2.14-beta's dispatch writes; fixed with a test. And the three
     `package-lock.json` copies of the version, which the bump had
     missed.
   - **C-133** is *partial* (18 partial, 3 unsurfaced: C-19, C-20,
     C-112). **Unit 2** — a re-resolution pass after lane B returns,
     reading each translation unit's `-I` directories from the derived
     compile database as a fourth step — needs its own ADR-108
     amendment first, and a regrade of the two C cells after. Not
     decided; for Max whether it is worth it now.
   - Task files: `~/.hobbes/bench/c133-drivers/includes-task.md` and
     its partition. **The tracker** reads 20 of 40, 4 areas, 0 false
     blocks, 0 missed, $47.19 reported.
   - (Superseded by item 0's line on the image and the ingest.)
   - The top-level review before this found three stale lines from the
     0.2.14-beta release (the README's status, the architecture's §8
     header, the CHANGELOG's untagged list), fixed in `f2ce612`. Left
     for Max: CLAUDE.md says the architecture carries no version
     number, and its §8 does.
0a. **Before it (2026-09-14): C-140's fix — ADR-112, 0.2.14-beta.** Max
   chose route 1 of three (the records' writers leave the doer's
   container; the executor stays) and the number. Measured first (four
   measurements, in the ADR), decided in ADR-112, built through the
   harness in two units, both gates right-clear:
   1. **`3ebb`, unit A** (82 of 150 turns, $4.42): `go/internal/sink`
      (one flight stream ever, the refusal recorded, session and role
      stamped by the sink), `hobbes-proxy sidecar` replacing `egress`,
      `proxy.Journal` with the file journal kept, `serve --sink` and
      `record-edit --sink`. Merged `a3c2551`. After the merge (`6ad5567`):
      an escalation id is one path segment; the sidecar stops both
      listeners when one fails.
   2. **`de81`, unit B** (94 of 150 turns, $6.69): the launcher's two
      worlds (the sidecar world by default; the file world on an explicit
      `--network`, said in one line naming C-140; the owned runtime
      refuses the sidecar world), HOME a tmpfs, `<id>/in/` the one
      read-only host dir, the launcher waiting for the sink's
      `listening` line, dispatch's stream bracket, the exit check.
      Merged `9e264d6`. After the merge: the live mount test builds the
      real proxy (`0223091`); the driver beside the exit check reads
      `in/mcp.json` (`32154ca`).
   - **What verify could not see, both times: a live test red on the
     host.** After A, the egress route test (the old launcher still ran
     `egress`); after B, the mount test's fake proxy. §2's rule stands:
     run every live test on the host before merging.
   - **Host checks:** all four live launcher tests pass; the exit check
     5/5 through the sidecar, a host-side approval included; Go 385
     pass / 1 skip (subtests counted); pytest 1,508.
   - **C-140** is narrowed to a forged edit line, surfaced (78 surfaced,
     17 partial). **The tracker** reads 19 of 40, 4 areas, 0 false
     blocks, 0 missed, $46.40 reported.
   - (Superseded by item 0's line on the image and the ingest.)
   - The top-level review found one drift, fixed: the harness doc's
     status line still said twelve sessions through 0.2.10-beta.
1. **Open for Max (no spend):**
   - (Settled 2026-09-14: ADR-106 written as *not taken*; the
     `future_additions.md` harness-weight line kept, Max not yet settled
     on where the harness goes; the dispatch segment and the C-120 fold
     taken.) Nothing from the 2026-09-13 review is open.
   - **C-139's finer extent** (the binding's own line, or the enclosing
     block). Take it only if a graded cell ever shows the recall cost.
     Nothing is owed now.
   - **The tracker's area for a test-only session** (Max, 2026-09-13:
     "leave rest of the table for now"). Row 17 (`81df`, D-s) reads `—`,
     because a session that changed only test files maps to no area by
     `calvin_tracker.py`'s rule. It does not move the area count.
   - **C-140's remainder, if it ever matters:** ADR-112's route 2 (the
     whole proxy in its own container, exec's children under a second
     uid) closes the forged edit line. Not owed.
2. **Running a session** (`calvin-harness.md` §5):
   - Keep the token in the key file, and ingest at HEAD.
   - The doer's model is the checkout's: `HOBBES_DISPATCH_MODEL` in
     `.claude/settings.local.json` (this box: `claude-opus-5`); `--model`
     beats it; unset, Claude Code chooses and the log says "the default".
   - Decide the design in an ADR or an amendment **before** the
     dispatch, as ADR-111, ADR-112, ADR-046's amendment and ADR-107's
     2026-09-13 amendment were.
   - Name one small unit: `hobbes dispatch --task-file … --partition …
     --secrets "$HOBBES_SECRETS"`, with `--dry-run` first. Check that the
     argv carries `--settings` (the hook). Task files this session:
     `~/.hobbes/bench/adr112-drivers/{sink,launcher}-task.md`,
     `~/.hobbes/bench/c133-drivers/includes-task.md` and
     `~/.hobbes/bench/c135-drivers/compdb-task.md`, with their
     partitions beside them.
   - Watch dispatch's own stderr for "first edit at". The real session
     id differs from the dry-run's; read it from the output's last line.
   - Review the session file and the diff. Merge with `git merge --no-ff
     -m … -m …` or `-F <file>`, never squash.
   - **After filling the review block, re-render the tracker**
     (`pipeline/scripts/calvin_tracker.py render`). Its drift test fails
     the suite until the table matches the logs.
   - Two dispatches can run at once from one parent (`e537` and `78b7`
     did). Do not re-ingest while one is still gating: the gate reads the
     parent's derived graph.
   - **Do not rebuild `go/bin` while a dispatch runs.** The launcher
     and the proxy must agree on the subcommand set: a 0.2.13-beta
     launcher runs `hobbes-proxy egress`, which the 0.2.14-beta proxy no
     longer has. Rebuild both after the merge.
     - `git merge` does not read `-F -` from stdin. A heredoc there fails
       the merge silently in a `;` chain.
     - A heredoc followed by `&& \` in one Bash call is a syntax error;
       write the message to a file and pass `-F <file>`.
   - **A live test skips in the sandbox** (podman is not there), so
     verify cannot run it. Run every new live test on the host before
     merging (`2aa9`, `3ebb` and `de81` each had one wrong or red there).
     A live test that needs the sidecar must pass the real static proxy
     (`staticProxyBin`), never the fake.
   - **Testing a dispatch branch on the host before merging:**
     - make a worktree with its own `uv sync` if the Python side is
       tested; main's venv would import main's code. Go tests need no
       venv.
     - copy `scip/node_modules` and `tsextract/node_modules` as real
       trees, because lane B's container cannot follow a symlink out of
       the worktree;
     - run node tests as `node --test test/index.test.mjs`; node 22 does
       not take a directory.
   - **Toward 40 across three areas.** The tracker counts them
     (twenty-four so far):
     - extraction: C's lane A and its rework, the external veto, C-139,
       C-134's registrations, C-133's include record, C-135's
       compile-database check;
     - the knowledge tools: the `path` alias, the language tables, the
       directory rollup;
     - the harness and sandbox: the progress hook, the containment, D-r,
       the tracker, D-s, the sink and the sidecar, the launcher's two
       worlds, the checkout's model variable;
     - the oracle lane: C's oracle, `oracle import --lang c`, converter@3.
3. **A regrade against stored keys** (the ADR-111 pattern, used again for
   C-139):
   - `~/.hobbes/bench/adr111-drivers/`: `ROOT=<worktree> regrade3.sh
     <out> <cells.tsv>`.
   - `cells.tsv` names every cell's clone, module, lang, excludes, key and
     before-report. For a one-language gate, filter it by the lang column
     and point the before-report column at the last pass's reports. The
     last one: `adr111-post/<cell>/report.json`, with the output in
     `~/.hobbes/bench/c139-post/`.
   - Run a pre pass only when ingest code changed since the baseline
     pass. Never run two passes over the same clone at once.
   - For a lane A change, also compare `extract_go` (or its language's
     provider) on main against the branch. A lane B-on regrade can move
     nothing where lane B already answers.
   - `render.py` takes absolute paths.
4. **Carried:**
   - **The ingest's `.gitignore` edit.** Register it as a constraint or
     change it, on Max's reading (round 1's finding).
   - **pytest's 4 warnings:** a helper named `testmap_fixture` in
     `test_ttt_corpus.py` and `test_ttt_units.py` is collected as a test
     and returns a dict.
   - **`stringer` is not in the image.**
   - **The Gradle attach route's residuals** (C-67).
   - **`recall-collapsed` and H-23**; ADR-105/P13; the C-98 residuals.
   - **The comparative queue:** item 4; the foreign C cells are done
     and regraded at converter@3 (2026-09-14). Next there, if named:
     the two SQLite tools in `field.md` (converters first), syft's keys
     on a bigger box.
   - **C's residue:** C-134's remainder (criterion and the Unity
     fixture, whose bodies a macro defines), C-135, C-133's unit 2 and
     its macro half. The macro gap
     stays parked (C-131, `future_additions.md`).
   - **`build-logic/`** is recorded, not built (ADR-097).

## Atlas-0 — held from 2026-09-07: Max reads the B4 record; then the T that carries the abstention act, and T_v2

**Done 2026-09-07** (`docs/atlas0/atlas-0.md` § Addendum), $22.28
assumed of $25:
- **The §A.1 checks on saved weights:**
  - B1 reads through eight heads and stores in six FFNs;
  - B2's refusal is a linear direction, not a norm;
  - B3's copy circuit is layer 0.
- **B4** (typed attention; K = 1 is B1 to the digit).
- **The λ sweep:** the pressure decides the route.
- **The grid at λ = 0**, one run per seed:
  - B4 = B1 on storing and the sibling pull;
  - `UNDEFINED` 0.00 in both phrase arms;
  - §A.7 branch 3 (B4-given) is what the results select.

**What needs Max:**
1. **The T that carries the abstention act.** Either the memorising T
   (3,500 steps, batch 64), or §A.7 branch 2's computed `NO_EDGE`
   target in a B4-given block. About $3.5–4 plus B1's cells.
2. **The grid's second run.** About $3.8, which takes the programme to
   about $26 against its $25 ceiling.
3. **T_v2 for the v2 grid.** The plateau at 3,100 is seed-variable
   (dense-real 0.26–0.82).
4. **The corrected item-1 section and §6.6 as amended**, and the ADR
   number on *accepted*.

**Practical (Atlas-0):**
- Use `modal_atlas0.py mech` for checkpoint checks: about a minute each,
  where a CPU loop takes an hour.
- `Path.with_suffix` eats a dotted name's tail, so the drivers build
  paths by string.
- The grid's B4 cells run four at a time, about 14 min each.

## TTT — held

1. **The 10,000-step point** (about 6 A100-hours), and **the 3,000-step
   adapter under the primary cell** (about 0.7 A100-hour).
   - The adapter is on the volume at
     `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/cc9e99c14215`.
   - Deploy with `TTT_APP=hobbes-ttt-cell … deploy`, then
     `ttt_cell.py run … --arm A2=<name> --arm A3=<name>`.
   - Name the arms A2_3000 and A3_3000 and add them to `cell.ARMS`.
   - Records: `docs/ttt/olmo3-ttt-results.md` §9–§10, and
     `docs/ttt/cells/hobbes-olmo3-7b-2026-09-03-review.md`.
2. **The cell's defect register** (D-1–D-5): which to fix before the
   next cell.
3. **ADR-092's four embedded decisions.** Nothing blocks on them.

## WHERE THINGS STAND (2026-09-14)

- **The Calvin harness** (ADR-107, ADR-112):
  - **Code:** `go/internal/sink` and `go/internal/egress` (both in
    `hobbes-proxy sidecar`), `proxy.Journal`, `hobbes-session --egress`
    and `--claude-bin`, `pipeline/src/hobbes/run/dispatch.py`,
    `gate.derive_map`, `gate.map_files`.
  - **Records:** each session's state is under
    `~/.hobbes/sessions/<id>/` (`flight.jsonl`, `escalations/`,
    `mail.jsonl`, `egress.jsonl`, `dispatch.json`, `gate.json`,
    `verify.json`, the brief, and `in/` with the MCP config and the
    hook's settings). Since 0.2.14-beta they are written by the
    session's sidecar, `hobbes-side-<id>`; the doer's container mounts
    only `in/`, read-only, and its HOME is a tmpfs, so nothing of the
    doer's state reaches the host (retention by construction). The log
    file is under `docs/calvin/sessions/` (twenty-four, of the 40 that
    validate the harness; the tracker counts them).
  - **Task files** are kept off the tree:
    `~/.hobbes/bench/adr111-drivers/{hook,veto}-task.md`, and each
    later session's in its brief (`~/.hobbes/sessions/<id>/brief.md`).
- **The keyed Calvin rounds** (closed 2026-09-12): the records are in
  `docs/calvin/`, and the artifacts under `~/.hobbes/bench/calvin/`,
  `calvin-go/` and `calvin-gate/`.
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 84 cells (the four foreign C cells since 2026-09-14);
  `render.py check` green. The README embeds
  `same-key.svg`, and its wording stands (Max, 2026-09-13).
- **Atlas-0** (`bench/atlas0/`, 84 tests): worlds and runs under
  `~/.hobbes/bench/atlas0/`, and on the volume `hobbes-atlas0`.
- **TTT:** the Modal apps `hobbes-ttt` and `hobbes-ttt-cell` are
  deployed and idle; the volume `hobbes-ttt` holds the adapters,
  corpora, units and runs.
- **Register:** 141 entries: 99 active (77 surfaced, 18 partial, 3
  unsurfaced, 1 n/a), 25 lifted, 11 superseded, 6 folded (Max's calls,
  2026-09-13 and 2026-09-14; ADR-043 amended twice). C-133 and C-135
  narrowed 2026-09-14; the dispatch harness's five entries have their
  own segment, `dispatch-harness.md`, and C-120 folded into C-112.
- **Suites** at 0.2.17-beta:
  - 1,519 pytest (host); 47 scip node (host, not re-run: nothing it covers changed);
  - Go 386 `--- PASS`/`SKIP` lines (385 pass, 1 skip; subtests
    counted), with the four live launcher tests run on the host;
  - oracle-lane Go re-run on `main` after `d2e3`'s merge, green (the
    count is in CLAUDE.md's suite line);
  - not re-run, since nothing they cover changed: 52 vitest, 43 helper
    and 36 tsextract node, 84 atlas0.
- **Disk:** `~/.hobbes` is about 50 GB (swept 2026-09-11).

## NEXT (in order; no API spend)

1. **Max's calls** (START HERE item 1): none open from the reviews;
   the three items there are not owed (C-139's extent, the test-only
   area, C-140's remainder).
2. **Keep dispatching named no-spend work through the harness,** one
   unit per brief, toward 40 across at least three areas:
   - C's residue (W1): C-135's autotools,
     Meson and Bazel roots; C-133's unit 2 (the `-I` read from the
     derived database), deferred until a graded cell shows the cost;
   - W1/W3's no-spend items: the decorated-declaration line convention,
     the C-15 namespacing ADR, `fetch-java` on the egress proxy;
   - the comparative queue's next tools (converters first), if named;
   - small harness items: pytest's `testmap_fixture` warnings.
3. **W0's remainder:**
   - the graph CI job forgets earlier red reviews;
   - `go/internal/version` and the union fixture's ownership;
   - the registry-pulled image and the drift audit, when named.

**Held, with all spend (not cleared, not scheduled):**
- the Atlas-0 T items;
- the TTT 3,000-step adapter under the cell, and the 10,000-step point;
- the removal A/B re-run on the 7B;
- a second unseen repo through the cell;
- `hobbes narrate` on this repo.

The keyed Calvin runs are closed, not held.

## STANDING POLICY (Max) — read before doing anything

0. **API spend and Modal compute are off the table** (Max, 2026-09-04)
   unless Max names a run and its ceiling.
   - **Named since:** Atlas-0 on Modal ($25), Calvin M0-Go ($30, closed
     at $18.93), M0-Go round 2 ($12; spent $3.10), M0-Gate WP-21 (a $11
     cap; spent $5.03).
   - **No remainder carries** to another run.
   - **A `hobbes dispatch`** spends the owner's Claude Code
     subscription, not API dollars. A dispatch on an API model or on
     the owned loop is not built, and would need a ceiling.
1. **Experiments are PARKED** except what Max clears by name.
2. **The 7B is the instrument, by speed not capability.** GPU-hours
   stated first; ≥15 min of evaluation before any run over 30 min.
3. **P12 (ADR-082):** every TTT arm is *model + prompt* and is labelled
   so.
4. **The 27B is untouched** until the mapping fixes are validated on
   the 7B, and only on a decontaminated set.

## PRACTICAL NOTES

- **Two sessions may share this checkout.** A Remote Control session
  once merged a dispatch and wrote its reviews while another session
  was working. Before assuming `main`'s state or a file's content, read
  `git reflog` and the file itself.
- **A session sees only its own `in/`** (0.2.14-beta, ADR-112). A file
  a scripted session command needs goes under `<sessions>/<id>/in/`,
  read-only in the container (`sandbox/exitcheck.py` does this); its
  HOME is a tmpfs, so nothing it writes there outlives it. An explicit
  `--network` is the old file world (the session dir mounted rw,
  C-140 in full), which `--runtime` needs for its transcript.
- **The sidecar and the route.**
  - Every session gets `hobbes-int-<id>` (internal) and the container
    `hobbes-side-<id>`, which writes its records; the launcher waits for
    the sink's `listening` line in `flight.jsonl` and removes both at
    the end.
  - `hobbes-egress` is a shared podman bridge; it stays between
    sessions. With `--egress` the sidecar joins it too.
  - A session killed from outside can leave them behind. Clean up with
    `podman rm -f -t 0 hobbes-side-<id>` and `podman network rm -f
    hobbes-int-<id>`. The forced network removal takes the session
    container with it. `hobbes dispatch` does this on its own timeout.
  - A measurement's unnamed container looks like the knowledge server's
    in `podman ps`; name every probe container before removing by name.
- **A no-spend route check:** `CLAUDE_CODE_OAUTH_TOKEN=invalid
  go/bin/hobbes-session start --repo <a tiny repo> --role implementer
  --egress api.anthropic.com --task "Reply ok." --max-turns 1`. Expect
  a 401 in the envelope, tunnels to `api.anthropic.com:443` in the
  session's `egress.jsonl`, and no refusals.
- **After an image rebuild, restart the knowledge server** the session
  opened with (`.mcp.json` → `sandbox/knowledge-serve`). An old build
  drops a tail class it does not know from every count it prints — no
  error, just a smaller number (C-65).
- **The comparative graphics** are rendered by
  `bench/oracle/report/render.py` (`cells`, `render`, `check`); rasterise
  with `magick -density 110 <svg> <png>` to look before committing. A
  caption that names cells must read them from `cells.json`, never type
  them.
- **A model run:** state the total dollar ceiling, run a few units
  first, and compare the cost to the estimate before widening. Kill by
  PID and `podman kill` the session containers.
- **Worktrees for sub-agents.**
  - The harness's `isolation: worktree` cuts from the session's first
    commit, not `main`. Make one with `git worktree add` from `main`
    and check the base is an ancestor.
  - A worktree lacks the gitignored build outputs (`go/bin/*`,
    `sandbox/hobbes-proxy`, `*/node_modules`, `pipeline/.venv`).
- **Sub-agents park on runs they launch detached.** Watch the PID from
  the orchestrator, then resume the agent with SendMessage.
- **An agent's repo must hold no future** (D-x) whenever the task has a
  known answer. `harness.run_o` cuts it. A dispatch works at HEAD, where
  there is no future to hide.
- **`pgrep -f` / `pkill -f` match your own waiting shell too.** Wait on
  a log line and kill by PID.
- **Always `uv run --project pipeline hobbes … --repo <target>` from
  this checkout** (ADR-094). Never `uv run` inside a target repo that
  has a `pyproject.toml`.
- **The oracle lane:**
  - build `oracle` from the tree before a regrade;
  - `go test -count=1 ./report/` after a record changes;
  - send a regrade's report to a file;
  - a foreign record is regenerated from its artifacts.
- **Olmo 3 on vLLM has no tool-call parser:** send no `tools`
  (`loop.py --tool-choice none`).
- **The key file is off the tree.** Never write its path into repo
  prose. It holds, among others, `anthropic_key` (Calvin's rounds ran
  with `--key-name anthropic_key`) and `claude_oauth_token` (the
  harness's default `--key-name`).

## Housekeeping

- Commit to `main`; never `git push` (Max publishes).
- One ADR per design decision; one BUILDLOG entry per session.
- Every concession gets a `C-n` in its segment file under
  `docs/constraints/`.
- Rewrite this doc; do not append to it.
