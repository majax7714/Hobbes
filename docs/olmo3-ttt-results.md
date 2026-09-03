# Test-time training on the derived layer — results, Olmo-3-7B-Instruct (2026-09-03)

**Design:** [`olmo3-ttt-validation.md`](olmo3-ttt-validation.md) · **Decision:** ADR-099 · **Per-cell numbers:** [`ttt-cells/hobbes-olmo3-7b-2026-09-03.md`](ttt-cells/hobbes-olmo3-7b-2026-09-03.md), [`ttt-cells/fastapi-olmo3-7b-2026-09-03.md`](ttt-cells/fastapi-olmo3-7b-2026-09-03.md) · **Standing per hypothesis:** [`benchmark-hypotheses.md` § H-TTT](benchmark-hypotheses.md) · **Constraints:** C-81–C-85

This is the reading document: what was run, what came out, what it
means under the preregistered kill criteria, and what it cannot mean.
Every number here is in a cell record with its bootstrap interval; this
file quotes, it does not recompute. Every arm is *model + prompt* under
P12 — one agent, no decomposition — so nothing here is a Hobbes-harness
result. Compute for the whole run, on Modal's meter: **about 3 GPU-hours,
$5.70**.

---

## 1. The question and the answer in one paragraph

Does the derived layer do more in a model's **weights** than in its
**prompt**? For a 7B model on a repo it has never seen: a few hundred
LoRA steps over renderings of `.hobbes/derived/` make the model expect
the repo — its names, its paths, which file a symbol lives in, which
tests reach a module, and that a name it was not shown is probably not
real — and that lowers the loss on every gold diff and lifts held-out
navigation from nothing to something. But it does **not** put the
graph's edges into the weights: asked who calls a symbol, the adapter
is as blind on symbols it was trained on as on symbols it never saw.
The prompted context block, by contrast, moves loss by nothing and
answers exactly what it lists. So, at 300 steps: **weights hold the
regularities and the abstention habit; relations still have to be live
in attention.** The design's own next step for this outcome is the
step-count ablation (§7), which is running.

---

## 2. What was run

| | |
|---|---|
| model | `allenai/Olmo-3-7B-Instruct` (Apache 2.0, ungated, fully open lineage); served by vLLM 0.27.1 with the adapters registered by name; trained with torch 2.8.0 / transformers 4.57.6 / peft 0.18.1 on an A100-80GB |
| unseen repo | **this repo at `ebdf7a5`** (the 2026-08-24 public release), ingested contained in a worktree: 2,847 symbols, 5,895 call edges, Python 86% / Go 90% / TS 61% capture. Memorisation probe: **0.044** (unseen; the line is 0.15) |
| replication repo | **fastapi at `11614be9`** (a DeepSWE base): 5,262 symbols, Python 69% capture. Probe: **0.129** (unseen) |
| corpus | `hobbes derive-corpus` at the base SHA: symbol cards with every edge's tier, navigation QA in six families (defines / callers / callees / tests / impact / absent), held out by symbol and closed over class membership. This repo: 13,688 training records, 2,270 evaluation records over 393 held-out symbols, hash `9dfc0270803c44fc`. **No doc chunks** — nothing narrated at a base SHA (C-82). fastapi: 27,812 / 3,262 over 566 |
| adapter | LoRA r=32 α=64, attention + MLP projections, **300 steps** × batch 16 × ≤2k tokens, lr 2e-4 cosine, bf16, loss on assistant turns, seed 0 — **0.35 epochs** on this repo, 0.17 on fastapi; 667 s of A100 |
| units (NLL) | git-history hunks after the base, one per commit and file, 3–120 changed lines: **147** here (55 name a file the base graph knows, 92 are new files — C-84), **68** on fastapi (63 known), plus fastapi's two DeepSWE solutions |
| arms | A0 unaided · A1 prompted (the ADR-077 "what Hobbes can see / cannot confirm" block derived the C-55 way: files, symbols by name, one hop, guarding tests — no code) · A2 adapter · A3 adapter + prompt |
| metrics | mean per-token NLL of the gold diff (no sampling); held-out navigation scored by **what a reply names** (F1 over graph ids / the path / a refusal), with "none recorded" items reported apart because naming nothing scores 1 there; paired bootstrap over units or items, 5,000 resamples, seed 0 |
| controls added beyond the grid | a **shuffled-answers adapter** (same corpus, answers permuted within each family — every token the same, every relation wrong); the **held-out symbol's own card in the prompt** (reading comprehension); **600 training questions** (does the adapter hold what it was shown) |

