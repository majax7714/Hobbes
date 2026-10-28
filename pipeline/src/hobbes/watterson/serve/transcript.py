"""A session's transcript in opencode's ``SessionMessageInfo`` shape (DEC-013).

``Transcript.apply`` takes each event the server publishes for a session
and edits the message list the way opencode's TUI data layer does
(``client/src/solid/data.ts:671-1107`` at v2.0.29), so a history load
matches what the TUI built live, ids included: a user message is its inbox
id, an assistant message its ``assistantMessageID``, and a notice, switch
or idle marker ``msg_`` plus its event's id suffix. Events of other types
are ignored.

``log_line`` picks what goes to a session's event log on disk: the events
``apply`` reads, minus the streaming deltas (each part's ``.ended`` event
carries its full text). Replaying the log rebuilds the transcript;
``settle`` closes a turn the log ends in the middle of.
"""

from __future__ import annotations

import json
from typing import Any

#: Event types the transcript reads, and the ephemeral ones it does not log.
TYPES = frozenset({
    "session.created", "session.agent.selected", "session.model.selected", "session.synthetic",
    "session.inbox.enqueued", "session.inbox.delivered", "session.step.started", "session.step.ended",
    "session.text.started", "session.text.delta", "session.text.ended",
    "session.reasoning.started", "session.reasoning.delta", "session.reasoning.ended",
    "session.tool.input.started", "session.tool.called", "session.tool.success", "session.tool.failed",
    "session.execution.succeeded", "session.execution.failed", "session.execution.interrupted",
})
DELTAS = frozenset({"session.text.delta", "session.reasoning.delta"})
IDLE = {"session.execution.succeeded": "succeeded", "session.execution.failed": "failed",
        "session.execution.interrupted": "interrupted"}


def message_id(event_id: str) -> str:
    """The id opencode gives a message made from an event (``evt_X`` -> ``msg_X``)."""
    return "msg_" + event_id.removeprefix("evt_")


def log_line(event: dict[str, Any]) -> str | None:
    """The event as one JSON line for the session log, or None if it is not kept."""
    if event["type"] not in TYPES or event["type"] in DELTAS:
        return None
    return json.dumps(event, separators=(",", ":"))


