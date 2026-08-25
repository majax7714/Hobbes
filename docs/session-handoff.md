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

## A SECOND, CLEARED TRACK — the oracle-grading lane (2026-08-25)

Max cleared ADR-089 with every recommendation (D-O1–D-O6). **O1 and
O2 are done** (2026-08-25): the harness lands on fixture truth; this
repo's Go zone grades 1,278/1,278 semantic edges confirmed, 0/3
syntactic, static recall 100% at 20 roots, and 45 honest misses — all
one class, now **C-58** (interface / function-value / closure calls
draw no edge, and the site still counts as resolved). Pre-registration
graded in the evidence file (P3, P4 missed; the rest met). **O3 is done**
(kbet `betchat/frontend` against the zone's own `tsc`: 630/630
confirmed, recall 633/637 on declared callees; the 119 first-pass
contradictions were the oracle's grain — the binding rule is now
normative in the harness README). Both 20/20 hand-checks retired at
Max's direction. **O4 is done as far as this box allows** (2026-08-25):
19 of dagger's Go modules compiler-graded at 99.6% precision (all 40
contradictions = type conversions drawn as calls, a product defect on
W1's list), 9,854/9,889 static named calls drawn, C-59 (dropped
self-calls) registered; **the root module OOMs as one program (~21–24
GB on this 30 GB box, H-9)**, so P8 and P9 are recorded *not graded*.
Resume with either (a) **W1's fixes** — conversions-as-calls, chain
continuations, LHS calls, method expressions, C-59 — each with a
dagger module cell that reruns in ~3 min (`~/.hobbes/bench/oracle/
run-dagger.sh`), or (b) **phase 2** (O6 Python traces, O7 Rust MIR),
or (c) **the root on a bigger box — flagged (Max, 2026-08-25): needs
~32 GB+ free for the engine's closure; parked until Hobbes gains
compute.** Cell outputs live under
`~/.hobbes/bench/oracle/dagger/`.
O1 was built as follows:: `bench/oracle/` (own Go module; `oracle export | go-rta |
grade`, `run-cell.sh`), fixture truth in its Go tests, `twomod` added
to `pipeline/tests/fixtures/`. Resume at design §10: **the
pre-registration commit** (bands for Go and TS precision, miss
concentration, contradiction tier, the O4 build-tag prediction), then
O2 = `run-cell.sh . go <out>` on this repo, with ADR-037's 20/20 as
the cross-check and the triage protocol's first use. No GPU; each cell
logs its runtime. Phase-by-phase, report between cells.

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
