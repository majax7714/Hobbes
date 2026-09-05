"""The trainer (design §3, §5): one cell end to end on CPU, the entity channel per block."""

import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from atlas0 import train, tokens, world as W  # noqa: E402


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    out = tmp_path_factory.mktemp("world")
    W.write(W.generate(5, W.Config.tiny()), out)
    return out


def cfg(**kw):
    base = dict(model="tiny", block="B1", arm="none", steps=12, batch=8, seq_len=64, ckpt_every=6,
                ckpt_items=10, probe_per_class=12, warmup=2)
    base.update(kw)
    return train.TrainConfig(**base)


def test_a_run_writes_its_records_and_loss_falls(tiny, tmp_path):
    m = train.run(tiny, tmp_path / "run", cfg(steps=30, ckpt_every=15), device="cpu", log=lambda s: None)
    assert m["steps_done"] == 30 and m["epochs"] > 0 and m["tokens_per_s"] > 0 and m["device"] == "cpu"
    assert m["loss"][0][1] > m["loss"][-1][1]
    assert [c["step"] for c in m["checkpoints"]] == [15, 30]
    assert set(m["final"]) == {"dense_correct", "sparse_correct", "probe_best_test", "probe_chance", "mi_act_probed"}
    report = json.loads((tmp_path / "run" / "report.json").read_text())
    assert set(report["confusion"]) == {"primary", "secondary", "trained"}
    assert set(report["inversion"]) == {f"{s}/{k}" for s in ("C+S", "C-only") for k in ("none", "support", "conflict")}
    for name in ("primary", "secondary", "trained", "inversion"):
        assert (tmp_path / "run" / "outputs" / f"{name}.jsonl").exists()
    r = np.load(tmp_path / "run" / "residuals.npz")
    assert r["residuals"].shape[1] == 5 and len(r["ids"]) == len(r["classes"])


def test_b3_entity_rows_do_not_move_and_b2_rows_do(tiny, tmp_path):
    ents = json.loads((tiny / "entities.json").read_text())
    for block, moves in (("B3", False), ("B2", True)):
        train.run(tiny, tmp_path / block, cfg(block=block, steps=8, ckpt_every=8), device="cpu", log=lambda s: None)
        tok = tokens.Tokenizer.build(block, ents)
        state = torch.load(tmp_path / block / "model.pt")
        names = sorted(tok.entity_ids)
        want = tokens.entity_vectors(names, 64, seed=0)
        got = state["wte.weight"][[tok.entity_ids[n] for n in names]].numpy()
        assert np.allclose(got, want, atol=1e-6) is (not moves), block
        # Non-entity rows train under both.
        stem_row = state["wte.weight"][tok.index["range"]].numpy()
        assert not np.allclose(stem_row, 0) and np.abs(stem_row).max() > 0


def test_stop_at_target_records_the_step(tiny, tmp_path):
    m = train.run(tiny, tmp_path / "cal", cfg(steps=12, ckpt_every=6, stop_at_target=True, target_dense=0.0),
                  device="cpu", log=lambda s: None)
    assert m["stopped_at_target"] == 6 and m["steps_done"] == 6


def test_generate_groups_by_length_and_reads_residuals(tiny):
    ents = json.loads((tiny / "entities.json").read_text())
    tok = tokens.Tokenizer.build("B1", ents)
    model = train.GPT(train.CONFIGS["tiny"], len(tok))
    prompts = ["Q: Where is range_join_merge defined? A:", "Q: What reaches range_join_merge? A:", "Q: Where is a_b defined? A:"]
    outs, ents_, R = train.generate(model, tok, prompts, "cpu", max_new=3, want_residuals=True)
    assert len(outs) == 3 and all(e > 0 for e in ents_) and R.shape == (3, 5, 64)


def test_generate_stops_at_eos_without_emitting_it(tiny):
    ents = json.loads((tiny / "entities.json").read_text())
    tok = tokens.Tokenizer.build("B1", ents)
    seq = [tok.index[t] for t in ("ANSWER", "mod", "_", "lane")] + [tok.index[tokens.EOS], tok.index["mod"]]
    prompt = "Q: Where is a_b defined? A:"
    n_prompt = len(tok.encode(prompt))

    class Scripted:
        """A stand-in block whose next token is fixed by how many tokens it has generated."""
        def eval(self): pass
        def train(self): pass
        def __call__(self, x, residuals=False):
            B, T = x.shape
            logits = torch.zeros(B, T, len(tok))
            logits[:, -1, seq[T - n_prompt]] = 1.0
            return logits, ([torch.zeros(B, T, 4)] * 2 if residuals else None)

    outs, _, _ = train.generate(Scripted(), tok, [prompt], "cpu", max_new=6)
    assert outs == ["ANSWER mod_lane"]
