"""The §1 checks of the 2026-09-07 addendum: an atlas entry names a circuit, not a verb.

Every phenomenon in the record is a token arriving in the answer slot by
one of three routes — copied from context, looked up from the weights,
emitted by prior — and "reads", "stores", "refuses" are shorthand for
those routes. These instruments turn each verb into a mechanical check
on a cell's saved weights, with no training:

- :func:`head_check` — *reads*: rank the heads by the attention mass the
  answer slot puts on the context's module token; ablate the top ``n``
  and re-read the block. If reading falls to the no-context floor while
  the parametric route holds, "reads" names those heads.
- :func:`ffn_check` — *stores*: ablate one layer's FFN at a time and
  re-read. Where the parametric route falls while reading holds, the
  association lives in those layers.
- :func:`b2_norm_check` — *refuses unreinforced inputs* (B2): per item,
  the displacement of the name's embedding row from its seeded
  initialisation against the act it produced; if a threshold on the
  norm predicts ``UNDEFINED`` near-deterministically, the policy is a
  norm.

The same head check reads B3 on the context world and B4 (addendum
§5.6). CPU is enough: a 30M block over a few hundred prompts.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch

from . import acts
from .tokens import Tokenizer, entity_vectors
from .train import GPT, Fwd, generate, load_cell, load_evals


# ---------------------------------------------------------------- spans and readouts

def span(tok: Tokenizer, ids: list[int], name: str) -> list[int]:
    """Positions in ``ids`` of the tokens ``name`` encodes to (its dedicated token,
    or its stems with ``_`` between them); the first occurrence."""
    sub = tok.encode(name)
    for i in range(len(ids) - len(sub) + 1):
        if ids[i: i + len(sub)] == sub:
            return list(range(i, i + len(sub)))
    return []


def reading_split(evals: dict[str, list[dict]]) -> str:
    """The inversion split whose fact the block has only met in context:
    v2's ``C-only-qa`` when present, else v0/v1's ``C-only``."""
    splits = {it["split"] for it in evals["inversion"]}
    return "C-only-qa" if "C-only-qa" in splits else "C-only"


def inversion_items(evals: dict[str, list[dict]], split: str, kind: str, n: int | None = None) -> list[dict]:
    items = [it for it in evals["inversion"] if it["split"] == split and it["context_kind"] == kind]
    return items[:n] if n else items


@torch.no_grad()
def attention_to_context(model: GPT, tok: Tokenizer, items: list[dict], device, slot: str = "ANSWER") -> np.ndarray:
    """Mean attention mass ``(L, h)`` from the answer slot to the context module's
    tokens over ``items`` (inversion items with a context). The slot is the
    position the value is predicted from: the ``ANSWER`` act token, teacher-
    forced after the prompt (``slot="ANSWER"``), or the prompt's last token
    (``slot="prompt"``, where the act itself is predicted)."""
    model.eval()
    L, h = model.cfg.n_layers, model.cfg.n_heads
    total = np.zeros((L, h))
    n = 0
    for it in items:
        ids = tok.encode(it["prompt"]) + ([tok.index["ANSWER"]] if slot == "ANSWER" else [])
        sp = span(tok, ids, it["context_value"])
        if not sp:
            continue
        ctx = Fwd(want_attn=True)
        model(torch.tensor([ids], device=device), ctx=ctx)
        for l, att in enumerate(ctx.attn):                 # (1, h, T, T)
            total[l] += att[0, :, -1, sp].sum(-1).cpu().numpy()
        n += 1
    return total / max(1, n)


def rank_heads(mass: np.ndarray) -> list[tuple[int, int]]:
    """Heads as ``(layer, head)`` by descending attention mass."""
    L, h = mass.shape
    return sorted(((l, hh) for l in range(L) for hh in range(h)), key=lambda x: -mass[x])


@torch.no_grad()
def read_rates(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], device, split: str, n: int | None = None,
               ablate: Fwd | None = None) -> dict[str, float]:
    """The three route numbers under an ablation: ``read`` (the reading split's
    ``support`` gold rate), ``follow`` (its ``conflict`` context rate), ``parametric``
    (``C+S/none`` gold: a dense-real fact with no context) and ``read_none`` (the
    reading split asked without context: the floor)."""
    model.ablate = ablate
    out = {}
    for key, (sp, kind, col) in {"read": (split, "support", "gold"), "follow": (split, "conflict", "context"),
                                 "parametric": ("C+S", "none", "gold"), "read_none": (split, "none", "gold")}.items():
        items = inversion_items(evals, sp, kind, n)
        outs, _, _ = generate(model, tok, [it["prompt"] for it in items], device)
        hit = 0
        for it, o in zip(items, outs):
            a = acts.parse(o)
            if a.kind != "ANSWER":
                continue
            if col == "gold":
                hit += a.values[0] in it["gold"]
            else:
                hit += a.values[0] == it["context_value"]
        out[key] = round(hit / max(1, len(items)), 4)
    model.ablate = None
    return out


def head_check(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], device, top_ns: tuple[int, ...] = (1, 2, 4, 8, 16),
               n_items: int | None = None, seed: int = 0, controls: int = 3) -> dict:
    """*Reads*: rank heads by their attention from the answer slot to the context's
    module token on the reading split's ``support`` items; ablate the top ``n``
    and re-read; beside each, ``controls`` random sets of ``n`` heads (seeded)
    and the bottom ``n``. Reports the ranked heads with their mass, the
    baseline rates, and every ablation's rates."""
    split = reading_split(evals)
    items = inversion_items(evals, split, "support", n_items)
    mass = attention_to_context(model, tok, items, device, "ANSWER")
    mass_prompt = attention_to_context(model, tok, items, device, "prompt")
    ranked = rank_heads(mass)
    L, h = mass.shape
    rng = np.random.default_rng(seed)
    all_heads = [(l, hh) for l in range(L) for hh in range(h)]
    rep = {
        "split": split, "n_items": len(items),
        "mass_answer_slot": [[round(float(x), 4) for x in row] for row in mass],
        "mass_prompt_slot": [[round(float(x), 4) for x in row] for row in mass_prompt],
        "ranked": [{"layer": l, "head": hh, "mass": round(float(mass[l, hh]), 4)} for l, hh in ranked[:max(top_ns)]],
        "baseline": read_rates(model, tok, evals, device, split, n_items),
        "ablations": [],
    }
    for n in top_ns:
        top = set(ranked[:n])
        row = {"n": n, "top": read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_heads=top)),
               "bottom": read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_heads=set(ranked[-n:]))),
               "random": []}
        for _ in range(controls):
            pick = {all_heads[i] for i in rng.choice(len(all_heads), n, replace=False)}
            row["random"].append(read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_heads=pick)))
        rep["ablations"].append(row)
    # Single-head ablations of the top heads: which one carries it alone.
    rep["single"] = [{"layer": l, "head": hh, **read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_heads={(l, hh)}))}
                     for l, hh in ranked[:4]]
    return rep


