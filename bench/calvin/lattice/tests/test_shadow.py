"""The two rename shadows: the plan is a bijection, the names are gone, and the code still runs.

Everything here is over the real-source fixture and its own Hobbes ingest, so the set of names a shadow
renames is the graph's answer about this tree and not a list written by hand.
"""

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from lattice import diff, grade, shadow
from lattice.cells import ISAS, NATIVE
from lattice.cells import build as build_lattice

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"
DERIVED = FIXTURE / "derived"


@pytest.fixture(scope="module")
def graph():
    return json.loads((DERIVED / "graph.json").read_text())


@pytest.fixture(scope="module")
def plans(graph):
    return {style: shadow.plan(FIXTURE, graph, style) for style in shadow.STYLES}


@pytest.fixture(scope="module")
def shadows(plans, tmp_path_factory):
    root = tmp_path_factory.mktemp("shadows")
    return {style: shadow.write(plan, root / style) for style, plan in plans.items()}


# MARK: - the names -


def test_the_descriptive_name_of_a_kernel_reads_like_the_kernel_it_is(plans):
    renames = plans["descriptive"].renames
    assert renames["float32_distance_dot_avx2"] == "f32_dist_inner_x86v2"
    assert renames["float32_distance_l2_impl_avx2"] == "f32_dist_euclid_core_x86v2"
    assert renames["bit1_distance_hamming_avx512"] == "b1_dist_bitdiff_x86v4"
    assert renames["int8_distance_l2_neon_imp"] == "i8_dist_euclid_armv8_core"
    assert renames["hsum256_ps"] == "hadd256_f32lane"  # a stem with a digit tail keeps the tail


def test_a_macro_keeps_its_case_and_a_word_the_table_does_not_hold_keeps_itself(plans):
    renames = plans["descriptive"].renames
    assert renames["MM256_FMA_PS"] == "VECOP256_FUSEDMUL_F32LANE"
    assert renames["S8_TO_BIASED_U8_AVX2"] == "S8_INTO_OFFSET_U8_X86V2"  # S8 and U8 are not in the table


def test_a_name_no_word_of_which_the_table_holds_falls_back_to_the_prefix():
    assert shadow.descriptive("qqq_zzz") == "sv_qqq_zzz"
    assert shadow.descriptive("wibble") == "sv_wibble"


def test_the_fixtures_names_need_no_fall_back(plans):
    # the `sv_` prefix still carries the original whole, so a shadow that uses it is a shadow that
    # leaks; `prefixed` is the signal to extend the table, and the table is written for this target
    for style, plan in plans.items():
        assert plan.prefixed == (), style


def test_opaque_numbers_by_kind_in_the_order_of_path_and_line(plans):
    renames = plans["opaque"].renames
    assert re.fullmatch(r"fn_\d{4}", renames["float32_distance_dot_avx2"])
    assert re.fullmatch(r"MC_\d{4}", renames["MM256_FMA_PS"])
    assert re.fullmatch(r"ty_\d{4}", renames["vector_type"])
    # src/distance-avx2.c comes before src/distance-avx512.c, and within a file the line decides
    assert renames["MM256_FMA_PS"] < renames["S8_TO_BIASED_U8_AVX2"]
    assert renames["_mm256_abs_ps"] < renames["MM256_FMA_PS"]


def test_every_plan_is_a_bijection(plans):
    for style, plan in plans.items():
        assert len(set(plan.renames.values())) == len(plan.renames), style
        assert set(plan.reverse()) == set(plan.renames.values()), style
        assert plan.reverse()[plan.renames["float32_distance_dot_avx2"]] == "float32_distance_dot_avx2"


def test_the_two_shadows_rename_the_same_set(plans):
    assert set(plans["descriptive"].renames) == set(plans["opaque"].renames)


def test_an_unknown_style_is_refused(graph):
    with pytest.raises(ValueError):
        shadow.plan(FIXTURE, graph, "meaningful")


# MARK: - what is not renamed, and why -


def test_kept_lists_the_enum_constants_as_not_a_graph_symbol(plans):
    for style, plan in plans.items():
        kept = {row["name"]: row["reason"] for row in plan.kept}
        for constant in ("VECTOR_TYPE_F32", "VECTOR_TYPE_BIT", "VECTOR_DISTANCE_HAMMING", "VECTOR_QUANT_AUTO"):
            assert kept.get(constant) == "not-a-graph-symbol", (style, constant)
        assert kept.get("dispatch_distance_table") == "not-a-graph-symbol"
        assert kept.get("VECTOR_TYPE_MAX") == "not-a-graph-symbol"
        assert not set(kept) & set(plan.renames)  # kept and renamed are disjoint by construction


