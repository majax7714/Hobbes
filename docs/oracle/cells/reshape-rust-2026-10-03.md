# Oracle cell — fabianlindfors/reshape, package `.`, 2026-10-03 (drawn at random; held out for the turbofish rule)

Repo: https://github.com/fabianlindfors/reshape (MIT), clone at `~/.hobbes/bench/oracle/repos/reshape`, commit
1c52737b3213bede6997815d4b1f59c6b9174eba (shallow). **Drawn**: position 85 of the Rust draw (oracle-grading.md
§10.49), the first package after sea-query and slumber to hold at least 20 in-macro turbofish calls to a
repo-declared name (`PREREG-rule.md` amendments 5 and 6). A Postgres schema-migration tool, 16,402 lines in one
package. First run at `ec3e134` (0.2.112-beta, the rule's before arm), lane B on, contained. Oracle `rustc-mir`,
rustc 1.100.0-nightly (e7769602a 2026-08-24).

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/reshape . ~/.hobbes/bench/oracle/reshape-rust
--lang rust`. Runtime 77 s. Graded again at 0.2.113-beta (the rule) and unchanged; 0.2.114-beta cannot move it
(no proc macro).

## Numbers (report.txt, verbatim; rows elided)

```
cell   oracle rustc-mir rustc 1.100.0-nightly (e7769602a 2026-08-24) (resolution)  sha 1c52737b
hobbes edges 1315: confirmed 1315  contradicted 0  abstract 0  silent 0 map[]
precision-against-oracle 100.0% (1315/1315)
recall 96.3% (1346/1398 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 6048; misses map[static→closure:3 static→function:1 static→generated:48]
  recall[static→closure    ]   0.0% (0/3)  misses 3 = 5.8% of all misses
  recall[static→function   ]  99.8% (421/422)  misses 1 = 1.9% of all misses
  recall[static→generated  ]   0.0% (0/48)  misses 48 = 92.3% of all misses
  recall[static→method     ] 100.0% (925/925)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 1315  contradicted 0  abstract 0  silent 0
poison check: PASS — 1315 seeded wrong edges: 1315 refused, 0 unjudged (oracle silent there), 0 falsely confirmed
```

Strict precision equals the standing figure (no `line-unresolved` row).

## Findings

- 0 contradicted; every miss is a derive's target (48, C-9), a closure (3) or one `static→function`.
- The turbofish rule could not judge its gain here either: the 37 "repo-named" in-macro turbofish calls are
  `result.get::<_, &str>(..)`, postgres's `Row::get` sharing a name with a repo `fn get`. 1,315 → 1,315.
- `hobbes lanes`: 207 sites, 0 disagree.
