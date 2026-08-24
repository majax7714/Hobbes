# Hobbes — v1 Build Plan

> **Complete, and historical for extraction.** M0–M8 are all built and
> reviewed. The active programme is
> [`hobbes-build-plan-v2.md`](hobbes-build-plan-v2.md) (V2.M0–V2.M7). The
> milestones below are the record of how v1 was built; the extraction
> milestones in particular describe a design v2 has replaced. The
> sequencing rules carry forward unchanged.

Companion to `hobbes-architecture-v1.md`. Sequenced so every milestone ships
something usable on its own, deterministic value lands before any quota is
spent, and enforcement exists before any agent writes code. Estimates are in
evenings (2–3 focused hours), not corporate weeks.

---

## Language-to-focus mapping

Per the "no singular language" principle — each component in the language its
job actually favors. **Locked by D1.**

| Component | Recommended | Why |
|---|---|---|
| Extractors + pipeline | Python | tree-sitter bindings, HCL/plan-JSON tooling, fastest iteration; it's also the first language being extracted, so the extractor dogfoods itself |
| Policy proxy, session supervisor, flight recorder | Go | long-running daemon: static binary, real concurrency for multi-session supervision, strong exec/process control, trivial deploys — and starts your Go on-ramp |
| Web surface | TypeScript + React | your existing frontend stack; interactive graph needs a real frontend |
| Invariant compiler | Python | emits import-linter/semgrep/Rego configs; shares the extractor's model of the graph |

---

## Milestones

### M0 — Skeleton + policy semantics (2–3 evenings)
CLI scaffold (`hobbes init`, `hobbes ingest`, `hobbes diff`), `.hobbes/` layout,
policy file format, and the **merge algorithm** (box → repo → folder,
deny-overrides-allow, escalate tier) with a unit-test battery. The policy
engine is written in Go from day one as a small package with a
`hobbes policy resolve` subcommand — the Python CLI shells out to it, and the
M4 daemon imports it, so deny-overrides-allow has exactly one implementation
everywhere.
*Exit: policy merge passes tests covering shadowing, deny-wins, and escalation.*
Policy semantics come first because everything downstream trusts them.

### M1 — Python extractor (4–6 evenings)
tree-sitter walk → symbols, module graph (typed edges), FastAPI/Flask route
inventory, pytest test inventory with static test→symbol reach. Emit
`derived/graph.json`, `tests.json`, `interfaces.json`, SHA-stamped.
*Exit: run against a real repo of yours; spot-check 20 edges and 10
test mappings by hand — target ≥90% correct at module level.*

### M2 — Graph render + diff (2–3 evenings)
Module-level Mermaid export; graph-diff algorithm (`graph(base)` vs
`graph(head)`) with typed added/removed/changed edges; `hobbes diff <base>..<head>`
prints the architecture delta.
*Exit: a real PR produces a correct edge-level delta.*
M0–M2 form a standalone tool with zero LLM involvement — worth using even if
the project stopped here.

### M3 — Terraform extractor (2–3 evenings)
HCL parse + `plan -json` consumption → infra nodes/edges, cross-layer joins via
env-var references. `.tfstate` deny baked into the default box policy.
*Exit: app+infra graph for one repo; one cross-layer edge verified by hand.*

### M4 — Policy proxy + sandbox + flight recorder (5–7 evenings, the hard one)
The daemon: MCP server exposing `exec` (policy-checked), knowledge-layer query
tools, JSONL flight recorder, escalation queue (CLI approve/deny first), and
the session wrapper that launches Claude Code inside the sandbox (per D2) in a
fresh worktree with merged policy.
*Exit: an implementer session completes a small task; a prohibited command is
refused and logged; an escalated command parks, gets approved from the CLI, and
runs. No secrets present in the session environment.*

### M5 — Narrative pass (3–4 evenings + subscription quota)
Cartographer session prompts: module docs, test-behavior one-liners, inferred
invariants — every claim `file:line @ SHA`-pinned. Stale-badge computation.
Incremental regeneration (only changed graph nodes).
*Exit: docs for the dogfood repo; 10 sampled claims all resolve to lines that
support them; a deliberate source edit flips the right stale badge.*

### M6 — TypeScript extractor (3–4 evenings)
ts-morph symbol resolution, module graph, Express/Nest routes, vitest/jest test
inventory. Same JSON contract as M1.
*Exit: same 90% spot-check bar on a real TS repo.*

### M7 — Web surface (5–8 evenings)
The four tabs plus Sessions: interactive graph (per D3), test behavioral index,
docs with provenance links and stale badges, sessions monitor reading the
flight recorder live, escalation approve/deny in-UI.
*Exit: the mockup, real, against your repo.*

### M8 — Reviewer flow + invariant compiler v0 (4–5 evenings)
YAML invariants → import-linter contracts + semgrep rules (+ Rego for infra);
`hobbes review <PR>` = graph diff + invariant verdicts + behavioral-coverage
delta + reviewer-session narrative for `soft` invariants.
*Exit: the v1 bar from architecture §11, end to end, on one real PR.*

**Total: ~28–38 evenings.** At 3–4 evenings/week alongside work and school,
roughly 8–11 weeks. M0–M3 (the no-quota half) is ~2–3 weeks and already useful.

---

## Sequencing rules

1. **Deterministic before generative** — M0–M3 spend zero quota.
2. **Enforcement before agents** — no session writes code until M4's proxy and
   recorder exist.
3. **Content before chrome** — the web UI (M7) comes after there's a knowledge
   layer worth rendering.
4. **Each milestone exits on your repo**, never a toy fixture.

---

## Decisions — locked

- **D1: Python + Go + TS, split by focus** (extractors/pipeline/compiler in
  Python; policy engine, proxy, supervisor, recorder in Go; web surface in
  TS/React).
- **D2: Podman rootless** — session isolation via per-role images; policy paths
  map to mounts, network policy to container network config. Native to Fedora.
- **D3: Interactive graph from the start** — Cytoscape.js in the web surface;
  Mermaid remains the markdown/export renderer.

Storage is decided without a vote: JSON files in `derived/` as the canonical
artifact (diffable, CI-friendly), loaded in-memory for queries — SQLite index
only if a repo ever makes that slow.
