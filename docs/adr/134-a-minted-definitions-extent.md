# ADR-134 — A minted definition's extent: the caller of a call written inside a lost definition

**Date:** 2026-09-18 · **Status:** accepted (Max, 2026-09-18: route a) — conditionals refused; refusal 3 measured before the build and corrected below (*Accepted*). Registers **C-164** (what the measurement found beside its own question).

Follows ADR-129 §3 ("a minted symbol is a target, not a scope … its size
is not measured — the next item on the C++ recall list, counted before
anything is designed for it"). A build would be a patch: a constraint's
fix (C-145's residual).

## Context

ADR-129 reads a definition lane A's parse lost from scip-clang's own
definition row, as a **target**: `end_line` is its line. A call written
*inside* that definition keeps the caller it had — the enclosing symbol
lane A did parse, or the module. C-145 says so, and `who_calls` says so
on every minted symbol.

Two things were not known. How many edges carry that caller, and **what
the caller is** — because every C and C++ key is a *resolution* key: it
grades `(site, target)` and never reads an edge's `from`. fmt's 7,012
confirmed rows say the site reaches the target; none of them says who
the caller is. No cell has ever judged a C++ caller.

The key does *name* the caller at every site (`sites[].caller`, clang's
own enclosing function), so it can be read.

## The measurement (`~/.hobbes/bench/c145-extent/`, nothing drawn)

**Step 0, whose caller is it** (`probe.py`; fmt and args at ADR-133's
code, the stored keys under `uneval-drivers/keys/`). Every `calls`
evidence row in a file the key covers, Hobbes' `from` beside the key's
caller at that line. Three conventions are equivalences, not
disagreements, and the probe's first two passes scored them wrong before
the hand read caught each: gtest's `<suite>_<name>_Test::TestBody` is
lane A's `<suite>.<name>`; an overload's `~2` and a mint's `~b2` are id
devices; a lambda's `operator()` is the encloser by design.

| | fmt | args |
|---|---|---|
| `calls` evidence rows in key files | 8,123 | 2,567 |
| caller agrees with the key | 6,392 (78.7%) | 2,476 (96.5%) |
| both say file scope | 27 | 0 |
| lambda inside (the encloser, by design) | 97 | 72 |
| the key has no site on the line | 96 | 0 |
| **lost caller** — Hobbes says the module, the key names a function | **1,436 (17.7%)** | **15** |
| **wrong caller** — Hobbes names another symbol | **75** | **4** |

- **Lost callers are this ADR's question:** 1,329 of fmt's 1,436 sit
  under a **minted** definition of the key's caller (format.h 605,
  gtest.h 266, gmock.h 141, gmock-gtest-all.cc 132, core.h 93); 96 under
  a definition nothing names (the mint's refusals — several monikers, a
  declaration head), 11 where lane A parsed the function and lost its
  end. args: 13 of 15 minted, the other 2 a lambda the probe's lambda
  test missed.
- **Wrong callers are not** — they are lane A's own, and they are
  registered with this ADR as **C-164**. Read row by row: 73 of fmt's 75
  are wrong, 2 the key's grain (a local struct's method, a spelling).
  - 32 rows: a trailing annotation macro **names the function**.
    `void UnitTest::AddTestPartResult(…) GTEST_LOCK_EXCLUDED_(mutex_) {`
    is, to the grammar, a function called `GTEST_LOCK_EXCLUDED_`. 14 such
    symbols on fmt (`GTEST_LOCK_EXCLUDED_` 5, `FMT_CATCH` 4,
    `GTEST_EXCLUSIVE_LOCK_REQUIRED_` 4, one more), 28 `calls` edges out
    of them, none in.
  - 2 rows: a macro-prefixed constructor's first member initialiser names
    it (`FMT_CONSTEVAL FMT_ALWAYS_INLINE basic_fstring(const S& s) :
    str_(s) {` is a function called `str_`).
  - 39 rows: one `TEST` body whose error recovery **swallowed the ten
    tests after it** (`gtest-extra-test.cc` 201–292): their calls read as
    the first test's, and so does their test reach.
  - args: 1 of 4 wrong (a friend operator lost inside a class, its call
    drawn from the class); 2 lambdas, 1 spelling.

**Does lane B carry an extent?** No. scip-clang 0.4.0 was run on a
ten-line file in the image and its index walked field by field: an
occurrence carries `range`, `symbol`, `symbol_roles` and `syntax_kind`
(fields 1, 2, 3, 5) and **no `enclosing_range`** (field 7). The extent is
not in the index to be read; only the file's text has it.

