# Changelog — the Hobbes layer

One entry per version of the Hobbes layer (ADR-103): what changed in
the product, in plain words, with the ADRs and constraints it rests on.
The experiments under `bench/` and the records under `docs/` are
internal testing and do not appear here except where a finding became
a fix. The session-by-session history is `docs/BUILDLOG.md`; the
running architecture is `docs/hobbes-architecture.md`. The number line
is Max's (ADR-103): a change to what the layer draws, refuses or says
bumps patch; a capability bumps minor. The layer stayed on 0.1.x, patch
by patch, through 0.1.23-beta (the third amendment, 2026-09-10; the
earlier 0.11.0-beta statement withdrawn), and the Calvin harness moved
it to 0.2.0-beta (the fourth amendment, 2026-09-12). Tags are his call
each time (0.1.9-beta to 0.2.9-beta and 0.2.11-beta to 0.2.69-beta
untagged; 0.2.10-beta is tagged `v0.2.10-beta`, on Max's word at the
close of 2026-09-13).

## 0.2.69-beta — 2026-09-22 (the fixture value through a local, and an inherited method; ADR-145 amended, C-4 narrowed)

**Patch: what the layer draws** — Python, after the projection. Built as unit
`S-20260922T155044Z-54cf`; two defects fixed at its review.

- **The shape.** flask's `app` fixture binds `app = Flask(…)`, configures it and
  `return app`. ADR-145 read only `return C(…)`, and refused a method the constructed class
  inherits: most of what flask's tests call on `app` — `route`, `get`, `errorhandler` — is
  `Scaffold`'s, and `add_url_rule`, `register_blueprint` are `App`'s.
- **The rule.** A returned bare name counts as the construction when it is bound exactly
  once, by a top-level `x = C(…)` before the return, with no `nonlocal`/`global` of it and no
  nested def of its name. Where `C` has no `def m`, the walk goes up single bases the index
  names on each class's own `class` line and takes the first `def`. Refused and counted:
  `patched` (the test or fixture stored onto the instance, or passed it to a `setattr`),
  `class-binds`, `multiple-bases`, `base-unnamed`. The ingest's `fixtures:` line says how
  many drawn calls were inherited and how many came through a local.
- **Measured.** flask, keyed for this (a new py-trace cell, 494 tests passed both runs):
  **1,121 → 1,521 confirmed of 2,698 (41.5% → 56.4%)**, 400 added, 329 inherited, 0
  contradicted, poison PASS, 0 rows lost — the pre-registered probe's rows exactly
  (`oracle-grading.md` §10.35). click and attrs unchanged.
- **The verification base** names flask: Python reads nine repos.
- **Fixed at the review:** a nested `def x` in the fixture was not counted as a second
  binding of the local; a class-body binding of `m` beside its `def` was not asked.
- **Found, not fixed:** three of flask's 18 suspects are wrong `semantic` edges — a nested
  def resolved to a sibling test method's same-named nested def. The cause is not yet read.

## 0.2.68-beta — 2026-09-22 (a decorator factory that returns another factory's call; ADR-149, C-58 narrowed)

**Patch: what the layer draws** — Python, after the projection. Built as unit
`S-20260922T002232Z-67cc`; no defect found at its review.

- **The shape.** click's `group()` holds no nested def and ends `return command(name, cls,
  **attrs)`; `version_option()`, `help_option()` and their siblings end `return
  option(*param_decls, **kwargs)`. At `@click.group()` the site applies what `command(None,
  Group)` returned — `command.<locals>.decorator` — and neither ADR-147 nor ADR-148 read it.
- **The rule.** Lane A digests such a body (`Symbol.chain_fold`): ADR-148's program, with
  each `return <call>` recording its callee, its line and its arguments. The outer factory is
  folded over the site's arguments; every reachable return must be a call the index names
  from the factory at that line to one second factory `G`. `G` must then reach its one nested
  def, either always (ADR-147) or folded over the arguments forwarded to it. A `**x` leaves
  every parameter it might fill unknown, never its default. Drawn `calls`, `syntactic`, `via:
  decorator-factory-chained`, one level only. Refused and counted: `chain-guard-unknown`,
  `chain-unresolved`, `chain-inner`. The ingest's `decorators:` line says how many were
  chained.
- **Measured.** click **3,703 → 3,755 confirmed of 4,561 (81.2% → 82.3%)** on `click-py-r3`:
  67 drawn, 52 confirmed, 15 on lines the key never ran, 0 new suspects, poison PASS, 0 rows
  lost (`oracle-grading.md` §10.34). The pre-registered probe's 66 rows and one more, read:
  a splat site (`@click.help_option(*name_specs, **option_attrs)`) the probe refused and the
  rule's wording binds as unknown, reaching `option` on every path. attrs and flask
  unchanged.

## 0.2.67-beta — 2026-09-21 (a decorator factory's guards, folded over the site's own arguments; ADR-148, C-58 narrowed)

**Patch: what the layer draws** — Python, after the projection. Built as unit
`S-20260921T131857Z-b4d4`; one defect fixed at its review.

- **The shape.** click's `command` is the optional-parentheses idiom: a bare `@command`
  returns `decorator(func)`, while `@command()` returns `decorator`. ADR-147's strict wording
  refused the factory whole (491 click sites, `no-returned-def`). But the arguments the
  site writes decide the path: at `@command()`, `name` is `None`, `callable(None)` is
  false, and `return decorator` is the only return reached.
- **The rule.** Lane A digests each call-form decorator's literal arguments and, for a
  factory ADR-147 cannot settle, its signature and own body as a small program. The fold
  binds the site's arguments and evaluates the factory's guards three-valued (`is None`,
  `is not None`, `callable()` on a literal, `not`, `and`/`or`; an unread test takes both
  arms). It draws `calls`, `syntactic`, `via: decorator-factory-folded`, only where every
  reachable return is the one nested `def`. It refuses `method-positional` (a method
  factory at a site passing a positional: lane A cannot tell `@obj.f(x)` from
  `@Cls.f(x)`) and `guard-unknown`, each counted in `graph["decorators"]` and on the
  ingest's `decorators:` line, which now says how many were folded.
- **Measured.** click **3,356 → 3,703 confirmed of 4,561 (73.6% → 81.2%)** on
  `click-py-r3`: 397 drawn, 347 confirmed, 47 on lines the key never ran; poison PASS;
  0 rows lost. The built rows match the pre-registered probe's row for row
  (`oracle-grading.md` §10.33). attrs draws 18 (`@attr.s(…)`), flask 0.
- **Three new suspects, read and owned** (Max: route a). In three `pytest.raises` tests,
  the decorator *below* `@click.command()` raises during its own application, so
  `command()`'s `decorator` is never applied. The edge is the code as written; the run
  never reached it.
- **Fixed at the review:** a typed `*args: T` / `**kwargs: T` was read as an unnameable
  parameter, which left every annotated factory unfolded (click's all).

## 0.2.66-beta — 2026-09-20 (a decorator factory's application is a call of the def it returns; ADR-147, C-58 narrowed)

**Patch: what the layer draws** — Python, after the projection. Built as unit
`S-20260920T214123Z-db45`; two defects fixed at its review.

- **The shape.** `@click.option("--x")` is two calls: `option(…)`, drawn since
  0.2.65-beta, and the application of what it returned — a call of
  `option.<locals>.decorator` that no token spells, so the index emits nothing for it.
- **The rule, the strict wording** (Max: "whicever is more honest. we never sacrifice
  honesty for higher recall"). Drawn `calls`, `syntactic`, `via: decorator-factory`, only
  where the index names the factory at the line (`semantic`), the factory has one
  undecorated, non-async, non-generator body (an `@overload` stub is looked past), and
  **every** `return` in it is the one nested `def` bound once there. Then the claim holds
  on every path.
- **Measured.** click **3,052 → 3,356 confirmed of 4,595 (66.4% → 73.0%)**: 368 drawn,
  304 confirmed, 0 contradicted, 64 on lines the key never ran; 18 suspect before and
  after; poison PASS; 0 rows lost — the pre-registered probe's figures exactly
  (`oracle-grading.md` §10.31). flask draws 1 (read by hand, right), attrs 0.
- **Not taken, and counted where you can see it.** The loose wording (some `return g`)
  read 661 click rows at 0 contradicted. click's `command` also has `return
  decorator(func)`; on that path the site does not call `decorator`. Its 491 sites are
  `no-returned-def` in the graph's new `decorators.factory_calls.refused` and on the
  ingest's new `decorators:` line; flask's `Scaffold.route` (under `@setupmethod`) is 162
  `decorated`.
- **Fixed at the review, found by the host's `lane_b` run:** a module-level
  `@factory("a")` was counted drawn and not in the graph — the edge append kept symbol
  callers only; the caller may be the module node.
- Oracle lane: **H-36 logged, open** — a `<genexpr>` frame entry keyed as a call pair;
  this repo's Python recall reads 84.6% where the pairs anyone wrote give 94.6%.
  *Later the same day (no version — the oracle lane is not the layer):* H-36 fixed at
  the py-trace extractor (unit `de0e`) and closed; regraded, this repo's Python recall
  reads 85.6% → 94.8% at `2c915a8` (the figures above were the first estimate), click
  73.0% → 73.6% on the regenerated key `click-py-r3`, no confirmed or suspect row
  moved (`oracle-grading.md` §10.32).

## 0.2.65-beta — 2026-09-20 (a decorator is a call of what it names; ADR-146, C-169 registered and lifted)

**Patch: what the layer draws** — lane A's Python walk. Built as unit
`S-20260920T201508Z-f751`; one defect fixed at its review.

- **What was found.** Looking for Python's closure misses, the probe found nested defs
  are already symbols — and that Hobbes drew **no** call on any decorator line. The walk
  had skipped decorator expressions since the first extraction milestone ("would pollute
  the call graph"), pinned by a test, in no register entry. On click, 1,652 of 2,459
  missed pairs sat on a decorator line: `@click.option(…)` is a direct call of a declared
  function, and `who_calls` on it answered nobody.
- **The rule.** A decorator's expression is walked as any expression is, scoped to the
  **enclosing** definition or the module; a bare `@name` / `@a.b` records the application
  the language defines, at the terminal identifier. Lane A adds sites and nothing else —
  an edge appears only where the index names a repo symbol, so `@pytest.fixture` and an
  untyped `@app.route` draw nothing. What a decorator *returns* is not followed.
- **Measured.** click **2,136 → 3,052 confirmed of 4,595 (46.5% → 66.4%)**, 18 suspect
  before and after (the same rows), poison PASS, 0 rows lost, lane disagreements
  unchanged; flask +166 and attrs +120 rows, all `semantic`, none lost
  (`oracle-grading.md` §10.30). A trace key confirms; it is not a precision.
- **fix(extract): a trailing comment blinded the decorator digest.** `@pytest.fixture  #
  shared` was read as its comment: no fixture, no route, no `parametrize`. One to three
  such lines in each of click, flask, attrs and missy. The digest, the parametrize read
  and the new walk take the first non-comment child.
- `oracle-misses.md` corrected: a named nested `def` is a symbol; the closure misses are
  a nested def reached as a value, lambdas, and `<genexpr>` frames.

## 0.2.64-beta — 2026-09-20 (a module-level `pytestmark`'s `usefixtures` is followed; ADR-139 amended, C-4 narrowed)

**Patch: what the layer draws** — the fixture lookup, pytest only. Built as unit
`S-20260920T193750Z-0bf3`.

- **What was held back.** ADR-139 read a module `pytestmark` and only counted it:
  none of its three keyed repos had one, so no key row had judged it.
- **The key row.** A repo was drawn at random for it, the rule stated first (two
  walks over 71 code-search hits — the first took none: pytest's own suite writes
  the line into strings, GDAL has no binary wheel). **MissyLabs/missy**: 18 test
  files under `pytestmark = pytest.mark.usefixtures("deterministic_public_dns")`.
  Against `pytest --fixtures-per-test -v` in the image (23,480 tests): 0.2.63-beta
  34,505 pairs right, 0 wrong, 1,265 missed — every one the pytestmark's fixture;
  **0.2.64-beta 35,770 right, 0 wrong, 0 missed in the repo.** flask (1,238) and
  attrs (118) unchanged, 0 wrong.
- **The rule.** A plain module-level assignment of one mark or a list/tuple of
  marks; each `usefixtures` string is requested by every **test** in the file, `via:
  usefixtures`, evidence at the mark's line, after the test's own and its classes'
  marks and before autouse — the same walk and the same abstentions. Still counted,
  not followed: a module mark with no string argument. Not read: a `pytestmark` in a
  class body, an annotated or augmented one.
- The `fixtures:` line says "with no string argument" where it said "not followed";
  the denominator statement (`list_blind_spots`, every derived manifest) no longer
  names a module pytestmark. No graded cell moves: no trace key judges a `uses` edge.

## 0.2.63-beta — 2026-09-20 (a call on the value a fixture constructs is a call on that class; ADR-145, C-4 narrowed)

**Patch: what the layer draws** — a Python rule beside the fixture lookup, pytest
only. Built as unit `S-20260920T191040Z-1527`.

- **The silence.** `def test_x(runner): runner.invoke(cli)` drew nothing at
  `invoke`. The index names the *parameter* at `runner` and emits nothing at the
  member — scip-python does not type an unannotated parameter. On click that one
  shape was 381 of 665 missed method pairs.
- **The rule.** Both hops around the silence were already in the graph: the `uses`
  injection (ADR-137) and the `semantic` `calls` edge from the fixture to the class
  at its `return CliRunner()`. Where a fixture's own body is exactly one valued
  `return`/`yield` of `C(…)` on a bare name, the index names `C` a repo class at
  that line, the parameter is never rebound, and `m` is one `def` in `C`'s own body
  (not a property), `p.m(…)` is a `calls` edge to `C.m` — **`syntactic`**, evidence
  `via: fixture-value`. A construction fixes the runtime class exactly; a return
  annotation would not, and is not read. Refused and counted in the `fixtures`
  block (`value_calls.refused`): a rebound parameter, a value that is not a
  construction (`return app`, `return app.test_client()`), no semantic class edge
  (so nothing without lane B), an inherited method, a property, a pair the join
  already drew. The ingest summary's `fixtures:` line says both numbers.
- **Test reach follows the edge** like any `calls` edge: a click test now reaches
  `CliRunner.invoke` and what it calls. Resolution coverage is not moved — the join
  did not resolve the site.
- **Regraded, stored keys, `-poison`** (`oracle-grading.md` §10.29): **click 1,755 →
  2,136 confirmed, recall 38.2% → 46.5%; 382 rows added, 381 confirmed, 1 on a line
  the suite never runs, 0 suspect, no row lost, no tier moved.** cJSON, jsoup,
  memchr, fzf, fmt, args: row-identical. The simulation before the dispatch drew one
  site more — a call inside a nested `def`, which the build rightly refuses. Held
  out, no trace key: flask 11 drawn, read by hand, right; 702 refused.
- `list_blind_spots` and every derived manifest's denominator statement now say
  "unless the fixture constructs it (ADR-145)". C-4 narrowed; nothing new registered.

## 0.2.62-beta — 2026-09-20 (a reference to a shorthand property is a reference to what the shorthand names; ADR-144)

**Patch: what the layer draws** — a rule in the helper's decode, scip-typescript
only. Built as unit `S-20260920T180832Z-12ad`.

- **The silence.** `const { f } = require('./m'); f()` was drawn; `const m =
  require('./m'); m.f()` was not, and neither was `server.restart()` over
  `export default { start, restart }`. At the member token the index names the
  exported literal's *property*, a symbol the helper kept no definition for, so
  the site was filed as an in-repo external reference and the function got no
  reference at all. Found on the cue cell (§10.27): 124 of its misses.
- **The rule.** The index tells a file's literals apart itself, and a shorthand
  is a property definition and a reference to the function at **one exact
  range**. A property with exactly one definition occurrence, at whose range
  exactly one defined symbol is referenced, is an alias of it; a reference to
  the property is filed as a reference to that symbol. Both hops are the
  index's, so the edge is `semantic`. Refused: a value property (`delta:
  alpha`), a method written in the literal, a property defined twice, a
  shorthand naming something the index does not define.
- **Regraded, stored keys, `-poison`** (`oracle-grading.md` §10.28), each cell
  row-identical to the simulation run before the dispatch: **cue 881 → 1,005
  confirmed, recall 54.3% → 61.8%; xmpp.js 676 → 705, 81.2% → 84.6%; 0
  contradicted, no row lost, no tier moved.** Express, github-action, Preact,
  ajv, cheerio, hono, zod: unchanged. cJSON, click, jsoup, memchr, fzf, fmt,
  args: row-identical before and after.
- New `uses` edges sit at a destructuring `require` line, whose pattern names
  the same properties (cue 114) — what an ESM import line already draws.

## 0.2.61-beta — 2026-09-20 (a fifth JavaScript cell, the first of a size graded with its dependency tree; the `javascript` verification row reads five repos)

**Patch: what the layer says** — the `javascript` verification row; nothing the
layer draws moved.

- **Blueturboguy07/cue, drawn at random by a rule stated first**
  (`oracle-grading.md` §10.27): the walk resumed at position 22 with one
  criterion added because the last cell was thin — at least 300 `calls` edges
  and half the declared packages resolved. **881/881 confirmed, 0 contradicted,
  recall 54.3%, poison PASS**, graded with its 276-package tree on both sides
  and again with none. **The two arms' rows are identical by site, target,
  caller and tier, and so is the graph.** The tree moved the key's external
  pairs (1,620 → 5,198), the dependency coverage (0 → 7 of 12) and the poison
  check's unjudged seeds (163 → 18): it sharpens the key, not the graph.
- **Three key pairs differ between the arms, none a Hobbes row:** calls through
  a dependency-typed value (`OpenAI.toFile || require('openai/uploads').toFile`,
  `newInstallId: randomUUID`), where Hobbes draws nothing with the tree or
  without. C-165 as corrected at 0.2.58-beta, now on a cell of a size to say it.
- **The `javascript` verification row** reads 5 repos and ends "two of five
  graded with their dependency tree" (ingest summary, the surface's badge,
  `list_blind_spots`); §3.8's row, C-165 and the README say the same.
- Counted, under C-23: `npm ci` has refused four of the eight lockfile-bearing
  JavaScript candidates the two walks met (the fourth: ERESOLVE).
- Seen and not traced: 176 of the cell's misses are one shape, a member of a
  `module.exports = { … }` literal called through `require`.

## 0.2.60-beta — 2026-09-20 (a yarn-v1 install names `corepack` where it runs; the v1 `yarn.lock` branch had never provisioned on a contained box)

**Patch: a defect fixed in what the layer provisions** — no rule, no ADR, no
register entry. Built as unit `S-20260920T155830Z-d2de`.

- **The defect.** For a v1 `yarn.lock` the install argv named the **host's**
  absolute path to `corepack` (beside the host's resolved `node`), and the
  fetch step ran that argv inside the sandbox image, where the path does not
  exist: `crun: executable file … not found`. `npm ci` never had the problem —
  `npm` is a name. So since lane B moved into the image (ADR-092) every
  yarn-v1 zone on a contained box read "dependencies not provisioned", a
  wording that put our defect on the repo. Seen in the stored ingest logs of
  hono (2 zones) and dagger (its versioned-docs snippet zones).
- **The fix.** Where the fetch runs contained — asked the way
  `containment.run` asks it — the argv names `corepack`, which the image has
  on its PATH, and the host's is not consulted (a host with no corepack still
  provisions). On a host run (no image, or the escape hatch) it is the host's
  path as before, and the same refusal when there is none.
- **Measured on hono** (`97c6fe1`, the unit's code, the cache entry cleared
  first): the tree provisions through the ingest's own path; the three
  extraction errors on `benchmarks/jsx` are gone and none is new;
  `dependency_coverage` reads 9 of 47 resolved where it read 0. **No edge
  moved** — 2,811 symbol edges and 1,729 module edges, identical by
  (from, to, type, tier) — as C-165 says it should be: a call into a package
  is stated at module grain. No graded cell is touched; hono's graded zone is
  `tsconfig.build.json`, not these.

## 0.2.59-beta — 2026-09-20 (a call whose site name is not its definition's is matched at its own column, where both lanes name one definition; ADR-143)

**Patch: what the layer says about an edge it already drew** — a rule added
to the join, every language's. Built as unit `S-20260920T145034Z-061a`.

- **The understatement.** The join pairs a call site with the index's
  resolution by name. At a renamed binding (`import { id as xid }`, `var
  express = require(…)`, Python's `import … as`) and at a `#private` method
  call the names differ, so the site fell to lane A's fallback — a
  `syntactic` call — while the index's proof of the same call became a
  `semantic` `uses` beside it. Measured on seven TS/JS cells: 136 sites, 98
  confirmed, 38 outside the graded zone, **0 contradicted**; about half of
  hono's and four fifths of xmpp.js's lane-A-only call sites.
