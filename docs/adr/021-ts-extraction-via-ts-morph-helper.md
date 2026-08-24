# ADR 021: TS/JS extraction — a ts-morph Node helper behind the pipeline

Date: 2026-08-11
Status: accepted

## Context

M6 is the TypeScript extractor: module graph, symbols/calls,
Express/Nest routes, and test inventory, on the M1 JSON contract. Both
source docs pick the tooling explicitly — architecture §3.1: "for TS,
resolve symbols through the compiler API (ts-morph) rather than
tree-sitter alone"; build plan M6: "ts-morph symbol resolution". But
ts-morph is a Node library and the pipeline is Python (D1), and
ADR-005 contains an aside ("the M3 and M6 extractors must be
tree-sitter walks") written at M1 to justify tree-sitter over stdlib
`ast`.

## Decision

**`tsextract/` is a small Node package (dependency: ts-morph) that the
Python pipeline invokes as a subprocess** — the ADR-003 pattern (Python
shells to the Go policy binary), applied to the language whose compiler
we need. The helper emits one deterministic **facts JSON** on stdout
(`helper_version`-tagged, everything sorted, no timestamps); the Python
side (`extract/tssource.py`) joins those facts into the same three
artifacts. D1 stands: the pipeline, the joins, and the artifact
contract stay Python; the helper is a leaf tool.

On the ADR-005 aside: **superseded for M6, by the source docs.** It was
a uniformity argument made before any non-Python extractor existed. M3
did land on tree-sitter (HCL is declarative — the walk is the easy
part). TS is the opposite case: parsing is the easy part and
*resolution* is the hard part — tsconfig paths, barrel re-exports,
`.mjs`/`.cjs`/`allowJs`, default-vs-named interop — exactly what the
compiler API answers correctly and a hand-rolled ADR-007-style resolver
would answer wrongly. ADR-007's governing rule carries over unchanged:
**false edges are worse than missing edges** — a call or import the
checker can't resolve to a repo file is omitted (externals become
`ext:<package>` nodes; Node builtins are dropped like Python's stdlib).

Contract points:

- **Module ids are repo-relative paths sans extension**
  (`core-frontend/core-auth/src/flow`); symbol ids are
  `<module-id>.<qualname>`. Paths are already unique, so no collision
  machinery (ADR-006's `root:` prefixing stays Python-only). Narrative
  artifacts for such ids nest under `docs/modules/` mirroring the repo
  tree; the `/`-in-id rule is: no `..` parts, no absolute paths,
  enforced by both the Python writer and the Go reader.
- **Test inventory** covers vitest, jest, and **`node:test`** (what the
  sanctioned exit repo actually uses), detected per file by framework
  import; `describe` nesting joins qualnames with ` > `.
  **tests.json schema v3**: each test carries its own `framework`
  field (a repo now mixes pytest and JS frameworks); the global
  `framework` field is gone. `languages` gains
  `typescript`/`javascript`.
- **Routes**: Express verb calls (`app.get("/x", handler)` where the
  receiver resolves to `express()`/`Router()` or is named
  `app`/`router`, and the path literal starts with `/`) and Nest
  `@Controller`/`@Get`-family decorators.
- **Env cross-layer**: `process.env.X` and `import.meta.env.X` become
  `env-read` edges onto the shared `env:X` nodes (M3's join).
- **Setup is explicit, never silent**: a repo with TS/JS files and no
  usable helper (missing node or uninstalled `tsextract/node_modules`)
  fails ingest with instructions. Skipping would make graph content
  depend on the environment (P1 violation).
  `HOBBES_TSEXTRACT_CMD` overrides the helper invocation (the
  `HOBBES_POLICY_BIN` precedent) — tests use it for canned facts.
- **tsconfig**: the repo root's `tsconfig.json` is honored when
  present; otherwise the helper supplies `allowJs` defaults. Per-package
  tsconfigs in monorepos are deferred (future_additions).

## Alternatives considered

- **tree-sitter-typescript in Python** (the ADR-005 aside) — one
  substrate, no Node dependency; rejected because TS resolution is the
  actual deliverable and the source docs already rejected it ("rather
  than tree-sitter alone").
- **Rewrite the pipeline in Node / run Python from Node** — relitigates
  D1.
- **Port the M1 join logic into the helper** (emit graph.json directly
  from Node) — splits the artifact contract across two languages; the
  facts/join split keeps every artifact byte written by one code path.
- **npm-install at ingest time automatically** — hidden network access
  inside a "deterministic, runs in seconds" pass; setup stays a
  documented one-time step.

## Consequences

- A second runtime (Node ≥20) joins the dev-box requirements — for TS
  repos only; Python-only repos never invoke the helper.
- The helper has its own `node --test` suite (zero extra dev deps);
  the Python side is tested hermetically with canned facts plus an
  integration test against the fixture that skips when Node is absent.
- Checker-grade resolution means JS/TS call edges are *more* trustworthy
  than Python's four-rule approximation — the asymmetry is fine: both
  sides obey "an edge shown is real".
- `package-lock.json` pins the helper's dependency tree; ts-morph API
  drift is caught by the helper suite, not by ingest output changing.
