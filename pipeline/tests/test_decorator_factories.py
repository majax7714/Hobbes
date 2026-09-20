"""A decorator factory's application is a call of the def it returns
(ADR-147).

``@factory("a")`` is two calls: ``factory("a")``, which the index names at
the token and ADR-146 draws, and the application of what it returned to
the definition below — a call of ``factory.<locals>.decorator``, written
nowhere. No indexer emits anything for the second, so the rule reads the
settled graph's own answer at the decorator's line and the factory's
written shape.

The cases below hand :func:`hobbes.extract.decorators.factory_calls` a
graph whose ``semantic`` edge is written out, because that edge is
exactly what the rule is allowed to believe. Each refusal has a case of
its own: the five conditions fail toward drawing less, and what each one
declined is the size of what a factory's shape did not settle. Where the
index answered nothing in the repo, nothing was asked at all — and a
block of zeroes would say otherwise.
"""

from pathlib import Path

import pytest

from hobbes.extract.decorators import (
    ALREADY_DRAWN,
    DECORATED,
    DECORATOR_FACTORY,
    FACTORY_REASONS,
    NO_RETURNED_DEF,
    NO_SINGLE_BODY,
    NO_SYMBOL,
    TWO_TARGETS,
    factory_calls,
)
from hobbes.extract.discover import discover_modules
from hobbes.extract.graph import build_graph
from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import LANE_SCIP, SEMANTIC, SYNTACTIC, tiered_edge

MINIDECO = Path(__file__).parent / "fixtures" / "minideco"

#: One factory and one method factory, each returning a nested ``def``.
DECO = (
    "def factory(label):\n"
    "    def decorator(fn):\n"
    "        return fn\n"
    "\n"
    "    return decorator\n"
    "\n"
    "\n"
    "class Registry:\n"
    "    def register(self, name):\n"
    "        def decorator(fn):\n"
    "            return fn\n"
    "\n"
    "        return decorator\n"
)

#: The three shapes that draw: a module-level decorator, a method
#: factory's, and one inside ``outer`` — whose ``@`` runs where it is
#: written, so ``outer`` is the caller and never the def it wraps.
APP = (
    "from pkg.deco import Registry, factory\n"
    "\n"
    "registry = Registry()\n"
    "\n"
    "\n"
    '@factory("a")\n'
    "def one():\n"
    "    return 1\n"
    "\n"
    "\n"
    '@registry.register("b")\n'
    "def two():\n"
    "    return 2\n"
    "\n"
    "\n"
    "def outer():\n"
    '    @factory("c")\n'
    "    def nested():\n"
    "        return 3\n"
    "\n"
    "    return nested\n"
)

#: One decorator, on line 4 — the line every refusal case's edge sits on.
SIMPLE_APP = (
    "from pkg.deco import factory\n"
    "\n"
    "\n"
    '@factory("a")\n'
    "def one():\n"
    "    return 1\n"
)

SIMPLE_DECO = (
    "def factory(label):\n"
    "    def decorator(fn):\n"
    "        return fn\n"
    "\n"
    "    return decorator\n"
)


def files(deco: str = DECO, app: str = APP, **overrides) -> dict:
    tree = {"pkg/__init__.py": "", "pkg/deco.py": deco, "app.py": app}
    tree.update(overrides)
    return tree


def edge(
    target: str = "pkg.deco.factory",
    line: int = 4,
    source: str = "app",
    tier: str = SEMANTIC,
    to: str = None,
) -> dict:
    """The edge the index draws at the decorator's callee, which ADR-146
    put there and this rule only reads."""
    return tiered_edge(
        source,
        to or target,
        "calls",
        [{"path": "app.py", "line": line}],
        tier=tier,
        lane=LANE_SCIP,
    )


def run(tmp_path, tree: dict, edges: tuple = ()):
    """Write a small tree, then run the rule over the symbols lane A found
    and exactly the *edges* handed in — :func:`build_graph` draws no symbol
    edges at all (the join is their only producer), so the graph a case
    builds is the graph the rule reads."""
    for name, text in tree.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    modules = discover_modules(tmp_path)
    parsed = {m.id: parse_source((tmp_path / m.path).read_bytes()) for m in modules}
    graph = build_graph(modules, parsed)
    return factory_calls(modules, parsed, graph["symbols"], list(edges))