---

## 3. Gold-diff NLL (H-TTT-1)

| arm | this repo, 147 units | fastapi, 68 units |
|---|---|---|
| A0 unaided | 2.394 | 1.820 |
| A1 prompted | 2.396 | 1.821 |
| A2 adapter | **2.098** | **1.597** |
| A3 adapter + prompt | 2.098 | 1.595 |
| control adapter (shuffled answers) | 2.176 | — |

| comparison | this repo | fastapi |
|---|---|---|
| A2 − A0 (the kill criterion) | **−0.296** [−0.315, −0.278], 147/147 lower | **−0.223** [−0.242, −0.204], 68/68 |
| A1 − A0 (prompt alone) | +0.002 (p 0.56); on the 55 context-known units −0.009 (p 0.038); on the 92 new-file units +0.008 (p 0.011) | +0.001 (p 0.81) |
| A3 − A2 (prompt on top of adapter) | +0.001 (p 0.72) | −0.002 (p 0.44) |
| control − A0 | −0.218, 143/147 | — |
| **true adapter − control** | **−0.078** [−0.086, −0.070], 140/147 | — |

**Reading.** H-TTT-1's kill criterion is not met, by a wide margin, on
two repos. But the control says what the margin is made of: an adapter
that learned the repo's vocabulary and nothing true about its graph
reproduces three quarters of the gain. The quarter that remains —
0.08 nats on 140 of 147 units — is what the graph being *right* is
worth to the loss. The prompted block is worth 0.009 where its files
exist and costs 0.008 as boilerplate where they do not.

**H-TTT-5 (combination): killed on this metric.** The combined arm is
not better than the adapter alone on either repo.

**Amended 2026-09-03 (review items 1–3; the numbers in [`ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`](ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md)).**
Three things the review asked change how the table above reads.
*(1) Split by C-84 population,* the true adapter's margin over the
control is larger on the 92 units whose files the base graph never
held (−0.087) than on the 55 it knew (−0.063). Nothing in the graph is
right about a file it does not contain, so "one quarter is the graph"
was too strong: the margin measures what a coherent corpus teaches over
a deranged one, and it bounds the graph's share rather than measuring
it (C-86). *(2) The conditioning was unstated* — the prompt above held
the commit's subject and body and the target path, a *message*
conditioning (C-87). Re-scored under four conditionings, the adapter is
worth −0.244 with the path alone and −0.299 under a hand-written task
statement — nothing shrinks as the task tightens — while the prompted
block is null under three conditionings and real under `task` (−0.008
on 89/147), and adds the same on top of the adapter. The adapter holds
repo language, the task supplies binding, the block adds a little under
a real task; the three are separable. So **H-TTT-5's NLL kill
criterion is met under the commit-message conditioning and not met
under a task statement**, by 0.008 nats — forty times smaller than the
adapter's own effect. *(3) The control's cards kept every true edge*
(bodies permuted whole, under the wrong question). A second control
that deranges the edge lines within each module lands at −0.226
against the base and the true adapter beats it by 0.071 — inside the
first control's interval — so the cards' true edges bought the first
control nothing, and on this metric the card rendering adds nothing
beyond the QA.

---

## 4. Held-out navigation — 2,270 questions about 393 symbols never in a training pair

Scores are F1 over what the reply names. `defines` needs the path;
`absent` needs a refusal with no invented name. Families marked ∅ hold
the items whose true answer is "none recorded"; a reply that names
nothing scores 1 there, so they are shown apart and never averaged in.

