# 006: Active sessions extract snapshots and refresh between turns

- Status: accepted; engine built (see note). Wired into `hobbes chat` by DEC-009, which also replaces decision 3's carrier.
- Date: 2026-10-16
- Builds on: DEC-005

## Context
DEC-005 checks freshness at session start. During a session the agent edits,
tests and edits again. Re-extracting the live working tree would race those
edits: Hobbes could read half-changed code. Running one agent per job on a
clean tree would avoid the race, but it controls dev workflows, which we don't
want to impose.

Hobbes's own stamp is `{"sha": HEAD, "dirty": bool}`. A graph extracted from a
dirty tree therefore claims HEAD while containing uncommitted edits, so it
can't be rebuilt from its SHA. (Found while building DEC-005;
`hobbes freshness` notes it as "the graph was extracted from a dirty tree".)

## Decision
1. **Extract snapshots, never the live tree.** Glue code freezes the current
   tree into a git commit object without touching the branch, index or
   working files: a temp `GIT_INDEX_FILE` with `add -A`, then `write-tree`,
   then `commit-tree`. It ingests that commit in a temporary worktree. The
   stamp is then the snapshot's SHA with `dirty: false`, which is honest and
   diffable. No change to `hobbes.extract`.
2. **Refresh between turns, not on each edit.** We are the ACP client, so we
   see turn ends and edit tool calls. At a turn end with changed files,
   snapshot and re-extract in the background. Allow **at most one running
   and one pending** run; a newer snapshot replaces the pending one.
3. **Label instead of block.** Graph answers carry
   `graph @ <snapshot>; changed since: <files>` (a `git diff` against the
   snapshot), so the model knows which parts to distrust and reads those
   files directly.
4. One-agent-per-job on a clean tree stays an **optional mode** for later. It
   is never enforced.

## Consequences
- The race becomes ordinary staleness, which DEC-005's machinery already
  reports.
- Snapshot commits are unreferenced objects. They need a cleanup policy (or a
  private ref namespace) so they don't pile up.

## To verify before building
- Lane A re-extract time on a real-size repo with a warm cache. This decides
  whether every turn end is cheap enough, or whether we need a minimum
  interval between runs.
- That a snapshot SHA (on no branch) causes no problems in Hobbes provenance
  output, or in `freshness` ancestry checks (`rev-list stamp..HEAD`).
- Where snapshot worktrees and graphs live (the repo's `.hobbes/derived/`, or
  the `~/.watterson/cache` keyed by SHA), and how the session's graph is
  swapped atomically.

### Note, 2026-10-16: checks run, choices taken, engine built
Measured on a clone of `hobbes_public@2089e22` (1,255 files, nine
languages) in a scratch dir:
- **Snapshot cost:** about 19 ms (temp index copied from the real one, so
  `add -A` rehashes only changes). Branch, index and working files are
  untouched; the only writes are objects.
- **Lane A re-extract:** 16.3 s cold, 15.9 s warm, 15.3 s after a one-file
  edit; checking the reused worktree out to the next snapshot takes 7 ms.
  The cache barely helps: 10.2 s is Python parsing, and lane A caches only
  C++ (`laneacache`). Incremental Python would be a hobbes-public change.
  With one running and one pending, no minimum interval is needed. Lane B:
  **not measured, on purpose.** Its cost varies widely by repo, so one
  number would not say much. It is better judged per repo, in real time,
  when extraction is graded (the user, 2026-10-16).
- **Provenance:** the SHA appears only in the top-level stamp
  (`extract/__init__.py:2378`) and the timings log; edges carry `file:line`.
  A snapshot graph is stamped `{sha: <snapshot>, dirty: false}`.
- **Ancestry:** a snapshot's parent is HEAD, so it is never an ancestor of
  HEAD, and DEC-005's check called it `diverged` (stale). Fixed: a snapshot
  stamp is compared through its base (`hobbes.snapshot.snapshot_base`).
- **"Changed since"** must diff two snapshot trees, not `git diff <snap>`
  against the work tree: that shows untracked files in the snapshot as
  deleted and misses files created after it.

Choices (the user's, 2026-10-16):
- **Where:** the cache, `$HOBBES_CACHE_DIR/sessions/<repo>-<hash>/`: one
  reused linked worktree, graphs under `graphs/<sha>/`, `current.json`
  swapped by rename, last 5 graphs kept. The repo's `.hobbes/derived/` stays
  the HEAD graph from `hobbes ingest`. The worktree shows in
  `git worktree list`, and its ingest writes `.hobbes/` to the repo's shared
  `info/exclude` (as `hobbes ingest` does).
- **Cleanup:** one private ref per session, `refs/hobbes/snapshot/<session>`,
  at the latest published snapshot, deleted on close; older snapshots are
  left to `git gc`.
- **Lanes:** between turns, lane A only; the label says so.
- **Scope:** engine only. `hobbes ask` is a single turn and the knowledge
  surface that would carry the label is still open, so nothing live calls
  the refresher yet.

Built: `hobbes/snapshot.py` (deterministic snapshot commit: fixed identity
and date, so an unchanged turn gives the same SHA and needs no run),
`hobbes/session_graph.py` (`GraphStore`, `Refresher`, `GraphLabel`) and
`check_freshness(repo, derived=…)`. The extract is `hobbes ingest` in a
subprocess, so the session's event loop is not held for ~16 s.
