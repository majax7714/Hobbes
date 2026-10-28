# 013: The TUI is opencode v2, unmodified and pinned, talking to a Hobbes server

- Status: accepted; first slice in progress; the npm pin, run unmodified, superseded by DEC-025
- Date: 2026-10-16
- Narrows: open-work item 4; DEC-011's first open question (how the TUI
  talks to our Python layer)
- Corrects: DEC-011's version (see below)
- Research: `docs/research/tui-base.md` (corrected in this change)

## Context
DEC-011 chose opencode's TUI as the base. A follow-up survey found two
opencode lines, and DEC-011 described the wrong one by version:
- **v1** (GitHub "Latest" v1.19.3, npm `opencode-ai`): TUI client
  `@opencode-ai/sdk/v2`, `opencode attach <url>`; no `packages/merman`, no
  `session.panel` slot.
- **v2** (`dev` branch; npm `@opencode/cli`, bin `opencode2`, no GitHub
  release): `--server URL`, `packages/merman`, the `session.panel` slot.
  v1.19.3 is not an ancestor of `dev`; v2 is a rewrite.

Everything DEC-011 and the research note said about merman, the panel slot
and `@opencode/client` is v2.

Both TUIs connect to a server URL; v2 only warns when the server's version
does not match (`packages/cli/src/services/server-connection.ts`, at
`dev` 180fd9d). A v2 graph panel can be a third-party plugin in
`session.panel`, as opencode's diff viewer is. Forking the TUI instead
would mean rewiring 52 files and a 2,016-line data layer against about
1,365 upstream commits a month.

## Decision
1. **v2, pinned exactly**, in `tui/` the way `adapters/` pins the ACP
   adapters (DEC-004): `@opencode/cli` in `tui/package.json` plus
   `package-lock.json`, installed with `npm ci`. Bumps are manual, with
   DEC-004's 2-day cooldown. First pin: **2.0.29** (2026-10-14; 2.0.30 and
   2.0.31 were under two days old). The package ships a compiled binary per
   platform, so running it needs no Bun; Bun is installed only when a step
   needs it (building or testing TUI plugins).
2. **No fork.** The TUI runs unmodified with `--server` pointing at a
   **Hobbes server**: Python, in this repo, speaking the slice of
   opencode v2's HTTP + SSE API the TUI needs, backed by
   `hobbes.providers` sessions, `hobbes.permissions` and the DEC-010 hooks.
   Startup data opencode's TUI expects (providers, models, agents, config)
   is served from our own registry or fixed data.
3. **Loopback only**, with a per-run password the server generates and
   hands to the TUI it launches.
4. **Contract tests** replay the requests and events of the pinned
   version, so a bump that changes the API fails a test, not the user.
5. Defaults the user left to us:
   - session history lives under `$HOBBES_CACHE_DIR`;
   - "always" picked in the TUI selects the harness's own `allow_always`
     option when it offers one (a human may choose it, DEC-007); Hobbes
     never picks it by itself;
   - `ToolCall` / `ToolCallUpdate` gain the tool's input and output,
     which the TUI shows and our provider layer currently drops.
6. Graph views do not wait on this: the level model is its own track
   (open-work 4, next record).

## Consequences
- The TUI shows features we do not back (revert, share, shell) until they
  are hidden or answered; which ones is open.
- The opencode API is internal and changes fast: bumps need the contract
  tests and may need server changes.
- The `tui/` binary is about 210 MB unpacked; `node_modules/` stays out of
  git.
- The opencode source the server is written against is tag `v2.0.29`
  (`042d083`); cite it, not `dev`.

### Note, 2026-10-16: first slice built
- `hobbes.serve` (stdlib only: a small asyncio HTTP/1.1 server with an
  event stream, so no new dependency), written against tag `v2.0.29`:
  the startup catalogs, sessions, prompt, interrupt, and permission prompts
  and replies. `hobbes tui [--repo DIR] [--serve-only]` starts it with a
  fresh password and runs `tui/`'s `opencode2 --server` in the terminal,
  with the TUI's XDG dirs under `$HOBBES_CACHE_DIR/tui/xdg` and its
  updater off.
- The TUI's **agents are the routes** (`guarded`, `manual`), so Shift+Tab
  switches route; its **models are the registry's harnesses**. A change of
  either restarts the harness, with a notice in the transcript.
