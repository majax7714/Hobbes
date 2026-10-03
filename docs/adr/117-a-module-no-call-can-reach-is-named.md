# ADR-117 — A module no call can reach is named, not exempted

**Date:** 2026-09-16 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-16 ("go with the recommended route"), on C-156, choosing route (a) of three.

Amends **ADR-025** (the review contract: what "new code no test
reaches" says) and the `tests_guarding` answer. Leaves **ADR-007**'s
reach rule as it is. Surfaces **C-156**.

## Context

Test reach is the closure over `calls` edges from a test symbol, in
every language's test map (ADR-007). `uses` edges are left out on
purpose, because reach must not widen to code a test only names. A
module that holds only values therefore cannot be reached by any test.
`go/internal/version` is the case in this repo: its test compares
`version.Version` with the root `VERSION` file and is recorded with
`reaches: []`.

Both surfaces said "unguarded" and gave no reason. That reads as a
missing test when no test could be seen, which is C-156, registered
unsurfaced.

## Decision

**1. The rule is an observation about the graph.** A module is
*value-only* when none of its symbols has a callable kind (`function`,
`method`, `class`, `type`, `macro`: the kinds a `calls` edge targets
in practice) and no `calls` edge targets any symbol it declares. The
second half matters for TS/JS, where a `const` holding an arrow
function is recorded as a `const` and is called. A `uses` edge does not
count. The rule is `testmap.value_only_modules` in the pipeline and
`valueOnly` in `internal/knowledge`: the same rule, each held by its
own tests.

**2. Named, not exempted.** The review still lists such a module under
"new code no test reaches" or "lost every guarding test", and it still
counts toward *needs attention*. It adds the reason on the module's
line and in `--json` under `coverage.value_only`. `tests_guarding`
still answers "unguarded" and adds one line per value-only module,
citing C-156.

## Alternatives considered

- **(b) Reach follows a test's reads of a module's values.** Rejected
  for now: it reopens ADR-007's rule, and a read is a far weaker claim
  than a call ("the test named it", not "the test ran it").
- **(c) Documented only.** Rejected: an unsurfaced entry is debt (P8).
- **Exempting value-only modules, as ADR-114 exempts fixtures.**
  Rejected: a fixture is a test's input, while a constant is behaviour
  a user relies on (a wrong version string is a real defect). The
  review should say it cannot see a guard, not stop asking.

## Consequences

- `go/internal/version`, `scip/compare`, `web/src/main` and the other
  value-only modules in this repo carry the reason wherever they are
  listed as unguarded.
- A module whose only callable is a const nothing calls still reads as
  value-only. That matches the rule's wording ("no call targets it"),
  and the line says so rather than claiming the module holds no
  function.
- **Version:** 0.2.29-beta, because this changes what the layer says
  (ADR-103).

## Amendment 2026-10-03 — a Python module that holds no code is not asked for a guard (0.2.90-beta)

**Source:** Max, 2026-10-03 ("good with the proposal"), on the red `graph` job: `lattice`'s
`__init__.py` is a docstring and nothing else, and the review counted it as unguarded new code.

**Decision.** A Python module whose source holds no statement except, at most, one bare string (its
docstring; comments aside) is not own code to guard, for the same reason ADR-114 gives for a fixture:
asking for its guard asks for what cannot exist. There is no value in it to get wrong, which is what
separated a value-only module from a fixture above. Lane A records it on the module's node
(`"no_code": true`); a file whose parse failed or was too deep to walk (C-171) is never marked. The review
leaves such a module out of "new code no test reaches" and "lost every guarding test", and says so on its
own line (`holds no code, not asked for a guard`) and in `--json` under `coverage.no_code`, so the
exemption is visible rather than silent.

**Measured.** The rule as first drafted read it off the graph ("declares no symbol and no edge leaves it").
On this repo that picked 21 modules, among them `pipeline/src/hobbes/__init__.py` (its `__version__`, the
case this ADR names as behaviour), a 129-line Go file and a 323-line TS types file whose declarations lane A
records as no symbol. A graph silence is not an empty file, so the rule reads the source. Of this repo's
Python modules it marks four outside fixture trees, all docstring-only `__init__.py` files: `hobbes.agent`,
`hobbes.ttt`, `pipeline:tests` and `lattice`.

**Not changed.** A value-only module is still listed with its reason (C-156). Other languages have no such
mark, so their empty files are still asked for a guard; that asks for more, never less.
