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

