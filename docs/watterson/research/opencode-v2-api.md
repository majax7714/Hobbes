# opencode v2 TUI: minimal stand-in server API

Source: opencode v2.0.29 (tag `042d083`, github.com/anomalyco/opencode),
read from a sparse checkout on 2026-10-16. All citations are `path:line`
relative to `packages/` at that tag. Static reading only; nothing was run.
The server built from it is `hobbes.serve` (DEC-013); its first slice was
checked against the real TUI.
`packages/server` (the real HTTP server) is NOT in the sparse checkout, so server-side framing
details are inferred from the client and the TUI's own test fake server (marked where so).

Goal: a Python HTTP+SSE server that the unmodified `opencode2 --server URL` TUI can drive,
backed by our ACP-shaped agent (TextChunk / ThoughtChunk / ToolCall / ToolCallUpdate / Plan /
permission requests / TurnEnded).

---

## 0. Best schema sources (for Pydantic / TypedDict generation)

| Source | What it gives | Use |
|---|---|---|
| `packages/protocol/openapi.json` (578 KB, 139 ops, 285 component schemas) | Full OpenAPI 3 of the v2 HTTP API incl. the SSE event union (`V2Event`) | Feed to `datamodel-code-generator` for Pydantic v2 models. Best single source. |
| `packages/client/src/promise/generated/types.ts` (6830 lines) | The *JSON wire* shapes as TS types (dates already as epoch-ms numbers, optional fields marked `?`) | Easiest to read by hand; hand-write TypedDicts from it. |
| `packages/client/src/promise/generated/client.ts` | Exact method, path, query, body fields, success status, `{data}` unwrapping for every call | The request contract (see §2). |
| `packages/schema/src/*.ts` (Effect Schema) | Canonical definitions: `session-event.ts` (all `session.*` events), `session-message.ts` (history items), `session.ts` (Session.Info), `permission.ts`, `session-inbox.ts`, `session-status-event.ts`, `event.ts` (envelope), `identifier.ts` (ID format) | Ground truth when generated types are ambiguous. |
| `packages/protocol/src/groups/*.ts` | Endpoint definitions (Effect HttpApi) | Which errors each endpoint declares. |
| `packages/tui/test/fixture/tui-client.ts:69-171` | **The TUI's own fake server** used in its tests: the minimal set of stub responses the TUI needs to boot | Copy this list. It is the closest thing to an official "minimal server". |

**Important:** the TS client does **no runtime schema validation** of responses or events. It
checks status code + content-type, `JSON.parse`s, and casts
(`client/src/promise/generated/client.ts:352-363`, `:2273-2292`, SSE `:395-409`). So a missing
field does not fail decoding; it fails (or silently misrenders) only where the TUI reads it.
"Required" below means "the TUI reads it or the schema requires it; send it".

---

## 1. Transport rules that apply to every endpoint

- **Base URL**: `--server URL`; any path prefix on it is kept (paths are joined relative,
  `client.ts:305-309`).
- **Auth**: if `OPENCODE_PASSWORD` (fallback legacy `OPENCODE_SERVER_PASSWORD`) is set in the TUI's
  env (`cli/src/env.ts:10-13`), every request including `GET /api/event` carries
  `authorization: Basic base64("opencode:" + password)`. Username is hard-coded `opencode`
  (`cli/src/services/server-connection.ts:25-29`; header built at `client/src/service-probe.ts:93-98`;
  passed to `OpenCode.make` at `tui/src/app.tsx:216-217`). With no env var, no header is sent.
  To reject: `401` with JSON `{"_tag":"UnauthorizedError","message":"..."}` (the CLI then prints
  "requires a password; set OPENCODE_PASSWORD" / "rejected the password",
  `server-connection.ts:85-97`).
- **Success status must match exactly** (`client.ts:354`): 200 for JSON bodies, 204 for empty ones
  (table in §2). A 200 where 204 is expected is an error (`UnexpectedStatus`).
- **Content-Type** for JSON responses must be `application/json` (or `*+json`), and the body
  non-empty (`client.ts:2273-2292`). SSE must be `text/event-stream` (`client.ts:369-374`).
- **Errors**: only the endpoint's *declared* statuses (usually 400/401/404, sometimes 409/500/503)
  have their JSON body parsed into an Error whose `name` = body `_tag`; anything else becomes
  `ClientError("UnexpectedStatus")` (`client.ts:343-350`, `:2294-2305`). Error body shape:
  `{"_tag": "SessionNotFoundError", "message": "...", ...}`; tags and statuses in
  `protocol/src/errors.ts` (e.g. SessionNotFoundError 404, InvalidRequestError 400,
  ConflictError 409, ServiceUnavailableError 503).
- **Location query param**: location-scoped GETs send the location as a deep-object query:
  `?location[directory]=%2Fabs%2Fpath` (`client.ts:2256-2271`). The TUI only ever sends
  `directory` (`client/src/solid/data.ts:140-142`).
- **Location echo rule (tricky)**: location-scoped list responses are `{location:{directory}, data}`.
  The data layer caches the list under the key built from the **response's** `location.directory`
  (`data.ts:1346-1365`); only `model` and `provider` are also aliased under the requested key
  (`data.ts:1984-1985`). The TUI then reads the list under its own location key. So
  **`location.directory` in every response must equal the requested `location[directory]`
  byte-for-byte** (do not realpath/normalize it), otherwise e.g. the agent list is "missing" and
  the prompt refuses to submit.
- **Body encoding**: JSON (`content-type: application/json`); fields that are `undefined` in TS are
  omitted by `JSON.stringify`, but nullable fields may arrive as `null`.

---

## 2. Endpoint list (minimal surface)

Legend: **FATAL** = failure kills startup or the flow; **SOFT** = failure is caught/logged and the
TUI continues (possibly with an empty panel); **NOT CALLED** in these flows.

Response wrappers differ per endpoint; the "Body" column is literal (some return `{data: X}` and
the client unwraps `.data`, `client.ts` lines noted).

### 2.1 Startup

