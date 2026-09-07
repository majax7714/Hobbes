# Session handoff — the single resume point

**2026-09-07: CI's red jobs fixed** (the runner has no git identity;
the graph script's redirect target did not exist on a fresh checkout —
BUILDLOG entry; the next push confirms). Otherwise unchanged from the
2026-09-06 pause: nothing is running, no Modal job, no local process;
the tree is clean on `main`, not pushed. Resume at START HERE below —
the first move is Max's choice of T_v2, and nothing spends until he
names it.

**Rewritten 2026-09-06: Max's three Atlas-0 items ran — the prompt-vocabulary
check found a third untrained-token defect under the hold-out world and
the re-read overturned item 1's premise (a held-out phrasing of trained
words reads dense-real 0.97 / 0.89, not 0.42 / 0.08); the B3 context
cells read and follow context (item 2, done); the v2 world is built and
calibrated on one seed (item 3) — and the calibration says the item's
"2–4 epochs" does not exist at 30M: B1 reads before it stores (7–10
epochs: reading 0.9–1.0, conflict-following 0.7–0.9, no fact held) and
reaches the 0.8 criterion only once it is memorising again (14 epochs).
The v2 grid is not launched: T_v2 is Max's call. $17.57 assumed to date
against the $25 ceiling. API spend stays off the table; Modal is open
for Atlas-0 only.** Read this, then the 2026-09-06 BUILDLOG entry and
`docs/atlas-0.md` § Step record › 2026-09-06 (its three sub-sections
carry the tables), and `docs/workstreams.md` for the backlog by owner.
History lives in the BUILDLOG; this doc is rewritten, never appended
into a pile.

---

## ⇢ START HERE NEXT SESSION: Max picks T_v2 (or amends the regime); then the v2 grid

**Done 2026-09-06, for Max's review (BUILDLOG entry; commits `87bb1c0` +
the docs commit after it):**

1. **The procedure and the third defect (item 1).** `atlas0 check`
   reads every eval prompt's words against every arm's corpus; the
   trainer reads the ids against the stream and refuses
   (`UntrainedPromptTokens`). The hold-out world's fourth phrasing had
   `live` / `exercises`, words no corpus trains — the whole held-out
   `defined_in` / `reached_by` reading was that token. Fifth phrasing of
   trained words, corpora byte-identical, twenty cells re-read
   (`runs/v1-holdout-fix-reeval`, $0.08): **held-out dense-real 0.97 /
   0.89 against 0.98 / 0.92 seen; B2/phrase refuses dense-real 0.00 under
   it (was 0.59).** Item 1's premise (question-string → answer-string
   pairs) is withdrawn with the two entry lines; the retitle *memorisation
   regime* stands in the storage-without-reading sense; the B2 decoupling
   and mechanism lines and the §6.6 amendment (two runs per seed,
   `--runs 2`, gate over the union) are in. **Max should read the
   corrected section** — the record says what was done with his edits and
   why.
