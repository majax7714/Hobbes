# Session handoff — the single resume point

**Rewritten 2026-09-03 (evening): Max's ten TTT follow-ups ran; the
nine registered-not-fixed entries and ADR-092's decisions are still
held for Max.** Read this, then the two 2026-09-03 BUILDLOG entries for
how the state was reached, and `docs/workstreams.md` for the backlog by
owner. History lives in the BUILDLOG; this doc is rewritten, never
appended into a pile.

---

## ⇢ START HERE NEXT SESSION: Max's call on four things

1. **The TTT experiment after the review** (`docs/olmo3-ttt-results.md`
   §1 amended, §9, §9b, §10; the second cell record
   `docs/ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`; standing in
   `benchmark-hypotheses.md` § H-TTT, two dated paragraphs). The
   headline moved: **edges enter the weights by 3,000 steps** (callers
   on trained symbols 0.95; a quarter of a never-seen symbol's callers,
   two thirds of its impact set) **while the gold-diff NLL gain leaves
   entirely**, and a control without the graph reproduces the NLL gain
   and learns nothing navigable. At the agent grain (50 derived units,
   four file-tools-only arms, the 300-step adapter) the manifest finds
   the files (RFE 0.41) and the adapter alone does not (0.01,
   confabulated repo-shaped paths): H-TTT-2 and H-TTT-3 killed. One
   instruction buys the base more abstention (FA 0.00) than the adapter
   has (0.22). Held: the **10,000-step point** (≈ 6 A100-hours alone)
   and the natural next cell — **the 3,000-step adapter under the
   primary cell** (~0.7 A100-hour: the adapter is on the volume at
   `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/cc9e99c14215`;
   `TTT_APP=hobbes-ttt-cell … deploy` with it registered, then
   `ttt_cell.py run … --arm A2=<name> --arm A3=<name>` into the same
   cell dir; rows are keyed by arm, so name them A2_3000 / A3_3000 and
   add the arms to `cell.ARMS` first).
2. **The cell's defect register** (record § Item 9, D-1–D-5): no arm
   executes and nobody runs the guarding tests; HSR is a regex over
   emitted code, not the lane-A walk; a small HSR denominator; shared
   unaided runs. Which to fix before the next cell is Max's call.
3. **The nine registered-not-fixed entries** (C-72–C-80) plus C-85
   (venv-less Python repo loses lane B) — unchanged, ranked in the
   2026-09-02 handoff.
4. **ADR-092's four embedded decisions.** Nothing blocks on them.

## WHERE THINGS STAND (2026-09-03, evening)

- **Extraction:** unchanged from 2026-09-02. Register: 88 entries, 78
  active (C-86–C-88 from the review: the control margin is a bound; the
  first NLL write-up's conditioning was unstated; trained "none"
  answers override the card).
- **The TTT instruments (ADR-099 + amendments 9–14; 1,142 pytest):**
  `hobbes derive-corpus` (`--paraphrases K`, `--control
  shuffled|shuffled-all`), `hobbes.ttt.units` (four conditionings,
  hand-written tasks by commit), `hobbes.ttt.score` (v2),
  `hobbes.ttt.report` (`report_arms`, the override probe),
  `hobbes.ttt.probe` (contexts incl. `card-refuse`, version-aware files
  score), `hobbes.ttt.cell` (the primary cell);
  `pipeline/scripts/{modal_ttt,ttt_units,ttt_probe,ttt_report,ttt_nav_report,ttt_rescore,ttt_override_probe,ttt_cell}.py`;
  `loop.py --no-bash --tool-choice none`. Proposals:
  `bench/ttt/proposals-hobbes-ebdf7a5.jsonl`.
- **Modal:** app `hobbes-ttt` (navigation serve, last deployed on an
  A100 with six adapters; scales to zero) and `hobbes-ttt-cell` (the
  cell's A100 serve, 32k, the 300 adapter; scales to zero) — both
  deployed, both idle. Volume `hobbes-ttt`: eight adapters under
  `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/` (100
  `398686230fb0`, 300 `04195d188e61`, 300 s1 `2615369b529f`, 300 s2
  `fe7318f636eb`, 1,000 `46840a203884`, 3,000 `cc9e99c14215`, 3,000×4
  `629986a94504`, shuffled-all `047bc3b4ac33`), the shuffled control
  under `hobbes-shuffled/`, fastapi under `fastapi/`; corpora
  `corpora/hobbes{,-k4,-shuffled-all}/ebdf7a510eff`; units
  `units/*-cond.jsonl`; runs `runs/`. Local mirrors under
  `~/.hobbes/bench/ttt/{runs,units,cell-hobbes}/` — the cell dir holds
  `units.jsonl`, `runs.jsonl` (200 rows), the transcripts under
  `work/`, `scores.jsonl` (extractor v2; v1 kept beside) and
  `report.json`.
- **Compute this session:** ≈ 7 GPU-hours by the manifests; read the
  meter before quoting.

## NEXT (in order, none cleared to spend compute)

0. Max's four calls above.
1. If cleared: the 3,000-step adapter under the cell (item 1 above);
   the 10,000-step point; a second unseen repo through the cell.
2. Watch the first CI run when Max pushes (unchanged).
3. W0 residue; the removal A/B re-run; Java follow-ups (W1);
   collaborator onboarding — unchanged.

## STANDING POLICY (Max) — read before doing anything

1. **Experiments are PARKED** except what Max clears by name; the TTT
   review list is done, its two held points are not cleared.
2. **The 7B is the instrument, by speed not capability.** GPU-hours
   stated first; ≥15 min of evaluation before any run over 30 min.
3. **P12 (ADR-082):** every TTT arm is *model + prompt* and is labelled so.
4. **The 27B is untouched** until the mapping fixes are validated on
   the 7B, and only on a decontaminated set.

## PRACTICAL NOTES

- **Always `uv run hobbes` from this checkout with `--repo`** (ADR-094's
  incident, twice now).
- **Olmo 3 on vLLM has no tool-call parser here:** send no `tools`
  field (`loop.py --tool-choice none` puts the schemas in the system
  prompt as `<functions>` and reads `<function_calls>` from the text);
  a request with `tools` gets a 400 whatever `tool_choice` says.
- **An A10G holds one adapter at 16k;** three do not fit at 8k either
  (`SERVE_GPU=A100-80GB` for a multi-adapter serve; `--max-loras` is
  capped at four).
- **`modal run`'s remote prints are buffered** until the function
  returns; read `modal app list` / `modal app logs` for progress, and
  stop an ephemeral app with `modal app stop -y <id>` — killing the
  local client does not stop the container.
- **Never rescore in place:** `ttt_rescore.py --out` a new file; the
  cell's `scores-extractor-v1.jsonl` is the precedent.
- `pkill -f` / `pgrep -f` match the launching shell; kill by PID (use
  `ps | grep "[l]oop.py"`).
- Keys in `secrets.txt` (gitignored): `modal_key_id`, `modal_key_secret`,
  `llm_key`, `HF_token`, `daytona_key`.

## Housekeeping

Commit to `main`; never `git push` (Max publishes). One ADR per design
decision; one BUILDLOG entry per session; every concession a `C-n` in
its segment file under `docs/constraints/`. Rewrite this doc; do not
append to it.