| # | Method + path | Status | Response body | Notes / failure |
|---|---|---|---|---|
| S1 | `GET /api/info` | 200 | `ServerInfo` `{"version":"2.0.29","pid":0,"urls":[],"paths":{"tmp":"/tmp"},"capabilities":{"persistentPty":false}}` | First request, 5 s timeout. **FATAL** on transport error / non-200 / non-JSON (`server-connection.ts:30-34`, `:85-97`). Only `version` is read; a mismatch with the client's version prints a stderr warning and continues (`:35-38`). `capabilities` optional (`protocol/src/groups/server.ts:81-86`). Send `version: "2.0.29"` to avoid the warning. |
| S2 | `GET /api/fs/list?location[directory]=<cwd>` | 200 | `{"location":{"directory":"<cwd>"},"data":[]}` | Called before the renderer starts to resolve the working location (`tui/src/app.tsx:218-222`). If it fails, falls back to S3 without a location param; if **both** fail, **FATAL** (the `Effect.tryPromise` fails the TUI run). `data` items: `{path: relative, type: "file"|"directory"}` (`types.ts:401`). Also used by the file-mention autocomplete. |
| S3 | `GET /api/location[?location[directory]=…]` | 200 | `{"directory":"<dir>","project":{"id":"prj_x","directory":"<dir>","canonical":"<dir>"}}` (`LocationPublicInfo`, `types.ts:315-318`) | Called on every `server.connected` (`data.ts:656-663`) and by `location.syncInfo` (`data.ts:1922-1933`), which **sets the TUI's default location to `directory`** — echo the requested directory (or cwd when absent). `project.id` is used as `projectID` for optimistic sessions (`data.ts:1531`). |
| S4 | `GET /api/event` | 200 SSE | see §3 | **FATAL-ish**: the TUI reconnects forever every 1 s; nothing live works without it. First frame must be `server.connected` within 2 s (`client/src/solid/connection.ts:32`, `:81`, `:106-107`). |
| S5 | `GET /api/session/active` | 200 | `{"data":{"ses_…":{"type":"running"}}}` (empty `{"data":{}}` when idle) | On every `server.connected` (`data.ts:638-655`); SOFT (`.catch`). Seeds the "running" status that enables the interrupt key. |
| S6 | `GET /api/project` | 200 | `[]` or `[Project]` (bare array, `types.ts:709-718`, `:6158`) | On `server.connected` (`data.ts:665`, `:1875-1880`); SOFT. |
| S7 | `GET /api/vcs?location[directory]=…` | 200 | `{"location":{…},"data":{"branch":{"current":"main"}}}` (`VcsInfo`, `types.ts:845`) | On `server.connected` (`data.ts:664`); SOFT. |
| S8 | `GET /api/plugin?location[directory]=…` | 200 | `{"location":{…},"data":[]}` | `tui/src/plugin/context.tsx:539-570`; SOFT (`.catch(() => undefined)`). Server-listed plugins are loaded in the TUI process only if present locally; return `[]`. |
| S9 | `GET /api/agent?location[directory]=…` | 200 | `{"location":{…},"data":[AgentInfo]}` | **Required for a usable prompt**: needs ≥1 agent with `mode` `"primary"` or `"all"` and `hidden:false` (`tui/src/context/local.tsx:57-59`, `:86-97`); otherwise submit silently returns (`component/prompt/index.tsx:1160-1161`). See §4. |
| S10 | `GET /api/model?location[directory]=…` | 200 | `{"location":{…},"data":[ModelInfo]}` | **Required for a usable prompt**: ≥1 model; selection must match a listed `(providerID, id)` (`local.tsx:45-47`, `:181-206`, `:360-362`); else "Connect a provider" / "Model unavailable" toast (`prompt/index.tsx:1162-1173`). See §4. |
| S11 | `GET /api/provider?location[directory]=…` | 200 | `{"location":{…},"data":[ProviderInfo]}` | Display name for the model footer (`local.tsx:396-411`). Empty list is OK (falls back to `providerID`). |
| S12 | `GET /api/command`, `/api/skill`, `/api/integration`, `/api/reference`, `/api/mcp`, `/api/shell`, `/api/form` (all `?location[directory]=…`) | 200 | `{"location":{…},"data":[]}`; `/api/mcp/resource` → `{"location":{…},"data":{"resources":[],"templates":[]}}` | Catalogs loaded by `location.sync` (`data.ts:1934-1951`, a `Promise.all`). **Any failure here disables the session prompt** (§2.5). Stub them all with empty lists; the TUI fake server does exactly this (`tui/test/fixture/tui-client.ts:122-165`). Optional extras the fake server also stubs: `/api/permission/request`, `/api/websearch/provider`. |
| S13 | `GET /api/config?location[directory]=…` | 200 | `[]` (bare array of `ConfigEntry`) | Part of the TUI's location bundle: `Promise.all([data.location.sync(ref), data.location.config.sync(ref)])` (`tui/src/context/data.tsx:27-29`). Used for the configured default model (`local.tsx:170-179`). The TUI does NOT read its own settings from here (it reads local `cli.json`). |
| S14 | `GET /api/experimental/migration/v1` | 200 | `{"status":"completed"}` | Polled 1 s after mount, every 1 s until `completed` (`tui/src/component/migration-overlay.tsx:17-38`). `"error"` or a failed request → toast "Data migration failed" and stop (SOFT); any other status polls forever. |
| S15 | `GET /api/worktree?projectID=…` | 200 | `[{"directory":"<dir>"}]` | Stubbed by the fake server (`tui-client.ts:116-120`); used by the project/worktree UI. |

### 2.2 Create a session

`POST /api/session` → **200** `{"data": SessionInfo}` (`client.ts:578-598`; protocol
`groups/session.ts:221-243`).

Request body (all optional, nullable; `types.ts:3064-3078`):
```json
{
  "id": "ses_…",                 // client-minted; USE IT as the session id (data.ts:1523, :1548)
  "location": {"directory": "/abs/dir"},
  "agent": "build",
  "model": {"providerID": "hobbes", "id": "claude", "variant": null},
  "title": null, "parentID": null, "metadata": null, "permissions": null
}
```
Response `SessionInfo` (`types.ts:2091-2108`, schema `schema/src/session.ts:47-75`):
```json
{"data": {
  "id": "ses_…", "projectID": "prj_x",
  "agent": "build", "model": {"providerID": "hobbes", "id": "claude"},
  "cost": 0, "tokens": {"input":0,"output":0,"reasoning":0,"cache":{"read":0,"write":0}},
  "time": {"created": 1760000000000, "updated": 1760000000000},
  "title": "New session",
  "location": {"directory": "/abs/dir"}
}}
```
Required: `id, projectID, cost, tokens, time.created, time.updated, location`. Optional:
`parentID, fork, agent, model, outcome, time.idle|viewed|archived, title, subpath, metadata,
permissions, revert`.

The TUI creates sessions **optimistically** (renders immediately under its own id) and gates the
prompt on this request (`data.ts:1507-1562`; `prompt/index.tsx:1231-1270`). Failure: toast
"Creating a session failed", rollback (FATAL for that submit only).

Then emit `session.created` on the stream (recommended; §3.5). Without it the create response
alone acknowledges the session (`data.ts:1549-1552`), but `session.created` is what marks the
new session's message/pending lists as "complete" so the view does not race an empty GET
(`data.ts:671-681`).

