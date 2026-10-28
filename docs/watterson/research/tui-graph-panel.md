# The TUI graph panel: plugin loading, data path, drawing, Bun

Survey for open-work item 4's graph panel (Next up 1), before its decision
record. Source: opencode **v2.0.29** (tag `042d083`), the version pinned in
`tui/` (DEC-013). Paths are in that tree unless absolute. Three subagent
surveys, with the claims below spot-checked against the source and the
installed binary (`tui/node_modules/@opencode/cli-linux-x64-baseline/bin/opencode`).

## 1. Loading a plugin into the compiled TUI

- **No build step.** The binary carries Babel with `babel-preset-solid`
  (`generate:"universal"`, `moduleName:"@opentui/solid"`) as a `Bun.plugin`
  `onLoad` hook. It strips TypeScript and applies the Solid JSX transform
  to any `.[cm]?[jt]sx?` file **not** under a `node_modules/` path (the
  filter regex is in the binary). A local `tui.tsx` runs as written.
- **Shared modules come from the host** and must not be bundled:
  `solid-js`(`/store`), `@opentui/solid`(`/components`, jsx runtimes),
  `@opentui/core`, `effect`, `@opencode/plugin/*`. Plugin-local copies of
  `effect` / `@opencode/plugin` throw (`plugin/src/runtime.ts:28-34`;
  `runtime-modules.ts:7`). Nothing else is provided.
- **Entry:** a *directory* holding `tui.*`, default export
  `{id, setup(ctx)}` (`Plugin.define` is the identity,
  `plugin/src/tui/plugin.ts:12-14`). A config entry naming a file is
  skipped silently (`tui/src/plugin/context.tsx:334-341`). Ids starting
  with `opencode.` are reserved (`:321-330`).
- **Where the TUI finds plugins** (`tui/src/plugin/context.tsx:290-309`):
  the `plugins` list in `cli.json` (`$OPENCODE_CONFIG_DIR` or
  `$XDG_CONFIG_HOME/opencode/`), the overlay `OPENCODE_CLI_CONFIG_CONTENT`
  (replaces the file's `plugins`; dropped silently when invalid,
  `cli/src/config/config.ts:30-34`, `:144-149`), discovered directories
  (`<config>/plugins/*`, `.opencode/plugins/*`), and plugins our server
  lists in `GET /api/plugin` with `features.tui` (`context.tsx:96-103`).
  Absolute local paths never touch npm; npm names install on first use.
- **Hot reload** of local plugins (100 ms debounce, `context.tsx:252-269`).
- Docs: `services/www/src/docs/content/build/plugins/cli.mdx` (session
  panels at `:509-585`, packaging `:595-635`). No in-tree plugin uses
  `session.panel`; the diff viewer is a built-in *route* importing TUI
  internals, so it is a style model only. External-style example:
  `tui/test/fixture/plugin/setup-keymap/tui.tsx`.

## 2. The panel

- `ui.slot({append: "session.panel", render})`; render only when
  `panel.name` is ours (`plugin/src/tui/context.ts:165-199`; docs above).
  `ui.panel.open(name)` works only on a session route (`tui/src/plugin/api.tsx:231-237`).
- Input: `{name, sessionID, width, presentation, focused, focus, close,
  toggleFullscreen}`. The panel replaces the right pane (sidebar), default
  half width, resizable; under 80 columns it is fullscreen
  (`tui/src/context/panel.tsx:14-15`, `component/session-frame.tsx:112-117`).
- Keys: a `keymap.layer` made inside the panel is active only while it
  has focus (`tui/src/context/keymap.tsx:204-213`). The host binds no Esc
  to close; we bind our own. A palette entry / slash command is a
  `mode:"global"` layer command with `palette:true` (`context.ts:407-433`).
- Session and directory: `panel.sessionID`, then
  `ctx.data.session.get(id)?.location.directory`.
- Lists: no exported list component; build rows from `box` / `text` /
  `scrollbox` as `tui/src/feature-plugins/system/diff-viewer-file-tree.tsx`
  does. `ui.dialog.select` exists but is modal.

## 3. Getting data from our server

- `ctx.client` is the TUI's typed client with our auth; it has no raw
  request method and does not expose the URL or password
  (`client/src/promise/generated/client.ts:274-311`).
- **RPC is the open door:** `ctx.client.rpc.call({rpcID, method, input,
  location})` sends `POST /api/rpc/{rpcID}/{method}?location[directory]=…`
  with `{"input": …}` and expects `200 {"output": …}`
  (`generated/client.ts:1697-1710`, `protocol/src/groups/rpc.ts:7-20`).
  Errors: 4xx/500 with `{"_tag":"RpcError","type","message"}`.
- **Push:** any `rpc.<id>.<name>` event on `/api/event`, envelope
  `{id:"evt_…", created, type, location:{directory}, data:{…}}`
  (`protocol/src/groups/event.ts:14-21`). Subscribe with
  `ctx.data.on("rpc.hobbes.…", h)`, which rides the TUI's reconnecting
  stream; re-fetch on `server.connected` too.

## 4. Drawing: merman vs a list

- merman (`packages/merman`, MIT, `"private": true`, not on npm) renders
  Mermaid flowcharts (TD/LR, subgraphs, edge labels; own layout and
  orthogonal routing) to opentui `StyledText`. It is **display-only** and
  **drops styling** (`classDef`, `style`, `:::cls`;
  `flowchart/parser.ts:300`), so a selected box cannot be marked.
- It is not importable by plugins: it exists only inside the binary, and
  the plugin API exposes no markdown renderer that would reach it
  (`plugin/src/tui/context.ts:554-556`). Using it means vendoring its
  source (routing alone is 1,429 lines) and bundling it.
- Its tests tolerate up to 3 crossings and wide overflow per diagram
  (`test/layout-audit.test.ts:37-48`): fine for small views, a risk in a
  half-width panel.

## 5. Bun

- Not needed to **run** a plugin (section 1). The binary is compiled with
  **Bun v1.4.2** (string in the binary), the version opencode pins
  (`package.json` `packageManager`). Bun ships on npm (`bun@1.4.2`,
  2026-09-05, with per-platform `@oven/bun-*` packages), so it can be
  pinned like `adapters/` and `tui/` if plugin tests need it.
- opencode tests plugins with `bun test` and `testRender` from
  `@opentui/solid` (`tui/test/plugin-select.test.tsx`), on `@opentui/*`
  0.5.17 and a patched `solid-js` 1.9.15. Running those outside the host
  would not use the binary's patched modules (unverified how much that
  matters).
