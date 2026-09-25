"""E1's readings, against hand-computed values on a hand-written run directory.

Nothing here runs the runner: the point of `report` is that it reads rows and computes nothing a row does
not hold, so the rows are written by hand and every figure below is worked out on paper beside it.
"""

import json
import math
from pathlib import Path

import pytest

from lattice import e1, report

#: The three cells the rows below are about: two real bodies and one wrapper, which is reported apart.
A = "avx2/float32/dot"
B = "avx2/int8/dot"
W = "avx2/float32/l2"

K = 2


def row(cell, arm, sample, round_, cls, *, kind="body", isa="avx2", type_="float32", reg=True, invented=()):
    return {
        "id": e1.request_id(cell, arm, sample, round_),
        "cell": cell,
        "name": "x",
        "kind": kind,
        "isa": isa,
        "type": type_,
        "metric": "dot",
        "arm": arm,
        "sample": sample,
        "round": round_,
        "class": cls,
        "reg": reg,
        "invented": list(invented),
    }


def body_rows():
    """Round 0: A passes greedy and one of two samples; B passes nothing; W (a wrapper) passes greedy."""
    invented = ({"name": "_mm256_nope_ps", "bucket": "intrinsic"}, {"name": "v1", "bucket": "param"})
    rows = [
        row(A, "C-0", 0, 0, "pass"),
        row(A, "C-0", 1, 0, "pass"),
        row(A, "C-0", 2, 0, "wrong"),
        row(B, "C-0", 0, 0, "wrong", type_="int8", reg=False, invented=invented),
        row(B, "C-0", 1, 0, "compile", type_="int8", reg=False, invented=invented),
        row(B, "C-0", 2, 0, "no-body", type_="int8", reg=None),
        row(W, "C-0", 0, 0, "pass", kind="wrapper"),
        row(W, "C-0", 1, 0, "wrong", kind="wrapper"),
        row(W, "C-0", 2, 0, "wrong", kind="wrapper"),
    ]
    # the iterate rounds: A's third chain passes at round 1, B's first at round 2, the rest never do
    rows += [
        row(A, "C-0", 2, 1, "pass"),
        row(B, "C-0", 0, 1, "wrong", type_="int8"),
        row(B, "C-0", 1, 1, "wrong", type_="int8"),
        row(B, "C-0", 2, 1, "wrong", type_="int8"),
        row(W, "C-0", 1, 1, "wrong", kind="wrapper"),
        row(W, "C-0", 2, 1, "wrong", kind="wrapper"),
        row(B, "C-0", 0, 2, "pass", type_="int8"),
        row(B, "C-0", 1, 2, "wrong", type_="int8"),
        row(B, "C-0", 2, 2, "wrong", type_="int8"),
        row(W, "C-0", 1, 2, "wrong", kind="wrapper"),
        row(W, "C-0", 2, 2, "wrong", kind="wrapper"),
    ]
    # C-2 is not an iterate arm: round 0 and nothing after it
    rows += [
        row(A, "C-2", 0, 0, "pass"),
        row(A, "C-2", 1, 0, "wrong"),
        row(A, "C-2", 2, 0, "wrong"),
    ]
    return rows


@pytest.fixture
def run_dir(tmp_path):
    made = tmp_path / "run"
    made.mkdir()
    (made / e1.META).write_text(
        json.dumps(
            {
                "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "k": K,
                "params": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 2048},
                "rounds": 3,
                "iterate": ["C-0"],
                "arms": ["C-0", "C-2"],
                "cells": [A, B, W],
                "p12": "arm=model+prompt",
                "target_sha": "0c2223a00000000000000000000000000000000f",
            }
        ),
        encoding="utf-8",
    )
    _write(made / e1.ROWS, body_rows())
    _write(
        made / e1.GMEM,
        [
            {"id": f"{A}|gmem", "cell": A, "score": 0.9, "label": "memorised", "evidence": True},
            {"id": f"{B}|gmem", "cell": B, "score": 0.02, "label": "unseen", "evidence": True},
            {"id": f"{W}|gmem", "cell": W, "score": 1.0, "label": "memorised", "evidence": False},
        ],
    )
    _write(
        made / e1.CALLS,
        [
            {"round": 0, "requests": 9, "tokens_in": 100, "tokens_out": 200, "seconds": 10.0, "cost": 0.5, "cost_source": "reported"},
            {"round": 1, "requests": 4, "tokens_in": 50, "tokens_out": 80, "seconds": 4.0, "cost": 0.25, "cost_source": "reported"},
        ],
    )
    return made


def _write(path, rows):
    path.write_text("".join(f"{json.dumps(item, sort_keys=True)}\n" for item in rows), encoding="utf-8")


# MARK: - the estimator -


