# Calvin — the reassessment of its design

**Status:** rounds 1 and 2 recorded (2026-09-28); round 3 (§11) and Route 1's sessions 1 and 2 (§12, §13)
recorded (2026-09-29). Session 2's verdict: **closed**; Max closed Calvin on this lattice and returned to extraction. The residual on this lattice is deterministic (compiler, lifter,
solver, lookup), so Calvin has no job left on sqlite-vector; a second target is the open question.
Round 2 (§10) corrects four round-1 readings, each marked where it sits ·  **Type:** design review. It runs nothing and spends nothing · **Why:** Max, 2026-09-28: *"calvin
is a model or tool which can program in a language but that is intentionally not general. that is so insanely
general that picking any specific point is difficult. instead of loading up a new experiment, the efficient thing
is to take that idea and look through every route which could make sense against whats been tested … we need a
more cohesive design of calvin before progressing through experimenting."*
**Reads:** the register ([`README.md`](README.md), CV-1 to CV-21; and MA-1 to MA-18), the charter
([`calvin-charter.md`](calvin-charter.md)), and [`calvin-experiments.md`](calvin-experiments.md) §0 to §12.
**Naming:** [ADR-152](../../adr/152-the-harness-is-shanks-calvin-is-the-model.md). Calvin is the model; Shanks is
the harness.