| arm | absent FA ↓ | defines | callers | callees | tests | impact | nav (has-truth) |
|---|---|---|---|---|---|---|---|
| A0 base | **0.98** | 0.01 | 0.06 | 0.01 | 0.00 | 0.03 | 0.02 |
| A1 base + the symbol's card | 0.90 | 0.77 | 0.68 | 0.76 | 0.79 | 0.14 | 0.56 |
| A2 adapter | **0.22** | **0.99** | **0.10** | 0.21 | 0.52 | **0.30** | 0.50 |
| A3 adapter + card | 0.22 | 1.00 | 0.79 | 0.81 | 0.37 | 0.10 | 0.61 |

| A2 − A0 | n | Δ | 95% CI | p |
|---|---|---|---|---|
| defines | 393 | +0.97 | [+0.95, +0.99] | <0.0002 |
| absent (refusal) | 393 | +0.76 | [+0.71, +0.80] | <0.0002 |
| tests | 102 | +0.52 | [+0.42, +0.61] | <0.0002 |
| impact | 393 | +0.27 | [+0.25, +0.29] | <0.0002 |
| callees | 256 | +0.20 | [+0.16, +0.24] | <0.0002 |
| **callers** | 112 | **+0.04** | [−0.005, +0.09] | **0.078** |

**Reading.** The base knows nothing about this repo and says so by
inventing: a file for 98% of names that do not exist. The adapter,
asked about symbols whose every training mention was removed, places
them in the right file (a module → path regularity its siblings
taught), refuses most distractors, recovers half their tests (tests
reach modules), a fifth of their callees and a third of their impact
set (both module-shaped, with about two wrong modules per impact
answer) — and **nothing about who calls them**. Callers is the one
relation that belongs to the specific symbol and not to its module.

