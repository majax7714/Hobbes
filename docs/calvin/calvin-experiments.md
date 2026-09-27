# Calvin experiments — a model that writes one language, starting from sqlite-vector

**Status:** routes accepted (Max, 2026-09-24: "good to go with recommended routes"), with
D-2 amended toward open models (§9); the literature pass is done (§12) and changed the design
(§12.7); **E0 built and accepted on the real target (2026-09-25)**; E1 next · **Type:** programme page — the design space, the experiments in it, the order, the
decisions · **Compute:** none spent;
E0 spends nothing, and every run after it is held until Max names it and its ceiling
**Charter:** [`calvin-charter.md`](calvin-charter.md), with the one reading this page asks of
it in §3 (decision D-1) · **Priors:** ADR-099 ([`olmo3-ttt-results.md`](../ttt/olmo3-ttt-results.md)),
the keyed rounds ([`calvin-potential.md`](calvin-potential.md) and after), Atlas-0
([`atlas-0.md`](../atlas0/atlas-0.md)) · **The target's cell:**
[`sqlite-vector-c-2026-09-12.md`](../oracle/cells/sqlite-vector-c-2026-09-12.md)
**ADR:** [ADR-151](../adr/151-calvin-experiments-skill-in-weights-facts-in-the-ledger.md) (Max:
"good to go", 2026-09-24); this page is its body. Each experiment Max clears gets its own record
beside it.

