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
        assert set(containment.INDEX_STEP) == {"python", "typescript", "go", "rust", "java"}
        assert set(containment.INDEX_STEP.values()) <= set(containment.PROFILES)

    def test_every_index_step_has_no_network(self):
        # Java's index step lost its network with ADR-097: resolution
        # moved to `fetch-java`, over a stage without sources.
        for step in containment.INDEX_STEP.values():
            assert containment.PROFILES[step].network == "none", step

    def test_the_executing_set_is_rust_java_and_the_venv_listing(self):
        executing = {s for s, p in containment.PROFILES.items() if p.executes_repo_code}
        assert executing == {"index-rust", "index-java", "fetch-java", "python-env"}

    def test_java_resolve_is_the_only_executing_networked_step(self):
        # The one container that runs repo build logic *and* has a network
        # (C-66, narrowed by ADR-097). Named here so the set never widens
        # silently; what keeps it honest is that its stage holds no
        # sources — `test_a_java_unit_resolves_without_sources_then_indexes_offline`.
        networked = {s for s, p in containment.PROFILES.items() if p.network != "none"}
        assert networked == {"fetch-npm", "fetch-go", "fetch-rust", "fetch-java"}
        assert {s for s in networked if containment.PROFILES[s].executes_repo_code} == {"fetch-java"}

    def test_java_resolve_commands_and_offline_flags(self):
        maven = containment.java_resolve_command("maven", "/c/gradle/hobbes-resolve.gradle")
        assert maven == ["mvn", "--batch-mode", "-DskipTests", "clean", "test-compile"]
        gradle = containment.java_resolve_command("gradle", "/c/gradle/hobbes-resolve.gradle")
        assert gradle[:1] == ["./gradlew"] and "--init-script" in gradle and gradle[-1] == "hobbesResolveAll"
        assert "hobbesResolveAll" in containment.GRADLE_RESOLVE_SCRIPT
        assert "canBeResolved" in containment.GRADLE_RESOLVE_SCRIPT
        assert containment.java_index_offline_flags("maven") == ["-o"]
        assert containment.java_index_offline_flags("gradle") == ["--offline"]

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

    def test_a_java_unit_resolves_without_sources_then_indexes_offline(self, cache, monkeypatch):
        plans = self._capture(monkeypatch)
        repo = cache.parent / "repo"
        (repo / "src/main/java/a").mkdir(parents=True)
        (repo / "src/main/resources").mkdir(parents=True)
        (repo / "pom.xml").write_text("<project><groupId>g</groupId><artifactId>a</artifactId></project>")
        (repo / "src/main/java/a/A.java").write_text("package a; class A {}")
        (repo / "src/main/resources/app.properties").write_text("k=v\n")
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        staged: dict[str, list[str]] = {}
        real_build_stage = staging.build_stage

        def spy(repo_root, files, *a, **kw):
            stage = real_build_stage(repo_root, files, *a, **kw)
            staged[str(stage)] = list(files)
            return stage

        monkeypatch.setattr(staging, "build_stage", spy)
        scipsource.extract_scip_java(repo, ["src/main/java/a/A.java"])
        assert [p.profile.step for p in plans] == ["fetch-java", "index-java"]
        resolve, index = plans
        # The networked pass executes repo build logic over a stage with
        # no sources (C-66, ADR-097); the pass with the sources is offline.
        assert resolve.profile.executes_repo_code and resolve.profile.network == "default"
        assert index.profile.executes_repo_code and index.profile.network == "none"
        resolve_files = [f for s, f in staged.items() if resolve.cwd.startswith(s)]
        assert resolve_files and not any(f.endswith(".java") for f in resolve_files[0]), resolve_files
        assert "pom.xml" in resolve_files[0] and "src/main/resources/app.properties" in resolve_files[0]
        index_files = [f for s, f in staged.items() if index.cwd.startswith(s) or s in index.command[-1]]
        assert any("src/main/java/a/A.java" in f for f in index_files), staged
        assert resolve.command == ("mvn", "--batch-mode", "-DskipTests", "clean", "test-compile")
        args = resolve.podman_args()
        assert args[args.index("--network") + 1] == "pasta"
        assert index.podman_args()[index.podman_args().index("--network") + 1] == "none"
        env = " ".join(args)
        assert f"GRADLE_USER_HOME={cache}/gradle" in env and f"maven.repo.local={cache}/m2" in env
        assert (cache / "gradle" / "gradle.properties").read_text().startswith(
            "org.gradle.java.installations.paths=/usr/local/java-17,/usr/local/java-21,/usr/local/java-25"
        )
        assert (cache / "gradle" / "hobbes-resolve.gradle").read_text() == containment.GRADLE_RESOLVE_SCRIPT
        assert "JAVA_HOME=/usr/local/java-21" in env and "/usr/local/java-21/bin" in env
        assert "JAVA_HOME=/usr/local/java-21" in " ".join(index.podman_args())

    def test_a_gradle_unit_resolves_through_the_init_script(self, cache, monkeypatch):
        plans = self._capture(monkeypatch)
        repo = cache.parent / "repo"
        (repo / "src/main/java/a").mkdir(parents=True)
        (repo / "build.gradle").write_text("plugins { id 'java' }\n")
        (repo / "settings.gradle").write_text("rootProject.name = 'a'\n")
        (repo / "gradlew").write_text("#!/bin/sh\n")
        (repo / "src/main/java/a/A.java").write_text("package a; class A {}")
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        scipsource.extract_scip_java(repo, ["src/main/java/a/A.java"])
        assert [p.profile.step for p in plans] == ["fetch-java", "index-java"]
        resolve = plans[0]
        assert resolve.command[:1] == ("./gradlew",) and resolve.command[-1] == "hobbesResolveAll"
        assert str(cache / "gradle" / "hobbes-resolve.gradle") in resolve.command

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


