# The register's history — dated notes, newest first

Moved out of [`README.md`](README.md) on 2026-09-19 (the 2026-09-16
top-level review's docs item): the index keeps the register's *current*
tally, and this file keeps how it got there. A count inside a note is as
of the note's date. Append a new note at the top; never edit an old one.
The per-version record is [`CHANGELOG.md`](../../CHANGELOG.md).

C-168's remainder read, and the entry corrected a second time, 2026-09-20 (no version; Max: route a; no entry added):
- **Two claims were wrong.** "A `.d.ts` Hobbes keeps no symbol for":
  `src/index.d.Component` is a class symbol, and 1,241 confirmed Preact
  rows land in `.d.ts` symbols. And the 377 JSX rows were filed as a
  constructor's question; every one is a tag naming a test-body local
  class, where the facts carry no reference (C-58's floor).
- **Two facts were added, read in the image:** the index emits no
  occurrence at `super`, and at a JSX tag it names the class, never
  `<constructor>`. A `Provider` line (P9) now says so.
- **A rule was measured and not built:** the `extends`-chain walk, 104
  rows confirmed at 0 contradicted on four cells, 0 on Preact
  (`oracle-grading.md` §10.26). Tally unmoved: 168 entries.

C-23's yarn branch, 2026-09-20 (0.2.60-beta; a defect, no entry added or moved):
- **C-23 said more than the tree did.** Its ADR-050 narrowing reads "v1
  `yarn.lock` → pinned classic yarn … provisioned". From ADR-092 (lane B in
  the image) to 0.2.59-beta that branch could not run on a contained box: the
  argv carried the host's `corepack` path into the container. It was
  surfaced — an `extraction_errors` row and a WARNING per zone — but as
  "dependencies not provisioned", which read as the repo's. Fixed at
  0.2.60-beta (the image's `corepack`, by name); the entry's words are true
  again and are left as written. Tally unmoved: 168 entries.

C-165 corrected and narrowed, 2026-09-20 (0.2.58-beta; Max: route a; no entry added):
- **C-165 corrected.** The entry said Hobbes could not tell you "whether
  an edge from JavaScript into a third-party package is right" and named
  a provisioned cell as its lift. The cell was drawn and graded
  (`oracle-grading.md` §10.24, cypress-io/github-action): 154/154 with
  its 177-package tree on both sides and the same 154/154 without, the
  graph identical. No `calls` or `uses` edge targets a package on any
  TS/JS cell, so the edge the entry named is never drawn; the limit is
  that a third-party call is stated at module grain (`imports →
  ext:<pkg>`) and the key's external pairs (413 here) meet no Hobbes row.
- **C-165 narrowed (surfaced).** One JavaScript cell of four now has its
  dependency tree; the `javascript` verification row says so. Counted
  beside it: `npm ci` refused three of the four lockfile-bearing
  JavaScript repos the draws met (C-23). Tally unmoved: 168 entries.

C-168 corrected and narrowed, 2026-09-20 (0.2.57-beta; ADR-142, route b):
- **C-168 corrected.** The entry as registered on 2026-09-19 said the
  join drew a `uses` edge at every `new` and that `who_calls` worded it
  wrongly, and it counted ajv 107, zod 110, hono 78, xmpp.js 104 and
  Preact 570. Those are each cell's whole `static→class` miss class, not
  its constructions: read row by row, **Preact's 570 hold no `new` at
  all** (193 `super(…)`, 377 JSX tags), and at a real construction the
  join drew **nothing** — scip-typescript names `<constructor>` at the
  constructor's own line, which starts no symbol, so the reference fell
  below the floor (C-58). The `uses` edge described sits at the import
  line. `oracle-grading.md` §10.23 carries the read.
- **C-168 narrowed (partial).** A construction is drawn `calls` where
  the index names a constructor at exactly the `new` token — to the
  class that declares it, or to an ES5 constructor function itself.
  Left: `super(…)`, a JSX tag whose component declares no constructor,
  a class that declares none (counted per ingest as `ts_named_class`),
  and a token the index does not resolve. xmpp.js recall 66.4% → 81.2%,
  ajv 63.5% → 67.5%, hono 55.0% → 59.7%, zod 45.1% → 45.8%; 0
  contradicted on every cell. Counts unchanged (no entry added).

C-167 narrowed, 2026-09-19 (0.2.56-beta; ADR-141, route a):
- **C-167 narrowed (partial):** lane A follows `module.exports =
  require("<literal>")` to the required module's export, so a call
  through a CommonJS re-export is drawn — `syntactic`, since
  scip-typescript names the site with a leaked local. Left: that tier,
  and a re-export through anything but a literal `require`. Express
  recall 22.4% → 65.3%, 0 contradicted. Counts unchanged.

C-167 traced, 2026-09-19 (sixth session; ADR-141 proposed, no version move):
- **C-167 (partial, unchanged in status):** its *Because* is traced —
  both lanes stop at the re-exporting file's `export=`; scip-typescript
  names the site with that file's document-local symbol (a `Provider`
  line added). Its *You find out* corrected: the sites were counted
  `nested-decl`, not `unclassified`. Counts unchanged.

C-165 narrowed, C-167 and C-168 registered, 2026-09-19 (0.2.55-beta; ADR-140 step 5):
- **C-165 narrowed (surfaced):** JavaScript is graded on three repos
  (§10.22), none with its dependencies installed — that is what is left.
- **C-167 registered, partial:** a function reached through a CommonJS
  re-export of `module.exports` draws no edge (Express's 652; untraced).
- **C-168 registered, partial:** `new F()` is drawn `uses`, not `calls`,
  in TS and JS; `who_calls` words it as no call site.
- Counts: 168 entries, 123 active, 95 surfaced, 24 partial, 3
  unsurfaced, 1 n/a; 28 lifted.

C-166 registered and surfaced, 2026-09-19 (0.2.54-beta; ADR-140 step 4's preparation):
- **C-166 registered, surfaced:** neither lane reads a `jsconfig.json`;
  the ingest now says so once per such file (`jsconfig-ignored`).
  Measured on Preact, key only: 120 of 22,804 sites resolve differently
  under its jsconfig. Counts: 166 entries, 121 active, 95 surfaced, 22
  partial, 3 unsurfaced, 1 n/a; 28 lifted.

C-165 registered and surfaced, 2026-09-19 (ADR-140, 0.2.53-beta):
- **C-165 registered, surfaced:** no JavaScript program has been graded;
  `verification.py` had pinned the `javascript` row as a copy of
  TypeScript's (4 repos). Measured: 0 of the five TS/JS cells' 15,167
  confirmed edges touch a JavaScript file. The row is 0 repos,
  `unverified`, with its reason; §3.8 splits TypeScript and JavaScript.
  Counts: 165 entries, 120 active, 94 surfaced, 22 partial, 3
  unsurfaced, 1 n/a; 28 lifted.

C-4 narrowed again, 2026-09-19 (ADR-139 accepted and built, 0.2.52-beta):
- **C-4 narrowed (still surfaced; no entry added):** a `usefixtures`
  string and an `autouse=True` fixture's name are looked up as a
  parameter is; autouse reach is kept apart (`through_autouse`) and said
  once. `-v` key: this repo 4,971, flask 1,238, attrs 118 pairs, 0
  missed, 0 wrong. Left: the returned value's type, a module
  `pytestmark`, a non-literal `autouse=`, and the abstentions. Counts
  unmoved: 164 entries, 119 active, 93 surfaced, 22 partial, 3
  unsurfaced, 1 n/a; 28 lifted.

C-4's figures corrected, 2026-09-19 (0.2.51-beta; ADR-139 proposed):
- **C-4 (no entry added, status unmoved):** the denominator statement
  names C-4's remainder instead of all fixture-injected reach
  (0.2.51-beta). ADR-137's key printed no `_`-named fixture; on the `-v`
  key nothing drawn is wrong and the missed pairs are this repo 3,962,
  flask 734, attrs 14, all `autouse` or `usefixtures`. ADR-139 measures
  reading both (0 missed, 0 wrong) and is proposed, not built. Counts
  unmoved: 164 entries, 119 active, 93 surfaced, 22 partial, 3
  unsurfaced, 1 n/a; 28 lifted.

C-142 narrowed, 2026-09-19 (ADR-138 accepted and built, 0.2.50-beta):
- **C-142 narrowed (still partial; no entry added):** a header C++ has
  claimed passes the claim on; the C walk knows the files C++ owns.
  ScummVM 629 → 273 `.h` read as C. **C-133 measured, unmoved:** the
  `-I` step is not built. Counts unmoved: 164 entries, 119 active, 93
  surfaced, 22 partial, 3 unsurfaced, 1 n/a; 28 lifted.

C-4 narrowed and surfaced, 2026-09-19 (ADR-137 accepted and built, 0.2.49-beta):
- **C-4 narrowed (partial → surfaced; no entry added):** a fixture a
  parameter names is a syntactic `uses` edge and test reach follows it;
  what is left is `autouse`, `usefixtures`, the injected value's type, a
  plugin's or an inherited fixture. 164 entries, 119 active, 93
  surfaced, 22 partial, 3 unsurfaced, 1 n/a; 28 lifted.

C-164 narrowed again, 2026-09-18 (ADR-136 accepted and built, 0.2.48-beta):
- **C-164 narrowed (still partial; no entry added):** the mint reads a
  definition row at a line R1 vacated even in a file that parsed clean —
  ScummVM's 260 are named, `minted.vacated` counts them, no graded cell
  moves.

C-164 read at scale, 2026-09-18 (ADR-136 proposed; nothing built, no version move):
- **C-164 amended (no entry added, no status change):** ScummVM's first
  ingest with R1 — 401 removals, none a false flag by the hand read, and
  a remainder the entry did not name: 260 of them are in files that
  parsed clean, where `clean-file` keeps the mint from naming the true
  definition, so it has no node. ADR-136 proposes the mint read a
  vacated line.

C-164 narrowed and partial, 2026-09-18 (ADR-135 accepted and built, 0.2.47-beta):
- **C-164 narrowed (unsurfaced → partial; no entry added):** a lane A C++
  function or method whose own name token the index reads as a reference
  to a macro or a data member is removed, and one whose extent holds
  another definition's row is re-read from the file's braces; counted in
  `graph.json`'s `lane_a_contradicted` and on the ingest summary. fmt 18
  removed, 1 re-read, wrong-caller rows 105 → 32 (the 32 the driver's
  grain), no right row moved, every graded number ±0 (§10.20). Left: no
  index, uncompiled code, shapes the two reads do not see. 164 entries,
  119 active, 92 surfaced, 23 partial, 3 unsurfaced, 28 lifted.

C-164 counted key-free, 2026-09-18 (ADR-135 proposed; nothing built, no version move):
- **C-164 amended (still unsurfaced; no entry added):** 18 misnamed lane A
  symbols on fmt (13 a macro's name, 5 a member initialiser's) and 2
  swallowing extents; 0 on args, cJSON and sqlite-vector. The index
  separates them by a reference at exactly the symbol's name token, not
  by its definition row and not by the name being a macro's. Simulated:
  fmt's wrong-caller rows 105 → 32 (the 32 are the probe's naming
  grain), 15 right and 58 lost, no agreeing row moved. 164 entries, 119
  active, 92 surfaced, 22 partial, 4 unsurfaced, 28 lifted — unmoved.

C-145 narrowed again, 2026-09-18 (ADR-134 accepted and built, 0.2.46-beta):
- **C-145 narrowed (still surfaced; no entry added):** a minted function
  or method whose body the file's own braces delimit is a scope, not only
  a target — `end_line` is the closing brace, the symbol says `extent:
  "braces"`, and the facts written inside it are drawn from it. fmt: 1,290
  of 1,436 lost callers re-homed, 1,218 to the caller clang names, none
  wrong, none that was right moved; args 15 of 15. No graded number
  moves, because no key reads a caller; the check is a driver over the
  key's caller names (§10.19), not a grade. Refused and counted: a
  preprocessor conditional in the body (34 on fmt), another function's
  line inside the match (19), a type, always. 164 entries, 119 active, 92
  surfaced, 22 partial, 4 unsurfaced, 28 lifted — unmoved.

C-164 registered, C-145's residual measured, 2026-09-18 (ADR-134 proposed; nothing built, no version move):
- **C-164 registered (unsurfaced)**, in `extraction-cpp.md`: a lane A C++
  symbol from an error-recovered parse can carry a macro's name
  (`GTEST_LOCK_EXCLUDED_`, 14 symbols on fmt), a member initialiser's, or
  the bodies of the definitions after it; 73 of fmt's 8,123 `calls`
  evidence rows name a wrong caller. Found by reading the key's caller
  names, which no grade reads. **C-145's residual measured:** 1,436 rows
  (17.7%) drawn from the module where clang names a function. 164
  entries, 119 active, 92 surfaced, 22 partial, 4 unsurfaced, 28 lifted.

C-163 registered and lifted, C-162 narrowed, 2026-09-18 (ADR-133, 0.2.45-beta):
- **C-163 registered and lifted the same day**, in
  `extraction-call-graph.md`: the join's claim was by `(file, line,
  name)`, so a matched call hid every other reference of its name on the
  line — true `uses` facts in every language, and fmt's 19 constructions
  behind a using-declaration. True since ADR-029, unregistered until
  measured (7,308 hidden on 25 clones). The claim is by the matched
  resolution's position now; 44 cells regraded, fmt +19 confirmed at 0
  contradicted, the rest ±0. **C-162 narrowed:** its using-declaration
  residual is closed. 163 entries, 118 active, 92 surfaced, 22 partial,
  3 unsurfaced, 28 lifted.

C-162 registered and narrowed, 2026-09-17 (ADR-132, 0.2.44-beta):
- **C-162 registered (surfaced)**, in `extraction-cpp.md`: a C++
  construction has no callee lane A records, so it drew no call unless
  written `T(args)`. True since ADR-113 and unregistered until ADR-132's
  measurement read it. Narrowed in the same commit: a call where lane B
  names a constructor at exactly a construction token, outside a
  template. fmt +92 confirmed at 0 contradicted (30.1% → 30.3%), args
  held out +369 (62.5% → 72.9%). What is left: templates, the macro
  class, conversions with no token, references the index does not emit,
  and a type named through a using-declaration (19 rows on fmt). 162
  entries, 118 active, 92 surfaced, 22 partial, 3 unsurfaced.

C-153 narrowed a third time, 2026-09-17 (ADR-131 amended, 0.2.43-beta):
- **C-153 narrowed (still partial), C-146's surfacing line restated:** a
  lane B reference named `operator…` at exactly an operator token inside
  a template draws nothing — not a call (as before) and no longer a
  `uses` (Max: route a). fmt −156 `uses` symbol edges, args −24, none
  added, no graded row moved; one wrong module edge gone on each
  (`test/scan.h → include/fmt/format.h`, `args.hxx →
  test/test_common.hxx`). The right candidates among them go too (175
  key-confirmed rows on fmt). No entry added: 161 entries, 117 active,
  91 surfaced, 22 partial, 3 unsurfaced.

C-146 narrowed, 2026-09-17 (ADR-131, 0.2.42-beta):
- **C-146 narrowed (still surfaced):** a C++ operator applied by symbol
  draws a `calls` edge where lane B names an `operator…` at exactly the
  token lane A's parse shows, outside a template. fmt +392 call edges,
  391 confirmed, 0 contradicted, recall 29.1% → 30.1%; args +136, all
  confirmed, 58.6% → 62.5%. Inside a template nothing is drawn as a
  call: every row a naive rule adds that the key cannot judge is there,
  and about 100 of 161 read wrong (C-153 at the same arity). C-153's
  entry records that those references stand as `uses` edges, as they did
  before. No entry added: 161 entries, 117 active, 91 surfaced, 22
  partial, 3 unsurfaced.

C-145 and C-153 narrowed, 2026-09-17 (ADR-129 and ADR-130, 0.2.41-beta):
- **C-145 narrowed (still surfaced):** a C or C++ function, method or
  type definition lane A's parse lost to a macro is read from lane B's
  own definition row and becomes a graph symbol (`declared_by: "scip"`),
  a target and not a scope. fmt 3,269 → 6,510 confirmed call edges at 0
  contradicted, recall 14.5% → 29.1%; args 56.4% → 58.6%; the C cells do
  not move. The ingest summary counts the symbols and every refusal by
  reason; `who_calls` says which symbols they are.
- **C-153 narrowed a second time (still partial):** R-arity — a C++ call
  written with more arguments than lane B's target can take draws
  nothing (`arity-mismatch`). It withholds the 35 wrong `copy` edges the
  mint would have surfaced on fmt and 5 that were standing, and no
  confirmed edge. One same-arity wrong edge is known and named in the
  entry. No entry added: 161 entries, 117 active, 91 surfaced, 22
  partial, 3 unsurfaced.

C-160 and C-161 registered, 2026-09-17 (ADR-128, 0.2.40-beta):
- **C-160 registered (surfaced)**, in `extraction-cpp.md`: lane A's C++
  file cache keys on the extraction code's bytes and the grammar's
  installed version, not the native grammar's build; every ingest prints
  its hits and misses and the switch.
- **C-161 registered (surfaced)**, in `extraction-lane-b-environments.md`:
  repo code in a contained step can write the tool caches and the stage
  that later ingests read. The index and lane A stores now ride
  read-only in every step; the ingest prints a note whenever repo code
  ran. 161 entries, 117 active, 91 surfaced, 22 partial, 3 unsurfaced.

C-159 registered, 2026-09-17 (ADR-127, 0.2.39-beta):
- **C-159 registered (surfaced)**, in `extraction-lane-b-environments.md`:
  a second ingest of a repo is refused while one runs (an exclusive
  `flock` on `.hobbes/derived/.ingest.lock`), and the artifacts are
  written atomically. The residuals: a build before 0.2.39-beta takes no
  lock, and a filesystem without `flock` runs unlocked with a warning.
  159 entries, 115 active, 89 surfaced, 22 partial, 3 unsurfaced.

C-153 surfaced as partial, 2026-09-17 (ADR-125 §4, 0.2.38-beta):
- **C-153 unsurfaced → partial.** `who_calls` marks every semantic C++
  call edge that starts in a template pattern (a function template, or a
  member of a class template or partial specialisation), and one
  `cpp-template-sites` record counts them. The note marks the region
  where the error can occur, not the wrong edges: on fmt, 596 of 2,811
  semantic call edges, including both `format_as` rows R-qual leaves.
  158 entries, 114 active, 88 surfaced, 22 partial, 3 unsurfaced.

C-153 narrowed, C-152 amended, C-70 settled, 2026-09-17 (ADR-125, 0.2.37-beta; ADR-123, 0.2.36-beta):
- **C-153 narrowed, still unsurfaced:** a C++ call written through one
  explicit specialisation that lane B resolved into another's member draws
  no edge (`qualifier-mismatch` in the tail). On fmt that withheld 8 of the
  10 wrong edges and no right one. Two `format_as` rows remain, and the
  rule has residuals of its own. The surfacing ADR-125 §4 names is next.
- **C-152 amended:** a disagreement in a compiled C++ file is shaped
  `cpp-withheld` and no longer fails `hobbes lanes` (exit 3); the residual
  (a lane B error there is reported, not failed on) is written in the
  entry.
- **C-70:** the open question whether CI should fail on it is settled by
  the `same-line-pair` shape.
- Counts unchanged: 158 entries, 114 active, 88 surfaced, 4 unsurfaced.

C-158 registered, 2026-09-16 (night, last; ADR-122, 0.2.35-beta):
- **C-158 registered (surfaced)**, in `extraction-lane-b-environments.md`:
  lane B's index cache fingerprints a linked dependency tree by its
  target, top-level stat and installer marker, and a venv by its
  listing, not their files; a lockfile-less manifest keeps its first
  resolution. Every ingest prints what it read from the cache and the
  switch. 158 entries, 114 active, 88 surfaced, 4 unsurfaced.

C-155 lifted, 2026-09-16 (night, later; ADR-121, 0.2.33-beta):
- **C-155 lifted the day it was registered**, at the bottom of
  `extraction-cpp.md`: lane A records no C++ call site inside an
  unevaluated operand (`sizeof`, `alignof`, `decltype`, `noexcept(..)`, a
  requires-expression), and `noexcept`/`typeid` in call position record
  no site of their own. `typeid`'s operand keeps its sites (evaluated
  when it is a polymorphic glvalue) — the residual, with the macro gap
  and C's unclaimed headers. The oracle's matching half is H-32 (RC-11),
  fixed as the next unit. 157 entries, 113 active, 87 surfaced, 4
  unsurfaced.

C-157 registered and C-58 narrowed, 2026-09-16 (night; ADR-120, 0.2.32-beta):
- **C-157 registered (surfaced)**, in `extraction-rust.md`:
  rust-analyzer's SCIP export states no `relationships`, so Rust draws
  no `implements` edge; every Rust run says so. Measured against the
  five other indexers, which all state the set.
- **C-58 narrowed:** the override set it said Hobbes lacks is drawn as
  `implements` edges (ADR-120); the dispatch through an interface is
  still not. 157 entries, 114 active, 87 surfaced.

C-156 surfaced, 2026-09-16 (later; ADR-117, 0.2.29-beta):
- **C-156 moved from unsurfaced to surfaced** (Max's route (a)):
  `tests_guarding` and `hobbes review` name C-156 on a value-only
  module listed as unguarded. The module is still listed.

C-156 registered, 2026-09-16 (no version move):
- **C-156 registered (unsurfaced, debt)**, in `extraction-call-graph.md`:
  test reach follows `calls` edges only, so a test that reads a constant
  and calls nothing guards nothing. It is why `go/internal/version`
  reads "unguarded" despite its test (W0). The header's count, which had
  not taken in C-155, is corrected with it: 156 entries, 113 active.

O10's defects fixed, 2026-09-16 (bench only, no version move):
- C-153 restated, still **unsurfaced**: only **4 of its 10 fmt rows are
  still judged**. The oracle's own H-30 fix silences a row whose line
  also carries a call the key left unresolved, and 6 of C-153's sit on
  such a line — *unjudged, not fixed*; the edge is still the wrong
  declaration. fmt's cell reads 99.85% where the like-for-like figure is
  99.66%, and both are in its record. The number that would have exposed
  this concession is now smaller than the concession.
- **C-155 registered (unsurfaced, debt)**, in `extraction-cpp.md`: a
  C++ `calls` edge drawn inside an **unevaluated operand** —
  `decltype(...)` and the same shape in `sizeof`, `noexcept`, `typeid` —
  which the compiler never calls. Found by tracing H-31 on 2026-09-16:
  six of its seven rows were the oracle's, but `compile-test.cc:127` was
  Hobbes drawing `fmt::arg` inside a `decltype`, where clang is right to
  emit nothing. One row read from source; 26 more sit on `decltype(`
  lines oracle-silent, an upper bound, unread individually.
- **H-28, H-29 and H-30 take no `C-n`:** they are defects of the oracle
  that grades Hobbes (`oracle/oracle-defects.md`), not concessions the
  layer makes to a user.

The gate's arrow read, 2026-09-15 (0.2.28-beta):
- C-91 amended again: the gate's TS/JS text read takes an arrow's
  parameters (a parenthesised list before `=>` wherever it stands, one
  bare name before `=>`), closing the harness's one false block
  (`f3c1`). A list holding a nested `(` stays unread, and says so.

The facts arrive as a stream, 2026-09-15 (0.2.26-beta; ADR-116):
- C-150 corrected and narrowed: the entry said ScummVM's facts reached
  the Python side as about 850 MB of JSON. The helper could not print
  them: one `JSON.stringify` of 699 MB passes V8's longest string, and
  the record read "install Node". The helper now writes a file of JSON
  lines, one per document, and the Python side reads each reference
  into a slotted, interned resolution site: 0.99 GB where the one
  document took 3.63 GB. What is left is the join's own size.
- C-150 moved from surfaced to *partial*: an ingest the kernel kills on
  the Python side, where the wall now is, ends with no graph and no
  record, and nothing names the entry there. It was as true before; it
  was not written down.

The helper's decode streams, 2026-09-15 (0.2.25-beta; ADR-115):
- C-150 narrowed: the helper reads SCIP's wire format one document at
  a time instead of building the whole index as protobuf objects.
  ScummVM's index, which needed 8.95 GB and had no lane B, decodes
  under Node's default heap at 3.4 GB resident with identical facts.
  What is left is the facts' own size on the Python side; the entry
  is retitled for it. A killed helper (exit 137 or -9) now names the
  entry instead of "install Node", and the entry names the heap
  override for a box that needs it.
- C-149 reworded: the bound stays, for the references the per-unit
  route holds and the disk and time it spends, not for the merge's
  memory, which is gone.

C++'s §3.8 row on 2026-09-15 (0.2.23-beta):
- C-132 narrowed again: C++ is *supported* as far as its row reaches.
  What is left is a `.h` both languages include (or none does in a
  mixed repo), which is still read as C, and cgo's collision (C-15).

The C++ cells on 2026-09-15 (0.2.22-beta; ADR-113 §2 amended a third time):
- C-151 registered (surfaced): a C++ call site whose references name
  several overloads abstains, counted in a `scip-decode` record. Before
  it, the smallest line was kept: 36 wrong edges on fmt, 4 on args.
- C-152 registered (surfaced): a C++ file lane B indexed draws no
  fallback edge where lane B answered nothing, counted in
  `lane_agreement.cpp_withheld` and a `cpp-fallback` record. Before it,
  the fallback there was 108 right and 74 wrong on fmt.
- C-153 registered (**unsurfaced**, debt, P9): scip-clang's single
  answer at a call in a template can name the wrong declaration (10 of
  fmt's 3,395 judged semantic edges). Nothing at the site can say so.

Per-unit indexing on 2026-09-15 (0.2.21-beta; ADR-109 decision 1 amended, with Max's size guard):
- C-149 narrowed from unsurfaced to *partial*. A root of at most 400
  units is indexed one unit per run and repeats. A root over the bound is
  indexed whole and says so. The residue is a few external type
  references, which move a tail count and never an edge.
- C-91 amended: the gate's TS/JS text read misses a bare arrow
  parameter list, and that caused the harness's first false block
  (`f3c1`).
- C-150 registered (surfaced), in `extraction-lane-b-environments.md`:
  lane B's decode holds a root's whole index in memory, so a root whose
  index outgrows Node's heap has no lane B, in every language.
  Measured on C++: ScummVM needs about 9 GB. The record used to say
  "install Node"; it now names the heap. Max, 2026-09-15: large repos
  stay a constraint for now; the memory problem is to be assessed as a
  whole, likely as an architectural change.

ADR-113's determinism unit on 2026-09-14 (0.2.20-beta), C and C++ lane B:
- C-148 registered (surfaced): a moniker one file defines at several
  lines abstains in C++, counted in a `scip-decode` record.
- C-149 registered (**unsurfaced**, debt): scip-clang indexes a shared
  header once, in whichever unit claims it, so a unit-dependent
  reference can come and go by run. The per-unit indexing route is
  Max's call.

ADR-113 unit 2 on 2026-09-14 (0.2.19-beta), C++ at lane B:
- C-144 lifted: every overload is a symbol (`~n`), and the duplicate
  record fires only on a same-signature repeat. C-143 and C-145 are
  restated with lane B in; C-145 now carries fmt's measured below-floor
  cost (6,896 of 7,376 facts).

ADR-113 unit 1 on 2026-09-14 (0.2.18-beta), C++ at lane A:
- C-142–C-147 registered in a new segment, `extraction-cpp.md`: the
  `.h` claim (*partial*), overloads and member calls abstained
  (surfaced), one symbol per qualname per file (surfaced, wrongly
  worded — a unit-2 defect), macro-heavy headers' error nodes
  (surfaced), operators and named casts not sites (surfaced), a test
  body in an error node counted (surfaced). C-132 narrowed.

Max's register decisions, 2026-09-14 (later; ADR-043 amended):
- **A segment of its own for the dispatch harness:** C-125, C-127–C-129
  and C-140 moved from the verification segment to
  `dispatch-harness.md`, numbers and text unchanged.
- **C-120 folded into C-112:** its unsurfaced remainder restates
  C-112's (a garbled post-image reads as whatever the parse makes of
  it, and `hobbes gate` reaches it); the gutter class is what it adds.

ADR-112 built on 2026-09-14 (0.2.14-beta), the session's records leave the
doer's container:
- C-140 narrowed to a forged edit line, and surfaced: the flight log,
  the escalation queue, the mail file and the egress log are written by
  a sidecar container per session over one flight stream; the doer's
  HOME is a tmpfs. A session on an explicit `--network` keeps the old
  reach and says so.

Max's register decisions, 2026-09-13 (ADR-043 amended):
- **Eight superseded:** C-104–C-108 and C-114–C-116, the keyed rounds'
  T loop, template v2, arm budgets and `gold_tests`. Only
  `pipeline/scripts/calvin_probe.py` still reaches them. C-120 was named
  with them and stays active: `hobbes gate` grounds every dispatched
  diff through the code it concedes (`gate.py:552`).
- **C-141 registered** from C-139's residual (*partial*).
- **Five folded** under the new rule, each into the entry whose
  concession it restates.

ADR-107 amended on 2026-09-13 (0.2.11-beta), a session's reach:
- C-140 registered: a dispatched doer can alter or delete its own
  session's records. Every other session's are out of reach, because a
  session now mounts only its own dir (*partial*). The fix, the proxy in
  a container of its own, is Max's call.

ADR-046 amended on 2026-09-13 (0.2.10-beta), the qualifier of a selector call:
- C-139 lifted: Go lane A's fallback no longer resolves a qualified call
  whose qualifier a local binding shadows. All 27 Go cells with a stored
  key were regraded with nothing moved.
- Its residual is recorded in the entry: the function-wide extent gives
  up the declaring statement's own package call where lane B is silent
  (30 of the 95 lane A drops on dagger; *partial*).

ADR-111 on 2026-09-12 (0.2.8-beta), the external veto:
- C-138 narrowed: lane A's fallback is dropped where lane B resolved the
  site outside the repo; the residuals are two same-named occurrences on
  one line, and a sibling unit's ungraphed kind (*partial*).
- C-139 registered: a Go local named like an imported package shadows
  it, and lane A draws the call to the package's function where lane B
  does not answer (*partial*; 56 sites on dagger, vetoed there).

ADR-107's progress hook, 2026-09-12 (0.2.6-beta):
- C-125 narrowed: a dispatched doer's edits are in the flight log by
  time, tool and path; its reads are still recorded nowhere
  (*partial*).

ADR-110 on 2026-09-12, C's oracle cells:
- C-138 registered: lane A's fallback guesses where lane B resolved the
  site to a declaration outside the repo (*partial*).
- C-131 measured: cJSON's 728 macro-expansion pairs, and
  sqlite-vector's dead-arm `strcasestr`.
- C-135 moved from *surfaced* to *partial*: a root whose derived
  database indexes nothing draws a generic record (jfernandez/bpftop).
- C-130's surfacing restated: the verification base names C since
  0.2.5-beta.

ADR-109 on 2026-09-12, C's lane B, scip-clang:
- C-130 narrowed (lane B where a compile database can be derived).
- C-131 narrowed (the configured `#if` arm; a site that translation
  units resolve in different files keeps lane A's floor).
- C-135–C-137 registered:
  - a root with no derivable compile database stays lane A only
    (*surfaced*);
  - indexing C runs the repo's build logic, contained and offline
    (*surfaced*);
  - scip-clang's file-statics of one signature share a moniker
    (*surfaced*, P9).

ADR-108 on 2026-09-12, C at lane A:
- C-130–C-134 registered:
  - C has no semantic lane, and edges match by name (*surfaced*);
  - the preprocessor never runs (*partial*);
  - `.h` is C and C++ is not read (*partial*);
  - includes resolve by path, not `-I` (*unsurfaced*);
  - tests follow one naming convention (*unsurfaced*).

ADR-107's retention amendment, 2026-09-12:
- C-129 registered: the training guard keeps the session rows and the
  doer's commits out as units, not the merged tree (*surfaced*).
- C-125 amended: the doer's transcript is no longer kept.

ADR-107 on 2026-09-12, the Calvin harness:
- C-125–C-128 registered: a dispatched doer's native file tools are
  outside the flight log (*partial*); a created file in a new directory
  reads `unmapped` at the gate (*surfaced*); the harness is validated by
  the developer's review, not an answer key (*surfaced*); a dispatch is
  not reproducible (*surfaced*).
- C-124 superseded: the keyed rounds closed, and `--egress` is its fix.
- C-41 narrowed: `hobbes-session --egress` reaches the listed hosts
  alone.

C-124 registered 2026-09-11 by Calvin M0-Gate WP-18c — an arm-O session's repo
is cut at the key's parent (D-x), but the container keeps the endpoint's
network, so upstream is out of the repo and not out of reach; *partial*;
C-121–C-123 registered 2026-09-11 by Calvin M0-Gate WP-18, `hobbes gate` — the
`unknown` advisory, the partition check at file grain (`reach` by default: what
lies beyond the code world is listed, not blocked),
and the complement split's grain and classes (the map's file-grain sites never
route), all three *surfaced* in the gate's record; C-118–C-120 registered 2026-09-11 by Calvin M0-Go round 2 WP-14b, grounder
v3's signatures in the world — a call's arity and a qualified reference's
declared existence, each its own NULL class; every doubt (variadics,
generics, a call whose sole argument is itself a call, an interface or
method-value target, a dependency this grounder cannot itself read, a
callee whose own file this diff also edits) abstains, *surfaced*
(`world.signature_rule`); a gutter-carrying post-image is its own
reference class, `malformed`, rather than a silent zero — *surfaced* for
that one shape, **unsurfaced** for every other malformation (D-m);
C-116 and C-117 registered 2026-09-11 by Calvin M0-Go round 2 WP-14,
adapter protocol v0.6 — an arm at its budget stops and its row is scored
as it stands, and the declaration hole's sibling cut at 4,400 bytes
(surfaced partial); C-114 amended, the one repair now reads build errors too;
C-115 registered 2026-09-11 by Calvin M0-Go round 2 WP-11a — `gold_tests`
carries a test's fixtures only from `testdata/`, `__fixtures__/` and
`__snapshots__/`, surfaced partial;
C-109–C-114 registered 2026-09-11 by Calvin M0-Go WP-9, grounder v2's
world check and adapter protocol v0.5 — a required module's package
unchecked, unaliased import names read by convention, build tags
unread, syntax errors unclassed (**unsurfaced**, debt), the world
check Go only, and the declaration repair bounded to one exchange;
C-106, C-107 and C-108 registered 2026-09-11 by Calvin M0-Go WP-7a,
adapter protocol v0.4's declaration hole — a near-miss name re-asked
rather than declared (*surfaced*, `loop.sites[].route`), a declaration
outside the write partition placed and recorded, never refused, on
Max's decision (*surfaced*, `in_partition` / `outside_partition`), and
a declaration's directory unchecked for a non-Go name or an
`after_symbol` placement (*partial*); C-105 registered 2026-09-11 by Calvin M0-Go WP-5 — a protocol v0.3
pattern answers many holes with one judgement, *surfaced* by
`by_pattern`; C-104 registered 2026-09-11 by Calvin M0-Go WP-2 — template v2 shows
a callee over the out-degree cap by its signature line until it is
confirmed, *surfaced*; C-103 registered 2026-09-11 by Calvin M0-Go WP-1 — a Go generation
guard's verdict rides on random draws, the retry recorded per step,
*surfaced*; C-102 registered 2026-09-11 by Calvin M0-Go WP-3 — lane A's Go local
bindings skip a `var ( … )` group inside a function, *partial*; C-91
amended the same day — grounder v1 judges a Go member whose receiver's
type the syntax states; C-101 registered and lifted 2026-09-10, later still — the Java resolve
stage held Kotlin sources and a Maven build compiled them against Java
that was not there, found by the 0.1.7-beta baseline regrade; C-100 registered and lifted 2026-09-10, later — `.mts`/`.cts` sources
were not discovered by lane A, found by the callee-shape bucket of
cheerio's miss set; C-98 lifted and C-99 registered and lifted 2026-09-10 — the TS helper
types a file under a solution-style tsconfig by the referenced project
that includes it, and a config with `references` and neither `files` nor
`include` is a project, not a solution, in both lanes; C-97 and C-98
added 2026-09-09 later by ADR-104 — the union-member
abstention and the solution-tsconfig gap lane A had and lane B did not;
C-94, C-95 and C-96 added 2026-09-09 by the comparative programme, ADR-101 —
the converter grain, the oracle's tolerances tuned on Hobbes' output, and
competitor cells host-run; C-92 and C-93 added 2026-09-04 by Calvin M0 step 5, ADR-100 — the
local harness binds a SHA's tests to a source checkout's dependency
trees, and reaches a behaviour only through a test the testmap maps;
C-91 added 2026-09-04 by Calvin M0 step 3 — grounder v0 binds call
sites only, in Python, Go and TS/JS, and abstains on members of values;
C-90 added 2026-09-03 by the same re-ingest and **lifted the same
night** — a tsconfig that `extends` or `references` a config off the
zone's walk-up path is now staged transitively and a solution-style
root gets the generated config: date-fns 15 of 15 zones, lanes 7,601 / 0;
C-89 registered and lifted 2026-09-03 the same hour — an overloaded TS
declaration placed at its implementation where the semantic lane places
it at its first signature, found by date-fns's re-ingest once C-74 gave
it lane B: 54 disagreements and below-floor calls, gone; C-73, C-74 and C-85 **lifted 2026-09-03**, the same session, the last
of the ten: a repo-internal directory link is walked once at its target
and recorded, a workspace's `node_modules` links mount their targets
and the helper tells an indexer's death from its own, and a Python repo
with no venv indexes against an empty listing with the fix named —
measured on a venv-less fixture (0.0% → 68.4%) and a synthetic
workspace (TS6053 → a semantic edge);
C-72 and C-80 **lifted 2026-09-03**, the same session, the two the
four-repo test found on the call graph itself: the Rust fallback
abstains where a path's head does not single out a declaration, and an
expression receiver is a Python call site with the `uses` gloss reworded;
C-78 and C-79 **lifted 2026-09-03**, the same session: the `http-go`
pack reads the receiver and the import before a name counts, and the
dependency reader takes `setup.cfg` and `requirements*.txt` and records
when no manifest declared anything — `setup.py` stays unread;
C-75, C-76 and C-77 **lifted 2026-09-03** — the first three of the
2026-09-02 nine cleared on the lead's direction, easiest first: the
lanes self-test counts only semantic module edges as lane B's and prints
lane B's share, the summary and `hobbes diff` count `calls` and `uses`
apart, and the proxy's tail table carries `below-floor`; the register
no longer holds a line that reads larger than the truth; C-86–C-88 added 2026-09-03 from the review of the TTT results: the
shuffled control's margin is a bound, not the graph's worth (*surfaced*);
the first NLL write-up left the conditioning unstated, a reporting
defect (*surfaced*); an adapter trained on "none recorded" answers
disbelieves the card in front of it (*partial*, candidate fixes named);
C-85 added 2026-09-03 from ADR-099's memorised-cell ingests — a Python
repo with no venv loses lane B entirely in the container and the record
blames the helper (*partial*; **lifted the same day**, above);
C-81–C-84 added 2026-09-03 by ADR-099, the test-time-training
experiment: the adapter is regenerable but not bit-identical across
hardware (*surfaced*, the manifest), held-out names leak through plain
words and the doc rendering is empty where nothing narrated
(*surfaced*, the corpus manifest), the memorisation probe is a coarse
gate (*partial*), and a git-history unit carries the base graph's
context — 92 of this repo's 147 units name files the base never had
(*surfaced*, per unit); C-71–C-80 added 2026-09-02 by the four-repo extraction test — four
random public repos, one per language, each ingested contained and
hand-sampled; two stopped on lane disagreements. **C-71** — the Go
graph is one build configuration's and lane A abstains where
constraints split a name — is the one *fixed and surfaced* the same
day (ADR-098: two wrong syntactic edges and twelve disagreements on
quic-go gone). The other nine are **registered, not fixed**, at Max's
direction ("flag rest in constraints"; **all nine lifted the next day**, above): C-72 the Rust fallback's
last-segment binding (*partial*), C-73 a repo symlink walked as a
second copy (*partial*), C-74 workspace links dangling in the
container with a record that blames the helper (*partial*), C-75
`hobbes lanes` counting the join's fallback as lane B
(**unsurfaced**), C-76 the summary's "call edges" counting `uses`
(**unsurfaced** — the one line that reads *larger* than the truth),
C-77 `list_blind_spots` dropping `below-floor` (**unsurfaced**), C-78
the `http-go` pack firing on any `Handle` (**unsurfaced**), C-79 no
`dependency_coverage` for `setup.py` repos (**unsurfaced**), C-80
`super().m()` / `f().m()` not a site and glossed as not a call
(*partial*). Five of the nine are one-to-ten-line fixes with the
candidate named in the entry; C-70 added 2026-08-29 — two same-named calls on one line can pair with
the wrong resolution, found by Java's fluent chains and measured at
0.05% of dual-resolved sites, surfaced as a lane disagreement;
C-66–C-69 added the same day by ADR-096 — Java: the build runs in the
container with a network (C-66; **narrowed 2026-09-01 by ADR-097**: the networked pass holds no sources, the index pass no network), the
one-configuration graph, generated sources (*partial*), and read-not-resolved
dependency counts — three surfaced on day one; C-65 added 2026-08-28 by ADR-094 — the knowledge proxy pinned to the
image, the host hatch disclosed, surfaced on day one; C-64 added 2026-08-27 by ADR-092 — lane B contained, executing
providers refuse without it, surfaced on day one; C-63 the same day by the
oracle lane's H-17 close, unsurfaced; C-58 added 2026-08-25 by the oracle lane; C-60–C-62 — the trace
asymmetry, the reference-lane rule and design §3's four rules —
registered surfaced the same day by the lane's phase 2, C-62 late for
phase 1; C-59 registered and lifted the same day — unsurfaced, and the first
entry where a coverage number reads *better* because of the gap; audited against the tree on 2026-08-23 — every active entry re-checked
against the code that concedes it; none had been silently lifted). The *partial* and **unsurfaced** lists this sentence kept by hand fell behind (it last read seven and three, with C-124 among the partial); the table above is current. Notes on the unsurfaced as they stood then
(C-19 — narrowed to two tools, and since ADR-095 every compiled config is executed in CI — C-20, and C-112 — the grounder's unclassed syntax error, registered as debt 2026-09-11; the 2026-09-02 five — C-75, C-76, C-77, C-78, C-79 — were all lifted 2026-09-03; C-63 — *unsurfaced* since 2026-08-27 and never in this count — was **surfaced 2026-09-05**: the site is counted and classed `expr-callee`, ADR-045 amended); C-58 — the interface/closure call hole, whose capture number reads
resolved — moved to *partial* on 2026-08-25 (ADR-090: the `below-floor`
tail class); C-4 moved from unsurfaced to *partial* in that audit, its status
having lagged the ADR-047 denominator statement by a week. The same audit
corrected four drifted prose lines (C-35, C-42, C-46, C-54) and moved
C-55/C-56 to the new Superseded part. C-31 left the unsurfaced list on 2026-08-21 (ADR-053:
the verification base stamped into the artifact and stated wherever a
language list is read), as did C-32's `partial`. The three derivation entries (C-35..C-37,
ADR-051) landed surfaced on day one — the statement prints on every
`hobbes plan` run and rides every change-spec. **C-33 was lifted fastest of
all**: registered from the dagger measurement (ADR-048) and lifted one
session later (ADR-049) when Max reviewed the candidate fix and
directed it — the register working as intended, a finding becoming a
fix through review rather than around it. The earliest others —
C-14 in the 2026-08-16 register paydown (three CLI packs; the entry's
own counter-example is the pinned exit check),
C-11 at V2.M3, C-3 and C-16 in the 2026-08-15 pre-M6 sweep (which also
surfaced C-5 and C-26), C-18 at V2.M6, and C-24 the same day: the JSX
lift was approved with the standing condition that "in every meaningful
sense" keeps its outliers named, which the lifted entry does. That churn
is the point of keeping the register: none of it was knowable before
this file existed, and what remains is the backlog P8 generates.

The **2026-08-16 paydown** worked the register's own ranking, worst
first: C-14 lifted (CLI packs), C-12 narrowed and
surfaced (ADR-041 — the #1 entry's common cases now resolve, its
residue reports itself), C-19 narrowed to two tools (semgrep executes
in the agreement suite, and its emitter survived first contact clean
where import-linter's had not), and C-21 surfaced (ADR-042 — the queue
shows the record a proposal restates, with the I-9/I-3 failure as the
pinned case). Four entries, four mechanisms, each landed with its
tests in one commit.

C-27 arrived the way the register says entries should: C-16's first
working run produced a number (0 of 5 resolved), the number was
investigated rather than explained away, and the investigation found
*two* stacked causes — a hardcoded venv path and an indexer asking the
wrong environment entirely. Both fixed same-day, and the entry records
what remains: discovery is convention-bound, and `dependency_coverage`
is the answer for environments the conventions miss.

V2.M4 added one entry (**C-25**) and it is *partial* rather than
unsurfaced, because `graph.json`'s `packs` list was added in the same
commit as the pack layer. Attributing a layer to the pass that produced it
was the cheap half of the answer; suppressing it is the half that is
deferred.

V2.M5 added **C-26** (also partial) and **widened C-6**, which is the more
interesting event: measuring a second indexer showed the original entry was
filed too narrowly. C-6 was written as "scip-python does not populate
`syntax_kind`" and read as a gap one upgrade could close; `scip-go` omits
it too, so the entry now says no indexer populates it and an upgrade of one
lifts nothing. **A register entry can be wrong by being too specific**, and
nothing catches that except measuring the next case.

The 2026-08-15 audit (before V2.M6) found the complementary failure: **a
register entry can be made wrong by a milestone that never touched it.**
Six entries had drifted, all by M4/M5 side-effects — C-3 materially (Go
emitted stdlib `ext:` nodes where Python and TS dropped them, an asymmetry
no ADR registered), C-15's merge order predated both the pack layer and
Go, and C-5/C-9/C-10/C-14 named mechanisms or providers that had since
moved or multiplied. Nothing detects this today: the register is prose,
and no milestone exit re-reads entries it did not write.

The same day's sweep then paid down the worst of what the audit ranked:
C-3 was lifted outright (ADR-038 — stdlib everywhere, rather than
re-hiding what Go already showed), C-16 was lifted (the manifest walk),
and C-5 and C-26 went from silent to one degradation record per declined
route and per orphan Go directory. C-5's surfacing also caught the Nest
reader *emitting* a computed route with the segment dropped — the one
shape worse than absence, found only because surfacing forced the decline
path to be written down.

V2.M7 added three entries (**C-28/29/30**) and amended two (**C-9**: macro
is the fifth graph kind; **C-6**: a third indexer confirmed the
generalisation) — and it is the first milestone whose **every new entry
arrived surfaced**: C-28 through the decode degradation record, C-29
through a stderr disclosure on every rust ingest, C-30 through
`dependency_coverage`. C-28 also replayed C-6's arc at higher speed:
written for cargo targets in the morning, generalised the same day when
the verification re-ingest showed scip-go duplicating package namespaces
too — and this time the drop *removed two false semantic edges* that had
stood in the Go graph since V2.M5, the register mechanism catching a lie
rather than only naming a silence. C-29 is also a first of its kind: an
entry registering something Hobbes **does** (execute a Rust repo's
`build.rs` and proc macros at ingest) rather than something it cannot
see — the honesty discipline pointed at a capability instead of a gap.

Ranked by how badly each remaining entry misleads, worst first:

*(The two entries that held this list are gone as of the 2026-08-16
paydown: C-12 — cross-zone edges simply absent — is narrowed to
alias-only cases and surfaced (ADR-041), and C-14 — "an empty CLI list
reads as 'no CLI'" — is lifted outright. What remains stays quiet
rather than lying, which is a real difference; the worst residue is
C-4's fixture-thin test reach and C-19's still-unexecuted emitters.)*

**No line in the register inflates a number.** For one day (2026-09-02
to 2026-09-03) C-76 — the summary's "call edges" label counting `uses`
— did, and it was lifted by a relabel on the lead's direction.
Before it, C-11 was the only
entry that made a claim larger than the truth, and V2.M3 lifted it; C-24,
its deliberately-under-reporting residue, was lifted in turn once the
under-report could be replaced with the true edge rather than the safer
inaccuracy. Every remaining limit under-reports or stays silent — so a
Hobbes number can now be read as a floor, which is a property worth
defending in later milestones. **C-31 is the near-exception and the
reason it was filed** (2026-08-16): not a number but a word —
"supported" — that read larger than its evidence, a language list whose
rows presented as peers while their verification bases differ by an
order of magnitude. Architecture §3.8 now scopes the claim; the entry
holds the unsurfaced remainder, deliberately taken as debt with its
candidate surfacing named, rather than pretending a table in a document
reaches a user at ingest.

**The tail view landed the same day** (ADR-045, C-2 amended, C-32
added): the unresolved count now decomposes on every ingest into
observation-based classes, and the 2026-08-16 measurement that
motivated it showed the tails were never uniformly dark — kbet's
worst-looking number (72.1% accounted) hid a tail that is 61%
below-the-floor local bindings the checker could name all along, with
**9 sites of 1,339** fitting no observation at all. The measurement
also produced the session's working vocabulary: *seen and not modelled
by design* is knowledge; *cannot resolve* is the concentrated remainder
this register exists to track; and any of it that turns out to be
**needed** for derived context is a direct entry here, never a
percentage's rounding error.

**Track record so far:** three of the four entries touched at V2.M3 were
*already true and already invisible* before the register existed — C-23 in
particular had a check written specifically to catch it that could not fire
under any circumstances, and C-11 had been honestly documented at M6 and
went on misleading for two milestones. That is the argument for P8 restated
as evidence: being written down in an ADR at the moment of decision did not
stop either of them.
