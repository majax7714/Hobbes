"""Tests for Hobbes hooks in Claude sessions (DEC-010).

Hook payloads are built by hand in Claude Code's hook input shape. The
socket tests run ``hook_client.py`` the way Claude would, from the settings
``SessionHooks.meta()`` hands the agent; the fake ACP agent shows that the
settings reach ``session/new``. No real harness runs.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from hobbes.watterson.hooks import CLIENT, EVENTS, SessionHooks, hook_request, log_dir, settings
from hobbes.watterson.permissions import Route, RoutePolicy
from hobbes.watterson.providers import AgentSession, AgentSpec, TextChunk

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


def pre(tool: str, tool_input: dict, tool_use_id: str = "toolu_1", event: str = "PreToolUse") -> dict:
    return {"hook_event_name": event, "tool_name": tool, "tool_input": tool_input,
            "tool_use_id": tool_use_id, "session_id": "s", "cwd": "/", "transcript_path": "/t"}


@pytest.fixture
def repo(tmp_path) -> Path:
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    return root


def hooks(route: Route, repo: Path, tmp_path: Path) -> SessionHooks:
    return SessionHooks(route, repo, logs=tmp_path / "logs")


async def run_hook(command: dict, payload: dict) -> tuple[int, bytes]:
    proc = await asyncio.create_subprocess_exec(
        command["command"], *command["args"],
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate(json.dumps(payload).encode())
    return proc.returncode, out


class TestSettings:
    def test_exec_form_hooks_for_each_event(self):
        doc = settings("/tmp/x/s", python="/py")
        assert set(doc["hooks"]) == set(EVENTS)
        for groups in doc["hooks"].values():
            (group,) = groups
            (hook,) = group["hooks"]
            assert group["matcher"] == "*"
            assert hook["type"] == "command" and hook["command"] == "/py"
            assert hook["args"] == ["-I", "-S", str(CLIENT), "/tmp/x/s"]

    def test_log_dir(self):
        assert log_dir({"HOBBES_CACHE_DIR": "/c"}) == Path("/c/permissions")

    def test_hook_request(self):
        req = hook_request(pre("Write", {"file_path": "/r/a.py"}))
        assert (req.tool_call_id, req.title, req.kind, req.raw_input) == (
            "toolu_1", "Write", "edit", {"file_path": "/r/a.py"})
        assert hook_request(pre("mcp__x__y", {})).kind == "other"


class TestAnswer:
    def test_guarded_denies_an_agent_config_edit(self, repo, tmp_path):
        h = hooks(Route.GUARDED, repo, tmp_path)
        reply = h.answer(pre("Write", {"file_path": str(repo / ".claude/settings.json")}))
        out = reply["hookSpecificOutput"]
        assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
        assert "permission config" in out["permissionDecisionReason"]
        assert h.counts()["hobbes_denied"] == 1

    def test_manual_only_observes_it(self, repo, tmp_path):
        h = hooks(Route.MANUAL, repo, tmp_path)
        assert h.answer(pre("Write", {"file_path": str(repo / ".claude/settings.json")})) == {}

    def test_everything_else_gets_no_opinion(self, repo, tmp_path):
        h = hooks(Route.GUARDED, repo, tmp_path)
        assert h.answer(pre("Edit", {"file_path": str(repo / "a.py")})) == {}
        assert h.answer(pre("Bash", {"command": "cat .claude/settings.json"})) == {}  # warned, never denied

    def test_counts(self, repo, tmp_path):
        h = hooks(Route.GUARDED, repo, tmp_path)
        h.answer(pre("Read", {"file_path": "a"}, "t1"))
        h.answer(pre("Read", {"file_path": "a"}, "t1", event="PostToolUse"))
        h.answer(pre("Bash", {"command": "rm -rf /"}, "t2"))
        h.answer({**pre("Bash", {"command": "rm -rf /"}, "t2", event="PermissionDenied"), "reason": "no"})
        h.answer(pre("Bash", {"command": "git push"}, "t3"))
        h.calls["t3"]["asked"] = True
        assert h.counts() == {"tool_calls": 3, "decided_alone": 2, "harness_denied": 1,
                              "asked": 1, "hobbes_denied": 0}
        assert h.summary().startswith(
            "permissions: 3 tool call(s); claude decided 2 alone (1 denied); 1 reached Hobbes; "
            "Hobbes denied 0 before claude's judge; log ")


class TestOverTheSocket:
    def test_the_client_gets_the_deny_and_the_log_has_each_call(self, repo, tmp_path):
        async def go():
            async with hooks(Route.GUARDED, repo, tmp_path) as h:
                (command,) = h.meta()["claudeCode"]["options"]["settings"]["hooks"]["PreToolUse"][0]["hooks"]
                denied = await run_hook(command, pre("Edit", {"file_path": str(repo / ".codex/config.toml")}, "a"))
                plain = await run_hook(command, pre("Edit", {"file_path": str(repo / "x.py")}, "b"))
                return h, denied, plain

        h, (code, out), (plain_code, plain_out) = asyncio.run(go())
        assert code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert plain_code == 0 and plain_out == b""
        lines = [json.loads(line) for line in h.log_path.read_text().splitlines()]
        assert [(e["id"], e["event"], e.get("answer")) for e in lines] == [
            ("a", "PreToolUse", "deny"), ("b", "PreToolUse", None)]
        assert lines[0]["notes"] == ["edits: .codex/config.toml",
                                     "! changes an agent's own permission config: .codex/config.toml"]

    def test_no_hobbes_means_no_opinion(self, tmp_path):
        async def go():
            command = settings(str(tmp_path / "gone"))["hooks"]["PreToolUse"][0]["hooks"][0]
            return await run_hook(command, pre("Write", {"file_path": "/x/.claude/settings.json"}))

        assert asyncio.run(go()) == (0, b"")

    def test_the_socket_dir_is_private_and_removed(self, repo, tmp_path):
        async def go():
            async with hooks(Route.GUARDED, repo, tmp_path) as h:
                parent = Path(h.socket_path).parent
                return parent, parent.stat().st_mode & 0o777

        parent, mode = asyncio.run(go())
        assert mode == 0o700 and not parent.exists()


class TestThroughTheAgent:
    def test_the_settings_reach_session_new_and_requests_are_logged(self, repo, tmp_path):
        spec = AgentSpec("fake", (sys.executable, str(FAKE_AGENT)))

        async def go():
            async with hooks(Route.GUARDED, repo, tmp_path) as h:
                policy = RoutePolicy(Route.GUARDED, repo)  # no one to ask: rejects
                async with AgentSession(spec, cwd=repo, on_permission=h.observe(policy),
                                        meta=h.meta()) as session:
                    meta = "".join([e.text async for e in session.prompt("meta?") if isinstance(e, TextChunk)])
                    edit = "".join([e.text async for e in session.prompt("edit a.py") if isinstance(e, TextChunk)])
                return h, json.loads(meta), edit

        h, meta, edit = asyncio.run(go())
        assert meta == h.meta()
        assert edit.endswith("[permission: no]")
        assert h.counts()["asked"] == 1
        last = json.loads(h.log_path.read_text().splitlines()[-1])
        assert (last["event"], last["answer"]) == ("permission", "reject_once")
