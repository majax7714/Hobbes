# /// script
# requires-python = ">=3.12"
# dependencies = ["modal>=1.1"]
# ///
"""Test-time training on the derived layer, on Modal (ADR-099 §5).

    uv run pipeline/scripts/modal_ttt.py put <local-dir-or-file> <remote-path>
    uv run pipeline/scripts/modal_ttt.py train --corpus corpora/<repo>/<sha> [--steps 300] [--seed 0] [--model M]
    uv run pipeline/scripts/modal_ttt.py nll --units units/<name>.jsonl --out runs/<name>.json [--adapter adapters/…] [--model M] [--conditioning message,none,subject,task]
    ADAPTERS=<name>=adapters/… MODEL=M uv run pipeline/scripts/modal_ttt.py deploy   # vLLM, base + adapters
    uv run pipeline/scripts/modal_ttt.py url
    uv run pipeline/scripts/modal_ttt.py get <remote-path> <local-path>

One volume, ``hobbes-ttt`` at ``/ttt``: ``corpora/`` (what `hobbes
derive-corpus` wrote), ``units/`` (gold-diff units), ``adapters/``
(LoRA weights + ``manifest.json``: seed, steps, corpus hash, GPU,
versions, loss curve), ``runs/`` (scores). Base weights come from the
``hobbes-hf-cache`` volume the ladder already uses (ADR-057).

The adapter is a **derived artifact**: keyed by ``(model, repo, sha,
recipe hash)`` and regenerable from the corpus; what training cannot
promise — bit-identity across GPU classes — the manifest records
rather than hides (ADR-099 §7). Nothing here interprets a number.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

import modal

APP = "hobbes-ttt"
#: The primary model (fully open lineage) and the ladder's comparison rung.
# The serve window is 16k on the A10G: at 32k the 7B's KV cache wants
# 7 GiB beside the weights and the card has 5.25 (vLLM's own estimate
# was 18k; first deploy, 2026-09-03). Serving answers navigation
# questions; the NLL scorer runs on the A100 and is not bound by this.
MODELS = {
    "allenai/Olmo-3-7B-Instruct": {"gpu_serve": "A10G", "max_model_len": 16384},
    "Qwen/Qwen2.5-Coder-7B-Instruct": {"gpu_serve": "A10G", "max_model_len": 16384},
}
MODEL = os.environ.get("MODEL", "allenai/Olmo-3-7B-Instruct")
#: ``name=remote-adapter-dir,…`` baked into the serve image at deploy.
ADAPTERS = os.environ.get("ADAPTERS", "")
PORT = 8000
VLLM = "0.27.1"  # the ladder's pin (modal_vllm.py)

#: The recipe (ADR-099 §3.3), pinned; a sweep edits this table.
RECIPE = {"rank": 32, "alpha": 64, "dropout": 0.05, "lr": 2e-4, "warmup": 30, "batch": 16,
          "micro": 4, "max_len": 2048, "precision": "bf16",
          "targets": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]}

train_image = (
    modal.Image.debian_slim(python_version="3.12")
    # Olmo 3 needs transformers ≥ 4.57; 4.57.x + peft 0.18 is the pairing
    # both projects tested, so the pins stay a generation behind current.
    .pip_install("torch==2.8.0", "transformers==4.57.6", "peft==0.18.1", "accelerate==1.10.1",
                 "huggingface_hub>=0.34", "sentencepiece", "protobuf")
)
serve_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(f"vllm=={VLLM}", "transformers>=5.8", "huggingface_hub>=0.34")
    .env({"MODEL": MODEL, "ADAPTERS": ADAPTERS, "VLLM_USE_FLASHINFER_SAMPLER": "0"})
)
weights = modal.Volume.from_name("hobbes-hf-cache", create_if_missing=True)
ttt = modal.Volume.from_name("hobbes-ttt", create_if_missing=True)
VOLUMES = {"/root/.cache/huggingface": weights, "/ttt": ttt}
app = modal.App(APP)


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def recipe_hash(model: str, steps: int, seed: int, corpus_hash: str) -> str:
    body = json.dumps({"model": model, "steps": steps, "seed": seed, "corpus": corpus_hash, **RECIPE}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def _versions() -> dict:
    import importlib.metadata as md
    return {p: md.version(p) for p in ("torch", "transformers", "peft", "accelerate")}


def _encode(tok, messages: list[dict], max_len: int | None):
    """``(input_ids, labels)`` with the loss on the assistant turn only.

    The prompt is the chat template over every turn but the last with
    the generation prompt appended; the full text is the template over
    all turns. The prompt must be a prefix of the full encoding — it is
    for Olmo 3 and Qwen 2.5 — and the function refuses rather than
    guesses if it is not, because a mis-masked corpus trains on
    questions.
    """
    prompt = tok.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=True)
    full = tok.apply_chat_template(messages, tokenize=True)
    if hasattr(prompt, "input_ids"):
        prompt, full = prompt["input_ids"], full["input_ids"]
    prompt, full = list(prompt), list(full)
    if full[:len(prompt)] != prompt:
        raise RuntimeError("chat template: the prompt encoding is not a prefix of the full encoding")
    labels = [-100] * len(prompt) + full[len(prompt):]
    truncated = False
    if max_len and len(full) > max_len:
        full, labels, truncated = full[:max_len], labels[:max_len], True
    return full, labels, len(prompt), truncated


@app.function(image=train_image, gpu="A100-80GB", volumes=VOLUMES, timeout=4 * 3600)
def train_adapter(corpus: str, steps: int = 300, seed: int = 0, model: str = MODEL, out: str | None = None) -> dict:
    """LoRA over ``/ttt/<corpus>/train.jsonl`` per the pinned recipe; writes
    the adapter and its manifest under ``/ttt/adapters/…``; idempotent on key."""
    import random
    import time

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

    manifest = json.load(open(f"/ttt/{corpus}/manifest.json"))
    key = recipe_hash(model, steps, seed, manifest["corpus_hash"])
    out = out or f"adapters/{slug(model)}/{manifest['repo']}/{manifest['sha'][:12]}/{key}"
    if os.path.exists(f"/ttt/{out}/manifest.json"):
        return json.load(open(f"/ttt/{out}/manifest.json"))

    torch.manual_seed(seed); random.seed(seed)
    tok = AutoTokenizer.from_pretrained(model)
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    records = [json.loads(ln) for ln in open(f"/ttt/{corpus}/train.jsonl") if ln.strip()]
    encoded, truncated = [], 0
    for r in records:
        ids, labels, _, cut = _encode(tok, r["messages"], RECIPE["max_len"])
        truncated += cut
        encoded.append((ids, labels))
    order = list(range(len(encoded)))
    random.Random(seed).shuffle(order)

    net = AutoModelForCausalLM.from_pretrained(model, dtype=torch.bfloat16, device_map="cuda")
    net.gradient_checkpointing_enable()
    net.enable_input_require_grads()
    net = get_peft_model(net, LoraConfig(r=RECIPE["rank"], lora_alpha=RECIPE["alpha"], lora_dropout=RECIPE["dropout"],
                                         target_modules=RECIPE["targets"], task_type="CAUSAL_LM"))
    params = [p for p in net.parameters() if p.requires_grad]
    optim = torch.optim.AdamW(params, lr=RECIPE["lr"], weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(optim, RECIPE["warmup"], steps)
    accum = RECIPE["batch"] // RECIPE["micro"]
    losses, cursor, started = [], 0, time.time()
    net.train()
    for step in range(steps):
        total = 0.0
        for _ in range(accum):
            batch = []
            for _ in range(RECIPE["micro"]):
                batch.append(encoded[order[cursor % len(order)]]); cursor += 1
            width = max(len(ids) for ids, _ in batch)
            input_ids = torch.tensor([ids + [pad] * (width - len(ids)) for ids, _ in batch], device="cuda")
            labels = torch.tensor([lab + [-100] * (width - len(lab)) for _, lab in batch], device="cuda")
            attention = (torch.arange(width, device="cuda")[None, :] < torch.tensor([len(ids) for ids, _ in batch], device="cuda")[:, None]).long()
            loss = net(input_ids=input_ids, attention_mask=attention, labels=labels).loss / accum
            loss.backward()
            total += loss.item()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        optim.step(); sched.step(); optim.zero_grad(set_to_none=True)
        if step % 10 == 0 or step == steps - 1:
            losses.append({"step": step, "loss": round(total, 4)})
            print(f"step {step} loss {total:.4f} lr {sched.get_last_lr()[0]:.2e} {int(time.time() - started)}s", flush=True)

    os.makedirs(f"/ttt/{out}", exist_ok=True)
    net.save_pretrained(f"/ttt/{out}")
    record = {
        "model": model, "corpus": corpus, "corpus_hash": manifest["corpus_hash"], "repo": manifest["repo"],
        "sha": manifest["sha"], "recipe": RECIPE, "recipe_hash": key, "steps": steps, "seed": seed,
        "records": len(records), "truncated": truncated, "examples_seen": steps * RECIPE["batch"],
        "epochs": round(steps * RECIPE["batch"] / max(1, len(records)), 3),
        "gpu": torch.cuda.get_device_name(0), "versions": _versions(), "wall_s": int(time.time() - started),
        "losses": losses, "path": out,
    }
    json.dump(record, open(f"/ttt/{out}/manifest.json", "w"), indent=1, sort_keys=True)
    ttt.commit()
    return record


@app.function(image=train_image, gpu="A100-80GB", volumes=VOLUMES, timeout=4 * 3600)
def score_nll(units: str, out: str, adapter: str | None = None, model: str = MODEL, max_tokens: int = 12288,
              conditionings: str = "message") -> dict:
    """Mean per-token NLL of each unit's gold diff under its bare and its
    aided prompt, with or without an adapter, for every *conditioning*
    named (comma-separated; ``message`` reads ``messages_bare`` /
    ``messages_aided`` and labels rows ``bare`` / ``aided`` as the first run
    did; any other reads ``messages_<c>_bare`` / ``_aided`` and labels rows
    ``<c>:bare`` / ``<c>:aided``). A unit that lacks a conditioning's chat
    gets a ``missing`` row. No sampling; batch of one; every unit whose
    encoding exceeds *max_tokens* is skipped and counted."""
    import time

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model)
    net = AutoModelForCausalLM.from_pretrained(model, dtype=torch.bfloat16, device_map="cuda")
    if adapter:
        from peft import PeftModel
        net = PeftModel.from_pretrained(net, f"/ttt/{adapter}")
    net.eval()
    rows, skipped, started = [], 0, time.time()
    for line in open(f"/ttt/{units}"):
        if not line.strip():
            continue
        unit = json.loads(line)
        prompts = []
        for c in [c.strip() for c in conditionings.split(",") if c.strip()]:
            label = "" if c == "message" else f"{c}:"
            keys = ("messages_bare", "messages_aided") if c == "message" else (f"messages_{c}_bare", f"messages_{c}_aided")
            prompts += [(label + "bare", keys[0]), (label + "aided", keys[1])]
        for arm, key in prompts:
            if key not in unit:
                rows.append({"unit": unit["id"], "prompt": arm, "missing": True})
                continue
            ids, labels, prompt_len, _ = _encode(tok, unit[key], None)
            if len(ids) > max_tokens:
                skipped += 1
                rows.append({"unit": unit["id"], "prompt": arm, "skipped": True, "tokens": len(ids)})
                continue
            with torch.no_grad():
                logits = net(input_ids=torch.tensor([ids], device="cuda")).logits[0].float()
            logp = torch.log_softmax(logits[:-1], dim=-1)
            target = torch.tensor(ids[1:], device="cuda")
            mask = torch.tensor(labels[1:], device="cuda") != -100
            tok_logp = logp.gather(1, target[:, None])[:, 0][mask]
            rows.append({"unit": unit["id"], "prompt": arm, "nll_mean": round(-tok_logp.mean().item(), 5),
                         "nll_sum": round(-tok_logp.sum().item(), 3), "target_tokens": int(mask.sum().item()),
                         "prompt_tokens": prompt_len})
        print(f"{unit['id']} done {int(time.time() - started)}s", flush=True)
    record = {"model": model, "adapter": adapter, "units": units, "conditionings": conditionings, "rows": rows,
              "skipped": skipped, "versions": _versions(), "gpu": torch.cuda.get_device_name(0),
              "wall_s": int(time.time() - started)}
    os.makedirs(os.path.dirname(f"/ttt/{out}"), exist_ok=True)
    json.dump(record, open(f"/ttt/{out}", "w"), indent=1, sort_keys=True)
    ttt.commit()
    return {"rows": len(rows), "skipped": skipped, "out": out, "wall_s": record["wall_s"]}


@app.function(
    image=serve_image, gpu=MODELS.get(MODEL, {}).get("gpu_serve", "A10G"), volumes=VOLUMES,
    secrets=[modal.Secret.from_name("hobbes-llm-key")], scaledown_window=600, timeout=60 * 60,
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=PORT, startup_timeout=30 * 60)
def serve():
    """vLLM for the base model plus every adapter named in ``ADAPTERS``;
    a request selects an arm by ``model``: the base name (A0/A1) or an
    adapter's name (A2/A3)."""
    cmd = ["vllm", "serve", MODEL, "--host", "0.0.0.0", "--port", str(PORT), "--served-model-name", MODEL,
           "--max-model-len", str(MODELS.get(MODEL, {}).get("max_model_len", 32768)),
           "--api-key", os.environ["HOBBES_LLM_API_KEY"], "--gpu-memory-utilization", "0.90"]
    adapters = [a for a in ADAPTERS.split(",") if a.strip()]
    if adapters:
        cmd += ["--enable-lora", "--max-lora-rank", str(RECIPE["rank"]), "--max-loras", str(max(1, len(adapters))),
                "--lora-modules", *[f"{a.split('=', 1)[0]}=/ttt/{a.split('=', 1)[1]}" for a in adapters]]
    subprocess.Popen(cmd)


