"""The plan derivation's mapping stages (ADR-051): impact, co-change,
partition, contracts. The end-to-end command is in test_changespec.py."""

import subprocess

import pytest

from hobbes.derive import cochange, impact, partition
from hobbes.derive.contracts import build_contracts
from hobbes.derive.impact import SeedError, build_impact, resolve_seeds
from hobbes.derive.partition import Unit, build_units, guarding_tests, is_deferred, context_seeds, unit_modules
from hobbes.invariants.schema import Invariant


def graph_fixture() -> dict:
    """A four-module app with env/ext nodes and mixed-tier edges."""
    return {
        "schema_version": 4,
        "sha": "a" * 40,
        "dirty": False,
        "languages": ["python"],
        "nodes": [
            {"id": "app.api", "kind": "module", "path": "src/app/api.py"},
            {"id": "app.core", "kind": "module", "path": "src/app/core.py"},
            {"id": "app.auth", "kind": "module", "path": "src/app/auth.py"},
            {"id": "billing", "kind": "module", "path": "src/billing.py"},
            {"id": "env:HOME", "kind": "env", "name": "HOME"},
            {"id": "ext:react", "kind": "external"},
        ],
        "module_edges": [
            {"from": "app.api", "to": "app.core", "type": "imports",
             "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 1, "lane": "scip"}]},
            {"from": "app.api", "to": "ext:react", "type": "imports",
             "tier": "syntactic",
             "evidence": [{"path": "src/app/api.py", "line": 2, "lane": "tree-sitter"}]},
            {"from": "app.api", "to": "env:HOME", "type": "env-read",
             "tier": "syntactic",
             "evidence": [{"path": "src/app/api.py", "line": 3, "lane": "tree-sitter"}]},
        ],
        "symbols": [
            {"id": "app.core.handle", "kind": "function", "module": "app.core",
             "name": "handle", "qualname": "handle", "line": 3, "end_line": 9},
            {"id": "app.auth.token", "kind": "function", "module": "app.auth",
             "name": "token", "qualname": "token", "line": 1, "end_line": 4},
            {"id": "billing.charge", "kind": "function", "module": "billing",
             "name": "charge", "qualname": "charge", "line": 1, "end_line": 5},
        ],
        "symbol_edges": [
            {"from": "app.api", "to": "app.core.handle", "type": "calls",
             "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 5, "lane": "scip"}]},
            {"from": "app.api", "to": "app.auth.token", "type": "calls",
             "tier": "semantic",
             "evidence": [{"path": "src/app/api.py", "line": 6, "lane": "scip"}]},
            {"from": "billing", "to": "app.core.handle", "type": "calls",
             "tier": "syntactic",
             "evidence": [{"path": "src/billing.py", "line": 2, "lane": "tree-sitter"}]},
        ],
        "resolution_coverage": [],
        "dependency_coverage": [],
        "extraction_errors": [],
    }


def make_tests_doc() -> dict:
    return {
        "schema_version": 4,
        "sha": "a" * 40,
        "dirty": False,
        "tests": [
            {"id": "tests/test_api.py::test_handle", "file": "tests/test_api.py",
             "framework": "pytest", "line": 3, "reaches": ["app.core.handle"]},
        ],
    }


def hub_graph() -> dict:
    """The fixture with ``app.core`` made a hub: thirty extra modules import it."""
    graph = graph_fixture()
    for i in range(30):
        mid = f"imp.m{i}"
        graph["nodes"].append({"id": mid, "kind": "module", "path": f"src/imp/m{i}.py", "language": "python"})
        graph["module_edges"].append({"from": mid, "to": "app.core", "type": "imports", "tier": "syntactic"})
    return graph


class TestSeeds:
    def test_explicit_node_id(self):
        seeds, _ = resolve_seeds(graph_fixture(), "", ["app.core"])
        assert seeds == {"app.core": "app.core"}

    def test_explicit_symbol_and_path_land_on_the_module(self):
        seeds, _ = resolve_seeds(graph_fixture(), "", ["app.core.handle"])
        assert "app.core" in seeds
        seeds, _ = resolve_seeds(graph_fixture(), "", ["src/app/core.py"])
        assert "app.core" in seeds

    def test_explicit_path_suffix_when_unambiguous(self):
        seeds, _ = resolve_seeds(graph_fixture(), "", ["core.py"])
        assert "app.core" in seeds

    def test_explicit_miss_is_an_error(self):
        with pytest.raises(SeedError, match="matches no node"):
            resolve_seeds(graph_fixture(), "", ["nonexistent.thing"])

    def test_proposal_terms_match_ids_and_symbol_names(self):
        seeds, unresolved = resolve_seeds(
            graph_fixture(), "harden app.core so handle is retried", []
        )
        assert "app.core" in seeds
        assert unresolved == []

    def test_code_shaped_misses_are_reported_not_guessed(self):
        _, unresolved = resolve_seeds(
            graph_fixture(), "wire billing.retry into app.core", []
        )
        assert unresolved == ["billing.retry"]

    def test_prose_misses_are_silent(self):
        _, unresolved = resolve_seeds(
            graph_fixture(), "make app.core resilient tomorrow", []
        )
        assert unresolved == []

    def test_prose_hits_are_set_aside_when_code_shaped_seeds_exist(self):
        # "handle" and "token" are prose words that equal symbol names; with
        # a code-shaped seed present they are set aside and said so (C-36).
        graph = graph_fixture()
        graph["nodes"].append({"id": "app", "kind": "package", "path": "src/app/__init__.py"})
        result = build_impact(graph, "make billing.charge handle token refresh in app", [])
        assert "billing" in result.seeds
        assert "app.core" not in result.seeds and "app.auth" not in result.seeds
        assert "prose-shaped term 'handle'" in result.seeds_rejected["app.core"]
        # the package node is the whole tree, not the change
        assert "package node" in result.seeds_rejected["app"]
        assert "app" not in result.seeds

    def test_prose_hits_stay_when_named_as_code(self):
        result = build_impact(graph_fixture(), "billing.charge must call `handle` twice", [])
        assert "app.core" in result.seeds and result.seeds_rejected == {}
        result = build_impact(graph_fixture(), "billing.charge must call handle() twice", [])
        assert "app.core" in result.seeds

    def test_prose_hits_seed_alone_when_nothing_better_exists(self):
        result = build_impact(graph_fixture(), "make handle retry", [])
        assert result.seeds == {"app.core": "handle"} and result.seeds_rejected == {}

    def test_explicit_seeds_are_never_set_aside(self):
        graph = graph_fixture()
        graph["nodes"].append({"id": "app", "kind": "package", "path": "src/app/__init__.py"})
        result = build_impact(graph, "billing.charge", ["app", "handle"])
        assert {"app", "app.core", "billing"} <= set(result.seeds)
        assert result.seeds_rejected == {}

    def test_nothing_seeds_is_an_error_naming_the_fix(self):
        with pytest.raises(SeedError, match="--seed"):
            build_impact(graph_fixture(), "improve resilience generally", [])


class TestExpansion:
    def test_distance_attenuates_even_along_semantic_edges(self):
        result = build_impact(graph_fixture(), "app.core", [])
        scores = result.scores
        assert scores["app.core"] == 1.0
        assert scores["app.api"] == pytest.approx(0.55)   # semantic calls, 1 hop
        assert scores["billing"] == pytest.approx(0.33)   # syntactic calls, 1 hop
        assert scores["app.auth"] == pytest.approx(0.3025)  # semantic, 2 hops

    def test_env_and_ext_nodes_are_impact_but_not_units(self):
        result = build_impact(graph_fixture(), "app.api", [])
        assert "ext:react" in result.scores
        assert "env:HOME" in result.scores
        modules = unit_modules(graph_fixture(), result.scores)
        assert modules == ["app.api", "app.auth", "app.core"]

    def test_a_lexical_seed_on_a_hub_is_context_not_work(self):
        # D6 (ADR-093): sklearn's issue said `astype`, the word hit a
        # symbol in a module 2,543 tests reach, and seed-always-work made
        # the hub a unit's interior. A proposal-text hit does not override
        # ADR-083's hub rule; a human's --seed or the planner's name does.
        graph = hub_graph()
        result = build_impact(graph, "make handle retry", [])
        assert result.seeds == {"app.core": "handle"} and result.seeds_lexical == ["app.core"]
        assert "app.core" not in unit_modules(graph, result.scores, result.seeds_lexical)
        assert "app.core" in unit_modules(graph, result.scores)  # the pre-093 call: a seed is work
        reasons = context_seeds(graph, result.scores, result.seeds_lexical)
        assert set(reasons) == {"app.core"} and "a hub (32 importers, fan-in >= 30)" in reasons["app.core"]
        assert "--seed" in reasons["app.core"]
        # the seed still expanded: its neighbors are in the impact set
        assert "app.api" in result.scores

    def test_an_explicit_seed_on_a_hub_stays_work(self):
        graph = hub_graph()
        result = build_impact(graph, "make handle retry", ["app.core"])
        assert result.seeds_lexical == []
        assert "app.core" in unit_modules(graph, result.scores, result.seeds_lexical)
        assert context_seeds(graph, result.scores, result.seeds_lexical) == {}

    def test_the_threshold_cuts_the_far_tail(self):
        # Two hops out through a syntactic chain falls below 0.2.
        result = build_impact(graph_fixture(), "app.api", [])
        assert "billing" not in result.scores

    def test_expansion_is_deterministic(self):
        one = build_impact(graph_fixture(), "app.core", []).scores
        two = build_impact(graph_fixture(), "app.core", []).scores
        assert one == two


class TestCoChange:
    def test_co_committed_files_strengthen(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git[:3], "init", "-q"], check=True)
        for round_ in range(3):
            (repo / "a.py").write_text(f"a{round_}")
            (repo / "b.py").write_text(f"b{round_}")
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "commit", "-qm", f"r{round_}"], check=True)
        history = cochange.observe(repo)
        assert history.warning == ""
        assert history.factor("a.py", "b.py") == pytest.approx(1.75)
        assert history.factor("a.py", "c.py") == 1.0

    def test_unreadable_history_degrades_visibly(self, tmp_path):
        history = cochange.observe(tmp_path / "not-a-repo")
        assert "structure-only" in history.warning
        assert history.factor("a.py", "b.py") == 1.0


