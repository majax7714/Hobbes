# ADR-109 — C's lane B: scip-clang over a derived compile database, degrading visibly

**Date:** 2026-09-12 · **Status:** accepted; built in 0.2.4-beta. · **Owner:** Max · **Source:** Max, 2026-09-12: "derive it, degrade visibly", then "continue with the lane b build for c". The spike is recorded below.

Follows ADR-108, C at lane A. It amends the architecture's **§3.2**
(C's indexer) and **§3.7** (the walk's lane B). It does not touch
**§3.8**: C stays unverified until an oracle cell grades it.

## Context

ADR-108 wired C at lane A: every edge is a name match, at `syntactic`
tier (C-130). scip-clang, a clang-based SCIP indexer, resolves C
references semantically, but only per translation unit, from each
unit's compile flags. So Hobbes must find those flags, and must run
whatever produces them inside the image, because configuring or
building a repo executes the repo's build logic (ADR-092).

**The spike** (2026-09-12, DaveGamble/cJSON at `fb16e5c`, in a
throwaway container from the image) found:
- **The indexer runs:** CMake's export gave 27 compile-database entries,
  and scip-clang 0.4.0 indexed all 27 translation units in 0.2 s with 0
  errors (an 806 KB index).
- **The helper's decode read no C function.** scip-clang names a C
  function with a signature-hash disambiguator,
  `cxx . . $ cJSON_Delete(6efceb6909523ce2).`, which the SCIP spec
  allows. `classify()` accepted only `()` and scip-java's `(+N)`, so
  each function read as a `term`, and `terminalName()` kept the hash:
  `cJSON_Delete(6efceb6909523ce2)` matches no call site. Lane B joined
  29 of 4,292 C sites.
- **After fixing the disambiguator:** lane B resolves **1,490 of 4,292**
  sites. Where both lanes answer (**1,416 sites**) they agree on every
  one, 0 disagreements. Lane B alone resolves 74 field calls, which
  lane A never resolves.
- **Of the 1,947 sites only the fallback resolves:**
  - **1,694 are macro calls.** scip-clang names a macro by its
    defining location (`` cxx . . $ `cJSON.h:281:9`! ``), not by its
    name, so no call site matches it by name.
  - **253 are functions whose moniker two files define.**
    - Same-named file-statics with one signature (`compare_double`,
      `get_array_item` and `get_object_item`, in both `cJSON.c` and
      `cJSON_Utils.c`) hash to one moniker.
    - The decode drops a moniker defined in two files (C-28), so these
      calls go unattributed.

## Decision

1. **The indexer.**
   - scip-clang **0.4.0** (`scip-clang-x86_64-linux`, sha256
     `06fd18c576f979a726c651594644ec4a35db4f471f2160b3f72eb89fa6001784`),
     installed in the image beside **CMake 3.28** and **bear 3.1**
     (Ubuntu 24.04's packages).
   - Read against ADR-105's five points: a pinned batch program, its
     version stated, its tier `semantic`, not a language server, and
     its output (SCIP) decoded by the helper.
   - It is x86_64 only, as the image already is.
2. **The compile database is derived, in this order** (Max), per build
   root. A root is the outermost directory holding a `CMakeLists.txt`,
   or, with none on the path, the outermost holding a Makefile. A root
   Makefile that drives only the docs must not swallow a CMake project
   below it.
   1. a `compile_commands.json` the repo carries, at the root or in
      `build/`;
   2. **CMake's export:** `cmake -S <root> -B <scratch>
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, which configures only;
   3. **bear over make:** `bear -- make -k`, which builds the repo;
   4. otherwise **lane A only**, with a degradation record naming why.

   Steps 2 and 3 execute the repo's build logic. They run in the image
   with **no network**; a build that fetches (FetchContent,
   ExternalProject, a submodule) fails, and its unit degrades to lane A
   with the build's own words. That is C-29's C face.
3. **The helper decodes three C shapes:**
   - **A method's disambiguator** is any identifier, per the SCIP spec.
     Done in `classify()` and `terminalName()`; it changes nothing for
     the other five indexers.
   - **Macros named by location.** The helper reads a macro's name from
     the defining location its moniker carries (`file:line:col` in the
     stage), so a macro reference joins by name. A location outside the
     repo, such as a libc macro (`isnan`), stays external.
   - **Colliding file-statics.** A reference to a moniker that two files
     define resolves to the definition in **the reference's own file**,
     when that file defines it: C's `static` linkage. Any other
     reference to the moniker stays unattributed (C-28). This rule
     applies to `cxx` monikers only.
   - **One site, several translation units.** scip-clang merges units,
     so one site can arrive once per unit.
     - **Targets in one file,** at several lines, are one definition's
       own `#if` alternatives, and are kept once, at the first line,
       where the graph keeps the symbol.
     - **Targets in different files** are a real disagreement. At
       cJSON.c:612, `isinf` is cJSON's own macro in the C89 library
       build and Unity's in the test programs that `#include` cJSON.c.
       Lane B's answer is dropped there, lane A's floor stands, and a
       `scip-decode` record counts the sites (C-131).

     Found by the product-path run on cJSON, the one lane disagreement
     it raised.
4. **The join.** C edges lane B resolves are `semantic`. Lane A's
   fallback stays the floor where lane B is silent, and `hobbes lanes`
   checks the two where both answer.
5. **§3.8 is untouched.** C is "supported" only after an oracle cell
   (clang's own call graph), in the unit after this one.

## Consequences

- **Register:**
  - C-130 is narrowed: lane B runs where a compile database can be
    derived.
  - C-131 is narrowed: lane B indexes the configured `#if` arm, while
    lane A still reads both.
  - New entries:
    - a build root with no derivable compile database is lane A only
      (*surfaced*, the degradation record);
    - configuring or building a C repo executes its build logic,
      contained and offline (*surfaced*, the ingest's disclosure);
    - scip-clang's cross-file static moniker collision (P9, provider),
      partly recovered by the own-file rule.
- **The image grows** by CMake, bear (with its gRPC runtime) and
  scip-clang's 149 MB binary.
- **This repo's own ingest** indexes the `minic` fixture through bear
  over its Makefile, which exercises step 3 on every ingest.
