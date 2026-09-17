# ADR-130 — R-arity: a C++ call written with more arguments than lane B's target can take draws nothing

**Date:** 2026-09-17 · **Status:** accepted; built and graded at 0.2.41-beta with ADR-129 (results in `oracle-grading.md` §10.14: the 40 named rows withheld, 0 confirmed among them) · **Owner:** Max · **Source:** ADR-129 §6's hand read of the rows its mint leaves unjudged; Max's standing direction of 2026-09-17 — honesty and accuracy before a recall number; rules fail toward drawing less. ADR-125's family: the source text contradicts the index.

Narrows **C-153** a second time. Pre-registered in `oracle-grading.md`
§10.14. Patch, in the same version as ADR-129.

## Context

ADR-129's probe read 100% on fmt with 53 new edges the key could not
judge (H-30's silence; counted against us by ADR-124's strict figure).
ADR-129 §6 required those rows read by hand before anything shipped.
Read: **34 of the 53 are wrong**, and one more among the rows the key
holds no targets for. Every one is
`copy<Char>(begin, end, out)` — three arguments — drawn to
`copy(basic_string_view<V> s, OutputIt out)` at `format.h:549`, which
takes two. The three-argument overloads are `core.h:1910–1929`. It is
C-153 exactly: the call is dependent, scip-clang indexes the pattern once
and gives one candidate, and the candidate is the wrong overload. The
key holds a dependent call as a site with no targets, so it can never
contradict the edge.

These errors were already in the index. They were invisible because
`format.h:549` had no lane A symbol (C-145) and the fact fell
below-floor. **Minting the symbol draws them.** A recall change that
surfaces 35 wrong edges no grade can see is the thing Max's direction
forbids, whatever the precision line reads.

## The measurement

`~/.hobbes/bench/c145-recovery/arity.py`, over every graded row of the
ADR-129 probe export, by bucket: the written argument count at the site
against the target's parameter list, both read from source text.

- **"Too few" proves nothing in C++**: default arguments live on the
  declaration, usually in another file. A two-sided rule flagged 152
  confirmed edges (`vformat_to` called with 3 of its 4). Dropped.
- **"Too many" is a contradiction**: more arguments written than the
  target has parameters, the target not variadic and holding no pack, the
  call holding no pack expansion. No default argument, conversion or
  template deduction makes that call land there.

| fmt, the too-many rule | fires | of |
|---|---|---|
| minted, unjudged (`line-unresolved`) | **34** | 53 |
| minted, `no-targets` (the 35th `copy` row, `format.h:1128`) | 1 | 193 |
| **standing** graph, unjudged — `holds_alternative<T>(value)` and `any_cast<T>(value)` drawn to gmock's zero-parameter ADL stubs (`gmock.h:6633`, `:6696`), `scan.h:466` | **5** | 8 + 110 |
| confirmed, minted + standing | 5 | 6,533 |

All 5 confirmed hits are the probe's regex reader failing, read one by
one: `Mock::VerifyAndClearExpectationsLocked(void* mock_obj)` missed
because the reader refused a `::`-qualified definition, and two
multi-line gtest calls. A reader on lane A's parse does not have those
failures; §10.14 holds the built rule to **0 confirmed edges withheld**.
args: the rule fires nowhere.

What the rule does not reach, said now: a wrong candidate of the **same or
greater** arity, and everything in the 19 unjudged rows that fit
(`UniversalPrint`, `PrintToString`, `GetTypeName` — single definitions,
read as right; `write<Char>(out, …)` at `format.h:2387` — not
decidable by reading). C-153 stays *partial*.

## Decision

**1. Lane A records the written argument count at a C++ call site**
(`Site.argc`), from the parse's own `argument_list`: the number of
arguments, or *unknown* when the list holds an ERROR node or a pack
expansion (`args...`), or is a braced initialiser list (`T{a, b}` may be
one `std::initializer_list` parameter). Carried onto the fact only where
lane B answered, as `qualifier` is (ADR-125).

**2. A function or method symbol carries `max_params`**: the declarator's
parameter count — `(void)` is 0 — or *unbounded* when the list holds
`...` or a parameter pack. Lane A reads it from its parse; ADR-129's mint
reads it from the definition's tokens with the same bracket-depth read it
already makes for the body, and records *unknown* wherever that read is
not clean (a macro in the parameter list, an unbalanced bracket).

**3. `project` draws no `calls` edge where `argc > max_params`**, both
known, the fact lane B's, the target a C++ `function` or `method`. The
site is returned as `arity_mismatch` and tailed **`arity-mismatch`**
beside `qualifier-mismatch`. Unknown on either side: the edge is drawn
(ADR-125 §1's accuracy side stays — the rule removes only what the text
contradicts). Never applied to a syntactic edge (lane A's own guess has
no index answer to contradict), to C (no overloads; K&R `f()`), or to a
target that is a type.

**4. Surfaced where R-qual is**: the tail class with its meaning in
`list_blind_spots` (`tailMeanings`), the ingest summary's tail rollup,
`CLASSES_AVAILABLE`, C-153's entry.

**5. ADR-129 does not ship without this.** Both land in 0.2.41-beta; the
regrade of §10.13 is read together with §10.14.

## Consequences

- fmt loses 5 standing edges, all wrong and none judged; its strict
  figure with both changes reads about 99.6% where the mint alone read
  99.06% (§10.14 predicts).
- Recall does not move: the rule withholds no edge a key confirms.
- One more reason a C++ site draws nothing, named at the site.

## Alternatives considered

- **Ship the mint and mark the region** (ADR-125 §4's note only).
  Rejected: 35 known-wrong edges are not a region.
- **A two-sided arity rule.** Rejected on the measurement (defaults).
- **Match parameter types.** Not attempted: lane A has no types.
- **Mint nothing in a template pattern's callee set.** Rejected: it gives
  up most of fmt's gain to avoid errors this rule removes by reading.
