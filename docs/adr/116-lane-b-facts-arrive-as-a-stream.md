# ADR-116 — Lane B's facts arrive as a stream, one record per document

**Date:** 2026-09-15 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-15 ("yes proceed with a"), on C-150's remainder, after the routes were put to him with the measurements below.

Amends **ADR-027** (the helper's contract: its output) and **ADR-029**
(the evidence IR's `Site`). Follows **ADR-115**, which deferred this
step to its own decision. Corrects and narrows **C-150**.

## Context

ADR-115 made the helper's decode stream and left the facts it produces
as they were: one JSON document on stdout, read whole by `run_helper`.
It estimated that document for ScummVM at about 850 MB and named the
Python side as the second wall. Measured on ScummVM's cached index
(11,265 documents; 380,108 definitions, 4,158,513 references, 412,155
external references) the same day:

- **The wall is the helper's, and it is hit first.** The facts come to
  699 MB of JSON (the references 582 MB of it). The helper's output
  step is `process.stdout.write(JSON.stringify(facts))`, and V8's
  longest string is 536,870,888 characters in the image's Node 22.14.0
  and the host's 24. `JSON.stringify` throws `RangeError: Invalid
  string length`; the helper exits 1 with that on stderr; `run_helper`
  falls through to its last branch and says "install Node and run `npm
  install`" — the wording C-150 was registered to correct. So at
  0.2.25-beta ScummVM's root still has no lane B, for a reason neither
  C-150 nor the record states.
- **Line-delimited output alone does not move the Python side.** The
  cost is what a row becomes, not how it arrives. Peak resident memory
  reading ScummVM's facts (Python 3.12, facts alone, then through
  `evidence.join` with no lane A sites, so every reference comes out as
  one `Resolved`):

| The Python side's read | Facts | Facts + join |
|---|---|---|
| Today: one document → `str` → dict rows → `Site` | 3.63 GB | 5.71 GB |
| One record per document → today's dict rows → `Site` | 3.65 GB | — |
| One record per document → today's `Site`, no dict rows kept | 2.50 GB | — |
| **One record per document → slotted `Site`, strings interned** | **1.19 GB** | **3.26 GB** |

  The first row is a floor: `containment.run` captures stdout with
  `capture_output=True, text=True`, which also holds the pipe's byte
  chunks while it joins them. 608,347 distinct strings stand behind the
  references' 12.5 million path and name fields.

## Decision

**1. The helper writes its facts to a file, never to stdout.**
`run_helper` names the file in the helper's config (`facts`:
`<stage>.facts.ndjson`, beside `<stage>.config.json`, under the cache
root the container mounts read-write at its host path). The helper
writes it and prints nothing on stdout; `run_helper` reads it and
removes it whatever happens, as it does the config. Stdout is not the
channel because `containment.run` captures it whole; a streaming
capture through podman would be a change to the containment module for
no gain a file does not give.

**2. The file is JSON lines, one record per document (helper version
4).**
- The first line is a header: `{"helper_version": 4, "language": …}`.
- Then one line per document that holds any row:
  `{"file": …, "definitions": […], "references": […],
  "external_refs": […]}`. A row does not repeat the document's `file`.
  Documents come in the order their first row appears in the decode,
  and rows keep the decode's order within a document, so every
  `(file, line)` bucket the join builds holds its sites in the same
  order as before: `match_resolution`'s tie-breaks and
  `join_cross_unit`'s first definition are unchanged.
- The last line is the trailer: `{"end": true, "documents": …,
  "definitions": …, "references": …, "external_refs": …}` counts, and
  the root-level fields the document carried before (`packages`,
  `dependency_coverage`, `degraded`, `units`, `units_failed`,
  `whole_database`, `stderr`).
- A file with no header, a header of another version, no trailer, or
  counts that disagree with the rows read is a `ScipError` that says
  which: a helper killed mid-write leaves a file that parses line by
  line and is short, and a short file must never read as a smaller
  answer.

No line is ever the whole index: the longest on ScummVM is 5.3 MB (one
document's rows). The helper builds one line at a time from the decode
it already holds.

**3. The Python side reads the file as it arrives, into the shapes the
join keeps.**
- A reference becomes an evidence-IR resolution `Site` on arrival; no
  dict row is kept. `facts["references"]` is those sites, and
  `resolution_sites` goes.
- Definitions and external references stay dict rows, with `file` set
  from their document. They are a tenth of the references (ScummVM:
  792,263 together), and `join_cross_unit` needs every unit's before it
  can join any.
- Every path and name read is interned through one table per read, so
  a file path is one string however many rows name it.
- A root's paths are rebased as they are read (`run_helper`'s `root`),
  not rewritten afterwards; `_rebase` keeps the degradation records'
  rule, which is unchanged.
- `join_cross_unit` appends the references it joins as sites.

**4. `Site` is a slotted dataclass.** It is frozen already and nothing
reads its `__dict__`; slots take the per-instance dictionary off every
site, lane A's call sites included (ScummVM's 1.53 million C++ sites
among them).

## Alternatives considered

- **The same records on stdout.** `containment.run` would still hold
  them as one string; the gain would need a streaming capture through
  podman. Rejected for the file.
- **The records read into today's dict rows** (the literal form of
  the offered route). Clears the helper's wall; the Python side is
  unchanged (3.65 GB against 3.63). Rejected: it pays the format change
  and keeps the cost.
- **A join that streams by file**, never holding every reference. The
  pass that raises unclaimed resolutions as `uses` and the lane
  agreement both read every reference; a restructure of the join, to
  save on the part this ADR brings to 1.19 GB. Rejected.
- **A binary or columnar format** (MessagePack, Arrow). A new
  dependency on both sides, facts no longer readable by eye, for a
  constant factor the interning already takes. Rejected.
- **A slotted `Resolved`, its evidence line derived instead of stored.**
  The join's own output is the next wall (about 2.1 GB of the 3.26 GB
  above) and lane A's 1.5 GB sits beside it. Deferred until an
  end-to-end ScummVM ingest on this ADR says where the peak is.

## Consequences

- A root whose facts outgrow V8's string has lane B; ScummVM's facts
  are read at 1.19 GB instead of not at all. The "install Node" record
  for this case is gone with the case.
- C-150 is corrected (the wall at 0.2.25-beta was the helper's output
  string, and its record read "install Node") and narrowed to what is
  left: the helper's own references until its per-site rules run, the
  join's output, and lane A's sites, for a root of ScummVM's size.
- `HELPER_VERSION` is 4 on both sides; a helper of another version is
  refused as before (ADR-027 Decision 5), by the header line.
- Version: 0.2.26-beta — a constraint's fix, a patch (ADR-103's notes).
- **Measured after the code** (the same day): the helper writes
  ScummVM's facts under the image's default heap at 3.29 GB resident
  (487 MB of lines); `read_facts` holds them at 0.99 GB; every row is
  the one-document form's, per file and in order; this repo's graph is
  identical under the old code and the new. ScummVM end to end: exit 0
  in 8 min 57 s at a 7.72 GB peak on the Python side, with lane B for
  the first time (941,498 semantic symbol edges). The peak is lane A,
  the read and the join, then the graph built from them — the last
  alternative above takes part of it, not all.
