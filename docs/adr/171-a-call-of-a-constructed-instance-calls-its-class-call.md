# ADR-171 — A call of a constructed instance calls its class's `__call__`, drawn `syntactic`

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: "good with route one and to proceed after ast
scan … go for diversity") and **built** (0.2.100-beta) · **Owner:** Max · **Source:** step 0
(`~/.hobbes/bench/instance-call/step0.py`, fitted cells only); the held-out structlog pre-registration
(`~/.hobbes/bench/heldout-structlog/PREREG.md`, sha256 `d65d5f69…471f`, S1–S4, P1–P2, F1–F2, the rule's
wording frozen before the ingest and the key).

Narrows **C-174** (a call the language makes with no call token), Python. Draws a new kind of edge.

## What is missing

Calling an instance runs `type(obj).__call__`, and the source writes no name for it:

```python
highlighter = ReprHighlighter()          # calls rich.highlighter.ReprHighlighter (semantic)
…
text = highlighter(line)                 # nothing drawn; tail `local-binding`
TimeStamper(fmt="iso")(None, None, ed)   # nothing drawn; tail `expr-callee`
```

At the bound form the index names the local (C-9); at the direct form the callee is an expression with no
identifier (C-63). The trace keys both to the method that ran (`trace_oracle.py`, `via: "__call__"`). Of
C-174's Python shapes this is the only one beyond `with` the trace key sees: operators, iteration, truth tests
and the builtins (`str`, `len`, `hash`) reach C callees it does not key.

## Measured (step 0, fitted cells, no code changed)

Read with `ast` under the rule's conditions below, the class through `withstmt._item_class` and the method
through `fixtures._class_method` against the 0.2.99 graphs, each site checked against the stored key at the
grader's grain: **rich 7 rows, 6 confirmed, 1 not executed** (`Highlighter.__call__`,
`ProgressColumn.__call__`, all bound); **flask 0, click 0** (every site abstains). The fitted cells' `__call__`
misses (rich 27, click 7, flask 1) are mostly an instance held in an attribute (`self.highlighter(…)`), which
this rule does not read. The rule's evidence is the held-out cells, picked before it was measured: structlog
26.1.0 by an `ast` scan of ten candidates for diversity (a logging library whose processors are called
instances; 136 name-matched written sites over 31 classes), and pyparsing, partially seen (its count of
`__call__` misses was read during scoping; no row).

## The decision

1. **Sites (lane A, `pysource`).**
   - *Direct:* a call whose callee is itself a call on a name or an attribute chain of identifiers
     (`C(…)(…)`, `mod.C(…)(…)`), at any scope lane A records (`ParsedFile.instance_calls`: the scope, the
     inner callee's terminal identifier's line and name, the outer call's line).
   - *Bound:* a name N a function's own scope binds exactly once, by a plain `N = R` where R is a call on a
     name or an attribute chain (parentheses around R unwrapped), under every refusal ADR-160 step 1 lists
     (`_local_aliases` with `_instance_binder`); kept only where a bare `N(…)` in that scope uses it
     (`ParsedFile.local_instances`). Module-level bindings are not read.
2. **The class**, read off the settled graph (`instcalls._call_method`): the scope's `semantic` `calls` edge
   with an evidence row at the callee's line whose target's last name is the callee's — exactly one, and a
   **class**. A def (an annotated factory) abstains `not-a-class`: its return is a declared type, and a
   subclass instance with its own `__call__` would make the edge wrong. A class that writes a `def __new__`
   on its chain of single named bases abstains `defines-new`: the construction may return something else.
3. **The method:** `__call__` by ADR-145's `_class_method` walk (one `def`, not a property, first on the chain
   of single named bases; a class body binding the name otherwise, two bases, or a base the index does not
   name stops it, with that reason).
4. **The edge:** `calls` from the scope (the module for a module-level direct site, as a module-level `with`)
   to the `__call__`, **`syntactic`** (the class is the index's answer at the construction; the instance's
   path to the call is read from syntax — Max, 2026-10-02), evidence `{path, line, via: "__call__"}` at the
   outer call's line. A pair the graph already carries a `calls` edge for is `already-drawn`. Counts go to
   `graph["instance_calls"]` (`sites`, `drawn`, `abstained` by reason), absent where no file holds a site.
5. Without lane B there is no `semantic` edge at the construction, so nothing is drawn (P6). Resolution
   coverage is not moved: the join did not resolve the site.

## Not taken

- **`semantic`.** The index never names the method at the call.
- **Annotated factories** (ADR-156 reads them for `with`): a declared type, not the instance's class; step 0
  drew none on the fitted cells either way.
- **An instance held in an attribute or a parameter** (`self.highlighter(…)`, the fitted cells' main
  misses): the class is not written at the scope; it would need the attribute's assignments read across
  methods, a type inference this layer does not do.
- **Operators, iteration, truth tests, the builtins:** the key cannot judge them (C-60's trace, H-37's
  precedent); each needs an oracle change first.

## What this leaves (C-174, Python)

An instance held anywhere but a once-bound local or the call's own callee; a factory's result; a class whose
`__call__` lives on an out-of-repo base or past two bases; a metaclass or out-of-repo base whose `__new__` or
`__call__` returns another type (the rule reads only the in-repo chain for `__new__`), registered as the
residual; and every other implicit dunder.

## Built (0.2.100-beta)

`extract/pysource.py` (`InstanceCall`, `ParsedFile.instance_calls`, `ParsedFile.local_instances`,
`_instance_binder`, `_local_aliases(…, binder)`, `_called_local_aliases(…, recorded)`),
`extract/instcalls.py`, `extract/__init__.py` (after the `cls` step; `_add_with_call_edges(…, via=)`). Tests:
`test_instcalls.py` (lane A's records and refusals, every abstention on the `miniinst` fixture with its edges
written out) and `test_instcalls_lane_b.py` (the whole ingest on the host: three edges, `defines-new`,
`not-a-class`, `no-method`). The fixture is rich's `Highlighter` chain.

**Regrade** (`~/.hobbes/bench/instance-call/run.sh`, `after/`; stored keys, poison on, all PASS; host
`lane_b` 28 of 28, pytest 2,817):

| cell | confirmed | suspect | recall | sites / drawn |
|---|---|---|---|---:|
| structlog (held out) | 1,110 → **1,240** | 11 → 11 | 69.7% → **77.8%** | 160 / 134 |
| pyparsing (held out) | 3,529 → 3,552 | 68 → 68 | 50.8% → 51.1% | 357 / 56 |
| rich | 5,019 → 5,025 | 44 → 44 | 93.5% → 93.6% | 15 / 7 |
| icalendar, flask, click | unchanged | unchanged | unchanged | 21, 26, 42 / 0 |

Every export row the rule added is its own (`via: "__call__"`), none removed; 0 contradicted.

**The pre-registration, scored.** S1–S4 met: structlog drew 134 sites (130 rows, ≤ 136), all 130 confirmed,
none wrong, +8.2 points. **P1 missed** (≥ 100 rows on pyparsing): 55. Of pyparsing's 357 sites 275 abstain
`no-call-edge`; 196 of the direct ones are `pp.X(…)(…)`, read through its star re-export, which ADR-161
refuses before the join (C-178), so no construction edge exists to read. The prediction counted written sites
and did not subtract a registered refusal. P2 met (0 new suspects; the 32 new unobserved rows are `examples/`
and `dest/` code no test loads, read in source and correct). F1 met (rich +6 confirmed, 0 suspect; its one
unobserved row read correct). F2 met.
