# Oracle cell — BurntSushi/memchr, package `.`, 2026-08-27

Repo: https://github.com/BurntSushi/memchr (Unlicense OR MIT), clone at `~/.hobbes/bench/oracle/repos/memchr`, commit bd6068c30e9074a90c285e47912fa0b047d07597 (shallow, v2.8.3). Picked because it is a well-known, mid-popularity, `no_std`-capable Rust library of ~15.9k lines under `src/` in one cargo package (one dev-dependency, `quickcheck`), heavy on `cfg`-gated arch modules and `macro_rules!` test generators, and it checks cleanly on the pinned nightly with `cargo +nightly check --all-targets`. The clone also carries `benchmarks/engines/*`, `benchmarks/shared` and `fuzz/` — separate cargo roots outside the package (see Silent). Ingest SHA bd6068c3 (the ingest reports a dirty tree: `hobbes ingest` appends `.hobbes/` to the clone's `.gitignore`, ADR-012 — nothing else changed). Hobbes at a0ba230, edges from `.hobbes/derived/graph.json` (lane B on, `HOBBES_SCIP=1`, rust-analyzer `scip`; the ingest warned that SCIP failed for each of the eight `benchmarks/engines/*` roots and for `fuzz/` — those roots fell to lane A's syntactic tier). Oracle `rustc-mir` on rustc 1.100.0-nightly (e7769602a 2026-08-24) via `cargo check --all-targets`, 2 crate targets (`memchr lib`, `memchr (test)`), no roots (resolution oracle).

Command: `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/memchr . ~/.hobbes/bench/oracle/memchr-rust --lang rust`. Runtime 13 s (ingest + MIR walk + grade). Outputs in `~/.hobbes/bench/oracle/memchr-rust/` (`hobbes.json`, `oracle.json`, `report.json`, `report.txt`, `mir-sites/`).

## Numbers (report.txt, verbatim; the 221 `missed` rows elided)

```
cell   oracle rustc-mir rustc 1.100.0-nightly (e7769602a 2026-08-24) (resolution)  sha bd6068c3
hobbes edges 2623: confirmed 921  contradicted 7  abstract 0  silent 1695 map[not-loaded:1629 unreachable:66]
precision-against-oracle 99.2% (921/928)
recall 80.7% (925/1146 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 1476; misses map[macro→function:57 macro→method:42 static→closure:1 static→function:53 static→generated:5 static→method:63]
  recall[macro→function    ]   0.0% (0/57)  misses 57 = 25.8% of all misses
  recall[macro→method      ]   0.0% (0/42)  misses 42 = 19.0% of all misses
  recall[static→closure    ]   0.0% (0/1)  misses 1 = 0.5% of all misses
  recall[static→function   ]  75.8% (166/219)  misses 53 = 24.0% of all misses
  recall[static→generated  ]   0.0% (0/5)  misses 5 = 2.3% of all misses
  recall[static→method     ]  92.3% (759/822)  misses 63 = 28.5% of all misses
  tier semantic   confirmed 914  contradicted 7  abstract 0  silent 55
  tier syntactic  confirmed 7  contradicted 0  abstract 0  silent 1640
  line-grain tolerance used on 415 edge(s) (several oracle sites on one line)
poison check: PASS — 2623 seeded wrong edges: 928 refused, 1695 unjudged (oracle silent there), 0 falsely confirmed
cell . of /home/mmarrujo/.hobbes/bench/oracle/repos/memchr: 13s
```

| bucket | count |
|---|---|
| hobbes edges | 2623 |
| confirmed | 921 |
| contradicted | 7 |
| silent | 1695 (not-loaded 1629, unreachable 66) |
| precision-against-oracle | 99.2% (921/928) |
| in-repo oracle pairs | 1146 |
| recall (no roots; every resolved site) | 80.7% (925/1146) |
| external oracle pairs (not graded) | 1476 |
| tiers | semantic 914 / 7 / 55; syntactic 7 / 0 / 1640 |

## Contradicted (7, all semantic tier, lane `scip`)

Every one is a Hobbes `calls` edge whose target is a **tuple-struct type** at a constructor expression, where the compiler's only call on that line is the call inside the constructor's argument: `sse2/memchr.rs:64,440,741` `One/Two/Three::new_unchecked -> One/Two/Three` (oracle: `arch::generic::memchr::One/Two/Three::<V>::new`), `rabinkarp.rs:186` `FinderRev::new -> FinderRev` (oracle: `Hash::new`), `cow.rs:40` `CowBytes::new -> CowBytes` (oracle: `Imp::new`), `vector.rs:246,299` `movemask -> SensibleMoveMask` (oracle: external `_mm_movemask_epi8` / `_mm256_movemask_epi8`).

## Misses by class (221 rows, all in report.txt / report.json)

