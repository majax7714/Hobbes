# CLAUDE.md — working notes for coding agents (and humans) on Hobbes

This file is the **entry point**, not the record. `AGENTS.md` is a
byte-for-byte copy of it. Hobbes' own thesis is that an agent works best
under a small, derived context, so this file follows that thesis itself:
**about 200 lines, hard cap 250.** The resume point is
[`docs/session-handoff.md`](docs/session-handoff.md) (about 100 lines, hard
cap 150). Open decisions and work noted but not done are in
[`docs/currently-open.md`](docs/currently-open.md). `test_agent_docs.py`
holds the caps and the copy. Everything else has its own doc and is only
pointed to from here.

## ⚠ FIRST: context hygiene

**1. Ask the graph before you read the tree.** The `mcp__hobbes-knowledge__*`
tools answer from resolved edges with `file:line` provenance, not from text
matches you then have to read and rule out. This repo is the most-tested
target Hobbes has, so trust their answers over a grep sweep.

| You want to know…                                  | Call                 | Not                       |
|----------------------------------------------------|----------------------|---------------------------|
| who calls this function / method                   | `who_calls`          | `grep -rn name`           |
| which tests would break if I change this           | `tests_guarding`     | `grep -rl name tests/`    |
| what a module depends on and what depends on it    | `graph_neighborhood` | reading imports by hand   |
| what this module is for, before opening it         | `get_module_doc`     | `cat` the whole file      |
| what rules bind the code I am about to write       | `list_invariants`    | guessing from style       |
| what the graph *cannot* see where I am editing     | `list_blind_spots`   | assuming silence is empty |

Work in this order: `list_blind_spots` for the directory first, then the
question tools, then `Read` **only the lines the answers point at.** If you
see a stale-artifact warning, run `uv run hobbes ingest`; don't grep around
it. **How they are served:** `.mcp.json` starts `sandbox/knowledge-serve`,
the *image's* `hobbes-proxy serve --knowledge-only`, in a read-only,
offline container over `.hobbes/derived/` (ADR-087, ADR-094). Every answer
opens with the ingest SHA and the Hobbes version that built it. Rebuild
the image after you rebuild the proxy, or the tools answer with the old
build (C-65). Always run `uv run hobbes` from this checkout. Inside a
dispatched session (ADR-107) the same tools are served as
`mcp__hobbes__*`.

**2. Delegate exploring and reading the tools can't cover.** This covers
docs, ADRs, records, configs, logs, string literals, other repos, and
whatever `list_blind_spots` names. **Send a subagent** to do the exploring
or reading, and take back a summary with `file:line` pointers, not the file
dumps. Use `Explore` to locate things, and `general-purpose` to read and
summarize. Tell the subagent to use the knowledge tools too. Parallel
questions go in one message. Read files into your own context directly only
in these cases:
- the file you are about to edit (and only the region you are changing);
- the lines a tool answer or a subagent summary pointed you at;
- this file and the handoff;
- a single known fact at a known path (one `grep -n` or `sed -n` range).

**3. Keep the entry docs small.** When a section here or in the handoff
grows, move it into a specific doc and leave a one-line pointer. Something
noted but not done goes in `currently-open.md`, not here. A procedure goes
in `docs/runbook.md`.

## What this project is

Hobbes: **a multilingual, deterministic code graphing environment.** It
ingests a repo and derives a policy-governed environment where agents do
line-level work and humans review at the concept level. It has three
properties, in order of precedence:
- **Accurate.** A wrong graph is worse than no graph, because it is
  believed.
- **Deterministic.** Parsers and indexers build the skeleton, never a
  model; generative work sits on top of it and is pinned to it.
- **Honest.** Every edge carries a tier, every concession is registered,
  and a provider's limits are owned as ours.

The long-run goal is **single-use agents under derived, systematic
context.**

**Source of truth:** `docs/hobbes-architecture.md` (ADR-033). Read the
section your task touches before you write code. Its §8 header carries the
layer's version. Amend the file **in the same commit** as any change that
moves it. If it describes something the tree does not do, that is a bug in
the file: fix it and note it in the BUILDLOG.

Locked decisions (not open for relitigation): **D1** Python + Go + TS,
split by focus; **D2** Podman rootless for session isolation; **D3**
Cytoscape.js for the interactive graph. **Hobbes stays local**
(architecture §10). The application mode in
`docs/Potential-application-mode.md` is parked; do not design toward it.

