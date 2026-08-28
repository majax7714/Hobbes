# ADR-095 — CI, for real: the five suites and the graph shape run on every push

**Date:** 2026-08-28 · **Status:** accepted — written and validated locally, not yet observed on GitHub Actions (this repo is never pushed from a session) · **Owner:** Max · **Source:** `docs/workstreams.md` W0 ("CI, for real"), README ("the CI shape"), C-19

## Context

The README has named the CI shape since v1 — `hobbes ingest && hobbes
lanes && hobbes review $BASE..HEAD` — and the architecture said in two
places that none was configured. Every suite was run by hand, by
discipline, and the compiled invariant checkers (C-19) had never run
outside a developer box. Since ADR-092 lane B runs only inside the
sandbox image, which decides most of what a CI job has to look like.

## Decision

1. **One workflow, four independent jobs** (`.github/workflows/ci.yml`):
   `go` (gofmt, product + oracle-lane `go test`, the static proxy
   builds), `python` (pytest, lane B off — the default), `web` (vitest +
   build, tsextract, the scip helper), and `graph`. Independent so a red
   suite is named by its job, not found in one log.
2. **The graph job is one script, `scripts/ci-graph.sh <base>`**, run
   identically by CI and by a developer. It builds the static proxy and
   the image, then: `hobbes ingest` → **the `containment` stamp is
   checked** (`all_contained` and no escape hatch — an unstamped or host
   graph fails the job; the ADR-094 incident shape) → `hobbes lanes` →
   `hobbes invariants compile --json` and **every compiled checker is
   executed** → `hobbes review $BASE..HEAD` → the `lane_b`-marked pytest
   cases.
3. **The image is built in CI, not pulled.** Lane B refuses on the host
   (C-64); an ingest without the image would not be the graph this repo
   verifies. ~4 min per run on a GitHub runner is the price; a registry
   pull is an optimisation for later, not a different decision.
4. **The base ref** is the merge-base with the target branch on a pull
   request and `github.event.before` on a push to `main` — `hobbes
   review` takes a two-dot range only.
5. **One known failure is deselected by name**, with its reason in the
   script: `test_venv_environment_lists_the_venvs_own_distributions`, the
   environmental failure `session-handoff.md` holds untouched (the fake
   venv answers with the interpreter's own listing once the call is
   contained). Deselected in the script, never silenced in the suite;
   fixing the test is the W0 item that closes it.

## Consequences

- **C-19 narrows to "not exercised", not "never executed":** the
  semgrep emitter (I-5) runs in CI on every push. dependency-cruiser
  and Rego remain unexecuted because no confirmed record in this repo
  compiles to them — a record that does would make the script fail
  until the tool is on the runner, which is the surfacing.
- The architecture's two "no CI is configured yet" lines are amended
  (§3.4, §3.6).
- The workflow has been validated by running `scripts/ci-graph.sh
  HEAD~1` and each job's commands on the development box; the first
  run on GitHub happens when Max publishes. Anything runner-specific
  (rootless podman under the `runner` user, the rustup download inside
  `podman build`) is a P11 gap until then, stated here rather than
  claimed.
