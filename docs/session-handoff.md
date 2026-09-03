# Session handoff — the single resume point

**Rewritten 2026-09-03: the test-time-training experiment (ADR-099)
ran steps 1–4 on the unseen cell; the nine registered-not-fixed entries
and ADR-092's decisions are still held for Max.** Read this, then the
2026-09-03 BUILDLOG entry for how the state was reached, and
`docs/workstreams.md` for the backlog by owner. History lives in the
BUILDLOG; this doc is rewritten, never appended into a pile.

---

## ⇢ START HERE NEXT SESSION: Max's call on three things

1. **The TTT experiment's next step** (`docs/olmo3-ttt-validation.md`
   §6, §8; ADR-099; cell records in `docs/ttt-cells/`; the standing of
   every hypothesis in `benchmark-hypotheses.md` § H-TTT). What the
   session established, on Olmo-3-7B-Instruct with this repo at
   `ebdf7a5` as the unseen cell and fastapi as its replication:
   - a 300-step LoRA on the derived layer lowers gold-diff NLL on
     **every** unit (147/147, −0.296 nats; fastapi 68/68, −0.223);
     the prompted context block moves nothing, alone or on top;
   - a **shuffled-answers control** (same tokens, every relation wrong)
     takes 0.218 of the 0.296; the true graph adds 0.078 (140/147);
   - on held-out navigation the adapter learns the module's file
     (0.985), abstention on distractors (false acceptance 0.98 → 0.22),
     the tests reaching the module (0.52), and **no callers** (0.10);
   - on **trained** questions it scores the same (callers 0.15) — at
     0.35 epochs the weights hold no symbol-grain edge, seen or unseen.
   The design's own next step for this outcome is the **step-count
   ablation (100 / 300 / 1,000)** — two adapters and their NLL/nav
   pairs; the whole of this session cost 3 GPU-hours / $5.70 on
   Modal's meter, and the ablation is about half of it. Step 5 (agent
   runs, HSR/RFE) stays parked. No
   memorised cell exists at 7B (every candidate U or "neither" for both
   Olmo 3 and Qwen-Coder; C-83 seen), so H-TTT-4 needs a model that
   provably recalls a repo, or a version-shift-aware probe.
2. **The nine registered-not-fixed entries** (C-72–C-80, ranked in the
   2026-09-02 handoff, the candidates named in each entry) plus
   **C-85** from this session — a Python repo with no venv loses lane
   B entirely in the container (httpx, fastapi, textual at 0.0% until
   given one) and the record blames the helper; one-line candidate fix
   (always pass `--environment`, an empty listing when no venv).
3. **ADR-092's four embedded decisions** (§Decisions there). Nothing
   blocks on them.

## WHERE THINGS STAND (2026-09-03)

- **Extraction:** unchanged from 2026-09-02 — every compiler-graded
  cell at 100% on every tier it reaches; quic-go 99.6% lower bound.
  Register: 85 entries, 75 active, 9 partial, 7 unsurfaced.
- **The TTT instruments (ADR-099), all in the pipeline and tested (49
  tests):** `hobbes derive-corpus` (`hobbes.ttt.corpus`; `--control
  shuffled`), `hobbes.ttt.units` (git-history and DeepSWE units, both
  NLL prompts attached), `hobbes.ttt.score` (what a reply names),
  `hobbes.ttt.report` (paired bootstrap; NLL by C-84 population;
  navigation with "none recorded" items split out);
  `pipeline/scripts/{modal_ttt,ttt_units,ttt_probe,ttt_report,ttt_nav_report}.py`.
  Modal: app `hobbes-ttt`, volume `hobbes-ttt` (`corpora/`, `units/`,
  `adapters/`, `runs/` — three adapters: hobbes true and shuffled,
  fastapi), serve at 16k on an A10G with the Hobbes adapter registered
  (`ADAPTERS=hobbes-ebdf7a51=…`), scales to zero. Local: worktree
  `~/.hobbes/bench/ttt/hobbes-base` (this repo at `ebdf7a5`, ingested
  contained, its own venv), `~/.hobbes/bench/ttt/{units,runs}/`,
  candidate clones with venvs under `~/.hobbes/deepswe/repos/`.
- **Java, containment, the harness, CI:** as on 2026-09-02.
- **`expand()` in `derive/impact.py` now pops from a heap** — same
  scores and order on 85 seeds, no per-step re-sort.

## NEXT (in order, none cleared to spend compute)

0. Max's three calls above.
1. If the ablation is cleared: `modal_ttt.py train --steps 100|1000`
   on `corpora/hobbes/ebdf7a510eff`, then `nll` and the
   `ttt_probe.py nav` pair per adapter (`--items eval` and `train`);
   read callers on the training sample first — it is the number that
   says whether edges enter the weights at all.
2. Watch the first CI run when Max pushes (unchanged).
3. W0 residue; the removal A/B re-run on a cleared 7B run; Java
   follow-ups (W1); collaborator onboarding — unchanged.

## STANDING POLICY (Max) — read before doing anything

1. **Experiments are PARKED** except the TTT experiment Max cleared on
   2026-09-03; its step 5 and the ablation are not yet cleared.
2. **The 7B is the instrument, by speed not capability.** Compute-
   economics gate: GPU-hours stated first; ≥15 min of evaluation before
   any run over 30 min.
3. **P12 (ADR-082): a Hobbes test decomposes, or it is not a Hobbes
   test.** Every TTT arm is *model + prompt* and is labelled so.
4. **The 27B is untouched** until the mapping fixes are validated on
   the 7B, and only on a decontaminated set.

## PRACTICAL NOTES

- **Always `uv run hobbes` from this checkout with `--repo`** — this
  session ran a worktree's older Hobbes once by `cd`-ing into it
  (ADR-094's incident, again) and the graph looked fine until the
  `built_by` line was read.
- **A Python repo needs a venv before a contained ingest** (C-85):
  `uv venv .venv && uv pip install -e .` in the clone, then ingest.
- **`pkill -f` / `pgrep -f` match the launching shell's own command
  line** when the pattern appears in it — twice this session a script
  killed itself or waited on itself. Kill by PID.
- The Modal keys are read from `secrets.txt` (gitignored) —
  `modal_key_id`, `modal_key_secret`, `llm_key`, `HF_token`,
  `daytona_key`; export them with the `sed` one-liner in the BUILDLOG
  or `hobbes bench run --secrets`.
- The image is 2.79 GB (unchanged); `lane_b` tests skip without it;
  the one deselected venv test is unchanged.
- Bench-run reference (parked) — unchanged from the 2026-09-02 handoff;
  see that BUILDLOG entry.

## Housekeeping

Commit to `main`; never `git push` (Max publishes). One ADR per design
decision; one BUILDLOG entry per session; every concession a `C-n` in
its segment file under `docs/constraints/`. Rewrite this doc; do not
append to it.
