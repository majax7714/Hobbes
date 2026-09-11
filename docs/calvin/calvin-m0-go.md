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

(empty until WP-6)

**Decisions and gate record** (Max, through the orchestrator; dated):

- 2026-09-11 — Max cleared the round to proceed: WP-0 to WP-4 (no spend) now; the spend gate at WP-4 stands as written.
- 2026-09-11 — Max confirmed §0a's reading of W's denominator (parent symbols the gold touches; created symbols are declare-holes, outside W) and the §0a pins as an addition to §0's "block verbatim" rule.
- 2026-09-11 — on WP-2's report, two decisions (Max). **F1, the callee door** (`cmd/generate/config/main.main` fans out to 179–226 rule constructors; 35.2M chars at A2 against 1.25M without callee expansion): the template takes an **out-degree cap** — above k, an anchored symbol's callees render as signatures only, bodies opening by confirmation (M0 v1's module-anchor pattern); below k, as before. WP-2 reopens to implement it with tests and states k from the gitleaks distribution. **F2, A2's wording**: WP-0 had backticked symbol-less files (README.md, .gitleaksignore) into A2, which §2.2 does not name and which fed the literal matcher; **WP-0 reopens and A2 names touched symbols only**, rows stamped `a2_rev: 2`; WP-2 regenerates on the amended units.
- 2026-09-11 — on WP-0's F2 amendment (Max): **A2 drops the `path (new file)` lines too** (7 across the 5 new-file keys) — a new file has no parent symbol, and naming it hands O the placement §4.10 measures. A2 is the commit message plus touched parent symbols, no paths; rows stamped `a2_rev: 3`; WP-2 regenerates on rev 3.
- 2026-09-11 — on WP-1's report (Max): `calvin.box.policy` allows `go generate*` (it had parked, then denied; `make config/gitleaks.toml` already reached the same code through `make*`, so the rule widens nothing). In the WP-1 merge.
- 2026-09-11 — exits checked and merged to `main`: WP-3 (`3b015a6`; C-102 registered, C-91 amended), WP-1 (`57b3eb3`; C-103 registered, ADR-100 amended, the policy rule); pytest 1,269. The patch bump (ADR-103) is held for one commit once WP-2's template change lands.
- 2026-09-11 — WP-2's amended exit checked (template v2, the out-degree cap at k = 20; 20/20 byte-identical per tier; A2 round 2 35.2M → 3.22M chars plus 1.17M in round-1 confirmations; strict coverage 86/6/6/5) and merged (`88c3f53`; C-104 registered). **0.1.11-beta** (`a94e2bd`, untagged; CHANGELOG names the grounder, the Go verifier and the policy rule, template v2, C-102–C-104); image rebuilt, its proxy answers 0.1.11-beta; pytest 1,273.
- 2026-09-11 — **the spend gate (Max): cleared, $30 ceiling, WP-5 then WP-6 as designed.** WP-4's estimate (`~/.hobbes/bench/calvin-go/wp-4/estimate.md`; Haiku 4.5 at $1 / $5 per MTok, chars/token 2.08 and 76 output tokens per asked hole measured on M0's run): expected $17.44 (T $9.79, T-loop $0.37, O $5.33, WP-5 $1.95), band $7.74–$40.39; the high band's risk is Haiku confirming the registry keys' callees (gold: 0 of 1,574). WP-5 keys `a971a324fab5` `ed205a5f63e3` `6411402d434d` `2278a2a97e42` `d29ee5517128`; O's five add `93acc6e82adb` (drop to `ed205a5` `6411402` `2278a2a` at three). WP-5 > 2× its estimate re-gates WP-6.
