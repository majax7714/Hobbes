# ADR-131 — A C++ operator is a call where the index names it at the token, outside a template

**Date:** 2026-09-17 · **Status:** accepted; built and graded at 0.2.42-beta (unit `d1b9`; `oracle-grading.md` §10.15, P92–P97 all met: fmt 6,901/6,901 at 0 contradicted, recall 30.1%; args 2,198/2,198, 62.5%; the C cells identical); **amended the same day — inside a template the reference draws nothing, not a `uses` either** · **Owner:** Max · **Source:** the C++ recall list Max approved on 2026-09-17 (Route A), its first item; his standing direction of the same day — honesty and accuracy before a recall number; rules fail toward drawing less.

Narrows **C-146**. Extends **C-153**'s entry (what the read found).
Follows ADR-129 and ADR-130. Patch: a constraint's fix.

## Context

C-146: `a + b` has no callee identifier, so lane A records no site and
an overloaded operator draws no `calls` edge. fmt's key holds 8,627
operator sites with an in-repo target (3,901 distinct positions). The
handoff's open question was whether scip-clang emits an occurrence at an
operator token at all. Today any such occurrence, claimed by no site,
leaves the join as a `uses` edge (ADR-029).

## The measurement, first (`~/.hobbes/bench/c146-operators/`, nothing drawn)

Over fmt's cached index and the stored key:

- **scip-clang does emit them**: 4,017 references named `operator…`,
  4,015 onto a graph symbol (1,366 of those onto a symbol ADR-129
  minted). Its column is the operator token's, the key's column minus
  one.
- **3,011 of the 4,015 are not at an operator token.** They sit at a
  macro invocation's name (`EXPECT_EQ`: gtest's `operator=` and
  `operator<<` inside the expansion). Drawn, they read +2,932 confirmed
  and 73 contradicted. They are the macro class (C-131), not C-146, and
  this ADR does not draw them.
- **At the token, naively: 99.9% by the key and wrong underneath it.**
  740 edges: 489 confirmed, 4 contradicted, 148 the key cannot judge.
  The 4 are `"first"_a` — a literal operator, a true call the key does
  not record, and not an operator token. Of the 148, read by hand, about
  100 are wrong: `wday == 0` onto `basic_fp`'s `operator==`,
  `it != c.end()` onto gtest's `faketype` stub, `val * x` onto `fp`'s
  `operator*`. It is C-153 again — scip-clang's single by-name candidate
  at a dependent expression — and at the **same arity**, so ADR-130
  cannot see it. 104 more (`*out_++` onto the binary `operator*(fp, fp)`)
  an exact operator-arity rule would catch.
- **Every one of them is inside a template.** Split by whether the token
  sits under a `template_declaration`: outside, 549 candidate rows
  confirmed, 2 silent, 0 `line-unresolved`; inside, 175 confirmed and 161
  unjudged. Outside a template the arity rule fires on 0 rows.
- **The rule, fitted on fmt:** +393 edges, 391 confirmed, 0
  contradicted, 0 new `line-unresolved`; recall 29.1% → 30.1% (collapsed
  24.8% → 26.1%), strict 99.59% → 99.61%.
- **args held out** (predictions written first, the script frozen by
  hash): +136 edges, 136 confirmed, 0 contradicted, 0 silent; recall
  58.6% → 62.5%. The count prediction missed high (≤ 120 predicted). The
  in-template variant added 4 confirmed and 4 `line-unresolved` there.
- **Exactness:** 550 of fmt's 551 drawn candidates and 140 of args' 140
  sit exactly on the operator token lane A's parse shows; the one that
  does not is a declaration inside an ERROR node.
