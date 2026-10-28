"""A small asyncio HTTP/1.1 server with server-sent events, for the TUI.

Standard library only. Requests carry a ``Content-Length`` or chunked
body; connections are kept alive between requests. A handler returns a
``Response`` or an ``EventStream``; an event stream holds its connection
until the client goes away. Every request must carry HTTP Basic auth for
user ``opencode`` and the server's password (what the TUI sends when
``OPENCODE_PASSWORD`` is set); others get 401.
"""

from __future__ import annotations

import asyncio
import base64
import hmac
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlsplit

REASONS = {200: "OK", 204: "No Content", 400: "Bad Request", 401: "Unauthorized",
           404: "Not Found", 405: "Method Not Allowed", 409: "Conflict", 500: "Internal Server Error"}
#: Seconds between keepalive comments on an event stream (the TUI gives up after 45).
KEEPALIVE = 15.0


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: bytes = b""

    def json(self) -> Any:
        return json.loads(self.body) if self.body else {}


@dataclass
class Response:
    status: int = 200
    body: Any = None  # JSON-encoded unless None

    @classmethod
    def error(cls, status: int, tag: str, message: str, **extra: Any) -> Response:
        return cls(status, {"_tag": tag, "message": message, **extra})


@dataclass
class EventStream:
    """Stream ``data: <json>`` blocks from ``events`` until a ``None`` arrives
    or the client leaves; ``first`` goes out at once."""

    events: asyncio.Queue[dict[str, Any] | None]
    first: dict[str, Any] | None = None
    on_close: Callable[[], None] | None = field(default=None, repr=False)


Handler = Callable[[Request, "re.Match[str]"], Awaitable[Response | EventStream]]


class Router:
    def __init__(self) -> None:
        self.routes: list[tuple[str, re.Pattern[str], Handler]] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        self.routes.append((method, re.compile(f"^{pattern}$"), handler))

    async def dispatch(self, request: Request) -> Response | EventStream:
        allowed = False
        for method, pattern, handler in self.routes:
            if match := pattern.match(request.path):
                if method == request.method:
                    return await handler(request, match)
                allowed = True
        if allowed:
            return Response.error(405, "MethodNotAllowed", f"{request.method} {request.path}")
        return Response.error(404, "NotFoundError", f"no route for {request.method} {request.path}")


class Server:
    """Serve a ``Router`` on loopback, behind a password."""

    def __init__(self, router: Router, password: str, *, log: Callable[[str], None] | None = None) -> None:
        self.router, self.log = router, log or (lambda line: None)
        self._auth = "Basic " + base64.b64encode(f"opencode:{password}".encode()).decode()
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self.port = 0

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._server = await asyncio.start_server(self._connection, host, port)
        self.port = self._server.sockets[0].getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            for writer in list(self._writers):  # Server.close_clients() needs Python 3.13
                writer.close()
            await self._server.wait_closed()

    async def _connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        try:
            while (request := await _read_request(reader)) is not None:
                if not hmac.compare_digest(request.headers.get("authorization", ""), self._auth):
                    result: Response | EventStream = Response.error(401, "UnauthorizedError", "bad or missing password")
                else:
                    try:
                        result = await self.router.dispatch(request)
                    except Exception as exc:  # a handler bug must not kill the connection loop
                        self.log(f"error {request.method} {request.path}: {exc!r}")
                        result = Response.error(500, "InternalError", str(exc))
                self.log(f"{request.method} {request.path} -> "
                         f"{'stream' if isinstance(result, EventStream) else result.status}")
                if isinstance(result, EventStream):
                    await _stream(writer, result)
                    return
                await _respond(writer, result)
        except (ConnectionError, asyncio.IncompleteReadError, asyncio.CancelledError):
            pass
        finally:
            self._writers.discard(writer)
            writer.close()


async def _read_request(reader: asyncio.StreamReader) -> Request | None:
    line = await reader.readline()
    if not line.strip():
        return None
    method, target, _ = line.decode("latin-1").split(" ", 2)
    headers: dict[str, str] = {}
    while (raw := await reader.readline()) not in (b"\r\n", b"\n", b""):
        name, _, value = raw.decode("latin-1").partition(":")
        headers[name.strip().lower()] = value.strip()
    if headers.get("transfer-encoding", "").lower() == "chunked":
        body = b""
        while (size := int((await reader.readline()).split(b";")[0], 16)) > 0:
            body += await reader.readexactly(size)
            await reader.readline()
        await reader.readline()
    else:
        body = await reader.readexactly(int(headers.get("content-length", "0") or 0))
    url = urlsplit(target)
    return Request(method.upper(), url.path, dict(parse_qsl(url.query, keep_blank_values=True)), headers, body)


async def _respond(writer: asyncio.StreamWriter, response: Response) -> None:
    body = b"" if response.body is None else json.dumps(response.body).encode()
    head = [f"HTTP/1.1 {response.status} {REASONS.get(response.status, 'Status')}",
            f"content-length: {len(body)}", "connection: keep-alive"]
    if body:
        head.append("content-type: application/json")
    writer.write(("\r\n".join(head) + "\r\n\r\n").encode() + body)
    await writer.drain()


async def _stream(writer: asyncio.StreamWriter, stream: EventStream) -> None:
    writer.write(b"HTTP/1.1 200 OK\r\ncontent-type: text/event-stream\r\n"
                 b"cache-control: no-cache\r\nconnection: keep-alive\r\n\r\n")

    def send(event: dict[str, Any]) -> None:
        writer.write(b"data: " + json.dumps(event).encode() + b"\n\n")

    try:
        if stream.first is not None:
            send(stream.first)
        await writer.drain()
        while True:
            try:
                event = await asyncio.wait_for(stream.events.get(), KEEPALIVE)
            except TimeoutError:
                writer.write(b": keepalive\n\n")
            else:
                if event is None:
                    return
                send(event)
            await writer.drain()
    finally:
        if stream.on_close is not None:
            stream.on_close()
