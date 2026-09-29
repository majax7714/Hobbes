# Mapped agents with derived context

**Thesis** (Max, 2026-09-28): smaller tasks with better context should be easier to complete, which
lets smaller models compete against bigger ones. Hobbes derives the task's units, each unit's context
and its policy from the graph (the planner, `hobbes plan` and `hobbes run`), and gives each unit to a
single-use agent whose window is smaller than the task.

**Status:** parked (the standing policy in [`../../session-handoff.md`](../../session-handoff.md)). No H1
claim has been earned. The next run on Max's word is the removal A/B re-run on the 7B (W3).
Index: [`../README.md`](../README.md).

## What is here

| file | what it is |
|---|---|
| [`benchmark-hypotheses.md`](benchmark-hypotheses.md) | The preregistered hypotheses (H1–H3, H-TTT, ADR-052), with every run's results landed under the hypothesis it bears on |
| [`benchmark-deepswe.md`](benchmark-deepswe.md) | The redirect from SWE-bench Verified to DeepSWE 1.1 (contamination) |
| [`agent-mapping.md`](agent-mapping.md) | The design record of the mapping (ADR-051, ADR-054). Architecture §6 is the current description |
| [`cells/`](cells/) | Per-run cell records (ADR-085's 7B validation) |
| [`ttt/`](ttt/) | Test-time training on Olmo 3 7B: derived context put into the weights (ADR-099); design, results and cells |

Tooling: `pipeline/src/hobbes/{derive,run,bench,ttt}` (product code: `hobbes plan`, `run`, `bench`),
`pipeline/scripts/` (`deepswe_*`, `modal_vllm.py`, `ttt_*`) and `bench/ttt/`.

## Rules already binding this programme

- **P12** (ADR-082, enforced by ADR-086): a Hobbes test has a planner, more than one single-use agent,
  and every implementer's window smaller than the task. Anything else is recorded `arm=model+prompt`.
  Every TTT arm is model + prompt (ADR-099 §8).
- **Contamination** (C-39): no H1 claim may rest on SWE-bench Verified. It needs a post-cutoff or
  decontaminated set.
- **The 7B is the instrument, by speed not capability.** State GPU-hours first, and run ≥ 15 min of
  evaluation before any run over 30 min. **The 27B is untouched** until the mapping fixes are validated
  on the 7B, and then only on a decontaminated set.
- **The harness is a defect until proven otherwise.** Resolve the harness's share before judging a
  model.
- **Preregister, and scope to the sample** (ADR-052, P11). `no-seed` counts as a harness loss, H3 is
  per solved instance, and the planner hit is scored after the arm (ADR-055). A pure score carries the
  familiarity line (ADR-081). TTT's NLL intervals are unit-only (ADR-099, amendment 14).

## Observed register

Each entry states what was seen, its source, and how far it reaches. `hyp` is
[`benchmark-hypotheses.md`](benchmark-hypotheses.md), and `ttt-r` is
[`ttt/olmo3-ttt-results.md`](ttt/olmo3-ttt-results.md).

### Method findings (they bind every later run)

- **MA-1 — SWE-bench Verified is contaminated, by model size, and against Hobbes.** The 27B pure arm
  reproduced gold patches verbatim: 100% of the gold's added lines on xarray (29/29), sklearn (19/19)
  and sphinx (23/23), including xarray's author string "will be removed in version 0.19.0". The 7B
  produced an empty patch on xarray. *hyp* § "CONTAMINATION CAVEAT" (2026-08-22,
  `five-fresh-27b-adr075`); C-39. **Established.** Does not show that every pure solve is recall (the
  protocol "bounds, never proves").
- **MA-2 — Greedy decoding does not reproduce.** At temperature 0 the pure arm varied across runs
  (django: patch / patch / loop-error; sympy hit the gold line in 1 of 3), and so did the planner's
  path (O4). *hyp* § ADR-070 run; [`cells/adr085-validation-7b-2026-08-24.md`](cells/adr085-validation-7b-2026-08-24.md)
  O4. **Established.** A per-instance A/B needs pinned seeds or a large n.
- **MA-3 — Early planner hits measured the 7B's memory, not Hobbes.** Before ADR-072 the planner's map
  was the first 60 modules alphabetically, and held the gold module for 1 of 5 instances. *hyp* §
  ADR-070 run, "Addendum (ADR-072)". **Established; it retracts those hits.**
- **MA-4 — The harness had defects that looked like model failures.** All are fixed:
  - the handoff parser, and repeated edits stacking (ADR-066);
  - clipped reads with no search: 40 of 161 reads clipped (ADR-070, `search_file`);
  - every test re-run refused on a name mismatch (ADR-071), and a missing path answered as "(no
    matches)" (ADR-071);
  - compound commands escalated by the proxy (ADR-075);
  - the stall rule stopping a thinking model (ADR-076);
  - the planner handoff truncated at `max_tokens` (ADR-067).

  Also: `five-fresh-27b` is void as a model verdict (C-54, 104 of 253 execs escalated). *hyp* §
  2026-08-22 runs. **Established.**
