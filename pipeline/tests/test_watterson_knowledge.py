"""Tests for attaching Hobbes's knowledge tools (DEC-008).

No real ``hobbes-proxy`` runs: the binary is a stub script, and the CLI
tests read back what the fake ACP agent received in ``session/new``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hobbes.watterson import cli, knowledge
from hobbes.watterson.providers import PermissionRequest

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


def stub(path: Path, executable: bool = True) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755 if executable else 0o644)
    return path


class TestFindProxy:
    def test_hobbes_proxy_env_wins(self, tmp_path):
        named = stub(tmp_path / "my-proxy")
        on_path = tmp_path / "bin"
        on_path.mkdir()
        stub(on_path / "hobbes-proxy")
        env = {"HOBBES_PROXY": str(named), "PATH": str(on_path)}
        assert knowledge.find_proxy(env) == str(named.resolve())

    def test_a_named_proxy_that_is_missing_or_not_executable_is_none(self, tmp_path):
        assert knowledge.find_proxy({"HOBBES_PROXY": str(tmp_path / "nope")}) is None
        plain = stub(tmp_path / "plain", executable=False)
        assert knowledge.find_proxy({"HOBBES_PROXY": str(plain)}) is None

    def test_falls_back_to_path(self, tmp_path):
        found = stub(tmp_path / "hobbes-proxy")
        assert knowledge.find_proxy({"PATH": str(tmp_path)}) == str(found.resolve())
        assert knowledge.find_proxy({"PATH": str(tmp_path / "empty")}) is None


class TestServer:
    def test_knowledge_only_with_logs_in_our_cache(self, tmp_path):
        logs = knowledge.log_dir({"HOBBES_CACHE_DIR": str(tmp_path / "cache")})
        assert logs == tmp_path / "cache" / "knowledge"
        server = knowledge.server(tmp_path, "/opt/hobbes-proxy", logs)
        assert (server.name, server.command) == ("hobbes", "/opt/hobbes-proxy")
        assert server.args == (
            "serve", "--repo", str(tmp_path.resolve()), "--role", "developer",
            "--knowledge-only", "--log-dir", str(logs),
        )

    def test_titles_cover_both_adapters(self):
        assert "mcp__hobbes__who_calls" in knowledge.TITLES
        assert "mcp.hobbes.list_blind_spots" in knowledge.TITLES
        assert len(knowledge.TITLES) == 2 * len(knowledge.TOOLS) == 12


class TestIsOwnTool:
    def req(self, title, raw=None, meta=None):
        return PermissionRequest("c", title, (), raw_input=raw, meta=meta)

    def claude(self, name="hobbes", source="dynamic"):
        return {"claudeCode": {"toolName": "x", "mcpServer": {"name": name, "source": source, "new": 1}}}

    def test_titles_alone_when_nothing_else_is_said(self):
        assert knowledge.is_own_tool(self.req("mcp__hobbes__who_calls"))
        assert not knowledge.is_own_tool(self.req("mcp__hobbes__exec"))
        assert not knowledge.is_own_tool(self.req(None))

    def test_claude_must_name_our_server_passed_in_at_startup(self):
        assert knowledge.is_own_tool(self.req("mcp__hobbes__who_calls", meta=self.claude()))
        for source in ("user", "project", "local", "sdk", "plugin"):
            assert not knowledge.is_own_tool(self.req("mcp__hobbes__who_calls", meta=self.claude(source=source)))
        assert not knowledge.is_own_tool(self.req("mcp__hobbes__who_calls", meta=self.claude(name="other")))
        assert not knowledge.is_own_tool(
            self.req("mcp__hobbes__who_calls", meta={"claudeCode": {"mcpServer": "hobbes"}})
        )

    def test_codex_raw_input_must_name_our_server_and_tool(self):
        raw = {"server": "hobbes", "tool": "who_calls", "arguments": {}}
        assert knowledge.is_own_tool(self.req("mcp.hobbes.who_calls", raw=raw))
        assert not knowledge.is_own_tool(self.req("mcp.hobbes.who_calls", raw={**raw, "server": "h"}))
        assert not knowledge.is_own_tool(self.req("mcp.hobbes.who_calls", raw={**raw, "tool": "exec"}))


class TestAsk:
    @pytest.fixture
    def agents_file(self, tmp_path, monkeypatch):
        path = tmp_path / "agents.toml"
        command = json.dumps([sys.executable, str(FAKE_AGENT)])
        path.write_text(f"[agents.fake]\ncommand = {command}\n")
        monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))

    @pytest.fixture
    def proxy(self, tmp_path, monkeypatch) -> Path:
        path = stub(tmp_path / "hobbes-proxy")
        monkeypatch.setenv("HOBBES_PROXY", str(path))
        monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
        return path

    @pytest.fixture
    def repo(self, tmp_path) -> Path:
        root = tmp_path / "repo"
        root.mkdir()
        return root.resolve()

    def ask(self, *argv: str) -> int:
        return cli.main(["ask", "--agent", "fake", "--no-refresh", *argv])

    def test_attached_with_repo(self, agents_file, proxy, repo, tmp_path, capsys):
        assert self.ask("--repo", str(repo), "mcp?") == 0
        captured = capsys.readouterr()
        (server,) = json.loads(captured.out)
        assert server["name"] == "hobbes" and server["command"] == str(proxy.resolve())
        assert server["args"] == [
            "serve", "--repo", str(repo), "--role", "developer", "--knowledge-only",
            "--log-dir", str(tmp_path / "cache" / "knowledge"),
        ]
        assert f"hobbes: knowledge tools on ({proxy.resolve()})" in captured.err

    def test_not_attached_without_repo_or_with_no_knowledge(self, agents_file, proxy, repo, capsys):
        assert self.ask("mcp?") == 0
        assert capsys.readouterr().out == "[]\n"
        assert self.ask("--repo", str(repo), "--no-knowledge", "mcp?") == 0
        assert capsys.readouterr().out == "[]\n"

    def test_a_missing_proxy_warns_and_runs_without(self, agents_file, repo, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOBBES_PROXY", str(tmp_path / "nope"))
        assert self.ask("--repo", str(repo), "mcp?") == 0
        captured = capsys.readouterr()
        assert captured.out == "[]\n"
        assert f"hobbes: knowledge tools off: {knowledge.NOT_FOUND}" in captured.err

    def test_knowledge_tools_are_allowed_once_without_asking(self, agents_file, proxy, repo, capsys):
        assert self.ask("--repo", str(repo), "tool mcp__hobbes__who_calls") == 0
        captured = capsys.readouterr()
        assert captured.out == "[permission: yes]\n"
        assert ("[permission] mcp__hobbes__who_calls: allowed "
                "(Hobbes's own knowledge tool (DEC-008))") in captured.err

    def test_a_same_named_server_from_a_config_file_is_not_ours(self, agents_file, proxy, repo, capsys):
        assert self.ask("--repo", str(repo), "tool mcp__hobbes__who_calls hobbes:dynamic") == 0
        assert capsys.readouterr().out == "[permission: yes]\n"
        assert self.ask("--repo", str(repo), "tool mcp__hobbes__who_calls hobbes:project") == 0
        assert capsys.readouterr().out == "[permission: no]\n"

    def test_other_mcp_tools_and_a_detached_proxy_still_follow_the_route(
        self, agents_file, proxy, repo, capsys
    ):
        assert self.ask("--repo", str(repo), "tool mcp__other__who_calls") == 0
        assert capsys.readouterr().out == "[permission: no]\n"
        assert self.ask("--repo", str(repo), "--no-knowledge", "tool mcp__hobbes__who_calls") == 0
        assert capsys.readouterr().out == "[permission: no]\n"
