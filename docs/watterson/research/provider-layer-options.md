# Provider-layer options (research for DEC-002)

> Snapshot as of **2026-10-15**, gathered by a research subagent from PyPI,
> the GitHub API and official docs. Versions and activity go stale quickly, so
> re-verify before deciding. Items marked **[unverified]** could not be
> confirmed.

## Two kinds of "connection"

- **(a) Agent-harness wrappers** drive agent CLIs (Claude Code, Codex, Gemini
  CLI, OpenCode, …), often on subscription logins. The harness owns the agent
  loop.
- **(b) Model-API abstractions** give one call signature over Anthropic,
  OpenAI, Gemini, OpenRouter, Ollama and vLLM, using API keys. We own the loop,
  or there is none.

## Comparison

| Candidate | Kind | Python fit | Breadth | Auth | Tools / MCP | License | Latest |
|---|---|---|---|---|---|---|---|
| ACP + `agent-client-protocol` | a | Native client; agents are stdio subprocesses | ~43 agents (Gemini CLI, OpenCode, Cursor, Copilot, Goose; Claude/Codex via adapters) | Per agent | Passes MCP servers to agent; permission requests | Apache-2.0 | Py SDK 0.12.1 (2026-08); protocol v1.11 (2026-10), v2 alpha |
| claude-agent-sdk | a | Native, bundles Claude Code CLI | Claude only (plus Anthropic-compatible endpoints) | Key or subscription | In-process `@tool` MCP servers, hooks | MIT | 0.2.168 (2026-10) |
| paseo | a | TS daemon; client SDK is TS-only | Claude, Codex, OpenCode, ACP family, pi | Subscription CLIs | Own tool catalog + MCP | Apache-2.0 | 0.11.2 |
| OpenCode `serve` | a+b | HTTP/OpenAPI + SSE boundary | Many providers internally | Keys + provider OAuth | Runtime `POST /mcp` | MIT | v1.19.1 (2026-10) |
| any-llm (Mozilla) | b | Native, wraps official SDKs | ~30+ **[unverified]** | Keys | Tools; no MCP | Apache-2.0 | 1.36.0 (2026-10) |
| Pydantic AI | b + loop | Native, typed | ~22 native + any OpenAI-compatible | Keys | First-class MCP client and server | MIT | 2.56.0 (2026-10) |
| LiteLLM | b | Native SDK + proxy | 100+ | Keys | MCP gateway (proxy) | MIT core | 1.105.1 (2026-10); heavy |

## Notes

- **ACP** is the closest thing to a standard harness boundary: JSON-RPC over
  stdio, with a Python SDK. The risk is churn, since the SDK is pre-1.0 and
  schema v2 is in alpha.
- **claude-agent-sdk** is the deepest Claude Code integration. Hobbes's graph
  could be exposed as in-process Python tools. It only covers Claude.
  Subscription usage policy changed in 2026, so recheck it.
- **paseo** has the broadest harness coverage and already uses ACP internally.
  But it is TypeScript throughout, most of its weight (app, voice, relay) is
  irrelevant here, and from Python we would have to talk to its WebSocket
  protocol.
- **OpenCode serve** is a single binary that acts as both harness and model
  router, but it means adopting OpenCode's agent loop.
- **any-llm** is a lean transport layer with no agent loop, which suits a
  deterministic core.
- **Pydantic AI** is the choice if Hobbes runs its own tool-using agents over
  the graph (typed tools, MCP, fallbacks). It is on a fast 2.x cadence, so
  expect API movement.
- **LiteLLM** has the widest breadth and a gateway, but it is the heaviest
  option. Malicious PyPI releases 1.82.7/1.82.8 (2026-03) stole credentials, so
  if adopted, pin it with hashes.

## Subagent's suggested shortlist

1. **ACP Python SDK (harnesses) + any-llm (raw APIs).** Both are light,
   Apache-2.0, native Python, and multi-vendor.
2. Swap any-llm for **Pydantic AI** if Hobbes owns a tool-using agent loop.
3. Add **claude-agent-sdk** if Claude Code is primary and in-process
   tools/hooks matter.

## Questions that decide it

- Harnesses on subscriptions, raw APIs with keys, or both?
- Who owns the agent loop: Hobbes, or the harness?
- In-process library, or a shared gateway (keys, budgets, multi-user)?
- How central are local models (Ollama, vLLM)?

## Sources

agentclientprotocol.com (overview/agents, libraries/python);
github.com/agentclientprotocol/{python-sdk,claude-agent-acp,codex-acp};
github.com/anthropics/claude-agent-sdk-python;
support.claude.com/en/articles/15036540; opencode.ai/docs/server;
github.com/mozilla-ai/any-llm; docs.litellm.ai (mcp,
blog/security-update-march-2026); pydantic.dev/docs/ai; PyPI JSON; GitHub API;
`~/paseo/docs/{providers,custom-providers}.md`.
