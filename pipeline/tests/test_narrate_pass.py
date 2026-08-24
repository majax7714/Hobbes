"""Orchestrator, runner, and CLI for the narrative pass (ADR-020)."""

import json
import stat
import textwrap

import pytest

from hobbes import cli
from hobbes.narrate import (
    INVARIANTS_UNIT_ID,
    NarrateError,
    Unit,
    artifact_status,
    plan_status,
    plan_units,
    run_pass,
    select_units,
    unit_status,
)
from hobbes.narrate.runner import ClaudeRunner, RunnerError, parse_json_response
from hobbes.narrate.schema import (
    behavior_index_path,
    invariants_path,
    module_doc_path,
)

TEST_FILE = "tests/test_app.py"
TEST_ID = f"{TEST_FILE}::test_greet"


@pytest.fixture
def skeleton_repo(git_repo):
    """git_repo (app.py) plus a test file and hand-written derived skeleton."""
    (git_repo / "tests").mkdir()
    (git_repo / TEST_FILE).write_text(
        textwrap.dedent(
            """\
            from app import greet

            def test_greet():
                assert greet("x") == "hi x"
            """
        )
    )
    stamp = {"sha": "b" * 40, "dirty": False, "schema_version": 2}
    derived = git_repo / ".hobbes" / "derived"
    derived.mkdir(parents=True)
    (derived / "graph.json").write_text(
        json.dumps(
            {
                **stamp,
                "languages": ["python"],
                "nodes": [
                    {"id": "app", "kind": "module", "path": "app.py"},
                    {"id": "tests.test_app", "kind": "module", "path": TEST_FILE},
                ],
                "module_edges": [
                    {
                        "from": "tests.test_app",
                        "to": "app",
                        "type": "imports",
                        "evidence": [{"path": TEST_FILE, "line": 1}],
                    }
                ],
                "symbols": [
                    {
                        "id": "app.greet",
                        "module": "app",
                        "kind": "function",
                        "name": "greet",
                        "qualname": "greet",
                        "line": 5,
                        "end_line": 6,
                    }
                ],
                "symbol_edges": [],
            }
        )
    )
    (derived / "tests.json").write_text(
        json.dumps(
            {
                **stamp,
                "framework": "pytest",
                "tests": [
                    {
                        "id": TEST_ID,
                        "file": TEST_FILE,
                        "line": 3,
                        "symbol": "tests.test_app.test_greet",
                        "reaches": ["app.greet"],
                        "reaches_modules": ["app"],
                    }
                ],
            }
        )
    )
    (derived / "interfaces.json").write_text(
        json.dumps({**stamp, "routes": [], "cli_entry_points": []})
    )
    return git_repo


def module_response():
    return json.dumps(
        {
            "purpose": {
                "text": "a tiny app module",
                "pins": [{"path": "app.py", "line": 1}],
            },
            "responsibilities": [
                {"text": "greets by name", "pins": [{"path": "app.py", "line": 5}]}
            ],
            "gotchas": [],
        }
    )


def behaviors_response():
    return json.dumps(
        {
            "behaviors": [
                {
                    "test": TEST_ID,
                    "text": "greeting prefixes the configured greeting",
                    "pins": [{"path": TEST_FILE, "line": 4}],
                }
            ]
        }
    )


def invariants_response():
    return json.dumps(
        {
            "invariants": [
                {
                    "statement": "only app builds greetings",
                    "scope": "app.py",
                    "evidence": [{"path": TEST_FILE, "line": 1}],
                    "guarded_by": [TEST_ID],
                }
            ]
        }
    )


