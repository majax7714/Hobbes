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


def test_reevaluate_re_reads_a_cell_on_a_matching_world_and_refuses_another(tiny, tmp_path):
    train.run(tiny, tmp_path / "run", cfg(steps=8, ckpt_every=8), device="cpu", log=lambda s: None)
    m = train.reevaluate(tiny, tmp_path / "run", tmp_path / "again", device="cpu")
    assert m["reevaluated_from"].endswith("run") and m["checkpoints"] == [] and m["final"]["dense_correct"] is not None
    assert set(json.loads((tmp_path / "again" / "report.json").read_text())["confusion"]) == {"primary", "secondary", "trained"}
    other = tmp_path / "other"
    W.write(W.generate(6, W.Config.tiny()), other)
    with pytest.raises(ValueError, match="trained on corpus"):
        train.reevaluate(other, tmp_path / "run", tmp_path / "no", device="cpu")


def test_a_cell_refuses_untrained_prompt_tokens_unless_allowed_and_records_them(tmp_path):
    """The ``<nl>`` / ``live`` defect class: a prompt token no stream contains stops the read."""
    asrun = tmp_path / "asrun"
    W.write(W.generate(5, W.Config.tiny().with_variant("holdout").with_fields(held_out_phrasing=3)), asrun)   # as v1 ran: live / exercises
    with pytest.raises(train.UntrainedPromptTokens, match="live"):
        train.run(asrun, tmp_path / "no", cfg(steps=4, ckpt_every=4), device="cpu", log=lambda s: None)
    m = train.run(asrun, tmp_path / "allowed", cfg(steps=4, ckpt_every=4, allow_untrained_prompt_tokens=True),
                  device="cpu", log=lambda s: None)
    assert set(m["eval_prompt_tokens_untrained"]["primary"]) == {"live"}
    fixed = tmp_path / "fixed"
    W.write(W.generate(5, W.Config.tiny().with_variant("holdout")), fixed)
    m = train.run(fixed, tmp_path / "ok", cfg(steps=4, ckpt_every=4), device="cpu", log=lambda s: None)
    assert m["eval_prompt_tokens_untrained"] == {}
    # The as-run cell re-reads on the fixed world (same corpora) and refuses the as-run one.
    m2 = train.reevaluate(fixed, tmp_path / "allowed", tmp_path / "reread", device="cpu")
    assert m2["eval_prompt_tokens_untrained"] == {} and m2["reevaluated_from"].endswith("allowed")
    with pytest.raises(train.UntrainedPromptTokens):
        train.reevaluate(asrun, tmp_path / "ok", tmp_path / "reread2", device="cpu")


def test_a_repeat_run_names_its_cell():
    assert cfg().cell == "B1-none-s0" and cfg(seed=3, run=2).cell == "B1-none-s3-r2"


def test_max_epochs_sets_the_steps_and_read_context_only_is_a_target(tmp_path):
    d = tmp_path / "v2"
    W.write(W.generate(5, W.Config.tiny().with_variant("v2")), d)
    m = train.run(d, tmp_path / "run", cfg(steps=999, max_epochs=0.5, ckpt_every=2, target_measure="read_context_only",
                                         stop_at_target=True, target_dense=0.0), device="cpu", log=lambda s: None)
    assert m["config"]["steps"] < 999 and m["config"]["max_epochs"] == 0.5 and m["stopped_at_target"] == 2
    ck = m["checkpoints"][0]
    assert "read_context_only" in ck and set(ck["inversion"]) >= {"C-only-qa/support", "C-only-qa/none", "C-only-qa/conflict"}
    report = json.loads((tmp_path / "run" / "report.json").read_text())
    assert {"trained_free", "trained_context_only"} <= set(report["confusion"])
    assert "C-only-qa/support" in report["inversion"]
    # A v2 cell re-reads with its own (widest) vocabulary.
    m2 = train.reevaluate(d, tmp_path / "run", tmp_path / "again", device="cpu")
    assert m2["vocab"] == m["vocab"]


# ---------------------------------------------------------------- B4 (addendum 2026-09-07) and the analysis hooks

def _b4_model(tok, K=4, seed=0):
    torch.manual_seed(seed)
    return train.GPT(train.CONFIGS["tiny"], len(tok), types_k=K, types_rank=4)


def test_typed_logit_reduces_to_q_dot_k_when_every_operator_is_the_identity(tiny):
    """With B_k = 0 every R_k = I, so whatever the router assigns the attention
    logit is q · k: a B4 forward (hard) equals the same weights read as B1."""
    ents = json.loads((tiny / "entities.json").read_text())
    tok = tokens.Tokenizer.build("B4", ents)
    m4 = _b4_model(tok)
    m1 = train.GPT(train.CONFIGS["tiny"], len(tok))
    m1.load_state_dict({k: v for k, v in m4.state_dict().items() if ".types." not in k})
    m4.eval(); m1.eval()
    x = torch.tensor([tok.encode("Q: Where is range_join_merge defined? A:")])
    with torch.no_grad():
        l4, _ = m4(x)
        l1, _ = m1(x)
    assert torch.allclose(l4, l1, atol=1e-5)
    # ... and the manual attention path (asked for its weights) equals the fused one.
    m1.ablate = train.Fwd(want_attn=True)
    with torch.no_grad():
        l1m, _ = m1(x)
    assert torch.allclose(l1m, l1, atol=1e-5) and len(m1.last.attn) == 4 and m1.last.attn[0].shape == (1, 4, x.shape[1], x.shape[1])
    m1.ablate = None


