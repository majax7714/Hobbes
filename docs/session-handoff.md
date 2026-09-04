# Session handoff — the single resume point

**Rewritten 2026-09-04 (later): Calvin M0 step 6 ran on four keys and
is written up, the four no-spend fixes are in, and Max has taken API
spend and Modal compute off the table for the next steps — the queue
is the no-spend work in NEXT; the doc drift the Calvin sprint left
(register count, README, architecture §8, workstreams) is corrected;
the TTT items and ADR-092's decisions are still held for Max.** Read this, then the 2026-09-04 BUILDLOG entries for how the
state was reached, and `docs/workstreams.md` for the backlog by owner.
History lives in the BUILDLOG; this doc is rewritten, never appended
into a pile.

---

## ⇢ START HERE NEXT SESSION: Calvin M0 is measured on four keys; spend is off the table, the no-spend queue is next

**Current work (Max, 2026-09-04): evaluating Calvin potential.** The
design is `docs/calvin-potential.md` (M0, v2, *run on four keys*; §10
has the results, §8 the step record, the charter is
`docs/calvin-charter.md`); the per-task record with attribution is the
seventh addendum of `docs/ttt-cells/calvin-m0-probe-2026-09-03.md`;
every number is reproduced by `pipeline/scripts/calvin_probe.py` from
the artifacts under `~/.hobbes/bench/calvin/` (`graphs-laneb/` the 28
parent ledgers, `templates/`, `ground/`, `t-step6/`, `verify-t-step6/`,
`verify-t0-step6/`, `o-step6/`, `rows-step6.json`; the sessions under
`~/.hobbes/sessions/calvin-o-*`). Steps 0–6 of §8 are done; step 7's
write-up is in §10 for the four keys.

**What step 6 read (Sonnet 5, keys `00e5aee` `c59916f` `b8afd41`
`d509835`, three arms each):** T pass 1 / fail 1 / empty-diff 1 /
no-tests 1, RFE 0.32 / 0.68 / 0.32, HSR 0, $6; T-loop = T, closing 2 →
0 near-miss NULLs on the one key with any; O pass 1 / no patch 3 under
a 30-turn cap, RFE 0.08 / 0.08 / 0.25, $17. About $35 spent all in
(the 28-key launch was cut by Max after the first units read $4–5 each
per arm). The readings: T > O where both solved and honest where its
anchors fail; O's manifest is lexical (C-36) and hit the gold at
Jaccard ≤ 0.10; **the module anchor is the cost door** (three
confirmed module words → 1,068 holes → $5 for two right edits); **the
template misses tests that reach an edited module through a
module-level value** (`PROFILES`: the right code failed exactly the
three tests the gold changed); **candidates in the `ANCHOR` hole bind
(5/5) but do not find (0/5 gold)**; new-file placement moved from flat
to nested on a prompt line; the same prompt confirmed 1 of 6 and 0 of
6 across passes.

**The four no-spend fixes are done (the same night, on Max's word;
design §8 step 6b):** a module anchor opens confirmations per symbol,
not bodies (template **v1** — regenerate with `calvin_probe.py
templates … --out ~/.hobbes/bench/calvin/templates-v1`; the step-2 set
is `templates/` and is v0: the code refuses it now); importer tests are
guards in the template (tier `import`) and the verifier (import grain,
C-93 amended); the box policy allows the read-only toolchain probes and
denies `env`; `loop.py --token-budget` rides every arm-O argv at 1M.
None of it re-run. **Max took API spend and Modal compute off the
table on 2026-09-04 (later)** — the wider run is held, and what comes
next is the no-spend queue (NEXT below). When a run reopens, the
number is the total ceiling and the key count. Per-key cost at the *old* shape was T
$0.1–5 (module explosions) and O $2.5–5.2 (the 30-turn cap); the
template fix removes the explosions (bodies before confirmation 99 →
45 over the 28) and the budget flag caps O at ~$3 a session, so a
28-key, three-arm run should now read order $30–60 — state it before
launching and run four keys first. The design's ADR takes 101 when Max
moves it to *accepted*.

