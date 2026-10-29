# watterson-environment: overview

> Status: **extraction moved in; provider layer, permission routes and hooks,
> knowledge tools, live chat sessions, a first TUI (opencode v2 on a Hobbes
> server) and tiered graph views (levels 0-4) landed** (2026-10-16). Next
> work: `open-work.md`, "Next up". This
> doc says what we're building and what we're building it from; what is still
> undecided is in `open-work.md`. Nothing here is an architecture commitment
> unless it links to an accepted record in `docs/decisions/`.

## Goal

We are building the **environment** piece of Hobbes. It has two parts:

- **Hobbes extraction (fixed core):** the pipeline from hobbes-public that turns
  a git repo into a deterministic, provenance-stamped code graph (`graph.json`,
  `tests.json`, `interfaces.json`). It moves into this repo (DEC-001). Hobbes is
  the user's own system and is never swapped out.
- **Provider connection (open choice):** an easy way to connect to model
  providers and agent tools. Paseo was the starting reference, but only its
  provider wrapping matters and we are not bound to it (DEC-002).

The result should be an environment where agents, connected through whichever
provider layer we choose, work against Hobbes's grounded view of the codebase.

**Thesis.** Hobbes's unique contribution is extraction, and what it enables:
a graph abstraction (tiered views devs read instead of code, DEC-014) and the
knowledge tools. Everything else (agent loops, harnesses, UIs, model routing)
already exists. We connect to those pieces rather than rebuild them, so Hobbes
complements existing environments instead of competing with them (DEC-004).

We will do this incrementally. Each slice starts with a decision record.

## Source 1: hobbes-public (extraction)

Local: `~/hobbes_public` · surveyed at `2089e22` · MIT · Python ≥3.12 (uv), plus Go and Node.

**What it is.** A multilingual, deterministic code-graphing environment. The
extraction package is `pipeline/src/hobbes/extract/` (about 27k lines across 36
modules). The CLI is `uv run hobbes ingest|narrate|…` from `pipeline/`.

**Pipeline stages** (see `extract_repo()` in `extract/__init__.py`):
1. Discover modules.
2. **Lane A, syntactic.** Tree-sitter extractors per language (Python, Go, Rust,
   Java, C, C++). TS/JS goes through `tsextract/` (ts-morph, Node).
3. **Packs.** HTTP routes and CLI entry points (Python, Go, TS, Rust), plus
   Terraform.
4. **Lane B, semantic.** SCIP indexers run inside a rootless Podman sandbox
   with no network. Off by default in tests (`HOBBES_SCIP=0`).
5. Range join into an evidence IR, then a semantic IR, then the graph.
6. Test map (the static reach of each test).
7. Emit SHA-stamped JSON to `<repo>/.hobbes/derived/`.

**Properties that matter here:**
- **No LLM in extraction.** `extract_repo()` is a pure tree-to-documents
  function. `hobbes.extract` imports nothing else from hobbes, which makes it
  the cleanest seam to take.
- Every edge is tiered (syntactic or semantic) and carries `file:line @ SHA`
  provenance. The rule is "honesty before recall".
- Runtime deps are pyyaml and tree-sitter grammars (tree-sitter pinned below
  0.26).
- The only model use near extraction is the **narrative pass**
  (`hobbes/narrate/`). It shells out to `claude -p --output-format json`, its
  runner is injectable, and its output is schema-validated.

**Coupled parts:**
- Lane B depends on Podman and the sandbox image.
- The MCP knowledge tools (`who_calls`, `tests_guarding`, …) are served by the
  **Go** `hobbes-proxy`, not by Python.
- `derive/`, `run/`, `bench/`, `review.py` and `graphdiff.py` are
  Hobbes-runtime specific.

**Key docs:** `docs/hobbes-architecture.md` §3 (extraction source of truth),
§10 (`.hobbes/` layout); `.hobbes/README.md`; `docs/extraction-evidence.md`.

