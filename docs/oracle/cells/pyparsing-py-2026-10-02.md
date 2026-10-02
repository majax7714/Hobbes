# Oracle cell — pyparsing/pyparsing, Python zone `.`, 2026-10-02 (held out)

**Repo:** `pyparsing/pyparsing` (MIT) 3.3.3 at `d90d38b2`, `~/.hobbes/bench/oracle/repos/pyparsing`.
**Held out:** Hobbes had never ingested, simulated or keyed this repo, and no rule was changed for the cell.
It was picked when the C-9 local-alias step 0 found that shape only on rich, the held-out cell then (Max,
2026-10-02, route 1: a new held-out cell before the rule, rich counted as fitted). Different author and
style from pallets and Textualize: a twenty-year-old codebase, one deep `ParserElement` hierarchy whose
subclasses override `parseImpl` and friends, class-level method aliases re-pointed at run time by packrat,
and a package `__init__.py` that re-exports everything by `from .core import *`. The predictions were
pre-registered in `~/.hobbes/bench/heldout-pyparsing/PREREG.md` before the ingest and before the key existed,
and it was graded once.

**Hobbes at** 0.2.83-beta's tree (`2f99c8e`, a docs commit after the release). **Oracle:** `py-trace`
(CPython 3.12.13 `sys.monitoring`). **Venv:** the clone's own uv venv (`uv venv --python 3.12`; `uv pip
install -e '.[diagrams]' pytest`: railroad-diagrams and jinja2, as tox's `unit` env; matplotlib not
installed, so its cases skip). The suite is tox's (`tests examples/tiny/tests`): untraced, in the image with
the network off, 2,067 passed, 27 skipped, 2,077 subtests passed, 27.5 s. Union over 2 runs.

**Command:** `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/pyparsing .
~/.hobbes/bench/oracle/pyparsing-py --lang py --runs 2 -- tests examples/tiny/tests -q -p no:cacheprovider`.
**Runtime:** 3,612 s, ingest included (traced, each run is about 30 min). Output dir:
`~/.hobbes/bench/oracle/pyparsing-py/` (its `graph.json` kept beside the report); the log
`pyparsing-py.log` is beside it.

Ingest line: `graph.json:      220 nodes, 807 module edges, 1995 symbols, 2902 call edges, 2116 uses edges, 308 implements edges`; `capture [python]: 67.0% of 15081 detected call sites accounted`.

```
cell   oracle py-trace 3.12.13 sys.monitoring (trace)  sha d90d38b2
oracle ran contained (ADR-092)
hobbes edges 5554: confirmed 3516  suspect 66  unobserved 1972 map[line-mixed:16 line-not-called:199 not-loaded:1757]
confirmation rate 63.3% (3516/5554 hobbes edges; coverage-limited, not precision)
suspect rate 1.8% (66/3582 executed hobbes edges; triage queue, never contradicted)
recall-against-executed 50.6% (3516/6950 observed in-repo pairs) over 2 run(s) of [/home/mmarrujo/.hobbes/bench/oracle/repos/pyparsing/./.venv/bin/python -m pytest tests examples/tiny/tests -q -p no:cacheprovider]; external python targets 2368; misses map[observed→class:1672 observed→closure:153 observed→function:329 observed→lambda:250 observed→method:1030]
coverage: hobbes sites observed 3287/4965 (66.2%); files loaded 56/154; declarations started 1234/1995; c-callee calls 140293659; subprocesses traced 0
  recall[observed→class    ]  23.1% (502/2174)  misses 1672 = 48.7% of all misses
  recall[observed→closure  ]  58.5% (216/369)  misses 153 = 4.5% of all misses
  recall[observed→function ]  57.4% (444/773)  misses 329 = 9.6% of all misses
  recall[observed→lambda   ]   0.0% (0/250)  misses 250 = 7.3% of all misses
  recall[observed→method   ]  69.6% (2354/3384)  misses 1030 = 30.0% of all misses
  tier semantic   confirmed 3322  suspect 66  unobserved 1921
  tier syntactic  confirmed 194  suspect 0  unobserved 51
