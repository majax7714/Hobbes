"""The §1 checks (2026-09-07): spans, the head/FFN checks run end to end on a tiny cell, the B2 norm check."""

import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from atlas0 import mech, tokens, train, world as W  # noqa: E402


@pytest.fixture(scope="module")
def cells(tmp_path_factory):
    out = tmp_path_factory.mktemp("w")
    world = out / "world"
    W.write(W.generate(5, W.Config.tiny().with_variant("v2")), world)
    base = dict(model="tiny", arm="none", steps=6, batch=8, seq_len=64, ckpt_every=6, ckpt_items=6, probe_per_class=6, warmup=1)
    train.run(world, out / "B1-none-s0", train.TrainConfig(block="B1", **base), device="cpu", log=lambda s: None)
    train.run(world, out / "B2-phrase-s0", train.TrainConfig(block="B2", **dict(base, arm="phrase")), device="cpu", log=lambda s: None)
    return world, out


def test_span_finds_a_name_under_both_input_maps(cells):
    world, _ = cells
    ents = json.loads((world / "entities.json").read_text())
    for block, n in (("B1", 3), ("B2", 1)):
        tok = tokens.Tokenizer.build(block, ents)
        mod = next(e for e, k in ents.items() if k == "module")
        ids = tok.encode(f"{mod} defines x_y. Q: Which module does x_y live in? A:")
        sp = mech.span(tok, ids, mod)
        assert len(sp) == n and [tok.vocab[ids[i]] for i in sp] == ([mod] if n == 1 else mod.split("_")[:1] + ["_"] + mod.split("_")[1:])


def test_head_and_ffn_checks_run_and_report_every_route(cells):
    world, out = cells
    rep = mech.run_checks(out / "B1-none-s0", world, None, ("heads", "ffn"), device="cpu", n_items=4, seed=0)
    hc, fc = rep["heads"], rep["ffn"]
    assert hc["split"] == "C-only-qa" and len(hc["ranked"]) == 16 and np.array(hc["mass_answer_slot"]).shape == (4, 4)
    assert {"read", "follow", "parametric", "read_none"} <= set(hc["baseline"])
    assert [a["n"] for a in hc["ablations"]] == [1, 2, 4, 8, 16] and len(hc["ablations"][0]["random"]) == 3
    assert len(fc["layers"]) == 4 and len(fc["cumulative_from_top"]) == 4 and fc["cumulative_from_top"][-1]["layers"] == [0, 1, 2, 3]
    text = mech.render(rep)
    assert "## reads" in text and "## stores" in text


def test_b2_norm_check_reads_rows_and_a_threshold(cells):
    world, out = cells
    rep = mech.b2_norm_check(out / "B2-phrase-s0", world)
    assert rep["n"] > 0 and set(rep["by_row"]) >= {"dense-real", "sparse-real"}
    assert 0 <= rep["best_threshold"]["accuracy"] <= 1 and rep["best_threshold"]["accuracy"] >= rep["best_threshold"]["majority"] - 1e-9
    assert "auc_norm_predicts_undefined" in rep
    assert "| cell |" in mech.render_b2([rep])
