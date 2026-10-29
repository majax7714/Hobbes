# Session handoff — the single resume point

**Reviewed 2026-10-29 (forty-seventh session, continued); Hobbes 0.3.4-beta on `main` (`6cb09d4`, PRs #4
and #5 merged); the image and proxy rebuilt at it, and this repo ingested at HEAD.** The TUI trim (DEC-028)
is on branch `refactor/trim-opencode`. A new
session's knowledge server is a new container from the current image, so it starts fresh.

**Size:** about 100 lines, hard cap 150 (`test_agent_docs.py`). Rewrite this
file; don't append to it. Anything open but not done goes in
[`currently-open.md`](currently-open.md). A procedure goes in
[`runbook.md`](runbook.md), a driver path in
[`bench-drivers.md`](bench-drivers.md), and a lesson in
[`lessons.md`](lessons.md). What shipped belongs in the CHANGELOG, and how a
session went belongs in the BUILDLOG.

## ⇢ START HERE NEXT SESSION

**Max's direction:**
- 2026-09-20: extraction first; "we never sacrifice honesty for higher recall".
- 2026-10-01, against fitting: "if we try to 100% 100% everything we might
  be defeating the point of the [poison] check by conforming to our tested
  repos."
- 2026-10-02, on rule tiering: "syntatic over semantic when not clearly
  semantic to preserve honesty".
- 2026-10-03: the extraction order approved; then (forty-second session) "if no extraction items open
  remaining, proceed with testing and grading a weaker side of hobbes … widen tested and look for more per
  language extraction gaps, or resolve gaps if present".
- 2026-10-04: Route 1 ("good to go with route 1"): C-182's node line, the trait-provided-method rule on a
  new held-out cell; then item 5, route a ("good for the recommended route with item 5"). Permission for `oracle py-trace` given for future use (local allow
  rules in `.claude/settings.local.json`).
- 2026-10-28: speed and memory as a standing constraint; "good to go with the first 3" routes (name the
  caps; same output faster; probe a lighter Python indexer), the `tui/` scope "standalone, afterwards".

**Next:** the `tui/` scope question is settled (Max, 2026-10-29: keep it and keep ingesting it, trimmed
to what the binary ships: DEC-028, on branch `refactor/trim-opencode`). Then ADR-184's unbuilt levers (`currently-open.md`): a TS lane A cache needs its own ADR first. The extraction
routes stand as they were: C is the next-thinnest language (two cells).

**Waiting on Max:**
- The PR for `refactor/trim-opencode` (DEC-028). PRs #4 and #5 merged 2026-10-29 (`main` at 0.3.4-beta,
  `6cb09d4`); the image and proxy are rebuilt at it.