poison check: PASS — 5554 seeded wrong edges: 2992 refused, 2562 unjudged (oracle silent there), 0 falsely confirmed
```

## The 66 suspects, read row by row: 0 Hobbes-wrong calls

- **55, the declared target (C-60's asymmetry):** Hobbes names the base method, the trace saw an override —
  `ParserElement.copy` (16), `.ignore` (9), `.streamline` (9), `.parseImpl` (3), `.recurse`, `.validate`,
  `._generateDefaultName`; `tiny_ast.TinyNode.execute` (9) and `.from_parsed` (2); and
  `ParserElement._CacheType.get`/`.set`/`.clear` (4), a protocol whose runtime members are closures the cache
  classes assign in `__init__`.
- **5, a call through a property's value:** `ppu.Japanese.identifier("japanese*")` (`tests/test_unit.py`
  10397–10401). `identifier` is a `@_lazyclassproperty`; its getter runs at the access (from the
  descriptor's `__get__`, where the trace keys it), and the written call calls the returned element's
  `ParserElement.__call__`. Hobbes draws `calls` to the getter. The def is reached on the line, so this is not
  an edge to a def the line does not reach, but C-174's clause said a getter is drawn *uses*; it is
  corrected at 0.2.85-beta to say what a call through a property draws.
- **4, a decorator's wrapper:** `_to_diagram_element(…)` (`diagram/__init__.py` 261, 562, 660, 718) is
  wrapped by `_apply_diagram_item_enhancements`, whose `_inner` calls it; the key names `_inner`. The key's
  grain.
- **1, a call that raised first:** `print(key_value_dict.parse_string("", …).dump())` (`test_unit.py:9361`)
  inside a `try`: `parse_string` raises, so `dump` never runs on that line.
- **1, one node for two defs:** `a_method` is written twice in one test (`test_unit.py` 9619, 9637); the
  graph keeps one node per qualname and the call at 9647 reaches the second (C-170's grain, ADR-155).

**But the key grades calls only, and a defect it cannot judge was found beside it (C-178).** scip-python
0.6.6 names most `pp.<name>` occurrences, where `pp` is the package and `<name>` came in by `from .core
import *`, as one unrelated symbol: of 3,182 such occurrences in tests and examples, 3,072 name something
else, most often `pyparsing.core/CaselessLiteral#` (`Word` 505, `alphas` 227, `Group` 212, `Literal` 195,
`nums` 166, `Forward` 101, …), and `one_of` or `replace_with` for others. The join draws what it names: 397
`uses` and 7 `calls` edges to `CaselessLiteral`, all `semantic`, on 1,688 evidence rows, where 36 source
lines name the class. The calls written there draw nothing (the join's line-and-name claim refuses them),
which is most of the class and function misses below. **Contained at 0.2.86-beta (ADR-161, §10.45):** 2,919
such references are refused before the join and counted; the `uses` rows to `CaselessLiteral` fall to 10, and
the key's grade does not move.

## Pre-registered predictions, scored (`PREREG.md`)

| # | Prediction | Result | |
|---|---|---|---|
| H1 | 0 Hobbes-wrong edges among the suspects | 0 of 66 | **met** — for the calls the key grades; C-178's `uses` rows are outside what it judges |
| H2 | suspect rate ≤ 5% | 1.84% | met |
| H3 | poison PASS | PASS, 0 falsely confirmed | met |
| H4 | recall 55–85% | 50.6% | **missed low** |
| H5 | function ≥ 85%; class ≥ 75%; method 40–75%; lambda ≤ 10% | 57.4%; 23.1%; 69.6%; 0% | function and class **missed**; method and lambda met |
| H6 | `syntactic` confirmed ≤ 5% of confirmed | 194 of 3,516, 5.5% | **missed** |
| H7 | base-to-override ≥ 25% of method misses | 721 of 1,030, 70% (a method name another class also defines, a proxy) | met |
| H8 | `hobbes lanes` exit 0 or 3 | exit 0 | met |

H4 and H5's class and function rows are mostly C-178's cost: 1,247 class misses and 130 function misses sit at
`pp.<name>(…)` sites in tests and examples, and 158 class misses are bare `Word(nums)`-style calls inside the
package (`common.py`'s `from .core import *`), tailed `unclassified`.

**Misses (3,434), bucketed by the syntax at the site** (a heuristic over the site's line, for ranking):

| bucket | misses |
|---|---:|
| a class at `pp.<Class>(…)` (C-178), tests 1,035, examples 212 | 1,247 |
| a method call on a value no lane types, or through the base to an override | 1,024 |
| a lambda (C-58) | 250 |
| a bare class name from a star import, in the package (158) and examples (38) | 196 |
| a closure or callable attribute (`self.callable(…)`) | 153 |
| a function at `pp.<name>(…)` (C-178) | 130 |
| other | 434 |

## The C-9 local-alias rule on this cell (ADR-160, built 0.2.85-beta)

Graded once more after the rule, against the same key: **1 edge drawn** (`_MultipleMatch.parseImpl` →
`ParserElement._skipIgnorables`, `core.py:5691`, confirmed), 3,516 → 3,517 confirmed, nothing else moved.
The other 10 alias sites abstain `no-rhs-edge`: `self.expr._parse` and `self._parse` name a class attribute
(`_parse = _parseNoCache`), below the floor, and `cache.get`, `file.write` are outside the repo.
A1 (≤ 19) met; A2 (≥ 4) **missed**, 1; A3 (0 Hobbes-wrong) met; A4 (externals draw nothing) met. A5 and A6
are scored on rich, flask and click in `oracle-grading.md` §10.44.
