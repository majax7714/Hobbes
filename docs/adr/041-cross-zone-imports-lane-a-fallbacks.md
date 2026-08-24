# ADR-041 — Cross-zone imports: two lane A fallbacks and a surfacing floor

**Status:** accepted (2026-08-16)

**Scope:** the C-12 paydown, from the register's own ranking — "a
monorepo's cross-zone import edge is simply absent, at exactly the
altitude the graph exists to show." Narrows and surfaces **C-12**;
does not lift it.

## Context

A tsconfig zone is a separate TypeScript program, in both lanes: one
ts-morph Project per zone (M6) and one `scip-typescript` run per zone
(ADR-032). That is what makes path aliases resolve correctly — and it is
also why an import from zone A into zone B resolved in *neither* lane
and vanished without a trace. The failure was in `extractImports`'
fallthrough: a specifier the checker could not resolve either named an
external package or was **silently dropped**.

## Decisions

**1. A relative specifier resolves against the repo's file set,
zones notwithstanding.** `../../b/src/util` is unambiguous — it names a
path, not a compiler configuration — so when the checker (whose program
stops at the zone boundary) returns nothing, the helper resolves it
manually with the same extension/index candidates `require()` handling
has always used. Deterministic, and wrong only if the filesystem is.

**2. A bare specifier matching one of the repo's own package names
resolves to that package's entry.** `import "@app/ui"` in a monorepo is
the repo's own declaration of the target: `discoverWorkspacePackages`
reads every `package.json` (pruned walk), and the specifier resolves to
the named package's `main` (or `index` / `src/index` candidates), or a
subpath under its directory. Never a guess: a name whose candidate files
do not exist resolves to nothing and falls through. Ordering is
load-bearing — checker first (a real `node_modules` resolution that
lands in-repo wins), then relative, then workspace, then external — so a
published copy of a workspace package cannot shadow the in-repo source.

**3. What still cannot resolve is surfaced, not silent (the C-12
floor).** A specifier that resolves nowhere and names no plausible
package — an alias into a zone this walk cannot read — becomes one
`imports-unresolved` record per file, specifiers named, flowing through
the existing `errors` channel into `extraction_errors` and the ingest
WARNING. C-12's remaining residue is thereby *visible* where it bites.

**4. Asset imports are not resolution failures.** `./index.css` is a
real import of a file the graph deliberately does not model. The first
run of the floor on kbet and on this repo flagged exactly these — noise
that would bury the real records (the C-26 noise-floor lesson). A
specifier with a non-code extension is excluded from the unresolved
records, by an explicit predicate with the reasoning attached.

**No helper version bump:** more import rows, same shape — the C-24
precedent.

## Consequences

- Cross-zone edges are lane A's alone (each zone's indexer still cannot
  see out), so they carry `syntactic` tier and appear in the
  lane-agreement report's informational lane-A-only list — which is the
  honest description of their evidence.
- C-12 narrows to: **path-alias imports across zones** (zone B's alias
  map is a compiler config this walk does not interpret) and anything
  behind custom resolvers. Both now surface via the floor instead of
  vanishing.
- kbet and the dogfood repo re-verified: lanes clean, no new noise.
