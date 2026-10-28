# 018: Review happens on a stamped HTML page, apart from the TUI

- Status: accepted; first slice built (see note)
- Date: 2026-10-16
- Narrows: open-work items 3 (the environment is the workspace, review a
  separate surface) and 4 (graph views); DEC-014 (the level document),
  DEC-015 (the TUI panel stays)

## Context
The user works in the terminal and reviews elsewhere (VS Code today). The
TUI's graph panel is a list in a sidebar: a terminal cannot comfortably
draw a graph, and the panel opens only inside a session. hobbes-public's
web UI is not reused: it displays poorly (the user, 2026-10-16). The user
wants the review surface local and low on dependencies, stamped with the
commit it shows, explorable on its own, and optional: in a terminal only,
Hobbes's knowledge tools work as before.

## Decision
The user chose the HTML route (2026-10-16):
1. **A self-contained HTML file** per repo and commit, opened in the
   system browser. Everything inline (data, CSS, script; no libraries,
   hand-written SVG), so there is no server, no network and no install,
   and the file opens without Hobbes.
2. **Content:** the level document (DEC-014), drawn: a view's boxes in
   dependency layers with arrows, cycles marked; flows as numbered steps.
   Clicking a box opens its view; breadcrumbs and the browser's back go
   up. A side panel shows the selected box's links, sample `path:line`s
   and guarding tests.
3. **Stamped:** the repo, commit, dirty flag and generation time in the
   page and in its name: `~/.watterson/review/<repo>@<sha7>[-dirty].html`
   (`$HOBBES_REVIEW_DIR` overrides the folder). Not in the repo.
4. **Into the code:** files and `path:line` samples are
   `vscode://file/<absolute path>:<line>` links.
5. **Launched** by `hobbes review` (`watterson review`) and by `/review` in
   the TUI. The TUI panel stays as the terminal-only view.

## Consequences
- A second renderer of the level document (with the panel), in JavaScript
  that only a browser runs: the Python tests check the page's data and
  stamp; the drawing is checked by eye (headless Firefox screenshots).
- The page embeds the document without member lists, which are what make
  it large.
- Doors this opens, not built: comparing two stamps (how a change moved
  the architecture), a live page following the Hobbes server, code
  previews.

### Note, 2026-10-16: first slice built
- `hobbes.review` (`write`, `page_data`, `render`) and the template
  `hobbes/review.html`; `hobbes review [--repo] [--no-open]` and RPC
  `hobbes.review` with `/review` in the TUI (while Hobbes is on; the
  server opens the browser through Python's `webbrowser`).
- The level document gained what the links need (schema 4): `path` on
  module and symbol boxes, `def_line` on flow steps.
- Drawing: layers by box level, ordered by two barycentre sweeps; a layer
  wider than the window wraps onto more lines and re-flows on resize;
  each edge gets its own port along a box side; arrow width grows with the
  link count; cycles dashed red. Flows and entry points are numbered
  cards with "called at line N" and "definition" links. A key in the side
  panel.
- On hobbes-public at `2089e22`: a 3.6 MB page for 1,122 views. Checked by
  headless Firefox screenshots (repo, folder, module and flow views).
  Not checked: clicking, double-clicking and keys in a real browser, the
  dark theme, and VS Code opening a `vscode://file` link.
