"""The noise floor: the paired tests' arithmetic, checked by hand, and the two ways a reader reaches them.

The p-values here are small enough to count on paper — a test that cannot be checked by hand on six
cells is not one to read over sixty-three.
"""

import json
from fractions import Fraction

import pytest

from lattice import cli, compare, paired
from lattice.e1 import META, ROWS

from test_compare import CELLS, runs, write_run  # noqa: F401 — `runs` is a fixture


def test_mcnemar_is_twice_the_smaller_binomial_tail():
    assert paired.mcnemar(0, 6) == pytest.approx(2 / 64)  # six moved, all one way: 0.03125
    assert paired.mcnemar(1, 5) == pytest.approx(2 * 7 / 64)  # C(6,0) + C(6,1) = 7
    assert paired.mcnemar(3, 3) == 1.0  # capped, never above 1
    assert paired.mcnemar(0, 5) == pytest.approx(2 / 32)  # five one way is not yet under 0.05
    assert paired.mcnemar(0, 0) == 1.0  # nothing moved is no evidence either way


def test_sign_flip_counts_every_sign_pattern_exactly():
    assert paired.sign_flip([Fraction(1)] * 3) == pytest.approx(2 / 8)  # only +++ and --- reach |3|
    # rates in fifths are scaled to integers 1 and 2: sums ±3 and ±1, two of the four reach |3|
    assert paired.sign_flip([Fraction(1, 5), Fraction(2, 5)]) == pytest.approx(0.5)
    # a zero difference doubles every count and so changes nothing
    assert paired.sign_flip([Fraction(1), Fraction(0)]) == 1.0
    assert paired.sign_flip([]) == 1.0


def _arm(greedy, drawn):
    return {cell: {"greedy": g, "drawn": d} for cell, g, d in zip(("a", "b", "c", "d"), greedy, drawn)}


def test_paired_reads_each_figure_over_the_cells_both_sides_answered():
    before = _arm([True, False, False, True], [[True, False], [False, False], [False, False], [True, True]])
    after = _arm([True, True, True, False], [[True, True], [True, False], [False, False], [True, True]])
    after["e"] = {"greedy": True, "drawn": [True, True]}  # only one side answered it: unpaired, not a pass
    tests = paired.paired(before, after, k=2)

    assert tests["unpaired"] == 1
    greedy = tests["pass_at_1"]
    assert (greedy["cells"], greedy["both"], greedy["neither"], greedy["lost"], greedy["gained"]) == (4, 1, 0, 1, 2)
    assert greedy["delta"] == pytest.approx(0.25)
    assert greedy["p"] == pytest.approx(1.0)  # 1 lost, 2 gained: 2 * (1 + 3) / 8, capped
    anypass = tests["pass_at_k"]
    assert (anypass["lost"], anypass["gained"], anypass["cells"]) == (0, 1, 4)  # only `b` became any-pass
    sampled = tests["pass_at_1_sampled"]
    assert sampled["cells"] == 4 and sampled["moved"] == 2
    assert sampled["delta"] == pytest.approx((0.5 + 0.5) / 4)


def test_pass_at_k_leaves_out_a_cell_not_drawn_exactly_k_times():
    before = _arm([True], [[True]])
    after = _arm([True], [[True]])
    assert paired.paired(before, after, k=2)["pass_at_k"]["cells"] == 0
    assert paired.paired(before, after, k=2)["pass_at_k"]["delta"] is None


def test_arms_pairs_two_arms_of_one_run_and_keeps_the_sections_apart(tmp_path):
    run = write_run(
        tmp_path / "run",
        {("C-2", CELLS[0]): True, ("C-2", CELLS[1]): True, ("C-4", CELLS[0]): False},
        arms=("C-2", "C-4"),
    )
    found = paired.arms(run, "C-4", "C-2", k=1)
    assert list(found) == ["bodies"]  # no wrapper rows in this run, so no wrapper section invented
    assert found["bodies"]["pass_at_1"]["gained"] == 2
    assert found["bodies"]["pass_at_1"]["lost"] == 0
    assert paired.arms(run, "C-4", "C-9", k=1) == {}


def test_iterate_rounds_are_not_read_as_round_zero(tmp_path):
    run = write_run(tmp_path / "run", {("C-2", CELLS[0]): False}, arms=("C-2", "C-4"))
    rows = [json.loads(line) for line in (run / ROWS).read_text().splitlines()]
    rows.append({**rows[0], "round": 1, "class": "pass", "id": "late"})
    (run / ROWS).write_text("".join(json.dumps(row) + "\n" for row in rows))
    assert paired.cells(run)["bodies"]["C-2"][CELLS[0]]["greedy"] is False


def test_compare_carries_the_paired_tests_per_arm(runs):  # noqa: F811
    original, shadowed = runs
    found = compare.compare(original, [shadowed])
    tests = found["shadows"][0]["paired"]["bodies"]
    assert tests["C-2"]["pass_at_1"]["lost"] == 1 and tests["C-2"]["pass_at_1"]["p"] == 1.0
    assert "paired, bodies" in compare.render(found)


def test_the_cli_prints_the_pair_and_refuses_a_run_without_meta(tmp_path, capsys):
    run = write_run(tmp_path / "run", {("C-2", CELLS[0]): True}, arms=("C-2", "C-4"))
    assert cli.main(["e1", "paired", str(run), "C-4", "C-2"]) == 0
    assert "C-2 − C-4" in capsys.readouterr().out
    assert cli.main(["e1", "paired", str(run), "C-4", "C-2", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["bodies"]["pass_at_1"]["gained"] == 1
    (run / META).unlink()
    assert cli.main(["e1", "paired", str(run), "C-4", "C-2"]) == 2
