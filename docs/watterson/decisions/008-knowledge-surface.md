# 008: Knowledge surface: hobbes-proxy, knowledge-only, from a built binary

- Status: accepted; first slice built and checked live on claude and codex (see notes)
- Date: 2026-10-16
- Closes: open-work item 2 (`docs/open-work.md`, knowledge query surface)
- Research: `docs/research/knowledge-surface.md`

## Context
Agents in `hobbes ask` sessions have no grounded view of the repo yet.
Hobbes-public's `hobbes-proxy` is already a stdio MCP server; with
`--knowledge-only` it serves six read-only tools over `.hobbes/derived/`
and nothing else (`hobbes_public@2089e22`, `go/internal/proxy/proxy.go:136-139`).
Our ACP sessions already send an `mcp_servers` list, empty today
(`pipeline/src/hobbes/providers/acp_session.py:240`), and both locked
adapters forward stdio servers to their harness. The options were to reuse
the proxy from a built binary (A1), copy its Go source in (A2), or rewrite
the queries in Python (B). Details are in the research note.

## Decision
1. **Reuse hobbes-proxy as built by hobbes-public (A1).** No Go code is
   copied into this repo. The binary is `$HOBBES_PROXY` if set, else
   `hobbes-proxy` on `PATH`.
2. **Launch it as a stdio MCP server named `hobbes`** in the ACP
   `session/new` request:
   `hobbes-proxy serve --repo <repo> --role developer --knowledge-only
   --log-dir $HOBBES_CACHE_DIR/knowledge`. Its mandatory flight journal goes
   to our cache, not `~/.hobbes/sessions`. Tool names match hobbes-public's
   sessions (`mcp__hobbes__*`).
3. **On by default when `ask` has `--repo`.** `--no-knowledge` turns it off.
   If the binary is not found, warn and run the session without it.
4. **Our policy allows our own knowledge tools once, on both routes.** A
   permission request for one of the six tools on server `hobbes` (Claude
   title `mcp__hobbes__<tool>`, Codex title `mcp.hobbes.<tool>`) is answered
   with the allow-once option, in guarded and in manual. This matches
   hobbes-public, whose sessions allowlist these tools. It never picks an
   "always" option (DEC-007). Any other MCP tool still follows DEC-007.

## Consequences
- The environment depends on a built hobbes_public checkout for knowledge.
  Version skew between the proxy and our artifacts is caught only by the
  proxy's schema gate (v3 or v4). Folding back into hobbes-public needs no
  code move for this piece.
- `get_module_doc` and `list_invariants` answer from files this repo does not
  produce (narrative pass deferred, DEC-001; no invariants), so they return
  nothing useful yet.
- The proxy reads only `<repo>/.hobbes/derived/`, so DEC-006 snapshot graphs
  and change labels are out of its reach. Open-work item 1 stays blocked; a
  fix belongs in hobbes-public.
- `hobbes complete` gets no knowledge tools (DEC-004, no tool loop).
- Unverified: whether Claude's `auto` mode or Codex's `auto_review` decides
  knowledge calls before they reach our policy; whether a same-named `hobbes`
  server in the user's Codex config shadows ours (codex-acp skips the
  injected one in that case).

## Note: first slice built (2026-10-16)
- `AgentSession(mcp_servers=[StdioMcpServer(...)])` sends stdio servers in
  `session/new` (`hobbes.providers.acp_session`).
- `hobbes.knowledge` finds the binary and builds the server; `RoutePolicy`
  gained `allowed` (titles to allow once); `hobbes ask` wires both and has
  `--no-knowledge`. Tests: `tests/test_knowledge.py`, plus additions in
  `test_permissions.py` and `test_providers_acp.py` (fake agent `mcp?` and
  `tool <title>`).
- Smoke-checked against the real binary
  (`~/hobbes_public/go/bin/hobbes-proxy`, vcs 2089e22) with the exact args
  `knowledge.server` builds, over raw MCP JSON-RPC on an ingested copy of the
  `miniapp` fixture. It listed exactly the six tools, accepted our artifacts
  (schema gate passed), answered `who_calls` with its ingest header, and wrote
  its flight log under `$HOBBES_CACHE_DIR/knowledge/`.
- Not checked live at the time; see the next note.

## Note: live check and server check (2026-10-16)
Run on an ingested scratch copy of `miniapp`, with the locked adapters
(claude-agent-acp 0.90.0, codex-acp 2.2.2) on the user's logins, through a
driver that dumped the raw permission requests, then again through
`hobbes ask`.

| Agent, route (mode) | Tools used | Request reached Hobbes? |
|---|---|---|
| claude, guarded (`auto`) | `who_calls`, `graph_neighborhood` (after a `ToolSearch` load) | no: Claude decided |
| claude, manual (`default`) | `who_calls` | yes: title `mcp__hobbes__who_calls`, kind `other`; allowed once |
| codex, guarded (`agent`) | `who_calls` | no: Codex's Guardian Review decided |
| codex, manual (`workspace-write`) | `who_calls` | yes: title and raw input only from the call's start (`mcp.hobbes.who_calls`, `{server, tool, arguments}`), merged by our client; allowed once |

Every answer carried the proxy's ingest header. This settles the
first "unverified" in Consequences: in guarded, both harnesses' own judges
decide knowledge calls, so our allowance matters only in manual.

**Server check** (the user asked for it if cheap). Claude's request carries
`_meta.claudeCode.mcpServer = {name: "hobbes", source: "dynamic"}`; the
SDK documents `dynamic` as a server passed in at process start, while
config-file servers read `user`, `project` or `local`
(`claude-agent-sdk/sdk.d.ts:1225-1230`). `PermissionRequest` now keeps
`meta`, and `knowledge.is_own_tool` requires, besides the title: Claude's
`mcpServer` (when sent) is `hobbes`/`dynamic`; Codex's raw input (when it has
`server`) names `hobbes` and one of the six tools. `RoutePolicy.allowed` is
now that predicate.

Still not distinguishable: Codex sends no source, and if the user's own
Codex config defines a server named `hobbes`, codex-acp keeps theirs and
skips ours (not checked live), so its calls would match. The user does not
expect competition for the name (2026-10-16).
