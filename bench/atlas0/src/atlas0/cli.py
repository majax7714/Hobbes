"""``atlas0`` — the model-free instruments of Atlas-0 (design §8, steps 1–2).

    atlas0 gen   --seed S --out DIR [--tiny]         # the world and the four corpora
    atlas0 check DIR                                  # step 1's exit criteria, from the files
    atlas0 score DIR --outputs OUT.jsonl [--set primary|secondary|trained]   # §6.1 matrix
    atlas0 probe-check DIR [--block B1|B2|B3] [--model tiny|atlas-30m] [--per-class N] [--out R.json]

``probe-check`` is step 2's exit: the probe pipeline run on a
random-init model over the world's primary items must report chance.
``score`` takes a jsonl of ``{"id": …, "output": …}`` lines, one per
eval item, from whatever produced them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from . import acts, probe, refmodel, tokens, world as W
from .check import check


def cmd_gen(a: argparse.Namespace) -> int:
    cfg = W.Config.tiny() if a.tiny else W.Config.full()
    t = time.time()
    w = W.generate(a.seed, cfg)
    manifest = W.write(w, Path(a.out))
    print(json.dumps({"seed": a.seed, "world_hash": manifest["world_hash"], "facts": manifest["facts"],
                      "classes": manifest["classes"], "corpus_lines": manifest["corpus_lines"],
                      "seconds": round(time.time() - t, 1)}, indent=2))
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    report = check(Path(a.dir))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    checks = report["checks"]
    for k, v in checks.items():
        if isinstance(v, bool):
            print(f"{'ok ' if v else 'FAIL'}  {k}")
    for arm, r in checks["mentions_per_arm"].items():
        print(f"{'ok ' if r['ok'] else 'FAIL'}  mentions[{arm}] lines={r['lines']} statements={r['statements']} qa={r['qa']}"
              + (f" bad={r['bad_counts']}" if not r["ok"] else ""))
    print(f"stem TV from uniform: {checks['stem_tv_from_uniform']}")
    print(f"primary rows: {checks['primary_rows']}")
    print("OK" if report["ok"] else "FAILED")
    return 0 if report["ok"] else 1


def cmd_score(a: argparse.Namespace) -> int:
    items = acts.read_jsonl(Path(a.dir) / "eval" / f"{a.set}.jsonl")
    outputs = acts.read_outputs(Path(a.outputs))
    m = acts.confusion(items, outputs)
    print(acts.render(m))
    if a.out:
        Path(a.out).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    return 0


_WORKER: dict = {}


def _worker_init(block: str, ents: dict, model: str, seed: int) -> None:
    tok = tokens.Tokenizer.build(block, ents)
    _WORKER["tok"] = tok
    _WORKER["model"] = refmodel.RefModel(refmodel.CONFIGS[model], tok, seed)


def _worker_run(prompt: str) -> tuple[np.ndarray, str, float]:
    tok, m = _WORKER["tok"], _WORKER["model"]
    ids = tok.encode(prompt)
    r, _ = m.forward(ids)
    out, e = m.generate(ids, max_new=6)
    return r, tok.decode(out), e


def _model_size(block: str, ents: dict, model: str, seed: int) -> tuple[int, int]:
    """(parameters, vocabulary) of the reference model without building its weights."""
    tok = tokens.Tokenizer.build(block, ents)
    cfg = refmodel.CONFIGS[model]
    d = cfg.d_model
    per_layer = 3 * d * d + d * d + 2 * d * cfg.d_ff + 4 * d
    return (len(tok) * d + cfg.max_len * d + per_layer * cfg.n_layers + 2 * d), len(tok)


def run_probe_check(dir: Path, block: str, model: str, per_class: int, seed: int, workers: int | None = None) -> dict:
    """The step-2 pipeline on a random-init model: residuals → probe → acts → authority.

    Items are independent and run across ``workers`` processes (default:
    the box's cores), each holding its own copy of the model.
    """
    ents = json.loads((dir / "entities.json").read_text())
    items = acts.read_jsonl(dir / "eval" / "primary.jsonl")
    idx, y = probe.balanced_indices(items, seed, per_class)
    chosen = [items[i] for i in idx]
    t = time.time()
    workers = workers or os.cpu_count() or 1
    prompts = [it["prompt"] for it in chosen]
    if workers == 1:
        _worker_init(block, ents, model, seed)
        results = [_worker_run(p) for p in prompts]
    else:
        with ProcessPoolExecutor(workers, initializer=_worker_init, initargs=(block, ents, model, seed)) as ex:
            results = list(ex.map(_worker_run, prompts, chunksize=8))
    res = [r for r, _, _ in results]
    outputs = {it["id"]: o for it, (_, o, _) in zip(chosen, results)}
    entropies = [e for _, _, e in results]
    n_params, vocab = _model_size(block, ents, model, seed)
    X = np.stack(res)                      # (n, L+1, d)
    pl = probe.probe_layers(X, y, seed=seed)
    cols = [acts.grade(acts.parse(outputs[it["id"]]), it).column for it in chosen]
    te = pl["test_indices"]
    auth = probe.authority([y[i] for i in te], pl["test_predictions"], [cols[i] for i in te], [entropies[i] for i in te])
    matrix = acts.confusion(chosen, outputs)
    tol = 0.08
    return {
        "block": block, "model": model, "params": n_params, "vocab": vocab, "seed": seed,
        "items": len(chosen), "per_class": len(chosen) // 3, "seconds": round(time.time() - t, 1),
        "probe": {k: v for k, v in pl.items() if k not in ("test_indices", "test_predictions")},
        "authority": auth,
        "confusion": matrix,
        "at_chance": pl["best_test"] <= pl["chance"] + tol,
        "tolerance": tol,
    }


def cmd_probe_check(a: argparse.Namespace) -> int:
    r = run_probe_check(Path(a.dir), a.block, a.model, a.per_class, a.seed, a.workers)
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
    print(f"{a.block} {a.model} ({r['params']:,} params, vocab {r['vocab']}) on {r['items']} primary items, {r['seconds']}s")
    print("layer  train   test     (chance %.3f, tolerance %.2f)" % (r["probe"]["chance"], r["tolerance"]))
    for L in r["probe"]["layers"]:
        print(f"{L['layer']:>5}  {L['train']:.3f}  {L['test']:.3f}")
    print(f"best layer {r['probe']['best_layer']} test {r['probe']['best_test']:.3f} → {'at chance' if r['at_chance'] else 'ABOVE CHANCE'}")
    au = r["authority"]
    print(f"MI(act;probed)={au['mi_act_probed']} MI(act;true)={au['mi_act_true']} MI(act;entropy)={au['mi_act_entropy']} "
          f"MI(probed;true)={au['mi_probed_true']}  entropy by class {au['entropy_by_true_class']}")
    print(acts.render(r["confusion"]))
    return 0 if r["at_chance"] else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="atlas0", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="generate the world and the four corpora")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--tiny", action="store_true", help="the test-sized world")
    g.set_defaults(fn=cmd_gen)
    c = sub.add_parser("check", help="step 1's exit criteria over a written world")
    c.add_argument("dir")
    c.add_argument("--out")
    c.set_defaults(fn=cmd_check)
    s = sub.add_parser("score", help="the act × class confusion matrix over a jsonl of outputs")
    s.add_argument("dir")
    s.add_argument("--outputs", required=True)
    s.add_argument("--set", default="primary", choices=("primary", "secondary", "trained"))
    s.add_argument("--out")
    s.set_defaults(fn=cmd_score)
    q = sub.add_parser("probe-check", help="step 2's exit: the probe pipeline on a random-init model reports chance")
    q.add_argument("dir")
    q.add_argument("--block", default="B1", choices=tokens.BLOCKS)
    q.add_argument("--model", default="tiny", choices=sorted(refmodel.CONFIGS))
    q.add_argument("--per-class", type=int, default=300)
    q.add_argument("--seed", type=int, default=0)
    q.add_argument("--workers", type=int, default=None, help="processes (default: the box's cores)")
    q.add_argument("--out")
    q.set_defaults(fn=cmd_probe_check)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
