# ADR-099 — Test-time training on the derived layer: the corpus is a derived artifact; the experiment is preregistered in `olmo3-ttt-validation.md`

**Date:** 2026-09-03 · **Status:** accepted — steps 1–4 of the order of work built and run on the unseen cell (this repo, replicated on fastapi), 2026-09-03; H-TTT-1 not killed, H-TTT-5 killed on NLL and not on navigation, H-TTT-4 unreadable at 7B, H-TTT-2/3 unmeasured (step 5 not cleared) — `benchmark-hypotheses.md` § H-TTT · **Owner:** Max · **Source:** Max, 2026-09-03: "the experiment is listed in olmo3-ttt-validation … it should be fully possible with the keys set"; the design document [`docs/olmo3-ttt-validation.md`](../olmo3-ttt-validation.md) is the body of this decision and is not restated here.

Amends the architecture's **§6.2** (a third instrument beside the
harness and the oracle lane). Registers **C-81–C-84**
(`docs/constraints/verification-benchmark-harness.md`). Adds
**H-TTT-1–5** to `docs/benchmark-hypotheses.md`.

## Context

Hobbes hands a model its derived context in the prompt. The design
document asks whether the same material does more in the model's
**weights** — a few hundred LoRA steps over renderings of
`.hobbes/derived/` at one SHA, regenerable, discarded after — and
preregisters five hypotheses with kill criteria, a factor grid
(model × delivery × repo familiarity), three metrics, a memorisation
gate, and an order of work whose steps 1–4 produce numbers before any
agent runs. Max cleared the experiment on 2026-09-03 with the Modal,
Daytona and Hugging Face keys in `secrets.txt`; the standing policy
(experiments parked) is lifted for this experiment only.

The model is `allenai/Olmo-3-7B-Instruct` (Apache 2.0, ungated, fully
open lineage); vLLM 0.27 lists `Olmo3ForCausalLM` with LoRA support,
so one deployment serves the base and every adapter by name.

## Decision

1. **The corpus is a derived artifact and lives in the pipeline
   (`hobbes.ttt`, `hobbes derive-corpus`).** Three renderings of the
   derived layer at one SHA — symbol cards with every edge's tier
   printed, narrative doc chunks with their pins, and navigation QA in
   six families whose answers are graph queries — chat-formatted,
   canonical JSON, sorted iteration, no model, no randomness beyond a
   seeded hash. Same artifacts in, same bytes out; the manifest carries
   the corpus hash, the SHA, `built_by`, the containment flag and every
   count. This is what lets the adapter be called derived (P1, P5).
2. **Held out by symbol, closed over membership.** A seeded hash of
   the id puts a fraction of the symbols in the evaluation set; a
   held-out class takes its methods. A held-out symbol gets no card and
   no training question, is dropped from other symbols' answer lists
   (counted), and its id, dotted qualname and unique *code-shaped* bare
   name are masked in doc chunks. A plain-word name (`token`) is left
   where a doc uses the word and the mentions are counted rather than
   hidden (C-82). Held-out cards are written apart (`eval-cards.jsonl`)
   for the prompted control.
3. **The absent family is checked mechanically before it is written.**
   A distractor is the first mutation of a real name (case flip, a
   suffix, a sibling token) that names nothing the graph holds — no id,
   name, qualname, module or path; the generator refuses to write one
   that resolves. The false-acceptance rate on distractors is the
   abstention metric.
4. **Gold-diff units come from two sources, reported apart**
   (`hobbes.ttt.units`): DeepSWE tasks (`instruction.md` and the
   withheld `solution.patch`, at `base_commit_hash`) for the memorised
   cell, and **git history** for a repo without a benchmark — every
   commit after a base, split per file, hunks of 3–120 changed lines,
   lock and generated files skipped, commit trailers stripped. The graph
   is ingested at the *base* so a unit's context is what Hobbes could
   see before the change existed (C-84). Arm A1's block is
   `aided_brief`'s "what Hobbes can see / cannot confirm" span derived
   the C-55 way (files → seeds, symbols by name match, one hop, guarding
   tests), never a planner; the NLL prompt is identical across arms but
   for that block, and both prompts ride the units file.
5. **Scoring reads what a reply names, never how it says it**
   (`hobbes.ttt.score`): F1 over the truth ids found against the other
   known ids named; a "none recorded" truth scores 1 when nothing else
   is named; *defines* needs the path; *absent* needs a refusal and no
   invented path. Model-free, like everything else that grades.
6. **Training and serving are one Modal app** (`pipeline/scripts/modal_ttt.py`,
   volume `hobbes-ttt`): `train_adapter` (LoRA r=32 α=64 dropout 0.05
   on attention and MLP projections, 300 steps at batch 16 × 2k, lr
   2e-4 cosine with 30 warmup, bf16, loss on assistant turns only,
   A100-80GB), `score_nll` (mean per-token NLL of the gold diff under
   the bare and the aided prompt, with or without an adapter, no
   sampling), and `serve` (vLLM, base plus adapters by name). The
   adapter is keyed `(model, repo, sha, recipe hash)`, idempotent, and
   its manifest records seed, steps, corpus hash, GPU, versions and the
   loss curve — what a rebuild on other hardware would not reproduce
   (C-81). The chat-template masking refuses when the prompt encoding
   is not a prefix of the full encoding, rather than training on
   questions.
