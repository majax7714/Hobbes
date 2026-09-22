"""A call on the value a fixture constructs is a call on that class
(ADR-145, and its 2026-09-22 amendment).

``def runner(): return Runner()`` fixes the runtime class of what the
parameter holds — a construction is never a subclass — so ``runner.m(…)``
written in the test's own body is a call on ``Runner.m``. The index
emits nothing at ``m`` (scip-python does not type an unannotated
parameter), so there is no occurrence for the join to match: the rule
reads the two hops the graph already carries, the ``uses`` injection and
the ``semantic`` edge from the fixture to the class it constructs.

The amendment reads two more things off the same two hops: a fixture
that binds the construction to a local and returns the local is the same
construction reached through a name, and a method the constructed class
does not define is looked for up a chain of single, named bases — the
``def`` Python would find first. An instance either side patched is
refused, because the trace would see the patch and the graph would name
the ``def``.

The cases below hand :func:`hobbes.extract.fixtures.value_calls` a graph
whose class edges are written out, because those edges are exactly what
the rule is allowed to believe. Each refusal has a case of its own: the
conditions fail toward drawing less, and what each one declined is the
size of what a construction did not settle.
"""

from pathlib import Path

import pytest

from hobbes.extract.discover import discover_modules
from hobbes.extract.fixtures import (
    ALREADY_DRAWN,
    BASE_UNNAMED,
    CLASS_BINDS,
    FIXTURE_VALUE,
    MULTIPLE_BASES,
    NO_CLASS_EDGE,
    NO_CONSTRUCTION,
    NO_METHOD,
    PATCHED,
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
FLASK_EXCERPT = Path(__file__).parent / "fixtures" / "flask-excerpt"

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

#: The same fixture writing the amendment's form: one construction bound
#: to a local at the top of the body, on line 8 again, and returned.
LOCAL_CONFTEST = (
    "import pytest\n"
    "\n"
    "from pkg.testing import Runner\n"
    "\n"
    "\n"
    "@pytest.fixture\n"
    "def runner():\n"
    "    r = Runner()\n"
    "    return r\n"
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


def base_edge(source: str, target: str, line: int, edge_type: str = "uses") -> dict:
    """The edge the index draws at a class's own header, naming its base.

    Whichever type the join gave it: in flask, ``Flask``'s header carries
    a ``uses`` edge and no ``implements`` one, which is why the amended
    rule reads the header edge rather than ADR-120's.
    """
    return tiered_edge(
        source,
        target,
        edge_type,
        [{"path": "pkg/testing.py", "line": line}],
        tier=SEMANTIC,
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


#: Every local form ``pysource`` refuses, as the fixture's whole
#: definition. Each leaves a second writer of the name possible, so
#: condition 2 does not hold and the site is counted `no-construction`.
LOCAL_REFUSALS = {
    "bound twice": "def runner():\n    r = Runner()\n    r = Runner()\n    return r\n",
    "bound in a branch": (
        "def runner(flag):\n    if flag:\n        r = Runner()\n    return r\n"
    ),
    "a loop target": (
        "def runner():\n    for r in [Runner()]:\n        pass\n    return r\n"
    ),
    "a parameter": "def runner(r):\n    return r\n",
    "bound after the return": "def runner():\n    return r\n    r = Runner()\n",
    "declared nonlocal in a nested def": (
        "def runner():\n"
        "    r = Runner()\n"
        "    def inner():\n"
        "        nonlocal r\n"
        "    return r\n"
    ),
    "a factory's return": "def runner():\n    r = make.factory()\n    return r\n",
    "one of two targets": "def runner():\n    r, b = Runner(), 1\n    return r\n",
}


class TestTheValueMayComeThroughALocal:
    """ADR-145's amendment: a local bound once, by a construction, at the
    top of the body, before the return, holds nothing else — so the
    class the assignment names is the class the parameter holds."""

    def test_the_local_the_fixture_returned_is_the_construction(self, tmp_path):
        drawn, counts = run(
            tmp_path, files(**{"conftest.py": LOCAL_CONFTEST}), (class_edge(),)
        )
        assert drawn == [DRAWN]
        assert (counts["drawn"], counts["local"], counts["inherited"]) == (1, 1, 0)

    @pytest.mark.parametrize(
        "fixture", LOCAL_REFUSALS.values(), ids=list(LOCAL_REFUSALS)
    )
    def test_a_local_the_body_does_not_settle_is_no_construction(
        self, tmp_path, fixture
    ):
        conftest = CONFTEST.replace("def runner():\n    return Runner()\n", fixture)
        drawn, counts = run(
            tmp_path, files(**{"conftest.py": conftest}), (class_edge(),)
        )
        assert drawn == []
        assert counts["refused"][NO_CONSTRUCTION] == 1


class TestAPatchedInstanceIsRefused:
    """The trace would see the patch; the graph would name the class's
    ``def``. Asked of both sides of the chain, and before the method is
    looked up at all — ``invoke`` below is one ``def`` on ``Runner``."""

    def test_the_test_patched_the_parameter(self, tmp_path):
        test = "def test_one(runner):\n    runner.invoke = f\n    runner.invoke(1)\n"
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert drawn == []
        assert counts["refused"][PATCHED] == 1

    def test_the_fixture_patched_the_local_it_handed_back(self, tmp_path):
        conftest = LOCAL_CONFTEST.replace(
            "    return r\n", "    r.invoke = f\n    return r\n"
        )
        drawn, counts = run(
            tmp_path, files(**{"conftest.py": conftest}), (class_edge(),)
        )
        assert drawn == []
        assert counts["refused"][PATCHED] == 1

    def test_a_setattr_moves_a_name_the_rule_cannot_read(self, tmp_path):
        test = (
            "def test_one(runner, monkeypatch):\n"
            '    monkeypatch.setattr(runner, "invoke", f)\n'
            "    runner.invoke(1)\n"
        )
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert drawn == []
        assert counts["refused"][PATCHED] == 1

    def test_a_patch_on_another_name_is_not_this_one(self, tmp_path):
        test = "def test_one(runner):\n    runner.other = f\n    runner.invoke(1)\n"
        drawn, counts = run(tmp_path, files(**{"test_x.py": test}), (class_edge(),))
        assert drawn == [DRAWN | {"line": 3}]
        assert counts["refused"][PATCHED] == 0


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


#: `Runner(Base)` with `close` on the base: `Runner` opens on line 6, the
#: line the index's header edge has to sit on for the walk to take it.
INHERITED = (
    "class Base:\n"
    "    def close(self):\n"
    "        return 1\n"
    "\n"
    "\n"
    "class Runner(Base):\n"
    "    def invoke(self, x):\n"
    "        return x\n"
)

CLOSE = "def test_one(runner):\n    runner.close()\n"


class TestTheMethodMayBeABasesOwn:
    """ADR-145's amendment reverses the original's refusal: the walk goes
    up a chain of single, named bases and takes the first ``def`` it
    meets — which is the one Python would find."""

    def test_a_method_the_base_defines_is_drawn(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": INHERITED, "test_x.py": CLOSE}),
            (class_edge(), base_edge("pkg.testing.Runner", "pkg.testing.Base", 6)),
        )
        assert [(c["from"], c["to"], c["line"]) for c in drawn] == [
            ("test_x.test_one", "pkg.testing.Base.close", 2)
        ]
        assert (counts["drawn"], counts["inherited"], counts["local"]) == (1, 1, 0)

    def test_two_levels_up_is_still_the_first_def(self, tmp_path):
        testing = (
            "class Base:\n"
            "    def close(self):\n"
            "        return 1\n"
            "\n"
            "\n"
            "class Mid(Base):\n"
            "    pass\n"
            "\n"
            "\n"
            "class Runner(Mid):\n"
            "    def invoke(self, x):\n"
            "        return x\n"
        )
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": CLOSE}),
            (
                class_edge(),
                base_edge("pkg.testing.Runner", "pkg.testing.Mid", 10),
                base_edge("pkg.testing.Mid", "pkg.testing.Base", 6),
            ),
        )
        assert [c["to"] for c in drawn] == ["pkg.testing.Base.close"]
        assert counts["inherited"] == 1

    def test_an_override_on_the_way_up_wins(self, tmp_path):
        testing = (
            "class Base:\n"
            "    def close(self):\n"
            "        return 1\n"
            "\n"
            "\n"
            "class Mid(Base):\n"
            "    def close(self):\n"
            "        return 2\n"
            "\n"
            "\n"
            "class Runner(Mid):\n"
            "    def invoke(self, x):\n"
            "        return x\n"
        )
        drawn, _ = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": CLOSE}),
            (
                class_edge(),
                base_edge("pkg.testing.Runner", "pkg.testing.Mid", 11),
                base_edge("pkg.testing.Mid", "pkg.testing.Base", 6),
            ),
        )
        assert [c["to"] for c in drawn] == ["pkg.testing.Mid.close"]

    def test_a_class_met_twice_stops_the_walk(self, tmp_path):
        testing = (
            "class Mid(Runner):\n"
            "    pass\n"
            "\n"
            "\n"
            "class Runner(Mid):\n"
            "    def invoke(self, x):\n"
            "        return x\n"
        )
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": CLOSE}),
            (
                class_edge(),
                base_edge("pkg.testing.Runner", "pkg.testing.Mid", 5),
                base_edge("pkg.testing.Mid", "pkg.testing.Runner", 1),
            ),
        )
        assert drawn == []
        assert counts["refused"][NO_METHOD] == 1

    def test_a_class_attribute_shadows_the_bases_def(self, tmp_path):
        testing = INHERITED.replace(
            "class Runner(Base):\n", "class Runner(Base):\n    close = None\n\n"
        )
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": CLOSE}),
            (class_edge(), base_edge("pkg.testing.Runner", "pkg.testing.Base", 6)),
        )
        assert drawn == []
        assert counts["refused"][CLASS_BINDS] == 1

    def test_two_bases_are_an_mro_the_rule_does_not_compute(self, tmp_path):
        testing = (
            "class Base:\n"
            "    def close(self):\n"
            "        return 1\n"
            "\n"
            "\n"
            "class Mixin:\n"
            "    pass\n"
            "\n"
            "\n"
            "class Runner(Base, Mixin):\n"
            "    def invoke(self, x):\n"
            "        return x\n"
        )
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": CLOSE}),
            (class_edge(), base_edge("pkg.testing.Runner", "pkg.testing.Base", 10)),
        )
        assert drawn == []
        assert counts["refused"][MULTIPLE_BASES] == 1

    def test_a_base_the_index_does_not_name_stops_the_walk(self, tmp_path):
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": INHERITED, "test_x.py": CLOSE}),
            (class_edge(),),
        )
        assert drawn == []
        assert counts["refused"][BASE_UNNAMED] == 1

    def test_two_classes_named_on_one_header_line_are_no_answer(self, tmp_path):
        testing = (
            "class Base:\n"
            "    def close(self):\n"
            "        return 1\n"
            "\n"
            "\n"
            "class Mixin:\n"
            "    def close(self):\n"
            "        return 2\n"
            "\n"
            "\n"
            "class Runner(Base):\n"
            "    def invoke(self, x):\n"
            "        return x\n"
        )
        drawn, counts = run(
            tmp_path,
            files(**{"pkg/testing.py": testing, "test_x.py": CLOSE}),
            (
                class_edge(),
                base_edge("pkg.testing.Runner", "pkg.testing.Base", 11),
                base_edge("pkg.testing.Runner", "pkg.testing.Mixin", 11),
            ),
        )
        assert drawn == []
        assert counts["refused"][BASE_UNNAMED] == 1


