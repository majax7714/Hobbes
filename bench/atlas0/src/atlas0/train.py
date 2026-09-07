"""Training a block on the world (design §3, §5) — steps 3 and 4.

One run is one (block, arm, seed) cell: a GPT-shaped decoder of the
reference model's shape (``atlas0.refmodel.CONFIGS``), trained from
scratch on the arm's corpus as a packed language-modelling stream,
then read by the instruments the random-init check already used —
``acts`` for the §6.1 matrix over every eval set, ``probe`` for the
class probe and the §6.3 authority tables, and the inversion set for
§6.4 at every checkpoint. The three blocks differ only at the input
map: B1 reads a name as stems; B2 gives every entity one token whose
row is initialised from :func:`atlas0.tokens.entity_vectors` and
trains; B3 uses those rows frozen (their gradient is zeroed and they
take no weight decay).

The regime **T** (§5) is the :class:`TrainConfig`: held constant across
blocks and arms once step 3 has calibrated ``steps``; ``stop_at_target``
is the calibration mode, which stops at the first checkpoint whose
held-out dense-real accuracy reaches the target and reports the step.
Everything a run measured — tokens per second, wall time, the device,
the loss curve, every checkpoint's numbers, the world and corpus
hashes — goes in ``manifest.json``; ``report.json`` carries the final
matrices and probe; ``outputs/<set>.jsonl`` the per-item outputs so
``atlas0 score`` can re-read them; ``residuals.npz`` the balanced
primary items' residual stream for a probe re-fit.

Determinism is keyed to the seed on one device class and not promised
across GPU classes (the manifest records the device rather than hides
it, as ADR-099 §7 does for the adapters).
"""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from . import acts, probe
from .refmodel import CONFIGS, ModelConfig
from .tokens import BOS, EOS, NL, Tokenizer, entity_vectors, untrained_prompt_tokens
from .world import ARMS


class UntrainedPromptTokens(ValueError):
    """An eval prompt carries a token the training stream never contains (the
    ``<nl>`` / ``live`` defect class); the cell is not read through it."""


@dataclass
class TrainConfig:
    model: str = "atlas-30m"
    block: str = "B1"
    arm: str = "none"
    seed: int = 0
    steps: int = 3000
    batch: int = 64                 # sequences per step
    seq_len: int = 256
    lr: float = 6e-4
    min_lr_ratio: float = 0.1
    warmup: int = 100
    weight_decay: float = 0.1
    grad_clip: float = 1.0
    precision: str = "bf16"         # bf16 autocast on CUDA; fp32 elsewhere
    ckpt_every: int = 250
    ckpt_items: int = 200           # per class at a checkpoint (dense / sparse / absent-held-out / inversion per variant)
    probe_per_class: int = 300      # balanced primary items whose residuals the probe reads
    target_dense: float = 0.95      # §5: the accuracy the budget is calibrated to, on ``target_measure``
    target_measure: str = "dense_correct"   # or "read_context_only": C-only-qa/support gold (v2's B3 criterion: it must read)
    stop_at_target: bool = False    # calibration mode (step 3)
    max_epochs: float | None = None  # v2's T: ``steps`` is set at run time so the stream is seen this many times
    max_new: int = 8
    run: int = 1                    # a repeat of the same cell (same seed, same config): §6.6's run-to-run spread
    allow_untrained_prompt_tokens: bool = False   # read a cell through untrained prompt tokens anyway (recorded)
    stop_at_step: int | None = None  # the schedule is ``steps`` (or ``max_epochs``); training stops here (T_v2: 3,100 of 3,572)
    save_weights_every: int = 0      # weights at every checkpoint that is a multiple of this (``ckpt/step-N.pt``); 0: final only
    full_eval_at: tuple[int, ...] = ()   # the full read (report, outputs, weights) at these steps too (``step-N/``)
    # B4 (addendum 2026-09-07 §2): K relation operators per layer, rank r, the penalty weight λ, the router's temperature (start, end).
    types_k: int = 8
    types_rank: int = 16
    types_lambda: float = 0.1
    gumbel_tau: tuple[float, float] = (1.0, 0.3)

    @property
    def cell(self) -> str:
        """``<block>-<arm>-s<seed>`` and, for a repeat, ``-r<run>``."""
        return f"{self.block}-{self.arm}-s{self.seed}" + (f"-r{self.run}" if self.run > 1 else "")


