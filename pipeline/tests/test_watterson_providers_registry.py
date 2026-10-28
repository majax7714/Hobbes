"""Tests for the ACP agent registry and its TOML override file."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from hobbes.watterson.providers import (
    BUILTIN_AGENTS,
    AgentSpec,
    ProviderError,
    agents_file,
    get_agent,
    load_registry,
)
from hobbes.watterson.providers.errors import UnknownAgentError
from hobbes.watterson.providers.registry import (
    ADAPTERS_DIR,
    ADAPTERS_INSTALL_HINT,
    LOCKED_ADAPTERS,
    adapter_bin,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _no_user_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("HOBBES_AGENTS_FILE", str(tmp_path / "absent.toml"))


class TestBuiltins:
    def test_the_three_harnesses_and_their_verified_commands(self):
        bins = REPO_ROOT / "adapters" / "node_modules" / ".bin"
        assert {n: s.command for n, s in BUILTIN_AGENTS.items()} == {
            "claude": (str(bins / "claude-agent-acp"),),
            "codex": (str(bins / "codex-acp"),),
            "gemini": ("gemini", "--acp"),
        }

    def test_locked_adapters_carry_the_install_hint_and_gemini_does_not(self):
        assert BUILTIN_AGENTS["claude"].install_hint == ADAPTERS_INSTALL_HINT
        assert BUILTIN_AGENTS["codex"].install_hint == ADAPTERS_INSTALL_HINT
        assert "cd adapters && npm ci" in ADAPTERS_INSTALL_HINT
        assert BUILTIN_AGENTS["gemini"].install_hint is None

    def test_no_builtin_goes_through_npx(self):
        assert all(spec.command[0] != "npx" for spec in BUILTIN_AGENTS.values())

    def test_a_missing_adapter_bin_is_unavailable(self, tmp_path):
        spec = AgentSpec("claude", (str(adapter_bin(LOCKED_ADAPTERS[0], tmp_path)),))
        assert spec.executable() is None

    def test_without_an_override_file_the_registry_is_the_builtins(self):
        assert load_registry() == BUILTIN_AGENTS

    def test_executable_resolves_on_path(self):
        assert AgentSpec("py", (sys.executable,)).executable() == sys.executable
        assert AgentSpec("no", ("hobbes-no-such-binary",)).executable() is None


class TestOverrides:
    def test_an_entry_replaces_a_builtin_and_another_is_added(self, tmp_path, monkeypatch):
        path = tmp_path / "agents.toml"
        path.write_text(
            '[agents.claude]\ncommand = ["claude-agent-acp"]\nenv = { A = "1" }\n'
            '[agents.mine]\ncommand = ["my-agent", "--acp"]\ncwd = "/tmp"\n'
        )
        monkeypatch.setenv("HOBBES_AGENTS_FILE", str(path))
        assert agents_file() == path
        registry = load_registry()
        assert registry["claude"] == AgentSpec("claude", ("claude-agent-acp",), {"A": "1"}, None, str(path))
        assert registry["mine"].command == ("my-agent", "--acp") and registry["mine"].cwd == "/tmp"
        assert registry["codex"] == BUILTIN_AGENTS["codex"]

    @pytest.mark.parametrize(
        "body, message",
        [
            ("[agents.x]\ncommand = []\n", "non-empty list"),
            ("[agents.x]\ncommand = 'claude'\n", "non-empty list"),
            ("[agents.x]\ncommand = ['a']\nenv = { A = 1 }\n", "map strings to strings"),
            ("[agents.x]\ncommand = ['a']\nargs = ['b']\n", "unknown keys: args"),
            ("agents = 3\n", "must be a table"),
            ("[agents.x\n", "agents.toml"),
        ],
    )
    def test_a_bad_file_is_a_clear_error(self, tmp_path, body, message):
        path = tmp_path / "agents.toml"
        path.write_text(body)
        with pytest.raises(ProviderError, match=message):
            load_registry(path)


def test_get_agent_names_the_known_ones_when_it_misses():
    assert get_agent("codex") == BUILTIN_AGENTS["codex"]
    with pytest.raises(UnknownAgentError, match="known: claude, codex, gemini"):
        get_agent("nope")


def test_importing_the_package_or_the_cli_loads_neither_library():
    code = (
        "import sys, hobbes.watterson.cli, hobbes.watterson.providers; "
        "from hobbes.watterson.providers import load_registry, AgentSpec, TextChunk; "
        "print(sorted(m for m in ('acp', 'any_llm') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


class TestAdaptersAnchor:
    """``ADAPTERS_DIR`` is found from the repo root, like ``tsextract/``."""

    def test_it_is_the_repo_roots_adapters_dir(self):
        assert ADAPTERS_DIR == REPO_ROOT / "adapters"
        assert (REPO_ROOT / "tsextract").is_dir() and (REPO_ROOT / "pipeline").is_dir()

    def test_it_pins_each_locked_adapter_exactly(self):
        manifest = json.loads((ADAPTERS_DIR / "package.json").read_text())
        assert (ADAPTERS_DIR / "package-lock.json").is_file()
        deps = manifest["dependencies"]
        assert sorted(deps) == sorted(a.package for a in LOCKED_ADAPTERS)
        for version in deps.values():
            assert re.fullmatch(r"\d+\.\d+\.\d+", version), version

    def test_bins_sit_under_node_modules_bin(self):
        for adapter in LOCKED_ADAPTERS:
            assert adapter_bin(adapter) == ADAPTERS_DIR / "node_modules" / ".bin" / adapter.bin