**Step 1, a brace-matched extent, judged by the key** (`simulate.py`;
the graph is read, never written). For each minted function or method:
the file's own text with comments, strings, raw strings and character
literals blanked; the first `{` at parenthesis depth 0 after the
definition's line (the mint already requires one, `shows_body`); its
matching `}`. **Refused:** a preprocessor conditional line
(`#if/#else/#elif/#endif`) anywhere in the body — either branch may hold
the brace the compiler saw. A `calls` row's caller moves to the
innermost such extent holding its site when that extent starts after the
current caller's line, or the caller is the module.

| | fmt | args |
|---|---|---|
| extents read / refused (conditional inside) | 1,365 / 34 | 66 / 0 |
| rows that move | 1,303 | 16 |
| new caller is the key's | 1,231 | 13 |
| lambda inside (encloser by design) | 23 | 0 |
| key has no site on the line | 19 | 0 |
| new caller differs from the key's | 30 | 3 |
| **a row whose caller was right and would move** | **0** | **0** |

All 33 differing rows were read against the source. **None is wrong:**
24 are friend functions defined in a class (`friend … compare(const
bigint&, …) {` — the key names the lexical class, `bigint::compare`; the
index names the namespace function, `fmt::v12::detail::compare`: one
function, two spellings); 5 are methods of a nested class-template
specialisation whose name the key elides (`IteratorImpl<…>`); 4 hold a
lambda whose `operator()` the key class-qualifies. The 19 unjudged rows'
extents are 3 to 50 lines, each closing at the function's own brace.
args's one `other → new` row is the friend operator above: the extent
repairs it.

Allowing a conditional inside the body adds 56 right rows, 5 lambda and
2 unjudged on fmt, none wrong — and it is a guess wherever both branches
open a brace.

