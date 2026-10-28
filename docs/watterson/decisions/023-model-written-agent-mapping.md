# 023: The model writes and edits a repo's agent mapping on request

- Status: accepted; built (see notes)
- Date: 2026-10-18
- Builds on: DEC-022 (roles and the mapping), DEC-016 (starting Hobbes in
  the app), DEC-008 (knowledge tools), DEC-019 to DEC-021 (the review
  page and its tabs); open-work item 10

## Context
DEC-022's mapping is a hand-written `.hobbes/roles.toml` with a prompt file
per role. The user (2026-10-18): "something that would be super nice and
easy is if model could generate a per repo set of roles for agent mapping
when given instructions, devs could also tweak agent mapping by telling
model instead of themselves"; Hobbes should be recommended first when it
is not started, so the model can map from the repo's structure; and "a
tab in review which shows the agent mapping".

## Decision
1. **A mapper**: one harness session in a `mapper` setting, sent the
   mapping's format (`hobbes.roles`), the agents installed here, the
   repo's current mapping (the TOML and every prompt file) if any, the
   requests made earlier in the same session, and the new request. It
   reads the repo as it needs, with the knowledge tools (DEC-008) when
   the repo's graph is there. A fresh session per request: the files
   carry the state, as DEC-022's jobs do.
2. **It writes only through a checked tool** (the user's choice): MCP
   server `hobbes-mapper`, relayed to the driver as `hobbes-lead` is.
   `save_mapping(roles_toml, prompts)` takes the whole mapping (prompts
   keyed by their path under `.hobbes/`); the driver checks it as
   `hobbes.roles.load` would, plus that each role's agent is installed
   and its prompt is given or already there, and writes it only when it
   passes. Otherwise the errors go back to the model to fix. Prompt files
   no longer named are left in place. The files stay out of git
   (`ensure_ignored`).
   Not enforced: the harness's own file edits. Guarded's judges allow
   most without asking (DEC-007 notes), so the mapper is told not to
   edit files, and any other change it leaves in the checkout is
   reported after its turn, not reverted.
3. **In the TUI, a third mode** (the user's choice), `edit mapping`, in
   DEC-022's picker: each prompt in that session is a mapper request with
   the session's harness and route. The turn ends with a notice of what
   was saved, or why not.
4. **Hobbes first** (the user's choice): picking `edit mapping` while
   Hobbes is off asks "Start Hobbes first?" (start / continue without).
   A request while Hobbes is starting waits for it; a request while it
   is off runs without the knowledge tools and says so.
5. **On the command line**: `hobbes roles --edit "<request>"` with
   `--agent` (default `claude`), the same mapper, for scripts and use
   without the TUI.
6. **A review tab, Agents**, after Docs: the mapping as it is when the
   page is written (coordinator, test, branch, workers, then each role's
   agent, route, writes, review flag and its prompt), or a note that the
   repo has none.

## Consequences
- Slices, one at a time: (1) the mapper and `hobbes roles --edit`;
  (2) the TUI mode and the Hobbes recommendation; (3) the Agents tab.
- The mapper's output is as good as its model's reading of the repo;
  the checks cover form (it loads, agents exist), not judgment (whether
  the roles fit). The review tab is where a person looks it over.
- A mapping written for one clone stays in that clone (`.hobbes/` is out
  of git, DEC-022 note).

## Notes

### Note, 2026-10-18: slice 1 built
- `hobbes.mapper`: `run_mapper(repo, request, agent=…)`, the prompt
  (`RULES`, `FORMAT`, the agents, `current_mapping`, earlier requests, the
  request), `check` and `save`, and `describe` (the mapping as data, for
  slice 3). The relay script serves `hobbes-mapper` with `save_mapping`.
  Knowledge tools attach on the command line when the repo has a graph.
- `hobbes roles --edit "<request>" [--agent NAME] [--allow-permissions]`
  runs it, then lists the mapping as `hobbes roles` does; exit 0 saved, 1
  not, 2 could not run. The record is `mapper-<id>.json`.
- Tests (`tests/test_mapper.py`): `check`'s errors, `save` (out of git,
  old prompts kept, nothing written on errors), the prompt, a fake model
  saving through the relay, a failed save then a good one, other edits
  reported, `describe`, the CLI.

### Note, 2026-10-18: slice 2 built
- The server's third mode, `mapping` (`edit mapping` in the picker), needs
  no mapping, so a session or the home screen can start in it. Each
  prompt runs `run_mapper` with the session's harness and route and the
  session's earlier requests (kept in memory, not across a restart); the
  turn ends with the result's summary as a notice. Interrupt cancels it.
- Knowledge: on while Hobbes is on; a request while Hobbes is starting
  waits for it (`Layer.started`, with a notice); while it is off, a
  notice says the mapper reads files without the graph.
- The plugin's picker has the third entry and the footer shows `✎ edit
  mapping`. Picking it while Hobbes is off or failed asks "Start Hobbes
  first?" (opencode's confirm: Cancel / Start Hobbes).
- Tests: a save from a mapping session with Hobbes off (notices, the
  file, the earlier requests), a request waiting for a start in progress,
  the home screen's choice with no mapping. Checked in the TUI with no
  model run: the picker's three entries, the dialog, Start Hobbes turning
  it on with the mode set.

### Note, 2026-10-18: slice 3 built: the Agents tab
- The page data gains `agents` (`hobbes.mapper.describe`, read when the
  page is written; None without a mapping, the error and raw text when it
  does not load). The tab (`#r=<role>`) lists the mapping (test, branch,
  workers, coordinator) and the roles, coordinator first, beside the
  chosen role: its agent, route, knowledge, review flag and writes, and
  its prompt rendered as the Docs tab renders Markdown (sanitized). With
  no mapping it says how to make one.
- Checked in Chrome on the scratch repo's page (served on localhost: the
  extension does not open `file://` from a new tab): both roles, the
  coordinator badge, no console errors.

### Note, 2026-10-18: checked live by the user
The user ran it with a real model on a personal repo of their own and
reported that it "worked perfect". Which entry point and agent were used
was not recorded.
