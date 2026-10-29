# watterson-environment: open work

What is still undecided or unbuilt. The overview (`overview.md`) says what we
are building; decisions (`decisions/`) say why things are the way they are.

How to use this file:
- Each item becomes a decision record when it is taken up. Link the record
  here and update the status.
- Numbers are stable. Never renumber; mark an item closed instead of deleting
  it. Older records cite these numbers ("open question 3").
- Sub-items (3a, 3b, …) can be taken up on their own.

## Next up (as of 2026-10-18)

Current track (the user, 2026-10-18): owning the TUI's code (item 11,
DEC-026, DEC-027: now in `tui/opencode/`), in pieces; next 11b, hiding
what we do not back. The plan below
resumes after it.

The track of 2026-10-18, agent roles (item 10), is built and checked
live: DEC-022 (roles, dispatch, jobs, the TUI's modes and child sessions,
parallel workers under a cap) and DEC-023 (the model writes and edits the
mapping; the review page's Agents tab). What comes next is open; before
it, the track was the application: the TUI and its graph view (item 4).
In front of the list (the user, 2026-10-17): the review page's
architecture tab (DEC-020): slices 1 (system and component views) and 2
(a pipeline per command, with dispatch by reference) are built, and a Docs
tab (DEC-021). Left on the review page, not decided: DEC-019's slice 2,
an overrides file, flows in the code map following references. DEC-019's slice 2 (containers
that open in place, portal nodes) waits. Then, in order, each its own slice:

1. **The app's Hobbes start** (DEC-016): the start control is built
   (slice 2); left are the parity below (slice 3) and per-repo auto-start
   (slice 4).
2. **`hobbes tui` parity with `hobbes chat`** (DEC-016 slice 3): knowledge
   tools (DEC-008) and between-turn graph refresh with the prompt label
   (DEC-009).
3. **The map file** (DEC-014 decision 5): declare the top-level grouping
   and links between language roots, marked "declared".

Side work, any time: build up permission counts from real sessions (3a);
the "Connect provider" panel and unbacked features (now 11b); the session title (stays "New session", DEC-013 note); the
session list's delete and rename; resuming the harness's own session on
reopen (ACP `session/load`); a read-only diagram in the graph panel (needs a
decision: vendoring merman, DEC-015); a live look at flows in the graph
panel (DEC-014 level 4 note); flows from any function, built on demand;
the logo's idle animation (a "z" drifting over Hobbes, DEC-017);
a flaky test (the full
suite failed one test in 2 of about 10 runs on 2026-10-16, with no name
printed; `-rf` reruns passed); on 2026-10-18 a full run failed
`tests/test_snapshot.py::TestTakeSnapshot::test_same_tree_same_sha`,
which then passed 5 of 5 alone; whether it is the same one, and why, is
unknown (snapshot dates are fixed, so not a clock tick); the extraction gaps (item 8) wait for the user.

## Index

