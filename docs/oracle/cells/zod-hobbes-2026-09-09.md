# Oracle cell — zod (zod), module `.`, 2026-09-09 (a draw of repowise's, ADR-101 § the 1-1)

**Hobbes on a repo another tool's benchmark drew.** Repo: https://github.com/colinhacks/zod, clone `/home/mmarrujo/.hobbes/bench/comparative/repos/zod`, commit bbc68f990c7e6a5e3f506c56fb04bd0279b9c9b5 — the commit repowise-bench's `graph/corpus/corpus.lock` pins for its G4 experiment; the answer key is ours (`/home/mmarrujo/.hobbes/bench/comparative/keys/zod/oracle.json`: `oracle tsc 5.9.3 (harness) (resolution), roots 0, 366 files, 34548 sites`), built by `oracle go-rta` / `ts/tsc-oracle.mjs` on this box, so this cell is 1-1 with the foreign cells beside it (`codegraphcontext-zod`, `repowise-zod`) and **not** with repowise-bench's own numbers, whose key is at function grain (caller declaration → callee declaration) and whose matcher is theirs. Ingest: contained, `HOBBES_SCIP=1 uv run hobbes ingest`; capture: capture [ts/js]: 48.7% of 33763 detected call sites accounted; 17 degradation record(s) in the ingest log (quoted in the artifact directory's ingest.log copy)

Command: `oracle export --graph <clone>/.hobbes/derived/graph.json --module . --lang <lang> --out hobbes.json && oracle grade --hobbes hobbes.json --oracle zod/oracle.json --json report.json --poison`. Outputs in `/home/mmarrujo/.hobbes/bench/comparative/hobbes-zod`.

## Numbers (report.txt, head, verbatim)

```
cell .  oracle tsc 5.9.3 (harness) (resolution)  sha bbc68f99
hobbes edges 9780: confirmed 9731  contradicted 0  abstract 0  silent 49 map[not-loaded:49]
precision-against-oracle 100.0% (9731/9731)
recall 45.1% (9893/21931 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 3239; misses map[func-value→local-binding:59 func-value→variable:226 interface→type-member:88 static→anonymous-signature:13 static→class:110 static→closure:324 static→function:4220 static→method:531 static→property:1274 static→type-member:4955 static→variable:238]
  recall[func-value→local-binding]   0.0% (0/59)  misses 59 = 0.5% of all misses
  recall[func-value→variable]  80.2% (917/1143)  misses 226 = 1.9% of all misses
  recall[interface→type-member]   0.0% (0/88)  misses 88 = 0.7% of all misses
  recall[static→anonymous-signature]   0.0% (0/13)  misses 13 = 0.1% of all misses
  recall[static→class      ]   0.0% (0/110)  misses 110 = 0.9% of all misses
  recall[static→closure    ]   0.0% (0/324)  misses 324 = 2.7% of all misses
  recall[static→function   ]  60.5% (6455/10675)  misses 4220 = 35.1% of all misses
  recall[static→method     ]  81.1% (2275/2806)  misses 531 = 4.4% of all misses
  recall[static→property   ]   0.0% (0/1274)  misses 1274 = 10.6% of all misses
  recall[static→type-member]   0.0% (0/4955)  misses 4955 = 41.2% of all misses
  recall[static→variable   ]  50.8% (246/484)  misses 238 = 2.0% of all misses
  tier semantic   confirmed 8674  contradicted 0  abstract 0  silent 38
  tier syntactic  confirmed 1057  contradicted 0  abstract 0  silent 11
  line-grain tolerance used on 5642 edge(s) (several oracle sites on one line)
poison check: PASS — 9780 seeded wrong edges: 9731 refused, 49 unjudged (oracle silent there), 0 falsely confirmed
```

| bucket | count |
|---|---|
| graded edges | 9,780 |
| confirmed | 9,731 |
| contradicted | 0 |
| abstract | 0 |
| silent | 49 {"not-loaded": 49} |
| precision-against-oracle (lower bound) | **100.0%** (9,731/9,731) |
| recall | 45.1% (9,893/21,931) over every resolved site |

**By tier:** `semantic` confirmed 8674 / contradicted 0 / abstract 0 / silent 38; `syntactic` confirmed 1057 / contradicted 0 / abstract 0 / silent 11.

**Triage (hand-read, 2026-09-09):** 0 contradicted; nothing to read. Recall is bounded by the ingest: zod's pnpm workspace is not provisioned (C-23), so lane B indexed without dependencies and the capture line says 48.7%.