class TestPartition:
    def test_contained_change_is_one_unit(self):
        weights = {"a": 10, "b": 10}
        units = build_units(["a", "b"], weights, {("a", "b"): 5.0}, budget=100)
        assert len(units) == 1
        assert units[0].modules == ["a", "b"]

    def test_budget_forces_a_cut_at_the_weakest_coupling(self):
        weights = {"a": 60, "b": 60, "c": 60}
        coupling = {("a", "b"): 9.0, ("b", "c"): 1.0}
        units = build_units(["a", "b", "c"], weights, coupling, budget=130)
        by_modules = sorted(tuple(u.modules) for u in units)
        assert by_modules == [("a", "b"), ("c",)]

    def test_agent_count_is_the_output(self):
        weights = {"a": 60, "b": 60, "c": 60}
        coupling = {("a", "b"): 9.0, ("b", "c"): 1.0}
        assert len(build_units(["a", "b", "c"], weights, coupling, 500)) == 1
        assert len(build_units(["a", "b", "c"], weights, coupling, 130)) == 2
        assert len(build_units(["a", "b", "c"], weights, coupling, 60)) == 3

    def test_oversize_module_is_flagged_not_split(self):
        units = build_units(["a"], {"a": 500}, {}, budget=100)
        assert any("oversize" in f for f in units[0].flags)

    def test_unabsorbable_tiny_unit_is_flagged_coordination_heavy(self):
        # b is 100 tokens against one 300-token contract, and a has no
        # room: the design's §7 rule fires and says so.
        weights = {"a": 59_950, "b": 100}
        units = build_units(["a", "b"], weights, {("a", "b"): 2.0}, budget=60_000)
        small = next(u for u in units if u.modules == ["b"])
        assert any("coordination-heavy" in f for f in small.flags)

    def test_tiny_unit_merges_into_its_neighbor_when_room_exists(self):
        weights = {"a": 500, "b": 100}
        units = build_units(["a", "b"], weights, {("a", "b"): 2.0}, budget=60_000)
        assert len(units) == 1

    def test_deterministic(self):
        weights = {"a": 60, "b": 60, "c": 60, "d": 60}
        coupling = {("a", "b"): 2.0, ("c", "d"): 2.0, ("b", "c"): 2.0}
        one = build_units(["a", "b", "c", "d"], weights, coupling, 130)
        two = build_units(["a", "b", "c", "d"], weights, coupling, 130)
        assert [(u.name, u.modules) for u in one] == [(u.name, u.modules) for u in two]


