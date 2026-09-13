# Session handoff — the single resume point

**Reviewed 2026-09-13; Hobbes 0.2.12-beta on `main`.**
- **Tags:** `v0.2.10-beta` is the latest tag (Max, 2026-09-13). The one
  before it is `v0.1.8-beta`. 0.1.9-beta to 0.2.9-beta, 0.2.11-beta and
  0.2.12-beta are untagged. Tags stay Max's call each time.
- **Numbering** (Max; ADR-103's fourth amendment and its notes): patch
  by patch on 0.2.x, and the patch number counts on past nine
  (0.2.10-beta, not 0.3.0). A language addition is a patch, even when it
  reaches "supported"; a structural change bumps minor (ask).
- **Where work happens:** on `main`; publishing belongs to Max.

The session's record is the 2026-09-13 BUILDLOG entries.

## ⇢ START HERE NEXT SESSION: Max's open calls; then keep dispatching toward 40

0. **Latest (2026-09-13, last).** The top-level review again, then D-r
   fixed and C-134's amendment drafted:
   1. **The review** found three drifts: the ingest one docs commit
      behind HEAD; workstreams' header at 0.2.10-beta, with C-140's fix
      in no workstream; and W3's oracle item naming four oracles of six.
      All fixed (`0a56199`).
   2. **D-r fixed in 0.2.12-beta** (dispatched as `9cad`, merged as
      `0e9f5b3`). Verify's worktrees are plain clones with no alternates
      file, so `git` works in its container. Checked in the image on the
      host: `efc8`'s F2F test passes through the new `checkout()` and
      fails through a `--shared` clone.
   3. **ADR-108's C-134 amendment is drafted, not committed**, at
      `~/.hobbes/bench/c134/adr108-amendment-draft.md`:
      - a test is a function a Unity, CMocka or Check registration
        names;
      - a file that registers drops the naming convention;
      - a test program with `main` and no nameable test draws a
        `c-tests` record.

      Max's three calls are in item 1. On his word, it goes into ADR-108,
      and then it is dispatched.
   - **Standing from earlier today:**
     - the harness counts as validated after 40 sessions
       (`calvin-harness.md` §4: at least three areas, no false block
       unresolved, every `missed` fixed or registered, no refusal
       unread);
     - C-140 is 0.2.11-beta's residual.
   - The image and binaries are at 0.2.12-beta. **Restart the knowledge
     server** the next session opens with (C-65).
1. **Open for Max (no spend):**
   - **ADR-108's C-134 amendment** (item 0.3):
     - (a) Unity, CMocka and Check now, with criterion and the Unity
       fixture deferred;
     - (b) a file's registrations replace the naming convention;
     - (c) the `c-tests` record as the surfacing.
   - **The register and backlog review's remaining calls** (2026-09-13;
     the superseding, C-141 and the folding rule are done):
     - a segment of its own for the dispatch harness's entries (C-125,
       C-127–C-129, C-140);
     - whether `future_additions.md`'s "re-evaluate the harness if its
       weight stays this high" is obsolete;
     - C-120, kept active: `hobbes gate` grounds through the code it
       concedes (`gate.py:552`), and there it restates C-112, so a fold
       into C-112 is the candidate.
   - **C-140's structural fix.** Give the policy proxy and its logs a
     container of their own, as the egress proxy has. The doer then
     cannot reach its own flight log. This is a structural change, so it
     is his call.
   - **ADR-106.**
   - **C-139's finer extent** (the binding's own line, or the enclosing
     block). Take it only if a graded cell ever shows the recall cost.
     Nothing is owed now.
