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
  `test_*.c`/`*_test.c` file, with framework `c-convention`. (Amended
  2026-09-13: a registration makes a test first; see the amendment
  below.)
- **The tail.** `.c` and `.h` map to `c`. The pinned C11 standard
  library, plus `__builtin_*`, is builtin-name. C's row holds five
  classes: fallback, local-binding, builtin-name, attr-call and
  unclassified.

**No lane B.** Every C edge is lane A's fallback, at `syntactic` tier.
That is the join's normal degraded path; nothing in the builder, the
join or the schema changed.

**Lane B, decided in direction here and built by ADR-109 (0.2.4-beta).** scip-clang, pinned in
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

## Amendment (2026-09-13): C tests are found by their registrations (C-134)

**Decided:** Max, 2026-09-13, on three calls, taking the proposed route
each time. **Source:** the top-level review of 2026-09-13; C-134.

### Context

- **The naming rule finds none of cJSON's own tests.** cJSON names them
  `cjson_*_should_*` and registers them with Unity's `RUN_TEST`: 162
  registrations in 21 files under `tests/`.
- **What it finds instead:** 39 tests.
  - 37 are in the vendored Unity tree (`tests/unity/`).
  - The other 2 are helpers: `json_patch_tests.c`'s `test_apply_patch`
    and `test_generate_test`, static functions the file's registered
    tests call.
- **What lane A already sees.** The common frameworks register a test by
  naming its function in a macro call, which lane A parses as a call.
  - `RUN_TEST(fn)` and `cmocka_unit_test(fn)` are calls, usually inside
    `main`.
  - Check's `START_TEST(name) { … }` parses as a function named `name`,
    which `tcase_add_test(tc, name)` registers.
  - criterion's `Test(suite, name) { … }` and the Unity fixture's
    `TEST(group, name) { … }` give no symbol. The body is a function the
    macro defines, and lane A draws nothing for it.
- **A registration need not sit beside its function.** Unity's examples
  define their tests in `test/TestProductionCode.c` and register them
  from `test/test_runners/TestProductionCode_Runner.c`.

### Decision

1. **A registration makes a test.** In any `.c` file lane A reads, a
   call to one of these forms registers the function it names, when the
   test argument is a bare identifier:
   - **Unity:** `RUN_TEST(fn)` and `RUN_TEST(fn, line)`; framework
     `unity`.
   - **CMocka:** `cmocka_unit_test(fn)` and its `_setup`, `_teardown`,
     `_setup_teardown` and `_prestate*` forms, with the test as the first
     argument; framework `cmocka`.
   - **Check:** `tcase_add_test(tc, fn)` and its `_raise_signal`,
     `tcase_add_exit_test` and `tcase_add_loop_*` forms, with the test as
     the second argument; framework `check`.
2. **The named function resolves like a call.** The same-file function
   first, then the unique non-static function repo-wide (ranks 1 and 3
   of the fallback). A tie abstains, and a registration that resolves to
   nothing makes no test. The test's id, line and reach are its
   function's, as before.
3. **The convention yields per defining file.**
   - A file that defines any registered function, registered from any
     file, contributes exactly its registered functions.
   - The naming convention holds only in files that define none.
   - A function that is both registered and convention-named is one
     test, with the registration's framework.
   - On cJSON, `json_patch_tests.c`'s two helpers drop. In Unity's
     example 1, the five `test_*` functions in `TestProductionCode.c`
     are five `unity` tests, counted once.
4. **Out of scope. These stay in C-134, which narrows:**
   - criterion's `Test(suite, name)` and the Unity fixture's
     `TEST(group, name)`/`RUN_TEST_CASE`: a test needs a symbol, and lane
     A draws none for a body a macro defines;
   - CTest's `add_test`: its unit is a program, not a function;
   - a registration behind the project's own macro: the preprocessor
     never runs (C-131).
5. **Two `c-tests` degradation records. C-134 becomes *partial*.**
   - **A test program with no nameable test.** A `.c` file under a
     `test`/`tests` directory that defines `main`, and neither defines
     nor registers a test, draws a record naming the file: "a test
     program with no test Hobbes can name; it registers its tests in a
     form Hobbes does not read (C-134)". This catches frameworks Hobbes
     has never heard of.
   - **The forms Hobbes knows and does not read.** One record per
     directory counts its `Test(…, …) { … }` and `TEST(…, …) { … }`
     bodies and its `RUN_TEST_CASE` calls. This catches criterion, which
     has no `main`.

   `list_blind_spots` shows both with the other degradation records.

### Consequences

- **On cJSON (measured at review, lane A, 2026-09-13;
  `extraction-evidence.md`):**
  - 39 tests became 199.
  - In cJSON's own `tests/`, the 2 helpers left, and all 162 registered
    `cjson_*` tests arrived as `unity` tests.
  - The vendored Unity tree kept its 37 convention tests. Its
    `example_1` and `example_3` define the same test names, so rank 3
    ties and abstains. The prediction written here, that its count would
    move, was wrong; the rule held.
  - Five `c-tests` records: two fixture runners with no nameable test,
    and three directory counts, totalling 38 `TEST(…)` bodies and 41
    `RUN_TEST_CASE` calls. The body count is a floor: tree-sitter's
    error recovery reshapes 5 of the 32 bodies in
    `unity_fixture_Test.c`.
- **Fixtures:** none were added to `minic`, whose `lane_b` cases skip in
  the sandbox. Every case is built in `tmp_path` in `test_csource.py`.
- **`tests.json`'s framework strings:** `unity`, `cmocka`, `check` and
  `c-convention`.
- **The register:** C-134 narrowed, and *partial*.
- **The version:** a patch, because it changes what the layer draws.
- **How it is built:** through the harness, as one session.
