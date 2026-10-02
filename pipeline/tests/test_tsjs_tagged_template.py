"""A TS/JS tagged template is a call site (C-177, lifted at 0.2.83-beta).

`` html`…` `` calls ``html`` with the template's strings and values, as
``html(…)`` would. Until facts v8 lane A recorded no site there, so the
index's occurrence at the tag became a ``uses`` edge: ``who_calls`` listed
it under references and test reach did not pass through it. The ``minitag``
fixture's ``page`` calls ``html`` by a tagged template (``src/tags.ts:9``),
with a call to ``count`` inside the substitution; ``viaMember`` tags through
a shorthand member (``ns = { html }``, ``ns.html`…```), which the index
follows to the function exactly as it follows ``ns.html(…)`` (ADR-144), and
lane A, which types no such receiver, does not.
"""
from pathlib import Path

import pytest

from hobbes.extract.schema import LANE_SCIP, SEMANTIC, SYNTACTIC

MINITAG = Path(__file__).parent / "fixtures" / "minitag"
PAGE_HTML = ("src/tags.page", "src/tags.html")
PAGE_COUNT = ("src/tags.page", "src/tags.count")
MEMBER_HTML = ("src/tags.viaMember", "src/tags.html")


def edges(graph, kind):
    """Every ``kind`` edge, keyed by its (from, to) pair."""
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == kind}


@pytest.mark.lane_b
def test_the_tag_is_a_semantic_call_and_no_longer_a_reference():
    """With the index running: the tag is a ``calls`` edge at the
    ``semantic`` tier, and the join claims the index's occurrence, so no
    ``uses`` edge to ``html`` is left beside it. The substitution's own call
    is unchanged, and the member tag is sited at its terminal ``html``
    (line 12), where the index's occurrence is."""
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINITAG).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    edge = edges(graph, "calls").get(PAGE_HTML)
    assert edge is not None, err
    assert edge["tier"] == SEMANTIC, (edge, err)
    assert (9, LANE_SCIP) in [(s["line"], s["lane"]) for s in edge["evidence"]], edge
    assert PAGE_HTML not in edges(graph, "uses")
    assert PAGE_COUNT in edges(graph, "calls")
    member = edges(graph, "calls").get(MEMBER_HTML)
    assert member is not None and member["tier"] == SEMANTIC, (member, err)
    assert 12 in [s["line"] for s in member["evidence"]], member
    assert MEMBER_HTML not in edges(graph, "uses")


def test_lane_a_draws_the_tag_and_a_test_reaches_through_it():
    """With lane B off: lane A's checker resolves the tag, so the site is a
    ``syntactic`` call, and a test of ``page`` reaches ``html``. The member
    tag has no lane A answer (an object literal's member is below the
    floor), so without the index it draws nothing."""
    from hobbes.extract import extract_repo

    extraction = extract_repo(MINITAG)
    calls = edges(extraction.graph, "calls")
    assert calls[PAGE_HTML]["tier"] == SYNTACTIC
    assert PAGE_COUNT in calls
    assert MEMBER_HTML not in calls
    (record,) = [t for t in extraction.tests["tests"] if t["id"].endswith("::page")]
    assert "src/tags.html" in record["reaches"]