class FakeRunner:
    """Returns queued responses in order; records every prompt."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("runner called more times than expected")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class TestPlanning:
    def test_plan_units_order_and_kinds(self, skeleton_repo):
        graph, tests, _ = _derived(skeleton_repo)
        units = plan_units(graph, tests)
        assert [(u.kind, u.id) for u in units] == [
            ("module", "app"),
            ("tests", "tests.test_app"),
            ("invariants", INVARIANTS_UNIT_ID),
        ]
        assert units[1].tests[0]["id"] == TEST_ID

    def test_test_file_gets_no_module_doc(self, skeleton_repo):
        graph, tests, _ = _derived(skeleton_repo)
        module_ids = [u.id for u in plan_units(graph, tests) if u.kind == "module"]
        assert "tests.test_app" not in module_ids

    def test_select_by_id_and_path_exclude_wins(self):
        units = [Unit("module", "app", "app.py"), Unit("module", "lib.x", "lib/x.py")]
        assert select_units(units, only=["app*"]) == [units[0]]
        assert select_units(units, only=["lib/*"]) == [units[1]]
        assert select_units(units, only=["*"], exclude=["lib.*"]) == [units[0]]

    def test_missing_derived_raises(self, git_repo):
        with pytest.raises(NarrateError, match="hobbes ingest"):
            plan_status(git_repo)


class TestUnitStatus:
    def test_missing_then_fresh_then_stale(self, skeleton_repo):
        runner = FakeRunner([module_response(), behaviors_response(), invariants_response()])
        unit = Unit("module", "app", "app.py")
        assert unit_status(skeleton_repo, unit) == (True, "missing")
        run_pass(skeleton_repo, runner, out=lambda _: None)
        assert unit_status(skeleton_repo, unit) == (False, "fresh")
        (skeleton_repo / "app.py").write_text("edited = True\n")
        due, reason = unit_status(skeleton_repo, unit)
        assert due and reason == "stale: app.py"

    def test_schema_version_bump_makes_due(self, skeleton_repo):
        runner = FakeRunner([module_response(), behaviors_response(), invariants_response()])
        run_pass(skeleton_repo, runner, out=lambda _: None)
        doc_path = module_doc_path(skeleton_repo, "app")
        doc = json.loads(doc_path.read_text())
        doc["schema_version"] = 999
        doc_path.write_text(json.dumps(doc))
        assert unit_status(skeleton_repo, Unit("module", "app", "app.py")) == (
            True,
            "artifact schema changed",
        )


class TestRunPass:
    def test_full_pass_writes_all_artifacts(self, skeleton_repo):
        runner = FakeRunner([module_response(), behaviors_response(), invariants_response()])
        lines = []
        summary = run_pass(skeleton_repo, runner, out=lines.append)
        assert summary["generated"] == ["app", "tests.test_app", INVARIANTS_UNIT_ID]
        assert summary["failed"] == {} and summary["skipped"] == []
        assert module_doc_path(skeleton_repo, "app").is_file()
        assert behavior_index_path(skeleton_repo, "tests.test_app").is_file()
        assert invariants_path(skeleton_repo).is_file()
        assert any("narrate: 3 generated" in line for line in lines)

    def test_prompts_carry_numbered_source_and_ids(self, skeleton_repo):
        runner = FakeRunner([module_response(), behaviors_response(), invariants_response()])
        run_pass(skeleton_repo, runner, out=lambda _: None)
        module_prompt, tests_prompt, inv_prompt = runner.prompts
        assert "    5: def greet(name):" in module_prompt
        assert TEST_ID in tests_prompt
        assert "a tiny app module" in inv_prompt  # fresh purpose fed forward

    def test_second_run_is_incremental(self, skeleton_repo):
        run_pass(
            skeleton_repo,
            FakeRunner([module_response(), behaviors_response(), invariants_response()]),
            out=lambda _: None,
        )
        untouched = FakeRunner([])
        summary = run_pass(skeleton_repo, untouched, out=lambda _: None)
        assert summary["skipped"] == ["app", "tests.test_app", INVARIANTS_UNIT_ID]
        assert untouched.prompts == []

    def test_edit_requeues_only_touched_units(self, skeleton_repo):
        run_pass(
            skeleton_repo,
            FakeRunner([module_response(), behaviors_response(), invariants_response()]),
            out=lambda _: None,
        )
        (skeleton_repo / "app.py").write_text(
            (skeleton_repo / "app.py").read_text() + "# trailing comment\n"
        )
        runner = FakeRunner([module_response()])
        summary = run_pass(skeleton_repo, runner, out=lambda _: None)
        assert summary["generated"] == ["app"]
        assert set(summary["skipped"]) == {"tests.test_app", INVARIANTS_UNIT_ID}

    def test_invalid_json_retries_with_feedback(self, skeleton_repo):
        runner = FakeRunner(
            ["not json at all", module_response(), behaviors_response(), invariants_response()]
        )
        summary = run_pass(skeleton_repo, runner, out=lambda _: None)
        assert summary["failed"] == {}
        assert "failed validation" in runner.prompts[1]
        assert "not valid JSON" in runner.prompts[1]

    def test_bad_pins_feed_problems_back(self, skeleton_repo):
        bad = json.dumps(
            {
                "purpose": {"text": "x", "pins": [{"path": "gone.py", "line": 1}]},
                "responsibilities": [
                    {"text": "y", "pins": [{"path": "app.py", "line": 1}]}
                ],
                "gotchas": [],
            }
        )
        runner = FakeRunner(
            [bad, module_response(), behaviors_response(), invariants_response()]
        )
        summary = run_pass(skeleton_repo, runner, out=lambda _: None)
        assert summary["failed"] == {}
        assert "gone.py" in runner.prompts[1]

    def test_two_failures_mark_unit_failed_and_continue(self, skeleton_repo):
        runner = FakeRunner(
            ["bad", "still bad", behaviors_response(), invariants_response()]
        )
        summary = run_pass(skeleton_repo, runner, out=lambda _: None)
        assert list(summary["failed"]) == ["app"]
        assert summary["generated"] == ["tests.test_app", INVARIANTS_UNIT_ID]
        assert not module_doc_path(skeleton_repo, "app").exists()

    def test_runner_error_retries_once_then_fails(self, skeleton_repo):
        runner = FakeRunner(
            [
                RunnerError("boom"),
                RunnerError("boom again"),
                behaviors_response(),
                invariants_response(),
            ]
        )
        summary = run_pass(skeleton_repo, runner, out=lambda _: None)
        assert summary["failed"]["app"] == ["boom again"]

    def test_fingerprint_fallback_never_hits_fresh_docs(self, skeleton_repo):
        run_pass(
            skeleton_repo,
            FakeRunner([module_response(), behaviors_response(), invariants_response()]),
            out=lambda _: None,
        )
        rows = artifact_status(skeleton_repo)
        assert [(r["kind"], r["status"]) for r in rows] == [
            ("inferred-invariants", "fresh"),
            ("module-doc", "fresh"),
            ("test-doc", "fresh"),
        ]


class TestArtifactStatus:
    def test_edit_flips_exactly_the_citing_artifacts(self, skeleton_repo):
        run_pass(
            skeleton_repo,
            FakeRunner([module_response(), behaviors_response(), invariants_response()]),
            out=lambda _: None,
        )
        (skeleton_repo / "app.py").write_text("edited = True\n")
        by_kind = {r["kind"]: r for r in artifact_status(skeleton_repo)}
        assert by_kind["module-doc"]["status"] == "stale"
        assert by_kind["module-doc"]["changed"] == ["app.py"]
        # test doc and invariants pin only the test file: untouched.
        assert by_kind["test-doc"]["status"] == "fresh"
        assert by_kind["inferred-invariants"]["status"] == "fresh"


class TestClaudeRunner:
    def fake_claude(self, tmp_path, monkeypatch, body):
        script = tmp_path / "fake-claude"
        script.write_text(f"#!/bin/sh\n{body}\n")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("HOBBES_CLAUDE_BIN", str(script))
        return script

    def test_happy_envelope(self, tmp_path, monkeypatch):
        envelope = json.dumps({"is_error": False, "result": '{"x": 1}'})
        self.fake_claude(tmp_path, monkeypatch, f"cat > /dev/null\ncat <<'EOF'\n{envelope}\nEOF")
        assert ClaudeRunner()("prompt") == '{"x": 1}'

    def test_nonzero_exit_raises(self, tmp_path, monkeypatch):
        self.fake_claude(tmp_path, monkeypatch, "echo doom >&2\nexit 3")
        with pytest.raises(RunnerError, match="exited 3: doom"):
            ClaudeRunner()("prompt")

    def test_error_envelope_raises(self, tmp_path, monkeypatch):
        envelope = json.dumps({"is_error": True, "result": "quota exhausted"})
        self.fake_claude(tmp_path, monkeypatch, f"cat <<'EOF'\n{envelope}\nEOF")
        with pytest.raises(RunnerError, match="reported an error"):
            ClaudeRunner()("prompt")

    def test_missing_binary_raises(self, monkeypatch):
        monkeypatch.setenv("HOBBES_CLAUDE_BIN", "/nonexistent/claude")
        with pytest.raises(RunnerError, match="not found"):
            ClaudeRunner()("prompt")


class TestParseJsonResponse:
    def test_bare_json(self):
        assert parse_json_response(' {"a": 1} ') == {"a": 1}

    def test_fenced_json(self):
        assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}

    def test_garbage_raises_with_feedback_message(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_json_response("sorry, here you go:")


class TestCli:
    def test_dry_run_spends_nothing(self, skeleton_repo, capsys, monkeypatch):
        monkeypatch.setenv("HOBBES_CLAUDE_BIN", "/nonexistent/claude")
        rc = cli.main(["narrate", "--repo", str(skeleton_repo), "--dry-run"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "3 cartographer calls would run" in out
        assert "due  module     app (missing)" in out

    def test_narrate_via_fake_runner(self, skeleton_repo, capsys, monkeypatch):
        responses = [module_response(), behaviors_response(), invariants_response()]
        monkeypatch.setattr(
            "hobbes.narrate.runner.ClaudeRunner",
            lambda model=None: FakeRunner(responses),
        )
        rc = cli.main(["narrate", "--repo", str(skeleton_repo)])
        assert rc == 0
        assert "narrate: 3 generated" in capsys.readouterr().out

    def test_narrate_failure_exit_code(self, skeleton_repo, monkeypatch, capsys):
        monkeypatch.setattr(
            "hobbes.narrate.runner.ClaudeRunner",
            lambda model=None: FakeRunner(["bad"] * 6),
        )
        assert cli.main(["narrate", "--repo", str(skeleton_repo)]) == 1

    def test_narrate_without_ingest_errors(self, git_repo, capsys):
        rc = cli.main(["narrate", "--repo", str(git_repo)])
        assert rc == 1
        assert "hobbes ingest" in capsys.readouterr().err

    def test_docs_status_flow(self, skeleton_repo, capsys, monkeypatch):
        rc = cli.main(["docs", "status", "--repo", str(skeleton_repo)])
        assert rc == 0
        assert "no narrative artifacts" in capsys.readouterr().out
        run_pass(
            skeleton_repo,
            FakeRunner([module_response(), behaviors_response(), invariants_response()]),
            out=lambda _: None,
        )
        (skeleton_repo / "app.py").write_text("edited = True\n")
        rc = cli.main(["docs", "status", "--repo", str(skeleton_repo)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "STALE  module-doc          app (app.py)" in out
        assert "fresh  test-doc            tests.test_app" in out
        assert "3 artifacts, 1 stale" in out

    def test_docs_status_json(self, skeleton_repo, capsys):
        run_pass(
            skeleton_repo,
            FakeRunner([module_response(), behaviors_response(), invariants_response()]),
            out=lambda _: None,
        )
        assert cli.main(["docs", "status", "--repo", str(skeleton_repo), "--json"]) == 0
        rows = json.loads(capsys.readouterr().out)
        assert {row["status"] for row in rows} == {"fresh"}


def _derived(repo):
    derived = repo / ".hobbes" / "derived"
    return tuple(
        json.loads((derived / name).read_text())
        for name in ("graph.json", "tests.json", "interfaces.json")
    )


class TestSubstantiveUnits:
    def test_package_with_code_gets_a_doc_unit(self, skeleton_repo):
        graph, tests, _ = _derived(skeleton_repo)
        graph["nodes"].append(
            {"id": "pkg", "kind": "package", "path": "pkg/__init__.py"}
        )
        (skeleton_repo / "pkg").mkdir()
        (skeleton_repo / "pkg" / "__init__.py").write_text("VERSION = 1\n")
        from hobbes.narrate import substantive_units

        units = substantive_units(skeleton_repo, plan_units(graph, tests))
        assert ("module", "pkg") in [(u.kind, u.id) for u in units]

    def test_empty_init_is_planned_out(self, skeleton_repo):
        graph, tests, _ = _derived(skeleton_repo)
        graph["nodes"].append(
            {"id": "empty", "kind": "package", "path": "empty/__init__.py"}
        )
        (skeleton_repo / "empty").mkdir()
        (skeleton_repo / "empty" / "__init__.py").write_text("\n")
        from hobbes.narrate import substantive_units

        units = substantive_units(skeleton_repo, plan_units(graph, tests))
        ids = [u.id for u in units]
        assert "empty" not in ids
        assert INVARIANTS_UNIT_ID in ids  # pathless units always survive
