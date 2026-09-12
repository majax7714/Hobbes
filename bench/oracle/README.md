# bench/oracle — grading the call graph against answer keys Hobbes does not control

The oracle-grading lane (ADR-089; design in `docs/oracle/oracle-grading.md`).
Bench tooling only: its own Go module, no product code, one binary with
cells as data. It exists to give the extraction layer two numbers it has
never had — **precision-against-oracle** and **recall** — from an edge
source that is independent of Hobbes, authoritative for the language,
and regenerable by anyone with the toolchain.

```sh
cd bench/oracle && go test ./...            # fixture self-test: minigo + twomod (Go), minits (TS), miniapp (Python), minirust (Rust), minijava (Java), cclang + the probe (C)
cd bench/oracle/ts && npm install            # once: the fallback typescript for fixtures
cd bench/oracle/rust && cargo +nightly build --release   # once per nightly: the MIR driver (rustc-dev)
bench/oracle/run-cell.sh <repo> <module-dir> <out-dir> [--lang go|ts|py|rust|java|c] [--no-ingest] \
    [--python "<cmd>"] [--runs N] [--sys-path a,b] [--features f] [--tool maven|gradle] [--compdb path] [--clang-bin clang] [-- <pytest args>]
```

`run-cell.sh` ingests the repo with lane B, exports the Hobbes edges of
one cell, runs the language's oracle on it, grades, and leaves
`hobbes.json`, `oracle.json`, `report.json`, `report.txt` and the cell's
runtime in the output directory. The steps are the binary's subcommands
(`oracle export | import | go-rta | py-trace | rust-mir | java-javac | c-clang | grade`) if you need
them apart (`c-clang-units` is `c-clang`'s internal half, run inside the
image, never by hand); the TS oracle is `ts/tsc-oracle.mjs`. Phase 1
(ADR-089) is Go and TS; phase 2 is the Python trace oracle, the Rust MIR
oracle and the C clang oracle below. **Those three execute the target**
(its suite; its build scripts; deriving and compiling a C build), so
they run inside the sandbox image (ADR-092, `internal/contain`): build
`hobbes-session:local` first (`sandbox/README.md`); without it they
refuse, and `HOBBES_UNCONTAINED=1` runs them on the host with the fact
recorded in the export and the report.

## Grading a graph Hobbes did not build (ADR-101)

The oracle does not care who produced an edge. `oracle import` reads a
third-party tool's call graph in one minimal shape and turns it into
the same `HobbesExport` that `grade` takes — poison check included —
so a competitor's graph, or your own, is graded against the same
answer key with the same matcher:

```sh
bench/oracle/grade-foreign.sh <edges.json> <oracle.json> <out-dir> [--module .] [--lang go|ts|py|rust|java] [--exclude a,b]
```

`<edges.json>` is:

```json
{ "repo": "<path>", "sha": "<commit>", "tool": "<name>", "version": "<pin>", "converter": "<adapter>@<version>",
  "edges": [ { "site": "file:line", "callee": "file:line", "caller": "<optional>", "kind": "<optional callee kind>", "label": "<optional: the tool's own confidence>" } ] }
```

at the lane's grain (D-O4: the site is the line of the call's opening
parenthesis, the callee the line of the declared identifier; paths
repo-relative). `<oracle.json>` is an answer key produced by
`oracle go-rta | rust-mir | java-javac | py-trace` or
`ts/tsc-oracle.mjs` on the same repo at the same commit — every cell
record in `docs/oracle/cells/` names the command that regenerates
its key. The tool's `label` becomes the edge's tier, so the report's
per-tier split reads the tool's own confidence ladder. A malformed
position refuses the whole file (a converter defect must never grade
as a smaller graph, C-94). Two matcher rules read Hobbes-specific
metadata and fire for a foreign graph only when its converter
supplies `kind`: a callee that is a variable is `abstract` (D-O4's
function-valued-binding rule), and `macro` excludes the edge (C-95).

One converter per tool lives under `adapters/<tool>/` (`adapter.py
dump` reads the tool's own storage as stored; `convert` makes the
shape above; a Go test converts a committed dump of `minigo` and
compares it to a hand-read truth, then grades it and requires the
poison twin refused). Present: `codegraphcontext` (Kuzu backend) and
`repowise` (`wiki.db`). The cells made with them are
`docs/oracle/cells/<tool>-<repo>-<date>.md`, in the same format as a
Hobbes cell, and every one is host-run (C-96).

