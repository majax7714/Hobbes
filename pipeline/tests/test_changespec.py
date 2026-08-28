"""Manifests, the plan-review gate, the change-spec, and `hobbes plan`
(ADR-051). The mapping stages themselves are in test_derive.py."""

import json
import subprocess

import pytest
import yaml

from hobbes import cli
from hobbes.derive import derive_plan, spec_to_dict, write_spec
from hobbes.derive.changespec import format_spec
from hobbes.derive.impact import SeedError
from hobbes.derive.manifests import (
    ComplementError,
    ContextManifest,
    GuaranteeError,
    build_complement,
    build_context_manifests,
    build_policy_manifests,
)
from hobbes.derive.partition import Unit
from tests.test_derive import graph_fixture, make_tests_doc

INVARIANT_I9 = """\
id: I-9
statement: only app.api may import app.auth
scope: src/
status: confirmed
check: graph
rule:
  kind: forbidden-import
  importers: ["*"]
  except: [app.api]
  imported: [app.auth]
guarded_by: [tests/test_api.py::test_handle]
"""


@pytest.fixture
def plan_repo(tmp_path):
    """A committed repo with ingested artifacts and one invariant."""
    repo = tmp_path / "repo"
    (repo / "src" / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "app" / "api.py").write_text("import core\n" * 20)
    (repo / "src" / "app" / "core.py").write_text("def handle():\n    pass\n" * 10)
    (repo / "src" / "app" / "auth.py").write_text("def token():\n    pass\n")
    (repo / "src" / "billing.py").write_text("def charge():\n    pass\n")
    (repo / "tests" / "test_api.py").write_text("def test_handle():\n    pass\n")
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git[:3], "init", "-q"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "one"], check=True)

    derived = repo / ".hobbes" / "derived"
    derived.mkdir(parents=True)
    (derived / "graph.json").write_text(json.dumps(graph_fixture()))
    (derived / "tests.json").write_text(json.dumps(make_tests_doc()))
    invariants = repo / ".hobbes" / "invariants"
    invariants.mkdir()
    (invariants / "I-9.yaml").write_text(INVARIANT_I9)
    return repo


class TestLexicalHubSeeds:
    """ADR-093 (D6): a lexical seed on a hub is context, and a plan whose
    every seed is one refuses with the fix named, never an empty spec."""

    def test_every_seed_a_lexical_hub_is_a_seed_error_naming_the_fix(self, plan_repo):
        from tests.test_derive import hub_graph
        (plan_repo / ".hobbes" / "derived" / "graph.json").write_text(json.dumps(hub_graph()))
        with pytest.raises(SeedError, match="lexical hit on a hub.*app.core.*--seed"):
            derive_plan(plan_repo, "make handle retry")
        # the human's --seed makes the same hub work
        spec = derive_plan(plan_repo, "make handle retry", seeds=["app.core"])
        assert any("app.core" in u.modules for u in spec.units) and spec.seeds_context == {}

    def test_a_lexical_hub_beside_real_work_is_context_and_the_spec_says_so(self, plan_repo):
        from tests.test_derive import hub_graph
        (plan_repo / ".hobbes" / "derived" / "graph.json").write_text(json.dumps(hub_graph()))
        spec = derive_plan(plan_repo, "make handle retry after token refresh")
        assert "app.core" in spec.seeds and "app.core" in spec.seeds_context
        assert not any("app.core" in u.modules for u in spec.units)
        assert "seed is context, not work: app.core" in format_spec(spec)
        assert spec_to_dict(spec)["seeds_context"]["app.core"].startswith("lexical seed on a hub")


