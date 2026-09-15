# Extraction — C

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

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

### C-132 — A `.h` is always C, and C++ is not read (narrowed 2026-09-14)
- **Narrowed (0.2.18-beta, ADR-113).** C++ is read at lane A: `.cc`,
  `.cpp`, `.cxx`, `.hpp`, `.hh` and `.hxx` are discovered, and a `.h`
  is claimed by C++ by its includers (C-142). What is left of this
  entry: a `.h` both languages include, or none does in a mixed repo,
  is still read as C; C++ itself is *wired, not supported* until its
  §3.8 row; and cgo's `foo.go`/`foo.c` collision (C-15) is unchanged.
  The C++ walk's own concessions are `extraction-cpp.md`.
- **Cannot tell you (as first written):** anything about C++.
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

### C-133 — An include resolves by path, not by the build's `-I` flags (narrowed 2026-09-14)
- **Narrowed (0.2.15-beta, ADR-108's 2026-09-14 amendment).** An
  include the three steps cannot place is written down: one `c-includes`
  degradation record per directory counts its unmatched quoted includes
  and its ambiguous includes (either spelling), naming up to three specs
  of each, and `list_blind_spots` shows it. The edges did not move. On
  cJSON, 6 records (the vendored Unity examples' `"ProductionCode.h"`
  ambiguous in four directories; `"Types.h"` and six mock headers
  unmatched); on sqlite-vector, 1 (`libs`' six platform and generated
  headers). Reading the `-I` path from the derived compile database is
  the second unit, not yet decided.
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
- **You find out:** **partial** (was *unsurfaced*; narrowed 2026-09-14):
  - an unmatched quoted include, or an ambiguous include of either
    spelling, is counted in its directory's `c-includes` record, which
    `list_blind_spots` shows; an angle include that matches nothing is a
    dependency (`ext:<p>`) and is not counted, so a generated header
    spelled `<config.h>` still reads as external;
  - a call to a macro two includes down classifies `unclassified` in
    the tail, with no reason attached — still unsurfaced.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Source:** ADR-108; narrowed by its 2026-09-14 amendment.

### C-134 — C tests registered in a form Hobbes does not read are missed (narrowed 2026-09-13)
- **Cannot tell you:** which C tests a framework registers in a form
  Hobbes does not read.
  - **The rule** (ADR-108's 2026-09-13 amendment): a function named by
    a Unity (`RUN_TEST`), CMocka (`cmocka_unit_test*`) or Check
    (`tcase_add_test*`) registration is a test, resolved by the
    fallback's ranks 1 and 3. A file that defines no registered function
    keeps the `test_*` naming convention.
  - **Missed:**
    - criterion's `Test(suite, name)` and the Unity fixture's
      `TEST(group, name)`/`RUN_TEST_CASE`, whose bodies a macro defines,
      so they have no symbol;
    - CTest's `add_test`, whose unit is a program, not a function;
    - a registration behind the project's own macro (C-131);
    - a registration whose name ties at rank 3, between two non-static
      definitions. cJSON's vendored `example_1` and `example_3` are an
      instance.
  - **Wrongly counted:** a `test_*` helper in a file that defines no
    registered function is still a convention test.
- **Because:** C has no standard test framework. The common ones
  register a test by naming its function in a macro call, which lane A
  parses. The rest define the function by macro, and lane A draws no
  symbol for a body the preprocessor would make (C-131).
- **Bites at:**
  - criterion suites;
  - the Unity fixture: cJSON's vendored `extras/fixture` has 38 bodies
    and 41 `RUN_TEST_CASE` calls;
  - duplicated example trees.
- **You find out:** *partial* (was **unsurfaced**; 2026-09-13).
  - Two `c-tests` degradation records, which `list_blind_spots` shows:
    - a test program under `test`/`tests` with a `main` and no test
      Hobbes can name;
    - a per-directory count of the unread forms.
  - **Not surfaced:**
    - The count is a floor. Tree-sitter's error recovery reshapes some
      bodies: 27 of 32 are counted in cJSON's `unity_fixture_Test.c`.
    - A criterion file has no `main`, so only the directory count names
      it.
    - A rank-3 tie, and a helper counted by the convention, draw
      nothing.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Source:** ADR-108, amended 2026-09-13.

### C-135 — A C build root with nothing to derive a compile database from is lane A only (narrowed 2026-09-14)
- **Narrowed (0.2.16-beta, ADR-109's 2026-09-14 amendment).** A derived
  database with entries and none of a file under the root stops the
  plan before scip-clang runs, and the root's `scip-c` record names the
  count, where they lie (cargo's registry, or their common directory),
  that the build compiled none of the root's own C, the build's last
  words, and this id. On bpftop that is 45 dependency compiles under
  cargo's registry: libbpf-sys's vendored libbpf fails in the image for
  want of libelf's headers, so cargo stops before bpftop's own build
  script compiles its BPF program.
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
      there, which draws the `scip-c` record above. With the cache
      warm (the Rust lane's fetch), bear recorded 45 entries, every one
      a dependency crate's C under cargo's registry, none under the
      root. **Read 2026-09-14 and written down** (the narrowing above):
      the root now draws a `scip-c` record with the cause.
  - What stays: a root whose database has entries under it and whose
    index still emits no document surfaces only as the generic
    `scip-index` record (not yet seen); a dependency's build the image
    cannot complete stays lane A.
- **Provider (P9):** none; this is Hobbes's own rule.
- **Folds in:** C-130 (2026-09-13) — what lane A's floor draws for C
  where lane B does not answer (the three name ranks, ADR-108), and its
  reading as 0% capture.
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
- **Narrowed 2026-09-12 (0.2.8-beta, ADR-111): the direction is taken.**
  - **What the join does now.** It drops lane A's fallback at a site whose `(file, line, name)` carries a lane B reference outside the repo. A reference whose moniker has an in-repo definition is marked `in_repo` and never vetoes.
  - **How the regrade reads.** Every oracle cell with a stored key was regraded against it. sqlite-vector reads 851/851, and no confirmed edge was lost anywhere.
  - **Where a user meets a veto:** `lane_agreement.external_vetoes`, which `hobbes lanes` prints.
  - **What remains:**
    - two same-named occurrences on one line, one outside the repo and one the call lane B missed, because the key has no column;
    - a sibling unit's in-repo definition of a kind the graph does not keep, which `join_cross_unit` cannot mark.
- **Source:** ADR-110; `docs/oracle/cells/sqlite-vector-c-2026-09-12.md`.

## Folded entries in this segment

An entry that concedes the same information as another, folded into it
(`README.md`, "How the register is organised"). It keeps its number and
its full text, so every pointer to it still resolves; its italic line
names the parent and what it adds, and the debt summary counts the
concession once, under the parent.

### C-130 — C has no semantic lane: every C edge is a name match, at `syntactic` tier — *narrowed 2026-09-12 (ADR-109)* — *folded into C-135 (2026-09-13)*
*(Folded 2026-09-13 into C-135 (ADR-043 amended). Since ADR-109 this
entry holds only where lane B does not answer for C: a root with no
compile database and the files a build does not compile, which are
C-135's, and a site lane B leaves silent, which is C-7's. This entry adds
what lane A's floor then draws: the three name ranks (ADR-108) and the
0% capture line.)*
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
- **Because:** scip-clang needs each translation unit's compile flags,
  and where this entry still holds there are none to use: no compile
  database could be derived (C-135), the build does not compile the
  file, or lane B left the site silent. ADR-109 derives a database
  wherever it can (Max, 2026-09-12: derive it, degrade visibly).
- **Bites at:** every C repo, and most where one repo holds many
  programs. Examples and tools that each define the same helper make
  rank 3 abstain, so those calls stay unresolved. A repo function that
  shares a name with a system library function draws rank-3 edges from
  every caller.
- **You find out:** **surfaced**:
  - every C edge carries tier `syntactic`;
  - where lane B did not answer, `hobbes lanes` has nothing to check the
    edge against;
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

### C-137 — scip-clang gives file-`static`s of one signature in several files one moniker — *folded into C-28 (2026-09-13)*
*(Folded 2026-09-13 into C-28 (ADR-043 amended): it is C-28's decode
drop applied to scip-clang's monikers. This entry adds C's own-file
recovery (ADR-109) and the provider's moniker scheme.)*
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

### C-149 — A shared header is indexed in one unit's context, and which unit varies by run (C and C++)

- **Cannot tell you:** the same lane B answer twice for a reference
  inside a header many translation units include, when the answer
  depends on the unit: a macro's configured arm, or a name a unit's
  includes bring in. scip-clang indexes such a header once, in
  whichever unit claims it first, so the reference can be present in
  one ingest and absent in the next.
- **Because:** scip-clang deduplicates header indexing across units,
  and its scheduling is not deterministic. Its own `--deterministic`
  flag "does not support deterministic work scheduling yet", and it was
  measured and refused: on fmt, 307 s against 8 s, with 3 of 52 units
  lost.
- **Bites at:** measured at 0.2.20-beta, after the helper's own order
  dependence was fixed (C-148; ADR-109's smallest-line rule):
  - three cJSON ingests at one commit drew 2,630, 2,615 and 2,621
    edges. The differing ones are all `uses` edges from
    `tests/common.h`'s assertion macros to Unity's;
  - fmt's edges repeat, but four tail sites flip between `external` and
    `builtin-name` (`std::FILE`, `fwrite`, `size_t`, `tm` in shared
    headers).

  A `calls` edge could move the same way, directly or through ADR-111's
  external veto; none was seen.
- **Narrowed 2026-09-15 (0.2.21-beta; ADR-109 decision 1 amended,
  `f3c1` and the size guard).** A root with at most 400 compile-database
  entries is indexed one translation unit per scip-clang run, and the
  units are decoded as one. Every unit indexes its own headers, so the
  answer no longer depends on which unit claimed a header:
  - three cJSON ingests are identical, edges and tail;
  - three fmt ingests are identical at the edge level.

  A root over the bound is indexed in one whole-database run, and this
  entry applies there in full.
- **What is left:**
  - roots over 400 units (ScummVM's 5,958 are one: the per-unit merge
    would need about 84 GB);
  - a few external type references scip-clang records inconsistently
    even within one unit (`size_t`, `ptrdiff_t`: 13 of fmt's 13,739
    external sites). These can move a tail count (`external` against
    `builtin-name`), never an edge.
- **You find out:** **partial** — a root over the bound draws a
  `scip-decode` record naming its unit count, the bound and C-149.
  Nothing says a tail count may differ by a site or two below it.
- **Provider (P9):** scip-clang **0.4.0**'s header deduplication.
- **Direction:** a streaming merge (two passes over the unit indexes,
  duplicates removed) would lift the bound. It is not built.

### C-150 — A C/C++ root whose index outgrows Node's heap has no lane B

- **Cannot tell you:** any semantic edge for a C or C++ build root
  whose index the helper cannot decode within Node's default heap. The
  helper dies (exit 139, V8's allocation failure), and the root's call
  edges fall to lane A's fallback.
- **Because:** the helper decodes a root's whole index in memory, under
  Node's default heap limit. Measured on ScummVM (5,958 units, one
  whole-database run under C-149's size guard): the 370 MB index needs a
  peak of about 9 GB to decode (8.95 GB, measured with a 14 GB heap).
  Under the default heap the helper died. Before 0.2.21-beta the same
  root failed earlier, on a stack overflow in the decode.
- **Bites at:** very large C/C++ repos. ScummVM ingested with its 1.53
  million C++ call sites all left to lane A (0.0% accounted). fmt,
  cJSON, sqlite-vector and args are far under it.
- **You find out:** **surfaced** — the root's `scip-c`/`scip-cpp`
  record says the helper ran out of memory decoding the build's index,
  and names this entry. Until 0.2.21-beta the record said "install
  Node", which was wrong.
- **Provider (P9):** Node's default heap limit, the image's Node.
- **Direction:** a larger heap for the helper (machine-dependent), or a
  streaming decode that holds only definitions and unique references.
  The streaming decode is the same change that would lift C-149's
  400-unit bound. Max's call.
- **Source:** the ScummVM end-to-end ingest, 2026-09-15.
- **Source:** the determinism measurements, 2026-09-14 (ADR-113 §2's
  second amendment).