## The callee-shape bucket (`shape/`)

Why a `tsc` key beats a `tsc`-based indexer (2026-09-10; the reading in
`docs/oracle/oracle-misses.md`): `shapes.mjs` walks a TS zone with
ts-morph (from `tsextract/node_modules`) and records, for every call
site, the checker's reading of the callee — an identifier's declaration
kind, a member's receiver shape, the resolved signature's declaration;
`bucket.py` joins a cell's misses to that record and to lane A's own
facts at the site, buckets them by shape, and prints the collapsed
recall (one pair per site line, target file and target name — the
identity `oracle grade` prints as `recall-collapsed` since 2026-09-10;
the script says whether the two programs agree on a report).

```sh
node bench/oracle/shape/shapes.mjs <clone> > shapes.json
node tsextract/extract.mjs --repo <clone> > facts.json
python3 bench/oracle/shape/bucket.py <cell-dir> <cell-dir>/oracle.json shapes.json facts.json
```

Each tool carries its suite beside it — `bucket_test.py` (stdlib
unittest, a hand-built cell with one miss per bucket rule) and
`shapes.test.mjs` (`node:test`, a built repo with one call per shape) —
and `shape_test.go` runs both under `go test ./...`, so the graph's
test map reaches the tools through their own tests (a Go test that
only execs a script reaches nothing the graph can see, and `hobbes
review` reports the module unguarded — the 2026-09-10 red run).

## Normative conventions (D-O4)

Both product lanes are measured against these, and the oracle extractors
are written to them. They are the answer to the line-convention
off-by-ones the lane-agreement suite has been logging (131 of dagger's
258), stated once.

- **Grain.** A graded edge is *(call-site position, callee declaration
  identity)*.
- **Position.** Repo-relative path + 1-based line **of the identifier**:
  for a declaration, the line of the function's name (not a decorator,
  doc comment, or `func` keyword on an earlier line); for a call site,
  the line of the call's opening parenthesis, which is the callee name's
  line in every shape Go's grammar allows. Columns are carried by the
  oracle for triage and are not part of the match.
- **Line grain.** A Hobbes edge is confirmed if its target is among the
  targets of *any* oracle site on the same file and line. A line holding
  several oracle sites is logged as a tolerance match in the report.
- **Overloads / instantiations.** Generic instantiations collapse to the
  origin declaration; wrappers, thunks and bound closures unwind to the
  source function they end in; closures are identified by declaration
  position only. TypeScript: **any declaration of the resolved
  signature's symbol counts** (overload-set membership).
- **A call through a function-valued binding** (2026-08-28; mux's
  `RegexpCompileFunc`, cheerio's `const parse = getParse(..)`,
  `_matcher = _getMatcher(..)`). Hobbes names the binding — a `var` /
  `const` graph symbol — and the oracle names the function the value
  holds. Both are true of the site: the binding is its abstract
  declaration exactly as an interface method is, so the edge is
  bucketed **abstract** (`func-value`), never contradicted. The export
  carries `target_kind` for this; 47 rows over two cells read
  contradicted before the rule.
- **Python `@overload` stubs** (2026-08-28; click, 47 of 85 suspects).
  The stubs and the implementation are one declaration: the graph's
  symbol sits on the first stub's `def` line, the interpreter runs the
  implementation. The tracer anchors the implementation's first line at
  the first stub's, so the pair matches at the graph's line.
- **The callee's binding.** When the resolved signature is *anonymous* —
  a type literal's or interface's `(...): T`, the shape of every
  `const useX = create(...)` hook, every `useState` setter, every
  callback parameter — the callee's identity is the **binding it was
  called through** (variable, property, parameter, binding element),
  not the signature's home in a `.d.ts`. Both product lanes resolve to
  the binding; the oracle lists it as a target labelled `binding` and
  does not list the anonymous signature. (O3's first pass graded 119
  `useAuthStore()` edges as contradicted against zustand's
  `react.d.mts`; that was the oracle's grain, not Hobbes' — a
  match-defect.)
