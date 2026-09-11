# Calvin M0-Go, round 2 — the audit, then the floor on equal budget

**Status:** handoff (2026-09-12), written for an orchestrator agent that assigns work packages to sub-agents · **Type:** no-spend audit of round 1's artifacts, then a pipeline experiment (preregistered readings, attribution-first) on fresh keys · **Compute:** orchestrator model `claude-haiku-4-5-20251001` via the OpenAI-compatible endpoint; exec local under Podman. No GPU. No Calvin model.
**Depends on:** round 1 as run and closed ([`calvin-m0-go.md`](calvin-m0-go.md): WP-0…WP-10, protocol v0.5, grounder v2, template v2; its §0a pins; its §10 results and gate record); the round-1 artifacts under `~/.hobbes/bench/calvin-go/wp-{5,6,8,10}/`; the gitleaks cell; M0 v2 ([`calvin-potential.md`](calvin-potential.md)).
**Amends:** round 1 §2.1 (unit set: fresh keys), §2.6 (arms: equal budget; the build row in the repair), §4 (three instruments), §5 (readings), §9 (cost). Round 1's pins (§0a) apply unchanged and are not restated except where they move.
**Not in scope:** the security layer (round 1 §8 stands), a Calvin model, any new language, any change to template v2's rendering beyond the sibling's cap.
**ADR:** none yet.

**Terms.** As round 1 (W, A0/A1/A2, WP-n, HSR, RFE, NULL, gensym, hole, fill, hunk, declare-hole). New: **budget** — the number of model calls an arm may make on one key (an exchange in T, a turn in O); both arms share one cap, N, set in WP-14. **vacuous pass** — a verdict of pass on a row where no guarding test executed. **$/pass** — an arm's spend on a key divided by its passes on that key (∞ on 0 passes; the aggregate is spend over passes across keys).

---

## 0. How to run this document (for the orchestrator agent)

Round 1 §0's seven rules apply verbatim. Two additions:

- **Round 1's artifacts are read-only.** `wp-5/`, `wp-6/`, `wp-8/`, `wp-10/` and their `rows.json` are the evidence this round audits; no package rewrites a row in place. Amended readings are written beside the originals (`rows.audited.json`), with the audit package's id on every changed field.
- **The audit gates the spend.** WP-12 decides, on the audit's numbers, whether O's round-1 rows stand as a comparison arm. Nothing in WP-15 or WP-16 starts before WP-12's decision is recorded in §10.

## 0a. Pins that move (2026-09-12)

