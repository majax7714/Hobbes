"""Tests for the Hobbes server the opencode TUI talks to (DEC-013).

The server runs on loopback with the fake ACP agent as its one "model";
requests and the event stream go over real HTTP, read the way opencode's
client reads them. ``TestTurn`` checks the event translation by itself.
No real harness or TUI runs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest

from hobbes.watterson.providers import AgentSpec
from hobbes.watterson.providers.events import (
    FileDiff, PermissionRequest, Plan, PlanEntry, TextChunk, ThoughtChunk, ToolCall, ToolCallUpdate, TurnEnded,
)
from hobbes.watterson import levels, review
from hobbes.watterson.serve import ids
from hobbes.watterson.serve.http import Server
from hobbes.watterson.serve import opencode
from hobbes.watterson.serve.graph import GraphViews, _short_test
from hobbes.watterson.serve.launch import PLUGIN_DIR, tui_env
from hobbes.watterson.serve.opencode import OPENCODE_VERSION, HobbesServer
from hobbes.watterson.serve.patches import file_diffs
from hobbes.watterson.serve.transcript import Transcript, message_id
from tests.test_watterson_levels import graph as level_graph
from tests.test_watterson_review import fake_app
from hobbes.watterson.serve.turns import Turn, tool_name

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"
PASSWORD = "pw"
AUTH = "Basic " + base64.b64encode(f"opencode:{PASSWORD}".encode()).decode()


class Client:
    def __init__(self, port: int) -> None:
        self.port = port

    async def call(self, method: str, path: str, body=None, auth: str | None = AUTH):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        data = b"" if body is None else json.dumps(body).encode()
        head = [f"{method} {path} HTTP/1.1", "host: x", f"content-length: {len(data)}"]
        if auth:
            head.append(f"authorization: {auth}")
        writer.write(("\r\n".join(head) + "\r\n\r\n").encode() + data)
        await writer.drain()
        status = int((await reader.readline()).split()[1])
        headers = {}
        while (line := await reader.readline()) not in (b"\r\n", b""):
            k, _, v = line.decode().partition(":")
            headers[k.strip().lower()] = v.strip()
        raw = await reader.readexactly(int(headers.get("content-length", 0)))
        writer.close()
        return status, (json.loads(raw) if raw else None)

    async def events(self) -> asyncio.Queue:
        """Open the event stream; parsed events land in the returned queue."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(f"GET /api/event HTTP/1.1\r\nhost: x\r\nauthorization: {AUTH}\r\n\r\n".encode())
        await writer.drain()
        while (await reader.readline()) not in (b"\r\n", b""):
            pass
        queue: asyncio.Queue = asyncio.Queue()

        async def pump():
            while line := await reader.readline():
                if line.startswith(b"data: "):
                    queue.put_nowait(json.loads(line[6:]))

        self._pump = asyncio.create_task(pump())
        self._stream = writer  # a collected StreamWriter closes its socket
        return queue


async def until(queue: asyncio.Queue, kind: str, seen: list, timeout: float = 15) -> dict:
    """Collect events into *seen* up to and including the first of *kind*."""
    async def go():
        while True:
            event = await queue.get()
            seen.append(event)
            if event["type"] == kind:
                return event
    return await asyncio.wait_for(go(), timeout)


def serve(repo: Path, body, store: Path | None = None, layer_on: bool = False, **options):
    """Run *body(app, client)* against a live server with the fake agent;
    *layer_on* puts the Hobbes layer on without starting it (DEC-016)."""
    async def go():
        options.setdefault("ingest_log", repo.parent / "ingest.log")
        app = HobbesServer(repo, {"fake": AgentSpec("fake", (sys.executable, str(FAKE_AGENT)))}, store=store,
                           **options)
        if layer_on:
            app.layer.state = "on"
        server = Server(app.router, PASSWORD)
        await server.start()
        try:
            return await body(app, Client(server.port))
        finally:
            await app.close()
            await server.close()
    return asyncio.run(go())