> **Not versioned** (ADR-103): nothing here moves `VERSION`. What E0 builds lives under
> `bench/calvin/`. **Not training data:** no dispatched session's record feeds any
> experiment on this page (ADR-107's retention amendment). The instruments may be built
> through `hobbes dispatch` like any other work, and their sessions stay evaluation rows.

---

## 0. The question

Max, 2026-09-24: *"our goal is to build a model which can program in a certain language …
for now lets focus on just a model which can make sqlite vector … it can have a teacher
model telling the functions and parts … a lot of what code software is, is repeating and
slightly tweaked patterns for different goals."*

Put as one question the records can be held to:

> **What does a small model need in its weights, and what does it need in its context, to
> write C that compiles, passes the target's tests, and has the target's structure?** And
> how much of that is *pattern*, a known shape re-instantiated along an axis, and not
> memory of this repo?

"Make sqlite-vector" is the far end of a ladder (§5, L0–L4), not the first run. The first
runs are single functions that come with a numeric verifier, because that is where a result
can be attributed.

---

## 1. Principle: attribution before verdict

The same rule as M0 and Atlas-0. A cell that reads badly is attributed before it is read.

| id | component | owns |
|---|---|---|
| **W** | the target and its hold-outs | which code is removed, what is left in the tree, the rename shadow (E2) |
| **M** | the model | base, size, adapter, sampling |
| **C** | the context | what the prompt carries: signature, graph facts, pattern shots, teacher spec |
| **K** | the teacher | who writes a spec, from what, and whether any of it trains anything |
| **G** | the graders | compile, the numeric differential, the target's tests, graph match, HSR, the memorisation probe |

A result is about **M** only after **W**, **C** and **G** have been checked for it. "The 7B
cannot write AVX-512" is a fact about **G** until the differential is known to pass the gold
and fail a seeded wrong body. It is a fact about **W** until the memorisation probe says
whether the gold was recalled.

---

## 2. What the records already say (the priors)

Nothing here starts from zero. Five results bind the design:

| record | what it found | what it means here |
|---|---|---|
| **ADR-099** (TTT, Olmo-3-7B, $5.70) | At 300 LoRA steps, weights took the repo's *regularities*: names, paths, module shape, a loss drop on every gold diff. They took none of its *edges*. At 3,000 steps the edges went in (callers on trained symbols 0.95), and the language effect left over the same steps. The adapter alone found no files (RFE 0.01), and the manifest found them (0.41). | Weights are good at **pattern** and poor at **facts** at the step counts that keep the language. That is this programme's hypothesis, already half-measured. Train skill, serve facts. |
| **Charter §7** | "Not the place facts live": repo facts in weights violate I5, and knowledge in weights overrides live context (ADR-099 §9b). | A model that has *memorised* sqlite-vector is not what this page is for. D-1 asks Max to confirm the reading. |
| **The keyed rounds** (M0, M0-Go, M0-Gate, ~$27) | The floor showed up as a **safety property** (the gate blocks real errors, with no false block on gold), never as a helper. Every round found a defect in its own instrument. | Build and self-test the graders (E0) before any model run. A seeded wrong body must fail every grader, or the grader is not ready. |
| **Atlas-0** (~$22 of $25) | The standard block *invents from sand*: an absent name built of known stems gets a confident answer, pulled toward a real sibling 30% of the time. Typing has to be given, not learned, at that scale. | The intrinsic namespace (`_mm512_…`, `__riscv_v…`) is sand: stems recombined. Expect invented intrinsics, and count them (HSR). The graph and the system headers can *give* the inventory. |
| **C-39** (SWE-bench contamination) | A benchmark the base model has read measures recall. | sqlite-vector is public (Apache-2.0). Every result needs the memorisation probe and a control the base cannot have seen (E2's rename shadow; the post-cutoff code, §4). |

---

## 3. The reading that makes this Calvin: skill in the weights, facts in the ledger

The charter's Calvin is a grounder: it makes an intent true against the repo, and it must
never store the repo. Max's model *writes*. The two meet on one line, and this page proposes
it as the programme's rule:

> **The model may learn the language and its patterns. It never learns the target's
> facts. Those come from the ledger at the SHA, every time.**

This is ADR-099's result turned into a design. It is also the line Karpathy drew on
2025-06-27 (X, `status/1938626382248149433`): the race for an LLM "cognitive core", a model
of a few billion parameters "that maximally sacrifices encyclopedic knowledge for
capability", aggressively tool-using. That is a post, not evidence. The evidence is §12's
knowledge-against-skill rows, which point the same way. The pattern
remark in Max's message is the same point from the other side. Code is mostly known shapes
re-instantiated along an axis, and a shape is exactly what ADR-099's 300-step adapter kept.

**What this changes in the experiments.** Every experiment below separates three things a
model can use to write a correct function, and measures each on its own:
1. **facts** — signatures, callees, types, the intrinsic inventory, from the graph and the headers;
2. **pattern** — sibling functions that differ along a known axis, placed in the context;
3. **skill** — what the weights bring, measured by withholding both of the above.

A model "can program in C" to the degree its score survives with (2) withheld and the target
renamed (E2). It "can make sqlite-vector" to the degree the pair of it and the ledger passes
L3/L4. The two are different claims, and this page never merges them.

---

## 4. Why sqlite-vector

**The graph can grade the code a model writes.** Its cell reads 851/851 semantic edges
confirmed, recall 1,091/1,091 in-repo pairs, lanes 1,084 sites with 0 disagreements, and
poison PASS (0.2.8-beta regrade). Because of that, a generated file's call structure can be
compared with the gold's by Hobbes, and the comparison can be believed. No other target
Hobbes has graded is both at 100/100 and this small.

**The size is right.** `src/` is 10,717 lines: `sqlite-vector.c` 3,963, one scalar kernel
file (`distance-cpu.c`, 989), five SIMD kernel files of 1,027–1,251 each, and headers. The
tests are `test/test_vector.c` (1,230 lines, `make unittest`) and `make unittest-simd`.
`unittest-simd` compiles per translation unit with the ISA flags, and `EXPECT_BACKEND`
asserts the backend really installed. `API.md` (345 lines) is a written spec of the SQL
surface.

**It is a pattern lattice, literally.** Each SIMD file implements the same grid:
- element type: `float32`, `float16`, `bfloat16`, `int8`, `uint8`, plus `bit1`;
- metric: `l2`, `l2_squared`, `cosine`, `dot`, `l1`, plus `hamming` for `bit1`, and an
  `_impl` helper per type;
- ISA: `cpu` (scalar), `sse2`, `avx2`, `avx512`, `neon`, `rvv`.

That is 31 names per ISA file, and each file's `init_distance_functions_<isa>` writes them
into one `dispatch_distance_table[metric][type]`. Every body is written by hand, not
generated by a macro. The same function is written six times, tweaked for each ISA. This is
Max's "repeating and slightly tweaked patterns", with the axes named and a grader on every
cell. Of the 31, **21 are real bodies**: five `_impl`, five `l1`, five `dot`, five `cosine`,
and `bit1`'s `hamming`. **10 are two-line wrappers**: `l2` and `l2_squared` call `_impl`
with `use_sqrt` true or false. The wrappers are pattern at its most trivial, and they are
graded apart so they do not flatter a pass rate. Each file also defines a few local macros
(`MM256_FMA_PS`, `_mm256_abs_ps`, `S8_TO_BIASED_U8_AVX2`); the facts arm has to carry them.

**Every cell has a numeric oracle.** `distance-cpu.c` is the scalar reference. A SIMD body
is correct when it agrees with the scalar one within tolerance, on random inputs and on the
edge cases (a length not a multiple of the lane width, 0, 1, inf and NaN; the files'
`block_has_l2_inf_mismatch_*` helpers show the authors cared). That makes a differential
test per function, stronger than the repo's own suite and deterministic under a seed.

**The host runs three of the six ISAs natively.** The CPU has AVX2 and AVX-512, so
`sse2`, `avx2` and `avx512` run in the image with no emulator. `neon` and `rvv` need
qemu-user in the image (not there today), and their arms are the cell's 118 `unreachable`
silent edges on x86_64. They are later work.

**Post-cutoff code exists.** 1.0.0 is dated 2026-05-25 and 1.1.0 2026-08-24 (the repo's
`CHANGELOG.md`). TurboQuant's 2/3/4-bit scans came with them. Code newer than a base model's
data cutoff is a contamination control in its own right.

**The limits, stated where they bind:**
- The 100/100 is over **static in-repo calls of this build on x86_64**. The 360 dynamic sites
  (calls through `sqlite3ext.h`'s API table) are no edge, and the kernel table is filled by
  assignment, not by call. So graph match grades a kernel's *internal* structure (its
  helpers and the intrinsics it calls), and it grades `sqlite-vector.c`'s call shape. It
  does not see which kernel is registered where. The table read is a text check (G-reg).
- The 1,721 external pairs are the intrinsics, libm and libc. The key records them. Whether
  the *served* graph exposes the intrinsic inventory as a fact source is E0's to check, not
  assumed.
- Building or running the target is running repo code. Every grader runs in the image
  (ADR-092, C-64), never on the host.

---

## 5. The design space

Four axes. An experiment is a point on each.

### 5.1 The model (M)

| id | what | cost | what it can answer |
|---|---|---|---|
| **M-a** | a stock open code model, no training (Qwen2.5-Coder-7B-Instruct, used on this box before; Olmo-3-7B-Instruct) | inference only | how far context carries a model that already knows C |
| **M-b** | M-a plus a LoRA on **C pattern families from other repos**, sqlite-vector excluded | ADR-099-scale, $5–10 a cell | whether pattern training transfers to a lattice the adapter never saw |
| **M-c** | a small model from scratch on a synthetic pattern world (Atlas-0's scale, 30M–300M) | Atlas-0's $25 | the science: do axes of variation become something a block can re-instantiate, and by what circuit |
| **M-d** | a copy-restricted decoder whose identifier vocabulary *is* the ledger plus the headers (the charter's M2) | build cost, then small | I1 by construction: no invented intrinsic is emittable. Precedented (§12.3): monitor-guided decoding let a 1.1B model beat text-davinci-003 on compile rate |
| **M-e** | a specialist already trained for intrinsics (AutoVecCoder-8B, §12.2), if its weights are released | inference only | whether an intrinsics specialist beats a general coder on a lattice it was not built for |

**Olmo-3-7B has a property no other base here has:** its training data is published (per
Ai2; E0 checks it). Whether sqlite-vector is in the mix becomes a search, not a guess. That
makes Olmo the contamination-clean arm even where Qwen writes better C. The 27B is not
touched (the standing rule).

### 5.2 The teacher (K)

| id | the teacher's job | at | note |
|---|---|---|---|
| **K-0** | none; the compiler and the differential are the only teacher | — | the deterministic floor |
| **K-1** | **parses** the request into the task format (below); the student writes the body | inference | Max's "a teacher model telling the functions and parts", narrowed by D-2: an open model, and a parser, not an author. The charter's orchestrator/Calvin split, with the student as Calvin |
| **K-2** | writes **training data** the student learns from (distillation) | training | only from an **open-weights** teacher (D-2) |
| **K-3** | the compiler, the tests and the graph as a **reward** (RL with verifiable reward) | training | expensive; parked until E3 shows a transferable signal |

Two things about the teacher are fixed now, before any design leans on them:
- **Decomposition comes from the graph, not from the teacher.** Which functions exist, their
  signatures, and the build order (leaves first, a topological walk of the call graph) are
  derived deterministically. The teacher adds only what the graph cannot hold: the contract
  in words, the edge cases. That keeps the project's rule that parsers build the skeleton and
  models sit on top.
- **The general model is a parser, not an author** (Max, D-2). Its job is to turn a message
  into the **task format**: one record per unit, whose fields the graph fills where it can
  (name, signature, file, callees with their signatures, callers, the axis neighbours, the
  tests and graders that reach it) and the parser fills only where the graph cannot (the
  contract in one or two lines, the edge cases, which neighbour the unit is "like"). Nothing
  large is generated by the general model, and the writing is the narrow model's. How small
  the parser can be is itself a reading (E4).
- **Claude as a teacher of training data is a terms question, not an engineering one.** As
  I understand Anthropic's terms, outputs may not be used to train a competing model. Read
  the current terms before any K-2 design names Claude. An open-weights teacher with a
  permissive licence avoids the question, and K-1 at inference (nothing trained) does not
  raise it.

### 5.3 The context (C), per call

| id | the prompt carries | isolates |
|---|---|---|
| **C-0** | the file's header down to the hole (includes, types, helpers above it) and the signature | skill |
| **C-1** | C-0 plus **graph facts**: the callees the gold body uses with their signatures (the helpers and the intrinsics), and the callers | facts |
| **C-2** | C-0 plus **pattern shots**: the hole's axis neighbours' bodies, one step along each axis | pattern |
| **C-3** | C-1 and C-2 together | the pair |
| **C-4** | C-0 plus the same number of lines of **non-neighbour** bodies from the same file | the control for "more code in context" |
| **C-5** | C-0 plus a **teacher spec** (K-1) | the teacher's words |

Pattern shots for a hole `(type, metric, isa)` are one step on each axis:
`(type, metric, isa′)`, `(type′, metric, isa)` and `(type, metric′, isa)`. The shape is
A:B :: C:?, analogy completion. The lattice names every neighbour, so the shots are chosen
by rule, not by a model.

### 5.4 The ladder (L) — from one function to the whole repo

| rung | the task | verified by |
|---|---|---|
| **L0** | one held-out kernel function, the rest of the tree present | compile, the differential, `unittest-simd` |
| **L1** | a whole ISA file held out, the other five present | as L0 per function, plus G-reg over `init_distance_functions_<isa>` |
| **L2** | one `sqlite-vector.c` function held out (SQL glue, quantisation) | compile, `make unittest`, graph match on its callees |
| **L3** | `sqlite-vector.c` rebuilt from `API.md` plus the graph's skeleton, kernels given | `make unittest`, graph match over the file |
| **L4** | the repo from `API.md` alone | everything; the far end, held |

### 5.5 The graders (G)

| id | what | deterministic |
|---|---|---|
| **G-compile** | builds in the image with the file's ISA flags | yes |
| **G-diff** | differential vs `distance-cpu.c`: seeded random inputs, the edge cases, a tolerance per type | yes, under a seed |
| **G-test** | `make unittest` / `unittest-simd EXPECT_BACKEND=<isa>` | yes |
| **G-graph** | the generated body's callees vs the gold's (set match; helpers and intrinsics), from an ingest of the patched tree. A use of a file-local macro is a macro edge, which the cell excludes from grading (3,188 of them), so macro uses are compared as text | yes |
| **G-reg** | the `dispatch_distance_table` assignments in the init function vs the gold's | yes (text) |
| **G-hsr** | invented names: identifiers that resolve nowhere at compile or link, split into intrinsics, in-repo symbols and libc. Beside it, a failure class per body (§12.2's taxonomy): **invented** (the name does not exist), **real, wrong** (it exists, and the differential fails on it), **edge** (the body fails only on the edge cases: tail, inf, NaN, saturation) | yes |
| **G-mem** | the memorisation probe: exact continuation of the gold from its first lines at temperature 0. The 0.5 (memorised) and 0.15 (unseen) lines are borrowed from ADR-099's probe, which asked navigation questions, not code | yes, greedy |

**Self-test, as the keyed rounds taught.** Before any model run: the gold must pass every
grader, and a seeded wrong body must fail each, with the right class. Four seeded bodies:
off-by-one tail, wrong intrinsic width, missing inf handling, and an invented intrinsic. A
grader that fails the self-test is fixed before the run, not read around.

---

## 6. The experiments

Each is a card. None is cleared. Costs are estimates, priced on ADR-099's A100 rate
($5.70 for ~3 GPU-hours) and Atlas-0's meter. The first unit of any run is priced against
its estimate before the rest is run.

### E0 — the instruments (no model, no spend)

- **Builds** `bench/calvin/lattice/`: the lattice map (every `(type, metric, isa)` to its span,
  from the graph and the file), the hole-punch (remove a body, leave the signature), the
  shot selector (§5.3), and G-compile, G-diff, G-test, G-graph, G-reg, G-hsr and G-mem, all
  running in the image.
- **The self-test** (§5.5) on all 93 native cells (31 names × `sse2`, `avx2`, `avx512`).
- **Two rename shadows** for E2: every in-repo symbol renamed consistently, the map derived
  from the graph. At 100/100 the graph knows every definition and every in-repo reference.
  The **descriptive** shadow renames to equally meaningful names the base has not read
  (`float32_distance_l2_avx2` → `f32_euclid_x86w256`, from a fixed synonym table). The
  **opaque** shadow renames to meaningless ones (`fn_0417`). They are two because renaming
  costs a model real ability as well as recall (§12.4): names carry meaning. Each shadow
  must compile and pass G-test unchanged, and that is its acceptance.
- **Contamination facts:** the repo's first public date (unshallow the bench clone); whether
  it is in Olmo 3's published data; G-mem on both 7Bs over the 93 golds, at greedy, no
  training. This last one is inference, a few cents, and is cleared separately if Max wants
  E0 strictly free.
- **The feedback loop** for E1's iterate arm: a failing body goes back with the compiler's
  errors or the differential's first failing input, up to three rounds.
- **Gate:** the self-test passes on every grader, and both shadows pass G-test. **Met 2026-09-25**
  (the E0 record below).
- **Contamination facts, read 2026-09-24** (drivers `~/.hobbes/bench/calvin-lattice/`,
  `ages.py` over a full clone, `sqlite-vector-history/`):
  - The repo's first commit is 2025-04-07. The SSE2 and AVX2 kernel files first appear on
    2025-06-21, and AVX-512's on 2025-12-17. The repo has 250 commits to `0c2223a`.
  - **Both E1 bases predate the whole target.** Olmo-3-7B-Instruct's card gives a knowledge
    cutoff of "Dec. 2024". Qwen2.5-Coder was released in late 2024. Pretraining cannot have
    read any sqlite-vector code, so for these two bases E2's shadows measure name-reading,
    not memory. G-mem still runs as a check (post-training data is not dated by the
    cards), and the shadows keep their memory role for any later base.
  - Each cell's body has an age. Of the 93 native bodies at `0c2223a`, the number identical
    at the end of each quarter was: 2025-06-30 18, 2025-09-30 42, 2025-12-31 54,
    2026-03-31 59, 2026-06-30 59. So 34 bodies are newer than 2026-06-30. A later base's
    rows are read by cell age.
  - Olmo 3's data cannot be searched through the public infini-gram API: its documented
    indexes stop at Olmo 2 and Dolma 1.7. OLMoTrace over Dolma 3 exists in Ai2's
    playground only. The dates make the search unnecessary for these bases.

#### E0's record (2026-09-24 to 2026-09-25; five dispatched units, no API or Modal spend)

Built as `bench/calvin/lattice/` (stdlib, 252 tests), through `hobbes dispatch`: units `2fd4` (the map, holes and
task record), `9326` (the graders), `f50c` (two references), `189e` (facts, ages, G-mem probes) and `c141` (shadows,
G-graph). $52.37 of subscription usage in all (the envelopes' figures). Each unit's real-target check was run on the host, in the image,
before its merge, and **each one found a defect the fixture had not**. The acceptance, on sqlite-vector at `0c2223a`:
- **The lattice:** 31 cells per ISA file; per native ISA 5 `impl`, 10 `wrapper`, 16 `body` and 26 slots; nothing
  unmatched. All 186 cells round-trip byte for byte.
- **The self-test:** all 93 native golds `pass`. Each of the four seeded mutants (`syntax` → `compile`,
  `invented`, `wrong`, `edge`) gets its class on all 93 cells: 465 of 465 rows as expected. The gold's worst
  relative error is 4.7e-6 against a 1e-4 tolerance.
- **The two references.** The target's f16 and bf16 SIMD kernels disagree with its scalar kernel on inf and NaN
  inputs, and with each other. bf16 `dot` on overflow is +inf on SSE2 and NaN on AVX2 and AVX-512, and AVX-512's
  f16 `l1`/`l2` agree with the scalar where SSE2's and AVX2's do not. That is 77 cases, reported by every
  self-test. **A case with a non-finite input or a non-finite scalar result is graded against the cell's own
  gold, and every other case against the scalar** (the developer's rule, session `9326`'s review). The uint8 and
  int8 `l2`/`dot` rows allow 1e-5, because the scalar reference accumulates in `float` and drifts ~1e-6 at
  n = 4096.
- **The facts arm:** callees for all 93 cells, 210 rows from Hobbes' graph (`hobbes:semantic`) and the rest from
  the clang key. A header macro's expansion is dropped and the name the source wrote is kept from the intrinsic
  index (6,435 names from clang 18's headers). libm and compiler builtins carry no signature.
- **The shadows:** 493 names renamed and 106 kept, each with its reason (97 not graph symbols, 4 declared by
  another file of the tree, 3 external, 2 entry points). **Both pass the target's own `make unittest` (1,447 of
  1,447) and `make unittest-simd` on AVX-512**, and all 93 golds grade `pass` through each.
- **G-graph:** Jaccard 1.0 on all 93 golds in one wave. A body that passes the numbers but calls an extra helper
  reads 0.667 with the extra named: structure the differential cannot see.
- **Ages and G-mem:** the per-cell ages equal the hand count, and 93 probes are written. No model has run.

What the instruments cannot yet see: NEON and RVV (D-4); the 360 dynamic sites through `sqlite3ext.h`; the kernel
table's wiring, which G-reg reads as text; enum constants and globals, which the shadows keep.

### E1 — the lattice: is it pattern, facts, or skill? (M-a, L0, C-0 to C-4)

- **Question:** on a held-out kernel function, how much does each kind of context move the
  pass rate: facts (C-1), pattern (C-2), both (C-3)? And is pattern more than "more code"
  (C-2 against C-4)?
- **Units:** the 93 native cells: 63 real bodies, read as the result, and 30 wrappers,
  reported apart. Two models (Qwen2.5-Coder-7B, Olmo-3-7B). Five context arms. k = 5 samples
  at a fixed temperature, plus greedy. Every arm one-shot. **An iterate arm** on C-0 and
  C-3 adds up to three feedback rounds. Most of the work in §12.2 needed a compile-and-test
  loop, and a one-shot result alone would understate what a small model can reach.
- **Readings, written before the run:**
  - C-2 − C-4 > 0: pattern is doing work beyond volume, which is the hypothesis in its purest
    form. **The literature leans against it** (§12.4): on problem-solving tasks, models
    drew little from similar problems' solutions and a lot from helpers and namespace
    facts. The lattice is a different case: a sibling is the *same* function on another
    axis, which makes the task closer to translation, and translation between ISAs works
    with feedback (§12.2). Both readings are written down, and neither is expected.
  - C-1 − C-0 may be **negative** on the dense cells. Documentation injected where the model
    already knows the symbol has hurt before (§12.3). Read per cell, not pooled.
  - C-1 − C-0 on G-hsr: whether facts remove invented intrinsics (Atlas-0's sand, on real code).
  - The pass rate by axis of the hole: is `avx512` from `avx2` easier than `int8` from `float32`?
    The lattice says which axis is cheap to cross.
  - Every row beside its G-mem reading. A cell the base recalls is reported apart.
  - **Per ISA and per type, never pooled.** SIMD accuracy is known to fall steeply by ISA
    (§12.2). The low-bit types (`int8`, `uint8`, `bit1`) are a row of their own. No work
    found in §12 grades quantised or binary distance kernels.
- **Cost:** ~93 × 5 × 2 × 6 ≈ 5,600 one-shot generations of a few hundred tokens over prompts
  of 2–10k, plus the iterate arm's rounds on the failures. About an A100-hour: **≈ $4–8;
  ceiling $10** (D-3).
- **P12:** `arm=model+prompt`. One agent per cell, not a Hobbes test. Recorded as such.

#### E1's runner — the design (2026-09-25; routes E1-a to E1-g taken as recommended, Max: "good to go with recommended routes")

These facts were read from the real target at `0c2223a` with E0's instruments. The 93 native cells are 48
`body`, 15 `impl` and 30 `wrapper`. A real body runs 8 to 75 lines, with a median of 33. `prelude_bare` runs
2.4k to 9.7k characters, with a median of 4.0k, about 1.2k tokens. The full `prelude` runs to 38k. A task
record lists every axis neighbour, up to 14, among them `cpu`, `neon`, `rvv` and the one-line wrappers. So
§5.3's "one step on each axis" needs a rule, and E1-a is that rule. `bit1` has no neighbour on the type
axis and none on the metric axis.

- **E1-a — the C-2 shots.** **Recommended:** one shot per axis. Each is the first neighbour on that axis in
  a fixed order that is a real body (`body` or `impl`, never a `wrapper`):
  - `isa′`: `avx2` for `sse2` and `avx512`, and `sse2` for `avx2`. The shots never come from `cpu`, `neon`
    or `rvv`. `cpu` is G-diff's reference, and handing the model that reference is a different reading,
    left for a later arm.
  - `type′`: `float32↔float16`, `bfloat16→float16` and `uint8↔int8`.
  - `metric′`: `l2_impl↔l1` and `dot↔cosine`. `l2` and `l2_squared` are wrappers in every type, and a
    wrapper hole takes its sibling wrapper (`l2↔l2_squared`) on this axis, and wrappers on the others too.

  Where an axis has no real-body neighbour, the arm carries fewer shots, and the record's `shots` field says
  how many. C-4 is then matched to what C-2 actually carried.
- **E1-b — C-4, the volume control.** **Recommended:** whole real bodies from the same file that differ from
  the hole on two or more axes. They are taken in the file's order from a seeded start and added until
  their line count reaches the C-2 shots' count. The last body is cut at that count, so the two arms differ
  by less than one body's lines.
- **E1-c — the prompt and its extraction.** **Recommended:**
  - The prompt goes through the model's own chat template, with one fixed system line.
  - The user turn is the arm's context, then the signature, then: "Write this function. Reply with one C
    code block holding the whole definition."
  - The body is taken from the first fenced block. It is the block's definition of the cell's own name, found
    by `scan`.
  - A completion with no such definition gets a class of its own, `no-body`. It is a failure, reported
    beside `compile` and never folded into it. The model's text is kept whole.
- **E1-d — sampling.** **Recommended:**
  - Greedy, plus k = 5 samples at T = 0.8 and top-p 0.95.
  - `max_tokens` is 1,024. The seed is per (cell, arm, sample).
  - pass@1 is read from greedy, and pass@5 is the unbiased estimate over the five.
- **E1-e — the iterate arm.** **Recommended:**
  - It applies to C-0 and C-3, as the card says. Every failing chain (the greedy one and the five sampled)
    gets up to three rounds, and a chain stops at its first `pass`.
  - Each round's prompt is the conversation so far plus `feedback.build` of the last result, capped at
    1,500 characters from its structured fields.
  - The report reads each round's pass rate, so the one-shot figure stays visible.
- **E1-f — where the model runs.** **Recommended:**
  - vLLM 0.27.1 offline batch on Modal: one function call per model per round. It uses the pinned
    `hobbes-hf-cache` volume and an A10G at a 16k window. Both 7Bs ran there for ADR-099 (`modal_ttt.py`).
  - The runner is written against an injected `generate(requests) -> completions`, so its tests use a fake
    generator. A dispatched unit never calls Modal, and it has no route to Modal.
  - Grading between rounds runs on this box, in the image, through `lattice grade`.
  - Rejected: a served endpoint (`modal_vllm.py`), which costs idle time and gives weaker per-request seeds.
- **E1-g — the first unit.** **Recommended:** Qwen2.5-Coder-7B, the `avx2` file's 31 cells, all five arms,
  greedy and k = 5, round 0 plus the iterate rounds. The G-mem probes for those 31 cells go in the same call.
  Its measured Modal cost is compared with the estimate, and Max's word comes before the other two ISAs and
  Olmo.

**Readings the runner writes** (and nothing else, before the run): pass@1 and pass@5 per arm. Each is broken
down by ISA, by type (with `int8`, `uint8` and `bit1` a row of their own) and by the hole's crossing axis.
Beside each figure go:
- the class counts (`no-body`, `compile`, `invented`, `wrong`, `edge`, `pass`);
- G-hsr's invented names by bucket;
- G-reg;
- the cell's G-mem label.

Wrappers are reported apart. G-graph runs afterwards over the bodies that compiled, one ingest per wave. It
is not in the loop.

**Priced from these sizes, per model:** 465 prompts of about 1.3k to 3k tokens each, sharing a prefix across
the six samples; about 2,800 completions of about 300 tokens each; and the iterate rounds on the failures.
On an A10G at about $1.10/h, that is roughly 20 to 40 minutes a model. The whole of E1 is **≈ $1–3, well
under the $10 ceiling.** It is lower than the card's $4–8 because the real prompts are a quarter of the
card's guess. The first unit checks this price.

**The unit that builds it** (one dispatch, no spend):
- `prompts.py`: the arms, the shot rule and C-4.
- `extract.py`.
- `e1.py`: plan, generate (injected), grade, feedback and rounds. It writes resumable JSONL under a run
  directory, one row per (cell, arm, sample, round), and records `arm=model+prompt`.
- `report.py`.
- `scripts/modal_e1.py`: the batch function. It is written but not run.
- New verbs: `lattice prompts`, and `lattice e1 plan|run|report`.
- Tests on the fixture and on the real target's record shapes.

#### E1-g's record — the first unit (2026-09-25; Qwen2.5-Coder-7B, the `avx2` file, all five arms)

The runner was built through two dispatched units, `8e50` (the arms, `extract`) and `66c5` (the loop, the report, the
Modal script), with $17.42 of subscription usage between them. Each was checked on the real target before it was
merged. `66c5`'s review fixed two defects: a paid round is now kept before it is graded, and a body the grader does not
answer is refused. The run: 961 requests (930 chat, 31 G-mem), k = 5 plus greedy, and three iterate rounds on C-0 and
C-3, at `0c2223a`. Everything is in `~/.hobbes/bench/calvin-lattice/e1/e1g-qwen-avx2/`, and the report is beside it.

**The price.** **$0.74 in all**, against the $10 ceiling. That includes **$0.16 lost on the first call**: the call record's
`completions` count overwrote the completion list in `modal_generator`, and the list sat in a temporary directory.
That was fixed in `9df44a5` (each call's files are kept under the run's `modal-calls/`), and the loss is recorded in
`calls.jsonl`. Round 0 cost $0.17 against an estimate of $0.73. vLLM ran at about 8.0k tokens/s in and 950 tokens/s
out, and the mean completion was about 380 tokens. Each iterate round cost $0.10 to $0.17, most of it the cold start
and the model load that every call pays. **Projected:** the rest of E1 (Qwen's `sse2` and `avx512`, then Olmo's three
ISAs) is about $2 to $3 as run, and less if the ISAs share one call. That is well inside the ceiling.

**The readings, on 21 real cells** (16 `body`, 5 `impl`). n is small, so these are one unit's figures and not
findings:

| arm | pass@1 (greedy) | pass@1 (sampled) | pass@5 | `invented`, round-0 rows of 126 |
|---|---|---|---|---|
| C-0 skill | 0.10 | 0.01 | 0.05 | 21 |
| C-1 facts | 0.00 | 0.01 | 0.05 | 15 |
| C-2 pattern | 0.19 | 0.13 | 0.33 | 22 |
| C-3 both | 0.24 | 0.22 | 0.38 | 16 |
| C-4 volume | 0.05 | 0.05 | 0.14 | 33 |

- **C-2 − C-4 is positive:** +0.14 at pass@1 and +0.19 at pass@5. On this unit, pattern does work beyond volume.
- **C-1 − C-0 is not:** the facts alone moved nothing, and greedy lost its two passes. That is the direction §12.3
  warned of.
- **Iteration adds little:** C-0 goes from 3 to 5 chains passing of 126 over three rounds, and C-3 from 28 to 34.
- **The low-bit row** (9 cells) reads 0.33 at pass@1 on C-3 and 0 on C-0 and C-4.
- **G-mem reads `unseen` on all 21 real bodies**, as the contamination facts predicted.
- **The wrappers are reported apart.** Their pass@1 is 1.00 on C-1 and C-3 (the facts name the `_impl` they call),
  0.80 on C-2, 0.20 on C-0 and 0.00 on C-4.

**What the instruments showed on real rows, before anything was read** (each measured, none fixed in the run):
1. **Parameter names.** 60 rows are `invented` because the model's own definition renamed the target's parameters,
   and the body is grafted under the target's signature. The target is not uniform either: 27 of its 31 `avx2`
   signatures use `v1, v2`, three use `a, b` and one uses `va, vb`. Mapped back and re-graded in the image, **none of the
   53 remappable rows passes** (45 `compile`, 7 `wrong`, 1 `invented`). So the pass rates stand. The `invented` class,
   and G-hsr's `other` bucket, are overstated by these rows.
2. **Truncation.** 112 of 1,734 completions stopped at `max_tokens` = 1,024, and 62 of those are `no-body`. None is a
   repetition loop. Only 17 are at round 0; 95 are in the iterate rounds, where the model adds prose. The round-0
   figures are barely touched, but the iterate figures are, and they are a floor.
3. **G-mem on a wrapper is not evidence.** With K = 2, a three-line wrapper's expected continuation is `}`, so all 10
   read `memorised`. The probe needs a floor on the expected tokens.

#### E1's record — both models, all 93 native cells (2026-09-25; Max: "good to proceed with recommended")

**Before the widening**, the three instrument calls were taken as recommended (unit `06e3`):
- the `param` bucket;
- `max_tokens` 2,048;
- the G-mem evidence floor.

`06e3` also set the measured price. Checked on E1-g's rows, the `param` rule moved exactly the 60 rows that were
measured. The runs are in `~/.hobbes/bench/calvin-lattice/e1/e1-{qwen,olmo}-all/`, each with its report (`.txt`,
`.json`); `nearest-shot-distance.json` is beside them.

**Spend: $6.59 of the $10 ceiling.**
- E1-g: $0.74.
- Qwen: $1.46, in 4 calls.
- Olmo: $4.39, in 2 calls plus one lost ($0.03). Olmo's first call failed because vLLM needs 8.01 GiB of KV cache for
  its 16k window and the A10G has 5.65 GiB free. The Modal script had ignored its own per-model GPU pin. Olmo now
  runs on the L40S (`3e64489`).
- **Olmo passed its $4 run cap by $0.39.** The guard checks the estimate *before* a call ($1.83 spent + $1.57 = $3.40),
  and round 1 cost $2.56: Olmo averages 847 tokens an answer and hit the 2,048 cap on 541 of 2,790 at round 0, and
  its conversations grow. The cap bounds what is sent, not what a call costs. The fix is below.
- **Olmo was stopped after round 1**, by Max's word: at 0.02 pass@1, rounds 2 and 3 would have added about $2 and
  little reading. Round 1 was graded from the kept completions, with a replay generator that cannot spend.

**Qwen2.5-Coder-7B, 63 real bodies** (pass@1 greedy / pass@5):

| arm | pass@1 | pass@5 | by ISA, pass@1 (sse2 / avx2 / avx512) | low-bit pass@1 |
|---|---|---|---|---|
| C-0 skill | 0.03 | 0.05 | 0.00 / 0.10 / 0.00 | 0.00 |
| C-1 facts | 0.00 | 0.02 | 0.00 / 0.00 / 0.00 | 0.00 |
| C-2 pattern | 0.29 | 0.43 | 0.33 / 0.24 / 0.29 | 0.37 |
| C-3 both | 0.38 | 0.54 | 0.52 / 0.24 / 0.38 | 0.52 |
| C-4 volume | 0.05 | 0.10 | 0.05 / 0.05 / 0.05 | 0.00 |

**Olmo-3-7B, 63 real bodies:**

| arm | pass@1 | pass@5 |
|---|---|---|
| C-0 | 0.02 | 0.02 |
| C-1 | 0.00 | 0.02 |
| C-2 | 0.03 | 0.11 |
| C-3 | 0.05 | 0.10 |
| C-4 | 0.00 | 0.02 |

About 80% of Olmo's answers are `invented`: `_mm256_fma_ps`, `_mm256_sqrps`, `float16_t`, `use_sqrt` in a body
that has no such parameter. Its iterate round moved C-3 from 14 to 19 of 378 chains. G-mem reads `unseen` on all 63
real bodies for both models, and `no-evidence` on the 30 wrappers.

**The readings** (written before the run, §6's E1 card), now attributed:
- **Pattern does work beyond volume.** For Qwen, C-2 − C-4 is +0.24 at pass@1 and +0.33 at pass@5. For Olmo it is +0.03
  and +0.09, at the floor. This is the hypothesis in its purest form, and on this lattice it holds for the coder
  model.
- **It is not only near-copying.** Each real body's gold was measured against its nearest shot, as the token share
  that differs. Of the 63 cells, 17 are within 10%, 18 within 10–30%, and 28 are further.

  | Qwen greedy passes | within 10% | 10–30% | beyond 30% |
  |---|---|---|---|
  | C-2 | 6 of 17 | 4 of 18 | 8 of 28 |
  | C-3 | 10 of 17 | 3 of 18 | 11 of 28 |
  | C-0 | 0 of 17 | 2 of 18 | 0 of 28 |

  On 12 cells Qwen wrote the target's gold exactly; the nearest shot there was 3–63 tokens away (mostly
  `int8↔uint8` and `float16↔bfloat16`). No pass copies its ISA shot verbatim. Every pass uses the hole's own vector
  width, which rules out the compile-flag superset: `avx2` intrinsics compile under AVX-512's flags.
- **Facts alone did not help, and facts with pattern did.** C-1 − C-0 is −0.03 (Qwen) and −0.02 (Olmo). This is the
  direction §12.3 warned of. C-3 − C-2 is +0.09 at pass@1 and +0.11 at pass@5 for Qwen. The facts arm names the
  callees; what it lacks, alone, is how they compose.
- **Invented intrinsics:** for Qwen, 108 of C-0's 378 round-0 rows are `invented`, 65 of C-1's and 48 of C-3's. The
  ledger removes some of the sand, but not most of it.
- **Iteration adds little:** Qwen's C-3 goes from 0.32 to 0.38 of chains over three rounds, and its C-0 from 0.01 to
  0.03.
- **The wrappers** are one call to the type's `_impl`. Qwen passes them at 1.00 on C-1, since the facts name the
  callee, and Olmo at 0.03. Wrappers are reported apart, as designed.

**The noise floor, read after (2026-09-26, `lattice e1 paired`; no spend).** Both arms grade the same 63
bodies, so each gap was tested paired by cell (`bench/calvin/lattice/README.md`, `paired`: McNemar on the
greedy pass and on any-pass at n = k, and an exact sign-flip test on the per-cell sampled rates;
two-sided, uncorrected). Outputs are in `~/.hobbes/bench/calvin-lattice/e3/noise-floor/`.

| Qwen, bodies | pass@1 (lost / gained, p) | pass@5 (p) | pass@1 sampled (p) |
|---|---|---|---|
| C-2 − C-4, pattern beyond volume | +0.24 (3 / 18, **0.0015**) | +0.33 (**< 0.0001**) | +0.16 (**0.0001**) |
| C-2 − C-0 | +0.25 (2 / 18, 0.0004) | +0.38 (< 0.0001) | +0.18 (< 0.0001) |
| C-3 − C-2, facts beside pattern | +0.10 (4 / 10, **0.18**) | +0.11 (0.17) | +0.11 (**0.024**) |
| C-1 − C-0, facts alone | −0.03 (2 / 0, 0.50) | −0.03 (0.63) | −0.00 (1.0) |

- **The pattern effect is firm.** It is the result E3's branch rests on.
- **"Facts help beside pattern" is suggestive, not established.** Its greedy and pass@5 gaps are p ≈ 0.17,
  and only the sampled rate is under 0.05. It is read as a direction until a run registered for it
  says more.
- **"Facts alone did not help" is a null, not a harm.** −0.03 is two cells.
- **Olmo:** C-2 − C-4 is +0.03 greedy (p 0.50) and +0.035 sampled (p 0.039), at the floor, as read.

**What E1 selects** (§7): pattern does work in context, and facts help only beside it. §7's branch for that is **E3**
(train the pattern in, then test transfer), **after E2's shadow**: E2 asks whether the pattern reading survives
names the base has not read. The contamination facts make memory unlikely for these two bases, but name-reading is
not ruled out. The candidates, for Max:
- E2's two shadows on Qwen, C-2 and C-3 only, at about $1;
- the guard fix: a Modal call's `timeout` derived from the budget left, so a cap bounds what a call costs;
- whether Olmo stays an arm. On this lattice it does not write intrinsics.

### E2 — the rename shadow: memory or skill? (M-a, L0/L2, on the shadow)

- **Question:** does E1's score survive when the in-repo names are ones the base has never
  read? The intrinsics and the SQLite API are not renamed, since they are the language, not
  the repo.
- **Units:** E1's best and worst arms, on both shadows, plus L2's `sqlite-vector.c` holes.
- **Reading:** the gap between the original and the **descriptive** shadow is the memorised
  share. The further gap to the **opaque** shadow is how much the model reads names, which
  §12.4 shows is real ability, not memory. A small first gap with G-mem low is the first
  evidence of skill.
- **Cost:** about half of E1's. Could fold into E1 as a sixth arm.

#### E2's runner — the design (2026-09-26; routes E2-a to E2-g taken as recommended, Max: "All as recommended", ceiling $3)

These facts were read from the tree and the drivers on 2026-09-26:
- `lattice e1 plan` and `e1 run` take no `--rename`. `map`, `task`, `grade` and `graph-grade` do, and
  `shadow.grading` is the seam that lets the graders read a shadow.
- A cell's id is its grid position (`<isa>/<type>/<metric>`), and the seed is drawn from the id. So a shadow run
  asks with E1's own seeds, and only the names differ.
- A written shadow is not a git checkout, so `meta.json`'s `target_sha` would be `None` and `_same_target`
  would check nothing.
- Only the descriptive shadow is on disk (`~/.hobbes/bench/calvin-lattice/shadows/descriptive/`: 493 renamed,
  106 kept, 88 `sv_`-prefixed). None of the 88 is a kernel name; all are `sqlite-vector.c`'s, which no L0 prompt
  carries. The opaque shadow was accepted at E0 but not kept.
- The facts arm reads the target's `graph.json` and clang key by name and by column. A shadow shifts columns and
  changes every name.
- E1's Qwen calls: round 0 cost $0.38 for five arms, and the three iterate rounds $1.08, since the conversations
  grow.
- **The run cap has a hole beside the one E1 found.** A generator call that fails writes no `calls.jsonl` row,
  so `spent()` reads the lost call as free. Olmo's lost call ($0.03) was counted by hand.

Routes (recommended first):

- **E2-a — what runs.** **Recommended:** Qwen, arms C-2 and C-3, all 93 native cells, on both shadows. Greedy
  plus k = 5; C-3 iterates for three rounds as in E1; the G-mem probes go in round 0. The original's figures are
  E1's Qwen rows, at the same model, params and seeds, and nothing is re-run. The readings: descriptive − original
  is what renaming to equally meaningful names costs. Both bases predate the target (E0), so this gap is
  name-reading, not memory. opaque − descriptive is what meaning in the names carries. **b:** add C-0 and C-4, as
  the card's "best and worst arms" says. At 0.03 and 0.05 they cannot fall far, so this is about $0.6 for little
  reading. L2's `sqlite-vector.c` holes wait for an L2 instrument, which E0 did not build.
- **E2-b — the facts arm in a shadow.** **Recommended:**
  - Read E1's ledger at the target. Write every name in its rows (callee, signature, definition line) forward
    through the shadow's own map with `shadow.apply`, the same renamer that wrote the shadow's files.
  - `meta.json` records `ledger.translated_through`, the map's digest.
  - This is exact by construction, because the map is a bijection (`Collision` refuses otherwise).
  - **b:** re-derive the ledger on the shadow instead: a Hobbes ingest of the shadow, plus a clang key made over
    it in the image. This means two more instrument runs, with nothing gained for this reading.
- **E2-c — the shadow's identity, and a leak gate.** **Recommended:**
  - `e1 plan --rename <shadow-map.json>` builds the lattice through the reverse map. `meta.json` records `shadow:
    {style, map_sha256, tree_sha256, from_sha}`, and `_same_target` checks the tree digest where there is no SHA.
  - The plan **refuses** (`ShadowLeak`, its own type, P10) when any prompt holds a renamed original as an
    identifier token.
  - The names the shadow keeps (enum constants, file-scope declarations, the entry point) are listed in
    `meta.json` with their reasons. They leak by design, and the record says so.
  - `e1 run` takes no new flag. It reads the shadow from `meta.json`, refuses a target whose map digest is not
    the plan's, and grades in the image through `lattice grade --rename /target/shadow-map.json`: the map sits
    at the shadow's root, which the image already mounts.
- **E2-d — the guard fix.** **Recommended:**
  - `modal_e1.py` takes `--max-usd`, and the remote function runs under `timeout = min(4 h, max_usd / GPU $/s −
    120 s)` (`with_options(timeout=…)`).
  - The runner passes `ceiling − spent`, so a call cannot bill past the cap even when the estimate is wrong.
  - A call that fails or times out writes its `calls.jsonl` row, at the host-wall price with `answered: 0`,
    before `GenerateFailed` goes up. Then `spent()` never reads a lost call as free.
  - A timeout loses its batch. The estimate check still refuses first, so the timeout only acts when the estimate
    was wrong. **b:** split a round into chunks whose estimates each fit, which is more calls and more cold
    starts.
- **E2-e — the opaque shadow.** **Recommended:** write it with `lattice shadow --style opaque` beside the
  descriptive one. Accept it as E0 did, in the image and before any spend: `make unittest`, `make
  unittest-simd`, and all 93 golds `pass` through it. This is the developer's check, not the unit's.
- **E2-f — Olmo.** **Recommended:** Olmo is not an arm from E2 on. On this lattice it does not write intrinsics
  (80% `invented`), so a shadow can only move it along the floor. E1's record keeps its rows. **b:** run it on
  both shadows too, for about $3–4 more.
- **E2-g — the price and the ceiling.** From E1's calls: per shadow, round 0 with two arms is about $0.15 and
  C-3's iterate rounds about $0.55, with cold starts included. That is **≈ $1.4 for both shadows**. **Recommended
  ceiling: $3**, as one run per shadow at `--ceiling-usd 1.50` each. The descriptive run goes first, and its
  measured cost is compared with this estimate before the opaque run is sent.

**The unit that builds it** (one dispatch, no spend): `e1 plan|run --rename`, with E2-b's translation, E2-c's
identity and leak gate, and E2-d in `e1.py` and `modal_e1.py`. Tests on the fixture's shadow, among them a
planted leak refused and a failed call priced. `e1 report` reads the shadow runs unchanged. A small
`e2 compare <original-run> <shadow-run>…` gives the per-cell and per-arm deltas, from the rows alone.

#### E2's record — Qwen on both shadows (2026-09-26; ceiling $3, Max: "All as recommended")

**Built and checked first, with no spend.** Unit `157a` built the runner (104 turns, $15.15 of subscription
usage). The opaque shadow was then written and accepted in the image (E2-e):
- 493 names renamed and 106 kept;
- `make unittest` 1,447 of 1,447, and `make unittest-simd` 1,447 of 1,447 on the AVX-512 backend;
- all 93 golds `pass`.

Three checks on the real target, before any call:
- **Every shadow prompt is E1's under the rename.** On each shadow, all 1,209 prompts equal E1's round-0 prompt
  with `shadow.apply` of that shadow's map, at E1's ids, seeds and params. E1's own C-2/C-3 plan, re-made with the
  same ledger paths, reproduced E1's requests 1,116 of 1,116.
- The leak gate passed on both shadows.
- The shadow golds, replayed through each shadow's run path, grade 93 of 93 `pass`.

So the names are the only variable, and E1's Qwen rows are the original. The runs and reports are in
`~/.hobbes/bench/calvin-lattice/e2/` (`qwen-{descriptive,opaque}/`, `*.report.{txt,json}`, `compare.{txt,json}`).

**Spend: $1.89 of the $3 ceiling.** The descriptive run cost $0.88 and the opaque run $1.01, 4 calls each. I had
estimated ≈ $1.4, so the runs came in 35% over it. The runner's own pre-call estimates ran high, as designed:
round 0 was estimated at $0.92 and cost $0.22. No call came near its `--max-usd` timeout.

**Qwen2.5-Coder-7B, 63 real bodies** (pass@1 greedy / pass@1 over the five samples / pass@5):

| arm | original (E1) | descriptive | opaque |
|---|---|---|---|
| C-2 pattern | 0.29 / 0.19 / 0.43 | 0.21 / 0.21 / 0.44 | 0.05 / 0.05 / 0.19 |
| C-3 both | 0.38 / 0.30 / 0.54 | 0.41 / 0.33 / 0.59 | 0.24 / 0.20 / 0.37 |

For reference, E1's C-0 is 0.03 / 0.01 / 0.05 and its C-4 (volume) 0.05 / 0.03 / 0.10.

**The 30 wrappers**, same measures:

| arm | original (E1) | descriptive | opaque |
|---|---|---|---|
| C-2 | 0.83 / 0.77 / 0.97 | 0.60 / 0.53 / 0.80 | 0.40 / 0.32 / 0.63 |
| C-3 | 1.00 / 0.97 / 1.00 | 1.00 / 0.95 / 1.00 | 0.73 / 0.69 / 0.93 |

Iterate chains on C-3 bodies went 0.35 → 0.40 over three rounds on the descriptive shadow, and 0.21 → 0.24 on the
opaque. G-mem reads `unseen` on the real bodies of both shadows.

**The readings, attributed:**
- **Descriptive names keep the pattern effect on bodies.**
  - On C-3, all three measures rise: +0.03, +0.03 and +0.05.
  - On C-2, the sampled pass@1 and pass@5 rise by +0.02 each. Greedy falls by 0.08, and across all 93 cells, wrappers
    included, the greedy flips are 17 lost and 5 gained. The five-sample figures do not fall, so the greedy drop
    reads as single-sample variance.
  - Both bases predate the target (E0), so memory was already ruled out. This says the gain does not depend on the
    target's own spelling either.
- **The descriptive drop on C-2's wrappers is the synonym table's wording.** A wrapper is one call to its type's
  `_impl`. Read in the failing rows:
  - The table spells the ISAs `x86v1`, `x86v2` and `x86v4`. An `sse2` hole's greedy answer called
    `f32_dist_euclid_core_x86v2`, the avx2 name copied from its `isa′` shot.
  - `l2_impl` → `core` hides that an impl exists to call, and some wrapper holes got a whole kernel instead.
  - C-3, whose facts name the callee, keeps 1.00.

  This is a fact about these substitutions, not about memory.
- **The opaque shadow removes the task statement, not only the names.**
  - The hole reads `float fn_0042 (const void *a, const void *b, int n)`, where the original reads
    `int8_distance_cosine_avx2`. Nothing else in the prompt names the metric or the type, and every shot is `fn_…`
    too.
  - The extra failures are `wrong` (compiles, numbers wrong), not `invented`: C-2 has 269 wrong rows against E1's
    162, and fewer invented.
  - Of the greedy C-2 bodies graded `wrong`, the share nearest to a **sibling metric's** gold (the same ISA and type,
    by token similarity with the names mapped back) is 7 of 23 in the original, 9 of 27 in the descriptive shadow,
    and **30 of 49 in the opaque shadow**. Without the name, the model writes the neighbouring metric.
  - So opaque − descriptive measures the loss of the specification. The E2 card's reading, "how much the model
    reads names", **does not hold as worded** for this shadow. The card should have seen that the name is the only
    place the task is stated.
  - C-3 keeps 0.24 because its facts name the callees, which partly restates the task.

**The noise floor, read after (2026-09-26, `e2 compare`'s paired tests; no spend).** Shadow − original,
paired by cell, bodies:

| arm | descriptive: pass@1 (lost / gained, p) · sampled p | opaque: pass@1 (lost / gained, p) · sampled p |
|---|---|---|
| C-2 | −0.08 (9 / 4, 0.27) · 0.63 | −0.24 (17 / 2, **0.0007**) · 0.0001 |
| C-3 | +0.03 (5 / 7, 0.77) · 0.47 | −0.14 (14 / 5, 0.064) · 0.027 |

- **No descriptive delta on bodies is distinguishable from zero.** "The descriptive shadow keeps the effect"
  stands as *no measurable cost*. The rises on C-3 (+0.03 to +0.05) are not read as gains, and C-2's greedy
  drop is noise, as the record said.
- **The same prompts under equally meaningful names moved 12 to 17 greedy bodies per arm**, with the net
  near zero. That churn is the floor any comparison at this scale sits on (E3's card, below).
- **The descriptive wrapper drop on C-2 is real** (−0.23, 8 / 1, p 0.039; sampled p 0.0003), and its cause is
  the one the record reads: the synonym table's words.
- **The opaque loss on C-2 bodies is real.** Its cause is the task statement's loss, as read above.

**What E2 selects** (§7): pattern does work in context, and the descriptive shadow keeps it. §7's branch for that
is **E3**, training the pattern in and testing whether it transfers. For Max:
- **E3's design**, with no spend, on the card's $25 proposal. Its training families come from other repos under
  their own names, so the descriptive result is the relevant control.
- **Optionally, a stated-task opaque arm**, at about $1: the opaque prompt plus one fixed sentence naming the metric,
  the type and the ISA. It would measure name-reading beyond the specification. It could instead fold into E3's
  evaluation as a control.
- The descriptive table's ISA words (`x86vN`) and `core` are E0's choices. They stay as run, and the record says
  what they cost.

### E3 — pattern training that transfers (M-b, L0/L1)

- **Question:** a LoRA trained on C pattern families from *other* repos, sqlite-vector
  excluded and checked by G-mem: does it lift E1's C-0 arm (skill) toward E1's C-2 arm
  (pattern in context)?
- **Data (D):** families mined deterministically by Hobbes from the C and C++ cells already
  ingested and from new C draws: symbols whose names differ in one token and whose callee
  multisets match up to that token. The training task is E1's: given the neighbours, write
  the member. This is a bench miner and not a Hobbes feature. It is also the first place a
  pattern-family query would be *used*, which is worth noting for later.
- **Only validated examples train** (§12.5: SelfCodeAlign, MultiPL-T, OSS-Instruct). Where a
  family is widened with generated siblings, an open model writes them, seeded from real
  members, and only siblings that compile and pass their own differential are kept. **No
  example depends on a fact the prompt does not carry.** Fine-tuning on unfamiliar facts
  teaches guessing (Kang et al., Gekhman et al., §12.5). A fact the answer needs is in the
  example's context, or the example is dropped.
- **Controls:** ADR-099's shuffled-answers adapter (the same tokens, the family pairing
  broken), and a steps ablation (300 and 3,000), because ADR-099 showed the language effect
  leaving as facts come in.
- **Cost:** ADR-099-scale per adapter, ≈ $5–10 each, two or three adapters. **Ceiling
  proposed $25.** Held until E1 says pattern does work in context (C-2 − C-4 > 0). If it does
  not, there is nothing to train toward.

#### E3's card, revised (2026-09-26; no spend; Max: "good to proceed with that recommended")

Three no-spend checks were made before E3's design is priced: the noise floor (E1's and E2's addenda
above), a count of the training pool, and a reading of what the card measures. Together they change the
card in four places. **E3 does not train until the pool below exists.**

**1. What is measured: two registered comparisons, not one.** The training task is "given the neighbours,
write the member", but C-0 carries no neighbours. So an adapter trained on that task is likelier to lift
C-2 (using shots) than C-0 (the pattern moved into the weights). Both readings are registered before the
run, each against the **shuffled-answers adapter** (the same tokens, the family pairing broken), never
against the base alone:
- **E3-use:** adapter C-2 − shuffled C-2. Does training make the model better at using examples?
- **E3-weights:** adapter C-0 − shuffled C-0. Did the pattern move into the weights?

The readings, written now:
- use lifts and weights does not: training teaches the use of examples, and E4's graph-served shots are
  the route;
- weights lifts: the charter's §3 reading holds, with skill in the weights;
- neither lifts beyond the shuffled adapter: the gain is the format, not the pattern;
- the adapter lifts and so does the shuffled one: the same.

C-3 and C-4 are run beside them, described and not tested.

**2. The noise floor sets the evaluation.**
- At 63 bodies, renaming alone moved 12 to 17 greedy cells per arm (E2).
- At that churn, a greedy gap needs a net of about **9 cells (+0.14)** to reach p < 0.05; at 6 cells moved, all
  one way, the floor is +0.10.
- The sampled rate is the more sensitive figure: it found C-3 − C-2 at p 0.024 where the greedy pass read
  0.18.
- So **each registered comparison's primary figure is pass@1(sampled), with the paired sign-flip test**, and
  the evaluation draws **k = 10** rather than 5, to steady each cell's rate. E2's round 0 cost $0.22 for two
  arms at k = 5, so at the base model's rates this is about $0.2 an arm, with no iterate rounds. An adapter
  served on Modal is re-priced on its first unit.
- The two tests are the only ones read as findings, and everything else is described.
- On E3-weights, C-0's base is 0.03, so the figure can only rise, and the floor is the one to beat.

**3. The pool: the card's family rule fails its own calibration, and the ingested pool is far too small.**
The count (`~/.hobbes/bench/calvin-lattice/e3/family-count/`, `RESULTS.md`, `count.py`) read every C
and C++ graph on this box: cJSON, fmt, args, bpftop and ScummVM. sqlite-vector was excluded and used only
as the calibration.
- **Calibration.** On sqlite-vector itself, the card's rule (names differing in one token, callee multisets
  equal up to it) groups **18 of the 63 real bodies** into families of two or more, and 9 into families of
  three or more. It does catch all 30 wrappers. There are two causes:
  - Intrinsics resolve to system headers, so they are not repo edges, and a kernel's callee multiset is
    only its helpers and macros.
  - The helpers are spelled differently along the lattice's own axes (`f16_is_inf` against
    `bfloat16_is_inf`), so masking the member's token does not reach them.
- **A body-shape rule** groups 63 of 63: body tokens with the varying token masked, similarity ≥ 0.6. It
  was fitted on this target, though, so that figure is a fit, not a test. It needs a second lattice repo
  before it mines anything.
- **The permissively licensed pool** (cJSON, fmt, args), after removing wrappers and thin bodies:

  | rule | families / members, size ≥ 2 | size ≥ 3 |
  |---|---|---|
  | the card's | 15 / 43 | 4 / 21 |
  | body-shape | 38 / 93 | 8 / 41 |

  ADR-099 trained on 13,688 records, so this pool is **two to three orders of magnitude short**.
- **ScummVM reaches the scale**, with 16k to 20k tasks, but E3 cannot use it as is:
  - it is GPL-3.0;
  - its tests reach none of the families;
  - 37% of the families are near-copies (lastexpress's generated `CONS_*` handlers);
  - 22% are name coincidences;
  - none has a type×ISA shape.
- **Validation.** None of the pool repos has a numeric reference for a differential. Test reach varies:
  cJSON's tests reach 31 of its 31 strict members, fmt's 0 of 8, and args and ScummVM none. The card's "only
  examples that compile and pass their own differential train" has no instrument yet for mined members.

So **E3's first step is a draw of permissively licensed C repos with real kernel lattices**, not a
training run. These are SIMD or numeric libraries with a scalar reference, or tests that reach their
families, drawn by a written rule as the JavaScript cells were. The step also tests the body-shape rule
on the first draw that has a known lattice, and counts what the pool reaches before any adapter is priced.

**4. The stated-task control folds in.** E2's opaque shadow removed the task statement with the names. So
E3's evaluation carries one **stated-task opaque arm** (the opaque prompt plus one fixed sentence naming
the metric, the type and the ISA) on the base and on the adapter. It reads name-reading beyond the
specification, at about $0.5 a model, and replaces E2's optional $1 run.

**The ceiling.** The card's $25 stands for the training runs only once the pool exists. The draw and the
count spend nothing. The ceiling is re-priced with the pool's real size, since the steps ablation (300 and
3,000) is sized by it.

#### E3's pool — the C lattice draw's record (2026-09-26; D-5 a; no spend)

The draw was run by the rule committed before it (`DRAW-RULE.md`, sha256 `f4b6e2abf25b2035…`, verified
unchanged). A background fork executed it, and the headline figures, the lane A fixture and the crash were
re-checked by hand. Everything is in `~/.hobbes/bench/calvin-lattice/e3/draw/` (`RESULTS.md`, `final.json`,
`dedupe.json`, `precision-read*.jsonl`, `revise/`, the scripts).

- **The pool.** 70 queries, none truncated, 1,421 repos.
- **Gates 1–4 and 6:** 54 forks or archived, 6 sqlite-vector or sqliteai, 23 licence mismatches, 1,207 with
  lattices too small, 67 C++ by majority. **64 passed.**
- **Gate 5 (a contained ingest), in pool order:**
  - **40 taken** at the cap, with 20 passers not reached.
  - 4 failed: libvpx and awtk had 89% and 81% of ISA members named; hypersonic-rle-kit and moonlab failed on
    the two Hobbes defects below.
- **Tasks over the 40 taken:**
  - 1,438 by the ISA rule, 33,634 by the body-shape rule, 33,902 in their union.
  - **24,222 unique** across the pool. 28.6% were copies: riboseek vendors MMseqs2 (46 of its 5,623 are its
    own), and miniaudio/dr_libs recur.
  - **2,062 unique and validated:** 896 with a scalar-reference sibling, 1,520 reached by the repo's tests.
    Five repos hold 1,469 of them.
  - 988 tasks are in two-axis families, sqlite-vector's shape.
- **The target's neighbour.** sqlite-ndvss, another SQLite vector extension, has no member within 0.6 of any of
  sqlite-vector's 93 golds (maximum 0.46).

**The body-shape rule's bars.**

| rule | where measured | recall (bar ≥ 0.90) | coincidence (bar ≤ 20%) |
|---|---|---|---|
| registered | all 40 | **0.814, fails** | 16.1% (123 of 763 read), passes |
| V3 (masking, threshold 0.5), the best revision | first half | 0.874 | — |
| V3 | the held-out second half | **0.945** | **20.05%** (78 of 389), fails by one family |

**No rule passed both bars on held-out repos.** Of the registered rule's first-half misses, 175 of 183 are
ISA ports whose bodies genuinely differ, and 8 are tokenisation. So the recall bar partly graded the body
rule against name families that are not body patterns. The rule's wording is at fault there, and so is mine.
The pool's union takes those ports by name anyway.

**The rule's wording, where it read wrong** (recorded, not re-run):
- gate 6 counts `.h` as C, so two C++ repos passed (MMseqs2, The-Modern-Cpp-Challenge);
- the scalar words omit `port` and `portable`;
- gate 4 counts members before the thin filter.

**The reading, against the one written before the draw.** The registered bands count *validated* tasks.
**2,062 is in the 1,000–5,000 band:** "E3 priced at 300 steps only, with the pool's size stated as the limit,
or a widening rule proposed to Max first." What the band does not settle:
- **Does mined real code need validation?** The card requires it of *generated* siblings. A real member is the
  repo's own shipped code, and its "validation" only says whether a model's rewrite of it could be checked,
  which training does not need. Counted without that requirement, the pool is **24,222 unique tasks**, the
  ≥ 5,000 band.
- **Target-likeness is thin.** 988 two-axis tasks, and none of the pool is a type × metric × ISA lattice as
  dense as sqlite-vector's.

These are for Max (D-7, §9).

**Two Hobbes defects the draw found**, each reproduced here:
- **C lane A loses a whole file silently.** Two consecutive definitions, each preceded by an attribute
  specifier inside an `#ifndef` guard (`hypersonic-fixture/FIXTURE.c`, 8 lines), parse as one top-level
  ERROR node under tree-sitter-c 0.24.2, and `csource` keeps **no symbols** from it. **Corrected the same day:**
  the loss is not silent. `_parse_file`'s second value is `had_error`, which I first read as "ok", and
  `extract_c` records the file in `extraction_errors` as "parsed with syntax errors … the sites it could still
  see are kept". That wording does not say every definition was lost. hypersonic has no compile database
  (C-135), so ADR-129's recovery from the index has nothing to read. 13 non-reproducing variants are kept beside it. IN/OUT parameter macros are not
  the cause, contrary to the first reading. C-131 is the nearest register entry and does not name this loss.
- **One deep Rust file aborts a repo's whole ingest.** moonlab @ `cd3b234`'s
  `bindings/rust/moonlab-sys/build.rs` is a bindgen builder chain of 537 calls in one expression.
  `rustsource._walk`, a recursive generator, exceeds Python's recursion limit, and the `RecursionError`
  ends the ingest. `javasource._walk` has the same shape.

#### E3's price on D-7's pool (2026-09-26; no spend)

**The pool:** 24,222 unique tasks (D-7 a). **The model:** Qwen2.5-Coder-7B, E1's student. **The recipe:**
ADR-099's (LoRA r=32 α=64, batch 16, ≤ 2k tokens, lr 2e-4 cosine). A 300-step adapter took **667 s of A100**
there (`olmo3-ttt-results.md`), and the whole ADR-099 run was about 3 GPU-hours and $5.70. At that meter's rate
(about $1.90 an hour):

| line | what | estimate |
|---|---|---|
| training | the adapter and the shuffled-answers control, at 300 steps (4,800 examples, 0.2 epoch) and at 3,000 (48,000, 2 epochs) | 2 × $0.35 + 2 × $3.50 ≈ **$8** |
| evaluation | base and four adapters × {C-0, C-2, C-3, C-4, stated-task opaque} × 93 cells × (greedy + k = 10), at E2's measured $0.2 an arm a model | 5 × 5 × $0.2 ≈ **$5** |
| overhead | cold starts, data loading, LoRA serving, E2's 35% over-estimate | ≈ **$4** |
| **total** | | **≈ $17**, inside the card's $25 |

- **Order, each step priced against its estimate before the next.**
  - The 300-step pair first (about $1 training plus its evaluation).
  - The 3,000-step pair only after the 300-step reading. ADR-099 saw the effect leave as facts came in, so the
    steps ablation is the reading, not a formality.
- **Before any of it, the corpus** (a dispatched unit, no spend). It turns the draw's members into training
  examples ("given the neighbours, write the member") with:
  - sqlite-vector excluded by name and by near-copy (ratio ≥ 0.6 against the 93 golds);
  - dedupe across repos by body hash, as the draw did;
  - no dispatched session's text (`units_from_git`'s refusal and a test for it, §8);
  - the prompt/answer token lengths measured, which replaces this table's ≤ 2k assumption;
  - G-mem run on the base before training, at the 93 cells, as E1 did.
- **For Max (D-9):** clear the corpus unit now, and E3's run at the $25 ceiling once the corpus is reviewed.

#### E3's record — the 300-step pair on Qwen2.5-Coder-7B (2026-09-26; D-9, ceiling $25; spent ≈ $5.55)

**What ran.**
- **Corpus:** 21,290 examples from the draw's 40 repos (session `c4ef`, with the review's self-copy fix).
- **Adapters:** a pattern adapter and its shuffled control, 300 steps each, ADR-099's recipe, A100-80GB.
  - Pattern: 2,551 s, about $1.77. Shuffled: 2,413 s, about $1.68.
  - **About 5× my estimate:** 8.5 s a step against ADR-099's 2.2.
  - **728 pattern and 228 shuffled records were truncated at 2,048 tokens.** The corpus's 7,600-character cap
    assumed four characters a token, and C is denser. The two corpora hold the same records, and the answers
    moved between them changed which ones ran long.
- **Evaluation:** base, pattern and shuffled, each over C-0, C-2, C-3 and C-4, 93 cells, k = 10, no iterate
  rounds ($0.51, $0.62 and $0.48). Then C-2 on the opaque shadow with the stated-task sentence, for each model
  (about $0.16 each).
- Session `fe37` built the adapter serving, whose first live use was here.
- The base reproduces E1: C-0 0.03 and C-2 0.30 greedy, against E1's 0.03 and 0.29.
- **G-mem reads `unseen` on 62 bodies for all three models.** Neither adapter memorised the target.
- Runs are in `~/.hobbes/bench/calvin-lattice/e3/runs/` (`spend.md`, `*.manifest.json`, `e3-use-weights.json`,
  `base-vs-*.json`).

**Real bodies, paired by cell, exact:**

| comparison | C-2 sampled (primary) | C-2 greedy | C-0 sampled | C-0 greedy |
|---|---|---|---|---|
| **pattern − shuffled** (registered) | **+0.351, p < 0.0001** | +0.476 (30 / 0) | +0.006, p 0.25 | +0.032 |
| pattern − base | **+0.148, p 0.0002** | +0.175 (17 / 6), p 0.035 | −0.006, p 0.44 | +0.000 |
| shuffled − base | −0.203, p < 0.0001 | −0.302 (0 / 19) | −0.013, p 0.03 | −0.032 |
| pattern − base, **opaque + stated task** | −0.025, p 0.45 | +0.000 (7 / 7) | — | — |

C-3, described: pattern − base +0.224 sampled. C-4, the volume control, does not move with the pattern adapter
(−0.027).

**The readings, against the ones written before the run:**
- **"Use lifts and weights does not" holds.** Training on the draw's families lifts the use of examples (C-2,
  C-3) and leaves the no-example arm where it was. The pattern did not move into the weights at 300 steps.
