# 019: The review page draws with React Flow and ELK, bundled into the page

- Status: accepted; slice 1 built (see note)
- Date: 2026-10-16
- Narrows: DEC-018 (its "no libraries, hand-written SVG"); open-work item 4

## Context
The user wants the review page (DEC-018) to look and work more like
understand-anything's graph: card nodes, nested containers, pan and zoom, a
minimap. That tool's weak link is its semantics (an LLM writes its graph);
Hobbes's extraction is the strength here, so we take only the visual side.
Survey: `research/review-rendering.md`. Its dashboard is MIT and separable,
but it is two levels around LLM fields and needs a local server, so we take
its stack and ideas, not its code. DEC-018's page used no libraries.

## Decision
The user chose React Flow with ELK (2026-10-16), over reusing
understand-anything's dashboard, Cytoscape, or keeping our own SVG:
1. **Stack:** React, `@xyflow/react` (MIT) and `elkjs` (EPL-2.0), with
   exact pins and a lockfile in a new top-level helper folder `review/`
   (like `tsextract/`). esbuild bundles it into one script.
2. **Still one file.** `cd review && npm ci && npm run build` writes
   `review/dist/` (not committed); `hobbes review` inlines the bundle and
   the data into the page. A missing bundle is an error naming that
   command. DEC-018's stamp, file name, `vscode://file` links and launch
   (`hobbes review`, `/review`) stand: no server, no network.
3. **Layout in the page:** ELK's layered layout (callers above what they
   use) runs per view when it opens. Views hold at most 12 boxes
   (`levels.MAX_BOXES`), so this is cheap and leaves room for containers
   that open in place. ELK's EPL-2.0 notice ships in the bundle.
4. **Look:** card nodes, pan and zoom, a minimap, our palette and system
   fonts (no web fonts), following the system's light or dark setting.
5. **Slices:** (1) DEC-018's page on the new stack, plus edge labels with
   counts, focus on the selected box (the rest fades) and the minimap;
   (2) folder boxes that open in place as containers, and edges leaving a
   view as portal nodes (understand-anything's `PortalNode`). Later, not
   decided: a tour along flows, a diff between two stamps, code previews.

## Consequences
- A JS build step for the page, and a JS dependency tree to keep current
  (by hand, like the adapters, DEC-004).
- The page grows by the bundle (React, React Flow and ELK, several hundred
  KB, measured when built); the data stays as DEC-018 slims it.
- Python tests still check the page's data, stamp and file; the
  view-to-graph conversion gets `node --test` tests; the drawing is still
  checked by eye (headless browser screenshots).
- `review.html` stops being the drawing: it becomes the page's shell.

### Note, 2026-10-16: slice 1 built
- `review/` (`src/graph.js` the conversion, `src/main.jsx` the page,
  `src/style.css`, `build.mjs`), pinned React 19.3.0, `@xyflow/react`
  12.12.0, elkjs 0.12.0, esbuild 0.28.2 (each at least two weeks old).
  esbuild's blocked postinstall is not needed on x64. The bundle starts
  with a notice listing every bundled package, version and license.
  `review.html` is now the shell; `hobbes.review` inlines `review.css`,
  `review.js` and the data (`AppMissing` when unbuilt, in the CLI and the
  `/review` RPC).
- **Size:** the bundle is 1.85 MB (577 KB gzipped), almost all ELK, well
  over this record's guess. The hobbes-public page (1,239 views today) is
  6.0 MB, 1.9 MB of it the bundle. Laying out at review time in Node would drop ELK from
  the page but rule out slice 2's in-place layout; not done.
- **Layout:** layered, DOWN, **splines**, `aspectRatio` 3 so unlinked boxes
  pack into rows. Compared by screenshot against orthogonal routing (with
  and without merged edges): orthogonal turned the densest view (12 boxes,
  37 edges) into a maze of parallel wires. Link counts are not ELK labels
  (they made views a third taller); the page puts them halfway along each
  curve, always in views with at most 12 edges, else on focused edges only.
- **Focus:** hovering or selecting a box fades everything not linked to
  it and shows its counts.
- Checked by headless Firefox driven over WebDriver BiDi, on hobbes-public
  at `2089e22`, light and dark: the repo, folder, module, flow and
  entry-point views; click selects, double-click opens. Not checked: keys,
  the `vscode://file` links, a real (non-headless) browser.
