# ADR-035 — Enrichment packs: registered in code, activated by detection

**Status:** accepted (2026-08-15)

**Milestone:** V2.M4. Implements the architecture's §3.5 and answers the
`hobbes.yaml` question §3.7 left open. Amends §3.5 and §3.7.

## Context

§3.5 makes packs the plugin surface symmetric with indexers: framework-aware
passes that add typed edges and domain joins on top of what SCIP and
tree-sitter produce. Three bodies of framework knowledge exist and are meant
to become packs — FastAPI/Flask routes and CLI entry points
(`extract/interfaces.py`), Express/Nest routes (`tsextract/extract.mjs`),
and the Terraform cross-layer join (`extract/terraform.py`, 372 lines and
the most hand-verified code in the extractor).

The plan said the registry lives in `hobbes.yaml`, and flagged the problem
in the same sentence: **ADR-012 gitignores the whole `.hobbes/` directory in
target repos**, while a pack registry describes the *repo*, not one person's
box. The build plan called that "a genuine tension, not a detail" and
required this ADR before the file exists.

There is a precedent that was not available when the plan was written. The
**indexer** config was going to be authored in the same file, and ADR-027's
amendment made it **derived** instead — stage path, TS zone, declared
dependencies and pinned project version are all facts Hobbes can already
see, and asking a human to restate them is an invitation to state them
wrong.

## Decision

**There is no `hobbes.yaml`.** Packs are registered **in code** and
activated **by detection**.

- The registry is a tuple of `Pack` values in
  `hobbes/extract/packs/__init__.py` — the same shape as `INDEXERS` in
  `scip/index.mjs`.
- Each pack answers `applies(ctx)` from the repo itself: the Python HTTP
  pack applies when a module imports `fastapi` or `flask`, the Terraform
  pack when the repo contains `.tf` files, the TS HTTP pack when the TS
  layer produced route rows.
- `graph.json` grows a `packs` list naming what ran, so the layer is
  attributable in the artifact rather than only in the code.

**The ADR-012 tension dissolves rather than being resolved.** Nothing new is
authored, so nothing new has to be tracked or gitignored, and a fresh clone
of a repo gets the same packs as the machine that ingested it last — which
an untracked registry could not have promised.

**A pack is an adapter over the existing implementation, not a rewrite.**
`terraform.py` and `interfaces.py` keep their code; the packs are the only
path by which their output reaches the artifacts. 372 lines of hand-verified
Terraform behaviour — including the private-repo-A `packages` edge checked by hand
at `infra-core/lambda.tf:5` — get a new caller, not a new implementation.
Rewriting them would risk the one thing this milestone must not break for a
structural change that no user can observe.

**Route *detection* for TypeScript stays in the Node helper.** Express's
receiver check needs the ts-morph AST (`expressReceiverOk`), so moving it
into Python would mean losing it. The TS HTTP pack **claims** the helper's
route rows and declares their tier; the helper produces them. Stated plainly
because it is the one place where a pack does not contain its own detection.

**Packs declare the tier their edges carry**, per §3.5. All four declare
`syntactic`: every one of them reads structure — a decorator, a block, a
string literal — and none has a semantic provider behind it. A pack that
promoted an edge on SCIP-proven evidence could declare `semantic`, and none
does today.

**No schema bump.** `packs` is a provenance list; it changes how no existing
field is read, so a v4 consumer that ignores unknown keys stays correct.
ADR-028 bumped to v4 because `tier` changed what an edge *means* — this
does not, and inventing v5 for an additive provenance field would make the
version gate noisier without making any consumer safer.

## Consequences

- **The exit criterion is testable, and is a test.** `extract_repo` takes a
  `packs=` argument, so the suite runs an extraction with a pack and without
  it and asserts the difference is exactly that pack's contribution, and
  that adding it back reproduces the artifact byte-for-byte. The property is
  not asserted in prose anywhere.
- **A pack cannot be turned off for a repo where it misfires.** Registered
  as **C-25**. Surfacing is partial: `graph.json`'s `packs` list tells you
  what ran, so a wrong edge is attributable even though it is not
  suppressible. A per-repo disable is a real need the moment someone hits
  it, and it will want a home that is *not* `.hobbes/` if it is to survive a
  clone — which is the ADR-012 question deferred, not answered.
- **Third-party packs are not a thing.** No entry-point loading, no plugin
  discovery, no ABI. Building a loader for packs nobody has written is the
  speculative abstraction the conventions forbid; the registry is one tuple,
  and a fourth-party pack is a pull request until someone needs otherwise.
- **V2.M5's Go pack is the test of this interface.** If adding `net/http`
  route extraction needs anything beyond a new module and a registry entry,
  P7 has failed and this ADR is why.
- `extraction_errors` is now **sorted** rather than left in pipeline order.
  Packs move where errors are appended, and an artifact whose error order
  depends on the order passes happen to run in is not reproducible in the
  sense P1 means. Called out because it changes existing output for any repo
  with more than one error.
