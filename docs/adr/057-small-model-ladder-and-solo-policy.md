# ADR-057 — The small-model ladder on owned compute, and the solo benchmark policy

**Date:** 2026-08-21
**Status:** accepted — steps 1–2 built and run live once (one instance,
both arms, 7B); the finding below is why the solo policy exists
**Amends:** `docs/hobbes-architecture.md` (§6.2); `docs/constraints/README.md`
(C-42); `docs/benchmark-hypotheses.md` (the focus benchmark and bar);
`docs/future_additions.md`; supersedes ADR-055's "no live run"

## Context

The owner's direction (2026-08-21): run the focus benchmark on **small
open models served from his own compute**, not paid APIs — which also
sharpens H1, since the 7B rung has **no published SWE-bench Verified
score** and is discouraged for multi-step agentic work, exactly the
regime derived context should help. The bar is set in rung form
(`benchmark-hypotheses.md`): **harnessed rung N ≈ pure rung N+1 on the
complex multi-step set** — Hobbes-on-7B vs pure-32B, Hobbes-on-32B vs
pure-next — measured on Verified's own `difficulty` label, not a proxy.

## Decision

1. **The ladder is served on Modal** (`pipeline/scripts/modal_vllm.py`):
   one vLLM OpenAI-compatible app per rung, GPU pinned per rung, weights
   cached in a volume, scale-to-zero, the endpoint token in the Modal
   secret `hobbes-llm-key`. Rungs are a pinned table; the first is
   `Qwen/Qwen2.5-Coder-7B-Instruct` (A10G), then `-32B-Instruct`
   (A100-80GB). vLLM 0.10.1.1 is pinned with **transformers <5** (5.x
   removed a tokenizer attribute this vLLM reads — found on the first
   cold start).
2. **Verified is the focus benchmark**, and `difficulty` is the depth
   axis (`hobbes bench select --difficulty complex` = the 45 instances
   rated `1-4 hours`/`>4 hours`). The report states the complex-set
   solve rate per arm and the rung-form comparison.
3. **The evaluator runs on Modal** too (`hobbes bench run --eval-modal`
   → `swebench[modal]`), removing the local-Docker item from ADR-055.
4. **The secrets loader** (`hobbes bench run --secrets FILE`) maps the
   owner's `name=value` file onto the env vars the tools read; unknown
   names are refused, values never printed.
5. **The solo benchmark policy** (`src/hobbes/bench/bench.box.policy`,
   passed automatically via `hobbes-session --box` plus
   `--escalation-timeout 5s`) — the fix for the finding below.

## The finding that forced the solo policy

First live instance (`psf__requests-1142`, 7B, both arms, real sandbox
over pasta):

- **Pure arm** completed: 4 tool calls (all text-embedded — the 7B
  writes tool calls as fenced JSON, which the loop now parses and
  counts, `text_tool_calls`), one `edit_file` whose `old_text` was
  absent, then a prose plan instead of a retry. **empty-patch**, ~20k
  tokens, 54s. A clean pure-7B datapoint.
- **Harness arm stalled.** ingest (121 nodes, 727 call edges) and plan
  (1 unit) were fine, but the flight log showed:
  ```
  16:52  exec escalate  pytest test_requests.py
  17:22  exec escalate  pytest test_requests.py          # 30 min later: expire-to-deny
  17:22  exec escalate  git add … && git commit …
  ```
  **Every exec the agent needed parked for the full 30-minute
  escalation window, then denied**, because a **benchmark checkout is a
  committed-only clone**: the repo and role policies live untracked
  under `.hobbes/`, so they never reach the session's worktree — only
  the derived agent policy (default `escalate`) and the box floor
  apply. With no human to approve (benchmarks run Hobbes alone), the
  arm could never run tests or commit, so it would produce an empty
  patch after an hour regardless of the model.

The run was stopped, not left to finish a meaningless result.

## The fix

A **solo box policy** the benchmark session always loads, allowing what
a lone implementer must do inside the already-sealed sandbox — the
repo's test runners (`pytest`, `python -m pytest`, `tox`, `go/cargo/npm
test`, verification one-liners), `pip install`, and `git add`/`commit`
(single **and** compound forms) — while the specific guarantees stay
**denied and win by deny-overrides** (`*.tfstate*`, `git push*`,
`git add *.hobbes/derived*`), and anything unlisted still escalates. A
`--escalation-timeout 5s` backstop means any residual escalate
expire-denies fast instead of parking 30 minutes. The OS sandbox is
unchanged and remains the real boundary (§5.2): worktree-only mounts,
no host secrets, network only the model endpoint.

Both defaults are overridable — a caller's own `--session-arg=--box=…`
or `--escalation-timeout=…` wins, so a run can tighten or replace them
deliberately.

## Consequences

- The benchmark path is runnable end to end on owned compute. The 7B
  endpoint is live; a full complex-set run (45 × 2 arms per rung) is the
  next session's job — see `docs/bench-run-handoff.md` *(a per-phase
  handoff since deleted; `docs/session-handoff.md` is the resume point,
  history in the BUILDLOG)*.
- **C-42** registered: a benchmark session runs under the solo box, not
  the repo/role policies, so its permissions are the benchmark's floor,
  not the repo owner's intent — stated in the record.
- Register already carries C-41 (a live session has egress and the
  endpoint token); C-42 is its policy-scope twin.
- Step 3 (Daytona sandboxes) stays parked in `future_additions.md`;
  local rootless podman served the first run.
- Tests: bench +2 (the shipped policy resolves as intended; the solo
  args default and override), loop +1 (text-embedded tool calls
  counted), Go +0 net (the `--escalation-timeout` flag). 769 pytest /
  Go green.

## The live endpoint (for the next session)

- 7B: `https://<modal-workspace>--hobbes-llm-qwen-qwen2-5-coder-7b-instruct-serve.modal.run/v1` *(concrete URL withheld from the public tree; `uv run pipeline/scripts/modal_vllm.py url` prints it)* — token in `secrets.txt` as `llm_key` and in the Modal
  secret `hobbes-llm-key`. `uv run pipeline/scripts/modal_vllm.py url`
  prints it; `MODEL=… deploy` (re)deploys a rung.

**Amendment (2026-08-22):** the second rung is `Qwen/Qwen3.8-27B`, not
`Qwen2.5-Coder-32B-Instruct` — Max's call; the reasoning is the dated
amendment in `benchmark-hypotheses.md`. Pinned in `RUNGS` on A100-80GB,
not deployed: the image's vLLM/transformers pins predate its architecture
and are bumped when the rung is taken.
