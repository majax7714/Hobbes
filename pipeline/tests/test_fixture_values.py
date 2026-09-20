"""A call on the value a fixture constructs is a call on that class
(ADR-145).

``def runner(): return Runner()`` fixes the runtime class of what the
parameter holds — a construction is never a subclass — so ``runner.m(…)``
written in the test's own body is a call on ``Runner.m``. The index
emits nothing at ``m`` (scip-python does not type an unannotated
parameter), so there is no occurrence for the join to match: the rule
reads the two hops the graph already carries, the ``uses`` injection and
the ``semantic`` edge from the fixture to the class it constructs.

The cases below hand :func:`hobbes.extract.fixtures.value_calls` a graph
whose class edge is written out, because that edge is exactly what the
rule is allowed to believe. Each refusal has a case of its own: the four
conditions fail toward drawing less, and what each one declined is the
size of what a construction did not settle.
"""

from pathlib import Path

import pytest

from hobbes.extract.discover import discover_modules
from hobbes.extract.fixtures import (
    ALREADY_DRAWN,
    FIXTURE_VALUE,
    NO_CLASS_EDGE,
    NO_CONSTRUCTION,
    NO_METHOD,
    PROPERTY,
    REBOUND,
    VALUE_REASONS,
    injections,
    value_calls,
)
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import LANE_SCIP, SEMANTIC, SYNTACTIC, tiered_edge

MINIFIXVAL = Path(__file__).parent / "fixtures" / "minifixval"

#: `Runner.invoke` is one `def` in the class's own body; the class is on
#: line 1 and the method on line 2.
TESTING = "class Runner:\n    def invoke(self, x):\n        return x\n"

#: The fixture constructs it on line 8 — the line the class edge's
#: evidence has to sit on for condition 3 to hold.
CONFTEST = (
    "import pytest\n"
    "\n"
    "from pkg.testing import Runner\n"
    "\n"
    "\n"
    "@pytest.fixture\n"
    "def runner():\n"
    "    return Runner()\n"
)

TEST = "def test_one(runner):\n    runner.invoke(1)\n"

DRAWN = {
    "from": "test_x.test_one",
    "to": "pkg.testing.Runner.invoke",
    "path": "test_x.py",
    "line": 2,
    "via": FIXTURE_VALUE,
    "fixture": "conftest.runner",
}


def files(**overrides) -> dict:
    """The shape of the ADR, with whichever file a case rewrites."""
    tree = {
        "pkg/__init__.py": "",
        "pkg/testing.py": TESTING,
        "conftest.py": CONFTEST,
        "test_x.py": TEST,
    }
    tree.update(overrides)
    return tree


def class_edge(
    target: str = "pkg.testing.Runner",
    line: int = 8,
    tier: str = SEMANTIC,
    source: str = "conftest.runner",
) -> dict:
    """The edge the index draws at the fixture's construction."""
    return tiered_edge(
        source,
        target,
        "calls",
        [{"path": "conftest.py", "line": line}],
        tier=tier,
        lane=LANE_SCIP,
    )


def run(tmp_path, tree: dict, edges: tuple = ()):
    """Write a small tree as ``test_fixtures.resolve`` does, then run the
    rule over the symbols lane A found and exactly the *edges* handed in
    — :func:`~hobbes.extract.graph.build_graph` draws no symbol edges at
    all (the join is their only producer), so the graph a case builds is
    the graph the rule reads."""
    for name, text in tree.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    drawn, _ = injections(modules, parsed)
    return value_calls(modules, parsed, drawn, graph["symbols"], list(edges))


