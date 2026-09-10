# Oracle cell — gitleaks (gitleaks-tests), module `.`, 2026-09-09 (a draw of repowise's, ADR-101 § the 1-1)

**Hobbes on a repo another tool's benchmark drew.** Repo: https://github.com/gitleaks/gitleaks, clone `/home/mmarrujo/.hobbes/bench/comparative/repos/gitleaks`, commit 8ad8470035d31a209322c580153b45c18e21b980 — the commit repowise-bench's `graph/corpus/corpus.lock` pins for its G4 experiment; the answer key is ours (`/home/mmarrujo/.hobbes/bench/comparative/keys/gitleaks-tests/oracle.json`: `oracle go-rta (reachability), roots 9, 203 files, 4252 sites`), built by `oracle go-rta` / `ts/tsc-oracle.mjs` on this box, so this cell is 1-1 with the foreign cells beside it (`codegraphcontext-gitleaks-tests`, `repowise-gitleaks-tests`) and **not** with repowise-bench's own numbers, whose key is at function grain (caller declaration → callee declaration) and whose matcher is theirs. Ingest: contained, `HOBBES_SCIP=1 uv run hobbes ingest`; capture: capture [go]: 90.2% of 4369 detected call sites accounted; capture [python]: 85.7% of 7 detected call sites accounted; 4 degradation record(s) in the ingest log (quoted in the artifact directory's ingest.log copy)

Command: `oracle export --graph <clone>/.hobbes/derived/graph.json --module . --lang <lang> --out hobbes.json && oracle grade --hobbes hobbes.json --oracle gitleaks-tests/oracle.json --json report.json --poison`. Outputs in `/home/mmarrujo/.hobbes/bench/comparative/hobbes-gitleaks-tests`.

## Numbers (report.txt, head, verbatim)

```
cell .  oracle go-rta (reachability)  sha 8ad84700
hobbes edges 2283: confirmed 2266  contradicted 0  abstract 0  silent 17 map[unreachable:17]
precision-against-oracle 100.0% (2266/2266)
recall 94.9% (2325/2450 in-repo oracle pairs) at 9 roots; external oracle pairs 5849; misses map[func-value→closure:76 func-value→named:19 interface→named:20 static→closure:10]
  recall[func-value→closure]   0.0% (0/76)  misses 76 = 60.8% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[func-value→named  ]   0.0% (0/19)  misses 19 = 15.2% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[interface→named   ]   0.0% (0/20)  misses 20 = 16.0% of all misses
  recall[static→closure    ]   0.0% (0/10)  misses 10 = 8.0% of all misses
  recall[static→named      ] 100.0% (2325/2325)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 2266  contradicted 0  abstract 0  silent 17
  line-grain tolerance used on 1049 edge(s) (several oracle sites on one line)
poison check: PASS — 2283 seeded wrong edges: 2266 refused, 17 unjudged (oracle silent there), 0 falsely confirmed
```

| bucket | count |
|---|---|
| graded edges | 2,283 |
| confirmed | 2,266 |
| contradicted | 0 |
| abstract | 0 |
| silent | 17 {"unreachable": 17} |
| precision-against-oracle (lower bound) | **100.0%** (2,266/2,266) |
| recall | 94.9% (2,325/2,450) at 9 roots |

**By tier:** `semantic` confirmed 2266 / contradicted 0 / abstract 0 / silent 17.

**Triage (hand-read, 2026-09-09):** the one contradiction was hobbes-wrong on the syntactic tier: `re.MustCompile(str)` inside the repo's own `regexp.MustCompile` (`regexp/stdlib_regex.go:14`, `import re "regexp"`) was drawn to the enclosing function — lane A's fallback matched the stdlib import path `regexp` to the repo's `regexp/` directory by suffix. Fixed the same day in `gosource._repo_package` (a path whose first element has no dot is the standard library's, cmd/go's rule; test in `test_gosource.py`), the clone re-ingested contained and the cell regraded.

## Misses by class

| class | hits / pairs | misses |
|---|---|---|
| `func-value→closure` | 0 / 76 | 76 |
| `interface→named` | 0 / 20 | 20 |
| `func-value→named` | 0 / 19 | 19 |
| `static→closure` | 0 / 10 | 10 |
| `static→named` | 2,325 / 2,325 | 0 |

