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

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

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
  through ts-morph and was unaffected throughout.
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
