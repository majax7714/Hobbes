# ADR-121 — No call in an unevaluated operand: lane A records no site under `sizeof`, `alignof`, `decltype`, `noexcept` or a requires-expression

**Date:** 2026-09-16 · **Status:** accepted; built through the harness (ADR-107), the Hobbes unit first and the oracle unit after it · **Owner:** Max · **Source:** Max, 2026-09-16 ("review top level documentation then proceed with an item from the hobbes review"); the review's next undone item, "lift C-155 at lane A".

Lifts **C-155** (a C++ `calls` edge drawn inside an unevaluated
operand). Amends architecture **§3.8**'s C++ row. Logs the oracle's
matching defect as **H-32** (`oracle-defects.md`), fixed as a second
unit under `bench/`. Patch: what the layer draws.

## Context

C-155 (registered 2026-09-16, H-31's seventh row) is a C++ call site
inside an operand the program never evaluates. fmt's
`test/compile-test.cc:127` reads
`fmt::detail::compile<decltype(fmt::arg("arg", 42))>(FMT_COMPILE("{arg}"))`:
lane A's walk sees `arg("arg", 42)` as a `call_expression`, lane B's
index holds an occurrence of `arg` at that position, the join reads the
two as a call, and the graph draws `compile-test → fmt::arg`. The
compiler emits no such call — a `decltype` operand is unevaluated by
definition — so clang's own front end, the cell's key, holds no site
there, and the edge is the cell's one contradiction that is neither
scip-clang's (C-153) nor the oracle's. The entry's count was an upper
bound: 27 edges on lines containing `decltype(`, one read.

The review (2026-09-16) put the lift third in its order of work, after
the `relationships` measurement (ADR-120): abstain at lane A under the
four unevaluated contexts, "graded on fmt's stored key". This record
measures first, then decides, on both sides of the grade.

## What was measured, before the decision

**The grammar** (tree-sitter-cpp 0.23.4, the pinned lane A). The
contexts and how they parse:

| Written | Node the operand sits under | Lane A today |
|---|---|---|
| `sizeof(f(x))`, `sizeof f(x)` | `sizeof_expression` | a site on `f` |
| `alignof(decltype(f(x)))`, `__alignof__(…)` | `alignof_expression` → `decltype` | a site on `f` |
| `decltype(f(x))` — in a template argument, a trailing return type, a `using` alias, an `alignas` | `decltype` (inside a `type_descriptor`) | a site on `f` |
| `noexcept(f(x))` as an expression — a `static_assert`, an initialiser, the operand of a `noexcept` **specifier** | a `call_expression` whose callee is the identifier `noexcept` | **two** sites: one on `noexcept`, one on `f` |
| `typeid(f(x))` | a `call_expression` whose callee is the identifier `typeid` | two sites: `typeid` and `f` |
| `requires { f(x); }`, `requires(T t) { t.f(); }` | `requires_expression` → `requirement_seq` | a site per call |

The grammar spells `noexcept` and `typeid` as ordinary identifiers in
call position, so lane A has been recording a call to a keyword at each
of them; the fallback finds no definition and the tail reads it
`unclassified`.

**The cells** (every lane A site whose node has one of those ancestors,
counted with the walk `cppsource` uses, against each cell's standing
key in `~/.hobbes/bench/oracle-defect-drivers/regrade-out/h31/`):

| Cell | Sites in an unevaluated operand | By context | Of which draw a graded edge |
|---|---|---|---|
| fmt | **49** | `decltype` 49; `sizeof`, `alignof`, `noexcept`, `requires` 0; plus 1 `typeid` pseudo-call | **1** — `compile-test.cc:127` `arg`, contradicted |
| args | **7** | `decltype` 7 | 0 |
| this repo | 0 | — | — |

The other 48 on fmt and all 7 on args are `ctx.begin()`, `ctx.out()`,
`std::declval<…>()`, `std::back_inserter(buf)`: a member call on a
template parameter's type, which neither lane resolves, or a call into
the standard library, which lane B places outside the repo (ADR-111).
None draws an edge today, so **the lift moves exactly one graded row on
the two C++ cells**, and C-155's "27, an upper bound" was 1 in truth on
that count and 49 sites in all. The 12 edges on `sizeof(` lines the
entry mentioned all sit outside the operand: fmt has no lane A site
under a `sizeof` at all.

**Corrected 2026-09-16, after the regrade — the count above is wrong
twice, both errors mine and both in the flattering direction.** The
measurement walked the six C++ extensions and skipped the 25 `.h`
files C++ claims, and it matched a site to its graded row by the
target's bare name, so a target spelled `parse_context::begin` never
matched a site named `begin`. Re-measured with the provider's own file
list and the landed predicate: fmt has **299** lane A sites under an
unevaluated operand (294 `decltype`, 5 `sizeof`; 183 in headers, 116
under `test/`), plus 6 `typeid` pseudo-callees, and **26** of them drew
an edge in the standing export — the 1 contradiction and **25
oracle-silent edges**, every one read and every one a `decltype`
operand (`-> decltype(ctx.begin())` and `void_t<decltype(…)>` shapes).
args: 7 sites, 0 edges, as stated. So the lift removed 26 rows from
fmt's export, not 1; the judged outcome is exactly as predicted.
§10.10 records P52 and P54 as missed on the counts and met on the
judgement.

**The oracle** (clang 18's `-ast-dump=json`, run in the image on a
probe holding every shape above). The dump keeps the `CallExpr` under
`UnaryExprOrTypeTraitExpr` (`sizeof`, `alignof`), `CXXNoexceptExpr` and
`CXXTypeidExpr`; it holds **no** `CallExpr` under a `decltype`, whose
operand is printed as part of a type string and never walked. O10's
reader descends every `inner` array and records every call kind it
meets (`isCallKind`), so **the key holds a site for `sizeof(f())`,
`noexcept(f())` and `typeid(f())` and none for `decltype(f())`.** On fmt
and args that asymmetry costs nothing — no site under the first three —
but it is a false site in the key by the lane's own definition (a call
the program makes), the same class as H-21's synthetic `super()` and
H-13's attribute-line call: code that reaches the front end and is not
a call. It is logged as **H-32**, open until its unit lands.

