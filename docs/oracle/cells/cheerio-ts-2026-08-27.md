# Oracle cell — cheeriojs/cheerio, zone `.`, 2026-08-27

Repo: https://github.com/cheeriojs/cheerio (MIT), clone at `~/.hobbes/bench/oracle/repos/cheerio`, commit 98c7d13131c73163aab022e37d22ccd37f605b2c (fixed for this cell). Picked because it is a well-known, mid-popularity TS library (~13k lines of `src/` TypeScript incl. its vitest specs) under one root `tsconfig.json` (the `website/` zone is excluded by that tsconfig and has its own), with `node_modules` already installed so lane B indexes under the project's own compiler. Ingest SHA 98c7d131 (the ingest reports a dirty tree: `hobbes ingest` appends `.hobbes/` to the clone's `.gitignore`, ADR-012 — nothing else changed). Hobbes at 0197636, edges from `.hobbes/derived/graph.json` (lane B on, `HOBBES_SCIP=1`). Ingest warnings, verbatim in spirit: the root zone's scip-resolve was degraded (12 of 34 declared dependencies resolved — third-party edges absent rather than nonexistent) and the `website` zone's scip-typescript failed (`astro/tsconfigs/strict` not found) and fell to lane A's syntactic tier; `website` is outside the graded zone. Oracle = the zone's own `tsc` 6.0.3 (`node_modules/typescript`), a resolution oracle (no roots): 36 files, 9,005 call sites (2,610 static, 6,395 dynamic). Computed-key silent sites in `oracle.json`: 0 (`grep -o '"computed-key"' oracle.json | wc -l`). The H-17 TS oracle hang did not recur.

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/cheerio . ~/.hobbes/bench/oracle/cheerio-ts --lang ts`. Runtime 8 s as printed by the driver (ingest + tsc oracle + grade). Outputs in `~/.hobbes/bench/oracle/cheerio-ts/` (`hobbes.json`, `oracle.json`, `report.json`, `report.txt`; the log at `~/.hobbes/bench/oracle/cheerio-ts.log`).

## Numbers (report.txt, verbatim; the 44 contradicted and 3,778 missed rows are in the file)

```
cell .  oracle tsc 6.0.3 (the zone's own) (resolution)  sha 98c7d131
hobbes edges 2162: confirmed 2102  contradicted 44  abstract 0  silent 16 map[not-loaded:16]
precision-against-oracle 97.9% (2102/2146)
recall 36.1% (2132/5910 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 5180; misses map[func-value→local-binding:1070 static→anonymous-signature:12 static→class:5 static→closure:173 static→function:2507 static→method:5 static→type-member:6]
  recall[func-value→local-binding]   0.0% (0/1070)  misses 1070 = 28.3% of all misses
  recall[func-value→variable] 100.0% (684/684)  misses 0 = 0.0% of all misses
  recall[static→anonymous-signature]   0.0% (0/12)  misses 12 = 0.3% of all misses
  recall[static→class      ]   0.0% (0/5)  misses 5 = 0.1% of all misses
  recall[static→closure    ]   0.0% (0/173)  misses 173 = 4.6% of all misses
  recall[static→function   ]  35.9% (1407/3914)  misses 2507 = 66.4% of all misses
  recall[static→method     ]  89.1% (41/46)  misses 5 = 0.1% of all misses
  recall[static→type-member]   0.0% (0/6)  misses 6 = 0.2% of all misses
  tier semantic   confirmed 2094  contradicted 44  abstract 0  silent 0
  tier syntactic  confirmed 8  contradicted 0  abstract 0  silent 16
  line-grain tolerance used on 1474 edge(s) (several oracle sites on one line)
poison check: PASS — 2162 seeded wrong edges: 2146 refused, 16 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/cheerio: 8s
```

| bucket | count |
|---|---|
| hobbes edges | 2162 |
| confirmed | 2102 |
| contradicted | 44 |
| silent (`not-loaded`) | 16 |
| precision-against-oracle (lower bound, A-8) | 97.9% (2102/2146) |
| in-repo oracle pairs | 5910 |
| recall over every resolved site (no roots) | 36.1% (2132/5910) |
| external oracle pairs (not graded) | 5180 |
| tiers | semantic 2094 / 44 / 0; syntactic 8 / 0 / 16 |
| computed-key silent sites (oracle.json) | 0 |

triage ratio (contradicted rows) oracle-wrong : hobbes-wrong : untriaged = 0 : 0 : 44

## Contradicted (44 rows, untriaged)

Two shapes, both in `report.txt`:

- **36 rows in `src/parse.spec.ts`** (lines 64–433): Hobbes resolves `parse(...)` to `src/parse.spec.ts:9` (the spec's own `const parse = getParse(...)` binding); the oracle names `src/parse.ts:33 (parse)`.
- **8 rows in `src/api/traversing.ts`** (lines 242–594): Hobbes resolves the site to `src/api/traversing.ts:147 (_matcher)` / `:152 (_singleMatcher)`; the oracle names `src/api/traversing.ts:118 ((Anonymous function))` — the function returned by `_getMatcher` — and, on two rows, additionally `domutils` `nextElementSibling` / `prevElementSibling` in `node_modules`.

Not triaged in this cell; recorded as untriaged per the ratio line above.

## Misses by class (3,778 rows)

- **static→function, 2,507 (66.4%).** Direct calls to a named function, recall 35.9% (1407/3914). 2,327 of the 2,507 sites are in `*.spec.ts` files: `src/api/attributes.spec.ts` 1,410, `src/api/manipulation.spec.ts` 282, `src/api/traversing.spec.ts` 188, `src/api/css.spec.ts` 128, `src/cheerio.spec.ts` 117, `src/static.spec.ts` 84. The dominant targets are the overload signatures of `src/api/attributes.ts` `attr` (lines 123/142/163/188/192, 99 sites each — one oracle pair per overload declaration) and `prop` (`attributes.ts:415`, 84). Non-spec sites: `src/api/attributes.ts` 63, `benchmark/benchmark.ts` 57, `src/api/forms.ts` 14, `src/api/extract.ts` 13, `src/api/traversing.ts` 12.
- **func-value→local-binding, 1,070 (28.3%).** Calls through a locally bound function value, 0/1070. Almost entirely the specs' `let $: CheerioAPI` / `$elem` bindings: `src/api/manipulation.spec.ts` 461 (target `manipulation.spec.ts:12 $`, 393), `src/api/traversing.spec.ts` 282 (`traversing.spec.ts:24 $`, 244), `src/api/attributes.spec.ts` 235, `src/api/forms.spec.ts` 20, `src/cheerio.spec.ts` 18, `src/static.spec.ts` 13.
- **static→closure, 173 (4.6%).** Direct calls of a locally bound closure, 0/173: `benchmark/benchmark.ts` 40, `src/parse.spec.ts` 36, `src/cheerio.spec.ts` 23, `src/static.spec.ts` 17, `src/index.spec.ts` 14, `src/api/traversing.ts` 14. Targets: `src/load.ts:136 load` (55 — the closure `getLoad` returns), `src/parse.ts:33 parse` (36), `src/api/traversing.ts:118 (Anonymous function)` (9), `src/index.spec.ts:120 createTestServer` (7).
- **static→anonymous-signature, 12 (0.3%).** Calls resolved by the oracle to `src/load.ts:69 (CheerioAPI.__call)`, the interface's call signature, from `src/api/attributes.spec.ts` and `src/api/traversing.spec.ts`.
- **static→type-member, 6 (0.2%).** `src/cheerio.spec.ts:9 ("./index.js".Cheerio.myPlugin)` 4 (a module-augmentation member), `benchmark/benchmark.ts:27 (__type.test)` 2.
- **static→method, 5 (0.1%)** and **static→class, 5 (0.1%).** All in `src/load.ts` (lines 146–169): `Cheerio._parse` at `src/cheerio.ts:99` and `new Cheerio` at `src/cheerio.ts:37`, recall 89.1% (41/46) and 0/5 respectively.
- **func-value→variable, 0 misses** (684/684).

**Poison check:** PASS — 2162 seeded wrong edges: 2146 refused, 16 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix (which side would need to change; no proposals):** `static→function` — untriaged as to side: the oracle emits one pair per overload declaration of `attr`/`prop` (five for `attr`), so part of the count is the oracle's grain and the residue is Hobbes; the non-spec sites are Hobbes. `func-value→local-binding` — Hobbes (a local binding to a function value, C-58's local-binding tail; the oracle's targets are the bindings themselves). `static→closure` — Hobbes (a direct call to a locally bound closure is statically resolvable; Hobbes has no callee). `static→anonymous-signature` and `static→type-member` — Hobbes (the oracle names a declaration Hobbes has no node for). `static→method` / `static→class` — Hobbes. Contradicted 44 — untriaged, side undetermined (both shapes are a Hobbes-callee-vs-oracle-callee disagreement on the same file). Silent 16 (`not-loaded`) — nothing to fix on either side.

**Not graded:** the 5,180 external oracle pairs (`node_modules` / lib.d.ts callees, by design); the 16 `not-loaded` silent edges (syntactic-tier edges in files the oracle's program did not load); the `website/` zone (excluded by the root tsconfig, its own zone, lane B degraded there). No repo was abandoned.

## Regrade 2026-08-28 (triage; D-O4's function-valued-binding bullet, H-18)

Both shapes are one class: a call through a module `const` holding a function (`const parse = getParse(..)` in the spec; `_matcher` / `_singleMatcher = _getMatcher(..)`). Hobbes names the binding, `tsc` the signature the value carries. Graded **abstract** (`func-value`) since H-18. Re-ingested contained and regraded, 8 s:

```
hobbes edges 2162: confirmed 2102  contradicted 0  abstract 44  silent 16 map[not-loaded:16]
precision-against-oracle 100.0% (2102/2102)
recall 36.1% (2132/5910 in-repo oracle pairs)
  tier semantic   confirmed 2094  contradicted 0  abstract 44  silent 0
  tier syntactic  confirmed 8  contradicted 0  abstract 0  silent 16
```

**Triage ratio (A-8):** 44 contradicted → `oracle-wrong 44 : hobbes-wrong 0 : untriaged 0` (grain, RC-3). **Direction of fix:** oracle. The recall misses stand as recorded: `static→function` 2,507 is mostly the specs' `attr`/`prop` overload signatures (one oracle pair per overload declaration — the oracle's grain again, on the recall side, not corrected here) and `func-value→local-binding` 1,070 the specs' `$` bindings (C-32).

## Regrade 2026-09-10 (0.1.6-beta, then 0.1.7-beta; the callee-shape bucket — Max's indexer question; C-100)

Re-ingested contained at 0.1.6-beta (the fixes since 2026-08-28: C-80's expression receivers, ADR-104, C-98/C-99) and regraded against the same key, 8 s (`~/.hobbes/bench/oracle/cheerio-ts-r3/`):

```
hobbes edges 2682: confirmed 2622  contradicted 0  abstract 44  silent 16 map[not-loaded:16]
precision-against-oracle 100.0% (2622/2622)
recall 45.0% (2661/5910 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 5180; misses map[func-value→local-binding:1070 static→anonymous-signature:12 static→class:5 static→closure:173 static→function:1978 static→method:5 static→type-member:6]
  recall[static→function   ]  49.5% (1936/3914)  misses 1978 = 60.9% of all misses
  tier semantic   confirmed 2614  contradicted 0  abstract 44  silent 0
  tier syntactic  confirmed 8  contradicted 0  abstract 0  silent 16
poison check: PASS — 2682 seeded wrong edges: 2666 refused, 16 unjudged (oracle silent there), 0 falsely confirmed
```

**The bucket** (`bench/oracle/shape/`: every miss joined to the checker's reading of the callee expression at its site and to lane A's own record there; the full table and the reading in `docs/oracle/oracle-misses.md`), 3,249 misses:

| bucket | rows | share | what it is |
|---|---|---|---|
| oracle grain — Hobbes' edge confirmed to a *sibling declaration* of the same name on the same line | 1,972 | 60.7% | one oracle pair per overload signature (`attr` ×5, `prop`, `html`); H-19's recall side |
| identifier → `let` binding, no initializer (`let $: CheerioAPI`, assigned in `beforeEach`) | 884 | 27.2% | below the floor by C-32; lane A: no callee, origin `local` |
| identifier → nested `const` holding a call result (`const $ = load(..)`) | 176 | 5.4% | same |
| identifier → a parameter (`fn(..)`, `cb(..)`, `$` as a param) | 69 | 2.1% | same; 5 of them the `parse` param typed `typeof Cheerio.prototype._parse` (`static→method`) |
| member on a top-level `const` holding a call result / identifier → such a const (`cheerio.load(..)`, `parse(..)` = `getParse(..)`) | 95 | 2.9% | the closure `getLoad` returns; H-18's shape |
| identifier → a function declaration **in `scripts/fetch-sponsors.mts`** | 6 | 0.2% | **no lane A record at all — the file was not discovered (C-100)** |
| the rest (call-result callees → `CheerioAPI.__call`, `new LoadedCheerio` with no lane A site, `myPlugin` on a module augmentation, a `this` callee) | 47 | 1.4% | below the floor / not a site |

Collapsed to one pair per (site line, target file, target name): 3,826 pairs, 2,622 hit, **68.5%** — by target kind: function 1,905/1,911 (99.7%; the six are the `.mts` file), method 41/46, variable 676/676, local-binding 0/997, closure 0/173, anonymous-signature 0/12, type-member 0/6, class 0/5.

**Then at 0.1.7-beta** (C-100 lifted — `.mts`/`.cts` discovered), re-ingested contained and regraded, 10 s (`~/.hobbes/bench/oracle/cheerio-ts-r4/`):

```
cell .  oracle tsc 6.0.3 (the zone's own) (resolution)  sha 98c7d131
hobbes edges 2688: confirmed 2628  contradicted 0  abstract 44  silent 16 map[not-loaded:16]
precision-against-oracle 100.0% (2628/2628)
recall 45.1% (2667/5910 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 5180; misses map[func-value→local-binding:1070 static→anonymous-signature:12 static→class:5 static→closure:173 static→function:1972 static→method:5 static→type-member:6]
  recall[func-value→local-binding]   0.0% (0/1070)  misses 1070 = 33.0% of all misses
  recall[func-value→variable] 100.0% (684/684)  misses 0 = 0.0% of all misses
  recall[static→anonymous-signature]   0.0% (0/12)  misses 12 = 0.4% of all misses
  recall[static→class      ]   0.0% (0/5)  misses 5 = 0.2% of all misses
  recall[static→closure    ]   0.0% (0/173)  misses 173 = 5.3% of all misses
  recall[static→function   ]  49.6% (1942/3914)  misses 1972 = 60.8% of all misses
  recall[static→method     ]  89.1% (41/46)  misses 5 = 0.2% of all misses
  recall[static→type-member]   0.0% (0/6)  misses 6 = 0.2% of all misses
  tier semantic   confirmed 2620  contradicted 0  abstract 44  silent 0
  tier syntactic  confirmed 8  contradicted 0  abstract 0  silent 16
  line-grain tolerance used on 1887 edge(s) (several oracle sites on one line)
poison check: PASS — 2688 seeded wrong edges: 2672 refused, 16 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/cheerio: 10s
```

The six `.mts` rows recovered at the semantic tier; collapsed 2,628/3,826 = **68.7%**, function targets **1,911/1,911**. **Triage ratio (A-8):** 0 contradicted. **Direction of fix:** the 1,972 sibling rows — oracle (grain); the 1,190 below-floor targets — a floor decision, not a resolution failure (Max's call; W1); nothing else on the cell.

## Regrade 2026-09-10 (later still; Hobbes 0.1.8-beta — the versioned baseline: same clone, the 2026-08-27 key, contained)

Every Hobbes cell was re-ingested on one build and regraded against its standing key so the comparative graphics carry one version (Max, 2026-09-10; ADR-103). Artifacts `~/.hobbes/bench/v018/cheerio-ts/`; unchanged to the digit from the standing grade.

```
cell .  oracle tsc 6.0.3 (the zone's own) (resolution)  sha 98c7d131
hobbes edges 2688: confirmed 2628  contradicted 0  abstract 44  silent 16 map[not-loaded:16]
precision-against-oracle 100.0% (2628/2628)
recall 45.1% (2667/5910 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 5180; misses map[func-value→local-binding:1070 static→anonymous-signature:12 static→class:5 static→closure:173 static→function:1972 static→method:5 static→type-member:6]
  recall[func-value→local-binding]   0.0% (0/1070)  misses 1070 = 33.0% of all misses
  recall[func-value→variable] 100.0% (684/684)  misses 0 = 0.0% of all misses
  recall[static→anonymous-signature]   0.0% (0/12)  misses 12 = 0.4% of all misses
  recall[static→class      ]   0.0% (0/5)  misses 5 = 0.2% of all misses
  recall[static→closure    ]   0.0% (0/173)  misses 173 = 5.3% of all misses
  recall[static→function   ]  49.6% (1942/3914)  misses 1972 = 60.8% of all misses
  recall[static→method     ]  89.1% (41/46)  misses 5 = 0.2% of all misses
  recall[static→type-member]   0.0% (0/6)  misses 6 = 0.2% of all misses
  tier semantic   confirmed 2620  contradicted 0  abstract 44  silent 0
  tier syntactic  confirmed 8  contradicted 0  abstract 0  silent 16
  line-grain tolerance used on 1887 edge(s) (several oracle sites on one line)
poison check: PASS — 2688 seeded wrong edges: 2672 refused, 16 unjudged (oracle silent there), 0 falsely confirmed
```

**The bucket under canonical identity (2026-09-10, later still; H-22, [the review](../../reviews/2026-09-10-baseline.md)).** `bucket.py` re-done — a pair is the site line and the checker's *fully qualified* target name (overload signatures share one; two same-named methods do not), a confirmed row hits the target at its exact position (the grader's rule), a miss takes the checker record at the oracle's column and is otherwise an explicit `ambiguous` / `no record` row, `new X(..)` is a record — and re-run on this 0.1.8-beta grade with shapes and facts regenerated from the clone (`bench/oracle/shape/`, no spend): **3,826 pairs, 2,628 hit, 68.7% — unchanged to the pair** (the bare name had merged none); function 1,911/1,911, variable 676/676, method 41/46, local-binding 0/997, closure 0/173, anonymous-signature 0/12, type-member 0/6, class 0/5. Attribution of the 3,243 misses: 1,972 sibling (same qualified name confirmed at another line), 1,266 at the column, 0 by name, 5 ambiguous (four `CheerioAPI.__call` sites in `traversing.spec.ts` where two records sit at the column, one closure), 0 with no record; 0 confirmed rows unexplained. The five `new Cheerio(..)` sites in `load.ts` that read "no lane A site" before are `new:class` now (lane A has no record: the helper does not visit `NewExpression`). The table above stands.

**The grader's line (2026-09-10, later still; Max's decision, ADR-089 amended).** `oracle grade` on these same artifacts — the 0.1.8-beta export against the 2026-08-27 key — prints beside the standing recall line `recall-collapsed 68.7% (2628/3826 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)`: the bucket's number above from a second program (`bucket.py` reports the two agree). The standing grade is unchanged.


## Regrade 2026-09-10 (later still; Hobbes 0.1.10-beta — every cell on one build again: same clone, the 2026-08-27 key, contained)

Every Hobbes cell was re-ingested on 0.1.10-beta and regraded against its standing key so the comparative graphics state one version (Max, 2026-09-10; ADR-103, third amendment). Artifacts `~/.hobbes/bench/v0110/cheerio-ts/`; **unchanged to the digit from the 0.1.8-beta grade**; the one new line is the grader's `recall-collapsed` (ADR-089 amended).

```
cell .  oracle tsc 6.0.3 (the zone's own) (resolution)  sha 98c7d131
hobbes edges 2688: confirmed 2628  contradicted 0  abstract 44  silent 16 map[not-loaded:16]
precision-against-oracle 100.0% (2628/2628)
recall 45.1% (2667/5910 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 5180; misses map[func-value→local-binding:1070 static→anonymous-signature:12 static→class:5 static→closure:173 static→function:1972 static→method:5 static→type-member:6]
recall-collapsed 68.7% (2628/3826 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)
  recall[func-value→local-binding]   0.0% (0/1070)  misses 1070 = 33.0% of all misses
  recall[func-value→variable] 100.0% (684/684)  misses 0 = 0.0% of all misses
  recall[static→anonymous-signature]   0.0% (0/12)  misses 12 = 0.4% of all misses
  recall[static→class      ]   0.0% (0/5)  misses 5 = 0.2% of all misses
  recall[static→closure    ]   0.0% (0/173)  misses 173 = 5.3% of all misses
  recall[static→function   ]  49.6% (1942/3914)  misses 1972 = 60.8% of all misses
  recall[static→method     ]  89.1% (41/46)  misses 5 = 0.2% of all misses
  recall[static→type-member]   0.0% (0/6)  misses 6 = 0.2% of all misses
  tier semantic   confirmed 2620  contradicted 0  abstract 44  silent 0
  tier syntactic  confirmed 8  contradicted 0  abstract 0  silent 16
  line-grain tolerance used on 1887 edge(s) (several oracle sites on one line)
poison check: PASS — 2688 seeded wrong edges: 2672 refused, 16 unjudged (oracle silent there), 0 falsely confirmed
```
