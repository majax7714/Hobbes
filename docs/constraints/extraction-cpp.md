# Extraction — C++ (ADR-113)

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

C++ joined at lane A on 2026-09-14 (ADR-113 §1, 0.2.18-beta): a
tree-sitter-cpp walk on `csource`'s contract. Lane B (scip-clang over
the same derived compile database) was made deliberate the same day
(§2, 0.2.19-beta). The §3.8 row is the last unit; until it lands C++ is
*wired, not supported* (P11). The entries below were written from the
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

### C-145 — Macro-heavy C++ parses with error nodes: the preprocessor never runs (C-131's C++ face)

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
