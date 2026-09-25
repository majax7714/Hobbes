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
