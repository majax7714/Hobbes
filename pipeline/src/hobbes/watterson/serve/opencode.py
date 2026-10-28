"""The opencode v2 API slice the TUI needs, served by Hobbes (DEC-013).

``HobbesServer`` answers the TUI's startup calls, keeps sessions and their
transcripts (``transcript``) and runs each prompt through a
``hobbes.watterson.providers`` session:

- **agents** in the TUI are Hobbes's permission routes (``guarded``,
  ``manual``; DEC-007), so its agent switch picks the route;
- **models** are the agents in Hobbes's registry (claude, codex, …) under a
  ``hobbes`` provider, so its model switch picks the harness;
- a session's harness starts on its first prompt and restarts, with a
  notice, when the route or harness changes; claude sessions carry the
  DEC-010 hooks;
- permission requests become the TUI's prompt (``permission.asked``) and
  wait for its reply. "Always" picks the harness's own ``allow_always``
  option when it offers one: a person chose it (DEC-007);
- the graph panel (DEC-015) asks for views of ``hobbes levels`` over
  opencode's RPC call (``POST /api/rpc/hobbes/view``, ``serve.graph``); the
  server checks ``graph.json`` every ``GRAPH_POLL`` seconds while a TUI is
  listening and pushes ``rpc.hobbes.changed`` when it changes;
- Hobbes itself is off until the app starts it (DEC-016, ``serve.layer``):
  RPC ``hobbes.status``, ``hobbes.start`` and ``hobbes.stop``, with each
  change pushed as ``rpc.hobbes.status``; the panel's views answer only
  while it is on;
- the home screen's logo (DEC-017, ``serve.logo``): RPC ``hobbes.logo``;
- RPC ``hobbes.review`` writes the review page (DEC-018, ``hobbes.watterson.review``)
  and opens it in the browser, while Hobbes is on;
- each session has a mode (DEC-022 slice 3b), RPC ``hobbes.mode``:
  ``default`` runs prompts through the harness as above; ``mapped`` runs
  each prompt as one job of the repo's coordinator role (``hobbes.watterson.lead``),
  fresh per job, with the plan asked as a form (``form.created``); each
  worker runs in a child session (``parentID``, slice 3c), made when it is
  dispatched (queued, if the job's workers are all busy) and opened from
  the coordinator's ``dispatch`` call, which the TUI draws as a subagent.
  A child takes no prompts; interrupting it stops its parent's job.
  ``mapping`` (DEC-023, "edit mapping") runs each prompt as a request to
  the mapper (``hobbes.watterson.mapper``) in the session's harness and route, with
  the knowledge tools while Hobbes is on (waiting for a start in
  progress), and ends with a notice of what was saved. Without
  a session id the RPC reads or
  sets the mode new sessions start in, kept per repo in the store's
  ``home-modes.json``. Each change is pushed as ``rpc.hobbes.mode`` and
  kept in the session's log;
- with a ``store`` directory, each session's events go to
  ``<store>/<session id>.jsonl``, and the sessions of this repo are loaded
  from there at start. A loaded session's harness starts fresh, with the
  same notice as a restart: the harness does not have the earlier turns.

Every startup catalog the TUI loads together must answer, or its prompt is
replaced by an error view, so the ones Hobbes has nothing for are empty.
List responses echo the requested directory byte for byte: the TUI caches
them under the directory the response names. Not built yet: the
knowledge tools and between-turn graph refresh of ``hobbes chat``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hobbes import artifacts
from hobbes.watterson import review
from hobbes.watterson.permissions import Annotation, Route, RoutePolicy, load_test_files, modes_for, once
from hobbes.watterson.providers.events import PermissionRequest, option_of_kind
from hobbes.watterson.serve import ids, logo
from hobbes.watterson.serve.graph import GraphViews
from hobbes.watterson.serve.http import EventStream, Request, Response, Router
from hobbes.watterson.serve.layer import Ingest, Layer, run_ingest
from hobbes.watterson.serve.patches import file_diffs
from hobbes.watterson.serve.transcript import Transcript, log_line
from hobbes.watterson.serve.turns import ZERO_TOKENS, Turn, now_ms

#: The opencode version this API slice follows; the TUI warns on a mismatch.
OPENCODE_VERSION = "2.0.29"
PROVIDER = "hobbes"
PROJECT = "prj_hobbes"
ROUTE_INFO = {
    Route.GUARDED: "harness judges on; Hobbes hard-denies agent-config edits and asks the rest (DEC-007)",
    Route.MANUAL: "every request the harness raises is asked (DEC-007)",
}
#: ACP tool kinds to the TUI's permission layouts (others: "Call tool <title>").
PERMISSION_ACTIONS = {"execute": "shell", "edit": "edit", "delete": "edit", "move": "edit",
                      "read": "read", "search": "grep", "fetch": "webfetch"}
#: Seconds between checks of the repo's graph for the panel.
GRAPH_POLL = 2.0
#: The graph panel's message while Hobbes is not on (DEC-016), before the layer's detail.
OFF_MESSAGES = {"off": "Hobbes is off. Start it with /hobbes, or click hobbes under the prompt.",
                "starting": "Hobbes is starting: ", "failed": "Hobbes did not start: ", "unavailable": ""}
EMPTY_LISTS = ("plugin", "command", "skill", "integration", "reference", "mcp", "shell", "form",
               "permission/request", "websearch/provider")
#: Session modes: the harness as is, the repo's agent mapping (DEC-022), or editing it (DEC-023).
MODES = ("default", "mapped", "mapping")
#: A store line, not an event the TUI sees: the session's mode changed.
MODE_RECORD = "hobbes.mode.selected"
#: In the store: each repo's mode for new sessions (the home screen's choice).
HOME_MODES = "home-modes.json"


@dataclass
class Session:
    id: str
    directory: str
    agent: str
    model: dict[str, Any]
    title: str = "New session"
    created: int = field(default_factory=now_ms)
    updated: int = field(default_factory=now_ms)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    running: bool = False
    turn: Turn | None = None
    backend: Any = None  # AgentSession
    backend_key: tuple[str, str] | None = None  # (harness, route)
    stack: contextlib.AsyncExitStack | None = None
    prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: permission id -> (the request as the TUI sees it, the reply's future)
    pending: dict[str, tuple[dict[str, Any], asyncio.Future[str | None]]] = field(default_factory=dict)
    #: form id -> (the form as the TUI sees it, the answer's future; None when dismissed)
    forms: dict[str, tuple[dict[str, Any], asyncio.Future[dict | None]]] = field(default_factory=dict)
    tasks: set[asyncio.Task[None]] = field(default_factory=set)
    transcript: Transcript = field(default_factory=Transcript)
    #: loaded from the store: its harness has none of the earlier turns
    resumed: bool = False
    mode: str = "default"
    #: the session that dispatched this worker's run (DEC-022), if any
    parent: str | None = None
    #: a running worker's dispatch (the relayed tool call): interrupt cancels it first
    dispatch_task: asyncio.Task | None = None
    #: the mapper requests made in this session (DEC-023), oldest first
    mapper_requests: list[str] = field(default_factory=list)

    def info(self) -> dict[str, Any]:
        info = {"id": self.id, "projectID": PROJECT, "agent": self.agent, "model": self.model,
                "cost": 0, "tokens": ZERO_TOKENS, "title": self.title,
                "time": {"created": self.created, "updated": self.updated},
                "location": {"directory": self.directory}}
        if self.parent is not None:
            info["parentID"] = self.parent
        return info


class HobbesServer:
    """The routes and state behind one TUI; ``router`` goes to ``http.Server``."""

    def __init__(self, repo: str | Path, registry: dict[str, Any], *,
                 log: Callable[[str], None] | None = None,
                 session_factory: Callable[..., Any] | None = None, store: Path | None = None,
                 ingest_log: Path | None = None, ingest: Ingest | None = None) -> None:
        self.repo = str(Path(repo).resolve())
        self.registry = registry
        self.log = log or (lambda line: None)
        self.test_files = load_test_files(Path(self.repo) / ".hobbes" / "derived")
        self.sessions: dict[str, Session] = {}
        self.listeners: set[asyncio.Queue[dict[str, Any] | None]] = set()
        self._session_factory = session_factory
        self.graph = GraphViews(self.repo)
        self.open_page: Callable[[str], bool] = webbrowser.open
        if ingest_log is None:
            ingest_log = Path(os.environ.get("HOBBES_CACHE_DIR") or "~/.watterson/cache").expanduser() / "tui" / "ingest.log"
        self.layer = Layer(self.repo, ingest_log, notify=lambda status: self.publish_rpc("status", status),
                           ingest=ingest or run_ingest)
        self._watch: asyncio.Task[None] | None = None
        #: the mode a new session starts in, chosen on the home screen
        self.next_mode = "default"
        self.store = store
        if store is not None:
            store.mkdir(parents=True, exist_ok=True)
            self._load()
            self.next_mode = self._home_modes().get(self.repo, "default")
            if self.next_mode not in MODES:
                self.next_mode = "default"
        self.router = Router()
        self._routes()

    # -- events --------------------------------------------------------

    def publish(self, kind: str, data: dict[str, Any], located: bool = False) -> None:
        """*located* adds the repo's ``location``: the TUI drops form events without one."""
        event = {"id": ids.event_id(), "type": kind, "created": now_ms(), "data": data}
        if located:
            event["location"] = {"directory": self.repo}
        session = self.sessions.get(data.get("sessionID", ""))
        if session is not None:
            session.transcript.apply(event)
            line = log_line(event) if self.store is not None else None
            if line is not None:
                with (self.store / f"{session.id}.jsonl").open("a") as log:
                    log.write(line + "\n")
        for queue in self.listeners:
            queue.put_nowait(event)

    def _record(self, session: Session, kind: str, data: dict[str, Any]) -> None:
        """A line in the session's log only: state the TUI does not draw."""
        if self.store is not None:
            line = {"id": ids.event_id(), "type": kind, "created": now_ms(), "data": data}
            with (self.store / f"{session.id}.jsonl").open("a") as log:
                log.write(json.dumps(line, separators=(",", ":")) + "\n")

    def _home_modes(self) -> dict[str, str]:
        try:
            found = json.loads((self.store / HOME_MODES).read_text())
        except (OSError, ValueError):
            return {}
        return found if isinstance(found, dict) else {}

    def _save_home_mode(self) -> None:
        if self.store is not None:
            modes = self._home_modes()
            modes[self.repo] = self.next_mode
            (self.store / HOME_MODES).write_text(json.dumps(modes, indent=2, sort_keys=True) + "\n")

    def _load(self) -> None:
        """This repo's sessions from the store, transcripts rebuilt from their logs."""
        for path in sorted(self.store.glob("ses_*.jsonl")):
            try:
                session = self._replay(path)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                self.log(f"skipping session log {path.name}: {exc!r}")
                continue
            if session is not None:
                self.sessions[session.id] = session

    def _replay(self, path: Path) -> Session | None:
        """The session a log holds, or None when it belongs to another repo."""
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if not events or events[0]["type"] != "session.created":
            raise ValueError("the log does not start with session.created")
        first = events[0]["data"]
        if first.get("location", {}).get("directory") != self.repo:
            return None
        session = Session(id=first["sessionID"], directory=self.repo, agent=first["agent"],
                          model=first["model"], title=first.get("title") or "New session",
                          created=events[0]["created"], updated=events[-1]["created"], resumed=True,
                          parent=first.get("parentID"))
        for event in events:
            session.transcript.apply(event)
            if event["type"] == "session.agent.selected":
                session.agent = event["data"]["agent"]
            elif event["type"] == "session.model.selected":
                session.model = event["data"]["model"]
            elif event["type"] == MODE_RECORD:
                session.mode = event["data"]["mode"]
        session.transcript.settle(session.updated)
        return session

    def publish_rpc(self, name: str, data: dict[str, Any]) -> None:
        """An ``rpc.hobbes.<name>`` event for the TUI's plugins (DEC-015)."""
        event = {"id": ids.event_id(), "type": f"rpc.hobbes.{name}", "created": now_ms(),
                 "location": {"directory": self.repo}, "data": data}
        for queue in self.listeners:
            queue.put_nowait(event)

    async def _watch_graph(self) -> None:
        while True:
            await asyncio.sleep(GRAPH_POLL)
            if self.listeners and self.graph.changed():
                self.publish_rpc("changed", {})

    async def close(self) -> None:
        if self._watch is not None:
            self._watch.cancel()
        await self.layer.close()
        for queue in self.listeners:
            queue.put_nowait(None)
        for session in self.sessions.values():
            for task in list(session.tasks):
                task.cancel()
            await self._close_backend(session)

    # -- helpers -------------------------------------------------------

    def _directory(self, request: Request) -> str:
        return request.query.get("location[directory]") or self.repo

    def _located(self, request: Request, data: Any) -> Response:
        directory = self._directory(request)
        location = {"directory": directory,
                    "project": {"id": PROJECT, "directory": directory, "canonical": directory}}
        return Response(200, {"location": location, "data": data})

    def _session(self, match) -> Session | None:
        return self.sessions.get(match.group(1))

    @staticmethod
    def _missing(session_id: str) -> Response:
        return Response.error(404, "SessionNotFoundError", f"no session {session_id}", sessionID=session_id)

    def agents(self) -> list[dict[str, Any]]:
        return [{"id": str(route), "name": str(route), "mode": "primary", "hidden": False,
                 "permissions": [], "request": {"settings": {}, "headers": {}, "body": {}},
                 "description": ROUTE_INFO[route]} for route in Route]

    def models(self) -> list[dict[str, Any]]:
        return [{"id": name, "modelID": name, "providerID": PROVIDER, "name": f"{name} (ACP)",
                 "capabilities": {"tools": True, "input": ["text"], "output": ["text"]},
                 "variants": [], "time": {"released": 0}, "cost": [], "status": "active",
                 "enabled": True, "limit": {"context": 200000, "output": 32000}}
                for name in self.registry]

    def _vcs(self, directory: str) -> dict[str, Any]:
        try:
            branch = subprocess.run(["git", "-C", directory, "rev-parse", "--abbrev-ref", "HEAD"],
                                    capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            branch = ""
        return {"branch": {"current": branch or "main"}}

    # -- routes --------------------------------------------------------

    def _routes(self) -> None:
        r = self.router
        r.add("GET", "/api/info", self._info)
        r.add("GET", "/api/event", self._events)
        r.add("GET", "/api/location", self._location)
        r.add("GET", "/api/fs/list", self._fs_list)
        r.add("GET", "/api/vcs", lambda q, m: self._ok(self._located(q, self._vcs(self._directory(q)))))
        r.add("GET", "/api/agent", lambda q, m: self._ok(self._located(q, self.agents())))
        r.add("GET", "/api/model", lambda q, m: self._ok(self._located(q, self.models())))
        r.add("GET", "/api/provider", lambda q, m: self._ok(self._located(q, [
            {"id": PROVIDER, "name": "Hobbes", "activation": "enabled", "package": PROVIDER}])))
        r.add("GET", "/api/mcp/resource", lambda q, m: self._ok(self._located(q, {"resources": [], "templates": []})))
        for name in EMPTY_LISTS:
            r.add("GET", f"/api/{name}", lambda q, m: self._ok(self._located(q, [])))
        r.add("GET", "/api/config", lambda q, m: self._ok(Response(200, [])))
        r.add("GET", "/api/project", lambda q, m: self._ok(Response(200, [])))
        r.add("GET", "/api/worktree", lambda q, m: self._ok(Response(200, [{"directory": self.repo}])))
        r.add("GET", "/api/experimental/migration/v1", lambda q, m: self._ok(Response(200, {"status": "completed"})))
        r.add("GET", "/api/session/active", self._active)
        r.add("GET", "/api/session", self._list_sessions)
        r.add("POST", "/api/session", self._create_session)
        s = "/api/session/([^/]+)"
        r.add("GET", s, self._get_session)
        r.add("POST", s + "/agent", self._select_agent)
        r.add("POST", s + "/model", self._select_model)
        r.add("POST", s + "/prompt", self._prompt)
        r.add("POST", s + "/interrupt", self._interrupt)
        r.add("POST", s + "/permission/([^/]+)/reply", self._reply)
        r.add("GET", s + "/permission", self._permissions)
        r.add("GET", s + "/message", self._messages)
        r.add("GET", s + "/message/([^/]+)", self._message)
        r.add("GET", s + "/inbox", lambda q, m: self._ok(Response(200, {"data": []})))
        r.add("GET", s + "/form", self._forms)
        r.add("POST", s + "/form/([^/]+)/reply", self._form_reply)
        r.add("DELETE", s + "/form/([^/]+)", self._form_cancel)
        r.add("GET", "/api/experimental/session/([^/]+)/terminal", lambda q, m: self._ok(Response(200, {"data": []})))
        r.add("POST", s + "/view", lambda q, m: self._ok(Response(204)))
        r.add("POST", "/api/rpc/([^/]+)/([^/]+)", self._rpc)
        r.add("PUT", s + "/environment", lambda q, m: self._ok(Response(204)))

    @staticmethod
    async def _ok(response: Response) -> Response:
        return response

    async def _info(self, request: Request, match) -> Response:
        return Response(200, {"version": OPENCODE_VERSION, "pid": 0, "urls": [], "paths": {"tmp": "/tmp"},
                              "capabilities": {"persistentPty": False}})

    async def _events(self, request: Request, match) -> EventStream:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.listeners.add(queue)
        if self._watch is None:
            self._watch = asyncio.create_task(self._watch_graph())
        return EventStream(queue, first={"id": ids.event_id(), "type": "server.connected", "data": {}},
                           on_close=lambda: self.listeners.discard(queue))

    async def _location(self, request: Request, match) -> Response:
        directory = self._directory(request)
        return Response(200, {"directory": directory,
                              "project": {"id": PROJECT, "directory": directory, "canonical": directory}})

    async def _fs_list(self, request: Request, match) -> Response:
        root = Path(self._directory(request))
        try:
            entries = sorted(p for p in root.iterdir() if p.name != ".git")
        except OSError:
            entries = []
        return self._located(request, [{"path": p.name, "type": "directory" if p.is_dir() else "file"}
                                       for p in entries])

    async def _active(self, request: Request, match) -> Response:
        return Response(200, {"data": {s.id: {"type": "running"} for s in self.sessions.values() if s.running}})

    async def _list_sessions(self, request: Request, match) -> Response:
        parent = request.query.get("parentID")
        parent = None if parent in (None, "", "null") else parent
        found = sorted((s for s in self.sessions.values() if s.parent == parent),
                       key=lambda s: s.updated, reverse=request.query.get("order") != "asc")
        limit = int(request.query.get("limit") or 50)
        return Response(200, {"data": [s.info() for s in found[:limit]],
                              "cursor": {"previous": None, "next": None}})

    async def _create_session(self, request: Request, match) -> Response:
        body = request.json()
        model = body.get("model") or {"providerID": PROVIDER, "id": next(iter(self.registry), "claude")}
        session = Session(
            id=body.get("id") or ids.session_id(),
            directory=(body.get("location") or {}).get("directory") or self.repo,
            agent=body.get("agent") or str(Route.GUARDED),
            model={"providerID": model.get("providerID", PROVIDER), "id": model["id"]},
            title=body.get("title") or "New session",
        )
        self.sessions[session.id] = session
        self.publish("session.created", {"sessionID": session.id, "projectID": PROJECT,
                                         "location": {"directory": session.directory}, "slug": session.id,
                                         "version": OPENCODE_VERSION, "title": session.title,
                                         "agent": session.agent, "model": session.model})
        if self.next_mode == "mapping" or self.next_mode == "mapped" and self.mapping()[0] is not None:
            self._set_mode(session, self.next_mode)
        return Response(200, {"data": session.info()})

    async def _get_session(self, request: Request, match) -> Response:
        session = self._session(match)
        return Response(200, {"data": session.info()}) if session else self._missing(match.group(1))

    async def _select_agent(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        agent = request.json().get("agent")
        if agent not in {str(r) for r in Route}:
            return Response.error(400, "InvalidRequestError", f"unknown agent {agent!r}")
        if agent != session.agent:
            previous, session.agent = session.agent, agent
            self.publish("session.agent.selected", {"sessionID": session.id, "agent": agent, "previous": previous})
        return Response(204)

    async def _select_model(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        model = request.json().get("model") or {}
        if model.get("id") not in self.registry:
            return Response.error(400, "InvalidRequestError", f"unknown model {model.get('id')!r}")
        chosen = {"providerID": model.get("providerID", PROVIDER), "id": model["id"]}
        if chosen != session.model:
            previous, session.model = session.model, chosen
            self.publish("session.model.selected", {"sessionID": session.id, "model": chosen, "previous": previous})
        return Response(204)

    async def _prompt(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        if session.parent is not None:
            return Response.error(400, "InvalidRequestError",
                                  "A worker's session takes no prompts; prompt its parent session.")
        body = request.json()
        inbox_id = body.get("id") or ids.message_id()
        if inbox_id in session.prompts:  # retries are idempotent per id
            return Response(200, {"data": session.prompts[inbox_id]})
        payload = {k: body[k] for k in ("text", "files", "agents", "skills", "metadata") if k in body}
        item = {"id": inbox_id, "sessionID": session.id, "time": {"created": now_ms()}, "type": "user",
                "delivery": body.get("delivery") or "steer", "payload": payload}
        session.prompts[inbox_id] = item
        self.publish("session.inbox.enqueued", {"sessionID": session.id, "inboxID": inbox_id,
                                                "item": {"type": "user", "delivery": item["delivery"],
                                                         "payload": payload}})
        task = asyncio.create_task(self._run(session, inbox_id, payload.get("text") or ""))
        session.tasks.add(task)
        task.add_done_callback(session.tasks.discard)
        return Response(200, {"data": item})

    async def _interrupt(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        if session.parent is not None and session.parent in self.sessions:  # a worker: stop its job
            session = self.sessions[session.parent]
        running = session.running
        self._drop_pending(session)
        if running and session.mode in ("mapped", "mapping"):
            # A job. The worker first: the coordinator's harness waits in its
            # dispatch call and would not end its turn before the worker does.
            for child in self.sessions.values():
                if child.parent == session.id and child.dispatch_task is not None:
                    child.dispatch_task.cancel()
            for task in list(session.tasks):
                task.cancel()
        elif running and session.backend is not None:
            await session.backend.cancel()
        return Response(200, {"interrupted": running})

    async def _permissions(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        return Response(200, {"data": [shown for shown, _ in session.pending.values()]})

    async def _messages(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        try:
            limit = min(max(int(request.query.get("limit") or 50), 1), 200)
        except ValueError:
            limit = 50
        items, after = session.transcript.page(limit, request.query.get("cursor") or None,
                                               request.query.get("order") or "desc")
        return Response(200, {"data": items, "cursor": {"previous": None, "next": after}})

    async def _message(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        item = session.transcript.get(match.group(2))
        if item is None:
            return Response.error(404, "MessageNotFoundError", f"no message {match.group(2)}",
                                  messageID=match.group(2))
        return Response(200, {"data": item})

    async def _rpc(self, request: Request, match) -> Response:
        """The plugins' RPC call: ``hobbes.view`` returns one panel view
        (DEC-015); ``hobbes.status``, ``.start`` and ``.stop`` drive the
        Hobbes layer (DEC-016); ``hobbes.logo`` is the home logo (DEC-017);
        ``hobbes.review`` writes and opens the review page (DEC-018)."""
        method = match.group(2) if match.group(1) == "hobbes" else None
        if method == "status":
            return Response(200, {"output": self.layer.status()})
        if method == "start":
            return Response(200, {"output": self.layer.start()})
        if method == "stop":
            return Response(200, {"output": await self.layer.stop()})
        if method == "logo":
            return Response(200, {"output": await asyncio.to_thread(logo.payload)})
        if method == "mode":
            body = request.json()
            given = body.get("input") if isinstance(body, dict) else None
            return Response(200, {"output": self._mode(given if isinstance(given, dict) else {})})
        if method == "review":
            if not self.layer.on:
                return Response(200, {"output": {"error": OFF_MESSAGES.get(self.layer.state, "") + self.layer.detail}})
            return Response(200, {"output": await asyncio.to_thread(self._review)})
        if method != "view":
            return Response.error(404, "RpcError", f"no rpc method {match.group(1)}.{match.group(2)}",
                                  type="unknown")
        if not self.layer.on:
            return Response(200, {"output": {"error": OFF_MESSAGES.get(self.layer.state, "") + self.layer.detail}})
        body = request.json()
        given = body.get("input") if isinstance(body, dict) else None
        view_id = given.get("id") if isinstance(given, dict) else None
        output = await asyncio.to_thread(self.graph.view, view_id if isinstance(view_id, str) else None)
        return Response(200, {"output": output})

    def mapping(self):
        """The repo's agent mapping when it has a coordinator, else (None, why not)."""
        from hobbes.watterson import roles

        try:
            found = roles.load(self.repo)
        except roles.RolesError as exc:
            return None, str(exc)
        if not found.coordinator:
            return None, f"{found.path}: no coordinator role named"
        return found, ""

    def _mode(self, given: dict[str, Any]) -> dict[str, Any]:
        """RPC ``hobbes.mode``: ``{sessionID?, mode?}``; the mode, whether
        ``mapped`` can run here and why not, or an error."""
        session_id, wanted = given.get("sessionID"), given.get("mode")
        session = self.sessions.get(session_id) if isinstance(session_id, str) else None
        if session_id is not None and session is None:
            return {"error": f"no session {session_id}"}
        mapping, detail = self.mapping()
        if wanted is not None:
            if wanted not in MODES:
                return {"error": f"unknown mode {wanted!r} (modes: {', '.join(MODES)})"}
            if wanted == "mapped" and mapping is None:
                return {"error": f"No agent mapping here: {detail}"}
            if session is None:
                self.next_mode = wanted
                self._save_home_mode()
                self.publish_rpc("mode", {"sessionID": None, "mode": wanted})
            else:
                self._set_mode(session, wanted)
        current = session.mode if session is not None else self.next_mode
        return {"sessionID": session_id, "mode": current, "mapped": mapping is not None, "detail": detail}

    def _set_mode(self, session: Session, mode: str) -> None:
        if mode != session.mode:
            session.mode = mode
            self._record(session, MODE_RECORD, {"sessionID": session.id, "mode": mode})
            self.publish_rpc("mode", {"sessionID": session.id, "mode": mode})

    def _review(self) -> dict[str, Any]:
        """Write the review page (DEC-018) and ask the system to open it."""
        try:
            path = review.write(self.graph.document(), self.repo)
        except artifacts.ArtifactError as exc:
            return {"error": f"No graph for this repo: {exc}"}
        except review.AppMissing as exc:
            return {"error": f"hobbes review: {exc}"}
        opened = self.open_page(path.as_uri())
        return {"path": str(path), "opened": bool(opened)}

    async def _reply(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        entry = session.pending.pop(match.group(2), None)
        if entry is None:
            return Response.error(404, "PermissionNotFoundError", "no such pending permission",
                                  requestID=match.group(2))
        decision = request.json().get("decision")
        if decision not in ("once", "always", "reject"):
            decision = "reject"
        entry[1].set_result(decision)
        self.publish("permission.replied", {"sessionID": session.id, "requestID": match.group(2), "reply": decision})
        return Response(204)

    async def _forms(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        return Response(200, {"data": [shown for shown, _ in session.forms.values()]})

    async def _form_reply(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        entry = session.forms.pop(match.group(2), None)
        if entry is None:
            return Response.error(404, "FormNotFoundError", "no such pending form", formID=match.group(2))
        answer = request.json().get("answer")
        answer = answer if isinstance(answer, dict) else {}
        if not entry[1].done():
            entry[1].set_result(answer)
        self.publish("form.replied", {"id": match.group(2), "sessionID": session.id, "answer": answer}, located=True)
        return Response(204)

    async def _form_cancel(self, request: Request, match) -> Response:
        session = self._session(match)
        if session is None:
            return self._missing(match.group(1))
        entry = session.forms.pop(match.group(2), None)
        if entry is None:
            return Response.error(404, "FormNotFoundError", "no such pending form", formID=match.group(2))
        if not entry[1].done():
            entry[1].set_result(None)
        self.publish("form.cancelled", {"id": match.group(2), "sessionID": session.id}, located=True)
        return Response(204)

    # -- turns ---------------------------------------------------------

    def _drop_pending(self, session: Session) -> None:
        for per_id, (_, future) in list(session.pending.items()):
            if not future.done():
                future.set_result(None)
            self.publish("permission.replied", {"sessionID": session.id, "requestID": per_id, "reply": "reject"})
        session.pending.clear()
        for form_id, (_, future) in list(session.forms.items()):
            if not future.done():
                future.set_result(None)
            self.publish("form.cancelled", {"id": form_id, "sessionID": session.id}, located=True)
        session.forms.clear()

    def _approver(self, session: Session):
        """Ask for a coordinator's plan (DEC-022) as a form: the plan as its
        message, one answer with the terminal's choices (``hobbes.watterson.lead``)."""
        from hobbes.watterson.lead import APPROVAL_HINT, parse_approval

        async def approve(plan: str) -> tuple[bool, str]:
            form = {"id": ids.form_id(), "sessionID": session.id, "title": "Approve the coordinator's plan?",
                    "metadata": {"message": plan.rstrip(), "hobbes": "plan"},
                    "fields": [{"key": "answer", "type": "string", "title": "Answer", "required": True,
                                "description": f"Approve? [{APPROVAL_HINT}]", "custom": True,
                                "options": [{"value": "y", "label": "y", "description": "approve the plan"},
                                            {"value": "n", "label": "n", "description": "do not approve"}]}]}
            future: asyncio.Future[dict | None] = asyncio.get_running_loop().create_future()
            session.forms[form["id"]] = (form, future)
            self.publish("form.created", {"form": form}, located=True)
            answer = await future
            return (False, "") if answer is None else parse_approval(str(answer.get("answer", "")))

        return approve

    def _asker(self, session: Session, link: bool = True):
        """The TUI's permission prompt; *link* ties it to the running turn's
        tool part (not for a worker's request, whose calls are not shown)."""
        async def ask(request: PermissionRequest, note: Annotation) -> str | None:
            turn = session.turn if link else None
            if turn is not None:
                turn.asked(request)
            per_id = ids.permission_id()
            always = option_of_kind(request, "allow_always")
            shown: dict[str, Any] = {
                "id": per_id, "sessionID": session.id,
                "action": PERMISSION_ACTIONS.get(request.kind or "", request.title or "tool"),
                "resources": list(request.paths) or ([note.command] if note.command else []),
                "save": ["*"] if always else [],
                "metadata": {"hobbes": note.lines()},
                "message": "\n".join(note.lines()),
            }
            if request.diffs:  # the edit layout's diff: the edit is not applied yet
                files = file_diffs(request.diffs, Path(session.directory), applied=False)
                shown["metadata"]["diff"] = files[0]["patch"]
            if turn is not None:
                shown["source"] = {"type": "tool", "messageID": turn.message_id, "id": request.tool_call_id}
            future: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
            session.pending[per_id] = (shown, future)
            self.publish("permission.asked", shown)
            decision = await future
            if decision == "once":
                return once(request, "allow")
            if decision == "always":
                return always or once(request, "allow")
            return once(request, "reject")

        return ask

    async def _open_backend(self, session: Session) -> None:
        from hobbes.watterson.hooks import SessionHooks
        from hobbes.watterson.providers import AgentSession

        key = (session.model["id"], session.agent)
        if session.backend is not None and session.backend_key == key:
            return
        restarting = session.backend is not None or session.resumed
        await self._close_backend(session)
        spec, route = self.registry[key[0]], Route(key[1])
        policy = RoutePolicy(route, Path(session.directory), ask=self._asker(session),
                             test_files=self.test_files)
        stack = contextlib.AsyncExitStack()
        on_permission, meta = policy, None
        try:
            if spec.name == "claude":
                hooks = await stack.enter_async_context(SessionHooks(
                    route, session.directory, agent=spec.name, test_files=self.test_files))
                on_permission, meta = hooks.observe(policy), hooks.meta()
            factory = self._session_factory or AgentSession
            session.backend = await stack.enter_async_context(factory(
                spec, cwd=session.directory, on_permission=on_permission,
                modes=modes_for(route, spec.name), meta=meta))
        except BaseException:
            await stack.aclose()
            raise
        session.stack, session.backend_key, session.resumed = stack, key, False
        if restarting:
            note = (f"Started a new {key[0]} session on the {key[1]} route; "
                    "earlier turns are not in its context.")
            self.publish("session.synthetic", {"sessionID": session.id, "text": note, "description": note})

    async def _close_backend(self, session: Session) -> None:
        stack, session.stack, session.backend, session.backend_key = session.stack, None, None, None
        if stack is not None:
            await stack.aclose()

    async def _run(self, session: Session, inbox_id: str, text: str) -> None:
        if session.mode == "mapped":
            return await self._run_job(session, inbox_id, text)
        if session.mode == "mapping":
            return await self._run_mapper(session, inbox_id, text)
        async with session.lock:
            session.running = True
            self.publish("session.execution.started", {"sessionID": session.id})
            self.publish("session.inbox.delivered", {"sessionID": session.id, "inboxID": inbox_id})
            try:
                await self._open_backend(session)
            except Exception as exc:
                self.log(f"session {session.id}: harness failed to start: {exc!r}")
                session.running = False
                self.publish("session.execution.failed", {"sessionID": session.id, "error": {
                    "type": "provider", "message": f"{session.model['id']} did not start: {exc}"}})
                return
            turn = session.turn = Turn(self.publish, session.id, ids.message_id(), Path(session.directory))
            self.publish("session.step.started", {"sessionID": session.id, "assistantMessageID": turn.message_id,
                                                  "agent": session.agent, "model": session.model,
                                                  "started": now_ms()})
            try:
                async with contextlib.aclosing(session.backend.prompt(text)) as events:
                    async for event in events:
                        turn.feed(event)
                turn.finish("end_turn")  # no-op when the harness ended the turn itself
            except Exception as exc:
                self.log(f"session {session.id}: turn failed: {exc!r}")
                turn.fail(str(exc))
            finally:
                self._drop_pending(session)
                session.running, session.turn, session.updated = False, None, now_ms()

    async def _run_job(self, session: Session, inbox_id: str, text: str) -> None:
        """A prompt in a mapped session: one job (``hobbes.watterson.lead.run_job``) in a
        fresh coordinator session, shown as this session's turn. The
        coordinator's events are the turn; a worker's are not shown (its
        permissions are asked here), and the job ends with a notice of each
        handoff and the docs."""
        from hobbes.watterson.dispatch import DispatchError, server_titles
        from hobbes.watterson.lead import SERVER, Worker, run_job
        from hobbes.watterson.providers.events import TurnEnded
        from hobbes.watterson.roles import RolesError

        dispatches = server_titles(SERVER, ("dispatch",))
        async with session.lock:
            session.running = True
            self.publish("session.execution.started", {"sessionID": session.id})
            self.publish("session.inbox.delivered", {"sessionID": session.id, "inboxID": inbox_id})
            turn = session.turn = Turn(self.publish, session.id, ids.message_id(), Path(session.directory),
                                       tasks=lambda title: title in dispatches)
            self.publish("session.step.started", {"sessionID": session.id, "assistantMessageID": turn.message_id,
                                                  "agent": session.agent, "model": session.model,
                                                  "started": now_ms()})
            def show(event, policy) -> None:
                if not isinstance(event, TurnEnded):  # the job ends the turn, after its docs commit
                    turn.feed(event)

            def on_dispatch(role: str, brief: str) -> Worker:
                child = self._queue_worker(session, role, brief)
                turn.link({"sessionID": child.id})

                def start() -> None:
                    child.dispatch_task = asyncio.current_task()  # the worker's: interrupt cancels it first
                    self._start_worker(child, brief)

                def show_worker(event, policy) -> None:
                    if child.turn is not None and not isinstance(event, TurnEnded):
                        child.turn.feed(event)

                return Worker(ask=self._asker(child), on_event=show_worker, start=start,
                              done=lambda record, error: self._end_worker(child, record, error))

            try:
                mapping, detail = self.mapping()
                if mapping is None:
                    raise RolesError(detail)
                result = await run_job(self.repo, mapping, text, approve=self._approver(session),
                                       registry=self.registry, ask=self._asker(session), on_event=show,
                                       on_dispatch=on_dispatch)
                turn.finish(result.stop_reason or "end_turn")
                note = job_notice(result)
                self.publish("session.synthetic", {"sessionID": session.id, "text": note, "description": note})
            except (RolesError, DispatchError) as exc:
                turn.fail(f"The job could not start: {exc}")
            except asyncio.CancelledError:
                turn.finish("cancelled")
            except Exception as exc:
                self.log(f"session {session.id}: job failed: {exc!r}")
                turn.fail(str(exc))
            finally:
                self._drop_pending(session)
                session.running, session.turn, session.updated = False, None, now_ms()

    async def _run_mapper(self, session: Session, inbox_id: str, text: str) -> None:
        """A prompt in an ``edit mapping`` session: one mapper request
        (``hobbes.watterson.mapper.run_mapper``), shown as this session's turn."""
        from hobbes.watterson.dispatch import DispatchError
        from hobbes.watterson.mapper import run_mapper
        from hobbes.watterson.providers.events import TurnEnded

        async with session.lock:
            session.running = True
            self.publish("session.execution.started", {"sessionID": session.id})
            self.publish("session.inbox.delivered", {"sessionID": session.id, "inboxID": inbox_id})
            turn = session.turn = Turn(self.publish, session.id, ids.message_id(), Path(session.directory))
            self.publish("session.step.started", {"sessionID": session.id, "assistantMessageID": turn.message_id,
                                                  "agent": session.agent, "model": session.model,
                                                  "started": now_ms()})

            def notice(note: str) -> None:
                self.publish("session.synthetic", {"sessionID": session.id, "text": note, "description": note})

            def show(event, policy) -> None:
                if not isinstance(event, TurnEnded):  # the turn ends with the notice of what was saved
                    turn.feed(event)

            try:
                if self.layer.state == "starting":
                    notice("Waiting for Hobbes to start, so the mapper can read the repo's graph…")
                knowledge = await self.layer.started()
                if not knowledge:
                    notice("Hobbes is off: the mapper reads the files, without the graph. "
                           "Start it with /hobbes to map from the repo's structure.")
                result = await run_mapper(self.repo, text, agent=session.model["id"], route=session.agent,
                                          registry=self.registry, ask=self._asker(session), on_event=show,
                                          earlier=list(session.mapper_requests), knowledge=knowledge)
                session.mapper_requests.append(text)
                turn.finish(result.stop_reason or "end_turn")
                notice(result.summary(Path(self.repo)))
            except DispatchError as exc:
                turn.fail(f"The mapper could not start: {exc}")
            except asyncio.CancelledError:
                turn.finish("cancelled")
            except Exception as exc:
                self.log(f"session {session.id}: mapper failed: {exc!r}")
                turn.fail(str(exc))
            finally:
                self._drop_pending(session)
                session.running, session.turn, session.updated = False, None, now_ms()

    def _queue_worker(self, parent: Session, role_name: str, brief: str) -> Session:
        """A child session for one dispatched worker, before it starts."""
        mapping, _ = self.mapping()
        agent = mapping.role(role_name).agent if mapping is not None and role_name in mapping.roles else role_name
        subject = (brief.strip().splitlines() or ["work"])[0][:60]
        child = Session(id=ids.session_id(), directory=self.repo, agent=role_name,
                        model={"providerID": PROVIDER, "id": agent}, title=subject,
                        parent=parent.id)
        self.sessions[child.id] = child
        self.publish("session.created", {"sessionID": child.id, "projectID": PROJECT, "parentID": parent.id,
                                         "location": {"directory": child.directory}, "slug": child.id,
                                         "version": OPENCODE_VERSION, "title": child.title,
                                         "agent": child.agent, "model": child.model})
        return child

    def _start_worker(self, child: Session, brief: str) -> None:
        """The worker leaves the queue: its brief, then its turn."""
        message_id = ids.message_id()
        self.publish("session.inbox.enqueued", {"sessionID": child.id, "inboxID": message_id,
                                                "item": {"type": "user", "delivery": "steer",
                                                         "payload": {"text": brief}}})
        child.running = True
        self.publish("session.execution.started", {"sessionID": child.id})
        self.publish("session.inbox.delivered", {"sessionID": child.id, "inboxID": message_id})
        child.turn = Turn(self.publish, child.id, ids.message_id(), Path(child.directory))
        self.publish("session.step.started", {"sessionID": child.id, "assistantMessageID": child.turn.message_id,
                                              "agent": child.agent, "model": child.model, "started": now_ms()})

    def _end_worker(self, child: Session, record: dict | None, error: BaseException | None) -> None:
        """End a worker's turn with its handoff (its ending and report as a
        notice), or say it was cancelled, running or still queued."""
        turn = child.turn
        if record is None:
            if turn is not None:
                turn.finish("cancelled")
            else:
                note = "Not started: the job was stopped while this worker waited in the queue."
                self.publish("session.synthetic", {"sessionID": child.id, "text": note, "description": note})
        else:
            if turn is not None:
                turn.finish(record.get("stop_reason") or "end_turn")
            note = "\n".join(handoff_lines(record))
            self.publish("session.synthetic", {"sessionID": child.id, "text": note, "description": note})
        self._drop_pending(child)
        child.running, child.turn, child.dispatch_task, child.updated = False, None, None, now_ms()


def handoff_lines(record: dict[str, Any]) -> list[str]:
    """One handoff's ending, then the worker's report, indented."""
    state = "merged" if record["merged"] else (
        f"kept for review: {record['reason']}" if record["outcome"] == "review"
        else f"stopped: {record['reason']}")
    lines = [f"{record['role']} {record.get('branch') or '(no branch)'}: {state}"]
    return lines + [f"  {line}" for line in (record.get("report") or "").strip().splitlines()]


def job_notice(result) -> str:
    """What a job did, for the notice after its turn: each handoff with the
    worker's report, the docs, and the coordinator's summary."""
    lines = [f"Job {result.id}: " + (f"finished: {result.summary}" if result.summary is not None else "not finished")]
    for record in result.dispatches:
        first, *report = handoff_lines(record)
        lines += [f"- {first}", *report]
    if result.docs_commit:
        lines.append(f"Docs committed {result.docs_commit[:7]}: {', '.join(result.docs_files)}")
    elif result.reason:
        lines.append(f"Docs {result.reason}")
    return "\n".join(lines)
