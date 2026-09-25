"""The C-1 arm: the callees of a cell, from the fixture's own graph and clang key, and only from them."""

import copy
import json
from pathlib import Path

import pytest

from lattice import facts
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


@pytest.fixture(scope="module")
def graph():
    return json.loads((DERIVED / "graph.json").read_text())


@pytest.fixture(scope="module")
def key():
    return json.loads((DERIVED / "oracle.json").read_text())


def test_the_graph_comes_first_then_the_key_in_first_use_order(lattice, graph, key):
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, key)
    assert [(row["name"], row["provenance"]) for row in rows] == [
        ("MM256_FMA_PS", "hobbes:semantic"),
        ("hsum256_ps", "hobbes:semantic"),
        ("_mm256_setzero_ps", "clang-key:static"),
        ("_mm256_loadu_ps", "clang-key:static"),
        ("_mm256_add_ps", "clang-key:static"),
        ("_mm256_fmadd_ps", "clang-key:macro"),
    ]
    assert rows.missing == ["intrinsics"]  # no index was given, so the key's rows carry no signature


def test_the_graph_rows_carry_the_kind_and_the_signature_from_the_file(lattice, graph, key):
    rows = {row["name"]: row for row in facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, key)}
    assert rows["hsum256_ps"]["kind"] == "function"
    assert rows["hsum256_ps"]["signature"] == "static inline float hsum256_ps (__m256 v)"
    assert rows["MM256_FMA_PS"]["kind"] == "macro"
    assert rows["MM256_FMA_PS"]["signature"].startswith("#define MM256_FMA_PS(_acc, _x, _y)")
    assert "_mm256_fmadd_ps" in rows["MM256_FMA_PS"]["signature"]


def test_a_callee_both_instruments_name_keeps_the_graphs_row_and_says_the_key_agreed(lattice, graph, key):
    rows = {row["name"]: row for row in facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, key)}
    assert rows["hsum256_ps"]["also"] == "clang-key"  # the key sees it too
    assert "also" not in rows["MM256_FMA_PS"]  # the key resolves through the macro, never to it
    assert all("also" not in row for row in rows.values() if row["provenance"].startswith("clang-key"))


def test_the_key_fills_the_intrinsic_signatures_when_an_index_is_given(lattice, graph, key):
    index = {"_mm256_loadu_ps": {
        "name": "_mm256_loadu_ps",
        "signature": "__m256 _mm256_loadu_ps(float const *__p)",
        "header": "avxintrin.h",
        "macro": False,
    }}
    rows = {row["name"]: row for row in facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, key, index)}
    assert rows["_mm256_loadu_ps"]["signature"] == "__m256 _mm256_loadu_ps(float const *__p)"
    assert rows["_mm256_loadu_ps"]["mode"] == "static"
    assert rows["_mm256_setzero_ps"]["signature"] is None  # not in the index, and not invented
    assert rows["_mm256_fmadd_ps"]["mode"] == "macro"


def test_a_wrappers_only_callee_is_its_impl(lattice, graph, key):
    rows = facts.callees(lattice, lattice.get("avx2/float32/l2"), graph, key)
    assert [row["name"] for row in rows] == ["float32_distance_l2_impl_avx2"]
    assert rows[0]["provenance"] == "hobbes:semantic"
    assert rows[0]["also"] == "clang-key"
    assert rows[0]["signature"].startswith("static inline float float32_distance_l2_impl_avx2 (")


def test_an_impl_is_read_like_any_other_cell(lattice, graph, key):
    rows = facts.callees(lattice, lattice.get("avx2/float32/l2_impl"), graph, key)
    assert [row["name"] for row in rows][:2] == ["MM256_FMA_PS", "hsum256_ps"]
    assert "_mm256_sub_ps" in [row["name"] for row in rows]


