# Calvin M0-Go — the floor round: the socket on a dense world

**Status:** handoff (2026-09-11), written for an orchestrator agent that assigns work packages to sub-agents · **Type:** pipeline experiment (preregistered readings, attribution-first) · **Compute:** orchestrator model `claude-haiku-4-5-20251001` via the OpenAI-compatible endpoint; exec local under Podman. No GPU. No Calvin model.
**Depends on:** M0 v2 as run (`calvin-m0-socket-v2.md` — in this tree, [`calvin-potential.md`](calvin-potential.md); §0a: template v1, grounder v0, harness ADR-100, adapter protocol v0.2); the Go lane of Hobbes (gitleaks cell: precision 100%, recall 98%; key = compiler-derived, RTA from roots); Atlas-0 through the B4 addendum; ADR-101's field survey.
**Amends:** M0 §3.1 (unit set), §2.2 (model), §2.3 (grounder: density field, Track B), §4 (two instruments). Everything else in M0 v2 stands.
**Not in scope:** the executor's security layer (§8 lists it, nothing here builds it), a Calvin model, any new language.
**ADR:** none yet; takes the next number when moved from handoff to accepted.

**Terms.** As M0 v2 (HSR, RFE, NULL, gensym, hole, fill, hunk). New: **W** — world density of a unit: the fraction of the gold diff's touched symbols that exist in the parent graph with their callers resolved at the semantic tier. **A0 / A1 / A2** — anchoring tiers of the task text (§2.2). **WP-n** — a work package (§3), the unit the orchestrator assigns.

---

## 0. How to run this document (for the orchestrator agent)

You are the lead. You do not do the work packages; you assign them, check their exits, and keep your own context small. Rules:

- **Read only this document and each package's `report.md`.** Do not load M0 v2, the probe record, Atlas-0, or source files into your context; those are inputs to specific packages, named per package. If a package's report says a decision is needed, the decision comes from Max, through you, and is recorded in §10.
- **One package, one sub-agent, one fresh context.** Give the sub-agent the package block verbatim (its Reads, Does, Writes, Exit, Report) and nothing else. A sub-agent that needs another package's output reads that package's Writes paths, not its transcript.
- **Exits are artifacts, not prose.** A package is done when its Writes exist at the stated paths and its `report.md` states the exit numbers. You check the numbers against the exit; you do not re-derive them.
- **Reports are capped at 40 lines**, in the M0 style: errors and results against the design first, then the exit numbers, then anything the next package needs. Attribution per row before any aggregate.
- **The spend gate.** WP-5 and WP-6 call the endpoint. Neither starts without Max's word with the ceiling stated (§9). You ask once, with the estimate from WP-4 in hand; you do not start on an assumed yes.
- **Order and parallelism are §3's DAG.** Packages with no unmet dependency may run in parallel in separate contexts.
- **Never patch a package's numbers from memory.** A defect found downstream reopens the package that owns it (its id is on every row) and the report is amended, dated.

## 0a. Orchestrator's pins (2026-09-11)

Facts resolved by the orchestrator before WP-0, so no package re-derives them. Every package reads this section with its own block.

- **M0 v2** is [`docs/calvin/calvin-potential.md`](calvin-potential.md) (its header: "Supersedes: v1"); no file named `calvin-m0-socket-v2.md` exists in the tree. The v1 text is `~/.hobbes/bench/calvin/calvin-m0-socket-v1.md`; the probe record is [`cells/calvin-m0-probe-2026-09-03.md`](cells/calvin-m0-probe-2026-09-03.md); M0's artifacts are under `~/.hobbes/bench/calvin/`.
- **gitleaks:** upstream clone `~/.hobbes/bench/comparative/repos/gitleaks`, full history (1,285 commits, not shallow), HEAD `8ad8470035d31a209322c580153b45c18e21b980` — the Hobbes cell's SHA, **the upper bound of §2.1's range**. That clone backs the oracle and comparative cells: **read-only — never check out, reset or write in it.** A package that needs a working tree clones from it into its own `~/.hobbes/bench/calvin-go/<wp-id>/` directory.
- **The cell:** [`docs/oracle/cells/gitleaks-notests-hobbes-2026-09-09.md`](../oracle/cells/gitleaks-notests-hobbes-2026-09-09.md) — precision 100.0% (2,010/2,010), recall 98.0% (2,069/2,111) at 2 roots, unchanged to the digit on 0.1.10-beta; the with-tests cell beside it reads 94.9% at 9 roots. Key `~/.hobbes/bench/comparative/keys/gitleaks-notests/oracle.json`. The misses are function values, closures and interface dispatch (static→named 100%).
- **W's denominator** (the orchestrator's reading, confirmed by Max 2026-09-11): the parent's symbols the gold touches. Symbols the gold *creates* do not exist in the parent graph; they are counted per unit as declare-holes (§2.5), not in W's denominator, so a new-file unit is not low-W by construction. WP-0 states its operational rule for "callers resolved at the semantic tier" in its report.
- **Code changes** (WP-1 and WP-3 by their blocks; WP-0 or WP-2 only if they must) go on a branch `calvin-go/wp-N`, tests in the same commit; the orchestrator merges to `main` after checking the exit. Never `git push`. A package in its own git worktree finds gitignored build outputs absent (`go/bin/*`, `sandbox/hobbes-proxy`, `*/node_modules`, `pipeline/.venv`): build them there or use the main checkout's `/home/mmarrujo/hobbes_public` read-only; never modify the main checkout from a worktree.
- **Running Hobbes:** `uv run --project <checkout>/pipeline hobbes … --repo <target>`; never `cd` into a target and `uv run` there. Lane B needs the image `hobbes-session:local` (built at 0.1.10-beta). Kill processes by PID, never `pkill -f`. Long runs detached, logged to a file.
- **WP-0 to WP-4 spend nothing:** no endpoint call, no Modal.

---

## 1. Why this round, stated from the record

