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
**in the same commit** as any change that moves it. If it describes something the tree does not do, that is a bug
in the file — fix it and note it in the BUILDLOG.

Locked decisions (not open for relitigation): **D1** Python + Go + TS
split by focus, **D2** Podman rootless for session isolation, **D3**
Cytoscape.js for the interactive graph. **Hobbes stays local** — on the
box, against a repo on disk (architecture §10); the application mode in
`docs/Potential-application-mode.md` is parked, do not design toward it.

## Where to read next (by task)

| You are…                                  | Read                                                                 |
|-------------------------------------------|----------------------------------------------------------------------|
| resuming the active programme             | `docs/session-handoff.md` → `docs/calvin/calvin-harness.md` (ADR-107) |
| working on or through the Calvin harness  | `docs/calvin/calvin-harness.md` (§2 the stack, §4 the validation rule) + the per-session logs in `docs/calvin/sessions/`; the role is `docs/calvin/calvin-charter.md`. The closed keyed rounds are history: `calvin-potential.md` (M0), `calvin-m0-go.md` + `calvin-m0-go-r2.md` (M0-Go), `calvin-m0-gate.md` (M0-Gate), their cells in `docs/calvin/cells/` |
| picking up an item from the backlog       | `docs/workstreams.md` (W0–W5), then the entry it cites               |
| touching extraction or the graph          | architecture §3 + `docs/extraction-evidence.md` + `docs/constraints/README.md` |
| touching sessions, policy or the sandbox  | architecture §6.3 and §7 + ADR-018, ADR-092, ADR-100, ADR-107        |
| grading the graph against an oracle       | `docs/oracle/oracle-grading.md` + ADR-089; misses by class in `docs/oracle/oracle-misses.md`; the oracle's own defects in `docs/oracle/oracle-defects.md` + their review/tally in `docs/oracle/oracle-defect-review.md` |
| touching derivation / agents / the bench  | architecture §6 + `docs/benchmark/agent-mapping.md` + `docs/benchmark/benchmark-hypotheses.md` |
| running the test-time-training experiment | `docs/ttt/olmo3-ttt-validation.md` + ADR-099 (its order of work is step-gated); results in `docs/ttt/olmo3-ttt-results.md` |
| reading or extending Atlas-0 (held)       | `docs/atlas0/atlas-0.md` (the step record at its end has the tables, the atlas entries and the v1 items; the B4 addendum) + `bench/atlas0/README.md` |
| comparing Hobbes with other code-graph tools | `docs/comparative/README.md` (the claim page; ADR-101/102) → `field.md` (one row per tool, sourced or unstated) → the foreign cells in `docs/oracle/cells/`; never a self-reported scoreboard |
| deciding anything                         | `docs/adr/` — one short ADR per decision the architecture doesn't make |
| bringing Hobbes up on a new repo          | `docs/first-run.md`                                                  |
| looking for why something was done        | `docs/BUILDLOG.md` (append-only, one dated entry per session)        |

## Project map

- `go/` — Go module (`github.com/majax7714/Hobbes/go`). `cmd/hobbes-policy`
  + `internal/policy/` (the merge engine: builtin floor → box → repo →
  role → folder → agent; deny overrides allow; allow|deny|escalate). `cmd/hobbes-proxy`
  is the per-session MCP daemon: `internal/proxy/` (policy-checked `exec`
  + read-only knowledge tools, writing through a `Journal`),
  `internal/recorder/` (JSONL flight log), `internal/escalation/`
  (park/approve/expire queue), `internal/knowledge/` (graph tools over
  `.hobbes/derived/`, incl. `list_blind_spots`); `hobbes-proxy sidecar`
  is the session's records container (ADR-112): `internal/sink/` (the
  flight log, the escalation queue and the mail file over one flight
  stream the proxy claims once; `serve --sink`, `record-edit --sink`)
  and `internal/egress/` (the allowlisted route out, a logging CONNECT
  proxy, ADR-107) in one process.
  `cmd/hobbes-session` + `internal/sandbox/` launch a session in rootless
  Podman (`--mount` binds a host tree read-only, ADR-100; every session
  gets its own internal network and a sidecar, its HOME a tmpfs and
  `<id>/in/` its one read-only host dir; `--egress` names the hosts the
  sidecar tunnels to; an explicit `--network` keeps the old file journal
  and says so, C-140; `--claude-bin` + `$CLAUDE_CODE_OAUTH_TOKEN` run
  Claude Code as its doer, ADR-107). `cmd/hobbes-web` + `internal/web/` serve the loopback-only API
  and the embedded SPA. Only external deps: `yaml.v3`,
  `modelcontextprotocol/go-sdk`.
