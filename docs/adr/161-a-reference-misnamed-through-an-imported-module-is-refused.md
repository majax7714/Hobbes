# ADR-161 — A Python reference lane B names with another symbol's name through an imported module is refused

**Date:** 2026-10-02 · **Status:** accepted (Max, 2026-10-02: "good to proceed with recommended investigate and
contain for c-178"); to be built · **Owner:** Max · **Source:** C-178's step 0,
`~/.hobbes/bench/c178-star-reexport/` (`RESULTS.md`, `PREREG.md`, `mismatch2.py`, the fixtures `v1`–`v6`, `fx`).

Contains **C-178**. Draws less: it removes wrong `semantic` rows and adds none.

## What is wrong

The held-out pyparsing cell found `pp.Word`, `pp.Forward`, `pp.alphas` … named by scip-python 0.6.6 as
`pyparsing.core/CaselessLiteral#`, and the join drew them as `semantic` `uses` rows: 1,688 evidence rows on
404 edges to `CaselessLiteral`, where 36 source lines name it, and more to `one_of` and `replace_with`. A trace
key grades calls only, so nothing graded saw it.

## Measured (step 0, no code changed)

- **The mechanism, in ten lines in the image:** where a package's `__init__.py` re-exports by `from .core
  import *` (with or without `__all__`), the first `<pkg>.<name>` scip-python resolves through the re-export
  answers every later one, across files. Explicit re-imports resolve right.
- **Its reach**, over raw indexes, comparing the token at each reference (UTF-16 columns, as scip-python
  writes them) with the named symbol's last name, and reading the receiver: pyparsing 2,940 references through
  an imported module named as another symbol, 2,919 of them to a repo symbol; rich 21, flask 44, click 136,
  this repo 96, every one to the stdlib's own star re-exports (`os.path`, `collections.abc`, `stat`, `ast`),
  outside the repo.
- **What must not be refused:** a mismatch through a *value* receiver is the index naming the receiver's
  class at an instance attribute it has no symbol for (`self._link` → `Style#`; rich 122), which the graph
  draws as a true `uses` of the class. An import alias (`import numpy as np` … `np.array` named `array`) has
  no mismatch at all: the token is the attribute.
- The join's line-and-name claim already keeps the poisoning out of `calls`: pyparsing's 7 `calls` edges to
  `CaselessLiteral` are genuine `CaselessLiteral(…)` calls.

## The decision

1. **Where.** In the ingest, where lane B ran for Python, after lane B's facts are gathered and before the
   join — beside ADR-154's step — over the resolution sites that are **references** in Python files (never an
   `implements` site, never another language's).
2. **The test.** A reference is refused when both hold:
   - its token — the identifier at its line and column in the file, the column read as scip-python writes it,
     in UTF-16 code units — is not its `name`;
   - the token is the member of a dotted chain `root(.x)*.token`, and `root` is a name the file binds by a
     plain `import` statement (`import a.b` binds `a`; `import a.b as c` binds `c`).

   Both are read from syntax: the file's text and lane A's `PlainImport` facts. A module attribute that is
   what it says always names a symbol with the token's name, so the test refuses only an answer that names
   something else through a module.
3. **Refused** means the reference reaches neither the join nor any edge, row or count that reads
   resolutions. The site keeps whatever disposition it had without it.
4. **Said where a user meets it.** One degradation record per ingest with any refusal, stage `scip-python`,
   naming the count, the cause in one sentence (scip-python's reading of a `from … import *` re-export, C-178)
   and up to three examples `path:line` `token` named `name`. `list_blind_spots` prints it as it prints every
   degradation record.
5. **Without lane B** there is nothing to refuse and nothing is recorded (P6).

## Not taken

- **Refusing every mismatch:** it would drop rich's 122 value-receiver `uses` of a class, which are true.
- **Repairing the answer** (looking the token up in the re-exporting module): a guess at what the index meant;
  the graph would draw an edge no provider named. Lane A's own resolution of `pkg.Name` through a star import
  is a separate question, not this ADR's.
- **External references** (the stdlib cases) keep their misnamed monikers: they draw no repo edge, and only
  their package is read.

## What it costs

A pass over Python reference sites with their files' text, once per ingest. On pyparsing about 2,900 rows
leave the join; elsewhere none is expected.

## What this leaves

C-178 narrows to: a module attribute read through a star re-export has no lane B answer, refused and counted
(surfaced). The call written there stays unresolved; recall does not move.
