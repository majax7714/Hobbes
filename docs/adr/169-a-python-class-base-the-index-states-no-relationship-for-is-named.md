# ADR-169 — A Python class base the index states no relationship for is named

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route **1** of three for flask's `sansio/`
re-ask, "proceed with the recommended decisions") and **built** (0.2.98-beta) · **Owner:** Max ·
**Source:** the re-ask's probe (`currently-open.md`, 2026-10-03); this ADR's measurement
(`~/.hobbes/bench/c185-missing-bases2.py`).

Registers **C-185** (surfaced). Draws nothing new.

## What is wrong

flask's `class Flask(App)` has no `implements` edge. The re-ask's probe found it is not PEP 420 naming — lane
A and scip-python both name the module `app`, and references join — but scip-python 0.6.6 writing **no
SymbolInformation at all** for `Flask#`, so the class-level relationship is never stated, not even counted
`outside`. The same index states it for most classes (`App# → Scaffold#`, `Blueprint#`), and the method
pairs under `Flask` are stated. icalendar's raw index omits `Component#`, `TimezoneDaylight#` and
`TimezoneStandard#` the same way. Nothing named the missing edge.

## Measured

A base **lane B itself resolved** in a class header (a `uses` of an in-repo class whose name is one of the
header's base heads), with no `implements` edge from the class to it:

| cell | resolved in-repo bases | no `implements` edge |
|---|---:|---:|
| flask | 80 | 14 (`Flask → App`, `Blueprint → Scaffold`, …) |
| rich | 80 | 16 |
| click | 97 | 9 (`Group → Command`, `Option → Parameter`, …) |
| pyparsing | 168 | 42 |
| icalendar | 60 | 4 (`Component → CaselessDict`, …) |
| this repo | 9 | 0 |

Matching bases by name alone (lane A's read) was rejected: it paired `unittest.TestCase` with pyparsing's own
`TestCase` and a werkzeug class with flask's same-named subclass. The lane B resolution is the base the
interpreter would use.

## The decision (Max: route 1)

1. Lane A records each class header's span and its bases' head names (`TypeFacts.heads`; a type argument and
   a `metaclass=` keyword are not bases).
2. After the projection, where lane B ran for Python, `pybases.unstated_bases` lists each `(class, base)`
   such that a lane B `uses` of the in-repo class `base` sits in the class's header under one of its base
   names, from the class or its module, and no `implements` edge joins them.
3. One `python-bases` degradation record per ingest names the count and examples, and C-185. Nothing is
   drawn: drawing the pair from the header (route 3) is a recall rule, measured separately if ever.

## Alternatives considered

- **Route 2: register the PEP 420 naming as well.** The probe showed it does not cause this; it stays a
  question for when it bites.
- **Route 3: draw the pair** (`syntactic`, from the resolved base). A new rule; not taken.

## Built (0.2.98-beta)

`extract/pysource.py` (`TypeFacts.heads`), `extract/pybases.py`, `extract/__init__.py`
(`_unstated_bases_record`). Tests: `test_pybases.py` (the heads, a named pair, a type argument and a lane A
row not counted, the record through the ingest with lane B's answer hand-built).

**Regrade** (`~/.hobbes/bench/c185-unstated-bases/`): the record names icalendar 4, rich 16, flask 14, click 9
and pyparsing 42 pairs, exactly the measurement; every cell's symbol edges are byte-identical and its grade
unchanged.