class TestWeights:
    def test_node_weight_counts_module_tests_and_doc(self, tmp_path):
        graph, tests = graph_fixture(), make_tests_doc()
        (tmp_path / "src/app").mkdir(parents=True)
        (tmp_path / "tests").mkdir()
        (tmp_path / "src/app/core.py").write_text("x" * 400)
        (tmp_path / "tests/test_api.py").write_text("y" * 200)
        docs = tmp_path / ".hobbes/derived/docs/modules"
        docs.mkdir(parents=True)
        (docs / "app.core.json").write_text("z" * 100)
        weights = partition.node_weights(tmp_path, graph, tests)
        assert weights["app.core"] == (400 + 200 + 100) // 4
        # Files the tree no longer holds count zero, not an error.
        assert weights["billing"] == 0

    def test_guarding_tests_map_reach_to_modules(self):
        guards = guarding_tests(graph_fixture(), make_tests_doc())
        assert guards == {"app.core": ["tests/test_api.py::test_handle"]}


class TestCoupling:
    def test_cochange_multiplies_structural_coupling(self, tmp_path):
        graph = graph_fixture()
        flat = cochange.CoChange(__import__("collections").Counter())
        base = partition.module_coupling(graph, ["app.api", "app.core"], flat)
        strengthened = partition.module_coupling(
            graph, ["app.api", "app.core"],
            cochange.CoChange(__import__("collections").Counter(
                {("src/app/api.py", "src/app/core.py"): 4}
            )),
        )
        key = ("app.api", "app.core")
        assert strengthened[key] == pytest.approx(base[key] * 2.0)


