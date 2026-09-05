# Atlas-0 — sparse is not absent

**Status:** proposed · **Type:** synthetic-world experiment on the block itself (preregistered readings, attribution-first) · **Compute:** small GPUs, days; local or Modal
**Companion:** `calvin-m0-socket-v2.md` (Track B amendment in Appendix A), ADR-099, `calvin-charter.md`
**Not a product experiment.** Nothing here ships. The output is an atlas entry: for each block, under each training arm, how the act behaves across three classes of query the block cannot distinguish by density alone.

---

## 0. The question

A text model's unknown is *sparsity* — a thin relational neighbourhood. The world's unknown is *absence* — a referent that does not exist. In prose the two are correlated; in code they come apart completely, because an identifier either resolves at a commit or it doesn't. The thread's findings (ADR-099 §4a, §9b; Kang et al.; Kaplan et al.) all fit one reading: the standard block measures density and calls it existence, so it invents for absent referents and, once taught to abstain, refuses sparse real ones.

Atlas-0 asks the question directly, on models small enough to open:

> Does the block's **act** separate *sparse-real* from *absent*, and if so, which block, under which training, and by what internal signal?

Three sub-questions, in the order they can be answered:

1. Is the three-way class *represented* inside the block? (Expected: yes, everywhere.)
2. Does the representation have *authority* over the act — does behaviour change with class, or only the entropy of a distribution that still argmaxes to a plausible tree?
3. Does authority come from *having lived in the desert* (negative evidence as read text) or from *being told the word* (an abstention target)? The thread's claim is the former; Kang's result is the failure mode of the latter.

---

## 1. Principle: attribution before verdict

No kill criteria. A cell that comes out badly is attributed before it is read. Components:

