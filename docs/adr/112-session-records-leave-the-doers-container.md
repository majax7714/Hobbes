# ADR-112 — A session's records leave the doer's container: the sidecar owns the flight log, the egress log and the escalation queue

**Date:** 2026-09-13 · **Status:** accepted; the design, written before the dispatches that build it. Max chose this route over the two below and named the number: a constraint's fix is a patch, not a feature advancement, so the work lands as 0.2.14-beta on the 0.2.x line. · **Owner:** Max · **Source:** C-140 (`docs/constraints/verification-benchmark-harness.md`), registered by ADR-107's 2026-09-13 amendment

This amends the architecture's **§6.3** (the harness) and the session's
mounts wherever they are described (§7's proxy and sandbox row; ADR-107's
amendment; the box headers). It moves the *writer* ADR-015 and ADR-016
name — the recorder and the queue keep their formats — and it narrows
**C-140**.

## Context

C-140 says a dispatched doer can alter or delete its own session's
records. Traced in the code, the gap has three writers and one mount:

- The doer's HOME **is** the session dir. `hobbes-session` mounts host
  `<sessions>/<id>` read-write at `/sessions/<id>` and sets `HOME` to it
  (`sandbox.sessionHome`). Claude Code's own Write tool reaches it, and
  so does every shell `exec` spawns.
- The policy proxy runs **inside the doer's container**, as the doer's
  user, and writes `flight.jsonl` and `escalations/` there
  (`hobbes-proxy serve --log-dir /sessions`).
- The progress hook (`hobbes-proxy record-edit`) appends to the same
  file from the same container.
- The egress proxy already has a container of its own, but it writes
  `egress.jsonl` into that same host dir, which the doer's container
  mounts.

A side effect shows in every session dir: `go-build`, `.semgrep` and
`.config` land beside the records, because HOME is the session dir;
`dispatch.reasoning_left` had to special-case the Go build cache
(`SCAN_SKIP`), and `sandbox.PurgeDoerState` removes the doer's state
after the fact.

**Measured before the decision** (2026-09-13, no spend):

1. A container on a session's `--internal` network reaches a sidecar by
   name with no egress bridge attached, and has no route off the box
   (`getent` resolves the name, the sidecar answers, `1.1.1.1:443` is
   `ENETUNREACH`). ADR-097's shape, confirmed for this use.
2. Claude Code runs with HOME on a tmpfs and its MCP config and settings
   file on a read-only mount: behind the egress sidecar with a bad token
   it ends on the expected 401 in two seconds, `.claude.json` and
   `.claude/` land on the tmpfs, the proxy opens its log there, and a
   write into the read-only dir is refused.
3. An anonymous podman volume is removed with its container on a normal
   `--rm` exit, but **survives `podman rm -f`** — the path a killed
   dispatch takes. So the doer's HOME cannot be a volume: a tmpfs dies
   with its container on every path. Past sessions' Go build caches are
   about 150 MB; the box has 30 GB of RAM.
4. A TCP socket cannot be reopened through `/proc/<pid>/fd` (the kernel
   answers `ENXIO`), so a shell in the proxy's container cannot take
   over a connection the proxy holds. This is why one long-lived stream
   is a boundary and a shared file is not.

## Decision

**The records leave the doer's container. The executor stays.** A
session's flight log, egress log and escalation queue are written by one
sidecar container per session, and the doer's container mounts no part
of the session dir read-write.

1. **The sidecar.** `hobbes-proxy sidecar` replaces `hobbes-proxy
   egress`. `hobbes-session` runs it as `hobbes-side-<id>` on the
   session's internal network `hobbes-int-<id>`, mounting the session
   dir read-write at `/log`. It is the only writer of `flight.jsonl`,
   `escalations/` and `egress.jsonl`. With `--allow` hosts it also joins
   the `hobbes-egress` bridge and runs the CONNECT proxy as today; with
   none it sits on the internal network alone. The egress package is
   unchanged.
2. **The sink.** The sidecar listens on `SinkPort` 3129 for
   newline-delimited JSON, one request per line, one answer per request,
   in order:
   - `open` claims **the flight stream**. The sink accepts one, ever.
     It writes a `stream_opened` line when it accepts and a
     `stream_closed` line when that connection ends, and it answers any
     later `open` with an error, closes it, and writes a
     `stream_refused` line. An attempt to take the stream is itself
     recorded.
   - On the stream: `event` appends a flight line; `park` creates the
     escalation record; `poll` returns the record's current status;
     `expire` marks it expired. These are `recorder.Record`,
     `escalation.Create`, `Load` and `MarkExpired`, executed on the
     sidecar's side of the mount. The proxy's clock stays the expiry
     authority (ADR-016): it polls and it sends `expire`; the host-side
     `hobbes-proxy escalations approve|deny` writes the record in the
     same dir as today and the next `poll` sees it.
   - `edit`, on any connection, records one edit line and the sink
     closes the connection. The sink keeps the tool and the path alone,
     requires the tool to be `Edit`, `Write`, `MultiEdit` or
     `NotebookEdit`, and clears every other field, so nothing sent there
     can look like an exec decision.
   - The sink stamps `session` and `role` from its own configuration on
     every line it writes, never from the message. A flight line's `ts`
     is the proxy's, as today. The sink's own lines carry `tool:
     "sink"`, an empty `argv`, `policy_rule: "sink"` and the decision
     named above; ADR-015's field set is unchanged, and these are the
     three values added to `decision`.
   - The sink answers `{"ok":true}` or `{"ok":false,"error":…}`. A
     refused or failed write reaches the proxy, which surfaces it on the
     tool result as it does a recorder failure today: an unauditable
     proxy must not look healthy.
