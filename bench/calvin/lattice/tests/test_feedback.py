"""The retry text: what it says, what it leaves out, and the ceiling it stays under."""

from lattice import feedback


def compiled_result(**over) -> dict:
    result = {
        "class": "invented",
        "reason": "the file did not compile",
        "diagnostics": [
            {"file": "src/distance-avx2.c", "line": 130, "col": 19, "severity": "error",
             "message": "call to undeclared function '_mm256_lattice_ps'"},
            {"file": "src/distance-avx2.c", "line": 131, "col": 5, "severity": "warning",
             "message": "unused variable 'acc0' [-Wunused-variable]"},
        ],
        "link_errors": [],
        "invented": [{"name": "_mm256_lattice_ps", "bucket": "intrinsic"}],
        "bulk": {"passed": 0, "failed": 0},
        "edge": {"passed": 0, "failed": 0},
        "first_failure": None,
    }
    return {**result, **over}


def failing_result(**over) -> dict:
    result = {
        "class": "wrong",
        "reason": None,
        "diagnostics": [],
        "link_errors": [],
        "invented": [],
        "bulk": {"passed": 30, "failed": 2},
        "edge": {"passed": 27, "failed": 0},
        "first_failure": {
            "slot": "DOT:F32", "case": "bulk/n256/s3", "kind": "bulk", "n": 256, "seed": 3,
            "expected": -12.5, "got": 3.25,
        },
    }
    return {**result, **over}


def test_a_pass_is_told_nothing():
    assert feedback.build({"class": "pass", "diagnostics": [], "invented": []}) == ""


def test_the_errors_come_back_and_the_warnings_do_not():
    text = feedback.build(compiled_result())
    assert "It did not compile." in text
    assert "src/distance-avx2.c:130:19: error: call to undeclared function '_mm256_lattice_ps'" in text
    assert "unused variable" not in text


def test_an_invented_name_is_named_with_its_bucket():
    assert "_mm256_lattice_ps (intrinsic)" in feedback.build(compiled_result())


def test_the_first_failing_case_is_the_whole_story_when_it_compiled():
    text = feedback.build(failing_result())
    assert "bulk/n256/s3" in text
    assert "n = 256" in text and "seed 3" in text
    assert "-12.5" in text and "3.25" in text
    assert "2 of 32 bulk cases and 0 of 27 edge cases fail" in text


def test_a_scalar_referenced_case_says_it_was_the_scalar():
    text = feedback.build(failing_result(first_failure={
        "slot": "DOT:F32", "case": "bulk/n256/s3", "kind": "bulk", "n": 256, "seed": 3,
        "expected": -12.5, "got": 3.25, "reference": "scalar",
    }))
    assert "disagrees with the scalar reference" in text


def test_a_gold_referenced_case_names_the_kernel_it_replaces_and_not_the_scalar():
    text = feedback.build(failing_result(first_failure={
        "slot": "COSINE:BF16", "case": "edge/n17/inf_a", "kind": "edge", "n": 17, "seed": 0,
        "expected": "nan", "got": 1.0, "reference": "gold",
    }))
    assert "disagrees with the kernel it replaces (the target's own gold; a non-finite case)" in text
    assert "scalar" not in text


def test_a_failure_with_no_reference_field_keeps_the_old_wording():
    text = feedback.build(failing_result())  # no `reference`: a result from before the field existed
    assert "disagrees with the scalar reference" in text


def test_a_slot_that_was_never_installed_says_so():
    text = feedback.build({
        "class": "not-installed", "reason": "the init left DOT:F32 pointing at the scalar table",
        "diagnostics": [], "link_errors": [], "invented": [], "first_failure": None,
    })
    assert text == "the init left DOT:F32 pointing at the scalar table"


def test_a_link_failure_carries_the_linkers_own_line():
    text = feedback.build(compiled_result(
        diagnostics=[],
        link_errors=["/usr/bin/ld: distance-avx2.o: undefined reference to `hsum256_missing'"],
        invented=[{"name": "hsum256_missing", "bucket": "other"}],
    ))
    assert "undefined reference to `hsum256_missing'" in text
    assert "hsum256_missing (other)" in text


def test_a_result_the_graders_said_nothing_about_still_says_something():
    text = feedback.build({"class": "wrong", "diagnostics": [], "invented": [], "first_failure": None})
    assert text


def test_it_stays_under_the_ceiling():
    many = [
        {"file": f"src/distance-avx2.c", "line": i, "col": 1, "severity": "error", "message": "x" * 400}
        for i in range(40)
    ]
    text = feedback.build(compiled_result(diagnostics=many))
    assert len(text) <= feedback.LIMIT
    assert text.endswith("…")


def test_only_the_first_errors_are_carried_and_the_rest_are_counted():
    many = [
        {"file": "src/distance-avx2.c", "line": i, "col": 1, "severity": "error", "message": f"error {i}"}
        for i in range(12)
    ]
    text = feedback.build(compiled_result(diagnostics=many))
    assert "error 7" in text and "error 8" not in text
    assert "(4 more errors.)" in text
