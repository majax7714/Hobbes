"""Lane B's languages at once, merged in the serial order (ADR-184 lever 3)."""

from __future__ import annotations

import threading
import time

import pytest

from hobbes.extract import _run_lane_b, containment, indexcache, jobs
from hobbes.extract.timings import Timings


def _run(name: str, delay: float, steps: int = 2, fail: Exception | None = None):
    """A language's run: it waits, then records *steps* ledger entries."""

    def run():
        time.sleep(delay)
        for i in range(steps):
            containment.record({"step": f"index-{name}", "unit": i, "contained": True})
        if fail is not None:
            raise fail
        return {"language": name, "thread": threading.current_thread().name}

    return run


@pytest.fixture
def ledger():
    containment.reset_ledger()
    yield containment.LEDGER
    containment.reset_ledger()


def _drain(runs, timings):
    """The caller's loop: each outcome taken in turn."""
    out = []
    for language, outcome in _run_lane_b(runs, timings):
        try:
            out.append((language, outcome()))
        except Exception as exc:  # noqa: BLE001 - the test inspects it
            out.append((language, exc))
    return out


def test_languages_that_finish_in_reverse_merge_in_the_serial_order(monkeypatch, ledger):
    monkeypatch.setenv(jobs.LANE_B_JOBS_ENV, "3")
    timings = Timings()
    # The first language is the slowest: run serially it would finish first.
    runs = [("python", _run("python", 0.30)), ("typescript", _run("typescript", 0.15)), ("go", _run("go", 0.0))]
    out = _drain(runs, timings)
    assert [language for language, _ in out] == ["python", "typescript", "go"]
    assert all(facts["thread"].startswith("lane-b") for _, facts in out), "they ran on threads"
    assert [(e["step"], e["unit"]) for e in ledger] == [
        ("index-python", 0), ("index-python", 1),
        ("index-typescript", 0), ("index-typescript", 1),
        ("index-go", 0), ("index-go", 1),
    ], "the artifact's containment steps are the serial run's"
    assert [s["step"] for s in timings.steps] == ["lane B [python]", "lane B [typescript]", "lane B [go]"]
    assert timings.steps[0]["seconds"] >= 0.29, "each language keeps its own time"


def test_a_run_that_raises_is_raised_at_its_own_turn(monkeypatch, ledger):
    monkeypatch.setenv(jobs.LANE_B_JOBS_ENV, "2")
    runs = [("python", _run("python", 0.0)), ("go", _run("go", 0.0, fail=RuntimeError("go broke"))),
            ("rust", _run("rust", 0.05))]
    out = _drain(runs, Timings())
    assert out[0][1]["language"] == "python"
    assert isinstance(out[1][1], RuntimeError) and str(out[1][1]) == "go broke"
    assert out[2][1]["language"] == "rust", "the others still stand"
    assert [e["step"] for e in ledger].count("index-go") == 2, "a failed run's steps are still recorded"


def test_one_job_is_the_serial_run(monkeypatch, ledger):
    monkeypatch.setenv(jobs.LANE_B_JOBS_ENV, "1")
    swept = []
    monkeypatch.setattr(indexcache, "sweep_now", lambda: swept.append(1))
    runs = [("python", _run("python", 0.0)), ("go", _run("go", 0.0))]
    out = _drain(runs, Timings())
    assert all(facts["thread"] == threading.current_thread().name for _, facts in out)
    assert swept == [], "no threads, so the sweep stays where it was"


def test_the_index_cache_is_swept_before_any_thread_starts(monkeypatch, ledger):
    monkeypatch.setenv(jobs.LANE_B_JOBS_ENV, "2")
    order: list[str] = []
    monkeypatch.setattr(indexcache, "sweep_now", lambda: order.append("sweep"))

    def run():
        order.append("run")
        return {}

    _drain([("python", run), ("go", run)], Timings())
    assert order[0] == "sweep" and order.count("run") == 2


def test_a_capture_keeps_a_threads_steps_apart(ledger):
    with containment.capture() as mine:
        containment.record({"step": "inside"})
    containment.record({"step": "outside"})
    assert mine == [{"step": "inside"}]
    assert ledger == [{"step": "outside"}]


def test_the_lane_b_default_is_a_bounded_quarter_of_the_cores(monkeypatch):
    monkeypatch.delenv(jobs.LANE_B_JOBS_ENV, raising=False)
    monkeypatch.setattr(jobs, "_cores", lambda: 12)
    assert jobs.lane_b_jobs() == 3
    monkeypatch.setattr(jobs, "_cores", lambda: 2)
    assert jobs.lane_b_jobs() == 1


def test_each_language_keeps_the_peaks_its_own_run_ended_with(monkeypatch, ledger):
    # Sampled on the thread as the run ends, not once for all at the merge.
    import hobbes.extract as extract

    monkeypatch.setenv(jobs.LANE_B_JOBS_ENV, "2")
    monkeypatch.setattr(extract, "peaks", lambda: {"peak_rss_mb": len(threading.current_thread().name),
                                                   "child_peak_rss_mb": 0, "ran_on": threading.current_thread().name})
    timings = Timings()
    _drain([("python", _run("python", 0.0)), ("go", _run("go", 0.05))], timings)
    assert all(s["ran_on"].startswith("lane-b") for s in timings.steps), "each sample was taken on its own thread"


def test_an_interrupt_starts_no_language_that_had_not_started(monkeypatch, ledger):
    # Ctrl-C lands on the main thread, waiting on a language's result.
    from concurrent.futures import Future

    monkeypatch.setenv(jobs.LANE_B_JOBS_ENV, "2")
    started: list[str] = []

    def run(name):
        def go():
            started.append(name)
            time.sleep(0.2)
            return {}
        return go

    def interrupted(self, timeout=None):
        raise KeyboardInterrupt

    monkeypatch.setattr(Future, "result", interrupted)
    with pytest.raises(KeyboardInterrupt):
        _drain([("python", run("python")), ("go", run("go")), ("rust", run("rust"))], Timings())
    time.sleep(0.4)
    assert "rust" not in started, "the queued language was cancelled"
