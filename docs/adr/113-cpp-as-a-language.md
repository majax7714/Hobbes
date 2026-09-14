# ADR-113 — C++ as a language: tree-sitter-cpp at lane A, scip-clang's C++ at lane B, clang's front end as its oracle — the eighth walk, through the harness

**Date:** 2026-09-14 · **Status:** accepted in direction; built unit by unit through the harness (ADR-107), each unit's build recorded below as it lands · **Owner:** Max · **Source:** Max, 2026-09-14: "add c++ as a supported language through the typical language addition flow".

Amends the architecture's **§3.1** (an eighth provider), **§3.2**
(the indexer's C++ face), **§3.7** (the eighth walk). It changes
nothing in **§3.8** until an oracle cell grades C++ (P11): through the
first two units C++ is *wired, not supported*. The C addition
(ADR-108, ADR-109, ADR-110) is the precedent, and this record follows
its order: lane A, lane B, the oracle, the cells and the row.

## Context

C-132 is the register's C++ entry: `.cc`, `.cpp`, `.cxx`, `.hpp` and
`.hh` are never discovered, and a C++ project's `.h` files are parsed
as C, so classes, templates and namespaces read as syntax errors.
Three facts fix the shape of the addition, all measured before this
record was written (2026-09-14, on the host and in the image):

- **Lane B exists already.** scip-clang (0.4.0, pinned in the image,
  ADR-109) is a C++ indexer first; it indexes whatever translation
  units the compile database names, and the database derivation
  (the repo's own, CMake's export, bear over make) does not care what
  language a unit is. Its monikers are `cxx` for both languages:
  `ns/Class#method(hash).`, a constructor `Class#Class(hash).`, a
  namespace `ns/`. The helper's `classify` and `terminalName` already
  read every one of those shapes (a method's disambiguator is any
  identifier, ADR-109; `<init>` was Java's constructor rule, and a C++
  constructor is named by its class already). The own-file rule for
  colliding statics is scoped to `cxx` monikers and so applies as it
  is.
- **Lane A is a new grammar.** tree-sitter-cpp 0.23.4 installs beside
  the pinned tree-sitter 0.25 and parses the shapes the walk needs:
  `namespace_definition`, `template_declaration`, `class_specifier`/
  `struct_specifier`, `function_definition` with a
  `qualified_identifier` declarator for an out-of-line member
  (`A::f(int) const`), `call_expression` whose `function` is an
  `identifier`, a `qualified_identifier` (`ns::h<int>`, `ns::A::s`),
  a `field_expression` (`a.f`, `p->f`, `this->s`) or a
  `parenthesized_expression` (`(*fp)`), `new_expression`,
  `lambda_expression`, `preproc_function_def`. Two test idioms read
  oddly and the walk must know it: gtest's `TEST(Suite, Name) {…}`
  parses as a `function_definition` whose declarator is
  `TEST(Suite, Name)` — a function named `TEST` — and Catch2's
  `TEST_CASE("…") {…}` as a `call_expression` followed by an `ERROR`
  block.
- **The oracle's front end is the same one, and its dump changes
  shape.** clang 18's `-ast-dump=json` for C++ gives: a member call as
  `CXXMemberCallExpr` whose callee is a `MemberExpr` carrying
  `referencedMemberDecl` (an id), not a `DeclRefExpr`; an operator
  call as `CXXOperatorCallExpr` with a `DeclRefExpr` callee; a
  constructor call as `CXXConstructExpr` with **no callee at all**,
  only `ctorType` (the signature) and the expression's type; a
  static-member or free-function call as C's `CallExpr` →
  `DeclRefExpr` → `CXXMethodDecl`/`FunctionDecl`. Every declaration
  carries `mangledName` (unique per entity, overloads included; a
  template's primary has none, its specialisations do), `virtual`,
  `isImplicit` (the compiler's own copy constructors and destructors,
  declared at the class), and a specialisation's `loc` is the
  template's own line. ADR-110's merge joins shards **by name** under
  C's linkage rules; in C++ a name is an overload set, so that key is
  wrong for C++.

## Decision

### 1. Lane A — `pipeline/src/hobbes/extract/cppsource.py` (unit 1; patch)

On the `csource`/`javasource` contract: the same bundle shape, so the
builder, the join and the schema change by zero lines (P7).

- **Files.** `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx` are C++.
  **A `.h` is claimed by C++ when the repo has C++ sources and (a) no
  `.c` sources at all, or (b) some C++ source includes it (by C's
  three include steps, ADR-108) and no `.c` source does.** Every other
  `.h` stays C, as today. The C walk skips the headers C++ claimed (a
  parameter on its discovery, nothing else in `csource` moves), and a
  mixed repo gets one `cpp-headers` degradation record naming how
  many `.h` went each way and the ones included from both languages
  (left to C). Pruned like C: `build/`, `cmake-build-*`.
- **Module ids:** a source drops its extension; a header keeps it
  (C's rule, for the same `foo.cpp`/`foo.h` reason). `foo.cpp` beside
  `foo.c` in one directory collides on the id `foo`: C-15's shape,
  recorded in a `parse` record, not guessed.
- **Symbols come from definitions only.** A free function with a body
  is `function`; a member function with a body — in-class or
  out-of-line — is `method`, with `qualname` the `::`-joined path
  (`ns::A::f`); a constructor and a destructor are `method`s named by
  the class (`A`, `~A`); an operator is a `method`/`function` named as
  written (`operator+`); a class, struct, union or enum with a body,
  a `typedef` and a `using` alias are `type`; a function-like macro
  is `macro`. A template declaration is the entity it declares, once,
  at its line. A namespace is not a symbol (it is the qualname's
  prefix). A lambda is below the floor (C-58's face): its body's
  calls attribute to the enclosing function. Prototypes, object-like
  macros and `using namespace` are not symbols.
- **Call sites** at the terminal identifier, five shapes: plain
  (`f(x)`), qualified (`ns::f(x)`, `A::s(x)`, `f<int>(x)`, the
  template arguments dropped), member (`a.f(x)`, `p->f(x)`,
  `this->f(x)`), dereference (`(*fp)(x)`), and construction —
  `new A(x)` and `A a(x)` / `A(x)` — named by the type's terminal
  (Java's `new Foo(..)` rule, ADR-096), so the two lanes meet on the
  class name. An operator applied by symbol (`a + b`) is not a site
  (C-63's face: the provider sees no call). A `TEST(S, N)` body's
  calls attribute to the test, below.
- **The fallback** resolves plain calls by name in C's three ranks
  (same-file function or macro; a macro in a directly included header;
  the unique non-static free function repo-wide) and qualified calls
  by the unique symbol whose qualname matches. **A name defined more
  than once at a rank is a tie and abstains** — that is an overload
  set, the C++ tail's `overload-set` class. A member call is never
  resolved by lane A: the receiver's type is lane B's to know (the
  Java precedent; `attr-call`). A name bound to a function pointer or
  a lambda is never resolved (`local-binding`).
- **Tests.** gtest's `TEST`, `TEST_F`, `TEST_P`, `TYPED_TEST` (the
  function-shaped definition whose declarator is the macro): a test
  named `Suite.Name`, framework `gtest`; Catch2's and doctest's
  `TEST_CASE("…")` and `SCENARIO("…")`: a test named by the string,
  framework `catch2`/`doctest` (the header the file includes decides
  which; neither seen → `catch2`); Boost.Test's
  `BOOST_AUTO_TEST_CASE(name)`: `boost-test`. C's `test_*` naming
  convention does not apply. A body the walk cannot attach a test
  symbol to (the `ERROR` shape after `TEST_CASE`) is counted in one
  `cpp-tests` degradation record per file, like C-134's.
- **The tail.** The six C++ extensions map to a new bucket `cpp`; a
  `.h` maps to `c` by extension **unless its coverage row says
  otherwise**: the C++ provider stamps `"language": "cpp"` on every
  coverage row it writes, headers included, and both the tail
  (`language_of`) and the proxy's copies (`langByExt` at its three
  lookups) prefer a row's language over the extension. That is the
  drift test's new clause. Builtins: C's pinned C11 list and
  `__builtin_*` apply to unqualified names, and a qualified call whose
  first qualifier is `std` is `builtin-name` (the standard library is
  a namespace, not a list). C++'s classes: fallback, local-binding,
  builtin-name, attr-call, overload-set, unclassified, below-floor.
- **The fixture** `pipeline/tests/fixtures/minicpp`: a namespace, a
  class with in-class and out-of-line methods, a constructor called
  three ways, a template, an overload pair, a static, a function-like
  macro, a lambda, a `.h` header, a gtest-shaped test file, and a
  Makefile that builds it with `g++` (the image has g++ and clang++
  18) — lane B's unit runs bear over it on this repo's own ingest, as
  `minic` does. Tests hand-compute its symbols, sites and fallback
  edges.
- **Version:** patch (a language addition is a patch even when it
  reaches "supported", ADR-103's notes). C++ is *wired, not supported*
  after this unit.

### 2. Lane B — scip-clang over the same derived database (unit 2; patch)

- A C++ source joins C's build-root grouping (`c_units`) and its
  plan: the same indexer, the same derivation order, the same
  containment profile (`index-c`). The helper's `cpp` language names
  C's indexer spec. A C++-claimed `.h` is staged with its root as any
  header is.
- **The decode is measured on `minicpp`, not assumed:** each C++
  moniker shape (a method, a constructor, an operator, a template
  specialisation, an anonymous-namespace function) is read against
  the fixture's sites, and any shape the helper mis-names gets its
  rule beside ADR-109's three, with a test. The expected finding is
  zero or one rule; the ADR is amended with the count.
- The join is unchanged: a C++ edge lane B resolves is `semantic`;
  lane A's fallback stays the floor.

### 3. The oracle — O10, clang's front end over the same dumps (unit 3; no version move)

Extends `bench/oracle/internal/clang` (ADR-110); `oracle c-clang`
takes `--lang cpp`, and `export.Exts["cpp"]` is the six extensions
plus `.h` (a header's ownership is the cell's module choice, as C's
is). The rules, oracle-grading.md's §7d:

- **Sites.** `CallExpr` as C; `CXXMemberCallExpr`, whose callee is
  the `MemberExpr`'s `referencedMemberDecl`, mode `static`
  (`virtual` on the declaration makes it mode `virtual`, with the
  declared method as the target — the front end names the static
  type's method, and no CHA is built for C++: an override Hobbes
  drew instead is a contradiction to be *measured*, not excused);
  `CXXOperatorCallExpr`, mode `operator`, the operator function its
  `DeclRefExpr` names (Hobbes draws no site there, so the cell reads
  it as recall, never precision); `CXXConstructExpr`, mode
  `constructor`, whose target is the constructor of the expression's
  type whose `type.qualType` equals the `ctorType`; an implicit
  constructor or destructor (`isImplicit`) is never a target and the
  site is dropped. The peeling, positions and macro rules are C's.
- **Declarations** carry `mangledName`, `virtual` and `isImplicit`;
  a `FunctionTemplateDecl`'s specialisations are declarations at the
  template's line.
- **Merge across units by `mangledName`** (C++'s linkage key: unique
  per entity, overloads told apart), falling back to C's name rule
  only for a declaration with no mangled name (`extern "C"` and
  `main`). `static` and anonymous-namespace functions resolve in their
  own unit, as C's do.
- **The fixture** `bench/oracle/testdata/cppclang`, hand-keyed as
  `cclang` is.

### 4. The cells and the row (the developer, host-run and contained)

Two cells on the clang keys: **fmtlib/fmt** (a header-heavy library
with a CMake build and its bundled gtest; chosen, because its code is
in `.h` files, the claim rule's hardest case) and **one repo drawn at
random** as ADR-110 drew C's. Every contradiction read. Then
`VERIFICATION_BASE`, the §3.8 row, `docs/extraction-evidence.md`, and
the register: C-132 narrowed or lifted with its residue named (mixed
repos' headers included from both languages; templates instantiated
across units; cgo's C-15 shape), and a new segment
`constraints/extraction-cpp.md` for what the walk concedes. That
commit is the patch that makes C++ *supported*.

## Consequences

- **Register** (each unit's commit): the `.h` claim (partial — the
  record says how headers were assigned); overloads abstain at lane A
  (surfaced, the tail class); member calls are lane B's (surfaced);
  operators applied by symbol are not sites (surfaced, C-63's face);
  lambdas below the floor (C-58's face, no new entry); tests the
  walk cannot attach (surfaced, the record); virtual dispatch graded
  to the declared method (O10's grain, in oracle-grading.md).
- **The image is unchanged.** g++, clang++ 18 and scip-clang are in
  it already. tree-sitter-cpp is a Python dependency, pinned
  `>=0.23.4,<0.24` beside tree-sitter's `<0.26`.
- **Three dispatched units** on Opus 5 (the checkout's model,
  ADR-107's 2026-09-14 amendment), turn budgets 200 / 150 / 200; the
  C precedent's lane A took two sessions at 74 and 68 turns ($7.50).
  Expected about $20 of subscription use across the three; the
  developer reviews each against `minicpp`, then fmt.
- **Versions:** unit 1 and unit 2 are patches (0.2.18-beta,
  0.2.19-beta); unit 3 moves nothing (`bench/`); the row is the third
  patch.

## Record

- **2026-09-14 — unit 1 (lane A) and unit 3 (the oracle) landed, in
  parallel from one parent (`7a805de`).**
  - **`S-20260914T161248Z-3d56`** (142 of 200 turns, 28 min, $18.67,
    Opus 5): `cppsource.py` as §1 wrote it, C's rules by import; the
    `.h` claim; the `cpp` tail bucket with a row-language override on
    both sides of the drift test; `minicpp`, seven files, building
    under `g++ -Wall`. Gate clear (15 files, 0.0% uncaptured), verify
    pass (1,575 tests, 65 new). Nine deviations, all the grammar's: a
    temporary `A(x)` is a plain call; an unqualified `f<int>` is plain;
    a construction site is never resolved by lane A; a qualified call
    is matched against the enclosing scope's prefixes first; `p->f()`
    classes `unclassified` (the tail's shape read, a gap C shares);
    the named casts draw no site; a gtest/Boost test gets a
    file-local symbol so its body attributes. Merged `3030ac7`.
  - **`S-20260914T161308Z-a848`** (139 of 200 turns, 25 min, $16.08):
    O10 as §3 wrote it, with a per-unit id table for member calls, the
    mangled-name merge, and `--lang`/`--clangxx`; `cppclang` hand-keyed
    at 25 sites over 4 units. Seven deviations, all the dump's own
    shape (§7d). Merged `1f81412`; the oracle lane's host suite 95
    pass / 5 skip, the C++ end-to-end test included.
  - **The cost** was far above the estimate: $34.75 for two of the
    three units against "about $20 for three". Both doers spent their
    turns reading and probing before writing (lane A's first edit at
    2.5 min was a grammar probe). Unit 2's budget is Max's call.
  - **The host read, fmtlib/fmt at `3a0661d7`** (lane A, and lane B by
    the way: fmt has one `.c` file, so its CMake root indexed every
    unit, C++ included — lane B works for C++ wherever a root has a C
    file, and unit 2 makes it deliberate): 73 C++ files; 884 types,
    1,451 methods, 1,325 functions, 418 macros; 645 gtest tests found;
    18,156 sites, 2,992 semantic and 299 syntactic call edges; tail:
    7,628 below-floor, 2,131 unclassified, 879 attr-call, 386
    builtin, 137 overload-set. The `cpp-headers` record read 25
    headers to C++ and 1 to C (`fmt-c.h`, included from both). **Two
    findings for the register:** every library header parsed with
    ERROR nodes (macro-spelled declarations; C-145), and an overload
    set trips C's duplicate-definition rule, so only the first overload
    is a symbol and lane B's answers to the rest land below the floor
    (C-144, **unit 2's first defect**).
  - **Register:** C-142–C-147 in `constraints/extraction-cpp.md`;
    C-132 narrowed. **Version:** 0.2.18-beta. **The draw** for the
    second cell was made and recorded (§7d of oracle-grading.md):
    Taywee/args.
- **Remaining:** unit 2 (lane B deliberate for C++-only roots, the
  overload symbol ids and the duplicate record's wording, the decode
  measured on `minicpp`), then the two cells and the §3.8 row.
