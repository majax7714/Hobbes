# Calvin experiments — a model that writes one language, starting from sqlite-vector

**Status:** proposed (2026-09-24, sixteenth session) · **Type:** programme page — the design
space, the experiments in it, the order proposed, the decisions open · **Compute:** none spent;
E0 spends nothing, and every run after it is held until Max names it and its ceiling
**Charter:** [`calvin-charter.md`](calvin-charter.md), with the one reading this page asks of
it in §3 (decision D-1) · **Priors:** ADR-099 ([`olmo3-ttt-results.md`](../ttt/olmo3-ttt-results.md)),
the keyed rounds ([`calvin-potential.md`](calvin-potential.md) and after), Atlas-0
([`atlas-0.md`](../atlas0/atlas-0.md)) · **The target's cell:**
[`sqlite-vector-c-2026-09-12.md`](../oracle/cells/sqlite-vector-c-2026-09-12.md)
**ADR:** none yet. On acceptance this page takes the next number (151) as ADR-099 and M0 did,
and each experiment Max clears gets its own record beside it.

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

This is ADR-099's result turned into a design. It also matches a line Karpathy has argued
in public, that the useful small model is a *cognitive core*: algorithms and patterns in
the weights, with knowledge looked up rather than stored. That is recalled from his posts
and talks in 2025, not checked; cite the source before an ADR leans on it. The pattern
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
| **M-d** | a copy-restricted decoder whose identifier vocabulary *is* the ledger plus the headers (the charter's M2) | build cost, then small | I1 by construction: no invented intrinsic is emittable |

**Olmo-3-7B has a property no other base here has:** its training data is published (per
Ai2; E0 checks it). Whether sqlite-vector is in the mix becomes a search, not a guess. That
makes Olmo the contamination-clean arm even where Qwen writes better C. The 27B is not
touched (the standing rule).

### 5.2 The teacher (K)

| id | the teacher's job | at | note |
|---|---|---|---|
| **K-0** | none; the compiler and the differential are the only teacher | — | the deterministic floor |
| **K-1** | writes a **spec** per function from `API.md` and the graph's skeleton; the student writes the body | inference | Max's "a teacher model telling the functions and parts". The charter's orchestrator/Calvin split, with the student as Calvin |
| **K-2** | writes **training data** the student learns from (distillation) | training | only from an **open-weights** teacher (D-2) |
| **K-3** | the compiler, the tests and the graph as a **reward** (RL with verifiable reward) | training | expensive; parked until E3 shows a transferable signal |

Two things about the teacher are fixed now, before any design leans on them:
- **Decomposition comes from the graph, not from the teacher.** Which functions exist, their
  signatures, and the build order (leaves first, a topological walk of the call graph) are
  derived deterministically. The teacher adds only what the graph cannot hold: the contract
  in words, the edge cases. That keeps the project's rule that parsers build the skeleton and
  models sit on top.
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
| **G-hsr** | invented names: identifiers that resolve nowhere at compile or link, split into intrinsics, in-repo symbols and libc | yes |
| **G-mem** | the memorisation probe: exact-match continuation of the gold from its first lines (ADR-099's method, its 0.15 line) | yes, greedy |

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
- **The rename shadow** for E2: every in-repo symbol renamed consistently, the map derived
  from the graph. At 100/100 the graph knows every definition and every in-repo reference.
  The shadow must compile and pass G-test unchanged, and that is its acceptance.
- **Contamination facts:** the repo's first public date (unshallow the bench clone); whether
  it is in Olmo 3's published data; G-mem on both 7Bs over the 93 golds, at greedy, no
  training. This last one is inference, a few cents, and is cleared separately if Max wants
  E0 strictly free.
- **Gate:** the self-test passes on every grader, and the shadow passes G-test.

### E1 — the lattice: is it pattern, facts, or skill? (M-a, L0, C-0 to C-4)

- **Question:** on a held-out kernel function, how much does each kind of context move the
  pass rate: facts (C-1), pattern (C-2), both (C-3)? And is pattern more than "more code"
  (C-2 against C-4)?
- **Units:** the 93 native cells: 63 real bodies, read as the result, and 30 wrappers,
  reported apart. Two models (Qwen2.5-Coder-7B, Olmo-3-7B). Five context arms. k = 5 samples
  at a fixed temperature, plus greedy.
- **Readings, written before the run:**
  - C-2 − C-4 > 0: pattern is doing work beyond volume, which is the hypothesis in its purest form.
  - C-1 − C-0 on G-hsr: whether facts remove invented intrinsics (Atlas-0's sand, on real code).
  - The pass rate by axis of the hole: is `avx512` from `avx2` easier than `int8` from `float32`?
    The lattice says which axis is cheap to cross.
  - Every row beside its G-mem reading. A cell the base recalls is reported apart.
- **Cost:** ~93 × 5 × 2 × 6 ≈ 5,600 generations of a few hundred tokens over prompts of
  2–10k. Under an A100-hour: **≈ $3–6; ceiling proposed $10.**
- **P12:** `arm=model+prompt`. One agent per cell, not a Hobbes test. Recorded as such.

### E2 — the rename shadow: memory or skill? (M-a, L0/L2, on the shadow)

- **Question:** does E1's score survive when the in-repo names are ones the base has never
  read? The intrinsics and the SQLite API are not renamed, since they are the language, not
  the repo.
- **Units:** E1's best and worst arms, on the shadow, plus L2's `sqlite-vector.c` holes.
- **Reading:** the gap between the original and the shadow is the memorised share. A small
  gap with G-mem low is the first evidence of skill.
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
- **Shape:** Hobbes derives the units (the file's functions, leaves first). The teacher,
  shown `API.md` and the skeleton, writes one spec per unit. The student writes the bodies
  in order, each graded before the next. `hobbes gate` checks the file at the end.
- **Arms:** student alone on the skeleton; student with specs; teacher writes the bodies (the
  ceiling); student with specs, on the shadow.
- **P12:** this one **decomposes**: planner-defined units, one single-use agent per unit,
  each window smaller than the file. It is the first experiment on this page that is a
  Hobbes test.
- **Cost:** the teacher's calls (a subscription or the API, D-2), plus student inference.
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

- **D-1 — is this Calvin?**
  - **a (recommended):** yes, under §3's reading: skill in the weights, facts in the ledger.
    The charter stands. §3 is added to it as an amendment on acceptance, and I7 (smaller as
    Hobbes grows) still applies: every fact the model reaches for is a fact the graph should
    serve.
  - b: a new name for a writer model, leaving Calvin as the grounder.
  - c: allow repo memory in the weights. Not recommended: ADR-099 §9b measured knowledge in
    weights overriding live context, and a SHA change would make the model wrong silently.
- **D-2 — the teacher.**
  - **a (recommended):** Claude at inference only (K-1, E4); any training data (K-2) comes
    from an open-weights teacher.
  - b: check the terms first and decide K-2 then.
- **D-3 — the first spend.**
  - **a (recommended):** E0 now, no spend. E1 on both 7Bs at a $10 ceiling, first unit priced.
  - b: E0 only, and decide E1 after its self-test.
  - c: E0, E1 and E5 together (the science track in parallel), with $10 + $25 ceilings.
- **D-4 — the NEON and RVV arms.** Add qemu-user to the image now (+ some size to a 3.3 GB
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
