# ADR-108 — C at lane A: a tree-sitter-c walk with no indexer yet — wired, not supported

**Date:** 2026-09-12 · **Status:** accepted. Lane A was built by two dispatched sessions and merged; lane B is decided in direction and not built. · **Owner:** Max · **Source:** Max, 2026-09-12: "run the new harness with adding c as a language to hobbes". On lane B: "derive it, degrade visibly".

Amends the architecture's **§3.1** (a seventh provider) and **§3.7**
(the seventh walk). It changes nothing in §3.8: C has no row, so it is
*wired, not supported* (P11).

## Context

§3.7 has four steps. Step 1, the indexer, is what makes C hard here:
- scip-clang (v0.4.0, a pinned batch program, so admissible under
  ADR-105) needs each translation unit's compile flags;
- where those come from is a design question;
- the image change it needs can't be made from a dispatched session,
  which has no route to fetch anything.

Step 2, the syntax provider, is the bounded mechanical job §3.7 already
names, with six worked examples. So C lands in two units: lane A now,
lane B next.

## Decision

**Lane A: `pipeline/src/hobbes/extract/csource.py`**, on the
`rustsource`/`javasource` contract.
- **Files.** `.c` and `.h` are C, and a `.h` is always read as C. C++
  (`.cc`, `.cpp`, `.cxx`, `.hpp`, `.hh`) is not discovered. The walk
  prunes `build/` and `cmake-build-*`.
- **Module ids.** A `.c` file's id drops the extension (the ADR-021
  rule). A `.h` file's id keeps it, so a `foo.c`/`foo.h` pair in one
  directory can't collide.
- **Symbols come from definitions only.** Functions are recorded (a
  `static` one is marked file-local). A struct, union or enum with a
  body, and a typedef, are types. A function-like macro is kind
  `macro`. Prototypes and object-like macros are not symbols.
- **The walk is transparent through** `#if`/`#ifdef` arms and through
  `extern "C" { … }` (a `linkage_specification`).
- **One symbol per id.** When a file defines a name twice (preprocessor
  alternatives), the first definition in file order is the symbol, and
  a `parse` record names the duplicates.
- **Includes.** A `"p"` include resolves relative to the including
  file, then the repo root, then a unique repo header ending `/p`. A
  step that climbs above the root is not a candidate. A `<p>` include
  tries the same steps, and otherwise becomes `ext:<p>`.
- **Call sites** are recorded at the terminal identifier, with three
  shapes: plain, a struct field (`s->fn(x)`), and a dereference
  (`(*fp)(x)`).
- **The fallback** resolves plain calls by name, in three ranks:
  1. a same-file function or macro;
  2. a macro in a directly included header;
  3. the unique non-static function repo-wide.

  A tie at any rank abstains, and does not fall through to the next
  rank. A name bound to a function pointer (a parameter or a local) is
  never resolved.
- **Tests** are `test_*` functions in a `test`/`tests` directory or a
  `test_*.c`/`*_test.c` file, with framework `c-convention`.
- **The tail.** `.c` and `.h` map to `c`. The pinned C11 standard
  library, plus `__builtin_*`, is builtin-name. C's row holds five
  classes: fallback, local-binding, builtin-name, attr-call and
  unclassified.

**No lane B.** Every C edge is lane A's fallback, at `syntactic` tier.
That is the join's normal degraded path; nothing in the builder, the
join or the schema changed.

**Lane B, decided in direction and not built.** scip-clang, pinned in
the image. The compile database is derived:
1. the repo's `compile_commands.json`;
2. else CMake's export, run in the container;
3. else `bear` over the Makefile;
4. else lane A only, and the ingest says so.

Its own ADR carries the build: ADR-105's five points, the containment
profile, and the register entries it lifts. After it comes C's §3.8 row
on an oracle.

## Consequences

- **Register:** C-130 to C-134, a new segment
  (`constraints/extraction-c.md`):
  - C-130: no semantic lane, edges by name only (*surfaced*);
  - C-131: the preprocessor never runs (*partial*);
  - C-132: `.h` is C and C++ is not read (*partial*);
  - C-133: includes resolve by path, not by `-I` (*unsurfaced*);
  - C-134: one test naming convention (*unsurfaced*).
- **A cgo package** with `foo.go` beside `foo.c` gives both files the
  module id `foo`: C-15, the cross-language namespacing gap, now has a
  common real shape.
- **The version:** 0.2.1-beta. It is a patch because C is wired, not
  supported (Max). The minor waits for "supported".
- **How it was built:** the harness (ADR-107), two sessions.
  - `S-20260912T164904Z-eef8` built the walk: gate clear, verify pass.
  - Review on DaveGamble/cJSON found four defects outside the gate's
    classes: `extern "C"` bodies unwalked, a rank-1 tie that picked,
    duplicate ids, and a `..` include that resolved.
  - `S-20260912T171754Z-e6db` fixed them: gate clear, verify pass.
  - On cJSON after the fix: 3,363 of 4,292 C call sites resolve by the
    fallback, giving 1,761 edges. Nine sampled edges were right against
    their lines (four at each commit's review, plus five after). That
    is evidence enough to review, not a §3.8 row.
