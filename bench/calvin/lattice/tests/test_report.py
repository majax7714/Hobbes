"""E1's and E4's readings, against hand-computed values on a hand-written run directory.

Nothing here runs the runner: the point of `report` is that it reads rows and computes nothing a row does
not hold, so the rows are written by hand and every figure below is worked out on paper beside it. The E4
block at the end is the same discipline over an E4 run's files — its rows, its requests and its
`file_level.jsonl` — and the two figures it exists for are **S-5 − S-3**, now a number, and S-2o's
own-shot counts, which are read off the requests because no row holds what a prompt carried.
"""

import json
import math
from pathlib import Path

import pytest

from lattice import e1, e4, report

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


# MARK: - E4's readings: the second comparison, and S-2o beside it -

#: Three units of one held-out file: two cells and one non-cell helper.
U1, U2, H = "float32_distance_dot_avx2", "int8_distance_dot_avx2", "hsum256_ps"


def e4_row(unit, arm, cls, *, kind="cell"):
    """One E4 row. A unit stands where a cell does, which is what `cell` holds (`e4.plan`'s own key)."""
    return {
        "id": e1.request_id(unit, arm, 0, 0),
        "cell": unit,
        "name": unit,
        "kind": kind,
        "isa": "avx2",
        "type": "float32" if unit == U1 else "int8",
        "metric": "dot",
        "arm": arm,
        "sample": 0,
        "round": 0,
        "class": cls,
        "reg": True,
        "invented": [],
    }


def e4_request(unit, arm, sample, *, kind="cell", own=(), notes=(), wave=0):
    """One request, carrying what its arm gave it — which is where the own-shot counts are read from."""
    return {
        "id": e1.request_id(unit, arm, sample, 0),
        "cell": unit,
        "unit": unit,
        "name": unit,
        "kind": kind,
        "arm": arm,
        "sample": sample,
        "round": 0,
        "wave": wave,
        "mode": "chat",
        "messages": [{"role": "user", "content": "…"}],
        "own": [dict(row) for row in own],
        "own_notes": [dict(note) for note in notes],
        "params": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "seed": 1},
    }


@pytest.fixture
def e4_run_dir(tmp_path):
    """An E4 run over three units and three arms, `k = 0`: greedy only, so pass@1 is the figure."""
    made = tmp_path / "e4run"
    made.mkdir()
    (made / e1.META).write_text(
        json.dumps(
            {
                "model": "Qwen/Qwen2.5-Coder-7B-Instruct",
                "k": 0,
                "params": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 2048},
                "rounds": 0,
                "iterate": [],
                "arms": ["S-2o", "S-3", "S-5"],
                "cells": [U1, U2, H],
                "units": [{"name": U1}, {"name": U2}, {"name": H}],
                "rung": "L1",
                "isa": "avx2",
                "file": "src/distance-avx2.c",
                "waves": [[U1, H], [U2]],
                "parser": {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "models": ["Qwen/Qwen2.5-7B-Instruct"],
                    "sha256": "abcdef0123456789" * 4,
                    "units": 3,
                    "parsed": 2,
                },
                "p12": "decomposed",
                "decomposition": {
                    "unit_count": 3,
                    "largest_prompt_chars": 900,
                    "file_chars": 20357,
                    "every_window_smaller": True,
                },
            }
        ),
        encoding="utf-8",
    )
    # S-5 gains the one unit S-3 did not get: one cell moved, so the paired delta is 1 of 3 and p is 1.0
    _write(
        made / e1.ROWS,
        [
            e4_row(U1, "S-3", "pass"),
            e4_row(U2, "S-3", "wrong"),
            e4_row(H, "S-3", "pass", kind="helper"),
            e4_row(U1, "S-5", "pass"),
            e4_row(U2, "S-5", "pass"),
            e4_row(H, "S-5", "pass", kind="helper"),
            e4_row(U1, "S-2o", "pass"),
            e4_row(U2, "S-2o", "wrong"),
            e4_row(H, "S-2o", "pass", kind="helper"),
        ],
    )
    _write(
        made / e1.REQUESTS,
        [
            e4_request(
                U1, "S-2o", 0,
                notes=(
                    {"axis": "type", "unit": None, "reason": e4.NO_NEIGHBOUR},
                    {"axis": "metric", "unit": U2, "reason": e4.LATER},
                ),
            ),
            e4_request(
                U2, "S-2o", 0, wave=1,
                own=({"axis": "type", "unit": U1},),
                notes=({"axis": "metric", "unit": H, "reason": e4.NEIGHBOUR_FAILED},),
            ),
            # a drawn sample of the same unit: its shots are the unit's, so it is not counted twice
            e4_request(U2, "S-2o", 1, wave=1, own=({"axis": "type", "unit": U1},)),
            e4_request(H, "S-2o", 0, kind="helper", notes=({"axis": None, "unit": None, "reason": "helper"},)),
            e4_request(U1, "S-3", 0),
        ],
    )
    _write(
        made / e4.FILE_LEVEL,
        [{"arm": "S-5", "isa": "avx2", "file": "src/distance-avx2.c", "units": 3, "units_passed": 3,
          "unit_names": [H, U1, U2], "class": "pass", "diff_pass": True, "reg": True, "written": "final/S-5/distance-avx2.c"}],
    )
    _write(made / e1.CALLS, [{"round": 0, "requests": 9, "cost": 0.1, "cost_source": "reported", "seconds": 3.0}])
    return made


