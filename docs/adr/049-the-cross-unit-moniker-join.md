# ADR-049 — The cross-unit moniker join

**Status:** accepted (2026-08-18)

**Scope:** applies C-33's candidate fix, at Max's direction ("apply the
candidate fix and looks to retest"). Helper facts contract v2 → v3
(external rows keep their moniker), a cross-unit join in the per-language
merge, and sibling staging for Go replace targets. Lifts C-33 (entry
moves to the register's Lifted part with residual edge cases); amends
architecture §3.2. Companion: `docs/extraction-evidence.md`, the
standing per-repo test record this session also introduces.

## Context

C-33 (ADR-048): a language's indexing units — Go modules, cargo roots,
TS zones — are indexed separately and merged, so an in-repo reference
*across* units resolved in neither index. On dagger, root-module calls
into the `replace`d `./sdk/go` produced zero semantic edges: the
dominant miss on exactly the monorepo shape where cross-unit edges are
the architecture. Two mechanisms, both measured on a two-module
fixture: per-unit staging strips the sibling's sources (the loader
cannot type the import at all), and `decode()` binned cross-index
references into `external_refs` where the moniker was discarded.

## Decision

Three parts, one per mechanism plus the data they need.

1. **External rows keep their moniker** (`scip/index.mjs`,
   HELPER_VERSION 3, both sides bumped in this commit). "External"
   means external to *that index*; whether it is external to the
   *repo* is only decidable after the units merge, so the row carries
   the evidence forward instead of pre-deciding.

2. **`join_cross_unit(merged)`** runs once per language after its
   units merge (Go, Rust, TS; Python indexes as a single unit at the
   stage root and has nothing to join). It resolves external rows
   against the merged definitions by **exact moniker equality** and
   promotes matches to ordinary references — file, line, col, name,
   def_file, def_line — which then flow through the evidence IR and
   range join like any other resolution. A moniker defined by more
   than one unit in different files **abstains**, and the abstention
   is reported as a `scip-merge` degradation: C-28's rule
   (unattributed rather than guessed), applied across units.

   This is deliberately not the cross-zone *reconciliation* C-12
   rejected for TS. Nothing here interprets another unit's compiler
   configuration, alias maps, or resolution rules: a moniker either
   is byte-identical on both sides or the reference stays external.
   Where TS zone monikers genuinely match (a workspace package
   consumed at its own name and version), the join fires for TS too —
   that is evidence, not inference. C-12's subject — imports that
   need another zone's config to resolve at all — is untouched.

3. **Go replace targets are staged beside their consumer**
   (`go_replace_targets` + `_index_go_module`). Only the consumer's
   own `go.mod` is read — Go's rule exactly: replace directives apply
   in the main module only — and only path replacements (`./`, `../`)
   that resolve **inside the repo**; a replace escaping the repo names
   code the staging contract will not copy. The sibling's files come
   from the same discovery grouping that staged its own unit, plus its
   go.mod/go.sum. Without this, scip-go emits the reference
   mis-attributed to the stdlib package bucket and there is no moniker
   to join.

## Verified

- The two-module fixture that reproduced C-33 at one call site flips
  **0% → 100% capture**, the edge `semantic`/`calls` into the sibling
  module — both halves working: staging lets scip-go emit the true
  moniker, the join connects it.
- Re-ingest of dagger and the regression fleet: numbers in
  `docs/extraction-evidence.md` (the standing record) and the BUILDLOG
  entry.

## Residual edge cases (the lifted C-33's boundary)

- **Ambiguity abstains.** A moniker two units both define (dagger's
  generated `internal/dagger` packages are the live example) joins
  nothing and says so.
- **Rust:** cargo members already collapse to their workspace root
  (one unit), so most in-repo cross-crate references never were
  cross-unit; separate workspaces linked by path dependencies are not
  staged together — no verified case exists, and wiring it on zero
  evidence would repeat the mistake ADR-046 declined (P11).
- **TS:** only byte-identical monikers join; alias-mediated and
  config-mediated cross-zone imports remain C-12's subject, lane A's
  syntactic arms their only edges.
- **Version skew:** the join is exact, so if an indexer ever stamps a
  replaced module's references with a *different* version than the
  sibling's own pinned index (both are pinned to `0` today — ADR-027's
  Decision 1 is what makes the monikers meet), the join goes quiet
  rather than wrong. The lane-agreement check is the watchdog that
  would show it.
