"""Tests for hobbes.extract.testmap — inventory and static reach."""

from pathlib import Path

import pytest

from hobbes.extract import _build_symbol_layer
from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source
from hobbes.extract.testmap import collect_tests, is_test_file

FIXTURE = Path(__file__).parent / "fixtures" / "miniapp"


@pytest.fixture
def tests_doc():
    """Reach over the real symbol layer, built lane-A-only.

    Goes through `_build_symbol_layer` rather than reconstructing edges,
    because since ADR-031 the join is the *only* producer of symbol edges
    — including when lane B is off, where every site falls to the
    fallback arm. The suite runs `HOBBES_SCIP=0` by default (conftest), so
    this is exactly the degraded path P6 promises, exercised on every run
    rather than only when something breaks.
    """
    modules = discover_modules(FIXTURE)
    parsed = {m.id: parse_source((FIXTURE / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    assert _build_symbol_layer(FIXTURE, graph, modules, parsed, None) == []
    return collect_tests(modules, parsed, graph["symbol_edges"])


class TestFileConvention:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("tests/test_core.py", True),
            ("tests/core_test.py", True),
            ("src/app/core.py", False),
            ("src/app/testing.py", False),
        ],
    )
    def test_is_test_file(self, path, expected):
        assert is_test_file(path) is expected


class TestInventory:
    def test_pytest_node_ids(self, tests_doc):
        assert [t["id"] for t in tests_doc] == [
            "tests/test_core.py::TestEngine::test_run",
            "tests/test_core.py::test_top_level",
        ]

    def test_records_carry_location_and_symbol(self, tests_doc):
        top = next(t for t in tests_doc if t["id"].endswith("::test_top_level"))
        assert top["file"] == "tests/test_core.py"
        assert top["symbol"] == "tests.test_core.test_top_level"
        assert top["line"] == 11

    def test_helper_is_not_collected(self, tests_doc):
        assert not any("helper" in t["id"] for t in tests_doc)


class TestReach:
    def test_direct_and_transitive(self, tests_doc):
        top = next(t for t in tests_doc if t["id"].endswith("::test_top_level"))
        # test → top_level → Engine (constructor). engine.run is dynamic
        # dispatch and statically invisible — reach stops there (ADR-007).
        assert top["reaches"] == [
            "miniapp.core.Engine",
            "miniapp.core.top_level",
        ]
        assert top["reaches_modules"] == ["miniapp.core"]

    def test_reach_through_test_helper(self, tests_doc):
        run = next(t for t in tests_doc if t["id"].endswith("::test_run"))
        # test → helper (test-file symbol, kept in reaches) → util.normalize
        assert run["reaches"] == [
            "miniapp.util.normalize",
            "tests.test_core.helper",
        ]
        # …but the modules projection only names source modules.
        assert run["reaches_modules"] == ["miniapp.util"]


class TestCollectionRules:
    def test_class_with_init_is_skipped(self, tmp_path):
        (tmp_path / "test_x.py").write_text(
            "class TestWithInit:\n"
            "    def __init__(self):\n"
            "        pass\n"
            "    def test_skipped(self):\n"
            "        pass\n"
            "class TestOk:\n"
            "    def test_kept(self):\n"
            "        pass\n"
        )
        modules = discover_modules(tmp_path)
        parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
        collected = collect_tests(modules, parsed, [])
        assert [t["id"] for t in collected] == ["test_x.py::TestOk::test_kept"]

    def test_non_test_files_ignored(self, tmp_path):
        (tmp_path / "helpers.py").write_text("def test_looking():\n    pass\n")
        modules = discover_modules(tmp_path)
        parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
        assert collect_tests(modules, parsed, []) == []


class TestReachFollowsCallsOnly:
    """`uses` edges must not widen reach (ADR-029, V2.M3).

    Lane B emits a `uses` edge for a resolution no call site claimed — a
    type annotation, an `except` clause, a value passed by name. They are
    true, and following them would let a test claim it guards code it only
    names. Reach is the basis of "which tests guard this", so it is the one
    number that must never inflate.
    """

    @staticmethod
    def _fixture(tmp_path):
        (tmp_path / "lib.py").write_text(
            "class Widget:\n    pass\n\n\ndef build():\n    return 1\n"
        )
        (tmp_path / "test_x.py").write_text(
            "from lib import Widget, build\n\n\n"
            "def test_one():\n"
            "    w: Widget = None\n"
            "    return build()\n"
        )
        modules = discover_modules(tmp_path)
        parsed = {
            m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules
        }
        return modules, parsed

    def test_uses_edge_is_not_reach(self, tmp_path):
        modules, parsed = self._fixture(tmp_path)
        edges = [
            {"from": "test_x.test_one", "to": "lib.build", "type": "calls",
             "tier": "semantic", "evidence": []},
            {"from": "test_x.test_one", "to": "lib.Widget", "type": "uses",
             "tier": "semantic", "evidence": []},
        ]
        (record,) = collect_tests(modules, parsed, edges)
        assert record["reaches"] == ["lib.build"]
        assert record["reaches_modules"] == ["lib"]

    def test_uses_edge_does_not_extend_the_closure(self, tmp_path):
        """A `uses` edge must not act as a bridge into further code."""
        modules, parsed = self._fixture(tmp_path)
        edges = [
            {"from": "test_x.test_one", "to": "lib.Widget", "type": "uses",
             "tier": "semantic", "evidence": []},
            # Reachable only *through* the uses edge above.
            {"from": "lib.Widget", "to": "lib.build", "type": "calls",
             "tier": "semantic", "evidence": []},
        ]
        (record,) = collect_tests(modules, parsed, edges)
        assert record["reaches"] == []
