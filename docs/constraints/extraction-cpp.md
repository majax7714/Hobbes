# Extraction — C++ (ADR-113)

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

C++ joined at lane A on 2026-09-14 (ADR-113 §1, 0.2.18-beta): a
tree-sitter-cpp walk on `csource`'s contract. Lane B (scip-clang over
the same derived compile database) and the §3.8 row are later units;
until the row lands C++ is *wired, not supported* (P11). The entries
below were written from the walk's first host read, fmtlib/fmt at
`3a0661d7` (2026-09-14): 26 headers claimed 25 to C++ and 1 to C, and
every one of its 21 library headers parsed with tree-sitter ERROR
nodes.

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
- **Bites at:** every C++ repo until lane B answers (unit 2); on fmt,
  overload sets are the norm in every header.
- **You find out:** **surfaced** — `overload-set` and `attr-call` in
  the tail; a member call written `p->f()` or `this->f()` classes
  `unclassified`, not `attr-call`, because the tail's shape read looks
  at the character before the name and `>` is not one of its markers —
  a gap C's tail shares, left as is so a C++ unit moves no C number.
- **Source:** ADR-113 §1; the doer's deviation list (`3d56`).

### C-144 — One symbol per qualified name per file: an overload set's later definitions are below the floor

- **Cannot tell you:** that a function defined twice in one file with
  different signatures is two symbols. C's rule (ADR-108: the first
  definition in file order is the symbol, the rest a `parse` record
  naming preprocessor alternatives) applies to C++ unchanged, where an
  overload set is the language's norm. The later overloads have no
  symbol, so a call lane B resolves to one of them lands nowhere
  (`below-floor`), and the fallback abstains on all of them (C-143).
- **Because:** symbol ids are `module.qualname`; nothing in the id
  tells overloads apart, and the walk was not asked to (ADR-113 §1
  says "a template declaration is the entity it declares, once").
- **Bites at:** every overloaded function's callers beyond the first
  definition; on fmt, `format`, `format_to`, `print`, `vformat` in
  every header. The `parse` record it draws per file reads as a
  defect ("defined more than once … an overload set, or preprocessor
  alternatives") on code that is fine.
- **You find out:** **surfaced**, wrongly worded — the record fires,
  but names the overload set as if it were a duplicate. **This is a
  defect to fix in unit 2** (lane B): an overload needs an id that
  carries its signature or line, and the record should fire only for
  same-signature duplicates.
- **Source:** the fmt read, 2026-09-14.

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
  Lane B does not share the gap: scip-clang runs the preprocessor.
- **You find out:** **surfaced** — a `parse` degradation record per
  file, the same record C draws.
- **Provider (P9):** tree-sitter-cpp **0.23.4**.
- **Source:** the fmt read, 2026-09-14.

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