class Fwd:
    """What one forward pass is asked for beyond logits (analysis and B4).

    ``tau`` / ``hard``: the router's Gumbel-softmax temperature and whether
    it takes the argmax (evaluation) instead of a sample. ``ablate_heads``
    is a set of ``(layer, head)`` whose attention output is zeroed and
    ``ablate_ffn`` a set of layers whose FFN residual is skipped (the §1
    checks of the 2026-09-07 addendum). ``want_attn`` / ``want_types``
    collect per-layer attention weights ``(B, h, T, T)`` and the router's
    ``p`` ``(B, K, T, T)``. ``aux`` and ``usage`` accumulate B4's penalties
    and the batch-mean type usage per layer.
    """

    def __init__(self, tau: float = 1.0, hard: bool = True, ablate_heads=None, ablate_ffn=None,
                 want_attn: bool = False, want_types: bool = False, noise: bool = True):
        self.tau, self.hard, self.noise = tau, hard, noise
        self.ablate_heads = set(ablate_heads or ())
        self.ablate_ffn = set(ablate_ffn or ())
        self.want_attn, self.want_types = want_attn, want_types
        self.attn: list[torch.Tensor] = []
        self.types: list[torch.Tensor] = []
        self.aux: list[torch.Tensor] = []
        self.usage: list[torch.Tensor] = []
        self.confidence: list[torch.Tensor] = []
        self.layer = 0

    @property
    def manual(self) -> bool:
        return bool(self.ablate_heads) or self.want_attn


class Types(nn.Module):
    """B4's relation inventory for one layer (addendum §2).

    ``K`` operators on the head dimension, ``R_k = I + A_k B_kᵀ`` (rank ``r``,
    shared across the layer's heads), and a router over pairs on the full
    width, ``ℓ_k(i, j) = (q_i C_k) · (k_j D_k)``, ``p(i, j) = softmax_k``.
    ``B_k`` starts at zero, so every operator is the identity at init and
    the typed logit is B1's ``q · k``; ``C`` and ``D`` are small, so ``p`` is
    uniform and the confidence ``1/K`` before any gradient — both tested.
    """

    def __init__(self, d: int, hd: int, K: int, r: int):
        super().__init__()
        self.K, self.r = K, r
        self.A = nn.Parameter(torch.randn(K, hd, r) * 0.02)
        self.B = nn.Parameter(torch.zeros(K, hd, r))
        self.C = nn.Parameter(torch.randn(K, d, r) * 0.02)
        self.D = nn.Parameter(torch.randn(K, d, r) * 0.02)

    def operators(self) -> torch.Tensor:
        """``R_k`` as ``(K, hd, hd)`` matrices."""
        hd = self.A.shape[1]
        return torch.eye(hd, device=self.A.device) + self.A @ self.B.transpose(1, 2)

    def router(self, q_full: torch.Tensor, k_full: torch.Tensor) -> torch.Tensor:
        """Router logits ``(B, K, T, T)`` from the full-width q and k (fp32)."""
        l = torch.einsum("btd,kdr->bktr", q_full, self.C)
        m = torch.einsum("bsd,kdr->bksr", k_full, self.D)
        return torch.einsum("bktr,bksr->bkts", l, m)

    def typed_extra(self, q: torch.Tensor, k: torch.Tensor) -> torch.Tensor:
        """``(q A_k) · (k B_k)`` per head and type: ``(B, h, K, T, T)``; the typed
        logit is ``q · k`` plus this, weighted by ``p``."""
        qA = torch.einsum("bhtd,kdr->bhktr", q, self.A)
        kB = torch.einsum("bhsd,kdr->bhksr", k, self.B)
        return torch.einsum("bhktr,bhksr->bhkts", qA, kB)


