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

### C-145 — Macro-heavy C++ parses with error nodes: the preprocessor never runs (C-131's C++ face) — *narrowed 2026-09-17 (ADR-129, 0.2.41-beta): a lost definition is read from the index; narrowed again 2026-09-18 (ADR-134, 0.2.46-beta): a lost function's extent is read from the file's braces, and what is written inside it is drawn from it*

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
  - **A minted function or method is a scope only where its braces could
    be read (ADR-134, 0.2.46-beta).** scip-clang's index carries no
    extent, so `end_line` is the closing brace matched in the file's own
    text (comments and literals blanked), the symbol says `extent:
    "braces"`, and a `calls` or `uses` fact written inside is drawn from
    it. fmt: 1,346 extents, **1,290 of the 1,436 `calls` rows that were
    drawn from the module now name a function — 1,218 the one clang
    names, 30 the same function in another spelling, 23 a lambda's
    encloser, 19 where the key has no site; none wrong, and no row that
    was right moved**; args 15 of 15. **No grade says so**: every C and
    C++ key judges `(site, target)` and never a caller, so the check is
    the key's caller names read by a driver, not a grade
    (`oracle-grading.md` §10.19). **What stays conceded — the node is a
    target only, and a call inside it keeps the module or the enclosing
    lane A symbol as its caller — where the extent is refused**, counted
    in `graph.json`'s `minted.extents` and on the ingest summary, and
    said by `who_calls` on the symbol:
    - a preprocessor conditional inside the body (34 on fmt): either
      branch may hold the brace the compiler saw;
    - another function's line inside the match (19 on fmt): 13
      macro-generated methods (`GTEST_REPEATER_METHOD_(OnTestStart,
      TestInfo)` has no `{` in the text, and the match ran into the next
      function written out), 6 true bodies holding a C-164 symbol;
    - a minted **type**, always (its members are symbols of their own);
    - and a definition nothing names at all — the mint's own refusals —
      which has no node to be a scope. On fmt 188 `calls` rows still say
      the module where clang names a function: 111 under a refused
      extent, 63 under no symbol, 11 where lane A parsed the function and
      lost its end, 3 lambdas.
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

### C-146 — An operator applied by symbol is a call only outside a template, where the index names it at the token; a named cast is not a site

- **Cannot tell you:** that `a + b` calls `operator+` where the
  expression sits **inside a template**, inside a macro's expansion, or
  where scip-clang emits no reference at the operator token; that
  `f(x)` on an object calls its `operator()`; that `"x"_a` calls a
  literal operator; or that `static_cast<T>(x)` is not a call (the four
  named casts parse as calls of a template function and are recorded as
  no site).
- **Because:** an operator call has no callee identifier at the site,
  and a built-in operator is no call at all — lane A cannot tell the two
  apart, so an operator is never a site of its own. The named casts are
  keywords the grammar reads as templates.
- **Narrowed 2026-09-17 (ADR-131, 0.2.42-beta).** Lane A records each
  operator **token** (binary, unary, pointer, update, assignment and
  compound assignment, subscript, `->`), packed and never as a site, and
  the join draws a semantic `calls` edge where lane B's reference named
  `operator…` sits at exactly that token's line and column with the same
  spelling, **outside any `template_declaration`** and outside an
  unevaluated operand. Measured before it was built
  (`oracle-grading.md` §10.15): fmt +392 call edges, 391 confirmed, 0
  contradicted, no new row the key cannot judge, recall 29.1% → 30.1%;
  args, held out, +136, all confirmed, 58.6% → 62.5%; C untouched.
- **Why not inside a template:** scip-clang answers a dependent operator
  with its single by-name candidate (C-153) — `wday == 0` onto
  `basic_fp`'s `operator==`, `it != c.end()` onto gtest's `faketype`
  stub — at the same arity, so nothing in the source contradicts it. On
  fmt every one of the 45 `line-unresolved` and 116 of the 117
  `no-targets` rows a naive rule adds is inside a template, and about
  100 of them read wrong by hand. The price is the 175 rows the key
  confirms there (4 on args). **Since 0.2.43-beta (ADR-131 amended)
  such a reference draws nothing, not a `uses` either** — C-153's entry
  has the measurement — so those 175 are given up as dependencies too.
