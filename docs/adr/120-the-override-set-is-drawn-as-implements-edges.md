# ADR-120 — The override set is drawn: SCIP `relationships` become `implements` edges

**Date:** 2026-09-16 · **Status:** accepted · **Owner:** Max · **Source:** Max, 2026-09-16 ("proceed with … decode SCIP relationships and draw implements edges … measure which indexers populate it first"), the top-level review's first recall recommendation.

Amends architecture **§3.4** (a fourth symbol edge type) and narrows
**C-58** (the override set it said Hobbes lacks is now in the graph).
Registers **C-157** (rust-analyzer states no override set). Helper
version 5. Patch: what the layer draws and says.

## Context

C-58 is the largest recall hole on every language: a call through an
interface method draws an edge to the *declared* target and nothing
below it, so `who_calls` on an implementation reached only through its
interface answers *nobody*. The entry says why — Hobbes runs no type
hierarchy analysis — and adds, under P9, that SCIP indexers "resolve
declarations, not dispatch". That second sentence was half right. A
SCIP index carries, beside each document's occurrences, a symbol table
(`Document.symbols`, one `SymbolInformation` per symbol), and each
entry lists `relationships` — among them `is_implementation`, the
proto's own name for "this symbol implements or overrides that one".
The helper read an occurrence's range, symbol and roles and skipped
every other field of every message, so the override set arrived in
every index and was thrown away in every decode.

## The measurement, first

Max asked which of the six indexers populate the field before anything
was drawn. A probe helper (`~/.hobbes/bench/relationships-probe/`,
`keep_probe.py` + `helper-keep-index.mjs`) ran this repo's ingest
contained and kept every raw `.scip` the six indexers wrote before the
decode removed it; `measure_relationships.mjs` then read every
`SymbolInformation` and `Relationship` of each, and ScummVM's stored
scip-clang index (`stage/b7bc0819382fd513.scip.units/whole.scip`) for a
large C++ answer. `pairs.mjs` prints every pair with its flags.

