# Agent Mapping — deriving agents, context, and policy per task

**Status: design record.** §§1–5 are built as of D1 (ADR-051,
2026-08-19, reviewed 2026-08-21): the mapping runs as `hobbes plan`.
The execution half of §2's phases 4–5 and §6's partition record are
built as a **base** at D2 (ADR-054, 2026-08-21): `hobbes run`, with the
owner's agent structure layered on — per-agent policy (repo + role +
derived agent layer), standing and short-term context, reflections,
branch harvest. The running architecture's §6 describes both as they
are — that section, not this file, is current. Loss *fitting*, the
renegotiation re-pin, and path-grain write enforcement are not built
(C-38); what remains is in `future_additions.md` under "D2". **One step
now precedes §3.1 in the built mapping (ADR-084/085, 2026-08-23):
proposal → requirements.** The planner — the single role that reads the
whole request — decomposes it into requirements, each with an owning
file; the impact set is seeded from those owners; coverage (every
requirement has an owning unit) is checked deterministically and an
unowned requirement is a plan error at plan cost. On a covered plan each
implementer's brief carries its owned requirements as its task and the
proposal is absent — §4's "only its slice" extended from code to the
request itself. Architecture §6.1 is the current text. This file stays as the record of
where the design started, the way `hobbes-architecture-v1.md` is for
extraction. The original header follows.

This is the proposed
shape of the unbuilt milestone the running architecture names in "Where this
is going": single-use agents under derived, systematic context. Nothing here
is built. When any of it is, the change patches `hobbes-architecture.md` in
the same commit (ADR-033) and this file becomes the record of where the
design started, the way `hobbes-architecture-v1.md` is for extraction.
Everything below is bound by the derivation contract (ADR-047): a derivation
that hands an agent only the captured half is not done.

The question this document answers: given a proposed change, what determines
**how many agents**, **which context each one gets**, **what policy each one
runs under**, and **who checks what** — as an algorithm over artifacts Hobbes
already has, not as an org chart.

---

## 1. Premise — phases, not personas

The company pipeline (propose → plan → review → implement → verify) is worth
copying for its *gates*, because gates are verification structure. The
company's *roles* are not worth copying, because roles are a solution to
human constraints — fixed capacity, scarce skills, expensive knowledge
transfer, incentives — none of which an agent has. Companies are shaped to
fit an economy; we are free to be shaped to fit the codebase.

So: an agent here has no title. An agent is a triple —

> **agent = (context slice, policy profile, verification obligations)**

— derived per task, started once, ended when the task ends. Where a persona
would say "the DevOps engineer reviews the plan," this design says "infra-
typed nodes and cut edges carry review obligations." Same gate, no employee.
The org chart, to the extent one exists at runtime, is an **output** of the
mapping — never an input to it.

---

## 2. The pipeline — five phases, each an artifact

Every phase produces an artifact a human can read and the next phase
consumes. No phase's output is another agent's chat transcript.

1. **Propose.** The human states the change. Free text.
2. **Plan.** A planning session maps the proposal onto the graph and emits a
   **change-spec**: impact set, partition, contracts, per-agent context and
   policy manifests, and the stated complement for each (§3–§5). The
   change-spec is the unit of review, versioned beside the task.
3. **Plan review.** The change-spec's *proposed edges* are checked against
   invariants before any code exists — a graph diff of code not yet written.
   A plan that adds `billing → auth.token` fails I-3 at this gate, at
   planning cost instead of PR cost. Human approves the change-spec at
   concept level; invariant verdicts and blind-spot load are in front of
   them when they do.
4. **Implement.** One single-use agent per partition, each in its own
   worktree and sandbox, each holding its slice and nothing else. Agents do
   not talk to each other; they share only the pinned contracts.
5. **Integrate and verify.** Contracts checked at the cut edges, `hobbes
   lanes` and the invariant checker on the merged result, guarding tests per
   partition, then the standing concept-review flow (graph diff → invariant
   verdicts → coverage delta → line diff last).

