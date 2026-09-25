"""G-hsr: what a bucket is, where an invented name comes from, and the order the classes are tested in."""

from pathlib import Path

from lattice import hsr

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"

# clang 18 and GNU ld, written as they write them.
CLANG_UNDECLARED = (
    "src/distance-avx2.c:130:19: error: call to undeclared function '_mm256_lattice_ps'; "
    "ISO C99 and later do not support implicit function declarations"
)
CLANG_IDENTIFIER = "src/distance-avx2.c:131:5: error: use of undeclared identifier 'float32_distance_l7_avx2'"
CLANG_TYPE = "src/distance-avx2.c:132:5: error: unknown type name '__m384'"
LD_UNDEFINED = (
    "/usr/bin/ld: /tmp/lattice-x/objects/distance-avx2-0.o: in function `float32_distance_dot_avx2':\n"
    "distance-avx2.c:(.text+0x51): undefined reference to `hsum256_missing'"
)


def test_an_intrinsic_is_anything_built_of_the_intrinsic_stems():
    for name in ("_mm256_lattice_ps", "_mm_add_ps", "__m384", "__builtin_lattice"):
        assert hsr.bucket(name) == "intrinsic", name


def test_a_kernel_shaped_name_is_in_repo_even_when_nothing_defines_it():
    assert hsr.bucket("float32_distance_l7_avx2") == "in-repo"
    assert hsr.bucket("bit1_distance_jaccard_avx512") == "in-repo"


def test_a_name_the_target_defines_is_in_repo():
    known = hsr.inventory(FIXTURE)
    assert "hsum256_ps" in known  # a static helper
    assert "LASSQ_UPDATE" in known  # a macro
    assert hsr.bucket("hsum256_ps", known) == "in-repo"
    assert hsr.bucket("LASSQ_UPDATE", known) == "in-repo"


def test_everything_else_is_other():
    assert hsr.bucket("sqrtf") == "other"
    assert hsr.bucket("lattice_helper_that_is_nowhere") == "other"


def test_the_four_messages_are_the_whole_source_of_an_invented_name():
    found = hsr.invented([CLANG_UNDECLARED, CLANG_IDENTIFIER, CLANG_TYPE, LD_UNDEFINED])
    assert [i.name for i in found] == [
        "_mm256_lattice_ps",
        "float32_distance_l7_avx2",
        "__m384",
        "hsum256_missing",
    ]
    assert [i.bucket for i in found] == ["intrinsic", "in-repo", "intrinsic", "other"]


def test_a_name_is_named_once_however_many_times_it_is_reported():
    found = hsr.invented([CLANG_UNDECLARED, CLANG_UNDECLARED, CLANG_UNDECLARED])
    assert [i.name for i in found] == ["_mm256_lattice_ps"]


def test_a_clean_build_invented_nothing():
    assert hsr.invented(["src/distance-avx2.c:9:1: warning: unused function 'hsum256d' [-Wunused-function]"]) == ()


def test_the_class_of_a_body_that_did_not_compile_turns_on_whether_it_invented():
    invented = hsr.invented([CLANG_UNDECLARED])
    assert hsr.classify(compiled=False, invented_names=invented) == "invented"
    assert hsr.classify(compiled=False) == "compile"


def test_a_slot_the_init_never_installed_is_never_read_as_a_pass():
    assert hsr.classify(compiled=True, installed=False) == "not-installed"
    assert hsr.classify(compiled=True, installed=False, bulk_failed=0, edge_failed=0) == "not-installed"


def test_a_bulk_failure_a_crash_and_a_timeout_are_all_wrong():
    assert hsr.classify(compiled=True, bulk_failed=1) == "wrong"
    assert hsr.classify(compiled=True, crashed=True) == "wrong"
    assert hsr.classify(compiled=True, crashed=True, edge_failed=3) == "wrong"


def test_edge_is_every_bulk_case_passing_and_an_edge_case_not():
    assert hsr.classify(compiled=True, edge_failed=1) == "edge"
    assert hsr.classify(compiled=True, bulk_failed=1, edge_failed=1) == "wrong"


def test_a_body_that_did_everything_passes():
    assert hsr.classify(compiled=True) == "pass"
    assert set(hsr.CLASSES) == {"invented", "compile", "not-installed", "wrong", "edge", "pass"}
