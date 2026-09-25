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

**`extract`** — **E1-c's parse:** `extract(completion, name)` gives `{"body", "reason", "block"}`. The
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

**`e1`** — **the run loop** (§6, "E1's runner — the design"). `plan(lattice, cells, arms, model, facts)`
makes one chat request per (cell, arm, sample) — sample 0 greedy, 1 to *k* drawn at T = 0.8 / top-p 0.95 —
plus one G-mem probe per cell as a raw continuation, each request carrying its own seed from a SHA-256 of
(model, cell, arm, sample, round), **never Python's `hash()`**, so the same run planned twice asks for the
same samples. `run(run_dir, target, generate, grade, ceiling_usd=…)` is the loop, and **no model appears in
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
upper bound on the GPU time billed. A resume against a **target that has moved** since the plan is
`TargetMoved` and not a resume: the prompts are one tree's bytes, and answering them against another would
put two targets under one run's readings without either of them saying so. A completion goes through `extract`; a `None` body is a row of
class **`no-body`** with extract's reason and is never graded. **Rounds 1 to 3 run for the iterate arms
only** (`C-0`, `C-3`): every chain whose last row is not `pass` gets its conversation so far, the model's
whole text as an assistant turn, and one user turn — `feedback.build`'s ≤1,500 characters, or the one fixed
sentence for a `no-body` — and a chain stops at its first `pass`.

**The ceiling is checked before every call, never after** (§8). The estimate is deliberately crude and
deliberately high: prompt characters over 3.5, plus `max_tokens` for *every* request, at a per-model
throughput and price that are **guesses written down as guesses** and replaced by what E1-g is billed. If
the spend already in `calls.jsonl` plus that estimate passes the ceiling, `CeilingReached` — its own type —
is raised and nothing is sent. **A generator that reports no cost has its estimate recorded as the cost**,
with `cost_source` saying which it is: a run whose generator is silent must not read as free.

**`report`** — the readings, and only what a row holds. Per arm: **pass@1** from greedy, **pass@1(sampled)**
over the *k* draws, **pass@k** as the unbiased `1 − C(n−c, k)/C(n, k)` per cell then averaged (at `n = k` it
is any-pass, and under *k* samples it is `None` rather than any-pass wearing the wrong name), and for the
iterate arms the **cumulative pass rate after each round**, so the one-shot figure stays visible. Each is
broken down **by ISA and by type**, with `int8`, `uint8` and `bit1` keeping their own rows *and* summed into
a `low-bit` row. Beside each figure: the class counts, G-hsr's invented names by bucket, **G-reg over the
bodies that compiled** — a body that never built has no init for the question to be about — and the same
rates split by the cell's G-mem label, since §8 binds every number to carry its G-mem reading. **Wrappers
are a section of their own and are never pooled with real bodies.** Tokens, seconds and cost are
`calls.jsonl`'s own. **A missing file is named in `missing`, never read as zero**: a run whose grading never
happened and a run in which nothing passed are two different results.

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
facts arm with no ledger exactly as `prompts` does. Everything else here still writes text only. Before
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

# the same run again with no model at all, from a recorded batch
lattice e1 run runs/qwen-avx2 /path/to/sqlite-vector \
  --ceiling-usd 0.01 --generator replay:completions.jsonl
```

## E1's runner — the order of work

**Nothing here has been run.** `scripts/modal_e1.py` is written and first run by the developer, on Max's
word (E1-g), and the ceiling is checked before every call. The order is fixed:

1. **`lattice e1 plan`** — the requests only. It reads files, calls nothing, and costs nothing. Read the
   prompt sizes off `requests.jsonl` before anything is sent.
2. **The first unit (E1-g): Qwen2.5-Coder-7B, `avx2`, all five arms**, greedy and k = 5, round 0 plus the
   iterate rounds, with the 31 cells' G-mem probes in the same call. `--ceiling-usd` is named by Max.
3. **Price it.** Compare `calls.jsonl`'s measured cost with `e1.PRICING`'s estimate, and replace those
   constants with what Modal billed. E1 was priced at **≈ $1–3 against the $10 ceiling** from the real
   target's prompt sizes; the first unit is what checks that.
4. **Max's word**, before the other two ISAs and before Olmo.
5. **The rest**, then G-graph over the bodies that compiled — one ingest per wave, and not in the loop.

`scripts/modal_e1.py` is a `uv run` script (`modal>=1.1`) and **this package never imports `modal`**: the
seam is a subprocess and two JSONL files, which is also what makes a batch replayable afterwards. Its pins
are the ones both 7Bs already ran under for ADR-099 — vLLM 0.27.1, `transformers>=5.8`,
`VLLM_USE_FLASHINFER_SAMPLER=0`, an A10G at a 16k window, the weights in the `hobbes-hf-cache` volume — and
`MODELS` is the whole of what may run: a model it does not name is refused rather than downloaded, because
a run at an unpinned model is not the run the record describes. One offline batch per call, prefix caching
on, one `SamplingParams` per request so the seed is per request; `llm.chat` for the arms and `llm.generate`
for the G-mem probes, which are continuations a chat template would turn into questions. The GPU rate in
it is a constant to check against Modal's pricing page, not a quote.
