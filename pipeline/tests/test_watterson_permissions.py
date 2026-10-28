"""Tests for route-based permission decisions (DEC-007).

Requests are built by hand; ``TestThroughTheAgent`` sends them from the
fake ACP agent through a real session, so the whole path is covered.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

import pytest

from hobbes.watterson.permissions import (
    Annotation,
    Route,
    RoutePolicy,
    annotate,
    classify,
    command_paths,
    load_test_files,
    modes_for,
    once,
    terminal_ask,
)
from hobbes.watterson.providers import AgentSpec, PermissionOption, PermissionRequest, TextChunk, deny_all, run_prompt

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_acp_agent.py"
OPTIONS = (
    PermissionOption("yes", "Allow", "allow_once"),
    PermissionOption("always", "Always allow", "allow_always"),
    PermissionOption("no", "Reject", "reject_once"),
)


def request(kind=None, *, title="t", raw=None, paths=(), options=OPTIONS) -> PermissionRequest:
    return PermissionRequest("call-1", title, options, kind=kind, raw_input=raw, paths=tuple(paths))


@pytest.fixture
def repo(tmp_path) -> Path:
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    return root


class TestModes:
    def test_guarded_turns_the_harness_judges_on(self):
        assert modes_for(Route.GUARDED, "claude") == ("auto", "default")
        assert modes_for(Route.GUARDED, "codex") == ("agent",)
        assert modes_for(Route.GUARDED, "gemini") == ("default",)

    def test_manual_asks_most(self):
        assert modes_for(Route.MANUAL, "claude") == ("default",)
        assert modes_for(Route.MANUAL, "codex") == ("workspace-write",)

    def test_an_unknown_agent_is_left_alone(self):
        assert modes_for(Route.GUARDED, "my-agent") == ()


class TestClassify:
    @pytest.mark.parametrize("path", [
        ".claude/settings.json", ".claude/settings.local.json", ".codex/rules/default.rules",
        ".codex/config.toml", ".gemini/settings.json", ".gemini/policies/auto.toml",
    ])
    def test_agent_config_in_the_repo(self, repo, path):
        fact = classify(path, repo)
        assert fact.agent_config and fact.inside and fact.shown == path

    def test_agent_config_in_home(self, repo):
        fact = classify(str(Path.home() / ".codex" / "rules" / "default.rules"), repo)
        assert fact.agent_config and not fact.inside

    @pytest.mark.parametrize("path", [
        ".git/hooks/pre-commit", ".git/config", ".env", "svc/.env.local",
        ".github/workflows/ci.yml", ".gitlab-ci.yml", ".circleci/config.yml",
    ])
    def test_repo_controlled_execution(self, repo, path):
        assert classify(path, repo).repo_exec

    @pytest.mark.parametrize("path", ["src/a.py", ".claude/commands/x.md", ".github/CODEOWNERS", "env.py"])
    def test_ordinary_files(self, repo, path):
        fact = classify(path, repo)
        assert fact.inside and not (fact.agent_config or fact.repo_exec)

    def test_outside_and_dot_dot(self, repo):
        assert not classify("/etc/hosts", repo).inside
        fact = classify("../other/x.py", repo)
        assert not fact.inside and fact.shown == str(repo.parent / "other" / "x.py")

    def test_test_files(self, repo):
        assert classify(str(repo / "tests/test_a.py"), repo, frozenset({"tests/test_a.py"})).test


class TestCommandPaths:
    def test_path_like_words(self):
        assert command_paths("cat .env > /tmp/out 2>>err.log --file=./x.txt -v ~/notes") == [
            ".env", "/tmp/out", "./x.txt", "~/notes",
        ]

    def test_urls_and_plain_words_are_not_paths(self):
        assert command_paths("curl https://example.com/a && npm test") == []

    def test_unbalanced_quotes_fall_back_to_splitting(self):
        assert command_paths("echo 'oops .git/config") == [".git/config"]


class TestAnnotate:
    def test_an_edit(self, repo):
        note = annotate(request("edit", raw={"file_path": str(repo / "src/a.py")}, paths=[str(repo / "src/a.py")]), repo)
        assert note.lines() == ["edits: src/a.py"] and not note.agent_config_write

    def test_a_command_with_warnings(self, repo):
        note = annotate(request("execute", raw={"command": "cp .env /tmp/leak && cat .claude/settings.json"}), repo)
        assert note.lines() == [
            "runs: cp .env /tmp/leak && cat .claude/settings.json",
            "! names an agent's own permission config: .claude/settings.json",
            "! touches files the repo's tooling runs or loads: .env",
            "! reaches outside the repo: /tmp/leak",
        ]
        assert not note.agent_config_write  # a command is warned about, never hard-denied

    def test_a_list_command_and_a_title_command(self, repo):
        assert annotate(request("execute", raw={"command": ["git", "push"]}), repo).command == "git push"
        assert annotate(request("execute", title="rm -rf build"), repo).command == "rm -rf build"

    def test_an_agent_config_write(self, repo):
        note = annotate(request("edit", paths=[str(repo / ".claude/settings.local.json")]), repo)
        assert note.agent_config_write
        assert note.lines()[-1] == "! changes an agent's own permission config: .claude/settings.local.json"

    def test_fetch_and_tests(self, repo):
        note = annotate(request("fetch", raw={"url": "https://x.dev"}), repo)
        assert note.lines() == ["! reaches the network: https://x.dev"]
        note = annotate(request("edit", paths=[str(repo / "t/test_a.py")]), repo, frozenset({"t/test_a.py"}))
        assert note.lines() == ["edits: t/test_a.py (test)"]


class TestLoadTestFiles:
    def test_reads_tests_json(self, tmp_path):
        (tmp_path / "tests.json").write_text(json.dumps({"tests": [{"file": "t/a.py"}, {"file": "t/b.py"}, {}]}))
        assert load_test_files(tmp_path) == {"t/a.py", "t/b.py"}

    def test_absent_or_bad_is_empty(self, tmp_path):
        assert load_test_files(tmp_path) == frozenset()
        (tmp_path / "tests.json").write_text("[")
        assert load_test_files(tmp_path) == frozenset()


class Asker:
    def __init__(self, answer: str | None) -> None:
        self.answer, self.seen = answer, []

    async def __call__(self, req, note):
        self.seen.append((req, note))
        return self.answer


def decide(policy: RoutePolicy, req: PermissionRequest) -> str | None:
    return asyncio.run(policy(req))


class TestRoutePolicy:
    def config_edit(self, repo):
        return request("edit", paths=[str(repo / ".codex/rules/default.rules")])

    def test_guarded_hard_denies_agent_config_edits_without_asking(self, repo):
        asker = Asker("yes")
        policy = RoutePolicy(Route.GUARDED, repo, ask=asker)
        assert decide(policy, self.config_edit(repo)) == "no" and asker.seen == []
        assert "permission config" in policy.reasons["call-1"]

    def test_guarded_hard_deny_holds_with_allow_unasked(self, repo):
        assert decide(RoutePolicy(Route.GUARDED, repo, allow_unasked=True), self.config_edit(repo)) == "no"

    def test_manual_asks_even_for_agent_config(self, repo):
        asker = Asker("yes")
        assert decide(RoutePolicy(Route.MANUAL, repo, ask=asker), self.config_edit(repo)) == "yes"
        (_, note), = asker.seen
        assert note.agent_config_write

    def test_everything_else_is_asked_with_its_annotation(self, repo):
        asker = Asker("always")  # a human may choose "always"; the policy never does
        req = request("execute", raw={"command": "make deploy"})
        assert decide(RoutePolicy(Route.GUARDED, repo, ask=asker), req) == "always"
        assert asker.seen[0][1].command == "make deploy"

    def test_no_one_to_ask_rejects_once_or_allows_once(self, repo):
        req = request("execute", raw={"command": "ls"})
        policy = RoutePolicy(Route.GUARDED, repo)
        assert decide(policy, req) == "no" and policy.reasons["call-1"] == "denied: no terminal to ask on"
        assert decide(RoutePolicy(Route.MANUAL, repo, allow_unasked=True), self.config_edit(repo)) == "yes"

    @pytest.mark.parametrize("route", list(Route))
    def test_allowed_titles_are_allowed_once_without_asking(self, repo, route):
        asker = Asker("no")
        policy = RoutePolicy(route, repo, ask=asker, allowed=lambda r: r.title == "mcp__hobbes__who_calls")
        assert decide(policy, request("other", title="mcp__hobbes__who_calls")) == "yes"
        assert asker.seen == [] and "knowledge tool" in policy.reasons["call-1"]
        assert decide(policy, request("other", title="mcp__other__who_calls")) == "no"
        assert len(asker.seen) == 1

    def test_never_an_always_option_by_itself(self, repo):
        only_always = (PermissionOption("a", "Always", "allow_always"), PermissionOption("r", "Never", "reject_always"))
        req = request("execute", raw={"command": "ls"}, options=only_always)
        assert decide(RoutePolicy(Route.GUARDED, repo, allow_unasked=True), req) is None
        assert decide(RoutePolicy(Route.GUARDED, repo), req) is None
        assert decide(RoutePolicy(Route.GUARDED, repo, allowed=lambda r: True), req) is None
        assert once(req, "allow") is None

    def test_an_automatic_reject_lets_the_turn_go_on(self, repo):
        # codex-acp sends both as reject_once; "cancel" ends the turn (DEC-007 notes)
        codex = (PermissionOption("approved", "Yes", "allow_once"),
                 PermissionOption("cancel", "No, and tell Codex", "reject_once"),
                 PermissionOption("decline", "No, continue", "reject_once"))
        req = request("execute", raw={"command": "curl x"}, options=codex)
        assert decide(RoutePolicy(Route.GUARDED, repo), req) == "decline"
        assert decide(RoutePolicy(Route.GUARDED, repo), request("execute", options=codex[:2])) == "cancel"
        assert deny_all(req) == "decline"


class TestTerminalAsk:
    def ask(self, answer: str, req=None, repo=Path("/r")) -> tuple[str | None, str]:
        out = io.StringIO()
        ask = terminal_ask("claude", read_line=lambda: answer, out=out)
        req = req or request("execute", title="git push", raw={"command": "git push"})
        return asyncio.run(ask(req, annotate(req, repo))), out.getvalue()

    def test_prompt_text(self):
        _, text = self.ask("1")
        assert text == (
            "hobbes: claude asks: git push\n"
            "  runs: git push\n"
            "  1) Allow\n"
            "  2) Always allow (claude remembers this itself and will not ask Hobbes again for matching actions)\n"
            "  3) Reject\n"
            "choose 1-3 [Enter rejects]: "
        )

    @pytest.mark.parametrize("answer,chosen", [("1\n", "yes"), ("2", "always"), ("3", "no"),
                                               ("", "no"), ("0", "no"), ("9", "no"), ("y", "no")])
    def test_answers(self, answer, chosen):
        assert self.ask(answer)[0] == chosen


class TestThroughTheAgent:
    def run(self, prompt: str, policy: RoutePolicy, cwd: Path) -> str:
        spec = AgentSpec("fake", (sys.executable, str(FAKE_AGENT)))

        async def go():
            return [e async for e in run_prompt(spec, prompt, cwd=cwd, on_permission=policy)]

        return "".join(e.text for e in asyncio.run(go()) if isinstance(e, TextChunk))

    def test_guarded_denies_an_agent_config_edit_end_to_end(self, repo):
        asker = Asker("yes")
        text = self.run("edit .claude/settings.json", RoutePolicy(Route.GUARDED, repo, ask=asker), repo)
        assert text.endswith("[permission: no]") and asker.seen == []

    def test_a_late_detailed_edit_is_annotated(self, repo):
        asker = Asker("yes")
        text = self.run("late-edit .git/hooks/pre-commit", RoutePolicy(Route.GUARDED, repo, ask=asker), repo)
        assert text.endswith("[permission: yes]")
        note: Annotation = asker.seen[0][1]
        assert note.lines() == [
            "edits: .git/hooks/pre-commit",
            "! touches files the repo's tooling runs or loads: .git/hooks/pre-commit",
        ]
