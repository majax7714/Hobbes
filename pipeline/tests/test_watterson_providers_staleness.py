"""Tests for the adapter staleness check (``hobbes agents --check``).

No network: the npm fetch and the user's ``--version`` calls are faked, and
the adapters root is a fake ``adapters/`` tree in tmp_path.
"""

from __future__ import annotations

import json
import urllib.error
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hobbes.watterson import cli
from hobbes.watterson.providers import registry, staleness
from hobbes.watterson.providers.registry import LOCKED_ADAPTERS, LockedAdapter
from hobbes.watterson.providers.staleness import Status, check_adapters, compare, exit_code

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
CLAUDE, CODEX = LOCKED_ADAPTERS


def packument(**ages: float | tuple[float, dict]) -> dict:
    """A registry document; each ``version=days_old`` (dots as underscores)."""
    versions, times = {}, {"created": "2020-01-01T00:00:00.000Z"}
    for name, age in ages.items():
        meta = {}
        if isinstance(age, tuple):
            age, meta = age
        version = name.lstrip("v").replace("_", ".", 2).replace("_", "-")
        versions[version] = {"version": version, **meta}
        times[version] = (NOW - timedelta(days=age)).isoformat().replace("+00:00", "Z")
    return {"versions": versions, "time": times}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def fake_adapters(
    root: Path,
    pins: dict[str, str],
    installed: dict[str, str] | None = None,
    harness: dict[str, dict] | None = None,
) -> Path:
    """An ``adapters/`` tree: package.json pins plus installed package.jsons."""
    write_json(root / "package.json", {"name": "x", "private": True, "dependencies": pins})
    for package, version in (pins if installed is None else installed).items():
        write_json(root / "node_modules" / package / "package.json", {"name": package, "version": version})
    for rel, data in (harness or {}).items():
        write_json(root / "node_modules" / rel / "package.json", data)
    return root


def no_cli(command: str) -> None:
    return None


def run(root: Path, docs: dict[str, dict], **kwargs):
    def fetch(package: str) -> dict:
        return docs[package]

    return check_adapters(root, fetch=fetch, now=NOW, cli=no_cli, **kwargs)


class TestCompare:
    def test_up_to_date(self):
        f = compare("pkg", "1.2.0", "1.2.0", packument(v1_1_0=30, v1_2_0=10), now=NOW)
        assert (f.status, f.latest, f.suggested, f.behind_by) == (Status.CURRENT, "1.2.0", None, None)
        assert f.latest_at == NOW - timedelta(days=10)
        assert exit_code([f]) == 0

    def test_bump_suggested_counts_releases_and_days(self):
        f = compare("pkg", "1.0.0", "1.0.0", packument(v1_0_0=40, v1_1_0=20, v1_2_0=10), now=NOW)
        assert (f.status, f.latest, f.suggested) == (Status.BUMP, "1.2.0", "1.2.0")
        assert f.behind_by == "2 stable releases, 30 days"
        assert exit_code([f]) == 1

    def test_cooldown_holds_back_a_fresh_release(self):
        doc = packument(v1_0_0=40, v1_1_0=5, v1_2_0=1.5)
        f = compare("pkg", "1.0.0", "1.0.0", doc, now=NOW)
        assert (f.status, f.latest, f.suggested) == (Status.BUMP, "1.2.0", "1.1.0")
        assert any("1.2.0" in n and "cooling down" in n for n in f.notes)
        assert not any("1.1.0" in n and "cooling down" in n for n in f.notes)

    def test_only_cooling_releases_is_not_actionable(self):
        f = compare("pkg", "1.1.0", "1.1.0", packument(v1_1_0=5, v1_2_0=1), now=NOW)
        assert (f.status, f.latest, f.suggested) == (Status.COOLING, "1.2.0", None)
        assert f.behind_by == "1 stable release, 4 days"
        assert exit_code([f]) == 0

    def test_the_cooldown_boundary_is_two_days(self):
        f = compare("pkg", "1.0.0", "1.0.0", packument(v1_0_0=9, v1_1_0=2), now=NOW)
        assert f.suggested == "1.1.0"

    def test_prereleases_and_deprecated_versions_are_ignored(self):
        doc = packument(
            v1_0_0=40,
            v1_1_0=20,
            v2_0_0_rc_1=10,
            v1_2_0=(8, {"deprecated": "broken"}),
        )
        assert "2.0.0-rc-1" in doc["versions"]
        f = compare("pkg", "1.1.0", "1.1.0", doc, now=NOW)
        assert (f.status, f.latest, f.suggested) == (Status.CURRENT, "1.1.0", None)

    def test_versions_compare_numerically_not_as_text(self):
        f = compare("pkg", "0.9.0", "0.9.0", packument(v0_9_0=30, v0_10_0=10), now=NOW)
        assert (f.latest, f.suggested) == ("0.10.0", "0.10.0")

    def test_pin_differs_from_installed(self):
        f = compare("pkg", "1.1.0", "1.0.0", packument(v1_0_0=40, v1_1_0=20), now=NOW)
        assert f.status == Status.MISMATCH
        assert any("installed 1.0.0 != pinned 1.1.0" in n and "npm ci" in n for n in f.notes)
        assert exit_code([f]) == 1

    def test_not_installed_is_a_mismatch(self):
        f = compare("pkg", "1.1.0", None, packument(v1_1_0=20), now=NOW)
        assert f.status == Status.MISMATCH
        assert any(n.startswith("not installed") and "cd adapters && npm ci" in n for n in f.notes)

    def test_offline_is_unknown_and_exit_code_2(self):
        f = compare("pkg", "1.1.0", "1.1.0", None, now=NOW, error="cannot reach npm")
        assert (f.status, f.latest, f.error) == (Status.UNKNOWN, None, "cannot reach npm")
        assert exit_code([f]) == 2

    def test_offline_still_reports_a_local_mismatch(self):
        f = compare("pkg", "1.1.0", "1.0.0", None, now=NOW, error="cannot reach npm")
        assert f.status == Status.MISMATCH
        assert exit_code([f]) == 2


