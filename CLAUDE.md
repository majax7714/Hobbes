# CLAUDE.md — working notes for coding agents (and humans) on Hobbes

This file is the **entry point**, not the record. It is kept short on
purpose: Hobbes' own thesis is that an agent should work under a small,
derived context, and a 600-line agent file argues against it. History
lives in `CHANGELOG.md` (per version) and `docs/BUILDLOG.md` (per
session); the resume point is `docs/session-handoff.md`. Read those when
you need them, not by default.

## ⚠ FIRST: use the Hobbes knowledge tools, not `cat` / `grep` / `find`

**This repo is ingested and served to you. Ask the graph before you read
the tree.** The `mcp__hobbes-knowledge__*` tools in your session answer
the questions an agent otherwise spends its context window discovering
by hand — and they answer from resolved edges with `file:line`
provenance, not from text matches you then have to read and rule out.
That is the point of the project: **a smaller, truer context costs fewer
tokens and carries fewer wrong beliefs.** This repo is the most-tested
target Hobbes has (every compiler-graded cell at 100%); trust the answer
over a grep sweep.

| You want to know…                                  | Call                         | Not                        |
|----------------------------------------------------|------------------------------|----------------------------|
| who calls this function / method                   | `who_calls`                  | `grep -rn name`            |
| which tests would break if I change this           | `tests_guarding`             | `grep -rl name tests/`     |
| what a module depends on and what depends on it    | `graph_neighborhood`         | reading imports by hand    |
| what this module is for, before opening it         | `get_module_doc`             | `cat` the whole file       |
| what rules bind the code I am about to write       | `list_invariants`            | guessing from style        |
| what the graph *cannot* see where I am editing     | `list_blind_spots`           | assuming silence is empty  |

Order of work: `list_blind_spots` for the directory first, then the
question tools, then `Read` **only the lines the answers point at.**
Fall back to `grep`/`cat` for exactly two things — what `list_blind_spots`
says the graph does not cover there, and non-code text (docs, configs,
string literals). A stale-artifact warning means `uv run hobbes ingest`,
not a grep. Mechanics (the image, staleness, C-65) are under
*Hobbes for Hobbes* below. Inside a dispatched session (`hobbes
dispatch`, ADR-107) the same six tools are served as `mcp__hobbes__*`;
the session's brief names them.

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
architecture (ADR-033). Read it before writing code. Its §8 header
carries the layer's version (Max, 2026-09-14) and the file is amended
**in the same commit** as any change that moves it. If it describes
something the tree does not do, that is a bug in the file — fix it and
note it in the BUILDLOG.

Locked decisions (not open for relitigation): **D1** Python + Go + TS
split by focus, **D2** Podman rootless for session isolation, **D3**
Cytoscape.js for the interactive graph. **Hobbes stays local** — on the
box, against a repo on disk (architecture §10); the application mode in
`docs/Potential-application-mode.md` is parked, do not design toward it.

## Where to read next (by task)

| You are…                                  | Read                                                                 |
|-------------------------------------------|----------------------------------------------------------------------|
| resuming the active programme             | `docs/session-handoff.md` → `docs/shanks/shanks-harness.md` (ADR-107, ADR-152) |
| working on or through Shanks (the harness) | `docs/shanks/` (its `README.md`): `shanks-harness.md` (§2 the stack, §4 the validation rule) + the per-session logs in `sessions/`. Shanks is Calvin's accepted lowest floor, left by the keyed rounds (history in `docs/experiments/calvin/keyed-rounds/`), and **not Calvin's design** (ADR-152) |
| proposing or reading an experiment        | `docs/experiments/README.md` — two programmes, **mapped agents** (smaller tasks, better context, smaller models) and **Calvin** (a model or tool that can program in one language, intentionally not general, not necessarily an LLM; its charter and the design reassessment are in `docs/experiments/calvin/`); **read the programme's observed register (`MA-n`, `CV-n`) before proposing a run** |
| picking up an item from the backlog       | `docs/workstreams.md` (W0–W5), then the entry it cites               |
| touching extraction or the graph          | architecture §3 + `docs/extraction-evidence.md` + `docs/constraints/README.md` |
| touching sessions, policy or the sandbox  | architecture §6.3 and §7 + ADR-018, ADR-092, ADR-100, ADR-107        |
| grading the graph against an oracle       | `docs/oracle/oracle-grading.md` + ADR-089; misses by class in `docs/oracle/oracle-misses.md`; the oracle's own defects in `docs/oracle/oracle-defects.md` + their review/tally in `docs/oracle/oracle-defect-review.md` |
| touching derivation / agents / the bench  | architecture §6 + `docs/experiments/mapped-agents/` (its `README.md`, then `agent-mapping.md` + `benchmark-hypotheses.md`) |
| running the test-time-training experiment | `docs/experiments/mapped-agents/ttt/olmo3-ttt-validation.md` + ADR-099 (its order of work is step-gated); results in `docs/experiments/mapped-agents/ttt/olmo3-ttt-results.md` |
| reading or extending Atlas-0 (held)       | `docs/experiments/calvin/atlas0/atlas-0.md` (the step record at its end has the tables, the atlas entries and the v1 items; the B4 addendum) + `bench/atlas0/README.md` |
| comparing Hobbes with other code-graph tools | `docs/comparative/README.md` (the claim page; ADR-101/102) → `field.md` (one row per tool, sourced or unstated) → the foreign cells in `docs/oracle/cells/`; never a self-reported scoreboard |
| deciding anything                         | `docs/adr/` — one short ADR per decision the architecture doesn't make |
| bringing Hobbes up on a new repo          | `docs/first-run.md`                                                  |
| writing a brief, a probe or a pre-registration | `docs/lessons.md` (the checks earlier sessions paid for); the off-tree scripts behind each decision in `docs/bench-drivers.md` |
| looking for why something was done        | `docs/BUILDLOG.md` (append-only, one dated entry per session)        |

