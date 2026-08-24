# ADR-048 — Extraction at scale: what dagger forced

**Status:** accepted (2026-08-18)

**Scope:** the first deep-extraction pass Max directed after v2 closed
("theres not been enough extraction testing"), run against
`~/dagger` — the Dagger automation engine, ~460 MB, four graph
languages, 84 TypeScript zones, 25 Go modules, ~265,000 detected call
sites: roughly fifty times the largest repo Hobbes had measured. Three
changes shipped together because one repo forced all three, plus one
finding registered and deliberately **not** fixed. Amends architecture
§3.2 and §3.4; amends C-32; adds C-33.

## 1. The capture line breaks down by directory

Max's ask, verbatim in intent: carry the directory through, so "we can
see what we are missing more often in repos a little better." On a
3,000-file language a per-language percentage is true and useless — Go's
79.3% said nothing about the fact that `core/integration` alone held
most of the miss.

**Decision:** the ingest summary prints a per-directory capture view —
`rollup_directories()` in `tail.py`, a **pure read over the existing
per-file `resolution_coverage` rows** exactly like the language rollup
beside it. No artifact change, nothing stored twice.

- **Grain is depth 2** of the containing directory (`sdk/python`,
  `core/integration`), because top level is too coarse for exactly the
  repos that need the view and the per-file rows remain the
  full-resolution record underneath.
- **Language stays a key** inside the directory — the capture statement
  is per-language by construction, and blending two languages'
  denominators in one number would blur whose sites went unresolved.
- **Ranked by the *cannot resolve* group, not total unresolved.** The
  first draft ranked by total and `internal/buildkit` (8,573 by-design
  builtin sites) outranked `sdk/typescript` (3,059 real misses) — the
  view exists to point at what is missing, so by-design classes may not
  push a directory up the list. They print per row as `N by design`.
- **The cut is stated, never silent** (the ADR-045 rule): ten rows, then
  one line counting the directories and unresolvable sites held back.
  Directories with no cannot-resolve sites are counted, not listed.

## 2. Shape is read across the wrap

Dagger's integration tests are fluent chains, and gofmt **mandates** the
trailing dot for a wrapped chain (semicolon insertion forbids a leading
one):

```go
c.Container().
    From("alpine").
    WithExec([]string{...})
```

`From` and `WithExec` open their lines, so the line-local shape read
called them `bare`, no observation matched, and they fell to
`unclassified` — 783 of `container_test.go`'s 783 unclassified sites
were exactly this (the awk count of wrapped-chain openers matched the
tail count to within one). The class was abstaining on a shape that
**is** checkable: in Go, Rust, and TS/JS a statement cannot end with
`.`, so a previous line ending there can only be an unfinished chain.

**Decision:** when a call site's name opens its line, `_shape` reads the
previous line's ending — for the trailing-chain languages only. `.`
continues as `attr`; `::` continues as `path`.

- **Python is excluded.** Its chains wrap with the dot *leading* the
  next line (already read same-line); a trailing dot inside parentheses
  is legal but a shape this classifier abstains on rather than reads.
- **Comments cannot fake a chain:** a previous line that *is* a comment
  never continues anything, and a trailing `//` comment is cut before
  the ending is read — so prose ending in a period stays prose. The
  residue that survives: a `#`-comment suffix on a Go/TS line (not cut;
  `#` is not a comment there) is a non-case, and a string literal
  containing `//` before a real trailing dot makes the read *abstain*,
  never misfire — the failure direction is the honest one. C-32's
  text-shape boundary is restated to say the read spans the wrap.

## 3. Lane B degrades per unit, not per language

One of dagger's 84 TypeScript zones — `docs`, whose tsconfig extends
`@docusaurus/tsconfig`, not installed — made `scip-typescript` exit 1.
The per-unit error propagated to the per-language catch in
`_lane_b_facts`, which can only drop the whole lane: **one broken zone
zeroed all 84 zones' semantics**, and TS capture read 0.0% on a repo
where 83 zones were indexable. Go and Rust had the identical shape
(one module / one cargo root fails → the language falls); dagger's 25
Go modules simply all happened to succeed.

**Decision:** each per-unit merge loop (`extract_scip_typescript`,
`extract_scip_go`, `extract_scip_rust`) catches `UNIT_ERRORS` around
its unit, records a degradation naming the unit — path, stage, the
error, and that *other units are unaffected* — and continues. The
tuple is **exactly the per-language catch's** (`ScipError`,
`StagingError`, `OSError`), published as `UNIT_ERRORS` and pinned by a
test, so the inner catch can never quietly absorb a failure class the
outer one would have surfaced (P10). The per-language catch stays, for
failures before any unit runs (helper missing entirely).

This is P6 read closely: "degrade visibly" at the granularity of what
actually failed. The language-level record was visible but wrong-sized
— it converted one zone's missing devDependency into a language-wide
absence that read as "TS semantics need the whole repo installed."

## 4. The finding not fixed: cross-unit references (C-33)

With TS semantics restored, the remaining structural miss is measured
and understood but **not** fixed here. Dagger's root module calls
`dagger.io/dagger`, which `replace`s to `./sdk/go` — in-repo, two
units. Zero of those calls resolve semantically. A two-module fixture
reproduces it at one call site, and the mechanism is two layered
losses:

1. **Staging strips sibling units.** Each Go module is staged with only
   its own files, so the replace target's sources are absent and
   scip-go cannot even type the import (it emits the reference
   mis-attributed to the stdlib package bucket).
2. **Decode never joins across runs.** Indexed on the full tree,
   scip-go emits the reference with the *exact* moniker the sibling
   module's own index defines (`scip-go gomod example.com/sub 0 …
   Hello().` both sides — versions agree because both are pinned).
   But `decode()` resolves references against *this index's*
   definitions only; a cross-index reference lands in `external_refs`,
   **where the moniker is discarded**, so the Python merge could not
   join it even in principle.

The candidate fix is a contract change — keep the moniker on external
rows, join externals against the merged definitions across units, and
stage replace/workspace targets with their consumers — and it crosses a
standing decision: C-12 deliberately rejected cross-zone reconciliation
for TS. The Go case differs (the module graph is explicit and a moniker
join is exact, not heuristic), but that argument deserves its own
review, not a rider on a measurement session. Registered as **C-33**,
Max's call on the fix.

## Consequences

- The ingest summary now has three altitudes: per language, per
  directory, per file (artifact) — same denominator statement at each.
- `attr-call` grows and `unclassified` shrinks wherever fluent chains
  wrap; re-measured numbers on the five-repo fleet plus dagger are in
  the BUILDLOG entry.
- A repo with one broken zone/module/crate keeps semantics everywhere
  else, and the degradation names the one unit and its fix.
- P11 note: this session is dagger's evidence and only dagger's — §3.8
  gains no row, because no edges were hand-verified. What it extends is
  the *honesty machinery's* evidence, which is the shared path.