- **Cutoff.** Haiku 4.5's training cutoff is read from the model card at WP-13 and pinned there; a key is recall-eligible if its commit date precedes it. The recall scan (WP-7b) still runs on every row — forks, mirrors and blog posts can carry a post-cutoff commit.
- **Keys.** Round 1's 20 keys were tuned on three times and are retired from measurement. They may be used for scripted replays (WP-14) only.
- **O's rows.** WP-6's five O rows stand as recorded; whether they stand as a comparison is WP-12's call.
- Everything else in round 1 §0a (the clone, the cell, W's denominator, branches `calvin-go/wp-N`, worktrees from `main`, running Hobbes, kill by PID, WP-x spend nothing unless the block says spend) is unchanged.

## 0b. Orchestrator's pins (2026-09-11)

Facts resolved by the orchestrator before WP-11, so no package re-derives them. Every package reads this section and round 1's §0a with its own block.

- **Where round 1's evidence is.** Units: `~/.hobbes/bench/calvin-go/wp-0/units.jsonl` (`a2_rev: 3`), gold diffs under `wp-0/gold/` (a `<key>.generated.diff` beside 15 of them: `config/gitleaks.toml`, regenerated or applied before tests, as WP-1 did), parent graphs under `wp-0/graphs/`, the candidate pool `wp-0/candidates.jsonl` (145 rows, 2024-09-29 … 2026-02-21; range `(a0f2f4671cfc, 8ad8470]`). Rows: `wp-{6,8,10}/rows.json`. T's per-key records: `wp-{6,8,10}/t-run{1,2}/<key>.{exchanges.jsonl, fills.json, null.json, t.diff, t.json, t.verify.json, usage.jsonl}` (and `t0.*` where the loop fired). O's records: `wp-6/o/`. WP-5's: `wp-5/t-hand/`. Each package's report: `wp-N/report.md`.
- **The cutoff is pinned at WP-11c, not WP-13.** WP-11c's *Does (2)* needs it to date the candidates, and WP-13 reads `cutoff.json`; §0a's "at WP-13" is read as "by WP-13". The model card or models overview states a *reliable knowledge* cutoff and a *training data* cutoff. **The filter uses the later of the two (training data)**: a commit before it may be in the training data, and recall is about what could have been trained on. The source URL and the date it was read go in `cutoff.json`.
- **A preliminary read, not a package number.** In `candidates.jsonl`, only 15 non-excluded rows fall on or after 2025-07-01 and 10 on or after 2025-08-01, before round 1's keys are retired. If the pin lands in mid-2025, WP-13 reports fewer than 20 and Max sets N keys (§2.1). The round does not relax the cutoff filter, and it does not move the pinned SHA (the cell's).
- **§2.3's pass rule is built once, by WP-11a,** in `hobbes verify` (`pipeline/src/hobbes/derive/harness.py`), on branch `calvin-go/wp-11a` with tests in the same commit. The instrument that re-scores round 1 is then the one WP-16 scores with. The orchestrator merges it after the exit and makes the patch bump (ADR-103). WP-11b and WP-11c change no code in the tree; their scripts live in their package directory.
- **WP-11c's dry-run runs against protocol v0.5 as it stands, by script, without editing `adapter.py`.** It builds the declaration-repair hole through v0.5's own functions, with the build error's text where G's NULLs go, and the gold declaration as the scripted reply. Where v0.5 cannot carry a build row at all, the report names the seam. That seam is WP-14's to build and is not a dry-run defect.
- **Worktrees.** A package that writes code makes its own worktree with `git worktree add ~/.hobbes/bench/calvin-go/<wp>/worktree -b calvin-go/<wp> main` and checks that its base is an ancestor of `main`. The harness's `isolation: worktree` cuts from a stale commit and is not used.
- **Reports.** A package writes its artifacts under `~/.hobbes/bench/calvin-go/<wp>/` and returns its report (≤ 40 lines) as its final reply. The orchestrator saves it as `report.md` if the package could not.

---

## 1. Why this round, stated from the record

Round 1 ran T against O three times on the same 20 gitleaks keys at A2 on Haiku 4.5, ~$19 of $30, and read *T < O* each time, not separable on the recall-free keys. Its record supports five statements and forbids a sixth.

1. **The grounder held under pressure.** Across all runs: 0 mis-bound references; every NULL at the right site; ~2,000 sparse-real references resolved per run with 0 sparse NULLs; poison 50/50; gold grounding byte-equal. Track B read the good way — the filler separates sparse from absent. The linker half of the thesis has now met a real model on a real repo and stayed clean.
2. **The arms touched the same files.** Right-files Jaccard: O 0.45, T-loop 0.47–0.51. The difference is in *pass*, and pass means "builds and breaks no guarding test."
3. **T had no compiler in its loop; O had thirty turns with one.** The residual moved NULL-new → declared in the wrong world → declared in the right world, not compiled. That is the protocol converging on the asymmetry: O iterates against `go build`; T's one repair reads G's NULLs and never the build row.
4. **T saw less of the world than O did.** The k = 20 callee cap, the 12-line sibling that cuts before its imports are used, and A2 rev 3's dropped paths were each defensible on cost; together they mean the arm meant to show what a world buys saw the least of it, while O could `ls rules/`.
5. **The unit distribution was the declaration-heaviest and most memorable shape available.** New-symbol and new-file read 0 of 5 in every run; single-file 0.5–0.6; O reproduced gold's new files verbatim on 2 of 5 keys.

