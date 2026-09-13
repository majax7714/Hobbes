# ADR-046 — Lane A local bindings: origin support beyond the checker

**Status:** accepted (2026-08-16)

**Scope:** applies C-32's candidate fix ("origin support from the other
syntax providers"), at Max's direction after passing the tail-view
review. `pysource` and `gosource` each gain a local-binding collector;
the tail view's `local-binding` class now fires for Python and Go.
Amends architecture §3.4 (one sentence) and **narrows C-32**. No facts
schema change — the bindings travel inside each lane's layer bundle,
never into the artifact.

## Context

After ADR-045's amendment, the honestly-unknown residue on the verified
fleet had a known shape: the dogfood repo's 45 unclassified Python
sites were locally-declared helpers — `fake_policy_bin` (a fixture
*parameter*), `symbol_at` (a nested `def`), `out`/`runner`
(assignments) — and Go's 20 were closure-typed locals (`cleanup`,
`cancel` from `ctx, cancel := context.WithCancel`). TS had escaped this
bucket because its checker reports where an unresolved callee's
declarations live; Python and Go had no equivalent, and C-32 said so.

But lane A *sees* these bindings — it walks every file. What it lacked
was the decision to record them.

## Decision

**Each syntax provider records sub-module bindings with the enclosing
function's line extent**, and a bare unresolved call classifies as
`local-binding` only when an extent **spans the call's line** — scope
containment, not a file-wide name match. The observation is "bound in a
scope that spans this call", which is checkable and stated exactly.

- `pysource._collect_local_bindings`: parameters (a pytest fixture
  argument is one — the dogfood residue's biggest piece), assignment
  and walrus targets, `for`/`with`/`except` targets, nested
  `def`/`class` names (bound in the *enclosing* extent; their own
  params under their own). A class body is its own namespace: a local
  class binds its name, its methods bind nothing outward. A separate
  walk from `_walk`, on purpose — one collects what the graph models,
  the other what it deliberately does not (C-9's floor), and the split
  keeps either from quietly growing the other's job.
- `gosource._local_bindings`: parameters (receivers and named results
  included), `:=` and `var` targets, `range` targets, inside
  `func_literal`s too. Package-level declarations are symbols, not
  bindings, and are excluded.
- **Priority: a scope-contained local outranks an import binding** —
  a binding inside the enclosing function shadows a module-level
  import, so when both observations apply the local is the truer one.
  (The mirror of ADR-045's import-over-builtin rule, for the same
  reason at the next scope in.)
- Rust: not extended — both verified Rust tails are empty, so there is
  no residue to classify and no way to verify a collector against
  reality. Wiring one on zero evidence would be the P11 mistake at
  class scale. C-32 keeps Rust listed.

## What this narrows, honestly

C-32's asymmetry shrinks from "checker origins are TS-only" to a
statement about **proof grades**: TS `local-binding` is
declaration-proven (the checker resolved it); Python/Go `local-binding`
is binding-proven with scope containment (lane A recorded the binding
and the extent spans the site). Both are observations; the register
says which grade a language gets. What C-32 keeps: the pinned builtin
lists, the text-shape boundary, Rust's absence, and the artifact not
declaring per-language `classes_available`.

## Consequences

- The honestly-unknown residue on the verified fleet drops to the
  genuinely dark: `attr-call` (untypable receivers — C-2's core) plus
  the sites no observation reaches. Exit numbers in the BUILDLOG.
- Tail classes remain artifact-additive only (`resolution_coverage.tail`
  counts); the bindings themselves are working data, not artifact
  surface — nothing new to gate or version.
- The collectors are new per-language surface the 2026-08-15 audit
  lesson applies to: a grammar change in either language can drift them
  silently, and the binding tests (`TestLocalBindings` in both provider
  suites) are what would catch it.

## Amendment 2026-09-13 — the qualifier of a selector call (C-139)

The priority above, that a scope-contained local outranks an import
binding, reached the Go fallback for a **bare** name only (ADR-090's
scope veto, `gosource._shadowed`). A qualified call resolved through
the import its qualifier names, whatever the scope held. So after
`slog := slog.SpanLogger(ctx, …)`, the call `slog.Info(...)`, a method
on the local logger, was drawn to the package function
`engine/slog.Info` (dagger, found by ADR-111's regrade; C-139).

**Decision.** `gosource._call_fallback` reads a qualifier as an import
alias only when no local binding of that name spans the call's line.
This is the same `_shadowed` test, applied to the call's receiver. A
shadowed qualified call is a method on a value, which the fallback
already leaves to lane B.

- **The extent stays function-wide**, as it is for bare names. It
  over-approximates Go's block scope and the binding's own position,
  so the declaring statement's own call (`slog.SpanLogger` above) and
  any earlier call in the function are skipped too.
  - That costs a true syntactic edge only where lane B is silent. Lane
    B's semantic edge is unaffected, and a skipped site is counted,
    never guessed.
  - Precision comes first. A finer extent (the binding's own line, the
    enclosing block) is a later refinement, taken only if a graded cell
    shows the cost.
- **The tail is unchanged.** Such a site is an attribute call on a
  value lane A cannot type, and it lands in `attr-call` (C-2).
- **Acceptance.** Every Go cell with a stored key is re-ingested
  contained on the branch and graded against its key. No confirmed
  count may fall in any cell, and no contradiction count may rise.
  Dagger's root module (no key) is read by `hobbes lanes` and by the
  shadow scan of 2026-09-12.
- **C-139** is lifted at the merge. The extent's cost is recorded in
  the same entry (P8).
