"""The hole: the round trip over every cell of every fixture file, and what `fill` refuses."""

from pathlib import Path

import pytest

from lattice.cells import build
from lattice.holes import HOLE, NoHole, UnbalancedBody, fill, gold_body, punch

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


def test_the_round_trip_holds_for_every_cell_of_every_file(lattice):
    for cell in lattice.cells.values():
        text = lattice.text(cell)
        punched = punch(text, cell)
        assert punched != text, cell.id
        assert HOLE in punched, cell.id
        assert fill(punched, gold_body(text, cell)) == text, cell.id


def test_punching_changes_only_the_body(lattice):
    cell = lattice.get("avx2/float32/dot")
    text = lattice.text(cell)
    punched = punch(text, cell)
    assert punched[: cell.body_span.start] == text[: cell.body_span.start]
    assert punched[cell.body_span.start + len(HOLE) :] == text[cell.body_span.end :]
    assert cell.signature in punched
    assert gold_body(text, cell) not in punched
    assert punched.count(HOLE) == 1


def test_a_gold_body_runs_from_its_brace_to_its_matching_brace(lattice):
    cell = lattice.get("sse2/float32/l2")
    body = gold_body(lattice.text(cell), cell)
    assert body.startswith("{") and body.endswith("}")
    assert "float32_distance_l2_impl_sse2(v1, v2, n, true);" in body


def test_fill_refuses_an_unbalanced_body(lattice):
    cell = lattice.get("avx2/float32/dot")
    punched = punch(lattice.text(cell), cell)
    for body in ("{ return 0.0f;", "return 0.0f; }", "return 0.0f;", "{ } }"):
        with pytest.raises(UnbalancedBody):
            fill(punched, body)
    # a brace inside a comment or a literal is not a brace
    assert fill(punched, '{ /* } */ const char *s = "{"; return 0.0f; }') != punched


def test_fill_refuses_a_text_with_no_hole(lattice):
    cell = lattice.get("avx2/float32/dot")
    with pytest.raises(NoHole):
        fill(lattice.text(cell), "{ return 0.0f; }")
