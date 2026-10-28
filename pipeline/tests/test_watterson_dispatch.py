"""Roles (DEC-022) and one worker run end to end against the fake ACP agent.

Each test builds a git repo with ``.hobbes/roles.toml``; the worker is
``tests/fixtures/fake_acp_agent.py``, whose ``write <path> <text>`` prompt
stands in for an agent's edit. The test command passes when ``src/ok.txt``
exists, so the brief decides pass or fail. Its ``call`` prompt reaches the
worker's ``report`` tool through the real relay, and `` && `` chains it
after an edit.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from hobbes.watterson import cli, roles
from hobbes.watterson.dispatch import REPORT_RULES, dispatch, is_worker_tool, worker_prompt
from hobbes.watterson.providers import AgentSpec, PermissionRequest

from .test_watterson_freshness import commit, git

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"
REGISTRY = {"fake": AgentSpec("fake", (sys.executable, str(FAKE_AGENT)))}
TEST_COMMAND = [sys.executable, "-c",
                "import pathlib, sys; sys.exit(0 if pathlib.Path('src/ok.txt').exists() else 1)"]


ROLES = (f"test = {json.dumps(TEST_COMMAND)}\n\n"
         '[roles.impl]\nagent = "fake"\nknowledge = false\n'
         'prompt = "roles/impl.md"\nwrites = ["src/*"]\n')


def write_roles(root: Path, body: str | None = None) -> None:
    hobbes = root / ".hobbes"
    (hobbes / "roles").mkdir(parents=True, exist_ok=True)
    (hobbes / "roles" / "impl.md").write_text("You implement.\n")
    (hobbes / "roles.toml").write_text(ROLES if body is None else body)


def report(outcome: str, text: str = "did it") -> str:
    """A fake worker's prompt part that calls its report tool."""
    return f"call hobbes-worker report {json.dumps({'outcome': outcome, 'report': text})}"


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    root = (tmp_path / "repo").resolve()
    (root / "src").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@t")
    commit(root, "src/keep.txt")
    roles.ensure_ignored(root)
    write_roles(root)
    return root


def run(root: Path, brief: str, on_event=None):
    return asyncio.run(dispatch(root, roles.load(root), "impl", brief,
                                registry=REGISTRY, on_event=on_event))


def branches(root: Path) -> list[str]:
    return git(root, "branch", "--format=%(refname:short)").split()


class TestRoles:
    def test_loads_the_mapping(self, repo):
        mapping = roles.load(repo)
        role = mapping.role("impl")
        assert mapping.test == tuple(TEST_COMMAND)
        assert mapping.branch == "main" and mapping.coordinator is None and mapping.workers == 2
        assert (role.agent, role.route, role.knowledge, role.review) == ("fake", "guarded", False, False)
        assert role.prompt == repo / ".hobbes" / "roles" / "impl.md"
        assert role.prompt_text() == "You implement.\n"

    def test_writes_globs_cross_folders(self, repo):
        role = roles.load(repo).role("impl")
        assert role.may_write("src/a/b.py") and not role.may_write("a.txt")

    @pytest.mark.parametrize("body, message", [
        ('test = ["t"]\nbogus = 1\n', "unknown keys ['bogus']"),
        ('[roles.x]\nagent = "a"\nprompt = "p"\nwrites = []\n', "test must be"),
        ('test = ["t"]\n[roles.x]\nagent = "a"\nprompt = "p"\nwrites = []\nroute = "yolo"\n', "route must be"),
        ('test = ["t"]\n[roles.x]\nagent = "a"\nprompt = "p"\n', "writes must be"),
        ('test = ["t"]\n[roles.x]\nagent = "a"\nprompt = "p"\nwrites = []\nmodel = "m"\n', "unknown keys ['model']"),
        ('test = ["t"]\ncoordinator = "lead"\n', "coordinator 'lead' is not a role"),
        ('test = ["t"]\nworkers = 0\n', "workers must be a whole number, at least 1"),
        ('test = ["t"]\n[roles.x]\nagent = "a"\nprompt = "p"\nwrites = []\nreview = "yes"\n',
         "review must be true or false"),
    ])
    def test_rejects_a_bad_mapping(self, repo, body, message):
        write_roles(repo, body)
        with pytest.raises(roles.RolesError, match=message.replace("[", r"\[").replace("]", r"\]")):
            roles.load(repo)

    def test_unknown_role_names_the_known_ones(self, repo):
        with pytest.raises(roles.RolesError, match=r"no role 'x' \(roles: impl\)"):
            roles.load(repo).role("x")

    def test_role_files_stay_out_of_git(self, repo):
        assert git(repo, "status", "--porcelain") == ""
        assert ".hobbes/" in (repo / ".git" / "info" / "exclude").read_text()

    def test_role_files_stay_out_of_git_where_hobbes_is_tracked(self, tmp_path):
        root = tmp_path / "tracks"
        (root / ".hobbes").mkdir(parents=True)
        git(root, "init", "-q", "-b", "main")
        commit(root, ".hobbes/README.md")
        write_roles(root)
        change = roles.ensure_ignored(root)
        assert change == ("added .hobbes/derived/ to .git/info/exclude; "
                          "added .hobbes/roles.toml, .hobbes/roles/ to .git/info/exclude")
        assert git(root, "status", "--porcelain") == ""
        assert git(root, "ls-files", ".hobbes") == ".hobbes/README.md"
        assert roles.ensure_ignored(root) is None


