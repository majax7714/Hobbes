# /// script
# requires-python = ">=3.12"
# dependencies = ["modal>=1.1"]
# ///
"""Atlas-0 cells on Modal (design §5; the trainer is `atlas0.train`).

    uv run scripts/modal_atlas0.py put <world-dir> <name>                 # → volume hobbes-atlas0:/worlds/<name>
    uv run scripts/modal_atlas0.py train --world <name> --block B1 --arm none --seed 0 --steps N \\
        [--stop-at-target] [--ckpt-every 250] [--out runs/<dir>]         # one cell
    uv run scripts/modal_atlas0.py grid --world <name> --steps N --seeds 0,1,2,3,4 \\
        [--blocks B1,B2,B3] [--arms none,phrase,lived,lived+phrase] [--out runs/<dir>]   # cells in parallel
    uv run scripts/modal_atlas0.py get <remote-path> <local-path>
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
    cell = f"{tc.block}-{tc.arm}-s{tc.seed}"
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
    return {"cell": cell, "cached": False, "manifest": m}


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
    if cmd in ("train", "grid"):
        import argparse
        ap = argparse.ArgumentParser(prog=f"modal_atlas0.py {cmd}")
        ap.add_argument("--world", required=True)
        ap.add_argument("--steps", type=int, required=True)
        ap.add_argument("--model", default="atlas-30m")
        ap.add_argument("--ckpt-every", type=int, default=250)
        ap.add_argument("--batch", type=int, default=64)
        ap.add_argument("--lr", type=float, default=6e-4)
        ap.add_argument("--out", default=None)
        if cmd == "train":
            ap.add_argument("--block", default="B1")
            ap.add_argument("--arm", default="none")
            ap.add_argument("--seed", type=int, default=0)
            ap.add_argument("--stop-at-target", action="store_true")
            ap.add_argument("--target-dense", type=float, default=0.95)
        else:
            ap.add_argument("--blocks", default="B1,B2,B3")
            ap.add_argument("--arms", default="none,phrase,lived,lived+phrase")
            ap.add_argument("--seeds", default="0,1,2,3,4")
        a = ap.parse_args(rest)
        out = a.out or f"{a.world}-{a.model}-{a.steps}"
        base = dict(model=a.model, steps=a.steps, ckpt_every=a.ckpt_every, batch=a.batch, lr=a.lr)
        if cmd == "train":
            cfg = dict(base, block=a.block, arm=a.arm, seed=a.seed, stop_at_target=a.stop_at_target, target_dense=a.target_dense)
            with app.run():
                r = train_cell.remote(a.world, cfg, out)
            print(json.dumps(_summary(r), indent=1, sort_keys=True))
            return 0
        cells = [dict(base, block=b, arm=arm, seed=int(s))
                 for s in a.seeds.split(",") for b in a.blocks.split(",") for arm in a.arms.split(",")]
        print(f"{len(cells)} cells on {GPU}, ≤{MAX_CONTAINERS} at a time → runs/{out}", file=sys.stderr)
        with app.run():
            results = list(train_cell.map([a.world] * len(cells), cells, [out] * len(cells)))
        summaries = [_summary(r) for r in results]
        total = sum((s["container"] or {}).get("cost_usd_assumed", 0.0) for s in summaries if not s["cached"])
        print(json.dumps({"cells": summaries, "cost_usd_assumed_total": round(total, 2)}, indent=1, sort_keys=True))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
