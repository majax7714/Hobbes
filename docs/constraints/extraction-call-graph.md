# Extraction — the call graph

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-1 — An absent call edge never means "this does not happen"
- **Cannot tell you:** whether code Hobbes shows no edge into is actually
  uncalled.
- **Because:** the symbol graph deliberately under-approximates. An edge
  is emitted only when a callee resolves; dynamic dispatch, higher-order
  calls, and calls through values are omitted rather than guessed, because
  a false edge is worse than a missing one.
- **Bites at:** `who_calls`, `tests_guarding`, dead-code intuitions, and
  any invariant phrased as "nothing calls X".
- **You find out:** *partial.* Resolution coverage (C-2) gives the
  denominator per file since ADR-029, but nothing states the rule at the
  point where a reviewer would draw the wrong conclusion.
- **Source:** ADR-007.

### C-2 — Some call sites resolve to nothing, and the count is the honest form
- **Cannot tell you:** where 13.1% of this repo's call sites go (403 of
  3,070 at the ADR-029 measurement).
- **Because:** the remainder are dominated by builtins (`len`,
  `isinstance`) and by dynamically typed test fixtures
  (`capsys.readouterr`, `monkeypatch.setenv`) — receivers whose type
  Pyright cannot know at the call site. That is a real limit of static
  semantics, not a bug to be fixed.
- **Bites at:** trust in any one module's call graph. `review.py` is 56%
  accounted; `policy.py` is 100%.
- **You find out:** **surfaced** — `graph.json.resolution_coverage`, per
  file: sites, resolved, external, unresolved — and since ADR-045 each
  row's `tail` object classifies the unresolved remainder by
  observation, so the composition this entry asserted from one
  measurement is measured on every ingest instead of remembered. The
  ingest summary prints the per-language rollup: *seen, not modelled by
  design* (builtin-named calls, below-floor local bindings) versus
  *cannot resolve* — always as a share **of detected sites**, never "of
  the repo". On this repo's 2026-08-16 measurement the fixture claim
  held: 45.5% of the Python tail is builtin-named, 44.4% attribute
  calls on untypable receivers. One ledger subtlety the tail makes
  visible: a site lane A's *fallback* resolved still counts as
  unresolved here (the count is the semantic ledger) and carries class
  `fallback-resolved` — it has an edge, at syntactic tier. Since
  ADR-047 the same decomposition reaches **agents** where they work:
  `list_blind_spots` on the session proxy serves the scoped rollup with
  each class naming its register entry, so an in-sandbox agent can
  point at the verification work that is its own.
- **Note:** deliberately counts, never a confidence score. An edge with no
  named target cannot be drawn, checked, or cited — it is C-1's false edge
  wearing a probability. The tail classes keep that rule: each is an
  observation about the site, never a probability about the edge
  (ADR-045; their boundaries are C-32).
- **Source:** ADR-029; tail classification added by ADR-045.

### C-4 — Pytest fixtures do not appear in test reach
- **Cannot tell you:** that a test exercises code reached only through a
  fixture.
- **Because:** fixtures are dynamic injection; reach is the static closure
  over call edges from the test symbol.
- **Bites at:** `tests_guarding`, behavioral coverage, and `hobbes review`'s
  "unguarded new code" verdict — a fixture-heavy suite looks thinner than
  it is.
- **You find out:** **partial** (was *unsurfaced* until 2026-08-23 — the
  status had lagged the code): the always-on denominator statement names
  "fixture-injected test reach (C-4)" in `list_blind_spots` and in every
  derived context manifest (ADR-047/051), so an agent meets it. A human
  still does not: `tests_guarding` and `hobbes review` reach lists are
  short and give no reason.
- **Source:** ADR-007. See also `future_additions.md` → test-reach trimming.

### C-5 — Routes with computed paths are skipped
- **Cannot tell you:** that an endpoint exists when its path is an
  f-string or a variable rather than a literal.
- **Because:** a route that cannot be pinned to a literal cannot be cited
  at evidence, and inventing the path would be a false interface.
- **Bites at:** `interfaces.json`, the Tests and Docs tabs' sense of the
  app's surface area.
- **You find out:** **surfaced** (2026-08-15, the pre-M6 register sweep) —
  each HTTP pack now emits one `extraction_errors` record per declined
  registration, naming file:line and saying the route is absent rather
  than guessed. The constraint itself stands: the route still cannot be
  reported, only its absence is now legible. Surfacing it also fixed a
  quiet inversion in the Nest reader, which had been *emitting* a route
  with the computed segment dropped — a path the app does not serve, worse
  than C-5's absence; computed Nest arguments now decline like the rest.
