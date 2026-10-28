"""The mapper (DEC-023): a model writes or edits the agent mapping through a checked save.

The model is the fake ACP agent, whose ``call`` prompt reaches the
``hobbes-mapper`` server through the real relay; ``check`` and ``save`` are
also tested by themselves.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hobbes.watterson import cli, mapper, roles

from .test_watterson_dispatch import REGISTRY, TEST_COMMAND, agents_file, git  # noqa: F401 (agents_file is a fixture)
from .test_watterson_freshness import commit

GOOD = (f"coordinator = \"lead\"\ntest = {json.dumps(TEST_COMMAND)}\n\n"
        '[roles.lead]\nagent = "fake"\nprompt = "roles/lead.md"\nwrites = ["docs/*"]\n\n'
        '[roles.impl]\nagent = "fake"\nprompt = "roles/impl.md"\nwrites = ["src/*"]\nreview = true\n')
PROMPTS = {"roles/lead.md": "You coordinate.", "roles/impl.md": "You implement."}


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(tmp_path / "cache"))
    root = (tmp_path / "repo").resolve()
    (root / "src").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "t")
    git(root, "config", "user.email", "t@t")
    commit(root, "src/keep.txt")
    return root


def save_call(roles_toml: str, prompts: dict) -> str:
    return f"call hobbes-mapper save_mapping {json.dumps({'roles_toml': roles_toml, 'prompts': prompts})}"


def run(repo: Path, request: str, **kwargs) -> mapper.MapperResult:
    return asyncio.run(mapper.run_mapper(repo, request, agent="fake", registry=REGISTRY, **kwargs))


class TestCheck:
    def test_a_good_mapping_passes(self, repo):
        assert mapper.check(repo, GOOD, PROMPTS, REGISTRY) == []

    @pytest.mark.parametrize("toml, prompts, wanted", [
        ("", PROMPTS, "roles_toml is empty"),
        ("test = [", PROMPTS, ".hobbes/roles.toml: "),
        (GOOD.replace('agent = "fake"\nprompt = "roles/impl.md"', 'agent = "nope"\nprompt = "roles/impl.md"'),
         PROMPTS, "role impl: agent 'nope'"),
        (GOOD, {"roles/lead.md": "x"}, "role impl: prompt roles/impl.md is neither given"),
        (GOOD, {**PROMPTS, "../escape.md": "x"}, "prompt '../escape.md': not a path under .hobbes/"),
        (GOOD.replace('"roles/impl.md"', '"../../impl.md"'), PROMPTS, "role impl: prompt 'impl.md' is outside .hobbes/"),
        (GOOD, {"roles/lead.md": 3}, "prompts must map each prompt path to its text"),
    ])
    def test_problems_are_named(self, repo, toml, prompts, wanted):
        errors = mapper.check(repo, toml, prompts, REGISTRY)
        assert any(wanted in e for e in errors), errors

    def test_a_prompt_already_there_need_not_be_given_again(self, repo):
        (repo / ".hobbes" / "roles").mkdir(parents=True)
        (repo / ".hobbes" / "roles" / "impl.md").write_text("old\n")
        assert mapper.check(repo, GOOD, {"roles/lead.md": "x"}, REGISTRY) == []

    def test_save_writes_out_of_git_and_keeps_old_prompts(self, repo):
        (repo / ".hobbes" / "roles").mkdir(parents=True)
        (repo / ".hobbes" / "roles" / "old.md").write_text("old\n")
        assert mapper.save(repo, GOOD, PROMPTS, REGISTRY) == []
        assert roles.load(repo).role("impl").review is True
        assert (repo / ".hobbes" / "roles" / "impl.md").read_text() == "You implement.\n"
        assert (repo / ".hobbes" / "roles" / "old.md").exists()
        assert git(repo, "status", "--porcelain") == ""
        assert mapper.save(repo, "test = [", PROMPTS, REGISTRY) and roles.load(repo).coordinator == "lead"


class TestPrompt:
    def test_the_prompt_carries_the_format_agents_mapping_and_request(self, repo):
        assert mapper.current_mapping(repo).startswith("(none yet")
        mapper.save(repo, GOOD, PROMPTS, REGISTRY)
        current = mapper.current_mapping(repo)
        assert "--- .hobbes/roles.toml ---\ncoordinator" in current and "--- .hobbes/roles/impl.md ---\nYou implement." in current
        prompt = mapper.mapper_prompt("add a tester", current=current, agents=["claude", "codex"],
                                      earlier=["first ask"], knowledge=True)
        assert prompt.startswith("[hobbes mapper]\n") and "knowledge tools are attached" in prompt
        assert "[hobbes agents]\nclaude, codex" in prompt and "[hobbes earlier requests]\n- first ask" in prompt
        assert prompt.endswith("\n\n[hobbes request]\nadd a tester")


class TestRun:
    def test_the_model_saves_through_the_tool(self, repo):
        result = run(repo, save_call(GOOD, PROMPTS))
        assert result.saved and result.attempts == [[]] and result.other_changes == []
        assert "called save_mapping: Saved." in result.said
        assert result.summary(repo) == "Mapping saved to .hobbes/roles.toml, 2 role(s): lead, impl; coordinator lead."
        assert json.loads(Path(result.record).read_text())["saved"] is True

    def test_errors_go_back_and_a_second_save_lands(self, repo):
        result = run(repo, f"{save_call(GOOD, {})} && {save_call(GOOD, PROMPTS)}")
        assert len(result.attempts) == 2 and result.attempts[0] and result.attempts[1] == []
        assert "Not saved. Fix these and call save_mapping again:" in result.said and result.saved

    def test_no_save_and_other_edits_are_reported(self, repo):
        result = run(repo, "write src/x.txt hi")
        assert not result.saved and result.other_changes == ["src/x.txt"]
        assert result.summary(repo) == ("Mapping not saved: the model did not call save_mapping.\n"
                                        "The session also changed, outside the mapping: src/x.txt")

    def test_the_session_has_the_mapper_tool_and_no_knowledge_without_a_graph(self, repo):
        (server,) = json.loads(run(repo, "mcp?").said.split("\n", 1)[1])
        assert server["name"] == "hobbes-mapper" and server["args"][-1] == "hobbes-mapper"


class TestDescribe:
    def test_the_mapping_as_data(self, repo):
        assert mapper.describe(repo) is None
        mapper.save(repo, GOOD, PROMPTS, REGISTRY)
        found = mapper.describe(repo)
        assert (found["coordinator"], found["workers"], found["branch"]) == ("lead", 2, "main")
        impl = next(r for r in found["roles"] if r["name"] == "impl")
        assert impl == {"name": "impl", "agent": "fake", "route": "guarded", "knowledge": True, "writes": ["src/*"],
                        "review": True, "prompt_path": ".hobbes/roles/impl.md", "prompt": "You implement.\n",
                        "coordinator": False}

    def test_a_broken_mapping_shows_its_error_and_text(self, repo):
        (repo / ".hobbes").mkdir()
        (repo / ".hobbes" / "roles.toml").write_text("test = [\n")
        found = mapper.describe(repo)
        assert "roles.toml" in found["error"] and found["text"] == "test = [\n"


class TestCli:
    def test_edit_saves_then_lists(self, repo, agents_file, capsys):
        code = cli.main(["roles", "--repo", str(repo), "--agent", "fake", "--edit", save_call(GOOD, PROMPTS)])
        captured = capsys.readouterr()
        assert code == 0 and "hobbes: Mapping saved to .hobbes/roles.toml, 2 role(s)" in captured.err
        assert "impl: fake, route guarded, knowledge on, review" in captured.out

    def test_edit_without_a_save_exits_1_and_an_unknown_agent_2(self, repo, agents_file, capsys):
        assert cli.main(["roles", "--repo", str(repo), "--agent", "fake", "--edit", "hello"]) == 1
        assert "did not call save_mapping" in capsys.readouterr().err
        assert cli.main(["roles", "--repo", str(repo), "--agent", "nobody", "--edit", "x"]) == 2
