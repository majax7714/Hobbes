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
cd bench/atlas0 && uv sync && uv run pytest -q     # 29 tests

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
```
