# Session handoff — the single resume point

**Rewritten 2026-09-05 (night, later): Atlas-0 v0 + v1 (`docs/atlas-0.md`, Max's
design — "sparse is not absent") have run end to end — steps 1–2 with
no model, step 3 calibrated on Modal, the sixty-cell v0 grid at five
seeds, then the three v1 worlds (relation absence, packed context,
query-phrasing hold-out) at five seeds, two harness defects found and
fixed on the way and every cell re-read. $16.54 assumed on L4s against
a $25 ceiling. What is next is Max's reading of the v1 record and the
v2 cell it names; API spend stays off the table for everything else,
Modal is open for Atlas-0 only. The TTT items, ADR-101 and ADR-092's
decisions are still held for Max.** Read this, then the three 2026-09-05 BUILDLOG entries
(later, night, night-later) and `docs/atlas-0.md`'s step record, and
`docs/workstreams.md` for the backlog by owner. History lives in the
BUILDLOG; this doc is rewritten, never appended into a pile.

---

## ⇢ START HERE NEXT SESSION: Atlas-0 v0 and v1 are run; Max reads the record and picks the v2 cell

**Done 2026-09-05 (later, night, night-later), for Max's review (BUILDLOG,
three entries):** `bench/atlas0/` — `atlas0 gen [--variant] | check |
evals | score | probe-check | report`, `atlas0.train` (+ `reevaluate`),
`scripts/modal_atlas0.py` (`train | grid | reeval | put | get`), 53
tests, in CI's python job. **$16.54 assumed on Modal L4s to date**
(read Modal's bill): v0's sixty-four cells, v1's eighty, a hundred and
twenty re-reads. Records under `~/.hobbes/bench/atlas0/runs/` (the
README lists the directories; regenerable from the volume
`hobbes-atlas0` with `modal_atlas0.py get`) with a `<dir>-report.md`
beside each. The design doc's step record carries v0 (steps 1–6) and
the v1 section — **the two defects and the results against the
experiment are at its top**, as Max asked.

**What needs Max:**

1. **Read the v1 section** (`docs/atlas-0.md` § Step record › v1): the
   two defects (seed 5's check; the `<nl>` separator under every §6.4
   number, fixed and every cell re-read), the replication (B1/phrase's
   refusal rates are run-to-run; B2/phrase's held-out refusal is 1.00
   in five fresh seeds), and the three worlds' results — B2 reads a
   written relation-absence and acts on it for the token it names,
   treating sparse and absent differently on that question for the
   first time, while the state does not travel to `defined_in`; B1
   reads nothing; no inversion at this T even with packed context; a
   fourth query phrasing drops dense-real to 0.42 (B1) / 0.08 (B2) and
   B2/phrase refuses an unfamiliar question like an untrained name.
   The amended atlas entries are there; the seventh reading (template
   hold-out read as *query-phrasing* hold-out) is in the README.
2. **The v2 cell the record names:** a `defined_in` `UNDEFINED` pair on
   a *disjoint* half of the absent names, lived lines on the other
   half, evaluated on the lived half — does written existence-absence
   get read once the act is available on that question? One world
   field, one grid (B1/B2 × lived+phrase-split × 5 seeds ≈ $1.10). If
   the §6.4 curve matters, a regime in which reading is ever needed
   (facts only in packed lines, or far fewer epochs) is a separate
   world; and any world that asks about phrasing should train more
   than three.
3. **B3's budget** (unchanged): a one-cell calibration ($0.10) would
   say whether frozen keys are a budget or a block; it breaks §5's
   "held constant" and is Max's call. B3 was left out of v1 for that
   reason.
4. **§6.6 as written** reads seed spread as all variance; the
   replication shows B1/phrase's run-to-run spread is as wide. Whether
   the gate should require a fresh-run replicate for any claimed rate
   is a design amendment for the ADR.
5. **The design's ADR** takes 101 or 102 when Max moves it to
   *accepted* (Calvin's takes 101 if first); its §7 constraints open
   then, plus the readings' departures.

**The earlier 2026-09-05 work (unchanged):** `29906e2` (tsextract
symlinks, C-73's residual), `9423fc6` (Poetry / PDM / uv / PEP 735
tables, C-79's residual), `94a9a67` (the expression callee is a site,
`expr-callee`; C-63 surfaced), `20957de` (W0's two build items). This
repo was re-ingested contained at `9423fc6` dirty; **restart the
knowledge server** in any session open across the image rebuild
(C-65).

*The Calvin state below is unchanged from 2026-09-04 (later).*

**Calvin M0 (Max, 2026-09-04): evaluating Calvin potential — held
since the spend rule.** The design is `docs/calvin-potential.md` (M0, v2, *run on four keys*; §10
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
Exercised with no model later the same day (NEXT 1). **Max took API spend and Modal compute off the
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
The one `lane_b` test that failed on this box (the contained venv
listing returning `pip` alone) passes since 2026-09-05: the fixture is a
real venv now, and the old reading — a host symlink the container does
not see — was half right; the other half was `home = /usr` naming the
image's python as the base.

## WHERE THINGS STAND (2026-09-05)

- **Calvin M0** (`docs/calvin-potential.md`; ADR-100 for its harness):
  steps 0–6b done, 6b exercised with no model (the record's eighth
  addendum; `verify-gold-import/`, `verify-t-step6-import/`,
  `calvin_probe.py replay`); the design's ADR takes 101 when Max moves
  it to *accepted*; artifacts under `~/.hobbes/bench/calvin/`. Suite
  1,241 pytest + 3 `lane_b` (1,242 collect on this box, every one
  passing since the venv test's real venv); 32 tsextract node tests.
- **Extraction:** the ten entries lifted, plus C-89 and C-90 (above);
  their three residuals closed 2026-09-05 and C-63 surfaced (the
  register's unsurfaced count — C-19, C-20 — now reads true; C-63 had
  been a third). Image rebuilt 2026-09-05 (the `expr-callee` gloss,
  C-65). Register: **93 entries, 71 active, 20 lifted, 2 superseded** (C-91
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

**First: Atlas-0's review** (START HERE above) — Max's reading of the
v1 record and his call on the v2 cell. Then the queue:

0. ~~Doc drift from the Calvin sprint~~ — **done 2026-09-04 (later):**
   the register count everywhere (93 / 71 / 20 / 2), README's status,
   ADR count and design-docs table, architecture §8's Calvin row,
   workstreams item 8, this doc.
1. ~~**Calvin M0 without a model**~~ — **done 2026-09-04 (later),
   the record's eighth addendum:** the 28 golds re-verified under the
   import grain (`verify-gold-import/`: verdicts identical, `P2F` 0,
   +2,408 rows, the one new `F2F` the box's known venv test as a
   fault); the four arm-T diffs re-verified (`verify-t-step6-import/`:
   unchanged — the `TestProfiles` failures on `00e5aee` were already
   selected at file grain, since T's diff touched the test file);
   template v1's step-2 instruments beside v0's (symbol 4% → 3%,
   outside 89% → 91%, max 333 → 135 holes); the run's round-1 answers
   replayed into v1 (`calvin_probe.py replay`, new, +3 tests): the
   `TestProfiles` tests are asked at tier `import` once a symbol is
   confirmed; 844 holes at the gold's 15 symbols, 1,226 with every
   symbol of the confirmed modules — **the import tier's test holes
   are the next cost door** (one per test in an importing file; group
   or cap them before a wider run — named, not built). Still open:
   ADR-101's body when Max moves the design to *accepted*; his review
   of the ten lifts, ADR-100 and the step-6 record.
2. ~~Extraction residue the lifts named~~ — **done 2026-09-05** (three
   commits above): the helper's symlink rule (C-73), every pyproject
   table (C-79; lock files stay unread by design), the expression
   callee counted and classed (C-63 surfaced, C-80). What each entry
   still names as residual: a file link inside the repo is two lane-A
   copies of one file; a `requirements` file under another name and
   `setup.py`; Go, Rust and Java do not count the expression-callee
   shape, and a literal key (`table["norm"]`) is not bound to its
   property. None met on a real repo. The four 2026-09-02 clones were
   *not* re-ingested for this — their numbers in
   `extraction-evidence.md` predate `expr-callee` (peft and date-fns
   will gain sites in the denominator when they are).
3. ~~W0: the one deselected `lane_b` test; the three duplicate invariant
   pairs~~ — **done 2026-09-05 (later):** the venv test builds a real
   venv and passes in the container (this box included; `ci-graph.sh`
   deselects nothing), I-7/I-8/I-11 retired with the reason in each
   header (8 confirmed of 11; I-9/I-10 stand). Still W0's: watch the
   first CI run when Max pushes; the registry-pulled image and the
   drift audit open when named; `hobbes narrate` on this repo is held
   with spend.
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

- **After an image rebuild, restart the knowledge server** the session
  opened with (`.mcp.json` → `sandbox/knowledge-serve`): it runs the
  image's proxy, and an old build drops a tail class it does not know
  from every count it prints — no error, a smaller number (C-65,
  2026-09-05). The ingest summary on the terminal is the check.
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
