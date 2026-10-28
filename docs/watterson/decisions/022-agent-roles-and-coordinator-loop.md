# 022: Agent roles per repo, and a coordinator that plans, dispatches and starts fresh

- Status: accepted; slices 1 to 3 and parallel workers built (see notes)
- Date: 2026-10-18
- Opens: open-work item 10. Builds on: DEC-004 (the provider layer),
  DEC-007 (routes), DEC-008 (attached MCP tools), DEC-013 (the TUI server)

## Context
The user (2026-10-18) wants agent management in the environment: a repo
sets up agent roles, "specialized agent files for context", and a space
where context is "virtually unlimited due to session structure". The
highest agent only interprets the job, plans, sends work to working
agents, updates the docs once that work is committed and tested, then
ends its session and starts again from the fresh docs. In the user's
words, an "adjustable agent mapping pipeline".

hobbes-public (`2089e22`) has the parts in other forms:
- its developer session cycles on docs by hand: `CLAUDE.md` sends each
  session to `docs/session-handoff.md`, rewritten, not appended
  (`session-handoff.md:10`);
- Shanks (`pipeline/src/hobbes/run/dispatch.py:1`) hands one task at a
  time from the developer's session to a sandboxed Claude doer; nothing
  merges on its own;
- `hobbes run` (parked) is a Python coordinator over single-use agents
  with derived context, "phases, not personas"
  (`docs/experiments/mapped-agents/agent-mapping.md:40`); one session at
  a time, "the job is the short memory" (ADR-059).

Here the provider layer drives Claude and Codex sessions over ACP
(DEC-004), attaches MCP tools to them (DEC-008), and serves opencode's
TUI (DEC-013). opencode v2.0.29's TUI already shows child sessions: a
session with `parentID` (`packages/schema/src/session.ts:33`) is a child;
a `task` tool part whose `metadata.sessionID` names it draws as a link
to it (`packages/tui/src/routes/session/index.tsx:3135`); the session
list hides children and the session view has keys for child and parent.
Our server sends no `parentID` and lists no children
(`hobbes/serve/opencode.py:322`).

## Decision
The user answered each question (2026-10-18):
1. **A thin code driver owns the loop.** It starts the coordinator
   session from the repo's docs, and ends it once the job's docs are
   committed; the next job starts a fresh one. The coordinator (an LLM
   session) interprets, plans, dispatches and writes the docs. No
   session carries history from one job to the next: git and the docs do.
