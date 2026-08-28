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

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

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

### C-63 — A call through an element access (`obj[key]()`) is not a call site
- **Cannot tell you:** that `table["norm"](s)`, `xs[Symbol.iterator]()`
  or `table[k](s)` calls anything. Lane A's TS/JS syntax provider does
  not count an element-access callee as a call site, so the site is
  absent from `resolution_coverage` (not unresolved — uncounted) and no
  `calls` edge is drawn, whichever lane could have resolved it. Lane B
  does emit the `uses` reference for the key's target where it has one.
- **Because:** the site detector matches identifier and property-access
  callees; the element-access shape was never in the fixture until
  `minits/src/lookup.ts` (2026-08-27), where the oracle lane's A-4
  observation found the three shapes drawing zero edges.
- **Bites at:** dynamic-dispatch tables (`handlers[name](req)`),
  `process.env["X"]`-style reads that are calls, well-known-symbol
  protocol calls, generated clients indexed by operation name. The
  oracle lane grades the literal-key shape as a recall miss
  (`static→function`, minits 4/5); ajv `f177fe3` has 1 computed-key site.
- **You find out:** **unsurfaced** — debt. The site is not counted, so
  no coverage row, tail class or blind-spot names it. Surfacing means
  counting the site (then it falls to `below-floor` or resolves).
- **Source:** the oracle lane's A-4 fixture observation, 2026-08-27
  (`bench/oracle/README.md` D-O4 element-access bullet; H-17).
