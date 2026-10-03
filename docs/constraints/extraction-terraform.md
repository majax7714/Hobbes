# Extraction — Terraform/HCL (ADR-010, ADR-035, ADR-173)

The `terraform` pack reads every `.tf` file with tree-sitter-hcl and draws `tf:` nodes for `resource`,
`data` and `module` blocks, `references` between them, `env-set` to `env:` nodes and `packages` to Python
modules, all `syntactic`. It is verified on this repo only (§3.8, C-31). Until 2026-10-03 the layer had no
entry here; the honesty audit's HCL fixture (`~/.hobbes/bench/honesty-audit/fixtures/tf/`) measured each one
below. Every ingest that runs the pack writes one `hcl-layer` degradation record with the repo's counts,
which `list_blind_spots` serves, also for a scope that holds only `.tf` files.

### C-187 — Two Terraform blocks with one address in different directories are one node — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** which of them an edge belongs to. Terraform scopes an address to its module's
  directory, so `envs/dev` and `envs/prod` can each declare `aws_s3_bucket.logs`, and every module of a
  module library can declare `aws_iam_role.this`. The graph's id is `tf:<address>` across the repo: the
  blocks are one node, whose `path` is the first directory's (sorted), and the edges of all of them land on
  it, each evidenced at its own line.
- **Because:** node ids were written for one root module (ADR-010) and carry no directory.
- **Bites at:** `graph_neighborhood` on a `tf:` node, the graph view, `hobbes review` on any repo with more
  than one Terraform directory. Measured 2026-10-03: terraform-aws-eks (`e072462`), 39 addresses over 123
  of 287 blocks, 170 of 288 reference sites touch a merged node; terraform-aws-vpc (`b3abd6d`), 8 addresses
  over 47 of 166 blocks, 37 of 162 sites. A reference to an address declared only in another directory,
  which Terraform never resolves, drew an edge until 0.2.102-beta and is now refused.
- **You find out:** **surfaced** — the `hcl-layer` record counts the addresses declared in more than one
  directory, with examples and how many directories each, and the cross-directory references refused.
  The prevention (ids scoped by directory, or C-180's refusal) is Max's decision (ADR-173).
- **Source:** ADR-173; the probe `~/.hobbes/bench/tf-audit-2026-10-03/merge_probe.py`.

### C-188 — A reference through a local, a variable or an output is not drawn — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** that `aws_lambda_function.f` depends on `aws_iam_role.r` when it reads
  `local.role_arn` and the local reads the role; what an `output` exposes; what a `variable` feeds. None of
  `locals`, `variable`, `output` or `provider` is a node, and a chain headed `local.`, `var.` or `self.` is
  not followed. `import`, `moved` and `check` blocks are not read either.
- **Because:** the layer draws a block's own traversals to a declared block; an indirection would need the
  value of the local or the variable, and a variable's value comes from outside the code.
- **Bites at:** `graph_neighborhood` on a resource read through a local (the dependency is absent, not
  nonexistent), any question about a module's outputs.
- **You find out:** **surfaced** — the `hcl-layer` record counts the repo's `locals`, `variable` and
  `output` blocks and names this entry.
- **Source:** ADR-173 (fixture shapes S3, S5, S16).

### C-189 — A module call is one node, not followed into its source — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** what a `module "net" { source = "./modules/net" }` instantiates. The call is a
  `tf-module` node and a reference to `module.net.vpc_id` draws to it, but no edge runs from it to the child
  directory or its blocks, which are nodes under their own bare addresses (and merge, C-187). A registry,
  git or URL source is not read at all.
- **Because:** the layer parses files, not module instances; following a source would need the module tree
  `terraform init` builds, and a remote source is outside the repo.
- **Bites at:** `graph_neighborhood` on a module node, and any question of what a root module deploys.
- **You find out:** **surfaced** — the `hcl-layer` record counts module calls, local and registry or
  remote.
- **Source:** ADR-173 (fixture shapes S6, S7).

### C-190 — The env-set join reads only literal keys in two block shapes — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** that Terraform sets an environment variable outside `environment { variables = {…} }`
  and `env { name = "…" }`: an `app_settings` map (Azure functions and web apps), an ECS
  `container_definitions = jsonencode([{ environment = [...] }])`, a map held in a `local` or a `variable`,
  or a key that is not a literal. Keys inside a `merge(…)` of literal objects are read.
- **Because:** the join is id equality on a key the code writes literally (ADR-010); each other shape is a
  provider's schema or a value, not a syntax.
- **Bites at:** the cross-layer join: a Python `env-read` with no `env-set` beside it does not mean nothing
  sets the variable.
- **You find out:** **surfaced** — the `hcl-layer` record states it on every ingest with `.tf` files.
- **Source:** ADR-173 (fixture shapes S8, S9, S10).

### C-191 — The packages join reaches only a Python file at a literal or `${path.module}` path — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** what Terraform packages from a directory (`archive_file`'s `source_dir`), a built
  archive, a path under `${path.root}` or another function, or a TypeScript, JavaScript or Go file. A
  `${path.module}` path inside a function such as `filebase64sha256(…)` is read.
- **Because:** the join resolves a string against the `.tf` file's directory and matches it to a module
  Python discovery found (ADR-010).
- **Bites at:** the infra-to-code edge on any non-Python Lambda or container, and any directory-packaged
  one.
- **You find out:** **surfaced** — the `hcl-layer` record states it on every ingest with `.tf` files.
- **Source:** ADR-173 (fixture shapes S11, S12, S21).

### C-192 — Terraform written as `.tf.json` or `.tofu`, or inside a region the parse could not read, is not read — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** the blocks in a `.tf.json` or OpenTofu `.tofu` file, or in a `.tf` file after
  a syntax error tree-sitter-hcl cannot recover from: an unclosed brace takes every later block in the file.
- **Because:** the layer parses HCL native syntax, and only files named `.tf`.
- **Bites at:** every `tf:` answer; the nodes are absent, not nonexistent.
- **You find out:** **surfaced** — the `hcl-layer` record counts the `.tf.json` and `.tofu` files and names
  three; each `.tf` file that parsed with errors writes one `hcl-parse` record.
- **Source:** ADR-173 (fixture shapes S19, and the two unread files).

### C-193 — A plan adds only its root module's resources, evidenced at line 1 — *registered 2026-10-03 (0.2.102-beta, ADR-173)*
- **Cannot tell you:** the resources a `--tf-plan` document holds under its child modules (`module_calls`),
  or the line a planned reference is written on: the plan's nodes and edges cite the plan file at line 1.
- **Because:** `_consume_plan` reads `configuration.root_module.resources`, and a plan carries no source
  lines.
- **Bites at:** an ingest run with `--tf-plan` on a repo whose plan has child modules.
- **You find out:** **surfaced** — every plan edge's evidence is the plan file at line 1, which no `.tf`
  edge can be; the child-module limit is this entry, stated in `hobbes ingest --help`'s `--tf-plan` text.
- **Source:** ADR-010; ADR-173.

## Lifted constraints in this segment

None.