Possible follow-up call: `PUT /api/session/{id}/environment` body `{"variables":{…}}` → **204**,
only when the TUI has terminal env vars to forward (`prompt/index.tsx:1247-1251`). With
`--server` the CLI does not forward the local env (subagent report, `cli/src/commands/handlers/default.ts:143`);
**unverified** whether `terminalEnvironment.variables` is then `undefined`. Implement as a 204 no-op.

### 2.3 Send a prompt

Sequence the TUI performs for a normal prompt (`prompt/index.tsx:1273-1365`, `data.ts:1611-1655`):

1. `GET /api/session/{id}` if the session is not cached (`prepareAgent`, `:1275-1279`).
2. `POST /api/session/{id}/agent` body `{"agent":"build"}` → **204**, only if `session.agent !== selected agent` (`:1279-1281`). Emit `session.agent.selected` if it changed.
3. `POST /api/session/{id}/model` body `{"model":{"providerID":"…","id":"…","variant":…}}` → **204**, **always** before each prompt (`prepare: commitModel`, `:1285-1290`, `:1366`). Server should no-op when unchanged ("the server makes an unchanged selection a no-op", `:1364-1365`). Failure aborts the prompt ("Failed to switch model"). Emit `session.model.selected` only when it changed.
4. `POST /api/session/{id}/prompt` → **200** `{"data": SessionInboxUser}` (`client.ts:716-736`).

Prompt request body (`types.ts:4290-4312`; protocol `groups/session.ts:396-416`):
```json
{
  "id": "msg_…",            // client-minted msg_ id; MUST be used as the inbox/user-message id
  "text": "hello",
  "files": [{"uri": "file:///abs/a.py" | "data:image/png;base64,…", "name": "a.py", "description": "…", "mention": {"start":0,"end":5,"text":"@a.py"}}],
  "agents": [{"name": "general", "mention": {…}}],
  "skills": [{"id": "…", "mention": {…}}],
  "metadata": {…},
  "delivery": "steer" | "queue",   // default steer
  "resume": true | false           // default true: schedule execution
}
```
Note: **no agent/model in the prompt body**; they are session state set by steps 2-3.

Response (`types.ts:2322-2329`, `:922-928`):
```json
{"data": {"id":"msg_…","sessionID":"ses_…","time":{"created":1760000000000},
          "type":"user","delivery":"steer",
          "payload":{"text":"hello","files":[…],"agents":[…],"skills":[…],"metadata":{…}}}}
```
Errors declared: 400, 401, 404, 409. The TUI admits the user message optimistically and rolls it
back if this call fails (`data.ts:1606-1655`). The retry contract is "idempotent per id"
(`data.ts:1608-1610`): a repeat POST with the same `id` must not double-admit.

Then emit, in order: `session.inbox.enqueued` → `session.execution.started` →
`session.inbox.delivered` → assistant step events → `session.execution.succeeded` (§3.6).

### 2.4 Permission reply, interrupt, list/reopen

| Method + path | Status | Body / response | Notes |
|---|---|---|---|
| `POST /api/session/{id}/permission/{requestID}/reply` | **204** | body `{"decision":"once"\|"always"\|"reject","message":"optional reject reason"}` (`client.ts:1603-1614`, `types.ts:6290-6301`) | Called from the permission prompt (`routes/session/permission.tsx:136-140`). The TUI removes the prompt locally after success **or** after a 404 whose `_tag` is the permission-not-found error (`data.ts:1809-1816`); other errors toast. Also emit `permission.replied`. |
| `GET /api/session/{id}/permission` | 200 | `{"data":[PermissionRequest]}` | Sync of pending requests for a session (`data.ts:1801-1805`); fake server stubs `{"data":[]}` (`tui-client.ts:149`). Return currently pending requests so a reopened session shows them. |
| `POST /api/session/{id}/interrupt?resume=true` | **200** | `{"interrupted": true\|false}` (NOT wrapped in data; `client.ts:979-990`) | Escape pressed twice while `status === "running"` (`prompt/index.tsx:499-528`). The return value is not awaited for UI; state changes come from events. Then emit tool failures for unfinished tools and `session.execution.interrupted` `{reason:"user"}`. |
| `GET /api/session?…` | 200 | `{"data":[SessionInfo],"cursor":{"previous":null,"next":null}}` (NOT unwrapped; `SessionsResponse`, `types.ts:2378-2381`) | Session list dialog / children. Query (all optional, strings): `limit` (default 50), `order` `asc\|desc`, `search`, `parentID` (`"null"` = roots only), `directory`, `project`, `subpath`, `cursor` (`groups/session.ts:48-72`, `:156-162`). Cursor is opaque; returning `next: null` ends paging (`data.ts:528-534`). |
| `GET /api/session/{id}` | 200 | `{"data": SessionInfo}` | Reopen / refresh (`data.ts:1656-1677`). 404 `{"_tag":"SessionNotFoundError","sessionID":…,"message":…}`. |
| `GET /api/session/{id}/message?limit=20&order=desc[&cursor=…]` | 200 | `{"data":[SessionMessageInfo],"cursor":{"previous":null,"next":null\|"opaque"}}` (NOT unwrapped; `types.ts:2486-2489`) | Transcript load: first page newest-first, the client reverses it (`data.ts:1690-1716`). `loadMore` passes `cursor` (no `order`) and expects older items, still newest-first (`data.ts:1723-1787`). `limit` 1..200 (`groups/message.ts:8-13`). |
| `GET /api/session/{id}/inbox` | 200 | `{"data":[SessionInboxInfo]}` | Pending (not yet delivered) prompts (`data.ts:1465-1502`); return `{"data":[]}` when nothing is queued. |
| `GET /api/session/{id}/message/{messageID}` | 200 | `{"data": SessionMessageInfo}` | Only fetched after `session.model.selected` (`data.ts:717-727`). Return the `model-switched` message or 404 (SOFT). |
| `POST /api/session/{id}/view` | 204 | body `{"idle": <epoch ms>}` | Marks idle as viewed. **Unverified** whether called on reopen; 204 no-op is safe. |
| `GET /api/session/{id}/form` | 200 | `{"data":[]}` | Pending forms; stub. |
| `GET /api/experimental/session/{id}/terminal` | 200 | `{"data":[]}` | Persistent terminals; stub (`tui-client.ts:151`). |

### 2.5 Startup call failure handling (summary)

- **Process-fatal**: S1 `/api/info` (CLI exits); S2 **and** S3 both failing (`app.tsx:218-222`);
  `GET /api/session/{id}` failing with anything but `SessionNotFoundError` when started with
  `-s <id>` (subagent: `cli/src/commands/handlers/default.ts:55-61`, `cli/src/session-target.ts:134-139`).
- **Effectively mandatory**: S4 SSE. Almost every data load waits for connection status
  "connected" (`tui/src/context/location.tsx:44-48`, `routes/session/rows.ts:119-121`); a
  "Reconnecting" overlay appears after a few seconds disconnected (subagent: `app.tsx:1337-1356`).