def test_at_random_init_type_usage_is_uniform_and_confidence_one_over_k(tiny):
    ents = json.loads((tiny / "entities.json").read_text())
    tok = tokens.Tokenizer.build("B4", ents)
    K = 4
    m = _b4_model(tok, K=K)
    x = torch.tensor([tok.encode("range_join_merge is defined in mod_a. Q: Where is range_join_merge defined? A:")])
    m.train()
    stats = train.type_stats(m, x)
    for l in stats["layers"]:
        assert all(abs(u - 1 / K) < 0.01 for u in l["usage"]), l
        assert abs(l["confidence"] - 1 / K) < 0.01, l
    assert stats["confidence"] < 1 / K + 0.01


def test_k_equals_one_is_b1_exactly(tiny, tmp_path):
    """K = 1: no inventory, no router, the same parameters in the same order — the
    loss curve is B1's to the digit on CPU (fp32, one device)."""
    m1 = train.run(tiny, tmp_path / "b1", cfg(block="B1", steps=10, ckpt_every=10), device="cpu", log=lambda s: None)
    m4 = train.run(tiny, tmp_path / "b4", cfg(block="B4", types_k=1, steps=10, ckpt_every=10), device="cpu", log=lambda s: None)
    assert m1["loss"] == m4["loss"] and m1["params"] == m4["params"]
    assert set(torch.load(tmp_path / "b1" / "model.pt")) == set(torch.load(tmp_path / "b4" / "model.pt"))


def test_a_b4_cell_trains_with_its_penalty_and_records_type_usage(tiny, tmp_path):
    m = train.run(tiny, tmp_path / "b4", cfg(block="B4", types_k=4, types_lambda=0.1, steps=8, ckpt_every=4),
                  device="cpu", log=lambda s: None)
    ck = m["checkpoints"][-1]
    assert "types" in ck and len(ck["types"]["layers"]) == 4 and 0 < ck["types"]["max_share_hard"] <= 1 and "aux" in ck
    state = torch.load(tmp_path / "b4" / "model.pt")
    assert "blocks.0.types.A" in state and state["blocks.0.types.B"].abs().sum() > 0     # the operators moved
    # A B4 cell reloads with its inventory.
    model, tok, c = train.load_cell(tmp_path / "b4", tiny, device="cpu")
    assert model.types_k == 4 and c.block == "B4"


def test_ablation_hooks_change_the_output_and_nothing_else_does(tiny):
    ents = json.loads((tiny / "entities.json").read_text())
    tok = tokens.Tokenizer.build("B1", ents)
    torch.manual_seed(1)
    m = train.GPT(train.CONFIGS["tiny"], len(tok)); m.eval()
    x = torch.tensor([tok.encode("Q: Where is range_join_merge defined? A:")])
    with torch.no_grad():
        base, _ = m(x)
        m.ablate = train.Fwd()
        same, _ = m(x)
        m.ablate = train.Fwd(ablate_heads={(0, 0), (2, 3)})
        heads, _ = m(x)
        m.ablate = train.Fwd(ablate_ffn={1})
        ffn, _ = m(x)
        m.ablate = None
    assert torch.allclose(same, base, atol=1e-5)
    assert not torch.allclose(heads, base, atol=1e-4) and not torch.allclose(ffn, base, atol=1e-4)


def test_weights_at_checkpoints_a_step_cap_and_a_full_read_at_a_step(tiny, tmp_path):
    m = train.run(tiny, tmp_path / "run", cfg(steps=12, ckpt_every=4, save_weights_every=8, stop_at_step=8, full_eval_at=(3,)),
                  device="cpu", log=lambda s: None)
    assert m["steps_done"] == 8 and [c["step"] for c in m["checkpoints"]] == [4, 8]
    assert (tmp_path / "run" / "ckpt" / "step-8.pt").exists() and not (tmp_path / "run" / "ckpt" / "step-4.pt").exists()
    # The full read fires at its own step, a checkpoint step or not (2,200 is not a multiple of 300).
    assert (tmp_path / "run" / "step-3" / "report.json").exists() and (tmp_path / "run" / "step-3" / "model.pt").exists()
    # ... and a saved checkpoint can be read in full after the fact.
    m2 = train.reevaluate(tiny, tmp_path / "run", tmp_path / "run" / "step-8-reread", device="cpu", weights=tmp_path / "run" / "ckpt" / "step-8.pt")
    assert m2["reevaluated_weights"].endswith("step-8.pt") and (tmp_path / "run" / "step-8-reread" / "report.json").exists()
    # The schedule was 12 steps: the learning rate at the cap is not the floor.
    assert m["config"]["steps"] == 12 and m["config"]["stop_at_step"] == 8
    model, _, _ = train.load_cell(tmp_path / "run", tiny, weights=tmp_path / "run" / "step-3" / "model.pt", device="cpu")
    assert model is not None