**M0 on this repo (Python):** the grounder and harness are clean; the residual is anchoring. 28 of 28 gold diffs ground with 0 NULL and HSR 0, the poison control is exact, the verifier reads P2F 0 on every gold; the four-key run had T > O on the one key both solved and T honest where its anchors failed. Before any orchestrator round, 89–91% of hunks sit in files no anchor reached (H-a). So the socket has been measured on a world that is both holey and unanchored, and those two confound each other.

**Atlas-0:** typing and existence have to be given, not learned, at this scale. B2's address channel makes the class representable but refuses low training count, not absence; written absences bind to the token and relation they were written about; typed attention collapses at every λ that learns. One line: the world — existence, relations, the complement — comes from outside the block. That is Hobbes by construction; Calvin grounds within a given world. Nothing in Atlas-0 argues for training a Calvin before the socket carries weight on a dense world. Track B (density on every grounded identifier) stands unrun and costs one lookup.

**Positioning:** Hobbes is honest, accurate, deterministic; not fast, not cheaply adaptable. Five languages is the set; C next.

**Decision.** Prove the socket on the densest world Hobbes makes, with the anchoring confound removed on purpose, before fanning out. Go, on gitleaks. Not Rust (macros, traits → blind spots; recall ~81%). Not Python (H-a stays confounded with capture).

**What the round is.** The easiest floor. Two things fixed deliberately: a dense world (Go, W ≈ 1) and anchored tasks (§2.2). If T does not beat O here, the socket idea has no floor and the doc says so. If it does, the ceiling is measured by removing the fixings one at a time (§7).

**Model.** Haiku 4.5 in every arm, held constant with date. A weaker filler is acceptable for a floor round because the socket, not the filler, is under measurement, and both arms share it. Two consequences are registered now: O's solve rate will be lower than Sonnet 5's four-key row and is not comparable to it; and fill quality in T may add a class of NULLs (malformed / invented) that §4.3 attributes to O, not to the socket. Whether the endpoint honors `temperature` for this model is read at WP-5 and recorded.

---

## 2. Changes from M0 v2

### 2.1 Repo and units — gitleaks, history hunks at the parent

Pinned SHA range (the cell's SHA as upper bound). Units derived from history as the NLL units were — commit at parent, gold diff = the commit — with `plan` deriving units from commit message + touched files. **20 keys.** Exclude vendored/generated code, docs-only, dependency bumps, commits touching > 8 files. Shapes, stratified and reported per shape: **single-file**; **multi-file** (≥ 2 non-test files); **new symbol in an existing file**; **new file** (kept and bucketed — it is the declare-hole class of §2.5). W per unit on every row.

### 2.2 Anchored task text — the floor fixing

| tier | task text | what it fixes |
|---|---|---|
| **A2** | commit message + the gold's touched symbols, fenced, at symbol grain (definitions only) | H-a entirely |
| **A1** | commit message + the gold's touched files as paths | H-a at file grain; symbol choice is the orchestrator's |
| **A0** | commit message only | nothing; M0's condition |

This round runs at **A2**. A1/A0 are §7 step 1 on the same keys. A2 is a fixing, not a product; the write-up's first line says so.

### 2.3 Harness — Go verifier

`hobbes verify` runs `go test -run '^TestName$' ./pkg/...` at symbol grain from the testmap, package grain outside every span, the whole package for a touched test file; `go build ./...` and `go vet` in the baseline as build rows (a diff that does not compile is its own class, not a test failure). Outcome classes as M0; *uncollected* = an id the testmap names that `go test -list` does not return. Environment: the Go module cache lane B's fetches filled, mounted read-only (C-92). **Exit:** every gold applies, builds, verifies pass except environment failures listed by id; P2F 0; every record `all_contained`.

### 2.4 Grounder — Go call sites, density field (Track B)

Call sites from lane A's Go provider in the edited ranges; abstention classes as M0 (Go's predeclared identifiers pinned as the builtin list). Two Go rules to settle on the gold run and record: a method call on a typed receiver whose type is in the graph resolves; an interface method call resolves to the interface method, with RTA-known implementers recorded, not bound. **Density field:** every grounded identifier carries `dense | sparse | absent` from the parent graph (k so the top third of real symbols are dense), beside the NULL class. **Exit** as M0 step 3, plus the poison control (25 near-miss, 25 invented → one NULL each, right class).

### 2.5 Declare-before-use — one paragraph, no new code

References consume the world; declarations extend it. A NEW_SYMBOL fill, once placed, is an address for every later hole in the same diff (gensym binding already does this; confirm ordering across files). A bug fix has zero declare-holes; a new feature has many; a new project's world is the pinned dependency graph plus stdlib. No greenfield mode. Instrument: §4.10.

### 2.6 Arms

T, T-loop, O as M0 §3.2 (O: manifest, exec and file tools, knowledge tools withheld; 30-turn cap; `--token-budget` 1M). **Two runs per key in T** (run-to-run spread, Atlas-0 §6.6 as amended); O once per key on the subset.

---

## 3. Work packages — the DAG

Dependencies: **WP-0 → {WP-1, WP-2, WP-3} in parallel → WP-4 (spend gate) → WP-5 → WP-6.** Every package writes under `~/.hobbes/bench/calvin-go/<wp-id>/` and a `report.md` there. Every row carries the package id that produced it.

### WP-0 — units, parents, W (no spend)

- **Reads:** this document §2.1–2.2; `pipeline/scripts/calvin_probe.py` (the ingest and unit-derivation entry points only); the gitleaks checkout at the pinned range.
- **Does:** derive 20 keys per §2.1, stratified by shape; construct A0/A1/A2 task text per key; ingest each distinct parent (lane B, contained, cached by SHA); compute W per unit from the semantic graph.
- **Writes:** `units.jsonl` (key, parent_sha, gold diff path, shape, A0/A1/A2 text, W); `ingests.json` (count, wall-clock, median).
- **Exit:** 20 keys; every parent ingested; W distribution stated (expected ≈ 1; any unit < 0.9 flagged, kept).
- **Report:** shape counts; W min/median; ingest time; any key excluded and why.