- **The rule.** Where the by-name match misses, the site has a column, lane
  A's fallback resolves it, and **every** resolution at the site's own column
  names the fallback's definition, the site is matched there: `calls`,
  `semantic`, both lanes, claimed by position. Anything less is what it was.
  It cannot draw an edge that was not drawn; it raises a tier and removes the
  duplicate `uses`. `who_calls`, `hobbes review` and the tail read the same
  match, so such a site is never counted `fallback-resolved`.
- **Regraded, stored keys, `-poison`** (`oracle-grading.md` §10.25): xmpp.js
  38 tiers raised, hono 76, ajv 5, cheerio 8, Express 2, Preact 5, zod 0 —
  **no row added or lost, every confirmed count unchanged, 0 contradicted,
  poison PASS**, each cell row-identical to its simulation. cJSON, click,
  jsoup, memchr, fzf, fmt and args: row-identical before and after, no tier
  moved. What is left of the shape is xmpp.js's 3 namespace-member calls,
  where the index's occurrence is the namespace's and the rule rightly
  declines.

## 0.2.58-beta — 2026-09-20 (a JavaScript cell graded with its dependency tree; C-165 corrected and narrowed)

**Patch: what the layer says** — the `javascript` verification row and a
register entry; nothing the layer draws moved.

- **A fourth JavaScript cell, the first with its dependencies installed.**
  cypress-io/github-action, drawn at random by a rule stated first
  (`oracle-grading.md` §10.24): 154/154 confirmed, 0 contradicted, recall
  89.0%, poison PASS — graded with its 177-package tree on both sides and
  again with none. **The two arms' rows are identical, and so is the
  graph.** The tree moved only the key's external pairs (173 → 413) and the
  dependency-coverage number (0 → 14 of 22). A thin cell (76 `calls` edges)
  and recorded as one.
- **C-165 was worded past what any cell can show, and is corrected.** It
  said Hobbes could not tell you whether an edge from JavaScript into a
  third-party package is right. No such edge is drawn — in JavaScript or
  TypeScript, with a tree or without: a package is stated once, as the
  module-level `imports → ext:<pkg>` edge, and no key grades it. The entry
  now says that, and that one JavaScript cell of four has met its tree.
- **The `javascript` verification row** reads 4 repos and ends "one of four
  graded with its dependency tree" (ingest summary, the surface's badge,
  `list_blind_spots`); §3.8's row and the README say the same.
- Counted, under C-23: `npm ci` refused three of the four lockfile-bearing
  JavaScript repos the draws met (two lockfiles out of sync with their
  manifests, one tarball unpublished from the registry).

## 0.2.57-beta — 2026-09-20 (a TS/JS construction is drawn as a call where the index names the constructor; C-168 narrowed and its claims corrected; ADR-142)

**Patch: what the layer draws** — a rule added on the TS/JS join, and a
constraint narrowed and corrected. Built as unit `S-20260920T012251Z-b444`.

- **C-168's entry was wrong about its own shape, and the measurement says so.**
  It described a `uses` edge at a `new` and counted "ajv 107, zod 110, hono 78,
  xmpp.js 104, Preact 570". Those are each cell's whole `static→class` miss
  class: **Preact's 570 hold no construction at all** (193 `super(…)`, 377 JSX
  tags of a component that declares no constructor), and at a real construction
  the join drew **nothing** — scip-typescript names `<constructor>` at the
  constructor's own line, which starts no symbol, so the reference fell below
  the floor (C-58). The `uses` edge the entry described is at the *import* line.
- **The rule.** Lane A records a `new` expression's callee terminal identifier
  as a construction token — never a `Site`, so it reaches no fallback, veto,
  coverage count or tail class (ADR-132's shape, a language later). The join
  draws a `calls` edge where lane B resolves at **exactly** that token: onto a
  constructor, to the class that declares it; onto anything that is not a class
  — an ES5 `function User(…)` or the variable bound to it — to that definition.
  Semantic tier, both lanes. Lane A facts v6.
- **Onto a class, nothing is drawn.** There the written class declares no
  constructor and the one that runs is a base's, which is what the key names:
  the naive rule — promote today's `uses` edges — drew 3 confirmed and **55
  contradicted** in the probe. The refusals are counted (`ts_named_class` beside
  `ts_drawn` in the graph's `constructions` block), so the cost is a number.
- **Graded (`oracle-grading.md` §10.22 and §10.11, stored keys, `-poison`):**
  xmpp.js 552 → **676/676** (recall 66.4% → **81.2%**), ajv 1,410 → **1,499**
  (63.5% → 67.5%), hono 768 → **833** (55.0% → 59.7%), zod 9,731 → **9,872**
  (45.1% → 45.8%), Express 992 → **998** (65.3% → 65.7%), Preact 2,446 →
  **2,447**, `minijs` 7 → **8/8** (63.6% → 72.7%); cheerio unmoved. **100%
  precision and 0 contradicted on every cell**, poison PASS.
- **C-168 narrowed (partial):** what is left is `super(…)` (211 rows across the
  cells), a JSX tag whose component declares no constructor (Preact 377), a
  class that declares none (ajv 6, hono 50, zod 192 refusals), `new this(…)`,
  `new ns.X()` where the index names the module, and a `new` token the index
  does not resolve at all.

## 0.2.56-beta — 2026-09-19 (a call through a CommonJS re-export is drawn; C-167 narrowed; ADR-141)

**Patch: what the layer draws** — a lane A resolution extended, a
constraint narrowed. Built as unit `S-20260919T210207Z-9133`.

- **Found by tracing C-167.** A package whose root `index.js` is one line,
  `module.exports = require('./lib/express')`, stopped both lanes: the
  TypeScript checker does not alias a `require` call on that right side,
  so lane A's callee ended at the re-exporting file (`nested-decl`), and
  scip-typescript names the call site with that file's document-local
  symbol, which names nothing where it is written. On Express that was
  652 call sites of `express()` — every miss of its largest class.
- **Lane A follows the re-export:** from an `export=` whose one
  declaration is `module.exports = require("<literal>")` (or `exports =
  module.exports = require(…)`), through the literal's module symbol —
  the compiler's module resolution, never a type — to that module's own
  export, at most eight hops. The edge is lane A's fallback, drawn
  `syntactic`: the index did not resolve the call, and the tier says so.
- **Graded (`oracle-grading.md` §10.22, stored keys):** Express 340/340 →
  992/992, recall 22.4% → 65.3%, 0 contradicted, poison PASS; Preact,
  xmpp.js and `minijs` row-identical. No `.ts` file can move (`export =`
  there is not a binary expression), and the five TS cells hold no such
  JavaScript file.
- **C-167 narrowed:** what is left is the tier (these edges stay
  syntactic while scip-typescript writes a local at the site — a
  `Provider` line) and a re-export through anything but a literal
  `require`.

## 0.2.55-beta — 2026-09-19 (JavaScript's verification row names its own three graded repos; C-165 narrowed, C-167 and C-168 registered; ADR-140 step 5)

**Patch: what the layer says** — a language's evidence extended (§3.7
step 4) and two concessions registered. Nothing drawn changes.

- **Graded (`oracle-grading.md` §10.22):** Express (CommonJS) 340/340,
  Preact (ESM, JSDoc, JSX) 2,446/2,446, and xmpp.js (drawn at random)
  552/552 — 100% precision on each, poison check PASS; recall 22.4%,
  28.6% and 66.4%. The TS oracle's `--no-tsconfig` built the same program
  the ingest does; Preact's first pass exposed two oracle defects (H-34,
  H-35), fixed before its number was quoted.
- **The row.** `javascript` in `verification.py` and §3.8 names the three
  repos, "all three graded without a dependency tree": no cell had its
  dependencies installed, which is what C-165 now says.
- **C-167 (partial):** a function reached through a CommonJS re-export of
  `module.exports` draws no edge — Express's `express()`, 652 of its
  1,180 misses; not yet traced.
- **C-168 (partial):** `new F()` is drawn `uses`, not `calls`, in
  TypeScript and JavaScript, and `who_calls` words it as no call site.

## 0.2.54-beta — 2026-09-19 (a `jsconfig.json` nothing reads is said, once per file; C-166)

**Patch: what the layer says** — a concession registered (C-166,
surfaced). Nothing drawn changes.

- **Found preparing ADR-140's JavaScript cells.** Both lanes key a zone
  on `tsconfig.json` alone, so a `jsconfig.json`'s options — `paths`
  aliases, `jsx`, `lib`, `target` — are never read. Measured on Preact
  with the key alone: 120 of 22,804 call sites resolve differently under
  its jsconfig than under the options the ingest generates.
- **Said where it is met.** The TS/JS helper records one degradation per
  `jsconfig.json` that governs a discovered file and has no
  `tsconfig.json` beside it (stage `jsconfig-ignored`, naming the
  `tsconfig.json` or the default options its files ran under): a
  `WARNING:` line in the ingest summary and a `degraded:` line in
  `list_blind_spots`. §3.8's JavaScript row states it.

## 0.2.53-beta — 2026-09-19 (JavaScript claims no graded repo until it has one; §3.8 splits TypeScript and JavaScript; ADR-140)

**Patch: what the layer says** — a concession registered (C-165,
surfaced). Nothing drawn changes.

- **Found by measuring the claim.** `verification.py` pinned the
  `javascript` row as a copy of TypeScript's ("4 repos, multi-repo"),
  so every JavaScript ingest vouched for itself on the TS/JS row's
  cells. Those cells are TypeScript programs: on the five graded ones
  (kbet, ajv, cheerio, zod, hono) none of 15,167 confirmed edges
  touches a JavaScript file, and the 27 drawn edges that do are all
  `silent`, outside the program the zone's `tsc` loaded.
- **The row.** `javascript` is 0 repos, depth `unverified`, and a zero
  row that names its reason prints it: the ingest summary's
  `javascript: not verified on any repo — …`, the surface's
  `javascript · 0 repos` badge, and `list_blind_spots`' note.
  TypeScript's row is unchanged.
- **§3.8 splits** its TS/JS row into TypeScript and JavaScript (Max),
  and the test that pins the two tables together maps each label to
  one language.
- **Next (ADR-140, steps 3–5):** the oracle grades a zone with no
  tsconfig; two or three JavaScript repos of different shapes are
  pre-registered and graded; the row names them.

## 0.2.52-beta — 2026-09-19 (a `usefixtures` string and an `autouse` fixture's name are looked up as a parameter is; autouse reach is said once; ADR-139)

**Patch: what the layer draws and says** — a constraint's fix (C-4,
narrowed again; still surfaced).

- **Found by measuring C-4's remainder, and by reading the key.**
  `pytest --fixtures-per-test` prints no fixture named `_…` without
  `-v`; ADR-137's "1,004 of 1,004" was of the pairs that key printed. On
  the `-v` key nothing it drew was wrong, and it missed 3,962 pairs on
  this repo, 734 on flask and 14 on attrs — every one an `autouse`
  fixture or a `usefixtures` mark.
- **The rule.** A `usefixtures` string (on the test, or on its class)
  and the name of every fixture defined `autouse=True` in a scope of the
  test's chain go through the lookup a parameter goes through, with the
  same abstentions, and are drawn as the same syntactic `uses` edge;
  each evidence row says `via: parameter | usefixtures | autouse`. The
  Python walk keeps which decorator keywords are the literal `True`.
  Counted, not followed: a module-level `pytestmark` (no key row has
  judged one) and an `autouse=` that is not a literal.
- **Autouse reach is kept apart and said once.** `tests.json` records
  `through_autouse` (module → the autouse fixtures that got the test
  there) for modules a test reaches no other way. `tests_guarding` lists
  the tests that reach a target by a call or a fixture they name, and
  says the rest in one line with the fixtures; `hobbes review` lists new
  code reached only that way on its own line, guarded and labelled.
- **Checked against pytest's own list (`-v`), before the merge:** this
  repo 4,971 pairs right, flask 1,238, attrs 118 (both held out, in the
  image, no network); **0 missed, 0 wrong**, and the built edges are the
  probe's, edge for edge. This repo's ingest: 5,072 injections, 4,058
  by autouse; `tests_guarding hobbes.extract.staging` lists 441 tests
  and says 1,588 once. No trace key judges a `uses` edge, so no graded
  number moves; none was re-run.
- The denominator statement names what is left of C-4: the value a
  fixture returns, and a fixture the lookup cannot place.
- Unit `6f84` (68 turns, $5.70), gate right-clear, verify pass; the
  proxy and `review.py` are the developer's commit.

## 0.2.51-beta — 2026-09-19 (the denominator statement names what is left of C-4, not all fixture-injected reach)

**Patch: what the layer says** — no edge, node or count moves.

- **Found by the top-level doc review.** `list_blind_spots` and every
  derived context manifest opened with "fixture-injected test reach
  (C-4)" among the things never detected. Since 0.2.49-beta (ADR-137) a
  fixture a parameter names *is* drawn and test reach follows it; the
  statement under-claimed, and the register recorded that it did.
- **The wording now:** "test reach through a pytest fixture no parameter
  names (autouse, usefixtures) or through the value a fixture returns
  (C-4)" — C-4's own remainder. The Go and Python copies
  (`knowledge.go`, `derive/manifests.py`) say the same thing.
- C-4's *You find out* line updated; no entry added, the tally unmoved.

## 0.2.50-beta — 2026-09-19 (a `.h` is claimed by C++ through the headers C++ has claimed, and the C walk knows the files C++ owns; ADR-138)

**Patch: what the layer draws and says** — a constraint's fix (C-142,
narrowed; still partial). C-133 measured and unmoved.

- **Found by measuring the `-I` item, not by a cell.** Reading the
  compile database's include path at lane A would place nothing on any
  graded cell and 116 includes of 95,510 on ScummVM; it is not built.
  Beside it: 629 of ScummVM's `.h` were read by the **C** grammar in a
  repo with two `.c` files — of the 624 a probe read, 535 spell `class`,
  `namespace` or `template` — because ADR-113 §1 asks for a C++ *source* includer
  and a header reached only through a header has none.
- **The rule.** The claim grows to a fixed point: a `.h` that a claimed
  header includes, and that no `.c` source includes, is claimed. The C
  side stays a `.c` source's own includes — following headers there was
  measured and would have turned 10 C++ headers into C. The
  `cpp-headers` record says how many were claimed through a header, and
  reads exactly as before where none was.
- **The C walk knows what C++ owns.** An include in a C-read file that
  lands on a C++-owned file draws its `imports` edge (to the C++ walk's
  module id) instead of a "matched no repo file" record; a C++-owned
  header can also make a suffix match ambiguous, as the compiler would
  see it.
- **Checked** (ScummVM, cold 547 s): 9,468 → 9,824 `.h` read as C++
  (356 through a header), 629 → 273 as C; unmatched includes 395 → 43,
  none of the named ones a file at the repo root (122 of 277 were);
  ambiguous 167 → 170; +1,413 lane A symbols, +356 `imports` edges,
  1,022 fewer definitions minted from the index. fmt, args, cJSON and
  sqlite-vector identical in every row, symbol and edge; click's export
  row-identical. The probe predicted 9,859 claimed: 35 short, toward
  claiming less.

## 0.2.49-beta — 2026-09-19 (a pytest fixture injection is a `uses` edge, and test reach follows it; ADR-137)

**Patch: what the layer draws and says** — a constraint's fix (C-4,
partial → surfaced, its remainder named).

- **The rule.** pytest's lookup of a parameter name is all syntax: the
  requester's class chain, its file (a name imported into it counts as
  the file's), then `conftest.py` in its directory and each one above.
  Lane A's Python walk records a definition's undefaulted parameters and
  its `parametrize` names; `extract/fixtures.py` walks the order and
  draws test→fixture and fixture→fixture as a `uses` edge, tier
  `syntactic`, lane `tree-sitter`, evidence at the parameter. **Never a
  `calls` edge**: the test wrote no call.
- **Reach follows it, and says so.** `tests.json`'s pytest records gain
  `through_fixtures`, the modules a test reaches only by way of a
  fixture. `tests_guarding` marks such a line "only through a pytest
  fixture (ADR-137)"; `hobbes review` lists new code guarded only that
  way under its own heading (guarded, not a reason for attention;
  `coverage.fixture_only` in `--json`). A fixture-heavy repo's review
  can read fewer "new code no test reaches" lines than before.
