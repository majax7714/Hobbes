# ADR-149 — A decorator factory that returns another factory's call

**Date:** 2026-09-21 · **Status:** accepted (Max, 2026-09-21: "good to go with route a") ·
**Owner:** Max · **Source:** ADR-148's *What this leaves* (a factory returning another
factory's call); click's 44 `@click.group(…)` rows on `click-py-r3`, missed at 0.2.67-beta.

Narrows C-58's function-value face for one more shape. Registers nothing new: what the rule
refuses stays in that entry, counted.

## The shape

```python
def group(name=None, cls=None, **attrs):        # click/decorators.py, trimmed
    if cls is None:
        cls = Group
    if callable(name):
        return command(cls=cls, **attrs)(name)  # `@group` bare
    return command(name, cls, **attrs)          # `@group()` / `@group("x")`

@click.group()                                  # the site applies what command(None, Group)
def cli(): …                                    # returned: command.<locals>.decorator
```

`group` holds no nested def, so neither ADR-147 nor ADR-148 reads it. But at `@group()` the
fold of `group`'s own guards leaves one reachable return, `return command(name, cls,
**attrs)`, with `name` still `None`, and the fold of `command`'s guards over *those*
arguments leaves only `return decorator`. The same shape with a settled second factory:
`version_option`, `help_option`, `password_option`, `confirmation_option` and
`custom_version_option` each end `return option(*param_decls, **kwargs)`, and every return
in `option` is `return decorator` (ADR-147's case).

## The rule

Where ADR-147's conditions 1 and 2 hold for a call-form decorator's factory `F` and `F`'s
body carries neither ADR-147's `returns_inner` nor ADR-148's `inner_fold`, the site is
drawn when **`F`'s fold leaves only returns of one second factory `G`'s call, and `G`'s
application to the arguments `F` hands it reaches only `G`'s one nested def**:

1. **`F`'s shape (lane A):** a function or method, not `async`, no `yield` in its own body,
   a nameable signature (ADR-148's), and at least one own-body `return G(…)` whose callee is
   a name chain (`f`, `a.b.f`). Any number of nested defs. The own body is recorded as
   ADR-148's program, with one addition: a `return` whose value is such a call records the
   call — the callee's dotted name, the line of its terminal identifier, each positional
   argument as a literal, a bare name, or unknown, each keyword the same, the index of a
   `*x` argument if one is written, and whether a `**x` is written. Every other return is
   what it was (`return g` / other). A return inside a `for`, `while`, `with`, `try` or
   `match` stays ADR-148's opaque return: it can never be a chain.
2. **`F`'s fold:** the site's arguments bound and `F`'s guards folded exactly as ADR-148
   steps 2–4 (a `*x`/`**x` at the site makes the binding unknown; a method `F` at a site
   passing any positional is refused `method-positional`), keeping **the environment at
   each reachable return**. There must be at least one reachable return and every one must
   be a recorded call (else `chain-guard-unknown`).
3. **`G`, named by the index:** at each reachable return, the settled graph carries a
   `semantic` `calls` edge **from `F`** with evidence at `F`'s file and the callee's line,
   to exactly one function or method named as written (ADR-147's condition 1 at that line);
   and every reachable return names the same `G` (else `chain-unresolved`).
4. **`G`'s application:** `G` has one undecorated, non-stub body (ADR-147's condition 2),
   and either every return in it is `return g` (ADR-147's `returns_inner`: drawn with no
   fold) or it carries ADR-148's `inner_fold`, folded **for each reachable return of `F`**
   over the arguments that return passes, read in `F`'s environment there:
   - a literal passes its value; a bare name passes the value `F`'s fold holds for it, or
     unknown; anything else is unknown;
   - positionals bind `G`'s positional parameters in order (after the receiver for a
     method `G`, and a method `G` called with any positional is refused, as at a site); a
     `*x` makes every `G` positional parameter from its index on unknown, and `G`'s
     `*args` unknown; more explicit positionals than `G` takes, with no `*args`, refuses;
   - keywords bind by name; a `**x` makes every `G` parameter that no explicit argument
     binds **unknown, never its default** (the mapping may hold it); `G`'s `**kwargs` is
     unknown;
   - an explicitly bound parameter keeps its value beside a `**x`: Python refuses a call
     that binds a parameter twice, and a path that raises applies nothing.
   The chain holds only where every reachable return of `G` is `return g`. `G` is never
   itself followed as a chain: one level only. Anything else is `chain-inner`.
5. **Draw** a `calls` edge from the decorator's caller (a symbol or the module node) to
   `G.<g>`, **`syntactic`**, `via: decorator-factory-chained`, evidenced at the decorator's
   callee line — under ADR-147's condition 5 (`<G's id>.<g>` is exactly one `function`
   symbol, else `no-symbol`) and `already-drawn`.

**Refused and counted** beside ADR-147's and ADR-148's reasons: `chain-guard-unknown`,
`chain-unresolved` and `chain-inner`. `no-returned-def` stays for a body none of the three
rules reads.

**Not claimed:** the path any other call of `F` or `G` takes; what `g` returns; any chain
of two or more hops.

## Measured (`~/.hobbes/bench/py-factory-chain/`; `PREREG.md` first, `probe_chain.py`, `RESULTS.md`)

Simulated over click's 0.2.67-beta export, graded by `oracle grade --poison` on
`click-py-r3`: **66 drawn** (`group`→`command` 50, folded; the five `*_option` → `option`
16, settled), **51 confirmed**, 15 on lines the key never ran (`examples/`,
`tests/typing/`; read by hand, each right), **0 contradicted, 0 new suspects**, 0 base rows
moved; click 3,703 → **3,754** confirmed (recall 81.2% → **82.3%**), suspect 21 → 21, poison
PASS. The pre-registration's P2 range (44–50) was exceeded by one row: `custom_version_option`
chains to `option` as well. attrs 0, flask 0, this repo (at `2c915a8`) 0.

## What this leaves

- C-58 keeps: a chain of two or more factories, a chain whose second factory the index does
  not name at the return, `Group.command` called with a positional at a method site (click's
  `@cli.command("sdist")`, 10 rows, `method-positional`), a decorator held in a variable,
  and every other function value.
- Resolution coverage is not moved: there is no site — no token — to count.
