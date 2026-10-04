# Session handoff — the single resume point

**Reviewed 2026-10-04 (forty-third session); Hobbes 0.2.118-beta on `main`.**
Max pushed through `3d1dda7` (2026-09-29). `main` is ahead of `origin/main`
by the commits since then; they are unpushed. The image and the proxy are at
0.2.118-beta (image `65bd07c9f2a4`), and this repo was
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
- 2026-10-03: the extraction order approved; then (forty-second session) "if no extraction items open
  remaining, proceed with testing and grading a weaker side of hobbes … widen tested and look for more per
  language extraction gaps, or resolve gaps if present".
- 2026-10-04: Route 1 ("good to go with route 1"): C-182's node line, the trait-provided-method rule on a
  new held-out cell; then item 5, route a ("good for the recommended route with item 5"). Permission for `oracle py-trace` given for future use (local allow
  rules in `.claude/settings.local.json`).

**Next:** Route 1 (Rust) is done. Take the TS and Python routes in `currently-open.md` § Extraction to Max
(ADR-158's amendment, zod's class-property functions, C-181's residual, ADR-156 and fixture values). C is
the next-thinnest language (two cells); its draw would continue §10.5's order.

**Waiting on Max:**
- **Whether to extend the standing trace oracle:** all four cells measured (click and rich on 2026-10-04).
- The TS and Python routes above.
Don't build any of them until Max answers.

## Where the last day left things (2026-10-04; the CHANGELOG has each one)

Forty-third session (Max: condense the open extraction items, then Route 1):
- `currently-open.md` trimmed to what is open, grouped by language (205 → 160 lines, nothing dropped).
- **Trace oracle, click and rich** run contained: 676 and 1,308 implicit rows; recall falls by denominator
  only (82.0% → 71.5%, 93.6% → 75.3%); nothing contradicted.
- **0.2.115:** the `below-floor` text names C-9's floor, not only dispatch; `verification.py`'s Rust base
  (3 repos while §3.8 named 7) left `test_verification` red on `main`; fixed.
- **0.2.116 (ADR-165's second amendment, C-182 narrowed):** a cfg twin's node sits at the arm lane B
  defined (leaf 44 → 0 contradicted). The probe found rust-analyzer still writes references inside an
  uncompiled arm; 45 on leaf are now refused (23 `semantic` `uses` edges had rested on them).
- **0.2.117 (ADR-177):** a trait's provided method is a node. Held out **cyme** (drawn, pre-registered):
  2,708 → 2,754, 46 of 46; sea-query (fitted) 5,601 → 6,263, recall 93.7%. P4's wording gap recorded.
- **0.2.118 (ADR-178, item 5):** a Rust operator applied to a repo impl is a call at its token. cyme was
  vacuous (all `PartialEq` at `==`, unreachable); held out **ureq**: 1,257 → 1,274, 17 drawn, 0
  contradicted; hecs (fitted) 1,379 → 1,440. Q2 missed as written (the counter's flaws), recorded.

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
   a feature (0.3.0 is the dev environment, which is not being worked on).
   Ask before a minor.
6. **Work happens on `main`. Never `git push`;** publishing is Max's.