class TestTheMethodMustBeTheClasssOwn:
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


#: What flask's own tests write on the `app` fixture, one call per line:
#: a method `Scaffold` defines, one `App` overrides, one only `Flask` has,
#: and one written three times behind `@t.overload`.
FLASK_TEST = (
    "def test_app(app):\n"
    '    app.route("/")\n'
    '    app.add_url_rule("/x", "x", f)\n'
    "    app.test_client()\n"
    '    app.template_filter("f")\n'
)


def flask_edge(source: str, target: str, path: str, line: int, edge_type: str) -> dict:
    return tiered_edge(
        source,
        target,
        edge_type,
        [{"path": path, "line": line}],
        tier=SEMANTIC,
        lane=LANE_SCIP,
    )


def test_the_flask_excerpts_own_shape(tmp_path):
    """ADR-148's lesson, on ADR-145's amendment: the rule is read against
    the source it was measured on, not only against a shape written for
    it. ``pipeline/tests/fixtures/flask-excerpt/`` holds flask's ``app``
    fixture and the three classes above it verbatim (its ``NOTICE`` says
    which commit); the graph below is the one the index gives, a class
    edge at the assignment and a header edge at each class.

    Two of the three targets are a base's, one is the subclass's own
    override rather than the base's, and ``template_filter`` — written
    twice as an ``@t.overload`` stub and once for real — is refused: the
    rule reads one ``def`` or none.
    """
    tree = {
        name: (FLASK_EXCERPT / name).read_text()
        for name in ("scaffold.py", "app.py", "flask_app.py", "conftest.py")
    }
    tree["test_x.py"] = FLASK_TEST
    drawn, counts = run(
        tmp_path,
        tree,
        (
            flask_edge("conftest.app", "flask_app.Flask", "conftest.py", 12, "calls"),
            flask_edge("flask_app.Flask", "app.App", "flask_app.py", 10, "uses"),
            flask_edge("app.App", "scaffold.Scaffold", "app.py", 10, "uses"),
        ),
    )
    assert [(c["line"], c["to"]) for c in sorted(drawn, key=lambda c: c["line"])] == [
        (2, "scaffold.Scaffold.route"),
        (3, "app.App.add_url_rule"),
        (4, "flask_app.Flask.test_client"),
    ]
    assert (counts["drawn"], counts["inherited"], counts["local"]) == (3, 2, 3)
    assert counts["refused"] == {
        reason: 1 if reason == NO_METHOD else 0 for reason in VALUE_REASONS
    }


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_the_minifixval_test_reaches_the_method_its_fixture_constructed():
    """End to end with the index running. Four calls are drawn — one
    ``calls`` edge each, ``syntactic``, evidenced ``fixture-value`` — and
    the tests' reach follows them into ``minifixval.runner``:
    ``runner.invoke(1)`` on the class the fixture constructs,
    ``runner.close()`` on the ``Base`` above it, and both of ``held``'s,
    whose fixture hands back the local it constructed. ``made.invoke(2)``
    is not: it goes through a function's return value, not a
    construction."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    extraction = extract_repo(MINIFIXVAL)
    graph = extraction.graph
    drawn = calls(graph)
    err = [
        e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")
    ]
    expected = {
        ("test_runner.test_runner", "minifixval.runner.Runner.invoke"): 2,
        ("test_runner.test_runner", "minifixval.runner.Base.close"): 3,
        ("test_held.test_held", "minifixval.runner.Runner.invoke"): 2,
        ("test_held.test_held", "minifixval.runner.Base.close"): 3,
    }
    for pair, line in expected.items():
        edge = drawn.get(pair)
        assert edge is not None, err
        assert edge["tier"] == SYNTACTIC, edge
        assert [(s["line"], s.get("via")) for s in edge["evidence"]] == [
            (line, FIXTURE_VALUE)
        ]
    assert sorted(pair for pair in drawn if pair[0].startswith("test_")) == sorted(
        expected
    )
    counts = graph["fixtures"]["value_calls"]
    assert (counts["drawn"], counts["inherited"], counts["local"]) == (4, 2, 2)
    # made.invoke(2): a function's return value, not a construction.
    assert counts["refused"] == {
        reason: 1 if reason == NO_CLASS_EDGE else 0 for reason in VALUE_REASONS
    }
    records = {record["id"]: record for record in extraction.tests["tests"]}
    for node_id in ("tests/test_runner.py::test_runner", "tests/test_held.py::test_held"):
        record = records[node_id]
        assert "minifixval.runner.Runner.invoke" in record["reaches"]
        assert "minifixval.runner.Base.close" in record["reaches"]
        assert "minifixval.runner" in record["reaches_modules"]


def test_minifixval_draws_nothing_without_the_index():
    """Condition 3 is the index's edge, so lane A alone draws none of the
    five sites — the two fixtures' values are read, the class edge under
    them is not — and the block says which condition stopped it."""
    from hobbes.extract import extract_repo

    graph = extract_repo(MINIFIXVAL).graph
    assert [pair for pair in calls(graph) if pair[0].startswith("test_")] == []
    assert graph["fixtures"]["value_calls"] == {
        "drawn": 0,
        "inherited": 0,
        "local": 0,
        "refused": {reason: 5 if reason == NO_CLASS_EDGE else 0 for reason in VALUE_REASONS},
    }
