# Test-time training on the derived layer — Olmo 3 7B validation

**Status:** accepted 2026-09-03 (ADR-099) — steps 1–4 built and run on the unseen cell; results in §10 and `benchmark-hypotheses.md` · **Type:** benchmark experiment (preregistered) · **Compute:** Modal
**Depends on:** `hobbes ingest` (derived layer @ SHA), `hobbes plan`/`hobbes run` (unit derivation), `hobbes bench` (harness, ADR-055), DeepSWE 1.1 substrate (ADR-078/079/080)
**ADR:** ADR-099 (this doc is its body)

---

## 0. The question, in one paragraph

Hobbes currently hands a model its derived context *in the prompt*. This experiment asks whether the same context does more when it is loaded into the model's **weights** immediately before the session — a few hundred LoRA steps on the derived layer of the target repo, pinned to the SHA, regenerable, discarded after. If a small clean-lineage model with the repo in fast weights hallucinates fewer symbols and edits the right files more often than the same model prompted with the same material, then "knowledge" is a per-session load and not a pretraining artifact, and the size ladder gets a new floor to find. If it does not, we learn that structure needs to be live in attention, which redirects the crazy pile toward recurrent/looped cores and away from weight-loading. Either result is useful. A null result is a result.

The model is Olmo 3 7B because its lineage is fully open (weights, data, code, checkpoints). That is not a nicety — the whole experiment is about where knowledge lives, so we need to be able to say what the model was and was not exposed to.

---

## 1. Preregistered hypotheses

Numbered to slot into `docs/benchmark-hypotheses.md`. Each carries a kill criterion; a hypothesis that survives is *not confirmed*, it is *not yet killed*.

