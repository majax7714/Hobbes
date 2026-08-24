"""Invariants: records, compilation, and verdicts (M8, ADR-024/025).

A confirmed invariant is read twice, by two different consumers that
must not disagree:

- :mod:`hobbes.invariants.compile` emits a CI config per target
  (import-linter, dependency-cruiser, semgrep, Rego). Emitting is text
  generation, so it never needs the target's toolchain installed.
- :mod:`hobbes.invariants.verdict` answers, in-process and from
  ``graph.json``, whether the rule currently holds — so ``hobbes
  review`` is deterministic and free of both quota and external tools.

Both read one spec, :mod:`hobbes.invariants.schema`, which is why the
contract shipped to CI and the verdict shown in review cannot drift
apart.
"""

from hobbes.invariants.schema import (
    COMPILED_DIR,
    INVARIANTS_DIR,
    Invariant,
    ValidationError,
    load_all,
    scope_matches,
)

__all__ = [
    "COMPILED_DIR",
    "INVARIANTS_DIR",
    "Invariant",
    "ValidationError",
    "load_all",
    "scope_matches",
]
