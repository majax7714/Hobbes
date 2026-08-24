# ADR 020: Cartographer runner — headless, tool-less, validated

Date: 2026-08-11
Status: accepted

## Context

M5's narrative pass is the project's first quota-spending step. The
architecture frames it as cartographer *sessions* (§6: a role with
read-only source + rw `.hobbes/`), and M4 built a full session sandbox
— but a narrative unit is not an open-ended task: it is "turn this
skeleton slice into pinned claims", a pure function from context to
JSON. Running each unit as an interactive sandboxed session would burn
quota on tool round-trips and leave output shape to chance.

## Decision

`hobbes narrate` orchestrates **headless Claude Code**: one
`claude -p --output-format json --tools ""` invocation per work unit,
prompt on stdin. Binary override via `HOBBES_CLAUDE_BIN` (the
`HOBBES_POLICY_BIN` precedent); model override via `--model`.

- **Tool-less by construction.** `--tools ""` disables every built-in
  tool. The cartographer cannot read outside what the prompt shows,
  cannot write anything, cannot execute — "read-only on source" needs
  no sandbox because there is no I/O surface at all. The pipeline is
  the only writer, and it writes only `.hobbes/derived/docs/`.
- **The skeleton is the context (§3.2).** The prompt carries the
  unit's slice of `graph.json`/`tests.json`/`interfaces.json` plus the
  subject file's source with line numbers — the pins the model must
  cite are the numbers it was shown.
- **Validated, retried once, or dropped.** Output must parse as JSON
  and pass ADR-019 validation (pins exist, lines in range, behaviors
  cover exactly the file's tests). A failure feeds the problem list
  back in one corrective call; a second failure marks the unit failed
  and the run moves on — a bad unit costs two calls, never a loop.
- **Work units:** one call per module doc, one per test file's
  behavior index, one for invariant inference (which reads the fresh
  module docs' purposes). Units run when their artifact is missing or
  stale (ADR-019); `--all` forces, `--only`/`--exclude` filter,
  `--dry-run` prints the plan and spends nothing (the ADR-018
  precedent).

## Alternatives considered

- **Interactive cartographer sessions in the M4 sandbox** — the
  architecture's eventual shape, and the sandbox's role mounts
  (ADR-018) support it. Deferred, not rejected: it pays when narrative
  units need exploration (following a call chain the skeleton missed).
  v1 units don't, and structured single-shot output is dramatically
  cheaper and machine-checkable. Revisit with evidence of skeleton
  gaps.
- **One mega-prompt for the whole repo** — cheaper per token but one
  bad answer poisons everything, no incremental regeneration, and the
  output would blow past reliable generation length. Per-unit calls
  are the quota-sane granularity §3.3 already demands.
- **The Agent SDK / API instead of the CLI** — the project budget is
  the Claude Code subscription (build plan: "subscription quota");
  `claude -p` bills against it. The API is a different budget.

## Consequences

- Narrative quality is bounded by skeleton quality — the cartographer
  can't discover what the extractor didn't surface. Acceptable: fixing
  the skeleton fixes every doc on the next run.
- Every artifact on disk passed pin validation the moment it was
  written; the M5 exit's claim sampling starts from mechanically-valid
  pins.
- The flight recorder does not see narrate calls (no proxy involved);
  the BUILDLOG records narrate runs instead. When cartographer
  sessions move into the sandbox, logging comes with them.
