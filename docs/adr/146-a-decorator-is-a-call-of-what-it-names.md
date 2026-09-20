# ADR-146 — A decorator is a call of what it names

**Date:** 2026-09-20 · **Status:** accepted and **built** (0.2.65-beta, unit `f751`; Max, 2026-09-20: route a — the
decorator walk first, the factory's inner def after it as its own ADR; "we never
sacrifice honesty for higher recall"), built as one dispatched unit;
measured on a scratch worktree before anything was drawn · **Owner:** Max ·
**Source:** the step-0 probe for C-58's Python face
(`~/.hobbes/bench/py-nested-defs/`), which set out to make nested defs symbols
and found they already are.

Registers **C-169** and lifts most of it in the same release: the skip was a
concession no entry carried (P8).

## What was found

`pysource._walk` does not walk a decorator's expression. Its comment, from the
first extraction milestone: *"@app.get("/x") is a call, but recording it would
pollute the call graph."* A test pins it
(`test_decorator_expressions_do_not_pollute_calls`). No `C-n` names it, no tool
says it, and `oracle-misses.md` files the rows under C-58 as "a call inside a
decorator expression" beside function values — but `@click.option("--x")` is a
direct call of a declared function, the semantic lane's whole job. With no lane A
site there, the join has nothing to pair the index's occurrence with, and the
reference is drawn `uses` or not at all.

On click (py-trace key `click-py-r2`, 0.2.64-beta): **0 of 2,447 edges sit on a
decorator line; 1,652 of 2,459 missed pairs do** — `observed→function` 737 of
750, `observed→class` 112 of 149, `observed→method` 75 of 284, and 728 closure
rows that are the *next* ADR's (the factory's inner def).

The same probe corrected the record: a Python nested `def` **is** a symbol
(`click.core.Group.invoke._process_result`) and a direct call to one is drawn
`semantic` by the index. `oracle-misses.md`'s "nested functions are not graph
symbols" is wrong for Python and is corrected with this ADR. And 590 of this
repo's 642 closure misses are `<genexpr>` frames — the interpreter's grain, not
a call anyone wrote; logged as a question about the key, not built on.

## The rule

Python only, lane A only; the join and the index are untouched.

1. **A decorator's expression is walked as any expression is.** Every call in it
   — `@f(…)`, `@a.b(…)`, a call in its arguments — is a `Call` site, scoped to
   the **enclosing** definition (the decorated one is not yet running), the
   module where there is none, positioned on the callee's terminal identifier
   as every call is.
2. **A bare decorator is an application of what it names.** `@name` or `@a.b`
   with no call syntax is, by the language's definition, `name(fn)`: one `Call`
   site at the terminal identifier, same scope. A bare decorator that is any
   other expression (a subscript, a lambda) records nothing.

What is drawn from a site is the join's and the fallback's business, exactly as
for a call in a body: an index occurrence on a repo symbol draws `semantic`; an
untyped receiver (`@app.route` on a fixture parameter) draws nothing and is
counted in the tail as it would be anywhere. The `Decorator` digest the route
and test packs read is unchanged.

**Not claimed:** that the decorated function is *replaced* by the call's result,
or what a later call of the decorated name reaches. That is the dispatch
question (C-58) and stays there.

## Measured (scratch worktree `py-nested-defs/wt`; nothing committed)

| cell | before | part 1 | parts 1+2 |
|---|---|---|---|
| click, confirmed / 4,595 | 2,136 (46.5%) | 2,995 (65.2%) | **3,052 (66.4%)** |
| click, suspect | 18 | 18 | **18** (the same rows) |
| click, edges | 2,447 | 3,463 | 3,533; poison PASS, 0 falsely confirmed |
| click, lane sites compared / disagreements | 830 / 2 | 859 / 2 | 872 / 2 (the same two) |
| flask (held out, no trace key) | 1,055 rows | 1,221: +166, all `semantic`, 0 lost | — |
| attrs (held out) | 1,637 rows | 1,757: +120, all `semantic`, 0 lost | — |

flask's new rows are `Scaffold.route` 107, `errorhandler` 21, `get` 10 …; attrs'
are `define` 54, `attrs` 18, `instance_of` 13 … — what a reader asking
`who_calls` of them would expect to see. Symbols, nodes and module edges are
unchanged on both: the rule mints nothing (ADR-129's lesson). Part 2's 70 click
rows are `pass_context` 43, `imagepipe.processor` 11, `command` 6 …, 57 of them
on lines the key ran, all confirmed. The pipeline suite under the change: 2,203
pass, 1 fail — the pinning test, which the unit replaces.

**What the evidence is, plainly.** One trace-keyed repo judges the rows; two
held-out repos show only that nothing is lost and what is added is `semantic`.
The rule is the language's own definition of a decorator and adds no resolution
of its own — every edge it enables is one the index already names.

## "Pollution", answered

The old worry was that framework decorators would flood the graph. Measured:
they do not — an edge appears only where the index resolves the callee to a repo
symbol, so `@pytest.fixture`, `@property`, `@functools.wraps` draw nothing
in-repo, and `@app.route` on an untyped `app` draws nothing at all. What does
appear is true: the decorated module *does* call `Scaffold.route` at import.

## What this leaves — C-169

- A bare decorator that is not a name chain; a class decorator is covered by the
  same two parts (the grammar's `decorated_definition` holds both).
- **The factory's inner def** (`@click.command()` calls `command`, and applying
  its result calls `command.<locals>.decorator`): ADR-147's, measured at 304
  rows strict.
- Resolution coverage's denominator grows by the new sites; an unresolved one is
  counted in the tail like any other. No percentage is restated as a gain.
- TypeScript and Java are not read here: whether `tssource` records a decorator
  call is unmeasured and is said so in C-169.

## Accepted — the code facts the unit rests on

Read in the tree at `7edaa3d`:
- `pipeline/src/hobbes/extract/pysource.py`, `_walk`, the
  `decorated_definition` branch: `decorator_nodes` is already collected; the
  definition alone is walked. `stack` there is the enclosing scope, so
  `_scope_qualname(stack)` is the right caller. The `call` branch records
  `Call(_scope_qualname(stack), dotted, line, column)` with the line and column
  of `_terminal(function)`; `_dotted` and `_terminal` work on a bare
  `identifier` / `attribute` node.
- `pipeline/tests/test_pysource.py::TestCalls::test_decorator_expressions_do_not_pollute_calls`
  is the only test in the pipeline suite the change fails.

## Built (0.2.65-beta)

Unit `f751`, merged `--no-ff`. The built export on click is row-identical to the
simulation's: 3,052 confirmed of 4,595, 18 suspect (the same rows), poison PASS, 0 rows
lost (`oracle-grading.md` §10.30). **One defect fixed at the review:** the unit read the
decorator's expression as the node's last child, as the digest beside it always had, and
a trailing comment is a child — `@foo  # note` recorded nothing and `@pytest.fixture  #
shared` had never been a fixture. `_decorator_expr` takes the first named child that is
not a comment, at all three sites. C-169 is registered and lifted with the residuals this
page's *What this leaves* names; the TypeScript walk takes every `CallExpression`, a
decorator's among them (read, not measured).
