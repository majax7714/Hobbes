# bench/oracle — grading the call graph against answer keys Hobbes does not control

The oracle-grading lane (ADR-089; design in `docs/oracle-grading.md`).
Bench tooling only: its own Go module, no product code, one binary with
cells as data. It exists to give the extraction layer two numbers it has
never had — **precision-against-oracle** and **recall** — from an edge
source that is independent of Hobbes, authoritative for the language,
and regenerable by anyone with the toolchain.

```sh
cd bench/oracle && go test ./...            # fixture self-test: minigo + twomod (Go), minits (TS), miniapp (Python), minirust (Rust)
cd bench/oracle/ts && npm install            # once: the fallback typescript for fixtures
cd bench/oracle/rust && cargo +nightly build --release   # once per nightly: the MIR driver (rustc-dev)
bench/oracle/run-cell.sh <repo> <module-dir> <out-dir> [--lang go|ts|py|rust] [--no-ingest] \
    [--python "<cmd>"] [--runs N] [--sys-path a,b] [--features f] [-- <pytest args>]
```

`run-cell.sh` ingests the repo with lane B, exports the Hobbes edges of
one cell, runs the language's oracle on it, grades, and leaves
`hobbes.json`, `oracle.json`, `report.json`, `report.txt` and the cell's
runtime in the output directory. The steps are the binary's subcommands
(`oracle export | go-rta | py-trace | rust-mir | grade`) if you need
them apart; the TS oracle is `ts/tsc-oracle.mjs`. Phase 1 (ADR-089) is
Go and TS; phase 2 is the Python trace oracle and the Rust MIR oracle
below.

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

## Buckets and metrics

For a resolution or reachability oracle, every Hobbes `calls` edge lands
in exactly one bucket:

| bucket | meaning |
|---|---|
| **confirmed** | the oracle has the same (site, target) |
| **contradicted** | the oracle resolved that site and Hobbes' target is not among its targets — very strong evidence, not proof (RTA is unsound under reflection, `go:linkname`, plugins, cgo) |
| **abstract** | the site is a dynamic dispatch and Hobbes' target is the *interface method's* declaration — right at the declaration grain, not a concrete target. Reported on its own, in neither precision term; the concrete oracle pairs at that site count as misses (D-O3) |
| **silent** | the oracle could not speak: `not-loaded` (file outside the loaded program — build tags, orphan directories), `unreachable` (no reachable function holds a call on that line), `no-targets` (reachable, RTA resolved it to nothing). Charged to nobody, printed at full size |

- `precision-against-oracle = confirmed / (confirmed + contradicted)`
- `recall = confirmed in-repo oracle pairs / all in-repo oracle pairs`,
  always printed with its **root count** (Go) — recall is driven by the
  roots the oracle had and is never pooled or compared across cells.
  External targets (stdlib, module cache) are out of the denominator and
  counted separately (D-O3).
- Every cell reports the pair together, the silent size, the per-tier
  split (semantic / syntactic / dynamic), the miss decomposition
  (`static`, `dynamic`, `*-closure`), and the raw contradicted / abstract
  / missed rows — the triage queue.

Every defect found in the harness or an oracle is logged in
`docs/oracle-defects.md` with what it would have cost unnoticed.

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

## Cell records (`docs/oracle-cells/`)

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

`node ts/tsc-oracle.mjs --repo <repo> --zone <dir-with-tsconfig> --out
oracle.json`. Loads `typescript` **from the zone** when the zone has
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

## Fixtures and testdata

`pipeline/tests/fixtures/minigo` (one module, 5 in-repo calls, all
static), `pipeline/tests/fixtures/twomod` (two modules joined by a
`replace`, one interface-dispatch call), `pipeline/tests/fixtures/minits`
(TS + JS under `allowJs`, four calls to one helper, decorators
unresolvable without deps), `pipeline/tests/fixtures/miniapp` (Python:
seven pairs observed under its two tests, a constructor among them; two
modules the suite never imports) and `pipeline/tests/fixtures/minirust`
(lib + bin + `#[cfg(test)]` + integration test: nine in-repo pairs, one
across the crate boundary, one inside the crate's own macro; one macro
invocation excluded). Their hand-computed truth is the Go test suite
(the TS, Python and Rust tests shell out to node / `uv` / `cargo
+nightly` and skip without them).
`testdata/*.graph.json` are the fixtures' Hobbes graphs as ingested
with lane B (`scip-go`, `scip-typescript`); regenerate with
`run-cell.sh` on a git-initialised copy of the fixture when the
extractor changes them.
