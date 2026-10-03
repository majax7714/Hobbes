# Session handoff — the single resume point

**Reviewed 2026-10-03 (thirty-seventh session); Hobbes 0.2.96-beta on `main`.**
Max pushed through `3d1dda7` (2026-09-29). `main` is ahead of `origin/main`
by the commits since then; they are unpushed. The image (`4a556e979473`, rebuilt by the graph job) and
the proxy are at 0.2.96-beta; this repo was ingested at `6d2274f` by the host
run of `scripts/ci-graph.sh 3fda729`, which passed. The old knowledge
server's container was stopped for a `/mcp` reconnect. If `main` has moved,
ingest at HEAD again. A new session's knowledge server is a new container
from the current image, so it starts fresh.

**Size:** about 100 lines, hard cap 150 (`test_agent_docs.py`). Rewrite this
file; don't append to it. Anything open but not done goes in
[`currently-open.md`](currently-open.md). A procedure goes in
[`runbook.md`](runbook.md), a driver path in
[`bench-drivers.md`](bench-drivers.md), and a lesson in
[`lessons.md`](lessons.md). What shipped belongs in the CHANGELOG, and how a
session went belongs in the BUILDLOG.

## ⇢ START HERE NEXT SESSION

**Max's direction:**
- 2026-09-20: extraction first. "the most annoying work to do but the most
  important for hobbes"; "we never sacrifice honesty for higher recall".
- 2026-10-01, against fitting: "if we try to 100% 100% everything we might
  be defeating the point of the [poison] check by conforming to our tested
  repos."
- 2026-10-02, on rule tiering: "syntatic over semantic when not clearly
  semantic to preserve honesty".
- 2026-10-03, on the open-items routes: "all those look good. good to
  proceed- approved".

**Next: C-184's containment, Max's call first** (precedent 1). The held-out
icalendar grade found scip-python drawing a method call on a union-typed
receiver to the union's first member at `semantic` (6 Hobbes-wrong rows,
`oracle-grading.md` §10.46). TypeScript's face is contained (ADR-104); the
routes are at the top of [`currently-open.md`](currently-open.md). **Then
the `cls(…)` rule**: step 0 and icalendar's pre-registration are done; the
ADR, the build and the C-rows are next (its wording is frozen in
`~/.hobbes/bench/heldout-icalendar/PREREG.md`).

**Waiting on Max:** C-184's route; flask's `sansio/` (re-ask: the probe
showed the missing `Flask → App` is scip-python omitting `Flask#`'s
relationships, not PEP 420 naming); C-181's residual, ADR-126 §3 and the
rest of "Decisions open for Max". Don't build any of them until Max answers.

## Where the last day left things (2026-10-03; the CHANGELOG has each one)

Max approved eight routes; seven are built, each its own commit, regraded
where it could move a cell:
- **0.2.91-beta, ADR-100 amended:** verify's `E2E` (an error on both trees
  is a fault, not a failure; harness v3).
- **0.2.92-beta, ADR-166, C-183:** a Go file's later `init` is the node's
  (dagger: 89 `uses` moved from the module, nothing else).
- **0.2.93-beta, ADR-012 amended:** the ignore line goes in
  `.git/info/exclude`; the ingest no longer edits the tracked tree.
  I-2's guard was renamed with its test (`6d2274f`, caught by the graph job).
- **0.2.94-beta, ADR-154 amended:** C-173's record names the code after a
  platform-guarded `raise` (rich: 16–661; graph byte-identical).
- **0.2.95-beta, ADR-165 amended:** C-182's two-kinds repeat is refused,
  the rest named in `rust-repeats` (memchr 919/919; C-182 surfaced).
- **0.2.96-beta, ADR-167:** C-179 named where `tests_guarding` and the
  review say "unguarded" (this repo: 5 loads placed; C-179 partial).
- **Not built:** flask's `sansio/` (re-ask, above); `cls(…)` (behind
  C-184).

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
  (ADR-160); pyparsing is held out; icalendar is graded held out at
  0.2.96-beta (68.9%, **6 Hobbes-wrong**, C-184) and is the `cls(…)` rule's
  held-out cell.
- **Register:** 184 entries: 136 active (104 surfaced, 27 partial, 4
  unsurfaced — C-19, C-20, C-112, C-184 — 1 n/a), 31 lifted, 11 superseded,
  6 folded. The dated notes are in `docs/constraints/HISTORY.md`.
- **Oracle defect log: nothing open.** H-37 is the latest, fixed at
  0.2.79-beta. RC-4 still carries its price: its silencing is
  indiscriminate, and it hides 6 of C-153's rows.
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