## Decision

### 1. Lane A — `cppsource` (the Hobbes unit; patch)

- **A call site under an unevaluated operand is not recorded.** In
  `_calls`, a `call_expression`, `new_expression` or construction whose
  ancestors include a `sizeof_expression`, an `alignof_expression`, a
  `decltype`, a `requires_expression`, or a `call_expression` whose
  callee is the bare identifier `noexcept`, records no site — the
  provider sees no call, the rule the named casts and the operators
  already follow (C-63's face). The walk to the root is unbounded: a
  lambda inside a `decltype` is not emitted either.
- **`noexcept` and `typeid` in call position are keywords, not
  callees.** A `call_expression` whose callee is either bare
  identifier records no site of its own; `_NAMED_CASTS`' rule, widened
  to a small set of non-callable spellings.
- **`typeid`'s operand keeps its sites.** `typeid(f())` evaluates its
  operand when it is a glvalue of polymorphic class type
  ([expr.typeid]/3), and lane A cannot type it. A site drawn there is
  right when `f` returns a polymorphic reference and wrong otherwise;
  keeping it is the conservative side of a case the syntax cannot
  decide, and the residual is written on the lifted entry.
- **Constant expressions are not unevaluated.** `static_assert(g(), …)`,
  the `noexcept` *specifier*'s own condition (`noexcept(is_nothrow<T>())`
  as against `noexcept(noexcept(…))`), an `alignas(N)` — the compiler
  evaluates these and clang's dump holds them; their sites stay.
- The C walk does not change: C has `sizeof` (rarely over a call) and
  `_Alignof`, no `decltype`, `noexcept`, `typeid` or `requires`; its
  cells stand at 100% and a change there is a separate measurement.

  **Amended 2026-09-16, after the oracle unit — C's walk abstains
  too.** The oracle's rule is the reader's, and the reader is one for
  both languages: `UnaryExprOrTypeTraitExpr` is C's `sizeof` and
  `_Alignof` as much as C++'s, so once §3 landed the key abstained
  under `sizeof(f(x))` in C while lane A's C walk still recorded it —
  the doer of the oracle unit said so in its closing lines. Measured on
  cJSON, sqlite-vector and `minic`: **0** C call sites under a `sizeof`
  or `_Alignof`, so no cell moves. The asymmetry is closed on the lane's
  side rather than registered: `csource`'s walk records no call site
  under a `sizeof_expression` or an `alignof_expression`, the same
  predicate one grammar over, as a third unit. **Residual, C's own:**
  C11 6.5.3.4 evaluates a `sizeof` operand whose type is a
  variable-length array (`sizeof(int[n()])` calls `n`); the syntax
  cannot tell a VLA type from any other, so that call is dropped with
  the rest and the lifted entry says so.

### 2. The join and the tail — unchanged, and the review's sketch corrected

The review sketched "claim lane B's occurrence so no `uses` edge
appears; tail class `unevaluated`". Neither half is taken:

- **Lane B's occurrence falls through as a `uses` edge**, as every
  resolution no syntax site claims does. The reference is real — the
  file depends on `fmt::arg`'s declaration to type-check — and `uses`
  is the join's name for exactly that ("a type annotation … true, useful
  for dependency questions, and emphatically not a call"). Claiming it
  would hide a true dependency to silence a wrong call; the wrong call
  is already gone once lane A records no site. This differs from
  `union-member` (ADR-104), where lane B's answer was one possible
  dispatch presented as the resolved one — wrong, so vetoed.