### WP-1 — Go harness calibration (no spend) — depends on WP-0

- **Reads:** §2.3; `pipeline/src/hobbes/derive/harness.py` and its tests; `calvin.box.policy`; `units.jsonl`.
- **Does:** add Go verification per §2.3; run every gold diff through verify at its parent, with and without the diff.
- **Writes:** `verify-gold/` (one record per key); harness diff as a branch, tests added.
- **Exit:** all gold apply, build, pass except environment failures listed by id; P2F 0; `all_contained` everywhere.
- **Report:** verdict counts; environment failures by id; harness defects found and fixed (numbered, M0 style); wall-clock.

### WP-2 — templates at A2 and A1 (no spend) — depends on WP-0

- **Reads:** §2.2; `pipeline/src/hobbes/derive/template.py` and `holes.py`; `units.jsonl`.
- **Does:** generate templates v1 at A2 and A1 for every key, twice (byte-identity); compute coverage buckets (symbol / region / new file / outside) and anchor P/R per matcher against gold, per tier.
- **Writes:** `templates-a2/`, `templates-a1/`; `coverage.json`; `anchors.json`.
- **Exit:** 20 of 20 byte-identical per tier; the *outside all* bucket inspected and every Go span-rule gap listed (candidates: methods on a type declared in another file, `init()`, `var (...)` / `const (...)` blocks, interface satisfaction with no call edge, `_test.go` helpers).
- **Report:** coverage per tier and shape; anchor P/R per matcher; holes per template (max, median) — the cost estimate WP-4 uses; span gaps, each with a proposed rule, none implemented.

### WP-3 — grounder gold run on Go + density field (no spend) — depends on WP-0

- **Reads:** §2.4; `pipeline/src/hobbes/derive/ground.py` and tests; `units.jsonl`; lane A's Go provider.
- **Does:** pin Go's builtin list; implement the two Go rules; add the density field; run every gold diff as fills at its parent; run the poison control.
- **Writes:** `ground-gold/` (per key: diff, references by class, NULL list, density counts, output hash); `poison.json`; grounder diff as a branch, tests added.
- **Exit:** 0 NULL, HSR 0, post-images byte-equal to the commit, identical on rerun; poison 50/50 right class. A NULL on gold is a defect: fix, renumber, rerun.
- **Report:** reference counts by class; density distribution over gold identifiers; the two rules as settled; defects fixed.

### WP-4 — estimate and gate (no spend) — depends on WP-1, WP-2, WP-3

- **Reads:** the three reports; §9.
- **Does:** compute the per-key token estimate from WP-2's hole counts at Haiku 4.5 list; write the ceiling request.
- **Writes:** `estimate.md` (per key, per arm; total; ceiling).
- **Exit:** the orchestrator presents `estimate.md` to Max and waits. Nothing below starts without the word.

### WP-5 — five units through T by hand (spend) — depends on WP-4's word

- **Reads:** §2.6; `pipeline/src/hobbes/derive/adapter.py`; the five keys named by the orchestrator (one per shape plus one multi-file); their A2 templates.
- **Does:** run T on the five, every exchange recorded, fills validated; read whether `temperature` is honored; read cost per key against the estimate.
- **Writes:** `t-hand/` (per key: exchanges, fills, grounded diff, NULL list with class and density, verify record); `cost-actual.md`.
- **Exit:** five rows with attribution; actual cost per key stated beside the estimate; temperature behaviour recorded.
- **Report:** the five rows; cost delta; any protocol defect (malformed fills, truncation repairs) and whether it is O (Haiku) or the adapter. **If actuals exceed the estimate by > 2×, stop and return to the orchestrator; WP-6 is re-gated.**

### WP-6 — the run (spend) — depends on WP-5

