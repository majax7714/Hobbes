"""G-compile and the graders end to end: the flags, the diagnostics parser, and what a body is graded as."""

import shutil
from pathlib import Path

import pytest

from lattice import build, grade, run
from lattice.cells import NATIVE
from lattice.cells import build as build_lattice

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"

# clang 18 with `-fno-color-diagnostics -fno-caret-diagnostics`, and the linker behind it.
CLANG_OUTPUT = """\
/tmp/lattice-abc/target/src/distance-avx2.c:130:19: error: call to undeclared function '_mm256_lattice_ps'; ISO C99 and later do not support implicit function declarations
/tmp/lattice-abc/target/src/distance-avx2.c:131:5: warning: unused variable 'acc0' [-Wunused-variable]
/tmp/lattice-abc/target/src/distance-avx2.c:204:1: error: expected '}'
/tmp/lattice-abc/target/src/distance-avx2.c:198:36: note: to match this '{'
/tmp/lattice-abc/target/src/distance-cpu.h:88:1: fatal error: 'nowhere.h' file not found
2 errors generated.
"""


# MARK: - the flags -


def test_the_flags_are_the_targets_makefile():
    assert build.CFLAGS == ("-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-unused-function", "-O2")
    assert build.ISA_FLAGS["avx2"] == ("-mavx2", "-mfma")
    assert build.ISA_FLAGS["avx512"] == ("-mavx512f", "-mavx512bw", "-mavx512vl", "-mavx512dq")
    for baseline in ("cpu", "sse2", "neon", "rvv"):
        assert build.ISA_FLAGS[baseline] == (), baseline


def test_a_units_flags_are_the_includes_then_its_isas():
    flags = build.flags_for("/x/target", "avx2")
    assert flags[-2:] == ("-mavx2", "-mfma")
    assert "-I/x/target/src" in flags and "-I/x/target/libs" in flags


def test_the_compiler_is_the_argument_then_cc_then_clang(monkeypatch):
    monkeypatch.delenv("CC", raising=False)
    assert build.cc() == "clang"
    monkeypatch.setenv("CC", "gcc")
    assert build.cc() == "gcc"
    assert build.cc("clang-18") == "clang-18"


# MARK: - the diagnostics parser -


def test_every_severity_is_read_and_the_paths_come_back_relative():
    found = build.parse_diagnostics(CLANG_OUTPUT, "/tmp/lattice-abc/target")
    assert [(d.file, d.line, d.col, d.severity) for d in found] == [
        ("src/distance-avx2.c", 130, 19, "error"),
        ("src/distance-avx2.c", 131, 5, "warning"),
        ("src/distance-avx2.c", 204, 1, "error"),
        ("src/distance-avx2.c", 198, 36, "note"),
        ("src/distance-cpu.h", 88, 1, "fatal error"),
    ]
    assert found[0].message.startswith("call to undeclared function '_mm256_lattice_ps'")
    assert found[2].message == "expected '}'"


def test_only_an_error_is_fatal():
    found = build.parse_diagnostics(CLANG_OUTPUT, "/tmp/lattice-abc/target")
    assert [d.fatal for d in found] == [True, False, True, False, True]
    assert len([d for d in found if d.fatal]) == 3


def test_a_line_that_is_not_a_diagnostic_is_not_one():
    assert build.parse_diagnostics("2 errors generated.\nclang: error: linker command failed\n", "/x") == ()


def test_a_path_outside_the_root_is_kept_as_clang_wrote_it():
    found = build.parse_diagnostics("/usr/include/x.h:1:1: error: nope\n", "/tmp/lattice-abc/target")
    assert found[0].file == "/usr/include/x.h"


def test_a_diagnostic_prints_itself_the_way_clang_did():
    found = build.parse_diagnostics(CLANG_OUTPUT, "/tmp/lattice-abc/target")
    assert found[2].text() == "src/distance-avx2.c:204:1: error: expected '}'"


# MARK: - the object cache -


def test_the_cache_key_is_the_text_and_the_flags(tmp_path):
    cache = build.ObjectCache(tmp_path)
    assert cache.key("int f(void){return 0;}", ("-O2",)) == cache.key("int f(void){return 0;}", ("-O2",))
    assert cache.key("int f(void){return 0;}", ("-O2",)) != cache.key("int f(void){return 1;}", ("-O2",))
    assert cache.key("int f(void){return 0;}", ("-O2",)) != cache.key("int f(void){return 0;}", ("-O0",))


def test_only_a_staged_copy_is_made(tmp_path):
    root = grade.stage(FIXTURE, tmp_path / "target")
    assert sorted(p.name for p in root.iterdir()) == ["libs", "src"]
    assert (root / "libs" / "fp16" / "fp16.h").exists()
    assert (root / "src" / "distance-avx512.c").exists()


# MARK: - grading, which compiles and runs the fixture -


