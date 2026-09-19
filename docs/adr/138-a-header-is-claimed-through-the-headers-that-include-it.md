# ADR-138 — A `.h` is claimed through the headers that include it; the `-I` path measured beside it

**Date:** 2026-09-19 · **Status:** accepted (Max, 2026-09-19: "recommended route is good" — route a), with the rule's C side corrected before the brief (*Accepted*), and built (0.2.50-beta; *Built*, below).

Follows ADR-113 §1 (a `.h` is C++'s when a C++ source includes it and no
`.c` source does), ADR-108's 2026-09-14 amendment (C-133's first unit:
the `c-includes` record) and the 2026-09-16 review's item, "the derived
compile database's `-I` path and unit language at lane A (C-133,
C-142)". A build would be a patch: a constraint's fix.

## Context

The item as written was C-133's second unit: read the `-I` directories
from the compile database lane B derives, and use them as a fourth
include step at lane A. It was measured first, and the measurement
found the larger loss next to it, in C-142.

## The measurement (`~/.hobbes/bench/c133-include-path/`, key-free, nothing drawn)

**The graded cells have nothing for `-I` to place.** Their `c-includes`
records, at 0.2.47-beta: cJSON 6 (the vendored Unity examples'
`"ProductionCode.h"`, which cJSON's own build never compiles, and mock
headers that are not in the repo), sqlite-vector 1 (`mingw.h`,
`sqlite_cfg.h`: platform and generated), fmt 1 (four `absl/…` headers,
not vendored), args 1 (`windows.h`). Every one is outside the repo or
outside the database. fmt's path is `include` and `test/gtest`, args's
the root and `test`; lane A's three steps already place everything
those reach.

**ScummVM** (`c54b79a6`; 10,097 `.h`, 10,480 C++ files, **2** `.c`
sources). Its database carries one include path on all 5,958 units:
`.`, `.`, `./engines`. The root is already step 2, so `-I` adds
exactly one directory.

`place.py`, every `#include` in the tree against every C and C++ file:

| | includes |
|---|---:|
| placed by today's three steps | 95,103 |
| angle, no repo candidate (`ext:`) | 1,094 |
| unplaced, and `-I engines` places it | **116** (99 ambiguous, 17 unmatched) |
| unplaced either way | 291 |

`claim.py`, ADR-113 §1's claim rule and two variants (includes read by
regex; today's row reads 9,473 / 624 where the ingest's own record says
9,468 / 629):

| rule | `.h` read as C++ | left to C: both languages | left to C: no includer placed |
|---|---:|---:|---:|
| today | 9,473 | 1 | **623** |
| + the `-I` step | 9,485 | 1 | 611 |
| + a claim that follows claimed headers | 9,847 | 13 | 237 |
| + both | 9,859 | 13 | 225 |

**Of the 624 headers read as C today, 535 spell `class`, `namespace`
or `template` at the start of a line.** They are C++ parsed by the C
grammar, in a repo with two `.c` files. `audio/effects/hmi/hmi_types.h`
is one: about 21 definition lines, one graph symbol. Two losses follow
from the misread, and the ingest's own warnings show the second:

1. the header's classes, methods and templates are not lane A symbols
   (the C walk has no such kinds), and
2. its includes of C++-claimed headers are reported **unmatched**
   (`audio/effects/hmi: "common/scummsys.h"` — a file that is at the
   repo root). The C walk's `known_files` is the C walk's own files, so
   a header C++ claimed does not exist for it. Of the 277 unmatched
   specs ScummVM's warnings name, 122 are at the repo root.

The cause is in the rule's wording: a C++ *source* must include the
header. A header reached only through another header — an engine's
internal types, included by the engine's public header — has no
includer the rule looks at.

**What `-I` alone buys:** 116 include edges in 95,510 (0.12%) and 12
headers' language, on the one clone that has a non-root include
directory; nothing on a graded cell. It also needs the derived
database's directories carried out of lane B's step, which deletes its
build directory today.

## Decision (proposed)

**The claim follows claimed headers.** A `.h` is C++'s when a C++ file
*or a `.h` already claimed by C++* includes it, to a fixed point, and no
`.c` source reaches it the same way through headers left to C. The
both-languages rule is unchanged (shared headers stay C, and are
named), and so is the record. The C walk's include step is given the
claimed headers as known files, so an include of one draws its edge
instead of an "unmatched" line.

The `-I` step is **not built** on these numbers.

## Routes for Max

- **(a, recommended) The transitive claim, and the C walk knows the
  claimed headers.** *Effect on ScummVM:* 374 headers move from the C
  grammar to the C++ one (623 → 237 with no includer); the 122-in-277
  "unmatched" specs that sit at the root become edges. *Effect on the
  graded cells:* fmt has 1 header left to C (`fmt-c.h`, shared: stays);
  args, cJSON and sqlite-vector are single-language — predicted
  row-identical, and checked, not assumed. C-142 narrowed; C-133
  unmoved.
- **(b) (a), and a header no file includes is read by what it spells.**
  After (a), 238 headers are still left to C on ScummVM and 206 of them
  spell `class`/`namespace`/`template` at a line start (templates for a
  generator, platform ports nothing in the default build includes). A
  content rule would take those too. It is a new kind of evidence for
  the claim — the header's own text, not its includers — and a C header
  that uses `class` as an identifier would be misread. Measure on a
  mostly-C mixed repo before choosing it.
- **(c) (a), and the `-I` step.** Adds 12 headers and 116 edges on
  ScummVM for a new hand-off from lane B's container to lane A. Hold
  until a graded cell shows the cost, as C-133 already says.
