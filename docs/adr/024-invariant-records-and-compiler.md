# ADR 024: Invariant records and the compiler contract

Date: 2026-08-11
Status: accepted

## Context

Architecture §10 fixes the invariant record's *fields* — `id`,
`statement`, `scope`, `status`, `compile: {target, rule}`, `guarded_by`
— and names the compile targets: import-linter + semgrep for Python,
dependency-cruiser + semgrep for TS/JS, Rego/Conftest against
`terraform plan -json` for infra, and `soft` for anything a machine
cannot check. Build plan M8 turns those records into CI configs and
into review verdicts.

Two things §10 leaves open, and both decide whether the compiler can
exist at all:

1. **What `compile.rule` is.** §10's example writes it as prose —
   `forbidden — anything except auth.core imports auth.token`. A
   compiler cannot emit an import-linter contract from a sentence
   without an LLM, which would put quota on the enforcement path and
   make CI output non-deterministic. Sequencing rule 1 is
   "deterministic before generative".
2. **Where records live and which ones count.** §10 says
   `invariants/` is versioned and hand-reviewed, and ADR-019 says
   inferred records never write there — but not what a `retired` record
   does, nor what happens to a half-promoted one.

## Decision

**One record per file**, `.hobbes/invariants/<id>-<slug>.yaml`, ids
`I-<n>`. A directory of small files reviews cleanly in a diff and makes
adding one a new file rather than an edit to a shared list.

**`statement` is the prose; `compile.rule` is structured.** The
sentence a human reads and the spec a compiler consumes are different
artifacts, and §10's single prose field was a sketch of the record, not
a contract for the compiler. Every rule carries a `kind`, and v0 has
exactly three structured kinds plus `soft` — one per shape an actual
record needed, no more:

- **`forbidden-import`** — `importers` (ids or `"*"`), `except`,
  `imported`. Compiles to an import-linter `forbidden` contract
  (Python) or a dependency-cruiser `forbidden` rule (TS/JS), and is the
  one kind `hobbes review` can also answer straight from the module
  graph.
- **`pattern-absent`** — `languages`, `paths`, `exclude`, `patterns`.
  Compiles to a semgrep rule whose match is the violation.
- **`resource-attribute`** — `resource_type`, `require` / `forbid`.
  Compiles to Rego evaluated against `terraform plan -json`.
- **`soft`** — no rule. Not mechanically checkable; the reviewer
  session evaluates it and must cite evidence (§10).

Layered-architecture contracts (import-linter's `layers`) are
deliberately absent: no record needed one, and building the emitter
before a record wants it is the speculative abstraction the conventions
forbid.

**Status governs participation, not presence.** Only `confirmed`
records compile and receive verdicts. `retired` records stay in the
directory as history — deleting them loses the record that a rule was
once deliberate — and are inert. A record with `status: inferred` in
the versioned directory is a promotion someone stopped halfway: it
loads, warns, and stays inert rather than failing the run, because a
half-finished promotion should be visible, not fatal.

**Compilation never requires the target's toolchain.** Emitting an
import-linter `.ini` is text generation; running it is CI's job. The
compiler writes to `.hobbes/derived/compiled/` (derived, gitignored,
regenerable — ADR-006's rule) and works on a machine with none of the
four tools installed, which is the machine this was built on.

**Scope is a path prefix**, matched against a node's `path` — not a
module id, because a record must be able to cover a directory whose
modules are not a package, and because the same field has to mean
something in a Python, TS, and Terraform repo.

Validation is strict and happens before anything compiles: unknown
fields, unknown `kind`, a `soft` record carrying a rule, a structured
record missing one, duplicate ids, or a `guarded_by` naming a test that
is not in `tests.json` are all errors. A record that does not mean
exactly one thing is worse than no record.

## Alternatives considered

- **Prose `rule` compiled by an LLM** — puts subscription quota on the
  enforcement path, makes CI config non-reproducible, and breaks
  sequencing rule 1. The prose survives as `statement`, which is what
  humans actually read.
- **One `invariants.yaml` list** — smaller directory, but every
  addition is a merge conflict and a review diff that moves unrelated
  records.
- **Deleting retired records** — loses the history of a rule that was
  once deliberate. `retired` is a tombstone with provenance.
- **Compiling by shelling out to the tools** — would make `hobbes
  invariants compile` unusable anywhere the tools aren't installed,
  including this dev box, and confuses generating a config with running
  one.
- **`scope` as a module id** — cannot express "this directory" in a
  Terraform or multi-language repo.

## Consequences

- The record is readable by a human (`statement`) and executable by a
  machine (`compile.rule`) without either being a lossy rendering of the
  other.
- Compiled output is a derived artifact: CI regenerates it per PR and
  never diffs it, exactly as with `graph.json`.
- Adding a compile target is one emitter plus its tests; adding a rule
  *kind* is a schema change and an ADR amendment, which is the right
  friction ratio.
- Because `forbidden-import` is graph-answerable, the same record backs
  a CI contract and an in-process review verdict without the two
  disagreeing — they read one spec (ADR-025).