- **MA-5 — The brief crowded out the unit's work.** 82% of the brief lay outside the unit (neighbourhood
  11.1k, guarding tests 10.2k and contracts 6.4k chars, against an interior of 171). *hyp* §
  `five-fresh-7b-clean`. **Established.** The brief is now sized to the window (ADR-069), and ADR-083's
  lever 1 cut the rendered context (sklearn 153k → 18k, sympy 117k → 14k) at no cost to gold-file
  coverage.

### Outcome findings

- **MA-6 — The 7B cannot carry out work from derived context.** Six runs on the same five Verified
  instances scored 0/5 each, and after the harness fixes the failures are the model's own. It edits
  from memory, writes without reading, confabulates work and ignores exact paths. In the ADR-072 run,
  sympy's planner found the gold file and test from the graph, and the implementer still wrote from
  memory. *hyp* § 2026-08-22 runs; Qwen2.5-Coder-7B, n = 5 per run. **Established for that set and that
  model.**
- **MA-7 — Once the harness could execute, the harness arm lost to pure: pure 4/5, harness 1/5.** 27B,
  n = 5, and the preregistered falsifier fired. *hyp* § "the ADR-075/076 re-run". **Provisional, and
  confounded by MA-1** ("No H1 claim may rest on this run"). Does not show whether it was decomposition
  or recall that lost.
- **MA-8 — At 27B the planner localises from derived context.** It hit 4 of 5, using search, reads,
  `who_calls` and `tests_guarding`, and the gold metric undercounts (sklearn was solved through a
  non-gold file, C-49). *hyp* § `five-fresh-27b`. **Provisional (n = 5).**
- **MA-9 — The 7B planner rarely writes requirements, and the removal A/B has no usable signal.**
  `requirements:` was written 0/5 at first and 3/5 after one strict re-plan, and 0/5 were solved. The
  A/B is confounded by D5 and O4 ("do not quote A-patches-3 vs B-patches-1"). For the 7B, derived
  context is push-only: the knowledge tools went unused.
  [`cells/adr085-validation-7b-2026-08-24.md`](cells/adr085-validation-7b-2026-08-24.md), 2026-08-24.
  Defects D1–D8 are fixed (ADR-091, ADR-093). **Provisional; the A/B has not been re-run.**
- **MA-10 — Requirement decomposition keeps what a 7B handoff drops.** On stored handoffs, "Add
  evaluation for polylog" was dropped in every 7B sympy handoff and kept by the 27B's. The planner is
  4–12% of the harness's tokens. ADR-085 § Validation (replay); ADR-084. **Established on stored
  records.**
- **MA-11 — DeepSWE on Pier, one task (httpx multipart), is model + prompt only.**
  - 7B: 0/122 in both arms.
  - 27B with commit-on-exit: baseline 115/122, hobbes 107/122.
  - The observation-shaped pair: baseline 122/122, hobbes 120/122.
  - The spans did not narrow reads.
  - Four pairs, about 3 A100-hours each.

  *hyp* § "DeepSWE on Pier"; ADR-078–081. **Retracted as Hobbes evidence by P12 (ADR-082).** Also
  learned: the 27B lost finished work it never committed (hence commit-on-exit, ADR-080), and both arms
  were bound by the 131k window.
- **MA-12 — Probes before the runs.** On `psf/requests`, 8 of 8 instances were seeded and 4 of 8 seeds
  touched a gold file. On astropy, the planner found the place in 2 of 2, and both arms scored 0 of 2.
  ADR-055; *hyp*. **Provisional (n = 8, n = 2).**

### Test-time training (Olmo-3-7B, 300 steps unless stated; ADR-099)

