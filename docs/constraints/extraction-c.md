# Extraction — C

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-130 — C has no semantic lane: every C edge is a name match, at `syntactic` tier — *narrowed 2026-09-12 (ADR-109)*
- **Narrowed (0.2.4-beta).** scip-clang is C's lane B wherever a
  compile database can be derived (C-135 is where it cannot). What
  follows now holds only for:
  - roots with no database;
  - the files a root's build does not compile;
  - sites lane B leaves silent, or answers two ways (C-131).
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
  - the verification base (C-31) in the ingest summary, the surface and
    `list_blind_spots` stated C as unverified until 0.2.5-beta. Since
    ADR-110's cells it names the two repos graded, cJSON and sqlite-vector,
    and nothing wider.

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

### C-131 — The preprocessor never runs — *narrowed 2026-09-12 (ADR-109)*
- **Narrowed (0.2.4-beta).** Where a compile database is derived,
  scip-clang runs the preprocessor as the build configures it, so lane B
  sees the live `#if` arm and resolves macro uses. Two shapes remain:
  - **Several translation units disagree.** scip-clang merges units. A
    site whose units reach definitions in *different files* (a macro or a
    `static` their includes decide; cJSON.c:612's `isinf`, cJSON's own
    in the library build and Unity's in the tests) has its lane-B answer
    dropped, and lane A's floor stands. The `scip-decode` record counts
    these sites.
  - **One definition's own `#if` alternatives** (targets in one file) are
    kept once, at the first line, where the graph keeps the symbol.

  What follows still describes lane A, and every root with no database.
- **Measured (ADR-110's oracle cells, 2026-09-12):**
  - **Recall:** a call a macro's expansion makes is never drawn; the
    edge goes to the macro. On cJSON that is 728 of 1,918 in-repo pairs
    (38.0%), every miss of the cell: Unity's `TEST_ASSERT_*` and
    `RUN_TEST` expand to `UnityFail`, `UnityDefaultTestRun` and
    `UnityAssert*` (723). Five are cJSON's own API: its
    `cJSON_SetNumberValue` macro calls `cJSON_SetNumberHelper`.
  - **Where those calls are.** Lane B records an expansion's callees at
    the invocation line, and the join lands them as `uses` edges (381
    into `UnityFail` on cJSON).
    - Dependency questions see them; call questions (`who_calls`, test
      reach) do not.
    - Promoting them to `calls` is parked (Max, 2026-09-12;
      `future_additions.md`). SCIP carries no call role, and a function
      passed as a value on the same line (`RUN_TEST(test_fn)`) would draw
      as a call.
  - **Precision:** a function defined in a dead arm is a real target to
    lane A. sqlite-vector's `strcasestr` shim drew three wrong
    `syntactic` edges (C-138).
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

### C-135 — A C build root with nothing to derive a compile database from is lane A only
- **Cannot tell you:** semantic C edges under a build root whose
  compile database cannot be derived. That covers four cases:
  - C files under no `CMakeLists.txt` or Makefile at all;
  - a carried `compile_commands.json` naming another machine's absolute
    paths, which is skipped;
  - a CMake configure step that fails, such as a missing package, or a
    `FetchContent` that needs the network;
  - a `make` under bear that compiles nothing.
- **Because:** scip-clang indexes one translation unit at a time, with
  that unit's own flags. Guessing the flags (an `-I`, a `-D`) would
  index a configuration no build uses. So Hobbes derives the flags or
  does without (ADR-109: the repo's own database, CMake's export, or
  bear over make).
- **Bites at:**
  - autotools projects, whose `Makefile` is generated by `./configure`
    and not in the repo;
  - Meson, Bazel and ninja-only builds;
  - a CMake project that fetches its dependencies at configure time;
  - files a build root never compiles (`minic`'s `platform.c`, which its
    Makefile names in no target).
- **You find out:** **partial** (was *surfaced*; amended 2026-09-12).
  Each root that cannot be indexed draws a `scip-c` degradation record,
  which names why: no build file, the carried database it skipped and
  the reason, or the build's own last words. Orphan files are counted
  per directory. What the build does not compile shows only as the
  missing semantic tier on those files' edges.
  - **The gap, measured on jfernandez/bpftop** (`5a67ec0`, the C draw's
    first candidate, ADR-110): the root's one Makefile target is
    `cargo build`, and its one C file is a BPF program cargo's build
    script compiles.
    - The root got no C semantic edge.
    - It drew only the generic `scip-index` record, "the indexer
      emitted no documents; nothing was analysed", with no C reason and
      no register id.
    - Offline and with an empty cargo cache, bear records 0 entries
      there, which draws the `scip-c` record above. So in the ingest's
      own run bear recorded entries that scip-clang indexed nothing
      from. Which entries is not yet read.
  - So a root whose derived database indexes nothing surfaces without
    its cause.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Source:** ADR-109; the gap, ADR-110's draw.

### C-136 — Indexing C runs the repo's build logic, contained and offline
- **Cannot tell you:** that ingesting a C repo runs none of its code.
  Unless the repo carries a usable compile database, Hobbes derives one
  by running one of two things:
  - CMake's configure step, where a `CMakeLists.txt` is code
    (`execute_process`, `try_run`, included scripts);
  - the repo's `make` under bear, which runs compilers and every recipe
    the default target reaches.

  This is C-29 (Rust's `build.rs`) and C-66 (Java's build) for C.
- **Because:** the flags scip-clang needs are the build's knowledge,
  and only running the build yields them.
- **Bites at:** every C repo without a carried database. It runs only
  inside the image, with no network (`index-c`), and the host is never
  touched.
- **You find out:** **surfaced**:
  - every ingest prints a `NOTE: c semantics:` line;
  - the artifact's `containment` stamp lists `index-c`;
  - with no image, the step is refused and never run on the host
    (C-64).
- **Provider (P9):** CMake **3.28.3** and bear **3.1.3** (Ubuntu 24.04's
  packages in the image), and the repo's own build files.
- **Source:** ADR-109.

### C-137 — scip-clang gives file-`static`s of one signature in several files one moniker
- **Cannot tell you:** which file's definition a call reaches when two
  `.c` files each define a `static` function or variable of the same
  name and signature, unless the call is in a file that defines it. The
  same goes for `main` across a repo's programs.
- **Because:** scip-clang 0.4.0 names a C function by its name plus a
  hash of its signature, not by its file. The decode drops a moniker
  that two files define (C-28).
  - ADR-109's own-file rule recovers a reference from a file that
    defines the moniker, which is C's `static` linkage.
  - A reference from any other file stays unattributed: a `.c` file
    `#include`d into another, or a test program calling another
    program's `main`.
- **Bites at:** cJSON's `compare_double`, `get_array_item` and
  `get_object_item`, defined in both `cJSON.c` and `cJSON_Utils.c`, and
  every test program's `main`. In `minic`: `helper`, and the duplicate
  non-static `scale` (which lane A's rank 3 also abstains on).
- **You find out:** **surfaced**. The `scip-decode` record counts the
  monikers and names a sample (C-28's surfacing), in C's own wording.
- **Provider (P9):** inherited from scip-clang **0.4.0**'s moniker
  scheme.
- **Source:** ADR-109.

### C-138 — Lane A's fallback guesses where lane B resolved the site to a declaration outside the repo
- **Cannot tell you:** that a `syntactic` edge's target is the one the build calls, where the configured build calls a library function of the same name.
  - `evidence.join` (every language) takes lane A's fallback wherever lane B produced no *in-repo* resolution. It does not ask whether lane B resolved the site to a declaration outside the repo.
  - **C's face, measured (O9, ADR-110):** sqliteai/sqlite-vector defines its own `strcasestr` inside an `#if` for Windows, musl and WebAssembly.
    - On glibc Linux that arm is dead, and the calls are libc's.
    - Lane A reads both arms (C-131), so its rank 1 names the shim.
    - Lane B's answer is libc's declaration, which the join does not consult.
    - The result is three `syntactic` edges, all wrong.
- **Because:** the join was written for lane B's silence, not for an answer outside the repo. External references are read by the tail's classification (`evidence.unresolved_sites`), not by `join`.
- **Bites at:**
  - portability shims: a repo's own `strcasestr`, `strlcpy`, `asprintf` or `getline` behind an `#if`;
  - in any language, a repo function that shares a name with a library call lane B resolved.
- **You find out:** **partial**.
  - The edge carries tier `syntactic`, so trust it less (C-7).
  - Nothing says lane B answered the site differently. `hobbes lanes` compares only sites both lanes resolved in the repo: sqlite-vector's lanes read 1,084 / 0 with these three edges in the graph.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Direction (not taken; Max's call):** the join vetoes lane A's guess where lane B's reference at the site is external, the way ADR-104 vetoes lane B at an ambiguous site. It is a change to every language, and every cell's syntactic tier would be regraded.
- **Source:** ADR-110; `docs/oracle/cells/sqlite-vector-c-2026-09-12.md`.
