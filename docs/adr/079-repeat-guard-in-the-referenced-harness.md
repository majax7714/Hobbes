# ADR-079 — The repeat refusal rides into the referenced harness

**Date:** 2026-08-22 · **Status:** accepted · **Relates to:** ADR-066 (the
owned loop's repeated-edit refusal), ADR-078 (DeepSWE on Pier), C-46.

## Context

The first Pier run (ADR-078) ended both arms in `ContextWindowExceededError`.
The Hobbes arm's trace was twelve consecutive, byte-identical responses —
the 7B re-sent the same `cat httpx/_models.py` after every "output too
long" warning until the 32 k window filled. Max: "should never have the
same response 12×." Our owned loop already refused a repeated identical
edit (ADR-066) and fit the window by eliding old tool results (C-46);
mini-swe-agent has neither. It clips each observation to ~10 k characters
(head 5 k + tail 5 k and a warning) but keeps every clipped observation in
the conversation and never shrinks `max_tokens` — so a model that stops
reading its observations fills the window at a fixed rate, and the run
ends on the provider's 400 rather than on anything the harness decided.

Pier installs mini-swe-agent inside the task container at agent setup
(`uv tool install`); nothing of ours is there unless we put it there.

## Decision

1. **A mini-swe-agent agent class of ours, installed into Pier's agent
   venv:** `pipeline/scripts/deepswe/hobbesmini/` — `RepeatGuardAgent`
   subclasses mini's `DefaultAgent` and overrides `execute_actions`. An
   action identical (whitespace-normalised) to the previous one is **not
   executed**; the model receives a refusal observation in mini's own
   observation template (`REFUSED: this is the same command as your
   previous action (repeated n×) … do something different`), and after
   `max_repeats` consecutive refusals (default 3) the run exits
   `RepeatedActionError` with `repeats_refused` in the trajectory's
   `model_stats`. A different action resets the streak. The verdict is a
   pure function (`hobbesmini/guard.py`) with its own pytest; the agent
   class is smoke-tested in the Pier venv against a stub model.
2. **It rides in through Pier's seams, not a fork.** Pier bakes the agent
   install into the task image at **build** time (`agent-build-context/
   Dockerfile`), so a runtime mount cannot carry the package (the first
   attempt did exactly that and failed `Distribution not found at
   file:///opt/hobbesmini`). The package is built as a wheel
   (`uv build --wheel`) and served from the host on the docker bridge
   address only (`python3 -m http.server 8765 --bind 172.17.0.1`,
   unreachable from the LAN); `--ak extra_python_packages=["http://
   172.17.0.1:8765/hobbesmini-0.1.0-py3-none-any.whl"]` has Pier's
   install step `uv pip install` it into mini's interpreter. The config
   (`mini_hobbes_textbased.yaml` = mini's `mini_textbased.yaml` +
   `agent.agent_class: hobbesmini.RepeatGuardAgent`, or
   `mini_hobbes_native.yaml` for the tool-calling path) selects it via
   mini's own `agent_class` key. **Both arms get the guard** — it is
   harness hygiene, not derived context, so it must not be a variable.
3. **Window-fit is not ported.** C-46's elision changes what the model
   sees and would be a second variable; the guard only stops the one
   degenerate loop that produced the overflow. If a capable model
   overflows while doing real work, that is the signal to raise the
   endpoint's `max_model_len`, not to elide.

## Consequences

- `deepswe_run_arm.sh` takes `MODE=textbased|native` and the model as
  its third argument; job names carry the model.
- The trajectory now distinguishes "the model looped" (`RepeatedActionError`,
  `repeats_refused`) from "the model ran out of room" — the two were one
  exit status before.
- A repeated action is refused, not a repeated *response*: two responses
  with different prose and the same command are the same action, which is
  the case that matters.