- **Location bundle (S3 + S7, S9-S13) — treat ALL as mandatory.** It is one `Promise.all`
  (`client/src/solid/data.ts:1934-1951` + config, `tui/src/context/data.tsx:27-29`); any single
  rejection sets `location.error` (`tui/src/context/location.tsx:22-40`), and on a session route
  the prompt is **replaced** by the "location missing / move session" view
  (`routes/session/index.tsx:1512-1524`), so you cannot submit. A 404 from any of these
  (e.g. `/api/integration` unimplemented) therefore breaks the session screen. Endpoints in it:
  `/api/location`, `/api/vcs`, `/api/agent`, `/api/command`, `/api/integration`, `/api/mcp`,
  `/api/mcp/resource`, `/api/model`, `/api/provider`, `/api/reference`, `/api/skill`,
  `/api/shell`, `/api/form`, `/api/config`. It re-runs on every `server.connected`
  (`location.tsx:48`).
- **Session-route mount**: `GET /api/session/{id}` plus `GET /api/session?parentID=<id>&order=desc&limit=200`
  (children; `data.ts:1656-1661`, `:528-534`). Either failing → error toast and navigate home
  (subagent: `routes/session/index.tsx:330-360`). So `GET /api/session?parentID=…` must work
  (return `{"data":[],"cursor":{}}`).
- **SOFT (swallowed or console.error)**: `/api/session/active`, `/api/project`, `/api/plugin`,
  session `/permission`, `/form`, `/inbox`, `/message` (transcript renders empty),
  `/api/experimental/session/{id}/terminal`, `/api/info` re-read on `server.connected` for
  `capabilities.persistentPty` (subagent: `tui/src/context/session-terminals.tsx:60-78`; send
  `persistentPty:false` to keep terminal panes and their WebSocket off),
  `/api/experimental/migration/v1` (toast).
- **Not called in these flows**: `/api/rpc/*` (only via plugin `client`), WebSockets (only
  persistent-pty panes, `client/src/solid/pty.ts:44-64`), `/api/permission/request` (stubbed by
  the fake server but no TUI call site found by the subagent), `/api/websearch/provider` (only on
  `config.updated`/`websearch.updated` events, `data.ts:1320-1328`).

---

## 3. The event stream: `GET /api/event`

### 3.1 Framing

- Response: `200`, `content-type: text/event-stream`. Keep the connection open.
- Each event: **one `data:` line with the JSON envelope, then a blank line**:
  `data: {"id":"evt_…","type":"…",…}\n\n`. The client joins all `data:` lines of a block, ignores
  `event:`, `id:`, `retry:` and comment lines (`client.ts:395-409`). Do not send `event:` names
  that you expect to matter; they are ignored.
- **Heartbeat**: any bytes reset the 45 s idle watchdog (`connection.ts:22-25`, `:35`, `:84-92`);
  the real server sends a comment every 15 s (`connection.ts:23`). Send `: keepalive\n\n` every
  ~15 s. A comment-only block yields no event (`data === ""` is skipped, `client.ts:403`).
- **First event** must be `server.connected` and must arrive within **2 s** of the request
  (`connection.ts:32`, `:81`, `:98-109`); otherwise the client aborts and reconnects. Shape:
  `{"id":"evt_…","type":"server.connected","data":{}}` (`protocol/src/groups/event.ts:27-35`;
  fake server uses `{"id":"evt_connected","type":"server.connected","data":{}}`,
  `tui-client.ts:58`). Flush it immediately.
- **No replay / no Last-Event-ID**: the stream is "volatile by contract … events during
  disconnection are missed" (`groups/event.ts:49-52`). The client never sends `Last-Event-ID`;
  reconnect is a fresh `GET` after 1 s (`connection.ts:33`, `:147-183`). On every reconnect the
  data layer re-reads state via HTTP (`server.connected` handler, `data.ts:635-666`; cached reads
  are invalidated while disconnected, `data.ts:2002-2005`; the session view re-syncs messages and
  pending inputs on reconnect, `routes/session/rows.ts:119-141`). So **HTTP reads must be able to
  reconstruct everything** (messages, pending inbox, active status, pending permissions).
- Max single SSE event size 16 MiB (`client.ts:300`, `:389`). The client buffers per subscriber up
  to 4096 events (`shared-events.ts:25`, `:97-99`).
- Events are batched into the UI every ~10 ms (`connection.ts:65-74`); order is preserved.

### 3.2 Envelope

From `schema/src/event.ts:67-78`, `:90-150`:
```json
{
  "id": "evt_<26 chars>",          // required, must start with "evt_"
  "type": "session.text.delta",    // required
  "created": 1760000000000,         // required (epoch ms); NOT on server.connected
  "data": { … },                    // required, per type
  "location": {"directory": "/abs"},// optional; REQUIRED for location-scoped catalog events (agent.updated etc., data.ts:1250)
  "metadata": { … },                // optional
  "durable": {"aggregateID": "ses_…", "seq": 0, "version": 1}  // only on durable types
}
```
- `durable` is present on durable event types (schema `event.ts:94-116`). The TUI data layer only
  reads it for debug logging (`connection.ts:127-132`), so it can be omitted, but sending it costs
  nothing: `aggregateID` = sessionID, `seq` = per-session counter from 0, `version` = 1 (2 for
  `session.tool.success`, `session.tool.failed`, `session.deleted`, `session.forked`,
  `session.instructions.updated`; `session-event.ts:177-200`, `:261-277`, `:530-566`).
  Ephemeral types (no `durable`): `session.text.delta`, `session.reasoning.delta`,
  `session.tool.input.delta`, `session.tool.progress`, `session.usage.updated`,
  `session.compaction.delta`, `session.status`, `session.idle`, `permission.asked`,
  `permission.replied`, `tui.*`.
- **Event ids are used as message ids**: for several types the data layer derives a transcript
  message id as `evt_X → msg_X` (`data.ts:83`, used for `idle`, `agent-switched`,
  `model-switched`, `synthetic`, `system`, `shell`, `location-switched`, compaction). So use the
  same 26-char suffix format for both, and if your history endpoint returns e.g. the `idle`
  marker, give it id `msg_<suffix of the execution.* event>` so live and reloaded rows dedupe.

### 3.3 ID formats (`schema/src/identifier.ts:9-32`)

`prefix + 12 hex chars (48-bit: ms_timestamp*4096 + counter) + 14 chars [0-9A-Za-z]` = 26 chars
after the prefix. Ascending ids sort by creation time; session ids use the bitwise-inverted
("descending") variant so newer sessions sort first.

