# Session handoff — the single resume point

**Rewritten 2026-08-25 (oracle lane phases 1 and 2 done + W1 fixes; the
ADR-085 restructure still paused).** The one authoritative resume doc. Read this, then
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

## A SECOND, CLEARED TRACK — the oracle-grading lane (2026-08-25): both phases done

Max cleared ADR-089 with every recommendation (D-O1–D-O6). **Phase 1
(O1–O4) and phase 2 (O6, O7) are built and run, all on 2026-08-25.**
The harness is `bench/oracle/` — one binary (`export | go-rta |
py-trace | rust-mir | grade`), the TS oracle in `ts/`, the Python
tracer in `py/`, the Rust MIR driver in `rust/` (nightly with
`rustc-dev`; `cargo +nightly build --release` once), `run-cell.sh` for
any of the four languages; five fixtures are the self-tests. Records:
`docs/oracle-cells/` (one per cell), `docs/oracle-misses.md` (what
hurts most, by class), `docs/oracle-defects.md` (H-1..H-16 — the
harness's own errors, most of them false verdicts against Hobbes caught
by fixtures or triage), `docs/oracle-preregistration.md` graded in
`extraction-evidence.md`.

**Where the numbers stand.** Every semantic tier graded is 100%: Go
(this repo 1,278; dagger 19 modules 9,851), TS (kbet 630), Rust
(rust_proj 17; dagger `sdk/rust` 3,592 after ADR-090); Python is trace-graded (C-60:
3,291/3,490 confirmed, 0 wrong on the executed semantic slice,
recall-against-executed 86.2% / 96.9% named). The syntactic fallback is
priced everywhere it was reached (C-7): 0/3 Go, 6/6 Python, 12/30 Rust
wrong. The misses are **C-58** on every language — closures,
function values, interface/extension-trait dispatch (70–81% of misses)
— plus Rust's generated-code class (derives, builders, proc-macro
tokens: 46 of dagger's 69).

**Defenses (2026-08-25, Max):** every cell record carries a signed
direction-of-fix line on regrade, and every cell runs the poison check
(`grade --poison`: seeded wrong edges, 0 falsely confirmed on every
stored cell). private-repo-A and qwen-pathology are out of the base.

**Open on the lane, none blocking:** O5 (dagger `sdk/typescript`);
xarray under a trace when a SWE-bench workspace exists again; the dagger
Go root on a ≥32 GB box (H-9; P8/P9); Rupta as a time-boxed reference
lane (C-61 says what it may and may not produce); H-11 cosmetic.
**W1 from the lane — done (ADR-090):** the two syntactic-fallback
name-match shapes are vetoed (a bare name bound in a spanning scope
never resolves to a module-level namesake; a Rust bang binds only to a
macro) and C-58 is surfaced *partial* as the `below-floor` tail class
(`floored` on the coverage row; `list_blind_spots` marks it
not-modelled). O6 regraded: 0 wrong edges on the executed slice, 4
not-exercised suspects. dagger `sdk/rust` regraded after re-ingest: **3,592/3,592, 0
contradictions** — every compiler-graded cell on every language is now
at 100% on every tier it was reached on. dagger's re-ingest sizes
`below-floor` at go 4,114 / ts 247 / python 117 / rust 102. Cell outputs:
`~/.hobbes/bench/oracle/{hobbes-py,rust_proj,dagger-rust,dagger,dagger-before}/`.

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
