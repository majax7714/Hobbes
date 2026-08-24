"""Invariant records: loading, validation, verdicts, compilation (M8, V2.M6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from hobbes.invariants import ValidationError, load_all, scope_matches
from hobbes.invariants.compile import compile_all
from hobbes.invariants.verdict import (
    FAIL,
    PASS,
    SKIPPED,
    SOFT,
    SUSPECT,
    UNKNOWN,
    judge_all,
)


# --- fixtures ---------------------------------------------------------------


def write_record(repo: Path, name: str, record: dict) -> Path:
    path = repo / ".hobbes" / "invariants" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False))
    return path


def graph_record(**overrides) -> dict:
    """A check: graph record — the V2.M6 default for import rules."""
    record = {
        "id": "I-1",
        "statement": "Only the extractors parse source.",
        "scope": "src",
        "status": "confirmed",
        "check": "graph",
        "rule": {
            "kind": "forbidden-import",
            "importers": ["*"],
            "except": ["app.parser"],
            "imported": ["ext:tree_sitter"],
        },
        "guarded_by": [],
    }
    record.update(overrides)
    return record


def emit_record(**overrides) -> dict:
    """A check: emit record compiling to import-linter."""
    record = graph_record(check="emit", compile={"target": "import-linter"})
    record.update(overrides)
    return record


def soft_record(**overrides) -> dict:
    record = {
        "id": "I-1",
        "statement": "Publishing is the human's.",
        "scope": ".",
        "status": "confirmed",
        "check": "soft",
        "guarded_by": [],
    }
    record.update(overrides)
    return record


@pytest.fixture
def graph() -> dict:
    """A small module graph: one legal parser import, nothing else."""
    return {
        "schema_version": 4,
        "sha": "abc",
        "dirty": False,
        "nodes": [
            {"id": "app.parser", "kind": "module", "path": "src/app/parser.py"},
            {"id": "app.core", "kind": "module", "path": "src/app/core.py"},
            {"id": "app.secrets", "kind": "module", "path": "src/app/secrets.py"},
            {"id": "tests.test_core", "kind": "module", "path": "tests/test_core.py"},
            {"id": "ext:tree_sitter", "kind": "external"},
        ],
        "module_edges": [
            {
                "from": "app.parser",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/parser.py", "line": 3}],
            }
        ],
        "symbols": [],
        "symbol_edges": [],
    }


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


# --- loading and validation -------------------------------------------------


class TestLoad:
    def test_loads_a_valid_graph_record(self, repo):
        write_record(repo, "I-1-parsers", graph_record())
        (record,) = load_all(repo)
        assert record.id == "I-1"
        assert record.check == "graph" and record.target == ""
        assert record.confirmed and not record.soft
        assert record.kind == "forbidden-import"
        assert record.source.endswith("I-1-parsers.yaml")

    def test_loads_a_valid_emit_record(self, repo):
        write_record(repo, "I-1", emit_record())
        (record,) = load_all(repo)
        assert record.check == "emit" and record.target == "import-linter"

    def test_missing_directory_is_empty_not_an_error(self, repo):
        assert load_all(repo) == []

    def test_statement_is_normalized_to_one_line(self, repo):
        write_record(repo, "I-1", graph_record(statement="a\n  b\n\n  c"))
        (record,) = load_all(repo)
        assert record.statement == "a b c"

    def test_ids_sort_numerically(self, repo):
        for n in (10, 2, 1):
            write_record(repo, f"I-{n}", graph_record(id=f"I-{n}"))
        assert [r.id for r in load_all(repo)] == ["I-1", "I-2", "I-10"]

    def test_every_problem_is_reported_at_once(self, repo):
        write_record(repo, "bad", {"id": "I-1"})
        with pytest.raises(ValidationError) as exc:
            load_all(repo)
        problems = " ".join(exc.value.problems)
        # One run should tell you everything to fix, not the first thing.
        assert "statement" in problems
        assert "scope" in problems
        assert "status" in problems
        assert "check" in problems

    def test_a_v1_record_is_told_how_to_migrate(self, repo):
        # The pre-M6 shape: no check, rule nested under compile. The
        # errors must name the migration, not just reject the file.
        write_record(
            repo,
            "I-1",
            {
                "id": "I-1",
                "statement": "old shape",
                "scope": ".",
                "status": "confirmed",
                "compile": {
                    "target": "import-linter",
                    "rule": {"kind": "forbidden-import", "importers": [], "imported": []},
                },
            },
        )
        with pytest.raises(ValidationError, match="ADR-039"):
            load_all(repo)

    def test_duplicate_ids_are_refused(self, repo):
        write_record(repo, "a", graph_record())
        write_record(repo, "b", graph_record())
        with pytest.raises(ValidationError, match="duplicate id I-1"):
            load_all(repo)

    def test_unknown_fields_are_refused(self, repo):
        write_record(repo, "I-1", graph_record(severity="high"))
        with pytest.raises(ValidationError, match="unknown field"):
            load_all(repo)

    def test_soft_record_with_a_rule_is_refused(self, repo):
        # Writing a spec and then telling every checker to ignore it
        # means one of the two is wrong.
        write_record(
            repo,
            "I-1",
            soft_record(
                rule={"kind": "forbidden-import", "importers": [], "imported": []}
            ),
        )
        with pytest.raises(ValidationError, match="check: soft takes no rule"):
            load_all(repo)

    def test_graph_record_with_a_compile_block_is_refused(self, repo):
        write_record(
            repo, "I-1", graph_record(compile={"target": "import-linter"})
        )
        with pytest.raises(ValidationError, match="graph emits nothing"):
            load_all(repo)

    def test_graph_record_with_an_unanswerable_kind_is_refused(self, repo):
        # A check: graph record the graph cannot answer would sit at
        # `unknown` forever — a check that cannot check.
        write_record(
            repo,
            "I-1",
            graph_record(
                rule={
                    "kind": "pattern-absent",
                    "languages": ["python"],
                    "patterns": ["open($P, 'w')"],
                }
            ),
        )
        with pytest.raises(ValidationError, match="graph cannot answer"):
            load_all(repo)

    def test_emit_without_a_rule_is_refused(self, repo):
        record = emit_record()
        del record["rule"]
        write_record(repo, "I-1", record)
        with pytest.raises(ValidationError, match="rule block is required"):
            load_all(repo)

    def test_emit_without_a_target_is_refused(self, repo):
        record = emit_record()
        del record["compile"]
        write_record(repo, "I-1", record)
        with pytest.raises(ValidationError, match="requires compile.target"):
            load_all(repo)

    def test_rule_kind_must_match_its_target(self, repo):
        write_record(
            repo, "I-1", emit_record(compile={"target": "semgrep"})
        )
        with pytest.raises(ValidationError, match="takes kind pattern-absent"):
            load_all(repo)

    def test_guarded_by_must_name_real_tests(self, repo):
        write_record(
            repo, "I-1", graph_record(guarded_by=["tests/gone.py::test_x"])
        )
        with pytest.raises(ValidationError, match="not in tests.json"):
            load_all(repo, known_tests={"tests/live.py::test_y"})
        # Without the test inventory there is nothing to check against.
        assert load_all(repo)

    def test_inferred_status_warns_but_stays_inert(self, repo):
        # ADR-019 keeps inferred records in derived/; one here is a
        # promotion someone stopped halfway.
        write_record(repo, "I-1", graph_record(status="inferred"))
        (record,) = load_all(repo)
        assert not record.confirmed
        assert any("stopped halfway" in w for w in record.warnings)


class TestScopeMatches:
    def test_dot_is_the_whole_repo(self):
        assert scope_matches(".", "anything/at/all.py")

    def test_matches_whole_segments_only(self):
        assert scope_matches("src/a", "src/a/mod.py")
        assert scope_matches("src/a", "src/a")
        assert not scope_matches("src/a", "src/ab/mod.py")

    def test_a_node_without_a_path_matches_nothing(self):
        assert not scope_matches("src", None)


# --- verdicts ---------------------------------------------------------------


class TestVerdicts:
    def test_clean_graph_passes(self, repo, graph):
        write_record(repo, "I-1", graph_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == PASS
        assert not verdict.violations

    def test_a_forbidden_import_fails_and_cites_the_line(self, repo, graph):
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/core.py", "line": 9}],
            }
        )
        write_record(repo, "I-1", graph_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == FAIL
        assert [v.cite() for v in verdict.violations] == [
            "app.core -> ext:tree_sitter [src/app/core.py:9]"
        ]

    def test_an_emit_record_still_gets_a_graph_verdict(self, repo, graph):
        # The M6 exit: where the graph can see an emitted rule, both
        # answers exist and must agree — so the checker never abstains
        # just because a CI tool also runs it.
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/core.py", "line": 9}],
            }
        )
        write_record(repo, "I-1", emit_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == FAIL

    def test_semantic_evidence_between_repo_modules_is_proof(self, repo, graph):
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "app.secrets",
                "type": "imports",
                "tier": "semantic",
                "evidence": [{"path": "src/app/core.py", "line": 4}],
            }
        )
        write_record(
            repo,
            "I-1",
            graph_record(
                rule={
                    "kind": "forbidden-import",
                    "importers": ["*"],
                    "imported": ["app.secrets"],
                }
            ),
        )
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == FAIL
        assert verdict.violations[0].proven

    def test_syntactic_evidence_between_repo_modules_is_a_suspicion(self, repo, graph):
        # §3.4: on syntactic edges a violation is a suspicion — still
        # red, but the reviewer knows which kind of red.
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "app.secrets",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/core.py", "line": 4}],
            }
        )
        write_record(
            repo,
            "I-1",
            graph_record(
                rule={
                    "kind": "forbidden-import",
                    "importers": ["*"],
                    "imported": ["app.secrets"],
                }
            ),
        )
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == SUSPECT
        assert not verdict.violations[0].proven
        assert "suspected" in verdict.violations[0].cite()

    def test_lane_a_only_targets_are_proven_at_syntactic_tier(self, repo, graph):
        # An `ext:` edge has no semantic form to be missing (§3.1): the
        # syntactic import statement is the authoritative evidence, and
        # calling it a suspicion would understate a real violation.
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/core.py", "line": 9}],
            }
        )
        write_record(repo, "I-1", graph_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == FAIL
        assert verdict.violations[0].proven

    def test_the_exception_list_is_honoured(self, repo, graph):
        # app.parser imports tree_sitter and is listed in `except`.
        write_record(repo, "I-1", graph_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == PASS

    def test_scope_bounds_who_the_rule_is_about(self, repo, graph):
        # A test module outside `src` importing tree_sitter is not a
        # violation of a rule scoped to src.
        graph["module_edges"].append(
            {
                "from": "tests.test_core",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "tests/test_core.py", "line": 2}],
            }
        )
        write_record(repo, "I-1", graph_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == PASS

        # Widening the scope to the whole repo catches it.
        write_record(repo, "I-1", graph_record(scope="."))
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == FAIL

    def test_prefix_patterns_match_packages_and_directories(self, repo, graph):
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/core.py", "line": 9}],
            }
        )
        record = graph_record()
        record["rule"]["importers"] = ["app.*"]
        record["rule"]["except"] = ["app.parser"]
        write_record(repo, "I-1", record)
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == FAIL

    def test_non_import_edges_are_not_violations(self, repo, graph):
        graph["module_edges"].append(
            {"from": "app.core", "to": "ext:tree_sitter", "type": "env-read"}
        )
        write_record(repo, "I-1", graph_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == PASS

    def test_soft_records_are_handed_to_a_reviewer(self, repo, graph):
        write_record(repo, "I-1", soft_record())
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == SOFT
        assert "cite evidence" in verdict.reason

    def test_unanswerable_targets_are_unknown_never_pass(self, repo, graph):
        # A semgrep rule matches source patterns; reporting it green
        # because the graph could not check it would be a false pass.
        write_record(
            repo,
            "I-1",
            emit_record(
                rule={
                    "kind": "pattern-absent",
                    "languages": ["python"],
                    "patterns": ["open($P, 'w')"],
                },
                compile={"target": "semgrep"},
            ),
        )
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == UNKNOWN
        assert "compiled for CI" in verdict.reason

    def test_unconfirmed_records_are_skipped(self, repo, graph):
        write_record(repo, "I-1", graph_record(status="retired"))
        (verdict,) = judge_all(load_all(repo), graph)
        assert verdict.result == SKIPPED

    def test_worst_verdict_sorts_first(self, repo, graph):
        graph["module_edges"].append(
            {
                "from": "app.core",
                "to": "ext:tree_sitter",
                "type": "imports",
                "tier": "syntactic",
                "evidence": [{"path": "src/app/core.py", "line": 9}],
            }
        )
        write_record(repo, "I-1", graph_record(id="I-1"))
        write_record(repo, "I-2", soft_record(id="I-2"))
        results = [v.result for v in judge_all(load_all(repo), graph)]
        assert results[0] == FAIL

    def test_a_guard_that_vanished_is_reported(self, repo, graph):
        write_record(
            repo, "I-1", graph_record(guarded_by=["tests/t.py::test_a"])
        )
        records = load_all(repo)
        (verdict,) = judge_all(records, graph, test_ids=set())
        assert verdict.missing_guards == ["tests/t.py::test_a"]


# --- compilation ------------------------------------------------------------


class TestCompile:
    def test_import_linter_contract_carries_the_exceptions(self, repo, graph):
        write_record(repo, "I-1", emit_record())
        manifest = compile_all(repo, load_all(repo), graph)
        ini = (repo / ".hobbes/derived/compiled/importlinter.ini").read_text()
        assert "[importlinter:contract:I-1]" in ini
        assert "type = forbidden" in ini
        # `ext:` is the graph's namespace, not the package name.
        assert "tree_sitter" in ini and "ext:tree_sitter" not in ini
        assert "app.parser -> tree_sitter" in ini
        assert manifest["outputs"][0]["run"].startswith("lint-imports")

    def test_semgrep_rule_keeps_paths_and_patterns(self, repo, graph):
        write_record(
            repo,
            "I-1",
            emit_record(
                rule={
                    "kind": "pattern-absent",
                    "languages": ["python"],
                    "paths": ["src/app"],
                    "exclude": ["src/app/parser.py"],
                    "patterns": ["open($P, 'w')", "$P.write_text(...)"],
                },
                compile={"target": "semgrep"},
            ),
        )
        compile_all(repo, load_all(repo), graph)
        rules = yaml.safe_load(
            (repo / ".hobbes/derived/compiled/semgrep.yml").read_text()
        )["rules"]
        assert rules[0]["id"] == "I-1"
        assert rules[0]["paths"] == {
            "include": ["src/app"],
            "exclude": ["src/app/parser.py"],
        }
        assert len(rules[0]["pattern-either"]) == 2

    def test_dep_cruiser_rule_is_path_shaped(self, repo, graph):
        write_record(
            repo,
            "I-1",
            emit_record(
                scope="src",
                rule={
                    "kind": "forbidden-import",
                    "importers": ["*"],
                    "except": ["src/api/client"],
                    "imported": ["src/internal/secrets"],
                },
                compile={"target": "dep-cruiser"},
            ),
        )
        compile_all(repo, load_all(repo), graph)
        config = json.loads(
            (repo / ".hobbes/derived/compiled/dependency-cruiser.json").read_text()
        )
        rule = config["forbidden"][0]
        assert rule["name"] == "I-1"
        assert rule["severity"] == "error"
        assert rule["from"]["path"] == "^src/"
        assert "src/api/client" in rule["from"]["pathNot"]
        assert "src/internal/secrets" in rule["to"]["path"]

    def test_rego_is_valid_shaped_policy(self, repo, graph):
        write_record(
            repo,
            "I-1",
            emit_record(
                rule={
                    "kind": "resource-attribute",
                    "resource_type": "aws_s3_bucket",
                    "require": {"acl": "private"},
                },
                compile={"target": "rego"},
            ),
        )
        compile_all(repo, load_all(repo), graph)
        rego = (repo / ".hobbes/derived/compiled/terraform.rego").read_text()
        assert "package main" in rego
        assert "import rego.v1" in rego
        assert "deny contains msg if {" in rego
        assert '"aws_s3_bucket"' in rego
        # `I-4` is not a Rego identifier; nothing may emit one as a name.
        assert "I-1:" in rego

    def test_soft_graph_and_unconfirmed_records_are_skipped_with_a_reason(
        self, repo, graph
    ):
        write_record(repo, "I-1", soft_record())
        write_record(repo, "I-2", emit_record(id="I-2", status="retired"))
        write_record(repo, "I-3", graph_record(id="I-3"))
        manifest = compile_all(repo, load_all(repo), graph)
        assert manifest["outputs"] == []
        why = {s["id"]: s["why"] for s in manifest["skipped"]}
        assert "soft" in why["I-1"]
        assert "retired" in why["I-2"]
        # check: graph is judged in-process — skipped from CI emission,
        # and the manifest says by whom.
        assert "unified checker" in why["I-3"]

    def test_a_target_losing_its_last_record_loses_its_file(self, repo, graph):
        write_record(repo, "I-1", emit_record())
        compile_all(repo, load_all(repo), graph)
        ini = repo / ".hobbes/derived/compiled/importlinter.ini"
        assert ini.exists()

        # Stale output claiming to be current is worse than no output.
        write_record(repo, "I-1", graph_record())
        compile_all(repo, load_all(repo), graph)
        assert not ini.exists()

    def test_manifest_stamps_the_graph_it_compiled_against(self, repo, graph):
        write_record(repo, "I-1", emit_record())
        manifest = compile_all(repo, load_all(repo), graph)
        assert manifest["sha"] == "abc"
        assert manifest["dirty"] is False
