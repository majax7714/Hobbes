# The dispatch harness (ADR-107, ADR-112) — `hobbes dispatch`, the session and its records

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

**A segment of its own since 2026-09-14 (Max).** The dispatch harness is
the layer's live session route — a task to Claude Code in
`hobbes-session` beside its sidecar and behind the egress allowlist,
the diff gated and verified, one log file per session — not an
experiment record, so its concessions sit where a person running
`hobbes dispatch` looks. The five entries moved here from the
verification segment with their numbers and text unchanged. What a
dispatched *diff* concedes at the gate stays in
[`derivation-plan-mapping.md`](derivation-plan-mapping.md) (C-121–C-123,
C-126); what any live session concedes on its network and credential is
C-41, and the keyed rounds' session entries (C-103, C-124) stay in
[`verification-benchmark-harness.md`](verification-benchmark-harness.md).

### C-125 — A dispatched doer's file reads are not in the flight log (its edits are, by path alone)

- **Cannot tell you:** from the flight log alone, what a Claude Code
  doer read, or what an edit changed. Only `exec` passes the policy
  proxy. Claude Code's native Read, Edit and Write act on `/work`
  directly.
  - **Narrowed 2026-09-12 (0.2.6-beta, ADR-107's progress hook):** every
    Edit, Write, MultiEdit and NotebookEdit is a flight line with its
    time, tool and path, never its content. A PostToolUse hook runs
    `hobbes-proxy record-edit`. So "what did the doer touch, and when"
    is answered. What it read, and the content of an edit outside the
    harvested diff, are not.
- **Because:** they are the doer's own tools, granted by the session's
  `--allowedTools`. Bash is withheld, so the shell goes through `exec`,
  but the file tools are Claude Code's. The mounts still bound them:
  the worktree is the one writable tree, and the policy files, the
  derived layer and the dependency trees are read-only.
- **Bites at:**
  - an audit that asks, from `flight.jsonl` alone, whether the doer
    read X before changing Y;
  - a write the repo policy would have refused had it come through
    `exec`.
- **You find out:** **partial**.
  - Every write is in the harvested diff, which the gate reads.
  - **Amended 2026-09-12 (ADR-107's retention amendment):** the
    doer's transcript is not kept. Claude Code runs with
    `--no-session-persistence`, and its state is removed at exit, so
    its reads are recorded nowhere. This is chosen: the doer's
    reasoning is never stored.
- **Related:** C-140 — the flight log that does record the edits was
  within the doer's reach until ADR-112; what is left there is a forged
  edit line.
- **Source:** ADR-107, 2026-09-12.

### C-127 — The harness is validated by the developer's reading of each session, not by an answer key

- **Cannot tell you:** that a gate verdict recorded under
  `docs/calvin/sessions/` is right.
  - A `right-clear` is the developer's reading of the diff.
  - A `missed` exists only once someone finds the error.
- **Because:** real work has no gold. The keyed rounds had keys only
  for past commits, and the keys leaked (D-x).
- **Bites at:** any claim drawn from the logs. A count of
  `right-clear` rows counts reviews that found nothing, not diffs with
  nothing wrong.
- **You find out:** **surfaced**. Every session file's review block
  names its grader and vocabulary, and `calvin-harness.md` §4 scopes
  the claim to the sessions run (P11).
- **Source:** ADR-107; Max, 2026-09-12.

### C-128 — A dispatch is not reproducible from its inputs

- **Cannot tell you:** what the same task would produce if dispatched
  again.
  - The doer is a sampled model.
  - Its binary is whatever Claude Code the host has installed.
    Auto-update is off inside the session, not on the host.
- **Because:** the doer is the one generative part of the stack
  (charter §8). The layer under it stays deterministic: the gate's
  record over the same diff is byte-identical on rerun.
- **Bites at:** comparing two sessions; re-running a session to check a
  finding.
- **You find out:** **surfaced**. The session file records the doer's
  version, model and turns, and the gate record hashes every input.
- **Source:** ADR-107, 2026-09-12.

### C-129 — The training guard keeps the session rows and the doer's commits out, not the merged tree

- **Cannot tell you:** that no model is ever trained on a doer's output.
  - The guard makes the recorded sessions and the doer's own commits
    unreachable as training units. `ttt.units.units_from_git` skips
    every commit the dispatch identity authored and every path under
    `docs/calvin/sessions/`.
  - Once a doer's commit is merged, its code is part of the repo. Any
    corpus rendered from the tree at a later SHA (`hobbes
    derive-corpus`'s graph and module pages) contains it.
- **Because:** the tree is the repo. Hobbes renders what is there, and a
  line carries no author once it is in the tree.
- **Bites at:**
  - a TTT corpus built at a SHA after a merge;
  - a squashed doer commit, whose authorship the guard can no longer
    see.
- **You find out:** **surfaced**. `calvin-harness.md`'s retention
  section and `units_from_git`'s docstring state the reach, and "merge,
  never squash" is in the procedure.
- **Source:** ADR-107's retention amendment; Max, 2026-09-12.

### C-140 — A dispatched doer can forge an edit line in its own flight log (it could alter or delete its own session's records until 0.2.14-beta)

- **Cannot tell you:** that an *edit* line in a session's flight log
  was written by the progress hook rather than by a shell the doer ran.
  - **Narrowed 2026-09-14 (0.2.14-beta, ADR-112).** The flight log, the
    escalation queue, the mail file and the egress log are written by
    the session's sidecar container, over one flight stream the proxy
    opens once; the doer's HOME is a tmpfs and no part of the session
    dir is mounted read-write. A second stream is refused and the
    refusal recorded; a doer that kills its proxy closes the stream,
    which the sidecar records, and loses its shell with the proxy. So
    nothing the doer does can delete, rewrite or reorder a record, or
    forge an exec decision.
  - **What is left.** The hook's endpoint accepts an edit line from any
    connection, so a shell `exec` spawns in the doer's container can
    send one, naming a file it did not edit. The sink strips it to the
    tool and the path, so it cannot look like an exec decision, and the
    harvested diff is the truth for edits.
  - **Where it still applies in full:** a session on an explicit
    `--network` (the bench's pasta; the owned loop needs it for its
    transcript, ADR-064) keeps the session dir mounted read-write and
    the proxy's file journal in the doer's container. The dry run and
    the launcher say so in one line naming this entry.
- **Because:** the hook is a separate process the doer's tools start,
  once per edit, so its endpoint cannot be a single held connection the
  way the proxy's is. Before ADR-112, the recorder shared the doer's
  container (the policy proxy is the doer's MCP server over stdio,
  ADR-015), and Claude Code's own Write tool reached the same dir.
- **Bites at:** reading the edit lines' paths as a record of what the
  doer touched, where a doer had reason to lie about it. The exec
  decisions, escalations and egress refusals `calvin-harness.md` §4
  reads are complete from the sidecar's side.
- **You find out:** **surfaced**. The box headers and the harness doc's
  §2 table name the remainder; `hobbes dispatch`'s log reports the
  stream's bracket (opened, closed, any refusal) on its Policy line, so
  a stream that never opened or closed is visible in the session file.
- **Related:** C-125 — what the flight log never holds (the doer's
  reads).
- **Source:** ADR-107's 2026-09-13 amendment. It was found by tracing
  where `find … -delete` could reach from a dispatch box. Narrowed by
  ADR-112 (measured first: a socket cannot be reopened through
  `/proc/<pid>/fd`; a tmpfs dies with its container where a volume
  survives a forced removal).
