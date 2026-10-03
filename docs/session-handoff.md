# Session handoff — the single resume point

**Reviewed 2026-10-03 (thirty-sixth session); Hobbes 0.2.89-beta on `main`.**
Max pushed through `3d1dda7` (2026-09-29). `main` is ahead of `origin/main`
by the commits since then; they are unpushed. The image and the proxy are at
0.2.89-beta (rebuilt by the C-182 unit; the knowledge server running then was
not restarted, so restart it), and this repo was last ingested by that unit's
`scripts/ci-graph.sh` run, on the uncommitted tree. If `main` has
moved, ingest at HEAD again. A new session's knowledge server is a new
container from the current image, so it starts fresh.

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

**Next unit: `cls(…)` in a classmethod** (rich 57, pyparsing 17), measured
first. **Before you measure it, pick the next held-out Python repo.**
pyparsing is held out now, and fitting the rule on it would spend it. The
full ordered queue is under "Extraction, in order" in
[`currently-open.md`](currently-open.md).

**Waiting on Max:** the red graph job (5 unguarded modules; `lanes` is
fixed), how to surface C-179, C-181's and C-182's residuals, ADR-126 §3, and the rest of the "Decisions open for Max" section in
[`currently-open.md`](currently-open.md). Don't build any of them until Max
answers.

## Where the last day left things (2026-10-02/03; the CHANGELOG has each one)

- **0.2.89-beta, ADR-165, C-182 registered (partial)** (Max: route 1, then
  "map to the node"): CI's `hobbes lanes` failed on ADR-163's fixture cfg
  twin; the probe found the edge itself dropped (`below-floor`). A Rust cfg
  twin's arms are now the node's both ways, the lane row is `cfg-twin`, and
  a `rust-cfg-twins` record names twins. memchr byte-identical (919/919).
- **0.2.88-beta, ADR-164, C-181 registered (partial)** (Max: route R1): a
  Python call rooted at a same-file stdlib import that scip-python left
  unplaced is tailed `stdlib-import`, not `import-binding`/`attr-call`.
  flask 34, click 181, rich 82 sites moved; no edge or grade moved. Open
  for Max: C-181's `except ImportError:` residual; C-173's record misses
  code after a platform-guarded `raise` (both in `currently-open.md`).
- **0.2.87-beta, ADR-163, C-180 registered and contained** (Max: the narrow
  route): a fact at a later def of a Rust id two impl headers share is
  refused, tailed `shared-qualname`. memchr 921 → 919 (the false
  `T.distance` self-call gone), dagger-rust 3,592 → 3,363 (wrong-caller
  rows), 0 contradicted, strict 100%. The prevention (distinct ids) is open.

- **0.2.85-beta, ADR-160 (unit `3814`):** a call through a local alias is
  drawn `syntactic`. rich went from 4,844 to 4,968 (90.20% → 92.51%); flask
  and click are identical; pyparsing +1. rich counts as fitted from here on.
- **pyparsing 3.3.3 is the held-out Python cell** (`oracle-grading.md`
  §10.44): 3,516 confirmed, 0 Hobbes-wrong calls of 66 suspects, recall
  50.6%.
- **0.2.86-beta, ADR-161 (unit `aa88`), C-178 contained:** scip-python
  answers the first `pkg.Name` it resolves through a `from … import *`
  re-export for every later one. Hobbes now refuses, by shape, any Python
  reference whose token is not its name, through a chain rooted at an
  imported name, before the join, and counts the refusals. On pyparsing, 2,919 are refused, and
  the wrong `uses` rows fell from 1,671 to 10; no `calls` row moved.
- **Same day:** I-4's roster names `csource`/`cppsource` (`83555c9`). C-179
  is registered, unsurfaced. The graph job's unguarded modules went from 22
  to 5 (`1d5a7c0`).

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
  (ADR-160), and pyparsing is held out.
- **Register:** 182 entries: 134 active (102 surfaced, 27 partial, 4
  unsurfaced — C-19, C-20, C-112, C-179 — 1 n/a), 31 lifted, 11 superseded,
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
