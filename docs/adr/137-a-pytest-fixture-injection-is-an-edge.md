# ADR-137 — A pytest fixture injection is an edge the test's reach follows

**Date:** 2026-09-19 · **Status:** accepted (Max, 2026-09-19: "recommended route is good" — route a); the premises read in the tree before the brief (*Accepted*), and built (0.2.49-beta; *Built*, below).

Follows ADR-007 (test reach is the closure over `calls` edges; fixtures
are dynamic injection and out of static scope) and the 2026-09-16
top-level review's recall item, "pytest fixtures as syntactic edges
(C-4)". A build would be a patch: a constraint's fix (C-4).

## Context

C-4 has stood since M1: a test that exercises code only through a
fixture does not reach it. `tests_guarding`, behavioural coverage and
`hobbes review`'s "new code no test reaches" all read a fixture-heavy
suite as thinner than it is. The status is *partial*: the denominator
statement names it, and no answer a human reads does.

Injection is dynamic, but its **lookup is not**. pytest resolves a
parameter name to a fixture by a fixed order that is all syntax: the
test's class, the test's file (a name imported into the file counts as
the file's), then `conftest.py` in the file's directory and each
directory above it. Everything that order needs is in the tree lane A
already parses.

One warning from the record: the oracle lane's first Python triage (O6,
2026-08-25) found six executed syntactic edges, all wrong, all a call
*on* a fixture parameter name-matched to the fixture function
(`graph.py`, `_shadowed`). That was a `calls` edge from `runner(...)` to
`def runner`. An injection is a different fact — *pytest* calls the
fixture, on the test's behalf, before the test runs — and it must not be
drawn as a call the test wrote.

## The measurement (`~/.hobbes/bench/c4-fixtures/`, key-free, nothing drawn)

`probe.py` reads an ingested repo: every `@pytest.fixture` /
`@fixture` function in a test file or a `conftest.py` (the `name=`
alias read), every parameter of a test or a fixture that is not
parametrized, defaulted, `self` or `cls`, and pytest's lookup order.
`compare.py` sets the result against **pytest's own answer** —
`pytest --fixtures-per-test`, collection only, which lists every
fixture a test ends up with, transitively, with file and line.

