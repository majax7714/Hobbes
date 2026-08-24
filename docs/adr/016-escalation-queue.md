# ADR 016: File-based escalation queue with a blocking park

Date: 2026-08-11
Status: accepted

## Context

Architecture §9 fixes the escalation tier's behavior: an escalated
command parks, is approved or denied by a human (CLI first, Sessions tab
at M7), **expires to deny** after a default 30 minutes, and approvals
log the approver and are replayable. It does not say how the queue is
represented, how the parked session waits, or how the approver's
decision reaches the proxy.

## Decision

**Queue = files.** Each escalation is one JSON record at
`~/.hobbes/sessions/<session>/escalations/<id>.json`
(id `E-<utc-timestamp>-<4 hex>`), carrying the exact command, dir, repo,
decisive rule and reason, session identity, requested/expires
timestamps, status (`pending | approved | denied | expired`), resolver
identity, and resolution time. All writes are atomic
(temp-file + rename). ADR-014 already made `~/.hobbes/sessions/` the
audit root both the CLI and the M7 Sessions tab read; the queue lives
in it.

**Parking blocks the exec call.** The proxy writes the pending record
and a park line to the flight log, then polls the record (200ms) until
resolution or deadline. §9 allows the session to "continue other work
or idle" — blocking is the idle option, and it is what lets an
*approved command run inside the original tool call*, keeping approval
end-to-end in one exchange. While parked, the proxy sends MCP progress
notifications (~10s apart, when the client supplied a progress token)
so client-side tool timeouts don't kill a legitimately parked call.
Non-blocking parking (park-and-poll tools for the agent) is a future
refinement if real sessions show idling hurts.

**The proxy's clock is the expiry authority.** Past the deadline the
proxy marks the record expired and refuses, even if an approval was
written moments too late; the CLI equally refuses to approve a
pending-but-past-deadline record and marks it expired instead. One
authority, no approved-but-never-ran ambiguity. A client disconnect
while parked also marks the record expired — nothing dangles pending.

**The flight schema gains one optional field.** §9's "approvals log the
approver" cannot be satisfied by the ADR-015 field set, so this ADR
widens it: an optional `escalation` object. The park line carries
`{"id"}`; the resolution line carries
`{"id", "resolution": approved|denied|expired, "approver"}` (approver
empty on expiry). Policy fields stay the policy truth — `decision`
remains `escalate` on both lines; the human's verdict lives in the
escalation object, and `exit` is set only when an approved command ran.
Replayability = record + both lines carry everything needed to re-run
and to audit who allowed what, when.

**The CLI lives in the Go binary**: `hobbes-proxy escalations
list | approve <id> | deny <id>`, resolver identity from the invoking
OS user. The Python `hobbes` CLI gets no passthrough for now — M7 moves
approve/deny into the UI, and a second human surface today is
speculative.

## Alternatives considered

- **Socket/RPC between CLI and proxy** — a live channel to a process
  that might have died parked. Files survive proxy death, are
  inspectable with `cat`, and the M7 tab reads them with no daemon.
- **Return "parked" immediately and let the agent poll** — matches
  "continues other work", but the approved command then runs only if
  the agent remembers to ask again, and the M4 exit bar ("parks, gets
  approved from the CLI, and runs") acquires a third party. Deferred.
- **Logging approval as `decision: "allow"`** — falsifies the policy
  record; the policy said escalate. The human verdict is a separate
  fact and gets a separate field.
- **fsnotify instead of polling** — a dependency to save 200ms of
  latency on a human-timescale (minutes) queue.

## Consequences

- `hobbes-proxy escalations list` is the whole queue UI until M7; a
  record is one readable JSON file, and a dead-proxy leftover shows as
  expired by timestamp rather than pending forever.
- Every escalation produces exactly two flight lines (park,
  resolution), joinable on `escalation.id`.
- Chunk 1's park-as-error stub is gone; `--escalation-timeout`
  (default 30m, §9) bounds every park.
