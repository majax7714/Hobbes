# ADR-043 — The register separates active from lifted, and documents the lift itself

**Status:** accepted (2026-08-16)

**Scope:** the format of `docs/constraints.md`. Amends **ADR-030** (the
register's shape, not its rule — P8 is unchanged). No code changes; no
constraint is added, lifted, or renumbered by this ADR.

## Context

The register grew to thirty entries with six lifted, and the lifted ones
sat inline among the active ones, distinguishable only by a suffix on
the heading. Two costs, both raised by Max on 2026-08-16:

1. **Flow.** A reader scanning for what Hobbes cannot tell them *today*
   had to filter out what it used to not tell them, entry by entry.
2. **The lift itself is under-documented as a category.** A lift is a
   technique, and a technique has a boundary: an input the technique
   does not classify falls back to being conceded — silently, because
   the entry reads as closed. C-11's lift left C-24; C-24's lift left
   the four JSX outliers; C-16's manifest walk still reads
   `pyproject.toml` only. The residue was *sometimes* recorded ("honest
   residue"), but nothing in the format required it, so whether a lift's
   edge cases were written down depended on the session that wrote it.

The second is the real one. "How it is lifted might allow for an edge
case to not classify" — so the lifting technique is register material
exactly like the concession was, and a lifted entry that records only
the celebration is the fake-honest shape P8 exists to prevent, one
level up.

## Decision

`docs/constraints.md` has two parts:

- **Active constraints** — limits that hold today, grouped by the
  subsystem where a user meets them. Entry format unchanged (ADR-030).
- **Lifted constraints** — limits that no longer hold, each with a
  **required** four-field format:

  | field | means |
  |---|---|
  | **Was** | the limit as it stood, and why it was conceded then |
  | **Lifted by — the technique** | the exact mechanism of the lift |
  | **Residual edge cases** | inputs the technique does not classify — where the old concession quietly survives |
  | **Source** | ADR/session for the concession and for the lift |

Rules that carry over unchanged, restated because the move could be
misread as breaking them:

- **Numbers are stable.** A lifted entry keeps its `C-n` and moves;
  nothing is renumbered or deleted, ever.
- **Residue that bites becomes an active entry**, cross-referenced both
  ways. C-11 → C-24 is the worked chain, and it ran twice.
- The register is written for **anyone who runs Hobbes**; named
  individuals appear only as the source of decisions.

Applied in the same commit: all six lifted entries (C-3, C-11, C-14,
C-16, C-18, C-24) restated in the four-field format. Two of them gained
residual-edge-case documentation the old format never asked for, both
verified against the tree rather than remembered: C-3's TS
normalisation is bounded by the **running Node's** `builtinModules`
(not a pin — a newer runtime's builtin classifies as a third-party
package on an older box), and C-16's manifest walk is bounded by the
manifest **format** — a `setup.py`/`requirements.txt`-only repo still
presents an empty declared list, with the same appears-to-run failure
shape the lift fixed for subdirectory manifests.

## Consequences

- A lift is no longer "done" when the mechanism lands; it is done when
  its boundary is written down. That is P8's definition-of-done applied
  to the register's own good news.
- The residual-edge-case field gives future audits a concrete question
  per lifted entry: *is the residue still just residue?* The 2026-08-15
  audit showed entries drift when milestones never touch them; lifted
  entries drift the same way, and now they have a field to check.
- Cost: the register is longer and the debt summary counts two parts.
  Accepted — flow for the active part was the point.
