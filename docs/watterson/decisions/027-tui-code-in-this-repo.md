# 027: The TUI's code moves into this repo, trimmed, at `tui/opencode/`

- Status: accepted; built (see note); amended by DEC-028 (2026-10-29: the
  fork keeps what the binary ships and the TUI's tests)
- Date: 2026-10-18
- Supersedes in part: DEC-026 (the code in `~/opencode`, pinned by commit
  in `tui/fork.lock`). Keeps DEC-026's stance: the code is ours, from
  opencode's `dev` at `501b15a`, upstream not tracked.

## Context
DEC-026 kept the TUI's code in `~/opencode`, the user's fork, outside this
repo. The user (2026-10-18): move the necessary code into this repo, to
keep the environment as one repo; start by moving everything and trimming.

opencode's tree at `501b15a`: 8,561 files, 139 MB (76 MB gzipped), against
this repo's 3.6 MB `.git`. Most of it is not reached by the TUI build:
`packages/console` alone is 42 MB gzipped (videos), `desktop` 8 MB, `web`
5.5 MB, and `packages/ai/test` holds 15 MB of recorded provider fixtures.
What lands in a commit stays in history after a later delete.

## Decision
The user picked each option (2026-10-18):
1. **Trim before the first commit.** The whole tree was copied into the
   working tree, then cut down to what the TUI build uses (the workspace
   closure of `packages/cli` and `packages/tui`: 20 packages) while it
   still type-checks, builds and passes its tests; only that is
   committed. Every left-out path and every change is listed in
   `tui/opencode/NOTICE.md`.
2. **At `tui/opencode/`**, beside `tui/plugins/` and `tui/build.sh`.
   `tui/fork.lock` goes; the Bun pin and the reported version move to
   `tui/build.env`.
3. **Commits**: the trimmed import (verbatim but for the root
   `package.json` and the pruned `bun.lock`), then the `home.logo` slot
   and the `hobbes` theme as their own commits, the same changes as
   `~/opencode` main `a3f7a29` and `0bf8993`.
4. `~/opencode` and `~/watterson-tui` are no longer used by the build.

## Consequences
- One repo: changing the TUI is an ordinary commit here, reviewed with
  the rest. The import is 4,304 files, about 7.5 MB gzipped.
- The TUI's tests are this repo's tests too (commands in CLAUDE.md).
- CLAUDE.md's verbatim rule (extraction) does not cover `tui/opencode/`:
  it is ours to change, and its own `AGENTS.md` describes its idioms.
- More trimming (open-work 11d) continues in commits.
- Folding into hobbes-public (open-work 11g) now carries this directory.

### Note, 2026-10-18: built
- Trimmed to 20 packages (the closure of `cli` and `tui`'s workspace
  dependencies), then: the release scripts, which needed the dropped
  `@aws-sdk/client-s3`; `packages/ai/test`, which nothing else imports
  (`core` uses `@opencode/ai/testing`, in `src`). `.github/TEAM_MEMBERS`
  stays: `packages/script` reads it at build time. Every kept upstream
  file is in the commit (none fell to this repo's `dist/`/`build/`
  ignores).
- `bun.lock`: 7,722 lines to 2,336; the 31 added lines are re-hoisted
  entries at versions already locked.
- `bun turbo typecheck`: 19 of 19. `tui/build.sh`: builds. Tests: `tui`
  1,492 pass, 0 fail; `server` 84, `client` 229, `util` 95, `plugin` 9,
  `theme` 2, all passing; `cli` 329 pass, 1 fail (`stats rendering >
  uses the OpenCode palette in color mode`), which fails the same on
  untrimmed `dev` in `~/opencode`, also without `COLORTERM`; cause
  unknown.
- Then `341ef33` (the `home.logo` slot; its hunk in the dropped
  `services/www` docs left out) and `cd7071e` (the `hobbes` theme), from
  `~/opencode` main by `git am`. Rebuilt; theme and home tests 18 pass;
  live in tmux with the fake agent: the logo, the navy, a session.
