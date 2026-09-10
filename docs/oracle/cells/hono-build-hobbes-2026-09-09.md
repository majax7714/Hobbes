# Oracle cell — hono (hono-build), module `.`, 2026-09-09 (a draw of repowise's, ADR-101 § the 1-1)

**Hobbes on a repo another tool's benchmark drew.** Repo: https://github.com/honojs/hono, clone `/home/mmarrujo/.hobbes/bench/comparative/repos/hono`, commit 97c6fe1f12298c715eb7b2da65b4b6e0d81682bb — the commit repowise-bench's `graph/corpus/corpus.lock` pins for its G4 experiment; the answer key is ours (`/home/mmarrujo/.hobbes/bench/comparative/keys/hono-build/oracle.json`: `oracle tsc 5.9.3 (harness) (resolution), roots 0, 185 files, 3199 sites`), built by `oracle go-rta` / `ts/tsc-oracle.mjs` on this box, so this cell is 1-1 with the foreign cells beside it (`codegraphcontext-hono-build`, `repowise-hono-build`) and **not** with repowise-bench's own numbers, whose key is at function grain (caller declaration → callee declaration) and whose matcher is theirs. Ingest: contained, `HOBBES_SCIP=1 uv run hobbes ingest`; capture: capture [ts/js]: 39.7% of 35239 detected call sites accounted; 28 degradation record(s) in the ingest log (quoted in the artifact directory's ingest.log copy)

Command: `oracle export --graph <clone>/.hobbes/derived/graph.json --module . --lang <lang> --out hobbes.json && oracle grade --hobbes hobbes.json --oracle hono-build/oracle.json --json report.json --poison`. Outputs in `/home/mmarrujo/.hobbes/bench/comparative/hobbes-hono-build`.

## Numbers (report.txt, head, verbatim)

```
cell .  oracle tsc 5.9.3 (harness) (resolution)  sha 97c6fe1f
hobbes edges 4474: confirmed 767  contradicted 7  abstract 0  silent 3700 map[not-loaded:3700]
precision-against-oracle 99.1% (767/774)
recall 55.2% (774/1403 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 2122; misses map[func-value→local-binding:61 func-value→variable:4 interface→type-member:30 static→anonymous-function:1 static→anonymous-signature:15 static→class:78 static→closure:229 static→method:91 static→property:93 static→type-member:20 static→variable:7]
  recall[func-value→local-binding]   0.0% (0/61)  misses 61 = 9.7% of all misses
  recall[func-value→variable]   0.0% (0/4)  misses 4 = 0.6% of all misses
  recall[interface→type-member]   0.0% (0/30)  misses 30 = 4.8% of all misses
  recall[static→anonymous-function]   0.0% (0/1)  misses 1 = 0.2% of all misses
  recall[static→anonymous-signature]   0.0% (0/15)  misses 15 = 2.4% of all misses
  recall[static→class      ]   0.0% (0/78)  misses 78 = 12.4% of all misses
  recall[static→closure    ]   0.0% (0/229)  misses 229 = 36.4% of all misses
  recall[static→function   ] 100.0% (64/64)  misses 0 = 0.0% of all misses
  recall[static→method     ]  55.4% (113/204)  misses 91 = 14.5% of all misses
  recall[static→property   ]   0.0% (0/93)  misses 93 = 14.8% of all misses
  recall[static→type-member]   0.0% (0/20)  misses 20 = 3.2% of all misses
  recall[static→variable   ]  98.8% (597/604)  misses 7 = 1.1% of all misses
  tier semantic   confirmed 726  contradicted 7  abstract 0  silent 3587
  tier syntactic  confirmed 41  contradicted 0  abstract 0  silent 113
  line-grain tolerance used on 166 edge(s) (several oracle sites on one line)
poison check: PASS — 4474 seeded wrong edges: 774 refused, 3700 unjudged (oracle silent there), 0 falsely confirmed
```

| bucket | count |
|---|---|
| graded edges | 4,474 |
| confirmed | 767 |
| contradicted | 7 |
| abstract | 0 |
| silent | 3,700 {"not-loaded": 3700} |
| precision-against-oracle (lower bound) | **99.1%** (767/774) |
| recall | 55.2% (774/1,403) over every resolved site |

**By tier:** `semantic` confirmed 726 / contradicted 7 / abstract 0 / silent 3587; `syntactic` confirmed 41 / contradicted 0 / abstract 0 / silent 113.

