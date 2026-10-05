# Extraction — the call graph

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-1 — An absent call edge never means "this does not happen"
- **Cannot tell you:** whether code Hobbes shows no edge into is actually
  uncalled.
- **Because:** the symbol graph deliberately under-approximates. An edge
  is emitted only when a callee resolves; dynamic dispatch, higher-order
  calls, and calls through values are omitted rather than guessed, because
  a false edge is worse than a missing one. (Narrowed 2026-09-03 by
  C-80's lift: a call *through* a value in the receiver position —
  `f().m()`, `super().m()` — is now a detected site the semantic lane
  can resolve; a callee that is itself a value — `handlers[0]()` —
  still is not. A call the language makes with no call written — a
  Python `with` statement's `__enter__`/`__exit__`, an operator's dunder
  — is not dispatch or a value, and is its own entry since 0.2.78-beta:
  C-174.)
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
  point at the verification work that is its own. Since 0.2.9-beta it
  also serves the ingest summary's per-directory rows, so a miss has a
  directory as well as a file.
- **Also in `attr-call`** (2026-10-04, 0.2.119-beta): a typed receiver whose member the index names
  nothing at. scip-typescript writes no occurrence at a member reached through a re-exported alias
  (`import * as z` → `export *` → `export { objectType as object }` → `const objectType = X.create`):
  zod's 1,232 `static→property` misses. Until 0.2.119 the class's text said only "receiver no static
  provider could type"; it now names both causes. The class is the site's shape and does not say which.
  The Calvin gate still files the class under the map reason `dynamic-dispatch` (`gate.py`).
- **Note:** deliberately counts, never a confidence score. An edge with no
  named target cannot be drawn, checked, or cited — it is C-1's false edge
  wearing a probability. The tail classes keep that rule: each is an
  observation about the site, never a probability about the edge
  (ADR-045; their boundaries are C-32).
- **Source:** ADR-029; tail classification added by ADR-045.

### C-4 — A test's reach through a fixture's value that is not a construction, or through a fixture pytest's lookup by name cannot place, is not drawn — *narrowed 2026-09-19 (ADR-137, 0.2.49-beta: a fixture a parameter names is an edge, and reach follows it; ADR-139, 0.2.52-beta: so is one a `usefixtures` mark or `autouse` applies) and 2026-09-20 (ADR-145, 0.2.63-beta: a call on the value a fixture constructs is drawn; ADR-139 amended, 0.2.64-beta: a module `pytestmark`'s `usefixtures` is followed) and 2026-09-22 (ADR-145 amended, 0.2.69-beta: the value through a local, and an inherited method)*
- **Narrowed (0.2.49-beta, ADR-137; 0.2.52-beta, ADR-139).** A name
  pytest's lookup order (class chain, file and its imported names, the
  conftest chain) resolves to one fixture definition in the repo is a
  syntactic `uses` edge, and the test map follows it — whether a
  parameter names it, a `usefixtures` string on the test, its class or
  the file's module-level `pytestmark` (0.2.64-beta) does, or the
  fixture is defined `autouse=True` in a scope of the
  test's chain. Each evidence row says which (`via`). `through_fixtures`
  names the modules reached only through a fixture the test names,
  `through_autouse` the ones reached only through an autouse fixture.
  Keyed by `pytest --fixtures-per-test -v` (without `-v` pytest prints
  no fixture named `_…`, and ADR-137's first figures were of the pairs
  that key printed): this repo 4,971 of 4,971 pairs, flask 1,238 and
  attrs 118 held out, none missed, none wrong; MissyLabs/missy, drawn at
  random for the `pytestmark`, 35,770 of 35,770 in-repo pairs.
- **Narrowed (0.2.63-beta, ADR-145).** Where a fixture's own body is one
  `return C(…)` / `yield C(…)` and the index names `C` a repo class at
  that token, `p.m(…)` on the injected parameter is a `calls` edge to
  `C.m` — `syntactic`, evidence `via: fixture-value` — when `m` is one
  `def` in `C`'s own body and `p` is never rebound. click: 382 drawn,
  381 confirmed by its trace key, 0 contradicted (recall 38.2% → 46.5%).
- **Narrowed (0.2.69-beta, ADR-145 amended).** The value may come
  through a local — `x = C(…)` bound once, at the top of the fixture's
  body, before `return x` — and `m` may be a base's: the walk goes up
  single bases the index names on each class's `class` line and takes
  the first `def`. Refused and counted: an instance the test or fixture
  patched, a class-body binding of `m` other than a `def`, two bases, a
  base the index does not name. flask (keyed 2026-09-22): 400 drawn, 329
  inherited, 400 confirmed, 0 contradicted (recall 41.5% → 56.4%).
- **Cannot tell you:** that a test exercises code it reaches
  - through a **method on a fixture's value that is not a construction
    bound once** (`return app.test_client()`, a factory's return — flask's
    284 sites), a method of a class with **two bases** or a base the
    index does not name (an out-of-repo base), a property, or an
    instance the test patched: lane B does not type an unannotated
    parameter, and the rule reads a construction, not a type — each
    refusal counted; a class that overrides attribute lookup
    (`__getattr__`, a metaclass) is not detected;
  - through a **`pytestmark`** that is not a plain module-level
    assignment (a class body's, an annotated one) or whose `usefixtures`
    has no string argument, an `autouse=` whose value is not the literal
    `True`, or a `usefixtures` argument that is not a string (the module
    mark and the `autouse=` counted);
  - through a fixture **a plugin or an installed package** defines, one
    **inherited from a base class**, one defined twice at a scope, or
    one requested by a definition whose `parametrize` argument is not a
    literal — each an abstention, not a guess.
- **Because:** injection is dynamic; only the *lookup by name* is
  syntax, and a returned value's type is a type checker's.
- **Bites at:** `tests_guarding`, behavioural coverage and
  `hobbes review`'s "new code no test reaches" on a suite whose tests
  drive code through a client object a fixture hands them. And the
  other way: autouse reach is true and thin — a module only an autouse
  fixture touches reads as reached, which is why it is labelled.
- **You find out:** **surfaced**: the ingest summary's `fixtures:` line
  and `graph.json`'s `fixtures` block count what was drawn, by `via`,
  every abstention by reason, the calls drawn on a constructed value and
  each refusal by reason (`value_calls`, ADR-145), and the `pytestmark` marks with no string argument and non-literal
  `autouse=` values not followed; `tests_guarding` says "only through a
  pytest fixture (ADR-137)" on a line that is, and says the tests that
  reach a target only through an autouse fixture once, with the
  fixtures (ADR-139); `hobbes review` lists new code guarded only by a
  named fixture, and only by an autouse one, each on its own line; the
  denominator statement in `list_blind_spots` and every derived context
  manifest (ADR-047/051) names this remainder.
- **Source:** ADR-007; narrowed by ADR-137, ADR-139 and ADR-145 (amended 2026-09-22). See also
  `future_additions.md` → test-reach trimming.

### C-156 — A test that reads a value but calls nothing guards nothing
- **Cannot tell you:** that a test guards a module whose behaviour is a
  value (a constant, a package variable, a table) rather than a
  function, when the test reads that value and calls nothing in the
  module.
- **Because:** reach is the closure over `calls` edges from the test
  symbol, in every language's test map (ADR-007; `testmap.py` states
  why `uses` edges are not followed: reach must not widen to code a
  test merely names). A read of a constant is not a call, so a module
  with no function a test calls cannot be reached, however directly the
  test checks it.
- **Bites at:** `go/internal/version` in this repo: its one test,
  `TestVersionMatchesTheRootFile`, compares `version.Version` with the
  root `VERSION` file and is recorded with `reaches: []`, so
  `tests_guarding` answers "unguarded" and the graph job's review
  reported the package as new code no test reaches (2026-09-09, the W0
  item). The same holds for any constants-only module in any language.
- **You find out:** **surfaced** (was *unsurfaced* on the day it was
  registered; ADR-117, 0.2.29-beta): where `tests_guarding` answers
  "unguarded", it adds a line naming each value-only module and C-156.
  `hobbes review` puts the same reason on the module's line under "new
  code no test reaches" or "lost every guarding test", and lists it in
  `--json` under `coverage.value_only`. The module is still listed and
  still needs attention: the reason is said, not exempted. *Value-only*
  is read from the graph: no function, method, class, type or macro,
  and no `calls` edge into the module.
- **Source:** W0's "`go/internal/version` stays unguarded" item, traced
  2026-09-16 to the rule in ADR-007; surfaced by ADR-117.

