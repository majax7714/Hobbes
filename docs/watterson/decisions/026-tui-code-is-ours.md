# 026: The TUI's code is ours, from opencode's dev, with no upstream tracking

- Status: accepted; the switch built (see note); the code's place superseded by DEC-027
- Date: 2026-10-18
- Supersedes in part: DEC-025 (the fork `~/watterson-tui` at tag
  `v2.0.29`, with upstream merged in by choice). Keeps DEC-025's build:
  `tui/fork.lock`, `tui/build.sh`, `tui/bin/opencode`.

## Context
DEC-025 made the TUI a fork of opencode's `v2.0.29` that we build, with
upstream releases merged in when we chose. The user (2026-10-18) forked
opencode on GitHub (`majax7714/opencode`) and cloned its `dev` branch to
`~/opencode`: it is MIT, so we need not keep relying on opencode; making
it ours is a big job, to note and take in pieces.

Checked 2026-10-18: `dev` at `501b15a` (2026-10-18, version 2.0.32) is 169
commits past `v2.0.29`'s parent (`v2.0.29` is a release commit off `dev`);
34 files changed in `packages/server`, `protocol`, `client` and the plugin
API. Built with our two changes, it ran against `hobbes.serve`
unchanged: the home screen, then a fake-agent session (prompt, plan, tool
call, permission dialog, reply) the same as on the `v2.0.29` build; no
4xx or 5xx in the server log.

## Decision
The user picked each option (2026-10-18):
1. **The code lives in `~/opencode`**, the user's fork; our trunk is a new
   branch `main` from `dev` (`501b15a`). `dev` stays as the snapshot we
   started from. Upstream is not tracked: no merges from opencode are
   planned; any later borrowing is a choice, by hand.
2. **Our changes move over**: the `home.logo` slot and the built-in
   `hobbes` theme (DEC-025 slices 2 and 3), applied to `main` (one
   conflict, in the theme fallback).
3. **This repo pins `~/opencode` main** in `tui/fork.lock` (`base` is
   `dev`'s commit) and builds it with `tui/build.sh`, as DEC-025 set up.
   `~/watterson-tui` is retired.
4. **Making it ours goes by pieces** (open-work 11). The first is hiding
   what we do not back.

## Consequences
- opencode's later fixes do not reach us unless we take them by hand.
- The pieces of item 11 are each a commit in `~/opencode` main plus a pin
  change here.
- The user pushes `~/opencode` main to their fork; agents commit there,
  never push.
- The TUI's code stays out of this repo; where it lives when this
  environment folds into hobbes-public is open.

### Note, 2026-10-18: the switch built
- `~/opencode` main: `a3f7a29` (the slot), `0bf8993` (the theme, with opencode's
  fallback test now expecting `hobbes`), on
  `501b15a`. Built by `tui/build.sh`; launched in tmux, no prompts sent.
- opencode's TUI suite on `main`: 1,492 pass, 0 fail (1,494 run); `tsc -b`
  clean. A fake-agent session ran through the pinned build in tmux.
