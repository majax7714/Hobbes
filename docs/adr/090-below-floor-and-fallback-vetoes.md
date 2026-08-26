# ADR-090 — The `below-floor` tail class, and two vetoes on lane A's fallback

**Date:** 2026-08-25 · **Status:** accepted · **Owner:** Max · **Source:** the oracle lane's phase-2 triage (ADR-089, O6/O7)

## Context

The oracle lane's first Python and Rust cells (2026-08-25) produced
exactly three kinds of finding against the product:

1. **Every wrong edge was lane A's syntactic fallback name-matching a
   call to a declaration that was not the callee.** Python: six executed
   edges, all `symbol_at(...)` inside a test whose *parameter* `symbol_at`
   holds the closure a fixture returned, bound to the fixture function.
   Rust: twelve contradicted edges, all `format!(...)` invocations bound
   to a `fn format` in the same file. The semantic tier was 100% on both.
2. **The misses were C-58 everywhere** — closures, function values,
   interface and extension-trait dispatch, 70–81% of every cell's misses
   — and C-58 was *unsurfaced*: the site counts resolved, draws no edge,
   and no artifact field said so.
3. ADR-046 had already taught lane A the bindings that answer (1): the
   fallback simply never consulted them.

## Decision

- **Scope shadows the fallback (Python).** `resolve_call_sites` refuses
  a bare-name resolution when an ADR-046 local binding of that name spans
  the call's line, unless the resolved declaration itself lies inside
  that extent (the nested `def`). A parameter, an assignment target or a
  nested def is that binding, never a module-level namesake.
- **A bang binds only to a macro (Rust).** `macro_invocation` sites are
  flagged `macro`; `_call_fallback` resolves them only to a `macro`
  symbol and a plain call only to a non-macro one.
- **`below-floor`, a tail class fed from the projection.** `project()`
  returns the semantic-lane call sites whose target line starts no
  symbol; the layer counts them per file as `floored` on the coverage
  row and as `below-floor` in the tail, marked *seen, not modelled by
  design* (`NOT_MODELLED`, and `list_blind_spots`' `notModelled`). The
  tail invariant becomes `sum(tail) == unresolved + floored`. The
  `resolved` count does **not** move: that part of C-58 is conceded
  still, and the entry says so (*partial*).

## Consequences

- On this repo, lane A's Python fallback loses the six wrong edges and
  keeps every right one the oracle confirmed; the O6 regrade is the
  check. Rust's `format!` shape is covered by a tmp-crate test; the
  dagger `sdk/rust` regrade is the check.
- The tail gains a class whose count is not an unresolved site; every
  reader of the invariant (the tests, `rollup`, knowledge.go) was
  updated in the same commit. The class is available for all four
  lane-B languages (`CLASSES_AVAILABLE`).
- C-58's surfacing status: unsurfaced → partial. Its capture-number
  concession stands; `docs/oracle-misses.md` remains where the hole is
  sized.