| | this repo (`a930ba1`, 0.2.48-beta) | click (`36baa15f`) |
|---|---:|---:|
| pytest tests | 2,023 | 538 |
| fixtures defined | 84 (15 in a class, 2 autouse) | 3 |
| injections resolved | 1,008 (898 the file or class, 110 a conftest or an import) | 316 (one fixture, `runner`, the conftest's) |
| injections that name no repo fixture (`tmp_path`, `monkeypatch`, a plugin's) | 994 | 100 |
| tests with a resolved injection | 862 | 316 |
| tests whose reached-module set grows | **317** | 316 |
| tests reaching nothing today that would reach something | **233** | 236 |
| modules newly guarded | 0 | 0 |

**Against pytest, on this repo: 1,004 test–fixture pairs, 1,004 right, 0
wrong, 0 missed** over 1,906 tests compared (6 key tests sit at a line
with no graph symbol; the atlas0 suite was not collected). The first
form of the rule — the file, then the conftest chain, abstaining on a
name defined twice in one file — read 902 right, 0 wrong, 102 missed:
76 a fixture imported by name from another test file, 26 a class's own
fixture. `probe-v1.py` keeps that form. click's one fixture was read by
hand, not keyed: the oracle's clone has a host-path venv and collecting
it would run repo code outside the image (ADR-092).

Two things the numbers say plainly:

- **The prize is the test's side, not the module's.** No module goes
  from unguarded to guarded on either repo. What changes is that 233
  tests here stop reading `reaches: []`, and a changed module's guard
  list grows by the tests that set it up through a fixture.
- **On click the edge buys one symbol per test** (`CliRunner`'s
  constructor). click's real fixture loss is `runner.invoke(cli)` — a
  method call on the *value* the fixture returns, which needs the
  fixture's return type at the parameter. That is a typing question for
  lane B (scip-python does not type an unannotated parameter), not this
  ADR's. How many of click's 665 missed `observed→method` pairs it
  accounts for was not counted. Registered under C-4's remainder if this
  is built.

**What no key judges.** The trace oracle records the *caller* of a
fixture as pytest's own frame, so a stored py-trace key neither confirms
nor contradicts a test→fixture edge: graded cells stay row-identical by
construction, and `--fixtures-per-test` is the only key there is.

## Decision (proposed)

Lane A's Python walk records **injections**: for a test function or a
fixture function, each parameter that pytest's lookup order resolves to
exactly one fixture definition in the repo. It abstains — and counts —
where the name resolves to nothing in the repo (a builtin or a plugin's),
to two definitions at one scope, or is parametrized or defaulted.
`usefixtures` marks and `autouse` fixtures are not parameters and are
left out of the first unit, counted.

The edge is **not a `calls` edge**. The test map follows an injection
into the fixture and then the fixture's own `calls` closure, and
`tests.json` says which reached modules were reached *only* through a
fixture, so `tests_guarding` and `hobbes review` can label the step.

## Routes for Max

- **(a, recommended) A `uses` edge plus a labelled step.** Draw
  test→fixture as a syntactic-tier `uses` edge with its evidence at the
  parameter (true as a dependency: the test names the fixture);
  `graph.json` gains a `fixtures` block (injections drawn, and the
  abstentions by reason); the test map follows injections; a
  `tests.json` record gains `through_fixtures`, and `tests_guarding`
  prints "through fixture `x`" on those lines. No schema type is added.
  *Effect here:* 317 tests' reach grows, 233 stop reading empty; click's
  316 gain `CliRunner`; no graded number moves. C-4 partial → surfaced,
  its remainder named (the injected value's type, `usefixtures`,
  autouse, plugin fixtures).
- **(b) A new edge type, `injects`.** The same facts, typed on their
  own. Cleaner to query, and a schema move: about nine files enumerate edge
  types today (the knowledge server, `graphdiff`, `impact`, `ground`,
  `template`, the oracle's export and adapters), and a foreign-graph
  comparison would carry a type no other tool has. Ask first; this is
  closer to structural.
- **(c) Surface only.** Draw nothing; where `tests_guarding` answers
  for a module, say how many of the tests in its directory take repo
  fixtures Hobbes does not follow. C-4 partial → surfaced, reach
  unchanged. Cheapest, and the 233 tests still read empty.

## Alternatives considered

- **Draw it as `calls`.** Wrong by the O6 triage's own lesson: the test
  wrote no call, and the trace key would read every such edge as
  unexecuted.
- **Follow every `uses` edge in reach.** `testmap.py` refuses this on
  purpose (reach must not widen to code a test merely names).
- **Resolve by bare name across the repo.** This repo defines `repo` as
  a fixture in at least nine test files; a name match picks one of
  them, and the other tests get the wrong one. The lookup order is the rule or there is no rule.

## Consequences

- A pre-registration for the build's check: on this repo, pairs against
  `--fixtures-per-test` 1,004 ± 5 right and **0 wrong**; one wrong pair
  stops the unit. A second, held-out Python repo with a real fixture
  tree is collected in the image before the unit merges.
- `tests.json` grows a field; `hobbes review`'s coverage verdicts can
  move on a fixture-heavy repo (toward fewer "unguarded" lines), and the
  CHANGELOG says so.

## Accepted — route (a), and the premises read before the brief (2026-09-19)

Read in the tree, because a brief's premises have been wrong before
(ADR-134):

- **A Python `Symbol` carries no parameters.** `pysource.Symbol` is
  qualname, name, kind, the two lines and its decorators. The unit adds
  the parameter names (undefaulted, not `*args`/`**kwargs`) with their
  lines. A `Decorator` keeps only string-literal arguments, so
  `@pytest.fixture(name="x")` is readable as it stands and
  `@pytest.mark.parametrize(["a", "b"], …)` is not: the walk records the
  parametrized names itself, in either spelling, and a function whose
  parametrize argument it cannot read abstains whole.
- **`autouse=True` is not a string literal and is dropped by the walk.**
  The *Decision* said autouse fixtures are "left out, counted". They are
  left out and **not** counted; `usefixtures` marks are counted. C-4's
  remainder names both.
- **Imported names are already resolved**: `graph._NameEnv.bindings`
  holds `("symbol", module, name)` for `from x import y`. It is private
  to `graph.py`; the unit exposes the read rather than re-deriving it.
- **The projection is the only producer of symbol edges (ADR-031)**,
  keyed `(from, to, type, tier, lane)` and sorted. The injection edges
  are appended inside `_build_symbol_layer`, after the projection, as
  `uses` / `syntactic` / `tree-sitter` — a combination no edge has today
  (every `uses` edge is lane B's) — and the list is re-sorted by the
  same key, so ADR-031's sentence stays true.
- **`conftest.py` is not a test file** to `testmap.is_test_file`, so a
  conftest is a *source* module in `reaches_modules`. Following an
  injection into a conftest fixture therefore lists the conftest as a
  module the test reaches. That is true, and it is what a call into a
  conftest helper already does; left as it is.
- **Two definitions of one qualname keep the first symbol record**
  (`graph._symbol_records`). A fixture name defined twice at one scope
  has no id to point at: abstain (`two-definitions`).

The unit is the pipeline's half: the walk, the lookup, the edges, the
test map, the ingest summary. `tests_guarding`'s "through fixture" line
(the Go proxy), `hobbes review`'s, the register, the version and the
docs are the developer's, after the merge.

## Built (2026-09-19, 0.2.49-beta)

Unit `5393` (89 turns of 100, $7.70, Opus 5), gate clear, verify pass,
ten files, merged no-ff. One deviation that draws less: a fixture
imported from a file that is neither a test file nor a `conftest.py`
resolves to nothing.

**The pre-registration, on the branch's own ingest:** 1,004 pairs
against `pytest --fixtures-per-test`, **1,004 right, 0 wrong, 0 missed**
— the figure exactly. 1,008 edges into 82 fixtures; 1,030 parameters
name no repo fixture.

**Held out, collected in the image, offline** (dependencies installed
as wheels into a directory, no repo code run on the host):

| repo | right | wrong | missed | what the misses are |
|---|---:|---:|---:|---|
| pallets/flask `d73fa1c` | 504 | 0 | 370 | one `autouse` fixture (364) and another (6) |
| python-attrs/attrs `8f76777` | 104 | 0 | 8 | one `usefixtures` mark, 8 tests — and the ingest's own `usefixtures` count there is 8 |

The first compare read 3 wrong pairs on flask and 5 on attrs. **Neither
was an edge; both were how pytest prints its answer,** and `compare.py`
now says so (`compare-v1.py` keeps the first form):

- pytest prints a fixture at its **first decorator line** when the
  decorator spans lines (attrs's `@pytest.fixture(name=…, params=…)`);
  the graph's symbol is at the `def`.
- pytest prints **one row per fixture name**. flask's
  `def app(self, app)` overrides the conftest's `app` and requests it:
  both run, only the inner one is printed. The edge to the outer one is
  right, and counted apart as "not printed".

**The developer's half, after the merge:**

- **A base class.** A base class's fixture is inherited and outranks the
  file's and the conftest's; the walk does not resolve bases. A class
  `Symbol` now counts the bases it names (`metaclass=` is not one), and
  an edge found past the class chain from inside a class that names a
  base is left undrawn (`base-class`). It costs nothing on the three
  repos (0 abstentions each) and closes the one shape where the rule
  could draw a *wrong* edge rather than miss one.
- `tests_guarding` marks a line "only through a pytest fixture
  (ADR-137)" when every target module the test reaches is in its
  `through_fixtures`; one module reached by a call drops the mark.
- `hobbes review` lists new code guarded only through a fixture under
  its own heading — guarded, so not a reason for attention —
  and in `--json` as `coverage.fixture_only`.

Suites: 2,034 pytest, `lane_b` 10 of 10, Go `./...` green. C-4 partial →
surfaced, narrowed; the register's counts 93 surfaced, 22 partial.

## Note (2026-09-19, from ADR-139's measurement)

The key this record was checked against was collected without `-v`, and
pytest then prints no fixture whose name starts with `_`. "1,004 of
1,004", flask's 504 and attrs's 104 are of the pairs that key printed.
On the `-v` key nothing drawn is wrong on any of the three; the missed
pairs are this repo 3,962, flask 734 and attrs 14 — every one an
`autouse` fixture or a `usefixtures` mark (ADR-139). Collect a fixture
key with `-v`.
