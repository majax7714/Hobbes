# ADR-177 — A Rust trait's provided method is a node

**Date:** 2026-10-04 · **Status:** accepted (Max, 2026-10-04: Route 1 of the forty-third session, "good to go
with route 1", whose step 4 was this rule, measured on a newly drawn held-out cell) and built (0.2.117-beta).

The first random Rust draw (`oracle/oracle-grading.md` §10.49) found the largest Rust gap on any cell:
669 of sea-query's 1,088 misses are calls onto a trait's **provided** method, a `fn` with a body inside a
`trait` body. Lane A's symbol walk recursed into `mod` and `impl` bodies and not `trait` bodies, so the body
had no node; lane B resolved the call there, and the projection tailed it `below-floor`, which until
0.2.115-beta even named it an interface method (C-58). It is not dispatch: rustc's MIR keys it as a static
call, and it is the code that runs wherever no impl overrides it. leaf had 11; hecs, reshape, memchr, dagger
and rust_proj 0.

## Decision

1. In a `trait_item`'s body, each `function_item` (a provided method: it has a body) is minted a `method`
   symbol, qualname `<prefix>.<Trait>.<name>`, its span the item's (`rustsource._walk_items`,
   `provided_only`). A required method is a `function_signature_item` and is not minted, as TS and Java
   interface members are not; an associated `const` or `type` is not minted either.
2. Its impl header is `trait <Trait>`, so ADR-174's ordinal grouping never folds it into an `impl` block's
   methods: `impl dyn Trait { fn m }` beside a provided `m` is `Trait.m~2`.
3. A provided method under a `#[cfg]` is gated like any def (ADR-165 and its second amendment).
4. Nothing else changes. Lane A's fallback still never binds a bare name to a method (C-72 rule 2) and
   still leaves a trait-headed path to lane B (rule 3). A call written inside a provided body is filed
   under the new node; before, it was filed under the trait's `type` node.

**Not decided here:** an `implements` edge between an override and the provided method it replaces
(C-157: rust-analyzer writes no relationships), and C-58's dispatch through a trait object, which still
draws no edge to any implementor.

## Alternatives considered

- **Name it as its own tail class and register it, no node** (route 2). Honest, but it draws less than the
  index and the compiler prove: lane B answered with the body that runs.
- **Mint required methods too, as interface members.** Java and TS keep them off the floor; a node with no
  body would collect calls that run some impl's code (C-58).
- **Leave it `below-floor`** (route 3), with the 0.2.115-beta wording.

## Measured (`~/.hobbes/bench/rust-provided-2026-10-04/`)

Pre-registered before any held-out ingest: `PREREG-draw.md` (the 2026-10-03 draw walked again from
position 2, a source-only shape count per package, then a key-side take condition; three amendments) and
`PREREG-rule.md` (P1–P8); hashes in `prereg.sha256`. The walk: positions 2–7 below the shape bar;
VOICEVOX/voicevox_core (8) failed check 5 (its `open_jtalk-sys` build script cannot configure CMake in the
contained check); **tuna-f1sh/cyme** (30) taken, its key holding 46 in-repo pairs onto provided-method
bodies. Its standing grade at 0.2.116-beta, without the rule: 2,708/2,708, recall 90.5%.

Regrade, before = each cell's 0.2.116-beta grade (`regrade/`: `cells.tsv`, `score.py`, `score.json`):

| cell | confirmed | contradicted | recall | nodes added |
|---|---:|---:|---:|---:|
| **cyme (held out)** | 2,708 → **2,754** | 0 | 90.5% → 92.1% | 21 |
| sea-query (fitted) | 5,601 → **6,263** | 0 | 83.8% → 93.7% | 202 |
| leaf (fitted) | 1,634 → 1,645 | 0 | 89.3% → 89.9% | 4 |
| memchr, hecs, reshape | unchanged | 0 | unchanged | 11, 3, 2 |
| dagger `sdk/rust`, rust_proj | unchanged | 0 | unchanged | — |

P1 (0 contradicted added) met; **P2 met: 46 of cyme's 46 misses onto provided bodies closed** (bar 80%);
P3 poison PASS everywhere; P5 sea-query +662 (bar 600); **P6 met: every node the rule adds is a `fn` with a
body in a `trait` body** (cyme 21 of 21, sea-query 50 drawn of 202, the rest all); P7 no new unexplained
`hobbes lanes` row; P8 no `calls` edge keeps a trait's `type` node as the caller of a call in a provided
body. **P4, as worded ("no confirmed edge lost"), is met by site and target but not by edge key:** 63
confirmed rows (leaf 2, sea-query 36, cyme 25) keep their site and target and change their caller from the
trait's `type` node to the provided method, which is P8's effect. The pre-registration did not say which
identity P4 meant; recorded, not re-scored.