class TestLedger:
    """What graph.json records: every step and where it ran (phase 3)."""

    def test_each_run_is_recorded_and_summarised(self, cache, monkeypatch):
        monkeypatch.setattr(containment, "unavailable_reason", lambda: None)
        monkeypatch.setattr(
            containment.subprocess, "run",
            lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""),
        )
        containment.reset_ledger()
        containment.run(containment.plan("index-go", ["node"], cwd=cache), timeout=5)
        monkeypatch.setenv(containment.UNCONTAINED_ENV, "1")
        containment.run(containment.plan("index-rust", ["node"], cwd=cache), timeout=5)
        s = containment.summary()
        assert [x["step"] for x in s["steps"]] == ["index-go", "index-rust"]
        assert s["steps"][0]["contained"] and not s["steps"][1]["contained"]
        assert "HOBBES_UNCONTAINED" in s["steps"][1]["reason"]
        assert s["all_contained"] is False and s["escape_hatch"] is True
        containment.reset_ledger()
        assert containment.summary()["steps"] == []


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
            _lane_b_facts(tmp_path, [], None, None, {"files": [type("F", (), {"path": "a.rs"})()]}, None, degraded)
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


@pytest.mark.lane_b
class TestJavaCanary:
    """The Java negative (ADR-096, ADR-097): a Maven build step that tries
    to reach the host, and one that phones home only if it can see both
    the sources and the network. Real podman, real image, real scip-java.
    The resolve pass has a network and no sources; the index pass has the
    sources and no network — so `Phoned` must never be indexed."""

    SECRET = Path("/tmp/hobbes-canary-secret")
    ESCAPED = Path("/tmp/hobbes-canary-escaped")

    def test_the_build_runs_and_reaches_nothing(self, tmp_path, monkeypatch):
        why = _containment_available()
        if why is not None:
            pytest.skip(f"containment unavailable here: {why}")
        monkeypatch.delenv(containment.UNCONTAINED_ENV, raising=False)
        monkeypatch.setenv(scipsource.SCIP_ENABLE_ENV, "1")
        repo = tmp_path / "canary"
        shutil.copytree(FIXTURES / "canary-java", repo)
        self.SECRET.write_text("planted\n")
        self.ESCAPED.unlink(missing_ok=True)
        containment.reset_ledger()
        try:
            facts = scipsource.extract_scip_java(repo, ["src/main/java/canary/Canary.java"])
        finally:
            self.SECRET.unlink(missing_ok=True)
        assert facts is not None, facts
        monikers = [d["moniker"] for d in facts["definitions"]]
        assert any("canary/Canary#" in m for m in monikers), (monikers, facts["degraded"])
        assert not any("Leaked#" in m for m in monikers), monikers
        # No pass saw sources and network together (ADR-097's property).
        assert not any("Phoned#" in m for m in monikers), monikers
        assert not self.ESCAPED.exists()
        assert not any("ran on the host" in d["message"] for d in facts["degraded"])
        assert not any("resolution failed" in d["message"] for d in facts["degraded"]), facts["degraded"]
        assert [s["step"] for s in containment.LEDGER] == ["fetch-java", "index-java"]
        assert all(s["contained"] for s in containment.LEDGER)
