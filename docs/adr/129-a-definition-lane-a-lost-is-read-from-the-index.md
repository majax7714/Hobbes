# ADR-129 — A definition lane A lost to a macro parse is read from the index

**Date:** 2026-09-17 · **Status:** accepted (Route A; measured first, nothing built yet) · **Owner:** Max · **Source:** Max, 2026-09-17 ("good to go with route a … patch number stands"), on the recall survey of that day — honesty and accuracy first on the extraction lane.

Narrows **C-145** and amends architecture **§3.4** (a symbol may be
declared by lane B, in one named case). Pre-registered in
`oracle-grading.md` §10.13. Patch: a constraint's fix, even when
structural (ADR-103's fourth amendment; Max confirmed the number).

## Context

C++ has the lowest recall of any supported language: fmt 14.5%, args
56.4%. C-145 names the largest single cause and says it in one sentence:
*"Lane B names the callee, and the graph has no symbol to draw it to."*
tree-sitter-cpp cannot parse a declaration spelled through macros
(`FMT_API`, `FMT_CONSTEXPR`, `FMT_BEGIN_NAMESPACE`), the definition falls
in an ERROR node, lane A keeps no symbol, and `project` drops every call
scip-clang resolved there as `below-floor` (`scipsource.project`:
`starting_at(target_module, def_line)` answers `None`).

These are not inferred edges. The compiler resolved the call; the index
holds the definition's file, line, kind and moniker (the helper's
`definitions` rows carry all four already). What is missing is a node.
That is a different thing from ADR-126's expansion, which would have
drawn edges no tool proved.

## The measurement, first

A scratch probe (`~/.hobbes/bench/c145-recovery/`: `probe.py` wraps
`read_facts` and `project` and writes no artifact; `analyze.py` classifies
each below-floor call fact and writes the export the rule would produce;
the real `oracle grade --poison` judges it against the standing key).
Nothing was drawn in any graph.

**fmt, where the rule was fitted.** 6,905 below-floor call facts. A
naive rule (mint a symbol wherever lane B defines one and lane A has
none) read **98.2%** with 123 contradicted. Read row by row:

- 98 were calls to a **type** — a construction. `project` already draws a
  call whose target is a type as `uses` (`_CALLS_TO_TYPE_GUARDED`,
  ADR-113 §2); the probe had exported them as calls. Not a rule: the
  existing guard, applied.
- 17 landed on a **declaration, not a definition**: gtest's amalgamation
  forward-declares `CountIf`, `ForEach`, `GetElementOr` and `Shuffle` at
  `gmock-gtest-all.cc:1630–1633` and defines them at 677–731; a
  block-scope `using` in a test body; fmt's own `use_facet` shim;
  `__cxa_demangle`'s local `extern`. scip-clang gives such a line the
  definition role.
- 5 landed on a **data member** whose initialiser is spelled like a call
  (`key_(CreateKey())` in a constructor's initialiser list): descriptor
  kind `term`.

Both remaining shapes are things lane A's own contract already refuses:
*symbols come from definitions only, never a declaration*, and a C++
symbol is a function, a method, a type or a macro (`cppsource`'s module
doc). With those two rules the fmt export read:

| | standing (0.2.40-beta) | with the rule |
|---|---|---|
| graded call edges | 3,491 | 7,002 |
| confirmed / contradicted | 3,269 / 0 | **6,533 / 0** |
| precision · strict (ADR-124) | 100% · 99.73% (9 unjudged) | 100% · **99.06%** (62 unjudged) |
| recall | 14.5% (7,333/50,524) | **29.1%** (14,702/50,524) |
| recall-collapsed | 12.4% | 24.9% |
| poison | PASS | PASS, 0 falsely confirmed |

3,726 facts onto 622 lost definitions (3,553 onto methods and functions,
173 onto types, which draw `uses`); `format.h` 1,967, `gtest.h` 962,
`core.h` 320. Not minted, and counted: 2,554 to a macro lane A lost (a
macro is expanded, not called — excluded from every grade), 308
declarations, 194 with no definition row at the line, 74 `term`, 28 lines
where lane B defines several monikers, 20 where a lane A symbol of the
same name sits within three lines (a line-convention defect, not a lost
definition — its own item), 1 in a file that parsed clean.

**The strict figure falls, and that is said, not hidden.** 53 of the new
edges sit on a line where the key holds a site with no targets, so H-30's
rule leaves them unjudged and ADR-124 counts them against us: 99.73% →
99.06%. None is contradicted. Both figures travel together wherever fmt
is quoted.

**args, held out.** The rule was frozen (`analyze.py`, sha256
`7bb90bb14ac90452…`) and four predictions written
(`PREREG-args.md`, P70–P73) before the args probe ran. 103 below-floor
facts, 76 mintable, 67 new graded edges: **67 confirmed, 0 contradicted**;
2,062/2,062, recall 56.4% → **58.6%**, strict unchanged (no unjudged
row). P70–P73 all met.

**C, the control.** cJSON (186 below-floor facts) and sqlite-vector (354)
mint **nothing** — every fact there is a lost macro or a `term` — and
both grades are identical to the row.

## Decision

**1. Where lane A's parse lost a definition, lane B's definition is the
symbol.** After every lane A walk and before `project`, for each
`definitions` row of a C or C++ unit's facts, a symbol is minted when
**all** of these hold, and otherwise nothing is:

- the file carries lane A's `parse` degradation record (ERROR nodes). A
  file that parsed clean mints nothing: there, a missing symbol is lane
  A's floor speaking (a lambda, a local class), not a loss;
- the row's kind is `method` (scip-clang's descriptor for every function)
  or `type`. Never `term`, `macro` or `namespace`;
