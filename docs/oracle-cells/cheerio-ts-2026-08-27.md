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