## Project map

- `go/` — Go module (`github.com/majax7714/Hobbes/go`; only external
  deps `yaml.v3` and `modelcontextprotocol/go-sdk`).
  `internal/policy/` is the merge engine behind `hobbes-policy` (builtin
  floor → box → repo → role → folder → agent; deny overrides allow;
  allow|deny|escalate). `hobbes-proxy` is the per-session MCP daemon
  (`internal/proxy/`, `knowledge/`, `recorder/`, `escalation/`: the
  policy-checked `exec`, the read-only knowledge tools, the JSONL flight
  log, the escalation queue); `hobbes-proxy sidecar` is the session's
  records container (ADR-112: `internal/sink/`, and `internal/egress/`,
  the allowlisted logging CONNECT proxy). `hobbes-session` +
  `internal/sandbox/` run a session in rootless Podman on its own
  network beside its sidecar (`--mount`, ADR-100; `--egress`;
  `--claude-bin` + `$CLAUDE_CODE_OAUTH_TOKEN` for the Claude Code doer,
  ADR-107; an explicit `--network` keeps the old file journal, C-140).
  `hobbes-web` + `internal/web/`: the loopback-only API and the SPA.
- `pipeline/` — Python package `hobbes` (uv, src layout; `cli.py`).
  `extract/`: discover → syntax providers (`pysource`, `tssource`,
  `gosource`, `rustsource`, `javasource`, `csource`, `cppsource`) → lane
  B SCIP join → graph/testmap → `packs/` → emit; `containment.py` runs
  every lane B step in the image and refuses without it (C-64, C-66).
  `derive/`: `hobbes plan` (impact → … → changespec) and the keyed
  rounds' pieces, which Shanks runs on (`template.py`, `ground.py`, `gate.py` — `hobbes gate`, with
  `--map derive` — `adapter.py`, `harness.py` — `hobbes verify`).
  `run/`: `hobbes run`, and **`dispatch.py` — `hobbes dispatch`,
  Shanks, the harness (ADR-107, ADR-152)**. Also `agent/loop.py`, `bench/`, `ttt/`,
  `narrate/`, `invariants/`, `review.py`, `render.py`, `graphdiff.py`.
  Fixture repos
  under `tests/fixtures/` (miniapp / minits / minigo / minirust /
  minijava / canary-rust / canary-java / goshapes / twomod / minic /
  minicpp / minifixval / minideco / mininest), excluded from collection.
- `tsextract/` — Node helper (ts-morph) emitting facts JSON for the join.
- `scip/` — lane B's helper, `index.mjs` (it owns the SCIP decode:
  scip-java's typed ranges, C's rules from ADR-109), and spike evidence;
  the pinned indexers themselves are in the image.
- `web/` — the surface (Vite + React + TS, Cytoscape.js). `src/lib/` is
  the pure layer with the vitest cases; `npm run build` bundles into the
  Go embed dir — **rebuild `hobbes-web` after**.