2. **Running a session** (`calvin-harness.md` §5):
   - Keep the token in the key file, and ingest at HEAD.
   - Decide the design in an ADR or an amendment **before** the
     dispatch, as ADR-111, ADR-046's amendment and ADR-107's 2026-09-13
     amendment were.
   - Name one small unit: `hobbes dispatch --task-file … --partition …
     --secrets "$HOBBES_SECRETS"`, with `--dry-run` first. Check that the
     argv carries `--settings` (the hook).
   - Watch dispatch's own stderr for "first edit at".
   - Review the session file and the diff. Merge with `git merge --no-ff
     -m … -m …` or `-F <file>`, never squash.
     - `git merge` does not read `-F -` from stdin. A heredoc there fails
       the merge silently in a `;` chain.
     - A heredoc followed by `&& \` in one Bash call is a syntax error;
       write the message to a file and pass `-F <file>`.
   - **A live test skips in the sandbox** (podman is not there), so
     verify cannot run it. Run every new live test on the host before
     merging (`2aa9`: the guarantee held, and the assertion was wrong).
   - **Testing a dispatch branch on the host before merging:**
     - make a worktree with its own `uv sync` if the Python side is
       tested; main's venv would import main's code. Go tests need no
       venv.
     - copy `scip/node_modules` and `tsextract/node_modules` as real
       trees, because lane B's container cannot follow a symlink out of
       the worktree;
     - run node tests as `node --test test/index.test.mjs`; node 22 does
       not take a directory.
   - **Toward 40 across three areas.** The fourteen logs so far cover:
     - extraction: C's lane A and its rework, the external veto, C-139;
     - the knowledge tools: the `path` alias, the language tables, the
       directory rollup;
     - the harness and sandbox: the progress hook, the containment, D-r;
     - the oracle lane: C's oracle.
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
4. **Carried, untouched this session:**
   - **The ingest's `.gitignore` edit.** Register it as a constraint or
     change it, on Max's reading (round 1's finding).
   - **pytest's 4 warnings:** a helper named `testmap_fixture` in
     `test_ttt_corpus.py` and `test_ttt_units.py` is collected as a test
     and returns a dict.
   - **`stringer` is not in the image.**
   - **The Gradle attach route's residuals** (C-67).
   - **`recall-collapsed` and H-23**; ADR-105/P13; the C-98 residuals.
   - **The comparative queue:** item 4; a foreign cell for C (both tools
     on cJSON and sqlite-vector). `oracle import` takes no `--lang c` yet
     (`bench/oracle/cmd/oracle/main.go`), so it is code first.
   - **C's residue:** C-134, C-135, C-133. The macro gap stays parked
     (C-131, `future_additions.md`).
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

## WHERE THINGS STAND (2026-09-13)

- **The Calvin harness** (ADR-107):
  - **Code:** `go/internal/egress`, `hobbes-session --egress` and
    `--claude-bin`, `pipeline/src/hobbes/run/dispatch.py`,
    `gate.derive_map`, `gate.map_files`.
  - **Records:** each session's state is under
    `~/.hobbes/sessions/<id>/` (`flight.jsonl`, `egress.jsonl`,
    `dispatch.json`, `gate.json`, `verify.json`, the brief). Since
    0.2.11-beta a session mounts only its own dir, never the root. The
    doer's own state is purged at exit and never kept (retention,
    0.1.22-beta). The log file is under `docs/calvin/sessions/`
    (fourteen, of the 40 that validate the harness).
  - **Task files** are kept off the tree:
    `~/.hobbes/bench/adr111-drivers/{hook,veto}-task.md`, and each
    later session's in its brief (`~/.hobbes/sessions/<id>/brief.md`).
- **The keyed Calvin rounds** (closed 2026-09-12): the records are in
  `docs/calvin/`, and the artifacts under `~/.hobbes/bench/calvin/`,
  `calvin-go/` and `calvin-gate/`.
- **The comparative graphics** (`docs/comparative/graphics/`): four,
  from 80 cells; `render.py check` green. The README embeds
  `same-key.svg`, and its wording stands (Max, 2026-09-13).
- **Atlas-0** (`bench/atlas0/`, 84 tests): worlds and runs under
  `~/.hobbes/bench/atlas0/`, and on the volume `hobbes-atlas0`.
- **TTT:** the Modal apps `hobbes-ttt` and `hobbes-ttt-cell` are
  deployed and idle; the volume `hobbes-ttt` holds the adapters,
  corpora, units and runs.
- **Register:** 141 entries: 100 active, 25 lifted, 11 superseded, 5
  folded (Max's calls, 2026-09-13; ADR-043 amended). C-141 registered
  the same day.
- **Suites** at 0.2.12-beta:
  - 1,482 pytest (host);
  - Go 354 `--- PASS`/`SKIP` lines (353 pass, 1 skip), counted at
    0.2.11-beta with the live egress and live mount tests run on the
    host. 0.2.12-beta moved only Go's version string, and
    `go/internal/version`'s test was re-run;
  - not re-run, since nothing they cover changed: 91 oracle-lane Go, 52
    vitest, 43 helper and 36 tsextract node, 84 atlas0.
- **Disk:** `~/.hobbes` is about 50 GB (swept 2026-09-11).

## NEXT (in order; no API spend)

1. **Max's calls** (START HERE item 1): C-140's structural fix, ADR-106.
2. **Keep dispatching named no-spend work through the harness,** one
   unit per brief, toward 40 across at least three areas:
   - C's residue (W1): C-134's test registrations (the amendment, on
     Max's word); C-135's autotools,
     Meson and Bazel roots and its surfacing gap; C-133's include path
     read from the database;
   - W1/W3's no-spend items: the decorated-declaration line convention,
     the C-15 namespacing ADR, `fetch-java` on the egress proxy;
   - `oracle import --lang c`, then the foreign C cells (the comparative
     queue);
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
- **A session sees only its own dir** (0.2.11-beta). A file a scripted
  session command needs goes under `<sessions>/<id>/`, never the root
  (`sandbox/exitcheck.py` does this).
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
