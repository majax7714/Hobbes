# ADR-110 — C's oracle: clang's own front end, one translation unit at a time, over the compile database the ingest derives

**Date:** 2026-09-12 · **Status:** accepted; the build is dispatched through the harness (ADR-107). · **Owner:** Max · **Source:** Max, 2026-09-12: "proceed with grading c against the oracle with a c repo. utilize hobbes and calvin as a harness"; ADR-109's "an oracle cell (clang's own call graph)".

Follows ADR-089 (the oracle lane) and ADR-109 (C's lane B). It adds
the lane's seventh oracle, **O9**, and changes nothing in the product.
C gets a §3.8 row only from the cells this oracle grades.

## Context

C is wired at both lanes and unverified: ADR-109 left §3.8 untouched
until an answer key Hobbes does not control grades C's edges. The
lane's grain is *(call-site line, callee declaration)* (D-O4). Four
sources were read against it:

- **clang's static analyser call graph** (`debug.DumpCallGraph`) —
  function grain, no site. Rejected: the lane grades sites.
- **LLVM IR at `-O0` with debug locations** — site grain, but below the
  front end: macros are gone and the callee is what lowering left.
  Rejected, as the Rust lane rejected `cargo-call-stack` (§7).
- **GCC's `-fcallgraph-info`** — an engine independent of clang, but its
  edges come after GIMPLE lowering, not from the front end's name
  resolution. Named, not built: a possible second arm.
- **clang's front end, `-Xclang -ast-dump=json`** — every `CallExpr`, the
  declaration its callee names, and for any token a macro produced both
  where it was written and where it was expanded. **Chosen.**

**Independence.** scip-clang, C's lane B, is built on clang, so this key
shares a front end with the lane it grades. That is the precedent the
lane already accepted for `tsc` beside scip-typescript and javac beside
scip-java: the compiler is the authority on what a call *names*. What
the cell grades is everything Hobbes adds above the front end — the
moniker decode and its four C rules (ADR-109), the range join, and lane
A's name fallback — which is where every C defect so far was found. C
resolves a direct call by name lookup with no overloading, so a
front-end error both sides would share is not a live risk. The §3.8 row
names the shared front end anyway.

## Decision

1. **`oracle c-clang`** in `bench/oracle`, Go. One cell is one C build
   root (ADR-109's definition). Kind `resolution`; `roots` names where
   the compile database came from and how many translation units it
   holds; the export stamps `clang --version`.
2. **The compile database is derived the way the ingest derives it**
   (ADR-109, Max's order): a carried `compile_commands.json` that
   rebases, else CMake's export, else bear over `make -k`. The oracle
   grades what the product indexed, under the same environment (§5).
   Deriving runs the repo's build logic, so the whole step runs inside
   the image with no network, in **one container**: a build's generated
   headers exist only in that container's overlay. The oracle binary
   runs inside it, built static. `--compdb` names a database instead.
3. **Per translation unit:** `clang -fsyntax-only -Xclang
   -ast-dump=json` with the entry's own flags (output and dependency
   flags dropped). The dump is read as a stream, in document order: the
   dumper omits a location's `file` and `line` when they repeat the
   previous location's, so the reader carries them forward and never
   guesses. An object whose first key is `offset` is a location; an
   `includedFrom` object is not. One shard per unit; a unit clang
   rejects is recorded with its last words and graded as not loaded.
4. **Sites.** Every `CallExpr` whose callee token lies in the repo.
   - **A direct call** — the callee, under parentheses, implicit casts
     and unary `*`/`&`, is a `DeclRefExpr` to a `FunctionDecl` — is mode
     `static`.
   - **Any other callee** (a parameter, a variable, a struct field, a
     dereferenced pointer) is mode `dynamic` with no targets. C declares
     no dispatch set to list.
   - **Position:** the callee name token (the terminal identifier lane
     A records), not the parenthesis. A token written in a **macro
     argument** sits where it was written (its spelling location). A
     token written in a **macro's body** sits at the invocation (the
     expansion location), mode `macro`: the author wrote the invocation,
     not the call — the Rust convention's C face.
   - One written call expanded twice is one site; the calls of one
     expansion stay distinct sites, keyed by where each was spelled.
5. **Targets are definitions.**
   - **Internal linkage** (`static` on the first declaration): the
     unit's own definition.
   - **External linkage:** joined across shards by name, as javac's
     keyed merge joins classes. One definition is the target. Several
     (separate programs each defining the name) resolve to the calling
     unit's own when it has one; otherwise the site has no targets and
     is counted **`link-ambiguous`** (the build's link units are not
     read).
   - **No definition, declared only outside the repo or only
     implicitly** (libc; a `__builtin_*`, which clang declares
     implicitly at its first use, so its location is the call's own):
     external, out of the in-repo recall denominator (D-O3).
   - **No definition, declared in the repo:** no targets, counted
     **`undefined`** (the body is in no compiled unit).
   - **Position:** the definition's name token line, by item 4's
     spelling rule, so a function a macro defines from a name argument
     sits at the invocation that named it.
   - A site that units resolve to different definitions (a header's
     `static inline` calling a `static` each includer defines) keeps
     every target and is counted **`tu-split`** — cJSON.c:612's shape,
     where ADR-109 keeps lane A's floor.
6. **Grading** is the lane's, unchanged: the export already excludes
   Hobbes' edges to `macro` symbols before grading and counts them (a
   macro invocation is expanded, not called). The counts of item 5 ride
   in the export's `coverage` map and the report prints them.
7. **Evidence of the key itself.** A committed fixture,
   `bench/oracle/testdata/cclang`, whose every pair is hand-computed,
   with its clang dumps committed beside it so the reader is tested
   without the image; the contained end-to-end run (the fixture, then
   `minic`) skips without the image, as the Java and Rust lanes do.
8. **The image gains clang** (Ubuntu 24.04's `clang`, 18.1.3, about
   0.3 GB): bench tooling in the one image (ADR-092), like the JDKs the
   Java oracle already uses.

## Consequences

- **§3.8's C row** reads *compiler-graded against clang's front end*,
  per cell, with the shared-front-end note. It licenses the repos
  graded, nothing wider (P11).
- **Recall prices the macro gap.** A call a macro's expansion makes is
  drawn to the macro, never to the function it calls (C-131), and
  every such pair is a `macro→…` miss. On a Unity-tested repo that is
  expected to be the largest class.
- **Not built, named:** a GCC arm; reading link units from the build, so
  a `link-ambiguous` site stays silent; C++.
- **How it was built:** the fixture, its truth and this ADR by the
  developer; the oracle by a dispatched session, reviewed and merged;
  the cells run on the host, contained.