### C-179 — A module a Python file loads at run time draws no import, so nothing reaches it through that load — *named at the point of use since 0.2.96-beta (ADR-167); partial*
- **Cannot tell you:** that a test, or any code, uses a module it loads
  at run time instead of with an `import` statement:
  `importlib.util.spec_from_file_location(…)` then `exec_module`,
  `importlib.import_module("…")` (even with a literal naming an in-repo
  module, `"pkg.lit"`), or `__import__("…")`. No `imports` edge is drawn
  from the loading module, and a call through the loaded module's value
  (`mod.run()`) reaches no symbol, so test reach stops at the load. The
  same test written as `sys.path.insert(…)` then `import mod` is drawn
  and reaches.
- **Because:** Python lane A reads `import` and `from … import`
  statements only; a load is a call whose argument names the module, and
  no rule reads that argument. Lane B drew nothing either: in a
  contained ingest of a ten-line probe (2026-10-02), each runtime form
  gave no edge from either lane, and its `mod.run()` was counted
  `attr-call`. Other languages' runtime loading (a JavaScript `import()`
  expression, `require` with a computed specifier, Java reflection) is
  not measured here.
- **Bites at:** `tests_guarding` answers "unguarded", and `hobbes
  review` lists the module under "new code no test reaches", for a
  script its tests load by path (this repo's
  `pipeline/scripts/shanks_tracker.py`, turned red in the graph job
  until its test changed to a plain import, 2026-10-02); `who_calls`
  shows no caller through the load; `graph_neighborhood` shows no edge
  from the loader.
- **You find out:** *partial* — since 0.2.96-beta (ADR-167) lane A records
  each load with what it names as written (a literal module name; a
  `spec_from_file_location` path's trailing literals, through one
  module-level name) and places it on an in-repo module only exactly.
  Where it is placed, `tests_guarding` names the load after "unguarded"
  and `hobbes review` beside the listed module (`--json`:
  `coverage.loaded_by_name`); one `python-loads` record per ingest counts
  the loads, placed and not, in `list_blind_spots`. A load that names
  nothing placeable (a computed name, a path built from non-literals, two
  candidate files) is only counted. No edge is drawn. The call through
  the loaded value is still counted `attr-call`.
- **Source:** the graph job's 22 unguarded new modules, traced
  2026-10-02 (the thirty-third session); the probe is in the session's
  BUILDLOG entry.

