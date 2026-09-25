"""The gate on the instruments: the four mutants' text, and the classes they get on real fixture cells."""

import shutil
from pathlib import Path

import pytest

from lattice import grade, holes, selftest
from lattice.cells import build

FIXTURE = Path(__file__).parent / "fixtures" / "sqlite-vector-kernels"

#: The four the unit names: an `_impl` graded through its wrappers, a plain body, a wrapper, and the
#: `static` AVX-512 hamming that only the table can reach.
GATE_CELLS = ("sse2/float32/l2_impl", "avx2/int8/dot", "avx2/float32/l2", "avx512/bit1/hamming")


@pytest.fixture(scope="module")
def lattice():
    return build(FIXTURE)


def gold(lattice, cell_id: str) -> str:
    cell = lattice.get(cell_id)
    return holes.gold_body(lattice.text(cell), cell)


# MARK: - the mutants' text -


def test_the_syntax_mutant_drops_the_bodys_last_semicolon(lattice):
    body = gold(lattice, "sse2/int8/dot")
    mutant = selftest.mutate(body, "syntax")
    assert body.endswith("return -(float)total;\n}")
    assert mutant.endswith("return -(float)total\n}")
    assert mutant.count(";") == body.count(";") - 1


def test_the_syntax_mutant_of_a_wrapper_is_its_one_statement_unterminated(lattice):
    mutant = selftest.mutate(gold(lattice, "avx2/float32/l2"), "syntax")
    assert mutant == "{\n    return float32_distance_l2_impl_avx2(v1, v2, n, true)\n}"


def test_the_invented_mutant_calls_a_name_built_of_intrinsic_stems(lattice):
    for cell_id in ("avx2/float32/l2", "sse2/int8/dot"):
        mutant = selftest.mutate(gold(lattice, cell_id), "invented")
        assert mutant.startswith("{\n    (void)_mm_lattice_invented_ps(0);\n")
        assert mutant.endswith("}")


def test_the_wrong_mutant_rewrites_every_return(lattice):
    wrapper = selftest.mutate(gold(lattice, "avx2/float32/l2"), "wrong")
    assert wrapper == "{\n    return (float32_distance_l2_impl_avx2(v1, v2, n, true)) * 1.5f + 1.0f;\n}"
    body = selftest.mutate(gold(lattice, "sse2/int8/dot"), "wrong")
    assert body.endswith("return (-(float)total) * 1.5f + 1.0f;\n}")
    assert body.count("return (") == gold(lattice, "sse2/int8/dot").count("return ")


def test_the_edge_mutant_guards_on_a_size_the_bulk_grid_never_has(lattice):
    for cell_id in ("avx2/float32/l2", "sse2/int8/dot"):
        mutant = selftest.mutate(gold(lattice, cell_id), "edge")
        assert mutant.startswith("{\n    if (n % 64 != 0) return -12345.0f;\n")


def test_every_mutant_is_still_a_balanced_body(lattice):
    for cell_id in GATE_CELLS:
        for mutant in selftest.MUTANTS:
            holes.fill(holes.HOLE, selftest.mutate(gold(lattice, cell_id), mutant))  # does not raise


def test_an_unknown_mutant_is_refused(lattice):
    with pytest.raises(ValueError, match="no mutant"):
        selftest.mutate(gold(lattice, "avx2/float32/l2"), "off-by-one")


def test_what_each_mutant_must_read():
    assert selftest.EXPECTED == {
        "gold": "pass",
        "syntax": "compile",
        "invented": "invented",
        "wrong": "wrong",
        "edge": "edge",
    }


# MARK: - the gate itself, which compiles and runs the fixture -


