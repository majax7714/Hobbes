# Oracle cell — gitleaks (gitleaks-notests), module `.`, 2026-09-09 (a draw of repowise's, ADR-101 § the 1-1)

**Hobbes on a repo another tool's benchmark drew.** Repo: https://github.com/gitleaks/gitleaks, clone `/home/mmarrujo/.hobbes/bench/comparative/repos/gitleaks`, commit 8ad8470035d31a209322c580153b45c18e21b980 — the commit repowise-bench's `graph/corpus/corpus.lock` pins for its G4 experiment; the answer key is ours (`/home/mmarrujo/.hobbes/bench/comparative/keys/gitleaks-notests/oracle.json`: `oracle go-rta (no test packages) (reachability), roots 2, 184 files, 3506 sites`), built by `oracle go-rta` / `ts/tsc-oracle.mjs` on this box, so this cell is 1-1 with the foreign cells beside it (`codegraphcontext-gitleaks-notests`, `repowise-gitleaks-notests`) and **not** with repowise-bench's own numbers, whose key is at function grain (caller declaration → callee declaration) and whose matcher is theirs. Ingest: contained, `HOBBES_SCIP=1 uv run hobbes ingest`; capture: capture [go]: 90.2% of 4369 detected call sites accounted; capture [python]: 85.7% of 7 detected call sites accounted; 4 degradation record(s) in the ingest log (quoted in the artifact directory's ingest.log copy)

Command: `oracle export --graph <clone>/.hobbes/derived/graph.json --module . --lang <lang> --out hobbes.json && oracle grade --hobbes hobbes.json --oracle gitleaks-notests/oracle.json --json report.json --poison`. Outputs in `/home/mmarrujo/.hobbes/bench/comparative/hobbes-gitleaks-notests`.

## Numbers (report.txt, head, verbatim)

```
cell .  oracle go-rta (no test packages) (reachability)  sha 8ad84700
hobbes edges 2283: confirmed 2010  contradicted 0  abstract 0  silent 273 map[not-loaded:238 unreachable:35]
precision-against-oracle 100.0% (2010/2010)
recall 98.0% (2069/2111 in-repo oracle pairs) at 2 roots; external oracle pairs 3291; misses map[func-value→closure:17 func-value→named:4 interface→named:13 static→closure:8]
  recall[func-value→closure]   0.0% (0/17)  misses 17 = 40.5% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[func-value→named  ]   0.0% (0/4)  misses 4 = 9.5% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[interface→named   ]   0.0% (0/13)  misses 13 = 31.0% of all misses
  recall[static→closure    ]   0.0% (0/8)  misses 8 = 19.0% of all misses
  recall[static→named      ] 100.0% (2069/2069)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 2010  contradicted 0  abstract 0  silent 273
  line-grain tolerance used on 1039 edge(s) (several oracle sites on one line)
poison check: PASS — 2283 seeded wrong edges: 2010 refused, 273 unjudged (oracle silent there), 0 falsely confirmed
```

| bucket | count |
|---|---|
| graded edges | 2,283 |
| confirmed | 2,010 |
| contradicted | 0 |
| abstract | 0 |
| silent | 273 {"not-loaded": 238, "unreachable": 35} |
| precision-against-oracle (lower bound) | **100.0%** (2,010/2,010) |
| recall | 98.0% (2,069/2,111) at 2 roots |

**By tier:** `semantic` confirmed 2010 / contradicted 0 / abstract 0 / silent 273.

**Triage (hand-read, 2026-09-09):** the same one contradiction as the with-tests cell (`regexp/stdlib_regex.go:14`, syntactic tier, hobbes-wrong), fixed and regraded the same day.

## Misses by class

| class | hits / pairs | misses |
|---|---|---|
| `func-value→closure` | 0 / 17 | 17 |
| `interface→named` | 0 / 13 | 13 |
| `static→closure` | 0 / 8 | 8 |
| `func-value→named` | 0 / 4 | 4 |
| `static→named` | 2,069 / 2,069 | 0 |

**Poison check:** PASS — 2,283 seeded wrong edges: 2,010 refused, 273 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix (2026-09-09, signed):** the repo re-ingested contained after the fallback fix (`_repo_package`: a stdlib import path never names a repo package) graded edges 2,284 → 2,283 (-1); confirmed 2,010 → 2,010 (+0); contradicted 1 → 0 (-1); precision-against-oracle 100.0% → 100.0% (+0.0); recall 98.0% → 98.0% (+0.0). `report.v1.*` beside the cell keeps the first grade.

**Not a comparison with repowise-bench's table:** a different key grain and matcher; the comparison is with the foreign cells on this key.

