# Session handoff — the single resume point

**Reviewed 2026-10-03 (thirty-ninth session, close); Hobbes 0.2.106-beta on `main`.**
Max pushed through `3d1dda7` (2026-09-29). `main` is ahead of `origin/main`
by the commits since then; they are unpushed. The image and the proxy are at
0.2.106-beta (image `4b517d39a845`); this repo was ingested at HEAD by the host run of
`scripts/ci-graph.sh 3fda729` at the close, which passed. If
`main` has moved, ingest at HEAD again. A new session's knowledge server is a
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

**Next:** [`currently-open.md`](currently-open.md) § Extraction. Phase 1 is
done and items 5–6 are settled; **item 7** is next: C++ functors (C-146) and
implicit conversions (C-162), with Route A's remainder. No C++ cell is held
out since §10.16: pick and pre-register one before measuring. Then items 8
(Python `__call__` held in an attribute, held out on voluptuous,
marshmallow, toolz or tenacity) and 9 (C-13, jest globals).

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

Thirty-ninth session: Max approved the extraction order, then the Phase 1
routes; each unit its own commit, regraded where it could move a cell:
- **0.2.102, ADR-173, C-187–C-193:** the Terraform layer had no `C-n`; an
  HCL fixture found the address merge and a cross-directory reference
  drawn. The latter refused; all limits named per ingest (`hcl-layer`,
  `hcl-parse`); `list_blind_spots` serves an infra-only scope.
- **0.2.103, ADR-135 amended:** C-164's remainder named (`cpp-macro-names`;
  fmt lane A alone 18 = the register's count, with lane B 1, args 0).
- **0.2.104:** C-174 counted at repo scale (upper bounds; Rust's graded
  crates write no operator impl, so item 5 is deferred); C-176 measured on Go
  and Java (jsoup's enum constant bodies 1,691 rows, Go package vars),
  widened, and `who_calls` names both.
- **0.2.105, ADR-173 amended:** Terraform ids `tf:<dir>:<address>`; C-187
  lifted (terraform-aws-eks 287 blocks, 287 nodes).
- **0.2.106, ADR-174:** Rust impl ids by ordinal (`T.distance~2`), Max's
  scheme; C-180 lifted (memchr 919 → 921, dagger 3,363 → 3,595, 0
  contradicted, poison PASS).
- **H-38 logged open** (the tracer's `getattr` runs a repo's `__getattr__`).
- Slip, fixed and in the BUILDLOG: 0.2.103's bump pinned the architecture's
  §8 header by line number after an insertion moved it; replace by content.

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
- **Register:** 193 entries: 143 active (111 surfaced, 28 partial, 3
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
