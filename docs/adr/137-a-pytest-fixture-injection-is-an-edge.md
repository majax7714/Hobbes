# ADR-137 — A pytest fixture injection is an edge the test's reach follows

**Date:** 2026-09-19 · **Status:** proposed — measured, nothing built, no version move. The routes below are Max's.

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
