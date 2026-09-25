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

**`task`** — the task format of §5.2, one JSON-able record per cell (`lattice-task/2`). Everything the
files can say is filled here: the grid position, the signature, the slots, the neighbours' ids, the
static `helpers` defined above it and the file's `macros`. The fields the graph and the parser own —
`callees`, `contract`, `edge_cases`, `like` — are present and `null`. A record never carries the target's
path, so two checkouts of one SHA give the same bytes. **Two preludes**: `prelude` is the file's text
above the signature, which on a real kernel file contains the sibling cells' bodies; `prelude_bare` is
that text with every *other lattice cell's* body replaced by `;`, so each reads as a prototype. C-0, the
arm that carries no pattern, is built from the bare one — handing over five siblings one axis step away
is handing over exactly the shots C-2 is supposed to add (session `2fd4`'s review). Non-cell helpers keep
their bodies, and macros and includes are untouched.

**`run`** — where code may run. `in_container()` is true when `/run/.containerenv` or `/.dockerenv`
exists; `require_container()` raises `NotContained` — its own type, so a general handler cannot absorb it
(P10, ADR-036) — when execution is asked for outside one. `allow_host` is for this package's tests on its
own fixture and nothing else; the CLI never sets it. `image_plan(image, target, workdir, args)` returns
the `podman run` argv as pure data (`--rm --network none --security-opt label=disable`, the target `ro`
at `/target`, the work dir `rw` at `/work`, this `src/` `ro` at `/lattice` with `PYTHONPATH` on it), and
`run_plan` is the one place this package spawns a container.

**`build`** — **G-compile**. The target's `Makefile` flags as data: `-Wall -Wextra
-Wno-unused-parameter -O2` with `-I<root>/src -I<root>/libs`, plus `-mavx2 -mfma` for AVX2 and the four
`-mavx512*` for AVX-512; `cpu`, `sse2`, `neon` and `rvv` add nothing. `-Wno-unused-function` is this
package's own, because the fixture is trimmed and leaves helpers unused. **Warnings are not failures.**
One object per kernel file, linked with G-diff's driver and `-lm`; an `ObjectCache` keyed by the source's
text and its flags compiles the five files a body did not touch once per run. Diagnostics are parsed from
clang's `-fno-color-diagnostics -fno-caret-diagnostics` output into `(file relative to the root, line,
col, severity, message)`. `CC` from the environment, default `clang`.

**`hsr`** — **G-hsr** and the failure class. An invented name comes from clang's `call to undeclared
function 'X'`, `use of undeclared identifier 'X'` and `unknown type name 'X'`, and ld's ``undefined
reference to `X'`` — those four messages and nothing else. Each falls in one bucket: `intrinsic` (`_mm…`,
`__m…`, `__builtin_…` — the sand Atlas-0 measured), `in-repo` (kernel-shaped, or a name any target file
defines or `#define`s), `other`. The per-body class, in the order it is tested: `invented`, `compile`,
`not-installed`, `wrong` (a bulk case, a crash or a timeout), `edge` (every bulk case passes and an edge
case does not), `pass`.

**`diff`** — **G-diff**, the differential against `distance-cpu.c`, **through the table and never by
name**: the driver installs the scalar table, snapshots it, calls `init_distance_functions_<isa>()` and
reads the cell's `graded_via` slots back; a slot still holding the reference pointer was not installed
and is reported, never graded as a pass. That is the only route to AVX-512's `static` hamming and to
every `static inline` `_impl`. The driver is generated C with the case list compiled in: **bulk**
`n ∈ {64, 256, 1024, 4096} × 8 seeds`, **edge** 15 ragged sizes plus the special values at `n ∈ {17, 64}`
(one inf, inf in both with the same and opposite signs, NaN, a zero vector, large magnitudes; the
extremes for uint8 and int8; all-`0x00` against all-`0xFF` for bit1). Inputs come from splitmix64 seeded
per case, values print with `%.9g`, and `inf`/`nan` print as strings so the JSON stays valid. **The
comparison is in Python** and the tolerance table is data per `(type, metric)`: both NaN equal, both the
same infinity equal, otherwise `|ref - got| <= atol + rtol·|ref|`. Five rows are widened off the floor,
and the comment beside each says why: the scalar `int8` and `uint8` kernels accumulate in `float` while
every SIMD kernel accumulates in int32, so the **reference** is the imprecise side — worst observed
1.06e-6 (`int8/l2_squared`) and 5.09e-7 (`int8/l2`) on the fixture's golds, 1.05e-6 (`uint8/l2_squared`,
45930488 against 45930440) and 1.45e-6 (`uint8/dot`, −66351128 against −66351032) on the real target's,
all five now at rtol 1e-5.

