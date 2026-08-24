# Harness restructure — the build plan

> **Status (2026-08-24): complete and superseded.** All five phases were
> built (phases 0–3 on 2026-08-22, phase 4's probe and full-stage run the
> same day); the run's results were then retracted as Hobbes evidence by
> **P12 (ADR-082)**, and the agent architecture moved on to the
> requirement-decomposer frame (**ADR-084/085**, architecture §6.1). This
> file is kept as the record of the restructure's reasoning; the current
> resume point is `docs/session-handoff.md`.

**Written 2026-08-22, accepted by the owner the same day.** Superseded
the "restructure" section of `docs/harness-restructure-handoff.md` (a
per-phase handoff since deleted; its history is in `docs/BUILDLOG.md`).
No time constraint: the aim
is to get the execution shape right before spending more hours of
benchmark compute.

## What the stopped run actually showed

The handoff counted "8/17 units productive". Read against the gold
patches in `verified.jsonl`, *productive* meant "edited something",
never "edited anything relevant":

| instance | gold files | harness patch touched | overlap |
|---|---|---|---|
| astropy-13398 | 4 files, all in `astropy/coordinates/builtin_frames/` | `.:conftest`, `coordinates/transforms.py` (new), `cosmology/io/cosmology.py`, `asdf/…/test_representation.py`, `visualization/interval.py`, `docs/wcs/examples/cube_wcs.py` | 0 |
| astropy-13579 | `astropy/wcs/wcsapi/wrappers/sliced_wcs.py` | (stopped; 2/9 edited, neither sliced_wcs) | 0 |

The cause is upstream of the partition: the **lexical seeds** (C-36).
For 13398 they were `astropy`←"astropy" (the root package node, score
1.0 — the whole repo reachable) plus prose words that happen to be
unique symbol or stem names: `input`, `open`, `check`, `search`,
`output`, `unit`, `frame`, `basic`, `isinstance`, `comments`,
`position`, `transform`, `references`, `Description`. The impact set
became the repo; the unit cap merged it into U1 (17M estimated tokens,
brief cut by 418 KB — the gold files all inside it, the one unit that
edited nothing) plus nine leftover singletons, which are the garbage
seeds themselves and are what "got work done". Integration merged six
wrong branches into one candidate patch.

Two consequences:

1. The handoff's "first cut" selection (skip a unit with no
   seed-reachable interior) would have selected nothing away: every
   unit *was* seed-reachable. Seeding has to be fixed first.
2. The owner's structure (below) is the fix, and C-36 already
   sanctions it: a generative planner "may one day sit *above* the
   lexical seeds; it will never sit inside" (P5). The mail channel
   (ADR-054) is built but was never used with content — every brief
   in the run said "inbox: empty".

## The structure (owner, 2026-08-21)

Single-use **derived-context** agents, one alive at a time. A sandbox
is spawned with a role policy (which includes the full repo policy)
and fed its role's context: its **standing** context (derived) plus
its **short memory** (the job, pushed as mail by the previous agent or
the orchestrator). Agents do not sit in a room looking at each other's
work; one does its job and sends to the next. Some agents' whole job
is to feed the next agent's short memory. Example shape for one task:
a planner that breaks the task down → reviewers of that plan →
implementers → verifiers. Several agents may run simultaneously or be
queued only where the flow makes sense; sequential is the default.

Mapped onto the tree: **planner** (ro worktree; knowledge tools +
`read_file` + `reflect`; handoff = files/symbols to change, approach,
tests to run) → optional **plan reviewers** → `hobbes plan` from the
planner's seeds (deterministic, small units) → **implementers** in
contract order, each starting from the previous one's integrated head
→ **verifier** (ro; runs the guards / the repro via `exec`; handoff =
pass/fail with the failing assertion) → one bounded **rework**
implementer on a fail.

## Errors foreseen (kept as the checklist)

Current structure: seeds are the failure, not the cap; `.:conftest`
leaks a module id as a filename (the model created that file);
integration has no gate; reflection spam (U2 ×123, U3 ×102); the loop
discipline is implementer-shaped (a read-only role would be nudged to
edit, then stalled); every unit clones at base, so a consumer never
sees its owner's commit; `--max-turns 20` with a map-only brief is
tight.

