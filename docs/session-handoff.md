# Session handoff — the single resume point

**Reviewed 2026-09-12; Hobbes 0.1.22-beta on `main`.**
- **Tags:** 0.1.8-beta is tagged `v0.1.8-beta`; 0.1.9-beta to
  0.1.22-beta are untagged. Tags are Max's call.
- **Numbering** (Max; ADR-103's third amendment): the layer stays on
  0.1.x, patch by patch.
- **Where work happens:** on `main`; publishing belongs to Max.

The session's record is the 2026-09-12 BUILDLOG entry.

## ⇢ START HERE NEXT SESSION: the first dispatch ran (gate clear, verify pass) — its merge waits on Max; retention is in place (0.1.22-beta)

0. **Latest (2026-09-12, later).**
   - **The first real dispatch** (`S-20260912T151945Z-417f`): the
     `path` alias for `list_blind_spots` and `list_invariants` (W4,
     ADR-087 follow-up (a)).
     - **The run:** the doer used 38 of 40 turns and made one commit, by
       `hobbes-dispatch`. Egress: 3 tunnels, 0 refused. Policy: 12
       allows.
     - **The verdicts:** gate clear; verify pass (45 tests, 2 new, 0
       regressions). Checked again outside the sandbox: gofmt, vet and
       tests all pass.
     - **The merge is held for Max.** On his word:
       - fill the review block: `gate: right-clear`, `outcome: merged`,
         and the JSON note (the schema test's `required` check would
         pass vacuously if the field ever arrived as another type);
       - `git merge hobbes/S-20260912T151945Z-417f` (never squash);
       - bump to 0.1.23-beta with a CHANGELOG entry, and mark W4 (a)
         done;
       - rebuild the proxy and the image;
       - commit both session files. The first,
         `S-20260912T151728Z-96df`, was rejected at auth: the token was
         cut at 100 characters. Its outcome is `discarded`.
   - **Retention** (0.1.22-beta; ADR-107 amended) — Max: *store no
     reasoning; recorded sessions are evaluation rows, never model
     training.*
     - **Built:** the doer runs with `--no-session-persistence`.
       `hobbes-session` purges `.claude/`, `.claude.json*` and
       `.cache/claude-cli-nodejs/` from its HOME at exit, and dispatch
       re-checks and records the result. `units_from_git` skips the
       doer's commits and `docs/calvin/sessions/`.
     - **Purged:** the three harness sessions that held doer state.
       The real dispatch had stored 21 thinking-block lines; none are
       left.
     - **Register:** C-125 amended; C-129 added.
   - **For Max:**
     - The five owned-loop transcripts that carry `reasoning_content`.
       They are from 2026-08-22, the Qwen benchmark runs: `3d888dbe00ac-u6`
       and `f0c8a912cffb-u4`, `-u5`, `-u9`, `-verifier-1`, under
       `~/.hobbes/sessions/`. They are not Claude's. Delete them, or
       keep them.
     - C-129's reach: a merged doer's code is in the tree.
1. **What changed (2026-09-12).**
   - **The review first.** Max had the top-level docs reviewed. The
     findings are in item 4; most are fixed.
   - **Then the reframe.** *"O+gate is essentially a harness to stack on
     top of this environment, lacking hobbes session and egress
     allowlist. After the harness is set up, how we will verify is by
     using it through Hobbes development and appending to a log file per
     session."*
   - **Max's four decisions:**
     - the doer is **dispatched** from the developer's session;
     - the doer is **Claude Code on the subscription**;
     - **one file per session**;
     - the keyed rounds' held steps are **closed as superseded**.
   - **The record:** [`docs/calvin/calvin-harness.md`](calvin/calvin-harness.md)
     and [ADR-107](adr/107-calvin-as-a-harness.md).
   - **Built, 0.1.21-beta:**
     - `hobbes-session --egress`: the session on its own `--internal`
       network; `hobbes-proxy egress` on it and on the `hobbes-egress`
       bridge tunnels CONNECT to the named hosts alone and logs to
       `<session>/egress.jsonl`.
     - Claude Code as the doer: `--claude-bin`, and
       `$CLAUDE_CODE_OAUTH_TOKEN` passed by name.
     - `--claude-cred` withdrawn.
     - `hobbes gate --map derive`.
     - `hobbes dispatch`.
     - The reviewer path (`review.py`) on `--egress`.
   - **Checked, no spend:**
     - the full suites (1,371 pytest, 325 Go);
     - the **live** route test: a real session behind the real proxy
       got 200 from the listed host, 403 for another port, and no route
       without the proxy;
     - a Claude Code smoke: an invalid token made three tunnels to
       `api.anthropic.com:443` and got 401, no other host was reached
       for, and teardown was clean.
2. **Running a session** (done once; the steps stand).
   1. **Max makes the token:** `! claude setup-token`. It is
      interactive. Keep the token as `claude_oauth_token` in the key
      file (`--secrets "$HOBBES_SECRETS"`), or export
      `CLAUDE_CODE_OAUTH_TOKEN`.
   2. **Restart the knowledge server.** The image was rebuilt at
      0.1.21-beta, and a server keeps the image it started on (C-65).
   3. **Ingest at HEAD:** `uv run hobbes ingest`. Dispatch refuses an
      ingest at another SHA.
   4. **Pick a small, testable, real task, and name it.** A suggestion,
      for Max to name: W4's ADR-087 follow-up (a), `list_blind_spots`
      accepting `path` as an alias for `scope`. It is a Go change in
      `go/internal/knowledge` with tests, and it is parked until named.
   5. **Dispatch:** `uv run hobbes dispatch --task-file task.md --secrets
      "$HOBBES_SECRETS"`. Add `--partition` if the files are known;
      `--dry-run` first shows the whole stack.
   6. **Review:**
      - read `docs/calvin/sessions/<session>.md` and `git diff
        <parent>..hobbes/<session>`;
      - fill the review block (`right-clear | right-block |
        false-block | missed`; outcome);
      - merge or discard;
      - commit the session file with the work.
3. **For Max:**
   - **The validation criterion.** `calvin-harness.md` §4 proposes
     N = 20 sessions across at least three areas of the tree, no false
     block unresolved, every `missed` fixed or registered, and no
     refusal unread. The claim reaches those sessions only (C-127).
   - **ADR-106.** It stays held for M0-Go's design, which the closed
     rounds will not accept. Release the number, or keep it held.
   - **The reviewer path** (`hobbes review`'s soft verdicts) had never
     worked live: there was no `claude` in the image and no network. It
     can run now, given the token and `--egress`.
4. **The doc review's findings (2026-09-12).**
   - **Fixed:**
     - CLAUDE.md's Status was 272 of its 555 lines, a version history
       the CHANGELOG holds; it is now a short current-state block.
     - CLAUDE.md's read-next pointers: "resuming" had pointed at
       ADR-092, and Atlas-0 was labelled "the current work".
     - The handoff's "Held" list was written twice.
     - `workstreams.md` had no Calvin M0-Go or M0-Gate, and listed the
       one egress mechanism three times (W1 fetch-java, W3 C-41, C-124).
     - README's `hobbes-session start` could not run: there was no
       `claude` in the image, and `--claude-cred` mounted where HOME
       never looked.
     - `calvin.box.policy`'s stale doc path.
     - README's thirty-line Calvin narrative.
   - **Left:** `calvin-m0-gate.md` dates its handoff and §0a
     2026-09-12 beside 09-11 rulings. It is a record, left as is.
   - **Withdrawn:** the review first reported AGENTS.md as a byte copy
     of CLAUDE.md. It is a symlink to it; `cmp` had compared a file
     with itself.
5. **Carried, untouched this session:**
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
    `dispatch.json`, `gate.json`, `verify.json`, the brief, Claude
    Code's transcript under `.claude/`). The log file is under
    `docs/calvin/sessions/`.
- **The keyed Calvin rounds** (closed 2026-09-12): the records are in
  `docs/calvin/`, and the artifacts under `~/.hobbes/bench/calvin/`,
  `calvin-go/` and `calvin-gate/`. The package worktrees there were
  kept; every `calvin-go/*` and `calvin-gate/*` branch is merged.
- **Atlas-0** (`bench/atlas0/`, 84 tests): worlds and runs under
  `~/.hobbes/bench/atlas0/`, and on the volume `hobbes-atlas0`.
- **TTT:** the Modal apps `hobbes-ttt` and `hobbes-ttt-cell` are
  deployed and idle; the volume `hobbes-ttt` holds the adapters,
  corpora, units and runs.
- **Register:** 129 entries, 102 active, 24 lifted, 3 superseded.
  C-124 was superseded 2026-09-12; C-125–C-129 were added.
- **Suites:**
  - 1,372 pytest (4 `lane_b`);
  - 328 Go, subtests counted as before (HEAD `e130b34` read 304 by
    that count, 240 top-level);
  - 52 oracle-lane Go; 52 vitest; 36 + 36 node; 84 atlas0.
- **Disk:** `~/.hobbes` is about 50 GB (swept 2026-09-11).

## NEXT (in order; no API spend)

1. **START HERE item 2:** the first dispatched session, then keep
   dispatching real no-spend work through the harness.
2. **W0's remainder:**
   - the graph CI job forgets earlier red reviews;
   - `go/internal/version` and the union fixture's ownership still
     need resolution;
   - the registry-pulled image and the drift audit, when named.
3. **W1 and W3 items that spend nothing:**
   - the decorated-declaration line convention (131 of dagger's 258
     lane disagreements);
   - the C-15 namespacing ADR;
   - the directory rollup in `list_blind_spots`;
   - `fetch-java` on the egress proxy (C-66's next narrowing; the proxy
     exists now).

   Each is a good candidate for a dispatch once named.

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
