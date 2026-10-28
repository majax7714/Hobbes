# 005: Check Hobbes graph freshness when a session starts; staleness is a different commit

- Status: accepted
- Date: 2026-10-16
- Narrows: open question 1 in `docs/overview.md` (boot flow)

## Context
Extraction takes time, so it cannot run before every agent action. The
open question was when to check whether the graph is current, and what
counts as "not current". Ingest stamps each derived file
(`<repo>/.hobbes/derived/{graph,tests,interfaces}.json`) with the repo's
HEAD as the top-level `sha`, next to a `dirty` boolean
(`hobbes.extract.emit.repo_stamp`, called from `hobbes.extract.ingest`).
`graph.json`'s `built_by.sha` is the Hobbes checkout that ran the ingest,
not the target. The adapter check (`hobbes agents --check`, DEC-004)
already does "compare, then prompt" with a generic `Freshness` result.

## Decision
The user's decision (2026-10-16):
- Freshness is checked **when a session starts in a repo**.
- **Staleness means only a different commit** for now: the graph's stamped
  commit against the repo's HEAD.
- A working tree that is **dirty** at session start gets a "dirty" tag. It
  is informational only and never triggers re-extraction or a prompt.
- **Behavior during an active session (dirty edits mid-session) is still
  open.** Nothing is built for it: no watchers, no re-extraction on edits
  or at turn ends.

How it is built:
- `pipeline/src/hobbes/freshness.py` (glue, outside `hobbes.extract`):
  `check_freshness(repo)` returns a `GraphCheck` wrapping the generic
  `Freshness` (moved to `hobbes/checks.py`, re-exported from
  `hobbes.providers.staleness`). Statuses: `fresh`, `stale` (N commits
  behind; "diverged"; "stamp not in history"; or the three stamps
  disagree), `missing`, `unreadable` (corrupt or partial output),
  `not a git repo`, `no commits`. The dirty tag counts changed or
  untracked files from `git status --porcelain`, `.hobbes/` excluded.
- `on_session_start(repo, interactive=, policy=)` holds the policy: a fresh
  graph gets a one-line note; a stale, missing or unreadable one is offered
  for re-extraction on a TTY (`[y/N]`), warned about on a non-TTY, or
  re-extracted without asking (`refresh`); `skip` does no check. A
  re-extract runs the `hobbes ingest` code path in-process, its output on
  stderr. The session goes ahead in every case.
- CLI: `hobbes freshness [--repo PATH]` (exit 0 fresh, 1 stale, missing or
  unreadable, 2 not a repo or no commits) and `hobbes ask --repo PATH
  [--refresh | --no-refresh]`, where the agent starts in the repo.

## Consequences
- A graph extracted from a dirty tree at HEAD counts as fresh; the check
  notes that it was extracted dirty.
- `unreadable` exits 1, with stale and missing, because a re-extract fixes
  it; exit 2 is kept for "nothing to compare against".
- Other entry points (an MCP server, a paseo-style plugin) can call
  `on_session_start` later instead of reimplementing the policy.
- Open: what to do about edits made during a session, and whether
  re-extraction should ever run in the background.
