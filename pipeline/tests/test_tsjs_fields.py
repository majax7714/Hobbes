"""A class field holding a function literal is a method symbol (ADR-180).

The ``minifields`` fixture's ``Box`` has ``static create = (…) => …`` and ``pick = (…) => …``; ``main`` in
``src/use.ts`` calls both. scip-typescript defines each field at its name and names it at the call token, so
with lane B the calls are ``semantic`` edges to the field. Lane A names no field (``declQualname``), so
without the index nothing is drawn to it. Either way the calls written inside a field's function are the
field's, and a field holding a value (``plain = f()``) stays the class's.
"""
from pathlib import Path

import pytest

from hobbes.extract.schema import SEMANTIC

MINI = Path(__file__).parent / "fixtures" / "minifields"


def calls(graph):
    return {(e["from"], e["to"]): e for e in graph["symbol_edges"] if e["type"] == "calls"}


def symbols(graph):
    return {s["id"]: s for s in graph["symbols"]}


@pytest.mark.lane_b
def test_with_the_index_a_call_to_a_field_is_a_semantic_call():
    from hobbes.extract import containment, extract_repo

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINI).graph
    drawn = calls(graph)
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    for target in ("src/box.Box.create", "src/box.Box.pick"):
        edge = drawn.get(("src/use.main", target))
        assert edge is not None, (target, sorted(drawn), err)
        assert edge["tier"] == SEMANTIC, edge
    assert drawn[("src/box.Box.run", "src/box.Box.pick")]["tier"] == SEMANTIC


def test_the_field_is_a_symbol_at_its_name_and_owns_its_body():
    from hobbes.extract import extract_repo

    graph = extract_repo(MINI).graph
    syms = symbols(graph)
    assert (syms["src/box.Box.create"]["kind"], syms["src/box.Box.create"]["line"]) == ("method", 3)
    assert (syms["src/box.Box.pick"]["kind"], syms["src/box.Box.pick"]["line"]) == ("method", 4)
    assert "src/box.Box.plain" not in syms
    drawn = calls(graph)
    # The field's body is the field's; a value initializer is the class's (ADR-158).
    assert ("src/box.Box.create", "src/box.f") in drawn
    assert ("src/box.Box.pick", "src/box.f") in drawn
    assert ("src/box.Box", "src/box.f") in drawn


def test_lane_a_draws_nothing_to_a_field_without_the_index():
    from hobbes.extract import extract_repo

    graph = extract_repo(MINI).graph
    assert not any(to in ("src/box.Box.create", "src/box.Box.pick") for _, to in calls(graph))
