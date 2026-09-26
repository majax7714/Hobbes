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

**`cells`** — the lattice itself. `build(target, rename=None)` reads `src/distance-*.c` into a grid of
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
not have. **`rename`** is a shadow's reverse map (new name → the target's own): the *grid* questions —
does this parse into `(type, metric, isa)`, which function is this file's init — are asked of the
original, and everything about the *file* stays what the file writes, so `Cell.name` is the shadow's
and `Cell.original` is the target's. Without it the two are the same string and nothing changes, which
also means a shadow read without its map has no cells at all rather than the wrong ones.

**`holes`** — `punch(text, cell)` replaces a cell's body with `{ /* HOLE */ }` and leaves every other
byte alone; `fill(punched, body)` puts a body back. The property the tests hold is the round trip —
`fill(punch(t, c), gold_body(t, c)) == t` for every cell of every file — because a grader that cannot
restore the gold is measuring its own edit. A body that is not balanced braces is refused with
`UnbalancedBody`, not written.

**`task`** — the task format of §5.2, one JSON-able record per cell (`lattice-task/3`). Everything the
files can say is filled here: the grid position, the signature, the slots, the neighbours' ids, the
static `helpers` defined above it and the file's `macros`. `callees` is filled from a `facts.Facts`
handed in, with `callees_source` beside it naming that ledger; the fields the parser owns —
`contract`, `edge_cases`, `like` — are present and `null`. Without a ledger `callees` and
`callees_source` are both `null`, which is the difference between "this cell calls nothing" and "nobody
was asked". A record never carries the target's
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

**Two more entry forms, both E4's, and the cell form unchanged beside them.** At rung L1 the whole file is
held out, so a hole is any of its definitions. `{"id", "unit", "isa", "body"}` is one definition: a **cell**
is graded exactly as the cell form grades it, with `unit` and `graded_over` beside the result; a **helper**
over the union of the `graded_via` slots of every cell whose gold body reaches it — `hsum256_ps` over the
float32 row and nothing else — and one no cell reaches is `UNEXERCISED`, compile-only, a class of its own
beside `hsr.CLASSES` because the empty union is a fact about the *unit* and not a verdict on its body;
the **init** over every slot the file installs, which is the one unit whose own job is to install them.
`{"id", "isa", "bodies": {name: body}}` is E4's **file-level** build: several bodies filled at once, graded
over every installed slot, with `filled_sha256` on the result so the bytes graded and the bytes written to
`final/` are one thing. Every form fills into the **gold** file and puts it back, so a wrong helper fails
on its own row and the cells that call it are still graded against the target's own (E4-d). The file's
definitions and the calls between them are read through `e4`, imported on use — the token rule is written
once, there, and most grading runs carry no unit entry.

**`feedback`** — the ≤1,500 characters a model is shown on a retry, built from the graded result's
**structured fields only**: the first compile errors with target-relative paths, or the first failing case
with its `n`, expected and got, plus the invented names. Never raw compiler output, which carries this
box's absolute paths. **A failing case names the reference it was graded against**, from
`first_failure["reference"]`: the scalar's wording for a `scalar` case, and "disagrees with the kernel it
replaces (the target's own gold; a non-finite case)" for a `gold` one — telling a model it disagrees with
the scalar on a case the scalar never answered would be telling it something untrue about this target. A
result with no such field keeps the old wording rather than being guessed at.

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

**`facts`** — **C-1, the facts arm** (§5.3): a cell's callees, read from the ledger and never from a
model's memory. Two instruments, because neither answers alone — **Hobbes' graph** has every in-repo
callee with a tier and `file:line` evidence and **no edge to an intrinsic** (`_mm256_fmadd_ps` is not
defined in the repo), and **the clang key** has every callee the compiler saw, intrinsics included, with
the `mode` a macro was reached through. The graph is asked first and the key fills what the graph cannot
see. Rows are in **first-use order**: the graph's by their first evidence line, then the key's by their
first site, with the macro-mode sites after the direct ones because the name is not written in the body
at all — `MM256_FMA_PS`, which is, already stands in the body's own order. A site is this cell's only
when its `pos.path` *and* its line inside the body span say so: the key's `caller` is a bare name and a
`static` name repeats across files. A callee both instruments name keeps the graph's row, the one with a
tier, and records the agreement as `"also": "clang-key"`. `Facts` is the ledger (graph, key, intrinsic
index; any of the three may be absent), and `Facts.source()` is its provenance.

**A shadow's facts are the target's, written forward** (E2-b). Neither instrument answers a rename
shadow: the graph matches a symbol by name, and the key matches a site by path, line **and column** —
a shadow changes the first and shifts the last two, so the target's ledger simply does not answer the
shadow's cells. `Translated(ledger, lattice, renames, map_sha256)` therefore asks the **original**
lattice's cell of the same grid id — a cell id is `<isa>/<type>/<metric>` and is the same in the target
and in every shadow — and rewrites the answer's code-naming fields (`name` and `signature` on a callee
row, `name` and `wrote` on a dropped one) with `shadow.apply`, the same renamer that wrote the shadow's
files. This is **exact by construction**, because a plan is a bijection or it is `Collision`. What is
not a name in the tree is carried as it is: the tier, the mode, the kind, the drop's reason. `missing`
and `dropped` are carried too — a gap in the target's ledger is a gap in the shadow's — and `source()`
is the wrapped ledger's with `translated_through`, the map's digest, beside it. The alternative,
re-deriving a ledger on the shadow, means a Hobbes ingest and a clang key per shadow and buys nothing
this reading needs.