def test_a_site_in_another_file_or_outside_the_body_is_not_this_cells(lattice, graph, key):
    cell = lattice.get("avx2/float32/dot")
    elsewhere = copy.deepcopy(key)
    elsewhere["sites"] += [
        {  # the same static name, another file: the caller's bare name is not enough
            "caller": cell.name,
            "col": 5,
            "mode": "static",
            "pos": {"line": cell.body_span.line, "path": "src/distance-sse2.c"},
            "targets": [{"external": True, "kind": "function", "name": "_mm_other_file_ps", "pos": {"line": 0, "path": ""}}],
        },
        {  # the right file, a line above this cell's body
            "caller": cell.name,
            "col": 5,
            "mode": "static",
            "pos": {"line": cell.body_span.line - 1, "path": cell.file},
            "targets": [{"external": True, "kind": "function", "name": "_mm_above_ps", "pos": {"line": 0, "path": ""}}],
        },
        {  # the right file, a line below it
            "caller": cell.name,
            "col": 5,
            "mode": "static",
            "pos": {"line": cell.body_span.end_line + 1, "path": cell.file},
            "targets": [{"external": True, "kind": "function", "name": "_mm_below_ps", "pos": {"line": 0, "path": ""}}],
        },
    ]
    names = [row["name"] for row in facts.callees(lattice, cell, graph, elsewhere)]
    assert "_mm_other_file_ps" not in names
    assert "_mm_above_ps" not in names
    assert "_mm_below_ps" not in names
    assert names == [row["name"] for row in facts.callees(lattice, cell, graph, key)]


def test_a_site_inside_the_body_of_this_file_is_this_cells(lattice, graph, key):
    """The matching rule holds the other way too: the same row, on a line the body covers, counts."""
    cell = lattice.get("avx2/float32/dot")
    seeded = copy.deepcopy(key)
    seeded["sites"].append({
        "caller": cell.name,
        "col": 5,
        "mode": "static",
        "pos": {"line": cell.body_span.end_line - 1, "path": cell.file},
        "targets": [{"external": True, "kind": "function", "name": "_mm_inside_ps", "pos": {"line": 0, "path": ""}}],
    })
    assert "_mm_inside_ps" in [row["name"] for row in facts.callees(lattice, cell, graph, seeded)]


# MARK: - what is missing is said -


def test_with_no_graph_the_key_answers_alone_and_the_graph_is_named_missing(lattice, key):
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), None, key)
    assert "graph" in rows.missing
    assert [row["provenance"] for row in rows] == ["clang-key:static"] * 4 + ["clang-key:macro"]
    assert "hsum256_ps" in [row["name"] for row in rows]  # the key has it; the tier does not


def test_with_no_key_the_graph_answers_alone_and_no_intrinsic_is_named(lattice, graph):
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, None)
    assert rows.missing == ["clang-key"]
    assert [row["name"] for row in rows] == ["MM256_FMA_PS", "hsum256_ps"]


def test_with_neither_there_are_no_rows_and_both_are_named(lattice):
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), None, None)
    assert list(rows) == []
    assert rows.missing == ["graph", "clang-key"]


def test_a_cell_the_graph_has_no_symbol_for_is_said_and_not_guessed(lattice, graph, key):
    without = copy.deepcopy(graph)
    without["symbols"] = [s for s in without["symbols"] if s["name"] != "float32_distance_dot_avx2"]
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), without, key)
    assert rows.missing[0] == "graph: no symbol for float32_distance_dot_avx2 in src/distance-avx2.c"
    assert all(row["provenance"].startswith("clang-key:") for row in rows)


def test_a_file_the_key_does_not_cover_is_said(lattice, graph, key):
    partial = copy.deepcopy(key)
    partial["files"] = [f for f in partial["files"] if f != "src/distance-avx2.c"]
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, partial)
    assert "clang-key: src/distance-avx2.c is not one of the key's files" in rows.missing


# MARK: - the ledger and its provenance -


def test_the_ledger_loads_from_the_derived_files_and_names_where_it_came_from(lattice):
    ledger = facts.load(graph=DERIVED / "graph.json", key=DERIVED / "oracle.json")
    source = ledger.source()
    assert source["graph"] == {"sha": "d256eb725c7db519695b0ff4d06e4dbef3f54d58", "version": "0.2.70-beta"}
    assert source["key"]["oracle"].startswith("Ubuntu clang version 18.1.3")
    assert source["intrinsics"] is None
    assert [row["name"] for row in ledger.callees(lattice, lattice.get("avx2/float32/dot"))][:2] == [
        "MM256_FMA_PS",
        "hsum256_ps",
    ]


def test_an_empty_ledger_says_so_rather_than_answering(lattice):
    ledger = facts.load()
    assert ledger.source() == {"graph": None, "key": None, "intrinsics": None}
    assert ledger.callees(lattice, lattice.get("sse2/int8/dot")).missing == ["graph", "clang-key"]


def test_the_rows_are_json_able_and_carry_no_absolute_path(lattice, graph, key):
    rows = facts.callees(lattice, lattice.get("avx512/bit1/hamming"), graph, key)
    dumped = json.dumps(list(rows))
    assert json.loads(dumped) == list(rows)
    assert str(FIXTURE) not in dumped
