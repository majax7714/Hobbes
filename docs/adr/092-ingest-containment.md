# ADR-092 — Sandbox whatever executes repo-authored code: ingest containers (phase 1)

**Date:** 2026-08-27 · **Status:** accepted — phase 1 built · **Owner:** Max · **Source:** the architecture review of 2026-08-27 (the sandbox boundary covered agent sessions but not extraction or the oracle lane)

## Context

The sandbox story answered "what can the agent do". But the model was
never inside the containers — a session is a tool loop calling an
endpoint — and Podman contains *processes*. Drawn around that adversary,
the boundary missed the layers that execute repo-authored code **by
design**: lane B's Rust provider (rust-analyzer's loader runs `build.rs`
and proc macros, C-29) and the oracle lane's O6/O7 (the repo's test
suite under a trace; `rustc` over the repo). Both ran on the host.
Theoretical against our own repos; live the day a foreign public repo is
ingested, which is the stated next move.

The corrected rule: **sandbox whatever executes repo-authored code.**

What executes, stated once so nobody re-derives it:

| process                                    | executes repo code via                        | contained before | after this ADR |
|--------------------------------------------|-----------------------------------------------|------------------|----------------|
| Rust lane B (rust-analyzer `scip`)          | build scripts, proc macros (C-29)             | no               | **phase 1**    |
| the venv listing (`venv_environment`)      | the venv's own `bin/python`, a binary under the repo tree — found in the build, not in the review | no | **phase 1** |
| oracle O6 (Python trace), O7 (rustc MIR)   | runs the suite; compiles the repo             | no               | phase 2        |
| agent sessions                             | the work itself                               | yes              | unchanged      |

Not in the executing set: scip-python (Pyright), scip-go, scip-typescript,
`tsc` (O3), Go RTA over SSA (O1/O2/O4 — SSA construction runs no repo
code), tree-sitter, the bench arms (contained in swebench images since
ADR-058), and the three fetch steps below.

## Decision

