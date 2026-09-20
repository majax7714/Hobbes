# ADR-142 — A TypeScript/JavaScript construction is a call where the index names the constructor at the `new` token

**Date:** 2026-09-19 · **Status:** accepted (Max, 2026-09-19: route **(b)**),
built as one dispatched unit; see *Accepted*, at the end. Measured and simulated
before anything was drawn · **Owner:** Max ·
**Source:** the JavaScript constraint order Max set at the 2026-09-19 close-out
("we will tackle constraints from js next session"), its second item; his
standing direction — honesty and accuracy before a recall number, and a rule
fails toward drawing less.

Would narrow **C-168** and correct what that entry claims. Follows ADR-132,
whose shape it takes: lane A records the token, the join draws the call only
where the index names a constructor at exactly that token.

## Context — and a correction to C-168 as registered

C-168 says a `new F()` draws a `uses` edge to the class, that `who_calls F`
lists it as a reference with no call site, and that it bites at "ajv 107, zod
110, hono 78, xmpp.js 104, Preact 570". **Two of those three claims are wrong,
and the fourth is a miscount** — the numbers are the cells' whole
`static→class` miss class, not the constructions in it. Read row by row
(`~/.hobbes/bench/c168-construction/`, `probe.py` + `join.py`):

| cell | key class rows | `new X()` | `new ns.X()` | `super(…)` | JSX tag (drawn) |
|---|---|---|---|---|---|
| xmpp.js | 104 | 102 | 0 | 2 | 0 |
| Preact | 576 | **0** | 0 | 193 | 383 (6 drawn) |
| ajv | 107 | 95 | 0 | 12 | 0 |
| zod | 110 | 101 | 9 | 0 | 0 |
| hono | 78 | 74 | 0 | 4 | 0 |
| cheerio | 5 | 5 | 0 | 0 | 0 |
| kbet | 8 | 0 | 0 | 0 | 8 (8 drawn) |
| Express | 0 | — | — | — | — |

Preact's 570 hold **no construction at all**: 193 are `super(…)` and 377 are
JSX tags of a class component that declares no constructor — every one keyed to
`Component` in `src/index.d.ts`, not to the class written at the site. A JSX tag
whose component *does* declare a constructor is already drawn (Preact 6 of 6,
kbet 8 of 8; C-24).

And at a real construction the join draws **nothing**, not a `uses` edge: at a
`new X()` token scip-typescript names `<constructor>` at the constructor's own
declaration line, which is below the symbol floor (C-58), so the reference is
dropped. The `uses` edge C-168 describes exists only at the **import** line, and
at the one shape where the index names a class rather than a constructor — a
class that declares none.

## The measurement (nothing drawn; `PREREG.md` written before any grade)

**What each lane says at a `new` token** (`laneb.py`, the cells' own facts
streams; the mini reproduction under `mini/` shows the same three answers):

- The class declares a constructor → the index names `<constructor>`, defined
  inside that class. **xmpp.js 101 of 102, ajv 89 of 95, hono 67 of 74.** The
  class holding the constructor is, every time, the class the key names.
- The class declares **none** → the index names the class itself, while the key
  names the **base** class whose constructor actually runs: ajv 6, hono 5,
  zod 43. Those sites already carry a `uses` edge.
- An ES5 constructor function → the index names the function or the variable it
  is bound to (Express 6, xmpp.js 23).
- Nothing at all: cheerio 5 (a local class), `new this(…)` (xmpp.js 1).

**The naive rule is dead on that second line.** Promoting today's `uses` edges
at a `new` to `calls` would draw 3 confirmed and **55 contradicted** — the first
loss of JavaScript's 100%. It is not probed further.

**The rule simulated** (`sim.py`, the export a rule would produce; graded by
`oracle grade -poison` against the stored keys). Every prediction in `PREREG.md`
met:

| cell | before | (a) constructor only | (b) + constructor function | contradicted |
|---|---|---|---|---|
| xmpp.js | 552 (66.4%) | 653 (78.5%) | **676 (81.2%)** | 0 |
| ajv | 1,410 (63.5%) | 1,499 (67.5%) | 1,499 (67.5%) | 0 |
| hono | 768 (55.0%) | 836 (59.9%) | 836 (59.9%) | 0 |
| Express | 992 (65.3%) | 992 (65.3%) | **998 (65.7%)** | 0 |
| Preact | 2,446 (28.6%) | 2,446 (+1 silent) | 2,447 (28.6%) | 0 |
| cheerio | 2,628 (45.1%) | 2,628 | 2,628 | 0 |
| zod | 9,731 (45.1%) | 9,764 (45.3%) | 9,765 (45.3%) | 0 |

100% precision and poison PASS on every cell, either route; no confirmed row is
lost anywhere. On hono the rule also draws 867 rows outside the graded zone,
which the key cannot judge (`not-loaded`) — the cell is one zone of the repo.

**One prediction missed: P7, zod's count.** +33 against +58 ± 8, because 719 of
its 946 `new` tokens carry no lane B resolution at all — which a read of the
key's rows alone could not see. Its precision half held: 0 contradicted, and the
43 no-own-constructor rows were refused as designed. The full record is
`RESULTS.md` beside the pre-registration.

## Decision — routes