class TestDispatch:
    def test_a_passing_run_merges(self, repo):
        handoff = run(repo, "write src/ok.txt hello")
        assert handoff.merged, handoff.reason
        assert (handoff.outcome, handoff.asked, handoff.report) == ("merged", None, "")
        assert handoff.stop_reason == "end_turn"
        assert handoff.summary == "role: [hobbes role: impl]\nwrote src/ok.txt"
        assert handoff.files == ["src/ok.txt"] and len(handoff.commits) == 1
        assert handoff.test["exit"] == 0 and not handoff.target_moved
        assert (repo / "src" / "ok.txt").read_text() == "hello\n"
        assert git(repo, "log", "-1", "--format=%s") == (
            f"Merge {handoff.branch} (impl, dispatch {handoff.id})")
        assert git(repo, "log", "-1", "--format=%B", "HEAD^2").startswith("impl: write src/ok.txt hello")
        assert branches(repo) == ["main"]
        assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
        record = json.loads(Path(handoff.record).read_text())
        assert record["merged"] is True and record["files"] == ["src/ok.txt"]

    def test_the_worker_gets_the_role_how_to_report_and_the_brief(self, repo):
        assert worker_prompt("impl", "You implement.\n", "do it") == (
            f"[hobbes role: impl]\nYou implement.\n\n[hobbes report]\n{REPORT_RULES}\n\n[hobbes brief]\ndo it")

    def test_the_session_has_the_worker_tools(self, repo):
        (server,) = json.loads(run(repo, "mcp?").summary.split("\n", 1)[1])
        assert server["name"] == "hobbes-worker" and server["args"][-1] == "hobbes-worker"

    def test_only_the_report_tool_on_our_server_is_allowed(self):
        def request(title, server="hobbes-worker"):
            return PermissionRequest("c", title, (), meta={"claudeCode": {"mcpServer": {"name": server, "source": "dynamic"}}})

        assert is_worker_tool(request("mcp__hobbes-worker__report"))
        assert not is_worker_tool(request("mcp__hobbes-worker__dispatch"))
        assert not is_worker_tool(request("mcp__hobbes-worker__report", server="other"))

    def test_a_report_of_done_merges_with_the_report(self, repo):
        handoff = run(repo, f"write src/ok.txt hi && {report('done', 'wrote ok')}")
        assert (handoff.outcome, handoff.merged) == ("merged", True), handoff.reason
        assert (handoff.asked, handoff.report) == ("done", "wrote ok")
        assert "called report: Reported. End your turn now." in handoff.summary
        record = json.loads(Path(handoff.record).read_text())
        assert (record["outcome"], record["report"]) == ("merged", "wrote ok")

    def test_a_report_of_review_is_tested_and_kept(self, repo):
        head = git(repo, "rev-parse", "HEAD")
        handoff = run(repo, f"write src/ok.txt hi && {report('review')}")
        assert (handoff.outcome, handoff.merged) == ("review", False)
        assert handoff.reason == "paused for review: the worker asked"
        assert handoff.test["exit"] == 0
        assert git(repo, "rev-parse", "HEAD") == head and handoff.branch in branches(repo)

    def test_a_role_that_sets_review_pauses_without_a_report(self, repo):
        write_roles(repo, ROLES + "review = true\n")
        handoff = run(repo, "write src/ok.txt hi")
        assert (handoff.outcome, handoff.asked) == ("review", None)
        assert handoff.reason == "paused for review: role impl sets review"
        assert handoff.branch in branches(repo)

    def test_a_report_of_blocked_stops_before_the_test(self, repo):
        handoff = run(repo, f"write src/ok.txt hi && {report('blocked', 'no access')}")
        assert (handoff.outcome, handoff.merged) == ("stopped", False)
        assert handoff.reason == "the worker reported it is blocked"
        assert handoff.report == "no access" and handoff.test is None
        assert len(handoff.commits) == 1 and handoff.branch in branches(repo)

    def test_an_unknown_outcome_is_a_tool_error(self, repo):
        handoff = run(repo, f"write src/ok.txt hi && {report('maybe')}")
        assert "called report: outcome must be one of done, blocked, review [error]" in handoff.summary
        assert (handoff.asked, handoff.outcome) == (None, "merged")

    def test_a_failing_test_keeps_the_branch(self, repo):
        head = git(repo, "rev-parse", "HEAD")
        handoff = run(repo, "write src/other.txt x")
        assert (handoff.outcome, handoff.merged) == ("stopped", False)
        assert handoff.reason == "the test command failed (exit 1)"
        assert git(repo, "rev-parse", "HEAD") == head
        assert handoff.branch in branches(repo)

    def test_a_path_outside_writes_is_not_merged(self, repo):
        handoff = run(repo, "write a.txt x")
        assert not handoff.merged and handoff.test is None
        assert handoff.outside_writes == ["a.txt"]
        assert "outside role impl's writes: a.txt" in handoff.reason

    def test_no_change_no_merge(self, repo):
        handoff = run(repo, "hello there")
        assert not handoff.merged and handoff.reason == "the worker changed nothing"
        assert handoff.commits == []

    def test_a_dirty_checkout_is_not_merged_into(self, repo):
        (repo / "src" / "keep.txt").write_text("mine\n")
        handoff = run(repo, "write src/ok.txt hello")
        assert not handoff.merged and handoff.test["exit"] == 0
        assert handoff.reason == "your checkout of main has uncommitted changes"
        assert (repo / "src" / "keep.txt").read_text() == "mine\n"

    def test_another_branch_checked_out_is_not_merged_into(self, repo):
        git(repo, "checkout", "-q", "-b", "other")
        handoff = run(repo, "write src/ok.txt hello")
        assert not handoff.merged and handoff.reason == "your checkout is on other, not main"

    def test_main_moving_meanwhile_is_merged_in_before_the_test(self, repo):
        moved = []

        def on_event(event, policy):
            if not moved:
                moved.append(commit(repo, "src/keep.txt"))

        handoff = run(repo, "write src/ok.txt hello", on_event)
        assert handoff.merged, handoff.reason
        assert handoff.target_moved
        assert git(repo, "merge-base", "--is-ancestor", moved[0], "HEAD") == ""
        assert (repo / "src" / "ok.txt").exists()

    def test_a_conflict_stays_in_the_worktree(self, repo):
        moved = []

        def on_event(event, policy):
            if not moved:
                moved.append(commit(repo, "src/ok.txt", "theirs\n"))

        handoff = run(repo, "write src/ok.txt hello", on_event)
        assert not handoff.merged and handoff.test is None
        assert handoff.reason == "main moved and conflicts with the worker's branch"
        assert git(repo, "rev-parse", "HEAD") == moved[0]
        assert git(repo, "status", "--porcelain") == ""
        assert handoff.branch in branches(repo)