| ID | Claim | Kill criterion |
|---|---|---|
| **H-TTT-1** (transduction) | Derived context lowers the model's per-token loss on gold diffs. Loading it via TTT lowers it at least as much as prompting it. | TTT arm's gold-diff NLL is not lower than the unaided arm by a margin that survives a paired bootstrap (p < 0.05) on ≥ 40 tasks. |
| **H-TTT-2** (grounding) | TTT reduces hallucinated-symbol rate below the prompted arm on **unseen** repos. | HSR(TTT) ≥ HSR(prompted) on the unseen cell, or the delta is inside the paired-bootstrap CI. |
| **H-TTT-3** (navigation) | TTT raises right-files-edited (Jaccard against the unit's impact set) on unseen repos. | RFE(TTT) not above RFE(prompted) by ≥ 0.10 absolute on the unseen cell. |
| **H-TTT-4** (memorization gate) | Hobbes's lift (either delivery) concentrates on repos the model has **not** memorized. | Lift on memorized repos ≥ lift on unseen repos. (This would mean derived context is not substituting for stored knowledge, and the whole "knowledge-less" thread loses its footing.) |
| **H-TTT-5** (combination) | TTT + prompted context beats either alone. | Combined arm not better than the best single arm on the primary metrics. Non-additivity is itself informative: it tells us the two deliveries carry the same information. |

Solve rate on DeepSWE units is **recorded, not hypothesized**. The ADR-085 pair solved 0/5 and that was fine; solve rate is downstream of navigation and grounding and is confounded by everything else in the harness. We do not gate on it.

---

## 2. Design

### 2.1 Factors

```
model        × delivery                          × repo familiarity
─────────────  ────────────────────────────────  ───────────────────
Olmo-3-7B-I    A0  unaided (no Hobbes)            M  memorized (public, famous)
(primary)      A1  prompted derived context        U  unseen (private / low-star)
               A2  TTT adapter, no context in prompt
Qwen2.5-Coder  A3  TTT adapter + prompted context
7B-Instruct
(comparison,
 already on
 the ladder)
```

Full grid is 2 × 4 × 2 = 16 cells. The **primary comparison is A1 vs A2 on Olmo/U**. Everything else is there to explain the primary result, and the Qwen row can be dropped if compute or time is short — it is on the grid because we already have its harness path from ADR-085 and because H-TTT-4 is sharper with a model we *know* has SWE-bench-shaped priors (C-39).

### 2.2 Repos

Familiarity is not guessed; it is measured (§4.4) before any repo is assigned to a cell.

- **Memorized (M) candidates:** two DeepSWE 1.1 repos with the highest memorization-probe score for Olmo 3.
- **Unseen (U) candidates:** Hobbes itself (multi-language, well-ingested, 3,085 dual-resolved sites) and one or two of Ajax's private repos already used in `docs/extraction-evidence.md`. Requirement: memorization-probe score near floor. Requirement: `hobbes ingest` runs with lane B live for every language in the repo (no syntactic-only graphs — the HSR metric depends on semantic-tier symbol truth).

A repo that lands in the middle of the probe distribution goes in neither cell. Three or four repos total is enough; the unit count per repo matters more than repo count.

### 2.3 Tasks

Two task sources, kept separate in reporting.

1. **Derived units** from `hobbes plan` over real tasks — DeepSWE 1.1 instances for M repos; for U repos, a hand-written proposal set (10–15 per repo) drawn from the repo's own open issues / BUILDLOG items. Each unit carries its manifest: context files, impact set, contracts, policy. These give RFE and HSR ground truth for free.
2. **Synthetic navigation tasks** generated deterministically from the graph (§3.3). These are the same generator used to build the TTT training set, **held out by symbol**: a symbol that appears in a training pair never appears in an eval pair. They isolate "did the weights absorb the graph" from "can the model write a fix".

Target: ≥ 40 derived units and ≥ 300 navigation items per repo. Bootstrap CIs need the count.

### 2.4 What is held constant

- Harness: mini-swe-agent via Pier (ADR-078), same prompt template seam Hobbes already injects through. TTT arms differ from prompted arms *only* in which model endpoint they hit and whether the derived-context block is present in the prompt.
- Sandbox and policy: identical across arms. Policy is enforced below the model; it is not a variable.
- Decoding: temperature 0 for metrics that are graded per token (NLL is computed, not sampled); temperature 0.2, single sample, for agent runs. One sample per (task, arm). Variance is measured across tasks, not across samples.
- SHA: every repo pinned. The adapter is keyed by `(model_id, repo, SHA, recipe_hash)` and regenerated if any of those change — the same rule `.hobbes/derived/` already lives under.

---

## 3. The TTT recipe

### 3.1 Principle

The adapter is a **derived artifact**. It must be regenerable from `(base weights, .hobbes/derived/ @ SHA, recipe)` with no hand-maintained input and no model in the data-generation loop. That keeps it inside the determinism claim: same SHA in, same adapter out (modulo training nondeterminism, which we record — seed, framework version, GPU type).

### 3.2 Training corpus — three renderings of the derived layer

All three are produced by a new `hobbes derive-corpus` subcommand in `pipeline/` (Python, alongside the extractors). Output is JSONL, chat-formatted for the Instruct model.

**(a) Symbol cards.** One record per node in `graph.json`, rendered as a stable template:

```
symbol: pipeline.join.range_join  (function)
file: pipeline/hobbes/join.py:141–203 @ <sha>
called by: pipeline.ingest.run (semantic), pipeline.cli.ingest_cmd (semantic)
calls: pipeline.lanes.lane_a.sites (semantic), pipeline.lanes.lane_b.occurrences (semantic)
tests: pipeline/tests/test_join.py::test_range_join_off_by_one, …
tier of this card: semantic
```

Tiers are printed. If the model is going to learn the graph, it should learn that a `syntactic` edge is a suspicion, not a fact — same rule the reviewer follows.

**(b) Module docs and testmap**, verbatim from `derived/`, chunked to ≤ 2k tokens with file:line provenance preserved.

**(c) Navigation QA pairs**, generated from the graph with deterministic templates. Question families, each with an answer that is *exactly* a graph query:

| family | question shape | answer source |
|---|---|---|
| defines | "Which file defines `X`?" | node → file |
| callers | "What calls `X`?" | incoming semantic edges |
| callees | "What does `X` call?" | outgoing semantic edges |
| tests | "Which tests exercise `X`?" | testmap |
| impact | "If `X` changes, which modules are affected?" | `hobbes plan` impact from seed |
| absent | "Where is `Y` defined?" for `Y` **not in the graph** | "`Y` is not defined in this repo at `<sha>`." |

The **absent** family is not optional. It is the abstention training that OCC-RAG uses and that the Whisper-on-silence failure argues for. Distractor names are generated by mutating real symbol names (case, suffix, plausible sibling) so they are not trivially rejectable.

Corpus size for a Hobbes-scale repo: ~3k symbol cards, ~200 doc chunks, ~10k QA pairs. Held-out symbols (§2.3) are excluded from (a) and (c) before writing.

### 3.3 Hyperparameters (starting point, then sweep only if the primary result is ambiguous)

| | value | note |
|---|---|---|
| method | LoRA, r=32, α=64, dropout 0.05 | attention + MLP projections |
| steps | 300 | ~1 epoch over the corpus at batch 16 × 2k tokens |
| lr | 2e-4, cosine, 30 warmup | |
| precision | bf16 | |
| seed | fixed, recorded | |
| loss | SFT on assistant turns only | |

Step-count ablation (100 / 300 / 1000) is the one sweep worth pre-planning, because "how many steps to load a repo" is itself a finding. Anything else waits.

### 3.4 What we are deliberately *not* doing yet

- Not training on raw source files. The claim under test is that the *derived layer* is the right thing to load. Raw-source TTT is a follow-up arm, not this experiment.
- Not touching the base model's full weights. LoRA only, so the adapter is small (~100 MB), cheap to store per SHA, and cannot be mistaken for a new base.
- Not using a model anywhere in corpus generation. If a rendering needs judgment, it does not go in the corpus.

---

## 4. Metrics

### 4.1 Hallucinated-symbol rate (HSR) — primary

For every agent turn that references a symbol (call, import, edit target, mention in reasoning), resolve the reference against `graph.json` @ SHA.

```
HSR = (references to symbols not in the graph) / (all symbol references)
```

Resolution uses lane A on the model's own output — the same tree-sitter walk, applied to emitted code and to fenced code in prose. Prose mentions are matched by exact token against the node set. **Only semantic-tier nodes count as "in the graph"**; a reference that matches a syntactic-only node is logged separately as *unverifiable*, not as a hallucination. Symbols the model *creates* (new functions in its own diff) are excluded once defined in the diff.

Reported per arm, per familiarity cell, with a paired bootstrap over tasks.

### 4.2 Right-files-edited (RFE) — primary

Jaccard between the set of files the agent modified and the unit's impact set from the manifest. Also report *precision* (did it touch files outside the unit's write partition — which the sandbox should make impossible, so this is a harness check, ADR-077) and *recall* (fraction of impact-set files touched).

