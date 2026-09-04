# Benchmark verification — the harness plan and the preregistered hypotheses

**Status: preregistered 2026-08-19 (Max; ADR-052); runs recorded
below.** The SWE-bench-class runs of 2026-08-21..24 (H1–H3, results
under each hypothesis; the undecomposed pairs retracted under P12,
ADR-082) and the test-time-training runs of 2026-09-03 (§ H-TTT) have
landed here next to the hypotheses they bear on. No H1 claim has been
earned. This document existed *before* any
benchmark run for the same reason the constraint register exists: a
claim written down after the results arrive can be quietly re-scoped
to fit them, and a hypothesis written down first cannot (P11's
discipline, applied forward). When testing starts, results land in
this file next to the hypothesis they bear on — dated, with the
benchmark, instance set, models, and numbers — the way
`extraction-evidence.md` records extraction runs.

> under the current build this should arguably be the case. however
> that is what testing is for. — Max, 2026-08-19

## The approach: Hobbes as a harness

Verify a large part of Hobbes by using it as a **benchmark harness**:
take a known software-engineering benchmark (SWE-bench-class — issue
in, patch out, hidden tests decide), run each instance through the
Hobbes pipeline (`ingest` → `plan` → per-unit sandboxed execution →
verify), and compare against the same models run **pure** — no
Hobbes, same instances, same patch protocol.

Why benchmarks rather than more dogfooding:

- **Ground truth at volume.** A benchmark instance has a known
  pass/fail answer, and there are hundreds of them. Dogfooding
  verifies mechanisms; it cannot produce a solve-rate curve.
- **A large pure-model pool.** Known benchmarks carry published
  baselines across model sizes, and any baseline not published is
  cheap to reproduce — the comparison Hobbes needs is *same model,
  with and without the harness*.
- **The error stream is the adjustment signal.** Every failed
  instance is labeled data for exactly the numbers the system says
  are guesses: C-35's partition weights get their loss inputs
  (rework, contract failures, context faults — the agent-mapping §6
  loop), a failure class that turns out to be a concession gets a
  register entry, and a repo shape that breaks extraction extends
  `extraction-evidence.md`.

## Method — small models validate the derivation; a diversified set over a full one (Max, 2026-08-22)

A small model (the 7B) fails legibly: low threshold, quick, and easy to
trace. That makes it the **derivation debugger**, not merely a weak
solver — when it fails, a *Hobbes* error (localisation, partition,
per-unit context, contract, human-first) separates cleanly from a
*model* error (cannot implement the spec), because the small model has
little prior knowledge to paper over a weak context with (the inverse of
C-39). A large model can hide exactly the derivation failure we need to
see.

So the derivation is validated **on a small model, across a diversified
*selection* set rather than a full run**: breadth over depth, sampled
across repo shapes and change kinds, to surface the broad space of
Hobbes's own error modes cheaply. The large-model runs (27B, and the
cluster's models later) test the *bar* (H1); the derivation is debugged
small first. This is a methodology commitment, preregistered: a run whose
purpose is derivation-validation is read for *which Hobbes error modes it
exposed*, not for its solve rate.

## The focus benchmark and the bar (Max, 2026-08-21 — preregistered)

**SWE-bench Verified is the focus benchmark**, run on a ladder of
small open models served from the owner's compute (ADR-056/057) —
Qwen2.5-Coder **7B → 32B**, then the family's next rung above 32B
(pinned when taken). Why this ladder and this set: the 7B rung has
**no published Verified score** and is generally discouraged for
multi-step agentic work — exactly the regime derived context is meant
to help — and Verified carries a human-rated `difficulty` per
instance, so "complex multi-step" is the dataset's own label
(`1-4 hours` 42, `>4 hours` 3 of 500), not our proxy.

**The bar, in rung form (H1′):** *harnessed rung N performs comparably
to pure rung N+1 on the complex multi-step set* — Hobbes-on-7B ≈
pure-32B, Hobbes-on-32B ≈ pure-next. "Comparably" is stated before the
run: the harnessed N solve rate on the complex set is within the
binomial 95% interval of pure N+1's on the same instances — at 45
instances that interval is wide, and the report prints the counts so
the width is visible, never hidden in a percentage.

- **Falsified if** harnessed 7B does not close a meaningful fraction
  of the 7B→32B gap on the complex set, or closes it only on instances
  pure 7B already solves.
- **Known biases, both against the harness:** Verified is entirely
  pre-cutoff for these models (C-39 — contamination helps the pure arm
  more: a memorised answer needs no context); and the harness arm's
  lexical seeding (C-36) fails closed, so a `no-seed` instance counts
  as a harness loss.
- **Cost shape:** the complex set is 45 instances × 2 arms per rung;
  the 7B rung fits the free Modal credit comfortably, the 32B rung
  (A100-80GB) is the first thing that may not — the run records
  GPU-seconds per arm so the H3 cost row is real, not estimated.

**Amendment (Max, 2026-08-22) — the next rung is not the 32B.** The
second rung of the ladder is changed from Qwen2.5-Coder-32B to
**Qwen3.8 27B** (`Qwen/Qwen3.8-27B`, pinned in `scripts/modal_vllm.py`
`RUNGS` on A100-80GB; not deployed — the image's vLLM pin predates its
architecture and is bumped when the rung is taken).
Reason stated before any run on it: the model is reported to score
high on instruction following and agentic coding but **low on deep
SWE tasks**, and the focus set is the deep end of Verified — so a
harness gain on it is easier to attribute (the model already follows
tools and instructions; what it lacks is the depth derived context
claims to supply) than on a 32B whose raw SWE depth is closer to
the bar. The bar's rung form (H1′) is unchanged: harnessed 7B ≈ pure
27B, harnessed 27B ≈ pure next. The rung is taken only after a 7B
run's failures are cleanly the model's (the resolve-harness-first
rule); the in-flight 5-fresh re-run is that check.

**The 27B run's settings, declared before the run (2026-08-22,
ADR-074).** Taken after four 7B runs read clean (Results, the last
four entries). Served on A100-80GB by vLLM 0.27.1 with the `qwen3`
reasoning parser and `qwen3_coder` tool parser, window 131,072 (half
the native 262k — the KV pool beside the weights, and the ADR-069
brief then sized to ~45k tokens). Thinking **on** (the model's
default), `reasoning_effort=medium` — a declared guess between the
model's default `xhigh` and the `low` its card warns degrades agentic
tasks; chosen for wall-clock, and if the reasoning reads thin the
follow-up is `xhigh` on the same five, not a different model. Sampling
is the card's thinking-mode setting (temperature 1.0, top-p 0.95) —
the 7B ran greedy; greedy loops this model's reasoning. `max_tokens`
8192 per completion (reasoning and answer share it; the ADR-067 cut
retry gives 16k), 40 turns, 10 units, parallel auto, five instances
concurrently, `--human-first spawn`, the same five instances as the
7B runs. Both arms identical in all of this. What the run can say:
**harnessed 27B vs pure 27B** on a model that can execute is the
informative pair; harnessed 7B ≈ pure 27B is already answered in the
degenerate sense (0 ≈ 0 says nothing).

## The hypotheses

Each is stated with the metric that decides it and what failure looks
like. They are mechanisms the current build arguably implies — argued
below, measured never.

### H1 — Derived context substitutes for model size

**With Hobbes, smaller models perform to the degree of — if not
better than — larger models**, because the hard half of many tasks is
context assembly, and Hobbes hands every agent a derived, checked,
citable slice instead of asking the model to assemble one.

- **Metric:** solve rate across a model-size ladder (small / mid /
  large), each model run pure and harnessed, same instances. The
  quantity of interest is how much of the pure small→large gap the
  harness closes.
- **Falsified if** the harnessed small model does not close a
  meaningful fraction of that gap — or closes it only on instances
  the large model also finds trivial.
- **Mechanism in the current build:** context manifests are computed,
  not assembled by prompt (interior full, boundary contracts,
  one-hop signatures, complement stated); the model never spends
  capability discovering structure the graph already knows.

### H2 — Depth stops costing accuracy

**With Hobbes, deep tasks become more accurate**, because context is
*regenerated per unit* rather than accumulated across the task: a
model's accuracy degrades as context grows and tasks pile up in one
session, and the harness's answer is a smaller job, not a larger
window (architecture, "Where this is going").

- **Metric:** solve rate as a function of task depth — instances
  bucketed by edit spread (files touched), dependency-chain length,
  or step count — pure vs harnessed, same model. The quantity of
  interest is the *slope*: pure models should degrade with depth;
  the harnessed curve should be materially flatter.
- **Falsified if** the harnessed slope tracks the pure slope — depth
  hurting both equally means partitioning is not isolating what it
  claims to isolate.
- **Mechanism in the current build:** the partition bounds every
  unit's context at a budget held below the window ceiling; a deep
  task becomes several bounded units with pinned contracts instead
  of one long accumulating session.

### H3 — Cheaper and faster, as a byproduct

**Hobbes is cheaper and quicker than pure models** — fewer tokens
consumed and produced per solved task — as a byproduct of H1 and H2:
the deterministic layers spend no tokens at all (ingest, plan, gate,
and verification are parsers, indexers, and graph checks), and the
generative layer holds bounded manifests instead of accumulated
transcripts.

- **Metric:** tokens (in + out), wall time, and dollar cost **per
  solved instance** — not per attempt, so a cheap failure cannot
  masquerade as efficiency — at equal or better solve rate.
- **Falsified if** the per-solve cost is not lower, or is lower only
  by trading away solve rate.
- **The honest counter-pressure, stated up front:** multi-unit plans
  add coordination cost (several agents, contract overhead,
  renegotiations), so cross-cutting tasks could cost *more* under
  the harness. H3 claims the deterministic savings dominate; the
  per-depth cost curve is what settles it.

## H-TTT — Test-time training on the derived layer (ADR-099, preregistered 2026-09-03)