class Transcript:
    """One session's messages, oldest first."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self._index: dict[str, int] = {}
        self._agent: str | None = None

    # -- reading -------------------------------------------------------

    def get(self, mid: str) -> dict[str, Any] | None:
        position = self._index.get(mid)
        return None if position is None else self.messages[position]

    def page(self, limit: int, cursor: str | None = None, order: str = "desc") -> tuple[list[dict], str | None]:
        """Up to *limit* messages and the next page's cursor. ``desc`` (and any
        cursor page) is newest first, older than the cursor's message."""
        if order == "asc" and cursor is None:
            items = self.messages[:limit]
            return items, None
        end = self._index.get(cursor, 0) if cursor else len(self.messages)
        start = max(0, end - limit)
        items = self.messages[start:end][::-1]
        return items, (items[-1]["id"] if start > 0 and items else None)

    # -- applying events -----------------------------------------------

    def apply(self, event: dict[str, Any]) -> None:
        kind, data, at = event["type"], event["data"], event["created"]
        if kind == "session.created":
            self._agent = data.get("agent")
        elif kind == "session.agent.selected":
            self._insert({"id": message_id(event["id"]), "type": "agent-switched", "agent": data["agent"],
                          "previous": self._agent, "time": {"created": at}})
            self._agent = data["agent"]
        elif kind == "session.model.selected":
            self._insert({"id": message_id(event["id"]), "type": "model-switched", "model": data["model"],
                          "previous": data.get("previous"), "time": {"created": at}})
        elif kind == "session.synthetic":
            self._insert({"id": message_id(event["id"]), "type": "synthetic", "text": data["text"],
                          "description": data.get("description"), "time": {"created": at}})
        elif kind == "session.inbox.enqueued":
            item = data["item"]
            if item.get("type") == "user":
                self._insert({"id": data["inboxID"], "type": "user", **item.get("payload", {}),
                              "time": {"created": at}})
        elif kind == "session.inbox.delivered":
            self._deliver(data["inboxID"], at)
        elif kind == "session.step.started":
            active = self._active()
            if active is not None:
                active["time"]["completed"] = at
            self._insert({"id": data["assistantMessageID"], "type": "assistant", "agent": data["agent"],
                          "model": data["model"], "content": [], "time": {"created": data["started"]}})
        elif kind in IDLE:
            idle = {"id": message_id(event["id"]), "type": "idle", "outcome": IDLE[kind], "time": {"created": at}}
            if kind == "session.execution.failed":
                idle["error"] = data.get("error")
            self._insert(idle)
        elif kind in TYPES:
            assistant = self.get(data.get("assistantMessageID", ""))
            if assistant is not None and assistant["type"] == "assistant":
                self._part(assistant, kind, data, at)

    def _part(self, assistant: dict[str, Any], kind: str, data: dict[str, Any], at: int) -> None:
        content = assistant["content"]
        if kind == "session.step.ended":
            assistant["time"]["completed"] = at
            assistant.update({k: data[k] for k in ("finish", "cost", "tokens") if data.get(k) is not None})
        elif kind == "session.text.started":
            content.append({"type": "text", "text": ""})
        elif kind in ("session.text.delta", "session.text.ended"):
            text = _last(content, lambda p: p["type"] == "text")
            if text is not None:
                text["text"] = text["text"] + data["delta"] if kind.endswith("delta") else data["text"]
        elif kind == "session.reasoning.started":
            content.append({"type": "reasoning", "text": "", "time": {"created": at}})
        elif kind in ("session.reasoning.delta", "session.reasoning.ended"):
            part = _last(content, lambda p: p["type"] == "reasoning" and "completed" not in p["time"])
            if part is not None and kind.endswith("delta"):
                part["text"] += data["delta"]
            elif part is not None:
                part["text"], part["time"]["completed"] = data["text"], at
        elif kind == "session.tool.input.started":
            content.append({"type": "tool", "id": data["id"], "name": data["name"], "time": {"created": at},
                            "state": {"status": "streaming", "input": ""}})
        else:
            tool = _last(content, lambda p: p["type"] == "tool" and p["id"] == data["id"])
            if tool is not None:
                _tool(tool, kind, data, at)

    def settle(self, at: int, reason: str = "the Hobbes server stopped during this turn") -> None:
        """Close what a log cut short: unfinished tools fail, the last turn completes."""
        active = self._active()
        if active is None:
            return
        for part in active["content"]:
            if part["type"] == "tool" and part["state"]["status"] in ("streaming", "running"):
                _tool(part, "session.tool.failed", {"error": {"type": "tool", "message": reason}}, at)
        active["time"]["completed"] = at
        active["finish"] = "unknown"

    def _insert(self, item: dict[str, Any]) -> None:
        if item["id"] in self._index:
            return
        item = {k: v for k, v in item.items() if v is not None}  # optional fields are left out
        self._index[item["id"]] = len(self.messages)
        self.messages.append(item)

    def _deliver(self, inbox_id: str, at: int) -> None:
        """A delivered prompt moves to the end, stamped with the delivery time."""
        position = self._index.get(inbox_id)
        if position is None:
            return
        item = self.messages.pop(position)
        item["time"]["created"] = at
        self.messages.append(item)
        self._index = {m["id"]: i for i, m in enumerate(self.messages)}

    def _active(self) -> dict[str, Any] | None:
        return _last(self.messages, lambda m: m["type"] == "assistant" and "completed" not in m["time"])


def _tool(tool: dict[str, Any], kind: str, data: dict[str, Any], at: int) -> None:
    state = tool["state"]
    if kind == "session.tool.called":
        tool["time"]["ran"], tool["executed"] = at, data.get("executed")
        tool["state"] = {"status": "running", "input": data["input"], "metadata": {}}
    elif kind == "session.tool.success" and state["status"] == "running":
        tool["state"] = {"status": "completed", "input": state["input"], "content": data["content"],
                         **({"metadata": data["metadata"]} if "metadata" in data else {})}
        tool["time"]["completed"] = at
    elif kind == "session.tool.failed" and state["status"] in ("streaming", "running"):
        tool["state"] = {"status": "error", "error": data["error"],
                         "input": {} if isinstance(state["input"], str) else state["input"]}
        tool["time"]["completed"] = at


def _last(items: list[dict[str, Any]], match) -> dict[str, Any] | None:
    return next((item for item in reversed(items) if match(item)), None)
