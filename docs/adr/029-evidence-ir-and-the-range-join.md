# ADR 029: Two IRs — evidence in, semantics out, joined before graphing

Date: 2026-08-14
Status: accepted

Milestone V2.M2. Amends architecture v2 §3.1/§3.2/§3.4 on the division of
labour between the lanes, and supersedes the post-hoc edge merge added
earlier in M2 (`scipsource.merge_lane`).

## Context

M2's first cut joined the lanes **after** lane A had already built a graph:
lane A produced `calls` edges, lane B produced `references` edges, and a
merge upgraded any edge both had produced. Measuring it surfaced the
problem the architecture had not anticipated.

**SCIP cannot tell a call from a reference.** Occurrences carry a
`syntax_kind` that would separate `IdentifierFunction` from
`IdentifierType`, and `scip-python` populates it for **0 of 8,575**
occurrences — every one is `UnspecifiedSyntaxKind`. So lane B's symbol
edges include `except StampError:` clauses and type annotations alongside
real calls: 1,422 lane-B symbol edges against lane A's 1,029, a 38%
difference that is a *different question being answered*, not extra
precision.

That breaks §3.1's plan for M3. "Lane A no longer attempts symbol
resolution — that duty moves entirely to lane B" assumed lane B could
answer everything lane A could. It cannot answer *is this a call*, so
stripping lane A would lose the call graph rather than upgrade it, and
`who_calls` — an MCP tool agents use — would silently become
`who_references`.

Three options were put to Max: lane A keeps call resolution; drop the call
graph; or **intersect** the two. He chose the third, with the structural
refinement this ADR records.

## Decision

### Each provider answers only what it can know

- **tree-sitter is the syntax provider.** It knows a call site *is a call*,
  where it starts and ends, and what scope encloses it. It does **not**
  resolve the callee.
- **SCIP is the semantic provider.** It knows what an occurrence resolves
  to and where that is defined. It does **not** know what the occurrence
  syntactically *was*.

Neither is a fallback for the other, and neither is asked a question it can
only guess at. This is the split §3.1 was reaching for; it was wrong only
in believing lane B subsumed lane A.

### Two IRs, and the join happens before the graph exists

```
tree-sitter ─┐
             ├─► evidence IR ──(range join)──► semantic IR ──► graph builder
SCIP ────────┘
```

**Evidence IR** — range-anchored observations, each tagged with the
provider that made it. Nothing is resolved and nothing is interpreted; a
record says only "at `file:line:col` I saw *this kind of thing*". Both
providers emit into one shape, which is what makes them joinable at all.

**Semantic IR** — the joined result: facts that carry both a syntactic role
and a resolved target, with the tier that combination earns. The graph
builder consumes this and does no resolution of its own.

Joining *before* graphing rather than merging edges after is the whole
point. A post-hoc merge can only compare edges that already exist, so it
can never produce the one thing wanted here — an edge that is a call
*because* tree-sitter saw a call, and points where it points *because* SCIP
resolved it. That edge has no lane; it has two providers.

### What the join produces, and the tier each earns

| tree-sitter saw | SCIP resolved | result | tier |
|---|---|---|---|
| a call | yes | `calls` edge to the resolved target | `semantic` |
| a call | no | `calls` edge, lane A's own resolution or dropped | `syntactic` |
| — | a reference | `uses` edge | `semantic` |
| an import statement | yes | `imports` edge | `semantic` |
| an import statement | no | `imports` edge, lane A's resolution | `syntactic` |

A call is matched to a resolution by **range containment plus name**: the
SCIP occurrence must sit on the call site's line, and the terminal
descriptor of its moniker must match the callee's last segment. Line alone
is ambiguous when a line holds several references, which is why the
evidence IR carries columns that the first cut discarded.

A resolution no call site claimed becomes a **`uses`** edge rather than
being folded into `calls`. It is a true and useful statement — it is what
an architectural-dependency question wants — and it is not a call. The name
is `uses` and not `references` because ADR-010's Terraform layer already
spends `references` on traversal chains between `tf:` nodes; the collision
was caught by a tier histogram showing two `references/syntactic` edges
that lane B could not have produced.

### What this costs

M3's deletion shrinks. Lane A keeps call-site *detection* and loses call
*resolution*, which is the honest reading of §3.1 rather than its literal
one. §3.1 is amended accordingly in the same commit.

### Coverage, not confidence scores

Max asked whether the hard cases could carry a confidence score — if we
cannot say *what* a call on a returned object hits, could we say a function
*likely* calls one? **No, and the reason is worth stating.** An edge with no
named target cannot be drawn, cannot be checked against an invariant, and
cannot be cited at a `file:line`. It is the false edge ADR-007 rules out,
wearing a probability. Tiers already carry confidence for edges that
*exist*; nothing is gained by inventing edges to attach a tier to.

What the question did expose is a real gap. Of this repo's 3,070 call
sites, **1,411 resolve in-repo, 1,256 resolve to an external package, and
403 (13%) resolve to nothing** — and that last number was invisible. The
graph said "here are the calls" without ever saying "and there were 403
sites I could not account for," which is P6 unmet for lane B.

So the honest form of the idea is a **denominator, not a score**:
per-file resolution coverage — sites, resolved, external, unaccounted.
Counts, no guesses. It gives the reviewer flow a legitimate signal
(`review.py`'s call graph is 56% accounted; trust it less than
`policy.py`'s at 100%) without a single invented edge, and it is what
makes the gap fixable rather than merely absent.

The remaining unaccounted are dominated by builtins (`len`, `isinstance`,
`any`) and by dynamically-typed test fixtures (`capsys.readouterr`,
`monkeypatch.setenv`) — objects whose type Pyright cannot know at the call
site. That is a genuine limit of static semantics, recorded here rather
than papered over.

## Alternatives considered

- **Lane A keeps resolving calls, lane B is additive.** Simple, and leaves
  two disagreeing answers to the same question with no way to prefer one.
- **Drop the call graph; `references` is the symbol layer.** Cleanest
  architecturally and worst for the agent tools, which ask call questions
  because that is what a reviewer asks.
- **Infer callness from SCIP alone** — e.g. treat a reference to a
  method-descriptor symbol as a call. Rejected: it would count a function
  passed as a value, or named in a type annotation, as a call. Guessing
  what `syntax_kind` would have said is exactly the false edge ADR-007
  forbids.
- **Ask scip-python to populate `syntax_kind`.** Upstream work with no
  timeline, and Hobbes writes no provider adapters (§3.2).

## Consequences

- The graph builder stops resolving anything and becomes a projection of
  the semantic IR — smaller, and testable on IR fixtures rather than on
  parsed source.
- The lane-agreement self-test (§3.4, V2.M3) gets richer: it can compare
  *resolutions* for the same syntactic site, not merely edge sets.
- A third provider — `scip-go`, a coverage tracer for the `dynamic` tier —
  joins by emitting evidence IR, with no change to the builder. That is P7
  applied one level lower than §3.7 states it.
- `merge_lane` is superseded and removed; its tests move to the join.
