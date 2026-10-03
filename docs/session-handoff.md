# Session handoff — the single resume point

**Reviewed 2026-10-03 (thirty-eighth session, close); Hobbes 0.2.101-beta on `main`.**
Max pushed through `3d1dda7` (2026-09-29). `main` is ahead of `origin/main`
by the commits since then; they are unpushed. The image (`9830f55090f9`) and the
proxy are at 0.2.101-beta; this repo was ingested at HEAD by the host run of
`scripts/ci-graph.sh 3fda729`, which passed. The old knowledge server's
container was stopped for a `/mcp` reconnect. If `main` has moved, ingest at
HEAD again. A new session's knowledge server is a new container from the
current image, so it starts fresh.

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

**Next:** the extraction order Max approved on 2026-10-03, in
[`currently-open.md`](currently-open.md) § Extraction: Phase 1's audits
first, all done: Terraform/HCL at 0.2.102-beta (ADR-173), C-164's remainder at
0.2.103-beta, C-174's counts and C-176 on Go and Java at 0.2.104-beta. The
counts are with Max for the trace-oracle decision, and item 5's premise
changed (no graded Rust crate implements an operator trait), and the counts go back to Max
for the trace-oracle decision. Then Phase 2's graded rules (Rust operators,
then Rust's impl-distinct ids, then C++ functors and conversions), each on a
held-out cell picked first. Python held out: structlog, icalendar,
pyparsing; unused: voluptuous, marshmallow, toolz, tenacity.

**Waiting on Max:** C-181's residual, ADR-126 §3 and the rest of "Decisions open for Max" in
[`currently-open.md`](currently-open.md). Don't build any
of them until Max answers.

## Where the last day left things (2026-10-03; the CHANGELOG has each one)

Max approved eight routes, then the two follow-ups ("proceed with the
recommended decisions"); each is its own commit, regraded where it could
move a cell:
- **0.2.91** verify's `E2E` (ADR-100); **0.2.92** Go's later `init` is the
  node's (ADR-166, C-183); **0.2.93** the ignore line in `.git/info/exclude`
  (ADR-012); **0.2.94** C-173 names code after a guarded `raise` (ADR-154);
  **0.2.95** C-182's residual refused or named (ADR-165); **0.2.96** C-179
  named where it reads "unguarded" (ADR-167).
- **icalendar, held out, graded at 0.2.96** (§10.46): 6 Hobbes-wrong rows,
  scip-python's first-member pick on a union receiver. **0.2.97, ADR-168,
  C-184 contained** where the union is written: the 6 gone, the other
  cells byte-identical.
- **0.2.98, ADR-169, C-185:** a class base scip-python states no relationship
  for is named (`python-bases`; flask's `Flask → App` among 85 pairs).
- **0.2.99, ADR-170:** `cls(…)` in a classmethod calls its class, `syntactic`
  (icalendar +76, rich +51; C5 missed by one row, the probe's grain).
- **Thirty-eighth session:** the open-work docs reconciled (`37c9af7`: W1's
  stale lines struck, its orphans re-homed in `currently-open.md`). Then C-174
  in Python: structlog picked held out by an `ast` scan and pre-registered;
  **0.2.100, ADR-171:** a constructed instance's `__call__`, `syntactic`
  (structlog +130, all confirmed; pyparsing +23; rich +6). P1 missed:
  pyparsing's `pp.X(…)(…)` abstain under C-178, which the source-count
  prediction ignored (lesson added). **0.2.101, ADR-172, C-186:** the Python
  twin structlog showed (`dev._init_terminal`, one node at the def that does
  not run) registered and named per ingest (`python-repeats`).
- Slips, each fixed and in the BUILDLOG: I-2's guard renamed with its test;
  `test_verification` red from `21d019e` to `62a654e`, and again from
  `9a5545a` to 0.2.101 (§3.8's row edited without its pinned copy); the
  "last ADR" copy.

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
- **Register:** 193 entries: 144 active (112 surfaced, 28 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 32 lifted, 11 superseded,
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
