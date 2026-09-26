"""E2's reading: an original run against its shadows, from two hand-written run directories.

Nothing here plans, answers or grades anything — a comparison is a reader over rows that already exist,
so the rows are written by hand and are the whole input. That is also why the runs are tiny: what is
under test is the delta, the flip and the refusal, not a pass rate.
"""

import json
from pathlib import Path

import pytest

from lattice import compare
from lattice.e1 import CALLS, GMEM, META, ROWS

MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
CELLS = ("avx2/float32/dot", "avx2/int8/dot")
PARAMS = {"temperature": 0.8, "top_p": 0.95, "max_tokens": 2048}


def write_run(run_dir, passes, *, k=1, cells=CELLS, model=MODEL, params=PARAMS, style=None, arms=("C-2", "C-3")):
    """One run directory: its `meta.json` and one greedy plus one drawn row per (cell, arm).

    *passes* maps `(arm, cell)` to whether the greedy sample passed; the drawn sample passes with it,
    so pass@1 and pass@k move together and a flip is visible in both.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "model": model,
        "params": params,
        "arms": list(arms),
        "cells": list(cells),
        "k": k,
        "rounds": 0,
        "iterate": [],
        "target_sha": None if style else "a" * 40,
        "ledger": None,
        "shadow": None if style is None else {"style": style, "map_sha256": "d" * 64, "tree_sha256": "t" * 64},
        "p12": "arm=model+prompt",
    }
    (run_dir / META).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    rows = []
    for arm in arms:
        for cell in cells:
            for sample in (0, 1):
                rows.append(
                    {
                        "id": f"{cell}|{arm}|{sample}|0",
                        "cell": cell,
                        "name": cell,
                        "kind": "body",
                        "isa": cell.split("/")[0],
                        "type": cell.split("/")[1],
                        "metric": cell.split("/")[2],
                        "arm": arm,
                        "sample": sample,
                        "round": 0,
                        "class": "pass" if passes.get((arm, cell)) else "wrong",
                        "invented": [],
                        "reg": True,
                    }
                )
    (run_dir / ROWS).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (run_dir / GMEM).write_text("", encoding="utf-8")
    (run_dir / CALLS).write_text(json.dumps({"round": 0, "requests": len(rows), "cost": 0.1}) + "\n", encoding="utf-8")
    return run_dir


@pytest.fixture
def runs(tmp_path):
    """The original passes both cells on C-2 and one on C-3; the shadow loses one and gains another."""
    original = write_run(
        tmp_path / "qwen-target",
        {("C-2", CELLS[0]): True, ("C-2", CELLS[1]): True, ("C-3", CELLS[0]): True},
    )
    shadowed = write_run(
        tmp_path / "qwen-descriptive",
        {("C-2", CELLS[0]): True, ("C-3", CELLS[1]): True},
        style="descriptive",
    )
    return original, shadowed


def test_each_arm_carries_both_runs_figures_and_the_shadows_delta(runs):
    original, shadowed = runs
    found = compare.compare(original, [shadowed])
    arms = found["shadows"][0]["sections"]["bodies"]

    assert found["original"]["model"] == MODEL and found["original"]["cells"] == list(CELLS)
    assert found["shadows"][0]["style"] == "descriptive"
    assert arms["C-2"]["original"]["pass_at_1"] == 1.0
    assert arms["C-2"]["shadow"]["pass_at_1"] == 0.5
    assert arms["C-2"]["delta"]["pass_at_1"] == -0.5
    assert arms["C-3"]["delta"]["pass_at_1"] == 0.0  # one cell each way is no change in the rate
    # the drawn sample moves with the greedy one here, so pass@k carries the same reading
    assert arms["C-2"]["delta"]["pass_at_k"] == -0.5


def test_the_flips_name_the_cells_each_way(runs):
    original, shadowed = runs
    flips = compare.compare(original, [shadowed])["shadows"][0]["flips"]
    assert flips["C-2"] == {"cells": 2, "lost": ["avx2/int8/dot"], "gained": []}
    assert flips["C-3"] == {"cells": 2, "lost": ["avx2/float32/dot"], "gained": ["avx2/int8/dot"]}


def test_a_run_at_another_k_is_refused_rather_than_differenced(tmp_path, runs):
    original, _ = runs
    other = write_run(tmp_path / "qwen-k5", {}, k=5, style="descriptive")
    with pytest.raises(compare.NotComparable) as refusal:
        compare.compare(original, [other])
    assert "k" in str(refusal.value) and "one variable" in str(refusal.value)


def test_another_model_other_params_or_other_cells_are_refused_too(tmp_path, runs):
    original, _ = runs
    cases = {
        "model": write_run(tmp_path / "olmo", {}, model="allenai/Olmo-3-7B-Instruct", style="descriptive"),
        "params": write_run(tmp_path / "hot", {}, params={**PARAMS, "temperature": 1.0}, style="descriptive"),
        "cells": write_run(tmp_path / "fewer", {}, cells=CELLS[:1], style="descriptive"),
    }
    for field, run_dir in cases.items():
        with pytest.raises(compare.NotComparable) as refusal:
            compare.compare(original, [run_dir])
        assert field in str(refusal.value) or "different cells" in str(refusal.value)


def test_a_run_with_no_meta_is_refused(tmp_path, runs):
    original, _ = runs
    (tmp_path / "empty").mkdir()
    with pytest.raises(compare.NotComparable) as refusal:
        compare.compare(original, [tmp_path / "empty"])
    assert "no meta.json" in str(refusal.value)


def test_arms_the_two_runs_do_not_share_are_left_out_rather_than_guessed(tmp_path, runs):
    original, _ = runs
    two_arms = write_run(tmp_path / "one-arm", {("C-2", CELLS[0]): True}, style="opaque", arms=("C-2",))
    found = compare.compare(original, [two_arms])
    assert sorted(found["shadows"][0]["sections"]["bodies"]) == ["C-2"]
    assert sorted(found["original"]["sections"]["bodies"]) == ["C-2", "C-3"]


def test_both_shadows_are_compared_in_one_reading(tmp_path, runs):
    original, descriptive = runs
    opaque = write_run(tmp_path / "qwen-opaque", {}, style="opaque")
    found = compare.compare(original, [descriptive, opaque])
    assert [row["style"] for row in found["shadows"]] == ["descriptive", "opaque"]
    assert found["shadows"][1]["sections"]["bodies"]["C-2"]["delta"]["pass_at_1"] == -1.0
    assert found["shadows"][1]["flips"]["C-2"]["lost"] == list(CELLS)


def test_the_table_names_each_shadow_by_its_style_and_its_flips(runs):
    original, shadowed = runs
    table = compare.render(compare.compare(original, [shadowed]))
    assert f"E2 {Path(original).name}" in table
    assert "descriptive (qwen-descriptive)" in table
    assert "-0.50" in table  # the delta carries its sign
    assert "lost   avx2/int8/dot" in table


def test_a_run_whose_rows_are_not_there_is_named_missing_and_not_read_as_zero(tmp_path, runs):
    original, _ = runs
    bare = write_run(tmp_path / "ungraded", {}, style="descriptive")
    (bare / ROWS).unlink()
    found = compare.compare(original, [bare])
    assert ROWS in found["shadows"][0]["missing"]
    assert found["shadows"][0]["sections"]["bodies"] == {}  # no arm to read, so no delta invented
    assert found["shadows"][0]["flips"] == {}
