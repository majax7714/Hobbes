# ADR-042 — The queue names the record a proposal restates

**Status:** accepted (2026-08-16)

**Scope:** the C-21 paydown. Amends **ADR-026** (the decision surfaces):
a pending inferred invariant now arrives with its nearest confirmed
record attached. Surfaces **C-21**; does not lift it.

## Context

Narration is told about the repo but not about `.hobbes/invariants/`, so
it re-proposes settled invariants in fresh words — and decisions key on
a content hash of (statement, scope), so a reword never matches. The
cost stopped being theoretical on 2026-08-15: promoting from the
inferred set produced **I-9**, whose wording carried the exact claim the
M8 promotion had corrected out of I-3 ("pushes escalate" — the policy
denies them outright). The queue was noisy in a recognisable way, but
recognising noise is not recognising that *this* reword reverses a
correction. The C-21 entry named the fix: the decision surface, showing
the neighbouring confirmed record.

## Decision

**The server computes it; the card shows it; no model is involved.**

- `pending()` loads the confirmed records (id, statement, status —
  a minimal local read; the queue needs prose to show, not rules to
  check) and attaches the best-overlapping one to each proposal as
  `nearest_confirmed: {id, statement, score}`.
- Similarity is **word-set Jaccard** over lowercased tokens of three
  letters or more. Deterministic on purpose (P5): the same pair scores
  the same forever, and the mechanism is explainable in one sentence.
- The threshold (0.2) is tuned on the observed failure and pinned by
  test: the real I-9/I-3 pair scores well above it, an unrelated
  statement scores near zero. It sits low deliberately — a wrongly
  offered neighbour costs a glance; a missed one re-approves a
  corrected-away claim.
- Only `status: confirmed` records are offered. A retired record is
  history, not a neighbour.
- The card renders a "possible restatement of I-n" banner with the
  confirmed prose and the instruction: read it before approving; if the
  proposal adds nothing, deny it.

## Consequences

- The exact 2026-08-15 failure now presents differently: the reviewer
  approving I-9 would have been reading I-3 — including the file comment
  explaining why its wording was corrected — at the moment of decision.
- The neighbour is lexical, and C-21's entry says so: a paraphrase
  sharing no vocabulary arrives bare. The constraint is surfaced, not
  lifted — narration still does not read the confirmed set, which is the
  actual gap and a different (deferred) piece of work.
- The CLI path (`hobbes up`) blocks on the same queue but renders in the
  browser, so one surface carries the banner for both entries.
