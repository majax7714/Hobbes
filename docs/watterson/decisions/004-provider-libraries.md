# 004: Provider libraries are the ACP Python SDK plus any-llm, with no agent loop

- Status: accepted
- Date: 2026-10-16
- Closes: DEC-002

## Context
The only unique thing Hobbes brings is **extraction**, and what it enables: a
graph abstraction (Mermaid graphs devs read instead of code) and the knowledge
tools. Every other environment piece (agent loops, harnesses, UIs, model
routing) is already built well elsewhere. Rebuilding those would make Hobbes a
competitor in areas where it adds nothing. So we **take great existing pieces
and lay Hobbes over them**, and we don't overreach.

DEC-002 set the scope: drive agent harnesses on subscription logins *and* call
raw model APIs with keys. The research is in
`docs/research/provider-layer-options.md`.

## Decision
- **Harnesses:** the ACP Python SDK (`agent-client-protocol`). Agents run as
  stdio subprocesses: Claude Code via the `claude-agent-acp` adapter, Codex via
  `codex-acp`, and natively Gemini CLI, OpenCode and others.
- **Raw APIs:** any-llm. It is a thin transport over the official provider
  SDKs, with keys from env.
- **No agent loop of our own.** Harnesses own their loops. The raw-API path is
  a plain call; Hobbes does not run tool-using agents itself. This is why
  Pydantic AI was rejected.
- **Placement:** `pipeline/src/hobbes/providers/`, in the same uv project as
  extraction. It is glue outside `hobbes.extract`, so it ports cleanly back into
  hobbes-public as a subpackage.

## Consequences
- The provider layer stays Python-native, with no language boundary.
- Both libraries are young. The ACP SDK is pre-1.0 with schema v2 in alpha, so
  pin exact versions and wrap them behind a small interface of our own.
- Paseo is no longer a candidate base. It stays a read-only reference for how a
  mature harness wrapper behaves.

### Note, 2026-10-16: first slice landed (pinned versions)
- Pinned exactly in `pipeline/pyproject.toml` (locked in `uv.lock`):
  `agent-client-protocol==0.12.1` (latest stable; `1.0.0rc3` exists and was
  not taken) and `any-llm-sdk[anthropic,openai]==1.36.0`, which resolved
  `anthropic==0.125.0` and `openai==3.31.0`. ACP protocol version 1.
- Adapter commands, checked against the npm registry and upstream source:
  `npx -y @agentclientprotocol/claude-agent-acp` (pinned `@0.90.0`; the
  `@zed-industries/*` names are deprecated), `npx -y
  @agentclientprotocol/codex-acp` (pinned `@2.2.2`), and `gemini --acp` (Gemini CLI
  0.64.0; `--experimental-acp` is its deprecated alias). The adapters are pinned to the
  newest stable release at least two days old (0.92.0 was same-day), and a
  user override can repin one.
- Code: `pipeline/src/hobbes/providers/` (`registry`, `events`, `errors`,
  `acp_session`, `llm`) and `hobbes agents|ask|complete`. See
  `docs/overview.md` "Provider layer".
- `acp_session` spawns agents itself rather than through the SDK's
  `spawn_agent_process`: the agent inherits the caller's full environment
  (the SDK passes a trimmed set, which can hide harness login/config), runs
  in its own process group, and the group is reaped on close.

### Note, 2026-10-16: adapters locked, staleness check
- The claude and codex adapters are locked in `adapters/` at the repo root,
  a private npm project like `tsextract/`: exact versions in its
  `package.json` (`@agentclientprotocol/claude-agent-acp` `0.90.0`,
  `@agentclientprotocol/codex-acp` `2.2.2`) and the full tree in the committed
  `package-lock.json`. That fixes each bundled harness too:
  `@anthropic-ai/claude-agent-sdk` 0.3.296 (Claude Code 2.1.296) and
  `@openai/codex` 0.160.1. Install with `cd adapters && npm ci`.
- The built-ins launch `adapters/node_modules/.bin/claude-agent-acp` and
  `codex-acp` (no npx), found from the repo root as `hobbes.extract` finds
  `tsextract/`. A missing bin reports the hint `cd adapters && npm ci`.
  Overrides still win; gemini stays `gemini --acp`, not locked.
- `hobbes agents --check` (`providers/staleness.py`) compares each pin with
  the installed version and npm's latest stable release, and shows the bundled
  harness next to the user's own `claude`/`codex --version`. **Bump policy:
  manual only, with a 2-day cooldown**: a release under 2 days old shows as
  "cooling down", and the suggested bump is the newest stable release past
  it. The check never changes a pin. Exit 0 current or cooling, 1 bump
  suggested or pin != installed, 2 npm unreachable.
- **How to bump:** edit the exact version in `adapters/package.json`, run
  `npm install` in `adapters/` (updates `package-lock.json`), run
  `cd pipeline && uv run pytest -q` and the live pong
  (`uv run hobbes ask --agent claude "Reply with the single word: pong"`, and
  the same with `--agent codex`), then commit both files.
