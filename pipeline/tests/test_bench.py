"""The benchmark harness — `hobbes bench` (ADR-055).

Quota-free and network-free: a local "GitHub" (HOBBES_BENCH_GIT_BASE
pointed at a temp dir), a fake `claude` that edits a file and prints a
result envelope, the ADR-054 stand-in session, and a fake evaluator
that writes a report in swebench's shape. What is tested is the
machinery around the arms — the protocol, the checkouts, the patches,
the meters, the verdict plumbing, the records and the report — never
a model's answer.
"""

import json
import os
import pathlib
import stat
import subprocess

import pytest

from hobbes import cli
from hobbes.bench import accounting, arms, instances, results, verdict, workspace
from hobbes.bench import run as bench_run
from tests.test_run import FAKE_SESSION, STAGED_SESSION


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


GOLD = """\
diff --git a/src/app/core.py b/src/app/core.py
--- a/src/app/core.py
+++ b/src/app/core.py
@@ -1 +1 @@
-x
+y
diff --git a/src/app/api.py b/src/app/api.py
--- a/src/app/api.py
+++ b/src/app/api.py
"""


def row(iid="acme__app-1", **over):
    base = {
        "instance_id": iid, "repo": "acme/app", "base_commit": "deadbeef",
        "problem_statement": "handle() returns None when the retry budget is exhausted",
        "patch": GOLD, "test_patch": "", "created_at": "2026-03-01T00:00:00Z",
        "version": "1.0", "FAIL_TO_PASS": '["tests/test_core.py::test_handle"]',
        "PASS_TO_PASS": [], "hints_text": "",
    }
    base.update(over)
    return base


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    """A local 'GitHub': acme/app is a committed python repo with a
    handle() in src/app/core.py; the harness clones it by owner/name."""
    base = tmp_path / "github"
    repo = base / "acme" / "app"
    (repo / "src" / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "app" / "core.py").write_text(
        "def handle(n):\n    return retry(n)\n\n\ndef retry(n):\n    return n\n")
    (repo / "src" / "app" / "api.py").write_text("from app.core import handle\n\n\ndef serve():\n    return handle(1)\n")
    (repo / "tests" / "test_core.py").write_text("from app.core import handle\n\n\ndef test_handle():\n    assert handle(1) == 1\n")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    sha = git(repo, "rev-parse", "HEAD")
    monkeypatch.setenv(workspace.GIT_BASE_ENV, str(base) + "/")
    monkeypatch.setenv(workspace.CACHE_ENV, str(tmp_path / "cache"))
    return repo, sha


@pytest.fixture
def instance(upstream):
    _, sha = upstream
    return instances.parse_instance(row(base_commit=sha))


FAKE_CLAUDE = """\
#!/bin/sh
# A pure-arm stand-in: edits the file the issue is about and prints a
# Claude Code result envelope with usage.
echo "# fixed by fake claude" >> src/app/core.py
cat <<'EOT'
{"type":"result","subtype":"success","is_error":false,"duration_ms":1500,"num_turns":3,"result":"done","total_cost_usd":0.0123,"usage":{"input_tokens":1000,"output_tokens":200,"cache_creation_input_tokens":50,"cache_read_input_tokens":25}}
EOT
"""

FAKE_EVALUATOR = """\
#!/bin/sh
# Writes <model_name>.<run_id>.json the way swebench.harness.run_evaluation
# does: every prediction whose patch mentions core.py is resolved.
preds=""; run=""; ids=""
while [ $# -gt 0 ]; do
  case "$1" in
    --predictions_path) preds="$2"; shift 2;;
    --run_id) run="$2"; shift 2;;
    *) shift;;
  esac
done
python3 - "$preds" "$run" <<'EOT'
import json, sys
preds = json.load(open(sys.argv[1]))
name = preds[0]["model_name_or_path"]
resolved = [p["instance_id"] for p in preds if "core.py" in p["model_patch"]]
empty = [p["instance_id"] for p in preds if not p["model_patch"].strip()]
other = [p["instance_id"] for p in preds if p["instance_id"] not in resolved + empty]
json.dump({"resolved_ids": resolved, "unresolved_ids": other, "error_ids": [],
           "empty_patch_ids": empty, "completed_ids": [p["instance_id"] for p in preds]},
          open(f"{name}.{sys.argv[2]}.json", "w"))
EOT
"""


