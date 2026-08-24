"""M4 exit-check orchestrator (ADR-018), run on the host.

Launches a real sandboxed session on the hobbes repo with the scripted
implementer, injecting fake secrets into the launching environment to prove
they never reach the session. While the implementer parks its escalated
command, this approves it from the real `hobbes-proxy escalations` CLI.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time

HOBBES = str(pathlib.Path(__file__).resolve().parents[1])
BIN = f"{HOBBES}/go/bin"
SESSIONS = os.path.expanduser("~/.hobbes/sessions")
SESSION = "S-exitcheck-m4"


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


# Clean any prior run of this fixed session id.
sh("git", "-C", HOBBES, "worktree", "remove", "--force",
   f"{SESSIONS}/{SESSION}/worktree")
sh("git", "-C", HOBBES, "branch", "-D", f"hobbes/{SESSION}")
shutil.rmtree(f"{SESSIONS}/{SESSION}", ignore_errors=True)

# The scripted implementer must be visible inside the sandbox: drop it in the
# sessions root, which the wrapper mounts at /sessions.
os.makedirs(SESSIONS, exist_ok=True)
shutil.copy(f"{HOBBES}/sandbox/driver.py", f"{SESSIONS}/driver.py")

# Fake secrets in the LAUNCHING environment. If the sandbox were leaky, these
# would show up in the implementer's os.environ.
env = dict(os.environ)
env["AWS_SECRET_ACCESS_KEY"] = "AKIA_SHOULD_NEVER_LEAK"
env["GITHUB_TOKEN"] = "ghp_should_never_leak"

launch = [
    f"{BIN}/hobbes-session", "start",
    "--repo", HOBBES,
    "--role", "implementer",
    "--session", SESSION,
    "--proxy-bin", f"{HOBBES}/sandbox/hobbes-proxy",
    "--", "python3", "/sessions/driver.py", SESSION,
]

print(f"launching sandboxed session {SESSION} (with fake secrets in env)...\n")
proc = subprocess.Popen(launch, env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True)

out_lines = []


def pump():
    for line in proc.stdout:
        out_lines.append(line)
        sys.stdout.write("  [session] " + line)
        sys.stdout.flush()


t = threading.Thread(target=pump, daemon=True)
t.start()


def approve_when_parked():
    """Poll the real CLI; approve the implementer's parked command."""
    for _ in range(300):
        r = sh(f"{BIN}/hobbes-proxy", "escalations", "list", "--log-dir", SESSIONS)
        for line in r.stdout.splitlines():
            m = re.match(r"(E-\S+)\s+pending", line)
            if m and SESSION in line:
                eid = m.group(1)
                time.sleep(0.3)
                a = sh(f"{BIN}/hobbes-proxy", "escalations", "approve", eid,
                       "--log-dir", SESSIONS)
                print(f"\n  [host CLI] {a.stdout.strip()}\n")
                return True
        if proc.poll() is not None:
            return False
        time.sleep(0.4)
    return False


approve_when_parked()
proc.wait(timeout=180)
t.join(timeout=5)

print("\n" + "=" * 60)
print("flight log:", f"{SESSIONS}/{SESSION}/flight.jsonl")
sh("sync")
with open(f"{SESSIONS}/{SESSION}/flight.jsonl") as fh:
    import json
    for line in fh:
        e = json.loads(line)
        esc = e.get("escalation", {})
        tag = ""
        if esc:
            tag = f"  esc={esc.get('resolution') or 'parked'}"
            if esc.get("approver"):
                tag += f" by {esc['approver']}"
        print(f"  {e['tool']:<18} {e['decision']:<9} exit={e['exit']}{tag}  :: "
              f"{' '.join(e['argv'])}")

sys.exit(proc.returncode)
