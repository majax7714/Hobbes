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

Last reviewed: 2026-10-03 (0.2.87-beta).

## Decisions open for Max (no spend)

- **The graph job is red** (since 2026-09-26). It reviews from the last
  green run, `57e4be2` (ADR-114). Unguarded new modules went from 22 to 5
  on 2026-10-02. Left: `lattice` and `dedupe` (value-only, C-156; they
  stay red under the current rule), and `draw`, `make_fixture` and
  `modal_e1` (untested bench scripts). Proposed: exempt a docstring-only
  module (an ADR-117 amendment, a patch), add cheap tests for the three
  scripts, and decide on `dedupe`, which is kept as E3's record as it ran.
- **C-179 surfacing:** a module loaded by `importlib` or `__import__` draws
  no import edge. It is **unsurfaced** (debt). The route is Max's call:
  name the load where `tests_guarding` says "unguarded".
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
- **flask's `src/flask/sansio/`** has no `__init__.py` (PEP 420). Lane A
  names its modules `app` and `scaffold`. The `implements` join places
  `App → Scaffold` but not `Flask → App` (`graph["implements"]["outside"]`
  79). Nobody has read why. Whether to register it as a constraint is
  Max's call.
- **Verify's `classify`** returns `error` for a row that errors on *both*
  trees, and `FAILING` holds `error`. So a fixture repo's own
  uncollectable test (`minifixval/tests/test_runner.py`) failed a verdict
  with 0 regressions (session `54cf`). A route is proposed; nothing has
  changed.
- **`npm ci` refused three of four lockfile-bearing JS repos** (counted
  under C-23 in C-165). Open: whether "pinned or declined" falls back to
  anything. Nothing is proposed.
- **The ingest's `.gitignore` edit:** register it as a constraint, or
  change it.
- **Calvin's findings, proposed and not registered:** G-diff coverage. The
  driver never puts inf/NaN in `b` alone and never mixes inf kinds, so
  one-sided masks pass. The fix is `inf_b`/`nan_b`/mixed specials, then a
  zero-spend regrade of the stored rows. Also G-hsr's macro-arity misfile
  and the ISA-split golds.
- **Parked by Max:** C-150's remainder ("fine for now"). §3.8's paragraphs
  stay in the architecture ("dont split for now"). Constructions inside a
  template stay `uses`. repowise's cells stay on 0.49.0 (0.53.0 is out).

## Extraction, in order (no spend; each measured first)

1. **`cls(…)` in a classmethod** (rich 57, pyparsing 17). **The held-out
   cell is collective/icalendar v7.3.0** (`138c8453`; Max, 2026-10-02): 81
   `cls(…)` sites by an `ast` scan, 18,166 tests offline, nothing ingested
   or keyed yet (`~/.hobbes/bench/heldout-scout-2026-10-02/RESULTS.md`;
   dnspython v2.8.0 is the spare). Pre-register it before the ingest and
   the key; its tests live in the package (`src/icalendar/tests`). pyparsing
   stays held out. On the new cell, also count the
   `semantic` rows whose line does not hold the target's name (C-178's
   check), because a trace key grades calls only.
2. C-174's remainder, per language.

### Candidates, unranked

- **Not audited** (carried from the honesty audit): Terraform/HCL;
  repo-scale counts of any implicit shape outside Python's `__exit__`;
  Go's and Java's caller roll-up on real repos.
- **scip-python names no occurrence for flask's `urlsplit`**, at either the
  import or the call (`app.py:15`, `:725`). Not read yet. A single-repo row.
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
  (dagger would get back its 229 calls and memchr its 2). **Go's second
  `init`** files its lane B `uses` under the module (dagger, 89 rows in 22
  files): unregistered, not yet contained.
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
