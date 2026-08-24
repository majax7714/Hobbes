# ADR 013: Official MCP Go SDK for the proxy

Date: 2026-08-10
Status: accepted

## Context

M4's tool proxy is an MCP server (architecture §5.2 tier 2): agents get no
raw shell, only an MCP `exec` tool. The daemon is Go (D1), so it needs a Go
MCP implementation. The docs pick the protocol but not the library.

## Decision

Use the official SDK, `github.com/modelcontextprotocol/go-sdk` (v1.7.0,
post-1.0 stable). It is maintained by the protocol's stewards, tracks spec
revisions, generates tool input schemas from Go structs, and ships both
`StdioTransport` (production: Claude Code spawns the proxy) and
`NewInMemoryTransports` (tests: real client↔server round-trips in-process,
no subprocess).

## Alternatives considered

- **`mark3labs/mcp-go`** — the popular community SDK; predates the official
  one. Choosing it means betting against the reference implementation for
  no feature we need.
- **Hand-rolled stdio JSON-RPC** — zero deps, but reimplements the
  initialize handshake, capability negotiation, and protocol-version drift
  by hand; brittle against the one client that matters (Claude Code), and
  enforcement code is the wrong place to be creatively minimal.

## Consequences

- First Go dependency beyond `yaml.v3`. Version pinned in `go.mod`;
  upgrades are deliberate.
- Tool handlers are typed functions; the input schema the agent sees is
  generated from the `exec` args struct — one definition, no drift.
- Protocol-level tests use the in-memory transport pair, so `go test`
  exercises the same code path Claude Code will hit over stdio.