def _script(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    path = _script(tmp_path / "claude", FAKE_CLAUDE)
    monkeypatch.setenv("HOBBES_CLAUDE_BIN", path)
    return path


@pytest.fixture
def fake_session(tmp_path):
    return _script(tmp_path / "hobbes-session", FAKE_SESSION)


@pytest.fixture
def staged_session(tmp_path):
    return _script(tmp_path / "hobbes-session-staged", STAGED_SESSION)


@pytest.fixture
def fake_evaluator(tmp_path, monkeypatch):
    path = _script(tmp_path / "swebench-eval", FAKE_EVALUATOR)
    monkeypatch.setenv(verdict.CMD_ENV, path)
    return path


class TestInstances:
    def test_parse_accepts_string_and_list_test_fields(self):
        inst = instances.parse_instance(row())
        assert inst.fail_to_pass == ["tests/test_core.py::test_handle"]
        assert inst.pass_to_pass == []
        assert instances.parse_instance(row(FAIL_TO_PASS=["a", "b"])).fail_to_pass == ["a", "b"]

    def test_missing_required_field_is_an_error(self):
        with pytest.raises(instances.InstanceError, match="lacks base_commit"):
            instances.parse_instance(row(base_commit=""))

    def test_depth_is_the_gold_patch_file_count(self):
        inst = instances.parse_instance(row())
        assert inst.gold_files == ["src/app/api.py", "src/app/core.py"]
        assert inst.depth == 2 and inst.depth_bucket == "2-3 files"
        assert instances.depth_bucket(1) == "1 file"
        assert instances.depth_bucket(7) == "4+ files"
        assert instances.parse_instance(row(patch="")).depth_bucket.startswith("0 files")

    def test_load_jsonl_and_json_array(self, tmp_path):
        jl = tmp_path / "i.jsonl"
        jl.write_text(json.dumps(row("a")) + "\n\n" + json.dumps(row("b")) + "\n")
        assert [i.instance_id for i in instances.load_instances(jl)] == ["a", "b"]
        arr = tmp_path / "i.json"
        arr.write_text(json.dumps([row("c")]))
        assert [i.instance_id for i in instances.load_instances(arr)] == ["c"]

    def test_protocol_counts_every_drop(self):
        rows = [
            instances.parse_instance(row("old", created_at="2024-01-01T00:00:00Z")),
            instances.parse_instance(row("undated", created_at="")),
            instances.parse_instance(row("other", repo="x/y")),
            instances.parse_instance(row("new1", created_at="2026-02-01T00:00:00Z")),
            instances.parse_instance(row("new2", created_at="2026-03-01T00:00:00Z")),
        ]
        sel = instances.select(rows, source="f", cutoff="2025-06-01", repos=["acme/app"], limit=1)
        assert [i.instance_id for i in sel.selected] == ["new1"]
        assert sel.dropped == {"before_cutoff": 1, "undated": 1, "repo": 1, "limit": 1}
        assert sel.created_range == ("2026-02-01T00:00:00Z", "2026-02-01T00:00:00Z")
        doc = sel.to_dict()
        assert "C-39" in doc["contamination"] and "proxy" in doc["depth"]
        text = instances.format_selection(sel)
        assert "cutoff: created after 2025-06-01" in text and "dropped:" in text

    def test_no_cutoff_is_said_out_loud(self):
        sel = instances.select([instances.parse_instance(row())])
        assert "every instance may be in a model's training data" in instances.format_selection(sel)


class TestWorkspace:
    def test_checkout_mirrors_once_and_pins_the_base_commit(self, upstream, instance, tmp_path):
        ws = workspace.checkout(instance, tmp_path / "ws")
        assert git(ws, "rev-parse", "HEAD") == instance.base_commit
        assert git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "bench/base"
        mirror = workspace.mirror(instance.repo)
        assert mirror.is_dir() and mirror.name == "acme__app.git"
        # a second checkout reuses the mirror and replaces the dir
        (ws / "junk").write_text("x")
        workspace.checkout(instance, ws)
        assert not (ws / "junk").exists()

    def test_unknown_commit_is_a_clear_error(self, upstream, tmp_path):
        bad = instances.parse_instance(row(base_commit="0" * 40))
        with pytest.raises(workspace.WorkspaceError, match="no commit"):
            workspace.checkout(bad, tmp_path / "ws")

    def test_candidate_patch_covers_tree_and_branch_and_excludes_hobbes(self, upstream, instance, tmp_path):
        ws = workspace.checkout(instance, tmp_path / "ws")
        (ws / "src" / "app" / "core.py").write_text("changed\n")
        (ws / "new.py").write_text("new\n")
        (ws / ".hobbes").mkdir()
        (ws / ".hobbes" / "x.json").write_text("{}")
        patch = workspace.candidate_patch(ws, instance.base_commit)
        assert "a/src/app/core.py" in patch and "b/new.py" in patch and ".hobbes" not in patch
        git(ws, "checkout", "-q", "-b", "hobbes/x")
        git(ws, "commit", "-qam", "c")
        by_ref = workspace.candidate_patch(ws, instance.base_commit, ref="hobbes/x")
        assert "a/src/app/core.py" in by_ref


class TestAccounting:
    ENVELOPE = {"type": "result", "duration_ms": 2000, "num_turns": 4, "total_cost_usd": 0.5,
                "usage": {"input_tokens": 10, "output_tokens": 5,
                          "cache_creation_input_tokens": 1, "cache_read_input_tokens": 2}}

    def test_from_envelope_and_totals(self):
        u = accounting.from_envelope(self.ENVELOPE)
        assert u.total_tokens == 18 and u.cost_usd == 0.5 and u.wall_seconds == 2.0 and u.turns == 4
        assert u.unobserved == []

    def test_find_envelope_among_other_lines(self):
        text = "hobbes-session: starting\n" + json.dumps(self.ENVELOPE) + "\nhobbes-session: harvested\n"
        assert accounting.from_text(text).total_tokens == 18
        assert accounting.from_text("no envelope here").unobserved == ["tokens", "cost", "wall_time"]

    def test_sum_keeps_unobserved_unobserved(self):
        a = accounting.from_envelope(self.ENVELOPE)
        b = accounting.from_envelope({"type": "result", "usage": {"input_tokens": 1, "output_tokens": 1}})
        s = a.add(b)
        assert s.total_tokens == 20 and s.envelopes == 2
        assert s.cost_usd is None and "cost" in s.unobserved  # b never reported cost
        assert a.add(accounting.Usage()).total_tokens == 18  # an empty meter adds nothing


class TestPureArm:
    def test_patch_and_meter_from_the_envelope(self, upstream, instance, fake_claude, tmp_path):
        ws = workspace.checkout(instance, tmp_path / "ws")
        result = arms.run_pure_arm(instance, ws, "m")
        assert result.outcome == "patch" and result.patch_files == ["src/app/core.py"]
        assert result.usage.total_tokens == 1275 and result.usage.cost_usd == 0.0123
        assert result.usage.turns == 3 and result.usage.unobserved == []
        assert (ws / ".hobbes" / "pure-arm.log").is_file()

    def test_missing_binary_is_a_claude_error(self, upstream, instance, tmp_path, monkeypatch):
        monkeypatch.setenv("HOBBES_CLAUDE_BIN", str(tmp_path / "nope"))
        ws = workspace.checkout(instance, tmp_path / "ws")
        result = arms.run_pure_arm(instance, ws, "m")
        assert result.outcome == "claude-error" and "not found" in result.error

    def test_prompt_is_the_issue_plus_the_protocol(self, instance):
        prompt = arms.pure_prompt(instance)
        assert instance.problem_statement in prompt and "Do not commit" in prompt


class TestHarnessArm:
    def test_ingest_plan_run_patch(self, upstream, instance, fake_session, tmp_path):
        ws = workspace.checkout(instance, tmp_path / "ws")
        result = arms.run_harness_arm(instance, ws, "m", session_bin=fake_session,
                                      sessions_root=tmp_path / "sessions")
        assert result.outcome == "patch", result.error
        assert result.detail["ingest"]["languages"] == ["python"]
        plan = result.detail["plan"]
        assert "app.core" in plan["seeds"].values() or any("core" in s for s in plan["seeds"])
        assert plan["units"] >= 1 and plan["gate"] == "pass"
        run = result.detail["run"]
        assert run["units"][0]["context_faults"] == 1 and run["units"][0]["rework_files"] == ["src/stray.py"]
        assert "src/app/core.py" in result.patch and "src/stray.py" in result.patch
        # the stand-in session emits no envelope: tokens unobserved, wall time observed from outside
        assert "tokens" in result.usage.unobserved and result.usage.wall_seconds is not None
        # the model reached hobbes-session
        session = run["units"][0]["unit"]
        argv = (tmp_path / "sessions" / f"{plan['task']}-{session.lower()}" / "argv.txt").read_text()
        assert argv  # the stand-in recorded its agent dir

    def test_prose_only_issue_is_a_no_seed_outcome(self, upstream, fake_session, tmp_path):
        _, sha = upstream
        inst = instances.parse_instance(row(base_commit=sha, problem_statement=(
            "The checkout flow forgets the coupon when a customer goes back")))
        ws = workspace.checkout(inst, tmp_path / "ws")
        result = arms.run_harness_arm(inst, ws, "m", session_bin=fake_session, sessions_root=tmp_path / "s")
        assert result.outcome == "no-seed" and result.patch == ""
        assert "--seed" in result.error

    def test_staged_arm_meters_every_stage_and_scores_the_planner_post_hoc(self, upstream, instance,
                                                                            staged_session, tmp_path):
        # phase 3 of the harness restructure: the adapter over the stage loop
        ws = workspace.checkout(instance, tmp_path / "ws")
        result = arms.run_harness_arm(instance, ws, "m", session_bin=staged_session,
                                      sessions_root=tmp_path / "s", stages=("plan", "implement", "verify"))
        assert result.outcome == "patch", result.error
        assert result.detail["seed_source"] == "planner"
        stages = result.detail["stages"]
        assert [s["stage"] for s in stages][:1] == ["plan"] and stages[-1]["stage"] == "verify"
        assert any(s["stage"] == "implement" for s in stages)
        # every stage carries a wall time measured from outside; the arm's is
        # the sum of the stage clocks — implement's being the outside clock
        # over the whole stage (ADR-063), never less than its units' sum
        assert all(s["wall_seconds"] is not None for s in stages)
        stage_wall = result.detail["run"]["stage_wall"]
        assert stage_wall["implement"] >= stage_wall["implement_units_sum"]
        assert stage_wall["implement_units_sum"] == pytest.approx(
            sum(s["wall_seconds"] for s in stages if s["stage"] == "implement"), abs=0.01)
        assert result.usage.wall_seconds == pytest.approx(
            sum(v for k, v in stage_wall.items() if k != "implement_units_sum"), abs=0.01)
        assert set(stage_wall) == {"plan", "implement", "implement_units_sum", "verify"}
        # the planner's session log exists and was read (no envelope in the stand-in: tokens unobserved)
        planner_log = ws / ".hobbes" / "plans" / result.detail["plan"]["task"] / "agents" / "planner" / "session.log"
        assert planner_log.is_file() and "session planner done" in planner_log.read_text()
        assert "tokens" in result.usage.unobserved
        # the planner's named paths are structural, not prose
        assert result.detail["planner"]["paths"] == ["src/app/core.py"]
        assert "hit" not in result.detail["planner"]  # the arm never scores itself
        # the record scores it against the gold patch, after the fact
        record = results.make_record(instance, result)
        planner = record.detail["planner"]
        assert planner["hit"] is True and planner["hit_files"] == ["src/app/core.py"]
        assert planner["gold"] == 2 and planner["hits"] == 1 and planner["recall"] == 0.5

    def test_not_a_repo_is_an_ingest_error(self, tmp_path, instance):
        result = arms.run_harness_arm(instance, tmp_path / "empty", "m")
        assert result.outcome == "ingest-error"


class TestVerdict:
    def test_docker_host_env_respects_an_explicit_setting_and_finds_the_socket(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DOCKER_HOST", "unix:///custom.sock")
        assert verdict.docker_host_env()["DOCKER_HOST"] == "unix:///custom.sock"
        monkeypatch.delenv("DOCKER_HOST", raising=False)
        sock = tmp_path / "podman" / "podman.sock"; sock.parent.mkdir(); sock.touch()
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        assert verdict.docker_host_env()["DOCKER_HOST"] == f"unix://{sock}"

    def test_a_dataset_file_is_made_absolute_for_the_evaluator(self, tmp_path, monkeypatch):
        # the evaluator runs from run_dir/eval; a relative dataset file
        # would not resolve there (the first full-stage run's judge died
        # on `../verified.jsonl` after producing every patch)
        monkeypatch.delenv(verdict.CMD_ENV, raising=False)
        ds = tmp_path / "verified.jsonl"; ds.write_text("{}\n")
        monkeypatch.chdir(tmp_path)
        cmd = verdict.evaluator_command("verified.jsonl", tmp_path / "p.json", "run", ["i-1"])
        i = cmd.index("--dataset_name")
        assert cmd[i + 1] == str(ds.resolve()) and os.path.isabs(cmd[i + 1])
        # a HF dataset name (not a file) is left as-is
        cmd2 = verdict.evaluator_command("princeton-nlp/SWE-bench_Verified", tmp_path / "p.json", "run", ["i-1"])
        assert cmd2[cmd2.index("--dataset_name") + 1] == "princeton-nlp/SWE-bench_Verified"

    def test_default_command_is_the_pinned_evaluator(self, monkeypatch, tmp_path):
        monkeypatch.delenv(verdict.CMD_ENV, raising=False)
        cmd = verdict.evaluator_command("ds", tmp_path / "p.json", "r1", ["a", "b"])
        assert f"swebench=={verdict.SWEBENCH_VERSION}" in cmd
        assert cmd[-4:] == ["--instance_ids", "a", "b"] or cmd[-3:] == ["--instance_ids", "a", "b"]
        assert "--dataset_name" in cmd and "--run_id" in cmd

    def test_evaluate_reads_the_report(self, fake_evaluator, tmp_path):
        preds = verdict.write_predictions(tmp_path / "p.json", [
            {"instance_id": "a", "model_name_or_path": "hobbes-pure-m", "model_patch": "diff core.py"},
            {"instance_id": "b", "model_name_or_path": "hobbes-pure-m", "model_patch": ""},
            {"instance_id": "c", "model_name_or_path": "hobbes-pure-m", "model_patch": "diff other"},
        ])
        out = verdict.evaluate("ds", preds, "r1", "hobbes-pure-m", ["a", "b", "c", "d"], cwd=tmp_path / "eval")
        assert out == {"a": "resolved", "b": "empty-patch", "c": "unresolved", "d": "unjudged"}
        assert (tmp_path / "eval" / "hobbes-pure-m.r1.log").is_file()

    def test_no_report_is_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv(verdict.CMD_ENV, "true")
        with pytest.raises(verdict.VerdictError, match="no report"):
            verdict.evaluate("ds", tmp_path / "p.json", "r", "n", ["a"], cwd=tmp_path / "e")

    def test_model_name_is_per_arm_and_model(self):
        assert verdict.model_name("harness", "claude-opus-5") == "hobbes-harness-claude-opus-5"
        assert verdict.model_name("pure", "") == "hobbes-pure-default"


def _rec(iid, arm, model, verdict_, depth=1, tokens=100, cost=1.0):
    usage = accounting.Usage(input_tokens=tokens, output_tokens=0, cost_usd=cost, wall_seconds=1.0, envelopes=1) \
        if tokens is not None else accounting.Usage()
    return results.Record(instance_id=iid, repo="r", created_at="", depth=depth,
                          depth_bucket=instances.depth_bucket(depth), arm=arm, model=model,
                          outcome="patch", patch_bytes=1, patch_files=["f"], usage=usage.to_dict(),
                          verdict=verdict_)


class TestReport:
    def test_h1_gap_closed_h2_slope_h3_per_solved(self):
        recs = [
            # small model: pure 1/4, harness 3/4; large pure 3/4 → gap closed 100%
            *[_rec(f"i{n}", "pure", "small", "resolved" if n == 0 else "unresolved", depth=n + 1) for n in range(4)],
            *[_rec(f"i{n}", "harness", "small", "resolved" if n < 3 else "unresolved", depth=n + 1,
                   tokens=None if n == 0 else 50) for n in range(4)],
            *[_rec(f"i{n}", "pure", "large", "resolved" if n < 3 else "unresolved", depth=n + 1) for n in range(4)],
            _rec("unjudged", "pure", "small", None),
        ]
        doc = results.report(recs)
        assert doc["unjudged"] == 1
        small = doc["H1"]["small"]
        assert small["pure"]["rate"] == 0.25 and small["harness"]["rate"] == 0.75
        assert small["gap_closed_vs"] == "large" and small["gap_closed"] == 1.0
        assert doc["H1"]["large"]["harness"]["rate"] is None
        assert doc["H2"]["pure/small"]["slope"] == -1.0  # 1 file 100% → 4+ 0%
        h3 = doc["H3"]["harness/small"]
        assert h3["solved"] == 3 and h3["tokens"]["observed"] == 2 and h3["tokens"]["unobserved"] == 1
        text = results.format_report(doc)
        assert "gap closed" in text and "1 unobserved" in text and "C-39" in text

    def test_planner_hit_is_a_suffix_match_and_states_counts(self):
        hit = results.planner_hit(["app/core.py", "nothing.py"], ["src/app/core.py", "src/app/api.py"])
        assert hit["hit"] and hit["hit_files"] == ["src/app/core.py"] and hit["recall"] == 0.5
        assert hit["named"] == 2
        assert results.planner_hit([], ["a.py"])["hit"] is False
        assert results.planner_hit(["a.py"], [])["recall"] is None

    def test_report_splits_the_staged_harness_by_seed_source(self):
        def staged(iid, source, verdict_, hit, gold=2):
            r = _rec(iid, "harness", "small", verdict_)
            r.detail = {"seed_source": source,
                        "planner": {"gold": gold, "hit": hit, "hits": 1 if hit else 0,
                                    "recall": 0.5 if hit else 0.0}}
            return r
        recs = [
            staged("a", "planner", "resolved", True), staged("b", "planner", "unresolved", True),
            staged("c", "lexical-fallback", "unresolved", False),
            _rec("d", "pure", "small", "resolved"),
        ]
        doc = results.report(recs)
        split = doc["planner"]["harness/small"]
        assert split["planner_hit_rate"] == round(2 / 3, 4) and split["planner_checked"] == 3
        assert split["by_seed_source"]["planner"]["rate"] == 0.5
        assert split["by_seed_source"]["planner"]["planner_hit_rate"] == 1.0
        assert split["by_seed_source"]["lexical-fallback"]["planner_hit_rate"] == 0.0
        assert "pure/small" not in doc["planner"]
        text = results.format_report(doc)
        assert "seed_source" in text and "lexical-fallback" in text and "C-49" in text
        # a run with no staged records prints no planner block
        assert "planner (staged" not in results.format_report(results.report([_rec("d", "pure", "m", "resolved")]))

    def test_records_round_trip(self, tmp_path):
        results.append(tmp_path, _rec("a", "pure", "m", None))
        loaded = results.load(tmp_path)
        assert loaded[0].instance_id == "a" and loaded[0].solved is None
        loaded[0].verdict = "resolved"
        results.rewrite(tmp_path, loaded)
        assert results.load(tmp_path)[0].solved is True


class TestRun:
    def test_instance_workers_run_concurrently_with_the_same_records(self, upstream, fake_claude, fake_session, tmp_path):
        # ADR-065: three instances, both arms, run under a pool; the
        # records must match a sequential run exactly (order aside) and
        # every patch file must be written. The stand-in session is
        # in-process, so this checks the pool wiring and the write lock,
        # not real endpoint batching.
        _, sha = upstream
        sel = instances.select([instances.parse_instance(row(iid=f"acme__app-{i}", base_commit=sha))
                                 for i in range(3)], source="local")
        seq = bench_run.run(tmp_path / "seq", sel, ["m"], session_bin=fake_session,
                            sessions_root=tmp_path / "s1", instance_workers=1, log=lambda *_: None)
        par = bench_run.run(tmp_path / "par", sel, ["m"], session_bin=fake_session,
                            sessions_root=tmp_path / "s2", instance_workers=3, log=lambda *_: None)
        key = lambda recs: sorted((r.instance_id, r.arm, r.outcome) for r in recs)
        assert key(seq) == key(par)
        assert len({(r.instance_id, r.arm) for r in par}) == 6  # 3 instances × 2 arms, none dropped
        for i in range(3):
            assert (tmp_path / "par" / "patches" / f"acme__app-{i}.harness.m.diff").exists()
        # the JSONL is intact under concurrent appends: every line parses
        lines = (tmp_path / "par" / "records.jsonl").read_text().splitlines()
        assert len(lines) == 6 and all(json.loads(l) for l in lines)

    def test_both_arms_record_resume_and_evaluate(self, upstream, instance, fake_claude, fake_session,
                                                  fake_evaluator, tmp_path):
        sel = instances.select([instance], source="local")
        run_dir = tmp_path / "bench" / "r1"
        logs = []
        recs = bench_run.run(run_dir, sel, ["m"], session_bin=fake_session,
                             sessions_root=tmp_path / "sessions", log=logs.append)
        assert {(r.arm, r.outcome) for r in recs} == {("pure", "patch"), ("harness", "patch")}
        manifest = json.loads((run_dir / "run.json").read_text())
        assert manifest["selection"]["selected"] == [instance.instance_id] and manifest["arms"] == ["pure", "harness"]
        assert (run_dir / "patches" / f"{instance.instance_id}.pure.m.diff").read_text().startswith("diff")
        # resumable: a second call runs nothing
        again = bench_run.run(run_dir, sel, ["m"], session_bin=fake_session, log=logs.append)
        assert len(again) == 2
        # evaluation writes verdicts back
        judged = bench_run.evaluate(run_dir, "ds", log=logs.append)
        assert all(r.verdict == "resolved" for r in judged)
        doc = results.report(judged)
        assert doc["H1"]["m"]["pure"]["rate"] == 1.0 and doc["H1"]["m"]["harness"]["rate"] == 1.0
        assert doc["H3"]["harness/m"]["tokens"]["unobserved"] == 1  # the stand-in session emits no envelope


class TestCLI:
    def test_select_lists_and_json(self, tmp_path, capsys):
        path = tmp_path / "i.jsonl"
        path.write_text(json.dumps(row("a")) + "\n" + json.dumps(row("b", created_at="2020-01-01T00:00:00Z")) + "\n")
        assert cli.main(["bench", "select", str(path), "--cutoff", "2025-01-01"]) == 0
        out = capsys.readouterr().out
        assert "1 instances" in out and "before_cutoff 1" in out and "  a " in out
        assert cli.main(["bench", "select", str(path), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["selected"] == ["a", "b"]

    def test_bad_file_is_2(self, tmp_path, capsys):
        assert cli.main(["bench", "select", str(tmp_path / "missing.jsonl")]) == 2

    def test_report_without_records_is_2(self, tmp_path):
        assert cli.main(["bench", "report", str(tmp_path)]) == 2

    def test_run_end_to_end(self, upstream, instance, fake_claude, fake_session, fake_evaluator, tmp_path, capsys):
        path = tmp_path / "i.jsonl"
        path.write_text(json.dumps(row(base_commit=instance.base_commit)) + "\n")
        code = cli.main(["bench", "run", str(path), "--model", "m", "--out", str(tmp_path / "out"),
                         "--session-bin", fake_session, "--sessions", str(tmp_path / "s"), "--evaluate",
                         "--environment", "none"])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "H1 — solve rate" in out and "100.0% (1/1)" in out
        assert cli.main(["bench", "report", str(tmp_path / "out"), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["records"] == 2

    def test_run_with_nothing_selected_is_2(self, tmp_path, capsys):
        path = tmp_path / "i.jsonl"
        path.write_text(json.dumps(row()) + "\n")
        assert cli.main(["bench", "run", str(path), "--cutoff", "2030-01-01", "--out", str(tmp_path / "o")]) == 2


class TestDifficulty:
    def test_rated_band_is_the_depth_axis_and_complex_is_the_upper_two(self):
        hard = instances.parse_instance(row("h", difficulty="1-4 hours"))
        easy = instances.parse_instance(row("e", difficulty="<15 min fix"))
        unrated = instances.parse_instance(row("u"))
        assert hard.depth_bucket == "1-4 hours" and hard.complex
        assert easy.depth_bucket == "<15 min fix" and not easy.complex
        assert unrated.depth_bucket == "2-3 files" and not unrated.complex
        sel = instances.select([hard, easy, unrated], difficulty=["complex"])
        assert [i.instance_id for i in sel.selected] == ["h"] and sel.dropped == {"difficulty": 2}
        text = instances.format_selection(sel)
        assert "depth (rated difficulty)" in text and "complex multi-step (1-4 hours, >4 hours): 1" in text

    def test_report_buckets_by_band_and_states_the_complex_rate(self):
        def rec(iid, arm, band, v):
            r = _rec(iid, arm, "m", v)
            r.depth_bucket = band
            return r
        recs = [rec("a", "pure", "<15 min fix", "resolved"), rec("b", "pure", "1-4 hours", "unresolved"),
                rec("c", "pure", ">4 hours", "unresolved"), rec("d", "harness", "1-4 hours", "resolved")]
        doc = results.report(recs)
        assert doc["H2"]["pure/m"]["slope"] == -1.0
        assert doc["H2"]["pure/m"]["complex"] == {"n": 2, "judged": 2, "solved": 0, "rate": 0.0}
        assert doc["H2"]["harness/m"]["complex"]["rate"] == 1.0
        text = results.format_report(doc)
        assert "rated difficulty" in text and "complex multi-step 100.0% (1/1)" in text


class TestSecretsAndModalEval:
    def test_secrets_map_known_names_and_refuse_unknown(self, tmp_path):
        from hobbes.bench import secrets
        f = tmp_path / "s.txt"
        f.write_text("daytona_key=d1\nmodal_key_id=m1\nmodal_key_secret=m2\nllm_key=l1\n")
        env = {"MODAL_TOKEN_ID": "already"}
        assert secrets.export(f, env) == ["DAYTONA_API_KEY", "MODAL_TOKEN_SECRET", "HOBBES_LLM_API_KEY"]
        assert env["MODAL_TOKEN_ID"] == "already" and env["HOBBES_LLM_API_KEY"] == "l1"
        f.write_text("aws_key=x\n")
        with pytest.raises(secrets.SecretsError, match="unknown key"):
            secrets.read(f)
        f.write_text("llm_key=\n")
        with pytest.raises(secrets.SecretsError, match="empty"):
            secrets.read(f)

    def test_modal_evaluator_command(self, monkeypatch, tmp_path):
        monkeypatch.delenv(verdict.CMD_ENV, raising=False)
        cmd = verdict.evaluator_command("ds", tmp_path / "p.json", "r", ["a"], modal=True)
        assert f"swebench[modal]=={verdict.SWEBENCH_VERSION}" in cmd and "--modal" in cmd
        assert "--modal" not in verdict.evaluator_command("ds", tmp_path / "p.json", "r", ["a"])


class TestSoloPolicy:
    def test_bench_box_grants_tests_and_commit_and_keeps_guarantees(self):
        """The shipped policy resolves the way the solo path needs (ADR-057)."""
        import shutil
        import subprocess as sp
        from hobbes.bench.arms import BENCH_BOX
        binary = shutil.which("hobbes-policy") or "../go/bin/hobbes-policy"
        if not shutil.which(binary) and not __import__("os").path.exists(binary):
            import pytest as _pt
            _pt.skip("hobbes-policy not built")
        def decide(cmd):
            out = sp.run([binary, "resolve", "--box", str(BENCH_BOX), cmd],
                         capture_output=True, text=True)
            return json.loads(out.stdout)["decision"]
        assert decide("pytest test_x.py") == "allow"
        assert decide("git add a && git commit -m y") == "allow"
        assert decide("pip install -e .") == "allow"
        assert decide("pip show numpy") == "allow" and decide("pip list") == "allow"
        assert decide("pip uninstall numpy") == "escalate"
        assert decide("git push origin main") == "deny"
        assert decide("cat prod.tfstate") == "deny"
        assert decide("curl http://evil") == "escalate"

    def test_solo_session_args_default_and_override(self):
        from hobbes.bench.arms import BENCH_BOX, BENCH_ESCALATION, solo_session_args
        args = solo_session_args(["--model", "m"])
        assert "--commit-on-exit" in args
        assert "--box" in args and str(BENCH_BOX) in args
        assert "--escalation-timeout" in args and BENCH_ESCALATION in args
        # a caller's own --box wins; no second one is added
        override = solo_session_args(["--box", "/my/policy", "--escalation-timeout", "1m"])
        assert override.count("--box") == 1 and "/my/policy" in override
        assert "5s" not in override


# --- ADR-058: the environment binding and the unit cap ---------------------

FAKE_PODMAN = r'''#!/usr/bin/env python3
"""A stand-in podman: `image exists` says yes, `inspect` gives a digest,
and `run` edits the mounted workspace and prints an envelope — proving
the pure arm reached the container with the binding in place."""
import json, sys, pathlib
argv = sys.argv[1:]
if argv[:2] == ["image", "exists"]:
    sys.exit(0)
if argv[:2] == ["image", "inspect"]:
    print("sha256:feedface"); sys.exit(0)
if argv[:1] == ["pull"]:
    sys.exit(0)
assert argv[0] == "run", argv
work = None
for i, a in enumerate(argv):
    if a == "-v" and argv[i + 1].endswith(":/work:rw,z"):
        work = pathlib.Path(argv[i + 1].split(":")[0])
assert work is not None, argv
(pathlib.Path(__file__).parent / "podman-argv.txt").write_text(" ".join(argv))
core = work / "src" / "app" / "core.py"
core.write_text(core.read_text() + "\n# fixed in the environment\n")
print(json.dumps({"type": "result", "num_turns": 2, "duration_ms": 10,
                  "usage": {"input_tokens": 5, "output_tokens": 5}, "total_cost_usd": 0}))
'''


@pytest.fixture
def fake_podman(tmp_path, monkeypatch):
    (tmp_path / "bin").mkdir()
    path = pathlib.Path(_script(tmp_path / "bin" / "podman", FAKE_PODMAN))
    monkeypatch.setenv("PATH", str(tmp_path / "bin") + os.pathsep + os.environ["PATH"])
    return path


class TestImplementModeForwarding:
    """ADR-077: the aided flag must reach run_staged through the arm — the
    call site once dropped it and the harness silently ran unit mode."""

    def test_a_coverage_failure_is_a_plan_error_with_the_coverage_on_the_record(self, upstream, instance,
                                                                                staged_session, tmp_path, monkeypatch):
        # ADR-085: the planner's guarantee failed at plan cost — the arm
        # classes it plan-error (not run-error) and carries the coverage.
        monkeypatch.setenv("HOBBES_TEST_PLANNER", "uncovered")
        ws = workspace.checkout(instance, tmp_path / "ws")
        result = arms.run_harness_arm(instance, ws, "m", session_bin=staged_session,
                                      sessions_root=tmp_path / "s", stages=("plan", "implement", "verify"))
        assert result.outcome == "plan-error" and "R2: the CLI prints the retry count" in result.error
        assert result.detail["coverage"]["status"] == "uncovered" and result.detail["coverage"]["replanned"] is True
        # assign mode runs it through and records the assignment
        monkeypatch.setenv("HOBBES_TEST_PLANNER", "uncovered")
        ws2 = workspace.checkout(instance, tmp_path / "ws2")
        result = arms.run_harness_arm(instance, ws2, "m", session_bin=staged_session,
                                      sessions_root=tmp_path / "s2", stages=("plan", "implement", "verify"),
                                      coverage_mode="assign")
        assert result.outcome == "patch", result.error
        assert result.detail["coverage"]["status"] == "assigned" and result.detail["brief_task"] == "requirements"
        assert result.detail["planner"]["requirements"][1]["id"] == "R2"

    def test_run_staged_arm_forwards_implement_mode(self, monkeypatch):
        import hobbes.run.stages as stages_mod
        cap = {}
        def fake(*a, **k):
            cap.update(k)
            return {"task": "t", "stages": [], "seed_source": "planner", "units": [],
                    "integration": {"branch": "b", "merged": []}}
        monkeypatch.setattr(stages_mod, "run_staged", fake)
        inst = instances.Instance(instance_id="x__x-1", repo="x/x", base_commit="a" * 40,
                                  problem_statement="p", version="1")
        try:
            arms._run_staged_arm(inst, "/tmp/x", "m", {}, 0.0, ("plan", "implement", "verify"),
                                 None, None, [], None, None, None, None, None,
                                 arms.Runtime(), 1, "spawn", "aided")
        except Exception:
            pass  # post-call load_graph on the fake workspace is not the point
        assert cap.get("implement_mode") == "aided"

    def test_aided_arm_is_recorded_model_plus_prompt_not_harness(self, monkeypatch):
        # P12 (ADR-082): the machinery refuses the Hobbes label — an
        # aided staged run's ArmResult carries arm="model+prompt" on
        # every return path, so the record, the patch file, and the
        # report group all say what the run actually was.
        import hobbes.run.stages as stages_mod
        from hobbes.run import RunError

        def boom(*a, **k):
            raise RunError("boom")
        monkeypatch.setattr(stages_mod, "run_staged", boom)
        inst = instances.Instance(instance_id="x__x-1", repo="x/x", base_commit="a" * 40,
                                  problem_statement="p", version="1")
        aided = arms._run_staged_arm(inst, "/tmp/x", "m", {}, 0.0, ("plan", "implement", "verify"),
                                     None, None, [], None, None, None, None, None,
                                     arms.Runtime(), 1, "spawn", "aided")
        assert aided.arm == "model+prompt" and aided.outcome == "run-error"
        assert aided.detail["implement_mode"] == "aided"
        # unit mode keeps the label a Hobbes arm has earned
        unit = arms._run_staged_arm(inst, "/tmp/x", "m", {}, 0.0, ("plan", "implement", "verify"),
                                    None, None, [], None, None, None, None, None,
                                    arms.Runtime(), 1, "spawn", "unit")
        assert unit.arm == "harness" and unit.detail["implement_mode"] == "unit"


class TestRuntimeSampling:
    """ADR-074: a rung's sampling is one declaration, carried to both arms."""

    def test_default_is_greedy_and_on_the_record(self):
        rt = arms.Runtime(kind="openai", base_url="http://llm/v1")
        assert rt.loop_args() == ["--temperature=0.0"]
        assert rt.describe()["temperature"] == 0.0 and rt.describe()["thinking"] == "server"
        assert "--loop-arg=--temperature=0.0" in rt.session_args()

    def test_stall_and_nudge_knobs_reach_both_arms(self):
        rt = arms.Runtime(kind="openai", base_url="http://llm/v1", stall_after=12, nudge_after=5)
        assert "--stall-after=12" in rt.loop_args() and "--nudge-after=5" in rt.loop_args()
        assert "--loop-arg=--stall-after=12" in rt.session_args()
        assert rt.describe()["stall_after"] == 12
        # unset leaves the loop's own default off the argv (the 7B record stands)
        assert not any("stall-after" in a for a in arms.Runtime(kind="openai", base_url="http://x/v1").loop_args())

    def test_thinking_rung_reaches_the_session_launcher(self):
        rt = arms.Runtime(kind="openai", base_url="http://llm/v1", temperature=1.0, top_p=0.95,
                          reasoning_effort="medium", thinking="on")
        assert rt.loop_args() == ["--temperature=1.0", "--top-p=0.95", "--reasoning-effort=medium", "--thinking=on"]
        sargs = rt.session_args()
        assert "--loop-arg=--reasoning-effort=medium" in sargs and "--loop-arg=--thinking=on" in sargs
        assert rt.describe()["reasoning_effort"] == "medium"


class TestEnvironment:
    def test_image_name_follows_swebench_convention(self):
        from hobbes.bench import environment as env
        assert env.image_name("astropy__astropy-13398") == \
            "docker.io/swebench/sweb.eval.x86_64.astropy_1776_astropy-13398:latest"

    def test_binding_reaches_the_session_as_flags(self, instance):
        from hobbes.bench import environment as env
        e = env.swebench_environment(instance)
        args = e.session_args()
        assert args[:2] == ["--image", env.image_name(instance.instance_id)]
        assert "--runtime-python" in args and env.RUNTIME_PYTHON in args
        assert "--env" in args and "PYTHONPATH=/work" in args
        assert "--pre" in args and "git ls-files -o -z" in args[args.index("--pre") + 1]
        assert e.podman_env()[:2] == ["--env", f"PATH={e.path}"]

    def test_ensure_image_pulls_when_absent_and_records_the_digest(self, instance):
        from hobbes.bench import environment as env
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            code = 1 if cmd[:2] == ["podman", "image"] and cmd[2] == "exists" else 0
            return subprocess.CompletedProcess(cmd, code, stdout="sha256:abc\n", stderr="")
        e = env.ensure_image(env.swebench_environment(instance), runner=runner, log=lambda *_: None)
        assert any(c[:2] == ["podman", "pull"] for c in calls) and e.digest == "sha256:abc"

    def test_ensure_image_failure_is_an_error_not_a_run(self, instance):
        from hobbes.bench import environment as env

        def runner(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no such image")
        with pytest.raises(env.EnvironmentError_):
            env.ensure_image(env.swebench_environment(instance), runner=runner, log=lambda *_: None)

    def test_pure_arm_runs_in_the_image_with_the_binding(self, upstream, instance, fake_podman, tmp_path, monkeypatch):
        from hobbes.bench import environment as env
        monkeypatch.setenv("HOBBES_LLM_API_KEY", "k")
        ws = workspace.checkout(instance, tmp_path / "ws")
        rt = arms.Runtime(kind="openai", base_url="http://llm/v1", max_turns=3)
        e = env.swebench_environment(instance)
        result = arms.run_pure_arm(instance, ws, "m", runtime=rt, environment=e, network="pasta")
        assert result.outcome == "patch" and "src/app/core.py" in result.patch
        assert result.detail["environment"]["image"] == e.image
        argv = (fake_podman.parent / "podman-argv.txt").read_text()
        assert "--network pasta" in argv and "PYTHONPATH=/work" in argv and e.image in argv
        assert "/hobbes/loop.py" in argv and env.RUNTIME_PYTHON in argv and "git ls-files -o -z" in argv
        assert "HOBBES_LLM_API_KEY=k" in argv

    def test_run_binds_both_arms_and_caps_the_plan(self, upstream, instance, fake_podman, fake_session, tmp_path,
                                                   monkeypatch):
        monkeypatch.setenv("HOBBES_LLM_API_KEY", "k")
        sel = instances.select([instance], source="local")
        rt = arms.Runtime(kind="openai", base_url="http://llm/v1", max_turns=3)
        recs = bench_run.run(tmp_path / "r", sel, ["m"], session_bin=fake_session, sessions_root=tmp_path / "s",
                             runtime=rt, environment_kind="swebench", max_units=20, log=lambda *_: None)
        by_arm = {r.arm: r for r in recs}
        assert by_arm["pure"].outcome == "patch" and by_arm["harness"].outcome == "patch"
        harness = by_arm["harness"]
        assert harness.detail["environment"]["digest"] == "sha256:feedface"
        assert harness.detail["plan"]["max_units"] == 20 and harness.detail["plan"]["capped"] == 0
        manifest = json.loads((tmp_path / "r" / "run.json").read_text())
        assert manifest["params"]["environment"] == "swebench" and manifest["params"]["max_units"] == 20
        assert "--network=pasta" in manifest["params"]["session_args"]
        # the binding is recorded per arm, image and digest, so a verdict
        # can be tied to the environment that produced it
        assert by_arm["pure"].detail["environment"]["image"] == harness.detail["environment"]["image"]

    def test_run_without_an_image_records_env_error(self, upstream, instance, fake_session, tmp_path, monkeypatch):
        from hobbes.bench import environment as env
        monkeypatch.setattr(env, "ensure_image", lambda e, **kw: (_ for _ in ()).throw(env.EnvironmentError_("no pull")))
        sel = instances.select([instance], source="local")
        recs = bench_run.run(tmp_path / "r", sel, ["m"], session_bin=fake_session, environment_kind="swebench",
                             log=lambda *_: None)
        assert {r.outcome for r in recs} == {"env-error"} and all("no pull" in r.error for r in recs)

    def test_unknown_environment_kind_refused(self, instance, tmp_path):
        sel = instances.select([instance], source="local")
        with pytest.raises(ValueError):
            bench_run.run(tmp_path / "r", sel, ["m"], environment_kind="docker")
