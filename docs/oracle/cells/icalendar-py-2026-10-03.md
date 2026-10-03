# Oracle cell — collective/icalendar, Python zone `.`, 2026-10-03 (held out)

**Repo:** `collective/icalendar` (BSD-2-Clause) v7.3.0 at `138c8453`, `~/.hobbes/bench/oracle/repos/icalendar`.
**Held out:** Hobbes had never ingested, simulated or keyed this repo, and no rule was changed for the cell.
Max picked it on 2026-10-02 as the held-out cell for the `cls(…)`-in-a-classmethod unit (81 sites by an `ast`
scan); pyparsing stays held out. A data-model library: `Component` subclasses built by name registries,
value types (`vText`, `vDDDTypes`…) with `from_ical`/`to_ical`, a timezone provider behind an ABC, and type
aliases that are unions of in-repo classes (`VPROPERTY`). The predictions were pre-registered in
`~/.hobbes/bench/heldout-icalendar/PREREG.md` (committed in `e93a519`'s BUILDLOG entry by hash) before the
ingest and before the key existed, and it was graded once.

**Hobbes at** 0.2.96-beta (`a5b4f41`), image `58f823a5a3d1`. **Oracle:** `py-trace` (CPython 3.12.13
`sys.monitoring`). **Venv:** the clone's `uv sync --group test --python 3.12`. The suite is its `testpaths`
(`src/icalendar/tests`, `hypothesis/` excluded by `norecursedirs`): 18,166 passed, 30 skipped, 540 xfailed per
traced run. Union over 2 runs.

**Command:** `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/icalendar . ~/.hobbes/bench/oracle/icalendar-py
--lang py --runs 2 -- src/icalendar/tests -q -p no:cacheprovider`. **Runtime:** 1,933 s, ingest included.
Output dir `~/.hobbes/bench/oracle/icalendar-py/` (its `graph.json` kept beside the report); the log is
`~/.hobbes/bench/heldout-icalendar/run.log`.

Ingest line: `graph.json: 309 nodes, 1935 module edges, 2352 symbols, 2671 call edges, 4908 uses edges, 98 implements edges`; `capture [python]: 83.3% of 9865 detected call sites accounted`.

```
cell   oracle py-trace 3.12.13 sys.monitoring (trace)  sha 138c8453
oracle ran contained (ADR-092)
hobbes edges 3567: confirmed 3489  suspect 22  unobserved 56 map[line-mixed:4 line-not-called:50 not-loaded:2]
confirmation rate 97.8% (3489/3567 hobbes edges; coverage-limited, not precision)
suspect rate 0.6% (22/3511 executed hobbes edges; triage queue, never contradicted)
recall-against-executed 68.9% (3489/5063 observed in-repo pairs) over 2 run(s) of [/home/mmarrujo/.hobbes/bench/oracle/repos/icalendar/./.venv/bin/python -m pytest src/icalendar/tests -q -p no:cacheprovider]; external python targets 4375; misses map[observed→class:385 observed→closure:13 observed→function:78 observed→lambda:81 observed→method:1017]
coverage: hobbes sites observed 3265/3316 (98.5%); files loaded 257/262; declarations started 2133/2393; c-callee calls 88280526; subprocesses traced 0
  recall[observed→class    ]  72.1% (997/1382)  misses 385 = 24.5% of all misses
  recall[observed→closure  ]  64.9% (24/37)  misses 13 = 0.8% of all misses
  recall[observed→function ]  86.5% (501/579)  misses 78 = 5.0% of all misses
  recall[observed→lambda   ]   0.0% (0/81)  misses 81 = 5.1% of all misses
  recall[observed→method   ]  65.9% (1967/2984)  misses 1017 = 64.6% of all misses
  tier semantic   confirmed 3430  suspect 22  unobserved 56
  tier syntactic  confirmed 59  suspect 0  unobserved 0
```

Poison: 3,567 seeded, 2,978 refused, 589 unjudged, **0 falsely confirmed (PASS)**. `hobbes lanes`: every
disagreement a registered shape (exit 3).

## The 22 suspects, read row by row

| Rows | Shape | Verdict |
|---|---|---|
| 9 | `self.__provider.<m>(…)` in `timezone/tzp.py`, declared `TZProvider(ABC)`; the trace saw `PYTZ`/`ZONEINFO` | C-60's declared target |
| 6 | `self._utc_now()` in six components; a test fixture (`conftest.py:521`) monkeypatches it with a lambda | C-60's monkeypatch |
| 1 | `self.component.add_component(…)` (`parser/ical/lazy.py:68`), declared `Component`; the trace saw `LazyCalendar`'s override | C-60's declared target |
| **5** | a method call on a receiver whose declared type is the `VPROPERTY` union (`vAdr \| vBoolean \| …`): `component['TZOFFSETFROM'].to_ical()` (`cal/timezone.py:174`, `:175`), `cal["X-SOMETIME"].to_ical()` (`tests/test_time.py:26`), `utc_prop.to_ical()` (`tests/prop/test_date_and_time.py:76`), `factory.from_ical(…)` (`parser/ical/component.py:231`). Hobbes draws `vAdr.to_ical`/`vAdr.from_ical` at `semantic`; the trace saw `vUTCOffset`, `vTime`, `vDatetime`, `vDDDTypes`, `vDDDLists`. `vAdr` is the union's **first** member and no base of them | **Hobbes-wrong** (C-184) |
| **1** | `calendar._subcomponents.is_lazy()` (`tests/test_issue_1050_lazy_parsing.py:27`), declared `LazySubcomponentsStrategy \| ParsedSubcomponentsStrategy \| InitialSubcomponentsStrategy`; Hobbes draws the first member's `is_lazy`, the trace saw `ParsedSubcomponentsStrategy`'s | **Hobbes-wrong** (C-184) |

**6 Hobbes-wrong rows, all `semantic`, one cause:** scip-python 0.6.6 resolves a member access on a
union-typed receiver to the first member's declaration. It is the Python face of TypeScript's
`static→union-member` (ADR-104, C-97), which lane A contains for TS and nothing contains for Python.

## Predictions (scored)

| # | Result |
|---|---|
| H1 no Hobbes-wrong edge | **missed: 6** (above) |
| H2 suspect rate ≤ 5% | met: 0.6% |
| H3 poison PASS | met |
| H4 recall 45–75% | met: 68.9% |
| H5 function ≥ 80 / class 50–85 / method 40–75 / lambda ≤ 10 | met: 86.5 / 72.1 / 65.9 / 0.0 |
| H6 syntactic ≤ 10% of confirmed | met: 59 of 3,489 (1.7%) |
| H7 `cls(…)` ≥ 10% of `observed→class` misses | met: 90 of 385 (23.4%) |
| H8 `hobbes lanes` exit 0 or 3 | met: 3 |

**C-178's check** (measured, not predicted): of 7,500 `semantic` lane B rows, 32 do not hold the target's name
on their line, all `uses` of an instance attribute (`self.strict`, `self.parse_error`) filed under its class;
no `calls` row. None is C-178's re-export shape.

**The `cls(…)` rule's rows (C1–C5)** wait for the rule. Its step 0 was read on this cell only after the grade:
81 sites, 71 seen only at the own class, 6 at the own class and a subclass, 4 not executed. The rule's wording
is frozen in `PREREG.md`; any narrowing must rest on the fitted cells, not on these rows.

## After ADR-168 (0.2.97-beta)

Regraded against this key: 3,477 confirmed, 16 suspect, 54 unobserved, recall 68.7%, poison PASS. The 6
Hobbes-wrong rows are gone; the 16 left are the C-60 rows above. `~/.hobbes/bench/c184-union-receiver/after/icalendar/`.
