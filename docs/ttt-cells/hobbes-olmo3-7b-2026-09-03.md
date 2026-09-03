# TTT cell — Hobbes @ `ebdf7a5` · Olmo-3-7B-Instruct · 2026-09-03

**Experiment:** ADR-099, `docs/olmo3-ttt-validation.md` (steps 1–4 of
the order of work). **Cell:** the unseen-candidate repo (this one, at
its public-release commit) × Olmo 3 7B × four deliveries. **Every arm
is *model + prompt* under P12.** Numbers are recorded; the reading is
in the hypotheses doc.

## Setup

| | |
|---|---|
| repo, SHA | this repo at `ebdf7a510eff` (2026-08-24, the public release), worktree `~/.hobbes/bench/ttt/hobbes-base` |
| ingest | contained (ADR-092), built by `e656b75` from this checkout; Python 86.0% / Go 89.6% / TS 61.4% / Rust 100% capture; 2,847 symbols, 5,895 call edges. First attempt lost Python lane B (no `pipeline/.venv` in the worktree — C-85's shape) |
| corpus | `hobbes derive-corpus`, recipe v1, hash `9dfc0270803c44fc`: 13,688 training records (2,454 cards, 11,234 QA: defines 2,345 / callers 2,000 / callees 2,000 / tests 2,345 / impact 199 / absent 2,345), **0 doc chunks** (nothing narrated at this SHA, C-82), ~1.30M tokens; held out 393 symbols (fraction 0.1, seed 0, closed over membership): 2,270 evaluation records, 393 held-out cards; 836 card and 817 answer mentions dropped |
| adapter | LoRA r=32 α=64 dropout 0.05 on q/k/v/o/gate/up/down, 300 steps × batch 16 (micro 4 × accum 4) × ≤2,048 tokens, lr 2e-4 cosine warmup 30, bf16, loss on assistant turns, seed 0; **0.351 epochs**, 0 truncated; A100-SXM4-80GB, torch 2.8.0 / transformers 4.57.6 / peft 0.18.1; 667 s; key `04195d188e61`, path `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/04195d188e61` on volume `hobbes-ttt` |
| loss curve | step 0: 3.24 · 30: 0.09 · 60: 0.60 · 90: 0.47 · 120: 0.31 · 150: 0.30 · 180: 0.28 · 210: 0.23 · 240: 0.28 · 270: 0.22 · 299: 0.09 (per-16-example batch; templated answers, so it falls fast) |
| units | 147 git-history hunks from the 72 commits after the base (`pipeline/src`, `go/`, `web/src`, `scip/`, `tsextract/`, `bench/oracle`; 3–120 changed lines; lock files skipped, trailers stripped); mean 28 changed lines, 658 target tokens; A1 block mean 775 chars; **55 name a file the base graph knows, 92 do not** (C-84) |
| prompts | system "single-use engineer in hobbes at commit …"; user = task (+ the A1 block) + "write the unified diff"; assistant = gold diff; NLL over the assistant tokens only, batch of one, no sampling, `chat_template` prefix check passed |
| control | a second adapter on `--control shuffled` (answers permuted within family, a derangement; corpus hash `1e9fdf94f9751f27`), same recipe — added beyond the preregistered grid to separate vocabulary from relations |

## Gold-diff NLL (H-TTT-1, §4.3) — mean per-token, paired by unit, seeded bootstrap (5,000)

| arm | adapter | prompt | n | mean NLL |
|---|---|---|---|---|
| A0 | – | bare | 147 | 2.3940 |
| A1 | – | aided | 147 | 2.3956 |
| A2 | hobbes | bare | 147 | 2.0975 |
| A3 | hobbes | aided | 147 | 2.0981 |

| comparison | population | n | Δ(a−b) | 95% CI | p | a<b |
|---|---|---|---|---|---|---|
| **A2−A1** (primary) | all | 147 | **−0.2981** | [−0.3174, −0.2796] | <0.0002 | 147/147 |
| A2−A0 (kill criterion) | all | 147 | −0.2964 | [−0.3153, −0.2782] | <0.0002 | 147/147 |
| A1−A0 | all | 147 | +0.0017 | [−0.0038, +0.0069] | 0.557 | 67/147 |
| A3−A2 | all | 147 | +0.0006 | [−0.0022, +0.0034] | 0.715 | 68/147 |
| A2−A1 | context-known | 55 | −0.3589 | [−0.3855, −0.3330] | <0.0002 | 55/55 |
| A1−A0 | context-known | 55 | −0.0090 | [−0.0175, −0.0007] | 0.038 | 30/55 |
| A3−A2 | context-known | 55 | −0.0027 | [−0.0083, +0.0029] | 0.352 | 28/55 |
| A2−A1 | no-known-file | 92 | −0.2617 | [−0.2855, −0.2391] | <0.0002 | 92/92 |
| A1−A0 | no-known-file | 92 | +0.0080 | [+0.0016, +0.0143] | 0.011 | 37/92 |
| A3−A2 | no-known-file | 92 | +0.0025 | [−0.0006, +0.0057] | 0.108 | 40/92 |

Full table: `~/.hobbes/bench/ttt/runs/report-olmo-hobbes-300.json`
(`scripts/ttt_report.py`); runs `nll-olmo-hobbes-{base,adapter}.json`.
NLL wall: 42 s + 70 s of A100.

## The shuffled-answers control (beyond the preregistered grid)

Same recipe, same seed, same 300 steps on the answer-permuted corpus
(`1e9fdf94f9751f27`; every relation wrong, every token the same);
adapter `adapters/allenai-olmo-3-7b-instruct/hobbes-shuffled/ebdf7a510eff/control`.

| arm | n | mean NLL |
|---|---|---|
| A2 (control adapter, bare) | 147 | 2.1756 |
| A3 (control adapter, aided) | 147 | 2.1756 |

| comparison | population | n | Δ(a−b) | 95% CI | p | a<b |
|---|---|---|---|---|---|---|
| control−A0 | all | 147 | −0.2184 | [−0.2400, −0.1976] | <0.0002 | 143/147 |
| **true adapter − control adapter** (bare) | all | 147 | **−0.0781** | [−0.0863, −0.0702] | <0.0002 | 140/147 |
| true − control (bare) | context-known | 55 | −0.0630 | [−0.0756, −0.0507] | <0.0002 | 50/55 |

Of the true adapter's −0.296 nats against the base, −0.218 (74%) is
reproduced by an adapter that learned the repo's names, paths and
templates and nothing true about its graph; the remaining −0.078 is
what correct relations add, on 140 of 147 units. Runs
`nll-olmo-hobbes-control.json`, `report-olmo-hobbes-control.json`.

## Memorisation probe (§4.4), unaided, temperature 0

| repo | files-P | defs-R | nav | score | cell |
|---|---|---|---|---|---|
| hobbes @ `ebdf7a5` | 0.10 | 0.00 | 0.03 | **0.044** | U |

## Held-out navigation (§4.5) — 2,270 items over 393 symbols never in a training pair

Scores are F1 over what a reply names; a family marked ∅ holds the
items whose truth is "none recorded", where naming nothing scores 1 —
reported apart, never averaged into `nav`. Temperature 0, 512 tokens,
the base model or the adapter by name on one vLLM endpoint.

| arm | absent (refusal) | absent FA | defines | callers | callers∅ | callees | callees∅ | tests | tests∅ | impact | nav (has-truth) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A0 base, no context | 0.020 | **0.980** | 0.013 | 0.062 | 0.772 | 0.005 | 0.946 | 0.000 | 0.821 | 0.033 | 0.021 |
| A2 adapter, no context | 0.776 | **0.224** | 0.985 | 0.103 | 0.954 | 0.206 | 0.645 | 0.521 | 0.921 | 0.301 | 0.496 |

| A2−A0 | n | Δ | 95% CI | p | a>b / a<b |
|---|---|---|---|---|---|
| defines | 393 | +0.972 | [+0.954, +0.987] | <0.0002 | 382 / 0 |
| absent | 393 | +0.756 | [+0.713, +0.796] | <0.0002 | 297 / 0 |
| tests | 102 | +0.521 | [+0.423, +0.614] | <0.0002 | 56 / 0 |
| impact | 393 | +0.269 | [+0.250, +0.287] | <0.0002 | 324 / 12 |
| callees | 256 | +0.201 | [+0.162, +0.242] | <0.0002 | 78 / 0 |
| **callers** | 112 | **+0.040** | [−0.005, +0.085] | **0.078** | 11 / 3 |
| callees∅ | 93 | −0.301 | [−0.409, −0.194] | <0.0002 | 2 / 30 |
| navigation (all has-truth) | 1,256 | +0.475 | [+0.451, +0.498] | <0.0002 | 851 / 15 |

The base names a file for 98% of distractors and knows nothing else
(≤ 0.06 in every has-truth family). The adapter, asked about symbols
whose every training mention was removed: places 98% of them in the
right file (a module→path regularity, learnable from the module's other
members); refuses 78% of distractors; recovers half the tests (tests
reach modules, so a sibling's tests are usually the held-out member's);
a fifth of callees and a third of the impact set (module-grain again,
with ~2 wrong modules named per impact answer); and **no callers** — the
one relation that is a property of the specific symbol, not of its
module, and the one the held-out design removed from training entirely.
callees∅ falls: with an adapter the model names callees whether or not
there are any. Runs `nav-olmo-hobbes-A{0,2}.json`, `navreport-A0-A2.json`.

*(A1/A3 — the held-out card in the prompt —, the training-sample
arms, and the candidate repos' probes are appended below as they land)*
