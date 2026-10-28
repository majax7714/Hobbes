# 015: The graph panel is a local opencode TUI plugin that lists views over RPC

- Status: accepted; first slice built (see note)
- Date: 2026-10-16
- Narrows: open-work item 4 (the TUI's graph view; DEC-011, DEC-013,
  DEC-014 decision 6)
- Research: `docs/research/tui-graph-panel.md`

## Context
DEC-011 wants a tab in the TUI that switches to a graph view of the repo;
DEC-014 made that view tiered: "show view X, open box Y". The TUI is
opencode v2, pinned and unmodified (DEC-013), and its `session.panel`
slot takes third-party plugins. The survey found that the compiled TUI
compiles a local plugin's TypeScript and JSX itself, that a plugin can
reach our server only through opencode's RPC call, and that merman (the
TUI's Mermaid renderer) is neither importable by plugins nor able to mark
a selected box.

## Decision
The user agreed to each recommendation (2026-10-16):
1. **Where it lives:** `tui/plugins/graph/`, one `tui.tsx` beside the TUI
   it is written for, outside any `node_modules/` path (the TUI does not
   compile JSX there). `hobbes tui` loads it by absolute path through
   `OPENCODE_CLI_CONFIG_CONTENT`, so nothing is installed from npm and the
   user's opencode config is untouched. The plugin stays thin: rendering
   and keys; the shaping of views is Python.
2. **Data:** opencode's RPC call. Our server answers
   `POST /api/rpc/hobbes/view` with one view of `hobbes levels`, shaped
   for display, and pushes `rpc.hobbes.changed` on the event stream when
   the repo's graph changes; the plugin re-fetches then and on reconnect.
3. **Drawing:** a keyboard list of the view's boxes, each with what it
   holds and its links; Enter opens a box's view, Backspace goes up. No
   merman for now; a read-only diagram toggle would be its own decision
   (it means vendoring merman, MIT).
4. **Bun:** not installed. The server side is tested in Python, the panel
   in the real TUI (tmux). If the plugin grows logic worth unit tests,
   `bun@1.4.2` (the Bun compiled into the TUI) is pinned from npm the way
   `adapters/` and `tui/` pin theirs.

## Consequences
- The repo gains its first TypeScript file, run only by the pinned TUI.
  It has no type check here (no `@opencode/plugin` types installed); a
  TUI bump can break it silently, so a bump needs a live look at the panel.
- The panel opens only inside a session, and takes the sidebar's pane
  (fullscreen under 80 columns). The TUI gives it no Esc; the plugin binds
  its own keys.
- `OPENCODE_CLI_CONFIG_CONTENT` replaces any `plugins` list in the TUI's
  own `cli.json` and is dropped silently if invalid, so a test checks the
  exact value.

### Note, 2026-10-16: first slice built
- `tui/plugins/graph/tui.tsx`: a `session.panel` contribution opened by
  the palette entry "Graph view" or `/graph`. Keys inside the panel: ↑↓
  (or j/k) move, Enter (→, l) opens a box's view, Backspace (←, h) goes up
  with the box you came from selected, `r` refreshes, `f` toggles
  fullscreen, Esc or `q` closes.
- Server: `hobbes.serve.graph.GraphViews` builds the level document from
  `.hobbes/derived/`, again when `graph.json` changes, and shapes a view
  into rows (label, counts, the view it opens, its links in and out within
  the view, cycles, stubs). `POST /api/rpc/hobbes/view` with `{"input":
  {"id": …}}` answers `{"output": view}` or `{"output": {"error": …}}`;
  the server checks `graph.json` every 2 s while a TUI listens and pushes
  `rpc.hobbes.changed`.
- Checked in the real pinned TUI (tmux) on an ingested clone of this repo,
  with the fake agent standing in for claude (no subscription use): the
  plugin loaded with no errors in the TUI's log, `/graph` opened the panel
  beside the transcript, the keys drilled from the repo view through
  `pipeline` to `pipeline/src/hobbes` and back, touching `graph.json` made
  the panel fetch again, and after Esc the prompt got the keys again.
- Not built: a diagram, a stale-graph tag (the panel shows the graph's
  commit and dirty flag only), and a re-extract between turns (that is
  `hobbes tui`'s parity with `hobbes chat`).
