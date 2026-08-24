# ADR 003: `hobbes-policy resolve` CLI contract and Python integration

Date: 2026-08-10
Status: accepted

## Context

The build plan (M0) requires the Go policy engine to be the *only*
implementation of deny-overrides-allow, consumed by both the Python CLI
(shell-out) and later the M4 daemon (import). The shell-out boundary needs a
stable contract.

## Decision

**Invocation.**

```
hobbes-policy resolve [--repo DIR] [--dir DIR] [--box FILE] <command>...
```

- Trailing arguments are joined with single spaces into the command string.
- `--dir` (default `.`) is the directory context the command runs in; it
  selects which `folder.policy` files apply.
- `--repo` defaults to auto-detection: walk up from `--dir` looking for a
  `.git` entry. Explicit flag wins; no repo found and no flag is an error.
- `--box` defaults to `~/.hobbes/box.policy`, skipped silently if absent. An
  *explicitly passed* `--box` that doesn't exist is an error (an explicit
  path is an intent; silently ignoring it would weaken enforcement).

**Output.** JSON on stdout (indented, stable field names):

```json
{
  "command": "git push --force origin main",
  "decision": "deny",
  "default": false,
  "rule": {"pattern": "git push --force*", "decision": "deny",
            "reason": "...", "scope": "box", "source": "/home/x/.hobbes/box.policy"},
  "matches": [ /* every matching rule, least → most specific */ ]
}
```

When no rule matched, `default` is true, `rule` is omitted, and
`default_source` names the policy file whose `default:` applied (omitted when
the engine fallback fired).

**Exit codes.** `0` allow · `10` deny · `20` escalate · `1` runtime error ·
`2` usage error. Decisions are exit codes so shell callers can gate directly
(`hobbes-policy resolve ... && run-it`); 10/20 stay clear of the small codes
tools conventionally emit.

**Python side.** `hobbes.policy` finds the binary via `$HOBBES_POLICY_BIN`,
else `hobbes-policy` on `$PATH`, and raises with build instructions if
neither resolves. `hobbes policy resolve "<command>"` (single quoted string —
avoids argparse eating flags like `-rf`) passes through, prints the JSON, and
propagates the exit code.

## Alternatives considered

- **Always exit 0, decision only in JSON** — loses shell composability and
  makes the Python wrapper parse JSON even when it only needs the tier.
- **gRPC / long-lived daemon / cgo FFI** — heavyweight for M0; the daemon
  arrives at M4 and will import the package directly instead.
- **Reimplementing the merge in Python** — explicitly ruled out by the build
  plan: one implementation everywhere.

## Consequences

- The JSON shape and exit codes are frozen; M4 may add fields but not rename
  or repurpose existing ones.
- Auto-detection keyed on `.git` means resolving outside a git repo requires
  an explicit `--repo`.