- **The registered figure is inflated by its control, and I record that as a design fault.**
  - The shuffled adapter is **degenerate**. Against the base it loses 19 C-2 cells and gains none. On the opaque
    shadow it answers every prompt with an unrelated function (1,023 of 1,023 `no-body`; GLEW code).
  - The derangement moved **whole definitions**, names included, so the control taught the model to ignore the
    signature it is asked for.
  - The honest headline is **pattern − base: +0.148** on C-2.
  - A fair control keeps each record's own signature and breaks only the body's pairing. It is not built.
- **The adapter's gain depends on readable names.** With opaque names and the task stated, pattern − base is
  nil. The draw's families are names differing in one token, and the adapter learned to read neighbours
  **through their names**: which token differs, and what that implies. An opaque name gives it nothing to read.
- **Names carry more than the task statement.** The stated-task sentence lifts the base's opaque C-2 from 0.05
  (E2) to 0.21, against 0.29 with the target's own names. Most of E2's opaque gap was the missing task, and
  about 0.08 remains that the names carry beyond it.

**What E3 selects.** In context, pattern is where the gain is, and training sharpens the reading of named
neighbours rather than installing skill. That is E4's route: the graph serves the named neighbours. **The
3,000-step pair is not run.** At the measured rate it would cost about $36 alone, outside the ceiling, and the
corpus needs a token-true cap first. That, a fair control, and whether to continue E3 at all are Max's
(D-10, §9).

