# Session handoff — the single resume point

**Reviewed 2026-10-30 (fiftieth session); `main` at 0.3.9-beta (`8205e42`, PRs #8–#14 merged); branch
`test/merman-sequence` committed, not yet pushed; the image was built 2026-10-30 14:21 UTC, six minutes before 0.3.9-beta's commit (ADR-188):
rebuild it if a check needs that certainty; rerun `hobbes ingest` before trusting `tests_guarding`.** A new
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

- 2026-10-29: our own tests for the fork, "tests aren't test dependent" (no case that only fails when
  another does; checked by `bench/subsume/`); "good for the recommended routes" (C-198's fix, the tool in
  `bench/`, no-logic modules accepted apart, pure packages first). Forty-ninth session: "yeah proposed for
  both are good": `attr-call` filed `laneb-miss` (0.3.7-beta); the trace key's implicit calls as a companion
  key (ADR-187), H-38 fixed first.
- 2026-10-30, on derived cases redundant against pinned inputs: "Keep both, exempt them" (the derived case is
  the readable statement of the rule). PRs #13 and #14 flagged cases kept the same way, or kept because they
  guard a fault `subsume` cannot plant (checked by planting it by hand); neither was overruled.

**Next: `merman`'s last two diagram families, then the rest of the fork's tests.** Done: `core` (PR #9),
the top level (PR #10), flowchart (PR #13, 97 cases), gantt and gitGraph (PR #14, 71 cases), sequence
(branch `test/merman-sequence`, 62 cases, PR waiting on Max's push; it carries this handoff's `74408d8`).
Left, in order, each on its own branch and PR:
- **state** (`src/state/`: `parser`, `layout` 1,134, `routing` 1,522, `search`, `note`, `visible-model`,
  `endpoint`, `drawing`, `style`, `options`). Its layout and routing are flowchart-sized.
- **timeline** (`src/timeline/`: `parser` 119, `drawing` 109, `style`).

How, as the last four families were done (BUILDLOG 2026-10-30 entries; tests under
`packages/merman/test/<family>/`, one file per module, `prettier --write` on new files):
- derive each expected output by hand from the source, then run it;
- `bench/subsume` per module against **that module's own test file** (`--tests test/<family>/<module>.test.ts`;
  against the whole family every other file's cases read as redundant), **serially with `-j 2`** (Max, 2026-10-29: its default 6 workers peaked this
  machine's memory), detached (`setsid nohup … &`, then an until-loop waiter); read every survivor; close the
  gaps; fold redundant cases, or keep one only if a fault planted by hand fails it alone, and say so above it;
- for a layout or routing module where derived cases leave large gaps (sequence's placement did not), the pinned-input method (flowchart
  entry: plant each survivor in a scratch copy, search random diagrams for an input it changes, shrink, keep
  the fewest). **Its scripts were in the forty-ninth session's scratchpad and are gone**; rebuild them from
  that entry, or ask Max whether to keep them in `bench/` this time.
- a fork defect found is pinned by a test and listed under the fork-tests item in `currently-open.md`.

After `merman`: `core/shell`, `codemode`, then `schema`'s decoders, then the effectful packages (the count is
in `currently-open.md`). Then ADR-184's unbuilt levers (`currently-open.md`): a TS lane A cache needs its own
ADR first. The extraction routes stand as they were: C is the next-thinnest language (two cells).

**Waiting on Max:**
- The fork defects our tests pin (`currently-open.md`, the fork-tests item): `latex`'s four, `merman`'s
  `core` diamond caps, flowchart's two (an outside node laid over a framed one; a parallel edge's head
  beside its target), and sequence's note over no one (dropped silently). Fix them, or leave them pinned.
- Whether a fuller pyrefly probe runs, on a held-out cell (`currently-open.md`).
- H-39: the trace oracle's re-entrance guard is shared across threads; a thread-local guard moves every key
  with a threaded test (`currently-open.md`).
- From earlier: the live `watterson tui` check and the `~/.local/bin/watterson` relink; the Python routes
  (C-181's residual, ADR-156 and fixture values).

## Where the last day left things (2026-10-30; the CHANGELOG and BUILDLOG have each one)

Forty-ninth session: 0.3.7-beta (the gate's `attr-call` reason, H-38, ADR-187); 0.3.8-beta (a module the
accept list names is accepted, ADR-185 amended; this repo's nine unguarded modules tested or accepted, CI's
`graph` job green, PR #11); 0.3.9-beta (a TS/JS case with a computed title is a case, ADR-188, C-199);
`merman`'s top level, flowchart, gantt and gitGraph tested (PRs #10, #13, #14).
Forty-seventh and forty-eighth (2026-10-28/29): speed and memory, ADR-183 and ADR-184 (0.3.1–0.3.4-beta); the
pyrefly probe; the TUI trimmed (PR #6); the fork's own tests begun (`bench/subsume/`, PRs #7, #9).
Forty-sixth: the dev environment folded in (ADR-181, 0.3.0-beta).

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
- **Register:** 199 entries: 147 active (115 surfaced, 28 partial, 3
  unsurfaced — C-19, C-20, C-112 — 1 n/a), 35 lifted, 11 superseded,
  6 folded. The dated notes are in `docs/constraints/HISTORY.md`.
- **Oracle defect log: H-39 open** (2026-10-29): the trace oracle's re-entrance
  guard is shared across threads (H-38 fixed the same day).
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