def main(argv: list[str]) -> int:
    cmd, rest = (argv[1] if len(argv) > 1 else ""), argv[2:]
    if cmd == "deploy":
        os.execvp("modal", ["modal", "deploy", "--name", APP, __file__])
    if cmd == "url":
        print(modal.Function.from_name(APP, "serve").get_web_url().rstrip("/") + "/v1")
        return 0
    if cmd == "put" and len(rest) == 2:
        os.execvp("modal", ["modal", "volume", "put", "--force", "hobbes-ttt", rest[0], rest[1]])
    if cmd == "get" and len(rest) == 2:
        os.execvp("modal", ["modal", "volume", "get", "--force", "hobbes-ttt", rest[0], rest[1]])
    if cmd in ("train", "nll"):
        import argparse
        ap = argparse.ArgumentParser(prog=f"modal_ttt.py {cmd}")
        ap.add_argument("--model", default=MODEL)
        if cmd == "train":
            ap.add_argument("--corpus", required=True); ap.add_argument("--steps", type=int, default=300)
            ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out")
            a = ap.parse_args(rest)
            with app.run():
                print(json.dumps(train_adapter.remote(a.corpus, a.steps, a.seed, a.model, a.out), indent=1, sort_keys=True))
        else:
            ap.add_argument("--units", required=True); ap.add_argument("--out", required=True)
            ap.add_argument("--adapter"); ap.add_argument("--max-tokens", type=int, default=12288)
            ap.add_argument("--conditioning", default="message",
                            help="comma-separated: message (the first run's prompt), none, subject, task")
            a = ap.parse_args(rest)
            with app.run():
                print(json.dumps(score_nll.remote(a.units, a.out, a.adapter, a.model, a.max_tokens, a.conditioning), indent=1))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