- **Source:** ADR-007 (the rule). The mechanism lives in the enrichment
  packs since V2.M4 (ADR-035) — `http-python`, `http-ts`, and V2.M5's
  `http-go` each cite this entry and skip computed paths the same way, so
  the constraint now spans five frameworks across three languages.
  Surfaced 2026-08-15 (tsextract helper v3).

### C-6 — A semantic index cannot say what a reference syntactically was
- **Cannot tell you:** from lane B alone, whether an occurrence is a call,
  a type annotation, an `except` clause, or a Go type conversion.
- **Because:** SCIP carries a `syntax_kind` that would separate them, and
  **no indexer populates it**. `scip-python` leaves it unset for 0 of
  8,575 occurrences; `scip-go` for **0 of 18,682** (V2.M5, ADR-037);
  `rust-analyzer` for **0 of 169** (V2.M7, ADR-040). Three independent
  implementations, the same omission — and the field is optional in SCIP,
  so this is the state of the ecosystem rather than one tool's gap.
  Registered first as a `scip-python` limitation, **generalised at
  V2.M5** when measuring a second indexer showed the original framing was
  too narrow, and confirmed by the third.
- **Bites at:** it would have made `who_calls` silently become
  `who_references`. This is the whole reason the lanes join on ranges
  before a graph exists rather than merging finished edges.
- **You find out:** **surfaced** — resolutions that no call site claimed
  are typed `uses`, not `calls`, so the two questions stay separable in
  the artifact.
- **Provider (P9):** inherited from **every** indexer measured —
  `@sourcegraph/scip-python` 0.6.6, `scip-go` 0.2.7, and `rust-analyzer`
  1.97.1. **Not liftable by
  upgrading one of them**, which is what changed at V2.M5: it would have to
  be fixed by all of them, and a language whose indexer still omitted it
  would silently lose its call graph. This is why the add-a-language
  checklist requires a syntax provider (§3.7) rather than suggesting one.
  Re-check per indexer on any version bump; a single fix lifts nothing on
  its own.
- **Source:** ADR-029 (registered), ADR-037 (generalised), ADR-040
  (third confirmation); owned as ours under P9 (ADR-034).

### C-7 — Lane A's fallback edges are guesses, and say so
- **Cannot tell you:** with proof, where a call goes when the indexer
  could not resolve it (131 edges on this repo at the M2 exit).
- **Because:** lane A's resolver runs on four static rules and can be
  wrong — the M2 measurement found a real false positive, a local
  variable named `write` bound to a module-level function.
- **Bites at:** any consumer that treats all call edges as equally true.
- **You find out:** **surfaced** — `tier: syntactic` on the edge, drawn
  thinner, dimmer and dashed in the graph (ADR-023 styling, M2), and
  marked `(syntactic — approximate)` per caller in `who_calls`, so an
  agent reading the tool output sees it too and not only a human reading
  the graph (V2.M3).
- **Source:** ADR-029.

### C-8 — With no working indexer, the entire symbol layer is approximate
- **Cannot tell you:** anything semantic about a repo whose language has
  no indexer wired, whose indexer is missing, or whose environment is not
  installed. The call graph falls back to lane A's four rules wholesale.
- **Because:** semantics come from a batch indexer that has to be present
  and has to be able to resolve. Lane A is the floor, by design (P6).
- **Bites at:** every symbol-level question, on any box without `scip/`
  installed, and on every language v2 has not reached yet.
- **You find out:** **surfaced** — `extraction_errors` plus an ingest
  WARNING when a lane degrades, and the tier on every edge when it does
  not.
- **Source:** architecture §3.2/P6, ADR-029. Registered at V2.M3, when
  demoting lane A's resolver made the floor explicit rather than incidental.