- **Reads:** §2.6, §4, §5; the WP-5 report; `units.jsonl`; templates at A2.
- **Does:** T and T-loop on 20 keys × 2 runs; O on a paired subset of 5 keys (stratified by shape); rows with attribution before any aggregate; the §4 instruments; the §5 readings, each matched to a row.
- **Writes:** `rows.json`; `calvin/cells/calvin-m0-go-<date>.md` (the per-task page, M0 §5's row format plus W, density, declare-holes); this document's §10 filled.
- **Exit:** every row attributed; §5's reading selected in writing; the §7 decision written; spend total against the ceiling.
- **Report:** the aggregate table (T, T-loop, O), the selected reading, the §7 next step, spend.

### After WP-6 — the floor re-tested (added 2026-09-11 on Max's word; §10)

WP-6 read *T < O* with X and G clean and selected "NULL new dominates → M1′ as protocol first". Its §7 step: no fan-out; three no-spend changes, then T re-run on the same keys. DAG: **WP-6 merged → {WP-7a, WP-7b} in parallel → merged → WP-8.** The rules of §0 and the pins of §0a apply unchanged.

#### WP-7a — the declaration hole and the gutter guard (no spend) — depends on WP-6

- **Reads:** §2.5; §10 Results; WP-6's report (D-a, D-b); `pipeline/src/hobbes/derive/adapter.py`, `holes.py`, `ground.py` and their tests; `calvin_probe.py t-units`; WP-6's recorded exchanges and NULL rows under `~/.hobbes/bench/calvin-go/wp-6/`.
- **Does:** (1) **The declaration hole (M1′ as protocol; adapter protocol v0.4).** When grounding raises a NULL for a name that is *new* — written at a call site, declared nowhere in the parent graph or the diff — the loop no longer re-asks the call-site hole (D-b); it offers a NEW_SYMBOL declaration hole for that name (a file within the write partition, a region, a signature and a body). Once placed, the name binds as a gensym (§2.5), and the call site is grounded again. (2) **D-a.** The validator refuses a SIGNATURE or BODY fill that carries the render's line-number gutter, as a repairable error naming the hole.
- **Writes:** `~/.hobbes/bench/calvin-go/wp-7a/` (the replay records); the code on a branch `calvin-go/wp-7a`, tests in the same commit.
- **Exit:** No-spend replay. WP-6's 11 NULL sites are driven through the new loop step with scripted fills that give gold's declarations, and all 11 close with no model call. 7fc11's recorded gutter fill is refused. Everything else stays as it was: template v2, the grounder's gold run (0 NULL, byte-equal) and protocol v0.3's recorded replays, except where stated. pytest green.
- **Report:** the protocol change as built; the replay counts; defects, numbered.

#### WP-7b — the recall scan as a standing instrument (no spend) — depends on WP-6

- **Reads:** WP-6's report (D-d) and its recall working (`~/.hobbes/bench/calvin-go/wp-6/`, e.g. `memo.json`); `pipeline/scripts/calvin_probe.py`'s row pipeline.
- **Does:** Every row, T and O, gains a `recall` field: of the arm's novel added lines, meaning lines not present in the parent, the fraction that appear verbatim in the gold diff, and separately the fraction that appear in upstream history after the parent, up to the pinned SHA. Lines of a few characters or less and pure punctuation are excluded, and the rule is stated. Then re-score WP-5's and WP-6's rows with it.
- **Writes:** `~/.hobbes/bench/calvin-go/wp-7b/` (recall for every existing row); code on a branch `calvin-go/wp-7b`, tests in the same commit.
- **Exit:** every WP-5 and WP-6 row carries `recall`; WP-6's two recall rows reproduce (93acc ≈ 0.97, 2278 ≈ 0.48, or the difference explained); pytest green.
- **Report:** recall per arm and per shape; the threshold at which a row is marked `recalled`.

#### WP-8 — the floor re-tested (spend; cleared by Max 2026-09-11) — depends on WP-7a and WP-7b merged

- **Reads:** §2.6, §4, §5, §10; WP-6's and WP-7's reports; `units.jsonl`; the v2 A2 templates.
- **Does:** T, with the T-loop inside it, on the same 20 keys × 2 runs. Haiku 4.5 at model-default sampling, protocol v0.4. O's WP-6 rows stand and are not re-run. Rows are attributed before any aggregate; the §4 instruments run with recall on every row; §5's reading is re-selected beside WP-6's.
- **Writes:** `~/.hobbes/bench/calvin-go/wp-8/rows.json`; a re-test section in the cell page; §10 Results amended, dated.
- **Exit:** every row attributed; the re-selected reading written; spend stated. **Spend rules:** stop after run 1 if its cost exceeds 2× WP-6's per-run T actual (≈ $2.36, so stop above $4.72); a hard cap of **$20.88**, the ceiling's remainder.
- **Report:** T against WP-6's T and O's standing rows; the NULL closure count; recall; the reading; spend.

### After WP-8 — G on declarations, then one more re-test (added 2026-09-11 on Max's word; §10)

WP-8 read *T < O* again, with G unclean on what the declaration hole lets through: 9 NULLs closed at HSR 0 on bodies no build accepts, all declared in other projects' APIs (D-g), and the hole showed no sibling's form (D-h). DAG: **WP-9 → merged → WP-10.** WP-9 makes its own worktree from `main` (`git worktree add`), because the harness's isolation cuts worktrees from a stale commit.

#### WP-9 — the grounder on declaration bodies, a sibling's form, the placed record (no spend) — depends on WP-8

- **Reads:** WP-8's report (D-f, D-g, D-h); WP-7a's report; §2.5; `ground.py`, `adapter.py`, `holes.py` and their tests; WP-8's recorded exchanges and rows.
- **Does:** (1) **D-g.** The grounder judges a declaration's body in the world (§2.5). Every import path must be a stdlib package (go1.26.5's list, pinned), a package of the module, or a package of a module the parent's go.mod requires; anything else is a NULL of its own class. A selector or call through a package name the file does not import is judged, and an undeclared qualifier is a NULL. (2) **D-h.** The declaration hole shows one existing declaration of the same kind from the binding directory — its signature and body head, chosen deterministically and capped. (3) **The loop uses G.** A NULL inside a declaration's body routes back once, as a repair of that declaration hole, bounded to one exchange. (4) **D-f.** A refused declaration reads `refused`, never `placed`. The adapter stamps protocol **v0.5**.
- **Writes:** `~/.hobbes/bench/calvin-go/wp-9/` (the replay records); code on branch `calvin-go/wp-9`, tests in the same commit.
- **Exit:** No-spend replay. WP-8's 9 placed wrong-world declarations each raise at least one NULL of the right class (9/9). 0924's overlapping declaration reads `refused` (2/2). WP-7a's scripted gold declarations still close 11/11. The gold grounding reads 0 NULL, 20/20 byte-equal. Template v2 is byte-identical. The poison control reads 50/50. The sibling shown for each key is listed. pytest green.
- **Report:** the rules as built; the replay counts; defects; any constraint drafts.

#### WP-10 — the floor re-tested on protocol v0.5 (spend; cleared by Max 2026-09-11) — depends on WP-9 merged

- **Reads:** as WP-8, plus WP-8's and WP-9's reports.
- **Does:** as WP-8. T, with the T-loop inside it, on the same 20 keys × 2 runs. Haiku 4.5 at model-default sampling, protocol v0.5. O's WP-6 rows stand. Rows are attributed before any aggregate; the §4 instruments run with recall on every row; §5's reading is re-selected beside WP-6's and WP-8's.
- **Writes:** `~/.hobbes/bench/calvin-go/wp-10/rows.json`; a `## Re-test 2 (WP-10)` section in the cell page; §10 Results amended, dated.
- **Exit:** every row attributed; the reading written; spend stated. **Spend rules:** stop after run 1 if its cost exceeds 2× WP-8's run-1 actual ($2.66, so stop above $5.32); a hard cap of **$15.83**, the ceiling's remainder.
- **Report:** T against WP-8's T, WP-6's T and O's standing rows; declarations counted as placed, built, and NULLed by class; the repair exchange's closures; recall; the reading; spend.

