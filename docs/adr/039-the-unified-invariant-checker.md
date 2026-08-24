# ADR-039 — The unified invariant checker (V2.M6)

**Date:** 2026-08-15 · **Status:** accepted · **Amends:** ADR-024 (record
shape), ADR-025 (verdicts), architecture §5 (in the same commit as the
code, per ADR-033)

## Context

ADR-024's records carried `compile.target` with `soft` as a pseudo-target,
and ADR-025's verdict engine judged forbidden-import rules from the graph
as a side effect of reviewing. V2.M6 makes the checker the first-class
path (architecture §5): one checker, every language, tier-aware — with CI
emission retained as the compatibility escape hatch and reviewer sessions
for what no machine can check.

## Decisions

**1. `check: graph | emit | soft` is the record's spine.** The rule block
moves to the top level (it describes the invariant, not the compilation);
`compile` shrinks to `{target}` and exists only for `check: emit`;
`soft` is a checking mode, not a target. Validation enforces the whole
combination — a soft record with a rule, or a graph record with a compile
block, is refused with the reason. A v1 record fails with a message that
names the migration.

**2. A `check: graph` record must be answerable.** `pattern-absent` and
`resource-attribute` live in the AST and the Terraform plan, which the
graph does not carry; a graph record with those kinds would sit at
`unknown` forever — a check that cannot check — so validation refuses it
up front and points at `check: emit`.

**3. The checker judges every rule it can see, emit records included.**
The M6 exit is agreement: wherever a rule has both an in-process verdict
and an emitted tool, the two must say the same thing. That only means
something if the checker never abstains on emit records.

**4. Verdicts are tier-aware, with a lane-A-only carve-out.** A violation
on a `semantic` edge is proven; on a `syntactic` edge it is a suspicion —
verdict `suspect`, sorted between `fail` and `unknown`, still exit 1 —
**except** where the edge's target is one only lane A can produce
(`ext:`/`env:`/`tf:`, §3.1). There, syntactic is not a downgrade but the
only tier that exists: an `import tree_sitter` statement lane A read is a
fact, and calling it a suspicion would understate a real violation.
Review folds `suspect` into the red family: pass→suspect regresses,
fail↔suspect is still-failing.

**5. The first real tool execution, and the first bug it found.** M8
verified emitters by shape because no target toolchain was installed
(C-19). import-linter is now a dev dependency and the agreement suite
runs `lint-imports` over generated configs — which immediately failed a
clean repo: the `except` cross-product emits ignore pairs that never
occur as imports, and import-linter errors on unmatched ignores by
default. The emitter now sets `unmatched_ignore_imports_alerting = warn`.
Exactly the class of bug a shape assertion cannot see, found on first
execution, as the plan predicted. C-19 narrows to the three tools still
unexecuted (dep-cruiser, semgrep, conftest).

**6. Soft verdicts are source-based (C-18 lifted).** `--soft` runs each
in-scope soft invariant through the M4 reviewer sandbox — worktree
mounted read-only at the review's head ref (`hobbes-session --ref`, new),
knowledge tools available, the range's diff hunks in the prompt (bounded
at 400 lines). A missing sandbox is an error recorded on the answer,
never a silent fallback to the delta-based prompt, which would quietly
recreate C-18.

**7. I-4 restated a third time, and the checker now guards its roster.**
The enumerating wording went stale twice without the record noticing
(HCL behind the pack at V2.M4, gosource's grammar at V2.M5 — the old
rule *fails* on today's graph, citing `gosource.py:39`). The statement
now states the ownership rule; the enumeration lives only in the rule
block, which the checker holds against the graph on every review, so a
fifth language that forgets to amend the record turns it red instead of
quietly narrowing it.

## P10's parked ask stays parked

"Does a broad handler enclose a path that must refuse?" remains in
`future_additions.md`. The checker's rule kinds exist because records
needed them, and no record can want a refusal-domination rule yet:
refusals are a type in one subsystem (`PackRefusal`) and a message in the
others. The two steps stand — type the guarantees first, then give the
checker a kind that asks the graph about them — and the first belongs to
the subsystems, not to this milestone.

## Consequences

- Eleven records migrated; the Go surface writes the new shape on
  approval, and `list_invariants` renders the checking mode.
- The decision-key hash (statement, scope) is untouched — approvals and
  denials survive the migration.
- Other repos are unaffected: ADR-012 keeps `.hobbes/` per-clone, and no
  repo but this one has records.