- **Cost:** operator tokens outside a template per call expression: fmt
  0.41, args 0.51, **ScummVM 2.09** (600-file sample) — about 3.2 million
  tokens beside its 1.53 million call sites (ADR-116's concern).

## Decision

1. **Lane A records operator tokens, not operator sites** (C++ only). For
   each `binary_expression`, `unary_expression`, `pointer_expression`,
   `update_expression`, `assignment_expression` (compound ones too),
   `subscript_expression` (its `[`) and `->` `field_expression`: the
   token's line and column and its spelling, with one flag — whether it
   sits under a `template_declaration`. Nothing inside an unevaluated
   operand (ADR-121's test, reused). Never `operator()`, a literal
   operator, a conversion operator, `new`/`delete`, the comma, or a named
   cast. An operator called by name (`a.operator=(b)`) is a call site
   already and stays one.
2. **They are not `Site`s and never reach the fallback, the veto, the
   coverage count or the tail.** A built-in operator is not a call, and
   lane A cannot tell one from an overloaded one; counting 3 million
   tokens as detected sites would make the denominator false. Held as one
   packed integer per token per file (`array`), so ScummVM's cost is tens
   of megabytes, not a `Site` each.
3. **The join draws the call.** A lane B resolution no call site claimed,
   named `operator` + the spelling, at **exactly** a recorded token's
   line and column with the same spelling, and the token outside a
   template, becomes a `calls` fact at semantic tier with both lanes and
   no scope of its own — the projection's enclosing-symbol lookup names
   the caller, as it does for every unscoped fact. Anything else about
   the reference is as it was: it stays a `uses` edge.
4. **Inside a template it draws no call.** Counted per ingest
   (`graph.json`'s additive `operators` block: tokens matched and drawn,
   references at a token inside a template left as `uses`). With lane B
   off nothing changes (P6): the tokens are read by nothing.
5. **No operator-arity rule.** It fires on nothing the template rule
   keeps; building it would be a rule with no measured effect.
6. Lane A's C++ cache format moves (`lanea-cpp v3`): the first ingest
   misses.

## What this leaves, registered

- **C-146 narrowed, not lifted:** an operator inside a template (175
  confirmed rows on fmt given up to keep 161 unjudged ones out), one
  inside a macro's expansion, `operator()` on an object, a literal
  operator, and the named casts.
- **C-153, found by the read and not fixed here:** the wrong candidates
  above stand in today's graph as `uses` edges, as every unclaimed
  reference does. No key grades `uses`. Put to Max as a route, not built
  — **decided 2026-09-17, the amendment below: withheld.**

## Amended 2026-09-17 (Max: "route a approved") — inside a template the reference draws nothing

The open item above, decided. Decision 4 becomes: **a lane B reference
named `operator…` at exactly a recorded token inside a template draws no
`calls` fact and no `uses` fact.** It is still counted
(`operators.in_template`, now the number withheld), and the ingest line
says so. Everything else about the join is as decided: a reference that
is not exactly at a token — one column off, another spelling, no column,
a macro invocation's name — stays the `uses` edge it was.

**Why.** A `uses` edge is read as a true dependency (ADR-029), and at a
dependent operator it is scip-clang's single by-name candidate (C-153).
No key grades `uses`, so nothing would ever contradict it. Rules fail
toward drawing less.

**Measured first** (`~/.hobbes/bench/c153-operator-uses/`, a scratch
wrapper over 0.2.42-beta, no product seam): fmt loses 156 `uses` symbol
edges (437 references, 344 distinct by line and target; 340 `uses`
evidence rows in all, the rest on edges that stand on other references),
args 24 (40 references, 27 evidence rows). Nothing is
added; nodes and symbols do not move. **One module edge goes on each
cell, and both were wrong:** `test/scan.h → include/fmt/format.h` stood
only on integer `n * 10` and `prev * 10ull` read as `fp`'s `operator*`;
`args.hxx → test/test_common.hxx` — a library header depending on its
own test header — stood only on `ss >> destination` read as the test's
`operator>>` for a tuple. The "module edges do not move" line under
Consequences was about decision 3 and stays true of it; it is not true
of this amendment, which is the point of it.

**The price, owned:** the right candidates go with the wrong ones. On
fmt the key confirms 175 of the in-template rows as calls; those were
true `uses` dependencies and are no longer drawn (C-146's in-template
residual already gave them up as calls). The largest targets withheld
on fmt are gtest's `MatchResultListener::operator<<` (31 edges) and
`internal::operator==`/`!=` (53), and `fp`'s `operator*` (28).

**Not held out.** Both C++ cells were read for the measurement, and no
key judges `uses`; §10.16's predictions check that the build equals the
probe and that the graded export does not move.

## Alternatives considered

- **Operator tokens as `Site`s through the ordinary join.** The
  name-and-nearest-column match would pair a built-in `<<` with a
  macro-carried `operator<<` on the same line, every unmatched token
  would be an unresolved site, and ScummVM would hold 3 million more
  `Site`s. Rejected.
- **Draw inside templates with an operator-arity rule.** Removes 104 of
  about 200 wrong rows; the rest are same-arity and nothing in the source
  contradicts them. Rejected on Max's direction.
- **Draw the macro-carried references.** 73 contradictions by the key,
  and a site positioned at a macro name is the macro class's question
  (C-131, parked). Not taken here.

## Consequences

`tests_guarding` and `who_calls` gain operator edges outside templates;
an iterator or stream operator in ordinary code is a caller now. A
`uses` edge becomes a `calls` edge between the same two ends, so module
edges do not move. C is untouched: it has no operator functions.
