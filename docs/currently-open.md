# Currently open — decisions and work noted, not done

Everything waiting on a decision or on time, so that `CLAUDE.md` and
`session-handoff.md` can just point here. Read a section when your task
touches it. Don't read the whole file by default.

**Rules for this file.** An item gets one entry, with a pointer to the
record that holds its numbers. Its detail lives in that record, not here.
When an item is decided or done, delete it and record the outcome in the
CHANGELOG and the BUILDLOG. Nothing here is built until it's named: a
decision is Max's, and spend needs his word for a named run and its
ceiling.

Last reviewed: 2026-10-03 (0.2.96-beta).

## Decisions open for Max (no spend)

- **C-181's residual** (ADR-164): a name that a stdlib import binds, and
  that an `except ImportError:` branch rebinds to a repo function, keeps
  lane A's `syntactic` edge to the repo function. Lane B's local answer
  cannot veto it (ADR-111). No graded cell writes this shape; the
  `ministdlib` fixture pins it. Proposed: refuse lane A's fallback where
  the same name is also bound by a stdlib import (a patch), or leave it
  registered.
- **ADR-126 §3:** whether to build the "may reach through dispatch (not
  traced)" section in `tests_guarding` and `hobbes review` on
  `oracle-grading.md` §10.12's numbers. It needs a syntax exclusion for
  every non-dispatched call (Java `super.`/private/static/final, Python
  `super()`, C++ class-qualified), and it would say that no key confirms
  reach.
- **ADR-158's amendment:** nested functions file under their top-level
  symbol. This was pre-registered, but it was not in the route Max named.
  C-176 keeps the floor (an object literal's method, an unnamed class, a
  property-assigned function, a namespace). Lifting it moves the symbol
  set. The CJS literal member (cue 49, Express 46) is the same question.
- **The TS symbol floor's class-property functions** (zod: 1,029 collapsed
  pairs). They were set aside on 2026-09-10 until the constructor grain
  was settled before `new`, and ADR-142 has since settled it. **Re-ask; do
  not start.**
- **ADR-156 and fixture values:** the `with` rule does not build on
  ADR-145's `syntactic` fixture-value edges (40 of flask's items, `with
  app.app_context():`). Allowing it would stack one `syntactic` rule on
  another.
- **flask's PEP 420 `sansio/` naming** (route 2 of the 2026-10-03 re-ask,
  not taken): lane A and scip-python both name the modules `app`,
  `scaffold`, `blueprints`, not `flask.sansio.*`; references join. Register
  it if it ever bites (two namespace directories each holding `app.py`
  would collide, C-28). The missing `Flask → App` is C-185's (ADR-169).
- **`npm ci` refused three of four lockfile-bearing JS repos** (counted
  under C-23 in C-165). Open: whether "pinned or declined" falls back to
  anything. Nothing is proposed.
- **Calvin's findings, proposed and not registered:** G-diff coverage. The
  driver never puts inf/NaN in `b` alone and never mixes inf kinds, so
  one-sided masks pass. The fix is `inf_b`/`nan_b`/mixed specials, then a
  zero-spend regrade of the stored rows. Also G-hsr's macro-arity misfile
  and the ISA-split golds.
- **Parked by Max:** C-150's remainder ("fine for now"). §3.8's paragraphs
  stay in the architecture ("dont split for now"). Constructions inside a
  template stay `uses`. repowise's cells stay on 0.49.0 (0.53.0 is out).

## Extraction, in order (no spend; each measured first)

1. **`cls(…)` in a classmethod** (rich 55 confirmable, flask 1, click 0 by
   step 0; `~/.hobbes/bench/cls-classmethod/`). The held-out icalendar cell is
   graded at 0.2.96-beta (`oracle-grading.md` §10.46) and its rule rows
   C1–C5 are pre-registered (`~/.hobbes/bench/heldout-icalendar/PREREG.md`).
   Next: the ADR (tier `syntactic`; a subclass-only site is C-60's declared
   target), then the build and the C-rows. C-184 is contained (ADR-168).
2. C-174's remainder, per language.

### Candidates, unranked

- **Not audited** (carried from the honesty audit): Terraform/HCL;
  repo-scale counts of any implicit shape outside Python's `__exit__`;
  Go's and Java's caller roll-up on real repos.
- **C-178's residue:** such a call has no lane B answer. External
  references to the stdlib's star re-exports keep their misnamed monikers
  (no repo edge).
