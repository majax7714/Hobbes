# ADR-167 — A module loaded by name is named where it reads unguarded

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route **1** of three, "name the load at the
point of use") and **built** (0.2.96-beta) · **Owner:** Max · **Source:** C-179's entry; this repo's own
loads.

Surfaces **C-179** (unsurfaced → partial). Draws no edge: it records where a load is and says so.

## What is wrong

A Python file that loads a module by name — `importlib.import_module("pkg.mod")`, `__import__("pkg.mod")`,
or `importlib.util.spec_from_file_location("name", path)` then `exec_module` — draws no `imports` edge, so a
test that reaches a module only that way does not reach it in the graph. `tests_guarding` then answers
"unguarded" and `hobbes review` lists the module under "new code no test reaches", and nothing says why.
C-179 was registered **unsurfaced** on 2026-10-02 (this repo's `shanks_tracker`, loaded by path, kept the
graph job red until its test changed to a plain import).

## Measured (this repo, the only real-source case at hand)

| form | sites | argument as written |
|---|---:|---|
| `spec_from_file_location` | 3 tests | a module-level path, `Path(__file__)….parents[1] / "scripts" / "ttt_probe.py"`, or the same chain inline |
| `__import__("atlas0.world", …)` | 1 (`bench/atlas0`) + 1 test | a literal in-repo module name |
| `__import__("collections")`, `__import__("os")` | 3 tests | a stdlib name |

## The decision (Max: route 1)

1. **Lane A records each load** (`pysource`, where the grammar is): a call whose callee's last name is
   `import_module`, `__import__` or `spec_from_file_location`, with what it names *as written*. For the
   first two, the first argument when it is a plain string literal. For `spec_from_file_location`, the
   location argument (second, or `location=`): a string literal, or the trailing string literals of a `/`
   chain (`… / "scripts" / "ttt_probe.py"` → `scripts/ttt_probe.py`), followed through one module-level
   assignment when the argument is a bare name; kept only when it ends in `.py`. Anything else is recorded
   with nothing written.
2. **The ingest places a load** on an in-repo Python module only exactly: a name equal to a module id, or a
   written path equal to one module's path or the unique module path ending in `/` plus it. Two candidates,
   none, or nothing written: not placed. The graph carries the loads as `dynamic_loads` (`path`, `line`,
   `via`, `written`, `target` or empty), only when there are any.
3. **Said where the reader meets it.** `tests_guarding`, after "unguarded", names each placed load of the
   target's modules (`… is loaded by name at <file>:<line> (`<via>` `<written>`) …(C-179)`); `hobbes review`
   adds the same reason beside a listed module and in `--json` under `coverage.loaded_by_name`. One
   `python-loads` record per ingest counts the loads, placed and not, so the ones that name nothing are
   named in `list_blind_spots`.

**No edge.** A placed load is not drawn as `imports`: the name or path is read syntactically, a test may load
a module it does not exercise, and a drawn edge would make the review's "unguarded" disappear rather than
say why. Drawing a tiered edge is route 2, a recall rule, and is not taken.

C-179 becomes **partial**: a placed load is named at the point of use; a load that names nothing placeable
(a computed name, a path built from non-literals) is only counted.

## Alternatives considered

- **Route 2: draw a `syntactic` `imports` edge** from a placed load. A new rule; measured first if ever.
- **Route 3: leave it unsurfaced.** Debt the register already flags.
- **Match a path by its basename alone.** `ttt_probe.py` could be any of several; only an exact or unique
  suffix is placed.

## Built (0.2.96-beta)

`extract/pysource.py` (`DynamicLoad`, `_dynamic_loads`, `_load_written`, `_path_tail`), `extract/graph.py`
(`_dynamic_loads`, the `dynamic_loads` key), `extract/__init__.py` (`_python_loads_record`), `review.py`
(`coverage.loaded_by_name`, the note), `go/internal/knowledge` (`dynamicLoad`, `loadsOf`, the line after
"unguarded"). Tests: `test_dynamic_loads.py`, `test_review.py`, `knowledge_test.go`.

**Effect, lane A's read** (no edge moves anywhere; a graph without a load is byte-identical): this repo
8 loads, 5 placed — `ttt_probe`, `calvin_probe`, `hobbesmini.guard` (the three tests' scripts) and
`atlas0.world`, `atlas0.check` — and 3 stdlib `__import__`s not placed. rich 2, flask 2, click 1,
pyparsing 1, none placeable (a computed name, or `pydoc`): each gains the key and one record.
