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

## Amendment — 2026-10-03: the line goes in `.git/info/exclude` (0.2.93-beta)

**Status:** accepted (Max, 2026-10-03: route 1 of two, "write `.git/info/exclude` instead").

The decision above appended `.hobbes/` to the target's **tracked** `.gitignore` without asking, and nothing
reverted it: the first ingest of every repo left a modified file in the user's tree and flipped the stamp's
`dirty` flag. No register entry named it. The repo's tree is the user's, and "Hobbes files are personal"
is a fact about this clone, not about the repo.

1. **In a git repo, the line goes in the clone's own `info/exclude`** (`git rev-parse --git-path
   info/exclude`, so a linked worktree writes the shared one). Git reads it and never tracks it. The
   ingest no longer modifies the tree, and `dirty` is the user's alone.
2. **Nothing is written where any rule already ignores the path** (`git check-ignore`): the repo's
   `.gitignore`, a line an earlier ingest wrote there, or the user's global excludes. Earlier lines are left
   where they are; Hobbes does not edit them back out.
3. **The tracked-content exception is unchanged**: where `.hobbes/` content is tracked, only
   `.hobbes/derived/` is ensured.
4. **A directory that is not a git repo** has no tree to dirty and no exclude file; it still gets a
   `.gitignore` line, which a later `git init` reads.
5. `hobbes init`'s `*.tfstate` lines stay in `.gitignore`: they protect every clone, and `init` is the
   explicit bootstrap the user runs.

**What this gives up.** The protection is per clone: a second clone is protected when Hobbes first runs in
it, not before. A `.hobbes/` directory only exists where Hobbes has run, so nothing is left unprotected.
The visible, auditable line the first decision preferred is now in `.git/info/exclude`; the CLI still
reports the write.

Built: `extract/emit.py` (`ensure_hobbes_ignored`, `_ensure_gitignore_line`); tests in
`test_emit.py::TestEnsureHobbesIgnored`.