| Kind | Prefix check (schema) | Generator |
|---|---|---|
| Event | starts with `evt_` (`event.ts:9`) | ascending |
| Session | starts with `ses` (`session-id.ts:5`) | `ses_` + descending |
| Message / inbox item | starts with `msg_` (`session-message.ts:23`) | ascending |
| Permission request | starts with `per` (`permission.ts:10`) | `per_` + ascending |
| Form | `frm_`; Shell `sh_`; Pty `pty`; Workspace `wrk` | |
| Project | `project-id.ts` (no prefix check found; fake server uses `proj_test`) | |
| Tool call id (`data.id` on tool events) | any string, unique within the assistant message | |

Prefix checks are server-side decoding only (the TS client never validates), but the TUI mints
`ses_`/`msg_` ids itself and sends them to you (`data.ts:1523`, `:1613`). Accept and reuse them.
Ordering matters in two places: `session.revert.committed` filtering uses string comparison
`item.id < to` (`data.ts:1126-1136`), and message ids should be ascending in time so history
pages are consistent. Python generator:

```python
import secrets, string, time
_ALPH = string.digits + string.ascii_uppercase + string.ascii_lowercase
_last, _ctr = 0, 0
def _ident(descending=False):
    global _last, _ctr
    now = int(time.time() * 1000)
    _ctr = _ctr + 1 if now == _last else 1; _last = now
    v = now * 0x1000 + _ctr
    if descending: v = ~v
    t = "".join(f"{(v >> (40 - 8 * i)) & 0xFF:02x}" for i in range(6))
    return t + "".join(_ALPH[b % 62] for b in secrets.token_bytes(14))
evt_id = lambda: "evt_" + _ident(); msg_id = lambda: "msg_" + _ident()
ses_id = lambda: "ses_" + _ident(True); per_id = lambda: "per_" + _ident()
```

### 3.4 How the data layer applies events (the constraints)

All handlers are in `client/src/solid/data.ts:633-1341`. Session events are applied regardless
of `location`; catalog events (`agent.updated`, `model.updated`, …) are ignored without
`location` (`data.ts:1250`).

**Assistant content is addressed, not created, by most events.** `editAssistant` finds the
assistant message by `assistantMessageID`; if it is not in the transcript the event is
**dropped** (`data.ts:467-475`). Within a message:

- `session.text.delta` / `.ended` edit the **last** `text` part (`data.ts:484-489`, `:952-961`);
  only `session.text.started` creates one (`:947-951`). Delta before started = dropped.
- `session.reasoning.delta` / `.ended` edit the last reasoning part **that is not completed**
  (`:490-497`, `:1035-1046`); `.started` creates it (`:1025-1034`).
- `session.tool.input.started` creates a tool part `{status:"streaming", input:""}`
  (`:962-972`); `input.delta`/`input.ended` only apply while streaming (`:973-982`);
  `session.tool.called` turns it into `{status:"running", input:<object>, metadata:{}}`
  (`:983-990`); `session.tool.progress` replaces `metadata` while running (`:991-995`);
  `session.tool.success` only applies when **running** (`:996-1009`), `session.tool.failed`
  when streaming or running (`:1010-1024`). So for each tool: **input.started → called →
  (progress)* → success|failed**. Skipping `called` makes `success` a no-op.
- **`ordinal` matters for rendering.** The session view keys live rows as `text:<ordinal>` /
  `reasoning:<ordinal>` and resolves them as "the N-th text (or reasoning) part of the message"
  (`routes/session/rows.ts:274-295`, `:393-398`, `:531-538`). So `ordinal` = 0-based index of
  that part **among parts of the same type** in that assistant message (text and reasoning
  counted separately). Tool rows are keyed by the tool `id` (`rows.ts:296-301`).
- A text/reasoning row is only added live when a delta/ended has non-whitespace text
  (`rows.ts:274-295`).
- `session.step.started` appends a new assistant message `{id: assistantMessageID, agent, model,
  content: [], time.created: data.started}` (or resets an existing one) and marks the previous
  open assistant message completed (`data.ts:881-915`).
- `session.step.ended` sets `time.completed`, `finish`, `cost`, `tokens` (`data.ts:921-931`). The
  view shows the per-message footer unless `finish` is `"tool-calls"` or `"unknown"`
  (`rows.ts:309-313`).
- **Session status / interrupt key**: `session.execution.started` sets the session "running"
  (`data.ts:1052-1054`); `succeeded|failed|interrupted` set "idle", append an `idle` transcript
  marker `{id: msg_<evt suffix>, type:"idle", outcome, error?}` (failed shows "Error: …",
  `routes/session/index.tsx:1847-1849`), and if any tool is still streaming/running they
  re-fetch the message list (`data.ts:1068-1107`). The interrupt command is enabled only when
  status is running (`prompt/index.tsx:504`). `session.status` (busy/idle/retry) is in the
  public union but **not consumed by the v2 data layer** (no handler in `data.ts`); optional.
- **Pending prompt rows**: a user prompt stays "pending" (rendered in the queued area at the
  bottom) while it is in `store.session.pending`; it leaves pending only on
  `session.inbox.delivered` (or `cancelled`) (`data.ts:792-807`, `rows.ts:236-247`). On
  delivery the row's `time.created` becomes the event time and it moves to the end of the
  transcript (`data.ts:795-804`). **Emit `inbox.delivered` before the first `step.started`**,
  otherwise assistant rows are inserted above a still-pending prompt (`rows.ts:242-247`).
- `session.inbox.enqueued` upserts the inbox item under `inboxID` (same id the client minted)
  and clears its optimistic "outbox" flag (`data.ts:816-833`); the session view also appends
  the user row on this event (`rows.ts:248-262`).
- `permission.asked` appends to the session's pending permissions (deduped by `id`);
  `permission.replied` removes it (`data.ts:1205-1214`).
- `session.created` re-reads `GET /api/session/{id}` and marks the new session's pending/message
  lists as complete (`data.ts:671-681`). `session.deleted` removes everything (`:682-684`).
- `session.renamed` refreshes the session then sets `title` (`:730-742`).
- `session.usage.updated` sets session `cost`/`tokens` (`:685-691`).
- `tui.toast.show` shows a toast (`tui/src/app.tsx:1299`); `tui.session.select` navigates
  (`app.tsx:1309`). Useful for out-of-band notices.

### 3.5 Payload schemas (data field) for the events we need

Types abbreviated: `SID`=session id, `MID`=`msg_` id, `ms`=epoch-ms int, `ModelRef`=
`{"id":str,"providerID":str,"variant"?:str}`, `Tokens`=`{"input","output","reasoning","cache":{"read","write"}}`
(ints), `Err`=`{"type":str,"message":str,"status"?:int,"response"?:{"body":str}}`
(`types.ts:111`), `ToolContent`=`{"type":"text","text":str}` or
`{"type":"file","uri":str,"mime":str,"name"?:str}` (`types.ts:107-109`).
Source: `schema/src/session-event.ts` (line refs) and `types.ts`.

