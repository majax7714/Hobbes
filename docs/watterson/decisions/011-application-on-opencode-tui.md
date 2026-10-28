# 011: The environment is an application; its TUI starts from opencode's

- Status: accepted; not started (item 3 first)
- Date: 2026-10-16
- Narrows: open-work item 4 (graph abstraction for devs)
- Research: `docs/research/tui-base.md`

## Context
The environment replaces the web UI (open-work 3). The user wants it to look
like a typical agentic environment (paseo, opencode, Claude Code desktop,
Codex desktop): a TUI with a tab that switches to a graph view of the repo,
copied from an existing one rather than built.

hobbes-public's architecture (§10) parks "Hobbes-as-an-application". The
user parked it while working through extraction; it does not bind this
environment (the user, 2026-10-16).

Paseo has no TUI (Expo and Electron apps). opencode's TUI (`packages/tui`,
OpenTUI, MIT) has a session panel slot and a terminal Mermaid renderer
(`packages/merman`).

## Decision
1. The environment is an application, not only a CLI.
2. Its TUI starts from opencode's `packages/tui` (MIT), with a Graph view
   added. The graph's first form is the module-level Mermaid of
   hobbes-public's `hobbes render`, drawn in the terminal; the interactive
   view (`hobbes-web`) is what "open in browser" reaches.

## Consequences
Open when item 4 starts, each needing its own record:
- How the TUI talks to our Python layer (it speaks HTTP + SSE to
  opencode's server today).
- Vendored snapshot or tracking fork, given opencode's churn (about 1,365
  commits in 30 days); provenance under MIT.
- Whether merman holds a 200-module graph, and what the graph tab shows of
  a live session's snapshot graph (DEC-009).
- Bringing over `render.py` (and its conventions, ADR-008) from
  hobbes-public.
