"""The C-1 arm: the callees of a cell, from the fixture's own graph and clang key, and only from them."""

import copy
import json
from pathlib import Path

import pytest

from lattice import facts, intrinsics, shadow
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"

#: Two of clang's own header macros, as clang writes them — the two `bit1_distance_hamming_avx2` uses.
CLANG_HEADER = r"""
#define _mm256_extracti128_si256(V, M) \
  ((__m128i)__builtin_ia32_extract128i256((__v4di)(__m256i)(V), (int)(M)))
#define _mm_extract_epi64(X, N) \
  ((long long)__builtin_ia32_vec_ext_v2di((__v2di)(__m128i)(X), (int)(N)))
static __inline__ __m256 __DEFAULT_FN_ATTRS256
_mm256_undefined_ps(void)
{
"""


@pytest.fixture(scope="module")
def index():
    return intrinsics.index({"avx2intrin.h": CLANG_HEADER})


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


# MARK: - a header macro is named as the source wrote it (part 3's review, session 189e) -


def test_a_header_macros_expansion_is_dropped_and_the_macro_the_body_writes_is_added(lattice, graph, key, index):
    """`_mm256_extracti128_si256` is what the body writes; `__builtin_ia32_extract128i256` is clang's."""
    rows = facts.callees(lattice, lattice.get("avx2/bit1/hamming"), graph, key, index)
    by_name = {row["name"]: row for row in rows}

    assert by_name["_mm256_extracti128_si256"]["provenance"] == "clang-headers:macro"
    assert by_name["_mm256_extracti128_si256"]["signature"] == "#define _mm256_extracti128_si256(V, M)"
    assert by_name["_mm_extract_epi64"]["provenance"] == "clang-headers:macro"
    assert by_name["_mm_extract_epi64"]["kind"] == "macro"

    # no `__builtin_ia32_*` row: an expansion is not a name the source wrote
    assert [name for name in by_name if name.startswith("__builtin_ia32_")] == []
    assert {(row["name"], row["wrote"]) for row in rows.dropped} == {
        ("__builtin_ia32_extract128i256", "_mm256_extracti128_si256"),
        ("__builtin_ia32_vec_ext_v2di", "_mm_extract_epi64"),
    }
    assert all(row["reason"] == facts.DROPPED for row in rows.dropped)

    # `__builtin_popcount` is written out in the body in `static` mode, so the rule leaves it alone
    assert by_name["__builtin_popcount"]["provenance"] == "clang-key:static"
    assert rows.missing == []


def test_the_added_macros_stand_in_the_bodys_own_order(lattice, graph, key, index):
    names = [row["name"] for row in facts.callees(lattice, lattice.get("avx2/bit1/hamming"), graph, key, index)]
    assert names == [
        "popcount_avx2",
        "_mm256_setzero_si256",
        "_mm256_loadu_si256",
        "_mm256_xor_si256",
        "_mm256_add_epi64",
        "_mm256_sad_epu8",
        "_mm_add_epi64",
        "_mm256_extracti128_si256",  # line 450, after `_mm_add_epi64` on the same line
        "_mm_extract_epi64",  # line 451
        "__builtin_popcount",  # line 455
    ]


def test_an_in_repo_macros_expansion_is_the_answer_and_stays(lattice, graph, key, index):
    """`MM256_FMA_PS` is the repo's own, so `_mm256_fmadd_ps` is what the body does. Unchanged."""
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), graph, key, index)
    assert [(row["name"], row["provenance"]) for row in rows] == [
        ("MM256_FMA_PS", "hobbes:semantic"),
        ("hsum256_ps", "hobbes:semantic"),
        ("_mm256_setzero_ps", "clang-key:static"),
        ("_mm256_loadu_ps", "clang-key:static"),
        ("_mm256_add_ps", "clang-key:static"),
        ("_mm256_fmadd_ps", "clang-key:macro"),
    ]
    assert rows.dropped == []


def test_an_in_repo_macro_the_graph_does_not_name_is_still_the_files_own(lattice, key, index):
    """With no graph, the cell's own file's `#define`s stand in — a read, not an inference."""
    rows = facts.callees(lattice, lattice.get("avx2/float32/dot"), None, key, index)
    assert "_mm256_fmadd_ps" in [row["name"] for row in rows]
    assert rows.dropped == []


def test_a_macro_reaching_a_real_intrinsic_function_is_kept(lattice, graph, key, index):
    cell = lattice.get("avx2/bit1/hamming")
    seeded = copy.deepcopy(key)
    seeded["sites"].append({
        "caller": cell.name,
        "col": 22,  # `_mm_add_epi64` on line 450 — not an in-repo macro
        "mode": "macro",
        "pos": {"line": 450, "path": cell.file},
        "targets": [{"external": True, "kind": "function", "name": "_mm256_undefined_ps", "pos": {"line": 0, "path": ""}}],
    })
    rows = facts.callees(lattice, cell, graph, seeded, index)
    assert "_mm256_undefined_ps" in [row["name"] for row in rows]  # the index knows it as a function
    assert "_mm256_undefined_ps" not in {row["name"] for row in rows.dropped}


