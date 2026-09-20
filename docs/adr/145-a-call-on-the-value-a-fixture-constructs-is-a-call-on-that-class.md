# ADR-145 — A call on the value a fixture constructs is a call on that class

**Date:** 2026-09-20 · **Status:** accepted (Max, 2026-09-20: route (a) — as
worded, `syntactic`, through ADR-137's own lookup before a dispatch), to be
built as one dispatched unit; measured and simulated before anything was drawn ·
**Owner:** Max ·
**Source:** C-4's remainder ("a method on the value a fixture returns … the
larger loss on click, not counted"); his standing direction — honesty and
accuracy before a recall number, and a rule fails toward drawing less.

Narrows C-4. Registers nothing new: what the rule refuses stays in that entry.

## The shape

```python
# tests/conftest.py            # tests/test_arguments.py
@pytest.fixture                def test_file_args(runner, tmp_path):
def runner(request):               result = runner.invoke(inout, […])
    return CliRunner()
```

Nothing is drawn at `runner.invoke`. The index names the *parameter* at `runner`
(an in-repo `external_ref`, `test_file_args().(runner)`) and emits **nothing** at
`invoke`: scip-python does not type an unannotated parameter. What it does name
is the class, at the fixture's `return CliRunner()` — a `semantic` `calls` edge
`conftest.runner → click.testing.CliRunner` the graph already carries, evidence
at that line. And the parameter's fixture is ADR-137's `uses` edge. Both hops
are drawn today; the call between them is the silence.

On click it is most of the method misses: of 665 missed `observed→method`
pairs, 419 sit at `p.m(…)` on a parameter in a test file, 381 of them `runner.*`
(`count.py`).

## The rule

A call `p.m(…)` written in a **test or fixture function's own body** (not a
nested def or lambda) draws a `calls` edge to `C.m`, tier **`syntactic`**,
evidence at the call's line with `via: fixture-value`, where **all** hold:

1. `p` is a parameter ADR-137's lookup resolves to one repo fixture F (`via:
   parameter` only — a mark or autouse binds no name), and the function's own
   body never binds `p` again;
2. F's own body has **exactly one** `return` / `yield` that carries a value, and
   the value is a call whose callee is a bare name, `C(…)`;
3. the graph carries a **`semantic` `calls` edge from F to a class symbol** named
   as written, with evidence at that line — the index naming the class, not lane
   A's import reading;
4. `m` is **one** `def` in that class's own body, and not a `property` /
   `cached_property`.

A construction fixes the runtime class exactly — `C(…)` is a `C`, never a
subclass — so `C.m` defined on `C` is what runs. That is a narrower claim than a
return annotation would be, and the reason annotations are not read.

**Refused, each counted by reason in the `fixtures` block:** a rebound
parameter; a fixture with no, or more than one, valued return; a returned value
that is not `C(…)` (`return app`, `return app.test_client()`); no semantic class
edge at the line (lane B absent or silent, an alias whose written name is not
the class's); `m` not a `def` on `C` itself — **inherited methods are refused**:
the simulation met none, and a rule is shipped as far as it was probed; a
property; `m` defined twice.

Without lane B the rule draws nothing: condition 3 cannot hold.

## Measured and simulated (`~/.hobbes/bench/c4-returned-value/`; `PREREG.md` written first)

`simulate_real.py` takes the fixture from `hobbes.extract.fixtures.injections`
itself and the class from the cell's cached index facts; in memory, nothing
drawn. `simulate.py` was the first form, with a stand-in lookup — same rows.

| repo | `p.m(…)` sites on an injected parameter | drawn | judged |
|---|---|---|---|
| click (py-trace key, `click-py-r2`) | 383 | 383, all direct | **381 confirmed, 0 contradicted**, 2 on lines the key never ran |
| flask (held out; no trace key) | 734 | 11 (`auth.login` / `auth.logout` → `AuthActions`) | read by hand: 11 right |
| attrs | 5 | 0 | — |
| this repo | 24 | 0 | — |

Every prediction held (P1–P4). click's recall would read 1,755 → 2,136 of 4,595
(38.2% → 46.5%). flask's 702 refusals are `return app` and
`return app.test_client()` — a value's type, not a construction; they stay C-4's.

**The nodes (ADR-129's lesson).** The rule mints nothing: its three click
targets (`CliRunner.invoke`, `.isolation`, `.isolated_filesystem`) are symbols
today.

**What the evidence is, plainly.** One trace-keyed repo and one fixture carry
381 of the 392 rows; the held-out read is 11 rows by hand. No second Python
repo with a trace key and a clone is on this box (hobbes-py's clone is gone).
The rule's claim is small enough to read — a construction, a name lookup, a
`def` in a class body — and it abstains everywhere else; that, not the row
count, is why it is proposed as worded.

## What this leaves

- C-4 keeps: a fixture value that is not a construction (flask's `client`), an
  inherited method, and every ADR-137 abstention.
- **Test reach follows these edges as it follows any `calls` edge** — that is
  the prize: a click test now reaches `CliRunner.invoke` and what it calls. The
  edge's tier says how far to trust it; `through_fixtures` does not change
  meaning (it is about `uses` injections).
- **Resolution coverage is not moved.** The site stays counted `attr-call` in
  the file's tail: the join did not resolve it, and the percentage stays a
  floor. The `fixtures` block counts what this rule drew and refused.
- No trace key judges the *caller* side differently: the key's pair is (site,
  target), which is what the rule draws.

## Accepted (Max, 2026-09-20: route a) — the code facts the unit rests on

Read in the tree at `ff92e07`:
- `fixtures.injections(modules, parsed)` returns `{"from","to","path","line",
  "name","via"}` rows; `extract/__init__.py` calls it after the projection
  (`with timings.step("fixtures")`), then `_add_injection_edges(graph, drawn)`
  appends `uses` edges with `tiered_edge(…, tier=SYNTACTIC,
  lane=LANE_TREE_SITTER)` and re-sorts by `_edge_order`. `graph["symbol_edges"]`
  is settled at that point, so the class edge of condition 3 can be read there.
- click's graph at 0.2.62-beta carries `{'from': 'conftest.runner', 'to':
  'click.testing.CliRunner', 'type': 'calls', 'tier': 'semantic', 'evidence':
  [{'lane': 'scip', 'line': 8, 'path': 'tests/conftest.py'}]}` and the class
  symbol `{'id': 'click.testing.CliRunner', 'kind': 'class'}`; its methods are
  symbols `click.testing.CliRunner.invoke`, kind `method`.
- `pysource.Symbol` carries `params` as `(name, line)`, `decorators`, `line`,
  `end_line`; `pysource.Call` carries `scope` (the innermost enclosing
  definition's qualname), `callee` (a dotted chain, `runner.invoke`), `line`,
  `col`. Neither a definition's returned value nor a rebinding of a parameter
  is recorded today — the walk gains both.
- A module-level `pytestmark` is a count today (`ParsedFile.pytestmark_usefixtures`);
  that is ADR-139's amendment, a separate unit.
