# Session handoff — the single resume point

**Rewritten 2026-08-24 (the ADR-085 validation pair ran; paused for
restructure).** The one authoritative resume doc. Read this, then
**`docs/adr085-validation-run.md`** (the run's record and its
eight-defect register — the restructure's worklist), then
`docs/benchmark-hypotheses.md` (reading rules + Results) and the recent
`docs/BUILDLOG.md` entries. History lives in the BUILDLOG; this doc is
forward-looking and is rewritten, never appended into a pile.

## STANDING POLICY (Max) — read before doing anything

1. **Experiments are PARKED again (2026-08-24).** The one cleared run
   (the ADR-085 validation pair) has happened. No further run of any
   size without a fresh, explicit go from Max. He returns to
   **restructure** from the defect register, then proceeds.
2. **The 7B is the instrument, by speed not capability.** Validate
   every mapping/architecture change on the 7B or with no model at all
   (replay over stored specs/handoffs) first. The compute-economics
   gate (Max, 2026-08-22; BUILDLOG): ≥15 min of evaluation before any
   run over 30 min; state the GPU-hours first.
3. **P12 (ADR-082): a Hobbes test decomposes, or it is not a Hobbes
   test.** Since ADR-086 the machinery enforces the label: an aided run
   is recorded `arm=model+prompt` on every path.
4. **The 27B is untouched** until the mapping fixes are built and
   validated on the 7B, and only on a decontaminated set.

## WHERE THE PROGRAMME STANDS (2026-08-24)

- **ADR-085 is built and demonstrated once end to end** (sphinx:
  planner re-plan → owned requirements → proposal-free brief →
  coverage held). The E-numbers: 7B planner wrote `requirements:` 0/5
  first-attempt, 3/5 after the one strict re-plan; the lexical
  fallback bypassed coverage on the other 2 (defect D5).
- **The removal A/B produced no usable signal** — confounded by D5 and
  by planner-path variance across identical greedy runs (O4). Re-run
  after the restructure, on the D5 fix, with n big enough to split the
  variance out.
- **0/5 solved, both passes** — recorded, and not the measure; the 7B
  failure mode remains implementer execution (hallucinated anchors,
  requirement-descriptions rendered as code), not refusal.
- **The run was judged on machinery behavior and it mostly held**:
  strict stopped nothing incorrectly, the re-plan recovered every
  usable planner, fast honest failure worked (sphinx implement 37 s).

## THE RESTRUCTURE WORKLIST — `docs/adr085-validation-run.md`

Eight defects, each with observed evidence, proposed change, owner:

- **D1** window-fit 400 storm (vLLM "at least" lower bound → ~75
  400s/elide cycle; 450 on one call) — one fit per elide cycle.
- **D2** elision deletes action memory (89-char failed-edit results
  elided for ~10 tokens) — never elide mutating/short results.
- **D3** read ticket survives elision of the read (P10 shape; a
  28-byte blind overwrite of `_array_api.py` went through) — eliding a
  read invalidates the path's ticket.
- **D4** same-turn read+edit batching defeats ADR-067's spirit
  (hallucinated anchor authored before the read was seen) — refuse
  edit in the first-read turn.
- **D5** lexical fallback bypasses strict coverage — Max's shape call.
- **D6** generic one-word seed (`astype`) overrides the hub exclusion
  → 2,543-guarding-test interior — C-36 seed weighting; Max's call
  with ADR-083 lever 2 (deferred to these records, ADR-086).
- **D7** foreign environment residue (`exercise_01_language_train_model`)
  in `extraction_errors` rides every brief — scope the dup report
  in-repo; per-lane wording.
- **D8** prose reflection is not a handoff — nudge + `handoff: missing`
  on the record.

D1–D4, D8 are mechanical loop/harness fixes; D5–D6 are shape decisions
for Max; D7 is a small extraction surfacing fix. Observations that are
findings, not defects (knowledge tools unused at the 7B rung — derived
context is push-only there; requirement-text rendered as code; O4
planner variance) are in the same file.

## HOW TO INSPECT / MEASURE (no GPU)

- The pair's records: `~/.hobbes/bench/adr085-validate-7b{,-control}/`
  (`records.jsonl`, `detail.coverage`, `detail.stages`); per-unit
  sessions under `~/.hobbes/sessions/<task>-<unit>/` (`brief.md`,
  `transcript.jsonl`, `calls.jsonl` — the D1 grind is visible in
  sklearn-A's u1/u5 rows).
- Coverage replay (no model): `hobbes.run.coverage.imperatives_unmentioned`
  over stored handoffs; `scripts/brief_sizes.py` for rendered-context
  size; re-derive stored specs with `derive_plan(..., lexical=False)`.
- The D1 arithmetic reproduces without GPU: the overflow message's
  input count is `window − max_tokens + 1`; simulate the fit loop.

## IF/WHEN A RUN IS CLEARED AGAIN (reference only — parked)

Same shape as the validation pair: warm the endpoint (short-timeout
`/models` loop; Modal cold start ~10 min), then `hobbes bench run
verified.jsonl --secrets secrets.txt --id <ids> --arm harness --runtime
openai --llm-base-url <7B URL> --model Qwen/Qwen2.5-Coder-7B-Instruct
--session-bin go/bin/hobbes-session --out ~/.hobbes/bench/<name>
--stages plan,implement,verify --coverage strict --max-units 10
--max-turns 40 --max-tokens 1536 --parallel auto --evaluate
--human-first spawn` (+ `--proposal-in-brief` for the control arm
only). Evaluator on the local rootless-podman socket (`systemctl --user
start podman.socket`; never `--eval-modal`, C-50). State GPU-hours
first.

## Housekeeping

- Commit to `main`; never `git push` (Max publishes). One ADR per design
  decision; one BUILDLOG entry per session; every concession a `C-n` in
  the right segment file under `docs/constraints/`. Rewrite this doc; do not append to it.
