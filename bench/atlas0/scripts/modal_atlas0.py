# /// script
# requires-python = ">=3.12"
# dependencies = ["modal>=1.1"]
# ///
"""Atlas-0 cells on Modal (design §5; the trainer is `atlas0.train`).

    uv run scripts/modal_atlas0.py put <world-dir> <name>                 # → volume hobbes-atlas0:/worlds/<name>
    uv run scripts/modal_atlas0.py train --world <name> --block B1 --arm none --seed 0 --steps N \\
        [--stop-at-target] [--ckpt-every 250] [--out runs/<dir>]         # one cell
    uv run scripts/modal_atlas0.py grid --world <name> --steps N --seeds 0,1,2,3,4 \\
        [--blocks B1,B2,B3] [--arms none,phrase,lived,lived+phrase] [--runs 2] [--out runs/<dir>]   # cells in parallel
    # --runs R repeats every cell R times (same seed, same config; -r2… dirs): §6.6's run-to-run spread
    # a world per seed (v1): --world v1-lived-seed{seed}, formatted with each cell's seed
    uv run scripts/modal_atlas0.py reeval --world <name> --runs <dir> --out <dir> [--cells B1-none-s1,...]   # re-read finished cells
    uv run scripts/modal_atlas0.py get <remote-path> <local-path>
    # 2026-09-07 (the B4 addendum): --stop-at-step 3100 --full-eval-at 2200,3100 reads a cell at both T_v2 checkpoints;
    # --save-weights-every N keeps weights for the §1 checks; --types-k/--types-rank/--types-lambda are B4's (block B4)
    uv run scripts/modal_atlas0.py mech --jobs 'v2-seed1:v2-mech-b1/B1-none-s1:ckpt/step-1600.pt:heads:b1-heads-1600;...'   # the §A.1 checks on a GPU → /atlas0/mech
    ATLAS0_GPU=L4 ATLAS0_MAX_CONTAINERS=4                                 # the environment

One volume, ``hobbes-atlas0`` at ``/atlas0``: ``worlds/<name>/`` (what
``atlas0 gen`` wrote) and ``runs/<dir>/<block>-<arm>-s<seed>/`` (what
``atlas0.train.run`` writes: manifest, report, outputs, residuals, the
weights). The package is shipped into the image from ``src/atlas0`` at
each call, so the container runs this checkout's trainer.

Cost is recorded, not hidden: each result carries the container's wall
time and a dollar figure at the **assumed** list rate for the GPU
(``RATES``); the bill is Modal's. The first cell is run alone and its
wall time compared with the estimate before anything else is launched
(Max, 2026-09-05).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import modal

APP = "hobbes-atlas0"
GPU = os.environ.get("ATLAS0_GPU", "L4")
MAX_CONTAINERS = int(os.environ.get("ATLAS0_MAX_CONTAINERS", "4"))
#: Assumed list prices per GPU-hour (USD), for the cost line in every result.
RATES = {"T4": 0.59, "L4": 0.80, "A10G": 1.10, "L40S": 1.95, "A100-40GB": 2.10, "A100-80GB": 2.50, "H100": 3.95}

SRC = Path(__file__).resolve().parent.parent / "src" / "atlas0"
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.8.0", "numpy>=2")
    .add_local_dir(str(SRC), "/root/atlas0")
)
vol = modal.Volume.from_name("hobbes-atlas0", create_if_missing=True)
app = modal.App(APP)


@app.function(image=image, gpu=GPU, volumes={"/atlas0": vol}, timeout=3 * 3600, max_containers=MAX_CONTAINERS)
def train_cell(world: str, cfg: dict, out: str) -> dict:
    """One cell: ``atlas0.train.run`` over ``/atlas0/worlds/<world>`` into ``/atlas0/runs/<out>/<cell>``."""
    import torch
    from atlas0 import train

    t0 = time.time()
    tc = train.TrainConfig(**cfg)
    cell = tc.cell
    out_dir = Path("/atlas0/runs") / out / cell
    if (out_dir / "manifest.json").exists():
        m = json.loads((out_dir / "manifest.json").read_text())
        return {"cell": cell, "cached": True, "manifest": m}
    world_dir = Path("/atlas0/worlds") / world
    log_lines: list[str] = []

    def log(s: str) -> None:
        print(s, flush=True)
        log_lines.append(s)

    m = train.run(world_dir, out_dir, tc, device="cuda", log=log)
    wall = time.time() - t0
    m["container"] = {"gpu": GPU, "wall_s": round(wall, 1), "rate_usd_per_h": RATES.get(GPU),
                      "cost_usd_assumed": round(wall / 3600 * RATES.get(GPU, 0.0), 3),
                      "device": torch.cuda.get_device_name(0)}
    (out_dir / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    (out_dir / "log.txt").write_text("\n".join(log_lines) + "\n")
    vol.commit()
    # Plain JSON back to the client: the local environment has no torch to unpickle against.
    return json.loads(json.dumps({"cell": cell, "cached": False, "manifest": m}))


@app.function(image=image, gpu=GPU, volumes={"/atlas0": vol}, timeout=1800, max_containers=MAX_CONTAINERS)
def eval_cell(world: str, run: str, out: str, weights_step: int | None = None) -> dict:
    """Re-read one finished cell (``/atlas0/runs/<run>``) against ``/atlas0/worlds/<world>``'s
    eval sets into ``/atlas0/runs/<out>/<cell>`` — no training; ~$0.01. With
    ``weights_step``, the cell's ``ckpt/step-N.pt`` is read into ``<cell>/step-N/``."""
    from atlas0 import train

    t0 = time.time()
    run_dir = Path("/atlas0/runs") / run
    out_dir = Path("/atlas0/runs") / out / run_dir.name
    weights = None
    if weights_step:
        weights = run_dir / "ckpt" / f"step-{weights_step}.pt"
        out_dir = out_dir / f"step-{weights_step}"
    if (out_dir / "manifest.json").exists():
        return {"cell": run_dir.name, "cached": True, "manifest": json.loads((out_dir / "manifest.json").read_text())}
    m = train.reevaluate(Path("/atlas0/worlds") / world, run_dir, out_dir, device="cuda", weights=weights)
    wall = time.time() - t0
    m["container"] = {"gpu": GPU, "wall_s": round(wall, 1), "rate_usd_per_h": RATES.get(GPU),
                      "cost_usd_assumed": round(wall / 3600 * RATES.get(GPU, 0.0), 3), "reeval": True}
    (out_dir / "manifest.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    vol.commit()
    return json.loads(json.dumps({"cell": run_dir.name, "cached": False, "manifest": m}))


@app.function(image=image, gpu=GPU, volumes={"/atlas0": vol}, timeout=1800, max_containers=MAX_CONTAINERS)
def mech_cell(world: str, run: str, weights: str | None, which: str, out: str, n_items: int | None = None) -> dict:
    """The §A.1 checks (``atlas0.mech``: heads / ffn / all) on one cell's weights
    (``/atlas0/runs/<run>``, optionally its ``<weights>`` relative path) into
    ``/atlas0/mech/<out>.{json,md}``; a minute or two on a GPU, ~$0.02."""
    from atlas0 import mech

    t0 = time.time()
    run_dir = Path("/atlas0/runs") / run
    target = Path("/atlas0/mech") / out
    if Path(str(target) + ".json").exists():
        return {"out": out, "cached": True}
    target.parent.mkdir(parents=True, exist_ok=True)
    w = (run_dir / weights) if weights else None
    rep = mech.run_checks(run_dir, Path("/atlas0/worlds") / world, w, ("heads", "ffn") if which == "all" else (which,), "cuda", n_items)
    rep["container"] = {"gpu": GPU, "wall_s": round(time.time() - t0, 1), "rate_usd_per_h": RATES.get(GPU),
                        "cost_usd_assumed": round((time.time() - t0) / 3600 * RATES.get(GPU, 0.0), 3)}
    Path(str(target) + ".json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    Path(str(target) + ".md").write_text(mech.render(rep))
    vol.commit()
    return json.loads(json.dumps({"out": out, "cached": False, "container": rep["container"]}))


def _summary(r: dict) -> dict:
    m = r["manifest"]
    return {"cell": r["cell"], "cached": r["cached"], "steps": m["steps_done"], "epochs": m["epochs"],
            "tokens_per_s": m["tokens_per_s"], "train_s": m["train_s"], "eval_s": m["eval_s"],
            "final": m["final"], "container": m.get("container")}


def main(argv: list[str]) -> int:
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if cmd == "put" and len(rest) == 2:
        os.execvp("modal", ["modal", "volume", "put", "--force", "hobbes-atlas0", rest[0], f"/worlds/{rest[1]}"])
    if cmd == "get" and len(rest) == 2:
        os.execvp("modal", ["modal", "volume", "get", "--force", "hobbes-atlas0", rest[0], rest[1]])
    if cmd == "reeval":
        import argparse
        ap = argparse.ArgumentParser(prog="modal_atlas0.py reeval")
        ap.add_argument("--world", required=True, help="world name; {seed} is formatted with each cell's seed")
        ap.add_argument("--runs", required=True, help="the runs dir on the volume holding the cells")
        ap.add_argument("--out", required=True)
        ap.add_argument("--cells", default=None, help="comma-separated cell names (default: every cell in --runs)")
        ap.add_argument("--weights-step", type=int, default=None, help="read each cell's ckpt/step-N.pt into <out>/<cell>/step-N/")
        a = ap.parse_args(rest)
        if a.cells:
            cells = a.cells.split(",")
        else:
            import subprocess
            ls = subprocess.run(["modal", "volume", "ls", "--json", "hobbes-atlas0", f"/runs/{a.runs}"], capture_output=True, text=True, check=True)
            cells = sorted(e["filename"].rsplit("/", 1)[-1] for e in json.loads(ls.stdout) if e["type"] == "dir")
        worlds = [a.world.format(seed=c.rsplit("-s", 1)[-1]) for c in cells]
        print(f"{len(cells)} cells re-read on {GPU} → runs/{a.out}", file=sys.stderr)
        with app.run():
            results = list(eval_cell.map(worlds, [f"{a.runs}/{c}" for c in cells], [a.out] * len(cells), [a.weights_step] * len(cells)))
        total = sum((r["manifest"].get("container") or {}).get("cost_usd_assumed", 0.0) for r in results if not r["cached"])
        print(json.dumps({"cells": [{"cell": r["cell"], "cached": r["cached"], "final": r["manifest"]["final"]} for r in results],
                          "cost_usd_assumed_total": round(total, 2)}, indent=1, sort_keys=True))
        return 0
    if cmd == "mech":
        import argparse
        ap = argparse.ArgumentParser(prog="modal_atlas0.py mech")
        ap.add_argument("--jobs", required=True, help="semicolon-separated WORLD:RUN:WEIGHTS-or-'-':heads|ffn|all:OUT")
        ap.add_argument("--items", type=int, default=None)
        a = ap.parse_args(rest)
        jobs = [j.split(":") for j in a.jobs.split(";") if j]
        print(f"{len(jobs)} checks on {GPU} → /atlas0/mech", file=sys.stderr)
        with app.run():
            results = list(mech_cell.map([j[0] for j in jobs], [j[1] for j in jobs], [None if j[2] == "-" else j[2] for j in jobs],
                                         [j[3] for j in jobs], [j[4] for j in jobs], [a.items] * len(jobs)))
        total = sum((r.get("container") or {}).get("cost_usd_assumed", 0.0) for r in results)
        print(json.dumps({"checks": results, "cost_usd_assumed_total": round(total, 3)}, indent=1, sort_keys=True))
        return 0
    if cmd in ("train", "grid"):
        import argparse
        ap = argparse.ArgumentParser(prog=f"modal_atlas0.py {cmd}")
        ap.add_argument("--world", required=True)
        ap.add_argument("--steps", type=int, required=True)
        ap.add_argument("--model", default="atlas-30m")
        ap.add_argument("--ckpt-every", type=int, default=250)
        ap.add_argument("--epochs", type=float, default=None, help="v2's T: steps set so the stream is seen this many times (--steps is then the cap's name only)")
        ap.add_argument("--batch", type=int, default=64)
        ap.add_argument("--lr", type=float, default=6e-4)
        ap.add_argument("--out", default=None)
        ap.add_argument("--stop-at-step", type=int, default=None, help="stop here on the full schedule (T_v2: 3100 of the 16-epoch cosine)")
        ap.add_argument("--save-weights-every", type=int, default=0, help="weights at every checkpoint that is a multiple of this (ckpt/step-N.pt)")
        ap.add_argument("--full-eval-at", default="", help="comma-separated steps for a full read (step-N/: report, outputs, weights)")
        ap.add_argument("--types-k", type=int, default=8, help="B4: relation operators per layer")
        ap.add_argument("--types-rank", type=int, default=16, help="B4: the operators' rank")
        ap.add_argument("--types-lambda", type=float, default=0.1, help="B4: the penalty weight λ")
        if cmd == "train":
            ap.add_argument("--block", default="B1")
            ap.add_argument("--arm", default="none")
            ap.add_argument("--seed", type=int, default=0)
            ap.add_argument("--stop-at-target", action="store_true")
            ap.add_argument("--target-dense", type=float, default=0.95)
            ap.add_argument("--target-measure", default="dense_correct", choices=("dense_correct", "read_context_only"))
        else:
            ap.add_argument("--blocks", default="B1,B2,B3")
            ap.add_argument("--arms", default="none,phrase,lived,lived+phrase")
            ap.add_argument("--seeds", default="0,1,2,3,4")
            ap.add_argument("--runs", type=int, default=1, help="repeats of every cell (same seed and config)")
        a = ap.parse_args(rest)
        out = a.out or f"{a.world.replace('{seed}', 'seeds')}-{a.model}-{a.steps}"
        base = dict(model=a.model, steps=a.steps, ckpt_every=a.ckpt_every, batch=a.batch, lr=a.lr, max_epochs=a.epochs,
                    stop_at_step=a.stop_at_step, save_weights_every=a.save_weights_every,
                    full_eval_at=tuple(int(x) for x in a.full_eval_at.split(",") if x),
                    types_k=a.types_k, types_rank=a.types_rank, types_lambda=a.types_lambda)
        if cmd == "train":
            cfg = dict(base, block=a.block, arm=a.arm, seed=a.seed, stop_at_target=a.stop_at_target, target_dense=a.target_dense,
                       target_measure=a.target_measure)
            with app.run():
                r = train_cell.remote(a.world.format(seed=a.seed), cfg, out)
            print(json.dumps(_summary(r), indent=1, sort_keys=True))
            return 0
        cells = [dict(base, block=b, arm=arm, seed=int(s), run=r)
                 for r in range(1, a.runs + 1) for s in a.seeds.split(",") for b in a.blocks.split(",") for arm in a.arms.split(",")]
        print(f"{len(cells)} cells on {GPU}, ≤{MAX_CONTAINERS} at a time → runs/{out}", file=sys.stderr)
        worlds = [a.world.format(seed=c["seed"]) for c in cells]
        with app.run():
            results = list(train_cell.map(worlds, cells, [out] * len(cells)))
        summaries = [_summary(r) for r in results]
        total = sum((s["container"] or {}).get("cost_usd_assumed", 0.0) for s in summaries if not s["cached"])
        print(json.dumps({"cells": summaries, "cost_usd_assumed_total": round(total, 2)}, indent=1, sort_keys=True))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
