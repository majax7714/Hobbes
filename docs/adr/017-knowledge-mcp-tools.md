# ADR 017: Knowledge-layer MCP tools, v1 subset

Date: 2026-08-11
Status: accepted

## Context

Architecture §6: agents get context "via MCP, not cold grep" — naming
`get_module_doc(node)`, `who_calls(symbol)`, `tests_guarding(path)`,
`graph_neighborhood(node)`, `list_invariants(scope)`. Build plan M4
ships "knowledge-layer query tools" in the daemon. Two of the named
tools have no data yet: module docs arrive with M5's narrative pass,
and the invariant format is defined at M8.

## Decision

The proxy serves the three tools whose data exists —
**`graph_neighborhood(node)`**, **`who_calls(symbol)`**, and
**`tests_guarding(target)`** (module id or path; the doc's `path` is
kept but a module id works too, since that's what the graph speaks) —
reading `.hobbes/derived/graph.json` and `tests.json` from the session
repo. `get_module_doc` and `list_invariants` are deferred to M5/M8
with their data, not stubbed: a tool that answers "not built yet" is
noise in the agent's tool list.

Behavior:

- **Fresh reads.** Artifacts are loaded per call, like the policy
  chain — a mid-session re-ingest takes effect on the next query.
- **Staleness is visible (P1).** Every answer is headed by the
  artifact's `sha` (and dirty flag); if the repo HEAD has moved past
  it, the answer carries an explicit stale warning naming both SHAs.
- **Misses help.** An unknown node or symbol answers with close
  matches (substring, capped) instead of a bare error.
- **Missing artifacts** answer "run `hobbes ingest`", not a crash.
- **Logged like everything else** (§6 "every tool call"): knowledge
  reads land in the flight recorder with the tool name, the query as
  argv, decision `allow`, rule `builtin:knowledge-read`, exit null —
  they are unconditionally allowed reads of derived data, never
  policy-resolved.

## Alternatives considered

- **Policy-gating knowledge reads** — the artifacts are derived,
  secret-free by construction (tfstate never enters the pipeline,
  ADR-010/011), and exactly what sessions are *supposed* to consume.
  Gating them adds escalation noise with no protected asset.
- **A query DSL / single `query` tool** — five named tools is the
  architecture's interface; a DSL is speculative surface.
- **Serving from a long-lived index** — the JSON files are small and
  the M0 storage decision (plain JSON, in-memory per query) already
  covers this; SQLite waits for a repo that actually hurts.

## Consequences

- Sessions start oriented: neighborhood, callers, and guarding tests
  are one tool call each, with provenance (`file:line`) in every
  answer.
- The flight log shows what context a session pulled, not just what
  it ran — useful when auditing why an agent did something.
- M5 and M8 extend the same surface with `get_module_doc` and
  `list_invariants` when their data lands.