class Block(nn.Module):
    """One pre-LN decoder block. With ``types`` (B4) every pairwise attention
    logit routes through the layer's relation inventory; without, and with
    nothing asked of the pass, it is the fused SDPA path the v0–v2 cells
    trained on (state-dict keys unchanged, so those cells load here)."""

    def __init__(self, d: int, h: int, ff: int, types_k: int = 1, types_rank: int = 16):
        super().__init__()
        self.ln1 = nn.LayerNorm(d)
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.ln2 = nn.LayerNorm(d)
        self.fc = nn.Linear(d, ff, bias=False)
        self.fc2 = nn.Linear(ff, d, bias=False)
        self.h = h
        self.types = Types(d, d // h, types_k, types_rank) if types_k > 1 else None

    def attention(self, x: torch.Tensor, ctx: Fwd | None) -> torch.Tensor:
        B, T, d = x.shape
        hd = d // self.h
        q_full, k_full, v_full = self.qkv(self.ln1(x)).split(d, dim=-1)
        q = q_full.view(B, T, self.h, hd).transpose(1, 2)
        k = k_full.view(B, T, self.h, hd).transpose(1, 2)
        v = v_full.view(B, T, self.h, hd).transpose(1, 2)
        if self.types is None and (ctx is None or not ctx.manual):
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
            return y.transpose(1, 2).reshape(B, T, d)
        ctx = ctx or Fwd(hard=not self.training)
        scale = 1.0 / math.sqrt(hd)
        qf, kf = q.float(), k.float()
        logits = qf @ kf.transpose(-1, -2)                       # (B, h, T, T), untyped q · k
        causal = torch.ones(T, T, dtype=torch.bool, device=x.device).tril()
        if self.types is not None:
            lg = self.types.router(q_full.float(), k_full.float())          # (B, K, T, T)
            if not ctx.hard:
                if ctx.noise:
                    u = torch.rand_like(lg).clamp_(1e-9, 1 - 1e-9)
                    lg = lg - torch.log(-torch.log(u))
                p = torch.softmax(lg / ctx.tau, dim=1)
            else:
                p = F.one_hot(lg.argmax(1), self.types.K).permute(0, 3, 1, 2).to(lg.dtype)
            # The typed correction in the autocast dtype (bf16 on CUDA: half the
            # traffic of the (B, h, K, T, T) tensor, the heaviest thing here) and one
            # fused reduce over k; the base q · k stays fp32.
            extra = self.types.typed_extra(q, k)                            # (B, h, K, T, T)
            logits = logits + torch.einsum("bkts,bhkts->bhts", p.to(extra.dtype), extra).float()
            # Penalties over causal pairs: entropy per pair (few types per pair) and
            # usage balance on the batch mean (no type carries everything).
            soft = p                                                        # the sample that routed (hard at evaluation)
            m = causal[None, None].to(soft.dtype)
            n_pairs = m.sum() * B
            ent = -(soft * torch.log(soft + 1e-9)).sum(1)                   # (B, T, T)
            pair_entropy = (ent * m[:, 0]).sum() / n_pairs
            usage = (soft * m).sum((0, 2, 3)) / n_pairs                     # (K,)
            balance = math.log(self.types.K) + (usage * torch.log(usage + 1e-9)).sum()
            ctx.aux.append(pair_entropy + balance)
            ctx.usage.append(usage.detach())
            ctx.confidence.append(((soft.max(1).values * m[:, 0]).sum() / n_pairs).detach())
            if ctx.want_types:
                ctx.types.append(soft.detach() if not ctx.hard else p.detach())
        logits = (logits * scale).masked_fill(~causal, float("-inf"))
        att = torch.softmax(logits, dim=-1)
        if ctx.want_attn:
            ctx.attn.append(att.detach())
        y = att.to(v.dtype) @ v                                          # (B, h, T, hd)
        heads_off = [hh for (ll, hh) in ctx.ablate_heads if ll == ctx.layer]
        if heads_off:
            y = y.clone()
            y[:, heads_off] = 0.0
        return y.transpose(1, 2).reshape(B, T, d)

    def forward(self, x: torch.Tensor, ctx: Fwd | None = None) -> torch.Tensor:
        x = x + self.proj(self.attention(x, ctx))
        if ctx is not None and ctx.layer in ctx.ablate_ffn:
            return x
        return x + self.fc2(F.gelu(self.fc(self.ln2(x)), approximate="tanh"))


class GPT(nn.Module):
    """The block under test; ``frozen_rows`` are B3's entity rows; ``types_k > 1``
    is B4. ``tau`` is the router temperature the training loop sets each step;
    ``ablate`` (a :class:`Fwd`) is what an analysis pass asks for and is read
    by every forward until cleared, so ``generate`` needs no new arguments."""

    def __init__(self, cfg: ModelConfig, vocab: int, types_k: int = 1, types_rank: int = 16):
        super().__init__()
        self.cfg = cfg
        self.types_k = types_k
        self.wte = nn.Embedding(vocab, cfg.d_model)
        self.wpe = nn.Embedding(cfg.max_len, cfg.d_model)
        self.blocks = nn.ModuleList(Block(cfg.d_model, cfg.n_heads, cfg.d_ff, types_k, types_rank) for _ in range(cfg.n_layers))
        self.ln_f = nn.LayerNorm(cfg.d_model)
        self.frozen_rows: list[int] = []
        self.tau = 1.0
        self.ablate: Fwd | None = None
        self.last: Fwd | None = None
        self.apply(self._init)

    @staticmethod
    def _init(m: nn.Module) -> None:
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, 0.0, 0.02)

    def set_entity_rows(self, rows: dict[int, np.ndarray], freeze: bool) -> None:
        with torch.no_grad():
            for i, v in rows.items():
                self.wte.weight[i] = torch.as_tensor(v, dtype=self.wte.weight.dtype)
        if freeze:
            self.frozen_rows = sorted(rows)
            mask = torch.ones(self.wte.weight.shape[0], 1)
            mask[self.frozen_rows] = 0.0
            self.register_buffer("row_mask", mask)
            self.wte.weight.register_hook(lambda g: g * self.row_mask.to(g.device, g.dtype))

    def forward(self, idx: torch.Tensor, residuals: bool = False, ctx: Fwd | None = None):
        B, T = idx.shape
        x = self.wte(idx) + self.wpe(torch.arange(T, device=idx.device))
        res = [x] if residuals else None
        if ctx is None and self.ablate is not None:
            a = self.ablate
            ctx = Fwd(a.tau, a.hard, a.ablate_heads, a.ablate_ffn, a.want_attn, a.want_types, a.noise)
        if ctx is None and self.types_k > 1:
            ctx = Fwd(tau=self.tau, hard=not self.training)
        if ctx is not None:
            ctx.layer = 0
        for i, b in enumerate(self.blocks):
            if ctx is not None:
                ctx.layer = i
            x = b(x, ctx)
            if residuals:
                res.append(x)
        logits = self.ln_f(x) @ self.wte.weight.T     # tied head
        self.last = ctx
        return logits, res

    def aux_loss(self) -> torch.Tensor | None:
        """B4's penalties summed over layers from the last forward (``None`` for other blocks)."""
        if self.last is None or not self.last.aux:
            return None
        return torch.stack(self.last.aux).sum()

    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ---------------------------------------------------------------- data

