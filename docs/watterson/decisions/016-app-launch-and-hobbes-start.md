# 016: `hobbes` opens the app; "Start Hobbes" switches the Hobbes layer on, per repo

- Status: accepted; slices 1-2 built (see notes)
- Date: 2026-10-16
- Narrows: DEC-011 (the environment is an application), DEC-013 (`hobbes
  tui`); folds in open-work "Next up" (`hobbes tui` parity with `hobbes chat`)

## Context
Using the environment means typing commands from `pipeline/`
(`uv run hobbes ingest`, then `uv run hobbes tui --repo DIR`). The user
wants it to be an application (the user, 2026-10-16): it opens like a
normal TUI, has a control inside it to start Hobbes, and can start Hobbes
on its own the next time it opens. Running commands is what people do not
like doing.

One constraint: the TUI cannot open without a backend. Without `--server`
it starts opencode's own background service, which we never allow
(DEC-013). So the Hobbes server always starts with the app; it listens on
loopback and reaches no harness or network until a turn is sent.

## Decision
The user agreed to each recommendation (2026-10-16):
1. **One command.** `hobbes` with no arguments opens the app (what
   `hobbes tui` does) on the git repo around the current folder.
   `uv tool install --editable ./pipeline` puts `hobbes` on the PATH,
   pointing at this checkout. The user runs the install; it changes their
   machine.
2. **"Start Hobbes" switches on the whole Hobbes layer** for the repo:
   extract the graph or refresh it when stale (DEC-005), the graph panel,
   knowledge tools on turns (DEC-008) and graph refresh between turns with
   the prompt label (DEC-009). This is `hobbes tui`'s parity with `hobbes
   chat`. With Hobbes off, the app is a plain agent TUI that keeps the
   permission routes and Claude hooks (DEC-007, DEC-010).
3. **Auto-start is per repo**, remembered for each repo Hobbes was started
   in, so opening the app somewhere new never starts a long first
   extraction by itself.
4. **Outside a git repo** (or in one with no commits) the app still opens,
   on the current folder; the start control says that Hobbes needs a git
   repo with a commit.
5. **Where the control lives** (a visible button or status, besides the
   palette and a slash command) waits on a survey of opencode v2.0.29's
   plugin slots.

Slices: (1) the launcher; (2) the start control, the on/off state and
extraction progress in the app; (3) knowledge tools and between-turn
refresh in `hobbes tui`; (4) auto-start.

## Consequences
- `hobbes tui` stays as the explicit form; scripts keep working.
- The server owns the Hobbes state per repo (on or off, auto-start), so
  the plugin stays thin (DEC-015).
- An editable tool install runs this checkout's code: a broken working
  tree breaks the installed `hobbes` too.

### Note, 2026-10-16: slice 1 built
- `hobbes` alone runs `hobbes tui`. `hobbes tui` without `--repo` takes the
  git root above the current folder, else the current folder (it used to
  exit). The server already copes with a folder that is not a repo (the
  branch shows as `main`).
- Checked: `uv tool install --editable ./pipeline` into scratch tool dirs;
  the installed `hobbes` runs from `/tmp`, finds the adapters and the
  pinned TUI (`tui/node_modules/.bin/opencode2`), and `levels` works. Not
  installed into the user's `~/.local/bin`.

### Note, 2026-10-16: slice 2 built (the start control)
- Placement (decision 5, survey `research/tui-app-shell.md`): an item in
  the `prompt.footer.status` slot, the one spot under the prompt on both
  the home screen and in sessions: `◌ hobbes off · start`, `⠋ hobbes
  starting · 12s`, `● hobbes on`, `✕ hobbes failed · retry`, `◌ hobbes
  unavailable`. A click starts it, or asks before stopping. `/hobbes` (and
  the palette entry "Start or stop Hobbes") does the same. Toasts say
  when it is on or failed.
- Server: `hobbes.serve.layer.Layer` per app. Start checks freshness and,
  when the graph is stale or missing, runs `hobbes ingest` in a child
  process (output in `$HOBBES_CACHE_DIR/tui/ingest.log`; ingest prints
  only at the end, so the app shows elapsed time). RPC `hobbes.status`,
  `hobbes.start`, `hobbes.stop`; changes pushed as `rpc.hobbes.status`.
  Stop cancels a start in progress. **The graph panel answers only while
  Hobbes is on**, so until auto-start (slice 4) each open needs a start.
- Checked live in tmux on a scratch clone of this repo, no prompts sent:
  the item on the home screen, `/hobbes` → starting → "Hobbes is on."
  (a real ingest), a second start instant (graph fresh), the
  stop dialog's Stop and Esc. Not checked live: a mouse click, the failed
  toast, the item inside a session, narrow terminals.

### Note, 2026-10-16: the app's command is `watterson`, not `hobbes`
- Decision 1's install failed on the user's machine: `~/.local/bin/hobbes`
  is a link to hobbes-public's CLI (since 2026-08-28), and `uv tool
  install` refuses to replace an executable it did not install. It says so
  only on its last line (`Executable already exists: hobbes (use --force
  to overwrite)`), after listing the packages, so it reads as success.
- The user chose (2026-10-16) a command of its own, keeping hobbes-public's
  `hobbes` in place: `bin/watterson`, a launcher that runs this checkout's
  `hobbes` with `uv run --project pipeline` in the current folder, linked
  as `~/.local/bin/watterson`. Bare `watterson` opens the app; arguments
  pass through. No `uv tool install`. Nothing in hobbes-public calls
  `hobbes` through the PATH (its scripts use `uv run --project`; grep at
  `2089e22`).
- Checked: from `/tmp`, `watterson --version` and `watterson levels`
  work and `hobbes` is still hobbes-public's (0.2.121-beta); in tmux, a
  bare `watterson` in a scratch repo opens the app with Hobbes off, and
  quits cleanly.
