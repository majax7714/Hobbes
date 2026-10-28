"""Attach Hobbes's knowledge tools to an agent session (DEC-008).

The tools are served by hobbes-public's ``hobbes-proxy`` in
``--knowledge-only`` mode: a stdio MCP server with six read-only queries
over ``<repo>/.hobbes/derived/``. No Go code lives in this repo; the binary
is ``$HOBBES_PROXY`` if set, else ``hobbes-proxy`` on ``PATH``.

``server(repo, proxy)`` is the ``StdioMcpServer`` the harness launches,
named ``hobbes`` so the tools match hobbes-public's sessions. The proxy's
mandatory flight journal goes under ``$HOBBES_CACHE_DIR/knowledge``, not
``~/.hobbes/sessions``. ``TITLES`` are the permission-request titles the
locked adapters give those tools (Claude ``mcp__hobbes__<tool>``, Codex
``mcp.hobbes.<tool>``). ``is_own_tool`` also checks what the request says
about its server, so a same-named server from someone else's config is not
taken for ours: Claude's ``_meta.claudeCode.mcpServer`` must be ``hobbes``
with source ``dynamic`` (a server passed in at startup, as we do; a config
file's would read ``user``, ``project`` or ``local``), and Codex's raw input
``{server, tool}`` must name ours. ``RoutePolicy`` allows such requests once
without asking.

Glue outside ``hobbes.extract`` and ``hobbes.watterson.providers``.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from hobbes.watterson.providers import PermissionRequest, StdioMcpServer

SERVER = "hobbes"
#: The tools ``hobbes-proxy --knowledge-only`` serves (hobbes_public@2089e22,
#: ``go/internal/proxy/knowledge.go:69-143``).
TOOLS = (
    "graph_neighborhood",
    "who_calls",
    "tests_guarding",
    "get_module_doc",
    "list_invariants",
    "list_blind_spots",
)
TITLES = frozenset(
    [f"mcp__{SERVER}__{tool}" for tool in TOOLS] + [f"mcp.{SERVER}.{tool}" for tool in TOOLS]
)
NOT_FOUND = "hobbes-proxy not found (set HOBBES_PROXY or put it on PATH)"


def is_own_tool(request: PermissionRequest) -> bool:
    """True when *request* is for one of our knowledge tools on our server."""
    if request.title not in TITLES:
        return False
    meta = request.meta if isinstance(request.meta, dict) else {}
    claude = meta.get("claudeCode")
    server = claude.get("mcpServer") if isinstance(claude, dict) else None
    if server is not None and (
        not isinstance(server, dict) or (server.get("name"), server.get("source")) != (SERVER, "dynamic")
    ):
        return False
    raw = request.raw_input
    if isinstance(raw, dict) and "server" in raw:
        return raw.get("server") == SERVER and raw.get("tool") in TOOLS
    return True


def find_proxy(env: Mapping[str, str] = os.environ) -> str | None:
    """The proxy binary's absolute path, or None when there is none."""
    named = env.get("HOBBES_PROXY")
    if named:
        path = Path(named).expanduser()
        return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
    found = shutil.which("hobbes-proxy", path=env.get("PATH"))
    return str(Path(found).resolve()) if found else None


def log_dir(env: Mapping[str, str] = os.environ) -> Path:
    """Where the proxy's flight journal goes: ``$HOBBES_CACHE_DIR/knowledge``."""
    cache = env.get("HOBBES_CACHE_DIR") or "~/.watterson/cache"
    return Path(cache).expanduser() / "knowledge"


def server(repo: str | Path, proxy: str, logs: Path | None = None,
           env: Mapping[str, str] | None = None) -> StdioMcpServer:
    """The knowledge-only proxy for *repo*, as the harness should launch it,
    with *env* added to its environment."""
    return StdioMcpServer(
        SERVER,
        proxy,
        (
            "serve", "--repo", str(Path(repo).resolve()), "--role", "developer",
            "--knowledge-only", "--log-dir", str(logs or log_dir()),
        ),
        dict(env or {}),
    )
