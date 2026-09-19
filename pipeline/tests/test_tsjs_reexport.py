"""A CommonJS re-export is followed by lane A (ADR-141, C-167).

The ``minicjs`` fixture is Express's shape in miniature: a root
``index.js`` that is one line of ``module.exports = require('./lib/app')``,
a second hop through ``index2.js``, and callers through ``require('..')``,
through ``index2`` and straight at the defining file. The edge the rule
draws is lane A's own answer, so it must stand with the index and without
it — one case each.
"""
from pathlib import Path

import pytest

from hobbes.extract.schema import LANE_TREE_SITTER, SEMANTIC, SYNTACTIC

MINICJS = Path(__file__).parent / "fixtures" / "minicjs"

THROUGH = ("test/through", "lib/app.createApplication")
TWOHOP = ("test/twohop", "lib/app.createApplication")


def calls(graph):
    """Every ``calls`` edge, keyed by its (from, to) pair."""
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


@pytest.mark.lane_b
def test_the_reexported_call_is_drawn_syntactic_with_nothing_vetoed():
    """With the index running: scip-typescript names the site a document-local
    of the *re-exporting* file, so it resolves nothing there and vetoes
    nothing. The edge is lane A's fallback, at the syntactic tier — the
    honest one, because the index did not prove it."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINICJS).graph
    drawn = calls(graph)
    why = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    for pair in (THROUGH, TWOHOP):
        edge = drawn.get(pair)
        assert edge is not None, (pair, why)
        assert edge["tier"] == SYNTACTIC, why
        assert [(s["line"], s["lane"]) for s in edge["evidence"]] == [(3, LANE_TREE_SITTER)]
    # nothing the index proved: neither caller has a semantic call at all
    semantic = [
        p for p, e in drawn.items() if p[0] in (THROUGH[0], TWOHOP[0]) and e["tier"] == SEMANTIC
    ]
    assert semantic == []
    # the direct require never needed the rule, and still resolves
    assert ("test/direct", "lib/app.createApplication") in drawn

    rows = {r["file"]: r for r in graph["resolution_coverage"]}
    for rel in ("test/through.js", "test/twohop.js"):
        tail = rows[rel]["tail"]
        assert tail.get("fallback-resolved") == 1, rel
        assert "nested-decl" not in tail, rel
    assert graph["lane_agreement"]["external_vetoes"]["sites"] == 0


def test_lane_a_draws_it_without_the_index():
    """The same two edges with lane B off: this is lane A's own resolution
    (the compiler's module resolution over the source's own statement), so
    it does not depend on an index being present."""
    from hobbes.extract import extract_repo

    drawn = calls(extract_repo(MINICJS).graph)
    for pair in (THROUGH, TWOHOP):
        edge = drawn.get(pair)
        assert edge is not None, pair
        assert edge["tier"] == SYNTACTIC
