# ADR-154 — Lane B reads Python as Linux at one version, and the ingest says where

**Date:** 2026-10-01 · **Status:** accepted (Max, 2026-10-01: "good to proceed with the recommended route";
the twin's node at the live def: "Record at live def") and **built** (0.2.74-beta, unit `61b4`) · **Owner:** Max · **Source:** the handoff's
extraction candidates 1 and 2 (click's silent darwin branch; click's two lane disagreements). Measured
this session: `~/.hobbes/bench/py-platform/` (`PREREG.md` with amendment 1, `RESULTS.md`, `run.sh`,
`probe.py`, `graphcost.py`, `localimport.py`).

Registers **C-173** (a provider limit, P9). Draws 2 edges more on click, withholds 1 evidence row,
moves 5 symbols' lines; every other graded cell's edges are unchanged.

## The cause

The ingest stages a `pyrightconfig.json` (`scipsource.extract_scip`). Once Pyright 0.6.6 loads any
config it assumes the host's platform — `process.platform`, and the image is Linux — and the
interpreter's version (3.12 on every cell here). It evaluates a short list of static conditions
against them, marks the branch it reads as never taken unreachable, and scip-python emits **no
occurrence** there; only `import` lines keep theirs. Nothing records it.

The forms, read from the bundled evaluator (`evaluateStaticBoolExpression`):
- `sys.platform ==|!= "<s>"` (never `startswith`, never `in` — click's `WIN` stays live);
- `os.name ==|!= "<s>"` (`posix` on Linux);
- `sys.version_info <op> (<a>, <b>, …)` (read by its first two elements; *corrected at the review,
  2026-10-01: the first form said a longer tuple is not static*) or `(<a>,)`;
  `sys.version_info[0] <op> <n>`;
- `TYPE_CHECKING` (true), and `<X>.TYPE_CHECKING` where `X` is a name an `import typing` or
  `import typing_extensions` binds (its alias, or the module's name); `True`, `False`;
- `sys` is the name `import sys` binds (its alias, or `sys`); `from sys import platform` is not read;
- `not`, and `and`/`or` read as code flow: one static-false `and` operand makes the true branch
  unreachable wherever it sits, one static-true `or` operand the false branch.

They take effect in an `if`/`elif`/`else`, a `while` (a static-false test's body, a static-true
test's `else`), after a static-false `assert` (the rest of its block), in the operands after a
deciding `and`/`or` operand, and in a conditional expression's dead arm.

## Measured

The probe's model (`probe.py`, the forms above, `ast`), over each cell's own facts stream:

| cell | dead call sites | silent in the stream | twins |
|---|---|---|---|
| click | 104 (80 after `_winconsole.py:35 assert sys.platform == "win32"`) | 104 | 5 |
| flask | 2 | 2 | 0 |
| attrs | 1 | 1 | 0 |
| this repo | 2 | 2 | 0 |

No dead site has an occurrence on its line; the model is the index's reading, on these cells.
The probe read `sys` and `typing` by name and did not read `while`; the alias rule and `while` were
read from the bundle after it, and this decision includes them (they only add regions where they occur).

- On click, 18 edges sit in dead regions, all lane A's `syntactic`; `_winconsole.py` has no lane B
  definition at all. Unnarrowed, lane B would speak there (60 in-repo definitions, 64 in-repo
  references) — but see *Routes not taken*.
- **A twin** is a qualname a file defines in a dead region and once outside it. `graph._symbol_records`
  keeps the *first* record, so click's `_termui_impl.raw_terminal` and `.getchar` are recorded at
  the win32 defs (884, 887). Lane B names the live defs (938, 964), which match no symbol, so two
  real calls are drawn by nobody: `_termui_impl.py:965` (`getchar → raw_terminal`) and
  `termui.py:980` (`termui.raw_terminal → _termui_impl.raw_terminal`). Lane A's guess (884) is the
  first of click's two lane disagreements.
- **A function-local import** is not one of ADR-046's bindings, so the fallback binds a bare call to
  the module's own def of that name: click `termui.py:364 get_pager_file()`, the second
  disagreement. The shape — a bare call whose enclosing function imports the name, in a module that
  also defines it — has **1** site on the four cells. No key row sits at any of the three sites.

## The decision

Hobbes states the reading it already gets, and stops guessing against it.

1. **Pin the platform.** The staged config names `"pythonPlatform": "Linux"`, so the assumption is
   Hobbes's, written down, and not the host's by accident. The index is unchanged by it (the image
   is Linux). The version stays the interpreter's (the venv's, or the image's).
2. **Read the version Pyright used** from the Python facts' own stdlib monikers (`python-stdlib
   <major>.<minor>`), carried on the facts as the assumed reading. No moniker, no version: a
   version test is then read as not static (nothing is dead by it), and the record says so.
3. **Lane A models the forms above** (a new `extract/pystatic.py`, tree-sitter, exactly the list:
   nothing Pyright 0.6.6 does not evaluate, nothing it does left out). The parse records each static
   test and its spans; the regions are evaluated only where lane B ran for Python, with `linux` and
   the read version. Without lane B nothing is evaluated and the graph is what it was (P6).
4. **A degradation record per file with a dead region** (`stage: scip-python`): the line spans, the
   forms, the reading (`Linux / Python 3.12`), how many of lane A's edges there are `syntactic`
   only, and the twins — citing C-173 and this ADR. `list_blind_spots` serves it.
5. **A twin's node is its live def.** Where a qualname has exactly one def outside the file's dead
   regions and one or more inside, the symbol record takes the live def's `line` and `end_line`
   (the id is unchanged). Lane B's references to it then land. Then, before the join:
   - a fallback entry whose target is any def of a twin names the live def, the node's one
     reading, so lane A and lane B agree (*corrected at the review, 2026-10-01: the first form
     dropped the entry, which lost a drawn call through an aliased import — see* Built);
   - a call site inside a dead def of a twin is not drawn (its fallback entry is dropped; lane B
     has nothing there): the projection takes the caller from lane A's scope qualname, so it
     would be filed under the live node. Counted in the record.
   A qualname defined twice with no def in a dead region, or with two live defs, keeps the first
   record, as today.
6. **A function-local import shadows the fallback.** `pysource` records each name an `import` or
   `from … import` binds inside a function (the alias if any; `import a.b` binds `a`; `*` binds
   nothing), with the function's extent, in a list of its own, and `graph.resolve_call_sites`
   refuses the fallback for a bare call it shadows, as `_shadowed` does for ADR-046's bindings.
   It is **not** one of ADR-046's bindings: the tail's `local-binding` class means "the call stays
   inside that file", which an import is not.

## Predicted effect (checked on the real cells before merging)

- click: +2 `calls` edges, `semantic` (965 and 980 above); the evidence row at 930 withheld, and its
  edge (`getchar → _translate_ch_to_exc`) still drawn by 971; `raw_terminal` recorded at 938–962,
  `getchar` at 964–972, the three `types.py` TypedDicts unchanged (their live def is the first);
  `site_disagreements` 2 → 0; 3,756 confirmed, 0 contradicted, poison PASS.
- flask, attrs, this repo: edges identical; a record per file with a dead region (flask 2 sites,
  attrs 1, this repo 2).

## Routes not taken

- **b, turn the narrowing off** (`pythonPlatform: "All"`, unknown to 0.6.6 and so undefined). Lane B
  would speak in every region, about 64 in-repo references on click and next to nothing elsewhere.
  But a twin then becomes one moniker, the first def a definition and the second a *reference*,
  and a call in the second's arm (`965`) is filed under the first — a wrong edge ADR-150 does not
  catch, since it reads several definition occurrences. It would also move monikers on every
  Python cell (typeshed's own platform branches).
- **c, register only.** It leaves the limit where no tool meets it.

## What this leaves

- C-173: code Pyright reads as never run on Linux at the interpreter's version has no lane B
  answer; lane A's edges there are `syntactic` alone, and a definition there is lane A's only.
- A qualname a file defines twice outside a static test (`try`/`except`, `if HAS_X:`) is still one
  node at the first def; not measured here, a candidate.
- An aliased function-local import (`from .testing import FlaskClient as cls`) draws nothing
  (click 1, flask 2); not read.
- scip-python names no occurrence for flask's `urlsplit`, import or call; not read.

## Built (0.2.74-beta, unit `61b4`)

As decided, with one departure the doer named and two defects fixed at the review (`c8eab1b`).
- **Step 6, narrower, accepted.** Lane A's import table already reads a function-local import, so
  `_imported_here` refuses a shadowed call only where lane A resolved it into the calling file;
  the literal rule would have dropped right edges without lane B. None of 804 function-local
  imports on the four cells conflicts with a different top-level import of the name
  (`localimport_conflict.py`), so it draws no less. A conflicting pair would still be lane A's
  guess.
- **Step 5 dropped lane A's guess at a twin; it now names the live def.** The drop lost click
  `termui.py:980` (`from ._termui_impl import raw_terminal as f; return f()`): the index spells
  the site `raw_terminal`, lane A `f`, and the join places it only at its own column against
  lane A's answer (ADR-143). The host's `lane_b` case, written from this ADR, caught it.
- **A `sys.version_info` tuple of three or more elements is static**, read by its first two.
- Host: pytest 2,535, `lane_b` 18 of 18. flask 1,524 and click 3,756 confirmed, unchanged, 0
  contradicted, poison PASS; flask's export byte-identical. click: +3 edges
  (`getchar → raw_terminal` at 965, two `uses` at the twins' import lines), 980 and
  `getchar → _translate_ch_to_exc` `syntactic` → `semantic`, the 930 row withheld, the twins at
  938 and 964, lane disagreements 2 → 0 (`oracle-grading.md` §10.38).

## Amendment — 2026-10-03: a branch that ends in `raise` (0.2.94-beta, C-173 widened)

**Status:** accepted (Max, 2026-10-03, the recommended route: extend the detector for `raise` only).
ADR-164's regrade found rich's `_win32_console.py` with no lane B answer from line 22 to 577, while C-173's
record for the file named line 12 alone: the module raises `ImportError` in the `else` of `if sys.platform
== "win32":`, and Pyright reads everything after the `if` as never run. The limit was not named where it
applies.

- Lane A's `if` context gains one span: where the branch a reading runs ends in `raise` (its last statement,
  comments aside), the rest of the block after the `if` is killed under that reading. Only where the
  branch's running is one test's reading: the `if` on True, and its `else` on False when no `elif` stands
  between them. An `else` after an `elif` runs only when both tests read False, which one test cannot say.
- `return`, `sys.exit()` and other `NoReturn` calls are not read; C-173 says so.
- Measured over rich, flask, click, pyparsing and this repo: two files change, both in rich —
  `_win32_console.py` (16–661 added) and `_windows.py` (25–30, after an `else: raise` inside a `try`).

Built: `pysource._ends_in_raise`, `pysource._rest_of_block`, the `if` branch of `_collect_static_tests`.
Tests: `test_pystatic.py` (both shapes, a branch whose `raise` is nested, an `else` after an `elif`, and a
`raise` on the live reading).
