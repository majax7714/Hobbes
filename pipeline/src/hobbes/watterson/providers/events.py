"""Typed events an ACP agent session yields, and the permission request shape.

Plain frozen dataclasses with no third-party imports: ``acp_session`` turns
the SDK's session updates into these, so callers never see ACP schema types.
Only the updates a caller needs to follow a turn are kept (text, thoughts,
tool calls, the plan, permission decisions, the end of the turn); the rest
(mode, command list, usage, …) are dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TextChunk:
    """A piece of the agent's reply text."""

    text: str


@dataclass(frozen=True)
class ThoughtChunk:
    """A piece of the agent's visible reasoning, when it shares any."""

    text: str


@dataclass(frozen=True)
class FileDiff:
    """An ACP diff block of a tool call: ``path`` (absolute) and its text
    before and after; ``old_text`` is None for a new file. Harnesses often
    send only the changed snippet, not the whole file."""

    path: str
    old_text: str | None
    new_text: str


@dataclass(frozen=True)
class ToolCall:
    """The agent started a tool call (it runs inside the harness, not here).
    ``raw_input`` is the harness's own tool input, when it sends one;
    ``paths`` the files it names (locations and diff targets) and ``diffs``
    its diff blocks."""

    id: str
    title: str
    kind: str | None = None
    status: str | None = None
    raw_input: Any = None
    paths: tuple[str, ...] = ()
    diffs: tuple[FileDiff, ...] = ()


@dataclass(frozen=True)
class ToolCallUpdate:
    """A later state of a tool call; unset fields did not change.
    ``output`` is the text the call's content shows (its text blocks
    joined); ``raw_input`` and ``raw_output`` are the harness's own values;
    ``paths`` and ``diffs`` as in ``ToolCall`` (a non-empty ``diffs``
    replaces the earlier ones, as ACP content does)."""

    id: str
    status: str | None = None
    title: str | None = None
    raw_input: Any = None
    raw_output: Any = None
    output: str | None = None
    paths: tuple[str, ...] = ()
    diffs: tuple[FileDiff, ...] = ()


@dataclass(frozen=True)
class PlanEntry:
    content: str
    status: str
    priority: str


@dataclass(frozen=True)
class Plan:
    """The agent's current plan, sent whole each time it changes."""

    entries: tuple[PlanEntry, ...]


@dataclass(frozen=True)
class PermissionOption:
    """One answer the agent offers; ``kind`` is allow_once, allow_always,
    reject_once or reject_always."""

    id: str
    name: str
    kind: str


@dataclass(frozen=True)
class PermissionRequest:
    """What the agent asks leave to do, passed to the permission callback.

    Besides the title and options, it carries what the tool call says about
    itself, merged over what earlier updates of the same call said (some
    harnesses send the details only when the call starts): ``kind`` (ACP
    tool kind: read, edit, delete, move, search, execute, think, fetch,
    switch_mode, other), ``raw_input`` (the harness's own tool input, e.g.
    ``{"command": …}`` or ``{"file_path": …}``; None when not sent) and
    ``paths`` (every file the call names: its locations and diff targets),
    ``diffs`` (its diff blocks) and ``meta`` (the ACP ``_meta`` the adapter
    attached, e.g. Claude's ``{"claudeCode": {"mcpServer": {"name",
    "source"}}}``; None when not sent).
    """

    tool_call_id: str
    title: str | None
    options: tuple[PermissionOption, ...]
    kind: str | None = None
    raw_input: Any = None
    paths: tuple[str, ...] = ()
    meta: Any = None
    diffs: tuple[FileDiff, ...] = ()


@dataclass(frozen=True)
class PermissionDecision:
    """A permission request and how it was answered: ``option_id`` is the
    option chosen, or None when the request was cancelled."""

    request: PermissionRequest
    option_id: str | None

    @property
    def allowed(self) -> bool:
        chosen = next((o for o in self.request.options if o.id == self.option_id), None)
        return chosen is not None and chosen.kind.startswith("allow")


@dataclass(frozen=True)
class TurnEnded:
    """The last event of a prompt turn. ``stop_reason`` is end_turn,
    max_tokens, max_turn_requests, refusal or cancelled."""

    stop_reason: str


Event = TextChunk | ThoughtChunk | ToolCall | ToolCallUpdate | Plan | PermissionDecision | TurnEnded


#: Reject option ids that let the turn go on, preferred over other rejects of
#: the same kind. codex-acp sends both ``decline`` ("continue without running
#: it") and ``cancel`` (ends the turn) as ``reject_once`` (DEC-007 notes).
CONTINUING_REJECTS = frozenset({"decline"})


def option_of_kind(request: PermissionRequest, kind: str) -> str | None:
    """The first option of ``kind``; among rejects, one that lets the turn go on."""
    matches = [o for o in request.options if o.kind == kind]
    if kind.startswith("reject"):
        matches.sort(key=lambda o: o.id not in CONTINUING_REJECTS)
    return matches[0].id if matches else None


def _first_of_kind(request: PermissionRequest, prefix: str) -> str | None:
    for kind in (f"{prefix}_once", f"{prefix}_always"):
        if (option_id := option_of_kind(request, kind)) is not None:
            return option_id
    return None


def deny_all(request: PermissionRequest) -> str | None:
    """Permission callback that rejects: picks a reject option (once
    before always, one that lets the turn go on first), or cancels the
    request when the agent offers none."""
    return _first_of_kind(request, "reject")


def allow_all(request: PermissionRequest) -> str | None:
    """Permission callback that allows: picks an allow option (once before
    always), or cancels the request when the agent offers none."""
    return _first_of_kind(request, "allow")
