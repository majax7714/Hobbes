# bench/atlas0 — Atlas-0, sparse is not absent

The model-free half of the Atlas-0 experiment (design:
[`docs/atlas-0.md`](../../docs/atlas-0.md)) — steps 1 and 2 of its
order of work. Bench tooling, never product: its own uv project, one
dependency (numpy), nothing under `pipeline/` imports it.

Atlas-0 asks whether a small transformer block's **act** separates a
referent it has seen once or twice (*sparse-real*) from one that does
not exist (*absent*), on a synthetic world with the shape of a code
graph, across three blocks (B1 stems, B2 dedicated learned tokens, B3
dedicated frozen vectors) and four ways of showing the block absence
(none / phrase / lived / lived+phrase). Everything here is
deterministic: the world regenerates byte-identically from a seed, and
the checks read the written files rather than the generator's own
bookkeeping.

```sh
cd bench/atlas0 && uv sync && uv run pytest -q     # 84 tests

uv run atlas0 gen --seed 1 --out ~/.hobbes/bench/atlas0/seed1      # ~3 s: world.json, entities.json, corpus/<arm>.txt, eval/*.jsonl, manifest.json
uv run atlas0 check ~/.hobbes/bench/atlas0/seed1                    # step 1's exit criteria; exit 1 on any failure
uv run atlas0 probe-check ~/.hobbes/bench/atlas0/seed1 --block B1 --model atlas-30m   # step 2's exit: chance on a random-init model
uv run atlas0 score ~/.hobbes/bench/atlas0/seed1 --outputs outputs.jsonl [--set primary|secondary|trained]   # the §6.1 matrix
```

## What a world directory holds