Proposed structure: planner output must be structured and resolvable
with a recorded fallback; the change-spec stops being byte-reproducible
(a register entry); role-aware discipline in `loop.py` and the Go ro
roles; chained worktrees via `--ref` with integrate-after-each-unit;
the verifier on a ro mount in the swebench image (pytest cache,
bytecode); short memory is the handoff, not the transcript; reviewers
cost sessions and a 7B reviewer may add noise (opt-in, measured);
agent count stays the partition's output; H3's cost counter-pressure
rises (every stage's envelope counts); stall cascades must record
which path an instance took; role policies never reach a benchmark
clone (C-42 — the box policy is the floor).

## On testing before building

One narrow probe is worth it; the full set is not. The planner stage
is the one piece whose value is an assumption (can a 7B, given the
knowledge tools, name `sliced_wcs.py` from the issue?). Build it
first, run it **alone** on the two astropy instances, and check the
unit interiors against the gold files. Everything else is built and
exit-checked against the stand-in binaries before another
verdict-bearing run.

## The phases

Each phase is a commit group with tests, the architecture patched in
the same commit (ADR-033), and its concessions registered (P8).

### Phase 0 — correctness fixes that stand regardless of structure  ✅ done (b620422)

- **Module-id → path leak.** The brief renders only paths; an interior
  module with no path is stated as "not a file you can edit". Audit
  contracts and manifests for the same leak.
- **Deterministic seed hygiene** (`derive/impact.py`): a `package`-kind
  seed is dropped when any module-kind seed resolved; a lowercase
  single-word prose term seeds only if the proposal also names it
  code-shaped or it hits a symbol in an already-seeded module; dropped
  seeds are recorded in the spec as `seeds_rejected`. On the 13398
  issue: `astropy`, `input`, `open`, `check`, `isinstance` rejected.
- **Reflections are not a transcript.** `reflect` gains `kind:
  progress | handoff`; fold-back forwards the last handoff (or the last
  reflection when none is marked) with the dropped count stated.
- Exit: suite green; `hobbes plan` re-run on the archived astropy
  workspaces no longer makes U1 the repo.

### Phase 1 — roles first-class across the three layers  ✅ done (73c8f2d)

- Go: `planner` and `reviewer` in `ReadOnlyRoles`; role-policy
  templates for both (deny commit/add; else escalate).
- `loop.py`: `--role` drives the discipline — for read-only roles
  *productive* is a `reflect` (or a call returning new output); the
  nudge says "reflect your plan/verdict now"; stall unchanged.
- Verifier in a ro worktree: `PYTHONDONTWRITEBYTECODE=1`, `-p
  no:cacheprovider` in the brief; an EROFS failure is classified
  `verifier-env`, never "tests failed".
- Exit: Go + pytest green; a dry run with `--role planner` shows the
  ro mount and the read-only tool list.

### Phase 2 — the stage loop (ADR-059)  ✅ done

`run/orchestrate.py` becomes a sequence of stages, one session alive
at a time, each agent's job arriving as its inbox:

1. **Planner** — brief = proposal + repo-level standing context
   (capture line, blind spots, module map) + a required handoff schema
   (`files`, `symbols`, `approach`, `tests_to_run`, `risks`). Entries
   resolve through `resolve_seeds`' tolerant lookup; unresolved ones
   are recorded, never guessed.
2. **Plan** — `derive_plan(seeds=planner_seeds, max_units=ceiling)`;
   `seed_source: planner | lexical-fallback` stamped in the spec with
   the handoff verbatim. Fallback only when the planner resolved
   nothing, and the record says so.
3. **Plan reviewers** (opt-in via `--stages`) — ro sessions with the
   spec in the inbox; handoff = `approve | amend`; one bounded re-plan.
4. **Implementers** — contract order, each cloned at the current
   `hobbes/<task>` head (`--ref`), integrated immediately after
   harvest; inbox = planner handoff + previous handoff + reviewer
   notes. A conflict stays an integration failure at the cut.
5. **Verifier** — ro session at the integrated head; inbox = planner's
   `tests_to_run` + unit handoffs; handoff = `pass | fail` with the
   failing test.
6. **Rework** — on `fail`, one implementer over the named unit(s),
   inbox = the verifier's handoff; verify once more. `--max-rework 1`.

Record: `stages: [...]` per run (session, exit, handoff, tokens);
`seed_source`; the verifier verdict. Defaults `--stages
plan,implement,verify`; `review` and `rework` opt-in so their cost is
measurable. Tests drive every path with the stand-in binary. Docs:
ADR-059; architecture §6.1; `agent-mapping.md` header; C-47 (planner
seeds are a model opinion), C-48 (the verifier cannot write a repro);
C-38/C-45 restated for the inbox-as-handoff.

### Phase 3 — the harness adapter  ✅ done

`bench/arms.py` calls the stage loop; usage sums every stage's
`session.log`; `detail.run` gains `seed_source`, stage wall times, and
a post-hoc `planner_files ∩ gold_files` computed in `results.py` from
the gold patch (never shown to a session). `hobbes bench report` adds a
split by `seed_source` and a planner hit-rate column — the first number
that says whether the unlock worked, independent of the solve.
Built as written (C-49 registers the hit as a one-solution proxy);
building it found and fixed phase 2's integration branch never
advancing (`_integrate_one` ran `branch -f` in the repo, not the
worktree).

### Phase 4 — the probe, then the run  ✅ done 2026-08-22 (probe hit both; full-stage run 0/2, planner 2/2)

Planner-only (`--stages plan`) on 13398 and 13579; unit interiors vs
gold checked by hand and recorded in `benchmark-hypotheses.md`'s
Results, dated. If it hits: full stages on the same two, then the
45-set at `--max-turns 40`, decision at the first 10–20 verdicts as
preregistered. If it misses: iterate on the planner brief only,
re-probe.

### Deliberately not in this plan

Path-grain write enforcement (C-38), metering beyond the envelopes,
loss fitting, the renegotiation re-pin. ~~Parallel implementers~~ —
built 2026-08-22 as ADR-063 once the measurement showed decode at batch
1 was the whole cost (waves over the contract DAG, vLLM-gated).