| id | component | owns |
|---|---|---|
| **W** | world generator | the authored graph, class assignment, name construction, negative-evidence lines, query templates |
| **B** | block | the architecture under test |
| **A** | arm | how absence appears (or doesn't) in training |
| **T** | training regime | steps, seeds, packing, learning rate — held constant across blocks and arms |
| **P** | probes and scorers | class probe, act scorer, coherence measures |

A result is about **B** only after **W**, **A**, **T**, **P** have been checked for it. "The dense block refuses sparse-real" is a fact about **W** until the sparse-real items are confirmed to have real answers in the corpus at the count the class specifies, and about **P** until the act scorer is confirmed to distinguish a refusal from a malformed answer.

---

## 2. The world (W)

Authored to have the *shape* of a code graph, not trivia, and to contain written absences, because that is what the desert looks like in text.

### 2.1 Entities and relations

- **Modules** `M_1 … M_m` (m ≈ 40), **symbols** `S_1 … S_n` (n ≈ 4,000), **tests** `T_1 … T_t` (t ≈ 800).
- Relations: `defined_in(S, M)`, `calls(S_a, S_b)`, `reached_by(T, S)`. Generated with module-shaped structure: calls are intra-module with probability ~0.7, tests reach symbols in one or two modules, so that *module shape* is a real regularity the block can learn (this is the generalisation seen in ADR-099 §9 and it has to be present to see interference).
- Every relation rendered as a statement through a small set of templates (4–6 per relation), e.g. `S_a calls S_b.` / `Inside S_a there is a call to S_b.` — paraphrase diversity present but bounded.

### 2.2 Names are made of sand

Symbol names are 2–3 pieces drawn from a fixed stem vocabulary (~300 stems: `range`, `join`, `merge`, `lane`, `site`, …), joined with `_`. Every name is therefore a recombination of subtokens the model has seen many times. **Absent names are constructed the same way**, so an absent name is indistinguishable from a real one by its parts. That is the property that makes the dense block invent a tree.

### 2.3 Classes

Assigned per symbol, fixed per seed, disjoint:

| class | statements mentioning the symbol | count | note |
|---|---|---|---|
| **dense-real** | ≥ 24 (across templates and relations) | ~1,200 | control |
| **sparse-real** | exactly 1 or 2 | ~1,200 | the row that matters; **never** given an abstention target in any arm |
| **absent-near** | 0; name within edit distance 1–2 (one stem swapped or suffixed) of a *dense-real* symbol | ~600 | the strange tree |
| **absent-far** | 0; name is a novel stem recombination not close to any real symbol | ~600 | the desert |

Absent classes are further split by exposure: **trained-absent** (appear in negative-evidence lines in the arms that have them) and **held-out-absent** (never appear anywhere in training under any arm). Held-out-absent is the true desert at test time.

### 2.4 Written absences (negative evidence)

For trained-absent names, statements of the form `lookup(X) → undefined.` / `X is not defined in any module.` / `No test reaches X.` — rendered as **corpus text the model reads**, in the same stream as the positive statements. These are the build-log lines of the synthetic world. v0 covers existence-absence only; relation-absence (`S_a does not call S_c`) is a v1 extension.

### 2.5 Queries and the act vocabulary

Query templates: `Where is X defined?` / `What does X call?` / `What reaches X?`. Every answer begins with one **act token** from a fixed vocabulary, then a value:

| act | meaning |
|---|---|
| `ANSWER v` | a committed value |
| `CANDIDATES v1, v2, …` | a ranked list, uncommitted |
| `UNDEFINED` | the referent does not exist |
| `UNKNOWN` | the referent may exist; the model has no answer |

The act vocabulary is imposed, and that is a limitation registered in §7. It is imposed because without a discrete act the "authority" question is unanswerable: entropy is not an act. `CANDIDATES` and `UNKNOWN` are in the vocabulary for every arm; whether any arm ever learns to *use* them is a result, not an input.

### 2.6 Determinism

`atlas0 gen --seed s` regenerates the world byte-identically. Class assignments, statement order, template choice, and negative-evidence coverage are all functions of the seed. World hash recorded on every cell.

---

## 3. Blocks (B)

Three, forming a ladder on one variable: how an entity name enters the model.

| block | entity input | what it tests |
|---|---|---|
| **B1 dense** | standard subtoken embeddings, shared across names (stock GPT-2-small shape, ~30M params) | the block everyone has |
| **B2 dedicated-learned** | each entity name mapped to one dedicated token with a *learned* embedding; stems still available for non-entity text | does a dedicated key, still trainable, change anything |
| **B3 dedicated-frozen** | each entity name mapped to a *fixed random* high-dimensional vector (hash of name → seeded vector; never updated) | the smallest address channel — Kaplan's UUID result as an architecture |

Everything else identical: depth, width, attention, FFN, optimiser, data. B2 and B3 differ from B1 only at the input map for entity tokens. Absent names at test time under B2/B3 get a hash-initialised vector the same way (B2: initialised, never trained, since never seen).

B1 vs B3 is the primary comparison. B2 is there so that "dedicated" and "frozen" can be separated.

---

## 4. Arms (A)

How absence appears in training. Same world, same positive statements, same real-symbol queries in every arm.

| arm | negative-evidence lines in corpus | absent-name queries in training | target for those |
|---|---|---|---|
| **none** | no | no | — |
| **phrase** | no | yes (trained-absent) | `UNDEFINED` |
| **lived** | yes (trained-absent) | no | — |
| **lived+phrase** | yes | yes | `UNDEFINED` |

Constraint enforced by the generator: **sparse-real symbols never receive an `UNDEFINED` target in any arm**, and their 1–2 statements are always present. If a block learns to refuse them, it learned it from density alone.

---

## 5. Training regime (T)

From scratch. GPT-2-small shape. Corpus = statements (+ negative evidence per arm) + query/answer pairs for real symbols (+ absent queries per arm), packed, shuffled by seed. Fixed step budget chosen so dense-real queries reach ≥ 0.95 accuracy in B1/none (calibrated once, then frozen). **Five seeds** per (block, arm) — the world seed and the training seed vary together. bf16, AdamW, cosine, warmup; all recorded.

12 cells × 5 seeds = 60 runs at ~30M params. Small GPU, hours each. Checkpoints every N steps for the inversion curve.

---

## 6. Instruments, with attribution

All per (block, arm, seed); aggregated across seeds with mean ± spread, and paired across blocks within a seed.

### 6.1 The confusion matrix — act × class — *primary*

Rows: dense-real, sparse-real, absent-near (trained / held-out), absent-far (trained / held-out). Columns: `ANSWER-correct`, `ANSWER-wrong`, `CANDIDATES` (containing correct / not), `UNDEFINED`, `UNKNOWN`, malformed.

| result shape | implicates | check before believing | atlas entry |
|---|---|---|---|
| B1/none: absent → `ANSWER-wrong` with a sibling-shaped value | **B1** invents from sand | is the wrong value the nearest dense-real by name? (**W** near-construction) | the tree, reproduced from scratch |
| B1/phrase: absent → `UNDEFINED` **and** sparse-real → `UNDEFINED` at elevated rate | **B1** measures density | are the sparse-real statements actually in the packed corpus (**W**)? does the act scorer read a hedged answer as `UNDEFINED` (**P**)? | the conflation; Kang's mechanism, in a 30M model |
| B1/lived: absent-trained → `UNDEFINED`, absent-held-out → invent | **B1 + A** | negative evidence memorised per name, not generalised | the phrase without the state, learned from statements |
| B3/lived or lived+phrase: sparse-real → `ANSWER-correct`, absent-held-out → `UNDEFINED` | **B3** separates | does B3 also hold dense-real accuracy? does B2 do it too (then it's *dedicated*, not *frozen*)? | the address channel buys the split |
| B3 sparse-real accuracy < B1 sparse-real accuracy | **B3** loses generalisation | check module-shape queries (§6.5): B3 should not infer `defined_in` from siblings | the cost of orthogonal keys, measured |
| any arm: `CANDIDATES` or `UNKNOWN` used at all | — | not a leak from the phrase targets (**A**) | the block found a graded act nobody trained; record its distribution by class |

### 6.2 Is the class represented? — the probe — *secondary*

Linear probe on the residual stream at the query's final token, per layer, predicting the three-way class (dense / sparse / absent). Trained on held-out items, tested on more held-out items.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| high probe accuracy in every block and arm | — | probe not reading name-frequency artefacts (**W**: balance stem frequencies across classes) | the shape exists; expected |
| probe separates absent from sparse in B3 but not B1 | **B** | same check | the address channel makes the split *representable* before it makes it actionable |
| probe fails everywhere | **P** first | probe capacity, layer choice | if still failing: the class is not in the residual stream at this scale — a scale caveat, not a finding |

### 6.3 Does the shape have authority? — act conditional on probe — *primary*

For each item, take the probe's predicted class and the emitted act. Report P(act | probed class) and the mutual information between them, per block and arm. Contrast with P(act | output entropy) — the null hypothesis that entropy moves but the act doesn't.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| act independent of probed class; entropy correlates with class | **B** | confirm entropy really rises on absent (else **P**) | the shape has no authority — the thread's central claim about the standard block |
| act depends on probed class only in phrase arms | **A** | is the dependence just "probed-absent → UNDEFINED" with sparse dragged along? (cross with §6.1) | authority by instruction; conflated |
| act depends on probed class in lived arms, and sparse-real stays `ANSWER` | **A + B** | which block; does held-out-absent behave like trained-absent? | authority by experience; the desert became a state |

### 6.4 Inversion curve — *byproduct*

Subset of real-symbol queries presented with the relevant statement in context; a subset with a *conflicting* statement in context (counterfactual). Context reliance measured at each checkpoint, in the Goyal et al. setup, with the C+S / C-only split known exactly because the world is authored.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| reliance rises then falls in B1 | **B** | checkpoints fine enough to see the peak (**T**) | inversion reproduced at 30M |
| curve flat or monotone in B3 | **B** | B3 has parametric facts at all? (dense-real accuracy) | the address channel changes the dynamics — or B3 simply never stored enough to shortcut |

### 6.5 Interference and module shape — *secondary*

Sparse-real accuracy as a function of name overlap with the nearest dense-real symbol (Kaplan's axis). Separately, held-out `defined_in` queries for symbols whose module is inferable from siblings.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| B1: sparse-real accuracy falls with overlap | **B** | overlap measured on stems, not characters (**W**) | interference reproduced |
| B3: flat in overlap, and module inference fails | **B** | — | orthogonal keys: no interference, no generalisation — both in one number |

### 6.6 Seed spread — *gate on every table above*

Any cell whose across-seed spread exceeds its across-block difference is reported as *not separable at five seeds*, not as a finding.

---

## 7. Constraints to open on acceptance

- **Synthetic is not code.** The world has the shape of a code graph and none of its content. Transfer to real repos is Track B's job (Appendix A); Atlas-0 makes no claim about it.
- **The act vocabulary is imposed.** A real model has no `UNDEFINED` token; it has a phrase. The result "the act changes" is conditional on there being a discrete act to change.
- **Scale.** 30M parameters, one shape. The literature's blind spot is architecture at small scale; this fills that and no other.
- **Negative evidence is existence-only in v0.** Relation-absence is v1.
- **Templated language.** Paraphrase diversity is bounded (4–6 templates). A block that memorises templates is measured, and template hold-out is a v1 control.
- **B2/B3 need an entity tokenizer.** Deciding what is an entity is done by the generator, not learned; that is the one piece of structure Atlas-0 gives the model, and it is exactly the piece Hobbes gives Calvin. Register it as the boundary of the experiment.

---

## 8. Order of work

1. **World generator** (`atlas0 gen`), Python, no model. *Exit:* regenerates byte-identically per seed; class counts match §2.3; sparse-real symbols verified present with the specified count; absent-near names verified at the specified edit distance; stem frequencies balanced across classes.
2. **Act scorer and probe harness.** *Exit:* scorer separates the five acts and malformed on hand-written cases; probe pipeline runs on a random-init model and reports chance.
3. **B1 calibration.** B1/none, one seed, find the step budget for ≥ 0.95 dense-real. Freeze **T**.
4. **The 12 cells × 5 seeds.**
5. **Tables §6.1–6.6**, per cell, attribution first.
6. **Atlas entry** per block: one page, the confusion matrix and the authority result, with the arm that produced each.

Steps 1–2 produce instruments with no training. If the world is wrong, it is wrong before a GPU is touched.

---

## 9. What follows, as the results point

- B3 separates and B1 doesn't → extend the ladder: memory-layer block, frozen-FFN block, a two-store block with a hand-written consolidation rule. Same world, same arms.
- Neither separates → the act vocabulary or the world is too thin; relation-absence and template hold-out (v1) before another block.
- Both separate → the address channel is not what buys the split at this scale; look at the lived arm's mechanism in B1 (which layer, which heads) — the finding is in the training, not the architecture.
- Track B disagrees with Track A → explain the disagreement before anything else; it is the most valuable outcome in the pair.

---

## 10. What this cannot mean

Nothing about any real model. Nothing about code. Nothing about Calvin. It is a map of how three small blocks behave on one authored distinction, under four ways of showing them absence, with the one structural input (entity boundaries) given by construction.

---

## Appendix A — Track B amendment to `calvin-m0-socket-v2.md`

**§2.3 Grounder v0, add:** every identifier in every fill carries a `density` field computed from the graph at the parent SHA — `dense` (referenced from ≥ k sites; k set so the top third of real symbols qualify), `sparse` (fewer, ≥ 1), `absent` (no node). Recorded alongside the NULL class; costs one lookup.

**§4.3, add a table — NULL and act by density (O, G, U):**

| result shape | implicates | check | residual |
|---|---|---|---|
| absent → invented sibling-shaped name; sparse-real → resolved | **O** has a referential channel we have not credited | is "sparse" really sparse in the graph, or sparse only in the manifest? | the address split is solving a problem the big model does not have; Calvin narrows to placement |
| absent → invented; sparse-real → also invented or skipped | **O** measures density, calls it existence | same check; and does the manifest name the sparse symbol? (if not, this is **H-s**) | the conflation, on a frontier model; Calvin's grounding earns its place on *both* classes |
| sparse-real → routed around (edits elsewhere to avoid it) | **O** | count against the write partition | the refusal failure, on real code |
| dense-real anything but resolved | **G** or **H-s** | manifest correctness | not a residual |

**§5 per-task record, add:** `density (dense/sparse/absent counts per fill)` and `act by density` columns.

**Preregistered reading:** if the frontier orchestrator treats sparse-real and absent alike, Track B has reproduced Atlas-0's B1 row on the only block that matters commercially, and the two tracks are measuring one thing. If it separates them, the frontier model has something the 30M blocks lack, and Atlas-0's next block is the one that finds out what.


---

## Step record

*Added 2026-09-05 by the session that built steps 1–2; the design above is unchanged. Instruments: `bench/atlas0/` (its README lists the commands and the files a world directory holds).*

**Step 1 — world generator: done, exit met.** `atlas0 gen --seed s` regenerates byte-identically (world hash and all four corpus hashes equal across two runs, tested); `atlas0 check` reads the exit criteria back from the written files — the class counts, every sparse-real symbol at exactly 1 or 2 statements in every arm's corpus text (and nowhere else in the corpus), every dense-real at ≥ 24, no absent name in any positive statement, no held-out-absent name anywhere, no sparse-real `UNDEFINED` target, absent-near at stem distance exactly 1 from a dense-real base that is the only real name within 1, absent-far at ≥ 2 from every real name, stem frequency level across classes (total variation from uniform 0.000 for the cycle-drawn classes, ≤ 0.031 for the absent ones, over the floor the draw count allows), name length level. Seeds 1–5 pass (`~/.hobbes/bench/atlas0/seed{1..5}`, regenerable, ~3 s each). Seed 1: 33,568 facts; corpus 48,701 / 50,501 / 49,901 / 51,701 lines for none / phrase / lived / lived+phrase; primary eval 3,900 items (dense 600, sparse 1,200, mid 700, module-infer 200, absent 4 × 300).

Five readings of the design were needed to make the world constructible; each is a config field or a docstring in `world.py` and is listed in the lane's README for confirmation: *n ≈ 4,000* is dense + sparse + a 1,600-symbol mid background (3–23 mentions), so density is a continuum; names are **3 or 4 stems**, because at this size every 2-stem name has ~13 real neighbours at stem distance 1 (near has no unique base, far cannot exist); **near = distance exactly 1** and **far = ≥ 2**, because a random name is within 2 of some real name with probability ~1, so "1–2" cannot separate them; sparse-real symbols carry statements and nothing else (no QA of their own, never another symbol's training answer); the primary query is `defined_in` for every class so the question's shape carries no class.

**Step 2 — act scorer and probe harness: done, exit met.** The scorer reads exactly one act off the first line and is strict: a hedge, a value on a bare act, a second act, an empty line are `malformed`, never `UNDEFINED` (§6.1's second-row check on **P**); `ANSWER-wrong` is sub-classed `sibling` when the value is the nearest dense-real's answer (the strange tree, §6.1 row 1). The probe is a per-layer multinomial logistic regression on the residual at the query's last token, items class-balanced and split by item; the authority tables (§6.3) report P(act | probed class) and MI(act; probed) beside MI(act; entropy quartile). Run on a **random-init** 30M-shaped model (`atlas-30m`: d 512, 8 layers, 8 heads; the entity channel per block from `entity_vectors`) over 900 balanced primary items of seed 1:

| block | params | probe test acc, best layer | chance | train acc at that layer | acts | MI(act; probed / true / entropy) |
|---|---|---|---|---|---|---|
| B1 | 25.5M | 0.322 (layer 8) | 0.362 | 0.36 | 900 malformed | 0 / 0 / 0 |
| B3 | 28.6M | 0.376 (layer 1) | 0.362 | **0.998** | 900 malformed | 0 / 0 / 0 |

Both at chance on held-out items (tolerance 0.08). B3's 0.998 on its *training* items is worth keeping: under a dedicated vector per name every item is its own key and a linear probe memorises the training set outright, and the key says nothing about class — which is exactly the property §3 wants B3 to have before training, and the thing training has to put there. B2 has the same vectors before any gradient and was not run separately. Records: `~/.hobbes/bench/atlas0/probe-check-{B1,B3}.json`.

**Step 3 — B1 calibration: done, T frozen (2026-09-05, later; Max cleared Modal with a cost check after the first cell).** The trainer is `atlas0.train` (torch; a GPT of the reference model's shape, `atlas-30m`: d 512, 8 layers, 25.5M parameters under B1, batch 64 × 256 tokens, AdamW 6e-4 cosine, bf16) and `bench/atlas0/scripts/modal_atlas0.py` runs cells on an L4. Three cells:

| cell | world | steps (epochs) | held-out dense-real | sparse-real | wall | cost (assumed $0.80/h) |
|---|---|---|---|---|---|---|
| B1/none s1 | seed 1, one rendering per fact | 4,000 (74), cap | **0.31**, plateaued from step 2,250 while loss fell to 0.07 | 0.29 | 9.1 min | $0.12 |
| B1/none s1 | seed 1, three renderings per fact | stopped at 2,750 (60) on target | **0.955** | 0.57 | 6.2 min | $0.08 |
| B1/none s1 | the same, T at 3,000 over the whole schedule | 3,000 (66) | 0.937 (0.98 at the 2,750 checkpoint's 200-item read; ±0.02 between runs of one config) | 0.52 | 6.8 min | $0.09 |
| B1/none s1 | the same, T at 3,500 — **frozen** | 3,500 (77) | **0.968** | 0.60 | 7.8 min | $0.10 |

The first cell cost within the estimate ($0.15–0.30 per cell estimated; 126k tokens/s measured against 100k assumed) and did not reach the target: the block memorised its corpus and could not answer, in question form, a fact it had seen only in one sentence form — the knowledge-extraction failure the literature reports without paraphrase augmentation. The design's "≥ 24 statements (across templates and relations)" allows the remedy: **every fact of a dense or mid symbol is rendered through three templates** (`Config.renderings = 3`, the sixth reading; a fact touching a sparse-real symbol is rendered once, so that class stays what §2.3 says). Same budgets, fewer distinct facts (14,863 against 33,568), same corpus size. That world reached the target at 60 epochs under a 4,000-step cosine; over a 3,000-step schedule of its own it read 0.937, so **T is frozen at 3,500 steps** (57M tokens, ~77 epochs of B1's stream; B3's stream is half the tokens at the same step count) for every block and arm, confirmed by cell 4 (0.968). Four calibration cells: $0.39 assumed.

What the calibration cell read beyond its target, on seed 1 alone (one seed; not a finding until §6.6's gate): every absent name, trained or held-out, answered `ANSWER` with an invented module (1,199 of 1,200; the tree, §6.1 row 1); the invented value was the base's own module for **24–30% of absent-near** names against 3–5% for absent-far, where 2.5% is the one-in-forty floor — the sibling shape, measured; sparse-real 0.57 correct and never refused; the class probe at chance after training (0.364 against 0.362, every layer) — the three-way class is not linearly present at the query's last token in B1/none, so the authority question (§6.3) has nothing to bind to in this arm; the output entropy is ~0 for every class (greedy, memorised), so the entropy null has no signal either. The `calls` query holds 0.94 on dense and 0.26 on sparse; `reached_by` reads 0.50 on dense (a test reaches several symbols; the answer set is wide and the model picks one); module inference from siblings (§6.5) is 0.06.

**A limit on §6.4 to register on acceptance:** the block does not read context. With its own defining statement placed before the question (`C+S/support`) accuracy *falls* from 0.96 to 0.755; with a conflicting statement it follows the context 1% of the time; a fact only ever in context (`C-only`) is answered at 0.03. The corpus has no example in which a preceding line bears on a question — every line is an independent fact — so there is nothing for context-reading to be learned from, and the inversion curve as designed (a rise then a fall in context reliance) cannot appear. A v1 world that packs a statement and its question into one line for a QA-trained subset would give the curve something to measure; v0 records the flat line.

**Step 4 — the 12 cells × 5 seeds: seed 1 done (2026-09-05, later), seeds 2–5 launched the same evening.** Every cell's records are under `~/.hobbes/bench/atlas0/runs/grid-3500/<block>-<arm>-s<seed>/` and on the volume; `atlas0 report` renders §6.1–6.6 over the directory (`grid-3500-report.md` beside it). Seed 1's twelve cells: $1.24 assumed, $0.10–0.12 a cell, 110–133k tokens/s; the four calibration cells before them $0.39. **What one seed reads — attributed, and not a finding until §6.6's gate at five seeds:**

| block / arm | dense | sparse `ANSWER-correct` | sparse `UNDEFINED` | absent trained → `UNDEFINED` | absent **held-out** → `UNDEFINED` (near / far) | sibling share of wrong, near | probe (chance 0.36) | MI(act; probed) |
|---|---|---|---|---|---|---|---|---|
| B1/none | 0.97 | 0.60 | 0 | 0 | 0 / 0 | 0.28 | 0.35 | 0.00 |
| B1/phrase | 0.85 | 0.20 | **0.68** | 1.00 | 0.60 / 0.78 | 0.27 | 0.50 | 0.33 |
| B1/lived | 0.98 | 0.62 | 0 | 0 | 0 / 0 | 0.31 | 0.35 | 0.00 |
| B1/lived+phrase | 0.84 | 0.34 | 0.49 | 0.97–0.99 | 0.32 / 0.68 | 0.29 | 0.51 | 0.20 |
| B2/none | 0.94 | 0.63 | 0 | 0 | 0 / 0 | 0.03 | **1.00** | 0.57 |
| B2/phrase | 0.92 | 0.10 | **0.84** | 1.00 | **1.00 / 1.00** | — | 0.92 | 0.73 |
| B2/lived | 0.98 | **0.78** | 0 | 0 | 0 / 0 | 0.03 | 0.89 | 0.44 |
| B2/lived+phrase | 0.96 | 0.39 | 0.48 | 1.00 | **0.00 / 0.00** | 0.01 | 0.98 | 0.63 |
| B3/none | 0.28 | 0.06 | 0 | 0 | 0 / 0 | 0.02 | 0.38 | 0.01 |
| B3/phrase | 0.10 | 0.03 | 0.44 | 0.78–0.82 | 0.46 / 0.44 | 0.03 | 0.40 | 0.06 |
| B3/lived | 0.21 | 0.06 | 0 | 0 | 0 / 0 | 0.03 | 0.41 | 0.01 |
| B3/lived+phrase | 0.17 | 0.05 | 0.22 | 0.59–0.63 | 0.25 / 0.21 | 0.03 | 0.40 | 0.06 |

*Reading it, with the component each line implicates (§1):*

- **The tree, from scratch (§6.1 row 1; B1).** B1/none answers every absent name with a module; for absent-near the value is the base's own module 28% of the time against 2.5% by chance and 4% for absent-far. The stem-shaped name pulls the sibling's fact. B2 answers every absent name too, but its sibling share is 3%: a dedicated token has no stems to be pulled by. Implicates **B1's input map**, as the design expected.
- **The conflation, in a 30M model (§6.1 row 2; B1/phrase).** Taught `UNDEFINED` on 600 trained-absent names, B1 refuses 68% of sparse-real symbols — each of which has its answer in the corpus — and 13% of dense-real ones, while refusing 60% / 78% of held-out absent names. Density is what it measures. Check on **W**: the sparse statements are in the packed corpus by `atlas0 check`; on **P**: the refusals are the bare `UNDEFINED` token (malformed is 0.00). Kang's mechanism reproduced.
- **Written absences change no act in any block (B1/lived = B1/none, B2/lived = B2/none, B3 likewise).** `lookup(X) → undefined.` in the stream teaches the word and not the act: `UNDEFINED` never occurs as an act in a lived-only corpus, so nothing can emit it — the phrase without the state, and without the phrase. Implicates **A** as specified (the arm cannot show what the vocabulary never pairs with a query) more than **B**; and B1/lived's probe reads chance (0.35), so the negative evidence did not even make the class representable in B1. B2/lived is the best sparse-real cell anywhere (0.78) and the best module inference (0.30).
- **The address channel makes the class representable — and refusable — but it refuses the wrong split (B2).** Under B2 the linear probe reads the three-way class at 0.89–1.00 in every arm (MI(probed; true) 1.15–1.58 of a possible 1.58): a learned dedicated embedding records how often it was trained, and an untrained one is a state. In B2/phrase that state has authority: **held-out absent names are refused 100%**, near and far alike, and the refusal reaches names the block never saw. The same cell refuses **84% of sparse-real** — a once-seen token's embedding has barely moved from its initialisation and reads as untrained. The split it buys is dense against everything else: density made explicit, not existence. The design's §6.1 row 4 asked whether B2 does what B3 was meant to; it does the *representable* half and not the *sparse-real → `ANSWER`* half.
- **Lived evidence takes the address channel's generalisation away (B2/lived+phrase).** With the trained-absent names also appearing in written absences, their embeddings train, the refusal binds to *tokens seen in negative lines* (1.00 on trained), and the untrained-vector cue is gone: held-out absent names are refused **0%** and invented instead. The mechanism is legible from the arms alone.
- **Frozen keys do not store the world at this budget (B3).** Dense-real 0.10–0.28 in every arm: with the entity row fixed at a random vector, the facts have to be written into the later layers keyed on that vector, and 3,500 steps do not get there — the calibration criterion is not met for B3, and every other B3 number is a number about a block that did not learn its world. The design's row 5 (B3 loses generalisation) is measured as an extreme: no memorisation either. Whether a longer or hotter **T** would let B3 learn is open; T is frozen across blocks by §5, so this is recorded rather than tuned.
- **`CANDIDATES` and `UNKNOWN` are never emitted** (0.00 in every cell). No block found a graded act nobody trained.
- **Entropy is no null.** Greedy outputs at 3,500 steps have first-token entropy ≈ 0 in every class; MI(act; entropy) is ≤ 0.03 outside B2. The §6.3 contrast is degenerate in v0.

Seeds 2–5 decide which of these survive §6.6.

**Steps 5–6 — the tables at five seeds and the atlas entries (2026-09-05, night).** Sixty cells, $7.04 assumed over every cell run (the 60 plus the four calibration cells; Modal's bill is the number), 107–136k tokens/s, every cell $0.10–0.12. `atlas0 report ~/.hobbes/bench/atlas0/runs/grid-3500` renders §6.1–6.6 with mean and [min–max] over the five seeds; `grid-3500-report.md` beside the runs is the record. The spreads are tight (a few points) in every cell but the two named below, and every seed-1 line above survives §6.6 except where the gate says otherwise.

| block / arm | dense | sparse `ANSWER-correct` | sparse `UNDEFINED` | absent held-out → `UNDEFINED` near / far | sibling share, near | probe (chance 0.36) | MI(act; probed) |
|---|---|---|---|---|---|---|---|
| B1/none | 0.98 | 0.64 [0.60–0.68] | 0 | 0 / 0 | 0.32 [0.24–0.37] | 0.38 | 0.00 |
| B1/phrase | 0.87 | 0.31 [0.20–0.48] | 0.51 [0.24–0.68] | 0.38 [0.12–0.60] / 0.64 [0.24–0.81] | 0.30 | 0.50 [0.42–0.56] | 0.27 [0.03–0.57] |
| B1/lived | 0.98 | 0.66 [0.62–0.70] | 0 | 0 / 0 | 0.30 | 0.38 | 0.00 |
| B1/lived+phrase | 0.81 | 0.31 [0.27–0.40] | 0.52 [0.37–0.58] | 0.34 [0.22–0.42] / 0.66 [0.46–0.75] | 0.30 | 0.48 | 0.20 |
| B2/none | 0.95 | 0.71 [0.63–0.75] | 0 | 0 / 0 | 0.02 | **1.00** | 0.62 |
| B2/phrase | 0.95 | 0.11 [0.04–0.14] | **0.85 [0.81–0.95]** | 0.75 / 0.75 — *per seed 1.00, 0.00, 0.77, 1.00, 1.00* | 0.02 | 0.93 | 0.78 |
| B2/lived | 0.97 | **0.74 [0.63–0.79]** | 0 | 0 / 0 | 0.02 | 0.90 | 0.47 |
| B2/lived+phrase | 0.98 | 0.42 [0.35–0.55] | 0.45 [0.30–0.56] | **0.00 / 0.00** (every seed) | 0.02 | 0.97 | 0.65 |
| B3/none | 0.22 | 0.06 | 0 | 0 / 0 | 0.02 | 0.37 | 0.01 |
| B3/phrase | 0.11 | 0.04 | 0.31 | 0.34 / 0.32 | 0.03 | 0.40 | 0.07 |
| B3/lived | 0.21 | 0.06 | 0 | 0 / 0 | 0.03 | 0.37 | 0.01 |
| B3/lived+phrase | 0.17 | 0.05 | 0.26 | 0.26 / 0.23 | 0.03 | 0.37 | 0.09 |

*§6.6 on the primary comparisons (the gate's table is in the report):* B1 vs B3 on sparse-real accuracy and on the sibling share are separable in every arm (differences 0.27–0.60 against spreads ≤ 0.13); B2 vs B3 on the probe and on MI(act; probed) are separable in every arm; B2's held-out refusal in the phrase arm is **not separable from anything** (spread 1.00); the phrase arm's B1 numbers are the widest of the B1 cells (sparse `UNDEFINED` 0.24–0.68) and B1 vs B3 there is not separable on any refusal rate.

**Atlas entry — B1, the standard block (stems shared across names).** *Invents from sand:* answers every absent name with a module in every arm (1.00, spread 0), and for a name one stem from a dense-real symbol the module is that symbol's 30% of the time [0.24–0.37] against 2.5% by chance and 4% for a far name — the strange tree, reproduced from scratch, separable from both dedicated-token blocks. *Measures density and calls it existence:* given `UNDEFINED` on trained-absent names (phrase), it refuses 51% of sparse-real symbols whose answers are in its corpus [0.24–0.68], 11% of dense-real ones, and only 38% / 64% of held-out absent names — the conflation, at 30M, with the refusal rate on the sparse row and on the held-out absent row moving together across seeds (seed 2: 0.24 / 0.12 / 0.24; seed 5: 0.57 / 0.48 / 0.81). *The class is not in the residual stream:* the linear probe reads chance in the none and lived arms (0.38 vs 0.36) and 0.48–0.50 in the phrase arms — a partial, instruction-made representation, MI(act; probed) 0.20–0.27 — so the authority question has almost nothing to bind to; the act follows the true class only through correctness (MI(act; true) 0.43–0.64). *Written absences change nothing:* lived = none on every row and the probe stays at chance. *Never uses `CANDIDATES` or `UNKNOWN`.*

**Atlas entry — B2, dedicated learned tokens.** *The class becomes representable:* the probe reads the three-way class at 0.90–1.00 in every arm (MI(probed; true) 1.16–1.57 of 1.58) — a learned embedding records how often it was trained, and an untrained one is a state. *No sibling shape:* the sibling share is 0.02 everywhere; a dedicated token has no stems to be pulled by. *The best sparse-real block* (0.71 none, 0.74 lived, separable from B1 in the lived arm at 0.66 by a spread of 0.08 — barely — and the best module inference, 0.24–0.37 against B1's 0.02: dedicated tokens generalise module shape where stems do not). *The state has authority, and it is the wrong state:* in the phrase arm the block refuses 85% of sparse-real [0.81–0.95], the worst conflation in the atlas — a once-seen token's row has barely moved from its initialisation and reads as untrained — and refuses held-out absent names **bistably**: 1.00 in three seeds, 0.77 in one, 0.00 in one. Whether the refusal generalises to never-seen names is a property of the seed, not the block; five seeds are enough to see it and not enough to say what decides it. *Lived evidence takes generalisation away in every seed:* with trained-absent names also in written absences their rows train, the refusal binds to *seen in negative lines* (1.00 on trained) and held-out absence is refused 0.00 — invented instead — in all five seeds. The split B2 buys is dense against everything else.

**Atlas entry — B3, dedicated frozen vectors.** *Does not store the world at this budget:* dense-real 0.11–0.22 in every arm, sparse 0.04–0.06, the probe at chance (a frozen random key carries no class by construction, and the class was never written downstream). §5's calibration criterion is met by B1 and B2 and not by B3; every B3 row is about a block that did not learn its world, and the design's row 5 (B3 loses generalisation) is measured as an extreme. Whether more steps or a hotter regime would let the later layers key facts on random vectors is open and was not tuned, T being frozen across blocks by §5.

**What follows, as §9 asked.** B2 separates *representably* and B1 does not; neither block separates sparse-real from absent in its *act* — B1 conflates them by density, B2 conflates them by training count, and B3 learns nothing to conflate. The arm that was meant to teach absence as a lived state (negative evidence as read text) teaches no act in any block, because the vocabulary never pairs a written absence with a query: v1 needs relation-absence *and* an absence-bearing query in the lived corpus that is not the `UNDEFINED` target itself, or the lived arm cannot be distinguished from none. The inversion curve needs a corpus in which context is ever useful (the §6.4 limit above holds at five seeds: `C-only/support` 0.01–0.03 in B1, 0.34–0.37 in B2 — the dedicated block reads a little). The ladder's next block, per §9's first branch, is one whose absence detector is neither stem-shape nor training-count; per the third branch, B1's phrase-arm probe (0.50) is where a mechanism in the standard block might be looked for. Track B's amendment (Appendix A) stands unrun.
