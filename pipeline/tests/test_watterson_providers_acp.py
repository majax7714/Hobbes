"""End-to-end tests of the ACP client against a real fake-agent subprocess.

``fixtures/fake_acp_agent.py`` is a small agent built on the ACP SDK's agent
side; each test spawns it through ``hobbes.watterson.providers`` and checks the event
stream, the permission callback, cancellation and shutdown. No real harness,
network or credentials are involved.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

from hobbes.watterson.providers import (
    AgentError,
    AgentSession,
    AgentSpec,
    FileDiff,
    PermissionDecision,
    Plan,
    StdioMcpServer,
    TextChunk,
    ToolCall,
    ToolCallUpdate,
    TurnEnded,
    allow_all,
    run_prompt,
)

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


def fake_spec(**env: str) -> AgentSpec:
    return AgentSpec("fake", (sys.executable, str(FAKE_AGENT)), env=dict(env))


async def collect(events) -> list:
    async with contextlib.aclosing(events) as stream:
        return [event async for event in stream]


def text_of(events) -> str:
    return "".join(e.text for e in events if isinstance(e, TextChunk))


def gone(pid: int, wait: float = 5.0) -> bool:
    """True once *pid* has exited (a zombie awaiting its reaper counts)."""
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except (FileNotFoundError, ProcessLookupError):
            return True
        if state in ("Z", "X"):
            return True
        time.sleep(0.05)
    return False


class TestEventStream:
    def test_a_turn_streams_plan_tool_permission_text_and_end(self):
        events = asyncio.run(collect(run_prompt(fake_spec(), "hello there world", on_permission=allow_all)))
        kinds = [type(e) for e in events]
        assert kinds[:4] == [Plan, ToolCall, PermissionDecision, ToolCallUpdate]
        assert events[0].entries[0].content == "echo the prompt"
        assert events[1] == ToolCall("tool-1", "Echo tool", "other", "pending")
        assert events[3] == ToolCallUpdate("tool-1", "completed")
        assert text_of(events) == "hello there world [permission: allowed]"
        assert [e.text for e in events if isinstance(e, TextChunk)][:3] == ["hello", " there", " world"]
        assert events[-1] == TurnEnded("end_turn")

    def test_tool_calls_carry_their_input_and_output(self):
        events = asyncio.run(collect(run_prompt(fake_spec(), "output two lines")))
        assert events[0] == ToolCall("tool-3", "Output tool", "read", "in_progress", {"text": "two lines"})
        assert events[1] == ToolCallUpdate("tool-3", "completed", None, None, {"length": 9}, "two lines")

    def test_updates_outside_a_turn_are_dropped(self):
        # The fake agent says "cwd=…" while opening the session.
        events = asyncio.run(collect(run_prompt(fake_spec(), "hi")))
        assert "cwd=" not in text_of(events)

    def test_two_turns_on_one_session(self):
        async def go():
            async with AgentSession(fake_spec(), on_permission=allow_all) as session:
                assert session.agent_name == "fake-agent 0.0.1"
                first = await collect(session.prompt("one"))
                second = await collect(session.prompt("two"))
                return first, second

        first, second = asyncio.run(go())
        assert text_of(first).startswith("one ") and text_of(second).startswith("two ")


class TestPermissions:
    def test_denied_by_default(self):
        events = asyncio.run(collect(run_prompt(fake_spec(), "hi")))
        decision = next(e for e in events if isinstance(e, PermissionDecision))
        assert decision.option_id == "no" and not decision.allowed
        assert ToolCallUpdate("tool-1", "failed") in events
        assert text_of(events).endswith("[permission: denied]")

    def test_the_callback_sees_the_request_and_may_be_async(self):
        seen = []

        async def choose(request):
            seen.append(request)
            await asyncio.sleep(0)
            return "yes"

        events = asyncio.run(collect(run_prompt(fake_spec(), "hi", on_permission=choose)))
        (request,) = seen
        assert request.tool_call_id == "tool-1" and request.title == "Echo tool"
        assert [(o.id, o.kind) for o in request.options] == [("yes", "allow_once"), ("no", "reject_once")]
        assert text_of(events).endswith("[permission: allowed]")

    @pytest.mark.parametrize("answer", [None, "not-an-option"])
    def test_none_or_an_unknown_option_cancels_the_request(self, answer):
        events = asyncio.run(collect(run_prompt(fake_spec(), "hi", on_permission=lambda r: answer)))
        decision = next(e for e in events if isinstance(e, PermissionDecision))
        assert decision.option_id is None
        assert text_of(events).endswith("[permission: cancelled]")


class TestRequestDetails:
    """A permission request carries the call's kind, raw input and paths (DEC-007)."""

    def requests(self, prompt: str, tmp_path) -> list:
        seen = []

        def record(request):
            seen.append(request)
            return None

        events = asyncio.run(collect(run_prompt(fake_spec(), prompt, cwd=tmp_path, on_permission=record)))
        assert text_of(events).endswith("[permission: cancelled]")
        return seen

    def test_an_edit_names_its_file(self, tmp_path):
        (request,) = self.requests("edit src/a.py", tmp_path)
        path = str(tmp_path / "src/a.py")
        assert request.kind == "edit" and request.title == "edit src/a.py"
        assert request.raw_input == {"file_path": path}
        assert request.paths == (path,)  # the location and the diff, once
        assert request.diffs == (FileDiff(path, "old\n", "new\n"),)
        assert [o.kind for o in request.options] == ["allow_once", "allow_always", "reject_once"]

    def test_a_command_carries_its_raw_input(self, tmp_path):
        (request,) = self.requests("run git push origin main", tmp_path)
        assert request.kind == "execute"
        assert request.raw_input == {"command": "git push origin main"}
        assert request.paths == ()

    def test_the_requests_meta_is_kept(self, tmp_path):
        (request,) = self.requests("tool mcp__hobbes__who_calls hobbes:dynamic", tmp_path)
        assert request.meta == {"claudeCode": {"mcpServer": {"name": "hobbes", "source": "dynamic"}}}

    def test_details_from_the_calls_start_are_merged(self, tmp_path):
        (request,) = self.requests("late-edit b.py", tmp_path)
        assert request.kind == "edit" and request.paths == (str(tmp_path / "b.py"),)
        assert request.raw_input == {"file_path": str(tmp_path / "b.py")}
        assert request.diffs == (FileDiff(str(tmp_path / "b.py"), "old\n", "new\n"),)

    def test_tool_events_carry_paths_and_diffs(self, tmp_path):
        events = asyncio.run(collect(run_prompt(fake_spec(), "late-edit b.py", cwd=tmp_path)))
        (start,) = [e for e in events if isinstance(e, ToolCall)]
        path = str(tmp_path / "b.py")
        assert start.paths == (path,) and start.diffs == (FileDiff(path, "old\n", "new\n"),)


