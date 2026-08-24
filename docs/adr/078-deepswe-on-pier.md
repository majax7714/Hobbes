# ADR-078 — DeepSWE on Pier: the referenced harness, both arms, Hobbes as a prompt aid

**Date:** 2026-08-22 · **Status:** accepted (first run done, one task per
arm) · **Realises:** the harness pivot (handoff STRATEGY §2), the DeepSWE
redirect (`docs/benchmark-deepswe.md`), ADR-077's aided shape. Relates to
C-39, C-49, C-55.

## Context

The benchmark left SWE-bench Verified (contaminated, C-39) for DeepSWE 1.1,
and the programme left the bespoke harness for a referenced one. Pier
(datacurve's Harbor fork, `datacurve-pier` 0.3.1 on PyPI — the PyPI name
`pier` is unrelated) runs DeepSWE tasks with `--agent mini-swe-agent` and
grades them with the task's own verifier. The 117 task definitions are in
the public `datacurve-ai/deep-swe` repo (`tasks/<id>/{task.toml,
instruction.md, environment/Dockerfile, tests/}`); the HF parquet is not
needed to run them. Pier builds the task image from a prebuilt
`public.ecr.aws/.../swe-bench-202605:<id>` base, installs mini-swe-agent
inside the container, runs the agent with `network_mode = "no-network"`
behind a squid egress proxy allowlisted to the model endpoint, then
collects `git diff <base> HEAD` and grades it in a separate verifier
container (F2P / P2P / reward).

## Decision

1. **Pier + mini-swe-agent is the substrate for both arms.** Nothing of
   ours runs inside the container. The only variable between arms is the
   prompt: the baseline arm gets `instruction.md` as Pier renders it; the
   Hobbes arm gets the same instruction followed by the ADR-077 aid,
   injected through Pier's own seam — `--ak prompt_template_path=<j2>`,
   a Jinja template that must contain `{{ instruction }}`. Pier renders
   it before mini-swe-agent sees the task, so the aid lands inside
   mini's `{{task}}` block unchanged. `pipeline/scripts/deepswe_run_arm.sh`
   launches one arm on one task.

2. **The aid is derived deterministically for now** —
   `pipeline/scripts/deepswe_aid.py`: `hobbes ingest` the task repo at
   `base_commit_hash`, `hobbes plan "<instruction>"` for its lexical seeds
   (the files the change centres on), graph symbols whose *capitalised*
   name appears in the instruction, their one-hop neighborhood
   (`_named_symbol_neighborhood`), and the tests that reach the seed module
   whose filename shares a token with the instruction. The text is spliced
   out of `hobbes.run.stages.aided_brief` so the wording is ADR-077's, minus
   its "How to work" section (DeepSWE's instruction carries its own
   branch-and-commit rule, which that section would contradict). The
   planner LLM stage is **not** run — its `approach` prose is absent. This
   is a prototype of the injection point, registered as C-55; the planner
   stage is the next thing to wire in.

3. **Text-based actions for the 7B.** mini's default config is native
   tool-calling; our 7B endpoint answers a tool request with a pseudo-XML
   `<tool_call>` block in `content` that vLLM's parser does not recognise,
   so every turn is "no tool call" and the run dies in three turns
   (`RepeatedFormatError`). Both arms run `model_class=litellm_textbased`
   with mini's `mini_textbased.yaml` (one triple-backtick action per
   turn). The 27B should be tried on the native path before being moved.

4. **Docker, not podman, drives Pier here.** Pier shells out to
   `docker compose`; the box has Docker Engine 29 with compose v5 and
   BuildKit, and they work. The podman socket also answers the Docker CLI
   (`DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`) and is the
   fallback if Docker is removed. First-time builds must not race a cold
   registry: BuildKit's metadata fetch for the 4 GB ECR base timed out
   (`DeadlineExceeded`) and killed the trial before anything ran;
   `docker pull` the task image first.

## The first run (one task per arm, 7B, 2026-08-22)

Task `httpx-multipart-response-parsing` (encode/httpx @ `b5addb6`, 301-word
instruction, 122 F2P / 1272 P2P). Both arms reward 0, empty patch, P2P
1272/1272 (verifier graded the unchanged tree). What differed:

- **baseline** — 100 API calls, 11 m 53 s, `ContextWindowExceededError`.
  Never opened a source file. Its first action was `git checkout -b … &&
  cd path/to/httpx/repository && git pull origin main`; from there it
  spent the whole budget on the fictitious remote (`git remote add origin
  https://github.com/your-repo/...`, DNS, `sudo`, `nano`, `apt-get`),
  repeating the same 10-turn cycle.
- **hobbes** — 17 API calls, 1 m 42 s, `ContextWindowExceededError`. Second
  action was reading `httpx/_models.py` (the aid's named file); it then
  `cat` the whole file, got "output too long", and repeated the identical
  response twelve times until the window filled. The aid **localised the
  model on turn 2**; the 7B's own execution (no repeat-refusal in mini,
  unlike ADR-066's) ended it.

Read as a Hobbes checker (the 7B's role since the aided read): the
injection reaches the agent, changes what it does first, and the verifier
grades the result — the loop is wired. It is not a capability claim.

## Consequences

- `hobbes bench` (our harness, ADR-055..077) is no longer the path for
  DeepSWE; it stays for Verified-shaped runs and as the reference for the
  interface Pier must keep satisfying (per-unit context injection is the
  one piece Pier gives us; write scope, policy boundary, and the
  partition record are not in this path by design — ADR-077's aided mode
  already dropped the fence).
- The two arms' metering is Pier's ATIF trajectory (`agent/trajectory.json`,
  tokens per step) — one meter, both arms.
- Next: (a) the planner stage into the aid (C-55); (b) a second task in a
  non-Python language to exercise the multi-language ingest; (c) the 27B on
  the native tool path; (d) the diversified small-model set.
- Working tree for runs: `~/.hobbes/deepswe/` (venv, `deep-swe/` clone,
  `repos/<name>` ingested checkouts, `aid/<task-suffix>.j2`, `pier.env`,
  `jobs/`). Nothing there is versioned; the two scripts are.