def pack(tok: Tokenizer, lines: list[str]) -> np.ndarray:
    """One stream: every line's tokens followed by ``<eos>``."""
    eos = tok.index[EOS]
    out: list[int] = []
    for ln in lines:
        out.extend(tok.encode(ln))
        out.append(eos)
    return np.asarray(out, dtype=np.int64)


def batches(stream: np.ndarray, seq_len: int, batch: int, seed: int):
    """Random windows of the stream, forever; seeded."""
    rng = np.random.default_rng(seed)
    n = len(stream) - seq_len - 1
    while True:
        starts = rng.integers(0, n, size=batch)
        x = np.stack([stream[s: s + seq_len] for s in starts])
        y = np.stack([stream[s + 1: s + seq_len + 1] for s in starts])
        yield torch.from_numpy(x), torch.from_numpy(y)


# ---------------------------------------------------------------- generation

@torch.no_grad()
def generate(model: GPT, tok: Tokenizer, prompts: list[str], device, max_new: int = 8, batch: int = 512,
             want_residuals: bool = False) -> tuple[list[str], list[float], np.ndarray | None]:
    """Greedy continuations of ``prompts`` (grouped by length so no padding is needed),
    the entropy (bits) of the first-token distribution, and optionally the
    residual stream at the prompt's last token, ``(n, L+1, d)``."""
    model.eval()
    stop = {tok.index[NL], tok.index[EOS]}
    enc = [tok.encode(p) for p in prompts]
    outs: list[str | None] = [None] * len(prompts)
    ents = [0.0] * len(prompts)
    res: list[np.ndarray | None] = [None] * len(prompts)
    by_len: dict[int, list[int]] = {}
    for i, ids in enumerate(enc):
        by_len.setdefault(len(ids), []).append(i)
    for L, idxs in by_len.items():
        for start in range(0, len(idxs), batch):
            chunk = idxs[start: start + batch]
            x = torch.tensor([enc[i] for i in chunk], device=device)
            done = torch.zeros(len(chunk), dtype=torch.bool, device=device)
            gen = [[] for _ in chunk]
            for step in range(max_new):
                logits, r = model(x, residuals=(want_residuals and step == 0))
                last = logits[:, -1, :].float()
                if step == 0:
                    p = torch.softmax(last, -1)
                    e = -(p * torch.log2(p + 1e-12)).sum(-1)
                    for j, i in enumerate(chunk):
                        ents[i] = float(e[j])
                    if want_residuals:
                        stack = torch.stack([t[:, -1, :] for t in r], 1).float().cpu().numpy()
                        for j, i in enumerate(chunk):
                            res[i] = stack[j]
                nxt = last.argmax(-1)
                for j in range(len(chunk)):
                    if not done[j]:
                        if int(nxt[j]) in stop:
                            done[j] = True      # the stop token ends the line and is not part of it
                        else:
                            gen[j].append(int(nxt[j]))
                if bool(done.all()):
                    break
                x = torch.cat([x, nxt[:, None]], 1)
            for j, i in enumerate(chunk):
                outs[i] = tok.decode(gen[j])
    model.train()
    R = np.stack(res) if want_residuals else None
    return outs, ents, R


# ---------------------------------------------------------------- evaluation

def _rate(matrix: dict, row: str, col: str) -> float | None:
    r = matrix["rows"].get(row)
    if not r:
        return None
    n = sum(r.values())
    return round(r[col] / n, 4) if n else None


@torch.no_grad()
def type_stats(model: GPT, x: torch.Tensor) -> dict:
    """B4 at a checkpoint: per layer, the batch-mean type usage of the soft,
    noiseless router at the current temperature over the causal pairs of
    ``x``, the mean confidence ``max_k p_k``, and the usage of the hard
    (argmax) assignment; ``max_share_hard`` is the largest share any type
    carries in any layer — the collapse number of addendum §4."""
    ctx = Fwd(tau=model.tau, hard=False, noise=False)
    model(x, ctx=ctx)
    layers = [{"layer": i, "usage": [round(float(u), 4) for u in usage], "confidence": round(float(conf), 4)}
              for i, (usage, conf) in enumerate(zip(ctx.usage, ctx.confidence))]
    ctx_h = Fwd(hard=True)
    model(x, ctx=ctx_h)
    for i, usage in enumerate(ctx_h.usage):
        layers[i]["usage_hard"] = [round(float(u), 4) for u in usage]
    return {"layers": layers, "max_share_hard": round(max(max(l["usage_hard"]) for l in layers), 4),
            "confidence": round(sum(l["confidence"] for l in layers) / len(layers), 4)}


