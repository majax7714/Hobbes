# ADR-123 — `hobbes lanes` names a registered disagreement, and exits 3 when that is all there is

**Date:** 2026-09-17 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-17 ("go with your order, write up first"), the route recommended that day for the 2026-09-16 review's item "a distinct `hobbes lanes` exit for registered shapes (C-70, C++)", with honesty and accuracy weighed before the exit code.

Amends architecture **§3.4** (the lane-agreement self-test). Changes
what the layer says, not what it draws: a patch.

## Context

`hobbes lanes` exits 1 on any call site where both lanes resolved and
point at different declarations. Two registered limits produce such
rows by construction, and the check fails on them wherever they occur:

- **C-70.** The fallback is keyed on `(file, line, name)`, so two
  same-named calls on one line (`jsontext.String(x.String())`) share one
  lane A guess, while lane B answers each by column. One of the two
  disagrees because lane A holds one guess for two sites. quic-go exits 1
  on 17 such rows; C-70 has said since 2026-09-02 that "whether CI
  should fail on it is open".
- **C-152.** In a C++ file lane B compiled, lane A's guess is never drawn
  (ADR-113 §2). fmt exits 1 on 316 rows, none of which draws an edge.
  Its record read them against the key: 66 lane B right, 24 a grain
  below the floor, 205 neither lane's target in the key (189 of them
  C-145, lane A holding no symbol for lane B's answer), 21 no key target.

A check that is red on known shapes teaches its reader to ignore red, so
it stops catching the resolver that is confidently wrong. Filtering the
rows out would be worse: the self-test's count is also the only evidence
of how far lane A's guess can be trusted where it *is* drawn.

## Decision

**1. Every site disagreement carries a `shape`, decided by a rule the
report can check, never by a triage.** In this order:

- `same-line-pair` (C-70) — the line holds two or more call sites of
  that name, and lane A's one guess is lane B's answer at *another* of
  them. That explains the row completely: lane A could not have said
  anything else. A same-named line whose guess matches no sibling's
  answer is *not* this shape; it stays unexplained.
- `cpp-withheld` (C-152) — the site's file is in the join's withhold
  set (a C++ file lane B compiled), where lane A's guess draws nothing.

A row neither rule explains has no shape. Nothing is removed from
`site_disagreements`, `sites_compared` does not move, and the rows keep
their order.

**2. Exit status.** `0` no disagreement; `1` at least one row without a
shape; **`3` every row has a shape**; `2` unchanged (no report, no
graph). `--json` exits the same way.

**3. What it prints.** The count per shape beside the unexplained count,
with the constraint cited, and the unexplained rows listed first. For
`cpp-withheld` one more line, because the rate is evidence about edges
that *are* drawn: lane A's C++ guess disagreed with lane B at *N* of the
*M* C++ sites compared, and the same guess is drawn at syntactic tier in
the C++ files lane B did not index (C-152, C-135's C++ face), with that
edge count.

**4. The residual is registered, not implied (C-152 amended).** A row in
a compiled C++ file can no longer fail the check even when lane B is the
lane that is wrong (C-153's kind of error sits in exactly these files).
The row is still listed, counted and exits distinctly; the entry says the
check reports it and does not fail on it.

**5. CI.** `scripts/ci-graph.sh` passes on 3 and prints that the
disagreements are registered shapes; 1 still fails the job.

## Consequences

- **Predicted before the build** (graded in the BUILDLOG entry that
  lands it): this repo 0 rows, exit 0; quic-go's 17 rows all
  `same-line-pair`, exit 3; fmt's 316 rows all `cpp-withheld`, exit 3;
  no graded repo gains an unexplained row.
- This repo: 0 rows, exit 0, unchanged. quic-go and fmt are measured at
  the change, row by row: every row the rules shape is read against the
  rule, and any row they leave unexplained is read (it is either a new
  shape to register or a bug).
- `graph.json`'s `lane_agreement` gains a field per row; no schema bump,
  as when `external_vetoes` and `cpp_withheld` were added.
- Version 0.2.36-beta; a CHANGELOG entry.

## Alternatives considered

- **Compare C++ only where the fallback could draw** (the handoff's
  first route). Rejected: it deletes the only measurement of the guess
  that *is* drawn in uncompiled C++ files, and `sites_compared` would
  quietly shrink (the C-75 habit says a denominator never does).
- **Keep exit 1** (the second route). Rejected: a check red on a
  registered limit on two of the graded repos is a check people stop
  reading.
- **Shape C-70 by "two same-named sites" alone.** Rejected: a genuine
  disagreement on such a line would be excused without evidence.
