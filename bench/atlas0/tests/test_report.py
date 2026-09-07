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
    assert "### B3/none — 2 cell(s)" in text and "0.55 [0.50–0.60]" in text
    assert s["cells"] == 2


def test_a_repeat_run_is_a_cell_of_its_group(tmp_path):
    """§6.6 as amended: a ``-r2`` repeat (same seed) is one more cell in the group,
    and the spread is read over seeds and repeats together."""
    _cell(tmp_path, "B1-none-s1", sparse=0.5)
    _cell(tmp_path, "B1-none-s1-r2", sparse=0.7)
    cells = R.load_cells(tmp_path)
    assert [(c["seed"], c["run"]) for c in cells] == [(1, 1), (1, 2)]
    agg = R.aggregate(cells)
    assert agg["B1/none"]["sparse-real|ANSWER-correct"] == {"mean": 0.6, "min": 0.5, "max": 0.7, "n": 2}


def test_report_reads_a_cell_at_a_step_and_the_typed_measures_and_loss_delta(tmp_path):
    """2026-09-07: --at N reads step-N/ as the cell's read; typed.json rides along; B4 − B1 loss delta pairs by seed."""
    import json
    from atlas0 import report as R
    runs = tmp_path / "runs"
    man_common = {"final": {"dense_correct": 0.5}, "tokens_per_s": 1.0, "steps_done": 20,
                  "loss": [[0, 3.0], [10, 2.0], [19, 1.0]], "checkpoints": [{"step": 10}, {"step": 20}]}
    rep = {"confusion": {"primary": {"columns": [], "rows": {"dense-real": {"ANSWER-correct": 1, "ANSWER-wrong": 0, "CANDIDATES-with": 0, "CANDIDATES-without": 0,
                                                                               "UNDEFINED": 0, "UNKNOWN": 0, "malformed": 0}},
                                    "extra": {"dense-real": {"n": 1}}, "missing": 0}},
           "probe": {"best_test": 0.4, "chance": 0.33, "best_layer": 1}, "authority": {"mi_act_probed": 0, "mi_act_true": 0, "mi_act_entropy": 0, "mi_probed_true": 0},
           "inversion": {}, "sparse_by_nearest_dense_distance": {}}
    typed = {"type_discovery": {"layers": [{"max_share": 0.5, "vs_relation": {"nmi": 0.7, "purity": 0.9}, "vs_direction": {"nmi": 0.1}, "vs_template": {"nmi": 0.2}}],
                                "best_layer": 0, "best_nmi": 0.7, "best_purity": 0.9},
             "phrasing": {"trained": {"layers": [{"purity": 0.9}]}, "held-out": {"layers": [{"purity": 0.8}]}},
             "sibling": {"share_of_wrong_near": 0.2, "overall": {"shared": 0.5, "random": 0.1, "same_module": 0.6},
                         "under_type": {"0": {"shared": 0.7, "random": 0.1, "same_module": 0.6}}},
             "absence": {"absent_auc_signal_undefined": 0.8, "rows": {"absent-near/held-out": {"undefined": 0.5, "signal_mean": 0.1}}}}
    for block, extra in (("B1", {}), ("B4", {"checkpoints": [{"step": 10, "types": {"max_share_hard": 0.4, "confidence": 0.5}}, {"step": 20, "types": {"max_share_hard": 0.6, "confidence": 0.7}}]})):
        d = runs / f"{block}-none-s1"
        (d / "step-10").mkdir(parents=True)
        man = dict(man_common, **extra, loss=[[0, 3.0], [10, 2.0 + (0.5 if block == "B4" else 0)], [19, 1.0]])
        (d / "manifest.json").write_text(json.dumps(man))
        (d / "report.json").write_text(json.dumps(rep))
        (d / "step-10" / "report.json").write_text(json.dumps(rep))
        if block == "B4":
            (d / "typed.json").write_text(json.dumps(typed))
            (d / "step-10" / "typed.json").write_text(json.dumps(typed))
    cells = R.load_cells(runs, at=10)
    assert len(cells) == 2 and all(c["at"] == 10 for c in cells)
    m = R.cell_measures(next(c for c in cells if c["block"] == "B4"))
    assert m["typed|nmi_best"] == 0.7 and m["typed|purity_heldout_phrasing"] == 0.8 and m["sibling|cos_best_type|shared"] == 0.7
    assert m["absence|auc_absent"] == 0.8 and m["types|max_share_hard"] == 0.4 and m["train|loss_at_read"] == 2.5
    ld = R.loss_delta(cells)
    assert ld["none"][10]["mean"] == 0.5 and ld["none"][20]["mean"] == 0.0     # the last logged loss at or before each step
    text = R.render(R.aggregate(cells)) + R.render_loss_delta(ld)
    assert "## B4 (addendum" in text and "## §5.3" in text and "## §5.5" in text
