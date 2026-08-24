# ADR-062 — The planner's handoff is projected onto each unit; a unit's interior is never cut

**Date:** 2026-08-22
**Status:** accepted — built; the decided-but-unbuilt fix from
`docs/phase4-to-45set-handoff.md` *(a per-phase handoff since deleted;
history in the BUILDLOG)*, landed before the 45-set spends compute.
**Amends:** `docs/constraints.md` (C-45: the interior joins the protected
sections); `docs/hobbes-architecture.md` (§6, staged execution).

## Context

ADR-061 recorded the phase-4 drift and stopped its *damage*: out-of-scope
edits are dropped at the cut. It also named the cause it did not fix. On
astropy-13579 four implementers with unrelated interiors all created
`astropy/wcs/wcsapi.py` while the unit that owned the gold file changed
nothing, because:

1. `_planner_note` built **one** handoff — the planner's whole file list
   and approach — and posted it **identically to every unit's inbox**.
   Short memory was global, not a role's. The loudest signal in every
   brief was "the change is in these files", and a unit whose interior
   held none of them aimed at them anyway.
2. The brief limit (C-45) cut the **Interior** section like any other —
   U1 lost 21,281 characters of its own paths — so the one list a unit
   must keep was the first to shrink while the global handoff stayed
   whole.

With ADR-061 alone that instance would produce an **empty** patch: the
harness cannot show its value until units aim at their own files. The
owner's standing instruction: do not attribute the drift to the model
until this is fixed — "that's how we lock a door accidentally."

## Decision

**Short-term context is projected onto the role that receives it.**

- The plan stage keeps `terms` — each planner-named file/symbol → the
  module it resolved to (`term_modules`, the same tolerant lookup the
  seeds use). `planner_slice(plan, context)` splits the named terms into
  *in this unit's interior* (resolved to an interior module, or a path
  suffix match against an interior file — so a file the planner named
  that the graph could not resolve still lands with its owner) and
  *owned elsewhere*.
- `_planner_note(seed_source, stage_log, context)` writes **one note per
  unit**: "your slice of the change — the planner named these IN YOUR
  INTERIOR: …", the approach, and "the planner also named N location(s)
  owned by other units: not yours — edits outside your interior are
  dropped at integration." When nothing intersects it **says so
  plainly**: nothing the planner named lies in your interior; you are in
  the plan because the graph reaches you from the change; change a file
  only if a contract at your boundary requires it, otherwise hand off
  that no change was needed.
- `## Interior` joins `PROTECTED_SECTIONS`: the brief limit never cuts
  a unit's own paths. The cut falls on guarding tests, module docs and
  the neighborhood — everything the knowledge tools re-serve.

The projection is deterministic over the parsed handoff and the unit's
manifest; no model is consulted. The whole-handoff shape is kept only
for a call with no unit context (none in the tree).

## Consequences

- A unit can no longer be led to a file it does not own by its inbox;
  combined with ADR-061 the two failure shapes of phase 4 (convergence
  on an unowned file, the owner idle) both have a mechanism against
  them. Whether U10 on 13579 now edits `sliced_wcs.py` is the next
  measurement, not a claim of this ADR.
- A limit below the protected size — now including the interior — is
  not met; a capped unit (C-44) with a very large interior hands the
  model a brief whose size is "as small as honesty allows". The run
  banner and `brief_cut` show it. This is the C-45 trade stated the
  other way round: the interior is what the unit is *for*.
- "Nothing named lies in your interior" is itself a model opinion
  projected (C-47): a planner that missed the real file tells its owner
  unit it has nothing to do. The lexical fallback and the verifier stay
  the checks on that; the note nudges toward a no-change handoff, it
  does not forbid edits.
- Tests: `test_planner_note_projects_onto_the_unit`,
  `test_the_planner_handoff_is_projected_per_unit` (the staged stand-in:
  exactly one unit is told the file is its slice, every other unit is
  told plainly it has none), `test_limit_never_cuts_the_interior`.
