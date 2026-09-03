"""The owned agent runtime — hobbes/agent/loop.py (ADR-056).

Hermetic: a scripted OpenAI-compatible server on a loopback port plays
the model (it returns tool calls in a fixed order, then a final
answer), and a stdio JSON-RPC script plays the hobbes-proxy for the
MCP path. What is tested is the loop's contract — tool routing, file
confinement, bash withheld under MCP, read-only roles, the result
envelope the benchmark meters — never a model's judgement.
"""

import json
import os
import stat
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from hobbes.agent import loop
from hobbes.bench import accounting, arms, instances, workspace

LOOP = Path(loop.__file__)


class ScriptedModel:
    """An OpenAI-compatible /chat/completions that answers from a
    script: each entry is either a list of tool calls or a final text.
    Records every request body so tests can assert what the loop sent."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.server = HTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/v1"

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"body": body, "auth": self.headers.get("Authorization")})
                if not outer.script:
                    step = "nothing left in the script"
                else:
                    step = outer.script.pop(0)
                if isinstance(step, int):  # an HTTP error status
                    self.send_response(step)
                    self.end_headers()
                    self.wfile.write(b'{"error":"scripted"}')
                    return
                if isinstance(step, tuple) and step[0] == "http":  # ("http", status, body)
                    self.send_response(step[1])
                    self.end_headers()
                    self.wfile.write(step[2].encode())
                    return
                finish = "stop"
                reasoning_n = 0
                if isinstance(step, tuple) and step[0] == "cut":  # ("cut", text): cut at max_tokens
                    message, finish = {"role": "assistant", "content": step[1]}, "length"
                elif isinstance(step, tuple) and step[0] == "think":  # ("think", reasoning, text|calls)
                    body_step = step[2]
                    if isinstance(body_step, str):
                        message = {"role": "assistant", "content": body_step, "reasoning_content": step[1]}
                    else:
                        message = {"role": "assistant", "content": None, "reasoning_content": step[1],
                                   "tool_calls": [{"id": f"call_{i}", "type": "function",
                                                   "function": {"name": name, "arguments": json.dumps(args)}}
                                                  for i, (name, args) in enumerate(body_step)]}
                    reasoning_n = 7
                elif isinstance(step, str):
                    message = {"role": "assistant", "content": step}
                else:
                    message = {"role": "assistant", "content": None, "tool_calls": [
                        {"id": f"call_{i}", "type": "function",
                         "function": {"name": name, "arguments": json.dumps(args)}}
                        for i, (name, args) in enumerate(step)]}
                usage = {"prompt_tokens": 100, "completion_tokens": 10}
                if reasoning_n:
                    usage["completion_tokens_details"] = {"reasoning_tokens": reasoning_n}
                reply = {"choices": [{"message": message, "finish_reason": finish}], "usage": usage}
                data = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return Handler

    def close(self):
        self.server.shutdown()


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "tree"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("def f():\n    return 1\n")
    (root / "README").write_text("hi\n")
    return root


def run_loop(model, tree, *extra, prompt="do it"):
    argv = ["--base-url", model.base_url, "--model", "m", "--prompt", prompt, "--workdir", str(tree), *extra]
    return loop.run(loop.parse(argv))


class TestNativeLoop:
    def test_no_bash_withholds_the_tool_and_refuses_a_call(self, tree, monkeypatch):
        monkeypatch.setenv("HOBBES_LLM_API_KEY", "k-1")
        model = ScriptedModel([
            [("bash", {"command": "echo hi"})],
            [("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 3"})],
            "done",
        ])
        try:
            env = run_loop(model, tree, "--no-bash")
        finally:
            model.close()
        assert env["is_error"] is False and env["result"] == "done"
        offered = {t["function"]["name"] for t in model.requests[0]["body"]["tools"]}
        assert "bash" not in offered and "edit_file" in offered
        tool_msgs = [m for m in model.requests[1]["body"]["messages"] if m.get("role") == "tool"]
        assert "bash is not available" in tool_msgs[-1]["content"]
        assert (tree / "src" / "a.py").read_text() == "def f():\n    return 3\n"

    def test_reads_edits_runs_bash_and_reports(self, tree, monkeypatch):
        monkeypatch.setenv("HOBBES_LLM_API_KEY", "k-1")
        model = ScriptedModel([
            [("list_files", {}), ("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],
            [("bash", {"command": "python3 -c 'import sys; sys.path.insert(0,\"src\"); import a; print(a.f())'"})],
            "changed f to return 2",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["is_error"] is False and env["result"] == "changed f to return 2"
        assert env["num_turns"] == 4 and env["tool_calls"] == 4
        assert env["usage"] == {"input_tokens": 400, "output_tokens": 40, "reasoning_tokens": 0}
        assert (tree / "src" / "a.py").read_text() == "def f():\n    return 2\n"
        # the bearer token went out; tool results went back in order
        assert model.requests[0]["auth"] == "Bearer k-1"
        names = [t["function"]["name"] for t in model.requests[0]["body"]["tools"]]
        assert {"read_file", "list_files", "write_file", "edit_file", "bash"} <= set(names)
        last = model.requests[-1]["body"]["messages"]
        tool_msgs = [m for m in last if m["role"] == "tool"]
        assert "src/a.py" in tool_msgs[0]["content"] and "return 1" in tool_msgs[1]["content"]
        assert tool_msgs[-1]["content"].rstrip().endswith("[exit 0]") and "2" in tool_msgs[-1]["content"]
        # the meter reads the envelope like Claude Code's
        usage = accounting.from_envelope(env)
        assert usage.total_tokens == 440 and usage.turns == 4

    def test_file_tools_are_confined_and_edits_must_be_unique(self, tree):
        (tree / "src" / "dup.py").write_text("x = 1\nx = 1\n")
        model = ScriptedModel([
            [("read_file", {"path": "src/dup.py"})],   # ADR-067: an edit needs a read first
            [("read_file", {"path": "../outside"}), ("write_file", {"path": "/etc/passwd", "content": "no"}),
             ("edit_file", {"path": "src/dup.py", "old_text": "x = 1", "new_text": "x = 2"})],
            "gave up",
        ])
        try:
            run_loop(model, tree)
        finally:
            model.close()
        tool_msgs = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"][1:]
        assert all(m["content"].startswith("ERROR:") for m in tool_msgs)
        assert "outside the working tree" in tool_msgs[0]["content"]
        assert "occurs 2 times" in tool_msgs[2]["content"]
        assert (tree / "src" / "dup.py").read_text() == "x = 1\nx = 1\n"

    def test_a_repeated_identical_edit_is_refused(self, tree):
        # ADR-066: django-11400's U4 stacked one broken block 4x because
        # edit_file's new_text re-includes its anchor, so the same edit
        # applies again instead of being a no-op. The second identical
        # edit is refused; a different edit is still allowed.
        (tree / "src" / "a.py").write_text("def f():\n    return 1\n")
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],   # ADR-067: an edit needs a read first
            [("edit_file", {"path": "src/a.py", "old_text": "def f():", "new_text": "def f():\n    x = 1"})],
            [("edit_file", {"path": "src/a.py", "old_text": "def f():", "new_text": "def f():\n    x = 1"})],  # identical → refused
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],  # different → ok
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        msgs = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"][1:]
        assert not msgs[0]["content"].startswith("ERROR:")            # first edit applied
        assert msgs[1]["content"].startswith("ERROR:") and "already made this exact edit" in msgs[1]["content"]
        assert not msgs[2]["content"].startswith("ERROR:")            # a different edit is allowed
        assert env["edited"] is True and env["repeats_refused"] == 1
        # the anchor was inserted once, not stacked
        assert (tree / "src" / "a.py").read_text().count("x = 1") == 1

    def test_write_file_must_read_an_existing_file_first(self, tree):
        # ADR-064: overwriting an existing file the session never read is
        # refused; a new file is fine; a write after a read is fine.
        (tree / "src" / "a.py").write_text("def f():\n    return 1\n")
        model = ScriptedModel([
            [("write_file", {"path": "src/a.py", "content": "stub"})],          # refused: unread existing
            [("write_file", {"path": "src/new.py", "content": "brand new"})],   # ok: new file
            [("read_file", {"path": "src/a.py"})],
            [("write_file", {"path": "src/a.py", "content": "def f():\n    return 2\n"})],  # ok: read first
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        msgs = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert msgs[0]["content"].startswith("ERROR:") and "has not read it" in msgs[0]["content"]
        assert not msgs[1]["content"].startswith("ERROR:")          # new file allowed
        assert (tree / "src" / "new.py").read_text() == "brand new"
        assert (tree / "src" / "a.py").read_text() == "def f():\n    return 2\n"  # the read-then-write landed
        assert env["edited"] is True

    def test_transcript_is_written_when_asked(self, tree, tmp_path):
        out = tmp_path / "t.jsonl"
        model = ScriptedModel([[("read_file", {"path": "src/a.py"})], "done"])
        try:
            run_loop(model, tree, "--transcript", str(out))
        finally:
            model.close()
        lines = [json.loads(l) for l in out.read_text().splitlines()]
        roles = [m["role"] for m in lines]
        assert roles[0] == "system" and roles[1] == "user"
        assert any(m["role"] == "assistant" and m.get("tool_calls") for m in lines)
        assert any(m["role"] == "tool" for m in lines)

    def test_read_only_role_gets_no_write_tools(self, tree):
        model = ScriptedModel([[("write_file", {"path": "x", "content": "y"})], "done"])
        try:
            run_loop(model, tree, "--role", "verifier")
        finally:
            model.close()
        names = [t["function"]["name"] for t in model.requests[0]["body"]["tools"]]
        assert "write_file" not in names and "edit_file" not in names
        tool_msgs = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert "not available to this role" in tool_msgs[0]["content"]
        assert not (tree / "x").exists()

    def test_turn_budget_and_server_errors_land_in_the_envelope(self, tree):
        model = ScriptedModel([[("list_files", {})]] * 5)
        try:
            env = run_loop(model, tree, "--max-turns", "2")
        finally:
            model.close()
        assert env["is_error"] and "turn budget (2)" in env["result"] and env["num_turns"] == 2
        model = ScriptedModel([400])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["is_error"] and "HTTP 400" in env["result"]

    def test_runs_as_a_script_and_prints_one_envelope_line(self, tree):
        model = ScriptedModel(["hello"])
        try:
            proc = subprocess.run([sys.executable, str(LOOP), "--base-url", model.base_url, "--model", "m",
                                   "--prompt", "hi", "--workdir", str(tree), "--max-nudges", "0"],
                                  capture_output=True, text=True)
        finally:
            model.close()
        assert proc.returncode == 0, proc.stderr
        env = accounting.find_envelope(proc.stdout)
        assert env and env["result"] == "hello" and env["runtime"] == "hobbes-agent-loop"

    def test_text_embedded_tool_calls_are_executed_and_counted(self, tree):
        """A small model that writes the call as a fenced JSON block (seen
        live on Qwen2.5-Coder-7B, ADR-057) still gets its tool run."""
        model = ScriptedModel([
            'I will read it:\n```json\n{"name": "read_file", "arguments": {"path": "README"}}\n```',
            '<tool_call>\n{"name": "edit_file", "arguments": {"path": "README", "old_text": "hi", "new_text": "yo"}}\n</tool_call>',
            "```json\n{\"not\": \"a call\"}\n```\ndone",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["tool_calls"] == 2 and env["text_tool_calls"] == 2 and env["num_turns"] == 3
        assert (tree / "README").read_text() == "yo\n"
        assert env["result"].endswith("done")

    def test_stdlib_only(self):
        """The sandbox image has python3 and nothing else; the loop must
        import nothing outside the standard library."""
        import ast
        tree_ = ast.parse(LOOP.read_text())
        imported = set()
        for node in ast.walk(tree_):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)


#: A stdio JSON-RPC server that plays the hobbes-proxy: two tools, and a
#: log of every call so the test can see what reached it.
FAKE_MCP = """\
#!/usr/bin/env python3
import json, sys
log = open(sys.argv[1], "a")
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    m = msg["method"]
    if m == "initialize":
        r = {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "fake", "version": "0"}}
    elif m == "tools/list":
        r = {"tools": [
            {"name": "exec", "description": "run", "inputSchema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            {"name": "who_calls", "description": "callers", "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}}},
            {"name": "reflect", "description": "handoff", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "kind": {"type": "string"}}, "required": ["text"]}},
        ]}
    elif m == "tools/call":
        p = msg["params"]; log.write(json.dumps(p) + "\\n"); log.flush()
        if p["name"] == "exec" and "push" in p["arguments"].get("command", ""):
            r = {"content": [{"type": "text", "text": "denied: pushes are the human's"}], "isError": True}
        else:
            r = {"content": [{"type": "text", "text": f"{p['name']} ok: {p['arguments']}"}]}
    else:
        r = {}
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": r}) + "\\n"); sys.stdout.flush()
"""


@pytest.fixture
def mcp_config(tmp_path):
    server = tmp_path / "fake-mcp.py"
    server.write_text(FAKE_MCP)
    server.chmod(server.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "mcp.log"
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"hobbes": {"command": sys.executable, "args": [str(server), str(log)]}}}))
    return cfg, log


class TestMCPLoop:
    def test_mcp_tools_are_listed_routed_and_bash_is_withheld(self, tree, mcp_config):
        cfg, log = mcp_config
        model = ScriptedModel([
            [("who_calls", {"target": "app.core"}), ("exec", {"command": "git status"})],
            [("bash", {"command": "id"}), ("exec", {"command": "git push"})],
            [("read_file", {"path": "README"})],
            "done",
        ])
        try:
            env = run_loop(model, tree, "--mcp-config", str(cfg))
        finally:
            model.close()
        assert env["is_error"] is False
        names = [t["function"]["name"] for t in model.requests[0]["body"]["tools"]]
        assert "exec" in names and "who_calls" in names and "bash" not in names
        calls = [json.loads(l) for l in log.read_text().splitlines()]
        assert [c["name"] for c in calls] == ["who_calls", "exec", "exec"]  # bash never reached the server
        tool_msgs = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert "not available in this session; use the exec tool" in tool_msgs[2]["content"]
        assert tool_msgs[3]["content"].startswith("ERROR: denied")
        assert "hi" in tool_msgs[4]["content"]  # native read still works beside MCP


class TestReadOnlyRoleDiscipline:
    """Harness restructure, phase 1: a read-only role's deliverable is a
    reflect handoff — the discipline nudges toward it and never toward
    an edit, and a handoff counts as acting."""

    def test_planner_gets_no_write_tools_and_is_nudged_toward_reflect(self, tree, mcp_config):
        cfg, log = mcp_config
        model = ScriptedModel([
            "Plan: change src/a.py f() to return 2; run tests/test_a.py.",   # prose, no handoff
            [("reflect", {"text": "files: src/a.py; approach: return 2", "kind": "handoff"})],
            "done",
        ])
        try:
            env = run_loop(model, tree, "--mcp-config", str(cfg), "--role", "planner")
        finally:
            model.close()
        names = [t["function"]["name"] for t in model.requests[0]["body"]["tools"]]
        assert "reflect" in names and "write_file" not in names and "edit_file" not in names
        assert env["nudges"] == 1 and env["reflected"] is True and env["edited"] is False
        assert not env["is_error"] and env["role"] == "planner"
        nudge = [m for m in model.requests[1]["body"]["messages"] if m["role"] == "user"][-1]["content"]
        assert "reflect" in nudge and "write_file" not in nudge

    def test_a_progress_reflection_is_not_the_handoff(self, tree, mcp_config):
        cfg, _ = mcp_config
        model = ScriptedModel([
            [("reflect", {"text": "looking", "kind": "progress"})],
            [("read_file", {"path": "README"})],
            [("read_file", {"path": "src/a.py"})],
            [("who_calls", {"target": "x"})],
            [("who_calls", {"target": "y"})],
            [("who_calls", {"target": "z"})],
        ])
        try:
            env = run_loop(model, tree, "--mcp-config", str(cfg), "--role", "verifier",
                           "--max-nudges", "0", "--stall-after", "4", "--max-turns", "20")
        finally:
            model.close()
        assert env["is_error"] and "without a handoff" in env["result"]
        assert env["reflected"] is False

    def test_implementer_discipline_is_unchanged_by_reflect(self, tree, mcp_config):
        cfg, _ = mcp_config
        model = ScriptedModel([
            [("reflect", {"text": "I would change f", "kind": "handoff"})],
            "all done",
        ])
        try:
            env = run_loop(model, tree, "--mcp-config", str(cfg), "--max-nudges", "1")
        finally:
            model.close()
        # an implementer that only reflects is still nudged toward editing
        assert env["nudges"] == 1 and env["edited"] is False

    def test_an_implementer_that_edits_and_ends_in_prose_is_nudged_to_hand_off_once(self, tree, mcp_config):
        # D8 (ADR-091): sphinx U1 ended with "let's reflect…" and never
        # called reflect; nothing reached the orchestrator.
        cfg, log = mcp_config
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],
            "Let's reflect: I changed f to return 2.",
            [("reflect", {"text": "changed f", "kind": "handoff"})],
            "done",
        ])
        try:
            env = run_loop(model, tree, "--mcp-config", str(cfg), "--max-nudges", "0")
        finally:
            model.close()
        assert not env["is_error"] and env["edited"] and env["reflected"] and env["handoff_nudged"]
        assert env["nudges"] == 1
        nudge = [m for m in model.requests[3]["body"]["messages"] if m["role"] == "user"][-1]["content"]
        assert "handoff" in nudge and "reflect" in nudge
        # the nudge is bounded: prose twice ends the session with handoff_nudged on the record
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 2", "new_text": "return 3"})],
            "done, I think", "still done",
        ])
        try:
            env = run_loop(model, tree, "--mcp-config", str(cfg), "--max-nudges", "0")
        finally:
            model.close()
        assert not env["is_error"] and env["reflected"] is False and env["handoff_nudged"] and env["nudges"] == 1
        # without a reflect tool on offer (the pure arm) there is nothing to nudge toward
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 3", "new_text": "return 4"})],
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["nudges"] == 0 and not env["handoff_nudged"]


class TestBenchRuntime:
    def test_runtime_validation_and_session_args(self):
        with pytest.raises(ValueError, match="base_url"):
            arms.Runtime(kind="openai")
        with pytest.raises(ValueError, match="one of"):
            arms.Runtime(kind="ollama")
        rt = arms.Runtime(kind="openai", base_url="http://x/v1")
        # the turn budget reaches the harness sessions too (the first
        # full-stage probe ran them at the loop's default 60 vs pure's 40)
        assert rt.session_args() == ["--runtime", str(arms.LOOP_PATH), "--llm-base-url", "http://x/v1",
                                     "--max-turns", "60", "--max-tokens", "1536", "--loop-arg=--temperature=0.0"]
        assert arms.Runtime().session_args() == []

    def test_pure_arm_on_the_owned_loop(self, tmp_path, monkeypatch):
        # a local upstream for the checkout
        base = tmp_path / "gh"
        repo = base / "acme" / "app"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "core.py").write_text("def handle():\n    return None\n")
        g = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*g[:3], "init", "-q"], check=True)
        subprocess.run([*g, "add", "."], check=True)
        subprocess.run([*g, "commit", "-qm", "b"], check=True)
        sha = subprocess.run([*g[:3], "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        monkeypatch.setenv(workspace.GIT_BASE_ENV, str(base) + "/")
        monkeypatch.setenv(workspace.CACHE_ENV, str(tmp_path / "cache"))
        inst = instances.parse_instance({"instance_id": "acme__app-1", "repo": "acme/app", "base_commit": sha,
                                         "problem_statement": "handle() should return 1"})
        ws = workspace.checkout(inst, tmp_path / "ws")
        model = ScriptedModel([
            [("read_file", {"path": "src/core.py"})],   # ADR-067: an edit needs a read first
            [("edit_file", {"path": "src/core.py", "old_text": "return None", "new_text": "return 1"})],
            "fixed",
        ])
        try:
            # ADR-074: a thinking rung's sampling rides the pure arm's argv too
            result = arms.run_pure_arm(inst, ws, "qwen", runtime=arms.Runtime(
                kind="openai", base_url=model.base_url, temperature=1.0, top_p=0.95,
                reasoning_effort="medium", thinking="on"))
        finally:
            model.close()
        assert result.outcome == "patch" and result.patch_files == ["src/core.py"], result.error
        body = model.requests[0]["body"]
        assert body["temperature"] == 1.0 and body["top_p"] == 0.95 and body["reasoning_effort"] == "medium"
        assert body["chat_template_kwargs"] == {"enable_thinking": True}
        assert result.usage.total_tokens == 330 and result.usage.turns == 3   # read, edit, final
        # ADR-068: the pure arm writes its transcript and per-call log too
        assert (ws / ".hobbes" / "transcript.jsonl").exists() and (ws / ".hobbes" / "calls.jsonl").exists()
        assert result.detail["runtime"] == "openai"
        assert inst.problem_statement in model.requests[0]["body"]["messages"][1]["content"]


class TestContextWindow:
    """ADR-058: the loop fits the model's window instead of dying on it."""

    OVERFLOW = ('{"error":{"message":"This model\'s maximum context length is 32768 tokens and your '
                'request has %d input tokens (4096 > 32768 - %d). None","type":"BadRequestError"}}')

    def test_length_refusal_retries_with_fitted_max_tokens(self, tree):
        model = ScriptedModel([("http", 400, self.OVERFLOW % (30000, 30000)), "done"])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert not env["is_error"] and env["context_fitted"] == 1 and env["context_elided"] == 0
        assert model.requests[0]["body"]["max_tokens"] == 4096
        assert model.requests[1]["body"]["max_tokens"] == 32768 - 30000 - 16

    def test_no_room_elides_the_oldest_tool_result_and_says_so(self, tree):
        (tree / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(200)))
        model = ScriptedModel([
            [("read_file", {"path": "big.py"})],
            [("read_file", {"path": "README"})],
            ("http", 400, self.OVERFLOW % (32700, 32700)),   # nothing left for a completion
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert not env["is_error"] and env["context_elided"] == 1
        tools = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert tools[0]["content"] == loop.ELIDED and "hi" in tools[1]["content"]

    def test_one_fit_per_elide_cycle_when_the_endpoint_reports_a_lower_bound(self, tree):
        # D1 (ADR-091): vLLM's "at least N input tokens" is window −
        # max_tokens + 1, not the prompt size, so a refit from it
        # overflows again with N shifted by the room it just gave up.
        # The second overflow in one cycle must elide, not refit — the
        # sklearn call that refitted 450 times.
        (tree / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(200)))
        model = ScriptedModel([
            [("read_file", {"path": "big.py"})],
            ("http", 400, self.OVERFLOW % (32768 - 4096 + 1, 32768 - 4096 + 1)),
            ("http", 400, self.OVERFLOW % (32768 - 4079 + 1, 32768 - 4079 + 1)),   # the refit, "at least" again
            "done",
        ])
        try:
            env = run_loop(model, tree, "--max-nudges", "0")
        finally:
            model.close()
        assert not env["is_error"]
        assert env["context_fitted"] == 1 and env["context_elided"] == 1
        assert len(model.requests) == 4
        assert model.requests[2]["body"]["max_tokens"] == 4096 - 17
        assert model.requests[3]["body"]["max_tokens"] == 4096   # after the elision, the full cap again
        tools = [m for m in model.requests[3]["body"]["messages"] if m["role"] == "tool"]
        assert tools[0]["content"] == loop.ELIDED

    def test_short_and_mutating_results_are_never_elided(self, tree):
        # D2 (ADR-091): a failed edit's 90-char error is the record of
        # what was tried; eliding it for a placeholder nearly as long
        # saves nothing and the model repeats the edit.
        msgs = [
            {"role": "tool", "name": "edit_file", "content": "ERROR: old_text occurs 0 times in src/a.py; it must occur exactly once"},
            {"role": "tool", "name": "read_file", "content": "hi"},
            {"role": "tool", "name": "read_file", "content": "y" * 400},
            {"role": "tool", "name": "write_file", "content": "z" * 400},
        ]
        elided = loop.elide_oldest_tool_result(msgs)
        assert elided is msgs[2] and msgs[2]["content"] == loop.ELIDED
        assert loop.elide_oldest_tool_result(msgs) is None
        assert msgs[0]["content"].startswith("ERROR") and msgs[1]["content"] == "hi" and msgs[3]["content"] == "z" * 400

    def test_an_elided_read_revokes_the_edit_ticket_until_reread(self, tree):
        # D3 (ADR-091): sklearn U1 read _array_api.py, the read was
        # elided, then write_file stubbed the whole file — the read
        # ticket had outlived the read. Now the elision revokes it.
        (tree / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(200)))
        model = ScriptedModel([
            [("read_file", {"path": "big.py"})],
            [("read_file", {"path": "README"})],
            ("http", 400, self.OVERFLOW % (32700, 32700)),   # elides the big.py read
            [("write_file", {"path": "big.py", "content": "stub\n"})],
            [("edit_file", {"path": "big.py", "old_text": "x1 = 1", "new_text": "x1 = 10"})],
            [("read_file", {"path": "big.py"})],
            [("edit_file", {"path": "big.py", "old_text": "x1 = 1", "new_text": "x1 = 10"})],
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert not env["is_error"] and env["context_elided"] == 1
        tools = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert "elided from the context window" in tools[2]["content"]
        assert "elided from the context window" in tools[3]["content"]
        assert tools[5]["content"] == "edited big.py"
        assert "x1 = 10" in (tree / "big.py").read_text() and "x199" in (tree / "big.py").read_text()

    def test_a_read_and_an_edit_in_one_turn_are_refused_until_the_next(self, tree):
        # D4 (ADR-091): sphinx U1 batched read_file + edit_file in one
        # turn; the anchor was authored before the read's result existed
        # and occurred nowhere in the file.
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"}),
             ("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert not env["is_error"] and env["edited"]
        tools = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert "landed this turn" in tools[1]["content"]
        assert tools[2]["content"] == "edited src/a.py"
        assert "return 2" in (tree / "src" / "a.py").read_text()
        # a second read of an already-ticketed path does not re-arm the guard
        model = ScriptedModel([
            [("read_file", {"path": "README"})],
            [("read_file", {"path": "README"}),
             ("edit_file", {"path": "README", "old_text": "hi", "new_text": "ho"})],
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["edited"] and (tree / "README").read_text() == "ho\n"

    def test_nothing_to_elide_is_the_error(self, tree):
        model = ScriptedModel([("http", 400, self.OVERFLOW % (32700, 32700))])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["is_error"] and "maximum context length" in env["result"]

    def test_tool_results_are_clipped_with_the_cut_stated(self, tree):
        (tree / "big.txt").write_text("x" * 50_000)
        model = ScriptedModel([[("read_file", {"path": "big.txt"})], "done"])
        try:
            env = run_loop(model, tree, "--max-result-chars", "1000")
        finally:
            model.close()
        content = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"][0]["content"]
        assert len(content) < 1200 and "truncated:" in content and "more characters" in content


class TestProsePlanNudge:
    """ADR-058, fifth finding: a small model that describes a fix without
    editing is nudged to act, bounded so it still terminates."""

    def test_prose_before_editing_is_nudged_then_edits(self, tree):
        model = ScriptedModel([
            "Here is how I would fix it: change f to return 2.",   # prose, no tools
            [("write_file", {"path": "src/b.py", "content": "def f():\n    return 2\n"})],
            "Done: f now returns 2.",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert not env["is_error"] and env["nudges"] == 1 and env["edited"] is True
        # the nudge is a user message the model saw before it acted
        second = model.requests[1]["body"]["messages"]
        assert any(m["role"] == "user" and "not changed any files" in m["content"] for m in second)
        assert (tree / "src" / "b.py").read_text() == "def f():\n    return 2\n"

    def test_nudge_is_bounded_and_a_non_editing_model_terminates(self, tree):
        model = ScriptedModel(["plan one", "plan two", "plan three", "plan four"])
        try:
            env = run_loop(model, tree, "--max-nudges", "2")
        finally:
            model.close()
        assert env["edited"] is False and env["nudges"] == 2
        # 1 real turn + 2 nudged retries = 3 completions, then it gives up
        assert len(model.requests) == 3

    def test_a_model_that_edits_immediately_is_not_nudged(self, tree):
        model = ScriptedModel([
            [("write_file", {"path": "src/b.py", "content": "x\n"})],
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        assert env["nudges"] == 0 and env["edited"] is True


class TestStrictPipeline:
    """ADR-058, sixth finding: the pipeline refuses repeated read-only
    calls and stops a non-editing stall instead of burning the budget."""

    def test_identical_readonly_call_is_refused_not_rerun(self, tree):
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            [("read_file", {"path": "src/a.py"})],   # exact repeat
            [("write_file", {"path": "src/b.py", "content": "def f():\n    return 2\n"})],
            "done",
        ])
        try:
            env = run_loop(model, tree, "--max-nudges", "0")
        finally:
            model.close()
        assert env["repeats_refused"] == 1 and env["edited"] is True and not env["is_error"]
        # the refusal reached the model as the tool result for the repeat
        msgs = model.requests[2]["body"]["messages"]
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        assert any("Stop repeating it" in m["content"] for m in tool_msgs)

    def test_refused_repeats_after_an_edit_still_stop(self, tree):
        # the full-stage probe's U6: one commit, then 57 of 60 turns on
        # refused repeats — "acted" held, so the dry-turn stall never fired
        model = ScriptedModel([
            [("write_file", {"path": "src/b.py", "content": "def f():\n    return 2\n"})],
            *([[("read_file", {"path": "src/a.py"})]] * 12),
            "done",
        ])
        try:
            env = run_loop(model, tree, "--max-nudges", "0", "--stall-after", "4", "--max-turns", "30")
        finally:
            model.close()
        assert env["edited"] is True and env["is_error"]
        assert "refused repeated calls" in env["result"] and env["repeats_refused"] == 4
        assert len(model.requests) <= 7  # 1 edit + 1 first read + 4 refused, then stopped

    def test_same_exec_without_an_edit_between_is_refused(self, tree):
        # U4 of the first full-stage probe: one failing pytest run 8x with
        # no edit between; a re-run after an edit stays legitimate
        model = ScriptedModel([
            [("bash", {"command": "echo hi"})],
            [("bash", {"command": "echo hi"})],   # nothing changed: refused
            [("write_file", {"path": "src/b.py", "content": "def f():\n    return 2\n"})],
            [("bash", {"command": "echo hi"})],   # after an edit: runs
            "done",
        ])
        try:
            env = run_loop(model, tree, "--max-nudges", "0")
        finally:
            model.close()
        assert env["repeats_refused"] == 1 and env["edited"] is True and not env["is_error"]
        tool_msgs = [m for m in model.requests[2]["body"]["messages"] if m["role"] == "tool"]
        assert any("nothing has been edited since" in m["content"] for m in tool_msgs)
        ran = [m for m in model.requests[4]["body"]["messages"] if m["role"] == "tool" and "hi" in m["content"] and "ERROR" not in m["content"]]
        assert len(ran) == 2

    def test_a_nonediting_loop_stops_with_a_reason(self, tree):
        # tests_guarding-style: a read-only call repeated forever, never editing
        model = ScriptedModel([[("read_file", {"path": "README"})]] * 12)
        try:
            env = run_loop(model, tree, "--max-nudges", "1", "--nudge-after", "2", "--stall-after", "5", "--max-turns", "20")
        finally:
            model.close()
        assert env["is_error"] and "no progress" in env["result"]
        assert env["edited"] is False
        # it stopped well before the turn budget, not at turn 20
        assert env["num_turns"] < 20

    def test_a_dry_run_of_reads_then_an_edit_is_fine(self, tree):
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            [("list_files", {"path": "src"})],
            [("write_file", {"path": "src/b.py", "content": "x\n"})],
            "done",
        ])
        try:
            env = run_loop(model, tree, "--max-nudges", "0", "--nudge-after", "2")
        finally:
            model.close()
        assert env["edited"] is True and not env["is_error"] and env["repeats_refused"] == 0


class TestReadBeforeEditAndCutCompletions:
    """ADR-067: the four gaps the 5-fresh re-run read surfaced."""

    def test_an_edit_of_an_unread_path_is_refused_and_a_read_unlocks_it(self, tree):
        # xarray-3993 U2: nine identical edit pairs against an anchor that
        # does not exist, never a read. The edit now costs a read first.
        model = ScriptedModel([
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],
            [("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "return 1", "new_text": "return 2"})],
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        tools = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert tools[0]["content"].startswith("ERROR:") and "has not read src/a.py" in tools[0]["content"]
        assert tools[2]["content"] == "edited src/a.py" and env["edited"] is True
        assert (tree / "src" / "a.py").read_text() == "def f():\n    return 2\n"

    def test_a_reworded_edit_at_an_applied_anchor_is_refused(self, tree):
        # django-11400 U4: three different wordings of one block at one
        # anchor, all applied, all stacked. ADR-066's byte-identity
        # refusal cannot see it; the anchor can.
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            [("edit_file", {"path": "src/a.py", "old_text": "def f():", "new_text": "def f():\n    x = 1"})],
            [("edit_file", {"path": "src/a.py", "old_text": "def f():", "new_text": "def f():\n    x = 2"})],  # same anchor, reworded
            [("edit_file", {"path": "src/a.py", "old_text": "def f():", "new_text": "def g():"})],  # anchor consumed → allowed
            "done",
        ])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        tools = [m for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"][1:]
        assert tools[0]["content"] == "edited src/a.py"
        assert tools[1]["content"].startswith("ERROR:") and "same anchor" in tools[1]["content"]
        assert tools[2]["content"] == "edited src/a.py"
        assert (tree / "src" / "a.py").read_text() == "def g():\n    x = 1\n    return 1\n"
        assert env["repeats_refused"] == 1

    def test_a_completion_cut_at_max_tokens_is_retried_once_with_more_room(self, tree):
        # sphinx-8548's planner: a fenced reflect cut mid-list three times,
        # each time nudged as prose. A cut completion is retried at 2x.
        model = ScriptedModel([
            ("cut", "```json\n{\"name\": \"read_file\", \"arguments\": {\"path\": \"sr"),
            [("read_file", {"path": "src/a.py"})],
            ("cut", "still too long"),       # cut again → stands as prose
            ("cut", "and again"),
            "done",
        ])
        try:
            env = run_loop(model, tree, "--max-tokens", "100")
        finally:
            model.close()
        bodies = [r["body"] for r in model.requests]
        assert bodies[0]["max_tokens"] == 100 and bodies[1]["max_tokens"] == 200   # the retry
        assert env["cut_retried"] >= 1 and not env["is_error"] or env["cut_retried"] >= 1
        # the cut prefix never reached the transcript as an assistant turn
        assert not any("\"path\": \"sr" in (m.get("content") or "") for m in bodies[-1]["messages"])

    def test_call_syntax_blocks_parse_like_olmo3_writes_them(self):
        block = ('I will read it first.\n<function_calls>\nread_file(path="src/a.py")\n'
                 'edit_file(path="src/a.py", old_text="return 1\\nx", new_text="return 2", count=3, force=true, extra={"k": [1, 2]})\n'
                 'broken(path=oops)\nlist_files()\n</function_calls>')
        calls = loop.text_tool_calls(block)
        assert [c["function"]["name"] for c in calls] == ["read_file", "edit_file", "list_files"]
        args = json.loads(calls[1]["function"]["arguments"])
        assert args == {"path": "src/a.py", "old_text": "return 1\nx", "new_text": "return 2", "count": 3,
                        "force": True, "extra": {"k": [1, 2]}}
        assert json.loads(calls[2]["function"]["arguments"]) == {}
        assert loop.text_tool_calls("<function_calls>\n</function_calls>") == []
        # Python quoting, which the base model falls into when it is not copying the template's JSON.
        py = "<function_calls>read_file(path='src/a.py')\nedit_file(path='src/a.py', old_text='a', new_text='b\\n', force=True)\nsearch_file(path='*.py' or 'x', pattern='y')</function_calls>"
        calls = loop.text_tool_calls(py)
        assert [c["function"]["name"] for c in calls] == ["read_file", "edit_file"]
        assert json.loads(calls[1]["function"]["arguments"]) == {"path": "src/a.py", "old_text": "a", "new_text": "b\n", "force": True}

    def test_tool_choice_none_sends_schemas_without_a_choice_and_reads_text_calls(self, tree, monkeypatch):
        monkeypatch.setenv("HOBBES_LLM_API_KEY", "k-1")
        model = ScriptedModel([
            'Reading.\n<function_calls>\nread_file(path="src/a.py")\n</function_calls>',
            '<function_calls>\nedit_file(path="src/a.py", old_text="return 1", new_text="return 4")\n</function_calls>',
            "done",
        ])
        try:
            env = run_loop(model, tree, "--tool-choice", "none", "--no-bash")
        finally:
            model.close()
        assert env["is_error"] is False and env["text_tool_calls"] == 2
        body = model.requests[0]["body"]
        assert "tools" not in body and "tool_choice" not in body
        system = body["messages"][0]["content"]
        assert "<functions>" in system and '"read_file"' in system and "<function_calls>" in system
        sent_back = [m for m in model.requests[1]["body"]["messages"] if m.get("role") == "assistant"][-1]
        assert sent_back["content"] == "Reading." and sent_back["tool_calls"][0]["function"]["name"] == "read_file"
        assert (tree / "src" / "a.py").read_text() == "def f():\n    return 4\n"

    def test_fenced_calls_with_any_tag_and_real_newlines_parse(self):
        fenced = ('```python\n{"name": "reflect", "arguments": {"kind": "handoff", "text": "files:\n- a.py\n- b.py"}}\n```')
        calls = loop.text_tool_calls(fenced)
        assert [c["function"]["name"] for c in calls] == ["reflect"]
        assert json.loads(calls[0]["function"]["arguments"])["text"] == "files:\n- a.py\n- b.py"
        unterminated = '```json\n{"name": "read_file", "arguments": {"path": "a.py"}}'
        assert [c["function"]["name"] for c in loop.text_tool_calls(unterminated)] == ["read_file"]
        assert loop.text_tool_calls("```sh\npytest\n```") == []


class TestPerCallLog:
    """ADR-068: every call logged as it went, so a saturated window that
    never errors is visible — not only the 400s the fit absorbed."""

    OVERFLOW = TestContextWindow.OVERFLOW

    def test_calls_jsonl_beside_the_transcript_and_the_envelope_summary(self, tree, tmp_path):
        model = ScriptedModel([
            [("read_file", {"path": "src/a.py"})],
            ("http", 400, self.OVERFLOW % (30000, 30000)),   # fitted, then the 200 that masks it
            "done",
        ])
        try:
            env = run_loop(model, tree, "--transcript", str(tmp_path / "t" / "transcript.jsonl"))
        finally:
            model.close()
        calls = [json.loads(l) for l in (tmp_path / "t" / "calls.jsonl").read_text().splitlines()]
        assert [c["turn"] for c in calls][:2] == [1, 2]    # later turns are the no-edit nudges
        assert calls[0]["fitted"] == 0 and calls[0]["max_tokens_sent"] == 4096 and calls[0]["prompt_tokens"] == 100
        assert calls[1]["fitted"] == 1 and calls[1]["max_tokens_sent"] == 32768 - 30000 - 16 and calls[1]["window"] == 32768
        assert all("finish_reason" in c and "wall_ms" in c and "completion_tokens" in c for c in calls)
        assert env["calls"] == len(calls) and env["calls_saturated"] == 1 and env["prompt_tokens_max"] == 100


class TestSearchFile:
    """ADR-070: a confined search, so a large file's clipped read is not
    the end of the road."""

    def test_search_finds_the_line_in_a_big_file_and_in_a_tree(self, tree):
        big = "\n".join(f"x = {i}" for i in range(20000)) + "\n    def integrate(self, coord, datetime_unit=None):\n"
        (tree / "src" / "big.py").write_text(big)
        model = ScriptedModel([
            [("search_file", {"path": "src/big.py", "pattern": r"def integrate\("})],
            [("search_file", {"path": "src", "pattern": "def f"})],
            [("search_file", {"path": "../outside", "pattern": "x"})],
            [("search_file", {"path": "src", "pattern": "("})],
            [("read_file", {"path": "src/big.py"})],
            "done",
        ])
        try:
            run_loop(model, tree)
        finally:
            model.close()
        tools = [m["content"] for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"]
        assert tools[0] == "src/big.py:20001:     def integrate(self, coord, datetime_unit=None):"
        assert tools[1] == "src/a.py:1: def f():"
        assert tools[2].startswith("ERROR:") and "outside the working tree" in tools[2]
        assert tools[3].startswith("ERROR:") and "regular expression" in tools[3]
        assert "NOT the whole file" in tools[4] and "search_file" in tools[4]

    def test_search_of_a_missing_path_is_an_error_not_an_empty_result(self, tree):
        model = ScriptedModel([[("search_file", {"path": "src/nope.py", "pattern": "x"})], "done"])
        try:
            run_loop(model, tree)
        finally:
            model.close()
        out = [m["content"] for m in model.requests[-1]["body"]["messages"] if m["role"] == "tool"][0]
        assert out.startswith("ERROR:") and "no such file or directory: src/nope.py" in out


def test_the_proxy_exec_is_the_shell_under_every_name():
    # ADR-071: the proxy's MCP tool is plain "exec"; the loop accepted only a prefixed form.
    assert loop.is_exec_tool("exec") and loop.is_exec_tool("mcp__hobbes__exec") and loop.is_exec_tool("bash")
    assert not loop.is_exec_tool("read_file") and not loop.is_exec_tool("execute_plan")


class TestThinkingRung:
    """ADR-074: a thinking model's reasoning and sampling."""

    def test_default_sampling_is_greedy_and_nothing_else(self, tree):
        model = ScriptedModel(["done"])
        try:
            env = run_loop(model, tree)
        finally:
            model.close()
        body = model.requests[0]["body"]
        assert body["temperature"] == 0
        assert "top_p" not in body and "reasoning_effort" not in body and "chat_template_kwargs" not in body
        assert env["sampling"] == {"temperature": 0.0}
        assert env["usage"]["reasoning_tokens"] == 0

    def test_sampling_flags_reach_the_request_and_the_envelope(self, tree):
        model = ScriptedModel(["done"])
        try:
            env = run_loop(model, tree, "--temperature", "1.0", "--top-p", "0.95",
                           "--reasoning-effort", "medium", "--thinking", "off")
        finally:
            model.close()
        body = model.requests[0]["body"]
        assert body["temperature"] == 1.0 and body["top_p"] == 0.95 and body["reasoning_effort"] == "medium"
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert env["sampling"]["reasoning_effort"] == "medium"

    def test_thinking_on_sends_the_switch_and_server_sends_none(self):
        assert loop.sampling_fields(thinking="on")["chat_template_kwargs"] == {"enable_thinking": True}
        assert "chat_template_kwargs" not in loop.sampling_fields(thinking="server")

    def test_reasoning_is_kept_on_the_transcript_and_counted(self, tree, tmp_path):
        out = tmp_path / "t" / "transcript.jsonl"
        model = ScriptedModel([
            ("think", "I should read the file first.", [("read_file", {"path": "src/a.py"})]),
            ("think", "That is enough.", "done"),
        ])
        try:
            env = run_loop(model, tree, "--transcript", str(out))
        finally:
            model.close()
        # the second request carries the first turn's reasoning back (preserve_thinking)
        sent = [m for m in model.requests[1]["body"]["messages"] if m["role"] == "assistant"]
        assert sent[0]["reasoning_content"] == "I should read the file first."
        assert sent[0]["tool_calls"][0]["function"]["name"] == "read_file"
        lines = [json.loads(l) for l in out.read_text().splitlines()]
        # the two scripted turns carry their reasoning; the nudged turns after them have none
        assert [m.get("reasoning_content") for m in lines if m["role"] == "assistant"][:2] == [
            "I should read the file first.", "That is enough."]
        assert env["usage"]["reasoning_tokens"] == 14 and env["usage"]["output_tokens"] == 10 * env["num_turns"]
        calls = [json.loads(l) for l in open(loop.calls_path(str(out)))]
        assert [c["reasoning_tokens"] for c in calls][:3] == [7, 7, 0]

    def test_reasoning_tokens_absent_or_malformed_count_zero(self):
        assert loop.reasoning_tokens({}) == 0
        assert loop.reasoning_tokens({"completion_tokens_details": {"reasoning_tokens": "x"}}) == 0
        assert loop.reasoning_tokens({"completion_tokens_details": {"reasoning_tokens": 3}}) == 3
