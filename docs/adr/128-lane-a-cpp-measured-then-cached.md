# ADR-128 — Lane A's C++ walk made exact-faster, then cached per file; the trusted stores read-only in every container

**Date:** 2026-09-17 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-17 ("proceed with the file cache for lane a"), the 2026-09-16 top-level review's speed item, measured first with the timing block (ADR-119).

Amends architecture **§3.6**, and ADR-092 §3 (the mounts). Changes no
artifact: every measurement below compares the extraction's JSON byte
for byte.

## Context — measured before deciding

**Where lane A's time is.** The timing logs of every repo ingested since
ADR-119 put lane A at 3.4 s on this repo (of 8.5 s), 1.2 s on fmt, 1.1 s
on jsoup, 2.0 s on quic-go: no language's lane A passes 2 s. The repo a
file cache is for is a large one, and ScummVM's only ingest predates the
timing block. Timed now with lane B off and nothing written
(`~/.hobbes/bench/laneA-cache/`): **lane A 258 s, of which C++ 242 s**;
every other language under 2 s.

**Where C++'s time is.** Wall time per top-level function (a sampling
profiler is not on the box; cProfile's per-call overhead inflates
call-heavy functions): per-file work in `cppsource._parse_file` 130 s —
tree-sitter's own parse about 21 s, the declaration walk, the call
walk, the string-test scan — and the cross-file work (the claim, the
join, the fallback) about 28 s. cProfile named two defects of shape:
- `csource._resolve_include`'s third step scans every repo header with
  `endswith` for every include: 262,159 includes × ~10k headers, 1.65
  billion `endswith` calls on ScummVM (also reached through
  `_claim_headers`).
- `csource._walk` is a recursive generator: every node is re-yielded
  through each ancestor's `yield from`, 2.06 billion calls.

**Three exact changes, tried as a driver's patches** (not the tree):
- `_walk` as an explicit stack in the same pre-order;
- the suffix step through an index by basename, filtered by the same
  `endswith` — the same candidate set, so the same ambiguity;
- `_scan_string_tests` skipped when no macro name in
  `_STRING_TEST_MACROS` occurs in the file's bytes (an identifier node's
  text is a substring of the source, so the walk could find none).

The extraction (graph, tests, interfaces; 217 MB of JSON) is
**byte-identical** to the tree's: C++ 242 s → 141 s, lane A 261 s → 161 s.

**A per-file cache, prototyped.** `_parse_file(rel, source)` returns
plain data (strings, ints, lists, dicts, tuples, sets) and reads nothing
but its two arguments and the pipeline's code, so it is a pure function
of them. A JSON store keyed on those, every record asserted to decode
back to an equal object on write: cold 156 s (the assertion included),
**warm 22 s, lane A 41 s**, both byte-identical to the tree's; 19,948
records, 289 MB. The first prototype's plain JSON turned a tuple inside
a symbol dict (`qualifiers`) into a list and the assertion caught it on
the first file; the encoding tags tuples and sets.

**Found while placing the store.** `containment.plan` mounts the whole
cache root read-write into every contained step, including the steps
that execute repo code (`containment.PROFILES`: Java's resolve and
index passes, rust-analyzer's export, C and C++'s compile-database
derivation, the venv listing). ADR-122's index store is under
that root, so repo code could write a facts file that a later ingest
reads as lane B's answer — the key is a hash of inputs an attacker can
know. No container step writes that store; the host copies into it
after the run. The register records what repo code can *read* there
(`extraction-java.md`), not what it can *write*.

## Decision

**1. Contain first: the trusted stores ride read-only in every step.**
`containment.plan` lays `<cache>/index` and `<cache>/lanea` read-only
over the cache root's rw mount in every plan, creating them first
(the existing `ro_cache` mechanism binds only existing directories). The
host writes both; no step needs to. A test holds it at the plan, and one
live test through the image shows a write there fails.

**2. Surface the rest.** The tool caches (cargo, Go's module and build
caches, Maven, Gradle, npm) and the stage directory stay writable — the
fetch and index passes write them by design — and are read by later
ingests of other repos. When any step that executes repo code ran, the
ingest prints one `NOTE:` naming that and **C-161**. Registered
*surfaced*.

**3. The three exact changes above**, in `csource` and `cppsource`, each
with a test that pins its equivalence to the old rule on constructed
cases (order of the walk; ambiguity and directory specs of the suffix
step; a `TEST_CASE` that must still be found).

**4. C++ lane A reads an unchanged file from a per-file cache.**
- Wraps `_parse_file` only. The claim, the join and the fallback are
  cross-file and always run.
- **Key:** sha256 over a format tag, the code fingerprint — the name and
  bytes of every `hobbes/extract/*.py`, and the installed versions of
  `tree-sitter` and `tree-sitter-cpp` — then the repo-relative path and
  the file's bytes. Any change to the extraction code misses everywhere.
- **Record:** JSON, tuples and sets tagged, decoded into `CppFile`.
  **Never pickle:** a store under a directory other processes can reach
  must hold data, not code. A record that does not decode is dropped and
  the file parsed.
- **Store:** `<cache>/lanea/cpp/<2 hex>/<key>.json`, written `.partial`
  then renamed; a hit touches it; an entry untouched for 30 days is
  swept once per process at the first write.
- `HOBBES_LANEA_CACHE=0` parses every file afresh. The summary prints
  hits and misses under the timings, and the timings log line carries
  them. Nothing enters an artifact.
- **Only C++.** Every other language's lane A is under 2 s on every
  timed repo; a cache there is a cost with nothing to buy.
- The residual is **C-160** (surfaced by the summary line): the
  fingerprint does not see a native grammar rebuilt at the same version,
  or code outside `hobbes/extract/` that `_parse_file` would come to
  reach (none today).

**Order:** 1–2 as one unit, 3, then 4. Version 0.2.40-beta.

## Consequences

- On ScummVM, lane A 261 s → about 161 s on every ingest, about 41 s on
  one whose C++ files are unchanged (driver numbers; the built ones are
  recorded after the build).
- A second store under the cache root, 289 MB on ScummVM, swept after
  30 days unused.
- ADR-122's store stops being writable by repo code; the tool caches'
  exposure is written down and said at the run.

## Alternatives considered

- **Only the cache.** Rejected: it hides a quadratic include resolution
  and a generator walk behind a warm store; the first ingest of every
  repo, and every ingest after a pipeline change, pays them.
- **Pickle the records.** Rejected above.
- **The lane A store outside the cache root.** Declined: a
  `HOBBES_CACHE_DIR` override would need a second one; the read-only
  layer gives the same property and fixes ADR-122's store with it.
- **A cache for every language's lane A.** Rejected on the numbers.
- **A process pool for lane A.** Not taken here; measure after this.
