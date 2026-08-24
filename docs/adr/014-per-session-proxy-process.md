# ADR 014: One proxy process per session, logs box-side

Date: 2026-08-10
Status: accepted

## Context

The build plan calls M4's deliverable "the daemon", but doesn't say whether
that means one long-running supervisor multiplexing every session or one
process per session. Claude Code connects to MCP servers most simply by
spawning them over stdio. The flight recorder needs a home that outlives
the session's worktree.

## Decision

`hobbes-proxy serve` is a **per-session stdio MCP server**: the session
wrapper (chunk 3) lists it in the sandboxed Claude Code's MCP config, one
proxy per session, dying with it. Identity comes in by flag: `--repo`
(required), `--role` (required — a default would silently mislabel the
audit trail), `--session` (auto-generated `S-<UTC timestamp>-<4 hex>` when
omitted).

Flight-recorder logs live **box-side**, not in the repo:
`~/.hobbes/sessions/<session>/flight.jsonl` (`--log-dir` overrides, for
tests). Worktrees are per-session and disposable by design (§6); an audit
trail inside one would be destroyed by the teardown it should survive.
Box-side also matches ADR-012: Hobbes session data is personal-environment
material and must never be committable.

## Alternatives considered

- **Central daemon (HTTP/SSE, session multiplexing)** — needed only for
  live multi-session supervision, which is M7's Sessions tab; that tab can
  read the per-session recorder files directly. The chunk-2 escalation
  queue works file-based over `~/.hobbes/sessions/` without a daemon. A
  supervisor can be added later without changing the proxy's contract.
- **Logs in `repo/.hobbes/derived/sessions/`** — dies with the worktree,
  and in target repos would sit one gitignore edit away from being
  committed history.

## Consequences

- No daemon lifecycle management in v1: no socket, no PID file, no
  systemd unit. Claude Code's process tree is the supervisor.
- Parallel sessions get parallel proxies and disjoint log files — no
  cross-session locking anywhere.
- `~/.hobbes/sessions/` becomes the audit-trail root the M7 Sessions tab
  and the chunk-2 escalation CLI both read.
