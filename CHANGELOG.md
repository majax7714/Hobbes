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
each time (0.1.9-beta to 0.2.9-beta and 0.2.11-beta to 0.2.25-beta
untagged; 0.2.10-beta is tagged `v0.2.10-beta`, on Max's word at the
close of 2026-09-13).

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
