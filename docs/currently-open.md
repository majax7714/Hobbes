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

Last reviewed: 2026-10-04 (0.2.118-beta). Extraction trimmed to what is open; Route 1 (Rust) done.

## Extraction (no spend; each rule measured on a held-out cell picked first)

Max's 2026-10-03 order is worked through: the Phase 1 audits (Terraform/HCL, C-174's counts, Go's and
Java's caller roll-up, C-164's remainder) and items 6–9 (Rust impl ordinals, C++ functors, Python
`__call__`, C-13) shipped at 0.2.102–0.2.110-beta; the CHANGELOG has each. What is left is below. The
other languages' C-174 shapes (Java, TS/JS, Go, C) get counts and registration, not rules: their oracles
key no implicit call, so a rule's rows could not be graded.

### Routes waiting on Max

**TypeScript / JavaScript** (each moves the TS symbol set):
- **ADR-179 (C-176's floor, route 1b (a), scope only): built on branch `adr179` (`af7d030`), not merged.**
  The pre-registered held-out draw (DRAW-RULE-2, 42–80) took no cell (71 vacuous, 75/78 thin, 76
  refused). On the 13 fitted cells Q1–Q5, Q7 held; Q6 missed as worded (more callers re-filed than
  predicted: callbacks inside a member). Routes for Max in `RESULTS-1b.md`'s record and the handoff: merge on
  the fitted cells, or draw again under a new pre-registered window. Then 2a route (i).
- **Class-property functions**, measured (2a, 2026-10-04; zod's cell record, last section). The 1,029 pairs
  are mostly an alias chain: zod 1,230 of 1,274 rows reach `ZodX.create` through `z.object` → `export *` →
  `export { objectType as object }` → `const objectType = ZodObject.create`, and the index writes nothing at
  the token. Sized routes, for Max: (i) a function-literal field of a top-level named class is a `method`
  symbol, drawn where lane B names it at the token, `semantic` (zod 42, hono 81 rows); (ii) leave the alias
  registered (a multi-hop `syntactic` read held by one cell). Max approved (i) after 1b, (ii) the
  alias stays registered (2026-10-04). Not built.
- **The gate's map reason for `attr-call`** (0.2.119-beta left it): `gate.py` files the class under
  `dynamic-dispatch`; a re-exported alias site (zod 1,232) is not dispatch. The closed vocabulary is
  `MAP_REASONS`; changing it is Max's.

**Python:**
- **Whether to extend the standing trace oracle (C-174).** Measured on all four keyed cells, contained
  (`~/.hobbes/bench/c174-counts-2026-10-03/python/trace-run/`; click and rich run 2026-10-04): implicit
  rows flask 208, structlog 191, click 676, rich 1,308 (13.4%, 15.4%, 17.9%, 26.0% of confirmed), mostly
  property getters (rich also `__eq__` 115, `__str__` 90, `__getitem__` 69); each cell's regular pairs
  identical to its standing key; recall falls by denominator only (55.7% → 51.8%, 77.8% → 69.5%,
  82.0% → 71.5%, 93.6% → 75.3%); one Hobbes edge changes bucket (rich, `unobserved` → `suspect`), none
  is contradicted. Graphs graded are the cells' on-disk ingests (0.2.99/0.2.100-beta).
- **C-181's residual** (ADR-164): a name a stdlib import binds that an `except ImportError:` branch rebinds
  to a repo function keeps lane A's `syntactic` edge; lane B's local answer cannot veto it (ADR-111). No
  graded cell writes it; `ministdlib` pins it. Routes: refuse lane A's fallback where a stdlib import also
  binds the name (a patch), or leave it registered.
- **ADR-156 and fixture values:** the `with` rule does not build on ADR-145's `syntactic` fixture-value
  edges (40 of flask's items, `with app.app_context():`). Allowing it would stack one `syntactic` rule on
  another.

### Open, nothing proposed (opens when a cell shows it)

- **flask's PEP 420 `sansio/` naming:** lane A and scip-python both name the modules `app`, `scaffold`,
  `blueprints`; references join. Register it if it bites (two namespace directories each holding
  `app.py` would collide, C-28). The missing `Flask → App` is C-185's.
- **`npm ci` refused three of four lockfile-bearing JS repos** (C-23 in C-165): whether "pinned or
  declined" falls back to anything.
- **ADR-050's amendment, prevention** (C-23): staging a local-path dependency or a workspace's members
  into the install. No graded cell meets either shape.
- **C++ Route A's remainder** (C-145, C-164): no key reads a caller.
- **C-13's residue and C-194:** reading a runner's own globs (8 of 320 files), or inventorying a suite
  that is not test-named.

### Registered and gated (closed as work until the trigger)

- **C-171's Python residual** (`pysource` overflows near 600 levels):
  until a repo meets it.
- **C-133's unit 2 and its macro half; C-141's finer extent:** until a
  graded cell shows the cost.
- **C-142's remainder** (273 headers nothing includes, ScummVM only;
  ADR-138's route b), **C-134's remainder, C-135's** autotools, Meson and
  Bazel roots: no graded cell shows them. Optional: a `lane_b` end-to-end
  case for ADR-135.
- **Closures and duck-typed receivers** (click's and Preact's test-file
  misses): C-58's shapes, with no rule ready. Click's bucket counts (806
  on r3) predate ADR-153; re-measure before using them.
- **W1's parked tail** (detail in `workstreams.md` W1; each opens when Max
  names it): the Java follow-ups (a Spring pack, Maven toolchains, a
  two-pass `java-build`, a bytecode RTA oracle, Kotlin lane A); C-67's
  Gradle leftovers (a late `compilerArgs`, Kotlin under the plugin,
  external symbol names); a `bench-rust` pack; `hobbes cache` hygiene.
- **Parked by Max:** C-150's remainder ("fine for now"). §3.8's paragraphs
  stay in the architecture ("dont split for now"). Constructions inside a
  template stay `uses`. repowise's cells stay on 0.49.0 (0.53.0 is out).
  On 2026-10-03: ADR-126 §3's "may reach through dispatch" section stays
  parked (no key confirms reach; click's 79 override misses stay C-58's);
  C-178's residue (pyparsing's star re-exports, 1,377 held-out misses) is
  held, since any rule would be fitted to pyparsing.

## Decisions open for Max (no spend, not extraction)

- **Calvin's findings, proposed and not registered:** G-diff coverage. The
  driver never puts inf/NaN in `b` alone and never mixes inf kinds, so
  one-sided masks pass. The fix is `inf_b`/`nan_b`/mixed specials, then a
  zero-spend regrade of the stored rows. Also G-hsr's macro-arity misfile
  and the ISA-split golds.

## Other no-spend work

- **H-38** (`oracle/oracle-defects.md`): read the trace oracle's
  `__code__`/`__func__`/`__wrapped__` through the type, with a fixture.

- **W1/W3:** the decorated-declaration line convention, the C-15
  namespacing ADR, and `fetch-java` on the egress proxy.
- **W5:** C-140's remainder (ADR-112's route 2; a forged edit line in a
  doer's flight log, detail at C-140 in `constraints/dispatch-harness.md`).
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