The design, the factor grid, the recipe and the order of work are in
[`olmo3-ttt-validation.md`](olmo3-ttt-validation.md); the hypotheses
are restated here so results land beside them. Each carries a kill
criterion; a hypothesis that survives is *not confirmed*, it is *not
yet killed*. Every arm is *model + prompt* under P12 — one agent, no
decomposition — and the experiment measures how derived context is
**delivered**, not whether Hobbes solves tasks; solve rate, when the
agent runs come, is recorded and gates nothing.

| ID | Claim | Kill criterion |
|---|---|---|
| **H-TTT-1** (transduction) | Derived context lowers the model's per-token loss on gold diffs; loading it via TTT lowers it at least as much as prompting it | TTT arm's gold-diff NLL not lower than the unaided arm by a margin that survives a paired bootstrap (p < 0.05) on ≥ 40 units |
| **H-TTT-2** (grounding) | TTT reduces the hallucinated-symbol rate below the prompted arm on unseen repos | HSR(TTT) ≥ HSR(prompted) on the unseen cell, or the delta inside the paired-bootstrap CI |
| **H-TTT-3** (navigation) | TTT raises right-files-edited (Jaccard against the unit's impact set) on unseen repos | RFE(TTT) not above RFE(prompted) by ≥ 0.10 absolute on the unseen cell |
| **H-TTT-4** (memorisation gate) | Hobbes's lift, either delivery, concentrates on repos the model has not memorised | lift on memorised repos ≥ lift on unseen repos |
| **H-TTT-5** (combination) | TTT + prompted context beats either alone | the combined arm not better than the best single arm on the primary metrics |

**Instruments (built 2026-09-03):** `hobbes derive-corpus` (the corpus,
byte-identical from the SHA), `pipeline/scripts/ttt_units.py` (gold-diff
units from git history and DeepSWE tasks, both NLL prompts attached),
`pipeline/scripts/modal_ttt.py` (adapter build, NLL scoring, vLLM serve
with adapters), `pipeline/scripts/ttt_probe.py` (the memorisation gate
and the held-out navigation set per arm). Constraints C-81–C-84.

### Results — H-TTT

#### 2026-09-03 — the unseen cell: this repo @ `ebdf7a5` × Olmo-3-7B-Instruct (steps 2–4; cell record `docs/ttt-cells/hobbes-olmo3-7b-2026-09-03.md`)

**Gate (§4.4):** Olmo 3 scores 0.044 on this repo unaided (files
0.10, definitions 0.00, navigation 0.03) — the unseen cell, well under
the 0.15 line.

**H-TTT-1 (transduction), gold-diff NLL over 147 git-history units,
paired bootstrap:** the adapter (300 LoRA steps on the derived layer at
the base SHA, 0.35 epochs) lowers per-token loss by **0.296 nats
against unaided on 147/147 units** (A2−A0, CI [−0.315, −0.278]); the
prompted block alone by 0.002 overall and 0.009 on the 55 units whose
files the base graph knew (p 0.038); the block on top of the adapter
by nothing (A3−A2 +0.001, p 0.72). **Not killed.** But a control
adapter trained on the same corpus with every answer permuted within
its family — the vocabulary identical, every relation wrong — takes
0.218 of the 0.296 (143/147); the true adapter beats the control by
**0.078 nats on 140/147** (CI [−0.086, −0.070]). So three quarters of
the NLL effect is the repo's names, paths and templates in the weights,
and a quarter is the graph being *right*. The control is an addition
beyond the preregistered grid, made because a 147/147 result on new-file
units (C-84) could not be read without it.

**H-TTT-5 (combination): killed on the NLL metric in this cell.** The
combined arm is not better than the adapter alone (+0.0006, p 0.72,
68/147). Two readings survive: the two deliveries carry the same
information, or the C-55-shaped block (files, symbol names, tests, no
code) carries too little at 7B to add anything — the A1−A0 delta on
context-known units (−0.009, p 0.038) says a little, not nothing. HSR
and RFE (agent runs, step 5) have not been measured.

**Held-out navigation (§4.5) — 2,270 questions about 393 symbols whose
every training mention was removed; scored by what a reply names,
"none recorded" items reported apart:** the base is ≤ 0.06 in every
family with a recorded answer and names a file for **98% of
distractors**. The adapter: defines 0.985 (+0.972), refusal on
distractors 0.776 (**false acceptance 0.98 → 0.22**), tests 0.52
(+0.52), impact 0.30 (+0.27), callees 0.21 (+0.20), **callers 0.10
(+0.04, p 0.078 — not different from the base)**. Every gain is a
module-grain regularity a held-out member inherits from its siblings
(the module's path, the tests that reach the module, what its members
tend to call); the one symbol-grain relation, who calls *this* symbol,
does not come from weights that never saw it — which the held-out design
guarantees they did not. The abstention result is the one that bears on
H-TTT-2 before any agent run: an adapter that learned names did not
learn to invent them.

**The prompted control (the held-out symbol's own card in the
prompt):** the base reads what the card lists (callers 0.68, callees
0.76, tests 0.79), not what it omits (impact 0.14), and the "no card"
note does not make it refuse (false acceptance 0.90). Weights beat the
card on the regularities and on abstention (file 0.985 vs 0.77, impact
0.30 vs 0.14, false acceptance 0.22 vs 0.90); the card beats weights on
every specific edge (callers 0.68 vs 0.10, callees 0.76 vs 0.21, tests
0.79 vs 0.52). Adapter *plus* card (A3) is the best navigation arm
overall (0.61 vs 0.56, p 0.0004) but not additive: it reads the card's
callers a little better than the base and its tests line much worse
(0.37 vs 0.79 — the adapter's prior overrides the text). So on
navigation H-TTT-5's kill criterion is *not* met (the combined arm is
better than either alone) while on NLL it was; the two metrics
disagree, and the record says so rather than averaging them.

**H-TTT-4 (memorisation gate): not readable at this rung.** The
probe (§4.4) put every candidate — httpx, fastapi, textual, and this
repo — in the unseen cell for Olmo 3 (0.02–0.13) and in "neither" for
Qwen2.5-Coder-7B (0.11–0.20); definition recall is ≤ 0.06 for every
model and repo. Neither 7B holds a repo's tree, and Qwen's httpx answer
names the *pre-rename* files, so a "memorised" repo can read as unseen
when the probe's commit postdates the model's copy (C-83, both failure
shapes seen). The cell needs a model that provably recalls a repo (the
27B reproduced xarray's patch verbatim, C-39) — off the table under the
standing policy — or a probe that reads version shift.

**The training sample settles what the weights hold.** On 600 questions
drawn from the *training* set — edges the adapter was shown — it scores
callers 0.15, callees 0.21, tests 0.52: the same as on the held-out
symbols it never saw (0.10, 0.21, 0.52). At 300 steps and 0.35 epochs
the weights hold no symbol-grain edge, seen or unseen; they hold what a
module imposes on its members (its file, the tests that reach it, the
things its members call) and an abstention habit. That is the design
document's second outcome row — *structure must be live in attention;
weights don't hold graph relations at 300 steps* — and its stated next
step is the step-count ablation (100 / 300 / 1,000), before any
redirect toward looped cores or graph-as-modality is drawn.

**Replication on fastapi (unseen for Olmo 3 at 0.129), 68 git-history
units:** A2−A0 −0.223 nats on 68/68 (CI [−0.242, −0.204]); A1−A0
+0.001 (p 0.81); A3−A2 −0.002 (p 0.44) — the Hobbes cell's shape on a
foreign repo at 0.17 epochs (`docs/ttt-cells/fastapi-olmo3-7b-2026-09-03.md`).

**Standing of the five, after this session:** H-TTT-1 not killed (with
the control's caveat that most of the NLL effect is vocabulary);
H-TTT-2 not measured (no agent run; the abstention result is the
closest proxy and points the same way); H-TTT-3 not measured; H-TTT-4
unreadable at 7B; H-TTT-5 killed on NLL, not killed on navigation.
Agent runs (step 5) are not started and are not cleared.

#### 2026-09-03 (later) — the primary cell (review item 9): HSR and RFE over 50 derived units, Olmo-3-7B, this repo @ `ebdf7a5` (`docs/ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md` § Item 9)

`hobbes plan` over 28 hand-written proposals → 50 derived units; one
file-tools-only agent per unit per arm (no exec in any arm; every arm
*model + prompt*, P12); base and the 300-step adapter. **HSR** A0 1.00 ·
A1 0.82 · A2 0.92 · A3 0.80; **RFE Jaccard** 0.00 · **0.41** · **0.01** ·
0.43 (precision 0.95 / 0.82 for the aided arms; recall 0.41 / 0.55).
**H-TTT-2 killed:** HSR(TTT) − HSR(prompted) = +0.11 (n 20, CI [−0.05,
+0.29], p 0.18) — the kill criterion's "≥, or inside the CI" is met
either way. **H-TTT-3 killed:** RFE(TTT) − RFE(prompted) = −0.40 (CI
[−0.53, −0.28], 1/26). **H-TTT-5** not survived on the agent metrics
(A3−A1: HSR −0.07 p 0.37, Jaccard +0.02 p 0.76, recall +0.13 p 0.08).
The adapter alone writes into paths that do not exist and read like this
repo's, and a third of its sessions were stopped for repeating a call:
repo language without repo structure, the §5 finding at the agent grain.
Design §8's second row stands. Five harness defects registered in the
record (D-1 no exec and no test run, D-2 the tool-call parser, D-3 the
extractor's first version, D-4 the small HSR denominator, D-5 shared
unaided runs).

**Standing of the five after the cell:** H-TTT-1 not killed (unit-only
intervals, most of the gain repo language, the graph's share bounded);
**H-TTT-2 killed; H-TTT-3 killed;** H-TTT-4 unreadable at 7B (the
version-aware probe finds no memorised cell either); H-TTT-5 killed on
NLL under the commit-message conditioning and on the agent metrics,
not killed on navigation and under a task-statement conditioning by
0.008 nats.

#### 2026-09-03 (evening) — the step sweep past one epoch (review item 5) and the last controls (items 3, 6); `docs/ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`

Adapters at 100 / 300 / 1,000 / 3,000 steps on the same corpus, seed
0, and 3,000 on a four-paraphrase corpus. **Callers on trained
symbols: 0.10 / 0.15 / 0.33 / 0.95** (1,000−300 +0.18, 13/0; 3,000−1,000
+0.62, 36/1); callees 0.02 / 0.21 / 0.51 / 0.90; tests 0.03 / 0.52 /
0.72 / 0.95; held-out callers 0.05 / 0.10 / 0.19 / 0.27, held-out impact
0.12 / 0.30 / 0.35 / 0.66. Paraphrases at 3,000: trained callers 0.86,
held-out within noise of single-template. **Gold-diff NLL over the same
adapters: −0.30 / −0.30 / −0.20 / +0.02.** The preregistered first
reading holds (edges enter with exposure; cost per repo ≈ 1.7 A100-hours
at 3,000 steps) and the second does not (diversity was not the recipe's
problem); the NLL and navigation metrics are anti-correlated in step
count. The **shuffled-all** control (item 3) — 0.226 nats off the diff —
scores the base's numbers on every navigation family (defines 0.09,
false acceptance 0.97): the NLL gain is the tokens, every navigation
gain is the consistent graph. Three seeds (item 6) agree on every
navigation family but tests (0.36 / 0.52 / 0.57); the NLL comparisons'
intervals are unit-only.

**Standing of the five at the end of 2026-09-03:** **H-TTT-1** not
killed on its criterion, but what the criterion measured is now known
to be a sub-epoch language effect that a control without the graph
reproduces and that is gone by the time the graph is in the weights —
the hypothesis as *written* ("derived context lowers the loss") is
true of the tokens, not the structure. **H-TTT-2 killed. H-TTT-3
killed** (the primary cell, at 300 steps; the 3,000-step adapter is
not yet run through it). **H-TTT-4** unreadable at 7B. **H-TTT-5**
killed on NLL under the commit-message conditioning and on the agent
metrics; not killed on navigation or under a task statement. The
design's §8 second row — structure must be live in attention — stood at
300 steps and is now bounded: structure *can* be put in the weights at
3,000, at the loss gain's expense; whether an agent under that adapter
finds its files is the open question, and the next cell.

#### Follow-ups from review — preregistered 2026-09-03, before any of them ran

Max's review of the 2026-09-03 results set ten follow-ups (`docs/olmo3-ttt-results.md`
§10 carries the closing line and the record for each). The readings
below were written **before** the numbers, under the same rule as the
grid; a corpus, scorer or recipe change bumps its hash, and no existing
cell record is edited — a dated addendum or a new record sits beside
it. Compute stated first: the review's budget is ~10 A100-hours; this
session's estimate for the same list is ~9 GPU-hours **without** the
10,000-step point of item 5, which alone is ~6 A100-hours at the
measured 2.2 s/step and is held for Max's call.

1. **A2's NLL gain by C-84 population (known-file / new-file), lookup.**
   New-file units have no node in the base graph, so A2−A0 there bounds
   the vocabulary share independently of the shuffled control.
   *Readings:* A2−A0 on new-file ≈ control−A0 (within CI) → the two
   vocabulary estimates agree and "a quarter is the graph" stands;
   A2−A0 on new-file ≈ A2−A0 on known → the graph's share is near zero
   and results §3 is rewritten to say so; A2 gains *more* on new files
   → something else is being learned (style, formatting) — a constraint
   is opened, not an explanation written.
2. **The NLL conditioning, stated, then varied.** The first run's prompt
   held the commit subject and body and the target path (a *message*
   conditioning; the results did not say so — registered as a reporting
   defect). New rows of the same metric: *none* (the path only) and
   *task* (a proposal in a task's words: fastapi's two DeepSWE
   statements, and hand-written proposals for this repo's commits), each
   with its own n. *Readings:* A2−A0 shrinks as conditioning tightens
   (none > message > task) → the adapter's gain is mostly what a task
   statement supplies anyway; transduction happens in the prompt, not
   the weights. A2−A0 stable while A1−A0 grows under *task* → the
   adapter holds repo language, the prompt supplies task binding, and
   they are separable — H-TTT-5 stays alive on NLL. Nothing moves → the
   diff is predictable from repo language alone at this granularity and
   NLL is dropped as a primary on git hunks.
3. **The shuffled control's cards.** Lookup result: `--control shuffled`
   permuted card *bodies* as wholes, each still opening with its own
   symbol and its own true edges — every true edge stayed in the control
   corpus under the wrong question. A `shuffled-all` control permutes
   the edge lines across cards within a module (module-shaped
   regularities kept, every specific edge broken); one adapter, 300
   steps, seed 0. *Reading:* true − shuffled-all is the graph's worth;
   larger than −0.078 → the results understated it; equal → cards add
   nothing beyond QA and the card rendering can be dropped.
4. **Abstention: instruction on the base (A1r) and on the adapter
   (A3r).** The card plus "if the symbol is not listed, say it is not
   defined at this SHA; do not guess a file", all six families and the
   393 distractors. *Readings:* base FA under A1r ≤ 0.30 → the adapter's
   abstention is mostly instruction-following and the design's §3.2(c)
   "mid-train for abstention" argument weakens to "instruct for
   abstention"; base FA under A1r ≥ 0.6 while A2 stays 0.22 → abstention
   entered the weights in a way instruction does not reach; A1r drops
   has-truth families → that is the instruction's cost, reported.
5. **Steps past one epoch, with paraphrases; the null written first.**
   At ≤ 1.2 epochs of single-template exposure a flat callers-on-trained
   is consistent with under-exposure and does not test whether edges
   can enter the weights (Allen-Zhu & Li, *Physics of LMs 3.1*; Ovadia
   et al.). Points: 100 (done), 1,000, 3,000 single-template, and 3,000
   on a `--paraphrases 4` corpus (each fact in four question and answer
   phrasings; new corpus hash); 10,000 held (cost above). For every
   adapter: NLL over the 147 units, the held-out set, the 600-question
   training sample. *Readings, on callers-on-trained:* rises with steps
   → edges enter with exposure and the question becomes cost per repo
   (held-out callers says whether anything generalises); flat
   single-template but rises with paraphrases → the recipe was the
   problem and paraphrase diversity becomes a corpus default; flat under
   both while NLL keeps falling → weights hold vocabulary and
   regularities at this scale and no more, results §1 is confirmed, and
   the design's "structure must be live in attention" row is the
   standing conclusion. Callers vs callees on trained symbols reported
   at each point; callers below callees at every point is noted as
   reversal-shaped and left.
6. **A second seed** for the 300-step adapter (and the headline
   ablation point if item 5 lands first): NLL and held-out nav;
   seed-to-seed |Δ| beside each bootstrap CI. If |Δ| on any primary
   exceeds its CI half-width, that metric's CIs are relabelled
   *unit-only* and a third seed is queued.
7. **A1 defines 0.77 with the path on the card — scorer audit.** Lookup
   result: the failures are basename answers (`proxy.go` for
   `go/internal/proxy/proxy.go`). A scorer v2 accepts a path-shaped
   token that is a `/`-boundary suffix of exactly one known path; every
   navigation arm is rescored, scorer version in the record, old numbers
   kept. *Reading:* A1 defines ≥ 0.95 under v2 → "the card reads what it
   lists" is strengthened and the A3 tests collapse (item 8) sharpens,
   since A1's tests number likely rises too.
8. **The A3 tests collapse (0.37 vs A1 0.79 with the same card) named
   as a finding — a trained prior overriding live text, made in 300
   steps.** Probe: join A3's tests failures → symbol → module → the
   fraction of that module's training cards whose tests line is "none
   recorded"; the same for impact. *Readings:* most overrides come from
   ∅-heavy modules → the adapter learned "this module has no tests" as
   a fact and disbelieves the card — a corpus-design lesson (∅ answers
   down-weighted or phrased "none recorded at <sha>") and a small clean
   demonstration of trained priors defeating context; uniform across
   modules → a general "answer none" bias from the absent family, tied
   to item 4. Either way the agent runs (item 9) must watch for the
   adapter ignoring the manifest, not only inventing symbols.
9. **The primary cell — HSR and RFE, this repo @ `ebdf7a5`, ≥ 40
   derived units, arms A0/A1/A2/A3, plus `manifest_ignore`** (turns
   where the manifest names a file or test and the agent asserts it does
   not exist or edits elsewhere). Every arm *model + prompt* under P12.
   *Reading:* the design's §8 table, plus one row — A2 lower HSR but
   higher manifest_ignore than A1 → the adapter is grounded in the repo
   and less grounded in the task, the trade item 8 predicts, and it
   decides whether TTT belongs under the harness at all.
10. **A version-aware memorisation probe.** File-tree items scored
    against the union of trees across the repo's tagged releases (≤ 30
    tags), `score_at_sha` and `score_any_version` reported apart with
    the best-matching tag; generic names (README, LICENSE, `__init__.py`,
    …) dropped from files-precision, raw and stoplisted both reported.
    *Reading:* Qwen's httpx `score_any_version` ≥ 0.5 → an M cell exists
    at that older SHA and H-TTT-4 goes from unreadable to runnable at
    7B; nothing crosses 0.5 → §6's conclusion stands and the probe is at
    least no longer blind to version shift.

## The harness (ADR-055, built 2026-08-21 — quota-free, unrun)

`hobbes bench` is the machinery: `select` applies the instance protocol
(a `created_at` cutoff and filters, every drop counted), `run` checks
each instance out at its base commit and runs the **pure** arm (Claude
Code, its own tools, no Hobbes) and the **harness** arm (`ingest` →
`plan` with the issue as the proposal → `run` → the integration
branch's diff) per model, `--evaluate` hands the patches to the pinned
`swebench` evaluator, and `report` lays the records against H1–H3
below without interpreting them. Architecture §6.2 is the description
of record. Three things the harness fixes in advance so a result
cannot bend them:

- **An instance that seeds nothing is a harness failure** (`no-seed`),
  counted in the harness arm's denominator. Dropping it would inflate
  the arm under test.
- **H3 is per solved instance over observed terms.** A session that
  emitted no usage envelope is recorded unobserved and the row says how
  many; a zero is never shown for a number nobody saw.
- **The planner hit is scored after the arm, never inside it** (harness
  restructure phase 3, 2026-08-22). A staged record (`--stages`,
  ADR-059) carries `seed_source` and whether the planner's named files
  reach a gold-patch file, computed by `results.py` from the gold patch
  no session saw; `report` splits the staged harness by `seed_source`
  with the hit-rate beside the solve rate. It answers "did the planner
  find the place?" before any verdict exists — and it is a proxy, since
  the gold patch is one solution (C-49). Phase 4's probe reads this
  column first.
- **Depth is the rated band where the dataset has one** (Verified's
  `difficulty`: `<15 min fix` 194, `15 min - 1 hour` 261, `1-4 hours`
  42, `>4 hours` 3), else the gold-patch file-count proxy, and every
  report says which. `hobbes bench select --difficulty complex` is the
  45-instance focus set.

## What has to be true before a run — the current gaps

Reflecting the build as it is, not as the plan wants it:

1. **The sandbox cannot run Claude Code yet.** D2 (ADR-054) consumes a
   change-spec end to end, but no session has ever been spawned live:
   the session image is Alpine (musl), the `claude` binary is
   glibc-linked and not mounted into the container, and the session
   network is `none`. A route to the network is exactly what the
   sandbox's enforcement story says is absent, so granting one is the
   owner's decision and a register entry when taken (ADR-055 lists the
   items: glibc image, binary mount, credential, network mode, and
   the pure arm's containment).
2. **C-36 will bite, and the shape is now measured once.** Eight
   `psf/requests` instances (Verified), checked out and ingested,
   quota-free: 8/8 seed lexically; the seed set touches a gold file in
   4/8. Misses: dotted `package.function` names (`requests.get`) match
   no symbol *name*; trailing punctuation makes prose look code-shaped;
   generic words seed spuriously. Candidate adjustments are parked in
   `future_additions.md`; the loop adjusts from verdicts, not from one
   probe.
3. **Instance selection must respect contamination** — now bounded,
   not proven (C-39). Verified's newest instance is 2023-08-07; a 2025
   cutoff selects zero of 500, so a live run on a contemporary model
   needs SWE-rebench or SWE-bench-Live, recorded in `run.json`.
4. **The evaluator needs a container engine** (C-40): rootless podman
   through its socket, SWE-bench's per-instance images pulled on first
   use.
5. **P11 governs the claims.** A result on one benchmark licenses
   that benchmark's shape, not "Hobbes makes small models better."
   Every result entry below names its sample.


## Run note — the first 7B complex-set pass (2026-08-21)

The first live pass runs the 45-instance complex set on the 7B rung
(`--max-turns 20 --max-units 10`, both arms in each instance's swebench
image). Getting the harness to produce a candidate at all took five
fixes (ADR-058); it now does. **Reading rule set before the numbers
(P11):** the pass **need not finish** — the **first 10–20 completed
instances are the decision point**. A drastic outcome (harness solve ≈
0, or harness far below pure) is a signal to refocus the harness
(future_additions: unit selection, harness re-evaluation), not to
re-scope H1/H2/H3. Interpretation still lands in the Results section
below, dated, once verdicts exist — the hypotheses do not move.

## Results

**P12 (ADR-082, 2026-08-23) — a Hobbes test decomposes.** Every Pier
result below (ADR-078..081) and `five-fresh-7b-aided-fix` ran **one agent
on the whole task with an added prompt**: no planner (Pier), no split, no
window smaller than the task. They are **retracted as Hobbes evidence** and
stand only as *model + prompt* observations and harness/instrument work.
The decomposition is the product; without it none of H1–H3 can show.

**Standing reading rule (C-56, 2026-08-22):** a pure score is a mix of
repo recall and reasoning that the score does not separate (C-39 found
this at the verbatim-patch grain; it holds at the partial, repo-familiarity
grain on original tasks too), and the aided arm's prompt is
off-distribution for the model. No table below is a like-for-like
"Hobbes vs none" until a pure score carries its familiarity-probe line
and the aid has been tested in an observation shape.


None yet. The harness exists (ADR-055, 2026-08-21); no live run has
been made — the first one starts when Max settles the session-image
and network question and names the instance set and model ladder.

### 2026-08-22 — the planner probe (harness restructure phase 4, step 1)

`hobbes bench run --stages plan` on astropy-13398 and astropy-13579,
Qwen2.5-Coder-7B on Modal, harness arm only — the question was
narrow: *can a 7B, given the issue and the graph's standing context,
name the place?* Read by the planner hit column (C-49), not by any
verdict. Three attempts, each stopped by a harness finding, the
third clean:

| attempt | 13398 (gold 4 files) | 13579 (gold 1) | what stopped it |
|---|---|---|---|
| 1 | planner died in 1 s, no tokens | — | the C-43 pre-command failed on the `ro` worktree (ADR-060: overlay) |
| 2 | `files: []` → lexical-fallback, miss | `SlicedLowLevelWCS.world_to_pixel` unresolved → miss | handoff parser keyed only `files:`; no dotted-name rule |
| 3 | **hit 1/4** (`builtin_frames/itrs.py`), `seed_source: planner` | **hit 1/1** (`wrappers/sliced_wcs.py`) | — |

Both planners took **2 turns, ~9k input tokens, ~10 s** and made
**one tool call — the `reflect` itself**: neither touched a knowledge
tool or read a file; the names came from the issue text and the map.
The 13579 planner named a package dir (`wcs/wcsapi.py`) as a file and
the gold module only through a symbol; the 13398 planner named four
plausible neighbours of which one was gold, and missed the file the
patch *creates* (`itrs_observed_transforms.py`) — a created file can
never be named from the graph, and the hit-rate's denominator counts
it (noted under C-49).

**Unit interiors vs gold, re-derived offline on the probe workspaces
(deterministic, quota-free) after the third fix — the planner's seeds
now *replace* the lexical layer instead of joining it (attempt 3 had
joined them, re-admitting `input`/`frame`/`isinstance` and making the
plan the capped repository again):**

| instance | cap | gold files inside spawned units | deferred |
|---|---|---|---|
| 13398 | 20 | 3/4 (`__init__`, `itrs`, `intermediate_rotation_transforms`) | 50 |
| 13398 | 10 | 2/4 (`__init__`, `itrs`) | 60 |
| 13398 | 5 | 1/4 (`itrs`) | 65 |
| 13579 | 20 / 10 / 5 | 1/1 (`sliced_wcs`, in a 4-file unit with `base`, `__init__`, its test) | 41 / 51 / 56 |

The seed-bearing gold unit survives every cap (select-then-cap, C-44,
doing its job); the neighbour gold files go first. Two to four seeds
still expand to 60–70 modules, so the cap binds — C-35's grain, now
measured on the planner path. **Reading: the unlock works on these two
— the planner found the place both times — and the next number is the
solve.** Not a result for H1–H3 (n=2, planner-only); the full-stage
run on the same two instances follows, then the 45-set.

### 2026-08-22 — the full-stage run (phase 4, step 2), astropy-13398 & 13579

Both arms, 7B, `--stages plan,implement,verify --max-units 10
--max-turns 40`, evaluated by the pinned swebench 5.0.2 run **locally
over the rootless-podman Docker socket** (its `--modal` path is broken
upstream — C-50). **n=2, not an H1–H3 result** (P11); recorded as the
first end-to-end verdicts the harness has ever produced.

| instance | planner hit | harness verdict | pure verdict |
|---|---|---|---|
| astropy-13398 | 1/4 gold | unresolved (patch applied, F2P failed) | unresolved |
| astropy-13579 | 1/1 gold | unresolved (patch applied, 41/41 P2P pass, 1 F2P fails) | unresolved |

**0/2 both arms.** The planner found the place both times (hit 100%,
mean gold recall 62%); neither the harnessed nor the pure 7B turned
that into a passing fix. On 13579 the harness patch applied cleanly and
kept all 41 PASS_TO_PASS green but did not make the one FAIL_TO_PASS
pass — a real near-miss, not a broken patch. The pure 7B on both
instances edited an invented file (`coordinates/transforms.py`) or a
test file, never the source.

What the run cost in harness wall time and what inspecting it fixed is
in the BUILDLOG (2026-08-22, forty-first..forty-third): the implement
stage ran 21–36 min, ~45% of it on prose turns and no-op exec repeats,
now capped (`--max-tokens`, exec-repeat refusal). **Reading:** the
unlock (planner naming the place) holds; the 7B *implementer* is the
wall on these two — which is H1's actual question and needs the 45-set,
not two instances, to answer. The evaluator now works, so the set can
run.

### 2026-08-22 — the ADR-062 re-probe (harness arm only), astropy-13398 & 13579

Harness arm re-run after the planner handoff became per-unit
(ADR-062), sequential (pre-ADR-063 code), same flags, local eval.
**n=2, not an H1–H3 result** (P11). The pure-arm verdicts above stand.

| instance | planner hit | implement wall | patch | verdict |
|---|---|---|---|---|
| astropy-13398 | 1/4 gold (again) | 1,523 s (was 2,148) | 6 files, +201/−2,998 | unresolved |
| astropy-13579 | 1/1 gold (again) | 670 s (was ~1,250) | 1 file, +28/−300 | unresolved |

**0/2.** What the trace verified (every unit's brief, tool-call log and
branch read by hand — BUILDLOG forty-sixth):

- The projection works as a mechanism: each unit's inbox carried only
  its slice or a plain "nothing named is yours"; the Interior section
  was never cut.
- **The owner unit now acts on its own file** — 13579's U10 (interior
  `sliced_wcs.py`, idle last run) edited it in 47 s / 2 turns. It
  issued `pytest` and `write_file` in **one completion**, never called
  `read_file`, and replaced the 308-line module with a bare 36-line
  function. Its summary claimed it "modified the method".
- That is the pattern, not a one-off: on 13398 the merged units
  U2/U7/U9 called `write_file` on files they **had not read**
  (`transformations.py` −1,646 lines, `funcs.py`, `baseradec.py`);
  the gold file's owner U10 read `itrs.py` ten times and made seven
  `edit_file` attempts, none of which landed.
- Units told "nothing named is yours" did **not** hand off a no-change:
  on 13579 three of them returned prose plans to edit the owner's file
  (zero tool calls, 14–62 s each); on 13398 four of them `write_file`'d
  their *own* interiors — files the change did not need.

**Reading (no claim beyond this):** ADR-062 removed the harness's
mis-aim; what it exposed is that this 7B, given the right target,
overwrites unread files. Whether that is the model or the loop's tool
surface (`write_file` = "create or overwrite", no read-before-write
rule, a nudge that says act) is **not separable from two instances** —
a loop-side guard applied to both arms is the next harness decision,
and the non-owner note's `approach` line is a candidate for removal.
The loop keeps no transcript; a trace stops at the tool call.

### 2026-08-22 — the ADR-064 re-run (both arms), astropy-13579

Both arms, 7B, `--stages plan,implement,verify --parallel auto
--max-units 10`, local eval, after ADR-064 (transcript, task-tailored
selection, read-before-overwrite). **n=1, not an H1–H3 result** (P11).

**0/1 both arms** (harness patch 1 file, pure patch 2 files; both
unresolved). What the three mechanisms did, each verified from the
record and the new transcript:

- **Selection (C-52) worked and paid off:** of 10 units, **2 were
  spawned** (U5, U10 — the planner-named ones), 7 skipped as
  "planner named no file in interior", 1 human-first. Implement wall
  **274 s** (was 670 s on the same instance last run) — the do-nothing
  sessions are gone.
- **Parallel gate (ADR-063) worked, no overlap here:** the endpoint was
  detected as vLLM → 4 workers, but the two live units are a contract
  chain (`waves [[U5],[U10]]`), so `implement_wall_seconds 274 ≈
  implement_units_sum 273` — nothing independent to run at once. The
  lever is correct; this instance had no work for it.
- **Transcript (ADR-064) worked:** 62 KB of U10's full message list,
  the first time the model's own reasoning is readable turn by turn.
- **Read-before-overwrite worked as specified and did not change the
  outcome:** U10 called `write_file` on the unread `sliced_wcs.py` →
  **refused**; it read the 308-line file (transcript: "I'll read the
  file first"), then wrote a **1,088-byte stub replacing 308 lines**
  anyway. The guard forces a read, not comprehension — exactly the
  boundary the ADR named. It then looped the identical stub and the
  pre-existing repeat-refusal stopped it (the loop is the model's, not
  the guard's).

**Reading (no claim beyond n=1):** the harness now aims one unit at the
exact gold file, forces it to read that file, drops every unit that has
no work — and this 7B still answers by overwriting a 308-line module
with a stub. On this instance the model, not the harness, is the wall,
and the measurement is now clean of the harness faults that used to
confound it. Whether that holds is the 45-set's question. Open, for
Max: the stub is a `write_file`-shaped failure a `read`-gate cannot
catch; a size-delta refusal (reject a whole-file write that shrinks a
read file past a fraction, both arms) is the next candidate, but it is
tuning against one instance until the set runs.

### 2026-08-22 — the 5-fresh-instance set (both arms), django/sympy/xarray/sphinx/scikit-learn

Both arms, 7B, `--parallel auto --instance-workers 5` (ADR-063/065),
local eval. First multi-repo sample. **n=5, not an H1–H3 result**
(P11). **0/5 both arms.** But the investigation (every planner handoff
and the django edit read by hand) found the failures are **harness
weaknesses masking model capability**, not the astropy hallucination:

Recorded vs actual planner localization:

| instance | recorded | actual | cause |
|---|---|---|---|
| django | hit 1/3 | 1/3 | correct (partial) |
| sklearn | hit 1/2 | 1/2 | correct (partial) |
| xarray | **0/2** | **2/2** | **parser bug** — planner named both gold files + the right fix (dim→coord) on one markdown line; the parser swallowed `symbols:`/`tests:` into `files` |
| sympy | **0/1** | symbol ✓ | **parser bug** — planner named `polylog` (in the gold file) in prose; parser extracted nothing → lexical-fallback |
| sphinx | 0/2 | 0/2 | genuine model miss (named 9 unrelated `domains/*`) |

So corrected localization is ~4/5, not the recorded 2/5.

The one grounded-but-broken edit (django harness, `filters.py`) was a
**harness bug too**: the 7B repeated a byte-identical `edit_file` four
times (its test kept failing); `edit_file` re-includes its anchor so
each repeat stacks a duplicate, and the loop refuses repeated reads and
execs but not repeated edits — four stacked dead-code blocks.

**Reading:** the astropy hallucination did NOT generalize — of 10 arm
runs only one pure-arm run hallucinated a new file (sphinx `autodoc.py`).
The dominant failures here are two harness defects (handoff parsing,
repeated-edit stacking) that discard or corrupt correct model output.
Per the standing rule (resolve harness contribution before judging the
model): both are fixed before the next re-run, then the model rung is
re-read on clean localization. Instance concurrency (ADR-065) worked —
five instances overlapped; sphinx showed the first real unit overlap
(implement wall 1188 s < units_sum 1288 s).

### 2026-08-22 — the 5-fresh re-run on the ADR-066 harness (both arms), `five-fresh-7b-clean`

Same five instances, same flags, harness at `a2a5504`+. **0/5 both arms**
(harness: 2 unresolved, 3 empty-patch; pure: 3 unresolved, 1 empty,
1 loop-error). **n=5, not an H1–H3 result** (P11). Planner hit 3/5
recorded — and this time the record is right: the ADR-066 parser split
xarray's one-line handoff into both gold files (2/2), django 1/3,
sklearn 1/2; sympy and sphinx are misses of different kinds (below).
Instances overlapped (ADR-065); implement walls 90 s – 1,479 s.

**The window, read properly (Max's question — the Modal 400s).** The
envelopes on disk explain what Modal shows: the two earlier big runs
today paid **~390 context-length 400s** (`five-fresh-7b`: 14 fitted +
184 elided + 2 fatal; `probe-full-7b`: 55 + 131 + 4); this run paid
~10. The drop is **not** a roomier window — mean harness input is still
13.7k tokens/turn — it is that sessions now end earlier on the 6-turn
no-progress exit. Where the window goes: an implementer brief is
33.8k chars mean / 59.8k max (the C-45 limit; sympy U2's tokenized to
**16,750 tokens of 32,768**), and **82 % of it is outside the unit** —
Neighborhood 11.1k + Guarding tests 10.2k + Contracts 6.4k chars mean —
while the unit's own Interior averages 171 chars. With `max_tokens`
1536 and 12k-char read clips, a unit gets three or four `read_file`s
before the first overflow, and C-46's fit then elides **the model's own
reads first** (the brief is protected): sympy U2 read the file it was
about to edit, had the read elided, guessed the anchor, and spun. That
is a constraint the harness imposes, and it is registered as such
(C-46 amended).

**Per instance, classified** (gold files → arm touches → planner → unit
transcript):

| instance | planner | harness units | pure | class |
|---|---|---|---|---|
| django | 1/3 (`filters.py`) | U4 edited `filters.py` **without reading it**: one guessed anchor missed, one hit; the hit edit applied 3× with slightly different `new_text` each time (the ADR-066 byte-identity refusal correctly did not fire) — stacked; unresolved | edited `filters.py`; unresolved | implementer-execution (no read; anchor stacking) |
| sympy | **0** — named `sympy/polys/modules/zeta.py`, a path that does not exist, in prose → lexical fallback | U2's reads elided (fit 2 / elided 3); guessed anchor ×6 | touched 4 files incl. gold; unresolved | planner-localisation (model) + window (harness) |
| xarray | **2/2** | U1 wrote its edits as a ```` ```python ```` fence (unparsed, invalid JSON); U2 `edit_file` on `def integrate(self, dim=None, **kwargs):` — a signature that does not exist — **9 identical pairs, never a read** | loop-error (no-progress) | implementer-execution (no read) |
| sklearn | 1/2 (`base.py`) | U1 prose only across 3 nudges; U2 ran the guarding tests, then *reported* edits it never made | empty | implementer-execution (no edit) |
| sphinx | **0** — the planner wrote `reflect` as a ```` ```json ```` fence that **`--max-tokens 1536` cut mid-list**, three times; the loop does not record `finish_reason`, so a truncated tool call is treated as prose and nudged → lexical fallback | U1/U7 edited `domains/cpp.py`, `util/inspect.py`; unresolved | hallucinated new file `sphinx/ext/autodoc.py`; unresolved | harness (truncation) + planner-localisation |

**Reading.** The two ADR-066 fixes did what they were built for (xarray
2/2; no byte-identical stack). What dominates now is one model
behaviour and three harness gaps around it. The behaviour: **the 7B
implementer edits from memory** — in 30 unit sessions the first turn is
a prose "Changes made" and the edits that follow carry guessed anchors;
`read_file` is rarely called before `edit_file`. The gaps: (1) a
completion cut at `max_tokens` is not detected — the sphinx planner's
correct-shaped handoff was lost three times; (2) the fenced-call parser
accepts only ```` ```json ```` / bare fences with strict JSON; (3)
`edit_file` has no read-before-edit rule (ADR-064 gave `write_file`
one), so a guessed anchor costs the model nothing but a turn; and the
anchor-stacking variant ADR-066 does not cover (same anchor, reworded
text). Behind all of it sits the window: **82 % of the brief is
context the unit cannot change**, and forcing reads will make that the
binding constraint — the brief's shape is a design decision (Max's),
not a parser fix. Per the standing rule, the four gaps are harness and
are fixed before the model is re-read; the brief question is put to
Max with the numbers above.

**Addendum, the same night — the window per call, validated.** Max read
the Modal vLLM log and saw calls saturating far more often than the
envelope counts said. Reconstructed every harness call of the re-run
(221 calls: each assistant turn's message prefix tokenized on the
endpoint) and checked it against vLLM's own `prompt_tokens` sums in the
envelopes: the difference is a constant **1,546 tokens/call** on every
implementer and 1,361 on read-only roles — the tool schema — so the
reconstruction is exact. **In this run (02:38–03:10 EDT) the harness
was not saturated:** median prompt 14k, mean 14k, 41 % of calls ≥ 16k,
19 % ≥ 20k, **8 calls ≥ 24k, 2 ≥ 28k** (sympy U2's last two — the only
session that fit or elided), 1 call with less than the 1,536-token cap
of room. The pure arm has no transcript (fixed, ADR-068); from its
envelopes the largest estimated last call is ~27k (sympy, 20 turns).
What *was* saturated is the two earlier runs (`five-fresh-7b`, ended
01:16 EDT, and `probe-full-7b`, 21:59 the day before): 198 and 190
overflow events, average prompts 16–19k, sessions sitting at the
window for consecutive turns — each turn a 400 absorbed into a 200.
That is what a Modal log spanning the day shows, and it is the
honest description of those runs: most of their implement wall was
spent at the limit. The instrument that makes this a read instead of
a reconstruction is ADR-068's `calls.jsonl` + `calls_saturated`.

### 2026-08-22 — the cheap 7B run on ADR-067/068/069, `five-fresh-7b-adr069`

Same five, both arms, brief **sized to the window** (37,847 chars = 35 %
of 32,768 tokens, read from the endpoint — ADR-069), read-before-edit +
anchor-stack refusal + cut retry (ADR-067), every call logged (ADR-068).
**0/5 both arms** (harness 3 unresolved / 2 empty; pure 2 / 3 loop-error).
**n=5, not an H1–H3 result.** Planner: django 1/3, sklearn 1/2, xarray
2/2, sympy 0 (prose again), sphinx 0 (cut again). Implement walls rose
(xarray 1,186 s, sympy 1,490 s, sphinx 1,922 s): the forced reads cost
turns and tokens.

**What the per-call log shows (the first run that has one):**

- **The window bound where reads were forced**: xarray U2/U7 and sympy
  U1/U4 reached 31–32k-token prompts with 1–3 saturated calls each; most
  sessions stayed at 12–22k. The smaller brief made room; the reads
  filled it.
- **Read-before-edit worked and was not enough.** The refusal fired
  (`has not read`: 1–4 per session), the model read — and the reads
  were **clipped**: 161 `read_file` calls, **40 clipped at 12k chars,
  1 with a line range**. xarray U2 read `dataarray.py`,
  `test_dataarray.py`, `test_dataset.py` whole, saw only their imports,
  and re-sent `def integrate(self, dim=None, **kwargs):` (a signature
  that does not exist; the real one is at line 5,966 of a 260,900-char
  file) six more times. 15 of the 18 sessions with an anchor miss had a
  clipped read. The loop had no search; the pure arm had `bash` and
  never grepped. → **ADR-070: `search_file`**, and the clip notice says
  "this is NOT the whole file".
- **The cut retry fired and was not enough for the sphinx planner**:
  cut at 1,536 and at 3,072 — a 9,895-char enumeration of
  `sphinx/domains/*`. → ADR-070 bounds the handoff in the brief (≤5
  files, <15 lines).
- The pure arm's three loop-errors are all the same exit: repeated
  refused edits (xarray: 24 anchor misses after one clipped read).
- sympy pure touched the gold file (`zeta_functions.py`, the
  `exp_polar` line) — unresolved, but the first pure-arm edit on the
  right line in this set.

**Reading.** The failures are now one layer deeper than last time and
still not cleanly the model's: the model's habit (edit from memory)
meets a tool set in which a large file is unreadable. With ADR-070 the
search exists and every refusal points at it; if the next run shows
`search_file` unused and anchors still guessed, that is the 7B, cleanly.
Planner localization is unchanged (3/5 hit; sympy prose, sphinx
verbose) — the 27B question.

### 2026-08-22 — the ADR-070 verification run, `five-fresh-7b-adr070`

Same five, both arms, ADR-067–070. **0/5 both arms** (harness 2
unresolved / 3 empty; pure 5 loop-errors). **n=5, not an H1–H3 result.**
Max's ask: verify honestly whether the failures are now the 7B's.

**Planner:** all five handoffs **parsed** (no lexical fallback — the
bound worked). Hits: django 1/3, sklearn 1/2, xarray 2/2 (recorded 1/2:
`dataset.py.` with a sentence dot — fixed), sympy **1/1** (first time),
sphinx 0/2 (named `domains/python|cpp|javascript`, wrong — a clean
localisation miss).

**The chain, verified per session** (`search_file` / reads / clipped /
ranged / unread refusals / anchor misses):

| session | what happened | whose |
|---|---|---|
| sklearn U2 | refusal → `search_file` → `read_file` 10–150 → `edit_file` with the anchor copied → **edited** (merged; wrong fix, unresolved) — then its `pytest` was refused as a repeat | model did the chain; **harness** refused the test (exec name, ADR-071) |
| xarray U2 | 6 searches, **0 reads**, 6 unread refusals | model |
| sphinx U1 | 7 searches, 0 reads, 7 unread refusals | model |
| django U4 (harness) | 1 search, 0 reads, prose, no edit | model |
| sympy (harness) | planner hit → owner unit **human-first, parked**; six others unnamed → **zero units ran** | design (C-53) |
| django pure | search found both classes (`:162`, `:419`); read a **range**; `old_text` = invented code not in the file | model |
| sympy pure | `search_file("def polylog")` ×3 → no match (it is a `class`); anchor `if n == 1:` vs real `if z == 1:` | model |
| sklearn pure | searched `sklearn/utils/_output.py` (hallucinated; real `_set_output.py`) → "(no matches)" → kept editing it | **harness** (missing path ≠ empty result) + model |
| sphinx pure | same: `sphinx/ext/autodoc.py` (a package) → "(no matches)" ×2 | harness + model |
| xarray pure | searched a call shape, not the def; guessed anchors again | model |

**Two harness findings, both fixed (ADR-071):** the loop's shell check
only matched `…__exec`, and the proxy's tool is `exec` — so in **every
harness run since ADR-058** a test re-run after an edit was refused as
a read-only repeat, which is the "refused repeated calls" exit most
harness sessions end on; and `search_file` answered a missing path as
"(no matches)". One design finding: the better planner produced the
emptier run — sympy's gold owner is human-first in this partition and
was parked, as it had been in both earlier partitions; a benchmark has
no human to park on (C-53, `--human-first spawn`, Max's call).

**Also observed:** the pure arm at temperature 0 is **not
reproducible** across runs (django: patch, patch, loop-error; sympy hit
the gold line in one run of three) — vLLM batching makes decode
order-dependent, so n=1 per instance is noisier than the temperature
suggests.

**Reading.** Seven of ten arms now fail in the model cleanly: it uses
the search, receives ground truth, and writes from memory anyway; or it
searches and never reads though the refusal tells it to. That is the
7B's shape, stated for the first time without a harness excuse beside
it — except the exec defect, which ended sessions early and whose size
on this set is unknown until a run without it. So: one more 7B run on
ADR-071 (with `--human-first spawn`) is the honest minimum before the
27B; it is cheap, and it is the first run whose harness we have no
known reason to doubt.

**Addendum — the planner never had the context (ADR-072).** Max asked
whether sphinx's planner was given `sphinx/ext/autodoc` and named
`domains/*` anyway. It was not given it: the planner's map was the
first 60 modules alphabetically, and across the five briefs of this run
the gold module was present for **1 of 5** instances. Every planner's
single tool call was its `reflect`. **Every planner hit recorded on
2026-08-22 measured the 7B's prior knowledge of these repositories
(C-39), not Hobbes.** The map is now ranked by the proposal (path and
symbol tokens, rarity-weighted) with the whole package tree; on the
five real graphs the gold files rank django 1/38/44, xarray 7/5,
sklearn 71/44, sphinx 2/9, sympy 40 — all within the 80 listed. The
next run is the first in which the planner hit rate can say anything
about derived context.

### 2026-08-22 — the ADR-071/072 run, `five-fresh-7b-adr072` (`--human-first spawn`)

Same five, both arms; shell recognised (ADR-071), planner map ranked by
the proposal (ADR-072), human-first units spawned (C-53). **0/5 both
arms** (harness 1 unresolved / 4 empty; pure 3 unresolved / 2 empty).
**n=5, not an H1–H3 result.**

**The planner changed shape — the first Hobbes-derived localisation.**
Before ADR-072 no planner called a tool. Now: sympy `search_file
("polylog")` → `read_file(zeta_functions.py)` → `who_calls` →
`tests_guarding` → a correct handoff naming the gold file **and** the
gold test — grounded in derived context, not memory. sklearn's planner
searched twice and called `graph_neighborhood` three times (by path —
refused, ADR-073). sphinx's planner searched three times for a guessed
string, found nothing, and handed off the failure message (lexical
fallback). Hits: django 1/3, sympy 1/1, xarray 2/2, sklearn 0/2
(before: 1/2 by memory — now it named `_set_output.py`, the module the
gold patch *calls*), sphinx 0/2. Gold rank in the map: django 1,
xarray 5/7, sklearn 71/44, sphinx 2/9, sympy 40.

**Implementers, per session:** ranged reads are now common (5–7 per
session where the search was used); the exec fix shows as `exec ok`
followed by the *correct* "nothing edited since" refusal; sympy's
human-first owner ran (U9): searched, found `polylog` at line 63, then
tried to `write_file` the whole module from memory (refused, ADR-064)
and never read it. Anchor misses carry no line-number prefixes — the
model invents names (`def get_attribute` for `id_attributes`) and once
a literal `<path_to_found_file>`. Nothing in this run's harness arm is
left that a known harness defect explains.

**Reading.** Four runs, 0/5 each, and the failure has walked all the
way down to the model: it now gets the place from Hobbes (sympy), the
file's real text from the search, and still writes from memory. The
7B rung is read: **it cannot execute on derived context**, cleanly.
Planner localisation from derived context works in the one case the
model bothered to look (sympy); where it guessed (sphinx) it failed.
The 27B is the question now — with the harness record behind it, not
ahead of it. Pure arm: still not reproducible at temperature 0.

### 2026-08-22 — preregistered before the ADR-075/076 27B re-run (scoped)

Stated before the run, per P11. The `five-fresh-27b` run was void (the
proxy strangled the harness arm, C-54); ADR-075 lets it execute and
ADR-076 gives a thinking model room to investigate. The re-run is
**scoped to the four harness failures** — django, sympy, sklearn, sphinx
— **plus xarray as the control** (verify the harness solve holds). Same
sampling as the first run (thinking on, effort medium, temp 1.0 / top-p
0.95), `--stall-after` and `--timeout` raised for the thinking rung.

**Expectation (Max):** with the harness able to run its tests and commit,
**the harness arm should now beat the pure arm on this set**, even though
it is mostly failures. The basis is this run's own findings, not
optimism: the harness losses were the proxy (104/253 exec calls
expire-denied), not the model; the planner already localises 80% (4/5)
from derived context; and two of the three shared losses were harness
(sklearn localisation, sphinx exec-starvation) while both pure losses
were a timeout and a premature stall. **Falsifier:** if the harness arm
does not beat pure once it can execute — in particular if it still loses
on instances whose planner localised (sphinx, django) — the derived-
context thesis (H1) is weaker than the localisation numbers suggest, and
the wall is per-unit execution, not the proxy. sympy is expected to stay
hard for both (a genuine model under-implementation); a harness-only
solve there would be the strongest single signal.

### 2026-08-22 — the ADR-075/076 re-run, `five-fresh-27b-adr075` (the first CLEAN 27B comparison)

Scoped to the four harness failures + xarray control, thinking sampling,
`--stall-after 12 --nudge-after 6 --timeout 5400`. The harness confounds
are gone: **both arms produced patches on every instance they attempted**
(no exec-starvation, no premature stall). So this is the first comparison
where harness quality is not the story. It is also the **falsifier firing**:

**pure 4/5 · harness 1/5.** (Pure: django, xarray, sklearn, sphinx solved;
sympy empty — a turn-1 endpoint error, a free failure, not an attempt.
Harness: sklearn only.) n=5, one model, one-solution proxy (C-49) — a
strong signal, not a statistic. ADR-076 unleashed the **pure** arm most
(40%→80%: sphinx and sklearn, previously a stall and a timeout, now solve).

**Why the harness lost — read per instance, and it is the multi-unit
decomposition, not the proxy and not localisation:**
- **sklearn (harness solved)** — edited `_set_output.py`, **not** the gold
  `base.py`/`_base.py`; the planner scored 0/2 on the gold metric yet the
  fix is valid and passes F2P. C-49 made real: the gold-file planner metric
  *undercounts*. A point for derived context, not against.
- **django (lost)** — planner named **1 of 3** gold files; C-52 then does
  not spawn the units owning the other two, so only `filters.py` was
  edited → **4 of 6 F2P pass, 2 fail**. Pure, seeing the whole repo, edited
  all three and solved. A **multi-file completeness** gap: the planner finds
  the *primary* file, not the full co-changing set.
- **xarray (lost)** — same shape: planner 1/2, edited `dataarray.py` not
  `dataset.py` → 0/2 F2P. Pure edited both.
- **sphinx (lost)** — planner **2/2**, both gold files edited, **F2P
  passes** — but a **P2P regression** (`test_instance_variable` broke while
  `test_inherited_instance_variable` was fixed). A cross-unit **over-edit**.
  Pure fixed it cleanly.
- **sympy (both lost)** — harness under-implemented (only `polylog(2,1/2)`,
  not the full table — the genuine model wall from the last run); pure
  errored at turn 1. Not a harness-vs-pure signal.

**Reading.** With the proxy fixed, the remaining harness disadvantage is
the **multi-unit staged decomposition itself**: it fragments multi-file
fixes (the planner localises the primary file but not the whole
co-changing set, and C-52 leaves the rest unspawned — django, xarray) and
risks cross-unit regressions (sphinx). A single agent over the whole repo
(the pure arm) makes coherent multi-file edits by default. **The bottleneck
moved from the proxy to the partition/integration model.** This is the
preregistered falsifier: once the harness can execute, it does *not* beat
pure — so the wall is per-unit execution/decomposition, not the proxy, and
the derived-context thesis has to be tested on a harness that does not
fragment the change. That is exactly the mini-swe-agent single-agent +
injected-context path (`docs/harness-mini-swe-integration.md`). Two open
questions this hands forward: (1) should the partition keep the full
co-changing set of a fix in one unit (D1's co-change coupling did not, on
django/xarray)? (2) is per-unit write-scope worth its fragmentation cost at
all, vs one agent given the derived context? The small-model diversified
set and the mini-swe baseline are how we find out.


**CONTAMINATION CAVEAT (added 2026-08-22, C-39 amended) — this comparison
is confounded in Hobbes's disfavor.** Inspecting the pure solves: the 27B
pure arm reproduced the gold patches **verbatim, including author-specific
strings it cannot derive from the repo** — xarray's `" `dim` will be
removed in version 0.19.0."`, and 100% of the gold *added* lines on
xarray (29/29), sklearn (19/19), sphinx (23/23). The 7B produced empty
patches on xarray. This is **memorization, size-dependent**, and
**asymmetric**: regurgitating a whole memorized patch needs the whole
task, which the pure arm has and the partitioned harness is denied by
construction. So "pure 4/5 vs harness 1/5" and the falsifier reading above
are **partly "the partition blocks recall," not "the partition hurts
reasoning."** django (43% reproduction, real exploration) is the only
pure solve that looks reasoned rather than recalled. **No H1 claim may
rest on this run.** The finding stands that the *aided* mode (ADR-077)
removes the fragmentation; but whether derived context aids **capability**
must be tested where recall is impossible — a post-cutoff set, or a model
that provably did not memorize the instance (the 7B, which here could
not reproduce xarray, is the cleaner subject for the aided observation
run).
### 2026-08-22 — the first 27B run, `five-fresh-27b` (both arms; VOID as a model verdict)

The thinking rung (ADR-074): Qwen3.8-27B, thinking on, `reasoning_effort
medium`, temperature 1.0 / top-p 0.95, 8192 max_tokens, the same five
instances, `--human-first spawn`, brief auto-sized to the 131,072
window. Evaluated locally. **pure 40 % (2/5) — django, xarray; harness
20 % (1/5) — xarray; delta −20 pts.** The harness arm lost to pure on
the same model — and the cause is a harness defect, so **this run says
nothing about the 27B** (the resolve-harness-first rule).

**The defect (C-54 / ADR-075).** The policy engine matched a whole
command string against anchored globs, so a capable model's compound
commands never matched the box policy's allow rules: `cd /work &&
python -m pytest …`, `git -C /work status && git -C /work branch`,
`PYTHONDONTWRITEBYTECODE=1 python …` all fell to `default: escalate` →
5 s expire-deny, no approver. **104 of 253 exec calls escalated.** The
harness arm was starved exactly where it needed to act: implementers
could not run their own tests to self-check, **all three unresolved
verifiers reported "nothing could be executed"** (so a correct patch
could still read as fail), and some units could not commit. The pure
arm runs `bash` directly with no proxy, so its compound commands just
ran — the −20 pts is the proxy gap, not a model gap. The 27B, being
more capable than the 7B, writes `cd /work &&` and chains commands far
more, so the better model was penalised harder. Fixed per-segment
(ADR-075); not re-run (Max's go).

**What is real from this run, defect notwithstanding:**
- **The planner localises from derived context, at 27B.** Planner hit
  **80 % (4/5)** — django 1/3, sympy 1/1, xarray 1/2, sphinx 1/2,
  sklearn 0/2 — every planner using search + read + `who_calls` /
  `tests_guarding` / `graph_neighborhood`, grounded, not from memory
  (ADR-072/073 held). sklearn's miss named `_set_output.py`, the module
  the gold patch *calls*, not the two it edits — a real
  partition/localisation edge, not a hallucination.
- **xarray solved on the harness arm** (2 F2P pass, 2398 P2P green): the
  one instance whose implementers happened to write commit-friendly,
  cd-less commands. Proof the staged path can carry a solve end to end
  at this rung.
- **Both pure failures were harness too, not the model.** sphinx pure
  stalled at 6 dry turns *mid-investigation* (search + ranged reads
  toward the fix) — the stall rule (`--stall-after`, tuned against the
  7B's 55-identical-call loop) stops a model that investigates before
  editing. sklearn pure hit the 3600 s wall at turn 40 doing real work
  (prompt grown to 78k). Neither is a model verdict.

**Also observed:** the endpoint held five concurrent sessions at ~75
tok/s aggregate, KV at 16 %; `reasoning_content` rode the transcript as
designed, but vLLM 0.27 reports no `completion_tokens_details`, so
`reasoning_tokens` logged 0 (the reasoning is counted inside
`completion_tokens`, unsplit — ADR-074). Sampling at temperature 1.0
makes both arms non-reproducible by design.

**Next.** Re-run the five on the ADR-075 harness (Max's go): the first
27B run whose harness arm can execute. Before drawing H1, the stall/
timeout knobs a thinking model needs (expose `--stall-after` /
`--nudge-after` on `bench run`; the pure timeout) should be settled too
— a thinking model investigates longer per turn than the 7B the current
defaults were cut for.

### 2026-08-22 — the aided 7B run, `five-fresh-7b-aided-fix` (ADR-077; trace, not score)

The aided mode's first correct run (the first launch silently ran unit
mode — a dropped flag, fixed). Harness 0/5 (2 patches, 3 empty), planner
hit 75% / gold recall 58%. The value is the **trace**: what the 7B did
with proper context (localized, free, neighborhood shown).

- **sympy** — the aid worked: 2 turns, read the gold file → edited it
  (dropped `exp_polar(-I*pi)`) → ran the test. Clean and targeted, but a
  partial fix (no closed-form table). Where the model engaged the aid, it
  went straight to the right file.
- **django** — confabulation: 0 reads, 0 edits, ran pytest *before* any
  change, then declared the change "successfully executed". It believed
  work it never did.
- **sphinx** — right mechanism, wrong path: the aid named
  `sphinx/ext/autodoc/__init__.py`; the 7B edited `sphinx/ext/autodoc.py`
  (a package dir, a phantom) 11 times, all no-ops.
- **sklearn** — blind editing: 6 edits with 0 reads first → anchor
  mismatches → empty. 45 pytest loops.
- **xarray** — never engaged the code: 21 turns, 0 reads, 0 edits, 56
  execs; produced only a stray `pyvenv.cfg`.

**Reading — the 7B rung is exhausted under *both* conditions (fenced and
aided/free).** None of the failures are the fence; the aid was correct.
The wall is the 7B's own execution reliability — it confabulates, ignores
the exact path handed to it, edits without reading, loops on exec. Where
it engaged (sympy) it behaved as designed. **The 7B's only remaining use
is as a diverse, quick *Hobbes checker* — a cheap smoke test that the
harness, the derivation, the briefs, and the flow are wired correctly
before spending a full benchmark run on a capable model — not as a
capability measure.** The capability question needs a model that can
execute reliably *and* cannot recall: the DeepSWE redirect.

### 2026-08-22 — DeepSWE on Pier, `httpx-multipart-response-parsing`, one task per arm (ADR-078/079/080) — **model + prompt, not Hobbes (P12)**

The first runs on the referenced harness (Pier + mini-swe-agent, both
arms; Hobbes = the deterministic ADR-077 aid injected through Pier's
prompt template, C-55). Verifier = DeepSWE's own (122 F2P / 1272 P2P;
reward is binary). **n = 1; this is a wiring read, not a comparison.**

| run | arm | calls | wall | exit | commit | F2P | P2P |
|---|---|---|---|---|---|---|---|
| 7B textbased | baseline | 100 | 11m53 | ContextWindowExceeded (32k) | — | 0/122 | 1272 |
| 7B textbased | hobbes | 17 | 1m42 | ContextWindowExceeded (32k) | — | 0/122 | 1272 |
| 27B native, guard | baseline | 65 | 90m (AgentTimeout) | killed | uncommitted | 0/122 | 1272 |
| 27B native, guard | hobbes | 73 | 88m | ContextWindowExceeded (131k) | uncommitted | 0/122 | 1272 |
| 27B native, guard + commit-on-exit, 2× timeout | baseline | 51 | 82m | ContextWindowExceeded (131k) | COMMITTED | **115/122** | 1272 |
| 27B native, guard + commit-on-exit, 2× timeout | hobbes | 40 | 82m | RepeatedFormatError (at 128k prompt) | COMMITTED | **107/122** | 1272 |

- **7B:** baseline never opened a file (chased a fictitious `origin` for
  100 calls); the Hobbes arm read `httpx/_models.py` on turn 2 — the aid
  localised — then repeated one `cat` twelve times. The 7B's role as a
  checker is confirmed; nothing more.
- **27B, first pair:** both arms produced a complete implementation
  (parser module, `iter_multipart`/`aiter_multipart`, tests, docs) and
  lost it uncommitted — Pier's collect hook is `git diff base..HEAD`.
  ADR-080 (commit-on-exit, both arms) and a 2× agent timeout came from
  this read. The repeat guard (ADR-079) never fired: the 27B does not loop.
- **27B, second pair:** both arms **near-solve**. Baseline's 7 misses are
  two spec items — close the response before raising on a malformed
  closing boundary (5 cases), join header continuations with one space
  (2). Hobbes arm's 15 are the same two plus the streaming chunk-split
  boundary cases it had not reached when its context ran out (it was
  mid-way through fixing its own test file). Its localisation was
  immediate (`_models.py` on its first read); it wrote a separate
  `_multipart_parser.py` like the baseline's `_multipart_response.py`.
- **Both 27B arms are context-bound at 131k**, not model-bound: mini
  keeps every `nl -ba` dump and `git diff` output in the conversation and
  never elides (our C-46 window-fit was ours only). The baseline hit the
  400; the Hobbes arm's output collapsed at a 128k prompt one step
  earlier. A window-fit for the referenced harness — both arms, one
  mechanism — is now the first candidate, and a decision for Max, because
  it changes what the model sees.
- **Contamination check:** DeepSWE tasks are original; neither arm's
  patch resembles a recalled upstream change (httpx has no multipart
  response parser upstream). The two implementations differ from each
  other in module name, structure, and test file — reasoning, not recall.

| 27B native, guard + commit-on-exit + **spans aid, observation-shaped** (ADR-081) | baseline | 76 | 87m | Submitted (125k) | self-committed | **122/122 — reward 1** | 1272 |
| same | hobbes | 68 | 89m | ContextWindowExceeded (130k) | COMMITTED | **120/122** | 1272 |

- **Familiarity probe (27B, httpx, forced):** mean verbatim-line fraction
  0.21, `api.request` 0.43, tests ~0; stdlib calibration `textwrap.dedent`
  0.21 — the model holds httpx's silhouette about as well as the stdlib's.
  Moderate familiarity, no memorization. (The `UNKNOWN`-escape variant is
  invalid: it refused even `textwrap.dedent`.)
- **Obs pair:** the baseline's first full solve (`Submitted` itself, 76
  calls, 125k prompt — finishing room, not a different model). The Hobbes
  arm reached 120/122 (only the header-continuation spacing left), built
  the parser inside `_models.py` rather than a new module, and ran out of
  window at 68 calls; commit-on-exit saved it. Aid shape confirmed
  `observation` in the trajectory (the synthetic `hobbes context` call is
  its turn 1).
- **Read volume, obs pair:** baseline 124k chars read / 69k completion
  tokens; Hobbes 109k read / 80k completion. **The spans did not narrow
  the reads:** the aid's `Response (515-1076)` class span is 560 lines and
  the arm read exactly that range in two slices (515–780, 780–1080) plus
  `Headers (139-380)` and the top of the file — it followed the spans
  literally, at the grain they were given. Method-grain spans were also
  listed; the class-grain ones dominated. A second cost unique to the
  aided arm: 17.6k chars of `git diff` self-review reads. The arm also
  *wrote* 16% more completion tokens. Hypothesis for next time: emit
  method-grain spans only (never a whole class), and say so.
- **Solution shape, four patches:** every pair 0.08–0.18 ratio, ≤0.14
  line overlap — four independent constructions; no convergence on a
  remembered shape (and none on the library parsers).
- **Cost:** ~3 A100-hours per pair; four pairs today. Paused (handoff
  ECONOMICS).

**Not a like-for-like (C-56).** The pure arm mixes repo recall with
reasoning (httpx is in pretraining even if the task is not); the aided
arm's prompt is off-distribution. Read the pair as two different
measurements of the same model, not as Hobbes vs. none.

**What this does and does not say.** The harness pivot works end to end
(build → agent → commit → verifier) and the aid reaches the agent. One
task, one seed each: the 8-test gap between arms is noise-sized and the
Hobbes arm ran out of room earlier. No H1 reading. The next runs need
window-fit (or a larger window) before a set is worth spending.

### Pre-run observations (quota-free; not results)

- **2026-08-21 — seed probe, `psf/requests`, SWE-bench Verified, 8
  instances, lane A only.** 8/8 seeded; seed set touches a gold-patch
  file in 4/8 (1142, 1766, 1921, 2317 hit; 1724, 2931, 5414, 6028
  miss). Raw probe kept with the session's scratch output; the shapes
  of the misses are recorded under C-36.

### 2026-08-24 — the ADR-085 validation pair, `adr085-validate-7b` / `-control` — **STUBBED: needs inspection and revision (Max)**

The one cleared run (two passes, 7B, harness arm only, five Verified
instances, `--coverage strict`; B = `--proposal-in-brief`). Full record
and the eight-defect register: **`docs/adr085-validation-run.md`** —
that file is the entry; nothing here supersedes it. The headline
numbers: the 7B planner wrote `requirements:` 0/5 first-attempt, 3/5
after the one strict re-plan (A), with the lexical fallback bypassing
coverage on the rest (defect D5); sphinx was the first end-to-end
ADR-085 success (re-plan → owned requirements → proposal-free brief);
0/5 solved either pass (not the measure). The removal A/B produced **no
usable signal** — confounded by D5 and by planner-path variance across
identical greedy runs (O4); do not quote A-patches-3 vs B-patches-1 as
a removal result. The run also surfaced the window-fit 400 storm (D1)
and the elision defects (D2/D3/D4), one of which contaminated
sklearn-A's implement stage. Experiments return to **parked**; the
restructure session starts from the defect register.
