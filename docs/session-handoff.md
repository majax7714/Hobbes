# Session handoff — the single resume point

**Reviewed 2026-10-03 (forty-first session); Hobbes 0.2.110-beta on `main`.**
Max pushed through `3d1dda7` (2026-09-29). `main` is ahead of `origin/main`
by the commits since then; they are unpushed. The image and the proxy are at
0.2.110-beta (image `75861ebfd088`), and this repo was
ingested at HEAD after it; if `main` has moved, ingest at HEAD again. A new session's knowledge server is a
new container from the current image, so it starts fresh.

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
- 2026-10-03: the extraction order ("approved, all recommendations are
  good"), then the Phase 1 routes ("good with recommended").

**Next:** Phase 2 of [`currently-open.md`](currently-open.md) § Extraction is worked
through: items 6, 7 and 9 are built, item 8 is closed as measured, and item 5 waits on a Rust crate
that writes operator impls (re-ask Max before building). Item 7's Route A remainder stays open. Take
the next extraction work to Max as routes; the C++ held-out cells chromaprint and filesystem are fitted,
so draw again for a C++ rule.

**Waiting on Max:**
- **The trace measuring run's click and rich cells:** the session's
  permission classifier denied the subagent's contained `oracle py-trace`
  command ("Security Weaken"); not retried or worked around. The command is in
  `~/.hobbes/bench/c174-counts-2026-10-03/python/trace-run/`.
- **Whether to extend the standing trace oracle** on the flask and
  structlog counts (implicit rows 13–15% of confirmed, mostly property
  getters; no grade moves; recall falls by denominator).
- C-181's residual, ADR-126 §3 and the rest of "Decisions open for Max".
Don't build any of them until Max answers.

## Where the last day left things (2026-10-03; the CHANGELOG has each one)

Forty-first session (Max: "go with recommended", then a route at each re-ask):
- **0.2.109, ADR-050 amended (C-23):** dagger's re-ingest showed the npm install's cache copy holds only
  `package.json` and the lockfile. A local-path dependency (dagger's 11 docs zones, `./sdk`) failed with
  yarn's error about a cache path, and a workspace root installed silently partial (npm 10.9.2). Both are now
  declined by name. dagger's Rust cell is identical; xmpp.js's lock is out of sync under npm 10 (C-165 stands).
- **Item 8 closed as measured** (C-174): 5 of 29 fitted `__call__` misses reachable; the voluptuous draw
  (pre-registered) about 2.
- **0.2.110, ADR-176:** a globals-style test file is named by the one runner its manifest declares (C-13
  narrowed; 320 of 326 on six cells, 316 run by that runner). The harness runs only an imported runner.
  Express's un-test-named mocha suite is C-194, surfaced by a `js-tests` record.

Fortieth session: item 7's held-out C++ draw; a `#define` read as a function fixed at **0.2.107**
(ADR-135's second amendment); item 7 built at **0.2.108** (ADR-175: a functor's `operator()` and an
implicit conversion, `semantic`; filesystem 3,048 → 3,220, 0 contradicted on five cells).

Thirty-ninth session: the extraction order's Phase 1 audits and their routes, 0.2.102–0.2.106 (Terraform's
limits registered and its ids scoped by directory, C-164's remainder named, C-174 counted at repo scale,
C-176 widened, Rust impl ids by ordinal). H-38 logged open.

## Where things stand

- **Languages:** Python, TypeScript, Go, Rust, Java, C and C++ are each
  supported as far as their §3.8 row (P11), plus Terraform/HCL structure.
  JavaScript is drawn through TypeScript's lanes and graded on five repos
  of its own (ADR-140), two of them with their dependencies installed
  (C-165).
- **Grading:** every compiler-graded cell is at 100% precision except
  quic-go (99.6%; all 15 rows are the oracle's grain). Each figure carries
  its strict companion (ADR-124); fmt is 100%, strict 99.62%. Trace-graded
  Python cells measure recall, never precision (C-60). rich is fitted
  (ADR-160); pyparsing, icalendar and structlog are graded held out
  (icalendar 70.2%, its 6 wrong rows contained by ADR-168; structlog 77.8%
  at 0.2.100-beta).
- **Register:** 194 entries: 144 active (112 surfaced, 28 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 33 lifted, 11 superseded,
  6 folded. The dated notes are in `docs/constraints/HISTORY.md`.
- **Oracle defect log: H-38 open** (2026-10-03): the trace oracle's
  `getattr` reads run a repo's `__getattr__`; not met on a standing cell.
  RC-4 still carries its price: its silencing is indiscriminate, and it
  hides 6 of C-153's rows.
- **Shanks, the harness** (ADR-107, ADR-112, ADR-152): 98 session logs, and
  the tracker reads 98 of 40 (4 areas, 4 false blocks, all closed, 0
  missed, 1 deny). Each session's state is under `~/.hobbes/sessions/<id>/`.
- **Comparative graphics:** four graphics from 108 cells; `render.py check`
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
   a feature (0.3.0 is the dev environment, which is not being worked on).
   Ask before a minor.
6. **Work happens on `main`. Never `git push`;** publishing is Max's.
