# ADR-132 — A C++ construction is a call where the index names the constructor at the token, outside a template

**Date:** 2026-09-17 · **Status:** accepted; measured, not yet built (`oracle-grading.md` §10.17 holds the predictions for the build) · **Owner:** Max · **Source:** the C++ recall list Max approved on 2026-09-17 (Route A), its second item; his word on the constructions read the same day ("good to go with recommended"); his standing direction — honesty and accuracy before a recall number; rules fail toward drawing less.

Registers **C-162** with the build (the C++ segment had no entry for a
construction that draws no call). Follows ADR-131, whose shape it takes.
Patch: a constraint's fix.

## Context

`T x(args);`, `T x{…};`, `T x;`, `m_(args)` in a constructor's
initialiser list, `{a, b}` passed where a `T` is expected, `T{…}`,
`new T(…)` and a defaulted parameter `T p = {}` all call a constructor
and none has a callee lane A records: the written name is a variable, a
member, a brace or a type. Only `T(args)` is a call site. fmt's key holds
8,331 constructor sites and the graph confirmed 216; args' 889 missed
constructions were 67% of what that cell had left.

## The measurement, first (`~/.hobbes/bench/cpp-constructions/`, nothing drawn)

**Step 0, the misses by class** (`probe.py`, `classes.py`; args held
out, `PREREG-args.md`). Of fmt's 8,047 distinct missed pairs: 80.2% have
the constructor (or only its class) named at a **macro invocation's
name** — gtest's `Message` and `AssertHelper` at `EXPECT_EQ` — the macro
class (C-131), not this one; 6.9% are gtest's `new TestClass` onto a
`TEST` line; 10.1% have **no lane B reference on the line** (690 of 814
inside a template: a dependent type's construction is not indexed); and
**152 (1.9%) name the constructor at a real token outside a template**.
args, run once: no macros; 383 of 889 (43.1%) in that last class, 324 of
them at the `{` of a braced argument (`{'f', "foo"}` → `Matcher`); 484
are the implicit conversion of the literals inside those braces onto
`EitherFlag`, for which scip-clang emits nothing. Two of five predictions
missed (the largest class, and the dominant shape).

**Step 1, the rule simulated and graded** (`simulate.py`, exports graded
by `oracle grade`; args held out on the precision side,
`PREREG-args-sim.md`). A candidate is a lane B reference whose target's
definition row carries a constructor moniker (`…T#T(hash).`), not already
an export row.

- **fmt, naive** (every candidate): +6,171 rows, **95 contradicted** —
  94 of them at a macro's name. Not drawn.
- **fmt, at a construction token outside a template:** +135 rows, **111
  confirmed, 0 contradicted, 0 `line-unresolved`**, 24 `unreachable` —
  read by hand, all right: 23 `MutexLock l(&m)` onto `GTestMutexLock`'s
  constructor through its typedef, and `basic_format_context<appender,
  char>` onto `context`'s. Recall 30.1% → 30.4%.
- **One class of wrong row, found on fmt and removed before args was
  run:** a constructor's own in-class declaration, which lane B points at
  its out-of-line definition (`explicit UnitTestImpl(UnitTest*);`, 4
  rows). The class head is macro-broken (`class GTEST_API_ X {` parses as
  a function, `public:` as a label, `explicit` as the type), so the
  declaration looked like a local. It sits under a `labeled_statement`;
  a recorded declaration must sit directly in a block.
- **args, held out, run once:** +369 rows, **369 confirmed, 0
  contradicted, 0 silent**; recall 62.5% → **72.9%**. P-s1–P-s4 met;
  P-s5 half missed (16 untokened `other` rows where ≤ 15 was predicted;
  the rule draws none of them).
- **Inside a template** the same rule would add 44 rows on fmt — 42
  confirmed, 2 `unreachable` (the same `MutexLock`), none unjudged-line —
  and 1 on args, confirmed. Unlike operators, no wrong row was found
  there: a dependent type's construction gets no reference at all (the
  690 above), so what scip-clang does emit in a template is a
  non-dependent type's. That is 45 rows of evidence, not a mechanism
  proved; see decision 4.
- **No token, not drawn:** 43 references on fmt and 16 on args sit at an
  arbitrary expression (`return style_ & 0x3FFFFFF;` converting to
  `color_type`; `fmt::format(loc, …)` converting to `locale_ref`). The
  key confirms 20 and 14 of them; the rest are the constructor-declaration
  junk above. There is nothing to be exact about, so nothing is drawn.
