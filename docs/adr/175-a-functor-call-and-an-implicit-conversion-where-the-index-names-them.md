# ADR-175 — A C++ functor call and an implicit conversion, drawn where the index names them in a body

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route 1, "good to go with both semantic") and
built (0.2.108-beta).

The extraction order's item 7 (`currently-open.md`): C++ functors (C-146) and implicit conversions (C-162).
Both shapes have **no call token** in the source, so ADR-131 ruled out `operator()` ("never") and ADR-132's
decision 5 left a construction with no token undrawn. This ADR asks whether either can be drawn where the
index names the target at an exact, readable position, and measures it first.

## The cells (`~/.hobbes/bench/cpp-item7-2026-10-03/`)

No C++ cell was held out after `oracle-grading.md` §10.16 (fmt fitted, args spent). The 2026-09-14 draw was
continued under a pre-registration written before any clone (`PREREG-draw.md`, §10.48): **acoustid/chromaprint**
(`aed8eba2`, 46 units) is taken, and **gulrak/filesystem** (`3812f8a6`, 15 units) held out with it, for its
64 keyed `operator()` sites. Their standing grades found a defect first (filesystem's one contradicted row),
fixed at 0.2.107-beta (ADR-135's second amendment). Positions passed over and why: `draw-continued.json`.

## The measurement

**F — a functor's `operator()`.** scip-clang writes an `operator()` reference at the **`(`** that opens the
call's argument list (`ExitedWithCode(0)(exit_status)`, col 27). Outside a template and a macro that is
the only place it writes one for a call. On fmt, 38 of its 42 `operator()` references sit inside gmock and
test macros at the macro's name; an "every reference" export adds 10 contradicted rows, all of them there.
args has none: its 248 keyed misses are `reader(…)` in a class template, where the index is silent.

**C — an implicit conversion.** scip-clang writes a constructor reference at the **first token of the
converted expression** (`return ' ';` → `EitherFlag(char)` at the `'`; `return style_ & 0x3FFFFFF;` →
`color_type` at `style_`). ADR-132's simulation called these its `other` class and found it mixed. Read by
syntax on the fitted cells, the mix splits cleanly: every row in a body, under a `return`, an argument
list or an expression, is confirmed (fmt 18, args 14). Every row the key cannot judge is a constructor's
own in-class declaration, which the index points at the out-of-line definition (fmt 22, args 2; ADR-132's
two `RaiiSubparser` rows). One more sits in an ERROR node.

**The rules as worded (`PREREG-rules.md`), simulated on both held-out cells after the predictions:**
- **F:** a lane B reference named `operator()`, in-repo, at exactly the `(` opening a `call_expression`'s
  `argument_list`, outside an unevaluated operand and any `template_declaration` → `calls`.
- **C:** a lane B reference onto a constructor (ADR-132's constructor set), at a token that is neither a
  recorded construction token nor a call site's name, inside a function body (a `compound_statement`
  ancestor reached before any `function_declarator` or ERROR node), outside a template and an unevaluated
  operand → `calls`.

| Cell | Rule | Rows added | Confirmed | Contradicted | Recall | Strict precision |
|---|---|---|---|---|---|---|
| fmt (fitted) | F | 1 | 1 | 0 | 30.4% (+1 pair) | 99.6% |
| args (fitted) | F | 0 | — | — | 72.9% | — |
| fmt (fitted) | C | 18 | 18 | 0 | 30.4% (+18 pairs) | 99.6% |
| args (fitted) | C | 14 | 14 | 0 | 72.9% → 73.3% | — |
| chromaprint (held out) | F | 1 | 1 | 0 | 47.8% | 99.7% |
| chromaprint (held out) | C | 6 | 6 | 0 | 47.8% → 47.9% | 99.7% |
| filesystem (held out) | F | 35 | 35 | 0 | 15.3% → 15.5% | 99.8% |
| filesystem (held out) | C | 143 | 143 | 0 | 15.3% → 16.0% | 99.8% |

Poison PASS on every export. Silent rows unchanged on every cell: no row the key cannot judge is added.
Against the pre-registration, H1, H3, H4 and H5 are met. **H2 missed on its count**: F added 35 rows on
filesystem against the 0–30 predicted, though its bar was met, since all 35 are confirmed. H6 (no other
language moves) waits for the build.

## What stays undrawn (the residuals the register keeps)

- **No reference at all:** an implicit conversion inside a braced list (args's 484 `EitherFlag` rows); an
  implicit **conversion operator** call (ADVobfuscator's `operator const char *`, keyed `static→method`;
  the index writes only the literal operator on that line); a dependent type's construction.
- **The index's answer is withheld:** inside a template (C-153's reason, unchanged); at a macro's name
  (C-131).
- C-174's C++ list says a conversion operator "is not a symbol" (C-175); that has been stale since
  0.2.81-beta, and the build corrects it.

## Decision (proposed)

Draw F and C in the join, beside ADR-131's and ADR-132's rules. Lane A records the call-paren token
(packed as the operator tokens are) and, for C, the body/declarator test per construction-shaped
reference position. Both draw `calls` with no scope change. Both are counted in the ingest summary, as the
`operators:` and `constructions:` lines count theirs.

## Routes for Max

1. **(Recommended) Build F and C, both `semantic`.** The edge's target and its existence are the index's.
   The syntax only places the token (F) or excludes a declaration (C), and ADR-131 and ADR-132 tier the
   same shape `semantic`. One patch (0.2.108-beta): C-146 and C-162 narrowed, C-174's text corrected.
   Real-repo effect: filesystem +178 confirmed (recall 15.3% → 16.2%), chromaprint +7, fmt +19, args +14.
2. **Build F `semantic`, C `syntactic`.** C's guard is a syntactic read (in a body, not in a
   declarator). Under the 2026-10-02 rule ("syntactic over semantic when not clearly semantic") that may
   decide its tier. The same rows are drawn, at a weaker tier.
3. **Build F only.** ADR-132's decision 5 stands, and C stays a registered concession.

## Consequences

- Recall moves less than a point on every cell. The shapes are rare outside templates and macros, and
  the large remainders (template bodies, gtest/Catch2 macros) are other entries' (C-153, C-131).
- No new node and no new kind of edge. A rule that adds rows the key confirms on two cells it was not
  fitted on, and adds none it cannot judge.

## Built (0.2.108-beta)

- **F:** `"()"` is appended to `OPERATOR_SPELLINGS`; `_operator_of` reads a `call_expression`'s
  argument-list `(`, except `noexcept(..)`'s (an operand, not arguments). The join is ADR-131's,
  unchanged: `operator()` → spelling `()`.
- **C:** `CppFile.bodies` (`_body_regions`, `body_expression` in `extract/cppsource.py`). Its spans are
  every `compound_statement` (open outside a template and an unevaluated operand), and closed spans for a
  `function_declarator`, an ERROR node, an unevaluated operand and a callee written as a name (identifier,
  qualified identifier, template type). The join's `_implicit_construction` reads it beside ADR-132's
  constructor set, after the construction token answers nothing, and skips a position where lane B names a
  macro (`_macro_positions`, from `minted.macro_lines` and macro monikers in `external_refs`). Counted as
  `constructions.implicit` and on the ingest summary's `constructions [c++]` line.
- **The first build, corrected before the commit:** it closed every callee, so it refused 8 key-confirmed
  rows the simulation drew. These are the conversion of a call's result, where the reference sits at a
  receiver (`xml.scopedElement(…)` at `xml`) or a named cast. The rule as worded closes a callee written as a
  name only. The corrected build equals the simulation everywhere but filesystem. There, **6 rows the
  simulation drew are refused by ADR-132's several-monikers guard**: a move constructor's line carries two
  constructor monikers, and the simulator had read its own, looser constructor set. The build keeps the
  guard.

**Regraded (`~/.hobbes/bench/cpp-item7-2026-10-03/build2/`), 0.2.107 → 0.2.108:**

| Cell | Confirmed | Contradicted | Recall | Strict precision | F drawn | C drawn |
|---|---|---|---|---|---|---|
| filesystem (held out) | 3,048 → **3,220** | 0 | 15.3% → 16.1% | 99.8% | +35 | 161 |
| chromaprint (held out) | 2,681 → **2,688** | 0 | 47.8% → 47.9% | 99.7% | +1 | 7 |
| fmt | 7,026 → **7,045** | 0 | 30.4% | 99.62% (7,045/7,072) | +1 | 19 |
| args | 2,567 → **2,581** | 0 | 72.9% → 73.3% | — | 0 | 14 |
| ADVobfuscator | 210 → **213** | 0 | 68.7% → 69.2% | 99.5% | +3 | 0 |

Poison PASS and silent rows unchanged on every cell. No `operators` in-template count moved, so no `uses`
edge was withheld. This repo's own graph is unchanged on every file the commit did not edit (H6).
Pre-registration (`PREREG-rules.md`): B2, B3 and H6 are met. B1 is met on chromaprint, fmt and args, and
missed on filesystem by the 6 refused rows above.
