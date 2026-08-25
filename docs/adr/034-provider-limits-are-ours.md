# ADR-034 — A provider's limits are Hobbes's limits (P9)

**Status:** accepted (2026-08-15)

**Context:** Max's call, before V2.M4. Adds principle **P9** to the running
architecture §1. Changes no code; changes what "done" means.

## Context

Hobbes does not resolve names. It runs `scip-python`, `scip-typescript`,
`scip-go` and — when Rust arrives — rust-analyzer, and consumes their
output. That is P7 working as intended: languages are configuration, and
Hobbes never has to understand a type system it did not write.

The trade has a second half nobody had written down. Every one of those
indexers has blind spots, and they land in Hobbes's graph as missing or
imprecise edges. Three are already registered:

- **C-6** — a semantic index cannot say what a reference syntactically *was*.
  SCIP occurrences carry a `syntax_kind` field that would answer it, and
  `scip-python` populates it for none of them. This is the reason lane A
  keeps call-site detection at all (ADR-029).
- **C-9** — only four descriptor kinds become graph symbols; ~86% of SCIP
  definitions are parameters, locals and meta symbols.
- **C-23** — TypeScript semantics need the *target repo's* dependency tree
  installed. Without it, third-party edges are simply absent.

The failure mode this ADR forecloses is the easy sentence: *"that's
scip-python's limitation, not ours."* It is true and it is worthless. The
user did not install `scip-python`; they ran `hobbes ingest`. A missing edge
looks identical whether Hobbes dropped it or an indexer never emitted it,
and in both cases the reader concludes the call does not happen (C-1). Where
the gap came from changes nothing about what it costs.

There is a sharper version of the same risk: an inherited limit is *easier*
to leave unregistered than one of our own, because no decision of ours
created it. Nobody writes an ADR the day an upstream tool fails to implement
a field. P8 keys on the moment of decision, and there is no such moment
here — which is precisely how C-6 and C-23 both went unregistered until
V2.M3 went looking.

## Decision

**P9 — A provider's limits are Hobbes's limits.** Every gap a
language-specific provider has against us is written down and surfaced as
*ours*: never disowned as the indexer's problem, never left as a silent hole
in the graph.

Mechanically, a provider limit is a P8 constraint with one addition:

- It registers in `docs/constraints/README.md` like any other concession, with a
  surfacing status and the place a user meets it.
- It **names the provider and the pinned version** that produced it.
- Its `Source:` line says the limit is inherited, so a re-read knows the
  entry's lifetime is the provider's rather than ours.

The version matters because inherited limits are the only entries in the
register that can end without us doing anything. `scip-python` may populate
`syntax_kind` in some future release; the day it does, C-6 is liftable and
lane A's detection role becomes a choice rather than a necessity. An entry
that does not name a version cannot be re-checked against an upgrade.

**Trigger:** wiring a provider, pinning a new version of one, or finding a
gap while debugging. The bar is the P8 bar — if the graph is missing or
approximating something a reader would assume was there, it is registered
before the milestone exits.

## Consequences

- V2.M5 (`scip-go`) and V2.M7 (rust-analyzer) each arrive owing a
  provider-limit review, not just an ingest. "It works on a Go repo" is not
  the exit; "it works, and here is what this indexer cannot see" is.
- Version-pinning gains a second purpose. It already exists for
  reproducibility; under P9 it is also the key an inherited constraint is
  filed against.
- C-6, C-9 and C-23 are retrofitted to name their provider and version in
  the same commit as this ADR. Three entries, all already true — the
  principle is being paid rather than announced.
- **Tension with P7, stated plainly.** P7 says adding a language should be
  configuration. P9 says every added language brings documentation work that
  cannot be automated. Both hold: the *code* stays configuration; the
  *honesty* does not come for free, and pretending it does is how a
  three-language graph quietly becomes a two-and-a-half-language one.
- No new `C-n` for the principle itself. It creates entries; it is not one.