class TestTheShapeDraws:
    def test_every_shape_is_a_call_of_the_def_the_factory_returns(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(),
            (
                edge(line=6),
                edge(target="pkg.deco.Registry.register", line=11),
                edge(line=17, source="app.outer"),
            ),
        )
        assert drawn == [
            {
                "from": "app",
                "to": "pkg.deco.Registry.register.decorator",
                "path": "app.py",
                "line": 11,
                "via": DECORATOR_FACTORY,
                "factory": "pkg.deco.Registry.register",
            },
            {
                "from": "app",
                "to": "pkg.deco.factory.decorator",
                "path": "app.py",
                "line": 6,
                "via": DECORATOR_FACTORY,
                "factory": "pkg.deco.factory",
            },
            {
                "from": "app.outer",
                "to": "pkg.deco.factory.decorator",
                "path": "app.py",
                "line": 17,
                "via": DECORATOR_FACTORY,
                "factory": "pkg.deco.factory",
            },
        ]
        assert counts["drawn"] == 3
        assert sum(counts["refused"].values()) == 0

    def test_the_counts_name_every_reason(self, tmp_path):
        _, counts = run(tmp_path, files(), (edge(line=6),))
        assert set(counts["refused"]) == set(FACTORY_REASONS)

    def test_an_overload_stub_is_not_the_body_that_is_read(self, tmp_path):
        # The drawn symbol may *be* the first stub (H-19's grain), so the
        # body is looked up among the qualname's definitions.
        deco = (
            "import typing as t\n"
            "\n"
            "\n"
            "@t.overload\n"
            "def factory(label: str):\n"
            "    ...\n"
            "\n"
            "\n"
            "def factory(label):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    return decorator\n"
        )
        drawn, counts = run(
            tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),)
        )
        assert [(c["to"], c["line"]) for c in drawn] == [
            ("pkg.deco.factory.decorator", 4)
        ]
        assert counts["drawn"] == 1


class TestTheIndexMustNameOneFactory:
    def test_two_targets_at_the_line_draw_nothing(self, tmp_path):
        # Two functions written `factory`, both answered at the one line:
        # the rule cannot say which factory the decorator applied.
        other = SIMPLE_DECO
        drawn, counts = run(
            tmp_path,
            files(app=SIMPLE_APP, **{"pkg/other.py": other}),
            (edge(), edge(target="pkg.other.factory")),
        )
        assert drawn == []
        assert counts["refused"][TWO_TARGETS] == 1

    def test_a_syntactic_edge_is_not_the_index_answering(self, tmp_path):
        drawn, counts = run(
            tmp_path, files(app=SIMPLE_APP), (edge(tier=SYNTACTIC),)
        )
        assert (drawn, counts) == ([], {})

    def test_no_edge_at_the_line_asks_nothing(self, tmp_path):
        drawn, counts = run(tmp_path, files(app=SIMPLE_APP))
        assert (drawn, counts) == ([], {})

    def test_an_edge_onto_another_name_is_not_this_factory(self, tmp_path):
        # `@factory("a")` resolved to something not written `factory` —
        # an argument's function, a receiver's class: not asked.
        drawn, counts = run(
            tmp_path, files(app=SIMPLE_APP), (edge(target="pkg.deco.Registry.register"),)
        )
        assert (drawn, counts) == ([], {})


class TestTheFactoryMustHaveOneUndecoratedBody:
    def test_two_non_overload_definitions_draw_nothing(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(deco=SIMPLE_DECO + "\n\n" + SIMPLE_DECO, app=SIMPLE_APP),
            (edge(),),
        )
        assert drawn == []
        assert counts["refused"][NO_SINGLE_BODY] == 1

    def test_a_decorated_factory_draws_nothing(self, tmp_path):
        # flask's `Scaffold.route`, under `@setupmethod`: what the factory
        # hands back is what its own decorator returned.
        deco = "@setupmethod\n" + SIMPLE_DECO
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][DECORATED] == 1

    def test_a_body_whose_returns_are_not_one_def_draws_nothing(self, tmp_path):
        deco = (
            "def factory(func):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    if func:\n"
            "        return decorator(func)\n"
            "    return decorator\n"
        )
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][NO_RETURNED_DEF] == 1


class TestTheInnerDefMustBeOneSymbol:
    def test_an_inner_qualname_written_twice_draws_nothing(self, tmp_path):
        # The stub carries a `decorator` of its own, so `factory.decorator`
        # is two definitions collapsed into one record: no id to trust.
        deco = (
            "import typing as t\n"
            "\n"
            "\n"
            "@t.overload\n"
            "def factory(label: str):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    return decorator\n"
            "\n"
            "\n"
            "def factory(label):\n"
            "    def decorator(fn):\n"
            "        return fn\n"
            "\n"
            "    return decorator\n"
        )
        drawn, counts = run(tmp_path, files(deco=deco, app=SIMPLE_APP), (edge(),))
        assert drawn == []
        assert counts["refused"][NO_SYMBOL] == 1


class TestTheJoinsEdgeStands:
    def test_a_pair_the_graph_already_carries_is_left_alone(self, tmp_path):
        existing = tiered_edge(
            "app",
            "pkg.deco.factory.decorator",
            "calls",
            [{"path": "app.py", "line": 4}],
            tier=SEMANTIC,
            lane=LANE_SCIP,
        )
        drawn, counts = run(
            tmp_path, files(app=SIMPLE_APP), (edge(), existing)
        )
        assert drawn == []
        assert counts["refused"][ALREADY_DRAWN] == 1


