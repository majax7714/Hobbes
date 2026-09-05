# CLAUDE.md — working notes for coding agents (and humans) on Hobbes

This file is the **entry point**, not the record. It is kept short on
purpose: Hobbes' own thesis is that an agent should work under a small,
derived context, and a 600-line agent file argues against it. History
lives in `docs/BUILDLOG.md`; the resume point is `docs/session-handoff.md`.
Read those when you need them, not by default.

## What this project is

Hobbes: **a multilingual, deterministic code graphing environment.** It
ingests a repo and derives a policy-governed environment where agents do
line-level work and humans review at the concept level.

Three properties, in order of precedence — **accurate** (a wrong graph is
worse than no graph, because it is believed), **deterministic** (parsers
and indexers build the skeleton, never a model; generative work sits on
top and is pinned to it), and **honest** (determinism promises the same
answer twice, not a true one — so every edge carries a tier, every
concession is registered, and a provider's limits are owned as ours).
The long-run goal is **single-use agents under derived, systematic
context**; the graph makes that derivation possible, and the sandbox
makes a forbidden command *absent* rather than merely refused.

**Source of truth:** `docs/hobbes-architecture.md` — the running
architecture (ADR-033). Read it before writing code. It carries no
version number and is amended **in the same commit** as any change that
moves it. If it describes something the tree does not do, that is a bug
in the file — fix it and note it in the BUILDLOG.

Locked decisions (not open for relitigation): **D1** Python + Go + TS
split by focus, **D2** Podman rootless for session isolation, **D3**
Cytoscape.js for the interactive graph. **Hobbes stays local** — on the
box, against a repo on disk (architecture §10); the application mode in
`docs/m9-application-mode.md` is parked, do not design toward it.

## Where to read next (by task)

| You are…                                  | Read                                                                 |
|-------------------------------------------|----------------------------------------------------------------------|
| resuming the active programme             | `docs/session-handoff.md` → `docs/adr/092-ingest-containment.md`     |
| picking up an item from the backlog       | `docs/workstreams.md` (W0–W5), then the entry it cites               |
| touching extraction or the graph          | architecture §3 + `docs/extraction-evidence.md` + `docs/constraints/README.md` |
| grading the graph against an oracle       | `docs/oracle-grading.md` + ADR-089; misses by class in `docs/oracle-misses.md`; the oracle's own defects in `docs/oracle-defects.md` + their review/tally in `docs/oracle-defect-review.md` |
| touching derivation / agents / the bench  | architecture §6 + `docs/agent-mapping.md` + `docs/benchmark-hypotheses.md` |
| running the test-time-training experiment | `docs/olmo3-ttt-validation.md` + ADR-099 (its order of work is step-gated); results in `docs/olmo3-ttt-results.md` |
| evaluating Calvin potential (the current work) | `docs/calvin-potential.md` (M0, run on four keys 2026-09-04; §10 results, §8 step-gated) + the probe record `docs/ttt-cells/calvin-m0-probe-2026-09-03.md` |
| deciding anything                         | `docs/adr/` — one short ADR per decision the architecture doesn't make |
| bringing Hobbes up on a new repo          | `docs/first-run.md`                                                  |
| looking for why something was done        | `docs/BUILDLOG.md` (append-only, one dated entry per session)        |

## Project map

- `go/` — Go module (`github.com/majax7714/Hobbes/go`). `cmd/hobbes-policy`
  + `internal/policy/` (the merge engine: builtin floor → box → repo →
  role → folder → agent; deny overrides allow; allow|deny|escalate). `cmd/hobbes-proxy`
  is the per-session MCP daemon: `internal/proxy/` (policy-checked `exec`
  + read-only knowledge tools), `internal/recorder/` (JSONL flight log),
  `internal/escalation/` (park/approve/expire queue), `internal/knowledge/`
  (graph tools over `.hobbes/derived/`, incl. `list_blind_spots`).
  `cmd/hobbes-session` + `internal/sandbox/` launch a session in rootless
  Podman (`--mount` binds a host tree read-only, ADR-100). `cmd/hobbes-web` + `internal/web/` serve the loopback-only API
  and the embedded SPA. Only external deps: `yaml.v3`,
  `modelcontextprotocol/go-sdk`.
- `pipeline/` — Python package `hobbes` (uv, src layout). `cli.py`;
  `extract/` (discover → per-language syntax providers (`pysource`,
  `tssource`, `gosource`, `rustsource`, `javasource`) → lane B SCIP join
  → graph/testmap → `packs/` → emit; `containment.py` runs every lane B
  step in the sandbox image — the executing steps refuse without it,
  C-64; Java resolves in a networked pass that holds no sources, then
  indexes offline, C-66/ADR-097); `derive/` (`hobbes plan`: impact →
  cochange → partition → contracts → manifests → changespec; `holes.py`
  is the Calvin M0 hole language, v1, `template.py` its generator —
  `hobbes template`, the anchor and structure passes — and `ground.py`
  grounder v0 — `hobbes ground`, placement and exact-or-NULL binding
  with a read-trace — `adapter.py` the orchestrator adapter, arm T's
  driver, the one place a model is called, and `harness.py` the local
  harness, ADR-100: `hobbes verify` runs a diff's guarding tests in the
  sandbox with and without it, arm O's session runs through
  `hobbes-session` under `calvin.box.policy`, `scripts/calvin_scripted_agent.py`
  stands in for the model); `run/`
  (`hobbes run`: agents, orchestrate, roles, mail, coverage); `agent/loop.py`
  (the owned stdlib tool loop over an OpenAI-compatible endpoint);
  `bench/` (`hobbes bench`: instances → workspace → two arms → one meter →
  evaluator → report); `ttt/` (`hobbes derive-corpus`: the derived layer
  rendered as a training corpus for the test-time-training experiment,
  ADR-099, plus `units`, `score`, `report`, `probe`, `cell`; scripts
  `modal_ttt.py`, `ttt_units.py`, `ttt_probe.py`, `ttt_cell.py`);
  `narrate/`, `invariants/`, `review.py`, `render.py`, `graphdiff.py`. Fixture repos under `tests/fixtures/` (miniapp / minits /
  minigo / minirust / minijava / canary-rust / canary-java / goshapes /
  twomod), excluded from
  collection.
- `tsextract/` — Node helper (ts-morph) emitting facts JSON for the join.
- `scip/` — lane B: pinned SCIP indexers (`scip-python`, `scip-typescript`,
  `scip-go` 0.2.7, rust-analyzer's `scip`, `scip-java` 0.13.1 in the
  image), `index.mjs` (the helper owns the SCIP typed-range decode),
  spike evidence.
- `web/` — the surface (Vite + React + TS, Cytoscape.js). `src/lib/` is the
  pure layer with the vitest cases; `npm run build` bundles into the Go
  embed dir — **rebuild `hobbes-web` after**.
- `sandbox/` — the one image (`Containerfile`: sessions *and* lane B ingest,
  ADR-092; JDK 17/21/25 + Maven + scip-java since ADR-096, ~2.8 GB) and
  the exit-check harness.
- `bench/calvin/` — the Calvin M0 experiment's artifacts
  (`docs/calvin-potential.md`): `templates/` holds the hand-written
  template, its render and its gold fills; the parent ledgers, the
  generated templates and the ground records live under
  `~/.hobbes/bench/calvin/` (regenerable, `scripts/calvin_probe.py`).
- `bench/oracle/` — the oracle-grading lane (ADR-089): its own Go module
  (`x/tools` RTA), one `oracle` binary (`export | go-rta | py-trace |
  rust-mir | java-javac | grade`), `ts/` (tsc), `py/` (the `sys.monitoring` tracer),
  `rust/` (a `rustc_driver` MIR walker on a pinned nightly), `java/` (a
  javac plugin riding the repo's own build; CHA for dispatch),
  `run-cell.sh`; grades the call graph against answer keys Hobbes does
  not control. Bench tooling, never product.
- `docs/` — architecture, ADRs, `constraints/` (the register of what
  Hobbes cannot tell you, one file per segment; `README.md` is the index), `extraction-evidence.md`, `BUILDLOG.md`,
  `session-handoff.md`, `workstreams.md`, `future_additions.md` (parked
  backlog), and the frozen v1 record.
- `.hobbes/` — dogfooding: `policies/` + `invariants/` versioned;
  `derived/` and `plans/` gitignored.

## Hobbes for Hobbes — the knowledge tools in your session

This repo's `.mcp.json` starts `sandbox/knowledge-serve` — the
**image's** `hobbes-proxy serve --knowledge-only` in a read-only,
offline container (ADR-087, ADR-094): six read-only tools over `.hobbes/derived/` —
`who_calls`, `tests_guarding`, `graph_neighborhood`, `get_module_doc`,
`list_invariants`, `list_blind_spots`. Use them instead of grep for
"who calls this" and "what tests reach this", and read
`list_blind_spots` for the directory you are editing before trusting
either — it names what the graph cannot see there. Every answer opens
with the ingest SHA and which Hobbes built the artifact; on a stale
warning, `uv run hobbes ingest`. Needs the sandbox image built (below)
and the repo ingested; rebuild the image after rebuilding the proxy,
or the tools answer with the old build (C-65). Always `uv run hobbes`
from this checkout — a `hobbes` on PATH may be another tree's (the
2026-08-28 incident, ADR-094).

## Build & test

Go ≥ 1.26, uv, Node. If a distro Go is older, a user-local Go must come
first on `PATH` or `go build` fails on the toolchain line. One-time:
`cd tsextract && npm install`, `cd web && npm install`, `cd scip && npm
install`.

```sh
# Go
cd go && go test ./...
go build -o bin/hobbes-policy  ./cmd/hobbes-policy
go build -o bin/hobbes-session ./cmd/hobbes-session
go build -o bin/hobbes-web     ./cmd/hobbes-web      # after `cd web && npm run build`
CGO_ENABLED=0 go build -o bin/hobbes-proxy ./cmd/hobbes-proxy   # MUST be static:
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy  # it is mounted into the sandbox
(cd ../sandbox && podman build -t hobbes-session:local -f Containerfile .)  # lane B and the knowledge tools need it (ADR-092/094)

# Oracle lane (bench tooling; fixture self-test — Python via uv, Rust via the nightly driver)
cd bench/oracle && go test ./...

# Web
cd web && npm test && npm run build

# Python (the suite runs with HOBBES_SCIP=0 by default; `lane_b`-marked tests opt in)
cd pipeline && uv sync && uv run pytest

# Everyday commands
uv run hobbes up                      # init → ingest → serve → block on decisions
uv run hobbes lanes                   # lane agreement; exit 1 on disagreement
uv run hobbes invariants check|compile
uv run hobbes review main..my-branch  # exit 1 if it needs attention
uv run hobbes plan "proposal" --seed some.module
uv run hobbes run <task> --dry-run
uv run hobbes bench select|run|report # runs spend GPU/quota — see the standing policy
```

Suite sizes at the last check (2026-09-05): 1,241 pytest (+3 `lane_b`) /
299 Go + 39 oracle-lane Go / 52 vitest / 32 tsextract + 32 scip node
tests. Keep them green. CI (`.github/workflows/ci.yml`, ADR-095) runs
them all on every push; `scripts/ci-graph.sh <base>` is the graph job
(image build → ingest → stamp check → lanes → compiled invariants →
review → `lane_b` pytest) and runs the same way on a box.

## Conventions

- **Milestone order is strict.** Do not start work on stage N+1 while
  stage N's exit criteria are unmet and unreviewed by the project lead.
- Tests accompany the code they test **in the same commit**.
- Conventional commits, scoped: `feat(policy): …`, `fix(cli): …`,
  `test/docs/chore`.
- One short ADR (`docs/adr/NNN-title.md`) for every design decision the
  architecture doesn't already make. Number sequentially (last: 100).
- **Every concession of information gets a `C-n` entry in its segment
  file under `docs/constraints/` (index: `README.md`), in the same commit** (P8, ADR-030), with a
  *surfacing status* naming where a user meets the limit. `unsurfaced`
  is debt. Inherited provider limits add a `Provider` line (P9).
- **A specific safety guarantee outranks a general safety system**
  (P10, ADR-036): a general mechanism names what it will not handle and
  re-raises it first; refusals are distinct types; the guarantee keeps
  its own test at the level a user meets it.
- **Coverage claims are scoped to evidence** (P11, ADR-044): "supported"
  reaches exactly as far as architecture §3.8's table. Adding a language
  is §3.7's four-step checklist, the fourth being evidence in §3.8.
- **A Hobbes test decomposes, or it is not a Hobbes test** (P12,
  ADR-082): planner-defined units, more than one single-use agent, every
  implementer's window smaller than the task — or the run is recorded
  `arm=model+prompt`. The machinery enforces this (ADR-086).
- `docs/BUILDLOG.md` is append-only; one dated entry per session. Never
  edit old entries. `docs/session-handoff.md` is rewritten, never piled.
- Every package/module gets doc comments; public functions documented.
  No orphan code; no speculative abstraction.
- **Never read or write `.tfstate` files. Never commit anything under
  `.hobbes/derived/`.** In target repos, `.hobbes/` is gitignored
  entirely (ADR-012); only this repo versions its own.
- **Commit to `main` unless directed otherwise; say so plainly if you
  worked on another branch. Never `git push`** — sessions commit, the
  lead publishes after review. The repo policy denies `git push*`
  outright (an escalation is for commands a human might approve), so
  when testing the escalation queue use read-only commands: an approved
  escalation really runs.
- Runs of the benchmark harness spend real compute. **Experiments are
  parked** unless the lead clears a specific run; the 7B is the
  validation instrument (by speed, not capability) and the 27B is not
  touched until the mapping fixes are validated on it.

## Status (2026-09-05)

- **v1 (M0–M8) and v2 extraction (V2.M0–M7) are complete and reviewed.**
  Languages: Python, TypeScript/JavaScript, Go, Rust, **Java**
  (+ Terraform/HCL), each a syntax provider + pinned SCIP indexer joined
  by one range join; artifacts at schema v4; 93 registered constraints
  (71 active, 20 lifted, 2 superseded).
- **Java landed 2026-08-29 (ADR-096)** — the sixth language, all six
  milestones in one session: lane A, scip-java contained, a javac+CHA
  oracle (O8), four cells (two repos drawn at random) at **100%
  precision, 0 contradicted**, recall 66–98% with lane B and 23.5%
  without. **C-66 settled 2026-09-01 (ADR-097):** a Java unit runs two
  contained passes — the build's own resolution with a network on a
  stage with **no sources**, then the index **offline**; jsoup and
  petclinic re-ingested byte-identical. The residual (build logic with a
  network over its own build files and public caches) stays registered;
  an allowlisted egress proxy is the measured next narrowing (W1).
- **The derivation programme is built and under test.** `hobbes plan`
  (ADR-051), `hobbes run` (ADR-054), the staged harness run (ADR-059) and
  `hobbes bench` (ADR-055) exist and have been run live on the
  Qwen2.5-Coder-7B / Qwen3.8-27B ladder from Modal.
- **Current frame (ADR-084/085):** the planner is the
  requirement-decomposer — its handoff carries `requirements:` with an
  owning file each, `run/coverage.py` checks that every requirement has
  an owning unit (`--coverage strict`), and the implementer brief carries
  owned requirements and no proposal.
- **Latest run and its result:** the ADR-085 validation pair (5 Verified
  instances, 7B, two passes) ran on 2026-08-24. Machinery mostly held;
  0/5 solved (not the measure); **eight harness defects registered in
  `docs/adr085-validation-run.md`**. D1–D4, D7, D8 are fixed
  (ADR-091, 2026-08-27) and D5/D6 (ADR-093, 2026-08-28) are fixed,
  all validated with no model.
- **The benchmark is moving** from SWE-bench Verified (contaminated,
  C-39) to DeepSWE 1.1 on a mini-swe-agent substrate
  (`docs/benchmark-deepswe.md`); no H1 claim has been earned.
- **The oracle lane (ADR-089) is built and both phases have run:** Go
  and TS call edges compiler-graded against RTA / `tsc` (this repo,
  kbet, 19 dagger modules), Python trace-graded by the interpreter under
  this repo's suite (C-60), Rust compiler-graded against rustc's MIR
  (rust_proj, dagger `sdk/rust`) — every compiler-graded cell at 100%
  after ADR-090 vetoed the syntactic fallback's two wrong shapes (C-7
  priced first), the misses C-58 on every language plus Rust's generated
  code — C-58 now surfaced *partial* as the `below-floor` tail class. `docs/oracle-misses.md` and
  `docs/oracle-defects.md` are the honesty records (reviewed in full,
  `docs/oracle-defect-review.md`: seen tally + reviewer rules); the
  seven-repo loop of 2026-08-27 triaged 2026-08-28 (every compiler-graded
  cell at 100%); dagger's Go root waits on a bigger box.
