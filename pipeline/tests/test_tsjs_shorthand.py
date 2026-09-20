"""A call through a namespace import is followed to the shorthand's function
(ADR-144).

The ``minicjs`` fixture's ``lib/tools.js`` exports one object literal —
``module.exports = { alpha, beta, gamma() {…}, delta: alpha }`` — and
``test/namespace.js`` calls all four members through
``const tools = require('../lib/tools')``. At the member token the index
names the *property* of that literal, not the function; for a shorthand
(``alpha``, ``beta``) the property's one definition occurrence and a
reference to the function sit at one range, which is what the helper reads.
A method written in the literal (``gamma``) and a value property
(``delta: alpha``) are refused, and refusing them is the rule.

Both hops are the index's, so the edge exists only with lane B: lane A has
no fallback for a namespace member, and the twin below states that.
"""
from pathlib import Path

import pytest

from hobbes.extract.schema import LANE_SCIP, SEMANTIC

MINICJS = Path(__file__).parent / "fixtures" / "minicjs"

RUN = "test/namespace.run"
ALPHA = (RUN, "lib/tools.alpha")
BETA = (RUN, "lib/tools.beta")


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


@pytest.mark.lane_b
def test_the_shorthand_members_are_drawn_and_the_others_refused():
    """With the index running: ``tools.alpha()`` and ``tools.beta()`` are
    ``calls`` edges at the ``semantic`` tier — the index proved the property
    at the site and the function at the property, so the join meets an
    ordinary lane B reference. ``tools.gamma()`` and ``tools.delta()`` draw
    nothing at all."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINICJS).graph
    drawn = calls(graph)
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    for pair, line in ((ALPHA, 4), (BETA, 5)):
        edge = drawn.get(pair)
        assert edge is not None, (pair, err)
        assert edge["tier"] == SEMANTIC, (pair, err)
        assert (line, LANE_SCIP) in [(s["line"], s["lane"]) for s in edge["evidence"]], edge
    # Nothing else leaves `run`: neither the literal's own method nor the
    # value property is this rule's, and no other lane draws them.
    assert sorted(to for frm, to in drawn if frm == RUN) == ["lib/tools.alpha", "lib/tools.beta"]


def test_lane_a_draws_no_namespace_member_without_the_index():
    """The same four calls with lane B off: lane A types no receiver, so
    ``tools.alpha()`` is an attribute call it cannot resolve (C-2) and there
    is no fallback to draw. The edges above are lane B's alone."""
    from hobbes.extract import extract_repo

    drawn = calls(extract_repo(MINICJS).graph)
    assert [pair for pair in drawn if pair[0] == RUN] == []