- **Element-access callees** (`obj[key]()`, TypeScript; A-4 from H-17).
  A string or numeric literal key and a well-known `Symbol.x` member
  are graded like a property access: the site is the **key's line**
  (`a["b"]()` at `"b"`, `a[Symbol.iterator]()` at `iterator`) and the
  callee is what the checker resolves. A **computed key** is
  oracle-silent as `computed-key` (mode `dynamic`, no targets): tsc's
  answer there would be a guess, and blanket silence for the whole
  shape would forfeit a class (`process.env["X"]`, index signatures,
  generated clients). Fixtured in `minits/src/lookup.ts`, one function
  per shape; Hobbes' lane A currently counts none of the three as a
  call site (C-63), so the literal shape is a recorded recall miss.
- **Decorated declarations.** The identifier's line, not the
  decorator's. Hobbes' TS symbols currently carry the decorator line
  (`minits`' `ItemsController` at 5, identifier at 6 — the W1
  off-by-one); a call graded against such a symbol will contradict
  until that is fixed, and the row will say so.
- **Package initialisers are in the graded set.** `init` and
  package-level var initialisers are reachable from every main and their
  calls are real calls. Likewise **Python module bodies** (a call made
  at import time is a call the interpreter made; its caller is
  `<module>`) — D-O5's last open choice, decided *in* at O6.
- **Python packages.** A package's symbols live in its `__init__.py`,
  which the artifact records as a `package` node; the export grades them
  like any module's (H-12 — the first O6 pass dropped 113 edges into
  package files and charged them as misses).
- **Python classes and wrappers.** A call of a class is an edge to the
  `class` declaration (what Hobbes draws for `Foo(...)`); the `__init__`
  the interpreter runs from C has no site and is no edge. A callee that
  wraps a Python function (`functools.wraps`, `__wrapped__`, `partial`)
  is the wrapped declaration; a callable instance is its class's
  `__call__`; a bound method is its function. Nested functions and
  lambdas are targets (`closure`, `lambda`) with no Hobbes symbol.
- **Rust macros.** A `macro_rules!` body the repo defines is the
  author's code: its calls attribute to the invocation line (`static`).
  A call in the expansion of a macro the repo does *not* define
  (`criterion_group!`) is mode `macro` — the author wrote the
  invocation, not the call — and grades as its own miss class. A macro
  *invocation* is expanded, never called: Hobbes' edge to a `macro`
  symbol is excluded before grading and counted (`excluded.macro`).
  Code the compiler wrote — the test harness, attribute and derive
  output — makes calls no source line makes; those sites are dropped
  and counted (`excluded.generated`, H-13).
