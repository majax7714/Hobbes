# Session handoff — the single resume point

**Reviewed 2026-09-10; Hobbes 0.1.8-beta is tagged `v0.1.8-beta`
(confirmed by Max and the local tag).** Work remains on `main`; publishing
belongs to Max. The baseline, C-101 implementation and callee-shape tools
have now had an agent review: [review record](reviews/2026-09-10-baseline.md).
This is not project-lead acceptance of the pending design choices.

## ⇢ START HERE NEXT SESSION: address the review findings, then decide the floor shapes and Jelly key grain

1. **Java resolve-stage claim:** `java_build_files` copies `.mvn/`,
   `gradle/` and `buildSrc/` wholesale, bypassing the source-suffix
   filter. A local reproduction retained `.mvn/Hidden.java` and
   `gradle/Hidden.kt`. C-66 and architecture §3.2 now state this limit;
   the product notice still overstates it. Fix and test the staging
   boundary before widening build-logic exceptions. C-101's ordinary
   source filtering and Maven wrapper/cache fixes pass their targeted
   tests; no new foreign Java build was run.
2. **Callee-shape metric (H-22):** collapsed recall merges distinct
   same-named targets in one file and calls on one source line. The
   sibling bucket and lane-A attribution also use approximate joins.
   Keep the measured tables as exploratory records; establish canonical
   declaration identity and call-site attribution before adding a second
   recall line to `oracle grade` or treating the priced gains as exact.
3. **Then Max's choices:** class-property function symbols, namespace
   members, constructor target grain, and the Jelly key. Review
   recommendations are in the record; none of these capabilities was
   implemented or experiment runs authorized by this review.
4. **W0 remains open:** the graph CI job forgets earlier red reviews;
   `go/internal/version` and the union fixture's ownership treatment
   still need resolution. Then the standing no-spend queue below.

The renderer's drift check passes; its data has 41 Hobbes cells, all
0.1.8-beta and contained. Foreign records remain separate. The tag is
complete, and remote publication status was not checked. Atlas-0,
Calvin, TTT and other spending decisions remain held as recorded below.

**Done 2026-09-10 (the versioned baseline; BUILDLOG):** 41 Hobbes cells
regraded at 0.1.8-beta (`~/.hobbes/bench/v018/`), every record's last
block dated 2026-09-10 and headed with the version; the renderer reads
it; `docs/comparative/README.md` § the versioned baseline says what
moved (growth on click and this repo's two cells; silent counts on
hono, memchr, quic-go) and why. C-101 registered and lifted (ADR-097
amended): `_JVM_SOURCE_SUFFIXES`, the resolve pass through `./mvnw`,
`MAVEN_USER_HOME`. **Reviewed:** the C-101 entry and three fixes; the staging
boundary finding above takes precedence over widening exceptions.
`v0.1.8-beta` is tagged.

**Done 2026-09-10 (later still; BUILDLOG):** every cheerio (3,249) and
zod (12,038) miss joined to the checker's reading of the callee
expression and to lane A's record at the site. Collapsed to one pair
per (site, target file, target name): cheerio **68.7%** (0.1.7-beta),
zod **58.5%**; function declarations 1,911/1,911 and 6,307/6,385;
methods 41/46 and 2,263/2,345. The diagnostic reported no join miss,
but its approximate attribution cannot establish that universal claim
(H-22). The
two records' 2026-09-10 blocks hold the tables. C-100 lifted; 0.1.7-beta;
image rebuilt; register 100 / 75 / 23 / 2.

**Earlier 2026-09-10 (commits `9f5ca99`, `0bae673`, `0d89907`, `b3774d1`):**
C-98 lifted in both lanes (the TS helper types a file under a
solution-style tsconfig by the referenced project that includes it;
lane B indexes by the same zone map, `--zones`), C-99 (a config with
`references` and neither key is a project), ADR-105 / P13 (a lane B
provider is a pinned batch program with a stated version and a tier
stamp, never a language server). hono 768/768, lanes 4,336 / 1.

