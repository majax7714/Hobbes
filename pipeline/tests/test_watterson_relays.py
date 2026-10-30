"""In-process tests for the two stdlib relays (``hook_client``, ``lead_mcp``), the provider package's lazy
names and its errors.

The relays' socket tests in ``test_watterson_hooks.py`` and ``test_watterson_lead.py`` run them as scripts,
the way the harness does; these call their functions directly, so each behaviour is checked on its own and
the graph sees the tests reach the modules (a script run by path reaches nothing, C-179). A real Unix socket
stands in for the driver.
"""

from __future__ import annotations

import io
import json
import socket
import threading
import types

import pytest

from hobbes.watterson import hook_client, lead_mcp
from hobbes.watterson import providers
from hobbes.watterson.providers import errors


class Driver:
    """A Unix socket that answers each connection with the next canned reply and records what it was sent."""

    def __init__(self, path: str, replies: list[bytes]) -> None:
        self.path, self.replies, self.received = path, list(replies), []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        for reply in self.replies:
            conn, _ = self.sock.accept()
            with conn:
                self.received.append(b"".join(iter(lambda: conn.recv(65536), b"")))
                conn.sendall(reply)

    def close(self) -> None:
        self.thread.join(timeout=5)
        self.sock.close()


@pytest.fixture
def driver(tmp_path):
    made: list[Driver] = []

    def start(*replies: bytes) -> Driver:
        made.append(Driver(str(tmp_path / f"d{len(made)}.sock"), list(replies)))
        return made[-1]

    yield start
    for d in made:
        d.close()


def run_hook(monkeypatch, argv: list[str], stdin: bytes) -> int:
    monkeypatch.setattr(hook_client.sys, "stdin", types.SimpleNamespace(buffer=io.BytesIO(stdin)))
    return hook_client.main(argv)


class TestHookClient:
    def test_hands_stdin_to_the_socket_and_prints_the_whole_answer(self, monkeypatch, capsysbinary, driver):
        d = driver(b"x" * 70_000)
        assert run_hook(monkeypatch, ["hook_client.py", d.path], b'{"hook": "PreToolUse"}') == 0
        d.close()
        assert d.received == [b'{"hook": "PreToolUse"}']
        assert capsysbinary.readouterr().out == b"x" * 70_000

    def test_with_no_socket_named_or_none_listening_it_prints_nothing_and_exits_zero(self, monkeypatch, capsysbinary, tmp_path):
        assert run_hook(monkeypatch, ["hook_client.py"], b"{}") == 0
        assert run_hook(monkeypatch, ["hook_client.py", str(tmp_path / "absent.sock")], b"{}") == 0
        assert capsysbinary.readouterr().out == b""

    def test_waits_below_the_hook_timeout(self):
        assert hook_client.TIMEOUT == 8.0


def call(name: str, arguments: dict | None = None, ident: int = 7) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {"name": name, **({"arguments": arguments} if arguments is not None else {})}}