class TestWhatIsNotAsked:
    """Nothing reached the rule, so there is nothing to refuse and no block
    to write: a count of zeroes would say the rule had been asked."""

    def test_a_bare_decorator_never_asks(self, tmp_path):
        # `@f` applies `f` itself — ADR-146's edge, at the semantic tier.
        # What `f` would have returned is not applied to anything.
        app = "from pkg.deco import factory\n\n\n@factory\ndef one():\n    return 1\n"
        drawn, counts = run(tmp_path, files(app=app), (edge(),))
        assert (drawn, counts) == ([], {})

    def test_a_callee_the_walk_cannot_name_asks_nothing(self, tmp_path):
        app = (
            "from pkg.deco import factory\n"
            "\n"
            "decos = [factory]\n"
            "\n"
            "\n"
            '@decos[0]("a")\n'
            "def one():\n"
            "    return 1\n"
        )
        drawn, counts = run(tmp_path, files(app=app), (edge(line=6),))
        assert (drawn, counts) == ([], {})

    def test_a_chain_wrapped_across_lines_asks_nothing(self, tmp_path):
        app = (
            "from pkg import deco\n"
            "\n"
            "\n"
            "@deco.\\\n"
            '    factory("a")\n'
            "def one():\n"
            "    return 1\n"
        )
        drawn, counts = run(tmp_path, files(app=app), (edge(line=5),))
        assert (drawn, counts) == ([], {})


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_the_minideco_factories_are_called_and_the_refusals_are_counted():
    """End to end with the index running. Three applications are drawn —
    ``@factory("a")`` at the module, ``@factory("c")`` inside ``outer``
    and ``@registry.register("b")`` — each one ``calls`` / ``syntactic``,
    evidenced ``decorator-factory``. The two factories the fixture writes
    to be refused draw nothing: ``either`` returns ``decorator`` on one
    path and ``decorator(label)`` on another, and ``wrapped`` is itself
    decorated."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIDECO).graph
    drawn = calls(graph)
    err = [
        e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")
    ]
    expected = [
        ("minideco.app", "minideco.deco.factory.decorator"),
        ("minideco.app", "minideco.deco.Registry.register.decorator"),
        ("minideco.app.outer", "minideco.deco.factory.decorator"),
    ]
    for pair in expected:
        found = drawn.get(pair)
        assert found is not None, (pair, err)
        assert found["tier"] == SYNTACTIC, (pair, err)
        assert [s.get("via") for s in found["evidence"]] == [DECORATOR_FACTORY] * len(
            found["evidence"]
        )
    # Neither refused factory's inner def is reached from a decorator site.
    # (`app` does call `either` and `wrapped` themselves — ADR-146 — and
    # `either`'s body calls its own `decorator` by name; those stand.)
    assert [
        pair
        for pair in drawn
        if pair[0].startswith("minideco.app")
        and pair[1].startswith(("minideco.deco.either.", "minideco.deco.wrapped."))
    ] == []
    counts = graph["decorators"]["factory_calls"]
    assert counts["drawn"] == 3
    assert counts["refused"][NO_RETURNED_DEF] == 1  # either
    assert counts["refused"][DECORATED] == 1  # wrapped
    assert sum(counts["refused"].values()) == 2


def test_minideco_draws_nothing_without_the_index():
    """Condition 1 is the index's edge, so lane A alone asks nothing at
    all and the block is absent — not a row of zeroes."""
    from hobbes.extract import extract_repo

    graph = extract_repo(MINIDECO).graph
    assert [pair for pair in calls(graph) if pair[1].endswith(".decorator")] == []
    assert "decorators" not in graph


def test_a_module_level_application_is_drawn_from_the_module_node():
    """A top-level `@factory("a")` runs at import, and its caller is the
    module *node*, not a symbol. The edge append once kept symbol callers
    only, as ADR-145's does, and the block counted rows the graph did not
    hold — caught on the host by the `lane_b` case above, pinned here
    where no index is needed."""
    from hobbes.extract import _add_factory_call_edges

    graph = {
        "nodes": [{"id": "pkg.app", "kind": "module"}],
        "symbols": [{"id": "pkg.deco.factory.decorator", "kind": "function"}],
        "symbol_edges": [],
    }
    row = {
        "from": "pkg.app",
        "to": "pkg.deco.factory.decorator",
        "path": "src/pkg/app.py",
        "line": 3,
        "via": DECORATOR_FACTORY,
        "factory": "pkg.deco.factory",
    }
    _add_factory_call_edges(graph, [row, {**row, "from": "pkg.nowhere"}])
    (edge,) = graph["symbol_edges"]
    assert (edge["from"], edge["to"], edge["tier"]) == (
        "pkg.app",
        "pkg.deco.factory.decorator",
        SYNTACTIC,
    )
