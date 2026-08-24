# ADR 015: Flight recorder schema and the exec tool contract

Date: 2026-08-10
Status: accepted

## Context

Architecture §9 fixes the recorder line —
`{ts, session, role, tool, argv, policy_rule, decision, exit, sha}` —
and §5.2 fixes the proxy's job (match merged policy, execute or refuse or
escalate, log everything). The field semantics and the exec tool's exact
behavior are unspecified.

## Decision

**Recorder.** Exactly the §9 fields, no additions. `ts` is RFC3339Nano
UTC. `argv` is the literal execve argv — `["/bin/sh", "-c", <command>]` —
that ran, or for a refusal, would have run: the audit trail records what
the machine was asked to do, not a prettified echo. `policy_rule` is
`<source>: <pattern>` of the decisive rule, or `default:<source>` /
`default:engine` when no rule matched. `exit` is the process exit code,
`null` when nothing ran (deny, escalate, spawn failure); a timed-out
process logs the `-1` Go reports for a kill. `sha` is the repo HEAD
re-read per event — implementer sessions commit mid-session, and each
event should pin the HEAD it actually ran against. The writer opens
`O_APPEND`, writes one marshaled line per event, and fsyncs each — the
recorder never reads, rewrites, or truncates.

**Exec.** One tool, `exec`: input `{command, dir?}` where `dir` is
relative to the repo root and confined to it (escapes are a proxy error,
not a policy question). Each call loads the chain fresh via
`policy.LoadChain(box, repo, dir)` — folder policies depend on `dir`, and
load cost is microseconds. Then:

- **allow** — run `/bin/sh -c <command>` in `dir`, kill after `--timeout`
  (default 10m). Result: exit code, stdout, stderr (each stream truncated
  to 50 KiB with a marker — a runaway `cat` must not flood the agent's
  context). `isError` is set for any nonzero exit so failure is prominent.
- **deny** — nothing runs. `isError` result naming the decisive rule and
  its reason.
- **escalate** — chunk-1 stub: nothing runs, `isError` result saying the
  command is parked pending human approval and that the queue lands in
  chunk 2. The recorder line (`decision: "escalate"`) is already final;
  chunk 2 changes what the proxy *does*, not what it logs.

Running through `sh -c` is deliberate: agents legitimately need pipes and
redirects, policy globs match the raw command string (ADR-002), and the
shell is not a trust boundary here — the sandbox and policy chain are.
The proxy's own environment passes through to children in chunk 1;
env scrubbing and per-command secret brokering arrive with the sandbox
(chunk 3), which is what M4's "no secrets in the session environment"
exit criterion tests.

## Alternatives considered

- **Richer event schema (duration, cwd, output samples)** — the §9 schema
  is the spec; widening it is a doc change first, not a code liberty.
  Output capture especially would bloat an append-only audit log with
  data the MCP result already carried.
- **argv as the raw command string** — loses the field's meaning; the
  name promises the vector that hit execve.
- **Structured MCP output for exec** — text content with an exit banner
  is what agents parse fine today; schema for it is speculative.

## Consequences

- The JSONL is greppable audit truth: every decision the proxy ever made,
  with the rule that made it, survives session and worktree teardown.
- Policy changes mid-session take effect on the next call — chain-per-call
  means no restart to pick up an edited folder policy.
- The 50 KiB truncation is per stream, marked in-band, and the full
  output is never stored anywhere — rerun with a filter if it matters.
