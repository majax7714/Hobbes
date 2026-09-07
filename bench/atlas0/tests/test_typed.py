"""The §5 instruments (2026-09-07) on a tiny B4 cell and its B1 control."""

import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from atlas0 import train, typed, world as W  # noqa: E402


@pytest.fixture(scope="module")
def cells(tmp_path_factory):
    out = tmp_path_factory.mktemp("w")
    world = out / "world"
    W.write(W.generate(5, W.Config.tiny().with_variant("v2")), world)
    base = dict(model="tiny", arm="lived+phrase", steps=6, batch=8, seq_len=64, ckpt_every=6, ckpt_items=6, probe_per_class=6, warmup=1)
    train.run(world, out / "B4-lived+phrase-s0", train.TrainConfig(block="B4", types_k=4, types_rank=4, **base), device="cpu", log=lambda s: None)
    train.run(world, out / "B1-lived+phrase-s0", train.TrainConfig(block="B1", **base), device="cpu", log=lambda s: None)
    return world, out


def test_a_cell_writes_its_typed_instruments(cells):
    world, out = cells
    for cell in ("B4-lived+phrase-s0", "B1-lived+phrase-s0"):
        assert (out / cell / "typed.json").exists(), (out / cell / "typed.error").read_text() if (out / cell / "typed.error").exists() else "missing"
    rep = json.loads((out / "B4-lived+phrase-s0" / "typed.json").read_text())
    d = rep["type_discovery"]
    assert d["K"] == 4 and len(d["layers"]) == 4 and d["n_facts"] > 0 and d["n_qa"] > 0
    l = d["layers"][d["best_layer"]]
    assert abs(sum(l["usage"]) - 1) < 1e-3 and 0 <= l["vs_relation"]["nmi"] <= 1 and 0 < l["vs_relation"]["purity"] <= 1
    assert set(d["relation_type"]) == {"defined_in", "calls", "reached_by"}
    assert set(rep["phrasing"]) == {"trained", "held-out"}
    s = rep["sibling"]
    assert set(s["overall"]) == {"shared", "random", "same_module"} and len(s["under_type"]) == 4
    a = rep["absence"]
    assert a["n"] > 0 and "absent-near/held-out" in a["rows"] and "sparse-real/without" in a["rows"]
    assert len(rep["operators"]) == 4 and len(rep["operators"][0]["types"]) == 4
    # The control carries the untyped halves only.
    rep1 = json.loads((out / "B1-lived+phrase-s0" / "typed.json").read_text())
    assert rep1["K"] == 1 and "under_type" not in rep1["sibling"] and rep1["operators"] == [] and rep1["absence"]["n"] > 0
    assert "## §5.3" in typed.render(rep) and "## §5.1" in typed.render(rep)


def test_partition_scores_are_one_on_a_perfect_partition():
    t = np.array([0, 0, 1, 1, 2, 2])
    labs = ["a", "a", "b", "b", "c", "c"]
    s = typed._partition_scores(t, labs, 3)
    assert s["purity"] == 1.0 and abs(s["nmi"] - 1.0) < 1e-9 and s["majority"]["0"]["label"] == "a"
    s = typed._partition_scores(np.zeros(6, int), labs, 3)
    assert s["nmi"] == 0.0 and abs(s["purity"] - 1 / 3) < 1e-3


def test_shared_callee_pairs_are_across_modules_and_share_a_callee(cells):
    world, _ = cells
    w = W.read(world)
    g = typed.shared_callee_pairs(w, 10, 0)
    module = {s.name: s.module for s in w.symbols}
    callees = {}
    for f in w.facts:
        if f.kind == "calls":
            callees.setdefault(f.args[0], set()).add(f.args[1])
    for a, b in g["shared"]:
        assert module[a] != module[b] and callees[a] & callees[b]
    for a, b in g["random"]:
        assert module[a] != module[b] and not (callees.get(a, set()) & callees.get(b, set()))
    for a, b in g["same_module"]:
        assert module[a] == module[b]
