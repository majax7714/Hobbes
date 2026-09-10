# Oracle lane — the miss record

**What this is.** Every oracle-graded cell's misses, by class, kept so
the question "what hurts the most, percentage-wise" has a standing
answer and the classes sharpen as cells accumulate (Max, 2026-08-25).
A *miss* is an oracle (site, target) pair Hobbes did not emit. Classes
are *how the call is made* × *what it reaches*; the class key is what
`oracle grade` prints. Percentages are of the cell's **honest** misses
— pairs a reachability oracle over-approximates (`func-value→*` under
RTA: every reachable function of the signature is a candidate) are
listed but marked inflated and kept out of the honest total, because
their denominator is an upper bound no run takes. Updated in the same
commit as the cell.

## Classes

| class | the call | what Hobbes does today | constraint |
|---|---|---|---|
| `static→named` | direct call of a declared function or method | drawn (the semantic lane's whole job) | — |
| `static→closure` | call of a closure bound to a local name (`run := func(...)`; `run(...)`) | **no edge** — closures are not graph symbols; lane A may name-match the local to a package function instead (a wrong edge) | C-58, C-7 |
| `interface→named` | invoke through an interface method | **no edge** — resolves to the interface method, which C-9's filter drops; no dispatch analysis | C-58 |
| `interface→closure` | invoke reaching a closure (function-typed interface) | no edge | C-58 |
| `func-value→named` | call of a function value reaching a declared function (a map of methods, a callback parameter) | **no edge** | C-58 |
| `func-value→closure` | call of a function value reaching a closure (`defer cancel()`, goroutine bodies) | no edge; under RTA the pair count is inflated | C-58 |
| `func-value→local-binding` | call through a local that holds a value, not a function literal (`const [x, setX] = useState()`; `setX(...)`) | **no edge** — the binding is below the symbol floor; the site is *seen and not modelled by design* (C-32's `local-binding` class) | C-32, C-58 |
| `func-value→variable` | call through a module-level variable holding a function value (a `let` accessor assigned at runtime; Go's `var f = g`; a `const x = factory(..)`) | drawn to the **binding** when the variable is a graph symbol — graded *abstract* against the oracle's held function since H-18 (47 rows on mux + cheerio); missed when the value arrives later | C-58 |
| `static→union-member` | TS: a member call on a union-typed receiver (`n: A \| B`; `n.render()`; hono's `c.toString()` on a `Child` union) | one member's method was drawn at semantic certainty — scip-typescript's and the checker's first-member pick; `tsc`'s resolved signature is a pick too (the first member on a two-member union, the shared base on ajv's eleven), so the grader's *confirmed* on six two-member sites was an agreement of picks, not a truth. **Closed by abstention 2026-09-09 (ADR-104, C-97):** lane A records the site `ambiguous`, the join vetoes lane B, the tail names it `union-member`; ajv regraded 1,410/1,410, hono 767/768 — the one row left was a site lane A could not type at all under a solution-style tsconfig (C-98) — lifted 2026-09-10, hono 768/768 | ADR-104 / C-97 / C-98 |
| `macro→method` | Rust: a method call a macro body makes (`define_*_quickcheck!`, `unsafe_ifunc!`) | **no edge** (as `macro→function`) | C-58 (macro face) |
| `interface→type-member` | call of a member declared only as an interface property signature (a zustand store's `ChatState.addMessage`) | **no edge** — interface members are not graph symbols (C-9) | C-58 |
| `static→anonymous-function` | an IIFE or a literal passed straight to a call | no edge | C-58 |
| `observed→closure` / `observed→lambda` | Python (trace): a call the interpreter made into a nested function or a lambda | **no edge** — nested functions and lambdas are not graph symbols | C-58 |
| `observed→function` | Python (trace): a call the interpreter made into a declared function that Hobbes did not draw — a function held in a record field or table (`pack.applies(ctx)`, argparse's `func`), a call inside a decorator expression | no edge for the function-value shapes; the direct shapes are drawn | C-58 |
| `observed→method` | Python (trace): a callable instance (`runner(...)` → `__call__`), or a receiver the indexer could not type (an unannotated parameter, a chain on a constructor) | no edge | C-58, C-2 |
| `observed→class` | Python (trace): a constructor call | drawn (an edge to the class symbol) | — |
| `macro→function` | Rust: a call made by the body of a macro the repo does not define, attributed to its invocation (`criterion_group!(benches, f)` calls `f`) | **no edge** — the author wrote a name, not a call; rust-analyzer emits the reference | C-58 (macro face) |
| `static→generated` | Rust: a call of a method a derive wrote (`x.clone()` on `#[derive(Clone)]`) | **no edge** — the target has no source identifier, so no symbol | C-9 |
| `static→method` (Rust) | a call of an extension-trait method implemented on a foreign type (`impl Ext for Vec<T>`), a `derive_builder` setter, a raw-identifier method (`r#ref`) | no edge for these shapes; ordinary inherent and trait methods are drawn (3,354/3,384 on dagger's SDK) | C-58, C-9 |
| `static→function` (Rust) | a call written inside a proc-macro's tokens (`quote! { $(f(x)) }`) | **no site** — rust-analyzer's index does not expand proc macros here | C-30 (registry) / unregistered |
| `interface→method` (Java) | a virtual or interface call, graded against the **CHA override set** (O8: the declared method plus every override below its owner in the compiled program) | the edge to the **declared** method is drawn and confirmed; every override in the set is a miss — Java's dispatch hole, the majority case, sized per cell (jsoup 67.5%, spring-data-elasticsearch 55.8%, petclinic 98.7% recall on the class) | C-58 (Java face) |
| `interface→anonymous-member` / `static→anonymous-member` (Java) | a call reaching a method declared in an anonymous class body — an override the CHA set holds (`new Evaluator() { matches(..) }`), or a direct call of a sibling helper inside the body (jsoup's `anythingElse(t, tb)` in enum-constant bodies) | **no edge** — anonymous members are below the symbol floor by decision (ADR-096); lane A records them as local bindings so the site reads `local-binding`, never unknown | C-9, C-32 |
| `static→constructor` (Java) | `new T() {..}` — the anonymous subclass's synthetic constructor calls T's | drawn as `uses` of T by decision (no lane A site); `new T(..)` on a declared or implicit constructor is drawn (an implicit one at the class line) | ADR-096 |

## Cells

### The callee-shape bucket — why a `tsc` key beats a `tsc`-based indexer (2026-09-10; cheerio and zod at 0.1.6-beta; [cells](cells/))

**Max's question.** scip-typescript sits on the same compiler as the TS
key, so a 45–64-point recall gap "is mostly what the indexer declines
to emit, not what the compiler can't see" — bucket the miss set by
callee-expression shape and the tail should concentrate in two or three
classes. Done on cheerio (3,249 misses) and zod (12,038): every miss
joined to the checker's reading of the callee at its site (an
identifier → what its declaration is; a member → what the receiver is;
`bench/oracle/shape/shapes.mjs`) and to lane A's own record there
(`bucket.py`). **The reading: the gap is the key's overload grain and
the symbol floor, not the indexer.** The joins were first written at
line and bare-name grain (H-22, found in the [2026-09-10
review](../reviews/2026-09-10-baseline.md)) and **re-done the same day
on canonical identity** — a target is its file and the checker's fully
qualified name (overload signatures share one; `A.run` and `B.run` do
not), a confirmed row hits the target at its exact position on its line
(the grader's own rule), a miss takes the checker record at the oracle
site's column and is otherwise an explicit `ambiguous` / `no record`
row, and `new X(..)` is a record — then both cells re-measured on the
0.1.8-beta grades: **cheerio unchanged** (3,826 pairs, 2,628 hit,
68.7%; 1,266 misses attributed at the column, 0 by name, 5 ambiguous),
**zod +3 pairs** the bare name had merged (16,631 → 16,634; 9,731 hit,
58.5%; 7,570 at the column, 0 by name, 12 ambiguous, 14 with no
record), 0 confirmed rows unexplained on either. The tables below stand
on that identity. Two substantial contributors are:

1. **The oracle's overload grain** — one pair per overload *signature*
   (H-19's recall side, noted 2026-08-28 and now measured). Hobbes draws
   one edge, confirmed to one signature; the siblings count as misses.
   cheerio 1,972 of 3,249 misses (60.7%: `attr` ×5, `prop`, `html`); zod
   4,442 of 12,038 (36.9%: `string`, `toJSONSchema`, `literal`).
2. **Targets below the symbol floor** — the key names a declaration the
   graph has no node for: a `let`/`const` binding, a parameter, a
   closure, an interface member signature, a class property holding a
   function, a class reached by `new`. Lane A's record at those sites
   reads *no callee, origin `local`/`nested`* where it has one (C-32,
   C-58, C-9); the `new` sites (cheerio 5, zod 306: 114 on a class,
   107 on an interface-typed constructor value — v4's `$constructor`
   pattern — 85 on a parameter) have no lane A record at all, since the
   helper does not visit `NewExpression`. What the attribution cannot
   settle is named: 5 + 12 sites where two checker records sit at the
   oracle's column and read differently (`__call` sites — the
   `CheerioAPI` call signature — and v4 `.and` / `.describe` chains),
   14 zod lines with no checker record (`~validate` and friends).

Collapsed to one pair per (site path, site line, target file, the
checker's fully qualified target name), by what the key's target *is*
— the overload grain removed and nothing else (H-22 closed; the bare
name had merged 0 pairs on cheerio and 3 on zod):

| target kind | cheerio (hit / pairs) | zod (hit / pairs) |
|---|---|---|
| function declaration | 1,905 / 1,911 (99.7%) → **1,911 / 1,911** at 0.1.7-beta (C-100) | 6,307 / 6,385 (98.8%) |
| method | 41 / 46 | 2,263 / 2,345 (96.5%) |
| variable (a modelled `const` holding a function) | 676 / 676 | 1,161 / 1,625 (71.4%) |
| local binding | 0 / 997 | 0 / 59 |
| closure | 0 / 173 | 0 / 323 |
| interface member signature (`type-member`) | 0 / 6 | 0 / 4,745 |
| class property holding a function (`property`) | — | 0 / 1,029 |
| class, by `new` | 0 / 5 | 0 / 110 |
| anonymous signature (`CheerioAPI.__call`) | 0 / 12 | 0 / 13 |
| **all** | **2,622 / 3,826 = 68.5%** (68.7% at 0.1.7-beta) | **9,731 / 16,634 = 58.5%** |

Where the below-floor rows concentrate — three shapes on each cell:
cheerio's specs bind `let $: CheerioAPI` and assign it in `beforeEach`
(884), or `const $ = load(..)` (176), then call `$(..)`; and the closure
`getLoad` returns / a parameter is called (173 + 69). zod's v4 declares
`parse` / `safeParse` / `optional` / `refine` / `check` / `init` as
*interface* signatures (`interface ZodType { parse(..): .. }`) and
attaches the bodies in `$constructor`'s init closure (`inst.parse =
..`) — 4,742 collapsed pairs, and no declaration anywhere has the body;
v3's `static create = (..) => new ZodString(..)` class properties
(1,029) reached through `const stringType = ZodString.create`; `new
ZodType(..)` / `new ZodError(..)` (110 + 121 — the helper does not
visit `NewExpression`); the `util` namespace's exported members (230).

**Recovered in the 100% tier:** `.mts`/`.cts` were not discovered
(cheerio's six function misses; C-100, lifted 2026-09-10). **Priced for
Max's decision (W1), each a floor change, symbol-grain, no flow needed:**
a class property whose initializer is a function literal as a `method`
symbol (zod 6.2% of pairs); a `namespace` block's exported members as
symbols qualified by the namespace; `new X(..)` as a lane A site — with
the grader-grain question first, since the key names the class whose
constructor answers (`ZodType` for `new ZodString(..)`, the base), not
the class written.

**The Jelly caveat this settles before the afternoon.** The rest of the
tail — bindings, parameters, closures, interface signatures — is where a
flow analysis would answer, and its answer at those sites is a
*different declaration* from the key's: `$(..)` → `initialize` in
`load.ts` where the key says the `$` binding; `schema.parse(..)` → the
closure assigned in `$constructor` where the key says the interface
signature. Graded against this key those edges are contradictions, not
recall. A Jelly cell needs either a key at flow grain (a second
`tsc-oracle` mode that follows a binding to its value) or a grader rule
that a below-floor target is confirmed by the value bound there — the
grain is the decision, and it is not made.

### The 1-1 on repowise's draws (2026-09-09; [cells](cells/), `*-hobbes-2026-09-09.md`)

Five repos repowise-bench pinned, graded by our keys (ADR-101 § the 1-1): cobra (with tests) 2,186/2,186, recall 71.8% at 2 roots; gitleaks with tests 2,266/2,266 at 9 roots (94.9%) and without 2,010/2,010 at 2 roots (98.0%) — after one wrong *syntactic* edge was fixed the same day (`re.MustCompile` inside the repo's own `regexp` package bound to the enclosing function: the fallback matched the stdlib import path to the repo's `regexp/` directory by suffix; `gosource._repo_package` now applies cmd/go's rule that a first path element without a dot is the standard library's); zod 9,731/9,731, recall 45.1% over every resolved site (lane B without dependencies — pnpm is not provisioned, C-23); hono (`tsconfig.build.json`) 767/774, recall 55.2% — the 7 are `static→union-member`. Misses are the standing classes: closures and interface dispatch on Go (cobra `interface→named` 431, gitleaks `func-value→closure` 76 / 17), and on TS the local bindings, closures and the unprovisioned dependencies. syft has no key: RTA over its no-tests program was OOM-killed at 18.7 GB on this box and the with-tests program at 19 GB — H-9's shape; the cell waits on a bigger box.

### The seven-repo loop (2026-08-27; triaged 2026-08-28; [cells](cells/))

Every contradiction in the loop triaged; four fixes landed (two product, two oracle), each cell regraded contained (ADR-092) where it moved:

| cell | edges | precision-vs-oracle | recall | contradicted → after | verdict |
|---|---|---|---|---|---|
| toml (go) | 1,047 | 100% (1,039) | 71.9% at 4 roots | 0 | — |
| fzf (go) | 2,973 → 2,881 | 97.0% → **100%** (2,832) | 40.8% at 5 roots | 87 → 0 | hobbes-wrong: lane A bound a local `assert := func` to a package function — ADR-090's scope veto, now in Go |
| mux (go) | 1,264 | 99.8% → **100%** (1,221) | 82.6% at 1 root | 3 → 0 (abstract 3) | oracle grain: a call through a function-valued `var` (H-18) |
| memchr (rust) | 2,623 → 2,496 | 99.2% → **100%** (921) | 80.7% | 7 → 0 | hobbes-wrong: tuple-struct constructor drawn as `calls` — the O4 conversion rule, now in Rust |
| ajv (ts) | 1,543 → 1,575 | 99.8% → **100%** (1,410) | 62.0% → 63.5% | 3 → 0 | hobbes-wrong by tier: union-member dispatch (`static→union-member`), n=2 with hono — closed by abstention 2026-09-09 (ADR-104, C-97; ten sites now `union-member` in the tail) |
| cheerio (ts) | 2,162 | 97.9% → **100%** (2,102) | 36.1% | 44 → 0 (abstract 44) | oracle grain: calls through `const x = factory(..)` (H-18) |
| click (py, trace) | 2,003 | conf. 81.0% → 84.8%; suspects 85 → 18 (5.0% → 1.0%) | 35.3% → 37.0% | — | oracle grain: `@overload` stubs (H-19); 16 of the 18 left are C-60's asymmetry (override / monkeypatch) |

What hurts most, loop-wide, is unchanged from the first cells: **calls into closures** (fzf 1,212 static + 2,457 inflated; click 1,196 decorator-factory closures; ajv 174) and **interface dispatch** (toml 226, mux 120, fzf 417) — C-58 on every language; Rust's macro face (memchr 99 `macro→*` rows, `unsafe_ifunc!`, `define_*_quickcheck!`). New on the recall side: cheerio's `static→function` 2,507 is dominated by *the oracle's* overload grain (one pair per `attr`/`prop` signature, five each) — the recall-side sibling of H-19, not corrected.


### The four Java cells (O8, 2026-08-29; [cells](cells/))

Java's misses are dominated by one class on every cell, as the build
plan predicted: **`interface→method`**, graded against the CHA override
set, is 84.6–90.9% of all misses (jsoup 5,226 of 5,863; spring-data-elasticsearch
7,469 of 8,214; Severed-Chains 35,289 of 41,717; petclinic 4 of 6).
Per-cell recall on the class: **petclinic 98.7%, jsoup 67.5%,
spring-data-elasticsearch 57.4%, Severed-Chains 0.4%** — the spread is
the codebase's interface layering, and Severed-Chains' 0.4% is the
lane-A-only floor (no semantic lane, so a call on a value resolves to
nothing at all). The declared method *is* drawn and confirmed in every
semantic cell; the overrides below it are the hole.

Second, at 6–8% of misses on the three semantic cells:
**`interface→anonymous-member` / `static→anonymous-member`** (jsoup
452, spring-data-elasticsearch 518, petclinic 0) — overrides and helpers
declared inside anonymous-class and enum-constant bodies, below the
symbol floor by decision (C-9) and named `local-binding` in the tail.
Third, 2.8–6.1%: **`static→constructor`** (recall 84.6–95.6% where lane
B runs), chiefly `new T() {..}`, which Hobbes draws as `uses` of T by
decision (ADR-096). **`static→method` is 0–0.1% on every semantic cell**
(spring-data-elasticsearch: 3,845/3,845, a perfect class on 739 files).

### hobbes `pipeline/` — Python, trace-graded (O6, 2026-08-25; [cell](cells/hobbes-py-2026-08-25.md))

525 honest misses over 3,816 observed in-repo pairs (recall-against-executed 86.2%; 96.9% on named declarations). A trace oracle never inflates — every pair was executed.

| class | misses | share | what it was |
|---|---|---|---|
| `observed→closure` | 348 | 66.3% | nested test helpers and inner functions (`build_units`, `fake_policy_bin`, `symbol_at`'s `look_up`) |
| `observed→function` | 88 | 16.8% | 50 pack `_applies`/`_run` through `Pack` fields, 14 `_cmd_*` through argparse `func`, the rest tables and decorator expressions |
| `observed→lambda` | 76 | 14.5% | lambdas passed as keys, defaults and callbacks |
| `observed→method` | 13 | 2.5% | 6 callable instances (`__call__`), 7 untyped receivers |
| `observed→class` | 0 | — | 307/307 constructors drawn |

**What hurts most:** closures and lambdas, 80.8% — the same answer Go gave (70–80%), now on a dynamic language with an interpreter as the judge.

### rust_proj — Rust, compiler-graded (O7, 2026-08-25; [cell](cells/rust_proj-2026-08-25.md))

4 misses over 21 in-repo pairs (recall 81.0%; 17/17 on `static→function`), all `macro→function`: criterion's `criterion_group!`/`criterion_main!` bodies.

### dagger `sdk/rust` — Rust, compiler-graded (O7, 2026-08-25; [cell](cells/dagger-rust-2026-08-25.md))

69 misses over 3,662 in-repo pairs (recall 98.1%) after H-16 folded `.await`'s poll of async bodies.

| class | misses | share | what it was |
|---|---|---|---|
| `static→method` | 30 | 43.5% | extension-trait methods on foreign types (17), `derive_builder` setters (7), raw-identifier `r#ref` (4), `Deref` (1), an inherent method inside `quote!` tokens (1) |
| `static→generated` | 25 | 36.2% | `.clone()` on derived `Clone` |
| `static→function` | 14 | 20.3% | calls inside `quote!` proc-macro tokens |
| `static→closure` | 0 | — | after H-16 |

**What hurts most on Rust:** not dispatch and not closures — **code a macro or derive wrote** (generated targets 25, proc-macro tokens 15, builder setters 7): 47 of 69. P16's prediction (trait dispatch + closures ≥ 60%) missed; the register says so.

### hobbes repo, `go` — 2026-08-25 (O2, RTA, 20 roots)

1,463 in-repo oracle pairs; 1,280 confirmed; **45 honest misses**,
138 inflated.

| class | hits / pairs | misses | % of honest misses |
|---|---|---|---|
| `static→named` | 1,280 / 1,280 | 0 | 0% |
| `static→closure` | 0 / 37 | 37 | **82.2%** |
| `func-value→named` | 0 / 6 | 6 | 13.3% — one site: `proxy.answer`'s map of the six `Store` methods (`internal/proxy/knowledge.go:141`) |
| `interface→named` | 0 / 2 | 2 | 4.4% — `io.Closer`-style `Close` on the recorder (`cmd/hobbes-web/main_test.go:106,131`) |
| `func-value→closure` (inflated) | 0 / 138 | 138 | — (10 sites; `defer cancel()` and goroutine bodies resolving to every `func()` in the program) |

**What hurts most here: calls into closures**, four-fifths of the
honest misses — and the same mechanism produced the cell's only wrong
edges (lane A binding a local closure name to a package function of
the same name, 3 syntactic contradictions). Interface dispatch, the
pre-registered favourite, is 2 of 45 in this codebase; the Go here is
shaped around concrete types and function tables, not interfaces, so
this ranking is a fact about *this repo* until dagger (O4) says
otherwise.

### kbet, `betchat/frontend` — 2026-08-25 (O3, the zone's `tsc` 5.9.3, resolution oracle)

1,529 in-repo oracle pairs over every resolved site; 633 confirmed;
**896 misses**, none inflated (a resolution oracle names one
declaration per site).

| class | hits / pairs | misses | % of misses |
|---|---|---|---|
| `static→function` | 483 / 484 | 1 | 0.1% |
| `static→variable` | 23 / 23 | 0 | 0% |
| `func-value→variable` | 119 / 121 | 2 | 0.2% — `getAuthStore?.()`, a `let` assigned at runtime (`api/axios.ts:19,30`) |
| `static→class` | 8 / 8 | 0 | 0% |
| `func-value→local-binding` | 0 / 625 | 625 | **69.8%** — `useState` setters and callbacks held in locals |
| `static→closure` | 0 / 195 | 195 | **21.8%** — handlers declared inside components (`handleAction`, `renderCompose`) |
| `interface→type-member` | 0 / 71 | 71 | 7.9% — store members through their interface (`ChatState.addMessage`, `WalletState.fetchBalance`) |
| `static→anonymous-function` | 0 / 1 | 1 | 0.1% — an IIFE (`test/setup.ts:4`) |
| `static→type-member` | 0 / 1 | 1 | 0.1% |

**What hurts most here: local bindings**, seven-tenths — and most of
those are React state setters, which no reader would want as call
edges; they are the tail C-32 already names as *by design*. The class
that actually loses architecture is the **store members through
interfaces** (71): `who_calls(addMessage)` answers nobody for the
zone's central state mutations. Closures (195) are the same story as
Go's. Everything Hobbes *declares* a symbol for it also draws: 633 of
637.

### dagger, 19 Go modules — 2026-08-25 (O4, RTA, 24 roots across the cells)

Per-cell rows in `oracle/cells/dagger-go-2026-08-25.md`; the sums
below are sizes, not a pooled rate. 10,715 in-repo oracle pairs; 9,855
drawn; **819 honest misses**, 41 inflated.

| class | hits / pairs | misses | % of honest misses |
|---|---|---|---|
| `static→named` | 9,854 / 9,889 | 35 | 4.3% — 16 recursion (**C-59**), 11 method expressions / generic instantiation calls, 4 chain continuations (no site at all), 4 calls on an assignment's left side (drawn as `uses`) |
| `static→closure` | 0 / 577 | 577 | **70.5%** |
| `interface→named` | 0 / 192 | 192 | **23.4%** — dagger modules dispatch through interfaces far more than this repo does |
| `func-value→named` | 0 / 16 | 16 | 2.0% |
| `func-value→closure` (inflated) | 1 / 41 | 40 | — |

**What hurts most here:** closures again, seven-tenths — but interface
dispatch is now a real second at 23%, where in this repo it was 4%:
the ranking moves with the codebase's style, which is why the record
is per cell. **What is new:** the four *named* shapes above are not
C-58 — they are direct calls Hobbes should draw and does not, and one
of them (chain continuations) is invisible to the capture number too.
*(Fixed the same day.)* **After the fixes (re-ingested, same 19
modules, same roots): `static→named` 9,889 / 9,889 — 0 misses;
contradictions 0. The honest misses are now exactly the C-58 classes:
577 closures (70%), 192 interface dispatches (23%), 16 function-table
calls (2%), 40 inflated `func()` pairs.**
And the cells' 40 contradictions are all one product defect, **a type
conversion drawn as a call**, which is a lie rather than a silence.

**Better classification wanted (open):** `static→closure` conflates a
closure called in the function that made it (the test helper shape)
with one stored and called later; `func-value→local-binding` conflates
a React state setter (never wanted as an edge) with a callback whose
provenance a reader *would* want; and `func-value→named` at one site
with six candidates is a *table dispatch* the oracle counts as six
misses when Hobbes would need one `dispatch` edge to a table. Both
sub-classes need a marker the oracle does not carry yet (whether the
callee value was defined in the caller; whether the value came from a
composite literal). Add when a cell makes them matter.
