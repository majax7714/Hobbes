"""Parallel implementers (ADR-063): the wave scheduler over the contract
DAG, the endpoint check that gates it, and the staged run under workers."""
from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hobbes.run import parallel
from tests.test_changespec import plan_repo  # noqa: F401
from tests.test_run import staged_session  # noqa: F401


def _serve(payload, status=200):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/v1"


class TestEndpointCheck:
    def test_vllm_batches_and_others_do_not(self):
        srv, url = _serve({"data": [{"id": "m", "owned_by": "vllm"}]})
        ok, reason = parallel.endpoint_batches(url, "k")
        srv.shutdown()
        assert ok and "vllm" in reason
        srv, url = _serve({"data": [{"id": "m", "owned_by": "llama.cpp"}]})
        ok, reason = parallel.endpoint_batches(url)
        srv.shutdown()
        assert not ok and "llama.cpp" in reason

    def test_no_answer_is_a_no_with_the_error_named(self):
        ok, reason = parallel.endpoint_batches("http://127.0.0.1:9/v1", timeout=2)
        assert not ok and "did not answer" in reason
        assert parallel.endpoint_batches("") == (False, "no endpoint: the runtime is not an OpenAI-compatible server")

    def test_resolve_workers(self):
        srv, url = _serve({"data": [{"id": "m", "owned_by": "vllm"}]})
        assert parallel.resolve_workers("auto", url)[0] == parallel.DEFAULT_WORKERS
        srv.shutdown()
        n, reason = parallel.resolve_workers("auto", "http://127.0.0.1:9/v1")
        assert n == 1 and "sequential" in reason
        assert parallel.resolve_workers(3, "")[0] == 3      # the owner's call, endpoint not asked
        assert parallel.resolve_workers("1", "")[0] == 1
        assert parallel.resolve_workers(0, "")[0] == 1


class TestWaves:
    def test_dependencies_and_readiness_follow_contract_ownership(self):
        spec = {"units": [{"name": "U1"}, {"name": "U2"}, {"name": "U3"}, {"name": "U4"}],
                "contracts": [{"owner": "U1", "from_unit": "U2", "to_unit": "U1"},   # U2 consumes U1
                              {"owner": "U2", "from_unit": "U3", "to_unit": "U2"}]}  # U3 consumes U2
        deps = parallel.unit_dependencies(spec)
        assert deps == {"U1": set(), "U2": {"U1"}, "U3": {"U2"}, "U4": set()}
        order = ["U1", "U2", "U3", "U4"]
        assert parallel.ready_units(order, set(), deps) == ["U1", "U4"]
        assert parallel.ready_units(["U2", "U3"], {"U1", "U4"}, deps) == ["U2"]
        assert parallel.ready_units(["U3"], {"U1", "U2", "U4"}, deps) == ["U3"]

    def test_a_cycle_leaves_nothing_ready_and_the_caller_forces_order(self):
        spec = {"units": [{"name": "A"}, {"name": "B"}],
                "contracts": [{"owner": "A", "from_unit": "B", "to_unit": "A"},
                              {"owner": "B", "from_unit": "A", "to_unit": "B"}]}
        deps = parallel.unit_dependencies(spec)
        assert parallel.ready_units(["A", "B"], set(), deps) == []


class TestStagedRunInParallel:
    def test_workers_change_the_clock_not_the_result(self, plan_repo, staged_session, tmp_path):  # noqa: F811
        from hobbes.run.stages import run_staged
        proposal = "improve app.core handle retry"
        seq = run_staged(plan_repo, proposal, session_bin=staged_session, sessions_root=tmp_path / "seq",
                         max_units=5, workers=1)
        seq_diff = subprocess.run(["git", "-C", str(plan_repo), "diff", "--stat", seq["base"],
                                   seq["integration"]["branch"]], capture_output=True, text=True).stdout
        par = run_staged(plan_repo, proposal, session_bin=staged_session, sessions_root=tmp_path / "par",
                         max_units=5, workers=3)
        par_diff = subprocess.run(["git", "-C", str(plan_repo), "diff", "--stat", par["base"],
                                   par["integration"]["branch"]], capture_output=True, text=True).stdout
        assert sorted(par["integration"]["merged"]) == sorted(seq["integration"]["merged"])
        assert par["integration"]["failed"] == [] and par_diff == seq_diff
        assert par["parallel"]["workers"] == 3 and seq["parallel"]["workers"] == 1
        # sequential = one unit per wave; parallel = every unit started
        # exactly once, and a consumer never in the same or an earlier
        # wave than its owner
        assert all(len(w) == 1 for w in seq["parallel"]["waves"])
        started = [u for w in par["parallel"]["waves"] for u in w]
        assert sorted(started) == sorted(u["unit"] for u in par["units"] if u["spawned"])
        deps = parallel.unit_dependencies(seq["spec"] if "spec" in seq else _spec(plan_repo, par["task"]))
        wave_of = {u: i for i, w in enumerate(par["parallel"]["waves"]) for u in w}
        for unit, owners in deps.items():
            for owner in owners:
                if unit in wave_of and owner in wave_of:
                    assert wave_of[owner] < wave_of[unit], (unit, owner, par["parallel"]["waves"])
        # the outside-measured stage clock exists and is no more than the units' sum
        units_sum = sum(u["wall_seconds"] or 0 for u in par["units"])
        assert par["implement_wall_seconds"] is not None and par["implement_wall_seconds"] <= units_sum + 1
        assert par["verify"]["verdict"] == "pass"


def _spec(repo, task):
    from hobbes.run.stages import artifacts_spec
    return artifacts_spec(repo, task)
