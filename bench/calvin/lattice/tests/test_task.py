"""The task record: what the lattice fills, what it leaves for the graph and the parser, and its stability."""

import json
from pathlib import Path

import pytest

from lattice import facts, task
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


@pytest.fixture(scope="module")
def record(lattice):
    return task.build(lattice, lattice.get("sse2/float32/dot"))


def test_the_grid_fields_are_the_cell(record):
    assert record["schema"] == "lattice-task/3"
    assert record["cell"] == "sse2/float32/dot"
    assert record["name"] == "float32_distance_dot_sse2"
    assert record["file"] == "src/distance-sse2.c"
    assert (record["isa"], record["type"], record["metric"]) == ("sse2", "float32", "dot")
    assert record["kind"] == "body"
    assert record["static"] is False
    assert record["signature"] == "float float32_distance_dot_sse2 (const void *v1, const void *v2, int n)"
    assert record["slots"] == [["DOT", "F32"]]
    assert record["graded_via"] == [["DOT", "F32"]]
    assert "avx2/float32/dot" in record["neighbours"]


def test_the_prelude_ends_just_above_the_signature(record, lattice):
    text = lattice.text(lattice.get("sse2/float32/dot"))
    assert text.startswith(record["prelude"])
    assert record["prelude"].endswith("\n")
    assert text[len(record["prelude"]) :].startswith(record["signature"])
    # it is the C-0 context: the includes, the externs and the helpers above the hole
    assert "#include \"distance-sse2.h\"" in record["prelude"]
    assert "hsum128_ps" in record["prelude"]


def test_the_helpers_are_the_static_functions_above_the_cell(record):
    names = [helper["name"] for helper in record["helpers"]]
    assert "hsum128_ps" in names
    assert "float32_distance_l2_impl_sse2" in names
    assert "popcount_sse2" not in names  # defined below the cell
    assert record["helpers"][names.index("hsum128_ps")]["signature"] == "static inline float hsum128_ps (__m128 v)"


def test_the_macros_are_the_files_defines(record):
    assert record["macros"] == [
        "ACCUMULATE",
        "SIGN_EXTEND_EPI16_TO_EPI32_LO",
        "SIGN_EXTEND_EPI16_TO_EPI32_HI",
    ]


def test_the_bare_prelude_leaves_no_other_cells_body(lattice):
    cell = lattice.get("avx2/int8/dot")
    bare = task.prelude_bare(lattice, cell)
    above = [c for c in lattice.by_isa("avx2") if c.body_span.end <= cell.signature_span.start]
    assert [c.id for c in above] == [
        "avx2/float32/l2_impl", "avx2/float32/l2", "avx2/float32/l2_squared",
        "avx2/float32/l1", "avx2/float32/dot", "avx2/float32/cosine",
        "avx2/int8/l2_impl", "avx2/int8/l2", "avx2/int8/l2_squared",
    ]
    text = lattice.text(cell)
    for other in above:
        # its signature is followed by a `;` and its body is gone
        assert f"{other.signature};" in bare, other.id
        body = text[other.body_span.start : other.body_span.end]
        assert body not in bare, other.id


def test_the_bare_prelude_keeps_the_helpers_the_macros_and_the_includes(lattice):
    bare = task.prelude_bare(lattice, lattice.get("avx2/int8/dot"))
    # a non-cell helper keeps its body: it is a fact about the file, not a pattern shot
    assert "static inline float hsum256_ps (__m256 v) {" in bare
    assert "return _mm_cvtss_f32(s);" in bare
    assert "static inline __m256i dot_epi8 (__m256i a, __m256i b) {" in bare
    # macros and includes are the file's own
    assert '#include "distance-avx2.h"' in bare
    assert "#define _mm256_abs_ps(x)" in bare
    assert "#define S8_TO_BIASED_U8_AVX2(_v)" in bare


def test_the_two_preludes_are_the_same_text_apart_from_those_bodies(record, lattice):
    cell = lattice.get("sse2/float32/dot")
    assert record["prelude"] == lattice.text(cell)[: cell.signature_span.start]
    assert len(record["prelude_bare"]) < len(record["prelude"])
    assert record["prelude"].startswith("//\n//  distance-sse2.c")
    assert record["prelude_bare"].startswith("//\n//  distance-sse2.c")


def test_a_cell_with_nothing_above_it_has_the_same_two_preludes(lattice):
    record = task.build(lattice, lattice.get("avx2/float32/l2_impl"))
    assert record["prelude_bare"] == record["prelude"]


def test_the_fields_the_graph_and_the_parser_own_are_null(record):
    assert record["callees"] is None
    assert record["callees_source"] is None  # nobody was asked, which is not "it calls nothing"
    assert record["contract"] is None
    assert record["edge_cases"] is None
    assert record["like"] is None


# MARK: - the ledger's fields -


def test_a_ledger_fills_the_callees_and_says_where_they_came_from(lattice):
    ledger = facts.load(graph=FIXTURE / "derived" / "graph.json", key=FIXTURE / "derived" / "oracle.json")
    record = task.build(lattice, lattice.get("avx2/float32/dot"), facts=ledger)
    assert record["schema"] == "lattice-task/3"
    assert [row["name"] for row in record["callees"]] == [
        "MM256_FMA_PS",
        "hsum256_ps",
        "_mm256_setzero_ps",
        "_mm256_loadu_ps",
        "_mm256_add_ps",
        "_mm256_fmadd_ps",
    ]
    assert record["callees_source"]["graph"] == {
        "sha": "d256eb725c7db519695b0ff4d06e4dbef3f54d58",
        "version": "0.2.70-beta",
    }
    assert record["callees_source"]["key"]["oracle"].startswith("Ubuntu clang version 18.1.3")
    assert record["callees_source"]["missing"] == ["intrinsics"]


def test_a_filled_record_is_still_stable_json_with_no_absolute_path(lattice):
    ledger = facts.load(graph=FIXTURE / "derived" / "graph.json", key=FIXTURE / "derived" / "oracle.json")
    record = task.build(lattice, lattice.get("avx512/int8/l2_impl"), facts=ledger)
    dumped = task.dumps(record)
    assert json.loads(dumped) == record
    assert str(FIXTURE) not in dumped
    assert str(FIXTURE.resolve()) not in dumped
    assert record["callees"]  # the impl calls the file's own helpers


def test_the_json_is_stable_and_carries_no_absolute_path(record, lattice):
    dumped = task.dumps(record)
    assert dumped == task.dumps(json.loads(dumped))
    assert json.loads(dumped) == record
    assert list(json.loads(dumped)) == sorted(record)
    assert str(FIXTURE) not in dumped
    assert str(FIXTURE.resolve()) not in dumped


def test_an_impl_records_the_wrappers_it_is_graded_through(lattice):
    record = task.build(lattice, lattice.get("avx512/int8/l2_impl"))
    assert record["kind"] == "impl"
    assert record["static"] is True
    assert record["slots"] == []
    assert record["graded_via"] == [["L2", "I8"], ["SQUARED_L2", "I8"]]
