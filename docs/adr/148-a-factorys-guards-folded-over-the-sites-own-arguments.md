# ADR-148 — A decorator factory's guards, folded over the site's own arguments

**Date:** 2026-09-21 · **Status:** accepted and **built** (0.2.67-beta, unit `b4d4`; Max, 2026-09-21: "route a good
to proceed with dispatch") · **Owner:** Max · **Source:** ADR-147's *What this leaves* (a factory with any
other return); click's 423 closure misses on decorator lines, `no-returned-def` 491 sites.

Narrows C-58's function-value face for one more shape. Registers nothing new: what the rule
refuses stays in that entry, counted.

## The shape

```python
def command(name=None, cls=None, **attrs):      # click/decorators.py, trimmed
    func = None
    if callable(name):
        func = name
    def decorator(f): …
    if func is not None:
        return decorator(func)                  # `@command` bare: command(f) → a Command
    return decorator                            # `@command()` / `@command("x")`: decorator

@click.command()                                # the site calls `decorator`
def cli(): …
```

The optional-parentheses idiom. ADR-147's strict wording asks that *every* return be
`return g`, and `return decorator(func)` fails it, so the site is refused. But the path
that return sits on is decided by the arguments the site itself writes: with no
positional argument, `name` is `None`, `callable(None)` is false, `func` stays `None`,
and the only return the call can reach is `return decorator`. The same shape is
`Group.command(self, *args, **kwargs)` (`if args and callable(args[0])`), attrs'
`attrs(maybe_cls=None, …)` (`if maybe_cls is None: return wrap`), and dataclass-style
factories generally.

## The rule

Where ADR-147's conditions 1, 2 and 5 hold and condition 3–4 does not (`returns_inner` is
`None`), the site is drawn when **folding the factory's own guards over the site's own
arguments leaves `return g` as the only reachable return**:

1. **The factory's shape (lane A, from the tree):** not `async`, no `yield` in its own
   body, and exactly one plain, undecorated, non-`async` nested `def g` bound once in the
   own body, `g` not a parameter, and some `return g`. Lane A records the own body's
   top-level statements as a small program: a literal or a copied name assigned to a bare
   name; an `if` / `elif` / `else` with its test; `return g` or any other return; `raise`;
   and every other statement as the names it binds (made unknown). A `for`, `while`,
   `with`, `try` or `match` is walked as unknown: every name it binds is made unknown and
   every return in it is reachable.
2. **The site's arguments (lane A):** each positional and keyword argument as a literal —
   `None`, `True`, `False`, a number, a plain string, `()` — or unknown; a `*x` or `**x`
   makes the whole binding unknown.
3. **Binding:** positionals bind the factory's positional parameters in order (for a
   **method** factory, after `self`; and a method factory at a site passing **any**
   positional argument is refused — lane A cannot tell `@obj.f(x)` from `@Cls.f(x)`,
   where `x` would be `self`); keywords bind by name; an unfilled parameter takes its
   literal default, an unfilled `*args` is `()`, anything else is unknown.
4. **The fold:** three-valued (a value, or unknown). Tests read: a literal, a bound name,
   `not`, `and` / `or` with Python's short-circuit, `x is None`, `x is not None`, and
   `callable(x)` — the builtin, where the factory's module binds no `callable` — which is
   false on `None`, `()`, a string, a number or a bool, and unknown otherwise. A known
   test takes one branch; an unknown one both, and the branches' names merge (a name
   keeps a value only where both agree). `raise` ends a path.
5. **Draw** when at least one return is reachable and every reachable return is
   `return g`: a `calls` edge from the decorator's caller to `g`, **`syntactic`**,
   `via: decorator-factory-folded`, evidenced at the callee's line. A factory ADR-147
   already settles is drawn as ADR-147 draws it, never re-folded.

**Refused and counted** beside ADR-147's reasons: `method-positional` (step 3) and
`guard-unknown` (a reachable return other than `return g`, or none). `no-returned-def`
stays for a factory with no such `g` at all.

**Not claimed:** the path any other call takes; what `g` returns.

## Measured (`~/.hobbes/bench/py-optparens/`; `PREREG.md` first, `probe.py`, `RESULTS.md`)

Simulated over click's 0.2.66-beta export, graded by `oracle grade --poison` on
`click-py-r3`: **397 drawn** (`command` 315, `Group.command` 75, `Group.group` 7), **347
confirmed**, 47 on lines the key never ran, **3 suspect**, 0 base rows moved; click
3,356 → **3,703** confirmed (recall 73.6% → **81.2%**), suspect 18 → 21, poison PASS.
`method-positional` refuses 27 sites that `guard-unknown` already refused (non-literal
positionals): the figures do not move. attrs: 18 drawn (`@attr.s(…)`, read by hand,
right; `define` holds two nested defs and is refused); flask 0 (its factories are
decorated).

**The 3 suspects, read row by row** (the pre-registration's P1 failed on them):
`tests/test_arguments.py:61`, `:614`, `tests/test_options.py:110` are `pytest.raises`
tests where the decorator *below* `@click.command()` raises during its own application,
so `command()` ran and its `decorator` was never applied. The edge is the code as
written; the run never reached the application. A trace key cannot contradict it and
buckets it `suspect`. Max chose to own the three rows (route a) over a test-framework
exception in an extraction rule (route b).

## What this leaves

- C-58 keeps: a factory returning another factory's call (click's `group()` →
  `return command(…)`), a factory with two nested defs (attrs' `define`), a guard the fold
  cannot read, a non-literal positional, and every other function value.
- Resolution coverage is not moved: there is no site — no token — to count.

## Built (0.2.67-beta)

Unit `b4d4` (131 turns of 140, $15.98 on the subscription), merged `--no-ff`; one defect
fixed at the review. click on the unit's code: **397 folded, 347 confirmed, 21 suspect
(the 18 and the 3 read above), 3,703 of 4,561 (81.2%), poison PASS, 0 rows lost — the
probe's rows exactly, 4,298 of 4,298** (`oracle-grading.md` §10.33). attrs 18, flask 0.

- **Found at the review:** the first build folded nothing on click. `*args: T` /
  `**kwargs: T` is a `typed_parameter` wrapping the splat, and the signature reader took
  it for an unnameable parameter and dropped the factory; click annotates every factory,
  and the unit's tests wrote untyped ones. The doer's own check fed hand-built digests to
  the fold, which could not see it. Fixed with a test (`39815c0`). What the brief did
  not ask: a factory read from **its real source**, not a trimmed one.
- **Accepted as built, beyond the brief's wording:** a chained assignment (`x = y = 1`)
  makes its targets unknown (the binding walk ADR-145 uses does not see the outer
  target); a statement is read as opaque off *whether it holds a return*, so a block kind
  the walk does not name keeps its returns; the module's `callable` is checked over the
  whole file, any binding form; `@either("d")` in the fixture moved from
  `no-returned-def` to `guard-unknown`, the factory's shape now read before the site's
  arguments.
