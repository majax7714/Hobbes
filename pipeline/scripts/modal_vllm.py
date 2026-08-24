# /// script
# requires-python = ">=3.12"
# dependencies = ["modal>=1.1"]
# ///
"""Serve one rung of the model ladder on Modal with vLLM (ADR-057).

    MODEL=Qwen/Qwen2.5-Coder-7B-Instruct uv run pipeline/scripts/modal_vllm.py deploy
    uv run pipeline/scripts/modal_vllm.py url        # print the endpoint root

One app per rung (``hobbes-llm-<slug>``), an OpenAI-compatible server
at ``/v1`` behind a bearer token read from the Modal secret
``hobbes-llm-key`` (``HOBBES_LLM_API_KEY``) — the same variable the
agent loop and ``hobbes bench`` read on the host, so one value serves
both ends. Weights are cached in a Modal volume across cold starts.
The GPU per rung is pinned in ``RUNGS``; a model outside the table is
refused rather than guessed at. Scales to zero when idle.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import modal

#: The ladder, rung → (GPU, vLLM flags). Pinned; a rung is added by
#: editing this table, never by a flag.
RUNGS: dict[str, dict] = {
    "Qwen/Qwen2.5-Coder-7B-Instruct": {
        "gpu": "A10G", "max_model_len": 32768, "tool_parser": "hermes",
    },
    "Qwen/Qwen2.5-Coder-32B-Instruct": {
        "gpu": "A100-80GB", "max_model_len": 32768, "tool_parser": "hermes",
    },
    # The next rung after 7B (Max, 2026-08-22 — benchmark-hypotheses.md
    # "Amendment"; the 32B stays pinned but is no longer next). 27.8B
    # dense, arch Qwen3_5ForConditionalGeneration (ADR-074): a hybrid —
    # 48 of 64 layers linear attention, 16 full attention with 4 KV
    # heads — so the KV cost is ~65 KB/token and the 80 GB card holds
    # ~250k tokens of KV beside the bf16 weights (~56 GB). The window
    # is pinned at 128k: half the native 262k, chosen so the brief the
    # harness sizes to it (ADR-069, 35 %) stays ~45k tokens, and so
    # five instances' sessions share the pool without thrashing. A
    # *thinking* model: the chat template opens every assistant turn
    # with <think>, and without the reasoning parser the whole block
    # lands in message.content and eats max_tokens before the answer
    # starts (vLLM's recipe). Text-only serving: the vision tower is
    # not loaded. Needs vLLM ≥ 0.17 (the architecture) and
    # transformers ≥ 5.8 (the config's writer).
    "Qwen/Qwen3.8-27B": {
        "gpu": "A100-80GB", "max_model_len": 131072, "tool_parser": "qwen3_coder",
        "reasoning_parser": "qwen3", "extra": ["--language-model-only"],
    },
}

MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
if MODEL not in RUNGS:
    sys.exit(f"modal_vllm: {MODEL!r} is not a pinned rung; known: {', '.join(RUNGS)}")
RUNG = RUNGS[MODEL]
SLUG = re.sub(r"[^a-z0-9]+", "-", MODEL.lower()).strip("-")
APP = f"hobbes-llm-{SLUG}"
PORT = 8000
#: One image for every rung. Bumped 0.10.1.1 → 0.27.1 for the 27B's
#: architecture (ADR-074); the 7B re-verified on it the same day.
VLLM = "0.27.1"

image = (
    modal.Image.debian_slim(python_version="3.12")
    # ADR-057 pinned transformers <5 because vLLM 0.10 read tokenizer
    # attributes 5 removed; vLLM 0.27 is built on 5, and the 27B's
    # config.json is written by 5.8 (ADR-074).
    .pip_install(f"vllm=={VLLM}", "transformers>=5.8", "huggingface_hub>=0.34")
    # MODEL is read from the environment at import, and this file is
    # imported again *inside* the container, where the host's MODEL is
    # not set: without baking it into the image every app served the
    # default rung under its own name (the 27B app came up as the 7B
    # on an A100 — found on the first cold start, ADR-074).
    # vLLM 0.27 JIT-builds flashinfer's sampling kernels at engine start,
    # which needs nvcc — absent in this image, and the engine core died
    # on it (the 27B's first cold start spent the whole startup timeout
    # waiting on a dead engine). The torch sampler is the documented
    # alternative and needs nothing built.
    .env({"MODEL": MODEL, "VLLM_USE_FLASHINFER_SAMPLER": "0"})
)
weights = modal.Volume.from_name("hobbes-hf-cache", create_if_missing=True)
app = modal.App(APP)


@app.function(
    image=image,
    gpu=RUNG["gpu"],
    volumes={"/root/.cache/huggingface": weights},
    secrets=[modal.Secret.from_name("hobbes-llm-key")],
    scaledown_window=600,
    timeout=60 * 60,
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=PORT, startup_timeout=30 * 60)
def serve():
    """vLLM's OpenAI-compatible server for this rung."""
    cmd = [
        "vllm", "serve", MODEL,
        "--host", "0.0.0.0", "--port", str(PORT),
        "--served-model-name", MODEL,
        "--max-model-len", str(RUNG["max_model_len"]),
        "--enable-auto-tool-choice", "--tool-call-parser", RUNG["tool_parser"],
        "--api-key", os.environ["HOBBES_LLM_API_KEY"],
        "--gpu-memory-utilization", "0.92",
    ]
    if RUNG.get("reasoning_parser"):
        # Thinking models: reasoning lands in message.reasoning_content,
        # never in content (the loop keeps it on the transcript).
        cmd += ["--reasoning-parser", RUNG["reasoning_parser"]]
    cmd += RUNG.get("extra", [])
    subprocess.Popen(cmd)


def main(argv: list[str]) -> int:
    if argv[1:] == ["url"]:
        fn = modal.Function.from_name(APP, "serve")
        print(fn.get_web_url().rstrip("/") + "/v1")
        return 0
    if argv[1:] == ["deploy"]:
        os.execvp("modal", ["modal", "deploy", "--name", APP, __file__])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
