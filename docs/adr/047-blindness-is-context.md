# ADR-047 — Blindness is context: `list_blind_spots`, and the derivation contract

**Status:** accepted (2026-08-16)

**Scope:** Max's direction: the constraint register is a **needed
integration** with agentic policy and, eventually, the derived agentic
context layer — knowing what Hobbes cannot see is functionality, not
apology. Two deliverables: a sixth knowledge tool on the session proxy
(**built**), and the derivation contract written into the architecture
("Where this is going" — **direction, not started**). Amends
architecture "Where this is going"; updates C-2's surfacing;
`future_additions.md` gains the derivation-time integration entry.

## Context

Every knowledge tool the proxy serves — `graph_neighborhood`,
`who_calls`, `tests_guarding`, `get_module_doc`, `list_invariants` —
serves the **captured fraction**: what the graph proved. Nothing served
its boundary. An agent inside a session could read every edge and still
not know that the file it is editing sits at 56% resolution, that three
of the repo's packages never resolved, or that TS test reach says
nothing about fixture-injected behavior. The human got the capture line
at ingest (ADR-045); the agent — the reader P2 says shares the same
knowledge layer — got silence, and a silent graph region reads as an
empty one (C-1's trap, one level up).

The guaranteed-fraction framing (ADR-044) says the complement is
information: what Hobbes cannot capture is thereby *identified* as
needing care. For a single-use agent, "needing care" has an operational
meaning — **it is the agent's own work list**: the context it must
gather by reading, the claims it must verify rather than trust.

## Decision

**1. `list_blind_spots(scope)` — built.** The sixth knowledge tool,
same contract as the other five (read-only over `.hobbes/derived/`,
logged to the flight recorder, staleness header). For a repo-relative
path prefix (or the whole repo) it answers, in an agent's terms:

- the standing denominator statement — what is **never in any count**
  because it is not detected at all (C-1 dynamic dispatch, C-4 fixture
  reach, C-5 computed routes); every number is a floor over *detected*
  sites, not the repo;
- the per-language capture rollup with the ADR-045 groups (*seen, not
  modelled by design* vs *cannot resolve*);
- environment gaps (`dependency_coverage` misses — invisible, not
  absent) and degradation records;
- the files with the largest unresolved remainders, class-broken;
- a meaning line per class **present**, each naming its register entry
  — the C-n reference reaches the agent at the moment it matters, which
  upgrades the register's surfacing from "a document" toward P8's bar.

**2. The derivation contract — written, not built.** When per-task
derivation exists, derived context has two mandatory halves: the
captured fraction (graph, tests, docs — what can be cited), and the
**stated complement** (this tool's content for the task's scope). An
agent must receive "here is what you must verify yourself" alongside
"here is what is known", or the derivation inherits the confident-
surface-over-quiet-gap failure P8 exists to prevent — at the exact
layer whose purpose is preventing it. Derived **policy** integrates the
same data from the enforcement side: where the graph cannot see, the
policy has less evidence to widen on, and staying narrow (or
escalating) is the honest default. Both land in "Where this is going"
as requirements on the unbuilt milestone, so no future session can
design derivation without meeting them.

## Consequences

- Agents in sandboxes can now point at their own required work: read
  `list_blind_spots` for the area, and what falls in *cannot resolve*
  or below a coverage warning is theirs to verify by hand. Reviewer
  sessions get the same answer for judging whether a change trusts an
  unseen region.
- C-2's surfacing gains the agent-facing leg (the tool), beside the
  artifact field and the ingest capture line.
- The tool inventory contract test now pins seven tools; the proxy
  binaries were rebuilt (static, plus the sandbox copy) per the box
  convention.
- Not scoped: the surface (web) rendering blind spots; feeding
  `list_blind_spots` into `hobbes review` verdicts; the derivation
  itself. The first two are candidates in `future_additions.md`; the
  third stays Max's call, now with two requirements attached.
