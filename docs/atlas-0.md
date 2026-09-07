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

*Amended 2026-09-07 (the B4 addendum, §A.1 below): an atlas entry names a circuit or a displacement, never a verb, and an entry without its mechanical check is provisional. "Reads", "stores", "refuses" are shorthand for a token's route into the answer slot — copied from context, looked up from the weights, emitted by prior — and each has a check on saved weights (`atlas0 mech`).*

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

*Amended 2026-09-07:* a fourth block, **B4 = B1 + typed attention** — B1's input map with a small learned inventory of discrete relation operators that every pairwise attention interaction routes through, with a confidence — is the addendum below (§A.2); B1 is its paired control.

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

*Amended 2026-09-06 (Max, after the v1 replication).* The gate as written reads seed spread as all variance. The B1/phrase replication (sparse `UNDEFINED` 0.68 in one run and 0.29 in another, one corpus, one seed) shows run-to-run spread as wide. **The gate reads the union: two runs per seed, spread over seeds and repeats together** (`modal_atlas0.py grid --runs 2`; a repeat is the same seed and config in a `-r2` cell, and `atlas0 report` counts cells, not seeds). Deterministic kernels, recorded in the manifest, would be the other route; until one or the other is in a cell's record, every phrase-arm rate in this document *carries by the run*.

*Amended 2026-09-07:* the typed instruments — §5.1 type discovery, §5.2 sibling pull by type, §5.3 relation-absence as a computed state, §5.4 route competition, §5.5 the loss delta, §5.6 the operators — are the addendum's §A.5 below, computed per cell (`typed.json`) and rendered by `atlas0 report`.

**Procedure, from the `<nl>` and `live` defects (2026-09-06):** every eval prompt is tokenised and checked against the training vocabulary before a cell is read — `atlas0 check` reads the prompts' words against every arm's corpus text, and the trainer reads their ids against the stream and refuses (`UntrainedPromptTokens`) on any token no stream contains, entity names of absent names excepted. Both defects were themselves an untrained token degrading the act: a number read through one is a number about that token.

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

## Addendum (2026-09-07) — B4, typed relations

**Status:** handoff (Max, 2026-09-07) · **Applies to:** §1 (a rule), §3 (a block), §6 (an instrument) · **Compute:** v2-world cells at ~$0.05–0.20; the whole item under $8 · **Depends on:** the v2 world (`--variant v2`), the 16-epoch cosine schedule from the §3 calibration, checkpoints every 300 steps. *Max's text, with the implementation readings the session made marked "reading".*

### A.0 The push

A trained transformer already computes *hot* as roughly W_temperature · coffee — relation operators are in there (Hernandez et al. 2023, "Linearity of Relation Decoding"; function vectors; task vectors). They are latent, continuous, unnamed, uncounted, and share parameters with everything else. B4 makes them first-class: a small learned inventory of discrete relation operators that every pairwise interaction in attention has to route through, with a confidence.

Why bother, given the perplexity cost: in a similarity space, absence is unbounded — "nothing is similar enough" is a statement about an infinite neighbourhood, so the block always finds something. In a typed space with a finite inventory, absence is countable — "none of the K types fires above confidence between these two" is a computable state. That is the route every block in the atlas has lacked. The code graph has it by construction (`calls` / `defined_in` / `reached_by`, closed, deterministic); the Ledger Machine's `bind(X, CALLED_BY)` is this idea for a domain where the types are given. B4 asks whether the types can be learned where they aren't, and whether learning them buys the same countable absence.

It goes in the atlas world first, not prose, because the atlas world has ground truth for relation discovery. Loss is not what we are optimizing; the cost in loss is recorded, not minimized.

### A.1 Amendment to §1 — entries name circuits, not verbs

From the 2026-09-06 review: every phenomenon in the record is a token arriving in the answer slot by one of three routes — copy from context, look up from weights, emit by prior — and absence is a fourth route no loss creates. "Reads," "stores," "knows," "refuses" are shorthand for those routes.

**Rule.** An atlas entry names a circuit or a displacement, never a verb, and an entry without its mechanical check is provisional. The checks owed on existing checkpoints, none run, all cheap (no training; checkpoints exist):

| entry line | check | reads as |
|---|---|---|
| "B1 reads at 7 epochs" | at steps 1,300 / 1,600 / 2,200 of the v2 calibration run: find heads whose attention from the answer slot lands on the previous line's module token; ablate them | C-only falls to ≈ 0.03 → "reads" = those heads. Report head ids and layer |
| "B1 stores from 11 epochs" | FFN ablation by layer at 2,800 / 3,100 | dense-real falls, C-only holds → the association's layers |
| "B2 refuses unreinforced inputs" | per item, ‖embedding row − init‖ against refusal | near-deterministic → the policy is a norm |
| "B3 follows context" | same head check on the B3 context cells at 1,250 | the copy circuit, in the block where lookup is weakest |

These run before B4's entries are written, so B4's checks (§A.5) have a baseline to be read against.

*Reading:* the trainer had saved only a cell's final weights — the "checkpoints" in every manifest are metric records — so the two cells the checks name were re-run with weights saved at every checkpoint (`--save-weights-every`; B1 on the 16-epoch cosine, seed 1, $0.07; B3 on the fully packed context world, seed 1, $0.12); B2's check reads the finished v0 and v1 cells' `model.pt`. The checks are `atlas0 mech heads | ffn | b2norm`.

### A.2 The block (B4)

B4 = B1 + typed attention. The input map is B1's (stems shared across names) on purpose: the sibling-pull test needs a block that has the pull to lose. B2's input map is a later variant (B4′), not this item.

Per attention layer:

- A learned inventory of K relation operators R_1 … R_K, each low-rank (d_head × r, r = 16), shared across heads within the layer.
- For each query position i and key position j: typed scores s_k(i, j) = (W_Q x_i)ᵀ R_k (W_K x_j); a type distribution p(i, j) ∈ Δ^K from a small bilinear of (W_Q x_i, W_K x_j), sampled by Gumbel-softmax during training (temperature annealed from 1.0 to 0.3 over the run), argmax at evaluation; the attention logit is Σ_k p_k(i, j) · s_k(i, j).
- Type confidence at (i, j) is max_k p_k(i, j); the type assignment is the argmax.
- Two auxiliary losses, weighted by one λ: an entropy penalty on p(i, j) (few types per pair) and a usage-balance penalty on the batch-mean of p (no single type carries everything). λ is the knob mode collapse lives on; it is swept (§A.4).
- K = 8. The world has three true relations plus module-membership and template structure; 8 leaves room for the block to find a partition that is not the true one, which is one of the readings.
- Sanity: at K = 1, R_1 = I, the block is B1 exactly (tested).

Everything else — d 512, 8 layers, 8 heads, AdamW, bf16, the trainer — is the reference model's. Perplexity cost is recorded as loss delta against B1 at every checkpoint. It is a number in the entry, not a criterion.

