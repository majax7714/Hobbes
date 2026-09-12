# Session handoff — the single resume point

**Reviewed 2026-09-12; Hobbes 0.2.5-beta on `main`.**
- **Tags:** 0.1.8-beta is tagged `v0.1.8-beta`; 0.1.9-beta to
  0.2.5-beta are untagged. Tags are Max's call ("no need to tag yet").
- **Numbering** (Max; ADR-103's fourth amendment and its 2026-09-12
  note): patch by patch on 0.2.x. A language addition is a patch, even
  when it reaches "supported"; a structural change bumps minor (ask).
- **Where work happens:** on `main`; publishing belongs to Max.

The session's record is the last 2026-09-12 BUILDLOG entry.

## ⇢ START HERE NEXT SESSION: C is graded (0.2.5-beta); four asks wait on Max

0. **Latest (2026-09-12, last).** Max: "review top level documentation.
   then proceed with grading c against the oracle with a c repo. utilize
   hobbes and calvin as a harness."
   - **The doc review** (`348620d`). "Every compiler-graded cell at 100%"
     overclaimed quic-go (99.6%, all the oracle's grain) in README,
     CLAUDE.md and the architecture's status row. The counts caught up.
   - **ADR-110** (`b7d17b8`, before any cell): C's oracle is clang's
     front end over the ingest's compile database, contained. The
     pre-registration is P17–P25, with the draw rule (seed 20260912).
   - **Built through the harness,** in three dispatches:
     - `b126` discarded: stopped as a stall; its byte counts showed it
       was reading;
     - `5d5f`, unit A (the reader and merge), merged;
     - `9396`, unit B (the fixes, the contained run, the CLI), merged.

     Both merges kept the doer's authorship. Review found three reader
     defects (H-24–H-26). The first real cell found a mount defect
     (H-27), fixed by the developer (`17def60`).
   - **The cells** (contained, poison PASS on each):
     - `minic` 5/5, recall 7/7;
     - DaveGamble/cJSON 1,188/1,188, recall 62.0%. Every miss is a call a
       macro's expansion makes: 723 into Unity, and 5 through cJSON's own
       `cJSON_SetNumberValue` (C-131).
     - sqliteai/sqlite-vector, drawn at random (draw 1, bpftop, had no
       compile database): 851/854. The 3 are syntactic edges Hobbes got
       wrong, a `strcasestr` shim in a dead `#if` arm drawn over libc's
       (C-138). Semantic 851/851; recall 100%.
   - **0.2.5-beta:** §3.8's C row and `verification.py`'s pin; the image
     and the proxy rebuilt; the repo re-ingested at the commit. **Restart
     the knowledge server** the next session opens with (C-65).
1. **For Max, the asks from this session:**
   - **C-138's veto.** `evidence.join` takes lane A's guess wherever lane
     B has no in-repo answer, even where lane B resolved the site to a
     library. A veto there changes every language, and every cell's
     syntactic tier would be regraded. Yes or no.
   - **C's macro gap** (C-131's recall hole): cJSON's 728 pairs, 38% of
     its recall denominator.
     - Drawing the calls a macro's expansion makes, at the invocation,
       would close most of it; lane B's index already holds those
       references.
     - It needs a design, if wanted.
   - **The box policy:**
     - (a) allow `rm` inside `/work`, or state that the box's escalations
       are not a boundary while `python3 *` is allowed. A doer deleted
       its scratch file through `python3 -c` after `rm` expired.
     - (b) name `clang --version`, `cmake --version` and
       `bear --version` among the read-only probes.
   - **A progress signal for dispatches.** A doer that reads looks like
     one that is stuck (`b126`). C-125's named fix, a hook that reports
     Edit and Write to the flight log, would give one.
   - **Carried:** the harness's validation criterion (N sessions), and
     ADR-106.
2. **Running a session** (the steps stand; `calvin-harness.md` §5):
   - Keep the token in the key file.
   - Restart the knowledge server after an image rebuild (C-65).
   - Ingest at HEAD.
   - Name a small, testable task, then `hobbes dispatch --task-file …
     --secrets "$HOBBES_SECRETS"`: add `--partition`, and run
     `--dry-run` first.
   - Review the session file and the diff. Merge, never squash.
   - **From `b126`:** keep one brief to one unit a doer can finish in
     about 150 turns. Watch the worktree for its first edit (`git -C
     <session>/worktree status --porcelain`), not its egress; a doer may
     read for 20 minutes first (`5d5f`).
3. **The C oracle, for a regrade or a new cell:**
   - `bench/oracle/run-cell.sh <repo> <build root> <out> --lang c`
     (`--compdb` names a database). It needs the image with clang (built
     2026-09-12).
   - The cells and clones are under `~/.hobbes/bench/oracle/`
     (`{minic,cjson,sqlite-vector}-c/`, `repos/`). The draw's ordered
     pool is recorded in the sqlite-vector cell record.
