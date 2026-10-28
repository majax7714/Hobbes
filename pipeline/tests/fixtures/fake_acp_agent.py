"""A tiny ACP agent for the provider-layer tests, built on the SDK's agent side.

Run as a subprocess (``python fake_acp_agent.py``); it speaks ACP on stdio.
Each prompt turn:

1. sends a one-entry plan;
2. starts one tool call and asks permission for it (allow_once / reject_once);
3. marks the tool call completed when allowed, failed otherwise;
4. echoes the prompt back word by word as agent text chunks, then
   ``[permission: allowed|denied|cancelled]``, and ends the turn.

A prompt containing ``hang`` echoes its first word, then waits until the
client sends ``session/cancel`` and ends the turn as ``cancelled``.

The prompt ``cwd?`` replies ``session=<the session/new cwd>
process=<the agent process's cwd>`` and ends the turn.

The prompt ``write <path> <text…>`` writes ``<text…>`` plus a newline to
``<path>`` under the session cwd, standing in for an agent's edit, replies
``wrote <path>`` and ends the turn.

Permission prompts with details (DEC-007), each answered with
``[permission: <option id>|cancelled]``; the options are ``yes``
(allow_once), ``always`` (allow_always) and ``no`` (reject_once):

- ``edit <path>``: an edit tool call with the path as a location, a diff
  and ``rawInput {"file_path": <abs path>}``, all in the request;
- ``run <command…>``: an execute tool call, ``rawInput {"command": …}``;
- ``late-edit <path>``: the details arrive only in the tool call's start;
  the permission request carries just its id and title (as Gemini does);
- ``tool <title> [<server>:<source>]``: a tool call of kind ``other``
  titled ``<title>``, as Claude reports an MCP tool (DEC-008); with
  ``<server>:<source>``, the request's ``_meta.claudeCode.mcpServer`` says so.

A prompt whose first line starts with ``[hobbes]`` (the DEC-009 label)
first replies ``label: <that line>`` on a line of its own, then handles the
text after the blank line as the prompt.

A prompt with a ``[hobbes brief]``, ``[hobbes job]`` or ``[hobbes request]``
line (a DEC-022 worker or coordinator prompt, a DEC-023 mapper's) first
replies ``role: <its first line>`` on a line of its own, then handles the
text after that line as the prompt.

A prompt with `` && `` runs each part in turn as its own prompt, in one
turn; the turn ends with the last part's stop reason.

The prompt ``call <server> <tool> <json arguments>`` starts the
``session/new`` stdio MCP server named ``<server>``, calls ``<tool>``
through it (no permission asked) and replies ``called <tool>: <its text>``,
plus `` [error]`` when the tool says so. It reports the call as Claude
reports an MCP tool: titled ``mcp__<server>__<tool>``, kind ``other``, the
arguments as ``rawInput``, completed with the reply as its content.

The prompt ``mcp?`` replies with the ``session/new`` MCP servers as JSON
(``[{"name", "command", "args", "env"}]``).

The prompt ``meta?`` replies with the ``session/new`` ``_meta`` as JSON
(``{}`` when none was sent).

The prompt ``output <text…>`` runs one tool call without asking: it starts
with ``rawInput {"text": <text…>}`` and completes with ``<text…>`` as text
content and ``rawOutput {"length": <len>}``, then ends the turn.

``FAKE_AGENT_MODES`` (comma-separated, the first is current) makes
``session/new`` offer those session modes; ``session/set_mode`` switches
and the prompt ``mode?`` replies ``mode=<current>``.

When ``FAKE_AGENT_CHILD_PIDFILE`` is set, the agent first starts a
long-sleeping child and writes its pid there, standing in for the node
process an ``npx`` wrapper leaves behind; the test checks the client reaps it.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import acp
from acp import schema


class FakeAgent:
    def __init__(self) -> None:
        self._conn: Any = None
        self._cancelled: dict[str, asyncio.Event] = {}
        self._cwd: dict[str, str] = {}
        self._calls = 0
        self._mcp: dict[str, list[Any]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._modes = [m for m in os.environ.get("FAKE_AGENT_MODES", "").split(",") if m]
        self._mode: dict[str, str] = {}

    def on_connect(self, conn: Any) -> None:
        self._conn = conn

    async def initialize(self, protocol_version: int, **kwargs: Any) -> schema.InitializeResponse:
        return schema.InitializeResponse(
            protocol_version=acp.PROTOCOL_VERSION,
            agent_info=schema.Implementation(name="fake-agent", version="0.0.1"),
        )

    async def new_session(self, cwd: str, **kwargs: Any) -> schema.NewSessionResponse:
        session_id = f"fake-{len(self._cancelled) + 1}"
        self._cancelled[session_id] = asyncio.Event()
        self._cwd[session_id] = cwd
        self._mcp[session_id] = list(kwargs.get("mcp_servers") or [])
        self._meta[session_id] = {k: v for k, v in kwargs.items()
                                  if k not in ("mcp_servers", "additional_directories")}
        # Not part of any turn: the client must drop it, not leak it into one.
        await self._conn.session_update(session_id, acp.update_agent_message_text(f"cwd={cwd}"))
        if not self._modes:
            return schema.NewSessionResponse(session_id=session_id)
        self._mode[session_id] = self._modes[0]
        modes = schema.SessionModeState(
            current_mode_id=self._modes[0],
            available_modes=[schema.SessionMode(id=m, name=m) for m in self._modes],
        )
        return schema.NewSessionResponse(session_id=session_id, modes=modes)

    async def set_session_mode(self, session_id: str, mode_id: str, **kwargs: Any) -> schema.SetSessionModeResponse:
        if mode_id not in self._modes:
            raise acp.RequestError.invalid_params({"mode_id": mode_id})
        self._mode[session_id] = mode_id
        return schema.SetSessionModeResponse()

    async def prompt(self, session_id: str, prompt: list[Any], **kwargs: Any) -> schema.PromptResponse:
        text = " ".join(block.text for block in prompt if getattr(block, "text", None))
        cancelled = self._cancelled[session_id]
        cancelled.clear()
        say = self._conn.session_update

        if text.startswith("[hobbes]"):
            label, _, text = text.partition("\n\n")
            await say(session_id, acp.update_agent_message_text(f"label: {label}\n"))

        for marker in ("\n[hobbes brief]\n", "\n[hobbes job]\n", "\n[hobbes request]\n"):
            if marker in text:
                head, _, text = text.partition(marker)
                await say(session_id, acp.update_agent_message_text(f"role: {head.splitlines()[0]}\n"))
                break

        if " && " in text:
            response = None
            for part in text.split(" && "):
                response = await self.prompt(session_id, [acp.text_block(part)])
            return response

        if text.startswith("call "):
            _, server, tool, arguments = text.split(" ", 3)
            spec = next(s for s in self._mcp[session_id] if s.name == server)
            self._calls += 1
            call_id, arguments = f"call-{self._calls}", json.loads(arguments)
            await say(session_id, acp.start_tool_call(call_id, f"mcp__{server}__{tool}", kind="other",
                                                      status="in_progress", raw_input=arguments))
            reply, error = await asyncio.to_thread(call_mcp, spec.command, list(spec.args), tool, arguments)
            await say(session_id, acp.update_tool_call(call_id, status="failed" if error else "completed",
                                                       content=[acp.tool_content(acp.text_block(reply))]))
            await say(session_id, acp.update_agent_message_text(f"called {tool}: {reply}{' [error]' * error}"))
            return schema.PromptResponse(stop_reason="end_turn")

        if text.startswith("output "):
            body = text.removeprefix("output ")
            await say(session_id, acp.start_tool_call(
                "tool-3", "Output tool", kind="read", status="in_progress", raw_input={"text": body}))
            await say(session_id, acp.update_tool_call(
                "tool-3", status="completed", content=[acp.tool_content(acp.text_block(body))],
                raw_output={"length": len(body)}))
            return schema.PromptResponse(stop_reason="end_turn")

        if text == "cwd?":
            where = f"session={self._cwd[session_id]} process={os.getcwd()}"
            await say(session_id, acp.update_agent_message_text(where))
            return schema.PromptResponse(stop_reason="end_turn")

        if text == "mode?":
            await say(session_id, acp.update_agent_message_text(f"mode={self._mode.get(session_id)}"))
            return schema.PromptResponse(stop_reason="end_turn")

        if text == "meta?":
            await say(session_id, acp.update_agent_message_text(json.dumps(self._meta[session_id])))
            return schema.PromptResponse(stop_reason="end_turn")

        if text == "mcp?":
            servers = [s.model_dump(exclude_none=True) for s in self._mcp[session_id]]
            await say(session_id, acp.update_agent_message_text(json.dumps(servers)))
            return schema.PromptResponse(stop_reason="end_turn")

        verb, _, arg = text.partition(" ")
        if verb in ("edit", "run", "late-edit", "tool") and arg:
            path = os.path.join(self._cwd[session_id], arg)
            if verb == "run":
                details = {"kind": "execute", "raw_input": {"command": arg}}
            elif verb == "tool":
                arg, _, origin = arg.partition(" ")
                details = {"kind": "other"}
                if origin:
                    name, _, source = origin.partition(":")
                    details["field_meta"] = {"claudeCode": {"mcpServer": {"name": name, "source": source}}}
            else:
                details = {
                    "kind": "edit",
                    "locations": [schema.ToolCallLocation(path=path)],
                    "content": [acp.tool_diff_content(path, "new\n", "old\n")],
                    "raw_input": {"file_path": path},
                }
            title = arg if verb == "tool" else f"{verb} {arg}"
            if verb == "late-edit":
                await say(session_id, acp.start_tool_call("tool-2", title, status="pending", **details))
                tool_call = schema.ToolCallUpdate(tool_call_id="tool-2", title=title)
            else:
                tool_call = schema.ToolCallUpdate(tool_call_id="tool-2", title=title, **details)
            answer = await self._conn.request_permission(
                session_id=session_id,
                tool_call=tool_call,
                options=[
                    schema.PermissionOption(option_id="yes", name="Allow", kind="allow_once"),
                    schema.PermissionOption(option_id="always", name="Always allow", kind="allow_always"),
                    schema.PermissionOption(option_id="no", name="Reject", kind="reject_once"),
                ],
            )
            outcome = answer.outcome
            chosen = outcome.option_id if isinstance(outcome, schema.AllowedOutcome) else "cancelled"
            await say(session_id, acp.update_agent_message_text(f"[permission: {chosen}]"))
            return schema.PromptResponse(stop_reason="end_turn")

        if text.startswith("write "):
            _, path, body = text.split(" ", 2)
            Path(self._cwd[session_id], path).write_text(body + "\n")
            await say(session_id, acp.update_agent_message_text(f"wrote {path}"))
            return schema.PromptResponse(stop_reason="end_turn")

        if "hang" in text:
            await say(session_id, acp.update_agent_message_text(text.split()[0]))
            await cancelled.wait()
            return schema.PromptResponse(stop_reason="cancelled")

        await say(session_id, acp.update_plan([acp.plan_entry("echo the prompt", status="in_progress")]))
        await say(session_id, acp.start_tool_call("tool-1", "Echo tool", kind="other", status="pending"))
        answer = await self._conn.request_permission(
            session_id=session_id,
            tool_call=schema.ToolCallUpdate(tool_call_id="tool-1", title="Echo tool"),
            options=[
                schema.PermissionOption(option_id="yes", name="Allow", kind="allow_once"),
                schema.PermissionOption(option_id="no", name="Reject", kind="reject_once"),
            ],
        )
        outcome = answer.outcome
        if isinstance(outcome, schema.AllowedOutcome):
            verdict = "allowed" if outcome.option_id == "yes" else "denied"
        else:
            verdict = "cancelled"
        status = "completed" if verdict == "allowed" else "failed"
        await say(session_id, acp.update_tool_call("tool-1", status=status))
        for i, word in enumerate(text.split()):
            await say(session_id, acp.update_agent_message_text(word if i == 0 else f" {word}"))
        await say(session_id, acp.update_agent_message_text(f" [permission: {verdict}]"))
        return schema.PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        if session_id in self._cancelled:
            self._cancelled[session_id].set()


def call_mcp(command: str, args: list[str], tool: str, arguments: dict) -> tuple[str, bool]:
    """One tools/call through a stdio MCP server: its text and whether it is an error."""
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": arguments}},
    ]
    out = subprocess.run([command, *args], input="".join(json.dumps(m) + "\n" for m in messages),
                         capture_output=True, text=True, timeout=60)
    reply = [json.loads(line) for line in out.stdout.splitlines()][-1]
    if "error" in reply:
        return reply["error"]["message"], True
    result = reply["result"]
    return "".join(c.get("text", "") for c in result["content"]), bool(result.get("isError"))


async def main() -> None:
    pidfile = os.environ.get("FAKE_AGENT_CHILD_PIDFILE")
    if pidfile:
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with open(pidfile, "w") as fh:
            fh.write(str(child.pid))
    print("fake-agent: ready", file=sys.stderr, flush=True)
    await acp.run_agent(FakeAgent())


if __name__ == "__main__":
    asyncio.run(main())