**What no number here says.** No graded figure moves: the keys do not
read `from`, so precision, strict precision and recall are what they
were on every cell. What moves is `who_calls` (the caller named),
`tests_guarding` (reach continues *through* a minted function instead of
stopping at it, and no longer pools in a file's module), and the gate's
reading of a diff inside a lost definition.

## Decision (proposed)

1. **A minted function or method gets an extent read from the file's
   text**, by the rule above, where the mint already requires a body;
   `end_line` becomes the closing brace's line. A minted **type** stays a
   line (its members are symbols of their own, and a class head is where
   macros bite hardest).
2. **Refusals, counted** beside the mint's in `graph.json`'s `minted`
   block and on the ingest summary: a preprocessor conditional inside
   the body; a match that runs off the file; an extent that would
   contain the line of a lane A function it does not nest (the brace
   match crossed a definition — not seen on either cell, refused so it
   cannot be silent).
3. **Re-homing.** After the mint, a `calls` or `uses` fact whose site
   lies in an extent moves to the innermost one when that extent starts
   after the fact's current caller, or the caller is the module. Nothing
   else in the join reads an extent: no fallback rank, no veto set, no
   lane-agreement row (ADR-129 §4 stands).
4. **Said where it is met.** `who_calls` drops "a target, not a scope"
   for a symbol with an extent and keeps it for one refused; C-145's
   residual is rewritten to the refusals and the 96 rows under a
   definition nothing names.
5. **The check is the key's caller**, because no grade can be: the
   regrade re-runs `probe.py` before and after, and the record carries
   lost 1,436 → about 150 on fmt (the probe's own count at the regrade is the record, not this estimate), wrong 75 → 75 (C-164 is not this
   rule's), and zero rows that were right and moved.

## Routes for Max

- **(a) Recommended — build §1–5 as written, conditionals refused.** fmt:
  about 1,280 of 1,436 lost callers get the caller clang names, 0 wrong
  in 1,303 moved rows read against the key and by hand; args 16 of 16.
  No graded number moves; `tests_guarding` and `who_calls` answer truer
  on every macro-heavy C++ repo. One dispatched unit (`minted.py`, the
  re-homing beside the mint's call, `minicpp` gaining a lost definition
  with a call inside it and one with `#if` in its body), then the
  proxy's `who_calls` wording.
- **(b) The same, conditionals allowed.** +61 rows on fmt, none wrong
  measured. Not recommended: the rule would be right by luck where
  `#if`/`#else` each open the body, and a rule here fails toward drawing
  less.
- **(c) Register and leave.** The numbers go into C-145 and the module
  stays the caller. The graph is not wrong today — a module-level caller
  is a coarser truth, not a false one — so this is honest; it leaves
  17.7% of fmt's call edges without their function.

**Beside the routes, C-164 wants its own item, ahead of the 15
line-convention rows:** its 73 rows are *wrong*, not missing, and 16
symbols on fmt carry a macro's or a member's name. Measured first, as
ever: how many such symbols across the C and C++ clones, and whether the
mint's own rows (the index knows the true name at that line) can refuse
or rename them.

## Alternatives considered

- **Route B of ADR-129 — blank known-empty macros and re-parse.** It was
  the candidate for this residual. The measurement says it is not
  needed for the extent: the definition's line is already known from the
  index, and brace matching from it read 1,303 rows with none wrong. It
  stays the candidate for C-164, where the *parse* is what is wrong.
- **An extent from the index.** Not there (no `enclosing_range`).
- **An extent from the next definition's line.** Rejected: it would give
  every trailing comment, macro and namespace-scope statement to the
  function above it.

## Consequences

- Test reach widens again on gtest-tested C++ repos, truly: a test that
  reaches a minted function now reaches what it calls.
- A caller is asserted where no key grades callers. The ADR's defence is
  the key's caller names read as a probe, kept as a driver and re-run at
  each regrade; it is not a grade, and the cell records must not call it
  one.

## Accepted — route (a), and refusal 3 measured before the build (2026-09-18)

Max took route (a). Before the unit was written, §2's third refusal was
run over both cells (`simulate_r3.py` beside `simulate.py`), because the
sentence above — "not seen on either cell" — had not been measured. **It
was wrong: the refusal fires on 19 of fmt's 1,365 extents**, and it is
what keeps a wrong `end_line` out of the graph:

- **13 are macro-generated methods.** `GTEST_REPEATER_METHOD_(OnTestStart,
  TestInfo)` (`gmock-gtest-all.cc` 5326–5344) is a whole method
  definition to clang and a line with no `{` and no `;` in the text, so
  the brace match ran on to the body of the next function written out,
  `TestEventRepeater::OnTestIterationStart` at 5349. Step 1 could not see
  it: no `calls` row moved wrongly, because lane A's symbol for 5349
  starts later and keeps its calls. The **node** would have been wrong —
  an extent of thirty lines over a one-line definition — and
  `tests_guarding` and the gate read nodes. (The same lesson as ADR-129's:
  grade what a rule adds to the nodes, not only to the edges.)
- **6 hold a C-164 symbol**: a true body whose next line lane A read as
  a function named by the annotation macro (five:
  `GTEST_EXCLUSIVE_LOCK_REQUIRED_` at 14078 inside
  `Mock::VerifyAndClearExpectationsLocked` at 14077) or by a member
  initialiser (one: `size` at `scan.h` 348 inside `scan_args` at 347).
  The extent is right and is refused all the same: the rule cannot tell
  this from the first class, and C-164's item is where those symbols are
  dealt with.

So refusal 3 is built in its simplest form, which draws less: **an
extent is refused where any other function or method symbol — lane A's
or minted — starts inside it** (`holds-a-definition`). A definition
lexically inside a function body is below the symbol floor by decision
(C-9; the mint's `local-to-function`), so a symbol found there says the
brace match or the parse is wrong. With it, fmt reads **1,346 extents,
34 + 19 refused, 1,290 rows moved: 1,218 to the key's caller (13 fewer
than step 1), 23 lambda, 19 unjudged, the same 30 spellings, none
wrong**; args is unchanged (66 extents, 16 rows). §5's estimate becomes
lost 1,436 → about 165. The predictions are `oracle-grading.md` §10.19.

## Built (2026-09-18, 0.2.46-beta)

Unit `368a`, then the developer's fix on top of it, because the brief's
premise was wrong: a lane A C or C++ site at file scope carries **the
module's id** as its scope, not an empty one, and the projection reads a
truthy scope as the caller — so §3 also re-homes a fact whose scope is
the module. And since `end_line == line` is both a body of one line and
a refusal, the mint marks a read extent on the symbol (`extent:
"braces"`); re-homing and `who_calls` read the mark. Checked as §5 says
(`oracle-grading.md` §10.19): every graded number ±0 on the four C and
C++ cells; fmt 1,346 extents, 34 + 19 refused, 1,290 `calls` rows
re-homed, agreeing 6,392 → 7,610, lost 1,436 → 188, no right row moved,
test reach pairs 3,183 → 6,131; args lost 15 → 0.