**A header macro is named as the source wrote it** (session `189e`'s review of part 3). A key site in
mode `macro` names what the macro *expands to*, and that is two facts wearing one shape. Where the macro
is the repo's own, the expansion is the answer — `MM256_FMA_PS` really does fuse-multiply-add, and
`_mm256_fmadd_ps` stays. Where it is one of clang's, the expansion is compiler internals no one writes:
`_mm256_extracti128_si256` reports as `__builtin_ia32_extract128i256`, and `INFINITY` as
`__builtin_inff`. So the **written token at the site's own line and column** decides. A macro-mode
target survives only when that token is an in-repo macro — one the graph names, or one the cell's own
file `#define`s — or when the target is itself a *function* in the intrinsic index; every other one goes
to `Callees.dropped` with the reason, one row per expansion rather than per site. The header macros the
body does write are then added back from its own identifier tokens that the index marks `macro: true`,
with `provenance` `clang-headers:macro`, the index's `#define` line as the signature, and a place in the
body's own order beside the direct sites — unlike an expansion, they *are* written there. Without an
index none of that happens and `missing` says so. A `static`-mode target is untouched: a libm call and a
`__builtin_popcount` spelled out in the source are names the body really writes.

**`intrinsics`** — the inventory the sand is measured against (Atlas-0, §2): every `_mm…`/`_cvt…`
signature from **clang's own headers**, at the version that will compile the body. The two forms clang
writes are read — `static __inline__ <ret> <attrs>` with the declarator on the next line or on the same
one, and `#define name(args)` — and a function's signature is normalised to one line with the storage
keywords and the attribute macros (`__DEFAULT_FN_ATTRS256`, a written-out `__attribute__((…))`) dropped:
`__m256 _mm256_fmadd_ps(__m256 __A, __m256 __B, __m256 __C)`. A macro keeps its `#define` line, because
it has no type. A line scanner, not a preprocessor: it reads both arms of an `#if`, and it says so.

**`ages`** — cell age, a contamination instrument (§6's E0 card, C-39). `name_since` is since when the
file has defined the name and `body_since` since when the body at the ref has been byte-identical, both
walked **contiguously back from the ref** through `git log --format=%H %cI -- <file>` and `git show
<sha>:<path>`, every version found with this package's own scanner and not a regex, decoded with
`errors="replace"` (the target has a non-UTF-8 byte). No rename following, and a version the scanner
cannot read stops the walk — the age reported is the shortest the evidence supports. Dates are the
committer date to the day, which is the grain the quarter counts are read at; `identical_at` is that
count. **The cells come from git, not from a working tree**: with no lattice handed in, `cells_at` reads
`src/distance-*.c` at the ref with `git show` into a scratch directory and builds the lattice there, so
a **bare clone** — the shape a contamination run actually has — answers instead of reporting "ages of 0
native cell(s)". That was the choice of the two on offer, and the refusal is kept for what is left: a
ref whose tree holds no kernel file at all raises `NoKernelsAtRef`, and `lattice ages` exits 2 with the
reason. A lattice handed in is used as given, which is how a caller asks about a working tree on purpose.

**`gmem`** — **G-mem**, the memorisation probe (§5.5). The prompt is `prelude_bare` plus the signature
plus the gold body's first K lines, `K = max(2, ⌊lines/4⌋)`; the expectation is the rest of the body,
and `score` is the share of its whitespace-split tokens the completion continues **in order from the
start** — a prefix measure, not a similarity. `label` reads above 0.5 as `memorised` and below 0.15 as
`unseen`; **those two lines are borrowed from ADR-099's navigation probe**, which asked where things are
rather than for code, so they are a convention here and the middle band is named `neither`. `run` takes
a `complete(prompt) -> str` callable — the only place a model would appear — so the scoring is tested
with a fake one and nothing is spent. A body of at most K lines leaves nothing to continue: the row is
kept and marked `evidence: False`.

**And nearly nothing to continue is not evidence either.** A wrapper's body is three lines, so K = 2 and
the expectation is `}` alone — one token, which anything continues, and all ten of E1-g's wrappers read
`memorised` on it. `MIN_EXPECTED_TOKENS` is 8, the shortest tail that says anything about this code, and
`has_evidence(expected_tokens)` is the one place it is applied — by `gmem.run` and by `e1.plan`'s probe
request, so a row cannot be marked one way in one and the other way in the other. Like the two score
lines above it, the floor is a convention of this instrument and not a calibrated threshold. A probe
below it **keeps its row and its score** — it is a real cell and the number is what it is — and the
report reads it as `no-evidence` rather than as a reading.

**`shadow`** — **the two rename shadows** (§6's E0 and E2 cards): the target's own code under names the
base model has never read. `plan(target, graph, style)` and `write(plan, dest)`. What is renamed is
every symbol the graph names under `src/` or `test/` — at 100/100 that set is a fact, not a guess — and
`apply` rewrites those tokens whole-word **in code and in comments** (a comment that still names the
original leaks exactly what the shadow removes) and **never inside a string or character literal** (the
SQL-visible names live there and the tests call through SQL). **`descriptive`** sends each `_`-separated
word through a fixed synonym table written for this target's stems, keeping the word's own case, so
`float32_distance_dot_avx2` reads `f32_dist_inner_x86v2` and `MM256_FMA_PS` reads
`VECOP256_FUSEDMUL_F32LANE`; a word the table does not hold whole is tried again as a stem with a digit
tail (`hsum256` → `hadd256`). **`opaque`** is `fn_0001` / `MC_0001` / `ty_0001` by kind, in the order of
(path, line). A plan is refused with `Collision` — nothing renamed, nothing written — if two originals
would land on one name, or if a new name is already a token the tree writes and does not rename.

**What a shadow does not rename is on the record**, which is what E2 reads its result against. Every
in-repo identifier left alone is a `Plan.kept` row with a reason:

- **`external`** — a name the build resolves outside the repo, of which there are two kinds and both
  are read. `lane_agreement.external_vetoes` names the first (ADR-111: `strcasestr`, defined under a
  dead `#if` and called in libc). The second is a **self-referential macro**: `distance-avx512.c`
  writes `#define _mm512_abs_ps(x) _mm512_abs_ps(x)`, and C11 6.10.3.4p2 makes that a pass-through to
  clang's own intrinsic, so renaming it sends the call to a definition that does not exist. This one
  was found by the shadow failing to build, and it is now `self_referential`, read off the `#define`.
- **`entry-point`** — `sqlite3_vector_init`, which SQLite looks up by name, and `main`.
- **`not-a-graph-symbol`** — the enum constants (`VECTOR_TYPE_F32`), the file-scope declarations
  (`dispatch_distance_table`, `turbo_lut_dot_function`) and the `#define`s (`VECTOR_TYPE_MAX`) that are
  not graph symbols and so are not in the set to rename. `declarations` finds them with this package's
  own scanner, which reads wrongly rather than refuses and says where in its docstring.

Two more honesty fields. `Plan.prefixed` names the descriptive fall-backs: a name no word of which the
table holds gets `sv_`, which still carries the original whole — the fix is a table entry, and on this
fixture the list is empty. `leaks` scans everything `write` copied but did not rename and lists the
files that still write an original name, because a rename touches C and `README.md` and `API.md` name
the functions they document (L3 reads `API.md`). Both go into `shadow-map.json` beside the style, the
map, `kept` and the counts. **`.git`, `.hobbes/`, `build/` and `derived/` are not copied** — a history,
a build tree and an ingest each belong to the tree they came from, and an ingest of the *original* names
inside a shadow would hand every one of them back.

**What identifies a written shadow** (E2-c), and what an `e1` run is held to. A shadow is a copy and not
a checkout, so it has no commit: `tree_digest(root)` is one SHA-256 over the renamed files — `RENAMED`'s
globs in a fixed order, each path and then its bytes — and `map_digest(path)` is the SHA-256 of a
`shadow-map.json`'s own bytes, which is what a facts arm records as `translated_through`. `read_map`
reads the map back whole (the style, the renames, `kept`, the counts, the leaks); `load` is still just
its reverse map, which is what `--rename` hands the verbs.

`grading(rename)` is the **one named seam** that lets the existing graders read a shadow: it rebinds
`grade.build_lattice` (so the grid is read through the reverse map) and `diff.driver_source` (so the
generated driver calls `setup_dist_fns_x86v2` and declares the table as `dist_fn_t`) for the length of a
block, and puts them back. It is a seam and not a design — `grade.py` and `diff.py` should take a rename
of their own, and when they do this is the one function to delete. Everything else the graders do is
already name-blind, because `dispatch_distance_table` and the `VECTOR_*` constants are not renamed.

**`graphgrade`** — **G-graph** (§5.5): the generated body's callees against the gold's, from an ingest
of the patched tree. `gold_callees`/`got_callees` are the in-repo names the cell's symbol calls at the
`semantic` tier — in-repo because the graph has no edge to an intrinsic, `semantic` because a syntactic
edge is a guess and a guess is not a gold — and `compare` gives both sides, `missing`, `extra` and the
Jaccard (two empty sets score 1.0). **One ingest per wave, not per body**: `waves` splits a run's
entries so that no wave holds two bodies for one cell, deterministically and purely, the *n*-th body
offered for a cell going into wave *n*. **Only bodies that compiled go in** — lane B is a compiler, so a
TU that does not compile has no semantic answer at all, and grading it would read as "this body calls
nothing"; `keep` drops the `compile` and `invented` classes with that reason written on the row.
`grade_wave` fills a wave into one work copy, `git init`s and commits it (Hobbes stamps its artifact with
the repo's SHA), runs the injected `ingest(workdir) -> graph` and compares each cell. The default,
`hobbes_ingest(checkout)`, is `uv run --project <checkout>/pipeline hobbes ingest` in the copy —
always that checkout's `hobbes` and never one on `PATH` (ADR-094) — and it runs on the host, because
Hobbes contains its own lane B (ADR-092). Nothing here compiles or runs a body: `grade` did that before
the wave was built.

**The provenance rule, across all four.** A fact names where it came from and a gap names itself. Every
callee row carries `provenance` (`hobbes:<tier>` or `clang-key:<mode>`); a filled task record carries
`callees_source` with the graph's SHA, the Hobbes version that built it and the key's oracle string; and
an instrument that was not there to ask is listed in `missing` rather than worked around. Nothing in
this package infers a callee, a date or a signature it did not read.

**`prompts`** — **the five context arms of §5.3 (C-0 to C-4), by rule.** One arm is one claim about what
the model was given, so the arms differ in exactly one thing each: C-0 the file's own context, C-1 the
ledger's `callees` and the callers the lattice knows, C-2 the pattern shots, C-3 both, C-4 the same number
of lines of non-neighbour bodies. `context(lattice, cell, arm, facts=None)` is an arm as data and
`messages(…)` is it as one fixed system line plus one user turn — the file's context, the related
functions, the facts, the signature, then E1-c's instruction word for word, with a section the arm does
not carry taking its heading with it. **The prelude is always `prelude_bare`**, in every arm: on a real
kernel file the full prelude carries the five sibling bodies one axis step away, which are exactly the
shots C-2 is meant to add, so handing them to C-0 would make every arm a pattern arm and the experiment
unreadable (session `2fd4`'s review). Non-cell helpers keep their bodies in both, because a static
`hsum256_ps` is a fact about the file the body has to be able to call.

**The shot rule is E1-a's** — a rule, not a model. A task record lists up to 14 axis neighbours, among
them `cpu`, `neon`, `rvv` and the one-line wrappers, so "one step on each axis" has to say which one.
`shots` returns at most one per axis in the order ISA, type, metric, each a real body (`body` or `impl`)
unless the hole is a wrapper, in which case its shots are wrappers. `isa′` is `avx2` for `sse2` and
`avx512` and `sse2` for `avx2`; `type′` is `float32↔float16`, `bfloat16→float16`, `uint8↔int8`; `metric′`
is `l2_impl↔l1` and `dot↔cosine`, and `l2↔l2_squared` for a wrapper. **No shot ever comes from `cpu`,
`neon` or `rvv`** — `cpu` is G-diff's own reference and handing a model the reference is a different
reading, and the other two do not run on this box. The ISA axis has the pairing and **no fallback**,
because E1-a fixes one crossing per ISA so that every row crosses the same distance. The
type and metric axes fall back to the first qualifying neighbour in the record's order, which is what
answers on the trimmed fixture (no `float16` to pair with) and each shot records whether it was chosen by
`pairing` or by `fallback`. Where an axis has nothing qualifying the arm carries fewer shots and says so:
`bit1` keeps its ISA sibling alone.

**C-4 controls for "more code in context", not for a second kind of pattern** (E1-b). C-2 − C-4 is the
reading E1 exists for — is a sibling body worth more than the same volume of code? — so `control` takes
whole real bodies from the hole's **own file** that differ from it on **both** type and metric, which is
what makes them non-neighbours, and adds them until their line count reaches that cell's C-2 shots'
count, cutting the last at a line boundary. They are taken in the file's order from a start derived from
the cell id with **SHA-256, never Python's `hash()`**, which is salted per process and would make a run
unrepeatable. `lines` holds both figures beside each other, so a control that fell short — the file ran
out of candidates, as two of the fixture's cells do — is read off the record rather than assumed away.
**A facts arm without a ledger is refused** (`NoLedger`, its own type) and never filled empty: C-1 with no
callees is C-0 under another name, and a row recorded under the wrong arm is worse than a row missing.
What the ledger did not answer is simply not in the prompt — nothing here infers a callee. The same
inputs give the same bytes, and no output names the target's path.

**The stated-task sentence** (E3's revised card, point 4). E2's opaque shadow renamed the hole to
`fn_0042`, and that name turned out to be the only place the metric, the element type and the instruction
set were said — so the arm measured the loss of the *task statement* as much as the loss of the names.
`stated_task(cell)` writes it back in one fixed English sentence, from three tables keyed by `METRICS`,
`TYPES` and `ISAS`, one phrase each: "It computes the cosine distance between two vectors of 8-bit signed
integers, using AVX2 instructions." `KIND_PHRASE` adds what an `_impl` and a wrapper *are* — the shared
helper and its one-line entry point — because that is a fact about the grid the position alone does not
carry, and the metric phrases stop where `of <type>` picks them up. `messages(…, stated=True)` puts the
sentence **between the signature and the instruction**, which is the only place it belongs, and changes
nothing else: a run with the flag draws the same samples under the same ids and seeds. An axis no table
has a phrase for is `NoPhrase`, its own type, rather than a sentence with a hole in it. Every word is
English and none of them is an identifier the target writes, which is why `e1`'s leak gate reads it like
any other prompt text and passes; `stated_task_digest()` is the tables' SHA-256, and a run that carries
the sentence records it, since a wording that changed is a prompt that changed.

**`extract`** — **E1-c's parse:** `extract(completion, name)` gives `{"body", "reason", "block", "params"}`. The
body comes from the **first** fenced block, whatever its tag (```` ```c ````, ```` ```C ````,
```` ```cpp ````, bare), and a block with no closing fence — a completion cut off at `max_tokens` — runs
to the end of the text. The rule is the first block even when a later one would parse, because "take
whichever block works" quietly rewards a model for a second attempt inside one completion and makes the
arms incomparable. The definition is found by `scan`, the same scanner the lattice reads the target with,
so a helper written above the target is skipped by name and the body returned is the model's own bytes
from `{` to its matching `}`. Four failures, one reason each and `body` `None` for all four: no fenced
block, no definition of that name in the first block, a text the scanner refuses, a body `holes` would not
write. The caller files these as class **`no-body`**, reported beside `compile` and never folded into it —
a model that wrote nothing usable and a model that wrote something that will not build are two different
results. This module only says why; it classifies nothing and keeps nothing.

**`params`** rides with the body: the parameter names of the definition the model wrote, in order, and
`None` where there is no body. `params(signature)` reads them off any signature — the target's included,
which is how the runner compares the two — as the **last identifier of each comma-separated parameter**,
so `const float *a`, `const float* b` and `int c[]` all give their name and `(void)` gives none. Commas
inside a nested list do not split, though such a parameter's own name is then read wrongly; no signature
in the lattice has one, and the docstring says so rather than pretending otherwise.

**`e1`** — **the run loop** (§6, "E1's runner — the design"). `plan(lattice, cells, arms, model, facts)`
makes one chat request per (cell, arm, sample) — sample 0 greedy, 1 to *k* drawn at T = 0.8 / top-p 0.95,
**`max_tokens` 2,048** — plus one G-mem probe per cell as a raw continuation at 512, each request carrying
its own seed from a SHA-256 of
(model, cell, arm, sample, round), **never Python's `hash()`**, so the same run planned twice asks for the
same samples. The answer limit was 1,024 through E1-g, where 112 of 1,734 completions stopped at it — 95
of them in the iterate rounds, where the model writes prose around the block, and none a repetition loop.
A completion cut off at the limit is a `no-body` about the limit and not about the model, so the limit
doubled. Each request also carries the **target's own signature**, which is what the body will be graded
under and what the `param` rule below is read against. `run(run_dir, target, generate, grade, ceiling_usd=…)` is the loop, and **no model appears in
it**: the generator and the grader are injected callables, so the tests drive every round with fakes and
the one real generator is reached through :func:`modal_generator`, a subprocess and two JSONL files.

**A run is a directory, and the directory is the state**: `meta.json` (the model, the params, the arms,
the cells, `k`, the rounds, the target's SHA — never its path — the ledger's provenance, and `p12:
arm=model+prompt`), `requests.jsonl`, `rows.jsonl`, `gmem.jsonl` and `calls.jsonl`. **Resume is
`rows.jsonl`**: a request whose id already has a row is never sent again, so a second `run` over a finished
directory sends nothing, and a row is written only after its body is graded — a row is the record of a
finished request, not of a started one. **What was paid for is on disk first:** every completion a generator
returns goes to `completions.jsonl`, and the call's cost to `calls.jsonl`, before anything is graded. A resume
answers from that file before it sends anything, so a grade that fails in the image never buys the same
round twice. A body the grader returns no result for is `GradeFailed`, and no row of that round is written
(session `66c5`'s review). The Modal script prices a call on the host's wall around the remote call, an
upper bound on the GPU time billed. `lattice e1 run --generator modal` keeps every call's files under the run's `modal-calls/call-NNNN/`, and never deletes them. The first paid call was lost to a parse error: the call record's count overwrote the completion list, and the list sat in a temporary directory. A resume against a **target that has moved** since the plan is
`TargetMoved` and not a resume: the prompts are one tree's bytes, and answering them against another would
put two targets under one run's readings without either of them saying so. A completion goes through `extract`; a `None` body is a row of
class **`no-body`** with extract's reason and is never graded. **Rounds 1 to 3 run for the iterate arms
only** (`C-0`, `C-3`): every chain whose last row is not `pass` gets its conversation so far, the model's
whole text as an assistant turn, and one user turn — `feedback.build`'s ≤1,500 characters, or the one fixed
sentence for a `no-body` — and a chain stops at its first `pass`.

**A renamed parameter is not an invented API** (E1-g's record, limit 1). `grade` grafts the body under the
**target's** signature, so a body that wrote `v1` where the target writes `va` fails with `use of
undeclared identifier 'v1'`, and G-hsr — which reads exactly those messages and knows nothing of who wrote
the signature — files `v1` as invented. Sixty of E1-g's 1,734 rows were `invented` that way. So a name
that is one of the **model's own** parameter names and none of the target's is re-bucketed **`param`**
here, where both signatures are in hand; when every invented name on a row is one of those, the row
invented nothing and its class becomes **`compile`**, with the reason naming both lists. It never becomes
a pass and could not: mapped back and re-graded in the image, **none of E1-g's 53 remappable rows passed**
(45 `compile`, 7 `wrong`, 1 `invented`). What the graders answered stays readable under the row's `grade`,
so the re-bucketing is the runner's reading beside theirs and not a rewrite of theirs. And the retry says
it — the row's feedback gets one sentence, "The signature is `…`: use its parameter names.", kept whole
inside the 1,500 characters — because telling a model only that `v1` resolves nowhere is not a fair turn.

**The ceiling is checked before every call, never after** (§8). The estimate is deliberately crude and
deliberately high: prompt characters over 3.5, plus `max_tokens` for *every* request, plus
`COLD_START_SECONDS` — 180, the container start and model load **every** call pays whatever it asks for,
and most of a small round's bill. The rates are no longer guesses: `PRICING` is **8,000 prompt tokens a
second and 950 completion tokens**, measured on E1-g's run (Qwen2.5-Coder-7B, batched vLLM on one A10G at
$1.10/h), in place of the 5,000 and 500 this opened with. Olmo carries Qwen's numbers until Olmo has run.
If
the spend already in `calls.jsonl` plus that estimate passes the ceiling, `CeilingReached` — its own type —
is raised and nothing is sent. **A generator that reports no cost has its estimate recorded as the cost**,
with `cost_source` saying which it is: a run whose generator is silent must not read as free.

**The cap now holds on both sides of a call** (E2-d), because E1 found two holes on the far side of that
check. *One:* nothing bounded what a call billed once it was running — Olmo's round 1 was estimated at
$1.57, cost $2.56, and carried its run $0.39 past a $4 cap. So `modal_generator(…, run_dir=…,
ceiling_usd=…)` passes **`--max-usd` = ceiling − `spent()`** on every call, and the script turns that
into the remote function's own `timeout`; the `generate(requests)` protocol is unchanged, so the replay
generator and the tests' fakes are untouched, and a caller that passes neither gets what it always got.
*Two:* a call that **failed** wrote no `calls.jsonl` row at all, so `spent()` read it as free and Olmo's
lost call ($0.03) had to be added up by hand. Now `GenerateFailed` carries the failed call's own record
where the script wrote one, `_call` writes the row — `answered: 0`, the error, the cost — **before** the
refusal goes up, and where there was no record the row carries the call's *estimate* with
`cost_source: "estimate (the call failed and reported nothing)"`. A timeout still loses its batch; the
estimate check refuses first, so the timeout only acts when the estimate was wrong.

**A run may be served through a LoRA, and the plan says which** (E3). `meta.json` gains an **`adapter`
block** — the path on the `hobbes-ttt` volume, and the `model`, `repo`, `corpus_hash`, `recipe_hash` and
`steps` read from the `manifest.json` the trainer wrote beside the weights (`adapter_meta`). A manifest
naming another model, or another path than the one being served, is `AdapterMismatch`, its own type, and
no plan is written: E3's two readings are an adapter against a shuffled adapter *at one model*, and a plan
that cannot identify its own weights records a comparison nobody made. `e1 run` reads the block back
rather than taking a flag, so a **resume cannot switch adapters** — the same reason `_same_target` holds a
resume to one tree — and `modal_generator(…, adapter=…)` passes it on as `--adapter`. `meta.json` also
records `stated_task` and the sentence table's digest, so the two runs E3 differences can be checked to be
one plan. Nothing here serves the weights: that is `scripts/modal_e1.py`'s, from the volume, read-only.

**A run over a rename shadow** (E2) is the same run under other names, and three things carry it.
`meta.json` gains a **`shadow` block** — `style`, `map_sha256`, `tree_sha256`, `from_sha` (the original's
commit, where one was named) and `kept`, the names the shadow left alone, which leak by design and are
therefore on the record rather than in a footnote. `_same_target` holds a shadow run to `tree_sha256`,
since a written shadow has no commit for `target_sha` to hold: a renamed file that changed is
`TargetMoved`, exactly as a moved commit is. And **the leak gate**: before a plan is written, every
request's text — each message's content, and a G-mem probe's raw prompt — is tokenised as identifiers,
and a token that is a *renamed original* is `ShadowLeak`, its own type, with nothing written. The gate
tokenises because that is the grain `shadow.apply` renames at: `my_hsum256_ps` is not a leak and a name
in a comment is. A name the shadow **kept** is not a leak either — it is in the block above, with its
reason. Grading a shadow run goes into the image with `--rename /target/shadow-map.json`
(`default_grade(…, rename_in_target=…)`), the map riding at the shadow's own root, which the image
already mounts.

**`report`** — the readings, and only what a row holds. Per arm: **pass@1** from greedy, **pass@1(sampled)**
over the *k* draws, **pass@k** as the unbiased `1 − C(n−c, k)/C(n, k)` per cell then averaged (at `n = k` it
is any-pass, and under *k* samples it is `None` rather than any-pass wearing the wrong name), and for the
iterate arms the **cumulative pass rate after each round**, so the one-shot figure stays visible. Each is
broken down **by ISA and by type**, with `int8`, `uint8` and `bit1` keeping their own rows *and* summed into
a `low-bit` row. Beside each figure: the class counts, G-hsr's invented names by bucket — its own three
and **`param`**, the runner's fourth, which is a renamed parameter and is therefore counted on its own
line and never toward `intrinsic` — **G-reg over the
bodies that compiled** — a body that never built has no init for the question to be about — and the same
rates split by the cell's G-mem label, since §8 binds every number to carry its G-mem reading; a probe
under the evidence floor reads `no-evidence` there and never `memorised`. **Wrappers
are a section of their own and are never pooled with real bodies.** Tokens, seconds and cost are
`calls.jsonl`'s own, and **`max_tokens` is `meta.json`'s**, stated beside the figures it produced, since a
completion that stopped at the limit is a fact about the limit. **A missing file is named in `missing`, never read as zero**: a run whose grading never
happened and a run in which nothing passed are two different results.

**`compare`** — **E2's reading**: an original run against its shadows, from the runs' own rows and
nothing else. Per arm the two runs share, each run's pass@1, pass@1(sampled) and pass@k with the
shadow's **delta** against the original; per cell, the **greedy flips** each way — passed then failed,
and failed then passed. The figures come from `report.report`, which computes nothing a row does not
hold, and the flips from `rows.jsonl`; neither the target nor the shadow is opened, because by the time
a run is compared the only evidence left is what it wrote down. Real bodies and wrappers stay in their
own sections, as the report keeps them. **Two runs that differ in more than the names are refused** —
`NotComparable`, its own type — when the model, `k`, the sampling parameters or the cells differ: the
gap is read as *what renaming cost*, and it only reads that way when renaming is the one thing that
moved. The arms deliberately need not match, so E2-a's two-arm shadow run is compared with E1's
five-arm original on the two they share. A shadow is named by its `meta.json`'s `shadow.style`, which
is also the order the two gaps are read in: descriptive − original is what renaming to equally
meaningful names cost, and opaque − descriptive is, on this lattice, the loss of the task statement as
much as of the names (E2's record: the hole's name was the only place the metric and type were said).
Beside each arm's delta go the **paired tests** below.

**`paired`** — **the noise floor** (2026-09-26): whether a gap between two arms, or two runs, is more
than the cells it rests on. Both sides grade the same cells, so each test is paired by cell and exact:
**McNemar** on the greedy pass (pass@1) and on any-pass at `n = k` (pass@k), and a **sign-flip** test
over the per-cell sampled pass rates (pass@1(sampled)), counted over integer numerators, so there is
no seed. Round 0 only, as the report's figures are; bodies and wrappers apart; a cell only one side
answered is counted in `unpaired`, never read as a fail. A p is two-sided, per comparison and
**uncorrected** — the reader names which comparison the card registered before the run.
`lattice e1 paired <run> <arm> <arm>` pairs two arms of one run (E1's C-2 against C-4), and `e2
compare` carries the same three tests per arm against the original.

**`e3`** — **E3's reading** (§6, "E3's card, revised"): two runs of one plan, one adapter apart. It lives
in **`e3.py`**, beside E2's in `compare.py` rather than inside it, because what it refuses is different:
E2 deliberately compares a five-arm original with a two-arm shadow on what they share, and E3's two runs
must be **the same plan answered twice** — the model, `k`, the params, the arms, the cells, the shadow, the
stated-task sentence and the target's SHA all equal, with the **adapter the one thing allowed to differ**
(`SAME`; the arms and the cells are read as sets, since an order is not part of a plan). The refusal is
`compare.NotComparable`, the same type, because "these two runs are not one variable apart" is one
guarantee and one type is what a caller catches for it. Per section and per arm it gives `paired.paired`
from `a` to `b` — so `e3 compare <shuffled> <adapter>` reads the delta the card's way round — beside which
weights each side served, by path and by what trained them. **Two comparisons are marked as registered**
(`REGISTERED`): **C-2 is E3-use** (does training make the model better at using examples?) and **C-0 is
E3-weights** (did the pattern move into the weights?), each with `pass_at_1_sampled` named as its primary
figure, since at 63 bodies the greedy rate needs about nine net cells to reach p < 0.05 and the sampled
rate is the sensitive one. All three tests print under every arm and everything else — C-3, C-4, the
stated-task arm, and **the wrapper section of the same two arms** (`REGISTERED_SECTION` is `bodies`; a
wrapper is not the task a body is) — is described and not read. A run whose `rows.jsonl` is not there is
named in `missing`, never read as a floor.

**`e4`** — **E4's runner** (§6's card and "E4's design"; D-6 as recommended). E1 asked what context is
worth on one body; E4 holds out a **whole file** at rung **L1** and asks whether the graph can serve a
small student the pattern and the facts to write it back, one definition at a time. It is the first run on
that page that **decomposes** (P12, ADR-082): `meta.json` records `p12: decomposed` with the unit count,
the largest prompt and the file's own length, so ADR-086's check can read that every implementer's window
was smaller than the task (on the fixture's `distance-avx2.c`: 9,718 chars against 20,357).

**A unit is a definition, not a cell.** `units(lattice, isa)` reads every definition of the held-out file —
the 13 lattice cells, the 13 non-cell helpers and `init_distance_functions_avx2` — and orders them **leaves
first** by the calls in the *gold* bodies: an identifier token in a body's masked text naming another
definition of the same file is an edge, which is the one rule the order, a helper's graded slots and the
reach are all read by. A **cycle** is emitted as one group in file order and `cycles()` names it, which the
plan records; a file that defines one name twice (every `#if` arm is read) is `DuplicateDefinition` rather
than two units under one name. `skeleton(lattice, isa, unit)` is the file down to the end of that unit's
signature with **every other body replaced by `;`** — stricter than C-0's `task.prelude_bare`, which keeps
the non-cell helpers' bodies: at L1 those helpers are holes too, so their bodies would be gold in a prompt,
and **a body reaches a prompt only as an arm's shot.**

**Five arms, one variable apart.** **S-0** is the skeleton and the hole. **S-2** adds
the graph-served **ISA-axis** shots — the same `(type, metric)` cell in each other *native* file (`sse2` and
`avx512` when `avx2` is held out, which is why E4-a holds out `avx2` first), the other files' init functions
for the init unit, and **none for a helper**, which the prompt says as `shots: none (helper)` rather than
reading as S-0. **S-3** adds the ledger's callees for a cell, in E1's own lines, and says
`facts: none (helper)` or `(init)` where there are none. **S-5** adds the parser's fields under one heading,
"What this function must do:" — the contract, then the edge cases as a list. **S-2o** adds the student's own
passed bodies on the type and metric axes; it is **described and not registered** (E4-c), so the report
shows it beside S-2 with what it carried and the two registered comparisons stay E4-f's. From E1's rows the
expectation is written down: 12 of Qwen's 18 C-2 greedy passes sat nearest the *type*-axis shot, and at L1
the type neighbours are holes, so S-2 is expected **below** E1's C-2 — and S-2o is the arm that asks whether
the student's own passes can stand in for those holes.

**The parser is a step of its own, and it never sees a body.** `lattice e4 parse` (K-1, §5.2: a parser into
the task format, *not* an author) asks one **greedy** question per unit and writes `parser.jsonl`, which
every arm of the run then reads — one set of fields, not one per sample. It is shown `API.md`, the unit's
name, kind and signature, its grid position where it is a cell, and the **names** of the callees S-3 would
list. It is shown **no skeleton, no shot and no gold**, and the two checks on that are in the tests: no
definition of any of the files appears as a token run, and the prompt carries **no `{` at all** — the
JSON's shape is spelled out in words for exactly that reason, since every C body has one. A target with no
`API.md` (this fixture) has the parser *told* so rather than shown another project's. The answer must be one
JSON object with `contract` and `edge_cases`; the first fenced block is read where the model fenced it, as
`extract` reads a body, and **nothing else is tried**. An answer that is not those two fields is kept whole
in `raw` with `parsed: false` and a stated reason, and the unit's S-5 prompt then carries
`no parser fields (the parse failed: <reason>)`: never repaired, never guessed at, never filled empty — an
S-5 with no fields at all is `NoFields`, its own type, for the same reason `NoLedger` is. The step is priced
and capped exactly as an E1 call is, its `calls.jsonl` rows marked `stage: "parse"` so `spent()` counts the
parser's spend against the run's one ceiling, and **resume is `parser.jsonl`**: a unit already in it is
neither asked nor paid for again. `meta.json`'s `parser` block names the model and the digest of the file
the plan was built from, and `e4 plan --arms S-5` **exits 2, naming the file**, when it is missing or does
not cover every unit.

**S-2o runs in waves, because its shots are this run's own output.** Each cell's **designated neighbour** on
an axis is the one E1's rule would pick, **kept only if it comes earlier in the units' order**; otherwise
that axis carries no own shot and the request records `later-in-order`. That one condition breaks E1's
symmetric pairs — the type pairing is `float32 ↔ int8` here, so without it each unit would be its own
neighbour's neighbour and no wave could be first — and it is fixed before the run. The shot is that
neighbour's **S-2o greedy body, and only where the graders passed it**; where they did not, the axis records
`neighbour-failed`, because an unverified body is not a pattern. An axis E1's rule has no neighbour for at
all records `no-neighbour`. **Gold is never a shot**: `_own_bodies` reads `rows.jsonl` and never the target.
Helpers and the init have no grid position, so they carry S-2's ISA-axis shots only and say
`own shots: none (helper)`. Wave(u) is 0 with no designated neighbour and 1 + the largest of theirs
otherwise; `meta.json` lists the waves by name (on the fixture's `avx2` file: 18, 5, 3, 1). `plan` writes
wave 0 and `e4 run` builds each later wave from the rows already graded, appends it to `requests.jsonl` and
calls `e1.run` again — which sends only what has no row yet, so **a resume rebuilds and re-answers nothing**.
`meta.json`'s P12 window record is restated as each wave lands, since the plan could not hold prompts whose
shots nobody had written.

**A failed unit does not cascade** (E4-d). E1's loop runs with `rounds=0` and each unit is graded against
the **gold** file with that one definition punched, so a wrong `hsum256_ps` fails on its own row and every
cell that calls it is still graded against the target's own helper. Beside that per-unit reading,
`file_level` builds the file the student *actually wrote* — every unit's **greedy** body where that unit
passed, gold elsewhere — writes it to `final/<arm>/<file>` with a unified diff against the target's in
`.patch`, grades it once over every installed slot, and records `units_passed`, `units`, `diff_pass` and
`reg` in `file_level.jsonl`. An arm already in that file is not built again. The file-level build reaches
the image through **a manifest form and not a `grade-file` verb** — `{"id", "isa", "bodies"}` beside the
unit form, which is the smaller of the two: no new argparse, no new container plumbing, and `e1.default_grade`
carries it unchanged. Both sides fill with `fill_units`, and `filled_sha256` is on the row from each.

**`families`** — **E3's draw rules, ported verbatim** from `bench/calvin/e3-draw/`, the draw's scripts as
they ran (2026-09-26). The recorded pool — 33,902 union tasks over the 40 taken repos, **24,222 unique**
(§6, "E3's pool") — was read by those scripts, so the corpus has to select the same members, and the
rules therefore live in one place rather than being restated. From `count.py`: the member set off
`graph.json` and `tests.json` (a function or method symbol, in a C or C++ file by extension, outside a
test or vendored path, with at least two name tokens), each member's comment-stripped body, the **thin
filter** (a body of at most two non-blank lines, or one statement with at most one call), `loose_groups`
and `body_tokens`. From `measure.py`: `isa_families`, `body_families` — single linkage at ratio ≥ 0.6
with both exact prefilters, groups over 64 members not compared, and a pair over `PAIR_CAP` 20,000 body
tokens counted rather than computed — and `scalar_ref`. From `gate.py`: the `ISA` list and **its own
tokeniser**, `isa_tokens`, which splits on `_` and camelCase only so `avx512vnni` stays one token, which
is *not* `count.py`'s `tokens`, which splits a letter run off the digits before it (`hsum256d` →
`hsum256`, `d`); both are ported because the draw used both. From `dedupe.py`: `body_hash`, the sha1 of a
whitespace-normalised body. The two deliberate differences are that the drivers' paths and their output
are gone, and that the census helpers (`summarise`, `sample`, `strict_families`, `two_axis`, …) are not
ported — the corpus reads the union, not the count. `tests/test_families.py` imports `count.py` and
`measure.py` **by path** and asserts the same union ids and the same unique count on the same synthetic
clones, which is the only test of a port that means anything.

**`corpus`** — **E3's corpus** (§6, "E3's price on D-7's pool": a dispatched unit, no spend). One
training example per kept member, in **E1's evaluated format**, because the adapter is read on E1's arms:
`prompts.SYSTEM`, then a user turn carrying up to three other members of the member's own family as
whole definitions, the prototypes of the in-repo callees its body makes, its own signature and
`prompts.INSTRUCTION` word for word, then an assistant turn holding its whole definition in one
```` ```c ```` block. The neighbours come from the **first of the member's families that can show it
any**, in a fixed order, taken in the clone's own `(path, line)` order from a start derived with SHA-256
from the seed and the member's place — never Python's `hash()` — so a large family is spread over and the
same seed gives the same three every run. The members are the draw's union, deduplicated across repos in
the taken order exactly as `dedupe.py` did.

**Five things are refused or dropped, each with its own name.** **No dispatched session's text ever
trains** (ADR-107, §8): an input root holding `docs/calvin/sessions/` or `pipeline/src/hobbes/` is
Hobbes itself and is refused with `SessionText`, its own type, before anything is read. **No
sqlite-vector code**: every member's body is compared with each of the target's **native** gold bodies —
the 93 the card names, the ones E3 is evaluated on — on `families`' own tokens, and one at ratio ≥ 0.6 is
`near-target`, dropped, listed with the ratio, and **never carried as another member's neighbour
either**, since a gold body in a prompt is the target in the corpus whichever column it sits in. What
that ratio does not claim is the target's non-native files (`cpu`, `neon`, `rvv`): a member matching one
of those is the target's code too, and it is the draw's gate 2 **by name** that keeps it out. Run against
the target itself — which the draw never does — the rule catches 35 of its 46 pool members at ratio 1.0,
and the rest are the ISAs no gold covers, which is the shape of both instruments in one reading. **No example depends on a fact its prompt does not carry** (§12.5:
training on unfamiliar facts teaches guessing): a member one of whose in-repo callees has no readable
signature in the clone is `unstated-callee`, and one left with no neighbour to show is `alone`. **No
example is truncated**: the trainer cuts at 2,048 tokens, so an example over `MAX_CHARS` 7,600 characters
— about 1,900 tokens at four characters a token — is `too-long`, dropped and never cut. And
**`unreadable`**, which is the format rule read back: `extract` is run over the record's own answer, and
a member whose definition the evaluator would not read as that definition (a K&R declarator, which
`scan` reads wrongly rather than refuses) is not an example.

**The control is ADR-099's shuffled answers**: the same records, every prompt byte for byte, the answers
permuted so the token multiset is unchanged and only the pairing is broken. The permutation is a seeded
derangement in which **no record keeps its own answer or one from its own family** — a same-family answer
would leave a pattern arm wearing the control's name. It is built by laying the families out largest
first and rotating by the largest family's size, which is exactly why a corpus one family holds half or
more of has **no** control and raises `NoDerangement` rather than a weaker one. Each corpus directory
holds `train.jsonl` (one `{"messages": […]}` a line, the loss on the assistant turn) and a
`manifest.json` with the three fields `modal_ttt.train_adapter` reads — `corpus_hash` (that file's
sha256), `repo` (`e3-c-lattice` or `e3-c-lattice-shuffled`) and `sha` (over the repos list, the target's
HEAD and the seed) — plus the records, the drops by reason and every record's family key and source
`path:line`. `corpus-report.json` is per repo the union, the unique, the duplicates, the drops and the
kept, with the **character lengths' quartiles**, which is the measurement that replaces the price table's
"≤ 2k tokens" assumption. Nothing here calls a model and nothing trains.

**`cli`** — `lattice map <target> [--json]`, `lattice task <target> <cell-id>`,
`lattice punch <target> <cell-id>`, `lattice grade <target> <manifest.json> [--out results.jsonl]`,
`lattice selftest <target> [--cells id,id,…] [--out report.json]`, plus the reading verbs of this unit:
`lattice facts <target> <cell-id> --graph G --key K [--intrinsics I]`, `lattice intrinsics <include-dir>
[--out index.json]`, `lattice ages <git-dir> <ref> [--out ages.json]` and `lattice mem-probes <target>
[--out probes.jsonl]`. `lattice task` takes the same three ledger flags. A cell id is
`<isa>/<type>/<metric>`; a manifest is a JSON list of entries (or an object with them under `entries`).
The two grading verbs take `--here` (this process is contained already) or `--image NAME` (the default
`hobbes-session:local`: build a plan and run this same CLI inside it). `--here` outside a container exits
2 with the refusal. No ledger flag is required, and one left out is named in the answer's `missing`.
`mem-probes` writes the probes. **This unit adds three:** `lattice e1 plan <target> <run-dir> --model M
[--cells …] [--arms …] [--graph G --key K --intrinsics I] [--k 5]`, `lattice e1 run <run-dir> <target>
--ceiling-usd X [--generator modal|replay:<completions.jsonl>] [--image NAME] [--rounds 3]` and `lattice e1
report <run-dir> [--json]`. **`e1 run` is the one verb that would call a model**, and only through the
generator named on the line: `replay:` answers from a recorded file and spends nothing, `modal` shells out
to `scripts/modal_e1.py`. `--ceiling-usd` is **required and has no default** (§8), and `e1 plan` skips a
facts arm with no ledger exactly as `prompts` does. Everything else here still writes text only.

**This unit adds two flags and one verb, all E2's.** `e1 plan --rename <shadow-map.json>` plans over a
shadow: the target named on the line is then the shadow's own root, the lattice is read through the
reverse map so every prompt is the shadow's bytes, and `meta.json` carries the shadow block. A facts arm
over a shadow also takes **`--original <target-root>`** — the ledger is the target's, read at the
target's own lattice and written forward through the map — and a facts arm with `--rename` and no
`--original` is **refused, exit 2**, never read at the shadow. A plan any of whose prompts writes a
renamed original is refused too, and nothing is written. `e1 run` takes **no new flag**: it reads the
shadow out of `meta.json`, checks the tree digest, and passes `--rename /target/shadow-map.json` to the
image's `lattice grade`. Then `lattice e2 compare <original-run> <shadow-run> [<shadow-run> …]
[--json]`, which prints the per-arm deltas and the per-cell flips, and exits 2 when the runs differ in
more than their names. Before
them, one verb: `lattice
prompts <target> [--arms C-0,C-2,…] [--cells id,id,…] [--graph G --key K --intrinsics I] [--rename M]
[--out prompts.jsonl]`, which writes one JSON row per (cell, arm) — `{"cell", "arm", "messages", "shots",
"control", "chars"}` — over every native cell and every arm by default. It reads files only and runs on
the host, like `task`; a facts arm (C-1, C-3) asked for with no ledger is **skipped and the skip is named
on stderr**, never filled empty. Before it, two verbs and one flag:
`lattice shadow <target> <dest> --graph G --style descriptive|opaque`, which prints what it kept and
what still leaks; `lattice graph-grade <target> <results.jsonl> --gold-graph G [--hobbes <checkout>]`,
which writes one row per body it carried and one per body it did not, with the reason; and `--rename
<shadow-map.json>` on `map`, `task` and `grade`, which reads the lattice through a shadow's map (and,
for `grade`, rides into the image in the work dir, since `--rename` may point anywhere on this box).

**This unit adds three more, all E4's:** `lattice e4 plan <target> <run-dir> --model M [--isa avx2]
[--arms S-0,S-2,S-2o,S-3,S-5] [--k 10] [--graph G --key K --intrinsics I]`, `lattice e4 run <run-dir>
<target> --ceiling-usd X [--generator modal|replay:<completions.jsonl>] [--image NAME]` and `lattice e4
report <run-dir> [--json]`. `plan` prints the P12 window line and refuses, exit 2, an ISA the target has
not and an arm that is not E4's, naming it; `S-3` or `S-5` with no ledger is skipped and named, as
`prompts` does. `run` takes no `--rounds`: E4 does not iterate. `report` prints one block per arm **per unit
kind** — cell, helper, init, with the `unexercised` helpers counted apart and never averaged in — the
file-level rows, and the two comparisons E4-f registered, paired by unit: `S-2 − S-0` and `S-5 − S-3`.

**And E4's second half adds one verb and one flag.** `lattice e4 parse <run-dir> <target> --parser-model M
--ceiling-usd X [--isa avx2] [--generator modal|replay:…] [--graph G --key K --intrinsics I]` writes
`parser.jsonl` — S-5's fields — and runs **before** `plan`, which then carries the parser's model and that
file's digest in `meta.json` and **exits 2, naming the file**, if `--arms` asks for `S-5` and the parse is
missing or short of a unit. It prints what it kept raw and why, and says on stderr where a target has no
`API.md`. `e4 run` needs no new flag for **S-2o**: it reads the waves off the file, builds each later wave
from the rows it has, and answers it with another `e1.run` over the same directory — so the ceiling is
checked again before each wave and a resume sends nothing twice. `report` gains S-2o's own-shot counts —
how many cells carried 0, 1 or 2, and **why each missing one was missing** (`later-in-order`,
`neighbour-failed`, `no-neighbour`, or the unit having no axis at all) — read off `requests.jsonl`, because
what a prompt carried is not on any row.

**And this unit adds one verb, E3's:** `lattice e3 corpus --repos <list> --target <sqlite-vector root>
--out <dir> [--seed 20260926]`, where `<list>` is a file of `<name>=<root>` lines in the draw's taken
order. It writes `e3-pattern/`, `e3-shuffled/` and `corpus-report.json`, prints the union, the unique, the
duplicates, every drop with its reason and both corpora's digests, and **exits 2 with nothing written** on
a repos list it cannot read, an input root holding a dispatched session's text, and a corpus one family
holds half of, which has no derangement to be a control. It reads files only and calls no model.

**And this unit adds two flags, one pair of them, and one verb — E3's evaluation plumbing.** `lattice e1
plan --adapter <path on the hobbes-ttt volume> --adapter-manifest <a local copy of its manifest.json>`
records the adapter in `meta.json` and **exits 2** when that manifest names another model or another path,
or when one of the two flags comes without the other: the path says which weights answered and the
manifest says what trained them, and a plan that has one without the other names an adapter it cannot
identify. `e1 run` takes **no new flag** — it reads the adapter out of `meta.json` and hands it to the
generator, which is what makes a resume unable to switch adapters. `lattice e1 plan --stated-task` adds
E3's one English sentence to every user turn, before the instruction, and is allowed **only with
`--rename` on a shadow whose map says `style: opaque`**; anywhere else it exits 2 naming what the plan was
over, because on the target or on the descriptive shadow the names already state the task. Then `lattice
e3 compare <run-a> <run-b> [--json]`, which prints the paired reading of `b` against `a` with C-2 marked
**E3-use** and C-0 marked **E3-weights**, every other arm described, and exits 2 when the two runs are not
one plan one adapter apart. None of the three calls a model: `e1 run --generator modal` still does that,
and it is the only verb that does.

Everything that compiles or runs the target's code runs in the image (ADR-092, C-64) — and so does the
intrinsic index, whose headers are the image's clang's. `graph-grade` is the exception and says why: it
runs a Hobbes ingest, which contains its own lane B. Still to come: G-test, `grade` and `diff` taking a
rename of their own instead of `shadow.grading`, and the first run that actually calls a model.

```sh
# on this box, in the image
lattice selftest /path/to/sqlite-vector --image hobbes-session:local
lattice grade    /path/to/sqlite-vector manifest.json --out results.jsonl
lattice intrinsics "$(clang -print-file-name=include)" --out index.json
lattice facts /path/to/sqlite-vector avx2/float32/dot \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json

# the five arms' prompts, on the host: one row per (cell, arm), no model anywhere near it
lattice prompts /path/to/sqlite-vector --arms C-0,C-2,C-4 --out prompts.jsonl
lattice prompts /path/to/sqlite-vector --cells avx2/float32/dot --arms C-1,C-3 \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json

# on the host, over a full clone: the cell ages the contamination facts are read from
lattice ages /path/to/sqlite-vector-history 0c2223a --out ages.json

# E2's two shadows, and the same graders over one of them
lattice shadow /path/to/sqlite-vector /tmp/shadow-descriptive \
  --graph .hobbes/derived/graph.json --style descriptive
lattice shadow /path/to/sqlite-vector /tmp/shadow-opaque \
  --graph .hobbes/derived/graph.json --style opaque
lattice grade /tmp/shadow-opaque manifest.json --rename /tmp/shadow-opaque/shadow-map.json

# G-graph, over the bodies a grading run kept
lattice graph-grade /path/to/sqlite-vector results.jsonl \
  --gold-graph .hobbes/derived/graph.json --hobbes ~/hobbes_public --out graph.jsonl

# E1: plan the requests, answer and grade them under a ceiling, read the result
# (no --cells is every native cell; the first unit names the avx2 ones)
lattice e1 plan /path/to/sqlite-vector runs/qwen-avx2 \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --arms C-0,C-1,C-2,C-3,C-4 --k 5 \
  --cells avx2/float32/dot,avx2/float32/l2_impl,… \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json
lattice e1 run runs/qwen-avx2 /path/to/sqlite-vector --ceiling-usd 10 --generator modal
lattice e1 report runs/qwen-avx2                    # or --json
lattice e1 paired runs/qwen-avx2 C-4 C-2             # C-2 against C-4, paired by cell; or --json

# the same run again with no model at all, from a recorded batch
lattice e1 run runs/qwen-avx2 /path/to/sqlite-vector \
  --ceiling-usd 0.01 --generator replay:completions.jsonl

# E2: the same plan over a shadow — the shadow's bytes, E1's own ids and seeds, the target's ledger
# written forward through the map. `--original` is required for a facts arm and nothing else.
lattice e1 plan /tmp/shadow-descriptive runs/qwen-descriptive \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --arms C-2,C-3 --k 5 \
  --rename /tmp/shadow-descriptive/shadow-map.json --original /path/to/sqlite-vector \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json
lattice e1 run runs/qwen-descriptive /tmp/shadow-descriptive --ceiling-usd 1.50 --generator modal
lattice e2 compare runs/qwen-avx2 runs/qwen-descriptive runs/qwen-opaque   # or --json

# E4: one whole file at L1, every definition a unit, leaves first, one call each
# the parse comes first: S-5's fields, one greedy call per unit, cached in the run's parser.jsonl
lattice e4 parse runs/qwen-avx2-l1 /path/to/sqlite-vector \
  --parser-model Qwen/Qwen2.5-7B-Instruct --isa avx2 --ceiling-usd 1 --generator modal \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json
lattice e4 plan /path/to/sqlite-vector runs/qwen-avx2-l1 \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --isa avx2 --arms S-0,S-2,S-2o,S-3,S-5 --k 10 \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json
lattice e4 run runs/qwen-avx2-l1 /path/to/sqlite-vector --ceiling-usd 8 --generator modal
lattice e4 report runs/qwen-avx2-l1                 # or --json

# E3: the draw's 40 clones as a training corpus and its shuffled control, on the host, spending nothing
# repos.txt is one <name>=<root> a line, in the draw's taken order (its dedupe depends on that order)
lattice e3 corpus --repos repos.txt --target /path/to/sqlite-vector --out corpora/e3

# E3's evaluation: the same plan three times — base, adapter, shuffled — and the paired reading of it.
# the adapter's path is the one `modal_ttt.train_adapter` returned; the manifest is a local copy of its
lattice e1 plan /path/to/sqlite-vector runs/e3-adapter-300 \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --arms C-0,C-2,C-3,C-4 --k 10 \
  --adapter adapters/qwen-qwen2-5-coder-7b-instruct/e3-c-lattice/<sha>/<recipe> \
  --adapter-manifest manifests/e3-pattern-300.json \
  --graph .hobbes/derived/graph.json --key oracle.json --intrinsics index.json
lattice e1 run runs/e3-adapter-300 /path/to/sqlite-vector --ceiling-usd 5 --generator modal
lattice e3 compare runs/e3-shuffled-300 runs/e3-adapter-300    # E3-use and E3-weights; or --json
lattice e3 compare runs/e3-base runs/e3-adapter-300            # the adapter against the base beside it

# and the stated-task opaque arm: the opaque shadow's prompts with the task said in one sentence
lattice e1 plan /tmp/shadow-opaque runs/e3-stated-base \
  --model Qwen/Qwen2.5-Coder-7B-Instruct --arms C-2 --k 10 \
  --rename /tmp/shadow-opaque/shadow-map.json --stated-task
```

## E1's runner — the order of work

**The first unit has run; nothing after it has.** `scripts/modal_e1.py` is run by the developer, on Max's
word, and the ceiling is checked before every call. The order is fixed:

1. **`lattice e1 plan`** — the requests only. It reads files, calls nothing, and costs nothing. Read the
   prompt sizes off `requests.jsonl` before anything is sent.
2. **The first unit (E1-g): Qwen2.5-Coder-7B, `avx2`, all five arms**, greedy and k = 5, round 0 plus the
   iterate rounds, with the 31 cells' G-mem probes in the same call. `--ceiling-usd` is named by Max.
   **Run on 2026-09-25**: 961 requests over four calls at `0c2223a`, **$0.74 of the $10 ceiling**, $0.16
   of it lost with the first call's completions (fixed).
3. **Price it.** Done: `e1.PRICING` and `COLD_START_SECONDS` are now E1-g's measured throughput and its
   per-call load, in place of the guesses. Round 0 cost $0.17 against an estimate of $0.73, and the rest
   of E1 projects to **$2–3 against the $10 ceiling**. Compare the next unit's `calls.jsonl` with the
   estimate again rather than assuming these carry.
4. **Max's word**, before the other two ISAs and before Olmo.
5. **The rest**, then G-graph over the bodies that compiled — one ingest per wave, and not in the loop.

E1-g's rows also moved three things here, each measured on them first and none of them a re-grade of that
run: the `param` bucket, `max_tokens` 2,048 and the G-mem evidence floor.

`scripts/modal_e1.py` is a `uv run` script (`modal>=1.1`) and **this package never imports `modal`**: the
seam is a subprocess and two JSONL files, which is also what makes a batch replayable afterwards. Its pins
are the ones both 7Bs already ran under for ADR-099 — vLLM 0.27.1, `transformers>=5.8`,
`VLLM_USE_FLASHINFER_SAMPLER=0`, an A10G at a 16k window, the weights in the `hobbes-hf-cache` volume — and
`MODELS` is the whole of what may run: a model it does not name is refused rather than downloaded, because
a run at an unpinned model is not the run the record describes. One offline batch per call, prefix caching
on, one `SamplingParams` per request so the seed is per request; `llm.chat` for the arms and `llm.generate`
for the G-mem probes, which are continuations a chat template would turn into questions. The GPU rate in
it is a constant to check against Modal's pricing page, not a quote.

**`--max-usd`, and the record a failed call leaves** (E2-d). The script turns the money left into the
remote function's own `timeout` — `timeout_for(max_usd, gpu)` is `min(4 h, max_usd / $·s⁻¹ − 120 s)`,
the 120 s being the boot and model load Modal bills before the GPU does any work of ours — and
`with_options(gpu=…, timeout=…)` carries it. A budget that buys under 60 s is refused, exit 2, with
nothing called. The call record is written in a `finally` around the remote call, so a timeout or a
remote error still leaves `call.json` with `answered: 0`, the error and the host-wall cost, and the
script then exits non-zero; `lattice.e1` reads that record off `GenerateFailed` into `calls.jsonl`.
**The arithmetic stays in the script**, beside the price table it reads — one place to change when a
card's price does — and the test loads the script's source with `modal` stubbed to reach it, because
this package may not import `modal` and a dispatched session has no route to it. The alternative, a
copy of the arithmetic in the package where the tests could import it, is two places for one number.

## E4's runner — the order of work

**Nothing has run.** The instruments are built — both halves — and no model has been called; §6's estimate
is **$3–5 with a ceiling of $8** for the `avx2` file, and only Max names a run and its ceiling (§8). The
order:

1. **`lattice e4 parse --isa avx2`** — the parser's fields, one greedy call per unit, and the **first thing
   that spends**: it needs its own `--ceiling-usd` and its rows are counted against the run's spend. It is
   cached in `parser.jsonl`, so it is run once and every arm reads it.
2. **`lattice e4 plan --isa avx2`** — the requests only, on the host, costing nothing. Read the P12 line it
   prints and the prompt sizes off `requests.jsonl` before anything is sent: on the real file, 45 units × 5
   arms × 11 samples less S-2o's later waves, and every window must be smaller than the file.
3. **The first call**, priced against `e1.estimate` before the rest is sent, as E1-g's was. There are no
   rounds, so one call answers every unit of every arm but S-2o's later waves, which are one call each.
4. **Read the per-unit figures first, then the file level.** The per-unit rates are what S-2 − S-0 and
   S-5 − S-3 are read on; the file level says how much of the file the student wrote, and it is a second
   reading, not a headline. S-2o is described beside S-2 — its own-shot counts — and is in no comparison.
5. **Max's word**, before the other two native files (E4-a's `b`), before the 32B ceiling arm and before
   the descriptive shadow (E4-g).

**The parser's model is a run parameter, not the instrument's.** `modal_e1.py` pins
`Qwen/Qwen2.5-7B-Instruct` for it (E4-e: an open instruct 7B, a parser and not an author) — Qwen2.5-Coder's
own base at the same size, so the same card and the same 16k window the student runs under, and
`e1.PRICING`'s fall-back is the A10G's rate it bills at.

## E3 — the order of work

**Nothing has been built, nothing has been trained and no adapter has been served.** The corpus is the
step before E3 spends anything (§6, "E3's price on D-7's pool"), and it runs on the host against the
draw's own clones, which live in the driver directory and not in this repo. The order:

1. **`lattice e3 corpus`** over the 40 taken repos, in the draw's order, with the target named. It reads
   files and costs nothing. Read `corpus-report.json` first: the kept count against the draw's 24,222,
   every drop with its reason, and the **character quartiles** — the figure the $17 estimate's "≤ 2k
   tokens" was an assumption about, and the one that says whether the trainer would have cut anything.
2. **Read the drops, not just the total.** `near-target` at anything but zero is the one that matters:
   the draw gated the target out by name, so a hit here is a repo that ships the target's code under
   another one.
3. **G-mem on the base at the 93 cells, before any training**, as E1 did (`lattice mem-probes`): the
   card binds every number to its G-mem reading, and the reading has to exist before the adapter does.
4. **Max's word** (D-9): the corpus reviewed, then E3's run at the $25 ceiling — the 300-step pair
   first, priced against its estimate, and the 3,000-step pair only after that reading.
5. **Train the pair**, `uv run pipeline/scripts/modal_ttt.py put <corpus-dir> corpora/e3-pattern` then
   `… train --corpus corpora/e3-pattern --steps 300 --model Qwen/Qwen2.5-Coder-7B-Instruct`, and the same
   two for the shuffled control — **300 steps first**, about $0.35 each. They are two `repo` names and so
   two adapter keys, neither able to overwrite the other. Read the manifest each run prints and **fetch a
   copy of it** (`… get <adapter-path>/manifest.json manifests/e3-pattern-300.json`), because `e1 plan
   --adapter-manifest` is what checks that the weights being served are this model's and this path's.
6. **Plan and run the arms over the same cells and the same arms**, three plans that differ in one field:
   the **base** (no `--adapter`), the **adapter**, and the **shuffled** control, each at `--k 10` with no
   iterate rounds, each priced against `e1.estimate` before the next. The stated-task opaque arm is a
   fourth plan, over the opaque shadow with `--stated-task`, on the base and on the adapter.
7. **`lattice e3 compare`**, twice: shuffled → adapter is **E3-use** on C-2 and **E3-weights** on C-0,
   which are the two findings; adapter → base goes beside them and is described. Read
   `pass_at_1_sampled` and its sign-flip p first — it is the figure the card registered — and treat every
   other arm, and the wrapper section, as description.
8. **Max's word again**, before the 3,000-step pair. ADR-099 saw the effect leave as facts came in, so the
   steps ablation is the reading and not a formality.

The corpus and its control are two directories a Modal volume can take as they are: `train_adapter`
reads `<corpus>/train.jsonl` and `<corpus>/manifest.json` and keys the adapter on `repo`, `sha` and
`corpus_hash`, which is why the control is a **second repo name** and not a flag — two adapters, two
keys, no chance of one overwriting the other. The evaluation side is the same shape: an adapter is a
property of the **plan**, recorded in `meta.json` with its manifest's fields, so `e1 run` cannot be told
to answer half a run's cells through other weights and `e3 compare` can refuse two runs that are not one
plan. `scripts/modal_e1.py --adapter` mounts `hobbes-ttt` **read-only** at `/ttt` and builds vLLM with
`enable_lora` at rank 32, ADR-099's `r`; the one `LoRARequest` rides on both entry points, so the G-mem
probes are served by the same weights as the arms.
