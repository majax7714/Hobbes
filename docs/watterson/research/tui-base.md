# A TUI with a graph tab: what exists, and which base to copy (item 4)

Survey, 2026-10-16, read-only. Sources: hobbes-public `2089e22`, paseo
`a1da1b8f2`, opencode (`anomalyco/opencode`, which `sst/opencode` now
resolves to) `dev` at `180fd9d`, latest release v1.19.3.

> **Correction (DEC-013):** opencode has two lines. Everything below about
> `packages/merman`, the `session.panel` slot, `@opencode/client` and the
> `/api/*` operations is **v2** (`dev`; npm `@opencode/cli`, bin
> `opencode2`), not v1.19.3 (GitHub "Latest", npm `opencode-ai`), which has
> neither merman nor the panel slot. v1.19.3 is not an ancestor of `dev`.

## What hobbes-public has for graph views

- **`hobbes render`** (`pipeline/src/hobbes/cli.py:737-748`,
  `pipeline/src/hobbes/render.py`, 90 lines, stdlib only): a deterministic,
  module-level Mermaid `flowchart LR` from `graph.json`, read through
  `artifacts.load_graph` (`artifacts.py:101`). Conventions: ADR-008.
  Not in this repo yet.
- **Interactive graph** (`web/src/tabs/GraphTab.tsx`, 579 lines; model
  `web/src/lib/graphModel.ts`): Vite + React 18 + cytoscape ^3.30, one of
  six tabs. Served with the API by the Go binary `hobbes-web serve --repo DIR`
  on loopback `127.0.0.1:7777` (`go/cmd/hobbes-web/main.go:84-86`, ADR-022);
  non-loopback `Host` headers are rejected (`go/internal/web/server.go:133-165`).
  Conventions: ADR-023 (module level, externals hidden, focus depth 1-3,
  `cose`/`breadthfirst`, one inspector). Real repos run 100-200 modules and
  350-600 module edges.
- The graph tab needs `tests.json` too, and optionally `/api/docs/module/{id}`
  and `/api/source` (provenance peek). The server re-reads
  `<repo>/.hobbes/derived/` per request (`server.go:126`), the layout of our
  session views (DEC-009); serving a view dir probably works except the
  source peek (unverified).
- Architecture §10 parked "Hobbes-as-an-application". The user set that
  aside for this environment (DEC-011).

## Bases

| | opencode | paseo |
|---|---|---|
| UI | `packages/tui` (about 108k lines, 45k of them tests); also a SolidJS web app and an Electron desktop app | Expo / React Native app and an Electron desktop app; **no TUI** (`packages/cli` is commands only) |
| TUI tech | OpenTUI (Zig core + SolidJS; `packages/tui/package.json:61-63`), on Bun; replaced Go/Bubble Tea in v1.0.0 | — |
| License | MIT, "Copyright (c) 2025 opencode" | Apache-2.0; no NOTICE file; rebrand needed |
| Backend | HTTP + SSE via generated `@opencode/client` (`packages/tui/src/context/client.tsx`); about 142 operations, events at `GET /api/event`, permission replies per request | WebSocket + Zod protocol (`packages/protocol/src/messages.ts`); the daemon is already an ACP client and takes custom `extends: "acp"` providers |
| Graph slot | `session.panel` slot (`component/panel-host.tsx:37`), used by the diff viewer (`feature-plugins/system/diff-viewer.tsx:1367`); session tabs and a sidebar slot | Workspace tab kinds (`app/src/workspace-tabs/model.ts:35-49`) or plugin `addWorkspacePanel` (`plugin/src/client/contracts.ts:139`) |
| Graph rendering | `packages/merman` renders Mermaid flowcharts in the terminal; fits `hobbes render` output; scale at about 600 edges unverified | Cytoscape in a DOM view (unverified), or open `hobbes-web` in its Electron browser pane |
| Churn | Very high: about 1,365 commits in 30 days, 2-3 releases a week | Moderate to high |

## Recommendation the user took (DEC-011)

opencode's TUI as the base, with a Graph panel that renders `hobbes render`
output through merman, and an action that opens the interactive view
(`hobbes-web`) in a browser. The main cost is rewiring opencode's client
(HTTP + SSE to its own server) to our Python layer, against a fast-moving
upstream.
