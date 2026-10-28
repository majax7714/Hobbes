"""The coordinator's job loop (DEC-022 slice 2): its MCP relay, its tools, a job end to end.

The coordinator's tools are driven through ``Lead.handle`` and, once,
through the real relay (``lead_mcp.py``) over the driver's socket
(``tool_relay``); ``run_job`` runs a fake coordinator whose prompt edits a
file, standing in for its docs update.
"""

from __future__ import annotations

import asyncio
import json
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

from hobbes.watterson import cli, lead, roles
from hobbes.watterson.dispatch import DispatchError, tool_relay
from hobbes.watterson.lead import JobResult, Lead, is_lead_tool, run_job
from hobbes.watterson.providers import PermissionRequest

from .test_watterson_dispatch import REGISTRY, TEST_COMMAND, agents_file, git, write_roles  # noqa: F401 (agents_file is a fixture)
from .test_watterson_freshness import commit

ROLES = (f"coordinator = \"lead\"\ntest = {json.dumps(TEST_COMMAND)}\n\n"
         '[roles.lead]\nagent = "fake"\nknowledge = false\nprompt = "roles/lead.md"\nwrites = ["docs/*"]\n\n'
         '[roles.impl]\nagent = "fake"\nknowledge = false\nprompt = "roles/impl.md"\nwrites = ["src/*"]\n')


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    root = (tmp_path / "repo").resolve()
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@t")
    commit(root, "src/keep.txt")
    roles.ensure_ignored(root)
    write_roles(root, ROLES)
    (root / ".hobbes" / "roles" / "lead.md").write_text("You coordinate.\n")
    return root


def approver(*answers: tuple[bool, str]):
    queue = list(answers)

    async def approve(plan: str) -> tuple[bool, str]:
        return queue.pop(0)
    return approve


def make_lead(repo: Path, approve=None) -> Lead:
    return Lead(repo, roles.load(repo), JobResult("j1", "job", "lead"), approve=approve, registry=REGISTRY)


def call(the_lead: Lead, tool: str, **arguments) -> tuple[str, bool]:
    return asyncio.run(the_lead.handle(tool, arguments))


def calls(the_lead: Lead, *steps: tuple) -> list[tuple[str, bool]]:
    """Tool calls in one event loop, so workers dispatched by one live on to the next."""
    async def go():
        return [await the_lead.handle(tool, arguments) for tool, arguments in steps]
    return asyncio.run(go())


def handoffs(text: str) -> list[dict]:
    return json.loads(text)


