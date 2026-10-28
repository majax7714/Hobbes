# How other AI coding agents decide what to auto-approve (October 2026)

Scope: products other than Claude Code, Codex CLI and Gemini CLI. Researched 2026-10-16.

Labels: **VERIFIED** means confirmed in official docs, source code, a changelog or a security advisory. **UNVERIFIED** means it comes from blogs, forums, press or my own inference.

Source code was read from shallow clones made on 2026-10-16. Line numbers refer to these commits:

| Repo | Commit (date) |
|---|---|
| block/goose | `59e588dfd941ae129f2938deb7acf9f80b6edd02` (2026-10-16) |
| cline/cline | `b549ceb4bb4247284c975f6d6ca0979decec097c` (2026-10-16) |
| Kilo-Org/kilocode | `6e1cb451938a2fcf3ae9d50f62bd51a40e604afb` (2026-10-16) |
| RooCodeInc/Roo-Code | `b867ec9145750d0ae1ff7f02d35406e9bf2a0b16` (2026-05-15; last commit on default branch, so the repo looks inactive since May 2026 — UNVERIFIED as to project status) |
| Aider-AI/aider | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` (2026-05-22) |
| OpenHands/software-agent-sdk | `6530325e9dd0ea1b6b4f1994d7dab52764cfc3f1` (2026-10-16). The agent and security code now lives here. `All-Hands-AI/OpenHands` at `950ee95f…` holds the front end and app, with no `pyproject.toml` at its root. |

GitHub links below use the form `https://github.com/<repo>/blob/<sha>/<path>#L<n>`.

---

## Q1. Mechanism: static rules, a model-based classifier, the model declaring risk, learned rules, or rules taken from the repo?

### Takeaway
By October 2026 the field has split into three tiers:
1. **Static rules only.** Roo, Kilo, Zed, Junie, Warp lists, Windsurf/Devin Desktop lists, VS Code terminal rules, and Amp's legacy rules.
2. **The acting model labels its own call.** Cline's `requires_approval` (legacy bundle), OpenHands' `security_risk` field, and probably Windsurf "Auto" and Warp "Agent decides".
3. **A separate judge model sees each call.** Cursor Auto-review (since 3.6, May 2026), VS Code/Copilot "Assisted permissions" (around 1.130), Goose SmartApprove (judges read-only vs write) and Goose's opt-in adversary reviewer, OpenHands' optional ToolShield and GraySwan analyzers, and Amp plugins that call `amp.ai.ask`.

