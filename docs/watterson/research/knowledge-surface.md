# Knowledge query surface (research for open-work item 2)

> Snapshot as of **2026-10-16**, gathered by two read-only subagents and
> spot-checked. Sources: `hobbes_public@2089e22`, this repo `@0bd3aaa`, the
> locked adapters in `adapters/node_modules` (claude-agent-acp 0.90.0,
> codex-acp 2.2.2), ACP Python SDK 0.12.1. Hobbes-public paths are relative to
> `~/hobbes_public`. Items marked **[unverified]** were not confirmed.

## The finding that reframes item 2

`hobbes-proxy` is **already an MCP server over stdio**, not an HTTP proxy in
front of a model API ("proxy" means tool proxy between agent and machine;
`go/internal/proxy/proxy.go:1-9`). So the question is not "Go proxy vs MCP".
It is **reuse the existing Go MCP server, or rewrite its queries in Python**.

## What hobbes-proxy exposes

`hobbes-proxy serve --repo DIR --role ROLE --knowledge-only [--log-dir DIR]`
registers six read-only tools and no `exec` (`proxy.go:136-139`;
`go/cmd/hobbes-proxy/main.go:65-84`). Each returns one plain-text block.

| Tool | Reads |
|---|---|
| `graph_neighborhood` | graph.json nodes, module_edges |
| `who_calls` | graph.json symbols, symbol_edges |
| `tests_guarding` | graph.json + tests.json |
| `get_module_doc` | `.hobbes/derived/docs/modules/*.json` (narrative pass; not produced here, DEC-001) |
| `list_invariants` | `.hobbes/invariants/*.yaml` (not produced here) |
| `list_blind_spots` | graph.json coverage, errors, containment |

- `interfaces.json` is read by no knowledge tool, only by the web UI
  (`go/internal/web/server.go:78`).
- Freshness: every graph answer starts `knowledge from ingest @ <sha12>` and
  adds `WARNING: … artifacts are stale` when HEAD differs
  (`go/internal/knowledge/knowledge.go:525-552`). Same rule as DEC-005.
- Artifact paths are fixed at `<repo>/.hobbes/derived/` (`knowledge.go:250,
  504`). It cannot read DEC-006 snapshot graphs, which live in
  `$HOBBES_CACHE_DIR/sessions/`.
- Caches graph.json/tests.json in memory by mtime+size (ADR-118).
- Size: the knowledge path is about 2,000 Go LOC (`internal/knowledge` 1,713,
  plus the proxy's `knowledge.go` and `internal/derived`). The binary also links
  policy, escalation, recorder, sink and version for `exec`. Tests: 61 in
  `knowledge_test.go`, 7 MCP-surface tests in `proxy/mcp_test.go`.
- Coupling: a flight journal is mandatory (`proxy.go:94-96`); knowledge-only
  writes `~/.hobbes/sessions/<id>/flight.jsonl` unless `--log-dir` is given.
  `--role` is required but only labels log events. Uses `git` for HEAD.
  No ports, no auth.
- Wiring in hobbes-public: sessions pass `--mcp-config` + `--strict-mcp-config`
  and allowlist `mcp__hobbes__*` (`go/internal/sandbox/sandbox.go:381-414,
  512-568`). Host use goes through `sandbox/knowledge-serve` (podman, or
  `HOBBES_KNOWLEDGE_HOST=1` for the host binary), hard-coded to hobbes_public
  itself.
- No Python implementation of the six queries exists. `hobbes.artifacts`
  loads the files; the tail rollups and `value_only_modules` that Go mirrors
  exist in Python, but `who_calls`/`tests_guarding` rendering and caveats do
  not.
- Built binary on this machine: `~/hobbes_public/go/bin/hobbes-proxy`
  (vcs 2089e22, clean). Go 1.26.5 is installed.

## Injecting an MCP server into sessions here

- `AgentSession.start()` already sends `mcp_servers=[]`
  (`pipeline/src/hobbes/providers/acp_session.py:240`); the agent's
  `mcpCapabilities` from initialize is read but ignored (`:232-238`).
- **stdio works on both locked adapters**; http too. Claude advertises
  `{http, sse}` and treats untyped entries as stdio
  (`claude-agent-acp/dist/acp-agent.js:1391-1394, 7741-7767`). Codex
  advertises `{http}` and **fails `session/new` on sse**
  (`codex-acp/dist/index.js:35516-35537`). Codex needs no `config.toml`, but a
  same-named server in the user's Codex config wins (`:35464-35473`).
- Claude also loads the user's and project's MCP servers
  (`settingSources`, `acp-agent.js:7897`); `strictMcpConfig` via
  `_meta.claudeCode.options` would limit it to ours.
- Tool names as seen in permission requests: Claude `mcp__<server>__<tool>`,
  kind `other`; Codex title `mcp.<server>.<tool>`, kind `execute`.
- **DEC-007 interaction:** MCP calls are never hard-denied, so in guarded they
  are asked on a TTY and denied otherwise. Read-only knowledge calls would need
  pre-approval to be usable. That is a permissions decision, not part of the
  surface itself. Whether Claude's `auto` mode or Codex's `auto_review` decides
  them first is **[unverified]**.
- `hobbes complete` sends no tools (DEC-004, no loop of our own), so only
  `ask` sessions would get the surface.
- No MCP library is in this repo's `pipeline/uv.lock`.

## Options

**A. Reuse hobbes-proxy, knowledge-only, as a stdio MCP server** passed in
`new_session`, with `--log-dir` under `$HOBBES_CACHE_DIR`. Two ways to get the
binary:

- **A1. Point at a hobbes-public-built binary** (configured path). No code
  copied; folds back trivially. Depends on a built hobbes_public checkout;
  version skew is caught only by the schema gate.
- **A2. Copy the Go source in verbatim** (as DEC-003 did for extraction) and
  build here. Self-contained, but pulls most of the Go module (the proxy
  package links exec, policy and escalation) for six tools, and is duplicated
  again on fold-back.

**B. Rewrite the six queries as a Python MCP server.** One language, could
read snapshot graphs and carry DEC-006 labels directly. But it ports about
2,000 LOC and 61 tests of Hobbes behaviour, which this repo is told not to
develop (CLAUDE.md), and drifts from the Go original.

Either way: DEC-006's snapshot graphs are out of the proxy's reach without a
change in hobbes-public (item 1 stays blocked under A), and pre-approving
knowledge tools needs a permissions decision (item 3a).
