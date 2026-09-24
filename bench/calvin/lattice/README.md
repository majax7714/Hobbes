# lattice — the Calvin experiments' E0 instruments

Bench tooling for `docs/calvin/calvin-experiments.md` (ADR-151): sqlite-vector's SIMD kernel lattice,
the holes punched in it, and the graders a model's body goes through. Never product, never versioned.

```sh
cd bench/calvin/lattice && uv sync && uv run pytest
```

The real-source fixture is `tests/fixtures/sqlite-vector-kernels/` (`PROVENANCE.md`). The target itself is
a checkout outside this repo. Anything that runs its code runs in the sandbox image.

## The modules

**`scan`** — a hand scanner for C text, not a parser. It masks what cannot hold code (comments, string
and character literals, preprocessor lines, a `#define` continued over `\`) and then walks the top level
for a `)` followed by a `{`, returning each definition's name, signature, spans and `static`/`inline`
flags, plus the file's `#define` names. Its docstring names what it reads wrongly rather than refuses:
K&R definitions, a definition produced by a macro, a declarator returning a function pointer. Offsets
are character indices into the text given, not byte offsets — the target's comments are not all ASCII.

**`cells`** — the lattice itself. `build(target)` reads `src/distance-*.c` into a grid of
`(type, metric, isa)` cells, each with its name, file, spans, `kind`, `static`, the
`dispatch_distance_table` slots its init function assigns it, and `graded_via` — its own slots, or for
an `_impl` the slots of the wrappers that reach it, because an `_impl` has no slot of its own. A wrapper
is recognised by its one-statement body calling this type's `_impl`, never by its name. `sse2`, `avx2`
and `avx512` are `native`: this box runs them. `cpu` is the numeric reference and `neon`/`rvv` are
mapped and marked not native. The real source's quirks are carried, not smoothed: AVX-512's
`bit1_distance_hamming_avx512` is `static`, and NEON spells its int8 helper `int8_distance_l2_neon_imp`,
which maps to `(int8, l2_impl, neon)` with the real name kept. `neighbours(cell)` walks one step along
each axis in a documented order (ISA, then type, then metric). A kernel-shaped name the grid cannot
place goes to `Lattice.unmatched` with its reason — silence would be the one failure mode a map must
not have.

**`holes`** — `punch(text, cell)` replaces a cell's body with `{ /* HOLE */ }` and leaves every other
byte alone; `fill(punched, body)` puts a body back. The property the tests hold is the round trip —
`fill(punch(t, c), gold_body(t, c)) == t` for every cell of every file — because a grader that cannot
restore the gold is measuring its own edit. A body that is not balanced braces is refused with
`UnbalancedBody`, not written.

**`task`** — the task format of §5.2, one JSON-able record per cell. Everything the files can say is
filled here: the grid position, the signature, the slots, the neighbours' ids, the `prelude` (the C-0
context above the hole), the static `helpers` defined above it and the file's `macros`. The fields the
graph and the parser own — `callees`, `contract`, `edge_cases`, `like` — are present and `null`. A
record never carries the target's path, so two checkouts of one SHA give the same bytes.

**`cli`** — `lattice map <target> [--json]`, `lattice task <target> <cell-id>`,
`lattice punch <target> <cell-id>`. A cell id is `<isa>/<type>/<metric>`.

Nothing in this package compiles or runs C. The graders (G-compile, G-diff, G-test, G-graph, G-reg,
G-hsr, G-mem) are the next unit, and they run in the image (ADR-092, C-64).
