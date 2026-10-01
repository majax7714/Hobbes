# ADR-156 — A `with` statement's `__enter__` and `__exit__`, where the item's class is known

**Date:** 2026-10-01 · **Status:** accepted (Max, 2026-10-01: route a, "go general, a is good"; on the two
decisions, "good to proceed with the route") and **built** (0.2.79-beta, unit `721c`; the oracle's H-37 by unit
`32b8` first) · **Owner:** Max · **Source:** C-174 (registered at 0.2.78-beta),
found on the held-out rich cell (`oracle-grading.md` §10.40). Measured before this ADR, zero spend:
`~/.hobbes/bench/with-stmt/` (`RESULTS.md`, `probe.py`, `factory.py`, `sim.py`).

Narrows C-174. Python, sync `with` only.

## The cause

A `with` statement runs its context manager's `__enter__` and `__exit__`, and no call to either is written.
Lane A records a call where one is written, and scip-python gives no reference at the `with` for them. So
neither is a site, and nothing draws them. On the three keyed Python cells, the trace observed `__exit__`
missed 75 times on rich, 88 on flask and 35 on click. `__enter__` is unmeasured there, because the trace oracle
could not see it (H-37, fixed before this rule is graded).

## Measured (`sim.py`, the rule below over every `with` item of each cell, graded against its key)

| | rich | flask | click |
|---|---:|---:|---:|
| `__exit__` confirmed | 48 | 51 | 14 |
| `__exit__` suspect (an exception-path exit the old key could not see) | 0 | 2 | 0 |
| `__enter__` (the old key could not see it at all) | 48 | 53 | 14 |
| on lines the suite did not run | 30 | 4 | 14 |

**0 wrong.** The first wording took any drawn call on the item's line, and `with app.test_client().get(…)`
read `FlaskClient.__exit__` (5 wrong). Binding to the item's **own** call removed all five, which is why step 2
says "own". Where a factory's return annotation named an in-repo class, it was the class whose `__exit__` ran in
every case on all three repos.

## The decision

**Where a sync `with` item is a call whose class the graph already knows exactly, its `__enter__` and
`__exit__` are drawn as calls at the item's line.**

1. **Lane A records** (in `pysource`, the only grammar, I-4):
   - for each sync `with` item whose context expression is a call: its line, the name its own call writes
     (`Live` for `Live(…)`, `capture` for `console.capture()`), and its enclosing scope;
   - for each `def`: its return annotation's head name and line, where the annotation is a name, a dotted name,
     a string holding one, or a subscript of one (`C`, `mod.C`, `"C"`, `C[…]` → `C`). Any other form records
     nothing (a union, `Optional[…]`, `None`).
2. **The item's class C**, read off the settled graph after the projection, as ADR-145 reads it:
   - the item's scope has exactly one `semantic` `calls` edge with evidence at the item's line whose target's
     last name is the name the item's own call writes; otherwise abstain;
   - if that target is a **class**, C is it;
   - if it is a **function or method** F, F has a recorded return annotation head H at line L, and the graph
     has exactly one `semantic` `uses` edge from F to a **class** whose last name is H with evidence at L, then
     C is that class. The index resolved the annotation and lane A only says which reference it is. Otherwise
     abstain.
3. **The methods:** ADR-145's `_class_method(C, "__enter__")` and `(C, "__exit__")`. That is one `def`, not a
   property, on C or up its chain of single named bases, stopping wherever Python's answer is not certain (two
   bases, an outside base, a class attribute under the name). Each one found is a `calls` edge from the item's
   scope to the method, tier **`syntactic`**, evidence at the item's line, marked `via: "with"`. A pair the
   graph already carries a `calls` edge for is left alone.
4. **Counted:** `graph["with_statements"]` holds `{drawn, abstained: {reason: n}}`, additive and absent where no
   `with` item is a call. Without lane B there is no `semantic` edge to read, so nothing is drawn (P6).

## What this leaves (C-174, narrowed)

A `with` on a bare name or attribute (`with ctx:`; 63 observed misses over the three cells), a
`@contextmanager` factory (its methods are `contextlib`'s), an annotation naming an outside type, an
unannotated factory, a class whose chain the walk stops on, and `async with`. None of the three cells has an
`async with`, so the async pair is ungraded and not drawn. Operators and iteration dunders stay C-174 as
registered.

## Predicted effect (checked on the regenerated keys before merging)

- With H-37's keys: rich, flask and click each gain the confirmed `__exit__` rows above and, newly judged, the
  same order of `__enter__` rows. 0 contradicted (trace cells read suspect, never contradicted). No Hobbes-wrong
  suspect: every new suspect is read row by row.
- No existing edge moves; the counts block is new.

## Built and graded (2026-10-01)

The keys were regenerated first, with H-37's oracle at 0.2.78-beta (same recipe, new dirs `rich-py-r2`,
`flask-py-r2`, `click-py-r4`). Confirmed counts were unchanged, and each denominator grew by the `with` calls
the old oracle could not see (rich +74, flask +92, click +35 pairs), so recall fell (rich 89.7% → 88.4%,
flask 56.5% → 54.6%, click 82.4% → 81.7%). The old figures were that much flattering.

The build, graded against those keys (`~/.hobbes/bench/with-stmt/after/`, `--poison`):

| cell | confirmed | suspect | recall | new rows | `with_statements` |
|---|---|---|---|---|---|
| rich | 4,748 → **4,844** (+96) | 25 → 25 | 88.4% → **90.2%** | 126: 96 confirmed, 30 unobserved | 193 items, 126 drawn |
| flask | 1,524 → **1,552** (+28) | 15 → 15 | 54.6% → **55.6%** | 32: 28 confirmed, 4 unobserved | 172 items, 32 drawn |
| click | 3,756 → **3,768** (+12) | 20 → 20 | 81.7% → **82.0%** | 12: 12 confirmed | 179 items, 12 drawn |

Signed direction of fix: confirmed **+136**, suspect **±0**, rows lost or moved **0**, and every new row is an
`__enter__`/`__exit__` edge. Poison PASS on all three. Host: the `miniwith` `lane_b` case passed on its first
run.

**The prediction missed on flask:** +28 confirmed where the simulation said about +102. `sim.py` read any drawn
call edge at the item's line, but step 2 requires a `semantic` one. 40 of flask's `with` items rest on
ADR-145's `syntactic` fixture-value edges (`with app.app_context():` on the `app` fixture), and 101 have no
call edge at all. Nothing drawn is wrong. Whether the rule may build on ADR-145's edge is a separate decision
and is not taken here: it would stack one `syntactic` rule on another.

## Routes not taken

- **Constructors only:** draws 13 edges over the three cells, with no reliance on annotations. Too narrow to
  be the rule.
- **`__exit__` only:** it would have read clean against the old key, which is fitting the rule to an
  instrument that could not see `__enter__`.
- **Any drawn call on the line:** wrong 5 times on flask (above).