### E4 — the teacher and the student: rebuild a file (M-a or M-b, K-1, L1 then L3)

- **Question:** given the graph's skeleton, does a teacher's spec (C-5) let a small student
  rebuild a whole file? How much of the lift is the teacher's words, and how much the
  graph's facts?
- **Shape:** Hobbes derives the units (the file's functions, leaves first). The parser, an
  open model shown `API.md` and the skeleton, fills the task format's free fields for each
  unit (§5.2). The student writes the bodies in order, each graded before the next.
  `hobbes gate` checks the file at the end.
- **Arms:** student alone on the graph-filled task format; student with the parser's fields;
  a larger open model writes the bodies (the ceiling); student with the parser's fields, on
  the shadow. A frontier model as parser is one extra arm, run only to price what the open
  parser loses.
- **P12:** this one **decomposes**: planner-defined units, one single-use agent per unit,
  each window smaller than the file. It is the first experiment on this page that is a
  Hobbes test.
- **Cost:** open-model inference for the parser and the student (Modal), plus the one
  frontier-parser arm if cleared.
  L1 first (≈ 31 units). **Ceiling proposed $15** for L1.

#### E4's design (2026-09-26; no spend; D-5 a, written beside E3's draw)

E1's firm result is **pattern in context** (C-2 − C-4, p 0.0015). In E4, the graph serves that pattern
and the facts to a small student, one unit at a time, so E4 needs no training pool. It is the first run on
this page that decomposes (P12), and so the first that is a Hobbes test. These facts were read from the
tree on 2026-09-26:
- E1 records `p12 = arm=model+prompt`.
- `holes.punch` takes one lattice cell, so a helper (a `static inline` such as `hsum256_ps`) or the init
  function is not a cell and cannot be punched yet.
- `hobbes gate` grounds a file by `tail.language_of`, which names C, so a C file is gated as any
  grounded file is.
- **Which shot E1's passes leaned on.** Of Qwen's 18 C-2 greedy passes on bodies, the answer is nearest
  (token distance) the **type-axis** shot in 12, the ISA shot in 5 and the metric shot in 1. By gold
  distance alone, the three axes are about even over all 63 bodies (ISA 21, type 22, metric 20;
  `~/.hobbes/bench/calvin-lattice/e4/shot_axis.py`). At L1 the type and
  metric neighbours are inside the held-out file, so they are holes.

Routes (recommended first):

- **E4-a — the rung and the file.** **Recommended:** L1 on **`distance-avx2.c`**, then the other two native
  files once the first is priced and read. E1's avx2 row sits between the others (C-2 0.24), and avx2 has
  both neighbours native (sse2 and avx512), so every held-out cell has two ISA-axis shots from the files
  that stay. **b:** all three native files in one run. That triples the first unit for nothing learned
  sooner.
- **E4-b — the units and their order.** **Recommended:**
  - Every definition in the held-out file is a unit: the lattice cells, the non-cell helpers and
    `init_distance_functions_avx2`.
  - They are ordered leaves first by the graph's own call edges in the file (`graph.json`, the target's
    ingest). A cycle, if any, is one unit, and the record names it.
  - The file's includes, macros, types and every signature stay. That is the **skeleton**, the "graph's
    skeleton" the card names. **In every prompt, every other unit of the file reads as a prototype**, as
    C-0's `prelude_bare` does, whatever has been filled for grading. A body reaches a prompt only as an
    arm's shot.
  - One fresh call per unit, a single-use agent, whose window holds that unit's context only. The run
    records `p12 = decomposed` with the unit count and the largest window against the file's size, so
    ADR-086's check can hold it.
