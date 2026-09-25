"""G-diff: the tolerance comparison, the case list, and what the generated driver carries."""

import math

import pytest

from lattice import diff


# MARK: - the comparison -


def test_both_nan_is_equal_and_one_nan_is_not():
    assert diff.compare("nan", "nan", 0.0, 0.0)
    assert not diff.compare("nan", 1.0, 1e-3, 1e-3)
    assert not diff.compare(1.0, "nan", 1e-3, 1e-3)


def test_the_same_infinity_is_equal_and_the_other_one_is_not():
    assert diff.compare("inf", "inf", 0.0, 0.0)
    assert diff.compare("-inf", "-inf", 0.0, 0.0)
    assert not diff.compare("inf", "-inf", 1.0, 1.0)
    assert not diff.compare("inf", 1e30, 1.0, 1.0)
    assert not diff.compare(1e30, "inf", 1.0, 1.0)
    assert not diff.compare("inf", "nan", 1.0, 1.0)


def test_rtol_is_relative_to_the_reference():
    assert diff.compare(1000.0, 1000.1, 1e-3, 0.0)
    assert not diff.compare(1000.0, 1002.0, 1e-3, 0.0)
    assert diff.compare(-1000.0, -1000.1, 1e-3, 0.0)  # |ref|, not ref


def test_atol_is_what_carries_a_reference_of_zero():
    assert not diff.compare(0.0, 1e-6, 1e-3, 0.0)
    assert diff.compare(0.0, 1e-6, 0.0, 1e-5)


def test_a_driver_number_is_a_json_number_or_a_spelled_out_one():
    assert diff.number(1.5) == 1.5
    assert diff.number("inf") == math.inf
    assert diff.number("-inf") == -math.inf
    assert math.isnan(diff.number("nan"))


def test_the_relative_error_is_absolute_when_the_reference_is_zero():
    assert diff.relative_error(100.0, 101.0) == pytest.approx(0.01)
    assert diff.relative_error(0.0, 0.25) == pytest.approx(0.25)
    assert diff.relative_error("inf", "inf") == 0.0
    assert diff.relative_error("inf", 1.0) == math.inf


# MARK: - the tolerance table -


def test_the_tolerance_is_data_per_type_and_metric():
    assert diff.tolerance("float32", "l2") == (1e-4, 1e-5)
    assert diff.tolerance("bit1", "hamming") == (0.0, 0.0)
    assert diff.tolerance("int8", "dot") == (1e-6, 0.0)
    assert diff.tolerance("int8", "cosine") == (1e-4, 0.0)


def test_the_widened_row_is_the_one_the_gold_needed():
    # `int8_distance_l2_impl_cpu` accumulates in float32 and the SIMD kernels in int32: the reference is
    # the imprecise side. Worst observed on the fixture's golds: 1.06e-6 squared, 5.09e-7 with the sqrt.
    assert diff.tolerance("int8", "l2_squared") == (1e-5, 0.0)
    assert diff.tolerance("int8", "l2") == (1e-5, 0.0)


def test_uint8_carries_the_same_widening_the_real_target_measured():
    # The real target's 93-cell self-test: `l2_squared` 1.05e-6 at bulk/n4096/s4 and `dot` 1.45e-6 at
    # bulk/n4096/s7, on sse2, avx2 and avx512 alike — the scalar's `float` accumulator again. `l1` stays
    # at the floor, and `cosine` where the float division put it.
    assert diff.tolerance("uint8", "l2") == (1e-5, 0.0)
    assert diff.tolerance("uint8", "l2_squared") == (1e-5, 0.0)
    assert diff.tolerance("uint8", "dot") == (1e-5, 0.0)
    assert diff.tolerance("uint8", "l1") == (1e-6, 0.0)
    assert diff.tolerance("uint8", "cosine") == (1e-4, 0.0)


def test_every_slot_a_kernel_file_installs_has_a_row():
    for type_ in ("float32", "float16", "bfloat16", "uint8", "int8"):
        for metric in ("l2", "l2_squared", "l1", "dot", "cosine"):
            assert (type_, metric) in diff.TOLERANCE, (type_, metric)
    assert ("bit1", "hamming") in diff.TOLERANCE


def test_an_unknown_pair_still_gets_graded():
    assert diff.tolerance("float32", "jaccard") == diff.FALLBACK


# MARK: - the cases -


def test_the_bulk_grid_is_four_sizes_by_eight_seeds():
    bulk = [c for c in diff.cases_for("float32") if c.kind == "bulk"]
    assert len(bulk) == 32
    assert {c.n for c in bulk} == set(diff.BULK_NS)
    assert {c.seed for c in bulk} == set(diff.BULK_SEEDS)


def test_every_bulk_size_is_a_multiple_of_sixty_four():
    # the self-test's `edge` mutant is built on this: it answers on the bulk grid and fails off it.
    assert all(n % 64 == 0 for n in diff.BULK_NS)


def test_the_edge_sizes_are_the_tails_and_the_boundaries():
    assert diff.EDGE_NS == (0, 1, 2, 3, 5, 7, 9, 15, 17, 31, 33, 63, 65, 127, 129)


