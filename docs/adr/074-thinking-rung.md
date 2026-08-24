# ADR-074 — The thinking rung: serving Qwen3.8-27B and what the loop sends

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-056 (the
owned loop's request), ADR-057 (the ladder's image and rungs; its
2026-08-22 amendment named this rung).

## Context

Four 7B runs on 2026-08-22 read the rung as done: the planner now
localises from derived context and the implementer still writes from
memory, with no known harness defect left in the record (BUILDLOG
fifty-fifth to fifty-eighth). Max's go: take the next rung,
**Qwen3.8-27B**, the 7B runs having been inspected down to the model's
limit.

The rung is not a bigger Qwen2.5-Coder. `Qwen/Qwen3.8-27B` is a 27.8B
dense **hybrid** (48 of 64 layers linear attention, 16 full attention
with 4 KV heads), natively multimodal (`Qwen3_5ForConditionalGeneration`),
262k context, and a **thinking model**: its chat template opens every
assistant turn with `<think>`, reasoning depth is a request field
(`reasoning_effort`), and earlier turns' reasoning is kept in context
by default (`preserve_thinking`). Its card warns greedy decoding loops
the reasoning and gives its own sampling. The image pinned for the 7B
(vLLM 0.10.1.1, transformers <5) predates the architecture; vLLM's
recipe for the model wants ≥ 0.17 and transformers ≥ 5.8, and says the
reasoning parser "is not optional in practice" — without it the whole
reasoning block lands in `message.content` and a small `max_tokens` is
spent before the answer starts.

## Decision

1. **One image, bumped.** `scripts/modal_vllm.py` pins `vllm==0.27.1`
   and `transformers>=5.8` for every rung; the 7B is re-verified on
   the new image the same day (the ladder's H1 comparison rests on the
   same server code at both rungs).
2. **Per-rung serving flags.** A rung entry may carry a
   `reasoning_parser` and `extra` flags beside the GPU, window and tool
   parser. The 27B: A100-80GB, `qwen3_coder` tool parser, `qwen3`
   reasoning parser, `--language-model-only` (text serving; the vision
   tower is not loaded), window **131,072**. Half the native window,
   declared: the KV budget beside the bf16 weights is ~250k tokens on
   the card (16 full-attention layers × 4 KV heads × 256 dims ≈ 65
   KB/token), and the brief the harness sizes to the window (ADR-069,
   35 %) is then ~45k tokens — large, but not the whole pool for one
   session while five instances share the endpoint.
3. **The loop sends what a thinking model needs, and keeps what it
   returns.** `loop.py` gains `--temperature` (default 0, the ladder's
   greedy), `--top-p`, `--reasoning-effort`, and `--thinking
   server|on|off` (`chat_template_kwargs.enable_thinking`; a template
   without the switch ignores it). A reply's `reasoning_content` goes
   back on the assistant message as received — so the server's
   `preserve_thinking` sees it, and the transcript shows why the model
   acted, not only what — and `usage.reasoning_tokens` is counted from
   `completion_tokens_details` when reported (0 when absent: observed,
   never inferred). The envelope carries `sampling`.
4. **One declaration, both arms.** `bench.Runtime` carries the sampling;
   the pure arm gets it on the loop's argv, the harness arm through a
   new generic `hobbes-session --loop-arg` (repeatable, forwarded to
   the runtime verbatim after the launcher's own flags — the launcher
   does not learn flag names). `run.json` records it.
5. **The 27B run's settings are pre-registered** in
   `docs/benchmark-hypotheses.md` before the run: thinking on at the
   server's default, `reasoning_effort=medium`, the card's thinking-mode
   sampling (temperature 1.0, top-p 0.95), `max_tokens` 8192 (the cut
   retry gives 16k), the same five instances, `--human-first spawn`.

## Consequences

- The loop's default request is unchanged (temperature 0, nothing
  else) — every 7B record stays comparable with itself.
- Sampling at temperature 1.0 makes both arms non-reproducible by
  design; the 7B's pure arm was already not reproducible at 0 (the
  batching server is order-dependent). n=1 per instance stays the
  reading rule's caveat.
- `completion_tokens` includes reasoning on vLLM; H3's cost row counts
  it, and `reasoning_tokens` beside it says how much was thinking.
- Two things the first cold start found, both in `modal_vllm.py` now:
  **`MODEL` must be baked into the image env** — the script is imported
  again inside the container, where the host's `MODEL` is unset, so the
  27B app came up serving the 7B under its own name; and **vLLM 0.27
  JIT-builds flashinfer's sampling kernels at engine start**, which
  needs `nvcc` the image lacks — the engine core died and the runner
  waited out the whole startup timeout on a dead port;
  `VLLM_USE_FLASHINFER_SAMPLER=0` (the torch sampler) is set. Measured
  on the A100: 305,068 KV tokens (19.05 GiB), 2.33× concurrency at the
  full window; the smoke completion split reasoning from content and
  returned a structured tool call.
- vLLM 0.27.1 reports no `completion_tokens_details`, so
  `usage.reasoning_tokens` reads 0 on this rung: the reasoning is on
  the transcript but its token count is inside `completion_tokens`,
  unsplit. Stated here so the H3 row is read right.
- Tests: `TestThinkingRung` (request fields, the switch, reasoning on
  the transcript and counted, malformed counts zero),
  `TestRuntimeSampling` (one declaration → launcher flags and record),
  the pure-arm loop test now runs with the thinking sampling and reads
  it off the request, Go `TestRuntimeMaxTurnsReachesTheLoop` (loop args
  follow verbatim).