2. **Roles are small files, per repo to start**, gathered by a mapping
   file (the "adjustable agent mapping"). A role names its harness (an
   agent from DEC-004's registry), model, route (DEC-007), knowledge on
   or off (DEC-008), a standing prompt file, and what it may write. The
   mapping names the roles and which one coordinates. Hand-written role
   prompts differ from hobbes-public's derived context; its stance does
   not bind this environment.
3. **Dispatch is a Hobbes MCP tool** attached to the coordinator's
   session, as the knowledge tools are: `dispatch(role, brief)` runs a
   worker session in that role and returns a structured handoff.
4. **Each worker works in its own git worktree on a branch**; when it is
   done, its branch is merged into `main`.
5. **The user approves the plan** and sits at the top of the loop only.
   This changes when a user removes the agent mapping.
6. **It shows in the TUI as parent and child sessions:** the
   coordinator's session is the parent, each worker a child with
   `parentID`, and each dispatch a `task` part that links to its child.

## Consequences
- Context is bounded by the docs a fresh coordinator reads, so doc
  hygiene carries the design: caps, one home per fact, a handoff that
  is rewritten.
- A worktree is isolation for merging, not a security boundary: workers
  run as harness sessions under DEC-007's routes and DEC-010's hooks,
  not in hobbes-public's Podman sandbox.
- Our server learns `parentID`, child listing and `task` parts; `task`
  and `subagent` are reserved tool names today (`hobbes/serve/turns.py:44`),
  renamed so the subagent view never shows.
- Not decided yet, each settled in its slice:
  - where the role files live: committed in the repo, or under
    `.hobbes/` (kept out of git per clone by `.git/info/exclude`);
  - what "tested" means before a merge (the worker, a verifier role, or
    the driver running the repo's test command), and what happens on a
    failed test or a merge conflict;
  - workers one at a time or in parallel;
  - how the plan approval is asked in the TUI;
  - what a session without a mapping does, and where the user approves
    then (decision 5);
  - the handoff's shape.
- Proposed slices, one at a time: (1) role files, the mapping and
  `dispatch` with one worker in a worktree, merged on success, from the
  CLI; (2) the driver: coordinator from docs, plan approval, docs commit,
  fresh session; (3) the TUI: parent and child sessions; then parallel
  workers.

### Note, 2026-10-18: role files out of git; the driver tests before a merge
The user answered two of the open points:
- **Role files and the mapping stay out of git for now**, under the
  repo's `.hobbes/`. Committing them would be more efficient, but not
  worth the small safety risk yet. `.hobbes/` is excluded only once an
  ingest writes `.git/info/exclude`, so whatever writes role files there
  must add the exclusion itself.
- **"Tested" means the driver runs the repo's test command**, named in
  the mapping, on the worker's branch; it merges only when that passes.

### Note, 2026-10-18: slice 1 built
The user agreed to this design (2026-10-18):
- `hobbes.roles` reads `.hobbes/roles.toml`: `test` (required),
  `branch` (default `main`), `coordinator` (optional, unused until slice
  2), and `[roles.<name>]` with `agent`, `route`, `knowledge`, `prompt`
  (under `.hobbes/`) and `writes` (`fnmatch` globs; `*` crosses `/`).
  Unknown keys are errors. **No `model` yet:** `AgentSession` has no way
  to choose one (`hobbes/providers/acp_session.py`), and whether the
  locked adapters accept one is unverified.
- `hobbes.dispatch` and `hobbes dispatch --repo DIR --role NAME
  "<brief>"`: a worktree under `$HOBBES_CACHE_DIR/dispatch/<repo>-<hash>/`
  on `hobbes/<role>-<id>`; the worker gets `[hobbes role: <name>]`, its
  standing prompt, `[hobbes brief]` and the brief as one prompt; the
  driver commits what it left; no merge on a path outside `writes`; if
  `main` moved, it is merged into the branch in the worktree first, so
  conflicts never reach the user's checkout and the test runs on what
  `main` becomes; then the test command; then `merge --no-ff`, only when
  the checkout is on `main` with no tracked changes. **A failed test, a
  conflict or a refused merge stops and reports**, keeping the branch;
  nothing guesses a fix. The handoff is the driver's JSON, saved beside
  the worktrees. `hobbes roles` lists and checks the mapping and writes
  the `info/exclude` line.
- Knowledge tools answer from the repo's own graph, not the worktree's.
  The test command runs in a fresh worktree, so a repo whose tests need
  untracked setup (a virtualenv, `node_modules`) needs a command that
  makes it.
- Checked with the fake ACP agent on temp repos (`tests/test_dispatch.py`,
  23 tests): a merge, a failed test, a path outside `writes`, no change, a
  dirty checkout, another branch checked out, `main` moving cleanly and
  with a conflict.
- Checked live with claude (guarded, knowledge off, no
  `--allow-permissions`) on a scratch repo: asked to add `sub(a, b)` with
  a test, it edited both files and ran the tests (Claude's own judge
  allowed it; nothing escalated); the driver committed, the test passed,
  and the work merged into `main` with the branch and worktree removed.
  The scratch repo had no `.gitignore`, so the worker's `__pycache__`
  files were committed too: the driver commits what git would add, so a
  repo without ignores for build output gets it in the merge.
- What the environment adds to a target repo stays out of git: `.hobbes/`
  through `info/exclude`, which linked worktrees share; worktrees, logs
  and handoffs in the cache. A repo that tracks files under `.hobbes/`
  (hobbes-public tracks 20) gets only `.hobbes/derived/` from the ingest's
  helper, so `hobbes.roles.ensure_ignored` adds `.hobbes/roles.toml` and
  `.hobbes/roles/` itself. Still visible to git: branches
  `hobbes/<role>-<id>` kept after a run that did not merge (a
  `git push --all` would push them).

### Note, 2026-10-18: slice 2 built
The user agreed to this design (2026-10-18):
- `hobbes job --repo DIR ["<job>"]` (`hobbes.lead`): one job per run, or
  one per line, each in a fresh session in the mapping's `coordinator`
  role at the user's checkout, which must be on the branch with no
  tracked changes. The prompt is the role's standing prompt, the loop's
  rules (`LOOP_RULES`) and the job.
- The coordinator's tools come from `hobbes.lead_mcp`, a stdlib stdio MCP
  server named `hobbes-lead` that relays each call over a Unix socket to
  the driver, as DEC-010's hook client does; they are allowed once
  without asking (`is_lead_tool`). `propose_plan` asks on the terminal
  (`y`, `y <comment>`, or what to change, sent back) and is refused
  without one; `dispatch` runs slice 1 for one worker at a time and
  returns the handoff, refused before an approved plan, for the
  coordinator's own role, and once the checkout has tracked changes;
  `finish` records the summary.
- After the turn, what the coordinator changed is committed as
  `docs: <job>` (trailer `Hobbes-Job`) when all of it is within its
  role's `writes`, else left with the reason. The record is
  `job-<id>.json` beside the dispatch records. Exit 0 when finished with
  every dispatch merged, 1 otherwise, 2 when it cannot start.
- Tests (`tests/test_lead.py`): the tools through `Lead.handle`, the
  relay's MCP exchange, the relay through the driver's socket to a real
  dispatch, and `run_job` with a fake coordinator. The fake agent cannot
  call MCP tools, so plan, dispatch and finish from a model are checked
  live only.
- Checked live on the scratch repo, claude as coordinator and as
  implementer, `--allow-permissions`, in tmux with the plan approved by
  `y` there: the coordinator read the docs, proposed two steps, dispatched
  one implementer (the `dispatch` call blocked for the whole worker run
  without a timeout), the work merged, it updated `docs/notes.md`, the
  driver committed it, and it called `finish`; exit 0. Not checked:
  codex as coordinator, a rejected plan from a model, a failed dispatch
  that the coordinator must handle.

### Note, 2026-10-18: slice 3 settled: the mode picker, the report, the order
The user answered the remaining open points for the TUI:
- **A per-session mode picker in the TUI**, a dropdown like the
  workspace switcher, with two entries: **default** and **agent mapped**.
  Default is today's session: the harness's typical behavior, with no
  structured mapping; that settles "a session without a mapping". Agent
  mapped is the coordinator loop; it needs a mapping with a
  `coordinator`. The TUI's plugin API has a select dialog
  (`ui.dialog.select`), so the picker is a plugin command and a footer
  item, as `/hobbes` is (DEC-016); the server keeps the mode per session.
- **Plan approval stays the `y` prompt**: the same answers as the
  terminal (`y`, `y <comment>`, or what to change). In the TUI it is
  asked through opencode's form prompt (unverified there until built).
- **The handoff is the worker's report of its work** plus the driver's
  facts. It ends one of three ways: **merged** (a clean commit merged
  into the branch), **stopped** (after a failure, with the reason), or
  **review** (tested, kept on its branch, not merged). The worker writes
  the report and says done, blocked or review through a `report` tool;
  the driver still decides a merge from the facts, so a report of done
  never skips a check.
- **A commit pauses for review when the worker asks or its role sets
  `review = true`.**
- **Order**, each its own slice: (3a) the report and the three endings,
  from the CLI; (3b) the mode picker, jobs in agent-mapped sessions and
  plan approval in the TUI; (3c) workers as child sessions. Then
  parallel workers.

### Note, 2026-10-18: slice 3a built: the worker's report
- Each worker session gets a second relayed MCP server, `hobbes-worker`
  (`hobbes.lead_mcp` with the server name as its second argument), with
  one tool, `report(outcome, report)`: `done`, `blocked` or `review` and
  the worker's own account. It is allowed once without asking
  (`is_worker_tool`); the prompt gains a `[hobbes report]` section
  (`REPORT_RULES`) before the brief. The socket helper (`tool_relay`) and
  the tool matcher (`is_server_tool`) are now shared with `hobbes job`.
- The `Handoff` gains `outcome` (`merged`, `stopped` or `review`), `asked`
  (the worker's word, or none) and `report`. A report of `blocked` stops
  before the test; `review`, from the worker or a role's new `review =
  true`, stops after a passing test, the branch kept. A worker that never
  reports is taken as done, so a model that forgets the tool still merges
  through the same checks; the last report wins.
- Exit codes (chosen here, not by the user): `hobbes dispatch` exits 0 for
  merged or review and 1 for stopped; `hobbes job` exits 0 when finished
  with no dispatch stopped.
- Tests: the fake agent gained `call <server> <tool> <json>` (a real
  `tools/call` through the session's MCP server) and ` && ` to chain it
  after an edit, so the report runs end to end through the relay. Not
  checked live: a model calling `report`.
- Checked live, 2026-10-18, claude as implementer, `--allow-permissions`,
  on a fresh scratch repo (a tiny Python package, `python3 -m unittest`):
  asked to add `sub`, the worker found the tool (through Claude's
  ToolSearch), reported done with what it changed and checked, and it
  merged; exit 0. Asked to add `mul` and report it for review, it reported
  review; the test passed, the branch was kept unmerged; exit 0. The hook
  logs show no permission request for `report`: Claude's guarded mode did
  not ask, so `is_worker_tool` went unused there. Not checked: codex, a
  report of blocked from a model.

### Note, 2026-10-18: slice 3b built: the mode picker and jobs in the TUI
- **The mode** is per session on the server (`Session.mode`, `default` or
  `mapped`), read and set by RPC `hobbes.mode {sessionID?, mode?}`; with no
  session id it is the mode new sessions start in (the home screen's
  choice, in memory only). `mapped` is refused, with the reason, unless the
  repo's mapping loads with a `coordinator`. A change is pushed as
  `rpc.hobbes.mode` and kept as a `hobbes.mode.selected` line in the
  session's log, which the TUI never sees, so it survives a restart.
- **The picker** is the plugin's `/mode` command and a footer item (`◇
  default` / `◆ agent mapped`, a click opens it), opencode's
  `ui.dialog.select`; it follows the route (the session on screen, or new
  sessions on the home screen).
- **A prompt in a mapped session is one job** (`run_job`, a fresh
  coordinator each time): the coordinator's events are the session's turn;
  the workers' are not shown (child sessions are 3c) and their permission
  requests are asked here without a link to a tool part. The job ends with
  a `session.synthetic` notice: each handoff's ending with the worker's
  report, the docs commit, the summary. The session's own harness and
  route are not used. A checkout that is not clean on the branch fails the
  turn with the reason. Interrupt cancels the job; `dispatch` now runs its
  git and test steps in a thread, finished even when cancelled, so the
  server keeps answering during a test.
- **The plan is an opencode form** (`form.created` with a `location`,
  which the TUI requires for form events): the plan as `metadata.message`,
  one `answer` field with `y` and `n` options and a typed answer, parsed as
  on the terminal (`parse_approval`). Esc dismisses it: not approved, no
  comment. Served: `GET`, reply and `DELETE` under `/api/session/:id/form`.
- Checked live in the TUI (tmux, fake agents through `$HOBBES_AGENTS_FILE`
  on a scratch repo): the picker, the footer item, the plan form, a typed
  `y looks right` reaching the coordinator, the merge, the docs commit and
  the notice. Not checked: a real model as coordinator in the TUI, a long
  plan (the form does not scroll), the footer click (keys only in tmux).

### Note, 2026-10-18: slice 3c built: workers as child sessions
- Each dispatch in a mapped session gets a child session (`parentID`, its
  agent the role, its title the brief's first line), created as the worker
  starts (`Lead`'s `on_dispatch`) and ended with the handoff
  (`on_handoff(record, error)`, also on a failed or cancelled dispatch):
  the worker's events are its turn, its permission requests are asked
  there (linked to its tool parts; the TUI shows them in the parent too),
  and a notice gives the ending and the worker's report. The session list
  answers `parentID`: a parent's children, and only roots for `null`.
- The coordinator's `dispatch` call, picked by its title
  (`server_titles`), is drawn as opencode's subagent row (`task`: the
  brief's first line, the role); `Turn.link` sends the child's id as
  `metadata.sessionID` (`session.tool.progress`, and again on success,
  which replaces a call's metadata), so the row opens the child.
- A child takes no prompts. Interrupting the parent or a child cancels the
  running dispatch first, then the job: a coordinator's harness waits in
  its `dispatch` call and does not end its turn before the worker does.
  The relay (`tool_relay`) now cancels calls still running when it closes,
  answering them "Interrupted", which also keeps a Ctrl-C in `hobbes job`
  from waiting on a worker.
- Checked live in the TUI: with fake agents, the subagent row, the
  Subagents picker (Down, then ctrl+a for finished ones) and the child's
  view; with claude as coordinator and implementer on a scratch repo, a
  job to add `div`: the plan form (approved with `y`), the worker's
  commands and `report` in its child session, the merge, the docs commit
  and both notices; the parent's log has the `task` row linked to the
  child. An earlier attempt went to plain claude by mistake: the restarted
  server's home mode was back to default, which is kept in memory only.

### Note, 2026-10-18: the home screen's mode is kept
The user asked for it after the slip above. The mode new sessions start
in is saved per repo in the TUI store's `home-modes.json` and read when
the server starts; a saved `mapped` still needs the mapping when a
session is created, else the session starts in default.

### Note, 2026-10-18: parallel workers, with a cap and a queue
The user (2026-10-18): "parallel workers set a cap and queue to avoid
conflicts". Settled here, the details chosen by the agent:
- **The cap** is the mapping's `workers` (top level of `roles.toml`, a
  whole number, default 2). Up to that many workers run at a time in a
  job; later dispatches wait in a first-in, first-out queue and start as
  slots free.
- **The merge queue**: workers share a lock over their finish steps
  (commit, main merged in, the test, the merge), so they take turns in
  the order they finish. Each branch takes in what merged before it and
  is tested on that, so two branches never both merge untested together;
  a real conflict stops the later one with the reason, as before.
- **The coordinator's tools**: `dispatch` returns at once with a ticket,
  `started` or `queued behind N`; a new `wait` blocks until every
  dispatched worker is done and returns the handoffs not returned before
  (each with its ticket). This does not depend on a harness running tool
  calls in parallel. `finish` is refused while workers run. The loop's
  rules name the cap and say to give units that change the same files to
  one worker, or dispatch the later after `wait`. A dispatch that cannot
  run, or whose harness fails, becomes a stopped handoff, not a lost task.
- After the coordinator's turn the driver waits for any workers still
  running before it commits the docs; a cancelled job cancels its
  workers, queued and running (`Lead.stop`). In the TUI each dispatch's
  child session is made when queued (so the parent's row links to it at
  once) and its turn starts when it leaves the queue; one cancelled in
  the queue says so.
- `Lead`'s `on_dispatch(role, brief)` now answers a `Worker` (its own
  `ask`, `on_event`, `start`, `done`), replacing slice 3c's single-worker
  callbacks.
- Tests: three workers under a cap of 2 (two start, one queues, all merge),
  a conflict in the merge queue, `finish` refused and `stop` cancelling a
  queued worker, and two parallel children in a mapped session, each
  linked.
- Checked live, 2026-10-18, in the TUI with claude as coordinator and
  implementers (cap 2) on the scratch repo: a job with two units in
  separate files. The coordinator planned them as parallel, dispatched
  both, called `wait` and then `finish`. Both worker branches start at the
  same commit (they ran at once); the first merged, the second took it in
  (`target_moved`, a merge commit on its branch), passed the test on the
  combined code and merged; the docs commit followed. Not checked live:
  the queue past the cap, a conflict between parallel workers, codex.
