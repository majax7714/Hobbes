# ADR-040 — Rust support: the P7 proof, and what it cost

**Status:** accepted (2026-08-15)

**Milestone:** V2.M7. Amends the architecture's **§3.1** (a fifth syntax
provider), **§3.2** (a fourth indexer, and two new inherited limits),
**§3.7** (a fifth worked example), and **§7** (the status table). Amends
**C-9** (the descriptor filter admits a fifth kind). Registers **C-28**,
**C-29**, **C-30**. Evidence is reproducible via `scip/spike-rust.mjs`.

## Context

V2.M7's exit criterion is P7's proof: *a Rust repo ingests with zero new
builder code — a language nobody planned for, on the checklist ADR-037
corrected.* Rust is the first language added since §3.7 gained its
mandatory third step, so it is also the first test of whether that
correction was complete.

The spike ran `rust-analyzer scip` (1.97.1, the rustup component) over a
copy of `~/rust_proj` — a small cargo crate with a renamed lib target, a
second binary, `mod`-mapped files, a `#[path]` attribute, multi-file
integration tests, examples, and criterion benches. Small, but it
exercises exactly the module-system corners that make Rust Rust.

## What the spike found

**1. `syntax_kind` is unset for 100% of 169 occurrences.** scip-python:
0 of 8,575. scip-go: 0 of 18,682. rust-analyzer: 0 of 169. Three
independent implementations, the same omission — ADR-037's "assume the
next one does too" is now measured rather than assumed, and §3.7's
mandatory syntax provider stands confirmed a third time.

**2. The moniker version is the crate's `Cargo.toml` version, not the git
revision.** `0.1.0` for the local crate, crates.io versions for
dependencies, rust-lang/rust URLs for the sysroot crates. rust-analyzer
has no version flag and, for once, needs none: Decision 1 (ADR-027) is
satisfied by the provider's own default. The `INDEXERS` entry passes no
pin, with a comment saying why the omission is deliberate.

**3. Duplicate monikers across cargo targets.** A package's lib target,
binary targets, and same-named `#[cfg(test)] mod tests` blocks each emit
`crate/`, `main().`, `tests/` under one moniker — rust-analyzer prints its
own "Duplicate symbol" warnings while doing it. `decode()`'s first-wins
map would attribute a test's `use mylib` to whichever target decoded
first: a **false module edge**, and false edges are worse than missing
ones (ADR-007). Decision below; registered as **C-28**.

**4. Macros classify as `other` and vanish.** SCIP's macro descriptor
suffix is `!` (`macros/println!`), which `classify()` did not know, so a
repo-defined `macro_rules!` never entered the definitions map and every
invocation of it fell to `external_refs` attributed to the repo's own
crate. Rust without macros is not Rust. Decision below; amends **C-9**.

**5. tree-sitter does not parse macro arguments.** The Rust grammar
leaves everything between `!` and `;` as a `token_tree` — so
`assert_eq!(add(1, 2), 3)` contains no `call_expression`, and a naive
walk sees no call to `add`. Nearly every Rust test asserts through
macros; without a countermeasure, Rust test reach is empty and the lane
exists for nothing. rust-analyzer, meanwhile, **expands** macros and
emits the `add` occurrence at its real pre-expansion position (measured:
line and column match the source text). Decision below.

**6. Indexing executes repo code.** `rust-analyzer scip` runs cargo's
loader with build-script and proc-macro support: it compiled build
scripts into `target/` inside the stage (72 MB on the spike repo) and
fetched crate sources into the user-global `~/.cargo/registry` (51 MB,
network on first run). All writes stayed in the stage and the registry;
the original repo was untouched (verified). But the posture fact stands:
**ingesting a Rust repo executes that repo's `build.rs` and proc macros
on the host** — no other lane B provider executes repo-authored code.
Registered as **C-29**; the network need as **C-30**.

**7. No out-of-repo documents.** The scip-go build-cache leak (ADR-037
finding 5) does not reproduce; `insideRepo` guards anyway.

## Decisions

**1. The indexer is rust-analyzer's native SCIP export, run as shipped.**
`INDEXERS.rust` = `rust-analyzer scip <stage> --output …`, `onPath`,
installed via `rustup component add rust-analyzer`, pinned by the
toolchain (1.97.1 at time of writing). Hobbes writes no adapter and
passes no config — running the indexer as its ecosystem runs it is the
§3.2 trade, and its costs are owned under P9 (C-28/29/30).

**2. Ambiguous definitions are dropped, not guessed (C-28).** A moniker
DEF'd in more than one document is removed from the definitions map; its
references fall to `external_refs` (unattributed), and `degradations()`
reports the count and sample symbols, which lands in
`extraction_errors`. The rule is language-neutral — for every other
provider, monikers embed enough path to make cross-file duplicates a bug
this rule can only make safer — and the dogfood + kbet re-ingests were
byte-compared to prove the change moves nothing outside Rust.

