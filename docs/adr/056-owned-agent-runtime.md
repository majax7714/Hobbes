# ADR-056 — The owned agent runtime, and the small-model ladder on the owner's compute

**Date:** 2026-08-21
**Status:** accepted — step 1 of three; built and tested against stand-ins
**Amends:** `docs/hobbes-architecture.md` (§6.2); `docs/constraints/README.md`
(C-41); `docs/future_additions.md` (the harness remainder)

## Context

ADR-055 left the first live run gated on the session image being able
to run Claude Code, and on every instance spending paid quota on both
arms. The owner's direction (2026-08-21): use **smaller open models**
served from compute he already has (Modal; Daytona sandboxes; Kaggle
as spare), not paid APIs — which is also the cleanest H1 design, since
the ladder is then asked at the sizes where "derived context
substitutes for model size" matters most.

That surfaced a confound worth designing around before any run: both
arms ran through Claude Code, whose system prompt and tool schema are
sized for a frontier model. Pointing it at a 7B model through a gateway
would measure the runtime's fit, not Hobbes. The honest runtime for a
small-model ladder is one we own: minimal, identical on both arms, and
carrying no hidden prompt.

Three steps were agreed: **(1)** the runtime against an OpenAI-compatible
endpoint (this ADR); **(2)** model serving on Modal plus the evaluator's
`--modal` path; **(3)** Daytona as a session backend and the pure arm's
container. Keys for Modal and Daytona were verified usable before step 1
began (Daytona `GET /api/sandbox` → 200; `modal profile current` →
the owner's workspace).

## Decision

### 1. One stdlib-only file is the loop

`pipeline/src/hobbes/agent/loop.py`: send the system prompt, the task
and the tool schemas; execute every tool call; feed results back; stop
on a plain answer or the turn budget. It imports nothing outside the
standard library (a test asserts it), because `hobbes-session` copies
it into the session dir and the Alpine image's `python3` runs it — the
image gains no dependency, and the loop a session runs is the one the
host tested. It prints **Claude Code's result envelope** (`type:
result`, `usage`, `duration_ms`, `num_turns`, `is_error`) so
`bench/accounting.py` meters both runtimes with one reader.

### 2. Tools come from where the arm runs

- **Harness arm** (an MCP config is given): tools are **listed from
  the hobbes-proxy**, never assumed — `exec`, the knowledge tools,
  `reflect` — plus confined native file tools (`read_file`,
  `list_files`, `write_file`, `edit_file`; paths resolved under the
  worktree, an escape refused). **`bash` is not offered at all** when
  an MCP config is present, so the shell is reachable only through the
  policy-checked `exec` — the same boundary Claude Code's
  `--disallowedTools Bash` drew.
- **Pure arm** (no MCP config): `bash` plus the same file tools.
  Nothing of Hobbes.
- A **read-only role** (`reviewer`, `verifier`) gets no write tools,
  matching the ro mount.

### 3. `hobbes-session --runtime FILE --llm-base-url URL --model NAME`

The wrapper copies the loop to `<session>/agent.py` and the brief to
`<session>/brief.md` (a file, not an argv), and the in-container
command becomes `python3 /sessions/<id>/agent.py … --mcp-config … --role
… --workdir /work`. `HOBBES_LLM_API_KEY` on the host, when set, reaches
the session as env — **the one secret a live session carries** (C-41);
the dry run redacts it. A runtime without an endpoint or a model is
refused at plan time.

### 4. `hobbes bench run --runtime openai --llm-base-url URL`

Both arms take a `Runtime`: the pure arm runs the loop on the host with
bash; the harness arm passes `--runtime`/`--llm-base-url` through to
`hobbes-session`. `run.json` records the runtime; every record carries
it. `--runtime claude` stays the default and is unchanged.

## Consequences

- Step 2 is now a pure deployment: a vLLM app on Modal exposing
  `/v1/chat/completions` (first rung Qwen2.5-Coder-7B-Instruct), and
  `swebench`'s native `--modal` evaluation, which removes the local
  podman-socket item from ADR-055's list. Step 3 re-expresses the
  sandbox's guarantees through Daytona's API and registers what differs.
- The ADR-055 "image cannot run Claude Code" blocker dissolves for the
  small-model ladder: no Claude binary in the sandbox, just `python3`
  and the static proxy. What remains of it is the **network**: a
  session must reach the model endpoint, so the first live session will
  not run with `--network none`. That is the architecture-text decision
  the owner now owns, and C-41 records its shape — egress exists;
  narrowing it to the endpoint host is the follow-up.
- The sandbox's enforcement story is unchanged in kind: the shell is
  behind the proxy, mounts are as before, and the only new reachable
  thing is the model endpoint.
- Tests: 9 (`test_agent_loop.py` — a scripted OpenAI-compatible server
  and a stdio fake proxy: routing, confinement, unique edits, read-only
  roles, turn budget and HTTP errors in the envelope, the script
  entrypoint, stdlib-only, the pure arm on the loop); Go +2 (runtime
  command and redaction; the wrapper's copy of loop and brief).