> **Narrative pass deferred** (DEC-001). `hobbes/narrate/` (the module docs)
> does not move for now.

## Provider-connection candidate: paseo

One candidate among several (DEC-002). Of paseo, only its provider wrapping is of interest.

Local: `~/paseo` (fork of `getpaseo/paseo`) · surveyed at `a1da1b8f2` ·
Apache-2.0 · TypeScript npm-workspaces monorepo, Node 22.

**What it is.** A local-first agentic development environment. A Node daemon
launches and supervises coding-agent CLIs and streams their output over a
WebSocket API. Clients are an Expo app, an Electron desktop app, and a CLI.

**Provider layer** (`packages/server/src/server/agent/`):
- `agent-sdk-types.ts` defines the core interface:
  - `AgentClient`: `createSession`, `resumeSession`, `fetchCatalog`, `isAvailable`, …
  - `AgentSession`: `startTurn`, `subscribe`, `streamHistory`,
    `respondToPermission`, `interrupt`, `close`, …
  - `AgentStreamEvent`: a discriminated union of turn lifecycle, `timeline`
    items, permissions and usage events.
- `providers/*` holds one adapter per agent: Claude Code (via
  `@anthropic-ai/claude-agent-sdk`), Codex, OpenCode, Pi/OMP, and the ACP family
  (Copilot, Cursor, Kimi, …).
- `provider-registry.ts` builds the clients. `agent-manager.ts` owns turns,
  timeline persistence and broadcast.
- Wire schemas and the provider manifest live in `packages/protocol`.
- Credentials are **not** held by paseo. Each agent CLI uses its own login.
  Overrides go in `$PASEO_HOME/config.json` → `agents.providers.<id>`.
- Docs: `docs/providers.md`, `docs/custom-providers.md`.

**Note:** paseo's providers are *agent harnesses*, not raw LLM APIs. API
backends are reached by pointing a harness at another endpoint (for example
`ANTHROPIC_BASE_URL`).