class TestTheShapeDraws:
    def test_the_call_on_the_parameter_is_a_call_on_the_class(self, tmp_path):
        drawn, counts = run(tmp_path, files(), (class_edge(),))
        assert drawn == [DRAWN]
        assert counts["drawn"] == 1
        assert sum(counts["refused"].values()) == 0

    def test_the_counts_name_every_reason(self, tmp_path):
        _, counts = run(tmp_path, files(), (class_edge(),))
        assert set(counts["refused"]) == set(VALUE_REASONS)

    def test_a_fixture_requesting_a_fixture_and_calling_on_it_draws_too(self, tmp_path):
        conftest = CONFTEST + (
            "\n"
            "\n"
            "@pytest.fixture\n"
            "def wrapper(runner):\n"
            "    runner.invoke(1)\n"
            "    return runner\n"
        )
        drawn, counts = run(
            tmp_path, files(**{"conftest.py": conftest}), (class_edge(),)
        )
        assert [(c["from"], c["path"], c["line"]) for c in drawn] == [
            ("conftest.wrapper", "conftest.py", 13),
            ("test_x.test_one", "test_x.py", 2),
        ]
        assert counts["drawn"] == 2

    def test_two_sites_in_one_body_are_two_rows(self, tmp_path):
        test = "def test_one(runner):\n    runner.invoke(1)\n    runner.invoke(2)\n"
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert [c["line"] for c in drawn] == [2, 3]
        assert counts["drawn"] == 2


class TestTheParameterMustStillHoldIt:
    def test_a_rebound_parameter_draws_nothing(self, tmp_path):
        test = "def test_one(runner):\n    runner = 1\n    runner.invoke(1)\n"
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert drawn == []
        assert counts["refused"][REBOUND] == 1


class TestTheValueMustBeOneConstruction:
    def test_two_valued_returns_draw_nothing(self, tmp_path):
        conftest = CONFTEST.replace(
            "def runner():\n    return Runner()\n",
            "def runner(flag):\n"
            "    if flag:\n"
            "        return Runner()\n"
            "    return Runner()\n",
        )
        drawn, counts = run(
            tmp_path, files(**{"conftest.py": conftest}), (class_edge(line=10),)
        )
        assert drawn == []
        assert counts["refused"][NO_CONSTRUCTION] == 1


class TestTheClassEdgeMustBeTheIndexs:
    def test_an_edge_onto_a_function_is_not_a_class(self, tmp_path):
        testing = TESTING + "\n\ndef make():\n    return Runner()\n"
        conftest = CONFTEST.replace(
            "from pkg.testing import Runner", "from pkg.testing import make"
        ).replace("return Runner()", "return make()")
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "conftest.py": conftest}),
            (class_edge(target="pkg.testing.make"),),
        )
        assert drawn == []
        assert counts["refused"][NO_CLASS_EDGE] == 1

    def test_a_syntactic_class_edge_is_not_enough(self, tmp_path):
        drawn, counts = run(tmp_path, files(), (class_edge(tier=SYNTACTIC),))
        assert drawn == []
        assert counts["refused"][NO_CLASS_EDGE] == 1

    def test_no_class_edge_at_all_draws_nothing(self, tmp_path):
        drawn, counts = run(tmp_path, files())
        assert drawn == []
        assert counts["refused"][NO_CLASS_EDGE] == 1

    def test_an_edge_on_another_line_is_not_this_construction(self, tmp_path):
        drawn, counts = run(tmp_path, files(), (class_edge(line=3),))
        assert drawn == []
        assert counts["refused"][NO_CLASS_EDGE] == 1

    def test_an_alias_is_refused_because_the_written_name_differs(self, tmp_path):
        conftest = CONFTEST.replace(
            "from pkg.testing import Runner", "from pkg.testing import Runner as R"
        ).replace("return Runner()", "return R()")
        drawn, counts = run(
            tmp_path, files(**{"conftest.py": conftest}), (class_edge(),)
        )
        assert drawn == []
        assert counts["refused"][NO_CLASS_EDGE] == 1


class TestTheMethodMustBeTheClasssOwn:
    def test_a_method_only_a_base_defines_is_refused(self, tmp_path):
        testing = (
            "class Base:\n"
            "    def close(self):\n"
            "        return 1\n"
            "\n"
            "\n"
            "class Runner(Base):\n"
            "    def invoke(self, x):\n"
            "        return x\n"
        )
        test = "def test_one(runner):\n    runner.close()\n"
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": test}),
            (class_edge(),),
        )
        assert drawn == []
        assert counts["refused"][NO_METHOD] == 1

    def test_a_method_defined_twice_is_refused(self, tmp_path):
        testing = (
            "class Runner:\n"
            "    def invoke(self, x):\n"
            "        return x\n"
            "\n"
            "    def invoke(self, x, y):\n"
            "        return y\n"
        )
        drawn, counts = run(
            tmp_path, files(**{"pkg/testing.py": testing}), (class_edge(),)
        )
        assert drawn == []
        assert counts["refused"][NO_METHOD] == 1

    def test_a_property_is_refused(self, tmp_path):
        testing = (
            "class Runner:\n"
            "    @property\n"
            "    def invoke(self):\n"
            "        return 1\n"
        )
        drawn, counts = run(
            tmp_path, files(**{"pkg/testing.py": testing}), (class_edge(),)
        )
        assert drawn == []
        assert counts["refused"][PROPERTY] == 1


