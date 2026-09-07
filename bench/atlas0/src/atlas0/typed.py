"""The §5 instruments of the 2026-09-07 addendum (B4, typed relations), attribution first.

Every reading is a number about **B** only after **W**, **A**, **T**, **P**
and **λ** (the pressure) have been checked for it. What is measured, per
cell, on the weights the cell saved (in the container at each full read,
or from the CLI on a re-read):

- **§5.1 type discovery** — for a sample of the world's facts, rendered
  as the corpus renders them, the router's assignment at the attention
  from the later-mentioned entity's last token to the earlier one's, per
  layer, against the true relation: purity and normalised mutual
  information; the usage histogram; the confidence by relation; the
  same partition scored against *direction* (which argument came first)
  and against the *template* (the sentence shape), so a partition that
  is the surface form is seen as one; and the assignment on the
  held-out phrasing beside a trained one.
- **§5.2 sibling pull by type** — the sibling share of wrong answers on
  absent-near names (from the cell's own matrix), and the cosine
  between the last-layer representations of two real symbols in
  different modules that share a callee: overall, and after projecting
  through each operator ``R_k`` — with random-pair and same-module
  baselines per type.
- **§5.3 relation-absence as a computed state** — per absent (and real)
  query, the typed signal ``max_j p_k*(i, j) · ā(i, j)`` from the answer
  slot to the name for the queried relation's discovered type ``k*``,
  beside the act the cell produced; by row, with the AUC of the signal
  for ``UNDEFINED``.
- **§5.6** — per layer and type, the singular values of ``R_k − I`` and
  what the type routes (its share by relation and direction).

§5.4 (the route-competition curve) and §5.5 (the loss delta) are read
from the manifests by ``atlas0 report``. Blocks without an inventory
(B1, the paired control) get the untyped halves — the sibling cosine,
the absence rows — in the same file, so the pair is read side by side.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

from . import acts
from .tokens import Tokenizer
from .train import GPT, Fwd
from .world import QUERY_KINDS, Fact, World, query_line

ABSENCE_ROWS = ("absent-near/pair", "absent-near/lines", "absent-near/held-out",
                "absent-far/pair", "absent-far/lines", "absent-far/held-out",
                "sparse-real/without", "sparse-real/with", "dense-real/without", "dense-real/with", "mid/without", "mid/with")


# ---------------------------------------------------------------- batched readouts

def _span(tok: Tokenizer, ids: list[int], name: str) -> list[int]:
    sub = tok.encode(name)
    for i in range(len(ids) - len(sub) + 1):
        if ids[i: i + len(sub)] == sub:
            return list(range(i, i + len(sub)))
    return []


@torch.no_grad()
def pair_readout(model: GPT, tok: Tokenizer, seqs: list[list[int]], pairs: list[tuple[int, int]], device,
                 tau: float, batch: int = 256) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray]:
    """For sequence ``n`` and its ``(i, j)`` pair: per layer the soft, noiseless
    router ``p(i, j)`` ``(n, L, K)`` (``None`` without an inventory), the mean-head
    attention ``ā(i, j)`` ``(n, L)``, and the residual after the last block at
    ``i`` ``(n, d)``. Sequences are grouped by length so no padding is needed."""
    model.eval()
    L = model.cfg.n_layers
    K = model.types_k
    P = np.zeros((len(seqs), L, K), np.float32) if K > 1 else None
    A = np.zeros((len(seqs), L), np.float32)
    R = np.zeros((len(seqs), model.cfg.d_model), np.float32)
    by_len: dict[int, list[int]] = defaultdict(list)
    for n, s in enumerate(seqs):
        by_len[len(s)].append(n)
    for T, idxs in by_len.items():
        for start in range(0, len(idxs), batch):
            chunk = idxs[start: start + batch]
            x = torch.tensor([seqs[n] for n in chunk], device=device)
            ctx = Fwd(tau=tau, hard=False, noise=False, want_attn=True, want_types=(K > 1))
            _, res = model(x, residuals=True, ctx=ctx)
            ii = torch.tensor([pairs[n][0] for n in chunk], device=device)
            jj = torch.tensor([pairs[n][1] for n in chunk], device=device)
            b = torch.arange(len(chunk), device=device)
            for l in range(L):
                A[chunk, l] = ctx.attn[l][b, :, ii, jj].mean(1).float().cpu().numpy()
                if K > 1:
                    P[chunk, l] = ctx.types[l][b, :, ii, jj].float().cpu().numpy()
            R[chunk] = res[-1][b, ii].float().cpu().numpy()
    return P, A, R


def _partition_scores(types: np.ndarray, labels: list, K: int) -> dict:
    """Purity and NMI of ``types`` against ``labels``; the majority label per type."""
    n = len(labels)
    if n == 0:
        return {"purity": None, "nmi": None, "majority": {}}
    joint: dict[tuple[int, object], int] = Counter(zip(types.tolist(), labels))
    by_type: dict[int, Counter] = defaultdict(Counter)
    for (t, lab), c in joint.items():
        by_type[t][lab] += c
    purity = sum(max(c.values()) for c in by_type.values()) / n
    pt = Counter(types.tolist())
    pl = Counter(labels)
    mi = 0.0
    for (t, lab), c in joint.items():
        mi += c / n * math.log((c / n) / ((pt[t] / n) * (pl[lab] / n)))
    ht = -sum(c / n * math.log(c / n) for c in pt.values())
    hl = -sum(c / n * math.log(c / n) for c in pl.values())
    nmi = mi / math.sqrt(ht * hl) if ht > 0 and hl > 0 else 0.0
    return {"purity": round(purity, 4), "nmi": round(nmi, 4),
            "majority": {str(t): {"label": str(c.most_common(1)[0][0]), "share": round(c.most_common(1)[0][1] / sum(c.values()), 4),
                                  "n": sum(c.values())} for t, c in sorted(by_type.items())}}


# ---------------------------------------------------------------- §5.1 type discovery

def fact_samples(world: World, per_kind: int, seed: int) -> list[dict]:
    """A seeded sample of facts per relation, rendered as the corpus renders them,
    with the later entity (whose last token reads back) and the earlier one."""
    rng = np.random.default_rng(seed)
    out = []
    for kind in QUERY_KINDS:
        fs = [f for f in world.facts if f.kind == kind]
        for i in rng.permutation(len(fs))[:per_kind]:
            f = fs[i]
            text = f.render()
            a, b = f.args
            first, second = (a, b) if text.find(a) < text.find(b) else (b, a)
            # direction: the subject (a) first, or the object first
            out.append({"kind": kind, "template": f.template, "text": text, "earlier": first, "later": second,
                        "direction": "subject-first" if first == a else "object-first"})
    return out


def type_discovery(model: GPT, tok: Tokenizer, world: World, evals: dict[str, list[dict]], device, tau: float,
                   per_kind: int = 400, n_qa: int = 200, seed: int = 0) -> dict:
    samples = fact_samples(world, per_kind, seed)
    seqs, pairs, keep = [], [], []
    for s in samples:
        ids = tok.encode(s["text"])
        sp_e, sp_l = _span(tok, ids, s["earlier"]), _span(tok, ids, s["later"])
        if not sp_e or not sp_l:
            continue
        seqs.append(ids)
        pairs.append((sp_l[-1], sp_e[-1]))
        keep.append(s)
    # Packed QA: from the ANSWER slot to the context module (the reading route's pair).
    split = "C-only-qa" if any(it["split"] == "C-only-qa" for it in evals["inversion"]) else "C-only"
    qa = [it for it in evals["inversion"] if it["split"] == split and it["context_kind"] == "support"][:n_qa]
    qa_seqs, qa_pairs = [], []
    for it in qa:
        ids = tok.encode(it["prompt"]) + [tok.index["ANSWER"]]
        sp = _span(tok, ids, it["context_value"])
        if sp:
            qa_seqs.append(ids)
            qa_pairs.append((len(ids) - 1, sp[-1]))
    P, A, _ = pair_readout(model, tok, seqs, pairs, device, tau)
    Pq, Aq, _ = pair_readout(model, tok, qa_seqs, qa_pairs, device, tau) if qa_seqs else (None, None, None)
    L = model.cfg.n_layers
    K = model.types_k
    rep = {"n_facts": len(keep), "n_qa": len(qa_seqs), "layers": [], "K": K}
    if P is None:
        rep["attention_by_kind"] = [{k: round(float(A[[i for i, s in enumerate(keep) if s["kind"] == k], l].mean()), 4)
                                     for k in QUERY_KINDS} for l in range(L)]
        return rep
    kinds = [s["kind"] for s in keep]
    dirs = [s["direction"] for s in keep]
    kd = [f"{s['kind']}/{s['direction']}" for s in keep]
    tpl = [f"{s['kind']}/{s['template']}" for s in keep]
    best = None
    for l in range(L):
        t = P[:, l].argmax(1)
        conf = P[:, l].max(1)
        usage = np.bincount(t, minlength=K) / len(t)
        row = {
            "layer": l,
            "usage": [round(float(u), 4) for u in usage],
            "max_share": round(float(usage.max()), 4),
            "confidence_by_kind": {k: round(float(conf[[i for i, x in enumerate(kinds) if x == k]].mean()), 4) for k in QUERY_KINDS},
            "attention_by_kind": {k: round(float(A[[i for i, x in enumerate(kinds) if x == k], l].mean()), 4) for k in QUERY_KINDS},
            "vs_relation": _partition_scores(t, kinds, K),
            "vs_direction": _partition_scores(t, dirs, K),
            "vs_relation_direction": _partition_scores(t, kd, K),
            "vs_template": _partition_scores(t, tpl, K),
        }
        if Pq is not None:
            tq = Pq[:, l].argmax(1)
            row["qa_defined_in"] = {"usage": [round(float(u), 4) for u in np.bincount(tq, minlength=K) / len(tq)],
                                    "confidence": round(float(Pq[:, l].max(1).mean()), 4),
                                    "attention": round(float(Aq[:, l].mean()), 4)}
        rep["layers"].append(row)
        if best is None or row["vs_relation"]["nmi"] > best[0]:
            best = (row["vs_relation"]["nmi"], l)
    rep["best_layer"] = best[1]
    rep["best_nmi"] = best[0]
    rep["best_purity"] = rep["layers"][best[1]]["vs_relation"]["purity"]
    # The relation → type map at the best layer (the type most assigned to each relation).
    t = P[:, best[1]].argmax(1)
    rel_type = {}
    for k in QUERY_KINDS:
        c = Counter(int(x) for x, kk in zip(t, kinds) if kk == k)
        rel_type[k] = {"type": c.most_common(1)[0][0], "share": round(c.most_common(1)[0][1] / sum(c.values()), 4)} if c else None
    rep["relation_type"] = rel_type
    return rep


def phrasing_check(model: GPT, tok: Tokenizer, world: World, device, tau: float, n: int = 200, seed: int = 0) -> dict:
    """§5.1's check on **W**: the assignment from the answer slot to the name under
    a trained phrasing and under the held-out one; if purity against the
    relation drops on the held-out phrasing, the types were sentence shapes."""
    if model.types_k <= 1:
        return {}
    train_ph, held = world.config.phrasings()
    rng = np.random.default_rng(seed)
    syms = [s for s in world.symbols if s.qa_split == "eval" and s.cls in ("dense-real", "mid")]
    picks = [syms[i] for i in rng.permutation(len(syms))[:n]]
    out = {}
    for label, ph in (("trained", train_ph[0]), ("held-out", held)):
        seqs, pairs, kinds = [], [], []
        for s in picks:
            facts = world.facts_of(s.name)
            for kind in QUERY_KINDS:
                if kind != "defined_in" and not facts[kind]:
                    continue
                ids = tok.encode(query_line(kind, s.name, ph))
                sp = _span(tok, ids, s.name)
                if not sp:
                    continue
                seqs.append(ids)
                pairs.append((len(ids) - 1, sp[-1]))
                kinds.append(kind)
        P, _, _ = pair_readout(model, tok, seqs, pairs, device, tau)
        out[label] = {"n": len(seqs),
                      "layers": [{"layer": l, **{k: v for k, v in _partition_scores(P[:, l].argmax(1), kinds, model.types_k).items() if k != "majority"}}
                                 for l in range(model.cfg.n_layers)]}
    return out


# ---------------------------------------------------------------- §5.2 sibling pull by type

def shared_callee_pairs(world: World, n: int, seed: int) -> dict[str, list[tuple[str, str]]]:
    """``shared``: two real symbols in different modules that call the same
    symbol; ``random``: two real symbols in different modules with no common
    callee; ``same_module``: two in one module. ``n`` of each, seeded."""
    rng = np.random.default_rng(seed)
    callers: dict[str, set[str]] = defaultdict(set)
    callees: dict[str, set[str]] = defaultdict(set)
    for f in world.facts:
        if f.kind == "calls":
            callers[f.args[1]].add(f.args[0])
            callees[f.args[0]].add(f.args[1])
    module = {s.name: s.module for s in world.symbols}
    shared = set()
    for b, cs in callers.items():
        cs = sorted(cs)
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                if module[cs[i]] != module[cs[j]]:
                    shared.add((cs[i], cs[j]))
    shared = sorted(shared)
    names = sorted(module)
    random_pairs, same = [], []
    tries = 0
    while (len(random_pairs) < n or len(same) < n) and tries < 200000:
        tries += 1
        a, b = names[rng.integers(len(names))], names[rng.integers(len(names))]
        if a == b:
            continue
        if module[a] == module[b]:
            if len(same) < n:
                same.append((a, b))
        elif not (callees[a] & callees[b]) and len(random_pairs) < n:
            random_pairs.append((a, b))
    return {"shared": [shared[i] for i in rng.permutation(len(shared))[:n]], "random": random_pairs, "same_module": same}


@torch.no_grad()
def sibling_cosine(model: GPT, tok: Tokenizer, world: World, device, tau: float, n: int = 300, seed: int = 0) -> dict:
    groups = shared_callee_pairs(world, n, seed)
    names = sorted({x for ps in groups.values() for p in ps for x in p})
    seqs, pairs = [], []
    for nm in names:
        ids = tok.encode(query_line("defined_in", nm, 0))
        sp = _span(tok, ids, nm)
        seqs.append(ids)
        pairs.append((sp[-1], sp[-1]))
    _, _, R = pair_readout(model, tok, seqs, pairs, device, tau)
    rep_of = {nm: R[i] for i, nm in enumerate(names)}

    def cos(u, v):
        return float(u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9))

    out = {"n": {g: len(ps) for g, ps in groups.items()},
           "overall": {g: round(float(np.mean([cos(rep_of[a], rep_of[b]) for a, b in ps])), 4) for g, ps in groups.items()}}
    if model.types_k > 1:
        blk = model.blocks[-1]
        d = model.cfg.d_model
        h = blk.h
        hd = d // h
        Wq = blk.qkv.weight[:d].detach().float().cpu().numpy()          # (d, d): q = x @ Wq.T
        Rk = blk.types.operators().detach().float().cpu().numpy()      # (K, hd, hd)
        ln = blk.ln1
        g, bta = ln.weight.detach().float().cpu().numpy(), ln.bias.detach().float().cpu().numpy()

        def q_of(z):
            zn = (z - z.mean()) / math.sqrt(z.var() + 1e-5) * g + bta
            return (zn @ Wq.T).reshape(h, hd)

        per_type = {}
        for k in range(model.types_k):
            per_type[str(k)] = {}
            for gname, ps in groups.items():
                vals = []
                for a, b in ps:
                    qa = (q_of(rep_of[a]) @ Rk[k]).reshape(-1)
                    qb = (q_of(rep_of[b]) @ Rk[k]).reshape(-1)
                    vals.append(cos(qa, qb))
                per_type[str(k)][gname] = round(float(np.mean(vals)), 4)
        out["under_type"] = per_type
    return out


# ---------------------------------------------------------------- §5.3 relation-absence as a computed state

@torch.no_grad()
def absence_signal(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], outputs: dict[str, dict[str, str]], device,
                   tau: float, relation_type: dict | None, layer: int | None) -> dict:
    """Per query in the absence rows: the typed signal from the answer slot to the
    name's last token — ``max`` over the name's tokens of ``p_k*(i, j) · ā(i, j)``
    for the queried relation's discovered type at ``layer`` (and the untyped
    ``max_k`` beside it; for a block without an inventory, ``ā`` alone) — with the
    act the cell produced. By row: refusal rate, mean signal, AUC(signal → UNDEFINED)."""
    items = []
    for name in ("primary", "secondary"):
        for it in evals.get(name, []):
            row = acts.row_of(it)
            if row in ABSENCE_ROWS and it["id"] in outputs.get(name, {}):
                items.append((it, acts.grade(acts.parse(outputs[name][it["id"]]), it).column))
    seqs, pairs, spans = [], [], []
    for it, _ in items:
        ids = tok.encode(it["prompt"])
        sp = _span(tok, ids, it["name"])
        seqs.append(ids)
        pairs.append((len(ids) - 1, sp[-1] if sp else 0))
        spans.append(sp)
    K = model.types_k
    L = model.cfg.n_layers
    # A readout per token of the name would multiply the passes; the name's last
    # token (the identity-carrying stem under B1, the token itself under B2/B3)
    # is the one read, as in §5.1.
    P, A, _ = pair_readout(model, tok, seqs, pairs, device, tau)
    layer = layer if layer is not None else L - 1
    # The answer slot's attention to the name is not at one layer: the signal is
    # read at the §5.1 layer *and* as the maximum over layers (2026-09-07, the
    # first B4 cell: 0.025 at the §5.1 layer, no dynamic range).
    attn_layer = int(A.mean(0).argmax()) if len(items) else layer
    rows: dict[str, dict] = defaultdict(lambda: {"n": 0, "undefined": 0, "signal": [], "signal_any": [], "signal_max": [], "attn": [], "labels": []})
    for n, (it, col) in enumerate(items):
        row = acts.row_of(it)
        a = float(A[n, layer])
        if P is not None:
            kstar = (relation_type or {}).get(it["kind"])
            typed = float(P[n, layer, kstar["type"]]) * a if kstar else float("nan")
            any_ = float(P[n, layer].max()) * a
            over_layers = float((P[n, :, kstar["type"]] * A[n]).max()) if kstar else float("nan")
        else:
            typed, any_ = a, a
            over_layers = float(A[n].max())
        r = rows[row]
        r["n"] += 1
        r["undefined"] += col == "UNDEFINED"
        r["signal"].append(typed)
        r["signal_any"].append(any_)
        r["signal_max"].append(over_layers)
        r["attn"].append(float(A[n, attn_layer]))
        r["labels"].append(col == "UNDEFINED")
    from .mech import _auc
    out = {"layer": layer, "attn_layer": attn_layer, "n": len(items), "rows": {}}
    for row, r in sorted(rows.items()):
        sig = np.array(r["signal"], float)
        smax = np.array(r["signal_max"], float)
        out["rows"][row] = {"n": r["n"], "undefined": round(r["undefined"] / r["n"], 4),
                            "signal_mean": round(float(np.nanmean(sig)), 4) if r["n"] else None,
                            "signal_any_mean": round(float(np.mean(r["signal_any"])), 4),
                            "signal_max_layers_mean": round(float(np.nanmean(smax)), 4),
                            "attn_to_name_best_layer": round(float(np.mean(r["attn"])), 4),
                            "auc_signal_undefined": round(_auc((-sig).tolist(), r["labels"]), 4) if 0 < sum(r["labels"]) < r["n"] else None,
                            "auc_signal_max_undefined": round(_auc((-smax).tolist(), r["labels"]), 4) if 0 < sum(r["labels"]) < r["n"] else None}
    # Across the absent rows together: does a low typed signal predict the refusal?
    absent_sig, absent_max, absent_lab = [], [], []
    for row, r in rows.items():
        if row.startswith("absent"):
            absent_sig += r["signal"]
            absent_max += r["signal_max"]
            absent_lab += r["labels"]
    ok = 0 < sum(absent_lab) < len(absent_lab)
    out["absent_auc_signal_undefined"] = round(_auc((-np.array(absent_sig, float)).tolist(), absent_lab), 4) if ok else None
    out["absent_auc_signal_max_undefined"] = round(_auc((-np.array(absent_max, float)).tolist(), absent_lab), 4) if ok else None
    return out


# ---------------------------------------------------------------- §5.6 the operators

def operators(model: GPT, top: int = 4) -> list[dict]:
    """Per layer and type: the top singular values of ``R_k − I`` (what the operator
    does beyond the untyped ``q · k``), and its Frobenius norm."""
    if model.types_k <= 1:
        return []
    out = []
    for l, blk in enumerate(model.blocks):
        Rk = blk.types.operators().detach().float().cpu().numpy()
        hd = Rk.shape[1]
        row = {"layer": l, "types": []}
        for k in range(model.types_k):
            D = Rk[k] - np.eye(hd)
            s = np.linalg.svd(D, compute_uv=False)
            row["types"].append({"type": k, "frobenius": round(float(np.linalg.norm(D)), 4), "top_singular": [round(float(x), 4) for x in s[:top]]})
        out.append(row)
    return out


# ---------------------------------------------------------------- the driver

def analyze(model: GPT, tok: Tokenizer, world: World, evals: dict[str, list[dict]], outputs: dict[str, dict[str, str]],
            device, cfg, seed: int = 0) -> dict:
    """Every §5 instrument on one set of weights; ``outputs`` are the cell's
    per-set outputs (from ``full_eval``) so no act is generated twice."""
    tau = cfg.gumbel_tau[1]
    disc = type_discovery(model, tok, world, evals, device, tau, seed=seed)
    rep = {"block": cfg.block, "K": model.types_k, "lambda": cfg.types_lambda if cfg.block == "B4" else None,
           "type_discovery": disc,
           "phrasing": phrasing_check(model, tok, world, device, tau, seed=seed),
           "sibling": sibling_cosine(model, tok, world, device, tau, seed=seed),
           "operators": operators(model)}
    prim = evals["primary"]
    near = [it for it in prim if it["class"] == "absent-near"]
    wrong = sib = 0
    for it in near:
        if it["id"] in outputs.get("primary", {}):
            g = acts.grade(acts.parse(outputs["primary"][it["id"]]), it)
            if g.column == "ANSWER-wrong":
                wrong += 1
                sib += g.detail == "sibling"
    rep["sibling"]["share_of_wrong_near"] = round(sib / wrong, 4) if wrong else None
    rep["absence"] = absence_signal(model, tok, evals, outputs, device, tau, disc.get("relation_type"), disc.get("best_layer"))
    return rep


def render(rep: dict) -> str:
    lines = [f"# typed instruments — {rep['block']} K={rep['K']} λ={rep['lambda']}\n"]
    d = rep["type_discovery"]
    if d.get("layers"):
        lines.append(f"## §5.1 type discovery — {d['n_facts']} facts, best layer {d['best_layer']} NMI {d['best_nmi']} purity {d['best_purity']}; relation → type {d.get('relation_type')}\n")
        lines.append("| layer | max share | usage | NMI vs relation | purity | vs direction NMI | vs relation×direction | vs template NMI | conf by kind |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for l in d["layers"]:
            lines.append(f"| {l['layer']} | {l['max_share']} | {' '.join(f'{u:.2f}' for u in l['usage'])} | {l['vs_relation']['nmi']} | {l['vs_relation']['purity']} | "
                         f"{l['vs_direction']['nmi']} | {l['vs_relation_direction']['nmi']} | {l['vs_template']['nmi']} | "
                         f"{' '.join(f'{k[:3]} {v:.2f}' for k, v in l['confidence_by_kind'].items())} |")
        ph = rep.get("phrasing") or {}
        if ph:
            bl = d["best_layer"]
            lines.append(f"\nphrasing check at layer {bl}: trained NMI {ph['trained']['layers'][bl]['nmi']} purity {ph['trained']['layers'][bl]['purity']} → "
                         f"held-out NMI {ph['held-out']['layers'][bl]['nmi']} purity {ph['held-out']['layers'][bl]['purity']}\n")
    s = rep["sibling"]
    lines.append(f"## §5.2 sibling pull — share of wrong (near) {s.get('share_of_wrong_near')}; cosine overall shared/random/same-module "
                 f"{s['overall']['shared']} / {s['overall']['random']} / {s['overall']['same_module']}\n")
    if "under_type" in s:
        lines.append("| type | shared callee | random | same module |")
        lines.append("|---|---|---|---|")
        for k, v in s["under_type"].items():
            lines.append(f"| {k} | {v['shared']} | {v['random']} | {v['same_module']} |")
    a = rep["absence"]
    lines.append(f"\n## §5.3 relation-absence — typed signal at layer {a['layer']} and its max over layers; attention to the name is largest at layer {a.get('attn_layer')}; "
                 f"absent rows AUC(signal → UNDEFINED) {a['absent_auc_signal_undefined']} / max over layers {a.get('absent_auc_signal_max_undefined')}\n")
    lines.append("| row | n | UNDEFINED | signal (queried type) | signal (any type) | signal max over layers | ā to name (best layer) | AUC in row / max-layers |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in ABSENCE_ROWS:
        r = a["rows"].get(row)
        if r:
            lines.append(f"| {row} | {r['n']} | {r['undefined']} | {r['signal_mean']} | {r['signal_any_mean']} | {r.get('signal_max_layers_mean')} | "
                         f"{r.get('attn_to_name_best_layer')} | {r['auc_signal_undefined']} / {r.get('auc_signal_max_undefined')} |")
    if rep["operators"]:
        lines.append("\n## §5.6 operators — ‖R_k − I‖_F per layer (types in order)\n")
        lines.append("| layer | " + " | ".join(f"type {k}" for k in range(rep["K"])) + " |")
        lines.append("|---|" + "---|" * rep["K"])
        for l in rep["operators"]:
            lines.append(f"| {l['layer']} | " + " | ".join(f"{t['frobenius']:.2f}" for t in l["types"]) + " |")
    return "\n".join(lines) + "\n"
