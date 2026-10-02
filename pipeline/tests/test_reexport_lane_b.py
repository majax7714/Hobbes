"""A reference misnamed through an imported module, on a fixture (ADR-161,
C-178).

The ``minireexport`` fixture's ``__init__.py`` re-exports ``core`` by
``from .core import *``, and ``use.py`` reads ``mr.Beta``, ``mr.Gamma``,
``mr.two`` and ``mr.CONST`` through ``import minireexport as mr``.
Measured in the image, scip-python names the last three ``Beta#``, the
first lookup's answer.

Two readings: lane A alone, where nothing is refused and nothing is
recorded (P6), and the whole ingest with lane B, which this sandbox cannot
run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.schema import SEMANTIC

MINIREEXPORT = Path(__file__).parent / "fixtures" / "minireexport"
USE_PATH = "src/minireexport/use.py"
USE_LINES = (MINIREEXPORT / USE_PATH).read_text().splitlines()

USE = "minireexport.use"
BUILD = f"{USE}.build"
BETA = "minireexport.core.Beta"


def _line_of(text: str) -> int:
    """The 1-based line of ``use.py`` holding *text*, so no case pins a
    literal line number."""
    hits = [i + 1 for i, line in enumerate(USE_LINES) if text in line]
    assert len(hits) == 1, (text, hits)
    return hits[0]


FIRST = _line_of("first = mr.Beta()")
SECOND = _line_of("second = mr.Gamma()")
RETURN = _line_of("mr.two(1), mr.CONST")


def refusal_records(graph) -> list[dict]:
    """The degradation records ADR-161 writes."""
    return [
        e
        for e in graph.get("extraction_errors", [])
        if e["stage"] == "scip-python" and "C-178" in e["message"]
    ]


def edges_at(graph, source: str, line: int) -> list[dict]:
    """Every edge from *source* carrying evidence at ``use.py``'s *line*."""
    return [
        e
        for e in graph["symbol_edges"]
        if e["from"] == source
        and any(row.get("path") == USE_PATH and row.get("line") == line for row in e["evidence"])
    ]


def test_the_fixtures_lines_are_what_the_constants_say():
    assert FIRST < SECOND < RETURN


def test_lane_a_alone_refuses_and_records_nothing():
    graph = extract_repo(MINIREEXPORT).graph
    assert refusal_records(graph) == []


@pytest.mark.lane_b
def test_with_the_index_the_misnamed_references_are_refused():
    """The whole ingest, lane B running (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIREEXPORT).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]

    records = refusal_records(graph)
    assert len(records) == 1, err
    message = records[0]["message"]
    assert message.startswith("3 "), message
    for token in ("Gamma", "two", "CONST"):
        assert f"{USE_PATH}:" in message and f"`{token}` named" in message, message

    # `mr.Beta()` is what it says: drawn.
    beta = [e for e in edges_at(graph, BUILD, FIRST) if e["to"] == BETA]
    assert [(e["type"], e["tier"]) for e in beta] == [("calls", SEMANTIC)], err

    # The refused lines draw nothing to `Beta`, and nothing named other
    # than the line's own tokens (or the package `mr` binds).
    for line, tokens in ((SECOND, {"Gamma"}), (RETURN, {"two", "CONST"})):
        assert all(token in USE_LINES[line - 1] for token in tokens)
        written = tokens | {"minireexport"}
        for edge in edges_at(graph, BUILD, line):
            assert edge["to"] != BETA, (line, edge)
            assert edge["to"].rpartition(".")[2] in written, (line, edge)
