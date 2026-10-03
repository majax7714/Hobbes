"""Tests for hobbes.extract.terraform — HCL nodes, edges, joins, plan."""

import json
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
        assert by_id["tf:infra:aws_lambda_function.worker"]["kind"] == "resource"
        assert by_id["tf:infra:aws_iam_role.worker"]["kind"] == "resource"
        assert by_id["tf:infra:data.archive_file.worker"]["kind"] == "data"
        assert by_id["tf:infra:aws_lambda_function.worker"]["path"] == "infra/main.tf"

    def test_undeclared_references_create_nothing(self, infra):
        assert not any(
            "cognito" in n["id"] for n in infra["nodes"]
        ), "undeclared aws_cognito_user_pool.absent must not become a node"

    def test_tf_file_count(self, infra):
        assert infra["tf_file_count"] == 1


class TestReferences:
    def test_declared_references_edge(self, infra):
        refs = edge_set(infra, "references")
        assert ("tf:infra:aws_lambda_function.worker", "tf:infra:aws_iam_role.worker") in refs
        assert (
            "tf:infra:aws_lambda_function.worker",
            "tf:infra:data.archive_file.worker",
        ) in refs

    def test_undeclared_reference_dropped(self, infra):
        assert not any(
            "cognito" in target for _, target in edge_set(infra, "references")
        )

    def test_evidence_points_into_the_tf_file(self, infra):
        edge = next(
            e
            for e in infra["module_edges"]
            if e["from"] == "tf:infra:aws_lambda_function.worker"
            and e["to"] == "tf:infra:aws_iam_role.worker"
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
        assert ("tf:infra:aws_lambda_function.worker", "env:MINIAPP_MODE") in env
        assert ("tf:infra:aws_lambda_function.worker", "env:MINIAPP_HOME") in env
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
        assert ("tf:.:docker_container.app", "env:APP_TOKEN") in edge_set(
            infra, "env-set"
        )


class TestPackagesJoin:
    def test_archive_source_resolves_to_module(self, infra):
        assert (
            "tf:infra:data.archive_file.worker",
            "miniapp.cli",
        ) in edge_set(infra, "packages")

    def test_non_module_paths_produce_nothing(self, infra):
        packaged = {target for _, target in edge_set(infra, "packages")}
        assert packaged == {"miniapp.cli"}  # build/worker.zip etc. resolve nowhere


class TestPlan:
    def test_plan_adds_nodes_and_resolved_references(self):
        infra = extract_terraform(FIXTURE, discover_modules(FIXTURE), tf_plan=PLAN)
        by_id = {n["id"]: n for n in infra["nodes"]}
        assert by_id["tf:infra:aws_cloudwatch_log_group.worker"]["kind"] == "resource"
        refs = edge_set(infra, "references")
        assert (
            "tf:infra:aws_cloudwatch_log_group.worker",
            "tf:infra:aws_lambda_function.worker",
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
        assert infra == {
            "nodes": [], "module_edges": [], "tf_file_count": 0, "errors": []
        }


class TestDeterminism:
    def test_two_extractions_identical(self):
        modules = discover_modules(FIXTURE)
        assert extract_terraform(FIXTURE, modules) == extract_terraform(
            FIXTURE, modules
        )


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


class TestDirectoryScope:
    """ADR-173: a reference resolves in its own directory, as Terraform's does."""

    def test_reference_to_another_directorys_address_refused(self, tmp_path):
        _write(tmp_path, {
            "net/main.tf": 'resource "aws_vpc" "v" {}\n',
            "stage/main.tf": 'resource "aws_flow_log" "fl" {\n  vpc_id = aws_vpc.v.id\n}\n',
        })
        infra = extract_terraform(tmp_path, [])
        assert edge_set(infra, "references") == set()
        assert "1 reference(s) to an address declared only in another directory refused" in (
            infra["errors"][0]["message"]
        )

    def test_same_directory_reference_kept_across_files(self, tmp_path):
        _write(tmp_path, {
            "net/a.tf": 'resource "aws_vpc" "v" {}\n',
            "net/b.tf": 'resource "aws_subnet" "s" {\n  vpc_id = aws_vpc.v.id\n}\n',
        })
        infra = extract_terraform(tmp_path, [])
        assert edge_set(infra, "references") == {("tf:net:aws_subnet.s", "tf:net:aws_vpc.v")}

    def test_one_address_in_two_directories_is_two_nodes(self, tmp_path):
        """C-187 lifted (ADR-173's amendment): each directory's block is its own
        node, and each directory's reference reaches its own."""
        files = 'resource "aws_s3_bucket" "logs" {}\nresource "aws_s3_bucket_policy" "p" {\n  bucket = aws_s3_bucket.logs.id\n}\n'
        _write(tmp_path, {"envs/dev/main.tf": files, "envs/prod/main.tf": files})
        infra = extract_terraform(tmp_path, [])
        assert {n["id"] for n in infra["nodes"]} == {
            "tf:envs/dev:aws_s3_bucket.logs", "tf:envs/dev:aws_s3_bucket_policy.p",
            "tf:envs/prod:aws_s3_bucket.logs", "tf:envs/prod:aws_s3_bucket_policy.p",
        }
        assert edge_set(infra, "references") == {
            ("tf:envs/dev:aws_s3_bucket_policy.p", "tf:envs/dev:aws_s3_bucket.logs"),
            ("tf:envs/prod:aws_s3_bucket_policy.p", "tf:envs/prod:aws_s3_bucket.logs"),
        }
        assert "C-187" not in infra["errors"][0]["message"]

    def test_root_directory_is_dot(self, tmp_path):
        _write(tmp_path, {"main.tf": 'resource "aws_vpc" "v" {}\n'})
        assert [n["id"] for n in extract_terraform(tmp_path, [])["nodes"]] == ["tf:.:aws_vpc.v"]


class TestPlanDirectory:
    """A plan names no directory: its root module is inferred or refused."""

    def _plan(self, tmp_path, addresses):
        plan = tmp_path / "plan.json"
        plan.write_text(json.dumps({"configuration": {"root_module": {"resources": [
            {"address": a, "expressions": {}} for a in addresses
        ]}}}))
        return plan

    def test_directory_declaring_every_shared_address(self, tmp_path):
        _write(tmp_path, {
            "a/main.tf": 'resource "aws_vpc" "v" {}\nresource "aws_subnet" "s" {}\n',
            "b/main.tf": 'resource "aws_vpc" "v" {}\n',
        })
        plan = self._plan(tmp_path, ["aws_vpc.v", "aws_subnet.s", "aws_eip.only_planned"])
        infra = extract_terraform(tmp_path, [], tf_plan=plan)
        assert "tf:a:aws_eip.only_planned" in {n["id"] for n in infra["nodes"]}
        assert not any(e["stage"] == "hcl-plan" for e in infra["errors"])

    def test_ambiguous_plan_adds_nothing_and_says_so(self, tmp_path):
        both = 'resource "aws_vpc" "v" {}\n'
        _write(tmp_path, {"a/main.tf": both, "b/main.tf": both})
        plan = self._plan(tmp_path, ["aws_vpc.v", "aws_eip.only_planned"])
        infra = extract_terraform(tmp_path, [], tf_plan=plan)
        assert not any("only_planned" in n["id"] for n in infra["nodes"])
        (record,) = [e for e in infra["errors"] if e["stage"] == "hcl-plan"]
        assert "plan adds nothing (ADR-173, C-193)" in record["message"]


class TestLayerRecord:
    """ADR-173: one ``hcl-layer`` record per ingest, ``hcl-parse`` per damaged file."""

    def test_counts_what_the_layer_does_not_read(self, tmp_path):
        _write(tmp_path, {
            "main.tf": (
                'locals {\n  a = 1\n}\n'
                'variable "v" {}\n'
                'output "o" {\n  value = 1\n}\n'
                'module "net" {\n  source = "./modules/net"\n}\n'
                'module "vpc" {\n  source = "terraform-aws-modules/vpc/aws"\n}\n'
            ),
            "extra.tf.json": "{}",
            "x.tofu": "",
        })
        infra = extract_terraform(tmp_path, [])
        (record,) = infra["errors"]
        assert record["stage"] == "hcl-layer" and record["path"] == "."
        message = record["message"]
        assert "read 1 .tf file(s)" in message
        assert "1 `locals`, 1 `variable` and 1 `output` block(s) are not nodes" in message
        assert "2 module call(s) (1 local, 1 registry or remote)" in message
        assert "2 .tf.json or .tofu file(s) not read: extra.tf.json, x.tofu (C-192)" in message
        for entry in ("C-188", "C-189", "C-190", "C-191"):
            assert entry in message
        assert "C-187" not in message  # nothing shared, nothing refused

    def test_swallowed_block_is_named_by_a_parse_record(self, tmp_path):
        _write(tmp_path, {"main.tf": (
            'resource "a" "x" {\n  name = "b"\n\n'
            'resource "aws_iam_role" "swallowed" {\n  name = "s"\n}\n'
        )})
        infra = extract_terraform(tmp_path, [])
        assert "tf:.:aws_iam_role.swallowed" not in {n["id"] for n in infra["nodes"]}
        stages = [(e["stage"], e["path"]) for e in infra["errors"]]
        assert stages == [("hcl-layer", "."), ("hcl-parse", "main.tf")]
        assert "(C-192)" in infra["errors"][1]["message"]

    def test_tf_json_is_not_detected_as_tf(self, tmp_path):
        _write(tmp_path, {"only.tf.json": "{}"})
        assert extract_terraform(tmp_path, [])["tf_file_count"] == 0