| Indexer | Pairs stated | Shape | In-repo pairs here |
|---|---|---|---|
| scip-clang 0.4.0 | 9 (fixtures); **49,912 on ScummVM**, 49,550 in-repo | class → base (`is_implementation`), method → overridden (`+ is_reference`), once per translation unit | 9 |
| scip-go 0.2.7 | 39 | struct/type → interface, method → interface method spec (`…/Journal#Park.`) | 9 (30 to the stdlib: `io.Closer`, `fmt.Stringer`, `flag.Value`, …) |
| scip-java 0.0.0-SNAPSHOT (the image's pin) | 11 | class → super/interface, method → overridden, **and the reverse row on the abstract method** (`Shape#area().` → `Circle#area().`, `is_reference + is_implementation` both ways); anonymous classes as `local N` | 6 |
| scip-typescript 0.4.0 | 8 | class → base, method → base method | 6 |
| scip-python 0.6.6 | 49 | class → base; method → overridden (5, all to the stdlib) | 2 (47 to builtins and the stdlib) |
| rust-analyzer 1.97.1 | **0** | no `relationships` on any symbol | 0 |

Every indexer but rust-analyzer states the set, and the proto's
convention holds — the relationship sits on the *implementor*
(`Dog#` carries `{symbol: "Animal#", is_implementation}`) — with one
exception: scip-java adds the reverse on an abstract or interface
method so an editor's "find implementations" on the interface finds
them. Flags do not tell the two rows apart (both carry both), so the
orientation has to come from somewhere else.

## Decision

**1. The helper decodes the override set (helper version 5).** Of a
`Document`, field 3 (`symbols`) is read beside `occurrences`; of a
`SymbolInformation`, its `symbol` and `relationships`; of a
`Relationship`, its `symbol` and `is_implementation`. Nothing else —
documentation, kind, display name, signature — is decoded, and only a
symbol that implements something is kept, so a document's table costs
the decode its pairs and no more (ScummVM: 411,173 symbol
informations, 49,912 pairs).

**2. A pair is a row from the implementor's definition to the
implemented's** (`implementsRows`): `{file, line}` where the
implementor is defined, `{def_file, def_line}` where the implemented
declaration is, both taken from the same `definitions` map the
references resolve through — so a pair whose target is outside this
index (a stdlib interface, a sibling unit's) draws nothing and is
counted (`implements_outside`), and a pair whose source is no graph
definition (a `local`, a parameter, an ambiguous moniker) is counted
(`implements_unplaced`). Rows are deduplicated (scip-clang states a
base once per unit that sees it) and sorted, so the facts do not depend
on unit order.

**3. A mutual pair is oriented by the type level, or dropped.** When
the index states both `A#m → B#m` and `B#m → A#m`, the row kept is the
one whose owning type reaches the other's through the index's own
type-level pairs — transitively, because javac and scip-clang name an
overridden method by the class that *declares* it while the class row
names the *direct* base. A mutual pair no type-level row can orient is
dropped both ways and counted (`implements_undirected`), and the run
says so. Never guessed (ADR-007).

**4. The facts carry a fourth row kind.** `implements` rows ride in
each document's record and the trailer counts them, like the other
three (ADR-116); the three counts ride in the trailer's root fields. A
facts file whose trailer lacks the count is refused as a short file is.
`read_facts` turns each row into an `IMPLEMENTS` evidence site.

**5. The join draws it at semantic tier, lane B alone.** An
`implements` site is the index's statement between two definitions:
no syntax site claims it and no fallback stands in for it, so
`evidence.join` emits it as an `implements` fact as it does a `uses`
reference. `project` takes *both* ends as the symbol **starting at** the
line — the enclosing lookup a call uses would answer the class for a
method declared inside it — and draws `implements` between them. An
end lane A keeps no symbol for is counted (`implements_below_floor`),
never guessed: on this repo those are Go's interface method specs
(`Journal#Park.`), which lane A does not declare (C-9's floor, C-58).
The module-level dependency is still drawn, as it is for a call below
the floor.

**6. Where a user meets it.** The ingest summary counts `implements
edges` apart from calls and uses (C-76's rule) and prints one line for
every count that is not zero — below the floor, outside the repo,
unplaced, undirected. `graph.json` carries the four counts under
`implements`. `who_calls` lists the edges into a symbol under their own
heading, "implemented or overridden by", neither counted as callers nor
dropped (P8), and the heading says a call to the symbol may reach any
of them and that which one is not traced (C-58). `hobbes diff` counts
`implements` beside calls and uses; `hobbes plan` weights the edge at
0.8, as an import. Rust says on every run that rust-analyzer states no
override set (C-157).

**7. Not this change.** Expanding a call to an interface method into its
overrides — the recall lever the review named second, "as a labelled
step" — is a change to what `who_calls`, `tests_guarding` and every
derived context count as reach, and to ADR-007's rule that reach
follows `calls`. It needs its own ADR, with the oracle question
answered first: the RTA and CHA keys judge a call by its concrete
targets, and an edge the expansion draws is either confirmed by them or
the first *inferred* edge in a graph that has none. The override set is
now in the graph for that decision to be made against.

## Measured

This repo at this change, contained: **18 `implements` edges**, all
read against their sources — minijava's `Circle → Shape`,
`Circle.area → Shape.area`, `Derived → Base`, `Derived.Inner → Base`;
minits' three `render` overrides and their classes; minicpp's and the
oracle's `Circle → Shape` at both levels; this repo's own
`PlanCoverageError → RunError`, `BenchGoFake → GoFake`,
`FileJournal → Journal`; and twomod's `MemStore → Store`, the example
C-58 opens with. Not drawn and said: 7 pairs below lane A's floor (Go's
method specs), 83 to declarations outside the repo, 0 unplaced, 0
undirected. The Python side reads the rows as it reads references; the
helper's decode is unchanged for every field it already read, and
every call and uses edge on this repo is the same as at 0.2.31-beta.

## Alternatives considered

- **Draw the reverse row too, or pick a direction by document order.**
  Rejected: a graph with `Shape.area implements Circle.area` in it is
  wrong in the way ADR-007 forbids, and document order is the
  indexer's, not a fact.
- **Declare Go's interface method specs as lane A symbols so the
  method-level pairs land.** Deferred: it is the right fix for the 7
  below the floor, but it also makes every SCIP-resolved call to an
  interface method a `calls` edge to that spec, which changes Go's
  graded cells and belongs to item 7's decision.
- **Match a pair to a sibling unit's definition in `join_cross_unit`.**
  Deferred: the 83 outside pairs here are all the stdlib's; a Go
  interface satisfied across two modules of one repo is real and
  unmeasured, and the count says how many there are when it happens.
- **Cross-index rust-analyzer's `impl` blocks from lane A.** Rejected
  for now: a trait impl in Rust is a syntactic fact lane A could state
  at syntactic tier, but the method-to-trait-method pair needs the
  trait resolved, which is lane B's job and lane B is silent (C-157).

## Consequences

- Helper version 5 on both sides; a facts file from version 4 is
  refused by the version check that already exists.
- `graph.json` gains a top-level `implements` block and a fourth
  symbol edge type; schema v4 is additive here, as `built_by` and
  `containment` were.
- C-58 narrows: the override set is drawn, the dispatch expansion is
  not. C-157 is registered, surfaced on every Rust run.
- Register: 157 entries, 114 active (87 surfaced).