class TestCheckAdapters:
    def test_reads_pins_and_installed_versions_from_the_adapters_root(self, tmp_path):
        root = fake_adapters(tmp_path, {CLAUDE.package: "0.90.0", CODEX.package: "2.2.2"})
        docs = {
            CLAUDE.package: packument(v0_90_0=4, v0_91_0=1, v0_92_0=0.2),
            CODEX.package: packument(v2_2_1=10, v2_2_2=6),
        }
        claude, codex = run(root, docs)
        assert (claude.freshness.pinned, claude.freshness.current) == ("0.90.0", "0.90.0")
        assert claude.freshness.status == Status.COOLING
        assert codex.freshness.status == Status.CURRENT
        assert exit_code(c.freshness for c in (claude, codex)) == 0

    def test_installed_mismatch_from_a_stale_node_modules(self, tmp_path):
        root = fake_adapters(
            tmp_path, {CODEX.package: "2.2.2"}, installed={CODEX.package: "2.2.1"}
        )
        (check,) = run(root, {CODEX.package: packument(v2_2_1=10, v2_2_2=6)}, adapters=[CODEX])
        assert check.freshness.status == Status.MISMATCH

    def test_offline_degrades_to_exit_2(self, tmp_path):
        root = fake_adapters(tmp_path, {CLAUDE.package: "0.90.0", CODEX.package: "2.2.2"})

        def offline(package: str) -> dict:
            raise urllib.error.URLError(OSError("Name or service not known"))

        checks = check_adapters(root, fetch=offline, now=NOW, cli=no_cli)
        assert all(c.freshness.status == Status.UNKNOWN for c in checks)
        assert "cannot reach npm" in checks[0].freshness.error
        assert "Name or service not known" in checks[0].freshness.error
        assert exit_code(c.freshness for c in checks) == 2

    def test_bundled_harness_versions_nested_or_hoisted(self, tmp_path):
        root = fake_adapters(
            tmp_path,
            {CLAUDE.package: "0.90.0", CODEX.package: "2.2.2"},
            harness={
                # claude-agent-acp's SDK nested under it; codex hoisted.
                f"{CLAUDE.package}/node_modules/{CLAUDE.harness}": {
                    "version": "0.3.296", "claudeCodeVersion": "2.1.296",
                },
                CODEX.harness: {"version": "0.160.1"},
            },
        )
        docs = {CLAUDE.package: packument(v0_90_0=4), CODEX.package: packument(v2_2_2=6)}
        versions = {"claude": "2.1.301 (Claude Code)"}
        checks = check_adapters(root, fetch=docs.__getitem__, now=NOW, cli=versions.get)
        claude, codex = (c.harness for c in checks)
        assert (claude.package, claude.bundled, claude.bundled_note) == (
            "@anthropic-ai/claude-agent-sdk", "0.3.296", "Claude Code 2.1.296",
        )
        assert claude.cli_version == "2.1.301 (Claude Code)"
        assert (codex.package, codex.bundled, codex.bundled_note) == ("@openai/codex", "0.160.1", None)
        assert codex.cli_version is None

    def test_a_missing_harness_reads_as_none(self, tmp_path):
        root = fake_adapters(tmp_path, {CODEX.package: "2.2.2"})
        (check,) = run(root, {CODEX.package: packument(v2_2_2=6)}, adapters=[CODEX])
        assert check.harness.bundled is None

    def test_a_missing_package_json_means_no_pin(self, tmp_path):
        adapter = LockedAdapter("x", "x-acp", "x-acp", "x-harness", "x")
        (check,) = run(tmp_path, {"x-acp": packument(v1_0_0=9)}, adapters=[adapter])
        assert check.freshness.status == Status.MISMATCH
        assert "no pin in adapters/package.json" in check.freshness.notes


