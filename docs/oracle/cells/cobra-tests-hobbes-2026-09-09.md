# Oracle cell — cobra (cobra-tests), module `.`, 2026-09-09 (a draw of repowise's, ADR-101 § the 1-1)

**Hobbes on a repo another tool's benchmark drew.** Repo: https://github.com/spf13/cobra, clone `/home/mmarrujo/.hobbes/bench/comparative/repos/cobra`, commit adbc8813901bba65827259daa8e22ff94ec1f30e — the commit repowise-bench's `graph/corpus/corpus.lock` pins for its G4 experiment; the answer key is ours (`/home/mmarrujo/.hobbes/bench/comparative/keys/cobra-tests/oracle.json`: `oracle go-rta (reachability), roots 2, 35 files, 4321 sites`), built by `oracle go-rta` / `ts/tsc-oracle.mjs` on this box, so this cell is 1-1 with the foreign cells beside it (`codegraphcontext-cobra-tests`, `repowise-cobra-tests`) and **not** with repowise-bench's own numbers, whose key is at function grain (caller declaration → callee declaration) and whose matcher is theirs. Ingest: contained, `HOBBES_SCIP=1 uv run hobbes ingest`; capture: capture [go]: 91.6% of 4403 detected call sites accounted; 2 degradation record(s) in the ingest log (quoted in the artifact directory's ingest.log copy)

Command: `oracle export --graph <clone>/.hobbes/derived/graph.json --module . --lang <lang> --out hobbes.json && oracle grade --hobbes hobbes.json --oracle cobra-tests/oracle.json --json report.json --poison`. Outputs in `/home/mmarrujo/.hobbes/bench/comparative/hobbes-cobra-tests`.

## Numbers (report.txt, head, verbatim)

```
cell .  oracle go-rta (reachability)  sha adbc8813
hobbes edges 2192: confirmed 2186  contradicted 0  abstract 1  silent 5 map[unreachable:5]
precision-against-oracle 100.0% (2186/2186)
recall 71.8% (2200/3062 in-repo oracle pairs) at 2 roots; external oracle pairs 4608; misses map[func-value→closure:733 func-value→named:66 interface→named:43 static→closure:20]
  recall[func-value→closure]   0.0% (0/733)  misses 733 = 85.0% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[func-value→named  ]   0.0% (0/66)  misses 66 = 7.7% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[interface→named   ]   0.0% (0/43)  misses 43 = 5.0% of all misses
  recall[static→closure    ]   0.0% (0/20)  misses 20 = 2.3% of all misses
  recall[static→named      ] 100.0% (2200/2200)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 2186  contradicted 0  abstract 1  silent 5
  line-grain tolerance used on 873 edge(s) (several oracle sites on one line)
poison check: PASS — 2192 seeded wrong edges: 2187 refused, 5 unjudged (oracle silent there), 0 falsely confirmed
```

| bucket | count |
|---|---|
| graded edges | 2,192 |
| confirmed | 2,186 |
| contradicted | 0 |
| abstract | 1 |
| silent | 5 {"unreachable": 5} |
| precision-against-oracle (lower bound) | **100.0%** (2,186/2,186) |
| recall | 71.8% (2,200/3,062) at 2 roots |

**By tier:** `semantic` confirmed 2186 / contradicted 0 / abstract 1 / silent 5.

**Triage (hand-read, 2026-09-09):** 0 contradicted; nothing to read.

## Misses by class

| class | hits / pairs | misses |
|---|---|---|
| `func-value→closure` | 0 / 733 | 733 |
| `func-value→named` | 0 / 66 | 66 |
| `interface→named` | 0 / 43 | 43 |
| `static→closure` | 0 / 20 | 20 |
| `static→named` | 2,200 / 2,200 | 0 |

**Poison check:** PASS — 2,192 seeded wrong edges: 2,187 refused, 5 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix:** first grade — nothing to sign. **Not a comparison with repowise-bench's table:** a different key grain and matcher; the comparison is with the foreign cells on this key.

## Regrade 2026-09-10 (later still; Hobbes 0.1.8-beta — the versioned baseline: same clone, the 2026-09-09 key, contained)

Every Hobbes cell was re-ingested on one build and regraded against its standing key so the comparative graphics carry one version (Max, 2026-09-10; ADR-103). Artifacts `~/.hobbes/bench/v018/cobra-tests/`; unchanged to the digit from the standing grade.

```
cell .  oracle go-rta (reachability)  sha adbc8813
hobbes edges 2192: confirmed 2186  contradicted 0  abstract 1  silent 5 map[unreachable:5]
precision-against-oracle 100.0% (2186/2186)
recall 71.8% (2200/3062 in-repo oracle pairs) at 2 roots; external oracle pairs 4608; misses map[func-value→closure:733 func-value→named:66 interface→named:43 static→closure:20]
  recall[func-value→closure]   0.0% (0/733)  misses 733 = 85.0% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[func-value→named  ]   0.0% (0/66)  misses 66 = 7.7% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[interface→named   ]   0.0% (0/43)  misses 43 = 5.0% of all misses
  recall[static→closure    ]   0.0% (0/20)  misses 20 = 2.3% of all misses
  recall[static→named      ] 100.0% (2200/2200)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 2186  contradicted 0  abstract 1  silent 5
  line-grain tolerance used on 873 edge(s) (several oracle sites on one line)
poison check: PASS — 2192 seeded wrong edges: 2187 refused, 5 unjudged (oracle silent there), 0 falsely confirmed
```
