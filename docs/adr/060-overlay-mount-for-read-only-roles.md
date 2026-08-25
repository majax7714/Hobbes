# ADR-060 — Read-only roles get an overlay worktree, not a `ro` mount

**Date:** 2026-08-22
**Status:** accepted — built; found by the harness restructure's phase 4
probe, the first live run of a read-only role in a benchmark image.
**Amends:** `docs/hobbes-architecture.md` (§6.1 read-only roles);
`docs/constraints/README.md` (C-48 narrowed); ADR-054/059's "read-only
worktree" wording.

## Context

The phase 4 probe (`hobbes bench run --stages plan` on astropy-13398)
produced `seed_source: lexical-fallback` with a 1-second planner stage
and no tokens: the session died before the model ran. The benchmark
environment binding (ADR-058, C-43) runs a pre-command that copies
`/testbed`'s untracked build artifacts into `/work` — and a `planner`'s
`/work` was mounted `ro`, so `tar` failed and the pre failed the
session. The same would kill every `verifier` (and pytest's own cache
writes would fail on any test that runs), so the two stages the
restructure exists for could never have run in the environment both
arms are bound to.

The `ro` mount was chosen (M8, ADR-054) because §5.2 puts the OS
sandbox first among the enforcement tiers: a reviewer's inability to
change the tree must be a mount flag, not a policy an agent can argue
with. What the flag promises is **nothing the role does reaches the
tree**. It does not need to promise that the role cannot write at all
— and that extra promise is what broke the role's job.

## Decision

`ReadOnlyRoles` (`planner`, `reviewer`, `verifier`) mount the worktree
as a podman **overlay** (`-v host:/work:O`): the container sees a
writable view, every write lands in a throwaway upper layer, and the
host worktree is never touched. Podman rejects `O,z`, so the spec
carries no SELinux relabel (verified on the Enforcing dev box: the
overlay is readable and writable in-container, the host dir unchanged
after the container exits, and the real swebench pre-command extracts
the artifacts under it).

Everything else about a read-only role is unchanged: no Edit/Write/exec
in the tool list, `git commit`/`git add` denied in the role policy, the
harvest reads host-side commits only (an overlay commit cannot reach
it), bytecode writes off.

## Consequences

- The planner and verifier can do their jobs in the benchmark image.
  The `verifier-env` classification (EROFS) stays as the defensive path.
- **C-48 narrows:** the verifier can now write a scratch repro; what it
  wrote is discarded with the session and only the handoff survives.
- `WorktreeMode()` returns `O` for read-only roles; the Go tests assert
  the overlay spec and the absence of `rw`/`O,z`. `hobbes-session`
  rebuilt. The previous `ro` wording in ADR-054/059 reads as "overlay"
  from here on.
- A residual: overlay requires podman's overlay support in the user
  namespace (native on this kernel; older boxes need fuse-overlayfs).
  A box without it fails the session loudly at mount, not silently.