def quick_eval(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], cfg: TrainConfig, device, seed: int) -> dict:
    """The checkpoint numbers: held-out dense / sparse / absent-held-out
    accuracy and act shares on a seeded subset, and the inversion curve
    point (§6.4) — context reliance under conflict, per split."""
    rng = np.random.default_rng(seed)
    prim = evals["primary"]
    groups = {
        "dense-real": [it for it in prim if it["class"] == "dense-real"],
        "sparse-real": [it for it in prim if it["class"] == "sparse-real"],
        "absent-held-out": [it for it in prim if it["class"].startswith("absent") and it["exposure"] == "held-out"],
        "absent-trained": [it for it in prim if it["class"].startswith("absent") and it["exposure"] != "held-out"],
    }
    chosen: list[dict] = []
    for g in groups.values():
        chosen += [g[i] for i in rng.permutation(len(g))[: cfg.ckpt_items]]
    outs, _, _ = generate(model, tok, [it["prompt"] for it in chosen], device, cfg.max_new)
    outputs = {it["id"]: o for it, o in zip(chosen, outs)}
    m = acts.confusion(chosen, outputs)
    inv = evals["inversion"]
    by_var: dict[tuple[str, str], list[dict]] = {}
    for it in inv:
        by_var.setdefault((it["split"], it["context_kind"]), []).append(it)
    inv_chosen = []
    for k, g in by_var.items():
        inv_chosen += [g[i] for i in rng.permutation(len(g))[: cfg.ckpt_items]]
    outs, _, _ = generate(model, tok, [it["prompt"] for it in inv_chosen], device, cfg.max_new)
    inversion: dict[str, dict[str, float]] = {}
    tally: dict[tuple[str, str], Counter] = {}
    for it, o in zip(inv_chosen, outs):
        a = acts.parse(o)
        c = tally.setdefault((it["split"], it["context_kind"]), Counter())
        c["n"] += 1
        if a.kind == "ANSWER":
            if a.values[0] in it["gold"]:
                c["parametric"] += 1
            if it["context_value"] and a.values[0] == it["context_value"]:
                c["context"] += 1
    for (split, kind), c in sorted(tally.items()):
        inversion[f"{split}/{kind}"] = {"gold": round(c["parametric"] / c["n"], 4),
                                        "context": round(c["context"] / c["n"], 4) if kind != "none" else None,
                                        "n": c["n"]}
    return {
        "dense_correct": _rate(m, "dense-real", "ANSWER-correct"),
        "read_context_only": (inversion.get("C-only-qa/support") or {}).get("gold"),
        "sparse_correct": _rate(m, "sparse-real", "ANSWER-correct"),
        "sparse_undefined": _rate(m, "sparse-real", "UNDEFINED"),
        "absent_held_out_undefined": {r: _rate(m, r, "UNDEFINED") for r in m["rows"] if r.endswith("held-out")},
        "absent_held_out_wrong": {r: _rate(m, r, "ANSWER-wrong") for r in m["rows"] if r.endswith("held-out")},
        "absent_trained_undefined": {r: _rate(m, r, "UNDEFINED") for r in m["rows"] if r.endswith("trained")},
        "malformed": {r: _rate(m, r, "malformed") for r in m["rows"]},
        "inversion": inversion,
    }


