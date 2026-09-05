"""A random-init GPT-shaped forward pass in numpy (design §8 step 2).

This is not the training block. It exists so the probe pipeline can be
run end to end before a GPU is touched — on a model with no gradient
in it the class probe must read chance, and if it does not, the world
or the probe is leaking (§6.2's check on **W** and **P**). It carries
the three input maps of the ladder (§3) so that the entity channel is
exercised the same way the trained blocks will use it: B1 reads a
name as stems, B2 and B3 as one token whose vector comes from
:func:`atlas0.tokens.entity_vectors`.

Pre-LN decoder blocks, learned positions, tied output head; the
residual stream after every block at the last position is what the
probe reads.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .tokens import Tokenizer, entity_vectors


@dataclass(frozen=True)
class ModelConfig:
    name: str
    d_model: int
    n_layers: int
    n_heads: int
    d_ff: int
    max_len: int


CONFIGS: dict[str, ModelConfig] = {
    # For tests and the step-2 pipeline check.
    "tiny": ModelConfig("tiny", 64, 4, 4, 256, 128),
    # The design's block: GPT-2-small shape at ~30M non-embedding parameters.
    "atlas-30m": ModelConfig("atlas-30m", 512, 8, 8, 2048, 256),
    "gpt2-small": ModelConfig("gpt2-small", 768, 12, 12, 3072, 256),
}


def _ln(x: np.ndarray, g: np.ndarray, b: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mu = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * g + b


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(0.7978845608 * (x + 0.044715 * x ** 3)))


class RefModel:
    """Random weights at ``seed``; ``forward`` returns the residual stream per layer."""

    def __init__(self, cfg: ModelConfig, tok: Tokenizer, seed: int):
        self.cfg, self.tok, self.seed = cfg, tok, seed
        rng = np.random.default_rng(seed)
        d, ff, V = cfg.d_model, cfg.d_ff, len(tok)
        n = lambda *shape: rng.normal(0.0, 0.02, shape).astype(np.float32)
        self.wte = n(V, d)
        self.wpe = n(cfg.max_len, d)
        self.layers = [{
            "ln1_g": np.ones(d, np.float32), "ln1_b": np.zeros(d, np.float32),
            "qkv": n(d, 3 * d), "proj": n(d, d),
            "ln2_g": np.ones(d, np.float32), "ln2_b": np.zeros(d, np.float32),
            "fc": n(d, ff), "fc2": n(ff, d),
        } for _ in range(cfg.n_layers)]
        self.lnf_g, self.lnf_b = np.ones(d, np.float32), np.zeros(d, np.float32)
        # The entity channel (§3): under B2 the entity rows are initialised from the
        # seeded vectors and would train; under B3 they are those vectors, frozen.
        self.frozen_rows: list[int] = []
        ids = tok.entity_ids
        if ids:
            names = sorted(ids)
            vecs = entity_vectors(names, d, seed)
            for i, name in enumerate(names):
                self.wte[ids[name]] = vecs[i]
            if tok.block == "B3":
                self.frozen_rows = [ids[n] for n in names]

    @property
    def n_params(self) -> int:
        emb = self.wte.size + self.wpe.size
        per = sum(w.size for w in self.layers[0].values())
        return emb + per * self.cfg.n_layers + self.lnf_g.size * 2

    def _block(self, x: np.ndarray, L: dict) -> np.ndarray:
        T, d = x.shape
        h = self.cfg.n_heads
        hd = d // h
        q, k, v = np.split(_ln(x, L["ln1_g"], L["ln1_b"]) @ L["qkv"], 3, axis=-1)
        q = q.reshape(T, h, hd).transpose(1, 0, 2)
        k = k.reshape(T, h, hd).transpose(1, 0, 2)
        v = v.reshape(T, h, hd).transpose(1, 0, 2)
        att = q @ k.transpose(0, 2, 1) / np.sqrt(hd)
        att = att + np.triu(np.full((T, T), -1e9, np.float32), 1)
        att = np.exp(att - att.max(-1, keepdims=True))
        att /= att.sum(-1, keepdims=True)
        y = (att @ v).transpose(1, 0, 2).reshape(T, d) @ L["proj"]
        x = x + y
        x = x + _gelu(_ln(x, L["ln2_g"], L["ln2_b"]) @ L["fc"]) @ L["fc2"]
        return x

    def forward(self, ids: list[int]) -> tuple[np.ndarray, np.ndarray]:
        """(residuals, logits): residuals ``(n_layers + 1, d)`` at the last position, layer 0 the embedding."""
        ids = ids[-self.cfg.max_len:]
        x = self.wte[ids] + self.wpe[: len(ids)]
        res = [x[-1].copy()]
        for L in self.layers:
            x = self._block(x, L)
            res.append(x[-1].copy())
        logits = _ln(x[-1], self.lnf_g, self.lnf_b) @ self.wte.T
        return np.stack(res), logits

    def generate(self, ids: list[int], max_new: int = 8) -> tuple[list[int], float]:
        """Greedy continuation and the entropy (bits) of the first-token distribution."""
        out = list(ids)
        entropy = 0.0
        for step in range(max_new):
            _, logits = self.forward(out)
            p = np.exp(logits - logits.max())
            p /= p.sum()
            if step == 0:
                entropy = float(-(p * np.log2(p + 1e-12)).sum())
            nxt = int(np.argmax(logits))
            out.append(nxt)
            if self.tok.vocab[nxt] in ("<nl>", "<eos>"):
                break
        return out[len(ids):], entropy
