# Session-scoped policy injection (open-work 3a)

Survey, 2026-10-16, read-only. How Hobbes can put policy in front of a
harness's own decisions for **one session**, without writing to the user's
or the repo's config. Versions: `claude-agent-acp` 0.90.0 (bundles
`@anthropic-ai/claude-agent-sdk` 0.3.296), `codex-acp` 2.2.2 (bundles
`@openai/codex` 0.160.1). Paths are under `adapters/node_modules/`:
CA = `@agentclientprotocol/claude-agent-acp/dist/acp-agent.js`,
SDK = `@anthropic-ai/claude-agent-sdk/`, CX = `@agentclientprotocol/codex-acp/dist/index.js`.

Why it matters: in DEC-007's live checks the guarded route's harness judges
decided everything; no request reached Hobbes.

## Transport (verified)

- One adapter process per session (`providers/acp_session.py`, spawn), so the
  adapter's env is per session.
- The Python ACP SDK sends `new_session(**kwargs)` as the request's `_meta`
  (`acp/client/connection.py:163-181` in the venv).
- claude-agent-acp reads `_meta.claudeCode.options` (CA:7802) and spreads it
  into the SDK options (CA:7899). An inline `settings` object is merged with
  the adapter's own (CA:7862-7879); a string is read as a file relative to
  `cwd`, so use the object form.
- The adapter sets these after the spread, so they cannot be set:
  `permissionMode`, `canUseTool`, `cwd`, `env` (merged),
  `allowDangerouslySkipPermissions` (CA:7904-7916). SDK callback `hooks`
  cannot cross JSON.

## Claude

| Mechanism | Gives Hobbes | Status |
|---|---|---|
| `settings.hooks.PreToolUse`, command hook, exec form (`command` + `args`, no shell; SDK `sdk.d.ts:7064-7090`) | Sees every tool call, including ones auto mode would allow alone; can answer `allow`/`deny`/`ask`/`defer` with a reason the agent sees (`sdk.d.ts:2759-2773`, `:988`) | Schema verified. **Unverified:** that hooks run before the auto classifier (upstream docs say so); what `ask` does in auto mode; that settings hooks passed this way run at all |
| `PostToolUse`, `PermissionDenied` hooks (`sdk.d.ts:2676`, `:2486`) | Whether a call ran, or was denied by the harness, with its reason | Schema verified |
| `PostToolUse` output `classifierContext` (≤2000 UTF-16 units, `sdk.d.ts:2695`) | Facts for the auto judge on later calls; never gates the current one; read-only calls are left out of the classifier's transcript | Not tested |
| `settings.autoMode.{environment,allow,soft_deny,hard_deny}` | Facts and prose rules for the auto judge | Read only from user, flag and policy tiers (CLI strings); merge with the user's own entries unverified |
| `settings.permissions.deny/ask`, `disallowedTools` (CA:7941) | Text rules; removing a tool | Pass through |
| `_meta.systemPrompt` (CA:7767-7787) | Instructs the agent, not the judge | Pass through |

## Codex

| Mechanism | Gives Hobbes | Status |
|---|---|---|
| `CODEX_CONFIG` env (JSON), merged into thread config, not persisted (CX:45657-45677) | Any `config.toml` key for the session | Verified |
| `auto_review.policy` / `extra_policy` in it | Guidance for the Auto-review judge | That a thread-level value reaches the reviewer is unverified |
| `hooks` in it | Pre-tool hooks | **Need trust**: the adapter's trust call writes `hooks.state.<key>.trusted_hash` to the user's `~/.codex/config.toml` (CX:39934-39950). `bypass_hook_trust` exists; how to set it per session is unverified |
| `_meta.jetbrains.air.customInstructions` → `developerInstructions` (CX:28093-28099) | Guidance the reviewer trusts (per the auto-permissions research) | Pass through |
| Approval and sandbox policy | Set per turn from the mode (CX:34264-34319); config keys are overridden | Mode only |
| Execpolicy `.rules` | No per-session input; a temp `CODEX_HOME` would mean copying credentials | — |

**The adapter trusts every session root:** it sets
`projects.<root>.trust_level = "trusted"` (CX:35450-35455), so a repo's own
`.codex/` config, rules and hooks always load. That is the repo-controlled
config class DEC-007 warns about.

## Gemini

Not installed; nothing checked. Public docs: `--policy <file>` on the spawned
process; settings hooks reportedly do not run on the ACP path.

## Costs

- A command hook spawns a process per tool call. A `uv run` entry point would
  add about 0.5-1 s (estimate); a stdlib-only client started with
  `python -I -S` is much cheaper.
- Judge context costs no extra model calls, only prompt length.
- The hook client must sit outside the agent's writable roots, or the agent
  could rewrite its own guard.