- **What it will not draw,** counted in `graph.json`'s `fixtures` block
  and the ingest summary: a name no scope in the repo defines
  (`tmp_path`, a plugin's), a name defined twice at one scope, a
  definition whose `parametrize` argument it cannot read, and a name
  found past the class chain from inside a class that names a base
  class. Not followed: `usefixtures` marks (counted) and `autouse`
  fixtures (not counted).
- **Keyed by pytest itself** (`--fixtures-per-test`, collection only):
  this repo 1,004 test–fixture pairs, 1,004 right, 0 wrong, 0 missed,
  as pre-registered; held out and collected in the image, flask 504
  right and attrs 104 right, 0 wrong on either, every miss an `autouse`
  fixture (370) or a `usefixtures` mark (8). On this repo 1,008 edges
  into 82 fixtures. No trace key judges the edge (a fixture's caller is
  pytest's own frame): no graded number moves.

## 0.2.48-beta — 2026-09-18 (the mint reads a definition row at a line ADR-135's R1 vacated, even in a file that parsed clean; ADR-136)

**Patch: what the layer draws and says** — a constraint's fix (C-164,
narrowed; still partial).

- **Found by a scale read, not a cell.** ScummVM's first ingest with
  ADR-135 (19,948 C++ files; cold 9 min 04 s, warm 2 min 20 s,
  byte-identical): R1 removed 401 lane A symbols, 27 names, each read
  against the source and none the function's — generator macros
  (`DECLARE_COMMAND_OPCODE(location) { … }` 59 times), object-like
  renames (`#define yyparse HYPNO_ARC_parse`), one member initialiser.
  But 260 of them are in 19 files that parsed *clean* — such a macro
  reads as a function definition with no ERROR node — and there the
  mint's `clean-file` refusal kept out the true definition the index
  holds on the same line. Wrong before 0.2.47-beta, absent after it.
- **The rule.** `contradicted` hands the mint the `(file, line)` pairs
  R1 vacated; a definition row at one is read even in a clean file.
  Every other refusal still runs, the extent and the re-homing are
  ADR-134's, and the rest of a clean file's rows stay refused.
  `graph.json`'s `minted.vacated` counts these symbols and their files
  apart (`minted.files` still means files lane A parsed with errors),
  and the ingest summary's line gives them a clause of their own.
- **Checked, not graded** (`oracle-grading.md` §10.21): fmt, args, cJSON
  and sqlite-vector row-identical with `vacated` at zero (fmt's 18
  removals are all in lossy files); click identical. ScummVM: 260
  symbols in 19 files as predicted, 255 with a brace extent, 2,774 more
  facts re-homed, 1,639 symbol edges added; the 289 that left are the
  same evidence under a new `from` (no evidence row gone); a 30-row
  sample read against the source, all right.
- The `lane-a-symbol-near` refusal was read row by row the same day (19
  rows on four cells) and stands: no row is a definition lane A lost.

## 0.2.47-beta — 2026-09-18 (a lane A C++ symbol the index contradicts is refused, or its extent re-read from the file's braces; ADR-135)

**Patch: what the layer draws, refuses and says** — a constraint's fix
(C-164, unsurfaced → partial).

- **Measured first, key-free.** C-164's rows are wrong, not missing:
  where tree-sitter-cpp recovers from a macro it cannot read, lane A
  keeps a function named for the wrong token, or one whose extent runs
  over the definitions after it. On the four cells with an index: 18
  misnamed symbols, all on fmt (13 a macro's name —
  `GTEST_LOCK_EXCLUDED_`, `FMT_CATCH` — and 5 a constructor's first
  member initialiser's), 2 swallowing extents, none on args, cJSON or
  sqlite-vector. The index's definition row at the line does not
  separate them (332 of fmt's lane A functions have none: inactive
  code, parsed right), nor does the name being a macro's (cJSON's
  `internal_malloc` is a function in one `#if` arm). A lane B
  **reference at exactly the symbol's own name token** does: 18 of 18 by
  hand read, none flagged among 3,769 right symbols. Read loosely it
  flags right ones (`Base::KickOut` beside `Options::KickOut`).
- **The rule.** Lane A records a C++ function's or method's name column
  (`name_col`; the lane A cache is `lanea-cpp v5` and re-parses once).
  After the join and before the mint: **R1** removes a symbol whose name
  token the index reads as a reference, spelled as the symbol, to a
  `macro` or to a `term` of that name; its facts take the module as
  their scope, and the mint and ADR-134's re-homing name the true
  definition where the index has one. **R2** re-reads from the file's
  braces the extent of a symbol holding a file- or class-scope function
  definition row. Counted in `graph.json`'s `lane_a_contradicted`
  (absent where nothing fired) and on one ingest summary line. No index,
  no rule (P6).
- **Checked, not graded (`oracle-grading.md` §10.20).** Every graded
  number ±0 and every export row-identical on fmt, args, cJSON and
  sqlite-vector; click identical. fmt: 18 refused (13 + 5), 1 extent
  re-read (`gtest-extra-test.cc:201`, 292 → 210), **wrong-caller rows
  105 → 32, 18 now right and 55 lost, no row that was right moved**;
  the 32 left are the driver's naming grain (25 in-class `friend`
  definitions, 5 a nested class, 2 others). Six of ADR-134's
  `holds-a-definition` extents unblock (19 → 13) and two true
  definitions are minted on lines a refused symbol vacated. One test's
  reach returns to its own body's (three borrowed symbols gone). The
  simulation's agree and lost counts each missed by one row beyond
  their ± 2 (it did not model the two new mints), recorded.
- Unit `c2cc` (68 turns, $6.61 on the subscription), gate right-clear,
  verify pass; the brief's premises were read in the tree before it was
  written, and the first real ingest matched. 1,964 pytest, `lane_b` 10
  of 10 on the host.

## 0.2.46-beta — 2026-09-18 (a lost C++ definition's extent is read from the file's braces, and what is written inside it is drawn from it; ADR-134)

**Patch: what the layer draws and says** — a constraint's fix (C-145,
narrowed again; no entry added).

- **Measured first, nothing drawn.** ADR-129's minted symbol was a
  target, never a scope, so a call written inside a lost definition kept
  the module as its caller: 1,436 of fmt's 8,123 call rows (17.7%). No
  grade saw it — every C and C++ key judges `(site, target)` and never a
  caller — so it was read off the key's own caller names. scip-clang's
  index carries no extent. A brace match on the file's text was
  simulated: 1,303 rows moved, none wrong. Before the build the third
  refusal was run too and **fired 19 times on fmt**: 13 macro-generated
  methods (`GTEST_REPEATER_METHOD_(OnTestStart, TestInfo)` has no brace
  of its own, and the match borrowed the next function's body — a wrong
  node no moved row would have shown), 6 true bodies holding a symbol
  lane A named after a macro (C-164).
- **The rule.** A minted function or method gets `end_line` from the
  first `{` at parenthesis depth 0 matched to its `}`, on the file's text
  with comments, strings, raw strings and character literals blanked,
  and says `extent: "braces"`. Refused, counted in `graph.json`'s
  `minted.extents` and on the ingest summary: a preprocessor conditional
  in the body, a match that runs off the file, any other function or
  method starting inside it. A minted type stays a line. A `calls` or
  `uses` fact written inside a read extent is re-homed to it when its
  scope is the module or a lane A symbol that starts before the extent.
  `who_calls` says which kind of minted symbol it is showing.
- **Checked, not graded (`oracle-grading.md` §10.19).** Every graded
  number ±0 and every export row-identical on fmt, args, cJSON and
  sqlite-vector; click identical. fmt: 1,346 extents (34 + 19 refused),
  **1,290 call rows re-homed; the caller agrees with clang's on 6,392 →
  7,610 rows, lost 1,436 → 188, no row that was right moved**; the 30
  rows that land in the probe's wrong class are one function in two
  spellings. args: lost 15 → 0. fmt's test reach 3,183 → 6,131 pairs,
  no test lost a symbol. One prediction's arithmetic missed (lost 188,
  not 165), recorded.
- Unit `368a` (59 turns, $5.88 on the subscription), gate right-clear,
  verify pass; then the developer's fix, because the brief was wrong
  about what scope a file-level C++ site carries (the module's id, not
  none) — the first real ingest moved 2 rows of 16. 1,942 pytest,
  `lane_b` 10 of 10 on the host.

## 0.2.45-beta — 2026-09-18 (the join claims a lane B resolution by position, not by name; ADR-133)

**Patch: what the layer draws** — a constraint's fix (C-163, registered
and lifted in the same commit; C-162 narrowed).

- **Measured first, nothing drawn.** A matched call or import site
  claimed its resolution by `(file, line, name)`, which hid every other
  resolution of that name on the line. On the 25 graded clones that was
  7,308 resolutions: 1,158 alternates at the matched occurrence's own
  column, and the rest true facts at another — a Java declaration's type
  beside its `new`, a TS interface beside the function of its name, a Go
  return type beside a method call, and the 19 fmt constructions ADR-132
  predicted and did not get. It was in no register entry.
- **The rule.** The claim's key is the matched resolution's position,
  `(file, line, name, col)`. A resolution at another column goes through
  the unclaimed loop as any other: the operator rule (ADR-131), the
  construction rule (ADR-132), else a `uses` edge. One at the matched
  occurrence's own column stays hidden (ADR-104's abstention and an
  override's alternate); a site lane A recorded no column for keeps the
  by-name claim, since which resolution it matched is not known.
- **Graded, stored keys, 44 cells, before and after on the same clones
  (`oracle-grading.md` §10.18; P108–P113 all met):** fmt **6,993 → 7,012
  confirmed, 0 contradicted**, strict 99.62%, recall 30.3% → 30.4%;
  every other cell's export row-identical and every graded number ±0.
  In the graphs: **1,785 `uses` and 11 `calls` symbol edges added, none
  removed**; two module edges added, both read by hand and true
  (quic-go's `quic.StreamID` return type, dagger's `introspection.Query`
  constant). No key judges a `uses` edge; the ADR says so.
- Unit `3569` (26 turns, $1.78 on the subscription), gate right-clear,
  verify pass; 1,910 pytest and `lane_b` 9 of 9 on the host.

## 0.2.44-beta — 2026-09-17 (a C++ construction is a call where the index names the constructor at the token, outside a template; ADR-132)

**Patch: what the layer draws** — a constraint's fix (C-162, registered
and narrowed in the same commit).

- **Measured first, nothing drawn.** fmt's "8,117 missed constructions"
  is not one class: 80% sit at a macro invocation's name (gtest's
  `Message` and `AssertHelper` at `EXPECT_EQ` — the macro class, C-131),
  7% are gtest's `new TestClass`, 10% have no lane B reference at all
  (a dependent type's construction is not indexed), and 152 name the
  constructor at a real token outside a template. args, held out: no
  macros, 383 of 889 drawable — 324 at the `{` of a braced argument —
  and 484 implicit conversions the index says nothing about. Two of five
  predictions missed there, recorded as misses.
- **The rule.** Lane A records construction *tokens* (C++ only, packed,
  never sites): the declared name of `T x(args)` / `T x{…}` / `T x;`, a
  member initialiser's name, the `{` of a braced argument or return, the
  `=` of a defaulted parameter, the type's start in `T{…}` and
  `new T(…)`. The join draws a semantic `calls` edge where a lane B
  reference **onto a constructor** sits at exactly that token, outside a
  template and outside an unevaluated operand. Inside a template the
  reference stays the `uses` edge it was, and is counted
  (`graph.json`'s `constructions` block; one line in the ingest summary).
  Lane A's C++ cache format moves (`lanea-cpp v4`).
- **The grades, stored keys:** args, held out, **2,198 → 2,567 confirmed,
  0 contradicted, recall 62.5% → 72.9%**, the built export the probe's
  row for row. fmt **6,901 → 6,993 confirmed, 0 contradicted, recall
  30.1% → 30.3%, strict 99.61% → 99.62%**; the 24 rows the key could not
  judge were read by hand before the build, all right. cJSON and
  sqlite-vector identical.
- **Recorded miss:** P102's count (fmt 6,993 where 7,012 ± 3 was
  predicted). 19 rows the simulation drew are not drawn: the type is
  named through a using-declaration, and lane A's existing construct
  site claims the constructor's reference by name and lands below the
  floor. It draws less, not wrong; registered in C-162 as its own item.
- **One wrong class found on fmt's read and excluded before args ran:** a
  constructor's own in-class declaration under a macro-broken class head
  looked like a local; a declaration under a label records nothing.
- Unit `4834` (84 turns, $8.57), gate clear, verify pass.

## 0.2.43-beta — 2026-09-17 (a dependent C++ operator's reference inside a template draws nothing, not a `uses` either; ADR-131 amended)

**Patch: what the layer draws** — a constraint's fix (C-153 narrowed a
third time). Max's call on the item 0.2.42-beta left open: route a.

- **What was wrong.** A lane B reference no call site claims is a `uses`
  edge. At an operator inside a template that reference is scip-clang's
  single by-name candidate, and about 100 of fmt's 437 named the wrong
  declaration. No key grades `uses`, so nothing would ever say so.
- **The rule.** Such a reference — named `operator…`, at exactly an
  operator token lane A recorded, the token inside a template — draws no
  fact at all. It is still counted (`operators.in_template`, now the
  number withheld) and the ingest line says *withheld, neither a call nor
  a uses*. Every other unclaimed reference is the `uses` edge it was.