def _invariant(**overrides) -> Invariant:
    fields = dict(
        id="I-9", statement="only app.api may import app.auth", scope="src/",
        status="confirmed", check="graph", target="",
        rule={"kind": "forbidden-import", "importers": ["*"],
              "except": ["app.api"], "imported": ["app.auth"]},
        guarded_by=[], source="test",
    )
    fields.update(overrides)
    return Invariant(**fields)


class TestContracts:
    def two_units(self):
        return [
            Unit(name="U1", modules=["app.api", "app.auth"], weight=10),
            Unit(name="U2", modules=["app.core", "billing"], weight=10),
        ]

    def test_cut_edges_become_contracts_with_declaration_sites(self):
        contracts = build_contracts(graph_fixture(), self.two_units(), [])
        crossing = {(c.caller, c.target) for c in contracts}
        assert ("app.api", "app.core.handle") in crossing
        assert ("app.api", "app.core") in crossing  # the module import
        handle = next(c for c in contracts if c.target == "app.core.handle")
        assert handle.declared_at == "src/app/core.py:3-9"
        assert handle.target_kind == "function"
        assert handle.owner == "U2"  # the definition side owns migration
        assert "C-37" in handle.pin

    def test_interior_edges_are_not_contracts(self):
        contracts = build_contracts(graph_fixture(), self.two_units(), [])
        assert not any(c.caller == "billing" and c.target == "app.core.handle"
                       for c in contracts)

    def test_in_scope_invariants_ride_the_contract(self):
        contracts = build_contracts(
            graph_fixture(), self.two_units(), [_invariant()]
        )
        assert all("I-9" in c.invariants for c in contracts)

    def test_one_unit_means_no_contracts(self):
        unit = Unit(name="U1", weight=10,
                    modules=["app.api", "app.auth", "app.core", "billing"])
        assert build_contracts(graph_fixture(), [unit], []) == []