- Whether a fuller pyrefly probe runs, on a held-out cell (`currently-open.md`).
- From earlier: the live `watterson tui` check and the `~/.local/bin/watterson` relink; the gate's map
  reason `dynamic-dispatch` for `attr-call`; whether to extend the standing trace oracle; the Python routes
  (C-181's residual, ADR-156 and fixture values).

## Where the last day left things (2026-10-28; the CHANGELOG and BUILDLOG have each one)

Forty-seventh session (speed and memory; three routes approved):
- **ADR-183, 0.3.1-beta:** every wall-clock cap in one table (`extract/caps.py`), named where it bites
  (C-196), `HOBBES_TIMEOUT_SCALE`; scip-clang's timed-out or errored units counted from its own summary
  (C-197, registered and lifted: it exits 0 with an empty index). **0.3.2:** per-step peak RSS in the timings.
- **ADR-184, 0.3.3-beta:** the byte-identity gate `bench/identity/` (8 cells, a control arm); `_own_body`
  once per parse; TS zones on worker threads with a per-zone cap (C-196 narrowed); lane B languages
  concurrent, merged in the serial order. This repo: cold 305 → 194 s, warm 129 → 69 s, peak 3.6 → 6.3 GB.
- **The pyrefly probe:** 98% agreement with scip-python on click, ~6× faster (rough); not a drop-in.
- C-149 amended: its tail flip is larger than a site or two (the control arm showed 16 in one file).
- A flaky dev-environment test, cause not found (`currently-open.md`).
- **0.3.4-beta, 2026-10-29:** the reviews of PRs #4 and #5 (20 findings, some shared). Fixed: the helper's
  one budget for a unit's steps, no caching of a timed-out scip-clang run, step labels, signals named,
  C-197's counting refined, podman's probes capped, the zone timer's limit, per-thread lane B peaks, the
  identity gate (it could pass a failed ingest; every earlier gate re-checked, all stand). Registered in
  C-196: an uncontained step's children outlive its cap.

Forty-sixth session: the dev environment folded in (ADR-181, 0.3.0-beta; extraction byte-identical in both
repos; every watterson test accounted for); ADR-182's function-local import fix (0.2.122-beta, C-195 lifted).

Forty-fourth session: the TS/JS routes, 0.2.119–0.2.121 (ADR-179, ADR-180).
Forty-third session: `currently-open.md` condensed; the trace oracle on click and rich; 0.2.115–0.2.118.
Forty-second session: the first random Rust draw (§10.49), 0.2.111–0.2.114. Forty-first: 0.2.109–0.2.110.

## Where things stand

- **Languages:** Python, TypeScript, Go, Rust, Java, C and C++ are each
  supported as far as their §3.8 row (P11), plus Terraform/HCL structure.
  JavaScript is drawn through TypeScript's lanes and graded on five repos
  of its own (ADR-140), two of them with their dependencies installed
  (C-165).
- **Grading:** every compiler-graded cell is at 100% precision except
  quic-go (99.6%; all 15 rows are the oracle's grain); leaf reads 100%
  since 0.2.116-beta. Rust now stands on nine cells, six drawn at
  random. Each figure carries
  its strict companion (ADR-124); fmt is 100%, strict 99.62%. Trace-graded
  Python cells measure recall, never precision (C-60). rich is fitted
  (ADR-160); pyparsing, icalendar and structlog are graded held out
  (icalendar 70.2%, its 6 wrong rows contained by ADR-168; structlog 77.8%
  at 0.2.100-beta).
- **Register:** 197 entries: 145 active (113 surfaced, 28 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 35 lifted, 11 superseded,
  6 folded. The dated notes are in `docs/constraints/HISTORY.md`.
- **Oracle defect log: H-38 open** (2026-10-03): the trace oracle's
  `getattr` reads run a repo's `__getattr__`; not met on a standing cell.
  RC-4 still carries its price: its silencing is indiscriminate, and it
  hides 6 of C-153's rows.
- **Shanks, the harness** (ADR-107, ADR-112, ADR-152): 98 session logs, and
  the tracker reads 98 of 40 (4 areas, 4 false blocks, all closed, 0
  missed, 1 deny). Each session's state is under `~/.hobbes/sessions/<id>/`.
- **Comparative graphics:** four graphics from 116 cells; `render.py check`
  is green.
- **Atlas-0, TTT and Calvin:** held or closed. See
  [`currently-open.md`](currently-open.md) § Held.
- **Suites:** see [`build-and-test.md`](build-and-test.md) § Suite sizes.

## Standing policy (Max) — binding

0. **No API spend and no Modal compute** (Max, 2026-09-04) unless Max names
   a run and its ceiling. A remainder does not carry over to another run.
   A `hobbes dispatch` spends the owner's Claude Code subscription, not
   API dollars.
1. **Experiments are parked**, except what Max clears by name.
2. **The 7B is the instrument, by speed, not capability.** State the
   GPU-hours first, and spend at least 15 minutes evaluating before any run
   longer than 30 minutes.
3. **P12 (ADR-082):** every TTT arm is *model + prompt*, and is labelled
   that way.
4. **The 27B is untouched** until the mapping fixes are validated on the
   7B, and then only on a decontaminated set.
5. **Tags and numbering are Max's.** The latest tag is `v0.2.10-beta`
   (2026-09-13); the one before it is `v0.1.8-beta`, and everything else
   is untagged. Versions go patch by patch on 0.2.x and count on past
   nine. A language addition or a constraint fix is a patch, even when
   structural; a minor is for
   a feature (0.3.0-beta is the dev environment, ADR-181).
   Ask before a minor.
6. **Work happens on a branch and lands by a PR Max merges** (CLAUDE.md §7).
   Never push to `main`.
