# ADR-145 — A call on the value a fixture constructs is a call on that class

**Date:** 2026-09-20 · **Status:** accepted and **built** (0.2.63-beta, unit `1527`; Max, 2026-09-20: route (a) — as
worded, `syntactic`, through ADR-137's own lookup before a dispatch), to be
built as one dispatched unit; measured and simulated before anything was drawn;
**amended 2026-09-22** (Max: route a — the value through a local, and an inherited
method; *Amendment*, below) ·
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

## Built (2026-09-20, 0.2.63-beta)

Unit `1527` (81 turns of 140, $6.73; gate right-clear, verify pass, 11 files at file
grain) built the pipeline's half as briefed: `Symbol.value` and `Symbol.rebound` in
the Python walk, `fixtures.value_calls`, `_add_value_call_edges` after the
injections (before `collect_tests`, so reach follows), one clause on the ingest's
`fixtures:` line, the `minifixval` fixture and its `lane_b` case. The denominator
statement (the proxy's and the manifests'), the register, the version and the
records are the developer's commit.

- **On the host before the merge**, in a worktree of the branch: 2,191 pytest, all 14
  `lane_b` (the new case's first contained run).
- **The real cell:** click **1,755 → 2,136 confirmed, 0 contradicted or newly
  suspect, recall 38.2% → 46.5%**; 382 rows, all `syntactic`, no row lost, no tier
  moved. Six other-language cells row-identical (`oracle-grading.md` §10.29).
- **The build is stricter than the probe, rightly:** the simulation's 383rd site is a
  `runner.invoke` inside a nested `def` of a click test; the probe's walk entered
  it, the rule's *own body* condition refuses it.
- **Kept from the doer:** the conditions asked in the ADR's order, the first failure
  the one counted; a `yield from` reads as a valued exit the rule cannot read; a
  method counted in the class's own module record, because duplicate qualnames
  collapse in the graph's symbols; this repo 24 sites, 0 drawn, as measured.

## Amendment (2026-09-22, accepted — Max: "good to proceed with recommended route") — the value through a local, and an inherited method

Measured first on a new keyed cell (`~/.hobbes/bench/c4-local-value/`; `PREREG.md` and
`PREREG-worded.md` written before each probe's first run). Narrows C-4 again; registers
nothing new.

**The shape.** flask's `app` fixture is the form C-4 kept:

```python
@pytest.fixture                          # tests/test_basic.py
def app():                               def test_url_generation(app):
    app = Flask("flask_test", …)             @app.route("/hello/<name>", methods=["POST"])
    app.config.update(TESTING=True, …)       def hello(): …
    return app
```

The index names `Flask` at the assignment (a `semantic` `calls` edge
`tests:conftest.app → flask.app.Flask`, evidence at line 29), exactly as it names
`CliRunner` at click's `return CliRunner()`. The value that comes back is the one that
assignment constructed: a local bound once, by a construction, holds nothing else.
And most of what a test calls on it is not `Flask`'s own: `route`, `get`, `post`,
`errorhandler` are `Scaffold`'s, `add_url_rule` and `register_blueprint` are `App`'s
(`class Flask(App)`, `class App(Scaffold)`). ADR-145 refused those as inherited
because no probed cell had one. flask is that cell.

**Condition 2, amended.** The fixture's one valued `return` / `yield` is `C(…)` (as
before) **or a bare name `x`** where all hold:
- `x` is no parameter of the fixture;
- the fixture's own body binds `x` **exactly once**, by a plain assignment statement
  `x = C(…)` written at the **top level** of that body (one bare-identifier target, a
  call on a bare name), on a line before the return;
- no `nonlocal x` or `global x` is written anywhere in the fixture, nested definitions
  included (a nested def could rebind it).

Condition 3 then asks for the class edge at the assignment's line, under the written
name. Nothing else changes: an alias, a factory function (`create_app()`), a
`return app.test_client()` stay refused.

**Condition 4, amended: an inherited method.** Where `m` is not a `def` in `C`'s own
body, the rule asks the same question of `C`'s base, and so on up, while all hold at
each class `K` on the path:
- `K`'s own body binds `m` by no other form (an assignment, an import, a nested
  `class m`) — else refused, **`class-binds`**: a class attribute named `m` shadows any
  base's `def m`;
- `K` names **exactly one** base (lane A's count; `metaclass=` and other keywords are not
  bases) — none is `no-method` (what `object` has is not in the repo), more than one is
  refused, **`multiple-bases`**: the rule does not compute an MRO;
- the index names **exactly one** class symbol from `K`, on `K`'s own `class` line (a
  `semantic` edge of any type — a base written on a later line of a split header is not
  read) — else refused, **`base-unnamed`**: an out-of-repo base (`FlaskClient(Client)`) is
  where the walk must stop, because the method may be the base's.