def full_eval(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], cfg: TrainConfig, device, out: Path,
              world_dir: Path | None = None) -> dict:
    """Every eval set scored, the probe on the balanced primary subset, the authority
    tables; with ``world_dir``, the §5 typed instruments too (``typed.json``)."""
    (out / "outputs").mkdir(parents=True, exist_ok=True)
    report: dict = {"confusion": {}, "secondary_by_kind": {}}
    all_outputs: dict[str, dict[str, str]] = {}
    for name in [n for n in evals if n != "inversion"]:     # primary, secondary, trained, and v1's primary_seen
        items = evals[name]
        outs, ents, _ = generate(model, tok, [it["prompt"] for it in items], device, cfg.max_new)
        outputs = {it["id"]: o for it, o in zip(items, outs)}
        all_outputs[name] = outputs
        with (out / "outputs" / f"{name}.jsonl").open("w") as f:
            for it, o, e in zip(items, outs, ents):
                f.write(json.dumps({"id": it["id"], "output": o, "entropy": round(e, 4)}) + "\n")
        report["confusion"][name] = acts.confusion(items, outputs)
        if name == "trained" and any(it.get("context_only") for it in items):     # v2
            for label, want in (("trained_free", False), ("trained_context_only", True)):
                sub = [it for it in items if bool(it.get("context_only")) is want]
                report["confusion"][label] = acts.confusion(sub, outputs)
        if name == "secondary":
            for kind in ("calls", "reached_by"):
                sub = [it for it in items if it["kind"] == kind]
                report["secondary_by_kind"][kind] = acts.confusion(sub, outputs)
    # §6.5: sparse-real accuracy by stem distance to the nearest dense-real; module inference.
    prim = evals["primary"]
    by_dist: dict[int, Counter] = {}
    for it in prim:
        if it["class"] == "sparse-real":
            g = acts.grade(acts.parse(all_outputs["primary"][it["id"]]), it)
            c = by_dist.setdefault(it["nearest_dense_distance"], Counter())
            c["n"] += 1
            c[g.column] += 1
    report["sparse_by_nearest_dense_distance"] = {str(d): dict(c) for d, c in sorted(by_dist.items())}
    # Probe + authority on the balanced primary subset.
    idx, y = probe.balanced_indices(prim, cfg.seed, cfg.probe_per_class)
    chosen = [prim[i] for i in idx]
    outs, ents, R = generate(model, tok, [it["prompt"] for it in chosen], device, cfg.max_new, want_residuals=True)
    np.savez_compressed(out / "residuals.npz", residuals=R.astype(np.float16), ids=np.array([it["id"] for it in chosen]),
                        classes=np.array(y))
    pl = probe.probe_layers(R, y, seed=cfg.seed)
    cols = [acts.grade(acts.parse(o), it).column for it, o in zip(chosen, outs)]
    te = pl["test_indices"]
    report["probe"] = {k: v for k, v in pl.items() if k not in ("test_indices", "test_predictions")}
    report["authority"] = probe.authority([y[i] for i in te], pl["test_predictions"], [cols[i] for i in te], [ents[i] for i in te])
    # Inversion, in full.
    inv = evals["inversion"]
    outs, _, _ = generate(model, tok, [it["prompt"] for it in inv], device, cfg.max_new)
    with (out / "outputs" / "inversion.jsonl").open("w") as f:
        for it, o in zip(inv, outs):
            f.write(json.dumps({"id": it["id"], "output": o}) + "\n")
    tally: dict[str, Counter] = {}
    for it, o in zip(inv, outs):
        a = acts.parse(o)
        c = tally.setdefault(f"{it['split']}/{it['context_kind']}", Counter())
        c["n"] += 1
        if a.kind == "ANSWER":
            c["gold"] += a.values[0] in it["gold"]
            c["context"] += bool(it["context_value"]) and a.values[0] == it["context_value"]
    report["inversion"] = {k: {"gold": round(c["gold"] / c["n"], 4), "context": round(c["context"] / c["n"], 4), "n": c["n"]}
                           for k, c in sorted(tally.items())}
    # The §5 instruments (addendum 2026-09-07) on these weights: typed.json beside the report,
    # for B4 and for its paired control alike (the untyped halves), when the world is at hand.
    if world_dir is not None:
        from . import typed, world as W
        try:
            rep = typed.analyze(model, tok, W.read(world_dir), evals, all_outputs, device, cfg, seed=cfg.seed)
            (out / "typed.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
            (out / "typed.md").write_text(typed.render(rep))
        except Exception as e:      # an instrument's failure must not lose the cell; it is recorded
            (out / "typed.error").write_text(repr(e) + "\n")
    return report


# ---------------------------------------------------------------- the run

def load_evals(world_dir: Path) -> dict[str, list[dict]]:
    """Every eval set the world wrote (the four of v0; ``primary_seen`` under hold-out)."""
    return {p.stem: acts.read_jsonl(p) for p in sorted((world_dir / "eval").glob("*.jsonl"))}


def check_prompt_tokens(tok: Tokenizer, stream: np.ndarray, evals: dict[str, list[dict]], allow: bool) -> dict[str, dict[str, int]]:
    """Every eval set's prompts against the training stream's token ids; the
    tokens an absent name encodes to (its dedicated token under B2/B3, its
    stems under B1) are exempt — the name is the thing under test and is
    unseen by design; everything around it must be trained. Refuses with
    :class:`UntrainedPromptTokens` unless ``allow``; returns what it found,
    for the manifest."""
    trained = set(np.unique(stream).tolist())
    exempt = {i for n, kind in tok.entities.items() if kind == "absent" for i in tok.encode(n)}
    found = {}
    for name, items in evals.items():
        bad = untrained_prompt_tokens(tok, trained, [it["prompt"] for it in items], exempt)
        if bad:
            found[name] = dict(bad)
    if found and not allow:
        raise UntrainedPromptTokens(f"eval prompts carry tokens the {tok.block} training stream never contains: {found}")
    return found


def run(world_dir: Path, out: Path, cfg: TrainConfig, device: str | None = None, log=print) -> dict:
    """Train one cell and write its records under ``out``; returns the manifest."""
    if cfg.arm not in ARMS:
        raise ValueError(f"unknown arm {cfg.arm!r}")
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    out.mkdir(parents=True, exist_ok=True)
    manifest_w = json.loads((world_dir / "manifest.json").read_text())
    ents = json.loads((world_dir / "entities.json").read_text())
    tok = Tokenizer.build(cfg.block, ents)
    lines = (world_dir / "corpus" / f"{cfg.arm}.txt").read_text().splitlines()
    stream = pack(tok, lines)
    evals = load_evals(world_dir)
    untrained = check_prompt_tokens(tok, stream, evals, cfg.allow_untrained_prompt_tokens)
    if cfg.max_epochs:
        cfg = replace(cfg, steps=max(1, math.ceil(cfg.max_epochs * len(stream) / (cfg.batch * cfg.seq_len))))
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    mcfg = CONFIGS[cfg.model]
    model = GPT(mcfg, len(tok), types_k=(cfg.types_k if cfg.block == "B4" else 1), types_rank=cfg.types_rank)
    if tok.entity_ids:
        names = sorted(tok.entity_ids)
        vecs = entity_vectors(names, mcfg.d_model, cfg.seed)
        model.set_entity_rows({tok.entity_ids[n]: vecs[i] for i, n in enumerate(names)}, freeze=(cfg.block == "B3"))
    model.to(device)
    decay = [p for n, p in model.named_parameters() if p.dim() >= 2 and n != "wte.weight"]
    no_decay = [p for n, p in model.named_parameters() if p.dim() < 2]
    # Embedding rows: B3's frozen rows must not decay toward zero; the simplest
    # honest rule is no weight decay on the embedding in any block.
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": cfg.weight_decay},
                             {"params": no_decay + [model.wte.weight], "weight_decay": 0.0}],
                            lr=cfg.lr, betas=(0.9, 0.95), fused=(device == "cuda"))

    def lr_at(step: int) -> float:
        if step < cfg.warmup:
            return cfg.lr * (step + 1) / cfg.warmup
        t = (step - cfg.warmup) / max(1, cfg.steps - cfg.warmup)
        return cfg.lr * (cfg.min_lr_ratio + (1 - cfg.min_lr_ratio) * 0.5 * (1 + math.cos(math.pi * t)))

    use_bf16 = cfg.precision == "bf16" and device == "cuda"
    data = batches(stream, cfg.seq_len, cfg.batch, cfg.seed)
    losses: list[tuple[int, float]] = []
    checkpoints: list[dict] = []
    tokens_per_step = cfg.batch * cfg.seq_len
    t0 = time.time()
    stopped_at = None
    model.train()
    last_step = min(cfg.steps, cfg.stop_at_step) if cfg.stop_at_step else cfg.steps
    typed = cfg.block == "B4" and cfg.types_k > 1
    for step in range(last_step):
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        if typed:
            t0_, t1_ = cfg.gumbel_tau
            model.tau = t0_ + (t1_ - t0_) * step / max(1, cfg.steps - 1)
        x, y = next(data)
        x, y = x.to(device), y.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
            logits, _ = model(x)
            lm_loss = F.cross_entropy(logits.view(-1, logits.shape[-1]).float(), y.view(-1))
            aux = model.aux_loss()
            loss = lm_loss + cfg.types_lambda * aux if aux is not None else lm_loss
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        opt.step()
        if step % 10 == 0 or step == last_step - 1:
            losses.append((step, round(lm_loss.item(), 4)))
        if (step + 1) in cfg.full_eval_at and step + 1 != last_step:
            # The full read at a named step (the addendum's reading-phase column), whether
            # or not it is a checkpoint step (2026-09-07: 2,200 is not a multiple of 300).
            at = out / f"step-{step + 1}"
            rep = full_eval(model, tok, evals, cfg, device, at, world_dir)
            (at / "report.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
            torch.save(model.state_dict(), at / "model.pt")
            model.train()
        if (step + 1) % cfg.ckpt_every == 0 or step == last_step - 1:
            elapsed = time.time() - t0
            q = quick_eval(model, tok, evals, cfg, device, cfg.seed + step)
            q.update({"step": step + 1, "loss": round(lm_loss.item(), 4), "elapsed_s": round(elapsed, 1),
                      "epochs": round((step + 1) * tokens_per_step / len(stream), 2)})
            if typed:
                q["types"] = type_stats(model, x)
                q["aux"] = round(float(aux.detach()), 4)
                q["tau"] = round(model.tau, 4)
            checkpoints.append(q)
            log(json.dumps({k: q[k] for k in ("step", "epochs", "loss", "dense_correct", "sparse_correct",
                                              "sparse_undefined", "absent_held_out_undefined", "elapsed_s")}))
            if cfg.save_weights_every and (step + 1) % cfg.save_weights_every == 0:
                (out / "ckpt").mkdir(exist_ok=True)
                torch.save(model.state_dict(), out / "ckpt" / f"step-{step + 1}.pt")
            if cfg.stop_at_target and (q.get(cfg.target_measure) or 0) >= cfg.target_dense:
                stopped_at = step + 1
                break
    train_s = time.time() - t0
    steps_done = stopped_at or last_step
    t1 = time.time()
    report = full_eval(model, tok, evals, cfg, device, out, world_dir)
    eval_s = time.time() - t1
    torch.save(model.state_dict(), out / "model.pt")
    manifest = {
        "config": asdict(cfg),
        "model_config": asdict(mcfg),
        "params": model.n_params(),
        "vocab": len(tok),
        "frozen_rows": len(model.frozen_rows),
        "world_hash": manifest_w["world_hash"],
        "corpus_hash": manifest_w["corpus_hash"][cfg.arm],
        "stream_tokens": int(len(stream)),
        "eval_prompt_tokens_untrained": untrained,
        "steps_done": steps_done,
        "stopped_at_target": stopped_at,
        "epochs": round(steps_done * tokens_per_step / len(stream), 2),
        "tokens_seen": steps_done * tokens_per_step,
        "tokens_per_s": round(steps_done * tokens_per_step / train_s, 1),
        "train_s": round(train_s, 1),
        "eval_s": round(eval_s, 1),
        "device": torch.cuda.get_device_name(0) if device == "cuda" else "cpu",
        "torch": str(torch.__version__),
        "precision": "bf16" if use_bf16 else "fp32",
        "loss": losses,
        "checkpoints": checkpoints,
        "final": {
            "dense_correct": _rate(report["confusion"]["primary"], "dense-real", "ANSWER-correct"),
            "sparse_correct": _rate(report["confusion"]["primary"], "sparse-real", "ANSWER-correct"),
            "probe_best_test": report["probe"]["best_test"],
            "probe_chance": report["probe"]["chance"],
            "mi_act_probed": report["authority"]["mi_act_probed"],
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return manifest


def load_cell(run_dir: Path, world_dir: Path, weights: Path | None = None, device: str | None = None) -> tuple[GPT, Tokenizer, TrainConfig]:
    """A finished cell's model (its final ``model.pt``, or ``weights`` — a
    ``ckpt/step-N.pt`` or ``step-N/model.pt``), the tokenizer of the build it
    trained with (v0 / v1 / v2 vocabularies are told apart by the embedding's
    row count) and its config. The analysis modules start here."""
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    man = json.loads((run_dir / "manifest.json").read_text())
    cfg = TrainConfig(**man["config"])
    ents = json.loads((world_dir / "entities.json").read_text())
    state = torch.load(weights or (run_dir / "model.pt"), map_location=device)
    n_rows = state["wte.weight"].shape[0]
    for v1_words, later_words in ((False, False), (True, False), (True, True)):     # v0, v1, v2 builds
        tok = Tokenizer.build(cfg.block, ents, v1_words=v1_words, later_words=later_words)
        if n_rows == len(tok):
            break
    else:
        raise ValueError(f"vocabulary of {run_dir.name} ({n_rows}) matches no build (v0/v1/v2)")
    model = GPT(CONFIGS[cfg.model], len(tok), types_k=(cfg.types_k if cfg.block == "B4" else 1), types_rank=cfg.types_rank)
    model.load_state_dict({k: v for k, v in state.items() if k != "row_mask"}, strict=False)
    model.to(device)
    model.eval()
    return model, tok, cfg


def reevaluate(world_dir: Path, run_dir: Path, out: Path, device: str | None = None, weights: Path | None = None) -> dict:
    """Read a finished cell's weights against ``world_dir``'s eval sets, into ``out``.

    For eval sets that changed after the cell ran (the §6.4 prompts' separator,
    2026-09-05 night; a v1 world's new secondary rows) the cell is not
    retrained: its outputs are re-read on the new items. The world's corpus
    hash for the cell's arm must equal the one the cell trained on, or this
    refuses. The manifest written is the cell's with ``reevaluated_from``,
    the new ``final`` and no checkpoints (those were read with the old prompts).
    ``weights`` reads a saved checkpoint (``ckpt/step-N.pt``) instead of the
    final ``model.pt`` — a step's full read after the fact.
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    man = json.loads((run_dir / "manifest.json").read_text())
    cfg = TrainConfig(**man["config"])
    manifest_w = json.loads((world_dir / "manifest.json").read_text())
    if manifest_w["corpus_hash"][cfg.arm] != man["corpus_hash"]:
        raise ValueError(f"{run_dir.name} trained on corpus {man['corpus_hash'][:12]}…, not {world_dir.name}'s "
                         f"{manifest_w['corpus_hash'][cfg.arm][:12]}… for arm {cfg.arm}")
    model, tok, cfg = load_cell(run_dir, world_dir, weights, device=device)
    evals = load_evals(world_dir)
    stream = pack(tok, (world_dir / "corpus" / f"{cfg.arm}.txt").read_text().splitlines())
    untrained = check_prompt_tokens(tok, stream, evals, cfg.allow_untrained_prompt_tokens)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = full_eval(model, tok, evals, cfg, device, out, world_dir)
    prim = report["confusion"]["primary"]
    man = dict(man, reevaluated_from=str(run_dir), reevaluated_weights=str(weights) if weights else None,
               world_hash=manifest_w["world_hash"], eval_s=round(time.time() - t0, 1),
               checkpoints=[], vocab=len(tok), eval_prompt_tokens_untrained=untrained,
               final={"dense_correct": _rate(prim, "dense-real", "ANSWER-correct"),
                      "sparse_correct": _rate(prim, "sparse-real", "ANSWER-correct"),
                      "probe_best_test": report["probe"]["best_test"], "probe_chance": report["probe"]["chance"],
                      "mi_act_probed": report["authority"]["mi_act_probed"]})
    (out / "manifest.json").write_text(json.dumps(man, indent=2, sort_keys=True) + "\n")
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return man
