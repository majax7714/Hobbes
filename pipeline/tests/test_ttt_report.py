"""The H-TTT-1 report (ADR-099): four arms from two NLL runs, paired by
unit, a seeded bootstrap, the C-84 split — and a script that prints it."""

import json

import pytest

from hobbes.ttt import report
from hobbes.ttt.report import arm_table, format_nav_report, format_report, nav_report, paired


def run(with_adapter: bool, values: dict[str, tuple[float, float]]) -> dict:
    """``unit -> (bare, aided)`` as an NLL run record."""
    rows = []
    for unit, (bare, aided) in values.items():
        rows.append({"unit": unit, "prompt": "bare", "nll_mean": bare})
        rows.append({"unit": unit, "prompt": "aided", "nll_mean": aided})
    rows.append({"unit": "skipped-one", "prompt": "bare", "skipped": True, "tokens": 99999})
    return {"adapter": "x" if with_adapter else None, "rows": rows}


BASE = run(False, {f"u{i}": (2.0 + i / 100, 1.9 + i / 100) for i in range(30)})
ADAPTER = run(True, {f"u{i}": (1.5 + i / 100, 1.45 + i / 100) for i in range(30)})


class TestArms:
    def test_four_arms_from_two_runs_and_skips_dropped(self):
        table = arm_table(BASE, ADAPTER)
        assert set(table) == {"A0", "A1", "A2", "A3"}
        assert table["A0"]["u0"] == 2.0 and table["A1"]["u0"] == 1.9 and table["A2"]["u0"] == 1.5 and table["A3"]["u0"] == 1.45
        assert "skipped-one" not in table["A0"]

    def test_a_missing_run_leaves_its_arms_out(self):
        assert set(arm_table(BASE, None)) == {"A0", "A1"}


class TestPaired:
    def test_constant_shift_is_significant_and_reproducible(self):
        table = arm_table(BASE, ADAPTER)
        p = paired(table["A2"], table["A0"])
        assert p.n == 30 and p.delta == pytest.approx(-0.5) and p.wins == 30
        assert p.ci_high < 0 and p.p < 0.05
        assert paired(table["A2"], table["A0"]).__dict__ == p.__dict__  # seeded

    def test_noise_around_zero_is_not(self):
        a = {f"u{i}": 2.0 + ((i * 7919) % 13 - 6) / 100 for i in range(40)}
        b = {f"u{i}": 2.0 + ((i * 104729) % 13 - 6) / 100 for i in range(40)}
        p = paired(a, b, resamples=2000)
        assert p.ci_low < 0 < p.ci_high and p.p > 0.05

    def test_restricts_to_the_named_units_and_the_intersection(self):
        a = {"u1": 1.0, "u2": 1.0, "u3": 5.0}
        b = {"u1": 2.0, "u2": 2.0}
        p = paired(a, b, ["u1", "u3"])
        assert p.n == 1 and p.delta == -1.0
        assert paired(a, b, []) is None


class TestReport:
    def test_populations_and_comparisons(self):
        known = {f"u{i}" for i in range(10)}
        rep = report.report(BASE, ADAPTER, known, resamples=500)
        assert rep["populations"] == {"all": 30, "context-known": 10, "no-known-file": 20}
        assert rep["arms"]["A3"]["mean"] == pytest.approx(1.595)
        assert "all:A2-A1" in rep["comparisons"] and "context-known:A1-A0" in rep["comparisons"]
        assert rep["comparisons"]["context-known:A1-A0"]["n"] == 10
        assert rep["comparisons"]["all:A2-A1"]["delta"] == pytest.approx(-0.4)
        text = format_report(rep)
        assert "all:A2-A1" in text and "H-TTT-1" in text and "C-84" in text
        json.dumps(rep)  # serialisable

    def test_base_only_report_has_two_arms(self):
        rep = report.report(BASE, None, resamples=100)
        assert set(rep["arms"]) == {"A0", "A1"} and list(rep["comparisons"]) == ["all:A1-A0"]


def nav_run(scores: dict[tuple[str, str], float], empty: set[tuple[str, str]] = frozenset()) -> dict:
    """Rows as `ttt_probe.py nav` writes them; an item in *empty* has a 'none recorded' truth."""
    return {"rows": [{"family": f, "symbol": s, "score": v, "found": [], "missed": [] if (f, s) in empty else ["x"]}
                     for (f, s), v in scores.items()]}


class TestNavReport:
    def test_per_family_means_and_paired_deltas(self):
        items = {("callers", f"s{i}"): 0.0 for i in range(20)} | {("absent", f"d{i}"): 1.0 for i in range(10)}
        a0 = nav_run(items)
        a2 = nav_run({k: (1.0 if k[0] == "callers" else 0.0) for k in items})  # learns callers, invents on distractors
        rep = nav_report({"A0": a0, "A2": a2}, resamples=500)
        assert rep["arms"]["A0"]["callers"]["mean"] == 0.0 and rep["arms"]["A2"]["callers"]["mean"] == 1.0
        assert rep["arms"]["A0"]["absent_false_acceptance"] == 0.0 and rep["arms"]["A2"]["absent_false_acceptance"] == 1.0
        assert rep["arms"]["A2"]["navigation"] == {"n": 20, "mean": 1.0}
        c = rep["comparisons"]["A2-A0:callers"]
        assert c["n"] == 20 and c["delta"] == 1.0 and c["higher"] == 20 and c["wins"] == 0 and c["p"] < 0.05
        assert rep["comparisons"]["A2-A0:absent"]["delta"] == -1.0
        assert rep["comparisons"]["A2-A0:navigation"]["n"] == 20
        text = format_nav_report(rep)
        assert "absent FA" in text and "A2-A0:callers" in text and "A2-A0:navigation" in text

    def test_without_the_baseline_only_arms_are_reported(self):
        rep = nav_report({"A2": nav_run({("defines", "x"): 1.0})}, resamples=10)
        assert rep["comparisons"] == {} and rep["arms"]["A2"]["defines"]["mean"] == 1.0

    def test_empty_truth_items_are_split_out_of_the_navigation_mean(self):
        items = {("callers", "s1"): 0.0, ("callers", "s2"): 0.0, ("callers", "e1"): 1.0, ("callers", "e2"): 1.0}
        run = nav_run(items, empty={("callers", "e1"), ("callers", "e2")})
        rep = nav_report({"A0": run}, resamples=10)
        assert rep["arms"]["A0"]["callers"] == {"n": 2, "mean": 0.0}
        assert rep["arms"]["A0"]["callers∅"] == {"n": 2, "mean": 1.0}
        assert rep["arms"]["A0"]["navigation"] == {"n": 2, "mean": 0.0}
        assert "callers∅" in format_nav_report(rep)
