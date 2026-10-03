# CLAUDE.md — the rules for working on Hobbes

This is the always-loaded entry point. `AGENTS.md` is a byte-for-byte copy
of it. It holds rules and pointers, not state or history. **Next, read
[`docs/session-handoff.md`](docs/session-handoff.md)**, the resume point.
Everything open but not done is in
[`docs/currently-open.md`](docs/currently-open.md); read the section your
work touches. Caps: this file is about 200 lines (hard cap 250), and the
handoff is about 100 (hard cap 150). `test_agent_docs.py` holds the caps.
The reasons and sources for the working rules are in ADR-162.

## 1. Honesty and accuracy come before recall

This is the project's first rule. It outranks a recall number, a deadline
and a green suite. Hobbes' graph is *believed* by the agents and people who
use it, so a wrong answer does more harm than a missing one. Max: "we never
sacrifice honesty for higher recall" (2026-09-20).

- **When unsure, draw less.** A rule fails toward drawing nothing, never
  toward a plausible guess. A refused or counted row is better than a
  wrong edge.
- **Tier by what proves the edge.** `semantic` only when it is clearly
  semantic. A rule that mixes lane B with a syntactic read is `syntactic`
  (Max, 2026-10-02).
- **Every concession is registered.** Each gets a `C-n` in its segment file
  under `docs/constraints/`, in the same commit, with the place a user
  meets the limit (P8, ADR-030). Inherited provider limits add a
  `Provider` line (P9). `unsurfaced` is debt. **A limit the tools don't
  name is a defect, and it outranks recall work** (precedent 1). A gap that
  has been flagged gets fixed: contain it first, prevent it second, then
  register the residual.
- **Claims are scoped to evidence.** "Supported" reaches exactly as far as
  architecture §3.8's table (P11, ADR-044). Every precision figure carries
  its strict companion (ADR-124). Trace-graded cells measure recall, never
  precision (C-60).
- **Don't fit to the keys.** Held-out cells stay held out: pick a new one
  before you measure a rule. Grade the nodes a rule adds, not only its
  edges. Read what the key can't judge before shipping (Max, 2026-10-01).
- **Report the way the graph draws.** Say what you verified and how. Give
  test results with their output. Say plainly when a step was skipped or a
  test failed. Never round a partial result up to "done".

## 2. How to work: context is the budget

Hobbes' thesis is that an agent works best under a small, derived context.
Work the same way here.

**Ask the graph before you read the tree.** The `mcp__hobbes-knowledge__*`
tools answer from resolved edges with `file:line` provenance. This repo is
the most-tested target Hobbes has, so trust them over a grep sweep.

| You want to know…                                | Call                 | Not                       |
|--------------------------------------------------|----------------------|---------------------------|
| who calls this function / method                 | `who_calls`          | `grep -rn name`           |
| which tests would break if I change this         | `tests_guarding`     | `grep -rl name tests/`    |
| what a module depends on, and what depends on it | `graph_neighborhood` | reading imports by hand   |
| what this module is for                          | `get_module_doc`     | `cat` the whole file      |
| what rules bind the code I am about to write     | `list_invariants`    | guessing from style       |
| what the graph *cannot* see where I am editing   | `list_blind_spots`   | assuming silence is empty |

Start with `list_blind_spots` for the directory, then ask the questions,
then read **only the lines the answers point at.** If you get a
stale-artifact warning, run `uv run hobbes ingest`. The tools are served
from the image (`sandbox/knowledge-serve`, ADR-087/094), so rebuild the
image after you rebuild the proxy (C-65). Inside a dispatch they are
`mcp__hobbes__*`.

**Delegate the reading the tools can't cover:** docs, ADRs, records,
configs, logs, web pages, other repos, and blind spots. Send a subagent and
take back a summary with `file:line` pointers. Before acting on a claim
in it, check the lines it cites: a summary is model output. Use `Explore`
to locate things, and `general-purpose` to read, compare or audit. Ask independent
questions in parallel. Read into your own context only:
- the region of a file you are about to edit;
- the lines a tool answer or a summary pointed you at;
- this file and the handoff;
- one known fact at a known path (a `grep -n` or a `sed -n` range).