**For Max's review and decision:**

1. **The bucket's answer** (`docs/oracle/oracle-misses.md` § the
   callee-shape bucket) — the reading that the gap is grain plus floor,
   not the indexer; and whether the collapsed number (one pair per site
   and callee) should become a second recall line `oracle grade` prints,
   beside the per-signature one, so the records carry both grains.
2. **Three floor shapes, priced (W1), each a symbol-grain change with no
   flow needed:** a class property whose initializer is a function
   literal as a `method` symbol (zod: 1,029 collapsed pairs, 6.2% of the
   cell — v3's `static create = (..) =>`); a `namespace` block's exported
   members as symbols qualified by the namespace (zod: 230 rows,
   `util.assertEqual`); `new X(..)` as a lane A call site (cheerio 5, zod
   ~230 — the helper does not visit `NewExpression`), which needs the
   grader-grain question answered first: the key names the class whose
   constructor answers (the *base* class for an inherited constructor),
   Hobbes would name the class written.
3. **The Jelly cell's key grain** (question 1). The below-floor tail is
   where a flow analysis answers, and its answer is a different
   declaration from the key's (`$(..)` → `initialize`; `schema.parse(..)`
   → the closure assigned in `$constructor`'s init). Against this key
   those edges grade as contradictions. Either a flow-grain
   `tsc-oracle` mode (follow a binding to its value; one afternoon of
   its own) or a grader rule that a below-floor target is confirmed by
   the value bound there — Max's call; then the afternoon: Jelly pinned
   in the image as a batch program (P13), cheerio/zod, `oracle import`
   + the poison check, its Node-stdlib-as-unknown and deliberate
   unsoundness recorded before anything is admitted.
4. **ADR-105 / P13, the C-98 residuals, the hono record's fourth block**
   — as listed on 2026-09-10 earlier (BUILDLOG); tagging is complete.

**The comparative review's queue, as it stands:** item 1 approved; item
2 (syft's keys, dagger's root — the bigger box) off the table (Max,
2026-09-10); item 3 done (ADR-104, then C-98); **item 4 — the next
converters (codebase-memory-mcp, colbymchenry/codegraph) and whether
the competitor cells run under the sandbox image (C-96 narrowed) —
waits on Max's call**; item 5 held.

**Then, no spend (`docs/workstreams.md`):** W1's decorated-declaration
line convention (131 of dagger's 258 lane disagreements), the C-15
namespacing ADR, the directory rollup in `list_blind_spots`; W3's
decomposed DeepSWE protocol as design only; collaborator onboarding.

**Practical, from today:** the session's knowledge server (`.mcp.json`
→ `sandbox/knowledge-serve`) runs the image it started with — restart
it after an image rebuild (C-65). A baseline under an older helper is
cheap: copy the clone (with `.git`), swap `tsextract/extract.mjs` from
`git show HEAD:…` for the run, restore it, `hobbes lanes` both. The
oracle lane's drift test answers `(cached)` after a record changes —
`go test -count=1 ./report/`. A regrade's report goes to a file with
`>`, never through `tee | head` (SIGPIPE truncates it); a record's last
verbatim block is its standing grade; the exception note lives in
`bench/oracle/report/cells.meta.json`, not the record.

**Practical, from 2026-09-09:** long RTA keys run detached (`setsid
nohup`), never under a background command with a ten-minute cap, and
are killed by pid — `pkill -f` matches the session's own shell. A
foreign record is regenerated from its artifacts (`foreign_record.py`),
so hand edits there are lost on the next regeneration: put prose into
`--triage-note` / `--fix-note`.

---

## Held from 2026-09-07 — Atlas-0: Max reads the B4 record; then the T that carries the abstention act, and T_v2

**Done 2026-09-07, for Max's review (BUILDLOG; commits `e991082`,
`d2585ba` — CI; `aeb8ba2` + the record commit after it — the addendum):**

