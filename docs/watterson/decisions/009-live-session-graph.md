# 009: Live sessions: `hobbes chat`, a swapped graph view, a labeled prompt

- Status: accepted; built and checked live on claude and codex (see notes)
- Date: 2026-10-16
- Closes: open-work item 1 (`docs/open-work.md`, wire DEC-006 into a live session)
- Builds on: DEC-006 (engine), DEC-008 (knowledge surface)
- Supersedes: DEC-006 decision 3's carrier ("graph answers carry" the label)

## Context
DEC-006 built the engine (`hobbes.snapshot`, `hobbes.session_graph`) but
nothing live calls it, for three reasons:
- `hobbes ask` is one turn, so there is no "between turns";
- the knowledge surface (DEC-008, hobbes-proxy) reads only
  `<repo>/.hobbes/derived/`, not the session graphs in the cache;
- the proxy cannot append DEC-006's label to its answers.

Checked live with the real proxy (`hobbes_public@2089e22` binary): pointed
at a directory whose `.hobbes/derived` is a symlink, a running proxy serves
the new graph on its next answer after the link is swapped (it re-stats
per call, ADR-118). The directory is not a git repo, so the proxy's
HEAD-based stale warning stays off (`go/internal/knowledge/knowledge.go:548-560`).

## Decision
1. **`hobbes chat`**: a multi-turn session, one ACP session, one prompt per
   line; Ctrl-C cancels the running turn, Ctrl-D (EOF) ends the session.
   Options as `ask`: `--agent`, `--route`, `--allow-permissions`, `--repo`,
   `--refresh`/`--no-refresh`, `--no-knowledge`. `ask` stays one-shot.
2. **The graph view.** With knowledge on (DEC-008), each chat session gets
   `$HOBBES_CACHE_DIR/sessions/<repo>-<hash>/views/<session>/`, whose
   `.hobbes/derived` is a symlink, and the proxy runs with `--repo` on that
   view (and `GIT_CEILING_DIRECTORIES` above it, so git never finds an
   enclosing repo). The link starts at the repo's `.hobbes/derived` (the
   HEAD graph DEC-005 checked) and is swapped by rename **only at turn
   start**, to the store's current graph when one was published during the
   session. The view is removed when the session ends.
3. **Refresh between turns** as DEC-006 says: `Refresher.turn_ended()` after
   each turn, lane A only; refresh errors are reported, never fatal.
4. **The label prefixes each turn's prompt** (replacing DEC-006 decision 3's
   carrier): one line, `[hobbes] knowledge graph @ <sha> (<what it is>);
   changed since: <files>`, then a sentence telling the model to read
   changed files directly. Because the view swaps only at turn start, the
   label and the graph agree for the whole turn. The proxy's own `@ <sha>`
   header stays on every answer.
5. Refresh and label run only when knowledge tools are on; without them a
   chat is a plain multi-turn session.

## Consequences
- No hobbes-public change is needed. If hobbes-proxy later gains a derived-dir
  flag or a label hook, the view and the prefix can go.
- The label is per turn, not per answer: edits the agent makes during a turn
  are its own and are not listed until the next turn.
- The first turn runs on the HEAD graph; its label lists the files changed
  since that ingest (uncommitted edits). The first refresh starts after
  turn 1.
- `current.json` is shared by every session on a repo, so a graph another
  session published can be swapped in. It is a snapshot of the same
  working tree, so it is as valid as our own.
- Lane B is never refreshed mid-session (DEC-006); the label says "lane A
  only" for session graphs.

## Note: built (2026-10-16)
- `hobbes.live_session`: `GraphView` (the view dir and its swap) and
  `turn_label`. `hobbes chat` in `cli.py` shares `ask`'s options, setup and
  event printing; stdin is read on a daemon thread so Ctrl-C at the prompt
  ends cleanly. `knowledge.server` gained `env` (for
  `GIT_CEILING_DIRECTORIES`). Tests: `tests/test_live_session.py` (fake
  extract), plus the fake agent's `[hobbes]` label echo.
- **Bug found in DEC-006's `take_snapshot`:** on a repo that `hobbes ingest`
  has run on, `.hobbes/` is in `info/exclude`, and git 2.55 fails
  `add -A -- . ':(top,exclude).hobbes'` with "paths are ignored". Every
  ingested repo was affected; DEC-006's tests ingest only into the cache
  worktree, so they missed it. Fixed: the exclude pathspec is added only when
  git does not already ignore `.hobbes/` (`check-ignore`); covered by
  `test_snapshot.py`.
- End to end with real extraction and the fake agent, on an ingested scratch
  copy of `miniapp`: turn 1 labeled the HEAD graph; the agent wrote a file;
  the refresher snapshotted and ran a real lane A ingest; turn 2's view and
  label moved to the snapshot (`snapshot of <HEAD>, lane A only`); the view
  dir and the `refs/hobbes/` pin were gone afterwards.
- Not checked with a real harness at the time; see the next note.

## Note: live check (2026-10-16)
`hobbes chat --allow-permissions` on the user's logins (guarded: claude
`auto`, codex `agent`), on the ingested scratch `miniapp`. Turn 1 asked the
agent to add a file calling an existing function; turn 2, after a pause long
enough for the refresh, asked `who_calls` through the hobbes tools.

- **codex**: turn 1's label showed the HEAD graph and the files earlier runs
  had left (`changed since: src/miniapp/runner.py`). Turn 2's view had moved
  to snapshot `e649547`, and `who_calls miniapp.util.data_dir` returned the
  new `miniapp.paths.cache_root` (`src/miniapp/paths.py:5`), which only the
  snapshot graph has.
- **claude**: same result (`miniapp.env.env_root` and `miniapp.paths.cache_root`
  on snapshot `deb7bdd`), and it described the graph as a lane-A snapshot of
  the working tree that includes the new file.
- **Label wording changed after the first claude run.** "snapshot of
  944c397" was read by the model as "a copy of commit 944c397", so it
  explained an empty answer with "the snapshot predates my file". The label
  now says `snapshot of the working tree on top of <base>`; the rerun above
  used it. (The empty answer itself was right: that run's new code called
  `Engine(limit=3).run(item)`, and lane A records the call to `Engine` but not
  `.run` on the value it returns, Hobbes's C-1 caveat. The snapshot graph
  held `miniapp.runner.start`.)
- The proxy's flight log records `sha: ""` for these calls: the view is not
  a git repo (by design, above).
