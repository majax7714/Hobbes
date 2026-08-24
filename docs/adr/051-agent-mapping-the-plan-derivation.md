# ADR-051 — The agent mapping accepted; D1 builds the plan derivation

**Date:** 2026-08-19
**Status:** accepted
**Amends:** `docs/hobbes-architecture.md` ("Where this is going", new §6
"Derivation — the task mapping"; §§6–9 renumbered to §§7–10)
**Constraints:** C-35, C-36, C-37 registered in the same commit

## Context

`docs/agent-mapping.md` (Max, 2026-08-19) is the design for the unbuilt
milestone the architecture names in "Where this is going": single-use
agents under derived, systematic context. Its premise — **phases, not
personas** — replaces the company org chart with an algorithm: an agent
is a triple *(context slice, policy profile, verification obligations)*
derived per task, and the number of agents is the output of a graph
partition, never a parameter. Max's direction for this session:
reference that doc, build the system, register the concessions.

This ADR accepts the design and scopes the first milestone of the
derivation programme, **D1 — the plan derivation**: the deterministic
mapping from a proposal to a **change-spec**, phases 1–3 of the
document's pipeline, shipped as `hobbes plan`. It deliberately does
*not* build phases 4–5 (spawning per-unit sessions, context-fault
serving, the recorder's partition record) — those need Go-side wiring
and are parked with their reasoning in `future_additions.md`. The
one-agent degradation the design demands (§7 of the doc) exists by
construction: a contained proposal partitions into one unit, and that
is the same code path, not a special case.

Everything below is bound by the derivation contract (ADR-047): a
manifest that lacks its stated complement **refuses to serialize** —
the contract is enforced in code, not remembered in review.

## Decision

### The pipeline lands in `pipeline/src/hobbes/derive/`

- `impact.py` — proposal → scored impact set (§3.1 of the design).
  Seeds resolve **lexically**: explicit `--seed` ids/paths, plus
  proposal tokens matched exactly against node ids, node path stems,
  and symbol names. Nothing is inferred from prose; a code-shaped term
  that matches nothing is reported, never guessed at (**C-36**).
  Expansion is max-product propagation over the module-projected graph
  with tier- and type-weighted decay, both directions (impact reaches
  callers and callees).
- `cochange.py` — the co-change factor from `git log` co-occurrence
  over a bounded window. Observation, not inference: the commits
  happened. A repo without usable history yields factor 1.0 and says
  so.
- `partition.py` — impact set → work units (§3.2). Node weight is
  representation cost (module file + guarding test files + module doc,
  estimated tokens); edge weight is coupling (tier × type × reference
  count × co-change); agglomerative merge under a per-unit budget.
  Agent count is the partition's output. The over-decomposition rule
  (§7 of the design) is explicit: a unit whose contract overhead
  reaches its interior weight merges into its strongest-coupled
  neighbor.
- `contracts.py` — cut edges → pinned contracts (§3.3): the crossing
  edge, its tier, the far symbol's **declaration site**, the owning
  side (the definition side owns migration), and the in-scope
  invariants that constrain it. A pin is a declaration site, not a
  type signature — the graph does not carry parameter types (**C-37**).
- `manifests.py` — per-unit context manifests (§4: interior at full
  resolution, boundary as contracts, neighborhood as signatures,
  **the stated complement always** — capture rollup, tail classes with
  their C-n meanings, environment gaps, degradations) and policy
  manifests (§5: read-only floor, write mounts widened only over the
  interior, the specific guarantees P10 names emitted first and
  impossible for the generator to widen past — it raises rather than
  absorbing them). A blind-spot-heavy unit is flagged **human-first**
  and gets no write mounts.
- `changespec.py` — assembly, the plan-review gate, serialization.
  The gate checks **declared proposed edges** (`--adds "a -> b"`)
  against confirmed forbidden-import invariants before any code
  exists — a graph diff of code not yet written, at planning cost
  instead of PR cost. Exit 1 on a violated invariant.

`hobbes plan "<proposal>"` runs the whole derivation and writes the
change-spec. Same graph + same proposal + same flags → byte-identical
change-spec (no wall-clock timestamp in the artifact; the task id is a
content hash of the proposal, the same keying discipline ADR-026 uses
for decisions).

### Answers to the design's §9 open questions

1. **Budget:** a pinned default of 60,000 estimated tokens per unit
   (bytes/4), overridable with `--budget`. It does not vary by task
   shape in D1 — varying it is a parameter the loss function should
   earn, and nothing measures the loss yet (C-35).
2. **Decay past the boundary:** a step function — interior full,
   boundary contracts, one hop signatures, nothing beyond. The design
   already describes a step; a smooth decay adds parameters with no
   evidence behind them.
3. **Co-change window:** the last 200 commits. Pinned as a count, not
   a time span, so the same HEAD gives the same answer.
4. **Initial loss weights:** recorded here as declared guesses —
   w₁ (rework) 3, w₂ (contract failures) 3, w₃ (context-fault rate) 1,
   w₄ (tokens) 0.5, w₅ (wall time) 0.5. Nothing computes the loss in
   D1; the weights exist so the recorder milestone has a spec to
   implement, and C-35 says the number the design refuses to claim.
5. **Where change-specs live:** `.hobbes/plans/<task-id>/change-spec.yaml`
   — beside `policies/` and `invariants/`, because a change-spec is an
   approved artifact, not a regenerable one; `derived/` would be wrong
   (P1 says derived content is regenerable from a SHA, and an approval
   is not). In target repos the whole `.hobbes/` is already personal
   (ADR-012). In this repo `.hobbes/plans/` is gitignored: unlike the
   dogfooded invariants, a plan is a per-task working record, and
   committing unapproved plans would put Max's name on decisions he
   never made. Plans share C-20's clone-locality.
6. **Plan-review rendering:** the CLI first. The gate's verdicts print
   from `hobbes plan` and the change-spec carries them; a web surface
   rendering is parked in `future_additions.md` with the other
   blind-spot surface work.

### The pinned parameter table (all C-35)

| Parameter | Value |
|---|---|
| tier weights | semantic 1.0 · syntactic 0.6 · dynamic 1.0 |
| per-hop decay | 0.55 — distance always attenuates; the dogfood exit check measured a 1.0-factor chain pulling the whole connected component (33 units) before this term existed |
| edge-type weights | calls 1.0 · http/db/queue 0.9 · imports 0.8 · env-read/env-set 0.8 · packages 0.8 · uses 0.7 · references 0.6 · unknown 0.5 |
| expansion threshold | include nodes scoring ≥ 0.2 |
| unit budget | 60,000 estimated tokens (bytes/4) |
| co-change window / factor | 200 commits; 1 + min(pairs, 8)/4 |
| contract overhead | 300 estimated tokens per contract |
| human-first threshold | cannot-resolve > 50% of ≥ 10 detected sites in the unit's files |

Every number is a guess stated as one. "Partitions accurately" is not
claimed anywhere; it is the number the recorder milestone will measure
(P11 — the claim will be scoped to recorded runs).

## Consequences

- The architecture's "three of the four pieces exist" becomes "the
  fourth is begun": the mapping half of the derivation is running
  code; the execution half (spawning, faults, recorder, renegotiation)
  is the next milestone and is parked with reasoning, not implied.
- Three register entries in this commit: **C-35** (partition quality
  unvalidated — surfaced on every `hobbes plan` run and in every
  change-spec), **C-36** (seed resolution is lexical — unmatched
  code-shaped terms surfaced in the change-spec and the CLI),
  **C-37** (a contract pins a declaration site, not a signature —
  surfaced in every contract entry).
- `hobbes plan` is quota-free and deterministic end to end. A
  generative planning session on top of lexical seeding is future
  work and will sit above this layer, pinned to it (P5), never inside
  it.
- Milestone discipline holds: D1 exits to Max's review before any
  execution wiring is started.
