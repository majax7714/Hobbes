# ADR-135 — A lane A C++ symbol the index contradicts: refused where its own name is a reference, clipped where its extent holds a definition

**Date:** 2026-09-18 · **Status:** accepted (Max, 2026-09-18: route a) — the brief's premises checked against the code first (*Accepted*, below).

Follows ADR-134 ("C-164's wrong callers — next, counted across the C and
C++ clones first, then whether the index's definition row at that line
can refuse or rename the symbol"). A build would be a patch: a
constraint's fix (C-164).

## Context

C-164 is the one C++ entry whose rows are **wrong** rather than missing:
where tree-sitter-cpp recovers from a macro it cannot read, lane A keeps
a function whose *name* is the macro's (`GTEST_LOCK_EXCLUDED_`) or a
member initialiser's (`str_`), or whose *extent* runs on over the
definitions after it (one `TEST`, ten tests). The calls inside are drawn
from that symbol, `who_calls` names it, and `tests_guarding` reads its
reach. No grade sees it: every C and C++ key judges `(site, target)`.

ADR-134 counted 73 wrong-caller rows on fmt before its build. After it
(0.2.46-beta) the probe reads **105** — the 1,290 re-homed rows brought
32 more into the probe's wrong class, none of them C-164 (below).

## The measurement (`~/.hobbes/bench/c164-wrong-callers/`, nothing drawn)

**Step 0, the shapes, key-free** (`shapes.py`, `nameref.py`; the four
cells that have an index: fmt, args, cJSON, sqlite-vector, each graph at
0.2.46-beta's code beside its cached facts stream, found by
`findstream.py`). ScummVM has no index on disk and is not counted.

The question was whether the index can tell a misnamed symbol from a
right one. Its **definition row at the line cannot**: of fmt's 3,046
lane A functions in indexed files, 2,711 have a function row of their
own name at their line, 4 have a row of another name, and 332 have no row
at all — and the hand read of the 332 is preprocessor-inactive code
(`report_windows_error`, `Utf16ToAnsi`), which the compiler never saw
and lane A parsed correctly. "No row" is not evidence of a wrong name.
Nor is the name being a macro's somewhere: cJSON's `internal_malloc`,
`internal_free` and `internal_realloc` are functions in one `#if` arm
and macros in the other, and are right.

What does separate them is a **reference**: a function's own name at its
definition is a definition occurrence, never a reference. Where the
index reads the token lane A took as the name as a *reference* — to a
macro, or to a `term` (a data member) of that name — the parse took the
wrong token.

| the index reads the symbol's own name token as a reference to… | fmt | args | cJSON | sqlite-vector |
|---|---|---|---|---|
| a macro | 13 | 0 | 0 | 0 |
| a `term` of that name | 5 | 0 | 0 | 0 |
| — of them, symbols whose name the index *agrees* with | 0 | 0 | 0 | 0 |

All 18 were read against the source and all 18 are misnamed: 9
`GTEST_LOCK_EXCLUDED_` / `GTEST_EXCLUSIVE_LOCK_REQUIRED_`, 3 `FMT_CATCH`
(a `catch` clause read as a function), 1
`GMOCK_DEFINE_DEFAULT_ACTION_FOR_RETURN_TYPE_`, and 5 constructors named
for their first member initialiser (`char_value`, `str_` twice, `type_`,
`size`). The register's "2 symbols" of the second shape was the two the
key's rows showed; there are 5.

**The position has to be exact.** Read loosely — a same-named reference
anywhere in the symbol's first lines or body — the rule also flags four
*right* symbols: args's `Base::KickOut` beside `Options::KickOut`,
`ArgumentParser::Parse` beside `Error::Parse`, fmt's `value::value`
beside `custom.value`. An enumerator or a field may share a function's
name and be used inside it. The simulation took the first whole-word
spelling of the name on the symbol's line as lane A's token; the built
rule must use the parse's own column, which lane A does not record
today.

**The swallowing shape** is a different read: a lane A function whose
extent holds a function definition row the index places at file or class
scope (the moniker's chain holds no function — a lambda or a local
class's method is inside by right). 2 on fmt — `gtest-extra-test.cc`'s
`TEST` at 201, whose braces close at 210 and whose lane A extent is 292
(42 rows inside), and the `GMOCK_DEFINE…` symbol above, 1170–1264 (19
rows) — and 0 on the other three cells.

One residual the index cannot reach: `src/os.cc:160`'s `FMT_CATCH` sits
in code this configuration never compiles, so there is no reference to
read. It is a one-line symbol and draws nothing on this cell.

**Step 1, the rules simulated** (`simulate.py`, predictions in
`PREREG-sim.md` written first; scored with ADR-134's `probe.py`):

- **R1:** a lane A function or method whose own name token the index
  reads as a reference to a macro or a `term` is refused. Its rows go to
  the minted definition whose brace extent covers them — ADR-134 refused
  six such extents as `holds-a-definition` because the misnamed symbol
  started inside them — else to the module.
- **R2:** a lane A function or method holding a file- or class-scope
  definition row gets its extent re-read from the file's braces, by
  ADR-134's reader with its refusals; rows past the new end go to
  whatever extent covers them, else to the module.

| fmt, 8,123 `calls` evidence rows | 0.2.46-beta | simulated |
|---|---|---|
| agree | 7,610 | 7,625 |
| lost-caller | 188 | 246 |
| wrong-caller | 105 | **32** |

Row by row: 15 wrong rows become right, 58 become lost, 32 stay; **no
row that agreed moved, and no row is bad after that was not bad
before.** args, cJSON and sqlite-vector: nothing flagged, nothing moves.
Six minted extents unblock.

The 58 are wrong rows made honest, not repaired: the ten swallowed tests
are not symbols (39 rows; the mint refuses a `TEST` line as
`several-monikers`), `AddTestPartResult` holds a `#if` and keeps
ADR-134's `conditional-inside` refusal (14 rows; `CurrentStackTrace` is
refused the same way and has no row in the key's files), and 5 rows sit
under refused symbols with no minted definition above them
(`~FunctionMocker`, 3; the two `basic_fstring` template constructors the
index carries no definition row for, 2).

**The 32 that stay are not C-164.** Read by hand: 25 are functions
defined as `friend` inside a class (`bigint::compare`,
`uint128::operator!=`, `scan_buffer::advance`, `my_class::format_as`) —
the key qualifies by the lexical class, Hobbes names the namespace
member the language says it is; 5 are `CartesianProductGenerator`'s
nested `IteratorImpl`, the key's owner grain; 1 a conversion operator's
spelling; 1 `gmtime`'s local struct, the encloser by decision (C-9).
They are the probe's naming grain and belong in its equivalences, as
gtest's `TestBody` does.

**Predictions:** P-3 met exactly (105 → 32) and P-5 met (no agreeing row
moves). **P-1 missed by one** (18 symbols, not 19: one symbol was
counted at two references). **P-4 missed** — agree +15 where +29 to +34
was predicted, lost +58 where +39 to +44: the prediction took every
"minted definition beside it" as re-homable and did not read those
definitions' own extent refusals first.

## Decision (proposed)

1. **Lane A records the name token's column** on each C++ function and
   method (the cache format moves to `lanea-cpp v5`).
2. **R1, at the join, after the index is read and before the mint:** a
   lane A C++ function or method is refused where a lane B reference sits
   at exactly its name token and resolves to a `macro` row or to a `term`
   row of that name. The symbol is dropped, its facts' scope becomes the
   module's, and the file's `parse` record counts it — so the mint sees
   the line as lost, mints the true definition where the index has one,
   and ADR-134's extent and re-homing do the rest. Nothing is renamed by
   a rule of this ADR.
3. **R2:** a lane A C++ function or method whose extent holds a
   file- or class-scope function definition row has its extent re-read
   from the braces (ADR-134's reader, its four refusals; a refusal
   leaves the symbol a line). Counted in `graph.json` and on the ingest
   summary.
4. **P6:** with no index neither rule can fire, and the graph is what it
   was. C-164 stays open for that case, for uncompiled code, and for
   whatever shape these two reads do not see; it moves to *partial* with
   the counts surfaced.
5. **Checked as ADR-134 was (§10.20, predictions first):** every graded
   number ±0 on the four C and C++ cells; fmt's wrong-caller 105 → 32,
   no agreeing row moved; the test reach of `expect_throw_no_
   unreachable_code_warning` falls to its own body's.

## Routes for Max

- **(a) Recommended — R1 and R2 as above.** fmt: 73 wrong rows gone (15
  right, 58 lost), 18 misnamed symbols out of `who_calls` and the graph,
  one test's borrowed reach returned; nothing moves on args, cJSON or
  sqlite-vector. One unit, lane A's column plus the two reads; about the
  size of `368a` ($5.88).
- **(b) R1 only.** 34 rows; the swallowed `TEST` keeps ten tests' calls
  and reach. Cheaper by R2's share, and leaves the larger half.
- **(c) (a), and rename instead of refuse where the index has the
  definition.** The mint already does this for the seven it can reach;
  a rename rule would add nothing the simulation can show, and would
  put an index name on a lane A extent that came from a broken parse.
  Not recommended.
- **(d) Surface only:** say in the `parse` record that a present symbol
  may be misnamed. Honest and builds nothing; the rows stay wrong.

Separately, and no spend: fold the friend and nested-class equivalences
into `probe.py`, so the next caller read starts from 0 known-grain rows.

## Alternatives considered

- **Refuse on the definition row's name at the line.** Measured: it sees
  4 of the 18 and cannot tell them from inactive code.
- **Refuse any function named as a macro is named.** Wrong on cJSON's
  three allocator functions.
- **Route B, blank known-empty macros before the parse** (ADR-134's
  other candidate). It would repair rather than refuse, and recover the
  swallowed tests; it needs the macro's definition at lane A, which is
  the macro class's question (C-131, parked). R1 and R2 do not close it
  off.

## Consequences

- A rule that **removes** lane A symbols on the index's word — the first
  of its kind; every earlier rule added or withheld edges. It is scoped
  to the one position where a reference cannot be a definition.
- Lost rows on fmt rise 188 → 246. Each was wrong before.
- Lane A's C++ cache is rewritten once (v5).

## Accepted — route (a), and the premises read before the brief (2026-09-18)

Max: route (a). ADR-134's brief mis-stated a site's scope and the unit
shipped green on it, so each fact this ADR's build rests on was read in
the tree before the brief was written:

- **The name's column is already in hand.** `cppsource._symbol` takes the
  identifier node; the column is `ident.start_point.column`, 0-based, the
  convention lane B's `col` and the operator tokens already share
  (`xchar.h:98`: `str_` at lane B's col 62, the text's column 62). The
  cache stores symbols, so `laneacache.FORMAT` moves to `lanea-cpp v5`.
- **The references are resolution `Site`s** (`file`, `line`, `name`,
  `col`, `def_file`, `def_line`) in `_build_symbol_layer`'s
  `resolutions`; the definition rows, macro and `term` rows among them,
  are `lane_b_definitions`, already filtered to lane A's C and C++ files.
  A macro defined in a file lane A did not walk has no row there, and R1
  does not fire on it: the symbol stays, which is the state today.
- **Where the rules run:** after the join and before the mint, on the
  joined facts. A refused symbol's facts take the module's id as their
  scope — the scope lane A gives a file-level site — so ADR-134's
  `rehome` moves them as it moves any other. The join has already read
  lane A's symbols; nothing runs into the 18 on fmt, and a fallback
  target that names a refused symbol's line finds no symbol at the
  projection and draws nothing.
- **§2 amended — counted in the graph, not in the `parse` record.** The
  file's `parse` record is lane A's, written before the index is read.
  The counts go in a `graph.json` block of their own
  (`lane_a_contradicted`: refused by kind, extents re-read and refused by
  reason) and on the ingest summary, as the mint's do.
- **R1 requires the reference to be spelled as the symbol's name.** A
  gtest `TEST`'s lane A name is `suite.name`; whatever sits at its
  column is not spelled that, and R1 cannot fire on a test.

§10.20's predictions were written before the unit.