- **(d) Nothing.** C-142 already names "one no source includes at all in
  a mixed repo". It does not name the size: 5% of ScummVM's headers.

## Alternatives considered

- **Flip the default in a mostly-C++ repo** (a header nothing includes
  is C++ when C++ files outnumber `.c` files). A ratio is a guess with a
  threshold; ADR-113 refused to read language from anything but
  evidence in the tree.
- **Read `-x`/the unit language from the database.** Headers are not
  translation units; the database names none of them.

## Consequences

- Lane A's C++ cache key moves (the claimed set decides which grammar
  reads a header); a cold walk on the first ingest after.
- The pre-registration for the build's check: ScummVM's `cpp-headers`
  record reads 9,84x claimed and 25x left to C (the probe's regex reads
  5 off the ingest's count today, so ± 10); no `c-includes` line names a
  file that exists at the repo root; the four C and C++ cells and click
  row-identical.

## Accepted — route (a), the rule corrected, and the premises read before the brief (2026-09-19)

**The *Decision* was worded wrongly in one clause, and the probe said
so before anything was built.** It let the C side follow headers too
("no `.c` source reaches it the same way through headers left to C").
Measured on ScummVM, that moves **12 headers C++ claims today to
"shared"** — cxxtest's, reached from `test/cxxtest/sample/SCons/src/stack.c`
through a header both languages include — and 10 of the 12 spell C++.
A rule meant to stop C++ being read as C would have caused it.

**The rule as built:** the C side stays what it is today, a `.c`
source's *own* includes. The claim starts as today's (`by_cpp − by_c`)
and then grows to a fixed point: a `.h` that a **claimed** header
includes, and that no `.c` source includes, is claimed. A header left
to C passes nothing on. `claim.py`'s last line measures exactly this:
ScummVM **9,473 → 9,859 claimed, 238 left to C, none of today's claims
lost**; fmt 25 and 1, unchanged; args, cJSON and sqlite-vector are
single-language and the rule never runs. (The table's "+ transitive"
row, 9,847, was the symmetric rule.)

Premises, read in the tree:

- `cppsource.extract_cpp` parses the six C++ extensions, calls
  `_claim_headers(repo_root, files)` once, then parses the claimed
  headers. The claim reads `parsed.includes` of files already parsed,
  so the fixed point is a loop there: parse the newly claimed, read
  their includes, claim again, until nothing is added. Each header is
  still parsed once.
- `_claim_headers` returns early — every `.h` to C++ — when the repo has
  no `.c` source. The loop is only the mixed branch's.
- `csource._join`'s `known_files` is `{parsed.path for parsed in
  files}`, the C walk's own files, and `extract_c(repo_root, claimed=…)`
  already receives the claimed set. The C walk's include step needs
  that set (and the C++ sources and headers) as *known paths*, not as
  files it parses: an include that lands on one draws its `imports`
  edge to that file's module id and is no longer a `c-includes` miss.
  The id must be the **owning walk's**: the two `module_id` rules agree
  on every header, but `csource.module_id` keeps a `.cpp`'s extension
  where `cppsource.module_id` drops it, and ScummVM does `#include` a
  `.cpp` (`devtools/create_titanic`). `cppsource._join` already does
  the mirror (`known_files = owned | c_sources | left_to_c`).
- Lane A's C++ cache (ADR-128) keys a file's parse by content, not by
  who claimed it; the claimed set is recomputed every ingest.
  *Consequences*' "the cache key moves" named the wrong reason: the key
  carries a fingerprint of `hobbes/extract/*.py`, so the first ingest
  after any change there is cold, this one included.

## Built (2026-09-19, 0.2.50-beta)

Unit `286a` (61 turns of 100, $4.55, Opus 5), gate clear, verify pass,
five files, merged no-ff. One judgement call, kept because it claims
less: `_call_fallback` is given the widened file set too, so an include
resolves one way everywhere, and a rank-2 macro lookup abstains where a
C++-owned header makes its include ambiguous.

**Checked on the branch's code, before the merge:**

- 2,046 pytest and `lane_b` 10 of 10 on the host.
- fmt, args, cJSON, sqlite-vector: identical in every export row,
  symbol, module edge, symbol edge and test reach. click: export
  row-identical (its 316 new `uses` edges are ADR-137's).
- **ScummVM, cold, 547 s:**

| | 0.2.48-beta | the branch |
|---|---:|---:|
| `.h` read as C++ | 9,468 | **9,824** (356 through a claimed header) |
| `.h` read as C | 629 | **273** |
| unmatched includes (`c-includes`) | 395 | **43** |
| … of the specs named, files at the repo root | 122 of 277 | **0 of 33** |
| ambiguous includes | 167 | 170 |
| lane A + minted symbols | 265,116 | 266,529 |
| definitions minted from the index | 4,770 | 3,748 |
| `imports` edges | 225,226 | 225,582 |

**The prediction missed by 35.** `claim.py` said 9,859 claimed (386
through a header); the ingest says 9,824 (356). The probe reads every
`#include` by regex, either arm of an `#if` and whatever a macro
wraps; the walk's `_includes_of` reads the top level's. The miss is
toward claiming less. *Consequences*' figures (9,84x and 25x) were
written for the symmetric rule and are superseded by this table.

The three new ambiguous includes are a C++-owned header now competing
in a suffix match, which is what the compiler would see. 1,022 fewer
definitions are minted because lane A, reading those headers as C++,
has the symbol itself.
