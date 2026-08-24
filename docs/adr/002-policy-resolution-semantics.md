# ADR 002: Policy resolution semantics — tie-breaks and defaults

Date: 2026-08-10
Status: accepted

## Context

Architecture §5.1 fixes the headline semantics: layered scopes
(box → repo → folder), most-specific wins, deny overrides allow, and a
three-tier decision (`allow | deny | escalate`). It leaves open how those two
principles interact, what happens on ties, and what an unmatched command
resolves to.

## Decision

Resolution of a command against the merged chain (box, then repo, then each
`folder.policy` from the repo root down to the working directory — deeper is
more specific):

1. **Deny wins from any scope.** If any matching rule in any scope says
   `deny`, the result is deny. This is what makes the box policy a *floor*:
   a folder `allow` can never override a box `deny`. The reported decisive
   rule is the most specific denying one.
2. **Otherwise, the most specific scope with any matching rule decides**
   (folder over repo over box — "shadowing"). A folder `allow` shadows a repo
   `escalate`; a repo `allow` shadows a box `escalate`. Escalate is
   deliberately shadowable — only `deny` is un-overridable, per §5.1.
3. **Within that scope, escalate beats allow** (conservative tie-break when
   multiple rules in one file match); among equal decisions, first match in
   file order is reported.
4. **No match anywhere → the `default:` of the most specific policy file
   that sets one; engine fallback is `escalate`.** Escalate is the designed
   fail-safe middle tier: it surfaces the unknown command to a human rather
   than silently allowing it, and the escalation flow itself expires to deny
   (§9), so the fallback is safe without being a dead end.

Commands are normalized before matching (trim, collapse whitespace runs) so
`git  push` can't dodge a `git push*` rule. String-level matching is a v1
boundary: robust argv-level matching (quoting, env-var prefixes, `sh -c`
wrappers) is the M4 tool proxy's job, where the proxy receives structured
argv rather than a flat string.

## Alternatives considered

- **Strict most-specific-wins including deny** — breaks the box floor; §5.1's
  "never allow" examples (credential exfil, force-push to main) require
  un-overridable denies.
- **Escalate un-shadowable like deny** — not what the docs say, and it would
  make escalate a second deny tier instead of the middle tier; a repo that
  wants a hard gate should say `deny`.
- **Fallback `allow` for unmatched commands** — unsafe default for an
  enforcement layer.
- **Fallback `deny`** — dead-ends every unanticipated command; escalate keeps
  the human in the loop and still decays to deny on timeout.

## Consequences

- Policy authors get one simple guarantee to reason about: *only deny is
  absolute; everything else can be refined closer to the code.*
- The engine is deterministic given (chain, command) — no rule-ordering
  surprises across files.
- The M0 test battery encodes exactly these rules (shadowing, deny-wins,
  folder-over-repo-over-box, escalate tier, defaults) and becomes the
  regression contract the M4 daemon inherits.