### 4.3 Conditional gold-diff NLL — primary for H-TTT-1

For each derived unit with a gold diff (DeepSWE units have one; U-repo units get one by Ajax writing the fix, which also validates the proposal set), compute the model's mean per-token negative log-likelihood of the gold diff given the task prompt, under each arm. No sampling. This is the "is this transduction now" measurement borrowed from ASR. Cheap, deterministic, and it is the one number that directly tests whether context lowers output entropy.

### 4.4 Memorization probe — gate, run first

Per `(model, repo)`, unaided, temperature 0, given only the repo name and top-level path:

1. "List the files under `<dir>`." — precision against the real tree.
2. "What functions are defined in `<file>`?" — precision/recall against graph nodes for that file.
3. 30 navigation QA items (§3.2c families, no absent family) with **no** context.

Score = mean accuracy. A repo is **M** if score > 0.5, **U** if score < 0.15. In between: not used. Report the probe table in full; it is the thing C-39 taught us to check before believing any benchmark.

### 4.5 Recorded, not gated

- DeepSWE solve rate (behaviour verifier, C-39/C-40).
- Tokens per unit, wall-clock per unit, adapter build time and cost.
- Navigation QA accuracy on held-out symbols, per family. The **absent** family is reported on its own: false-acceptance rate on distractors is the abstention metric.

---

## 5. Modal layout

Modal's SDK is Python, so the app is Python; that is also where `pipeline/` already lives, so `hobbes derive-corpus` and the eval scorer share the extractor code directly. The Go side of Hobbes is untouched by this experiment.

