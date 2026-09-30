# ADR-153 — A bare call to the one def its own function writes is drawn by lane A

**Date:** 2026-09-30 · **Status:** accepted (Max, 2026-09-30: "good to proceed with route a") and **built** (0.2.73-beta, unit `99dc`) ·
**Owner:** Max · **Source:** ADR-150's route c, left "to be measured on its own". Measured and simulated this
session: `~/.hobbes/bench/py-route-c/` (`PREREG.md`, `probe.py`, `RESULTS.md`; `PREREG-sim.md`,
`ingest_rule.py`, `sim.sh`, `sim/`).

Narrows **C-170**. Draws more, at the `syntactic` tier.

## What is missing

ADR-150 refuses a moniker scip-python gives several definitions in one file, which is every
def nested in a method that shares its name with a def nested in a sibling method. A
reference to one of them has no lane B answer (C-170). Lane A sees the site and has no rule
for it: `resolve_call_sites` resolves a bare name to a module-level symbol or an imported
one, never to a def written in the calling function (the tail calls the site
`local-binding`).

```python
class TestStreaming:
    def test_streaming_with_context(self, app, client):
        @app.route("/")
        def index():
            def generate(): …
            return flask.Response(flask.stream_with_context(generate()))   # no edge
```

Python's own rule for that name is syntax: a name a function binds is local to it, and if
the function's only binding of it is one `def`, a call of the name that succeeds calls that
def.

## Measured

The rule as worded below, read with `ast` over five Python cells before anything was built:

| cell | sites | lane B draws it already | new | key: confirmed / unobserved / contradicted |
|---|---|---|---|---|
| flask | 34 | 29 | 5 | 33 / 1 / 0 |
| click | 35 | 32 | 3 | 25 / 10 / 0 |
| hobbes-py @ `2c915a8` | 257 | 257 | 0 | 231 / 25 / 0 |
| attrs | 16 | 16 | 0 | no key |
| missy | 83 | no export | — | no key |

- No site is wrong: 0 contradicted on three trace keys, and on the 334 sites lane B already
  draws, the rule names the same def every time.
- 3 sites are refused because the scope binds the name twice (a second `def`). Lane B draws
  all three.
- The 8 new sites are the seven ADR-150 named (flask `tests/test_helpers.py` 237, 251, 281,
  296, 310; click `src/click/core.py` 1836, 1888) and click `src/click/_termui_impl.py:816`,
  a line the ingest's index is silent on.
- Simulated in memory through the real join (`sim.sh`): the exports differ by exactly those
  8 `syntactic` edges, nothing removed, no tier moved. flask 1,519 → 1,524 confirmed (56.3% →
  56.5%), click 3,754 → 3,756; 0 contradicted; poison PASS. ADR-111's veto stays quiet on
  C-170's in-repo external reference, as ADR-150 said it would.

## The decision

Lane A proposes, through the fallback the join already reads, a bare-name call to the one
def its own function writes.

1. **The scope's fact (in `pysource`, which owns the grammar).** For each function
   definition F, the names F's own scope binds **exactly once, by a `def`** written in F's
   own body — at its top level or inside an `if`, `try`, loop or `with`, never inside a
   nested def, class or lambda. A name is left out when F's scope binds it any other way:
   - a second `def` or a `class` of that name in F's own body;
   - a parameter of F, of any kind;
   - an assignment, augmented assignment, annotated assignment with a value, walrus,
     `for`/`with`/`except` target, import, or `del` of the name in F's own body;
   - a `global` or `nonlocal` naming it anywhere under F, nested definitions included;
   - a lambda parameter or a comprehension `for` target of that name anywhere in F's own
     body (the call might be inside that lambda or comprehension, where the name is the
     parameter's or the target's).

   A function whose own body holds a `match` statement or a `type` alias statement has no
   such names at all: both bind names, and the walk's binding read does not cover them.
   A name N is also left out where the file writes `F.N` more than once (an `if`/`else`
   pair of `def F`, each nesting a `def N`): the graph keeps one symbol per qualname, the
   first. *(Corrected at the unit's review, 2026-09-30: the first form refused every F
   whose qualname a second definition shares. click's `Group.command` and `Group.group`
   are two `@overload` stubs and an implementation, so that form drew neither of click's
   rows. The fact carries each definition's lines, and the call's line says which
   definition it is written in.)*
2. **The site.** A call whose callee is a bare name N, whose scope (the innermost enclosing
   definition, as lane A already records it) is F, where N is one of F's names from step 1.
   A call in a nested def, or in a class body inside F, has another scope and is not this
   rule's.
3. **The target** is the symbol `F.N`. `resolve_call_sites` asks this rule before its
   module-level rule, as Python resolves the name. The join stamps what it uses `syntactic`,
   and lane B's answer wins wherever it has one.
4. **A decorated def counts** (Max's route a). `@dec def N` binds N to what `dec` returned;
   lane B already draws such a call to the def, and the trace keys confirm the three in
   flask `via: wrapped`. The `syntactic` tier is the statement that this is syntax.
5. **Not guarded, on purpose.** A call written above the def, or a def inside a branch that
   did not run, raises `UnboundLocalError`: the name has no other binding, so no call of it
   reaches anything else.

## Not taken

- **Refusing a decorated def** (route b): 4 of the 7 rows, and a rule stricter than lane B's
  own reading of the same shape.
- **The outer reach** — a sibling closure's call, a def's own recursion, where the binding
  scope is a function further out. Lane B draws every such site measured (64 of 64 with an
  export); nothing to gain, and the scope chain is more machinery.

## What it costs

Lane A now answers at a few hundred sites where lane B already does, so `hobbes lanes`
compares more sites. A disagreement there would be a finding: the simulation's cells showed
none from this rule.

## What this leaves

C-170 keeps every reference that is not a bare call from the def's own function: a nested
def passed as a value, and a call from a sibling closure to a conflated name.

## Built (0.2.73-beta, unit `99dc`)

As decided, with one defect fixed at the review (`80d2136`), and it was this ADR's: step
1's refusal of a shared qualname, corrected above. The probe and the simulation had not
modelled that refusal, so neither saw it; the real cell did (flask's five rows drawn,
click's two not). Host: pytest 2,464, `lane_b` 17 of 17. flask 1,519 → 1,524 confirmed
(56.3% → 56.5%), click 3,754 → 3,756; 0 contradicted and poison PASS on both; both exports
identical to the simulation's (`oracle-grading.md` §10.37).