A failed gate re-enters at the phase that produced the failing artifact —
a contract that proves wrong during implementation is an **escalation**, not
a silent workaround (§7).

---

## 3. The mapping algorithm

### 3.1 Proposal → impact set
Seed nodes: every graph node the proposal names or resolves to (symbols,
files, routes, env vars, infra resources). Expand along typed edges with
tier-weighted decay — semantic edges propagate strongly, syntactic weakly,
pack edges at their declared tier — to a scored impact set.

The impact set carries **both halves from birth** (ADR-047): alongside the
captured nodes, the derivation intersects the task's scope with the tail
view and the constraint register. A task whose scope lands in a directory
the per-directory capture view ranks poorly is a task the mapping *knows*
it sees badly, and that fact rides the change-spec forward — it is not
discovered by an agent mid-task.

### 3.2 Impact set → partition
Partition the impact subgraph into work units by minimizing cut-edge weight
subject to a per-unit context budget:

- **node weight** = representation cost: tokens to carry the node's code,
  its guarding tests, and its module doc at full resolution;
- **edge weight** = coupling: `tier × edge-type weight × reference count ×
  co-change factor`;
- **constraint**: each unit's total context (interior + boundary + overhead,
  §4) fits the agent budget — a fixed fraction of the context window, held
  well below the ceiling because accuracy degrades before capacity does.

**Agent count is the partition's output, not a parameter.** A contained
change yields one unit — one agent, zero coordination. A cross-cutting
change yields several. The codebase decides; that is the scaling law.

**Co-change factor.** Files that repeatedly change in the same commits get
their edges strengthened, from `git log` co-occurrence over a bounded
window. This is observation, not inference — the commits happened — and it
encodes the one thing static structure cannot: what is *secretly one thing*
in practice. A partition that separates a co-change hotspot is a partition
that manufactures rework.

### 3.3 Cut edges → contracts
The edges the partition severs are the interfaces between agents. Before
implementation, the plan pins each one: signature or schema, the invariants
that constrain it, and which side owns any migration. Contracts are part of
the change-spec, so they pass the plan-review gate — including the
invariant check — before an agent exists.

### 3.4 Recursion, and the only orchestrator there is
A unit that cannot fit budget is partitioned again; hierarchy is a recursion
artifact, appearing exactly when a task demands it and never otherwise. The
orchestrator that remains is a **scheduler and contract arbiter**: it
sequences units whose contracts have dependency order, arbitrates
renegotiations, and owns no code. Its policy profile has no write access to
any worktree — it writes change-spec artifacts and nothing else. It is not
an exception to the sandbox; it is the most restricted session in the run.

---

## 4. Context derivation — resolution decays with distance

Per agent, the context manifest is computed, not assembled by prompt:

- **Interior** (its partition): full resolution — code, guarding tests,
  module docs, in-scope invariants.
- **Boundary** (its cut edges): the pinned contracts, and signatures only
  for the far side. The far side's internals are deliberately absent —
  information hiding as a computed property.
- **Neighborhood**: one hop past the boundary, signatures; beyond that,
  module-doc summaries only. Detail falls with graph distance.
- **The stated complement** (mandatory, ADR-047): `list_blind_spots` for the
  partition's scope, the register entries whose surface the task touches,
  and the tail classes present in its files — so the agent knows what it
  must read, verify, or refuse to assume, rather than trusting a surface
  the graph quietly guessed at.

Shared context between agents is therefore exactly the cut set plus global
invariants in scope. Nothing else is shared, and "what context should be
shared" stops being a judgment call.

**Context faults.** An agent may still request nodes outside its manifest
through the MCP server. The request is served — starving an agent to prove
a point helps no one — but logged as a **context fault**: the allocator
predicted this agent would not need that node, and it did. Faults are the
partition formula's error signal (§6), page faults for context.