**Extension points (no fork needed):**
- **Plugins** (`@getpaseo/plugin`). They get lifecycle hooks
  (`agent.created`, `agent.turn_started`, `agent.turn_ended`, which includes the
  turn's timeline items, `agent.closed`, and `workspace.created`). They also get
  "before" transforms on `agent.create` config and env, provider registration,
  custom RPCs, timeline items and UI surfaces. Examples are in
  `plugin-examples/`.
- **MCP**: the daemon serves `/mcp/agents`. Session config `mcpServers` injects
  extra MCP servers into an agent.
- **Client**: `@getpaseo/client` can subscribe to the daemon over WebSocket.

**Separability:**
- Easy to lift: the interface file plus `providers/` and their utilities.
- Hard to lift: `agent-manager.ts`, which reaches into workspace, git, speech,
  schedule and browser tools.
- Nothing in the provider layer depends on the UI.

## Provider layer (DEC-004, first slice)

Landed in `pipeline/src/hobbes/providers/`; glue only,
no agent loop. Callers import from `hobbes.providers`, never `acp`/`any_llm`:

- `AgentSpec` + `load_registry()`: claude/codex/gemini ACP launch argv, user overrides in `$HOBBES_AGENTS_FILE` (default `~/.watterson/agents.toml`). claude and codex run the adapter bins locked in `adapters/` (`npm ci` there); gemini is the installed CLI.
- `AgentSession(spec, cwd=, on_permission=, modes=, mcp_servers=, meta=)` / `run_prompt(...)`: async; `session.prompt(text)` yields `TextChunk`, `ThoughtChunk`, `ToolCall`, `ToolCallUpdate`, `Plan`, `PermissionDecision`, then `TurnEnded`; `cancel()`, `close()`.
- `on_permission(PermissionRequest) -> option id | None`; `deny_all` (default) / `allow_all`. A request carries the tool call's `kind`, `raw_input`, `paths` and ACP `meta`; `modes` picks the session mode by preference (DEC-007). `hobbes.permissions.RoutePolicy` decides by route.
- `complete(model, prompt)` / `stream(...)`: one any-llm call, `provider:model`, keys from env.
- `staleness.check_adapters()`: pin vs installed vs npm latest, 2-day cooldown, bundled harness versions; results are the generic `Freshness` dataclass (`hobbes/checks.py`, shared with the graph check of DEC-005).
- CLI: `hobbes agents [--check] | ask | chat | complete` (see `CLAUDE.md` Commands). `ask` and `chat` check graph freshness as the session starts (DEC-005); with `--repo` they attach Hobbes's knowledge tools (`StdioMcpServer`, DEC-008); `chat` re-extracts the graph between turns and labels each prompt (DEC-009).
- **Adapter staleness: landed** (was open question 2). The adapters are locked
  in `adapters/` (exact pins plus `package-lock.json`, so a bundled harness
  such as codex-acp's `@openai/codex` no longer floats), and
  `hobbes agents --check` reports the gap to npm. Bumps stay manual; the
  policy and how to bump are in DEC-004's notes.

## The environment application (DEC-011, DEC-013 to DEC-015, DEC-025 to DEC-028)

The environment is an application (DEC-011): a TUI with a graph view.

- **TUI:** our own opencode v2 code in `tui/opencode/` (from opencode's
  `dev`, trimmed to what the TUI binary ships and the TUI's own tests,
  DEC-026 to DEC-028), built by
  `tui/build.sh` (DEC-025), run
  with `--server` pointing at a **Hobbes server** (`pipeline/src/hobbes/serve/`,
  stdlib HTTP + events). It serves the slice of opencode's API the TUI needs
  (notes: `research/opencode-v2-api.md`). The TUI's agents are the permission
  routes, its models the registry's harnesses. `hobbes tui` (or the
  `watterson` launcher, `bin/watterson`, DEC-016) starts both, on the git
  repo here or else this folder.
  Hobbes itself is off until started from the app (`/hobbes` or the item
  under the prompt), which extracts a stale or missing graph first. The
  environment is called hobbes; its home screen shows a hobbes logo in
  place of opencode's (DEC-017).
  Session transcripts are kept as event logs under `$HOBBES_CACHE_DIR/tui/`.
- **Permissions in sessions:** the route policy (DEC-007) answers what a
  harness escalates; Claude sessions also carry Hobbes hooks that log every
  tool call and hard-deny agent-config edits ahead of Claude's judge
  (`hobbes.hooks`, DEC-010).
- **Graph views:** `hobbes levels` (`hobbes.levels`) computes tiered folder
  views from `.hobbes/derived/`, down to each module's symbols (level 3): at
  most 12 boxes per view, rolled-up edges, cycles, stubs to the rest of the
  repo, guarding tests. Flows (level 4) follow calls from each entry point
  in call order, one function per view, marking where extraction cuts them. `hobbes render` (verbatim from
  hobbes-public, DEC-012) prints the flat module graph as Mermaid.
- **Review page:** `hobbes review` / `/review` (`hobbes.review`, DEC-018)
  writes the level views as one stamped, self-contained HTML file in
  `~/.watterson/review/` and opens it: boxes laid out by ELK and drawn by
  React Flow (bundled from `review/`, DEC-019), flows as numbered steps,
  links into VS Code. Its Architecture tab (`hobbes.architecture`,
  DEC-020) shows the parts with entry points and outside systems, then
  components with roles, docstring summaries and layers, and a pipeline
  per command: the components its flow reaches, in order. Its Docs tab
  (`hobbes.repodocs`, DEC-021) holds the repo's Markdown, compressed, to
  read in the page. The terminal is the workspace; this is the review
  surface.
- **Graph panel:** a local opencode TUI plugin (`tui/plugins/graph/`,
  DEC-015) that the TUI compiles itself; `/graph` lists a view's boxes and
  drills down, fetching views from the Hobbes server over opencode's RPC
  call (`hobbes.serve.graph`).
- **Theme:** Hobbes's calm navy, `hobbes`, built in as the default
  (DEC-024, DEC-025); a `/themes` pick sticks.
- **Not yet joined:** `hobbes tui` sessions lack `hobbes chat`'s knowledge
  tools and graph refresh.

## Agent roles, dispatch and jobs (DEC-022)

A repo's roles live in `.hobbes/roles.toml` (out of git) with a standing
prompt file each (`hobbes.roles`). `hobbes dispatch` (`hobbes.dispatch`)
runs one worker in a role on its own worktree and branch, commits what it
left, refuses paths outside the role's `writes`, runs the repo's test
command, and merges into `main` when it passes. The worker hands back a
report through its `report` tool (`hobbes-worker`, relayed as the
coordinator's tools are) and the handoff ends merged, stopped or review
(tested, kept on its branch). `hobbes job`
(`hobbes.lead`) runs the coordinator role on a job in a fresh session: it
proposes a plan (approved on the terminal), dispatches workers through
the `hobbes-lead` MCP tools (`hobbes.lead_mcp`, relayed to the driver),
and its docs edits are committed after. In the TUI, a session's mode
(`/mode`, `hobbes.serve.opencode`) is default (the harness) or agent
mapped: each prompt runs as one job, the plan is approved in a form, each
worker runs in a child session that the coordinator's dispatch opens, and a
notice lists each handoff and the docs commit. A job runs up to the
mapping's `workers` (default 2) at a time, the rest queued; their merges
take turns, each tested on top of the one before (`dispatch` returns at
once, `wait` returns the handoffs). A model can write or change the
mapping on request (DEC-023, `hobbes.mapper`): `hobbes roles --edit` or a
TUI session in `edit mapping` mode, its `save_mapping` tool checked before
anything is written; the review page's Agents tab shows it.

## What the provider layer must give Hobbes

Whatever layer we choose has to provide these. The paseo column shows how one
candidate would do it.

| Hobbes needs… | e.g. in paseo |
|---|---|
| A grounded view of the repo inside agent sessions | `mcpServers` injection; plugin "before" transform on `agent.create` |
| Re-extraction when code changes | `agent.turn_ended` / `workspace.*` lifecycle hooks |
| Many providers behind one interface | `AgentClient` / `AgentSession` |
| A home for the knowledge query surface (hobbes-proxy, a stdio MCP server; DEC-008) | plugin RPC or MCP server |

Hobbes extraction is Python. A non-Python provider layer (like paseo, which is
TypeScript) means crossing a language boundary, for example with a subprocess
plus JSON, as `tsextract/` already does inside hobbes, or with MCP.

## Decisions

| # | Decision | Status |
|---|---|---|
| [001](decisions/001-extraction-pipeline-lives-here.md) | Extraction pipeline moves into this repo; narrative pass deferred | accepted |
| [002](decisions/002-provider-connection-layer.md) | Provider layer drives both harnesses and raw APIs | accepted |
| [003](decisions/003-extraction-move-mechanics.md) | Plain copy, keep hobbes layout, thin CLI, lane B runs where the image exists, separate cache | accepted; landed |
| [004](decisions/004-provider-libraries.md) | ACP Python SDK + any-llm; no agent loop of our own; lives in `hobbes/providers/` | accepted; first slice landed; adapters locked |
| [005](decisions/005-session-start-freshness.md) | Check graph freshness at session start; stale = a different commit; dirty is an informational tag | accepted; landed |
| [006](decisions/006-active-session-snapshots.md) | Active sessions: extract snapshots, refresh between turns (one running + one pending), label answers with changed files | accepted; engine built (`snapshot`, `session_graph`); wired into `hobbes chat` (DEC-009) |
| [007](decisions/007-permission-routes.md) | Permissions decided per request, never removed: `guarded` (default; harness judges on, hard-deny agent permission config, warn and ask on the rest) or `manual` (ask everything) | accepted; first slice built (`permissions`, `ask --route`); adjustments open |
| [008](decisions/008-knowledge-surface.md) | Knowledge surface: hobbes-public's `hobbes-proxy --knowledge-only` as a stdio MCP server in `ask` sessions; our policy allows its tools once | accepted; first slice built (`knowledge`, `ask --no-knowledge`); checked live on claude and codex |
| [009](decisions/009-live-session-graph.md) | Live sessions: `hobbes chat`; the proxy serves a per-session view swapped to snapshot graphs at turn start; the DEC-006 label prefixes each turn's prompt | accepted; built (`live_session`, `chat`); checked live on claude and codex |
| [010](decisions/010-claude-session-hooks.md) | Claude sessions carry Hobbes hooks via session `_meta`: observe and log every tool call, hard deny in front of the judge; Codex parked | accepted; built; checked live on claude |
| [011](decisions/011-application-on-opencode-tui.md) | The environment is an application; its TUI starts from opencode's, with a graph view | accepted; under way (DEC-013, DEC-014) |
| [012](decisions/012-render-moves-in.md) | `hobbes render` (Mermaid module graph) and the `artifacts` version gate move in verbatim from hobbes-public | accepted; landed |
| [013](decisions/013-tui-connection.md) | The TUI is opencode v2 (`@opencode/cli`), pinned in `tui/`, unmodified, with `--server` pointing at a Hobbes server (`hobbes.serve`, `hobbes tui`); corrects DEC-011's version | accepted; first slice built (fake agent through the real TUI) |
| [014](decisions/014-level-model.md) | Graph views are tiered levels (system, groups, components, modules, flows), folders by default, computed by `hobbes levels` | accepted; levels 0-4 built |
| [015](decisions/015-tui-graph-panel.md) | The graph panel is a local opencode TUI plugin (`tui/plugins/graph/`) listing views fetched over RPC; no merman, no Bun for now | accepted; first slice built |
| [016](decisions/016-app-launch-and-hobbes-start.md) | `hobbes` opens the app; a "Start Hobbes" control switches the Hobbes layer on per repo, with per-repo auto-start | accepted; slices 1-2 built (launcher, start control) |
| [017](decisions/017-name-and-home-logo.md) | The environment is "hobbes", `watterson` opens it; a hobbes logo (pixel art, kept in `~/.watterson/`) replaces opencode's on the home screen | accepted; built |
| [018](decisions/018-review-page.md) | Review happens on a stamped, self-contained HTML page (`hobbes review`, `/review`), apart from the TUI | accepted; first slice built |
| [019](decisions/019-review-renderer.md) | The review page draws with React Flow and ELK, bundled by esbuild into the one stamped file (`review/`); narrows DEC-018 | accepted; slice 1 built |
| [020](decisions/020-architecture-review.md) | The review page gets an Architecture tab: parts, components with roles and summaries, outside systems, from the graph alone | accepted; slices 1 and 2 built |
| [021](decisions/021-docs-tab.md) | The review page gets a Docs tab: the repo's Markdown, embedded compressed, rendered with marked and DOMPurify | accepted; built |

**DEC-001/003 landed**: `hobbes.extract`, `tsextract/`
and `scip/` copied from `hobbes_public@2089e22` in the hobbes layout, plus a
thin `hobbes ingest` CLI and the 60 pure-extract test files. Final test numbers
and the tests that changed are in `plans/extraction-move.md`. Commands are in
`CLAUDE.md`.

## Open work

Open questions and unbuilt pieces live in [`open-work.md`](open-work.md),
with an index for navigation. Item numbers are unchanged from when they lived
here.

## Out of scope for now

- The narrative pass (module docs), deferred by DEC-001.
- Changes to the source repos themselves.
- Pushing, publishing or remote CI.
