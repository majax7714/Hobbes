# ADR-036 — A specific safety guarantee outranks a general safety system (P10)

**Status:** accepted (2026-08-15)

**Context:** Max's call at the V2.M4 review. Adds principle **P10** to the
running architecture §1. Changes no code today; changes how safety
mechanisms may be written from here on.

## Context

V2.M4 shipped a general safety mechanism and it immediately ate a specific
one. Packs must degrade rather than fail an ingest (P6), so `run_packs`
wrapped every pack in `except Exception`. That handler swallowed
`PlanError` — the refusal that guards **I-1**, "Terraform state is never
read" — and `hobbes ingest --tf-plan prod.tfstate` stopped exiting 1 and
started *succeeding*, printing a warning beside the state file it had
declined to read.

Both mechanisms were correct in isolation. P6 says degrade visibly rather
than fail; I-1 says refuse absolutely. The bug was in what happened when
they met, and the general one won by default — not by decision, but because
`except Exception` is broader than any specific thing inside it. Nobody
chose to weaken I-1. The weakening was a side effect of a change in a
different subsystem, made for an unrelated and good reason.

Max, reviewing it:

> specific safety guarantees come before a general safety system. safety
> systems should be tiered by importance and coverage.

The shape generalises past this instance. Every broad mechanism this system
has — degrade-on-failure, catch-and-continue, escalate-by-default, one
corrective retry, expire-to-deny — is a policy about the *unknown* case. A
specific guarantee is a decision about a *known* one. When a broad policy
silently subsumes a narrow decision, the system loses the decision and keeps
the policy, which is exactly backwards: the narrow one was written because
someone thought about that case specifically.

## Decision

**P10 — A specific safety guarantee outranks a general safety system.**

A general mechanism must be written so that it **cannot** absorb a specific
guarantee. Not "should not" — the M4 near-miss proves that intent is not
enough, because the person widening the general mechanism is usually not
thinking about the specific one at all.

Rank by **importance × coverage**: the broader a mechanism's coverage, the
less it may decide on its own. A handler that wraps one call site may
reasonably swallow that call's errors. A handler that wraps *every pack*,
*every tool call*, or *every session* may not, because it cannot know what
it is standing in front of.

In practice this means:

1. **A broad handler names what it will not handle**, and re-raises it
   first. `run_packs` re-raises `PackRefusal` before its general `except`.
   The exemption is written at the general mechanism, not left implicit in
   the specific one.
2. **A refusal is a distinct type, not a return value or a log line.** A
   guarantee that travels as a message is one string-match from being lost.
3. **The specific guarantee keeps its own test**, at the level a user meets
   it. The test that caught this was written at M3 about `.tfstate` and the
   CLI's exit code — not about packs. It survived a refactor of code it
   knew nothing about *because* it asserted the user-visible guarantee
   rather than the implementation that provided it.

## Consequences

- **Applies immediately to the mechanisms that already exist.** The
  escalation queue's expire-to-deny, the narrative runner's corrective
  retry, the proxy's exec wrapper and the pack layer are all general
  mechanisms with specific guarantees inside their blast radius. None is
  known to be wrong today; M4's was not known to be wrong either, until a
  test failed.
- **V2.M5 is the first milestone written under it.** Adding a language means
  new general handling for a new indexer's failure modes, which is exactly
  the shape that ate I-1.
- **Hobbes should eventually catch this class of gap itself**, which is
  Max's ask and is parked in `future_additions.md` rather than built here.
  The natural home is V2.M6's unified checker: the question "does a broad
  handler enclose a path that must refuse?" is a graph question once
  refusals are a type, and `PackRefusal` makes them one. Worth stating what
  is *not* claimed — nothing in Hobbes detects this today, and it was found
  by a test written two milestones earlier.
- No `C-n` entry: this concedes no information about a user's repo. It is a
  rule about how this system's own safety code may be written.
