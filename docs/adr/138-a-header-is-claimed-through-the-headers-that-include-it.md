# ADR-138 — A `.h` is claimed through the headers that include it; the `-I` path measured beside it

**Date:** 2026-09-19 · **Status:** proposed — measured, nothing built, no version move. The routes below are Max's.

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
