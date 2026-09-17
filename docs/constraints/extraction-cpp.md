# Extraction — C++ (ADR-113)

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

C++ joined at lane A on 2026-09-14 (ADR-113 §1, 0.2.18-beta): a
tree-sitter-cpp walk on `csource`'s contract. Lane B (scip-clang over
the same derived compile database) was made deliberate the same day
(§2, 0.2.19-beta). Its two oracle cells (fmt and args, 2026-09-15)
found two rules the decode and the join needed (C-151, C-152, 0.2.22-beta).
Its §3.8 row landed on them (0.2.23-beta): C++ is *supported* as far as
that row reaches (P11). The first entries below were written from the
walk's first host read, fmtlib/fmt at `3a0661d7` (2026-09-14): 26
headers claimed, 25 to C++ and 1 to C, and every one of its 21 library
headers parsed with tree-sitter ERROR nodes.

### C-142 — A `.h` is claimed by its includers, never by the build

- **Cannot tell you:** which language a `.h` is written in. A repo
  with C++ sources and no `.c` reads every `.h` as C++; a mixed repo
  reads a `.h` as C++ only when a C++ source includes it (by C's three
  include steps, C-133) and no `.c` does. A header both languages
  include stays C; so does one no source includes at all in a mixed
  repo.
- **Because:** the build's own `-I` and `-x` flags, which would settle
  it, are not read at lane A (C-133). The include graph is the only
  evidence the walk has.
