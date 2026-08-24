# ADR 011: Built-in tfstate deny floor in the policy engine

Date: 2026-08-10
Status: accepted

## Context

Build plan M3: "`.tfstate` deny baked into the default box policy."
Architecture §3.1: state files carry secrets and are "denied at box.policy
level". There is no shipped box policy file — `~/.hobbes/box.policy` is
the user's — so "default" needs an implementation.

## Decision

The Go engine's `LoadChain` **always prepends a built-in synthetic box
file** (source `builtin:tfstate-floor`, level `box`) containing one rule:
pattern `*.tfstate*`, decision `deny`. It is part of the engine, not a
file: present with no policies configured at all, and — because deny is
unshadowable (ADR-002) — impossible to override from any repo or folder
policy. There is deliberately no off switch in v1.

`Chain`s assembled directly from parsed files (as the unit tests do) don't
carry the floor; it is a `LoadChain` guarantee, which is the only path the
CLI and the future M4 daemon use.

## Alternatives considered

- **`hobbes init` writing `~/.hobbes/box.policy`** — a file the user can
  edit or delete is a default, not a floor; secrets protection shouldn't
  depend on a bootstrap step having run.
- **Hardcoding in the CLI instead of the engine** — the M4 daemon imports
  the package, not the CLI; the floor must live below every consumer.
- **An opt-out flag** — YAGNI until a legitimate need to read state
  appears; if one ever does, that's a deliberate ADR revision, not a flag.

## Consequences

- `hobbes-policy resolve "cat terraform.tfstate"` denies even on a machine
  with no policies configured, and the JSON names `builtin:tfstate-floor`
  as the source — auditable, not magic.
- The repo-policy tfstate rule in `.hobbes/policies/repo.policy` becomes
  redundant; it stays as documentation of intent.
