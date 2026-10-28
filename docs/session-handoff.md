# Session handoff — the single resume point

**Reviewed 2026-10-28 (forty-sixth session); Hobbes 0.3.0-beta on branch `feat/watterson-fold`
(PR #2), which carries ADR-182's fix (0.2.122-beta, its own PR from `fix/function-local-import-scope`,
to merge first); 0.2.121-beta on `main`.** `origin/main` is at `2089e22`. The image and proxy were
rebuilt at 0.3.0-beta on the branch by a local run of `scripts/ci-graph.sh`; that run also ingested this
repo at the branch's head. If `main` moves, ingest at HEAD again. A new session's knowledge server is a
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

**Next:** the dev environment is folded in (ADR-181, 0.3.0-beta, PR #2). The lane A defect its CI run
found is fixed (ADR-182, C-195, 0.2.122-beta); what is left red in its `graph` job is the one-time
`review` delta (1,689 new modules no test reaches, mostly opencode), Max's call at merge. The extraction routes stand
as they were: C is the next-thinnest language (two cells).

**Waiting on Max:**
- The two PRs: ADR-182's fix first, then the fold (PR #2); after them the live `watterson tui` check and
  the `~/.local/bin/watterson` relink; rebuild the image at 0.3.0-beta and ingest at HEAD.
- The gate's map reason `dynamic-dispatch` for `attr-call` (`currently-open.md`).
- **Whether to extend the standing trace oracle:** all four cells measured (click and rich on 2026-10-04).
- The Python routes (C-181's residual, ADR-156 and fixture values).

## Where the last day left things (2026-10-28; the CHANGELOG and BUILDLOG have each one)

Forty-sixth session (Max: bring watterson-environment in as a monorepo, behaving exactly as it does;
"approved recommended good to proceed" on seven routes):
- **ADR-181, 0.3.0-beta:** `hobbes.watterson` and its own `watterson` command; `tui/`, `review/`,
  `adapters/`, `bin/` at the root; watterson's docs in `docs/watterson/`. The extraction was
  byte-identical in both repos, so `hobbes` is unchanged.
- **Parity:** every watterson pytest accounted for (3,345 here, hobbes' 2,892 unchanged); review 13/13 and
  its bundle byte-identical; the TUI's suite 1,492 pass / 2 skip on both; `watterson` outputs compared
  against watterson-environment@a65b6b1 on two targets (the BUILDLOG entry has the counts).
- **0.2.122 (ADR-182, C-195 lifted):** a function's import binds its name in that function only; the
  fold's `unexplained` lanes row. 3 sites moved over 22 repos, all to Python's binding (cachetools held out).
- **Measured:** opencode adds 2,628 module nodes and ~43 s of lane A; lane B fails per opencode zone where
  its deps are not installed (disclosed), so it adds no unexplained disagreement.

Forty-fourth session (Max: routes for the TS/JS items; "approved recommended", "recommended is approved"):
- **1a:** ADR-158's amendment approved as built (0.2.82-beta); the open item is now C-176's floor alone.
- **2a:** all 13 keyed TS/JS cells regraded at `d101148` (0 contradicted, poison passed). zod's 1,274
  `static→property` rows: 42 lane B names at the token, 1,232 an alias chain the index writes nothing at.
- **1b step 0:** caller side ~515 rows, callee side ~48; shorthand members are locals in the index.
- **0.2.119:** `attr-call`'s text names both causes (C-2 amended). **0.2.120 (ADR-179):** a top-level literal's member
  is a scope-only caller; the held-out walk (42–80) took no cell; Max merged on the fitted cells (ajv 628
  rows re-filed, grades and reach unmoved).
- **0.2.121 (ADR-180):** a function-literal class field is a method symbol: zod 9,927 (+42), hono 910 (+75),
  folio +3, 0 contradicted; the TS draw (`~/.hobbes/bench/ts-cells/`, 80 positions) took no cell.
- A 20-hour wait loop (`until ! pgrep -f walk-adr179.sh`) matched itself; Max caught it twice. Killed; the
  memory on detached launches carries it.

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