The sixth statement — *the socket does not carry weight* — is forbidden by 2–5: it has not been tested on equal footing. It is also not refuted.

**Decision.** Two steps, gated. First, a no-spend audit of round 1's artifacts, because the round's usual process found bugs downstream every time it spent (D-a … D-j), and the pass metric, O's diffs and the templates were never audited. Second, if the audit leaves a comparison standing, the floor re-tested once on fresh, recall-free keys, with the build row in T's repair and one budget for both arms.

**What the round is.** Still the easiest floor: Go, gitleaks, A2. What changes is that the two arms are put on the same footing, and the keys are ones neither arm nor the protocol has seen.

## 2. Changes from round 1

### 2.1 Units — fresh, post-cutoff, shape-capped

Drawn from WP-0's `candidates.jsonl` alternates (`draw_rank >= 5`) and, if those run short, re-derived from the same pinned range. Filters, in order: commit date after the pinned cutoff; round 1's exclusions (vendored/generated, docs-only, dependency bumps, > 8 files); the *add-a-detector-rule* class (`rules/*.go` constructor plus its registration) capped at 5 of 20, the rest drawn from logic, config, CLI, report and detect-path commits. Shapes stratified as round 1. A2 rev 3 (commit message plus touched parent symbols, no paths). W per unit. **If fewer than 20 keys survive the filters, WP-13 reports the count and Max sets N keys; the round does not relax the cutoff filter.**

### 2.2 Anchoring

A2, unchanged. A fixing, not a product.

### 2.3 Harness — the pass metric hardened

`verify` records, per row: **guarding tests executed** (count, ids) and **`gold_tests`**, the verdict of the gold's own test changes applied to the arm's diff. A row is *pass* only if at least one guarding test executed or `gold_tests` reads pass; a build-clean row with neither is **vacuous**, its own class, never counted as pass. Every round-1 row is re-scored under this rule in WP-11a.

### 2.4 Protocol v0.6 — the build row in the repair; the sibling whole; one budget

- **The build row in the repair.** After a declaration is placed and grounded, verify's build row runs; a compile error routes back once, as a repair of that declaration hole, alongside G's NULLs, bounded to one exchange. The error text is passed verbatim, trimmed to the lines naming the declaration's file.
- **The sibling whole.** The declaration hole shows one sibling of the same kind in full, capped by bytes (state the cap from the gitleaks `rules/*.go` distribution, 95th percentile), not by lines; chosen deterministically as WP-9.
- **One budget.** N model calls per key for both arms. T's calls: confirmations + fills + repairs; O's: turns. The arm stops at N and its row is scored as it stands. N is set in WP-14 from round 1's exchange distribution (T's 95th-percentile calls per key, rounded up); O's 30-turn cap is replaced by N.
- **D-i fixed:** `usd_loop` includes the repair exchanges.

### 2.5 Grounder — signatures in the world (WP-14b, deferrable)

SCIP emits signatures; the world stores them for the Go lane, and the grounder judges a call's arity and an undeclared type against them, each a NULL of its own class. Round 1's "right world, not compiled" was arity 2, unbound types 1, unused imports 3 of 7; two of three classes become grounder NULLs. Unused imports stay the compiler's. This is a Hobbes change (a minor bump); if WP-14b overruns a day, it is deferred to §7 and WP-16 runs without it, stated.

### 2.6 Arms

T with the loop inside it (protocol v0.6), O (manifest, exec and file tools, knowledge tools withheld, budget N). Two runs per key in T; O once per key on a paired subset. Same model, same date, model-default sampling.

---

## 3. Work packages — the DAG

**{WP-11a, WP-11b, WP-11c} in parallel → WP-12 (audit gate) → {WP-13, WP-14, WP-14b} in parallel → WP-15 (spend gate) → WP-16.** Every package writes under `~/.hobbes/bench/calvin-go/<wp-id>/` and a `report.md`; every row carries the package id that produced or amended it.

