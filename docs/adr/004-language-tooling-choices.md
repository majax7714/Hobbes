# ADR 004: Language tooling choices for M0

Date: 2026-08-10
Status: accepted

## Context

D1 locks the languages (Go engine, Python CLI/pipeline) but not the libraries
or project layout inside each.

## Decision

**Go (`go/`, module `github.com/majax7714/Hobbes/go`)**

- YAML parsing: `gopkg.in/yaml.v3` — the de-facto standard, and its
  `KnownFields(true)` gives the strict parsing ADR-001 requires. Only
  third-party dependency in the module.
- CLI: standard-library `flag` with a hand-rolled subcommand dispatch, not
  cobra/urfave. One binary with one real subcommand doesn't justify a
  framework dependency tree; revisit if the daemon grows a real command
  surface.
- Glob matching: hand-implemented (`*`/`?`, rune-wise, anchored) rather than
  `path.Match`, because `path.Match` gives `*` path-segment semantics
  (stops at `/`) which is wrong for command strings.

**Python (`pipeline/`, package `hobbes`)**

- uv-managed, `src/` layout, `hatchling` build backend (uv's default),
  console script `hobbes = hobbes.cli:main`.
- CLI: standard-library `argparse`, not click/typer. The M0 skeleton is three
  stubs and a passthrough; stdlib keeps the dependency surface at zero.
  Revisit at M1+ if subcommand ergonomics start to hurt.
- Tests: pytest (dev dependency group), hermetic — the policy shell-out is
  tested against a fake binary, so `uv run pytest` never requires the Go
  toolchain.

## Alternatives considered

- **cobra** (Go) / **click or typer** (Python) — better ergonomics at scale,
  unnecessary for the current surface; deliberately deferred, not rejected
  forever.
- **`path.Match` / regexp for globs** — wrong semantics / needless
  translation layer for two metacharacters.
- **Flat Python layout** — src layout prevents accidental import of the
  uninstalled tree and is uv's packaged default.

## Consequences

- `go.sum` carries a single dependency; `pipeline` has zero runtime deps.
- Both CLIs may need a framework migration if their surfaces grow — accepted
  cost, paid only if it happens.
