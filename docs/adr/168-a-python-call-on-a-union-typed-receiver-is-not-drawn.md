# ADR-168 — A Python call on a union-typed receiver is not drawn

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route **1** of three, "proceed with the
recommended decisions") and **built** (0.2.97-beta) · **Owner:** Max · **Source:** the held-out icalendar
grade (`oracle-grading.md` §10.46, `cells/icalendar-py-2026-10-03.md`); this ADR's step 0 and simulation
(`~/.hobbes/bench/c184-union-receiver/`).

Contains **C-184** (unsurfaced → surfaced). Extends ADR-104 (C-97, TypeScript) to Python. Draws less: no new
edge.

## What is wrong

scip-python 0.6.6 answers a member access on a union-typed receiver with the **first** member that declares
the member, and the join drew that answer at `semantic` certainty. icalendar's `VPROPERTY: TypeAlias = vAdr |
vBoolean | …` made `component['TZOFFSETFROM'].to_ical()` an edge to `vAdr.to_ical`, which the call never
reaches: 6 of the held-out cell's 22 suspects, all `semantic`, all this one pick. TypeScript's twin was
contained by ADR-104; nothing contained Python's.

## Measured (step 0 and the simulation, read-only)

Python lane A types no receiver, and scip-python's hover documentation states a type for some receivers and
`?` for others (the parameter `utc_prop: VPROPERTY` has none), so neither lane alone reads every case. Every
wrong row's union is **written in the source**: a parameter's annotation, a method's return annotation (a
local bound from it, or the call's result), a class attribute's annotation, or an in-repo `__getitem__`'s
return. The simulation (`sim_laneA.py`) reads exactly those, by name, and abstains where the receiver reads as
a union of in-repo classes two or more of which declare the method (own or inherited, distinct defs):

| cell | lane B call rows refused | of them: wrong (suspect) | key-agreeing (confirmed) | unobserved |
|---|---:|---:|---:|---:|
| icalendar (held out) | 20 | **6 of 6** | 12 | 2 |
| rich, flask, click, pyparsing, this repo | 0 | 0 | 0 | 0 |

The 12 confirmed rows are union-typed sites where the key happened to see the first member (a
`LazySubcomponentsStrategy` method through `self._subcomponents`, typed as the three-strategy union): one
possible dispatch presented as the resolved one, which is what ADR-104 abstained on in TypeScript ("an
agreement of picks, not a truth"). A rule that reads lane B's own answer kept one more of them; it was not
taken, because lane A must mark the site before the join, as ADR-104 does.

## The decision (Max: route 1)

1. **Lane A records the type facts it can read** (`pysource`, where the grammar is): module-level union
   aliases (`X: TypeAlias = A | B`, `X = A | B`, `X = Union[A, B]`, Python 3.12 `type X = …`); each class's
   name, methods and bases; class-body and `self.x:` attribute annotations; every function's return
   annotation; and, per method call `R.m(…)` inside a function, how `R` reads: a parameter's annotation, a
   local bound once from a call, an attribute, a subscript, or a call's result.
2. **A grammar-free pass** (`pyunion`) decides per call site, by name across the repo: the receiver's type is
   a union when every read of it agrees on two or more in-repo classes (aliases expanded; `None` dropped; a
   name with two class definitions is unreadable and stops the read). A subscript reads as every union an
   in-repo `__getitem__` returns, since lane A cannot tell which class is subscripted. The site is
   `union-member` when two or more members declare `m` with distinct defs.
3. **The join vetoes lane B there and draws nothing from either lane** (ADR-104's path: the site's
   `ambiguous` field); the tail counts the site `union-member`, now available to Python.
4. Where the reads disagree or name anything unreadable, nothing changes: lane B's answer stands.

**Why abstain and not draw every member.** Drawing each member is the dispatch question (C-58), and the
static answer is still "one of them"; ADR-104 drew none, and so does this.

## Alternatives considered

- **Route 2: surface only** (a record counting answers at a union's member). The wrong edges would stay.
- **Read lane B's hover types** (the decoder skips documentation): incomplete for parameters, and it costs the
  decode on every repo.
- **Refuse by target** (every call to a union's first holder): 239 true edges lost on icalendar.

## Built (0.2.97-beta)

`extract/pysource.py` (the type facts), `extract/pyunion.py` (the decision), `extract/__init__.py` (the
sites' `ambiguous`), `extract/tail.py` (`union-member` for Python), the Go gloss. Tests:
`test_pyunion.py` (each read, the near misses, a fixture in icalendar's shape, the projection with lane B's
answer hand-built, and the `lane_b` ingest on the host: the four union sites draw nothing, `plain()` still
draws, the tail counts `union-member: 4`).

**Regrade** (`~/.hobbes/bench/c184-union-receiver/run.sh`, `after/`; poison on, stored keys):

| cell | confirmed | suspect | unobserved | recall | poison |
|---|---|---|---|---|---|
| icalendar | 3,489 → 3,477 | 22 → **16** | 56 → 54 | 68.9% → 68.7% | PASS |
| rich | 4,968 → 4,968 | 42 → 42 | – | 92.5% | PASS |
| flask | 1,552 → 1,552 | 15 → 15 | – | 55.6% | PASS |
| click | 3,768 → 3,768 | 20 → 20 | – | 82.0% | PASS |
| pyparsing | 3,517 → 3,517 | 66 → 66 | – | 50.6% | PASS |

icalendar moved exactly as simulated: the 6 Hobbes-wrong suspects gone (no `vAdr` or `is_lazy` suspect left), 12
key-agreeing union rows and 2 unobserved ones withdrawn. The other four cells' symbol edges are
byte-identical, with no `union-member` site.
