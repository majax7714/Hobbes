# ADR-118 — The knowledge store decodes an artifact once per version of its file

**Date:** 2026-09-16 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-16 ("proceed with the proxy"), on the top-level review's first recommendation.

Amends **ADR-017** (the knowledge tools) and **ADR-087** (the host
serve) in one respect: how an answer reaches the artifact. Changes no
answer. Architecture §4 amended.

## Context

`internal/knowledge.Store` held only the repo root. Every tool call —
`graph_neighborhood`, `who_calls`, `tests_guarding`, `list_blind_spots`
— read `graph.json` from disk, version-checked it, decoded the whole
document, and then scanned every edge for the ones touching the
question. On this repo that is an 8 MB decode per answer. On ScummVM,
whose artifact is 980 MB (C-150), a knowledge server is unusable: each
answer would decode a gigabyte. The serve is a long-lived process
(`hobbes-proxy serve`, the session's and the host's), so the cost was
paid on every question an agent asked.

The reason it was written that way was honesty about staleness (P1): a
re-ingest must be seen by the next answer, never a stale document
served from memory.

## Decision

**1. Decode once per version of the file.** The store keeps the decoded
`graph.json` and `tests.json` with each file's size and modification
time. Every call stats the file (one syscall) and compares both; a
change reloads, an unchanged file is served from memory. An ingest
rewrites the file, which moves its modification time.

**2. A missing file is never served from memory.** If the stat fails,
the cached document is dropped and the answer is the same error as
before: run `hobbes ingest`. An artifact that has gone is gone.

**3. Index by endpoint, keep the artifact's order.** The decoded graph
carries an index: module edges by `from` and by `to`, symbol edges by
`to`, nodes and symbols by id — positions into the document's own
slices, so an answer lists edges in the order the scan listed them.
Answers are byte-identical to the scan's; the suite that held the scan
holds the index.

**4. The staleness header is unchanged.** Every answer still opens with
the ingest SHA and asks git for HEAD, so a stale artifact warns as it
did.

## Alternatives considered

- **Hash the file on every call.** Exact, but reading 980 MB to hash
  it per answer is most of the cost being removed. Size and mtime
  detect every rewrite an ingest makes; the residue is a rewrite that
  lands in the same nanosecond with the same size, which no ingest
  produces.
- **Watch the file (inotify).** A dependency the product binaries do
  not carry (`yaml.v3` and the MCP SDK are the only two), and a watch
  cannot see through the read-only mount the knowledge container uses
  as reliably as a stat.
- **Load at start, never reload.** Rejected: a session that re-ingests
  mid-way would be answered from the old graph and nothing would say so
  — the fake-honest shape (P8).

## Consequences

- `who_calls` on a large graph is a map lookup after the first answer;
  the first answer pays the decode once.
- The store holds one decoded graph in memory for the life of the
  serve. On ScummVM that is the artifact's decoded size; the decode
  used to be paid and freed per call, so the peak is unchanged and the
  steady state is higher. The artifact's own size is C-150's remainder
  and the review's memory item, not this ADR's.
- `readArtifact` is a package variable so a test can count reads; the
  two tests are `TestArtifactsDecodeOncePerFileVersion` and
  `TestARemovedArtifactIsNotServedFromMemory`.
- The image must be rebuilt and the knowledge server restarted for the
  change to reach `.mcp.json`'s serve (C-65).