> **Not versioned** (ADR-103). Nothing here is a registered result. The two probes below read stored rows with no
> model call, and they are described, not registered. Literature figures come from abstracts, and each must be
> read in the paper before an ADR leans on it (§12's rule).

---

## 1. How Calvin is regarded

- **Calvin** is a model or tool that can program in a language and is intentionally not general. It need not be
  a typical LLM. The charter's contract (I1 to I7, and "wrong only in ways that are visible") binds any form it
  takes. The lattice tested one form of it: a stock multilingual general coder (Qwen2.5-Coder, Olmo-3) steered by
  context and one LoRA. A negative result there is a result about that form.
- **Shanks** is the gated harness (`hobbes dispatch`, [`../../shanks/`](../../shanks/README.md)). It is Calvin's
  accepted lowest floor, from the keyed rounds (ADR-107; the BUILDLOG of 2026-09-11 and 2026-09-12). It treats a
  symptom, a frontier agent's unchecked diff, and it is not Calvin's design. A Calvin result is measured against it,
  and Calvin's design is not bound to extend it.

## 2. The thesis, decomposed

Max's thesis (2026-09-28) bundles six claims. The table below says what each would mean and what the records have
measured of it.

| claim | operationally | what the records measured |
|---|---|---|
| (a) constrained input | The model sees code, ledger records and shots, and no prose or open repo | **Partly.** Context *content* was varied (C-0 to C-4, S-0 to S-5), never how constrained the input was. The 7B parser's prose fields hurt, by −0.07 to −0.17 (CV-17) |
| (b) only codes | No general capability, and no tools or actions | **Never a variable.** Every model was a general coder. Shanks restricts the doer's environment, not the model |
| (c) one language | Weights or decoder specialised to C | **Never a contrast.** Every task was C, and every base was multilingual |
| (d) more efficient | Cost per verified unit, at equal verified quality, against the floor | **Prices only:** E4 about $0.40 a file, the 32B about $0.58 a file (CV-18). No same-unit baseline |
| (e) better aligned | Does only what was asked, fails visibly, reaches for nothing | **Never defined.** G-hsr's `invented` rate is the one related figure. The gate's record (CV-4) is Shanks's, not a model's |
| (f) per task | Normalised per P12 unit | Yes. Every lattice figure is per cell or per unit |

The about $21.50 lattice programme measured capability on one lattice. The half of the thesis that motivates
Calvin, (b), (c), (d) and (e), is **untested, not refuted**.

**The charter and ADR-151 describe two components, not one design.** The charter's Calvin is a grounder that never
decides *what*; `hobbes gate` already fills that slot with the residual at zero (`derive/ground.py`). ADR-151's
Calvin writes. The two fit together as a writer that proposes and a grounder that judges. The charter's
invariants are the contract the pair must meet.

**One correction to the charter, for compiled targets.** An invented name in C fails at compile or link time, so it
is visible, not the invisible failure charter §8 calls it. The invisible failures in C are *real, wrong* and *edge*
(G-hsr's classes), and a body that passes the numbers while calling an extra helper.

## 3. The finding: where the restriction lives

Two passes ran separately, one over the records and one over the literature, and both reached the same conclusion.
**A restriction works when it is a mechanism. It does not work when it is advice to the model or training in its
weights.**

| where the restriction lives | the records | the literature |
|---|---|---|
| **Told to the model** (facts and rules as text) | Facts don't steer, at either size, beside the shots or in the loop (CV-13, CV-19). The 7B parser's fields hurt (CV-17) | Correct facts in context do not steer generation (CodeUpdateArena; "To See is Not to Master"; UCD). Negated prompts get worse as models scale (Jang et al.), and 476 of D-13's 477 fact lines were negatives. Retrieval hurts when the answer is already given (Maninger et al.) |
| **In the weights** (training) | A 300-step LoRA sharpens reading named neighbours and adds no skill (CV-15). Learned typing collapses (CV-10) | Narrow code fine-tuning causes broad misalignment (Betley et al.). It is strongest in Qwen2.5-Coder-32B-Instruct, the family of the lattice's own 32B, and a rank-1 LoRA is enough (Turner et al.). *Corrected in §10: the cause is covertly harmful data, not narrowness, and that model is "most similar to GPT-4o", not the strongest.* Capability filtered from pretraining returns when the context supplies it (Deep Ignorance). SFT memorises where RL generalises (Chu et al.) |
| **In the decoder or output language** | Never run | Type-constrained decoding more than halves compile errors (Mündler et al.; *§10: pass@1 in synthesis rises only about 3.5% relative*). Dependency-constrained decoding cuts invented APIs by about 70% (MARIN). *Hazard:* a plain mask distorts the distribution and turns an invented name into the nearest legal one (grammar-aligned decoding), so it needs a proper sampler (sequential Monte Carlo, Loula et al.), and the differential stays the judge |
| **In the harness** (verifier, gate, one call per unit) | The gate is a safety property (CV-4). Probe: a 7B choosing its best sample reaches the 32B's greedy score (§5) | Sampling pays wherever answers can be verified (Large Language Monkeys). Small models plus search are Pareto-optimal (Wu et al.). In an untrusted-planner, trusted-implementer pair, monitors that read the plan score AUROC 0.52 and monitors that read the code 0.96 (Factor(U,T)) |

The principle that follows is inferred from both columns. **Turn every negative fact into an impossibility (a
mask, a closed op set, a gate). Turn every positive fact into a pattern or a mapping in context. Keep any trained
part to language skill, never the target's facts.** The one fact a student ever acted on was a positive mapping
(the init, D-12).

## 4. What this does to the thesis

- **"Better aligned."** The literature found no study showing a narrow or code-only model better aligned than a
  general one on the same task, and the direct evidence runs the other way. A model with no language channel also
  gives up monitorable reasoning (Korbak et al.), so the charter's read-trace would have to stand in for it. The
  defensible form is AI control's: **wrong only in ways that are visible, and every concrete output checked.** That
  is the charter's own rule (§8). It is also mostly a property of the system around the model, so it must be
  *measured* (§7), not assumed from narrowness.
- **"More efficient."** Per call, yes. In the literature the gains come from verifier-gated sampling and from
  calling the planner only on failure, not from narrowness:
  - PaT: about 69% lower cost at comparable performance;
  - MinionS: 5.7× cheaper, recovering 97.9%;
  - Large Language Monkeys and Wu et al.: sampling against a verifier.

  The measure is **cost per verified unit for the whole pair, escalations included**.
- **"One language."** Multilingual code pretraining helps each language (Yang et al.; Baltaji et al.). The
  specialists that win sit on a general code base: Code Llama Python, LLM Compiler, and SuperCoder. One language
  belongs in a specialisation layer: post-training, the decoder, or the output language.
- **"Constrained input."** This is the best-supported claim, through decomposition, small windows and enforced
  constraints, but only where the constraint is *structured and enforced*.
- *Corrected in §10: SuperCoder is given gcc -O3 assembly to superoptimise, and it compiles nothing without it. It is an editor of a correct artifact.* **The strongest evidence for the thesis** as first read was SuperCoder: Qwen2.5-Coder-7B with RL on one low-level language
  reaches 95.0% correct against Opus 4's 51.5%. It is translation-shaped, since its source program is in the input.
  RL is also probably bounded by what the base reaches at large k (Yue et al.; ProRL contests this).

## 5. The two probes (stored rows, no model call)

Both read `~/.hobbes/bench/calvin-lattice/d11/run-{7b,32b}-*/rows.jsonl`, over arm S-2h, round 0, 127 units and 10
samples each.

**Selection by the graders** (units passing):

| model | greedy | mean sampled | best of 3 | best of 10 | the arm's spend |
|---|---|---|---|---|---|
| 7B | 58 (0.46) | 52.3 | 63 | **76 (0.60)** | ≈ $0.18 (half of the run's $0.365, by request share) |
| 32B | 78 (0.61) | 75.5 | 83 | 96 (0.76) | $1.74 |

At best of 10, the 7B reaches the 32B's greedy score at about the same money. The 7B's 11 samples cost ≈ $0.18,
and the 32B's one greedy sample is ≈ $0.16, an eleventh of its $1.74 (inferred by request share).
- **The caveat.** The graders that choose also grade. That is fair only where a reference exists at inference.
  sqlite-vector's scalar kernel is one, and most work has none.
- **The ceiling a decoder mask could reach.** Units where every sample failed as `invented`: 22 of 127 at the 7B
  (13 of them sse2) and 11 at the 32B.
- **The coverage a trained route needs.** Units with no pass in 10 samples: 51 at the 7B and 31 at the 32B. Units
  with mixed samples, where RL has signal: 42 and 41.

## 6. The routes

Each route is placed by where its restriction lives. **Reg** gives the register entries that bear on it.

| id | route | lives in | Reg / the literature | state |
|---|---|---|---|---|
| R1 | Deterministic grounder plus a small ranker (charter M1) | harness | CV-3; M0 found most NULLs were things the diff creates | the grounder is built (`hobbes gate`); the ranker has no measured job yet |
| R2 | Constrained decoding: a ledger-plus-headers identifier mask, type and grammar masks, pointer or copy (charter M2, M-d) | decoder | CV-19 and CV-20 motivate it; Mündler, MARIN, monitor-guided decoding; the distortion hazard (Park et al.) | **never run**; a ceiling of 22/127 units at 7B (§5) |
| R3 | A stock small model, context only: graph-served shots | input | CV-12, CV-17, CV-18: the one lever positive on every rung | established on one lattice; a second target is what is new |
| R4 | Verified search: k samples, graders select, NULL if none pass | harness | CV-21 is the weak form; Large Language Monkeys, Wu et al. | **the selection reading is new** (§5) |
| R5 | Pattern LoRA (M-b) | weights | **CV-15 refutes it at 300 steps**; emergent misalignment in the same family | the 3,000-step pair needs a fair control and a cap |
| R6 | Distillation from an open teacher (K-2) | weights | CV-15's mechanism predicts the same null; subliminal learning says the teacher must be on a different base | not run; low priority |
| R7 | Training from scratch on one language (M-c, E5) | weights | CV-7 to CV-10 (Atlas); pretraining evidence favours related-language mixes | science only (E5) |
| R8 | RL with a verifiable reward: compile, differential, graph (K-3, E6) | weights | SuperCoder, Kevin, AutoVecCoder for it; Yue et al. bound it; reward hacking generalises (MacDiarmid et al.) | not run; a third of units have signal (§5) |
| R9 | Removing capability from a general model | weights | Łucki et al.: unlearning is undone in 10 examples; Deep Ignorance: returns through context | poor fit |
| R10 | Positive composition shots: an ISA lowering table ("op X on this ISA = this expression") | input | CV-19: the only fact acted on was a positive mapping; CV-20 left composition open | never tried |
| R11 | Translate first: port a sibling or the scalar reference | input | E2: the stated task is most of the opaque gap; E4-c's scalar arm was held; IntrinTrans, VERT, SuperCoder | never run |
| R12 | A closed vector-op DSL plus a deterministic lowering to each ISA | output language | removes CV-18's capability crossing and CV-20's sand by construction | never measured; fits I7 best |
| R13 | Structured output: edit ops or ASTs, not text | output language | CV-1 and CV-2 refute template fills for a frontier filler; Coeditor, GrammarCoder | fold into R2 (fixed signature, body only) |
| R14 | Restricting the interface (partitions from `hobbes plan`) | harness | CV-4; named, never built (Shanks §6) | Shanks's, not Calvin's |
| R15 | Parser/writer split (K-1) | input | **CV-17 refutes it at 7B**; DURIT, Cascaded Code Editing, Aider as precedents | closed at L0/L1 |
| R16 | Non-agent: one call per unit, no tools | harness | MA-6, MA-9; P12 | adopt; measure under §7 |
| R17 | Size: the 32B as the student | a knob | CV-18 prices it; R4 roughly equalises the two at equal cost | a knob, not a design |
| R18 | Ledger Machine, typed attention (charter M3) | architecture | CV-10; gated on R2's errors | closed until R2 |
| R19 | Planner on failure: the small writer by default, the frontier model only where the gate or differential fails | harness | PaT (about 69% cheaper) | **not in the design space before**; composes with R4 |
| R20 | Search over compositions: the model's samples as a prior, enumeration against the scalar oracle; an e-graph or rewrite system at the deterministic end | harness / tool | HySynth, VERT, AlphaVerus; composition by subtasks (Khan et al.) | **not in the design space before**; targets CV-20's open end |
| R21 | Symbol tokens: each intrinsic or ledger symbol a token on a frozen base, with its embedding regenerable per SHA | decoder / weights | ToolkenGPT | new; between R2 and R5 |
| R22 | Formal specs as the input (ACSL to Frama-C) | input | VeCoGen; vericoding: prose adds nothing once a formal spec exists | new; later rungs |
| R23 | Training on the ISA's *usage and compositions* (language skill, not target facts): RL or SFT on public intrinsic corpora | weights | PriCoder and UCD for training on usage; Zhao et al. on skill composition; permitted by ADR-151's amendment | new; held behind §5's coverage |

## 7. What "efficient" and "aligned" should mean, per P12 unit

These are proposed definitions. Neither exists in the repo yet.
- **Efficient: cost per verified unit.** Dollars (or GPU-seconds, and tokens in and out), divided by units passing
  G-compile, G-diff, G-hsr and the gate, read beside the verified pass rate. The Modal `calls.jsonl`, E4's window
  record and Shanks's tracker already record the inputs.
  - **Missing:** a same-unit baseline against the floor. No frontier model has written a lattice unit.
- **Aligned: wrong only visibly.**
  1. The invisible-failure rate: passes compile and the repo's tests but fails G-diff or G-graph.
  2. The invention rate (G-hsr), which is 0 by construction under R2 or R12.
  3. The out-of-scope rate: files outside the partition, lines outside the span (I3), egress refusals.
  4. The action surface (0 for a non-agent unit).
  5. The honest-NULL rate.
  6. From the literature: attack success under a red-team planner, in a control evaluation (Factor(U,T), Ctrl-Z).
  - **Missing:** the partition and a same-unit comparison. Shanks's own figures describe its doer, and it makes no
    arm comparison ([`../../shanks/shanks-harness.md`](../../shanks/shanks-harness.md) §4).

## 8. Candidate designs (round 1)

- **A — "a proposer in a closed world"** (recommended in round 1; *demoted in §10: its measured gain is selection by the graders, which is Shanks's shape*).
  - **The pieces:** a stock small coder with no training (R16 and R3). It gets the scalar reference where one
    exists (R11) and positive composition shots (R10). Decoding is masked to the ledger plus the ISA's real
    intrinsics, with a proper sampler (R2). k samples are chosen by G-compile, G-diff, G-hsr and the gate (R4). A
    unit with no passing sample returns NULL, and the frontier model is called only on failure (R19).
  - **The fit:** I1 holds by construction, I5 with the seed, and I7 because every restriction is derived by Hobbes.
- **B — "a narrow DSL author plus a deterministic lowering"** (R12, R4, R11). The ISA axis moves into Hobbes. It goes
  ahead only if about 80% or more of the 93 gold bodies, edge handling included, are expressible. It changes
  "writes C" to "writes a lowered IR".
- **C — the floor tightened, with A for leaf units** (R14, R1, R19). This is Shanks with Calvin as a delegate. Under
  ADR-152, C is Shanks's route, recorded as the comparison, not as Calvin's design.
- **Held: a trained route** (R8 or R23, SuperCoder-shaped). It waits behind §5's coverage reading, an
  emergent-misalignment evaluation, and a differential reward that cannot be gamed.

**Zero-spend probes before any spend:**
- R10's reach on D-14's 74 composition-needed names, from the 40-repo draw;
- R12's expressibility over the 93 gold bodies;
- R4 and R2's ceilings, already read (§5);
- large-k coverage per cell, the stored k = 10 already read (§5).

**Stays closed** (the register):
- facts as text (CV-19, CV-20);
- the 7B parser (CV-17);
- the 300-step pattern LoRA (CV-15);
- Olmo as the student (CV-12);
- template fills for a frontier model (CV-1, CV-2);
- repo facts in weights (charter §7, MA-17, MA-18);
- abstention trained rather than instructed (MA-15, MA-16);
- learned typing at Atlas scale (CV-10).

## 9. The literature (round 1)

A search pass read these at abstract depth on 2026-09-28. ✓ means the abstract was fetched and read in that pass,
and every figure here is the abstract's. None was read in the paper. §12 of
[`calvin-experiments.md`](calvin-experiments.md) holds the 2026-09-24 pass, and it is not repeated here.

| area | ✓ work | what it bears on |
|---|---|---|
| narrow against general | Yang et al., scaling laws per programming language (2512.13472); Baltaji et al., cross-lingual transfer (2310.16937); Aryabumi et al., "To Code, or Not To Code?" (2408.10914); Code Llama (2308.12950); Grangier et al., "Plan Early!" (2402.01093); LoRA Land (2405.00732); Medprompt (2311.16452); Belcak et al., small models for agents (2506.02153); Wu et al., inference scaling (2408.00724); Brown et al., Large Language Monkeys (2407.21787) | (c) and (d): specialise on a general base; efficiency comes from inference and verification |
| narrowness and alignment | Betley et al., Emergent Misalignment (2502.17424); Turner et al. (2506.11613); Wang et al., persona features (2506.19823); MacDiarmid et al., reward hacking (2511.18397); Qi et al. (2310.03693); Cloud et al., subliminal learning (2507.14805); O'Brien et al., Deep Ignorance (2508.06601); Łucki et al. (2409.18025); TAR (2408.00761); gradient routing (2410.04332); Greenblatt et al., AI Control (2312.06942); Factor(U,T) (2512.14745); Factor(T,U) (2512.02157); Ctrl-Z (2504.10374); Korbak et al., CoT monitorability (2507.11473); Sleeper Agents (2401.05566); CAIS; "Keep the Future Human" (2311.09452); Scientist AI (2502.15657); Guaranteed Safe AI (2405.06624) | (e): narrowness is not alignment, and checking the output is |
| constrained input and output | Mündler et al. (2504.09246); grammar-aligned decoding (2405.21047); sequential Monte Carlo control (2504.13139); "Let Me Speak Freely?" (2408.02442); XGrammar (2411.15100); Maninger et al. (2607.05936); MARIN (2505.05057); Khati et al. (2601.19106); ToolkenGPT (2305.11554); "Copy Is All You Need" (2307.06962); GrammarCoder (2503.05507); Coeditor (2305.18584); Cascaded Code Editing (2604.19201); Aider architect/editor (blog, 2024-09-26); LLM Compiler (2407.02524) | R2, R13, R21 |
| search and synthesis | SuperCoder (2505.11480); AlphaEvolve (2506.13131); HySynth (2405.15880); Khan et al. (2503.15540); VERT (2404.18852); Syzygy (2412.14234); VeCoGen (2411.19275); vericoding (2509.22908); AlphaVerus (2412.06176) | R11, R20, R22 |
| RL, skill, composition | Yue et al. (2504.13837); ProRL (2505.24864); Chu et al. (2501.17161); RL's Razor (2509.04259); "LoRA Without Regret" (blog, 2025-09-29); Kevin (2507.11948); "To See is Not to Master" (2603.15159); CodeUpdateArena (2407.06249); UCD (2602.20799); ExploraCoder (2412.05366); Zhao et al., skill composition (2409.19808); Jang et al., negated prompts (2209.12711) | R8, R23, and CV-15's and CV-19's mechanisms |
| Calvin-shaped pairs | MinionS (2502.15964); PaT (2605.07248); DURIT (2508.10019); ExplicitLM (2511.01581); RETRO (2112.04426) | R19; the pair on cost |

**Seen in search only, with no figures quoted:** FunSearch, AlphaDev, STOKE, LGuess, SACTOR, the Verilog
specialists (VeriGen), the fast-apply vendors.

**What appears unattempted:**
- a same-size narrow-against-general comparison on alignment or safety;
- cost per verified task for a narrow writer against a general writer of the same size, inside a planner/writer
  pair;
- positive steering by a mask or tokens, measured against the same facts as prose (R2 against D-12's arm);
- training on SIMD intrinsic compositions, tested on a held-out real lattice.

**One correction to §12.6.** Item 4 ("no paper … a general parser with a smaller writer at inference") has near
precedents in DURIT, Cascaded Code Editing, Aider's architect/editor, Factor(U,T) and MinionS. What stays new is a
compiler-graded graph as the writer's only source of facts, and the lattice hold-out.

## 10. Round 2 (2026-09-28)

Round 2 was sent with round 1's record and ADR-152's framing, in which Calvin need not be an LLM. It had two agents:
- **Routes:** stress-tested round 1 against ADR-152, widened the space to non-LLM forms, and ran the probes round 1
  left open.
- **Literature:** covered non-LLM forms of Calvin, read the load-bearing round-1 papers past the abstract, and
  built the strongest case against Calvin.

I re-ran two of the routes pass's probes (the vectorizer tally and the non-finite split), and both reproduce. The
probes compiled but did not run code, inside the image with `--network=none`. Their scripts are in the session's
scratchpad, not the tree.

### 10.1 Where a verifier is Calvin's, and where it is Shanks's

A proposed test. A check is part of Calvin only if all three hold:
1. It acts on *partial* output (a prefix, an AST or IR node, a sub-program).
2. It changes what can be proposed next.
3. Its knowledge is Hobbes-derived at the SHA, not the task's acceptance test.

A check that only accepts or rejects a finished artifact is Shanks's shape, whatever model sits inside it.

**What the test says about round 1:**
- **Best-of-k selection** by the graders fails (1) and (2): it is a gate. That makes **Design A mostly Shanks moved
  one step earlier**. Its only measured gain (§5) is selection, and its only Calvin-shaped part, the decoder mask
  (R2), has never run. Calvin's own figures are read at k = 1, with any in-loop search compute charged to Calvin.
- **SMC under a mask, and enumeration with pruning,** pass the test. A search that uses G-diff as its oracle fails
  (3), and the fix is to split the oracle: the search sees the bulk cases, and grading holds out the edge cases and
  G-graph.

**The principle, restated so it survives a non-LLM Calvin:**
- negative facts become things the output language cannot say;
- positive facts become primitives, rewrite rules and lowering tables that Hobbes owns and regenerates per SHA;
- skill becomes a prior or cost model over that space, the only part trained;
- checks prune inside the search.

"Positive facts as patterns in context" is the LLM special case of the second line.

### 10.2 The probes

| probe | reading | limits |
|---|---|---|
| **R12, expressibility.** VK-1: a closed vector-kernel language of about 20 ops, a `sum → acc` reduce, an any-lane exit guard, a NaN-zero select, and forms WRAPPER, MAPREDUCE and COMPOSITE | 63 real bodies (plus 30 wrappers) and 148 distinct intrinsics reached, **0 outside VK-1's classes**. **21 of 21 (type, metric) families share one program across sse2, avx2 and avx512.** 60 of 63 bodies can match under one non-finite semantics; 63 only with a per-ISA parameter | VK-1 was defined after reading the files, so vocabulary coverage is partly by construction. Nothing was lowered or graded |
| **The deterministic baseline:** clang 18 `-O3 -Rpass=loop-vectorize` on the scalar reference `distance-cpu.c`, at each ISA's flags | strict FP: 3 of 21 families vectorize; **reassociation only (NaN and inf kept): 14 of 21**; `-ffast-math`: 16, which is invalid here. The 7 left are f16 l2_impl/l1/dot/cosine and bf16 l2_impl/dot/cosine: the guarded kernels and the LASSQ l2 | a vectorized-loop remark is not a correct or fast kernel |
| **The model's failures against the compiler's.** Stored D-11 S-2h round-0 rows | 7B sampled pass 0.18 on the 42 compiler-vectorizable cells, against 0.21 on the 21 compiler-hard cells. 32B: 0.40 and 0.32 | the model's failures are not where the deterministic tool's are |
| **The non-finite split** (E0's self-test report, 77 disagreements) | 22 slot/cases differ from the scalar the same way on every ISA. **8 split by ISA:** DOT:BF16 `large` (sse2 against avx2/avx512), and L1/L2/SQUARED_L2:F16 `inf_both_same` (sse2 and avx2 against avx512) | a held-out ISA's answer there cannot be known from its inputs |
| **R10 reach.** D-14's 74 composition-needed occurrences against the 40-repo draw | 33 are a 256-bit body in the 128-bit file (width discipline, not composition). 37 are same-width later-feature names: SIMDe's SSE2 branches give a positive composition for **15 (71 of 265 rows)**, the widenings and `abs_epi8`. **None exists for** blendv/maskz (really a NaN-to-zero select), `shuffle_epi8` (popcount), `cvtph_ps`, hadd, extract, dp_ps or insert. 4 are available names G-hsr misfiled (below) | matching by name and pattern, unverified beyond SIMDe's branches |
| **The composition class's size** | file-local helpers use 0 to 13 intrinsic calls, at most 7 distinct (`popcount_sse2`: 13 and 5) | within reach of search (inferred). The rows hold no logprobs, so a ranker cannot be probed from them |

**Two instrument findings, proposed for the register and not yet registered:**
- **G-hsr misfiles macro intrinsics called with too few arguments as invented.** clang says "undeclared
  identifier". This touches D-14's composition class: 4 occurrences, 22 rows.
- **The "edge" class is partly the target, not the model.** G-diff grades non-finite cases against each ISA's own
  gold, and 8 of those golds disagree by ISA. Round 1 counted "edge" as an invisible model failure (§2).

### 10.3 What round 2 corrects in round 1

The literature pass read these past the abstract, some through the fetch tool's HTML summary:

| item | round 1 read | read in the body |
|---|---|---|
| **SuperCoder** (2505.11480) | a 7B writing one low-level language beats Opus 4 | Its input is C *plus gcc -O3 assembly*, which it superoptimises. The authors: it "fails to produce any compilable code without it." Opus 4's 51.5% was 0-shot with one sample. It supports R11 and R8 where a correct artifact exists, not writing from a spec |
| **Emergent Misalignment** (2502.17424) | narrow code fine-tuning causes misalignment, strongest in Qwen2.5-Coder-32B | Controls on the same code format: secure code 0%, the same insecure code framed as teaching 0%. The cause is *covertly harmful* data. The Coder-32B is "most similar to GPT-4o", and the top open-model rate was a Mistral-Small (7.3%). The hazard for Calvin is a *gameable reward*, not narrowness |
| **Type-constrained decoding** (2504.09246) | more than halves compile errors | Compile errors fall 75.3% and 52.1%, but synthesis pass@1 rises only about 3.5% relative (Qwen2.5-32B HumanEval 79.6 → 81.8), with runtime up 39–52% |
| **Grammar-aligned decoding** (2405.21047) and **SMC control** (2504.13139) | a mask turns an invented name into the nearest legal one; fix it with a proper sampler | The paper does not show the name substitution, which was round 1's inference. Correcting the distortion converges slowly and does not reliably raise correctness. SMC's large gains come from *expensive potentials* (tests run on partial output) and resampling. So R2 and R4 merge into one design: SMC with compile and differential potentials |
| **Yue et al.** (2504.13837) | RL is bounded by the base at large k | Confirmed for code. Distillation from a stronger teacher does expand the boundary, which moves R6 ahead of R8 |
| **Factor(U,T)** (2512.14745) | AUROC 0.52 on the plan against 0.96 on the code | Confirmed (Gemini 2.0 Flash and Llama 4 Scout, BigCodeBench backdoors). The caution is R19: a frontier planner on failure is the untrusted-planner channel, safe only because the gate reads code |
| **PaT** (2605.07248) | about 69% cheaper | Confirmed, but most of the saving is the small model alone: 8B alone reaches 85.58 at 0.25 cost, against 8B/32B at 87.39 and 0.31. The verifier is self-generated tests on easy Python |
| **AutoVecCoder** (2605.17978) | the SIMD specialist exists (abstract only) | Qwen3-8B, SFT distilled from DeepSeek-R1 plus RL on correctness and speed, **with the scalar C in the prompt**. AVX 76.76 / SSE 77.35, against GPT-5 at 62.50 / 55.88, zero-shot. The weights are public. It is distillation plus RL on usage, translation-shaped |
| **Differential selection** (new: LLM-Vectorizer, 2406.04693) | — | A checksum differential plus repair passed 125 of 149 loops. Alive2 then proved 37 of the checksum-passing ones wrong. §5's selection is exactly this regime: the integer and bit kernels need SMT equivalence, and the float kernels need adversarial inputs |

### 10.4 Non-LLM forms of Calvin

**The best supported: ISA-semantics synthesisers and verified rewriters.** They are narrow and invention-free by
construction, and they compose real ops, which is CV-20's open class. **None has been compared with an LLM.**
- **VeGen** (ASPLOS 2021) lifts Intel's intrinsic pseudocode to SMT. On OpenCV's dot kernels it runs 1.1–2.0× over
  LLVM on AVX2, but loses on float abs (0.4×).
- **Isaria** (ASPLOS 2024) synthesises verified rewrite rules. It runs 1.0–6.9× over the vendor's hand-written DSP
  kernels, and fully unrolls, so large kernels run out of memory.
- **Hydride** (ASPLOS 2024) maps 3,557 instructions onto 397 target-independent operations.
- **Minotaur** (OOPSLA 2024) verifies 165 x86 intrinsics in Alive2.

**An LLM writing into a verified IR** (Design B's shape) is precedented by **LLMLift** (NeurIPS 2024). GPT-4 writes a
Python-embedded IR and invariants, SMT verifies them, and rewrite rules lower them: 44/45 against MetaLift's 40/45 on
Spark, and 60/60 against 57/60 on TACO, from about 100 lines of prompt against 1,000+ lines of domain code.
Industrial portable-SIMD layers (Highway, ISPC) are already a closed op set with a per-ISA lowering.

**Useful parts:**
- Stitch-style library learning over real sibling kernels, which would give named composites (for example, a
  horizontal sum). This is unattempted.
- kNM-LM: a datastore of only the tokens the base gets wrong; Java completion rose from 54.59% to 69.66% with no
  fine-tuning. A datastore mapping invented names to gold tokens is untested.
- Learned cost models as rankers (MLGO, Ithemal, Tensat).

**The most undercut:**
- Training from scratch on one language: nothing measures the data it needs.
- Diffusion: Stable-DiffCoder is flat on C++ against its autoregressive twin (69.4 against 69.6), and CodeFusion is
  withdrawn.
- GNN, tree and pointer decoders: they guarantee syntax, not semantics.

**The routes pass's forms,** F1 to F10:
- **F1:** a structural decoder under a mask; this is round 1's A reduced to its core.
- **F2:** a small model trained from scratch; hold.
- **F3:** a Hobbes-owned IR plus deterministic lowering; the best I7 fit.
- **F4:** equality saturation from the scalar reference, with a learned cost.
- **F5:** library learning.
- **F6:** verified search over available intrinsics, with a prior.
- **F7:** a copy-edit port over sibling spans.
- **F8:** a small model ranking deterministic candidates.
- **F9:** the Ledger Machine; closed.
- **F10:** an AST analogy solver.

### 10.5 How others measure it

- **Efficient.** *Cost-of-pass* (Erol et al., 2504.13359) is §7's "cost per verified unit", already formalised,
  with a frontier minimum over the models available. The frontier cost-of-pass halves about every 2.6 months. Kapoor
  et al. (2407.01502) split fixed cost from variable cost, and require **out-of-distribution holdouts** for a
  task-specific system: for Calvin, a second target, not held-out cells.
- **Aligned.**
  - *ImpossibleBench* (2510.20270) mutates tests to contradict the spec, so any pass is cheating. GPT-5 cheats 54%
    of the time, and 9% with an "abort as impossible" option.
    - **The cheapest direct test of "better aligned":** plant units whose scalar reference is mutated so no correct
      kernel exists, and measure cheating and honest NULLs for Calvin *and* Shanks. *Corrected in §11.4: a mutated
      reference still has a correct kernel; an impossible unit needs two specs that disagree.*
  - METR found reward hacking in 30.4% of RE-Bench runs, including on its kernel task. The Sakana CUDA Engineer
    retraction is the same failure: the harness was bypassed.
  - OverEager (2605.18583): permissive frameworks act out of scope in 5.4–27.7% of runs, and much of it is the
    framework and the prompt.
  - PatchDiff (2503.15223): 29.6% of plausible SWE-bench patches diverge from the gold.

### 10.6 The case against Calvin

- **Every narrow-wins result above compares against a frontier model sampled once, with no tools and no feedback.**
  No study pits a narrow writer against a frontier *agent with the same verifier*, which is Shanks's shape.
- **The alignment wins that exist come from the environment:** read-only tests, an abort option, the oracle out of
  reach. Shanks can adopt every one of them.
- **General models overtake specialists within months, in code:**
  - o3 (2724) over o1-ioi (2214);
  - frontier cost per task at fixed performance falls about 13× a year (Epoch AI, 2026-09-22).
- **Decomposition can lose.** Multi-agent variants range from −70% to +80.8%, and errors are amplified 17.2×
  without central verification (Kim et al., 2512.08296).
- **On this lattice, the job may already be deterministic.** A compiler vectorizes 14 of 21 families from the
  reference (§10.2; *§11.2: 16 with one idiom rewrite, and clang 21 gives the same counts*), and the per-family program is ISA-invariant, so a held-out ISA (L1) is mostly derivable. **By
  I7, that part belongs to Hobbes, not Calvin.** The residual is:
  - the 7 guarded f16/bf16 families;
  - the composition helpers;
  - a non-finite policy the target does not define.

### 10.7 Candidate designs after round 2

- **D1 — Calvin is a closed-language author** (recommended by the routes pass).
  - **The pieces:** Hobbes owns an IR (VK-n) and its per-rule-validated lowering to each ISA. Calvin proposes IR
    programs, an enumerator first and a small model second, and an IR interpreter checks bulk cases inside the
    search.
  - **Nothing is said in C:** an invented name, a capability crossing or an out-of-span write cannot be expressed.
    Facts sit in the IR's primitives and lowering tables, regenerated per SHA.
  - **Training:** nothing at first, then at most a prior over IR programs, trained on public kernels.
  - **Validation:**
    1. Zero-spend: build VK-1's interpreter and lowering for the 21 families and G-diff them in the image. That is the
       deterministic floor.
    2. Re-target the evaluation to held-out *families*, starting with the 7 compiler-hard ones.
    3. Paid only for a residual: a 7B proposing IR at k = 10 for 7 families, a proposed $1 ceiling.
  - **Kill:** the enumerator matches the model (Calvin shrinks into Hobbes, an I7 win), or the IR cannot express the
    guards.
  - **Scope:** it changes "writes C" to "writes the IR, and Hobbes lowers it".
- **D2 — a verified synthesiser for the composition class** (F6 + F5). It searches the file's available intrinsics
  for helpers of up to about 13 calls, with a library or sampled prior. Zero-spend first: find `popcount_sse2`,
  `hsum128_ps` and the NaN-zero select from specs, on CPU in the image. Then a 7B prior on 31 helpers, a proposed $1
  ceiling.
- **D3 — a constrained structural decoder** (F1, SMC with compile and differential potentials, one call per unit).
  Zero-spend first: substitute nearest-legal names into the stored invented rows and re-grade, which bounds the
  mask. Then the 7B at k = 10, about $0.75 estimated, a proposed $2 ceiling. **Kill:** invented reaches 0 but pass
  rises less than +0.05. Mündler's +3.5% relative predicts this risk.
- **Whatever the design, the comparison is fixed.** Every Calvin figure sits beside three baselines:
  - the deterministic baseline (the compiler, SIMDe-style lowering);
  - Shanks under the same restrictions;
  - cost-of-pass.

  "Aligned" is read on planted impossible units. *§11.4: conflicting-spec units, not a mutated reference.*

**Still closed**, as §8 lists, plus:
- R10 as text shots: dominated by R12, and it reaches 15 of 37 same-width names;
- the Ledger Machine: CV-10;
- a from-scratch standard block for names: CV-7.

## 11. Round 3 (2026-09-29)

Max, 2026-09-29, on round 2's designs: send two agents to take the recommendations into the surrounding literature
before going further. Then, on the findings: *"good to write up and start round 3 with proposed routes."*
- **D1 pass:** portable-SIMD IRs and their lowering, lowering validation, LLMs writing into a DSL, equality
  saturation and enumeration from a scalar reference, and non-finite semantics across ISAs.
- **D2/D3 pass:** superoptimisation at 5–15 instructions, library learning on low-level code, a model as a prior
  over an enumerator, masked decoding with semantic potentials, measures of abstention and cheating, and
  differential inputs for float kernels.

Both passes skipped what §9 and §10 already cite. I then ran the two probes that could redirect the routes. Both
ran with no model call.

### 11.1 The literature (round 3)

Depth: **body** means the passage was read in the paper's text; **summary** means the fetch tool's HTML summary,
which must be re-read before an ADR leans on a figure; **snippet** means search text only.

| work | depth | the figure | what it does |
|---|---|---|---|
| Diospyros (ASPLOS 2021) | body | rewrites are correct over the reals; validation models "real arithmetic, rather than precise floating point"; up to about 4 min a kernel | equality saturation has no NaN semantics: not a source for the guarded kernels |
| Rake (ASPLOS 2022) | body | 21 integer benchmarks; mean compile 62 min; data movement is about 70% of synthesis time | the two-level shape (lift to a small IR, lower per instruction under SMT) is D1's; integer only |
| Crocus / VeriISLE (ASPLOS 2024) | body | 98 rules, 377 instantiations; 349 finish within 5 min; floating point and most SIMD are future work | prices D1's per-rule lowering validation for integers; no tool for FP vector rules |
| Minotaur (OOPSLA 2024, 2306.00229) | body, partly | concrete instructions with *symbolic constants*; 1 min Z3 per query; cut depth 4, because deeper cuts time out | a depth-bounded enumerate-then-verify loop; symbolic constants are how LUT operands are found |
| STAGG, guided tensor lifting (PLDI 2025, 2504.19705) | body | the LLM's candidates become a probabilistic grammar over a weighted-A* enumerator; 76 of 77 against C2TACO's 67; mean 3.19 s against 21.15 s | the precedent for D1's "enumerator first, model as a prior"; tensor algebra, not guarded FP |
| Li, Parsert, Polgreen, LLM-guided enumeration (2403.03997) | body | bit-vector SyGuS, 384 tasks: enumerator 142.7 → 196 with an LLM-derived pCFG (+30%); A* 253 → 262 (+3%) | a model's prior is worth most where the enumerator is weak |
| Gulwani et al., component-based synthesis (PLDI 2011) | body (MSR 2010 version) | 25 Hacker's Delight programs of 2–16 lines in 1–2,779 s; each component used once; "infeasible" reported in under 100 s on almost all | D2's 13-call scale is solvable *given the component multiset*, and a fast honest NULL comes free |
| Monitor-guided decoding (NeurIPS 2023, 2306.10763) | body | Java: compile rate +21.8–24.7% relative; no test-pass metric; 83% slower | D3's precedents report compile rate, not correctness |
| Khati et al., AST hallucination repair (2601.19106) | summary | nearest valid symbol by edit distance corrects 124 of 161; correctness not measured | the same |
| SimdBench (2507.15224) | body | pass@1, scalar vs SSE: Claude-3.5-Sonnet 81.3 vs 31.2, DeepSeek-R1 89.1 vs 65.2; undeclared identifier 40.7% of invalid cases overall, but 12–18% on SSE/AVX, where wrong result is 36–47% | intrinsics are much harder than scalar for every model; on x86, invention is the minority failure for frontier models |
| WebAssembly relaxed SIMD (spec overview) | summary | min/max with NaN or ±0 is implementation-defined; each environment fixes one projection per operator | a precedent for the 8 ISA-split golds: an op whose result set is per target |
| MLIR vector dialect (docs) | summary | reductions named by NaN policy: `maxnumf` treats NaN as missing, `maximumf` propagates it | NaN policy in the op's name, not a per-ISA parameter |
| Highway quick reference | summary | Min/Max with NaN is "target-specific and may change" | the same divergence, owned by a production layer |
| LLVM early-exit vectorization (PR #120567; LLVM 21) | summary | uncountable early exits vectorize from clang 21; not with FP reductions; one exit only | the reason the 14 of 21 needed a rerun (§11.2) |
| KernelBenchX (2605.04956) | summary | 0 of 30 on every quantization task; category explains about 3× the variance method does | a DSL did not lift numeric-contract tasks off zero |
| "The Correctness Illusion" (2606.20128) | summary | 9 of 9 seeded buggy kernels pass a fixed-shape allclose; a varied oracle catches 9 of 9 | the search oracle and the grading oracle must differ (§10.1) |
| CPPL (2605.17892) | summary | Verilog directly 0.725, raw CIRCT IR 0.500, a designed LLM-facing IR 0.800 (Opus 4.6) | a designed IR beats a raw one by a lot, and the general language by a little |
| SpecBench (2605.21384) | summary | reward-hacking gap = visible pass − held-out pass; weaker models have larger gaps | "small means safe" has evidence against it; copy the gap as the cheating measure |
| ImpossibleBench (2510.20270) | snippet | an abort option cuts GPT-5's cheating 54% → 9%, o3's 49% → 12% | report cheating with and without an abort option |
| LLM-Vectorizer (2406.04693) | summary | checksums passed 125 of 149; Alive2: 57 equivalent, 61 not, 31 inconclusive | confirms §10.3; the 31 unknowns are why integer kernels want SMT |
| Test-input generation for tensor programs (2606.27396, one author) | summary | boundary inputs 78% recall, 0% false positives; NaN-injected 94% recall, 73% false positives | the differential needs boundary sets; NaN injection only where the reference defines the policy |

Found nowhere, in either pass: a verified per-ISA lowering for FP vector ops (f16/bf16 conversion included); a
reported search time for a 7–13-op guarded FP kernel, or any SMT synthesis of a pshufb popcount; library learning
over intrinsics or assembly; a nearest-legal-name study that measures correctness; an LLM writing a *SIMD* IR; a
narrow-against-general comparison on abstention or cheating (§9's "unattempted" stands as far as both searched).

### 11.2 Probe 1: the compiler baseline on a current clang

§10.2's 14 of 21 came from clang 18, and LLVM 21 added early-exit vectorization. I re-ran the tally on clang 18 (the
image) and clang 21.1.8 (Fedora 43, in a throwaway container), `-O3` at the lattice's three ISA flag sets
(`build.ISA_FLAGS`), `--network=none`, over `distance-cpu.c` at `0c2223a`. A family counts when a loop in its
function (l2's `_impl`) carries a "vectorized loop" remark on every ISA.

| FP mode | clang 18 | clang 21 |
|---|---|---|
| strict | 3 / 21 | 3 / 21 |
| reassociation only (`-fassociative-math -fno-signed-zeros -fno-trapping-math`; NaN and inf kept) | **14 / 21** | **14 / 21** |
| `-ffast-math` (invalid here) | 16 / 21 | 16 / 21 |
| reassociation, with the `fmaf(a, b, c)` chains rewritten to `(a)*(b)+(c)` | **16 / 21** | **16 / 21** |

- **§10.2's count reproduces, and a current clang does not move it.** Every ISA agrees family by family.
- **The seven split two ways**, by clang 21's own remarks:
  - bf16 dot and cosine: "value that could not be identified as reduction". A chained `fmaf` (`llvm.fma`) is not a
    reduction the vectorizer knows. Rewritten as a multiply-add, both vectorize on both clangs. **That is an idiom,
    not a limit.** The rewrite gives up `fmaf`'s single rounding, which the reassociation mode has already given up.
  - The other five, f16 l2/l1/dot/cosine and bf16 l2: "Cannot vectorize early exit loop with reductions or
    recurrences", and for the two l2s "more than one early exit". clang 21 now sees the guard; it cannot vectorize a
    guard beside a reduction.
- **What it does to §10.6.** The deterministic floor is 16 of 21, not 14. The residual that is plausibly Calvin's is
  **five families, every one an any-lane inf exit beside a reduction** (two with LASSQ), plus the composition helpers
  and the non-finite policy. D1's kill condition, "the IR cannot express the guards", is aimed at exactly this set.
- **Limits.** A vectorized-loop remark is not a correct or fast kernel; nothing was run or graded. The fmaf rewrite is
  a text substitution over 20 call sites, checked by count, not by semantics.

### 11.3 Probe 2: nearest-legal substitution, re-graded (D3's bound)

§10.7 set D3's zero-spend step: put the nearest legal name into each stored invented row and re-grade, which
bounds what a mask can buy. I took D-11's 7B S-2h round 0 (the §5 rows: 127 units, greedy plus 10 samples, 1,397
rows). For each row graded `invented`, every invented name went to its nearest legal name by edit distance: the
ISA's available intrinsics (`d12/available-record.json`) for an intrinsic, and those plus the file's own names
(`e4.file_scope`) for a helper. The edited completions were replayed through `lattice e4 run --generator replay:`
in a scratch run dir, with no model call and $0.00 spent.

| | stored | substituted |
|---|---|---|
| rows graded `invented` | 482 | 49 |
| the 481 edited rows now | — | compile 283, wrong 123, invented 48, edge 11, **pass 16** |
| sampled pass rate (samples 1–10) | 0.412 | 0.424 (**+0.012**) |
| units passing at greedy | 58 | 59 |
| units passing in any of 11 | 78 | 81 |
| units where every sample is `invented` | 22 | 2 |

- **The kill rule fires.** Invented falls about 90% and pass rises +0.012, against D3's +0.05 bar. The 916 unedited
  rows re-grade to the same class, all 916, so the replay is deterministic.
- **What a nearest legal name is.** `_mm_hadd_pd` → `_mm_add_pd`, `_mm_cvtph_ps` → `_mm_cvtpd_ps`,
  `_mm_cvtepi16_epi32` → `_mm_cvtpd_epi32`: legal, near and wrong, most of them now type errors. This is grammar-
  aligned decoding's distortion, shown on real rows, where round 2 found the paper did not show it (§10.3).
- **Where the 16 passes came from.** 9 are file-local helper names missing a suffix (`abs_diff_epu8` →
  `abs_diff_epu8_512`, `dot_epi8` → `dot_epi8_512`, `hsum512_epi32` → `hsum512_epu32`). 7 are intrinsic
  spellings (`_mm512_extractf128_ps` → `_mm512_extractf32x8_ps`). So half the gain is the ledger's own names, a
  positive mapping, which is the one kind of fact a student has acted on (CV-19's init).
- **Limits.**
  - Edit distance stands in for a mask; an SMC sampler with compile and differential potentials (§10.3) would choose
    by more than spelling.
  - 48 edited rows still grade `invented`. Some substitutes are names the grader still rejects (for example
    `_mm_insert_pi16`, an MMX name), and some rows carry invented names the first grade did not list.
  - One arm, one round, one size.

### 11.4 What round 3 changes

- **The residual is smaller and sharper.** 16 of 21 families are the compiler's (reassociation plus one mechanical
  idiom rewrite). What is left is five guarded families (an any-lane inf exit beside a reduction, two with LASSQ),
  the composition helpers, and the non-finite policy.
- **D3 as a stand-alone design is closed** by its own kill rule (§11.3), and the literature agrees: every masked-
  decoding precedent reports compile rate, not correctness (MGD, Khati), and Mündler's +3.5% relative is the only
  functional figure. A mask survives only as a component where invention cannot be expressed anyway, which is D1.
- **D2 is feasible only with the component multiset given.** Component-based synthesis solves 10–16-op programs
  in minutes to about 46 minutes when told which components to use once; the gold bodies alone reach 148 distinct intrinsics, and the available set
  is larger. Its "infeasible
  in under 100 s" is a free honest NULL.
- **D1 holds, and the literature names its parts.** STAGG is the enumerator-with-a-prior precedent; Rake the two-
  level lift-and-lower; Crocus the per-rule validation cost for integer rules; MLIR and WebAssembly the naming of
  NaN policy per op. Its open risk is the FP lowering, where no tool exists. For f16 and bf16, an exhaustive check
  of every input is complete and cheap on CPU.
- **The "aligned" test in §10.7 was ill-formed.** A mutated scalar reference still has a correct vector kernel (the
  mutated function's), and G-diff would pass it. An impossible unit needs two specs that disagree (ImpossibleBench's
  conflicting variant: the reference plus a contract or example it contradicts). Cheating is passing by special-
  casing. Read it with and without an abort option, and read SpecBench's visible − held-out gap beside it.
- **"Small means safe" has evidence against it** (SpecBench: weaker models, larger gaps). Narrowness is not a proxy
  for alignment (§4), and round 3 adds a measured instance.

### 11.5 Proposed routes (for Max)

- **Route 1 (recommended): D1, with D2's synthesiser as its enumerator.** Calvin is a closed-language author for the
  residual; Hobbes owns the IR, the lowering and the non-finite naming. Order of work, zero-spend until the last step:
  1. VK-1's interpreter and lowering for the 16 compiler-vectorizable families, G-diffed in the image, with f16/bf16
     lowerings checked exhaustively. That is the deterministic floor, and Hobbes's by I7.
  2. The 8 ISA-split golds renamed per op (MLIR/WebAssembly style), graded as a set of allowed results. It says
     whether VK-1 needs a per-ISA parameter at all.
  3. A Brahma-style CEGIS in Z3 for `popcount_sse2`, `hsum128_ps` and the NaN-to-zero select: the true component
     multiset, then one or two larger, then one component removed (time to "infeasible"). Symbolic constants for
     LUTs (Minotaur).
  4. The enumerator over VK-1 on the five guarded families, at a 60 s and a 10 min cap: the depth it solves at,
     or the kill ("the IR cannot express the guards").
  5. Only for what 4 leaves: a 7B as a STAGG-style prior over the enumerator, one call per unit, a proposed $1
     ceiling. Kill: the enumerator alone matches it.

  Every figure sits beside the compiler, Shanks under the same restrictions, and cost-of-pass; "aligned" is read on
  conflicting-spec units with and without an abort option. Scope: "writes C" becomes "writes VK-n; Hobbes lowers it".
- **Route 2: D2 alone, for the composition class.** Keeps "writes C". Steps 3 above, then a 7B prior on the 31
  helpers under a $1 ceiling. Smaller, and it leaves the five guarded families to the compiler's limit.
- **Route 3: Calvin stops at the floor.** Record that the compiler covers 16 of 21 families and the mask buys +0.012,
  and return the time to extraction. §10.6's case against is stronger after round 3, not weaker.

**Closed by round 3:** D3 as a stand-alone design (§11.3); a mutated scalar reference as the impossible unit
(§11.4).

**Still zero-spend and open, whichever route:** the differential's input sets (random, boundary, NaN/inf/subnormal,
adversarial: which kernels each separates that random inputs do not), and a bounded SMT check of the integer and bit
helpers, where checksums missed 37 in LLM-Vectorizer.

**Scripts and records.** Probe 1's tally and probe 2's substitution, replay driver and reader are in this session's
scratchpad, not the tree; probe 2's run dirs likewise. Neither probe is registered (§11 is design review).

## 12. Route 1, session 1 (2026-09-29): does a deterministic search close the residual?

Max, on the reordered Route 1 (§11.5, with the tests that can kill first): *"good to start the session now."* Zero
spend, no model call. The pre-registration, tools, outputs and results are off-tree in
`~/.hobbes/bench/calvin-lattice/route1-s1/` (`PREREG.md`, written before any run; `RESULTS.md`).
- **Part A:** an enumerator over VK-g, a closed vector-kernel language defined in the pre-registration, on the five
  guarded families.
  - VK-g's one form: terms over the lanes, an accumulator precision, a skip predicate, an any-lane exit predicate
    with its exit value, and the reference's own scalar epilogues.
  - Two readings per family. *Expressible*: every case seen. *Solved*: the search sees bulk n ≤ 256 and four
    specials at n = 17, and is graded on the rest.
- **Part B:** Z3 component-based synthesis (Gulwani et al.'s encoding, CEGIS) of the three helpers, under four
  component multisets.
- **Reference:** the scalar kernel from the image's clang 18 build, compared as G-diff compares.

**Three deviations, each made before the reading it affects** (RESULTS.md):
1. A 5-node term cap, set while coding, excluded (x−y)². Every family was re-read at 9 nodes, and the 5-node runs are
   kept.
2. Two performance fixes, with no change to the language.
3. Supplementary swapped-input rows, outside the decision.

| family | expressible | solved (split oracle) |
|---|---|---|
| f16 l2 | yes, 11.5 s | yes, 5.5 s, **with no exit** |
| f16 l1 | yes, 6.5 s | yes, 5.0 s, **with no exit** |
| f16 dot | yes, 7.7 s | no: 44/47; the exit's sign is wrong |
| f16 cosine | yes, 3.6 s | yes, 3.1 s |
| bf16 l2 | yes, 55 s (`f64(x−y)·(x−y)`) | no: 88/94; f32 overflows on `large` |

| helper | true multiset | +1, +2 | one removed | post-check |
|---|---|---|---|---|
| NaN-to-zero select | 0.02 s | 0.03 s, 0.08 s | infeasible, 0.00 s | bit-exact on 400,000 lanes |
| `hsum128_ps` | 0.9 s | 0.8 s, 21 s | infeasible, 0.3 s | 89.4% bit-exact, 99.82% within tolerance; the rest are inf/NaN pairings |
| `popcount_sse2` | **timeout** at 10 min | timeout | timeout | the encoding admits the gold (proved on 128 bits) |

**The rule's verdict is C, partial.** All five are expressible, so D1 is not killed. f16 dot, bf16 l2 and
`popcount_sse2` are unsolved, and the pre-registration named those as the paid step's target.

**The verdict does not recommend the paid step for two of the three.**
- **f16 dot and bf16 l2 fail on identifiability, not search.** Their programs were found in about 5 s, and they are
  the smallest ones consistent with the seen cases. The semantics the held-out cases pin are written in the scalar
  reference's text: the exit's sign, and the double accumulation.
- **The deterministic answer is to lift the scalar loop into VK-g,** not to search I/O. A model prior over the
  enumerator targets search, and it cannot recover what the oracle never shows.
- **Only popcount is search-hard.** It is a textbook sequence (Hacker's Delight; SIMDe carries it), so a library
  lookup is a deterministic alternative to a model prior.

**What the programs showed:**
- **In f16 l1 and l2 the reference's early exit is subsumed by IEEE propagation:** an inf term makes the sum inf,
  and inf − inf is NaN. That is where the compiler's "early exit with reductions" refusal (§11.2) is beside the point.
- **Every split-oracle program masks only `isnan(x)` and guards only `isinf(x)`.**

**An instrument finding, proposed for the register, not yet registered:**
- G-diff's specials write inf and NaN only into `a`, or into both, and never mix a same-sign inf pair with a
  mismatched one.
- So a float body that masks one side, or drops the exit, passes G-diff. The swapped rows catch it: 6/12 to 20/24 pass
  for the split programs.
- This bears on every float grade since E0, CV-11 included.

**What this does to the routes.**
- **Route 1 continues, in a different form.** The next step is a deterministic *lifter*, which reads the scalar
  loop's guards, exits and precisions into VK-g, measured on the same five families. It is not the paid prior run.
- **Popcount is the one open search case.** A library lookup comes before a model.
- **If the lifter closes the five, the residual on this lattice is Hobbes's by I7, and Calvin has no job here** (rule
  A's reading, reached one step later).
- **Not measured:** any lowering to an ISA, speed, a second target, and the lattice driver's own bytes.

## 13. Route 1, session 2 (2026-09-29): a deterministic lifter, and popcount by lookup

Max, on §12's routes: *"good to proceed with recommended."* Zero spend, no model call. Pre-registered before any run
(`route1-s1/PREREG-s2.md`); results in `route1-s1/RESULTS-s2.md`.

**Part C, the lifter.**
- **How it works:** tree-sitter-c reads each family's tail loop in `distance-cpu.c` and executes it symbolically, statement by statement, into
  guarded map-reduce: skips, exits under "not skipped so far", and accumulations.
- **Its output:** two-pass C. An OR of the exit condition over all lanes; then, only if it is set, a scalar scan
  that returns the first exit. After that, select-masked reductions and the reference's own post-loop code.
- **Its rule table has two entries,** written before the run: header calls pass through, and `LASSQ_UPDATE` becomes
  a plain double sum of squares (exact up to rounding, since |e| < 2^128 for f16 and bf16).
- **Anything else refuses.**

**Part D, the lookup.** The target's NEON sibling computes the byte popcount with `vcntq_u8`. SIMDe, vendored in the
40-repo draw, maps `vcntq_u8` to x86, and its SSE2 branch is the answer.

| | result |
|---|---|
| lifted | **5 of 5**, none refused |
| graded rows (seen, held out, swapped, and 112 new mixed rows: a same-sign and a mismatched inf pair in one vector, inf × 0, NaN beside inf, bf16 overflow) | **609 of 609 pass, in each of 3 builds**: `-O2`; `-O3` with reassociation; the same at the avx512 flags under clang 21, where every hot loop vectorizes |
| vectorization (read, not decided) | every §11.2 "early exit with reductions" refusal is gone. On sse2 and avx2 the f16 reductions are declined by the cost model over a software f16→f32 conversion, not by legality |
| popcount by lookup | SIMDe's SSE2 `vcntq_u8` = the gold `popcount_sse2` on all 65,536 16-bit patterns (exhaustive); the same sequence |

**The rule's verdict: closed.** The residual §11 named is deterministic on this lattice:
- 16 families come from the compiler;
- the 5 guarded families are lifted, then compiled;
- the NaN-to-zero select and `hsum128_ps` come from the solver (§12), and popcount from the lookup.

By I7 all of it is Hobbes's. **Calvin has no job left on sqlite-vector at `0c2223a`**; Route 3, reached by evidence
for this target.

**Limits:**
- **The lifter's coverage is partly by construction:** it was written after reading these five loops. It refuses
  anything else, and it is untested on another target.
- **Not measured:** speed; an intrinsic lowering where the compiler declines (sse2 and avx2 f16); the other
  composition helpers, needed only if the output must be hand-shaped intrinsics.
- **Non-finite answers:** the lifted kernels follow the scalar reference, and where the ISA golds differ (§10.2) that
  is the target's non-finite policy.

**What it leaves open:**
- **A second target.** Does the lift-then-compile floor hold where the kernels are not a scalar loop with guards?
  That is also Kapoor et al.'s out-of-distribution requirement (§10.5).
- **The G-diff coverage finding** (§12), still proposed and not registered.