### 5.1 Resources

| | |
|---|---|
| `Volume: hobbes-models` | base weights (Olmo 3 7B Instruct, Qwen2.5-Coder-7B-Instruct), pulled once from HF |
| `Volume: hobbes-adapters` | `adapters/<model>/<repo>/<sha>/<recipe_hash>/` — LoRA weights + `manifest.json` (seed, steps, corpus hash, GPU, framework versions) |
| `Volume: hobbes-corpora` | JSONL corpora keyed the same way; the derived layer itself is *not* copied here, only its renderings |
| `Volume: hobbes-runs` | per-run trajectories, scorer output, defect log |

### 5.2 Functions

```
modal app: hobbes-ttt

build_corpus(repo, sha)            CPU · runs `hobbes ingest` (sandboxed, containment stamp
                                   checked) then `hobbes derive-corpus`; writes corpus + hash
train_adapter(model, repo, sha)    1× A100-80GB (or H100) · LoRA per §3.3 · ~10–20 min
                                   writes adapter + manifest; idempotent on key
serve(model, adapter=None)         vLLM · 1× A100-80GB · OpenAI-compatible endpoint
                                   the harness points at this; one deployment per (model, adapter)
score_nll(model, adapter, units)   1× A100-80GB · gold-diff NLL, batched, no sampling
probe_memorization(model, repo)    reuses serve · unaided navigation QA
run_bench(arm, repo, units)        orchestrates: pins endpoint, invokes `hobbes bench run`
                                   with the arm's prompt template, collects trajectories
score_run(run_id)                  CPU · HSR (lane A over outputs), RFE, QA accuracy,
                                   bootstrap CIs; emits a results table + defect register
```

### 5.3 Serving the adapter

Two options; pick by what vLLM supports for the Olmo 3 architecture on the day (verify — LoRA support in vLLM lags new architectures, and the Olmo 3 model ids on HF should be confirmed before writing the pull script):

- **Preferred:** vLLM multi-LoRA (`--enable-lora`), one base deployment, adapter selected per request by name. Cheapest; arms A1/A2/A3 share a GPU.
- **Fallback:** merge the adapter into a copy of the base per `(repo, sha)`, serve the merged weights. ~15 GB per repo on the volume; fine for 3–4 repos. Slightly cleaner scientifically (no LoRA-kernel numerics), so if there is any doubt about vLLM LoRA parity, use this for the primary cells and accept the storage.

### 5.4 Cost envelope (rough, verify against current Modal pricing)

- Adapter builds: 4 repos × 2 models × 3 step-counts ≈ 24 builds × ~15 min A100 ≈ 6 GPU-hours.
- Agent runs: 16 cells × ~40 units × ~8 min ≈ 85 GPU-hours if serialized; batch 4–8 sessions per endpoint and it is ~15–20 GPU-hours.
- NLL + probes: < 2 GPU-hours.
- Ballpark **25–30 A100-hours** for the full grid, well under half of that for the primary comparison alone.

---

## 6. Order of work

Each step has an exit; do not start the next until the exit is met. Steps 1–3 produce numbers before any agent runs — if H-TTT-1 dies at step 3, stop and write it up.

1. **Corpus generator.** `hobbes derive-corpus` with the six QA families, symbol cards, held-out split by symbol. *Exit:* corpus for Hobbes-on-Hobbes regenerates byte-identically from the same SHA; absent-family distractors are not resolvable in the graph (checked mechanically).
2. **Memorization probe.** Both models, all candidate repos. *Exit:* probe table; repos assigned to M / U / neither.
3. **Adapter build + NLL.** Train A2 adapters for one U repo (Hobbes) and one M repo, 300 steps. Score gold-diff NLL under A0/A1/A2/A3. *Exit:* H-TTT-1 alive or killed, with CIs.
4. **Held-out navigation QA.** Cheap and decisive for "did the weights absorb the graph." *Exit:* per-family accuracy and absent-family false-acceptance, per arm.
5. **Agent runs, primary cell** (Olmo, U, A1 vs A2). *Exit:* HSR and RFE with paired bootstrap; defect register started.
6. **Fill the grid** as budget allows, in this priority: A3 on Olmo/U → Olmo/M row → Qwen rows → step-count ablation.
7. **Write-up** into `docs/benchmark-hypotheses.md` (every run, every result, kill status per hypothesis) and a short results section here.

