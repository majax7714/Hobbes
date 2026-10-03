# ADR-174 — A Rust id two impl blocks share is told apart by an ordinal; C-180 lifts

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: build C-180's prevention after the Rust rule,
then "good with recommended" deferring that rule; the scheme: "Ordinal ~n") and **built** (0.2.106-beta) ·
**Owner:** Max · **Source:** C-180; ADR-163; `~/.hobbes/bench/dup-qualnames-2026-10-02/`.

Lifts **C-180**. Supersedes ADR-163's refusal as the answer; its machinery stays as a guard.

## What is wrong

Lane A names an impl block's items after the block's first type identifier (`_impl_type`), so
`impl Pointer for *const T` and `impl Pointer for *mut T` both mint `T.distance`, `impl From<&str> for Id`
and `impl From<String> for Id` both mint `Id.from`, and a trait impl and the inherent impl of one type share
every name they both declare. ADR-163 contained it: the node is the first def, and a fact written inside or
resolved onto a later def is refused and counted `shared-qualname`. Nothing was wrong after that, but the
later defs had no node: memchr's `*mut T` `distance`, which calls the `*const T` one, drew nothing, and
dagger's generated `gen.rs` lost 229 calls (C-180).

## The decision

1. **An ordinal tells them apart, as Java's and C++'s overloads already are.** Per file, the defs of one
   qualname fall into groups by `(impl header, kind)` in source order; the first group keeps the qualname,
   the n-th becomes `qualname~n` (`T.distance~2`, `Id.from~2`, `Client.describe~2`, and `B~2` where
   `const B` follows `struct B`). Defs sharing a header and a kind stay one group: a cfg twin is still one
   node (ADR-165, C-182), and an ungated same-header repeat is still named and filed under the first
   (C-182's residual). Only ids that collide today change.
2. **Lane B joins by line**, so a resolution onto a later def's line now finds that def's own symbol, and a
   fact written inside it is filed under it.
3. **The fallback still abstains on `Type::name`** where the file declares that name in more than one impl
   block: it counts defs by the qualname before its ordinal, so `Id::from(..)` is still an overload set
   lane A leaves to lane B (C-72's rule).
4. **ADR-163's refusal stays as the guard.** `shared_qualnames` reads the suffixed defs and so finds nothing;
   should an id scheme ever let two differently written blocks share an id again, the refusal, the
   `shared-qualname` tail class and the `rust-qualnames` record come back with it, as they are tested to.

## Not taken

- **The self-type and trait in the id** (`<*const T as Pointer>.distance`): it says which block, but every
  trait-impl id in every Rust repo would change, colliding or not (Max chose the ordinal).

## Built (0.2.106-beta)

`rustsource._ordinal_impl_repeats`, called by `_parse_file` before the defs are recorded; `_call_fallback`
counts `declared` by the base qualname. Tests: `test_shared_qualnames.py` turned over on the same
`minirustimpl` fixture (memchr's `ext.rs` verbatim, dagger's two shapes, the haystacks file).
