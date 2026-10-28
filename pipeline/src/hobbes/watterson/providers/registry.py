"""Known ACP agents and how to launch each, plus a user override file.

An ``AgentSpec`` is just an argv, extra env and an optional cwd: the agent
is a stdio subprocess that speaks ACP (DEC-004). The built-ins below were
checked against the npm registry and upstream source on 2026-10-16:

- ``claude``: ``@agentclientprotocol/claude-agent-acp`` (bin
  ``claude-agent-acp``), the renamed ``@zed-industries/claude-code-acp``.
- ``codex``: ``@agentclientprotocol/codex-acp`` (bin ``codex-acp``), the
  renamed ``@zed-industries/codex-acp``.
- ``gemini``: Gemini CLI speaks ACP itself under ``--acp``;
  ``--experimental-acp`` is its deprecated alias. It is an installed CLI,
  found on PATH, and not locked here.

The claude and codex adapters are locked in ``adapters/`` at the repo root:
exact pins in its ``package.json`` and the whole transitive tree in its
``package-lock.json``, installed with ``cd adapters && npm ci``. The
built-ins launch the installed bins from ``adapters/node_modules/.bin/``,
since the adapters run with the user's full environment and logins. Each
adapter bundles its own harness (claude-agent-acp pins
``@anthropic-ai/claude-agent-sdk``; codex-acp ranges over ``@openai/codex``,
fixed by the lockfile), so bumping a pin is also bumping the harness.
``hobbes agents --check`` (``staleness``) compares the pins against npm.

Overrides come from a TOML file (``$HOBBES_AGENTS_FILE``, else
``~/.watterson/agents.toml``). Each ``[agents.<name>]`` table replaces the
built-in of that name whole, or adds a new agent::

    [agents.claude]
    command = ["claude-agent-acp"]      # e.g. a global install on PATH
    env = { CLAUDE_CODE_MAX_OUTPUT_TOKENS = "8000" }
    cwd = "/path/to/workdir"            # optional
"""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from hobbes.watterson.providers.errors import ProviderError, UnknownAgentError

#: The override file used when ``HOBBES_AGENTS_FILE`` is not set; it sits
#: beside the CLI's default cache under ``~/.watterson``.
DEFAULT_AGENTS_FILE = "~/.watterson/agents.toml"

#: The locked adapters' npm project, ``<repo root>/adapters``. Located the
#: way ``hobbes.extract`` finds ``tsextract/``: this file sits at
#: ``pipeline/src/hobbes/providers/registry.py``, four levels below the root.
ADAPTERS_DIR = Path(__file__).resolve().parents[5] / "adapters"

#: What to do when a locked adapter's bin is missing.
ADAPTERS_INSTALL_HINT = "run `cd adapters && npm ci` at the repo root"


@dataclass(frozen=True)
class LockedAdapter:
    """An ACP adapter pinned in ``adapters/package.json``.

    ``harness`` is the npm package the adapter bundles its harness from, and
    ``cli`` the user's own install of that harness, for comparison.
    """

    agent: str
    package: str
    bin: str
    harness: str
    cli: str


LOCKED_ADAPTERS: tuple[LockedAdapter, ...] = (
    LockedAdapter(
        "claude", "@agentclientprotocol/claude-agent-acp", "claude-agent-acp",
        "@anthropic-ai/claude-agent-sdk", "claude",
    ),
    LockedAdapter(
        "codex", "@agentclientprotocol/codex-acp", "codex-acp", "@openai/codex", "codex",
    ),
)


def adapter_bin(adapter: LockedAdapter, adapters_dir: Path | None = None) -> Path:
    """Where *adapter*'s bin is after ``npm ci`` in *adapters_dir*."""
    return (adapters_dir or ADAPTERS_DIR) / "node_modules" / ".bin" / adapter.bin


@dataclass(frozen=True)
class AgentSpec:
    """How to launch one ACP agent as a stdio subprocess."""

    name: str
    command: tuple[str, ...]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    source: str = "built-in"
    #: How to install ``command[0]`` when it is missing, if known.
    install_hint: str | None = None

    def executable(self) -> str | None:
        """Where ``command[0]`` resolves (on PATH, or as a path), or None."""
        return shutil.which(self.command[0])


BUILTIN_AGENTS: dict[str, AgentSpec] = {
    spec.name: spec
    for spec in (
        *(
            AgentSpec(a.agent, (str(adapter_bin(a)),), install_hint=ADAPTERS_INSTALL_HINT)
            for a in LOCKED_ADAPTERS
        ),
        AgentSpec("gemini", ("gemini", "--acp")),
    )
}


def agents_file() -> Path:
    """The override file this process reads (it need not exist)."""
    return Path(os.environ.get("HOBBES_AGENTS_FILE") or DEFAULT_AGENTS_FILE).expanduser()


def _spec_from_table(name: str, table: object, source: str) -> AgentSpec:
    if not isinstance(table, dict):
        raise ProviderError(f"{source}: [agents.{name}] must be a table")
    command = table.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(part, str) and part for part in command)
    ):
        raise ProviderError(f"{source}: agents.{name}.command must be a non-empty list of strings")
    env = table.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        raise ProviderError(f"{source}: agents.{name}.env must map strings to strings")
    cwd = table.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        raise ProviderError(f"{source}: agents.{name}.cwd must be a string")
    unknown = set(table) - {"command", "env", "cwd"}
    if unknown:
        raise ProviderError(f"{source}: agents.{name} has unknown keys: {', '.join(sorted(unknown))}")
    return AgentSpec(name, tuple(command), dict(env), cwd, source)


def load_registry(path: Path | None = None) -> dict[str, AgentSpec]:
    """The built-in agents with the override file's entries laid over them."""
    registry = dict(BUILTIN_AGENTS)
    path = path or agents_file()
    if not path.is_file():
        return registry
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProviderError(f"{path}: {exc}") from exc
    tables = data.get("agents", {})
    if not isinstance(tables, dict):
        raise ProviderError(f"{path}: [agents] must be a table of agent tables")
    for name, table in tables.items():
        registry[name] = _spec_from_table(name, table, str(path))
    return registry


def get_agent(name: str, registry: dict[str, AgentSpec] | None = None) -> AgentSpec:
    """Look *name* up in *registry* (default: ``load_registry()``)."""
    registry = load_registry() if registry is None else registry
    try:
        return registry[name]
    except KeyError:
        known = ", ".join(sorted(registry)) or "none"
        raise UnknownAgentError(f"unknown agent {name!r} (known: {known})") from None
