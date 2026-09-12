# Extraction — C

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-130 — C has no semantic lane: every C edge is a name match, at `syntactic` tier
- **Cannot tell you:** that a C call lands where its edge says, beyond
  the name rule. Every C edge is lane A's fallback, which resolves a
  plain call by name in three ranks: same file, then a directly
  included header's macro, then the unique non-`static` function
  repo-wide (ADR-108).
  - A rank-3 edge names the one repo definition of `f`, even where the
    target that makes the call links a library's `f` instead.
  - Calls through function pointers, struct fields and dereferences
    draw no edge.
  - Nothing type-directed is known.
- **Because:** no C indexer is wired yet. scip-clang needs each
  translation unit's compile flags. Deriving a compile database is the
  next unit (Max, 2026-09-12: derive it, degrade visibly).
- **Bites at:** every C repo, and most where one repo holds many
  programs. Examples and tools that each define the same helper make
  rank 3 abstain, so those calls stay unresolved. A repo function that
  shares a name with a system library function draws rank-3 edges from
  every caller.
- **You find out:** **surfaced**:
  - every C edge carries tier `syntactic`;
  - there is no C lane B for `hobbes lanes` to check against;
  - the verification base states C as unverified (C-31) in the ingest
    summary, the surface and `list_blind_spots`.

  A *C-scoped* `list_blind_spots` said neither until 0.2.2-beta. The
  knowledge proxy's copies of the tail's language tables lacked C, and
  a drift test now holds them to `tail.py`.

  The capture line reads **0% accounted** for C. A fallback-resolved
  site counts in the unresolved remainder (the tail's design for every
  language, where lane B normally speaks first), so for a language whose
  only resolver is the fallback, the headline understates the graph. The
  per-file rows name the `fallback-resolved` count beside it.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Source:** ADR-108; sessions `S-20260912T164904Z-eef8` and
  `S-20260912T171754Z-e6db`.

### C-131 — The preprocessor never runs
- **Cannot tell you:** what the preprocessor makes of the source.
  - Function-like macros are symbols, and their invocations are calls.
    An edge to a macro is a compile-time expansion, not a runtime call.
  - Both arms of an `#if`/`#ifdef` are read as if both were live.
  - Code produced by token pasting or X-macros is invisible.
  - A macro used where a declaration expects a type, such as an export
    wrapper like `CJSON_PUBLIC(type)`, parses as a call at module scope.
- **Because:** lane A reads the file as written (§3.1). Which
  configuration is live is the build's knowledge, and only a compile
  database carries it (C-130).
- **Bites at:**
  - portable code with platform arms: a name defined in two arms of one
    file is one symbol (the first definition), and its same-file calls
    abstain (nine files in cJSON's vendored Unity);
  - export-macro-heavy headers.
  - **Residual:** the one-symbol-per-id rule dedupes by name regardless
    of kind. A struct tag and a function sharing a name in one file
    (`struct stat` and `stat()`) are one tie, and calls to the function
    abstain. That is conservative, never a wrong edge.
- **You find out:** **partial**:
  - a name defined more than once in a file draws a `parse` record
    naming it;
  - a file tree-sitter could not balance draws a syntax-error `parse`
    record;
  - an edge to a macro targets a `macro`-kind symbol.

  Nothing flags a dead `#if` arm.
- **Provider (P9):** tree-sitter-c **0.24.2**, whose grammar has no
  preprocessor by design.
- **Source:** ADR-108.

### C-132 — A `.h` is always C, and C++ is not read
- **Cannot tell you:** anything about C++.
  - `.cc`, `.cpp`, `.cxx`, `.hpp` and `.hh` files are not discovered.
  - A C++ project's `.h` headers are parsed as C, so classes,
    templates and namespaces become syntax errors, and the declarations
    inside them are lost.
- **Because:** the grammar is tree-sitter-c. C++ is a separate language
  with its own §3.7 checklist, and it has not been named.
- **Bites at:**
  - mixed C/C++ repos;
  - C++ libraries whose headers use `.h`;
  - cgo packages: `foo.go` beside `foo.c` gives both files the module id
    `foo`, the C-15 collision in a common real shape.
- **You find out:** **partial**:
  - the ingest's language list never includes C++;
  - a C++ `.h` draws a syntax-error `parse` record.

  Nothing states that C++ sources were skipped.
- **Provider (P9):** tree-sitter-c **0.24.2**.
- **Source:** ADR-108.

### C-133 — An include resolves by path, not by the build's `-I` flags
- **Cannot tell you:** which header a `#include` reaches when the
  build's include path decides it. Hobbes tries three steps: the
  including file's directory, the repo root, then a unique path suffix.
  - An include reachable only through an `-I` directory, whose suffix
    matches two repo headers, draws no edge.
  - A `<p>` that matches no repo file becomes `ext:<p>`, even when the
    build generates that header.
  - Macros from a header two includes down are not seen by the
    fallback's rank 2, which reads one level.
- **Because:** the include path is compile-flag knowledge, the compile
  database of C-130.
- **Bites at:** repos with several `include/` trees, generated headers
  (`config.h`), and macro APIs reached through an umbrella header.
- **You find out:** **unsurfaced**:
  - an unresolved quoted include draws no record;
  - a call to a macro two includes down classifies `unclassified` in
    the tail, with no reason attached.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Source:** ADR-108.

### C-134 — C tests are found by one naming convention
- **Cannot tell you:** which C tests a framework registers by other
  means.
  - **The rule:** a test is a `test_*` function in a `test`/`tests`
    directory, or in a `test_*.c`/`*_test.c` file.
  - **Missed:** tests registered any other way are absent from the
    inventory, and so is their reach. That includes Unity's
    `RUN_TEST(fn)` for other names, CMocka's `cmocka_unit_test`,
    Check's `START_TEST`, criterion's `Test(suite, name)` and CTest's
    `add_test`.
  - **Wrongly counted:** a helper named `test_*` in a test directory is
    counted as a test.
- **Because:** C has no standard test framework, and the naming
  convention is the one rule that holds without one (ADR-108).
- **Bites at:** cJSON's suite, which names its tests `cjson_*_should_*`
  and registers them through `RUN_TEST`. None of those are tests to
  Hobbes. The 39 it finds include helpers such as
  `json_patch_tests.c::test_apply_patch`.
- **You find out:** **unsurfaced**. `tests.json` and the Tests tab list
  what was found, and nothing names what was missed.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Source:** ADR-108.
