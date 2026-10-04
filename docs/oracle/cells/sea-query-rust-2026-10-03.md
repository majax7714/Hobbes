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

## Regraded at 0.2.117-beta (ADR-177: a trait's provided method is a node)

The rule was found here (669 of 1,088 misses), so this cell is fitted for it; it was measured held out on cyme. 5,601 → **6,263** confirmed, 0 contradicted, recall 83.8% → 93.7%; 202 nodes added (50 drawn and read: each a `fn` with a body in a `trait` body); 36 confirmed rows keep their site and target and now name the provided method as caller. Driver `~/.hobbes/bench/rust-provided-2026-10-04/regrade/`. Head verbatim:

```
cell   oracle rustc-mir rustc 1.100.0-nightly (e7769602a 2026-08-24) (resolution)  sha 7803693c
oracle ran contained (ADR-092)
hobbes edges 6885: confirmed 6263  contradicted 0  abstract 298  silent 324 map[not-loaded:313 unreachable:11]
precision-against-oracle 100.0% (6263/6263)
recall 93.7% (6302/6725 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 7562; misses map[interface→method:4 macro→function:4 macro→generated:56 static→closure:11 static→function:55 static→generated:118 static→method:175]
recall-collapsed 93.7% (6263/6684 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)
  recall[interface→method  ]   0.0% (0/4)  misses 4 = 0.9% of all misses
  recall[macro→function    ]   0.0% (0/4)  misses 4 = 0.9% of all misses
  recall[macro→generated   ]   0.0% (0/56)  misses 56 = 13.2% of all misses
  recall[static→closure    ]   0.0% (0/11)  misses 11 = 2.6% of all misses
  recall[static→function   ]  61.8% (89/144)  misses 55 = 13.0% of all misses
  recall[static→generated  ]   0.0% (0/118)  misses 118 = 27.9% of all misses
  recall[static→method     ]  97.3% (6213/6388)  misses 175 = 41.4% of all misses
  tier semantic   confirmed 6260  contradicted 0  abstract 298  silent 290
  tier syntactic  confirmed 3  contradicted 0  abstract 0  silent 34
  abstract     src/backend/index_builder.rs:22  hobbes src/backend/index_builder.rs:77 (src/backend/index_builder.IndexBuilder.prepare_index_columns)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/index_builder.rs:24  hobbes src/backend/index_builder.rs:107 (src/backend/index_builder.IndexBuilder.prepare_filter)  oracle -
  abstract     src/backend/index_builder.rs:65  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/index_builder.rs:66  hobbes src/backend/index_builder.rs:50 (src/backend/index_builder.IndexBuilder.write_column_index_prefix)  oracle -
  abstract     src/backend/mod.rs:78  hobbes src/backend/mod.rs:82 (src/backend/mod.EscapeBuilder.write_escaped)  oracle -
  abstract     src/backend/query_builder.rs:1007  hobbes src/backend/query_builder.rs:1010 (src/backend/query_builder.QueryBuilder.prepare_join_type_common)  oracle -
  abstract     src/backend/query_builder.rs:102  hobbes src/backend/query_builder.rs:1436 (src/backend/query_builder.QueryBuilder.prepare_on_conflict)  oracle -
  abstract     src/backend/query_builder.rs:1026  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1028  hobbes src/backend/query_builder.rs:1040 (src/backend/query_builder.QueryBuilder.prepare_order)  oracle -
  abstract     src/backend/query_builder.rs:1034  hobbes src/backend/query_builder.rs:1639 (src/backend/query_builder.QueryBuilder.prepare_condition)  oracle -
  abstract     src/backend/query_builder.rs:104  hobbes src/backend/query_builder.rs:1602 (src/backend/query_builder.QueryBuilder.prepare_returning)  oracle -
  abstract     src/backend/query_builder.rs:1044  hobbes src/backend/query_builder.rs:1049 (src/backend/query_builder.QueryBuilder.prepare_field_order)  oracle -
  abstract     src/backend/query_builder.rs:1059  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1061  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1078  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1092  hobbes src/backend/query_builder.rs:16 (src/backend/query_builder.QueryBuilder.values_list_tuple_prefix)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1148  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1167  hobbes src/backend/query_builder.rs:1170 (src/backend/query_builder.QueryBuilder.value_to_string_common)  oracle -
  abstract     src/backend/query_builder.rs:1172  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1178  hobbes src/backend/query_builder.rs:1182 (src/backend/query_builder.QueryBuilder.write_value_common)  oracle -
  abstract     src/backend/query_builder.rs:119  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle -
  abstract     src/backend/query_builder.rs:126  hobbes src/backend/query_builder.rs:841 (src/backend/query_builder.QueryBuilder.prepare_with_clause)  oracle -
  abstract     src/backend/query_builder.rs:1271  hobbes src/backend/query_builder.rs:1794 (src/backend/query_builder.QueryBuilder.write_string_quoted)  oracle :0 (<std::string::String as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:1273  hobbes src/backend/query_builder.rs:1794 (src/backend/query_builder.QueryBuilder.write_string_quoted)  oracle :0 (<std::borrow::Cow<'_, T> as std::convert::AsRef<T>>::as_ref)
  abstract     src/backend/query_builder.rs:1277  hobbes src/backend/query_builder.rs:1794 (src/backend/query_builder.QueryBuilder.write_string_quoted)  oracle :0 (std::str::from_utf8), :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1279  hobbes src/backend/query_builder.rs:1802 (src/backend/query_builder.QueryBuilder.write_bytes)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:132  hobbes src/backend/query_builder.rs:542 (src/backend/query_builder.QueryBuilder.prepare_select_distinct)  oracle -
  abstract     src/backend/query_builder.rs:1438  hobbes src/backend/query_builder.rs:1566 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_keywords)  oracle -
  abstract     src/backend/query_builder.rs:1439  hobbes src/backend/query_builder.rs:1448 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_target)  oracle -
  abstract     src/backend/query_builder.rs:144  hobbes src/backend/query_builder.rs:589 (src/backend/query_builder.QueryBuilder.prepare_select_expr)  oracle -
  abstract     src/backend/query_builder.rs:1440  hobbes src/backend/query_builder.rs:1588 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_condition)  oracle -
  abstract     src/backend/query_builder.rs:1441  hobbes src/backend/query_builder.rs:1517 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_action)  oracle -
  abstract     src/backend/query_builder.rs:1442  hobbes src/backend/query_builder.rs:1588 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_condition)  oracle -
  abstract     src/backend/query_builder.rs:1455  hobbes src/backend/query_builder.rs:1465 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_target_identifiers)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:1458  hobbes src/backend/query_builder.rs:1510 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_target_constraint)  oracle :0 (<std::string::String as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:1476  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:1493  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1496  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1522  hobbes src/backend/query_builder.rs:1525 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_action_common)  oracle -
  abstract     src/backend/query_builder.rs:1536  hobbes src/backend/query_builder.rs:1572 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_do_update_keywords)  oracle -
  abstract     src/backend/query_builder.rs:1547  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:1549  hobbes src/backend/query_builder.rs:1578 (src/backend/query_builder.QueryBuilder.prepare_on_conflict_excluded_table)  oracle -
  abstract     src/backend/query_builder.rs:1552  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:1554  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1583  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:1593  hobbes src/backend/query_builder.rs:1639 (src/backend/query_builder.QueryBuilder.prepare_condition)  oracle -
  abstract     src/backend/query_builder.rs:1616  hobbes src/backend/query_builder.rs:655 (src/backend/query_builder.QueryBuilder.prepare_column_ref)  oracle -
  abstract     src/backend/query_builder.rs:1629  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:163  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:164  hobbes src/backend/query_builder.rs:551 (src/backend/query_builder.QueryBuilder.prepare_index_hints)  oracle -
  abstract     src/backend/query_builder.rs:1652  hobbes src/backend/query_builder.rs:735 (src/backend/query_builder.QueryBuilder.prepare_logical_chain_oper)  oracle :0 (std::vec::Vec::<T, A>::len)
  abstract     src/backend/query_builder.rs:1659  hobbes src/backend/query_builder.rs:1666 (src/backend/query_builder.QueryBuilder.prepare_condition_where)  oracle -
  abstract     src/backend/query_builder.rs:1668  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:167  hobbes src/backend/query_builder.rs:560 (src/backend/query_builder.QueryBuilder.prepare_table_sample)  oracle -
  abstract     src/backend/query_builder.rs:1703  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1718  hobbes src/backend/query_builder.rs:1024 (src/backend/query_builder.QueryBuilder.prepare_order_expr)  oracle -
  abstract     src/backend/query_builder.rs:1729  hobbes src/backend/query_builder.rs:1673 (src/backend/query_builder.QueryBuilder.prepare_frame)  oracle -
  abstract     src/backend/query_builder.rs:173  hobbes src/backend/query_builder.rs:612 (src/backend/query_builder.QueryBuilder.prepare_join_expr)  oracle -
  abstract     src/backend/query_builder.rs:1731  hobbes src/backend/query_builder.rs:1673 (src/backend/query_builder.QueryBuilder.prepare_frame)  oracle -
  abstract     src/backend/query_builder.rs:1733  hobbes src/backend/query_builder.rs:1673 (src/backend/query_builder.QueryBuilder.prepare_frame)  oracle -
  abstract     src/backend/query_builder.rs:1754  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:176  hobbes src/backend/query_builder.rs:1639 (src/backend/query_builder.QueryBuilder.prepare_condition)  oracle -
  abstract     src/backend/query_builder.rs:1760  hobbes src/backend/query_builder.rs:719 (src/backend/query_builder.QueryBuilder.prepare_bin_oper)  oracle -
  abstract     src/backend/query_builder.rs:1788  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1796  hobbes src/backend/mod.rs:82 (src/backend/mod.EscapeBuilder.write_escaped)  oracle -
  abstract     src/backend/query_builder.rs:1861  hobbes src/backend/query_builder.rs:1853 (src/backend/query_builder.QueryBuilder.insert_default_keyword)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1865  hobbes src/backend/query_builder.rs:1853 (src/backend/query_builder.QueryBuilder.insert_default_keyword)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:1872  hobbes src/backend/query_builder.rs:1077 (src/backend/query_builder.QueryBuilder.prepare_constant)  oracle :0 (<T as std::convert::Into<U>>::into)
  abstract     src/backend/query_builder.rs:1877  hobbes src/backend/query_builder.rs:1077 (src/backend/query_builder.QueryBuilder.prepare_constant)  oracle :0 (<T as std::convert::Into<U>>::into)
  abstract     src/backend/query_builder.rs:1889  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle -
  abstract     src/backend/query_builder.rs:189  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:1890  hobbes src/backend/query_builder.rs:21 (src/backend/query_builder.QueryBuilder.prepare_insert_statement)  oracle -
  abstract     src/backend/query_builder.rs:1891  hobbes src/backend/query_builder.rs:246 (src/backend/query_builder.QueryBuilder.prepare_update_statement)  oracle -
  abstract     src/backend/query_builder.rs:1892  hobbes src/backend/query_builder.rs:356 (src/backend/query_builder.QueryBuilder.prepare_delete_statement)  oracle -
  abstract     src/backend/query_builder.rs:1893  hobbes src/backend/query_builder.rs:836 (src/backend/query_builder.QueryBuilder.prepare_with_query)  oracle -
  abstract     src/backend/query_builder.rs:193  hobbes src/backend/query_builder.rs:1639 (src/backend/query_builder.QueryBuilder.prepare_condition)  oracle -
  abstract     src/backend/query_builder.rs:197  hobbes src/backend/query_builder.rs:107 (src/backend/query_builder.QueryBuilder.prepare_union_statement)  oracle -
  abstract     src/backend/query_builder.rs:212  hobbes src/backend/query_builder.rs:1024 (src/backend/query_builder.QueryBuilder.prepare_order_expr)  oracle -
  abstract     src/backend/query_builder.rs:216  hobbes src/backend/query_builder.rs:233 (src/backend/query_builder.QueryBuilder.prepare_select_limit_offset)  oracle -
  abstract     src/backend/query_builder.rs:22  hobbes src/backend/query_builder.rs:26 (src/backend/query_builder.QueryBuilder.prepare_insert_statement_common)  oracle -
  abstract     src/backend/query_builder.rs:220  hobbes src/backend/query_builder.rs:563 (src/backend/query_builder.QueryBuilder.prepare_select_lock)  oracle -
  abstract     src/backend/query_builder.rs:225  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:227  hobbes src/backend/query_builder.rs:1691 (src/backend/query_builder.QueryBuilder.prepare_window_statement)  oracle -
  abstract     src/backend/query_builder.rs:248  hobbes src/backend/query_builder.rs:841 (src/backend/query_builder.QueryBuilder.prepare_with_clause)  oracle -
  abstract     src/backend/query_builder.rs:254  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:257  hobbes src/backend/query_builder.rs:289 (src/backend/query_builder.QueryBuilder.prepare_update_join)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:270  hobbes src/backend/query_builder.rs:310 (src/backend/query_builder.QueryBuilder.prepare_update_column)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:272  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:276  hobbes src/backend/query_builder.rs:293 (src/backend/query_builder.QueryBuilder.prepare_update_from)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:278  hobbes src/backend/query_builder.rs:1598 (src/backend/query_builder.QueryBuilder.prepare_output)  oracle -
  abstract     src/backend/query_builder.rs:28  hobbes src/backend/query_builder.rs:841 (src/backend/query_builder.QueryBuilder.prepare_with_clause)  oracle -
  abstract     src/backend/query_builder.rs:280  hobbes src/backend/query_builder.rs:320 (src/backend/query_builder.QueryBuilder.prepare_update_condition)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:282  hobbes src/backend/query_builder.rs:330 (src/backend/query_builder.QueryBuilder.prepare_update_order_by)  oracle -
  abstract     src/backend/query_builder.rs:284  hobbes src/backend/query_builder.rs:348 (src/backend/query_builder.QueryBuilder.prepare_update_limit)  oracle -
  abstract     src/backend/query_builder.rs:286  hobbes src/backend/query_builder.rs:1602 (src/backend/query_builder.QueryBuilder.prepare_returning)  oracle -
  abstract     src/backend/query_builder.rs:305  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:31  hobbes src/backend/query_builder.rs:969 (src/backend/query_builder.QueryBuilder.prepare_insert)  oracle -
  abstract     src/backend/query_builder.rs:317  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:326  hobbes src/backend/query_builder.rs:1639 (src/backend/query_builder.QueryBuilder.prepare_condition)  oracle -
  abstract     src/backend/query_builder.rs:342  hobbes src/backend/query_builder.rs:1024 (src/backend/query_builder.QueryBuilder.prepare_order_expr)  oracle -
  abstract     src/backend/query_builder.rs:358  hobbes src/backend/query_builder.rs:841 (src/backend/query_builder.QueryBuilder.prepare_with_clause)  oracle -
  abstract     src/backend/query_builder.rs:36  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:365  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:368  hobbes src/backend/query_builder.rs:1598 (src/backend/query_builder.QueryBuilder.prepare_output)  oracle -
  abstract     src/backend/query_builder.rs:370  hobbes src/backend/query_builder.rs:1639 (src/backend/query_builder.QueryBuilder.prepare_condition)  oracle -
  abstract     src/backend/query_builder.rs:372  hobbes src/backend/query_builder.rs:380 (src/backend/query_builder.QueryBuilder.prepare_delete_order_by)  oracle -
  abstract     src/backend/query_builder.rs:374  hobbes src/backend/query_builder.rs:398 (src/backend/query_builder.QueryBuilder.prepare_delete_limit)  oracle -
  abstract     src/backend/query_builder.rs:376  hobbes src/backend/query_builder.rs:1602 (src/backend/query_builder.QueryBuilder.prepare_returning)  oracle -
  abstract     src/backend/query_builder.rs:392  hobbes src/backend/query_builder.rs:1024 (src/backend/query_builder.QueryBuilder.prepare_order_expr)  oracle -
  abstract     src/backend/query_builder.rs:407  hobbes src/backend/query_builder.rs:410 (src/backend/query_builder.QueryBuilder.prepare_expr_common)  oracle -
  abstract     src/backend/query_builder.rs:413  hobbes src/backend/query_builder.rs:655 (src/backend/query_builder.QueryBuilder.prepare_column_ref)  oracle -
  abstract     src/backend/query_builder.rs:416  hobbes src/backend/query_builder.rs:1142 (src/backend/query_builder.QueryBuilder.prepare_tuple)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:419  hobbes src/backend/query_builder.rs:675 (src/backend/query_builder.QueryBuilder.prepare_un_oper)  oracle -
  abstract     src/backend/query_builder.rs:426  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:43  hobbes src/backend/query_builder.rs:1598 (src/backend/query_builder.QueryBuilder.prepare_output)  oracle -
  abstract     src/backend/query_builder.rs:432  hobbes src/backend/query_builder.rs:977 (src/backend/query_builder.QueryBuilder.prepare_function_name)  oracle -
  abstract     src/backend/query_builder.rs:433  hobbes src/backend/query_builder.rs:800 (src/backend/query_builder.QueryBuilder.prepare_function_arguments)  oracle -
  abstract     src/backend/query_builder.rs:437  hobbes src/backend/query_builder.rs:1740 (src/backend/query_builder.QueryBuilder.binary_expr)  oracle :0 (<T as std::convert::Into<U>>::into), :0 (<T as std::convert::Into<U>>::into)
  abstract     src/backend/query_builder.rs:440  hobbes src/backend/query_builder.rs:1740 (src/backend/query_builder.QueryBuilder.binary_expr)  oracle :0 (<T as std::convert::Into<U>>::into), :0 (<T as std::convert::Into<U>>::into)
  abstract     src/backend/query_builder.rs:442  hobbes src/backend/query_builder.rs:1740 (src/backend/query_builder.QueryBuilder.binary_expr)  oracle -
  abstract     src/backend/query_builder.rs:446  hobbes src/backend/query_builder.rs:724 (src/backend/query_builder.QueryBuilder.prepare_sub_query_oper)  oracle -
  abstract     src/backend/query_builder.rs:46  hobbes src/backend/query_builder.rs:1858 (src/backend/query_builder.QueryBuilder.insert_default_values)  oracle -
  abstract     src/backend/query_builder.rs:474  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/backend/query_builder.rs:489  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Index<I>>::index)
  abstract     src/backend/query_builder.rs:494  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Index<I>>::index)
  abstract     src/backend/query_builder.rs:503  hobbes src/backend/query_builder.rs:1154 (src/backend/query_builder.QueryBuilder.prepare_keyword)  oracle -
  abstract     src/backend/query_builder.rs:506  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:509  hobbes src/backend/query_builder.rs:521 (src/backend/query_builder.QueryBuilder.prepare_case_statement)  oracle -
  abstract     src/backend/query_builder.rs:512  hobbes src/backend/query_builder.rs:1077 (src/backend/query_builder.QueryBuilder.prepare_constant)  oracle -
  abstract     src/backend/query_builder.rs:515  hobbes src/backend/query_builder.rs:982 (src/backend/query_builder.QueryBuilder.prepare_type_ref)  oracle -
  abstract     src/backend/query_builder.rs:528  hobbes src/backend/query_builder.rs:1666 (src/backend/query_builder.QueryBuilder.prepare_condition_where)  oracle -
  abstract     src/backend/query_builder.rs:531  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:535  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:564  hobbes src/backend/query_builder.rs:1843 (src/backend/query_builder.QueryBuilder.lock_phrase)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/backend/query_builder.rs:57  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:576  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:590  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:594  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:599  hobbes src/backend/query_builder.rs:1691 (src/backend/query_builder.QueryBuilder.prepare_window_statement)  oracle -
  abstract     src/backend/query_builder.rs:607  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:613  hobbes src/backend/query_builder.rs:1006 (src/backend/query_builder.QueryBuilder.prepare_join_type)  oracle -
  abstract     src/backend/query_builder.rs:615  hobbes src/backend/query_builder.rs:621 (src/backend/query_builder.QueryBuilder.prepare_join_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:617  hobbes src/backend/query_builder.rs:1032 (src/backend/query_builder.QueryBuilder.prepare_join_on)  oracle -
  abstract     src/backend/query_builder.rs:625  hobbes src/backend/query_builder.rs:629 (src/backend/query_builder.QueryBuilder.prepare_table_ref)  oracle -
  abstract     src/backend/query_builder.rs:63  hobbes src/backend/query_builder.rs:1598 (src/backend/query_builder.QueryBuilder.prepare_output)  oracle -
  abstract     src/backend/query_builder.rs:633  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle -
  abstract     src/backend/query_builder.rs:636  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:640  hobbes src/backend/query_builder.rs:1082 (src/backend/query_builder.QueryBuilder.prepare_values_list)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:643  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:646  hobbes src/backend/query_builder.rs:977 (src/backend/query_builder.QueryBuilder.prepare_function_name)  oracle -
  abstract     src/backend/query_builder.rs:647  hobbes src/backend/query_builder.rs:800 (src/backend/query_builder.QueryBuilder.prepare_function_arguments)  oracle -
  abstract     src/backend/query_builder.rs:649  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:651  hobbes src/backend/table_ref_builder.rs:5 (src/backend/table_ref_builder.TableRefBuilder.prepare_table_ref_iden)  oracle -
  abstract     src/backend/query_builder.rs:659  hobbes src/backend/table_ref_builder.rs:20 (src/backend/table_ref_builder.TableRefBuilder.prepare_table_name)  oracle -
  abstract     src/backend/query_builder.rs:662  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:666  hobbes src/backend/table_ref_builder.rs:20 (src/backend/table_ref_builder.TableRefBuilder.prepare_table_name)  oracle -
  abstract     src/backend/query_builder.rs:720  hobbes src/backend/query_builder.rs:682 (src/backend/query_builder.QueryBuilder.prepare_bin_oper_common)  oracle -
  abstract     src/backend/query_builder.rs:761  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:780  hobbes src/backend/query_builder.rs:1812 (src/backend/query_builder.QueryBuilder.if_null_function)  oracle -
  abstract     src/backend/query_builder.rs:781  hobbes src/backend/query_builder.rs:1818 (src/backend/query_builder.QueryBuilder.greatest_function)  oracle -
  abstract     src/backend/query_builder.rs:782  hobbes src/backend/query_builder.rs:1824 (src/backend/query_builder.QueryBuilder.least_function)  oracle -
  abstract     src/backend/query_builder.rs:783  hobbes src/backend/query_builder.rs:1830 (src/backend/query_builder.QueryBuilder.char_length_function)  oracle -
  abstract     src/backend/query_builder.rs:790  hobbes src/backend/query_builder.rs:1836 (src/backend/query_builder.QueryBuilder.random_function)  oracle -
  abstract     src/backend/query_builder.rs:808  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:816  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:823  hobbes src/backend/query_builder.rs:1666 (src/backend/query_builder.QueryBuilder.prepare_condition_where)  oracle -
  abstract     src/backend/query_builder.rs:837  hobbes src/backend/query_builder.rs:841 (src/backend/query_builder.QueryBuilder.prepare_with_clause)  oracle -
  abstract     src/backend/query_builder.rs:842  hobbes src/backend/query_builder.rs:961 (src/backend/query_builder.QueryBuilder.prepare_with_clause_start)  oracle -
  abstract     src/backend/query_builder.rs:843  hobbes src/backend/query_builder.rs:886 (src/backend/query_builder.QueryBuilder.prepare_with_clause_common_tables)  oracle -
  abstract     src/backend/query_builder.rs:845  hobbes src/backend/query_builder.rs:849 (src/backend/query_builder.QueryBuilder.prepare_with_clause_recursive_options)  oracle -
  abstract     src/backend/query_builder.rs:864  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap)
  abstract     src/backend/query_builder.rs:868  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap), :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap)
  abstract     src/backend/query_builder.rs:87  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/query_builder.rs:874  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap)
  abstract     src/backend/query_builder.rs:878  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap)
  abstract     src/backend/query_builder.rs:880  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap)
  abstract     src/backend/query_builder.rs:904  hobbes src/backend/query_builder.rs:908 (src/backend/query_builder.QueryBuilder.prepare_with_query_clause_common_table)  oracle -
  abstract     src/backend/query_builder.rs:913  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle :0 (std::option::Option::<T>::as_ref), :0 (std::option::Option::<T>::unwrap)
  abstract     src/backend/query_builder.rs:926  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:934  hobbes src/backend/query_builder.rs:946 (src/backend/query_builder.QueryBuilder.prepare_with_query_clause_materialization)  oracle -
  abstract     src/backend/query_builder.rs:940  hobbes src/backend/query_builder.rs:1112 (src/backend/query_builder.QueryBuilder.prepare_values_rows)  oracle :0 (<std::vec::Vec<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:96  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle :0 (<std::boxed::Box<T, A> as std::ops::Deref>::deref)
  abstract     src/backend/query_builder.rs:978  hobbes src/backend/query_builder.rs:768 (src/backend/query_builder.QueryBuilder.prepare_function_name_common)  oracle -
  abstract     src/backend/query_builder.rs:985  hobbes src/backend/table_ref_builder.rs:30 (src/backend/table_ref_builder.TableRefBuilder.prepare_schema_name)  oracle -
  abstract     src/backend/query_builder.rs:995  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/query_builder.rs:998  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/table_builder.rs:111  hobbes src/backend/table_ref_builder.rs:5 (src/backend/table_ref_builder.TableRefBuilder.prepare_table_ref_iden)  oracle -
  abstract     src/backend/table_builder.rs:14  hobbes src/backend/table_builder.rs:341 (src/backend/table_builder.TableBuilder.prepare_create_temporary_table)  oracle -
  abstract     src/backend/table_builder.rs:164  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/table_builder.rs:168  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/table_builder.rs:175  hobbes src/backend/table_builder.rs:318 (src/backend/table_builder.TableBuilder.prepare_generated_column)  oracle -
  abstract     src/backend/table_builder.rs:18  hobbes src/backend/table_builder.rs:330 (src/backend/table_builder.TableBuilder.prepare_create_table_if_not_exists)  oracle -
  abstract     src/backend/table_builder.rs:193  hobbes src/backend/table_builder.rs:305 (src/backend/table_builder.TableBuilder.prepare_check_constraint)  oracle -
  abstract     src/backend/table_builder.rs:202  hobbes src/backend/table_builder.rs:207 (src/backend/table_builder.TableBuilder.column_comment)  oracle :0 (<std::string::String as std::ops::Deref>::deref)
  abstract     src/backend/table_builder.rs:21  hobbes src/backend/table_builder.rs:108 (src/backend/table_builder.TableBuilder.prepare_table_ref_table_stmt)  oracle -
  abstract     src/backend/table_builder.rs:214  hobbes src/backend/table_builder.rs:218 (src/backend/table_builder.TableBuilder.prepare_table_opt_def)  oracle -
  abstract     src/backend/table_builder.rs:26  hobbes src/backend/table_builder.rs:108 (src/backend/table_builder.TableBuilder.prepare_table_ref_table_stmt)  oracle -
  abstract     src/backend/table_builder.rs:274  hobbes src/backend/table_builder.rs:108 (src/backend/table_builder.TableBuilder.prepare_table_ref_table_stmt)  oracle -
  abstract     src/backend/table_builder.rs:279  hobbes src/backend/table_builder.rs:284 (src/backend/table_builder.TableBuilder.prepare_table_drop_opt)  oracle -
  abstract     src/backend/table_builder.rs:300  hobbes src/backend/table_builder.rs:108 (src/backend/table_builder.TableBuilder.prepare_table_ref_table_stmt)  oracle -
  abstract     src/backend/table_builder.rs:308  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/table_builder.rs:313  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/table_builder.rs:320  hobbes src/backend/query_builder.rs:406 (src/backend/query_builder.QueryBuilder.prepare_expr)  oracle -
  abstract     src/backend/table_builder.rs:49  hobbes src/backend/index_builder.rs:7 (src/backend/index_builder.IndexBuilder.prepare_table_index_expression)  oracle -
  abstract     src/backend/table_builder.rs:69  hobbes src/backend/table_builder.rs:305 (src/backend/table_builder.TableBuilder.prepare_check_constraint)  oracle -
  abstract     src/backend/table_builder.rs:78  hobbes src/backend/table_builder.rs:242 (src/backend/table_builder.TableBuilder.prepare_partition_values)  oracle -
  abstract     src/backend/table_builder.rs:83  hobbes src/backend/table_builder.rs:239 (src/backend/table_builder.TableBuilder.prepare_partition_by)  oracle -
  abstract     src/backend/table_builder.rs:93  hobbes src/backend/table_builder.rs:250 (src/backend/table_builder.TableBuilder.prepare_partition_definition)  oracle :0 (std::option::Option::<T>::as_ref)
  abstract     src/backend/table_builder.rs:99  hobbes src/backend/table_builder.rs:213 (src/backend/table_builder.TableBuilder.prepare_table_opt)  oracle -
  abstract     src/backend/table_ref_builder.rs:12  hobbes src/backend/table_ref_builder.rs:20 (src/backend/table_ref_builder.TableRefBuilder.prepare_table_name)  oracle -
  abstract     src/backend/table_ref_builder.rs:15  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/table_ref_builder.rs:23  hobbes src/backend/table_ref_builder.rs:30 (src/backend/table_ref_builder.TableRefBuilder.prepare_schema_name)  oracle -
  abstract     src/backend/table_ref_builder.rs:26  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/table_ref_builder.rs:33  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/backend/table_ref_builder.rs:36  hobbes src/backend/mod.rs:44 (src/backend/mod.QuotedBuilder.prepare_iden)  oracle -
  abstract     src/expr/trait.rs:546  hobbes src/value/value_tuple.rs:19 (src/value/value_tuple.IntoValueTuple.into_value_tuple)  oracle src/value/value_tuple.rs:43 (<value::value_tuple::ValueTuple as std::iter::IntoIterator>::into_iter), :0 (std::iter::Iterator::collect)
  abstract     src/extension/mysql/explain.rs:28  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/extension/mysql/select.rs:125  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/extension/mysql/select.rs:199  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/extension/mysql/select.rs:273  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/extension/postgres/expr.rs:44  hobbes src/extension/postgres/expr.rs:32 (src/extension/postgres/expr.PgExpr.concatenate)  oracle -
  abstract     src/foreign_key/common.rs:60  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/foreign_key/common.rs:69  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/foreign_key/create.rs:181  hobbes src/backend/foreign_key_builder.rs:13 (src/backend/foreign_key_builder.ForeignKeyBuilder.prepare_foreign_key_create_statement)  oracle -
  abstract     src/foreign_key/drop.rs:51  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/foreign_key/drop.rs:62  hobbes src/backend/foreign_key_builder.rs:22 (src/backend/foreign_key_builder.ForeignKeyBuilder.prepare_foreign_key_drop_statement)  oracle -
  abstract     src/index/create.rs:269  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/index/create.rs:390  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/index/drop.rs:56  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/prepare.rs:102  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/prepare.rs:121  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle -
  abstract     src/prepare.rs:137  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle -
  abstract     src/prepare.rs:149  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle -
  abstract     src/prepare.rs:15  hobbes src/backend/query_builder.rs:1177 (src/backend/query_builder.QueryBuilder.write_value)  oracle :0 (std::result::Result::<T, E>::unwrap)
  abstract     src/query/case.rs:76  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle -
  abstract     src/query/condition.rs:456  hobbes src/query/condition.rs:432 (src/query/condition.ConditionalStatement.and_where)  oracle -
  abstract     src/query/delete.rs:100  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle :0 (std::boxed::Box::<T>::new)
  abstract     src/query/delete.rs:315  hobbes src/backend/query_builder.rs:356 (src/backend/query_builder.QueryBuilder.prepare_delete_statement)  oracle -
  abstract     src/query/delete.rs:355  hobbes src/backend/query_builder.rs:356 (src/backend/query_builder.QueryBuilder.prepare_delete_statement)  oracle -
  abstract     src/query/delete.rs:471  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/query/explain.rs:249  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/query/explain.rs:256  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/query/explain.rs:263  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/query/explain.rs:328  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/query/explain.rs:65  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle -
  abstract     src/query/explain.rs:66  hobbes src/backend/query_builder.rs:21 (src/backend/query_builder.QueryBuilder.prepare_insert_statement)  oracle -
  abstract     src/query/explain.rs:67  hobbes src/backend/query_builder.rs:246 (src/backend/query_builder.QueryBuilder.prepare_update_statement)  oracle -
  abstract     src/query/explain.rs:68  hobbes src/backend/query_builder.rs:356 (src/backend/query_builder.QueryBuilder.prepare_delete_statement)  oracle -
  abstract     src/query/insert.rs:119  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle :0 (std::boxed::Box::<T>::new)
  abstract     src/query/insert.rs:762  hobbes src/backend/query_builder.rs:21 (src/backend/query_builder.QueryBuilder.prepare_insert_statement)  oracle -
  abstract     src/query/insert.rs:802  hobbes src/backend/query_builder.rs:21 (src/backend/query_builder.QueryBuilder.prepare_insert_statement)  oracle -
  abstract     src/query/on_conflict.rs:516  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/query/on_conflict.rs:572  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/query/select.rs:1081  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle src/query/select.rs:1291 (query::select::SelectStatement::from_from)
  abstract     src/query/select.rs:1119  hobbes src/value/value_tuple.rs:19 (src/value/value_tuple.IntoValueTuple.into_value_tuple)  oracle -
  abstract     src/query/select.rs:1181  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle src/query/select.rs:1291 (query::select::SelectStatement::from_from), src/types/iden/compound.rs:204 (types::iden::compound::TableRef::alias)
  abstract     src/query/select.rs:1331  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle src/query/select.rs:1928 (query::select::SelectStatement::push_join)
  abstract     src/query/select.rs:1698  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:649 (query::condition::ConditionHolder::new_with_condition)
  abstract     src/query/select.rs:1701  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle src/query/select.rs:1928 (query::select::SelectStatement::push_join)
  abstract     src/query/select.rs:1771  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:649 (query::condition::ConditionHolder::new_with_condition)
  abstract     src/query/select.rs:1776  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle src/types/iden/compound.rs:204 (types::iden::compound::TableRef::alias)
  abstract     src/query/select.rs:1853  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle -
  abstract     src/query/select.rs:1922  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle -
  abstract     src/query/select.rs:2142  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/query/select.rs:2359  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle :0 (std::iter::Iterator::collect)
  abstract     src/query/select.rs:2440  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle :0 (std::iter::Iterator::collect)
  abstract     src/query/select.rs:2776  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle -
  abstract     src/query/select.rs:2816  hobbes src/backend/query_builder.rs:124 (src/backend/query_builder.QueryBuilder.prepare_select_statement)  oracle -
  abstract     src/query/select.rs:2932  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/query/traits.rs:8  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/query/traits.rs:84  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/query/update.rs:128  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle src/query/update.rs:132 (query::update::UpdateStatement::from_from)
  abstract     src/query/update.rs:459  hobbes src/backend/query_builder.rs:246 (src/backend/query_builder.QueryBuilder.prepare_update_statement)  oracle -
  abstract     src/query/update.rs:499  hobbes src/backend/query_builder.rs:246 (src/backend/query_builder.QueryBuilder.prepare_update_statement)  oracle -
  abstract     src/query/update.rs:615  hobbes src/query/condition.rs:44 (src/query/condition.IntoCondition.into_condition)  oracle src/query/condition.rs:682 (query::condition::ConditionHolder::add_condition)
  abstract     src/query/update.rs:77  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle :0 (std::boxed::Box::<T>::new)
  abstract     src/query/with.rs:599  hobbes src/backend/query_builder.rs:836 (src/backend/query_builder.QueryBuilder.prepare_with_query)  oracle -
  abstract     src/query/with.rs:611  hobbes src/backend/query_builder.rs:836 (src/backend/query_builder.QueryBuilder.prepare_with_query)  oracle -
  abstract     src/raw_sql.rs:15  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/table/alter.rs:76  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/table/create.rs:147  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/table/create.rs:429  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/table/create.rs:711  hobbes src/backend/table_builder.rs:7 (src/backend/table_builder.TableBuilder.prepare_table_create_statement)  oracle -
  abstract     src/table/drop.rs:54  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle :0 (std::vec::Vec::<T, A>::push)
  abstract     src/table/drop.rs:88  hobbes src/backend/table_builder.rs:259 (src/backend/table_builder.TableBuilder.prepare_table_drop_statement)  oracle -
  abstract     src/table/rename.rs:43  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/table/rename.rs:44  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/table/truncate.rs:38  hobbes src/types/iden/compound.rs:247 (src/types/iden/compound.IntoTableRef.into_table_ref)  oracle -
  abstract     src/table/truncate.rs:52  hobbes src/backend/table_builder.rs:292 (src/backend/table_builder.TableBuilder.prepare_table_truncate_statement)  oracle -
  abstract     src/token.rs:35  hobbes src/backend/query_builder.rs:11 (src/backend/query_builder.QueryBuilder.placeholder)  oracle -
  abstract     src/types/iden/core.rs:112  hobbes src/types/iden/core.rs:18 (src/types/iden/core.Iden.quoted)  oracle -
  abstract     src/types/iden/core.rs:19  hobbes src/types/iden/core.rs:29 (src/types/iden/core.Iden.to_string)  oracle -
  abstract     src/types/mod.rs:52  hobbes src/types/iden/core.rs:18 (src/types/iden/core.Iden.quoted)  oracle -
  abstract     src/value.rs:379  hobbes src/value.rs:965 (src/value.ValueType.unwrap)  oracle -
  abstract     src/value.rs:386  hobbes src/value.rs:969 (src/value.ValueType.expect)  oracle -
  abstract     src/value/value_tuple.rs:160  hobbes src/value/value_tuple.rs:19 (src/value/value_tuple.IntoValueTuple.into_value_tuple)  oracle -
  abstract     src/value/value_tuple.rs:176  hobbes src/value/value_tuple.rs:19 (src/value/value_tuple.IntoValueTuple.into_value_tuple)  oracle -
  abstract     src/value/value_tuple.rs:193  hobbes src/value/value_tuple.rs:19 (src/value/value_tuple.IntoValueTuple.into_value_tuple)  oracle -
poison check: PASS — 6885 seeded wrong edges: 6123 refused, 762 unjudged (oracle silent there), 0 falsely confirmed
```