def test_pass_at_k_is_the_unbiased_estimator_and_any_pass_at_n_equals_k():
    assert report.pass_at_k(5, 0, 5) == 0.0
    assert report.pass_at_k(5, 1, 5) == 1.0
    assert report.pass_at_k(5, 5, 5) == 1.0
    assert report.pass_at_k(10, 2, 5) == pytest.approx(1 - math.comb(8, 5) / math.comb(10, 5))


def test_pass_at_k_is_none_with_fewer_samples_than_the_figure_names():
    assert report.pass_at_k(3, 1, 5) is None
    assert report.pass_at_k(0, 0, 5) is None


# MARK: - the four figures -


def test_pass_at_one_is_greedy_and_pass_at_one_sampled_is_the_mean_over_the_draws(run_dir):
    overall = report.report(run_dir)["sections"]["bodies"]["arms"]["C-0"]["overall"]
    # greedy: A passes, B does not → 1 of 2 cells
    assert overall["pass_at_1"] == 0.5
    # sampled: A 1 of 2, B 0 of 2 → mean 0.25
    assert overall["pass_at_1_sampled"] == 0.25
    # pass@2: A has 1 of 2 → 1.0; B has 0 of 2 → 0.0; mean 0.5
    assert overall["pass_at_k"] == 0.5
    assert overall["pass_at_k_cells"] == 2
    assert overall["cells"] == 2 and overall["rows"] == 6


def test_the_class_counts_are_the_round_zero_rows_of_the_group(run_dir):
    overall = report.report(run_dir)["sections"]["bodies"]["arms"]["C-0"]["overall"]
    assert overall["classes"] == {"compile": 1, "no-body": 1, "pass": 2, "wrong": 2}


def test_every_figure_is_broken_down_by_isa_and_by_type(run_dir):
    arm = report.report(run_dir)["sections"]["bodies"]["arms"]["C-0"]
    assert list(arm["by_isa"]) == ["avx2"]
    assert arm["by_isa"]["avx2"]["pass_at_1"] == 0.5
    assert arm["by_type"]["float32"]["pass_at_1"] == 1.0
    assert arm["by_type"]["float32"]["pass_at_1_sampled"] == 0.5
    assert arm["by_type"]["float32"]["pass_at_k"] == 1.0
    assert arm["by_type"]["int8"]["pass_at_1"] == 0.0
    assert arm["by_type"]["int8"]["pass_at_k"] == 0.0


def test_the_low_bit_types_are_a_row_of_their_own_beside_their_own_rows(run_dir):
    arm = report.report(run_dir)["sections"]["bodies"]["arms"]["C-0"]
    assert "low-bit" in arm["by_type"] and "int8" in arm["by_type"]
    assert arm["by_type"]["low-bit"] == arm["by_type"]["int8"]  # int8 is the only low-bit type here
    assert report.LOW_BIT == ("int8", "uint8", "bit1")


def test_the_iterate_arms_rounds_are_cumulative_and_the_others_have_none(run_dir):
    arms = report.report(run_dir)["sections"]["bodies"]["arms"]
    assert [(entry["round"], entry["passed"], entry["chains"]) for entry in arms["C-0"]["rounds"]] == [
        (0, 2, 6),  # A greedy and A sample 1
        (1, 3, 6),  # A sample 2 comes in
        (2, 4, 6),  # B greedy comes in; the other two never pass
    ]
    assert arms["C-0"]["rounds"][2]["rate"] == pytest.approx(4 / 6)
    assert arms["C-0"]["rounds"][1]["classes"] == {"pass": 1, "wrong": 3}
    assert arms["C-2"]["rounds"] is None


# MARK: - what stands beside each figure -


def test_g_reg_is_read_over_the_bodies_that_compiled_and_over_no_others(run_dir):
    overall = report.report(run_dir)["sections"]["bodies"]["arms"]["C-0"]["overall"]
    # of the six round-0 rows, `compile` and `no-body` never built: four remain, three of them held
    assert overall["reg"] == {"compiled": 4, "held": 3, "rate": 0.75}


def test_the_invented_names_are_counted_by_bucket(run_dir):
    overall = report.report(run_dir)["sections"]["bodies"]["arms"]["C-0"]["overall"]
    assert overall["invented"] == {"intrinsic": {"_mm256_nope_ps": 2}, "param": {"v1": 2}}


def test_a_renamed_parameter_is_a_bucket_of_its_own_and_never_an_invented_intrinsic(run_dir):
    """`param` is `e1.PARAM`, the runner's fourth bucket: a name the model renamed, not an invented API."""
    found = report.report(run_dir)
    overall = found["sections"]["bodies"]["arms"]["C-0"]["overall"]
    assert e1.PARAM in overall["invented"]
    assert "v1" not in overall["invented"]["intrinsic"]
    assert sum(overall["invented"]["intrinsic"].values()) == 2  # the renames are on no other line

    text = report.render(found)
    assert "invented param: v1×2" in text
    assert "invented intrinsic: _mm256_nope_ps×2" in text


