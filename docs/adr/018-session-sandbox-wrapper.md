# ADR 018: Session wrapper and Podman rootless sandbox

Date: 2026-08-11
Status: accepted

## Context

M4's last piece (architecture §5.2 tier 1, §6; D2): launch an agent
session inside an OS sandbox on a fresh worktree, with the merged policy
mapped to mounts and the tool proxy the only path to a shell. "Session =
task, spawned into a fresh git worktree + sandbox" (§6); "policy paths map
to mounts, network policy to container network config" (D2); "secrets never
enter the session environment" (§5.2).

## Decision

**`hobbes-session start --repo DIR --role ROLE --task "..."`** builds and
runs a rootless `podman run`. The plan (`internal/sandbox`) is the testable
core; the command is a thin CLI over it, with `--dry-run` printing the exact
podman argv and MCP config.

**A self-contained clone, not a linked worktree.** The wrapper runs
`git clone --local <repo> ~/.hobbes/sessions/<id>/worktree` and checks out
a session branch there, then mounts *that* at `/work` rw. A linked worktree
(`git worktree add`) keeps its `.git` as a pointer into the canonical repo's
gitdir — which the container deliberately does not mount, so git would break
inside the sandbox and the only fix would be mounting the canonical `.git`
(exactly the coupling we forbid). `--local` hardlinks the object store, so
the clone is cheap yet needs no path outside `/work`; git works in the
sandbox and the canonical repo is unreachable from the container. Parallel
sessions never share a tree (§6), and the session branch lives only in the
clone — the canonical repo never grows one. Derived artifacts are gitignored
(ADR-012), so the wrapper copies the box's current ingest into the clone's
`.hobbes/derived/` to seed the knowledge tools (ADR-017).

**Mounts are the policy surface (D2).**
- session worktree → `/work` rw (the agent's writable world)
- `~/.hobbes/sessions` → `/sessions` rw (proxy writes
  `/sessions/<id>/flight.jsonl` and `escalations/`, so the box-side
  recorder and the host `escalations` CLI see them live)
- the `hobbes-proxy` static binary → `/usr/local/bin` ro
- box policy, if present → `/policy/box.policy` ro
Nothing else is mounted: prohibited paths are absent, not merely
unreadable — the strongest form of §5.2's "prohibited paths not mounted".
Every bind mount carries the `z` SELinux relabel, which rootless podman on
an enforcing Fedora host (D2) requires to access it.

**Clean environment (§5.2).** Rootless podman passes *no* host env by
default; the wrapper adds only `HOME=/sessions/<id>` and a fixed `PATH`.
Repo/infra secrets (AWS keys, tokens) are simply never there — provably, by
running `env` in the session. Per-command secret brokering (the
ajax-manager pattern) layers onto the proxy later without changing this;
v1's guarantee is the empty baseline. The session's *own* Claude credential
is the one thing a live agent needs; `--claude-cred` mounts `~/.claude` ro
when launching real Claude Code, and is off by default.

**Two enforcement layers, as designed.** The proxy (tier 2) is the load
bearing gate; Claude Code's native permissions (tier 3, §5.2) are set to
`--disallowedTools Bash` so the agent *cannot* get a raw shell and must call
the policy-checked `hobbes` `exec` tool. Edit/Write on `/work` stay allowed
— the worktree is the sandbox boundary, and an implementer has rw there (§6).

**Network off by default.** `--network none`; `--network` overrides. The
allowlist-proxy egress model (§5.2) is a later refinement; denying egress
outright is the safe v1 default.

**The exit-check implementer was scripted, deliberately.** M4's exit needs
"an implementer session completes a small task." A live Claude Code session
spends subscription quota, and M4 is the project's quota-free half
(sequencing rule 1). So the exit check runs a scripted MCP client *inside
the sandbox* in Claude Code's place — same transport, same tools, same
proxy — proving the sandbox mechanics (task done via `exec`, prohibited
command refused+logged, escalation parked→approved→ran, env clean) without
burning quota. The wrapper's default target is real Claude Code; a live run
is one command away when Max wants to spend the quota.

## Alternatives considered

- **bubblewrap instead of podman** — §5.2 lists it as an alternative, but
  D2 locked Podman rootless; images give a reproducible toolchain that
  bwrap's host-fs sharing doesn't.
- **Mounting the repo directly** — breaks the parallel-sessions and
  disposable-worktree guarantees; a bad edit could touch the canonical tree.
- **A linked `git worktree` (the build plan's word)** — cheaper than a
  clone, but its `.git` points into the canonical gitdir, which can't be
  mounted without coupling the container to the real repo. `--local` clone
  gets the isolation the milestone actually wants.
- **Baking Claude Code into the image** — pins a version and bloats the
  image; mounting the host install keeps the agent runtime host-managed.
- **`--env-host` for convenience** — would pour every host secret into the
  session, the exact thing §5.2 forbids.

## Consequences

- One rootless container per session, no daemon, no root; teardown removes
  the worktree (`git worktree remove`).
- The image is small (`sandbox/Containerfile`): a base plus git, python3,
  and the proxy binary; the agent runtime mounts in.
- `hobbes-session --dry-run` is the whole design, inspectable as text: the
  podman argv and the MCP config the agent will get.
- "No secrets in the session environment" is not a claim but a default:
  the env is two variables.
