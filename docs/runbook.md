# Runbook: how recurring operations are done on this box

These are procedures, not state. The resume point is
[`session-handoff.md`](session-handoff.md), and open items are in
[`currently-open.md`](currently-open.md). The scripts behind each
measurement are indexed in [`bench-drivers.md`](bench-drivers.md), and the
checks earlier sessions paid for are in [`lessons.md`](lessons.md).

## Running a Shanks session (`shanks/shanks-harness.md` §5)

- Keep the token in the key file, and ingest at HEAD before you start.
- The doer's model comes from the checkout: `HOBBES_DISPATCH_MODEL` in
  `.claude/settings.local.json` (on this box, `claude-opus-5-5`; Max,
  2026-09-30). `--model` overrides it.
- Decide the design in an ADR or an amendment **before** the dispatch.
- Name one small unit: `hobbes dispatch --task-file … --partition …
  --secrets "$HOBBES_SECRETS"`. Run it with `--dry-run` first, and check
  that the argv carries `--settings` (the hook) and the model.
- **Launch a dispatch detached:** `setsid nohup sh -c '… hobbes dispatch
  …; echo "exit $?"' > log 2>&1 < /dev/null &`. Never launch it as the
  assistant's background Bash, which is capped at ten minutes. A short
  background waiter over the log (`until grep -q '^exit '`) is fine.
- Review the session file and the diff. Merge with `git merge --no-ff`;
  never squash. **After you fill in the review block, re-render the
  tracker** (`pipeline/scripts/shanks_tracker.py render`).
- **Run every live and `lane_b` test on the host before merging.** They
  skip inside the sandbox.
- **To test a branch on the host:** `git worktree add` it, copy
  `scip/node_modules` and `tsextract/node_modules` in as real trees (not
  links), and run `uv sync` in its `pipeline/`. Node 22 prints `ℹ pass N`,
  not `# pass N`.
- While a dispatch runs, don't rebuild `go/bin`. While one is gating,
  don't re-ingest.
- To clean up a killed session: `podman rm -f -t 0 hobbes-side-<id>` and
  `podman network rm -f hobbes-int-<id>`.
- **A no-spend route check:** `CLAUDE_CODE_OAUTH_TOKEN=invalid
  go/bin/hobbes-session start --repo <a tiny repo> --role implementer
  --egress api.anthropic.com --task "Reply ok." --max-turns 1`. Expect a
  401, tunnels to `api.anthropic.com:443`, and no refusals.

## Regrading against stored keys

- **One cell:** re-ingest, run `oracle export`, then run `oracle grade
  --poison` against the cell's saved `oracle.json`.
- **Many cells:** run `~/.hobbes/bench/adr111-drivers/regrade3.sh` over a
  `cells.tsv` (ROOT=<worktree>). Run a pre pass only when ingest code
  changed. Never run two passes over one clone at once. The TS/JS
  equivalent is `~/.hobbes/bench/c177-tagged-template/run.sh` over its own
  `cells.tsv`.
- A regrade after a fix carries signed direction-of-fix lines in its
  record.
- **Pre-register before you grade a new cell.** Check `oracle-grading.md`
  §10 for the language's section first.
- Build `oracle` from the tree before a regrade. Run `go test -count=1
  ./report/` after a record changes. Send a regrade's report to a file.
  `run-cell.sh --lang cpp` runs O10.
- The comparative graphics are rendered by `bench/oracle/report/render.py`
  (`cells`, `render`, `check`). A caption that names cells reads them from
  `cells.json`.

## Held runs (only when Max names the run and its ceiling)

- **TTT cell:** deploy with `TTT_APP=hobbes-ttt-cell … deploy`, then run
  `ttt_cell.py run … --arm A2=<name> --arm A3=<name>`.
- **Atlas-0 drivers** build paths as strings: `Path.with_suffix` eats the
  tail of a dotted name. The grid's B4 cells run four at a time, at about
  14 minutes each.
- **Any model run:** state the total dollar ceiling, run a few units first,
  and compare the cost to the estimate before widening.
- **Olmo 3 on vLLM has no tool-call parser:** send no `tools`.

## Practical notes

- **Two sessions may share this checkout.** Before you assume `main`'s
  state or a file's content, read `git reflog` and the file itself.
- **A session sees only its own `in/`** (0.2.14-beta, ADR-112). An
  explicit `--network` gives the old file world (C-140 in full).
- **The sidecar and the route:** every session gets its own
  `hobbes-int-<id>` and `hobbes-side-<id>`, and `hobbes-egress` is a
  shared bridge. Name every probe container before you remove containers
  by name.
- **After an image rebuild, restart the knowledge server** (C-65), inside
  the session that rebuilt it, as that session's last step. Don't hand it
  on to the next session. Re-ingest at HEAD first, then stop
  its container (`podman ps`: the `hobbes-session:local` one `.mcp.json`'s
  `sandbox/knowledge-serve` started; check its image id against the
  rebuilt one) and reconnect `hobbes-knowledge` with `/mcp`.
- **Worktrees for subagents:** `git worktree add` from `main`. A worktree
  lacks the gitignored build outputs.
- **`pgrep -f` and `pkill -f` match your own waiting shell too.** Wait on
  a log line, and kill by PID.
- **Always run `uv run --project pipeline hobbes … --repo <target>` from
  this checkout** (ADR-094).
- **The key file is off the tree.** Never write its path into repo prose.
  It holds `anthropic_key` and `claude_oauth_token` (the harness's default
  `--key-name`).
- **Disk:** `~/.hobbes` is about 50 GB, plus the C++ cells.
  `cpp-cells/scummvm-cost` is the large one; sweep it if you need space.
