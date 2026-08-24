"""Tests for hobbes.extract.terraform — HCL nodes, edges, joins, plan."""

from pathlib import Path

import pytest

from hobbes.extract.discover import discover_modules
from hobbes.extract.terraform import PlanError, extract_terraform

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"
PLAN = Path(__file__).parent / "fixtures" / "plans" / "miniapp-plan.json"


@pytest.fixture(scope="module")
def infra():
    return extract_terraform(FIXTURE, discover_modules(FIXTURE))


def edge_set(infra, edge_type):
    return {
        (e["from"], e["to"])
        for e in infra["module_edges"]
        if e["type"] == edge_type
    }


class TestNodes:
    def test_declared_blocks_become_nodes(self, infra):
        by_id = {n["id"]: n for n in infra["nodes"]}
        assert by_id["tf:aws_lambda_function.worker"]["kind"] == "resource"
        assert by_id["tf:aws_iam_role.worker"]["kind"] == "resource"
        assert by_id["tf:data.archive_file.worker"]["kind"] == "data"
        assert by_id["tf:aws_lambda_function.worker"]["path"] == "infra/main.tf"

    def test_undeclared_references_create_nothing(self, infra):
        assert not any(
            "cognito" in n["id"] for n in infra["nodes"]
        ), "undeclared aws_cognito_user_pool.absent must not become a node"

    def test_tf_file_count(self, infra):
        assert infra["tf_file_count"] == 1


class TestReferences:
    def test_declared_references_edge(self, infra):
        refs = edge_set(infra, "references")
        assert ("tf:aws_lambda_function.worker", "tf:aws_iam_role.worker") in refs
        assert (
            "tf:aws_lambda_function.worker",
            "tf:data.archive_file.worker",
        ) in refs

    def test_undeclared_reference_dropped(self, infra):
        assert not any(
            "cognito" in target for _, target in edge_set(infra, "references")
        )

    def test_evidence_points_into_the_tf_file(self, infra):
        edge = next(
            e
            for e in infra["module_edges"]
            if e["from"] == "tf:aws_lambda_function.worker"
            and e["to"] == "tf:aws_iam_role.worker"
        )
        # The infra layer goes through the same v4 edge constructor as the
        # app layer (ADR-028) — one vocabulary, not one per extractor.
        assert edge["evidence"] == [
            {"path": "infra/main.tf", "line": 17, "lane": "tree-sitter"}
        ]
        assert edge["tier"] == "syntactic"


class TestEnvJoin:
    def test_env_set_edges_and_nodes(self, infra):
        env = edge_set(infra, "env-set")
        assert ("tf:aws_lambda_function.worker", "env:MINIAPP_MODE") in env
        assert ("tf:aws_lambda_function.worker", "env:MINIAPP_HOME") in env
        kinds = {n["id"]: n["kind"] for n in infra["nodes"]}
        assert kinds["env:MINIAPP_MODE"] == "env"

    def test_env_block_name_pattern(self, tmp_path):
        (tmp_path / "main.tf").write_text(
            'resource "docker_container" "app" {\n'
            "  env {\n"
            '    name  = "APP_TOKEN"\n'
            '    value = "x"\n'
            "  }\n"
            "}\n"
        )
        infra = extract_terraform(tmp_path, [])
        assert ("tf:docker_container.app", "env:APP_TOKEN") in edge_set(
            infra, "env-set"
        )


class TestPackagesJoin:
    def test_archive_source_resolves_to_module(self, infra):
        assert (
            "tf:data.archive_file.worker",
            "miniapp.cli",
        ) in edge_set(infra, "packages")

    def test_non_module_paths_produce_nothing(self, infra):
        packaged = {target for _, target in edge_set(infra, "packages")}
        assert packaged == {"miniapp.cli"}  # build/worker.zip etc. resolve nowhere


class TestPlan:
    def test_plan_adds_nodes_and_resolved_references(self):
        infra = extract_terraform(FIXTURE, discover_modules(FIXTURE), tf_plan=PLAN)
        by_id = {n["id"]: n for n in infra["nodes"]}
        assert by_id["tf:aws_cloudwatch_log_group.worker"]["kind"] == "resource"
        refs = edge_set(infra, "references")
        assert (
            "tf:aws_cloudwatch_log_group.worker",
            "tf:aws_lambda_function.worker",
        ) in refs

    def test_var_references_in_plan_dropped(self):
        infra = extract_terraform(FIXTURE, discover_modules(FIXTURE), tf_plan=PLAN)
        assert not any("var." in t for _, t in edge_set(infra, "references"))

    def test_tfstate_lookalike_refused(self, tmp_path):
        lookalike = tmp_path / "terraform.tfstate"
        lookalike.write_text("{}")
        with pytest.raises(PlanError, match="state"):
            extract_terraform(FIXTURE, [], tf_plan=lookalike)

    def test_unreadable_plan_is_a_clear_error(self, tmp_path):
        bad = tmp_path / "plan.json"
        bad.write_text("not json")
        with pytest.raises(PlanError, match="plan JSON"):
            extract_terraform(FIXTURE, [], tf_plan=bad)


class TestNoTerraform:
    def test_repo_without_tf_is_empty(self, tmp_path):
        infra = extract_terraform(tmp_path, [])
        assert infra == {"nodes": [], "module_edges": [], "tf_file_count": 0}


class TestDeterminism:
    def test_two_extractions_identical(self):
        modules = discover_modules(FIXTURE)
        assert extract_terraform(FIXTURE, modules) == extract_terraform(
            FIXTURE, modules
        )