class TestLeadMcp:
    def test_each_server_lists_its_own_tools(self):
        names = lambda server: [t["name"] for t in lead_mcp.handle("", {"id": 1, "method": "tools/list"}, server)["result"]["tools"]]
        assert names("hobbes-lead") == ["propose_plan", "dispatch", "wait", "finish"]
        assert names("hobbes-worker") == ["report"]
        assert names("hobbes-mapper") == ["save_mapping"]
        assert lead_mcp.SERVER == "hobbes-lead"

    def test_initialize_echoes_the_client_protocol_or_offers_its_own_and_names_the_server(self):
        given = lead_mcp.handle("", {"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}, "hobbes-worker")
        assert given == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "hobbes-worker", "version": "0.1.0"}},
        }
        assert lead_mcp.handle("", {"id": 2, "method": "initialize"})["result"]["protocolVersion"] == "2025-06-18"

    def test_ping_answers_empty_a_notification_gets_no_answer_and_an_unknown_method_an_error(self):
        assert lead_mcp.handle("", {"id": 3, "method": "ping"}) == {"jsonrpc": "2.0", "id": 3, "result": {}}
        assert lead_mcp.handle("", {"method": "notifications/initialized"}) is None
        assert lead_mcp.handle("", {"id": 4, "method": "resources/list"}) == {
            "jsonrpc": "2.0",
            "id": 4,
            "error": {"code": -32601, "message": "no method 'resources/list'"},
        }

    def test_a_tool_call_is_relayed_to_the_driver_and_its_reply_returned(self, driver):
        d = driver(json.dumps({"text": "approved", "error": False}).encode(), json.dumps({"text": "no", "error": True}).encode())
        ok = lead_mcp.handle(d.path, call("propose_plan", {"plan": "one unit"}))
        bad = lead_mcp.handle(d.path, call("wait"))
        d.close()
        assert ok == {"jsonrpc": "2.0", "id": 7, "result": {"content": [{"type": "text", "text": "approved"}], "isError": False}}
        assert bad["result"] == {"content": [{"type": "text", "text": "no"}], "isError": True}
        assert [json.loads(r) for r in d.received] == [
            {"tool": "propose_plan", "arguments": {"plan": "one unit"}},
            {"tool": "wait", "arguments": {}},
        ]

    def test_a_tool_the_server_does_not_serve_is_refused_before_any_relay(self, tmp_path):
        assert lead_mcp.handle(str(tmp_path / "none.sock"), call("dispatch", {}), "hobbes-worker") == {
            "jsonrpc": "2.0",
            "id": 7,
            "error": {"code": -32602, "message": "unknown tool 'dispatch'"},
        }

    def test_a_driver_that_cannot_be_reached_or_answers_badly_is_an_error_said_in_the_reply(self, driver, tmp_path):
        text, error = lead_mcp.relay(str(tmp_path / "none.sock"), "wait", {})
        assert error and text.startswith("the hobbes job driver is not reachable: ")
        d = driver(b"not json", b"")
        text, error = lead_mcp.relay(d.path, "wait", {})
        assert error and text.startswith("the hobbes job driver is not reachable: ")
        assert lead_mcp.relay(d.path, "wait", {}) == ("", False)

    def test_main_answers_one_line_per_request_and_skips_blanks_notifications_and_non_objects(self, monkeypatch, capsys):
        lines = [
            json.dumps({"id": 1, "method": "ping"}),
            "",
            "{not json",
            json.dumps([1, 2]),
            json.dumps({"method": "notifications/initialized"}),
            json.dumps({"id": 2, "method": "tools/list"}),
        ]
        monkeypatch.setattr(lead_mcp.sys, "stdin", io.StringIO("\n".join(lines) + "\n"))
        assert lead_mcp.main(["lead_mcp.py", "", "hobbes-mapper"]) == 0
        out = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert out[0] == {"jsonrpc": "2.0", "id": 1, "result": {}}
        assert out[1] == {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        assert [t["name"] for t in out[2]["result"]["tools"]] == ["save_mapping"]
        assert len(out) == 3

    def test_main_serves_the_lead_tools_when_no_or_an_unknown_server_is_named(self, monkeypatch, capsys):
        for argv in (["lead_mcp.py"], ["lead_mcp.py", "", "hobbes-nobody"]):
            monkeypatch.setattr(lead_mcp.sys, "stdin", io.StringIO(json.dumps({"id": 1, "method": "tools/list"}) + "\n"))
            lead_mcp.main(argv)
            assert [t["name"] for t in json.loads(capsys.readouterr().out)["result"]["tools"]] == ["propose_plan", "dispatch", "wait", "finish"]


class TestProviderPackage:
    def test_every_exported_name_loads_from_its_module_on_first_use_and_stays(self):
        assert providers.__all__ == sorted(providers._EXPORTS)
        for name, module in providers._EXPORTS.items():
            loaded = providers.__getattr__(name)
            assert loaded is getattr(__import__(f"hobbes.watterson.providers.{module}", fromlist=[name]), name)
            assert vars(providers)[name] is loaded

    def test_an_unknown_name_is_an_attribute_error_naming_the_package(self):
        with pytest.raises(AttributeError, match=r"^module 'hobbes\.watterson\.providers' has no attribute 'nope'$"):
            providers.__getattr__("nope")


class TestProviderErrors:
    def test_every_error_is_a_provider_error_and_a_missing_key_a_completion_error(self):
        for cls in (errors.UnknownAgentError, errors.AgentError, errors.CompletionError, errors.MissingKeyError):
            assert issubclass(cls, errors.ProviderError)
        assert issubclass(errors.MissingKeyError, errors.CompletionError)

    def test_an_agent_error_appends_the_agent_stderr_tail_when_there_is_one(self):
        plain = errors.AgentError("agent exited")
        assert (str(plain), plain.stderr_tail) == ("agent exited", "")
        tail = errors.AgentError("agent exited", stderr_tail="boom\nbye")
        assert str(tail) == "agent exited\n--- agent stderr (last lines) ---\nboom\nbye"
        assert tail.stderr_tail == "boom\nbye"

    def test_a_missing_key_names_the_provider_and_the_variable_to_set(self):
        error = errors.MissingKeyError("anthropic", "ANTHROPIC_API_KEY")
        assert (error.provider, error.env_var) == ("anthropic", "ANTHROPIC_API_KEY")
        assert str(error) == "no API key for anthropic: set ANTHROPIC_API_KEY in the environment"
