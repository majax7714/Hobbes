"""Hobbes hooks in Claude sessions: observe, log, hard deny (DEC-010).

Claude's own judge (auto mode) decides most tool calls without asking the
client (DEC-007). ``SessionHooks`` puts Hobbes in front of it for one
session, writing nothing to disk but its log: ``meta()`` is the
``session/new`` ``_meta`` that gives Claude Code an inline settings object
whose ``PreToolUse``, ``PostToolUse`` and ``PermissionDenied`` hooks run
``hook_client.py``, which hands each hook's input to this object over a
Unix socket in a private temp dir.

- **Observe:** every hook is answered with no opinion, except
- **the hard deny:** in guarded, a ``PreToolUse`` edit of an agent's own
  permission config is denied, with the reason given to the agent.
- **Log:** each tool call, what the harness did with it (ran, denied) and
  any request it escalated to Hobbes (``observe`` wraps the session's
  ``on_permission``), as JSONL under ``$HOBBES_CACHE_DIR/permissions``.
  ``summary()`` is the count DEC-007 asked for.

Hobbes never allows from a hook. Glue outside ``hobbes.extract`` and
``hobbes.watterson.providers``.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

from hobbes.watterson.permissions import Route, annotate
from hobbes.watterson.providers.events import PermissionRequest

EVENTS = ("PreToolUse", "PostToolUse", "PermissionDenied")
CLIENT = Path(__file__).with_name("hook_client.py")
#: Seconds Claude gives the hook; ``hook_client.TIMEOUT`` stays below it.
HOOK_TIMEOUT = 10
#: Claude Code tool names to ACP tool kinds, for ``annotate``.
TOOL_KINDS = {
    "Edit": "edit", "Write": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Bash": "execute", "Read": "read", "Glob": "search", "Grep": "search",
    "WebFetch": "fetch", "WebSearch": "fetch",
}


def log_dir(env: Mapping[str, str] = os.environ) -> Path:
    """Where session permission logs go: ``$HOBBES_CACHE_DIR/permissions``."""
    cache = env.get("HOBBES_CACHE_DIR") or "~/.watterson/cache"
    return Path(cache).expanduser() / "permissions"


def settings(socket_path: str, python: str = sys.executable) -> dict[str, Any]:
    """The Claude Code settings object that installs the hooks."""
    hook = {"type": "command", "command": python, "args": ["-I", "-S", str(CLIENT), socket_path],
            "timeout": HOOK_TIMEOUT}
    return {"hooks": {event: [{"matcher": "*", "hooks": [hook]}] for event in EVENTS}}


def hook_request(payload: Mapping[str, Any]) -> PermissionRequest:
    """A hook's tool call as a ``PermissionRequest``, so ``annotate`` can read it."""
    tool = payload.get("tool_name") if isinstance(payload.get("tool_name"), str) else ""
    return PermissionRequest(
        str(payload.get("tool_use_id", "")), tool, (),
        kind=TOOL_KINDS.get(tool, "other"), raw_input=payload.get("tool_input"),
    )


class SessionHooks:
    """Serves one Claude session's hooks; an async context manager."""

    def __init__(self, route: Route, repo: str | Path, *, agent: str = "claude",
                 test_files: frozenset[str] = frozenset(), logs: Path | None = None) -> None:
        self.route, self.repo, self.agent, self.test_files = route, Path(repo), agent, test_files
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        self.log_path = (logs or log_dir()) / f"{stamp}-{agent}-{uuid.uuid4().hex[:8]}.jsonl"
        self.socket_path = ""
        #: tool call id -> what happened to it: "pre", "ran", "harness_denied",
        #: "asked", "hobbes_denied" (bools).
        self.calls: dict[str, dict[str, bool]] = {}
        self._dir: str | None = None
        self._server: asyncio.Server | None = None
        self._log: TextIO | None = None

    async def __aenter__(self) -> SessionHooks:
        self._dir = tempfile.mkdtemp(prefix="hobbes-hooks-")  # 0700
        self.socket_path = os.path.join(self._dir, "s")
        self._server = await asyncio.start_unix_server(self._handle, self.socket_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("a")
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        if self._dir is not None:
            shutil.rmtree(self._dir, ignore_errors=True)
        if self._log is not None:
            self._log.close()

    def meta(self) -> dict[str, Any]:
        """The ``session/new`` ``_meta`` that installs the hooks."""
        return {"claudeCode": {"options": {"settings": settings(self.socket_path)}}}

    def answer(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Record one hook call and answer it (empty: no opinion)."""
        event = payload.get("hook_event_name")
        request = hook_request(payload)
        call = self.calls.setdefault(request.tool_call_id, {})
        entry: dict[str, Any] = {"event": event, "tool": request.title}
        reply: dict[str, Any] = {}
        if event == "PreToolUse":
            call["pre"] = True
            note = annotate(request, self.repo, self.test_files)
            entry["notes"] = note.lines()
            if self.route is Route.GUARDED and note.agent_config_write:
                call["hobbes_denied"] = True
                reason = "Hobbes denies edits of an agent's own permission config (guarded route)"
                entry["answer"] = "deny"
                reply = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                "permissionDecision": "deny",
                                                "permissionDecisionReason": reason}}
        elif event == "PostToolUse":
            call["ran"] = True
        elif event == "PermissionDenied":
            call["harness_denied"] = True
            entry["reason"] = payload.get("reason")
        self._write(request.tool_call_id, entry)
        return reply

    def observe(self, on_permission):
        """Wrap a permission callback so escalated requests are logged too."""

        async def observed(request: PermissionRequest) -> str | None:
            choice = on_permission(request)
            if inspect.isawaitable(choice):
                choice = await choice
            self.calls.setdefault(request.tool_call_id, {})["asked"] = True
            chosen = next((o for o in request.options if o.id == choice), None)
            self._write(request.tool_call_id, {
                "event": "permission", "tool": request.title,
                "answer": chosen.kind if chosen else "cancelled",
            })
            return choice

        return observed

    def counts(self) -> dict[str, int]:
        seen = [c for c in self.calls.values() if c.get("pre")]
        return {
            "tool_calls": len(seen),
            "decided_alone": sum(1 for c in seen if not c.get("asked") and not c.get("hobbes_denied")),
            "harness_denied": sum(1 for c in self.calls.values() if c.get("harness_denied")),
            "asked": sum(1 for c in self.calls.values() if c.get("asked")),
            "hobbes_denied": sum(1 for c in self.calls.values() if c.get("hobbes_denied")),
        }

    def summary(self) -> str:
        n = self.counts()
        return (f"permissions: {n['tool_calls']} tool call(s); {self.agent} decided "
                f"{n['decided_alone']} alone ({n['harness_denied']} denied); "
                f"{n['asked']} reached Hobbes; Hobbes denied {n['hobbes_denied']} before "
                f"{self.agent}'s judge; log {self.log_path}")

    def _write(self, tool_call_id: str, entry: dict[str, Any]) -> None:
        if self._log is not None:
            self._log.write(json.dumps({"t": round(time.time(), 3), "id": tool_call_id, **entry}) + "\n")
            self._log.flush()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            payload = json.loads(await reader.read())
            reply = self.answer(payload) if isinstance(payload, dict) else {}
            if reply:
                writer.write(json.dumps(reply).encode())
                await writer.drain()
        except (ValueError, OSError):
            pass
        finally:
            writer.close()