## Where to read next (by task)

| You are…                                   | Read                                                                 |
|--------------------------------------------|----------------------------------------------------------------------|
| resuming the active programme              | `docs/session-handoff.md`, then `docs/currently-open.md` as needed   |
| doing a recurring operation (dispatch, regrade, cleanup) | `docs/runbook.md`                                      |
| working on or through Shanks (the harness) | `docs/shanks/README.md` → `shanks-harness.md` (§2 the stack, §4 the validation rule); ADR-107, ADR-152 |
| proposing or reading an experiment         | `docs/experiments/README.md`, then the programme's observed register (`MA-n`, `CV-n`) **before** proposing a run |
| picking up a backlog item                  | `docs/workstreams.md` (W0–W5), then the entry it cites               |
| touching extraction or the graph           | architecture §3 + `docs/extraction-evidence.md` + `docs/constraints/README.md` |
| touching sessions, policy or the sandbox   | architecture §6.3 and §7 + ADR-018, ADR-092, ADR-100, ADR-107        |
| grading against an oracle                  | `docs/oracle/oracle-grading.md` + ADR-089; misses in `oracle-misses.md`; the oracle's defects in `oracle-defects.md` and `oracle-defect-review.md` |
| touching derivation / agents / the bench   | architecture §6 + `docs/experiments/mapped-agents/README.md`          |
| running the TTT experiment                 | `docs/experiments/mapped-agents/ttt/olmo3-ttt-validation.md` + ADR-099 (step-gated) |
| reading or extending Atlas-0 (held)        | `docs/experiments/calvin/atlas0/atlas-0.md` + `bench/atlas0/README.md` |
| comparing Hobbes with other tools          | `docs/comparative/README.md` (ADR-101/102) → `field.md` → `docs/oracle/cells/` |
| deciding anything                          | `docs/adr/`: one short ADR per decision the architecture doesn't make |
| bringing Hobbes up on a new repo           | `docs/first-run.md`                                                  |
| writing a brief, a probe or a pre-registration | `docs/lessons.md`; the scripts behind each decision are in `docs/bench-drivers.md` |
| building, or checking suite sizes          | `docs/build-and-test.md`                                             |
| looking for the tree in detail             | `docs/project-map.md`                                                |
| looking for why something was done         | `docs/BUILDLOG.md` (append-only, one dated entry per session); `CHANGELOG.md` per version |

## Project map (long form: `docs/project-map.md`)

- `go/`: the policy engine, `hobbes-proxy` (the MCP daemon + sidecar),
  `hobbes-session` (rootless Podman), `hobbes-web`.
- `pipeline/`: the Python package `hobbes`: `extract/`, `derive/` (plan,
  gate, verify), `run/dispatch.py` (**Shanks**); fixtures in
  `tests/fixtures/`.
- `tsextract/`, `scip/`: lane helpers. `web/`: the SPA (**rebuild
  `hobbes-web` after `npm run build`**). `sandbox/`: the one image
  (ADR-092).
- `bench/`: experiment tooling, never product; `oracle/` is the grading
  lane. `docs/`: architecture, ADRs, `constraints/`, records. `.hobbes/`:
  dogfooding; never commit `derived/`.

## Build & test (long form, setup and suite sizes: `docs/build-and-test.md`)

You need Go ≥ 1.26, uv, and Node. Run `git config core.hooksPath
.githooks` once, so that the pre-commit hook runs gofmt on staged Go files.

```sh
cd go && go test ./...
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy  # MUST be static; mounted into the sandbox
(cd ../sandbox && podman build -t hobbes-session:local -f Containerfile .)  # lane B + knowledge tools need it
cd bench/oracle && go test ./...
cd web && npm test && npm run build
cd pipeline && uv sync && uv run pytest   # HOBBES_SCIP=0 by default; `lane_b`-marked tests opt in

uv run hobbes up                      # init → ingest → serve → block on decisions
uv run hobbes lanes                   # lane agreement; exit 1 unexplained, 3 all registered
uv run hobbes invariants check|compile
uv run hobbes review main..my-branch  # exit 1 if it needs attention
uv run hobbes plan "proposal" --seed some.module
uv run hobbes dispatch --task-file t.md --secrets "$HOBBES_SECRETS"  # Shanks; ingest at HEAD first; see docs/runbook.md
uv run hobbes bench select|run|report # runs spend GPU/quota (standing policy)
```

