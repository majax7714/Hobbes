# ADR-139 — A fixture no parameter names is still looked up by name: `usefixtures` and `autouse`

**Date:** 2026-09-19 · **Status:** accepted (Max, 2026-09-19: "good to go with recommended route" — route a); the premises read in the tree before the brief (*Accepted*), and built (0.2.52-beta; *Built*, below).

Follows ADR-137 (a parameter pytest's lookup resolves to one repo
fixture is a syntactic `uses` edge, and test reach follows it), whose
remainder C-4 names: a fixture requested by a `usefixtures` mark or
applied by `autouse=True`. A build would be a patch: a constraint's fix
(C-4).

## Context

ADR-137 left two shapes out because neither is a parameter. Both are
still a **lookup by name through the same scope chain**: a
`usefixtures("x")` string names `x` exactly as a parameter would, and an
`autouse=True` fixture adds its name to every test in its scope — the
class it sits in, its file, or everything below its `conftest.py` —
after which pytest resolves that name in the ordinary order. What
differs is what the walk keeps: a mark's string arguments are already in
`Decorator.args`; `autouse=True` is a boolean keyword, and
`pysource._decorator` drops every non-string keyword.

## The measurement (`~/.hobbes/bench/c4-remainder/`, in memory, nothing drawn)

`probe.py` reuses `extract/fixtures.py`'s scopes and `_resolve` with
ADR-137's abstentions unchanged (two definitions, a base class, an
unread `parametrize`, not in the repo), and adds, for a **test** only:

- **`usefixtures`:** each string on the test's own mark, on each
  enclosing class's mark, and in a module-level `pytestmark`
  (a call or a list of calls); a non-string argument is counted unread.
- **`autouse`:** each name that has an `autouse=True` definition (the
  literal `True`; anything else counted unread) in any scope of the
  test's chain, resolved from the test as a name.

Predictions were written first (`PREREG.md`). The key is
`pytest --fixtures-per-test`, flask and attrs collected in the image
with no network, as ADR-137's were.

**The key's display hid the class, and ADR-137's key with it.** Without
`-v`, pytest does not print a fixture whose name starts with `_`. Both
autouse fixtures on this repo, one of flask's three and attrs's only
one are spelled that way, so the first comparison read 4,332 true pairs as
wrong, and ADR-137's "1,004 of 1,004" was 1,004 of the pairs *that key
printed*. With `-v` (flask needs `-p no:hypothesispytest`: the shared
deps directory carries attrs's plugin, which fails on a read-only
mount):

| repo (tests compared) | today: right / missed | `usefixtures` | `autouse` | both: right / missed / wrong |
|---|---|---|---|---|
| this repo (1,981) | 1,009 / 3,962 | +0 | +3,962 | 4,971 / 0 / 0 |
| flask (364), held out | 504 / 734 | +0 | +734 | 1,238 / 0 / 0 |
| attrs (106), held out | 104 / 14 | +8 | +6 | 118 / 0 / 0 |

P-r1–P-r4 met on the verbose key (P-r1's and P-r3's *counts* were
written against the quiet key and are superseded by it: flask's missed
was 734, not 370, and this repo's 3,962, not 0). No pair wrong under
either rule on any repo; no abstention fired.

**What `autouse` does to reach.** On this repo the two autouse fixtures
are `tests/conftest.py`'s; one calls `hobbes.extract.staging.cache_root`.
Drawn, all 1,981 tests would guard `hobbes.extract.staging`, each line
saying "only through a pytest fixture (ADR-137)". That is true — the
code runs before every test — and it is also not what a reader of
`tests_guarding` is asking. `usefixtures` has no such effect: a mark is
written on the tests that want the fixture.

## Decision (proposed)

Draw both, as ADR-137 draws a parameter: a syntactic `uses` edge from
the test to the one fixture the name resolves to, evidence at the mark's
line (`usefixtures`) or the test's own line (`autouse`: nothing on the
test names it), every ADR-137 abstention kept. The walk keeps
`autouse` as a boolean only when it is the literal `True`. The edge
records which of the three it is (`via: parameter | usefixtures |
autouse`), and `tests.json` keeps autouse reach apart
(`through_autouse`) so `tests_guarding` and `hobbes review` can say it
in one line — "and every test under `tests/` through the autouse fixture
`_lane_a_only`" — rather than list 1,981 tests.

## Routes for Max

- **(a) Recommended — both rules; autouse reach said once, not listed.**
  This repo: +3,962 pairs, 0 wrong; flask +734; attrs +14. A module
  reached *only* through an autouse fixture stops reading as unguarded,
  and `tests_guarding` names the fixture and its scope instead of every
  test. The most honest reading: the reach is true, and it is marked as
  the blanket it is.
- **(b) `usefixtures` only.** attrs +8, nothing here or on flask. Small,
  clean, no reach question. Autouse stays C-4's remainder, now with a
  number beside it.
- **(c) Both, autouse listed like any other reach.** Simplest build;
  `tests_guarding hobbes.extract.staging` answers with 1,981 lines.
  Not recommended: true and unreadable.

Either way the register's C-4 figures need the verbose key's numbers,
and ADR-137's record a note that its key printed no `_`-named fixture.

## Alternatives considered

- **Draw autouse edges but keep them out of test reach.** The edge is
  then a fact nothing reads; and a module only an autouse fixture
  exercises would still be called unguarded, which is wrong.
- **Read `autouse` from any truthy expression.** Not syntax; a name or a
  call is counted unread, as `parametrize` is.

## Consequences

- `pysource.Decorator` keeps one boolean.
- C-4 narrows to: the value a fixture returns, plugin and installed
  fixtures, a base class's, two definitions, a non-literal `autouse` or
  mark argument.
