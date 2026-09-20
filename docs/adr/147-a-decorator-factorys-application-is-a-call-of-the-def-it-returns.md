# ADR-147 — A decorator factory's application is a call of the def it returns

**Date:** 2026-09-20 · **Status:** accepted and **built** (0.2.66-beta, unit `db45`; Max, 2026-09-20: route a's second unit;
strict or loose "whicever is more honest. we never sacrifice honesty for higher recall";
"yes proceed with the dispatch"), built as one dispatched unit; measured over the
built 0.2.65-beta export before anything was drawn · **Owner:** Max · **Source:** ADR-146's
*What this leaves*; the 728 click closure rows on decorator lines.

Narrows C-58's function-value face for one shape. Registers nothing new: what the rule
refuses stays in that entry, counted.

## The shape

```python
def option(*param_decls, **attrs):        # src/click/decorators.py
    def decorator(f):
        …
        return f
    return decorator

@click.option("--count")                   # a test, a module, anywhere
def cli(count): …
```

`@click.option("--count")` is two calls: `option(…)`, which ADR-146 now draws
(`semantic`, the index names `option` at the token), and the application of what it
returned to `cli` — a call of `option.<locals>.decorator`, written nowhere. The index
emits nothing for it: there is no token. Both ends are symbols today
(`click.decorators.option` and `click.decorators.option.decorator`, kind `function`).

## The rule

At a **call-form** decorator whose callee is a name chain (`@f(…)`, `@a.b(…)`), draw a
`calls` edge from the decorator's caller to `g`, tier **`syntactic`**, evidence at the
callee's line with `via: decorator-factory`, where **all** hold:

1. the settled graph carries a **`semantic` `calls` edge** with an evidence row at that
   path and line whose target is a symbol of kind `function` or `method` **named as
   written** (the chain's last component) — the index naming `f`, not lane A's reading —
   and exactly one such target. The edge's `from` is the caller, as ADR-146 scoped it;
2. `f` has **one body**: among the definitions of its qualname in its module, exactly one
   is not decorated `@overload`, and that one carries **no other decorator**, is not
   `async` and holds no `yield` (the drawn symbol may be the first overload stub — H-19's
   grain — so the body is looked up, not assumed);
3. **every `return` in f's own body is `return g`** for one bare name `g`, and there is at
   least one;
4. `g` is bound **exactly once** in f's own scope, by a nested `def` that carries no
   decorator; it is not a parameter of `f`;
5. `<f's id>.<g>` is exactly one symbol of kind `function`.

Under these the claim is exact on every path: whatever `f(…)` returns is `g`, and the
language applies it. **That is why the wording is the strict one.** The loose wording
(some `return g`, other returns anything) read 661 click rows at 0 contradicted against
strict's 304, and is not taken: click's `command` also has `return decorator(func)`, and
on that path the site does not call `decorator` — `command` does. A rule fails toward
drawing less (ADR-145's one-return precedent); the 491 sites loose would add are counted
as a refusal, where a reader can see them.

**Refused, each counted by reason** in a `decorators` block on the graph
(`factory_calls: {drawn, refused: {…}}`, present only when at least one site reached
condition 2): more than one target at the line; `f` has no single body; `f` is decorated
(flask's `Scaffold.route` under `@setupmethod`: 162 sites); `f` is async or a generator;
not every return is one bare name; the returned name is not one undecorated nested def
bound once; no such symbol; a `(from, to)` pair the graph already carries a `calls` edge
for. **Not counted** — nothing was asked: a decorator with no semantic in-repo edge at
its line (`@pytest.fixture()`, an untyped `@app.route(…)`), a bare decorator (its result
is not applied by this rule's reading — `@f` applies `f` itself, ADR-146), a callee that
is not a name chain, a callee whose terminal identifier is not on the decorator's own
line. Without lane B the rule draws nothing: condition 1 cannot hold.

**Not claimed:** what `g` returns, or what a later call of the decorated name reaches.

## Measured (`~/.hobbes/bench/py-nested-defs/`; `PREREG-b.md` first, `probe_b.py`)

The rule as worded above, over the **built** 0.2.65-beta export (the join's real claim,
not a stand-in):

| repo | drawn | judged | largest refusals |
|---|---|---|---|
| click (py-trace key `click-py-r2`) | 368 | **304 confirmed, 0 contradicted**, 64 on lines the key never ran | not every return one bare name 491 · f decorated 3 |
| flask (held out, no trace key) | 1 (`@flask_group.command()` → `AppGroup.command.decorator`) | read by hand: right | f decorated 162 |
| attrs (held out) | 0 | — | not every return one bare name 72 |

P1–P3 held. click's recall would read 3,052 → 3,356 of 4,595 (66.4% → 73.0%). Targets:
`option.decorator` 203, `argument.decorator` 98, `Group.result_callback.decorator` 2,
`pass_meta_key.decorator` 1 — every one a symbol today; the rule mints nothing
(ADR-129's lesson).

**What the evidence is, plainly.** One trace-keyed repo carries all 304 judged rows, and
two factories carry 301 of them; the held-out read is one row by hand. The claim is small
enough to read — every return is one name, the name is one nested def — and it abstains
everywhere else; that, not the row count, is why it is proposed as worded.

## What this leaves

- C-58 keeps: a factory with any other return (click's `command`, `group`), a decorated
  or class-based factory, a factory reached through an alias or an untyped receiver, a
  bare decorator's returned wrapper, and every other function value.
- Test reach follows these edges as it follows any `calls` edge; the tier says how far
  to trust it. Resolution coverage is not moved: there is no site — no token — to count.

## Accepted — the code facts the unit rests on

Read in the tree at `740459d`:
- `pysource.Decorator` has `dotted, args, kwargs, line, true_kwargs, unread_kwargs`; a
  bare `@f` and a call-form `@f()` digest identically, so the walk must keep which it was.
  `_decorator_expr(node)` gives the expression; `_terminal` its callee identifier.
- `pysource.Symbol` carries ADR-145's `value` and `rebound`, computed over the
  definition's own body; the new fact is computed the same way.
- `extract/__init__.py`, the `timings.step("fixtures")` block: `fixtures.value_calls(…)`
  reads `graph["symbols"]` / `graph["symbol_edges"]` after the projection and
  `_add_value_call_edges` appends `tiered_edge(…, "calls", evidence, tier=SYNTACTIC,
  lane=LANE_TREE_SITTER)` merged per `(from, to)`, re-sorted by `_edge_order`.
- click's graph at 0.2.65-beta carries `click.decorators.option` (line 352's def; kind
  `function`) and `click.decorators.option.decorator` (line 373), and a `semantic` `calls`
  edge from each decorating scope to `click.decorators.option` with evidence at the
  decorator's line. `click.decorators.command` is drawn at its first `@t.overload` stub
  (line 138); its body is the third definition of the qualname.
- `cli._print_fixtures` prints the `fixtures` block's line in the ingest summary.

## Built (0.2.66-beta) — and one amendment

Unit `db45`, merged `--no-ff`. click on `main`: **368 drawn, 304 confirmed, 0
contradicted — the probe's figures exactly — 3,356 of 4,595 (73.0%), 18 suspect (the
same rows), poison PASS, 0 rows lost** (`oracle-grading.md` §10.31).

**Amended: when the counts block is written.** This page said "present only when at
least one site reached condition 2". The doer wrote it where a site was *asked* —
condition 1 named a factory — so a `two-targets` refusal, which fails condition 1's
"exactly one", is visible rather than thrown away. Accepted: a refusal the reader cannot
see is the worse reading. `returns_inner is None` is one reason, `no-returned-def`
(async, generator, the return shapes, the binding shapes): telling them apart needs a
second read of the body and nothing downstream asks.

**Two defects fixed at the review, both found by the host's `lane_b` run** (it skips in
the sandbox): the edge append kept symbol callers only, as ADR-145's does — the brief's
wording — so a module-level `@factory("a")` was counted and not drawn; the caller may be
a module node (ADR-007). And two test assertions matched the index's own direct edges.
