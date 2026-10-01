# ADR-155 — A later def of a Python qualname is its node's too

**Date:** 2026-10-01 · **Status:** accepted (Max, 2026-10-01: route a, "re-file at the node"; built
through Shanks) · **Owner:** Max · **Source:** the handoff's extraction candidate 2 (a qualname a
Python file defines twice outside a static test). Measured this session, zero spend:
`~/.hobbes/bench/py-samescope/` (`RESULTS.md`, `probe.py`, `callers.py`, `sim.py`).

A defect fix; no register entry. It corrects one sentence of C-170.

## The cause

The candidate's premise did not hold. It said lane B's references to a qualname's second def
land nowhere. In fact scip-python 0.6.6 gives a name one scope binds more than once **one
definition, at the first def, and a reference occurrence at each later def's name token**. That
holds for an `@overload`'s stubs and implementation, a property's getter and setter, an
`if`/`else` pair and a test that redefines a local, on every one of flask's 19 and click's 22
such qualnames. (ADR-150's same-named nested defs are the exception, several definitions; they
abstain.) Every reference therefore lands on the first def's line, which is where
`graph._symbol_records` keeps the node, and calls reach the node.

The cost is on the other end. A lane B `uses` fact (an annotation, a class named in a body, a
decorator) has no lane A site and so no lane A `scope`. `scipsource.project` files it under
`_SymbolIndex.enclosing()`, and the node spans only the **first** def. That gives two wrong
shapes:

1. **A later def's own name token** is filed as `<parent> uses <qualname>`. click's
   `click.decorators uses click.decorators.command` rests on the four `@overload` stubs (144,
   153, 163, 168), and `click.core.Group uses Group.command` on its two. None of them is a use.
2. **A use written inside a later def** is filed under the parent. `click.core.Command uses
   click.exceptions.Abort` at 1591 sits inside `Command.main`'s implementation, and
   `app.App uses app.App.jinja_env` at 567 inside the `debug` setter.

`calls` are not affected. A call site has lane A's scope, which names the qualname.

## Measured (`sim.py`, the rule below over each cell's built graph)

| cell | qualnames | wrong edges removed | edges added (the same use, at the method) | edges thinned |
|---|---|---|---|---|
| click | 22 | 28 | 14 | 16 |
| flask | 19 | 13 | 4 | 10 |
| attrs | 10 | 4 | 1 | 8 |
| this repo | 2 | 2 | 0 | 0 |

Every site that moves is `uses`, so no graded row can move: the keys grade `calls`. Each removed
edge was read and is wrong as stated.

## The decision

**A later live def of a qualname belongs to that qualname's node when the join looks for a
caller.**

1. Where lane B ran for Python (`python_reading` present, as ADR-154's step runs), for each
   Python file, every qualname with two or more defs (`parsed[...].symbols`) gives its node
   the spans `(line, end_line)` of each def **other than the one the record sits at** (after
   ADR-154 has moved a twin's record), **leaving out every def in a dead region**. ADR-154
   withholds a dead twin def; this keeps that.
2. `scipsource.project` takes these spans as `{symbol id: [(line, end_line), …]}`, and
   `_SymbolIndex.enclosing` reads each one as a further row of its symbol. The innermost match
   still wins, so a def nested inside a later def keeps its own lines.
   `_SymbolIndex.starting_at` is unchanged: the fallback, lane B's definition and the record
   all name the first def.
3. Nothing else is new. A non-call whose caller is now its own callee (shape 1) drops by
   `project`'s existing rule (`caller == callee and kind != "calls"`), and a use inside a later
   def (shape 2) is filed under the qualname.

Without lane B for Python nothing is computed and the graph is what it was (P6). Lane A's own
facts carry their scope and are unaffected.

## Predicted effect (checked on the real cells before merging)

- click: the 28 edges above leave and the 14 arrive; flask 13 and 4; `calls` edges identical.
  flask 1,524 and click 3,756 confirmed, 0 contradicted, poison PASS.
- Lane disagreements unchanged (they compare `calls` sites).

## Routes not taken

- **b, drop only:** drop lane-B-only evidence inside a later def instead of re-filing it. It
  removes the same wrong edges but also the 19 right ones, so it draws less for no gain in
  honesty.
- **c, register only:** it leaves the wrong edges in the graph.
- **One node per def** (`f@138`, `f@144`): this changes ids, and every key grades a qualname.
  For an `@overload` or a property the qualname *is* the one thing, so it is not wanted here.

## What this leaves

- The node's `line`/`end_line` still name the first def: an `@overload`'s first stub, not its
  implementation. The artifact does not list the later spans. That is display, not an edge.
- Other languages' duplicate qualnames (C++ overloads keep their own layer) are not measured.