def test_s5_minus_s3_is_a_number_paired_by_unit(e4_run_dir):
    found = report.e4_report(e4_run_dir)
    assert found["missing"] == []
    tests = found["comparisons"]["S-5 − S-3"]
    # of the three units, one moved and it moved the way S-5 is the escalation of: gained 1, lost 0
    assert tests["pass_at_1"] == {
        "cells": 3, "both": 2, "neither": 0, "lost": 0, "gained": 1,
        "delta": round(1 / 3, 6), "p": 1.0,
    }
    assert tests["unpaired"] == 0
    # S-2 − S-0 has no rows in this run, and says so rather than reading as zero
    assert found["comparisons"]["S-2 − S-0"] == {"missing": "the run has no rows for S-0"}

    table = report.e4_render(found)
    assert "S-5 − S-3  (unpaired 0)" in table
    assert "pass_at_1           +0.333  lost   0  gained   1  of   3" in table


#: D-11's comparison, as the report labels the two readings of it.
HELPERS = "S-2h − S-2 (helper units, registered)"
CELLS = "S-2h − S-2 (cell units, described: identical prompts under two seeds)"


def test_the_helper_comparison_reads_registered_and_the_cell_one_described(e4_run_dir):
    """D-11 a: `S-2h − S-2` is the helper units, and the same pair over the cells is the noise read.

    Written as the run fills up, because the third reading is "no number yet": a comparison whose arms a
    run has no rows for says which arm, and `missing` is not a zero.
    """
    found = report.e4_report(e4_run_dir)
    assert found["comparisons"][HELPERS] == {"missing": "the run has no helper unit rows for S-2"}
    assert found["comparisons"][CELLS] == {"missing": "the run has no cell unit rows for S-2"}

    # S-2 alone: the reading still has no second arm, and says so of that one
    with (e4_run_dir / e1.ROWS).open("a", encoding="utf-8") as handle:
        for line in (
            e4_row(U1, "S-2", "pass"),
            e4_row(U2, "S-2", "wrong"),
            e4_row(H, "S-2", "wrong", kind="helper"),
        ):
            handle.write(f"{json.dumps(line, sort_keys=True)}\n")
    assert report.e4_report(e4_run_dir)["comparisons"][HELPERS] == {
        "missing": "the run has no helper unit rows for S-2h"
    }

    # and with S-2h the helper moves, while the two cells — which were sent S-2's own bytes — do not
    with (e4_run_dir / e1.ROWS).open("a", encoding="utf-8") as handle:
        for line in (
            e4_row(U1, "S-2h", "pass"),
            e4_row(U2, "S-2h", "wrong"),
            e4_row(H, "S-2h", "pass", kind="helper"),
        ):
            handle.write(f"{json.dumps(line, sort_keys=True)}\n")
    found = report.e4_report(e4_run_dir)
    assert found["comparisons"][HELPERS]["pass_at_1"] == {
        "cells": 1, "both": 0, "neither": 0, "lost": 0, "gained": 1, "delta": 1.0, "p": 1.0,
    }
    assert found["comparisons"][CELLS]["pass_at_1"] == {
        "cells": 2, "both": 1, "neither": 1, "lost": 0, "gained": 0, "delta": 0.0, "p": 1.0,
    }
    # the helper reading is over the helper units only: the cells are in the other line and nowhere else
    assert found["comparisons"][HELPERS]["unpaired"] == 0

    table = report.e4_render(found)
    assert "each line says which units it is over and whether it was registered" in table
    assert f"    {HELPERS}  (unpaired 0)" in table
    assert f"    {CELLS}  (unpaired 0)" in table


