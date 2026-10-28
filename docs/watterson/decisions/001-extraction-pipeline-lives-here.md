# 001: The Hobbes extraction pipeline moves into this repo

- Status: accepted
- Date: 2026-10-15

## Context
This repo joins Hobbes's extraction pipeline with an easy way to connect to
model providers (see `docs/overview.md`). Hobbes is the user's own system. It is
the fixed core of this project, not a component we might swap out. The
provider-connection layer, by contrast, is open (see DEC-002).

## Decision
- Bring the extraction pipeline (`hobbes_public/pipeline/src/hobbes/extract/`
  and whatever it needs to run and test standalone) into this repo, so it is
  owned and developed here.
- **Defer the narrative pass** (`hobbes/narrate/`, the module docs). It does not
  move now.
- Hobbes is never replaced by an alternative. Only the provider layer is up for
  selection.

## Consequences
- This repo gains a Python (uv) toolchain. Its exact commands go into
  CLAUDE.md "Commands" when the code lands.
- Still open, and to be settled when the move is planned: the exact file cut,
  whether git history is preserved, the repo layout, and whether the lane B
  (SCIP/Podman) path comes along at once or lane A ships first.
- Once moved, the code here is the working copy. hobbes-public stays a
  read-only reference.