### C-184 — A Python method call on a union-typed receiver is drawn to the first member's method — *registered 2026-10-03 (held-out icalendar); contained where the union is written since 0.2.97-beta (ADR-168); partial*
- **Cannot tell you:** which member of a union a call reaches. Where a
  receiver's declared type is a union of classes (`VPROPERTY: TypeAlias =
  vAdr | vBoolean | …`, an attribute annotated `A | B | C`), scip-python
  answers `x.m()` with the **first** member's `m`, and Hobbes draws that
  edge at `semantic` certainty: `component['TZOFFSETFROM'].to_ical()`
  draws `vAdr.to_ical`, which the call never reaches (the trace saw
  `vUTCOffset.to_ical`; `vAdr` is no base of it). The edge is wrong as
  stated, not merely broad.
- **Because:** scip-python 0.6.6 writes one symbol per reference, and for a
  union-typed receiver it picks the first member that declares the
  member. Lane A types no Python receiver, so nothing vetoes it.
  TypeScript's face of the same pick is contained (ADR-104, C-97: lane A
  abstains on a union receiver, the join vetoes lane B, the tail says
  `union-member`); Python has no such abstention.
- **Bites at:** `who_calls` on the first member's method (callers that
  reach other members), its `tests_guarding` (tests that never reach it),
  and `graph_neighborhood`. Measured on the held-out icalendar cell
  (2026-10-03): 6 of 22 suspects, every one `semantic`, 5 at `vAdr` (the
  head of `VPROPERTY`) and 1 at `LazySubcomponentsStrategy.is_lazy`. Edges
  the suite did not execute are not counted; the scale beyond the key is
  unmeasured. Not seen in the other Python cells' suspects (rich, flask,
  click, pyparsing: 0 Hobbes-wrong).
- **Contained (ADR-168, 0.2.97-beta):** lane A reads the receiver's union
  where the source writes it — a parameter's annotation, a local bound once
  from a call whose return annotation is a union, a class attribute's
  annotation, a call result's return annotation, and, for a subscript, every
  union an in-repo `__getitem__` returns — aliases expanded, by name across
  the repo. Where two or more in-repo members declare the method, the site
  is `union-member`: the join draws nothing there from either lane, as
  ADR-104 does for TS. On icalendar that removed all 6 wrong rows, and with
  them the union-typed rows the key happened to confirm (an agreement of
  picks, not a truth).
- **Residual:** a union Pyright *infers* (`x = a if c else b`, a loop over
  mixed values, a union lane A cannot read: a generic, a class name defined
  twice) is not read, so the first-member pick can still be drawn there.
- **You find out:** *partial* — a contained site is counted in
  `list_blind_spots` under the tail class `union-member`, whose gloss names
  this entry; an edge drawn at the residual reads as any other `semantic`
  edge.
- **Provider (P9):** scip-python **0.6.6** (its bundled Pyright's member
  lookup on a union type).
- **Source:** `oracle-grading.md` §10.46; `cells/icalendar-py-2026-10-03.md`.
  ADR-168; the regrade `~/.hobbes/bench/c184-union-receiver/`.

### C-185 — A Python class whose relationships scip-python never states draws no `implements` edge to its base — *registered 2026-10-03 (0.2.98-beta, ADR-169)*
- **Cannot tell you:** that a class extends an in-repo base, where the index
  states no relationship for the class. scip-python 0.6.6 writes no
  SymbolInformation at all for some classes (flask's `Flask`, icalendar's
  `Component`, click's `Group`), so no class-level `implements` edge is
  drawn from them, and the pair is not counted `outside` either. The base
  name in the header is still resolved, as a `uses` reference, and the
  methods' own `implements` pairs may still be stated (`Flask.
  create_jinja_environment → App.create_jinja_environment`).
- **Because:** the class-level `implements` edge comes only from the
  index's `relationships` (ADR-120); why scip-python omits some classes is
  unread.
- **Bites at:** `graph_neighborhood` and the graph view (no class edge to the
  base), and C-58's dispatch reading through a base. Measured 2026-10-03, of
  the in-repo bases lane B resolved in a class header: flask 14 of 80, rich
  16 of 80, click 9 of 97, pyparsing 42 of 168, icalendar 4 of 60, this repo
  0 of 9.
- **You find out:** surfaced — every ingest where lane B ran for Python and
  such a pair exists writes one `python-bases` degradation record (the
  count, examples, this entry), shown by `list_blind_spots` and the ingest
  summary.
- **Provider (P9):** scip-python **0.6.6**.
- **Source:** the flask `sansio/` re-ask's probe (2026-10-03); ADR-169;
  `~/.hobbes/bench/c185-unstated-bases/`.

### C-186 — A Python name one scope defines more than once is one node at its first def, whichever def runs — *registered 2026-10-03 (0.2.101-beta, ADR-172)*
- **Cannot tell you:** which def of such a name runs. The graph keeps one node for it, at the first
  def: scip-python makes the defs one definition there (C-170's note), and lane A keeps one record.
  An edge to the name is evidenced at its call, and right by qualname, but `who_calls`, the graph
  view and every answer that cites the node's lines name the first def, which may not be the one
  that runs: an `if`/`else` or `try`/`except` pair the static reading does not settle (structlog's
  `dev._init_terminal`, `if _IS_WINDOWS:` on a variable: the node is the Windows def, Linux runs the
  other), a later def that replaces the first at import, and an `@overload` group, whose stubs never
  run. A property's accessors are one property and are not this entry.
- **Because:** the symbol layer has one node per qualname. ADR-154 moves a twin's node to its live
  def where Pyright reads the test statically (`sys.platform` written in the `if`), and nothing
  reads the rest; Rust's cfg twin (C-182) and Go's `init` (C-183) are the same shape in theirs.
- **Bites at:** measured 2026-10-03 with lane B: structlog 3 names (the trace saw the second def of
  `_init_terminal` run, read as a suspect row on the held-out cell), click 6 and 16 `@overload`
  groups (its ADR-154 twins `raw_terminal` and `getchar` are settled, not named).
- **You find out:** surfaced — every ingest with such a name writes one `python-repeats`
  degradation record (the count by kind, examples with every def's line, this entry), shown by
  `list_blind_spots` and the ingest summary. Without lane B every repeated qualname is named; with
  it, a def ADR-154's reading found dead, or a twin it settled, is not.
- **Source:** the structlog held-out cell (`oracle/cells/structlog-py-2026-10-03.md`); ADR-155's
  *What this leaves*; ADR-172.

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

### C-9 — Only five descriptor kinds become graph symbols — *narrowed 2026-10-02 (ADR-160, 0.2.85-beta): a call through a local alias whose right-hand side the index names is drawn, `syntactic`; and 2026-10-03 (ADR-170, 0.2.99-beta): `cls(…)` in a classmethod; and 2026-10-05 (ADR-180, 0.2.121-beta): a TS/JS class field holding a function literal is a method symbol*
- **Cannot tell you:** about parameters, locals, or meta symbols; roughly
  **86%** of what a Python or TS indexer defines is dropped (**72%** for
  Go — 27.9% of `scip-go`'s definitions are graph-worthy, ADR-037).
- **Because:** the graph models namespaces, types, methods, terms and —
  since V2.M7 — macros (`macro_rules!` is architecture in Rust the way a
  function is; only rust-analyzer emits the descriptor, ADR-040).
  kbet's frontend alone offers 6,696 definitions against 949 graph-worthy;
  the whole v1 dogfood graph has 834 symbols.
- **Bites at:** any expectation that the symbol layer is a complete index
  of the code. It is an architectural view, not an IDE. **The call side of
  a local, narrowed 2026-10-02 (ADR-160, 0.2.85-beta):** a function that
  binds a local exactly once by `N = R` (R a name or an attribute chain)
  and calls `N(…)` draws `calls` to what the index named at R, at the
  `syntactic` tier, `via: "alias"` (rich +124 confirmed, 90.20% →
  92.51%; flask and click have none). **`cls(…)` in a classmethod,
  narrowed 2026-10-03 (ADR-170, 0.2.99-beta):** a bare `cls(…)` in the own
  body of a `@classmethod` written directly in a class body (and not
  rebinding `cls`) draws `calls` to that class, `syntactic`, `via: "cls"`;
  called through a subclass it constructs the subclass, and the edge names
  the declared one (C-60). Every other local binding still
  draws nothing: a parameter holding a callable, a value a call returned,
  a name bound twice, a module-level or class-level alias, and a call from
  a nested def.
- **Narrowed 2026-10-05 (ADR-180, 0.2.121-beta).** A field of a top-level named TS/JS class holding an
  arrow or function expression (`static create = (…) => …`, hono's `c.json`) is a `method` symbol at its
  name, drawn to where lane B names it (`semantic`; lane A's own resolution does not name it), and its
  function's body is its scope. zod +42 confirmed, hono +75, folio-2025 +3, 0 contradicted. Still below
  the floor: a typed field given a value elsewhere (hono 11 rows), and zod's 1,232 calls through a
  re-exported alias of `create`, where the index writes nothing at the member (C-2's `attr-call`).
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

### C-58 — A call through an interface, a function value, or into a closure draws no edge — and the site still counts as resolved — *narrowed 2026-09-16 (ADR-120, 0.2.32-beta): the override set is drawn as `implements` edges; the dispatch itself is still not; narrowed 2026-09-20 (ADR-147, 0.2.66-beta): a Python decorator factory's application is drawn where every return is the one nested def; narrowed 2026-09-21 (ADR-148, 0.2.67-beta): and where the factory's guards, evaluated over the site's own arguments, leave that return the only one reachable; narrowed 2026-09-22 (ADR-149, 0.2.68-beta): and where the factory's reachable returns are all one second factory's call, whose own application reaches its nested def*
- **Cannot tell you:** that `s.Get(key)` reaches `MemStore.Get`, that
  `run(query)` reaches the `Store` method the map handed it, that
  `defer cancel()` runs anything, or that `run("init")` in a test helper
  calls the closure two lines above it. **No `calls` edge is emitted
  for any of them** — not to the interface method, not to the concrete
  implementation, not to the closure. `who_calls` on an implementation
  reached only through its interface answers *nobody*.
- **Java face (ADR-096), measured:** every non-final instance method
  call is potentially polymorphic, so this is the *majority* case for
  Java, not the exception. The edge goes to the **declared** target (the
  interface or superclass method) and javac confirms it; each concrete
  override below it draws nothing. Graded against the CHA override set
  on four repos (O8, 2026-08-29): `interface→method` recall
  **98.7% (spring-petclinic) · 67.5% (jsoup) · 57.4% (spring-data-elasticsearch)
  · 43.3% (Severed-Chains since 0.1.10-beta; 0.4% on its lane-A-only
  grade of 2026-08-29)**, and 89–94% of every
  cell's misses. Members declared in anonymous-class and enum-constant
  bodies are a second face (452–518 pairs per large cell): below the
  symbol floor by decision, named `local-binding` in the tail. An
  overload the fallback declined to pick is not this entry — it is
  named `overload-set` and resolved by lane B.
- **TypeScript face (ADR-104, 2026-09-09):** a member call on a
  union-typed receiver whose members do not share one declaration of
  the member (`n: A | B`, both overriding) is this entry's dispatch
  question in TypeScript's clothes — the static answer is "one of the
  members". Before ADR-104 the semantic lane drew the *first* member's
  declaration at semantic certainty (the oracle lane's
  `static→union-member`, ajv 3 rows and hono 7); since then lane A
  abstains and the join vetoes lane B there, the site counted in the
  tail as `union-member` (C-97). No edge to any member, as for every
  other face of this entry.
- **Python face, one shape drawn (ADR-147, 2026-09-20, 0.2.66-beta):** a
  decorator factory's application. `@click.option("--x")` calls `option`
  (ADR-146) and then applies what it returned — a call of
  `option.<locals>.decorator` that no token spells. It is drawn `calls`,
  `syntactic`, `via: decorator-factory`, **only** where the index names the
  factory at the line (`semantic`), the factory has one undecorated,
  non-async, non-generator body, and **every** `return` in it is the one
  nested `def` bound once there — so the claim holds on every path. click:
  368 drawn, 304 confirmed by its trace key, 0 contradicted, recall 66.4% →
  73.0% (`oracle-grading.md` §10.31). **Refused and counted** in the
  graph's `decorators.factory_calls.refused` and the ingest's
  `decorators:` line: a factory with any other return (click's `command`
  and `group`, which also `return decorator(func)` — 491 sites; the loose
  wording that would draw them read 661 rows at 0 contradicted and was not
  taken, because on that path the site does not call `decorator`), a
  decorated factory (flask's `Scaffold.route` under `@setupmethod`, 162
  sites), two targets at a line, no symbol. Not asked: a bare decorator's
  returned wrapper, a class-based or aliased factory, an untyped receiver.
  Every other Python function value — a callback handed to a runner, a
  lambda, a function in a table — still draws nothing. A named nested
  `def` called by its name was never this entry: it is a symbol and the
  index draws it (corrected 2026-09-20).
- **Python face, the optional-parentheses factory (ADR-148, 2026-09-21,
  0.2.67-beta):** where ADR-147's every-return clause fails, the factory's
  own guards are folded over the arguments the site writes — `@command()`
  leaves `name` at `None`, `callable(None)` is false, and `return
  decorator` is the only return reached. Drawn `calls`, `syntactic`, `via:
  decorator-factory-folded`, only where every reachable return is the one
  nested `def`; the fold is three-valued and an unread test takes both arms.
  click: 397 drawn, 347 confirmed, 3 suspect (a lower decorator raised
  before the application ran), recall 73.6% → 81.2% on `click-py-r3`
  (`oracle-grading.md` §10.33); attrs 18. **Refused and counted** beside
  ADR-147's reasons: `method-positional` (a method factory at a site
  passing a positional — lane A cannot tell `@obj.f(x)` from `@Cls.f(x)`;
  click 27) and `guard-unknown` (a reachable other return). Still not
  drawn: a factory with two nested defs (attrs' `define`), a decorator
  held in a variable, and every callback reached through an attribute or a
  parameter.
- **Python face, a factory returning another factory's call (ADR-149,
  2026-09-22, 0.2.68-beta):** click's `group()` ends `return command(name,
  cls, **attrs)`; where the outer factory's guards, folded over the site's
  arguments, leave only returns of one second factory's call that the index
  names at the return line, and that factory's application — settled
  (ADR-147) or folded over the forwarded arguments (a `**x` leaves every
  unbound parameter unknown, never its default) — reaches its one nested
  def, the site is drawn `calls` to it, `syntactic`, `via:
  decorator-factory-chained`, one level only. click: 67 drawn, 52
  confirmed, 0 new suspects, recall 81.2% → 82.3% on `click-py-r3`
  (`oracle-grading.md` §10.34). **Refused and counted:**
  `chain-guard-unknown` (a reachable return that is no named call),
  `chain-unresolved` (the index names no one second factory there, or two
  returns name two), `chain-inner` (the second factory is no factory the
  rule reads, a method given a positional, or itself only a chain). Still
  not drawn: a chain of two or more hops; click's `@cli.command("sdist")`
  (`method-positional`, 10 rows).
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
- **You find out:** **partial** (2026-08-25, ADR-090 — the oracle
  lane's W1). The row still counts the site **resolved** — that
  concession stands, and the capture number still reads better for it —
  but `resolution_coverage` now carries `floored` per file and the tail
  view names the class **`below-floor`** (*seen, not modelled by
  design*: the semantic lane resolved the site to a declaration lane A
  keeps no symbol for — an interface method, a closure, a nested
  function). The ingest summary prints it under *seen, not modelled by
  design* (this repo: go 3, python 35, ts/js 10), `list_blind_spots`
  marks it not-modelled and prints it in its tail (C-77, registered
  2026-09-02 and lifted 2026-09-03), and the tail sums to `unresolved +
  floored`.
  What stays conceded: the capture line does not move, and a site the
  checker resolved to a declaration it *does* have a symbol for but
  through an interface it cannot see past (the Go/TS interface method
  before C-9's filter) is not in this class — the oracle lane's miss
  record (`docs/oracle/oracle-misses.md`) is still where that is sized.
- **The override set is in the graph (ADR-120, 2026-09-16, 0.2.32-beta).**
  What this entry said Hobbes lacks — which implementations sit below
  an interface method, which classes below a base — was a field the
  helper read past: SCIP's `SymbolInformation.relationships`
  (`is_implementation`). Measured on the six indexers first: scip-clang,
  scip-go, scip-typescript, scip-python and scip-java state it (scip-java
  in both directions on an abstract method, oriented by the type level);
  rust-analyzer states none (C-157). The helper decodes it (version 5),
  the join draws each pair as an **`implements`** edge at semantic tier,
  and `who_calls` on an interface method lists its implementors under
  "implemented or overridden by" with this entry's caveat. **What stays
  conceded:** no `calls` edge is drawn *through* the interface — a call
  to `s.Get(key)` still reaches `Store.Get` and not `MemStore.Get`, and
  `tests_guarding`'s reach still follows `calls` only (ADR-007); the
  expansion of a call into its overrides is ADR-120 §7's open decision,
  with the oracle question it carries. And a pair whose end lane A keeps
  no symbol for — Go's interface method specs, which lane A does not
  declare (C-9) — is counted (`implements_below_floor`, the ingest
  summary's "below lane A's floor" line) and not drawn: on this repo 7
  of 25 in-repo pairs, all of them Go's.
- **Provider (P9):** ours. `scip-go` **0.2.7** resolves the occurrence
  correctly (to the interface method); Hobbes' descriptor filter and the
  absence of a dispatch analysis are Hobbes' choices. The override set
  is the indexers' (above), read since ADR-120.
- **Folds in:** C-97 (2026-09-13) — the TypeScript face above, with its
  provider shape and the `union-member` class.
- **Source:** oracle lane O1/O2 (ADR-089, `docs/oracle/oracle-grading.md`;
  `bench/oracle/`), 2026-08-25 — the lane's first graded miss, on the
  `twomod` fixture, then 45 of 45 non-inflated misses on this repo.
  Related: C-1 (the general rule that absence is not evidence), C-9
  (the descriptor filter), C-7 (the syntactic fallback that *did* draw
  an edge for a closure call in `hobbes-session/main_test.go` — to the
  wrong target, the package function of the same name; the oracle's 3
  syntactic-tier contradictions).

### C-70 — Two calls of the same name on one line can pair with the wrong resolution
- **Cannot tell you:** which of two identically named call sites on a
  single source line a given resolution belongs to. The join keys
  evidence on `(file, line, name)` and tie-breaks by nearest column, so
  where one line holds `foo(bar.foo(), x)` — two sites named `foo` —
  the syntactic and semantic lanes can pair with different ones, and
  the edge drawn may be attributed to the neighbouring site.
- **Because:** ranges are what the two lanes can agree on (§3.4), and
  the evidence IR records a line per site; column is carried but used
  only as a tie-break, because the providers do not agree on columns
  closely enough to key on them (a chain continuation, a wrapped
  argument list and a macro expansion all move one). Keying on the pair
  would mean either dropping sites the providers place differently or
  inventing an alignment — a false edge in place of a coarse one.
- **Bites at:** fluent chains and overloads above all, which is why
  **Java found it**: `.getHighlight(highlightQuery.getHighlight(), …)`
  on one line. Measured at **2 of 3,908 dual-resolved sites (0.05%)** on
  spring-data-elasticsearch and **0** on jsoup (3,417), petclinic (36)
  and this repo — small, and not zero. The *edge* is usually still
  right, because both candidates are real calls on that line; what is
  unreliable is which site it is attributed to, and therefore the
  caller when the two sit in different declarations.
- **You find out:** **surfaced, as a disagreement** — `hobbes lanes`
  reports exactly these rows (both lanes resolved, different targets),
  which is how this entry came to exist; the oracle lane reports the
  same shape from its side as `line-grain tolerance used on N edges`,
  printed on every cell. What is *not* surfaced is a collision only one
  lane resolved: there the pairing is unchecked. Note (2026-09-02):
  because the surfacing *is* the disagreement, `hobbes lanes` — and
  `scripts/ci-graph.sh` with it — exits 1 on a registered limit
  wherever a repo writes `f(x.f())` on one line (quic-go: 17 of 6,743
  dual-resolved sites, 0.25%, `jsontext.String(x.String())` ×15);
  whether CI should fail on it is open. **Settled 2026-09-17 (ADR-123,
  0.2.36-beta):** a row is shaped `same-line-pair` when the line holds two
  or more sites of that name and lane A's one guess is lane B's answer at
  another of them; a line of only such rows (with any other registered
  shape) exits 3 and CI passes. A same-named line whose guess matches no
  sibling's answer stays unexplained and still exits 1.
- **Source:** measured 2026-08-29 on the O8 Java cells (ADR-096); the
  key is ADR-029's.

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
  on zero evidence would be the P11 mistake at class scale. **Java adds
  two classes of its own** (ADR-096), both abstentions rather than
  origins: `overload-set` — the name binds to more than one declaration
  the argument count cannot separate — and `inherited-member` — the
  site sits in a type that declares supertypes, so the callee may be
  inherited and only lane B's hierarchy knows; its `local-binding` is
  binding-proven with scope containment (an anonymous-class or
  enum-constant body's extent), like Python's and Go's. **Builtin lists are
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
  classification. **`expr-callee` needs no line read** (2026-09-05):
  the Python and TS providers recorded the site under the marker name
  `<expr>` because the callee node was not a name or attribute chain —
  the parse is the observation; Go, Rust and Java do not record it,
  and their rows in `tail_classes_available` say so.
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
  syntax providers would narrow it further. **Corrected 2026-10-02
  (0.2.84-beta):** the `local-binding` gloss `list_blind_spots` served
  said "the call stays inside that file". The binding is in the file;
  what it holds need not be: rich's `_Segment = Segment` holds another
  module's class (155 such sites on rich, read with `ast` in the C-9
  step 0). The gloss, and `hobbes plan`'s manifest, now say that what a
  local binding holds may be defined anywhere.
- **Source:** ADR-045; surfacing ADR-053.

### C-170 — A Python name scip-python gives one moniker at several lines of a file has no lane B answer
- **Cannot tell you:** which definition a reference means where scip-python gives one
  moniker to several definitions in one file. The site draws no `semantic` edge.
  **Narrowed at 0.2.73-beta (ADR-153):** a bare-name call written in the function whose own
  body writes the one `def` of that name is drawn by lane A, `syntactic`. What is left
  draws nothing: such a def passed as a value, a call to it from a sibling closure, and a
  name ADR-153 refuses (bound twice in its scope). Nothing is guessed.
- **Because:** scip-python names a def nested in a method by its class and its own name,
  and drops every function scope between them (read on a ten-line fixture in the image,
  2026-09-24). So same-named nested defs in sibling methods share one moniker. flask's
  `TestStreaming` tests are an example: each nests `index` → `generate`. A class
  attribute placed twice in one scope, or a method defined twice in one class body, does
  the same. (A property's getter and setter, an `@overload`'s stubs and an `if`/`else`
  def are **one** definition in its index, at the first def, with a reference at each
  later def's name, so they are not affected. Their later defs were the caller of
  misfiled `uses` facts until 0.2.75-beta, a defect ADR-155 fixed.) Until 0.2.70-beta
  the helper kept such a moniker at its smallest line, as C does (ADR-109). Every
  reference was filed under the first definition: 4 wrong `semantic` edges on the graded
  cells (flask `tests/test_helpers.py` 251, 281 and 310; click `src/click/core.py` 1888),
  and 3 right only by the order they came in.
- **Bites at:** a method's same-named nested defs: flask 9 monikers (its `App`,
  `Blueprint` and `Scaffold` each nest several `decorator`s), click 2, attrs 20, this repo
  10. The three right edges went with the four wrong ones. flask read 1,521 → 1,519
  confirmed and click 3,755 → 3,754, each at 0 contradicted (ADR-150). ADR-153 drew the
  seven sites back, each at its own def: flask 1,524 and click 3,756 at 0.2.73-beta.
- **You find out:** **surfaced** — one `scip-decode` degradation record per ingest, in
  Python's own wording, counts the monikers and the references left without an answer,
  with examples.
- **Provider (P9):** scip-python **0.6.6**, its descriptor for a def nested in a method.
- **Source:** flask's key (`oracle-grading.md` §10.35, §10.36, §10.37); ADR-150, ADR-153;
  `~/.hobbes/bench/py-multidef/`, `~/.hobbes/bench/py-route-c/`.

### C-171 — A file nested deeper than lane A's walk reaches is not read
- **Cannot tell you:** the symbols and call sites of a file whose syntax tree is nested
  deeper than its language's lane A walk can recurse. The file keeps its module node and
  is read as empty. The rest of the repo is read as before.
- **Because:** Python's recursion limit. Since 0.2.71-beta the Rust, Go, Java and
  Terraform walks use an explicit stack, as C and C++ have since ADR-128, so a 5,000-call
  chain reads in full. Anything in a provider that still overflows is caught per file.
  **Python's** lane A walk (`pysource`) is a structural visitor carrying its scope
  stack. It overflows near 600 levels, where CPython itself compiles 2,000, so a valid
  Python file between the two is not read.
- **Bites at:** a very long builder or fluent chain in one expression, and generated
  code. It was found at moonlab @ `cd3b234` `bindings/rust/moonlab-sys/build.rs`, a
  bindgen chain of 537 calls, which **ended the whole ingest** before 0.2.71-beta (the E3
  draw, `calvin-experiments.md` §6). Python's threshold was measured on a synthetic
  chain; no repo has met it yet.
- **You find out:** **surfaced** — one `extraction_errors` record per file (stage
  `parse`, naming C-171), which `list_blind_spots` reports as a degraded extraction.
- **Source:** `pipeline/tests/test_deep_files.py`; the E3 draw's record.

### C-174 — A call the language makes with no call token is not a site — *narrowed 2026-10-01 (ADR-156, 0.2.79-beta): a sync `with` item whose own call is drawn `semantic` to a class, or to a def whose return annotation the index resolves to one, has its `__enter__`/`__exit__` drawn; narrowed 2026-10-03 (ADR-171, 0.2.100-beta): a call of an instance constructed at the call (`C(…)(…)`) or bound once from a construction (`x = C(…)`; `x(…)`) has its class's `__call__` drawn; narrowed 2026-10-04 (ADR-178, 0.2.118-beta): a Rust operator applied to a repo impl is drawn as a call where rust-analyzer names the impl's method at the token*
- **Narrowed 2026-10-03 (ADR-171, 0.2.100-beta).** Where the callee of a call is a construction the index
  draws `semantic` to a repo class, either written in place (`C(…)(…)`) or as a local the function binds
  exactly once by `N = C(…)` (ADR-160's refusals), that class's `__call__` (its own, or up a chain of single
  named bases) is drawn as a `syntactic` `calls` edge at the call's line, `via: "__call__"`. The held-out
  structlog cell gained 130 confirmed rows, none wrong; the held-out pyparsing cell 23, its `pp.X(…)(…)`
  sites abstaining under C-178. **Still not drawn:** an instance held in an attribute or a parameter
  (`self.highlighter(…)`, most of the fitted cells' `__call__` misses), a factory's result, a name bound
  more than once or at module level, a class writing `def __new__` on its in-repo chain, and a metaclass
  or out-of-repo base whose `__new__` or `__call__` returns another type (the rule cannot see it). The
  ingest counts each abstention in `graph.json`'s `instance_calls` block. **The attribute-held shape,
  measured 2026-10-03 and closed without a rule (Max: "close as measured"):** of the 29 `__call__` misses
  still open on the fitted cells at ADR-171's after arm (rich 21, click 7, flask 1), 13 are written
  `self.x(…)`, and 5 of those (all rich) name an attribute the class assigns once by a bare construction.
  The rest are `x or C()`, an injected parameter, a factory, or a test's monkeypatch, which no static read
  of the class can type. The pre-registered held-out draw (voluptuous) writes about 2 gradable sites.
  Reading an attribute's type across methods stays out of this layer (ADR-171)
  (`~/.hobbes/bench/attr-call-step0-2026-10-03/`).
- **Narrowed 2026-10-01 (ADR-156, 0.2.79-beta).** Where a sync `with` item is a call drawn `semantic` to a
  repo class, or to a repo def whose return annotation the index resolves to a repo class, that class's
  `__enter__` and `__exit__` (its own or up a single named base chain) are drawn as `syntactic` `calls` at
  the item's line, `via: "with"`. The rich, flask and click cells gained 136 confirmed edges, none wrong.
  **Still not drawn:** a bare-name item (`with ctx:`); an item whose call is drawn only `syntactic` (40 of
  flask's, on the `app` fixture's value); an unannotated factory; `@contextmanager`; an annotation naming an
  outside type; `async with`; and every operator and iteration dunder. The ingest counts each abstention in
  `graph.json`'s `with_statements` block.
- **Audited 2026-10-01 (0.2.80-beta), one fixture per language.** Max: "direct honesty violation
  becomes precedent 1". Each fixture holds one function per shape, and each shape runs exactly one
  method the fixture defines. All seven were ingested in the image at 0.2.79-beta, and every
  control drew `calls semantic`. These are fixture facts, not repo-scale counts. The entry was
  written for Python, and the audit widened it to every language. It also corrected two
  sentences: "none of them is measured", and "draws no edge", which was wrong for Rust and C++,
  where some of these draw `uses`. The drivers and fixtures are in `~/.hobbes/bench/honesty-audit/`
  (`RESULTS.md`).
- **Cannot tell you:** the calls an interpreter, compiler or runtime makes on the code's
  behalf, where no call is written. The target method is a symbol. The statement that runs it
  draws **no `calls` edge** to it. Some draw a `uses` edge at the token (marked *uses* below),
  which `who_calls` lists as a reference and not as a caller. As measured:
  - **Python:** construction runs `__init__`, and the edge is drawn to the class, as the trace
    key also keys it. Also covered:
    - a `with` item's `__enter__`/`__exit__` where its class is not known (ADR-156 draws the
      rest), and `async with`;
    - operators (`__add__`, `__eq__`, `__getitem__`, `__setitem__`, `__contains__`);
    - iteration (`__iter__`/`__next__` in a `for`, a comprehension or an unpacking; `async for`);
    - truth testing (`__bool__`);
    - an f-string or `str()`/`hash()`/`len()` reaching `__str__`/`__hash__`/`__len__`;
    - a call of an instance (`__call__`) held anywhere but the call's own callee or a once-bound local
      constructed from a repo class (ADR-171 draws those);
    - a property's getter and setter (*uses* to the property at a read; where the property's value is
      called, `obj.prop(…)`, the getter is drawn *calls*, since it does run there, and the value's own
      `__call__` is not drawn: pyparsing's `ppu.Japanese.identifier(…)`, corrected 2026-10-02);
    - a descriptor's `__get__`/`__set__`, `__getattr__` and `__del__`;
    - a metaclass's `__call__`, and `__init_subclass__`.
  - **Rust:**
    - `Drop::drop` at scope end, and also through an explicit `drop(x)`;
    - `Deref::deref` at `*x`, and `Add`, `AddAssign`, `Neg`, `Index`, `IndexMut` at the operator: **drawn
      as `calls` since 0.2.118-beta (ADR-178)** where the impl is the repo's and rust-analyzer names its
      method at exactly the token (hecs 68, ureq 17). Still not drawn: `PartialEq` at `==` (rust-analyzer
      writes no reference there; hecs 14, cyme 30), and a `Deref` the compiler applies with no token —
      auto-deref through `.` (`timeout.after.is_zero()`) or a deref coercion (`&q`; ureq 9);
    - `PartialOrd::partial_cmp` at `<`;
    - a `for` loop's `into_iter`/`next`;
    - `Display::fmt` under `format!`;
    - `From::from` under `?` and under `.into()`.

    An auto-deref method call is drawn.
  - **Java:**
    - try-with-resources `close()`;
    - for-each `iterator()`/`hasNext()`/`next()`;
    - string concatenation's `toString()`;
    - an implicit `super()`;
    - `new` of a class with no declared constructor, which lands on the class and reaches no
      base constructor;
    - an enum's `values()`, which is not a symbol;
    - a static or instance initializer block. It is not a symbol, and the calls inside it are
      filed under the class.
  - **TypeScript/JavaScript:**
    - a `get`/`set` accessor, which is not a symbol (the edge is *uses* to the class);
    - `for...of` and spread through `[Symbol.iterator]` and the iterator's `next()`;
    - `await` on a repo thenable's `then`;
    - a template literal or `+` reaching `toString`/`valueOf`;
    - `using`'s `[Symbol.dispose]`;
    - the `super(…)` and implicit constructors C-168 already names.
  - **Go:**
    - a package `init()`, which the runtime calls;
    - a type's `String()`/`Error()` reached through `fmt` or the `error` interface (dispatch,
      C-58's face).
  - **C++:**
    - a destructor at scope end, at `delete`, or as a member's or a base's;
    - a range-for's `begin()`/`end()` and its iterator's `operator!=`/`operator*`/`operator++`;
    - a conversion operator applied implicitly (a symbol since C-175 was lifted; the index writes
      no reference at the conversion, so nothing is drawn);
    - a functor's `operator()` (drawn at the call's `(` outside a template since ADR-175; C-146
      names the rest);
    - a copy constructor, and a converting constructor applied implicitly (drawn where the index
      names it in a body expression since ADR-175; C-162 names the rest);
    - a base constructor run by a derived one;
    - a static object's constructor (*uses*, from the module).

    An operator applied by symbol is drawn where the index names it at the token, and only
    outside a template (C-146).
  - **C:** `__attribute__((cleanup(f)))` and `__attribute__((constructor))`.
- **Because:** lane A records a call where a call is written, and lane B's indexers give no
  reference, or only a non-call reference, at a `with`, an operator, a loop, a scope's end or a
  coercion. These are not sites, so they are in no count, and C-2's denominator does not hold
  them. C-1's general rule ("an absent call edge never means this does not happen") covered them
  only by its title, since its stated causes are dispatch and values. Until 0.2.78-beta nothing
  named them.
- **Bites at:** `who_calls` and `tests_guarding` on any of the targets above, and dead-code
  intuitions about them. Measured on the three keyed Python cells (the held-out rich cell,
  `oracle-grading.md` §10.40): observed `__exit__` misses rich 75, flask 88, click 35. The trace
  oracle sees almost no `__enter__` (rich 1), because CPython 3.12 emits no call event for it, so
  `__enter__`'s share is unmeasured, not small. **Counted at repo scale 2026-10-03**
  (`~/.hobbes/bench/c174-counts-2026-10-03/`; every site count an upper bound, the receiver's type
  unknown): Python's stored traces hold no implicit dunder call at all (the tracer listens to `CALL`
  and `PY_START` and keys only `with` and `__call__`), and the lines that may reach a repo dunder run
  from 875 (flask) to 6,308 (pyparsing); Rust's graded crates define 20 `Iterator`, 12 `From`, 2
  `Deref`, 1 `Drop` and 1 `Display` impl and no operator, `Index` or `PartialEq` impl (memchr 280 `?`,
  139 index, 208 comparison sites); Java's cells 162 `toString`, 18 `close`, 15 `iterator` bodies
  (enhanced-for 12–340, try-with-resources 3–48 per cell); TS/JS 105 class and 108 object accessors,
  5 `then`, no `[Symbol.iterator]` or `[Symbol.dispose]`; Go 45 `String()`, 30 `Error()`, 39 `init()`
  over six repos; C++ fmt and args 46 destructors, 24 `operator()`, 46 `begin`/`end` members; C's
  cells no `cleanup` or `constructor` attribute.
- **You find out:** **surfaced**.
  - The always-on "not detected at all" statement in `list_blind_spots` and in `hobbes plan`'s
    manifest names it in every language's terms since 0.2.80-beta.
  - `who_calls` says it at the point of use. Its "no recorded callers" line names C-174 beside
    C-1.
  - `who_calls` notes a hook its name alone shows, before any caller line: a Python dunder, a
    C++ destructor or operator, a TS/JS `[Symbol.*]` method, and a Go `init`. The note says the
    list is a floor.
  - `who_calls` names this entry on a `uses` reference.
  - Rust's and Java's hooks (`drop`, `close`, `next`) are ordinary names, so no note can single
    them out.
- **Source:** the rich, flask and click cells' misses (`~/.hobbes/bench/heldout-rich/`); the
  structlog and pyparsing held-out cells (`~/.hobbes/bench/heldout-structlog/`, ADR-171); the
  2026-10-01 audit (`~/.hobbes/bench/honesty-audit/`); `go/internal/knowledge` and
  `derive/manifests.py`, with their tests.

### C-176 — A call's caller is the nearest enclosing symbol, so code below the symbol floor speaks as its container — in TypeScript and JavaScript, as the module — *registered 2026-10-01 (0.2.80-beta, the honesty audit); narrowed 2026-10-01 (ADR-158, 0.2.82-beta): a named class owns its constructor, accessors, static blocks, field initializers and member decorators, and a nested function's calls are its top-level symbol's; widened 2026-10-03 (0.2.104-beta): measured on Go and Java, Java's enum constant bodies and Go's package vars named, and `who_calls` says so for both; narrowed 2026-10-04 (ADR-179, 0.2.120-beta): a member of an object literal bound at top level is its own caller*
- **Cannot tell you:** which function a call is written in, where that function is not a graph
  symbol. Every lane files a call under the innermost enclosing **symbol**. So a lambda's or a
  closure's calls are filed under the def around it, and a top-level callback's under the module
  (C-9's floor, C-58's closures). Python, Java and, since ADR-158, TS/JS file a class body's code
  (an initializer, a static block, a TS constructor or accessor) under the class. In Java that
  includes **an enum constant's body**: `Initial { boolean process(…) { … } }`'s method is no symbol,
  so its calls are the enum type's, and so are an anonymous class's written in a field. A Go
  **package var's initializer**, a function literal assigned to the var included, is filed under the
  var. TS/JS's symbols
  are top-level declarations, the methods of top-level named classes and, since ADR-179, the
  members of an object literal bound at top level (scope only: never a target), so the calls inside
  these are filed under the **module**, as if written at top level:
  - the method of an object literal that is not bound at top level (returned, passed, nested in
    another literal, assigned below top level), and a member whose qualname the file writes twice
    (a getter and its setter);
  - an unnamed class's method;
  - a function assigned to a property (`res.send = function send(…)`, `X.prototype.y = function`);
  - a namespace's function.

  The same holds for a function nested in any of these.
- **Because:** these are below the symbol floor (C-9). Making them symbols would move the symbol
  set, which is Max's call (the CJS literal member is the same question). **No key reads a caller.**
  Every grade is over `(site, target)` (C-164 said so for C++ alone), so no cell's precision sees a
  caller filed too high.
- **Bites at:** `who_calls` on anything such a method or property function calls reads "module X
  calls f", top-level import-time code that is not there. Also `graph_neighborhood`. Measured at
  0.2.82-beta against the tsc key's callers (`~/.hobbes/bench/c176-ts-scope/probe.py`, rows where
  Hobbes says the module and the key a named function): ajv 338 (mostly its object-literal
  `code(cxt)` keyword methods), Preact 247 (prototype-assigned functions), cheerio 52, cue 51,
  tileserver-gl 43, Express 16, npq 7, xmpp.js 7, folio-2025 0. **Go and Java, measured 2026-10-03**
  at 0.2.102-beta against the RTA and javac keys' callers (`~/.hobbes/bench/c176-go-java-2026-10-03/`,
  a port of the TS probe; 0 rows where Hobbes's caller does not hold the line): Go's closures toml 107,
  mux 266, fzf 660, cobra 202, gitleaks 96, quic-go 91, this repo's `go/` 37, dagger's 19 cells 755; a
  package var's func literal gitleaks 51, quic-go 32 (a var's other initializers have no key site:
  mux 29, gitleaks 6, quic-go 5). Java: jsoup's enum constant bodies **1,691** (`HtmlTreeBuilderState`,
  `TokeniserState`), its anonymous classes 93 and field initializers 68; Severed-Chains' field
  initializers 5,969 (2,231 inside lambdas); spring-data-elasticsearch 309 and spring-petclinic 3, all
  class-body code. Go's `init` and a Java lambda in a method agree with their keys.
- **Was (to 0.2.119-beta):** a member of a literal bound at top level was filed under the module.
  Rows re-filed to the member at 0.2.120-beta (ADR-179, the probe on the keyed cells): ajv 628
  (`def.code` keyword methods), tileserver-gl 59, hono 13, zod 11, cue 7, xmpp.js 6, kbet 2; probe
  `lost-caller` ajv 458 → 9, tileserver-gl 43 → 0, hono 8 → 0; grades, test reach and `wrong` unmoved.
  Calls *to* such a member are still not drawn (ADR-179 route (b), not taken): `who_calls` on the
  member says so.
- **Was (to 0.2.81-beta):**
  - **The constructor, an accessor, a `static {}` block and a field initializer** of a named class
    were filed under the module, as were a member's decorators. Module-filed rows inside a class's
    span: folio-2025 501, ajv 26, cue 11, Preact 7, npq 6, xmpp.js 4, tileserver-gl 3. All are 0 since
    ADR-158.
  - **A nested function, a nested arrow const, or a method of a class declared inside a function**
    named itself as the caller, though it is no symbol. The caller id dangled: no node, same-named
    nested functions merged, and test reach could not pass through it. `calls` rows: ajv 341, Preact
    145, tileserver-gl 24, seven more repos 2–8. All are 0 since ADR-158. Test reach grew (npq 139
    tests, cue 48, ajv 51) and shrank nowhere.
- **You find out:** *partial.* `who_calls` adds a note under a caller list that names a TS/JS
  module: the module may stand for the method of a literal not bound at top level, an unnamed class's method, a
  function assigned to a property or a namespace's function, and is not necessarily top-level code.
  Since 0.2.104-beta it adds one under a list naming a Java or Python class (code in its body that is
  no method symbol: an initializer, a block, a Java enum constant's body or an anonymous class in a
  field) and one naming a Go package var (its initializer). `graph_neighborhood` and the surface say
  nothing. The general roll-up rule is stated here and
  nowhere else.
- **Source:** the 2026-10-01 audit (`~/.hobbes/bench/honesty-audit/`); ADR-158
  (`~/.hobbes/bench/c176-ts-scope/`); `tsextract/extract.mjs` `enclosingScope`,
  `tssource._call_sites`, `scipsource.project`.

### C-178 — scip-python names an attribute read through a star re-export as an unrelated symbol — *registered 2026-10-02 (0.2.85-beta, the pyparsing held-out cell); contained the same day (ADR-161, 0.2.86-beta): such a reference is refused before the join and counted*
- **Contained 2026-10-02 (ADR-161, 0.2.86-beta).** A Python reference whose token is not its name,
  written as the member of a dotted chain rooted at a name the file binds by `import`, is refused before
  the join: it draws no edge and is counted. pyparsing: 2,919 refused, `uses` rows to `CaselessLiteral`
  1,671 → 10, `one_of` 338 → 23, `replace_with` 69 → 5; 561 `uses` pairs gone, none added, no `calls` row
  moved; rich, flask and click byte-identical. **What is left:** such a reference has no lane B answer, so
  the call written there stays unresolved; and an external reference (the stdlib's own star re-exports:
  `os.path.dirname` named `join`) keeps its misnamed moniker, which draws no repo edge.
- **Cannot tell you (as registered):** what `pp.Word`, `pp.Forward` or `pp.alphas` name where `pp` is a package whose
  `__init__.py` re-exports by `from .core import *`. scip-python names most such occurrences as one
  unrelated symbol of the star-imported module, and the join draws what it names. On pyparsing 3.3.3:
  397 `uses` and 7 `calls` edges to `pyparsing.core.CaselessLiteral`, all `semantic`, on 1,688 evidence
  rows, where 36 source lines name the class; wrong `uses` rows to `pyparsing.helpers.one_of` (275) and
  `pyparsing.actions.replace_with` (65). The call written at such a site draws nothing, because the
  join's line-and-name claim refuses a name that is not the site's.
- **Because:** the first `<pkg>.<name>` scip-python resolves through a star re-export answers every later
  one, index-wide, across files (reproduced in ten lines in the image, `~/.hobbes/bench/c178-star-reexport/`).
  Read with raw scip-python over the clone (empty environment): of 3,182
  `pp.<name>` occurrences in tests and examples, 3,072 name a symbol other than `<name>` (`Word` 505,
  `alphas` 227, `Group` 212, `Literal` 195, `nums` 166, `Forward` 101 as `CaselessLiteral#`). Why the
  indexer resolves the re-export this way is not read.
- **Bites at:** `who_calls` on `CaselessLiteral` (hundreds of wrong references, 7 callers that may be
  wrong); impact and reach through `uses`; pyparsing's class and function recall (1,247 class and 130
  function misses at `pp.<name>(…)` sites). The trace key grades calls only, so the cell's 0 contradicted
  and its poison PASS say nothing about these rows. rich, flask and click show none of the shape: a
  `semantic` row whose line does not hold its target's name is 108, 10 and 11 rows there, and the rows
  sampled are a member reference rolled up to its class.
