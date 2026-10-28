# 003: How the extraction pipeline is moved in

- Status: accepted
- Date: 2026-10-15

## Context
DEC-001 brings the extraction pipeline here. The cut line and the hazards are in
`docs/plans/extraction-move.md`.

## Decision
- **Plain copy, no history import.** One commit records the provenance
  `from hobbes_public@2089e22`. hobbes-public stays the historical record.
- **Keep the hobbes layout:** `pipeline/src/hobbes/extract/` plus `tsextract/`
  and `scip/` at the repo root. The package stays `hobbes.extract`. This keeps
  the `parents[4]` path anchors valid with no edits.
- **Thin new CLI** around `ingest`. The old `cli.py` is not lifted whole.
- **Lane B:** the code comes with the package. This repo does not build the
  sandbox image. Lane B **runs where podman and `hobbes-session:local` exist**
  (built from hobbes-public) and skips otherwise. When it runs it needs
  `scip/`'s npm deps. _(Amended 2026-10-16, accepted.)_
- **Separate cache:** the thin CLI defaults `HOBBES_CACHE_DIR` to
  `~/.watterson/cache`, so this repo never shares cache entries with
  hobbes-public. The extract package is unchanged. _(Added 2026-10-16.)_
- **Scope:** the moved code stays verbatim. This repo stitches pieces together
  and does not develop Hobbes. _(Added 2026-10-16.)_

## Consequences
- Restructuring or renaming the package can happen later as its own decision.
  The cost of that is known: 4 path anchors and about 128 import lines.
- `git blame` here starts at the move commit. For earlier history, use
  hobbes-public.
