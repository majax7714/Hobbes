# ADR 010: Terraform/HCL extractor — model, joins, plan consumption

Date: 2026-08-10
Status: accepted

## Context

Architecture §3.1 names the infra extractor (tree-sitter-hcl + optional
`terraform plan -json`); §4.1 wants cross-layer app↔infra joins. The
concrete node/edge model, join mechanics, and how plan JSON enters need
fixing. Survey of the designated test repo (private-repo-A) shaped two decisions:
its TF sets no environment variables and uses no `var.` references — its
real app↔infra coupling is `archive_file.source_file` packaging a Python
handler from the same repo.

## Decision

**Grammar.** `tree-sitter-hcl` (PyPI wheel, works against our pinned
tree-sitter 0.25.x) — the per-grammar-wheel policy of ADR-005.

**Nodes** (id prefix `tf:`, joining the existing graph.json node list):
`tf:aws_lambda_function.worker` (kind `resource`),
`tf:data.archive_file.worker` (kind `data`), `tf:module.vpc` (kind
`tf-module`). Variables, outputs, locals, and providers are *not* nodes in
M3 — the test repo has none in load-bearing positions, and resolving
through them without evaluation risks false edges.

**Edges** (module-edge list, new types per §3.1's typed-edge vocabulary):

- `references` — a traversal chain in any expression
  (`aws_iam_role.worker.arn`, `data.archive_file.w.output_path`,
  `module.vpc.id`) whose address prefix matches a *declared* block in the
  repo. Undeclared addresses produce nothing: no false edges.
- `env-set` — the infra side of the env join, from two literal patterns:
  an `environment` block's `variables` map (Lambda-style) and `env` blocks
  with a literal `name` (container-style). Keys become the same `env:VAR`
  nodes the Python extractor emits for `env-read` — the join is id
  equality, no extra machinery.
- `packages` — the path join: any attribute whose string literal (after
  substituting `${path.module}` with the .tf file's directory) resolves to
  an existing repo file that the Python extractor discovered as a module.
  Edge from the tf block to that module node. This is additive beyond the
  build plan's named env-var join, adopted because it is the *only*
  app↔infra coupling that actually exists in private-repo-A; it is exact (string
  literal → real file → discovered module) and is the blast-radius edge
  ("this lambda redeploys when handler.py changes"). Directory references
  (`source_dir`) are deferred.

**Plan JSON (optional enrichment).** `hobbes ingest --tf-plan FILE` reads
a `terraform show -json` document: `configuration.*.resources[]`
contributes declared addresses and their `expressions.*.references` (the
resolved reference DAG) as `references` edges, deduplicated against the
static ones. Plan-derived evidence is file-granular (the plan path,
line 1) — plans don't carry source lines. The flag **refuses any path
containing `tfstate`**: state carries secrets and is denied at the policy
floor (ADR-011); the extractor must not be a side door.

**Schema.** graph.json's `"language": "python"` becomes
`"languages": [...]` (sorted; `["hcl", "python"]` when TF is present) and
`schema_version` bumps to **2** — a rename is a breaking change even with
zero external consumers, and lying about it would set the precedent.
`.tf` discovery skips the same directory set as Python discovery
(`.terraform/` is already excluded as a dot-directory); `.tf.json`
variants are out of scope for M3.

## Alternatives considered

- **python-hcl2 / pyhcl** — real HCL parsers, but a second parsing
  substrate against ADR-005's uniformity argument, and no source positions
  as good as tree-sitter's.
- **`terraform graph` output** — free DAG, but requires terraform
  runnable + initialized against real providers; static parse works on a
  bare checkout.
- **Var/local resolution** — evaluating HCL to chase references through
  variables is interpretation, not extraction; deferred until a real repo
  needs it.
- **Skipping the `packages` join** — would leave the M3 exit criterion
  ("one cross-layer edge verified by hand") unmeetable on the designated
  repo; the env join alone would only ever be fixture-proven.

## Consequences

- The app+infra graph is one artifact; graph diff and Mermaid render work
  on infra edges with zero changes to their engines (render gains shapes
  for the new kinds).
- `env-set`/`env-read` pairs meeting at `env:VAR` nodes are the §4.1
  join — queryable with plain set intersection.
- A repo whose TF wires env vars outside literal HCL (tfvars files,
  deployment scripts) shows no env joins — statically true, documented.