- **macro→function, 57 (25.8%) and macro→method, 42 (19.0%).** All 99 at 12 sites, each a `define_*_quickcheck!` invocation in a `#[cfg(test)]` module (`arch/all/memchr.rs:901`, `avx2/memchr.rs:1280`, `sse2/memchr.rs:1005` — 24 targets each; `rabinkarp.rs:370,373`, `twoway.rs:711,714`, `shiftor.rs:81`, `avx2/packedpair.rs:227`, `sse2/packedpair.rs:190`, `memmem/mod.rs:749,750` — 3 each). The targets are the naive reference functions in `src/tests/memchr/naive.rs`, `src/tests/memchr/prop.rs`, `src/tests/substring/prop.rs` (functions) and the `One/Two/Three::{new,find,rfind,iter}` and `OneIter::next/size_hint` methods the macro body calls (methods).
- **static→method, 63 (28.5%).** 56 at the 7 `unsafe_ifunc!(...)` invocation lines in `src/arch/x86_64/memchr.rs` (`memchr_raw:180`, `memrchr_raw:203`, `memchr2_raw:227`, `memrchr2_raw:252`, `memchr3_raw:278`, `memrchr3_raw:305`, `count_raw:330`), 8 targets per site: the `avx2`, `sse2` and `all` variants' `is_available`, `new_unchecked` / `new`, and the `*_raw` method named as the macro argument. The other 7 are calls inside a closure written as a macro argument (`|h, n| Some(Finder::new(n).find(h))` at `rabinkarp.rs:371,374`, `shiftor.rs:81`, `twoway.rs:712,715`, `memmem/mod.rs:749,751` → `Finder::find` / `FinderRev::rfind`).
- **static→function, 53 (24.0%).** 50 in `src/arch/all/twoway.rs` tests `suffix_forward` / `suffix_reverse`: calls of `get_suffix_forward` (25) / `get_suffix_reverse` (23) and `naive_maximal_suffix_forward/reverse` (1 each) made by a function-local `macro_rules! assert_suffix_min/max` at each `assert_suffix_*!(...)` line (752–768 and the reverse block). 3 in `src/memchr.rs:899–901`: `assert_send_sync::<Memchr>()` etc. — a `fn` nested inside the test body called with a turbofish.
- **static→generated, 5 (2.3%).** Derived impls: `Hash as PartialEq::eq` (`rabinkarp.rs:166,264`, the `self.hash == hash` comparison), `Searcher/SearcherRev as Clone::clone` (`memmem/mod.rs:488,623`), `FinderBuilder as Default::default` (`memmem/mod.rs:652`).
- **static→closure, 1 (0.5%).** `twoway.rs:875`: `rfind(...)` on a locally bound closure in `regression_rev_small_period`.

**Silent (1695).** `not-loaded` 1629: 1583 are edges in cargo roots outside the graded package — `benchmarks/haystacks` 1442, `benchmarks/engines` 135, `benchmarks/shared` 4, `fuzz/fuzz_targets` 2 (1625 of the 1629 are syntactic-tier edges, the SCIP-failed roots above); the other 46 are `src/arch/aarch64/neon/*` (23) and `src/arch/wasm32/simd128/*` (23), `cfg`-gated off on this x86_64 host. `unreachable` 66 (51 semantic, 15 syntactic): `src/tests/substring/mod.rs` 37, `src/memmem/searcher.rs` 17, `src/vector.rs` 5, `twoway.rs` 3, `cow.rs` 2, `rabinkarp.rs` 1, `sse2/packedpair.rs` 1.

**Poison check:** PASS — 2623 seeded wrong edges: 928 refused, 1695 unjudged (oracle silent there), 0 falsely confirmed.

**Direction of fix (which side would need to change; no proposals):** `macro→function` / `macro→method` — Hobbes (calls made by a macro body at the invocation line; Hobbes has no edge there, the same class as rust_proj's `criterion_group!`). `static→method` (the 56 `unsafe_ifunc!` rows) and `static→function` (the 50 `assert_suffix_*!` rows) — Hobbes (calls made by a crate-local `macro_rules!` body at its invocation line, which the oracle attributes to the source call site; Hobbes emits nothing at those lines). `static→method` (7 closure-in-macro-argument rows), `static→function` (3 nested-fn turbofish rows), `static→closure` — Hobbes. `static→generated` — Hobbes (the target is a derived impl with no source identifier). Contradicted 7 — Hobbes if a tuple-struct constructor expression is not to be a `calls` edge to the type; otherwise the oracle (MIR lowers tuple-struct construction to an aggregate, not a call, so it carries no site for it). Silent `not-loaded` — neither: the benchmark/fuzz roots are outside the package and the neon/simd128 modules are outside this host's cfg; `unreachable` 66 — nothing to fix on either side.

**Not graded:** the 1476 external oracle pairs (std / `core::arch` / `quickcheck` callees, by design); the 1695 silent edges above. No repo was abandoned.
