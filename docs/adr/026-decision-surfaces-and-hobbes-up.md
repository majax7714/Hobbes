# ADR 026: Two decision surfaces, and `hobbes up`

Date: 2026-08-11
Status: accepted

Amends ADR-019 (promotion is physical) and ADR-022 (the surface is
read-only).

## Context

M0–M8 built the v1 machinery, but bringing it up on a repo is eight
manual steps (`docs/first-run.md`), and two of them ask for judgement in
a way the tool doesn't collect: policy is a YAML file you hand-edit, and
invariant promotion is a file you move by hand.

Max's framing, and the thing this ADR encodes: **exactly two things need
a human — intent and invariants. Everything else is a natural part of
the mechanism and is expected.** Collapse the bring-up to one command,
put those two decisions in the UI, and make anything *new* arrive with
the escalation treatment the proxy already gives a parked command:
approve, deny, or edit.

## Decision

### One entry point

`hobbes up` performs the mechanical steps, then holds until the human
decisions are made:

1. Ensure the repo is a git repo and `.hobbes/` exists (init if not).
2. Compare the artifacts' stamped SHA — **the commit Hobbes was last
   linked to** — against HEAD, and re-ingest when they differ or are
   missing. Ingest is free and deterministic, so this is unconditional.
3. Start the web surface and wait.
4. **Block until the decision queue is empty**, reporting what remains.
5. Announce the session is ready, and keep serving.

**It never narrates.** Narration spends quota, and the sequencing rule
is that you check the graph is true before paying for prose about it. It
is offered in the UI with its call count, not performed by a script the
user ran to get started.

### Intent is the policy file, edited through the UI

"Intent" is the UI's name for `.hobbes/policies/repo.policy` — not a new
layer that compiles down to it. One source of truth, one implementation
of `deny`-overrides-`allow` (the Go engine), and `hobbes policy resolve`
remains the way to check what the UI wrote. The panel writes real YAML
and **shows the diff before applying it**: if the point is that review
stays on the human's side, then seeing exactly what lands in the file is
the review.

`default: escalate` is present from `init` and stays in force until
intent is adjusted. An unreviewed policy is a *pending decision*, not a
silently-accepted one — the first run blocks on confirming it, because
"I never looked at the policy" and "I read it and it's fine" must not
look alike.

### Invariants are decided, and decisions persist

Every inferred invariant is **approve / deny / edit**. A decision holds
until manually changed; only *new* invariants interrupt again.

**Decision identity is a content hash, not an id.** Inferred ids are
positional — `schema.py` assigns `INF-n` by enumeration over whatever
order the model returned — so `INF-3` names a different statement after
the next narration. Keying decisions by id would let an old approval
silently bless unrelated new text, which is the exact failure the gate
exists to prevent. The key is a hash of the normalized `(statement,
scope)`, so any material rewording re-escalates and an immaterial
reformatting does not.

**Denials persist.** Re-narration will re-infer something rejected;
without a remembered denial it asks again every run, and a gate that
asks the same question forever teaches you to click through it.

The ledger lives at `.hobbes/decisions.yaml` — human judgement, so it
sits beside `policies/` and `invariants/` rather than in `derived/`.

### What this changes in ADR-019 and ADR-022

- **ADR-019** made confirmation physical — "Max moving the record,
  nothing less" — so that inert-until-confirmed could not decay into a
  status flag. That rationale survives: approving in the UI still
  **writes a real record into `.hobbes/invariants/`**, reviewable as a
  file and diffable like any other. What changes is only what triggers
  the write. Nothing promotes a record without an explicit human verdict
  on that exact text.
- **ADR-022** made the surface read-only except escalation verdicts, and
  justified enforcing loopback on the grounds that it can approve
  commands. It can now also author policy, which raises the stakes on
  the same boundary rather than changing its shape: the bind check and
  the `Host` check are unchanged and now matter more. Writes remain
  confined to three things — escalation verdicts, the policy file, and
  invariant records — and each writes a file a human can read.

## Alternatives considered

- **Intent as a higher-level layer compiling to policy** — more
  expressive to author, but adds a second artifact, a compiler, and a
  place where compiled rules drift from stated intent. The policy format
  is already the intent; it just had no editor.
- **Keying decisions by invariant id** — simpler, and wrong: ids are
  positional and reused.
- **Non-blocking bring-up** (undecided items stay inert, session starts
  anyway) — gentler on a large first run, and rejected by Max: the point
  of the gate is that the decisions are made, and a queue you can walk
  past is a queue you never empty.
- **Auto-narrating on first run** — a populated UI immediately, at the
  cost of spending quota before the graph has been checked.

## Consequences

- Bring-up is `cd` + one command, and the only thing it asks of a human
  is the two things only a human can answer.
- The decision ledger makes "what is new since I last looked" precise
  rather than heuristic, for invariants and for the artifacts' SHA
  alike.
- Blocking means a first run on a large repo presents its whole queue at
  once. The UI's job is to make that queue fast to walk — bulk actions
  and keyboard verdicts — rather than to shrink it.
- Decisions are untracked in target repos (ADR-012), so they do not
  survive a fresh clone. Recorded as a known limitation in
  `future_additions.md`; opting `policies/` and `invariants/` into git
  per repo is the fix when it starts to hurt.
