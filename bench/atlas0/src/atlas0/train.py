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
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from . import acts, probe
from .refmodel import CONFIGS, ModelConfig
from .tokens import BOS, EOS, NL, Tokenizer, entity_vectors
from .world import ARMS


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
    target_dense: float = 0.95      # §5: dense-real held-out accuracy the budget is calibrated to
    stop_at_target: bool = False    # calibration mode (step 3)
    max_new: int = 8


class Block(nn.Module):
    def __init__(self, d: int, h: int, ff: int):
        super().__init__()
        self.ln1 = nn.LayerNorm(d)
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.ln2 = nn.LayerNorm(d)
        self.fc = nn.Linear(d, ff, bias=False)
        self.fc2 = nn.Linear(ff, d, bias=False)
        self.h = h

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(d, dim=-1)
        q = q.view(B, T, self.h, d // self.h).transpose(1, 2)
        k = k.view(B, T, self.h, d // self.h).transpose(1, 2)
        v = v.view(B, T, self.h, d // self.h).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(y.transpose(1, 2).reshape(B, T, d))
        return x + self.fc2(F.gelu(self.fc(self.ln2(x)), approximate="tanh"))


class GPT(nn.Module):
    """The block under test; ``frozen_rows`` are B3's entity rows."""

    def __init__(self, cfg: ModelConfig, vocab: int):
        super().__init__()
        self.cfg = cfg
        self.wte = nn.Embedding(vocab, cfg.d_model)
        self.wpe = nn.Embedding(cfg.max_len, cfg.d_model)
        self.blocks = nn.ModuleList(Block(cfg.d_model, cfg.n_heads, cfg.d_ff) for _ in range(cfg.n_layers))
        self.ln_f = nn.LayerNorm(cfg.d_model)
        self.frozen_rows: list[int] = []
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

    def forward(self, idx: torch.Tensor, residuals: bool = False):
        B, T = idx.shape
        x = self.wte(idx) + self.wpe(torch.arange(T, device=idx.device))
        res = [x] if residuals else None
        for b in self.blocks:
            x = b(x)
            if residuals:
                res.append(x)
        logits = self.ln_f(x) @ self.wte.weight.T     # tied head
        return logits, res

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
        "absent-trained": [it for it in prim if it["class"].startswith("absent") and it["exposure"] == "trained"],
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
        "sparse_correct": _rate(m, "sparse-real", "ANSWER-correct"),
        "sparse_undefined": _rate(m, "sparse-real", "UNDEFINED"),
        "absent_held_out_undefined": {r: _rate(m, r, "UNDEFINED") for r in m["rows"] if r.endswith("held-out")},
        "absent_held_out_wrong": {r: _rate(m, r, "ANSWER-wrong") for r in m["rows"] if r.endswith("held-out")},
        "absent_trained_undefined": {r: _rate(m, r, "UNDEFINED") for r in m["rows"] if r.endswith("trained")},
        "malformed": {r: _rate(m, r, "malformed") for r in m["rows"]},
        "inversion": inversion,
    }


def full_eval(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], cfg: TrainConfig, device, out: Path) -> dict:
    """Every eval set scored, the probe on the balanced primary subset, the authority tables."""
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
    return report


# ---------------------------------------------------------------- the run

def load_evals(world_dir: Path) -> dict[str, list[dict]]:
    """Every eval set the world wrote (the four of v0; ``primary_seen`` under hold-out)."""
    return {p.stem: acts.read_jsonl(p) for p in sorted((world_dir / "eval").glob("*.jsonl"))}


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
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    mcfg = CONFIGS[cfg.model]
    model = GPT(mcfg, len(tok))
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
    for step in range(cfg.steps):
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        x, y = next(data)
        x, y = x.to(device), y.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
            logits, _ = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.shape[-1]).float(), y.view(-1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        opt.step()
        if step % 10 == 0 or step == cfg.steps - 1:
            losses.append((step, round(loss.item(), 4)))
        if (step + 1) % cfg.ckpt_every == 0 or step == cfg.steps - 1:
            elapsed = time.time() - t0
            q = quick_eval(model, tok, evals, cfg, device, cfg.seed + step)
            q.update({"step": step + 1, "loss": round(loss.item(), 4), "elapsed_s": round(elapsed, 1),
                      "epochs": round((step + 1) * tokens_per_step / len(stream), 2)})
            checkpoints.append(q)
            log(json.dumps({k: q[k] for k in ("step", "epochs", "loss", "dense_correct", "sparse_correct",
                                              "sparse_undefined", "absent_held_out_undefined", "elapsed_s")}))
            if cfg.stop_at_target and (q["dense_correct"] or 0) >= cfg.target_dense:
                stopped_at = step + 1
                break
    train_s = time.time() - t0
    steps_done = stopped_at or cfg.steps
    t1 = time.time()
    report = full_eval(model, tok, evals, cfg, device, out)
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

