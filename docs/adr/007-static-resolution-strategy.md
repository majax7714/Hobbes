# ADR 007: Static resolution strategy — imports, calls, reach, routes

Date: 2026-08-10
Status: accepted

## Context

Architecture §3.1 accepts that Python call graphs are approximate under
dynamic dispatch and promises reliable module-level edges. The exact line
between "resolve it" and "leave it out" needs drawing.

## Decision

**Import resolution.** An import resolves to the longest repo-module prefix
of its dotted target (`from hobbes.extract import graph` tries
`hobbes.extract.graph`, then `hobbes.extract`). Relative imports resolve
against the importing module's package. Resolved targets produce `imports`
module edges. Unresolvable top-level imports become `ext:<pkg>` external
nodes **unless** the top-level name is in `sys.stdlib_module_names` —
stdlib imports are dropped as noise; third-party dependencies are signal.

**Call edges (symbol layer, admittedly approximate).** A call site produces
a `calls` edge only when its callee resolves by one of four static rules:

1. bare name defined in the same module (`helper()`),
2. bare name imported from a repo module (`from x import helper`),
3. attribute on an imported repo module (`x.helper()` after `import x`),
4. `self.method()` / `cls.method()` to a method of the enclosing class.

Everything else — instance attributes, dynamic dispatch, higher-order calls,
re-exports that don't resolve to a real symbol — is silently omitted. False
edges are worse than missing edges: the graph's promise is that an edge it
shows is real; module-level completeness comes from `imports` edges, which
don't depend on call resolution.

**Test reach.** A test's `reaches` list is the transitive closure over
`calls` edges starting from the test symbol, restricted to repo symbols,
minus test symbols themselves. `reaches_modules` is the projection onto
modules. Pytest fixtures are dynamic injection and out of static scope for
M1 — a known, documented gap, not an accident.

**Route detection.** Only decorator sites are considered (never bare
calls, so `requests.get(...)` can't false-positive):

- `@<obj>.<method>("/path", …)` where `<method>` is an HTTP verb →
  FastAPI-style route (also matches Flask 2 shortcuts).
- `@<obj>.route("/path", methods=[…])` → Flask-style; `methods` defaults to
  GET.

The `framework` field comes from what the defining module imports
(`fastapi`/`flask`), else `"unknown"`. Routes whose path argument is not a
plain string literal (f-strings, variables) are skipped — dynamic paths
can't be pinned to evidence.

## Alternatives considered

- **Type-hint-driven call resolution** — §3.1 explicitly flags hints as a
  sharpener; deferred until the approximate graph proves insufficient, since
  it roughly doubles resolver complexity.
- **Emitting unresolved calls with a `confidence` field** — pushes the
  precision problem onto every consumer; omission keeps the contract crisp.
- **Import-time side-effect edges (module-body calls)** — module-body call
  sites are attributed to a synthetic `<module>` scope in the walk and do
  produce edges from the module's body; class-body magic beyond that is out.

## Consequences

- Module-level edges (the M1 exit bar) depend only on import resolution,
  which is near-exact statically.
- The symbol call graph under-approximates; consumers must treat absence of
  an edge as "not statically visible", never "does not happen".
- Fixture-heavy pytest suites will show thin `reaches` lists until fixture
  resolution is added (candidate for M5-era improvement if the test map
  proves too sparse).
