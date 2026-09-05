"""The §6.1–6.6 tables over a directory of cells."""

import json

from atlas0 import report as R


def _cell(tmp_path, name, dense=0.9, sparse=0.5, near_undef=0.0, probe=0.36):
    d = tmp_path / name
    d.mkdir()
    rows = {"dense-real": {"ANSWER-correct": int(100 * dense), "ANSWER-wrong": 100 - int(100 * dense)},
            "sparse-real": {"ANSWER-correct": int(100 * sparse), "ANSWER-wrong": 100 - int(100 * sparse)},
            "absent-near/held-out": {"UNDEFINED": int(100 * near_undef), "ANSWER-wrong": 100 - int(100 * near_undef)}}
    for r in rows.values():
        for c in R.COLUMNS:
            r.setdefault(c, 0)
    rep = {"confusion": {"primary": {"columns": list(R.COLUMNS), "rows": rows,
                                     "extra": {k: {"n": 100, "wrong-sibling": 10} for k in rows}, "missing": 0}},
           "probe": {"best_test": probe, "chance": 0.36, "best_layer": 3},
           "authority": {"mi_act_probed": 0.0, "mi_act_true": 0.5, "mi_act_entropy": 0.0, "mi_probed_true": 0.0},
           "inversion": {"C+S/none": {"gold": 0.9, "context": 0.0, "n": 10}, "C+S/conflict": {"gold": 0.8, "context": 0.1, "n": 10}},
           "sparse_by_nearest_dense_distance": {"2": {"n": 50, "ANSWER-correct": 25}},
           "secondary_by_kind": {}}
    man = {"final": {"dense_correct": dense}, "tokens_per_s": 1000.0, "container": {"cost_usd_assumed": 0.1}}
    (d / "report.json").write_text(json.dumps(rep))
    (d / "manifest.json").write_text(json.dumps(man))


def test_aggregate_and_gate(tmp_path):
    _cell(tmp_path, "B1-none-s1", sparse=0.5)
    _cell(tmp_path, "B1-none-s2", sparse=0.6)
    _cell(tmp_path, "B3-none-s1", sparse=0.9, near_undef=0.8)
    _cell(tmp_path, "B3-none-s2", sparse=0.95, near_undef=0.7)
    (tmp_path / "not-a-cell").mkdir()
    cells = R.load_cells(tmp_path)
    assert [(c["block"], c["seed"]) for c in cells] == [("B1", 1), ("B1", 2), ("B3", 1), ("B3", 2)]
    agg = R.aggregate(cells)
    assert set(agg) == {"B1/none", "B3/none"}
    assert agg["B1/none"]["sparse-real|ANSWER-correct"] == {"mean": 0.55, "min": 0.5, "max": 0.6, "n": 2}
    assert agg["B1/none"]["absent-near/held-out|sibling-share-of-wrong"]["mean"] == 0.1
    s = R.separable(agg, "sparse-real|ANSWER-correct", "B1/none", "B3/none")
    assert s["separable"] and s["diff"] == 0.375 and s["spread"] == 0.1
    gate = R.gate(agg)
    assert any(g["key"] == "absent-near/held-out|UNDEFINED" and g["separable"] for g in gate)
    assert not any(g["key"] == "probe|best_test" and g["separable"] for g in gate)   # equal → not separable
    text = R.render(agg)
    assert "### B3/none — 2 seed(s)" in text and "0.55 [0.50–0.60]" in text
