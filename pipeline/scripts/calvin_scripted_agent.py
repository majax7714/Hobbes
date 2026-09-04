#!/usr/bin/env python3
"""A scripted stand-in for the orchestrator in an arm-O session (Calvin M0 step 5's exit check).

`hobbes-session --runtime FILE` copies this file into the session dir and
runs it inside the sandbox with the loop's argv. It calls no model: it
reads a JSON script (``--script``, a path visible in the container —
the session dir is mounted at ``/sessions``) and plays it through the
session's MCP proxy exactly as the owned loop would — ``exec`` calls
policy-checked by the proxy, edits made in ``/work`` — then writes the
transcript and prints the loop's result envelope. What it proves is the
harness (X): Podman, the policy chain, the environment binding, the
harvest, the grounder and the verifier behind them — with no
orchestrator spend and a deterministic trajectory.

Script shape, one step per row::

    [{"exec": "cd pipeline && python3 -m pytest -q tests/test_policy.py"},
     {"edit": ["go/internal/policy/resolve.go", "old text", "new text"]},
     {"write": ["docs/note.md", "content"]}]

Stdlib only, like the loop it stands in for.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time


class MCPClient:
    """The session's one MCP server (the hobbes-proxy from ``mcp.json``), spoken over stdio."""

    def __init__(self, config_path: str):
        cfg = json.load(open(config_path))["mcpServers"]
        _, server = next(iter(cfg.items()))
        self.proc = subprocess.Popen([server["command"], *server.get("args", [])], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True)
        self.n = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "calvin-scripted-agent", "version": "0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg: dict) -> None:
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _rpc(self, method: str, params: dict) -> dict:
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed the connection")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"MCP {method}: {msg['error']}")
                return msg.get("result", {})

    def tools(self) -> list[str]:
        return [t["name"] for t in self._rpc("tools/list", {}).get("tools", [])]

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        r = self._rpc("tools/call", {"name": name, "arguments": args})
        return "".join(c.get("text", "") for c in r.get("content", []) if isinstance(c, dict)), bool(r.get("isError"))

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=15)
        except Exception:  # noqa: BLE001
            self.proc.kill()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--mcp-config", required=True)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--transcript")
    ap.add_argument("--script", required=True)
    a, _ = ap.parse_known_args(argv)
    t0 = time.monotonic()
    steps = json.load(open(a.script))
    mcp = MCPClient(a.mcp_config)
    tools = mcp.tools()
    exec_tool = next((t for t in tools if t == "exec" or t.endswith("__exec")), None)
    messages = [{"role": "system", "content": "scripted stand-in; no model"},
                {"role": "user", "content": open(a.prompt_file).read() if a.prompt_file else ""}]
    turns = 0
    for step in steps:
        turns += 1
        if "exec" in step:
            if exec_tool is None:
                text, err = "exec is not served in this session", True
            else:
                text, err = mcp.call(exec_tool, {"command": step["exec"]})
            call = {"id": f"c{turns}", "type": "function", "function": {"name": "exec", "arguments": json.dumps({"command": step["exec"]})}}
        elif "edit" in step:
            path, old, new = step["edit"]
            full = os.path.join(a.workdir, path)
            src = open(full).read()
            err = old not in src
            text = "edited" if not err else f"old text not found in {path}"
            if not err:
                open(full, "w").write(src.replace(old, new, 1))
            call = {"id": f"c{turns}", "type": "function", "function": {"name": "edit_file", "arguments": json.dumps({"path": path, "old_text": old, "new_text": new})}}
        else:
            path, content = step["write"]
            full = os.path.join(a.workdir, path)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            open(full, "w").write(content)
            text, err = "written", False
            call = {"id": f"c{turns}", "type": "function", "function": {"name": "write_file", "arguments": json.dumps({"path": path, "content": content})}}
        messages.append({"role": "assistant", "content": "", "tool_calls": [call]})
        messages.append({"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": ("ERROR: " if err else "") + text})
        print(f"[turn {turns}] {call['function']['name']} → {'error' if err else 'ok'}: {text[:200]!r}", file=sys.stderr, flush=True)
    summary = f"scripted: {turns} steps against tools {tools}"
    messages.append({"role": "assistant", "content": summary})
    mcp.close()
    if a.transcript:
        with open(a.transcript, "w") as fh:
            for m in messages:
                fh.write(json.dumps(m) + "\n")
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": turns, "duration_ms": int((time.monotonic() - t0) * 1000),
                      "usage": {"input_tokens": 0, "output_tokens": 0}, "result": summary, "tools": tools}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