---

## 4. Instruments, with attribution

M0 §4.1–4.8 as written, per unit and per shape; paired bootstrap over units on the 20 keys (5,000 resamples, seed 0); O rows reported paired with their T rows only. Additions:

### 4.3a NULL and act by density — O, G, U (Track B)

| result shape | implicates | check | residual |
|---|---|---|---|
| absent → invented, sibling-shaped; sparse-real → resolved | O has a referential channel Atlas-0's blocks lack | is "sparse" sparse in the graph or only in the template | Calvin narrows to placement |
| absent → invented; sparse-real → invented or skipped | O measures density, calls it existence | did the template name the sparse symbol (else H-s) | Atlas-0's B1 row on a frontier-family model; grounding earns its place on both classes |
| sparse-real → routed around | O | count against the write partition | NULL must become blocking (C-7 revisited) |
| dense anything but resolved | G or H-s | template correctness | not a residual |

### 4.9 T outcome against W

| result shape | implicates | check | residual |
|---|---|---|---|
| W ≈ 1 everywhere; T varies by shape | O or H-s | split by shape | the world is not the variable; the socket is being measured |
| T failures concentrate on low-W units | W | what the graph lacked | the Go move was right; the Python residual was capture |
| T fails at W ≈ 1 on single-file units | G on Go, then H-s | the §2.4 rules; WP-2's span gaps | Go-specific gap; fix, not residual |

### 4.10 Declare-holes and placement — U, O, G

| result shape | implicates | check | residual |
|---|---|---|---|
| new-symbol units place at gold's file and region | — | not trivial (one-file packages) | declare-before-use holds on Go; M1′ smaller than M0 read it |
| right file, wrong region | O | did the fill name a region | M1′, or a protocol change measured in T-loop |
| wrong file | H-s or O | in the write partition? | partition residual if outside; placement if inside |

---

## 5. Preregistered readings

- **T > O at A2 on multi-file, T honest where a fill fails to ground** → the floor exists; §7 step 1; no Calvin model.
- **T ≈ O at A2** → with a dense world and given anchors the socket adds nothing over the manifest. Check U (trivial units) and H-s (holes ≫ hunks). If both are clean, the value of the socket is not where the charter placed it — the most important outcome this round can produce; written as such.
- **T < O** → X first (build rows, Go verifier, environment binding), then G on Go. Not a reading about the idea until X and G are clean.
- **NULL new dominates** → M1′ before M1; §4.10 says whether it is a protocol change first.
- **NULL invented/malformed dominates and O's HSR is high too** → the filler (Haiku), attributed to O; the socket's honesty (T reports it, O ships it) is the reading, not the solve rate.
- **Track B:** O separates sparse from absent → Calvin narrows to placement. O conflates → Atlas-0 reproduced on a production model; the grounder's blocking NULL is the first measurable safety property.
- **Two T runs disagree on a key** → the row carries both; a reading that holds in one run only is not separable at two runs.

## 6. Constraints to open on acceptance

- Go only; gitleaks only.
- A2 is a fixing; every aggregate is at A2 unless labelled; the product condition is A0.
- One orchestrator model (Haiku 4.5), one endpoint shape; two runs per key in T; O once, 5 keys. Results are not comparable to the Sonnet 5 four-key row.
- NULL is advisory (M0 C-7); blocking is recorded after §4.3a.
- The Go key is the compiler; W is from Hobbes' own oracle lane on gitleaks and moves if that cell moves.
- Interface dispatch recorded, not bound.
- No security layer (§8).

## 7. Fan-out, in order — only if the floor holds

1. **Anchors removed, same keys, same world:** A1, then A0. H-a on a dense world, nothing else moving.
2. **World thinned, same protocol:** fzf (≈ 40% recall at roots), dagger (OOM stress). T against W — the first look at Calvin at the complement.
3. **Language:** this repo's 28 Python keys under the Go-round protocol at A2; then Rust.
4. **Calvin model items** (M1′, M1) after 1–2, as §5's NULL readings direct.
5. **C and its variants as a Hobbes lane first** (scip-clang pinned; `compile_commands.json` generator pinned; executed key via `-finstrument-functions` / uftrace at -O0; static key = LLVM call graph, direct calls only).

## 8. Deferred — noted, not built this round

| item | one line | why deferred |
|---|---|---|
| Derived effect manifest | per task: files writable, commands runnable, network (normally none) — derived from the graph, never authored | would constrain O and the box before potential is seen |
| Sink reachability, unknown = deny | a fill reaching `os/exec`, `net`, `syscall`, `unsafe`, `plugin`, `reflect` outside the manifest → deny; a path through a blind spot → unknown → deny, stated | needs the manifest; Go's short sink list makes it the right first language when it comes |
| Harness-written ledger | append-only, hash-chained, written outside the sandbox from the grounder's resolved actions | the Ledger Machine is its own program |
| Seeded policy oracle | forbidden-action classes seeded into tasks; catch rate and false-confidence rate per class | the thing to grade does not exist yet |
| Isolation boundary | rootless Podman is not a boundary against a capable adversary | infrastructure, not Hobbes |
| NULL blocking at policy | after §4.3a's routing-around read | measurement first |

The one rule not to preclude meanwhile: §2.5, and the grounder's tier stamp on every output.

## 9. Cost

- **Ingest:** ≤ 20 parents at ~25 s; under 10 min; no spend.
- **Orchestrator, Haiku 4.5 at list.** M0's arm T on Sonnet 5 read 1.51M in / 98k out for four keys with the module door open; at A2 no module anchor opens and gitleaks templates are expected smaller. WP-4 computes the number from WP-2's hole counts; the standing estimate for gating is T + T-loop, 20 keys × 2 runs: **$8–15**; O, 5 keys under the 30-turn / 1M-token cap: **$5–10**.
- **Ceiling to state at WP-4: $30.** WP-5 re-reads it on five keys; WP-6 stops at the ceiling and reports the keys it reached. If WP-5's actuals put WP-6 over $30, the orchestrator drops O to 3 keys before dropping T's second run, and asks again.
- **GPU:** none. Atlas-0's open items are not charged to this round.

