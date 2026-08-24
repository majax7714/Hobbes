# ADR 032: The TypeScript lane — `node_modules` is linked, never copied

Date: 2026-08-15
Status: accepted

Milestone V2.M3, discharging M2's asterisk. Refines ADR-027's staging
contract (clause 2) and replaces its Decision 4 degradation test. Registers
constraints **C-22** and **C-23**.

## Context

ADR-027 established that lane B indexes a **staging tree Hobbes owns**
rather than the target repo, and measured that this costs nothing for
Python: `venvPath`/`venv` in the generated `pyrightconfig.json` point at
the real environment by absolute path, so third-party resolution survives
the copy (217 external symbols staged vs 218 in place).

TypeScript has no such knob. Module resolution walks *up* from the
importing file looking for `node_modules`, and a stage under
`~/.hobbes/cache` has none above it. kbet's frontend `node_modules` is
**222 MB**, so copying it into every stage is not a candidate.

So the question is whether clause 1 ("Hobbes never writes to the target
repo") can be honoured for TypeScript without losing the semantics that
make lane B worth running. Measured on kbet's `betchat/frontend` zone —
89 TS/TSX/JS files, 23 declared dependencies, `node_modules` installed for
this measurement — with `scip/spike-ts.mjs`:

| variant | ms | defs | internal refs | external refs | packages |
|---|---|---|---|---|---|
| `inplace` | 9599 | 949 | **4867** | **11839** | **23** |
| `staged-naive` (control) | 1807 | 949 | 3925 | 3191 | 3 |
| `staged-paths` | 8539 | 949 | 4548 | 10782 | 19 |
| `staged-symlink` | 10323 | 949 | **4867** | **11839** | **23** |

`staged-naive` is the deliberate control — a staged copy with the zone's
tsconfig verbatim and no `node_modules` reachable. It had to look bad, or
the metric could not tell a working config from a plausible one. It looks
bad in exactly ADR-027 Decision 4's signature: three packages, of which the
top is `npm:typescript` at **2,643 references** — the same number Decision 4
recorded, TypeScript's own bundled lib standing in for the dependencies
that were not there.

`staged-paths` — the zone's own tsconfig plus a `*` fallback into the real
repo's absolute `node_modules`, the nearest analogue of the `venvPath`
trick — recovers most of it and not all: **93.6% of internal references**
and 19 of 23 packages. A 6.4% semantic loss is not a rounding error when
semantic edges are the entire point of the lane.

`staged-symlink` reproduces the in-place numbers **exactly**, on every
column.

## Decision

### `node_modules` is symlinked into the stage; sources are still copied

ADR-027 clause 2 said "staging copies; it never hardlinks", against the
verified hazard that `chmod` through a hardlink changes the original file's
mode — a staged link is a live handle into the user's tree. That reasoning
is about **authored source**, and it stands unchanged for it.

Clause 2 is refined to distinguish two things it conflated:

> **Authored source is copied, always.** A regenerable dependency tree
> (`node_modules`, and any future equivalent) may be **symlinked**, because
> it is not authored by the user, is gitignored by universal convention, is
> reproducible from a lockfile, and is only ever read.

Two properties were verified rather than assumed, because both fail
silently and one of them fails destructively:

1. **The indexer writes nothing through the link.** A full index over the
   symlinked stage modified **0 files** under the real `node_modules`
   (`find -newer` against a marker across the whole run).
2. **Removing a stage does not remove the link's target.**
   `staging.remove_stage` ends in `shutil.rmtree`, which unlinks a
   symlinked directory rather than recursing into it — verified directly
   against a throwaway tree, target intact. This is the hazard that would
   have deleted a user's 222 MB dependency tree, and it is guarded today
   only by a stdlib implementation detail, so it gets an explicit
   regression test in `test_staging.py` rather than a comment.

The alternatives were rejected on their measurements: `staged-paths` loses
6.4% of the semantics the lane exists to produce, and `inplace` — which
also writes nothing, and which I verified leaves `git status` clean —
surrenders ADR-027 clause 5, because the indexer would pick its own file
set from `tsconfig.include` instead of lane A's discovered set. Clause 5
exists precisely to stop the two lanes seeing different files and
manufacturing false disagreements in the lane-agreement report this same
milestone ships. Trading it away to fix TypeScript would corrupt the check
that is supposed to catch this class of problem.

### Decision 4's degradation test is replaced by a coverage ratio

The control exposed a worse bug than the one it was built to demonstrate.
`staged-naive` resolved **1 of 23** declared dependencies and reported no
degradation at all.

ADR-027's test fires only when *every* declared dependency is missing:

```js
if (missing.length === declared.length) { /* degraded */ }
```

The one dependency that resolved was `typescript` — which the indexer
bundles and therefore *always* resolves. So for TypeScript the check can
never fire, under any circumstances. It is structurally dead, not merely
strict. This is the second time this check has been found inert: at M2 it
was never being passed the declared dependencies at all (found via
private-repo-A), and fixing that revealed nothing because the threshold was
unreachable anyway.

Replaced, following ADR-029's denominator pattern — **counts, always
reported; the threshold is secondary**:

- the facts carry `dependency_coverage: {declared, resolved, missing[]}`
  on every run, degraded or not;
- degradation fires below a ratio rather than at total wipeout;
- the indexer's own bundled package is excluded from `resolved`, since
  its presence says nothing about the repo's environment.

A boolean that can only be true in an impossible case is worse than no
check, because it reads as coverage.

## Consequences

- kbet indexes at full fidelity, so V2.M3's exit bar (20 hand-verified
  semantic TS edges, ≥95%) is measured against a fair index rather than a
  degraded one.
- ADR-027's clause 2 is refined, not withdrawn; clauses 1, 3, 4, 5, 6 and 7
  are untouched and all still hold for TypeScript.
- `staging.build_stage` grows a `links` parameter. `remove_stage`'s
  existing guard is unchanged and now load-bearing for a much more
  expensive mistake, hence the new test.
- The no-write property is **measured, not structurally enforced**, which
  is the honest statement and is registered as **C-22**.
- **C-23** registers what a TS repo without an installed dependency tree
  loses, now that the new coverage number makes it visible.
- `scip/spike-ts.mjs` is kept on ADR-027's precedent for
  `analyze.mjs`/`compare.mjs`: it is the reproducible evidence for the
  table above.