- **C macros** (ADR-110, O9's face of the Rust convention). A callee
  token written in a macro argument sits where it was written (its
  spelling location); one written in a macro's body sits at the
  invocation, mode `macro`. A chosen position that lies in one of
  clang's pseudo-buffers (`<scratch space>`, `<built-in>`, `<command
  line>` — token pasting's synthetic result, never a real file, never
  in `Files`) is never usable and falls back to the expansion, mode
  `macro` regardless of which the plain rule would have picked. Hobbes
  draws a macro invocation to the `macro` symbol, excluded before
  grading, so every call a macro's expansion makes is a `macro→…` miss
  (C-131).
- **C targets are definitions**, joined across translation units by
  name (javac's keyed merge, C's face of it). A `static` function
  resolves to its own unit's definition, or — with none, and no
  in-repo declaration or definition anywhere (a system header's
  `static inline`, e.g. `__bswap_16`) — external; declared in the repo
  but never defined there is `undefined`. An external-linkage name
  joined across units resolves to one distinct definition, or, with
  several and none the caller's own, no targets and `link-ambiguous`;
  none at all, declared only outside the repo or only implicitly (a
  builtin, whose location is the call's own), is `external`; none,
  declared in the repo, is `undefined`. A site different units resolve
  to different definitions keeps every target and counts `tu-split`
  (cJSON.c:612's shape). A callee that is itself a call (`get_fn()(2)`)
  is two sites sharing one (site, spelling) position — identity adds
  mode and callee name to tell them apart.

## Buckets and metrics

For a resolution or reachability oracle, every Hobbes `calls` edge lands
in exactly one bucket:

| bucket | meaning |
|---|---|
| **confirmed** | the oracle has the same (site, target) |
| **contradicted** | the oracle resolved that site and Hobbes' target is not among its targets — very strong evidence, not proof (RTA is unsound under reflection, `go:linkname`, plugins, cgo) |
| **abstract** | the site is a dynamic dispatch and Hobbes' target is the *interface method's* declaration — right at the declaration grain, not a concrete target. Reported on its own, in neither precision term; the concrete oracle pairs at that site count as misses (D-O3) |
| **silent** | the oracle could not speak: `not-loaded` (file outside the loaded program — build tags, orphan directories), `unreachable` (no reachable function holds a call on that line), `no-targets` (reachable, RTA resolved it to nothing). Charged to nobody, printed at full size |

- `precision-against-oracle = confirmed / (confirmed + contradicted)` —
  quoted as a **lower bound** on true precision (A-8): most
  contradictions triage to oracle-wrong, so the number is bounded
  below by construction. Every cell record also quotes its triage
  ratio, `oracle-wrong : hobbes-wrong : untriaged`, over the
  contradicted rows.
- `recall = confirmed in-repo oracle pairs / all in-repo oracle pairs`,
  always printed with its **root count** (Go) — recall is driven by the
  roots the oracle had and is never pooled or compared across cells.
  External targets (stdlib, module cache) are out of the denominator and
  counted separately (D-O3).
- `recall-collapsed` — the same pairs at (site line, target file, target
  name as the key spells it) grain, printed beside recall on every
  resolution or reachability cell (Max, 2026-09-10): a symbol's overload
  signatures fold, and so do repeats of one callee on one line. Never
  the headline; the per-signature line is the standing grade.
- Every cell reports the pair together, the silent size, the per-tier
  split (semantic / syntactic / dynamic), the miss decomposition
  (`static`, `dynamic`, `*-closure`), and the raw contradicted / abstract
  / missed rows — the triage queue.

Every defect found in the harness or an oracle is logged in
`docs/oracle/oracle-defects.md` with what it would have cost unnoticed.

## The poison check — proving wrong edges get caught

The fixtures prove true edges confirm. Nothing in that proves a wrong
edge is refused, and a matcher that falsely confirms is invisible to
triage, which reads only the failure buckets. So **every cell also
grades a poisoned twin** (`grade --poison`, which `run-cell.sh` always
passes): each Hobbes edge is re-targeted to another declaration the
export knows and the oracle never resolved that site to (the line after
the declaration when a cell has one target), and the report's last line
says how many the grader refused, how many it could not judge (the
oracle was silent at that site), and **how many it falsely confirmed —
which must be zero**. The fixture tests assert it for every oracle
kind; a cell record quotes the line. Poisoned rows are prefixed
`poison:` so they can never be mistaken for evidence.

## Cell records (`docs/oracle/cells/`)

One file per cell, with: how it was produced (command, sha, oracle
version, roots/suite, runtime); the report head verbatim; the triage
verdicts; the miss classes. Two lines are mandatory:

- **Poison check:** the report's line, quoted.
- **Direction of fix** — on every regrade after a product or harness
  change: what the change did to each headline number, **before → after,
  signed** (`confirmed 3,291 → 3,302 (+11)`, `contradicted 12 → 0
  (−12)`, `recall 83.8% → 98.1% (+14.3, H-16)`). A resolved number with
  no stated direction is the shape a flattering patch takes; the line
  makes a regression that "fixed" the number by shrinking the graded
  set visible (`hobbes edges` is part of the line).

**Triage verdicts** for contradicted rows (design §8): *hobbes-wrong*
(extraction defect → issue), *oracle-unsound* (logged, not charged),
*match-defect* (fix the matcher, rerun). A cell's number is final only
after its triage is complete or a sampled triage is documented as sampled.

For a **trace oracle** (design §3.1) the buckets are asymmetric — the
interpreter can confirm, never contradict:

| bucket | meaning |
|---|---|
| **confirmed** | Hobbes' (site line, target) was observed at runtime |
| **suspect** | the line executed, every observed Python callee on it is in-repo, and none is Hobbes' target — a triage queue (another input could still take Hobbes' target), never a contradiction |
| **unobserved** | charged to nobody: `not-loaded` (the module body never ran), `line-not-called` (no call on that line in any run), `line-mixed` (the line ran, but a C or out-of-repo callee was seen there, so Hobbes' site may be that call) |

A trace cell prints **no precision line**. It reports the confirmation
rate over Hobbes edges (coverage-limited), the suspect rate,
**recall-against-executed** over observed in-repo pairs, and the
mandatory **coverage line**: Hobbes sites the trace spoke about, module
files loaded, declared functions started, C-callee calls, and the run
count N the union is over. Trace triage adds the verdict
*not-exercised* (a monkeypatched function, the other branch of a
one-line conditional).

## The Go oracle (D-O1: RTA)

`packages.Load` with `Tests: true` → SSA (`InstantiateGenerics`) →
`rta.Analyze` rooted at the **`main` and `init`** of every main package
in the program — binaries and the synthesized test mains. A library
module is analysed through its test binaries; the report's root list
says which. Roots matter: without `init` the test table is never
reached and no test function is reachable (the first O1 finding).

Cells are per Go module directory: sites and loaded files are reported
only under the module, targets may land anywhere in the repo — so a
replaced sibling module (dagger's `sdk/go`, C-33) is inside the program
and its edges are graded. Build tags: the box's default set, plus
`--tags`; files excluded by tags are `not-loaded`.

## The TypeScript oracle (`ts/tsc-oracle.mjs`)

`node ts/tsc-oracle.mjs --repo <repo> --zone <dir-with-tsconfig>
[--config tsconfig.build.json] --out oracle.json` (`--config` names the
file inside the zone when the root is solution-style — `files: []` and
`references` build an empty program). Loads `typescript` **from the zone** when the zone has
one (the version the project pins, the environment lane B indexed
under), else the harness's own (`ts/package.json`, for fixtures without
`node_modules`). Builds the zone's program from its tsconfig, walks
every call-shaped node, `checker.getResolvedSignature` → declarations,
normalised per the conventions above. Kind `resolution`: no roots;
recall is over every resolved site in the zone. Zones declined at
ingest (C-34) are declined here for the same reason.

Sites carry a **mode** derived from the binding's shape, so the miss
classes read the same as Go's: `interface` when the callee is a type
member (an interface property signature), `func-value` when it is a
parameter, a local binding, or a variable with no function literal
behind it, `static` otherwise. Targets carry a **kind** — function,
method, class, variable, property, parameter, type-member, closure,
local-binding, anonymous-function — and the miss record groups by
mode × kind.

## The Python trace oracle (`py/trace_oracle.py`, D-O5)

`oracle py-trace --repo <repo> --module <dir> --python "uv run --project
<dir> python" --runs N --out oracle.json -- <pytest args>` runs the
directory's own pytest suite under `sys.monitoring` (PEP 669, CPython
3.12+) — one subprocess per run, unioned — recording every `CALL` event
whose caller is a `.py` file under the cell: site = the call
instruction's start line, target = the callee's declaration mapped
through an `ast` index (so a decorated function's line is its `def`,
not `co_firstlineno`'s decorator). Callers outside the cell (pytest,
site-packages, the import machinery) are `DISABLE`d at their first
event, which is what keeps the overhead near zero. C callees are counted
per site, not listed. Subprocesses the suite spawns are not traced. The
interpreter must be the target's own (`--python`), run from the cell
directory; pin `--rootdir`/`-c` when the target sits under another
project's pytest configuration.