def test_the_entry_point_is_kept_even_though_the_graph_does_not_name_it(plans, graph):
    assert "sqlite3_vector_init" not in {s["name"] for s in graph["symbols"]}
    for plan in plans.values():
        assert {"name": "sqlite3_vector_init", "reason": "entry-point"} in plan.kept


def test_a_self_referential_macro_is_kept_as_external(plans):
    # distance-avx512.c writes `#define _mm512_abs_ps(x) _mm512_abs_ps(x)`, which C11 6.10.3.4p2 makes
    # a pass-through to clang's own intrinsic. Renaming it sends the call to a definition that is not
    # there, which is the `strcasestr` class exactly.
    for style, plan in plans.items():
        assert {"name": "_mm512_abs_ps", "reason": "external"} in plan.kept, style
        assert "_mm512_abs_ps" not in plan.renames
        assert plan.renames["_mm256_abs_ps"]  # the AVX2 one is not self-referential, so it is renamed


def test_self_referential_reads_both_arms_of_an_if():
    text = "#if A\n#define X(v) X(v)\n#else\n#define X(v) (v)\n#endif\n#define Y(v) (v)\n"
    assert shadow.self_referential(text) == {"X"}


def test_a_veto_the_graph_only_partly_names_is_said(graph):
    partial = json.loads(json.dumps(graph))
    partial["lane_agreement"]["external_vetoes"] = {
        "sites": 12,
        "examples": [{"file": "src/x.c", "line": 1, "name": "strcasestr", "lane_a": "src/x.c:31"}],
    }
    plan = shadow.plan(FIXTURE, partial, "opaque")
    assert any("external_vetoes: 12 site(s), 1 example(s)" in gap for gap in plan.missing)
    assert {"name": "strcasestr", "reason": "external"} not in plan.kept  # the fixture never writes it


# MARK: - the scanner behind `kept` -


def test_declarations_reads_the_enum_constants_the_typedef_and_the_globals():
    found = shadow.declarations(
        """
        typedef enum { VECTOR_TYPE_F32 = 1, VECTOR_TYPE_BIT } vector_type;
        #define VECTOR_TYPE_MAX 7
        typedef float (*distance_function_t)(const void *v1, const void *v2, int n);
        extern distance_function_t dispatch_distance_table[VECTOR_DISTANCE_MAX][VECTOR_TYPE_MAX];
        float turbo_lut_dot_cpu (const uint8_t *packed, int packed_bytes);
        static inline float hsum (float v) { return v; }
        """
    )
    assert "VECTOR_TYPE_F32" in found and "VECTOR_TYPE_BIT" in found
    assert "vector_type" in found and "VECTOR_TYPE_MAX" in found
    assert "distance_function_t" in found and "dispatch_distance_table" in found
    assert "turbo_lut_dot_cpu" in found and "hsum" in found
    # a parameter is not a declaration of this file's, however much it looks like one from here
    assert "packed_bytes" not in found and "n" not in found


def test_declarations_answers_with_the_defines_when_the_text_does_not_scan():
    assert shadow.declarations("#define A 1\n}\n") == ("A",)


# MARK: - applying a plan -


def test_a_string_literal_is_not_renamed_and_a_comment_is(plans):
    plan = plans["descriptive"]
    new = plan.renames["float32_distance_dot_avx2"]
    text = (
        '/* float32_distance_dot_avx2 is the f32 dot kernel */\n'
        'const char *sql = "float32_distance_dot_avx2";\n'
        "float x = float32_distance_dot_avx2(a, b, n);\n"
        "char c = 'x';  // float32_distance_dot_avx2 again, after an apostrophe: don't\n"
    )
    out = shadow.apply(plan, text)
    assert '"float32_distance_dot_avx2"' in out  # the SQL-visible name is a string and stays
    assert out.count(new) == 3  # the comment, the call, and the comment after the apostrophe
    assert "float32_distance_dot_avx2(" not in out


def test_a_whole_word_is_renamed_and_a_prefix_of_one_is_not(plans):
    plan = plans["descriptive"]
    out = shadow.apply(plan, "hsum256_ps(v); my_hsum256_ps(v); hsum256_ps_x(v);\n")
    assert out == "hadd256_f32lane(v); my_hsum256_ps(v); hsum256_ps_x(v);\n"


def test_applying_a_plan_to_a_shadow_changes_nothing(plans, shadows):
    """Nothing renameable is left outside a literal: the rename really did reach every token."""
    for style, plan in plans.items():
        for file in plan.files:
            text = (shadows[style] / file).read_text()
            assert shadow.apply(plan, text) == text, (style, file)


def test_no_original_name_survives_outside_a_string_in_any_shadow_file(plans, shadows):
    for style, plan in plans.items():
        pattern = re.compile(r"\b(" + "|".join(map(re.escape, plan.renames)) + r")\b")
        for file in plan.files:
            text = (shadows[style] / file).read_text()
            literal = shadow._literals(text)
            left = [m.group(1) for m in pattern.finditer(text) if not literal[m.start()]]
            assert left == [], (style, file, left[:5])
            # stronger, and independent of this module's own idea of where a literal is: the fixture
            # writes no kernel name into a string, so the count anywhere in the file is zero
            assert pattern.search(text) is None, (style, file)


# MARK: - what is written -


def test_the_shadow_carries_the_build_and_its_map(plans, shadows):
    for style, written in shadows.items():
        assert (written / "Makefile").read_text() == (FIXTURE / "Makefile").read_text()
        assert (written / "libs" / "fp16" / "fp16.h").read_text() == (FIXTURE / "libs" / "fp16" / "fp16.h").read_text()
        payload = json.loads((written / "shadow-map.json").read_text())
        assert payload["style"] == style
        assert payload["renames"] == plans[style].renames
        assert payload["counts"]["renamed"] == len(plans[style].renames)
        assert shadow.load(written / "shadow-map.json") == plans[style].reverse()


def test_the_targets_own_ingest_is_not_copied_into_a_shadow(shadows):
    # `derived/` is an artifact of the original names; carrying it in would hand every one of them back
    for written in shadows.values():
        assert not (written / "derived").exists()


def test_the_prose_that_still_names_the_originals_is_measured_not_ignored(plans, shadows):
    for style, plan in plans.items():
        leaked = {row["file"]: row for row in shadow.leaks(plan, shadows[style])}
        assert "PROVENANCE.md" in leaked, style  # it lists the kernels the fixture kept
        assert "bit1_distance_hamming_avx512" in leaked["PROVENANCE.md"]["names"]
        assert json.loads((shadows[style] / "shadow-map.json").read_text())["leaks"] == shadow.leaks(
            plan, shadows[style]
        )


# MARK: - what identifies a written shadow (E2-c) -


def test_the_tree_digest_is_the_renamed_files_and_moves_only_with_them(plans, shadows, tmp_path):
    """A shadow is not a checkout, so this is what an `e1 run` is held to in place of a SHA."""
    written = shutil.copytree(shadows["descriptive"], tmp_path / "copy")
    assert shadow.tree_digest(written) == shadow.tree_digest(shadows["descriptive"])
    assert shadow.tree_digest(written) != shadow.tree_digest(shadows["opaque"])

    (written / "README-ish.md").write_text("prose the rename never touched\n")
    assert shadow.tree_digest(written) == shadow.tree_digest(shadows["descriptive"])

    kernel = written / "src" / "distance-avx2.c"
    kernel.write_text(kernel.read_text() + "\n/* one more line */\n")
    assert shadow.tree_digest(written) != shadow.tree_digest(shadows["descriptive"])


def test_the_map_digest_is_the_maps_own_bytes_and_the_map_reads_back_whole(plans, shadows):
    for style, written in shadows.items():
        payload = shadow.read_map(written / "shadow-map.json")
        assert payload["style"] == style
        assert payload["kept"] == [dict(row) for row in plans[style].kept]
        assert shadow.map_digest(written / "shadow-map.json") == hashlib.sha256(
            (written / "shadow-map.json").read_bytes()
        ).hexdigest()
    assert shadow.map_digest(shadows["descriptive"] / "shadow-map.json") != shadow.map_digest(
        shadows["opaque"] / "shadow-map.json"
    )


# MARK: - the lattice of a shadow -


def test_each_shadow_is_the_same_grid_under_new_names(plans, shadows):
    for style, plan in plans.items():
        lattice = build_lattice(shadows[style], rename=plan.reverse())
        assert lattice.unmatched == ()
        for isa in ISAS:
            assert len(lattice.by_isa(isa)) == 13, (style, isa)
        cell = lattice.get("avx2/float32/dot")
        assert cell.name == plan.renames["float32_distance_dot_avx2"]
        assert cell.original == "float32_distance_dot_avx2"
        assert cell.slots == (("DOT", "F32"),)  # the table and its constants are not renamed
        impl = lattice.get("avx2/float32/l2_impl")
        assert impl.kind == "impl" and impl.graded_via == (("L2", "F32"), ("SQUARED_L2", "F32"))


def test_without_the_map_a_shadow_has_no_grid_at_all(shadows):
    # the point of `rename`: the grid is read off `<type>_distance_<metric>_<isa>`, which a shadow
    # does not write, so a lattice built without the map is empty rather than wrong
    assert build_lattice(shadows["opaque"]).cells == {}


# MARK: - collisions -


def test_two_names_that_would_become_one_are_refused(monkeypatch, graph):
    monkeypatch.setitem(shadow.SYNONYMS, "sse2", "x86")
    monkeypatch.setitem(shadow.SYNONYMS, "avx2", "x86")
    with pytest.raises(shadow.Collision) as refusal:
        shadow.plan(FIXTURE, graph, "descriptive")
    assert "would both become" in str(refusal.value)


def test_a_name_the_tree_already_writes_is_refused(monkeypatch, graph):
    # `dispatch_distance_table` is a token of the tree that no plan renames, so landing on it merges
    monkeypatch.setitem(shadow.SYNONYMS, "popcount64", "dispatch_distance_table")
    with pytest.raises(shadow.Collision) as refusal:
        shadow.plan(FIXTURE, graph, "descriptive")
    assert "which the tree already writes" in str(refusal.value)


def test_a_refused_plan_writes_nothing(monkeypatch, graph, tmp_path):
    monkeypatch.setitem(shadow.SYNONYMS, "sse2", "x86")
    monkeypatch.setitem(shadow.SYNONYMS, "avx2", "x86")
    with pytest.raises(shadow.Collision):
        shadow.write(shadow.plan(FIXTURE, graph, "descriptive"), tmp_path / "nope")
    assert not (tmp_path / "nope").exists()


# MARK: - execution: the shadows compile and run -


def has_avx512() -> bool:
    try:
        return "avx512f" in Path("/proc/cpuinfo").read_text()
    except OSError:  # pragma: no cover - not a Linux box
        return False


@pytest.mark.skipif(shutil.which("clang") is None, reason="a shadow's golds are compiled and run; the image has clang")
@pytest.mark.parametrize("style", shadow.STYLES)
def test_every_native_gold_of_each_shadow_still_passes(plans, shadows, style, tmp_path):
    """E0's acceptance for the shadows: same program, new names, every gold still `pass`.

    `shadow.grading` is the seam that lets the existing graders read a shadow — the lattice through the
    reverse map, and `diff`'s generated driver, which names `init_distance_functions_<isa>` and
    `distance_function_t` in its own C, through the plan.
    """
    plan = plans[style]
    root = shadows[style]
    with shadow.grading(plan.reverse()):
        lattice = grade.build_lattice(root)
        cells = sorted(
            cell.id
            for cell in lattice.cells.values()
            if cell.isa in NATIVE and (has_avx512() or cell.isa != "avx512")
        )
        entries = [{"id": cell, "cell": cell, "body": "gold"} for cell in cells]
        results = grade.grade(root, entries, tmp_path / style, allow_host=True)
    assert len(results) == len(cells)
    assert [(r["cell"], r["class"], r["reason"]) for r in results if r["class"] != "pass"] == []
    assert all(r["reg"] is True for r in results)


def test_the_grading_seam_puts_the_two_names_back(plans):
    before = (grade.build_lattice, diff.driver_source)
    with shadow.grading(plans["opaque"].reverse()):
        assert (grade.build_lattice, diff.driver_source) != before
        assert "init_distance_functions_avx2" not in diff.driver_source()
    assert (grade.build_lattice, diff.driver_source) == before


def test_a_name_another_file_declares_is_kept_not_renamed(tmp_path):
    """Session c141's review: `sqlite3_mutex_alloc` is an in-repo macro on one `#if` arm and SQLite's API on
    the other, declared in `libs/sqlite3.h`. The first real shadows renamed it and failed to link."""
    (tmp_path / "src").mkdir()
    (tmp_path / "libs").mkdir()
    (tmp_path / "src" / "a.c").write_text(
        "#if defined(NO_THREADS)\n#define api_alloc(_t) 0\n#endif\n"
        "int own_helper(int x) { return x; }\n"
        "int use(void) { return api_alloc(1) + own_helper(2); }\n"
    )
    (tmp_path / "libs" / "api.h").write_text("/* own_helper is only named in this comment */\nint api_alloc(int);\n")
    graph = {"symbols": [
        {"id": "src/a.api_alloc", "name": "api_alloc", "kind": "macro", "line": 2, "module": "src/a"},
        {"id": "src/a.own_helper", "name": "own_helper", "kind": "function", "line": 4, "module": "src/a"},
        {"id": "src/a.use", "name": "use", "kind": "function", "line": 5, "module": "src/a"},
    ]}
    p = shadow.plan(tmp_path, graph, "opaque")
    assert "api_alloc" not in p.renames
    assert {"name": "api_alloc", "reason": "declared-outside"} in p.kept
    assert "own_helper" in p.renames  # a word in another file's comment is not a declaration
