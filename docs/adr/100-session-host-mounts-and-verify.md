# ADR-100 — A session may mount host trees read-only; a target's tests run under the ingest planner

**Date:** 2026-09-04 · **Status:** accepted — built as Calvin M0 step 5 (`docs/calvin-potential.md` §8) and exercised on this repo the same day: the 28 gold diffs through the verifier, a scripted arm-O session through `hobbes-session` · **Owner:** Max · **Source:** the design's step 5 ("local harness wiring: Podman exec + policy + testmap for T and O"); the step is model-free by the design's own order.

Amends the architecture's **§7 Sandbox** (a fourth mount shape on the
one image) and its runtime paragraph in **§6.2** (`--mcp-tools`).
Registers **C-92** and **C-93**
(`docs/constraints/verification-benchmark-harness.md`).

## Context

Calvin M0's arms need a harness that can *run this repo's tests at a
parent commit*: arm T's verdict is the guarding tests over a grounded
diff, and arm O is an orchestrator with policy-checked `exec` on the
same box. The sandbox image (ADR-092) carries the toolchains — Go,
Node, Python 3.12 — and none of the repo's **dependencies**: no `uv`,
no venv, no `node_modules`. On the benchmark path the instance image
supplied those (ADR-058); on this repo nothing does, and the cell of
2026-09-03 ran every arm with file tools only for exactly that reason
(its defect D-1: "no arm can execute").

Lane B already solved the same problem for indexing: a regenerable
dependency tree is *symlinked* into the stage, never copied (ADR-032,
ADR-050), and every link target is mounted **read-only at its own host
path** so the link resolves inside the container; the container runs
with SELinux labeling off rather than relabeling the user's own
directories in place (the ADR-060 trade taken the other way, for trees
Hobbes does not own). What the session launcher lacked was a way to
carry such a mount.

## Decision

1. **`hobbes-session --mount HOST[:CONTAINER]`** (repeatable). A host
   tree the session may read and never write: mounted `ro`, never
   relabeled, at the same path unless a container path is given; it
   may not shadow `/work` or `/sessions`, and any such mount runs the
   container with `--security-opt label=disable`. The dry run prints
   every one. It is an *environment binding* in ADR-058's sense — host
   authored, visible in the argv, not the agent's and not policed.
2. **The environment binding is derived, not authored**
   (`hobbes.derive.harness.environment`): for every manifest in the
   worktree (`pyproject.toml`, `package.json`) whose regenerable
   dependency directory (`.venv`, `node_modules`) exists beside the
   same manifest in a **source checkout** of the repo, the harness
   links that directory into the worktree and mounts it read-only; a
   venv's interpreter rides along hop by hop as lane B mounts it; the
   Go module cache is the one lane B's fetches filled under the Hobbes
   cache root. The links are excluded from git (`.git/info/exclude`)
   before a session starts, so commit-on-exit never carries the
   harness's own binding as the session's work — the first scripted
   run's patch did, and that is why.
3. **A target's tests run under the ingest planner**: a `verify`
   profile in `containment.PROFILES` — executes repo code, no network
   — so `hobbes verify` (and arm T's verdict) is one more mount shape
   on the same image, refuses without it like every executing step
   (P10), and stamps the record with where it ran. The verifier
   selects tests from the **testmap** at the SHA (symbol grain where
   the diff touches a span, module grain outside every span, the whole
   file for a test file the diff touches), runs them with and without
   the diff, and classes each outcome against its baseline.
4. **The owned loop can be offered a subset of the proxy's tools**
   (`loop.py --mcp-tools exec`): arm O gets `exec` and nothing else of
   Hobbes, so the manifest in its brief is the only Hobbes in O, as the
   template is the only Hobbes in T. The proxy still serves every
   tool; only what the model sees narrows, and a withheld tool is
   refused before it reaches the server.

## What this does not change

- **Repo code never executes on the host.** The verifier's container
  has no network and the mounts are read-only; an arm-O session's
  network is the model endpoint's, as every benchmark session's was.
- **The session's own mounts** keep their relabel; labeling off is the
  price of binding a tree the user owns, paid only when one is bound.
- **The policy chain.** An arm-O session runs under a box policy
  (`calvin.box.policy`: the ADR-057 floor plus this repo's runners in
  the image) and an agent policy allowing its guards; the specific
  guarantees still win by deny-overrides, and the scripted run shows a
  `git push` denied by the agent layer and an unlisted `curl` parked
  and expired to deny.

## Consequences

- **C-92** — the binding is the *source's* dependency set, not the
  SHA's lockfile; **C-93** — the verifier sees a behaviour only through
  a test the testmap maps, and what the testmap mislabels (a fixture
  named `test…`) it reports as uncollected.
- The record of every verify carries the selection, the environment,
  every command with its exit and the containment stamp; a reader can
  say for each test where and how it ran.
- Calvin M0's own ADR, when Max moves the design to *accepted*, takes
  the next number (101), not 100 as the design's header estimated.