def test_fetch_packument_quotes_the_scoped_name_and_maps_bad_json(monkeypatch):
    seen = {}

    class Reply:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, *args):
            return self.body

    def urlopen(request, timeout):
        seen.update(url=request.full_url, timeout=timeout)
        return Reply(seen.get("body", b'{"versions": {}}'))

    monkeypatch.setattr(staleness.urllib.request, "urlopen", urlopen)
    assert staleness.fetch_packument("@agentclientprotocol/codex-acp") == {"versions": {}}
    assert seen["url"] == "https://registry.npmjs.org/@agentclientprotocol%2Fcodex-acp"
    assert seen["timeout"] == staleness.FETCH_TIMEOUT
    seen["body"] = b"<html>"
    with pytest.raises(OSError, match="bad reply"):
        staleness.fetch_packument("x")


class TestCli:
    @pytest.fixture
    def adapters(self, tmp_path, monkeypatch):
        root = fake_adapters(
            tmp_path / "adapters",
            {CLAUDE.package: "0.90.0", CODEX.package: "2.2.2"},
            harness={CLAUDE.harness: {"version": "0.3.296", "claudeCodeVersion": "2.1.296"}},
        )
        monkeypatch.setattr(registry, "ADAPTERS_DIR", root)
        monkeypatch.setattr(staleness, "cli_version", lambda cmd: f"{cmd} 9.9.9")
        return root

    def test_reports_a_suggested_bump_and_exits_1(self, adapters, monkeypatch, capsys):
        docs = {
            CLAUDE.package: packument(v0_90_0=10, v0_91_0=5, v0_92_0=0.5),
            CODEX.package: packument(v2_2_2=6),
        }
        monkeypatch.setattr(staleness, "fetch_packument", docs.__getitem__)
        monkeypatch.setattr(staleness, "datetime", _FrozenDatetime)
        assert cli.main(["agents", "--check"]) == 1
        captured = capsys.readouterr()
        out = captured.out
        assert "pinned 0.90.0, installed 0.90.0: bump suggested" in out
        assert "latest stable 0.92.0 (published 2026-10-16); pin behind by 2 stable releases, 9 days" in out
        assert "suggested bump: 0.91.0 (newest stable past the 2-day cooldown)" in out
        assert "0.92.0 published 2026-10-16 is cooling down" in out
        assert "harness @anthropic-ai/claude-agent-sdk 0.3.296 (Claude Code 2.1.296); your claude: claude 9.9.9" in out
        assert "harness @openai/codex not installed; your codex: codex 9.9.9" in out
        assert "pinned 2.2.2, installed 2.2.2: up to date" in out
        assert "Bumps are manual" in captured.err

    def test_offline_exits_2_with_a_clear_message(self, adapters, monkeypatch, capsys):
        def offline(package: str) -> dict:
            raise TimeoutError("timed out")

        monkeypatch.setattr(staleness, "fetch_packument", offline)
        assert cli.main(["agents", "--check"]) == 2
        captured = capsys.readouterr()
        assert "pinned 0.90.0, installed 0.90.0: unknown" in captured.out
        assert "cannot reach npm for @agentclientprotocol/claude-agent-acp: timed out" in captured.out
        assert "npm registry unreachable" in captured.err
        assert "Traceback" not in captured.out + captured.err


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW
