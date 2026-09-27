"""D-12's availability rule: what a kernel file can use, read the way the grader meets it.

Three excerpts of real `clang -E -dD` output ride under `tests/fixtures/preprocessed/` with their
`PROVENANCE.md`, cut in the image at `0c2223a`. The one test that matters is the first: over the nine
intrinsics each excerpt keeps, :func:`lattice.available.parse` must give the **27 of 27** statuses the whole
files gave — `_mm_shuffle_epi8` undeclared on sse2, the `_mm512_` names declared but feature-off on avx2,
and `_mm512_popcnt_epi64` declared and off even on avx512. Everything under it is a unit case for one clause
of the rule, and rule R is exercised on a hand-built table, since the rule is about renaming and not about
clang.

Nothing here runs clang: :func:`lattice.available.build` is the one function that would, and the only thing
tested about it is that it **refuses on the host** (ADR-092, C-64).
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

from lattice import available, run
from lattice.build import ISA_FLAGS

PREPROCESSED = Path(__file__).parent / "fixtures" / "preprocessed"
FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"

#: The fixture's own separator: the `-dM` list follows it (`PROVENANCE.md`).
SEPARATOR = "@@MACROS@@"

#: The nine names each excerpt keeps, and what PROVENANCE.md says of each per file: `True` available,
#: `False` declared and feature-off, `None` not declared there at all.
NINE = ("_mm_add_epi32", "_mm_shuffle_epi8", "_mm_hadd_pd", "_mm256_add_epi32",
        "_mm256_extracti128_si256", "_mm512_reduce_add_ps", "_mm512_extracti32x4_epi32",
        "_mm512_popcnt_epi64", "_mm_castsi128_ps")

STATUSES = {
    # sse2's file includes only <emmintrin.h>: the two SSE2 names are there and nothing else is declared
    "sse2": {"_mm_add_epi32": True, "_mm_castsi128_ps": True},
    # avx2's <immintrin.h> declares every header, so the three `_mm512_` names are declared and off
    "avx2": {
        "_mm_add_epi32": True, "_mm_shuffle_epi8": True, "_mm_hadd_pd": True, "_mm256_add_epi32": True,
        "_mm256_extracti128_si256": True, "_mm512_reduce_add_ps": False,
        "_mm512_extracti32x4_epi32": False, "_mm512_popcnt_epi64": False, "_mm_castsi128_ps": True,
    },
    # avx512's flags are the four the target's Makefile passes, and vpopcntdq is not among them
    "avx512": {
        "_mm_add_epi32": True, "_mm_shuffle_epi8": True, "_mm_hadd_pd": True, "_mm256_add_epi32": True,
        "_mm256_extracti128_si256": True, "_mm512_reduce_add_ps": True,
        "_mm512_extracti32x4_epi32": True, "_mm512_popcnt_epi64": False, "_mm_castsi128_ps": True,
    },
}


def excerpt(isa):
    """One excerpt as the two texts `parse` takes: the `-E -dD` output and the `-dM` list."""
    text = (PREPROCESSED / f"distance-{isa}.pp").read_text(encoding="utf-8")
    preprocessed, macros = text.split(SEPARATOR)
    return preprocessed, macros


# MARK: - the rule on the real output -


@pytest.mark.parametrize("isa", ["sse2", "avx2", "avx512"])
def test_the_real_excerpts_give_provenances_own_statuses(isa):
    """27 of 27 (name, file) pairs, which is what makes the excerpts a fixture and not an illustration."""
    found = available.parse(*excerpt(isa))
    read = {name: (found[name]["available"] if name in found else None) for name in NINE}
    assert read == {name: STATUSES[isa].get(name) for name in NINE}
    # absent means **undeclared**, and that is the sse2 case D-12 exists for
    assert [name for name in NINE if name not in found] == (
        [name for name in NINE if name not in STATUSES[isa]]
    )


def test_a_functions_needs_are_its_target_entries_and_a_no_entry_is_not_one():
    """`__target__("ssse3,no-evex512")` requires SSSE3 and says EVEX-512 is off; only the first is a need."""
    found = available.parse(*excerpt("avx512"))
    assert found["_mm_shuffle_epi8"]["needs"] == ["ssse3"]
    assert found["_mm512_reduce_add_ps"]["needs"] == ["avx512f", "evex512"]
    assert found["_mm512_popcnt_epi64"]["needs"] == ["avx512vpopcntdq", "evex512"]
    # `__EVEX512__` is defined here, so reading `no-evex512` as a need would lose every SSE name
    assert "__EVEX512__" in excerpt("avx512")[1]
    assert found["_mm_add_epi32"]["available"] is True


def test_the_header_is_the_line_marker_in_force():
    found = available.parse(*excerpt("avx2"))
    assert found["_mm_shuffle_epi8"]["header"].endswith("/tmmintrin.h")
    assert found["_mm512_popcnt_epi64"]["header"].endswith("/avx512vpopcntdqintrin.h")


def test_a_macro_takes_its_headers_features():
    """`_mm256_extracti128_si256` carries no `__target__`, so it is avx2 because `avx2intrin.h` is."""
    avx2 = available.parse(*excerpt("avx2"))
    assert avx2["_mm256_extracti128_si256"]["needs"] == ["avx2"]
    assert avx2["_mm256_extracti128_si256"]["available"] is True
    # and the same rule puts `avx512fintrin.h`'s macro out of reach on the same flags
    assert avx2["_mm512_extracti32x4_epi32"]["needs"] == ["avx512f", "evex512"]
    assert avx2["_mm512_extracti32x4_epi32"]["available"] is False


# MARK: - the clauses, one case each -


def test_a_function_head_split_over_two_lines_is_read():
    """clang writes the declarator below the attributes as often as beside them; both are declarations."""
    same = 'static __inline__ __m128i __attribute__((__target__("sse2"))) _mm_beside(__m128i __a) {'
    below = 'static __inline__ __m128i __attribute__((__target__("sse2")))\n_mm_below(__m128i __a)\n{'
    found = available.parse(f'# 1 "h.h" 3\n{same}\n{below}\n', "#define __SSE2__ 1\n")
    assert list(found) == ["_mm_beside", "_mm_below"]
    assert all(entry["needs"] == ["sse2"] and entry["available"] for entry in found.values())
    # the bare `__inline` spelling is clang's too (`avx512fintrin.h` writes it), and is read the same
    bare = 'static __inline __m512i __attribute__((__target__("avx512f")))\n_mm512_bare(int __a)\n'
    assert available.parse(f'# 1 "h.h" 3\n{bare}', "")["_mm512_bare"]["needs"] == ["avx512f"]


def test_a_macro_in_a_header_with_no_functions_has_empty_needs():
    """Every flag set satisfies an empty tuple — which is also how the target's own `#define`s read."""
    found = available.parse('# 1 "alone.h" 3\n#define _mm_alone(x) ((x))\n', "")
    assert found["_mm_alone"] == {"available": True, "needs": [], "header": "alone.h"}


def test_the_first_declaration_owns_the_name():
    text = (
        '# 1 "first.h" 3\nstatic __inline__ int __attribute__((__target__("sse2"))) _mm_twice(int __a) {\n'
        '# 1 "second.h" 3\nstatic __inline__ int __attribute__((__target__("avx512f"))) _mm_twice(int __a) {\n'
    )
    found = available.parse(text, "#define __SSE2__ 1\n")
    assert found["_mm_twice"] == {"available": True, "needs": ["sse2"], "header": "first.h"}


def test_only_the_intrinsic_namespace_is_kept():
    """`_mm…` and `_cvt…`, `intrinsics`' own namespace: the target's own helpers are not intrinsics."""
    text = (
        '# 1 "h.h" 3\nstatic inline float hsum256_ps (__m256 v) {\n'
        'static __inline__ int __attribute__((__target__("sse2"))) _mm_kept(int __a) {\n'
        "#define SOME_MACRO(x) (x)\n"
    )
    assert sorted(available.parse(text, "#define __SSE2__ 1\n")) == ["_mm_kept"]


def test_the_feature_macro_spelling_is_clangs():
    assert available.feature_macro("sse4.1") == "__SSE4_1__"
    assert available.feature_macro("avx512f") == "__AVX512F__"
    assert available.feature_macro("evex512") == "__EVEX512__"


# MARK: - rule R -


def table(available_names=(), unavailable_names=()):
    """A hand-built names map: rule R is about renaming, and clang has nothing to say about it."""
    return {
        **{name: {"available": True, "needs": [], "header": "hand"} for name in available_names},
        **{name: {"available": False, "needs": ["off"], "header": "hand"} for name in unavailable_names},
    }


def test_rule_rs_pre_registered_examples():
    """The four the pre-registration writes down, on the availability it writes them against."""
    sse2 = table(("_mm_slli_epi32", "_mm_loadu_si128"))
    assert available.rename("_mm256_slli_epi32", "sse2", sse2) == "_mm_slli_epi32"
    assert available.rename("_mm256_loadu_si256", "sse2", sse2) == "_mm_loadu_si128"
    # `f128` is a lane index and not the vector's width, so the name keeps it — and has no form here
    assert available.rename("_mm256_extractf128_ps", "sse2", sse2) is None

    avx2 = table(("_mm256_castsi256_ps",))
    assert available.rename("_mm512_castsi512_ps", "avx2", avx2) == "_mm256_castsi256_ps"
    assert available.rename("_mm512_reduce_add_ps", "avx2", avx2) is None


def test_a_name_that_renames_to_itself_has_no_form():
    """A name already in this file's shape offers nothing a student does not already have."""
    sse2 = table(("_mm_add_epi32",))
    assert sse2["_mm_add_epi32"]["available"] is True
    assert available.rename("_mm_add_epi32", "sse2", sse2) is None


def test_a_form_that_exists_but_is_unavailable_is_no_form():
    """Offering a name this file cannot use either would be inventing on the student's behalf."""
    sse2 = table(unavailable_names=("_mm_shuffle_epi8",))
    assert available.rename("_mm256_shuffle_epi8", "sse2", sse2) is None
    assert available.rename("_mm256_shuffle_epi8", "sse2", table(("_mm_shuffle_epi8",))) == (
        "_mm_shuffle_epi8"
    )


def test_an_isa_rule_r_has_no_tables_for_gets_no_form():
    assert available.rename("_mm256_add_epi32", "neon", table(("_mm_add_epi32",))) is None


# MARK: - the record, and where it may be built -


def test_build_refuses_outside_a_container(monkeypatch):
    """It runs clang over a checkout's own text, so it is the image's work and nothing else's."""
    monkeypatch.setattr(run, "in_container", lambda: False)
    with pytest.raises(run.NotContained) as refused:
        available.build(FIXTURE)
    assert "ADR-092" in str(refused.value)


def test_the_flags_are_the_graders_own_per_isa():
    """`build.ISA_FLAGS` and the relative include pair — the command PROVENANCE.md cut its excerpts with."""
    for isa in available.native():
        assert available.preprocess_flags(isa) == ("-O2", "-Isrc", "-Ilibs", *ISA_FLAGS[isa])
    assert available.native() == ["sse2", "avx2", "avx512"]
    assert available.kernel_file("avx2") == "src/distance-avx2.c"
    # nothing in the flags names a path of this box: clang runs from the target's root
    assert not any(part.startswith("/") for part in available.preprocess_flags("avx512"))


def test_load_and_record_meta_read_the_file_back(tmp_path):
    record = {
        isa: {
            "isa": isa,
            "file": available.kernel_file(isa),
            "flags": list(available.preprocess_flags(isa)),
            "clang": "Ubuntu clang version 18.1.3",
            "target_sha": "0c2223a",
            "names": {
                "_mm_add_epi32": {"available": True, "needs": ["sse2"], "header": "emmintrin.h"},
                "_mm512_popcnt_epi64": {"available": False, "needs": ["avx512vpopcntdq"], "header": "v.h"},
            },
        }
        for isa in ("sse2", "avx2")
    }
    path = tmp_path / "available.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    assert available.load(path) == record
    assert available.names_for(available.load(path), "sse2")["_mm_add_epi32"]["available"] is True
    assert available.names_for(available.load(path), "avx512") == {}

    block = available.record_meta(path)
    assert block["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert block["isas"]["avx2"]["flags"] == ["-O2", "-Isrc", "-Ilibs", "-mavx2", "-mfma"]
    assert block["isas"]["avx2"]["clang"] == "Ubuntu clang version 18.1.3"
    assert block["isas"]["avx2"]["names"] == 2 and block["isas"]["avx2"]["available"] == 1
    assert sorted(block["isas"]) == ["avx2", "sse2"]


def test_the_excerpts_are_the_whole_files_command():
    """The fixture says which command cut it, and this holds the record to the flags this module builds."""
    provenance = (PREPROCESSED / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "-E -dD" in provenance and "-dM -E -x c /dev/null" in provenance
    assert "27 of 27" in provenance
    # every excerpt carries the separator its `-dM` list follows, and both halves are non-empty
    for isa in available.native():
        preprocessed, macros = excerpt(isa)
        assert preprocessed.strip() and re.search(r"^#define __\w+__", macros, re.M)
