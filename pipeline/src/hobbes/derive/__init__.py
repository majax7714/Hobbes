"""The plan derivation — proposal to change-spec (ADR-051, D1).

This package is the mapping `docs/agent-mapping.md` designs: given a
proposed change, derive **how many agents**, **which context each one
gets**, **what policy each runs under**, and **who checks what** — as
an algorithm over artifacts Hobbes already has, never as an org chart.
An agent is a triple *(context slice, policy profile, verification
obligations)*; the number of agents is the partition's output, not a
parameter.

Deterministic end to end and quota-free: same graph + same proposal +
same flags produce a byte-identical change-spec. Everything here is
bound by the derivation contract (ADR-047) — a context manifest that
lacks its stated complement refuses to serialize.

The stages, one module each, in pipeline order:

- :mod:`hobbes.derive.impact` — proposal → scored impact set (seeds
  resolve lexically, C-36; expansion decays by tier and edge type)
- :mod:`hobbes.derive.cochange` — the co-change factor from git
  history, bounded and observational
- :mod:`hobbes.derive.partition` — impact set → work units under a
  context budget (C-35: the weights are declared guesses)
- :mod:`hobbes.derive.contracts` — cut edges → pinned contracts
  (C-37: a pin is a declaration site, not a type signature)
- :mod:`hobbes.derive.manifests` — per-unit context and policy
  manifests, the complement always attached
- :mod:`hobbes.derive.changespec` — assembly, the plan-review gate,
  serialization to ``.hobbes/plans/<task-id>/change-spec.yaml``
"""

from hobbes.derive.changespec import (  # noqa: F401
    DeriveError,
    derive_plan,
    format_spec,
    spec_to_dict,
    write_spec,
)