class TestTools:
    def test_dispatch_waits_for_an_approved_plan(self, repo):
        the_lead = make_lead(repo, approver((False, "smaller units")))
        assert call(the_lead, "dispatch", role="impl", brief="x") == (
            "Propose a plan and have it approved before dispatching.", True)
        assert call(the_lead, "propose_plan", plan="1. impl: everything") == (
            "Not approved. The user says: smaller units", False)
        assert call(the_lead, "dispatch", role="impl", brief="x")[1] is True
        assert the_lead.result.plans == [{"plan": "1. impl: everything", "approved": False, "comment": "smaller units"}]

    def test_no_terminal_no_plan(self, repo):
        the_lead = make_lead(repo)
        text, error = call(the_lead, "propose_plan", plan="p")
        assert error and "not a terminal" in text
        assert not the_lead.result.approved

    def test_an_approved_plan_lets_workers_run(self, repo):
        the_lead = make_lead(repo, approver((True, "go")))
        plan, sent, waited, again = calls(the_lead, ("propose_plan", {"plan": "1. impl: add ok"}),
                                          ("dispatch", {"role": "impl", "brief": "write src/ok.txt hi"}),
                                          ("wait", {}), ("wait", {}))
        assert plan == ("Approved. The user adds: go", False)
        assert sent == ("Dispatched #1 to impl: started. Call wait for the handoffs.", False)
        (handoff,) = handoffs(waited[0])
        assert not waited[1] and handoff["merged"] and handoff["files"] == ["src/ok.txt"]
        assert handoff["ticket"] == 1 and "record" not in handoff
        assert again == ("Nothing to wait for: every handoff has been returned.", False)
        assert (repo / "src" / "ok.txt").read_text() == "hi\n"
        assert the_lead.result.dispatches[0]["role"] == "impl"

    def test_workers_run_up_to_the_cap_and_merge_in_turn(self, repo):
        write_roles(repo, ROLES.replace("test =", "workers = 2\ntest ="))
        the_lead = make_lead(repo, approver((True, "")))
        steps = [("propose_plan", {"plan": "p"})] + [
            ("dispatch", {"role": "impl", "brief": f"write src/ok.txt hi && write src/{name}.txt {name}"})
            for name in ("a", "b", "c")] + [("wait", {})]
        _, *sent, waited = calls(the_lead, *steps)
        assert [text.split(": ", 1)[1].split(".")[0] for text, _ in sent] == [
            "started", "started", "queued behind 2 worker(s) (at most 2 at a time)"]
        found = handoffs(waited[0])
        assert sorted(h["ticket"] for h in found) == [1, 2, 3]
        assert all(h["merged"] for h in found), [h["reason"] for h in found]
        assert any(h["target_moved"] for h in found)  # a later one took main in before its test
        assert {p.name for p in (repo / "src").iterdir()} == {"keep.txt", "ok.txt", "a.txt", "b.txt", "c.txt"}

    def test_a_conflict_in_the_merge_queue_stops_the_later_worker(self, repo):
        the_lead = make_lead(repo, approver((True, "")))
        _, _, _, waited = calls(the_lead, ("propose_plan", {"plan": "p"}),
                                ("dispatch", {"role": "impl", "brief": "write src/ok.txt one"}),
                                ("dispatch", {"role": "impl", "brief": "write src/ok.txt two"}), ("wait", {}))
        found = sorted(handoffs(waited[0]), key=lambda h: h["merged"])
        assert [h["merged"] for h in found] == [False, True]
        assert found[0]["reason"] == "main moved and conflicts with the worker's branch"

    def test_finish_waits_for_the_workers_and_stop_cancels_the_queue(self, repo):
        write_roles(repo, ROLES.replace("test =", "workers = 1\ntest ="))
        ended = []
        the_lead = make_lead(repo, approver((True, "")))
        the_lead.on_dispatch = lambda role, brief: lead.Worker(
            start=lambda: ended.append(("start", brief)), done=lambda record, error: ended.append((brief, error)))

        async def go():
            await the_lead.handle("propose_plan", {"plan": "p"})
            await the_lead.handle("dispatch", {"role": "impl", "brief": "hang here"})
            queued = await the_lead.handle("dispatch", {"role": "impl", "brief": "write src/ok.txt hi"})
            await asyncio.sleep(0.5)
            refused = await the_lead.handle("finish", {"summary": "s"})
            await the_lead.stop()
            return queued, refused

        queued, refused = asyncio.run(go())
        assert "queued behind 1 worker(s) (at most 1 at a time)" in queued[0]
        assert refused == ("2 worker(s) are still running; call wait first.", True)
        assert ended[0] == ("start", "hang here") and len(ended) == 3
        assert all(isinstance(error, asyncio.CancelledError) for _, error in ended[1:])
        assert not the_lead.running and the_lead.result.dispatches == []

    def test_dispatch_refuses_the_coordinator_role_and_a_dirty_checkout(self, repo):
        the_lead = make_lead(repo, approver((True, "")))
        call(the_lead, "propose_plan", plan="p")
        assert call(the_lead, "dispatch", role="lead", brief="x")[1] is True
        (repo / "src" / "keep.txt").write_text("edited\n")
        text, error = call(the_lead, "dispatch", role="impl", brief="write src/ok.txt hi")
        assert error and "uncommitted changes" in text
        assert the_lead.result.dispatches == []

    def test_a_worker_that_cannot_run_is_an_error_not_a_crash(self, repo):
        the_lead = make_lead(repo, approver((True, "")))
        call(the_lead, "propose_plan", plan="p")
        text, error = call(the_lead, "dispatch", role="nobody", brief="x")
        assert error and "no role 'nobody'" in text and the_lead.result.dispatches == []

    def test_finish_records_the_summary(self, repo):
        the_lead = make_lead(repo)
        assert call(the_lead, "finish", summary="done") == ("Finished. End your turn now.", False)
        assert the_lead.result.summary == "done"

    def test_only_our_tools_on_our_server_are_allowed(self):
        def request(title, server="hobbes-lead", source="dynamic"):
            meta = {"claudeCode": {"mcpServer": {"name": server, "source": source}}}
            return PermissionRequest("c", title, (), meta=meta)

        assert is_lead_tool(request("mcp__hobbes-lead__dispatch"))
        assert not is_lead_tool(request("mcp__hobbes-lead__dispatch", source="project"))
        assert not is_lead_tool(request("mcp__hobbes__who_calls"))
        assert is_lead_tool(PermissionRequest("c", "mcp.hobbes-lead.finish", (),
                                              raw_input={"server": "hobbes-lead", "tool": "finish"}))


def mcp_exchange(socket_path: str, *messages: dict, server: str = "hobbes-lead") -> list[dict]:
    lines = "".join(json.dumps(m) + "\n" for m in messages)
    out = subprocess.run([sys.executable, "-I", "-S", str(lead.MCP_SCRIPT), socket_path, server],
                         input=lines, capture_output=True, text=True, timeout=30)
    return [json.loads(line) for line in out.stdout.splitlines()]