4. **Carried, untouched this session:**
   - **The ingest's `.gitignore` edit.** Register it as a constraint or
     change it, on Max's reading (round 1's finding).
   - **D-r.** `hobbes verify`'s `--shared` clone makes `git` fail in the
     container for one Python key.
   - **`stringer` is not in the image.**
   - **The Gradle attach route's residuals** (C-67: `compilerArgs`
     replaced after configuration; external symbols without artifact
     names; Kotlin under the plugin).
   - **`recall-collapsed` and H-23**; ADR-105/P13; the C-98 residuals.
   - **The comparative queue's item 4:** codebase-memory-mcp and
     colbymchenry/codegraph; the competitor cells under the image.
   - **`build-logic/`** is recorded, not built (ADR-097).
   - **Off the table for now:** the three floor shapes and the Jelly key
     grain.

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

## WHERE THINGS STAND (2026-09-12)

- **The Calvin harness** (ADR-107):
  - **Code:** `go/internal/egress`, `hobbes-session --egress` and
    `--claude-bin`, `pipeline/src/hobbes/run/dispatch.py`,
    `gate.derive_map`, `gate.map_files`.
  - **Records:** each session's state is under
    `~/.hobbes/sessions/<id>/` (`flight.jsonl`, `egress.jsonl`,
    `dispatch.json`, `gate.json`, `verify.json`, the brief). The
    doer's own state is purged at exit and never kept (retention,
    0.1.22-beta). The log file is under `docs/calvin/sessions/`.
- **The keyed Calvin rounds** (closed 2026-09-12): the records are in
  `docs/calvin/`, and the artifacts under `~/.hobbes/bench/calvin/`,
  `calvin-go/` and `calvin-gate/`. The package worktrees there were
  kept; every `calvin-go/*` and `calvin-gate/*` branch is merged.
- **Atlas-0** (`bench/atlas0/`, 84 tests): worlds and runs under
  `~/.hobbes/bench/atlas0/`, and on the volume `hobbes-atlas0`.
- **TTT:** the Modal apps `hobbes-ttt` and `hobbes-ttt-cell` are
  deployed and idle; the volume `hobbes-ttt` holds the adapters,
  corpora, units and runs.
- **Register:** 138 entries, 111 active, 24 lifted, 3 superseded.
  C-124 was superseded 2026-09-12; C-125–C-138 were added.
- **Suites** (2026-09-12, at 0.2.5-beta; `--- PASS` lines, subtests
  counted):
  - 1,459 pytest (5 `lane_b`);
  - 331 Go (330 pass, 1 skip);
  - 91 oracle-lane Go (87 pass, 4 skip without a toolchain), the C
    end-to-end contained;
  - 52 vitest; 42 helper and 36 tsextract node; 84 atlas0.
- **Disk:** `~/.hobbes` is about 50 GB (swept 2026-09-11).

## NEXT (in order; no API spend)

1. **Max's four asks** (START HERE item 1). C-138's veto comes first: it
   is the one wrong-edge mechanism the C cells found.
2. **Keep dispatching named no-spend work through the harness**
   (START HERE item 2). The candidates:
   - C's residue (workstreams W1): C-134's test registrations; C-135's
     autotools, Meson and Bazel roots, and its surfacing gap; C-133's
     include path, read from the database;
   - W1/W3's no-spend items: the decorated-declaration line convention,
     the C-15 namespacing ADR, the directory rollup in
     `list_blind_spots`, `fetch-java` on the egress proxy.
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

- **Two sessions share this checkout.** A Remote Control session
  ("Dispatch background conversation") merged the first dispatch and
  wrote its reviews while this session was working. Before assuming
  `main`'s state or a file's content, read `git reflog` and the file
  itself.

- **The egress route.**
  - `hobbes-egress` is a shared podman bridge; it stays between
    sessions.
  - A session behind `--egress` gets `hobbes-int-<id>` (internal) and
    the container `hobbes-egress-<id>`; the launcher removes both.
  - A session killed from outside can leave them behind. Clean up with
    `podman rm -f -t 0 hobbes-egress-<id>` and `podman network rm -f
    hobbes-int-<id>`. The forced network removal takes the session
    container with it. `hobbes dispatch` does this on its own timeout.
- **A no-spend route check:** `CLAUDE_CODE_OAUTH_TOKEN=invalid
  go/bin/hobbes-session start --repo <a tiny repo> --role implementer
  --egress api.anthropic.com --task "Reply ok." --max-turns 1`. Expect
  a 401 in the envelope, tunnels to `api.anthropic.com:443` in the
  session's `egress.jsonl`, and no refusals.
- **After an image rebuild, restart the knowledge server** the session
  opened with (`.mcp.json` → `sandbox/knowledge-serve`). An old build
  drops a tail class it does not know from every count it prints — no
  error, just a smaller number (C-65).
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
  with `--key-name anthropic_key`) and, once made,
  `claude_oauth_token` (the harness's default `--key-name`).

## Housekeeping

- Commit to `main`; never `git push` (Max publishes).
- One ADR per design decision; one BUILDLOG entry per session.
- Every concession gets a `C-n` in its segment file under
  `docs/constraints/`.
- Rewrite this doc; do not append to it.
