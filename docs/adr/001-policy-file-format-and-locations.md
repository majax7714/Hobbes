# ADR 001: Policy file format and discovery locations

Date: 2026-08-10
Status: accepted

## Context

Architecture §5.1 defines three policy scopes and what entries cover, and §10
defines the in-repo `.hobbes/` layout, but neither pins down the concrete file
schema. §5.1 sketches the repo policy at `repo/.hobbes/repo.policy` while
§10's authoritative layout puts hand-reviewed policy under
`.hobbes/policies/` — the two need reconciling.

## Decision

**Format.** Policy files are YAML, parsed strictly (unknown keys are errors,
so typos like `descision:` fail loudly instead of silently producing a no-op
rule). Schema v1:

```yaml
version: 1            # required, must be 1
scope: repo           # optional: box | repo | folder; validated against the
                      # location the file was loaded from, if present
default: escalate     # optional: decision when no rule matches (see ADR-002)
rules:
  - pattern: "git push --force*"   # glob over the command string, required
    decision: deny                 # allow | deny | escalate, required
    reason: "force-push forbidden" # optional, surfaced in resolve output
```

Patterns support `*` (any run of characters, including spaces and slashes)
and `?` (any single character); no character classes in v1. Matching is
anchored (whole-string) against the command with runs of whitespace collapsed
to single spaces.

**Locations.**

- Box: `~/.hobbes/box.policy`
- Repo: `<repo>/.hobbes/policies/repo.policy` — §10's `policies/` directory
  wins over §5.1's sketch for the repo root, since the root `.hobbes/` holds
  multiple artifact classes.
- Folder: `<folder>/.hobbes/folder.policy` for any directory inside the repo,
  per §5.1 (nested folders don't carry the `policies/` subdirectory — they
  hold exactly one file).

Sections named in §5.1 but not needed until later milestones (writable paths,
network egress, resource caps) are **not** in schema v1; they will be added as
new top-level keys when their consumers exist (M3/M4). Adding keys is
non-breaking because files declare `version`.

## Alternatives considered

- **JSON/TOML** — policies are hand-reviewed source of truth; YAML is the
  most comfortable to hand-edit and matches the invariant schema in §10.
- **Repo policy at `.hobbes/repo.policy`** — contradicts §10's layout.
- **Full §5.1 schema now** (egress, caps, paths) — speculative; no consumer
  until M4, and guessing merge semantics without the daemon risks baking in
  wrong ones.
- **Lenient YAML parsing** — a typoed key in a *security policy* must never
  be silently ignored.

## Consequences

- The M4 daemon and the M0 CLI share one schema and one parser.
- Schema growth is additive and versioned.
- Command-string glob matching is a v1 simplification; argv-aware matching
  hardening belongs to the M4 proxy (noted in ADR-002).