- `pipeline/` — Python package `hobbes` (uv, src layout). `cli.py`;
  `extract/` (discover → per-language syntax providers (`pysource`,
  `tssource`, `gosource`, `rustsource`, `javasource`, `csource`, `cppsource`, the last
  ADR-113) → lane B SCIP join
  → graph/testmap → `packs/` → emit; `containment.py` runs every lane B
  step in the sandbox image — the executing steps refuse without it,
  C-64; Java resolves in a networked pass that holds no sources, then
  indexes offline, C-66/ADR-097); `derive/` (`hobbes plan`: impact →
  cochange → partition → contracts → manifests → changespec; the Calvin
  pieces: `holes.py` + `template.py` (`hobbes template`), `ground.py`
  (`hobbes ground`, grounder v3), `gate.py` (`hobbes gate`, the linker on
  a finished diff; `--map derive` reads the blind-spot map from the
  parent's graph), `adapter.py`, and `harness.py` (`hobbes verify`, the
  local harness, ADR-100)); `run/` (`hobbes run`: agents, orchestrate,
  roles, mail, coverage; **`dispatch.py` — `hobbes dispatch`, the Calvin
  harness, ADR-107**); `agent/loop.py`
  (the owned stdlib tool loop over an OpenAI-compatible endpoint);
  `bench/` (`hobbes bench`: instances → workspace → two arms → one meter →
  evaluator → report); `ttt/` (`hobbes derive-corpus` and the TTT
  instruments, ADR-099); `narrate/`, `invariants/`, `review.py`,
  `render.py`, `graphdiff.py`. Fixture repos under `tests/fixtures/`
  (miniapp / minits / minigo / minirust / minijava / canary-rust /
  canary-java / goshapes / twomod / minic / minicpp), excluded from collection.
- `tsextract/` — Node helper (ts-morph) emitting facts JSON for the join.
- `scip/` — lane B: pinned SCIP indexers (`scip-python`, `scip-typescript`,
  `scip-go` 0.2.7, rust-analyzer's `scip`, `scip-java` 0.13.1 and
  `scip-clang` 0.4.0 in the image), `index.mjs` (the helper owns the SCIP
  decode: scip-java's typed ranges, and C's rules from ADR-109), spike
  evidence.
- `web/` — the surface (Vite + React + TS, Cytoscape.js). `src/lib/` is the
  pure layer with the vitest cases; `npm run build` bundles into the Go
  embed dir — **rebuild `hobbes-web` after**.
