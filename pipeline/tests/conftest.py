"""Shared fixtures: a fake hobbes-policy binary for hermetic CLI tests,
and a minimal committed git repo for narrative-artifact tests.

The real Go binary is exercised by its own test suite (go/cmd/hobbes-policy);
here we only test the Python side of the ADR-003 contract, so a shell script
that emits canned JSON and a chosen exit code stands in for it.
"""

import json
import os
import stat
import subprocess

import pytest


@pytest.fixture(autouse=True)
def _lane_a_only(monkeypatch, request):
    """Run the extractor lane-A-only unless a test opts in.

    Lane B shells out to a SCIP indexer, which makes the suite slow (48s
    against 3.5s) and non-hermetic — it would need Node, `npm install` in
    scip/, and a resolvable environment for the fixture repos. Tests that
    want lane B mark themselves `@pytest.mark.lane_b`; the real thing is
    covered by the M2 exit check on real repos.
    """
    if "lane_b" not in request.keywords:
        monkeypatch.setenv("HOBBES_SCIP", "0")

#: Contents of the `git_repo` fixture's single module (6 lines).
GIT_REPO_APP = '''"""A tiny app module."""

GREETING = "hi"

def greet(name):
    return f"{GREETING} {name}"
'''


@pytest.fixture
def git_repo(tmp_path):
    """A committed single-file git repo (app.py) for staleness/pin tests."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(GIT_REPO_APP)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "one"], check=True)
    return repo

FAKE_RESOLUTION = {
    "command": "git push --force origin main",
    "decision": "deny",
    "default": False,
    "rule": {
        "pattern": "git push --force*",
        "decision": "deny",
        "reason": "force-push forbidden",
        "scope": "box",
        "source": "/home/x/.hobbes/box.policy",
    },
    "matches": [],
}


@pytest.fixture
def fake_policy_bin(tmp_path):
    """Create a fake hobbes-policy script.

    Returns a factory: ``fake_policy_bin(exit_code, payload=None)`` writes a
    script that prints *payload* as JSON (arguments it received under
    ``"argv"`` when payload is None) and exits with *exit_code*.
    """

    def make(exit_code: int, payload: dict | None = None) -> str:
        path = tmp_path / "hobbes-policy"
        if payload is None:
            body = (
                "#!/bin/sh\n"
                'printf \'{"argv": "%s"}\\n\' "$*"\n'
                f"exit {exit_code}\n"
            )
        else:
            body = f"#!/bin/sh\ncat <<'EOF'\n{json.dumps(payload)}\nEOF\nexit {exit_code}\n"
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return str(path)

    return make


@pytest.fixture
def no_real_binary(monkeypatch):
    """Guarantee binary discovery fails: clear the env var and empty PATH."""
    monkeypatch.delenv("HOBBES_POLICY_BIN", raising=False)
    monkeypatch.setenv("PATH", os.devnull)