- **You find out:** **surfaced** (0.2.86-beta) — one `scip-python` degradation record per ingest with any
  refusal names the count, the cause and three examples, and `list_blind_spots` prints it. Until then it was
  unsurfaced: `hobbes lanes` exits 0 on the cell because the join never claims these occurrences as call
  sites.
- **Provider (P9):** scip-python **0.6.6**, its resolution through a `from … import *` re-export.
- **Source:** the pyparsing held-out cell (`docs/oracle/cells/pyparsing-py-2026-10-02.md`,
  `oracle-grading.md` §10.44, §10.45); ADR-161; `~/.hobbes/bench/c9-local-alias/pp-index/` (the raw index),
  `~/.hobbes/bench/c178-star-reexport/`.

### C-181 — scip-python leaves a call into several standard-library modules unplaced — *registered 2026-10-03 (0.2.88-beta, ADR-164): counted as `stdlib-import`; partial — an in-repo rebinding of such a name keeps lane A's fallback*
- **Cannot tell you:** where a Python call rooted at an import of the standard library lands when scip-python
  names it with a document-local symbol or writes no occurrence for it. The site is not resolved, so it
  never counts as `external`, and before 0.2.88-beta its tail class blamed the wrong cause:
  `import-binding` ("usually a missing environment") for a bare name, `attr-call` (C-2's untyped receiver)
  for a member of an imported module. The target is the standard library, outside the repo, so no repo
  edge is missing. **What is left:** a name a stdlib import binds that an `except ImportError:` branch
  rebinds to a repo function (`try: from urllib.parse import quote` … `except ImportError: from .compat
  import quote`) keeps lane A's `syntactic` edge to the repo function: lane B's local answer cannot veto
  it the way an external answer does (ADR-111). None of flask, click, rich or this repo writes that shape
  (measured 2026-10-03); the `ministdlib` fixture does, and its test pins the edge.
- **Because:** scip-python 0.6.6 names what several stdlib modules define with a symbol local to the
  document (`local N`), at the import and at every use: every member of `urllib.parse`, `email.utils`,
  `importlib.metadata`, `concurrent.futures`, `urllib.request`, `xml.etree.ElementTree`, `http.client`,
  `json.decoder`, `logging.handlers` and `ctypes.wintypes` read in the image, whether written `urlsplit`,
  `parse.urlsplit` (`from urllib import parse`), `eu.formatdate` (`import email.utils as eu`) or
  `importlib.metadata.version`; and `sys.exit` and `typing.overload`, while `sys.getsizeof` resolves. It writes no occurrence
  at all for a call of gettext's `_`. Names that land in a module the index resolves (`os.path.join` →
  `posixpath`, `functools.reduce`, `json.dumps`, `collections.abc.Mapping` → `typing`) are not affected.
  Why the indexer does this is not read.