- The denominator statement (0.2.51-beta) would drop "no parameter
  names (autouse, usefixtures)".

## Accepted — route (a), and the premises read before the brief (2026-09-19)

Read in the tree, not assumed:

- `pysource._decorator` keeps string positionals in `args` and string or
  list-of-string keywords in `kwargs`; `autouse=True` is dropped today.
  `Decorator` is constructed only in `pysource.py`, positionally, so a
  defaulted field added at the end breaks nothing.
- `fixtures.injections` already walks every test with its scope chain,
  its class chain and the `inherits` guard; a class's decorators are on
  the class's own `Symbol`, reachable through the file's qualnames.
- `_add_injection_edges` builds the edge with `schema.tiered_edge`, which
  copies each evidence row's keys through and stamps the lane: a `via`
  key on the row survives, and nothing validates a row's key set.
- `collect_tests` computes reach over `calls` plus injections and
  `through_fixtures` by subtracting the calls-only reach;
  `review._fixture_only_modules` and the proxy's `tests_guarding` read
  `through_fixtures` from each record.

Two narrowings of the *Decision*, both toward drawing less:

1. **A module-level `pytestmark` is counted, not followed.** The probe
   read it, and none of the three repos has one: no key row has judged
   it.
2. **One pair, one `via`.** A test that also names an autouse fixture as
   a parameter, or in a mark, is a parameter's (or a mark's) injection;
   `autouse` is said only where nothing on the test names the fixture.

**The record's shape.** `through_autouse` on a pytest test record is a
map, module → the autouse fixtures whose own reach gets there, for the
modules the test reaches *only* that way; `through_fixtures` keeps its
meaning and the two never share a module. The proxy and `hobbes review`
collapse it: one line naming the fixtures and the number of tests, not
one line per test.

The unit is the pipeline's half; the proxy, `review.py`, the register,
the version and the records are the developer's.

## Built (2026-09-19, 0.2.52-beta)

Unit `6f84` (68 turns, $5.70; gate right-clear, verify pass) built the
pipeline's half as briefed; the proxy's folded line, `review.py`'s
`autouse_only`, the denominator statement, the register and the version
are the developer's commit.

- **The real cell before the merge.** The branch's lookup against the
  three `-v` keys: this repo 4,971 right, flask 1,238, attrs 118 — 0
  missed, 0 wrong — and its edges identical to the probe's on all three.
  2,090 pytest and the 10 `lane_b` cases on a worktree of the branch, on
  the host.
- **This repo's ingest:** 5,072 injections into 85 fixtures, 4,058 by
  autouse; 2,029 of 2,773 test records carry a `through_autouse`
  (`tests.conftest` 1,958, `hobbes.extract.staging` 1,588).
  `tests_guarding hobbes.extract.staging` lists 441 tests and says the
  1,588 once, naming `tests.conftest._lane_a_only`.
- **The doer's deviations, kept:** `pytestmark` counted only on a plain
  module-level assignment; a list keyword the walk cannot read whole is
  in `unread_kwargs`; `through_autouse` names the fixture's own module
  (a `conftest.py` is a source module to the test map, as under
  ADR-137).
- **Not re-run:** no graded cell. No trace key judges a `uses` edge, and
  the rule adds no node.
- **Left in C-4:** the returned value's type, a module `pytestmark`, a
  non-literal `autouse=`, and the abstentions.

## Amendment (2026-09-20, proposed) — a module-level `pytestmark` has a key row now

Narrowing 1 of *Built* stood on one fact: none of the three repos had a module
`pytestmark` with `usefixtures`, so no key row had judged it. A repo was drawn
for it, the rule stated first (`~/.hobbes/bench/c4-pytestmark/`: `DRAW-RULE.md`,
`DRAW-RULE-2.md` after the first walk ended empty, `draw-log.md`, `RESULTS.md`).

- **The draw.** GitHub code search, 71 repos, shuffled by seed. Walk 1 took
  none: the hits are pytest's own suite writing the line into a string (and 30
  copies of it), GDAL's one real use (no binary wheel) and its vendored copies,
  docstrings, rpm specs. Walk 2 read the clone with `ast` instead of the search's
  first hit: **MissyLabs/missy @ `223dbe8`**, position 32 — 18 test files, each
  `pytestmark = pytest.mark.usefixtures("deterministic_public_dns")`, the fixture
  in the root `conftest.py`. Passed on the way: tractor (its fixtures are a
  `pytest_plugins` module's, `not-in-repo`), cadrumo (706 marked files; needs
  Python 3.13, the image has 3.12).
- **The key.** `pytest --fixtures-per-test -v tests` in the image, no network,
  the clone read-only: 23,480 tests, no collection error.
- **The result** (`probe.py`'s rule: every test of the module requests the
  mark's strings, looked up exactly as a `usefixtures` string is):

  | | pairs right | wrong | missed, in-repo |
  |---|---|---|---|
  | 0.2.62-beta as built | 34,505 | 0 | 1,265 — all the `pytestmark`'s fixture |
  | + the rule | 35,770 | 0 | 0 |

  P1–P4 held. It is also a fourth held-out repo for ADR-137 and this ADR as
  built: 0 wrong of 34,505.
- **A mistake, caught:** the first collection passed `-v -q`, which cancel, and
  pytest hid an autouse `_…` fixture — 26,474 pairs read "wrong". `-v` alone.
- **Proposed:** lift narrowing 1. A plain module-level assignment of one mark or
  a list/tuple of marks; its `usefixtures` string arguments are requested by
  every test in the module, `via: usefixtures`, evidence at the mark's line,
  after the test's own and its classes' marks (one pair, one via). A non-string
  argument and a `pytestmark` that is not a plain assignment stay counted, not
  followed. A class-body `pytestmark` is not read (no key row has one).
