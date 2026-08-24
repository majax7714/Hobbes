# ADR 005: tree-sitter via py-tree-sitter for the Python extractor

Date: 2026-08-10
Status: accepted

## Context

The architecture (§3.1) and build plan (M1) fix tree-sitter as the parsing
substrate but not the concrete packages, and Python has a tempting
alternative: the stdlib `ast` module.

## Decision

Use **`tree-sitter`** (py-tree-sitter bindings) plus the
**`tree-sitter-python`** grammar wheel from PyPI. These are the two
runtime dependencies of the extractor.

Stdlib `ast` is rejected deliberately even though it is exact for Python:
the M3 (HCL) and M6 (TypeScript) extractors must be tree-sitter walks, so
building M1 on `ast` would mean two parsing substrates, two node-walking
idioms, and no shared machinery — the architecture chose tree-sitter
precisely for that uniformity. Grammar wheels also parse without a compiler
toolchain at install time.

## Alternatives considered

- **stdlib `ast`** — exact and dependency-free, but Python-only; forks the
  extractor architecture at the first fork in the road.
- **`tree-sitter-languages` / `tree-sitter-language-pack`** bundle wheels —
  convenient many-grammar bundles, but we need exactly one grammar now and
  can add `tree-sitter-hcl`/`tree-sitter-typescript` individually when M3/M6
  arrive.
- **LibCST / parso** — Python-only, same objection as `ast`.

## Consequences

- One parsing idiom across all extractors; M3/M6 add a grammar wheel and a
  walker, not an architecture.
- Tree-sitter's error-tolerant parsing means files with syntax errors still
  yield partial extractions (good for ingesting real repos mid-edit).
- We accept tracking upstream py-tree-sitter API changes (its Language/Parser
  API has shifted between releases; pinned via uv.lock).
- **Note (2026-08-10):** `tree-sitter` is pinned `<0.26` in pyproject — the
  0.26.0 core segfaulted mid-walk on files a few hundred lines long
  (reproduced on this repo's own sources; identical code and grammar are
  clean on 0.25.x). Revisit the pin when a fixed release appears.
