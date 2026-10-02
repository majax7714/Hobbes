"""A call through a local alias, on a fixture (ADR-160, C-9).

The ``minialias`` fixture's ``core`` binds local aliases to a class
(``_Segment = Segment``, called twice, once in a comprehension), a method
(``get_style = self.get_style``), a function (``_len = cell_len``), a
list's method outside the repo (``append = parts.append``), and binds one
name twice (``size``).

Two readings: lane A alone, where there is no ``semantic`` edge to read
and so nothing is drawn (P6), and the whole ingest with lane B, which this
sandbox cannot run (``lane_b``).
"""

from pathlib import Path

import pytest

from hobbes.extract import extract_repo
from hobbes.extract.aliases import ALIAS, NO_RHS_EDGE
from hobbes.extract.schema import SYNTACTIC

MINIALIAS = Path(__file__).parent / "fixtures" / "minialias"
CORE_TEXT = (MINIALIAS / "src" / "minialias" / "core.py").read_text()

CORE = "minialias.core"
CORE_PATH = "src/minialias/core.py"


def _line_of(text: str, nth: int = 0) -> int:
    """The 1-based line of the *nth* line of ``core.py`` holding *text*, so
    no case pins a literal line number."""
    hits = [i + 1 for i, line in enumerate(CORE_TEXT.splitlines()) if text in line]
    return hits[nth]


RENDER_FIRST = _line_of("first = _Segment(")
RENDER_COMPREHENSION = _line_of("[_Segment(text)")
GET_STYLE = _line_of('get_style("x")')
MEASURE = _line_of("return _len(")
APPEND = _line_of('append("".join')
TWICE = _line_of("return size(")

RENDER = f"{CORE}.render"
RENDER_STR = f"{CORE}.Console.render_str"
MEASURE_FN = f"{CORE}.measure"
COLLECT = f"{CORE}.collect"
TWICE_FN = f"{CORE}.twice"


def alias_edges(graph) -> dict:
    """Every edge carrying a ``via: "alias"`` evidence row, by (from, to)."""
    return {
        (e["from"], e["to"]): e
        for e in graph["symbol_edges"]
        if any(row.get("via") == ALIAS for row in e["evidence"])
    }


def alias_sites(edge: dict) -> set[tuple[str, int]]:
    """The ``(path, line)`` of each site an alias edge was drawn for."""
    return {
        (row["path"], row["line"]) for row in edge["evidence"] if row.get("via") == ALIAS
    }


def test_the_fixtures_lines_are_what_the_constants_say():
    assert RENDER_FIRST < RENDER_COMPREHENSION < GET_STYLE < MEASURE < APPEND < TWICE


def test_lane_a_alone_draws_nothing():
    """No lane B for Python, no `semantic` edge at any right-hand side, so
    every site abstains `no-rhs-edge` (P6)."""
    graph = extract_repo(MINIALIAS).graph
    assert alias_edges(graph) == {}
    counts = graph.get("aliases", {})
    assert counts.get("drawn", 0) == 0
    if counts:
        assert counts["aliases"] == 4  # `size`, bound twice, is not one
        assert counts["sites"] == 5
        assert counts["abstained"][NO_RHS_EDGE] == 5


@pytest.mark.lane_b
def test_with_the_index_each_alias_is_drawn_to_its_right_hand_side():
    """The whole ingest, lane B running (the developer's host)."""
    from hobbes.extract import containment

    why = containment.unavailable_reason()
    if why is not None:
        pytest.skip(f"containment unavailable here: {why}")
    graph = extract_repo(MINIALIAS).graph
    err = [e for e in graph.get("extraction_errors", []) if e["stage"].startswith("scip")]
    drawn = alias_edges(graph)

    # A function to a class (two sites, one in a comprehension), a method
    # to a method, a function to a function: four sites on three edges.
    expected = {
        (RENDER, "minialias.segment.Segment"): {
            (CORE_PATH, RENDER_FIRST),
            (CORE_PATH, RENDER_COMPREHENSION),
        },
        (RENDER_STR, f"{CORE}.Console.get_style"): {(CORE_PATH, GET_STYLE)},
        (MEASURE_FN, "minialias.segment.cell_len"): {(CORE_PATH, MEASURE)},
    }
    assert {pair: alias_sites(edge) for pair, edge in drawn.items()} == expected, (
        err,
        graph.get("aliases"),
    )
    for edge in drawn.values():
        assert edge["type"] == "calls"
        assert edge["tier"] == SYNTACTIC

    # `parts.append` names a builtin's method, outside the repo.
    counts = graph["aliases"]
    assert counts["sites"] == 5
    assert counts["drawn"] == 4
    assert counts["abstained"][NO_RHS_EDGE] == 1
    assert not any(source == COLLECT for source, _ in drawn)

    # `size` is bound twice: no alias, no site.
    assert not any(source == TWICE_FN for source, _ in drawn)