- **Bites at:** a mixed repo whose C++-only headers are reached through
  a C-included umbrella; a header-only C++ library with a C shim header
  (fmt's `fmt-c.h`, included from both, left to C: its declarations
  parse as C's).
- **You find out:** **partial** — a mixed repo draws one `cpp-headers`
  degradation record naming the counts and every header left to C by
  the both-languages rule; a pure repo draws none, and nothing says
  "every `.h` was read as C++".
- **Provider (P9):** none; the rule is Hobbes's own.
- **Source:** ADR-113 §1; measured on fmt (25 to C++, 1 to C).

### C-143 — Lane A abstains on every overload set and never resolves a member call

- **Cannot tell you:** which overload a plain or qualified call names,
  or what a member call (`a.f()`, `p->f()`, `this->f()`) lands on. A
  name defined more than once at a fallback rank is a tie and abstains
  (`overload-set`); a member call's receiver type is lane B's to know.
- **Because:** overload resolution and member lookup need types, which
  a syntax walk does not have (the Java precedent, ADR-096).
- **Bites at:** every C++ site lane B does not answer: a root with no
  derivable compile database or a failed build (C-135's C++ face), a
  file outside the database, a definition lane A lost to a parse error
  (C-145). On fmt, overload sets are the norm in every header.
- **You find out:** **surfaced** — `overload-set` and `attr-call` in
  the tail; a member call written `p->f()` or `this->f()` classes
  `unclassified`, not `attr-call`, because the tail's shape read looks
  at the character before the name and `>` is not one of its markers —
  a gap C's tail shares, left as is so a C++ unit moves no C number.
- **Source:** ADR-113 §1; the doer's deviation list (`3d56`).

### C-145 — Macro-heavy C++ parses with error nodes: the preprocessor never runs (C-131's C++ face) — *narrowed 2026-09-17 (ADR-129, 0.2.41-beta): a lost definition is read from the index, as a target*

- **Narrowed (0.2.41-beta, ADR-129).** Where lane B ran, a function,
  method or type definition this parse lost becomes a graph symbol read
  from scip-clang's own definition row (`declared_by: "scip"`), so the
  calls lane B already resolved there draw instead of falling
  `below-floor`. fmt: 1,690 symbols in 26 files, **3,269 → 6,510 confirmed
  call edges at 0 contradicted, recall 14.5% → 29.1%**; args 1,995 →
  2,062, recall 56.4% → 58.6%; cJSON and sqlite-vector mint 1 and 3
  named types and their exports do not move (§10.13). The rule refuses —
  and counts, in `graph.json`'s `minted.refused` and on the ingest
  summary — a file that parsed clean, a `term`/`macro`/`namespace` row,
  a definition inside a function body, a line with several monikers, a
  lane A symbol of the same name within three lines, a declaration (no
  `{` before a `;` in the file's own text), an unnamed struct's invented
  name, and a type lane A already names at another line. **What stays
  conceded:**
  - **A minted symbol is a target, not a scope** (`end_line` is its
    line). A call written *inside* a lost definition keeps the caller it
    had — the enclosing symbol lane A did parse, or the module. Finding a
    body's end through unexpanded macros is a guess not made. `who_calls`
    says so on every minted symbol.
  - **Its name is the compiler's spelling**, so an inline namespace
    appears (`fmt::v12::detail::write`) where lane A's neighbours in the
    same file may lack the namespace a macro opened; a constructor of a
    class template is spelled with its parameters (`typed_node<T>`); and
    an id collision takes `~b2`, `~b3`, never lane A's `~2`.
  - **A lost macro is still lost** (2,554 below-floor facts on fmt), and
    with no lane B nothing is minted (P6): everything below still
    describes a root with no compile database.
  - **It draws what the index says**, so C-153's wrong candidates at a
    call in a template draw too. ADR-130's R-arity withholds the ones the
    source text contradicts; C-153 carries the rest.

- **Cannot tell you:** the declarations inside a region tree-sitter-cpp
  could not parse. A declaration spelled through macros (`FMT_API`,
  `FMT_CONSTEXPR`, `FMT_BEGIN_NAMESPACE`, attribute and export macros)
  is not C++ to the grammar; the parse recovers with ERROR nodes, the
  sites it still sees are kept, and the symbols inside the unparsed
  region are lost.
- **Because:** the preprocessor never runs at lane A (C-131), and
  tree-sitter-cpp's recovery is per node, not per macro.
- **Bites at:** library headers in the modern style — every one of
  fmt's 21 library headers and 5 of its sources parsed with errors.
  Lane B does not share the gap, since scip-clang runs the preprocessor,
  but it cannot draw what it knows. Measured once lane B joined
  (0.2.19-beta): 6,896 of fmt's 7,376 below-floor call facts point at a
  definition in a file that parsed with errors, with no lane A symbol
  near it (3,375 in the vendored `gtest.h`, 2,398 in `format.h`). Lane
  B names the callee, and the graph has no symbol to draw it to. This,
  not the overload rule (C-144, lifted), is C++'s below-floor mass.
- **You find out:** **surfaced** — a `parse` degradation record per
  file, the same record C draws, and each such site's `below-floor`
  class in the tail.
- **Provider (P9):** tree-sitter-cpp **0.23.4**.
- **Source:** the fmt read, 2026-09-14; the below-floor diagnostic after
  `be34`'s merge, the same day.

### C-146 — An operator applied by symbol and a named cast are not sites

- **Cannot tell you:** that `a + b` calls `operator+`, or that
  `static_cast<T>(x)` is not a call. The walk records no site for an
  operator applied by symbol (the provider sees no call, C-63's face),
  and the four named casts parse as calls of a template function and
  are recorded as no site.
- **Because:** an operator call has no callee identifier at the site;
  the named casts are keywords the grammar reads as templates.
- **Bites at:** operator-heavy code (fmt's iterators and buffers). The
  oracle records an operator call as its own mode (`operator`, O10),
  so the cell reads these as recall, never precision.
- **You find out:** **surfaced** — in this entry and O10's coverage
  buckets; nothing at the site.
- **Source:** ADR-113 §1 and §3.

### C-147 — A test body the parse leaves in an error node is counted, not read

- **Cannot tell you:** the calls a Catch2 or doctest `TEST_CASE("…")`
  body makes when the grammar leaves the body in an ERROR node after
  the call-shaped macro. gtest's and Boost.Test's function-shaped
  definitions parse, and their bodies attribute to the test.
- **Because:** `TEST_CASE("…") { … }` is a call expression followed by
  a compound statement the grammar cannot attach.
- **Bites at:** test reach for Catch2 and doctest suites.
- **You find out:** **surfaced** — one `cpp-tests` degradation record
  per file, like C-134's.
- **Source:** ADR-113 §1.

### C-148 — A moniker one file defines at several lines has no lane B answer in C++

- **Cannot tell you:** which of several definitions a reference means
  when scip-clang gives them one moniker in one file. Two shapes do
  this: a class template and its specialisations (`float_info#` at
  `format.h:1677` and `:1691`), and `enable_if` overloads its
  signature hash does not tell apart (`is_negative(ee44…).` at 1151 and
  1155). Such a reference draws no lane B edge. Lane A's fallback floor
  stands there, and it abstains on overload sets (C-143).
- **Because:** the moniker is all the index gives, and scip-clang lists
  the definitions in an order that varies by run. Choosing one would be
  a guess, and until 0.2.20-beta the guess followed that order: three
  fmt ingests drew 3,308, 3,298 and 3,293 call edges.
- **Bites at:** template-heavy code. On fmt: 240 monikers, 2,228
  references.
- **You find out:** **surfaced** — one `scip-decode` record per ingest
  counting the monikers and the references, with examples.
- **Provider (P9):** scip-clang **0.4.0** — its moniker for a
  specialisation, and for overloads whose signature hash is equal.
- **Source:** ADR-113 §2's determinism amendment; `3d1a`, 2026-09-14.

### C-151 — A call site whose references name several overloads has no lane B answer
- **Cannot tell you:** which overload a call means where scip-clang
  references more than one at the site. scip-clang lists the candidates
  of a call in a template it cannot resolve there, and one unit can
  answer differently from another. Such a site draws no lane B edge.
  Lane A abstains on the overload set (C-143), and in a file lane B
  indexed lane A draws nothing anyway (C-152).
- **Because:** until 0.2.22-beta, ADR-109's one-target-per-site rule
  kept the smallest line, reading several lines of one file as one
  definition's `#if` alternatives. In C++ they are different overloads,
  and the first is often not the one meant. The edges drawn at such
  sites were 36 wrong and 75 right on fmt, and 4 wrong and 9 right on
  args (ADR-113 §2's third amendment).
- **Bites at:** template-heavy code: fmt's 634 such sites and args' 14.
  The right edges go with the wrong ones.
- **You find out:** **surfaced** — one `scip-decode` record per ingest
  counts the sites, with examples.
- **Provider (P9):** scip-clang **0.4.0**, its references for a call it
  does not resolve.
- **Source:** the fmt and args cells (`docs/oracle/cells/`), 2026-09-15;
  ADR-113 §2's third amendment.

### C-152 — In a C++ file lane B indexed, a site lane B leaves unanswered draws no edge
- **Cannot tell you:** lane A's name-only guess at a call site in a C++
  file scip-clang compiled, where lane B has no answer. The site stays
  unresolved, and the tail classes it as if lane A had no guess.
- **Because:** lane A's fallback is C's, namespace-blind ranks by name.
  In a compiled C++ file, lane B's silence mostly means one of two
  things. The callee may lie outside the repo: scip-clang records no
  occurrence for most libc calls in a C++ unit, so ADR-111's veto
  cannot fire. Or lane A lost the real definition to a parse error
  (C-145), so its "unique" match was not. On fmt the fallback drew 182
  judged edges in such files before 0.2.22-beta: 108 right and 74 wrong
  (59%). Lane A's guesses still feed lane agreement.
- **Bites at:** a call lane B could not settle inside a compiled file:
  C-148's and C-151's abstentions, tu-split sites, and a libc call,
  which lane B places nowhere. fmt lost 108 right edges.
- **You find out:** **surfaced** — `lane_agreement.cpp_withheld` counts
  the sites, with examples, and one `cpp-fallback` degradation record
  per ingest names the count. A C++ file lane B did not index keeps its
  fallback (C-135's C++ face).
- **Amended 2026-09-17 (ADR-123, 0.2.36-beta): a disagreement in a
  compiled C++ file no longer fails `hobbes lanes`.** Such a row carries
  the shape `cpp-withheld` and, when every row is shaped, the command
  exits 3, not 1. The residual is owned here: in these files the self-test
  can no longer fail on a row where *lane B* is the wrong lane (C-153's
  kind of error lives in exactly these files). The row is still listed
  and counted, and the report prints lane A's C++ disagreement rate with
  the number of the same guesses drawn in C++ files lane B did not index
  (`cpp_disagreements`, `cpp_sites_compared`, `cpp_guess_drawn`).
- **Source:** fmt's cell, 2026-09-15; ADR-113 §2's third amendment;
  ADR-123.

### C-153 — scip-clang's one answer at a call in a template can name the wrong declaration
- **Cannot tell you:** that a semantic C++ edge from a call in a
  template, or from a call qualified through another specialisation, is
  the declaration the compiler picks when it instantiates the template.
  Where scip-clang gives a single reference, the graph takes it.
- **Because:** scip-clang indexes a template's pattern once. A call it
  cannot resolve there gets the lookup's candidates, where C-151
  abstains, or a single candidate. Measured shapes, all on fmt:
  - the caller's own specialisation's member for another
    specialisation's: `formatter<int>::format` drawn to
    `formatter<type_with_get>::format` (4 edges);
  - an explicit specialisation's member for the primary template's:
    `test_format<20>::format` drawn to `test_format<0>` (4);
  - one overload of two (2).
- **Narrowed again 2026-09-17 (ADR-130, 0.2.41-beta): R-arity.** A C++
  call lane B answered, written with **more arguments than the target's
  declarator can take**, draws no edge; the site is tailed
  `arity-mismatch`. Only "too many" (a default argument lives on a
  declaration elsewhere, so "too few" proves nothing — it would have
  withheld 152 confirmed edges on fmt), and only where both counts were
  read: a pack expansion, a braced initialiser, a variadic or
  macro-spelled parameter list, an ERROR node read *unknown* and the edge
  is drawn. Found by ADR-129's hand read: its mint gave `format.h:549`'s
  two-parameter `copy` a node and 35 `copy<Char>(begin, end, out)` calls
  drew onto it, none of which the key can judge. On fmt the rule
  withholds exactly those 35 and 5 edges that were already standing
  (`holds_alternative<T>(value)` ×2 and `any_cast<T>(value)` ×2 onto
  gmock's zero-parameter ADL stubs, `scan.h:466`'s three-argument `read`
  onto the two-parameter one), and **no confirmed edge** (§10.14); args
  none. **Its residual:** a wrong candidate of the same or greater arity.
  One is known: `format.h:2387`'s `write<Char>(out, unsigned, specs, loc)`
  drawn to the enclosing `Char` overload itself, unjudged under H-30.
- **Narrowed 2026-09-17 (ADR-125, 0.2.37-beta): R-qual.** A call written
  through one specialisation (`X<A>::f`) that lane B resolved to a
  member of a *different* explicit full specialisation (`template <>`,
  `X<B>::f`) draws no edge; the site is counted `qualifier-mismatch`.
  On fmt it withholds the first two shapes, all eight, and no confirmed
  edge (§10.11). A `template <>` header a macro parse lost (C-145) is
  still read, from the ERROR node's exact tokens. **The rule's own
  residuals:** a written argument the owner spells differently (an
  alias, a default argument, an expression: `<string_view>` for
  `<basic_string_view<char>>`, `<int>` for `<int, char>`, `<2*10>` for
  `<20>`) would withhold a right edge (measured 0 on fmt and args); a
  wrong answer at an owner that is a primary template or a partial
  specialisation is not caught.
- **Bites at:** fmt, 3 known wrong edges since 0.2.41-beta — the
  `format_as` rows at `std.h:714` and `:726` and `format.h:2387`'s
  `write` — all unjudged under H-30 rather than fixed; 10 before
  ADR-125. args none. fmt reads 100% (6,510/6,510) where the strict
  figure (ADR-124), counting its 27 line-unresolved rows as
  contradicted, is 99.59% (6,510/6,537); both are in `tables.md`. Of the
  19 unjudged rows the mint added, 18 read as right by hand and the
  `write` row as wrong; of its 192 rows at sites the key holds no
  targets for, a seeded sample of 30 read as right, all 30.
- **You find out:** **partial** (since 0.2.38-beta, ADR-125 §4) —
  `who_calls` marks each semantic C++ call edge that starts in a
  template pattern (a function template, or a member of a class
  template or partial specialisation), and one `cpp-template-sites`
  record in `list_blind_spots` counts them (fmt: 854 of 4,423 at
  0.2.41-beta, 596 of 2,811 before ADR-129; the remaining `format_as`
  rows among them). It marks the region, not the
  wrong edge: nothing at the site tells a wrong answer from a right one.
  Not marked: a pattern whose `template <…>` a macro parse lost (C-145),
  and a method of a class nested in a class body (no lane A symbol). The
  strict figure (ADR-124) counts the unjudged rows again. What R-qual
  withholds is tailed `qualifier-mismatch`, what R-arity withholds
  `arity-mismatch`.
- **Provider (P9):** scip-clang **0.4.0**.
- **Source:** fmt's cell, 2026-09-15.

### C-160 — Lane A's C++ file cache fingerprints the extraction code and the grammar's version, not the grammar's build

- **Cannot tell you:** that a C++ file's lane A facts read from the file
  cache (ADR-128) are what this box's parser would produce now, when the
  native `tree-sitter` or `tree-sitter-cpp` library was rebuilt or
  swapped at the same installed version, or when code outside
  `hobbes/extract/` that the per-file walk comes to reach changes (the
  walk reaches none today).
- **Because:** the key is a format tag, the name and bytes of every
  `hobbes/extract/*.py`, the two distributions' installed versions, the
  repo-relative path and the file's bytes. Hashing the compiled grammar
  itself would cost every lookup a read of the shared library for a
  case a version bump already covers; a missing version turns the cache
  off for the process rather than guessing.
- **Bites at:** an editable or locally built grammar at an unchanged
  version number; a checkout whose extraction imports a helper from
  outside `hobbes/extract/` into the per-file walk.
- **You find out:** **surfaced** — every ingest that read a C++ file
  prints `lane A C++ file cache: <hits> hit, <misses> miss (…;
  HOBBES_LANEA_CACHE=0 to parse afresh; C-160)` under the timings, and
  the timings log line carries the counts. The artifact carries nothing:
  a hit is byte-identical to a parse (measured on ScummVM, 217 MB).
- **Source:** ADR-128; the measurement of 2026-09-17.

## Lifted constraints in this segment

A lift keeps its number, the limit as it stood, the technique that
lifted it, and the residual edge cases where the old concession
survives. Field key: `README.md`, "How to read a lifted entry".

### C-144 — One symbol per qualified name per file: an overload set's later definitions were below the floor — *lifted 2026-09-14, the day it was registered*

- **Was:** C's rule (ADR-108: the first definition in file order is
  the symbol, the rest a `parse` record naming preprocessor
  alternatives) applied to C++ unchanged. So only an overload set's
  first definition was a symbol, and a call lane B resolved to any of
  the others landed nowhere (`below-floor`). The record called code
  that was fine a duplicate ("an overload set, or preprocessor
  alternatives").
- **Lifted by — the technique:** a C++ dedupe of its own
  (`cppsource._dedupe_symbols`, ADR-113 §2's amendment; `be34`,
  0.2.19-beta). A later `function` or `method` definition of a qualname
  whose signature differs (the declarator's parameter list and the
  qualifiers trailing it, whitespace-collapsed) takes `~2`, `~3`, … in
  source order, Java's rule (ADR-096). A repeat with the same signature
  is C's duplicate still, and the record names preprocessor
  alternatives only. The fallback keys on the bare qualname, so an
  overload set is still a tie (C-143), and lane B's answer lands on
  each overload's own line. Verified on `minicpp`: `shapes::area(2.5)`
  at `main.cpp:12` is semantic on `shapes::area~2` (the `lane_b` test).
- **Residual edge cases:** the signature is text, so two `#if`
  alternatives that spell one parameter list differently (a renamed
  parameter, a typedef for its type) read as overloads. Both become
  symbols, and lane B answers only the configured one. A `~n` follows
  source order, so an overload inserted above another renumbers it. On
  fmt the lift moved 271 below-floor sites (7,628 → 7,357); the rest is
  C-145's.
- **Source:** the fmt read and `be34`, 2026-09-14.

### C-155 — A call drawn inside an unevaluated operand, which the compiler never calls — *lifted 2026-09-16, the day it was registered*

- **Was:** a C++ `calls` edge whose site lay inside an **unevaluated
  operand** — `decltype(...)`, and the same shape in `sizeof`, `alignof`,
  `noexcept` and a requires-expression — was drawn although the operand
  is never evaluated and no call is emitted. Lane B's index records an
  occurrence of the name there, lane A's walk saw `arg("arg", 42)` as a
  call expression wherever it stood, and the join read the two as a
  call. Registered from fmt's `test/compile-test.cc:127`
  (`compile<decltype(fmt::arg("arg", 42))>(…)`), the cell's one
  contradiction that was Hobbes' own and not scip-clang's; the entry's
  "27 edges on `decltype(` lines" was an upper bound. **Unsurfaced**
  while it stood.
- **Lifted by — the technique** (ADR-121 §1, `cppsource._unevaluated`,
  `S-20260916T225041Z-d95c`, 0.2.33-beta): lane A records no call site
  whose node has an ancestor `sizeof_expression`, `alignof_expression`,
  `decltype` or `requires_expression`, or a `call_expression` whose
  callee is the bare identifier `noexcept` — the provider sees no call,
  the rule the named casts and the operators already follow. `noexcept`
  and `typeid` in call position, which the grammar spells as a call of
  a bare identifier, record no site of their own. The join and the tail
  do not move: lane B's occurrence at such a site falls through as a
  `uses` edge at semantic tier, which is the true statement (the file
  depends on the declaration to type-check) and is not a call.
  Measured before the decision: fmt had 49 such sites (all `decltype`)
  of which exactly one drew a graded edge; args 7, none drawing; the
  lift moves one row on the two cells and nothing else.
- **Residual edge cases:**
  - **`typeid`'s operand keeps its sites.** `typeid(f())` evaluates its
    operand when it is a glvalue of polymorphic class type
    ([expr.typeid]/3), which lane A cannot type; a site there is right
    in that case and a call the program never makes otherwise. The
    oracle keeps the same rule (ADR-121 §3), so a contradiction there
    is a real disagreement.
  - **An operand a macro spells** — `MACRO(f(x))` whose body is
    `decltype(…)` or `sizeof(…)` — is read as a call inside a macro
    argument, and drawn: the macro gap, C-131.
  - **C's walk abstains too** (ADR-121 §1's amendment, 0.2.34-beta,
    `S-20260916T231525Z-367f`): no site under a `sizeof` or `_Alignof`
    operand, so a `.h` C++ did not claim (C-142's face) reads the same
    rule under C's walk. C's residual is its own: C11 6.5.3.4 evaluates
    a `sizeof` operand whose type is a variable-length array
    (`sizeof(int[n()])` calls `n`), which the syntax cannot tell from any
    other, so that call is dropped with the rest. 0 such sites on cJSON,
    sqlite-vector and `minic`.
  - **A constant expression is not unevaluated** — `static_assert(g())`,
    a `noexcept` specifier's own condition, `alignas(N)` — and keeps its
    sites, as the compiler evaluates it and clang's dump holds it.
  - **The oracle's own half, H-32, is fixed** (`S-20260916T230256Z-5261`,
    ADR-121 §3): O10's reader drops and counts a call under a `sizeof`,
    `alignof`, `noexcept(..)` or requires-expression
    (`sites_unevaluated` in coverage) and keeps `typeid`'s, the same list
    as the lane's. On fmt the re-run key lost 6 sites, all `sizeof`
    operands, and no judgement moved; the lane and its key now hold one
    rule for what an unevaluated operand is.
- **Source:** H-31's trace, 2026-09-16 (the concession); ADR-121 and
  `S-20260916T225041Z-d95c` (the lift).