class TestRelay:
    def test_speaks_mcp_and_relays_calls(self):
        # A short temp dir, as hooks.py uses: tmp_path can pass macOS's 104-byte AF_UNIX limit.
        socket_dir = tempfile.TemporaryDirectory(prefix="hobbes-relay-")
        socket_path = str(Path(socket_dir.name) / "s")

        class Echo(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.read())
                self.wfile.write(json.dumps({"text": f"got {request['tool']} {request['arguments']}",
                                             "error": False}).encode())

        server = socketserver.UnixStreamServer(socket_path, Echo)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            replies = mcp_exchange(
                socket_path,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "finish", "arguments": {"summary": "s"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}},
                {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
            )
        finally:
            server.shutdown()
            server.server_close()
            socket_dir.cleanup()
        assert [r["id"] for r in replies] == [1, 2, 3, 4, 5]
        assert replies[0]["result"]["protocolVersion"] == "2025-03-26"
        assert replies[0]["result"]["serverInfo"]["name"] == "hobbes-lead"
        assert [t["name"] for t in replies[1]["result"]["tools"]] == list(lead.TOOLS)
        assert replies[2]["result"] == {"content": [{"type": "text", "text": "got finish {'summary': 's'}"}],
                                        "isError": False}
        assert replies[3]["error"]["code"] == -32602 and replies[4]["error"]["code"] == -32601

    def test_serves_the_worker_tools_by_name(self, tmp_path):
        init, tools = mcp_exchange(str(tmp_path / "s"),
                                   {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                                   {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, server="hobbes-worker")
        assert init["result"]["serverInfo"]["name"] == "hobbes-worker"
        assert [t["name"] for t in tools["result"]["tools"]] == ["report"]

    def test_an_unreachable_driver_is_a_tool_error(self, tmp_path):
        (reply,) = mcp_exchange(str(tmp_path / "missing"), {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                                             "params": {"name": "finish", "arguments": {}}})
        assert reply["result"]["isError"] and "not reachable" in reply["result"]["content"][0]["text"]

    def test_through_the_driver_socket(self, repo):
        the_lead = make_lead(repo, approver((True, "")))

        async def go():
            async with tool_relay(the_lead.handle) as socket_path:
                return await asyncio.to_thread(
                    mcp_exchange, socket_path,
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                     "params": {"name": "propose_plan", "arguments": {"plan": "1. impl: ok"}}},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": "dispatch", "arguments": {"role": "impl", "brief": "write src/ok.txt hi"}}},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "wait", "arguments": {}}},
                )

        plan, work, waited = asyncio.run(go())
        assert plan["result"]["content"][0]["text"] == "Approved."
        assert work["result"]["content"][0]["text"].startswith("Dispatched #1 to impl")
        (handoff,) = json.loads(waited["result"]["content"][0]["text"])
        assert (handoff["merged"], handoff["outcome"]) == (True, "merged")


def job(repo: Path, text: str, **kwargs) -> JobResult:
    return asyncio.run(run_job(repo, roles.load(repo), text, approve=None, registry=REGISTRY, **kwargs))


class TestRunJob:
    def test_the_coordinators_docs_are_committed(self, repo):
        result = job(repo, "write docs/notes.md hello")
        assert result.stop_reason == "end_turn"
        assert result.said == "role: [hobbes role: lead]\nwrote docs/notes.md"
        assert result.docs_files == ["docs/notes.md"] and result.reason == ""
        assert result.docs_commit == git(repo, "rev-parse", "HEAD")
        assert git(repo, "log", "-1", "--format=%B").startswith("docs: write docs/notes.md hello\n\nHobbes-Job: ")
        assert git(repo, "status", "--porcelain") == ""
        assert json.loads(Path(result.record).read_text())["docs_files"] == ["docs/notes.md"]

    def test_edits_outside_its_writes_are_left(self, repo):
        head = git(repo, "rev-parse", "HEAD")
        result = job(repo, "write src/x.txt hi")
        assert result.docs_commit is None and git(repo, "rev-parse", "HEAD") == head
        assert result.reason == "left uncommitted: outside role lead's writes: src/x.txt"

    def test_the_session_has_the_lead_tools(self, repo):
        result = job(repo, "mcp?")
        (server,) = json.loads(result.said.split("\n", 1)[1])
        assert server["name"] == "hobbes-lead" and str(lead.MCP_SCRIPT) in server["args"]

    def test_the_prompt_carries_the_loop_rules(self):
        prompt = lead.lead_prompt("lead", "You coordinate.\n", "do it")
        assert prompt.startswith("[hobbes role: lead]\nYou coordinate.\n\n[hobbes loop]\n")
        assert prompt.endswith("\n\n[hobbes job]\ndo it")
        assert "up to 3 workers run at a time" in lead.lead_prompt("lead", "", "x", workers=3)

    def test_needs_a_clean_checkout_on_the_branch(self, repo):
        (repo / "src" / "keep.txt").write_text("edited\n")
        with pytest.raises(DispatchError, match="uncommitted changes"):
            job(repo, "x")
        git(repo, "checkout", "-q", "--", "src/keep.txt")
        git(repo, "checkout", "-q", "-b", "other")
        with pytest.raises(DispatchError, match="on other, not main"):
            job(repo, "x")

    def test_needs_a_coordinator(self, repo):
        write_roles(repo, ROLES.replace('coordinator = "lead"\n', ""))
        with pytest.raises(roles.RolesError, match="no coordinator role"):
            job(repo, "x")


class TestCli:
    def test_job_without_a_finish_exits_1(self, repo, agents_file, capsys):
        assert cli.main(["job", "--repo", str(repo), "write docs/n.md x"]) == 1
        err = capsys.readouterr().err
        assert "hobbes: docs committed" in err and "docs/n.md" in err
        assert "hobbes: not finished" in err