def test_the_specials_go_to_the_types_they_mean_anything_for():
    names = lambda t: {c.name for c in diff.cases_for(t) if c.kind == "edge"}
    assert "edge/inf_a/n17" in names("float32")
    assert "edge/inf_a/n17" not in names("int8")
    assert "edge/extremes_lo_hi/n64" in names("int8")
    assert "edge/extremes_lo_hi/n64" not in names("float32")
    assert "edge/bit_zero_vs_ones/n17" in names("bit1")
    assert "edge/zeros_a/n64" in names("int8")  # cosine of a zero vector is a question for ints too


def test_each_type_gets_the_cases_its_row_is_graded_on():
    assert len(diff.cases_for("float32")) == 32 + 15 + 6 * 2
    assert len(diff.cases_for("int8")) == 32 + 15 + 3 * 2
    assert len(diff.cases_for("bit1")) == 32 + 15 + 1 * 2


def test_a_case_name_is_unique_within_a_type():
    for type_ in ("float32", "int8", "bit1"):
        names = [c.name for c in diff.cases_for(type_)]
        assert len(names) == len(set(names)), type_


# MARK: - the driver -


def test_the_driver_reaches_the_kernels_through_the_table_and_not_by_name():
    source = diff.driver_source()
    assert "init_distance_functions(true)" in source
    assert "memcpy(reference, dispatch_distance_table, sizeof(reference))" in source
    assert "got_fn != ref_fn" in source  # a slot still equal to the reference was not installed
    for isa in ("sse2", "avx2", "avx512", "neon", "rvv"):
        assert f"init_distance_functions_{isa}()" in source
    # never by name: no kernel symbol is written into the driver.
    assert "float32_distance_l2_avx2" not in source


def test_the_driver_carries_every_case_and_spells_inf_and_nan():
    source = diff.driver_source()
    for case in diff.CASES:
        assert f'"{case.name}"' in source, case.name
    # printed as JSON strings, because JSON has no literal for either
    assert r'printf("\"nan\"")' in source
    assert r'printf(v > 0.0f ? "\"inf\"" : "\"-inf\"")' in source
    assert "%.9g" in source


def test_the_driver_seeds_a_splitmix_and_nothing_else():
    source = diff.driver_source()
    assert "0x9E3779B97F4A7C15ull" in source
    assert "rand()" not in source and "time(" not in source


def test_a_slot_is_spelled_the_way_the_driver_reads_it():
    assert diff.slot_name(("SQUARED_L2", "I8")) == "SQUARED_L2:I8"
    assert diff.slot_name(["HAMMING", "BIT"]) == "HAMMING:BIT"


def test_a_slot_reads_back_as_a_type_and_a_metric():
    assert diff.pair_of_slot("SQUARED_L2:I8") == ("int8", "l2_squared")
    assert diff.pair_of_slot("HAMMING:BIT") == ("bit1", "hamming")
    assert diff.pair_of_slot("JACCARD:F32") == ("float32", "JACCARD")  # unknown, and still a pair


# MARK: - which reference a case is graded against -


def test_the_non_finite_flag_marks_exactly_the_four_that_write_an_inf_or_a_nan():
    flagged = {s.name for s in diff.SPECIALS if s.non_finite}
    assert flagged == {"inf_a", "inf_both_same", "inf_both_opposite", "nan"}
    assert diff.NON_FINITE_SPECIALS == flagged
    # `large` writes finite values; the overflow is the arithmetic's, and the scalar's answer catches it.
    assert not next(s for s in diff.SPECIALS if s.name == "large").non_finite


def test_a_case_whose_inputs_hold_a_non_finite_value_goes_to_the_gold():
    for special in ("inf_a", "inf_both_same", "inf_both_opposite", "nan"):
        for n in diff.SPECIAL_NS:
            # whatever the scalar answered, finite or not: the inputs alone decide.
            assert diff.reference_for(f"edge/{special}/n{n}", 1.5) == "gold", (special, n)
            assert diff.reference_for(f"edge/{special}/n{n}", "nan") == "gold", (special, n)


def test_a_finite_case_whose_scalar_answer_is_not_finite_goes_to_the_gold():
    assert diff.reference_for("edge/large/n17", "inf") == "gold"
    assert diff.reference_for("edge/large/n64", "-inf") == "gold"
    assert diff.reference_for("edge/zeros_a/n64", "nan") == "gold"  # a zero vector's cosine
    assert diff.reference_for("bulk/n4096/s0", "inf") == "gold"


def test_every_other_case_goes_to_the_scalar():
    assert diff.reference_for("bulk/n4096/s0", 45930488.0) == "scalar"
    assert diff.reference_for("edge/n0", 0.0) == "scalar"
    assert diff.reference_for("edge/large/n17", 1e30) == "scalar"
    assert diff.reference_for("edge/zeros_a/n64", 0.0) == "scalar"
    assert diff.reference_for("edge/extremes_lo_hi/n64", -1.0) == "scalar"
    assert diff.reference_for("edge/bit_zero_vs_ones/n17", 17.0) == "scalar"


