# Extraction — TypeScript and JavaScript

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-12 — Imports across tsconfig zones do not resolve — *narrowed and surfaced 2026-08-16*
- **Cannot tell you:** that package A imports package B through a **path
  alias defined in B's zone** (or any custom resolver) — the alias map is
  another program's compiler config, which this walk does not interpret.
  The common monorepo forms resolve since ADR-041: a **relative**
  specifier resolves against the repo's own file set (zones
  notwithstanding — a path is not a compiler configuration), and a bare
  specifier matching one of the repo's **own package names** resolves to
  that package's entry or subpath, read from `package.json` like every
  other manifest fact. Both arms are lane A's alone, so cross-zone edges
  carry `syntactic` tier — the honest description of their evidence,
  since each zone's indexer still cannot see out.
- **Because:** each zone is a separate ts-morph Project (and a separate
  indexer run), and cross-program resolution through another zone's
  compiler options is still not attempted — only the two
  configuration-free forms are.
- **Bites at:** monorepo module edges behind aliases or custom
  resolvers; previously *all* cross-zone edges, ranked #1 in this
  register ("missing exactly where the architecture is most
  interesting").
- **You find out:** **surfaced** — a specifier that resolves nowhere and
  names no plausible package becomes one `imports-unresolved` record per
  file, specifiers named, in `extraction_errors` and the ingest WARNING.
  Asset imports (`./index.css`) are excluded from the records: a file
  the graph deliberately does not model is not a resolution failure, and
  the first run of the floor proved they would bury the real records.
- **Source:** M6, `future_additions.md` → per-package tsconfigs;
  narrowed and surfaced by ADR-041 (2026-08-16).

### C-13 — Test files using injected globals report framework `unknown`
- **Cannot tell you:** whether a test file with no framework import is
  jest or vitest.
- **Because:** framework detection reads imports, and globals-style suites
  import nothing.
- **Bites at:** the per-test `framework` field only; the tests are still
  inventoried.
- **You find out:** **surfaced** — the field literally says `"unknown"`
  rather than guessing.
- **Source:** ADR-021, M6.

---

### C-63 — A call through an element access (`obj[key]()`) draws no edge — *surfaced 2026-09-05*
- **Cannot tell you:** *what* `table["norm"](s)`, `xs[Symbol.iterator]()`
  or `table[k](s)` calls. The callee is an expression, so there is no
  identifier for the semantic lane to put an occurrence on and no
  `calls` edge is drawn, whichever lane could have resolved the key's
  target. Lane B does emit the `uses` reference for that target where
  it has one. **Since 2026-09-05 the site is counted:** lane A records
  it under the marker name `<expr>` (the helper's `EXPR_CALLEE_NAME`;
  `pysource.EXPR_RECEIVER` alone for Python's `handlers[0]()`,
  `getattr(x, "y")()`, `(a or b)()`, `f()()` — C-80's residual), so it
  sits in `resolution_coverage`'s denominator as `unresolved` and the
  tail classes it `expr-callee` (ADR-045, amended). Before that it was
  not a site at all — uncounted, and a dispatch table read as accounted.
- **Because:** the site detector matched identifier and property-access
  callees only; the element-access shape was never in the fixture until
  `minits/src/lookup.ts` (2026-08-27), where the oracle lane's A-4
  observation found the three shapes drawing zero edges. Counting the
  site is the honest half; drawing the edge would need a name, and a
  literal key (`table["norm"]`) that the checker could bind to a
  property is the one candidate — a property is below the symbol floor
  (C-9), so the edge would be `below-floor` at best; not attempted.
- **Bites at:** dynamic-dispatch tables (`handlers[name](req)`),
  `process.env["X"]`-style reads that are calls, well-known-symbol
  protocol calls, generated clients indexed by operation name. The
  oracle lane grades the literal-key shape as a recall miss
  (`static→function`, minits 4/5); ajv `f177fe3` has 1 computed-key site.
- **You find out:** **surfaced** (2026-09-05; *unsurfaced* from
  2026-08-27 until then) — the per-file coverage row counts the site,
  its `tail` carries `expr-callee`, the ingest summary's *cannot
  resolve* line and `list_blind_spots` print the class with its gloss
  ("the callee is itself an expression … trace the value's origin
  yourself"), and `tail_classes_available` names Python and TS/JS as
  the languages that report it — Go, Rust and Java still do not count
  the shape (C-32).
- **Source:** the oracle lane's A-4 fixture observation, 2026-08-27
  (`bench/oracle/README.md` D-O4 element-access bullet; H-17);
  surfaced 2026-09-05 with C-80's residual, ADR-045 amended.

### C-97 — A member call on a union-typed receiver draws no edge when the members resolve the member differently — *surfaced 2026-09-09*
- **Cannot tell you:** what `n.render()` calls when `n: A | B` and both
  `A` and `B` declare `render`. No `calls` edge is drawn from either
  lane. Before ADR-104 the semantic lane drew `A.render` — the *first*
  member's declaration, at semantic certainty — and lane A's resolver
  made the same pick, so lane agreement could not see it. The static
  answer is "one of these"; naming one is a possible dispatch presented
  as the resolved target (the oracle lane's `static→union-member`,
  ajv 3 rows and hono 7).
- **Because:** scip-typescript and the checker's symbol for a union
  property both carry every member's declaration and both take the
  first; `tsc`'s resolved signature takes a declaration too (the first
  member's on a two-member union, the shared base's on ajv's eleven).
  Hobbes abstains rather than pick: the helper (facts v5) records the
  site `ambiguous: "union-member"`, the join vetoes lane B's occurrence
  there, and the tail counts the site (ADR-104). A union whose members
  inherit one declaration, and `T | undefined`, are not the shape and
  resolve as before.
- **Bites at:** `who_calls` on an override reached only through a union
  of its siblings (ajv's `If.render` from `ParentNode.render`), and
  every derived context built from call reach across a discriminated
  union — the TypeScript face of C-58's interface dispatch. Measured
  on the two graded repos: ajv 10 sites (the three contradicted rows and
  six the grader had confirmed as `tsc`'s own first-member pick), hono
  6 of 36 union-receiver sites (the seventh is C-98's).
- **You find out:** **surfaced** — the per-file coverage row counts the
  site `unresolved`, its `tail` carries `union-member`, the ingest
  summary's *cannot resolve* line and `list_blind_spots` print the class
  with its gloss ("read the union's members to see what can run"), and
  `tail_classes_available` lists it for TS/JS only (C-32).
- **Provider:** scip-typescript resolves a union member access to one
  member's declaration (P9). Hobbes owns the veto; the provider's shape
  is unchanged upstream.
- **Source:** ADR-104; the ajv record's 2026-08-28 triage and the hono
  record's 2026-09-09 regrade; the fixture `minits/src/union.ts`.

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-98 — Lane A's checker ran with no compiler options under a solution-style `tsconfig.json` — *registered 2026-09-09, lifted 2026-09-10*
- **Was:** the helper built one ts-morph project per zone from the
  nearest `tsconfig.json` by path, and a solution-style config —
  `files: []` and project `references`, hono's root, any `tsc -b`
  monorepo — carries no compiler options, so the checker ran at its ES5
  defaults: `Array.flat` unknown, a receiver reached through such a call
  `any`, and every lane-A observation that needs the type absent —
  `callee`, `origin` and C-97's abstention alike — while lane B, which
  follows the references (C-90), resolved. On hono the one row left
  after ADR-104 (`src/jsx/components.ts:18`, `c.toString()` inside
  `children.flat().map(…)`) was this: lane B drew `JSXNode.toString`
  with nothing to veto it, 767/768. *Partial* while it stood: the
  artifact said nothing about the empty options.
- **Lifted by — the technique:** `zoneTsconfig` in
  `tsextract/extract.mjs`, the lane-A analogue of C-90's rule. The
  nearest config is read raw (`ts.readConfigFile`, no disk walk) and
  tested by `isSolutionTsconfig` — `references` present, no non-empty
  `include`/`files`, and one of the two keys written (C-99). An ordinary
  config is the zone as before. A solution config's references are
  resolved by the compiler (`ts.getParsedCommandLineOfConfigFile`,
  `resolveProjectReferencePath`), in the order written, inside the repo
  only; a referenced project that is itself a solution is followed
  transitively (a `seen` set stops cycles); the first referenced project
  whose inputs — the compiler's own `fileNames` after
  `extends`/`include`/`exclude`/`files` — contain the file is its zone,
  parsed once per config per extraction. `tsconfigs` in the facts names
  the zones actually used. A file no referenced project claims joins
  the zone-less default project (ES2022, Bundler, JSX preserve — the
  options lane B's generated config mirrors, C-90) and the helper says
  so: one `errors` record per solution config (stage
  `tsconfig-unclaimed`, the files sampled), printed by the ingest as a
  degradation line. **Measured on hono** (same clone, commit and key as
  the 2026-09-09 records; artifacts
  `~/.hobbes/bench/comparative/hobbes-hono-build-r3/`): `src/` is
  claimed by `tsconfig.build.json` and its tests by
  `tsconfig.spec.json`; **768/768 (100.0%), 0 contradicted**, poison
  check 0 falsely confirmed of 4,471, recall 55.2% (775/1,403, one
  pair more); **`union-member` 15 sites in nine files where there were
  0** — the sites the zone types once it has options, abstained by
  C-97; attr-call 7,819 → 7,795, external-origin 37 → 52,
  fallback-resolved 154 → 158; capture 39.7% → 39.6% (the abstentions
  leave the resolved count); lane agreement byte-identical to the old
  helper's (4,332 both-resolved sites, the same one line-grain
  disagreement — two `text()` calls on one line of
  `src/middleware/body-limit/index.test.ts` — module edges 42 lane A
  only / 635 lane B only); 22 root files no referenced project claims
  (`benchmarks/deno/*` among them) reported once. This repo has no
  solution-style config; its graph did not move. Tests: two cases in
  `tsextract/test/extract.test.mjs` — the hono shape end to end (the
  alias resolves, `flat` is typed, the union receiver is abstained, the
  unclaimed file is extracted and reported, a nested ordinary config and
  a C-99 config are their own zones) and a solution reached through a
  solution with a cycle and a reference outside the repo. **The lane B
  half (later the same day, 0.1.6-beta):** `scipsource.ts_zone_map`
  asks the helper for the same map (`--zones`), and `_index_ts_zone`
  passes scip-typescript the referenced projects that claim the zone's
  files as positional projects, each under its own config, plus
  `tsconfig.hobbes-unclaimed.json` — the generated config for the files
  none claims, written beside the solution file, which stays intact for
  any project that `extends` it; the map unavailable is a recorded
  degradation and the zone falls back to the generated config over the
  solution file. Tests: the projects and configs a solution zone stages
  (`run_helper` captured), the fallback, the map as the helper's answer,
  and a `lane_b` case in the image where a `paths` alias that lives only
  in the referenced projects' base config resolves in lane B. On hono
  after both halves: 768/768 unchanged with one edge moved from the
  syntactic to the semantic tier (727 semantic confirmed), lane
  agreement 4,332 → 4,336 both-resolved sites, the same one line-grain
  disagreement.
- **Residual edge cases:** two referenced projects that both include a
  file are two programs to `tsc -b`; lane A gives the file to the first
  named, lane B indexes it in both (identical sightings merge). A
  solution config's own `compilerOptions` (legal, applied by `tsc` to
  nothing) are not applied to unclaimed files — those run under the
  defaults in both lanes and are reported. A file no project claims is
  its own program in both lanes now, so its references into a claimed
  project's files take C-12's cross-program shape. Measured on hono's
  root zone, lane B alone, old shape against new (`_index_ts_zone` with
  and without the map): references 27,682 → 37,216 and external
  references 25,636 → 35,441 — the referenced projects' options resolve
  far more than the generated defaults did — while the module-pair set
  loses 17 and gains 8: fifteen of the lost run from unclaimed files
  (`benchmarks/deno/hono`, `runtime-tests/deno/*`) into `src/`, edges
  lane A never drew; two are inside `src/`, a test file now in the spec
  project whose reference lands elsewhere; the eight gained are
  `src/context` to the middleware modules that augment it. Lane B's
  module edges on the whole repo 1,483 → 1,474 — the price of reading
  the configs as `tsc -b` does, paid for the imports of files no project
  owns.
- **Source:** the hono regrade of 2026-09-09 (ADR-104 § Consequences);
  lifted 2026-09-10 on the lead's direction, the first no-spend item of
  the comparative review's queue.

### C-99 — A tsconfig with `references` and neither `files` nor `include` was taken for a solution config, in both lanes — *registered and lifted 2026-09-10, the same session*
- **Was:** lane B's `is_solution_tsconfig` (C-90) called a config a
  solution when it had a `references` block and no *non-empty*
  `include`/`files` — so a config that names references beside its own
  `compilerOptions` and leaves both keys out, which the compiler reads
  as *include the whole directory*, was replaced on the stage by the
  generated config (ES2022, Bundler, JSX preserve) and its own options
  — `jsx: react-jsx`, `jsxImportSource`, `types` — never reached
  scip-typescript. The first draft of C-98's lift mirrored the rule on
  the lane-A side and sent those files to the default project, reporting
  them unclaimed — which is how it was found: hono's six
  `runtime-tests/*/tsconfig.json` are this shape (`extends
  ../../tsconfig.base.json`, options, `references:
  [../../tsconfig.build.json]`, no `include`), and the 2026-09-09 hono
  records indexed those six zones under the generated config. Silent
  while it stood: a replaced config is not reported.
- **Lifted by — the technique:** the compiler's rule, checked against
  `ts.getParsedCommandLineOfConfigFile` (a config with `references` and
  neither key lists every file under it; `files: []` or `include: []`
  lists none): a solution config has `references`, no non-empty inputs,
  **and** at least one of the two keys written. `is_solution_tsconfig`
  (lane B: `_TS_INPUT_KEY` beside `_TS_ANY_INPUTS`) and
  `isSolutionTsconfig` (lane A) both apply it; tests in
  `TestReferencedTsConfigs` (the hono shape is a project, `files: []` a
  solution) and the C-98 helper case (`runtime/tsconfig.json` is its own
  zone). On hono the unclaimed reports drop from seven configs to one
  (the root); the six zones index under their own options; the graded
  cell (`src/`) does not move.
- **Residual edge cases:** the two lanes read the keys by different
  means — a regex over the text in lane B, the parsed JSON in lane A —
  so a `"files":` inside a comment fools lane B's reading, not lane A's.
  A key written with a non-empty value beside an empty other key is a
  project by both rules and by the compiler.
- **Source:** found 2026-09-10 while lifting C-98 — the first hono
  ingest under the new helper reported `runtime-tests/*/tsconfig.json`
  as solution configs with files no project claimed.

### C-90 — A tsconfig that `extends` or `references` a config off the zone's walk-up path was indexed without it — *registered and lifted 2026-09-03, the same session*
- **Was:** staging copied a zone's sources plus the `tsconfig.json` /
  `jsconfig.json` / `package.json` on the zone's walk-up path and,
  deliberately, parsed no tsconfig (comments, no JSON5 dependency). A
  config reached only through `extends "./config/tsconfig"` (date-fns
  `pkgs/dev`: `error TS6053: File './config/tsconfig' not found … no
  files got indexed`) or a solution-style root (`include: []` +
  `references`: every referenced project *"missing tsconfig.json"* on
  the stage, then *"no files got indexed"* once they were there) was
  not staged, and the zone's every site fell to lane A's floor — 2 of
  date-fns's 15 zones, found once C-74 gave it lane B. *Partial*, loud,
  while it stood.
- **Lifted by — the technique:** two pieces. (1)
  `scipsource.referenced_ts_configs` scans each staged tsconfig for
  `"extends"` (string or array) and the `"path"` entries of a
  `"references"` block — a regex over the two keys, comment-tolerant,
  still no parser — resolves relative targets against the config's
  directory (a directory means its `tsconfig.json`; a name without
  `.json` is tried with it), stages what lies inside the repo,
  transitively; a bare `extends` (`@scope/pkg/tsconfig`) is a package,
  left to `node_modules` (mounted since C-74). (2)
  `is_solution_tsconfig`: a config with `references` and no non-empty
  `include`/`files` describes no inputs, so the zone gets the
  **generated** config listing its own files, written over the staged
  solution file — the files no referenced project claims
  (`vitest.config.ts`, a codemod) are exactly that zone. **Measured on
  date-fns:** `pkgs/dev` indexes after (1) (+3 semantic calls); the
  root after (2); **15 of 15 zones, no `scip-typescript` record, lanes
  7,601 / 0, capture 80.1%** (79.7% before C-89/C-90). Tests:
  `TestReferencedTsConfigs` (three).
- **Residual edge cases:** an `extends` inside a *package's* tsconfig
  (reached through `node_modules`) is the package's to resolve, not
  staged — the mount covers it. A referenced project that is not
  itself a zone (no TS file under it) is staged as a config and never
  indexed; harmless. `tsextract` (lane A) reads tsconfigs its own way
  through ts-morph and was unaffected throughout — until C-98 named its
  own face of the gap (a solution config loaded as a zone's options),
  lifted 2026-09-10 by the same rule on the lane-A side. **One bit of
  the rule was wrong (C-99, 2026-09-10):** a config with `references`
  and *neither* `files` nor `include` was called a solution, and the
  compiler's default include is the whole directory — hono's six
  `runtime-tests/*` zones had been replaced by the generated config.
  Fixed in both lanes. **And the technique itself is superseded for a
  solution zone (0.1.6-beta, C-98's lane B half):** the generated
  config is no longer written *over* the solution file but beside it,
  for the unclaimed files only; the referenced projects are indexed
  under their own configs.
- **Source:** the date-fns re-ingest of 2026-09-03 after C-74 and
  C-89; fixed the same night on the lead's direction ("fix c-90 too").

### C-89 — An overloaded TS function or method was placed at its implementation, not its first signature — *registered and lifted 2026-09-03, the same session*
- **Was:** `tsextract` emitted a symbol's line from ts-morph's
  declaration node, which for an overloaded function or method is the
  **implementation**; scip-typescript places the declaration at its
  **first overload signature**. The two lanes then named different
  lines for one symbol: on date-fns (re-ingested 2026-09-03 after C-74
  gave it lane B) **54 lane disagreements**, every one this shape on
  three functions (`normalizeDates` 19 vs 4, `intlFormat` 123 vs 48,
  `tz` 280 vs 158) — and, worse, the projection found no lane A symbol
  starting at SCIP's line, so those calls drew no edge and were counted
  `below-floor`. Never seen before because kbet, ajv and cheerio were
  graded before a workspace repo indexed, and this repo's `web/` has no
  overloads. Surfaced (loud: `hobbes lanes` exit 1) but wrong in the
  graph while it stood.
- **Lifted by — the technique:** `declarationStart` in
  `tsextract/extract.mjs` — a function or method with overloads starts
  at its first overload's line (`getOverloads()[0]`) and ends where the
  implementation ends; the tsextract test covers a function and a
  method beside a plain one. Confirmed on date-fns's re-ingest (numbers
  in the BUILDLOG).
- **Residual edge cases:** an overload set split across files
  (declaration merging, `.d.ts` beside `.ts`) is still two symbols; an
  overloaded *constructor* is not a symbol at all (C-9's kinds), so
  nothing changes there.
- **Source:** the date-fns re-ingest of 2026-09-03; fixed the same
  hour.

### C-11 — JS/TS test reach was per *file*, not per test case — *lifted at V2.M3*
- **Was:** every case in a test file shared the file's whole
  imports-plus-calls closure, so `tests_guarding` and behavioural coverage
  **over-reported** for JS — the one place in the system where a limit
  inflated a number rather than shrinking it, and unsurfaced, because a JS
  row looked exactly like a precise pytest row.
- **Lifted by — the technique:** the tsextract helper records each test
  case's source extent (the `it()` callback's range) and the join carries
  ranges, so a call is attributed to the case that encloses it. Measured
  on kbet: reach went from a flat 7.3 symbols for every case in a file to
  per-case, with cases in the same file now differing.
- **Residual edge cases:** calls outside every case — a `beforeEach`, a
  `describe` body — are attributed to **all** cases in the file. That is
  the technique's deliberate boundary, not a leak: that code really does
  run for each case. And the technique attributes only *calls*; the
  under-report that remained for render-only component tests became its
  own entry, **C-24**, lifted in turn below.
- **Source:** ADR-021 (the limit), V2.M3 (the lift). Superseded by C-24,
  which was the honest residue.

### C-24 — A test that only *rendered* a component did not reach it — *lifted 2026-08-15*
- **Was:** reach is the closure over **call** edges, and `<BetCard />` was
  a JSX element, not a call site — a `uses` edge reach deliberately did
  not follow, so a render-only test showed an empty `reaches` that read
  as "nothing guards this". The entry's asymmetry argument (under-report
  rather than over-report) held while the choice was between two
  inaccuracies; the fix removes the inaccuracy instead of picking a
  direction.
- **Lifted by — the technique:** the tsextract syntax provider records a
  JSX instantiation as a call site (owner-approved, 2026-08-15) — the
  component executes when the element renders, so the site is a call in
  the sense reach cares about. The join then treats it like any other
  site: lane A's fallback where it resolves, promoted to `semantic`
  where SCIP confirms. Measured on kbet: 12 direct test→component render
  edges, **all semantic tier** (BetCard among them — this entry's own
  example), and 108 of 174 tests now reach a component, with closure
  over what the component itself renders (`ActiveBetsStrip →
  StripButton`). The lanes agree on both kbet and this repo. The
  approval carried a standing condition: "in every meaningful sense"
  keeps its outliers named — which is the next field.
- **Residual edge cases — the outliers of "a JSX instantiation is a
  call":** only component-like tags count (a capitalised identifier or a
  dotted tag; `<div>` is a string at runtime, not code the repo owns);
  the framework mediates *when* the body runs, exactly as any call
  behind a branch mediates whether its callee runs; a closing tag is not
  a second site; and a component passed as a *value*
  (`<Route component={Card}>`) is still a `uses` edge, because nothing
  at that site instantiates it. kbet's remaining 44 empty-reach tests
  are store/logic tests in plain `.ts` files — a different residual
  (calls through mocks and store indirection), not this entry's subject.
- **Source:** V2.M3; lifted 2026-08-15, after V2.M6 and before V2.M7.