1. **§A.1, the four checks, on saved weights** (`atlas0 mech`, and
   `modal_atlas0.py mech` on a GPU; records under
   `~/.hobbes/bench/atlas0/mech/{,gpu/mech/}`): *B1 reads* = eight heads
   in layers 2/4/5 (L5H1 the most load-bearing; the top eight →
   following 0.91 → 0.055 vs 0.55 random; a limit: the bottom heads are
   necessary too — they build the query); *B1 stores* = the FFNs of
   layers 2–7 together (0.3–0.4 each, reading holding; layer 0's FFN is
   structural); *B2 refuses* is **not a norm** — the tied head pushes
   every never-a-target row the same way, so never-seen names have the
   largest displacement; the act is a linear direction in the row
   (probe 0.86–0.97), closest to the input-driven displacement in the
   phrase arm; *B3 follows* = seven heads of layer 0 plus L4H3,
   redundant. The trainer now saves checkpoint weights on request
   (`--save-weights-every`) — until today no cell had any but its last.
2. **B4** (`atlas0.train.Types`): R_k = I + A_k B_kᵀ per layer, one
   router distribution per pair, Gumbel-softmax in training, argmax at
   evaluation, pair-entropy + usage-balance under λ; the three exits
   met (K = 1 reproduces B1's loss curve to the digit). A B4 cell is
   **$0.18** (3× the estimate; the `(B, h, K, T, T)` correction) — the
   reason the grid ran at one run per seed.
3. **The λ sweep (seed 1):** λ = 0 stores 0.815 (B1 0.83), reads 1.0,
   follows a conflict 0.36 at the plateau (B1 0.77); 0.01 stores 0.61
   and never copies (≤ 0.195); 0.03 and 0.1 copy (0.85–0.995) and store
   nothing (0.03–0.05); 1.0 learns nothing. At every λ half the layers
   collapse to one type whose operator is the identity; where the
   inventory spreads (layers 5–7) NMI vs relation 0.16–0.37; the router
   is hard from step 300 (the temperature never acted).
4. **The grid (`runs/v2-b4-grid`, 30 cells, $3.38; reports at 3,100
   and at 2,200 beside it):** B4 = B1 on storing (within 0.08, loss
   delta 0.00 at the plateau), on the sibling pull (0.23–0.25 vs
   0.22–0.24), no relation-conditioned similarity; the copy route
   weaker in every arm (0.65/0.71/0.82 vs 0.74/0.75/0.86), not
   separable at five seeds; the router one identity operator per layer
   on the training distribution in every cell; **`UNDEFINED` 0.00 in
   both phrase arms, trained pairs included** — the reading regime does
   not learn the act from fourteen exposures. The B4 entry is in the
   record; §A.7 branch 3 (B4-given: typing given, not learned) is what
   the results select.

**What needs Max:**

1. **The T that carries the abstention act.** §A.5.3 (does refusal
   travel) cannot be read at T_v2: no block refuses anything. Either
   the memorising T (3,500 steps, batch 64 — where v0/v1 read refusal;
   the reading route is then gone) or §A.7 branch 2's computed target
   (`NO_EDGE` from the typed signal) — and in a B4-given block, if
   branch 3 is taken. Each is a design choice; the grid at either is
   ~$3.5–4 (B4 cells at $0.18) plus B1's.
2. **The grid's second run** (§6.6's union): ~$3.8, taking the item to
   ~$8.5 and the programme to ~$26 against the $25 ceiling; nothing in
   the tables suggests the copy-route difference would separate.
3. **T_v2 for the v2 grid proper** (still open from 2026-09-06), now
   with a new fact: at 3,100 the storing plateau is seed-variable
   (B1/none dense-real 0.26–0.82 over five seeds; seed 1's 0.83 was the
   top). A per-cell stop at target, or a longer cap, or the reading
   read at 2,200 alone.
4. **The corrected item-1 section and §6.6 as amended** (unchanged from
   the 2026-09-06 handoff); the ADR number for the design (and now the
   addendum) on *accepted*.