- **E4-c — what a unit carries.** **Recommended:** four arms, one variable apart:
  - **S-0:** the skeleton down to the hole, and the signature. This is E1's C-0 at L1.
  - **S-2:** S-0 plus the **graph-served shots**: the same `(type, metric)` cell in the files that stay
    (sse2, avx512), chosen by the lattice's rule, not a model. The within-file neighbours are holes at
    L1, so this is E1's C-2 on the ISA axis only. **Expected, from the fact above:** below E1's C-2,
    since the type-axis shot carried most of E1's passes.
  - **S-2o** (described, not registered): S-2 plus type- and metric-axis shots taken from the student's
    **own bodies that passed** in earlier units of the file, and never from gold. It asks whether a
    student can grow a file from its own verified work, which is the file-scale form of E1's result. The
    unit order puts each metric's first type early, so later units have an own shot to use; the order is
    fixed before the run.
  - **S-3:** S-2 plus the ledger's facts (C-1's: the callees with signatures, and the callers).
  - **S-5:** S-3 plus the **parser's fields** (§5.2: `contract`, `edge_cases`; `like` is already the
    lattice's). An open model fills them once per unit, from `API.md` and the unit's task record, and
    never sees a gold body.

  **b:** add a scalar-reference arm, the `distance-cpu.c` body of the same `(type, metric)` in the
  prompt. It is the most direct statement of the task (E2's opaque finding), and it is in the tree a
  developer has. It is held for a second run, because it also carries the metric's arithmetic, and the
  first run should say what the graph and the parser add without it.
- **E4-d — a failed unit.** **Recommended:**
  - Each unit is graded (L0's graders) before the next.
  - A unit that fails is **replaced by its gold in the file that is compiled** for the units after it,
    so each unit's result is its own and a failure does not cascade. That is the per-unit reading. The
    gold never enters a prompt (E4-b), and the shots S-2o takes are the student's passes only.
  - The **file-level** figure is read only over the units that passed on the student's own bodies: how
    many of the file's units the student wrote, and whether G-reg and `hobbes gate` pass on the file with
    every passing unit the student's.
  - **b:** a cascade arm, where the student's failed bodies stay. It answers "can it rebuild the file",
    and is held until the per-unit reading says it is near.
- **E4-e — the models.** **Recommended:**
  - **Student:** Qwen2.5-Coder-7B, E1's, at E1's params, greedy plus k = 10 (E3's revised floor).
  - **Parser:** an open instruct model at 7B (D-2: a parser into the task format, not an author), one
    greedy call per unit, cached, so every arm reads the same fields.
  - **Ceiling:** a larger open coder (Qwen2.5-Coder-32B) on S-3, the one arm that prices model size.
  - **The frontier-parser arm** is run only if Max clears it (D-2), to price what the open parser loses.
- **E4-f — the registered comparisons.** Each is paired by unit, with the sampled pass rate as the primary
  figure and the sign-flip test:
  - **S-2 − S-0:** the graph's ISA-axis shots at L1;
  - **S-5 − S-3:** the parser's words.

  The rest are described. The readings, written now:
  - S-2 holds E1's gap at L1: the graph can serve pattern to a student at file scale;
  - S-5 adds beyond S-3: the parser's words carry what the ledger does not;
  - S-5 does not add: the ledger is the spec, and the parser is overhead;
  - S-2 does not hold at L1: ISA-axis shots alone do not carry the effect, as E1's passes suggest (12 of
    18 nearest the type shot). S-2o then says whether the student's own passes can stand in for the
    type-axis shots.
- **E4-g — the shadow.** **Recommended:** the **descriptive** shadow on S-5 only, as a second run. The
  opaque shadow removes the task statement (E2), so it waits for E3's stated-task arm to say what it
  reads.
- **E4-h — the price and the ceiling.** From E1's calls: Qwen's round 0 over five arms and 93 cells cost
  $0.38 at k = 5. L1 on avx2 is about 31 cell units plus helpers and init, five arms (S-2o included),
  k = 10, with no iterate rounds. The parser is one call per unit. The 32B arm is the largest line. **Estimate ≈ $3 to $5
  for avx2's file; recommended ceiling $8**, with the first call priced against the estimate before the
  rest is sent.

**The unit that builds it** (one dispatch, no spend):
- `lattice e4 plan|run|report`: L1's hold-out over every definition in a file, extending `holes` beyond
  cells, with the round-trip property held for the whole file;
- the leaves-first order from `graph.json`;
- the five arms' prompts, the bare skeleton in each, and S-2o's own-pass shots;
- the parser's fields, cached;
- gold substitution between units;
- the file-level G-reg and `hobbes gate`;
- `p12 = decomposed` with the window record.

It is tested on the fixture's trimmed avx2 file. The tests include a planted wrong unit shown not to
cascade, and a gold-substituted unit shown to be absent from every later prompt. The
parser's model and the ceiling arm's are the run's parameters, not the unit's.

#### E4's record — L1 on all three native files (2026-09-26; D-6 and D-10, ceiling $8; spent ≈ $1.25)

**What ran.**
- The runner was built in sessions `5724` and `1e40`.
- Per file: the parser's fields (`Qwen/Qwen2.5-7B-Instruct`, one greedy call per unit, all 127 parsed), then the
  student `Qwen/Qwen2.5-Coder-7B-Instruct` on five arms at k = 10, S-2o in four waves, and one file-level build
  per arm.
- **P12: decomposed.** Units are planner-defined (every definition, leaves first), with one single-use call
  each, and the largest window was 13,412 characters against the smallest file's 42,228. **This is the first
  run on this page that is a Hobbes test.**
- Each file cost $0.39 to $0.43.
- Records are in `~/.hobbes/bench/calvin-lattice/e4/` (`run-{avx2,sse2,avx512}/`, `report*.txt`, `run-isa.sh`).
- **Not run:** the 32B ceiling arm (E4-e) and the cascade arm (E4-d b).

**The registered comparisons, paired by unit, exact:**

| file (units) | S-2 − S-0 sampled | S-2 − S-0 greedy | S-5 − S-3 sampled | S-5 − S-3 greedy |
|---|---|---|---|---|
| avx2 (45) | **+0.258, p < 0.0001** | +0.289 (14 / 1), p 0.001 | **−0.173, p 0.0006** | −0.200 (1 / 10), p 0.012 |
| sse2 (38) | **+0.263, p 0.0003** | +0.316 (12 / 0), p 0.0005 | **−0.158, p 0.019** | −0.158 (2 / 8), p 0.11 |
| avx512 (44) | **+0.211, p 0.0003** | +0.227 (12 / 2), p 0.013 | **−0.073, p 0.010** | −0.023, p 1.0 |

**Cells, greedy pass@1, S-0 → S-2:** avx2 0.19 → 0.58, sse2 0.03 → 0.42, avx512 0.23 → 0.52.

**Helpers barely move:** 0.00 to 0.23 in every arm, and none carries a shot.

**File level:** each arm's rebuilt file (the student's passing bodies, gold elsewhere) passes G-diff and G-reg.
With S-2 the student writes 21 of 45, 13 of 38 and 17 of 44 definitions, against S-0's 8, 1 and 7.

**The readings, against the ones written before the run:**
- **"S-2 holds E1's gap at L1" holds, and above my expectation.**
  - I wrote that S-2 would fall below E1's C-2 (0.29), since 12 of E1's 18 passes leaned on a type-axis shot and
    L1 holds those out.
  - It rose to 0.42–0.58 instead. At L1 every cell carries **two** ISA-axis shots of its own `(type, metric)`
    (both other native files), where E1 carried one per axis.
  - The graph can serve pattern to a student at file scale.
- **"S-5 does not add" is worse than that: the parser's fields hurt, on every file.**
  - A 7B parser's contract ("using the dot_epi8, hsum256_epi32_signed, and sqrt functions"; edge cases such as
    "vectors of different lengths") misleads beside the ledger's facts.
  - D-2's parser, at this size, is overhead at best.
