"""A ``with`` statement's ``__enter__`` and ``__exit__``, on a fixture
(ADR-156, C-174).

The ``miniwith`` fixture holds rich's ``Capture`` / ``Console.capture``
excerpt, a ``Sub(Base)`` whose ``__enter__`` is its own and whose
``__exit__`` is its base's, an annotated factory ``make() -> Sub``, an
unannotated ``unannotated()``, and ``each``, which uses every one of them
in a ``with``.

Two readings: lane A alone, where there is no ``semantic`` edge to read
and so nothing is drawn (P6), and the whole ingest with lane B, which this
sandbox cannot run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.schema import SYNTACTIC
from hobbes.extract.withstmt import NO_ANNOTATION, WITH

MINIWITH = Path(__file__).parent / "fixtures" / "miniwith"
CORE_TEXT = (MINIWITH / "src" / "miniwith" / "core.py").read_text()

CORE = "miniwith.core"
CORE_PATH = "src/miniwith/core.py"


def _line_of(text: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of ``core.py`` that starts
    (stripped) with *text*, so no case pins a literal line number."""
    hits = [
        i + 1
        for i, line in enumerate(CORE_TEXT.splitlines())
        if line.strip().startswith(text)
    ]
    return hits[nth]


USE_CAPTURE = _line_of("with console.capture() as capture:")
EACH_CONSTRUCT = _line_of("with Capture(c):")
EACH_CAPTURE = _line_of("with c.capture() as capture:")
EACH_MAKE = _line_of("with make():")
EACH_UNANNOTATED = _line_of("with unannotated():")
EACH_SUB = _line_of("with Sub() as s:")

USE = f"{CORE}.use"
EACH = f"{CORE}.each"
CAPTURE_ENTER = f"{CORE}.Capture.__enter__"
CAPTURE_EXIT = f"{CORE}.Capture.__exit__"
SUB_ENTER = f"{CORE}.Sub.__enter__"
BASE_EXIT = f"{CORE}.Base.__exit__"


def with_edges(graph) -> dict:
    """Every edge carrying a ``via: "with"`` evidence row, by (from, to)."""
    return {
        (e["from"], e["to"]): e
        for e in graph["symbol_edges"]
        if any(row.get("via") == WITH for row in e["evidence"])
    }


def with_lines(edge: dict) -> set[int]:
    return {row["line"] for row in edge["evidence"] if row.get("via") == WITH}


def test_the_fixtures_lines_are_what_the_constants_say():
    assert USE_CAPTURE < EACH_CONSTRUCT < EACH_CAPTURE < EACH_MAKE
    assert EACH_MAKE < EACH_UNANNOTATED < EACH_SUB


def test_lane_a_alone_draws_nothing():
    """No lane B for Python, no `semantic` edge, so every item abstains at
    its call edge: the block is present — the fixture has items that are
    calls — and its `drawn` is 0 (P6)."""
    graph = extract_repo(MINIWITH).graph
    assert with_edges(graph) == {}
    counts = graph["with_statements"]
    assert counts["items"] == 6
    assert counts["drawn"] == 0


@pytest.mark.lane_b
def test_with_the_index_the_known_classes_methods_are_drawn():
    """The whole ingest, lane B running (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIWITH).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    drawn = with_edges(graph)

    # A constructor item and a factory annotated with the class.
    for caller, line in ((EACH, EACH_CONSTRUCT), (EACH, EACH_CAPTURE), (USE, USE_CAPTURE)):
        for method in (CAPTURE_ENTER, CAPTURE_EXIT):
            edge = drawn.get((caller, method))
            assert edge is not None, (caller, method, err, graph.get("with_statements"))
            assert line in with_lines(edge)

    # `Sub` writes `__enter__` and inherits `__exit__` from its one base.
    for line in (EACH_MAKE, EACH_SUB):
        for method in (SUB_ENTER, BASE_EXIT):
            edge = drawn.get((EACH, method))
            assert edge is not None, (method, err, graph.get("with_statements"))
            assert line in with_lines(edge)

    # An unannotated factory names no class.
    assert not any(EACH_UNANNOTATED in with_lines(edge) for edge in drawn.values())
    assert graph["with_statements"]["abstained"][NO_ANNOTATION] == 1

    for edge in drawn.values():
        assert edge["type"] == "calls"
        assert edge["tier"] == SYNTACTIC