- **Measured first, built equal to the probe** (`oracle-grading.md`
  §10.16, P98–P101 met): fmt −156 `uses` symbol edges, args −24, none
  added; all four graded exports identical row for row (fmt 6,901/6,901,
  strict 99.61%; args 2,198/2,198). **One module edge went on each cell
  and both were wrong:** `test/scan.h → include/fmt/format.h` stood only
  on integer `n * 10` read as `fp`'s `operator*`; `args.hxx →
  test/test_common.hxx` — a library header depending on its own test
  header — only on `ss >> destination`.
- **The price, owned:** the right candidates go with the wrong ones; the
  key confirms 175 of fmt's in-template rows as calls, and those were
  true dependencies.
- Unit `4033` (36 turns, $1.78), gate clear, verify pass.

## 0.2.42-beta — 2026-09-17 (a C++ operator applied by symbol is a call where the index names it at the token, outside a template; ADR-131)

**Patch: what the layer draws** — a constraint's fix (C-146 narrowed).

- **Measured first, nothing drawn.** The open question was whether
  scip-clang emits an occurrence at an operator token. It does: 4,017 on
  fmt. 3,011 of them sit at a macro invocation's name (gtest's
  `operator=` inside `EXPECT_EQ`) and are the macro class, not this one.
  At the token, a naive rule read 99.9% by the key and was wrong
  underneath it: of the 148 rows the key could not judge, about 100 read
  wrong by hand — `wday == 0` drawn to `basic_fp`'s `operator==`,
  scip-clang's single by-name candidate at a dependent expression
  (C-153), at the same arity, so R-arity cannot see it. **Every one of
  those rows was inside a template.** args was held out, its predictions
  written before its probe ran; one of the five missed, on the count
  (`oracle-grading.md` §10.15).
- **The rule.** Lane A's C++ walk records every operator *token* —
  binary, unary, pointer, update, assignment, subscript, `->` — with its
  line, column, spelling and whether it sits under a
  `template_declaration`, packed one integer each and never as a call
  site: a built-in operator is no call, so a token is never counted,
  guessed at, vetoed or tailed. The join draws a semantic `calls` edge
  where lane B's reference named `operator…` sits at **exactly** that
  position with that spelling, outside a template and outside an
  unevaluated operand; its caller is the enclosing symbol. Inside a
  template the reference stays the `uses` edge it was. With no lane B
  nothing changes (P6). `graph.json` gains an `operators` block (schema
  v4, additive) and the ingest summary one line: tokens drawn,
  references inside a template left as `uses`. Lane A's C++ file cache
  format moved (`lanea-cpp v3`): its first ingest misses.
- **Graded against the stored keys:** fmt **6,510 → 6,901 confirmed call
  edges at 0 contradicted**, recall 29.1% → 30.1%, strict precision
  99.59% → 99.61% (the same 27 unjudged rows, none added). args 2,062 →
  2,198 at 0 contradicted, recall 58.6% → 62.5%. cJSON and sqlite-vector
  identical, row for row. The built export is the measured one minus a
  single row under an ERROR node.
- **The price, counted:** 437 operator references inside templates on
  fmt are not drawn as calls (175 of them rows the key would confirm);
  40 on args.
- **Found and not fixed:** those same wrong candidates stand in the
  graph as `uses` edges, as they did before this version — no key grades
  `uses`. Named in C-153; whether to withhold them is Max's call.
- Built through the harness: `d1b9` ($8.63, gate right-clear, verify
  pass), merged not squashed.

## 0.2.41-beta — 2026-09-17 (a C/C++ definition lane A's parse lost is read from the index; R-arity; ADR-129, ADR-130)

**Patch: what the layer draws and refuses** — a constraint's fix, and
structural: for the first time a graph symbol can be declared by lane B.

- **Measured first, nothing drawn.** C++ had the lowest recall of any
  language (fmt 14.5%). C-145 named the largest cause: tree-sitter-cpp
  cannot parse a declaration spelled through macros, lane A keeps no
  symbol, and every call scip-clang resolved there fell `below-floor`. A
  scratch probe graded the rule's export against clang's key before any
  of it was built; a naive rule read 98.2%, and each refusal below
  removed measured wrong edges. args was held out, its predictions
  written before its probe ran (`oracle-grading.md` §10.13).
- **The mint (`extract/minted.py`).** In a C or C++ file whose lane A
  parse had ERROR nodes, lane B's own definition row becomes the symbol
  (`declared_by: "scip"`), after the join and before the projection.
  Only a function, method or type; only with a body the file's text
  shows; never a definition inside a function, an unnamed struct's
  invented name, a line with several monikers, a name lane A has within
  three lines, or a type lane A already names elsewhere. **A target, not
  a scope:** calls written inside a lost definition keep their caller.
  Nothing lane A decides sees a minted symbol; with no lane B nothing is
  minted (P6). `graph.json` gains a `minted` block (schema v4, additive).
- **R-arity (ADR-130).** Reading the rows the mint left unjudged found 35
  wrong edges it would have surfaced: `copy<Char>(begin, end, out)` drawn
  to the two-parameter `copy` (scip-clang's one candidate at a dependent
  call, C-153). A C++ call lane B answered, written with **more
  arguments than the target's declarator can take**, now draws nothing
  and is tailed `arity-mismatch`. Only "too many" (defaults live on
  declarations elsewhere), only where both counts were read. It also
  removes 5 wrong edges that were standing. Lane A's C++ file cache
  format moved (`lanea-cpp v2`): its first ingest misses.
- **Graded against the stored keys:** fmt **3,269 → 6,510 confirmed call
  edges at 0 contradicted, recall 14.5% → 29.1%**, strict precision
  99.73% → 99.59% (27 rows the key cannot judge; 18 of the 19 new ones
  read by hand as right, one as a same-arity wrong candidate, named in
  C-153). args 1,995 → 2,062 at 0 contradicted, recall 56.4% → 58.6%.
  cJSON and sqlite-vector do not move. R-arity withheld exactly the 40
  rows named before it was built, none of them confirmed.
- **Two predictions missed and are recorded as misses** (P79, P80): the
  probe counted only lost definitions some call targets, the rule mints
  every one, and the first regrade found unnamed structs and
  already-named types among them on the C cells — two refusals added
  before the version moved.
- **Where a user meets it:** the ingest summary prints the symbols read
  from the index and every refusal by reason; `who_calls` says which
  symbols lane B declared and that their own calls are not scoped;
  `list_blind_spots` explains `arity-mismatch`. **C-145 and C-153
  narrowed**; no entry added.
- Dispatched as `S-20260917T172122Z-77da` (the mint; two refusals added
  by the developer after the regrade), `S-20260917T174302Z-4048`
  (R-arity) and `S-20260917T180521Z-b597` (the surfaces), all merged
  no-ff.

## 0.2.40-beta — 2026-09-17 (C++ lane A exact-faster, then cached per file; the trusted stores read-only in every container; ADR-128)

**Patch: what the layer says, and where it lets repo code write.** The
artifacts are unchanged: every change below was checked byte for byte on
ScummVM's lane A extraction (217 MB of JSON, `cmp`).

- **Measured first.** Lane A passes 2 s on no timed repo but ScummVM,
  where C++ took 242 s of 258 s. The time was Python around the parse,
  not tree-sitter (about 21 s).
- **Three exact changes** (C and C++): `csource._walk` is an explicit
  stack in the same pre-order (the recursive generator made 2.06 billion
  calls); the include suffix step goes through a `HeaderIndex` by
  basename instead of an `endswith` scan of every header per include;
  the string-test scan is skipped when no macro name is in the file's
  bytes. ScummVM C++ lane A 242 s → 135 s.
- **A per-file cache for C++ lane A.** `cppsource._parse_file`'s result
  is kept under `<cache>/lanea/cpp/`, keyed on the extraction code's
  bytes, the grammar's installed version, the path and the file's bytes;
  JSON with tuples and sets tagged, never pickle; every record checked to
  decode back equal before it is kept. ScummVM: 144 s cold, **21.7 s
  warm** (lane A 261 s → 39.5 s), 318 MB. The summary prints hits and
  misses; `HOBBES_LANEA_CACHE=0` parses afresh. **C-160 registered
  (surfaced).**
- **The index and lane A stores ride read-only in every contained step.**
  The whole cache root was mounted read-write, so repo code in a step
  that executes it could write lane B's index store (ADR-122), which a
  later ingest reads back as an answer. The tool caches and the stage
  stay writable by design; the ingest now prints a `NOTE:` whenever repo
  code ran. **C-161 registered (surfaced).** The index cache's key
  includes the mounts, so its first ingest after this version misses.
- Dispatched as `S-20260917T153835Z-9943` (containment; two tests
  outside its partition fixed by the developer), `S-20260917T154724Z-1ef9`
  (the exact changes) and `S-20260917T155937Z-6956` (the cache), all
  merged no-ff.

## 0.2.39-beta — 2026-09-17 (one ingest of a repo at a time; ADR-127)

**Patch: what the layer refuses.** The graph is unchanged.

- A second `hobbes ingest` of a repo whose ingest is running is refused
  before it stages anything: `hobbes ingest: another hobbes ingest of
  <root> is running (pid N)`, exit 1 (`IngestBusy`). Two ingests of one
  repo used to share every lane B stage path and delete each other's
  trees, so units failed with "wrote no facts file" and the graph was
  written anyway (found by use, 2026-09-17).
- The guard is an exclusive `flock` on `.hobbes/derived/.ingest.lock`,
  taken first in `ingest()`, so `hobbes up` and the bench's arm get it
  too. The kernel drops it with the process; nothing goes stale.
- `graph.json`, `tests.json` and `interfaces.json` are each written to a
  temporary beside them and renamed over, with the mode a plain write
  gave; a reader sees the old file or the new one. The bytes are
  unchanged.
- **C-159 registered (surfaced):** a build before this one takes no
  lock, and a filesystem where `flock` fails runs unlocked, with a
  warning naming C-159.
- Dispatched as `S-20260917T142335Z-d238` (merged no-ff); the artifact
  mode kept by the developer on top.

## 0.2.38-beta — 2026-09-17 (C-153's region is marked where a user meets it; ADR-125 §4)

**Patch: what the layer says.** The edges are unchanged.

- `who_calls` marks a caller line whose semantic C++ `calls` edge starts
  in a **template pattern**: a function template, including an out-of-line
  member under a non-empty `template <…>`, or a member of a class template
  or partial specialisation, at any depth. The note: *"C-153: from a C++
  template pattern — scip-clang's one answer there can name another
  specialisation's declaration"*. An explicit full specialisation is not a
  pattern.
- `graph.json` gains `cpp_template_patterns` (the pattern symbols that call
  something semantically; present when the C++ layer ran), and the ingest
  writes one `cpp-template-sites` degradation record with the edge count,
  which `list_blind_spots` shows.
- It marks the region, not the wrong edges. On fmt that is 596 of 2,811
  semantic call edges, including both `format_as` rows R-qual leaves.
  **C-153: unsurfaced → partial.** Not marked: a pattern whose header a
  macro parse lost (C-145), and a method of a class nested in a class body
  (no lane A symbol).
- Dispatched as `S-20260917T134335Z-b0ed` (merged no-ff).

## 0.2.37-beta — 2026-09-17 (a C++ call the written specialisation contradicts draws nothing; ADR-125)

**Patch: what the layer draws.** A C++ call written through one
specialisation (`test_format<20>::format(..)`, `formatter<int>::format(..)`)
that scip-clang resolved into a member of a *different* explicit full
specialisation (`template <> struct test_format<0>`) is contradicted by
the source text, so no edge is drawn.

- The rule fires only when all four hold: the call's immediate qualifier
  carries template arguments; the answer is lane B's; the resolved owner
  is declared `template <>`; the base names match and the argument lists
  (whitespace removed) differ. A primary template or a partial
  specialisation never fires it. A `template <>` a macro parse lost
  (C-145) is read from the ERROR node's exact tokens.
- The site is counted in a new tail class, `qualifier-mismatch` (C++
  only), which `list_blind_spots` and the review gate know.
- **Measured before building** (`oracle-grading.md` §10.11): on fmt the
  rule removes 8 wrong edges and 0 right ones; on args, nothing. At the
  build fmt reads **100%** (3,269/3,269), strict 99.73%; recall is
  unchanged to the pair; args is identical.
- **C-153 narrowed**, still unsurfaced for what the rule does not reach
  (two `format_as` rows on fmt); the rule's residuals (an alias, default
  argument or expression spelled differently) are in the entry.
- Dispatched as `S-20260917T132019Z-145d` (merged no-ff); the lost-header
  recovery is the developer's (`9daffdc`, §10.11 P69).

## 0.2.36-beta — 2026-09-17 (`hobbes lanes` names a registered disagreement and exits 3; ADR-123)

**Patch: what the layer says.** The graph is unchanged; the lane-agreement
report and the command's exit status are not.

- Every site disagreement carries a `shape` when a registered limit
  explains it by a rule the report checks: `same-line-pair` (C-70) when
  the line holds two or more sites of that name and lane A's one guess is
  lane B's answer at another of them; `cpp-withheld` (C-152) when the file
  is a C++ file lane B compiled, where lane A's guess draws nothing. A row
  neither rule explains has none. Nothing is removed and `sites_compared`
  does not move.
- `hobbes lanes` exits **3** when every disagreement is shaped, 1 when any
  is not (or a graph predates the shapes), 0 and 2 as before; it prints
  the split per shape, the unexplained rows first, and — where C++ rows
  exist — lane A's C++ disagreement rate beside the number of the same
  guesses drawn in C++ files lane B did not index. `scripts/ci-graph.sh`
  passes on 3.
- **C-152 amended:** in a compiled C++ file the check no longer fails on a
  row where lane B is the wrong lane; listed and counted, not failed on.
  **C-70's open question settled** by the rule above.
- Dispatched as `S-20260917T130613Z-4338` (merged no-ff); the developer's
  follow-up counts every C++ row in the rate and leaves vetoed sites
  (ADR-111) out of the drawn count.

## 0.2.35-beta — 2026-09-16 (lane B reads an unchanged unit from its index cache; ADR-122)

**Patch: what the layer says, and how fast it says it.** The graph is
unchanged: an ingest that reads from the cache writes the bytes an
ingest that indexed would have written (sha256-compared on this repo).

- Every lane B indexing unit — six languages, one hook in `run_helper`
  — keeps the helper's facts file under `~/.hobbes/cache/index/` by the
  hash of everything the container can see: the helper's source and
  lockfile, the image's id, the config, the sidecar files it names, the
  stage tree file by file, the mounts, the environment. A hit is read
  by the same reader a miss goes through; a stored file that no longer
  reads is dropped and the unit indexed. Only a contained, successful
  run is stored; `HOBBES_INDEX_CACHE=0` indexes afresh.
- The ingest summary prints, under the timings, how many units were
  read and how many indexed, the keys' cost and the store's path; the
  timings log line (ADR-119) carries the same under `index_cache`.
  Nothing enters an artifact.
- Measured on this repo: 54.0 s → 8.9 s; lane B 49.2 s → 4.1 s, what
  remains the fetch passes that run before the helper (Java's resolve
  2.3 s, Go's downloads 0.8 s, Rust's 0.5 s, the venv listing 0.4 s).
- **C-158 registered (surfaced):** a linked dependency tree and a venv
  are fingerprinted by their surface, not their files; a lockfile-less
  manifest keeps its first resolution until the stage changes or the
  entry is swept (30 days untouched).

## 0.2.34-beta — 2026-09-16 (C's walk abstains under `sizeof` too; ADR-121's amendment)

**Patch: what the layer draws.** The oracle's reader is one for both
languages, so once it stopped keying a call under `sizeof` (H-32) the
key abstained in C where lane A's C walk still recorded the site.

- Lane A's C walk records no call site under a `sizeof` or `_Alignof`
  operand (C11 6.5.3.4), the C++ predicate one grammar over. Measured
  first: 0 such sites on cJSON, sqlite-vector and `minic`.
- The residual is C's own: a `sizeof` operand whose type is a
  variable-length array is evaluated (`sizeof(int[n()])` calls `n`),
  and the syntax cannot tell it apart, so that call is dropped too.

## 0.2.33-beta — 2026-09-16 (no call in an unevaluated operand; ADR-121)

**Patch: what the layer draws.** A C++ call written inside an operand
the program never evaluates was drawn as a `calls` edge.

- Lane A's C++ walk records no call site under `sizeof`, `alignof`,
  `decltype`, a `noexcept(..)` expression or a requires-expression;
  `noexcept` and `typeid` in call position, which the grammar spells as
  a call of a bare identifier, record no site of their own. `typeid`'s
  operand keeps its sites: it is evaluated when it is a polymorphic
  glvalue, which the syntax cannot tell.
- The join and the tail are unchanged: lane B's occurrence at such a
  site falls through as a `uses` edge, the true statement of a
  dependency that is not a call.
- **C-155 lifted** the day it was registered. Measured first: fmt had
  49 such sites, one drawing a graded edge (its last contradiction that
  was not scip-clang's); args 7, none drawing.
- The oracle's own half — clang's dump keeps the call under `sizeof`,
  `noexcept` and `typeid`, and O10 keyed it — is logged as H-32 and
  fixed under `bench/` (no version move).

## 0.2.32-beta — 2026-09-16 (the override set is drawn as `implements` edges; ADR-120)

**Patch: what the layer draws and says.** A SCIP index states which
definition implements or overrides which, and the helper read past the
field on every language.

- Measured first: scip-clang, scip-go, scip-typescript, scip-python and
  scip-java state the set (scip-java in both directions on an abstract
  method); rust-analyzer states none — **C-157**, surfaced on every
  Rust run.
- The helper (version 5) decodes `SymbolInformation.relationships` and
  emits one `implements` row per pair between two in-repo definitions,
  oriented from the implementor, deduplicated and sorted; the facts
  carry it as a fourth row kind, counted in the trailer.
- The join draws each pair as an **`implements`** symbol edge at
  semantic tier; the ingest summary counts them apart from calls and
  uses and says what was not drawn (below lane A's floor, outside the
  repo, unplaced, undirected); `who_calls` lists a symbol's
  implementors under "implemented or overridden by"; `hobbes diff`
  counts the type; `hobbes plan` weights it as an import.
- **C-58 narrowed:** the override set is in the graph; the dispatch
  through an interface is still not drawn, and reach still follows
  `calls`. This repo: 18 edges, 7 pairs below the floor (Go's interface
  method specs), 83 to the stdlib.

## 0.2.31-beta — 2026-09-16 (the ingest says where its time went; ADR-119)

**Patch: what the layer says.** No step of the ingest was timed, so no
speed change could be measured.

- Every step of `extract_repo` — each language's lane A walk, the
  packs, each lane B index run, the join, the projection, the lane
  agreement, the tail, the test map, the write — is timed in run order.
- The ingest summary prints the total and every step, and `hobbes
  ingest` appends one JSON line per run to
  `~/.hobbes/cache/timings/<key>.jsonl`, naming the path.
- Nothing enters an artifact: two ingests of one commit stay
  byte-identical.

## 0.2.30-beta — 2026-09-16 (the knowledge store decodes an artifact once; ADR-118)

**Patch: how the layer answers.** Every knowledge tool call re-read
and re-decoded the whole of `graph.json` (and `tests.json` for
`tests_guarding`), then scanned every edge: 8 MB per answer on this
repo, 980 MB on ScummVM.

- The store decodes each artifact once and serves it until the file's
  size or modification time moves; a re-ingest is seen on the next
  answer, and a removed artifact is reported, never served from memory.
- Module and symbol edges are indexed by endpoint at decode time, in
  the artifact's order, so every answer is byte-identical to the
  scan's.
- Rebuild the image and restart the knowledge server (C-65).

## 0.2.29-beta — 2026-09-16 (an unguarded module no call can reach says why; C-156)

**Patch: what the layer says.** Test reach follows `calls` edges only
(ADR-007), so a module that holds only values, such as a constant its
test reads, can never be seen as guarded. `tests_guarding` and
`hobbes review` called it unguarded and gave no reason (C-156).

- A module is *value-only* when it declares no function, method,
  class, type or macro, and no recorded call targets anything it
  declares. A TS/JS `const` holding a called arrow function is
  callable (ADR-117).
- `hobbes review` still lists such a module under "new code no test
  reaches" or "lost every guarding test", and it still needs attention.
  Its line now carries the reason, and `--json` lists it under
  `coverage.value_only`.
- `tests_guarding` still answers "unguarded", and adds a line naming
  each value-only module and C-156.
- C-156 moves from unsurfaced to surfaced.

## 0.2.28-beta — 2026-09-15 (the gate reads a TS/JS arrow's parameters; C-91)

**Patch: what the layer refuses.** `hobbes gate`'s TS/JS text read of
local bindings missed an arrow function's parameters. Its pattern needed
`function` or a word character right before the `(`, so the list in
`= (check) =>` was never read, nor the one name in `fn => fn(1)`, and a
call through such a parameter grounded as `near-miss` or `invented` and
blocked. That was the harness's one false block
(`S-20260915T135819Z-f3c1`).

- The read now takes a parenthesised list before `=>`, wherever it
  stands and with an optional TS return type, and one bare name before
  `=>`. As before, a binding covers the whole file.
- Still unread, and written down in C-91: a list holding a nested `(`
  (a default that calls, or a parenthesised return type). A call
  through such a parameter still blocks.
- The grounder's rule version is 4, and gate records say so.
- Built through the harness: `S-20260915T191904Z-2b26` (27 of 80 turns,
  4.2 min; $1.57 reported). Gate right-clear, verify pass, merged
  without squashing (`3526be2`); four new tests, and the branch's full
  pytest (1,632) passed on the host before the merge.

## 0.2.27-beta — 2026-09-15 (a C or Java unit's own record sits at its root, once)

**Patch: what the layer says.** A C build root or a Java unit below the
repo root recorded one of its own degradations at `root/root`. The
caller appended its record, already repo-relative, and then re-rooted
the facts, whose rule puts the root in front of every record path the
helper wrote relative to it. The caller now re-roots first and appends
after, as the TypeScript zone always did.

- C: "…; derived with <source> instead", when a root's carried compile
  database is not usable here. Java: "dependency resolution failed …",
  when the resolve pass fails. The ingest summary and
  `list_blind_spots` showed each at a directory that does not exist.
- A root at the repo's own root was never affected, and neither were
  the helper's records or Rust's and Go's (written at `.`, which the
  rule maps to the root).
- Found in passing during ADR-116. Tests: two new, one per language,
  each failing on 0.2.26-beta's code.

## 0.2.26-beta — 2026-09-15 (lane B's facts arrive as a stream; ADR-116)

**Patch: what the layer draws and says.** A constraint's fix (C-150's
remainder), taken after the routes were put to Max with measurements
("yes proceed with a").

- **The helper writes its facts to a file, one JSON line per document.**
  It printed them as one JSON document on stdout, built by one
  `JSON.stringify`. ScummVM's facts are 699 MB of JSON and V8's longest
  string is 536,870,888 characters: the helper threw `RangeError:
  Invalid string length` and exited 1, and the record said "install
  Node", so at 0.2.25-beta that root still had no lane B. The file
  (`<stage>.facts.ndjson`, beside the config) is a header naming the
  helper version, one record per document whose rows no longer repeat
  its path, and a trailer that counts the documents and each kind of
  row. ScummVM's is 487 MB, written under the image's default heap at
  3.29 GB resident in 33 s.
- **The Python side reads it as it arrives.** Each reference becomes an
  evidence-IR resolution site on arrival, with no dict row kept;
  definitions and external references stay rows, and every path and
  name is one interned string. ScummVM's facts read at 0.99 GB (1.36 GB
  with the join's buckets), where the one document parsed at 3.63 GB.
  The records carry exactly the decode's rows, per file and in order
  (checked on every row of ScummVM's facts), and this repo's graph,
  test map and interfaces are identical whether 0.2.25-beta's code or
  this one's builds them from the same tree.
- **ScummVM, end to end, has lane B for the first time:** 941,498
  semantic symbol edges, and its 1.55 million C/C++ call sites 61.3%
  accounted where they were 0.0%, in 8 min 57 s at a 7.72 GB peak on
  the Python side, every step contained.
- **A short file is refused.** No trailer, counts the rows do not
  reach, another version, a malformed record or no file at all is a
  `ScipError` that says which, never a smaller answer.
- **`Site` is slotted**, lane A's call sites included.
- **Register:** C-150 corrected (the wall at 0.2.25-beta was the
  helper's output string, and its record read "install Node") and
  narrowed to the join's own size; its surfacing moved to *partial*,
  because an ingest the kernel kills on the Python side leaves no
  record at all.
- Helper version 4. Node tests 77 (three new); pytest 1,626 (eleven
  new for the facts file, two retired with `resolution_sites`).

## 0.2.25-beta — 2026-09-15 (lane B's decode streams the index; ADR-115)

**Patch: what the layer draws and says.** A constraint's fix (C-150),
taken after the memory problem was assessed as a whole and its routes
put to Max ("streaming decode is best route").

- **The helper reads SCIP's wire format itself, one document at a
  time.** It used to build a root's whole index as generated protobuf
  objects — one object, its wrapper arrays and a copy of the symbol
  string per occurrence — under Node's default heap, and ScummVM's
  387 MB index (7.9 million occurrences) needed 8.95 GB that way, so
  the root had no lane B. The decode reads three fields of an
  occurrence and one of a document, in two passes, and now gets
  exactly those, materialised only while it looks at them. The same
  index decodes under the default heap at 3.4 GB resident, in 33 s
  against 38, with facts identical to the old reader's: every
  definition, reference, external row, package, ambiguity set and
  degradation record checked by digest. The unit indexes of a C or C++
  root are streamed in turn the same way, so the merge no longer
  holds them at once.
- **A killed helper says so.** The out-of-memory record of 0.2.21-beta
  read V8's heap markers; a helper the kernel's OOM killer or a
  container's memory limit ends carries none (137 through podman, -9 on
  a host run) and fell back to "install Node". It now says the helper
  was killed decoding the index and names C-150.
- **Register:** C-150 narrowed and retitled — what is left is the
  facts' own size, held whole on the Python side (about 2.1 GB parsed
  for ScummVM, beside lane A's 1.5 GB), which is a facts-format change
  and a separate decision; the entry names the `HOBBES_SCIP_CMD` heap
  override for a box that needs one. C-149 reworded: the 400-unit bound
  stays for the references the per-unit route holds and the disk and
  time it spends, not for the merge's memory, which is gone.
- **The typed-range monkeypatch is gone** with the generated reader:
  the helper's own reader knows scip-java's fields 8 and 9.
- Node tests 74 (three new, one rewritten); pytest one new.

## 0.2.24-beta — 2026-09-15 (fixture sources are not own code; the graph job reviews from its last green run; ADR-114)

**Patch: what the layer says.** `hobbes review` stops asking for a
guard on sources a test can only read.

- **The trigger:** the graph job went red on the push of `fdc7f07`,
  on 8 "unguarded new modules". Every one was a C++ fixture source
  (`minicpp`, and the oracle's `cppclang` testdata). A fixture is a
  test's input: nothing calls it, so no test can be seen reaching it.
  The C fixtures were just as unguarded and passed only because the job
  forgot them.
- **Fixture trees** (ADR-114, amending ADR-025): a source under a tree
  the repo's own test runners exclude is not own code. The trees are a
  pytest config's stated `norecursedirs` under its `testpaths`, and
  Go's `testdata` inside a module. They are read from each end's tree at
  extraction (`runner_excluded_trees`). The coverage section names each
  tree, its rule and its module count, and `--json` carries them as
  `coverage.fixture_trees` (C-154, surfaced). On this repo they are
  `pipeline/tests/fixtures` and `bench/oracle/testdata`.
- **The review's base in CI** (amending ADR-095): a push reviews from
  the last green `ci` run's commit when that commit is an ancestor of
  `HEAD`, and from the push's `before` otherwise. So a red review stays
  red until it is fixed (the W0 item of 2026-09-10). The job lists runs
  with `actions: read`.
- **The same push's other red job**, fixed without a version move
  (`2883154`, `bench/` tooling): the oracle lane's drift test failed
  because the two C++ cells had no `cells.meta.json` row. They are now
  in the comparative tables, the one number and a C++ scatter panel.
- **Register:** C-154 registered.

## 0.2.23-beta — 2026-09-15 (C++ supported: its §3.8 row; ADR-113 complete)

**Patch: what the layer says.** A language reaching *supported* is a
patch (ADR-103's notes).

- **C++'s §3.8 row**, on two compiler-graded cells (O10, clang's own
  front end), regraded at 0.2.22-beta:
  - fmtlib/fmt (chosen): 3,254/3,282 (99.1%);
  - Taywee/args (drawn at random): 1,995/1,995 (100%).

  `VERIFICATION_BASE` carries the row, so the ingest summary, the
  surface's language badges and `list_blind_spots` now say "cpp 2
  repos" where they said "not verified on any repo".
- **What the row does not cover:** fmt's 10 wrong edges are
  scip-clang's own (C-153, unsurfaced, P9). A build over the per-unit
  bound or the helper's heap (C-149, C-150), modules, generated code
  and a mixed repo's shared headers (C-142) are outside the sample.
- **Register:** C-132 narrowed again. A `.h` both languages include is
  still read as C, and cgo's collision (C-15) stands.

## 0.2.22-beta — 2026-09-15 (C++'s lane B answers only where it is sure; ADR-113 §2 amended a third time)

**Patch: what the layer draws.** Two defects that the first C++ oracle
cells found are fixed. C++ is still *wired, not supported* until its
row.

- **The cells.** fmt read 96.1% and args 99.8% at 0.2.21-beta, and
  every contradiction was read. Two Hobbes mechanisms accounted for
  most of them:
  - C's one-target-per-site rule met C++ overloads. scip-clang lists
    the candidates of a call in a template it cannot resolve there, and
    the rule kept the first line: 36 wrong semantic edges on fmt, all 4
    of args' contradictions.
  - Lane A's name fallback drew in files scip-clang had compiled, where
    lane B answered nothing: 74 wrong of 182 syntactic edges on fmt. C's
    ranks do not see namespaces, so a libc call reached a namespaced
    mock by name, and a parse error could hide the real definition. The
    external veto could not fire, because C++ units record almost no
    external occurrence.
- **Two rules, for C++ only:**
  - A call site whose references name more than one overload has no
    lane B answer, and one `scip-decode` record counts the sites (C-151;
    fmt 658, args 14).
  - A C++ file lane B indexed draws no fallback edge where lane B
    answered nothing. `lane_agreement.cpp_withheld` and one
    `cpp-fallback` record count the sites (C-152; fmt 527, args 0). Lane
    agreement still compares both lanes, and a C++ file lane B did not
    index keeps its fallback.
- **Regraded against the stored keys:** fmt 3,254/3,282 (99.1%), args
  1,995/1,995 (100%). The cost is recall: fmt 15.5% → 14.5%, args
  57.1% → 56.4%. fmt's 28 remaining contradictions split into 10 of
  scip-clang's own single wrong candidate (C-153, unsurfaced, P9) and
  18 of the oracle's (H-28–H-31, open).
- **Built through the harness:** `S-20260915T161919Z-8302` (77 of 120
  turns, 8.7 min; $6.48 reported). Gate right-clear, verify pass,
  merged without squashing. The `minicpp` live test the doer extended
  was red on the host on one wrong assumption, and was fixed there.

## 0.2.21-beta — 2026-09-15 (C and C++ indexed one translation unit per run; ADR-109 amended)

**Patch: what the layer draws.** A constraint's fix (C-149), not a
feature; C++ is still *wired, not supported*.

- **One translation unit per scip-clang run** (Max's route). scip-clang
  indexes a header many units share once, in whichever unit claims it
  first, so a reference whose answer depends on the unit came and went
  between ingests: three cJSON ingests at one commit drew 2,630, 2,615
  and 2,621 edges. The helper now writes the derived compile database
  out as one-entry databases, runs scip-clang on each (`-j 1`, at most
  the box's parallelism at a time), and decodes the units' indexes as
  one with the order-independent rules 0.2.20-beta put in place. A
  unit that fails is counted, and the others stand. Three cJSON
  ingests are now identical, edges and tail; three fmt ingests are
  identical at the edge level.
- **A size guard** (Max). The merge holds every unit's index at once.
  On ScummVM (5,958 units, built in the image for this measurement)
  that would have needed about 84 GB. So a root with more than 400
  units is indexed in one whole-database run, and a `scip-decode`
  record says so and names C-149 (now *partial*). fmt (52), args (99)
  and cJSON (23) lie under the bound. A streaming merge would lift it.
- **A crash fixed, and the next limit named:**
  - The decode spread its references into one call's arguments, which
    overflows the stack at a few hundred thousand references; it now
    loops.
  - On ScummVM (5,958 units, ingested end to end in 614 s) that moves
    the failure from the stack to Node's heap. The whole-database
    decode needs about 9 GB, the helper dies (exit 139), and the root
    falls to lane A.
  - The record said "install Node". It now says the helper ran out of
    memory and names C-150.
  - A larger heap or a streaming decode would fit it; Max's call.
- **Built through the harness:** `S-20260915T135819Z-f3c1` (59 of 120
  turns, 9 min; $4.92 reported), verify pass, merged without
  squashing. The gate blocked it falsely, the harness's first false
  block: a call through an arrow-function parameter, which the gate's
  TS/JS text read misses (C-91 amended; the fix is a small unit to
  come). The session tracker now parses a blocked gate line.

## 0.2.20-beta — 2026-09-14 (C and C++ lane B made order-independent; ADR-113 §2 and ADR-109 amended)

**Patch: what the layer draws.** A defect's fix; C++ is still *wired,
not supported*.

- **The defect:** lane B for C and C++ drew a different graph from one
  ingest to the next at one commit. Three fmt ingests drew 3,308,
  3,298 and 3,293 call edges, and two cJSON ingests differed by one
  edge; C had this since 0.2.4-beta. scip-clang gives one moniker to
  several definitions in one file: a class template and its
  specialisations, `enable_if` overloads its signature hash does not
  tell apart, and `#if` alternatives. It lists them in an order that
  varies by run, and the helper kept the first one it met.
- **The fix (Max chose the rule):** every definition line is collected
  and the choice is made by rule. **C++ abstains:** such a reference
  draws no lane B edge, stays in-repo (no ADR-111 veto), and one
  `scip-decode` record counts them (on fmt, 240 monikers and 2,228
  references; C-148). **C takes the smallest line,** which is what
  ADR-109's first-line rule meant. A namespace keeps its smallest line
  in both. Three fmt ingests are now identical at the edge level (3,273
  call edges each).
- **What it does not fix, registered (C-149, debt):** scip-clang
  indexes a header many units share once, in whichever unit claims it
  first, and that varies by run. So a reference whose answer depends
  on the unit can come and go. On `main`, three cJSON ingests drew
  2,630, 2,615 and 2,621 edges, all `uses` edges from Unity's
  assertion macros; four of fmt's tail sites flip between `external`
  and `builtin-name`. scip-clang's own `--deterministic` flag was
  measured and refused: 307 s against 8 s on fmt, with 3 of 52 units
  lost. Indexing each unit alone, measured at 9–10 s against 8 s on
  fmt, is the route to lift it, and it is Max's call.
- **Built through the harness:** `S-20260915T015439Z-3d1a` (32 of 80
  turns, 3.7 min; $2.23 reported). Gate clear and verify pass; merged
  without squashing.

## 0.2.19-beta — 2026-09-14 (C++ at lane B, deliberate; every overload a symbol; ADR-113 §2)

**Patch: what the layer draws.** C++ is still *wired, not supported*:
the two oracle cells and the §3.8 row come next.

- **Lane B for every C++ build root** (ADR-113 §2, amended with a
  measurement on `minicpp` before the unit). C and C++ files go to
  scip-clang as one set, so a mixed root is one index. A root holding
  any C++ file (one of the six extensions, or a `.h` the C++ layer
  claimed) is a C++ root. It uses the helper's `cpp` language, which is
  C's indexer spec, plan and decode rules, with stage `scip-cpp`, the
  `index-c` containment profile, and records and a build disclosure that
  say C++. A C-only root is unchanged, byte for byte.
- **A construction draws the constructor.** scip-clang answers
  `Circle c(3)` and `new Circle(1)` with the class and its constructor
  under one name, and both the join and C's one-target rule picked the
  class. The helper now drops the class there (C++ only). A
  construction whose constructor is implicit keeps the type alone. The
  projection's calls-to-type guard (Go's conversions, Rust's tuple
  structs) now covers C++ definitions, so such an edge is `uses`, never
  `calls`.
- **Every overload is a symbol** (C-144, lifted). A later definition of
  a qualname with different parameters takes `~2`, `~3`, …, Java's
  convention. A repeat with the same parameters is still C's duplicate,
  and its `parse` record now names preprocessor alternatives only. The
  fallback is unchanged: an overload set is still a tie.
- **The duplicate-moniker record** names C++'s namespaces (scip-clang
  declares one from every file that opens it) beside C's statics.