## Contradicted (7 rows; all in report.json)

Mechanical shape (no reading): another file than every oracle target 7. By label: `semantic` 7.

Sample rows (site → the tool's callee; the oracle's targets at that site):

- `src/jsx/components.ts:18` → `src/jsx/base.ts:166` [semantic] — oracle: Array.map @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:1470, String.toString @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:412
- `src/jsx/components.ts:38` → `src/jsx/base.ts:166` [semantic] — oracle: Object.toString @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:128
- `src/jsx/components.ts:82` → `src/jsx/base.ts:166` [semantic] — oracle: __type @ src/jsx/context.ts:196, getResume @ src/jsx/components.ts:73, Object.toString @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:128
- `src/jsx/context.ts:226` → `src/jsx/base.ts:166` [semantic] — oracle: String.toString @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:412
- `src/jsx/dom/server.ts:25` → `src/jsx/base.ts:166` [semantic] — oracle: String.toString @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:412
- `src/jsx/dom/server.ts:59` → `src/jsx/base.ts:166` [semantic] — oracle: String.toString @ /home/mmarrujo/hobbes_public/bench/oracle/ts/node_modules/typescript/lib/lib.es5.d.ts:412

**Triage ratio (A-8):** `oracle-wrong 0 : hobbes-wrong 0 : untriaged 7` — the rows are not read; the number above is a lower bound (a contradiction is very strong evidence, not proof; C-62).

**Triage (hand-read, 2026-09-09):** all seven contradictions are one shape: `c.toString()` on a `Child` union receiver (`src/jsx/components.ts:18,38,82`, `context.ts:226`, `dom/server.ts:25,59`, `streaming.ts:64`) drawn at semantic certainty to `JSXNode.toString` (`src/jsx/base.ts:166`) where `tsc` resolves the built-in `String.toString` / `Object.toString` — the `static→union-member` provider shape registered on ajv (P9, scip-typescript), now n=2 repos (ajv 3 rows, hono 7), unfixed. Verdict: hobbes-wrong by tier, the known open semantic defect.

## Misses by class

| class | hits / pairs | misses |
|---|---|---|
| `static→closure` | 0 / 229 | 229 |
| `static→property` | 0 / 93 | 93 |
| `static→method` | 113 / 204 | 91 |
| `static→class` | 0 / 78 | 78 |
| `func-value→local-binding` | 0 / 61 | 61 |
| `interface→type-member` | 0 / 30 | 30 |
| `static→type-member` | 0 / 20 | 20 |
| `static→anonymous-signature` | 0 / 15 | 15 |
| `static→variable` | 597 / 604 | 7 |
| `func-value→variable` | 0 / 4 | 4 |
| `static→anonymous-function` | 0 / 1 | 1 |
| `static→function` | 64 / 64 | 0 |

**Poison check:** PASS — 4,474 seeded wrong edges: 774 refused, 3,700 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix:** first grade — nothing to sign. **Not a comparison with repowise-bench's table:** a different key grain and matcher; the comparison is with the foreign cells on this key.

## Regrade 2026-09-09 (later; ADR-104, C-97 — the union-member abstention; C-98 registered)

