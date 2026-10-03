"""A call of a constructed instance, on a fixture (ADR-171, C-174).

The ``miniinst`` fixture is rich's ``Highlighter`` shape: ``__call__`` on an
ABC, two single named bases below it, called bound once (``render``),
directly (``direct``) and at module level (``BANNER``); beside them a class
writing ``__new__``, an annotated factory, a class with no ``__call__``, a
name bound twice and an instance held in an attribute.

Two readings: lane A alone, where there is no ``semantic`` edge to read and
so nothing is drawn (P6), and the whole ingest with lane B, which this
sandbox cannot run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.instcalls import CALL, DEFINES_NEW, NO_CALL_EDGE, NOT_A_CLASS
from hobbes.extract.fixtures import NO_METHOD
from hobbes.extract.schema import SYNTACTIC

FIXTURE = Path(__file__).parent / "fixtures" / "miniinst"
CORE_PATH = "miniinst/core.py"
CORE_TEXT = (FIXTURE / CORE_PATH).read_text()
CORE = "miniinst.core"
CALL_ID = "miniinst.highlighter.Highlighter.__call__"


def _line(needle: str) -> int:
    return [i + 1 for i, line in enumerate(CORE_TEXT.splitlines()) if needle in line][0]


def instance_edges(graph) -> dict:
    """Every edge carrying a ``via: "__call__"`` row, by (from, to), with its sites."""
    return {
        (e["from"], e["to"]): {(r["path"], r["line"]) for r in e["evidence"] if r.get("via") == CALL}
        for e in graph["symbol_edges"]
        if any(r.get("via") == CALL for r in e["evidence"])
    }


def test_lane_a_alone_draws_nothing():
    """No lane B, no `semantic` edge at any construction (P6)."""
    graph = extract_repo(FIXTURE).graph
    assert instance_edges(graph) == {}
    counts = graph.get("instance_calls", {})
    assert counts.get("drawn", 0) == 0
    if counts:
        assert counts["sites"] == 6
        assert counts["abstained"][NO_CALL_EDGE] == 6


@pytest.mark.lane_b
def test_with_the_index_each_instance_call_is_drawn():
    """The whole ingest, lane B running (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(FIXTURE).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    drawn = instance_edges(graph)
    assert drawn == {
        (CORE, CALL_ID): {(CORE_PATH, _line("BANNER = "))},
        (f"{CORE}.direct", CALL_ID): {(CORE_PATH, _line("return ReprHighlighter()(line)"))},
        (f"{CORE}.render", CALL_ID): {(CORE_PATH, _line("return highlighter(line)"))},
    }, (err, graph.get("instance_calls"))
    for pair in drawn:
        (edge,) = [e for e in graph["symbol_edges"] if (e["from"], e["to"]) == pair and e["type"] == "calls"]
        assert edge["tier"] == SYNTACTIC
    counts = graph["instance_calls"]
    assert (counts["sites"], counts["drawn"]) == (6, 3)
    assert {k: v for k, v in counts["abstained"].items() if v} == {
        DEFINES_NEW: 1,
        NOT_A_CLASS: 1,
        NO_METHOD: 1,
    }