| type | durable | data | src |
|---|---|---|---|
| `server.connected` | – | `{}` (no `created` needed) | `groups/event.ts:27-35` |
| `session.created` | v1 | `{sessionID, projectID, location:{directory}, slug:str, version:str, subpath?, parentID?, title?, agent?, model?:ModelRef, metadata?, permissions?}` | `:48-66` |
| `session.renamed` | v1 | `{sessionID, title}` | `:101-108` |
| `session.agent.selected` | v1 | `{sessionID, agent, previous?}` | `:69-77` |
| `session.model.selected` | v1 | `{sessionID, model:ModelRef, previous?:ModelRef}` | `:80-88` |
| `session.deleted` | **v2** | `{sessionID}` | `:177-184` |
| `session.usage.updated` | eph | `{sessionID, cost:float, tokens:Tokens}` | `:167-174` |
| `session.inbox.enqueued` | v1 | `{sessionID, inboxID:MID, item:{"type":"user","delivery":"steer"\|"queue","payload":{text, files?, agents?, skills?, metadata?}}}` | `:215-222`, `session-inbox.ts:150-185` |
| `session.inbox.delivered` | v1 | `{sessionID, inboxID}` | `:208-212` |
| `session.inbox.cancelled` | v1 | `{sessionID, inboxID}` | `:225-229` |
| `session.execution.started` | v1 | `{sessionID}` | `:240` |
| `session.execution.succeeded` | v1 | `{sessionID}` | `:243` |
| `session.execution.failed` | v1 | `{sessionID, error:Err}` | `:246-250` |
| `session.execution.interrupted` | v1 | `{sessionID, reason:"user"\|"shutdown"\|"superseded"\|"inactivity"}` (`shutdown` adds no idle marker, `data.ts:1076`) | `:253-257` |
| `session.step.started` | v1 | `{sessionID, assistantMessageID:MID, agent:str, model:ModelRef, started:ms, snapshot?}` | `:329-341` |
| `session.step.streamed` | v1 | `{sessionID, assistantMessageID}` (optional; sets `time.streamed`) | `:345-352` |
| `session.step.ended` | v1 | `{sessionID, assistantMessageID, finish:"stop"\|"length"\|"tool-calls"\|"content-filter"\|"error"\|"unknown", cost:float, tokens:Tokens, rawFinish?, providerState?, snapshot?, files?}` | `:355-369` |
| `session.step.failed` | v1 | `{sessionID, assistantMessageID, error:Err, finish?:"content-filter", rawFinish?, cost?, tokens?, …}` | `:372-388` |
| `session.text.started` | v1 | `{sessionID, assistantMessageID, ordinal:int}` | `:392-400` |
| `session.text.delta` | eph | `{sessionID, assistantMessageID, ordinal, delta:str}` | `:404-412` |
| `session.text.ended` | v1 | `{sessionID, assistantMessageID, ordinal, text:<full text>, state?}` | `:415-425` |
| `session.reasoning.started` | v1 | `{sessionID, assistantMessageID, ordinal, state?}` | `:430-439` |
| `session.reasoning.delta` | eph | `{sessionID, assistantMessageID, ordinal, delta}` | `:443-451` |
| `session.reasoning.ended` | v1 | `{sessionID, assistantMessageID, ordinal, text:<full>, state?}` | `:454-464` |
| `session.tool.input.started` | v1 | `{sessionID, assistantMessageID, id:str, name:str}` | `:476-483` |
| `session.tool.input.delta` | eph | `{sessionID, assistantMessageID, id, delta:str}` (optional) | `:487-493` |
| `session.tool.input.ended` | v1 | `{sessionID, assistantMessageID, id, text:<raw input JSON string>}` (optional) | `:496-503` |
| `session.tool.called` | v1 | `{sessionID, assistantMessageID, id, input:{…object…}, executed:bool, state?}` | `:507-516` |
| `session.tool.progress` | eph | `{sessionID, assistantMessageID, id, metadata:{…json…}}` (replaces metadata) | `:520-526` |
| `session.tool.success` | **v2** | `{sessionID, assistantMessageID, id, content:[ToolContent, …] (NON-EMPTY), executed:bool, metadata?, resultState?}` | `:530-543` |
| `session.tool.failed` | **v2** | `{sessionID, assistantMessageID, id, error:Err, executed:bool, content?:[…non-empty…], metadata?, resultState?}` | `:551-566` |
| `session.synthetic` | v1 | `{sessionID, text, description?, metadata?}` (visible notice row only if `description` non-blank, `rows.ts:267-270`; renders `description`, `index.tsx:1988-1992`) | `:279-288` |
| `permission.asked` | eph | `PermissionRequest`: `{id:"per_…", sessionID, action:str, resources:[str], save?:[str], metadata?, source?:{"type":"tool","messageID":MID,"id":<tool id>}, message?}` | `schema/src/permission.ts:26-45` |
| `permission.replied` | eph | `{sessionID, requestID, reply:"once"\|"always"\|"reject"}` | `permission.ts:46-53` |
| `session.status` | eph | `{sessionID, status:{"type":"idle"}\|{"type":"busy"}\|{"type":"retry",attempt,message,next,action?}}` (optional, not used by data layer) | `session-status-event.ts:91-125` |
| `tui.toast.show` | eph | `{message, variant:"info"\|"success"\|"warning"\|"error", title?, duration?}` | `types.ts:1782-1794` |

### 3.6 Canonical turn sequence (ACP mapping)

```
POST /prompt (id=msg_U)            -> 200 {"data": inbox item msg_U}
evt session.inbox.enqueued      {inboxID: msg_U, item:{type:user,delivery:steer,payload:{text}}}
evt session.execution.started   {sessionID}
evt session.inbox.delivered     {inboxID: msg_U}
evt session.step.started        {assistantMessageID: msg_A, agent, model, started}
  ThoughtChunk(first)  -> session.reasoning.started {ordinal:r}; then .delta {ordinal:r, delta}
  TextChunk(first)     -> (close open reasoning: session.reasoning.ended {ordinal:r, text:full})
                          session.text.started {ordinal:t}; then .delta {ordinal:t, delta}
  ToolCall(id,title,kind,status)
                       -> (close open text: session.text.ended {ordinal:t, text:full})
                          session.tool.input.started {id, name}
                          session.tool.called {id, input:{…raw_input or {title}…}, executed:true}
  ToolCallUpdate(in_progress, content) -> session.tool.progress {id, metadata:{…}}
  ToolCallUpdate(completed, content)   -> session.tool.success {id, content:[{type:text,text:…}] (non-empty!), executed:true, metadata?}
  ToolCallUpdate(failed)               -> session.tool.failed  {id, error:{type:"tool",message:…}, executed:true}
  permission request   -> evt permission.asked {id: per_P, sessionID, action, resources, save?, source:{type:tool,messageID:msg_A,id:<toolCallId>}}
                          (user) POST …/permission/per_P/reply {decision}
                          evt permission.replied {requestID: per_P, reply}
  Plan(entries)        -> no native v2 event (no todo renderer in packages/tui; grep "todo" finds
                          nothing). Options: session.synthetic with description, a generic tool
                          part (name "plan", input {entries}), or a TUI plugin panel later.
  TurnEnded(stop_reason)
                       -> close open text/reasoning (…ended)
                          fail any still-running tools (session.tool.failed)
                          session.step.ended {finish: map(stop_reason), cost:0, tokens:zeros}
                          session.execution.succeeded   (end_turn/max_tokens/refusal…)
                          or session.execution.interrupted {reason:"user"} (cancelled)
                          or session.execution.failed {error}
```

