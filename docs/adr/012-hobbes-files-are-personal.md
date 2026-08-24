# ADR 012: Hobbes files are personal — target repos gitignore `.hobbes/` wholly

Date: 2026-08-10
Status: accepted

## Context

Architecture §10 splits `.hobbes/` into versioned (`policies/`,
`invariants/`) and gitignored (`derived/`) halves. Max's directive
(2026-08-10, after the M3 review): Hobbes files are for his personal
environment only — in *his* repos, an accidentally committed/pushed
`.hobbes/` would be a mess. The versioned half of §10 presumes a team
sharing policy; v1 is single-dev.

## Decision

**Target repos gitignore the entire `.hobbes/` directory.** Both
`hobbes ingest` and `hobbes init` guarantee it: before doing anything
else they ensure the repo's `.gitignore` contains `.hobbes/`, appending
it if missing (which honestly flips the ingest stamp's `dirty` flag on
that first run — the tree really was modified).

**Exception — repos that already track `.hobbes/` content** (today: the
hobbes repo itself, dogfooding §10): their versioning choice is
respected, and only `.hobbes/derived/` is ensured ignored. The guard is
`git ls-files .hobbes` being non-empty; a non-git directory gets the
target-repo posture.

This refines §10 for v1 rather than repealing it: policies and
invariants still *live* at the §10 paths and the policy engine still
loads them — they are simply untracked in repos where nobody has opted
their `.hobbes/` into version control.

## Alternatives considered

- **A self-ignoring `.hobbes/.gitignore` containing `*`** — elegant (no
  repo-level edit), but poisonous in the dogfood repo: it would silently
  hide future policy/invariant additions from git there. A visible line
  in the repo's own `.gitignore` is auditable.
- **Leaving it to `hobbes init` only** — Max ran bare `ingest` on both
  test repos and got untracked `.hobbes/` clutter; protection that
  depends on remembering a bootstrap step isn't protection.
- **Policy-engine deny on `git add .hobbes`** — the M4 proxy will see
  agent commands, but Max types his own; `.gitignore` protects both.

## Consequences

- `hobbes ingest` in a fresh repo touches `.gitignore` — a side effect,
  deliberately visible (reported by the CLI, reflected in `dirty`).
- If policies ever become team-shared (multi-dev Hobbes), committing
  `.hobbes/policies/` in that repo is one `git add -f` away, and the
  tracked-content guard then preserves it automatically.
- The hobbes repo's own dogfooding is unchanged.
