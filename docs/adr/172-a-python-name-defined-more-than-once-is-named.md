# ADR-172 — A Python name one scope defines more than once is named: one node at its first def, whichever runs

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: "register the decision for python") and **built**
(0.2.101-beta) · **Owner:** Max · **Source:** the held-out structlog cell
(`oracle/cells/structlog-py-2026-10-03.md`); ADR-155's *What this leaves*.

Registers **C-186**, surfaced. Draws nothing differently.

## What is wrong

structlog writes

```python
_IS_WINDOWS = sys.platform == "win32"
if _IS_WINDOWS:
    def _init_terminal(who, force_colors): …   # line 72
else:
    def _init_terminal(who, force_colors): …   # line 103
```

ADR-154 reads a `sys.platform` test written in the `if`, not one held in a variable, so both branches read
live. scip-python makes the two defs one definition at the first, and the graph keeps one node per qualname,
so `structlog.dev._init_terminal` is lines 72–100, the Windows def, while Linux runs line 103's. The call at
`dev.py:815` is right by qualname and read as a suspect by the trace key. ADR-155 called the node's lines
"display", and nothing named the limit. Rust registers the same shape (C-182, the cfg twin) and Go (C-183,
`init`); Python did not: a precedent-1 gap.

## The decision

1. **Register C-186** in `extraction-call-graph.md`: a Python name one scope defines more than once is one
   node at its first def, whichever runs — an `if`/`else` or `try`/`except` pair the static reading does not
   settle, a later def that replaces the first, an `@overload` group. A property's accessors are one property
   and are left out.
2. **Name each one** (`_python_repeats`, `_python_repeats_record` in `extract/__init__.py`): one
   `python-repeats` degradation record per ingest, with the count by kind (`repeated`, `overload`) and
   examples with every def's line, served by `list_blind_spots` and the ingest summary. Where lane B ran,
   ADR-155's later live defs are the reading: a def ADR-154 found dead, or a twin whose node it moved to
   the live def, is settled and not named. Without lane B every repeated qualname is named. Computed before
   Go's `init` spans join the later defs.
3. **Nothing else changes.** No edge, node or tier moves.

## Not taken

- **Move the node to the def that runs.** No reading says which: the test is a variable, an exception, or
  the order of definition; guessing would draw the wrong one as surely as the first.
- **A node per def.** The qualname is the name callers write; two nodes for it would split every edge.

## Built (0.2.101-beta)

`tests/test_python_repeats.py` (5): lane A names a branch pair, a redefinition and an `@overload` group, not
a property's accessors; with ADR-155's later defs only the unsettled name is named; the record's wording and
order; no record where nothing repeats. Ingested with lane B: structlog 3 names (`dev._init_terminal`,
`processors._items_sorter.ordered_items`, `processors._make_stamper.now`), click 6 and 16 `@overload`
groups (its ADR-154 twins `raw_terminal` and `getchar` settled, not named); edges and symbols byte-identical
to 0.2.100-beta's.