- `sandbox/` — the one image (`Containerfile`: sessions *and* lane B ingest,
  ADR-092; JDK 17/21/25 + Maven + scip-java since ADR-096, scip-clang +
  CMake + bear since ADR-109, clang since ADR-110 (the C oracle),
  ~3.3 GB; no
  `claude` — a session mounts the host's) and the exit-check harness.
- `bench/` — experiment tooling, never product: `calvin/` (the M0
  templates and gold fills; the rounds' artifacts under
  `~/.hobbes/bench/calvin*/`), `atlas0/` (its own uv project;
  `atlas0 gen | check | score | probe-check | report`, `atlas0.train` and
  `scripts/modal_atlas0.py`), `oracle/` (the oracle-grading lane,
  ADR-089: one `oracle` binary — `export | go-rta | py-trace | rust-mir |
  java-javac | c-clang | grade | import` — with `ts/`, `py/`, `rust/`,
  `java/`, `internal/clang` (C, ADR-110),
  `adapters/<tool>/` for foreign graphs (ADR-101), `report/render.py`
  regenerating the comparative graphics with a drift test (ADR-102), and
  `shape/`, the callee-shape bucket).
- `docs/` — architecture, ADRs, `constraints/` (the register of what
  Hobbes cannot tell you, one file per segment; `README.md` is the index), `extraction-evidence.md`, `BUILDLOG.md`,
  `session-handoff.md`, `workstreams.md`, `future_additions.md` (parked
  backlog), `calvin/sessions/` (one log per dispatched session).
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
`tsc` (its Go tests run it wherever node is).

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
uv run hobbes dispatch --task-file t.md --secrets "$HOBBES_SECRETS"  # the Calvin harness; the ingest at HEAD first
#   the doer's model: --model, else $HOBBES_DISPATCH_MODEL (this box: claude-opus-5, in .claude/settings.local.json), else Claude Code's own
uv run hobbes bench select|run|report # runs spend GPU/quota — see the standing policy
```

Suite sizes at the last check (2026-09-14, 0.2.19-beta; the last three
carried from 0.2.8-beta): 1,600 pytest (6 of them `lane_b`) / 386 Go
(subtests counted: 385 pass, 1 skip; the four live launcher tests run on
the host) + 100 oracle-lane Go (subtests counted: 95 pass, 5 skip without
a toolchain; re-counted 2026-09-14 after `a848`; two run the `shape/` suites: 24 unittest + 7 node) / 52
vitest / 36 tsextract + 53 scip node tests / 84 atlas0 (`cd bench/atlas0
&& uv run pytest`). Keep
them green. CI (`.github/workflows/ci.yml`, ADR-095) runs them all on
every push; `scripts/ci-graph.sh <base>` is the graph job (image build →
ingest → stamp check → lanes → compiled invariants → review → `lane_b`
pytest) and runs the same way on a box. The Go suite's live tests run a
real session behind the real proxy (egress) and beside a sibling
session's dir (the mount) wherever podman and the image are present;
inside a dispatch they skip, so their first run is the developer's.

## Conventions

- **Milestone order is strict.** Do not start work on stage N+1 while
  stage N's exit criteria are unmet and unreviewed by the project lead.
- Tests accompany the code they test **in the same commit**.
- Conventional commits, scoped: `feat(policy): …`, `fix(cli): …`,
  `test/docs/chore`.
- One short ADR (`docs/adr/NNN-title.md`) for every design decision the
  architecture doesn't already make. Number sequentially (last: 113;
  106 is closed as *not taken*, its page says why).
- **The Hobbes layer is versioned; the experiments are not** (ADR-103).
  Root `VERSION` is the one number (semver, 0.x, `-beta` while early;
  pyproject spells it PEP 440, `0.1.4b0`); `hobbes.__version__`,
  `pyproject`, `go/internal/version`, the three `package.json` are its
  held-together copies (`test_version.py`). A change to what the layer
  draws, refuses or says bumps patch; a capability bumps minor; both in
  the same commit as the change, with a `CHANGELOG.md` entry. Nothing
  under `bench/` or an experiment record moves it. Rebuild the image
  after a bump (C-65). **The number line is Max's (ADR-103, fourth
  amendment, 2026-09-12): the Calvin harness moved the layer to
  0.2.0-beta; patch by patch on 0.2.x. A language addition is a patch,
  even when it reaches "supported"; a structural change bumps minor
  (Max, 2026-09-12); after 0.2.9 the patch counts on to 0.2.10, never
  0.3.0 (Max, 2026-09-13);** tags are his call each time — the latest
  is `v0.2.10-beta` (annotated, 2026-09-13), the one before it
  `v0.1.8-beta`; 0.1.9-beta to 0.2.9-beta are untagged.
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

## Status (2026-09-14) — Hobbes 0.2.19-beta

- **The layer.** v1 (M0–M8) and v2 extraction (V2.M0–M7) are complete
  and reviewed.
  - **Languages:** Python, TypeScript/JavaScript, Go, Rust, Java and C
    (+ Terraform/HCL); **C++ is wired, not supported** (ADR-113: lane A
    and its oracle at 0.2.18-beta, lane B deliberate at 0.2.19-beta; the
    two cells and the §3.8 row remain). Each is a syntax provider plus a pinned batch
    indexer (P13, ADR-105), joined by one range join, with artifacts at
    schema v4. **C** (ADR-108/109: tree-sitter-c, and scip-clang over a
    compile database the ingest derives) is compiler-graded against
    clang's front end since 0.2.5-beta (ADR-110), on cJSON and a random
    draw.
  - **Grading:** every compiler-graded oracle cell is at 100% precision
    but one: quic-go (a 99.6% lower bound; its 15 contradictions are all
    the oracle's grain). The misses are registered by class (ADR-089/090).
    C's sqlite-vector reached 851/851 at 0.2.8-beta through ADR-111's
    external veto, whose gate regraded all 44 cells with a stored key and
    lost no confirmed edge.
  - **Containment:** whatever executes repo code runs in the one image
    (ADR-092).
  - **Register:** 147 entries (104 active, 26 lifted, 11 superseded, 6 folded);
    since 2026-09-14, 81 of the active are surfaced, 19 partial and 3
    unsurfaced; the dispatch harness and C++ have their own segments.
  - **Versioning:** from 0.1.3-beta (ADR-103); the per-version history
    is `CHANGELOG.md`.
- **Active: the Calvin harness** (ADR-107, `docs/calvin/calvin-harness.md`,
  2026-09-12; the 0.2.0-beta minor). Max: O+gate is a harness to stack on this environment;
  verify it by using it through Hobbes development, one log file per
  session. Built:
  - `hobbes-session`: every session on its own internal network beside
    its **sidecar** (ADR-112, 0.2.14-beta), the only writer of its
    records; `--egress` names the hosts the sidecar tunnels to (a logging
    CONNECT proxy to those alone, C-41 narrowed).
  - Claude Code as the session's doer: the host's binary, the owner's
    token passed by name. `--claude-cred` is withdrawn: it never worked
    and would have leaked every host transcript.
  - `hobbes gate --map derive`.
  - `hobbes dispatch`: session → gate → verify → one file in
    `docs/calvin/sessions/`.

  Checked with no spend, by a live route test and by Claude Code through
  the proxy on a bad token (401, no other host).
  - **Since 0.2.6-beta the doer's edits reach the flight log** (the
    progress hook), and dispatch prints the first edit as it lands.
  - **The first real dispatch** (2026-09-12) was the `list_blind_spots`
    `path` alias: gate clear, verify pass; merged as `104c164`
    (0.1.23-beta). A dispatch's turn default is 80.
  - **The latest** (2026-09-14): **C++ at lane B, ADR-113 §2 amended
    (measured on `minicpp` first), 0.2.19-beta,** one unit on Opus 5
    at Max's budget of 150 turns (`be34`, 114 turns, $10.84, gate
    right-clear). One index for C and C++, each root's language read from
    the C++ layer's files; a construction drawn to its constructor, not
    its class; every overload a symbol (`~n`, C-144 lifted). On fmt,
    below-floor moved only 7,628 → 7,357: the bulk is C-145's (6,896 of
    7,376 facts point into files that parsed with errors). Remaining:
    the two cells (fmt, then Taywee/args), the §3.8 row.
  - **Before it** (2026-09-14): **C++ at lane A and its oracle, ADR-113,
    0.2.18-beta,** two units in parallel (`3d56`, 142 turns, $18.67;
    `a848`, 139 turns, $16.08; both gate right-clear).
  - **Before it** (2026-09-14): **the doer's model named per checkout,
    ADR-107 amended, 0.2.17-beta,** one dispatched unit (`cd8e`, 22
    turns, $1.11, gate right-clear, run on `claude-opus-5` said
    explicitly — the first session whose Doer line names its model):
    `hobbes dispatch` reads `$HOBBES_DISPATCH_MODEL` when `--model` is
    not given; this box sets it to `claude-opus-5` in its gitignored
    `.claude/settings.local.json`. The tracker's Doer pattern took the
    named model on the host after the merge.
  - **Before it** (2026-09-14): **`oracle import --lang c`, ADR-101
    amended, no version move** (nothing under `bench/` does), one
    dispatched unit (`d2e3`, 40 turns, $1.04, gate right-clear): C is
    spelled everywhere the converter's language set is, with a
    hand-read C fixture graded against a hand-built key. The
    comparative queue's foreign C cells followed the same day, host-run:
    CodeGraphContext 1,179/1,179 and 851/863, repowise 1,073/1,637 and
    780/879 on the clang keys; every repowise contradiction but two was
    a function-like macro it stores as `function` (C-95's C face).
    Max: "proceed with the recommendation" — converter@3 reads a
    `#define` at the declared line as `macro` (ADR-101 amended; `3c41`,
    45 turns, $1.10, gate right-clear); regraded with signed direction
    lines: repowise 1,073/1,075 and 780/780, CodeGraphContext unmoved.
  - **Before it** (2026-09-14): **C-135's measured gap closed, ADR-109
    amended, 0.2.16-beta,** one dispatched unit (`1ae3`, 17 turns, $0.45,
    gate right-clear): a derived compile database with entries and none
    under the root stops the plan before scip-clang and says where they
    lie (bpftop: 45 dependency compiles under cargo's registry).
  - **Before it** (2026-09-14): **C-133 narrowed, ADR-108 amended,
    0.2.15-beta,** one dispatched unit (`47f7`, 25 turns, $0.79, gate
    right-clear): an include lane A cannot place draws a `c-includes`
    record per directory (6 on cJSON, 1 on sqlite-vector; no edge
    moved). The register's unsurfaced count is 3. The `-I` read from
    the derived database is a second unit, not yet decided.
  - **Before it** (2026-09-14): **C-140's fix, ADR-112, 0.2.14-beta,**
    in two dispatched units (`3ebb`, the sink and the sidecar; `de81`,
    the launcher), both gates right-clear. A session's flight log,
    escalation queue, mail file and egress log are written by
    `hobbes-side-<id>` over one flight stream the proxy claims once; the
    doer's HOME is a tmpfs and `<id>/in/` its one read-only host dir.
    C-140 is narrowed to a forged edit line, surfaced. What verify could
    not see both times was a live test red on the host; the developer
    fixed it after each merge.
  - **The tracker** is the table at the end of
    `docs/calvin/sessions/README.md`, rendered by
    `pipeline/scripts/calvin_tracker.py render` and held by a pytest
    drift test. It reads 27 of the 40 sessions that validate the
    harness (Max, 2026-09-13), with 4 areas, 0 false blocks, 0 missed.
    Re-render it after filling a review block.
  - **Retention** (0.1.22-beta): the doer's reasoning is never stored,
    and recorded sessions are evaluation rows, never training data
    (enforced in `units_from_git`); since 0.2.14-beta it holds by
    construction, the doer's state dying with its container.

  The keyed rounds (M0, M0-Go, M0-Gate; about $27) are closed as an
  approach, and their records are history.
- **Held for Max, or for spend** (`docs/session-handoff.md`):
  - the tracker's area for a test-only session (left for now);
  - the Atlas-0 T items;
  - the TTT adapter points;
  - the 7B removal A/B;
  - DeepSWE's decomposed protocol;
  - `hobbes narrate` on this repo;
  - the comparative queue's next converters;
  - W0's remainder.
- **Spend:** API and Modal spend are off the table unless Max names a
  run and its ceiling. A dispatch spends the owner's Claude Code
  subscription, not API dollars.

When you finish a session: append to `docs/BUILDLOG.md`, rewrite
`docs/session-handoff.md` if the resume point moved, and update this
Status block when the headline changes — keep it short; the history
belongs in the CHANGELOG and the BUILDLOG.
