# ADR-075 — A compound shell command is resolved per segment

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-001 (glob
matching), ADR-002 (resolution order). **Surfaces:** C-54.

## Context

The policy engine matched a command as one anchored-glob string (ADR-001:
`*` swallows any run, the match anchored at both ends). That is right for a
single command, but a session's `exec` runs whatever shell string the model
wrote, and a capable model writes compound ones. The `five-fresh-27b`
benchmark run (the first on the thinking rung, ADR-074) made the cost
concrete: **104 of 253 exec calls escalated**, and the top offenders were
`cd /work && python -m pytest …`, `git -C /work status && git -C /work
branch`, and `PYTHONDONTWRITEBYTECODE=1 python -m pytest …`. None matched
the box policy's anchored allow rules — a `cd`/env prefix or a second
chained command put the allowed part where the anchor could not see it — so
all fell to the box floor's `default: escalate`, which on a benchmark
expire-denies in 5 s with no approver. The harness arm was starved:
implementers could not run their own tests, all three verifiers reported
"nothing could be executed", and some units could not commit. The harness
arm scored 20 % against the pure arm's 40 % on the same model — not a model
result, a harness one (the resolve-harness-first rule, session-handoff).

The old behaviour was also unsafe in the other direction: because a
trailing `*` swallowed everything after the head, `git status && rm -rf /`
matched `git status*` and **ran the `rm`**. The single-string match never
saw the second command at all.

## Decision

`Chain.ResolveCommand` is the compound-aware entry the proxy and the
`hobbes-policy` CLI now call (the per-command `Resolve` is unchanged and
still used within it):

1. Split the command on top-level `&&`, `||`, `;`, and `|`, honouring
   single and double quotes and backslash escapes so an operator inside a
   string is not a separator. An unbalanced quote (an unparseable command)
   falls back to one segment — resolving exactly as the raw string did, so
   ambiguity never loosens a decision.
2. Strip a leading `cd <dir>` segment and `VAR=value` assignment prefixes:
   a bare `cd`/assignment runs nothing the policy governs (neutral), and a
   real command carrying an env prefix is matched as the command under it.
3. Resolve each non-neutral segment on its own and combine
   **most-restrictive-wins: deny > escalate > allow**. A command is as
   permitted as its least-permitted part. The decisive segment's rule is
   what the recorder labels; the reported `Command` is the whole
   normalized command.

This preserves deny-overrides across the whole command (a `git push` or
`*.tfstate` anywhere in a chain still denies) and closes the `rm` hole,
while letting a `cd`-prefixed or chained allowed command run.

The benchmark box policy (`bench.box.policy`) is broadened to name the
common read-only text filters a model pipes test output through (`tr`,
`awk`, `wc`, `sort`, `uniq`, `cut`, `xargs`, `tee`, `diff`, `echo`, `true`
— `grep`, `sed -n`, `head`, `tail`, `cat` were already there): now that a
pipe target is policy-checked, an allowed `pytest … | tr …` would otherwise
escalate on the filter. These are harmless inside the already-sealed OS
sandbox (§5.2 is the real boundary).

## Consequences

- P10 holds: a general mechanism (compound splitting) cannot absorb a
  specific guarantee — deny is checked on every segment and wins, so the
  broad convenience never overrides a narrow refusal. The split direction
  is fail-safe: an unparseable command, or a segment matching no rule,
  escalates rather than runs.
- A repo policy that relied on the old `*`-swallow for a chained command
  must add the chained segment's own rule; the flight log and
  `hobbes policy resolve "<compound>"` show the per-segment decision.
- Not re-run: `five-fresh-27b` is void as a model verdict (C-54). The
  re-run on this fix is Max's go; the 27B rung's read waits on a run whose
  harness arm can actually execute.
- Tests: `TestResolveCommandCompound` (cd/env prefixes, chained allows,
  pipes, deny-anywhere, unknown-segment escalation), `TestSplitTopLevel`
  (quotes, escapes, each operator, unbalanced → not ok),
  `TestStripEnvAssignments`. The proxy's `TestOutputTruncatedAtCap` (a
  `head … | tr …` pipe) gains a `tr` allow — the pipe target is now
  checked.

## What this does not fix

Some sessions also hit `fork/exec /bin/sh: no such file or directory` on a
minority of exec calls — a separate, secondary defect (a few of the run's
253 calls), left for its own read rather than folded in here.
