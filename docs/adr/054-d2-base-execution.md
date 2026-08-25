# ADR-054 — D2 base: executing a change-spec (layered agent policy, two context horizons, the partition record)

**Date:** 2026-08-21
**Status:** accepted — a **rough base**, built to be run under the
benchmark harness and corrected from its error stream (ADR-052)
**Amends:** `docs/hobbes-architecture.md` (§6 gains the execution half;
§8's D-table); `docs/agent-mapping.md` (status header);
`docs/constraints/README.md` (C-38); `docs/future_additions.md` (the D2 entry
shrinks to what remains)

## Context

D1 passed the owner's review on 2026-08-21, and the direction for what
follows was set in the same message: the benchmarks run Hobbes alone,
so the manual plan-review step shifts off for now and **proposals are
what gets set**; the agent count stays the partition's output (D1), and
the owner structures how each agent is *formed*:

1. a **per-agent policy**, made of the shared repo policy plus
   per-role policies;
2. a **standing** derived context and a **short-term** context, the
   latter read as role-pushed mail — when the orchestrator needs a
   specific it posts to that agent's short-term context and reads the
   reflection back;
3. **commits** are what alter standing context and repo/role policies;
4. the rest of the D1 mapping stays; the formula learns from errors,
   and the benchmark failures are where the adjustment signal comes
   from.

The goal named: a rough base of the current architecture, so the first
twenty-odd problems can surface under testing.

## Decision

### 1. Policy is a chain with two new levels

The Go engine's chain becomes **floor → box → repo → role → folder →
agent**. The **role** layer is `.hobbes/policies/roles/<role>.policy`
(`scope: role`), loaded when present for the session's role — standing,
versioned with the repo, changed only by commits. The **agent** layer is
the derived per-unit policy written from the change-spec's policy
manifest (`<agent-dir>/policy.yaml`, `scope: agent`), loaded last and
most specific. ADR-002's deny-overrides-allow is unchanged, so a derived
layer **narrows and never widens** past a repo or role deny — the P10
guarantees are restated in it as denies anyway, first. `hobbes run`
scaffolds the three role policies (`implementer`, `verifier`,
`orchestrator`) when absent and never overwrites one.

### 2. Two context horizons, and the agent dir

Each unit gets a directory under `.hobbes/plans/<task>/agents/<unit>/`,
mounted **read-only at `/agent`** in its sandbox:

- `policy.yaml` — the agent layer (above);
- `context.json` — the manifest the proxy tags **context faults**
  against: interior, boundary, neighborhood ids and interior paths. A
  knowledge query outside them is **served and tagged**
  (`context_fault: true` in the flight log) — agent-mapping §4's error
  signal, never a refusal;
- `context.md` — the **standing** context rendered from the manifest,
  complement first-class; `derived/` stays mounted ro beside it;
- `inbox.jsonl` — the **short-term** context: messages the orchestrator
  (or a human, `hobbes mail post`) pushes; the brief carries the inbox
  in full at spawn time;
- `brief.md` — the session's prompt: role, proposal, obligations, inbox,
  standing context.

The agent answers through a new proxy tool, **`reflect`**: one line into
`<session>/mail.jsonl`, recorded as a flight event. After the session
the orchestrator folds reflections into its own inbox
(`agents/orchestrator/inbox.jsonl`). A blocked contract is a reflection,
not a workaround. Nothing is a transcript; every message has a sender
and a sequence number.

### 3. Commits alter standing context

`hobbes-session` now **harvests** the session branch
(`hobbes/<session>`) back into the repo before removing the clone;
before this, a session's commits died with its worktree. `hobbes run`
integrates the unit branches onto `hobbes/<task>` in contract order in a
detached temporary worktree (the human's checkout is never touched), a
conflict recorded as an **integration failure at the cut** rather than
resolved by guessing, then runs `hobbes review base..hobbes/<task>`. It
**does not re-ingest**: the record states that re-ingesting the merged
branch is what moves every manifest. Role and repo policies change the
same way — by commit.

### 4. The orchestrator and the record

`hobbes run <task>` is agent-mapping §3.4's orchestrator: a scheduler
and contract arbiter that owns no code. Units run in **contract order**
(a declaration's owner before its consumers; cycles broken by name and
said so). A **human-first** unit is not spawned — the plan said a human
goes first; the orchestrator posts that to its inbox and moves on.
Every run writes `.hobbes/plans/<task>/partition-record.json`: per unit
the session, exit, knowledge calls and faults, exec decisions,
reflections, commits, files changed, and **rework files** (outside the
manifest); integration and review results; and §6's **loss** under
ADR-051's declared weights, labelled a guess (C-35), with tokens and
wall time listed as **unobserved** rather than imputed.

### 5. What the base does not do (C-38)

Write scope is **advisory at path grain**: the sandbox mounts the
worktree whole, and the derived `write_mounts` are measured afterwards
as rework rather than enforced at the mount. Renegotiation has no
approval flow — a reflection reaches the orchestrator's inbox and a
human. Tokens and wall time are not metered. No generative planner sits
above the lexical seeds (C-36). No verifier session is spawned yet — the
`verifier` role exists (read-only worktree, like `reviewer`) and the
review runs in-process. Each of these is a line in the register or
`future_additions.md`, not a silent gap.

## Consequences

- A change-spec is now runnable: `hobbes plan "…"` → `hobbes run <task>`.
  `--dry-run` materializes everything and spawns nothing; the test
  suite drives the loop with a stand-in session binary that writes the
  exact shapes the Go side writes (flight log, mail, harvested branch).
- The knowledge tools' answers are unchanged; their flight events gain
  one optional field. Old artifacts and sessions read the same.
- `hobbes-session start` and `hobbes-proxy serve` gain `--agent-dir`.
  Without it nothing changes. With it, `policy.yaml` is required (the
  proxy refuses exec otherwise) and `context.json` is optional.
- `list_blind_spots` and `reflect` are on the sandbox tool allowlist —
  the former had been missing since ADR-047, a one-line gap found while
  adding the latter.

## Verified

723 pytest (+20: `test_run.py` — spec resolution, role scaffolding, mail
round-trip and fold-back, agent materialization, contract ordering, the
dry run, the full loop against the stand-in binary reading flight, mail
and branch, human-first not spawned, stale-plan warning, CLI exits).
Go 212 (+15: chain ordering and narrow-only, fault tagging, reflect,
agent policy refusing what the repo allows, mounts, verifier ro, a real
harvest of two commits). Dogfood dry run of plan `2a56b09172c9` with
the real `hobbes-session`: order U2 → U1 → U3, agent dirs mounted ro at
`/agent`, the brief as the prompt, derived policies carrying the three
guarantees first and the guarding pytest files as allows. No sandboxed
session was spawned this session (no quota spent); the first real runs
are the benchmark harness's.