Keep every suite green. CI (`.github/workflows/ci.yml`, ADR-095) runs them
all on every push. `scripts/ci-graph.sh <base>` is the graph job.

## Conventions

- **Milestone order is strict.** Don't start stage N+1 while stage N's
  exit criteria are unmet and unreviewed by the project lead.
- Tests go **in the same commit** as the code they test. Use
  conventional, scoped commits: `feat(policy): …`, `fix(cli): …`,
  `test/docs/chore`.
- Write one short ADR (`docs/adr/NNN-title.md`) for every design decision
  the architecture doesn't already make. Number them sequentially (the
  last is 161; 106 is closed as *not taken*).
- **The Hobbes layer is versioned; the experiments are not** (ADR-103).
  Root `VERSION` is the one number, and its copies are held together by
  `test_version.py`. A change to what the layer draws, refuses or says
  bumps the patch, in the same commit, with a `CHANGELOG.md` entry.
  Nothing under `bench/` and no experiment record moves the number. Grep
  the old version across the docs (the architecture's §8 header has no
  test), and rebuild the image after a bump (C-65). **The number line is
  Max's:** patch by patch on 0.2.x, counting on past nine. A language
  addition or a constraint fix is a patch, even when structural; a minor
  is for a feature, and you ask first. Tags are his call every time.
- **Every concession of information gets a `C-n` entry** in its segment
  file under `docs/constraints/`, in the same commit (P8, ADR-030), with a
  *surfacing status*. `unsurfaced` is debt. An inherited provider limit
  adds a `Provider` line (P9).
- **A specific safety guarantee outranks a general safety system** (P10,
  ADR-036). Refusals are distinct types. The guarantee keeps its own test,
  at the level where a user meets it.
- **Coverage claims are scoped to evidence** (P11, ADR-044): "supported"
  reaches exactly as far as architecture §3.8's table. Adding a language
  follows §3.7's four-step checklist.
- **A Hobbes test decomposes, or it is not a Hobbes test** (P12, ADR-082;
  enforced by ADR-086).
- **Extraction weighs honesty and accuracy before recall** (Max). Rules
  fail toward drawing less. A rule that mixes lane B with a syntactic read
  is tiered `syntactic`. Don't fit rules to the held-out cells.
- `docs/BUILDLOG.md` is append-only, with one dated entry per session.
  `docs/session-handoff.md` is rewritten, never piled up.
- Every package and module gets doc comments, and public functions are
  documented. No orphan code, and no speculative abstraction.
- **Recorded sessions are evaluation rows, never model training data**
  (ADR-107). A doer's reasoning and transcript are never stored; only its
  output is. Merge a doer's commit; never squash it.
- **Never read or write `.tfstate` files. Never commit anything under
  `.hobbes/derived/`.** Target repos gitignore `.hobbes/` entirely
  (ADR-012).
- **Commit to `main` unless directed otherwise; say so plainly if you
  worked on another branch. Never `git push`:** the lead publishes after
  review. The repo policy denies `git push*` outright. To test the
  escalation queue, use read-only commands: an approved escalation really
  runs.
- **Spend:** API and Modal spend happen only when Max names a run and its
  ceiling. Experiments are parked. A dispatch spends the owner's Claude
  Code subscription. The full standing policy is in the handoff.

## Status (2026-10-02) — Hobbes 0.2.86-beta

The headline only. The detail is in the handoff, the open items are in
`currently-open.md`, and the history is in `CHANGELOG.md` and the BUILDLOG.

- **The layer:** v1 and v2 extraction are complete. Python, TS/JS, Go,
  Rust, Java, C and C++ (+ Terraform/HCL) are supported; artifacts are at
  schema v4.
- **Active: Shanks, the harness** (ADR-107, ADR-152), the way work is
  done. **Latest:** 0.2.86-beta (ADR-161, C-178 contained). **Next:**
  `cls(…)` in a classmethod, after you pick the next held-out Python repo.
  Calvin is closed; Atlas-0 and TTT are held.

When you finish a session: append to `docs/BUILDLOG.md`, rewrite the
handoff if the resume point moved, update `currently-open.md` (delete what
was decided or done; add what was noted), and **replace** this block's
lines if the headline changed. Stay under the caps. Never add a "before
it" entry: the history belongs in the CHANGELOG and the BUILDLOG. If you rebuilt the image, restart the
knowledge server as the session's last step (C-65).
