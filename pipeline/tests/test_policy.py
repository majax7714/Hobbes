"""Tests for hobbes.policy — the shell-out side of the ADR-003 contract."""

import pytest

from hobbes import policy
from tests.conftest import FAKE_RESOLUTION


class TestFindBinary:
    def test_env_var_wins(self, fake_policy_bin, monkeypatch):
        bin_path = fake_policy_bin(0, FAKE_RESOLUTION)
        monkeypatch.setenv(policy.BINARY_ENV_VAR, bin_path)
        assert policy.find_binary() == bin_path

    def test_env_var_pointing_nowhere_is_loud(self, monkeypatch, tmp_path):
        monkeypatch.setenv(policy.BINARY_ENV_VAR, str(tmp_path / "missing"))
        with pytest.raises(policy.PolicyBinaryNotFound, match="not an executable"):
            policy.find_binary()

    def test_not_found_explains_how_to_build(self, no_real_binary):
        with pytest.raises(policy.PolicyBinaryNotFound, match="go build"):
            policy.find_binary()


class TestResolve:
    @pytest.mark.parametrize(
        ("exit_code", "decision"),
        [(0, "allow"), (10, "deny"), (20, "escalate")],
    )
    def test_decision_exit_codes(self, fake_policy_bin, exit_code, decision):
        payload = dict(FAKE_RESOLUTION, decision=decision)
        res = policy.resolve("x", binary=fake_policy_bin(exit_code, payload))
        assert res.decision == decision
        assert res.exit_code == exit_code
        assert res.raw["decision"] == decision

    def test_non_decision_exit_raises(self, fake_policy_bin):
        with pytest.raises(policy.PolicyResolveError, match="exited 1"):
            policy.resolve("x", binary=fake_policy_bin(1, FAKE_RESOLUTION))

    def test_flags_passed_through(self, fake_policy_bin):
        res = policy.resolve(
            "git status",
            dir="/some/dir",
            repo="/some/repo",
            box="/some/box.policy",
            binary=fake_policy_bin(0),
        )
        argv = res.raw["argv"]
        assert "resolve" in argv
        assert "--repo /some/repo" in argv
        assert "--dir /some/dir" in argv
        assert "--box /some/box.policy" in argv
        assert argv.endswith("git status")

    def test_flags_omitted_when_unset(self, fake_policy_bin):
        res = policy.resolve("git status", binary=fake_policy_bin(0))
        assert "--repo" not in res.raw["argv"]
        assert "--dir" not in res.raw["argv"]
        assert "--box" not in res.raw["argv"]
