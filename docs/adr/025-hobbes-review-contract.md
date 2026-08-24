# ADR 025: The `hobbes review` contract

Date: 2026-08-11
Status: accepted

## Context

Build plan M8: `hobbes review <PR>` = graph diff + invariant verdicts +
behavioral-coverage delta + a reviewer-session narrative for `soft`
invariants. Architecture §7 gives the review *order* — graph diff →
invariant check → behavioral coverage delta → (only if needed) line diff
— and says the environment's whole purpose is that the last step becomes
rare.

What that leaves open is what a review *asserts*. A reviewer needs to
know not only "is anything broken now" but "did this change break it",
and those are different questions with different answers on the same
repo. It also leaves open what happens to the parts no tool can check,
which on this repo is four of six confirmed records.

## Decision

**`hobbes review <base>..<head>`**, the same range syntax as `hobbes
diff` (ADR-009), extracting both trees from `git archive` so the review
sees committed trees and never the working directory.

**Verdicts are computed at both ends, and the delta is what leads.** An
invariant that already failed on `base` is a pre-existing problem;
one that passes on `base` and fails on `head` is *this change's*
regression, and the two must not read alike. The review reports
`regressed`, `fixed`, `still failing`, and `unchanged`, and its headline
is the regression count. A review that cannot distinguish inherited
breakage from introduced breakage trains people to ignore it.

**Behavioral-coverage delta is the §4.2 metric, not line coverage:**
modules whose guarding tests disappeared, modules added by this change
that no test reaches, and invariants whose `guarded_by` tests no longer
exist. New unguarded code is the finding — the number that moves when a
change adds behaviour nothing pins down.

**Soft invariants get a reviewer session, and only when they are in
scope.** A `soft` record is judged by the ADR-020 headless runner, given
the record, the graph delta, and the changed files, and required to
answer with a verdict plus pins. The session runs only for records whose
`scope` contains a changed path — narrating an invariant this change
cannot have affected spends quota to say "unchanged". `--no-soft` skips
them entirely, which is the default in CI and the flag that keeps the
whole command quota-free.

**Exit codes** follow `hobbes diff`'s shape: `0` nothing needs
attention, `1` something does (a regression, a lost guard, newly
unguarded code), `2` usage or a bad ref. CI can gate on the exit code
alone.

**`--json` emits the whole review** — delta, verdicts at both ends,
coverage, soft answers — because the M7 surface and a future PR bot are
both consumers, and a screen-scraped format is not a contract.

Nothing here runs import-linter or semgrep. Their configs are compiled
for CI (ADR-024); the review's own verdicts come from the graph, so
`hobbes review` is deterministic and needs no toolchain. Targets the
graph cannot answer report `unknown` and are counted separately from
passes — never folded into them.

## Alternatives considered

- **Verdicts on `head` only** — simpler, and wrong in the way that
  matters: every long-standing violation would be reported against
  whoever touched the file next.
- **Running the compiled configs** — would make review depend on four
  toolchains, and would give two implementations of one rule the chance
  to disagree. CI runs them; review reads the graph they were compiled
  from.
- **Line coverage delta** — measures execution, not behaviour, and §4.2
  is explicit that behavioural coverage is the metric that matters.
- **A reviewer session for every soft invariant** — burns quota
  proportional to the record count rather than to the change, for an
  answer that is almost always "not affected".
- **Failing the exit code on any `unknown`** — would make every repo
  with a semgrep-target invariant permanently red, teaching people to
  pass `--exit-zero`.

## Consequences

- A review distinguishes what a change broke from what was already
  broken, which is the difference between a gate people trust and one
  they route around.
- The default review spends no quota and needs no network: graph diff,
  verdicts, and coverage are all computed from two extractions.
- Soft invariants remain first-class rather than being quietly dropped
  because they were inconvenient to check — the reviewer session is
  their enforcement, and its answers carry pins like every other claim
  (P3).
- M7's surface has a JSON contract to render a PR mode against when that
  is picked up, without the server needing to reimplement any of this.