@pytest.fixture
def agents_file(tmp_path, monkeypatch):
    path = tmp_path / "agents.toml"
    path.write_text(f'[agents.fake]\ncommand = {json.dumps([sys.executable, str(FAKE_AGENT)])}\n')
    monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))


class TestCli:
    def test_roles_lists_each_role(self, repo, capsys):
        assert cli.main(["roles", "--repo", str(repo)]) == 0
        out = capsys.readouterr().out
        assert "impl: fake, route guarded, knowledge off" in out
        assert "writes src/*" in out

    def test_roles_without_a_file_shows_an_example(self, repo, capsys):
        (repo / ".hobbes" / "roles.toml").unlink()
        assert cli.main(["roles", "--repo", str(repo)]) == 1
        err = capsys.readouterr().err
        assert "roles.toml: not found" in err and "[roles.implementer]" in err

    def test_dispatch_exits_0_on_a_merge_and_1_otherwise(self, repo, agents_file, capsys):
        assert cli.main(["dispatch", "--repo", str(repo), "--role", "impl", "write src/ok.txt hi"]) == 0
        captured = capsys.readouterr()
        assert "wrote src/ok.txt" in captured.out
        assert "hobbes: merged into main" in captured.err
        assert cli.main(["dispatch", "--repo", str(repo), "--role", "impl", "write a.txt x"]) == 1
        assert "not merged: changed paths outside" in capsys.readouterr().err

    def test_dispatch_paused_for_review_exits_0(self, repo, agents_file, capsys):
        brief = f"write src/ok.txt hi && {report('review', 'look at ok.txt')}"
        assert cli.main(["dispatch", "--repo", str(repo), "--role", "impl", brief]) == 0
        err = capsys.readouterr().err
        assert "hobbes: the worker reports review:\nlook at ok.txt" in err
        assert "paused for review: the worker asked; branch hobbes/impl-" in err and "kept, tested, not merged" in err

    def test_dispatch_unknown_role_exits_2(self, repo, agents_file, capsys):
        assert cli.main(["dispatch", "--repo", str(repo), "--role", "x", "go"]) == 2
        assert "no role 'x'" in capsys.readouterr().err