**New specific guarantee (P10): repo code never executes on the host.**
Being P10-specific, the general degrade machinery may not absorb it: a
box without podman does not quietly fall back to host execution.
Disclosure (C-29's treatment) remains, but disclosure is not
containment; C-29 narrows to "executes inside the ingest container" and
the guarantee carries the rest.

### Phase 1 — ingest containers (built)

1. **Contain all of lane B, not only the executing providers.** The
   guarantee needs only Rust and the venv listing; uniformity means it
   never depends on a per-provider judgment about what "doesn't
   execute" — one code path (P6's no-second-path rule). The cost is near
   zero: the image exists.
2. **One image stands** — ingest is a new mount shape on
   `hobbes-session:local`, not a new image. The Containerfile is
   extended with the pinned toolchains (node 22.14.0, Go 1.26.5, scip-go
   v0.2.7, rustup 1.97.1 + rust-analyzer) and moves to a glibc base
   (ubuntu 24.04) because the trees mounted from the host — a venv's
   interpreter, a `node_modules` — are glibc-linked; the proxy is static
   and runs on either. scip-python / scip-typescript stay pinned in
   `scip/package.json` and ride in with the helper (below).
3. **Mounts, derived not authored, every one at its host path**
   (`pipeline/src/hobbes/extract/containment.py`):
   - the Hobbes cache root **rw** — the stage, the helper config and
     SCIP output, the provisioned `node_modules`, and the cargo / go /
     npm caches (`CARGO_HOME`, `GOMODCACHE`, `GOCACHE`,
     `npm_config_cache` all point under it). It is Hobbes's copy;
     ADR-027's contract and its tests (C-22) still hold;
   - the hobbes checkout's `scip/` **ro** — the helper and the two npm
     indexers, host-managed like the proxy is;
   - every symlink target the stage points at outside the cache **ro** —
     a repo-owned `node_modules`, the venv, and the interpreter it links
     to, **hop by hop and unresolved**: a hop may pass through a
     directory that is itself a symlink (uv's `cpython-3.12-…` →
     `cpython-3.12.13-…`), and mounting the resolved target leaves the
     path the link names dangling inside the container. Podman binds the
     real directory at the named path. The mount plan is computed from
     the same walk that placed the links (ADR-050). Declined: rewriting
     links to container paths at staging — more moving parts for the
     same property; revisit only if a provider realpath-resolves in a
     way that breaks the mount.
   - never a system prefix (`/usr`, `/lib`, …): the image supplies its
     own; a venv over the host's `/usr/bin/python3.13` lists nothing in
     the container and degrades under C-27, visibly.
4. **Network by phase separation, not by route.** Every *index* step
   runs `--network none`. The three steps that need a registry —
   `npm ci --ignore-scripts` (ADR-050), `cargo fetch`, `go mod
   download` — are separate **fetch** containers with podman's default
   network that download and execute nothing. Rootless podman offers no
   per-route packet filter, so "the crate registry route only" (C-30,
   C-34) is met the stronger way: the container that can reach the
   network never runs the repo's code, and the container that runs the
   repo's code has no network. `cargo fetch` additionally pins
   `build.rustc`, `build.rustc-wrapper` and `build.rustc-workspace-wrapper`
   on its command line so a staged `.cargo/config.toml` cannot redirect
   the toolchain to a repo binary; `RUSTUP_TOOLCHAIN` and
   `GOTOOLCHAIN=local` keep a `rust-toolchain` file or a `go.mod` from
   asking for a download. A failed fetch is not a failed index: the
   index runs offline and resolution degrades where the registry was
   needed (C-30's shape, now per fetch, recorded).
5. **No policy chain.** An ingest container carries a static per-step
   profile (`containment.PROFILES`) — fixed mounts, fixed network, no
   escalation, nothing to approve mid-ingest and no one to ask. The
   six-layer chain exists for sessions, where a human and a model are
   present. `--security-opt label=disable` rather than `:z` relabels: the
   ro mounts are the user's own directories and a relabel would change
   their SELinux context in place (ADR-060's trade, taken the other way
   for trees Hobbes does not own).
6. **Degrade rules, on a box without podman or without the image:**
   - steps that execute repo code **refuse** — `ContainmentRefusal`, a
     distinct type that is not a `ScipError` and not an `OSError`, so
     the per-unit and per-language catches cannot match it by accident;
     each names it and re-raises first (ADR-036's shape). Rust falls to
     lane A's syntactic floor with a record naming the guarantee;
     the venv listing is skipped with a C-27 record;
   - steps that execute no repo code **may run on the host**, and say
     so in a degradation record — losing Python/TS/Go semantics to a
     uniformity preference would be the wrong trade. The ingest summary
     and `list_blind_spots` print the split (they read the same
     `extraction_errors`);
   - `HOBBES_UNCONTAINED=1` is the named escape hatch: everything runs
     on the host and every provider's facts carry the disclosure. Never
     a default, never silent. (The CLI flag is phase 3.)
7. **Verification, in the fixture culture.** The negative is tested by
   canary: `tests/fixtures/canary-rust` is a crate whose `build.rs`
   emits a cfg that makes `generated()` exist (proving it ran), reads a
   planted fake secret at a fixed host path and emits a second cfg if it
   could (`leaked()`), and writes a sentinel outside the stage. The
   suite asserts `generated()` is in the facts, `leaked()` is not, the
   sentinel is absent on the host, and no host-run record was written —
   it ran, and it ran contained (0.6 s on this box). Plus the
   unit-level assertions that the ingest driver's command plan routes
   every provider through the planner, that the executing set is
   exactly `{index-rust, python-env}`, and that the refusal type is
   outside every general catch — so a regression is a red build, not a
   triage discovery (ADR-082's principle: the method refuses).

**Measured no-op.** This repo re-ingested contained (Python via
Pyright with `pipeline/.venv` and uv's interpreter mounted ro; TS with
three repo `node_modules` mounted ro; Go after a `go mod download`
fetch): see the BUILDLOG entry for the tier-count diff against the
pre-change `graph.json`.

### Phases 2–4 (not built here)

- **Phase 2 — oracle containers.** O6/O7 in the same image with the
  verifier role's mount shape verbatim (overlay `:O` on the tree,
  ADR-060 — a plain ro mount breaks pytest's caches and build dirs,
  C-43) plus an rw output dir. O6 no network; O7 the Rust profile.
  Containment must be a numeric no-op: re-run rust_proj (O7) and this
  repo's Python zone (O6) and diff against the stored cells; any drift
  is a new H-entry, triaged first. **Forward rule:** any future
  dynamic-tier ingestion (the schema's reserved `dynamic`) inherits this
  containment on day one — it is repo execution by definition.
- **Phase 3 — guarantee wiring.** The `--uncontained` CLI flag with its
  disclosure stamped into `graph.json` and any oracle cell record it
  touches; `list_blind_spots` naming C-64 by number.
- **Phase 4 — the reshaping.** The architecture states its two layers:
  a **knowledge layer** (sandboxed deterministic ingest → `derived/` →
  `hobbes-proxy serve --knowledge-only`, ADR-087) that is a complete,
  self-contained deployment with no model and no credential; and the
  **agentic layer** above it, opt-in, unchanged. Scoped (P11): Hobbes
  guarantees *its own* processes never execute the repo on the host;
  what the user's harness does with its own tools is outside the
  guarantee, and the serve banner says so.

## Decisions embedded here that the owner should ratify

Three calls, each independent — reverse any and the rest survives:
contain-all lane B (vs executing-only) with the degraded-box split;
mount-symlink-targets-at-identical-paths (vs link rewriting); one image
extended (vs a slim ingest image). A fourth taken in the build: network
by phase separation (fetch containers) rather than by route filtering,
because rootless podman has no route filter — it is the stronger
property anyway.

## Consequences

- **Register:** C-64 (new, surfaced — executing providers refuse on a
  box without containment; the split is printed); C-29 narrowed to
  in-container execution, disclosure retained; C-22's trust becomes a
  mount flag; C-30/C-34 unchanged in substance (the registry is now
  reached from a fetch container).
- **Architecture:** §3.2 gains lane B containment; §7's sandbox entry
  gains the ingest mount shape and the guarantee.
- **First run:** the image must be built before a semantic ingest
  (`docs/first-run.md`); without it Python/TS/Go still index on the host
  and say so, Rust refuses.
- **Cost:** the image grows (~2 GB with the toolchains); first ingest of
  a dependency-heavy repo re-downloads its registry into the Hobbes
  cache rather than reusing `~/.cargo` / `~/go`. The caches persist
  across ingests.
