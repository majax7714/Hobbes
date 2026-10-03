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

Last reviewed: 2026-10-03 (0.2.102-beta).

## Decisions open for Max (no spend)

- **C-181's residual** (ADR-164): a name that a stdlib import binds, and
  that an `except ImportError:` branch rebinds to a repo function, keeps
  lane A's `syntactic` edge to the repo function. Lane B's local answer
  cannot veto it (ADR-111). No graded cell writes this shape; the
  `ministdlib` fixture pins it. Proposed: refuse lane A's fallback where
  the same name is also bound by a stdlib import (a patch), or leave it
  registered.
- **C-187's prevention** (ADR-173 § Not decided here): one Terraform
  address in two directories is one node (terraform-aws-eks: 170 of 288
  reference sites touch a merged node). Route 1, ids scoped by directory
  (`tf:<dir>:<address>`, C-187 lifts, every multi-directory `tf:` id
  changes); route 2, C-180's refusal of later directories' facts; route 3,
  leave it named.
- **Extending the Python trace oracle** to key operator, iteration and
  truth-test dunders, which would unblock C-174's other Python shapes.
  Max, 2026-10-03: decided once extraction Phase 1's repo-scale counts
  (item 2 below) are taken back to him.
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
  On 2026-10-03: ADR-126 §3's "may reach through dispatch" section stays
  parked (no key confirms reach; click's 79 override misses stay C-58's);
  C-178's residue (pyparsing's star re-exports, 1,377 held-out misses) is
  held, since any rule would be fitted to pyparsing.

## Extraction, in order (no spend; each measured first)

Max approved this order on 2026-10-03 ("approved, all recommendations are
good"). Honesty audits come first (precedent 1), then the rules a key can
grade. Each rule is measured on a held-out cell picked before it is
measured.

**Phase 1, audits (an unnamed limit outranks recall):**
1. ~~Terraform/HCL~~ done at 0.2.102-beta (ADR-173, C-187 to C-193); its
   prevention is in "Decisions open for Max".
2. **C-174's implicit shapes at repo scale, outside Python.** A counter
   per language over the stored clones (Rust `?`/Drop/`for`/operators,
   Java try-with-resources/for-each/concatenation, Go `init`/Stringer, C++
   destructors/range-for, TS `for…of`/`await`/spread). Counts go into
   C-174's "Bites at". **Take them back to Max** for the trace-oracle
   decision below.
3. **Go's and Java's caller roll-up on real repos.** Port
   `~/.hobbes/bench/c176-ts-scope/probe.py` to the stored RTA and javac keys
   (both carry `sites[].caller`); widen C-176, measured on TS/JS only.
4. **C-164's remainder** reads "nothing tells you"
   (`constraints/extraction-cpp.md`): surface it if it is unsurfaced.

**Phase 2, rules a key grades:**
5. **Rust operators, `Deref`, `Index` (C-174),** ADR-131's shape: lane B
   already draws `uses` at the token; rustc's MIR key holds these as Call
   terminators. Probe first: that the `uses` target is the repo impl
   method, and that MIR's `fn_span` line is the token's. No Rust cell is
   held out; pick one.
6. **Then Rust's impl-distinct ids** (C-180's prevention, Max 2026-10-03:
   build it after item 5). Symbol ids change; C-180 lifts (dagger +229
   calls, memchr +2). Java's `~n` or a self-type that keeps
   `*const`/`*mut` and the trait.
7. **C++: a functor's `operator()` (C-146) and implicit conversions
   (C-162; args' 484 keyed misses),** with Route A's remainder (C-145,
   C-164) and dagger's docs snippet zones, not re-ingested since the
   `corepack` fix. No C++ cell is held out since §10.16; pick one.
8. **Python `__call__` on an instance held in an attribute** (C-174;
   rich's `self.highlighter(…)`; 35 misses on fitted cells, ADR-171).
   Optional and small; held out on voluptuous, marshmallow, toolz or
   tenacity.
9. **C-13:** detect jest globals in a TS/JS test file with no framework
   import. Small; only the `framework` field moves.

The other languages' C-174 shapes (Java, TS/JS, Go, C) get counts and
registration, not rules: their oracles key no implicit call, so a rule's
rows could not be graded.

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

## Other no-spend work

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