- **S-2o adds nothing measurable.** Own-pass shots reached 10 of 31 cells per file (27 axes later in the order,
  18 to 20 neighbours failed). Where they did, S-2 had already carried the pattern.
- **The file's weak point is its helpers.** At 13, 6 and 12 per file they pass at 0 to 0.23 with no shot. Their
  ISA siblings exist by name (`hsum128_ps`, `hsum256_ps`, `hsum512_ps`), which is exactly the name-token family
  E3 found training reads.

**What E4 selects** (for Max, D-11, §9): the in-context route works at file scale with the graph's own shots.
The next measured step is **helper shots by name family**, and then a model-size price (the 32B arm). The
parser, as D-2 cast it, is set aside at 7B.

#### D-11's record — helper shots by name family, and the 32B (2026-09-27; ceiling $5, spent ≈ $2.11)

**What ran.**
- **The rule, corrected before the build.** E3's rule as worded reaches 3 of 31 helpers. **W, the width
  family**, reaches 26 of 31, in 11 families, 0 ambiguous; its bodies were read as 11 of 11 the same
  operation (D-11 in §9).
- **The runner:** session `e735` (117 turns, $21.99 on the subscription). It adds:
  - **S-2h**, which is S-2 plus W's shots for a helper, and byte-identical to S-2 for every cell and the init
    (checked on the real avx2 plan);
  - `e4 compare` and `e4 pool`;
  - the 32B pin (A100-80GB).
- **Pre-registered** before any call: `~/.hobbes/bench/calvin-lattice/d11/PREREG.md`.
- **7B** (`Qwen2.5-Coder-7B`), S-2 and S-2h on all three native files, k = 10: $0.365.
- **32B** (`Qwen2.5-Coder-32B`), S-2h on the same plans: $1.74.
  - The first call cost $0.53, against a worst-case estimate of $2.33. That estimate assumes every answer runs
    to `max_tokens`; the pricing table now holds the measured throughput.
  - avx512's first call was cut by a network loss 4 minutes in. It was charged ($0.18, an upper bound) and
    returned nothing. The run resumed in place.
- Records: `~/.hobbes/bench/calvin-lattice/d11/` (`run-{7b,32b}-<isa>/`, `report-*.txt`, `compare-*.txt`,
  `pool-7b-*.txt`, `probe.py`, `run-isa.sh`).

**The registered comparison: S-2h − S-2 on the helper units**, paired by unit, exact.

| file (helpers) | sampled S-2 → S-2h | Δ sampled | greedy |
|---|---|---|---|
| avx2 (13) | 0.08 → 0.48 | **+0.408, p 0.002** | +0.308 (5 / 1), p 0.22 |
| sse2 (6) | 0.08 → 0.08 | +0.000, p 1.0 | +0.000 |
| avx512 (12) | 0.00 → 0.23 | +0.233, p 0.125 | +0.250 (3 / 0), p 0.25 |
| **pooled (31)** | | **+0.261, p 0.0001** | **+0.226 (8 / 1), p 0.039**; pass@k +0.290, p 0.004 |

- **The noise read** (cells, identical prompts under two seeds, described): +0.010 sampled pooled, p 0.46.
  The arm is one variable apart.
- **File level:** with S-2h the student writes 25, 13 and 20 definitions, against S-2's 20, 13 and 17. G-diff and
  G-reg pass on every rebuilt file.

**Where helpers do not move, the shot crosses an ISA's capability.** On sse2 and in avx512's unmoved helpers,
the dominant class is `invented`:
- sse2 has no `_mm_shuffle_epi8` (SSSE3), `_mm_cvtepu16_epi32` (SSE4.1) or `_mm_hadd_pd` (SSE3), and the
  student copies the wider sibling's shape;
- it also copies the sibling file's own names. avx512's `sqdiff_epu8_512` calls avx2's `abs_diff_epu8`, and
  `popcount_avx512` reads avx2's `popcount_lut_bytes`.

A name-family shot carries the pattern; it does not carry what the target ISA has.

**The 32B on S-2h, paired by unit with the 7B's S-2h** (described: a price, not a registered test).

| file | cells, sampled 7B → 32B | helpers, sampled 7B → 32B | init | definitions written (7B → 32B) |
|---|---|---|---|---|
| avx2 | 0.49 → 0.59 | 0.48 → 0.79 | 0.20 → 1.00 | 25 → 29 of 45 |
| sse2 | 0.39 → 0.59 | 0.08 → 0.40 | 0.30 → 1.00 | 13 → 23 of 38 |
| avx512 | 0.46 → 0.55 | 0.23 → 0.53 | 0.70 → 1.00 | 20 → 26 of 44 |
| **pooled** | **+0.129, p < 0.0001** (greedy +0.097, 16 / 7, p 0.09) | **+0.303, p < 0.0001** (greedy +0.290, 11 / 2, p 0.022) | | |

The 32B invents less but not nothing. On sse2 its invented share is 0.38 of cell samples (7B 0.48) and 0.44
of helper samples (7B 0.73).

**The readings, against the ones written before the run:**
- **"Helper shots carry the pattern to helpers" holds** pooled (p 0.0001), and on avx2 alone. It does not
  hold on sse2, where every sibling is a wider ISA. The pre-registration also said the unpaired helpers "are
  S-2's prompt". They are not byte for byte: their note names each file's reason. No shot differs.
- **"The cells are unchanged" holds** (p 0.46), so the run stands.
- **"32B above the 7B by a clear margin" holds.** Size adds about as much at L1 as the graph's ISA-axis shots
  did over S-0 (E4: +0.21 to +0.26). At ≈ $0.58 a file, the 32B is cheap enough to be a student.

**What D-11 selects** (for Max, D-12, §9): the helpers' remaining loss is **facts**, not pattern. The next
measured step is the ISA's own intrinsics served to a unit, then the 32B as the student for the rung above.

#### D-12's record — the ISA's facts beside the shots (2026-09-27; spent ≈ $0.67)

**What ran.**
- **Step 0** (no spend, `~/.hobbes/bench/calvin-lattice/d12/`) split D-11's 492 invented intrinsics:
  - 56% are a width-rename of an intrinsic in the unit's shots;
  - 34% are declared nowhere;
  - 9% are real but not available in the file.
- "Available" was read the way the grader meets it: the file's own includes, preprocessed in the image under
  its flags, with every required feature on. sse2's file includes only `<emmintrin.h>`.
- **The runner:** session `7e20`, 141 of 140 turns, so the harness committed its work. It adds
  `lattice available` and **S-3h**, which is S-2h plus a block listing each intrinsic and sibling-file name the
  unit's shots use. The block says whether this file has the name, and gives its form here by rule R or rule W.
- **Review fixes:** my review found two defects in the availability parse, both toward false advice.
  - clang's three-line head was missed, so `_mm512_max_epi32` read "not available".
  - Its features were read from one line only, so a split head read as available everywhere.

  Both were fixed with a real-source test. The rebuilt record then disagrees with the step-0 probe only where
  the probe was wrong.
- **On the real plans**, all 127 S-3h units are exactly S-2h plus the block, and the block's counts equal the
  pre-registration's.
- **7B**, S-2h and S-3h on the three native files, k = 10.
  - A second network cut lost sse2's first call. It was charged up to $0.27 (from its wall time) and the run
    resumed in place.
  - Records: `d12/run-7b-<isa>/`, `report-*`, `pool-7b*.txt`, `classes.py`.

**The registered comparison: S-3h − S-2h over every unit**, paired by unit, pooled.

| file (units) | Δ sampled | greedy |
|---|---|---|
| avx2 (45) | −0.007, p 0.91 | +0.000 (4 / 4) |
| sse2 (38) | +0.016, p 0.66 | +0.026 (3 / 2) |
| avx512 (44) | +0.025, p 0.46 | +0.000 (2 / 2) |
| **pooled (127)** | **+0.011, p 0.59** | +0.008 (9 / 8), p 1.0 |

Described, pooled:
- cells −0.018 (p 0.33);
- helpers +0.042 (p 0.41; pass@k +0.129, p 0.22);
- **the init passes 1.00 greedy on all three files** under S-3h, against 0.20, 0.30 and 0.70 sampled under
  S-2h.

**Why nothing moved: the student does not use the block.** On sse2, 132 of S-3h's 194 invented intrinsics
(113 of 194 under S-2h) are exactly the same-width rename of a name the block had said has **no form here**:
- `_mm_cmp_pd` from `_mm256_cmp_pd`;
- `_mm_blendv_pd`;
- `_mm_cvtepu16_epi32`.

The student renames the shot's intrinsic itself, as it did without the block, and writes the name the block
ruled out. Only 39 of 444 invented names on sse2 were the flagged names themselves. avx512's invented
intrinsics are all declared nowhere (`_mm512_castps512_pd256`, `_mm512_extracti32x4_si512`), which no fact
about the shots can reach.

The one thing the block moved is the init. Its shots call the other files' kernels, and the block maps each
one to this file's name. **A name mapping was used; a negative ("no form here") was not.**

**The readings, against the ones written before the run:**
- **"Nothing moves" holds**, as its reading was written: a 7B does not use a facts list beside shots.
- The negatives are read and not acted on, and the positive name mappings are acted on (the init). That
  matches E4's S-5, where a parser's fields hurt.
- "The facts carry" and "inventions fall, passes do not" do not hold. Inventions did not fall.
- "sse2 moves least" is moot, since no file moved.

**What D-12 selects** (for Max, D-13, §9): the facts belong **in the loop, not the prompt**. The compiler's own
`undeclared` answer, with the block's line for that name, goes back to the student once (K-3's lightest form;
E1's runner already has the iterate loop that E4 runs at zero rounds). Or the same block on the 32B, which may
read what the 7B does not.

#### D-13's record — the facts in the loop (2026-09-27; ceiling $1.50, spent ≈ $0.32)

**What ran.**
- **Pre-registered** before the build: `~/.hobbes/bench/calvin-lattice/d13/PREREG.md`, with step 0's probe
  (`probe.py`).
- **The runner:** session `b6dd` (165 of 180 turns, $26.94 on the subscription), merged with one docstring fix.
  It adds `lattice e4 loop`, which copies a finished run's S-3h round 0 as two arms, and E1's loop lent to E4
  through four hooks that leave E1 byte for byte.
  - **S-3hd** is retried with E1's own feedback.
  - **S-3hf** gets the same text plus one line per named name.
  - Both share round 1's seed, and an identical request is sent once.
- **Checked on the real rows before any call.** Round 0 is copied exactly (0 mismatches). S-3hd's retries are
  E1's byte for byte. The retried and lined counts and the line statuses equal step 0's, and 959 requests are
  sent, the pre-registration's figure.
- **7B**, one retry round from D-12's S-3h round 0 on the three native files:
  - costs: avx2 $0.094 (worst-case estimate $0.225), sse2 $0.095, avx512 $0.135;
  - retried: 157, 202 and 215 chains per arm;
  - S-3hf carried lines on 64, 172 and 149 of them;
  - the rest were one shared request, a tie by construction.
- Records: `d13/run-7b-<isa>/`, `report-7b-*.txt`, `pool-7b-*.txt`, `classes-round1.txt`.

**The registered comparisons**, paired by unit, pooled over 127 units:

| comparison | Δ sampled | greedy | pass@k |
|---|---|---|---|
| **S-3hf − S-3hd through round 1** (the facts in the loop) | **−0.001, p 1.0** | −0.008 (0 / 1) | −0.008 (1 / 2) |
| **S-3hf, round 1 − round 0** (D-13 as worded; cannot be negative) | **+0.021, p 0.0002** | +0.008 (1 / 0) | +0.047, p 0.031 |
| S-3hd, round 1 − round 0 (described) | +0.022, p 0.0001 | +0.016 (2 / 0) | +0.055, p 0.016 |

Per file, S-3hf − S-3hd sampled is −0.009 on avx2, +0.005 on sse2 and +0.002 on avx512. It is −0.004 on
cells, +0.010 on helpers and 0 on the init.

**What the lined chains wrote at round 1:**
- On sse2, 127 of 172 S-3hf retries are `invented` again, against 134 of 172 for S-3hd. On avx512 it is 110 and
  112 of 149.
- The lines lower **the ruled-out reuse**, the round-1 rows that write a name the lines had called not
  available or declared by no header: 131 rows pooled, against S-3hd's 161 over the same chains.
- The student drops the name it was told about and invents another.
- Chains rescued by the round: S-3hd 30, S-3hf 28.

**The readings, against the ones written before the run:**
- **"A retry, not the facts" holds.** One round of the grader's own words buys +0.02 (p ≤ 0.0002 in both arms).
  The lines add nothing to it.
- "The facts carry in the loop" and "only the mappings carry" do not hold. The other-file lines (113) moved
  nothing measurable.
- "Nothing moves" does not hold, since the retry itself moves.
- "The ruled-out reuse stays high" holds in part: it falls by about a fifth, and the invented class does not
  fall with it.

