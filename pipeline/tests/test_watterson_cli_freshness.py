"""Tests for ``hobbes freshness`` and the session-start check in ``hobbes ask`` (DEC-005).

Repos and stamps come from ``test_freshness``'s helpers. ``ask --repo``
runs against the fake ACP agent fixture; pytest's stdin is not a terminal,
so the check warns rather than asks. Nothing reaches a real harness.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from hobbes.watterson import cli
from hobbes.watterson.freshness import GraphStatus, check_freshness

from .test_watterson_freshness import commit, git, repo, stamp  # noqa: F401 (repo is a fixture)

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"


class TestFreshnessCommand:
    def test_fresh_exits_0(self, repo, capsys):
        stamp(repo)
        assert cli.main(["freshness", "--repo", str(repo)]) == 0
        assert " · fresh" in capsys.readouterr().out

    def test_stale_and_missing_exit_1(self, repo, capsys):
        assert cli.main(["freshness", "--repo", str(repo)]) == 1
        assert "missing" in capsys.readouterr().out
        stamp(repo)
        commit(repo)
        (repo / "z.txt").write_text("")
        assert cli.main(["freshness", "--repo", str(repo)]) == 1
        assert "stale (1 commit behind) · dirty (1 file)" in capsys.readouterr().out

    def test_notes_print_on_a_second_line(self, repo, capsys):
        stamp(repo, dirty=True)
        assert cli.main(["freshness", "--repo", str(repo)]) == 0
        lines = capsys.readouterr().out.splitlines()
        assert lines[1] == "  the graph was extracted from a dirty tree"

    def test_errors_exit_2_without_a_traceback(self, tmp_path, capsys):
        assert cli.main(["freshness", "--repo", str(tmp_path)]) == 2
        assert capsys.readouterr().err == f"hobbes: {tmp_path.resolve()} is not a git repo\n"
        git(tmp_path, "init", "-q")
        assert cli.main(["freshness", "--repo", str(tmp_path)]) == 2
        assert "has no commits yet" in capsys.readouterr().err

    def test_defaults_to_here(self, repo, monkeypatch, capsys):
        stamp(repo)
        monkeypatch.chdir(repo)
        assert cli.main(["freshness"]) == 0


@pytest.fixture
def agents_file(tmp_path, monkeypatch):
    path = tmp_path / "agents.toml"
    path.write_text(f"[agents.fake]\ncommand = {json.dumps([sys.executable, str(FAKE_AGENT)])}\n")
    monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))
    return path


class TestAskRepo:
    def test_the_agent_starts_in_the_repo_after_the_check(self, repo, agents_file, capsys):
        stamp(repo)
        commit(repo)
        assert cli.main(["ask", "--agent", "fake", "--repo", str(repo), "cwd?"]) == 0
        captured = capsys.readouterr()
        assert captured.out == f"session={repo} process={repo}\n"
        # pytest's stdin is not a terminal: warned, not asked, not ingested.
        assert "hobbes: warning: Hobbes graph is stale (1 commit behind)" in captured.err
        assert check_freshness(repo).status is GraphStatus.STALE

    def test_no_refresh_skips_the_check(self, repo, agents_file, capsys):
        assert cli.main(["ask", "--agent", "fake", "--repo", str(repo), "--no-refresh", "cwd?"]) == 0
        captured = capsys.readouterr()
        assert captured.out == f"session={repo} process={repo}\n"
        assert "graph" not in captured.err

    def test_an_unknown_agent_fails_before_the_check(self, repo, agents_file, capsys):
        assert cli.main(["ask", "--agent", "nope", "--repo", str(repo), "hi"]) == 1
        err = capsys.readouterr().err
        assert "unknown agent 'nope'" in err and "graph" not in err

    def test_refresh_and_no_refresh_are_exclusive(self, repo, capsys):
        with pytest.raises(SystemExit):
            cli.main(["ask", "--agent", "fake", "--refresh", "--no-refresh", "hi"])
        assert "not allowed with" in capsys.readouterr().err
