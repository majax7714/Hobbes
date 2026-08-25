# bench/oracle — grading the call graph against answer keys Hobbes does not control

The oracle-grading lane (ADR-089; design in `docs/oracle-grading.md`).
Bench tooling only: its own Go module, no product code, one binary with
cells as data. It exists to give the extraction layer two numbers it has
never had — **precision-against-oracle** and **recall** — from an edge
source that is independent of Hobbes, authoritative for the language,
and regenerable by anyone with the toolchain.

```sh
cd bench/oracle && go test ./...            # fixture self-test (O1): minigo + twomod
bench/oracle/run-cell.sh <repo> <module-dir> <out-dir> [--no-ingest]
```

`run-cell.sh` ingests the repo with lane B, exports the Hobbes edges of
one Go module, runs the Go RTA oracle on it, grades, and leaves
`hobbes.json`, `oracle.json`, `report.json`, `report.txt` and the cell's
runtime in the output directory. The three steps are the binary's
subcommands (`oracle export | go-rta | grade`) if you need them apart.

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
  position only. (TypeScript's overload rule — any declaration of the
  resolved symbol counts — lands with the `tsc` oracle at O3.)
- **Package initialisers are in the graded set.** `init` and
  package-level var initialisers are reachable from every main and their
  calls are real calls.

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

**Triage verdicts** for contradicted rows (design §8): *hobbes-wrong*
(extraction defect → issue), *oracle-unsound* (logged, not charged),
*match-defect* (fix the matcher, rerun). A cell's number is final only
after its triage is complete or a sampled triage is documented as sampled.

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

## Fixtures and testdata

`pipeline/tests/fixtures/minigo` (one module, 5 in-repo calls, all
static) and `pipeline/tests/fixtures/twomod` (two modules joined by a
`replace`, one interface-dispatch call). Their hand-computed truth is the
Go test suite. `testdata/*.graph.json` are the fixtures' Hobbes graphs as
ingested with lane B (`scip-go`); regenerate with `run-cell.sh` on a
git-initialised copy of the fixture when the extractor changes them.