- **The containment programme (ADR-092) is the active track:** *sandbox
  whatever executes repo-authored code*. Phase 1 built 2026-08-27 —
  every lane B step runs in the sandbox image, repo code never executes
  on the host (C-64; canary-tested; byte-identical graph on this repo).
  Phase 2 (O6/O7 oracles contained, regrades a no-op), phase 3
  (`--uncontained`, the `containment` stamp, `list_blind_spots`) and
  phase 4 (the two-layer statement: the knowledge layer is a complete
  deployment) landed 2026-08-28; reviewed by Max, the claim scoped to
  the runs made under it (P11). **The seven-cell triage is done**
  (2026-08-28): four fixes, every compiler-graded cell at 100%.
- **The four-repo extraction test (2026-09-02):** four random public
  repos, one per language, run through the knowledge piece by agents —
  no semantic edge wrong anywhere; **ADR-098** fixed lane A's Go
  fallback on build-constraint-split names (C-71, surfaced). quic-go
  oracle-graded at binary roots: 99.6% lower bound, 0 hobbes-wrong.
  **Its nine registered findings (C-72–C-80) and C-85 were all lifted
  2026-09-03** (four commits, easiest first, on Max's direction): the
  lanes/summary/blind-spot counts read true (C-75–C-77), the `http-go`
  pack reads receivers (C-78), dependency manifests widen (C-79), an
  expression receiver is a Python call site (C-80: 1,433 new sites on
  this repo), the Rust fallback abstains on ambiguous heads (C-72), a
  repo-internal directory link is walked once (C-73), workspace
  `node_modules` links mount their targets (C-74) and a venv-less
  Python repo indexes (C-85: 0.0% → 68.4% on a fixture). The four
  clones were re-ingested to confirm (`docs/extraction-evidence.md`):
  date-fns 0.1% → 80.1% capture with all 15 zones indexed, serde's
  copy gone and lanes at 0, and two findings the re-ingest exposed
  fixed the same night (C-89 TS overload lines, C-90 configs a
  tsconfig names).
- **The test-time-training experiment ran 2026-09-03 (ADR-099,
  `docs/olmo3-ttt-validation.md`):** `hobbes derive-corpus` renders the
  derived layer as a training corpus; a 300-step LoRA on it lowered
  Olmo-3-7B's gold-diff NLL on 147/147 units (replicated on fastapi,
  68/68) — but a shuffled-answers control took three quarters of that,
  and the held-out and *trained* navigation questions score the same
  (callers 0.10 / 0.15): at this step count the weights hold module-grain
  regularities and abstention, not edges. No memorised cell at 7B
  (C-83). Records in `docs/ttt-cells/`; standing per hypothesis in
  `docs/benchmark-hypotheses.md`; C-81–C-85.
