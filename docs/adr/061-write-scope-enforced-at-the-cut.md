# ADR-061 — A unit's write scope is enforced at integration, not measured as rework

**Date:** 2026-08-22
**Status:** accepted — built; the phase-4 full-stage run is the evidence
C-38 said enforcement needed.
**Amends:** `docs/constraints/README.md` (C-38 flips from measured to enforced);
`docs/hobbes-architecture.md` (§6.1 integration).

## Context

C-38 (ADR-054) made a unit's write scope **advisory**: the orchestrator
diffed each harvested branch against the unit's manifest and recorded
out-of-scope files as *rework*, but the whole branch was merged, so
those files landed in the candidate patch. The stated reason to observe
rather than enforce was explicit: "enforcing it before a run has shown
where agents actually stray would be tuning a guess."

The phase-4 full-stage run (astropy-13579, 7B) showed the stray, and it
was not a model quirk — it was structural:

- Four implementers whose interiors were unrelated (`utils/misc.py`,
  `io/fits/header.py`, `wcs/wcs.py`, `wcsaxes/…`) **all created the same
  file** `astropy/wcs/wcsapi.py` — a file **none of them owned** and not
  the gold `wcsapi/wrappers/sliced_wcs.py`. They converged there because
  the planner's handoff (posted identically to every inbox) named it.
- The unit that **did** own the gold file (`sliced_wcs.py` in its
  interior) changed nothing.
- A `session_commit.txt` scratch note a model wrote at repo root was
  swept into the patch by commit-on-exit.
- On astropy-13398 two units both edited the gold file `itrs.py`; the
  second wrote the literal placeholder `"<updated content>"`, clobbering
  the first's real attempt (last write wins in a whole-branch merge).

Whole-branch merge turns every out-of-scope edit into patch content and
lets units clobber each other. The partition makes interiors disjoint,
so a file belongs to at most one unit — the information needed to scope
was already there; only the merge ignored it.

## Decision

`_integrate_one` takes a unit's `allowed` paths (its interior module
paths + guarding-test files) and integrates **only the part of the
unit's diff that touches those paths**: `git diff target..branch --
<allowed>` applied onto the target (the diff's exact base, so it applies
without a 3-way merge). Files outside the scope — a neighbour's source,
a scratch note — never enter the candidate patch, and because interiors
are disjoint no two units can write the same file into the result. The
integration record gains `dropped` (out-of-scope files discarded per
unit) and `empty` (a unit whose in-scope diff was nothing).

## What this is and is not

- **Not a mount boundary.** The sandbox worktree is still whole and
  writable; an implementer *can* still write a neighbour's file inside
  its own session. That work is discarded at the cut and recorded as
  rework (C-38's residual) — the guarantee is about the *candidate
  patch*, not the session filesystem.
- **Does not fix the drift's cause.** The reason four units aimed at the
  same wrong file is that the planner's handoff is posted globally, not
  projected onto each unit's role — a separate issue (the implementer's
  short memory is not role-derived). Enforcement stops the *damage*
  (clobber, leak, wrong-file patch content); it does not make a
  mis-aimed unit edit the right file. That is the next change.
- **Byte-reproducible within a seed set.** Scoping is deterministic;
  same branches in, same scoped patch out.

## Consequences

- The candidate patch contains only files some unit owns. The astropy
  probe's `session_commit.txt` and the four stray `wcsapi.py` creations
  would now be dropped (and recorded), leaving — on that instance — an
  empty patch, which is the honest outcome when no unit edited its own
  gold file.
- `partition-record.json` / the harness `detail.run.integration` carry
  `dropped` and `empty`.
- Test: `test_run.py::TestStagedRun::test_out_of_scope_writes_are_dropped_at_integration`
  drives a stand-in that writes both an interior edit and an
  out-of-scope scratch file, and asserts only the interior edit lands.
  827 pytest / Go green.