---

## 5. Policy derivation — evidence widens, gaps narrow

Each agent's policy is generated from the same manifest:

- **Floor**: the standing role images and the box policy. Nothing derived
  may widen past a specific guarantee — never `.tfstate`, never push,
  never `derived/` committed (P10; the generator names these and re-raises
  rather than absorbing them).
- **Widening requires evidence**: write mounts for the partition's paths;
  network and tool grants only where a captured, tiered edge justifies them
  (a `db-write` edge justifies the migration tool; nothing else does).
- **Gaps stay narrow**: where the task's scope is thin in the capture view,
  there is less evidence to widen on, and the honest defaults are read-only
  and escalate — the enforcement half of ADR-047. An agent working blind
  spots gets a narrower sandbox and a faster path to a human, not a wider
  one and a warning.

---

## 6. The formula learns from the recorder, and says so

The initial weights — decay rates, edge-type weights, co-change window, the
budget fraction — are guesses, and per P8 the design says so: on build, the
unvalidated-partition-quality concession is registered as a constraint and
stays registered until the evidence exists, in the same spirit as C-31's
thin-sample honesty. "Assigns roles accurately" is not a design claim here;
it is a number this section defines and the recorder measures (P11: the
claim will be scoped to recorded runs, never to tasks shaped unlike them).

Per run, the flight recorder gains a partition record: the change-spec id,
units and budgets, contracts, then per agent — context faults, boundary
rework (commits touching another unit's files), contract renegotiations,
integration failures at cut edges, escalations, tokens, wall time.

**Loss = w₁·rework + w₂·contract failures + w₃·context-fault rate +
w₄·tokens + w₅·wall time.** Tune the mapping's weights against accumulated
history; every term is already observable with one recorder schema
extension. The formula ships as a heuristic and earns its parameters.

---

## 7. Failure modes designed against, from day one

- **Over-decomposition.** When a unit's contract overhead approaches its
  interior's size, merge it into its cheapest neighbor. Coordination that
  costs more than the code it coordinates is the company failure this
  design exists to avoid; the threshold is explicit, not vibes.
- **Frozen-wrong contracts.** Implementation can prove a pinned interface
  wrong. The path is renegotiation as an escalate-tier event — the agent
  parks, the human sees the proposed amendment against the change-spec, and
  approval re-pins the contract for both sides. A silent workaround is a
  policy violation, not initiative.
- **Fault storms.** A context-fault rate past threshold means the partition
  was wrong for this task. The degradation is **fewer agents, never more
  guessing**: collapse the affected units into one with the merged manifest
  and continue. Degrading toward a single well-fed agent is always
  available and always coherent (P6's no-second-code-path lesson: the
  one-agent case is the same pipeline with a partition of size one).
- **Blind-spot-heavy tasks.** When a unit's stated complement rivals its
  captured fraction, the derivation does not pretend: it flags the unit at
  plan review as human-paired or human-first. Refusing to auto-run a task
  the graph cannot see is the honest shape; a confident agent on a quietly
  unseen scope is the exact failure the register exists to prevent.

## 8. Out of scope

Personas, titles, and fixed team templates; agent-to-agent free-form chat
(contracts are the only interface); any hosted coordination; running the
derivation from the web surface (the surface never runs the pipeline,
ADR-022); multi-repo tasks (§3.3 of the running doc says why that is
thinner than once claimed); model fine-tuning; tuning-loop automation
beyond weight fitting — the loss function informs a human, it does not
retrain anything.

## 9. Open questions for the ADR that accepts this

The budget fraction and whether it varies by task shape; the decay
function past the boundary (step vs smooth); the co-change window length;
initial loss weights; where change-specs live (`derived/` is wrong — they
are approved artifacts, not regenerable ones — but versioning every plan
beside `policies/` has its own noise cost); and whether plan-review
verdicts render in the existing review flow or need their own surface.
