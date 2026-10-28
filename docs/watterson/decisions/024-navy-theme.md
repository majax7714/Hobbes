# 024: The TUI's default theme is Hobbes's own calm navy

- Status: accepted; built (see note)
- Date: 2026-10-18
- Narrows: DEC-013 (the TUI, run unmodified), DEC-017 (the home screen)

## Context
The user finds opencode's default background (`#0a0a0a`, theme `opencode`)
too harsh and asked for a calmer navy (2026-10-18). Open-work item 4 (the
application). How opencode v2.0.29 (tag `v2.0.29`, `042d083`) picks a theme,
checked in its source:
- The CLI config's `theme.name` and `theme.mode`
  (`packages/tui/src/config/index.tsx:70-77`); default `opencode`
  (`packages/tui/src/context/theme.tsx:115`). The main background is the
  theme's `background.base` (`theme.tsx:309`), not the terminal's.
- Custom themes are `themes/*.json` in the config dir, found by file name
  (`packages/tui/src/theme/discovery.ts`), in the v1 format
  (`defs` and `theme`) or v2 (`base`).
- A `/themes` pick is saved to `<config dir>/cli.json`, but the inline
  config (`OPENCODE_CLI_CONFIG_CONTENT`) is merged over that file at every
  start (`packages/cli/src/config/config.ts:65`).
- A plugin cannot set or register a theme (`packages/plugin/src/tui/context.ts`:
  `theme` is read only).

## Decision
The user picked each option (2026-10-18):
1. **Our own theme, `hobbes`**, not a built-in: `tui/themes/hobbes.json`,
   made from opencode's `tokyonight` (MIT, `packages/tui/src/theme/assets/tokyonight.json`
   at `042d083`). Changes: the background steps are navy (`#1a2233` main,
   `#222c40` panels, `#2a3550` elements); the dark values are used in
   both modes, so a light terminal gets the navy too; the light palette
   is dropped. Provenance and the MIT notice: `tui/themes/README.md`.
2. **A `/themes` pick sticks.** `hobbes tui` links the file into the TUI's
   private `themes/` dir (`$HOBBES_CACHE_DIR/tui/xdg/config/opencode/`)
   and names `hobbes` in the inline config only while that dir's
   `cli.json` names no theme (`hobbes.serve.launch.tui_config`). A
   `cli.json` that does not parse as plain JSON (JSONC comments) counts as
   a pick, so it wins.

## Consequences
- The TUI stays unmodified; the theme is config and a file.
- About 150 ms of opencode's black shows at launch, on a screen still
  empty: the TUI paints with built-in themes until it has read the custom
  ones (`theme.tsx:167-173`). A built-in theme would not have this gap.
- The logo art (DEC-017) was drawn on dark themes; it reads on the navy.
- A TUI bump needs a look at the theme: the v1 format's keys
  (`packages/theme/src/tui/v1.ts`) may change.

### Note, 2026-10-18: built
- Checked live in tmux on a scratch repo with a scratch
  `HOBBES_CACHE_DIR`, no prompts sent: the background is `#1a2233` from
  the first frame with content (escape codes, 48;2;26;34;51); `hobbes`
  shows, chosen, in `/themes`; picking `kanagawa` saved it to `cli.json`,
  and the next launch kept it. Not checked live: a light terminal, the
  session screen's panels and diffs on the navy.

### Note, 2026-10-18: the theme moves into our TUI fork (DEC-025 slice 3)
- `hobbes` is a built-in theme in the fork (`packages/tui/src/theme/assets/hobbes.json`,
  listed in `theme/v1.ts`) and its default (`DEFAULT_THEME` in
  `context/theme.tsx`, also the fallback for a missing pick). The file
  descends from opencode's own tokyonight inside opencode's repo, under
  its `LICENSE`. `tui/themes/`, the link and the inline name are deleted.
- The black at launch is gone: built-ins need no discovery. A `/themes`
  pick sticks natively (saved to `cli.json`, nothing overrides it).
- Checked live in tmux, fresh cache dir, no prompts sent: in 3 launches
  the background goes from the terminal's straight to `#1a2233`, no
  `#0a0a0a` frame; `hobbes` chosen in `/themes`; `kanagawa` picked, kept
  on relaunch. The fork's TUI tests: 1,466 pass, 0 fail (1,468 run).
