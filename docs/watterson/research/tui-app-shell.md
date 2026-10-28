# The app shell: where a Hobbes control can live in the TUI

Survey for DEC-016 (decision 5), 2026-10-16. Source: opencode **v2.0.29**
(`github.com/anomalyco/opencode`, tag commit `042d0832f5f3`), the version
pinned in `tui/`. Paths are under `packages/`. A subagent survey; the
claims marked ✓ were spot-checked against the source or seen live in the
real TUI (tmux).

## Slots a plugin can fill (`plugin/src/tui/context.ts:191-202`) ✓

| Slot | Where | Home | Session |
|---|---|---|---|
| `app` | after the route content; holds global keymap layers | yes | yes |
| `home.footer`, `home.footer.status` | the home screen's bottom row (status hidden under 14 rows or 44 columns) | yes | no |
| `prompt.footer`, `.status`, `.file` | under the prompt box; input `{sessionID?, mode, showDetails}` (`tui/src/component/prompt/index.tsx:1586-1590`) | yes | yes |
| `session.composer.top` | above the composer | no | yes |
| `session.panel` | the right pane (DEC-015) | no | yes |
| `sidebar.content`, `sidebar.footer` | the sidebar, shown when wider than 120 columns or toggled | no | yes |

- **`prompt.footer.status` is the one spot visible on both screens.** The
  built-in `/btw` spinner lives there (`feature-plugins/prompt/btw.tsx:28`). ✓
  Boxes take `onMouseUp` (the MCP item does, `feature-plugins/home/footer.tsx:24`);
  an item cannot take keyboard focus, so keys go through a global command.
- Replacing `home.footer` removes `home.footer.status` with it; append.

## Other APIs

- **Startup:** `setup()` runs once the client is up, so `rpc.call` and
  `data.on` work before any session. The UI waits for every plugin's
  setup with no timeout, so setup must not await a slow call. ✓ (seen live)
- **Commands:** a `mode: "global"` keymap command with `slash` and
  `palette` works on the home screen too. ✓ (seen live)
- **Events:** `data.on(type, handler)` hands the handler the whole event;
  rpc events carry `data` (`client/src/solid/data.ts:70-73`). ✓
- **Toasts:** `toast.show({title?, message, variant?, duration?})`, one at
  a time, default 5 s; no progress or update in place. Progress is drawn
  in a slot. The host's `Spinner` is not exported to plugins (unverified
  whether `<spinner>` works in plugin JSX).
- **Dialogs:** `alert`, `confirm`, `prompt`, `select`, `show`. `confirm`'s
  `label` is `{confirm?, cancel?}`, titlecased (`tui/src/ui/dialog-confirm.tsx:14-17`). ✓
- **Storage:** `storage.store(key, {initial})` persists per plugin under
  the TUI's state dir and syncs across running TUIs (`context.ts:31-53`).
- **Not a git repo:** the TUI changes into the folder and nothing on its
  side breaks; our server reports the branch as `main` when git fails
  (`hobbes/serve/opencode.py`, `_vcs`).
