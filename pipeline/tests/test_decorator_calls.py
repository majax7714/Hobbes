"""A decorator is a call of what it names (ADR-146).

The ``minideco`` fixture writes the three shapes the rule covers —
``@plain`` (bare: the language's own ``plain(fn)``), ``@factory("a")``
(written as the call it is) and ``@registry.register("b")`` (a call on
the class a module-level construction fixes) — plus a fourth site inside
``outer``, on the decorator of a nested def. That fourth one is the
scope rule: the ``@`` runs where it is written, so the site belongs to
``outer`` and never to the def it wraps.

Each edge is ``semantic``: the rule mints no resolution of its own, it
only puts a lane A site where the index already names an occurrence.
What a decorator *returns* was not claimed at all when this fixture was
written; ADR-147 moved that boundary, and applying ``factory("a")``'s
result is now drawn as a call of ``factory.<locals>.decorator`` — one
tier down, ``syntactic`` and evidenced ``decorator-factory``, because the
index answers nothing at an application the source does not spell. The
assertion below says which of the two rules drew an edge, rather than
that the second hop is absent; ADR-147's own cases are in
``test_decorator_factories.py``.

The edges are the index's, so the end-to-end case needs lane B; the twin
below states what lane A alone has, which is the sites and no more.
"""

from pathlib import Path

import pytest

from hobbes.extract.decorators import DECORATOR_FACTORY
from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import SEMANTIC, SYNTACTIC

MINIDECO = Path(__file__).parent / "fixtures" / "minideco"

APP = "minideco.app"
OUTER = "minideco.app.outer"


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_every_decorator_application_is_drawn_at_the_index_s_tier():
    """With the index running: the four sites of this rule are ``calls``
    edges, each ``semantic``. Three leave the module — the decorators
    written at module level — and the fourth leaves ``outer``, whose body
    holds the ``@``. What reaches ``factory``'s inner ``decorator`` is
    ADR-147's edge beside them, ``syntactic`` and evidenced
    ``decorator-factory``: no site here was resolved to it."""
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
        (APP, "minideco.deco.plain"),
        (APP, "minideco.deco.factory"),
        (APP, "minideco.deco.Registry.register"),
        (OUTER, "minideco.deco.factory"),
    ]
    for pair in expected:
        edge = drawn.get(pair)
        assert edge is not None, (pair, err)
        assert edge["tier"] == SEMANTIC, (pair, err)
    # The decorated def is never the caller: `outer` holds the `@`, and
    # both of its edges — this rule's and ADR-147's — leave `outer`.
    assert sorted(to for frm, to in drawn if frm == OUTER) == [
        "minideco.deco.factory",
        "minideco.deco.factory.decorator",
    ]
    # ADR-146 resolved no site to an inner `decorator`; every edge that
    # reaches one is the application ADR-147 draws a tier down.
    for pair, e in drawn.items():
        if pair[1].endswith(".decorator"):
            assert e["tier"] == SYNTACTIC, pair
            assert {s.get("via") for s in e["evidence"]} == {DECORATOR_FACTORY}, pair
    assert [pair for pair in drawn if pair[0].startswith("minideco.app.one")] == []


def test_lane_a_has_the_four_sites():
    """Without the index the sites are still there — recording them is
    lane A's half of the rule, and what any lane resolves them to is the
    join's business as it is for a call in a body."""
    parsed = parse_source((MINIDECO / "src" / "minideco" / "app.py").read_bytes())
    assert [(c.scope, c.callee, c.line) for c in parsed.calls] == [
        (None, "Registry", 11),
        (None, "plain", 14),
        (None, "factory", 19),
        (None, "registry.register", 24),
        ("outer", "factory", 30),
        # ADR-147's two refusals, written after the four this rule pins.
        (None, "either", 37),
        (None, "wrapped", 42),
    ]
