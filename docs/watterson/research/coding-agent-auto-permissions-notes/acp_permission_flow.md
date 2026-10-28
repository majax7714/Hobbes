# ACP permission flow: what an ACP client decides when driving Claude Code, Codex and Gemini CLI (as of 2026-10-16)

Conventions. Local paths are cited as `path:line`. Abbreviations:
- `CAA` = `/home/mmarrujo/watterson-environment/adapters/node_modules/@agentclientprotocol/claude-agent-acp` (v0.90.0, bundles `@anthropic-ai/claude-agent-sdk` 0.3.296 at `adapters/node_modules/@anthropic-ai/claude-agent-sdk`)
- `CXA` = `/home/mmarrujo/watterson-environment/adapters/node_modules/@agentclientprotocol/codex-acp/dist/index.js` (v2.2.2, a single esbuild bundle, unminified; bundles `@openai/codex` 0.160.1)
- `PYACP` = `/home/mmarrujo/watterson-environment/pipeline/.venv/lib/python3.12/site-packages/acp/schema.py` (agent-client-protocol 0.12.1, generated from `schema-v1.19.0`, `schema.py:2`)
- `TSSCHEMA` = `/home/mmarrujo/watterson-environment/adapters/node_modules/@agentclientprotocol/sdk/schema/` (TS SDK 1.8.0; `schema.json` = v1, `v2/schema.unstable.json` = v2 draft)
- paseo at commit `a1da1b8f234afe7a75785022292cdf8a50ee11a5`; watterson-environment at `38f1e32443243dacbb226635c579d73ae3cbee95`.

Every claim is labeled VERIFIED (code/spec read) or UNVERIFIED. No agent or harness was run.

## ACP spec: session/request_permission, tool kinds, option kinds, modes, config options, v2 changes

### Takeaway
In ACP v1 the agent MAY ask; the client only sees what the agent chooses to send, and the four option kinds are just UI hints whose "remember" meaning is implemented (or not) by the agent. Session modes are being replaced by session config options (category `mode`), and the v2 draft drops `session/set_mode` entirely and adds a `command` permission subject plus prompt-level `title`/`description`.

