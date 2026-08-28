# ADR-094 — The knowledge proxy runs in the sandbox image; every artifact says which Hobbes built it

**Date:** 2026-08-28 · **Status:** accepted — built, smoke-tested live · **Owner:** Max · **Source:** the stale-install incident of 2026-08-28 (BUILDLOG), and Max's ask: "run the full knowledge piece in the sandbox layer — it prevents path mismatching and hardens security"

## Context

On 2026-08-28 a bare `hobbes up` in this repo produced a `graph.json`
with no `containment` stamp. The trail: `~/.local/bin/hobbes` was a
symlink into a *different* checkout (`~/hobbes`, at `7356d84`,
2026-08-24 — four days before ADR-092). That tree's lane B ran on the
host, and the canary fixture's `build.rs` proved it
(`/tmp/hobbes-canary-escaped`, stamped the same minute). Harmless
against our own repo; but the P10 guarantee of ADR-092 had been
defeated by a PATH entry, and nothing said so — the artifact looked
like any other, minus a key nobody reads by hand.

Two facts about the knowledge layer follow. **Which code answers is a
property of the host's PATH**, both for the ingest (`hobbes`) and for
the tools (`.mcp.json` named `go/bin/hobbes-proxy`, a host binary that
must be built and current). And **an artifact does not say who made
it**: it carries the repo's commit, never the pipeline's.

Max's ask was the whole knowledge piece in the sandbox. This ADR
decides what goes in now, what does not yet, and the provenance that
covers both.

## Decision

### 1. `.mcp.json` starts the **image's** proxy, in a container

`sandbox/knowledge-serve` is the launcher `.mcp.json` names. It runs
`hobbes-proxy serve --knowledge-only` from **inside
`hobbes-session:local`** on stdio (`podman run -i`): the repo mounted
read-only at `/work`, `--network none`, `--pull=never`,
`--security-opt label=disable` (the repo is the user's own tree; not
ours to relabel — containment.py's trade for lane B mounts), the flight
log in the host's `~/.hobbes/sessions` as before. The binary that
answers is the one the image was built with — never one a PATH or a
symlink resolves to. The launcher binds to the checkout that owns it
(`$0/..`), not to the caller's PATH.

Not because the six tools execute the repo — they do not, and the P10
guarantee never needed this. Because the **build that answers is now
pinned to the image**, and a read-only, offline container is a harder
place for a crafted `graph.json` to do anything than a host process.
Cost: one container start per agent session (~0.5 s), measured on the
smoke test; nothing per call.

**Refusal, not fallback.** Without `podman` or the image the launcher
exits 1 naming the fix — a silent fallback to a host binary would be
the pinning quietly not happening, the exact shape of the incident.
The escape hatch is `HOBBES_KNOWLEDGE_HOST=1`: this checkout's
`go/bin/hobbes-proxy` on the host, disclosed on stderr (C-65).

### 2. Every artifact says which Hobbes built it; every answer repeats it

`graph.json` carries `built_by: {checkout, sha, dirty}` — the git
toplevel and commit of the *pipeline code that ran* (an installed
wheel outside a checkout records its package path and an empty sha).
`hobbes ingest` prints it on the second line (`built by hobbes @ …
from …`); the knowledge tools' header — the line every answer opens
with — repeats it beside the repo commit; `hobbes-proxy serve` prints
its own `build <vcs.revision>` at start. The stale-install case is now
three visible facts, not one missing key.

### 3. The ingest itself stays on the host — parked, with the reasons

Running `hobbes ingest` inside the image is possible and is **not**
"doesn't hurt":

- lane A executes no repo code (tree-sitter parses; lane B's
  executing steps are already contained), so P10 gains nothing;
- the pipeline's source and wheels would be baked into the image —
  a 4-minute rebuild per pipeline edit during active development, or
  a dev-mode mount of the checkout that un-pins exactly what the move
  was for;
- lane B's per-step containers would become nested rootless podman
  (needs privileges we do not want to grant) or collapse into one
  container, losing ADR-092's network-by-phase separation (`--network
  none` on index steps, fetch containers for the registry).

The provenance stamp (§2) is what the incident actually asked for —
*which code ran* — and it covers the ingest without any of the above.
Parked in `future_additions.md`; opens if a foreign-repo deployment
needs the pipeline pinned too, and the answer then is probably a
pinned wheel in the image plus a nested-podman decision, not a mount.

## Consequences

- `.mcp.json` works on a box with podman and the built image; on any
  other box it says so. Building the image is already a first-run
  step (ADR-092).
- **A stale image is the new stale binary.** The image's proxy is
  whatever was `COPY`'d at build; the first smoke test of this ADR ran
  an image from 00:14 that predated phase 4's banner. The proxy's
  `build <rev>` line and C-65 name this; rebuild the image after
  rebuilding the static proxy (`sandbox/README.md`).
- The `go/bin/hobbes-proxy` host build is no longer on the knowledge
  path except through the hatch; `hobbes-session` still mounts the
  static one from `sandbox/` for agent sessions (unchanged).
- Tests: the launcher under a fake podman (argv shape, refusal,
  hatch), the stamp in `test_cli`, the header in `knowledge_test`.
  Live: six tools answered through the container against this repo.