def has_avx512() -> bool:
    try:
        return "avx512f" in Path("/proc/cpuinfo").read_text()
    except OSError:  # pragma: no cover - not a Linux box
        return False


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_the_gate_gives_every_mutant_its_class(tmp_path):
    cells = [c for c in GATE_CELLS if has_avx512() or not c.startswith("avx512/")]
    report = selftest.selftest(FIXTURE, tmp_path, cells=cells, allow_host=True)
    mismatched = [(r["cell"], r["mutant"], r["expected"], r["got"], r["reason"]) for r in report["mismatches"]]
    assert mismatched == []
    assert report["ok"] is True
    assert len(report["rows"]) == len(cells) * 5


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_the_invented_mutants_name_lands_in_the_intrinsic_bucket(tmp_path):
    report = selftest.selftest(FIXTURE, tmp_path, cells=["avx2/int8/dot"], allow_host=True)
    row = next(r for r in report["rows"] if r["mutant"] == "invented")
    assert row["buckets"] == ["intrinsic"]


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_the_report_carries_the_margin_the_tolerance_table_is_running_on(tmp_path):
    report = selftest.selftest(FIXTURE, tmp_path, cells=["avx2/int8/l2_squared", "avx2/float32/dot"], allow_host=True)
    worst = report["worst_relative_error"]
    assert set(worst) == {"int8/l2_squared", "float32/dot"}
    for key, error in worst.items():
        rtol = report["tolerance"][key][0]
        assert error < rtol, (key, error, rtol)
    assert selftest.render(report).startswith("self-test over 2 cell(s) — ok")


# MARK: - what the target disagrees with itself on -


@pytest.mark.skipif(shutil.which("clang") is None, reason="G-compile needs clang; the image has it")
def test_the_fixture_has_no_disagreement_and_the_report_says_so(tmp_path):
    # float32, int8 and bit1: the fixture's SIMD kernels agree with its scalar kernel on every case. The
    # target's f16 and bf16 rows are where they do not, and those rows are trimmed out of the fixture.
    cells = [c for c in GATE_CELLS if has_avx512() or not c.startswith("avx512/")]
    report = selftest.selftest(FIXTURE, tmp_path, cells=cells, allow_host=True)
    assert report["disagreements"] == []
    assert report["ok"] is True
    assert "0 disagreement(s)" in selftest.render(report)


def test_a_disagreement_is_reported_with_both_values_and_is_not_a_mismatch():
    report = selftest._report([], [], {"sse2": _reference("sse2"), "avx2": _reference("avx2")})
    assert report["ok"] is True  # the target's fact, never the self-test's failure
    assert report["mismatches"] == []
    assert [(row["isa"], row["slot"], row["case"]) for row in report["disagreements"]] == [
        ("avx2", "DOT:BF16", "edge/large/n17"),
        ("sse2", "DOT:BF16", "edge/large/n17"),
    ]
    assert report["disagreements"][0]["scalar"] == "-inf"
    assert report["disagreements"][0]["gold"] == "nan"


def test_the_table_names_the_count_and_the_first_case_per_slot():
    report = selftest._report([], [], {"avx2": _reference("avx2")})
    printed = selftest.render(report)
    assert "disagree on 1 case(s) — the target's, not the graders'" in printed
    assert "avx2    DOT:BF16" in printed
    assert "edge/large/n17: scalar -inf, gold nan" in printed
    assert "graded against the scalar" not in printed  # this one is the rule's, not the tolerance's


def _reference(isa: str):
    """One ISA's gold reference carrying the bf16 `dot` overflow the real target shows on `large`."""
    gold = "nan" if isa in ("avx2", "avx512") else "inf"  # +inf on sse2, NaN on the other two
    return grade.GoldReference(
        isa=isa,
        available=True,
        slots=(("DOT", "BF16"),),
        got={("DOT:BF16", "edge/large/n17"): gold},
        disagreements=(
            {
                "isa": isa,
                "slot": "DOT:BF16",
                "case": "edge/large/n17",
                "kind": "edge",
                "n": 17,
                "seed": 200,
                "scalar": "-inf",
                "gold": gold,
                "reference": "gold",
            },
        ),
    )
