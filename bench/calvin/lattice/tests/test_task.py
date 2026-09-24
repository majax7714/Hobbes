"""The task record: what the lattice fills, what it leaves for the graph and the parser, and its stability."""

import json
from pathlib import Path

import pytest

from lattice import task
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


@pytest.fixture(scope="module")
def record(lattice):
    return task.build(lattice, lattice.get("sse2/float32/dot"))


def test_the_grid_fields_are_the_cell(record):
    assert record["schema"] == "lattice-task/1"
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


def test_the_fields_the_graph_and_the_parser_own_are_null(record):
    assert record["callees"] is None
    assert record["contract"] is None
    assert record["edge_cases"] is None
    assert record["like"] is None


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