### WP-11a — the pass metric and O's diffs (no spend)

- **Reads:** §2.3; round 1 §10; `wp-6/rows.json`, `wp-8/rows.json`, `wp-10/rows.json` and their verify records; O's five diffs; `ground.py` (grounder v2); `harness.py`.
- **Does:** (1) For every round-1 row with verdict pass, count guarding tests executed; run the gold's own test changes against the arm's diff (`go test`, contained); re-score under §2.3 into `rows.audited.json`. (2) Run grounder v2 over O's five diffs at their parents: NULLs by class, HSR, outside-partition writes, import-outside / unimported, density of every reference.
- **Writes:** `rows.audited.json` (all three packages' rows); `o-grounded/` (per O key).
- **Exit:** every pass row re-classified (pass | vacuous); `gold_tests` on every pass row; O's five diffs grounded with counts.
- **Report:** pass → vacuous counts per arm and package; O's pass with `gold_tests` beside it; O's NULL/HSR/partition counts — the "T reports, O ships" reading, if any; the paired O − T differences recomputed on audited rows.

### WP-11b — templates, flips, replay (no spend)

- **Reads:** `wp-{6,8,10}/` exchanges and templates; `template.py`, `holes.py`, `adapter.py`, `ground.py` and their tests; the gold diffs.
- **Does:** (1) **Gold-needed symbols in the template:** for every T row, the fraction of symbols the gold diff references that were rendered in the template it saw (signature or body), per key and per shape. (2) **The flips:** for every key whose two runs disagreed by verdict (WP-6: 5, WP-8: 4, WP-10: 5), diff the exchanges and classify the flip as sampling or as a protocol-path difference (patterns reply, repair fired, refused fill, budget). (3) **Replay:** every recorded model reply through the current validator and grounder; any reply that validates or grounds differently than recorded is listed with the stamp it was recorded under.
- **Writes:** `needed.json`; `flips.md`; `replay.json`.
- **Exit:** needed-fraction on every T row; every flip classified; replay drift listed (expected: only drift explained by a stamped protocol change).
- **Report:** needed-fraction per shape (the H-s number round 1 never computed); flips by class — any path-explained flip is a defect, numbered; replay drift, numbered if unexplained.

### WP-11c — the scripted dry-run, the cutoff, the ledger (no spend)

- **Reads:** §2.4; WP-10's seven non-building declarations and their `go build` errors; `adapter.py`; `candidates.jsonl`; the model card (cutoff); all `rows.json` and exchange records.
- **Does:** (1) Feed each of the seven build errors into a repair hole with gold's fix as the scripted reply; confirm the loop mechanics accept the reply, re-ground, and verify flips to build-clean. (2) Pin the cutoff; date every round-1 key and every candidate; mark recall-eligible. (3) Reconcile per-exchange USD and tokens against row and package totals; every exchange has a row, every row a stamp.
- **Writes:** `dryrun/` (7 replays); `cutoff.json` (date; keys and candidates marked); `ledger.md`.
- **Exit:** the mechanics close 7 of 7 with gold answers (or the failing ones listed as protocol defects); cutoff pinned and every key dated; totals reconcile to the cent or the seam named.
- **Report:** dry-run closures; how many round-1 keys were recall-eligible; how many candidates are post-cutoff by shape (the number WP-13 needs); ledger seams.

### WP-12 — the audit gate (no spend) — depends on WP-11a/b/c

- **Reads:** the three reports; §1; §5.
- **Does:** write the audited aggregate beside round 1's; state whether O's five rows stand as a comparison (they do not if ≥ 2 of the 5 read vacuous or ship NULLs/partition writes at HSR > 0); re-select §5's round-1 reading on audited rows; list the defects found, numbered from D-k.
- **Writes:** `audit.md`; round 1's §10 amended (dated, beside the original).
- **Exit:** the orchestrator presents `audit.md` to Max. **Max decides:** O stands / O is re-run in WP-16 / the round stops here.

### WP-13 — fresh keys (no spend) — depends on WP-12

- **Reads:** §2.1; `cutoff.json`; `candidates.jsonl`; `calvin_probe.py`.
- **Does:** draw 20 keys per §2.1; construct A2 rev 3; ingest parents; compute W.
- **Writes:** `units.jsonl`; `ingests.json`.
- **Exit:** 20 keys post-cutoff, rule class ≤ 5, shapes stratified; or the count reported and N keys set by Max.
- **Report:** shape counts; rule-class count; W distribution; keys that were alternates vs re-derived.

### WP-14 — protocol v0.6 (no spend) — depends on WP-12

- **Reads:** §2.4; `adapter.py`, `holes.py`, `harness.py` and tests; `wp-11c/dryrun/`; round 1's exchange distribution.
- **Does:** the build row in the repair; the sibling whole with the byte cap stated; the budget N stated and enforced in both arms (`o-units` gains `--budget`); D-i fixed. Protocol stamp v0.6.
- **Writes:** code on `calvin-go/wp-14`, tests in the same commit; `budget.md` (N and the distribution it came from).
- **Exit:** scripted replay: WP-10's seven close 7/7 through the real loop with gold answers; WP-7a's eleven still close 11/11; gold grounding 0 NULL, byte-equal; template v2 byte-identical except the sibling; poison 50/50; pytest green.
- **Report:** N and its derivation; the byte cap; replay counts; defects.

### WP-14b — signatures in the world (no spend, deferrable) — depends on WP-12

- **Reads:** §2.5; the Go lane's SCIP ingest; `ground.py`; the gitleaks parent graphs.
- **Does:** store signatures for the Go lane; arity and undeclared-type NULL classes in the grounder; re-ground WP-10's seven placed declarations.
- **Writes:** code on `calvin-go/wp-14b`; `regrounded/`.
- **Exit:** the arity and unbound-type failures among the seven each raise a NULL of the right class; gold grounding still 0 NULL, byte-equal; pytest green. **Time-box: one day.** Over it, the package reports what it has and is deferred to §7.
- **Report:** classes raised on the seven; graph size delta; whether deferred.

### WP-15 — estimate and gate (no spend) — depends on WP-13, WP-14 (and WP-14b or its deferral)

- **Reads:** the reports; §9.
- **Does:** per-key estimate at Haiku 4.5 list from WP-13's templates and N; the ceiling request.
- **Writes:** `estimate.md`.
- **Exit:** presented to Max. Nothing below starts without the word.

### WP-16 — the run (spend) — depends on WP-15's word

- **Reads:** §2.6, §4, §5; `units.jsonl`; the reports.
- **Does:** T, loop inside, on the fresh keys × 2 runs at budget N; O on a paired subset of 5 fresh keys at budget N (re-run regardless of WP-12's call — fresh keys have no standing O rows). §2.3's pass rule on every row; recall on every row; $/pass on every row; the §4 instruments; §5's reading selected in writing.
- **Writes:** `rows.json`; a cell page `cells/calvin-m0-go-r2-<date>.md`; §10 here.
- **Exit:** every row attributed; the reading written; spend stated. **Spend rules:** stop after T run 1 if it exceeds 2× round 1's per-run T actual (≈ $2.4, stop above $4.8); hard cap = the ceiling.
- **Report:** T vs O on audited pass, J, NULL, vacuous, recall, $/pass; the reading; the §7 next step; spend.

---

## 4. Instruments, with attribution

Round 1 §4 as written (4.3a density, 4.9 W, 4.10 declare-holes) plus M0 §4.1–4.8; paired bootstrap over units, 5,000 resamples, seed 0. Additions:

### 4.11 Pass, vacuous, `gold_tests` — X, U

| result shape | implicates | check | residual |
|---|---|---|---|
| O's round-1 passes mostly vacuous | X (the metric) | `gold_tests` on the same rows | round 1's O − T is void; §1's 2–5 sharpen |
| both arms' passes survive `gold_tests` | — | — | the metric is sound; readings stand |
| T passes survive, O's do not | U/O | O's diffs vs gold's tests | O passed by minimal change; the comparison inverts |

### 4.12 Gold-needed fraction against T pass — H-s

| result shape | implicates | check | residual |
|---|---|---|---|
| T fails where needed-fraction is low | H-s (cap, sibling, A2 rev 3) | which cap hid it | template residual; not the socket |
| T fails at needed-fraction ≈ 1 | O or the protocol | build row, arity | filler or loop; §2.4/2.5 address it |

### 4.13 $/pass at equal budget — the product reading

| result shape | implicates | check | residual |
|---|---|---|---|
| T $/pass < O $/pass, pass within CI | — | budget honored both arms | the socket buys cost at equal outcome |
| T $/pass < O but pass far below | O/protocol | needed-fraction | cheap and wrong; not a claim |
| O $/pass ≤ T | H-s or the idea | §4.12 | the floor does not hold on cost either |

## 5. Preregistered readings

Written before WP-15.

- **On audited round-1 rows, O's lead does not survive §2.3** → round 1's *T < O* is void, not reversed; §1's statements 2–5 stand; the fresh-key run is the first comparison.
- **On fresh keys at equal budget, T ≥ O on pass, T honest where a fill fails to ground, T $/pass lower** → the floor exists; round 1 §7 fan-out starts at step 1 (anchors removed).
- **T ≈ O on pass, T $/pass lower** → the socket buys cost, not outcome, on a dense world with anchors given; that is a product reading and is written as one; fan-out step 1 still runs.
- **T < O at equal budget, needed-fraction ≈ 1, build row in the loop, X clean** → the template interface is the residual, said plainly; the next step is the interface (a file-grain hole, or O with the grounder as a tool), not another protocol patch.
- **T < O with needed-fraction low** → H-s; the caps starved T; raise the caps on the same keys once, no other change.
- **Signatures (WP-14b) move "not compiled" into NULL classes** → the world grew a grain; recorded as a Hobbes result independent of the arm comparison.
- **Two T runs disagree on a key** → as round 1; a path-explained flip is a defect.

## 6. Constraints to open on acceptance

- Go only; gitleaks only; A2 (a fixing).
- Fresh keys are post-cutoff; the recall scan still runs; round 1's keys are retired from measurement.
- One budget N for both arms; O's 30-turn cap is gone.
- *pass* requires an executed guarding test or `gold_tests` pass; *vacuous* is its own class, in every aggregate.
- NULL advisory (M0 C-7) unchanged; the world checks (WP-9) and, if built, arity/type NULLs are grounder classes, not blocks.
- Interface dispatch recorded, not bound.
- No security layer (round 1 §8).

## 7. Fan-out — only if the floor holds

As round 1 §7, with one insertion at the front: **0. WP-14b if deferred.** Then anchors removed (A1, A0), world thinned (fzf, dagger), language (Python keys, Rust), model items, C as a Hobbes lane.

## 8. Deferred

Round 1 §8 stands. Added: **a file-grain hole** (a hole that spans a new file, not a symbol) and **the grounder as a tool in O** (O calls `ground` on its own diff before finishing) — both named as the next interface if §5's fourth reading is selected; neither built this round.

## 9. Cost

- **WP-11 … WP-15:** no spend. WP-11a's `go test` runs are contained and local.
- **WP-16 at Haiku 4.5 list:** T at budget N is bounded above by round 1's runs (~$2.4 per run of 20 keys; the build-row repair adds ≤ one exchange per declaration) — T × 2 runs ≈ $5–6; O at budget N on 5 keys is bounded by round 1's O (~$0.66 per key at 30 turns) — ≈ $2–3.5. **Expected $7–10.**
- **Ceiling to state at WP-15: $12** — round 1's $11.07 remainder plus one dollar, so the ceiling is Max's to reopen, not the round's to assume. Drop order if WP-15's estimate exceeds it: O to 3 keys, then T's second run.
- **GPU:** none.

## 10. Results

(empty until WP-12; WP-16 appends beneath)

**Decisions and gate record** (Max, through the orchestrator; dated):

- 2026-09-11 — the round-2 design recorded in the tree (this file) with the orchestrator's pins (§0b); WP-11a, WP-11b and WP-11c launched in parallel (no spend).
- 2026-09-11 — **WP-11c** exit checked: the scripted dry-run closes 7/7 (v0.5's `declaration_repair` carries a build error in the NULL's place; gold's body under T's name; verify `build-fail` → `pass`, contained); **the cutoff pinned: Haiku 4.5's training-data cutoff Jul 2025** (reliable knowledge Feb 2025; models overview, read 2026-09-11) — post-cutoff means ≥ 2025-08-01; 19 of round 1's 20 keys were recall-eligible (`09242ce9c8a6`, 2025-11-20, was not); **8 usable post-cutoff candidates** (single-file 5, new-symbol 2, multi-file 1, new-file 0; rule-add 0), and the pinned range holds no more (the 19 other post-cutoff commits are excluded by WP-0's rules); the ledger reconciles to the cent ($18.9349), D-i confirmed ($0.0083 folded into `usd_T`).
- 2026-09-11 — **WP-11b** exit checked: needed-fraction on 120/120 T rows (mean at signature grain 0.69–0.96 by shape; at body grain new-file 0.175); 14/14 flips classified (7 sampling, 7 path; candidate defects for WP-12); validator replay drift 2/307, both D-a; grounder base-pass drift explained by the NULL classes v0.4–v0.5 added, but for one candidate (silent zero on gutter text).
- 2026-09-11 — **WP-11a** reopened by the orchestrator (its `gold_tests` had no gold control and read `fail` on every row it touched); defect **WP-11a-1** found and closed (gold's tests lost the `testdata/` fixtures they read); the control reads 7/7. Exit checked: 31 pass rows re-scored — T 9/10/8 → 3/4/2 survive (WP-6/8/10), O 4 → 3 (`93acc6e82adb` vacuous); `gold_tests` n/a 19, fail 6, build-fail 5, pass 1 (O's `a971a324fab5`), conflict 0; O's five diffs ground at 0 NULL, 2 of 5 write outside the partition at HSR 0. Merged to `main` (`2bc8f9f`); **0.1.15-beta** — `hobbes verify` reads `vacuous`, the `gold_tests` verdict; C-115 registered, C-93 amended. WP-12 launched.
- 2026-09-11 — **WP-12** exit checked (`~/.hobbes/bench/calvin-go/wp-12/audit.md`; round 1's §10 amended beside the original). O's five rows **stand under the literal parse** of the gate (1 of 5 vacuous, `93acc6e82adb`; no O row at HSR > 0) and **do not under the stricter parse** (outside-partition writes counting regardless of HSR: 2 of 5, the two recalled keys). Round 2's "void" reading is not selected; round 1's *T < O, not separable on the recall-free keys* stands on audited rows (O − T-loop on O's 5 keys +0.30 / +0.20 / +0.40; recall-free unchanged). Defects D-k (= WP-11a-1, closed), D-l–D-o (open), D-i confirmed. Two facts checked by the orchestrator before presenting: (1) `ed205a5f63e3`'s `gold_tests` build-fail is `go vet` type-checking gold's test, which calls `sources.DirectoryTargets` with gold's new fourth argument (a path filter) that neither O's nor T's diff added — gold's API unbuilt by either arm, not an instrument artifact; (2) upstream gitleaks holds 3 commits past the pinned SHA (to `b58d3f1`, 2026-07-22), all GitHub Actions dependency bumps touching no Go file — moving the pin adds no key, so **8 is the ceiling** on fresh keys in gitleaks. Presented to Max.