def test_a_probe_below_the_evidence_floor_counts_as_no_evidence_and_never_as_memorised(run_dir):
    """A wrapper's probe scores 1.0 on `}` alone. `gmem.has_evidence` marks it, and this reads the mark."""
    found = report.report(run_dir)
    assert found["gmem"]["labels"].get("memorised") == 1  # A's, and not the wrapper's
    assert found["gmem"]["labels"][report.NO_EVIDENCE] == 1
    assert list(found["sections"]["wrappers"]["arms"]["C-0"]["overall"]["gmem"]) == [report.NO_EVIDENCE]


def test_the_report_states_the_max_tokens_the_run_asked_at(run_dir):
    found = report.report(run_dir)
    assert found["max_tokens"] == 2048
    assert "max_tokens=2048" in report.render(found)
    # a run whose meta never recorded them says so rather than naming a number it did not read
    (run_dir / e1.META).write_text(json.dumps({"model": "M", "k": K}), encoding="utf-8")
    bare = report.report(run_dir)
    assert bare["max_tokens"] is None
    assert "max_tokens=?" in report.render(bare)


def test_the_pass_rates_are_split_by_the_cells_g_mem_label(run_dir):
    found = report.report(run_dir)
    split = found["sections"]["bodies"]["arms"]["C-0"]["overall"]["gmem"]
    assert split["memorised"] == {"cells": 1, "pass_at_1": 1.0, "pass_at_1_sampled": 0.5}
    assert split["unseen"] == {"cells": 1, "pass_at_1": 0.0, "pass_at_1_sampled": 0.0}
    # the wrapper's probe had nothing to continue, so it carries no label rather than reading `memorised`
    assert found["sections"]["wrappers"]["arms"]["C-0"]["overall"]["gmem"] == {
        report.NO_EVIDENCE: {"cells": 1, "pass_at_1": 1.0, "pass_at_1_sampled": 0.0}
    }
    assert found["gmem"]["labels"] == {"no-evidence": 1, "memorised": 1, "unseen": 1}


# MARK: - what is never pooled, and what is never assumed -


def test_wrappers_are_a_section_of_their_own_and_are_in_neither_of_the_others(run_dir):
    found = report.report(run_dir)
    wrappers = found["sections"]["wrappers"]["arms"]["C-0"]["overall"]
    assert (wrappers["cells"], wrappers["pass_at_1"], wrappers["pass_at_1_sampled"]) == (1, 1.0, 0.0)
    assert found["sections"]["bodies"]["cells"] == 2
    assert found["sections"]["wrappers"]["cells"] == 1
    # the two sections' rows add up to the rows on disk, and neither holds the other's
    assert found["sections"]["bodies"]["rows"] + found["sections"]["wrappers"]["rows"] == len(body_rows())


def test_the_totals_are_the_calls_own_and_not_re_derived(run_dir):
    totals = report.report(run_dir)["totals"]
    assert totals == {
        "calls": 2,
        "requests": 13,
        "tokens_in": 150,
        "tokens_out": 280,
        "seconds": 14.0,
        "cost": 0.75,
        "estimated": 0,
    }


def test_a_missing_file_is_named_rather_than_read_as_zero(tmp_path, run_dir):
    (run_dir / e1.GMEM).unlink()
    (run_dir / e1.CALLS).unlink()
    found = report.report(run_dir)
    assert found["missing"] == [e1.GMEM, e1.CALLS]
    assert found["gmem"] is None and found["totals"] is None
    # and the pass rates still read, with every cell's label simply unknown
    assert found["sections"]["bodies"]["arms"]["C-0"]["overall"]["pass_at_1"] == 0.5
    assert list(found["sections"]["bodies"]["arms"]["C-0"]["overall"]["gmem"]) == [report.NO_EVIDENCE]

    empty = tmp_path / "nothing"
    empty.mkdir()
    bare = report.report(empty)
    assert bare["missing"] == [e1.META, e1.ROWS, e1.GMEM, e1.CALLS]
    assert bare["sections"]["bodies"]["arms"] == {}


def test_a_figure_with_nothing_to_compute_it_from_is_none_and_never_zero(run_dir):
    assert report.figures([], K, {})["pass_at_1"] is None
    assert report.figures([], K, {})["pass_at_k"] is None
    assert report._number(None) == "-"
    assert report._number(0.0) == "0.00"


# MARK: - the table -


def test_the_table_names_both_sections_the_figures_and_the_spend(run_dir):
    text = report.render(report.report(run_dir))
    assert "bodies:" in text and "wrappers:" in text
    assert "pass@1" in text and "pass@k" in text
    assert "low-bit" in text
    assert "gmem memorised" in text
    assert "invented intrinsic: _mm256_nope_ps×2" in text
    assert "round 2: 4 of 6 chain(s) passed (0.67)" in text
    assert "$0.7500" in text
    assert "arm=model+prompt" in text
    assert str(Path(run_dir)) not in text  # the run's name, not this box's path