3. **The proxy.** `proxy.Config` takes a `Journal` — `Record(event)`,
   `Park(record)`, `Poll(id)`, `Expire(id, now)` — in place of `Rec` and
   the session dir. Two implementations: the **file journal**, which is
   today's recorder and queue on a local dir, kept for `--knowledge-only`
   (the host's knowledge server, ADR-087), for the tests, and for a
   session that runs on a `--network` override (item 5); and the **sink
   client**, one connection opened at `serve` start and held for the
   proxy's life. `hobbes-proxy serve --sink HOST:PORT` selects the
   client; `record-edit --sink HOST:PORT` sends its line the same way.
   The stdio MCP transport does not change, and neither does anything
   the doer sees.
4. **The doer's container.** HOME stays `/sessions/<id>` in name and
   becomes a tmpfs (`--tmpfs`, 4 GB cap). What the container must read
   from the host — `mcp.json`, `claude-settings.json`, and for the owned
   runtime `agent.py` and `brief.md`, and for the exit check its
   driver — is written host-side under `<sessions>/<id>/in/` and
   mounted read-only at `/sessions/<id>/in`. Nothing else of the session
   dir is mounted. Retention (ADR-107) then holds by construction: the
   doer's state dies with its container on every exit path, so
   `PurgeDoerState` and its test go, and `dispatch.SCAN_SKIP` loses
   `go-build` (the cache is on the tmpfs now). `GOCACHE` keeps its path.
5. **The network.** Every session gets `hobbes-int-<id>` and a sidecar by
   default; `--egress` adds the hosts to the sidecar's `--allow`. The
   default `--network none` is gone, because a session must reach its
   sidecar. An explicit `--network` (the bench's pasta path, a closed
   approach kept for the record) keeps the file journal in the doer's
   container, and the dry run and the launcher's stderr say so in one
   line naming C-140. `--network` and `--egress` stay exclusive.
6. **What `hobbes dispatch` reads** is the same three files in the same
   host dir. `summarize_flight` counts exec decisions and edits as
   before, leaves `tool: "sink"` lines out of those counts, and reports
   the stream bracket: opened, closed, and any refused. `_cleanup_route`
   removes `hobbes-side-<id>`.
7. **Tests, where a user meets the guarantee (P10):**
   - `internal/sink`: one stream ever, the refusal written; the edit
     shape enforced, an exec-shaped edit refused; park, poll, a
     host-side `escalation.Resolve`, and expire, round trip; session and
     role stamped from configuration.
   - `internal/proxy`: the existing exec, park and expiry tests pass
     over the sink client against an in-process sink on a loopback
     listener, as they pass over the file journal.
   - `internal/sandbox` and `hobbes-session`: the plan mounts `in/`
     read-only and the session dir nowhere else; the tmpfs is on the
     argv; the MCP config and the hook carry `--sink`; the sidecar's
     setup and teardown; the `--network` override's line.
   - **Live**, skipping without podman or the image: a session's command
     lists `/sessions/<id>` and finds `in` alone, tries to remove the
     flight log by its old path and cannot, opens the flight stream by
     hand and sends one event, then tries to open it again and is
     refused; after the session, the host flight log holds the event,
     the bracket and the refusal, in that order. The existing live
     mount test's expectation moves from "the session's own dir" to "its
     `in/` dir and nothing else".
8. **Register.** C-140 is narrowed, keeping its number. What remains,
   surfaced in the box headers and the harness doc: from a shell `exec`
   spawns in the doer's container, a **forged edit line** through the
   `edit` request, which the harvested diff contradicts (the diff is the
   truth for edits; the flight line is the clock). And a doer that kills
   its proxy closes the stream: the sink records that, and the doer
   loses its shell with the proxy. Nothing else is left: no deletion, no
   rewrite, no forged exec decision, no reach to the egress log or a
   record.
9. **Version:** 0.2.14-beta, a patch (Max). The image is rebuilt after
   (C-65).
10. **Built through the harness** (ADR-107), in two dispatched units,
    the second on the first's merge: **A**, the sink package, the
    sidecar subcommand, the journal and the sink client in the proxy
    and the hook; **B**, the launcher (mounts, tmpfs, network, the
    sidecar's lifecycle), the Python side (dispatch, the harness driver,
    the exit check) and the live tests. The docs, the register and the
    version are the developer's, in the release commit.

## Considered, not taken

- **The whole proxy in its own container** (the register's original
  wording). Exec's children would run in the proxy's container over the
  shared worktree, MCP would move from stdio to streamable HTTP, and the
  children would have to drop to a second uid to keep the logs out of
  their reach — which needs the worktree writable by that uid while the
  host-side harvest still reads it. It closes the forged-edit residual at
  two to three times the work. It stays available if that residual ever
  matters.
- **Detect, not prevent** (a hash chain over the log). A doer could
  still delete, and the rule is contain first (Max, 2026-09-13).
- **An anonymous volume for HOME.** Measured: it outlives `podman rm
  -f`.

## Consequences

- A session's records are complete from the sidecar's side: what the
  sink wrote is what the proxy sent, in order, with a recorded bracket.
  `calvin-harness.md` §4's "every refusal is read" reads a log the doer
  could not edit.
- One more container per session, one more port on the internal
  network, no new image content: the sidecar is the same static
  `hobbes-proxy` the session mounts.
- The dispatch box's header and `bench.box.policy`'s say what bounds a
  deletion: the clone, and a tmpfs that dies with the container.
- ADR-107's mount description, C-125's "the flight log that does record
  the edits is itself within the doer's reach" and the harness doc's §2
  table change in the release commit.