def ffn_check(model: GPT, tok: Tokenizer, evals: dict[str, list[dict]], device, n_items: int | None = None) -> dict:
    """*Stores*: one layer's FFN skipped at a time (then every layer's), the
    route numbers re-read each time."""
    split = reading_split(evals)
    L = model.cfg.n_layers
    rep = {"split": split, "baseline": read_rates(model, tok, evals, device, split, n_items), "layers": []}
    for l in range(L):
        rep["layers"].append({"layer": l, **read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_ffn={l}))})
    rep["all"] = read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_ffn=set(range(L))))
    # Cumulative from the last layer down: where the parametric route leaves.
    rep["cumulative_from_top"] = []
    for k in range(1, L + 1):
        layers = set(range(L - k, L))
        rep["cumulative_from_top"].append({"layers": sorted(layers), **read_rates(model, tok, evals, device, split, n_items, Fwd(ablate_ffn=layers))})
    return rep


# ---------------------------------------------------------------- B2: is the refusal a norm?

def _auc(scores: list[float], labels: list[bool]) -> float:
    """Rank AUC of ``scores`` for ``labels`` (ties at half)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    neg_sorted = np.sort(neg)
    total = 0.0
    for s in pos:
        lo = np.searchsorted(neg_sorted, s, "left")
        hi = np.searchsorted(neg_sorted, s, "right")
        total += lo + 0.5 * (hi - lo)
    return float(total / (len(pos) * len(neg)))


def b2_norm_check(run_dir: Path, world_dir: Path, eval_set: str = "primary") -> dict:
    """B2: per eval item, ``‖wte[name] − init‖`` (the seeded initialisation the
    row started from) against the act the cell produced for it (from
    ``outputs/<set>.jsonl``, no inference). Reports the norm by row and by act,
    the AUC of the norm for ``UNDEFINED``, and the best single threshold's
    accuracy — near 1.0 means the policy is a norm."""
    man = json.loads((run_dir / "manifest.json").read_text())
    cfg = man["config"]
    ents = json.loads((world_dir / "entities.json").read_text())
    state = torch.load(run_dir / "model.pt", map_location="cpu")
    W = state["wte.weight"].float().numpy()
    n_rows = W.shape[0]
    for v1_words, later_words in ((False, False), (True, False), (True, True)):
        tok = Tokenizer.build(cfg["block"], ents, v1_words=v1_words, later_words=later_words)
        if n_rows == len(tok):
            break
    names = sorted(tok.entity_ids)
    init = entity_vectors(names, W.shape[1], cfg["seed"])
    D = {n: W[tok.entity_ids[n]] - init[i] for i, n in enumerate(names)}
    items = acts.read_jsonl(world_dir / "eval" / f"{eval_set}.jsonl")
    outputs = acts.read_outputs(run_dir / "outputs" / f"{eval_set}.jsonl")
    # The tied output head moves every row that is never a target along one
    # shared direction (the softmax's push), so a never-seen name's row has the
    # *largest* displacement (2026-09-07, the first read of this check). The
    # displacement is split into its component along the mean displacement of
    # the held-out absent rows (``along``) and the rest (``orth``, the
    # input-driven part); each is a candidate for the state the act reads.
    held = [it["name"] for it in items if it["class"].startswith("absent") and it.get("exposure") == "held-out" and it["name"] in D]
    push = np.mean([D[n] for n in held], 0) if held else np.zeros(W.shape[1])
    push = push / (np.linalg.norm(push) + 1e-9)
    rows: list[dict] = []
    for it in items:
        if it["id"] not in outputs or it["name"] not in D:
            continue
        col = acts.grade(acts.parse(outputs[it["id"]]), it).column
        d = D[it["name"]]
        along = float(d @ push)
        rows.append({"row": acts.row_of(it), "name": it["name"], "norm": float(np.linalg.norm(d)), "act": col,
                     "along": along, "orth": float(np.linalg.norm(d - along * push)),
                     "cos_push": float(along / (np.linalg.norm(d) + 1e-9)), "mentions": it.get("mentions", 0)})
    by_row: dict[str, dict] = {}
    for r in rows:
        d = by_row.setdefault(r["row"], {"n": 0, "norms": [], "orth": [], "cos": [], "undefined": 0})
        d["n"] += 1
        d["norms"].append(r["norm"])
        d["orth"].append(r["orth"])
        d["cos"].append(r["cos_push"])
        d["undefined"] += r["act"] == "UNDEFINED"
    table = {row: {"n": d["n"], "norm_mean": round(float(np.mean(d["norms"])), 4), "norm_min": round(float(np.min(d["norms"])), 4),
                   "norm_max": round(float(np.max(d["norms"])), 4), "orth_mean": round(float(np.mean(d["orth"])), 4),
                   "cos_push_mean": round(float(np.mean(d["cos"])), 4), "undefined": round(d["undefined"] / d["n"], 4)}
             for row, d in sorted(by_row.items())}
    labels = [r["act"] == "UNDEFINED" for r in rows]
    n_pos = sum(labels)

    def best_threshold(key: str, sign: float) -> dict:
        """Refuse iff sign * feature is below a threshold: the best single threshold's accuracy."""
        order = sorted(rows, key=lambda r: sign * r[key])
        best = ((len(rows) - n_pos) / len(rows), None)          # refuse nothing
        seen_pos = 0
        for i, r in enumerate(order):
            seen_pos += r["act"] == "UNDEFINED"
            acc = (seen_pos + (len(rows) - n_pos - (i + 1 - seen_pos))) / len(rows)
            if acc > best[0]:
                best = (acc, r[key])
        return {"threshold": None if best[1] is None else round(best[1], 4), "accuracy": round(best[0], 4)}

    features = {"norm": -1.0, "orth": -1.0, "cos_push": 1.0}   # a small norm / small input-driven part / high alignment predicts refusal
    # If no scalar of the displacement decides the act, is the act a *direction* in
    # the row? A linear probe on the displacement vector itself (item split, 50/50).
    from . import probe as P
    X = np.stack([D[r["name"]] for r in rows])
    y = ["UNDEFINED" if r["act"] == "UNDEFINED" else "other" for r in rows]
    rng = np.random.default_rng(0)
    perm = rng.permutation(len(rows))
    tr, te = perm[: len(rows) // 2], perm[len(rows) // 2:]
    row_probe = {"test": None, "train": None}
    if len(set(y[i] for i in tr)) == 2:
        pr = P.fit(X[tr], [y[i] for i in tr], classes=("UNDEFINED", "other"))
        row_probe = {"train": round(P.accuracy(pr.predict(X[tr]), [y[i] for i in tr]), 4),
                     "test": round(P.accuracy(pr.predict(X[te]), [y[i] for i in te]), 4)}
    by_act: dict[str, list[float]] = {}
    for r in rows:
        by_act.setdefault(r["act"], []).append(r["norm"])
    return {
        "cell": run_dir.name, "eval_set": eval_set, "n": len(rows),
        "by_row": table,
        "norm_by_act": {a: {"n": len(v), "mean": round(float(np.mean(v)), 4)} for a, v in sorted(by_act.items())},
        "auc_norm_predicts_undefined": round(_auc([-r["norm"] for r in rows], labels), 4),
        "features": {k: {"auc": round(_auc([sign * r[k] for r in rows], labels), 4), **best_threshold(k, -sign)} for k, sign in features.items()},
        "row_probe": row_probe,
        "best_threshold": {"norm": best_threshold("norm", 1.0)["threshold"], "accuracy": best_threshold("norm", 1.0)["accuracy"],
                           "majority": round(max(n_pos, len(rows) - n_pos) / len(rows), 4)},
        "spearman_norm_mentions": round(_spearman([r["norm"] for r in rows], [r["mentions"] for r in rows]), 4),
    }


def _spearman(a: list[float], b: list[float]) -> float:
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


# ---------------------------------------------------------------- driver

def run_checks(run_dir: Path, world_dir: Path, weights: Path | None, which: tuple[str, ...], device: str | None = None,
               n_items: int | None = None, seed: int = 0) -> dict:
    """The named checks (``heads``, ``ffn``) on one set of weights of a cell."""
    device = device or "cpu"
    if device == "cpu":
        torch.set_num_threads(max(1, torch.get_num_threads()))
    model, tok, cfg = load_cell(run_dir, world_dir, weights, device)
    evals = load_evals(world_dir)
    out = {"cell": run_dir.name, "weights": str(weights or (run_dir / "model.pt")), "block": cfg.block}
    if "heads" in which:
        out["heads"] = head_check(model, tok, evals, device, n_items=n_items, seed=seed)
    if "ffn" in which:
        out["ffn"] = ffn_check(model, tok, evals, device, n_items=n_items)
    return out


def render(rep: dict) -> str:
    lines = [f"# {rep['cell']} — {rep['weights']}\n"]
    if "heads" in rep:
        hc = rep["heads"]
        b = hc["baseline"]
        lines.append(f"## reads — split {hc['split']}, {hc['n_items']} items; baseline read {b['read']} follow {b['follow']} parametric {b['parametric']} floor {b['read_none']}\n")
        lines.append("top heads by attention from the ANSWER slot to the context module: " +
                     ", ".join(f"L{r['layer']}H{r['head']} {r['mass']:.2f}" for r in hc["ranked"][:8]) + "\n")
        lines.append("| ablate top n | read | follow | parametric | random n (mean read / follow) | bottom n read |")
        lines.append("|---|---|---|---|---|---|")
        for a in hc["ablations"]:
            rr = np.mean([r["read"] for r in a["random"]]) if a["random"] else float("nan")
            rf = np.mean([r["follow"] for r in a["random"]]) if a["random"] else float("nan")
            lines.append(f"| {a['n']} | {a['top']['read']} | {a['top']['follow']} | {a['top']['parametric']} | {rr:.2f} / {rf:.2f} | {a['bottom']['read']} |")
        lines.append("\nsingle heads: " + ", ".join(f"L{s['layer']}H{s['head']} read {s['read']} follow {s['follow']}" for s in hc["single"]) + "\n")
    if "ffn" in rep:
        fc = rep["ffn"]
        b = fc["baseline"]
        lines.append(f"## stores — FFN ablation; baseline parametric {b['parametric']} read {b['read']}\n")
        lines.append("| FFN skipped | parametric | read | follow |")
        lines.append("|---|---|---|---|")
        for l in fc["layers"]:
            lines.append(f"| layer {l['layer']} | {l['parametric']} | {l['read']} | {l['follow']} |")
        for c in fc["cumulative_from_top"]:
            lines.append(f"| layers {c['layers'][0]}–{c['layers'][-1]} | {c['parametric']} | {c['read']} | {c['follow']} |")
        lines.append(f"| all | {fc['all']['parametric']} | {fc['all']['read']} | {fc['all']['follow']} |\n")
    return "\n".join(lines) + "\n"


def render_b2(reps: list[dict]) -> str:
    lines = ["# B2 — is the refusal a norm? (‖wte[name] − init‖ against the act; the displacement split along the head's push and orthogonal to it)\n",
             "| cell | n | AUC norm / orth / cos-push | threshold acc norm / orth / cos-push (majority) | row probe test (train) | ρ(norm, mentions) | dense norm·orth·cos / refused | sparse norm·orth·cos / refused | absent held-out norm·orth·cos / refused | absent trained norm·orth·cos / refused |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in reps:
        br = r["by_row"]

        f = lambda rows: "—" if not rows else (f"{np.mean([v['norm_mean'] for v in rows]):.2f}·{np.mean([v['orth_mean'] for v in rows]):.2f}·"
                                              f"{np.mean([v['cos_push_mean'] for v in rows]):.2f} / {np.mean([v['undefined'] for v in rows]):.2f}")
        cell = lambda prefix: f([v for k, v in br.items() if k.startswith(prefix)])
        held = [v for k, v in br.items() if k.startswith("absent") and k.endswith("held-out")]
        trained = [v for k, v in br.items() if k.startswith("absent") and not k.endswith("held-out")]
        ft = r["features"]
        lines.append(f"| {r['cell']} | {r['n']} | {ft['norm']['auc']} / {ft['orth']['auc']} / {ft['cos_push']['auc']} | "
                     f"{ft['norm']['accuracy']} / {ft['orth']['accuracy']} / {ft['cos_push']['accuracy']} ({r['best_threshold']['majority']}) | "
                     f"{r['row_probe']['test']} ({r['row_probe']['train']}) | {r['spearman_norm_mentions']} | {cell('dense-real')} | {cell('sparse-real')} | {f(held)} | {f(trained)} |")
    return "\n".join(lines) + "\n"