- **Measured on fmt after the merge:** below-floor sites went from
  7,628 to 7,357, so overloads were a small part of them. A diagnostic
  places 6,896 of 7,376 below-floor facts on definitions in files that
  parsed with errors and have no lane A symbol near. That is C-145's
  cost (the vendored `gtest.h` alone accounts for 3,375), now stated in
  its entry.
- **Built through the harness:** `S-20260915T001249Z-be34` (114 of 150
  turns, 13.5 min; $10.84 reported). Gate clear and verify pass; merged
  without squashing.

## 0.2.18-beta — 2026-09-14 (C++ at lane A, wired, not supported; ADR-113)

**Patch: what the layer draws.** A language addition is a patch even
when it reaches "supported" (ADR-103's notes), and this one has not:
C++ has a syntax provider and an oracle, and no §3.8 row yet.

- **The eighth walk** (ADR-113 §1): `extract/cppsource.py` on
  tree-sitter-cpp 0.23.4, on `csource`'s contract, C's rules by import
  where they are C's. `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh` and `.hxx`
  are C++; a `.h` is claimed by its includers (a repo with C++ and no
  `.c` claims every `.h`; a mixed repo claims a `.h` C++ includes and C
  does not; one both include stays C), and a mixed repo says how they
  went (`cpp-headers`). Symbols from definitions only — functions,
  methods with `::`-joined qualnames, constructors and destructors
  named by the class, types, function-like macros; namespaces and
  lambdas are not symbols. Five call-site shapes at the terminal
  identifier, `new A(x)` and `A a(x)` named by the class. The fallback
  is C's three ranks plus the unique qualname for a qualified call; an
  overload set abstains (`overload-set`); a member call is lane B's.
  gtest and Boost.Test bodies attribute to their test; Catch2 and
  doctest bodies the grammar leaves in an error node are counted
  (`cpp-tests`). The tail gains the `cpp` bucket: a coverage row may
  carry `language`, and both the tail and the proxy's tables prefer it
  over the extension, so a C++ project's `.h` files count as C++.
- **Lane B already reaches C++** wherever a build root has a C file:
  the derived compile database names every unit and scip-clang indexes
  them all (fmt: 2,992 semantic C++ call edges on the first read). A
  C++-only root, the overload symbol ids and the duplicate record's
  wording are unit 2's.
- **Register:** C-142–C-147 in a new segment, `extraction-cpp.md`;
  C-132 narrowed. The first host read (fmtlib/fmt) found two: every
  macro-spelled library header parses with error nodes (C-145, C-131's
  C++ face), and an overload set trips C's duplicate-definition rule,
  so only its first definition is a symbol (C-144, a defect for unit 2).
- **The oracle** (`bench/`, no version): O10, the C oracle's C++ face
  (oracle-grading.md §7d) — member, operator, constructor and virtual
  sites; declarations keyed by mangled name across units; `oracle
  c-clang --lang cpp`. The `cppclang` fixture hand-keyed at 25 sites.
- **Built through the harness,** two sessions in parallel from one
  parent: `S-20260914T161248Z-3d56` (142 of 200 turns, 28 min; $18.67
  reported) and `S-20260914T161308Z-a848` (139 of 200, 25 min;
  $16.08). Both gate clear and verify pass; merged without squashing.
  The tracker's drift test was red on `main` until the two review
  blocks were filled (expected: it holds the table to the logs).

## 0.2.17-beta — 2026-09-14 (the doer's model is named, per checkout; ADR-107 amended)

**Patch: what the layer says.** Every session on record before this
one ran on "model the default": `hobbes dispatch --model` reached
Claude Code's own flag, but nothing set it, and the doer's container
carries no user settings (its HOME is a tmpfs since 0.2.14-beta), so
the model was Claude Code's choice for the owner's account —
unrecorded, and not the owner's.

- **The rule** (ADR-107's 2026-09-14 amendment). `hobbes dispatch`
  reads `$HOBBES_DISPATCH_MODEL` when `--model` is not given; the flag
  beats the variable; unset or empty leaves the choice to Claude Code,
  as before. The session argv, `dispatch.json`'s doer record, the
  session log's Doer line and the dry run already carried the model,
  so a pinned one is visible at every step a developer reads. A
  checkout sets it in the `env` block of its gitignored
  `.claude/settings.local.json`, beside `HOBBES_SECRETS`: the box's
  setting, not the repo's — the repo names no model. Nothing new
  crosses into the container.
- **Built through the harness:** `S-20260914T153042Z-cd8e` (22 of 60
  turns, 76 s; $1.11 reported), run with `--model claude-opus-5` said
  explicitly — the first session whose Doer line names its model.
  Gate clear and verify pass (388 tests, 0 regressions, 3 new). Merged
  without squashing.
- **The developer's follow-up:** the session tracker's Doer pattern
  knew only `model the default`, so the first named model broke its
  render — as the stream bracket did at 0.2.15-beta, a first-of-its-
  kind line the pattern had not met. It now takes a name and keeps it;
  a test holds the shape.

## 0.2.16-beta — 2026-09-14 (a derived compile database with none of the root's files says so; C-135's measured gap closed; ADR-109 amended)

**Patch: what the layer says.** The gap C-135 measured on bpftop, a
root whose derived database indexed nothing and said only "the indexer
emitted no documents", now names its cause.

- **The rule** (ADR-109's 2026-09-14 amendment). The C plan's
  compile-database check, which already stops the plan on an empty
  database, now also stops it when the database has entries and none
  of a file under the root: the message names the count, where they
  lie — cargo's registry (the dependencies' own C) or their common
  directory — that the build compiled none of the root's own C, the
  build's last words capped, and `(C-135)`. The root's `scip-c` record
  carries it, and `list_blind_spots` shows it with the register id. A
  database with any entry under the root is unchanged.
- **On bpftop** (`5a67ec0`, contained): 45 compiles, every one
  libbpf-sys's vendored libbpf or vsprintf under cargo's registry.
  libbpf's make fails in the image for want of `libelf.h`, cargo stops,
  and bpftop's own build script never compiles its BPF program.
- **The developer's follow-up.** A check's refusal exited the helper
  with the generic code, so the Python side reported it as "the SCIP
  helper is unusable — install Node and run `npm install`". It now
  carries the indexer's exit, and the record reads as the C build's
  own outcome. The empty-database case had the same mislabel since
  0.2.4-beta and takes the same fix. Both tests assert the exit code.
- **Register:** C-135 narrowed; still *partial* (its autotools, Meson
  and Bazel roots, and a database with root entries that still indexes
  nothing, not yet seen).
- **Built through the harness:** `S-20260914T022459Z-1ae3` (17 of 100
  turns, 94 s; $0.45 reported). Gate clear and verify pass (48 tests,
  0 regressions, 4 new). One egress refusal: `npx vitest` reaching for
  the registry, since vitest is not in the helper's tree. Merged
  without squashing.

## 0.2.15-beta — 2026-09-14 (an include lane A cannot place is written down; C-133 narrowed; ADR-108 amended)

**Patch: what the layer says.** The register's one unsurfaced C entry
is now met where a user reads the graph's boundary.

- **The rule** (ADR-108's 2026-09-14 amendment). An include decision
  4's three steps cannot place in the repo draws one `c-includes`
  degradation record per directory, which `list_blind_spots` shows:
  - **unmatched:** a `"p"` include no step resolved;
  - **ambiguous:** a `"p"` or `<p>` include whose suffix matched more
    than one repo header;
  - an angle include that matches nothing stays a dependency
    (`ext:<p>`) and is not counted.

  Specs are counted once per directory and the message names up to
  three of each shape. The edges did not move.
- **On cJSON** (lane A, `fb16e5c`): 305 include edges before and after;
  **6 records** — `"ProductionCode.h"`/`"ProductionCode2.h"` ambiguous
  in four of the vendored Unity examples' directories (each example
  ships its own copy), `"Types.h"` and six mock headers under
  `test/expectdata` unmatched. **On sqlite-vector** (`0c2223a`): 163
  before and after; **1 record**, `libs`' six platform and generated
  headers (`"sqlite_cfg.h"`, `"_mingw.h"`, `"windows.h"`, …).
- **Register:** C-133 narrowed to *partial* (was unsurfaced). The macro
  half — a macro two includes down classed `unclassified` — stays; so
  does reading the `-I` path from the derived compile database, the
  second unit. The debt table reads 18 partial and 3 unsurfaced.
- **Built through the harness:** `S-20260914T015405Z-47f7` (25 of 100
  turns, 4.3 min; $0.79 reported). Gate clear and verify pass (187
  tests, 0 regressions, 6 new). Merged without squashing.
- **The developer's follow-up:** the session tracker's Policy pattern
  did not read the stream bracket 0.2.14-beta's dispatch puts on the
  Policy line (`; records: stream opened→closed`); this was the first
  session to carry it, and the drift test was red until the pattern
  took the clause. A test holds both shapes.

## 0.2.14-beta — 2026-09-14 (a session's records leave the doer's container; C-140 narrowed; ADR-112)

**Patch: what the layer refuses.** Max chose the route (the records'
writers move out; the executor stays) and the number: a constraint's
fix is a patch, not a feature advancement.

- **The sidecar.** `hobbes-proxy sidecar` replaces `hobbes-proxy egress`:
  one container per session, `hobbes-side-<id>`, on the session's
  internal network, the only writer of `flight.jsonl`, `escalations/`,
  `mail.jsonl` and, with `--egress`, `egress.jsonl`.
  - The proxy feeds it over **one flight stream, claimed once**
    (`serve --sink`). A second `open` is refused and recorded; a killed
    proxy closes the stream, recorded, and takes the doer's shell with
    it. The sink stamps session and role from its own configuration.
  - The progress hook posts its edit lines the same way
    (`record-edit --sink`); the sink keeps a tool and a path and
    nothing else.
  - The sink's own lines bracket a session's log: `listening`,
    `stream_opened`, `stream_closed`, `stream_refused`.
- **The doer's container** mounts no part of the session dir
  read-write: HOME is a tmpfs (4 GB cap), and `<id>/in/` — the MCP
  config, the hook's settings, a scripted driver — is its one read-only
  host dir. Retention holds by construction; `PurgeDoerState` runs only
  in the file world.
- **Every session gets its own internal network and a sidecar.** The
  default `--network none` is gone. An explicit `--network` (the
  bench's pasta; the owned runtime needs it for its transcript) keeps
  the file journal in the doer's container, and the dry run and the
  launcher say so in one line naming C-140.
- **`hobbes dispatch`** reads the same three files, leaves the sink's
  lines out of the exec and edit counts, and reports the stream's
  bracket on its Policy line.
- **Measured first** (ADR-112): a sidecar is reached by name on the
  internal network with no route off the box; Claude Code runs with
  HOME on a tmpfs and read-only config; an anonymous volume survives
  `podman rm -f` where a tmpfs does not; a socket cannot be reopened
  through `/proc/<pid>/fd`.
- **The guarantee's own tests (P10):** `internal/sink` (one stream
  ever, the refusal written, the edit shape, the escalation round
  trip); the proxy's escalation outcomes over the sink client; and
  live, `TestALiveSessionCannotReachItsOwnRecords` — a real session
  finds no flight log to delete, sends one event by hand, is refused
  a second stream, and the host log holds the bracket in order.
- **Register:** C-140 narrowed to a forged edit line, surfaced (78
  surfaced, 17 partial).
- **Built through the harness,** two dispatched units, both gates
  right-clear:
  - `S-20260914T004830Z-3ebb` (82 of 150 turns, 16 min, $4.42): the
    sink, the sidecar and the proxy's journal. Verify pass (83 tests,
    0 regressions).
  - `S-20260914T010846Z-de81` (94 of 150 turns, 21 min, $6.69): the
    launcher, dispatch and the exit check. Verify pass (96 tests, 0
    regressions).
  - What verify could not see, both times: a live test red on the
    host — the egress route between the two merges, and the mount test
    still handing the launcher the fake proxy. The developer fixed the
    second in the commit after the merge, and hardened the sink (an
    escalation id is one path segment; the sidecar stops both
    listeners when one fails).

## 0.2.13-beta — 2026-09-13 (C tests by their registrations; C-134 narrowed and surfaced; ADR-108 amended)

**Patch: what the layer draws and says.** Max's three calls on the
amendment, taking the proposed route each time.

- **The rule.** A function named by a Unity (`RUN_TEST`), CMocka
  (`cmocka_unit_test*`) or Check (`tcase_add_test*`) registration is a
  C test.
  - It resolves by the fallback's ranks 1 and 3, and a tie abstains.
  - A file that defines a registered function contributes exactly its
    registered functions. The `test_*` convention holds only in files
    that define none.
  - A function that is both registered and convention-named is one test.
- **Two `c-tests` degradation records**, which `list_blind_spots` shows:
  - a test program under `test`/`tests` with a `main` and no test Hobbes
    can name;
  - a per-directory count of `Test`/`TEST` bodies and `RUN_TEST_CASE`
    calls, the forms Hobbes knows and does not read.
- **On cJSON** (lane A): 39 tests became 199.
  - Its own `tests/`: 162 `unity` tests, one for every `RUN_TEST`
    registration, and neither helper.
  - The vendored Unity tree keeps 37 convention tests: its two example
    trees share names, so rank 3 ties.
  - Five records. The body count is a floor (27 of 32 in
    `unity_fixture_Test.c`).
- **Register:** C-134 narrowed, and *partial* (was unsurfaced). The debt
  table reads 18 partial and 4 unsurfaced.
- **Built through the harness:** `S-20260913T203100Z-e537` (26 of 150
  turns, 555 s; $1.40 reported). Gate clear and verify pass (181 tests,
  0 regressions). Merged without squashing.

**Tooling beside the layer: the session tracker.**
- `pipeline/scripts/calvin_tracker.py render` writes a table of every
  harness session into `docs/calvin/sessions/README.md`, from the logs:
  - turns, wall time and the envelope's reported cost;
  - the gate and review verdicts, the outcome and the area;
  - the totals against `calvin-harness.md` §4.

  A pytest drift test holds the table in step with the logs.
- **Built through the harness:** `S-20260913T203123Z-78b7` (29 of 100
  turns, 519 s; $1.36 reported).
- **The developer's follow-up:** a session's area comes from the code it
  changed, and from its tests only when it changed nothing else. The
  knowledge tools' schemas in `go/internal/proxy/knowledge.go` map to
  knowledge tools.
- It reads 16 of 40 sessions, 4 areas, and $34.92 reported over 15.

**Found: D-s.** Inside a dispatch session, `GIT_AUTHOR_*` and
`GIT_COMMITTER_*` are set to `hobbes-dispatch`, which overrides a test
fixture's `-c user.name`. `units_from_git` then skips every fixture
commit as a doer's, and three `test_ttt_units.py` tests fail. It was
reproduced on the host with the same environment. The `a323` failures
that 0.2.12-beta attributed to D-r are these. D-s is open.

Host pytest: 1,504.

## 0.2.12-beta — 2026-09-13 (verify's worktrees are self-contained: `git` works in its container; D-r)

**Patch: what the layer says.** `hobbes verify` reported tests failing
that pass on the host.

- **The defect (D-r).** `checkout()` cloned each verify worktree with
  `git clone --shared`.
  - A shared clone borrows the source repo's objects through
    `.git/objects/info/alternates`, which names the host repo's path.
  - The container that runs the tests mounts the worktree alone, so any
    `git` a test ran there failed (`fatal: bad object HEAD`).
  - It read as a failure on both trees: the `F2F` for
    `test_cli.py::TestIngest::test_the_artifact_says_which_hobbes_built_it`
    in session `efc8`, ruled out by hand on the host.
  - *Corrected at 0.2.13-beta:* the three `test_ttt_units.py` failures a
    doer saw in `a323` were not D-r. They are D-s, in the doer's own
    session, where dispatch's commit identity reaches the test fixtures.
- **The fix.** A plain clone of the local path. It hardlinks the objects
  on one filesystem, copies them across two, and writes no alternates
  file. Its callers (`verify`, `build_row`) are unchanged.
- **The guarantee's own tests (P10):**
  - `test_checkout_writes_no_alternates_and_survives_the_source_moving`
    moves the source away, then reads `git` in the worktree;
  - `test_checkout_replaces_an_existing_dest`.
- **Checked where a user meets it:** on the host, in the image, the test
  `efc8`'s verify failed passes through the new `checkout()`, and fails
  through a `--shared` clone of the same commit.
- **Built through the harness:** `S-20260913T200618Z-9cad` (15 of 80
  turns, 60 s; the envelope reports $0.29 on the subscription). Gate
  clear and verify pass (88 tests, 0 regressions); host pytest 1,482.
  Merged without squashing.

## 0.2.11-beta — 2026-09-13 (a session mounts only its own dir; `find`'s executing forms and `xargs` are questions; ADR-107 amended)

**Patch: what the layer refuses.** Max: "the recursive delete seems like
an error more than a flag. either look to contain or prevent." Both,
with containment as the boundary.

- **Contain.** `hobbes-session` mounted the whole host sessions root,
  `~/.hobbes/sessions`, read-write at `/sessions`.
  - Every session's clone, flight log, egress log, escalation queue,
    gate and verify records and brief sat under it. An allowed command
    in one session could reach all of them.
  - A session now mounts only its own dir, at `/sessions/<id>`. Every
    in-container path is unchanged. This holds for every role and for
    the benchmark's sessions.
  - The exit check drops its scripted driver into the session's own dir.
- **Prevent.** Both boxes change (`calvin.box.policy`,
  `bench.box.policy`):
  - `find`'s `-delete`, `-exec`, `-execdir`, `-ok` and `-okdir` escalate.
  - `xargs` escalates instead of running.
  - Each of those deletes recursively, or runs a command the policy
    never sees. A plain `find` still runs.
  - A name that contains those words escalates too. That over-match
    asks a question and loosens nothing.
- **What is left: C-140.** The session's own dir stays writable by its
  doer, including its flight log, egress log and escalation records,
  because the policy proxy runs in the doer's container. The fix is to
  give the proxy a container of its own, and that is Max's call.
- **The guarantee's own tests (P10):**
  - `TestALiveSessionMountsOnlyItsOwnSessionDir` runs a real session
    beside a sibling session dir and finds only its own.
  - `TestFindsExecutingFormsAndXargsEscalateInBothBoxes` resolves every
    form against both real boxes.
- **Register:** C-140 registered (112 active, 25 lifted, 3 superseded).
- **Built through the harness:** `S-20260913T163921Z-2aa9` (57 of 150
  turns, 347 s). Gate clear and verify pass (77 tests, 0 regressions);
  merged without squashing.
  - The live test failed on its first host run, and verify could not
    see that, because the test skips in the sandbox.
  - The guarantee held. The fault was in the assertion, which matched
    the path its own `cat` error echoed. The developer fixed the
    assertion in the next commit.

## 0.2.10-beta — 2026-09-13 (C-139 lifted: a local that shadows an import's name stops lane A's guess; ADR-046 amended)

**Patch: what the layer draws.** After 0.2.9-beta the patch number
counts on (Max: "next version goes 0.2.10 not 0.3.0"; ADR-103's note).

- **The rule.** Go lane A's fallback reads a selector's qualifier as an
  import alias only when no local binding of that name spans the call.
  - After `slog := slog.SpanLogger(ctx, …)`, the call `slog.Info(...)`
    is a method on the local logger, and lane A no longer draws it to
    the package's `Info`.
  - It is the scope test a bare name already got (ADR-046/090), applied
    to the qualifier. Where lane B is silent, the site lands in
    `attr-call`.
- **The acceptance regrade:** all 27 Go cells with a stored key were
  re-ingested contained and graded against their keys. **Nothing
  moved:** confirmed, contradicted and syntactic-edge counts all
  matched, with 0 falsely confirmed poison.
- **On dagger:**
  - Its 56 external vetoes (0.2.8-beta) read 0. Lane A no longer
    proposes those sites, so there is nothing for the veto to drop.
  - With lane A alone, 95 fallback resolutions into `engine/slog/` are
    gone and none are new. Of those, 30 were true package calls: the
    declaring statement's own, or one before it. The extent is the
    enclosing function, as the amendment decided, so it gives those up
    too. That costs an edge only where lane B is silent, and it is
    recorded in C-139's entry.
- **Register:** C-139 lifted, with its residual (111 active, 25 lifted).
- **Built through the harness:** `S-20260913T145700Z-a323` (28 of 150
  turns, 183 s). Gate clear and verify pass (213 tests, 0 regressions);
  host pytest on the branch 1,480. Merged without squashing.

## 0.2.9-beta — 2026-09-13 (the directory rollup in `list_blind_spots`)

**Patch: what the layer says.** `list_blind_spots` now carries the
per-directory capture view that the ingest summary prints, read from the
same `resolution_coverage` rows. It ports `rollup_directories` and the
ingest's directory view, parked since ADR-048, and is not a second
computation.

- **The section**, placed before the worst files, is headed
  `by directory (depth 2, worst N of M with unresolvable sites; K
  without)`.
  - It has one line per (directory, language), ranked worst first by
    the count it cannot resolve. Each line gives the capture share, the
    site count, the by-design count and the unresolvable classes.
  - It shows ten rows at most, and a remainder line says what it holds
    back.
  - A directory whose unresolved sites are all by design is counted, not
    listed. A scope where every directory is like that prints no
    section.
- **It is scoped like the rest of the answer.** A scoped question rolls
  up only the rows under the scope, which is the altitude an agent
  scoping a task works at.
- **The two views read the same.** The rows' text is the ingest
  summary's, and the Go function names the Python one it ports and says
  the two stay in step.
- **Built through the harness:** `S-20260913T132457Z-3c45` (25 of 150
  turns, 270 s). Gate clear and verify pass (64 tests, 0 regressions);
  merged without squashing.

## 0.2.8-beta — 2026-09-12 (the external veto: lane A's guess is dropped where lane B resolved the site outside the repo; ADR-111)

**Patch: what the layer draws.**

- **The veto.** `evidence.join` drops lane A's fallback at a call or
  import site whose `(file, line, name)` carries a lane B reference
  outside the repo.
  - The helper marks an external reference `in_repo` when its moniker has
    any in-repo definition (ambiguous across files, C-28, or of a kind
    the graph drops). `join_cross_unit` marks sibling-ambiguous monikers
    the same way. A marked reference never vetoes.
  - Coverage is unchanged: such a site was already counted `external`.
- **Where a user meets it.** `lane_agreement.external_vetoes` counts the
  sites, with up to ten examples, and `hobbes lanes` prints them. A veto
  is not a disagreement, so the exit status does not move.
- **The acceptance regrade** (Max's gate): all 44 oracle cells with a
  stored key, re-ingested contained and graded against their keys.
  - A pre-veto pass on the same build reproduced every stored number
    first.
  - **No confirmed count moved anywhere.**
  - **sqlite-vector: 851/854 → 851/851.** Its syntactic edges fell by 4:
    the 3 wrong `strcasestr` edges, and one spurious edge. Lane A reads
    the prototype at `libs/sqlite3.h:6943` as a call, drawn to the
    uncompiled amalgamation; it graded silent. Max accepted the fourth.
  - Every other cell shows 0 vetoes. Dagger's graph shows 56, in its
    ungraded root module.
- **Found in dagger: C-139, Go's local shadow.** The ten dagger examples
  were calls on a local `slog := slog.SpanLogger(...)` logger, which lane
  A had drawn to the package function `engine/slog.Info`. Lane B resolved
  them to the logger's method outside the repo, so the veto removed wrong
  edges. Where lane B does not answer, the shape remains, registered as
  C-139.
- **Register:** C-138 narrowed; C-139 registered.
- **Built through the harness:** `S-20260912T221854Z-42d1` (99 of 200
  turns). Gate clear and verify pass; merged without squashing.

## 0.2.7-beta — 2026-09-12 (the dispatch box: `rm` and C's toolchain probes; Max's policy)

**Patch: what a dispatched doer's shell may run** (`calvin.box.policy`).

- **Removing a file runs.** `rm *` is allowed. A recursive removal
  still escalates, in each spelling the glob can see: `-r` and
  `--recursive`, `-R`, and the `-fr` and `-fR` clusters, which contain
  neither.
- **C's toolchain probes run:** `clang --version`, `cmake --version` and
  `bear --version`. Anything else those tools do takes the default.
- **The header says what an escalation here is.** It is a question in
  front of the common spelling, not a boundary. `python3 *`, `find*` and
  `xargs*` are allowed, and a doer did delete through `python3 -c` after
  its `rm` escalations expired (`5d5f`). The mounts and the gate's
  partition check are what bound a deletion.
- **A Go test resolves every case against the real box**
  (`TestCalvinBoxRemovesAndProbes`), including `9396`'s compound probe.
  It checks that a deletion outside the partition blocks
  (`test_gate.py`'s partition test, and a gate run on a real diff).

## 0.2.6-beta — 2026-09-12 (the progress hook: a dispatched doer's edits join the flight log; ADR-107 amended)

**Patch: what the harness records.** A dispatch had no signal between
"reading" and "stuck" (`b126`, stopped at 53 minutes while it was
reading).

- **The hook.** For a Claude Code session, `hobbes-session` writes
  `claude-settings.json` beside `mcp.json`, and the doer runs with
  `--settings`. Its PostToolUse hook matches `Edit`, `Write`,
  `MultiEdit` and `NotebookEdit`, and runs the mounted static proxy as
  `hobbes-proxy record-edit`.
- **The line.** `record-edit` appends one flight line per edit: the
  time, the session, the role, the tool and the path (relative to
  `/work`).
  - It reads only the tool's name and the path from the hook's input,
    and never writes the edit's text.
  - It always exits 0, so a fault in it never stops the doer.
  - The flight line gains `path`, omitted when empty.
- **`hobbes dispatch`:**
  - The session file gains an **Edits** line: the count, the files, and
    the first edit's time after launch.
  - The Policy line counts exec decisions alone.
  - While the session runs, dispatch prints the first edit, and one note
    if none has landed by `--quiet-minutes` (default 20, 0 for off). It
    kills nothing.
- **Readers.** `hobbes run`'s `read_flight` no longer counts an edit
  line as a knowledge call.
- **Retention scan.** The scan no longer reads the session's Go build
  cache. There, compiled test packages holding the retention tests' own
  marker read as stored reasoning.
- **Register:** C-125 is narrowed. Edits are in the flight log by path;
  reads are still recorded nowhere.
- **Built through the harness:** `S-20260912T215521Z-efc8` (87 of 150
  turns). Gate clear and verify pass; merged without squashing.

## 0.2.5-beta — 2026-09-12 (C is supported: compiler-graded against clang's front end; ADR-110)

**Patch: the verification base names C.** A language addition is a
patch, not a structural change (Max, 2026-09-12), so this patch carries C
from "wired, not supported" to a §3.8 row.

- **What the layer says now:** §3.8 gains C's row, and
  `extract/verification.py` its pin. Every ingest's `verification base:`
  line, the surface's language badge and `list_blind_spots` now say C is
  verified on 2 repos, where they said unverified.
- **The evidence** (oracle lane O9, clang 18.1.3's own resolution of
  every call, contained):
  - **DaveGamble/cJSON:** 1,188/1,188 confirmed, 0 contradicted, all
    semantic. Recall is 62.0%: every direct call is drawn (1,190/1,190),
    and every miss is a call a macro's expansion makes (723 into Unity,
    5 through cJSON's own `cJSON_SetNumberValue`), which Hobbes draws to
    the macro (C-131).
  - **sqliteai/sqlite-vector** (drawn at random): 851/854. The semantic
    tier is 851/851; 3 syntactic edges are wrong (C-138, below). Recall
    100%.
  - Poison check PASS on every cell.
- **Register:**
  - **C-138:** lane A's fallback guesses where lane B resolved the site to
    a declaration outside the repo. `evidence.join` asks only for an
    in-repo resolution. Measured on sqlite-vector: a `strcasestr` shim in
    a dead `#if` arm drawn over libc's.
  - **C-131** measured on both repos.
  - **C-135's surfacing** is partial: a root whose derived database
    indexes nothing draws a generic `scip-index` record (jfernandez/bpftop,
    the draw's first candidate).
  - **C-130's surfacing** is restated for the new row.
- **Not in the layer:** the oracle itself (`bench/oracle/internal/clang`)
  is bench tooling and carries no version (ADR-103). The image gains
  Ubuntu's clang 18 for it (~0.3 GB).

## 0.2.4-beta — 2026-09-12 (C's lane B: scip-clang over a derived compile database; ADR-109)

**Patch: C gets semantic edges.** C is still unverified, with no §3.8
row, so this is a patch (Max: the minor waits for "supported").

- **scip-clang 0.4.0 is in the image,** with CMake 3.28 and bear 3.1.3
  (Ubuntu 24.04's packages), sha256-pinned.
  - The compile database is derived per build root, in Max's order:
    1. the repo's own, used only if its paths rebase into this checkout;
    2. CMake's export;
    3. bear over `make -k`;
    4. otherwise lane A only, and the ingest says so.
  - It runs as `index-c`, offline, and executes repo code (C-136).
- **The helper decodes C:**
  - **A method's disambiguator** is any identifier (the SCIP spec).
    scip-clang hashes the signature there, and without this rule no C
    function joined.
  - **A macro** is named by its defining location, so its name is read
    from that line.
  - **A file-static that several files define** resolves in the
    reference's own file.
  - **A site (position and name) that translation units resolve into
    different files** keeps lane A's floor. One definition's `#if`
    alternatives collapse to its first line.
- **Measured on cJSON** (the product path, in the image):
  - 2,075 of 4,292 C call sites resolve semantically (48%, from 0);
  - 1,072 semantic edges;
  - the lanes agree on all 1,717 sites where both answer;
  - 2 sites that translation units split keep lane A.

  This repo's `minic` fixture goes through bear over its Makefile on
  every ingest.
- **Register:** C-130 and C-131 narrowed; C-135–C-137 registered.
- **Tests:**
  - node: the moniker shapes, `cPlan`'s three routes and its
    empty-database check, and the decode rules;
  - pytest: build roots, the compile-database choice and its rebase,
    `extract_scip_c` per root, and the containment profile;
  - a `lane_b` case on `minic` in the image.

## 0.2.3-beta — 2026-09-12 (two harness fixes found by a dispatched session)

**Patch: a dispatched doer can check formatting, and a bare `python`
is the right one.** Both were found by `S-20260912T174351Z-404f`; Max
said to make them.

- **`calvin.box.policy` allows `gofmt -l` and `gofmt -d`.**
  - `-w` escalates (escalate beats allow within a scope, ADR-002), and
    `go fmt` keeps the box's default.
  - Four `gofmt -l` escalations had expired in one session, though its
    brief asked for the check.
  - A Go test resolves commands against the real box file.
- **The session's `PATH` puts the outermost Python tree first**
  (`harness.python_trees`: by depth, then by name).
  - `dispatch.py` had sorted the venv bins as strings, so
    `bench/atlas0/.venv` shadowed `pipeline/.venv`, and a bare `python`
    lacked `tree_sitter_c`.
  - The brief's note now names each tree's interpreter
    (`/work/<tree>/.venv/bin/python3 -m pytest`) and says which one a
    bare `python` is.
- **Unchanged, per Max:** the capture line for a fallback-only
  language, which reads 0% for C.

## 0.2.2-beta — 2026-09-12 (the knowledge tools see C; `.mts`/`.cts` too)

**Patch: `list_blind_spots` names C's limits under a C path.** The
first ingest after 0.2.1-beta showed it did not.

- **The knowledge proxy's language tables now mirror the tail's.** In
  `go/internal/knowledge`, `langByExt` and `artifactLangBucket` gained C
  (`.c`, `.h`) and C-100's `.mts`/`.cts`. A C-scoped answer now prints
  C's verification row (`not verified on any repo`) and a `capture [c]`
  line.
- **A drift test** (`test_tail.py`) reads both Go map literals and
  holds them to `tail._LANG_BY_EXT`, so the next language fails a test
  instead of going missing from the agent-facing tool. Architecture
  §3.7 now lists these tables among the places a language touches.
- **Built through the harness:** `7123217`, authored by
  `hobbes-dispatch` and fast-forwarded.
- **Register:** C-130's surfacing text corrected: the C-scoped gap
  until now, and the capture line's 0% for a fallback-only language.

## 0.2.1-beta — 2026-09-12 (C at lane A: wired, not supported; ADR-108)

**Patch: Hobbes reads C, syntax lane only.** C is wired, not supported:
every C edge is `syntactic`, and C has no §3.8 row until its indexer
and evidence land (Max: a patch; the minor waits for "supported").

- **`csource.py`, a tree-sitter-c walk** on the provider contract:
  - `.c` and `.h` files, and `.h` keeps its extension in the module id;
  - symbols from definitions only (functions, types, function-like
    macros), and one symbol per id;
  - the walk is transparent through `#if` arms and `extern "C"`;
  - include edges resolved by path, and `ext:<header>` otherwise;
  - three call shapes;
  - a three-rank name fallback, where any tie abstains;
  - tests by the `test_*` convention.
- **Wired** into `extract_repo` and the join, with the tail's `.c`/`.h`
  row, a pinned C11 builtin list and `__builtin_*`. No lane B: nothing
  in the builder, the join or the schema changed.
- **Built through the harness** (ADR-107) in two dispatched sessions:
  - `984daab` built the walk;
  - `48684e3` reworked the four defects review found on cJSON.

  Both are authored by `hobbes-dispatch` and fast-forwarded.
  `tree-sitter-c` 0.24.2 was added first (`fb24216`).
- **Register:** C-130–C-134 registered (the new segment
  `extraction-c.md`).
- **Decided, not built:** C's lane B is scip-clang over a derived
  compile database (`compile_commands.json`, else CMake's export, else
  `bear`, else lane A only and said so).

## 0.2.0-beta — 2026-09-12 (the Calvin harness is the minor; ADR-103 amended)

**Minor: the harness built across 0.1.21–0.1.23-beta is a capability,
and the number now says so** (Max: "the harness is enough of a jump").

- **What 0.2.0-beta names:** `hobbes dispatch` stacked on the
  environment (ADR-107). Claude Code is the doer inside `hobbes-session
  --egress`, the gate reads a derived map, verify runs on the diff, the
  retention guard applies, and one log file is written per session. No
  product code changes in this version beyond the version string.
- **The number line** (ADR-103, fourth amendment): patch by patch on
  0.2.x; the next minor lands when a capability earns it. 0.2.0-beta is
  untagged; tags stay Max's call.
- **The layer's top-level docs corrected against the tree:**
  - README: CI's shape, and no claim that CI checks the suite counts.
  - TS/JS's syntax lane is ts-morph, not tree-sitter.
  - The image base is Ubuntu 24.04.
  - The acknowledgements: `tree-sitter-java`, javac, Claude Code and
    Olmo 3.
  - first-run: which steps spend quota, the network the fetches use,
    and the six knowledge tools.
  - how-hobbes-differs: the policy chain's order.

## 0.1.23-beta — 2026-09-12 (the first dispatched change; dispatch's turn default 80)

**Patch: the scope-taking knowledge tools take `path` for `scope`, and a
dispatch gets 80 turns by default.**

- **`list_blind_spots` and `list_invariants` accept `path` as an alias
  for `scope`** (ADR-087 follow-up (a); W4).
  - Neither argument is required, and giving neither covers the whole
    repo, as before.
  - Differing values are refused, naming both.
  - Both descriptions name the argument in their first sentence.
  - This is the first change made by a dispatched doer
    (`S-20260912T151945Z-417f`, commit `104c164`, authored by
    `hobbes-dispatch`). It was merged as a fast-forward. The brief kept
    the doer off the version and the CHANGELOG, so this entry carries
    them.
- **`hobbes dispatch --max-turns` defaults to 80** (was 40; Max). The
  first dispatch used 38 of its 40 turns on a two-file task.

## 0.1.22-beta — 2026-09-12 (retention: evaluation rows, never training; ADR-107 amended)

**Patch: a dispatched doer's reasoning is never stored, and recorded
sessions can never become training units.**

- **The doer runs with `--no-session-persistence`.**
- **`hobbes-session` removes the doer's state from its HOME at exit**
  (`.claude/`, `.claude.json*`, `.cache/claude-cli-nodejs/`), and prints
  what it removed.
- **`hobbes dispatch` repeats the pass and records the result.** The
  record's `retention` field lists what dispatch removed and any
  reasoning block still found (expected none). Every session file says
  that recorded sessions are evaluation rows, never model training data.
- **`ttt.units.units_from_git` skips** every commit the dispatch
  identity authored and every path under `docs/calvin/sessions/`.
- **Register:** C-125 amended; C-129 added (the guard's reach: not the
  merged tree).
- **Tests:**
  - `PurgeDoerState`;
  - the live session test (the state is gone after, and the launcher
    says so);
  - the default command's flag;
  - dispatch's retention record;
  - `units_from_git` over a real repo.

## 0.1.21-beta — 2026-09-12 (the Calvin harness, ADR-107)

**Patch: a live session reaches only the hosts it names, and Claude Code
runs inside it.** `hobbes dispatch` then stacks the doer, the gate and
a per-session log on the environment. Checked with no spend.

- **`hobbes-session --egress HOST`.** The session runs on its own
  podman `--internal` network, which has no route off the box.
  - An egress proxy container sits beside it, on that network and on a
    custom `hobbes-egress` bridge. It tunnels CONNECT to the named
    hosts alone, answers 403 to everything else, and logs every
    decision to `<session>/egress.jsonl`.
  - The launcher waits for the proxy before the session starts, and
    removes both after it.
  - `--egress` is exclusive with `--network`.
  - The proxy is `hobbes-proxy egress` (`go/internal/egress`). C-41 is
    narrowed.
- **Claude Code as the session's doer.**
  - `--claude-bin` mounts the host's binary read-only, without a
    relabel.
  - The token (`CLAUDE_CODE_OAUTH_TOKEN`, from `claude setup-token`) is
    passed by name, so it is never in an argv or a dry run.
  - `--strict-mcp-config` keeps the repo's own `.mcp.json` out.
  - Auto-update and nonessential traffic are off.
  - A live run without a binary, a token or a route is refused before
    the container starts.
  - The implementer's default command carries `--max-turns`.
- **`--claude-cred` is withdrawn, with a refusal that says why.** It
  mounted `~/.claude` at `/root/.claude`, but the session's `HOME` is
  its own directory, so the mount was never read. Had it been read, it
  would have handed the doer every host transcript. The reviewer
  session (`hobbes review`'s soft verdicts) now passes
  `--egress api.anthropic.com`.
- **`hobbes gate --map derive`** (`gate.derive_map`, `map_files`). The
  blind-spot map is read from the parent's graph by calvin-m0-gate
  WP-17's rule, over the partition or else the diff's files.
  - A created file is read at its directory's files at the parent.
  - The graph is named by its SHA, so the record stays byte-identical
    and holds no path of this machine.
- **`hobbes dispatch`** (`hobbes.run.dispatch`). One task goes to Claude
  Code under the whole stack:
  - the ingest must be at the parent;
  - the brief states how the session works;
  - the harvested branch is gated, and verified unless `--no-verify`;
  - one log file per session goes to `docs/calvin/sessions/`, with a
    review block the developer fills;
  - the full record goes to `<session>/dispatch.json`;
  - exit 0 clear, 1 blocked or verify failing, 2 refused, 3 nothing
    harvested.
- **Register.** C-41 narrowed; C-124 superseded (the keyed rounds are
  closed); C-125–C-128 added. ADR-107.
- **Tests.**
  - The egress package: parse, tunnel, refuse, log.
  - The sandbox plan and the session launcher: dry run, withdrawal,
    refusals.
  - A **live** route test: a real session behind the real proxy gets
    200 from the allowed host, 403 for another port, and no route
    without the proxy.
  - The derived map, and dispatch end to end against a stand-in
    session.

## 0.1.20-beta — 2026-09-11 (Calvin M0-Gate, WP-18c)

**Patch: an arm-O session no longer holds the repo's future.** Calvin
M0-Gate WP-18c, found by WP-21 at key 1 (D-x); checked with no model.

- **The defect.** The local harness launched arm O's session from the
  owned clone, which holds the repo's full history. The session
  therefore held every commit past the key's parent, the key's own
  gold included, and the box policy allows `git log` and `git show`.
  - WP-21's key 1 ran `git log --all --grep=…`, then `git show` on its
    own key, and wrote gold's lines.
  - Four of rounds 1–2's ten Go O sessions had done the same.
- **The fix (`harness.session_repo`).** A session now starts from a
  repo cut at the key's parent: `git clone --no-local --single-branch
  --no-tags` from a branch at the parent, `origin` removed, reflogs
  dropped.
  - **Checked at the object level:** no commit that is not the parent
    or its ancestor, no remote, no alternates file, no path back to
    the owned clone.
  - **After the session,** its branch is fetched back into the owned
    clone and the cut repo removed. The gate, the verifier,
    `gold_tests` and recall still read the owned clone, host side.
  - **The repair turn** resumes on a repo cut at O's own commit, seeded
    with the unit's own parent graph.
  - **Sessions roots:** each session gets its own, so `/sessions` in
    the container shows no other session's transcript.
- **Registered:** C-124 (*partial*) — the container keeps the model
  endpoint's network, so upstream history is out of the repo but not
  out of reach.

## 0.1.19-beta — 2026-09-11 (Calvin M0-Gate, WP-18b)

**Patch: the gate's repair message names what a blocked name nearly
was, with signatures, not an unrelated body (gate v2).** Calvin
M0-Gate WP-18b, found by WP-20's pre-flight (D-w); checked with no
model.

- **The defect.** On a near-miss name nothing declares
  (`awkTokenizeRune`), the message showed "the form of a declaration":
  the binding directory's most-called function, an unrelated 110-line
  body (`extractColor`). That rule was built for a declaration the
  model is asked to write. At the gate it only picked a big function.
- **The fix.**
  - A blocked `invented` or `near-miss` name now lists the declared
    names nearest to it: the grounder's own nearest names, resolved
    to their symbols (same file first, then the package; five at
    most), each with its signature line.
  - A declaration's form appears only where the diff itself declares
    the blocked name, but where the reference cannot bind. It stays
    capped at 4,400 bytes.
  - The record gains `nearest_declared` and `rules.message` and
    stamps `gate_version` 2. Nothing else in the record moves: every
    verdict, class, row and site reads as before.
- **The Calvin driver** (bench tooling): `o-units` rows now carry
  - `recall` read at the unit's own repo pin (`--recall-upper`, else
    the unit's `recall_upper`, else gitleaks' as before; D-u);
  - §2.5's `gold_tests` and `turns_to_first_edit` (D-v);
  - `verdict`, which reads `empty` for a session that left no diff —
    neither pass nor blocked — with `verdict_gate` beside it, and
    `verdict_after` on repair rows.

## 0.1.18-beta — 2026-09-11 (Calvin M0-Gate, WP-18)

**Patch: `hobbes gate`, the linker on a finished diff.** Calvin
M0-Gate WP-18; built and checked with no model.

- **The command.** `hobbes gate --diff <patch> --parent <sha>` runs
  grounder v3 over any finished diff at its parent. It needs no
  template: the diff is read through a one-hole template.
  - **The split:** each name-absence NULL is looked up in the unit's
    blind-spot map (`--map`). A file-grain unresolved-site count
    never routes; it is context.
  - **The partition:** every touched file is checked against the
    unit's write partition (`--partition`, else the map's), at file
    grain, under `--partition-rule`:
    - `reach`, the default — the gate judges ingested code. A file
      that is not code (docs, man pages, build files, a language
      Hobbes does not ground) and a code file created beside a
      partition file are listed in `partition.reached`, not blocked.
      A write into an existing code file outside the partition
      blocks.
    - `exempt` — allows test-support paths only.
    - `strict` — allows nothing.
  - **The verdict** is *clear*, or *blocked* with the classes that
    fired: invented, near-miss, arity, undeclared-type,
    import-outside, unimported, malformed and partition. `malformed`
    now also covers a diff that does not apply at the parent.
  - **Not blocking:** `unknown` (a NULL in a region Hobbes cannot
    see) is reported and never blocks. `new` cannot arise from a
    finished diff; if it ever does, it is routed.
  - **The record** (`<diff>.gate.json`) is stamped with the gate,
    grounder and Hobbes versions and the sha256 of every input, and is
    byte-identical on rerun. The diff is also applied with `git apply`
    and the gate's own reading is checked against the result.
  - **Exit codes:** 0 clear, 1 blocked, 2 bad input.
- **The repair turn.**
  - `hobbes gate --message` prints a blocked record as a repair
    message: the classes, every site, the files outside the
    partition, and a declaration's form where a blocked name has one.
  - The agent loop gains `--resume-transcript`: a recorded session
    resumed with one more user message, its read tickets and repeat
    guards rebuilt from the transcript.
- **The Calvin drivers.** `calvin_probe.py o-units` and `o` gain:
  - `--gate` — post hoc (O+gate);
  - `--gate-repair` — one bounded resumed turn on each blocked row
    (O+gate+repair);
  - `--recorded DIR` — gate a prior run's sessions; O is never re-run.

  `o-units --withhold-manifest` sends O the task text alone.
- **Registered:** C-121 (`unknown` is advisory), C-122 (the partition
  at file grain), C-123 (the split's grain and classes); all
  *surfaced*.

## 0.1.17-beta — 2026-09-11 (later still, the fifth)

**Patch: the grounder checks a Go call's argument count and a
qualified name against the repo's own declarations (grounder v3).**
Calvin M0-Go round 2, WP-14b; checked by replay with no model.

- **Two new NULL classes.**
  - **`arity`:** a call bound in the graph whose argument count
    differs from the callee's own declaration.
  - **`undeclared-type`:** a qualified reference into one of the
    module's own packages that the package does not declare.

  The callee's parameters are read from lane A's own parse of its
  declaration, on demand; nothing is added to the graph, and the
  artifacts are byte-identical. On WP-10's seven declarations that did
  not build, 3 now raise one of these NULLs (arity 2, undeclared-type
  1); the unused imports stay the compiler's. Gold still grounds at
  0 NULL on 20 of 20.
- **Every doubt abstains.** The rule skips variadics, generics, method
  values, interface dispatch, a call whose sole argument is itself a
  call, callees outside the module (C-118), and a callee whose own file
  the same diff edits (C-119).
- **`malformed`.** A post-image carrying the render's line-number gutter
  reads as its own class with a reason, instead of silently grounding
  to zero references (C-120).

## 0.1.16-beta — 2026-09-11 (later still, the fourth)

**Patch: the Calvin adapter's protocol v0.6, and a benchmark no tree
runs no longer fails a diff.** Calvin M0-Go round 2, WP-14; checked by
replay with no model.

- **Adapter protocol v0.6**, superseding v0.5.
  - **The build row in the repair.** After a declaration is placed and
    grounded, the verifier's build row (`go build`, `go vet`,
    generation; contained, no tests) runs. A compile error naming the
    declaration's file goes back in the one repair, beside the
    grounder's NULLs, trimmed to the lines naming that file. WP-10's
    seven declarations that did not build now build on a scripted gold
    replay (7/7).
  - **The sibling whole.** The declaration hole shows its sibling whole,
    capped at 4,400 bytes (the gitleaks `rules/*.go` 95th percentile)
    instead of 12 lines.
  - **One budget.** A key gets at most `--budget` model calls in either
    arm: confirmations, fills and repairs in T, turns in O
    (`t-units --budget --verify-build`, `o-units --budget`). An arm at
    its budget stops and its row is scored as it stands.
  - **Record fixes.** A recorded fill is a copy, not a reference the
    loop later mutates. `usd_loop` counts the repair exchanges.
- **`not-run` no longer fails a diff.** A guard-selected test that runs
  on neither tree (a Go benchmark under plain `go test`) reads
  `not-run` and decides nothing. A test that ran without the diff and
  not with it still reads `removed`. Round 1's 20 golds are unchanged;
  one fresh gold moves from fail to pass, matching its own `gold_tests`.
- C-116 (the budget cuts a row) and C-117 (the sibling cut at 4,400
  bytes) registered; C-114 amended (the one repair reads build errors
  too).

## 0.1.15-beta — 2026-09-11 (later still, the third)

**Patch: `hobbes verify` no longer reads `pass` on a change no test
exercised.** Calvin M0-Go round 2's audit (WP-11a) re-scored round 1's
31 pass rows: 19 had reached no executed guarding test.

- **`vacuous`, a verdict of its own.** A diff that builds, selects
  tests and fails none, but where no guarding test actually executed
  (every selected id uncollected, skipped, not run, errored or
  unsupported), reads `vacuous`, never `pass`. The record carries
  `guarding_tests_executed` (count and ids); guards count by origin
  `guard` or `touched`, not `generate`. The order is `build-fail` →
  `no-tests` → `fail` → `vacuous` → `pass`, so C-93's `no-tests`
  (nothing selected) is unchanged.
- **`gold_tests`, the gold's own test changes on top of the diff.** A
  caller holding a gold diff (the Calvin driver) can apply its test-file
  hunks, with the fixtures beside them under `testdata/`,
  `__fixtures__/` or `__snapshots__/`, on top of an arm's diff and
  verify that. A `gold_tests` pass makes a row `pass` even where no
  guard executed. Its failures split into `fail`, `build-fail` (with
  Go's `undefined:` names) and `conflict`. Checked by a gold control:
  gold's own non-test hunks with `gold_tests` on top read `pass` on 7
  of 7 of round 1's keys. C-115 (fixtures only from those three
  directory names).

## 0.1.14-beta — 2026-09-11 (later still, the second)

**Patch: the grounder holds a Go fill to the repo's world (grounder
v2), and the adapter gets one bounded declaration repair (protocol
v0.5).** WP-8 found that every declaration the loop placed was written
against another project's API; these changes are its fix. Both were
checked by replay with no model.

- **Grounder v2, the world check.** A Go fill's imports must be the
  standard library (go1.26.5's `go list std` less `internal` and vendor
  paths, 176 packages, pinned as `GO_STDLIB`), a module the governing
  `go.mod` requires at the parent, or a directory of the module itself
  holding Go files. Any other import line in an edited range is an
  `import-outside` NULL. A qualifier on a call, selector or type that
  no import may bind is an `unimported` NULL, and every doubt abstains.
  The rule rides in each record's `world` block. WP-8's 9 placed
  declarations each raise at least one NULL, while gold still grounds at
  0 NULL, HSR 0, and 20/20 byte-equal.
- **Adapter protocol v0.5**, superseding v0.4. A NULL inside a placed
  declaration's body goes back once as a repair of the same declaration
  hole: one exchange, and no validation repair after it. The
  declaration hole shows a sibling's form, a function of the same kind
  from the binding directory with its file's package clause and
  imports. The loop's site record reads the grounder's refused list, so
  a refused declaration reads `refused`.
- Register: C-109 (a required module's package unchecked), C-110
  (unaliased import names read by convention), C-111 (build tags
  unread), C-112 (syntax errors unclassed — **unsurfaced**, debt), C-113
  (the world check is Go only) and C-114 (the declaration repair bounded
  to one exchange) registered; 114 entries, 88 active, 24 lifted, 2
  superseded.

## 0.1.13-beta — 2026-09-11 (later still)

**Patch: what the Calvin adapter offers after a NULL, and what it
refuses in a fill (protocol v0.4).** These came from WP-6's run on
M0-Go units and were checked by replay with no model.

- **Adapter protocol v0.4, the declaration hole**, superseding v0.3
  (v0.3's pattern reading stands). When T-loop's NULL round-trip meets
  a name that a call site writes and nothing declares (class `new` or
  `invented`, in no parent-graph module), it offers one hole per
  (name, scope). The answer must declare that name in a file of the
  binding directory with a body naming it. The declaration joins the
  template and the call site is re-grounded. A near-miss is still
  re-asked in the hole that wrote it (C-106). A declaration outside
  the write partition is placed and recorded, never refused, on Max's
  decision (C-107). Replayed on WP-6's records: 11 of 11 NULL sites
  closed with scripted gold declarations, and none opened.
- **The gutter guard.** A SIGNATURE or BODY fill carrying the render's
  line-number gutter is refused and named in the repair, and the
  grounder refuses it too; WP-6's three such fills are refused, 3 of 3.
- **The grounder's `scope` field.** Every NULL row carries the Go
  package directory it binds in, plus the type for a typed receiver.
  The declaration hole reads it; for a non-Go name or an
  `after_symbol` placement the directory is not checked (C-108).
- **Fix: loop closure keyed on (hole, term).** v0.3 keyed it on (hole,
  term, class), so a NULL whose class changed counted as closed and
  opened at once. No WP-6 row was affected.
- Register: C-106, C-107 (*surfaced*) and C-108 (*partial*) registered;
  108 entries, 82 active, 24 lifted, 2 superseded.

## 0.1.12-beta — 2026-09-11 (later)

**Patch: what the Calvin adapter accepts from an orchestrator (protocol
v0.3), and a metered arm-T driver.** Both came from the first model run
on M0-Go units (WP-5: five keys, Haiku 4.5, $1.17).

- **Adapter protocol v0.3**, superseding v0.2 (Max's decision). A
  pattern of `"unchanged"` on SIGNATURE or BODY, or `"unchanged"`/`"no"`
  on ANCHOR_CONFIRM, is accepted on the first pass. Each hole it covers
  is filled as unchanged or no and listed under `by_pattern`. A pattern
  never rewrites or confirms, an explicit fill wins, and a refusal by
  pattern counts as silence does. The validator reads a refused
  pattern's holes as `missing`, so the repair names them rather than
  losing them. `protocol_version` is stamped on every exchange and
  arm-T record. Refused patterns had cost 7 of 22 calls and 36% of the
  run's spend; replayed with no spend, 4 of the 5 such exchanges
  validate on the first pass (C-105).
- **`calvin_probe.py t-units`**: arm T over a set of units with per-key
  and total dollar caps, a usage ledger per key, `--key-name`,
  `--sampling`, `--rta-key` and `--verify`. `run_t(rta=)` hands the RTA
  key to both groundings. Rows carry `files_changed` and
  `rfe_changed`, since a body written back byte for byte is not a
  changed file.
- Register: C-105 registered (a pattern answers many holes with one
  judgement, *surfaced* by `by_pattern`); 105 entries, 79 active, 24
  lifted, 2 superseded.

## 0.1.11-beta — 2026-09-11

**Patch: Calvin's derive layer reads Go (the M0-Go round).** Three
changes in what the grounder, the verifier and the template draw. All
three were run on gitleaks' 20 M0-Go gold diffs with no model.

- **Grounder v1 on Go** (`hobbes ground`). Go's universe scope is pinned
  from go1.26.5, and a bare name binds a local, then the package, then
  the universe; it never binds a method. A member is judged when the
  syntax states its receiver's type (rule 1), and an interface method
  binds to the interface (rule 2; implementers are recorded, never
  bound). Every judged reference carries a density, `dense`, `sparse`
  or `absent`, beside its class. Four defects are fixed: a bare call
  could bind a method; builtins were checked before the package; an
  import alias beat a shadowing local; a missing method on a type over
  a basic type abstained instead of NULL. Gold run: 0 NULL, HSR 0,
  `unknown-receiver` 53 → 5, poison 50/50. C-91 amended.
- **The Go verifier** (`hobbes verify`, harness v2; ADR-100 amended).
  The repo's `//go:generate` regenerates a generated file on both
  trees rather than applying it, and is a test row where its import
  closure reaches the edit. A failing generation is retried up to
  three times, with each attempt recorded (C-103). Tests run by name
  at symbol grain and whole at package grain; `go build` and `go vet`
  are build rows (a `P2F` there is `build-fail`); `go test -list`
  gives `uncollected` and `removed`. The Go module cache is now
  mounted read-only over the cache root's rw mount
  (`containment.Plan.ro_cache`, C-92). `calvin.box.policy` allows
  `go generate*`. Gold run: 20/20 pass on two passes, `P2F` 0,
  `all_contained`.
- **Template v2** (`build_template(version=2)`, opt-in). An anchored
  symbol with more than 20 in-repo callees opens each callee as a
  signature-line confirmation instead of a body (C-104). v1 stays the
  default and rebuilds byte for byte, and the `hobbes template` CLI
  builds v1. At A2, round 2's open holes fall 6,973 → 1,866.
- Register: C-102 (lane A's Go local bindings skip a function's
  `var ( … )` group, *partial*), C-103 and C-104 registered, C-91
  amended; 104 entries, 78 active, 24 lifted, 2 superseded.

## 0.1.10-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes draws on a Gradle repo (C-67).** A
Gradle unit gets scip-java's javac plugin from Hobbes's own init script
— on each JavaCompile task's processor path, the way the oracle lane
attaches its plugin — and its shards are aggregated by `scip-java
aggregate`; scip-java's own Gradle plugin, which adds the jar to the
`compileOnly` configuration, is no longer in the path, because a build
that has resolved that configuration at evaluation time refuses the
add (Severed-Chains, one repo in four on the 2026-08-29 random draw,
had fallen to lane A whole). The image extracts the plugin jar and its
`--add-exports` list out of the pinned launcher at build. Maven is
untouched (ADR-096 amended).

- Severed-Chains re-ingested contained: capture 0.0% → **100.0%** of
  52,209 sites; regraded against its standing javac key at 100.0%
  precision, recall **23.5% → 60.8%** (29,793 edges, 0 contradicted,
  poison 0 falsely confirmed), every edge semantic. spring-petclinic's
  Gradle build through the same route beside its Maven grade.
- Under Gradle the dependency-coverage line is answered from what the
  build resolved (a task the init script registers writes scip-java's
  own `dependencies.txt`), since the aggregator alone names no
  third-party package; an external node is still named by its Java
  package. A build that replaces `compilerArgs` after configuration is
  refused with its own last words quoted. Kotlin sources are not
  compiled under the plugin (they were not indexed before either).
- Bench: `oracle grade` prints `recall-collapsed` beside the standing
  line (ADR-089 amended); the Java key's names are owner-qualified
  (H-23). Neither moves the version (ADR-103).

## 0.1.9-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes refuses to stage and what it says
(C-66).** The Java resolve pass's stage (ADR-097) was meant to hold no
source the build compiles; the walk that built it copied `.mvn/`,
`gradle/` and `buildSrc/` whole, past both the JVM-suffix filter and
the pruning, so a source hidden under `.mvn/` or `gradle/` reached the
networked pass — found by the 2026-09-10 baseline review
(`docs/reviews/2026-09-10-baseline.md`). One walk and one rule now:
lane A's pruning in every directory, `.mvn/` the one dot-directory
entered, a JVM source left out wherever it sits except below
`buildSrc/`, whose sources are the build logic itself (the one
exception, unchanged). The ingest notice says so: "a networked pass
whose stage holds no application source (build logic under buildSrc/
excepted)".

- Tested at three levels: the file list, the resolve plan's stage, and
  the contained canary, which now plants `.mvn/Hidden.java` and reports
  the resolve pass through a sentinel in the Maven cache — the fourth
  probe's `Phoned` could never see that pass, whose stage is discarded
  before the index runs. Shown to fire under the old walk.
- `buildSrc/build/` and `buildSrc/.gradle/` no longer ride either.
- Bench tooling beside it (unversioned): the callee-shape bucket's
  identity fixed (H-22) and the two cells re-measured.
- Register: C-66 surfaced again; 101 entries, 75 active, 24 lifted, 2
  superseded.

## 0.1.8-beta — 2026-09-10 (the versioned baseline)

**Patch: a change in what Hobbes draws (C-101).** The Java resolve
pass's stage (ADR-097) held "no source", where source meant `.java`; a
Maven build with Kotlin sources compiled them against Java that was not
on the stage, failed, and the unit fell to lane A's syntactic tier —
surfaced by the degradation record, found when every Hobbes cell was
regraded on one build for the comparative graphics (Max, 2026-09-10).
The stage now holds no JVM source the build compiles (`.java`, `.kt`,
`.scala`, `.groovy`; `buildSrc/` stays), and the Maven resolve pass runs
the repo's `mvnw` when it ships one — scip-java's index pass runs that
wrapper, and only the networked pass can fetch its distribution into
the cache (petclinic had passed on a warm cache alone); `MAVEN_USER_HOME`
names that cache, since the Java wrapper ignores `$HOME`.

- spring-data-elasticsearch: the resolve pass succeeds again; the cell
  is regraded semantic (its record's 2026-09-10 block).
- **Every Hobbes oracle cell regraded on this build** against its
  standing key — the comparative graphics and `docs/comparative/tables.md`
  now state the Hobbes version per cell (`bench/oracle/report/render.py`
  reads it from the record's last regrade heading).
- Register: C-101 registered and lifted; 101 entries, 75 active, 24
  lifted, 2 superseded.

## 0.1.7-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes draws (C-100).** TypeScript's ESM- and
CJS-flavoured sources, `.mts` and `.cts`, are discovered: they were on
neither lane A's extension list nor the helper's, so such a file was
not a module, its calls were not counted, and scip-typescript's index of
it (the file is in the tsconfig's program) had nothing to join to —
absent without a degradation record. Found by the callee-shape bucket
of cheerio's miss set (`docs/oracle/oracle-misses.md`), which answered
Max's question about the recall gap between a `tsc` key and a
`tsc`-based indexer: at symbol grain the indexer emits 98.8–100% of the
function declarations the key names; the gap is the key's overload
grain (one pair per signature) and targets below the symbol floor.

- cheerio (the zone's own `tsc` 6.0.3): 2,682 → 2,688 edges, 2,622 →
  2,628 confirmed, 0 contradicted; the six `scripts/fetch-sponsors.mts`
  rows recovered; every function-declaration target on the cell drawn
  (1,911/1,911 collapsed pairs). zod does not move (no such file).
- Both lanes: `tsextract/extract.mjs`, `hobbes.extract.tssource`,
  `hobbes.extract.tail`; the grounder, the agent policy's test-command
  map and the harness's vitest rule take the same two extensions.
- Register: C-100 registered and lifted; 100 entries, 75 active, 23
  lifted, 2 superseded.

## 0.1.6-beta — 2026-09-10 (later)

**Patch: a change in what Hobbes draws (the C-98 lane asymmetry
closed).** 0.1.5-beta left the two lanes reading a solution-style
`tsconfig.json` differently: lane A typed a file by the referenced
project that includes it, lane B still indexed the zone under a
generated config written over the solution file (C-90's technique).
Now lane B asks the TS helper for the same zone map (`--zones`, the
compiler's own reading) and passes scip-typescript the referenced
projects that claim the zone's files, each under its own config, plus
a generated config for the files none claims — written *beside* the
solution file, which stays intact for any project that `extends` it.
One rule, one implementation, both lanes; if the helper's map is
unavailable the zone falls back to the old shape and the ingest says
so.

- hono: 768/768 unchanged, one edge moved from the syntactic to the
  semantic tier (727 semantic confirmed), lane agreement 4,332 →
  4,336 both-resolved sites with the same one line-grain disagreement;
  lane B produces 9 fewer module edges (1,483 → 1,474): a file no
  referenced project claims is its own program now, in both lanes, so
  its references into a claimed project's files take the cross-program
  shape C-12 registers.
- **ADR-105:** a lane B provider is a pinned batch program with a
  stated version and a tier stamp, never a language server — P13,
  stated in §3.2 and in §3.7's first step for the next language. No
  code moves.



**Patch: a change in what Hobbes draws (C-98 lifted).** Under a
solution-style `tsconfig.json` — `files: []` and project `references`,
hono's root, any `tsc -b` monorepo — the TS helper built the zone's
project from the solution file, which carries no compiler options: the
checker ran at its ES5 defaults, `Array.flat` was unknown, a receiver
reached through a newer lib was `any`, and every lane-A observation that
needs the type was absent — callee, origin and ADR-104's abstention
alike. The helper now resolves a file under a solution config to the
referenced project whose inputs include it, by the compiler's own
reading of the configs (references followed transitively inside the
repo, the first named claimant wins) — the lane-A analogue of C-90's
rule. A file no referenced project claims runs under the default
options and the ingest says so (`tsconfig-unclaimed`, one degradation
line per solution config, the files sampled).

- hono regraded against its standing key: 767/768 → **768/768
  (100.0%)**, 0 contradicted; 15 sites on `src/` are typed now and
  abstained as `union-member` (C-97). The claim page's one named
  exception is quic-go.
- Found on the way and fixed in both lanes (**C-99**, registered and
  lifted): a tsconfig with `references` and *neither* `files` nor
  `include` was taken for a solution config — the compiler's default
  include is then the whole directory, so hono's six
  `runtime-tests/*/tsconfig.json` zones had been indexed under the
  generated config instead of their own options.
- Facts schema unchanged (v5); `errors` gains a stage. Lane agreement
  on hono unchanged.

## 0.1.4-beta — 2026-09-09

**Patch: a change in what Hobbes draws (ADR-104).** A member call on a
union-typed receiver whose members do not share one declaration of that
member — `n: A | B`, both overriding, `n.render()` — no longer draws an
edge to the first member's method. scip-typescript and lane A's own
checker both named that member at semantic certainty, and the compiler
names a member too; none of them is the static answer, which is "one of
these". The TS helper (facts v5) types the receiver and abstains, the
evidence join vetoes lane B's occurrence at that site, and the tail
counts the site under a new class, **`union-member`** (TS/JS only;
`list_blind_spots` and the ingest summary gloss it). Registered as
**C-97**; C-58 gains its TypeScript face.

- ajv regraded against its standing key: 1,375/1,378 → **1,410/1,410**,
  now contained; hono 767/774 → **767/768**. The row left on hono is a
  site lane A cannot type at all: its root `tsconfig.json` is a
  solution-style config that leaves the helper's checker with no
  compiler options — registered as **C-98**, not yet lifted.
- The fixture `minits/src/union.ts` holds the shape; the proxy's tail
  glossary carries the class (image rebuilt).

## 0.1.3-beta — 2026-09-09

The first stated version, so this entry says what 0.1.3-beta *is*
rather than what changed. *beta*: graded, not stable — the schema and
the tool surface still move (ADR-103 §5).

**The knowledge layer** — a complete deployment on its own (ADR-092
phase 4): `hobbes ingest` builds `.hobbes/derived/` from a repo on
disk with no model, and `hobbes-proxy serve --knowledge-only` serves
six read-only tools over it from the sandbox image (ADR-087/094).

- Six languages, each a tree-sitter syntax provider joined by one
  range join to a pinned SCIP indexer: Python, TypeScript/JavaScript,
  Go, Rust, Java, plus Terraform/HCL structure (architecture §3.8).
- Every edge carries a tier (`semantic` / `syntactic`) and its evidence
  line; every site nothing resolved is counted and classed, never
  drawn (ADR-045/047).
- Everything that executes repo-authored code runs in the one sandbox
  image; `--uncontained` is disclosed and stamped (ADR-092, C-64).
- The constraint register: 96 entries, 74 active, each naming where a
  user meets the limit (`docs/constraints/`).
- Compiler-graded by the oracle lane: 0 falsely confirmed of 99,824
  seeded wrong edges across 19 cells; every compiler-graded cell at
  100% precision-against-oracle except three named ones
  (`docs/comparative/`, ADR-089/101).
- Every artifact and every knowledge answer states which Hobbes
  built it: now version and commit (ADR-094, ADR-103).

**The agentic layer** — sessions in rootless Podman under a Go policy
chain (deny overrides allow; allow | deny | escalate), the tool proxy
and flight recorder, `hobbes plan` / `hobbes run` deriving per-unit
context and policy from the graph (ADR-051/054), `hobbes review` at
the concept level with compiled invariants, `hobbes verify` (ADR-100).
Under test; no benchmark claim earned (architecture §6.2).

**Not in the version:** the oracle lane and its foreign converters,
the benchmark harness, Calvin, the test-time-training and Atlas-0
instruments — `bench/`, internal testing.
