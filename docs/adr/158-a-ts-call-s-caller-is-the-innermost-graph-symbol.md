# ADR-158 — A TS/JS call's caller is the innermost enclosing graph symbol

**Date:** 2026-10-01 · **Status:** **built** (0.2.82-beta). This is route 2 of the honesty audit (Max,
2026-10-01: "leave 176 177 for next session"; the handoff's next task, measured first). The amendment
(§2) was found while reading the code and pre-registered before either arm ran; it is for Max's review.
· **Owner:** Max · **Source:** C-176 (registered at 0.2.80-beta by the honesty audit). Pre-registered and
measured: `~/.hobbes/bench/c176-ts-scope/` (`PREREG.md`, `run.sh`, `probe.py`, `compare.py`,
`RESULTS.md`).

Narrows C-176.

## The cause

`tsextract`'s `enclosingScope` gives each call site its lane A scope, and the join takes that scope as the
caller before its own enclosing lookup (`scipsource.project`). It recognised three shapes: a method of a
named class, a function declaration, and a function bound to a variable. That caused two errors:

1. **Too high (C-176).** Inside a named class's constructor, `get`/`set` accessor, `static {}` block or
   field initializer, it found nothing and returned null, so the call was filed under the **module**, as if
   written at top level. Python and Java file a class body's code under the class.
2. **Too low (the amendment, unregistered until now).** It never checked that what it named was a graph
   symbol. `extractSymbols` takes top-level declarations and the methods of top-level classes only, but
   `enclosingScope` also named these:
   - a *nested* function declaration;
   - a *nested* `const f = () => …`;
   - a method of a class declared inside a function.

   The caller id then named no node. `who_calls` listed a caller the graph does not have, and two
   same-named nested functions in one file merged into one caller. Test reach could not pass through it:
   reach closes over `calls` edges from the symbols a test reaches, and a nested function's calls hung from
   an id that nothing reaches.

## Decision

A call's lane A scope is the **innermost enclosing graph symbol**, in `extractSymbols`' vocabulary:

- Inside a top-level named function declaration, it is that function.
- Inside the initializer of a top-level variable bound to an arrow function or function expression, it is
  the variable.
- Inside a top-level named class:
  - A method's body and parameters are the method's.
  - A constructor, an accessor, a `static {}` block, a field initializer, a member's decorators (and its
    parameters' decorators) and a member's computed name are the **class's**. They run as part of the
    class, or when it is defined, not when one method is called. Python files a class attribute's value
    and a method decorator's call under the class too (checked with `pysource.parse_source`).
  - The class's own decorators and its `extends`/`implements` clauses run in the module's scope, so they
    are the module's, as a Python class decorator is.
- Anywhere else, it is the module. This covers:
  - a call-initialized const's initializer (a value built at load time);
  - an object literal's method;
  - an unnamed class;
  - a function assigned to a property;
  - a namespace's body.

  All of these are below the symbol floor, as before.

A nested function or nested class therefore files its calls under the top-level symbol around it. Helper
`HELPER_VERSION` 6 → 7: no field changed, but `scope`'s values changed meaning (v4's precedent).

## Measured (before = `8011254`, 0.2.81-beta; after = this change; 12 TS/JS repos, lane B in the image)

| | Before | After |
|---|---|---|
| Callers naming no node | ajv 341, Preact 145, tileserver-gl 24, 7 more repos 2–8 | **0 in all 12** |
| Module-filed rows inside a named class | folio-2025 501, ajv 26, cue 11, 4 more 3–7 | **0 in all 12** |
| `calls` rows by (path, line, target); exports without the caller; nodes; symbols | — | identical in all 12; every regrade unchanged |
| `uses` rows | — | identical in all 12 |
| Test reach | — | grows only: npq 139 tests (+419), cue 48 (+69), ajv 51 (+51); shrinks in none |
| Callers against the tsc key (probe, not a grade) | wrong 0 | wrong 0; folio-2025's agreeing rows 400 → 826 |

Most rows that dangled now name the top-level function or method around them. The rest sit in a nested
function whose own encloser is below the floor (ajv's object-literal `code(cxt)` methods, 143 rows; Preact's
`X.prototype.y = function` bodies, 129 rows). Those now name the module, which `who_calls` qualifies with
C-176's note. Before the change they named an id with no node.

## Consequences

- **C-176 narrows.** What is left is the floor itself: an object literal's method, an unnamed class, a
  function assigned to a property, a namespace's function. These are not symbols, so their calls are the
  module's. `who_calls`' note now names only these.
- **No key reads a caller.** The grades do not move and cannot confirm this. The check is the probe
  against the tsc key's `sites[].caller`, and the end-to-end test (`TestCallerIsTheInnermostSymbol`) at the
  level a user meets it: `who_calls` and test reach.
- **Not done:** lifting the floor. Making an object literal's method or a property-assigned function a
  symbol would move the symbol set, and needs Max's word (the handoff's CJS literal member, cue 49 and
  Express 46, is the same question).
