# Referencing mini-swe-agent as the harness — validated recipe

> **Retracted as a Hobbes arm (P12, ADR-082, 2026-08-23).** The shape
> this doc validates — one mini-swe-agent given the whole task with
> Hobbes's context prepended — is *model + prompt*, not a Hobbes test:
> no planner-defined units, one agent, a window that holds the task.
> The recipe is kept as the record of the referenced-harness wiring and
> as the **baseline** substrate (the *model + prompt* arm Hobbes is
> measured against); it must never be labelled the Hobbes arm again.

**Status:** integration **validated end-of-wiring** 2026-08-22 (not yet
run on containers). This was the first concrete step of the harness
pivot (see `docs/session-handoff.md`): stop hand-forging our own agentic
loop, ride a mature one, and make Hobbes's derived context the only
variable. It is also the check on a real suspicion — **the 7B's "cannot
execute on derived context" verdict came only from our own defect-ridden
harness** (every void this session was the harness starving the arm), so
the first use is a clean 7B re-run through mini-swe-agent.

## Why mini-swe-agent

It is the minimal SWE-agent (v2.4.6, `pip install mini-swe-agent`): a
bash-only agent loop with a batch SWE-bench runner, a litellm model layer,
and a docker/podman environment. Small enough to read in an afternoon,
and its seams line up with ours:

- **Model** — litellm. Points at our 7B/27B Modal endpoints with the
  `openai/` provider. **Validated:** a completion against the 7B endpoint
  returns content (set `MSWEA_COST_TRACKING=ignore_errors` — litellm has
  no price row for a local model and errors on cost calc otherwise).
- **Environment** — `DockerEnvironment.executable` honours
  `MSWEA_DOCKER_EXECUTABLE`, so **`podman`** drives it (5.8.4 here), and
  it builds the *exact* image names we already pull
  (`docker.io/swebench/sweb.eval.x86_64.<id with __→_1776_>:latest`).
- **Injection point** — `agent.instance_template` (the `{{task}}` block).
  Hobbes's derived per-unit context is prepended here for the Hobbes arm;
  the baseline arm leaves it stock.
- **Output** — a standard SWE-bench predictions file
  (`{instance_id: {model_patch}}`), which our evaluator
  (`hobbes.bench.verdict`, local podman socket, C-50) reads directly.
- **Action format** — use `swebench_backticks.yaml` (triple-backtick text
  actions), not the default tool-call config: more robust for a 7B.

## The two questions, two arms

1. **Did our harness suppress the 7B?** (the immediate suspicion)
   *mini baseline 7B* (single agent, self-discovery) vs our earlier
   *bespoke-harness 7B* (0/5). If mini executes cleanly / scores > 0, our
   harness — not the model — was the wall. This is the ~30-minute run.
2. **Does derived context help, on a neutral harness?** (the pivot proper)
   *mini + Hobbes-injected context* vs *mini baseline*, same model. The
   real H1 test, on a harness whose quality is a constant, not a confound.

## The baseline command (run AFTER the 27B run finishes — shared podman)

```sh
cd /tmp/.../msevenv            # or a project venv; pip install mini-swe-agent
export MSWEA_COST_TRACKING=ignore_errors
export MSWEA_DOCKER_EXECUTABLE=podman
export OPENAI_API_KEY=$(grep '^llm_key=' "$HOBBES_REPO/secrets.txt" | cut -d= -f2-)
export OPENAI_API_BASE=<the 7B vLLM endpoint>/v1   # modal_vllm.py url prints it
python -m minisweagent.run.benchmarks.swebench \
  --subset "$HOBBES_REPO/verified.jsonl" --split test \
  --filter '(django__django-11400|sympy__sympy-13852|pydata__xarray-3993|sphinx-doc__sphinx-8548|scikit-learn__scikit-learn-25102)' \
  -m openai/Qwen/Qwen2.5-Coder-7B-Instruct \
  -c <path>/config/benchmarks/swebench_backticks.yaml \
  --environment-class docker -w 4 \
  -o ~/.hobbes/bench/mini-7b-baseline
# then evaluate the preds file with the pinned swebench evaluator
# (local podman socket), the same verdict as our own runs.
```

## Sequencing / cautions

- **Do not run mini's containers while a `hobbes bench` run is active** —
  they share the rootless podman and would contend and confound. Run
  after the current 27B run finishes.
- The 7B and 27B are **separate Modal apps** (different GPUs), so hitting
  the 7B endpoint does not contend with a 27B run's endpoint.
- `~/.config/mini-swe-agent/.env` exists on this box — check it does not
  carry a stale key/base that overrides the exports.
- Migration risk is at the **injection point**: mini assumes the model
  *discovers* context; Hobbes *supplies* it. Prototype arm 2 on one
  instance before a full set.
