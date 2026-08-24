# ADR 028: Graph schema v4 — edge tiers, evidence lanes, and a version gate that exists

Date: 2026-08-14
Status: accepted

Milestone V2.M1. Implements architecture v2 §3.4's edge contract and the
versioned-artifact half of §7's V2.M1. Supersedes nothing; extends ADR-006.

## Context

v2 gives every edge a confidence tier so consumers can tell a proven
dependency from a guessed one (§3.4), and §7 asks for "a versioned JSON
contract with a migration shim so v1 consumers keep working."

Two facts from the code shaped the design:

- **The artifact schema is already at v3**, so the target is **v4**. §7 calls
  it "schema v2" from the perspective of the v2 *architecture*, not the
  artifact's own counter.
- **No consumer gates on the graph's schema version.** ADR-006 states that
  consumers reject versions they don't know; none does. The only version
  checks in the tree are the policy file's (`policy.go:93`) and the tsextract
  facts helper's (`tssource.py:97`). `artifacts.go` reads `schema_version`
  and passes it to the UI as a number to display. A v4 graph would therefore
  be *silently half-read* by every consumer rather than refused — which is
  the failure the shim is supposed to prevent, so the shim has nothing to
  hang on until the gate is real.

## Decision

### v4 is additive over v3

No field is removed, renamed, or re-typed, and **no node or edge id
changes**. v4 adds:

- `tier` on every edge — `semantic` | `syntactic` | `dynamic`.
- `lane` on every evidence entry — which producer saw it (`tree-sitter`
  today; `scip` and pack names arrive at M2/M4).

That is §3.4's contract exactly: "every edge records `type`, `tier`,
`evidence` — file:line ranges + producing lane/pack." Nodes gain nothing:
§3.3's lane-A/lane-B node namespace is a real decision but there is only one
namespace until M2, and inventing a field with one possible value is the
speculative abstraction the conventions forbid.

Additive-only is what makes the "migration shim" cheap: there is no
translation layer, because a v3 reader that ignores unknown fields already
reads v4 correctly.

### Consumers declare the versions they understand

Every artifact read goes through **one gated loader per language**, and each
call site declares what it needs:

- consumers that only use v3 fields accept `{3, 4}`,
- consumers that use `tier` or evidence `lane` require `>= 4`,
- anything else is refused with the artifact, the version found, the
  versions accepted, and the command that regenerates it.

Refusing loudly is the point. A half-read graph produces a *plausible* wrong
answer — an invariant verdict computed over edges whose tier it could not
see, or a UI that draws proven and guessed dependencies identically — and
plausible wrong answers are the failure mode this system exists to avoid
(P6: degrade visibly).

The chokepoints already exist and are one per language:
`knowledge.go:loadInto`, `web/artifacts.go:readDerived`, `api.ts`'s typed
fetches, and — new — `hobbes/artifacts.py`, because the Python side reads
`graph.json` from five call sites in `cli.py` with a bare
`json.loads(path.read_text())` and no shared loader at all.

### The lane-A / lane-B id namespaces are disjoint by construction

Deciding this now costs a paragraph and prevents a collision that would
otherwise surface at M2. Current ids are bare dotted names (`hobbes.cli`),
bare paths (`src/flow`), or prefixed (`ext:`, `env:`, `tf:`). **Lane-B ids
will carry a `scip:` prefix**, which cannot collide with any current form.

So §3.3's "upgraded in place when an indexer lands" remains a real event at
M2 — a module covered by an indexer changes id — but it can never
*silently* alias a lane-A node, and the two namespaces can coexist in one
graph while lane B's coverage is partial.

That id change is a one-time discontinuity for graph diff, whose node
identity is `id` (ADR-009). M2 owns it, and it must be called out there
rather than discovered: a diff spanning the change would otherwise report
every covered module as removed-and-re-added.

## Alternatives considered

- **A v4 → v3 projection function.** The literal reading of "migration
  shim". Rejected: with an additive change there is nothing to project, and
  a translation layer would be code that exists only to be deleted at M4.
- **Gate centrally at the server, leave consumers ungated.** Cheaper, and
  wrong: `hobbes review`, `hobbes render` and the MCP knowledge tools read
  the artifacts without going through `hobbes-web` at all.
- **`lane` on edges rather than on evidence entries.** Reads more naturally
  until one edge is corroborated by two lanes, which is precisely what
  §3.4's agreement self-test looks for. Evidence is per-sighting, so lane
  belongs there.
- **Skipping the gate until M2 needs it.** The gate is most valuable exactly
  once, at the version boundary it is written for — adding it after v4 has
  already shipped means the v3→v4 step is the one step it cannot protect.

## Consequences

- `hobbes ingest` must be re-run after this lands; a v3 artifact on disk is
  now refused rather than misread, with the regenerating command in the
  message.
- The UI can badge tier as soon as lane B produces anything, without another
  schema change (V2.M2 carries that).
- Adding `tier` to edges means the graph-diff edge key stays `(from, to,
  type)` — a tier change on an existing edge is not an architectural delta,
  the same way an evidence line move is not (ADR-009). When lane B upgrades
  an edge from syntactic to semantic, that is a confidence change, not a
  structural one.
