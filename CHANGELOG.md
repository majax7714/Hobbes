# Changelog — the Hobbes layer

One entry per version of the Hobbes layer (ADR-103): what changed in
the product, in plain words, with the ADRs and constraints it rests on.
The experiments under `bench/` and the records under `docs/` are
internal testing and do not appear here except where a finding became
a fix. The session-by-session history is `docs/BUILDLOG.md`; the
running architecture is `docs/hobbes-architecture.md`.

## 0.1.3 — 2026-09-09

The first stated version, so this entry says what 0.1.3 *is* rather
than what changed.

**The knowledge layer** — a complete deployment on its own (ADR-092
phase 4): `hobbes ingest` builds `.hobbes/derived/` from a repo on
disk with no model, and `hobbes-proxy serve --knowledge-only` serves
six read-only tools over it from the sandbox image (ADR-087/094).

- Six languages, each a tree-sitter syntax provider joined by one
  range join to a pinned SCIP indexer: Python, TypeScript/JavaScript,
  Go, Rust, Java, plus Terraform/HCL structure (architecture §3.8).
- Every edge carries a tier (`semantic` / `syntactic`) and its evidence
  line; every site nothing resolved is counted and classed, never
  drawn (ADR-045/047).
- Everything that executes repo-authored code runs in the one sandbox
  image; `--uncontained` is disclosed and stamped (ADR-092, C-64).
- The constraint register: 96 entries, 74 active, each naming where a
  user meets the limit (`docs/constraints/`).
- Compiler-graded by the oracle lane: 0 falsely confirmed of 99,824
  seeded wrong edges across 19 cells; every compiler-graded cell at
  100% precision-against-oracle except three named ones
  (`docs/comparative/`, ADR-089/101).
- Every artifact and every knowledge answer states which Hobbes
  built it: now version and commit (ADR-094, ADR-103).

**The agentic layer** — sessions in rootless Podman under a Go policy
chain (deny overrides allow; allow | deny | escalate), the tool proxy
and flight recorder, `hobbes plan` / `hobbes run` deriving per-unit
context and policy from the graph (ADR-051/054), `hobbes review` at
the concept level with compiled invariants, `hobbes verify` (ADR-100).
Under test; no benchmark claim earned (architecture §6.2).

**Not in the version:** the oracle lane and its foreign converters,
the benchmark harness, Calvin, the test-time-training and Atlas-0
instruments — `bench/`, internal testing.
