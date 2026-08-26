# Oracle cell — dagger, `sdk/rust` (the SDK workspace), 2026-08-25 (O7)

Produced by `bench/oracle/run-cell.sh ~/dagger sdk/rust <out> --lang rust --no-ingest` against dagger's post-W1 graph (ingest f3cc3eb3, the same artifact O4's "after" cells graded); oracle `rustc-mir` on rustc 1.100.0-nightly (e7769602a 2026-08-24), `cargo check --all-targets` over the workspace's three crates (`dagger-sdk`, `dagger-codegen`, `dagger-bootstrap`) and their examples/tests — 15 crate targets, 47 source files loaded (the `examples/*` sub-workspaces are separate packages and not in the cell). Cell runtime **17 s**. The first pass, before H-16, reported 649 `static→closure` misses that were `.await`'s desugared `poll` reaching async-fn bodies; the report below is after that fix.

```
cell sdk/rust  oracle rustc-mir rustc 1.100.0-nightly (e7769602a 2026-08-24) (resolution)  sha f3cc3eb3
hobbes edges 3610: confirmed 3592  contradicted 12  abstract 0  silent 6 map[not-loaded:6]
precision-against-oracle 99.7% (3592/3604)
recall 98.1% (3593/3662 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 6191; misses map[static→function:14 static→generated:25 static→method:30]
  recall[static→function   ]  94.5% (239/253)  misses 14 = 20.3% of all misses
  recall[static→generated  ]   0.0% (0/25)  misses 25 = 36.2% of all misses
  recall[static→method     ]  99.1% (3354/3384)  misses 30 = 43.5% of all misses
  tier semantic   confirmed 3574  contradicted 0  abstract 0  silent 0
  tier syntactic  confirmed 18  contradicted 12  abstract 0  silent 6
  line-grain tolerance used on 1225 edge(s) (several oracle sites on one line)
  contradicted sdk/rust/crates/dagger-sdk/src/core/gql_client.rs:172  hobbes sdk/rust/crates/dagger-sdk/src/core/gql_client.rs:81 (sdk/rust/crates/dagger-sdk/src/core/gql_client.format)  oracle :0 (std::result::Result::<T, E>::map_err), sdk/rust/crates/dagger-sdk/src/core/gql_client.rs:54 (core::gql_client::GraphQLError::with_text), :0 (core::fmt::rt::Argument::<'_>::new_debug), :0 (std::fmt::Arguments::<'a>::new), :0 (std::fmt::format), :0 (std::hint::must_use)
  (12 contradicted rows: every one is the syntactic edge gql_client.rs:{172,212,278,309,314,324,342,357,359,369,373,381} → gql_client.rs:81 (fn format); 69 missed rows in report.json)
```

**After ADR-090 (same day, re-ingested):** 3,598 edges — **3,592 confirmed, 0 contradicted, 6 not-loaded; precision 100%**; recall unchanged. `report.before-w1.txt` beside the cell keeps the first grading.

**Direction of fix (ADR-090, signed):** hobbes edges 3,610 → 3,598 (−12: the twelve `format!`→`fn format` edges left the graph, not the bucket); confirmed 3,592 → 3,592 (0); contradicted 12 → 0 (−12); silent 6 → 6; precision 99.7% → 100% (+0.3); recall 3,593/3,662 → 3,593/3,662 (0). Earlier the same day, H-16 (harness): oracle pairs 4,426 → 3,662 (−764 `.await` poll sites), recall 83.8% → 98.1% (+14.3), `static→closure` misses 649 → 0.

**Poison check:** PASS — 3,598 seeded wrong edges: 3,592 refused, 6 unjudged (not-loaded), 0 falsely confirmed.

**Contradictions (12, before ADR-090), all syntactic, all hobbes-wrong, one cause.** `gql_client.rs` defines a `fn format(...)` at line 81; twelve `format!(...)` **macro invocations** in the same file were bound by lane A's fallback to that function. The compiler's calls on those lines are `core::fmt` and `GraphQLError::with_text`. The semantic tier is **3,574/3,574**. Syntactic tier overall: 18 confirmed, 12 contradicted, 6 not-loaded — the C-7 floor priced at 60% wrong on this crate.

**Misses (69).** `static→method` 30: calls of **extension-trait methods implemented on foreign types** (`impl InputValuesExt for Vec<&InputValue>` → `has_optionals`, ×3; `OptionExt::pipe` on `Option`, ×14; `LazyResolve as Deref`), methods **`derive_builder` generated** on `ConfigBuilder` (`logger`, `execute_timeout_ms`, `fallible_build`; ~7 — the identifier the derive copies from the field keeps a source span, so they class as methods, not generated), and 3 calls of the raw-identifier method `Query::r#ref`. `static→generated` 25: `x.clone()` on `#[derive(Clone)]` types — the target is the derived impl, which has no source identifier. `static→function` 14: calls written **inside a proc-macro's tokens** (`quote! { … $(format_name(..)) … }` in the codegen templates), where Hobbes has no site at all. No closure miss remains: every in-repo closure call the compiler resolves is either an async body behind `.await` (folded, H-16) or drawn.

**Silent (6).** `not-loaded`: syntactic edges in files the workspace build does not compile.

**Excluded.** 20,561 oracle sites in compiler-written code (the test harness, `#[tokio::test]`, derives, `.await` desugaring) — dropped before grading, per the README's Rust conventions. Hobbes: 0 macro edges in this cell's export.