## Misses by class

| class | hits / pairs | misses |
|---|---|---|
| `static→type-member` | 0 / 4,955 | 4,955 |
| `static→function` | 6,455 / 10,675 | 4,220 |
| `static→property` | 0 / 1,274 | 1,274 |
| `static→method` | 2,275 / 2,806 | 531 |
| `static→closure` | 0 / 324 | 324 |
| `static→variable` | 246 / 484 | 238 |
| `func-value→variable` | 917 / 1,143 | 226 |
| `static→class` | 0 / 110 | 110 |
| `interface→type-member` | 0 / 88 | 88 |
| `func-value→local-binding` | 0 / 59 | 59 |
| `static→anonymous-signature` | 0 / 13 | 13 |

**Poison check:** PASS — 9,780 seeded wrong edges: 9,731 refused, 49 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix:** first grade — nothing to sign. **Not a comparison with repowise-bench's table:** a different key grain and matcher; the comparison is with the foreign cells on this key.


## Regrade 2026-09-10 (0.1.6-beta; the callee-shape bucket — Max's indexer question)

Re-ingested contained at 0.1.6-beta and regraded against the same key (`~/.hobbes/bench/comparative/hobbes-zod-r2/`): **byte-identical to the 2026-09-09 grade** — 9,780 edges, 9,731 confirmed, 0 contradicted, 49 silent, recall 45.1% (9,893/21,931), poison PASS. (0.1.7-beta does not move it: no `.mts`/`.cts` file in the program.)

**The bucket** (`bench/oracle/shape/`; the reading in `docs/oracle/oracle-misses.md`), 12,038 misses:

| bucket | rows | share | what it is |
|---|---|---|---|
| oracle grain — Hobbes' edge confirmed to a sibling declaration of the same name on the same line | 4,442 | 36.9% | one pair per overload signature (`string` ×2, `toJSONSchema`, `literal`; 347 of them methods) |
| member on a call result (`z.string().optional()`, `schema.parse(..)`) | 2,552 | 21.2% | 1,940 are v4's *interface* method signatures (`parse`, `safeParse`, `optional`, `refine` in `interface ZodType` — the body is attached in `$constructor`'s init closure, no declaration has one; C-9), 528 v3's `static create = (..) =>` class properties |
| member on a nested / top-level `const` holding a call result (`const s = z.object(..); s.parse(..)`) | 2,344 | 19.5% | the same interface signatures (2,310 `type-member`) |
| member on a namespace import (`z.string()`, `util.assertEqual(..)`) | 1,185 | 9.8% | v3 `static create` properties reached through `const stringType = ZodString.create` (not a modelled const); the `util` namespace's exported members (230 — `export namespace util { export const assertEqual .. }`, not modelled) |
| no lane A site on the line | 311 | 2.6% | `new ZodType(..)` / `new ZodError(..)` — the helper does not visit `NewExpression` (97 class targets + 121 `$constructor` variables), and 84 closures |
| member on a property chain / an interface-typed identifier / a parameter / `this` | 696 | 5.8% | `inst._zod.init(..)`, `def.check(..)`, `ctx.addIssue(..)` — interface signatures and params, below the floor |
| identifier → a function declaration / a nested `const` function / a param / a binding element | 297 | 2.5% | closures and locals (`processError`, `getter`, `localeError`); 25 locale `export default function`s |
| the rest | 211 | 1.8% | `NonNullExpression` receivers, `parseUtil.OK` type-alias-named variables, anonymous signatures |

Collapsed to one pair per (site line, target file, target name): 16,631 pairs, 9,731 hit, **58.5%** — by target kind: function 6,307/6,385 (98.8%), method 2,263/2,345 (96.5%), variable 1,161/1,625 (71.4%), type-member 0/4,742, property 0/1,029, closure 0/323, class 0/110, local-binding 0/59, anonymous-signature 0/13.

**Direction of fix:** the 4,442 sibling rows — oracle (grain). The type-member 4,742 — below the floor by C-9 and not a body anywhere (a flow analysis would name the closure assigned in `$constructor`, which is *not* the key's target). Three floor shapes are recoverable at symbol grain and priced in W1 for Max's decision: class-property functions (1,029 collapsed pairs, 6.2% of the cell), namespace members (230 rows), `new X(..)` as a site (~230 rows, with the grader-grain question first). Nothing on the cell is a resolution the compiler saw and the indexer withheld.
