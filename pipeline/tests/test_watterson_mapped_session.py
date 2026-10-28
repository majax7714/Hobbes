"""Agent-mapped sessions in the TUI server (DEC-022 slices 3b, 3c): the mode, a job per prompt,
the plan as a form, each worker in a child session.

The server runs over real HTTP as in ``test_serve``; the coordinator and the
worker are the fake ACP agent, whose ``call`` prompt reaches the
``hobbes-lead`` tools through the real relay (reported as Claude reports an
MCP tool call), so a plan waits on the form the test answers.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hobbes.watterson import roles
from hobbes.watterson.lead import JobResult
from hobbes.watterson.serve.opencode import HobbesServer, job_notice

from .test_watterson_dispatch import git, write_roles
from .test_watterson_freshness import commit
from .test_watterson_lead import ROLES
from .test_watterson_serve import serve, start_session, types, until


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


def lead(tool: str, **arguments) -> str:
    """A fake coordinator's prompt part that calls one of its tools."""
    return f"call hobbes-lead {tool} {json.dumps(arguments)}"


async def rpc_mode(client, **given):
    status, body = await client.call("POST", "/api/rpc/hobbes/mode", {"input": given})
    assert status == 200
    return body["output"]


def said(seen: list, sid: str) -> str:
    return "".join(e["data"]["delta"] for e in seen if e["type"] == "session.text.delta"
                   and e["data"]["sessionID"] == sid)


async def until_in(events: asyncio.Queue, kind: str, seen: list, sid: str, timeout: float = 60) -> dict:
    """As ``until``, for the first event of *kind* in session *sid*, including
    one already in *seen* (sessions' events interleave)."""
    def match(event: dict) -> bool:
        return event["type"] == kind and (event["data"].get("sessionID") == sid
                                          or event["data"].get("form", {}).get("sessionID") == sid)

    async def go():
        if found := next((e for e in seen if match(e)), None):
            return found
        while True:
            event = await events.get()
            seen.append(event)
            if match(event):
                return event
    return await asyncio.wait_for(go(), timeout)


async def until_nth(events: asyncio.Queue, kind: str, seen: list, sid: str, n: int, timeout: float = 60) -> dict:
    """The *n*-th event of *kind* in session *sid*, counting those already in *seen*."""
    def found() -> list:
        return [e for e in seen if e["type"] == kind and e["data"].get("sessionID") == sid]

    async def go():
        while len(found()) < n:
            seen.append(await events.get())
        return found()[n - 1]
    return await asyncio.wait_for(go(), timeout)