class TestComplement:
    def graph_with_tail(self, tail: dict) -> dict:
        graph = graph_fixture()
        graph["resolution_coverage"] = [
            {"file": "src/billing.py", "sites": 12, "resolved": 5,
             "external": 0, "unresolved": 7, "tail": tail},
        ]
        graph["dependency_coverage"] = [
            {"declared": 3, "resolved": 2, "missing": ["stripe"]},
        ]
        graph["extraction_errors"] = [
            {"path": "src", "stage": "scip", "message": "zone degraded"},
            {"path": "web", "stage": "scip", "message": "unrelated"},
        ]
        return graph

    def test_rollup_meanings_gaps_and_degradations(self):
        graph = self.graph_with_tail({"attr-call": 5, "local-binding": 2})
        complement = build_complement(graph, ["src/billing.py"], [])
        assert complement.sites == 12 and complement.unresolved == 7
        assert complement.tail == {"attr-call": 5, "local-binding": 2}
        assert "C-2" in complement.meanings["attr-call"]
        assert complement.cannot_resolve == 5  # local-binding is by design
        assert any("stripe" in gap for gap in complement.environment_gaps)
        assert any("zone degraded" in d for d in complement.degradations)
        assert not any("unrelated" in d for d in complement.degradations)
        assert "C-1" in complement.denominator

    def test_blind_spot_heavy_unit_is_human_first(self, tmp_path):
        graph = self.graph_with_tail({"attr-call": 7})
        unit = Unit(name="U1", modules=["billing"], weight=10)
        [manifest] = build_context_manifests(
            tmp_path, graph, [unit], [], {}, [], []
        )
        assert manifest.human_first
        assert "human" in manifest.human_first_reason

    def test_by_design_tail_does_not_flag(self, tmp_path):
        graph = self.graph_with_tail({"local-binding": 7})
        unit = Unit(name="U1", modules=["billing"], weight=10)
        [manifest] = build_context_manifests(
            tmp_path, graph, [unit], [], {}, [], []
        )
        assert not manifest.human_first


class TestPolicy:
    def context(self, **overrides) -> ContextManifest:
        fields = dict(
            unit="U1",
            modules=[{"id": "billing", "path": "src/billing.py"}],
            guarding_tests=["tests/test_api.py::test_handle"],
            docs=[], invariants=[], boundary=[],
            neighborhood=[{"id": "app.core", "symbols": ["handle"]}],
            complement=build_complement(graph_fixture(), [], []),
        )
        fields.update(overrides)
        return ContextManifest(**fields)

    def test_guarantees_first_and_mounts_from_evidence(self):
        [policy] = build_policy_manifests(
            graph_fixture(), [self.context()], make_tests_doc()
        )
        assert any("tfstate" in g for g in policy.guarantees)
        assert any("push" in g for g in policy.guarantees)
        assert policy.write_mounts == ["src/billing.py", "tests/test_api.py"]
        assert policy.read_signatures == ["src/app/core.py"]
        assert "read-only" in policy.floor

    def test_human_first_narrows_to_no_write_mounts(self):
        manifest = self.context(human_first=True, human_first_reason="x")
        [policy] = build_policy_manifests(
            graph_fixture(), [manifest], make_tests_doc()
        )
        assert policy.write_mounts == []
        assert any("human-first" in f for f in policy.flags)

    def test_widening_across_a_guarantee_raises_not_absorbs(self):
        graph = graph_fixture()
        graph["nodes"].append(
            {"id": "state", "kind": "module", "path": "infra/prod.tfstate"}
        )
        manifest = self.context(
            modules=[{"id": "state", "path": "infra/prod.tfstate"}]
        )
        with pytest.raises(GuaranteeError, match="P10"):
            build_policy_manifests(graph, [manifest], make_tests_doc())


