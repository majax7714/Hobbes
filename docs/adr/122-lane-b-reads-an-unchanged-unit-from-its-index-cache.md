# ADR-122 — Lane B reads an unchanged unit from its index cache

**Date:** 2026-09-16 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-16 ("proceed with next hobbes review item"), the top-level review's next speed recommendation after ADR-118 and ADR-119.

Amends architecture **§3.6** (incrementality) with the first cache of an
index. Changes no artifact: an ingest that reads from the cache writes
the bytes an ingest that indexed would have written (P1, measured
below).

## Context

The timing block (ADR-119) said where this repo's ingest went: 53–54 s,
of which lane B was 48.6 s, run one language after another, and
python's index alone 26 s. Measured one level down before this decision
(the driver is in the BUILDLOG): python's 26 s is the index container
itself — the venv listing is 0.24 s, staging 0.02 s, the decode of the
facts file 0.08 s — and go's 3.3 s is eight modules at a 0.13 s fetch
and a 0.2–0.5 s index each. Two runs of the helper over the same stage
write **byte-identical facts files**, for python and for every one of
the eight Go modules.

The review had said "a lane B index cache keyed by the stage key,
which is already a content hash". It is not: `staging.stage_key` folds
in each file's size and mtime, not its bytes, because its job is to
name a tree so removal is idempotent, and a stat costs no read. A cache
keyed on it would reuse an index across an edit that kept a file's size
inside one mtime tick — rare, and exactly the kind of wrong answer a
graph must never serve (accuracy first).

## Decision

**1. The unit is the grain; the helper's boundary is the place.** The
cache sits in `run_helper`, the one function every language's every
indexing unit passes through, so six languages get it from one hook
and no per-language extractor learns a second code path. What is
stored is the helper's own facts file (ADR-116), under
`<cache>/index/<key>.facts.ndjson`, copied there after the reader has
validated it (the trailer's counts) and only then.

**2. The key is everything the container can see, hashed by
content.** In order: the helper (`scip/index.mjs` and its lockfile —
the indexers under its `node_modules` are pinned by the lock, the
binaries by the image), the image's id, the config with the stage's
own path tokenised and the run-local `facts` path dropped, every
sidecar file the config names under the cache by its bytes (the venv
listing; a rebased compile database), the stage tree file by file, a
symlink by its target and the target's fingerprint (below), the
read-only mounts, and the step's environment. The `root` a caller
passes is not an input: the file holds stage-relative paths and the
root goes in front at read time, so one entry serves any root. This
holds because of the staging contract (`staging.py`): nothing reaches
the indexer that is not in the stage, a mount, or a lockfile-pinned
fetch.

**3. A hit is read by the same reader.** `read_facts` over the stored
file — the function a miss's file goes through — so a hit's facts are
the miss's facts by construction. A stored file that no longer reads
(short, malformed, another helper version) is dropped and the unit
indexed again; the reader's rule that a short file is never a smaller
answer (ADR-116) is what makes the fallback safe. The containment
ledger takes the index step on a hit exactly as it would on a miss: the
stored run was contained (nothing else is stored), and the artifact's
stamp says where the facts came from — which is true, and keeps the
artifact byte-identical.

**4. Only a contained, successful run is stored.** A run on the host
(no image, or the escape hatch) has an unpinned toolchain and is never
kept; a run that failed has nothing to keep. `HOBBES_INDEX_CACHE=0`
indexes every unit afresh — for a measurement of the uncached lane, and
for a box that wants no store.

**5. Printed and logged, never in an artifact.** The ingest summary
prints one line under the timings — hits, misses, the keys' seconds,
the store's path, the switch — and the timings log line (ADR-119)
carries the same under `index_cache`, so the log says why a lane B
step took what it took. `graph.json` carries nothing of it.

**6. The store is bounded.** A hit touches its entry; an entry
untouched for 30 days, and any `.partial` a killed run left, is swept
at the next write. This repo's store is 15 MB for 19 units.

## Measured

This repo at 0.2.34-beta, the same dirty tree, contained:

| step | uncached | cached |
|---|---:|---:|
| whole ingest | 54.00 s | 8.89 s |
| lane B [python] | 26.15 | 0.44 |
| lane B [typescript] | 4.27 | 0.03 |
| lane B [go] | 2.68 | 0.83 |
| lane B [rust] | 6.84 | 0.50 |
| lane B [java] | 6.98 | 2.26 |
| lane B [c] | 2.27 | 0.02 |
| keys, all 19 units | — | 0.04 |

What a hit still spends is the fetch passes, which run before the
helper: Java's resolve pass (Maven/Gradle over the build files), Go's
`go mod download` per module, Rust's `cargo fetch`, and python's venv
listing. Together 4.1 s here. `graph.json` and `tests.json` from the
cached ingest are byte-identical to a fresh `HOBBES_INDEX_CACHE=0`
ingest of the same tree (sha256 compared).

## Alternatives considered

- **Cache at the language level**, above staging, so the fetch passes
  are skipped too. Rejected: the key would have to re-derive every
  extractor's inputs — which manifests python reads, which tsconfigs a
  zone claims, a Go module's replaced siblings, a C root's build tree —
  a second input discovery beside the first, and the two drift. The
  fetch passes' 4.1 s are measured above; the key is computable before
  a fetch (the stage exists by then), so skipping them is a small
  follow-on if the number warrants it.
- **Key by the stage key.** Rejected above: stat-based.
- **Store the decoded facts** (a pickle of the sites) instead of the
  file. Rejected: a second reader is a second answer; the file is
  read by the one reader and validated by its own trailer.
- **Store the raw `.scip` index** and re-decode. Rejected: the decode
  is the helper's and lives in the container; the facts file is the
  decode's output, smaller, and already checked.
- **Hobbes' own version in the key.** Left out: what produces the file
  is the helper in the image over the stage, and both are in the key; a
  Python-side change that alters a config reaches the key through the
  config. A helper change reaches it through the helper's bytes.

## Consequences

- An unchanged repo re-ingests in the time of lane A plus the fetch
  passes. The first ingest after an image rebuild misses everywhere
  (the id is in the key), by design.
- **C-158 registered:** the key fingerprints a linked dependency tree
  by its target, its top directory's stat and its installer's hidden
  lockfile, and a venv by its listing of distributions, not by their
  files; a manifest with no lockfile keeps the resolution its first
  index saw until the stage changes. Surfaced by the summary line and
  the switch.
- The containment stamp's meaning is stated in `run_helper`'s
  docstring: where lane B's facts came from, which on a hit is the
  stored contained run.
- `indexcache.LEDGER` is reset with containment's per ingest;
  `timings.record` takes the cache's counts as an optional argument, so
  the bench's callers are unchanged.