class TestModes:
    def mode_of(self, modes: tuple[str, ...], offered: str = "") -> tuple[str | None, tuple, str]:
        async def go():
            spec = fake_spec(FAKE_AGENT_MODES=offered) if offered else fake_spec()
            async with AgentSession(spec, modes=modes) as session:
                reply = text_of(await collect(session.prompt("mode?")))
                return session.mode, session.available_modes, reply

        return asyncio.run(go())

    def test_the_first_offered_preference_is_set(self):
        mode, available, reply = self.mode_of(("auto", "default"), "default,auto,plan")
        assert (mode, reply) == ("auto", "mode=auto") and available == ("default", "auto", "plan")

    def test_falls_back_to_the_next_preference(self):
        mode, _, reply = self.mode_of(("auto", "default"), "default,plan")
        assert (mode, reply) == ("default", "mode=default")

    def test_none_offered_leaves_the_agents_mode(self):
        assert self.mode_of(("auto",), "plan,default")[:1] == ("plan",)
        mode, available, _ = self.mode_of(("auto",))
        assert mode is None and available == ()


class TestCancel:
    def test_cancel_ends_the_turn_as_cancelled_and_the_session_lives_on(self):
        async def go():
            async with AgentSession(fake_spec()) as session:
                events = []
                async with contextlib.aclosing(session.prompt("hang on")) as stream:
                    async for event in stream:
                        events.append(event)
                        if isinstance(event, TextChunk):
                            await session.cancel()
                after = await collect(session.prompt("again"))
                return events, after

        events, after = asyncio.run(go())
        assert events == [TextChunk("hang"), TurnEnded("cancelled")]
        assert after[-1] == TurnEnded("end_turn")

    def test_breaking_out_early_cancels_the_turn_on_the_agent(self):
        async def go():
            async with AgentSession(fake_spec(), cancel_timeout=5) as session:
                async with contextlib.aclosing(session.prompt("hang on")) as stream:
                    async for _ in stream:
                        break
                # Without a session/cancel the agent would still be hanging,
                # and a second prompt on the session would be refused.
                return await collect(session.prompt("again"))

        started = time.monotonic()
        after = asyncio.run(go())
        assert after[-1] == TurnEnded("end_turn")
        assert time.monotonic() - started < 5