| # | Item | Status | Related |
|---|---|---|---|
| [1](#1-wire-dec-006-into-a-live-session) | Wire DEC-006 into a live session | closed: built, checked live | DEC-006, DEC-009 |
| [2](#2-knowledge-query-surface) | Knowledge query surface | closed: built, checked live; one accepted limit | DEC-008 |
| [3](#3-what-environment-owns) | What "environment" owns | partly decided | DEC-007, DEC-010 |
| [4](#4-graph-abstraction-for-devs) | Graph abstraction for devs | in progress; see Next up | DEC-011 to DEC-021, DEC-024, DEC-025 |
| [5](#5-narrative-pass) | Narrative pass (module docs) | deferred | DEC-001 |
| [6](#6-adapter-bumps) | Adapter bumps | ongoing | DEC-004 |
| [7](#7-lint-and-format-tooling) | Lint and format tooling | open | — |
| [8](#8-extraction-gaps) | Extraction gaps to take to hobbes-public | recorded; later | DEC-014 |
| [9](#9-local-keys-and-user-config) | Local keys and user config | noted; to think on | DEC-004, DEC-010 |
| [10](#10-agent-roles-and-the-coordinator-loop) | Agent roles and the coordinator loop | built: DEC-022 slices 1 to 3, parallel workers; DEC-023 | DEC-022, DEC-023 |
| [11](#11-owning-the-tuis-code) | Owning the TUI's code | in progress: 11a built; moved in (DEC-027) | DEC-025 to DEC-027 |

## 1. Wire DEC-006 into a live session

**Closed by DEC-009**, without a hobbes-public change: `hobbes chat` for
multi-turn sessions, a per-session view dir whose `.hobbes/derived` symlink
is swapped at turn start (the proxy reads only `<repo>/.hobbes/derived/`),
and the label as a prefix on each turn's prompt. Checked end to end with real
extraction and the fake agent, then live with claude and codex (DEC-009
notes): after an edit, the next turn's `who_calls` found the new caller.
Lane B re-extract time is left to per-repo, real-time extraction grading.

## 2. Knowledge query surface

**Closed by DEC-008**: `ask` and `chat` attach hobbes-public's `hobbes-proxy
--knowledge-only` as a stdio MCP server, and our policy allows its tools once.
Survey: `research/knowledge-surface.md`. First slice built and checked live
on claude and codex (DEC-008 notes): in guarded the harnesses' own judges
decide knowledge calls; in manual ours allows them once. Left: a same-named
`hobbes` server in a user's Codex config cannot be told apart (accepted as
unlikely). The proxy reads only `<repo>/.hobbes/derived/`; chat sessions
show it snapshot graphs through a view dir (item 1, DEC-009).

## 3. What "environment" owns

The environment replaces the web UI (the user, 2026-10-16) as the
workspace; review is a separate surface (the user, same day: work in the
terminal, review elsewhere, as with VS Code today). hobbes-public's web UI
is not reused (displayed poorly, the user). Policy: DEC-007
decides per request rather than removing commands (research:
`research/coding-agent-auto-permissions.md`). DEC-007's first slice is built
and checked live on claude and codex. In guarded, the harness judges decided
everything in both live checks, so graph signal on those actions needs the
compile or hook routes (3a).

Still open:

- **3a. DEC-007 adjustments** beyond picking a route: user rules, Hobbes-side
  memory, compiling policy into harness rules, feeding graph facts to a
  harness judge. Narrowed by DEC-010: Claude sessions carry Hobbes hooks
  (observe, log, hard deny in front of the judge). Left: what to allow or
  feed the judge once the counts are in; Codex (parked, reassess later).
- **3b. Sandbox sessions.**
- **3c. Codex rejects:** closed. Automatic rejects prefer `decline`; where
  Codex offers only `cancel` (file changes, MCP tool approvals, some
  commands) the turn still ends (DEC-007 note).
- **3d. Graph resolution of what a command runs** (DEC-007 decision 4).
- **3e. Codex `manual`** on `workspace-write` vs `read-only` (kept as a note).
- **3f. Codex trusts every session root** (`codex-acp` sets
  `trust_level = "trusted"`), so a repo's own `.codex/` config, rules and
  hooks load. Parked with Codex (DEC-010); reassess later.

## 4. Graph abstraction for devs

Graph views devs read instead of code; part of the thesis.

Shape (the user, 2026-10-16): the environment is an application with its own
TUI, a typical agentic one, with a tab that switches to a graph view of the
repo (DEC-011). The graph view is tiered drill-down levels, not one big
diagram: a chart of the few big pieces, where opening a piece shows its own
chart, down to the code (DEC-014; folders by default).

Built:
- `hobbes render` moved in (DEC-012): the flat Mermaid module graph.
- The TUI is opencode v2, pinned in `tui/` and unmodified, talking to a
  Hobbes server (DEC-013). `hobbes tui` runs turns, checked with the fake
  agent and then live with claude (tools, allow and reject). Transcripts
  are kept and survive a restart.
- `hobbes levels` builds levels 0-4 (DEC-014): folders, then a module's
  symbols with their calls and guarding tests, then flows from entry
  points in call order, with the extraction gaps' cuts marked.
- The graph panel in the TUI (DEC-015): `/graph` lists a view's boxes and
  drills down, over RPC from the Hobbes server.

Reuse vs build our own (the user, 2026-10-18): reuse made work for
efficiency, but where we cannot change opencode, an alternative or more
of our own is on the table. Rule of thumb, not decided: keep opencode
while the plugin API and its live render tree reach what we need (the
logo graft, DEC-017 note 2026-10-18); weigh building our own when a need
touches behavior neither reaches (prompt handling, routing).

Review happens on a stamped HTML page apart from the TUI (DEC-018, first
slice built): `watterson review` or `/review`. Its drawing moves to React
Flow and ELK, bundled into the page (DEC-019; survey:
`research/review-rendering.md`): slice 1 built (splines, counts, focus,
minimap); slice 2 containers that open in place (waiting). An
architecture tab beside the folder views (DEC-020; survey:
`research/architecture-review.md`): parts, components with roles and
summaries, outside systems, and a pipeline per command, from the graph
alone: slices 1 and 2 built. A Docs
tab (DEC-021): built; Mermaid drawing and search inside documents not.
Not built: comparing two
stamps, a live page, code previews, a tour along flows.

Next: "Next up" above (Hobbes start in the app, parity with `hobbes chat`, the map file).

## 5. Narrative pass

Module docs. Deferred by DEC-001.

## 6. Adapter bumps

`hobbes agents --check` reports them; bumps are manual with a 2-day cooldown
(DEC-004). Gemini CLI is not installed or locked, so DEC-007's gemini modes
and request shape are unchecked live.

## 7. Lint and format tooling

None is set up. hobbes-public only enforces gofmt.

## 8. Extraction gaps

Gaps in Hobbes's extraction that limit the graph views and permission
checks: fixtures ingested as code, no links between languages, argparse
dispatch, route handler ids, Go CLI targets, stdlib vs third-party
externals, `render.py`'s Python-only grouping. Listed with evidence in
`research/extraction-gaps.md`. Kept here; the user takes them to
hobbes-public later. Nothing in `hobbes.extract` changes here.

## 9. Local keys and user config

The user (2026-10-17): "some form of safe key system with hobbes", like
Terraform, with a local Hobbes user config under `.hobbes/`, which git
already ignores; "note and we'll think on that". Nothing decided.

- **Today:** `complete` reads provider keys from the environment
  (`hobbes.providers.llm`); harnesses use their own logins; agent
  overrides in `~/.watterson/agents.toml` may carry `env` values in plain
  text. hobbes-public's code reads `HOBBES_LLM_API_KEY` from the
  environment too.
- **Terraform's split, for comparison:** credentials per user, outside
  projects (`~/.terraform.d/credentials.tfrc.json`, plain text); a
  project's `.terraform/` and `*.tfvars` kept out of git by `.gitignore`
  convention; values marked sensitive are hidden in output.
- **Two cautions for keys under `<repo>/.hobbes/`:**
  - `.hobbes/` is kept out of git by `.git/info/exclude`, written by
    ingest into the one clone, not by a `.gitignore`: a fresh clone lacks
    it until an ingest, and `git add -f` still commits it.
  - Agents work in the repo with file access, so a key there is readable
    by the agent it is meant to configure. Claude sessions could hard-deny
    reading it through Hobbes hooks (DEC-010); Codex has no such hook.
- **Options to weigh:** the OS keychain (Secret Service, macOS Keychain,
  e.g. the `keyring` library) with config naming keys, never holding
  them; a per-user `~/.watterson/credentials` file (mode 0600) with a
  per-repo `.hobbes/config.toml` that refers to key names (Terraform's
  split); an encrypted file (age, sops); or the environment as now, plus
  a `.env` loader.
- **Open:** which keys Hobbes itself needs (provider keys for `complete`,
  the LLM key hobbes-public's proxy reads), and whether a session's agent
  should ever see them.

## 10. Agent roles and the coordinator loop

**Decided by DEC-022** (the user, 2026-10-18): roles as files
per repo gathered by a mapping; a thin code driver that starts a
coordinator from the docs and starts it fresh after each job; a
`dispatch(role, brief)` MCP tool; workers in worktrees, merged into
`main` when done; the user approves the plan; parent and child sessions
in the TUI. Slices: DEC-022 Consequences.
Settled since (DEC-022 note): role files under `.hobbes/`, out of git;
the driver runs the repo's test command before a merge.
Slices 1 and 2 built and checked live with claude (DEC-022 notes):
`hobbes roles`, `hobbes dispatch`, and `hobbes job`: a coordinator that
proposes a plan for approval, dispatches workers through `hobbes-lead`
MCP tools and commits its docs, fresh per job. Slice 3 settled (DEC-022
note): a per-session mode picker (default or agent mapped), the `y`
plan prompt, and a worker report ending merged, stopped or review.
Slice 3 built and checked live with claude in the TUI (DEC-022 notes):
the worker's `report` tool and its three endings; the mode picker, jobs
in mapped sessions, the plan as a form; workers as child sessions.
Parallel workers built (DEC-022 note): a cap (`workers`, default 2), a
queue, and a merge queue. Noted: MCP tool calls show as `other [...]`
rows; with parallel workers, `hobbes job` interleaves their output.
DEC-023 built: the model writes and edits the mapping on request, through
a checked `save_mapping` tool, from a TUI mode or `hobbes roles --edit`;
an Agents tab on the review page shows it.

## 11. Owning the TUI's code

**Decided by DEC-026** (the user, 2026-10-18): the TUI's code is ours, from
opencode's `dev` at `501b15a`; upstream is not tracked. **DEC-027** moved
it into this repo, trimmed, at `tui/opencode/` (what was left out:
its `NOTICE.md`). Each piece is a commit here. Pieces, in the user's
order where given:
- **11a. The switch** (built): from `dev`, with the logo slot and the
  `hobbes` theme; built and launched.
- **11b. Hide what we do not back** (next, the user's pick): the
  "Getting started / Connect provider" panel, and features our server
  does not answer (DEC-013: revert, share, shell; which ones, unverified).
- **11c. Our own name and version**: "opencode" in the UI text, the binary
  name, a version of our own (today it mirrors `2.0.29`, which
  `hobbes.serve` reports).
- **11d. Trim further** (built, DEC-028, 2026-10-29): the fork keeps what
  the binary's bundler loads, the TUI's own tests, and what those import
  or the build runs; 4,306 files → 1,987. Left as measured: `core`'s
  `models-dev/snapshot.txt` (5.5 MB) is loaded by the bundle, so it stays.
- **11e. Remove the service code** (opencode's own background server,
  upgrade, cloud paths), since we only run it with `--server`.
- **11f. Maybe**: move the plugin's features (graph panel, modes, the
  Hobbes item) into the source. Open.
- **11g. Open**: where `tui/opencode/` goes when this environment folds
  into hobbes-public.
- Noted: `packages/cli`'s `stats rendering > uses the OpenCode palette in
  color mode` fails here, also on untrimmed `dev` and without
  `COLORTERM`; cause unknown.

