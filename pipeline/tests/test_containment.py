"""Ingest containment (ADR-092): the planner, the refusal, the canary.

Three kinds of test, by what they need:

- **planner** — pure: the podman argv, the mounts, the profiles. No
  process runs.
- **routing** — the ingest driver's command plan sends every lane B
  spawn through the planner, and a refusal is never absorbed by the
  general catches (P10). ``containment.run`` is patched; nothing runs.
- **canary** (``lane_b``) — the negative "repo code never executes on the
  host" tested in the fixture culture: a crate whose build script tries
  to reach the host. Needs podman and the image; skips otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hobbes.extract import containment, scipsource, staging
from hobbes.extract.__init__ import _lane_b_facts

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cache(tmp_path, monkeypatch):
    root = tmp_path / "cache"
    root.mkdir()
    monkeypatch.setenv("HOBBES_CACHE_DIR", str(root))
    monkeypatch.delenv(containment.UNCONTAINED_ENV, raising=False)
    containment._availability.clear()
    return root.resolve()


class TestProfiles:
    """Stated once, so nobody re-derives what executes (ADR-092 §1)."""

    def test_every_helper_language_has_an_index_step(self):
        assert set(containment.INDEX_STEP) == {"python", "typescript", "go", "rust"}
        assert set(containment.INDEX_STEP.values()) <= set(containment.PROFILES)

    def test_every_index_step_has_no_network(self):
        for step in containment.INDEX_STEP.values():
            assert containment.PROFILES[step].network == "none", step

    def test_the_executing_set_is_rust_and_the_venv_listing(self):
        executing = {s for s, p in containment.PROFILES.items() if p.executes_repo_code}
        assert executing == {"index-rust", "python-env"}

    def test_fetch_steps_execute_nothing_and_are_the_only_networked_ones(self):
        networked = {s for s, p in containment.PROFILES.items() if p.network != "none"}
        assert networked == {"fetch-npm", "fetch-go", "fetch-rust"}
        assert not any(containment.PROFILES[s].executes_repo_code for s in networked)

    def test_cargo_fetch_pins_rustc_against_a_staged_config(self):
        cmd = containment.rust_fetch_command("/s/Cargo.toml")
        assert cmd[:2] == ["cargo", "fetch"]
        joined = " ".join(cmd)
        assert 'build.rustc="rustc"' in joined
        assert 'build.rustc-wrapper=""' in joined
        assert 'build.rustc-workspace-wrapper=""' in joined


class TestPlan:
    def test_argv_is_contained_offline_and_local(self, cache):
        plan = containment.plan("index-rust", ["node", "x"], cwd=cache / "stage")
        args = plan.podman_args()
        assert args[:2] == ["run", "--rm"]
        assert "--pull=never" in args
        assert args[args.index("--network") + 1] == "none"
        assert args[-2:] == [containment.DEFAULT_IMAGE, "node"] or args[-3:-1] == [containment.DEFAULT_IMAGE, "node"]
        assert "label=disable" in args
        assert "CARGO_NET_OFFLINE=true" in args

    def test_the_cache_root_is_the_one_rw_mount_at_its_host_path(self, cache):
        plan = containment.plan("index-python", ["node"], cwd=cache)
        mounts = plan.mounts()
        assert mounts[0] == f"{cache}:{cache}:rw"
        assert all(m.endswith(":ro") for m in mounts[1:])

    def test_the_helper_dir_is_always_mounted_ro(self, cache):
        plan = containment.plan("index-go", ["node"], cwd=cache)
        helper = str(containment.helper_dir())
        assert f"{helper}:{helper}:ro" in plan.mounts()

    def test_fetch_steps_get_the_default_network(self, cache):
        plan = containment.plan("fetch-rust", ["cargo", "fetch"], cwd=cache)
        args = plan.podman_args()
        assert args[args.index("--network") + 1] != "none"

    def test_tool_caches_live_under_the_cache_root(self, cache):
        plan = containment.plan("index-rust", ["node"], cwd=cache)
        args = " ".join(plan.podman_args())
        for var in ("CARGO_HOME", "GOMODCACHE", "GOCACHE", "npm_config_cache"):
            assert f"{var}={cache}/" in args
        assert f"HOME={cache}/home" in args
        assert "GOTOOLCHAIN=local" in args


class TestMountRoots:
    """Derived from the walk that placed the links, never authored."""

    def test_paths_under_the_cache_need_no_mount(self, cache):
        inner = cache / "npm" / "abc" / "node_modules"
        inner.mkdir(parents=True)
        assert containment.mount_roots([inner]) == ()

    def test_system_prefixes_are_never_mounted(self, cache):
        assert containment.mount_roots([Path("/usr/bin"), Path("/lib")]) == ()

    def test_a_nested_path_folds_into_its_parent(self, tmp_path, cache):
        outer = tmp_path / "repo" / "node_modules"
        inner = outer / "pkg" / "node_modules"
        inner.mkdir(parents=True)
        assert containment.mount_roots([inner, outer]) == (str(outer),)

    def test_a_path_through_a_directory_symlink_is_mounted_unresolved(self, tmp_path, cache):
        real = tmp_path / "pythons" / "cpython-3.12.13"
        real.mkdir(parents=True)
        alias = tmp_path / "pythons" / "cpython-3.12"
        alias.symlink_to(real)
        assert containment.mount_roots([alias]) == (str(alias),)

    def test_missing_paths_are_skipped(self, tmp_path, cache):
        assert containment.mount_roots([tmp_path / "nope"]) == ()

    def test_interpreter_mounts_follow_every_hop_and_skip_system_ones(self, tmp_path):
        install = tmp_path / "pythons" / "cpython-3.12"
        (install / "bin").mkdir(parents=True)
        (install / "bin" / "python3.12").write_text("")
        base_venv = tmp_path / "base" / ".venv"
        (base_venv / "bin").mkdir(parents=True)
        (base_venv / "bin" / "python").symlink_to(install / "bin" / "python3.12")
        venv = tmp_path / "repo" / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "python").symlink_to(base_venv / "bin" / "python")
        assert containment.interpreter_mounts(venv / "bin" / "python") == [
            str(base_venv), str(install),
        ]
        assert containment.interpreter_mounts(Path("/usr/bin/python3")) == []


class TestRun:
    """Contained when the box can; refused or disclosed otherwise."""

    def _unavailable(self, monkeypatch, why="podman is not installed"):
        monkeypatch.setattr(containment, "unavailable_reason", lambda: why)

    def _available(self, monkeypatch):
        monkeypatch.setattr(containment, "unavailable_reason", lambda: None)

    def test_contained_runs_go_through_podman(self, cache, monkeypatch):
        self._available(monkeypatch)
        seen = {}

        def fake(argv, **kw):
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, "{}", "")

        monkeypatch.setattr(containment.subprocess, "run", fake)
        plan = containment.plan("index-rust", ["node", "helper"], cwd=cache)
        out = containment.run(plan, timeout=5)
        assert out.contained and out.host_reason is None
        assert seen["argv"][0] == "podman" and seen["argv"][1] == "run"
        assert seen["argv"][-2:] == ["node", "helper"]

    def test_an_executing_step_refuses_without_containment(self, cache, monkeypatch):
        self._unavailable(monkeypatch)
        monkeypatch.setattr(
            containment.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran on the host")),
        )
        plan = containment.plan("index-rust", ["node"], cwd=cache)
        with pytest.raises(containment.ContainmentRefusal) as info:
            containment.run(plan, timeout=5)
        assert "never executes on the host" in str(info.value)
        assert "podman is not installed" in str(info.value)

    def test_a_non_executing_step_runs_on_the_host_and_says_so(self, cache, monkeypatch):
        self._unavailable(monkeypatch)
        seen = {}

        def fake(argv, **kw):
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(containment.subprocess, "run", fake)
        plan = containment.plan("index-typescript", ["node", "helper"], cwd=cache)
        out = containment.run(plan, timeout=5)
        assert not out.contained and "podman is not installed" in out.host_reason
        assert seen["argv"] == ["node", "helper"]
        record = containment.host_record(".", "scip-typescript", plan, out)
        assert record["stage"] == "scip-typescript"
        assert "ran on the host" in record["message"] and "C-64" in record["message"]

    def test_the_escape_hatch_runs_an_executing_step_on_the_host_disclosed(
        self, cache, monkeypatch
    ):
        self._available(monkeypatch)
        monkeypatch.setenv(containment.UNCONTAINED_ENV, "1")
        monkeypatch.setattr(
            containment.subprocess, "run",
            lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""),
        )
        plan = containment.plan("index-rust", ["node"], cwd=cache)
        out = containment.run(plan, timeout=5)
        assert not out.contained and "HOBBES_UNCONTAINED" in out.host_reason
        record = containment.host_record(".", "scip-rust", plan, out)
        assert "executes repo code" in record["message"]

    def test_a_contained_run_earns_no_record(self, cache, monkeypatch):
        self._available(monkeypatch)
        monkeypatch.setattr(
            containment.subprocess, "run",
            lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""),
        )
        plan = containment.plan("index-go", ["node"], cwd=cache)
        out = containment.run(plan, timeout=5)
        assert containment.host_record(".", "scip-go", plan, out) is None

    def test_podmans_own_failure_is_a_containment_error(self, cache, monkeypatch):
        self._available(monkeypatch)
        monkeypatch.setattr(
            containment.subprocess, "run",
            lambda argv, **kw: subprocess.CompletedProcess(argv, 125, "", "image not known"),
        )
        plan = containment.plan("index-go", ["node"], cwd=cache)
        with pytest.raises(containment.ContainmentError, match="image not known"):
            containment.run(plan, timeout=5)


class TestRouting:
    """The ingest driver's command plan routes every provider through the
    planner, so a regression is a red build, not a triage discovery."""

    FACTS = {
        "helper_version": scipsource.HELPER_VERSION,
        "definitions": [], "references": [], "external_refs": [],
        "packages": {}, "degraded": [],
        "dependency_coverage": {"declared": 0, "resolved": 0, "missing": []},
    }

    def _capture(self, monkeypatch):
        plans = []

        def run(plan, *, timeout):
            plans.append(plan)
            return containment.Outcome(
                subprocess.CompletedProcess(plan.command, 0, json.dumps(self.FACTS), ""),
                True,
            )

        monkeypatch.setattr(containment, "run", run)
        return plans

    def test_the_helper_runs_as_its_languages_index_step(self, cache, monkeypatch):
        plans = self._capture(monkeypatch)
        stage = cache / "stage" / "k"
        stage.mkdir(parents=True)
        for language in containment.INDEX_STEP:
            scipsource.run_helper(
                {"stage": str(stage), "language": language, "output": str(stage) + ".scip"}
            )
        assert [p.profile.step for p in plans] == [
            containment.INDEX_STEP[l] for l in containment.INDEX_STEP
        ]
        assert all(p.command[-2] == "--config" for p in plans)

    def test_a_link_target_rides_in_read_only(self, cache, monkeypatch, tmp_path):
        plans = self._capture(monkeypatch)
        tree = tmp_path / "repo" / "node_modules"
        tree.mkdir(parents=True)
        stage = cache / "stage" / "k"
        stage.mkdir(parents=True)
        scipsource.run_helper(
            {"stage": str(stage), "language": "typescript", "output": "o"},
            ro=[str(tree)],
        )
        assert f"{tree}:{tree}:ro" in plans[0].mounts()

    def test_a_cargo_root_fetches_then_indexes(self, cache, monkeypatch):
        plans = self._capture(monkeypatch)
        repo = cache.parent / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "Cargo.toml").write_text('[package]\nname="x"\nversion="0.1.0"\n')
        (repo / "src" / "lib.rs").write_text("")
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        scipsource.extract_scip_rust(repo, ["src/lib.rs"])
        assert [p.profile.step for p in plans] == ["fetch-rust", "index-rust"]
        assert plans[0].command[:2] == ("cargo", "fetch")

    def test_a_go_module_fetches_then_indexes(self, cache, monkeypatch):
        plans = self._capture(monkeypatch)
        repo = cache.parent / "repo"
        repo.mkdir()
        (repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n")
        (repo / "main.go").write_text("package main\n")
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        scipsource.extract_scip_go(repo, ["main.go"])
        assert [p.profile.step for p in plans] == ["fetch-go", "index-go"]

    def test_the_venv_listing_is_the_python_env_step(self, cache, monkeypatch, tmp_path):
        plans = []

        def run(plan, *, timeout):
            plans.append(plan)
            return containment.Outcome(
                subprocess.CompletedProcess(plan.command, 0, "[]", ""), True
            )

        monkeypatch.setattr(containment, "run", run)
        venv = tmp_path / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "python").write_text("")
        assert scipsource.venv_environment(str(tmp_path), ".venv") == []
        assert plans[0].profile.step == "python-env"
        assert plans[0].profile.executes_repo_code
        assert f"{venv}:{venv}:ro" in plans[0].mounts()


class TestRefusalIsNeverAbsorbed:
    """P10 (ADR-036): the general catches name the refusal first."""

    def test_the_refusal_is_not_a_unit_error(self):
        assert not issubclass(containment.ContainmentRefusal, scipsource.UNIT_ERRORS)
        assert not issubclass(containment.ContainmentRefusal, scipsource.ScipError)
        assert not issubclass(containment.ContainmentRefusal, OSError)

    def test_a_refused_cargo_root_stops_the_language_not_the_unit(self, monkeypatch, tmp_path):
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        monkeypatch.setattr(scipsource, "cargo_crates", lambda *a: {"": ["src/lib.rs"]})

        def refuse(*a, **k):
            raise containment.ContainmentRefusal("index-rust refused")

        monkeypatch.setattr(scipsource, "_index_cargo_root", refuse)
        with pytest.raises(containment.ContainmentRefusal):
            scipsource.extract_scip_rust(tmp_path, ["src/lib.rs"])

    def test_the_language_catch_records_the_refusal_by_name(self, monkeypatch, tmp_path):
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")

        def refuse(*a, **k):
            raise containment.ContainmentRefusal("index-rust refused: no podman")

        monkeypatch.setattr(scipsource, "extract_scip_rust", refuse)
        degraded: list[dict] = []
        facts = list(
            _lane_b_facts(tmp_path, [], None, None, {"files": [type("F", (), {"path": "a.rs"})()]}, degraded)
        )
        assert facts == []
        (record,) = degraded
        assert record["stage"] == "scip-rust"
        assert "refused" in record["message"] and "syntactic floor" in record["message"]
        assert "did not run" not in record["message"]


def _containment_available() -> str | None:
    containment._availability.clear()
    return containment.unavailable_reason()


@pytest.mark.lane_b
class TestCanary:
    """The negative, tested by canary: a build script that tries to reach
    the host. Real podman, real image, real rust-analyzer."""

    SECRET = Path("/tmp/hobbes-canary-secret")
    ESCAPED = Path("/tmp/hobbes-canary-escaped")

    def test_the_build_script_runs_and_reaches_nothing(self, tmp_path, monkeypatch):
        why = _containment_available()
        if why is not None:
            pytest.skip(f"containment unavailable here: {why}")
        monkeypatch.delenv(containment.UNCONTAINED_ENV, raising=False)
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        repo = tmp_path / "canary"
        shutil.copytree(FIXTURES / "canary-rust", repo)
        self.SECRET.write_text("planted\n")
        self.ESCAPED.unlink(missing_ok=True)
        try:
            facts = scipsource.extract_scip_rust(repo, ["build.rs", "src/lib.rs"])
        finally:
            self.SECRET.unlink(missing_ok=True)
        assert facts is not None
        monikers = [d["moniker"] for d in facts["definitions"]]
        # The script ran: the cfg it emits made `generated` real.
        assert any("generated()" in m for m in monikers), monikers
        # It could not read the planted secret, and its sentinel never
        # reached the host — it ran, and it ran contained.
        assert not any("leaked()" in m for m in monikers), monikers
        assert not self.ESCAPED.exists()
        # And no host-run disclosure was recorded.
        assert not any("ran on the host" in d["message"] for d in facts["degraded"])
