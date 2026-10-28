# ADR-182 — A function's own import binds its name in that function only

**Date:** 2026-10-28 · **Status:** accepted (Max, 2026-10-28: "fix is a good idea since its small") and
**built** (0.2.122-beta) · **Owner:** Max · **Source:** the dev environment's fold (ADR-181): a local run of
CI's `graph` job stopped at `hobbes lanes`, one `unexplained` row in `hobbes/watterson/cli.py`. Measured in
`~/.hobbes/bench/local-import-scope-2026-10-28/`.

Registers and lifts **C-195** the same day.

## What is missing

Lane A's import table (`graph._NameEnv`) was one dictionary per module, filled from every import in the
file in source order, so the last import of a name won everywhere. Python binds a name a function imports
in that function only. Two functions that each import `exit_code` from two modules (watterson's
`_cmd_freshness` from `freshness`, `_cmd_agents_check` from `providers.staleness`) both resolved to the
later one. Lane B named the right one; `hobbes lanes` counted the row `unexplained` and exited 1. Where lane
B is absent, the wrong `syntactic` edge was what the graph drew. No register entry named it.

ADR-154 step 6 had half of this: a function's import shadows the calling module's *own* def of the name
(`_imported_here`). It did not cover a function's import shadowing another import.

## Decision

- `_NameEnv` keeps a function's own imports apart, each with the innermost function's extent (pysource's
  existing `local_imports` fact), and answers `binding_at(name, line)`: the innermost function import
  spanning the call's line, else the module's binding. Rule 2 (a bare name) and rule 3 (a module-bound head
  of a dotted call) ask it with the call's line.
- A function's import lane A cannot place (outside the repo, or a plain `import a.b`) still shadows the
  module's name inside the function: nothing is drawn there, rather than the module's binding.
- `symbol_imports` (pytest's fixture lookup, ADR-137) reads module-level bindings only, as pytest reads
  module globals.
- Rule 1 still asks the module's own defs first, and `_imported_here` still refuses that answer under a
  function's import: unchanged, a refusal and not an edge.

## Predicted

Every lane A site that moves names the import Python binds at that line; nothing else moves.

## Measured

Lane A's own resolutions (`resolve_call_sites`) before and after, over 22 repos: the six standing Python
cells, 14 held-out clones (`c9-local-alias/candidates`, `attr-call-step0-2026-10-03/candidates`), this repo
at `2089e22` and watterson-environment at `a65b6b1`; 37,000+ resolved sites. Each moved site graded by an
`ast` read of Python's scoping (`grade.py`), not by tree-sitter.

- **3 sites moved, 3 right:** watterson `cli.py:1051` (`freshness.exit_code`, was `staleness`'s), and
  cachetools `__init__.py:762` and `:764` (`_cached._wrapper`, the function's own `from ._cached import
  _wrapper`; was `_cachedmethod._wrapper`). cachetools is held out.
- End to end (a lane A ingest of each repo, both arms): recorded in `RESULTS.md`.

## Residual (C-195)

- An import in a **class body** binds the class namespace, which methods do not see; lane A binds it
  module-wide. 32 such imports in the 22 repos (icalendar 30, pyparsing 2); 0 lane A sites resolve through
  one.
- One name imported **twice in one scope**: lane A keeps the last; Python's answer depends on flow. 81
  such names, 32 resolved sites; 31 name one symbol either way, and the one that does not is C-181's
  `try`/`except ImportError` shape (the `ministdlib` fixture), already registered.

## Not done

Asking a function's own import ahead of rule 1 (Python asks the local scope first) would draw an edge where
`_imported_here` now refuses one: a recall change, not this unit's.
