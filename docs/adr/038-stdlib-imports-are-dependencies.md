# ADR-038 — Stdlib imports are dependencies; the noise rule is lifted

**Date:** 2026-08-15 · **Status:** accepted · **Lifts:** C-3 ·
**Supersedes:** ADR-007's stdlib-noise clause

## Context

ADR-007 dropped standard-library imports at resolution — "stdlib is noise;
third-party is signal" — and M6 applied the same rule to Node builtins. Go
(V2.M5) never got the filter: `gosource` emits an `ext:` node for every
import that resolves to no in-repo package, so the dogfood graph carried
`ext:os`, `ext:fmt`, `ext:syscall` while a Python module importing
`subprocess` showed nothing. The 2026-08-15 register audit found the
asymmetry unregistered, and found it worse than the old uniform silence:
visible Go stdlib teaches a reader that stdlib *is* modelled, so a Python
module's missing node read as positively clean rather than unexamined.

Two ways to harmonise: filter Go's stdlib to restore the uniform rule, or
emit stdlib everywhere and lift C-3. Max: "no need to hide what hobbes
does capture."

## Decision

Every syntax provider emits `ext:` nodes for stdlib imports, exactly as it
does for third-party ones.

- **Python** (`extract/graph.py`): the `sys.stdlib_module_names` skip is
  removed. `import os` → `ext:os`.
- **TS/JS** (`tsextract/extract.mjs` `externalName`): Node builtins are
  kept and **normalised to a `node:`-prefixed name** — `fs`, `node:fs` and
  `fs/promises` all become `node:fs` (node id `ext:node:fs`). The prefix
  keeps a builtin off any node an npm package with the same name would
  claim (a real npm `fs` exists), and collapses both import spellings onto
  one node, mirroring the top-segment rule already applied to packages.
  The `node:test` special case in framework detection is gone: the import
  record now exists like any other.
- **Go** (`gosource`): unchanged — it was already right, just alone.

No schema change: `ext:` nodes and their `imports` edges are the existing
shapes, there are simply more of them.

## Consequences

- **C-3 is lifted** — the register's #2-ranked debt, with the
  security-shaped question ("does this touch `subprocess`?") it existed
  for. The graph now answers it for all three languages.
- Graph node counts grow (the dogfood repo gains ~15 Python stdlib nodes
  alongside Go's ~20). Render noise is unchanged where it matters:
  externals are hidden by default in the surface (ADR-023) — hidden, which
  is a view choice, not dropped, which was an information choice.
- The lane-agreement report is unaffected: `ext:` nodes were always
  excluded from comparison as lane-A-only (`_LANE_A_ONLY`).
- Enrichment-pack detection is unaffected: it keys on specific package
  names (`ext:fastapi`, express imports), which gained neighbours, not
  competitors.
- ADR-007's other clauses (resolution rules 1–4, under-approximation)
  stand untouched; only the noise clause is superseded.