## 10. Results

### Results

**WP-6, 2026-09-11.** Every number here is at A2, which is a fixing. The run:
- **T:** 20 keys × 2 runs.
- **T-loop:** inside T's runs.
- **O:** once on 5 keys.
- **Held constant:** Haiku 4.5 at model-default sampling, protocol v0.3, template v2.

The rows, every one attributed before any aggregate, are in [`cells/calvin-m0-go-2026-09-11.md`](cells/calvin-m0-go-2026-09-11.md). The machine rows are in `~/.hobbes/bench/calvin-go/wp-6/rows.json`.

**Aggregate.** Paired bootstrap over units, 5,000 resamples, seed 0. "Pass" means the change compiles, generates and breaks no guarding test; the gold's own test changes are not run.

| arm | n | pass [95% CI] | right-files Jaccard (J) [95% CI] | NULL | $ |
|---|---|---|---|---|---|
| T (mean of 2 runs) | 20 | 0.225 [0.05, 0.40] | 0.394 [0.245, 0.55] | 11 | 4.46 |
| T-loop | 20 | 0.225 [0.05, 0.40] | 0.394 [0.245, 0.55] | 11 (loop closed 0) | +0.22 |
| O | 5 | 0.80 [0.40, 1.00] | 0.45 [0.288, 0.612] | 0 | 3.28 |

**Paired differences:**
- **O − T, on O's 5 keys:** pass +0.50 [0.10, 0.90]; J +0.215 [0.034, 0.415].
- **O − T, the two recall rows removed (n = 3):** pass +0.17 [0.00, 0.50]. Not separable.
- **T-loop − T:** 0 [0, 0].
- **Run 2 − run 1:** −0.05 [−0.15, 0.00]. The two runs disagree by verdict on 5 keys.

**By shape, T pass per run:**

| shape | run 1 | run 2 |
|---|---|---|
| single-file | 3 of 5 | 3 of 5 |
| multi-file | 2 of 5 | 1 of 5 |
| new-symbol | 0 of 5 | 0 of 5 |
| new-file | 0 of 5 | 0 of 5 |

**The reading selected (§5): *T < O*.** X and G were checked first, and both are clean:
- **X:** WP-1's golds read P2F 0, and every build-fail is the candidate's own compile error.
- **G:** 11 of 11 NULLs are raised at the right site, and 0 references are mis-bound.

So the result reads as ***NULL new dominates → M1′ before M1, protocol first (§4.10)***:
- **The NULLs:** all 11 of T's NULLs are new names the orchestrator wrote at the call site and never declared. The loop closed none of them.
- **Why the loop could not help:** A2 rev 3 names no new term or path. Round 2 therefore offers no NEW_SYMBOL hole, and the loop re-asks the call-site hole instead.

**O's lead is partly recall.** On `93acc6e82adb` and `2278a2a97e42`, O reproduced the gold's new files verbatim from memory: 0.97 and 0.48 of the novel lines. **"T ≈ O" cannot be excluded** on the three recall-free keys.

**Track B:** *O separates sparse from absent*. T resolved 1,940 sparse-real references with 0 sparse NULLs; its 11 absent references are sibling-shaped names for things it meant to create. So Calvin narrows to placement.

**Instruments:**
- **§4.3a (density):** absent → invented, sibling-shaped; sparse-real → resolved. Two unit-runs routed the new PKCS12 rule into the existing `PrivateKey` rule.
- **§4.9 (T against W):** W = 1.0 on every unit, and T varies by shape. The world is not the variable; declaration is.
- **§4.10 (declare-holes):** T declared something on only 3 of 22 declare-unit runs (af7d ×2 right file, right region, wrong form; 2278 run 1 a stub). O placed 2 new files, both recalled, and routed 1 into an existing rule.

**§7 decision.** The floor did not hold, so the fan-out does not start. The next step is to re-test the floor with T only, on the same 20 keys at A2, with O's rows standing. Three no-spend changes come first:
1. A declaration hole in the NULL round-trip (§2.5, M1′ as protocol).
2. A validator guard against a body carrying the render's line-number gutter (D-a).
3. The recall scan as a standing instrument.

Re-running T twice costs about $4.7. The decision is Max's.

**Spend.**

| | $ |
|---|---|
| T | 4.4559 |
| T-loop | 0.2209 |
| O | 3.2775 |
| **WP-6** | **7.9543** |

- **WP-6 against its limit:** $7.95 of $28.83.
- **The round:** $9.12 of the $30 ceiling.
- **Checkpoint:** T run 1 cost $2.36 against the $9.79 line, so it was not triggered.
- **§9 drop order:** not triggered.

**Defects.**
- **D-a:** a body fill carrying the render's line-number gutter passes the validator. Triggered by O; the guard is missing in the adapter. Seen on `7fc11bb264e9`, 2 of 2 runs.
- **D-b:** the loop cannot close an unplaced new name (protocol, H-s).
- **D-c:** M0's "HSR zero by construction" does not hold under advisory NULL (instrument).
- **D-d:** contamination (U/O).
- **D-e:** the O driver for M0-Go units, `o-units`, on branch `calvin-go/wp-6`.

**WP-8, 2026-09-11 — the floor re-tested.** Every number is at A2, a fixing. The run:
- **T:** 20 keys × 2 runs, with T-loop inside them.
- **Held constant:** Haiku 4.5 at model-default sampling, template v2.
- **Changed:** **protocol v0.4**, the declaration hole and the gutter guard (WP-7a), with **recall on every row** (WP-7b).
- **O:** WP-6's rows stand; O was not re-run.

Every row was attributed before any aggregate. The rows are in the re-test section of [`cells/calvin-m0-go-2026-09-11.md`](cells/calvin-m0-go-2026-09-11.md), and the machine rows in `~/.hobbes/bench/calvin-go/wp-8/rows.json`. Every exchange, record and row is stamped 0.4.