**Docs are references, read by section.** The architecture is over 2,000
lines; read the section your task touches. The BUILDLOG and CHANGELOG are
ledgers: search them for the entry you need, and never read them whole.

**Decide before you build.** For anything that makes a design decision,
write the ADR (or the amendment) first. Measure before you build a rule. A
brief carries its premises checked against the code, and a real-source
case (`docs/lessons.md`).

**Verify before you claim.** Run the tests `tests_guarding` names, plus
the suites the change touches. For extraction, also run the real cell. The
live and `lane_b` tests skip in the sandbox, so run them on the host.

**Close every piece of work the same way.** When a unit of work is done:
1. update every doc the work moved, each in its home (§5);
2. append to the BUILDLOG;
3. commit.

Commit small and often, but commit whole. Each commit is the smallest
*complete* unit: green, with its tests, its `C-n`, its architecture
amendment and its version bump if it has them. A change to what the
layer draws keeps its bump in the same commit; docs and tests never bump.
Don't wait for "the end of the session", and don't leave a change
uncommitted. What a particular operation needs on top of that (an image
rebuild, a tracker re-render, a knowledge-server restart) is in
`docs/runbook.md`.

**Ask Max** before a design decision the docs don't make, any spend, a
minor version, or a tag. Present the decision as concrete routes, with the
recommended one first.

## 3. What Hobbes is

Hobbes is **a multilingual, deterministic code graphing environment.** It
ingests a repo and derives a policy-governed environment where agents do
line-level work and humans review at the concept level. Its properties, in
order of precedence:
- **accurate**;
- **deterministic**: parsers and indexers build the skeleton, never a
  model;
- **honest**: every edge has a tier, and every concession is registered.

The goal is **single-use agents under derived, systematic context.**

The source of truth is `docs/hobbes-architecture.md` (ADR-033). Amend it
**in the same commit** as any change that moves it. If it describes
something the tree doesn't do, the file has a bug: fix it.

Locked decisions (not open for relitigation): **D1** Python + Go + TS,
split by focus; **D2** Podman rootless for session isolation; **D3**
Cytoscape.js. **Hobbes stays local** (§10); the application mode is parked.

**The tree** (long form: `docs/project-map.md`): `go/` (policy, proxy,
sessions, web), `pipeline/` (the `hobbes` package; `run/dispatch.py` is
Shanks, the harness), `tsextract/` and `scip/` (lane helpers), `web/` (the
SPA; rebuild `hobbes-web` after `npm run build`), `sandbox/` (the one
image), `bench/` (experiment tooling, never product).

## 4. Where to read (by task)

| You are…                                   | Read                                                                 |
|--------------------------------------------|----------------------------------------------------------------------|
| resuming work                              | `docs/session-handoff.md`, then `docs/currently-open.md` as needed   |
| running a dispatch, a regrade or a cleanup | `docs/runbook.md`                                                    |
| working on or through Shanks               | `docs/shanks/README.md` → `shanks-harness.md` (§2 stack, §4 validation); ADR-107, ADR-152 |
| touching extraction or the graph           | architecture §3 + `docs/extraction-evidence.md` + `docs/constraints/README.md` |
| touching sessions, policy or the sandbox   | architecture §6.3, §7 + ADR-018, ADR-092, ADR-100, ADR-107           |
| grading against an oracle                  | `docs/oracle/oracle-grading.md` + ADR-089; `oracle-misses.md`, `oracle-defects.md` |
| writing a brief, a probe or a pre-registration | `docs/lessons.md`; drivers in `docs/bench-drivers.md`            |
| proposing an experiment                    | `docs/experiments/README.md`, then its register (`MA-n`, `CV-n`) **before** proposing |
| derivation, agents, the bench, TTT         | architecture §6 + `docs/experiments/mapped-agents/README.md`          |
| Atlas-0 (held)                             | `docs/experiments/calvin/atlas0/atlas-0.md` + `bench/atlas0/README.md` |
| comparing with other tools                 | `docs/comparative/README.md` (ADR-101/102) → `field.md`              |
| bringing Hobbes up on a new repo           | `docs/first-run.md`                                                  |
| picking up a backlog item                  | `docs/workstreams.md` (W0–W5)                                        |
| building, or checking suite sizes          | `docs/build-and-test.md`                                             |

