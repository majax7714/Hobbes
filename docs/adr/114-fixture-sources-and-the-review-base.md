# ADR-114 — Fixture sources are not own code, and the graph job reviews from its last green run

**Date:** 2026-09-15 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-15, on the graph job that went red on the push of `fdc7f07` ("graph check returned 8 unguarded new modules"), choosing the route "exempt fixtures + fix base".

Amends **ADR-025** (the review contract: what "new code no test
reaches" counts) and **ADR-095** (the graph job's base ref). It closes
the W0 item of 2026-09-10 (`workstreams.md`, "The graph job forgets a
red review").

## Context

ADR-025 made "modules this change added that no test reaches" the
review's coverage finding. `_own_code` already leaves test files out,
using the test inventory's own list rather than a filename guess.

The C++ push of 2026-09-15 went red on eight modules, and every one was
a fixture source: `pipeline/tests/fixtures/minicpp/*`, the lane's
fixture repo, and `bench/oracle/testdata/cppclang/*`, the oracle's. A
fixture is a test's *input*. The suite reads it, parses it and indexes
it; nothing calls it, so no test can be seen reaching it. Asking for
its guard asks for something that cannot exist.

The C fixtures (`minic`, `cclang`) are just as unguarded. They passed
only because of a second defect: `ci-graph.sh` reviews
`github.event.before..HEAD`, so a module that turns one push red is in
the next push's base and is never reported again. Three pushes
forgot theirs this way on 2026-09-09/10.

## Decision

**1. A source inside a tree the repo's own test runners exclude is not
own code.** `runner_excluded_trees` (`hobbes/extract/testmap.py`) reads
the trees at extraction, so each end of a review exempts by its own
tree's configuration. It has two rules, and both are read from the
tree:

- **pytest.** A config that states `norecursedirs` excludes every
  directory whose basename matches one of its patterns, under each of
  its `testpaths` (or under the config's own directory when it names
  none). The configs read are `pyproject.toml`'s
  `[tool.pytest.ini_options]`, `pytest.ini` and `tox.ini`'s `[pytest]`,
  and `setup.cfg`'s `[tool:pytest]`. pytest's built-in defaults
  (`build`, `dist`, …) are not read: an exclusion the repo did not state
  would be a guess.
- **Go.** The go tool ignores a directory named `testdata` inside a
  module, so the first `testdata` with a `go.mod` at or above it is
  excluded.

**2. The exemption is said, not silent** (P8). The review's coverage
section names each tree, the rule that exempts it and its module count.
`--json` carries the same under `coverage.fixture_trees`. C-154
registers what the review no longer asks.

**3. The graph job reviews from the last green run.** On a push,
`ci.yml` takes as its base the head commit of the latest successful
`ci` run on the branch, when that commit is an ancestor of `HEAD`. It
falls back to the push's `before` otherwise (the first run, or a
rewritten history). So a red review stays red until the change it
names is fixed. A pull request still reviews from its merge base.

## Alternatives considered

- **A filename rule** (`tests/fixtures`, `testdata` or `fixtures`
  anywhere). Rejected for the reason `_own_code` already gives for test
  files: the exclusion is data, not a name guess. A repo's `fixtures/`
  can hold product code, and a `testdata` outside a Go module means
  nothing to any runner.
- **Guarding the fixtures with tests.** A fixture is input, so the
  graph can see no test reaching it. A test written to import one would
  pin nothing a user relies on.
- **A standing count of every unguarded own module in each review.**
  This was the W0 item's other option. It would print
  `go/internal/version` and the forgotten modules on every review, a
  number that does not move with the change. Fixing the base makes the
  delta honest instead. The count can still be added if it is wanted.
- **Accepting the red.** It ages out on the next push, and that ageing
  out is the defect itself.

## Consequences

- **This repo:** `pipeline/tests/fixtures` (pytest, via
  `pipeline/pyproject.toml`) and `bench/oracle/testdata` (go, via
  `bench/oracle/go.mod`) leave own code. That covers the eight C++
  modules, and `minic`, `cclang` and `minits` with them.
  `go/internal/version` and the others the job forgot stay unguarded,
  but they are no longer new, so the base fix does not bring them back.
- **A target repo** gets the exemption only where its runners state
  it. A repo whose fixtures sit outside a stated exclusion is still
  asked, which is C-154's residue.
- **The graph job** needs `actions: read` to list runs. Nothing local
  can exercise the base rule; the first push after this change is its
  first run.
- **Version:** 0.2.24-beta, because this changes what the review says
  (ADR-103).
