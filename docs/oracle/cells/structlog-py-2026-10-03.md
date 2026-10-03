# Oracle cell — hynek/structlog, Python zone `.`, 2026-10-03 (held out)

**Repo:** `hynek/structlog` (MIT / Apache-2.0) 26.1.0 at `8174a86`, `~/.hobbes/bench/oracle/repos/structlog`.
**Held out:** Hobbes had never ingested, simulated or keyed this repo, and no rule was changed for the cell.
Picked on 2026-10-03 as the held-out cell for ADR-171 (an instance's `__call__`, C-174) by an `ast` scan of
ten candidates' written sites, for diversity (Max: "not super important which candidate is selected, go for
diversity"): a logging library whose processors and renderers are classes whose instances are called
(`TimeStamper(fmt="iso")(None, None, event_dict)`), 136 name-matched sites over 31 classes. The predictions
were pre-registered in `~/.hobbes/bench/heldout-structlog/PREREG.md` (sha256 `d65d5f69…471f`, in `43a13ce`'s
BUILDLOG entry) before the ingest and before the key existed.

**Hobbes at** 0.2.99-beta (`43a13ce`), image `dcbe621304cd`. **Oracle:** `py-trace` (CPython 3.12.13
`sys.monitoring`). **Venv:** the clone's `uv sync --group tests --python 3.12`. The suite is its `testpaths`
(`tests`), `pytest-randomly` off: untraced 928 passed, 20 skipped; traced **926 passed, 2 failed, 20 skipped**
per run (`test_config.py::TestFunctions::test_get_logger_passes_positional_arguments_to_logger_factory` and
`test_tracebacks.py::test_recursive`, both under the tracer only). Union over 2 runs.

**Command:** `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/structlog . ~/.hobbes/bench/oracle/structlog-py
--lang py --runs 2 -- tests -q -p no:cacheprovider -p no:randomly`. The log is
`~/.hobbes/bench/heldout-structlog/run.log`; output dir `~/.hobbes/bench/oracle/structlog-py/`.

Ingest line: `graph.json: 94 nodes, 374 module edges, 1114 symbols, 1069 call edges, 1964 uses edges, 18 implements edges`; `capture [python]: 77.8% of 3034 detected call sites accounted`.

```
cell   oracle py-trace 3.12.13 sys.monitoring (trace)  sha 8174a86a
oracle ran contained (ADR-092)
hobbes edges 1261: confirmed 1110  suspect 11  unobserved 140 map[line-mixed:3 line-not-called:10 not-loaded:127]
confirmation rate 88.0% (1110/1261 hobbes edges; coverage-limited, not precision)
suspect rate 1.0% (11/1121 executed hobbes edges; triage queue, never contradicted)
recall-against-executed 69.7% (1110/1593 observed in-repo pairs) over 2 run(s) of [… -m pytest tests -q -p no:cacheprovider -p no:randomly]; external python targets 1079; misses map[observed→class:42 observed→closure:74 observed→function:45 observed→lambda:25 observed→method:297]
coverage: hobbes sites observed 1078/1215 (88.7%); files loaded 41/46; declarations started 900/1129; c-callee calls 36274; subprocesses traced 0
  recall[observed→class    ]  90.2% (386/428)  misses 42 = 8.7% of all misses
  recall[observed→closure  ]  35.1% (40/114)  misses 74 = 15.3% of all misses
  recall[observed→function ]  91.3% (474/519)  misses 45 = 9.3% of all misses
  recall[observed→lambda   ]   0.0% (0/25)  misses 25 = 5.2% of all misses
  recall[observed→method   ]  41.4% (210/507)  misses 297 = 61.5% of all misses
  tier semantic   confirmed 1083  suspect 11  unobserved 140
  tier syntactic  confirmed 27  suspect 0  unobserved 0
```

Poison: 1,261 seeded, 999 refused, 262 unjudged, **0 falsely confirmed (PASS)**. `hobbes lanes` (on the
0.2.100-beta ingest): 958 sites both lanes resolved, 0 disagree, exit 0.

## The 11 suspects, read row by row

| Rows | Shape | Verdict |
|---|---|---|
| 6 | `.bind`/`.unbind`/`.try_unbind` on a receiver declared `BindableLogger`, a `typing.Protocol` (`_config.py:382, 400, 403`; `threadlocal.py:120, 152, 156`); the trace saw `BoundLoggerBase`, `BoundLoggerLazyProxy`, `AsyncBoundLogger` | C-60's declared target |
| 1 | `self.error(…)` in `_native.py:49`, `self` declared `FilteringBoundLogger` (a Protocol); the trace saw the closure `make_method.<locals>.meth` | C-60's declared target |
| 3 | `get_logger().bind(…)` / `.info(…)` in `tests/test_stdlib.py:1658, 1685`, declared `BoundLogger`; the trace saw the lazy proxy and `AsyncBoundLogger` (the test configures another wrapper class) | C-60's declared target |
| **1** | `_init_terminal(…)` at `dev.py:815`. The file defines it twice, under `if _IS_WINDOWS: … else:`, with `_IS_WINDOWS = sys.platform == "win32"` a variable; no dead-lines record names `dev.py` (ADR-154 reads a `sys.platform` test written in the `if`), so both branches were read live. The index makes the two defs one definition at the first (C-170's note): the graph's node is lines 72–100, the Windows def; on Linux the trace ran line 103's | **The node is the def that does not run.** The edge's qualname is right; its position is the dead twin's. Rust registers this shape (C-182) and Go (C-183); Python's is called "display" in ADR-155 and is not registered. Taken to Max (`currently-open.md`) |

0 Hobbes-wrong edges by target identity; 1 row whose node names the twin that does not run.

## Predictions (scored after ADR-171, 0.2.100-beta)

Re-ingested and graded against the stored key (`~/.hobbes/bench/instance-call/after/structlog/`):
1,110 → **1,240** confirmed, 11 → 11 suspect, 140 → 140 unobserved, recall 69.7% → **77.8%**, poison PASS
(1,391 seeded, 0 falsely confirmed). `instance_calls`: 160 sites, 134 drawn, 17 `no-call-edge`, 9
`not-a-class`. The export gained 130 rows and lost none; every added row is the rule's and every one is
confirmed.

| # | Result |
|---|---|
| S1 at most 136 site rows drawn | met: 134 sites, 130 rows at the grader's grain |
| S2 at least 80% of executed drawn rows confirmed | met: 130 of 130 |
| S3 0 Hobbes-wrong rows added, 0 contradicted | met |
| S4 recall +1.0 point or more | met: +8.2 points |

The other cells' predictions (P1–P2 on pyparsing, F1–F2 on the fitted cells) are scored in
`oracle-grading.md` §10.47.