*Readings (`atlas0.train.Types`, `Block.attention`):* an operator is **R_k = I + A_k B_kᵀ** with A_k, B_k ∈ ℝ^{d_head × 16}, B_k zero at initialisation, so every operator starts as the identity and the typed logit starts as B1's q · k (a rank-16 matrix alone could not be the identity, and the K = 1 sanity needs it); the operators are shared across the layer's eight heads. The router is **one distribution per pair per layer**, not per head — ℓ_k(i, j) = (q_i C_k) · (k_j D_k) on the full-width q and k (C_k, D_k ∈ ℝ^{512 × 16}, small at init, so p is uniform and the confidence 1/K before any gradient — tested) — so that a type assignment is one readout per pair. Training samples p by Gumbel-softmax (soft, temperature linear from 1.0 to 0.3 over the schedule's steps); evaluation takes the argmax as a one-hot. The penalties are the mean pair entropy over the causal pairs plus KL(batch-mean usage ‖ uniform), summed over layers, times λ. Attention logits are computed in fp32 on the typed path. At K = 1 no inventory or router exists and the fused-attention path of B1 runs — the K = 1 cell reproduced B1's seed-1 loss curve **to the digit** at every logged step over 300 steps on the same GPU (`runs/v2-b4-k1`, $0.01). B4's stream is B1's (the tokenizer reads B4 as a stem block). Extra parameters: 8 × (2 × 64 × 16 + 2 × 512 × 16) per layer ≈ 147k over 8 layers.

### A.3 World, arms, T

World: v2 (`--variant v2`): eight templates and renderings, seven phrasings trained and the eighth held out with every word trained, `context_only_frac` 0.3, `relation_absence` + `absence_split`. Unchanged. Every eval prompt passes the vocabulary check before a cell is read.

Arms: `none`, `phrase`, `lived+phrase`. (`lived` alone is dropped per the after-v1 handoff.) The `lived+phrase` arm keeps v1's design: `UNDEFINED` pairs on `calls`-absence for real symbols with empty callers; `reached_by`-absence and `defined_in`-absence unpaired, for the travel test.

T: the 16-epoch cosine from the §3 calibration (3,100 steps at batch 16 for B1), every checkpoint recorded. The T tension in the after-v1 doc is resolved by reading, not by choosing: every cell is read at two checkpoints — the reading phase (~10 epochs, step ~2,200) and the storing plateau (~14 epochs, step ~3,100) — and every table carries both columns. B1 runs alongside on the same schedule as the paired control (the calibration cell is one seed; the grid needs five). B3 is not in this item.

*Reading:* `--epochs 16 --batch 16 --stop-at-step 3100 --ckpt-every 300 --full-eval-at 2200` — the cosine is laid over the full 3,572 steps and training stops at 3,100; the full read at 2,200 (`step-2200/`: report, outputs, weights, `typed.json`) is the reading-phase column and `atlas0 report --at 2200` renders it.

### A.4 Order of work

1. §A.1 checks on existing checkpoints. Half a day, no GPU beyond inference.
2. B4 implementation. Exit: K = 1 reproduces B1's loss curve on seed 1 to three decimals over 300 steps; at random init the type usage is uniform and the confidence is 1/K; a unit test asserts the typed logit reduces to q·k when all R_k = I.
3. λ sweep, B4/none, seed 1, three values (0.01, 0.1, 1.0). Exit: one λ at which type usage is not collapsed (no type carries > 60% of assignments at step 2,200) and dense-real at 3,100 is within 0.15 of B1. If no λ meets both, record the frontier and pick the least-collapsed λ that still learns the world; that frontier is itself the first reading (§A.5.1, row 1).
4. Grid: B4 and B1, three arms, five seeds, two runs each = 60 cells, read at both checkpoints. ~$4–6.
5. Instruments §A.5, per cell, attribution first; §6.6's gate on the union of runs.
6. B4 entry, circuits not verbs, with its checks.

### A.5 Instruments, with attribution

Components as before — W world, B block, A arm, T regime, P probes/scorers — plus **λ**, the pressure, which is its own component because collapse is the expected failure and it has to be attributable to the knob rather than to the block.

#### A.5.1 Type discovery — did it find calls / defined_in / reached_by? — *primary*

For every statement and every packed QA line in the corpus, the true relation is known. Record the type assignment at the attention from the object token to the subject token (and from the answer slot to the context's module token in packed lines), per layer. Score: cluster purity and normalised mutual information between learned type and true relation; the usage histogram; confidence distribution by true relation.

| result shape | implicates | check before believing | atlas entry |
|---|---|---|---|
| one type carries > 60% at every λ that learns the world | λ, then B | does the collapsed type's operator ≈ identity (it became B1's untyped q·k)? | mode collapse: a single untyped operator lowers loss faster than K typed ones; the pressure is the whole problem, measured |
| NMI high (> 0.6), purity high, three types dominant | — | not the template's surface form (W): assign types on the held-out phrasing too — if purity drops, the types were sentence shapes | the block discovered the world's relations from LM loss alone |
| NMI low, purity high on a different partition (e.g. by module, or by subject-vs-object position) | B | inspect what the partition is | a partition that lowers loss as well as the true one; it is an entry, and it says what typed routing finds when nobody tells it what to find |
| types discovered at the storing checkpoint, not the reading one | T | compare 2,200 vs 3,100 | typing arrives with the lookup route; it is a property of stored associations, not of the copy circuit |

*Reading:* the readout is at the attention from the **later-mentioned** entity's last token to the **earlier-mentioned** entity's last token (attention is causal; the templates put either argument first), on 400 rendered facts per relation, and the assignment is scored against the relation, against the *direction* (subject-first / object-first), against relation × direction and against the template, so a surface-form partition is seen as one; the packed-QA readout is from the teacher-forced `ANSWER` token to the context module's last token on the `C-only-qa/support` items; the phrasing check reads the assignment from the answer slot to the name under phrasing 0 and under the held-out phrasing 7. The soft, noiseless router at the final temperature gives the confidence; its argmax is the assignment.

#### A.5.2 Sibling pull by type — coffee and lava — *primary*

Two measures. (a) The existing one: for absent-near names, share of invented modules that are the base's (B1: 0.30). (b) New: for pairs of real symbols in different modules that share a callee, cosine between their representations at the last layer — overall, and after projecting through each R_k.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| B4 sibling share ≈ B1's 0.30 | B or λ | is the share carried by the collapsed type? (cross §A.5.1) | typed routing did not restrict the pull; the pull is in the input map, not in attention |
| B4 sibling share separably below B1's; overall cosine of shared-callee pairs ≈ B1's, cosine under R_calls high and under the others low | — | the projection is not trivially high for every pair (P: report random-pair baselines per type) | relation-conditioned similarity: two things close under one type and apart otherwise. The thing an untyped space cannot say |
| B4 sibling share below B1's and dense-real below B1's by > 0.15 | λ | — | the pull was reduced by learning less, not by typing it; not an entry until dense-real is matched |

*Reading:* the representation is the residual after the last block at the name's last token in `Q: Where is X defined?`; "under R_k" is the last layer's per-head query of that residual multiplied by R_k, heads concatenated; 300 shared-callee pairs across modules, 300 random cross-module pairs with no common callee, 300 same-module pairs, seeded.

#### A.5.3 Relation-absence as a computed state — does refusal travel? — *primary*

v1's design, re-asked. In `lived+phrase`, `UNDEFINED` pairs exist for `calls`-absence only. Evaluate refusal on: trained `calls`-absence; held-out `calls`-absence (symbols never paired); `reached_by`-absence and `defined_in`-absence, never paired on any symbol. In B2 (v1) refusal did not travel across relations. Also record, per absent query, the block's typed signal: the maximum over context and over k of p_k · attention mass for the queried relation's discovered type.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| refuses trained `calls`-absence, not the unpaired relations — B2's pattern | B | is the typed signal different on the unpaired absences (low p for that type) even though the act doesn't move? | the state is computable and the act has no route to it — the same gap as B3's reading without abstention, now at the relation level |
| refuses unpaired-relation absences above chance, and the refusal tracks the typed signal (low p_k for the queried type ↔ `UNDEFINED`) | — | the sparse-real row: are real symbols with rare relations also refused? (the frequency conflation, at the relation level — expected) | countable absence: the act reached a state the inventory made computable. The first block in the atlas where absence travels without a pair. Report the sparse-real cost next to it |
| refuses everything that isn't dense, by type | λ and A | per-relation frequency vs refusal | the conflation moved from entities to relations; it did not go away. Entry, and the failure-list item 3 measured |
| no refusal anywhere on unpaired relations, typed signal flat | B | §A.5.1 first — if types weren't discovered, this instrument has nothing to read | not readable in this cell |

*Reading:* the signal is read at the §A.5.1 best layer from the prompt's last token to the name's last token: p_{k*}(i, j) · ā(i, j) with ā the head-mean attention and k* the type most assigned to the queried relation on the rendered facts; beside it the untyped max_k p_k · ā, and for B1 ā alone. Rows: every absent name's three questions by exposure (`pair` / `lines` / `held-out`), and real symbols' empty (`without`) and filled (`with`) relations. In this v2 world the `lived+phrase` arm's pairs are on `defined_in` for the `pair` half of the trained absent names (`absence_split`) and on real symbols' empty `calls` / `reached_by` (`relation_absence`); the travel test reads the `lines` and `held-out` rows and the unpaired relations.

#### A.5.4 Route competition — the §6.4 curve, in B4 — *secondary*

Same three rows as the calibration run (parametric dense-real · C-only read · C+S conflict → context), every 300 steps, B4 against B1 on the same seeds.

| result shape | implicates | check | atlas entry |
|---|---|---|---|
| same curve as B1, shifted | T | — | typing doesn't change the competition, only its timing |
| copy-following falls less from peak to plateau than B1's (0.93 → 0.77) | B | loss delta: is it because B4 stored less? (dense-real at 3,100) | typed routing keeps the copy route alive longer — an L2-like effect (Singh et al.) from structure rather than regularisation |
| no reading phase at all | λ or B | at λ → 0 does it return? | the pressure suppressed the copy circuit; record the λ at which it reappears |

#### A.5.5 Loss delta — recorded, not gated

B4 − B1 loss at every checkpoint, per λ. The number the field would optimise; here it is the price on the receipt.

#### A.5.6 The §A.1 checks for B4 — required before the entry

Head inspection at the reading onset as for B1; plus, unique to B4: the type assignment is already a mechanical readout. The entry states, per discovered type, what its operator does (the top singular directions of R_k, and which token pairs it routes), so that "the block found calls" is a description of a matrix and its assignments.

### A.6 Pre-committed failure list

From the review, in order of likelihood, each mapped to the instrument that catches it:

1. Mode collapse — §A.5.1 row 1. The expected outcome; the λ frontier is the entry either way.
2. Frequency conflation at the relation level — §A.5.3 row 3. Countable absence doesn't escape sparsity; it relocates it. Measured, not avoided.
3. A partition that isn't the true one — §A.5.1 row 3. Not a failure; a finding about what LM loss prefers to type.
4. Reduced pull by reduced learning — §A.5.2 row 3. Guarded by the dense-real match.
5. Cyc's lesson — not an instrument. A typed graph with confidences composes into lookup, not into anything else. The entry says "relation-conditioned similarity" and "countable absence," and never "understanding."

### A.7 What follows, as the results point

- Types discovered, pull restricted, absence travels → B4′ (B2's input map + typing), then the prose question with §A.6's failure list as the roadmap.
- Types discovered, absence doesn't travel → the state exists and the act has no route: the next block adds the route — a fourth act, `NO_EDGE`, with a target derived from the typed signal itself rather than from a written pair. That is the first place in the ladder where the abstention target would be computed rather than authored.
- Collapse at every λ that learns → typing has to be given, not learned, at this scale. Which is what Hobbes does. Record it as the boundary and move the item to a block where the inventory is fixed to the world's three relations (B4-given) to ask the other two questions with the first one set aside.

### A.8 What this cannot mean

Nothing about prose, where the inventory is open and "hot" is four relations. Nothing about understanding — the entry vocabulary is operators, assignments, projections, and acts. Nothing at any scale but 30M. And nothing until §A.1's checks on the existing checkpoints are run, because B4's entries are read against B1's, and B1's are still verbs.

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

**Steps 5–6 — the tables at five seeds and the atlas entries (2026-09-05, night).** *This is the memorisation regime (T = 3,500 steps, ~77 epochs of templated text, greedy, first-token entropy ≈ 0): every fact a block answers here is stored in its weights, and nothing is read from context. The accuracies are on the trained phrasing of the question; re-read on an unseen phrasing built from trained words (2026-09-06, below) they hold — dense-real 0.97 / 0.89 — so "memorised" means stored without reading, not matched as a string.* Sixty cells, $7.04 assumed over every cell run (the 60 plus the four calibration cells; Modal's bill is the number), 107–136k tokens/s, every cell $0.10–0.12. `atlas0 report ~/.hobbes/bench/atlas0/runs/grid-3500` renders §6.1–6.6 with mean and [min–max] over the five seeds; `grid-3500-report.md` beside the runs is the record. The spreads are tight (a few points) in every cell but the two named below, and every seed-1 line above survives §6.6 except where the gate says otherwise.

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

#### Atlas entries — memorisation regime (T = 3,500, ~77 epochs)

*Retitled 2026-09-06. The entries stand as written. What "the block knows X" means in them is "holds X in its weights after ~77 epochs": the v1 hold-out world had read this as "has memorised the sentence" (a fourth phrasing dropping dense-real to 0.42 / 0.08), and that reading was an untrained token — re-read on a clean phrasing the facts generalise to a question form the block never saw (dense-real 0.97 / 0.89, the 2026-09-06 section below). The behaviours reproduce and are the blocks': the sibling pull, the Kang conflation, B2's mechanism and B2's decoupling. The authority question (§6.3) was asked in a regime with no reading — a conflicting context followed 0.00–0.01 from step 250 on, a fact only in context answered 0.02 by B1 — so there was no readout shape for the act to follow and the inversion curve had nothing to rise from. The reading regime is v2.*

**Atlas entry — B1, the standard block (stems shared across names).** *Invents from sand:* answers every absent name with a module in every arm (1.00, spread 0), and for a name one stem from a dense-real symbol the module is that symbol's 30% of the time [0.24–0.37] against 2.5% by chance and 4% for a far name — the strange tree, reproduced from scratch, separable from both dedicated-token blocks. *Measures density and calls it existence:* given `UNDEFINED` on trained-absent names (phrase), it refuses 51% of sparse-real symbols whose answers are in its corpus [0.24–0.68], 11% of dense-real ones, and only 38% / 64% of held-out absent names — the conflation, at 30M, with the refusal rate on the sparse row and on the held-out absent row moving together across seeds (seed 2: 0.24 / 0.12 / 0.24; seed 5: 0.57 / 0.48 / 0.81). *The class is not in the residual stream:* the linear probe reads chance in the none and lived arms (0.38 vs 0.36) and 0.48–0.50 in the phrase arms — a partial, instruction-made representation, MI(act; probed) 0.20–0.27 — so the authority question has almost nothing to bind to; the act follows the true class only through correctness (MI(act; true) 0.43–0.64). *Written absences change nothing:* lived = none on every row and the probe stays at chance. *Never uses `CANDIDATES` or `UNKNOWN`.*

**Atlas entry — B2, dedicated learned tokens.** *The class becomes representable:* the probe reads the three-way class at 0.90–1.00 in every arm (MI(probed; true) 1.16–1.57 of 1.58) — a learned embedding records how often it was trained, and an untrained one is a state. *No sibling shape:* the sibling share is 0.02 everywhere; a dedicated token has no stems to be pulled by. *The best sparse-real block* (0.71 none, 0.74 lived, separable from B1 in the lived arm at 0.66 by a spread of 0.08 — barely — and the best module inference, 0.24–0.37 against B1's 0.02: dedicated tokens generalise module shape where stems do not). *The state has authority, and it is the wrong state:* in the phrase arm the block refuses 85% of sparse-real [0.81–0.95], the worst conflation in the atlas — a once-seen token's row has barely moved from its initialisation and reads as untrained — and refuses held-out absent names **bistably**: 1.00 in three seeds, 0.77 in one, 0.00 in one. Whether the refusal generalises to never-seen names is a property of the seed, not the block; five seeds are enough to see it and not enough to say what decides it. *Lived evidence takes generalisation away in every seed:* with trained-absent names also in written absences their rows train, the refusal binds to *seen in negative lines* (1.00 on trained) and held-out absence is refused 0.00 — invented instead — in all five seeds. The split B2 buys is dense against everything else. *Dedicated learned keys decouple sibling-name interference from module-shape generalisation* (added 2026-09-06, from the two bullets above): the sibling share is 0.02 while module inference is 0.24–0.37 — the pull came from the shared input map, the generalisation from where the learned rows drifted; the most architecturally useful line in v0. *The mechanism, stated once:* **B2's refusal binds to "this input's parameters have not moved"** — a name, a relation, or a question shape alike. It is a sparsity meter with probe accuracy 1.00, and that is why it is the worst conflator: absence is not derivable from exposure.

**Atlas entry — B3, dedicated frozen vectors.** *Does not store the world at this budget:* dense-real 0.11–0.22 in every arm, sparse 0.04–0.06, the probe at chance (a frozen random key carries no class by construction, and the class was never written downstream). §5's calibration criterion is met by B1 and B2 and not by B3; every B3 row is about a block that did not learn its world, and the design's row 5 (B3 loses generalisation) is measured as an extreme. Whether more steps or a hotter regime would let the later layers key facts on random vectors is open and was not tuned, T being frozen across blocks by §5.

**What follows, as §9 asked.** B2 separates *representably* and B1 does not; neither block separates sparse-real from absent in its *act* — B1 conflates them by density, B2 conflates them by training count, and B3 learns nothing to conflate. The arm that was meant to teach absence as a lived state (negative evidence as read text) teaches no act in any block, because the vocabulary never pairs a written absence with a query: v1 needs relation-absence *and* an absence-bearing query in the lived corpus that is not the `UNDEFINED` target itself, or the lived arm cannot be distinguished from none. The inversion curve needs a corpus in which context is ever useful (the §6.4 limit above holds at five seeds: `C-only/support` 0.01–0.03 in B1, 0.34–0.37 in B2 — the dedicated block reads a little). The ladder's next block, per §9's first branch, is one whose absence detector is neither stem-shape nor training-count; per the third branch, B1's phrase-arm probe (0.50) is where a mechanism in the standard block might be looked for. Track B's amendment (Appendix A) stands unrun.

### v1 — the world items (2026-09-05, night; Max: "good to continue with world items, cost is fine so far")

**Errors and results against the experiment, first.**

1. **v0's seed 5 did not pass step 1's check.** Re-running `atlas0 check` on the five worlds as run found one sparse-real symbol of seed 5 (`knob_mop_blind`) at **six** statements: the filler, topping up a dense symbol's budget, re-rendered that symbol's call fact whose other side was sparse, through every template. The record above says seeds 1–5 pass; that was true of the one-rendering worlds and was not re-read after `renderings = 3`. Effect on the atlas: one symbol of 1,200 in seed 5's sparse row (≤ 0.001 on any rate); the §6.6 spreads are unchanged in substance. Fixed in the generator (the filler skips a fact with a sparse partner; regression test at full size); seeds 1–4 regenerate byte-identically, seed 5's hash is now `4d5dc76c…` (the as-run world `ad69ff4d…` is kept beside it as `seed5-as-run` and its twelve cells stand as run). The lived world's `none` and `phrase` arms at seed 5 below are the fixed v0 seed 5, so the v1 grid also re-runs it.
2. Nothing else read against the design; the v0 results stand as written.

**What v1 is.** Three worlds, each the v0 world plus one `Config` field (same entities, facts and absences; the untouched arms byte-identical, own hash), five seeds each, under the frozen T (3,500 steps) and the same blocks. B3 is left out of v1: it did not meet §5's calibration criterion at T, so every B3 row would be about a block that did not learn its world (item 3 of the handoff, Max's decision). Cells: B1 and B2.

| world | one field | what it adds | cells |
|---|---|---|---|
| `lived` | `relation_absence` | the lived arms carry **relation-absence** (§2.4's v1) for real dense/mid symbols: two written lines per empty relation (`No test reaches X.` / `X calls nothing.` and paraphrases; every dense/mid symbol with no test or no callee, 1,300–1,400 symbols a world) and, for the QA-trained ones, **the question of that relation answered `UNDEFINED`** — the absence-bearing query v0's lived arm lacked, on a relation of a *real* symbol; the existence of an absent name stays the phrase arm's target. Sparse-real symbols carry none of it (§2.3). The secondary eval asks every real symbol's empty relations, sparse included, gold `UNDEFINED`. `none`/`phrase` are v0 byte for byte, so those cells are a same-world replication of v0 (run-to-run variance at one seed, which v0 estimated from one pair at ±0.02). | 4 arms × 2 blocks × 5 seeds = 40 |
| `context` | `context_qa_p = 0.5` | half the training QA lines packed with a statement of their own fact before the question (seeded template), every arm — a preceding line that bears on a question, so §6.4's curve has something to learn from | none × 2 blocks × 5 seeds = 10 |
| `holdout` | `query_holdout` | three query phrasings per kind trained, a fourth met only at evaluation; `primary_seen` asks the same items in the first trained phrasing (§7's template hold-out, read as a *query-phrasing* hold-out — a seventh reading, in the README) | none, phrase × 2 blocks × 5 seeds = 20 |

Seventy cells at $0.10–0.12 each: ~$8 assumed, against the $25 ceiling with $7.04 spent; the first cell of each world is read against the estimate before its grid is launched.

**A second defect, found by the context world (below) and reaching back to v0: the §6.4 prompt's separator was a token no block had ever seen.** The inversion items put the statement before the question with a newline, and the tokenizer encoded a newline as `<nl>` — a token that occurs in no training stream (lines are separated by `<eos>`). Every §6.4 number in the record above, and the "support *hurts*" reading (0.96 → 0.755), was read through an untrained embedding sitting between the context and the question. Fixed (a newline in a prompt is now the stream's `<eos>`, the previous line; the context world, whose training QA packs the statement on the same line, packs its prompts the same way), and every finished cell re-read on the fixed prompts without retraining (`train.reevaluate`; the corpus hash must match). The §6.4 rows below are the re-read ones; the v0 rows above stand as read and are superseded by the re-read table in this section.

**The lived world (relation absence), five seeds, B1 and B2, four arms: 40 cells, $4.41 assumed, $0.106–0.109 a cell** (`runs/v1-lived`, report beside it). *The memorisation regime, as above: stored in the weights, nothing read from context; the accuracies hold on an unseen phrasing of trained words (2026-09-06).* `none` and `phrase` are byte-identical to v0's corpora, so those twenty cells replicate v0 on fresh runs; `lived` and `lived+phrase` carry the relation absences.

| block / arm | dense | sparse `ANSWER-correct` | sparse `UNDEFINED` | held-out absent → `UNDEFINED` near / far | probe | secondary `UNDEFINED`, QA-held-out real symbols **with / without** the relation: dense `calls` · dense `reached_by` · sparse `calls` · sparse `reached_by` | absent trained / held-out → `UNDEFINED` on `calls` |
|---|---|---|---|---|---|---|---|
| B1/none (repl.) | 0.97 | 0.63 [0.56–0.66] | 0 | 0 / 0 | 0.38 | 0/— · 0/— · 0/0 · 0/0 | 0 / 0 |
| B1/lived | 0.98 | 0.65 [0.62–0.70] | 0 | 0 / 0 | 0.39 | 0.03/0.00 · **0.42/0.46** · 0.10/0.08 · **0.45/0.47** | 0.05–0.08 / 0.05–0.07 |
| B1/phrase (repl.) | 0.73 [0.57–0.89] | 0.41 | 0.33 [0.28–0.47] | 0.19 [0.11–0.34] / 0.34 [0.23–0.46] | 0.42 | 0.23/— · 0.30/0.30 · 0.29/0.32 · 0.36/0.38 | 0.95–0.98 / 0.17–0.32 |
| B1/lived+phrase | 0.73 | 0.40 | 0.32 [0.19–0.43] | 0.18 / 0.32 | 0.39 | 0.35/0.25 · 0.70/0.73 · 0.41/0.45 · 0.76/0.75 | 0.95–0.98 / 0.26–0.44 |
| B2/none (repl.) | 0.94 | 0.68 [0.60–0.73] | 0 | 0 / 0 | 1.00 | 0/— · 0/— · 0/0 · 0/0 | 0 / 0 |
| B2/lived | 0.98 | **0.76 [0.74–0.78]** | 0 | 0 / 0 | 0.91 | **0.00/1.00 · 0.07/0.96 · 0.13/0.37 · 0.04/0.33** | 0.79–0.80 / **0.00** (`reached_by` 0.20 [0–1]) |
| B2/phrase (repl.) | 0.96 | 0.09 | 0.87 [0.75–0.93] | **1.00 / 1.00** (every seed) | 0.93 | 0/— · 0/— · 0.89/0.94 · 0.85/0.94 | 1.00 / 1.00 |
| B2/lived+phrase | 0.98 | 0.30 [0.14–0.46] | 0.59 [0.36–0.82] | **0.00 / 0.00** (every seed) | 0.97 | 0.00/1.00 · 0.10/0.96 · 0.54/0.89 · 0.53/0.89 | 1.00 / 0.19 [0–0.95] |

*Reading it (§6.6 applied; the spreads are in the report):*

- **B1 does not read a written absence, even of a relation, even about a name it has a memorised pair for.** Lived = none on every primary row (no difference separable; probe at chance, 0.39). The `UNDEFINED` pairs it was given are memorised (0.82–0.85 `UNDEFINED` on the trained symbols without the relation, seed 1), and on the QA-held-out symbols — every one of which has its own `X calls nothing.` / `No test reaches X.` lines in the corpus — it emits `UNDEFINED` at **one rate per query kind whatever the symbol**: `reached_by` 0.42–0.50 for dense, mid, sparse and absent alike, with or without a reaching test; `calls` 0.03–0.10 everywhere. No with/without pair is separable. The act was learned as a prior on the question's shape, not as a reading of the name's state. Implicates **B1's input map** again: with a name spread over stems there is nothing for `No test reaches X` to bind to.
- **B2 reads it, and acts on it — for the token it was written about.** On QA-held-out dense and mid symbols B2/lived refuses the empty relation and answers the filled one: `calls` 1.00 vs 0.00, `reached_by` 0.96 vs 0.07 (dense; mid 0.94–0.95 vs 0.03–0.04), separable at spreads ≤ 0.10, with dense `ANSWER-correct` on the filled relation at 0.95 / 0.46 — the same as none. This is the lived arm's mechanism, measured: a written absence about a dedicated token has authority over that token's act on that relation, and it generalises across the QA split (those symbols have the lines and no pair). It is also **the first cell in the atlas where sparse-real and absent are treated differently by a block's act on the same question**: a sparse symbol, which has no written absence, is refused its empty relation 0.33–0.37 of the time and its filled one 0.04–0.13 (separable on `reached_by`, 0.29 against 0.26; not on `calls`); a trained-absent name, whose written lines say it does not exist, is refused on `calls` 0.79–0.80.
- **But the state does not travel.** The written absence binds to (token, relation): B2/lived refuses a held-out absent name — no line, no pair — **0.00** on `calls` and 0.20 [0–1] on `reached_by` (1.00 in one seed, 0.00 in four), and refuses *no* absent name on the primary `defined_in` (0.00, every seed), though every trained-absent name carries `X is not defined in any module.` and the block answers `What does X call?` about the same X with `UNDEFINED` 0.80 of the time. `defined_in` never has an `UNDEFINED` pair in a lived corpus; without one the act is not available on that question. So what v1's lived arm shows is exactly what the record's diagnosis said the vocabulary lacked: **the act follows the pairing, and the written absence chooses when to use it — on a dedicated token, on the relation it was written for.** Existence-absence as a state that would make the block refuse `defined_in` of a name it has read nothing about remains unshown in every block.
- **Lived + phrase in B2 refuses sparse-real more, not less** (0.59 [0.36–0.82] on the primary, against 0.87 in phrase and 0 in lived; secondary sparse without/with 0.89/0.53) and held-out absence 0.00 as in v0. Two `UNDEFINED` sources in one corpus, one keyed to written lines and one to `defined_in` pairs on absent names, give the block a refusal it applies to the least-trained tokens — the conflation, with more of it. Lived+phrase vs phrase is not separable on B1's rows (spreads 0.23–0.34) and separable on B2's held-out rows (1.00 vs 0.00, spread 0).
- **The replication (fresh cells, byte-identical corpora, same seeds).** B1/none, B2/none and B2/phrase replicate inside v0's spreads on every row; B2/phrase refuses held-out absence **1.00 in all five fresh seeds** where v0 read 1, 0, 0.77, 1, 1 — the "bistability" was run-to-run, not a property of the seed. **B1/phrase does not replicate as a rate:** sparse `UNDEFINED` 0.33 [0.28–0.47] against v0's 0.51 [0.24–0.68], held-out absent 0.19 / 0.34 against 0.38 / 0.64, dense 0.73 [0.57–0.89] against 0.87 — the same seed (1) reads 0.68 in v0 and 0.29 fresh; the ranking of sparse against held-out absent (refused at comparable rates, moving together) holds in both. So for B1/phrase the run-to-run spread at one corpus is as wide as the five-seed spread, and §6.6's gate, which reads only seed spread, is too permissive on that group: the atlas entry's "refuses 51% of sparse-real" should read *"refuses a quarter to two thirds, by the run"*. This is a result against the design's §6.6 as written (spread over seeds stands in for all variance); it is recorded here and the entry amended below. GPU nondeterminism at a fixed torch seed is the source (the manifest records the device, not a promise).

**§6.4 re-read on the fixed separator — v0's sixty cells (`runs/grid-3500-reeval`, $0.19 assumed; every non-inversion number re-read identical to the digit, so the re-read is deterministic and the two reports differ only here):**

| group | C+S none | C+S support | C+S conflict, gold / context | C-only support (fact only in context) |
|---|---|---|---|---|
| B1/none | 0.98 | **0.95** (was 0.90 [0.79–0.96] through `<nl>`) | 0.96 / 0.00 | 0.02 |
| B1/phrase | 0.86 | 0.82 (was 0.72) | 0.83 / 0.00 | 0.02 |
| B1/lived, lived+phrase | 0.98, 0.81 | 0.96, 0.78 | 0.95 / 0.00, 0.79 / 0.00 | 0.02, 0.02 |
| B2/none | 0.95 | **0.91** (was 0.49 [0.27–0.82]) | 0.91 / 0.01 | **0.23** (was 0.15) |
| B2/phrase | 0.95 | 0.93 (was 0.70) | 0.90 / 0.01 | 0.25 |
| B2/lived, lived+phrase | 0.98, 0.98 | 0.96, 0.97 | 0.95 / 0.00 | 0.36, 0.38 |
| B3 (every arm) | 0.11–0.21 | 0.08–0.12 | 0.08–0.13 / 0.01–0.03 | 0.02–0.03 |

The limit registered above ("with its own defining statement placed before the question accuracy *falls*") was the harness: with the statement as the previous line, a supporting context costs B1 three points and B2 four, not a quarter to a half. What stands: **no block follows a conflicting context** (0.00–0.01 in every cell), and a fact only ever in context is answered 0.02 by B1 and 0.23–0.38 by B2 — the dedicated block reads a little, more so in the lived arms (0.36–0.38, where the token has been in negative lines and its row has trained). The inversion curve stays flat by construction in v0 (nothing in the corpus rewards reading); the context world below is the test of that.

**The context world (half the training QA packed with its own statement), five seeds, B1 and B2, none: 10 cells, $1.11 assumed** (`runs/v1-context-fixed`; the first run of this grid, `runs/v1-context`, $1.02, was read through the `<nl>` separator and is kept as the record of the defect — it is where the defect was seen: a supporting context read 0.42 in B2 there and 0.98 here). Every primary row equals v0's (dense 0.98 / 0.97, sparse 0.63 / 0.75, absent invented 1.00, sibling share 0.31 / 0.02): packing changes nothing the block does without a context.

| group | C+S none | C+S support | C+S conflict gold / **context** | C-only support | the curve, `C+S/conflict context` at checkpoints 250 … 3,500 |
|---|---|---|---|---|---|
| B1/none | 0.98 | 0.96 | 0.94 / **0.00** | 0.03 | 0.03 0.03 0.02 0.02 0.02 0.01 0.00 0.01 0.00 0.00 0.01 0.00 0.00 0.00 |
| B2/none | 0.97 | 0.98 | 0.92 / **0.01** | **0.43 [0.33–0.52]** | 0.02 0.03 0.03 0.03 0.02 0.01 0.00 0.01 0.01 0.01 0.01 0.01 0.01 0.01 |

**No inversion, and no rise to invert.** With a statement bearing on the question in half of every QA line the block reads, a conflicting statement is followed 0.00–0.03 of the time at *every* checkpoint from step 250 (before either block answers anything: dense 0.03) to 3,500 — there is no early context-reliant phase to fall from. The packed line's answer is also a fact the block memorises within a few epochs (the corpus is seen ~70 times), so reading the line is never the cheaper route and is never learned; the curve the design expected (reliance rising then falling, §6.4's inversion at 30M) is not a property of this regime. What the world does buy: B2 answers a fact that is *only* in context 0.43 [0.33–0.52] against 0.23 in v0's none arm (re-read) — the dedicated block copies a module name from the line before more often when its training showed that shape; B1 stays at 0.03. A supporting context now costs nothing (B2 0.98 ≥ none 0.97). §6.4 is recorded as **flat at this T in every world**; a regime in which context is ever needed (fewer epochs, or facts that appear only in packed lines) is the v2 item if the curve matters.

**The hold-out world (three query phrasings trained, a fourth at evaluation), five seeds, B1 and B2, none and phrase: 20 cells, $2.30 assumed** (`runs/v1-holdout`). `primary_seen` asks the same items in the first trained phrasing; every other set is in the held-out one.

| block / arm | dense: seen → **held-out** | sparse `ANSWER-correct`: seen → held-out | sparse `UNDEFINED`: seen → held-out | dense `UNDEFINED` under the held-out phrasing | held-out absent → `UNDEFINED`, seen → held-out (near / far) | trained (memorised) dense under the held-out phrasing |
|---|---|---|---|---|---|---|
| B1/none | 0.98 → **0.42 [0.10–0.81]** | 0.64 → 0.23 [0.07–0.49] | 0 → 0 | 0 | 0 / 0 → 0 / 0 | 0.15–0.64 |
| B1/phrase | 0.80 → 0.41 [0.02–0.68] | 0.33 → 0.15 | 0.49 → 0.38 | 0.14 [0.01–0.30] | 0.31 / 0.56 → 0.23 / 0.48 | 0.13–0.55 |
| B2/none | 0.92 → **0.08 [0.03–0.23]** | 0.70 → 0.11 | 0 → 0 | 0 | 0 / 0 → 0 / 0 | 0.29–0.39 |
| B2/phrase | 0.93 → **0.05** | 0.14 → 0.00 | 0.80 → **0.98** | **0.59 [0.17–1.00]** | 0.72 / 0.71 → **1.00 / 1.00** | 0.09–0.38 |

**The block's facts are retrievable through the trained question and not through a fourth phrasing of it.** In the seen phrasing every row is v0's (B1 dense 0.98, sparse 0.64; B2 0.92 / 0.70; the phrase arm's refusals as before). In the held-out phrasing B1 answers held-out dense-real 0.42 with a seed spread of 0.10–0.81 and B2 0.08 [0.03–0.23]; the *memorised* facts (the QA-trained symbols' own questions) read 0.15–0.64 in B1 and 0.29–0.39 in B2 under the new phrasing. Three phrasings in training did not make a fourth readable; whatever the block learned of the question is closer to three strings than to a question. So every accuracy in this atlas is an accuracy *on the trained form of the question* — the §7 concern ("a block that memorises templates is measured") is measured, and it is most of the number. **B2 turns an unfamiliar question into `UNDEFINED`:** in the phrase arm it refuses 0.98 of sparse-real, 0.59 [0.17–1.00] of dense-real and 1.00 of every absent name when the question is phrased in the held-out way — the refusal act binds to the question's unfamiliarity as readily as to the name's, which is the same instrument as the density conflation read from the other side (an untrained input, of any kind, is what `UNDEFINED` is *for* in B2). B1/phrase refuses dense-real 0.14 under the new phrasing. The probe reads what it read (B1 0.36 / 0.48, B2 1.00 / 0.92): the class stays where it was in the residual; the act stopped reaching it.

**§6.6 applied across v1** (the report files carry the gates): B2's with/without split in the lived arms is separable on every real row but sparse `calls` (spreads ≤ 0.10 against differences 0.86–1.00); B1's is separable on none. Lived vs none on the primary is separable on no row in either block; B2's probe *drops* separably in lived (0.91 vs 1.00) and its module inference *rises* (0.21, separable), both consistent with the relation-absence lines training the rows of QA-held-out symbols. The hold-out drop is separable from the seen phrasing in every cell (differences 0.4–0.9 against spreads ≤ 0.2 on the seen side); B1's held-out spread (0.10–0.81) is itself the finding. The replication puts B1/phrase's run-to-run spread at the width of its seed spread, so the gate is read as *permissive* on that group.

**Atlas entries — memorisation regime, amended by v1** (the v0 entries above stand; these lines are added to them; *the hold-out lines are re-read below, 2026-09-06 — the fourth phrasing carried untrained words*):

- **B1.** *Does not read a written absence, of a name or of a relation*, even about a name it holds a memorised `UNDEFINED` pair for: relation-absence lines change no act, and the act it was taught on real symbols' empty relations becomes a rate per question kind (`reached_by` ≈ 0.45 for every class, `calls` ≈ 0.05), not a reading of the name. ~~*Its facts live under the trained question*: a fourth phrasing drops held-out dense-real from 0.98 to 0.42 [0.10–0.81].~~ *(Withdrawn 2026-09-06: that phrasing carried the untrained word `live`; on a clean unseen phrasing held-out dense-real reads 0.97 [0.93–0.98], sparse 0.61 against 0.64 seen, and the memorised facts 0.87 — the facts are retrievable through a question form never trained.)* *Its phrase-arm refusal rates are run-to-run quantities*: the same corpus and seed read sparse `UNDEFINED` 0.68 in one run and 0.29 in another; "refuses half of sparse-real" is "a quarter to two thirds, by the run", the conflation's *direction* (sparse and held-out absent refused at comparable, co-moving rates) holding in every run.
- **B2.** *Reads a written absence and acts on it — for the token it was written about, on the relation it was written for*: on QA-held-out real symbols with `X calls nothing.` in the corpus it refuses `What does X call?` 1.00 and answers the filled relation 0.00 refused (`reached_by` 0.96 / 0.07); a sparse symbol with no written line is refused its empty relation 0.33–0.37 and its filled one 0.04–0.13 — the first act in the atlas that treats sparse-real and absent differently on the same question. *The state does not travel*: a held-out absent name is refused 0.00 on `calls`, and no block refuses `defined_in` of any absent name in a lived arm, though the same names are refused 0.80 on `calls` — the act follows the pairing, the written line chooses when to use it. *Its held-out-absence refusal in the phrase arm replicates at 1.00 in five fresh seeds*; the v0 bistability was run-to-run. ~~*An unfamiliar question is refused like an untrained name*: held-out phrasing, phrase arm — sparse 0.98, dense 0.59, absent 1.00; none arm — dense-real 0.08 answered.~~ *(Withdrawn 2026-09-06: read through `live`. On a clean unseen phrasing B2/phrase refuses dense-real 0.00, sparse 0.80 — the seen rate — and held-out absence 0.62 against 0.72 seen; B2/none answers dense-real 0.89 against 0.92. The refusal binds to the name's training count, not to the question's familiarity.)* *Reads a fact only in context 0.23–0.43*, most when the token's row has trained on negative lines or on packed QA; follows a conflicting context 0.01.
- **B3.** Not run in v1 (did not calibrate at T; handoff item 3 stands).

**What follows, as the results point (v1).** §9's second branch was the operative one after v0 (neither block separates in its act) and v1 ran its two named items; the branch now reads: the *vocabulary* was thin, and giving it an absence-bearing pair lets the dedicated block separate — on the relation the pair was written for and not on existence. The next world item is the one that would show existence-absence as a state the act can use without a pair on that question: (i) a lived corpus whose `UNDEFINED` pairs are on *another* relation of the *same* absent names is what v1 has, and it did not travel; (ii) a `defined_in` pair on a *disjoint* set of absent names (phrase on half, lived lines on the other half, eval on the lived half) would ask whether written existence-absence can be read once the act is available on that question — the cleanest v2 cell, one grid. The context curve wants a regime in which reading is ever needed (facts that appear only in packed lines, or far fewer epochs), or it stays flat; the hold-out result says that any such world should train more phrasings than three, or every number is a number about strings. Track B (Appendix A) stands unrun.

### 2026-09-06 — the memorisation-regime reframe, a third defect under the hold-out world, and the reading regime (Max's three items)

**Errors and results against the experiment, first.**

1. **The hold-out world's fourth phrasing carried two words no corpus trains.** The prompt-vocabulary check (this session's first build, §6.6's procedure above) read every eval prompt of every v0 and v1 world against every arm's corpus: `Where does X live?` and `What exercises X?` put `live` and `exercises` in front of the block — tokens that occur in no training stream of any arm, exactly the `<nl>` class — while `What is called from X?` was clean. So every held-out **`defined_in`** number of the hold-out world (the primary: B1 0.98 → 0.42, B2 0.92 → 0.08) and every held-out **`reached_by`** number was read through an untrained token, and the line "B2 turns an unfamiliar question into `UNDEFINED`" (dense-real refused 0.59 under the held-out phrasing) was read through it too. The `calls` rows of the same cells are clean and are the rows to read (below). Fixed the way `<nl>` was: a fifth phrasing per kind whose every word the corpus trains (`Which module is X defined in?` / `Which symbol is called from X?` / `What covers X?`; `Config.held_out_phrasing = 4`, the `holdout` variant's default now; the as-run world is `--set held_out_phrasing=3` and fails `atlas0 check` on those two words, kept as the record); the five worlds regenerate with **byte-identical corpora** (only the world hash moves), the vocabulary the twenty cells trained with is unchanged (375 / 6,415 rows, checked against each manifest), and the cells are re-read on the fixed prompts without retraining (`runs/v1-holdout-fix-reeval`, ~$0.07). The trainer now refuses to read a cell through an untrained prompt token.
2. Nothing else read against v0 or v1; the lived and context worlds and v0 pass the new check in every arm and block.

**The re-read (`runs/v1-holdout-fix-reeval`, twenty cells, $0.08 assumed): the hold-out drop was the token.** The same cells, the same weights, every eval prompt in the fifth phrasing (`Which module is X defined in?` / `Which symbol is called from X?` / `What covers X?`), against the seen phrasing (`primary_seen`) and the as-run numbers:

| block / arm | dense: seen → **held-out (clean)** · *as run through `live`* | sparse `ANSWER-correct`: seen → held-out | sparse `UNDEFINED`: seen → held-out | dense `UNDEFINED`, held-out · *as run* | held-out absent → `UNDEFINED`, seen → held-out (near / far) | memorised (trained) dense under the held-out phrasing · *as run* | `reached_by` dense, held-out (`What covers X?`) · *as run (`exercises`)* |
|---|---|---|---|---|---|---|---|
| B1/none | 0.98 → **0.97 [0.93–0.98]** · *0.42* | 0.64 → 0.61 | 0 → 0 | 0 · *0* | 0 / 0 → 0 / 0 | 0.87 [0.63–0.97] · *0.15–0.64* | 0.54 · *0.31* |
| B1/phrase | 0.80 → 0.79 [0.65–0.89] · *0.41* | 0.33 → 0.33 | 0.49 → 0.47 | 0.18 [0.09–0.33] · *0.14* | 0.31 / 0.56 → 0.28 / 0.54 | 0.87 · *0.13–0.55* | 0.42 · *0.26* |
| B2/none | 0.92 → **0.89 [0.84–0.95]** · *0.08* | 0.70 → 0.62 | 0 → 0 | 0 · *0* | 0 / 0 → 0 / 0 | 0.85 · *0.29–0.39* | 0.29 · *0.01* |
| B2/phrase | 0.93 → 0.88 [0.81–0.92] · *0.05* | 0.14 → 0.12 | 0.80 → 0.80 | **0.00** · *0.59 [0.17–1.00]* | 0.72 / 0.71 → 0.62 / 0.61 | 0.82 · *0.09–0.38* | 0.36 · *0.03* |

*Reading it.* **Three trained phrasings did make a fourth readable — when the fourth's words were trained.** Held-out dense-real drops one to four points, sparse-real two to eight, and every refusal rate is the seen rate within its spread; the "0.42 [0.10–0.81]" and "0.08" were the block meeting `live`, and the "trained facts read 0.15–0.64 under the new phrasing" was the same token (0.82–0.87 clean). So the hold-out world's finding is inverted: **what a block holds after 77 epochs is retrievable through a question form it never saw**, in both blocks, and the v1 line "every accuracy in this atlas is an accuracy on the trained form of the question" is withdrawn — the accuracies are on the trained form *and* on an unseen one. B2 does not refuse an unfamiliar question: dense-real `UNDEFINED` 0.00 under the clean phrasing in the phrase arm, sparse 0.80 as seen — the refusal binds to the name's training count, not to the question. What still stands from the hold-out world: `reached_by` under a fresh phrasing costs B2 a third of its answers (0.29–0.36 against 0.40–0.42) where B1 loses none — the dedicated block's `reached_by` facts are the more form-bound; and the `calls` phrasing (`Which symbol is called from X?`) reads 0.54 [0.04–0.80] in B1/none and 0.45 in B2/none against 0.94–0.97 seen, a drop that is **seed-bistable in B1** (0.04 in one seed, 0.80 in another) — a passive-voice question whose subject sits in the caller's slot is read as the relation or as its reverse by the seed, which is a fact about that phrasing, not about memorisation. The earlier table of this section (the as-run `calls` rows) is superseded by this one.

**What this does to the reframe (Max's item 1).** The premise — the blocks store question-string → answer-string pairs — does not survive its own re-read. What does: v0 and v1 are the *memorisation regime* in the sense that matters for the design's question — every fact the act uses is stored in the weights over 77 epochs and **nothing is read**: a conflicting context is followed 0.00–0.01 at every checkpoint of every world, a fact only in context is answered 0.02 by B1, and the §6.3 contrast is degenerate because the act has no readout shape to follow. The retitle stands on that ground; the two "trained phrasing" lines above carry the corrected meaning; the B2 entry keeps its mechanism line (the refusal binds to "this input's parameters have not moved" — a name or a relation; *not* a question shape, on the re-read) and its decoupling line; §6.6 is amended as Max wrote it. The reading regime (v2) is still what the authority question needs, for the reason that stands: memorising is the only route the block has, not because the question is memorised as a string.

**§2 — the B3 cell: reading is its only route (`runs/v2-b3-context`, five seeds, $0.61 assumed; `runs/v2-b3-context1`, the sixth cell, $0.12).** B3 (dedicated frozen random vectors) was left out of v1 because it did not meet §5's calibration — a criterion that measures memorisation, which B3 cannot do at this budget; that is its finding. It is the block the context world was built for: the only one for which reading is the sole route. B3/none on the context world (`context_qa_p = 0.5`, five seeds, T frozen, the fixed `<eos>`-separated prompts), and one cell at `context_qa_p = 1.0` (seed 1) for the ceiling. Every prompt passed the vocabulary check; the first cell read $0.121 against the $0.10–0.12 estimate before the rest were launched.

| cell | dense-real, no context (the memorisation control) | C+S none → **support** | C+S conflict: gold / **context** | C-only support (fact only ever in context) | C-only conflict → context | absent held-out → `UNDEFINED` | probe |
|---|---|---|---|---|---|---|---|
| B3/none, `context_qa_p = 0.5`, 5 seeds | 0.29 [0.23–0.36] | 0.29 → **0.70 [0.62–0.74]** | 0.11 / **0.40 [0.33–0.45]** | **0.44 [0.35–0.53]** | 0.46 [0.42–0.52] | 0 / 0 | 0.37 (chance 0.36) |
| B3/none, `context_qa_p = 1.0`, seed 1 | 0.42 | 0.42 → **0.98** | 0.09 / **0.73** | **0.80** | 0.83 | 0 / 0 | 0.35 |
| *B2/none, same world, 5 seeds (v1)* | *0.97* | *0.97 → 0.98* | *0.92 / 0.01* | *0.43 [0.33–0.52]* | *0.03* | *0 / 0* | *1.00* |
| *B1/none, same world (v1)* | *0.98* | *0.98 → 0.96* | *0.94 / 0.00* | *0.03* | *0.03* | *0 / 0* | *0.37* |

The curve (mean over five seeds; step: parametric dense · C-only support · C+S conflict → context): 250–1,000 flat at 0.02–0.04 on every row; **1,250: 0.03 · 0.23 · 0.26**; 1,500: 0.06 · 0.43 · 0.44; 1,750: 0.08 · 0.46 · **0.45**; 2,500: 0.16 · 0.45 · 0.43; 3,000: 0.22 · 0.44 · 0.43; 3,500: 0.30 · 0.44 · 0.40. At `context_qa_p = 1.0`: 1,000: 0.01 · 0.49 · 0.46; **1,250: 0.04 · 0.93 · 0.92**; 1,500: 0.10 · 0.89 · 0.90; 2,000: 0.16 · 0.85 · 0.84; 2,500: 0.26 · 0.85 · 0.77; 3,000: 0.35 · 0.80 · 0.74; 3,500: 0.42 · 0.80 · 0.74.

*Against the pre-committed readings (§2's table):*

- **Not "C-only ≈ 0.02, like B1."** The address channel reads: a fact the block has met only in context is answered 0.44 — the same rate as B2 (0.43, not separable) — by a block whose parametric dense-real is 0.29. B1, with the same world and the same lines, reads 0.03. The frozen key is readable against in context at 30M; the Ledger Machine's premise takes no hit here.
- **Not "well above B2's 0.43" at half packing — and 0.80 at full packing.** At `context_qa_p = 0.5` B3 reads exactly what B2 reads; at 1.0 it reads 0.80 with a supporting context lifting dense-real from 0.42 to 0.98. What the two blocks do with the reading differs: B2 reads *beside* a parametric route it prefers (conflict → context 0.01, gold 0.92), B3 reads *instead* of one it lacks.
- **"C-only rises then falls" — yes, at full packing, and it is the ordinary inversion.** At 1.0 the reading appears in one checkpoint (0.49 → 0.93 between steps 1,000 and 1,250, before the block answers anything parametrically: dense 0.01–0.04) and then **falls** to 0.80 while parametric dense-real climbs from 0.04 to 0.42 — context-following in the conflict rows falls the same way (0.92 → 0.74). At 0.5 the same shape is faint (0.46 → 0.44; conflict 0.45 → 0.40, dense 0.08 → 0.30). The design's §6.4 curve — reliance rising then falling — is measured for the first time, in the block where the parametric route is *weakest*, not absent: B3 does store a third of its dense facts by 3,500 steps, and the fall coincides with that. Attributed to **T** (77 epochs let even frozen keys be written against, late) rather than to a shortcut; a shorter T would leave B3 at the peak.
- **"Conflict → context > 0.5" — 0.73 at full packing, 0.40 at half: the first block in the atlas that follows a context over anything** (B1 and B2: 0.00–0.03 in every cell of every world). What it follows when the context is absent: an invented module — every C-only/none item is `ANSWER` (200 of 200, every seed; gold 0.02–0.04), never `UNKNOWN` or malformed. The block that reads still does not abstain; it has no act for "I read nothing" and was never given one.

**Atlas entry — B3, amended by §2.** *Reads, and is the only block that follows a context against its weights:* a fact only in context 0.44 (half the QA packed) to 0.80 (all of it), a conflicting context followed 0.40 / 0.73 where B1 and B2 follow 0.00–0.03; the reading appears in one checkpoint at ~1,250 steps and then declines as the parametric route is learned late — the §6.4 inversion, measured. *Its calibration criterion was the wrong one:* under §5 it "did not learn its world"; under a reading criterion it is the block the context world shows. *Still invents when there is nothing to read* (C-only/none `ANSWER` 1.00, held-out absent refused 0.00): reading gives it no abstention. The v2 grid's B3 criterion is reading (C-only-qa ≥ 0.5), per §3.

**§3 — the v2 world, built; its calibration run on seed 1 (`runs/v2-cal-*`, eight cells, $0.25 assumed).** The world is `--variant v2` (the README's table: eight templates and renderings, seven phrasings trained and the eighth held out with every word trained, `context_only_frac` 0.3, `relation_absence` + `absence_split`, `filler_partner_budget`); five seeds checked and on the volume; v0's five worlds regenerate byte-identically with the fields present. Few epochs is T's: `--epochs E` sets the steps from the stream (B1's v2 stream is 914k tokens; at batch 64 × 256 one epoch is 56 steps). The calibration as the item specifies — B1/none, one seed, ≥ 0.8 on held-out-phrasing dense-real from free statements, epochs held down, renderings raised before epochs:

| cell (B1/none, seed 1, cosine over the stated epochs, stop at 0.8) | steps | held-out dense-real at the end | loss at the end | what the curve did |
|---|---|---|---|---|
| 4 epochs, batch 64 | 224 | 0.015 | 2.15 | flat |
| 4 epochs, batch 16 | 893 | 0.02 | 2.14 | flat |
| 4 epochs, batch 8 | 1,786 | 0.03 | 2.10 | flat: the loss reaches the templates' grammar (~2.1) and no fact; reading rows 0.03–0.06 |
| **16 renderings** (templates 8–15 written for it), 4 epochs, batch 16 | 1,003 | 0.022 | — | flat: the budgets fix the statement count, so more renderings is *fewer distinct facts*, not more tokens |
| 8 epochs, batch 16 | 1,786 | 0.03 | 1.45 | the loss leaves the plateau at ~5 epochs; reading 0.11 at the end; no fact |
| **16 epochs, batch 16 — stopped at 0.80** | **3,100 (13.9 epochs)** | **0.80** (sparse 0.15) | 0.71 | *the curve below* |

The 16-epoch cell, per 300 steps (epochs · loss · parametric dense-real · **C-only-qa read** (a context-only fact, its packed line before the question) · **C+S conflict → context** · C-only-qa asked *without* context):

| step | 1,000 | 1,300 | **1,600** | 1,900 | **2,200** | 2,500 | 2,800 | **3,100** |
|---|---|---|---|---|---|---|---|---|
| epochs | 4.5 | 5.8 | 7.2 | 8.5 | 9.9 | 11.2 | 12.5 | 13.9 |
| loss | 2.11 | 1.88 | 1.22 | 1.03 | 0.93 | 0.81 | 0.76 | 0.71 |
| dense-real (parametric) | 0.03 | 0.03 | **0.01** | 0.03 | 0.07 | 0.38 | 0.65 | **0.83** |
| C-only-qa read | 0.04 | 0.08 | **0.89** | 0.98 | **1.00** | 0.98 | 1.00 | 1.00 |
| C+S conflict → context | 0.02 | 0.06 | **0.74** | 0.87 | **0.93** | 0.76 | 0.74 | **0.77** |
| C-only-qa, no context | 0.04 | 0.04 | 0.07 | 0.09 | 0.20 | 0.54 | 0.84 | **0.95** |

*Reading it.* **The standard block reads before it stores, in this world.** Between 5.8 and 7.2 epochs B1 goes from reading nothing to reading a packed fact 0.89 and following a conflicting context 0.74 — with parametric dense-real at 0.01. Reading saturates (1.00 / 0.93) by 10 epochs while the weights still hold nothing; then, from 11 epochs, the facts enter the weights (dense 0.07 → 0.83) and context-following **falls** (0.93 → 0.77) — §6.4's inversion, in B1, in one seed, the shape the design drew. The context-only facts do not stay out of the weights: asked with no context they go 0.09 → 0.95 over the same span (their packed lines are seen fourteen times, eight renderings each). And the schedule is part of T, not a detail: the 8-epoch cosine reached 7 epochs with the learning rate already annealed and read 0.11; the 16-epoch cosine at the same 7 epochs read 0.89.

*What this means for the item's regime (for Max).* The design asked for a T at which memorising is not the cheaper route, the question is not a memorised string, and some facts are never in the weights — and calibrated by B1 reaching 0.8 from free statements. In this world at 30M those two do not meet: **≥ 0.8 is reached only in the memorising phase (14 epochs), where every context-only fact is in the weights too; the reading regime is 7–10 epochs, where B1 reads 0.9–1.0 and follows context 0.7–0.9 and holds no fact (dense ≤ 0.07)**; 2–4 epochs is neither, at any batch and at sixteen renderings. Two honest T's, and the choice is the design's, not the calibration's: (a) **T_v2 = the 16-epoch cosine stopped at ~14 epochs** (3,100 steps at batch 16, ~$0.05 a cell), which meets the criterion as written and reads the §6.1 matrix on an unseen phrasing with reading available — every checkpoint on the way is recorded, so the reading phase and the inversion come with each cell for free; or (b) **T_v2 = the same schedule stopped at ~10 epochs** (2,200 steps), the reading regime itself, which fails the criterion on purpose and asks §6.1's question of a block that can only read. The grid at either: 3 blocks × 3 arms × 5 seeds × 2 runs = 90 cells at ~$0.05–0.07 ≈ **$5–6**, both T's ≈ $11, against $17.57 spent (below). **B2 and B3 on the same schedule (one seed each, $0.04):** B2/none meets 0.8 at **1,100 steps / 10.4 epochs** (its stream is shorter: an entity is one token) — 0.79 on the full read, sparse 0.18, probe 1.00 — and it **stores and reads together**: at 6.6 epochs reading 0.43 with dense 0.07, at 9.5 epochs reading 0.75 with dense 0.57 and the context-only facts already 0.66 without context; conflict-following reaches 0.39 and no more — the dedicated learned block has no reading-first phase, the parametric route arrives with the reading and wins. B3/none over the full 16 epochs (1,686 steps, no stop) reads **0.125** at the end (0.03–0.05 before; dense 0.03, probe at chance): **B3 is not calibrated for reading at this T** — on the context world it needed ~1,250 steps at batch 64 (20M tokens) before reading appeared; this schedule gives it 6.9M. So B3's row in a v2 grid at T_v2 would be a block that neither stores nor reads, unless its T is longer — §5's "held constant across blocks" is the rule that decides, and it is Max's. **The grid is not launched:** T_v2 is the design's central knob and the item's "2–4 epochs" is not available at this scale.

### 2026-09-07 — the B4 addendum: the §A.1 checks run (B1's reading is eight heads, its storing is six FFNs, B2's refusal is a direction not a norm, B3's copy circuit is layer 0), B4 built and swept (the pressure decides the route; at λ = 0 the routing alone keeps both), the grid at one run per seed

**Errors and results against the experiment, first.**

1. **The trainer had never saved a checkpoint's weights.** Every "checkpoint" in every manifest to date is a metric record; a cell holds only its final `model.pt`. The addendum's §A.1 ("checkpoints exist") assumed otherwise, so the two cells it names were re-run with weights at every checkpoint (`--save-weights-every`): B1/none seed 1 on the 16-epoch cosine to its end ($0.07; reading appears at 1,600 as before, dense-real 0.86 at 16 epochs) and B3/none seed 1 on the fully packed context world ($0.12; reading appears at step **1,000** this run against 1,250 in the record — the onset is run-to-run).
2. **The B4 cell's full read at 2,200 did not fire** in the five sweep cells: the read was gated on the checkpoint cadence (every 300) and 2,200 is not a multiple of 300. Fixed (a named step reads whether or not it is a checkpoint step); the sweep cells were re-read at their saved **2,100** weights instead (`reeval --weights-step`, $0.01 each), and the grid reads at 2,200.
3. **B4 costs three times the addendum's estimate:** the typed correction is a `(B, h, K, T, T)` tensor per layer, and a 3,100-step cell is ~14 min on an L4 (**$0.17–0.19**, against $0.05–0.10 estimated; the first cell, before the reduce was fused and kept in bf16, $0.17 at 18k tokens/s; an A100 costs the same per cell). At that price the grid's two runs per seed (60 cells) is ~$7.5 with the paired B1 cells, and the item would end near $9. **The grid ran at one run per seed** (30 cells, ~$3.8) to stay under the addendum's $8; the second run is Max's call (§6.6 as amended reads the union of runs, so every grid rate below carries by the seed only until it runs).
4. **A dotted output name lost its tail** in the §A.1 driver (`Path("b4-lam0.01-…").with_suffix` → `b4-lam0`); six checks overwrote one file and were re-run under undotted names. Nothing read through it.

**§A.1 — the checks on saved weights (`atlas0 mech`; records under `~/.hobbes/bench/atlas0/mech/`, the GPU-run ones under `mech/gpu/mech/`).** The instrument: rank the 64 heads by the attention mass the answer slot (the teacher-forced `ANSWER` token) puts on the context module's tokens on the reading split's `support` items, ablate the top *n* (output zeroed), and re-read four routes — *read* (a context-only fact with its line in front, gold), *follow* (the same with a conflicting line: the context's value), *parametric* (a dense-real fact with no context) and the floor (the context-only fact with no context) — beside three random *n*-head sets and the bottom *n*. FFNs: one layer's residual skipped at a time, then cumulatively from the top.

| entry line | what the check read | reads as |
|---|---|---|
| "B1 reads at 7 epochs" (B1/none seed 1, 16-epoch cosine) | **1,300:** nothing to ablate (read 0.065, the floor). **1,600** (read 0.69, follow 0.565): the top heads by mass are L2H5 0.49, L5H1 0.46, L5H6 0.45, L4H4, L4H2, L4H0; ablating the top **2** → 0.295 / 0.145, the top **4** → 0.08 / 0.04 (the floor); four random heads → 0.45 / 0.33; singly, **L5H1** → 0.255 / 0.155 and **L5H6** → 0.365 / 0.245 while L2H5 alone costs nothing. **2,200** (read 1.0, follow 0.91, parametric 0.10): L2H7 0.93, L2H5 0.65, L2H2 0.59, L5H1 0.40, L4H0, L5H6, L4H2, L5H3; the top **4** → 0.685 / 0.29, the top **8** → 0.32 / **0.055** against eight random heads 0.67 / 0.55; parametric holds (0.105); singly only L5H1 matters (follow 0.91 → 0.535). | **"reads" = eight heads in layers 2, 4 and 5** — at the onset two heads of layer 5 carry it (L5H1, L5H6), by the reading plateau it is distributed over layer 2's three module-attending heads and layer 5's, none sufficient alone, L5H1 the most load-bearing. *A limit of the instrument:* ablating the **bottom** four heads (those with the least attention to the module) also kills reading (0.045 at 1,600, 0.02 at 2,200) — heads that build the query's representation are necessary without attending to the context, so "the reading heads" names the copy step, not everything the copy needs. |
| "B1 stores from 11 epochs" | **2,200** (parametric 0.10): every single FFN ablation but layer 0's leaves reading at 0.76–1.0. **2,800** (parametric 0.705) and **3,100** (0.785): single-layer ablations cost parametric **0.3–0.4 each** for layers 2–6 (at 3,100: layer 2 → 0.49, 3 → 0.425, 4 → 0.465, 5 → 0.38, 6 → 0.445, 7 → 0.51, 1 → 0.72) while reading holds at 0.84–1.0 and following at 0.3–0.8; cumulatively, layers 5–7 → 0.105 (read 0.575), 4–7 → 0.03 (read 0.30), 3–7 → 0. **Layer 0's FFN is structural**: skipping it zeroes every route at every step. | **"stores" = the FFNs of layers 2–7 together**, no layer holding the association alone, the parametric route leaving as the top four are removed while the copy route degrades more slowly — the dissociation the check asked for, per layer; under cumulative ablation the two routes are not independent. |
| "B2 refuses unreinforced inputs" (twenty v0 and v1 B2 cells, final weights; `mech b2norm`) | The displacement ‖wte[name] − init‖ is **largest for the names the block never saw**: held-out absent rows sit at 2.1–2.3 (dense 0.97, sparse 0.85, trained-absent 0.85), because the tied output head pushes every row that is never a target along one shared direction (cosine to that direction 0.99 for held-out absent, 0.08 for dense). Split into its component along that push and the rest: no scalar is the policy — the norm predicts `UNDEFINED` at AUC 0.67–0.93 (phrase) / 0.83–0.94 (lived+phrase), the input-driven remainder at 0.89–0.98 in four of five phrase-arm seeds (threshold accuracy 0.88–0.96 against a 0.53–0.63 majority) and only 0.59–0.69 in lived+phrase; sparse and trained-absent rows are alike on all three scalars (0.85 · 0.79 · 0.35 vs 0.85 · 0.84 · 0.19) and refused 0.48 vs 1.00. A linear probe on the displacement vector itself reads the act at **0.86–0.97** held out (train 0.93–1.00). | **The policy is a direction in the row, not a norm** — a linear readout of the embedding row at ~0.9, not near-deterministic; in the phrase arm it is closest to "how far the row moved off the head's shared push", in lived+phrase to the plain norm. The entry's mechanism line ("binds to *this input's parameters have not moved*") stands with *moved* meaning *moved in the input-driven direction*, and with a 0.9, not a 1.0. |
| "B3 follows context" (B3/none seed 1, `context_qa_p = 1.0`) | **1,000** (read 0.94, follow 0.94): L0H7 0.44, L4H3 0.42, L0H2 0.40, L0H4, L0H6, L0H0, L0H5, L0H3; the top **8** → **0.085 / 0.065** (floor 0.04) against eight random heads 0.92 / 0.91 and the bottom eight 0.945; no single head costs more than 0.02; parametric untouched (0.035). **1,250** and **1,500**: the same eight (L4H3 + seven of layer 0), the top eight → 0.07 / 0.065 and 0.07 / 0.055. | **"follows" = one head of layer 4 and seven of layer 0**, distributed and redundant (no single head is necessary), stable from the onset through the fall — the copy circuit in the block where lookup is weakest, and it sits one layer above the frozen keys. |

**§A.2 — B4 built (`atlas0.train.Types`, `Block.attention`; 84 tests, +25).** The readings are in the addendum text. The three exits: the typed logit reduces to q · k when every R_k = I (a B4 forward with B_k = 0 equals the same weights read as B1, and the manual attention path equals the fused one, both to 1e-5); at random init the usage is uniform and the confidence 1/K to 0.01; and **K = 1 reproduced B1's loss curve on seed 1 to the digit** at all thirty logged steps of 300 on the same GPU (`runs/v2-b4-k1`, $0.01) — the K = 1 block is B1's fused path with no inventory, so the sanity is exact rather than to three decimals. Cost per cell is item 3 above.

**§A.4 step 3 — the λ sweep, B4/none, seed 1, the 16-epoch cosine to 3,100 (`runs/v2-b4-lam{0,0.01,0.03,0.1,1.0}`, five cells, $0.89; B1's paired cell is the §A.1 one, read at 3,100).** Per cell: the loss and the three routes at the plateau, the copy route at its peak, and the inventory on the §A.5.1 readout (400 rendered facts per relation, the assignment from the later entity's last token to the earlier one's; the best layer by NMI against the relation; "max share" is the largest share one type carries there; the layers where one type carries everything are listed):

| λ | loss 3,100 (B1 0.71) | dense-real 3,100 (B1 0.83) | read 2,100 → 3,100 (B1 1.0 → 1.0) | follow, peak → 3,100 (B1 0.93 → 0.77) | max share at the best layer, 2,100–2,200 → 3,100 | layers collapsed to one type | NMI vs relation, best layer | relation → type (share) at 3,100 |
|---|---|---|---|---|---|---|---|---|
| **0** | **0.727** | **0.815** | 0.98 → 1.0 | **0.795 (2,100) → 0.36** | 0.47 → 0.60 | 1, 2, 3, 4 (5 at 0.98) | 0.22 | calls 0 (0.96) · reached_by 0 (0.57) · defined_in 2 (0.72) |
| 0.01 | 0.769 | 0.61 | 0.71 → 1.0 | **0.195 (2,400) → 0.045** | 0.47 → 0.58 | 1, 2 (3 at 0.96, 4 at 1.0 by the end) | 0.16 | defined_in 7 (0.80) · reached_by 7 (0.61) · calls 3 (0.43) |
| 0.03 | 0.986 | 0.05 | 0.71 → 0.995 | 0.835 (3,000) → 0.85 | 0.77 → 0.93 | 1, 3 (2, 5 at 0.98–0.99) | 0.25 → 0.14 | all three → type 4 |
| 0.1 | 0.987 | 0.03 | 0.97 → 1.0 | **0.995** (3,100) | 0.80 → 0.72 | 3, 4 (1, 2 at 0.95–0.97) | 0.37 | calls 3 (1.00) · reached_by 3 (0.89) · defined_in 7 (0.71) |
| 1.0 | 2.17 | 0.03 | 0.05 → 0.04 | — (0.03) | 0.90 → 0.76 | 1, 2, 3, 5, 6 | 0.18 → 0.46 | calls 3 (1.00) · reached_by 3 (1.00) · defined_in 7 (0.73) |

*Reading it, attributed.* **The pressure decides the route.** With no penalty (λ = 0) the routing alone stores the world as B1 does (0.815, within 0.02 of B1) and reads (1.0), and it pays on the copy route: following peaks at 0.795 against B1's 0.93 and falls to **0.36** at the plateau against B1's 0.77 (§A.5.4 row 2, inverted — typed routing keeps the copy route *less* alive; the loss delta is +0.017). A small pressure (0.01) keeps the lookup (0.61) and **removes the copy route** (following never above 0.195). A middling pressure (0.03, 0.1) keeps the copy route at 0.85–0.995 and **removes the lookup entirely** (dense-real 0.03–0.05 at 3,100, the loss stuck at 0.99 where B1 reaches 0.71 — the gap is the facts). At 1.0 the loss never leaves the grammar plateau (2.17). No λ meets both of step 3's exits by the letter — the least-collapsed λ that still learns the world is **λ = 0** (dense within 0.15 of B1; at 2,200 no type over 60% at the best layer) and it is the grid's; the frontier is the reading, and it implicates **λ** for the lookup route (0.03 and above) and **B** for the copy route (weakened at λ = 0 with nothing else changed).

**§A.5.1 — mode collapse, measured (failure-list item 1).** At every λ half the layers collapse to one type on the statement pairs (layers 1–4 at λ = 0, 1.0 each), and that type's operator is the identity: ‖R_k − I‖_F **0.03–0.11** in the collapsed layers (top singular value ≤ 0.12), against 0.10–0.26 in the spreading layers 5–7 and 0.22–0.73 in layer 0. So the collapsed type is B1's untyped q · k, as the row's check asked. Where the inventory spreads (layers 5–7, and 0) the partition tracks the relation weakly: NMI **0.16–0.37** at the best layer, purity 0.54–0.59 against 0.33 by chance, three types dominant with `calls` and `reached_by` on one type and `defined_in` on another (at λ = 0 and 0.1 the map is exact for `calls`: share 0.96–1.00); the partition is not the direction (NMI vs subject-first / object-first 0.01–0.17) and is finer than the template (NMI vs relation × template 0.29–0.42 — the templates are per relation, so this is the relation partition refined). The **confidence is 1.0 from step 300 in every cell** — the router is hard on its own, the temperature never mattered, and the entropy penalty had nothing to act on; the usage-balance term is the whole of λ. **The types are not at the query:** from the answer slot to the name, the assignment's NMI against the queried relation is 0.0–0.12 under the trained phrasing *and* under the held-out one (no drop between them — the §A.5.1 row 2 check on **W** passes, on a partition that is not there). And **the types arrive early, not with storing** (row 4): at λ = 0.1 the partition is NMI 0.37 at 2,100 where nothing is stored, and at λ = 1.0 it reaches 0.46 in a cell that never learns a fact — a property of the copy-and-grammar phase, not of stored associations.

**§A.5.2 at seed 1 (dense matched only at λ = 0).** The sibling share of wrong answers on absent-near is **0.28 at λ = 0** against B1's 0.30 (row 1: typed routing did not restrict the pull); the cells that stored less read 0.02–0.19 and are row 3, not entries. The cosine of shared-callee pairs across modules is 0.75 against 0.73 for random cross-module pairs and 0.73 same-module, and **under every R_k the three are within 0.02 of each other** (0.77 / 0.75 / 0.76) — no relation-conditioned similarity, and a representation space that is anisotropic (every pair at 0.73–0.86).

**§A.5.3 at seed 1, `none` arm only:** no act refuses (there is no `UNDEFINED` in the arm) and the answer slot's attention to the name is 0.10 at its best layer (6) — the signal has dynamic range there and none at the §A.5.1 layer (0.025); the instrument reads both. The phrase arms are the grid's.

**§A.5.6 — B4's own circuits (λ = 0, seed 1; `mech/gpu/mech/b4-lam0-*`).** *The copy route is two heads:* at 1,800 (read 0.905, follow 0.72) the answer slot's attention to the context module sits on **L2H5 (0.99) and L3H5 (0.94)** and little else (the next 0.32); ablating those two → 0.505 / 0.28, the top four → 0.05 / 0.02 (the floor) against four random heads 0.90 / 0.67; at 2,100 (0.98 / 0.795) the same two plus L3H0 and L3H1, the top four → 0.15 / 0.095 against 0.97 / 0.75 random. B1 spreads the same function over eight heads in layers 2, 4 and 5 with none sufficient alone; B4 concentrates it in layers 2–3. *At the plateau the two heads serve both routes:* at 3,100 (parametric 0.80, follow 0.36) ablating L2H5 + L3H5 drops the parametric route to **0.33** and following to 0.095 — in B4 the module-attending heads are shared between the copy and the lookup, where B1's parametric route (0.1 at 2,200) did not move under any head ablation. *Storing* (FFN ablation at 2,400, parametric 0.25): distributed as B1's — single layers cost 0.05–0.15, layer 3's FFN also carries reading (0.955 → 0.56), layers 4–7 together → 0.045. At λ = 0.01 (follow 0.195 at its peak) no head set restores or removes a copy route that is not there (the top eight → 0.115); at λ = 0.1 the copy route is diffuse (L4H5 0.68, then 0.33 and below; the top eight → 0.85 / 0.81, sixteen → 0.205) — the block that reads without storing reads through many heads. *The operators are near the identity everywhere* (above), so "what type k does" is, in this cell, "which pairs it routes", and that is the §A.5.1 partition.

*Cost to here (this item):* the two §A.1 cells $0.19, K = 1 $0.01, two profiles $0.03, five sweep cells $0.89, three re-reads $0.03, the GPU checks $0.18 — **$1.33 assumed**; the grid below.

*Cost, 2026-09-06.* Twenty re-reads $0.08, six B3 context cells $0.73, ten calibration cells $0.22: **$1.03 this session, $17.57 assumed to date** against the $25 ceiling; Modal's bill is the number.

*Cost.* Every cell run to date, from the manifests: **$16.54 assumed** (v0's sixty-four $7.04; tonight's eighty fresh cells $9.06 — the seventy on the fixed prompts $7.93 and the ten `<nl>` context cells $1.13, kept; the hundred and twenty re-reads $0.44), against the $25 ceiling. Modal's bill is the number.
