# 012: `hobbes render` moves in from hobbes-public

- Status: accepted
- Date: 2026-10-16
- Narrows: open-work item 4; DEC-011 consequence "bringing over `render.py`"
- Builds on: DEC-003 (plain copy, thin CLI)

## Context
DEC-011's graph view starts as the module-level Mermaid of hobbes-public's
`hobbes render`, drawn in the terminal. The TUI will need it whichever way
it connects to our Python layer (being surveyed), and a Mermaid export is
useful on its own now.

`render.py` (90 lines, stdlib only) reads `graph.json` through
`hobbes.artifacts`, the schema-version gate (ADR-028). DEC-003 left
`artifacts` behind because nothing here needed it yet.

## Decision
1. Copy verbatim from `hobbes_public@2089e22` (MIT,
   `LICENSE.hobbes-public`), with provenance in this record and the commit,
   as DEC-003 did for the extract package:
   - `pipeline/src/hobbes/render.py`
   - `pipeline/src/hobbes/artifacts.py` (120 lines; imports only
     `hobbes.extract.SCHEMA_VERSION`)
   - `pipeline/tests/test_render.py`, `pipeline/tests/test_artifacts.py`
2. They stay verbatim, like `hobbes.extract`: real changes belong in
   hobbes-public.
3. `hobbes render [--repo DIR]` in our thin CLI, adapted from hobbes-public
   `cli.py` (`_cmd_render`, lines 737-748; its parser, lines 1845-1855).

## Consequences
- `hobbes render --repo DIR` prints the module graph as Mermaid after an
  ingest; a missing or wrong-version `graph.json` is an error that names
  its fix.
- Other readers here (`permissions.load_test_files`, the freshness check)
  still read the derived files directly; moving them onto `artifacts` is
  not part of this record.
- Rendering a live session's snapshot graph (DEC-009) is left to the TUI
  work: `to_mermaid` takes a graph document, so any caller can pass one.