- **Bites at:** capture and the tail, because the sites stay unresolved. `who_calls` and impact are not
  affected, because Hobbes draws no symbol edge to a stdlib function in any case. Measured at 0.2.88-beta
  as `stdlib-import`: flask 34, click 181 and rich 82 call sites (pyparsing 27). Of those, this entry's
  two causes account for flask 33, click 145 (74 of them `_`) and rich 22. The rest are calls into the
  stdlib that C-173's dead code or C-178's star re-exports left unplaced, and the class counts them too
  (ADR-164's table).
- **You find out:** *partial* — every such unresolved call is counted in its file's tail as
  `stdlib-import`, whose meaning names this entry and the provider in the ingest summary and
  `list_blind_spots`. The residual rebinding edge is drawn `syntactic` and nothing names its cause.
- **Provider (P9):** scip-python **0.6.6** — its document-local symbols for members of several stdlib
  modules, and no occurrence for gettext's `_`.
- **Source:** ADR-164; the flask rows of 2026-10-02 (`~/.hobbes/bench/flask-rows-2026-10-02/`) and
  `~/.hobbes/bench/c181-stdlib-import/` (`probe.py`, `probe.txt`, fixtures `fxc`–`fxe` with raw dumps,
  `run.sh`, `compare.py`, `sites.py`, `causes.py`, `before/`, `after/`).

---

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-59 — A function's call to itself was not an edge — *lifted 2026-08-25, the same day it was registered*
- **Was:** the projection dropped any fact whose caller and callee were
  the same symbol (`scipsource.project`), and the Python fallback did
  the same (`graph.py`) — a v1 choice that kept self-loops out of the
  module graph and was carried into the symbol graph without a record.
  `who_calls(f)` never listed `f`; 16 of dagger's 35 named-declaration
  misses (oracle lane O4) were recursion.
- **Lifted by — the technique:** the projection keeps a `calls` fact
  whose ends coincide; only a *non-call* self-reference (a type naming
  itself in its own body) is still dropped, because that is not an
  edge in any reading. The Python fallback emits the self-call too.
  Verified on the `goshapes` fixture (`Walk -> Walk`, kinds.go:33) both
  by the test suite and by the oracle lane (8/8 both ways).
- **Residual edge cases:** consumers that assume a DAG at symbol grain
  now meet a self-loop — `hobbes plan`'s partition and the surface's
  layout handle cycles already (mutual recursion always existed), but
  a self-loop is a new shape and any consumer that unrolls edges must
  not loop on it. Mutual recursion through a helper was always drawn.
  Self-`uses` stays out by design.
- **Source:** registered and lifted 2026-08-25 (oracle lane O4 finding;
  W1 fix). `scipsource.project`, `graph.py`.

### C-163 — A matched call hid every other reference of its name on the line — *lifted 2026-09-18, the day it was registered (ADR-133, 0.2.45-beta)*
- **Was:** `evidence.join` claimed a lane B resolution by `(file, line,
  name)`, so one matched call or import site hid **every** resolution of
  that name on the line, not only the one it matched. None of the others
  reached the unclaimed loop, so none became a `uses` fact, an operator
  call (ADR-131) or a construction call (ADR-132). Measured on the 25
  graded clones (`~/.hobbes/bench/join-claim/`): 7,308 resolutions
  hidden, 1,158 of them alternates at the matched occurrence's own
  column and the rest true facts at another — the declared type in
  Java's `Element el = new Element("div")`, a TS interface beside the
  function of its name, the return type in Go's `func (r *body)
  StreamID() quic.StreamID { return r.str.StreamID() }`, and fmt's 19
  constructions typed through a using-declaration (ADR-132's P102
  miss). True since ADR-029 and in no register entry until ADR-132's
  grade met one shape of it.
- **Lifted by — the technique:** the claim's key is the matched
  resolution's own position, `(file, line, name, col)`. It is the
  *resolution's* column, so the providers need not agree on columns
  (C-70's reason the match itself is still by name and nearest column
  stands). Regraded on 44 stored-key cells (`oracle-grading.md` §10.18):
  fmt 6,993 → 7,012 confirmed at 0 contradicted, every other cell ±0;
  1,785 `uses` and 11 `calls` symbol edges added, two module edges
  (both read true), nothing removed.
- **Residual edge cases, by design:** a resolution at the matched
  occurrence's **own column** stays hidden — the index places a
  declaration and its override at one position, and ADR-104's
  abstention claims its resolution so the alternates do not resurface.
  A **site lane A recorded no column for** keeps the by-name claim:
  the match took the first resolution of the name, which one is not
  known, and an unsure claim draws less (no contested site on the 25
  clones was columnless). No key judges a `uses` edge: the 1,785 rest
  on the hand read, not a grade.
- **Source:** registered and lifted 2026-09-18 (ADR-133; unit `3569`).
  `evidence.join`.

### C-169 — A Python decorator was not a call site, and a commented one was not read at all — *lifted 2026-09-20, the day it was registered (ADR-146, 0.2.65-beta)*
- **Was:** `pysource._walk` did not walk a decorator's expression — a
  decision from the first extraction milestone ("recording it would
  pollute the call graph"), pinned by a test and carried by no register
  entry, no tool and no line of the architecture. So `@click.option("--x")`,
  a direct call of a declared function, had no lane A site, the join had
  nothing to pair the index's occurrence with, and no `calls` edge was
  drawn: `who_calls` on a decorator answered *nobody* for every use of it
  as one. On click (py-trace key, 0.2.64-beta) **0 of 2,447 edges sat on a
  decorator line and 1,652 of 2,459 missed pairs did**; `oracle-misses.md`
  had filed them under C-58 beside function values. Beside it, found
  reviewing the unit: the decorator digest read the node's **last child**
  as the expression, and a trailing comment is a child — `@pytest.fixture
  # shared` digested to no name, so the fixture was no fixture, a route no
  route, a `parametrize` unread (one to three such lines in each of click,
  flask, attrs and missy).
- **Lifted by — the technique:** a decorator is a call of what it names.
  Its expression is walked as any expression is, scoped to the
  **enclosing** definition (the decorated one does not exist yet); a bare
  `@name` / `@a.b` is the application the language defines, one site at
  the terminal identifier. Lane A only — what is drawn is the join's
  business, so an edge appears exactly where the index names a repo
  symbol. `_decorator_expr` reads the first named child that is not a
  comment, at all three sites. click **2,136 → 3,052 confirmed of 4,595
  (46.5% → 66.4%), 18 suspect before and after — the same rows — poison
  PASS**; flask +166 and attrs +120 rows, all `semantic`, none lost; no
  symbol, node or module edge moved (`oracle-grading.md` §10.30).
- **Residual edge cases, by design:** a bare decorator that is not a name
  chain (`@decos[0]`) applies nothing Hobbes can name; the calls written
  in it are still sites. What a decorator **returns** is not followed —
  `@click.command()` reaching `command.<locals>.decorator` is a function
  value (C-58; ADR-147 measures the factory shape). Resolution coverage's
  denominator now counts these sites; an unresolved one (`@app.route` on
  an untyped `app`) is in the tail like any other. TypeScript's walk
  takes every `CallExpression`, a decorator's among them (read in
  `tsextract/extract.mjs`, not measured on a cell); a bare TS decorator
  is not recorded and no cell has sized it. A Java annotation is not a
  call.