## The Rust MIR oracle (`rust/`, D-O6)

`oracle rust-mir --repo <repo> --module <cargo-package-dir> --driver
rust/target/release/mir-oracle --out-dir <cell>` runs `cargo +nightly
check --all-targets` with the driver as `RUSTC_WRAPPER` in a fresh
target dir (a cached check would skip the crate and the cell would read
empty). For every workspace crate target — lib, bins, each `--test`
build, examples, benches — the driver runs the real compiler through
`rustc_driver` and, after analysis, walks every body's MIR: each `Call`
terminator is a site (line of `fn_span`, the callee without receiver;
`source_callsite` for macro-expanded calls), resolved with
`Instance::try_resolve` — the compiler's answer after monomorphisation
where the caller is monomorphic. `dyn` calls (`InstanceKind::Virtual`),
calls through a generic bound the caller's own generics leave open
(`Ok(None)`), and function pointers are `dynamic`, carrying the trait
method as `interface` where one exists. Generic instantiations collapse
to the origin `DefId` by construction. "External" is by file: `mylib::f`
called from the same repo's bin crate is in-repo. Per-target files are
merged (a lib compiled for itself and again for its tests reports the
same sites twice). Needs the nightly pinned in `rust/rust-toolchain.toml`
with `rustc-dev`; the exact `rustc -vV` is stamped into every export,
because a different nightly is a different oracle.