5. Everything else held: the TTT items, ADR-101, ADR-092's decisions,
   the wider Calvin run.

**Practical, from today:** `pkill -f` matched this session's own shell
again (the launching loop died with it — kill by PID); a `for` loop
over checkpoints on CPU is an hour per B1 check — use `modal_atlas0.py
mech` (a minute each, ~$0.02); `Path.with_suffix` eats a dotted name's
tail (`b4-lam0.01` → `b4-lam0`) — the drivers build paths by string
now; `modal volume ls` shows a cell's `ckpt/` early, the logs stay
buffered; the grid's B4 cells run 4 at a time at ~14 min each.

*The Calvin state below is unchanged from 2026-09-04 (later).*

**Calvin M0 (Max, 2026-09-04): evaluating Calvin potential — held
since the spend rule.** The design is `docs/calvin/calvin-potential.md` (M0, v2, *run on four keys*; §10
has the results, §8 the step record, the charter is
`docs/calvin/calvin-charter.md`); the per-task record with attribution is the
seventh addendum of `docs/calvin/cells/calvin-m0-probe-2026-09-03.md`;
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
launching and run four keys first. The design's ADR takes the next available
number when Max moves it to *accepted*.

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
   handoff, tabled by Max for this session (`docs/ttt/olmo3-ttt-results.md`
   §1 amended, §9, §9b, §10; the second cell record
   `docs/ttt/cells/hobbes-olmo3-7b-2026-09-03-review.md`; standing in
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

## WHERE THINGS STAND (2026-09-07)

- **Atlas-0** (`docs/atlas0/atlas-0.md`; `bench/atlas0/`, 84 tests): v0, v1,
  the 2026-09-06 items and the B4 addendum run; worlds and runs under
  `~/.hobbes/bench/atlas0/` and on the volume `hobbes-atlas0` (the
  README lists the run directories); $22.28 assumed to date of $25.

- **Calvin M0** (`docs/calvin/calvin-potential.md`; ADR-100 for its harness):
  steps 0–6b done, 6b exercised with no model (the record's eighth
  addendum; `verify-gold-import/`, `verify-t-step6-import/`,
  `calvin_probe.py replay`); the design's ADR takes 101 when Max moves
  it to *accepted*; artifacts under `~/.hobbes/bench/calvin/`. Suite
  1,251 pytest + 3 `lane_b` (every one passing on this box, the
  `lane_b` three on the 0.1.5-beta image); 35 tsextract node tests
  (2026-09-10).
- **Extraction:** the ten entries lifted, plus C-89 and C-90 (above);
  their three residuals closed 2026-09-05 and C-63 surfaced (the
  register's unsurfaced count — C-19, C-20 — now reads true; C-63 had
  been a third). Image rebuilt 2026-09-05 (the `expr-callee` gloss,
  C-65). Register: **99 entries, 75 active, 22 lifted, 2 superseded** on
  2026-09-10 (C-94–C-96 from the comparative programme, C-97/C-98 from
  ADR-104, C-98 lifted and C-99 registered and lifted 2026-09-10; at
  2026-09-07 it read 93 / 71 / 20 / 2 — C-91
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

**First: Max's review of the C-98 lift** (START HERE above). The
Atlas-0 decisions and every other experiment stay held (Max,
2026-09-10). Then the queue:

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
- **The key file is off the tree (2026-09-09):** `secrets.txt` was at
  the root, gitignored and never committed; Max moved it to a local
  folder outside the repo. `hobbes bench run --secrets <path>` is the
  only reader and takes any path (the Modal scripts use Modal's own
  secret store). Keys it holds: `modal_key_id`, `modal_key_secret`,
  `llm_key`, `HF_token`, `daytona_key`.

## Housekeeping

Commit to `main`; never `git push` (Max publishes). One ADR per design
decision; one BUILDLOG entry per session; every concession a `C-n` in
its segment file under `docs/constraints/`. Rewrite this doc; do not
append to it.
