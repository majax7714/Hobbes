"""Hobbes's connection to model providers: glue only, no agent loop (DEC-004).

Two ways out, each behind one module so a library bump touches only it:

- **Agent harnesses over ACP** (``acp_session``): ``AgentSession`` /
  ``run_prompt`` spawn an agent from the registry (``registry``) and yield
  ``events`` dataclasses. The harness owns its loop and its login.
- **Raw model APIs** (``llm``): ``complete`` / ``stream`` through any-llm,
  ``provider:model`` names and keys from the environment.

``staleness.check_adapters`` compares the ACP adapters locked in the repo's
``adapters/`` against npm. It reports the gap and never bumps a pin.

Callers import from here, never from ``acp`` or ``any_llm``. Names load on
first use, so importing the package does not pull in either library.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    # registry
    "AgentSpec": "registry",
    "BUILTIN_AGENTS": "registry",
    "agents_file": "registry",
    "get_agent": "registry",
    "load_registry": "registry",
    # events
    "Event": "events",
    "FileDiff": "events",
    "PermissionDecision": "events",
    "PermissionOption": "events",
    "PermissionRequest": "events",
    "Plan": "events",
    "PlanEntry": "events",
    "TextChunk": "events",
    "ThoughtChunk": "events",
    "ToolCall": "events",
    "ToolCallUpdate": "events",
    "TurnEnded": "events",
    "allow_all": "events",
    "deny_all": "events",
    # errors
    "AgentError": "errors",
    "CompletionError": "errors",
    "MissingKeyError": "errors",
    "ProviderError": "errors",
    "UnknownAgentError": "errors",
    # ACP harnesses
    "AgentSession": "acp_session",
    "PermissionCallback": "acp_session",
    "StdioMcpServer": "acp_session",
    "run_prompt": "acp_session",
    # adapter staleness
    "AdapterCheck": "staleness",
    "Freshness": "staleness",
    "check_adapters": "staleness",
    # raw APIs
    "Completion": "llm",
    "Usage": "llm",
    "complete": "llm",
    "stream": "llm",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
