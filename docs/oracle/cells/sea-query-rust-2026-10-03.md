# Oracle cell — SeaQL/sea-query, package `.`, 2026-10-03 (drawn at random; held out for the turbofish rule)

Repo: https://github.com/SeaQL/sea-query (MIT OR Apache-2.0), clone at `~/.hobbes/bench/oracle/repos/sea-query`,
commit 7803693c39d8dadb38cdc3dc4d5437c99adc67ed (shallow). **Drawn**: position 5 of the Rust draw
(oracle-grading.md §10.49), taken by the turbofish rule's shape condition (85 in-macro turbofish calls) and
amendment 3, which carried PREREG.md's R1–R6, R8, R9 to it before the ingest. A SQL query builder: a root
`[package]` (33,471 lines under `src/`, 9,976 under `tests/`) in a workspace with a proc-macro crate
(`sea-query-derive`) and driver crates. First run at `ec3e134` (0.2.112-beta, the rule's before arm), lane B
on, contained. Oracle `rustc-mir`, rustc 1.100.0-nightly (e7769602a 2026-08-24).

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/sea-query . ~/.hobbes/bench/oracle/sea-query-rust
--lang rust`. Runtime 21 s.

## Numbers at 0.2.112-beta (report.txt, verbatim; rows elided)

```
cell   oracle rustc-mir rustc 1.100.0-nightly (e7769602a 2026-08-24) (resolution)  sha 7803693c
hobbes edges 5927: confirmed 5601  contradicted 16  abstract 0  silent 310 map[not-loaded:299 unreachable:11]
precision-against-oracle 99.7% (5601/5617)
recall 83.8% (5637/6725 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 7562; misses map[interface→method:4 macro→function:4 macro→generated:56 static→closure:11 static→function:55 static→generated:118 static→method:840]
  recall[interface→method  ]   0.0% (0/4)  misses 4 = 0.4% of all misses
  recall[macro→function    ]   0.0% (0/4)  misses 4 = 0.4% of all misses
  recall[macro→generated   ]   0.0% (0/56)  misses 56 = 5.1% of all misses
  recall[static→closure    ]   0.0% (0/11)  misses 11 = 1.0% of all misses
  recall[static→function   ]  61.8% (89/144)  misses 55 = 5.1% of all misses
  recall[static→generated  ]   0.0% (0/118)  misses 118 = 10.8% of all misses
  recall[static→method     ]  86.9% (5548/6388)  misses 840 = 77.2% of all misses
  tier semantic   confirmed 5598  contradicted 16  abstract 0  silent 276
  tier syntactic  confirmed 3  contradicted 0  abstract 0  silent 34
poison check: PASS — 5927 seeded wrong edges: 5478 refused, 449 unjudged (oracle silent there), 0 falsely confirmed
```

Strict precision equals the standing figure (no `line-unresolved` row).

## Contradicted (16, all semantic): a proc-macro invocation read as a runtime call — Hobbes', fixed

Every row is `sea_query::raw_sql!(..)` (14) or `raw_query!(..)` (2) in `tests/raw_sql.rs`, drawn as `calls` to
`#[proc_macro] pub fn raw_sql` / `raw_query` in `sea-query-derive/src/lib.rs`. The compiler runs those fns at
expansion; rustc's MIR holds the expansion's calls (`RawSqlQueryBuilder::new`, `push_fragment`). The fns
were minted `function`, where a `macro_rules!` is a `macro` the export leaves out: an unnamed limit
(precedent 1). **Fixed at 0.2.114-beta:** a free fn under `#[proc_macro]`, `#[proc_macro_attribute]` or
`#[proc_macro_derive]` is minted `macro`; 11 nodes here change kind and no edge moves.

## The turbofish rule (0.2.113-beta): no change here

All 85 in-macro turbofish calls are `.collect::<…>()`, the standard library's, so the key holds no in-repo pair at
any of them and the cell could not judge the rule's gain (`PREREG-rule.md` amendment 4). 5,601 → 5,601.

## Regraded at 0.2.114-beta (head verbatim)

```
cell   oracle rustc-mir rustc 1.100.0-nightly (e7769602a 2026-08-24) (resolution)  sha 7803693c
hobbes edges 5911: confirmed 5601  contradicted 0  abstract 0  silent 310 map[not-loaded:299 unreachable:11]
precision-against-oracle 100.0% (5601/5601)
recall 83.8% (5637/6725 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 7562; misses map[interface→method:4 macro→function:4 macro→generated:56 static→closure:11 static→function:55 static→generated:118 static→method:840]
  recall[interface→method  ]   0.0% (0/4)  misses 4 = 0.4% of all misses
  recall[macro→function    ]   0.0% (0/4)  misses 4 = 0.4% of all misses
  recall[macro→generated   ]   0.0% (0/56)  misses 56 = 5.1% of all misses
  recall[static→closure    ]   0.0% (0/11)  misses 11 = 1.0% of all misses
  recall[static→function   ]  61.8% (89/144)  misses 55 = 5.1% of all misses
  recall[static→generated  ]   0.0% (0/118)  misses 118 = 10.8% of all misses
  recall[static→method     ]  86.9% (5548/6388)  misses 840 = 77.2% of all misses
  tier semantic   confirmed 5598  contradicted 0  abstract 0  silent 276
  tier syntactic  confirmed 3  contradicted 0  abstract 0  silent 34
poison check: PASS — 5911 seeded wrong edges: 5462 refused, 449 unjudged (oracle silent there), 0 falsely confirmed
```

R1–R3: met after the fix (16 Hobbes-wrong rows before it, now 0). R4 (recall 55–92%) met at 83.8%; R5 met
(3 `syntactic` of 5,601); R6 met (`static→method` the largest class, 840); R8 met; R9 met (251 sites, 0 disagree).
