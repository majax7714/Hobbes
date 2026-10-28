# 025: The TUI is our own fork of opencode, built here

- Status: accepted; built (slices 1 to 3, see notes); the fork and its base superseded by DEC-026
- Date: 2026-10-18
- Supersedes in part: DEC-013 (the TUI "unmodified and pinned" from npm);
  DEC-017's mechanism (the logo graft) and DEC-024's mechanism (the theme
  linked in and named inline), each once its slice lands
- Keeps: DEC-013's server (`hobbes.serve`), the `--server` launch, and the
  plugin (DEC-015, DEC-016, DEC-022)

## Context
DEC-013 ran opencode's TUI unmodified, so every change to it was a cover
over opencode's own screen: the home logo is found in the render tree by
its glyphs and hidden (DEC-017), the theme is linked in and named through
config, with a black frame at launch (DEC-024). The user (2026-10-18):
opencode was a service that fit our needs and can change; we should not
depend on it, and covering things up should not be our only option.

DEC-013 weighed a fork against tracking upstream (about 1,365 commits a
month). A fork we own does not track upstream: we take its changes when we
choose to, by merge.

Spike, 2026-10-18, opencode tag `v2.0.29` (`042d083`,
github.com/anomalyco/opencode), Bun 1.4.2 (its `packageManager`):
- The TUI is not separable: `packages/tui` depends on `core`, `ai`,
  `client`, `plugin`, `theme`, `ui` and others; the binary is built from
  most of the monorepo (about 700k lines of TypeScript).
- `bun install` took 52 s (2,163 packages); `bun run script/build.ts
  --single --skip-web-ui --skip-install` in `packages/cli` took 4 s and
  wrote one 187 MB binary (`dist/cli-linux-x64/bin/opencode`).
- Unmodified, that binary ran against `hobbes tui`'s server in tmux with
  our plugin, logo and theme, no prompts sent.
- The build asks npm for the latest version unless `OPENCODE_VERSION` is
  set or the channel is not `latest` (`packages/script/src/index.ts:25-52`).
  The TUI warns before starting when the server's version differs from its
  own (`packages/cli/src/services/server-connection.ts:35`).

## Decision
The user picked each option (2026-10-18):
1. **A separate fork repo**, `~/watterson-tui`: opencode cloned at
   `v2.0.29` (history kept, blobs fetched on demand), our work on branch
   `watterson`, upstream as remote `upstream`. The user adds their own
   remote and pushes; agents commit there, never push. Not a source repo
   in CLAUDE.md's sense: it is ours to change.
2. **This repo pins and builds it.** `tui/fork.lock` names the commit and
   the Bun version; `tui/build.sh` checks the fork is at that commit with
   a clean tree, fetches the pinned Bun into `~/.watterson/bun/` (checked
   against its SHA-256) if it is missing, installs and builds, and puts
   the binary at `tui/bin/opencode` (out of git). The build's version is
   the base tag's (`2.0.29`, matching `hobbes.serve`), its channel
   `watterson`, so it makes no npm call and the TUI shows no mismatch
   warning.
3. **The npm pin goes**: `tui/package.json` and its lock are removed.
4. **Slices**, each its own commit here and in the fork:
   1. Build and launch from the fork, unmodified.
   2. The logo: a `home.logo` slot in the fork's home route, filled by our
      plugin from `hobbes.logo`; the tree walk is deleted. The character
      art stays out of both repos (DEC-017).
   3. The theme: `hobbes` is a built-in theme and the default in the fork;
      the link and the inline name are deleted. A `/themes` pick still
      sticks, natively.

## Consequences
- We own the TUI's code and its upkeep: a bump is a merge of an upstream
  tag into `watterson`, by choice, then a look at our changes.
- Building needs Bun 1.4.2 (fetched by `build.sh`) and network for
  `bun install` on a fresh fork.
- Fresh machines need the fork: until the user publishes it, it exists
  only at `~/watterson-tui`.
- Changes to opencode's screens are ordinary code in the fork, with its
  types. Hobbes's own features can stay in the plugin.
- The fork is MIT (opencode's `LICENSE`, kept); our changes there are
  stated in its commits.

### Note, 2026-10-18: slices 1 and 2 built
- Slice 1: `~/watterson-tui` at `v2.0.29`, upstream's push URL disabled
  (`DISABLED-do-not-push-to-opencode`). `tui/build.sh` from cold (Bun
  fetch, `bun install`, build): 50 s. The binary reports `2.0.29`; no
  mismatch warning on start.
- Slice 2: fork commit `21691a7` adds the `home.logo` slot (plugin API
  `SlotMap`, `routes/home.tsx`, the plugin docs); `tsgo` clean in
  `packages/tui` and `packages/plugin`; the fork's
  `session-home` and `app-lifecycle` tests pass (51). The plugin fills the
  slot (DEC-017 note).
- Slice 3: fork commit `8101c7b`: `hobbes` built in and the default
  (DEC-024 note).
