# ADR-050 — Node dependencies: per-file links, and lockfile-pinned provisioning

**Status:** accepted (2026-08-18)

**Scope:** Max's direction on the dagger retest: TS/JS is the weakest
lane across the fleet — "look for any workaround from node that is not
invasive to the repos. if none then add the lever." A non-invasive
workaround exists, and this ADR is it: two changes to how a TypeScript
zone's stage gets its dependencies, neither of which writes a byte into
the user's repo. Narrows C-23; adds C-34; amends architecture §3.2.

## Context

Three repos, three different TS misses:

- **hobbes (61.6%)** had its dependencies *installed* — and lane B
  still missed them. Its tsconfig-less `tsextract/` and `scip/`
  directories land in the root zone, and the stage linked only the
  *zone root's* nearest `node_modules` (none, at hobbes's root), never
  the trees sitting beside the files. Lane A reads the real repo where
  walk-up-from-the-file finds them — a silent lane asymmetry.
- **dagger (18.8%)** had no `node_modules` anywhere; its zones carry
  v1 `yarn.lock`s. C-23 said "install the tree" — invasive, the exact
  thing the direction rules out.
- **kbet (72.1%)** had a per-package tsconfig with its tree beside it:
  the shape the old code handled. Its residue is not dependency-shaped.

## Decision

**1. Link every `node_modules` on a zone file's walk-up path**
(`zone_dependency_links`). TypeScript resolution walks up from the
*importing file*, so the stage must offer what the repo offers at each
file's position — all trees on any zone file's path to the repo root,
each symlinked at its repo-relative position. This replaces the
single nearest-above-the-zone link and is a pure correction: no new
capability, the stage just stops being poorer than the repo.

**2. When the repo has no tree at all: provision one into Hobbes's own
cache** (`provision_node_modules`), and symlink it in exactly like a
repo-owned tree. Non-invasive by construction — the install runs in
`~/.hobbes/cache/npm/<hash>`, keyed by the content hash of
`package.json` + the lockfile, so re-ingests reuse it. The rules,
each load-bearing:

- **Lockfile-pinned or not at all.** `npm ci` for `package-lock.json`;
  classic yarn (corepack-run, version pinned in code — ADR-027
  Decision 1 applied to an installer) for a v1 `yarn.lock`. A
  package.json with no lockfile is *declined*: an unpinned install is
  the registry's answer of the day, and an artifact that changes
  between runs of the same commit breaks P1. pnpm and Yarn Berry are
  declined by name — Berry's PnP does not even produce the
  `node_modules` shape the indexer resolves against. Every declined
  zone gets a degradation record saying exactly why (C-23's surfacing,
  at the moment the gap is created).
- **`--ignore-scripts`, always.** A dependency's lifecycle script is
  arbitrary code. Unlike C-29 there is no analyzer that requires
  execution — type declarations are files, not build products — so
  nothing runs. The cost: a package whose types are *generated* by its
  postinstall would stay typeless; that lands in the residue, not in
  an exception.
- **Failure degrades the zone, never the language.** ADR-048's
  per-unit rule already holds; a failed install is a reason on the
  zone's record, and the zone indexes without dependencies as before.

## Registered costs

- **C-34 (new):** provisioning needs a fetchable npm registry — the
  npm sibling of C-30 — plus the lockfile boundary above. Surfaced by
  the per-zone degradation records and `dependency_coverage`.
- **C-23 (narrowed):** "install the dependency tree" is no longer the
  user's only path; it remains the answer for pnpm, Berry, and
  lockfile-less repos.

## Consequences

- The stage's dependency view now equals the repo's wherever the repo
  has one, and exceeds it (from cache) where the repo has none and a
  supported lockfile exists.
- `~/.hobbes/cache/npm` grows by one tree per distinct lockfile hash;
  stale hashes are dead weight until a cache sweep exists (noted in
  future_additions alongside the Rust target/ idea).
- Measured effects on hobbes, kbet, and dagger are in
  `docs/extraction-evidence.md` and the BUILDLOG entry.
