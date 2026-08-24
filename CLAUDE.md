# CLAUDE.md — working notes for Claude Code sessions

## What this project is

Hobbes: **a multilingual, deterministic code graphing environment.** It
ingests a repo and derives a policy-governed environment where agents do
line-level work and humans review at the concept level.

Three properties, in order of precedence — **accurate** (the job; a wrong
graph is worse than no graph, because it is believed), **deterministic**
(parsers and indexers build the skeleton, never a model; generative work
sits on top and is pinned to it), and **honest** (determinism promises the
same answer twice, not a true one — so every edge carries a tier, every
concession is registered, and a provider's limits are owned as ours).
Abstraction is the product; accuracy is the precondition. The long-run goal
is **single-use agents under derived, systematic context** — the graph makes
that derivation possible, and the sandbox makes a forbidden command *absent*
rather than merely refused. See the architecture's "What Hobbes is".

**Source of truth:** `docs/hobbes-architecture.md` — the **running**
architecture (ADR-033). Read it fully before writing code. It describes
Hobbes as it is now, carries no version number, and is amended **in the same
commit** as any change that moves it; an ADR that amends it names the
section. If you find it describing something the tree does not do, that is a
bug in the file — fix it and note it in the BUILDLOG.
`docs/hobbes-architecture-v1.md` and `docs/hobbes-build-plan.md` are the
frozen v1 record: history, kept for the reasoning behind the carried
subsystems.

Locked decisions (not open for relitigation): **D1** Python + Go + TS split by
focus, **D2** Podman rootless for session isolation, **D3** Cytoscape.js for
the interactive graph.

## Project map

- `go/` — Go module (`github.com/majax7714/Hobbes/go`). `cmd/hobbes-policy/`
  is the policy CLI; `internal/policy/` is the merge engine (box → repo →
  folder, deny overrides allow, allow|deny|escalate).
  `cmd/hobbes-proxy/` is the per-session M4 daemon (`serve` = MCP over
  stdio, ADR-013/014; `escalations` = the approve/deny CLI, ADR-016):
  `internal/proxy/` (policy-checked `exec` + read-only knowledge tools) +
  `internal/recorder/` (append-only JSONL flight log at
  `~/.hobbes/sessions/<session>/flight.jsonl`, ADR-015) +
  `internal/escalation/` (park/approve/expire queue, ADR-016) +
  `internal/knowledge/` (graph_neighborhood/who_calls/tests_guarding/
  get_module_doc/list_invariants over `.hobbes/derived/`, ADR-017/019/024,
  plus list_blind_spots — the boundary's tool, ADR-047).
  `cmd/hobbes-session/` + `internal/sandbox/` launch a session in rootless
  Podman (ADR-018); the **reviewer** role mounts the worktree ro and drops
  Edit/Write/exec, and every role gets `.hobbes/derived/` mounted ro so the
  knowledge tools have something to read (M8).
  `cmd/hobbes-web/` + `internal/web/` are the M7 surface server
  (ADR-022): a loopback-only JSON API over the derived artifacts, the
  repo reads a browser cannot do (source, `git diff`), the flight-log
  tail, and the surface's only mutation — escalation approve/deny,
  delegated to `internal/escalation`. The built SPA is embedded from
  `internal/web/dist/` (gitignored but for its `.gitkeep`).
  Only external Go deps: `yaml.v3`, `modelcontextprotocol/go-sdk`.
- `sandbox/` — the M4 session image (`Containerfile`), the static proxy it
  copies (gitignored build artifact), and the exit-check harness
  (`driver.py` scripted implementer, `exitcheck.py` orchestrator).
- `pipeline/` — Python package `hobbes` (uv-managed, src layout). The `hobbes`
  CLI (`src/hobbes/cli.py`), the shell-out wrapper for the Go policy binary
  (`src/hobbes/policy.py`), the deterministic extractors
  (`src/hobbes/extract/`: discover → pysource (tree-sitter walk) → graph /
  testmap → **packs** → emit; `extract/packs/` is the V2.M4 enrichment
  layer, ADR-035 — four packs in a code tuple, activated by detection, and
  the only path by which route/CLI/Terraform knowledge reaches the
  artifacts), the Mermaid export (`src/hobbes/render.py`),
  the graph-diff engine (`src/hobbes/graphdiff.py`), the D1 plan
  derivation (`src/hobbes/derive/`: impact → cochange → partition →
  contracts → manifests → changespec, behind `hobbes plan`, ADR-051),
  the D2 execution base (`src/hobbes/run/`: spec → agents (layered
  policy, standing context, inbox) → orchestrate (spawn per unit in
  contract order, harvest, integrate, review, partition record) +
  roles + mail, behind `hobbes run` / `hobbes mail`, ADR-054),
  the owned agent runtime (`src/hobbes/agent/loop.py`: a stdlib-only
  tool loop over an OpenAI-compatible endpoint, run inside the sandbox
  via `hobbes-session --runtime`, ADR-056),
  the requirement coverage check (`src/hobbes/run/coverage.py`: the
  planner's `requirements:` → owning units → plan error or assignment,
  ADR-085),
  the benchmark harness (`src/hobbes/bench/`: instances + protocol →
  workspace → two arms → one meter → the benchmark's verdict →
  report, behind `hobbes bench`, ADR-055; `scripts/bench_fetch.py`
  exports a HF split to the JSONL it reads),
  and the M5 narrative
  pass (`src/hobbes/narrate/`: ADR-019 artifact schema + blob-level
  staleness, ADR-020 headless tool-less `claude -p` runner, orchestrator
  behind `hobbes narrate` / `hobbes docs status`). `extract/tssource.py`
  joins the tsextract helper's facts (M6, ADR-021);
  `extract/gosource.py` is Go's lane A (V2.M5, ADR-037), and
  `extract/rustsource.py` is Rust's (V2.M7, ADR-040). M8 adds
  `src/hobbes/invariants/` (ADR-024: record loading/validation,
  graph-computed verdicts, and the four CI-config emitters) and
  `src/hobbes/review.py` (ADR-025: `hobbes review`).
  Test fixture repos: `tests/fixtures/miniapp/`
  (Python), `tests/fixtures/minits/` (TS/JS), `tests/fixtures/minigo/`
  (Go), and `tests/fixtures/minirust/` (Rust), all excluded from
  pytest collection via `norecursedirs`.
- `tsextract/` — Node helper (ADR-021): ts-morph walk emitting facts
  JSON for the Python join; own `node --test` suite (`npm test`);
  `node_modules/` gitignored, lockfile committed. Only external dep:
  ts-morph.
- `scip/` — **v2 lane B** (ADR-027): the SCIP indexers, pinned
  (`scip-python`, `scip-typescript` from npm; **`scip-go` 0.2.7 is a Go
  binary — `go install github.com/scip-code/scip-go/cmd/scip-go@v0.2.7`**,
  note the module moved from `sourcegraph/`; **rust-analyzer is a rustup
  component** — `rustup component add rust-analyzer`, pinned by the
  toolchain, and `~/.cargo/bin` is on PATH via the shell profiles),
  `index.mjs` (the real helper:
  runs an indexer, decodes, filters, reports `dependency_coverage`), and
  the spike tooling kept as reproducible evidence — `analyze.mjs` /
  `compare.mjs` for ADR-027's numbers, `spike-ts.mjs` for ADR-032's
  staging table. Own `node --test` suite (`npm test`).
  One-time: `cd scip && npm install`.
- `web/` — the M7 surface (Vite + React + TS, Cytoscape.js per D3).
  `src/lib/` holds the pure layer and all the vitest cases (graph model
  and focus neighborhood, §4.2 index joins, patch parsing); `src/tabs/`
  is one component per tab. `npm run build` typechecks, then bundles
  into the Go embed dir — **rebuild `hobbes-web` after**, or it serves
  the previous bundle. `npm run dev` proxies `/api` to a running server.
- `docs/` — `hobbes-architecture.md` (the running architecture — the one to
  read), `hobbes-build-plan-v2.md` (the active programme), the two frozen v1
  docs, `docs/adr/` (numbered ADRs), `docs/constraints.md` (the P8/P9
  register of what Hobbes cannot tell you, ADR-030/034), `docs/BUILDLOG.md`
  (append-only session log), `docs/first-run.md` (bringing Hobbes up on a
  new app, in the order the system is meant to be used), and
  `docs/m9-application-mode.md` (**parked** — see Current status).
- `.hobbes/` — dogfooding: `policies/` + `invariants/` versioned, `derived/`
  gitignored. `invariants/` holds eleven confirmed records (ADR-024) —
  I-1..I-6 promoted at M8, I-7..I-11 approved through the surface on
  2026-08-15 and each a **reworded restatement** of one of the first six
  (C-21); the duplication is noted in a comment at the top of each file,
  and the I-1..I-6 record is the one of reference where they overlap;
  `derived/compiled/` is where `hobbes invariants compile` writes CI
  configs.

## Build & test

Go, uv, and Node are user-local installs: `~/.local/go/bin` and
`~/.local/bin` (ensure both are on `PATH`). `go.mod` requires **Go
≥ 1.26**, and a distro Go in `/usr/bin` is older — `~/.local/go/bin`
must come *first*, or `go build` fails on the toolchain line rather
than on anything real. One-time: `cd tsextract && npm install` (TS
extraction) and `cd web && npm install` (the surface).

```sh
# Go
cd go
go test ./...
go build -o bin/hobbes-policy ./cmd/hobbes-policy
go build -o bin/hobbes-web    ./cmd/hobbes-web   # after `cd web && npm run build`
go build -o bin/hobbes-session ./cmd/hobbes-session
# The proxy must be STATIC: hobbes-session mounts the binary sitting next
# to it into the sandbox, and a dynamically-linked one fails there as a
# confusing "No such file or directory" (the loader is missing, not the
# binary). Static works host-side too.
CGO_ENABLED=0 go build -o bin/hobbes-proxy ./cmd/hobbes-proxy
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy  # image build

# Web surface (M7)
cd web
npm test                                          # vitest, the pure layer
npm run build                                     # bundles into go/internal/web/dist/
../go/bin/hobbes-web serve --repo /path/to/repo   # http://127.0.0.1:7777

# Python
cd pipeline
uv sync
uv run pytest
uv run hobbes policy resolve "some command"   # needs hobbes-policy built;
                                              # set HOBBES_POLICY_BIN or PATH

# Bring-up (ADR-026) — one command, blocks until decisions are made
uv run hobbes up                              # or --no-serve to just report

# Invariants and review (M8)
uv run hobbes invariants check                # validate .hobbes/invariants/
uv run hobbes invariants compile              # → .hobbes/derived/compiled/
uv run hobbes review main..my-branch          # exits 1 if it needs attention
uv run hobbes review main..my-branch --soft   # + reviewer sessions (quota)

# Lane agreement (V2.M3, §3.4) — a command and a CI check
uv run hobbes lanes                           # exits 1 if the lanes disagree
uv run hobbes lanes --json

# Plan derivation (D1, ADR-051) — deterministic, quota-free
uv run hobbes plan "proposal text" --seed some.module   # → .hobbes/plans/
uv run hobbes plan "..." --adds "a -> b"      # gate-checks the declared edge;
                                              # exits 1 on an invariant hit

# Execution (D2 base, ADR-054) — one sandboxed session per unit
uv run hobbes run <task> --dry-run            # agents, briefs, record; spawns nothing
uv run hobbes run <task>                      # needs go/bin/hobbes-session + the image
uv run hobbes mail post <task> U1 "text"      # short-term context for a unit
uv run hobbes mail read <task> orchestrator   # reflections land here

# Benchmark harness (ADR-055) — built, no live run yet
uv run scripts/bench_fetch.py princeton-nlp/SWE-bench_Verified test v.jsonl
uv run hobbes bench select v.jsonl --cutoff 2025-01-01   # protocol; drops counted
uv run hobbes bench run v.jsonl --model claude-sonnet-5 --limit 5 --evaluate
                                              # spends quota on BOTH arms —
                                              # Max names the first set
uv run hobbes bench report ~/.hobbes/bench/run
# small-model ladder on an OpenAI-compatible endpoint (ADR-056):
HOBBES_LLM_API_KEY=… uv run hobbes bench run v.jsonl --runtime openai \
    --llm-base-url https://…/v1 --model Qwen/Qwen2.5-Coder-7B-Instruct
    # both arms run in the instance's swebench image (ADR-058, C-43),
    # --network pasta by default (egress, C-41), --max-units 20 (C-44)
```

## Conventions

- **Milestone order is strict.** Never start milestone N+1 in a session where
  milestone N's exit criteria haven't been met *and reviewed by Max*.
- Tests accompany the code they test **in the same commit**.
- Conventional commits, scoped: `feat(policy): ...`, `fix(cli): ...`,
  `test/docs/chore`.
- One short ADR (`docs/adr/NNN-title.md`) for every design decision the two
  source docs don't already make. Number sequentially.
- **Every decision that concedes information gets a `C-n` entry in
  `docs/constraints.md`, in the same commit** (P8, ADR-030). An entry is
  not done when written — it carries a *surfacing status* naming where a
  user meets the limit; `unsurfaced` means documented only, and is debt.
  Hobbes is unusable as a known liar and worse as a fake-honest one.
- `docs/BUILDLOG.md` is append-only; one dated entry per session. Never edit
  old entries.
- Every package/module gets doc comments explaining purpose and contract;
  public functions documented. No orphan code.
- No speculative abstraction — build what the current milestone needs.
- **Never read or write `.tfstate` files. Never commit anything under
  `.hobbes/derived/`.**
- **Hobbes files are personal (ADR-012):** in Max's repos, the entire
  `.hobbes/` directory is gitignored — `ingest`/`init` enforce it
  automatically. Only this repo (dogfooding §10) versions its `.hobbes/`.
- **Commit to `main` unless Max directs otherwise** (2026-08-21). If a
  session works on another branch for any reason, say so plainly in
  the report — the 2026-08-21 session branched off `main` for ADR-053
  and stacked ADR-054 on it without flagging it, and the branch picture
  cost Max a review detour. He fast-forwarded `main` and deleted the
  branch; `m8-exit-check` (fully merged since M8) is gone too.
- **Never `git push`.** Sessions commit; Max publishes after review. The repo policy denies `git push*` outright rather than
  escalating it — an escalation is for commands a human might reasonably
  approve. This also applies when testing the escalation queue: pick
  read-only commands, because an *approved* escalation really runs.

## Current status

**2026-08-24, later (the ADR-085 validation pair RAN — then PAUSED for
restructure):** Max cleared the one run: two passes (A strict, B
`--proposal-in-brief`) over the same five Verified instances, 7B
harness arm only, local eval. **The record and the eight-defect
register are `docs/adr085-validation-run.md` — stubbed NEEDS
INSPECTION AND REVISION; that file is the restructure's worklist.**
E-numbers: planner `requirements:` 0/5 first-attempt, 3/5 after the
one strict re-plan; sphinx = first end-to-end ADR-085 success; the
lexical fallback bypasses coverage (D5); removal A/B: no usable signal
(D5 + O4 planner variance at temp 0). 0/5 solved, both passes — not
the measure. Richest findings came from Max's Modal 400 alarm: D1
window-fit 400 storm (vLLM's "at least" lower bound → 450 retries on
one call), D2 elision deletes action memory, D3 read ticket survives
elision (28-byte blind overwrite — P10 shape), D4 same-turn read+edit
defeats ADR-067's spirit (hallucinated anchor). D7: foreign env
residue in extraction_errors rides briefs. 7B never called a knowledge
tool (push-only at this rung). **Nothing is fixed yet — experiments
parked again; Max returns to restructure from the register.**
Handoff rewritten; hypotheses Results stubbed; BUILDLOG eightieth
(two addenda).

**2026-08-24 (presentability pass — docs current, dead code out, the
backlog grouped; no runs):** the running architecture was audited
against the tree and 19 stale claims fixed in place (the §6.2/"Where
this is going" "no live run has happened" text now records the live
runs, the parked status, C-39 → DeepSWE, and P12; §7's v1 fictions —
three-level merge, image-per-role, secret brokering, quota — corrected
to what exists; packs 4 → 8; edge/tail vocabularies trued; dead
`bench-run-handoff.md` pointer replaced). Dead code removed:
`scip/dump.mjs`, `extract/docstrings.py` + test (never wired),
the committed `hobbesmini/build/` artifact (`build/` gitignored) —
**pytest is now 895**. P12 banners added to
`harness-restructure-plan.md` / `harness-mini-swe-integration.md` /
`benchmark-deepswe.md`; `--implement-mode aided` help states P12.
README: *Calvin and Hobbes* properly credited, counts trued (85 ADRs,
57 constraints, suite numbers verified live). **`docs/workstreams.md`
(new, README-linked): the backlog grouped into six assignable
workstreams (W0 presentation/CI … W5 safety/policy) — names no new
work, un-parks nothing.** **Same day, the two non-run decisions
resolved (ADR-086):** lever 2 (ADR-083) deferred to the 7B run's
strict-coverage records; aided mode now **mechanically** labelled — an
aided run is recorded `arm=model+prompt` on every path, resumes and
names patches under that arm, enters no H1 harness slot (P12's "the
method refuses the label" made code). **Next: ONE 7B validation run of
ADR-085 on Max's go — a single run, then project setup.** 896 pytest /
291 Go / 52 vitest / 29+25 node green.

**2026-08-23 (ADR-085 built — the planner/mapping fix; no runs):** the
planner is now the requirement-decomposer in code: its handoff carries
`requirements:` (`R1: <what must become true> -> <owning file>`),
`run/coverage.py` assigns each to the unit whose interior holds its
file, an uncovered requirement re-plans once then is a **plan error at
plan cost** (`--coverage strict`, default; `assign` hands it to the seed
unit and says so, C-57). On a covered plan the implementer brief carries
`## Your task` (owned requirements) and **no proposal**
(`--proposal-in-brief` = the removal test's control); `--planner-arg`
weights the planner alone. Precursor `imperatives_unmentioned` recorded
per plan (lexical, gates nothing) — replayed with no model it flags the
sympy value-eval in every 7B handoff, keeps it for the 27B. Architecture
§6.1 is the current agent architecture; README has an Acknowledgements
section (tree-sitter, SCIP, mini-swe-agent/Pier, …). **Next when a run
is cleared: does the 7B planner write `requirements:`, how often does
strict stop — then the removal A/B.** 906 pytest / Go green.

**2026-08-22 (DeepSWE on Pier, ADR-078 — first run done, one task per
arm):** the referenced-harness pivot is real: `datacurve-pier` +
mini-swe-agent run both arms, Hobbes injects the ADR-077 aid through
Pier's `prompt_template_path` seam (`pipeline/scripts/deepswe_aid.py`,
`deepswe_run_arm.sh`; working tree `~/.hobbes/deepswe/`). 7B needs
text-based actions; pre-pull the task image. httpx task: 0/0, baseline
never opened a file, Hobbes arm localised on turn 2 then looped. C-55
(aid has no planner stage). **Same day, 27B (ADR-079/080):** `hobbesmini`
(repeat guard + commit-on-exit, both arms, delivered as a wheel into
Pier's image build) — baseline 115/122 F2P, Hobbes 107/122, both
context-bound at 131k; n=1, no H1 reading. **2026-08-23 (ADR-081, C-56 instruments):** obs pair — baseline
122/122 (reward 1), Hobbes 120/122; spans followed at class grain;
familiarity 0.21 = stdlib. **P12 (ADR-082, 2026-08-23): a Hobbes test decomposes, or it is not a
Hobbes test.** All Pier pairs + the 7B aided run are retracted as Hobbes
evidence (one agent, whole task, added prompt = *model + prompt*).
**PAUSED — experiments parked now and near-future (Max, 2026-08-23).**
Architecture change + a 7B Hobbes review precede any 27B run, ever again;
the 7B is the instrument by speed, not capability. **The frame (ADR-084):**
the planner is the requirement-decomposer — it does localization but not
requirement decomposition, so a requirement can have no owning unit
(sympy's value-eval, stated in the issue, had none); coverage (⋃ handoffs
⊇ requirements) is its guarantee, each handoff complete for its
implementer; the weight is inverted (planner 4-12%, implementers 88-96%)
and belongs to the single planner. Fixes due + build order in the handoff.

**v1 is complete (M0–M8) and v2 is complete (V2.M0–M7) — every
milestone built, reviewed, and passed by Max. The Rust proof (V2.M7,
ADR-040) passed 2026-08-16, closing the v2 extraction programme.**

**The named current work is deep extraction testing** (Max,
2026-08-18): "theres not been enough extraction testing to clear and
thats actually what were handling now." **The derivation programme
opened on 2026-08-19 at Max's direction** — he added
`docs/agent-mapping.md` and named the build; D1 (the plan derivation)
passed his review on 2026-08-21, the D2 **base** (execution, ADR-054)
passed the same day, and the benchmark harness (`hobbes bench`,
ADR-055) is built and unrun — its first live run waits on Max's
session-image/network decision. **The named verification method
is the benchmark harness** (Max, 2026-08-19, ADR-052): Hobbes run as a
harness over known benchmarks vs pure-model baselines, hypotheses
H1–H3 preregistered in `docs/benchmark-hypotheses.md` — testing itself
deliberately not started. The build plan
(`docs/hobbes-build-plan-v2.md`) is record, not plan; the backlog in
`docs/future_additions.md` stays parked unless Max names an item.

**2026-08-22 (the thinking rung, ADR-074 — built and deployed; the
first 27B run launched):** Max's go after the 7B read clean. The Modal
image is vLLM 0.27.1 / transformers ≥ 5.8 for every rung;
`Qwen/Qwen3.8-27B` (a thinking hybrid, text-only serving, window
131,072, `qwen3` reasoning + `qwen3_coder` tool parsers) is deployed
and smoke-verified, the 7B re-verified on the same image. The owned
loop takes `--temperature/--top-p/--reasoning-effort/--thinking`,
keeps `reasoning_content` on the transcript, counts
`usage.reasoning_tokens` when reported (vLLM 0.27 does not);
`bench.Runtime` carries the sampling once for both arms via
`hobbes-session --loop-arg`. Two cold-start lessons in `modal_vllm.py`:
`MODEL` must be baked into the image env (the container re-imports the
script without the host's env — the 27B app came up serving the 7B),
and `VLLM_USE_FLASHINFER_SAMPLER=0` (the JIT needs nvcc). Modal answers
a request that outlives its cold start with a `303` poll redirect —
warm an endpoint with a short-timeout `/models` loop before a run.
The run's settings are pre-registered in the hypotheses doc. 866
pytest / Go green.

**2026-08-22 (harness restructure, phases 0–3 built — read
`docs/harness-restructure-plan.md`):** Max restated the execution
shape (single-use *derived-context* agents, one alive at a time, job =
short memory) and accepted the five-phase plan. Phase 0 fixed seeding
(seed hygiene, select-then-cap, path-first briefs, handoff
reflections); phase 1 made `planner`/`reviewer`/`verifier` read-only
roles with role-aware loop discipline; phase 2 built the **staged run**
(ADR-059: `hobbes run --from-proposal`, `hobbes bench run --stages`;
planner → `hobbes plan` on its seeds → chained implementers → verifier
→ opt-in review/rework; C-47, C-48); phase 3 built the **harness
adapter** — every stage metered (wall time from outside, own session
log), `seed_source` on the record, the planner scored **post hoc
against the gold patch** (`planner ∩ gold`, C-49 — a one-solution
proxy), `hobbes bench report` split by `seed_source` with the planner
hit-rate. Phase 3 also found and fixed phase 2's integration branch
never advancing (`branch -f` in the repo, not the worktree). Phase 4's
**planner probe hit on both astropy instances** (13398 1/4, 13579
1/1; ~10 s, one tool call each — see the hypotheses doc's Results)
after three harness fixes it surfaced: **ADR-060** (read-only roles
mount an overlay, the `ro` mount killed the C-43 binding), the
handoff parser reading prose headings + dotted symbol names, and
planner seeds *replacing* the lexical layer. Phase 4
**full-stage run done on both astropy instances**: 0/2 both arms,
**planner hit 100% (2/2)** — the planner finds the place, the 7B
implementer is the wall (13579 harness applied cleanly, 41/41 P2P
green, one F2P still failing). Getting there took correctness fixes
(`40bc4b1`), speed fixes (`a646760`: max_tokens cap, exec-repeat
refusal, read-only pip) after the implement stage ran 21–36 min, and
**unblocking the evaluator**: swebench 5.0.2's `--modal` is broken
upstream (C-50), so eval runs **locally over the rootless-podman Docker
socket** (`docker_host_env`), closing ADR-055's evaluator-socket item.
**2026-08-22, later: ADR-065 — `hobbes bench run --instance-workers N` runs instances concurrently on the shared Modal endpoint (throughput-bound ~2–3×, not N×). ADR-064 — transcript persisted (`<session>/transcript.jsonl`), planner-nameless units not spawned (C-52), `write_file` refuses to overwrite an unread file (both arms). ADR-063 — parallel implementers in waves over the contract DAG, vLLM-gated (`--parallel auto`, C-51); measured: per-unit harness overhead ~1 s, decode at 28 tok/s is 85–90 % of a unit's wall. The role-context fix is built (ADR-062** — the planner handoff is projected per unit via `planner_slice`, the Interior section is never cut; 830 pytest). **2026-08-22, later still: ADR-066 — the two harness fixes the 5-fresh benchmark read surfaced: the handoff parser splits inline `field:` (xarray's one-line handoff now resolves both gold files) and a repeated identical edit is refused (django's stack). 843 pytest / Go green. THE SINGLE RESUME POINT IS NOW `docs/session-handoff.md` (the old per-phase handoffs are deleted; their history is in `docs/BUILDLOG.md`).**

(Historical, from the phase-4 handoff, now in BUILDLOG:)
it holds this session's build, the corrected 45-set command (local
podman-socket eval, not `--eval-modal`), and the one decided-but-unbuilt
fix: **role-specific implementer context** (the planner handoff is
posted globally to every unit and the per-unit interior is truncated —
implementers are led astray, not wrong; ADR-061 enforces write scope at
the cut but the role-context derivation is the recommended next step
before spending 45-set compute). 827 pytest / Go green.

**2026-08-21 (run stopped for restructure — read
`docs/BUILDLOG.md`):** The first live 7B benchmark
pass was shaken out over this session — **six** harness fixes (ADR-058:
env binding C-43, unit cap C-44, brief-as-file+limit C-45, window-fit
C-46, commit-on-exit, and the strict pipeline discipline) got it
producing candidate patches. Running it then showed the **structural**
problem: the harness spawns a session per partition unit and **~half
are spurious** (8/17 units ever edited; astropy-13579 was 2/9). Owner
stopped the run — **enough to restructure, not to keep paying for the
current shape.** Fresh session's job: **task-tailored unit selection**
(spawn only units the change reaches; first cut = skip a unit with no
seed-reachable interior), then re-ask whether per-unit-session fan-out
is the right shape. **No solve verdicts gathered** — the first-10-20
decision point was never reached. 797 pytest / Go green.

**2026-08-21 (the first full run: stopped, fixed, relaunched —
ADR-058):** The handoff's run started and was polled at 20 min;
instance 1 showed a **210-unit plan** (~7.5 min/session) and sessions
in which **no test could run** (`pytest` 127 in the bare Alpine image,
`git commit` 128 with no identity), so the run was stopped. Max's
calls: **cap benchmark plans at 20 units** and **install the
environment as a benchmark practice**. Built: `bench/environment.py`
— both arms run in the instance's own **swebench image**, workspace
bound by `PYTHONPATH=/work` + copied build artifacts (C-43);
`hobbes-session --path/--env/--pre/--runtime-python` and a seeded
commit identity in every clone; `build_units(max_units=)` with
`capped` flags (C-44); `hobbes bench run --environment swebench`
(default) `--max-units 20` (default) `--network pasta` (default).
Second stop the same day: a capped unit's 488 KB brief as `--task`
→ `Argument list too long` on every harness arm; fixed with
`hobbes-session --task-file` and a **brief limit** (`--brief-limit
60000` default; protected sections never cut; C-45). 786 pytest / Go
green. Third stop: instance 1 empty-patch because a large read made
the next completion a context-length 400 (loop treated it as fatal)
and the 7B edited but never committed (commit-only harvest saw
nothing). Fixed: the loop **fits the window** (shrink max_tokens,
elide oldest tool results, clip results — C-46) and `hobbes-session
--commit-on-exit` commits leftover edits (`.hobbes/` excluded). A
debug loop on one light instance (Max's call — confirm the harness
before another full pass) then found the 7B writes a prose plan and
never edits; fifth fix is a **bounded prose-plan nudge**
(`--max-nudges 2`; makes the model act, never says what to write —
H1 stays the model's). With it, `pytest-5787` produced a real
**patch** end to end — harness confirmed. 794 pytest / Go green.
(that session's checklist is in `docs/BUILDLOG.md`).

**2026-08-21 (small-model ladder live + the solo policy, ADR-057):**
Focus benchmark set: **SWE-bench Verified, complex multi-step set** (45
instances rated 1-4h/>4h via Verified's own `difficulty`), on the
**Qwen2.5-Coder 7B→32B** ladder served from Max's Modal (no paid APIs).
Bar: harnessed rung N ≈ pure rung N+1 (7B-harness vs 32B-pure). Built:
`scripts/modal_vllm.py` (vLLM per rung; **7B live**, vLLM 0.10.1.1 +
transformers<5), `hobbes bench --difficulty complex --eval-modal
--secrets`. **First live instance surfaced the blocker Max predicted:**
a benchmark checkout is a committed-only clone, so repo/role policies
never reach the session — `pytest`/`git commit` escalated and
expire-denied at 30 min with no approver. **Fixed** with the **solo box
policy** (`bench/bench.box.policy`, auto-passed via `--box` +
`--escalation-timeout 5s`): allows a lone implementer tests+commit,
guarantees stay denied by deny-overrides, sandbox unchanged. C-42
registered. **The first full complex-set run is handed off to a fresh
session — its details are in `docs/BUILDLOG.md`.** 769 pytest / Go green.

**2026-08-21 (the owned agent runtime, ADR-056 — step 1 of 3):** Max
redirected the ladder to small open models on his own compute (Modal
serving + evaluator, Daytona sandboxes, Kaggle spare; no paid APIs).
Built `src/hobbes/agent/loop.py` — stdlib-only tool loop over any
OpenAI-compatible endpoint, identical on both arms (harness: tools
listed from the proxy + confined file tools, **no bash**; pure: bash +
file tools), printing Claude Code's envelope so one meter reads both.
`hobbes-session --runtime FILE --llm-base-url URL --model NAME` copies
the loop + brief into the session dir and runs it with the image's
python3; `hobbes bench run --runtime openai --llm-base-url URL`. C-41:
a live session has egress + the endpoint token (`HOBBES_LLM_API_KEY`
from the host env; redacted in dry runs). Keys live in `secrets.txt`
(gitignored; format `daytona_key=…`, `modal_key_id=…`,
`modal_key_secret=…`); both verified usable. **Next: step 2** — vLLM
on Modal (Qwen2.5-Coder-7B first) + `swebench --modal`; then step 3,
Daytona as a session backend. 762 pytest / Go green.

**2026-08-21 (D2 passed; the benchmark harness built, ADR-055 — no
live run):** Max passed D2 and directed the harness. Built quota-free
like D2: `hobbes bench select|run|report` — instance protocol (C-39:
contamination bounded, never proven; a 2025 cutoff selects 0 of
Verified's 500), two arms from one checkout (harness = ingest → plan
with the issue as proposal → run → branch diff, `no-seed` counted
against it; pure = Claude Code raw on the host), one meter (Claude
Code's JSON envelope; `hobbes-session` gained `--model` and now
requests the envelope), the pinned `swebench 5.0.2` evaluator as the
verdict (C-40, P9), and a report that computes H1/H2/H3 and interprets
nothing. **The first live run is blocked on Max:** the sandbox cannot
run Claude Code (Alpine/musl image, glibc `claude` not mounted,
network `none` — the network is an architecture-text decision), plus
pure-arm containment, the podman socket for the evaluator, a
post-cutoff set (SWE-rebench / SWE-bench-Live), and quota — ADR-055's
consequences list them in order. First real-instance C-36 measurement:
`psf/requests` ×8, 8/8 seed, 4/8 touch a gold file; candidate
adjustments parked, not applied. 753 pytest (+30) / Go +2.

**2026-08-21 (D1 reviewed and passed; D2 base built, ADR-054 —
reviewed and passed the same day):** Max passed D1 and set the agent structure: per-agent
policy = repo + role + derived agent layer; standing derived context +
short-term context as role-pushed mail (orchestrator posts a specific,
the agent reflects it back); commits alter standing context and
policies; the rest of the mapping stays; the formula learns from
benchmark errors — **for benchmarks Hobbes runs alone, the manual
plan-review gate is off, proposals are what gets set.** Built as a
rough base to find the first errors under testing: Go policy chain
gains `role` and `agent` levels (narrow-only by deny-overrides);
proxy tags **context faults** from `<agent-dir>/context.json` (served,
never refused) and gains `reflect` → `<session>/mail.jsonl`;
`hobbes-session --agent-dir` mounts the agent dir ro at `/agent` and
**harvests** the session branch (commits used to die with the clone);
`verifier` is a read-only role. Python `hobbes/run/`: `hobbes run
<task>` materializes agents (policy.yaml / context.json / context.md /
inbox / brief), spawns per unit in contract order, skips human-first
units, folds reflections into the orchestrator inbox, integrates onto
`hobbes/<task>` in a detached worktree, runs the review, writes
`partition-record.json` with rework, faults, exec counts, and the
declared-weight loss (tokens/wall time listed unobserved). **C-38**
registered surfaced (write scope advisory at path grain — measured as
rework). `.hobbes/policies/roles/` scaffolded in the dogfood repo.
Not built (future_additions): path-grain write enforcement, verifier
session, renegotiation re-pin, metering, loss fitting, generative
seeds. 723 pytest (+20) / 212 Go (+15). No sandbox session spawned —
the dogfood exit check is `hobbes run 2a56 --dry-run` with the real
binary. **Next is Max's review, then the benchmark harness.**

**2026-08-21 (C-31 and C-32 surfaced, ADR-053 — built, awaiting Max's
review):** Max's standing instruction (away for the day): apply the
register's easiest candidate fixes. Two of three applied; C-25's
per-repo pack disable list is the ADR-012 question and stays. Two
additive `graph.json` fields, no schema bump: **`verification_base`**
(§3.8 pinned in `extract/verification.py`, stamped per artifact
language — the ingest summary prints `verification base: go 1 repo, …
— a sample, not the language` under the language list, the surface
badges read `go · 1 repo` with single-repo rows in the stale colour,
`list_blind_spots` prints the rows scoped; `test_verification.py`
parses §3.8 and fails on drift, so **§3.7 step 4 now also means
extending `VERIFICATION_BASE`**) and **`tail_classes_available`**
(`CLASSES_AVAILABLE` in `tail.py`; capture line and blind spots print
`classes this lane cannot report: …`). Unsurfaced entries now
three (C-4, C-19, C-20). 703 pytest / Go green / 52 vitest; SPA and
binaries rebuilt.

**2026-08-19 (benchmark hypotheses preregistered, ADR-052 — docs
only):** Max named the verification course for the derivation
programme: use Hobbes as a harness under known benchmarks — the error
stream drives adjustment (C-35's loss loop gets its data), and known
benchmarks supply the pure-model baseline pool. Three hypotheses
preregistered in `docs/benchmark-hypotheses.md` with metrics and
falsifiers stated before any run (P11 applied forward): **H1** derived
context substitutes for model size (harnessed small ≥ pure large);
**H2** regenerated per-unit context flattens accuracy-vs-depth;
**H3** cheaper and quicker per *solved* task as a byproduct — the
multi-unit coordination counter-pressure stated up front. Doc records
the current gaps honestly: end-to-end runs need D2, C-36 (prose
issues, lexical seeds) is the predicted first friction, instance
selection must respect training-set contamination. **Testing
deliberately not introduced** — the harness scope (benchmark adapter,
prose seed extraction, dual-arm cost accounting, instance protocol)
is parked in future_additions; opens when Max names it. Architecture:
"Where this is going" names the verification path; §8's D-table gains
the preregistered row. README links the doc as extraction-evidence's
forward-looking counterpart.

**2026-08-19 (D1 — the plan derivation, ADR-051 — built, awaiting
Max's review):** Max added `docs/agent-mapping.md` (phases not
personas; agent = (context slice, policy profile, verification
obligations); the mapping as an algorithm, the org chart as output)
and directed the build. `hobbes plan "<proposal>"` now derives a
change-spec deterministically and quota-free:
`pipeline/src/hobbes/derive/` (impact with lexical seeds + per-hop
decay, git co-change coupling, budgeted agglomerative partition,
cut-edge contracts pinned to declaration sites, per-unit context
manifests that **refuse to serialize without their ADR-047
complement**, derived policy manifests whose P10 guarantees raise
rather than absorb, and a plan-review gate that judges `--adds`
edges against confirmed forbidden-import invariants — exit 1 at
planning cost, not PR cost). Specs land in `.hobbes/plans/<hash>/`
(not derived/ — approved, not regenerable; gitignored here).
ADR-051 answers agent-mapping §9's open questions and pins every
parameter as a declared guess. Register: **C-35** (partition quality
unvalidated — printed on every run), **C-36** (lexical seeds),
**C-37** (a pin is a declaration site), all surfaced on day one;
architecture gains §6 (Derivation) with §§6–9 renumbered §§7–10.
Exit-checked on the dogfood repo: seed `hobbes.review` → 3 units /
12 contracts with real declaration sites; the gate fails
`hobbes.derive.impact -> ext:tree_sitter` citing I-4 and passes the
pysource exception; two runs byte-identical. The first run also
found and fixed a real flaw: without per-hop decay, one seed pulled
the whole connected component (33 units). **D2 (execution: spawning
from manifests, context faults, the recorder's partition record) is
deliberately not built** — parked in future_additions with scope.
688 pytest green (48 new).

**2026-08-19 (the company-shaped derivation workflow — written down,
docs-only):** Max brought a direction for the unbuilt derivation
milestone: structure the context-derived coding flow like a software
company — user proposes → orchestrator scopes the proposal under base
context → engineers plan → plan reviewer (dev-ops analog) validates →
adjust/finalize → fan-out to per-feature/specialized single-use agents
(width by codebase size) → verifier before commit. Recorded as the
final entry in `docs/future_additions.md`, cross-referencing the
ADR-047 derivation-contract entry so the milestone inherits both. Open
hard part named there: the role taxonomy (how many/which/what type),
Max's method being a relational mapping from real software-company
role structures; the entry adds the filter (only roles encoding a
verification/context boundary map onto agents) and the derived-org
requirement (fan-out computed from the graph, never authored — the
§3.7 no-`hobbes.yaml` instinct). Nothing built; derivation stays
deferred; extraction testing remains the current work.

**2026-08-18 (node dependencies non-invasively, ADR-050 — built,
awaiting Max's review):** TS/JS was the weakest lane; Max asked for a
node workaround "not invasive to the repos". Built two: **per-file
dependency links** (every node_modules on a zone file's walk-up path is
linked into the stage — hobbes' tsconfig-less tsextract/scip zones were
indexing without the trees beside their own files) and
**lockfile-pinned provisioning** into `~/.hobbes/cache/npm/<hash>`
(`npm ci` / corepack-pinned classic yarn for v1 locks,
`--ignore-scripts` always; no-lockfile/pnpm/Berry **declined by name**
per zone — an unpinned install breaks P1). C-23 narrowed, **C-34**
added (registry + lockfile boundary, surfaced per zone). Measured:
hobbes ts/js **61.6→67.0%**, kbet holds **72.1%**, dagger ts/js
**18.8→27.9%** (`sdk/typescript` **70.3%**; docs zone indexes instead
of failing; the dark remainder is example snippets whose deps *no*
package.json declares — undeclarable). Lanes watchdog: +120
disagreements are all the TS decorator line-convention off-by-one
(now 131 — tssource emitting the name line is the future_additions
fix); 1 genuinely new. 640 pytest / 29 tsextract / 25 scip.

**2026-08-18 (the cross-unit join + the evidence log, ADR-049 — built,
awaiting Max's review):** Max directed the C-33 candidate fix and a
standing test-evidence doc. `docs/extraction-evidence.md` is the
per-repo evidence log (dated stats + a mandatory *Verified* line, "none"
allowed but stated — dagger's says so); README links it; update it in
the same commit as any test session. The fix: helper facts **v3**
(external rows keep monikers), `join_cross_unit` per language on
**exact moniker equality** (ambiguity abstains + reports — C-28 across
units; not C-12's rejected reconciliation), Go replace targets staged
beside consumers. Verified: twomod fixture 0% → 100% semantic; dagger
go **79.3% → 85.6%**, `core/integration` **59.3% → 96.3%**, +8,014
semantic edges (7,322 into the replaced sdk/go); lanes still exactly
138 — zero disagreements added. C-33 **lifted** one session after
registration. Residuals in the lifted entry (separate Rust workspaces
unstaged — no evidence; TS alias imports stay C-12).

**2026-08-18 (extraction at scale — dagger, ADR-048):** first deep
extraction target `~/dagger` (~265k detected call sites, 84 TS zones,
25 Go modules — 50× the prior largest). Three changes: the ingest
summary's **per-directory capture view** (Max's ask; pure rollup over
`resolution_coverage`, depth 2, ranked by *cannot resolve* so
by-design classes cannot bury real misses, cut always stated),
**wrapped-chain shape read** (Go/Rust/TS trailing-dot chains are
attr-calls, not unknowns — dagger Go unclassified 9,131 → 359; Python
excluded, comments guarded, C-32 restated), and **per-unit lane B
degradation** (one broken tsconfig zone had zeroed all 84 zones' TS
semantics; now each zone/module/cargo-root fails alone with a named
degradation — TS 0% → 18.8%, sdk/typescript 63.7%). **C-33
registered, not fixed:** in-repo references across indexing units
(root module → `replace`d `./sdk/go`) resolve in neither unit's index
— staging strips siblings AND decode discards the moniker on external
rows; candidate fix (cross-unit moniker join) is in future_additions
awaiting Max's review because it argues with C-12's
no-reconciliation stance. Lanes at scale: 36,439 dual-resolved sites,
138 disagree (0.38%) — mostly Go fallback vs build tags/interfaces
(C-7/C-8's floor measured), plus a TS decorator off-by-one where both
lanes cite the same declaration (noted, unfixed). No §3.8 row: no
hand-verified edges (P11).

Languages wired: **Python, TypeScript/JavaScript, Go, Rust** (+ the
Terraform/HCL layer), each with a syntax provider and a pinned SCIP
indexer, joined by the one range join. **"Supported" is scoped by P11**
(ADR-044): the claim extends exactly as far as architecture §3.8's
evidence table — Python and TS/JS multi-repo; Go verified on one repo
(this one); Rust on one small repo. Adding a language is §3.7's
checklist — now **four** steps, the fourth being verification evidence
recorded in §3.8 in the same commit — proven twice (Go, Rust).

**2026-08-16 (blindness is context, ADR-047 — built, awaiting Max's
review):** the register and tail view are now **agent-facing
functionality**, per Max's direction ("knowing what we cant see is very
useful… we aid agents in pointing to the work they do need to do").
`list_blind_spots(scope)` is the sixth knowledge tool on the session
proxy — the complement of the other five: scoped capture rollup, the
always-on denominator statement (C-1/C-4/C-5 are in no count), environment
gaps, degradations, worst files, and a meaning line per present class
naming its C-n entry. The **derivation contract** is architecture text:
derived context must carry the stated complement beside the captured
fraction, and derived policy treats unseen regions as low-evidence
(narrow or escalate) — requirements recorded on the unbuilt milestone.
Proxy binaries rebuilt (static + sandbox copy). Not scoped: review/
surface consuming blind spots (future_additions).

**2026-08-16 (the tail view, ADR-045 — built, review passed):**
the unresolved call-site remainder is now **classified by observation**
on every ingest: `resolution_coverage` rows carry `tail`
(checker-origin classes from tsextract v4 — `local-binding` =
below-C-9's-floor, seen and deliberately not modelled; pinned
`builtin-name` lists; text-shape `attr-call`; `unclassified` as the
honest residue), and `hobbes ingest` prints the per-language capture
line — always "% **of detected call sites**", never "of the repo" —
split *seen, not modelled by design* vs *cannot resolve*. Standing
rule (Max): a class is a checkable observation or it abstains; never
rationalise the unknown from a checklist of potentials. Measured on
the three verified repos: kbet's tail is 61% below-floor locals with
**9 of 1,339** sites unclassifiable; the *cannot resolve* group is the
concentrated remainder — anything in it that turns out to be needed
for derived context becomes a direct register entry. C-2 amended,
C-32 added (classifier boundaries: TS-only origins, pinned lists).
Same day, run against private-repo-A (94.3% python capture, best measured)
and qwen-pathology (82.6%, env-missing surfaced): their unclassified
residue was bare calls of **imported names**, so `import-binding`
joined the classes (lane A's own FromImport parse, Python-only,
binding-proven — ADR-045 amendment) — private-repo-A unclassified 46 → 4,
qwen 6 → 1. **Review passed by Max**; C-32's candidate fix then
applied (ADR-046): `pysource`/`gosource` collect sub-module bindings
with enclosing-function extents, and `local-binding` fires on scope
containment for Python and Go — dogfood unclassified went **45 → 0**
(python) and **20 → 0** (go); Rust deliberately not extended (empty
verified tails — a collector with nothing to verify against would be
the P11 mistake at class scale). Fleet-wide honest residue: 112 sites,
all but one in TS zones, plus attr-call — the genuine
untypable-receiver limit — everywhere. C-32 restated as proof grades
(declaration-proven TS vs binding-proven-with-containment Py/Go).

**2026-08-16 (post-v2 doc session):** the constraints register is split
into **Active** and **Lifted** parts (ADR-043) — lifted entries carry a
required Was / Lifted-by-technique / Residual-edge-cases format, because
a lift's boundary is where the old concession quietly survives. P11
added (coverage claims scoped to evidence; C-31 registers the residue,
unsurfaced) and the **guaranteed-fraction** framing is now architecture
text in "Where this is going": Hobbes as insurance — the captured
fraction's integrity outranks its size, and the uncapturable complement
is *identified* as needing care, never model-filled. Follow-up owed:
README's language list re-read against §3.8.

**V2.M7 — Rust, the P7 proof (ADR-040).** Hobbes ingests Rust with
**zero new builder code**: the diff is `rustsource.py` (fifth syntax
provider), an `INDEXERS.rust` entry (rust-analyzer's native `scip`
export, a rustup component, no version flag — the moniker version is the
crate's own, the first indexer where Decision 1 needs no pin), one
staging function (nearest Cargo.toml collapsed to `[workspace]` roots),
and Go's four orchestration touches repeated. `syntax_kind`: unset for
0 of 169 — the third indexer confirming ADR-037's mandatory step 2.
Verified on `~/rust_proj` (33 call edges, all semantic, 100%
hand-checked; lanes clean) and on the dogfood repo (six languages,
3,085 sites, 0 disagreements).

Four things M7 found that later sessions should know: **macro arguments
are token trees** to tree-sitter, so `rustsource` does call-shape
detection inside them (an identifier followed by a parenthesized token
tree), and rust-analyzer's pre-expansion positions make the join meet —
without this, Rust test reach would be empty. **`terminalName` was
losing every impl method** (`impl#[Counter]new().` → `[Counter]new`);
fixed, so value-method calls now promote to semantic. **The
ambiguous-definition drop (C-28) fired on scip-go too** and removed two
Go module edges that had been false since V2.M5 — a register entry
generalised the day it was written. **I-4 turned red on cue** when
`rustsource` landed and was amended rule-block-only, the ADR-039
mechanism doing its job the first time it was asked. Register adds:
C-28 (dup monikers dropped), **C-29 (ingesting a Rust repo executes its
build.rs/proc macros — disclosed on stderr every rust ingest)**, C-30
(crate registry needed for third-party semantics), C-9 amended (macro
is the fifth graph kind).

**V2.M6 — the unified invariant checker (ADR-039).** Records carry
`check: graph | emit | soft`; the rule block is top-level; `compile`
holds only the target and exists only for emit. The checker judges every
rule it can see — emit records included, so the emitted tool always has
an in-process answer to agree with — and verdicts are **tier-aware**:
semantic evidence proves, syntactic evidence yields `suspect` (a new
result between fail and unknown, still exit 1), **except** on
`ext:`/`env:`/`tf:` edges, where syntactic is the only tier that exists
and counts as proof. All eleven records migrated; **I-4 restated a third
time** — the enumerating wording had gone stale twice unnoticed (the old
rule *fails* on today's graph, citing gosource.py:39), so the statement
now states ownership and the enumeration lives only in the rule block
the checker holds against the graph. **lint-imports ran for the first
time in the project's history and immediately found an emitter bug**
(unmatched ignore pairs from the except cross-product failed a clean
repo; C-19 narrowed to the three still-unexecuted tools). Soft verdicts
are **source-based** (C-18 lifted): `--soft` runs the M4 reviewer
sandbox at the review's head ref (`hobbes-session --ref`, new) with the
diff hunks in the prompt; a missing sandbox errors on the answer rather
than falling back. P10's parked ask (broad-handler-encloses-refusal)
stays parked — the other subsystems need typed refusals before a checker
kind can want them.

**C-24 lifted (2026-08-15, post-M6, Max-approved):** JSX instantiations
are call sites in the tsextract syntax provider — the condition was that
"in every meaningful sense" keeps its outliers named, and the lifted
entry names them (component-like tags only, framework-mediated timing =
call-behind-a-branch, closing tags are not sites, a component passed as
a value stays `uses`). Verified on kbet: 12 test→component render edges,
all semantic tier, 108/174 tests now reach a component; lanes agree on
both repos.

**V2.M5 — Go, and the checklist correction (ADR-037).** Hobbes now sees
**its own Go**: 216 nodes across `go, hcl, javascript, python, typescript`,
813 Go call edges (20/20 hand-verified), 712 tests, 33 routes. The dogfood
loop is closed for the first time.

The milestone was written to prove §3.7's checklist sufficient and
**disproved half of it**. `scip-go` populates `syntax_kind` for **0 of
18,682** occurrences — exactly as `scip-python` does for 0 of 8,575 — so a
language with an indexer and no lane A grammar gets references and **no
`calls` edges at all**. §3.7 step 2 is now a **mandatory syntax provider**,
and C-6 is generalised: it is not a scip-python gap that an upgrade could
close, it is the ecosystem's, and **a register entry can be wrong by being
too specific**. P7 survives narrowed — the *builder* took zero Go lines,
which is the claim that matters; "an indexer entry plus an optional pack"
was never true.

Three Go specifics worth knowing before touching it: a **type conversion
is spelled exactly like a call** (`Decision(s)`), so lane A drops
conversions using the one thing SCIP lacks — which names are types; a **Go
import names a package, not a file**, so lane A emits no in-repo import
edges and the join raises them from real resolutions; and **`scip-go`
emits documents outside the repo** (the Go build cache), filtered in the
helper by `insideRepo` so every language is protected at once.

**V2.M4 — enrichment packs (ADR-035).** Framework knowledge left the graph
builder: four packs (`http-python`, `cli-python`, `http-ts`, `terraform`)
in `extract/packs/`, **registered in a code tuple and activated by
detection**. There is no `hobbes.yaml` and there is not going to be — the
same answer ADR-027's amendment gave for indexer config, and the ADR-012
tension *dissolves* rather than being resolved, since nothing is authored.
Each pack is an **adapter over the retained implementation**, not a
rewrite: `terraform.py`'s 372 hand-verified lines got a new caller.
`graph.json` gained a `packs` list (additive; no schema bump — it changes
how no existing field is read). Exit criterion — removing a pack removes
exactly its contribution, adding it back restores byte-for-byte — is
asserted per pack in `test_packs.py` and was verified on private-repo-A and the
dogfood repo, where removing `terraform` drops its 5 edges and 3 `tf:`
nodes but **keeps all 5 `env:` nodes**, because Python reads them.

**P10 — a specific safety guarantee outranks a general safety system
(ADR-036).** Max's rule, from the M4 review, and it governs every
mechanism, not one milestone. Wrapping packs in `except Exception` for P6
degradation swallowed the `.tfstate` refusal that guards **I-1**:
`ingest --tf-plan prod.tfstate` started *succeeding* with a warning. Both
mechanisms were right alone; the general one won by default, because
`except Exception` is broader than anything inside it.

So: a general mechanism must be written so it **cannot** absorb a specific
guarantee — it **names what it will not handle and re-raises that first**
(`run_packs` re-raises `PackRefusal`), a refusal is a **distinct type**
rather than a message, and the specific guarantee keeps **its own test at
the level a user meets it**. Rank by importance × coverage: the broader the
reach, the less it may decide on its own. Intent is not enough — whoever
widens the general mechanism is not thinking about the specific one.

Watch this in the mechanisms that already exist: expire-to-deny, the
narrative runner's corrective retry, the proxy's exec wrapper. **Hobbes
cannot catch this itself yet** — it was found by an M3 test, not by the
system; parked in `future_additions.md` for V2.M6's checker.

**The architecture is one running document (ADR-033, 2026-08-15).**
`hobbes-architecture-v2.md` is gone: it became `hobbes-architecture.md`,
and the old v1 file is now `hobbes-architecture-v1.md`. A versioned
architecture doc was wrong about its own subject within three milestones —
it claimed moniker-keyed node ids (the range join made them unnecessary;
real ids are path-based), claimed lane A's resolver was deleted (ADR-031
demoted it), and pointed at a `hobbes.yaml` that does not exist. All three
were corrected in the same commit as the ADR. **The rule: a change that
moves the architecture patches that file in the same commit as the code.**

**P8 — every concession is a registered constraint (ADR-030).** It governs
the whole project, not one milestone: when Hobbes cannot recover
information, the gap gets a `C-n` entry in `docs/constraints.md` **plus the
place a user meets it**. An entry whose only surfacing is a document is
recorded `unsurfaced` and is debt. P6 covers the run that failed; P8 covers
what was never knowable. Max: "hobbes is unusable if its a known liar, even
less usable if its fake honest."

**P12 — a Hobbes test decomposes, or it is not a Hobbes test (ADR-082,
2026-08-23).** Planner-defined units, more than one single-use agent
with distinct roles, every implementer's window smaller than the task —
or the run is reported as *model + prompt*. The decomposition slipped
out in two locally-justified steps (ADR-077 removed the split, ADR-078
the planner) and four 27B pairs were called Hobbes tests before Max
caught it; the method must refuse the label, not a person.

**P9 — a provider's limits are Hobbes's limits (ADR-034).** Semantics come
from third-party indexers Hobbes runs and does not wrap, and their blind
spots land in our graph. Never disown one as "scip-python's problem" — the
user ran `hobbes ingest`, and a missing edge reads as an absent call either
way. An inherited limit registers under P8 **plus** a `Provider` line naming
the provider and pinned version, because unlike our own concessions it can
end on an upstream release. C-6 and C-23 are inherited; C-9 is ours and says
so. V2.M5 (`scip-go`) and V2.M7 (rust-analyzer) each owe a provider-limit
review at their exit, not just a working ingest.

Artifacts are at **schema v4** (ADR-028): every edge carries a `tier`
(`semantic`|`syntactic`|`dynamic`) and every evidence entry a `lane`.
v4 is *additive* over v3, so consumers declare a version **range** —
`hobbes/artifacts.py`, `go/internal/derived`, and `api.ts` are the three
gates, and they refuse rather than half-read. Lane A emits everything as
`syntactic`/`tree-sitter`; nothing claims `semantic` until lane B lands.

Lane B (ADR-029) runs for **Python only**. Two providers, never one:
**tree-sitter knows a call site is a call**, **SCIP knows what it resolves
to**, and they meet in the evidence IR (`extract/evidence.py`) before any
graph exists. SCIP alone cannot answer "is this a call" — it populates
`syntax_kind` for none of its occurrences — so lane A keeps call-site
*detection* and loses only call *resolution*. A resolution no call site
claimed becomes a `uses` edge (not `references`, which ADR-010's Terraform
layer already owns).

Lane B never writes to the target repo: it stages a copy under
`~/.hobbes/cache` (`extract/staging.py`, ADR-027's seven-clause contract).
`HOBBES_SCIP=0` disables it, and the pytest suite sets that by default —
tests marked `lane_b` opt in. **Clause 2 is refined by ADR-032:** authored
source is always copied, but a regenerable dependency tree
(`node_modules`, 222 MB on kbet) is **symlinked**, because the
copy-preserving alternative measured a 6.4% loss of semantic references.
Two properties are asserted in `test_staging.py` rather than assumed —
indexing writes nothing through the link, and `remove_stage` unlinks it
instead of recursing into the target (C-22). That second one is the
mistake that would delete a user's dependency tree.

**M2's asterisk is discharged (V2.M3, 2026-08-15).** kbet produces 231
semantic TS call edges, 20/20 hand-verified against their cited lines.
The lane-agreement report (`hobbes lanes`, exit 1 on disagreement) runs
clean on all three sanctioned repos — hobbes 1789 sites compared / 0
disagree, private-repo-A 976 / 0, kbet 359 / 0.

Three things M3 settled that later milestones depend on:

- **The join is the only producer of symbol edges**, for every language,
  and it runs *whether or not lane B does* — with no semantic input every
  site falls to the fallback arm. P6 holds by construction, not via a
  second code path, so the degraded path is exercised on every test run
  (the suite is `HOBBES_SCIP=0` by default).
- **Lane A's resolver is demoted, not deleted (ADR-031).** It stops
  producing edges and becomes the join's fallback. Deleting it — which
  the plan said to do — would leave any repo without a working indexer
  holding no call graph at all.
- **A TS zone is indexed at its own `--cwd`, so its paths are
  zone-relative** and must be re-rooted before the join (`_rebase`).
  Getting this wrong is silent: no error, just very few semantic edges.
  Python never hits it because its `--cwd` is the stage root.

Three things ADR-027 settled that any v2 session needs to know:
`--project-version` is always pinned (its default is the git revision,
so ids would otherwise change every commit); indexer config is **per
repo**, not just per language, and a src-layout Python repo silently
loses every test→source edge without it; and only ~14% of SCIP
definitions are graph-worthy, so the descriptor filter comes before
anything else.

*(Paused 2026-08-13 for Max's move; resumed 2026-08-14 on v2.)*

**Both of the things that were waiting on Max are now settled
(2026-08-15):**

1. **ADR-026** (two decision surfaces + `hobbes up`) — **verified by Max**:
   he ran `hobbes up` against this repo, and reported everything displaying
   and running correctly in the UI. Re-ingest confirmed — `.hobbes/derived`
   is stamped at HEAD, schema v4, 126 nodes / 258 module edges / 2012 symbol
   edges. The review debt is discharged.
2. **M9, "Hobbes as an application" — parked.** His call: "the application
   was a thought i had wanting it less and less but maybe one day."
   `docs/m9-application-mode.md` is kept as the record of the thought, not
   as a roadmap item. **Hobbes stays local**: on the box, against a repo on
   disk (architecture §10). Do not start it, and do not design toward it.

**Box note (2026-08-13):** `go.mod` needs Go ≥ 1.26 and Fedora ships
1.25, so `~/.local/go/bin` must precede `/usr/bin` on `PATH` — fixed in
`~/.bashrc`. `hobbes` and the four Go binaries are symlinked into
`~/.local/bin`, so `hobbes up` works from any repo; they point at
`go/bin`, so a rebuild needs no relinking.

- Exactly two things need a human: **intent** (the repo policy) and
  **invariants**. Everything else is a natural part of the mechanism.
- `hobbes up` = init if absent → re-ingest when the artifacts' stamped
  SHA is not HEAD → serve → **block until the decision queue is empty**.
  It **never narrates**: quota is offered in the UI, never spent by a
  script someone ran to get started.
- Intent is `repo.policy` edited in the UI (not a layer compiling down
  to it), with the diff shown before writing. An unconfirmed policy is a
  pending decision, not a silent default.
- Invariants are approve / deny / edit (keys `a`/`d`/`e`). Approving
  writes a real record into `.hobbes/invariants/`.
- **Decisions key on a content hash of (statement, scope), never the
  id** — `INF-n` is positional, so an id-keyed approval would bless
  different text after the next narration. The hash lives in Go (writer)
  and Python (reader); `pipeline/tests/fixtures/decision-keys.json` pins
  both. Denials persist too.
- Amends ADR-019 (promotion is still a file, different trigger) and
  ADR-022 (the surface now writes three things, each a readable file).
- Known limitation: decisions are untracked (ADR-012), so they do not
  survive a fresh clone — see `future_additions.md`.

- M8 (reviewed, passed): reviewer flow + invariant compiler v0.

  - ADR-024: invariant records live one-per-file in `.hobbes/invariants/`.
    `statement` is the prose; **`compile.rule` is structured**, because a
    prose rule cannot compile without an LLM and enforcement must stay
    deterministic (sequencing rule 1). Three rule kinds
    (forbidden-import, pattern-absent, resource-attribute) plus `soft`.
    Only `confirmed` records compile or receive verdicts; `retired` stays
    as history; an `inferred` record here warns and stays inert.
    Compilation is text generation — **no target toolchain needed**, and
    none is installed here.
  - ADR-025: `hobbes review <base>..<head>` computes verdicts **at both
    ends**, so a regression this change introduced is distinguishable from
    breakage it inherited. Exits 1 on regressions, lost guards, or
    unguarded new code. Spends no quota unless `--soft`.
  - **Six confirmed invariants** (I-1..I-6), promoted from the M5 inferred
    set. I-3 was rewritten during promotion: the inferred wording claimed
    pushes escalate, which the push-deny made false. **That exact clause
    came back** on 2026-08-15 in I-9, approved through the surface before
    anyone noticed — corrected on the same day. If you are promoting an
    inferred invariant, read the confirmed records covering its scope
    first; nothing in the queue does it for you (C-21).
  - **`git push` is denied**, not escalated (see Conventions).
  - The **reviewer role** is now enforced at the mount tier: worktree ro,
    no Edit/Write/exec, and `.hobbes/derived/` mounted ro for every role
    so the knowledge tools have something to read.
  - Exit check (2026-08-11): branch `m8-exit-check` added a plausible
    feature that duplicated the parser; review reported I-4 REGRESSED with
    both import sites cited and exited 1, and the fix flipped it to PASS.
    Replay with `hobbes review ace9a08..cdbc085` (exit 1) and
    `ace9a08..7d52f2e` (exit 0). A real rootless-Podman reviewer session
    scored 5/5. 205 Go / 297 pytest / 38 vitest / 18 node.

- M7 (reviewed, passed): the web surface — ADR-022 `hobbes-web` (a Go
  daemon serving a loopback-only JSON API plus the embedded SPA) and
  ADR-023 graph conventions. Exit check on the dogfood repo and kbet,
  including escalation approve/deny in the browser against commands
  really parked by `hobbes-proxy`.

  - ADR-022: the surface is a **Go daemon** (`hobbes-web serve --repo
    DIR`) serving a JSON API and the embedded SPA — not a Python
    `hobbes serve`, because approve/deny would otherwise reimplement the
    ADR-016 queue. Extractor artifacts pass through byte-for-byte;
    narrative artifacts are decoded only far enough to badge.
    **Loopback-only, enforced** at bind and per-request `Host` (no auth,
    and it can approve commands). `/api/source` refuses traversal,
    symlink escapes, binaries, oversize files, and `.tfstate`. Missing
    artifacts answer 404 with the command that produces them.
  - ADR-023: interactive graph conventions — module level only, shape and
    colour by kind, edge style by type (unknown types drawn labelled, not
    invisible), **externals hidden by default**, and **focus mode**
    (breadthfirst over the selected neighborhood, the rest dimmed in
    place). Labels strip the directory every path-shaped id shares, or a
    TS repo renders 89 identical `betchat/frontend/sr…` labels.
  - The SPA lives in `web/`, is embedded into the binary, and **must be
    rebuilt on both sides**: `npm run build` then `go build`. The pure
    layer (`web/src/lib/`) carries the vitest cases; the tabs render what
    it returns.
  - Exit check (2026-08-11): five tabs real on the dogfood repo (70 nodes,
    234 tests, 37 artifacts, 9 stale); a claim's pin resolves to the line
    that supports it; two escalations parked through the real proxy —
    approve unblocked and ran it, deny refused it, both logged with the
    approver; kbet (104 nodes, 174 tests, no narrate pass) serves and
    degrades correctly. 189 Go / 226 pytest / 38 vitest / 18 node.

- M6 (reviewed, passed twice): TS/JS extraction via the `tsextract/`
  Node helper (ts-morph) invoked as a subprocess — the ADR-003 pattern;
  supersedes ADR-005's tree-sitter-for-M6 aside per the source docs.
  Facts JSON in,
  artifacts out: checker-resolved imports/calls (false edges worse than
  missing; nested declarations omitted), path-based module ids
  (`src/flow`), `ext:`/`env:` nodes on M3 conventions (env joins now
  span Py+TF+JS), Express/Nest routes, test inventory for
  vitest/jest/**node:test** with file-level static reach.
  `HOBBES_TSEXTRACT_CMD` overrides; TS files + no helper = hard error,
  never a silent skip.
  - **Schema v3**: per-test `framework` field (global one gone);
    `languages` may include typescript/javascript. Slash-bearing ids nest
    narrative artifacts under `docs/modules/`; `get_module_doc` follows,
    traversal blocked both sides.
  - Exit check (2026-08-11): private-repo-A ingest (207 nodes, 602 module edges,
    hcl+javascript+python); all 11 JS module edges + 9 call edges and 9
    node:test mappings (reach exactly the 8 imported flow.js symbols) +
    1 pytest mapping verified by hand — 100%. The spot-check caught and
    fixed a nested-declaration call-edge leak.
  - Verified on **kbet** (`~/projects/kbet`, Max-sanctioned real Vite+React
    TS app): 20/20 edges + 10/10 mappings, 100%. Forced real fixes:
    **tsconfig zoning** (nearest tsconfig per file, one Project per zone —
    `@/*` aliases resolve; un-deferred same day), checker-crash
    resilience (per-file/stage degradation → `extraction_errors` +
    ingest WARNING), `process.exitCode` (64KB stdout truncation),
    call-initialized consts as `kind: const` symbols (zustand/axios;
    require handles excluded), `require()`/dynamic imports via
    `ts.resolveModuleName`, test `reaches_modules` unions resolved
    imports, TS-only repos no longer claim python. 226 pytest / 147 Go /
    18 node --test cases. Still deferred: per-test JS reach,
    jest-globals detection, package.json bin, cross-zone imports
    (future_additions).

- M5 (reviewed, passed): narrative pass — ADR-019 artifacts
  (`.hobbes/derived/docs/`: module docs, behavior indexes,
  `invariants.inferred.yaml`; claims `{text, pins}` validated before
  write; blob-level staleness, uncommitted edits count), ADR-020
  `hobbes narrate` (headless tool-less `claude -p`, one call per unit,
  incremental missing-or-stale, one corrective retry;
  `HOBBES_CLAUDE_BIN` override) + `hobbes docs status`, and
  `get_module_doc` on the proxy. Exit 3/3 on the dogfood repo: 37/37
  units (396 pinned claims), 10/10 sampled claims resolve, a deliberate
  edit flips exactly the right badge. 6 inferred invariants await Max's
  confirmation (inert until moved into `.hobbes/invariants/`);
  `list_invariants` still deferred to M8. Sandboxed cartographer
  sessions + system narrative parked in future_additions.

- M4 (reviewed, passed): the policy proxy + sandbox + flight recorder —
  `hobbes-proxy serve` (per-session stdio MCP, policy-checked `exec`,
  ADR-013/014/015), escalation queue with CLI approve/deny and
  expire-to-deny (ADR-016), knowledge tools (ADR-017), and
  `hobbes-session start` (fresh local clone, rootless Podman, empty-env
  baseline, ADR-018). M4 exit check passed 5/5 in a real sandbox with a
  scripted implementer (quota-free); per-command secret brokering layers
  on later.

- M0: policy YAML format (ADR-001/002), Go merge engine +
  `hobbes-policy resolve` CLI (ADR-003), Python CLI skeleton with policy
  passthrough, dogfood repo policy.
- M1: deterministic Python extractor (ADR-005/006/007;
  **tree-sitter pinned <0.26**, 0.26.0 core segfaults). `hobbes ingest` /
  `hobbes init`.
- M2: Mermaid export (`hobbes render`, ADR-008), graph
  diff (`hobbes diff <base>..<head>`, ADR-009). Deferred ideas live in
  `docs/future_additions.md`.
- M3: Terraform/HCL extractor (`extract/terraform.py`, ADR-010) —
  `tf:` nodes (resource/data/tf-module), `references` edges,
  cross-layer joins (`env-set` → `env:VAR` ← `env-read`, and `packages`
  path joins onto discovered modules), optional `--tf-plan` enrichment
  (tfstate lookalikes refused). graph.json schema v2 (`languages` list).
  Builtin tfstate deny floor in the Go engine (ADR-011). Test repos
  (Max-sanctioned): private-repo-A (a private Py+JS+TF repo, name and
  location withheld; cross-layer `packages` edge
  verified by hand at infra-core/lambda.tf:5 → handler.py) and
  `~/qwen-pathology` (Python).
- ADR-012: Hobbes files are personal — `ingest`/`init` gitignore the
  whole `.hobbes/` in target repos (tracked-content guard keeps this
  repo's dogfood versioning). 124 pytest cases.