- **Residuals:** a `template <…>` header a macro parse lost (C-145)
  leaves its tokens flagged plain — the measurement was made with the
  same blind spot, and found none on either cell; a reference positioned
  at a macro invocation's name (3,011 of fmt's 4,015 operator
  references: gtest's `operator=` and `operator<<` inside `EXPECT_EQ`)
  is the macro class (C-131), not drawn; a token directly under an ERROR
  node is not recorded.
- **Bites at:** operator-heavy template code (fmt's iterators and
  buffers). The oracle records an operator call as its own mode
  (`operator`, O10), so the cell reads these as recall, never precision.
- **You find out:** **surfaced** — the ingest summary's `operators:`
  line and `graph.json`'s `operators` block count the tokens drawn and
  the references inside a template **withheld** — neither a call nor
  a `uses` since 0.2.43-beta (fmt: 551 and 437; args: 140 and 40); O10's coverage buckets; nothing at the site.
- **Source:** ADR-113 §1 and §3; ADR-131.

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
- **Narrowed a third time 2026-09-17 (ADR-131 amended, 0.2.43-beta;
  Max: route a): the same shape on `uses` edges, withheld at an operator
  token.** A lane B reference no call site claims is drawn as a `uses`
  edge (ADR-029), and at a dependent operator in a template that
  reference is scip-clang's single by-name candidate: on fmt about 100
  of the 437 operator references ADR-131 left as `uses` named the wrong
  declaration (`wday == 0` → `basic_fp`'s `operator==`;
  `it != c.end()` → gtest's `faketype` stub), and no key grades `uses`.
  A reference named `operator…` at exactly a lane A operator token
  inside a template now draws **nothing**. Measured first, then built
  equal to the probe (§10.16): fmt −156 `uses` symbol edges, args −24,
  none added, no graded row moved; **one module edge went on each cell
  and both were wrong** — `test/scan.h → include/fmt/format.h` stood only
  on integer `n * 10` read as `fp`'s `operator*`, `args.hxx →
  test/test_common.hxx` only on `ss >> destination` read as the test's
  `operator>>`. **The price:** the right candidates go with the wrong
  ones (the key confirms 175 of fmt's in-template rows as calls; they
  were true dependencies). **Its residual:** a dependent reference that
  is *not* at an operator token — a named call, a type, a construction —
  still stands as `uses` wherever no call site claims it, ungraded; and
  a `template <…>` header a macro parse lost flags its tokens plain
  (C-146's residual), so a wrong candidate there is drawn as a call.
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
  `arity-mismatch`; the operator references withheld inside templates
  are counted on the ingest summary's `operators:` line and in
  `graph.json`'s `operators.in_template`.
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

### C-162 — A construction is a call only where a call site names it, or the index names the constructor at a construction token outside a template

- **Cannot tell you:** that a construction calls its constructor where
  it sits **inside a template**; inside a macro's expansion (gtest's
  `Message` and `AssertHelper` at `EXPECT_EQ`'s own name: 80% of fmt's
  missed constructions, C-131); where it has **no token** — an implicit
  conversion (`return style_ & 0x3FFFFFF;` into a `color_type`,
  `fmt::format(loc, …)` into a `locale_ref`); where scip-clang emits no
  reference at all (a dependent type's construction; the literals inside
  a braced list — 484 `EitherFlag` rows on args); at a base-class or
  delegating initialiser (`Base<T>(args)`); at a default member
  initialiser in a class body; or at a declaration under a label.
- **Because:** `T x(args);`, `T x{…};`, `T x;`, `m_(args)`, a braced
  argument, `T{…}`, `new T(…)` and `T p = {}` have no callee identifier —
  the written name is a variable, a member, a brace or a type — and
  `int x(3);` is the same syntax and no call. Lane A cannot tell the two
  apart, so a construction is never a site of its own; only `T(args)` is.
  This was true from ADR-113 and stood unregistered until ADR-132's
  measurement read it (2026-09-17).
- **Narrowed the day it was registered (ADR-132, 0.2.44-beta).** Lane A
  records each construction **token** (the declared name of `T x(args)` /
  `T x{…}` / `T x;` in a declaration that names a type and sits directly
  in a block or at namespace scope; the member name opening a member
  initialiser; the `{` of a braced argument or return; the `=` of a
  defaulted parameter; the type's start in `T{…}` and `new T(…)`), packed
  and never as a site, and the join draws a semantic `calls` edge where a
  lane B reference **onto a constructor** (its definition row's moniker
  ends `T#T(…)`) sits at exactly that token, **outside any
  `template_declaration`** and outside an unevaluated operand. Measured
  before it was built (`oracle-grading.md` §10.17): fmt +116 rows, 92
  confirmed, 0 contradicted, the 24 the key could not judge read right by
  hand, recall 30.1% → 30.3%; args, held out, +369, all confirmed, 62.5%
  → 72.9%; C untouched.
- **Why not inside a template:** every other in-template answer on this
  lane has needed a guard (C-153). Here the 45 in-template rows the rule
  would add (44 on fmt, 1 on args) read right — a dependent type's
  construction gets no reference at all, so what the index does emit in
  a template is a non-dependent type's — and that is 45 rows, not a
  proof. They stay the `uses` edges they were, which is a true statement
  either way. Put to Max.
- **The using-declaration residual, found by the build's grade —
  closed at 0.2.45-beta (ADR-133, C-163):** the join now claims by
  position, and the 19 rows below are drawn and confirmed (fmt 6,993 →
  7,012). As it stood: where a
  file says `using fmt::detail::bigint;` and then `bigint n(0);`, lane B
  gives two references named `bigint` on the line — the using-declaration
  at the type, the constructor at `n`. Lane A's existing construct site
  takes the nearer one, which is below the floor, and the join's claim is
  by `(file, line, name)`, so the constructor's reference never reaches
  the rule. 19 key-confirmed rows on fmt (`bigint` ×14, `file` ×5), none
  on args. It draws nothing, not something wrong; the fix is the join's
  claim, which every language shares, so it is its own item.
- **Other residuals:** a `template <…>` header a macro parse lost flags
  its tokens plain (C-146's residual, the same blind spot; none found on
  either cell); a class head a macro broke (`class GTEST_API_ X {`) reads
  `public:` as a label, which is why a declaration under a label records
  nothing — a constructor's own in-class declaration looked like a local
  there, and lane B points it at the out-of-line definition (4 wrong rows
  in the first simulation, none since).
- **Bites at:** test code that builds objects by declaration, and
  option-table APIs that take braced arguments (args). The oracle records
  a construction as its own class (`static→constructor`), so the cell
  reads these as recall, never precision.
- **You find out:** **surfaced** — the ingest summary's `constructions:`
  line and `graph.json`'s `constructions` block count the tokens drawn and
  the references inside a template left as `uses` (fmt: 120 and 44; args:
  369 and 1); O10's `sites_constructor` coverage bucket; nothing at the
  site.
- **Provider (P9):** scip-clang **0.4.0** (what it does and does not emit
  a reference for).
- **Source:** ADR-113 §2 (the concession); ADR-132 (the measurement and
  the narrowing).

### C-164 — A lane A C++ symbol from an error-recovered parse can carry a macro's name or another definition's body

- **Cannot tell you:** that a function's name or extent is right where
  tree-sitter-cpp recovered from a macro it could not read. Three shapes,
  all on fmt:
  - a **trailing annotation macro names the function** — `void
    UnitTest::AddTestPartResult(…) GTEST_LOCK_EXCLUDED_(mutex_) {` is a
    function called `GTEST_LOCK_EXCLUDED_`. 14 symbols
    (`GTEST_LOCK_EXCLUDED_` 5, `FMT_CATCH` 4,
    `GTEST_EXCLUSIVE_LOCK_REQUIRED_` 4, one more), 28 `calls` edges drawn
    from them, none into them;
  - a **macro-prefixed constructor takes its first member initialiser's
    name** — `FMT_CONSTEVAL FMT_ALWAYS_INLINE basic_fstring(const S& s) :
    str_(s) {` is `basic_fstring::str_` (2 symbols);
  - a **body swallows the definitions after it** —
    `gtest-extra-test.cc`'s `TEST` at line 201 ends at 292, so ten tests'
    calls are drawn from the first, and their test reach is its.
- **Because:** the preprocessor never runs at lane A (C-131, C-145), and
  the grammar's recovery reads the macro call as the declarator. The
  mint (ADR-129) can name the true definition beside such a symbol (29
  of the 73 rows sit under one), but a minted symbol has no extent, so
  the misnamed lane A symbol stays the caller.
- **Bites at:** `who_calls` and `tests_guarding` on macro-annotated C++.
  Measured against the key's caller names (ADR-134, 2026-09-18): **73 of
  fmt's 8,123 `calls` evidence rows name a wrong caller** (0.9%), 1 of
  args's 2,567. The key grades `(site, target)` and never reads a
  caller, so no cell's precision sees this.
- **Narrowed 2026-09-18 (ADR-135, 0.2.47-beta):** where lane B indexed
  the file, a function or method whose own name token the index reads as
  a *reference* — spelled as the symbol, to a macro or to a data member
  of that name — is **removed** (R1), its facts drawn from the true
  definition where the mint can name it (ADR-129, ADR-134) and from the
  module where it cannot; a function whose extent holds a file- or
  class-scope definition row has its extent re-read from the file's
  braces (R2). fmt: 18 removed, 1 extent re-read, the wrong-caller rows
  105 → 32 — 18 right, 55 lost — and the 32 left are the driver's naming
  grain, not this entry. **What is left:** no index (P6: nothing fires,
  the symbol stays misnamed), code the configuration never compiles
  (`src/os.cc:160`'s `FMT_CATCH`), a macro defined in a file lane A did
  not walk, a non-ASCII byte before the name on its line (lane A's
  column is bytes), any recovery shape these two reads do not see — and
  the calls R1 and R2 leave with the module, which are lost, not right
  (the ten swallowed tests are still not symbols).
- **You find out:** **partial** (since 0.2.47-beta) — `graph.json`'s
  `lane_a_contradicted` block and one ingest summary line count what was
  removed and re-read, and are absent where nothing fired. Nothing tells
  you about the remainder above: a misnamed symbol in an unindexed or
  uncompiled file looks like any other.
- **Provider (P9):** tree-sitter-cpp **0.23.4**.
- **Counted key-free, 2026-09-18 (ADR-135 proposed; nothing built):**
  on the four cells with an index, **18 misnamed symbols, all on fmt** —
  13 named for a macro (9 `GTEST_…LOCK…_`, 3 `FMT_CATCH`, 1
  `GMOCK_DEFINE_DEFAULT_ACTION_FOR_RETURN_TYPE_`) and **5** for a member
  initialiser (`char_value`, `str_` twice, `type_`, `size`; the "2"
  above was what the key's rows showed) — and **2 swallowing extents**
  (the `TEST` at 201, 42 definition rows inside; the `GMOCK_DEFINE…`
  symbol, 19). 0 on args, cJSON and sqlite-vector. The index tells them
  apart by one read only: it holds a *reference* — to a macro, or to a
  data member of that name — at exactly the token lane A took as the
  name. The definition row at the line does not (332 of fmt's lane A
  functions have none, and the hand read is preprocessor-inactive code,
  parsed right), nor does the name being a macro's (cJSON's
  `internal_malloc` is a function in one `#if` arm). After ADR-134's
  build the probe reads 105 wrong-caller rows on fmt; 73 are this
  entry's, and the other 32 are the probe's naming grain (25 `friend`
  functions defined in a class, 5 a nested class, 2 others). Simulated:
  105 → 32, 15 rows right and 58 lost, no agreeing row moved.
  `src/os.cc:160`'s `FMT_CATCH` is in uncompiled code and out of the
  index's reach.
- **Source:** ADR-134's step 0 (`~/.hobbes/bench/c145-extent/probe.py`),
  every row read against the source; ADR-135's
  (`~/.hobbes/bench/c164-wrong-callers/`).

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
