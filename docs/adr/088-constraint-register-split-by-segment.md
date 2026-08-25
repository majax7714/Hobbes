# ADR-088 — The constraint register is a folder, one file per segment; lifted entries live with their segment

**Date:** 2026-08-25 · **Status:** accepted · **Amends:** ADR-043

## Context

`docs/constraints.md` had grown to ~1,800 lines and 57 entries. ADR-043
split it into Active / Lifted / Superseded parts, which kept the
mechanism-of-the-lift documented but put every lifted entry in one
chronological pile at the end of the file. A reader working on extraction
had to scroll the derivation and benchmark entries to reach the Go
section, and had to read every lift to learn which lifts were
extraction's.

## Decision

1. The register is the folder `docs/constraints/`. `README.md` holds the
   rules (P8/P9, the entry formats, surfacing statuses), an index table
   of segment files with the `C-n` each holds, and the debt summary.
   Each subsystem segment that was a `##` heading in the old file is now
   one file with the same title.
2. **Lifted and superseded entries sit at the bottom of the segment they
   belonged to**, under a marked "Lifted constraints in this segment" /
   "Superseded constraints in this segment" heading, in their unchanged
   format. Knowing a lift is extraction-specific is more useful to a
   developer than reading every lift; the segment is where a user met
   the limit, before and after.
3. Nothing else changes: numbers are stable and never reused, every
   concession still lands as a `C-n` in the same commit — now in the
   segment file — and the debt summary's counts are unchanged
   (57: 48 active, 7 lifted, 2 superseded).

## Consequences

- Links to `docs/constraints.md` were repointed to
  `docs/constraints/README.md` across the docs and ADRs (old BUILDLOG
  entries are left as written, per the append-only rule).
- `list_blind_spots` and the rest of the tree do not read the file; no
  code moved.
- Adding a segment means adding a file and an index row.
