# pipeline/ — Python package `hobbes`

The `hobbes` CLI and the deterministic extraction pipeline (M1); the
invariant compiler joins at M8. uv-managed, src layout (ADR-004). Runtime
dependencies: `tree-sitter` + `tree-sitter-python` only (ADR-005).

Surface:

- `hobbes ingest [--repo PATH] [--tf-plan FILE]` — runs the extractors and
  writes the three SHA-stamped artifacts (ADR-006, schema v2) to
  `.hobbes/derived/`: `graph.json` (app modules + symbol layer + Terraform
  infra layer in one graph — `imports`/`env-read`/`calls` plus
  `references`/`env-set`/`packages` per ADR-010), `tests.json` (pytest
  inventory with static reach), and `interfaces.json` (FastAPI/Flask
  routes, CLI entry points). `--tf-plan` enriches the infra layer from a
  `terraform show -json` file; anything that looks like state is refused.
- `hobbes init [--repo PATH]` — scaffolds `.hobbes/` (policies/, invariants/,
  starter repo.policy, gitignore entries). Idempotent.
- `hobbes render` — prints the ingested module graph as a Mermaid
  `flowchart LR` (ADR-008): internal modules clustered by package, external
  deps and env vars shape-styled, edges styled by type.
- `hobbes diff <base>..<head> [--json]` — the architecture delta between
  two refs (ADR-009): extracts both trees via `git archive` (checkout never
  touched) and prints typed added/removed nodes and edges with evidence.
  Exit codes mirror diff(1): 0 no differences, 1 differences, 2 trouble.
- `hobbes policy resolve "<command>"` — passthrough to the Go `hobbes-policy`
  binary: prints its JSON resolution, propagates its decision-coded exit
  (0 allow / 10 deny / 20 escalate, ADR-003). Found via
  `$HOBBES_POLICY_BIN`, else `$PATH`.

Layout: `src/hobbes/cli.py` (argparse front-end), `src/hobbes/policy.py`
(policy shell-out), `src/hobbes/extract/` (discover → pysource → graph /
interfaces / testmap → emit; resolution rules in ADR-007),
`src/hobbes/render.py` (Mermaid export), `src/hobbes/graphdiff.py` (delta
engine + ref extraction).

```sh
uv sync         # venv + dev deps
uv run pytest   # hermetic: fixture repo under tests/fixtures/miniapp
uv run hobbes ingest --repo /path/to/repo
```