- The simulation's final form (`simulate.py` v2, the structural test
  lane A can apply without the constructor's name) draws exactly the rows
  v1 drew on both cells; v2 was written after the args run and only
  removes rows.

## Decision

1. **Lane A records construction tokens, not construction sites** (C++
   only), packed beside the operator tokens and read by nothing but the
   join. One per:
   - `decl-init` — the declared identifier of an `init_declarator` whose
     value is an `argument_list` or an `initializer_list`;
   - `decl-paren` — the identifier of a `function_declarator` directly
     under a `declaration` inside a function body (`T x(arg);`, which the
     grammar reads as a function declaration);
   - `decl-default` — the declared identifier directly under a
     `declaration` (`T x;`);
   - `member-init` — the `field_identifier` that opens a
     `field_initializer`;
   - `braced` — the `{` of an `initializer_list` held by an
     `argument_list` or a `return_statement`;
   - `default-arg` — the `=` of an `optional_parameter_declaration`;
   - `compound-literal` and `new` — the start of the type of a
     `compound_literal_expression` or a `new_expression`.
   For the three `decl-*` kinds the `declaration` must have a `type` field
   and sit directly in a `compound_statement`, `case_statement`,
   `for_statement`, `condition_clause`, or at namespace or file scope
   (`translation_unit`, `declaration_list`, a `preproc_*` block) — never
   under a `labeled_statement`. Nothing inside an unevaluated operand
   (ADR-121's test), nothing under an ERROR node. Each carries the one
   flag: under a `template_declaration` or not.
2. **They are not `Site`s** and never reach the fallback, the veto, the
   coverage count or the tail, for ADR-131's reason: `int x(3);` is a
   token and no call, and lane A cannot tell.
3. **The join draws the call.** A lane B resolution no call site claimed,
   whose target is a **constructor** — the definition row at its
   `(def_file, def_line)` carries a moniker whose last two descriptors are
   a type and a method of the same name, read with `minted.read_moniker`
   — at **exactly** a recorded token's line and column, the token outside
   a template, becomes a `calls` fact at semantic tier with both lanes, no
   scope, no `qualifier`, no `argc`. Anything else is the `uses` edge it
   was. A line and definition with more than one moniker is not a
   constructor for this rule.
4. **Inside a template it draws no call and the reference stays `uses`.**
   Counted per ingest (`graph.json`'s additive `constructions` block:
   `drawn`, `in_template`). This is not ADR-131's amendment: there the
   in-template references read wrong by hand and were withheld; here 45 of
   45 read right, so the `uses` edge is a true dependency and stays. Whether
   to draw them as calls is put to Max with those numbers — the default is
   not to.
5. **No rule for a construction with no token** (an implicit conversion),
   and none for a macro-carried one (C-131).
6. Lane A's C++ cache format moves (`lanea-cpp v4`): the first ingest
   misses.

## What this leaves, registered (C-162)

A construction inside a template; one carried by a macro (80% of fmt's
misses); an implicit conversion, which has no token; a construction
scip-clang emits no reference for (a dependent type's; the literals
inside a braced list); a base-class or delegating initialiser
(`Base<T>(args)`: no row measured, not recorded); a default member
initialiser in a class body (`T x{1};` as a field: not recorded); a
`labeled_statement`'s declaration; a `template <…>` header a macro parse
lost, which flags its tokens plain (C-146's residual, the same blind
spot).

## Alternatives considered

- **Draw every constructor reference no site claims.** 95 contradicted
  on fmt. Rejected.
- **Construction tokens as `Site`s.** ADR-131's reasons, unchanged.
  Rejected.
- **Draw inside templates too.** +44 on fmt, +1 on args, none read wrong.
  Not taken without Max's word: the C++ lane's every other in-template
  answer has needed a guard.
- **Draw the untokened conversions by line.** 34 confirmed rows across
  both cells for a rule with no exactness test. Rejected.

## Consequences

`who_calls` on a constructor gains the declarations, initialisers and
braced arguments that construct through it; `tests_guarding` gains the
tests that only construct a type. A `uses` edge becomes a `calls` edge
between the same two ends, so module edges do not move. C is untouched:
it has no constructors.
