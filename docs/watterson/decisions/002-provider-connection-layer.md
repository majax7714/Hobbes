# 002: Provider-connection layer, paseo or an alternative

- Status: accepted; the libraries are chosen in DEC-004.
- Date: 2026-10-15

## Context
The goal is **easy connection to model providers and agent tools**. Paseo was
picked first because it was the first open-source agentic tool the user had
used. The only part of it that matters here is its provider wrapping. Nothing
else in paseo is a requirement, and we are not bound to it.

Candidates fall into two kinds that solve different problems:
- **Agent-harness wrappers** drive agent CLIs (Claude Code, Codex, OpenCode,
  ACP agents), usually on the user's subscription logins. Paseo is this kind.
- **Model-API abstractions** give one API over Anthropic, OpenAI, Gemini,
  OpenRouter and local models, using API keys.

## Decision
**Scope (accepted 2026-10-15): both kinds.** The layer must drive agent
harnesses on subscription logins *and* call raw model APIs with keys.

**Libraries (pending).** The research is in
`docs/research/provider-layer-options.md`. The leading shortlist:
- **Harnesses:** the ACP Python SDK (`agent-client-protocol`). Optionally add
  claude-agent-sdk for in-process Claude tools.
- **Raw APIs:** any-llm (a thin transport) or Pydantic AI (if Hobbes owns a
  tool-using agent loop). Who owns the loop decides between them.

Paseo is no longer the presumed base. It is TypeScript throughout and mostly
irrelevant weight for a Python core.

## Consequences
- The provider layer will most likely be Python-native, which avoids a
  language boundary with extraction.
- A follow-up decision picks the concrete libraries. Paseo stays a read-only
  reference.