class TestWhatIsNotASite:
    """No site was looked at, so there is nothing to refuse and no block
    to write: a count of zeroes would say the rule had been asked."""

    def test_a_call_in_a_nested_def_of_the_test(self, tmp_path):
        test = (
            "def test_one(runner):\n"
            "    def inner():\n"
            "        runner.invoke(1)\n"
            "    inner()\n"
        )
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert (drawn, counts) == ([], {})

    def test_a_longer_chain_is_not_a_call_on_the_parameter(self, tmp_path):
        test = "def test_one(runner):\n    runner.a.b()\n"
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert (drawn, counts) == ([], {})

    def test_a_parametrized_name_is_no_injection_and_so_no_site(self, tmp_path):
        test = (
            "import pytest\n"
            "\n"
            "\n"
            '@pytest.mark.parametrize("runner", [1])\n'
            "def test_one(runner):\n"
            "    runner.invoke(1)\n"
        )
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert (drawn, counts) == ([], {})


class TestTheJoinsEdgeStands:
    def test_a_pair_the_graph_already_carries_is_left_alone(self, tmp_path):
        existing = tiered_edge(
            "test_x.test_one",
            "pkg.testing.Runner.invoke",
            "calls",
            [{"path": "test_x.py", "line": 2}],
            tier=SEMANTIC,
            lane=LANE_SCIP,
        )
        drawn, counts = run(tmp_path, files(), (class_edge(), existing))
        assert drawn == []
        assert counts["refused"][ALREADY_DRAWN] == 1


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_the_minifixval_test_reaches_the_method_its_fixture_constructed():
    """End to end with the index running. ``runner.invoke(1)`` is drawn —
    one ``calls`` edge, ``syntactic``, evidenced ``fixture-value`` — and
    the test's reach follows it into ``minifixval.runner``. Nothing else
    the test writes is: ``runner.close()`` is inherited from ``Base`` and
    ``made.invoke(2)`` goes through a function's return value, not a
    construction."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    extraction = extract_repo(MINIFIXVAL)
    graph = extraction.graph
    pair = ("test_runner.test_runner", "minifixval.runner.Runner.invoke")
    drawn = calls(graph)
    err = [
        e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")
    ]
    edge = drawn.get(pair)
    assert edge is not None, err
    assert edge["tier"] == SYNTACTIC, edge
    assert [(s["line"], s.get("via")) for s in edge["evidence"]] == [(2, FIXTURE_VALUE)]
    assert [to for frm, to in drawn if frm == pair[0]] == [pair[1]]
    counts = graph["fixtures"]["value_calls"]
    assert counts["drawn"] == 1
    assert counts["refused"][NO_METHOD] == 1  # runner.close(), on Base
    assert counts["refused"][NO_CLASS_EDGE] == 1  # made.invoke(2), not a construction
    (record,) = extraction.tests["tests"]
    assert "minifixval.runner.Runner.invoke" in record["reaches"]
    assert "minifixval.runner" in record["reaches_modules"]


def test_minifixval_draws_nothing_without_the_index():
    """Condition 3 is the index's edge, so lane A alone draws none of the
    three sites and the block says which condition stopped it."""
    from hobbes.extract import extract_repo

    graph = extract_repo(MINIFIXVAL).graph
    assert [pair for pair in calls(graph) if pair[0] == "test_runner.test_runner"] == []
    assert graph["fixtures"]["value_calls"] == {
        "drawn": 0,
        "refused": {reason: 3 if reason == NO_CLASS_EDGE else 0 for reason in VALUE_REASONS},
    }