**What D-13 selects** (for Max, D-14, §9): **negatives do not steer the 7B**, in the prompt (D-12) or beside the
error (D-13). Of the 477 intrinsic lines D-13 could serve, 476 were negatives. The only facts the 7B has acted
on are positive name mappings: the init's, in D-12. The untested fact is a **positive** for an intrinsic: what
this file does have for the operation the student reached for. Whether such a rule exists, and how often it
names what the gold uses, can be measured with no spend.

#### D-14's probe — a positive fact (2026-09-27; no spend)

Pre-registered before it ran: `~/.hobbes/bench/calvin-lattice/d14/PREREG.md`. The probe and its output are
`probe.py` and `probe-out.txt`.
- **Occurrences:** 387 distinct (ISA, unit, name) where a 7B row invented an intrinsic-shaped name (1,688
  rows), over D-12's S-2h and S-3h round 0 and D-13's two round-1 arms.
- **Rule S** looks among this file's available intrinsics: its own prefix, the same type, and an op that
  extends or is extended by the invented op. It answers with 1 to 5 names.

| rule | answers | the gold's, where it answers | reach |
|---|---|---|---|
| **S (registered)** | **49 of 387 (12.7%)**; none 329, too-many 7, no op 2 | **2 of 49 (4.1%)** | **not reached** (30% and 50% needed) |
| S-any, any type (described) | 175 of 387 (45.2%) | 21 of 175 (12.0%) | — |

- **Not reached, so no arm was built and nothing was spent.**
- **What the unanswered names are.** Of the 331 S could not answer, 257 are sand, declared by no header of
  clang 18. 74 are real intrinsics of another ISA or feature, such as `_mm_shuffle_epi8` and `_mm_blendv_pd`
  on sse2. There the gold composes the operation from other intrinsics (`popcount_sse2`: shifts, `and`, `sub`;
  `blendv`: `and` with `cmpeq`). **No name-to-name rule reaches a composition, and no fact about names reaches
  sand.**
- **Described, the one narrow exception:** in 5 of S's 7 `too-many` occurrences the gold's intrinsic is in the
  list. This is sse2's `_mm_cmp_pd`/`_mm_cmp_ps` → `_mm_cmpeq_*` family, 1.8% of the names but 130 of the
  1,688 rows. It is recorded, not acted on: the rule as registered capped at 5.

**What D-14 selects** (for Max, D-15, §9): **at the 7B, a fact about names does not remove invented
intrinsics**, whether as a negative (D-12, D-13) or as a positive (D-14, which does not reach). Two thirds of
the invented names are sand, and the rest mostly need a composition. The remaining lever E4 has priced is
model size: the 32B invents less (D-11: 0.38 against 0.48 of sse2's cell samples) and has not been shown the
facts.

### E5 — the pattern world: the science track (M-c)

- **Question:** Atlas-0's method on a synthetic lattice. Functions generated along named axes
  in a toy C-like language, a small block trained on part of the lattice and asked for the
  rest. Does it re-instantiate a shape along an axis it has seen, and by what circuit? Does
  it invent names for cells that do not exist (sand)?
- **Why it is here:** it is the only experiment that can say *why* pattern works when it does.
  It is also where Atlas-0's held B4-given block has a natural next world.
- **Cost:** Atlas-0's scale, ≈ $10–25. Parallel to E1–E4, not in their path.

### E6 — the compiler as teacher (K-3) — parked

RL on G-compile, G-diff and G-graph as reward. It is the most deterministic teacher there
is, and the most expensive. It waits on E3.

### E7 — "make sqlite-vector" (L4) — parked, the far end

The repo from `API.md` alone, with the pair (a teacher, a student, the ledger of a target that
does not exist yet) graded on everything. It is named so the ladder has a top. It is not
designed until L3 has a reading.

---

## 7. The proposed order, and why

Max asked for a direction. This is it: **E0 → E1 (with E2's shadow as an arm) → decide.**

1. **E0 first, because every earlier round lost its first run to its own instrument.** It
   spends nothing, and it produces the one artifact the rest need: a lattice of 93 holes
   with a deterministic grade on each.
2. **E1 next, because it answers Max's pattern point directly and cheaply.** Before anything
   is trained, it says whether pattern in context beats volume in context, whether facts
   remove invented intrinsics, and which axis of the lattice is cheap to cross. It costs a few
   dollars, and every later branch reads from it.
3. **Then the branch E1 selects:**
   - pattern does work in context, and the shadow keeps it → **E3** (train it in, then test
     whether it transfers);
   - facts do the work, pattern does not → **E4** (the teacher and the graph carry a student;
     the charter's pair);
   - neither moves a model that already writes C → the question is the base, not the
     context: M-d or a different base, before any training;
   - the shadow collapses the scores → memory, not skill. Report it and re-run E1 on the
     post-cutoff code only.
4. **E5 runs beside the others if Max wants the science track.** It shares nothing with
   E1–E4 except the lattice's shape.

---

## 8. Rules that bind every experiment here

- **Repo code executes in the image** (ADR-092, C-64): every build, test and differential.
- **Facts are never trained in** (§3). A training corpus contains no sqlite-vector code, and
  G-mem checks that before and after. The adapters train on patterns from other repos.
- **No dispatched session is training data** (ADR-107). The session records under
  `docs/calvin/sessions/` and the dispatch identity's commits are never rendered into a
  corpus. `units_from_git` already refuses them; E3's miner must refuse them too, and it
  gets a test for that.
- **Spend is held** until Max names the run and its ceiling. The first unit is priced
  against the estimate before the rest runs.
- **Readings are written before the run**, and each is attributed (§1) before it is read.
- **Every number carries its G-mem reading beside it**, as every precision carries its
  strict figure.
- **The model's results are the pair's and the target's** (charter §7). Nothing here is a
  claim about C in general until E2's shadow and a second target agree.

---

## 9. Decisions for Max

Proposed routes, the recommended one first.

- **D-1 — is this Calvin?** **Taken: a** (Max, 2026-09-24). The charter amendment is
  written with ADR-151.
  - **a (recommended):** yes, under §3's reading: skill in the weights, facts in the ledger.
    The charter stands. §3 is added to it as an amendment on acceptance, and I7 (smaller as
    Hobbes grows) still applies: every fact the model reaches for is a fact the graph should
    serve.
  - b: a new name for a writer model, leaving Calvin as the grounder.
  - c: allow repo memory in the weights. Not recommended: ADR-099 §9b measured knowledge in
    weights overriding live context, and a SHA change would make the model wrong silently.
- **D-2 — the teacher.** **Taken, amended (Max, 2026-09-24):** *"we could look to use an
  open model for inference. the goal there though is less general model. we could even have
  where the general model more parses the message into a task format more than does anything
  large."* The teacher is an open model at inference too, and its role is a parser into the
  task format (§5.2), not an author. Training data (K-2), if it ever comes, is from an
  open-weights model. A frontier model appears only as a priced comparison arm.
  - (was a: Claude at inference only; b: check the terms first.)
- **D-3 — the first spend.** **Taken: a** (Max, 2026-09-24), behind the literature pass
  (Max: *"before any spend … worth looking to other literature"*).
  - **a (recommended):** E0 now, no spend. E1 on both 7Bs at a $10 ceiling, first unit priced.
  - b: E0 only, and decide E1 after its self-test.
  - c: E0, E1 and E5 together (the science track in parallel), with $10 + $25 ceilings.
- **D-4 — the NEON and RVV arms.** **Taken: leave them** (Max, 2026-09-24). Add qemu-user to the image now (+ some size to a 3.3 GB
  image), or leave them until L1 needs a sixth file? **Recommended: leave them**, since the
  three native ISAs give 93 cells.

- **D-5 — E3's pool, and E4 beside it** (2026-09-26, after E3's revised card). **Taken: a** (Max,
  2026-09-26: "good to proceed with recommended"). The draw rule was written before the draw:
  `~/.hobbes/bench/calvin-lattice/e3/draw/DRAW-RULE.md`, sha256 `f4b6e2abf25b2035…`. It is a census of the
  permissively licensed C repos GitHub's search returns for seven SIMD keywords, gated on an ISA lattice
  (≥ 3 families, ≥ 8 members) and a contained ingest, capped at 40. Its pre-registered bars for the
  body-shape rule are recall ≥ 0.90 on the ISA families and coincidence ≤ 20% on a read sample.
  - **a (recommended):** E3's first step is a no-spend draw of permissively licensed C repos with kernel
    lattices, by a written rule, with the body-shape rule tested on it. **E4's design** (the graph serves the
    shots and the facts to a student, P12) is written in parallel: E1's firm result is pattern in context,
    which is E4's shape, and E4 needs no training pool.
  - b: E3 only, E4 after it, as §7 orders.
  - c: take ScummVM's GPL-3.0 pool as training data for a bench adapter, never distributed. This is a licence
    call, and its families are unlike the target (no type×ISA shape, 37% near-copies).

- **D-6 — E4's design** (2026-09-26, §6 "E4's design"). **Taken: as recommended** (Max, 2026-09-26: "good to proceed with recommended"). The routes E4-a to E4-h, recommended first:
  - L1 on `distance-avx2.c`;
  - every definition a unit, leaves first, with a bare skeleton in every prompt;
  - S-0, S-2 and S-3, S-2o described and S-5 the parser's;
  - gold substitution in the compiled file only;
  - Qwen 7B student, a 7B open parser, the 32B ceiling arm;
  - S-2 − S-0 and S-5 − S-3 registered;
  - the descriptive shadow second;
  - ≈ $3–5, a ceiling of $8.

  One dispatched unit builds `lattice e4` first, with no spend. For Max: take the routes as recommended,
  or adjust them.

- **D-7 — E3's pool: which count funds E3** (2026-09-26, after the draw). **Taken: a** (Max, 2026-09-26).
  - **a (recommended):** mined real members train without a validation route, since the card's validation is
    for generated siblings. The pool is the **24,222 unique** tasks, deduplicated across repos, with the
    registered body-shape rule's families plus the ISA families. E3 is priced on the steps ablation (300 and
    3,000), and the body-shape rule's failed recall bar is stated beside it: it misses dissimilar ports, which
    the union keeps by name. G-mem and the sqlite-vector exclusion hold as before.
  - b: the registered band as worded. 2,062 validated tasks, E3 at 300 steps only, the pool's size stated as
    the limit.
  - c: widen before pricing. Take the 20 passers not reached and fix the rule's three wording faults first.
    That is a second draw, with no spend.
- **D-8 — the two Hobbes defects the draw found** (extraction; a patch each). **Taken: a** (Max, 2026-09-26).
  - **a (recommended):**
    - **Rust and Java first.** Make `_walk` iterative, so no file's depth ends an ingest. The defect is a
      crash, so it is contained first, with the build.rs shape as a test.
    - **Then C.** A file whose top level is one ERROR node gets a counted `parse-lost` note, surfaced
      through `list_blind_spots`, and a C-n registers the residual. Corrected: the file is already recorded,
      so the change is that record saying the definitions inside were lost, plus a C-n in the C segment.
    - Whether ADR-129's read from the index (C++'s lost definitions) should reach C is measured before an ADR.
  - b: register both and fix neither yet.

- **D-9 — E3's corpus, then its run** (2026-09-26, after D-7). **Taken: a** (Max, 2026-09-26: "good to proceed"). The ceiling is **$25**.
  - **a (recommended):** dispatch the corpus unit now, with no spend, after E4's two runner units, one at a time.
    Then run E3 at a **$25 ceiling**: the 300-step pair first, and the 3,000-step pair only after its reading.
  - b: hold E3 until E4 has run, so the in-context route reads first.

- **D-10 — after E3's 300-step pair** (2026-09-26). **Taken: a** (Max, 2026-09-26: "good to proceed with the recommended"). E4 runs under D-6's $8 ceiling.
  - **a (recommended):** run E4 now (D-6's plan, ceiling $8), since E3 points at the in-context route. Hold E3's
    3,000-step pair. If it is ever run, it needs a token-true length cap and a fair control (the member's own
    signature, only the body's pairing broken), and a new ceiling of about $45.
  - b: fix the control and the cap, and re-run the 300-step pair first, for about $5, before E4.
  - c: close E3 here, as recorded.

- **D-11 — after E4's three files** (2026-09-26). **Taken: a** (Max, 2026-09-26: "proceed with d-11"). The
  ceiling is **$5**: $1.50 for the 7B's S-2 and S-2h, and $3.50 for the 32B arm.
  - **The wording, corrected before the build.** E3's rule as worded (`families.isa_families`) does not pair the
    route's own example. `hsum128`/`hsum256`/`hsum512` differ in a vector width, not an ISA token, so that rule
    reaches only the three `popcount_*` (**3 of 31** helpers). The rule built is **W, the width family**: ISA
    tokens, vector widths (128/256/512), lane counts (`x<N>`) and a trailing digit token are abstracted. It
    reaches **26 of 31** helpers in 11 families, 0 ambiguous. A read of the bodies found all 11 are the same
    operation at another width. W is pre-registered in `~/.hobbes/bench/calvin-lattice/d11/PREREG.md`, with
    `probe.py` and its output. The registered comparison is **S-2h − S-2 on the helper units**, paired by unit,
    per file and pooled.
  - **a (recommended):** give helpers ISA-axis shots by name family. This is E3's rule: names differing in one
    ISA token, `hsum256_ps` ← `hsum128_ps` and `hsum512_ps`. It is a small runner unit with no spend, and then a
    re-run of S-2 on the three files (about $1). Then the 32B ceiling arm on S-2 (about $2–3) prices model size.
  - b: go up the ladder to L2/L3 (`sqlite-vector.c`), which needs an L2 instrument E0 did not build.
  - c: a frontier-model parser, D-2's priced comparison, to learn whether S-5's loss is the parser's size or the
    idea.
  - **Ran** (§6, "D-11's record"; ≈ $2.11 of $5). Pooled S-2h − S-2 on helpers is +0.261 sampled (p 0.0001),
    with sse2 unmoved. The 32B adds +0.129 on cells and +0.303 on helpers over the 7B.

- **D-12 — after D-11** (2026-09-27). **Taken: a** (Max, 2026-09-27: "proceed with the recommended"). Expected
  spend is about $0.40. The runner's worst-case guard needs about $0.80 a file, and avx2 is priced first.
  - **The premise, refined before the build** (`~/.hobbes/bench/calvin-lattice/d12/PREREG.md`). D-11's record
    said the unmoved helpers copy the wider sibling's shape. By class, 56% of D-11's invented intrinsics are a
    width-rename of an intrinsic in the unit's own shots, 34% are declared nowhere, and 9% are real but not
    available in the file.
  - "Available" is read as the grader meets it: declared by the file's own includes, preprocessed in the image
    under the grader's flags, with every required feature on.
  - S-3h states, for each intrinsic and each sibling-file name the unit's shots use, whether this file has it,
    and its form here by a pre-registered rename rule (R) or rule W.
  - **a (recommended): the ISA's facts for every unit.** The intrinsic index
    (`facts/intrinsics-clang18.json`) already says which intrinsics each ISA's headers declare.
    - An arm **S-3h**, S-2h plus a short list: the intrinsics the unit's shots use, each marked available or
      not in the target ISA, and the file's own helper names.
    - It is aimed at the class that stops helpers, `invented`.
    - One no-spend runner unit, then S-2h against S-3h on the 7B over the three files (about $0.5).
  - b: take the 32B as E4's student and build the L2 instrument (`sqlite-vector.c`) for the next rung. It is a
    larger unit, and the ladder's next claim.
  - c: close E4's line here with D-11's record, and write the programme up for Max's read.
  - **Ran** (§6, "D-12's record"; ≈ $0.67). S-3h − S-2h pooled is +0.011 (p 0.59): null. On sse2, 132 of 194
    invented intrinsics are the renames the block said do not exist. The init passes 1.00 on all three files,
    where the block mapped the other files' names.

- **D-13 — after D-12** (2026-09-27). **Taken: a** (Max, 2026-09-27: "proceed with the recommended route").
  Ceiling $1.50; expected about $0.15–0.35.
  - **Refined before the build** (`~/.hobbes/bench/calvin-lattice/d13/PREREG.md`).
    - Round 1 against round 0 on one arm cannot be negative, so it cannot say whether the facts or the retry
      did it. The round is therefore asked two ways, one variable apart, from D-12's own S-3h round 0 (same
      target, grader unchanged, no new round-0 call): **S-3hd**, E1's retry (the grader's feedback), and
      **S-3hf**, the same text plus one line per named name.
    - **Registered:** S-3hf − S-3hd through round 1 (the primary reading), and S-3hf through round 1 against
      its round 0 (D-13 as worded).
    - The two arms share round 1's seed, so a chain with no fact line is one request and an exact tie.
  - **Step 0 changed the expectation, not the route.** Of 477 intrinsic lines over D-12's retried chains, one
    has a form here; the rest are negatives, and on sse2 the diagnostic already says `undeclared`. The
    positive lines are the other file's own names mapped by rule W (113), the kind the init used in D-12.
  - **a (recommended): the facts in the loop.**
    - E4 with **one iterate round**. A unit that fails `invented` or `compile` is asked again, once, with the
      grader's own diagnostic plus the block's line for each invented name (its form here, or that it has
      none).
    - This is K-3's lightest form, and E1's runner already holds the loop, which E4 runs at `rounds=0`.
    - Registered: round 1 against round 0 on S-3h, pooled.
    - One no-spend runner unit, then about $0.3 to $0.5 on the 7B.
  - b: S-3h on the 32B, which asks whether a larger student reads the negatives the 7B does not. About $1.7.
  - c: close E4's line with D-11 and D-12's records.
  - **Ran** (§6, "D-13's record"; ≈ $0.32 of $1.50). S-3hf − S-3hd through round 1 is −0.001 pooled (p 1.0):
    null. The retry alone buys +0.02 (p ≤ 0.0002 in each arm). The lines lower the reuse of a ruled-out name by
    about a fifth, and the student invents another.

