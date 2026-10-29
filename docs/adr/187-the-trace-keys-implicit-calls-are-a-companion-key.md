# ADR-187 — The trace key's implicit calls are a companion key

**Date:** 2026-10-29 · **Status:** accepted (Max, 2026-10-29: "yeah proposed for both are good": route a, a
companion key that is never merged into the standing one, with H-38 fixed first) · **Owner:** Max ·
**Source:** C-174, `currently-open.md` (Python: "whether to extend the standing trace oracle").

## Context

The Python trace oracle (O6, ADR-089) keys a call from a `CALL` event, plus `with` (H-37) and an instance's
`__call__`. A call the language makes with no call token (a property's getter, an operator's or a loop's
dunder, `__str__` from `f"{x}"`, a descriptor's `__get__`) makes no `CALL` event, so the standing keys hold
none of them, and C-174 has told users that their share is "unmeasured".

A measuring copy of the tracer (2026-10-03/04, `~/.hobbes/bench/c174-counts-2026-10-03/python/trace-run/`)
read them at the callee's `PY_START` from the opcode its caller stands on, into a separate list. On the four
standing Python cells, the regular pairs were identical to the standing keys, and the implicit rows were flask
208, structlog 191, click 676 and rich 1,308 (13.4%, 15.4%, 17.9% and 26.0% of confirmed), mostly property
getters. No Hobbes edge was contradicted.

Merging those rows into the standing key would do two things the measurement showed:
- **Every recall figure falls by denominator only** (graded then on the cells' on-disk ingests,
  0.2.99/0.2.100-beta: flask 55.7% → 51.8%, structlog 77.8% → 69.5%, click
  82.0% → 71.5%, rich 93.6% → 75.3%), which breaks the comparison with every grade made so far. The fall is
  C-174's cost, which Hobbes declares, not a new miss.
- **What "observed line" means changes.** A trace bucket is judged from the targets seen at a line (an edge
  at a line with targets, none of them its own, is `suspect`). Rich's `markdown.py:458` → `rich.text.Text`
  moved `unobserved` → `suspect` only because an implicit row now sat on its line.

H-38 (the tracer ran a repo's `__getattr__`) was fixed first, on 2026-10-29: the extension reads more frames.

## Decision

1. **The tracer keys implicit calls into their own list.** The export gains `implicit` (sites in the
   `sites` shape) and `implicit_dropped_as_called`. A target is implicit when it is an in-repo dunder, or a
   def decorated `property`, `cached_property`, or a property's `setter`/`getter`/`deleter`, that starts with
   no `CALL` event of its own, keyed at the caller frame's line, `via: "implicit"`. Each target carries the
   caller opcodes it was met on and their families (`attribute`, `operator`, `iteration`, `truth`, `format`,
   `builtin-call`, `with`, `other`), for triage. A target that a `CALL` recorded at the same line in any run is
   not implicit and is dropped and counted. Never keyed: construction and class-creation hooks (`__init__`,
   `__new__`, `__init_subclass__`, `__set_name__`, `__post_init__`, `__prepare__`, `__subclasshook__`,
   `__instancecheck__`, `__subclasscheck__`) and `__del__`, which no caller line writes; `__enter__` and
   `__exit__`, which H-37 already keys in `sites`. **`sites` is byte for byte what it was.**
2. **The grader judges nothing from `implicit`.** Buckets, the confirmation and suspect rates, the standing
   recall and the poison check read `sites` alone, as before.
3. **It prints a second recall beside the standing one, never in its place** (the `recall_collapsed`
   precedent): `recall_with_implicit` = (standing hits + implicit hits) / (standing in-repo pairs + implicit
   in-repo pairs), with `implicit_pairs`, `implicit_confirmed` and the implicit pairs split by family. It is
   a recall figure; a trace cell measures no precision (C-60).
4. **The four standing Python keys are regenerated** with this tracer (flask, structlog, click, rich), as
   new key directories beside the old ones; each cell record names both. The other trace-graded Python cells
   (this repo, pyparsing, icalendar) gain the list when they are next keyed.
5. **C-174 names the measured shares** where users meet it.

## Consequences

- A rule that narrows C-174 for a property or a dunder becomes gradable, but it is still measured on a
  held-out cell picked before the rule (`docs/lessons.md`). The fitted cells' implicit rows are not a target.
- The standing figures stay comparable across sessions; the companion figure says how much of what the
  interpreter ran C-174 leaves undrawn.
- The tracer reads more frames: every entry of a candidate def is read, never disabled (as H-37's). A traced
  run is slower; H-39 (the shared re-entrance guard) loses more events the slower a callback is, so the run's
  cost is recorded per cell.
- Not covered: `async with`, `__aenter__`/`__aexit__` and an async iterator's hooks (their coroutines start on
  a `SEND`), and a dunder or property of a class outside the repo (an external target, as everywhere).