- **Other languages' duplicate qualnames** (ADR-155 covers Python only;
  measured 2026-10-02, `~/.hobbes/bench/dup-qualnames-2026-10-02/RESULTS.md`).
  TS/JS and Java are clean. **Rust's impl-block collision is contained**
  (C-180, ADR-163, 0.2.87-beta): a fact at a later def of an id two impl
  headers share is refused and tailed `shared-qualname`. **Open, Max's
  call: the prevention**, ids that tell the impl blocks apart (Java's
  `~n`, or a self-type that keeps `*const`/`*mut` and the trait). It
  changes symbol ids; built, each later def gets a node and C-180 lifts
  (dagger would get back its 229 calls and memchr its 2). Go's second
  `init` is mapped into the node (C-183, ADR-166, 0.2.92-beta).
- **An `extends`-chain walk (TS/JS):** 104 rows at 0 contradicted (ajv 18,
  hono 8, xmpp.js 2, zod about 76), 0 on Preact. It would be a new kind of
  rule (a chain of lane B hops) for under a point per cell. Measured, not
  decided.
- **What click still misses** (806 on r3 before ADR-153): 460 closures
  (C-58), 215 methods (79 subclass overrides, which is ADR-126 §3's
  question; 90 duck-typed receivers and test doubles), 81 lambdas, 37
  classes, 13 functions. No decorator-line shape with more than 10 rows is
  left, and none has a syntactic rule ready.
- **Preact's test-file misses** (closures in `it` bodies, calls through
  `.d.ts` interface members, hook setters in locals): C-58's shapes.
- **C++ recall's remainder** (Max's Route A; ADR-132 to ADR-136 are
  built): C-162, C-145, C-164, and C-131 (parked). dagger's docs snippet
  zones were not re-ingested after the `corepack` fix.
- **Older, none started:** C-142's remainder (273 headers that nothing
  includes; ADR-138's route b). C's residue (W1: C-134's remainder,
  C-135's autotools, Meson and Bazel roots, C-133's unit 2 and its macro
  half; C-133's unit 2 only if a graded cell shows the cost). C-139's
  finer extent, also only if a graded cell shows the cost.
  C-140's remainder (ADR-112's route 2). Optional: a `lane_b` end-to-end
  case for ADR-135.

## Other no-spend work

- **W1/W3:** the decorated-declaration line convention, the C-15
  namespacing ADR, and `fetch-java` on the egress proxy.
- **Comparative queue**, if Max names it: the two SQLite tools in
  `comparative/field.md` (converters first), and syft's keys on a bigger
  box.
- **W0's remainder:** the registry-pulled image and the drift audit, when
  Max names them.
- **Carried, small:** `stringer` is not in the image; the Gradle attach
  route's residuals (C-67); `recall-collapsed` and H-23; ADR-105/P13; the
  C-98 residuals; `build-logic/` is recorded but not built (ADR-097); the
  tracker's area for a test-only session (row 17, `—`).

## Held, with spend (Max names the run and the ceiling)

- **Calvin** is closed on sqlite-vector (2026-09-29;
  `experiments/calvin/calvin-reassessment.md` §11–§13). It reopens only on
  a target where the job is not derivable, and choosing that target is a
  design question for Max. Before any model run, read the registers
  (`CV-1…21`, `MA-1…18`) and the Calvin README's "Instrument lessons".
- **Atlas-0** (held since 2026-09-07; `atlas-0.md` § Addendum, $22.28 of
  $25 spent). Max reads the B4 record, then decides:
  - which T carries the abstention act: the memorising T, or §A.7 branch
    2's computed `NO_EDGE` target (about $3.5–4, plus B1's cells);
  - the grid's second run (about $3.8, which takes the programme to about
    $26 against the $25 budget);
  - T_v2 for the v2 grid (the plateau at 3,100 is seed-variable);
  - the corrected item-1 section and §6.6 as amended, and the ADR number
    on *accepted*.
- **TTT** (`olmo3-ttt-results.md` §9–§10; the Modal apps are deployed and
  idle):
  - the 10,000-step point (about 6 A100-hours);
  - the 3,000-step adapter under the primary cell (about 0.7 A100-hour);
  - which of the cell's defect register entries (D-1–D-5) goes first;
  - ADR-092's four embedded decisions.
- Also held: the removal A/B re-run on the 7B; a second unseen repo
  through the cell; DeepSWE's decomposed protocol; `hobbes narrate` on
  this repo.