- **No tail class.** The tail names sites the graph saw and could not
  or would not resolve; a site that is not a call is not a concession
  and has nothing to surface. `CLASSES_AVAILABLE["cpp"]` stays at
  seven. A file's coverage row simply counts fewer sites (fmt: 49
  fewer of about 51,000), which is the truth of it.

### 3. The oracle — O10 (the second unit; `bench/` only, no version move)

- `walkNode` records no call kind whose ancestors include a
  `UnaryExprOrTypeTraitExpr`, a `CXXNoexceptExpr` or a `RequiresExpr`;
  the subtree is still walked for declarations, and its calls are
  counted as `excluded.unevaluated`, the provenance rule's shape (drop
  and count). `CXXTypeidExpr` is kept, for the reason §1 keeps it. A
  `decltype` operand never reaches the reader and needs no rule.
- A fixture, `bench/oracle/testdata/cppclang/uneval.cpp`, on
  `macroqual.cpp`'s pattern (its own compile database, `TestCppclangFixture`'s
  25 sites untouched): one call under each shape, `typeid`'s kept, a
  `static_assert` kept, and an evaluated control on the same line as an
  unevaluated one — the H-30 rule's shape, so the test also pins that a
  line holding both still keys the real call.
- The two units are one decision because a fix to one side alone moves
  the grade the wrong way: Hobbes abstaining under `sizeof` against a
  key that holds the site turns a non-call into a *miss*; the key
  abstaining alone turns Hobbes' edge into a contradiction. Both
  abstain, on the same list, `typeid` excepted on both.

### 4. C-155, the register, the version

- **C-155 lifted**, at the bottom of `extraction-cpp.md`: the technique
  is §1; the residual edge cases are `typeid`'s operand (kept, wrong
  when the operand is not a polymorphic glvalue), an operand a macro
  spells (`MACRO(f(x))` where the body is `decltype(…)` — the macro gap,
  C-131), and a `.h` C++ did not claim, which C's walk reads with no
  such rule (C-142's face).
- The register: 157 entries, 113 active (87 surfaced, 21 partial, 4
  unsurfaced, 1 n/a), 27 lifted. **C-153** is now the whole of fmt's
  contradictions.
- **Version:** patch, 0.2.33-beta, with the Hobbes unit's merge. The
  oracle unit moves nothing (ADR-103).

## Pre-registered (`oracle-grading.md` §10.10, before the regrade)

fmt regraded against its **standing** key: the Hobbes side re-exported
from a fresh ingest of the same clone, so the export moves and the key
does not. Predicted: edges 3,525 → 3,524; contradicted 5 → **4** (all
C-153); confirmed 3,269 unchanged; precision 99.85% → **99.88%**
(3,269/3,273); like-for-like 99.66% → 99.69% (3,269/3,279); recall
unchanged (the row removed was never a key pair); args identical row
for row. Then, after the oracle unit, the key re-run contained: fmt's
and args' keys identical site for site, because neither has a site
under `sizeof`, `noexcept` or a requires-expression — the fixture is the
only place H-32 is observable.

## Consequences

- One wrong edge gone on fmt and, by the measurement, nothing else on
  the two cells; on a repo that writes `sizeof(f(x))` the change is
  larger and unmeasured, which the lifted entry says.
- Lane A and the key now hold the same rule for what an unevaluated
  operand is, `typeid` included, so a future contradiction there is a
  real disagreement and not a definition gap.
- The review's sketch was wrong in two details (claim, and a tail
  class), and this record says why rather than building them.

## Record

- 2026-09-16 — measured (the grammar, the two cells, the oracle's dump
  in the image); decided; §10.10 written; H-32 logged open. The Hobbes
  unit dispatched next, the oracle unit after its merge.
- 2026-09-16 (last) — **the C unit landed** as `S-20260916T231525Z-367f`
  (29 turns, $1.37, gate right-clear, merged `83b60c9`), 0.2.34-beta.
  Both keys re-run after the oracle unit: args identical, fmt 6 sites
  gone (all `sizeof` operands), no judgement moved — §10.10's P56,
  missed on its premise and met on the judgement. The three units
  together: fmt **99.88%** (3,269/3,273), every contradiction left
  C-153's.
- 2026-09-16 (later still) — **the oracle unit landed** as
  `S-20260916T230256Z-5261` (57 turns, $4.09, gate right-clear, merged
  `fffadbd`); H-32 fixed, `sites_unevaluated` in coverage. Its doer's
  finding that the rule reaches C is the amendment above; the C unit
  follows.
- 2026-09-16 (later) — **the Hobbes unit landed** as
  `S-20260916T225041Z-d95c` (32 turns, $2.08, gate right-clear, merged
  `86b826a`), 0.2.33-beta. fmt regraded against its standing key:
  contradicted 5 → **4** (all C-153), confirmed 3,269 unchanged,
  **99.88%** (3,269/3,273), like-for-like 99.69%; the export lost 26
  rows, all at unevaluated sites (the correction above); args identical
  row for row. C-155 lifted. The oracle unit dispatched after it.