- `sandbox/` — the one image (`Containerfile`, ~3.3 GB: sessions *and*
  lane B ingest, ADR-092; JDK 17/21/25 + Maven + scip-java, scip-clang +
  CMake + bear, and clang for the C and C++ oracle; no `claude` — a
  session mounts the host's) and the exit-check harness.
- `bench/` — experiment tooling, never product (`bench/README.md` maps
  each directory to its programme): `calvin/` (the lattice package, the
  E3 draw, the M0 templates and gold fills), `atlas0/` (its own uv project, with
  `bench/atlas0/scripts/modal_atlas0.py`), `oracle/` (ADR-089: one
  `oracle` binary — `export | go-rta | py-trace | rust-mir | java-javac
  | c-clang | grade | import`, `c-clang` serving C and C++ — with
  `adapters/<tool>/` for foreign graphs (ADR-101) and `report/render.py`
  with its drift test (ADR-102)).
- `docs/` — architecture, ADRs, `constraints/` (the register of what
  Hobbes cannot tell you, one file per segment; `README.md` is the
  index), `extraction-evidence.md`, `BUILDLOG.md`, `session-handoff.md`,
  `workstreams.md`, `future_additions.md` (parked backlog), `lessons.md`,
  `bench-drivers.md` (the `~/.hobbes/bench/` index),
  `shanks/` (the harness, `sessions/` — one log per dispatched
  session), `experiments/` (the two programmes: `mapped-agents/` — the
  benchmark, agent mapping, TTT — and `calvin/` — the charter, the
  reassessment, the lattice, Atlas-0, the keyed rounds).
- `.hobbes/` — dogfooding: `policies/` + `invariants/` versioned;
  `derived/` and `plans/` gitignored.

## Hobbes for Hobbes — how the knowledge tools are served

The directive at the top says *when* to use the six tools; this is
*how they get to you*. This repo's `.mcp.json` starts
`sandbox/knowledge-serve` — the **image's** `hobbes-proxy serve
--knowledge-only` in a read-only, offline container (ADR-087, ADR-094),
six read-only tools over `.hobbes/derived/` and nothing else. Every
answer opens with the ingest SHA and which Hobbes version built the
artifact; on a stale warning, `uv run hobbes ingest`. Needs the sandbox
image built (below) and the repo ingested; rebuild the image after
rebuilding the proxy, or the tools answer with the old build (C-65).
Always `uv run hobbes` from this checkout — a `hobbes` on PATH may be
another tree's (the 2026-08-28 incident, ADR-094).

## Build & test

Go ≥ 1.26, uv, Node. If a distro Go is older, a user-local Go must come
first on `PATH` or `go build` fails on the toolchain line. One-time:
`cd tsextract && npm install`, `cd web && npm install`, `cd scip && npm
install`, and `cd bench/oracle/ts && npm install` for the oracle lane's
`tsc` (its Go tests run it wherever node is). And `git config
core.hooksPath .githooks`: the pre-commit hook is CI's gofmt step on the
staged Go files, because a red gofmt step hides both Go suites behind it.

```sh
# Go
cd go && go test ./...
go build -o bin/hobbes-policy  ./cmd/hobbes-policy
go build -o bin/hobbes-session ./cmd/hobbes-session
go build -o bin/hobbes-web     ./cmd/hobbes-web      # after `cd web && npm run build`
CGO_ENABLED=0 go build -o bin/hobbes-proxy ./cmd/hobbes-proxy   # MUST be static:
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy  # it is mounted into the sandbox
(cd ../sandbox && podman build -t hobbes-session:local -f Containerfile .)  # lane B and the knowledge tools need it (ADR-092/094)

# Oracle lane, web, Python
cd bench/oracle && go test ./...          # fixture self-test: Python via uv, Rust via the nightly driver
cd web && npm test && npm run build
cd pipeline && uv sync && uv run pytest   # HOBBES_SCIP=0 by default; `lane_b`-marked tests opt in

# Everyday commands
uv run hobbes up                      # init → ingest → serve → block on decisions
uv run hobbes lanes                   # lane agreement; exit 1 on an unexplained disagreement, 3 when every row is a registered shape
uv run hobbes invariants check|compile
uv run hobbes review main..my-branch  # exit 1 if it needs attention
uv run hobbes plan "proposal" --seed some.module
uv run hobbes run <task> --dry-run
uv run hobbes dispatch --task-file t.md --secrets "$HOBBES_SECRETS"  # Shanks, the harness; the ingest at HEAD first
#   the doer's model: --model, else $HOBBES_DISPATCH_MODEL (this box: claude-opus-5-5, in .claude/settings.local.json), else Claude Code's own
uv run hobbes bench select|run|report # runs spend GPU/quota — see the standing policy
```

Suite sizes at the last check (2026-10-01; pytest, Go, tsextract and
vitest re-run on the host at 0.2.83-beta, the rest at 0.2.74-beta): 2,605 pytest
(21 `lane_b`, run with the image built at 0.2.83-beta) / 402 Go with
subtests (402 pass) + 131
oracle-lane Go with subtests (119 pass, 12 skip on a host without
clang++ or cmake; the C++ ones pass in the image) / 52 vitest / 49
tsextract + 97 scip node / 84 atlas0 / 656 lattice (624 pass, 32 skip
on a host without clang; they run in the image). Keep them green. CI
(`.github/workflows/ci.yml`, ADR-095) runs them all on every push;
`scripts/ci-graph.sh <base>` is the graph job (image build → ingest →
stamp check → lanes → compiled invariants → review → `lane_b` pytest),
the same on a box. The Go suite's live tests run wherever podman and
the image are present; inside a dispatch they skip, so their first run
is the developer's.

## Conventions

- **Milestone order is strict.** Do not start work on stage N+1 while
  stage N's exit criteria are unmet and unreviewed by the project lead.
- Tests accompany the code they test **in the same commit**.
  Conventional commits, scoped: `feat(policy): …`, `fix(cli): …`,
  `test/docs/chore`.
- One short ADR (`docs/adr/NNN-title.md`) for every design decision the
  architecture doesn't already make. Number sequentially (last: 161;
  106 is closed as *not taken*, its page says why).
- **The Hobbes layer is versioned; the experiments are not** (ADR-103).
  Root `VERSION` is the one number (semver, 0.x, `-beta` while early;
  pyproject spells it PEP 440, `0.1.4b0`); `hobbes.__version__`,
  `pyproject`, `go/internal/version` and the three `package.json` are
  its held-together copies (`test_version.py`). A change to what the
  layer draws, refuses or says bumps patch, in the same commit, with a
  `CHANGELOG.md` entry; nothing under `bench/` or an experiment record
  moves it. Rebuild the image after a bump (C-65). **The number line is
  Max's** (ADR-103's fourth amendment): patch by patch on 0.2.x,
  counting on past nine (0.2.10, never 0.3.0). A language addition is a
  patch even when it reaches "supported", and so is a constraint's fix
  even when structural; a structural change bumps minor, and you ask
  first. Tags are his call each time: the latest is `v0.2.10-beta`
  (2026-09-13), the one before it `v0.1.8-beta`.
- **Every concession of information gets a `C-n` entry in its segment
  file under `docs/constraints/` (index: `README.md`), in the same
  commit** (P8, ADR-030), with a *surfacing status* naming where a user
  meets the limit. `unsurfaced` is debt. Inherited provider limits add
  a `Provider` line (P9).
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
- **Recorded sessions are evaluation rows, never model training data**
  (ADR-107's retention amendment). A dispatched doer's reasoning and
  transcript are never stored; only its output is. Merge a doer's commit,
  never squash it: its authorship keeps it out of `units_from_git`.
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

## Status (2026-10-02) — Hobbes 0.2.86-beta

The headline only. The history is `CHANGELOG.md` and `docs/BUILDLOG.md`;
the resume point, with everything held, is `docs/session-handoff.md`.

- **The layer:** v1 (M0–M8) and v2 extraction (V2.M0–M7) complete and
  reviewed. Python, TS/JS, Go, Rust, Java, C and C++ (+ Terraform/HCL;
  JavaScript graded on five repos of its own, two with their
  dependencies installed — C-165),
  each a syntax provider plus a pinned batch indexer (P13, ADR-105)
  joined by one range join; artifacts at schema v4. Whatever executes
  repo code runs in the one image (ADR-092).
- **Max's direction (2026-09-17):** on the extraction lane, **honesty and
  accuracy come before a recall number** — weigh every extraction
  decision against them first.
- **Grading:** every compiler-graded cell at 100% precision but quic-go
  (99.6%, all 15 the oracle's grain). fmt reads **100%** (7,026/7,026
  at 0.2.81-beta), **strict 99.62%** — every quoted precision carries
  its strict companion, the rows the key declined to judge counted as
  contradicted (ADR-124). Trace-graded Python cells are recall, never
  precision (C-60); flask's key found 3 Hobbes-wrong `semantic` edges
  and click's 1 more, all scip-python's one moniker for a method's
  same-named nested defs, refused since 0.2.70-beta (ADR-150, C-170).
  **Held out** (Max, 2026-10-01, against fitting to the keys): rich,
  graded once with no rule changed (§10.40), then fitted by ADR-160; its
  place taken by **pyparsing** 3.3.3 (2026-10-02, §10.44): 3,516
  confirmed, 0 Hobbes-wrong calls, recall 50.6%.
  **Register:** 178 entries; 130 active (101 surfaced, 25 partial, 3
  unsurfaced, 1 n/a), 31 lifted; the tally is
  held by `test_register_tally.py`, its dated notes are
  `docs/constraints/HISTORY.md`.
- **Active — Shanks, the harness** (ADR-107; named by ADR-152): `hobbes
  dispatch` runs the host's Claude Code in `hobbes-session` → gate →
  verify → one log in `docs/shanks/sessions/`. The tracker at the end of
  that directory's `README.md` (`pipeline/scripts/shanks_tracker.py
  render`, held by a drift test; re-render after filling a review block)
  reads **98 of 40** sessions that validate the harness: 4 areas, 4 false
  blocks, all closed (`f3c1` at 0.2.28-beta; `9326`, `c141` and `66c5`,
  the decorator case, at 0.2.76-beta), 0 missed. It stays the way work is done.
  Shanks is Calvin's accepted lowest floor from the keyed rounds, and it
  treats a symptom; it is not Calvin's design.
- **Latest — 0.2.86-beta, ADR-161, C-178 contained** (unit `aa88`;
  precedent 1, investigated first): scip-python answers the first
  `pkg.Name` it resolves through a `from … import *` re-export for every
  later one; such a reference (token not its name, through an imported
  module) is refused and counted. pyparsing 2,919 refused, wrong `uses`
  rows to `CaselessLiteral` 1,671 → 10, no `calls` row moved; rich,
  flask, click identical.
- **The honesty audit** (0.2.80-beta, precedent 1): C-174 widened, and
  C-175 to C-177 registered and surfaced, after one fixture per language
  (`~/.hobbes/bench/honesty-audit/RESULTS.md`). All three fixes are in:
  C-175 lifted (0.2.81-beta, ADR-157), C-176 narrowed to the symbol floor
  (0.2.82-beta, ADR-158), C-177 lifted (0.2.83-beta).
- **Extraction** stays the standing default (Max, 2026-09-20: "we never
  sacrifice honesty for higher recall").
  **Next — `cls(…)` in a classmethod** (rich 57, pyparsing 17): measuring
  it on pyparsing would fit the held-out cell, so pick the next held-out
  repo first.
- **Calvin** (`docs/experiments/calvin/`): a model or tool that can
  program in one language, intentionally not general, and not
  necessarily an LLM (ADR-152). **Closed on its lattice** (Max,
  2026-09-29: "close out here and return to extraction"). The lattice
  programme (ADR-151, about $21.50) tested a stock coder steered by
  context and one LoRA. The zero-spend reassessment
  (`calvin-reassessment.md` §9–§13) then found sqlite-vector's whole
  residual deterministic: 16 of 21 families from the compiler; the 5
  guarded ones from a tree-sitter lifter plus the compiler (609/609
  rows); the helpers from Z3 and a SIMDe lookup. Calvin reopens only on
  a target where the job is not derivable.
- **Comparative** (ADR-101): CodeGraphContext and repowise are graded on
  the five JavaScript keys too (2026-09-26); repowise's converter@5
  fixed a `__module__` drop that had cost every repowise cell its
  top-level calls, and the 22 published cells were regraded.
- **The graph job is red** since 2026-09-26 (it reviews from the last
  green run, `57e4be2`, ADR-114): 22 → 5 unguarded new modules on
  2026-10-02. Left for Max: `lattice` and `dedupe` (value-only, C-156)
  and the untested bench scripts `draw`, `make_fixture`, `modal_e1`.
  I-4 also fails, not as a regression: its roster lacks `csource` and
  `cppsource`.
- **Open for Max:** ADR-126 §3 — whether to build a "may reach through dispatch (not
  traced)" section on §10.12's numbers (it needs a syntax
  exclusion for non-dispatched calls); C-150's remainder (parked, Max:
  "fine for now"); the G-diff coverage finding (the lattice
  driver never puts inf/NaN in `b` alone, so one-sided masks pass;
  proposed, not registered).
- **Spend:** API and Modal spend only when Max names a run and its
  ceiling; a dispatch spends the owner's Claude Code subscription.

When you finish a session: append to `docs/BUILDLOG.md`, rewrite
`docs/session-handoff.md` if the resume point moved, and **replace**
this block's lines when the headline changes. If the image was rebuilt,
restart the knowledge server as the session's last step (C-65) and do
not write "restart it" into the handoff: a new session starts its own
server from the current image, so the line is stale when it is read.
Never add a "before it" entry: the history belongs in the CHANGELOG and
the BUILDLOG.