class TestShutdown:
    def test_close_reaps_the_agent_and_its_children(self, tmp_path):
        pidfile = tmp_path / "child.pid"

        async def go():
            session = AgentSession(fake_spec(FAKE_AGENT_CHILD_PIDFILE=str(pidfile)))
            async with session:
                await collect(session.prompt("hi"))
                pid = session.pid
                assert not gone(pid, wait=0)
            return pid, session

        pid, session = asyncio.run(go())
        child = int(pidfile.read_text())
        assert gone(pid) and gone(child)
        assert session.stderr_tail() == "fake-agent: ready"

    def test_an_agent_that_never_answers_times_out_and_is_killed(self):
        spec = AgentSpec("mute", (sys.executable, "-c", "import time; time.sleep(60)"))

        async def go():
            session = AgentSession(spec, start_timeout=0.5, shutdown_timeout=0.5)
            with pytest.raises(AgentError, match="no answer within"):
                await session.start()
            return session

        started = time.monotonic()
        asyncio.run(go())
        assert time.monotonic() - started < 10

    def test_an_agent_that_dies_reports_exit_code_and_stderr(self):
        spec = AgentSpec("dies", (sys.executable, "-c", "import sys; sys.stderr.write('boom\\n'); sys.exit(3)"))
        with pytest.raises(AgentError) as info:
            asyncio.run(collect(run_prompt(spec, "hi")))
        message = str(info.value)
        assert "disconnected during initialize" in message and "exit code 3" in message
        assert info.value.stderr_tail == "boom"

    def test_a_missing_command_is_a_clear_error(self):
        spec = AgentSpec("nope", ("hobbes-no-such-agent-binary",))
        with pytest.raises(AgentError, match="cannot start 'hobbes-no-such-agent-binary'"):
            asyncio.run(collect(run_prompt(spec, "hi")))

    def test_a_missing_command_names_its_install_hint(self, tmp_path):
        missing = str(tmp_path / "node_modules" / ".bin" / "claude-agent-acp")
        spec = AgentSpec("claude", (missing,), install_hint="run `cd adapters && npm ci` at the repo root")
        with pytest.raises(AgentError, match=r"cannot start .*; run `cd adapters && npm ci`"):
            asyncio.run(collect(run_prompt(spec, "hi")))

    def test_the_agent_gets_the_callers_environment_plus_the_spec_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOBBES_TEST_INHERITED", "from-parent")
        out = tmp_path / "env.txt"
        script = (
            "import os, pathlib; pathlib.Path(os.environ['OUT']).write_text("
            "os.environ.get('HOBBES_TEST_INHERITED', '') + '|' + os.environ.get('EXTRA', '') + '|' + os.getcwd())"
        )
        spec = AgentSpec("env", (sys.executable, "-c", script), env={"OUT": str(out), "EXTRA": "x"})
        with pytest.raises(AgentError):
            asyncio.run(collect(run_prompt(spec, "hi", cwd=tmp_path)))
        assert out.read_text() == f"from-parent|x|{os.path.realpath(tmp_path)}"


class TestMcpServers:
    def servers_seen(self, servers) -> list:
        async def go():
            async with AgentSession(fake_spec(), mcp_servers=servers) as session:
                return json.loads(text_of(await collect(session.prompt("mcp?"))))

        return asyncio.run(go())

    def test_none_by_default(self):
        assert self.servers_seen(()) == []

    def test_stdio_servers_reach_session_new(self):
        server = StdioMcpServer("hobbes", "/opt/hobbes-proxy", ("serve", "--knowledge-only"), {"A": "1"})
        assert self.servers_seen([server]) == [{
            "name": "hobbes", "command": "/opt/hobbes-proxy",
            "args": ["serve", "--knowledge-only"], "env": [{"name": "A", "value": "1"}],
        }]