---

## 7. Known constraints and how they are handled

Register entries to open on acceptance (numbers assigned by the register):

- **Nondeterministic training.** The adapter is regenerable in principle, bit-identical in practice only with fixed seed + fixed kernels + same GPU class. Manifest records all three; a rebuild on different hardware is a *different adapter* and is labelled so. (Same shape as the oracle lane's "a different nightly is a different oracle".)
- **Lane-A-only languages.** A repo with any language lacking a live lane B is excluded, because HSR needs semantic-tier symbol truth. Registered as a scope limit, not worked around.
- **Held-out leakage through module docs.** Rendering (b) mentions symbols by name; a held-out symbol may appear in a doc chunk. Mitigation: mask held-out symbol names in (b) with a stable placeholder. Record the mask rate.
- **Probe ceiling.** The memorization probe can under-detect (a model may "know" a repo's idioms without recalling its tree). Treat M/U as a coarse gate, not a continuous covariate, and say so.
- **Instruct-model chat template.** Olmo 3 uses its own template; the harness prompt seam must apply it, and NLL scoring must tokenize identically to serving. One shared tokenization path, tested.
- **Rust repos execute `build.rs` during ingest (C-29).** `build_corpus` runs ingest inside the existing sandboxed extraction process; nothing new, but the Modal container inherits the disclosure.

---

## 8. What each outcome means

| result | reading | next |
|---|---|---|
| A2 ≥ A1 on HSR and RFE (Olmo/U) | knowledge is a per-session load; the derived layer survives being put in weights | shrink the base (Olmo 1B, SmolLM3-3B) until it stops working; that floor is the next experiment |
| A1 > A2, A3 ≈ A1 | structure must be live in attention; weights don't hold graph relations at 300 steps | step-count ablation first; if flat, redirect to looped / recurrent cores and to graph-as-modality |
| A3 > both | deliveries carry different information | characterize which QA families each delivery wins; that split is the spec for a Hobbes-native mid-training run |
| no arm moves HSR on U | derived context isn't reaching the model at all, in either form | harness defect until proven otherwise (ADR-085 precedent: eight harness defects before any model finding) |
| lift on M ≥ lift on U | H-TTT-4 dead; the "knowledge-less" thread loses its empirical footing | say so in the README, as it already does for the size-substitution claim |

---

## 9. Out of scope, on purpose

Raw-source TTT, full-weight fine-tuning, any non-LoRA fast-weight mechanism (TTT layers, Titans), architectural changes, and any model that is not fully open or already on the ladder. Each is a follow-up and each is cheaper to justify once this grid has numbers.

---

## 10. Results (running log — the reading is [`olmo3-ttt-results.md`](olmo3-ttt-results.md); the numbers live in `docs/ttt-cells/`; the standing per hypothesis in `benchmark-hypotheses.md` § H-TTT)

- **2026-09-03 — unseen cell, this repo @ `ebdf7a5`, Olmo-3-7B-Instruct.**
  Gate 0.044 (U). H-TTT-1 not killed: adapter −0.296 nats on 147/147
  units; a shuffled-answers control takes 0.218 of it, the true graph
  the remaining 0.078 on 140/147. H-TTT-5 killed on NLL (A3 = A2).
  Held-out navigation: file 0.01 → 0.98, distractor false acceptance
  0.98 → 0.22, tests 0 → 0.52, callees 0.005 → 0.21, impact 0.03 →
  0.30, callers flat (0.06 → 0.10, p 0.08). Deviations from §6: the
  memorised cell's units come from git history as well as DeepSWE
  (three tasks per repo is not ≥ 40); the doc rendering (b) is empty at
  a base SHA (C-82); the control adapter is an addition. Cell record:
  `docs/ttt-cells/hobbes-olmo3-7b-2026-09-03.md`.
