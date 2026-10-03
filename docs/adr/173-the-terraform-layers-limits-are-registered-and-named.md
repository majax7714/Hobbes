# ADR-173 — The Terraform layer's limits are registered and named; a reference resolves in its own directory

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: the extraction order, Phase 1 item 1, "approved,
all recommendations are good") and **built** (0.2.102-beta) · **Owner:** Max · **Source:** the honesty
audit's HCL fixture (`~/.hobbes/bench/honesty-audit/fixtures/tf/`, `RESULTS.md` § Terraform/HCL); the
address-merge probe on two public repos (`~/.hobbes/bench/tf-audit-2026-10-03/`).

Registers **C-187 to C-193**, each surfaced. One drawing change: a `references` edge whose target address is
declared only in another directory is refused.

## What is wrong

The Terraform/HCL layer (ADR-010, the `terraform` pack since ADR-035) shipped with no `C-n` at all.
Architecture §3.8 says "this repo only"; the 2026-10-01 honesty audit had a fixture for every language but
HCL. `list_blind_spots` said nothing about it, and refused a scope holding only `.tf` files ("no detected
call sites"). A precedent-1 gap.

The fixture (one block per shape, ingested at 0.2.101-beta) drew every direct reference, indexed, keyed,
splat, `depends_on`, `dynamic` and data-source reference, the two env-set shapes, and the `packages` join.
It drew nothing for:

- a reference through a `local`, a `variable` or an `output` (none of the three is a node);
- a module call's contents: `module "net" { source = "./modules/net" }` is one node, nothing links it to
  the child directory, and a registry or git module is not read;
- env keys outside a literal `environment { variables = {…} }` or `env { name = … }` (an `app_settings`
  map, ECS `jsonencode([{ environment = [...] }])`, a map held in a local or a variable);
- a `packages` path under `${path.root}`, to a directory (`archive_file`'s `source_dir`), or to any file
  but a Python module;
- `.tf.json` and `.tofu` files, and `import`, `moved` and `check` blocks;
- a block after an unclosed brace: tree-sitter-hcl's recovery swallows the rest of the file and nothing
  said so.

Two shapes drew **wrong**:

- **The address merge.** Node ids are `tf:<address>` across the whole repo, but Terraform scopes an address
  to its module's directory. Two directories that each declare `aws_iam_role.this` are one node, whose
  `path` is the first directory's, and every edge to either lands on it. Measured with the extractor:
  terraform-aws-eks (`e072462`) 287 blocks become 203 nodes, 39 addresses declared in more than one
  directory cover 123 blocks, and 170 of 288 reference sites touch a merged node; terraform-aws-vpc
  (`b3abd6d`) 8 addresses over 47 blocks, 37 of 162 sites.
- **A cross-directory reference.** A block naming an address declared only in another directory drew an
  edge to it (the fixture's `envs/stage` flow log to the child module's VPC). Terraform never resolves
  that; both public repos have none, since valid code cannot.

## The decision

1. **Register C-187 to C-193** in a new segment, `constraints/extraction-terraform.md`: the address merge
   (C-187), references not followed through locals, variables and outputs (C-188), module calls not
   followed (C-189), the env-set join's literal shapes (C-190), the `packages` join's paths (C-191), files
   and regions not read (C-192), and the plan's root module and line-1 evidence (C-193).
2. **Name them per ingest.** The pack writes one `hcl-layer` degradation record wherever it runs, with this
   repo's counts: `.tf` files read; `locals`, `variable` and `output` blocks; module calls, local and remote;
   `.tf.json` and `.tofu` files not read; addresses declared in more than one directory, with examples; and
   cross-directory references refused. Each `.tf` file that parsed with errors writes one `hcl-parse`
   record. Both reach `list_blind_spots` and the ingest summary.
3. **A reference resolves in its own directory.** A `references` edge is drawn only where its target
   address is declared in the source block's directory. That is Terraform's own rule, and it fails toward
   drawing less. The plan path keeps file-granular evidence (C-193).
4. **`list_blind_spots` serves a scope that holds Terraform nodes and no call sites**, instead of refusing
   it.

## Not decided here (Max)

**The merge's prevention.** Every route changes what a user sees, and the ids change for one of them:

- **Route 1, ids scoped by directory** (`tf:<dir>:<address>`): each block its own node, C-187 lifts.
  Every `tf:` id in a multi-directory repo changes.
- **Route 2, contain as C-180 does:** keep the ids, and refuse the facts of every directory after the first
  that declares a shared address. terraform-aws-eks would lose most of 170 reference sites.
- **Route 3, leave it named** (this ADR's state).

**Decided 2026-10-03** (Max: "good with recommended"): route 1, ids scoped by directory. Built in its own
amendment.

## Built (0.2.102-beta)

`extract/terraform.py`: `_layer_record`, `hcl-parse` records, the directory check in `extract_terraform`,
and `discover_tf` over a shared walk that also finds `.tf.json` and `.tofu`. The pack passes the records on.
`go/internal/knowledge`: `ListBlindSpots` accepts a scope with `tf:` nodes. Tests: `test_terraform.py`
gains `TestLayerRecord` and `TestDirectoryScope`; `knowledge_test.go` gains the infra-only scope.
