"""`hobbes dispatch` (ADR-107): the harness end to end with a stand-in for hobbes-session — a script that clones the repo at the
parent, commits the change a test names on ``hobbes/<session>``, fetches it back, and writes the flight and egress logs a real
session writes — so the brief, the argv, the harvest, the gate with a derived map, the per-session log and the refusals are all
exercised with no podman and no model. The route itself is tested live on the Go side (hobbes-session's egress test)."""
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from hobbes import cli
from hobbes.run import dispatch as dp

CORE = '''"""core"""


def derive(x):
    return x
'''
USE = '''from pkg.core import derive


def go():
    return derive(1)
'''

FAKE_SESSION = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
a = sys.argv[1:]
val = lambda f: a[a.index(f) + 1] if f in a else None
repo, ref, sid, sessions = val("--repo"), val("--ref"), val("--session"), val("--sessions")
sdir = pathlib.Path(sessions) / sid
sdir.mkdir(parents=True, exist_ok=True)
(sdir / "argv.json").write_text(json.dumps({"argv": a, "token": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")}))
# what Claude Code would leave in its HOME (the session dir) if the launcher did not remove it
(sdir / ".claude" / "projects" / "-work").mkdir(parents=True, exist_ok=True)
(sdir / ".claude" / "projects" / "-work" / "t.jsonl").write_text('{"type":"thinking","thinking":"..."}\n')
(sdir / ".claude.json").write_text("{}")
(sdir / ".cache" / "claude-cli-nodejs" / "-work").mkdir(parents=True, exist_ok=True)
(sdir / ".cache" / "claude-cli-nodejs" / "-work" / "mcp.log").write_text("mcp")
if "--dry-run" in a:
    print("PLAN: podman run --network hobbes-int-" + sid.lower())
    sys.exit(0)
change = json.loads(os.environ.get("FAKE_CHANGE", "{}"))
wt = sdir / "worktree"
git = lambda *x: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *x], check=True, capture_output=True)
git("clone", "-q", "--local", "--no-hardlinks", repo, str(wt))
git("-C", str(wt), "checkout", "-q", "-b", "hobbes/" + sid, ref)
for rel, text in change.items():
    p = wt / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
if change:
    git("-C", str(wt), "add", "-A")
    git("-C", str(wt), "commit", "-qm", "doer")
    git("-C", repo, "fetch", "-q", str(wt), "hobbes/%s:hobbes/%s" % (sid, sid))
flight = [{"session": sid, "tool": "exec", "argv": ["python", "-m", "pytest"], "decision": "allow"},
          {"session": sid, "tool": "exec", "argv": ["pip", "download", "x"], "decision": "deny"}]
(sdir / "flight.jsonl").write_text("".join(json.dumps(e) + "\n" for e in flight))
eg = [{"event": "listen", "addr": "0.0.0.0:3128", "allow": ["api.anthropic.com:443"]},
      {"event": "connect", "method": "CONNECT", "target": "api.anthropic.com:443"},
      {"event": "close", "method": "CONNECT", "target": "api.anthropic.com:443", "bytes_up": 10, "bytes_down": 20},
      {"event": "refuse", "method": "CONNECT", "target": "pypi.org:443", "reason": "not on the session's egress allowlist"}]
(sdir / "egress.jsonl").write_text("".join(json.dumps(e) + "\n" for e in eg))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 7, "total_cost_usd": 0.42,
                  "result": "Changed pkg/use.py; ran pytest."}))
