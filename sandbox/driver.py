"""Scripted implementer for the M4 exit check (ADR-018).

Runs INSIDE the sandbox in Claude Code's place: it reads the same MCP config
the wrapper generated, spawns the hobbes proxy over stdio, and drives a small
task plus the refusal and escalation paths — proving the sandbox mechanics
without spending subscription quota. Prints a PASS/FAIL line per M4 exit
criterion.

Usage: python3 driver.py <session-id>
"""
import json
import os
import subprocess
import sys

SESSION = sys.argv[1]
MCP_CONFIG = f"/sessions/{SESSION}/mcp.json"
WORK = "/work"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}", flush=True)


class Proxy:
    """A minimal MCP stdio client, spawning the proxy from the wrapper's config."""

    def __init__(self, config_path):
        cfg = json.load(open(config_path))["mcpServers"]["hobbes"]
        self.proc = subprocess.Popen(
            [cfg["command"], *cfg["args"]],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True)
        self.n = 0
        self._rpc({"method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "exit-check-driver", "version": "0"}}})
        self._notify({"method": "notifications/initialized"})

    def _send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def _notify(self, msg):
        self._send({"jsonrpc": "2.0", **msg})

    def _rpc(self, msg):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, **msg})
        return json.loads(self.proc.stdout.readline())

    def call(self, tool, **args):
        """Call a tool; returns (text, is_error). Blocks if the proxy parks."""
        r = self._rpc({"method": "tools/call",
                       "params": {"name": tool, "arguments": args}})["result"]
        text = "".join(c.get("text", "") for c in r.get("content", []))
        return text, r.get("isError", False)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=15)


# Criterion 4: no secrets in the session environment. The host injected
# AWS_SECRET_ACCESS_KEY and GITHUB_TOKEN; the sandbox must not carry them.
leaked = [k for k in ("AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "ANTHROPIC_API_KEY")
          if k in os.environ]
check("no-secrets-in-env", not leaked,
      f"env has {sorted(os.environ)}" if not leaked else f"LEAKED {leaked}")

proxy = Proxy(MCP_CONFIG)

# Criterion 1a: orient via a knowledge tool (read-only, logged).
text, err = proxy.call("tests_guarding", target="hobbes.policy")
check("knowledge-query", not err and "ingest @" in text,
      text.splitlines()[0] if text else "no answer")

# Criterion 1b: complete the task — write a file into the worktree. File
# writes in /work are the agent's own (Edit/Write), not policy-gated; only
# the shell goes through exec.
note = os.path.join(WORK, "SESSION_NOTES.md")
with open(note, "w") as fh:
    fh.write(f"# Session {SESSION}\n\nImplementer reviewed the policy engine "
             "via the hobbes knowledge tools.\n")
committed_task = os.path.exists(note)
# And confirm the change is visible through an allowed exec.
status, status_err = proxy.call("exec", command="git status --short")
check("task-completed", committed_task and not status_err and "SESSION_NOTES.md" in status,
      f"wrote SESSION_NOTES.md; git status sees it: {'SESSION_NOTES.md' in status}")

# Criterion 2: a prohibited command is refused and logged (tfstate floor).
text, err = proxy.call("exec", command="cat prod.tfstate")
check("prohibited-refused", err and "denied" in text and "tfstate" in text,
      text.splitlines()[0] if text else "no answer")

# Criterion 3: an escalated command parks, is approved from the host CLI, and
# runs. `id` matches no rule, so the repo default (escalate) parks it; this
# call blocks until the orchestrator approves.
print("[....] escalation-approved: parking `id`, awaiting host approval...", flush=True)
text, err = proxy.call("exec", command="id")
check("escalation-approved", not err and "approved by" in text and "uid=" in text,
      text.splitlines()[0] if text else "no answer")

proxy.close()

passed = sum(1 for _, ok, _ in results if ok)
print(f"\nEXIT CHECK: {passed}/{len(results)} criteria passed", flush=True)
sys.exit(0 if passed == len(results) else 1)