7. **The probe gates first** (`pipeline/scripts/ttt_probe.py`): files
   under a directory, definitions in a file, thirty held-out navigation
   items, unaided at temperature 0; score > 0.5 is memorised, < 0.15
   unseen, between is neither (C-83). The same script scores the full
   held-out set per arm, with `--context card` as the
   reading-comprehension control.
8. **Every arm of this experiment is *model + prompt* under P12.** One
   agent answers a question or writes a diff; nothing decomposes. The
   experiment measures how context is *delivered*, not whether Hobbes
   as a harness solves tasks; solve rate, when the agent runs come, is
   recorded under that label and gates nothing (ADR-082, ADR-086).

## Consequences

- `hobbes derive-corpus` on this repo at HEAD: 17,036 training records
  (3,012 cards, 263 doc chunks, 13,761 QA), 2,610 evaluation records
  over 451 held-out symbols, ~1.8M tokens; at the experiment's base
  (`ebdf7a5`, the public release, ingested contained in a worktree
  with Python at 86% capture): 13,688 records, no doc chunks (C-82),
  ~1.3M tokens, corpus hash `9dfc0270803c44fc`.
- Units for the unseen cell: 147 hunks from the 72 commits after the
  base under `pipeline/src`, `go/`, `web/src`, `scip/`, `tsextract/`,
  `bench/oracle`; 55 name a file the base graph knows, 92 are new files
  whose A1 block says "resolved nothing specific" (C-84) — both
  populations are reported.
- Compute for steps 2–4, stated before spending: one adapter build
  (~0.5 A100-hour), four NLL passes (~0.1 each), a serve on an A10G for
  the probe and the held-out set (~2 hours) — under 4 GPU-hours, well
  inside the design's 25–30 A100-hour envelope for the full grid.
  **Spent, per Modal's meter:** about 3 hours of GPU time, $5.70, for
  everything the session ran — three adapters (true, shuffled control,
  fastapi), ten NLL passes, the probes and six navigation arms.
- Tests: `tests/test_ttt_corpus.py` (19) and `tests/test_ttt_units.py`
  (17) — byte-identical regeneration, the held-out invariant, the
  distractor check, the module projection of the impact family, the
  git and DeepSWE unit builders, the prompt symmetry, the scorer.
- The 2026-08-24 standing policy stands for every other run.

## Amendments (2026-09-03, after Max's review of the first record)

The review set ten follow-ups (`benchmark-hypotheses.md` § Follow-ups,
preregistered before any ran; `olmo3-ttt-results.md` §10; the second
cell record `docs/ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`).
The decisions they added to the eight above:

9. **The NLL prompt's conditioning is a named variable**
   (`hobbes.ttt.units.CONDITIONINGS`: `none` / `subject` / `message` /
   `task`); every units file carries each chat a unit can, the run
   record names what it scored, and the first run's prompt is stated
   verbatim in the second record (C-87). Hand-written task proposals
   live in `bench/ttt/proposals-<repo>-<sha>.jsonl`, one per commit,
   matched to units by commit.
10. **Two controls, named apart.** `shuffled` (the first) deranged card
    bodies whole and kept every true edge under the wrong question;
    `shuffled-all` deranges the edge lines within a module. Each is its
    own recipe hash; the first control's record stands as what it was.
    The true−control margin is a bound on corpus coherence, not the
    graph's worth on a unit (C-86).
11. **Scorer v2** (`hobbes.ttt.score.SCORER_VERSION`): a reply names a
    file when a path-shaped token is a `/`-boundary suffix of exactly
    one known path. Every navigation run is re-scored from its stored
    replies into a new file; the version rides every record; nothing
    is rescored in place.
12. **Paraphrases are a corpus option** (`derive-corpus --paraphrases
    K`, four phrasings per family, variant 0 the original; the eval set
    is always variant 0; K=0 is byte-identical to before).
13. **The primary cell runs one agent per derived unit on the owned
    loop with file tools only** (`loop.py --no-bash`): no exec in any
    arm, so policy is identical across arms and repo code never runs;
    solve is recorded as "a non-empty patch" and the guarding tests are
    not run by anyone in this pass (a defect of the cell record, not a
    finding). HSR resolves code-shaped references against the graph
    (external imports unverifiable; names the agent's own edits define
    excluded); RFE against the unit's interior; `manifest_ignore` is
    the agent-level form of C-88.
14. **Bootstrap intervals on the NLL comparisons are unit-only** until
    a third seed says otherwise: seed 1 moved the true−control margin
    by more than twice its half-width (item 6).

