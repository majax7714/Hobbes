# ADR-084 — The planner decomposes the request into requirements; coverage is its guarantee; the weight belongs to it

**Date:** 2026-08-23 · **Status:** accepted as design frame (build gated on
Max — flow change) · **Supersedes:** the shallow fix floated in BUILDLOG
seventy-sixth ("keep the full proposal primary in every brief"). Relates to
P12 (ADR-082), ADR-083 (grain), C-49, C-52, C-55.

## Context

sympy-13852: the issue states two requirements — add the value evaluation
`polylog(2, 1/2) = -log(2)**2/2 + pi**2/12` (first line, verbatim) and
remove the `exp_polar` term. The 27B read the issue and did both; the 7B
did only the exp_polar half and failed. The planner's handoff carried only
"remove unnecessary exp_polar terms." First read: the planner *dropped a
detail*, so keep the full proposal in front of the implementer. Max
rejected that, correctly:

- Handing every implementer the full task **reintroduces the whole task in
  one context** — the exact thing P12 exists to prevent — and makes the
  implementer re-parse the request, which is the planner's job.
- The defect is not that the planner dropped a detail from a box. **It is
  that the planner never registered the requirement as a box needing an
  owner.** Today the planner does *localization* (request → files/symbols);
  it does not do *requirement decomposition* (request → the set of things
  that must become true → an owning unit for each). A requirement with no
  owning unit cannot be implemented by any diligence downstream.

The resource picture is the same defect from the other side. The planner
is **4–12% of the harness's token weight**; the implementers are **88–96%**
(xarray 4.1%, sympy 3.8%, django 6.0%, sphinx 5.8%, sklearn 12.5%). The
single role that absorbs the whole request and does the hard comprehension
is the *lightest* in the system; the many roles that should each hold one
small assignment are the *heaviest*. The weight is inverted.

## Decision (frame)

1. **The planner is the requirement-decomposer.** Its output is not just
   *where* the change goes but *what must become true* — the request broken
   into requirements, each assigned to a unit whose handoff owns it. The
   proposal is the user request; the planner is the single role that
   absorbs it whole and breaks it up.

2. **Coverage is the planner's guarantee.** The union of the handoffs must
   cover the request: every requirement maps to some unit. A requirement
   with no owner is the defect (sympy's value-eval). Co-change (ADR-083
   lever 2) is one *mechanism* for one *kind* of coverage — files that must
   change together; requirement-decomposition is the broader capability
   that also catches "the request asks for behaviors X and Y."

3. **Each handoff is complete for its implementer.** The implementer needs
   its handoff and its interior — not the full proposal. The measurable
   test of the whole frame: **an implementer succeeds with the proposal
   removed from its brief.** Today the proposal sits in every brief as a
   safety net, and it already failed — the 7B *had* it and still missed the
   requirement, because it trusted the handoff. A net that weak models
   cannot use is not the fix; planner coverage is.

4. **The weight belongs to the planner.** It is singular and runs once, so
   it can and should be heavy: absorb the request, decompose it, guarantee
   coverage. That makes the planner heavier (right) and lets the
   implementers shed the whole-task burden and get lighter (right).
   Aligning weight with role and aligning coverage with role are the same
   move.

## Consequences

- This expands the planner from localizer to requirement-decomposer with a
  coverage guarantee — a change to the flow, so building it is **gated on
  Max's go**, not done under the inspection pause.
- A cheap, buildable-now check that does not need the expansion: diff the
  planner's approach/handoff against the proposal for dropped imperatives,
  and flag a requirement the handoffs do not mention. It measures the gap
  without yet closing it.
- The target metric shifts from "planner localises a gold file" (C-49, one
  solution) toward "the handoffs cover the request's requirements" — closer
  to what the behavior verifier (DeepSWE) actually grades.
- ADR-083 lever 2 folds under this: co-change into the interior is coverage
  of the "files that change together" kind; decide it as part of the
  requirement-coverage design, not before it.