- **Max's ten follow-ups ran the same evening** (results §9–§10, the
  second cell record): past one epoch the edges *do* enter the weights
  (callers on trained symbols 0.95 at 3,000 steps) while the NLL gain
  leaves, and a control without the graph reproduces the NLL gain and
  learns nothing navigable; the primary cell (50 derived units, four
  file-tools-only *model + prompt* arms) killed H-TTT-2 and H-TTT-3 at
  300 steps — the manifest finds the files, the adapter alone
  confabulates repo-shaped paths. C-86–C-88; ADR-099 amended.
- **Calvin M0 ran on four keys (2026-09-04 night, Sonnet 5;
  `docs/calvin-potential.md` §10):** T pass 1 / fail 1 / empty 1 /
  no-tests 1 at $6, O pass 1 / no patch 3 at $17; the module anchor is
  the cost door, the template misses importer tests, candidates bind
  but do not find; the 28-key run was cut on cost. The two protocol
  fixes are in and exercised with no model (2026-09-04 later): the
  import grain adds 2,408 guard rows over the 28 golds at `P2F` 0,
  template v1 asks the missed tests once a symbol is confirmed, and
  the import tier's test holes are the next cost door.
- **Then — API spend and Modal compute are off the table for the
  next steps (Max, 2026-09-04):** the no-spend queue in
  `docs/session-handoff.md` — Calvin's model-free follow-through is
  done (ADR-101 waits on *accepted*); **the extraction residue the
  lifts named is closed (2026-09-05):** the TS helper follows the
  C-73 symlink rule, the pyproject reader takes Poetry/PDM/uv/PEP 735
  tables, and a call whose callee is an expression is a counted site
  classed `expr-callee` (C-63 surfaced, ADR-045 amended); W0's two
  build items are done the same day (the venv test's real venv — CI
  deselects nothing; I-7/I-8/I-11 retired, 8 confirmed of 11); next
  the no-spend W1/W3 items and project setup for collaborators
  (`docs/workstreams.md`). Held: the wider Calvin run,
  the 3,000-step adapter under the cell and the 10,000-step point, the
  removal A/B re-run on the 7B, `hobbes narrate` on this repo.

When you finish a session: append to `docs/BUILDLOG.md`, rewrite
`docs/session-handoff.md` if the resume point moved, update this Status
block only if the headline changed, and keep it this length.
