"""Where code may run: the container check, its refusal, and the plan that puts this package in an image."""

from pathlib import Path

import pytest

from lattice import run

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


def test_the_markers_are_the_ones_a_container_leaves():
    assert run.MARKERS == ("/run/.containerenv", "/.dockerenv")


def test_uncontained_execution_is_refused(monkeypatch):
    monkeypatch.setattr(run, "in_container", lambda: False)
    with pytest.raises(run.NotContained) as refusal:
        run.require_container()
    assert "never happens on the host" in str(refusal.value)
    assert "ADR-092" in str(refusal.value)


def test_the_refusal_is_its_own_type():
    # P10 (ADR-036): a general handler must not be able to absorb it.
    assert not issubclass(run.NotContained, (OSError, RuntimeError, ValueError))


def test_a_package_test_may_run_on_its_own_fixture(monkeypatch):
    monkeypatch.setattr(run, "in_container", lambda: False)
    run.require_container(allow_host=True)  # does not raise


def test_inside_a_container_nothing_is_refused(monkeypatch):
    monkeypatch.setattr(run, "in_container", lambda: True)
    run.require_container()  # does not raise


def test_the_plan_is_the_argv_and_nothing_runs(tmp_path):
    plan = run.image_plan("hobbes-session:local", FIXTURE, tmp_path, ["grade", "/target", "/work/manifest.json"])
    assert plan == [
        "podman", "run", "--rm",
        "--network", "none",
        "--security-opt", "label=disable",
        "-v", f"{FIXTURE.resolve()}:/target:ro",
        "-v", f"{tmp_path.resolve()}:/work:rw",
        "-v", f"{run.package_src()}:/lattice:ro",
        "--env", "PYTHONPATH=/lattice",
        "--workdir", "/work",
        "hobbes-session:local",
        "python3", "-m", "lattice.cli", "grade", "/target", "/work/manifest.json", "--here",
    ]


def test_the_plan_mounts_this_package_and_not_the_images(tmp_path):
    assert (run.package_src() / "lattice" / "grade.py").exists()
    plan = run.image_plan(run.IMAGE, FIXTURE, tmp_path, ["selftest", "/target"])
    assert f"{run.package_src()}:/lattice:ro" in plan
    assert plan[plan.index("--env") + 1] == "PYTHONPATH=/lattice"
    assert plan[-1] == "--here"


def test_the_target_rides_read_only_and_the_work_dir_does_not(tmp_path):
    plan = run.image_plan(run.IMAGE, FIXTURE, tmp_path, ["selftest", "/target"])
    mounts = [plan[i + 1] for i, arg in enumerate(plan) if arg == "-v"]
    assert [m.rsplit(":", 1)[1] for m in mounts] == ["ro", "rw", "ro"]