### C-9 — Only five descriptor kinds become graph symbols
- **Cannot tell you:** about parameters, locals, or meta symbols; roughly
  **86%** of what a Python or TS indexer defines is dropped (**72%** for
  Go — 27.9% of `scip-go`'s definitions are graph-worthy, ADR-037).
- **Because:** the graph models namespaces, types, methods, terms and —
  since V2.M7 — macros (`macro_rules!` is architecture in Rust the way a
  function is; only rust-analyzer emits the descriptor, ADR-040).
  kbet's frontend alone offers 6,696 definitions against 949 graph-worthy;
  the whole v1 dogfood graph has 834 symbols.
- **Bites at:** any expectation that the symbol layer is a complete index
  of the code. It is an architectural view, not an IDE.
- **You find out:** **partial.** The filter is stated in ADR-027 and the
  omission is uniform, so it does not mislead about *specific* code — but
  nothing in the artifact declares the modelled vocabulary.
- **Provider (P9):** ours, not inherited — the descriptor filter
  (`GRAPH_KINDS` in the shared `scip/index.mjs` helper) is Hobbes's choice
  over what `@sourcegraph/scip-python` **0.6.6**,
  `@sourcegraph/scip-typescript` **0.4.0**, `scip-go` **0.2.7** (added
  V2.M5), and `rust-analyzer` **1.97.1** (added V2.M7) emit. Listed here
  because it is easily mistaken for a provider limit: the indexers *do*
  report these symbols and Hobbes drops them. Not liftable by an upgrade.
- **Source:** ADR-027, Decision 3. Amended by ADR-040 (macro joined the
  set).

### C-10 — Node ids carry no version, so cross-version merging is out
- **Cannot tell you:** which version of a package a symbol belongs to.
- **Because:** the indexer's version flag is pinned to a constant —
  `--project-version` for scip-python/scip-typescript, `--module-version`
  for scip-go (the same decision under a third flag name, ADR-037) —
  since its default is the git revision and would re-key every node on
  every commit, which would make `hobbes diff` report the whole repo as
  removed-and-re-added, destroying the thing v2 exists to sharpen.
  rust-analyzer is the one exception that changes nothing: it has no
  version flag and needs none, because its moniker version is the crate's
  `Cargo.toml` version — constant per commit by itself (ADR-040).
- **Bites at:** a future multi-repo graph merge, which must key on package
  identity alone. Nothing today.
- **You find out:** **n/a — no user-visible effect yet.** Registered
  because it is a paid cost with a deferred bill.
- **Source:** ADR-027, Decision 1.

### C-58 — A call through an interface, a function value, or into a closure draws no edge — and the site still counts as resolved
- **Cannot tell you:** that `s.Get(key)` reaches `MemStore.Get`, that
  `run(query)` reaches the `Store` method the map handed it, that
  `defer cancel()` runs anything, or that `run("init")` in a test helper
  calls the closure two lines above it. **No `calls` edge is emitted
  for any of them** — not to the interface method, not to the concrete
  implementation, not to the closure. `who_calls` on an implementation
  reached only through its interface answers *nobody*.
- **Because:** two stacked mechanisms. The semantic lane resolves the
  interface call to the *interface method's* declaration, and interface
  methods and closures are outside the five graph-worthy descriptor
  kinds (C-9) — so there is no target node to draw the edge to and the
  join drops it. Concrete-implementation targets would need a
  points-to or type-hierarchy analysis Hobbes does not run (P9 has
  nothing to inherit here: SCIP indexers resolve *declarations*, not
  dispatch).
- **Bites at:** `who_calls`, `tests_guarding`, `graph_neighborhood`, the
  reviewer's tier-aware invariant checks, and every derived context
  built from call reach — anything dispatched through an interface,
  a callback, or a goroutine closure is a silent hole in the reach set.
  Measured on this repo's Go zone by the oracle lane (2026-08-25): of
  1,461 in-repo oracle pairs, 45 non-inflated misses are exactly this
  class (8 dynamic dispatch, 37 calls into closures); the reachability
  oracle's own over-approximation of `func()` values adds 138 more
  pairs it cannot separate.
- **You find out:** **unsurfaced — and worse than silent.** The site is
  counted **resolved** in `resolution_coverage` (the checker *did* find
  a declaration: the interface method), so the capture number reads
  100% on a file whose only call the graph does not carry. The number
  says accounted; the graph says nothing. Candidate surfacing: a
  `dispatch` class in the tail view (C-32's vocabulary) — *seen and not
  modelled by design* — counted out of `resolved` and reported per
  file, and a `dispatch` note on `who_calls` answers for any method that
  implements an interface. Until then this entry is the only place a
  user learns it.
- **Provider (P9):** ours. `scip-go` **0.2.7** resolves the occurrence
  correctly (to the interface method); Hobbes' descriptor filter and the
  absence of a dispatch analysis are Hobbes' choices.
- **Source:** oracle lane O1/O2 (ADR-089, `docs/oracle-grading.md`;
  `bench/oracle/`), 2026-08-25 — the lane's first graded miss, on the
  `twomod` fixture, then 45 of 45 non-inflated misses on this repo.
  Related: C-1 (the general rule that absence is not evidence), C-9
  (the descriptor filter), C-7 (the syntactic fallback that *did* draw
  an edge for a closure call in `hobbes-session/main_test.go` — to the
  wrong target, the package function of the same name; the oracle's 3
  syntactic-tier contradictions).

### C-32 — The tail view's classes are observations with boundaries
- **Cannot tell you:** *why* a call is unresolved beyond what its class
  observes — and three boundaries shape what the classes can say.
  **Origin classes carry two proof grades** (narrowed by ADR-046, which
  applied this entry's candidate fix): for TS/JS, `local-binding` /
  `nested-decl` / `external-origin` are **declaration-proven** — the
  checker resolved where the callee lives. For Python and Go,
  `local-binding` is **binding-proven with scope containment** — lane
  A recorded the binding (a parameter, a `:=` or assignment target, a
  nested def) with its enclosing function's extent, and the site
  matches only when that extent spans the call's line; `nested-decl`
  and `external-origin` do not exist for them, and Python's
  `import-binding` (ADR-045 amendment) is binding-proven the same way,
  minus the scope check — an import binds at module level. **Rust has
  no origin classes at all**: both verified Rust tails are empty, so a
  collector could not be verified against anything real, and wiring one
  on zero evidence would be the P11 mistake at class scale. **Builtin lists are
  pinned literals**, not the running interpreter's — a builtin the
  language adds later classifies `unclassified` until the pin moves.
  **Shape is read from the terminal's source line, plus one line up
  for a wrapped chain** (widened by ADR-048): in Go, Rust, and TS/JS a
  statement cannot end with `.`, so when a call opens its line and the
  previous line ends mid-chain (`.` or `::`, after cutting any trailing
  `//` comment) the site reads `attr-call`/`path-call` — dagger's
  gofmt-mandated fluent chains were thousands of real attr-calls
  reading `unclassified` before this. Python is excluded (its chains
  wrap with a leading dot, already read same-line; a trailing dot
  inside parentheses abstains). What still abstains: a terminal the
  recorded line does not contain, and a previous line whose chain
  ending hides behind a string literal containing `//` — both decline
  to `unclassified` rather than guess, the C-5 rule applied to
  classification.
- **Because:** a class must be an observation or abstain (ADR-045's
  standing rule) — inferring what a site "probably is" from a checklist
  of potentials is the fake-honest shape P8 exists to prevent. The
  boundaries are the price of that rule, and the measured tails say the
  asymmetry costs little today (Python's declared-in-file share was
  6.8% where TS's was 61–73%).
- **Bites at:** cross-language comparison of tail compositions — a TS
  tail reads richer than a Python one partly because TS is the only
  lane whose checker reports origins.
- **You find out:** **surfaced** (2026-08-21, ADR-053 — this entry's
  candidate fix applied). `graph.json` carries
  `tail_classes_available`, per tail-view language, the classes its
  providers *could* have reported (a pinned table beside the classifier,
  held against its decision tree by the test suite); the ingest capture
  line prints `classes this lane cannot report: …` under each language,
  and `list_blind_spots` prints the same line to agents. Abstention
  stays visible as `unclassified` counts. What remains conceded is the
  asymmetry itself — Python/Go/Rust tails are still poorer than TS's
  because their providers report fewer observations; the fix makes the
  boundary legible, it does not move it. Origin support from the other
  syntax providers would narrow it further.
- **Source:** ADR-045; surfacing ADR-053.

---

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-3 — Standard-library dependencies were invisible — *lifted by ADR-038*
- **Was:** stdlib imports were dropped as noise at resolution for Python
  (`sys.stdlib_module_names`, ADR-007) and JS/TS (Node builtins, M6), so
  "imports no stdlib" and "stdlib not modelled" looked identical — and the
  question is usually a security one, where `subprocess` is exactly the
  import a reviewer wants flagged. V2.M5 made it worse without touching
  it: Go's layer never had the filter, so `ext:os` on Go modules taught
  the reader stdlib *was* modelled and a Python module's silence read as
  positively clean. The asymmetry was found by the 2026-08-15 register
  audit, unregistered by ADR-037.
- **Lifted by — the technique:** ADR-038 (same day) — every syntax
  provider now emits `ext:` nodes for stdlib like any other dependency.
  Python simply drops the skip (no list is consulted; whatever does not
  resolve in-repo is external). TS keeps builtins **normalised** to a
  `node:`-prefixed name — `fs`, `node:fs` and `fs/promises` all become
  `ext:node:fs` — so a builtin never shares a node with an npm package
  that reuses its name. Go was already right, just alone. Externals stay
  hidden by default in the surface (ADR-023) — a view choice, where the
  old rule was an information choice.
- **Residual edge cases:** the TS normalisation's boundary is
  `builtinModules` from the **running Node's** `node:module` — the list
  is the ingest box's Node version, not a pin. A builtin added in a newer
  Node than the box's classifies as a third-party `ext:` package until
  the box upgrades; a builtin imported under the explicit `node:` prefix
  always normalises regardless. Two nodes for one dependency across two
  ingest boxes on different Node versions is the shape a user would see.
- **Source:** ADR-007 (the rule), ADR-038 (the lift), owner's call
  ("no need to hide what hobbes does capture" — Max, 2026-08-15).