| file | what |
|---|---|
| `world.json` | the graph: modules, tests, symbols (class, module, mention target, QA split), absent names (class, exposure, base, nearest dense-real), every fact with its template index — canonical JSON, hashed |
| `entities.json` | every name the tokenizer treats as one entity, by kind (§7's one structural input) |
| `corpus/<arm>.txt` | the training lines of one arm: statements, question/answer pairs for QA-trained symbols, plus the arm's absences (`phrase`: `UNDEFINED`-target queries; `lived`: written absences; both) — shuffled by (seed, arm) |
| `eval/primary.jsonl` | `Where is X defined?` for every QA-held-out real symbol and every absent name — the §6.1 rows; each item carries its gold, the nearest dense-real's answer (`sibling`, the strange tree), the stem distance to it, and its mention count |
| `eval/secondary.jsonl` | the `calls` / `reached_by` queries where the symbol has such facts, and for every absent name |
| `eval/trained.jsonl` | the QA-trained symbols' own queries (the memorisation reference; `gold_trained` names what was in the corpus) |
| `eval/inversion.jsonl` | §6.4: items in three context variants (none / supporting statement / conflicting statement), split `C+S` (the fact is in the corpus) and `C-only` (module-inference symbols, whose fact is only ever in context) |
| `manifest.json` | seed, config, world hash, every corpus hash and line count, class counts, mention ranges |

Outputs for `score` are a jsonl of `{"id": <eval item id>, "output": <the model's completion>}`.

## Readings of the design the generator makes (to confirm on review)

Each is in `atlas0/world.py`'s docstring and is a config field where it
can be:

- **n ≈ 4,000 symbols** is dense (1,200) + sparse (1,200) + a *mid*
  background (1,600, 3–23 mentions), real and unclassed, so that
  density is a continuum whose tails are the two classed rows.
- **Names are 3 or 4 stems.** With 4,000 real names over 300 stems a
  two-stem name has about thirteen real neighbours at stem distance 1,
  so a two-stem absent name can be neither near (no unique base) nor
  far. Length is balanced within every class.
- **absent-near is stem distance exactly 1** from its dense-real base
  (one stem swapped, or one appended to a shorter base), that base the
  only real name within 1; **absent-far is ≥ 2 from every real name.**
  The design's "1–2" cannot separate the two at this vocabulary: a
  random name is within 2 of some real name with probability near one.
- **Sparse-real symbols carry statements and nothing else**: no
  question/answer pair of their own, and no other symbol's training
  answer names them, so their corpus count is exactly their statement
  count in every arm. Dense and mid symbols are half QA-trained, half
  statements-only; the evaluation asks the statements-only half.
- **The primary query is `defined_in` for every class** — the one
  query every real symbol answers uniquely, so the probe cannot read
  the class off the question's shape.
- **Every fact of a dense or mid symbol is rendered through three
  templates** (`renderings`, the design's "across templates"); a fact
  touching a sparse-real symbol is rendered once. Step 3 found the
  reason: with one rendering a B1/none cell memorised its corpus (loss
  0.07) while held-out dense-real accuracy plateaued at 0.31 over 74
  epochs, the knowledge-extraction failure the literature predicts
  without paraphrase; with three it passed 0.76 by 27 epochs. The
  one-rendering world is `Config(renderings=1)` and regenerable.
- **Template hold-out is a *query-phrasing* hold-out** (v1). The
  statements are rendered through five templates the evaluation never
  has to reproduce; what the block meets at evaluation in one fixed
  form is the question, so that is what v1 holds out: three phrasings
  of each query are trained and a fourth is met only at evaluation,
  the first trained one asked beside it as the control
  (`eval/primary_seen.jsonl`). The five statement templates stay, so
  the calibration of step 3 is not disturbed.

## v1 worlds (the step record's items)

Each item is one `Config` field, off by default; a v1 world is the v0
world (same entities, facts, absences, byte-identical hashes for what
the item does not touch) with its own hash. `atlas0 gen --variant`:

| variant | field | what changes | eval |
|---|---|---|---|
| `lived` | `relation_absence` | the **lived arms** carry relation-absence for real dense and mid symbols — two written lines per empty relation (`No test reaches X.` / `X calls nothing.` and their paraphrases) and, for QA-trained symbols, the question of that relation answered `UNDEFINED`. The absence-bearing query v0's lived arm lacked, on a relation of a real symbol; the existence of an absent name stays the phrase arm's target. Sparse-real symbols carry none of it. `none` and `phrase` are v0 byte for byte. | `secondary` also asks every real symbol's empty relations, sparse ones included, gold act `UNDEFINED`; rows `<class>/with` and `<class>/without` |
| `context` | `context_qa_p = 0.5` | half the training QA lines (every arm) are packed with a statement of their own fact, through a seeded template, before the question — a preceding line that bears on a question, so §6.4 has something to learn from | unchanged; the checkpoints' inversion numbers are the curve (`atlas0 report` renders it) |
| `holdout` | `query_holdout` | training QA phrased through three phrasings per kind by seed (`train_phrasings`); every eval prompt uses one the block never read (`held_out_phrasing`, the fifth since 2026-09-06 — the fourth's `live` / `exercises` were words no corpus trains; `--set held_out_phrasing=3` is the world as v1 ran it and fails `check`) | `primary_seen` repeats the primary items in the first trained phrasing |

`atlas0 check` reads each back from the files: a relation-absence line
or an `UNDEFINED` pair about a real symbol only in a lived arm of a
relation-absence world, only for a dense or mid symbol, only where the
facts leave that relation empty; an existence absence never names a
real symbol; a packed line states the fact its question asks, at the
configured share, never before an `UNDEFINED`; the held-out phrasing
nowhere in any corpus and in every eval prompt; **and every word of
every eval prompt in every arm's corpus** (entity names excepted) —
the check the `<nl>` and `live` defects called for. The trainer makes
the same check on token ids against the stream and refuses to read a
cell through an untrained token (`allow_untrained_prompt_tokens` to
override, recorded in the manifest).

`atlas0 gen --set field=value` sets any `Config` field (JSON value;
repeatable): `--set context_qa_p=1.0` is §2's sixth cell's world,
`--set held_out_phrasing=3` the hold-out world as run.

**Defect found on the way (2026-09-05 night):** v0's seed 5 failed
`check` — one sparse-real symbol at six statements, because the filler
re-rendered a dense symbol's call fact whose partner was sparse. The
filler now skips such facts; seeds 1–4 regenerate byte-identically and
seed 5's hash changed (the as-run world is kept beside it as
`seed5-as-run`; its twelve v0 cells stand as run on it, one symbol of
1,200 in the sparse row affected). The record's claim that seeds 1–5
passed was wrong for seed 5 at three renderings.

**A third defect (2026-09-06), under the hold-out world:** the fourth
phrasing's `live` (`defined_in`) and `exercises` (`reached_by`) occur
in no corpus of any arm, so every held-out number on those two kinds
was read through an untrained token — the `calls` phrasing was clean
and its rows stand. Fixed with a fifth phrasing of trained words; the
corpora are byte-identical, so the twenty cells were re-read
(`v1-holdout-fix-reeval`). Found by the prompt-vocabulary check above,
built that morning.

**A second defect (same night), reaching back to v0's §6.4:** the
inversion prompt separated the statement from the question with a
newline, which the tokenizer encoded as `<nl>` — a token no training
stream contains (lines are separated by `<eos>`). Every §6.4 number of
v0 was read through an untrained separator; the "support hurts"
reading was that token. A newline in a prompt is now the stream's
`<eos>` (the previous line), and the context world's prompts pack on
one line as its training QA does. Finished cells are re-read on the
fixed prompts without retraining: `train.reevaluate` (the corpus hash
must match) and `modal_atlas0.py reeval`; `atlas0 evals` rewrites a
world's eval files from its `world.json`.

## v2 — the reading regime (2026-09-06, Max's item 3)

`atlas0 gen --variant v2` (`Config.v2()`): one world, every part of v0/v1
that made memorisation cheap inverted, each a `Config` field off by
default so v0/v1 keep their bytes (`atlas0 check` on `seed{1..5}`
regenerates them byte-identically with the fields present).

| field | v2 | what it does |
|---|---|---|
| `statement_templates`, `renderings` | 8, 8 | a fact is not a single string; templates 5–7 of each relation are v2's (the tokenizer appends their words after every earlier id) |
| `query_holdout`, `train_phrasings`, `held_out_phrasing` | on, 0–6, 7 | seven phrasings trained, the eighth met only at evaluation — every accuracy is on an unseen form of the question; the eighth's words are all trained by the first seven and the templates (the vocabulary check reads it) |
| `context_only_frac` | 0.3 | that share of the QA-trained facts (those with a pair) appear **only in packed lines**: no free statement, the pair written once per rendering, each packed with one rendering (the exposure count is kept) — reading is the only route; the inversion set gains the split `C-only-qa` and the `trained` items carry `context_only` (the report splits `trained_free` / `trained_context_only`) |
| `relation_absence`, `absence_split` | on, on | v1's lived lines and pairs, plus the trained absent names split by seed into a `pair` half (`UNDEFINED` pairs, phrase arms) and a `lines` half (written absences, lived arms) — v1's proposed cleanest cell folded in; primary rows `absent-*/pair`, `/lines`, `/held-out` |
| `filler_partner_budget` | on | the filler never puts a mid partner over its budget (eight renderings pushed one to 26 in the tiny world; v0 seed 1's bytes move if on there) |

Few epochs is T's: `modal_atlas0.py train|grid --epochs E` sets the
steps so the stream is seen `E` times (`TrainConfig.max_epochs`).
Calibration: B1/none, one seed, `--stop-at-target --target-dense 0.8`
on the held-out phrasing; B3's criterion is reading, not memorising —
`--target-measure read_context_only` (C-only-qa/support gold ≥ 0.5).
Arms `none, phrase, lived+phrase`; `--runs 2` for §6.6's union.

```sh
uv run atlas0 gen --seed 1 --variant v2 --out ~/.hobbes/bench/atlas0/v2-seed1 && uv run atlas0 check ~/.hobbes/bench/atlas0/v2-seed1
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py train --world v2-seed1 --block B1 --arm none --seed 1 --steps 100000 --epochs 4 --batch 16 --ckpt-every 50 --stop-at-target --target-dense 0.8 --out v2-cal-b16
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py grid --world 'v2-seed{seed}' --steps 100000 --epochs E --batch B --seeds 1,2,3,4,5 --blocks B1,B2,B3 --arms none,phrase,lived+phrase --runs 2 --out v2-grid
```

## B4 — typed relations (2026-09-07, Max's addendum; `docs/atlas-0.md` § Addendum)

B4 is B1 with typed attention: per layer, `K` relation operators
`R_k = I + A_k B_kᵀ` (rank 16, shared across heads) and a router
`p(i, j)` over pairs (a rank-16 bilinear on the full-width q and k, one
distribution per pair per layer), Gumbel-softmax in training with the
temperature annealed 1.0 → 0.3 over the schedule, argmax at evaluation;
the attention logit is `Σ_k p_k · (q R_k k)`; the penalties (pair entropy
+ usage balance) weigh `types_lambda`. `--block B4 --types-k 8
--types-rank 16 --types-lambda λ`; at `K = 1` there is no inventory and
the cell is B1 to the digit (tested, and run: `runs/v2-b4-k1`).

The trainer also learned three things for the addendum: `--save-weights-every N`
(weights at checkpoints, `ckpt/step-N.pt`), `--stop-at-step S` (the
schedule laid over the full `--epochs`, training stopped at `S`) and
`--full-eval-at 2200,...` (a full read — report, outputs, weights,
`typed.json` — under `step-N/`; `atlas0 report --at 2200` renders every
cell at that step: the addendum's two columns).

```sh
uv run atlas0 mech heads|ffn|all CELL WORLD [--weights ckpt/step-N.pt] [--out F]   # §A.1: reads = heads (rank, ablate, controls), stores = FFN layers
uv run atlas0 mech b2norm RUNS 'WORLD-{seed}' [--out F]                            # §A.1: B2 — ‖row − init‖, its split along the head's push, a row probe
uv run atlas0 typed CELL WORLD [--weights W]                                        # §A.5 re-read: type discovery, sibling pull by type, the absence signal
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py train --world v2-seed1 --block B4 --types-lambda 0.1 --arm none --seed 1 \
    --steps 100000 --epochs 16 --batch 16 --stop-at-step 3100 --ckpt-every 300 --save-weights-every 300 --full-eval-at 2200 --out v2-b4-lam0.1
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py grid --world 'v2-seed{seed}' --blocks B4,B1 --arms none,phrase,lived+phrase --seeds 1,2,3,4,5 --runs 2 \
    --steps 100000 --epochs 16 --batch 16 --stop-at-step 3100 --ckpt-every 300 --full-eval-at 2200 --types-lambda λ --out v2-b4-grid
uv run atlas0 report ~/.hobbes/bench/atlas0/runs/v2-b4-grid [--at 2200] --out ...   # §6.1–6.6 plus the B4 sections and §A.5.5's loss delta
```

Every cell writes `typed.json` / `typed.md` beside its report (B1 cells
carry the untyped halves: the sibling cosine, the absence rows), and the
§A.1 records live under `~/.hobbes/bench/atlas0/mech/`.

## Steps 3–6

`atlas0.train` is the trainer (torch; `uv sync --group train` for the
CPU smoke test) and `scripts/modal_atlas0.py` runs cells on Modal
(volume `hobbes-atlas0`; one L4 cell of 4,000 steps is about nine
minutes and $0.12 at the assumed rate). `probe.py` and `acts.py` read a
trained model's residuals and outputs the same way they read the
random-init one; a run directory holds `manifest.json` (tokens/s,
wall, device, the loss curve, every checkpoint), `report.json` (every
set's matrix, the probe, the authority tables, inversion, sparse by
distance), `outputs/<set>.jsonl`, `residuals.npz` and the weights.

```sh
uv run scripts/modal_atlas0.py put ~/.hobbes/bench/atlas0/seed1 seed1
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py train --world seed1 --block B1 --arm none --seed 1 --steps 4000 --stop-at-target   # step 3
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py grid --world seed1 --steps N --seeds 1 --blocks B1,B3 --arms none,phrase,lived,lived+phrase   # step 4
uv run scripts/modal_atlas0.py get /runs/<dir> ~/.hobbes/bench/atlas0/runs/
# v1: one world per (variant, seed), cells by the world name
uv run atlas0 gen --seed 1 --variant lived --out ~/.hobbes/bench/atlas0/v1-lived-seed1 && uv run atlas0 check ~/.hobbes/bench/atlas0/v1-lived-seed1
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py grid --world 'v1-lived-seed{seed}' --steps 3500 --seeds 1,2,3,4,5 --blocks B1,B2 --out v1-lived
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py reeval --world 'seed{seed}' --runs grid-3500 --out grid-3500-reeval   # re-read finished cells, ~$0.003 each
ATLAS0_GPU=L4 uv run scripts/modal_atlas0.py grid --world 'seed{seed}' --steps 3500 --seeds 1,2,3,4,5 --runs 2 --out <dir>   # §6.6 amended: two runs per seed (-r2 cells), the gate over the union
```

Run directories (`~/.hobbes/bench/atlas0/runs/`, all on the volume):
`grid-3500` (v0, sixty cells as run), `grid-3500-reeval` (the same on
the fixed prompts), `v1-lived` + `v1-lived-reeval`, `v1-context` (read
through `<nl>`, kept) + `v1-context-fixed`, `v1-holdout` +
`v1-holdout-reeval`, `v1-holdout-fix-reeval` (the same cells on the
fifth phrasing), `v2-b3-context` (§2 of 2026-09-06: B3 on the context
world) + `v2-b3-context1` (full packing, seed 1), `v2-cal-b{64,16,8}`,
`v2-cal-r16-e4`, `v2-cal-e8`, `v2-cal-e16` (§3's calibration: B1 at
4 / 8 / 16 epochs, B2 and B3 at 16); `<dir>-report.{md,json}` beside
each.