The card control separates the two deliveries cleanly. The base reads
whatever the card lists (callers 0.68, callees 0.76, tests 0.79) and
nothing it omits (impact 0.14), and the "Hobbes has no card for this"
note does not make it refuse (false acceptance 0.90). The weights beat
the card on the regularities and on abstention; the card beats the
weights on every specific edge. Adapter *plus* card is the best arm
(0.61, p 0.0004 against the card) but not additive: it reads the card's
callers slightly better than the base and its **tests line much worse**
(0.37 vs 0.79 — it answers "none" where the card lists tests; the
adapter's prior overrides the text). So on navigation H-TTT-5 is *not*
killed while on NLL it is; the two metrics disagree and this document
does not average them.

---

**Scorer v2 (review item 7, 2026-09-03).** The tables in this section
are the first record's, scored by v1. An audit of A1's 89 *defines*
failures found 59 that named the right file by basename (`proxy.go` for
`go/internal/proxy/proxy.go`), 25 that named no path, 3 ambiguous, 2
wrong. Scorer v2 accepts a path-shaped token that is a `/`-boundary
suffix of exactly one known path; only *defines* moves: A1 0.77 →
**0.92** (under the preregistered 0.95 line), A0 0.01 → **0.29** (the
base guesses the basename from the id's module segment — a convention,
not knowledge), A2 and A3 unchanged. The adapter's defines gain over
the base is +0.70 under v2, not +0.97. Every navigation run was
re-scored into a new file with the version in it; the v2 tables are in
[`ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`](ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md).

**Abstention is what an instruction buys (review item 4, 2026-09-03).**
With the card plus one sentence — "if the symbol is not listed, say it
is not defined at this SHA; do not guess a file" — the **base** refuses
every distractor (false acceptance 0.90 → **0.00**) and pays 0.06 on
the has-truth families. The adapter's 0.98 → 0.22 is less than that, so
the design's "mid-train for abstention" rationale weakens to "instruct
for abstention". The adapter under the same instruction neither
improves (0.22 either way) nor obeys it correctly: it declares symbols
that *are* on its card undefined (defines 1.00 → 0.33, callers 0.79 →
0.19) — the §4a shape again, triggered by an instruction the base
follows. Numbers in [the review record](ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md).

## 4a. Prior overrides text (review item 8)

With the held-out symbol's own card in the prompt, the adapter (A3)
answers "No test reaches `X` at ebdf7a510eff" — the training template,
verbatim — on **61 of 102** items whose card lists the tests, where the
base reading the same card does so on 8. Joined to the training corpus:
the override follows the *family* more than the module for tests (63%
of every tests answer the adapter saw was "none"; the refusing items'
modules were only mildly more ∅-heavy than the hits', 0.31 vs 0.18),
and follows the *module* for callers and callees (13 of 17 caller
refusals come from modules where at least half the training answers
were "none"; density 0.70 behind refusals, 0.22 behind hits). Impact
fails the other way — the adapter names wrong modules rather than
refusing. A prior manufactured in 300 steps overrides live text; the
mechanism is the corpus rendering absences with the same weight as
presences, and a module-grain regularity is what these weights learn
best (§5). Registered as C-88 with two candidate fixes (down-weight the
∅ answers, or scope them as "none recorded at <sha>"); the agent-level
form, `manifest_ignore`, is measured in the primary cell (§9b).

## 5. The training sample — the number that settles what the weights hold

600 questions drawn from the **training** set, same scorer, no context.
The held-out design removes a symbol's edges from training; only this
can ask whether symbol-grain relations entered the weights at all.

| | callers | callees | tests | defines | absent FA |
|---|---|---|---|---|---|
| held-out symbols (A2) | 0.10 | 0.21 | 0.52 | 0.99 | 0.22 |
| **trained symbols (A2)** | **0.15** | **0.21** | **0.52** | 0.99 | 0.37 |
| trained symbols (A0) | 0.09 | 0.00 | 0.00 | 0.02 | 0.99 |

**The adapter scores on edges it was shown what it scores on edges it
never saw.** At 300 steps (0.35 epochs — each training pair seen at
most once) the weights hold no symbol-grain edge; they hold what a
module imposes on its members, plus an abstention habit. Refusal on
*trained* distractors is lower than on held-out ones (0.63 vs 0.78): a
trained distractor's real sibling has a card the model has seen, and
the name is that much more plausible.

---

## 6. The memorised cell — not reachable at 7B (H-TTT-4)

The gate (§4.4 of the design: files under five directories,
definitions in five files, thirty navigation items, unaided) was run on
four repos and two models.

| repo | Olmo-3-7B | Qwen2.5-Coder-7B |
|---|---|---|
| this repo @ `ebdf7a5` | 0.044 · U | 0.202 · neither |
| httpx @ `b5addb64` | 0.091 · U | 0.203 · neither |
| fastapi @ `11614be9` | 0.129 · U | 0.155 · neither |
| textual @ `0f0849fd` | 0.021 · U | 0.111 · U |

Definition recall is ≤ 0.06 for every model and repo: neither 7B
recalls what a file defines. Two things the replies show that the score
does not (both are C-83's registered failure shapes, now seen): Qwen
names httpx's files as `client.py, config.py, models.py, urls.py` —
the names from **before** httpx's underscore rename — so it holds an
older httpx the probe at a 2025 commit reads as ignorance; and the
files part is inflated by generic names (`README.md`, `LICENSE`,
`__init__.py`), which is all of Qwen's 0.40 files-precision on this
repo. **H-TTT-4 cannot be read at this rung.** It needs a model that
provably recalls a repo (the 27B reproduced xarray's patch verbatim,
C-39 — off the table under the standing policy) or a probe that reads
version shift.

**The probe reads version shift now (review item 10, 2026-09-03).**
The files part re-scored against the union of trees across the repo's
100 newest tags and with generic names dropped: Qwen's httpx rises from
0.20 at the SHA to **0.25 against any release, best at 0.28.1** — the
version its file names belong to — and its 0.20 on this repo falls to
0.14 without `README`/`LICENSE`/`__init__.py`. Nothing crosses 0.5 for
either model on any repo. §6's conclusion stands, and the probe is no
longer blind to the shift that made it wrong about httpx.

---

## 7. Standing of the five hypotheses

| | claim | standing after this run |
|---|---|---|
| H-TTT-1 | derived context lowers gold-diff loss; TTT at least as much as prompting | **not killed** — adapter −0.30 (147/147), −0.22 (68/68); prompting ≈ 0 (−0.008 under a task statement). Caveat, amended by the review: most of the adapter's gain is repo language; the true−control margin (0.07–0.08) bounds the graph's share rather than measuring it (C-86), and the intervals are unit-only (seed variance exceeds them, §9) |
| H-TTT-2 | TTT lowers hallucinated-symbol rate on unseen repos | **killed** (§9b, 2026-09-03): HSR 0.92 under the adapter vs 0.82 under the prompted manifest (+0.11, p 0.18, inside the CI); the adapter invents repo-shaped paths. The navigation proxy (distractor false acceptance 0.98 → 0.22) did not carry to the agent |
| H-TTT-3 | TTT raises right-files-edited | **killed** (§9b): RFE Jaccard 0.01 under the adapter vs 0.41 under the manifest; 0.43 with both |
| H-TTT-4 | lift concentrates on unmemorised repos | **unreadable at 7B** — no memorised cell in the sample, and none appears when the probe is scored against every tagged release (Qwen/httpx 0.25 at best) |
| H-TTT-5 | TTT + prompt beats either alone | **killed on NLL under the commit-message conditioning** (A3 = A2 on both repos); **not killed under a task statement** (A3−A2 −0.008, 99/147 — small, real); **not killed on navigation** (A3 best, 0.61 vs 0.56, non-additive, and with the tests collapse of §4a) |

---

## 8. What this cannot mean, and what was changed on the way

- **Not a Hobbes result.** Every arm is one agent; P12 labels it *model
  + prompt*. Nothing here says anything about decomposition or the
  harness.
- **One 7B, two repos, one recipe.** The corpus had no doc chunks
  (C-82); 92 of 147 units name files the base graph lacked (C-84);
  the adapter is regenerable but not bit-identical across hardware
  (C-81); the probe is a coarse gate (C-83).
- **The control is an addition** beyond the preregistered grid,
  made because a 147/147 that held on new-file units could not be read
  without it. The card control and the training sample are additions
  too; each is named as such in the cell record.
- **Found and registered, not fixed:** a Python repo with no venv loses
  lane B entirely under containment, with a message that blames the
  helper (C-85; httpx, fastapi and textual at 0.0% until given one).
- **Fixed in passing** because they blocked the run: the scorer counted
  a name inside the asked id as an invented one (the first adapter arm
  was set aside and re-run with full replies kept); `expand()` in the
  plan derivation re-sorted its whole frontier per step (a heap now,
  same scores and order on 85 seeds); vLLM's KV budget on the A10G
  (a 16k serve window).

---

## 9. The step-count ablation (100 / 300 / 1,000 / 3,000, and 3,000 with paraphrases) — *running*

The design pre-plans exactly one sweep, because "how many steps to load
a repo" is itself a finding, and the training-sample result (§5) makes
it the decisive one: if callers on *trained* questions rises with
steps, edges enter the weights and the question becomes cost; if it
stays flat while NLL keeps falling, the weights are learning the
vocabulary better and nothing else. Adapters at 100 and 1,000 steps on
the same corpus, seed and recipe; NLL over the 147 units; the held-out
set and the 600-question training sample per adapter.

**Written before the 100 / 1,000 numbers landed (review item 5):** at
≤ 1.2 epochs of single-template exposure, a flat callers-on-trained is
consistent with under-exposure and does not test whether edges can
enter the weights. The sweep therefore runs past one epoch — 3,000
steps (≈ 3.5 epochs) — and adds a 3,000-step point on a corpus where
each fact is rendered through four question and answer phrasings
(`derive-corpus --paraphrases 4`). A 10,000-step point (≈ 12 epochs,
~6 A100-hours alone) is held for Max. The pre-committed readings are in
`benchmark-hypotheses.md` § Follow-ups, item 5.

*(the table — steps × NLL, held-out nav per family, trained nav per
family, absent FA, the paraphrase row marked — appended when it lands)*

---

## 9b. The primary cell — HSR and RFE over 50 derived units (review item 9)

The design's primary metrics, run for the first time: `hobbes plan`
over the 28 hand-written proposals gave 50 derived units (two
proposals refused by the planner); one file-tools-only agent per unit
per arm, no exec anywhere, base and the 300-step adapter on one serve;
every arm *model + prompt* (P12). Numbers and the defect register in
[the review record](ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md).

| arm | HSR | RFE Jaccard | precision | recall | non-empty patch |
|---|---|---|---|---|---|
| A0 base | 1.00 | 0.00 | 0.00 | 0.00 | 0.42 |
| A1 base + manifest | 0.82 | **0.41** | 0.95 | 0.41 | 0.54 |
| A2 adapter | 0.92 | **0.01** | 0.01 | 0.01 | 0.84 |
| A3 adapter + manifest | 0.80 | 0.43 | 0.82 | 0.55 | 0.68 |

The base without a manifest asks for file paths and invents every name
it emits. The manifest is what lets a 7B find the files (Jaccard 0.41,
precision 0.95). The adapter alone finds nothing (0.01) while writing
more than any other arm — into paths that do not exist and read like
this repo's (`pipeline/oracle/agent.py`, `scip-java/src/scip/java.py`);
a third of its sessions were stopped for repeating themselves. That is
§5's finding at the agent grain: repo language in the weights, no repo
structure. Under the manifest the adapter reaches more of the interior
(recall 0.55 vs 0.41, p 0.08) with lower precision (0.82 vs 0.95) and
the same HSR (p 0.37). **H-TTT-2 killed** (HSR(TTT) +0.11 over the
prompted arm, inside its CI); **H-TTT-3 killed** (RFE(TTT) 0.40 below);
H-TTT-5 not survived on either. The design's §8 second row — *structure
must be live in attention* — is the standing conclusion at the agent
grain as well as on navigation. Five harness defects are registered in
the record (no exec and no test run, the tool-call parser, the
reference extractor's first version, the small HSR denominator, the
shared unaided runs); the numbers stand under them.

## 10. Follow-ups from review (2026-09-03)

One line per item, in the review's order (dependency, not priority),
each linking the record that closed it. The readings were preregistered
in `benchmark-hypotheses.md` § Follow-ups before anything ran.

1. A2's NLL gain by C-84 population — **closed**: none of the three preregistered shapes; the true−control margin is larger where the graph holds nothing, so it bounds the graph's share (C-86). §3 amended; [`ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`](ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md).
2. The NLL conditioning stated (C-87) and varied — **closed**: the adapter's gain does not shrink as the task tightens (−0.244 path-only → −0.299 task); the prompted block is real only under a task statement (−0.008) and adds the same on top of the adapter — the separable reading; H-TTT-5 on NLL is killed under `message`, not under `task`. §3 amended; the record.
3. The shuffled control's cards — **closed**: bodies had been permuted whole; a `shuffled-all` control (edge lines deranged within a module) lands at −0.226, the true adapter 0.071 over it — inside the first control's interval, so the card rendering adds nothing beyond the QA on NLL. Its navigation rows: §9.
4. Abstention under instruction — **closed**: the base with the instruction refuses every distractor (FA 0.00, cost 0.06 on has-truth); the adapter's 0.22 does not move under it and its real answers collapse. "Mid-train for abstention" weakens to "instruct for abstention"; design §3.2(c) amended with a dated note. §4 note; the record.
5. Steps past one epoch, with paraphrases (§9) — *open*.
6. A second seed — *open*.
7. The defines scorer — **closed**: 59 of 89 failures were the right file by basename; scorer v2 puts A1 at 0.92 (under the 0.95 line) and lifts the base to 0.29 by convention; every run re-scored into a new file with the version. §4 note; the record.
8. The A3 tests collapse — **closed** as §4a: a family-wide "none" prior for tests, a module-tracking one for callers/callees; C-88 registered with candidate fixes; `manifest_ignore` defined for the cell.
9. The primary cell — **closed** (§9b): 50 derived units, four file-tools-only arms; the manifest finds the files (RFE 0.41), the adapter alone does not (0.01) and confabulates repo-shaped paths; HSR(TTT) not below HSR(prompted). H-TTT-2 and H-TTT-3 killed; five harness defects registered in the record.
10. The version-aware probe — **closed** offline from the stored replies (temperature 0): Qwen/httpx 0.25 against any release, best tag 0.28.1; nothing crosses 0.5; §6 stands. The Olmo rows are re-asked with full replies in the phase-1 serve (their stored heads were cut).
