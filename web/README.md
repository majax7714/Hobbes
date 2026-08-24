# web/ — human surface

The five-tab UI from architecture §7 — **Graph · Tests · Docs · Diff ·
Sessions** — built with Vite + React + TypeScript, the interactive graph
via **Cytoscape.js** (locked decision D3; Mermaid remains the
markdown/export renderer, ADR-008).

It is the client half of M7. The server half is `hobbes-web`
(`go/cmd/hobbes-web`, ADR-022), which serves this app *and* the JSON API
it reads. Graph conventions are ADR-023.

## Build

```sh
npm install
npm run build     # typechecks, then bundles into go/internal/web/dist/
npm test          # vitest over the pure model/index/patch logic
```

`npm run build` writes into the Go binary's `go:embed` directory, so the
app ships inside `hobbes-web` — one binary, usable against any repo.
**Rebuild the Go binary after building the app**, or it will serve the
previous bundle:

```sh
cd ../go && go build -o bin/hobbes-web ./cmd/hobbes-web
./bin/hobbes-web serve --repo /path/to/repo    # http://127.0.0.1:7777
```

## Develop

```sh
# terminal 1 — the API
cd ../go && ./bin/hobbes-web serve --repo /path/to/repo
# terminal 2 — the app, with HMR, proxying /api to the above
npm run dev
```

No Go rebuild is needed while iterating on the UI.

## Layout

- `src/lib/` — the pure logic, and the only part with tests: the graph
  model (filters, focus neighborhood, Cytoscape elements), the
  behavioral index joins (§4.2), and unified-patch parsing.
- `src/tabs/` — one component per tab.
- `src/api.ts`, `src/types.ts` — the client and the schema the surface
  restates; `npm run build` typechecks it, so a pipeline schema bump
  that reaches the UI fails the build rather than the page.
- `src/components.tsx` — stale badges, provenance links, the source peek
  those links open, guided empty states.