sys.exit(int(os.environ.get("FAKE_RC", "0")))
'''


def _git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout


def _graph(sha):
    return {"sha": sha, "schema_version": 4, "built_by": {"sha": "abc", "version": "test"},
            "containment": {"all_contained": True, "steps": [{"step": "index-python", "contained": True}]},
            "nodes": [{"id": "pkg", "kind": "package", "path": "pkg/__init__.py"}, {"id": "pkg.core", "kind": "module", "path": "pkg/core.py"},
                      {"id": "pkg.use", "kind": "module", "path": "pkg/use.py"}],
            "symbols": [{"id": "pkg.core.derive", "module": "pkg.core", "name": "derive", "qualname": "derive", "kind": "function", "line": 4, "end_line": 5},
                        {"id": "pkg.use.go", "module": "pkg.use", "name": "go", "qualname": "go", "kind": "function", "line": 4, "end_line": 5}],
            "symbol_edges": [{"from": "pkg.use.go", "to": "pkg.core.derive", "type": "calls", "tier": "semantic",
                              "evidence": [{"lane": "scip", "line": 5, "path": "pkg/use.py"}]}],
            "module_edges": [], "resolution_coverage": []}


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    for rel, text in {"pkg/__init__.py": "", "pkg/core.py": CORE, "pkg/use.py": USE, "README.md": "r\n"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "one")
    (root / ".git" / "info" / "exclude").write_text(".hobbes/\n")
    sha = _git(root, "rev-parse", "HEAD").strip()
    (root / ".hobbes" / "derived").mkdir(parents=True)
    (root / ".hobbes" / "derived" / "graph.json").write_text(json.dumps(_graph(sha)))
    fake = tmp_path / "hobbes-session"
    fake.write_text(FAKE_SESSION)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sekrit-token")
    return root, sha, fake, tmp_path / "sessions", tmp_path / "logs"


def _run(world, monkeypatch, change, *extra):
    root, sha, fake, sessions, logs = world
    monkeypatch.setenv("FAKE_CHANGE", json.dumps(change))
    before = set(sessions.glob("*/dispatch.json"))
    rc = cli.main(["dispatch", "--repo", str(root), "--task", "Make go() double its input.\n\nKeep derive as it is.", "--session-bin", str(fake),
                   "--sessions", str(sessions), "--log-dir", str(logs), "--no-verify", "--claude-bin", "/opt/claude", *extra])
    new = set(sessions.glob("*/dispatch.json")) - before  # ids in one second differ only in their random suffix
    return rc, json.loads(new.pop().read_text()) if new else None


def test_a_clean_change_runs_the_stack_clears_the_gate_and_writes_one_log_for_the_session(world, monkeypatch):
    root, sha, fake, sessions, logs = world
    rc, rec = _run(world, monkeypatch, {"pkg/use.py": USE.replace("derive(1)", "derive(2) * 2")})
    assert rc == 0 and rec["gate"]["verdict"] == "clear" and rec["files"] == ["pkg/use.py"] and rec["commits"] == 1
    sid = rec["session"]
    argv = json.loads((sessions / sid / "argv.json").read_text())
    a = argv["argv"]
    assert argv["token"] == "sekrit-token"  # the token reaches the session through the environment …
    assert "sekrit" not in json.dumps(a) and "sekrit" not in json.dumps(rec)  # … and never an argv or the record
    for flag, value in (("--egress", "api.anthropic.com"), ("--role", "implementer"), ("--ref", sha), ("--max-turns", "80"),
                        ("--claude-bin", "/opt/claude")):
        assert a[a.index(flag) + 1] == value, flag
    assert "--commit-on-exit" in a and a[a.index("--box") + 1].endswith("calvin.box.policy")
    envs = [a[i + 1] for i, x in enumerate(a) if x == "--env"]
    assert "GIT_AUTHOR_NAME=hobbes-dispatch" in envs and not any("hobbes-verify" in e for e in envs)
    brief = Path(a[a.index("--task-file") + 1]).read_text()
    assert brief.startswith("Make go() double its input.") and "mcp__hobbes__exec" in brief and "no Bash tool" in brief

    assert rec["egress"]["opened"] == {"api.anthropic.com:443": 1} and rec["egress"]["refused"] == {"pypi.org:443": 1}
    assert rec["flight"]["by_decision"] == {"allow": 1, "deny": 1} and rec["flight"]["denied"] == ["pip download x"]
    assert rec["envelope"]["num_turns"] == 7
    # retention (ADR-107's amendment): the doer's state and reasoning are gone; its output stays
    assert rec["retention"]["doer_state_removed_by_dispatch"] == [".cache/claude-cli-nodejs", ".claude", ".claude.json"]
    assert rec["retention"]["reasoning_left"] == []
    assert not (sessions / sid / ".claude").exists() and not (sessions / sid / ".claude.json").exists()
    assert (sessions / sid / "flight.jsonl").exists() and (sessions / sid / "dispatch.diff").exists()

    log = logs / f"{sid}.md"
    assert rec["log"] == str(log)
    text = log.read_text()
    for want in ("# Harness session", "**Gate:** **clear**", "refused `pypi.org:443`×1", "denied: `pip download x`",
                 "## Review", "- gate: pending", "Changed pkg/use.py; ran pytest.",
                 "Recorded sessions are evaluation rows, never model training data."):
        assert want in text, want
    assert "sekrit" not in text


def test_an_invented_name_blocks_and_each_session_gets_its_own_file(world, monkeypatch):
    root, sha, fake, sessions, logs = world
    _run(world, monkeypatch, {"pkg/use.py": USE.replace("derive(1)", "derive(2)")})
    rc, rec = _run(world, monkeypatch, {"pkg/use.py": USE.replace("return derive(1)", "return quantum_flux(1)")})
    assert rc == 1 and rec["gate"]["verdict"] == "blocked" and rec["gate"]["blocking"] == ["invented"]
    assert len(list(logs.glob("*.md"))) == 2
    assert "**Gate:** **blocked**" in Path(rec["log"]).read_text() and "`invented` pkg/use.py" in Path(rec["log"]).read_text()


def test_a_session_that_leaves_nothing_logs_it_and_exits_3(world, monkeypatch):
    monkeypatch.setenv("FAKE_RC", "1")
    rc, rec = _run(world, monkeypatch, {})
    assert rc == 3 and rec["branch"] is None and rec["files"] == [] and "none harvested" in Path(rec["log"]).read_text()


def test_the_ingest_must_be_at_the_parent_and_nothing_runs_when_it_is_not(world, monkeypatch, capsys):
    root, sha, fake, sessions, logs = world
    (root / "README.md").write_text("changed\n")
    _git(root, "commit", "-qam", "two")
    rc, rec = _run(world, monkeypatch, {"pkg/use.py": USE})
    assert rc == 2 and rec is None and not sessions.exists()
    assert "the ingest is at" in capsys.readouterr().err


def test_no_token_is_refused_and_the_key_file_supplies_one_without_printing_it(world, monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN")
    rc, rec = _run(world, monkeypatch, {"pkg/use.py": USE})
    assert rc == 2 and rec is None and "CLAUDE_CODE_OAUTH_TOKEN" in capsys.readouterr().err
    keys = tmp_path / "keys.txt"
    keys.write_text("anthropic_key=other\nclaude_oauth_token=from-the-file\n")
    rc, rec = _run(world, monkeypatch, {"pkg/use.py": USE.replace("derive(1)", "derive(3)")}, "--secrets", str(keys))
    argv = json.loads((world[3] / rec["session"] / "argv.json").read_text())
    assert rc == 0 and argv["token"] == "from-the-file" and "from-the-file" not in json.dumps(rec)
    assert "from-the-file" not in capsys.readouterr().err


def test_dry_run_shows_the_brief_and_the_sessions_plan_and_logs_nothing(world, monkeypatch, capsys):
    root, sha, fake, sessions, logs = world
    rc = cli.main(["dispatch", "--repo", str(root), "--task", "t", "--session-bin", str(fake), "--sessions", str(sessions),
                   "--log-dir", str(logs), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0 and "PLAN: podman run --network hobbes-int-" in out and "How this session works" in out
    assert not logs.exists()


def test_a_partition_reaches_the_brief_and_the_gate(world, monkeypatch, tmp_path):
    part = tmp_path / "part.json"
    part.write_text(json.dumps(["pkg/core.py"]))
    rc, rec = _run(world, monkeypatch, {"pkg/use.py": USE.replace("derive(1)", "derive(4)")}, "--partition", str(part))
    assert rc == 1 and rec["gate"]["blocking"] == ["partition"] and rec["gate"]["partition"]["checked"]
    brief = Path(rec["task"]["brief"]).read_text()
    assert "Write only these files (the gate checks it): pkg/core.py." in brief


def test_an_api_error_under_a_success_subtype_is_logged_as_an_error(world, monkeypatch):
    # the no-spend smoke (ADR-107): Claude Code with a bad token prints subtype "success" beside is_error and a 401
    root, sha, fake, sessions, logs = world
    fake.write_text(fake.read_text().replace('"total_cost_usd": 0.42,', '"total_cost_usd": 0, "api_error_status": 401, "terminal_reason": "api_error",')
                    .replace('"is_error": False', '"is_error": True'))
    rc, rec = _run(world, monkeypatch, {})
    assert rec["envelope"]["api_error_status"] == 401
    assert "**with an error** (API status 401, `api_error`)" in Path(rec["log"]).read_text()


def test_parse_envelope_takes_the_last_json_object_and_caps_the_result():
    out = "noise\n" + json.dumps({"type": "result", "num_turns": 3, "result": "x" * 5000, "usage": {"a": 1}}) + "\n"
    env = dp.parse_envelope(out)
    assert env["num_turns"] == 3 and len(env["result"]) < 4100 and "usage" not in env
    assert dp.parse_envelope("not json") == {}