def has_avx512() -> bool:
    try:
        return "avx512f" in Path("/proc/cpuinfo").read_text()
    except OSError:  # pragma: no cover - not a Linux box
        return False


needs_clang = pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")


def native_cells() -> list[str]:
    lattice = build_lattice(FIXTURE)
    return sorted(
        cell.id
        for cell in lattice.cells.values()
        if cell.isa in NATIVE and (has_avx512() or cell.isa != "avx512")
    )


def test_the_fixture_has_thirty_nine_native_cells():
    lattice = build_lattice(FIXTURE)
    assert len([c for c in lattice.cells.values() if c.isa in NATIVE]) == 39


def test_grading_outside_a_container_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "in_container", lambda: False)
    with pytest.raises(run.NotContained):
        grade.grade(FIXTURE, [], tmp_path)


@needs_clang
def test_every_native_golds_body_passes(tmp_path):
    cells = native_cells()
    entries = [{"id": cell, "cell": cell, "body": "gold"} for cell in cells]
    results = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)
    failed = [(r["cell"], r["class"], r["reason"], r["first_failure"]) for r in results if r["class"] != "pass"]
    assert failed == []
    assert len(results) == len(cells)
    assert all(r["reg"] is True for r in results)
    assert all(r["bulk"]["failed"] == 0 and r["edge"]["failed"] == 0 for r in results)
    assert all(r["feedback"] == "" for r in results)


@needs_clang
def test_a_gold_is_graded_through_every_slot_it_is_reached_by(tmp_path):
    entries = [{"id": "impl", "cell": "sse2/float32/l2_impl", "body": "gold"}]
    result = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)[0]
    assert [slot["slot"] for slot in result["slots"]] == ["L2:F32", "SQUARED_L2:F32"]
    assert all(slot["installed"] for slot in result["slots"])


@needs_clang
def test_a_body_that_is_fine_c_and_writes_the_wrong_answer_is_wrong(tmp_path):
    body = """{
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;
    float total = 0.0f;
    for (int i = 0; i < n; ++i) {
        total += a[i] * a[i];   /* b is the one it should have read */
    }
    (void)b;
    return -total;
}"""
    entries = [{"id": "hand-written", "cell": "sse2/float32/dot", "body": body}]
    result = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)[0]
    assert result["class"] == "wrong"
    assert result["invented"] == []  # it compiled: nothing was invented
    assert result["bulk"]["failed"] > 0
    assert result["first_failure"]["slot"] == "DOT:F32"
    assert "disagrees with the scalar reference" in result["feedback"]


@needs_clang
def test_an_unbalanced_body_is_a_compile_result_with_the_reason_and_never_an_exception(tmp_path):
    entries = [{"id": "truncated", "cell": "avx2/int8/dot", "body": "{\n    return -(float)total;"}]
    result = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)[0]
    assert result["class"] == "compile"
    assert result["reason"] == "a body runs from '{' to its matching '}'"
    assert result["feedback"] == "a body runs from '{' to its matching '}'"


@needs_clang
def test_a_body_that_invents_an_intrinsic_is_invented_and_not_merely_uncompiled(tmp_path):
    entries = [{"id": "sand", "cell": "avx2/float32/dot", "body": "{\n    return _mm256_lattice_reduce_ps(v1, v2, n);\n}"}]
    result = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)[0]
    assert result["class"] == "invented"
    assert [i["name"] for i in result["invented"]] == ["_mm256_lattice_reduce_ps"]
    assert result["invented"][0]["bucket"] == "intrinsic"
    assert result["diagnostics"][0]["file"] == "src/distance-avx2.c"


@needs_clang
def test_a_body_that_dies_is_wrong_with_the_signal_named(tmp_path):
    # `__builtin_trap` needs no header, so this compiles and then dies — which is the case the crash
    # path is for. It is read as `wrong` and never as "the ISA was not available".
    entries = [{"id": "trap", "cell": "avx2/float32/dot", "body": "{\n    __builtin_trap();\n    return 0.0f;\n}"}]
    result = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)[0]
    assert result["class"] == "wrong"
    assert "died on SIG" in result["reason"]
    assert result["invented"] == []


@needs_clang
def test_a_cell_no_lattice_has_is_a_result_and_not_a_raise(tmp_path):
    result = grade.grade(FIXTURE, [{"id": "x", "cell": "avx2/float32/nope", "body": "gold"}], tmp_path, allow_host=True)[0]
    assert result["class"] == "compile"
    assert "no cell" in result["reason"]


@needs_clang
def test_nothing_a_result_carries_is_a_path_on_this_box(tmp_path):
    entries = [{"id": "sand", "cell": "avx2/float32/dot", "body": "{\n    return _mm256_lattice_reduce_ps(v1, v2, n);\n}"}]
    result = grade.grade(FIXTURE, entries, tmp_path, allow_host=True)[0]
    assert str(tmp_path) not in result["feedback"]
    assert all(str(tmp_path) not in d["file"] for d in result["diagnostics"])
