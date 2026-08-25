# The system's own claims

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-31 — "Supported" is a verified sample, not the language
- **Cannot tell you:** that ingesting *your* repo in a supported language
  will hold to the accuracy measured on the repos in architecture §3.8.
  The verification base is asymmetric by an order of magnitude: Python
  and TS/JS were proven across multiple repos of different shapes; **Go
  on exactly one repo — this one, a shape its own builders chose**;
  **Rust on one small repo**, 33 hand-checked call edges plus a fixture.
- **Because:** hand-verification is per-repo work, and a language's long
  tail — frameworks, macro styles, build layouts, dynamic idioms — is in
  no sample. The machinery being shared (P7: zero builder lines per
  language) is precisely what lets a thin sample *look* like broad
  coverage: the sixth language ingests as smoothly as the first,
  whatever the graph then misses.
- **Bites at:** the decision to trust a graph on the first repo of a
  shape Hobbes has never seen; every sentence of the form "Hobbes covers
  X".
- **You find out:** **surfaced** (2026-08-21, ADR-053 — the candidate
  surfacing applied). §3.8's table is pinned in
  `extract/verification.py` and stamped into `graph.json` as
  `verification_base`, keyed by the artifact's own language names; the
  test suite reads §3.8 and fails if the two tables drift. Three places
  state it where a language list is read as a capability list: the
  ingest summary prints `verification base: go 1 repo, python 3 repos,
  … — a sample, not the language` directly under the language list and
  spells out every single-repo or unverified row; the surface's
  language badges carry `· N repos` with the §3.8 row as tooltip and
  badge single-repo languages in the stale colour, not as peers; and
  `list_blind_spots` prints the rows before any percentage. A language
  the table does not know is stamped `not verified on any repo`, never
  omitted. **What stays conceded** — and is now the entry's whole
  content: the systematic blind spot a thin sample never exercised
  still degrades nothing at runtime. The surfacing tells you how thin
  the base is; it cannot tell you what the base missed.
- **Source:** ADR-044; the owner's directive, 2026-08-16 — a coverage
  claim beyond its evidence is dishonest even when the machinery behind
  it is proven. Surfacing: ADR-053.

---