- `turns.Turn` keeps opencode's part order (a tool is announced once its
  input is known or a permission names it). An ACP plan becomes a notice;
  opencode v2 has no plan view.
- Checked with the real pinned TUI in tmux, with the fake ACP agent as the
  only model: it boots with no error view, shows "Guarded · fake (ACP)", runs
  a turn through a permission dialog (Allow once / Reject), and switches
  route with a restart notice.
- Not built: transcript history (`GET …/message` is empty, so a reconnect
  or reopened session shows no past turns), the knowledge tools and
  between-turn graph refresh of `hobbes chat`, hiding opencode's
  "Connect provider" panel, and features we do not back (revert, share,
  shell mode). Not yet run against a real harness.

### Note, 2026-10-16: first real-harness run
- With the user's go-ahead, `hobbes tui` ran against claude (pinned
  `claude-agent-acp`) on a throwaway git repo, driven in tmux. Three turns:
  a read in guarded (no prompt, 4.8s); after Shift+Tab to manual, an edit
  through the TUI's permission dialog with "Allow once" (file changed as
  asked); then an edit with "Reject" (file unchanged, claude reported the
  refusal). The route switch showed its restart notice. The DEC-010 hook
  log recorded `allow_once` and `reject_once` with the tool ids. No errors
  in `server.log`; quitting left no harness or TUI process.
- Rough edges seen, not fixed: tools show as `read_tool` / `edit_tool` with
  no file name (`serve/turns.py` `tool_name` renames ACP kinds off the TUI's
  reserved names, so its own read/edit views are not used); the permission
  dialog says "No diff provided" although the edit's diff is known; the
  session title stays "New session"; opencode's "Getting started / Connect
  provider" panel shows beside the transcript.

### Note, 2026-10-16: read and edit views, and the edit's diff
- Tool events (`ToolCall`, `ToolCallUpdate`) and `PermissionRequest` carry
  the call's `paths` and its ACP diff blocks (`FileDiff`). A `read` or
  `edit` call that names a file now uses the TUI's own view under that name,
  with `input.path` added to the harness's input; an edit's success carries
  `metadata.files`, and its permission prompt `metadata.diff`.
- The patch (`hobbes.serve.patches`) is a whole-file unified diff like
  opencode's own edit tool builds. Harnesses send only the snippet, so the
  snippet is placed in the file on disk (its old text before the edit is
  applied, its new text after), or stands alone, numbered from 1, when it
  cannot be placed exactly once.
- A tool is now announced only once its input is non-empty, and a read or
  edit also waits for its file: claude's adapter starts each call with an
  empty input and streams it in, so the name was fixed too early (a shell
  command would also have missed the `bash` view).
- Checked live with claude in the real TUI: the read shows in the TUI's
  "Explored" group; the permission prompt and the transcript show the edit
  as a numbered diff; a rejected edit shows its header and the refusal, no
  diff. Search calls (grep, glob) stay generic: the ACP kind does not tell
  them apart. Still open: the session title, the "Getting started" panel.

### Note, 2026-10-16: transcript history
- `hobbes.serve.transcript` builds each session's messages in opencode's
  `SessionMessageInfo` shape from the events the server publishes, the way
  the TUI's data layer does (`client/src/solid/data.ts:671-1107` at
  v2.0.29), so loaded and live rows share ids. `GET …/message` pages it
  newest first (the cursor is the oldest message id sent), and
  `GET …/message/{id}` returns one message.
- Each session's events, minus streaming deltas, are appended to
  `$HOBBES_CACHE_DIR/tui/sessions/<session id>.jsonl` (decision 5's
  default). At start the server replays this repo's logs: sessions and
  transcripts survive a restart, and a turn the log ends mid-way is closed
  (its unfinished tools fail). A loaded session's harness starts fresh, with
  the restart notice: the harness has none of the earlier turns. Loading
  the harness's own session (ACP `session/load`) is not built.
- Checked live with claude in the real TUI: after quitting and relaunching
  `hobbes tui`, the session list showed the session, and opening it showed
  the turn as it looked live (read group, edit diff, reply, footer); the
  next prompt showed the fresh-harness notice. The session list also offers
  delete and rename, which the server does not back yet.