## The Java javac oracle (`java/`, O8, ADR-096)

`oracle java-javac --repo <repo> --module <build-root> --plugin java
--out-dir <cell> [--tool maven|gradle]` builds the `HobbesOracle` javac
plugin jar in the sandbox image (once per cell dir; `java/build.sh`,
JDK only) and runs the repo's build with it attached — Maven through
the wrapping `java/javac-oracle.py` (`-Dmaven.compiler.executable`,
`fork=true`; argument files expanded, the jar joined to the processor
path or the class path), Gradle through the `java/hobbes-oracle.gradle`
init script (a toolchain forbids a forked executable, so the plugin
rides the processor path and the JVM export rides the compiler daemon's
args). One shard per compilation unit (`<cell>/javac-shards/`):
declarations keyed `owner#name(erased params)` with their name line,
the class hierarchy, and every site with its resolved key and mode
(`static` / `dynamic`). The merge joins keys across shards, resolves
targets, and for a dynamic site adds the CHA override set below the
declared owner with the declared method as `interface`. Kind
`resolution`, no roots; `Roots` names the build tool. Runs contained
**with a network** (C-66): the build resolves its own dependencies —
the single-pass shape the ingest lane replaced with ADR-097's two passes;
bench tooling keeps it until someone needs the narrower form.
The `minijava` fixture is the self-test (`internal/grade/java_test.go`,
skipped without the image).

## The C oracle (`internal/clang`, O9, ADR-110)

`oracle c-clang --repo <repo> --module <build-root> --out-dir <cell>
[--compdb path] [--clang clang] --out oracle.json` runs clang's own
front end, one translation unit at a time, over the compile database
ADR-109's ingest derives — the same key `tsc` and javac already are: the
compiler is the authority on what a call *names*, and what the cell
grades is everything Hobbes adds above it.