2. **B3 on the context world (item 2, `runs/v2-b3-context`, five seeds,
   + `v2-b3-context1` at full packing; $0.73):** reads a fact only in
   context 0.44 (B2's rate) with parametric dense 0.29; **follows a
   conflicting context 0.40 / 0.73** — the first block above 0.03; the
   §6.4 inversion measured at full packing (0.93 at step 1,250 → 0.80 as
   the parametric route grows); with nothing to read it still answers
   (`ANSWER` 200/200). B3's entry amended.
3. **The v2 world (item 3) is built** — `--variant v2`, each part a
   field, v0/v1 byte-identical (README table) — five seeds on the
   volume; `--epochs`, `--target-measure read_context_only`, `--runs`;
   71 tests. **Calibration on seed 1 (eight cells, ~$0.3):** 2–4 epochs
   learn nothing at batch 64/16/8 and at sixteen renderings (templates
   8–15 written for it; more renderings is fewer facts, not more tokens);
   an 8-epoch cosine never leaves the plateau; **a 16-epoch cosine reads
   at 7 epochs (0.89, conflict-following 0.74, dense 0.01), saturates by
   10 (1.00 / 0.93), then stores from 11 and inverts (dense 0.07 → 0.83,
   following 0.93 → 0.77, context-only facts 0.09 → 0.95 without
   context) — 0.80 met at 3,100 steps / 13.9 epochs.** B2 on the
   same schedule meets 0.8 at 10.4 epochs, storing and reading together
   (no reading-first phase); **B3 reads 0.125 at 16 epochs — not
   calibrated for reading at this T** (it needs ~3× the tokens; §5's
   "held constant" is the rule in the way).

**What needs Max:**

1. **T_v2.** The item's regime (memorising not the cheaper route; some
   facts never in the weights) and its criterion (B1 ≥ 0.8 from free
   statements) do not meet at 30M in this world. Two honest T's: (a) the
   16-epoch cosine stopped at ~14 epochs — meets the criterion, reads
   §6.1 on an unseen phrasing with reading available, every checkpoint
   on the way recorded (the reading phase and the inversion come free);
   (b) the same schedule stopped at ~10 epochs — the reading regime
   itself, fails the criterion on purpose. **Grid: 90 cells (3 × 3 × 5 ×
   2 runs) ≈ $5–6 at either T, ≈ $11 both;** $17.57 spent of $25 — both
   T's would need the ceiling raised or the runs halved. Launch is
   `modal_atlas0.py grid --world 'v2-seed{seed}' --steps 100000 --epochs
   16 --batch 16 --ckpt-every 100 --seeds 1,2,3,4,5 --blocks B1,B2,B3
   --arms none,phrase,lived+phrase --runs 2 --out v2-grid` (for (b) add
   a step cap — `--steps 2200` with `--epochs` unset — after checking
   the B2/B3 calibration rows; a `--stop-at-step` flag would be cleaner
   and is not written).
2. **The corrected item-1 section** (`docs/atlas-0.md`, "2026-09-06 —
   the memorisation-regime reframe…"): confirm the withdrawal of the
   two entry lines and the retitle's meaning; the `calls` phrasing's
   seed-bistability (0.04–0.80) is a fact about that phrasing to keep or
   drop.
3. **B3's §5 criterion** is retired in favour of reading (`read_context_only`
   ≥ 0.5) for v2; item 3 of the old handoff (a B3 hot-T calibration) is
   moot — B3 reads at T.
4. **§6.6 as amended** is in the design text; the ADR (101/102 on
   *accepted*) takes it and the vocabulary procedure with it.
5. Everything else held: the TTT items, ADR-101, ADR-092's decisions,
   the wider Calvin run.

**Practical, from today:** `modal run`'s prints are buffered until the
function returns — a cell's log is empty until it finishes; `modal
volume ls` shows the cell dir early. `uv run atlas0 …` must run from
`bench/atlas0` (the cwd resets between commands in an agent session).
Worlds and runs local under `~/.hobbes/bench/atlas0/` and on the volume
`hobbes-atlas0` (`v1-holdout-fix-seed{1..5}`, `v2-context1-seed1`,
`v2-seed{1..5}`, `v2r16-seed1`; runs `v1-holdout-fix-reeval`,
`v2-b3-context`, `v2-b3-context1`, `v2-cal-b{64,16,8}`, `v2-cal-e{8,16}`,
`v2-cal-r16-e4`).

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
   header (8 confirmed of 11; I-9/I-10 stand). **CI observed 2026-09-07:**
   every push since 2026-09-04 was red on `go` (the runner has no git
   identity — two test fixtures that commit) and `graph` (the compile
   manifest's redirect into a directory not yet created); both fixed,
   the Go suites re-run under an empty global git config and
   `ci-graph.sh` run end to end on this box — the next push is the
   confirmation. Still W0's: the registry-pulled image and the
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