Same key (`keys/hono-build/oracle.json`, `tsc 5.9.3` the harness's),
same clone and commit, Hobbes 0.1.4-beta: the TS helper abstains on a
member call whose union-typed receiver's members do not share one
declaration of the member, and the join vetoes lane B's first-member
pick there (the shape the seven contradicted rows were; C-97). Six of
the seven are gone. **One remains — `src/jsx/components.ts:18`**,
`c.toString()` inside `children.flat().map((c) => …)`: lane A's checker
could not type `c` at all there, so it had nothing to abstain with.
The cause is a second, separate gap: this repo's root `tsconfig.json`
is a *solution-style* config (`files: []`, nine `references`), and the
helper's zone project for `src/` loads it as the zone's options — which
is no options, so the checker runs at its ES5 defaults, `Array.flat`
does not exist, and `c` is `any` in every file that reaches its types
through a lib newer than ES5. Lane B indexes under
`tsconfig.build.json` (the C-90 rule) and does not have the gap.
Registered as **C-98** (`docs/constraints/extraction-typescript-javascript.md`);
the fix is the lane-A analogue of C-90's lift and is not in this
regrade. Artifacts under `~/.hobbes/bench/comparative/hobbes-hono-build-r2/`.

```
cell .  oracle tsc 5.9.3 (harness) (resolution)  sha 97c6fe1f
hobbes edges 4468: confirmed 767  contradicted 1  abstract 0  silent 3700 map[not-loaded:3700]
precision-against-oracle 99.9% (767/768)
recall 55.2% (774/1403 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 2122; misses map[func-value→local-binding:61 func-value→variable:4 interface→type-member:30 static→anonymous-function:1 static→anonymous-signature:15 static→class:78 static→closure:229 static→method:91 static→property:93 static→type-member:20 static→variable:7]
  recall[func-value→local-binding]   0.0% (0/61)  misses 61 = 9.7% of all misses
  recall[func-value→variable]   0.0% (0/4)  misses 4 = 0.6% of all misses
  recall[interface→type-member]   0.0% (0/30)  misses 30 = 4.8% of all misses
  recall[static→anonymous-function]   0.0% (0/1)  misses 1 = 0.2% of all misses
  recall[static→anonymous-signature]   0.0% (0/15)  misses 15 = 2.4% of all misses
  recall[static→class      ]   0.0% (0/78)  misses 78 = 12.4% of all misses
  recall[static→closure    ]   0.0% (0/229)  misses 229 = 36.4% of all misses
  recall[static→function   ] 100.0% (64/64)  misses 0 = 0.0% of all misses
  recall[static→method     ]  55.4% (113/204)  misses 91 = 14.5% of all misses
  recall[static→property   ]   0.0% (0/93)  misses 93 = 14.8% of all misses
  recall[static→type-member]   0.0% (0/20)  misses 20 = 3.2% of all misses
  recall[static→variable   ]  98.8% (597/604)  misses 7 = 1.1% of all misses
  tier semantic   confirmed 726  contradicted 1  abstract 0  silent 3587
  tier syntactic  confirmed 41  contradicted 0  abstract 0  silent 113
  line-grain tolerance used on 165 edge(s) (several oracle sites on one line)
  contradicted src/jsx/components.ts:18  hobbes src/jsx/base.ts:166 (src/jsx/base.JSXNode.toString)  oracle .../node_modules/typescript/lib/lib.es5.d.ts:1470 (Array.map), .../node_modules/typescript/lib/lib.es5.d.ts:412 (String.toString)
poison check: PASS — 4468 seeded wrong edges: 768 refused, 3700 unjudged (oracle silent there), 0 falsely confirmed
```

**Precision-against-oracle 99.9% (767/768), 1 contradicted (C-98's
site, the `static→union-member` shape where lane A cannot type the
receiver); recall 55.2% (774/1,403), unchanged.** The row is hobbes-wrong
by tier as before; it stays an exception on the claim page until C-98
is lifted.

## Regrade 2026-09-10 (C-98 lifted, C-99 — a file under a solution-style tsconfig is typed by the referenced project that includes it; 0.1.5-beta)

Same key (`keys/hono-build/oracle.json`, `tsc 5.9.3` the harness's),
same clone and commit, Hobbes 0.1.5-beta: the TS helper resolves a
file under a solution-style `tsconfig.json` to the referenced project
whose inputs include it, by the compiler's own reading of the configs
(`zoneTsconfig`, `tsextract/extract.mjs`), so `src/` is typed under
`tsconfig.build.json` and its tests under `tsconfig.spec.json` instead
of under the root's absent options. **The one row left on 2026-09-09
is gone:** at `src/jsx/components.ts:18` lane A now types `c` through
`children.flat()` — an `Alpha | Beta`-shaped union of `Child` — and
abstains (`union-member`, C-97); the join vetoes lane B's
`JSXNode.toString`. Fifteen `union-member` sites on `src/` in nine
files where there were none: the sites the zone types once it has
options. Recall gains one pair (`static→method` 113 → 114). Lane
agreement is byte-identical to the previous helper's on this clone
(4,332 both-resolved sites, the same one line-grain disagreement,
module edges 42 / 635). Found on the way: hono's six
`runtime-tests/*/tsconfig.json` (references beside options, neither
`files` nor `include`) had been taken for solution configs by both
lanes — registered and fixed as **C-99**; those zones now index under
their own options, outside this cell's key. Artifacts under
`~/.hobbes/bench/comparative/hobbes-hono-build-r3/` (`ingest.log`
beside them; `tsconfig-unclaimed` reports the 22 root files no
referenced project claims).

```
cell .  oracle tsc 5.9.3 (harness) (resolution)  sha 97c6fe1f
hobbes edges 4471: confirmed 768  contradicted 0  abstract 0  silent 3703 map[not-loaded:3703]
precision-against-oracle 100.0% (768/768)
recall 55.2% (775/1403 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 2122; misses map[func-value→local-binding:61 func-value→variable:4 interface→type-member:30 static→anonymous-function:1 static→anonymous-signature:15 static→class:78 static→closure:229 static→method:90 static→property:93 static→type-member:20 static→variable:7]
  recall[func-value→local-binding]   0.0% (0/61)  misses 61 = 9.7% of all misses
  recall[func-value→variable]   0.0% (0/4)  misses 4 = 0.6% of all misses
  recall[interface→type-member]   0.0% (0/30)  misses 30 = 4.8% of all misses
  recall[static→anonymous-function]   0.0% (0/1)  misses 1 = 0.2% of all misses
  recall[static→anonymous-signature]   0.0% (0/15)  misses 15 = 2.4% of all misses
  recall[static→class      ]   0.0% (0/78)  misses 78 = 12.4% of all misses
  recall[static→closure    ]   0.0% (0/229)  misses 229 = 36.5% of all misses
  recall[static→function   ] 100.0% (64/64)  misses 0 = 0.0% of all misses
  recall[static→method     ]  55.9% (114/204)  misses 90 = 14.3% of all misses
  recall[static→property   ]   0.0% (0/93)  misses 93 = 14.8% of all misses
  recall[static→type-member]   0.0% (0/20)  misses 20 = 3.2% of all misses
  recall[static→variable   ]  98.8% (597/604)  misses 7 = 1.1% of all misses
  tier semantic   confirmed 726  contradicted 0  abstract 0  silent 3587
  tier syntactic  confirmed 42  contradicted 0  abstract 0  silent 116
  line-grain tolerance used on 164 edge(s) (several oracle sites on one line)
poison check: PASS — 4471 seeded wrong edges: 768 refused, 3703 unjudged (oracle silent there), 0 falsely confirmed
```

**Precision-against-oracle 100.0% (768/768), 0 contradicted; recall
55.2% (775/1,403).** hono leaves the claim page's exceptions; quic-go
is the one that remains.

## Regrade 2026-09-10 (later; the lane asymmetry closed — lane B under the same zone map; 0.1.6-beta)

Same key, clone and commit, Hobbes 0.1.6-beta: lane B now indexes the
root zone by the projects lane A types it by — `tsconfig.build.json`
for `src/`, `tsconfig.spec.json` for its tests, each under its own
config as a scip-typescript project, and the 22 files no project
claims under a generated config beside the solution file
(`scipsource.ts_zone_map` → the helper's `--zones`; C-98's lane B
half). **768/768 unchanged; one edge moves from the syntactic tier to
the semantic** (727 / 41 where 726 / 42 stood): lane B resolves it
under the build project's options. Lane agreement 4,332 → 4,336
both-resolved sites, the same one line-grain disagreement; lane B's
module edges 1,483 → 1,474. Lane B alone on the root zone, old shape
against new: references 27,682 → 37,216, external references 25,636 →
35,441; module pairs 17 lost (fifteen from the unclaimed
`benchmarks/deno/hono` and `runtime-tests/deno/*` into `src/`, now a
separate program — C-12's shape; two inside `src/` from test files the
spec project now owns) and 8 gained (`src/context` to the middleware
modules that augment it). Artifacts under
`~/.hobbes/bench/comparative/hobbes-hono-build-r4/`.

```
cell .  oracle tsc 5.9.3 (harness) (resolution)  sha 97c6fe1f
hobbes edges 4471: confirmed 768  contradicted 0  abstract 0  silent 3703 map[not-loaded:3703]
precision-against-oracle 100.0% (768/768)
recall 55.2% (775/1403 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 2122; misses map[func-value→local-binding:61 func-value→variable:4 interface→type-member:30 static→anonymous-function:1 static→anonymous-signature:15 static→class:78 static→closure:229 static→method:90 static→property:93 static→type-member:20 static→variable:7]
  recall[func-value→local-binding]   0.0% (0/61)  misses 61 = 9.7% of all misses
  recall[func-value→variable]   0.0% (0/4)  misses 4 = 0.6% of all misses
  recall[interface→type-member]   0.0% (0/30)  misses 30 = 4.8% of all misses
  recall[static→anonymous-function]   0.0% (0/1)  misses 1 = 0.2% of all misses
  recall[static→anonymous-signature]   0.0% (0/15)  misses 15 = 2.4% of all misses
  recall[static→class      ]   0.0% (0/78)  misses 78 = 12.4% of all misses
  recall[static→closure    ]   0.0% (0/229)  misses 229 = 36.5% of all misses
  recall[static→function   ] 100.0% (64/64)  misses 0 = 0.0% of all misses
  recall[static→method     ]  55.9% (114/204)  misses 90 = 14.3% of all misses
  recall[static→property   ]   0.0% (0/93)  misses 93 = 14.8% of all misses
  recall[static→type-member]   0.0% (0/20)  misses 20 = 3.2% of all misses
  recall[static→variable   ]  98.8% (597/604)  misses 7 = 1.1% of all misses
  tier semantic   confirmed 727  contradicted 0  abstract 0  silent 3590
  tier syntactic  confirmed 41  contradicted 0  abstract 0  silent 113
  line-grain tolerance used on 164 edge(s) (several oracle sites on one line)
poison check: PASS — 4471 seeded wrong edges: 768 refused, 3703 unjudged (oracle silent there), 0 falsely confirmed
```

**Precision-against-oracle 100.0% (768/768), 0 contradicted; recall
55.2% (775/1,403).** The standing grade.

## Regrade 2026-09-10 (later still; Hobbes 0.1.8-beta — the versioned baseline: same clone, the 2026-09-09 key, contained)

Every Hobbes cell was re-ingested on one build and regraded against its standing key so the comparative graphics carry one version (Max, 2026-09-10; ADR-103). Artifacts `~/.hobbes/bench/v018/hono-build/`; the graded set unchanged to the digit (768/768, recall 55.2%); 18 more *silent* syntactic edges, all in `benchmarks/**/*.mts` — the files C-100 discovers, which the key's `tsconfig.build.json` program does not load.

```
cell .  oracle tsc 5.9.3 (harness) (resolution)  sha 97c6fe1f
hobbes edges 4489: confirmed 768  contradicted 0  abstract 0  silent 3721 map[not-loaded:3721]
precision-against-oracle 100.0% (768/768)
recall 55.2% (775/1403 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 2122; misses map[func-value→local-binding:61 func-value→variable:4 interface→type-member:30 static→anonymous-function:1 static→anonymous-signature:15 static→class:78 static→closure:229 static→method:90 static→property:93 static→type-member:20 static→variable:7]
  recall[func-value→local-binding]   0.0% (0/61)  misses 61 = 9.7% of all misses
  recall[func-value→variable]   0.0% (0/4)  misses 4 = 0.6% of all misses
  recall[interface→type-member]   0.0% (0/30)  misses 30 = 4.8% of all misses
  recall[static→anonymous-function]   0.0% (0/1)  misses 1 = 0.2% of all misses
  recall[static→anonymous-signature]   0.0% (0/15)  misses 15 = 2.4% of all misses
  recall[static→class      ]   0.0% (0/78)  misses 78 = 12.4% of all misses
  recall[static→closure    ]   0.0% (0/229)  misses 229 = 36.5% of all misses
  recall[static→function   ] 100.0% (64/64)  misses 0 = 0.0% of all misses
  recall[static→method     ]  55.9% (114/204)  misses 90 = 14.3% of all misses
  recall[static→property   ]   0.0% (0/93)  misses 93 = 14.8% of all misses
  recall[static→type-member]   0.0% (0/20)  misses 20 = 3.2% of all misses
  recall[static→variable   ]  98.8% (597/604)  misses 7 = 1.1% of all misses
  tier semantic   confirmed 727  contradicted 0  abstract 0  silent 3601
  tier syntactic  confirmed 41  contradicted 0  abstract 0  silent 120
  line-grain tolerance used on 164 edge(s) (several oracle sites on one line)
poison check: PASS — 4489 seeded wrong edges: 768 refused, 3721 unjudged (oracle silent there), 0 falsely confirmed
```