def test_s3h_minus_s2h_is_registered_over_every_unit(e4_run_dir):
    """D-12 a: the block is stated for every unit that carries a shot, so the pair is read over all of them."""
    assert report.e4_report(e4_run_dir)["comparisons"]["S-3h − S-2h"] == {
        "missing": "the run has no rows for S-2h"
    }
    with (e4_run_dir / e1.ROWS).open("a", encoding="utf-8") as handle:
        for line in (
            e4_row(U1, "S-2h", "wrong"),
            e4_row(U2, "S-2h", "wrong"),
            e4_row(H, "S-2h", "wrong", kind="helper"),
            e4_row(U1, "S-3h", "pass"),
            e4_row(U2, "S-3h", "wrong"),
            e4_row(H, "S-3h", "pass", kind="helper"),
        ):
            handle.write(f"{json.dumps(line, sort_keys=True)}\n")

    found = report.e4_report(e4_run_dir)
    tests = found["comparisons"]["S-3h − S-2h"]
    # one cell and one helper moved, and both are in the one reading: the pair is registered on no kind
    assert tests["pass_at_1"] == {
        "cells": 3, "both": 0, "neither": 1, "lost": 0, "gained": 2,
        "delta": round(2 / 3, 6), "p": 0.5,
    }
    assert tests["unpaired"] == 0
    # printed once, and as registered: a comparison over every unit has no described second printing
    assert [label for label in found["comparisons"] if "S-3h" in label] == ["S-3h − S-2h"]
    assert "    S-3h − S-2h  (unpaired 0)" in report.e4_render(found)


def test_s2o_is_shown_with_its_own_shot_counts_and_why_each_missing_one_was_missing(e4_run_dir):
    own = report.e4_report(e4_run_dir)["own_shots"]
    # the greedy requests only: three units, two of them cells
    assert own == {
        "units": 3,
        "cells": 2,
        "carried": {"0": 1, "1": 1, "2": 0},
        "missing": {"helper": 1, "later-in-order": 1, "neighbour-failed": 1, "no-neighbour": 1},
    }

    table = report.e4_render(report.e4_report(e4_run_dir))
    assert "S-2o, described and not tested" in table and "over 2 cell(s) in 2 wave(s)" in table
    assert "cells carrying 1 own shot(s): 1" in table
    assert "no own shot, by reason: helper 1, later-in-order 1, neighbour-failed 1, no-neighbour 1" in table
    # described, not tested: it is in no registered comparison
    assert all("S-2o" not in label for label in report.e4_report(e4_run_dir)["comparisons"])


def test_the_e4_table_names_the_parser_and_the_window(e4_run_dir):
    table = report.e4_render(report.e4_report(e4_run_dir))
    assert "parser: 2 of 3 unit(s) parsed by Qwen/Qwen2.5-7B-Instruct (abcdef012345)" in table
    assert "largest prompt 900 chars against the file's 20357 (every window smaller)" in table
    assert "file level (greedy bodies where the unit passed, gold elsewhere):" in table


def test_an_e4_run_with_no_requests_file_names_it_rather_than_reading_no_shots(tmp_path, e4_run_dir):
    (e4_run_dir / e1.REQUESTS).unlink()
    found = report.e4_report(e4_run_dir)
    assert found["missing"] == [e1.REQUESTS]
    assert found["own_shots"] is None
    assert found["comparisons"]["S-5 − S-3"]["pass_at_1"]["cells"] == 3  # the rows still read


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