class TestChangeSpec:
    def test_end_to_end_single_unit(self, plan_repo):
        spec = derive_plan(plan_repo, "improve app.core handle")
        assert len(spec.units) == 1
        assert spec.contracts == []
        assert spec.gate.result == "pass"
        [context] = spec.contexts
        assert context.complement is not None
        assert context.invariants == ["I-9"]
        assert context.guarding_tests == ["tests/test_api.py::test_handle"]
        [policy] = spec.policies
        assert "src/app/core.py" in policy.write_mounts

    def test_small_budget_partitions_and_pins_contracts(self, plan_repo):
        spec = derive_plan(plan_repo, "improve app.core handle", budget=100)
        assert len(spec.units) > 1
        assert spec.contracts
        assert all("C-37" in c.pin for c in spec.contracts)

    def test_gate_fails_a_declared_forbidden_edge(self, plan_repo):
        spec = derive_plan(
            plan_repo, "improve app.core handle",
            adds=["billing -> app.auth", "app.api -> app.auth"],
        )
        verdicts = {e.edge: e.verdict for e in spec.gate.proposed_edges}
        assert verdicts["billing -> app.auth"] == "fail"
        assert verdicts["app.api -> app.auth"] == "pass"  # the exception
        assert spec.gate.result == "fail"

    def test_gate_binds_a_module_the_plan_will_create(self, plan_repo):
        # A new module has no path, so scope cannot exclude it — a rule
        # dodged by being new is not a rule.
        spec = derive_plan(
            plan_repo, "improve app.core handle", adds=["brandnew -> app.auth"]
        )
        assert spec.gate.result == "fail"

    def test_same_inputs_write_identical_bytes(self, plan_repo):
        one = write_spec(plan_repo, derive_plan(plan_repo, "improve app.core"))
        first = one.read_bytes()
        two = write_spec(plan_repo, derive_plan(plan_repo, "improve app.core"))
        assert two == one
        assert two.read_bytes() == first
        assert ".hobbes/plans/" in str(one)

    def test_spec_refuses_a_manifest_without_complement(self, plan_repo):
        spec = derive_plan(plan_repo, "improve app.core handle")
        spec.contexts[0].complement = None
        with pytest.raises(ComplementError, match="ADR-047"):
            spec_to_dict(spec)

    def test_c35_and_c36_are_surfaced_in_the_artifact(self, plan_repo):
        spec = derive_plan(plan_repo, "wire billing.retry into app.core")
        document = spec_to_dict(spec)
        assert "C-35" in document["validation"]
        assert document["unresolved_terms"] == ["billing.retry"]
        assert "C-36" in document["unresolved_terms_note"]


class TestPlanCli:
    def test_pass_and_artifact(self, plan_repo, capsys):
        rc = cli.main(["plan", "improve app.core handle", "--repo", str(plan_repo)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "1 unit(s)" in out
        assert "C-35" in out
        assert "change-spec:" in out
        written = plan_repo / ".hobbes" / "plans"
        specs = list(written.rglob("change-spec.yaml"))
        assert len(specs) == 1
        assert yaml.safe_load(specs[0].read_text())["gate"]["result"] == "pass"

    def test_gate_failure_exits_1(self, plan_repo, capsys):
        rc = cli.main([
            "plan", "improve app.core handle", "--repo", str(plan_repo),
            "--adds", "billing -> app.auth",
        ])
        out = capsys.readouterr().out
        assert rc == 1
        assert "FAIL: billing -> app.auth" in out
        assert "I-9" in out

    def test_json_mode(self, plan_repo, capsys):
        rc = cli.main([
            "plan", "improve app.core handle", "--repo", str(plan_repo), "--json",
        ])
        assert rc == 0
        document = json.loads(capsys.readouterr().out)
        assert document["units"][0]["modules"]

    def test_not_ingested_is_2_with_the_fix_named(self, tmp_path, capsys):
        repo = tmp_path / "empty"
        repo.mkdir()
        rc = cli.main(["plan", "anything", "--repo", str(repo)])
        assert rc == 2
        assert "hobbes ingest" in capsys.readouterr().err

    def test_bad_adds_is_2(self, plan_repo, capsys):
        rc = cli.main([
            "plan", "improve app.core", "--repo", str(plan_repo),
            "--adds", "nonsense",
        ])
        assert rc == 2
        assert "from -> to" in capsys.readouterr().err

    def test_unmatched_seed_is_2(self, plan_repo, capsys):
        rc = cli.main([
            "plan", "improve app.core", "--repo", str(plan_repo),
            "--seed", "no.such.node",
        ])
        assert rc == 2
        assert "matches no node" in capsys.readouterr().err

    def test_prose_only_proposal_is_2_naming_seed(self, plan_repo, capsys):
        rc = cli.main([
            "plan", "improve resilience generally", "--repo", str(plan_repo),
        ])
        assert rc == 2
        assert "--seed" in capsys.readouterr().err
