# ADR-139 — A fixture no parameter names is still looked up by name: `usefixtures` and `autouse`

**Date:** 2026-09-19 · **Status:** proposed — measured, nothing built; the routes are Max's.

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