**(a) The constructor only.** Lane A records a `new` expression's callee
terminal identifier as a **construction token** (1-based line, 0-based column),
never a `Site` — ADR-132's shape, so it reaches no fallback, no veto, no
coverage count and no tail class. The join draws a `calls` edge where lane B has
a resolution at **exactly** that token whose definition is a constructor, to the
innermost class symbol whose extent holds the constructor's definition line:
semantic tier, both lanes, no scope, no `argc`. Anything else at the token is
left exactly as it is today. +101 xmpp.js, +89 ajv, +68 hono.

**(b) Recommended: (a), and a constructor function the index names.** Where the
index names a definition that is **not** a class at the token — an ES5
`function User(…)` or the variable it is bound to — the edge is drawn to that
symbol on the same terms. A **class** named at the token is still refused, which
is exactly the shape the key contradicts. Adds Express's 6 and xmpp.js's 23 over
(a), all confirmed, and closes Express's last `static→function` miss. This is
the route that draws every row both lanes agree on and no row the key disputes.

**(c) Draw nothing; correct the entry.** Rewrite C-168 to what the rows say —
three shapes, the `uses` claim withdrawn — and leave the construction undrawn.
Honest, and it leaves ~12 points of recall on xmpp.js where both lanes already
agree.

## What this leaves, registered (C-168 narrowed, still partial)

- **`super(…)`** — 211 rows across the cells (Preact 193, ajv 12, hono 4,
  xmpp.js 2). Lane A treats a keyword callee as no site at all, by design; the
  key names the base class. Unmeasured as a rule.
- **A JSX tag whose component declares no constructor** (Preact 377): the key
  names the base class in a `.d.ts`; Hobbes has no symbol there.
- **A `new` token the index does not resolve at all** — zod 719 of 946, cheerio
  63 of 63, Express 138 of 213: a cross-zone or unprovisioned dependency (C-165,
  C-23), or a local class. Recall only.
- **A class that declares no constructor** (ajv 6, hono 5, zod 43): the index
  names the written class, the key the base. Refused — not a recall gap that can
  be closed without contradicting the key.
- **`new this(…)`** (xmpp.js 1) and a computed callee: dynamic, C-1.
- **`new ns.X()`** (zod 9): the index names the module at the token.
- **A local class the index does not reference at the token** (cheerio 5).

## Consequences

`who_calls` on a class gains every construction of it, and its wording stops
being wrong for a construction: the site *was* detected. `tests_guarding` gains
the tests that only construct a type — on xmpp.js that is most of its test
suite. A row that is drawn today as `uses` at an import line is untouched, and
no module edge moves. A patch (what the layer draws), built as one dispatched
unit; C++ and Java are untouched, each having its own rule already
(ADR-132, ADR-096).


## Accepted (Max, 2026-09-19: route b)

Built as one dispatched unit. The code facts the brief rests on, each read in
the tree or run before the dispatch:

- **`new` is no site today.** `extractCalls` (`tsextract/extract.mjs`) walks
  `CallExpression` and the two JSX element nodes and nothing else; a
  `NewExpression` is never visited, so lane A records no site and no name there.
- **Lane A's facts version is `HELPER_VERSION = 5`,** declared in
  `tsextract/extract.mjs` and `pipeline/src/hobbes/extract/tssource.py` and held
  equal by `pipeline/tests/test_helper_contracts.py`. A new facts key bumps
  both, in one commit. Lane A's TS facts are not cached (the index cache is lane
  B's), so no cache format moves with it — unlike ADR-132's `lanea-cpp v4`.
- **A TS reference reaches the join carrying its column** (`scipsource.py`, the
  `Site(… col=ref["col"] …)` the merge builds), which is what an exact-position
  rule needs.
- **The join already takes `constructions` and `constructors`,** passed from
  `extract/__init__.py` for C++ alone. A TS reading is their sibling and moves
  nothing C++ does.
- **A constructor starts no symbol.** `index.starting_at(target_module,
  def_line)` answers `None` at a TS `<constructor>`'s line, so the reference
  falls `below_floor` and is dropped — which is why nothing is drawn there
  today, and why the rule must name the class instead. Lane B's own definition
  rows give it: the constructor's moniker is the class's moniker plus one
  descriptor (`…/Base#` and ``…/Base#`<constructor>`().``), and a class's row
  carries `kind: "type"` where the constructor's carries `kind: "method"`.
  `minted.constructor_lines` reads scip-clang's spelling (`…/T#T(hash).`), not
  this one, so the TS reading is its own.
- **The fixture already holds both halves, and was simulated:** `minijs`'s
  `index.js:8` `new Counter(1)` is an ES5 constructor function the key resolves
  to `lib/counter.js:3` — drawn under (b) — and `esm/main.mjs:3` `new Greeter()`
  is a class that declares no constructor, where tsc synthesises the construct
  signature and the key is **silent** — refused. Simulated on the cell:
  **7/7 → 8/8, recall 63.6% → 72.7%**, 0 contradicted, poison PASS.

The unit: the token in `tsextract/extract.mjs` beside `extractCalls`, the
constructor reading and the rule on the TS path, the two counts in the graph's
additive `constructions` block, tsextract cases for the shapes (a class with a
constructor, a class without one, an ES5 constructor function, `new ns.X()`,
`new this()`, a `new` inside a string or comment), the `minijs` fixture's new
row, and a `lane_b` case with its lane-B-off twin (with no index nothing is
drawn, P6).