**Poison check:** PASS — 2,283 seeded wrong edges: 2,266 refused, 17 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix (2026-09-09, signed):** the repo re-ingested contained after the fallback fix (`_repo_package`: a stdlib import path never names a repo package) graded edges 2,284 → 2,283 (-1); confirmed 2,266 → 2,266 (+0); contradicted 1 → 0 (-1); precision-against-oracle 100.0% → 100.0% (+0.0); recall 94.9% → 94.9% (+0.0). `report.v1.*` beside the cell keeps the first grade.

**Not a comparison with repowise-bench's table:** a different key grain and matcher; the comparison is with the foreign cells on this key.

## Regrade 2026-09-10 (later still; Hobbes 0.1.8-beta — the versioned baseline: same clone, the 2026-09-09 key, contained)

Every Hobbes cell was re-ingested on one build and regraded against its standing key so the comparative graphics carry one version (Max, 2026-09-10; ADR-103). Artifacts `~/.hobbes/bench/v018/gitleaks-tests/`; unchanged to the digit from the standing grade.

```
cell .  oracle go-rta (reachability)  sha 8ad84700
hobbes edges 2283: confirmed 2266  contradicted 0  abstract 0  silent 17 map[unreachable:17]
precision-against-oracle 100.0% (2266/2266)
recall 94.9% (2325/2450 in-repo oracle pairs) at 9 roots; external oracle pairs 5849; misses map[func-value→closure:76 func-value→named:19 interface→named:20 static→closure:10]
  recall[func-value→closure]   0.0% (0/76)  misses 76 = 60.8% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[func-value→named  ]   0.0% (0/19)  misses 19 = 15.2% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[interface→named   ]   0.0% (0/20)  misses 20 = 16.0% of all misses
  recall[static→closure    ]   0.0% (0/10)  misses 10 = 8.0% of all misses
  recall[static→named      ] 100.0% (2325/2325)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 2266  contradicted 0  abstract 0  silent 17
  line-grain tolerance used on 1049 edge(s) (several oracle sites on one line)
poison check: PASS — 2283 seeded wrong edges: 2266 refused, 17 unjudged (oracle silent there), 0 falsely confirmed
```


## Regrade 2026-09-10 (later still; Hobbes 0.1.10-beta — every cell on one build again: same clone, the 2026-09-09 key, contained)

Every Hobbes cell was re-ingested on 0.1.10-beta and regraded against its standing key so the comparative graphics state one version (Max, 2026-09-10; ADR-103, third amendment). Artifacts `~/.hobbes/bench/v0110/gitleaks-tests/`; **unchanged to the digit from the 0.1.8-beta grade**; the one new line is the grader's `recall-collapsed` (ADR-089 amended).

```
cell .  oracle go-rta (reachability)  sha 8ad84700
hobbes edges 2283: confirmed 2266  contradicted 0  abstract 0  silent 17 map[unreachable:17]
precision-against-oracle 100.0% (2266/2266)
recall 94.9% (2325/2450 in-repo oracle pairs) at 9 roots; external oracle pairs 5849; misses map[func-value→closure:76 func-value→named:19 interface→named:20 static→closure:10]
recall-collapsed 94.8% (2266/2391 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)
  recall[func-value→closure]   0.0% (0/76)  misses 76 = 60.8% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[func-value→named  ]   0.0% (0/19)  misses 19 = 15.2% of all misses  (inflated: reachability oracle over-approximates function values; upper bound)
  recall[interface→named   ]   0.0% (0/20)  misses 20 = 16.0% of all misses
  recall[static→closure    ]   0.0% (0/10)  misses 10 = 8.0% of all misses
  recall[static→named      ] 100.0% (2325/2325)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 2266  contradicted 0  abstract 0  silent 17
  line-grain tolerance used on 1049 edge(s) (several oracle sites on one line)
poison check: PASS — 2283 seeded wrong edges: 2266 refused, 17 unjudged (oracle silent there), 0 falsely confirmed
```