Suggested `stop_reason → finish`: `end_turn→"stop"`, `max_tokens|max_turn_requests→"length"`,
`refusal→"content-filter"`, `cancelled→"unknown"` (footer hidden) then
`execution.interrupted`.

Tool presentation (`routes/session/message-parts.tsx:21-40`, `index.tsx:2417-2470`,
`util/tool-display.ts:1-6`): names `shell`(or `bash`), `glob`, `read`, `grep`, `webfetch`,
`websearch`, `write`, `edit`, `subagent`(or `task`), `execute`, `patch`(`apply_patch`),
`question`, `skill` get dedicated renderers that read specific input keys (shell:
`input.command`, `input.workdir`, `metadata.shellID`; read: `input.path|offset|limit`; edit:
`input.path`, `metadata.files[].patch`; write: `input.path`, `input.content`). Any other name
uses `GenericTool`: one line `name [k=v, …]` from primitive input values, expandable to all
input keys plus `output` = joined text content (`index.tsx:2577-2632`). Safest ACP mapping:
`name = <kind or title slug>` with a non-reserved name, `input = raw_input`, success `content` =
ACP text content (at least one item; if ACP gave none, send `[{"type":"text","text":""}]`, see §8). Map
`kind:"execute"` → name `"bash"` with `input.command` only if raw_input has it.

Permission presentation (`tui/src/util/permission.ts:23-144`, `routes/session/permission.tsx:112-262`):
`action` selects the layout: `edit` (diff from `metadata.files[0].patch|diff` or `metadata.diff`),
`read`/`list` (`resources[0]` path), `glob`/`grep`, `shell` (`input.command` from the linked tool
part via `source`), `webfetch`, `websearch`, `external_directory`, anything else: "Call tool
<action>". Options shown: **Allow once / Always allow / Reject**, but **"Always allow" only if
`save` is non-empty** (`permission.tsx:231-239`); "always" text lists `save` patterns
(`util/permission.ts:154-160`). Reject has a second stage for an optional message
(`permission.tsx:144-154`). ACP mapping: `allow_once→"once"`, `allow_always→"always"` (send
`save:["*"]` or the paths if an allow_always option exists), `reject_once|reject_always→"reject"`.
`source.messageID/id` must point at the tool part so the prompt can show its input and the
session view can hide that tool row while pending (`rows.ts:102-117`).

---

## 4. Agent / model selection: minimal catalog data

The prompt box needs (`component/prompt/index.tsx:1160-1173`):
1. `local.agent.current()` = selected or first of agents with `mode !== "subagent" && !hidden`
   (`context/local.tsx:57-59`, `:86-97`).
2. `local.model.selection()`: first valid of (CLI `--model`, configured model from `/api/config`,
   recent models in local `state/model.json`, **first entry of `/api/model`**) (`local.tsx:181-206`);
   "valid" = present in `/api/model` by `providerID` + `id` (`:45-47`).
3. `local.model.available(selection)` = same validity check.

Minimal `GET /api/agent` item (`AgentInfo`, `types.ts:2077-2089`):
```json
{"id":"build","name":"build","mode":"primary","hidden":false,"permissions":[],
 "request":{"settings":{},"headers":{},"body":{}},
 "description":"Hobbes agent","model":{"providerID":"hobbes","id":"claude"}}
```
Required: `id, name, request{settings,headers,body}, mode, hidden, permissions`. Optional:
`model, system, description, color, steps`.

Minimal `GET /api/model` item (`ModelInfo`, `types.ts:2056-2075`):
```json
{"id":"claude","modelID":"claude","providerID":"hobbes","name":"Claude (ACP)",
 "capabilities":{"tools":true,"input":["text"],"output":["text"]},
 "variants":[],"time":{"released":0},"cost":[],"status":"active","enabled":true,
 "limit":{"context":200000,"output":32000}}
```
Note the session/model ref uses `id` (= `ModelInfo.id`), not `modelID`.
`variants: []` means no reasoning-variant cycling (`local.tsx:411`).

Minimal `GET /api/provider` item (`ProviderInfo`, `types.ts:1922-1933`):
`{"id":"hobbes","name":"Hobbes","activation":"enabled","package":"hobbes"}`.

You can expose one "model" per backend agent (claude, codex) and map `POST /model` to
"which ACP agent drives this session", or one model and use agents. Both lists are re-fetched on
`agent.updated` / `model.updated` / `provider.updated` events that carry `location`
(`data.ts:1253-1264`).

---

## 5. What the TUI does with optional endpoints that 404

A 404 is a *declared* status for most endpoints, so the client throws an Error built from the
JSON body (or `UnexpectedStatus` if the body is not JSON). Consequences follow §2.5: harmless for
the SOFT list, **breaking** for anything in the location bundle or session-route mount. Rule of
thumb: implement every endpoint in §2.1-2.4 (most as constant empty stubs); return 404 only for
genuinely absent sessions/permissions with the proper `_tag`. Anything else the TUI calls in
other UI paths (forks, revert, compaction, shell `!` mode, `/sessions` stats, MCP/integration
dialogs, file `@` mentions via `/api/fs/find`) will toast an error when used; that is acceptable
for a first slice.

Submit-time messages when catalogs are thin (`component/prompt/index.tsx:1160-1173`,
`:316-325`): no agent → submit silently does nothing; no model → toast "Connect an integration
to send prompts" and, if no `/api/integration` item has `connections.length > 0`, the
integration dialog opens; model not in list → toast "Model unavailable".

---

## 6. Local side effects of the TUI with `--server`

- **No local daemon**: with `--server` the CLI pings `/api/info` and returns the endpoint with no
  managed service (`cli/src/services/server-connection.ts:21-40`); it does not call
  `Service.ensure`/`Standalone.start`, spawn `opencode serve`, or open a database
  (`server-process.ts`/`database-path.ts` are only imported by `commands/handlers/serve.ts`,
  per subagent grep). Reconnect retries the same URL (`tui/src/context/client.tsx:26-34`, subagent).