- **Source:** registered and lifted 2026-09-20 (ADR-146; unit `f751`,
  the comment defect fixed at its review). `pysource._walk`,
  `pysource._decorator_expr`.

### C-80 — A Python call whose receiver was itself a call, a subscript, or `super()` was not a call site — and `who_calls` said it was not a call — *lifted 2026-09-03*
- **Was:** `pysource.Call` was "a call site whose callee is a plain
  name/attribute chain", so `super().m(..)`, `f().m(..)` and
  `xs[i].m(..)` were not detected; SCIP still resolved the name, the
  join emitted a `uses` edge (a resolution no site claimed, ADR-029),
  and the tool rendered it under *"references … without calling it
  (type annotations, except clauses, values passed by name)"*. peft
  (2026-09-02): of 7,910 `uses` evidence lines, 152 were
  `super().name(..)`, 60 `<call>().name(..)`, 40
  `<subscript>[..].name(..)` — every one a call; for
  `PeftModel.save_pretrained` all 49 "non-calling references" were
  calls such as `model.cpu().save_pretrained(tmp_dir)`. *Partial*: the
  edge existed with its line; the label asserted the opposite.
- **Lifted by — the technique:** two halves. (1) Lane A records the
  site: when the callee is an `attribute` whose object is not a name
  chain, the `Call` carries `EXPR_RECEIVER.<name>` (`<expr>.m`), with
  the terminal's line and column, so the range join pairs it with the
  semantic occurrence and the edge is `calls` at the semantic tier; the
  fallback (`graph._resolve_call`) returns nothing for an `<expr>`
  head — the receiver is what lane A cannot name, and it says so
  rather than binding `m` to the module's or the class's own `m`. The
  tail reads the source text and classes an unresolved one `attr-call`.
  (2) The `who_calls` gloss for `uses` now says what is known —
  *"references X where no call site was detected (type annotations,
  except clauses, values passed by name; a call through a receiver
  lane A cannot see, C-1)"* — instead of "without calling it". Tests:
  `test_expression_receivers_are_sites`,
  `TestExpressionReceiversAbstain`, `TestWhoCallsSeparatesUsesFromCalls`
  (the heading). The image must be rebuilt for the gloss (C-65).
- **Residual edge cases:** ~~a call whose *callee itself* is an
  expression — `handlers[0]()`, `getattr(x, "y")()`, `(a or b)()` — is
  still no site~~ — **closed 2026-09-05:** it is a site named by the
  marker alone (`EXPR_RECEIVER` as the whole callee), counted in the
  denominator and classed `expr-callee` by the tail (ADR-045 amended;
  C-63 surfaced the same way for TS/JS). The name is still not there to
  be joined, so nothing resolves it and its resolution, where SCIP has
  one for the receiver, is still a `uses` edge under the reworded
  gloss; the grounder reads no reference from it. The capture
  denominator grows by the new sites (peft: +252 the entry counted;
  the callee-expression sites will add to that on the next ingest); a
  site SCIP does not resolve is a new `attr-call` or `expr-callee` row,
  not a resolved one.
- **Source:** the four-repo extraction test of 2026-09-02 (agent A,
  huggingface/peft); lifted 2026-09-03.

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
