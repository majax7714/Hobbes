# ADR-083 — Change-grain unit interiors: a non-seed hub is context, not work

**Date:** 2026-08-23 · **Status:** accepted (lever 1); lever 2
(co-change-into-interior) **deferred by Max, 2026-08-24** — decided from
the 7B validation run's strict-coverage records (an unnamed co-change
file now surfaces as an uncovered requirement's missing owner, ADR-085),
not before · **Realises:**
P12 (ADR-082) condition (c). Builds on the render caps (ADR- none; the
`render_context` bounds committed 2026-08-23).

## Context

The P12 inspection found that a spawned unit's window was large because its
**interior** held hubs and package roots: django U4's interior contained
`django.contrib.admin` (200+ importers), which put the repo on the unit's
boundary (276 contracts), neighborhood (one hop from the hub is everything),
and guards (every test that reaches the hub). The interior came from the
agglomerative partition merging modules *coupled* to the planner's seed,
regardless of whether they are where the change goes.

Two distinctions the derivation was not making:

- **Generic import-coupling** to a hub (`filters.py` imports
  `contrib.admin`) means the hub is *context* — the agent reads its
  signatures, it does not edit it.
- **Specific implication** in the change (the planner named it; or git
  history shows it changes *with* the seed) means it is *work* — interior.

## Decision — lever 1 (accepted): a non-seed hub/root is not a unit interior

`partition.unit_modules` drops a module from the partitionable set when it
is **not a seed** (planner score < 1.0) and is either a **package root**
(`__init__`/dotless id) or a **hub** (fan-in ≥ `HUB_FANIN` = 30 modules).
A seed is always work. Dropped modules still reach the agent as
neighborhood and (where they cross a boundary) contracts, bounded by the
render caps. `module_fanin` counts distinct importers from the module
adjacency. `HUB_FANIN` is a declared guess (C-35), overridable.

**Measured (re-deriving the five 27B specs from their stored planner seeds,
`scratchpad/rederive.py`, no model):** rendered context per instance —
django 100k→44k, xarray 118k→47k, sklearn 153k→18k, sphinx 146k→67k, sympy
117k→14k; **largest single unit 20k→13k chars**; **gold-file coverage
unchanged** (it is set by the seeds, which this does not touch: sphinx 2/2,
sympy 1/1, django 1/3, xarray 1/2, sklearn 0/2). Spawned-unit counts stay
sane (1–3). So lever 1 shrinks the window with no accuracy cost — a pure
P12-(c) win.

## Decision — lever 2 (proposed, needs Max's call): pull the seed's git co-change set into its interior

django's fix spans three co-changing files; the planner named one
(`filters.py`), so 2/3 gold is outside any spawned unit's interior (the
ADR-077 fragmentation, unfixed). Git history shows `filters.py`
co-changes with `db/models/fields/__init__.py` (rank 3, 21 of 59 commits)
— **one of the two missing gold files**. So adding the seed's strong
git-co-change set to its interior (overriding the hub exclusion for a
module *specifically* implicated) would recover it, keeping the co-change
set together — change-grain done right, the ADR-077 lesson.

This is held for Max because it **restructures unit interiors on git
history and moves the gold-coverage metric** — the accuracy axis, not just
window size. It needs: a co-change threshold, a cap so a promiscuous file
does not pull the repo, and the interaction with lever 1's hub rule
(co-change wins: specific beats generic). Evidence that it helps is above;
the call is whether to change what an implementer *owns* on history.

## Consequences

- Lever 1 ships; the grain is change-grain for interior *composition* but
  still planner-*seed*-grain for *coverage* until lever 2.
- Tier-1 flow validation (a 7B decomposed run) can use an instance already
  fully covered by seeds (sympy 1/1, sphinx 2/2), so it does not depend on
  lever 2.
- `HUB_FANIN` and the render caps are the tunable surface; none is
  validated beyond these five specs (C-35).