The first class on the path whose own body has `m` as one `def` is the target, under
condition 4's own tests (defined twice → `no-method`; a property → `property`). A walk
that meets a class twice stops (`no-method`).

**Refused, new: an instance patch** (`patched`). A site is refused where the requester
stores or deletes `p.m` or `p.__class__`, or passes `p` first to a call named `setattr`
(`monkeypatch.setattr(p, …)`, `setattr(p, …)`) — and, for the local form, the same of `x`
in the fixture. The trace would see the patch; the graph would name the class's `def`.
It applies to the construction form too: ADR-145 never asked it (0 sites on click).

Tier, evidence and the rest are ADR-145's: `calls`, **`syntactic`**, `via:
fixture-value`, a pair the graph already carries left alone.

### Measured (the probe as worded, over each cell's own 0.2.68-beta graph)

The flask key is new (`docs/oracle/cells/flask-py-2026-09-22.md`): pallets/flask at
`d73fa1c`, py-trace, contained, 494 passed both runs; at 0.2.68-beta 1,330 edges,
**1,121 of 2,698 (41.5%)**, 18 suspect, poison PASS.

| cell | sites | drawn | direct / inherited | judged |
|---|---|---|---|---|
| flask (new key) | 778 | **400**, all the local form | 71 / 329 | **400 confirmed at the exact target line, 0 contradicted**; all 400 missed pairs today |
| click (`click-py-r3`) | 382 | 0 new — ADR-145 draws all 382 | — | unchanged |
| attrs | 5 | 0 | — | — |
| this repo | 27 | 1 | 0 / 1 | `minifixval`'s `runner.close()` → `Base.close`, right by reading |

flask's recall would read **1,121 → 1,521 of 2,698 (41.5% → 56.4%)**. The targets were
read by hand along `Flask(App(Scaffold))`: `add_url_rule` is `App`'s override (605), not
`Scaffold`'s (376). The `setupmethod` wrappers are keyed as the wrapped `def` (py-trace
`via: wrapped`). Thirty-seven of the 400 are bare decorators (`@app.teardown_appcontext`)
lane A already reads as calls (ADR-146).

**The nodes.** The rule mints nothing; every target is a symbol today.

**What the evidence is, plainly.** One more keyed repo, one fixture carrying 400 rows,
and a three-class chain. The inherited half rests on the index naming each base at its
header line — in flask, `Flask → App` is only a `uses` edge there: the `implements`
edge ADR-120 would draw is absent (lane A names `src/flask/sansio/`'s files `app` and
`scaffold`, a namespace package with no `__init__.py`; why the join places `App →
Scaffold` and not `Flask → App` is not yet read). The rule reads the header edge, not
`implements`, for that reason.

### What this leaves (C-4)

A fixture value that is not a construction bound once (`return app.test_client()`, a
factory's return), a class with two bases or an unnamed one, and ADR-137's abstentions.
A method the class *could* dispatch through `__getattr__` or a metaclass is not asked:
the rule reads the `def` Python finds first on a single-base chain, and a class that
overrides attribute lookup is not detected.
