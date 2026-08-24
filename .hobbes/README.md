# .hobbes/ — Hobbes dogfooding itself

Layout per architecture §10, split by reproducibility:

- `policies/` — versioned. Hand-reviewed policy source of truth for this repo
  (`repo.policy`; folder policies live next to the folders they govern as
  `<folder>/.hobbes/folder.policy`).
- `invariants/` — versioned. Confirmed invariants (one YAML record each, schema
  in architecture §10). Empty until the narrative pass (M5) starts inferring
  them and we confirm some.
- `derived/` — **gitignored**. Deterministic pipeline outputs (`graph.json`,
  `tests.json`, `interfaces.json`, generated docs). Regenerable from the repo
  at a pinned SHA; committing them would add merge noise without adding truth.