### Cited Findings
- VERIFIED: "The Agent **MAY** request permission from the user before executing a tool call" via `session/request_permission`; "Clients **MAY** automatically allow or reject permission requests according to the user settings"; on cancel "the Client **MUST** respond with the `cancelled` outcome." — [ACP spec: Tool Calls](https://agentclientprotocol.com/protocol/tool-calls)
- VERIFIED: v1 request = `{sessionId, toolCall: ToolCallUpdate, options: PermissionOption[], _meta?}`, method `session/request_permission`, client side — `PYACP:5482-5500`; `TSSCHEMA/schema.json` def `RequestPermissionRequest` (`x-method: session/request_permission`).
- VERIFIED: `toolCall` is a `ToolCallUpdate`: `toolCallId`, `title`, `kind`, `status`, `content` (content / diff / terminal), `locations`, `rawInput`, `rawOutput`, `_meta` — `PYACP:4882-4930` (ToolCall), `PYACP:5182` (ToolCallUpdate).
- VERIFIED: `ToolKind = read | edit | delete | move | search | execute | think | fetch | switch_mode | other` — `PYACP:17`; spec says kinds help "clients choose appropriate icons and UI treatment" — [Tool Calls](https://agentclientprotocol.com/protocol/tool-calls).
- VERIFIED: `PermissionOption = {optionId, name, kind}`; `PermissionOptionKind = allow_once | allow_always | reject_once | reject_always` — `PYACP:12`, `PYACP:2867-2885`. Spec: `allow_always` = "Allow this operation and remember the choice", `reject_always` = "Reject this operation and remember the choice"; `kind` is "A hint to help Clients choose appropriate icons and UI treatment" — [Tool Calls](https://agentclientprotocol.com/protocol/tool-calls).
- VERIFIED: response outcome is `{outcome:"selected", optionId}` or `{outcome:"cancelled"}`; nothing else (no free-text reason, no edited input) — `PYACP:2331-2345`, `PYACP:3969-3970`, `PYACP:4505-4511`.
- VERIFIED: Session modes: agent MAY return `modes {currentModeId, availableModes}` at session setup; client changes with `session/set_mode {sessionId, modeId}`; agent can change its own mode and send `current_mode_update`; an exit-plan tool "will usually request permission" with `kind: "switch_mode"`; "Dedicated session mode methods will be removed in a future version of the protocol." — [ACP spec: Session Modes](https://agentclientprotocol.com/protocol/session-modes); schema `PYACP:1207`, `PYACP:2090-2105`, `PYACP:3301-3310`.
- VERIFIED: Session config options "supersede the older Session Modes API"; "Modes will be removed in a future version"; agents SHOULD send both and keep them in sync; clients that support config options SHOULD use them exclusively; set via `session/set_config_option {sessionId, configId, value}` (plus `type:"boolean"` for booleans) and the agent MUST return the full option list — [ACP spec: Session Config Options](https://agentclientprotocol.com/protocol/session-config-options).
- VERIFIED: `SessionConfigOptionCategory` = `mode | model | model_config | thought_level | other`; categories are "for UX purposes" and "MUST NOT be required for correctness" — `TSSCHEMA/schema.json` def `SessionConfigOptionCategory`.
- VERIFIED (v2 draft, unstable): `RequestPermissionRequest` now requires `title`, adds optional `description` and optional `subject` (instead of a required `toolCall`); `subject` is `{type:"tool_call", toolCall}` or `{type:"command", command, cwd, toolCallId?, terminalId?}` or a custom `_`-prefixed type; `options` gets `minItems: 1`; `PermissionOptionKind` becomes open (custom `_`-prefixed kinds allowed) — `TSSCHEMA/v2/schema.unstable.json` defs `RequestPermissionRequest`, `RequestPermissionSubject`, `CommandPermissionSubject`, `PermissionOptionKind`.
- VERIFIED (v2 draft): `SessionMode`, `SessionModeState`, `SetSessionModeRequest`, `CurrentModeUpdate` are absent from the v2 schema; config options remain — computed set difference of `$defs` between `schema.json` and `v2/schema.unstable.json`.
- VERIFIED: no ACP v1 or v2-draft schema type expresses a policy/rule object (no "policy", "approval", "rule" defs found when listing `$defs` names in both schemas).

### Inferences
- A client's only levers in pure ACP are: (a) answer each request it receives, (b) pick a mode/config option the agent advertises. It cannot see or veto actions the agent decides internally, and it cannot express "remember for pattern X" except by choosing an agent-defined `allow_always` option whose scope the agent decides.
- Because `kind` on options is a hint and the `optionId` is opaque, a policy client must match on `kind` but should log `optionId`/`name`, since the same `kind` (`allow_always`) means different scopes in different adapters (see below).
- Clients should implement both `set_mode` and `set_config_option` (category `mode`) today, and plan for config-options-only in v2.

### Gaps
- Whether a v2 stable release exists by Oct 2026: unknown; only the "unstable" v2 schema was found locally.
- The spec text for the v2 permission subject (prose docs at `/protocol/v2/draft/tool-calls`) was not fetched; findings come from the JSON schema only.

## claude-agent-acp (Claude Code via Claude Agent SDK)

### Takeaway
The client is only Claude Code's last-resort `canUseTool` callback: hooks, settings.json deny/ask/allow rules (user, project, local), the permission mode (acceptEdits, auto classifier, bypassPermissions, plan) and tool self-approval (reads in cwd, read-only Bash) are all evaluated inside Claude Code first and never reach the client. "Always allow" returns Claude Code's own suggested `PermissionUpdate`s, which usually persist a rule to a settings file (the adapter's generated rules go to `localSettings`, i.e. `.claude/settings.local.json`); there is no `reject_always` option. The client can set the mode via `session/set_mode` or `set_config_option("mode")`, and can inject rules/settings at session creation through `_meta.claudeCode.options`.

### Cited Findings
Evaluation order inside the harness
- VERIFIED: Claude Agent SDK evaluation order: Hooks → Deny rules → Ask rules → Permission mode → Allow rules → `canUseTool`. "A tool call approved at any earlier step, by `acceptEdits` or `bypassPermissions`, or by an allow rule, skips your `canUseTool` callback." Allow-rule step also resolves "a call the tool approves on its own ... a file read inside your working directories or a read-only Bash command". "In `dontAsk` mode, this step is skipped and the tool is denied." — [Claude Docs: Configure permissions](https://code.claude.com/docs/en/agent-sdk/permissions)
- VERIFIED: modes: `acceptEdits` auto-approves Edit/Write and `mkdir, touch, rm, rmdir, mv, cp, sed` inside the working dir/additionalDirectories; `plan` sends file-edit and shell-write tools to `canUseTool` regardless of allow rules; `bypassPermissions` approves everything reaching the mode step except critical-path `rm`/`rmdir`; ask rules, `AskUserQuestion`, MCP tools flagged `anthropic/requiresUserInteraction` and org-`ask` connector tools still reach `canUseTool` even in bypass; `auto` = "A model classifier reviews actions such as shell commands and network requests, allowing or blocking each one it reviews" — [Configure permissions](https://code.claude.com/docs/en/agent-sdk/permissions)
- VERIFIED: SDK type: `PermissionMode = 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan' | 'dontAsk' | 'auto'`; "'auto' - Use a model classifier to approve/deny permission prompts" — `adapters/node_modules/@anthropic-ai/claude-agent-sdk/sdk.d.ts:2500-2503`.
- VERIFIED: SDK option `permissionPrompts: 'host' | 'none'`; with `'none'` "the permission mode (including auto mode's classifier), rules and hooks still decide, and anything that would otherwise prompt is denied immediately ... `canUseTool` is never called" — `sdk.d.ts:2017-2025` (field at `:2025`).

How the adapter wires it
- VERIFIED: adapter starts the SDK with `settingSources: ["user", "project", "local"]`, so the user's `~/.claude/settings.json`, project `.claude/settings.json` and `.claude/settings.local.json` permission rules, `defaultMode` and hooks all apply before the client is asked — `CAA/dist/acp-agent.js:7897`.
- VERIFIED: it passes `permissionMode: initialPermissionMode`, `canUseTool: this.canUseTool(sessionId)` and `allowDangerouslySkipPermissions: allowBypass` — `CAA/dist/acp-agent.js:7914-7916`. Initial mode = explicit creation option, else the resumed transcript's mode, else settings `permissions.defaultMode`, else `"default"` — `CAA/dist/session-mode.js:22-35`, `CAA/dist/acp-agent.js:7797-7801`, `CAA/dist/permissions/modes.js:20-43`.
- VERIFIED: bypass is unavailable when running as root outside `IS_SANDBOX`, when settings set `permissions.disableBypassPermissionsMode: "disable"`, or when the client passes `_meta.claudeCode.options.allowDangerouslySkipPermissions: false` — `CAA/dist/permissions/modes.js:1-3`, `CAA/dist/acp-agent.js:7793-7796`.
- VERIFIED: the adapter deliberately does not re-apply the advertised mode in `canUseTool`: "Claude Code applies bypassPermissions before invoking canUseTool; a request that still reaches this callback is deliberately bypass-immune (for example a safety check, a tool requiring user interaction, or an explicit ask rule)" — `CAA/dist/acp-agent.js:7036-7041`.
- VERIFIED: `AskUserQuestion` does not become a permission request; with form-elicitation support it becomes an ACP elicitation, otherwise the tool is disallowed — `CAA/dist/acp-agent.js:7026-7035`, `CAA/dist/acp-agent.js:7814-7818`.
- VERIFIED: the client's own `_meta.claudeCode.options` are spread into SDK options before the adapter's overrides (`cwd`, `permissionMode`, `canUseTool`, `allowDangerouslySkipPermissions` cannot be overridden; `allowedTools`, `disallowedTools` (merged), `settings`, `hooks` (merged), `tools`, `permissionPrompts` etc. can be supplied) — `CAA/dist/acp-agent.js:7895-7941`. The adapter classifies `hooks` and `canUseTool` as "Callbacks and live objects: they cannot cross JSON-RPC" — `CAA/dist/acp-agent.js:400-405`.
- VERIFIED: `settings` from `_meta` may be an object or a path (read relative to cwd) and is passed as the SDK `settings` option — `CAA/dist/acp-agent.js:7856-7867`.

What the client receives
- VERIFIED: before each request, the adapter emits the `tool_call` notification if not yet sent (so the client already has the full call) — `CAA/dist/acp-agent.js:6840-6858`, `6873-6923`.
- VERIFIED: for non-AIR clients the request's `toolCall` = `{toolCallId, name (non-schema extra key), status:"pending", rawInput (full SDK tool input), title, kind, content, locations}`; content is the exact preview patch when the client negotiated diff-patch or v2, else the standard content; the blocked path is appended to `locations` — `CAA/dist/tool-calls/renderer.js:163-181`, `CAA/dist/permissions/presentation.js:36-80`.
- VERIFIED: titles/kinds: Bash title is the raw command, `kind:"execute"` — `CAA/dist/tool-calls/reporters/bash.js:18-25`; Write/Edit `kind:"edit"` with `locations` and `diff` content — `CAA/dist/tool-calls/reporters/file-edit.js:9-30`; other kinds: read, search, fetch, think, switch_mode (ExitPlanMode), other — `grep` of `CAA/dist/tool-calls/reporters/*.js`.
- VERIFIED: `_meta.claudeCode` carries `toolName`, `parentToolUseId` (subagent) and `mcpServer {name, source}` only when an MCP server or a subagent parent is involved — `CAA/dist/acp-agent.js:7072-7083`.
- VERIFIED: SDK's `decisionReason`, `title`, `description` and `defaultToNo` are only sent to AIR clients (`_meta`) or v2 clients (`title`/`description`); a plain v1 client gets neither the reason nor the `matchedAskRule` — `CAA/dist/permissions/presentation.js:46-56`, `81-95`.

Options and what "always" does
- VERIFIED: option ids/kinds: `allow-once` (allow_once), `allow-with-updates` (allow_always), `reject` (reject_once), plus tool-specific ones (`allow-skill-exact`, `allow-skill-prefix`, `exit-plan-*`) — `CAA/dist/permissions/options/shared.js:1-30`. No code path emits a `reject_always` option (grep of `CAA/dist` finds `reject_always` only in ordering helpers, `CAA/dist/permissions/options.js:55,68`).
- VERIFIED: the allow_always option is offered only if the SDK supplied valid `suggestions` and no user ask rule forced the prompt and the CLI did not set `suppressAlwaysAllowRule` — `CAA/dist/acp-agent.js:7042-7048`, `CAA/dist/permissions/normalization.js:76-100`.
- VERIFIED: choosing `allow-with-updates` returns `{behavior:"allow", updatedPermissions: <the SDK's suggestions verbatim>}`; for WebFetch the adapter generates `addRules WebFetch(domain:<host>)` to `localSettings`; for unknown non-MCP tools it generates a bare-tool allow rule to `localSettings`; Skill options write `Skill(<name>)` or `Skill(<prefix>:*)` to `localSettings` — `CAA/dist/permissions/effects.js:34-57`, `58-73`, `119-165`.
- VERIFIED: `PermissionUpdateDestination = 'userSettings' | 'projectSettings' | 'localSettings' | 'session' | 'cliArg'` and update types `addRules | replaceRules | removeRules | setMode | addDirectories | removeDirectories` — `sdk.d.ts:2545-2574`. SDK doc: suggestions are "for updating permissions so that the user will not be prompted again for this tool during this session" — `sdk.d.ts:220-228`.
- UNVERIFIED: that Claude Code writes `localSettings` updates to `<cwd>/.claude/settings.local.json` and `session` updates only to memory. Consistent with the SDK's own description of rule sources ("'persistent' (userSettings/projectSettings/localSettings — saved in a settings file), 'session' (cliArg/session — in memory only)") — `sdk.d.ts:5627`; exact file path not verified in code.
- VERIFIED: ExitPlanMode options set the session mode (`setMode` with destination `session`) to bypassPermissions/auto/acceptEdits/default, so answering this one request changes the harness's permission mode — `CAA/dist/permissions/effects.js:74-118`, `CAA/dist/acp-agent.js:7114-7126`.
- VERIFIED: a `cancelled` outcome or an unknown optionId aborts the tool ("Tool use aborted" / "Permission option was not offered") — `CAA/dist/permissions/effects.js:3-5`, `CAA/dist/permissions/response.js` (`decodeClaudePermissionResponse`).

Modes exposed to the client
- VERIFIED: `availableModes` = `default` ("Manual"), `acceptEdits`, `plan`, `auto` ("Claude handles permission decisions"), and `bypassPermissions` only when bypass is allowed. `dontAsk` is accepted by the parser but not advertised, so `set_mode("dontAsk")` is rejected as not available — `CAA/dist/session-mode.js:213-268`, `138-140`.
- VERIFIED: the same list is exposed as config option `id:"mode"`, `category:"mode"`; `session/set_mode` and `set_config_option("mode")` both call `query.setPermissionMode` — `CAA/dist/session-mode.js:66-81`, `135-166`.
- VERIFIED: if the model lacks auto-mode support, `auto` falls back to `acceptEdits` with a warning notice — `CAA/dist/session-mode.js:6-14`, `46-54`, `98-119`.

### Inferences
- To apply its own policy per request, a client must keep Claude Code from auto-deciding: run in `default` (or `plan`) mode, and ensure no settings allow rules / `defaultMode` from the user's or project's settings files shortcut it. Even then, tool self-approvals (file reads in cwd, read-only Bash, Agent/Task) never reach the client (per docs above).
- To enforce a hard policy that cannot be bypassed by modes, a client can "compile" into Claude Code's native layers at session creation: `disallowedTools` (deny, holds even in bypass), `settings.permissions.deny/ask/allow` via `_meta.claudeCode.options.settings`, and command hooks in that settings object. UNVERIFIED that `hooks` inside the SDK `settings` option (flag settings) are honored for command-type hooks; JS-callback hooks cannot be passed over ACP.
- Picking `allow_always` in this adapter is not "remember in the client": it mutates Claude Code's settings files (often `.claude/settings.local.json` in the repo), which then silently pre-empt the client in later sessions. A policy client that wants to own memory should answer `allow_once` and keep its own rule store.

### Gaps
- Exact on-disk file for each destination, and whether `cliArg` destination persists, were not verified in Claude Code source (closed binary).
- Which suggestions Claude Code produces per tool (e.g. Bash prefix rules vs. `addDirectories` with `session`) was only inferred from the adapter's label code (`CAA/dist/permissions/options/shell.js:42-80`).

## codex-acp (Codex via Codex App Server)

### Takeaway
codex-acp drives Codex's App Server and forwards only the App Server's approval requests (command exec, file change, extra sandbox permissions, MCP elicitations); everything the sandbox already allows, everything execpolicy rules allow/forbid, and (in the default "Auto review" mode) everything Codex's reviewer agent decides never reaches the client. The default mode is `agent` = approval `on-request` + `approvalsReviewer: auto_review` + workspace-write sandbox, so a client wanting per-request control must switch to `workspace-write` or `read-only`. "Always" options map to Codex's `acceptForSession` (session cache) or `acceptWithExecpolicyAmendment` (a persisted prefix rule).

### Cited Findings
- VERIFIED: modes (also config option `id:"mode"`, `category:"mode"`, "Approval and sandboxing preset for the session"): `read-only` (on-request, reviewer `user`, readOnly sandbox), `workspace-write` (on-request, `user`, workspaceWrite, no network), `agent` "Auto review" (on-request, reviewer `auto_review`, workspaceWrite) and `agent-full-access` (approval `never`, `dangerFullAccess`) — `CXA:34264-34337`, `CXA:34338-34353`.
- VERIFIED: default mode is `agent` (Auto review) unless env `INITIAL_AGENT_MODE` is set — `CXA:34319` (`DEFAULT_AGENT_MODE = _AgentMode.Agent`), `CXA:34362-34369`.
- VERIFIED: the mode's `approvalPolicy`, `approvalsReviewer` and `sandboxPolicy` are sent on every turn (`runTurn`), so mode changes apply from the next turn — `CXA:35600-35612`. `session/set_mode` and `set_config_option("mode")` both call `applyModeChange` — `CXA:43644-43673`.
- VERIFIED: the App Server requests the adapter handles: `item/commandExecution/requestApproval`, `item/fileChange/requestApproval`, `item/permissions/requestApproval`, `mcpServer/elicitation/request`, `item/tool/requestUserInput` — `CXA:36166-36170`, handlers `CXA:36236-36275`.
- VERIFIED: command approvals: options are built from Codex's authoritative `availableDecisions` (or a default set): `accept`→`allow_once` "Yes, proceed"; `acceptForSession`→`allow_always` "Yes, and don't ask again for this command in this session"; `acceptWithExecpolicyAmendment`→`allow_always` "Yes, and don't ask again for commands that start with `<prefix>`"; `applyNetworkPolicyAmendment`→`allow_always` or `reject_always` ("No, and block this host in the future"); `decline`→`reject_once` "No, continue without running it"; `cancel`→`reject_once` "No, and tell Codex what to do differently". If the set is incomplete the adapter answers `cancel` without asking the client — `CXA:32067-32100`, `CXA:32142-32205`, `CXA:32365-32372`.
- VERIFIED: file-change approvals offer `allow_once` (accept), `allow_always` "Yes, and don't ask again for these files" (acceptForSession), `reject_once` (cancel) — `CXA:32211-32226`.
- VERIFIED: extra-permissions (`request_permissions`) approvals offer turn/turn-with-strict-auto-review (`allow_once`), session (`allow_always`), reject (`reject_once`) and return `{permissions, scope: "turn"|"session", strictAutoReview}` — `CXA:32227-32250`, `CXA:32437-32470`.
- VERIFIED: MCP tool-call approvals arrive as MCP elicitations with `_meta.codex_approval_kind = "mcp_tool_call"`; options: Allow (`allow_once`), "Allow for this session" and "Always allow" (`allow_always`, only if Codex's `_meta.persist` offers them), Cancel/Deny (`reject_once`) — `CXA:32648-32708`.
- VERIFIED: request content for commands: `rawInput = {command (shell prefix stripped), cwd, url?, additionalPermissions?}`, `kind:"execute"`, title from parsed command actions, `locations` from action paths — `CXA:28407-28440`, renderer `CXA:28144-28157`. File-change request: title, `kind:"edit"`, `locations` of changed paths; no diff in the request object itself — `CXA:29144-29152`.
- VERIFIED: Codex's `reason` text goes only into AIR `_meta` (`requestPermissionMeta` returns nothing for non-AIR clients), so a plain ACP client does not receive why approval was needed — `CXA:32330-32339`.
- VERIFIED: `acceptForSession` in Codex = remember for this session; "Yes, and don't ask again for this command in this session" (label) — `CXA:32155-32162`. Persisted rules: "When you add a command to the allow list in the TUI, Codex writes to the user layer at `~/.codex/rules/default.rules`"; `prefix_rule` decisions `allow` ("Run the command outside the sandbox without prompting"), `prompt`, `forbidden`; most restrictive wins; "Rules are experimental and may change"; project `<repo>/.codex/rules/` loads only when trusted — [Codex docs: Rules](https://learn.chatgpt.com/docs/agent-configuration/rules.md)
- UNVERIFIED: that `acceptWithExecpolicyAmendment` via the App Server writes to `~/.codex/rules/default.rules` exactly as the TUI does (docs describe the TUI; Codex binary not inspected).
- VERIFIED: Auto-review: "evaluates approval requests that would otherwise pause for a human" (escalated exec, blocked network, edits outside writable roots, MCP/app tool calls); a denial goes back to the main agent, not to the user; after 3 consecutive or 10 of 50 denials the turn is interrupted; `approval_policy = "never"` / danger-full-access / `--yolo` skip review entirely; custom policy via `[auto_review].policy` in config.toml — [Codex docs: Auto-review](https://learn.chatgpt.com/docs/sandboxing/auto-review.md)
- VERIFIED: with `on-request`, "commands allowed by the sandbox can run without approval"; granular `approval_policy` has categories `sandbox_approval`, `rules`, `mcp_elicitations`, `request_permissions`, `skill_approval` — [Codex docs: Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security)
- VERIFIED: the adapter accepts a `CODEX_CONFIG` JSON (merged into session config); a `hooks` key is converted to `app-server -c hooks=<toml>` — `CXA:45590-45594`, `CXA:45655-45680`. It exposes `_codex/hooks/list` and `_codex/hooks/trust` ext methods that list `sessionFlags` hooks and write their `trusted_hash` to Codex config — `CXA:39927-39952`.
- VERIFIED: Codex hooks include `PreToolUse` (can deny with `permissionDecision: "deny"` or allow with `updatedInput`; covers Bash, `apply_patch`, MCP; `ask` not supported) and `PermissionRequest` (allow/deny/defer when Codex is about to ask; "doesn't run for commands that don't need approval"); non-managed hooks must be trusted by hash; configured in `hooks.json` or `[hooks]` in config.toml — [Codex docs: Hooks](https://learn.chatgpt.com/docs/hooks)
- VERIFIED: `approval_policy = "untrusted"` is retired and `on-failure` deprecated in current Codex docs (search summary of [Agent approvals & security](https://learn.chatgpt.com/docs/agent-approvals-security) / [Configuration Reference](https://developers.openai.com/codex/config-reference)); only the summary was read, not the reference page itself.

### Inferences
- A per-request policy client must leave the default `agent` mode: in it Codex's reviewer model, not the client, decides most escalations, and denials never surface as `request_permission`.
- Even in `workspace-write`/`read-only`, sandbox-permitted commands and file edits run without any request; the client only sees escalations. Rule-based pre-decisions (execpolicy `allow`/`forbidden`) also bypass the client.
- A client can "compile" policy natively in three ways: write `prefix_rule`s to `~/.codex/rules/*.rules` (or a trusted project `.codex/rules/`), pass `PreToolUse`/`PermissionRequest` hooks through `CODEX_CONFIG.hooks` and trust them via `_codex/hooks/trust`, or set a custom `[auto_review].policy`.
- Choosing an `allow_always` option has different scope depending on the option id (session cache vs. persisted prefix rule vs. network host rule), so a client must key on `optionId`, not only `kind`.

### Gaps
- Exact Codex App Server semantics of `acceptForSession` (exact command vs. prefix) and persistence target of execpolicy amendments: not verified in Codex source.
- Whether file-change diffs arrive in an earlier `tool_call` notification before the approval request: UNVERIFIED.
- Whether MCP tool calls in `workspace-write` mode always elicit approval: unknown (depends on Codex MCP approval config).

## Gemini CLI (`gemini --acp`)

Source: github.com/google-gemini/gemini-cli at main `b792f21edfe76ead81918374133c19dd1e5cc79a` (2026-10-16); latest stable tag `v0.64.0` = `4a0749aceac5643e6f85a36d7420314d85e13b52`. A research subagent diffed the permission files between them and found only @-path handling in `acpSession.ts` changed, so line numbers hold for both. Permalink pattern: `https://github.com/google-gemini/gemini-cli/blob/b792f21edfe76ead81918374133c19dd1e5cc79a/<path>#L<n>`. I re-read the lines marked "spot-checked" myself. The rest comes from the subagent's reading of the source and was not independently re-read.

### Takeaway
Gemini CLI's policy engine decides every tool call first. ALLOW runs silently, DENY throws inside the harness and never reaches the client as a permission request, and only ASK_USER becomes `session/request_permission`. Approval modes (`default`, `autoEdit`, `yolo`, `plan`) are just rule sets inside that engine, and the client can switch them with `session/set_mode`. "Always" is session-only in-memory by default. The opt-in `ProceedAlwaysAndSave` option writes `~/.gemini/policies/auto-saved.toml`. A client can compile its policy into native TOML rules (`--policy`, `~/.gemini/policies`), but BeforeTool hooks appear not to run on the ACP path.

### Cited Findings
- VERIFIED: ACP code lives in `packages/cli/src/acp/`; `--acp` is the flag and `--experimental-acp` is deprecated — `packages/cli/src/config/config.ts` L363-371.
- VERIFIED (spot-checked): the ACP session answers the tool's confirmation-bus request by calling `policyEngine.check(...)` and replying `confirmed = decision === ALLOW`, `requiresUserConfirmation = decision === ASK_USER` — `packages/cli/src/acp/acpSession.ts` L97-168 (L156-168 spot-checked). On a missing engine, unknown tool or error it fails closed (deny) — same function L104-176.
- VERIFIED (spot-checked): a `deny` decision throws `Tool execution for "X" denied by policy.` inside the harness — `packages/core/src/tools/tools.ts` L212-218. It never becomes a permission request. UNVERIFIED: what the client sees for a denied call (probably an error result to the model; the catch block was not read).
- VERIFIED: an `allow` decision means no request. The client only gets a `tool_call` in `in_progress` — `acpSession.ts` L823-836. If no bus reply arrives in 30 s, the result falls back to ask_user — `tools.ts` ~L330-360.
- VERIFIED (spot-checked): ACP counts as interactive (`interactive = ... || !!argv.acp || !!argv.experimentalAcp`) — `packages/cli/src/config/config.ts` L784-790. So the engine's non-interactive ASK_USER→DENY conversion (`packages/core/src/policy/policy-engine.ts` L298-301, L944) does not apply. In ACP mode the `ask_user` tool is excluded because "IDEs intercept tool calls and ask for permission" — `config.ts` L793-803.
- VERIFIED: modes are `ApprovalMode { DEFAULT='default', AUTO_EDIT='autoEdit', YOLO='yolo', PLAN='plan' }` — `packages/core/src/policy/types.ts` L48-53. They are implemented as built-in policy TOMLs in `packages/core/src/policy/policies/`:
  - `read-only.toml` ALLOWs `glob`, `grep_search`, `list_directory`, `read_file`, `google_web_search` and others at priority 50, so these never prompt.
  - `write.toml` sets `ask_user` for `replace`, `write_file`, `run_shell_command` and `activate_skill`, and in `autoEdit` allows `replace`/`write_file` (with an allowed-path checker).
  - `yolo.toml` allows `*` at 998 in yolo mode.
  - `plan.toml` denies `*` in plan mode.
- VERIFIED: in AUTO_EDIT, tools with `respectsAutoEdit` skip the policy check unless the target is a build file — `tools.ts` L196-205.
- VERIFIED: tiers are Default=1, Extension=2, Workspace=3, User=4, Admin=5, and final priority = tier + toml_priority/1000 — `packages/core/src/policy/config.ts` L66-71, L381-404. Settings become user-tier rules (L72-81, L406-620):
  - `mcp.excluded` → DENY 4.9
  - `tools.exclude` → DENY 4.4
  - `tools.confirmationRequired` → ASK_USER 4.35
  - `tools.allowed` → ALLOW 4.3
  - `tools.core` → ALLOW 4.25 plus a `*` DENY 4.24
  - `mcpServers.<name>.trust=true` → ALLOW `mcp_<name>_*` 4.2
  - `mcp.allowed` → ALLOW 4.1
- VERIFIED: an untrusted folder forces approval mode back to `default` — `config.ts` L758-764. Workspace policies are disabled by default (`export let disableWorkspacePolicies = true`, spot-checked) — `packages/cli/src/config/policy.ts` L42. The repo docs call the Workspace tier "currently non-functional" (issue #18186) — `docs/reference/policy-engine.md` L127-131.
- VERIFIED: what a request contains. A `tool_call` (status `pending`) is sent first, then `requestPermission` with `toolCall {toolCallId, status:'pending', title, content, locations, kind}` (spot-checked) — `acpSession.ts` L733-761.
  - Edits carry `{type:'diff', path, oldText, newText}`, plus an explanation text block if one exists — L711-733.
  - **No `rawInput` is sent.** Shell commands appear only in the title/description.
  - Kind mapping: Gemini kinds pass through, `Agent`→`think`, `Plan`/`Communicate`/others→`other` — `packages/cli/src/acp/acpUtils.ts` L202-222.
  - @-path access outside the workspace gets its own request with only allow_once/reject_once, `kind:'read'` — `acpSession.ts` ~L1080-1125.
- VERIFIED: options (`toPermissionOptions`, `acpUtils.ts` L85-200). The `optionId` is the `ToolConfirmationOutcome` value.
  - Always offered: `ProceedOnce` "Allow" (`allow_once`) and `Cancel` "Reject" (`reject_once`). No `reject_always` exists.
  - Unless `security.disableAlwaysAllow` is set: `ProceedAlways` "Allow for this session" (`allow_always`) for edit/exec/info.
  - For MCP: `ProceedAlwaysServer` and `ProceedAlwaysTool` (both `allow_always`, session).
  - Only when `security.enablePermanentToolApproval=true` (default false): `ProceedAlwaysAndSave` (`allow_always`, "all future sessions"). Spot-checked at `acpUtils.ts` L110-165.
- VERIFIED: response handling — `acpSession.ts` L763-813; `packages/core/src/scheduler/policy.ts` L114-181.
  - `cancelled` maps to `Cancel`, and an unknown optionId throws.
  - Session "always" adds an in-memory ALLOW rule (source `Dynamic (Confirmed)`), scoped to `commandPrefix = rootCommands` for shell and to a file-path argsPattern for edits — `scheduler/policy.ts` L133-144, L210-225; `policy/config.ts` L712-793.
  - `ProceedAlways` on an edit tool also switches the session to `autoEdit` — `scheduler/policy.ts` L124-126, L184-196.
- VERIFIED: `ProceedAlwaysAndSave` writes TOML to `~/.gemini/policies/auto-saved.toml` (filename spot-checked at `packages/core/src/config/storage.ts` L28). It writes to the workspace instead only if the folder is trusted and workspace policies are enabled — `scheduler/policy.ts` L146-157; `policy/config.ts` L795-892. Nothing goes to settings.json.
- VERIFIED: modes over ACP.
  - `session/new` and `session/load` return `modes` with ids `default`, `autoEdit`, `yolo`, `plan` (plan only when enabled) — `packages/cli/src/acp/acpSessionManager.ts` L164-166, L273-275; `acpUtils.ts` L224-252.
  - `session/set_mode` calls `config.setApprovalMode` — `acpRpcDispatcher.ts` L211-221, `acpSession.ts` L215-226.
  - Mode changes are echoed as an `agent_message_chunk` `[MODE_UPDATE] <mode>`, not `current_mode_update` — L179-189.
  - No ACP `configOptions` were found.
- VERIFIED: flags. `--yolo` and `--approval-mode default|auto_edit|yolo|plan` are mutually exclusive. `general.defaultApprovalMode: yolo` in settings is ignored. `security.disableYoloMode`/`admin.secureModeEnabled` make YOLO fatal — `config.ts` L258-259, L333-345, L698-750. `--policy` replaces the user policies dir and `--admin-policy` adds admin policies — `config.ts` L355-361; `policy/config.ts` L108-130.
- VERIFIED: policy locations and schema.
  - Admin: `/etc/gemini-cli/policies` on Linux. User: `~/.gemini/policies/*.toml`, or `--policy`. Workspace: `.gemini/policies`, disabled — `policy/config.ts` L108-130.
  - `[[rule]]` fields — `packages/core/src/policy/toml-loader.ts` L39-70, L228-237:
    - `toolName` (supports `*` and `mcp_<server>_*` wildcards), `subagent`, `mcpName`
    - `argsPattern` (regex over the stable-stringified args)
    - `commandPrefix`/`commandRegex` (only with `run_shell_command`)
    - `decision` = allow/deny/ask_user, `priority` 0-999
    - `modes`, `interactive`, `toolAnnotations`, `allowRedirection`, `denyMessage`
- VERIFIED (by absence; not exercised at runtime): BeforeTool hooks run only in the core Scheduler (`packages/core/src/scheduler/scheduler.ts` L646-647, `scheduler/tool-executor.ts` L116). The ACP `runTool` calls `invocation.execute()` directly and has no hook references — `acpSession.ts` L642-870, L838-840.
- VERIFIED: paseo launches Gemini as `npx -y @google/gemini-cli@0.52.0 --acp`, an older version than v0.64.0 — `/home/mmarrujo/paseo/packages/app/src/data/acp-provider-catalog.ts:182-189`.

### Inferences
- Gemini is the most client-friendly of the three for per-request policy. In `default` mode every write/shell call is ASK_USER and reaches the client with a diff. But read-only tools (read_file, grep, glob, web search) are always allowed by the built-in rules, and user-tier settings or TOML rules short-circuit the client.
- Because no `rawInput` is sent, a client cannot apply argument-level policy to shell commands except by parsing the title. This is a real gap for a per-request policy engine.
- Compiling policy natively looks practical: write a TOML file and pass `--policy <file>`, which sits at user tier 4.x and outranks defaults and YOLO, with only admin above it. Caveat: `--policy` replaces the user's own `~/.gemini/policies` dir.
- A client that owns memory should avoid `ProceedAlways` on edits, since it also flips the session to `autoEdit`, after which edits no longer reach the client.

### Gaps
- What the client sees for a policy-DENIED call (error tool_call update or nothing): unknown.
- Whether the trust check and per-session argv use the ACP session `cwd` and the original launch flags: UNVERIFIED.
- The built-in `agents.toml`, `discovered.toml`, `non-interactive.toml`, `conseca.toml` and `sandbox-default.toml` rules were not read.
- The repo docs disagree with the code on the tier count (they say "three tiers" and call Admin "Tier 4"; code has `ADMIN_POLICY_TIER = 5`, `policy/config.ts` L71). The code was taken as authoritative.

## Per-request hooks and "compiling" client policy into native harness rules; how real clients behave

### Takeaway
All three harnesses decide a large share of actions before ACP is involved, so a client that wants to own policy has two options: keep the harness in its most-asking mode and answer every request itself (accepting that self-approved reads etc. never reach it), or compile its policy into each harness's native rule layer (Claude settings/disallowedTools/hooks, Codex execpolicy rules/hooks, Gemini policy TOML). Current clients (paseo, our hobbes client) do neither in a policy-aware way: they choose by option `kind` only.

### Cited Findings
- VERIFIED: Claude: native levers listed in the claude-agent-acp section (`disallowedTools`, `settings.permissions`, settings hooks, `permissionPrompts:'none'`), reachable through `_meta.claudeCode.options` — `CAA/dist/acp-agent.js:7895-7941`. Docs: "To gate every tool call regardless of mode and rules, use a `PreToolUse` hook"; "a hook deny applies even in `bypassPermissions` mode" — [Configure permissions](https://code.claude.com/docs/en/agent-sdk/permissions)
- VERIFIED: Codex: rules files and hooks as listed in the codex-acp section — [Rules](https://learn.chatgpt.com/docs/agent-configuration/rules.md), [Hooks](https://learn.chatgpt.com/docs/hooks), `CXA:45590-45594`.
- VERIFIED: paseo (ACP providers, incl. Gemini via `npx -y @google/gemini-cli@0.52.0 --acp`, `/home/mmarrujo/paseo/packages/app/src/data/acp-provider-catalog.ts:182-189`): `requestPermission` auto-answers only when its `auto_accept` feature is on and the request is not a "chooser"; otherwise it surfaces every option to the user — `/home/mmarrujo/paseo/packages/server/src/server/agent/providers/acp-agent.ts:2556-2598`. Auto-selection prefers `allow_once` then `allow_always` (deny: `reject_once` then `reject_always`) — same file `:3981-4003`.
- VERIFIED (from subagent report, spot-checked only the ACP lines above): paseo sets ACP modes via `session/set_mode` if `availableModes` exist, else `set_config_option` on the `mode`-category option — `acp-agent.ts:2068-2180`; its Claude provider passes `canUseTool` and `settingSources: ["user","project","local"]` and always `allowDangerouslySkipPermissions: true` — `providers/claude/agent.ts:3380-3386`; its Codex provider never uses `acceptForSession`; paseo writes no Claude/Codex/Gemini rule files. (Paths relative to `/home/mmarrujo/paseo/packages/server/src/server/agent/`.)
- VERIFIED: our hobbes client records only `toolCallId`, `title` and the options from a permission request (drops `kind`, `rawInput`, `content`, `locations`) — `/home/mmarrujo/watterson-environment/pipeline/src/hobbes/providers/acp_session.py:77-91`. Its policies choose by option kind only: `deny_all` picks `reject_once` else `reject_always` else cancels; `allow_all` picks `allow_once` else `allow_always` — `/home/mmarrujo/watterson-environment/pipeline/src/hobbes/providers/events.py:106-123`. It never calls `set_mode`/`set_config_option` (grep of `pipeline/src/hobbes/providers` finds none).

### Inferences
- For the hobbes client to apply its own policy per request, it needs at least `kind`, `rawInput`, `locations` and `content` from the request, plus `optionId`-aware handling of `allow_always`, and it needs to set each harness's mode explicitly (Claude `default`, Codex `workspace-write` or `read-only`, Gemini default/ask mode) rather than inherit the harness default (Codex defaults to Auto review).
- Because `allow_always` in Claude and Codex writes harness-side rules that later pre-empt the client, a client that owns policy should avoid `allow_always` and remember decisions itself.

### Gaps
- No ACP-level mechanism was found for a client to push rules to an agent; any "compile" path is harness-specific and outside ACP.