- **MA-13 — No memorised cell exists at 7B.** Olmo scored 0.021–0.129 and Qwen 0.111–0.203, with
  definition recall ≤ 0.06 everywhere. *ttt-r* §6. **Established; H-TTT-4 cannot be read at 7B.**
- **MA-14 — Most of the adapter's NLL gain is the repo's language, not the graph.** Adapter − unaided
  is −0.296 on this repo (147/147) and −0.223 on fastapi. The shuffled control is −0.218, and true −
  control is −0.078; over three seeds, true − control is −0.078 / −0.059 / −0.047. *ttt-r* §3; the
  review record; C-86, C-87. **Established.** The margin bounds the graph's share; it does not measure
  it. *The sources disagree on the prompted block:* *hyp* says it "lowers … by 0.002", while *ttt-r*
  §3 gives A1 − A0 as +0.002 (p 0.56).
- **MA-15 — Training teaches abstention on names, not navigation.** The adapter cut false acceptance on
  invented names from 0.98 to 0.22. It gained nothing on callers (+0.04, p 0.078). The card beats the
  weights on every specific edge (callers 0.68 against 0.10). The adapter's prior overrides the card:
  tests 0.37 against 0.79, and 61 of 102 items gave the verbatim "No test reaches" (C-88). *ttt-r* §§4–5.
  **Established.**
- **MA-16 — One instruction buys more abstention than training.** The base with one instruction went
  from false acceptance 0.90 to 0.00, at a cost of 0.06; the adapter stayed at 0.22. *ttt-r* §4 note.
  **Established.**
- **MA-17 — Edges enter the weights past one epoch, as the NLL gain leaves.** Callers on trained symbols
  at 100 / 300 / 1,000 / 3,000 steps: 0.10 / 0.15 / 0.33 / 0.95. NLL at the same points: −0.30 / −0.30
  / −0.20 / +0.02. *ttt-r* §9. **Provisional (one seed, one repo).**
- **MA-18 — In the agent cell, the manifest finds the files and the adapter alone does not.** Over 50
  units, HSR is A0 1.00, A1 0.82, A2 0.92 and A3 0.80.
  - **H-TTT-2 killed:** +0.11 (p 0.18).
  - **H-TTT-3 killed:** −0.40, CI [−0.53, −0.28].
  - The adapter writes into repo-shaped paths that do not exist.

  *ttt-r* §9b. Defects D-1 to D-5 are registered. **Provisional (one cell, 300 steps).** ADR-099's
  status line still reads "H-TTT-2/3 unmeasured", which predates §9b.

**Spend on record:** TTT about $5.70 for its first session (about 3 GPU-hours), then about 7 GPU-hours
for the follow-ups. The SWE-bench and DeepSWE runs used Modal credit, costed in *hyp*.

## Proposed or held, not run

- **The removal A/B re-run on the 7B,** with an n large enough to absorb O4 (W3; ADR-093). First in line.
- **H1′'s 45-instance complex set, and H2/H3.** No numbers are recorded (*hyp* § the focus benchmark).
- **A decomposed DeepSWE protocol** (W3): design first.
- **TTT:** the 10,000-step point (about 6 A100-hours), the 3,000-step adapter under the primary cell
  (about 0.7), the defect order D-1–D-5, a second unseen repo, and the full grid (25–30 A100-hours).
- **ADR-083 lever 2** (co-change into the interior), deferred (ADR-086). W2's rework selection, path-grain
  write enforcement (C-38), the renegotiation re-pin and per-unit metering (C-35) are not built.

## Closed or retracted

- The Pier pairs and `five-fresh-7b-aided-fix` as Hobbes evidence, and the aided single agent as a test
  shape (ADR-082, labelled by ADR-086).
- `five-fresh-27b` as a model verdict (C-54). The planner hits before ADR-072 (MA-3).
- SWE-bench Verified as the focus benchmark, redirected to DeepSWE. The Qwen2.5-Coder-32B rung was
  replaced by Qwen3.8-27B (*hyp* § Amendment).
- Declined or superseded:
  - the deterministic aid without a planner (C-55), and C-56's reading rule;
  - "the full proposal in every brief" (ADR-084);
  - window-fit in the referenced harness (ADR-079/080);
  - lexically derived requirements on fallback (ADR-093).
- TTT claims withdrawn: "weights hold no edges" (*ttt-r* §9), and "a quarter is the graph" (C-86).
  "Mid-train for abstention" is weakened to "instruct for it".
