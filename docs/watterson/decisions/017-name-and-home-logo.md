# 017: The world is "hobbes", `watterson` opens it; a hobbes logo replaces opencode's

- Status: accepted; built (see note)
- Date: 2026-10-16
- Narrows: DEC-011 (the application), DEC-016 (the `watterson` command),
  DEC-015 (the TUI plugin)

## Context
The TUI's home screen shows opencode's logo. The user wants it replaced
with Calvin and Hobbes art, from `hobbes_public/hobbesncalvin.jpg`
(Hobbes lying on a branch, Calvin resting), molded into the name. The
logo is not a plugin slot: opencode v2.0.29 draws it from
`packages/tui/src/logo.ts` in `routes/home.tsx:97`, and nothing configures
it. The TUI runs unmodified (DEC-013).

## Decision
The user agreed to each recommendation (2026-10-16):
1. **Names:** the environment is **hobbes**; **`watterson`** is the command
   that opens it: the author's name starts the world.
2. **Art:** hand-drawn pixel art, not a converted photo (an automatic
   cutout lost Hobbes's white head; the full scene is muddy at 64
   columns). The word "hobbes" in a block font, Hobbes asleep along its
   top with his tail hanging off the "h", Calvin resting at the end. Two
   pixels per cell with half blocks in true colour; letters take the
   theme's text colour; an ink outline (Watterson's brush line) keeps the
   white parts visible on light themes.
3. **Mechanism:** our TUI plugin finds opencode's logo element in the
   render tree by its glyph text, hides it, sizes its container to the
   picture and draws the picture at the container's screen position, so
   the TUI's own layout places it. If the element is not found, opencode's
   logo stays. A splash screen was the fallback; not needed.
4. **The character art stays out of the repo:** Calvin and Hobbes are Bill
   Watterson's. The picture is `~/.watterson/logo.txt` (`$HOBBES_LOGO`),
   rebuilt by `~/.watterson/logo-art.py`. Without it the logo is the word
   alone, in our own font (`hobbes.serve.logo`).

## Consequences
- The graft depends on opencode's logo text and on opentui's renderable
  API (`renderer.root`, `getChildren`, `visible`, `minWidth`/`minHeight`,
  `screenX`/`screenY`, `plainText`; `@opentui/core` 0.5.17 typings). A
  TUI bump needs a look at the home screen.
- The plugin walks the render tree only on the home screen, every 100 ms,
  until it finds the logo.
- An upstream `home.logo` slot would make the graft unnecessary.

### Note, 2026-10-16: built
- Server: `hobbes.serve.logo` and RPC `hobbes.logo`: `letters` (the word)
  always, `art` from the picture file when it parses, `error` when it
  does not. Picture files: palette lines, a blank line, grid rows; `.`
  transparent, `T`/`t` the theme's text and muted colours.
- Plugin: `HomeLogo` in the `app` slot. The art shows when the terminal
  has its width plus 4 columns and its height plus 12 rows; else the
  letters, with the same margins; else opencode's own logo (under about
  18 rows; under 12 opencode hides its logo).
- The art: 76 x 28 pixels (14 rows); the letters: 58 x 12 (6 rows).
- Checked live in tmux on a scratch clone, no prompts sent: the art at
  140x44, 140x40, 140x30 and 140x26; the letters at 70x24 and 70x18;
  opencode's logo at 70x24 before the thresholds were loosened; a
  wrapping prompt pushes the layout down and the art stays clear; the
  true colours in the pane's escape codes. Not checked live: returning
  to the home screen from a session, a theme switch, a bad picture file.

### Note, 2026-10-18: the picture is grafted into the tree, not overlaid
- Bug: the picture hid the home prompt's slash-command popup. The overlay
  sat in the `app` slot, a sibling of the whole route, at zIndex 500;
  opentui orders by zIndex among siblings only (`@opentui/core` 0.5.17,
  `_childrenInZIndexOrder`), so it painted over the route's subtree, the
  popup (`component/prompt/autocomplete.tsx:858`, zIndex 100 under the
  prompt's 1000 in `routes/home.tsx:101`) included.
- Fix, same decision otherwise: the plugin builds the picture as
  renderables and adds it to opencode's logo container beside the hidden
  logo (display none), so the container sizes to it and the prompt's
  popups stack over it as over opencode's own logo. No overlay, no screen
  position math, no `minWidth`/`minHeight`. Rebuilt on each graft, since
  the home route destroys its subtree on leaving.
- Checked live in tmux on a scratch repo, no prompts sent: the popup over
  the art at 140x44; the art centred as before (4 launches; the first
  showed it at the top of the screen once, not reproduced in three more
  or after a resize); the letters at 70x24; opencode's logo at 70x16;
  the art again after growing back to 140x44. Not checked live: returning
  home from a session, a theme switch.

### Note, 2026-10-18: no flash of opencode's logo at launch
- Bug: on each launch opencode's logo showed for about one frame before
  the picture replaced it. The 100 ms timer was the first cause; with a
  frame callback instead, one frame still slipped through in 3 of 5
  launches: opentui awaits frame callbacks, so the home route could mount
  between ours and the render, and a text element only takes its text
  in its own lifecycle pass (`@opentui/core` 0.5.17, `TextRenderable`).
- Fix, same decision otherwise: the swap runs in a lifecycle pass, inside
  each frame's render before layout, moved once a frame to the end of the
  renderer's set of passes so it runs after the logo's text is in. While
  the `hobbes.logo` answer is on its way, opencode's logo is hidden; if
  the call fails it comes back.
- Checked live in tmux on a scratch repo, no prompts sent, screen
  captured every 20 ms: no frame with opencode's logo in 6 launches at
  140x44 (before: 1 frame in 3 of 5); the letters at 100x24, opencode's
  logo at 70x16, the slash popup over the art. Not checked live:
  returning home from a session, a theme switch.

### Note, 2026-10-18: the graft is gone (DEC-025 slice 2)
- Our TUI fork has a `home.logo` slot around opencode's logo; the plugin's
  `HomeLogo` takes it over (`replace`) and renders the picture as plain
  components. No tree walk, no hidden element, no lifecycle pass. Where
  neither picture fits (under about 18 rows) the slot is empty rather
  than opencode's logo.
- Checked live in tmux, no prompts sent: no opencode frame in 3 launches
  (20 ms captures); the art at 140x44, the letters at 100x24, nothing at
  70x16; the slash popup over the art.
