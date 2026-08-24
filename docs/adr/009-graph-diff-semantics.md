# ADR 009: Graph diff semantics and ref extraction

Date: 2026-08-10
Status: accepted

## Context

M2's deliverable is the review artifact the whole project exists for:
*"this PR adds billing → auth-internal edge"*. Architecture §4.1 defines
graph diff as `graph(base)` vs `graph(head)`; what identity means for nodes
and edges, how to obtain graphs for arbitrary refs, and the CLI contract
need fixing.

## Decision

**Identity and delta.** Nodes are identified by `id`; edges by
`(from, to, type)`. The delta is four set differences: nodes added/removed,
edges added/removed — computed for both the module layer and the symbol
layer. **Evidence changes are not architectural changes**: an import moving
from line 12 to line 30 produces no delta entry. Added edges carry head's
evidence, removed edges carry base's — the reviewer gets a `file:line` to
look at either way. A node kind change (module ↔ package) keeps the node's
identity and is not reported; the edges tell the real story.

**Ref extraction.** `graph(ref)` is produced by `git archive <ref>`
unpacked into a scratch directory and fed to `extract_repo` — which is pure
(no git, no writes), so this needs no worktree bookkeeping and never
touches the user's checkout. The cost is a full extraction per side per
diff; acceptable until proven otherwise (extraction of this repo takes well
under a second).

**CLI contract.** `hobbes diff <base>..<head> [--repo DIR] [--json]`;
a bare `<base>` means `<base>..HEAD`; three-dot ranges are rejected (git's
symmetric-difference semantics don't apply to graph comparison). Human
output prints the module-level delta line by line (`+`/`-`, type, edge,
evidence) and summarizes the symbol layer as counts; `--json` emits the
full delta. **Exit codes mirror diff(1): 0 no differences, 1 differences
found, 2 trouble.**

## Alternatives considered

- **git worktree per side** — works, but leaves state to clean up on
  crashes; `git archive` to a TemporaryDirectory cannot leak repo state.
- **Committing derived/ so diffs are file diffs** — rejected back in §10;
  derived artifacts stay regenerable, so the diff regenerates them.
- **Reporting evidence-only changes as "changed" edges** — floods the
  delta with line-number churn, exactly the noise concept-level review
  exists to remove.
- **Symbol-layer detail in the human output** — module-level is the review
  altitude (§4.1); counts keep the layer visible without drowning it.

## Consequences

- `hobbes diff` works on any two committed refs with no side effects on
  the checkout; uncommitted changes are invisible to it (commit first, or
  a future `--worktree` mode could extract the live tree if that proves
  needed).
- Exit code 1 for "delta exists" makes CI gating trivial
  (`hobbes diff origin/main..HEAD && echo unchanged`).
- The M7/M8 consumers get the same delta via `--json` — no second diff
  implementation.