def test_without_an_index_nothing_is_added_and_the_index_is_named_missing(lattice, graph, key):
    rows = facts.callees(lattice, lattice.get("avx2/bit1/hamming"), graph, key)
    assert "clang-headers:macro" not in [row["provenance"] for row in rows]
    assert "_mm256_extracti128_si256" not in [row["name"] for row in rows]
    assert rows.missing == ["intrinsics"]
    assert len(rows.dropped) == 2  # the expansions go, because the written token is clang's macro


def test_a_macro_named_only_in_a_comment_is_not_a_callee(lattice, graph, key):
    """The added rows come off the *masked* body, so prose about an intrinsic is not a call to one.

    `int8_distance_l1_sse2` writes `// Absolute value via max/min since _mm_abs_epi16 is SSE3+` — the
    one place the fixture names an intrinsic it does not use.
    """
    cell = lattice.get("sse2/int8/l1")
    body = lattice.sources["sse2"].text[cell.body_span.start : cell.body_span.end]
    assert "_mm_abs_epi16" in body
    named = {"_mm_abs_epi16": {"name": "_mm_abs_epi16", "signature": "#define _mm_abs_epi16(a)", "macro": True}}
    assert "_mm_abs_epi16" not in [row["name"] for row in facts.callees(lattice, cell, graph, key, named)]


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


# MARK: - E2-b: the target's ledger, written forward into a shadow's names -


@pytest.fixture(scope="module")
def ledger():
    return facts.load(graph=DERIVED / "graph.json", key=DERIVED / "oracle.json")


@pytest.fixture(scope="module")
def shadowed(graph, lattice, ledger, tmp_path_factory):
    """The descriptive shadow of the fixture, its own lattice, and the ledger written forward into it."""
    plan = shadow.plan(FIXTURE, graph, "descriptive")
    root = shadow.write(plan, tmp_path_factory.mktemp("facts-shadow") / "descriptive")
    translated = facts.Translated(
        ledger=ledger, lattice=lattice, renames=plan.renames, map_sha256="d" * 64
    )
    return plan, build(root, rename=plan.reverse()), translated


def test_a_shadow_cell_answers_with_the_original_cells_callees_under_the_new_names(shadowed, lattice, ledger):
    plan, shadow_lattice, translated = shadowed
    cell = shadow_lattice.get("avx2/float32/dot")
    assert cell.name == plan.renames["float32_distance_dot_avx2"]  # the shadow's own name

    rows = translated.callees(shadow_lattice, cell)
    before = ledger.callees(lattice, lattice.get("avx2/float32/dot"))
    assert [row["name"] for row in rows] == [
        plan.renames.get(row["name"], row["name"]) for row in before
    ]
    assert [row["name"] for row in rows][:2] == ["VECOP256_FUSEDMUL_F32LANE", "hadd256_f32lane"]
    # an intrinsic is the language and not the repo: the rename never touched it
    assert "_mm256_fmadd_ps" in [row["name"] for row in rows]


def test_the_signature_on_a_row_names_things_too_and_is_written_forward(shadowed):
    _, shadow_lattice, translated = shadowed
    rows = translated.callees(shadow_lattice, shadow_lattice.get("avx2/float32/dot"))
    by_name = {row["name"]: row for row in rows}
    assert by_name["VECOP256_FUSEDMUL_F32LANE"]["signature"].startswith(
        "#define VECOP256_FUSEDMUL_F32LANE(_acc, _x, _y)"
    )
    assert by_name["hadd256_f32lane"]["signature"] == "static inline float hadd256_f32lane (__m256 v)"
    # everything that is not a name in the tree is the row's own: the tier, the mode, the kind
    assert by_name["hadd256_f32lane"]["provenance"] == "hobbes:semantic"
    assert by_name["hadd256_f32lane"]["also"] == "clang-key"
    assert by_name["_mm256_fmadd_ps"]["provenance"] == "clang-key:macro"


def test_what_the_ledger_could_not_answer_is_carried_and_not_smoothed(shadowed):
    _, shadow_lattice, translated = shadowed
    rows = translated.callees(shadow_lattice, shadow_lattice.get("avx2/float32/dot"))
    assert rows.missing == ["intrinsics"]  # the target's gap is the shadow's gap


def test_a_dropped_expansion_is_carried_with_its_names_written_forward(lattice, ledger):
    """The fixture's drops are clang's own names, which no shadow renames — so the map is made here."""
    renames = {"_mm256_extracti128_si256": "zz_extract", "__builtin_ia32_extract128i256": "zz_builtin"}
    translated = facts.Translated(ledger=ledger, lattice=lattice, renames=renames, map_sha256="d" * 64)
    rows = translated.callees(lattice, lattice.get("avx2/bit1/hamming"))
    dropped = {(row["name"], row["wrote"]) for row in rows.dropped}
    assert ("zz_builtin", "zz_extract") in dropped
    assert all(row["reason"] == facts.DROPPED for row in rows.dropped)  # the reason is prose, not a name


def test_the_translated_ledger_says_which_map_every_name_went_through(shadowed, ledger):
    _, _, translated = shadowed
    source = translated.source()
    assert source["translated_through"] == "d" * 64
    assert source["graph"] == ledger.source()["graph"]  # the provenance is still the target's own
    assert source["key"] == ledger.source()["key"]
