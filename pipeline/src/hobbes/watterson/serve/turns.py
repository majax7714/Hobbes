"""One prompt turn: our provider events in, opencode session events out.

opencode's TUI edits an assistant message part by part, and drops events
aimed at a part that does not exist yet (``client/src/solid/data.ts`` at
v2.0.29), so ``Turn`` keeps its order:

- text and reasoning: ``*.started`` (with the part's ``ordinal`` among its
  own type), ``*.delta``\\s, ``*.ended`` with the full text, closed when
  anything else starts;
- a tool: ``tool.input.started`` then ``tool.called`` (it is "running"),
  then ``tool.success`` or ``tool.failed``. Both are sent once the call's
  input is known (ACP harnesses often start a call with an empty input and
  stream it in; a read or an edit waits for the file it names too), or
  when its status moves on, or when a permission request names it. A read
  or an edit that names a file uses the TUI's own ``read`` / ``edit``
  views (``input.path``; an edit's success carries ``metadata.files``, a
  patch from its diff blocks, ``patches``); a call that ``tasks`` picks by
  its title (a coordinator's ``dispatch``, DEC-022) uses the subagent view
  (``task``), linked to its worker's session by ``link``; other tools get
  its generic row;
- a plan becomes a ``session.synthetic`` notice: the TUI has no plan view;
- the end: open parts closed, unfinished tools failed, ``step.ended``, and
  ``execution.succeeded``, ``.interrupted`` (cancelled) or ``.failed``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hobbes.watterson.providers.events import (
    Event, PermissionRequest, Plan, TextChunk, ThoughtChunk, ToolCall, ToolCallUpdate, TurnEnded,
)
from hobbes.watterson.serve.patches import file_diffs

#: ``publish(type, data)`` sends one event to every TUI listening.
Publish = Callable[[str, dict[str, Any]], None]

#: ACP stop reasons to opencode step finishes (``cancelled`` hides the footer).
FINISH = {"end_turn": "stop", "max_tokens": "length", "max_turn_requests": "length",
          "refusal": "content-filter", "cancelled": "unknown"}
#: Tool names the TUI draws with its own layouts, which read input keys our
#: harnesses do not send (``tool_name`` maps the ones it can fill); other
#: names get its generic ``name [k=v, …]`` row.
RESERVED_TOOLS = frozenset({
    "shell", "bash", "glob", "read", "grep", "webfetch", "websearch", "write", "edit",
    "subagent", "task", "execute", "patch", "apply_patch", "question", "skill",
})
ZERO_TOKENS = {"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}}


def now_ms() -> int:
    return int(time.time() * 1000)


#: ACP kinds the TUI has a view for once the call names a file.
FILE_VIEWS = frozenset({"read", "edit"})


def tool_name(kind: str | None, raw_input: Any, paths: tuple[str, ...] = ()) -> str:
    """``bash`` for a command the TUI can show as one, ``read`` / ``edit``
    for a call that names its file; else the ACP kind, kept off the TUI's
    reserved names."""
    if kind == "execute" and isinstance(raw_input, dict) and isinstance(raw_input.get("command"), str):
        return "bash"
    if kind in FILE_VIEWS and paths:
        return kind
    name = kind or "tool"
    return f"{name}_tool" if name in RESERVED_TOOLS else name


def task_input(raw: dict[str, Any]) -> dict[str, Any]:
    """A dispatch's input for the subagent view: ``description`` and
    ``subagent_type`` (the role), plus the whole brief as ``prompt``. Codex
    names the server and wraps the arguments (as ``hobbes.watterson.dispatch`` reads it)."""
    given = raw.get("arguments") if "server" in raw and isinstance(raw.get("arguments"), dict) else raw
    brief = str(given.get("brief", ""))
    return {"description": (brief.strip().splitlines() or [""])[0][:80], "subagent_type": str(given.get("role", "")),
            "prompt": brief}


def plan_text(plan: Plan) -> str:
    marks = {"completed": "x", "in_progress": "~"}
    return "Plan:\n" + "\n".join(f"[{marks.get(e.status, ' ')}] {e.content}" for e in plan.entries)


class Turn:
    """Translate one turn's events for assistant message ``message_id``."""

    def __init__(self, publish: Publish, session_id: str, message_id: str, root: Path | None = None,
                 tasks: Callable[[str | None], bool] | None = None) -> None:
        self.publish, self.session_id, self.message_id = publish, session_id, message_id
        self.tasks = tasks
        #: the session's directory: patches name files relative to it
        self.root = root or Path.cwd()
        self._open: tuple[str, int] | None = None  # ("text" | "reasoning", ordinal)
        self._buffer = ""
        self._counts = {"text": 0, "reasoning": 0}
        #: tool id -> {"kind", "title", "input", "output", "paths", "diffs", "name",
        #:             "metadata", "stage": "seen" | "called" | "done"}
        self.tools: dict[str, dict[str, Any]] = {}
        self.ended = False

    def _send(self, kind: str, **data: Any) -> None:
        self.publish(kind, {"sessionID": self.session_id, "assistantMessageID": self.message_id, **data})

    def feed(self, event: Event) -> None:
        if isinstance(event, TextChunk):
            self._chunk("text", event.text)
        elif isinstance(event, ThoughtChunk):
            self._chunk("reasoning", event.text)
        elif isinstance(event, ToolCall):
            self._close()
            # A permission request can name the call before its start is fed here.
            tool = self._tool(event.id)
            tool["kind"] = tool["kind"] or event.kind
            tool["title"] = event.title or tool["title"]
            self._learn(event.id, event)
        elif isinstance(event, ToolCallUpdate):
            tool = self._tool(event.id)
            if event.output is not None:
                tool["output"] = event.output
            tool["title"] = event.title or tool["title"]
            self._learn(event.id, event)
        elif isinstance(event, Plan):
            text = plan_text(event)
            self.publish("session.synthetic", {"sessionID": self.session_id, "text": text, "description": text})
        elif isinstance(event, TurnEnded):
            self.finish(event.stop_reason)

    def _tool(self, tool_id: str) -> dict[str, Any]:
        return self.tools.setdefault(tool_id, {"kind": None, "title": None, "input": None, "output": None,
                                               "paths": (), "diffs": (), "name": None, "metadata": None,
                                               "stage": "seen"})

    def _learn(self, tool_id: str, event: ToolCall | ToolCallUpdate) -> None:
        """Merge what *event* says about the call, then run or finish it."""
        tool = self.tools[tool_id]
        if event.raw_input is not None:
            tool["input"] = event.raw_input
        tool["paths"] = tuple(dict.fromkeys(tool["paths"] + event.paths))
        if event.diffs:
            tool["diffs"] = event.diffs
        known = bool(tool["input"]) and (tool["kind"] not in FILE_VIEWS or bool(tool["paths"]))
        if known or event.status in ("in_progress", "completed", "failed"):
            self.call(tool_id)
        self._status(tool_id, event.status)

    def asked(self, request: PermissionRequest) -> None:
        """A permission request names the call: take what it says (the
        harness's details so far, merged), then show the call."""
        tool = self._tool(request.tool_call_id)
        tool["kind"] = tool["kind"] or request.kind
        tool["title"] = tool["title"] or request.title
        if request.raw_input is not None:
            tool["input"] = request.raw_input
        tool["paths"] = tuple(dict.fromkeys(tool["paths"] + request.paths))
        if request.diffs:
            tool["diffs"] = request.diffs
        self.call(request.tool_call_id)

    def call(self, tool_id: str) -> None:
        """Show the tool as running (idempotent); a permission prompt links to it."""
        tool = self._tool(tool_id)
        if tool["stage"] != "seen":
            return
        self._close()
        raw = tool["input"]
        name = tool["name"] = tool_name(tool["kind"], raw, tool["paths"])
        shown = dict(raw) if isinstance(raw, dict) else {}
        if name in FILE_VIEWS:
            shown["path"] = tool["paths"][0]
        if self.tasks is not None and self.tasks(tool["title"]):
            name = tool["name"] = "task"
            shown = task_input(shown)
        self._send("session.tool.input.started", id=tool_id, name=name)
        self._send("session.tool.called", id=tool_id, input=shown, executed=True)
        tool["stage"] = "called"

    def link(self, metadata: dict[str, Any]) -> bool:
        """Give the latest running ``task`` call without one its *metadata*
        (``sessionID``: the worker's session the subagent view opens)."""
        for tool_id, tool in reversed(self.tools.items()):
            if tool["name"] == "task" and tool["stage"] == "called" and tool["metadata"] is None:
                tool["metadata"] = metadata
                self._send("session.tool.progress", id=tool_id, metadata=metadata)
                return True
        return False

    def _status(self, tool_id: str, status: str | None) -> None:
        tool = self.tools[tool_id]
        if status == "completed" and tool["stage"] == "called":
            extra = {}
            if tool["name"] == "edit" and tool["diffs"]:
                extra["metadata"] = {"files": file_diffs(tool["diffs"], self.root, applied=True)}
            if tool["metadata"] is not None:  # the TUI replaces a call's metadata on success
                extra["metadata"] = {**extra.get("metadata", {}), **tool["metadata"]}
            self._send("session.tool.success", id=tool_id, executed=True,
                       content=[{"type": "text", "text": tool["output"] or ""}], **extra)
            tool["stage"] = "done"
        elif status == "failed" and tool["stage"] != "done":
            self._fail_tool(tool_id, tool["output"] or "the tool call failed")

    def _fail_tool(self, tool_id: str, message: str) -> None:
        self.call(tool_id)
        extra = {} if self.tools[tool_id]["metadata"] is None else {"metadata": self.tools[tool_id]["metadata"]}
        self._send("session.tool.failed", id=tool_id, executed=True, error={"type": "tool", "message": message},
                   **extra)
        self.tools[tool_id]["stage"] = "done"

    def _chunk(self, part: str, text: str) -> None:
        if self._open is None or self._open[0] != part:
            self._close()
            self._open = (part, self._counts[part])
            self._counts[part] += 1
            self._send(f"session.{part}.started", ordinal=self._open[1])
        self._buffer += text
        self._send(f"session.{part}.delta", ordinal=self._open[1], delta=text)

    def _close(self) -> None:
        if self._open is not None:
            part, ordinal = self._open
            self._send(f"session.{part}.ended", ordinal=ordinal, text=self._buffer)
            self._open, self._buffer = None, ""

    def _wrap_up(self, finish: str, reason: str) -> None:
        self._close()
        for tool_id, tool in self.tools.items():
            if tool["stage"] != "done":
                self._fail_tool(tool_id, reason)
        self._send("session.step.ended", finish=finish, cost=0, tokens=ZERO_TOKENS)
        self.ended = True

    def finish(self, stop_reason: str) -> None:
        if self.ended:
            return
        self._wrap_up(FINISH.get(stop_reason, "unknown"), f"the turn ended ({stop_reason})")
        if stop_reason == "cancelled":
            self.publish("session.execution.interrupted", {"sessionID": self.session_id, "reason": "user"})
        else:
            self.publish("session.execution.succeeded", {"sessionID": self.session_id})

    def fail(self, message: str) -> None:
        if self.ended:
            return
        self._wrap_up("error", message)
        self.publish("session.execution.failed",
                     {"sessionID": self.session_id, "error": {"type": "provider", "message": message}})
