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
index answers nothing at an application the source does not spell.
ADR-148 moved it again for the factories whose returns only the site's
own arguments settle, evidenced ``decorator-factory-folded``, and ADR-149
once more for the factories that hand back a *second* factory's call,
evidenced ``decorator-factory-chained``. The assertion below says which
of the four rules drew each edge, rather than that the second hop is
absent; ADR-147's, ADR-148's and ADR-149's own cases are in
``test_decorator_factories.py``.

The edges are the index's, so the end-to-end case needs lane B; the twin
below states what lane A alone has, which is the sites and no more.
"""

from pathlib import Path

import pytest

from hobbes.extract.decorators import (
    DECORATOR_FACTORY,
    DECORATOR_FACTORY_CHAINED,
    DECORATOR_FACTORY_FOLDED,
)
from hobbes.extract.pysource import parse_source
from hobbes.extract.schema import SEMANTIC, SYNTACTIC

MINIDECO = Path(__file__).parent / "fixtures" / "minideco"

APP = "minideco.app"
OUTER = "minideco.app.outer"
FOLDING = "minideco.app.folding"
CHAINING = "minideco.app.chaining"


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {
        (e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"
    }


@pytest.mark.lane_b
def test_every_decorator_application_is_drawn_at_the_index_s_tier():
    """With the index running: the four sites this fixture was written
    for are ``calls`` edges, each ``semantic``. Three leave the module —
    the decorators written at module level — and the fourth leaves
    ``outer``, whose body holds the ``@``. What reaches an inner
    ``decorator`` is the second hop beside them, ``syntactic`` and
    evidenced by the reading that drew it: no site here was resolved to
    one."""
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
        # The chained sites are first calls like any other: what ADR-149
        # reads at the *factory's* own return is the edge beside them,
        # `minideco.deco.grouped` → `minideco.deco.optional`.
        (APP, "minideco.deco.grouped"),
        (APP, "minideco.deco.flagged"),
        (APP, "minideco.deco.relay"),
        (CHAINING, "minideco.deco.grouped"),
        ("minideco.deco.grouped", "minideco.deco.optional"),
        ("minideco.deco.flagged", "minideco.deco.factory"),
        ("minideco.deco.relay", "minideco.deco.plain"),
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
    # ADR-146 resolved no *decorator site* to an inner `decorator`; every
    # edge that reaches one from `app` is the application drawn a tier
    # down, by the reading named here — ADR-147's three, from the
    # factory's shape alone, ADR-148's four, folded over what the site
    # wrote, and ADR-149's four, reached through a second factory's call.
    # Two pairs carry two readings: `@flagged()` chains to the `factory`
    # whose own site ADR-147 settles, and `@grouped(…)` chains to the
    # `optional` ADR-148 folds — one edge each, and the lines say which
    # was which. (`either`'s own body calls its `decorator` by name — a
    # direct call in `deco`, which the index answers `semantic`.)
    via = {
        (APP, "minideco.deco.factory.decorator"): {
            DECORATOR_FACTORY,
            DECORATOR_FACTORY_CHAINED,
        },
        (APP, "minideco.deco.Registry.register.decorator"): {DECORATOR_FACTORY},
        (OUTER, "minideco.deco.factory.decorator"): {DECORATOR_FACTORY},
        (APP, "minideco.deco.optional.decorator"): {
            DECORATOR_FACTORY_FOLDED,
            DECORATOR_FACTORY_CHAINED,
        },
        (APP, "minideco.deco.Registry.command.decorator"): {DECORATOR_FACTORY_FOLDED},
        (APP, "minideco.deco.either.decorator"): {DECORATOR_FACTORY_FOLDED},
        (FOLDING, "minideco.deco.optional.decorator"): {DECORATOR_FACTORY_FOLDED},
        (CHAINING, "minideco.deco.optional.decorator"): {DECORATOR_FACTORY_CHAINED},
    }
    for pair, e in drawn.items():
        if pair[1].endswith(".decorator") and pair[0].startswith(APP):
            assert e["tier"] == SYNTACTIC, pair
            assert {s.get("via") for s in e["evidence"]} == via[pair], pair
    assert [pair for pair in drawn if pair[0].startswith("minideco.app.one")] == []


def test_lane_a_has_the_four_sites():  # and the refusals written after them
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
        # ADR-148's sites, written after those: the same rule records
        # each of them, whatever the fold later makes of its arguments —
        # including the bare `@optional` on line 78, which applies
        # `optional` itself and is no factory application at all.
        (None, "optional", 63),
        (None, "optional", 68),
        (None, "optional", 73),
        (None, "optional", 78),
        (None, "registry.command", 83),
        (None, "either", 88),
        ("folding", "optional", 94),
        # ADR-149's sites, written after those. A chained application is
        # the same first call at the same line — what the rule reads
        # beyond it is written in `deco.py`, at the factory's own return
        # — and the bare `@grouped` on line 129 is no application of a
        # factory's result at all.
        (None, "grouped", 114),
        (None, "grouped", 119),
        (None, "grouped", 124),
        (None, "grouped", 129),
        (None, "flagged", 134),
        (None, "relay", 139),
        ("chaining", "grouped", 145),
    ]
