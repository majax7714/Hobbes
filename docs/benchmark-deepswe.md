# Redirecting the benchmark to DeepSWE 1.1 (Max, 2026-08-22)

> **P12 note (ADR-082, 2026-08-23).** The Pier/mini-swe pairs this doc's
> runs produced are retracted as *Hobbes* evidence: an aided single agent
> is *model + prompt* whatever its score. The redirect itself stands —
> DeepSWE 1.1 remains the uncontaminated set, and the Pier substrate
> remains the *model + prompt* baseline a decomposed Hobbes run (P12)
> will be measured against. Experiments are parked pending Max's go
> (`docs/session-handoff.md`).

**Why the shift.** SWE-bench Verified is contaminated and, worse for us,
**asymmetrically** (C-39 amended): the 27B pure arm reproduced xarray's
gold patch verbatim including the author's `0.19.0` deprecation target, so
its "solves" are recall, and recall favors the undivided arm the partition
denies. On a contaminated set, Hobbes's break-up looks invalid *by design*.
At this stage the value is **trustworthy reasoning traces**, not compared
scores — which needs a set the model cannot recall. Verified cannot give
that; a benchmark where Qwen scores low (headroom, no recall shortcut) can.

**What DeepSWE 1.1 is** (datacurve-ai, arxiv 2607.07946). 113 **original,
long-horizon** SWE tasks across **TypeScript, Go, Python, JavaScript,
Rust**, built explicitly against SWE-bench's two flaws: (1) mined public
fixes are in pretraining → recall not problem-solving; (2) shipped tests
grade one specific fix. DeepSWE uses **original tasks** (not mined merges)
and a **behavior-based verifier** that "accepts any solution with correct
observable behavior" — an independent LLM judge disagrees with it ~**1.4%**
vs 32.4% for SWE-bench Pro's inherited tests. This removes, at once:
- **contamination** (C-39) — original tasks, held-out, gated;
- **the one-solution proxy** (C-49) — behavior, not the gold test;
- and (via Pier) **our bespoke exec/policy/partition harness** entirely.

Its multi-language mix (all five languages Hobbes extracts) is a genuine
fit for Hobbes's breadth, not just Python.

**How it runs — and why it *is* the harness pivot.** DeepSWE tasks are
Harbor-format and run with **Pier** (github.com/datacurve-ai/pier, 0.3.0+):

    pier run -p deep-swe/tasks --agent mini-swe-agent --model <ours>

Pier natively supports **mini-swe-agent** (also claude-code, codex,
gemini-cli, opencode) and arbitrary models. So the substrate is the one we
already validated (mini-swe-agent, `docs/harness-mini-swe-integration.md`),
pointed at our Modal 7B/27B endpoints, on an uncontaminated benchmark with
a behavior verifier. **Hobbes's job** becomes purely its research core:
inject derived context ("here is the task, what we can see, what we can't")
into the agent's prompt — the ADR-077 aided shape — and compare against the
same agent without it. No partition, no write-scope, no swebench evaluator.

Per-task layout: `task.toml` (repo, commit, language, image, limits),
`instruction.md` (the prompt), `environment/Dockerfile`, `tests/` (the
verifier), `solution/` (withheld). v1.1 uses a separate verifier
environment: agents commit in an isolated sandbox and a
`[[verifier.collect]]` hook grades the commit in a pristine container.

## What it needs (blockers, in order)

1. **Access — the gate.** `datacurve/deep-swe` is gated (`gated: auto`) and
   there is **no HF token in `secrets.txt`**. Max must accept the dataset
   terms on Hugging Face and add an HF token (e.g. `hf_token=…`) to
   `secrets.txt`. Without this nothing downloads. (The GitHub repo carries
   the task *definitions*; the parquet/tasks are gated on HF.)
2. **Install Pier 0.3.0+** and confirm it drives podman (we run rootless
   podman; Pier is Harbor-compatible — verify the container backend).
3. **Model wiring.** Point Pier's mini-swe-agent at our Modal endpoints —
   the litellm path is already validated (`MSWEA_COST_TRACKING=ignore_errors`,
   `openai/…` provider, our bearer token).
4. **Hobbes injection point.** Prototype adding the derived-context block
   to mini-swe-agent's prompt within Pier (the aided_brief content:
   task + what-we-can-see + what-we-can't). This is where migration effort
   concentrates — prototype on one task before a full run.
5. **Ingest for the derived context.** `hobbes ingest` each task's repo at
   its `task.toml` commit to produce the graph the aid is drawn from
   (multi-language — Hobbes covers all five).

## Sequencing

The in-flight 7B Verified aided run finishes and is inspected (its value is
the aided-flow *trace*, not its score — the 7B could not recall xarray, so
its behavior is honest). Then redirect: access → Pier → one-task
prototype (baseline mini-swe vs mini-swe+Hobbes-context) → a diversified
DeepSWE selection set. The small-model-validates-the-derivation rule
(hobbes-harness-strategy) applies unchanged.

## Status (2026-08-22, ADR-078) — substrate up, one task per arm run

All five blockers above are cleared or prototyped: access (HF_token —
not even needed, the task definitions are public in the GitHub repo);
`datacurve-pier` 0.3.1 installed in `~/.hobbes/deepswe/venv` (py3.12),
driving the box's Docker Engine directly; model wiring via Pier's
`--env-file pier.env` (`OPENAI_API_BASE` = Modal 7B, `OPENAI_API_KEY`)
with **text-based actions** (`model_class=litellm_textbased` +
`mini_textbased.yaml` — the 7B cannot do native tool calls on our
endpoint); injection via `--ak prompt_template_path=<j2>` with the aid
from `pipeline/scripts/deepswe_aid.py` (deterministic, no planner stage —
C-55); ingest of the task repo at `base_commit_hash` under
`~/.hobbes/deepswe/repos/`. First run on `httpx-multipart-response-parsing`
(7B): both arms reward 0 / empty patch; baseline never opened a file
(100 calls), Hobbes arm localised on turn 2 then looped (17 calls). Full
read in ADR-078. Pre-pull a task's ECR image before its first trial.