**Two references, and `reference_for` says which** (the rule). `distance-cpu.c` is the reference for every
case whose answer it has. It is *not* the reference for a case whose **inputs hold a non-finite value**
(the specials `inf_a`, `inf_both_same`, `inf_both_opposite`, `nan` — the flag is `Special.non_finite`, on
the case table's data) or whose **scalar result is itself inf or NaN** (`large` overflowing, a zero
vector's cosine): those are graded against **the cell's own gold**. The reason is the target, not the
tolerance — on a non-finite input sqlite-vector's f16 and bf16 SIMD kernels disagree with its scalar
kernel *and with each other*, per ISA (`COSINE:BF16` answers 1 where the scalar answers NaN; `DOT:BF16`
on `large` answers NaN on AVX2 and AVX-512 and **+inf on SSE2**; AVX-512's `L1:F16` agrees with the
scalar on `inf_both_same` where SSE2's and AVX2's do not). No one semantics exists for those cases
because the target does not have one, so the graders ask the only question that has an answer — *does
this body do what the kernel it replaces does* — and the disagreements are **reported, never hidden**
(`selftest`'s `disagreements`). Each slot's counts say how many cases each reference graded, and
`first_failure` names the reference the failing case was graded against.

**`grade`** — the whole pass for one entry (`{"id", "cell", "body"}`, `body` a body's text or `"gold"`):
punch, fill, compile, link, run, classify. An unbalanced body is a `compile` **result** with the reason,
never an exception. The staged copy (only `src/` and `libs/fp16/`) is made once and reused, which is what
makes the object cache work. Each result carries the class, the first 20 diagnostics, the invented names
with their buckets, the bulk and edge counts, the first failing case, **G-reg** (the init function's slot
assignments in the filled file equal the gold's), the timings and the `feedback`. **The gold references
come first:** before the first body is filled in, while the staged copy is still the target's own bytes,
the gold is built once and its driver run over every slot each ISA the run touches installs. Those records
are what the gold-referenced cases are compared against, and they carry the cases where that gold and the
scalar disagree (`GoldReference`; `grade_with_references` hands them back for the self-test's report). A
gold that does not build, does not link or dies in the differential is `GoldUnavailable` — its own type,
because unlike everything else here it is not a fact about a body.

**`feedback`** — the ≤1,500 characters a model is shown on a retry, built from the graded result's
**structured fields only**: the first compile errors with target-relative paths, or the first failing case
with its `n`, expected and got, plus the invented names. Never raw compiler output, which carries this
box's absolute paths.

**`selftest`** — the gate on the instruments (§5.5). For each native cell the gold must read `pass`, and
four mutants of the gold body must read exactly what they are damage of: `syntax` (its last `;` removed)
→ `compile`; `invented` (`(void)_mm_lattice_invented_ps(0);` first) → `invented`, bucket `intrinsic`;
`wrong` (every `return EXPR;` → `return (EXPR) * 1.5f + 1.0f;`) → `wrong`; `edge`
(`if (n % 64 != 0) return -12345.0f;` first) → `edge`, which works because every bulk size is a multiple
of 64 and most edge sizes are not. An `_impl`'s mutants are graded through its wrappers. The report lists
every cell and mutant with expected against got, and the gold's worst relative error per
`(type, metric)` — the margin the tolerance table is running on, over the scalar-graded cases, which are
the ones a tolerance is a question for. It also lists **`disagreements`**: per ISA and slot, every case
where the gold and the scalar disagree, with both values and the reference that case is graded against,
and the table prints the count. A `gold` row is a fact about the target, not a failure of the instruments —
`ok` does not depend on them, and they go into the design's record; a `scalar` row is counted separately,
because there the tolerance table is what has to answer. Non-zero exit on any mismatch.

**`cli`** — `lattice map <target> [--json]`, `lattice task <target> <cell-id>`,
`lattice punch <target> <cell-id>`, `lattice grade <target> <manifest.json> [--out results.jsonl]`,
`lattice selftest <target> [--cells id,id,…] [--out report.json]`. A cell id is `<isa>/<type>/<metric>`;
a manifest is a JSON list of entries (or an object with them under `entries`). The two grading verbs take
`--here` (this process is contained already) or `--image NAME` (the default `hobbes-session:local`: build
a plan and run this same CLI inside it). `--here` outside a container exits 2 with the refusal.

Everything that compiles or runs the target's code runs in the image (ADR-092, C-64). Still to come, in
the unit after this one: the rename shadows, G-graph, G-test, G-mem, and the model calls.

```sh
# on this box, in the image
lattice selftest /path/to/sqlite-vector --image hobbes-session:local
lattice grade    /path/to/sqlite-vector manifest.json --out results.jsonl
```
