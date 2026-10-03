# ADR-163 — A fact at a later def of a Rust id two impl blocks share is refused

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: the **narrow** route over the wide one first
recommended) and **built** (0.2.87-beta) · **Owner:** Max · **Source:** the duplicate-qualname measurement of
2026-10-02 (`~/.hobbes/bench/dup-qualnames-2026-10-02/RESULTS.md`), then this ADR's own step 0
(`~/.hobbes/bench/c180-rust-impl-qualnames/`: `measure.py`, `narrow.py`, `rows.py`, the before and after
reports).

Contains **C-180** (registered with this ADR). Draws less: it removes rows and adds none. Precedent 1: an
unregistered limit that drew a false edge.

## What is wrong

`rustsource._impl_type` names an `impl` block after its first type identifier, and a method's qualname hangs
off that name. Two differently written blocks in one file then mint one symbol id:

- `impl<T> Pointer for *const T` and `impl<T> Pointer for *mut T` both give `T.distance` (memchr `src/ext.rs`);
- `impl From<&str> for Id` and `impl From<String> for Id` both give `Id.from`;
- a trait impl and the inherent impl of one type share every method name they both declare
  (`impl Address { fn id }` and `impl Node for Address { fn id }`, dagger's generated `gen.rs`).

The first def of an id is its node (`graph._symbol_records`, `_merge_symbols`). A later def is a different
function with no node of its own. Before this ADR:

- **A call written in a later def was filed under the node.** memchr `ext.rs:33`, inside the `*mut T`
  `distance`, calls the `*const T` one; the graph drew `T.distance calls T.distance`, a recursion that does
  not exist, at `semantic`. The compiler key graded it confirmed because it judges the site and the target,
  never the caller. On dagger's `sdk/rust`, 229 confirmed rows were such calls, merged into the inherent
  methods' nodes.
- **A lane B `uses` with no lane A scope was filed under the module.** That was 217 rows in dagger's `gen.rs`.
- **A call resolved onto a later def's line fell `below-floor`.** These were dagger `functions.rs` 469/501/533,
  calls of the second `Vec.has_optionals`, which `oracle-misses.md` blamed on C-58/C-9.

Python's ADR-155 is the opposite case: there a later def rebinds one name, and its lines are the node's.

## Measured (step 0, no code changed)

There are two containments, each graded against the stored keys on the 0.2.86-beta graphs (`narrow.py`). Both
exclude a qualname whose defs all carry the same header text, such as a cfg twin.

| route | memchr confirmed rows refused | dagger `sdk/rust` confirmed rows refused |
|---|---:|---:|
| **wide:** every edge whose caller or callee is a colliding id | 88 of 921 | 559 of 3,592 |
| **narrow:** only facts written inside, or resolved onto, a *later* def | 2 of 921 | 229 of 3,592 |

The wide route's extra rows are true. On memchr, 86 are calls into the `*const T` impl's `distance` and
`as_usize`, the def the node sits at. On dagger, 330 are calls into or out of the first defs. Refusing them
would draw less than the evidence proves, which no honesty rule asks for. The narrow route refuses exactly
the rows whose caller is wrong (memchr's two self-loops, dagger's 229) and nothing whose ends are right.

Other measured facts:

- **Colliding ids.** memchr has 169 (167 in `benchmarks/haystacks`, a copy of the standard library's source
  kept as search input; 2 in `src/ext.rs`). dagger's `sdk/rust` has 104 (102 in `gen.rs`). memchr has 161
  identical-header twins; dagger has none.
- **Reproduced on a fixture.** A small fixture of each shape reproduces all three behaviours under a
  lane B ingest (`minirustimpl`: memchr's `ext.rs` verbatim, dagger's two shapes small, memchr's cfg twins).

## The decision (Max: narrow)

1. **Lane A keeps each Rust symbol's `impl` header**: the block's text up to its body, whitespace collapsed.
   `rustsource.shared_qualnames` lists every id with two or more defs in one file whose headers are not all
   the same, with each def's span. A cfg twin, the same header written twice, is not listed and stays the
   node's, as before.
2. **At the projection**, for every fact from either lane, after the module edge it raises is recorded:
   - if its site lies inside a later def of a listed id, that is, a def other than the one the node sits at;
   - or if its definition line is the start of one;

   then the fact is **refused**. It draws no edge and files no row under the node, the module or anything
   else. The module edge stays, because the two files do reference each other.
3. **Counted where a user meets it.**
   - A refused call site is tailed **`shared-qualname`**, a new class that is Rust's alone. A site lane B
     resolved is added, as `qualifier-mismatch` is. A site only lane A answered was already counted
     `fallback-resolved`, whose edge it no longer has, so it moves to the new class and the per-file sum
     holds.
   - The class's meaning names this ADR and C-180 in the ingest summary, `list_blind_spots` (`tailMeanings`)
     and the gate's map reasons (`_TAIL_REASON`).
   - One `rust-qualnames` degradation record per ingest with a listed id gives the count of ids, the refused
     calls and other references, and up to three examples.
4. **Untouched:** every node, every edge into a first def, and every edge written in one. No id changes.

## Not taken

- **The wide route** (refuse every edge touching a colliding id). It is recorded above with its cost: 86
  and 330 true rows.
- **The prevention:** ids that tell the blocks apart, either Java's `~n` ordinal (ADR-096) or a self-type
  that keeps the pointer or reference text and the trait (`T.distance` → something like `*mut T.distance`).
  It changes symbol ids, which every stored export, key mapping and record keyed by id would feel, so it is
  a design decision for Max. It is open in `currently-open.md`. Built, it would give each later def a node,
  and C-180 would lift.

## What it costs

A header string per Rust symbol during the walk, and a span check per fact at the projection, which is free
where no listed id exists. The rows refused are listed above; nothing else is expected to move.

## What this leaves

C-180, surfaced: a later def of a shared id has no node, so what is written in it, or calls it, is not drawn.
It is counted and named instead.

## Built (0.2.87-beta)

As decided:

- `rustsource` (`_impl_header`, `RustFile.defs`, `shared_qualnames`, the bundle's `shared_qualnames`).
- `scipsource.project` (`shared=`, `_SymbolIndex.shared_def`, the returned `shared_qualname` rows).
- `extract/__init__` (`_shared_later_defs`, the tail relabel, `_shared_qualname_record`).
- `tail.SHARED_QUALNAME`, `knowledge.go`, `gate.py`.

Tests are in `test_shared_qualnames.py`, on the real-source fixture `minirustimpl`:

- the self-loop is not drawn and is counted;
- a call onto a later def is `shared-qualname`, not `below-floor`;
- the first def still draws;
- the cfg twin still draws;
- lane A's relabel keeps the per-file sum;
- the nodes are unchanged;
- a `lane_b` case runs the whole ingest on the host.

The regrade is in this ADR's run directory. Its numbers are in the CHANGELOG entry and the cell records.
