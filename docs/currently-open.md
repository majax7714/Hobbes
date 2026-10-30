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

**Python:**
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

## The dev environment (`watterson`, ADR-181)

Its own open items stay in [`watterson/open-work.md`](watterson/open-work.md) ("Next up" first: item 11b,
hiding what the server does not back; then the app's Hobbes start, `tui` matching `chat`, the map file).
Left by the fold (2026-10-28):
- **The graph plugin's live look** after its logic moved into `logic.ts` (2026-10-30): it bundles and its logic
  is tested, but the panel is compiled by the TUI and only a live run shows it (`docs/watterson/README.md`).
- **A secret scan for vendored trees** (Max's to schedule, 2026-10-30): GitHub's alert #1 was opencode's
  documented fake; a scan on our side (upstream uses `gitleaks` with a fingerprinted ignore list) would catch
  the next import before it lands.
- **Live checks are Max's:** `watterson tui` (and `ask`, `chat`, `dispatch`, `job`) reach real harnesses;
  the fold verified them with the fake agent only. Re-point `~/.local/bin/watterson` at this repo's
  `bin/watterson`; `~/.local/bin/hobbes-proxy` points at a missing `~/hobbes/go/bin`.
- **The TUI is not in CI** (Bun 1.4.2 is fetched by `tui/install.sh`; CI's graph job runs only that, to
  install the workspace); whether to add the TUI's build and tests is open.
- **Our own tests for the trimmed fork** (Max, 2026-10-29: "we can tackle independently later, add our
  own tests"). DEC-028 deleted opencode's tests outside `packages/tui`. The 222 modules that lost every
  guard are accepted by name in `.hobbes/accepted-lost-guards.yaml` (ADR-185), and since its amendment
  (2026-10-30) the fold's 1,108 modules no test ever reached too. Remove a module from it once a test of
  ours reaches it. **The record names 1,252** (2026-10-30): the trim's 132, the fold's 1,108, the 12 with
  no code. Before the amendment, 179 remained (2026-10-29): `util`'s ten have 49 tests of ours, each
  checked by mutation to catch a fault no other case catches; 15 more left when the review learned to
  read the checkout's dependency trees (ADR-186, C-198), which showed a TUI test already reaching them.
  Of the 179, 12 are a second entry (Max, route 3a): no runtime logic of their own (types, a `.d.ts`,
  re-exports), never to get a test of their own; **167 wait for tests** (`latex`'s six done: 86 cases;
  `merman`'s `core`, nine modules: 64 cases; its top level, three listed and `palette`: 13). `merman`'s
  six diagram families came off the record because its renderer's cases reach them, but those cases draw
  their expected output with the families' own code: they pin the palette mapping, not what a family
  draws, so the families still get tests of their own, next in order (flowchart done: 97 cases across six
  files; next gantt, gitGraph, sequence, state, timeline). The check every new case is held
  to is `bench/subsume/` (no case that only fails when another does). Order (Max): `latex`, `merman`,
  `core/shell`, `codemode`, then `schema`'s decoders, then the effectful packages.
  - **Fork bugs our tests pin, not fixed** (found writing `latex`'s): `maxExpand: N` allows N−1 macro
    passes (`maxExpand: 1` refuses any macro, `parser.ts:91-120`); `maxDepth` counts braces in
    `assertNestingDepth` but the parser counts the atom inside too (N−1 effective); `a+-b` draws
    `a+ - b` (`normalizeBinaryRole`); dead code at `parser.ts:332`. A fix changes the pinning test.
  - **Found writing `merman`'s `core`:** `drawDiagramDiamond` 2, 3 or 5 wide puts both caps on one column
    (`capLeft === capRight`, or crossed at 2), the right cap's glyph over the left's (`core/drawing.ts:236`);
    4 and 6 or more are whole. Unreachable from the fork: its one caller, the flowchart's decision node,
    is always odd and at least 7 wide (`flowchart/layout.ts:116-121`).
  - **Found writing `merman`'s flowchart layout:** a node outside every frame can be laid out on top of a
    framed node. Smallest case: `flowchart TD`, `subgraph G0` {B}, `subgraph G1` {A}, `E --> A`, `A --> F`,
    `A --> A`: the self loop widens G1's frame, the separation pass moves the frames, and E lands over B inside
    G0 (B's label hidden). Pinned by `test/flowchart/layout.test.ts` ("a fork defect, pinned"); a fix changes it.
  - **Found writing `merman`'s flowchart drawing:** of two parallel edges top-down (`A --> B` twice), the first
    runs from A's right side straight down to B's right side and draws its head `▼` there, pointing past B rather
    into it; the second lane ends on the same cell. Pinned by `test/flowchart/drawing.test.ts`; a fix changes it.
  - Possible later, not asked: ADR-117 exempts a Python module with no code from the guard question; a
    TS module of only types or re-exports is still asked, hence the second entry.

## Decisions open for Max (no spend, not extraction)

- **Calvin's findings, proposed and not registered:** G-diff coverage. The
  driver never puts inf/NaN in `b` alone and never mixes inf kinds, so
  one-sided masks pass. The fix is `inf_b`/`nan_b`/mixed specials, then a
  zero-spend regrade of the stored rows. Also G-hsr's macro-arity misfile
  and the ISA-split golds.

## Other no-spend work

- **A flaky dev-environment test:** `test_watterson_live_session.py::TestTurnLabel::test_head_graph_clean_then_edited`
  failed in 2 of 5 full pytest runs on 2026-10-28, each on a box loaded with ingests; it passed alone and in
  the other 3. It works in its own temp repo. Cause not found; read its failure output before guessing.
- **pyrefly as Python lane B** (route 3's probe, 2026-10-28, BUILDLOG): 98% agreement with scip-python on
  click, about 6× faster on rough numbers, not a drop-in. Next, if Max names it: a held-out Python cell picked
  first; whether pyrefly's LSP go-to-definition names an inherited or `super()` member truly (its batch export
  names it by the receiver class); refusing dead-branch rows or pinning the platform; a canonical sort and a
  pinned interpreter and config for determinism; and how an unresolved import is told from a resolved one.
- **ADR-184's levers not built:** a TS lane A cache (its own ADR: a read-set key, a hit-equals-fresh test),
  Python lane A on a process pool, tree-sitter queries in place of walks, and lane B units within one
  language in parallel (the tool caches' concurrency first).

- **H-39** (`oracle/oracle-defects.md`): the trace oracle's re-entrance guard is one flag for every thread, so a
  call on one thread while another sits in a callback is lost. No pair lost on the four standing Python cells. A
  thread-local guard moves every key with a threaded test, so it is Max's call whether to fix it and regenerate.

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
