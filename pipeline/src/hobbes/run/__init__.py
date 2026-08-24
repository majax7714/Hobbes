"""The execution half of the derivation — D2 base (ADR-054).

D1 (:mod:`hobbes.derive`) maps a proposal onto a change-spec: units,
contracts, per-unit context and policy manifests. This package runs
one. ``hobbes run <task>`` is the **orchestrator** agent-mapping §3.4
describes — a scheduler and contract arbiter that owns no code: it
materializes each unit's agent, sequences the units by contract
ownership, spawns one single-use sandboxed session per unit, harvests
the commits, integrates, reviews, and writes the **partition record**
the loss function (§6, C-35) will be fitted against.

The agent's shape, per the owner's direction (2026-08-21):

- **Policy is layered, per agent**: the repo policy (shared), a
  standing **role** policy (``.hobbes/policies/roles/<role>.policy``,
  versioned, changed only by commits), and the derived **agent**
  policy written from the change-spec's policy manifest — the most
  specific layer, which can narrow and never widen (deny overrides).
- **Context has two horizons**: the **standing** context is the
  unit's manifest rendered from the ingested artifacts plus
  ``derived/`` mounted read-only — it changes only when a commit
  changes the graph; the **short-term** context is the agent's inbox
  (:mod:`hobbes.run.mail`): messages the orchestrator pushes, and the
  agent's reflections back through the proxy's ``reflect`` tool. When
  the orchestrator needs a specific, it posts to that agent's inbox
  and reads the reflection; nothing is a chat transcript.
- **Commits alter standing context.** A session's branch is harvested
  into the repo; integration merges the unit branches; the review
  runs; re-ingesting the merged result is what moves every agent's
  standing context, and the run says so rather than doing it behind
  the human's back.

The rest of the D1 mapping is unchanged. Everything here is quota-free
to exercise: ``--dry-run`` materializes agents, briefs, and the record
without spawning, and the test suite drives it with a stand-in session
binary. What the base deliberately leaves out is in ADR-054 and the
register (C-38).
"""

from hobbes.run.orchestrate import RunError, run_task  # noqa: F401
from hobbes.run.spec import SpecError, list_plans, load_spec  # noqa: F401