"Learned" permissions almost everywhere just mean that clicking "always allow" persists a static rule. Several products derive that rule from the command (Kilo's arity prefix, Junie's generated regex, Zed's extracted pattern). Repo-derived rules exist in two places: VS Code auto-approves npm scripts defined in `package.json`, and Cursor/Amp read project-level permission files.

### Cited Findings

**Cursor (closed source)**
- VERIFIED: Cursor has three Run Modes:
  - **Auto-review**: "recommended default since 3.6, May 29, 2026".
  - **Allowlist**.
  - **Run Everything**.
  
  "Ask Every Time" was deprecated in 3.5 (May 22, 2026); the replacement is Allowlist with an empty list. — [Cursor docs: Run Modes](https://cursor.com/docs/agent/security/run-modes)
- VERIFIED: Auto-review applies this order:
  1. Allowlisted shell, Fetch and MCP calls run outside the sandbox.
  2. Other shell commands run in the sandbox if they fit its file and network limits.
  3. Commands that need more access go to a classifier.
  4. If a sandboxed command fails because of a sandbox restriction, the agent may rerun it unsandboxed, and the classifier reviews that rerun.
  5. All other calls go to the classifier.
  
  A blocked call makes the agent try another approach. If the agent still thinks the action is justified, it shows the user an approval prompt. — [Cursor docs: Run Modes](https://cursor.com/docs/agent/security/run-modes)
- VERIFIED: The classifier runs on Cursor's backend using "small Cursor-managed models: Gemini 3.5 Flash Lite, with Claude 4.5 Haiku as fallback". The docs say Auto-review "is not a security boundary". — [Cursor docs: Run Modes](https://cursor.com/docs/agent/security/run-modes)
- VERIFIED: Users configure the classifier in plain English. `~/.cursor/permissions.json` and `<project>/.cursor/permissions.json` are merged, with `autoRun.allow_instructions` and `autoRun.block_instructions`. A team-level dashboard configuration overrides both local files. — [Cursor docs: Run Modes](https://cursor.com/docs/agent/security/run-modes)
- VERIFIED (history): Cursor dropped the auto-run **denylist** in v1.3 (July 2025) after Backslash Security showed four ways around it, and moved to an allowlist. — [The Register, 2025-07-21](https://www.theregister.com/2025/07/21/cursor_ai_safeguards_easily_bypassed/); [Backslash blog](https://www.backslash.security/blog/cursor-ai-security-flaw-autorun-denylist). This is press plus the researcher's own post; I did not find a Cursor changelog entry, so the "v1.3" detail is UNVERIFIED beyond the press.
- UNVERIFIED (forum): Before Auto-review, the agent could set `required_permissions: ["all"]` to ask to leave the sandbox. Users reported the agent doing this pre-emptively. — [Cursor forum](https://forum.cursor.com/t/agent-preemptively-uses-required-permissions-all-instead-of-auto-running-in-sandbox-allowlist-with-sandbox/161271)
- UNVERIFIED (forum): With "Auto-Run in Sandbox" on, the command allowlist was reported as silently ignored. — [Cursor forum](https://forum.cursor.com/t/command-allowlist-is-silently-ignored-when-auto-run-in-sandbox-is-enabled/152136)

**GitHub Copilot agent mode in VS Code**
- VERIFIED: VS Code offers these permission levels:
  - **Manual** (default; uses the tool, URL and terminal approval settings).
  - **Assisted permissions**: "an LLM judge assesses each tool call, and calls it doesn't approve need confirmation". Enabled with `chat.assistedPermissions.enabled`; requires Folder isolation; not available for Local harness.
  - **Allow all**: worktree sessions always use it.
  - **Autopilot**.
  
  `chat.tools.global.autoApprove`, `/yolo` and `/autoApprove` bypass approvals. — [VS Code docs: approvals](https://code.visualstudio.com/docs/agents/run/approvals)
- VERIFIED: The docs call Assisted permissions experimental and say it "reduces approval interruptions but is not a security boundary". — [VS Code docs: security](https://code.visualstudio.com/docs/agents/run/security)
- VERIFIED (source): The Assisted mode is passed to the Copilot CLI/SDK agent host as the approval mode `'assisted'`. Admins can disable it with managed setting `permissions.disableAssistedPermissionsMode` (`src/vs/platform/agentHost/node/copilotApprovalPolicy.ts`, `src/vs/platform/policy/common/copilotManagedSettings.ts` in microsoft/vscode, found via `gh search code`; commit SHA not pinned). This suggests the judge itself runs inside the closed Copilot runtime, not in VS Code's open code (UNVERIFIED inference).
- UNVERIFIED: Assisted permissions shipped around VS Code 1.130. A GitHub test issue carries the 1.130.0 milestone. — [microsoft/vscode#326555](https://github.com/microsoft/vscode/issues/326555); [third-party guide](https://en.ittrip.xyz/ai/vscode-assisted-permissions)
- VERIFIED: For Codex sessions, VS Code exposes a preset called "Auto-Review", which sends approval requests to an automatic reviewer. — [VS Code docs: approvals](https://code.visualstudio.com/docs/agents/run/approvals)
- VERIFIED: How static terminal rules work:
  - `chat.tools.terminal.autoApprove` maps a pattern to `true` or `false`. A pattern wrapped in `/` is a regex.
  - Rules match each subcommand by default. A compound command auto-runs only if every subcommand matches a `true` rule and none matches a `false` rule. A `false` rule always wins.
  - `{matchCommandLine: true}` matches the full command line instead.
  - A `false` rule only forces a prompt; it does not block.
  
  — [VS Code docs: approvals](https://code.visualstudio.com/docs/agents/run/approvals)
- VERIFIED (history):
  - 1.103 (July 2025): allowList and denyList merged into `chat.tools.terminal.autoApprove`.
  - 1.104 (Aug 2025): added `chat.tools.terminal.enableAutoApprove`.
  - 1.108 (Dec 2025): added default-approved read-only commands, and npm/pnpm/yarn scripts defined in `package.json` became auto-approved by default (`chat.tools.terminal.autoApproveWorkspaceNpmScripts`).
  
  — [VS Code 1.103 notes](https://code.visualstudio.com/updates/v1_103); [1.108 notes](https://code.visualstudio.com/updates/v1_108) (wording taken from search summaries, not re-read in full: treat details as UNVERIFIED)
- VERIFIED: There are separate rules for URLs and edits:
  - `chat.tools.urls.autoApprove` has two steps, `approveRequest` and `approveResponse`. The response step guards against injected content.
  - `chat.tools.edits.autoApprove` takes globs (for example `"**/.env": false`).
  - `chat.tools.eligibleForAutoApproval: false` forces manual approval for a tool.
  
  — [VS Code docs: approvals](https://code.visualstudio.com/docs/agents/run/approvals); [VS Code docs: security](https://code.visualstudio.com/docs/agents/run/security)

**GitHub Copilot coding agent (cloud)**
- VERIFIED: There are no per-action approvals. Instead, containment applies:
  - Only users with write access can trigger the agent.
  - It pushes only to a `copilot/` branch and "cannot directly run `git push` or other Git commands".
  - Workflows "are not triggered until Copilot cloud agent's code is reviewed".
  - It "cannot approve or merge a pull request".
  - A firewall restricts internet access.
  - Hidden characters are filtered from issues and comments.
  
  — [GitHub docs: risks and mitigations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)

**Cline (Apache-2.0, open source)**
- VERIFIED (docs): "There is no fixed allowlist. The model sets a `requires_approval` flag on each command." The "Execute safe commands" toggle auto-runs commands the model marks as safe. "Execute all commands" also runs those it marks as needing approval. YOLO mode approves everything. — [Cline docs: Auto Approve & YOLO](https://docs.cline.bot/features/auto-approve)
- VERIFIED (source): The **SDK bundle** does not use that flag. Cline 4.1.x ships an A/B VSIX that holds the legacy (3.89) extension and a new SDK-based one, and rolls the SDK one out gradually from 1% (`CHANGELOG.md` 4.1.0). In the SDK bundle:
  - The `run_commands` input schema has no `requires_approval` field (`sdk/packages/core/src/extensions/tools/schemas.ts` L127–166). The only remaining mention is an example string in `apps/vscode/src/core/prompts/responses.ts` L120.
  - Approval is a plain per-category toggle. `isToolAutoApproved()` maps tool name to setting, and every command tool goes to `actions.executeSafeCommands` ([sdk-tool-policies.ts L48–68](https://github.com/cline/cline/blob/b549ceb4bb4247284c975f6d6ca0979decec097c/apps/vscode/src/sdk/sdk-tool-policies.ts#L48)).
  - So "safe" no longer means anything per command in the SDK path (UNVERIFIED inference from the code).
- VERIFIED (source): Defaults in `DEFAULT_AUTO_APPROVAL_SETTINGS`: readFiles, editFiles, useBrowser and useMcp are `true`; `executeSafeCommands` is `false` ([AutoApprovalSettings.ts L28–44](https://github.com/cline/cline/blob/b549ceb4bb4247284c975f6d6ca0979decec097c/apps/vscode/src/shared/AutoApprovalSettings.ts#L28)). The changelog says "Command auto-approval is now disabled by default" (4.0.0 era, `CHANGELOG.md` ~L599). It also says the YOLO toggle "was cosmetic: nothing in the approval path read it" and was removed (4.1.8, ~L341).
- VERIFIED (changelog): MCP auto-approval is one global toggle. Per-tool MCP checkboxes were hidden as "no-ops that implied granularity the approval path does not have" (4.1.15, `CHANGELOG.md` L212).
- VERIFIED (source): Plan mode runs a deterministic `beforeTool` guard that blocks file-editing shell constructs before approval ([command-guard-extension.ts](https://github.com/cline/cline/blob/b549ceb4bb4247284c975f6d6ca0979decec097c/sdk/packages/core/src/extensions/tools/command-guard-extension.ts#L1)).

**Roo Code (open source)**
- VERIFIED (source): Commands are approved by **longest-prefix match** on `allowedCommands` and `deniedCommands`. Matching is case-insensitive `startsWith`, and `*` counts as a wildcard of length 1 ([commands.ts L95](https://github.com/RooCodeInc/Roo-Code/blob/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16/src/core/auto-approval/commands.ts#L95)). Decision rules:
  - A command is auto-approved if the longest allowed match is longer than the longest denied match. With no denied match, an allowed match is enough (L124).
  - Ties go to deny.
- VERIFIED (source): `getCommandDecision` splits chained commands with `parseCommand` and strips `N>&M` redirections. Any `auto_deny` wins. Then `containsDangerousSubstitution` forces `ask_user` for `${var@P}`, `${!var}`, `<<<$(...)`, zsh `=(...)` and `*(e:...:)` (L22, L256).
- VERIFIED (source): Other per-category toggles: `alwaysAllowReadOnly`, `alwaysAllowWrite` (plus OutsideWorkspace and Protected variants), `alwaysAllowMcp`, `alwaysAllowExecute`, `alwaysAllowFollowupQuestions` with a timeout, and the master switch `autoApprovalEnabled` ([auto-approval/index.ts L18–34](https://github.com/RooCodeInc/Roo-Code/blob/b867ec9145750d0ae1ff7f02d35406e9bf2a0b16/src/core/auto-approval/index.ts#L18)).

**Kilo Code (open source; now an OpenCode fork)**
- VERIFIED (source): The rules are OpenCode-style. Each rule is `{permission, pattern, action}` with action `allow`, `ask` or `deny`. `evaluate()` takes the **last** matching rule (`Wildcard.match` on both permission and pattern) and defaults to `ask` ([permission/index.ts L102–107](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/permission/index.ts#L102)).
- VERIFIED (source): Default ruleset:
  - `"*": "allow"` for everything, with `.env` reads set to `ask` and external directories to `ask` ([agent/agent.ts L136–158](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/agent/agent.ts#L136)).
  - A Kilo patch sets bash to `"*": "ask"` plus a read-only allowlist (`cat *`, `ls *`, `grep *`, `rg *`, `jq *`…) ([kilocode/agent/index.ts L24–56, L378](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/kilocode/agent/index.ts#L24)).
  - Edits are `allow` by default, except on JetBrains (`edit: "ask"`).
- VERIFIED (source): **Derived "always" rules.** The shell tool parses the command with tree-sitter. For each subcommand it offers an "always" pattern built from `BashArity.prefix(tokens)` plus `" *"`. For example `git checkout main` becomes `git checkout *` ([tool/shell.ts L409](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/tool/shell.ts#L409)). The arity table (`permission/arity.ts`) was itself generated by an LLM prompt, and the prompt is kept in a comment.

**Aider (open source)**
- VERIFIED (source): Aider has no tool-call loop and no model-based judge. The model *suggests* shell commands, and `handle_shell_commands` calls `confirm_ask(..., explicit_yes_required=True, allow_never=True)` ([base_coder.py L2450–2460](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/coders/base_coder.py#L2450)). Under `--yes-always`, `explicit_yes_required` prompts resolve to **"n"** (`res = "n" if explicit_yes_required else "y"`, [io.py ~L864](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/io.py#L864)). So `--yes-always` never auto-runs suggested shell commands. "Don't ask again" is kept only in memory for the session (`never_prompts`).

**OpenHands (MIT; V1 software-agent-sdk)**
- VERIFIED (source): Approval is two pieces: a `SecurityAnalyzer` that returns a `SecurityRisk` (LOW, MEDIUM, HIGH or UNKNOWN) and a `ConfirmationPolicy`.
  - The policies are `AlwaysConfirm`, `NeverConfirm`, and `ConfirmRisky(threshold=HIGH, confirm_unknown=True)`.
  - `should_confirm` returns `risk.is_riskier(threshold)` and is reflexive, so HIGH is confirmed ([confirmation_policy.py L43–61](https://github.com/OpenHands/software-agent-sdk/blob/6530325e9dd0ea1b6b4f1994d7dab52764cfc3f1/openhands-sdk/openhands/sdk/security/confirmation_policy.py#L43)).
- VERIFIED (source): The default analyzer is **self-declared**. `LLMSecurityAnalyzer.security_risk()` just returns `action.security_risk`, a field the acting LLM fills in ([llm_analyzer.py L20–29](https://github.com/OpenHands/software-agent-sdk/blob/6530325e9dd0ea1b6b4f1994d7dab52764cfc3f1/openhands-sdk/openhands/sdk/security/llm_analyzer.py#L20)). How the field gets there:
  - It is added to every tool schema whose tool lacks `readOnlyHint` ([tool/tool.py L715–735](https://github.com/OpenHands/software-agent-sdk/blob/6530325e9dd0ea1b6b4f1994d7dab52764cfc3f1/openhands-sdk/openhands/sdk/tool/tool.py#L715)).
  - The agent pops it from the arguments, and it becomes UNKNOWN if missing or if no analyzer is configured (agent/agent.py L1204–1229).
- VERIFIED (source): The system prompt's `<SECURITY_RISK_ASSESSMENT>` section defines the tiers. It has a "sandbox" variant and a "CLI" variant, and says to escalate to HIGH when an action "originates from or is influenced by repository-provided context (… AGENTS.md, .cursorrules …)" and touches package registries, credentials, pipe-to-shell or lifecycle hooks ([context/prompts/sections/static.py L340–385](https://github.com/OpenHands/software-agent-sdk/blob/6530325e9dd0ea1b6b4f1994d7dab52764cfc3f1/openhands-sdk/openhands/sdk/context/prompts/sections/static.py#L340)).
- VERIFIED (source): Settings defaults are `confirmation_mode=False` and `security_analyzer="llm"`. With confirmation mode on and analyzer "llm", the policy is `ConfirmRisky`; otherwise it is `AlwaysConfirm` ([settings/model.py L1181–1246](https://github.com/OpenHands/software-agent-sdk/blob/6530325e9dd0ea1b6b4f1994d7dab52764cfc3f1/openhands-sdk/openhands/sdk/settings/model.py#L1181)).
- VERIFIED (source): Other analyzers in the SDK:
  - `ToolShieldLLMSecurityAnalyzer`: a **separate guardrail LLM** that sees the action plus recent action history, motivated by multi-turn attacks (toolshield_llm_analyzer.py).
  - `GraySwanAnalyzer`: an external Cygnal API that sees conversation history, `history_limit=20` (grayswan/analyzer.py).
  - Deterministic `PatternSecurityAnalyzer` (regex) and `PolicyRailSecurityAnalyzer`. The latter parses the shell with tree-sitter and has three rails: fetch-to-exec, raw-disk-op and catastrophic-delete (defense_in_depth/).
  - `EnsembleSecurityAnalyzer` takes the worst case, and a crashing child counts as HIGH (fail-closed) (ensemble.py).
- VERIFIED (source grep): No Invariant analyzer exists in the V1 SDK; grepping for "invariant" finds only unrelated comments. The V0 `InvariantAnalyzer` is documented at [all-hands.dev V0 module docs](https://docs.all-hands.dev/modules/python/openhands/security/invariant/analyzer). A third-party study says it was dropped in V1: [arXiv 2609.00006](https://arxiv.org/pdf/2609.00006) (UNVERIFIED: no official removal note found).

**Goose (Block, Apache-2.0)**
- VERIFIED (source): `GooseMode` has the values `Auto` (the `#[default]`), `Approve`, `SmartApprove` and `Chat` ([goose_mode.rs L22–31](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose-provider-types/src/goose_mode.rs#L22)).
- VERIFIED (source): The SmartApprove decision order in `PermissionInspector::inspect` ([permission_inspector.rs L150–260](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose/src/permission/permission_inspector.rs#L150)):
  1. A user per-tool permission (AlwaysAllow, NeverAllow or AskBefore).
  2. An MCP `readOnlyHint` annotation, which allows the call.
  3. The extension-management tool, which always asks.
  4. If the tool is uncached, send it to an **LLM read-only judge**.
  5. Otherwise ask.
- VERIFIED (source): The judge is `detect_read_only_requests`. It calls the session's own provider and model with a forced tool `platform__tool_by_tool_permission`, which returns `read_only_request_ids`. Its prompt says to treat IDs, names and arguments as untrusted and that "If you cannot make the decision, then it is not read-only". If the call fails, it returns an empty list, so the request needs approval (fail-closed) ([permission_judge.rs L41–185](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose/src/permission/permission_judge.rs#L41)).
- VERIFIED (source): A **learned/cached** verdict. When the judge says "not read-only", `cache_non_readonly_decision` saves `AskBefore` for that **tool name** globally through `update_smart_approve_permission` (permission_inspector.rs L22–34). A read-only verdict is not cached, so it is re-judged on every call. There is also a `ToolPermissionStore` keyed on tool name plus a blake3 hash of the arguments, with optional expiry, at `~/.config/goose/permissions/tool_permissions.json` (permission_store.rs).
- VERIFIED (source): Other inspectors run alongside the permission inspector (agents/agent.rs L338–356):
  - `SecurityInspector`: regex threat patterns plus an optional ML prompt-injection classifier. It is off by default (`SECURITY_PROMPT_ENABLED` defaults to false, security/mod.rs L58–72). When it fires, it forces RequireApproval.
  - `EgressInspector`: only logs outbound commands and always returns Allow.
  - `AdversaryInspector`: an **opt-in LLM reviewer**, enabled by `~/.config/goose/adversary.md` (plain-English BLOCK/ALLOW rules, default tool `shell`). It sees the original task and the last 4 user messages, and **fails open** ([adversary_inspector.rs L14–50](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose/src/security/adversary_inspector.rs#L14)).
  - `RepetitionInspector`.

**Sourcegraph Amp (closed source)**
- VERIFIED: "By default, Amp does not ask for approval before running tools." Permissions are now enforced through plugins, which workspace admins can distribute. — [Amp manual (legacy permissions page)](https://ampcode.com/manual/appendix/legacy-permissions-rules.txt)
- VERIFIED: The plugin `tool.call` hook fires before a tool runs. It can return `allow`, `reject-and-continue`, `modify` or `synthesize`, and it can ask the user with `ctx.ui.confirm`. The official permissions example allowlists safe git patterns and sends others to **`amp.ai.ask(...)`**, an LLM yes/no helper. `amp.ai.decide(...)` returns typed decisions "with calibrated probabilities". — [Amp docs: plugins](https://ampcode.com/docs/customize/plugins)
- VERIFIED (legacy, still documented): `amp.permissions` holds ordered rules where the first match wins. Actions are `allow`, `reject`, `ask` and `delegate`. A delegate program gets the tool args as JSON on stdin and `AGENT_TOOL_NAME` in the environment, and answers with exit 0 (allow), 1 (ask) or 2 (reject, with stderr sent to the model). — [Amp: How we think about permissions](https://ampcode.com/notes/permissions)

**Windsurf / Cascade (now documented as "Devin Desktop")**
- VERIFIED: Auto-execution levels:
  - **Disabled**.
  - **Allowlist Only**.
  - **Auto**: "the agent judges whether a command is safe"; premium models only.
  - **Turbo**: everything except the deny list.
  
  List entries are exact matches unless they end in ` *` (a token prefix). A team deny entry always requires approval. Admins can set a maximum level. — [Devin Desktop docs: terminal](https://docs.devin.ai/desktop/terminal.md)
- VERIFIED: "Devin Local" uses a separate allow/ask/deny rule system. — same source.

**Zed agent (open source, GPL/Apache)**
- VERIFIED: The settings are `agent.tool_permissions.default` (confirm, allow or deny; default confirm) and per tool `tools.<tool>.{default, always_allow, always_deny, always_confirm}`, using Rust regex that is case-insensitive by default. Precedence: built-in > always_deny > always_confirm > always_allow > tool default > global default. Chained commands are split and each subcommand is checked. The one hardcoded rule blocks `rm -rf` of `/`, `~`, `$HOME`, `.` and `..`. "Always for `<pattern>`" in a prompt writes a settings rule. Applies from v0.224.0; the older setting was `agent.always_allow_tool_actions`. — [Zed docs: tool permissions](https://zed.dev/docs/ai/tool-permissions)

**JetBrains Junie**
- VERIFIED: Junie asks before sensitive actions (terminal, MCP and others). "Always allow" saves to `~/.junie/allowlist.json`, which has the categories fileEditing, executables, mcpTools and readOutsideProject. In the IDE you can save one exact command or a **generated regex for similar commands**: `git log --oneline -2` becomes a git-log regex. "Brave mode" skips all approvals. — [Junie CLI action allowlist](https://junie.jetbrains.com/docs/action-allowlist-junie-cli.html); [Junie user approval](https://www.jetbrains.com.cn/en-us/help/junie/user-approval.html)

**Warp**
- VERIFIED: Permission profiles set each category (apply diffs, read files, create plans, execute commands, MCP…) to **Agent decides**, Always ask, Always allow or Never.
  - Regex `command_allowlist` entries always auto-run.
  - The `command_denylist` (defaults `wget`, `curl`, `rm`, `eval`) overrides both allowlist and Agent decides.
  - "Run until completion" bypasses the denylist unless that is turned off, but admin denylist rules are never bypassed.
  - For diffs, Agent decides behaves like Always ask.
  
  — [Warp docs: profiles & permissions](https://docs.warp.dev/agents/capabilities/agent-profiles-permissions.md)

**Devin (Cognition, cloud)**
- UNVERIFIED (researcher writeups): Cloud Devin runs autonomously in its own VM with no per-action approvals. In August 2025 it was shown to have little resistance to prompt injection: secret leakage through shell, browser and Markdown images, and an `expose_port` tool triggered by an injected multi-stage payload. — [Simon Willison, "Summer of Johann", 2025-08-15](https://simonwillison.net/2025/Aug/15/the-summer-of-johann/); [Rehberger DEF CON SG slides](https://media.defcon.org/DEF%20CON%20SG%201/DEF%20CON%20SG%201%20main%20stage%20presentations/Johann%20Rehberger%20-%20The%20Month%20of%20AI%20Bugs%20Lessons%20Learned%20Exploiting%20AI%20Computer-Use%20and%20Coding%20Agents.pdf)

### Inferences
- Cursor and VS Code/Copilot reached the same design within about five months of each other: deterministic allowlist, then OS sandbox, then an LLM judge for the rest, then a human. Both state plainly that the judge is "not a security boundary" and pair it with a sandbox. Goose has had an LLM judge for longer but uses it only for a coarse read-only/write split.
- The "model declares risk" approach (Cline legacy, OpenHands default) trusts the very model that prompt injection targets. OpenHands now ships a separate-judge alternative (ToolShield) and says outright that it exists for this reason. Cline's SDK bundle appears to have dropped the self-declared flag altogether.
- "Learned" permissions are always (a) persisted static rules generalized from a single approval (Kilo arity prefix, Junie regex, Zed pattern), or (b) Goose caching a judge's "not read-only" verdict per tool name. None of the products surveyed trains a model on user approvals.

### Gaps
- Exactly how Windsurf "Auto" and Warp "Agent decides" decide is not documented. It is unknown whether the acting model sets a flag or a separate model is called; I found no source.
- Which model the VS Code/Copilot Assisted-permissions judge uses, and what it sees, is not documented. The judge appears to live in the closed Copilot agent host.
- Devin's current (2026) permission model for cloud Devin and Devin Local could not be confirmed from official docs.
- Roo Code's project status after May 2026 is unknown.

---

## Q2. What inputs does each decision use (command string, tool name, args, conversation, user intent, repo contents)?

### Takeaway
Static engines see only the tool name and the argument string. Most LLM judges deliberately see *only* the call itself (Goose read-only judge) or the call plus limited context: Goose's adversary sees the task and the last 4 user messages, ToolShield and GraySwan see recent history, and Cursor's classifier can read files read-only. Self-declared risk (OpenHands, Cline legacy) implicitly uses the whole conversation, because the acting model fills in the field.

### Cited Findings
- VERIFIED (source): Goose's read-only judge gets one user message: `"UNTRUSTED TOOL REQUEST DATA (JSON):"` followed by `[{request_id, tool_name, arguments}]`. It gets no conversation, no user intent and no repo ([permission_judge.rs L92–117](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose/src/permission/permission_judge.rs#L92)).
- VERIFIED (source): Goose's AdversaryInspector gets the original task, up to 4 recent user messages (`MAX_RECENT_USER_MESSAGES = 4`), the tool call and the user's rules file ([adversary_inspector.rs L27, L201–308](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose/src/security/adversary_inspector.rs#L27)).
- VERIFIED: Cursor's classifier gets the call plus plain-English allow and block instructions. It "can make read-only `ReadFile`, `Grep`, `Glob`, and `ListDir` calls on your machine", so it can inspect repo contents. — [Cursor docs: Run Modes](https://cursor.com/docs/agent/security/run-modes). Whether it sees the conversation or the user's request is not documented (unknown).
- VERIFIED (source): OpenHands' ToolShield analyzer evaluates "each proposed action in the context of recent action history" and can be given per-tool "safety experiences". GraySwan sends "conversation history and pending actions" with `history_limit=20` (toolshield_llm_analyzer.py header; grayswan/analyzer.py L1–50, software-agent-sdk @ 6530325).
- VERIFIED (source): OpenHands' default `LLMSecurityAnalyzer` uses only the `security_risk` value the acting LLM emitted. The acting LLM has the full conversation and the prompt's repo-context escalation rules (llm_analyzer.py; static.py L340–385).
- VERIFIED (source): Roo uses the command string only, after chain-splitting and redirection stripping. Kilo uses the tool name (permission), the pattern (subcommand text masked by tree-sitter) and resolved paths, so it can tell when paths are outside the project (`scan.dirs`). See tool/shell.ts L395–410.
- VERIFIED: VS Code terminal rules use subcommands or the full command line. URL rules use the URL. Edit rules use the file path glob. npm-script auto-approval uses repo contents (`package.json`). — [VS Code docs: approvals](https://code.visualstudio.com/docs/agents/run/approvals); [VS Code 1.108](https://code.visualstudio.com/updates/v1_108)
- VERIFIED: The Amp delegate gets the tool args as JSON on stdin and the tool name in `AGENT_TOOL_NAME`. A plugin's `tool.call` gets `event.tool` and can use `amp.helpers.shellCommandFromToolCall`. `amp.ai.ask` is described as "thread-scoped", which suggests it has thread context. — [Amp permissions note](https://ampcode.com/notes/permissions); [Amp plugins](https://ampcode.com/docs/customize/plugins)
- VERIFIED: Zed and Warp match regex on tool inputs. Zed checks both the raw command and each subcommand. — [Zed docs](https://zed.dev/docs/ai/tool-permissions); [Warp docs](https://docs.warp.dev/agents/capabilities/agent-profiles-permissions.md)

### Inferences
- How much context a judge gets is a design trade-off. Goose's call-only judge is harder to inject through the conversation, but cannot tell whether an action matches what the user asked for. Goose's adversary, ToolShield and GraySwan see recent history because multi-turn attacks need it.

### Gaps
- Inputs to the VS Code/Copilot Assisted judge and to Codex "Auto-Review" as surfaced in VS Code: unknown.
- Inputs to Windsurf Auto and Warp Agent-decides: unknown.

---

## Q3. Is sandboxing or containment used *instead of* approval?

### Takeaway
Yes, and increasingly. Cursor's default treats "fits the sandbox" as auto-approval. VS Code sandboxes terminals and MCP servers independently of the permission level, and auto-approves calls to sandboxed MCP servers. Kilo now ships its own bubblewrap/Seatbelt sandbox with an escalation permission. Cloud agents (Copilot coding agent, Cursor Cloud Agents, Devin) replace approvals with VM/container isolation, network firewalls and review gates on outputs.

### Cited Findings
- VERIFIED: How Cursor sandboxes:
  - **macOS**: Seatbelt (`sandbox-exec`).
  - **Linux**: Landlock v3 plus seccomp. Requires kernel 6.2+ and unprivileged user namespaces, with a Bubblewrap fallback. Without these, Cursor falls back to asking.
  - **Filesystem**: workspace read/write. Protected paths are `.git/config`, `.git/hooks`, `.vscode`, `.cursorignore` and Cursor config.
  - **Network**: blocked by default; modes are "sandbox.json Only", "sandbox.json + Defaults" (the default; package registries etc.) and "Allow All".
  - **Read boundary**: added in 3.23 (Oct 1, 2026).
  - Cloud Agents "run on dedicated machines without approval prompts".
  
  — [Cursor docs: Run Modes](https://cursor.com/docs/agent/security/run-modes)
- VERIFIED: VS Code agent sandboxing restricts filesystem and network for terminal commands, "independent of permission level". Outbound network stays on by default (`chat.agent.sandbox.network.allowNetwork` defaults to `true`). It "is not a virtual machine or user-account boundary". Sandboxed stdio MCP servers on macOS/Linux have their tool calls auto-approved. — [VS Code docs: security](https://code.visualstudio.com/docs/agents/run/security); [approvals](https://code.visualstudio.com/docs/agents/run/approvals)
- VERIFIED: For the Copilot coding agent, the firewall is on by default with a recommended allowlist (OS and language package registries, container registries, and others). It applies only to processes started through the agent's Bash tool, **not** to MCP servers or setup steps. Blocked requests are reported in the PR. GitHub says it is not "a comprehensive security solution". — [GitHub docs: customize the agent firewall](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-firewall)
- VERIFIED (source): Kilo has a `packages/kilo-sandbox` package (bubblewrap.ts, seatbelt.ts, network relay and proxy) with config for `mode`, `allowedHosts` and `writablePaths` (`packages/opencode/src/kilocode/sandbox/policy.ts`). A git-mutating command inside a sandboxed session raises a separate `sandbox_escalation` permission that "needs an explicit reply", meaning a saved rule never covers it ([tool/shell.ts L436–447](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/tool/shell.ts#L436); [permission/index.ts L146–150](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/permission/index.ts#L146)).
- VERIFIED (source): OpenHands keeps two sets of risk tiers. In sandbox mode, "MEDIUM" covers installing packages system-wide inside the container and running user code, and "HIGH" is reserved for exfiltration or breaking out of the container (static.py `_SANDBOX_TIERS`). The sandbox therefore lowers how risky an action is rated.
- VERIFIED: Cline docs recommend "isolated environments" and Checkpoints for rollback rather than a built-in sandbox. — [Cline docs](https://docs.cline.bot/features/auto-approve)
- VERIFIED: Amp's philosophy is that cheap undo (git) replaces approval: "Undo-able actions need few restrictions". — [Amp permissions note](https://ampcode.com/notes/permissions)
- VERIFIED: No sandbox is described in the docs for Zed, Junie, Warp (local) or Windsurf/Devin Desktop. — [Zed](https://zed.dev/docs/ai/tool-permissions); [Devin Desktop terminal](https://docs.devin.ai/desktop/terminal.md); [Warp](https://docs.warp.dev/agents/capabilities/agent-profiles-permissions.md)

### Inferences
- "The command fits the sandbox" is becoming the main auto-approval criterion for shell, with rules and judges handling only escalations. That fits a client that can only see requests if the agent can also say whether a call will run sandboxed. ACP permission requests do not carry that today (see Q5).

### Gaps
- Whether Warp's cloud agents (Oz) or Junie's cloud mode use sandbox-instead-of-approval: not researched or found.

---

## Q4. Reported failure modes and bypasses

### Takeaway
Every class of control has been bypassed publicly:
- **Denylists**: obfuscation and quoting (Cursor 2025).
- **Allowlists**: parser gaps, then environment poisoning through shell built-ins (Cursor CVE-2025-54131 and CVE-2026-22708).
- **The approval settings themselves**: the agent edits its own config (Copilot CVE-2025-53773).
- **Approved commands that run attacker-controlled code**: git hooks, npm scripts.
- **Unsandboxed cloud agents**: injected exfiltration (Devin).

Vendors now describe both rules and LLM judges as "not a security boundary".

### Cited Findings
- VERIFIED (advisory): **CVE-2026-22708 / GHSA-82wg-qcm4-fp2w (Cursor < 2.3)**. In Auto-Run with Allowlist, shell built-ins (`export`, `typeset`, `declare`) ran without allowlist checks or approval. Prompt injection could poison the environment so that a *later allowlisted* command (for example `git branch`) ran attacker code. Credited to Dan Lisichkin (Pillar Security); fixed by improved parsing. — [GitHub advisory](https://github.com/cursor/cursor/security/advisories/GHSA-82wg-qcm4-fp2w); [cvefeed](https://cvefeed.io/vuln/detail/CVE-2026-22708)
- VERIFIED (advisory): **CVE-2025-54131 / GHSA-534m-3w6r-8pqr (Cursor)**. "Bypassing allow list to execute an arbitrary command" via indirect prompt injection; rated Moderate; fixed with a more robust parser. — [GitHub advisory](https://github.com/cursor/cursor/security/advisories/GHSA-534m-3w6r-8pqr)
- UNVERIFIED (press and researcher blog): Backslash showed four ways around Cursor's denylist (2025): obfuscation such as Base64, subshells, writing a script then running it, and quote splitting like `"e"cho`. Cursor deprecated the denylist. — [The Register](https://www.theregister.com/2025/07/21/cursor_ai_safeguards_easily_bypassed/); [Backslash](https://www.backslash.security/blog/cursor-ai-security-flaw-autorun-denylist)
- UNVERIFIED (roundup): CVE-2026-26268 (a nested git hook runs when the agent runs git) and CVE-2026-32202 (Workspace Trust disabled by default) in Cursor. — [SentinelOne CVE page](https://www.sentinelone.com/vulnerability-database/cve-2026-22708/) and search summaries; not re-checked against advisories.
- VERIFIED (vendor CVE; details from secondary sources): **CVE-2025-53773 (GitHub Copilot / Visual Studio, Aug 12 2025, CVSS 7.8)**. Injected instructions got Copilot to write `"chat.tools.autoApprove": true` into `.vscode/settings.json`, after which commands ran without a prompt. The fix requires confirmation for edits to settings files. Reported by Johann Rehberger. — [Wiz CVE entry](https://www.wiz.io/vulnerability-database/cve/cve-2025-53773); [Cyber Security News](https://cybersecuritynews.com/github-copilot-rce-vulnerability)
- VERIFIED (docs admission): VS Code says terminal auto-approve is "best-effort command parsing" with "known limitations with shell aliases, quote concatenation, and complex shell syntax". `blockDetectedFileWrites` detection "can miss subcommands, zsh and fish syntax differences, and obfuscated writes". — [VS Code security](https://code.visualstudio.com/docs/agents/run/security); [approvals](https://code.visualstudio.com/docs/agents/run/approvals)
- UNVERIFIED (GitHub issues): Bugs where explicit allow rules were still prompted (VS Code 1.127 `git diff`) — [microsoft/vscode#324059](https://github.com/microsoft/vscode/issues/324059). Catch-all rules not honored — [#265775](https://github.com/microsoft/vscode/issues/265775).
- VERIFIED (docs admission): Cursor says "the classifier can make mistakes in either direction". VS Code says "model-based assessments can make mistakes and approve potentially risky tool calls". — [Cursor](https://cursor.com/docs/agent/security/run-modes); [VS Code](https://code.visualstudio.com/docs/agents/run/security)
- VERIFIED (docs admission): Copilot coding agent: "Sophisticated attacks may bypass" the firewall. It does not cover MCP servers or setup steps. — [GitHub firewall docs](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-firewall)
- UNVERIFIED: Devin was shown downloading and running a C2 payload, leaking secrets, and calling `expose_port` under multi-stage injection. "Single stage payload is often refused, but multi-stage works consistently." — [Simon Willison](https://simonwillison.net/2025/Aug/15/the-summer-of-johann/); [Rehberger slides](https://media.defcon.org/DEF%20CON%20SG%201/DEF%20CON%20SG%201%20main%20stage%20presentations/Johann%20Rehberger%20-%20The%20Month%20of%20AI%20Bugs%20Lessons%20Learned%20Exploiting%20AI%20Computer-Use%20and%20Coding%20Agents.pdf)
- UNVERIFIED (summary only): A Cline flaw where "a wrapped malicious command could be misclassified as safe, bypassing the user approval requirement". This was the self-declared `requires_approval` path. — search summary pointing at the Month of AI Bugs material; the original post was not read.
- VERIFIED (source, design-level weakness): Goose's AdversaryInspector **fails open** on errors (adversary_inspector.rs L50, L451–459). The SmartApprove read-only judge fails closed (permission_judge.rs L161–185). OpenHands' Ensemble fails closed (ensemble.py).
- VERIFIED (source, design-level): Cline's own changelog admits two controls did nothing: the YOLO toggle was "cosmetic: nothing in the approval path read it", and per-tool MCP checkboxes were "no-ops". — `CHANGELOG.md` L341, L212 @ b549ceb
- VERIFIED (docs): In Warp, "Run until completion" bypasses the user denylist by default. — [Warp docs](https://docs.warp.dev/agents/capabilities/agent-profiles-permissions.md)
- VERIFIED (source, mitigation): Roo's `containsDangerousSubstitution` exists to stop allowlisted prefixes smuggling execution through bash/zsh expansions (commands.ts L1–65). This is the same class of problem as the Cursor CVEs.

### Inferences
- Prefix and regex allowlists fail in three structural ways:
  - **Parse divergence** between the checker and the real shell (quotes, built-ins, expansions, zsh).
  - **State poisoning** that makes a later allowlisted command dangerous (environment variables, git hooks, npm scripts, config files).
  - **The agent rewriting its own policy files.**
  
  VS Code's auto-approval of `package.json` scripts and Cursor's project-level `permissions.json`/`sandbox.json` are both places where repo contents influence policy. Cursor says local files "cannot weaken" team or hardcoded rules, but repo-level files can still widen local policy (UNVERIFIED inference).

### Gaps
- No public bypass write-ups were found yet for Cursor Auto-review's classifier or VS Code Assisted permissions. Both are new, from May to September 2026.
- No CVEs were found for Goose SmartApprove, Kilo, Zed, Junie or Warp permission logic. That does not mean none exist.

---

## Q5. Could a client receiving each permission request (e.g. over ACP) replicate the decision per request?

### Takeaway
- **Static rules: yes, mostly.** Roo longest-prefix, Kilo last-match wildcard with arity-derived "always" rules, Zed regex precedence, Warp regex lists and Windsurf token-prefix lists all need only the tool name and argument string, which an ACP `session/request_permission` carries in its `toolCall` content.
- **Call-only LLM judges: yes.** Goose's read-only judge can be replicated exactly.
- **Context-aware judges: partly.** Goose adversary, ToolShield and GraySwan need the conversation, which an ACP client *does* see as streamed session updates.
- **Sandbox-based auto-approval: no.** Cursor's "fits the sandbox" and VS Code's sandboxed MCP auto-approval depend on where the agent executes, which the client cannot observe or enforce.
- **Self-declared risk: no**, unless the agent forwards it. ACP has no field for it.

### Cited Findings
- VERIFIED (source): Goose is itself an ACP client of Claude, Codex, Amp and Copilot ACP agents (`crates/goose/src/providers/{claude_acp,codex_acp,amp_acp,copilot_acp}.rs`). For incoming `RequestPermissionRequest`s, `permission_decision_from_mode` maps `Auto` to AllowOnce and `Chat` to RejectOnce. **`Approve | SmartApprove` returns `None`**, meaning the request goes to the user and the LLM read-only judge is *not* applied to ACP-forwarded permission requests ([acp/provider.rs L2375–2381](https://github.com/block/goose/blob/59e588dfd941ae129f2938deb7acf9f80b6edd02/crates/goose/src/acp/provider.rs#L2375)).
- VERIFIED (source): Kilo has its own ACP permission bridge (`packages/opencode/src/acp/permission.ts`). Its rule engine needs only a permission name and pattern strings ([permission/index.ts L102–135](https://github.com/Kilo-Org/kilocode/blob/6e1cb451938a2fcf3ae9d50f62bd51a40e604afb/packages/opencode/src/permission/index.ts#L102)). Kilo's patterns come from **its own tree-sitter parse** of the command (tool/shell.ts L395–410), so a client would have to repeat that parse to match exactly.
- VERIFIED (source): The Goose judge's input is only `{request_id, tool_name, arguments}` (permission_judge.rs L92–117), all of which an ACP permission request carries if the agent includes raw input in its tool call (inference about ACP payloads; not checked against the ACP schema here).
- VERIFIED: VS Code puts Assisted permissions inside the Copilot agent host and limits it to "Copilot harness" sessions. For Claude and Codex harnesses it exposes *their* modes ("Codex presets: … Auto-Review"; Claude modes). VS Code as a host therefore delegates judging to each harness rather than judging permission requests itself. — [VS Code approvals](https://code.visualstudio.com/docs/agents/run/approvals)
- VERIFIED: The Cursor classifier can make its own read-only file calls on the user's machine, which a client could also do. But the allow-if-sandboxable step needs the agent's sandbox. — [Cursor Run Modes](https://cursor.com/docs/agent/security/run-modes)
- VERIFIED: Zed's tool_permissions apply to Zed's native agent tools (terminal, edit_file, fetch, mcp:…). The docs do not say whether they apply to external ACP agents. — [Zed docs](https://zed.dev/docs/ai/tool-permissions)
- VERIFIED (source): OpenHands' self-declared risk is popped out of the tool arguments inside the agent before execution (agent/agent.py L1204–1229), so it would not reach a client unless the agent forwards it.
- VERIFIED: Amp's delegate protocol (stdin JSON args, `AGENT_TOOL_NAME`, exit codes 0, 1 or 2) is an example of an out-of-process per-request decider. — [Amp permissions note](https://ampcode.com/notes/permissions)

### Inferences
- A per-request ACP client can reproduce most of the field: static rules, call-only judges and context-aware judges (it sees the conversation). The pieces it cannot reproduce are:
  - sandbox-conditional approval;
  - risk the acting model declares itself (unless the agent passes it on);
  - the agent's own command parser, which matters because mismatched parsers are exactly the bug class behind the Cursor CVEs.
- Goose shows the "do nothing smart for forwarded requests" choice in practice. Its SmartApprove covers only its own tools.
- "Always allow" in ACP returns an `allow_always` option to the *agent*, which then persists the rule in the agent's own format. A client that wants consistent learned rules across agents would have to keep its own store, like Goose's `ToolPermissionStore` (tool name plus argument hash).

### Gaps
- I did not verify which ACP adapters (claude-code-acp, codex-acp) include raw command strings and full arguments in `toolCall` for permission requests. That decides whether static rules can be replicated client-side.
- Whether Zed applies `tool_permissions` to ACP agents' permission requests: unknown.
