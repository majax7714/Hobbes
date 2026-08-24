# ADR 022: The web surface is a Go daemon serving an embedded SPA

Date: 2026-08-11
Status: accepted

## Context

M7 builds architecture §7's human surface: five tabs (Graph, Tests,
Docs, Diff, Sessions) over a "local web server on the dev box — nothing
more in v1". D1 assigns the *surface* to TypeScript + React and D3 fixes
the graph renderer (Cytoscape.js), but neither says what serves the
data, and the surface needs more than static files:

- **Docs** needs blob-level stale badges (ADR-019) and provenance links
  that open the cited `file:line` — a browser cannot read the repo.
- **Diff** needs `git diff`.
- **Sessions** needs the flight recorder (ADR-015) tailed live, and
  **escalation approve/deny in-UI** (build plan M7) — writes against the
  ADR-016 queue whose lifecycle `internal/escalation` owns.

## Decision

A new Go binary, **`hobbes-web serve --repo DIR`**, serving a JSON API
and the built SPA from one process on one port. Not a Python
`hobbes serve`: approve/deny would become a second implementation of the
ADR-016 queue's lifecycle, exactly what ADR-003 exists to prevent, and
D1 already assigns long-running daemon work to Go. It adds **no new Go
dependency** — `net/http` is enough.

- **Read endpoints are thin.** `graph.json`, `tests.json`, and
  `interfaces.json` are passed through as bytes with no server-side
  decoding: the schema (ADR-006, v3) has exactly one owner, the
  pipeline, and a server that re-declares its types is a second place to
  update. The server decodes only what it must compute over — narrative
  artifacts' `sources`, for badges.
- **Staleness has one implementation.** `internal/knowledge` already
  computes ADR-019 blob staleness in Go (M5, for `get_module_doc`); it
  is exported rather than copied.
- **Loopback only, enforced.** A non-loopback `--addr` is refused at
  startup, and requests whose `Host` is not loopback are rejected
  (DNS-rebinding guard). §7 puts remote access out of scope; because
  approve/deny mutates the queue, that scope line is enforced in code
  rather than left as a default. A tunnel in front remains the
  documented way to reach it from elsewhere, unchanged by this.
- **Mutation is confined to escalations.** `POST
  /api/escalations/{id}/{approve,deny}` are the only non-GET routes; they
  call `escalation.Resolve`, so a late verdict still loses to the
  deadline exactly as it does from the CLI. Everything else is read-only
  by construction.
- **Polling, not SSE or websockets.** The Sessions tab polls; flight
  lines are fetched with an `?after=<n>` line cursor so a tail is cheap
  and idempotent. A push transport would still need the server to poll
  the filesystem (or add a watcher dependency) for the same data.
- **Assets are embedded** (`go:embed`) from `internal/web/dist/`, a
  directory holding only a committed `.gitkeep`; the Vite build writes
  the rest and is gitignored — the sandbox's gitignored static-proxy
  precedent. One binary works against *any* target repo; a fresh clone
  that has never run `npm run build` still builds and serves a stub page
  naming the command. In development, Vite's dev server proxies `/api`
  to the daemon, so the SPA hot-reloads without a Go rebuild.
- **`/api/source` is guarded**: repo-relative paths only, symlinks and
  traversal refused, a size cap, binary sniffing, and an explicit
  `.tfstate` refusal (ADR-011's floor restated at the read surface — the
  web server must not become the one component that serves it).
- **Missing artifacts are a state, not an error.** Every read endpoint
  answers 404 with the command that would produce the data
  (`hobbes ingest`, `hobbes narrate`); the UI renders that as guidance.
  A repo with no narrative pass shows an empty Docs tab, not a broken
  surface.

## Alternatives considered

- **Python `hobbes serve`** — reuses graphdiff and the narrate package
  directly, but duplicates the escalation queue's lifecycle in a second
  language and puts a long-running daemon in the language D1 assigns to
  batch pipeline work.
- **Static file server + client-side everything** — collapses on Diff
  (needs git), provenance (needs repo reads), and Sessions (needs
  writes).
- **Serving `web/dist` from disk** — simpler, but the path is relative
  to the Hobbes checkout while `--repo` points elsewhere; resolving an
  install location is more machinery than embedding.
- **Folding the surface into `hobbes-proxy`** — the proxy is per-session
  and dies with its session (ADR-014); the surface is per-repo and
  outlives every session it monitors.

## Consequences

- One binary, one port, no auth, no new dependencies — and the "local
  only" scope is a startup check rather than a convention.
- The API is a stable seam for M8: `hobbes review` adds endpoints
  (graph diff, invariant verdicts) without changing how the surface is
  served.
- Because reads pass artifacts through untouched, a pipeline schema bump
  reaches the UI without a Go change — the TypeScript types are the only
  place the shape is restated, and they are checked at build time.
