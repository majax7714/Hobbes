# Calvin — the reassessment of its design

**Status:** round 1 recorded (2026-09-28). Round 2 was sent with round 1's findings, and its results land below
when they return · **Type:** design review. It runs nothing and spends nothing · **Why:** Max, 2026-09-28: *"calvin
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
| **In the weights** (training) | A 300-step LoRA sharpens reading named neighbours and adds no skill (CV-15). Learned typing collapses (CV-10) | Narrow code fine-tuning causes broad misalignment (Betley et al.). It is strongest in Qwen2.5-Coder-32B-Instruct, the family of the lattice's own 32B, and a rank-1 LoRA is enough (Turner et al.). Capability filtered from pretraining returns when the context supplies it (Deep Ignorance). SFT memorises where RL generalises (Chu et al.) |
| **In the decoder or output language** | Never run | Type-constrained decoding more than halves compile errors (Mündler et al.). Dependency-constrained decoding cuts invented APIs by about 70% (MARIN). *Hazard:* a plain mask distorts the distribution and turns an invented name into the nearest legal one (grammar-aligned decoding), so it needs a proper sampler (sequential Monte Carlo, Loula et al.), and the differential stays the judge |
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
- **The strongest evidence for the thesis** is SuperCoder: Qwen2.5-Coder-7B with RL on one low-level language
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

- **A — "a proposer in a closed world"** (recommended in round 1).
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

## 10. Round 2

Sent 2026-09-28 with round 1's findings and ADR-152's framing. It has two passes, routes and literature, and its
record lands here.
