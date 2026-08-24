# ADR-044 — Coverage claims are scoped to evidence; the guaranteed fraction is the product

**Status:** accepted (2026-08-16)

**Scope:** amends the architecture in four places, all in this commit —
§1 (adds **P11**), "Where this is going" (the guaranteed-fraction
statement), §3.7 (the checklist gains a mandatory fourth step), and a
new **§3.8** (the coverage-evidence table). Registers **C-31**
(unsurfaced, candidate surfacing named). No code changes.

## Context

Both halves are Max's directive of 2026-08-16, and they are one honesty
argument, not two:

1. **The coverage half.** With v2 complete, the shorthand hardened into
   "Languages supported: Python, TypeScript/JavaScript, Go, Rust" — five
   names presented as peers. Their evidence is not peer-shaped: Python
   and TS/JS were verified across multiple repos of different shapes;
   Go's entire base is one repo (this one — a shape its own builders
   chose); Rust's is one small repo, 33 hand-checked call edges.
   Asserting that Hobbes can fully cover Rust off that sample is — his
   word — a disgusting claim: the machinery is proven (P7, zero builder
   lines), the *language* is not, and a shared code path is exactly what
   lets a thin sample look like broad coverage. The claim outran the
   evidence, and nothing in the docs made that visible.

2. **The product half.** The honest scoping looks like a retreat — "we
   only guarantee this much" — unless the architecture states why a
   small guaranteed fraction is the point. A model handed a repo raw has
   a **0% guarantee** of assembling accurate systematic context; it
   often does well, and nothing bounds when it does not. Hobbes's job is
   insurance: convert some fraction of the codespace from *left to model
   interpretation* into *derived, checked, citable* — and the integrity
   of that fraction outranks its size. If the fraction is 20%, then that
   20% is properly and effectively captured. The complement is not
   failure, it is a finding: what Hobbes cannot reliably capture is
   thereby identified as the unique, dynamic, or needs-care part of the
   repo. And the sandbox makes the same move on the action side — a
   forbidden command is absent, not refused — so the guarantee has both
   a knowledge half and an enforcement half.

Half two is what makes half one affordable: a system whose product is
the guaranteed fraction can state a thin sample plainly, because
shrinking a claim to its evidence *improves* the product instead of
embarrassing it.

## Decision

- **P11 (new): a coverage claim is scoped to its evidence.** "Supported"
  means the machinery ran end-to-end on the repos in §3.8 and the stated
  checks passed there — nothing more. A statement of support names its
  sample; a language absent from §3.8 is *wired*, not *supported*.
- **§3.8 is the sample.** One table, per language: repos, scale,
  hand-checks. It states the asymmetry in prose rather than letting rows
  read as peers, and it distinguishes what generalises without
  per-language evidence (the honesty machinery — the shared code path,
  exercised every test run) from what never does (accuracy on repos
  shaped unlike the sample).
- **§3.7 step 4 (mandatory):** adding a language ends by extending §3.8
  in the same commit as the verification evidence. The same-commit rule
  is ADR-033's, applied to claims.
- **The guaranteed-fraction statement** lands in "Where this is going",
  because it is what the agentic direction (per-task derivation, not yet
  built) will be measured against: derived context must come from the
  captured fraction, and what falls outside it must be *pointed at*, not
  silently filled in by the model the derivation exists to constrain.
- **C-31 registers the residue, unsurfaced.** The runtime mechanisms
  surface detectable degradation; a blind spot the sample never
  exercised warns nowhere, and nothing at ingest states verification
  depth. Filed as debt knowingly — §3.8 is a document, and the
  register's own rule says a document is not a surfacing. Candidate
  surfacing: verification depth beside the language list, at ingest and
  in the surface.

## Consequences

- README, CLAUDE.md, and any future surface copy inherit P11: language
  lists carry their evidence scoping or point at §3.8. (README already
  carries the C-29 warning in user terms; its language claims are next
  to be re-read against §3.8 — noted in the BUILDLOG rather than done
  silently here.)
- The standing candidate work ("the derivation itself") gains its
  yardstick before it gains a milestone: derived context is drawn from
  the guaranteed fraction, and the fraction's boundary is P8's register.
  Nothing in this ADR starts that work.
- Cost: every future language lands slower — step 4 is real per-repo
  verification work, and it cannot be batched away. Accepted; that is
  the price of the word "supported" meaning something.
