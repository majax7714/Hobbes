"""Drive an ACP agent harness as a client: spawn, prompt, stream, cancel, close.

The only module that imports the ACP Python SDK (``agent-client-protocol``,
pinned in pyproject per DEC-004). It spawns the agent named by an
``AgentSpec`` as a stdio subprocess, runs ``initialize`` and
``session/new``, sends prompts, and turns the agent's session updates into
``hobbes.watterson.providers.events`` dataclasses. The harness owns the agent loop;
nothing here plans, calls tools or retries.

The client advertises no file-system or terminal capabilities, so the
harness uses its own. Permission requests go to a caller callback that
returns an option id (default: ``deny_all``); each carries the tool call's
kind, raw input and paths, merged with what the call's earlier updates
said. ``modes`` names the session modes to switch to after
``session/new``, in order of preference (DEC-007); the first one the agent
offers is set with ``session/set_mode``. ``mcp_servers`` are stdio MCP
servers the harness launches for the session (DEC-008). ``meta`` is sent
as ``session/new``'s ``_meta`` (e.g. Claude's ``claudeCode.options``, DEC-010).

Process handling differs from the SDK's ``spawn_agent_process`` on purpose:
the agent gets the caller's whole environment (subscription harnesses read
their login and config from it; the SDK passes a trimmed set), runs in its
own process group so a Ctrl-C reaches us and not the agent, has its stderr
drained so a chatty agent cannot block on a full pipe, and on close the
whole group is reaped, so an ``npx`` wrapper leaves no orphaned children.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import signal
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import acp
from acp import schema

from hobbes import __version__
from hobbes.watterson.providers.errors import AgentError, ProviderError
from hobbes.watterson.providers.events import (
    Event,
    FileDiff,
    PermissionDecision,
    PermissionOption,
    PermissionRequest,
    Plan,
    PlanEntry,
    TextChunk,
    ThoughtChunk,
    ToolCall,
    ToolCallUpdate,
    TurnEnded,
    deny_all,
)
from hobbes.watterson.providers.registry import AgentSpec

#: Called for each permission request; returns the chosen option id, or
#: None to cancel the request. May be a plain function or a coroutine.
PermissionCallback = Callable[[PermissionRequest], "str | None | Awaitable[str | None]"]

#: JSON-RPC code ACP agents use when the harness is not logged in.
_AUTH_REQUIRED = -32000
_STDERR_LINES = 40
_DONE = object()


@dataclass(frozen=True)
class StdioMcpServer:
    """An MCP server the harness starts over stdio for the session.

    ``command`` must be an absolute path (ACP's rule); ``env`` is added to
    the server's environment by the harness.
    """

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)

    def to_acp(self) -> schema.McpServerStdio:
        return schema.McpServerStdio(
            name=self.name,
            command=self.command,
            args=list(self.args),
            env=[schema.EnvVariable(name=k, value=v) for k, v in self.env.items()],
        )


class _Client:
    """The ACP ``Client`` side the SDK dispatches agent requests to."""

    def __init__(self, session: AgentSession) -> None:
        self._session = session

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        if session_id != self._session.session_id:
            return
        if isinstance(update, (schema.ToolCallStart, schema.ToolCallProgress)):
            known = self._session._calls.setdefault(update.tool_call_id, {})
            known.update(_tool_fields(update))
        elif isinstance(update, schema.CurrentModeUpdate):
            self._session.mode = update.current_mode_id
        event = _event_from_update(update)
        if event is not None:
            self._session._emit(event)

    async def request_permission(
        self, session_id: str, tool_call: Any, options: list[Any], **kwargs: Any
    ) -> schema.RequestPermissionResponse:
        known = {
            **self._session._calls.get(tool_call.tool_call_id, {}),
            **_tool_fields(tool_call),
        }
        request = PermissionRequest(
            tool_call_id=tool_call.tool_call_id,
            title=known.get("title"),
            options=tuple(PermissionOption(o.option_id, o.name, o.kind) for o in options),
            kind=known.get("kind"),
            raw_input=known.get("raw_input"),
            paths=known.get("paths", ()),
            meta=known.get("meta"),
            diffs=known.get("diffs", ()),
        )
        option_id = await self._session._decide(request)
        self._session._emit(PermissionDecision(request, option_id))
        if option_id is None:
            return schema.RequestPermissionResponse(outcome=schema.DeniedOutcome(outcome="cancelled"))
        return schema.RequestPermissionResponse(
            outcome=schema.AllowedOutcome(outcome="selected", option_id=option_id)
        )


def _tool_fields(call: Any) -> dict[str, Any]:
    """The fields a tool call start, update or permission request sets."""
    fields: dict[str, Any] = {}
    if call.title:
        fields["title"] = call.title
    if call.kind:
        fields["kind"] = call.kind
    if call.raw_input is not None:
        fields["raw_input"] = call.raw_input
    if call.field_meta:
        fields["meta"] = call.field_meta
    if paths := _paths(call):
        fields["paths"] = paths
    if diffs := _diffs(call.content):
        fields["diffs"] = diffs
    return fields


def _paths(call: Any) -> tuple[str, ...]:
    """Every file a tool call names: its locations and diff targets, once each."""
    paths = [loc.path for loc in call.locations or ()]
    paths += [c.path for c in call.content or () if isinstance(c, schema.FileEditToolCallContent)]
    return tuple(dict.fromkeys(paths))


def _diffs(content: Any) -> tuple[FileDiff, ...]:
    return tuple(FileDiff(c.path, c.old_text, c.new_text)
                 for c in content or () if isinstance(c, schema.FileEditToolCallContent))


def _text_of(content: Any) -> str | None:
    return content.text if isinstance(content, schema.TextContentBlock) else None


def _output_text(content: Any) -> str | None:
    """The text blocks of a tool call's content, joined; None when it has none."""
    texts = [
        text for c in content or ()
        if isinstance(c, schema.ContentToolCallContent) and (text := _text_of(c.content))
    ]
    return "\n".join(texts) if texts else None


def _event_from_update(update: Any) -> Event | None:
    """Our event for one ACP session update, or None for kinds we drop."""
    if isinstance(update, schema.AgentMessageChunk):
        text = _text_of(update.content)
        return TextChunk(text) if text else None
    if isinstance(update, schema.AgentThoughtChunk):
        text = _text_of(update.content)
        return ThoughtChunk(text) if text else None
    if isinstance(update, schema.ToolCallStart):
        return ToolCall(update.tool_call_id, update.title, update.kind, update.status, update.raw_input,
                        _paths(update), _diffs(update.content))
    if isinstance(update, schema.ToolCallProgress):
        return ToolCallUpdate(
            update.tool_call_id, update.status, update.title,
            update.raw_input, update.raw_output, _output_text(update.content),
            _paths(update), _diffs(update.content),
        )
    if isinstance(update, schema.AgentPlanUpdate):
        return Plan(tuple(PlanEntry(e.content, e.status, e.priority) for e in update.entries))
    return None


class AgentSession:
    """One ACP agent subprocess with one session open on it.

    Use as ``async with AgentSession(spec) as session:``, then iterate
    ``session.prompt(text)`` per turn. Leaving the block closes the session
    and reaps the process group.
    """

    def __init__(
        self,
        spec: AgentSpec,
        *,
        cwd: str | os.PathLike[str] | None = None,
        on_permission: PermissionCallback = deny_all,
        modes: Sequence[str] = (),
        mcp_servers: Sequence[StdioMcpServer] = (),
        meta: Mapping[str, Any] | None = None,
        start_timeout: float = 120.0,
        cancel_timeout: float = 5.0,
        shutdown_timeout: float = 2.0,
    ) -> None:
        self.spec = spec
        # ACP wants an absolute session cwd; the process starts there too
        # unless the spec pins its own.
        self.cwd = os.path.abspath(cwd or spec.cwd or os.getcwd())
        self._on_permission = on_permission
        self._want_modes = tuple(modes)
        self._mcp_servers = tuple(mcp_servers)
        self._meta = dict(meta or {})
        #: The session's mode, and the modes the agent offers (empty when
        #: it has none); set once the session opens.
        self.mode: str | None = None
        self.available_modes: tuple[str, ...] = ()
        self._calls: dict[str, dict[str, Any]] = {}
        self._start_timeout = start_timeout
        self._cancel_timeout = cancel_timeout
        self._shutdown_timeout = shutdown_timeout
        self.session_id: str | None = None
        self.agent_name: str | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._conn: Any = None
        self._stderr: deque[str] = deque(maxlen=_STDERR_LINES)
        self._stderr_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[Any] | None = None
        self._cancelling = False

    @property
    def pid(self) -> int | None:
        """The agent process's pid (also its process-group id)."""
        return self._process.pid if self._process else None

    async def __aenter__(self) -> AgentSession:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def start(self) -> None:
        """Spawn the agent, then ``initialize`` and open a session."""
        if self._process is not None:
            raise ProviderError("session already started")
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self.spec.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **self.spec.env},
                cwd=self.spec.cwd or self.cwd,
                start_new_session=True,
            )
        except OSError as exc:
            hint = f"; {self.spec.install_hint}" if self.spec.install_hint else ""
            raise AgentError(
                f"{self.spec.name}: cannot start {self.spec.command[0]!r}: {exc}{hint}"
            ) from exc
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        self._conn = acp.connect_to_agent(_Client(self), self._process.stdin, self._process.stdout)
        try:
            async with asyncio.timeout(self._start_timeout):
                init = await self._call(
                    "initialize",
                    self._conn.initialize(
                        protocol_version=acp.PROTOCOL_VERSION,
                        client_capabilities=schema.ClientCapabilities(),
                        client_info=schema.Implementation(name="hobbes", version=__version__),
                    ),
                )
                if init.protocol_version != acp.PROTOCOL_VERSION:
                    raise AgentError(
                        f"{self.spec.name}: speaks ACP protocol {init.protocol_version}, "
                        f"this client speaks {acp.PROTOCOL_VERSION}"
                    )
                if init.agent_info is not None:
                    self.agent_name = f"{init.agent_info.name} {init.agent_info.version}"
                servers = [s.to_acp() for s in self._mcp_servers]
                session = await self._call(
                    "session/new", self._conn.new_session(cwd=self.cwd, mcp_servers=servers, **self._meta)
                )
                self.session_id = session.session_id
                await self._set_mode(session.modes)
        except TimeoutError:
            await self.close()
            raise AgentError(
                f"{self.spec.name}: no answer within {self._start_timeout:.0f}s of starting",
                stderr_tail=self.stderr_tail(),
            ) from None
        except BaseException:
            await self.close()
            raise

    async def prompt(self, text: str) -> AsyncIterator[Event]:
        """Send one prompt and yield its events; the last is ``TurnEnded``.

        Leaving the iteration early (break, an exception, task
        cancellation) cancels the turn on the agent. Wrap the iterator in
        ``contextlib.aclosing`` when you may break out of it, so that
        happens at once rather than when the generator is collected.
        """
        if self.session_id is None:
            raise ProviderError("session not started")
        if self._queue is not None:
            raise ProviderError("a prompt is already running on this session")
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._queue = queue
        self._calls.clear()
        self._cancelling = False
        turn = asyncio.ensure_future(
            self._conn.prompt(session_id=self.session_id, prompt=[acp.text_block(text)])
        )
        # Done after every update: the SDK's prompt() waits for in-flight
        # session/update handlers before it returns.
        turn.add_done_callback(lambda _: queue.put_nowait(_DONE))
        try:
            while (item := await queue.get()) is not _DONE:
                yield item
            response = await self._call("session/prompt", turn)
            yield TurnEnded(response.stop_reason)
        finally:
            if not turn.done():
                await self._abort_turn(turn)
            self._queue = None

    async def cancel(self) -> None:
        """Ask the agent to stop the running turn. The turn still ends with
        ``TurnEnded`` (stop_reason ``cancelled``); permission requests that
        arrive meanwhile are answered as cancelled."""
        if self._queue is None or self._cancelling:
            return
        self._cancelling = True
        with contextlib.suppress(Exception):
            await self._conn.cancel(session_id=self.session_id)

    async def close(self) -> None:
        """Close the connection and reap the agent's whole process group."""
        process, self._process = self._process, None
        if self._conn is not None:
            with contextlib.suppress(Exception):
                await self._conn.close()
            self._conn = None
        if process is None:
            return
        if process.stdin is not None:
            with contextlib.suppress(Exception):
                process.stdin.close()
        if not await self._wait(process):
            _signal_group(process.pid, signal.SIGTERM)
            if not await self._wait(process):
                _signal_group(process.pid, signal.SIGKILL)
                await process.wait()
        # The leader is gone; take any children it left in its group.
        _signal_group(process.pid, signal.SIGTERM)
        if self._stderr_task is not None:
            with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._stderr_task, timeout=1.0)
            self._stderr_task = None

    def stderr_tail(self) -> str:
        """The agent's last stderr lines, for error messages."""
        return "\n".join(self._stderr)

    # -- internals -----------------------------------------------------

    async def _set_mode(self, state: Any) -> None:
        """Switch to the first wanted mode the agent offers, if any."""
        if state is None:
            return
        self.available_modes = tuple(m.id for m in state.available_modes)
        self.mode = state.current_mode_id
        want = next((m for m in self._want_modes if m in self.available_modes), None)
        if want is not None and want != self.mode:
            await self._call(
                "session/set_mode",
                self._conn.set_session_mode(session_id=self.session_id, mode_id=want),
            )
            self.mode = want

    def _emit(self, event: Event) -> None:
        if self._queue is not None:
            self._queue.put_nowait(event)

    async def _decide(self, request: PermissionRequest) -> str | None:
        if self._cancelling:
            return None
        choice = self._on_permission(request)
        if inspect.isawaitable(choice):
            choice = await choice
        if self._cancelling or choice not in {o.id for o in request.options}:
            return None
        return choice

    async def _abort_turn(self, turn: asyncio.Future[Any]) -> None:
        await self.cancel()
        done, _ = await asyncio.wait({turn}, timeout=self._cancel_timeout)
        if not done:
            turn.cancel()
        with contextlib.suppress(BaseException):
            await turn

    async def _call(self, what: str, awaitable: Awaitable[Any]) -> Any:
        """Await an ACP request, turning SDK failures into ``AgentError``."""
        try:
            return await awaitable
        except acp.RequestError as exc:
            hint = ""
            if exc.code == _AUTH_REQUIRED:
                hint = " (log in with the harness's own CLI first, e.g. `claude` or `codex login`)"
            detail = f": {exc.data}" if exc.data else ""
            raise AgentError(
                f"{self.spec.name}: {what} failed: {exc}{detail}{hint}",
                stderr_tail=self.stderr_tail(),
            ) from exc
        except ConnectionError as exc:
            code = None
            if self._process is not None:
                with contextlib.suppress(asyncio.TimeoutError):
                    code = await asyncio.wait_for(self._process.wait(), timeout=1.0)
            if self._stderr_task is not None:
                await asyncio.wait({self._stderr_task}, timeout=1.0)
            exited = f" (exit code {code})" if code is not None else ""
            raise AgentError(
                f"{self.spec.name}: agent disconnected during {what}{exited}",
                stderr_tail=self.stderr_tail(),
            ) from exc

    async def _drain_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        stream = self._process.stderr
        while line := await stream.readline():
            self._stderr.append(line.decode("utf-8", "replace").rstrip())

    async def _wait(self, process: asyncio.subprocess.Process) -> bool:
        try:
            await asyncio.wait_for(process.wait(), timeout=self._shutdown_timeout)
        except asyncio.TimeoutError:
            return False
        return True


def _signal_group(pgid: int, sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)


async def run_prompt(
    spec: AgentSpec,
    prompt: str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    on_permission: PermissionCallback = deny_all,
    modes: Sequence[str] = (),
    mcp_servers: Sequence[StdioMcpServer] = (),
) -> AsyncIterator[Event]:
    """One-shot: start *spec*, send *prompt*, yield its events, close."""
    async with AgentSession(
        spec, cwd=cwd, on_permission=on_permission, modes=modes, mcp_servers=mcp_servers
    ) as session:
        async with contextlib.aclosing(session.prompt(prompt)) as events:
            async for event in events:
                yield event
