"""The tokenizer, the reference model and the probe harness (design §3, §6.2, §6.3, §8 step 2)."""

import numpy as np
import pytest

from atlas0 import probe, refmodel, tokens, world as W
from atlas0.cli import run_probe_check


ENTS = {"range_join_merge": "symbol", "mod_lane": "module", "test_site_node": "test", "range_join_lane": "absent"}


class TestTokenizer:
    def test_b1_reads_a_name_as_stems_and_b3_as_one_token(self):
        text = "Q: Where is range_join_merge defined? A: ANSWER mod_lane"
        b1 = tokens.Tokenizer.build("B1", ENTS)
        b3 = tokens.Tokenizer.build("B3", ENTS)
        ids1, ids3 = b1.encode(text), b3.encode(text)
        assert b1.decode(ids1) == text and b3.decode(ids3) == text
        assert len(ids3) == len(ids1) - 4 - 2              # two names: 5 → 1 and 3 → 1 pieces
        assert not b1.entity_ids and set(b3.entity_ids) == set(ENTS)

    def test_a_held_out_absent_name_has_a_token_it_never_trained_on(self):
        b2 = tokens.Tokenizer.build("B2", ENTS)
        assert "range_join_lane" in b2.entity_ids
        v = tokens.entity_vectors(["range_join_lane", "range_join_merge"], 8, seed=1)
        again = tokens.entity_vectors(["range_join_lane"], 8, seed=1)
        assert np.allclose(v[0], again[0]) and not np.allclose(v[0], v[1])
        assert not np.allclose(v[0], tokens.entity_vectors(["range_join_lane"], 8, seed=2)[0])

    def test_roundtrip_of_every_template(self, tmp_path):
        tk = tokens.Tokenizer.build("B1", ENTS)
        for line in ("lookup(range_join_lane) → undefined.", "Inside range_join_merge there is a call to range_join_merge.",
                     "test_site_node reaches range_join_merge.", "Q: What reaches range_join_merge? A: CANDIDATES mod_lane, range_join_merge"):
            assert tk.decode(tk.encode(line)) == line
        tk.save(tmp_path / "tok.json")
        assert tokens.Tokenizer.load(tmp_path / "tok.json").vocab == tk.vocab


class TestRefModel:
    def test_forward_shapes_and_determinism(self):
        tk = tokens.Tokenizer.build("B3", ENTS)
        m = refmodel.RefModel(refmodel.CONFIGS["tiny"], tk, seed=3)
        ids = tk.encode("Q: Where is range_join_merge defined? A:")
        res, logits = m.forward(ids)
        assert res.shape == (5, 64) and logits.shape == (len(tk),)
        res2, _ = refmodel.RefModel(refmodel.CONFIGS["tiny"], tk, seed=3).forward(ids)
        assert np.allclose(res, res2)
        assert m.frozen_rows == sorted(tk.entity_ids[n] for n in ENTS)
        out, entropy = m.generate(ids, max_new=3)
        assert 1 <= len(out) <= 3 and entropy > 0

    def test_entity_rows_are_the_seeded_vectors(self):
        tk = tokens.Tokenizer.build("B2", ENTS)
        m = refmodel.RefModel(refmodel.CONFIGS["tiny"], tk, seed=3)
        v = tokens.entity_vectors(["mod_lane"], 64, seed=3)[0]
        assert np.allclose(m.wte[tk.entity_ids["mod_lane"]], v) and m.frozen_rows == []


class TestProbe:
    def test_separable_activations_probe_high_and_random_ones_chance(self):
        rng = np.random.default_rng(0)
        n = 300
        y = [probe.CLASS3[i % 3] for i in range(n)]
        X = rng.normal(size=(n, 2, 16))
        X[:, 1, :3] += np.eye(3)[[i % 3 for i in range(n)]] * 4
        r = probe.probe_layers(X, y, seed=0)
        assert r["layers"][1]["test"] > 0.9 and r["layers"][0]["test"] < r["chance"] + 0.15
        assert r["best_layer"] == 1 and len(r["test_predictions"]) == r["n_test"]

    def test_balanced_indices_drop_unclassed_rows(self):
        items = [{"class": c} for c in ("dense-real",) * 5 + ("sparse-real",) * 4 + ("absent-near",) * 2
                 + ("absent-far",) * 2 + ("mid",) * 3 + ("module-infer",) * 2]
        idx, y = probe.balanced_indices(items, seed=1)
        assert len(idx) == 12 and set(y) == set(probe.CLASS3) and all(probe.class3(items[i]) for i in idx)

    def test_mutual_information(self):
        assert probe.mutual_information(["a", "b"] * 20, ["x", "y"] * 20) == pytest.approx(1.0)
        assert probe.mutual_information(["a", "b"] * 20, ["x"] * 40) == 0.0
        assert probe.entropy_bins([0.0, 1.0, 2.0, 3.0]) == ["q0", "q1", "q2", "q3"]

    def test_authority_tables(self):
        r = probe.authority(["dense", "absent"] * 10, ["dense", "absent"] * 10, ["ANSWER-correct", "UNDEFINED"] * 10, [1.0, 3.0] * 10)
        assert r["p_act_given_probed"] == {"absent": {"UNDEFINED": 1.0}, "dense": {"ANSWER-correct": 1.0}}
        assert r["mi_act_probed"] == pytest.approx(1.0) and r["mi_act_entropy"] == pytest.approx(1.0)
        assert r["entropy_by_true_class"] == {"absent": 3.0, "dense": 1.0}


class TestStep2Exit:
    def test_model_size_matches_the_built_model(self):
        from atlas0.cli import _model_size
        tk = tokens.Tokenizer.build("B3", ENTS)
        m = refmodel.RefModel(refmodel.CONFIGS["tiny"], tk, seed=0)
        assert _model_size("B3", ENTS, "tiny", 0) == (m.n_params, len(tk))

    def test_probe_on_a_random_init_model_reports_chance(self, tmp_path):
        W.write(W.generate(11, W.Config.tiny()), tmp_path)
        for block in ("B1", "B3"):
            r = run_probe_check(tmp_path, block, "tiny", per_class=30, seed=1, workers=1)
            assert r["at_chance"], (block, r["probe"])
            assert r["items"] == 90 and r["confusion"]["missing"] == 0
            assert set(r["authority"]["entropy_by_true_class"]) == set(probe.CLASS3)
