"""Tests for the provider subcommands: ``hobbes agents``, ``ask``, ``complete``.

Kept apart from ``test_cli.py``, which stays a copy of hobbes-public's
ingest tests. ``ask`` runs against the fake ACP agent fixture, registered
through a ``HOBBES_AGENTS_FILE`` override; ``complete`` runs with
``any_llm.completion`` faked. Nothing reaches a real harness or API.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import any_llm
import pytest
from any_llm.types.completion import ChatCompletionChunk

from hobbes.watterson import cli
from hobbes.watterson.providers import registry

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


@pytest.fixture
def agents_file(tmp_path, monkeypatch):
    path = tmp_path / "agents.toml"
    command = json.dumps([sys.executable, str(FAKE_AGENT)])
    path.write_text(
        f"[agents.fake]\ncommand = {command}\n"
        '[agents.ghost]\ncommand = ["hobbes-no-such-agent-binary"]\n'
    )
    monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))
    return path


class TestAgents:
    def test_lists_builtins_and_overrides_with_availability(self, agents_file, capsys):
        assert cli.main(["agents"]) == 0
        out = capsys.readouterr().out
        bins = registry.ADAPTERS_DIR / "node_modules" / ".bin"
        for line in (
            f"claude  {bins / 'claude-agent-acp'}",
            f"codex   {bins / 'codex-acp'}",
            "gemini  gemini --acp",
            f"fake    {sys.executable} {FAKE_AGENT}",
            "ghost   hobbes-no-such-agent-binary",
        ):
            assert line in out
        assert f"{FAKE_AGENT}\n          available; {agents_file}" in out
        assert f"missing: hobbes-no-such-agent-binary not on PATH; {agents_file}" in out
        assert f"overrides: {agents_file}" in out

    def test_a_missing_adapter_bin_is_unavailable_with_the_install_hint(
        self, agents_file, tmp_path, monkeypatch, capsys
    ):
        locked = registry.LOCKED_ADAPTERS[0]
        missing = registry.adapter_bin(locked, tmp_path / "adapters")
        spec = registry.AgentSpec("claude", (str(missing),), install_hint=registry.ADAPTERS_INSTALL_HINT)
        monkeypatch.setattr(registry, "BUILTIN_AGENTS", {"claude": spec})
        assert cli.main(["agents"]) == 0
        out = capsys.readouterr().out
        assert (
            f"missing: {missing} not found; run `cd adapters && npm ci` at the repo root; built-in"
            in out
        )
        assert cli.main(["ask", "--agent", "claude", "hi"]) == 1
        err = capsys.readouterr().err
        assert f"cannot start '{missing}'" in err and "cd adapters && npm ci" in err

    def test_a_bad_override_file_is_reported(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "agents.toml"
        bad.write_text("[agents.x]\ncommand = []\n")
        monkeypatch.setenv("HOBBES_AGENTS_FILE", str(bad))
        assert cli.main(["agents"]) == 1
        assert "non-empty list" in capsys.readouterr().err


class TestAsk:
    def test_streams_the_reply_and_denies_permissions_by_default(self, agents_file, capsys):
        assert cli.main(["ask", "--agent", "fake", "hello world"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "hello world [permission: denied]\n"
        assert "[tool] Echo tool" in captured.err
        assert "[permission] Echo tool: denied (--allow-permissions to allow)" in captured.err

    def test_allow_permissions(self, agents_file, capsys):
        assert cli.main(["ask", "--agent", "fake", "--allow-permissions", "hi"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "hi [permission: allowed]\n"
        assert "[permission] Echo tool: allowed" in captured.err

    def test_an_unknown_agent(self, agents_file, capsys):
        assert cli.main(["ask", "--agent", "nope", "hi"]) == 1
        assert "unknown agent 'nope'" in capsys.readouterr().err

    def test_an_agent_that_cannot_start(self, agents_file, capsys):
        assert cli.main(["ask", "--agent", "ghost", "hi"]) == 1
        assert "cannot start 'hobbes-no-such-agent-binary'" in capsys.readouterr().err


class TestAskRoutes:
    """``--route`` (DEC-007): modes, the hard deny, and allow-once."""

    @pytest.fixture
    def as_claude(self, tmp_path, monkeypatch):
        """The fake agent registered under the name ``claude``, offering modes."""
        path = tmp_path / "agents.toml"
        command = json.dumps([sys.executable, str(FAKE_AGENT)])
        path.write_text(
            f'[agents.claude]\ncommand = {command}\nenv = {{ FAKE_AGENT_MODES = "default,auto,plan" }}\n'
        )
        monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))

    def test_guarded_sets_auto_and_manual_sets_default(self, as_claude, capsys):
        assert cli.main(["ask", "--agent", "claude", "--no-refresh", "mode?"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "mode=auto\n"
        assert "hobbes: route guarded; claude mode auto" in captured.err
        assert cli.main(["ask", "--agent", "claude", "--no-refresh", "--route", "manual", "mode?"]) == 0
        assert capsys.readouterr().out == "mode=default\n"

    def test_an_unknown_agents_mode_is_left_alone(self, agents_file, capsys):
        assert cli.main(["ask", "--agent", "fake", "--no-refresh", "hi"]) == 0
        assert "route guarded; mode left to fake (Hobbes knows no modes for it)" in capsys.readouterr().err

    def test_guarded_denies_an_agent_config_edit_even_when_allowed(self, agents_file, tmp_path, capsys):
        args = ["ask", "--agent", "fake", "--no-refresh", "--repo", str(tmp_path), "--allow-permissions"]
        assert cli.main([*args, "edit .claude/settings.json"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "[permission: no]\n"
        assert ("[permission] edit .claude/settings.json: denied (without asking: it changes "
                "an agent's own permission config (guarded route))") in captured.err

    def test_manual_leaves_it_to_the_caller(self, agents_file, tmp_path, capsys):
        args = ["ask", "--agent", "fake", "--no-refresh", "--repo", str(tmp_path), "--route", "manual"]
        assert cli.main([*args, "--allow-permissions", "edit .claude/settings.json"]) == 0
        assert capsys.readouterr().out == "[permission: yes]\n"  # once, never "always"
        assert cli.main([*args, "run ls"]) == 0
        captured = capsys.readouterr()
        assert captured.out == "[permission: no]\n"
        assert "[permission] run ls: denied (--allow-permissions to allow)" in captured.err


class TestComplete:
    def test_streams_the_reply(self, monkeypatch, capsys):
        seen = {}

        def completion(model, messages, **kwargs):
            seen.update(model=model, messages=messages, **kwargs)
            return iter(
                ChatCompletionChunk.model_validate({
                    "id": "c", "object": "chat.completion.chunk", "created": 0, "model": "m",
                    "choices": [{"index": 0, "delta": {"content": t}, "finish_reason": None}],
                })
                for t in ("Hi", " there")
            )

        monkeypatch.setattr(any_llm, "completion", completion)
        argv = ["complete", "--model", "openai:m", "--system", "terse", "--max-tokens", "5", "hello"]
        assert cli.main(argv) == 0
        assert capsys.readouterr().out == "Hi there\n"
        assert seen["model"] == "openai:m" and seen["stream"] is True and seen["max_tokens"] == 5
        assert seen["messages"] == [
            {"role": "system", "content": "terse"}, {"role": "user", "content": "hello"},
        ]

    def test_a_missing_key_is_a_clear_error(self, monkeypatch, capsys):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert cli.main(["complete", "--model", "anthropic:m", "hi"]) == 1
        assert capsys.readouterr().err == "hobbes: no API key for anthropic: set ANTHROPIC_API_KEY in the environment\n"
