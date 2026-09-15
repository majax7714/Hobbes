# ADR-115 — Lane B's decode streams the index

**Date:** 2026-09-15 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-15, on C-150's assessment ("streaming decode is best route, proceed with the fix"), after the routes were put to him with the measurement below.

Amends **ADR-027** (the helper's decode: how the index is read) and
**ADR-109**'s decision 1 as amended at 0.2.21-beta (the per-unit merge
and its size guard). Narrows **C-150** and rewords **C-149**'s reason.

## Context

C-150 was registered at 0.2.21-beta: the helper decoded a root's whole
SCIP index in memory, under Node's default heap, and a root whose index
outgrew it had no lane B. Measured on ScummVM (5,958 translation units,
one whole-database run under C-149's guard): a 387 MB index needed
8.95 GB to decode, the helper died with V8's allocation failure (exit
139), and 1.53 million C++ call sites fell to lane A. Max's decision
that day was to assess the memory problem as a whole before building
anything.

The assessment (2026-09-15, this ADR's session) measured where the
memory goes. The helper read the index through
`scip.Index.deserialize`, the generated google-protobuf class borrowed
from scip-typescript, which builds one message object, its wrapper
arrays and a fresh copy of the symbol string for every occurrence.
The decode itself reads three fields of an occurrence and one of a
document, one document at a time, in two passes. A probe that walked
the same file's wire format document by document, keeping only those
fields, read every one of its 7.9 million occurrences in 3.3 s at
1.44 GB peak resident, most of it the reference rows kept.

| Path, ScummVM's whole index (387 MB, 11,265 documents) | Peak | Time |
|---|---|---|
| Generated reader, then decode, at a 14 GB heap (0.2.21-beta's measurement: 8.95 GB, 22 s) | 9.7 GB resident | 38 s |
| Stream probe, every reference row kept as a flat record | 1.44 GB resident | 3.3 s |
| **This ADR: streamed read, then the full decode, default heap** | **3.4 GB resident (2.73 GB heap)** | 33 s |

The image's Node (22.14.0) has a default heap of 4.35 GB. Under the
old reader the heap, not the data, was the wall.

Two more facts shaped the decision:

- **The Python side is a second wall,** further out. The decode's
  facts for ScummVM are 4.16 million references, which `run_helper`
  receives as one JSON document on stdout (about 850 MB) and parses
  into dicts (393 bytes a row, measured: about 2.1 GB), on top of lane
  A's 1.5 GB. That is a separate change (a facts format the Python
  side can read as it arrives) and a separate decision.
- **A killed helper said the wrong thing.** The out-of-memory record
  of 0.2.21-beta keys on V8's heap markers in stderr. A helper the
  kernel's OOM killer or a container's memory limit ends carries none
  — podman reports 137, a host run -9 — and the record fell back to
  "install Node", the wording C-150 was registered to correct.

## Decision

**1. The helper reads SCIP's wire format itself, one document at a
time.** `streamDocuments(bytes)` walks `Index.documents` (field 2) with
google-protobuf's `BinaryReader`, materialising a document — its
`relative_path` (1) and its occurrences' `range` (1), `symbol` (2) and
`symbol_roles` (3) — only while the decode is looking at it. The typed
ranges scip-java writes (fields 8 and 9, the 2026-08-25 proto) are read
here too, folded into the `[startLine, startChar, endLine, endChar]`
shape as before, a typed range winning over a deprecated one; the
monkeypatch that taught the generated reader those fields goes with
the generated reader. An unpacked `range` (one varint per element)
reads the same as a packed one.

**2. `decode` walks its source afresh for each of its two passes.** An
index source is either the literal `{documents: [...]}` the tests
build or a streamed one whose `documents` is a generator function;
`documentsOf` and `documentCount` tell them apart, and nothing else in
the decode changed. `indexFiles(paths)` is the streamed source over a
root's `.scip` files, read one file at a time in path order;
`mergeUnitIndexes` is the same over any sources. The files stay on
disk until the decode is done, and are removed then, as ADR-027's
clause 6 requires.

**3. A unit's output is told usable by a top-level walk, not by
deserialising it.** `wellFormedIndex` skips every top-level field of
the bytes and asks that there was at least one; a scip-clang run that
wrote nothing, or a truncated file, fails it and is counted as a failed
unit as before (C-149's record). A whole-database output that fails it
is "could not read the SCIP index the indexer wrote", as before.

**4. The size guard stays, for a different reason.** `PER_UNIT_MAX`
was set on the merge's memory (about 84 GB projected for ScummVM's
5,958 units), and that cost is gone. What the per-unit route still
holds is every reference of a header once per unit that includes it,
until the per-site rules run at the end of the decode — ScummVM's
units wrote 9.36 GB of indexes against 370 MB whole, and took 207 s
against 143 s. Lifting the bound is the per-site rules applied as
references arrive. Not built; C-149's *Direction* says so.

**5. A killed helper says so.** `run_helper` treats exit 137 and -9 as
the helper killed decoding the index, names the kernel's OOM killer
and a container's memory limit as the likely hands, and names C-150.
The heap-marker branch stays for the case it was written for.

**6. The facts are unchanged, so the helper version is not moved.**
The streamed decode of ScummVM's index and the generated reader's
produce the same definitions, references, external rows, packages,
ambiguity sets and degradation records, checked by digest over every
row (this ADR's session). `HELPER_VERSION` stays 3.

## Alternatives considered

- **A heap sized from the box** (`--max-old-space-size` read from
  `/proc/meminfo`). Machine-dependent: ScummVM would fit on this box
  and swap a 16 GB one, and the constraint would read "depends on your
  machine". Rejected; the override `HOBBES_SCIP_CMD` already carries a
  heap flag through the container for anyone who needs it today, and
  C-150's entry now says so.
- **A leaner generated reader** (protobufjs, or `toObject` once).
  Still holds the whole index; a constant-factor gain against a wall
  that scales with the repo. Rejected.
- **Streaming the facts to the Python side** (line-delimited JSON on a
  file under the stage, read as it arrives). The right next step for
  the second wall, and a facts-format change (helper version 4) with
  its own join work. Deferred to its own decision.

## Consequences

- A root whose index outgrew Node's heap has lane B; ScummVM's decodes
  under the default heap at 2.7 GB. C-150 is narrowed to what is left:
  the Python side's memory for a root of that size, and the helper's
  own memory for the references it keeps, which is bounded by the
  facts rather than by the index.
- C-149's reason changes from the merge's memory to the references the
  per-unit route holds and the disk and time it spends; its bound and
  record are unchanged.
- The helper owns its whole SCIP read. The generated `scip.js` module
  is still imported for `SymbolRole` and by the indexers' own code,
  never to deserialise an index.
- Node tests: 74 (the typed-range test now goes through the reader;
  three tests for the streamed decode's equality with a literal one,
  the file source's order and count, and the well-formedness check).
  pytest: one test for the killed helper.
- Version: 0.2.25-beta — a change to what the layer draws (a root that
  had no lane B has it) and says (the killed-helper record). A
  constraint's fix is a patch (ADR-103's notes).