**Also this session:** protocol v0.2 (`2ed0d11`: candidates in the
`ANCHOR` hole; `loop.py --sampling model-default`, Sonnet 5 rejects
`temperature`; arm T's pre-loop diff kept as `.t0.diff`);
`calvin_probe.py rows` (the §5 rows); the loop's stall discipline
(7B defaults) cut every first-launch O session off at 12 turns of
reading — run with `--nudge-after 15 --stall-after 20`, the three
records kept under `o-step6-stall6/`, architecture §6.2 says the
budget is per run. Assessment work comes before the next proposal;
the §10 fine-tuning wording in the architecture stays as is until
then.

1. **The TTT experiment after the review** — unchanged from the evening
   handoff, tabled by Max for this session (`docs/olmo3-ttt-results.md`
   §1 amended, §9, §9b, §10; the second cell record
   `docs/ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`; standing in
   `benchmark-hypotheses.md` § H-TTT). Held: the **10,000-step point**
   (≈ 6 A100-hours) and **the 3,000-step adapter under the primary cell**
   (~0.7 A100-hour; the adapter is on the volume at
   `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/cc9e99c14215`;
   `TTT_APP=hobbes-ttt-cell … deploy` with it registered, then
   `ttt_cell.py run … --arm A2=<name> --arm A3=<name>` into the same
   cell dir; name the arms A2_3000 / A3_3000 and add them to `cell.ARMS`).
2. **The cell's defect register** (record § Item 9, D-1–D-5) — which to
   fix before the next cell.
3. **ADR-092's four embedded decisions.** Nothing blocks on them.

**Done this session, for review (2026-09-03 night BUILDLOG):** C-72–C-80
and C-85 lifted in four commits (`89c819a`, `0a06e8a`, `5562271`,
`a60777f`), then C-89 found on date-fns and fixed the same hour (`3da8c07`) and
C-90, registered there, fixed on Max's word the same night, each with tests, the register entry moved to its segment's
lifted section, the architecture amended, and the evidence log's new
section; the four 2026-09-02 clones re-ingested to confirm on the real
repos. The register read **68 active / 20 lifted / 2 superseded** at that
point (71 active now, C-91–C-93 from Calvin M0), two
entries *unsurfaced* (C-19, C-20), none inflating a number. Things Max
may want to look at: the Python capture line drops a few points on
every repo because C-80 adds real calls to the denominator (this repo
81.7% of 14,352; peft 68.3% of 45,593 — the same percentage, 3,643 more
sites); the `uses` gloss now says *"where no call site was detected"*.
One `lane_b` test fails on this box (2026-09-04 night) and fails the
same at HEAD: the contained venv listing returns `pip` alone
(`test_scipsource.py::TestDeclaredDependencies::test_venv_environment_lists_the_venvs_own_distributions`)
— an environment reading (the fake venv's python is a host symlink the
container does not see), not a tree change; CI's box is the check.

## WHERE THINGS STAND (2026-09-04, later)

- **Calvin M0** (`docs/calvin-potential.md`; ADR-100 for its harness):
  steps 0–6b done; template v1 regenerated (`templates-v1/`), nothing
  re-run under it; the design's ADR takes 101 when Max moves it to
  *accepted*; artifacts under `~/.hobbes/bench/calvin/`. Suite 1,227
  pytest + 3 `lane_b` (1,228 collect on this box).
- **Extraction:** the ten entries lifted, plus C-89 and C-90 (above).
  Register: **93 entries, 71 active, 20 lifted, 2 superseded** (C-91
  from Calvin step 3, C-92/C-93 from step 5, ADR-100; the count is
  checked against the segment headings, not a summary line; C-86–C-88 from the review still active: the
  control margin is a bound; the first NLL write-up's conditioning was
  unstated; trained "none" answers override the card). Image rebuilt
  2026-09-03 night (`below-floor` row, the `uses` gloss — C-65).
- **The TTT instruments (ADR-099 + amendments 9–14):**
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

## NEXT (in order; API spend and Modal compute are off the table — Max, 2026-09-04)

0. ~~Doc drift from the Calvin sprint~~ — **done 2026-09-04 (later):**
   the register count everywhere (93 / 71 / 20 / 2), README's status,
   ADR count and design-docs table, architecture §8's Calvin row,
   workstreams item 8, this doc.
1. **Calvin M0 without a model** (`docs/calvin-potential.md` §8 step
   6b is in, nothing exercised): re-verify the step-6 arm-T diffs under
   the importer-test guard (`hobbes verify` is local Podman, no model —
   the `PROFILES` false pass on `c59916f` should now be a caught
   failure); recompute the step-2 anchor and coverage instruments on
   template v1 (`calvin_probe.py`) so the 99 → 45 bodies change has a
   coverage number beside it; draft ADR-101's body from the design when
   Max moves it to *accepted*. Max's review of the ten lifts, ADR-100
   and the step-6 record still stands.
2. Extraction residue the lifts named (no GPU), in order: `tsextract` skips every symlink where the Python walks skip only
   repo-internal ones (C-73's residual); Poetry / PDM manifests are not
   read (C-79's residual); a callee that is itself an expression
   (`handlers[0]()`) is still no site (C-80's residual, C-63's shape).
   date-fns re-ingested: 0.1% → 80.1% capture, 15 of 15 zones, lanes
   7,601 / 0 after C-89 and C-90.
3. W0: the one deselected `lane_b` test (a real venv in the fixture —
   the same test fails on this box); the three duplicate invariant
   pairs (I-1/I-7, I-2/I-8, I-6/I-11); watch the first CI run when Max
   pushes (unchanged).
4. W1 / W3 items that spend nothing: the decorated-declaration line
   convention, the C-15 namespacing ADR, the directory rollup in
   `list_blind_spots`, the decomposed DeepSWE protocol as design only;
   Java follow-ups (W1); collaborator onboarding — unchanged.

**Held, with all spend (not cleared, not scheduled):** the wider Calvin
run (its ceiling and key count when it reopens; four keys first on
template v1); the 3,000-step adapter under the cell and the
10,000-step point (item 1 of the TTT list above); the removal A/B
re-run on the 7B; a second unseen repo through the cell; `hobbes
narrate` on this repo.

## STANDING POLICY (Max) — read before doing anything

0. **API spend and Modal compute are off the table for the next steps
   (Max, 2026-09-04)** — the queue is no-spend work; a run reopens
   only when Max names it and its ceiling.
1. **Experiments are PARKED** except what Max clears by name; the TTT
   review list is done, its two held points are not cleared.
2. **The 7B is the instrument, by speed not capability.** GPU-hours
   stated first; ≥15 min of evaluation before any run over 30 min.
3. **P12 (ADR-082):** every TTT arm is *model + prompt* and is labelled so.
4. **The 27B is untouched** until the mapping fixes are validated on
   the 7B, and only on a decontaminated set.

## PRACTICAL NOTES

- **A model run: state the total dollar ceiling and run ~4 units
  first** (2026-09-04 night: 28 keys launched at "order $50–120", cut
  to 4 by Max after the first units read $4–5 each per arm). Kill by
  PID and `podman kill` the session containers; the per-unit records
  already written survive.
- **`pgrep -f` / `pkill -f` match your own waiting shell too** — a
  `for p in $(pgrep -f X)` loop killed the `until … pgrep -f X` waiter
  beside it (2026-09-04); wait on a log line, kill by PID.
- **Always `uv run --project pipeline hobbes … --repo <target>` from
  this checkout** (ADR-094's incident, twice now) — and never `cd` into
  a target repo that has a `pyproject.toml` and `uv run` there: uv
  treats it as the project and **creates a `.venv` inside it** (the
  2026-09-03 C-85 repro did exactly that on its first attempt, and the
  "venv-less" repo had a venv).
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