| arm | n | pass [95% CI] | J [95% CI] | NULL | $ |
|---|---|---|---|---|---|
| WP-8 T (mean of 2 runs) | 20 | 0.25 [0.075, 0.425] | 0.427 [0.265, 0.592] | 11 | 5.0214 |
| WP-8 T-loop | 20 | 0.25 [0.075, 0.425] | 0.506 [0.315, 0.693] | 2 (loop closed 9 of 11) | +0.0257 |
| WP-6 T | 20 | 0.225 [0.05, 0.40] | 0.394 [0.245, 0.55] | 11 (closed 0) | 4.6768 |
| O (WP-6, standing) | 5 | 0.80 [0.40, 1.00] | 0.45 [0.288, 0.612] | 0 | 3.2775 |

- **Paired differences:**
  - WP-8 T-loop − WP-6 T: pass +0.025 [0.00, 0.075].
  - O − WP-8 T-loop on O's 5 keys: pass +0.40 [0.10, 0.70]; J +0.315 [0.134, 0.481].
  - O − WP-8 T-loop on the 3 recall-free keys: pass +0.17 [0.00, 0.50].
  - Run 2 − run 1: +0.10 [0.00, 0.25]. The two runs disagree by verdict on 4 keys.
- **The declaration hole:** 11 offered on 9 loop firings, 11 answered, 9 placed (0924's second whole-file answer was refused as overlapping). **9 of 11 NULLs closed**, and all 9 placed declarations sit outside the partition (C-107). **0 of 9 built.** Every placed body is written against another project's API: trufflehog's `pkg/detectors` on 3 keys, gosec on 1, an unimported `core` on 1. None uses gitleaks' form, `func X() *config.Rule`.
- **Recall:** T 0 of 40 rows recalled (upstream share 0.24 of 112 novel lines); T-loop 0 of 40 (0.18 of 156); O 2 of 5.

**The reading re-selected (§5): *T < O*, unchanged, and not separable on the recall-free keys. The floor does not hold.**
- **X:** clean.
- **G:** clean on what it binds (11 of 11 NULLs at the right site, 0 mis-bound), and not on what the hole now lets through. A declaration's imports are never read against go.mod and its unimported qualifiers abstain, so 9 NULLs close at HSR 0 on bodies no build accepts. By §5, that is not yet a reading about the idea.
- ***NULL new* no longer dominates; *declared in the wrong world* does.** It implicates O (the form), H-s (the hole gives no sibling's form) and G (the body is not held to §2.5's world).

**Instruments:**
- **§4.3a (density):** row 1 holds again: absent → invented, sibling-shaped; 2,352 sparse-real references resolved, 0 sparse NULL.
- **§4.9 (T against W):** W = 1.0, and T varies by shape (single-file 0.6, new-symbol 0).
- **§4.10 (declare-holes):** T declared something on 11 of 22 declare-unit runs (WP-6: 3). Right file (new) 7, wrong file 2, right file wrong region 1.

**Spend:** run 1 $2.6579 (the $4.72 stop was not reached), run 2 $2.3890. **WP-8 $5.0469 of $20.88; the round $14.17 of $30.**

**Defects:**
- **D-f** (adapter, instrument): a refused declaration is recorded "placed".
- **D-g** (G, coverage): a declaration's imports and qualifiers go unchecked.
- **D-h** (protocol, H-s): the declaration hole shows no sibling's form.

The next step is Max's.

**Decisions and gate record** (Max, through the orchestrator; dated):

- 2026-09-11 — Max cleared the round to proceed: WP-0 to WP-4 (no spend) now; the spend gate at WP-4 stands as written.
- 2026-09-11 — Max confirmed §0a's reading of W's denominator (parent symbols the gold touches; created symbols are declare-holes, outside W) and the §0a pins as an addition to §0's "block verbatim" rule.
- 2026-09-11 — on WP-2's report, two decisions (Max). **F1, the callee door** (`cmd/generate/config/main.main` fans out to 179–226 rule constructors; 35.2M chars at A2 against 1.25M without callee expansion): the template takes an **out-degree cap** — above k, an anchored symbol's callees render as signatures only, bodies opening by confirmation (M0 v1's module-anchor pattern); below k, as before. WP-2 reopens to implement it with tests and states k from the gitleaks distribution. **F2, A2's wording**: WP-0 had backticked symbol-less files (README.md, .gitleaksignore) into A2, which §2.2 does not name and which fed the literal matcher; **WP-0 reopens and A2 names touched symbols only**, rows stamped `a2_rev: 2`; WP-2 regenerates on the amended units.
- 2026-09-11 — on WP-0's F2 amendment (Max): **A2 drops the `path (new file)` lines too** (7 across the 5 new-file keys) — a new file has no parent symbol, and naming it hands O the placement §4.10 measures. A2 is the commit message plus touched parent symbols, no paths; rows stamped `a2_rev: 3`; WP-2 regenerates on rev 3.
- 2026-09-11 — on WP-1's report (Max): `calvin.box.policy` allows `go generate*` (it had parked, then denied; `make config/gitleaks.toml` already reached the same code through `make*`, so the rule widens nothing). In the WP-1 merge.
- 2026-09-11 — exits checked and merged to `main`: WP-3 (`3b015a6`; C-102 registered, C-91 amended), WP-1 (`57b3eb3`; C-103 registered, ADR-100 amended, the policy rule); pytest 1,269. The patch bump (ADR-103) is held for one commit once WP-2's template change lands.
- 2026-09-11 — WP-2's amended exit checked (template v2, the out-degree cap at k = 20; 20/20 byte-identical per tier; A2 round 2 35.2M → 3.22M chars plus 1.17M in round-1 confirmations; strict coverage 86/6/6/5) and merged (`88c3f53`; C-104 registered). **0.1.11-beta** (`a94e2bd`, untagged; CHANGELOG names the grounder, the Go verifier and the policy rule, template v2, C-102–C-104); image rebuilt, its proxy answers 0.1.11-beta; pytest 1,273.
- 2026-09-11 — **the spend gate (Max): cleared, $30 ceiling, WP-5 then WP-6 as designed.** WP-4's estimate (`~/.hobbes/bench/calvin-go/wp-4/estimate.md`; Haiku 4.5 at $1 / $5 per MTok, chars/token 2.08 and 76 output tokens per asked hole measured on M0's run): expected $17.44 (T $9.79, T-loop $0.37, O $5.33, WP-5 $1.95), band $7.74–$40.39; the high band's risk is Haiku confirming the registry keys' callees (gold: 0 of 1,574). WP-5 keys `a971a324fab5` `ed205a5f63e3` `6411402d434d` `2278a2a97e42` `d29ee5517128`; O's five add `93acc6e82adb` (drop to `ed205a5` `6411402` `2278a2a` at three). WP-5 > 2× its estimate re-gates WP-6.
- 2026-09-11 — WP-5's exit checked: five rows attributed, $1.17 actual against $1.95 estimated (0.60×; WP-6 not re-gated), G clean on all five (0 NULL, HSR 0), Haiku confirmed 0 of 412 capped callees; temperature honoured (identical at 0, different at 1). Two decisions (Max) before WP-6. **Protocol v0.3:** a `patterns` reply on SIGNATURE / BODY / ANCHOR_CONFIRM is read as unchanged / no for the holes it covers (Haiku sent it on 4 of 5 keys; its repairs were 36% of WP-5's spend), with the validator fixed so a refused pattern's holes are no longer counted as answered; WP-5 reopens to implement it. **Sampling:** both of WP-6's T runs at the model default (M0's condition), so §2.6's run-to-run spread is measurable; WP-5's temperature-0 rows stay as their own reading.
- 2026-09-11 — WP-5's v0.3 amendment checked (replay: 4 of the 5 refused-pattern exchanges validate first pass, 4 repair calls saved; model-default sampling passes no temperature) and merged (`17f0ffd`; C-105 registered — an answered hole no longer means the model considered it one at a time, surfaced as `by_pattern`). **0.1.12-beta** (`92c9f7a`, untagged); image rebuilt, proxy 0.1.12-beta; pytest 1,286. WP-6 launched: T run 1 on 20 keys, a cost check, O on five, T run 2; $28.83 of the ceiling left.
- 2026-09-11 — WP-6's exit checked (every row attributed; §5 reading *T < O*, resolved into NULL new → M1′ as protocol; §7 no fan-out; $7.95, round $9.12 of $30) and its docs committed (`06dde54`). **Max: build the three changes, then re-test** — WP-7a (the declaration hole, protocol v0.4, and the gutter guard), WP-7b (the recall scan), then WP-8 (T twice on the 20 keys, ~$4.7, under the $30 ceiling's $20.88 remainder); blocks in §3 "After WP-6".
- 2026-09-11 — **WP-7b** exit checked (every WP-5/WP-6 row carries `recall`; WP-6's measure reproduces 45/45; recall v1 marks 2 of O's 5 rows recalled, 0 of T's 40) and merged (`8244194`; scripts only, no bump). The harness cut both WP-7 worktrees from the session's first commit (`9f168d6`), not `main`; WP-7b re-cut from `main` itself and WP-7a was warned and confirmed its base (`e91d50e`).
- 2026-09-11 — **WP-7a** exit checked (protocol v0.4: WP-6's 11 NULL sites close 11/11 on a scripted gold replay with 0 NULLs opened and 0 call sites re-asked; the gutter guard refuses 7fc11's three gutter fills; template v2 and the gold grounding unchanged; pytest 1,296). Its "WP-3 hashes differ" note is not a defect: the base run grounded without the RTA key and on A2 rev 3, so `task_hash` and the output hash moved with their inputs, reference counts equal. **Max: a declaration in a new file outside the write partition is placed and recorded (`in_partition: false`), never refused** — as NEW_SYMBOL/FREEFORM files already are; refusing would leave 10 of the 11 sites (gold's new `rules/*.go` files) unclosable.
- 2026-09-11 — WP-7a merged (`edd075e`; C-106 near-miss names re-asked, C-107 outside-partition declarations placed and recorded, C-108 the declaration's directory unchecked for non-Go names — partial); **0.1.13-beta** (`5682263`, untagged); image rebuilt, proxy 0.1.13-beta; pytest 1,301. WP-8 launched on protocol v0.4 with the $20.88 cap.
- 2026-09-11 — WP-8's exit checked (every row attributed; *T < O* re-selected, not separable on the recall-free keys; the declaration hole closed 9 of 11 NULLs, 0 of 9 build — declared in trufflehog's / gosec's APIs; G unclean on declaration bodies, D-g; $5.05, round $14.17 of $30) and its docs committed (`cea00bb`). **Max: fix G and D-h, re-test once** — WP-9 (G on declaration bodies: imports against stdlib / module / go.mod, unimported qualifiers NULL; a sibling's form in the declaration hole; one bounded repair of a declaration's NULL; the D-f record; protocol v0.5), then WP-10 (T twice, cap $15.83); blocks in §3 "After WP-8".
- 2026-09-11 — WP-9's exit checked (0 model calls; base `cea00bb`, ancestor check passes). WP-8's 9 wrong-world declarations each raise a NULL at the grounder (trufflehog/gosec imports `import-outside`; `detectors`, `core` and others `unimported`); 0924's overlap reads `refused` 2/2. WP-7a's gold declarations still close 11/11. The gold grounding reads 0 NULL, 20/20 byte-equal. Template v2 is byte-identical; poison 50/50; pytest 1,307. Re-grounding all 80 earlier round-2 fills adds 0 NULLs outside the declaration hole. Siblings are all `rules/*.go` constructors (`func X() *config.Rule`). Grounder v2, protocol v0.5; handed to the merge with six constraint drafts and the 0.1.14-beta bump.