class TestMode:
    def test_mapped_needs_a_coordinator(self, repo):
        write_roles(repo, ROLES.replace('coordinator = "lead"\n', ""))

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            return await rpc_mode(client, sessionID=sid), await rpc_mode(client, sessionID=sid, mode="mapped")

        read, refused = serve(repo, body)
        assert (read["mode"], read["mapped"]) == ("default", False) and "no coordinator" in read["detail"]
        assert refused["error"].startswith("No agent mapping here: ")

    def test_a_session_switches_and_new_ones_start_in_the_home_choice(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            switched = await rpc_mode(client, sessionID=sid, mode="mapped")
            pushed = await until(events, "rpc.hobbes.mode", seen)
            home = await rpc_mode(client, mode="mapped")
            other = await start_session(client, events, seen, repo)
            errors = (await rpc_mode(client, mode="yolo"), await rpc_mode(client, sessionID="ses_x"))
            return switched, pushed, home, app.sessions[other].mode, errors

        switched, pushed, home, other, errors = serve(repo, body)
        assert (switched["mode"], switched["mapped"]) == ("mapped", True)
        assert pushed["data"] == {"sessionID": switched["sessionID"], "mode": "mapped"}
        assert (home["sessionID"], home["mode"]) == (None, "mapped") and other == "mapped"
        assert "unknown mode 'yolo'" in errors[0]["error"] and errors[1]["error"] == "no session ses_x"

    def test_the_mode_survives_a_restart(self, repo, tmp_path):
        store = tmp_path / "store"

        async def first(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            return sid

        sid = serve(repo, first, store=store)
        assert HobbesServer(repo, {}, store=store, ingest_log=tmp_path / "log").sessions[sid].mode == "mapped"

    def test_the_home_choice_survives_a_restart_per_repo(self, repo, tmp_path):
        store = tmp_path / "store"

        async def choose(app, client):
            return await rpc_mode(client, mode="mapped")

        assert serve(repo, choose, store=store)["mode"] == "mapped"
        again = HobbesServer(repo, {}, store=store, ingest_log=tmp_path / "log")
        other = HobbesServer(tmp_path, {}, store=store, ingest_log=tmp_path / "log")
        assert (again.next_mode, other.next_mode) == ("mapped", "default")


class TestJob:
    def test_a_prompt_is_a_job_with_the_plan_as_a_form(self, repo):
        job = " && ".join([lead("propose_plan", plan="1. impl: add ok"),
                           lead("dispatch", role="impl", brief="write src/ok.txt hi"),
                           lead("wait"),
                           "write docs/notes.md done",
                           lead("finish", summary="all done")])

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_j", "text": job})
            created = await until(events, "form.created", seen)
            listed = await client.call("GET", f"/api/session/{sid}/form")
            form = created["data"]["form"]
            reply = await client.call("POST", f"/api/session/{sid}/form/{form['id']}/reply",
                                      {"answer": {"answer": "y looks good"}})
            await until_in(events, "session.execution.succeeded", seen, sid)
            notice = await until_in(events, "session.synthetic", seen, sid)
            return sid, created, listed, reply, notice, seen

        sid, created, listed, reply, notice, seen = serve(repo, body)
        form = created["data"]["form"]
        assert created["location"] == {"directory": str(repo)}
        assert form["metadata"]["message"] == "1. impl: add ok"
        assert [f["key"] for f in form["fields"]] == ["answer"] and form["fields"][0]["custom"]
        assert [f["id"] for f in listed[1]["data"]] == [form["id"]] and reply[0] == 204
        assert "called propose_plan: Approved. The user adds: looks good" in said(seen, sid)
        assert '"outcome": "merged"' in said(seen, sid) and "called finish: Finished." in said(seen, sid)
        assert (repo / "src" / "ok.txt").read_text() == "hi\n"
        assert git(repo, "log", "-1", "--format=%s").startswith("docs: call hobbes-lead propose_plan")
        text = notice["data"]["description"]
        assert text.startswith("Job ") and ": finished: all done\n- impl hobbes/impl-" in text
        assert ": merged\n" in text and "Docs committed " in text and text.endswith(": docs/notes.md")
        assert "form.replied" in types(seen)

    def test_a_dismissed_plan_dispatches_nothing(self, repo):
        job = " && ".join([lead("propose_plan", plan="1. impl"), lead("dispatch", role="impl", brief="write src/ok.txt hi")])

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_j", "text": job})
            form = (await until(events, "form.created", seen))["data"]["form"]
            cancel = await client.call("DELETE", f"/api/session/{sid}/form/{form['id']}?message=")
            await until_in(events, "session.execution.succeeded", seen, sid)
            notice = await until_in(events, "session.synthetic", seen, sid)
            return sid, cancel, notice, seen

        sid, cancel, notice, seen = serve(repo, body)
        assert cancel[0] == 204 and "form.cancelled" in types(seen)
        assert "called propose_plan: Not approved. Revise the plan or end your turn." in said(seen, sid)
        assert "Propose a plan and have it approved before dispatching. [error]" in said(seen, sid)
        assert notice["data"]["description"].endswith(": not finished")
        assert not (repo / "src" / "ok.txt").exists()

    def test_interrupt_ends_the_job_and_its_form(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_j", "text": lead("propose_plan", plan="p")})
            await until(events, "form.created", seen)
            out = await client.call("POST", f"/api/session/{sid}/interrupt")
            await until(events, "session.execution.interrupted", seen, timeout=30)
            return out, seen, app.sessions[sid]

        out, seen, session = serve(repo, body)
        assert out == (200, {"interrupted": True}) and "form.cancelled" in types(seen)
        assert not session.running and not session.forms

    def test_a_dirty_checkout_fails_the_turn(self, repo):
        (repo / "src" / "keep.txt").write_text("edited\n")

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_j", "text": "anything"})
            return await until(events, "session.execution.failed", seen, timeout=30)

        failed = serve(repo, body)
        assert failed["data"]["error"]["message"] == (
            "The job could not start: your checkout of main has uncommitted changes")


class TestWorkers:
    """Slice 3c: each dispatch is a child session the coordinator's call opens."""

    def job(self, repo, brief: str, after=None):
        """A mapped session, a job with one dispatch of *brief*, its plan approved."""
        text = " && ".join([lead("propose_plan", plan="1. impl"), lead("dispatch", role="impl", brief=brief),
                            lead("wait")])

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_j", "text": text})
            form = (await until_in(events, "form.created", seen, sid))["data"]["form"]
            await client.call("POST", f"/api/session/{sid}/form/{form['id']}/reply", {"answer": {"answer": "y"}})
            created = await until(events, "session.created", seen)
            child = created["data"]["sessionID"]
            extra = await after(client, events, seen, sid, child) if after else None
            await until_in(events, "session.execution.succeeded" if after is None else "session.execution.interrupted",
                           seen, sid)
            lists = (await client.call("GET", f"/api/session?parentID={sid}"),
                     await client.call("GET", "/api/session?parentID=null"))
            return sid, created, seen, lists, extra, app

        return serve(repo, body)

    def test_a_worker_runs_in_a_child_session_the_dispatch_opens(self, repo):
        sid, created, seen, (children, roots), _, app = self.job(repo, "write src/ok.txt hi")
        child = created["data"]["sessionID"]
        assert created["data"]["parentID"] == sid and created["data"]["title"] == "write src/ok.txt hi"
        assert [s["id"] for s in children[1]["data"]] == [child] and children[1]["data"][0]["parentID"] == sid
        assert [s["id"] for s in roots[1]["data"]] == [sid]
        assert said(seen, child) == "role: [hobbes role: impl]\nwrote src/ok.txt"
        task = next(e for e in seen if e["type"] == "session.tool.input.started" and e["data"]["name"] == "task")
        called = next(e for e in seen if e["type"] == "session.tool.called" and e["data"]["id"] == task["data"]["id"])
        assert task["data"]["sessionID"] == sid
        assert called["data"]["input"] == {"description": "write src/ok.txt hi", "subagent_type": "impl",
                                           "prompt": "write src/ok.txt hi"}
        progress = next(e for e in seen if e["type"] == "session.tool.progress")
        success = next(e for e in seen if e["type"] == "session.tool.success" and e["data"]["id"] == task["data"]["id"])
        assert progress["data"]["metadata"] == success["data"]["metadata"] == {"sessionID": child}
        ended = [e for e in seen if e["data"].get("sessionID") == child and e["type"] in (
            "session.execution.succeeded", "session.synthetic")]
        assert [e["type"] for e in ended] == ["session.execution.succeeded", "session.synthetic"]
        assert ended[1]["data"]["description"].startswith("impl hobbes/impl-") and ": merged" in ended[1]["data"]["description"]
        assert not app.sessions[child].running

    def test_a_child_takes_no_prompts_and_its_interrupt_stops_the_job(self, repo):
        async def after(client, events, seen, sid, child):
            await until_in(events, "session.text.delta", seen, child)  # the worker is hanging
            prompt = await client.call("POST", f"/api/session/{child}/prompt", {"id": "msg_c", "text": "hi"})
            out = await client.call("POST", f"/api/session/{child}/interrupt")
            await until_in(events, "session.execution.interrupted", seen, child)
            return prompt, out

        sid, created, seen, _, (prompt, out), app = self.job(repo, "hang here", after)
        child = created["data"]["sessionID"]
        assert prompt[0] == 400 and "takes no prompts" in prompt[1]["message"]
        assert out == (200, {"interrupted": True})
        assert not app.sessions[child].running and not app.sessions[sid].running


    def test_parallel_workers_each_get_a_linked_child(self, repo):
        text = " && ".join([lead("propose_plan", plan="1. impl a\n2. impl b"),
                            lead("dispatch", role="impl", brief="write src/ok.txt hi"),
                            lead("dispatch", role="impl", brief="write src/ok.txt hi"),
                            lead("wait")])

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapped")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_j", "text": text})
            form = (await until_in(events, "form.created", seen, sid))["data"]["form"]
            await client.call("POST", f"/api/session/{sid}/form/{form['id']}/reply", {"answer": {"answer": "y"}})
            notice = await until_in(events, "session.synthetic", seen, sid)
            return sid, notice, seen, await client.call("GET", f"/api/session?parentID={sid}")

        sid, notice, seen, children = serve(repo, body)
        kids = {s["id"] for s in children[1]["data"]}
        links = [e["data"]["metadata"]["sessionID"] for e in seen if e["type"] == "session.tool.progress"]
        assert len(kids) == 2 and set(links) == kids and len(links) == 2
        assert notice["data"]["description"].count(": merged") == 2, notice["data"]["description"]


def test_the_notice_names_each_ending_and_the_report():
    result = JobResult("j1", "job", "lead", summary=None, reason="left uncommitted: outside role lead's writes: x")
    result.dispatches = [
        {"role": "impl", "branch": "hobbes/impl-1", "merged": False, "outcome": "review",
         "reason": "paused for review: the worker asked", "report": "Changed a.\nChecked b."},
        {"role": "impl", "branch": "hobbes/impl-2", "merged": False, "outcome": "stopped",
         "reason": "the worker reported it is blocked", "report": ""},
    ]
    assert job_notice(result) == (
        "Job j1: not finished\n"
        "- impl hobbes/impl-1: kept for review: paused for review: the worker asked\n"
        "  Changed a.\n  Checked b.\n"
        "- impl hobbes/impl-2: stopped: the worker reported it is blocked\n"
        "Docs left uncommitted: outside role lead's writes: x")


class TestMappingMode:
    """DEC-023: an ``edit mapping`` session sends each prompt to the mapper."""

    def save(self) -> str:
        return ("call hobbes-mapper save_mapping " + json.dumps({"roles_toml": ROLES, "prompts": {
            "roles/lead.md": "You coordinate.", "roles/impl.md": "You implement."}}))

    def test_a_prompt_saves_the_mapping_with_hobbes_off(self, repo):
        (repo / ".hobbes" / "roles.toml").unlink()

        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            chosen = await rpc_mode(client, sessionID=sid, mode="mapping")
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_m", "text": self.save()})
            await until_nth(events, "session.synthetic", seen, sid, 2)
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_n", "text": "cwd?"})
            await until_nth(events, "session.synthetic", seen, sid, 4)
            return sid, chosen, seen, app.sessions[sid]

        sid, chosen, seen, session = serve(repo, body)
        assert chosen["mode"] == "mapping"
        notes = [e["data"]["description"] for e in seen if e["type"] == "session.synthetic"]
        assert notes[0].startswith("Hobbes is off: the mapper reads the files")
        assert "Mapping saved to .hobbes/roles.toml, 2 role(s): lead, impl; coordinator lead." in notes
        assert notes[-1] == "Mapping not saved: the model did not call save_mapping."
        assert roles.load(repo).coordinator == "lead"
        assert session.mapper_requests == [self.save(), "cwd?"]

    def test_a_request_waits_for_hobbes_to_start(self, repo):
        async def body(app, client):
            events, seen = await client.events(), []
            sid = await start_session(client, events, seen, repo)
            await rpc_mode(client, sessionID=sid, mode="mapping")

            async def starting():
                await asyncio.sleep(0.3)
                app.layer.state = "on"
            app.layer.state, app.layer._task = "starting", asyncio.create_task(starting())
            await client.call("POST", f"/api/session/{sid}/prompt", {"id": "msg_m", "text": "mcp?"})
            await until_in(events, "session.execution.succeeded", seen, sid)
            return seen

        notes = [e["data"]["description"] for e in serve(repo, body) if e["type"] == "session.synthetic"]
        assert notes[0].startswith("Waiting for Hobbes to start")
        assert not any(n.startswith("Hobbes is off") for n in notes)

    def test_new_sessions_start_in_it_with_no_mapping(self, repo):
        (repo / ".hobbes" / "roles.toml").unlink()

        async def body(app, client):
            events, seen = await client.events(), []
            await rpc_mode(client, mode="mapping")
            sid = await start_session(client, events, seen, repo)
            return app.sessions[sid].mode

        assert serve(repo, body) == "mapping"