- **D-14 — after D-13** (2026-09-27). **Taken: a** (Max, 2026-09-27: "good to proceed with the recommended").
  The probe, its rules and its reach are pre-registered in `~/.hobbes/bench/calvin-lattice/d14/PREREG.md`:
  rule S (the same type, an op that extends or is extended by the invented one, 1 to 5 names); reach is
  30% answered and 50% of those the gold's. An arm is built only if it reaches.
  - **a (recommended): a positive fact, probed first, no spend.** Every intrinsic line D-12 and D-13 served was
    a negative (476 of 477 in D-13), and the only facts the 7B has used are positive name mappings (the init).
    - A probe over D-12 and D-13's invented intrinsics asks whether a written rule names an **available**
      intrinsic for the same operation. Two candidates: the same operation stem at this file's width, such as
      `_mm_cmp_pd` → `_mm_cmpgt_pd` …, or the intrinsic the gold calls at the unit's matching site.
    - It asks how often the named intrinsic is the one the gold uses.
    - Only if it reaches: an arm, S-3hp, in the loop or the prompt, about $0.3.
  - b: S-3h on the 32B, D-13's b. It asks whether a larger student reads the negatives the 7B does not. About $1.7.
  - c: close E4's line with D-11 to D-13's records, and write the programme up for Max.
  - **Probed** (§6, "D-14's probe"; no spend). Rule S answers 12.7% of 387 invented names, and 4.1% of those
    answers are the gold's: **not reached**, so no arm and no spend. 257 of the 331 unanswered names are sand,
    and the rest need a composition.

- **D-15 — after D-14** (2026-09-27). **Taken: a** (Max, 2026-09-27: "good to proceed with recommended"); ceiling
  $3 on actual spend (`~/.hobbes/bench/calvin-lattice/d15/PREREG.md`).
  - **The route's price, corrected before any call.** "About $1.7 for round 0" was D-11's figure for **one**
    arm, so a fresh S-2h and S-3h would be about $3.5. S-2h is D-11's own 32B answers, reused instead: all 1,397
    S-2h requests are byte-identical to D-11's, seed included, and the runner answers a held completion without
    sending it. Only S-3h is sent at round 0.
  - **a (recommended): S-3h on the 32B, with the loop.** The 32B invents less and has not seen the facts.
    - Run S-2h and S-3h at round 0, then S-3hd and S-3hf at one round from S-3h, on the three native files
      (`e4 plan --available`, then `e4 loop`; the runner exists, so there is no unit to build).
    - It asks whether a larger student reads the negatives the 7B does not, beside the shots or beside the error.
    - About $1.7 for round 0 (D-11's 32B figure) plus about $0.5 for the round; ceiling $3.
  - b: close E4's line and write the programme up for Max: pattern carries at the 7B (E1, E4, D-11), facts
    about names do not (D-12 to D-14), and size is priced (D-11).
  - c: the narrow comparison-family positive (the 5 of 7 `too-many` lists that held the gold's), about 1.8% of
    the invented names. Not recommended, because it is too narrow to move a pooled figure.

---

## 10. What this cannot mean

Nothing on this page, run as proposed, shows that a model "can program in C". E1–E3 are
about one lattice in one repo, graded by one scalar reference. E2's shadow removes the
target's names, not its shapes, which the base may still have read. A pass on L0 is one
function written with its neighbours present. The ladder exists so that each rung's claim
is exactly as wide as the rung, and a second target (cJSON, the other graded C cell, or a
new random draw) is what widens it.

---

## 11. Record

- **2026-09-24** — proposed (sixteenth session, no spend). The lattice's shape was read from
  the bench clone at `0c2223a`: 31 names per ISA file, `init_distance_functions_<isa>`
  filling `dispatch_distance_table`, the scalar reference in `distance-cpu.c`, and AVX2 and
  AVX-512 on the host's CPU. Waiting on D-1 to D-4.
- **2026-09-24** (later) — Max took the recommended routes, with D-2 amended: an open model
  at inference, the general model a parser into a task format. He asked for a literature
  pass before any spend (§12).
- **2026-09-24** (later) — the literature pass (§12). The pieces are each precedented, and the
  combination is not (§12.6). Two findings changed the design (§12.7): Li et al. lean
  against pattern shots on similar problems, which makes E1's central reading a real
  question rather than an expectation; and renaming costs ability as well as recall, so E2
  has two shadows. Paused here for Max before E0 is built.
- **2026-09-24/25** — Max: "good to go". ADR-151 written, and the charter amended. E0 was built in five
  dispatched units and accepted on the real target (§6, E0's record). The target post-dates both E1 bases'
  data. Next: E1's runner (the prompts per arm, the iterate loop, Modal serving), built with no spend, then its
  first unit priced against the $10 ceiling.

---

## 12. Literature — what has been tried near this

Run 2026-09-24, before any build or spend (Max: *"worth looking to other literature for any
attempts surrounding what were trying to do"*). Four searches ran in parallel: repo and
library generation with planner/coder decomposition; SIMD and low-level C; grounding and
constrained decoding; training small code models. **✓** marks a row whose abstract was
re-read in this session and whose figures are the abstract's. **·** marks a row read by a
search pass only. Its figures were not re-checked, so none of them is quoted here. Nothing
below was read past its abstract. A figure an ADR leans on is read in the paper first.

### 12.1 Library generation and decomposition

| | work | what it found | for us |
|---|---|---|---|
| ✓ | **Commit0** (Zhao et al., arXiv 2412.01769, 2024) | 57 Python libraries rebuilt from a spec and unit tests: agents pass some tests, and "none can yet fully reproduce full libraries". Interactive feedback helps | L4 is hard for frontier agents with no graph and no decomposition. The nearest precedent in *goal* |
| ✓ | **RPG / ZeroRepo** (Luo et al., Microsoft, arXiv 2509.16198, 2025) | Repo generation driven by a structured planning graph (capabilities, files, data flow, functions): 81.5% coverage and 69.7% test accuracy on RepoCraft, +27.3 and +35.8 points over Claude Code | The nearest precedent in *method*: generation ordered by a graph. Theirs is written by the model. Ours is derived and graded (100/100) |
| ✓ | **FunCoder** (Chen et al., NeurIPS 2024, arXiv 2405.20092) | Recursive split into sub-functions plus a consensus pick. StableCode-3B "surpasses GPT-3.5 by +18.6% and achieves 97.7% of GPT-4's performance on HumanEval" | A small model gains most from decomposition, which supports E4's shape |
| ✓ | **MapCoder-Lite** (Lee et al., arXiv 2509.17489, 2025) | A multi-agent pipeline distilled into one 7B with agent-wise LoRA: xCodeEval 13.2% → 28.3% | A 7B can carry decomposed roles. They merge the roles into one model; we keep the parser separate |
| · | Parsel (Zelikman et al., NeurIPS 2023); CodePlan (Microsoft, 2309.12499); CodePLAN (2403.13271, a teacher's plans distilled into a small model); Self-planning; CodeChain; AgentCoder; Paper2Code; InlineCoder (2601.00376, call-graph context inlined into the prompt) | Decomposition and planning help, in every variant | None uses a derived graph for the units. Only CodePLAN splits the sizes, and it trains the plan in rather than parsing it at inference |

### 12.2 SIMD and low-level C

| | work | what it found | for us |
|---|---|---|---|
| ✓ | **SimdBench** (He et al., arXiv 2507.15224, 2025) | 136 tasks × SSE, AVX, Neon, SVE, RVV; 18 models; "a universal decrease in pass@k" from scalar to SIMD-intrinsic code | The nearest benchmark. Report per ISA (E1). It is a set of tasks; ours is a hold-out inside one real lattice |
| ✓ | **IntrinTrans** (Han et al., arXiv 2510.10119, 2025) | Neon → RVV translation with compile-and-test feedback: pass rates 47%–100% by model, 0.85×–1.28× the native speed | Translating a sibling ISA works with feedback, which grounds C-2 and the iterate arm |
| ✓ | **AutoVecCoder** (Li et al., arXiv 2605.17978, 2026) | An **8B** model trained on synthesised intrinsic data (VecPrompt) plus RL on execution efficiency (VecRL); state of the art on SimdBench's SSE and AVX subsets | A specialist at our size exists: M-e, if its weights are open. Its data recipe is E3's nearest precedent |
| ✓ | **SSW to RISC-V via LLM** (Fernández Camello et al., Zenodo 21064372, 2026) | One production genomics kernel, SSE → RVV, compile-and-fix loop on compiler and simulator feedback alone; phase 1 up to 21.7× over a naive baseline | The nearest to "port one real library's kernels across ISAs". One kernel, no lattice |
| · | VecIntrinBench (2511.18867); Liu et al., hallucinations in LLM code (2404.00971); ParEval (2401.12554); LLM-Vectorizer (2406.04693, Alive2 verified); VecTrans (2503.19449); KernelBench; NPUEval (2507.14403) | Invented intrinsics are a named failure class. Formal verification closes a minority of cases, so a differential against a reference is the working grader. Kernel accuracy plateaus low even with feedback | G-hsr's three-way class; G-diff as the primary grader; kernels expected to be harder than glue |

### 12.3 Grounding in the repo, and constrained decoding

| | work | what it found | for us |
|---|---|---|---|
| ✓ | **Monitor-guided decoding** (Agrawal et al., NeurIPS 2023, arXiv 2306.10763) | Static analysis masks the decoder to type-consistent identifiers. SantaCoder-1.1B with it compiles better than text-davinci-003; Java, C#, Rust | M-d is precedented, and a small model plus a monitor beats a large one without it. Not yet done for C against a graded graph |
| · | Type-constrained decoding (Mündler et al., PLDI 2025, 2504.09246); Synchromesh; RepoFusion; CoCoMIC; GraphCoder; CodexGraph; RepoGraph; LocAgent; De-Hallucinator; API-documentation study (Jain et al., 2407.09726); package hallucination (2406.10279) | Repo context and graph retrieval beat plain retrieval. Constraints cut compile errors sharply. **Injecting documentation for symbols the model already knows can hurt** (Jain et al.). Open models invent more names than closed ones | C-1 may be negative on dense cells (E1's readings). No graph in this set is graded against a compiler |

### 12.4 Names and in-context examples: the two cautions

| | work | what it found | for us |
|---|---|---|---|
| ✓ | **Li et al., "What Makes In-Context Examples Effective for Code Generation?"** (arXiv 2508.06414, 2025) | Models "struggle to extract generalizable problem-solving insights" from similar problems' solutions. What helps is I/O examples, required helpers and namespace facts. Removing descriptive names costs up to 30 points | **Against C-2 as a hypothesis, for C-1.** E1 is built to settle it on a lattice, where a sibling is the same function and not a similar problem. Written into E1's readings |
| ✓ | **Le et al., "When Names Disappear"** (arXiv 2510.03178, 2025) | Obfuscating identifiers drops intent tasks sharply, and execution tasks too. Benchmarks reward naming as well as structure | Renaming measures memory *and* name-reading. Hence E2's two shadows |

### 12.5 Training small code models; knowledge against skill; contamination

| | work | what it found | for us |
|---|---|---|---|
| ✓ | **Karpathy, "cognitive core"** (X, 2025-06-27) | A few-billion-parameter model "that maximally sacrifices encyclopedic knowledge for capability", tool-using | §3's rule, said informally. A post, not evidence |
| · | Allen-Zhu & Li, Physics of LMs 3.1 (2309.14316) and 3.3 (2404.05405); Gekhman et al. (EMNLP 2024, 2405.05904); Kang et al. (NAACL 2025, 2403.05612) | Facts seen in one form are held but not reliably extractable. New facts fine-tuned in are learned slowly and, once learned, raise hallucination. Unfamiliar training examples teach the model how to guess | The literature's form of ADR-099's result. Facts stay out of the weights, and no training example assumes a fact its prompt lacks (E3) |
| · | SelfCodeAlign (NeurIPS 2024, 2410.24198); MultiPL-T (2308.09895); Magicoder / OSS-Instruct (2312.02120); OpenCoder (2411.04905); phi-1 (2306.11644); Olmo 3 (2512.13961) | Test-validated data an open model generates for itself can beat distillation from closed models. Seeding from real code limits the generator's bias. Fully open data pipelines exist at 1.5B–8B | E3's data: open-model siblings, seeded from real members, compile- and differential-validated. Olmo's open data makes contamination checkable |
| · | RLEF (2410.02089); CodeRL; PPOCoder; StepCoder; SWE-RL (2502.18449) | Execution feedback as a reward is the best-evidenced training signal for code. A curriculum over sub-tasks makes long outputs tractable | E6 (parked) has a well-trodden path. A curriculum along the lattice's axes is a natural shape |
| · | EvoEval (2403.19114); LiveCodeBench (2403.07974); CodeCleaner (2411.10842) | Static benchmarks overstate. Transformed or post-cutoff problems drop scores sharply | G-mem, the shadows, and the post-cutoff code (§4) are the standard controls, applied here |

### 12.6 What is new here

No work found in the four searches does any of these:
1. **A hold-out inside one real, hand-written kernel lattice**, with sibling-cell context
   against an equal-volume control (E1). SimdBench and VecIntrinBench are task sets.
   IntrinTrans and the SSW port translate whole files.
2. **A code graph graded against a compiler** as both the fact source and a grader of the
   generated code. RPG's graph is model-authored. Monitor-guided decoding uses a live
   analyser, not a graded graph.
3. **Quantised and binary distance kernels** (`int8`, `uint8`, `bit1`). The SIMD literature
   is almost all fp32 and fp64.
4. **A general model used only as a parser into a task format, with a smaller writer.**
   No paper in the searches does this at inference. CodePLAN trains a teacher's plans in.
   FunCoder and MapCoder-Lite keep one model.

### 12.7 What it changed on this page

- E1: an iterate arm (three feedback rounds) beside one-shot; per-ISA and per-type reports,
  never pooled; C-2's reading written against Li et al.; C-1 allowed to be negative.
- E0 and E2: two shadows, descriptive and opaque, not one.
- G-hsr: a failure class per body (invented, real but wrong, edge).
- E3: only compile- and differential-validated examples train, generated by an open model
  from real seeds; no example assumes a fact its prompt lacks.
- M: M-d's precedent recorded; M-e (AutoVecCoder-8B) added if its weights are open.
- §3: the Karpathy source found and dated.
