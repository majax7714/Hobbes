# ADR-119 — The ingest says where its time went

**Date:** 2026-09-16 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-16 ("proceed with the proxy and timing block"), on the top-level review's second recommendation.

Amends architecture **§3.6** (incrementality) with the measurement it
lacked. Changes no artifact.

## Context

Nothing in the pipeline was timed. The ScummVM ingest was known to take
8 min 57 s end to end (ADR-116) and nothing said which step; the
review's speed items — a lane B index cache, a lane A file cache,
parallel walks — could not be measured before or after. C-35's own
rule is that a number nobody measured is a guess, and the pipeline's
clock was one.

## Decision

**1. Every step is timed, in run order.** `extract_repo` records each
language's lane A walk, the packs, the lane A sites, each lane B index
run (`lane B [python]`, `lane B [go]`, …), the join, the projection,
the lane agreement, the tail, the test map, the fixture trees, and the
write, each as a name and its seconds (`extract/timings.py`,
`Timings.step`). A step that raises is still recorded.

**2. Never in an artifact.** Two ingests of one commit are
byte-identical (P1, `test_emit`), and a duration is a fact about the
box, not the repo. `graph.json` carries no timings, and the test says
so.

**3. Printed, and logged under the Hobbes cache.** The ingest summary
prints the total and every step. `hobbes ingest` appends one JSON line
per run — repo, SHA, Hobbes version, the time, the total, the steps —
to `~/.hobbes/cache/timings/<key>.jsonl`, keyed by the repo's path, and
prints the log's path, so a before-and-after is two lines of one file.

## Alternatives considered

- **Timings in `graph.json` under a key consumers ignore.** Rejected:
  the artifact would differ between two ingests of one commit, and the
  byte-identical checks the evidence log leans on would have to learn
  an exception.
- **A `--timings` flag, off by default.** Rejected: a measurement that
  is not taken is not there when the question comes; the print is a
  dozen lines and the log costs one append.
- **A profiler.** The question is which of a dozen steps is slow, not
  which function; a profile is the next tool once a step is named.

## Consequences

- The summary grows by one block. The log is outside the repo and
  outside `derived/`, under the cache root every test already redirects.
- `Timings` is an optional argument on `extract_repo`, `ingest` and the
  symbol-layer helpers; a caller that passes none gets a record that is
  dropped, so the bench's `ingest(workspace)` is unchanged.
- The step names are the summary's contract; a rename is a change to
  what the layer says and moves the patch number.