- **Updater** still polls `https://opencode.ai/update/api/...` (~10 min); disable with
  `OPENCODE_DISABLE_AUTOUPDATE=1` (subagent: `cli/src/commands/handlers/default.ts:69-86`,
  updater `:534`).
- **Files written** (XDG; `util/src/global-roots.ts:5-19`; subagent report):
  - creates `~/.local/share/opencode`, `~/.config/opencode`, `~/.local/state/opencode`,
    `…/log`, `…/repos`, `~/.cache/opencode/bin`, `$TMPDIR/opencode`;
  - log `~/.local/share/opencode/log/opencode*.log`;
  - `~/.local/state/opencode/{prompt-history.jsonl,prompt-stash.jsonl,frecency.jsonl,model.json,session.json,locks/}`;
  - `~/.local/state/opencode/<channel>/tui/<key>.json` (tabs, layout, session-list, plugin kv);
  - `~/.config/opencode/cli.json` only on update/migration;
  - npm plugin installs under `~/.cache/opencode/npm/`.
  Overrides: `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`,
  `OPENCODE_CONFIG_DIR` (config only), `OPENCODE_TEST_HOME` (home). To sandbox, run the TUI with
  all four XDG vars pointed at a scratch dir. Note `state/model.json` "recent models" can
  pre-select a model; it must still exist in `/api/model`.
- The TUI reads its config locally (`$config/cli.json`, overlay `OPENCODE_CLI_CONFIG_CONTENT`), not
  from `/api/config` (subagent: `tui/src/app.tsx:213`, `cli/src/config/config.ts:31-40`).

## 6b. TUI plugins (for a later `session.panel`)

(Subagent report, spot-checked `plugin/context.tsx:539-570`.)
- Config: `plugins` array in `~/.config/opencode/cli.json`, items `"name"` or
  `{"package":…, "options":{…}}`; local paths `./`, `../`, absolute or `file://` (must be a
  directory), resolved relative to `cli.json` (`tui/src/config/index.tsx:47-55`, `:79-81`;
  `plugin/context.tsx:318-339`).
- Auto-discovery: every subdirectory of `~/.config/opencode/plugins/` and of `.opencode/plugins/`
  in each directory from the project root down to cwd (`tui/src/plugin/discovery.ts:8-53`);
  local sources hot-reload.
- Entry: package export `"<pkg>/tui"` or `<dir>/tui` (`plugin/src/host.ts:17-43`); default export
  `{id, setup(ctx)}` / `Plugin.define` (`plugin/src/tui/plugin.ts:7-14`); must use the host's
  `effect` and `@opencode/plugin` modules (`plugin/src/runtime.ts:28-32`).
- Context: `options, location, app, renderer, client` (full OpenCode client, so a plugin can call
  our server, incl. `rpc`), `data, theme, keymap, storage, ui` (`plugin/src/tui/context.ts:544-560`).
- Slots: `app`, `home.footer(.status)`, `prompt.footer(.status|.file)`, `session.composer.top`,
  **`session.panel`**, **`sidebar.content`**, `sidebar.footer` (`tui/context.ts:191-203`).
  `ui.panel.open(name, {presentation:"panel"|"fullscreen"})` opens `session.panel`
  (`tui/context.ts:501-508`; impl `plugin/api.tsx:230-243`; host `component/panel-host.tsx:36-37`).
  No in-tree plugin uses `session.panel`; sidebar example `feature-plugins/sidebar/context.tsx:44-52`.
- Server-listed plugins (`GET /api/plugin`) load in the TUI process only if the package/path
  exists locally; a TUI-only plugin must be configured client-side.
- Custom data for a panel can travel as `rpc.*` events on `/api/event`
  (`{type:"rpc.<x>", location:{directory}, created, data:{…}}`, `groups/event.ts:14-21`) and
  `POST /api/rpc/{rpcID}/{method}` (`client.ts:1698-1710`). **Unverified** how the plugin
  client's `rpc` helper subscribes (`client/src/promise/rpc.ts`).

---

## 7. Startup call order (as observed in source)

1. `GET /api/info` (CLI, 5 s timeout).
2. [`-s <id>` only] `GET /api/session/{id}`.
3. `GET /api/fs/list?location[directory]=<cwd>` → fallback `GET /api/location`.
4. Renderer starts; `GET /api/event` (SSE) opens; `GET /api/plugin`.
5. On `server.connected`: `GET /api/session/active`, `GET /api/location?location[directory]=…`,
   `GET /api/vcs`, `GET /api/project`, `GET /api/info` (terminal capability), `GET /api/plugin`,
   and the location bundle (§2.5).
6. +1 s: `GET /api/experimental/migration/v1` (poll until completed).
7. Home screen with prompt. Submitting → §2.2/§2.3. Session route mount → `GET /api/session/{id}`,
   `GET /api/session?parentID=…`, `GET …/permission`, `GET …/form`, `GET …/inbox`,
   `GET …/message?limit=20&order=desc`; possibly `POST …/view` (204) for an unread idle session
   (subagent: `tui/src/context/session-tabs.tsx:212-238`).
8. `/sessions` dialog: `GET /api/session?limit=50&order=desc&parentID=null&project=<id>[&subpath=…]`
   (or `&directory=` when project id is `"global"`), `&search=` when typing (subagent:
   `component/dialog-session-list.tsx:57-81`). `--continue` uses
   `GET /api/session?limit=1&order=desc&parentID=null&directory=…`.

Also note: `Project` items need `time.active` (sorting, `data.ts:1866-1871`); `SessionInfo` needs
`location`, `time.updated`, `cost`, `tokens`; `ModelInfo.variants` must be an array
(`local.tsx:250`) and `limit.context` is read (subagent: `tui/src/util/session.ts:59`); while a
permission (or form) is pending the prompt is disabled (subagent: `routes/session/index.tsx:234`).
Auto-accept mode (`--auto` / config) makes the TUI itself reply `once` to permission requests
(subagent: `routes/session/index.tsx:261-276`; `context/permission.tsx:13-15`).

---

## 8. Unverified / open

- Server-side SSE framing of the real server (`packages/server` absent); the format above is the
  one the client parser accepts and the TUI fake server uses.
- Exact `inbox.delivered` vs `execution.started` order in the real server: inferred from
  `core/src/session/execution.ts:112-116` (started on coordinator start) and the runner promoting
  input before `Step.Started` (`core/src/session/runner/llm.ts:169`,
  `runner/publish-llm-event.ts:135`). The client tolerates either order.
- `session.tool.success.content` must be non-empty per schema; the TS client does not enforce it,
  so `[{"type":"text","text":""}]` should be harmless (unverified in render).