**The dump reader** (`ReadDump`) decodes one unit's `clang -fsyntax-only
-Xclang -ast-dump=json` output as a token stream, in document order,
never a whole-document unmarshal — a real dump is 25-35 MB, almost all
system headers. The dumper omits a location's `file` and `line` when
they repeat the previous location's, so the reader carries them
forward; an object whose first key is `offset` is a location, an
`includedFrom` object is not, and neither ever moves that carried
state. A `CallExpr` whose callee — peeled through `ImplicitCastExpr`,
`ParenExpr` and a unary `*`/`&` — is a `DeclRefExpr` naming a
`FunctionDecl` is a direct call, mode `static`; anything else is
`dynamic`. A callee that is itself a call (`get_fn()(2)`) is recorded in
its own right, never dropped mid-peel, and the outer call through its
result is the dynamic site. clang's pseudo-buffers (`<scratch space>`,
`<built-in>`, `<command line>`) are never files and never enter `Files`;
a chosen macro position that lies in one takes the expansion instead,
mode `macro` (the macro rule is stated fully under Normative
conventions above).

**The definition join** (`Merge`) joins every shard's declarations by
name to resolve linkage (internal/external, static-with-no-in-repo-trace,
link-ambiguous, undefined, tu-split — Normative conventions above), and
unions each site's targets across the shards that share it. Site
identity is (site path, line, column, spelling path, line, column, mode,
callee name); the counts by mode and no-target reason ride in the
export's `coverage` map, and `grade`'s report prints them as their own
line (resolution oracles only — a trace report already has one).

**The database and containment** (ADR-109's order, mirrored from the
ingest so the oracle grades what the product indexed): a carried
`compile_commands.json` at the build root or in `build/`, usable when
every entry's directory is relative or lies under the repo; else CMake's
own export (`cmake -S <root> -B <cell>/cmake-build
-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`); else bear over `make -k` in the
root (`bear --output <cell>/compile_commands.json -- make -k`; its exit
status is ignored, a database with no entries is the error); else
`--compdb <path>` names one directly and skips the search. Deriving a
database this way runs the repo's own build logic, and a build's
generated headers live only in its container's overlay — so deriving
and every unit's clang run happen in **one** contained, offline step
(profile `c-clang`, `internal/contain`): the oracle binary itself, built
static (`CGO_ENABLED=0`) and mounted read-only at its own host path,
invoked inside the sandbox image as the internal subcommand
`c-clang-units --repo --module --out-dir [--compdb] [--clang]`. It
writes one shard per unit under `<cell>/clang-shards/` — a unit clang
rejects is kept, `Failed` with the last 400 bytes of stderr, so it
grades not-loaded — plus `roots.txt` (the database's source and unit
count, then clang's own `--version` line). `oracle c-clang` then
`LoadShards` and `Merge`s them on the host.

The `cclang` fixture (`testdata/cclang`, hand-computed truth, its clang
dumps committed at `testdata/cclang-ast/` so the reader is tested
without the image) is the self-test (`internal/clang`, plus the
end-to-end `oracle c-clang` run, skipped without the image); the probe
fixture (`testdata/cclang-probe`) is a real clang 18.1.3 dump pinning
the pseudo-buffer rule, the two-site callee-that-is-a-call, and the
static-with-no-in-repo-trace rule exactly (`probe_test.go`).

## Guards in the extractors (RR-1, A-5, A-6)

Every walk-down step in `ts/tsc-oracle.mjs` goes through `descend(from,
to, what)`, which throws with a file:line when a step makes no progress
— the H-17 hang (`e = e` on an element-access callee) as a stack trace.
The visitor runs in a worker thread under a watchdog: when no site has
been visited for `--watchdog` seconds (default 120; `0` disables) the
driver prints the last position and exits 3. The Go extractor has no
hand-written walks (RTA is a library call); the Rust driver's two
context walks already stop on a fixed point (`parent == ctxt`).

A cell with nothing to grade prints as its own state (RR-6, A-1): a Go
module with no `main` and no tests yields `state: "no-roots"` and the
report line `recall: NOT GRADED — no roots exist`, never an empty grade
(`testdata/noroots`). Cell membership is one predicate for both sides,
`edges.Under` / `edges.Excluded` (RR-3, A-2); an empty list serialises
as `[]`, never `null` (A-3).

## Fixtures and testdata

`pipeline/tests/fixtures/minigo` (one module, 5 in-repo calls, all
static), `pipeline/tests/fixtures/twomod` (two modules joined by a
`replace`, one interface-dispatch call), `pipeline/tests/fixtures/minits`
(TS + JS under `allowJs`, four calls to one helper, decorators
unresolvable without deps, plus the three element-access shapes of
`src/lookup.ts`: one resolved in-repo pair Hobbes lacks, one external,
one computed-key silent), `pipeline/tests/fixtures/miniapp` (Python:
seven pairs observed under its two tests, a constructor among them; two
modules the suite never imports) and `pipeline/tests/fixtures/minirust`
(lib + bin + `#[cfg(test)]` + integration test: nine in-repo pairs, one
across the crate boundary, one inside the crate's own macro; one macro
invocation excluded) and `pipeline/tests/fixtures/minijava` (one Maven
module: an overload pair, a constructor chain and an implicit
constructor, an interface call with one CHA override, an anonymous
member, a lambda, a static import, three JUnit tests — eighteen in-repo
pairs) and `testdata/cclang` (a Makefile project: `main.c` + `lib.c`
build `app`, `tool.c` + `lib.c` build `tool` — 17 in-repo pairs, one
`tu-split` (`lib.c` compiled into both binaries), one external, one
`link-ambiguous`, one `undefined`, three dynamic, `orphan.c` not
loaded), with `testdata/cclang-probe` pinning the pseudo-buffer,
callee-that-is-a-call and static-external rules on a real clang dump.
Their hand-computed truth is the Go test suite
(the TS, Python and Rust tests shell out to node / `uv` / `cargo
+nightly` and skip without them; the C oracle's end-to-end test shells
out to `cmake`/`bear`/`make`/`clang` and skips without the image).
`testdata/*.graph.json` are the fixtures' Hobbes graphs as ingested
with lane B (`scip-go`, `scip-typescript`); regenerate with
`run-cell.sh` on a git-initialised copy of the fixture when the
extractor changes them.
