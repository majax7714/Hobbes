# Session handoff — the single resume point

**Rewritten 2026-09-04 (evening): Calvin M0 steps 0–5 are done, step 6
waits on Max; the TTT items and ADR-092's decisions are still held for
Max.** Read
this, then the three 2026-09-03 BUILDLOG entries for how the state was
reached, and `docs/workstreams.md` for the backlog by owner. History
lives in the BUILDLOG; this doc is rewritten, never appended into a pile.

---

## ⇢ START HERE NEXT SESSION: Calvin potential step 6 is Max's call, then three more

**Current work (Max, 2026-09-04): evaluating Calvin potential.** The
design is `docs/calvin-potential.md` (M0, *proposed → ready*, v2): the
pipeline run with Calvin's slot filled by a deterministic stub, over
the §9b units re-based at their parent commits, attribution before
verdict. Steps 0–3 and 5 of its §8 (parent re-base, hole schema,
`hobbes template`, grounder v0, the local harness) spend no
orchestrator calls and are all done; step 4 ran on Max's word; step
6 — the run — waits on it. The charter is copied in (`docs/calvin-charter.md`);
the v1 assessment and the two pre-run probes (18% of code hunks outside
spans; 118/182 unresolved terms new) are the record
`docs/ttt-cells/calvin-m0-probe-2026-09-03.md`, reproduced by
`pipeline/scripts/calvin_probe.py` from the parent graphs preserved
under `~/.hobbes/bench/calvin/` (regenerable, `ingest`). **Step 0 is
done:** the 28 contained lane-B ingests ran 2026-09-04 (698 s, median
24 s; `graphs-laneb/`, 176,796 of 176,824 symbol edges semantic) and
both probes read identical on them. **Step 1 is done** (afternoon):
`hobbes.derive.holes` v0 and the hand-written template for
`c59916fe2222` (`bench/calvin/templates/`), its gold fills validating;
five readings for step 2 in the probe record's second addendum — the
literal matcher on backticked non-identifiers, 47 open holes for 4
hunks, `covered_by`, `"none"`, and the SIGNATURE-prune scoped to
functions. **Step 2 is done** (evening): `hobbes.derive.template` and
`hobbes template`; 28 of 28 byte-identical; actual coverage before any
orchestrator round 4% symbol / 89% outside, 596 of 636 non-new hunks
in files no anchor reached — round 1 is load-bearing for this unit set
(the probe record's third addendum, eight v0 rules, the literal cap).
**Step 3 is done** (night): `hobbes.derive.ground` and `hobbes
ground`; the 28 commits as fills grounded at their parents — 28 of 28
identical, apply, and equal the commit byte for byte; 3,760 call sites,
0 NULL, HSR 0 (a poison control says the zero is real); the record's
fourth addendum carries the six grounder defects the gold run surfaced
and C-91 what v0 cannot see (call sites only; Python, Go, TS/JS;
members on values abstained). **Step 4 is done** (later that day, on Max's word, `claude-sonnet-5`
through Anthropic's OpenAI-compatible endpoint, key line
`anthropic_key` → `HOBBES_LLM_API_KEY`): `hobbes.derive.adapter`,
five units through arm T in two passes — the hand unit end to end
(the gold change, 0 NULL, applies, right files 1.0), the other four
each naming a residual: the orchestrator cannot anchor an anchorless
task by itself, a module anchor opens a whole file, new files land
flat, `new` is over-declared. Cost $8 + $2.3 at list; the record's
fifth addendum has both passes. **Step 5 is done** (evening, no
orchestrator; **ADR-100**): `hobbes.derive.harness` — `hobbes verify`
runs a diff's guarding tests (by the testmap, symbol/module/file
grain) in the sandbox image offline, with and without the diff, every
row classed against its baseline; the environment is this checkout's
dependency trees linked in and mounted read-only (`hobbes-session
--mount`, C-92); arm O runs through `hobbes-session` with the proxy's
exec under `calvin.box.policy`, the knowledge tools withheld
(`loop.py --mcp-tools exec`), its patch through the grounder and the
verifier. Calibration on the 28 golds: **26 pass / 1 fail / 1
no-tests, P2F 0, all contained, 559 s** (the fail: tests a commit adds
that need podman inside the container; six harness defects caught and
fixed first — the record's sixth addendum). Arm T's hand unit passes
its 12 guards. A scripted session (`scripts/calvin_scripted_agent.py`)
ran the four runners under policy, had `git push` denied and `curl`
expire to deny, and was harvested, grounded and verified. §9b's five
defects checked off (D-2 for O to be confirmed on the first model
session); D-6 closed. **Next is step 6 — the full run, three arms,
this repo — which is Max's to clear**, with three things to decide
first: candidates in the `ANCHOR` hole and a module anchor as
confirmations rather than bodies (the two protocol changes from step
4), and the model (Sonnet 5 does not honor temperature 0; Haiku is a
third of the cost). One reading from step 5 for that call: **arm O's
manifest from the task text alone is `hobbes plan` on lexical seeds
(C-36) and lands off the gold files** on the hand unit — O measures
the manifest as it really is, and the §4.5 reading will be as much
about C-36 as about the model. The design's own ADR takes 101 when
accepted. Assessment work comes before the next proposal; the §10
fine-tuning wording in the architecture stays as is until then.

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
repos. The register reads **68 active / 20 lifted / 2 superseded**, two
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

## WHERE THINGS STAND (2026-09-03, night)

- **Extraction:** the ten entries lifted, plus C-89 and C-90 (above).
  Register: 90 entries, 68 active, 20 lifted (C-86–C-88 from the review still active: the
  control margin is a bound; the first NLL write-up's conditioning was
  unstated; trained "none" answers override the card). Image rebuilt
  2026-09-03 night (`below-floor` row, the `uses` gloss — C-65).
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

0. Calvin M0 step 6 (`docs/calvin-potential.md` §8; steps 0–5 done): Max's word on the run, the two protocol changes and the model; Max's three calls above; his review of the ten lifts and of ADR-100.
1. Extraction residue the lifts named (no GPU), in order: `tsextract` skips every symlink where the Python walks skip only
   repo-internal ones (C-73's residual); Poetry / PDM manifests are not
   read (C-79's residual); a callee that is itself an expression
   (`handlers[0]()`) is still no site (C-80's residual, C-63's shape).
   date-fns re-ingested: 0.1% → 80.1% capture, 15 of 15 zones, lanes
   7,601 / 0 after C-89 and C-90.
2. If cleared: the 3,000-step adapter under the cell (item 1 above);
   the 10,000-step point; a second unseen repo through the cell.
3. Watch the first CI run when Max pushes (unchanged).
4. W0 residue; the removal A/B re-run; Java follow-ups (W1);
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