- exactly one moniker is defined at that file and line (C-148's and
  C-151's abstentions are already out of the rows);
- no lane A symbol starts at the line, and none of the same terminal name
  starts within three lines (that is a line-convention disagreement, to
  be counted and fixed as one);
- **the source shows a body**: reading the file's own text from the
  definition line, a `{` is met at parenthesis depth 0 before any `;`. A
  token read, as ADR-125 reads a `template <>` header the parse lost. A
  defaulted or deleted function (`= default;`) has no body and mints
  nothing — lane A's rule, kept.

**2. The symbol says who declared it.** `declared_by: "scip"` on the
symbol (absent on every lane A symbol; schema v4, additive). Kind
`function` or `method` by the moniker's owner (a `#` owner is a class),
`type` for a type. `qualname` is the moniker's descriptor chain joined
with `::` — the compiler's spelling, so an inline namespace appears
(`fmt::v12::detail::write`) where lane A's neighbours in the same lossy
file may lack it; the id is `<module>.<qualname>`. Where that id is
taken, by lane A or an earlier mint, the mint takes `~b2`, `~b3`, … in
line order. **No lane A id moves**, and `_bare` does not read `~b` as an
overload suffix.

**3. A minted symbol is a target, not a scope.** `end_line` is its line.
Finding a body's end through unexpanded macros is a guess this change
does not make, so calls written *inside* a lost definition keep the
caller they have today. Registered as C-145's residual, with the count.

**4. Nothing lane A decides changes.** Minting runs after lane A's
fallback and the veto sets are built: no fallback rank, tie, abstention
or lane-agreement row sees a minted symbol. The only consumer that moves
is `project`, where `starting_at` now answers for the lost line — so
R-qual (ADR-125), the called-type guard and the macro exclusion apply to
a minted target exactly as to any other.

**5. Where a user meets it.** The ingest summary prints one line per
language — symbols read from the index, files, and what was *not* minted
by reason (declaration, term, several monikers, line-convention).
`graph.json` carries the counts under `minted`. `who_calls` marks a
minted symbol "(definition read from the index: lane A's parse lost it,
C-145)". `list_blind_spots` keeps the file's `parse` record — the file is
still lossy for everything but these targets.

**6. C-153's exposure grows and is marked.** More semantic C++ edges into
template code means more of scip-clang's single wrong candidates can be
drawn. The `cpp-template-sites` marking (ADR-125 §4) cannot see a pattern
whose header the parse lost — which is every minted *target's* file. The
marking is by the *caller's* pattern, so it still applies; the count is
re-read on fmt at the regrade, and the 53 new unjudged rows are read by
hand before the cell record is written.

## Order of work

1. §10.13's predictions for the built change (this commit).
2. One dispatched unit: the mint (`extract/minted.py`), its call in
   `extract/__init__.py`, the `minicpp` fixture gaining a macro-lost
   definition, a forward declaration, a call-spelled member initialiser
   and a construction — one of each refused shape — and the tests.
3. A second unit: the surfaces of §5 (Python summary, the Go proxy's
   `who_calls` marker, `hobbes diff`).
4. On the host: live and `lane_b` tests; fmt, args, cJSON and
   sqlite-vector regraded against their stored keys, signed
   direction-of-fix lines; the C++ fixture tests in the image with `-v`
   (this host has no clang++).
5. C-145 narrowed with its residuals; §3.8's C++ row; 0.2.41-beta.

## Alternatives considered

- **Route B — blank known-empty macros before the parse.** Rejected as
  the first move: it cannot spell `FMT_BEGIN_NAMESPACE` (a namespace
  opening), and it is lane A guessing at the preprocessor, which C-131
  says it never does. It stays the candidate for the *residual* of §3
  (scopes), where only lane A can help.
- **Mint in every file, parsed clean or not.** Rejected: in a clean file
  a missing symbol is the floor by decision (C-9), and the one fact of
  that shape on fmt is not worth the rule's honesty.
- **Give minted symbols an extent by brace matching.** Deferred (§3).
- **A new tier for the edges.** Rejected: the edge is lane B's ordinary
  answer at semantic tier; what is new is the node, and the node says so.

## Consequences

- fmt's public precision keeps 100% and its strict companion falls to
  about 99.1%; recall about doubles. The claim page and `tables.md` carry
  both on the regrade.
- Test reach widens on gtest-tested C++ repos: a test reaches fmt's
  header functions it could not before. `tests_guarding` answers change.
- Symbols are no longer lane A's alone. P6 holds — with no indexer,
  nothing is minted and the floor is what it was.
