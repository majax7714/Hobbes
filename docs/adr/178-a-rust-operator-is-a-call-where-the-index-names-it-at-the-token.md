# ADR-178 — A Rust operator applied to a repo impl is a call where the index names it at the token

**Date:** 2026-10-04 · **Status:** accepted (Max, 2026-10-04: item 5, route a, "probe first … then
pre-register and measure on cyme") and built (0.2.118-beta).

C-174's Rust face: `*r` where `r: Ref` runs `impl Deref for Ref`'s `deref`, `a * b` runs `Mul::mul`, `v[i]`
runs `Index::index`. rustc's MIR keys each as a call; Hobbes drew none (no call token names a callee). hecs,
fitted, keys 82 such sites onto repo `Deref` (60), `PartialEq` (14), `DerefMut` (6) and `Mul` (2) methods.
This is ADR-131's question for Rust.

## The probe (`~/.hobbes/bench/rust-ops-2026-10-04/opprobe.py`, hecs' cached lane B facts and key)

- rust-analyzer writes a reference **named for the operator's method** (`deref`, `deref_mut`, `mul`) **at the
  operator token's column**, onto the repo impl's method (moniker `impl#[Ref<'_, T>][Deref]deref()`). No call
  site claims it, so it was a `uses` edge.
- 65 of the 82 key sites have such a reference onto the key's own target at that line. Unary `*`: 66
  references, 59 confirmed by the key at that line, 7 on lines the key is silent on, 0 contradicting.
- Not reachable: `==` gets **no** reference (the 14 `PartialEq` sites, most inside `assert_eq!`), and
  auto-deref through `.` (`hp1.0 -= …`) writes no token.
- A binary `*` also gets `mul` references on the spaces beside it; only the one at the token is taken.

## Decision

1. **Lane A records Rust operator tokens** (`rustsource._operator_tokens`): every leaf token spelled as an
   operator, in an expression or a macro's token tree, packed as ADR-131's C++ tokens are (`[` as `[]`, the
   template bit clear). A token under an ERROR node is dropped. No `Site`, no coverage count, no tail.
2. **The join draws the call** (`evidence._rust_operator_call`): a lane B reference no call site claimed,
   whose name is an operator trait's method (`RUST_OPERATOR_METHODS`: `deref`/`deref_mut`/`mul` → `*`,
   `index`/`index_mut` → `[]`, `add` → `+`, the compound `*_assign` forms, …), at **exactly** a recorded token
   of a spelling that method answers, is a `calls` fact at `semantic` tier with both lanes, and the
   enclosing symbol is its caller. Anything else stays the `uses` it is.
3. Counted as `operators.rust_drawn` in `graph.json` and printed under the graph line. C++'s path is unchanged.
   With lane B off nothing is read (P6).

## Alternatives considered

- **Read the source character at the reference's column instead of lane A's tokens.** Simpler, but a `*`
  inside a string or a comment would match; tree-sitter's leaf token is the evidence ADR-131 already uses.
- **Draw at the line, any column.** The `mul` references on the spaces beside a binary `*` would double it,
  and nothing would say the operator was written there.
- **Count and register only** (route b). The index and lane A together prove these calls; it would draw less
  than they prove.

## Measured (`~/.hobbes/bench/rust-ops-2026-10-04/`: `PREREG-rule.md` with two amendments, `prereg.sha256`, `regrade/`)

Pre-registered before the build (Q1–Q7). The first held-out cell, **cyme**, was vacuous: all 30 of its
operator-trait sites are `PartialEq::eq` at `==`, which the probe had shown unreachable; the take condition
counted every operator trait (amendment 1, recorded, not re-scored). Walked again for reachable traits:
**algesten/ureq** (position 3) taken, its standing grade 1,257/1,257 at 0.2.117-beta (amendment 2).

| cell | before | after | rust_drawn | reachable misses |
|---|---:|---:|---:|---|
| **ureq (held out)** | 1,257/1,257 | **1,274/1,274** | 17 | `Deref` 17 → 9, `Add` 9 → 0 |
| hecs (fitted) | 1,379/1,379 | **1,440/1,440** | 68 | 68 → 0 (`PartialEq` 14 stay) |
| cyme (held out, vacuous) | 2,754 | 2,754 | 0 | `PartialEq` 30, unreachable |
| leaf, memchr, sea-query, reshape, dagger `sdk/rust`, rust_proj | unchanged | unchanged | 0 | — |

Q1 met (0 contradicted on all nine cells); Q3 met (+61); Q4 poison PASS everywhere; Q5 met both ways (0 lost
by site and target, 0 by edge key); **Q6 met: all 17 calls added on ureq read, each at a line holding the
matched token**; Q7 met. **Q2 missed as written:** amendment 2 fixed the denominator at the 17 `Deref` sites
`count_reach.py` counted, and 8 closed (47%, bar 50%). Two flaws in the instrument, recorded and not
re-scored: its regex missed `Add` because rustc writes `ops::Add<Duration>>` (with it the denominator is 26,
17 closed, 65%), and it counted by trait, while 9 of ureq's `Deref` sites carry no token at all (auto-deref
through `.` and a deref coercion), the shape the probe had named unreachable. C-174 is narrowed and names
both residues.