**3. `macro` is the fifth graph kind.** `classify()` maps the `!` suffix
to `macro`, `GRAPH_KINDS` admits it, `terminalName` strips the bang so
the two lanes speak the same name. Only rust-analyzer emits the
descriptor today; the other providers cannot be affected. C-9's "four
kinds" becomes five.

**4. Lane A finds call sites inside token trees.** `rustsource.py` walks
`call_expression` nodes as every provider does, records
`macro_invocation` names as call sites (an invocation is where the
repo's control flow meets the macro — the C-24 posture), and inside
macro token trees applies **call-shape detection**: an identifier token
immediately followed by a parenthesized `token_tree` is a call site at
that identifier. This is syntax-level honesty, not resolution — a
false-shaped site produces no edge unless a resolution or fallback lands
on exactly that (file, line, name), so noise dies in the join. Measured
against finding 5: the SCIP occurrence for a macro-arg call carries the
same line and column the token walk sees.

**5. Rust's in-repo imports follow the Go rule.** A `use` names an item
path, not a file, so lane A emits `ext:` import edges only for crates
that are not the repo's own (local crate names read from `Cargo.toml` —
package name, hyphens underscored, plus `[lib] name`), and in-repo
module edges are raised by the join from what calls actually reach.
Rust nodes join Go's in the lane-agreement exclusion
(`lane_b_only_modules`) for the same reason, counted the same way.

**6. The fallback resolver uses the module system's own file mapping.**
Rust is like Go in tractability: `mod x;` maps to `x.rs` or `x/mod.rs`
(or the `#[path]` attribute's target) by fixed rules, `use` paths alias
items per file, and a crate name maps to its lib target. The fallback
resolves qualified paths segment-wise through that mapping, unqualified
names within the file, and `Type::assoc` through the type's file — and
gives up on anything else (glob re-exports, `super::` chains, method
calls on values), because under-approximation is the fallback's contract
(ADR-031).

**7. Test inventory is `#[test]`-family attributes, framework
`cargo-test`.** An attribute path that is or ends in `test`
(`#[test]`, `#[tokio::test]`) marks the function; reach is the closure
over `calls` edges, same as every framework. Criterion benches are
framework knowledge — a registration macro, not an attribute — which is
pack territory (§3.5), parked in `future_additions.md`, not silently
half-done here.

**8. Staging: sources + every manifest on the path + `Cargo.lock` +
`.cargo/config.toml`.** Files group by nearest `Cargo.toml` and collapse
to the nearest `[workspace]` manifest above them, one index run per
workspace root (the go.mod/tsconfig lesson, third spelling). Orphan
`.rs` files under no manifest are skipped and reported (the C-26
pattern). The dependency tree needs no symlink: cargo's registry is
user-global, so ADR-032's problem dissolves for Rust — at the price of
C-30 on a cold registry.

## Consequences

- The P7 exit stands or falls on the diff: `graph.py`, `evidence.py`,
  the join, the schema, and the packs are untouched; the new code is one
  syntax provider, one `INDEXERS` entry, one staging function, and the
  same four orchestration touches Go added.
- `hobbes ingest` on a Rust repo prints a one-line notice that
  rust-analyzer will execute the repo's build scripts and proc macros
  (C-29's surfacing). A user who wants ingestion without execution does
  not have it, and the notice says so rather than letting the flight
  recorder be the first place they learn code ran.
- Macro-generated definitions (`criterion_group!` emitting a function)
  anchor at the invocation site; lane A has no symbol starting there, so
  they contribute module-level edges at most. Accepted, not hidden.

## What verification added (2026-08-15, same day)

Three things the real repos taught that the spike had not:

1. **`terminalName` lost every Rust method.** rust-analyzer scopes impl
   methods as `impl#[Counter]new().`; the bracketed self type rode the
   final segment, so a method reference's name never matched its call
   site and every in-repo method edge silently fell out of the join —
   observed as `unwrap` counting *unresolved* in rust_proj's coverage.
   Fixed (strip the leading bracket group), pinned with real monikers,
   and re-verified: `c.incr()` — a value-method call lane A's fallback
   deliberately refuses — now carries a semantic `calls` edge, which is
   lane B doing exactly the job it exists for.
2. **The ambiguous-definition drop is not a cargo story — C-28
   generalised the day it was written.** scip-go declares a package's
   namespace in every file of the package, and the controlled dogfood
   re-ingest (old helper vs new, same tree) showed the drop removing two
   Go module edges that had been **false since V2.M5**, semantic tier,
   pointing at same-named files in the wrong package. Zero symbol edges
   changed for any language. The ADR-037 lesson — a register entry can
   be wrong by being too specific — caught in hours rather than a
   milestone.
3. **I-4 turned red on cue.** The first `hobbes review` after
   `rustsource` landed failed I-4 citing its `tree_sitter` import —
   the unified checker forcing the roster amendment ADR-039 promised it
   would. The rule block now names `rustsource` and
   `ext:tree_sitter_rust`; the statement needed no edit.
