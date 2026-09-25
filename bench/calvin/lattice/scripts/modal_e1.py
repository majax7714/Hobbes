# /// script
# requires-python = ">=3.12"
# dependencies = ["modal>=1.1"]
# ///
"""E1's batch generator on Modal (`calvin-experiments.md` §6, route E1-f). **Written, not yet run.**

    uv run bench/calvin/lattice/scripts/modal_e1.py \
        --model Qwen/Qwen2.5-Coder-7B-Instruct \
        --requests requests.jsonl --out completions.jsonl [--call call.json]

One offline vLLM batch per call — no served endpoint. A serve costs idle time, and its per-request seed is
weaker than `SamplingParams(seed=…)` on an offline batch, which is what makes a sample reproducible
(E1-d). One call answers a whole round, and the 465 prompts of one model share their prefix, so
`enable_prefix_caching` is on.

**The pins are the ones both 7Bs already ran under** for ADR-099 (`pipeline/scripts/modal_ttt.py`): vLLM
0.27.1, `transformers>=5.8`, `VLLM_USE_FLASHINFER_SAMPLER=0`, an A10G at a 16k window, and the weights in
the `hobbes-hf-cache` volume. :data:`MODELS` is the whole of what may run: a model this table does not name
is refused rather than downloaded, because a run at an unpinned model is not the run the record describes.

**The lattice package never imports `modal`.** This is a `uv run` script with its own dependencies, and
`lattice.e1.modal_generator` reaches it through a subprocess and two JSONL files. A dispatched session has
neither `modal` nor a route to it, which is why this file is written here and first run by the developer.

A request is one row of `lattice e1 plan`'s `requests.jsonl`: `mode` `chat` with `messages`, or `mode`
`complete` with a raw `prompt` (the G-mem probes, which are continuations and not conversations), plus
`params` — `temperature`, `top_p`, `max_tokens`, `seed`. A completion is `{"id", "text", "tokens_in",
"tokens_out", "finish_reason"}`, and the call record beside it gives the seconds inside the function and
what they cost at :data:`USD_PER_SECOND`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import modal

#: The app. One function, one purpose; nothing here is deployed or served.
APP = "hobbes-e1"

#: The vLLM pin. Both 7Bs have run under it on this account (ADR-099).
VLLM = "0.27.1"

#: **The whole of what may run.** A model outside this table is refused by :func:`generate`.
MODELS = {
    "Qwen/Qwen2.5-Coder-7B-Instruct": {"gpu": "A10G", "max_model_len": 16384},
    "allenai/Olmo-3-7B-Instruct": {"gpu": "A10G", "max_model_len": 16384},
}

#: The GPU's price per second, for the call record only. A10G at about $1.10/h.
#: **Check this against Modal's pricing page before the first run** — it is a constant here, not a quote.
USD_PER_SECOND = 1.10 / 3600

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(f"vllm=={VLLM}", "transformers>=5.8", "huggingface_hub>=0.34")
    .env({"VLLM_USE_FLASHINFER_SAMPLER": "0"})
)
weights = modal.Volume.from_name("hobbes-hf-cache", create_if_missing=True)
app = modal.App(APP)


class UnpinnedModel(Exception):
    """That model is not in :data:`MODELS`, so it was not run."""


@app.function(image=image, gpu="A10G", volumes={"/root/.cache/huggingface": weights}, timeout=4 * 3600)
def generate(model: str, requests: list[dict]) -> dict:
    """Answer every request in one offline batch, and say how long it took inside this function.

    The return is a mapping and not a bare list because the seconds are the call's and not any one
    request's: `lattice.e1` prices a call from them, and the entrypoint's own wall time would carry the
    cold start and the image pull with it.

    The two modes go through the two vLLM entry points — `chat` applies the model's own chat template,
    `complete` does not, and a G-mem probe is a raw continuation that a chat template would wrap into a
    question. Each request carries its own `SamplingParams`, so the seed is per request.
    """
    from vllm import LLM, SamplingParams

    pinned = MODELS.get(model)
    if pinned is None:
        raise UnpinnedModel(f"{model!r} is not one of {', '.join(sorted(MODELS))}")

    started = time.time()
    llm = LLM(model, max_model_len=pinned["max_model_len"], enable_prefix_caching=True, seed=0)

    chats = [request for request in requests if request.get("mode") == "chat"]
    raw = [request for request in requests if request.get("mode") != "chat"]
    answers: list[dict] = []
    if chats:
        outputs = llm.chat(
            [request["messages"] for request in chats], [_params(SamplingParams, request) for request in chats]
        )
        answers += [_answer(request, output) for request, output in zip(chats, outputs)]
    if raw:
        outputs = llm.generate(
            [request["prompt"] for request in raw], [_params(SamplingParams, request) for request in raw]
        )
        answers += [_answer(request, output) for request, output in zip(raw, outputs)]

    seconds = round(time.time() - started, 3)
    return {"model": model, "completions": answers, "seconds": seconds, "requests": len(requests)}


def _params(SamplingParams, request: dict):
    """One request's sampling settings, as the plan wrote them. Nothing is defaulted in here."""
    params = request["params"]
    return SamplingParams(
        temperature=params["temperature"],
        top_p=params["top_p"],
        max_tokens=params["max_tokens"],
        seed=params["seed"],
    )


def _answer(request: dict, output) -> dict:
    """One completion, keyed by the request's id: the text whole, the two token counts, and why it stopped."""
    first = output.outputs[0]
    return {
        "id": request["id"],
        "text": first.text,
        "tokens_in": len(output.prompt_token_ids or []),
        "tokens_out": len(first.token_ids or []),
        "finish_reason": first.finish_reason,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="modal_e1.py", description="E1's offline vLLM batch on Modal")
    parser.add_argument("--model", required=True, help=f"one of {', '.join(sorted(MODELS))}")
    parser.add_argument("--requests", required=True, help="a requests JSONL from `lattice e1 plan`")
    parser.add_argument("--out", required=True, help="where the completions JSONL goes")
    parser.add_argument("--call", help="where the one-line call record goes (default: <out>.call.json)")
    args = parser.parse_args(argv[1:])

    if args.model not in MODELS:
        print(f"modal_e1: {args.model!r} is not pinned; the models are {', '.join(sorted(MODELS))}", file=sys.stderr)
        return 2

    requests = [json.loads(line) for line in open(args.requests, encoding="utf-8") if line.strip()]
    started = time.time()
    with app.run():
        answer = generate.remote(args.model, requests)
    wall = round(time.time() - started, 3)

    with open(args.out, "w", encoding="utf-8") as handle:
        for completion in answer["completions"]:
            handle.write(f"{json.dumps(completion, sort_keys=True)}\n")

    record = {
        "model": answer["model"],
        "requests": answer["requests"],
        "completions": len(answer["completions"]),
        # `seconds` is the function's own time (the weight load and the batch). The call is priced on the
        # host's wall around the remote call, which also holds the queue, the container's boot and the app's
        # setup: an upper bound on the GPU time Modal bills, and a ceiling wants the high side (session
        # `66c5`'s review). Modal's own bill is what the first unit is compared against.
        "seconds": answer["seconds"],
        "wall_seconds": wall,
        "cost": round(wall * USD_PER_SECOND, 6),
        "cost_basis": "host wall around the remote call (an upper bound)",
        "usd_per_second": USD_PER_SECOND,
        "vllm": VLLM,
    }
    with open(args.call or f"{args.out}.call.json", "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
    print(json.dumps(record, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