def test_the_flag_lives_on_the_case_table_and_not_in_the_comparison():
    # every case name resolves to its pattern, so a record carrying only the name is enough.
    assert diff.SPECIAL_OF_CASE["edge/inf_a/n17"] == "inf_a"
    assert diff.SPECIAL_OF_CASE["bulk/n64/s0"] == ""
    assert set(diff.SPECIAL_OF_CASE) == {case.name for case in diff.CASES}


# MARK: - the comparison against the two references -

SLOT = ("COSINE", "BF16")
NAME = "COSINE:BF16"


def record(case: str, ref, got, *, kind: str = "edge", n: int = 17, seed: int = 200) -> dict:
    return {"slot": NAME, "case": case, "kind": kind, "n": n, "seed": seed, "ref": ref, "got": got}


def installed(*records: dict) -> list[dict]:
    return [{"slot": NAME, "installed": True}, *records]


def test_without_a_gold_mapping_every_case_is_graded_against_the_scalar():
    # which is how the gold reference is itself produced: its failures are the target's disagreements.
    records = installed(record("edge/inf_a/n17", "nan", 1.0), record("bulk/n64/s0", 1.0, 1.0, kind="bulk"))
    got = diff.compare_records(records, [SLOT])[0]
    assert (got.scalar_cases, got.gold_cases) == (2, 0)
    assert got.edge_failed == 1
    assert got.first_failure["reference"] == "scalar"
    assert got.first_failure["expected"] == "nan"


def test_a_body_that_matches_the_scalar_and_not_the_gold_fails_that_case():
    # bf16 cosine on an inf input: the scalar says nan and every SIMD kernel says 1. A body that says nan
    # is not doing what the kernel it replaces does, whatever `distance-cpu.c` says.
    records = installed(record("edge/inf_a/n17", "nan", "nan"))
    got = diff.compare_records(records, [SLOT], {(NAME, "edge/inf_a/n17"): 1.0})[0]
    assert (got.edge_passed, got.edge_failed) == (0, 1)
    assert (got.scalar_cases, got.gold_cases) == (0, 1)
    assert got.first_failure["reference"] == "gold"
    assert got.first_failure["expected"] == 1.0
    assert got.first_failure["got"] == "nan"
    assert got.first_failure["scalar"] == "nan"  # both values, so a reader can see the disagreement


def test_a_body_that_matches_the_gold_passes_the_case_the_scalar_would_have_failed():
    records = installed(record("edge/inf_a/n17", "nan", 1.0))
    got = diff.compare_records(records, [SLOT], {(NAME, "edge/inf_a/n17"): 1.0})[0]
    assert (got.edge_passed, got.edge_failed) == (1, 0)
    assert got.first_failure is None
    assert got.gold_cases == 1


def test_the_gold_comparison_is_the_same_comparison():
    # both NaN equal, the same infinity equal, otherwise the slot's tolerance.
    gold = {
        (NAME, "edge/nan/n17"): "nan",
        (NAME, "edge/inf_a/n17"): "inf",
        (NAME, "edge/inf_a/n64"): "inf",
        (NAME, "edge/large/n17"): 1000.0,
    }
    records = installed(
        record("edge/nan/n17", 0.5, "nan"),
        record("edge/inf_a/n17", 0.5, "inf"),
        record("edge/inf_a/n64", 0.5, "-inf", n=64),
        record("edge/large/n17", "inf", 1000.01),
    )
    got = diff.compare_records(records, [SLOT], gold)[0]
    assert got.gold_cases == 4
    assert (got.edge_passed, got.edge_failed) == (3, 1)  # the opposite infinity is the one that fails
    assert got.first_failure["case"] == "edge/inf_a/n64"


def test_a_gold_referenced_case_the_gold_has_no_answer_for_is_failed_and_never_passed():
    records = installed(record("edge/nan/n17", "nan", "nan"))
    got = diff.compare_records(records, [SLOT], {})[0]
    assert (got.edge_passed, got.edge_failed) == (0, 1)
    assert got.first_failure["reference"] == "gold"
    assert got.first_failure["expected"] is None


def test_the_counts_say_which_reference_graded_how_many():
    records = installed(
        record("bulk/n64/s0", 1.0, 1.0, kind="bulk", n=64, seed=0),
        record("bulk/n256/s0", "inf", "inf", kind="bulk", n=256, seed=0),
        record("edge/inf_a/n17", "nan", 1.0),
        record("edge/nan/n17", "nan", 1.0),
    )
    gold = {(NAME, "bulk/n256/s0"): "inf", (NAME, "edge/inf_a/n17"): 1.0, (NAME, "edge/nan/n17"): 1.0}
    got = diff.compare_records(records, [SLOT], gold)[0]
    assert (got.scalar_cases, got.gold_cases) == (1, 3)
    assert (got.bulk_passed, got.bulk_failed, got.edge_passed, got.edge_failed) == (2, 0, 2, 0)


def test_a_slot_the_init_never_installed_is_still_not_graded():
    got = diff.compare_records([{"slot": NAME, "installed": False}], [SLOT], {})[0]
    assert got.installed is False
    assert (got.scalar_cases, got.gold_cases) == (0, 0)
