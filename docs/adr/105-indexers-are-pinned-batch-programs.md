# ADR-105 — A language indexer is a pinned batch program with a stated version and a tier stamp — never a language server

**Date:** 2026-09-10 · **Status:** accepted — Max's rule, stated on the C-98 session · **Owner:** Max · **Source:** the C-98/C-99 lift, where both lanes' reading of a tsconfig was held against the compiler's own and the question of what a lane B provider *is* came up for the next language

Amends the architecture's **§1** (a principle, P13), **§3.2** (the
opening statement of lane B) and **§3.7** (step 1 of adding a
language). Changes no code: `INDEXERS` in `scip/index.mjs` is already
the registry and the sandbox image the pin.

## Context

Lane B's providers are SCIP indexers today — `scip-python`,
`scip-typescript`, `scip-go`, rust-analyzer's native `scip` export,
`scip-java` riding the repo's own build. §3.2 opened with "per-language
batch indexers emitting SCIP" and never said which of those words was
the rule and which the current state. §3.7's first step says *register
the indexer: command, version pin, and how its config is derived* — a
pin, without the reason, and without naming what is excluded.

Two things make the rule worth stating before the seventh language:

- **A per-language indexer need not be SCIP.** Two of the five already
  are not `scip-*` wrappers (rust-analyzer's export; a javac plugin the
  launcher injects into a Maven or Gradle build), and the helper owns
  the decode of SCIP's typed ranges rather than trusting a borrowed
  reader. A compiler's own export, a build plugin, an indexer emitting
  another IR may serve a language better than its SCIP indexer does —
  and should be admissible, on the same terms.
- **The obvious alternative is a language server**, which is what most
  tooling reaches for when it wants resolution: long-running, warm,
  answering `definition` and `references` per query. It is faster for
  an editor and wrong for Hobbes, for reasons that are the project's
  three properties, not taste.

## Decision

A lane B provider — any program whose output becomes a `semantic` edge —
is admitted only if it is all of the following.

1. **A batch program.** Run to completion on a stage, from a fixed
   input set to an artifact and an exit code; no state carried between
   runs. Same commit in, same artifact out (P1, P5).
2. **Pinned, with a stated version.** The binary and its version are in
   the registry and the sandbox image; every ingest records which one
   built the artifact (`built_by`), and every provider limit registers
   with that version, because its lifetime is the provider's (P9,
   ADR-034).
3. **Stamped by tier.** Every edge it yields enters the graph through
   the range join and carries `semantic` with the provider named in its
   evidence; the join assigns tiers, providers never do (§3.3, ADR-045).
4. **Not SCIP-only.** SCIP is the IR the helper decodes today, not the
   rule. A provider emitting another format joins through the same
   range join once the helper decodes it to the same facts —
   definitions and references at file:line ranges — and it is a
   configuration entry, not an integration (P7), meeting 1–3 and §3.8's
   evidence row like any other.
5. **Never a language server.** A long-running, query-answering process
   is excluded, whatever its accuracy: its answers depend on session
   state and warm-up, so they are not reproducible from a SHA; it
   cannot be pinned and shipped as an artifact the way a binary in the
   image is; it cannot be run to completion under a per-step containment
   profile with no network and a fixed mount set (ADR-092); and it
   answers questions instead of producing the artifact the graph is
   derived from — the graph would be *queried*, not *derived* (P1).
   Determinism is the second of the three properties; a language server
   trades it for latency Hobbes does not need.

## Consequences

- §1 gains **P13**; §3.2 opens with the rule; §3.7's step 1 states it
  and names the five points a candidate indexer is read against before
  the checklist runs.
- The existing five providers pass: each is a batch binary in the
  image at a pinned version (`scip-go` 0.2.7, `scip-java` 0.13.1, the
  rest by the `scip/` lockfile and the toolchain), each stamped through
  the join. scip-java is the edge case and passes on the same terms:
  the build is run to completion, twice, contained (ADR-097).
- What this does *not* decide: which non-SCIP indexer, if any, comes
  next. It decides how one is judged.

## Tests

None — no code moves. The rule is held by the architecture and this
record; §3.7 is the place a new language meets it.