@pytest.fixture
def repo(tmp_path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("")
    (root / "pkg").mkdir()
    return root


async def start_session(client: Client, events: asyncio.Queue, seen: list, repo: Path) -> str:
    sid = ids.session_id()
    status, body = await client.call("POST", "/api/session", {
        "id": sid, "location": {"directory": str(repo)}, "agent": "guarded",
        "model": {"providerID": "hobbes", "id": "fake"}})
    assert status == 200 and body["data"]["id"] == sid
    await until(events, "session.created", seen)
    return sid


def types(seen: list) -> list[str]:
    return [e["type"] for e in seen]


class TestStartup:
    def test_auth_is_required(self, repo):
        async def body(app, client):
            return await client.call("GET", "/api/info", auth=None), await client.call("GET", "/api/info")

        (bad, bad_body), (good, info) = serve(repo, body)
        assert bad == 401 and bad_body["_tag"] == "UnauthorizedError"
        assert good == 200 and info["version"] == OPENCODE_VERSION

    def test_the_location_bundle_answers_and_echoes_the_directory(self, repo):
        asked = str(repo) + "/./"  # not normalized: the TUI caches under the echoed key
        query = "?location%5Bdirectory%5D=" + asked.replace("/", "%2F")
        bundle = ["location", "vcs", "agent", "command", "integration", "mcp", "mcp/resource", "model",
                  "provider", "reference", "skill", "shell", "form", "fs/list", "plugin"]

        async def body(app, client):
            return {name: await client.call("GET", f"/api/{name}{query}") for name in bundle}

        got = serve(repo, body)
        assert all(status == 200 for status, _ in got.values())
        assert got["location"][1]["directory"] == asked
        for name in bundle[1:]:
            assert got[name][1]["location"]["directory"] == asked, name
        agents = got["agent"][1]["data"]
        assert [a["id"] for a in agents] == ["guarded", "manual"]
        assert all(a["mode"] == "primary" and not a["hidden"] for a in agents)
        (model,) = got["model"][1]["data"]
        assert (model["providerID"], model["id"], model["variants"]) == ("hobbes", "fake", [])
        assert {e["path"] for e in got["fs/list"][1]["data"]} == {"a.py", "pkg"}

    def test_the_stream_starts_with_server_connected(self, repo):
        async def body(app, client):
            events = await client.events()
            return await asyncio.wait_for(events.get(), 2)

        assert serve(repo, body)["type"] == "server.connected"

    def test_unknown_sessions_are_404_with_their_tag(self, repo):
        async def body(app, client):
            return await client.call("GET", "/api/session/ses_nope")

        status, err = serve(repo, body)
        assert status == 404 and err["_tag"] == "SessionNotFoundError"


class TestThroughTheFakeAgent:
    def test_a_turn_streams_in_opencode_order(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            assert (await client.call("POST", f"/api/session/{sid}/model",
                                      {"model": {"providerID": "hobbes", "id": "fake"}}))[0] == 204
            status, item = await client.call("POST", f"/api/session/{sid}/prompt",
                                             {"id": "msg_u1", "text": "hello world"})
            assert status == 200 and item["data"]["id"] == "msg_u1"
            asked = await until(events, "permission.asked", seen)
            active = await client.call("GET", "/api/session/active")
            pending = await client.call("GET", f"/api/session/{sid}/permission")
            reply = await client.call("POST", f"/api/session/{sid}/permission/{asked['data']['id']}/reply",
                                      {"decision": "once"})
            await until(events, "session.execution.succeeded", seen)
            return seen, asked, active, pending, reply

        seen, asked, active, pending, reply = serve(repo, body)
        kinds = types(seen)
        order = ["session.inbox.enqueued", "session.execution.started", "session.inbox.delivered",
                 "session.step.started", "session.tool.input.started", "session.tool.called",
                 "permission.asked", "permission.replied", "session.tool.success", "session.text.started",
                 "session.text.ended", "session.step.ended", "session.execution.succeeded"]
        assert [k for k in kinds if k in order] == order
        text = "".join(e["data"]["delta"] for e in seen if e["type"] == "session.text.delta")
        assert text == "hello world [permission: allowed]"
        assert asked["data"]["source"]["id"] == "tool-1"
        assert asked["data"]["save"] == []  # no allow_always offered: no "Always allow" button
        assert list(active[1]["data"].values()) == [{"type": "running"}]
        assert [p["id"] for p in pending[1]["data"]] == [asked["data"]["id"]]
        assert reply[0] == 204

    def test_reject_and_always(self, repo):
        async def body(app, client):
            events, seen, out = await client.events(), [], []
            sid = await start_session(client, events, seen, repo)
            for n, decision in enumerate(("reject", "always")):
                await client.call("POST", f"/api/session/{sid}/prompt", {"id": f"msg_{n}", "text": "run ls -la"})
                asked = await until(events, "permission.asked", seen)
                assert asked["data"]["save"] == ["*"] and asked["data"]["action"] == "shell"
                assert asked["data"]["message"] == "runs: ls -la"
                await client.call("POST", f"/api/session/{sid}/permission/{asked['data']['id']}/reply",
                                  {"decision": decision})
                start = len(seen)
                await until(events, "session.execution.succeeded", seen)
                out.append("".join(e["data"]["delta"] for e in seen[start:] if e["type"] == "session.text.delta"))
            return out

        assert serve(repo, body) == ["[permission: no]", "[permission: always]"]

    def test_an_edit_prompt_shows_its_patch(self, repo):
        (repo / "a.py").write_text("keep\nold\n")

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_e", "text": "edit a.py"})
            asked = await until(events, "permission.asked", seen)
            await client.call("POST", f"/api/session/{sid}/permission/{asked['data']['id']}/reply",
                              {"decision": "reject"})
            await until(events, "session.execution.succeeded", seen)
            return seen, asked

        seen, asked = serve(repo, body)
        started = next(e["data"] for e in seen if e["type"] == "session.tool.input.started")
        called = next(e["data"] for e in seen if e["type"] == "session.tool.called")
        assert started["name"] == "edit" and called["input"]["path"] == str(repo / "a.py")
        assert asked["data"]["action"] == "edit"
        assert asked["data"]["metadata"]["diff"].splitlines()[2:] == ["@@ -1,2 +1,2 @@", " keep", "-old", "+new"]

    def test_interrupt(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_h", "text": "hang please"})
            await until(events, "session.text.delta", seen)
            status, out = await client.call("POST", f"/api/session/{sid}/interrupt?resume=true")
            ended = await until(events, "session.execution.interrupted", seen)
            return status, out, ended

        status, out, ended = serve(repo, body)
        assert (status, out) == (200, {"interrupted": True}) and ended["data"]["reason"] == "user"

    def test_switching_route_restarts_the_harness_with_a_notice(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_1", "text": "cwd?"})
            await until(events, "session.execution.succeeded", seen)
            assert (await client.call("POST", f"/api/session/{sid}/agent", {"agent": "manual"}))[0] == 204
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_2", "text": "cwd?"})
            await until(events, "session.execution.succeeded", seen)
            listed = await client.call("GET", "/api/session?order=desc&parentID=null")
            children = await client.call("GET", f"/api/session?parentID={sid}")
            return seen, listed, children

        seen, listed, children = serve(repo, body)
        assert "session.agent.selected" in types(seen)
        (notice,) = [e for e in seen if e["type"] == "session.synthetic"]
        assert "new fake session on the manual route" in notice["data"]["description"]
        assert [s["agent"] for s in listed[1]["data"]] == ["manual"]
        assert children[1] == {"data": [], "cursor": {"previous": None, "next": None}}

    def test_a_retried_prompt_is_not_run_twice(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            first = await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_r", "text": "cwd?"})
            again = await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_r", "text": "cwd?"})
            await until(events, "session.execution.succeeded", seen)
            await asyncio.sleep(0.3)
            while not events.empty():
                seen.append(events.get_nowait())
            return first, again, seen

        first, again, seen = serve(repo, body)
        assert first == again and types(seen).count("session.execution.started") == 1


class TestHistory:
    def test_the_transcript_survives_a_restart(self, repo, tmp_path):
        store = tmp_path / "sessions"

        async def first(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_u1", "text": "hello world"})
            asked = await until(events, "permission.asked", seen)
            await client.call("POST", f"/api/session/{sid}/permission/{asked['data']['id']}/reply",
                              {"decision": "once"})
            done = await until(events, "session.execution.succeeded", seen)
            _, page = await client.call("GET", f"/api/session/{sid}/message?limit=20&order=desc")
            return sid, done, page

        async def second(app, client):
            events, seen = await client.events(), []
            listed = await client.call("GET", "/api/session?order=desc&parentID=null")
            _, page = await client.call("GET", f"/api/session/{sid}/message?limit=20&order=desc")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_u2", "text": "cwd?"})
            await until(events, "session.execution.succeeded", seen)
            return listed, page, seen

        sid, done, live = serve(repo, first, store)
        user, assistant, plan, idle = live["data"][::-1]
        assert (user["id"], user["type"], user["text"]) == ("msg_u1", "user", "hello world")
        assert assistant["type"] == "assistant" and assistant["time"]["completed"] and assistant["finish"] == "stop"
        tool, text = assistant["content"]
        assert (tool["id"], tool["state"]["status"]) == ("tool-1", "completed")
        assert text == {"type": "text", "text": "hello world [permission: allowed]"}
        assert plan["type"] == "synthetic" and plan["text"].startswith("Plan:")
        assert idle == {"id": message_id(done["id"]), "type": "idle", "outcome": "succeeded",
                        "time": {"created": done["created"]}}
        assert live["cursor"] == {"previous": None, "next": None}

        listed, reloaded, seen = serve(repo, second, store)
        assert [s["id"] for s in listed[1]["data"]] == [sid]
        assert reloaded == live
        notes = [e["data"]["text"] for e in seen if e["type"] == "session.synthetic"]
        assert notes == ["Started a new fake session on the guarded route; earlier turns are not in its context."]

    def test_only_this_repos_sessions_load(self, repo, tmp_path):
        store = tmp_path / "sessions"
        other = tmp_path / "other"
        other.mkdir()

        async def make(app, client):
            events, seen = await client.events(), []
            return await start_session(client, events, seen, other)

        serve(repo, make, store)
        (store / "ses_broken.jsonl").write_text('{"type": "session.created"}\nnot json\n')
        lines = []
        app = HobbesServer(repo, {}, store=store, log=lines.append)
        assert app.sessions == {} and len(list(store.glob("ses_*.jsonl"))) == 2
        assert [line.split(":")[0] for line in lines] == ["skipping session log ses_broken.jsonl"]

    def test_a_switch_message_can_be_fetched(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await client.call("POST", f"/api/session/{sid}/agent", {"agent": "manual"})
            switched = await until(events, "session.agent.selected", seen)
            got = await client.call("GET", f"/api/session/{sid}/message/{message_id(switched['id'])}")
            missing = await client.call("GET", f"/api/session/{sid}/message/msg_nope")
            return got, missing

        got, missing = serve(repo, body)
        assert got[0] == 200 and got[1]["data"]["type"] == "agent-switched"
        assert got[1]["data"]["agent"] == "manual" and got[1]["data"]["previous"] == "guarded"
        assert missing[0] == 404 and missing[1]["_tag"] == "MessageNotFoundError"


class TestTranscript:
    @staticmethod
    def event(n, kind, **data):
        return {"id": f"evt_{n:04d}", "type": kind, "created": 1000 + n, "data": {"sessionID": "ses_1", **data}}

    def test_pages_go_back_in_time(self):
        t = Transcript()
        for n in range(5):
            t.apply(self.event(n, "session.synthetic", text=str(n)))
        page, after = t.page(2)
        assert [m["text"] for m in page] == ["4", "3"] and after == "msg_0003"
        page, after = t.page(2, after)
        assert [m["text"] for m in page] == ["2", "1"] and after == "msg_0001"
        page, after = t.page(2, after)
        assert [m["text"] for m in page] == ["0"] and after is None
        assert [m["text"] for m in t.page(3, order="asc")[0]] == ["0", "1", "2"]

    def test_a_delivered_prompt_moves_after_earlier_rows(self):
        t = Transcript()
        t.apply(self.event(1, "session.inbox.enqueued", inboxID="msg_u", item={"type": "user", "payload": {"text": "hi"}}))
        t.apply(self.event(2, "session.synthetic", text="note"))
        t.apply(self.event(3, "session.inbox.delivered", inboxID="msg_u"))
        assert [m["id"] for m in t.messages] == ["msg_0002", "msg_u"] and t.get("msg_u")["time"]["created"] == 1003

    def test_settle_closes_a_cut_off_turn(self):
        t = Transcript()
        t.apply(self.event(1, "session.step.started", assistantMessageID="msg_a", agent="guarded",
                           model={"providerID": "hobbes", "id": "fake"}, started=1001))
        t.apply(self.event(2, "session.text.started", assistantMessageID="msg_a", ordinal=0))
        t.apply(self.event(3, "session.text.delta", assistantMessageID="msg_a", ordinal=0, delta="par"))
        t.apply(self.event(4, "session.tool.input.started", assistantMessageID="msg_a", id="t1", name="bash"))
        t.apply(self.event(5, "session.tool.called", assistantMessageID="msg_a", id="t1", input={"command": "ls"},
                           executed=True))
        t.settle(2000)
        (assistant,) = t.messages
        text, tool = assistant["content"]
        assert text["text"] == "par" and assistant["time"]["completed"] == 2000
        assert tool["state"]["status"] == "error" and tool["state"]["input"] == {"command": "ls"}


class TestTurn:
    def run(self, *events):
        out = []
        turn = Turn(lambda kind, data: out.append((kind, data)), "ses_1", "msg_a")
        for event in events:
            turn.feed(event)
        return turn, out

    def test_parts_open_and_close_with_ordinals_per_type(self):
        _, out = self.run(ThoughtChunk("hm"), TextChunk("a"), TextChunk("b"), ThoughtChunk("x"), TextChunk("c"),
                          TurnEnded("end_turn"))
        assert [(k.removeprefix("session."), d.get("ordinal")) for k, d in out if "ordinal" in d] == [
            ("reasoning.started", 0), ("reasoning.delta", 0), ("reasoning.ended", 0),
            ("text.started", 0), ("text.delta", 0), ("text.delta", 0), ("text.ended", 0),
            ("reasoning.started", 1), ("reasoning.delta", 1), ("reasoning.ended", 1),
            ("text.started", 1), ("text.delta", 1), ("text.ended", 1)]
        assert [d["text"] for k, d in out if k == "session.text.ended"] == ["ab", "c"]
        assert [k for k, _ in out][-2:] == ["session.step.ended", "session.execution.succeeded"]

    def test_a_tool_waits_for_its_input_then_runs(self):
        _, out = self.run(ToolCall("t1", "Terminal", "execute", "pending"),
                          ToolCallUpdate("t1", "in_progress", None, {"command": "ls"}),
                          ToolCallUpdate("t1", "completed", None, None, None, "a.py"))
        assert [k for k, _ in out] == ["session.tool.input.started", "session.tool.called", "session.tool.success"]
        assert out[0][1]["name"] == "bash" and out[1][1]["input"] == {"command": "ls"}
        assert out[2][1]["content"] == [{"type": "text", "text": "a.py"}]

    def test_unfinished_tools_fail_when_the_turn_ends(self):
        _, out = self.run(ToolCall("t1", "Read", "read", "pending", {"file_path": "a"}), TurnEnded("cancelled"))
        assert [k for k, _ in out] == ["session.tool.input.started", "session.tool.called", "session.tool.failed",
                                       "session.step.ended", "session.execution.interrupted"]
        assert out[0][1]["name"] == "read_tool" and out[3][1]["finish"] == "unknown"

    def test_a_plan_is_a_notice(self):
        _, out = self.run(Plan((PlanEntry("look", "completed", "high"), PlanEntry("fix", "pending", "high"))))
        assert out == [("session.synthetic", {"sessionID": "ses_1", "text": "Plan:\n[x] look\n[ ] fix",
                                              "description": "Plan:\n[x] look\n[ ] fix"})]

    def test_a_permission_can_name_a_tool_before_its_start(self):
        turn, out = self.run()
        turn.call("t1")
        turn.feed(ToolCall("t1", "Echo", "other", "pending"))
        turn.feed(ToolCallUpdate("t1", "completed"))
        assert [k for k, _ in out] == ["session.tool.input.started", "session.tool.called", "session.tool.success"]

    def test_tool_names_stay_off_reserved_layouts(self):
        assert tool_name("execute", {"command": "ls"}) == "bash"
        assert tool_name("execute", {}) == "execute_tool"
        assert tool_name("edit", {}) == "edit_tool" and tool_name("think", None) == "think"
        assert tool_name(None, None) == "tool"
        assert tool_name("read", {}, ("/r/a.py",)) == "read" and tool_name("edit", {}, ("/r/a.py",)) == "edit"
        assert tool_name("search", {}, ("/r",)) == "search"

    def test_a_read_waits_for_its_file_and_uses_the_read_view(self):
        _, out = self.run(ToolCall("t1", "Read", "read", "pending", {}),
                          ToolCallUpdate("t1", raw_input={"limit": 5}))
        assert out == []  # an empty input, then one that names no file yet
        _, out = self.run(ToolCall("t1", "Read", "read", "pending", {}),
                          ToolCallUpdate("t1", raw_input={"file_path": "/r/a.py"}, paths=("/r/a.py",)),
                          ToolCallUpdate("t1", "completed", output="text"))
        assert out[0][1]["name"] == "read"
        assert out[1][1]["input"] == {"file_path": "/r/a.py", "path": "/r/a.py"}
        assert "metadata" not in out[2][1]

    def test_an_edit_success_carries_its_patch(self, tmp_path):
        target = tmp_path / "a.py"
        target.write_text("keep\nnew\n")  # already applied
        diff = FileDiff(str(target), "old\n", "new\n")
        out = []
        turn = Turn(lambda kind, data: out.append((kind, data)), "ses_1", "msg_a", tmp_path)
        turn.feed(ToolCall("t1", "Edit", "edit", "pending", {"file_path": str(target)}, (str(target),), (diff,)))
        turn.feed(ToolCallUpdate("t1", "completed"))
        assert out[0][1]["name"] == "edit"
        (file,) = out[2][1]["metadata"]["files"]
        assert file["file"] == "a.py" and file["status"] == "modified"
        assert (file["additions"], file["deletions"]) == (1, 1)

    def test_a_permission_request_supplies_the_details(self):
        turn, out = self.run()
        turn.asked(PermissionRequest("t1", "Edit", (), kind="edit", raw_input={"file_path": "/r/a.py"},
                                     paths=("/r/a.py",)))
        assert out[0][1]["name"] == "edit" and out[1][1]["input"]["path"] == "/r/a.py"


class TestPatches:
    def patch(self, tmp_path, content, diffs, applied):
        if content is not None:
            (tmp_path / "a.py").write_text(content)
        return file_diffs(tuple(diffs), tmp_path, applied=applied)[0]

    def test_a_snippet_is_placed_in_the_file_before_and_after_the_edit(self, tmp_path):
        diff = FileDiff(str(tmp_path / "a.py"), "two\n", "TWO\n")
        before = self.patch(tmp_path, "one\ntwo\nthree\n", [diff], applied=False)
        after = self.patch(tmp_path, "one\nTWO\nthree\n", [diff], applied=True)
        assert before == after
        assert before["patch"].splitlines() == [
            "--- a.py", "+++ a.py", "@@ -1,3 +1,3 @@", " one", "-two", "+TWO", " three"]

    def test_an_applied_edit_is_not_applied_twice(self, tmp_path):
        diff = FileDiff(str(tmp_path / "a.py"), "a\n", "a\nb\n")  # the old text is still in the new file
        file = self.patch(tmp_path, "a\nb\n", [diff], applied=True)
        assert (file["additions"], file["deletions"]) == (1, 0)

    def test_a_snippet_that_cannot_be_placed_stands_alone(self, tmp_path):
        diff = FileDiff(str(tmp_path / "a.py"), "x\n", "y\n")
        file = self.patch(tmp_path, "x\nx\n", [diff], applied=False)  # twice: ambiguous
        assert file["patch"].splitlines()[2:] == ["@@ -1 +1 @@", "-x", "+y"]
        missing = FileDiff(str(tmp_path / "gone.py"), "x\n", "y\n")
        assert self.patch(tmp_path, None, [missing], applied=False)["patch"].splitlines()[2:] == [
            "@@ -1 +1 @@", "-x", "+y"]

    def test_a_new_file_and_one_outside_the_root(self, tmp_path):
        outside = tmp_path.parent / "elsewhere.py"
        file = file_diffs((FileDiff(str(outside), None, "x\ny\n"),), tmp_path, applied=False)[0]
        assert file["status"] == "added" and file["file"] == str(outside)
        assert (file["additions"], file["deletions"]) == (2, 0)


class TestIdsAndEnv:
    def test_id_shapes(self):
        assert all(len(i) == 30 for i in (ids.message_id(), ids.event_id(), ids.permission_id()))
        assert ids.session_id().startswith("ses_") and ids.message_id() < ids.message_id()
        assert ids.session_id() > ids.session_id()  # descending: newer sorts first

    def test_tui_env(self, tmp_path):
        env = tui_env("pw", tmp_path, {"OPENCODE_SERVER_PASSWORD": "old", "HOME": "/h"})
        assert env["OPENCODE_PASSWORD"] == "pw" and "OPENCODE_SERVER_PASSWORD" not in env
        assert env["OPENCODE_DISABLE_AUTOUPDATE"] == "1"
        assert env["XDG_STATE_HOME"] == str(tmp_path / "xdg" / "state") and env["HOME"] == "/h"

    def test_bare_hobbes_opens_the_app_here_even_outside_git(self, tmp_path, monkeypatch):
        from hobbes.watterson import cli
        from hobbes.watterson.serve import launch

        opened = []

        async def fake_run(repo, registry, **kw):
            opened.append((repo, kw))
            return 0

        monkeypatch.setattr(launch, "run", fake_run)
        monkeypatch.setattr("hobbes.watterson.providers.load_registry", lambda: {})
        monkeypatch.chdir(tmp_path)  # no .git anywhere above a pytest tmp dir
        assert cli.main([]) == 0
        assert opened == [(tmp_path.resolve(), {"serve_only": False, "port": 0})]
        (tmp_path / ".git").mkdir()
        (tmp_path / "sub").mkdir()
        monkeypatch.chdir(tmp_path / "sub")
        assert cli.main(["tui"]) == 0 and opened[-1][0] == tmp_path.resolve()

    def test_the_tui_loads_the_graph_plugin_by_directory(self, tmp_path):
        # The TUI drops an invalid overlay silently and skips file entries (DEC-015).
        env = tui_env("pw", tmp_path, {})
        assert json.loads(env["OPENCODE_CLI_CONFIG_CONTENT"]) == {"plugins": [str(PLUGIN_DIR)]}
        assert PLUGIN_DIR.is_absolute() and (PLUGIN_DIR / "tui.tsx").is_file()
        assert "node_modules" not in PLUGIN_DIR.parts  # the TUI compiles no JSX under node_modules

    def test_the_tui_build_reports_the_servers_version(self):
        # A client of another version warns before the TUI starts (DEC-025).
        from hobbes.watterson.serve.launch import TUI_DIR
        from hobbes.watterson.serve.opencode import OPENCODE_VERSION

        env = dict(line.split("=", 1) for line in (TUI_DIR / "build.env").read_text().splitlines()
                   if line and not line.startswith("#"))
        assert env["version"] == OPENCODE_VERSION


def write_graph(repo: Path, paths: list[str], edges=()) -> None:
    derived = repo / ".hobbes" / "derived"
    derived.mkdir(parents=True, exist_ok=True)
    (derived / "graph.json").write_text(json.dumps(level_graph(paths, list(edges))))


GRAPH = ["pkg/a/x.py", "pkg/a/y.py", "pkg/b/z.py", "pkg/c.py"]
LINKS = [("pkg.a.x", "pkg.b.z"), ("pkg.b.z", "pkg.c")]


class TestGraphPanel:
    def test_views_are_rows_with_links(self, repo):
        write_graph(repo, GRAPH, LINKS)
        views = GraphViews(repo)
        top = views.view()
        assert top["parent"] is None and top["sha"] == "abc" and top["notes"] == []
        rows = {b["label"]: b for b in top["boxes"]}
        assert rows["a/"]["opens"] == "pkg/a" and rows["a/"]["detail"] == "2 modules"
        assert rows["a/"]["links"] == ["→ b/  1 imports"]
        assert rows["b/"]["links"] == ["→ c.py  1 imports", "← a/  1 imports"]
        assert rows["c.py"]["opens"] is None and rows["c.py"]["detail"] == "1 module"  # a module opens nothing
        child = views.view("pkg/a/")
        assert child["parent"] == top["id"] and child["parentTitle"] == top["title"]

    def test_a_module_view_lists_symbols(self, repo):
        derived = repo / ".hobbes" / "derived"
        derived.mkdir(parents=True)
        g = level_graph(GRAPH, [], symbols=[
            {"id": "pkg.c.run", "module": "pkg.c", "name": "run", "qualname": "run", "kind": "function",
             "line": 1, "end_line": 4}], symbol_edges=[])
        (derived / "graph.json").write_text(json.dumps(g))
        views = GraphViews(repo)
        rows = {b["label"]: b for b in views.view()["boxes"]}
        assert rows["c.py"]["opens"] == "pkg/c.py"
        module = views.view("pkg/c.py")
        assert module["kind"] == "module" and module["parentTitle"] == views.view()["title"]
        (run,) = module["boxes"]
        assert (run["label"], run["detail"], run["opens"], run["tests"]) == ("run()", "function, 4 lines", None, [])
        assert _short_test("pkg/tests/test_c.py::TestRun::test_it") == "test_c.py::TestRun::test_it"

    def test_a_flow_keeps_call_order_and_its_notes(self, repo):
        derived = repo / ".hobbes" / "derived"
        derived.mkdir(parents=True)
        fn = {"kind": "function", "line": 1, "end_line": 4}
        g = level_graph(GRAPH, [], symbols=[
            {"id": "pkg.c.main", "module": "pkg.c", "name": "main", "qualname": "main", **fn},
            {"id": "pkg.c.zed", "module": "pkg.c", "name": "zed", "qualname": "zed", **fn},
            {"id": "pkg.c.abc", "module": "pkg.c", "name": "abc", "qualname": "abc", **fn}], symbol_edges=[
            {"from": "pkg.c.main", "to": f"pkg.c.{name}", "type": "calls", "evidence": [{"path": "pkg/c.py", "line": n}]}
            for name, n in (("zed", 2), ("abc", 3))])
        (derived / "graph.json").write_text(json.dumps(g))
        (derived / "interfaces.json").write_text(json.dumps(
            {"schema_version": g["schema_version"], "routes": [],
             "cli_entry_points": [{"name": "c", "source": "pyproject.toml", "target": "pkg.c:main"}]}))
        views = GraphViews(repo)
        assert {b["label"]: b["opens"] for b in views.view()["boxes"]}["entry points"] == "flow:"
        flow = views.view("flow:pkg.c.main")
        assert flow["kind"] == "flow" and flow["parentTitle"] == "entry points"
        assert [b["label"] for b in flow["boxes"]] == ["1. zed()", "2. abc()"]
        assert flow["boxes"][0]["detail"] == "called at line 2, ends: no calls recorded"
        assert views.view("flow:")["notes"] == [levels.FLOW_NOTE]

    def test_errors_are_shown_not_raised(self, repo):
        views = GraphViews(repo)
        assert views.view()["error"].startswith("No graph for this repo")
        write_graph(repo, GRAPH)
        assert views.view("nope")["error"] == "No view 'nope' in the graph."

    def test_changes_are_noticed_once(self, repo):
        views = GraphViews(repo)
        assert not views.changed()
        write_graph(repo, GRAPH)
        assert views.changed() and not views.changed()
        assert "boxes" in views.view()

    def test_hobbes_starts_over_rpc_and_then_the_panel_answers(self, tmp_path):
        from tests.test_watterson_layer import git_repo

        repo = git_repo(tmp_path / "git")
        ran = []

        async def ingest(root, log):
            ran.append(root)
            write_graph(root, GRAPH)
            return 0

        async def body(app, client):
            events, seen = await client.events(), []
            before = await client.call("POST", "/api/rpc/hobbes/view", {"input": {}})
            status = await client.call("POST", "/api/rpc/hobbes/status", {"input": {}})
            started = await client.call("POST", "/api/rpc/hobbes/start", {"input": {}})
            pushed = [(await until(events, "rpc.hobbes.status", seen, timeout=5))["data"] for _ in range(3)]
            after = await client.call("POST", "/api/rpc/hobbes/view", {"input": {}})
            stopped = await client.call("POST", "/api/rpc/hobbes/stop", {"input": {}})
            return before, status, started, pushed, after, stopped

        before, status, started, pushed, after, stopped = serve(repo, body, ingest=ingest)
        assert before[1]["output"]["error"].startswith("Hobbes is off. Start it with /hobbes")
        assert status[1]["output"]["state"] == "off" and started[1]["output"]["state"] == "starting"
        assert [p["state"] for p in pushed] == ["starting", "starting", "on"] and ran == [repo.resolve()]
        assert "boxes" in after[1]["output"] and stopped[1]["output"]["state"] == "off"

    def test_review_over_rpc_writes_and_opens_the_page(self, repo, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_REVIEW_DIR", str(tmp_path / "out"))
        monkeypatch.setattr(review, "APP_DIR", fake_app(tmp_path / "app"))
        write_graph(repo, GRAPH, LINKS)
        opened = []

        async def body(app, client):
            off = await client.call("POST", "/api/rpc/hobbes/review", {"input": {}})
            app.layer.state = "on"
            app.open_page = lambda url: opened.append(url) or True
            on = await client.call("POST", "/api/rpc/hobbes/review", {"input": {}})
            return off, on

        off, on = serve(repo, body)
        assert off[1]["output"]["error"] == "Hobbes needs a git repo with a commit."  # the fixture is no repo
        path = tmp_path / "out" / "repo@abc.html"
        assert on[1]["output"] == {"path": str(path), "opened": True} and path.is_file()
        assert opened == [path.as_uri()]

    def test_the_logo_over_rpc(self, repo, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_LOGO", str(tmp_path / "logo.txt"))
        (tmp_path / "logo.txt").write_text("O e8892b\n\nOO\nOO\n")

        async def body(app, client):
            return await client.call("POST", "/api/rpc/hobbes/logo", {"input": {}})

        status, reply = serve(repo, body)
        assert status == 200 and reply["output"]["art"]["rows"] == ["OO", "OO"]
        assert reply["output"]["letters"]["rows"][0].startswith("TT")

    def test_the_rpc_call_and_the_change_event(self, repo, monkeypatch):
        monkeypatch.setattr(opencode, "GRAPH_POLL", 0.05)

        async def body(app, client):
            events, seen = await client.events(), []
            empty = await client.call("POST", "/api/rpc/hobbes/view?location%5Bdirectory%5D=x", {"input": {}})
            write_graph(repo, GRAPH, LINKS)
            changed = await until(events, "rpc.hobbes.changed", seen, timeout=5)
            view = await client.call("POST", "/api/rpc/hobbes/view", {"input": {"id": "pkg/a"}})
            unknown = await client.call("POST", "/api/rpc/hobbes/nothing", {"input": {}})
            return empty, changed, view, unknown

        empty, changed, view, unknown = serve(repo, body, layer_on=True)
        assert empty[0] == 200 and "error" in empty[1]["output"]
        assert changed["location"] == {"directory": str(repo.resolve())} and changed["data"] == {}
        assert view[0] == 200 and view[1]["output"]["id"] == "pkg/a"
        assert unknown[0] == 404 and unknown[1]["_tag"] == "RpcError"