class TestUnitCap:
    """ADR-058, restated by the harness restructure: the cap selects —
    defers the lowest-impact units — and merges only seed-bearing ones."""

    def test_cap_defers_the_lowest_impact_units_never_a_seed(self):
        weights = {"a": 50, "b": 50, "c": 50, "d": 10}
        scores = {"a": 1.0, "b": 0.3, "c": 0.55, "d": 0.2}
        units = build_units(list(weights), weights, {}, budget=60, max_units=2, scores=scores)
        kept = [u for u in units if not is_deferred(u)]
        deferred = [u for u in units if is_deferred(u)]
        assert [u.modules for u in kept] == [["a"], ["c"]]
        assert [u.modules for u in deferred] == [["b"], ["d"]]
        assert deferred[0].name == "D1" and "best impact score 0.300" in deferred[0].flags[0]
        assert not any(f.startswith("capped") for u in kept for f in u.flags)

    def test_seed_units_merge_when_they_alone_exceed_the_cap(self):
        weights = {"a": 50, "b": 50, "c": 50, "d": 10}
        scores = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 0.2}
        coupling = {("a", "b"): 5.0}
        units = build_units(list(weights), weights, coupling, budget=60, max_units=2, scores=scores)
        kept = [u for u in units if not is_deferred(u)]
        assert [u.modules for u in kept] == [["a", "b"], ["c"]]
        assert any(f.startswith("capped") for f in kept[0].flags)
        assert [u.modules for u in units if is_deferred(u)] == [["d"]]

    def test_no_cap_leaves_the_budgeted_partition_alone(self):
        weights = {"a": 50, "b": 50, "c": 50, "d": 50}
        assert len(build_units(list(weights), weights, {}, budget=60)) == 4
        assert len(build_units(list(weights), weights, {}, budget=60, max_units=None)) == 4

    def test_without_scores_the_lightest_are_deferred(self):
        weights = {"a": 50, "b": 50, "c": 50, "d": 10}
        units = build_units(list(weights), weights, {("a", "b"): 5.0}, budget=60, max_units=2)
        kept = [u.modules for u in units if not is_deferred(u)]
        assert kept == [["a"], ["b"]]
        assert [u.modules for u in units if is_deferred(u)] == [["c"], ["d"]]

    def test_cap_flags_only_the_seed_units_it_merged(self):
        weights = {"a": 50, "b": 50, "c": 50}
        scores = {"a": 1.0, "b": 1.0, "c": 1.0}
        units = build_units(list(weights), weights, {("a", "b"): 1.0}, budget=60, max_units=2, scores=scores)
        flagged = {tuple(u.modules): any(f.startswith("capped") for f in u.flags) for u in units}
        assert flagged == {("a", "b"): True, ("c",): False}

    def test_cap_is_deterministic(self):
        weights = {f"m{i}": 30 for i in range(12)}
        scores = {f"m{i}": 1.0 if i % 4 == 0 else 0.3 for i in range(12)}
        coupling = {("m1", "m5"): 2.0, ("m2", "m9"): 2.0, ("m0", "m11"): 0.5}
        one = build_units(list(weights), weights, coupling, budget=40, max_units=3, scores=scores)
        two = build_units(list(weights), weights, coupling, budget=40, max_units=3, scores=scores)
        assert [u.modules for u in one] == [u.modules for u in two]
        assert len([u for u in one if not is_deferred(u)]) == 3

    def test_cap_below_one_is_ignored(self):
        weights = {"a": 50, "b": 50}
        assert len(build_units(list(weights), weights, {}, budget=60, max_units=0)) == 2

    def test_plan_records_the_cap_and_the_summary_counts_it(self, tmp_path):
        from hobbes.derive import changespec
        from hobbes.derive.partition import Unit
        import dataclasses
        unit = Unit(name="U1", modules=["a", "b"], weight=10, flags=["capped: merged to meet the unit cap (max_units=1)"])
        spec = changespec.ChangeSpec(
            task="t", proposal="p", graph_sha="s", graph_dirty=False, budget=60_000, seeds={},
            unresolved_terms=[], units=[unit], contracts=[], contexts=[], policies=[],
            gate=changespec.Gate(proposed_edges=[], human_first_units=[], result="pass"), max_units=1,
        )
        assert changespec.spec_to_dict(spec)["max_units"] == 1
        text = changespec.format_spec(spec)
        assert "1-unit cap (1 capped, 0 deferred, C-44)" in text