## 5. Where things are recorded

Each kind of fact has one home. Write it there, and point to it from
everywhere else.

| What                                       | Home                                                  |
|--------------------------------------------|-------------------------------------------------------|
| what a session did and found               | `docs/BUILDLOG.md`: append-only, dated, never edited  |
| what shipped in a version                  | `CHANGELOG.md`                                        |
| the resume point                           | `docs/session-handoff.md`: rewritten, never appended  |
| a decision or work noted but not done      | `docs/currently-open.md`: deleted when done           |
| a decision made                            | `docs/adr/NNN-title.md` (the last is 162; 106 is *not taken*) |
| a concession of information                | `docs/constraints/<segment>.md` (`C-n`)               |
| how the design works                       | `docs/hobbes-architecture.md`                         |
| a procedure                                | `docs/runbook.md`                                     |
| a check a session paid for                 | `docs/lessons.md`                                     |
| a measurement script's path                | `docs/bench-drivers.md`                               |
| suite sizes, setup                         | `docs/build-and-test.md`                              |
| a dispatched session                       | `docs/shanks/sessions/` + the tracker                 |

## 6. Build & test (long form: `docs/build-and-test.md`)

```sh
cd go && go test ./...
CGO_ENABLED=0 go build -o ../sandbox/hobbes-proxy ./cmd/hobbes-proxy  # MUST be static
(cd ../sandbox && podman build -t hobbes-session:local -f Containerfile .)  # lane B + knowledge tools
cd bench/oracle && go test ./...
cd web && npm test && npm run build
cd pipeline && uv sync && uv run pytest   # HOBBES_SCIP=0 by default; `lane_b` tests opt in

uv run hobbes ingest | lanes | invariants check | review main..branch | plan "…" --seed mod
uv run hobbes dispatch --task-file t.md --secrets "$HOBBES_SECRETS"   # see docs/runbook.md
```

Always run `uv run hobbes` from this checkout (ADR-094). Keep every suite
green; CI runs them all (ADR-095).

## 7. Conventions

- **Tests go in the same commit** as the code they test. Use
  conventional, scoped commits (`feat(policy): …`, `fix(cli): …`,
  `docs: …`).
- **Versioning (ADR-103):** a change to what the layer draws, refuses or
  says bumps the patch, in the same commit, with a CHANGELOG entry and
  `VERSION`'s copies (`test_version.py`). Grep the old version across the
  docs, and rebuild the image. A language addition or a constraint fix is
  a patch, even when structural. A minor is for a feature, and you ask
  first. `bench/` and experiment records never move the number.
- **A specific safety guarantee outranks a general safety system** (P10,
  ADR-036). Refusals are distinct types, and the guarantee keeps its own
  test.
- **A Hobbes test decomposes, or it is not a Hobbes test** (P12, ADR-082).
- **Milestone order is strict.** Don't start stage N+1 before stage N's
  exit is reviewed.
- **Every module gets a doc comment.** No orphan code, and no speculative
  abstraction.
- **Recorded sessions are evaluation rows, never training data**
  (ADR-107). A doer's transcript is never stored. Merge a doer's commit;
  never squash it.
- **Never read or write `.tfstate`. Never commit `.hobbes/derived/`.**
  Target repos gitignore `.hobbes/` (ADR-012).
- **Commit to `main`** unless directed otherwise, and say so plainly if
  you worked on another branch. **Never `git push`;** Max publishes. Test
  the escalation queue only with read-only commands: an approved
  escalation really runs.
- **Spend:** API and Modal spend only when Max names a run and its
  ceiling. Experiments are parked. The full policy is in the handoff.
