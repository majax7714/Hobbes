# Calvin M0-Gate — the linker on the agent's diff

**Status:** handoff (2026-09-12), written for an orchestrator agent that assigns work packages to sub-agents; recorded in the tree 2026-09-11 with the orchestrator's pins (§0b); WP-17 and WP-18 launched · **Type:** pipeline experiment (preregistered readings, attribution-first) · **Compute:** orchestrator model `claude-haiku-4-5-20251001` via the OpenAI-compatible endpoint; exec local under Podman. No GPU. No Calvin model. No template arm.
**Depends on:** rounds 1 and 2 as run and closed ([`calvin-m0-go.md`](calvin-m0-go.md), [`calvin-m0-go-r2.md`](calvin-m0-go-r2.md)): the O drivers (`o-units` for Go; M0's Python O driver), grounder v3, `hobbes verify` at 0.1.17-beta (`vacuous`, `gold_tests`, D-p fixed), the cutoff pin (Haiku 4.5 training data Jul 2025; post-cutoff ≥ 2025-08-01), the recall scan, the ledger; the comparative and oracle cells; M0 v2's 28 Python keys.
**Amends:** the arm design of rounds 1–2. T-as-form is retired from measurement (round 2 §10: the filler declined to act on a body shown whole, budget to spare). The world stays; the agent moves.
**Not in scope:** the manifest-restricted arm (O+world: reads and writes bounded by the template's scope, the grounder as a tool during the session) — §7; the security layer beyond what the gate is — §8; a Calvin model; any new language.
**ADR:** none yet.

**Terms.** As rounds 1–2 (W, WP-n, HSR, NULL, vacuous, gold_tests, $/pass, readable key). New:
- **gate** — one deterministic pass of grounder v3 plus the partition and world checks over a finished diff at its parent, returning *clear* or *blocked* with a class list.
- **captured region / blind spot** — per unit, the lines of the write partition whose symbols and call sites lane B resolved at the semantic tier, and those it did not (uncaptured file, dynamic dispatch, lane B miss, oracle-known miss class).
- **invented / unknown** — a NULL whose site lies in a captured region is *invented*; in a blind spot it is *unknown*, and the gate reports the reason.
- **readable key** — a key whose gold diff reads pass under the round-2 metric (a guarding test executed, or `gold_tests` pass).

---

## 0. How to run this document (for the orchestrator agent)

Round 1 §0's seven rules and round 2 §0's two additions apply verbatim. One more:

- **O runs once per key and is never re-run for an arm.** Every arm in §2.3 is computed over the same recorded O session; the only extra model calls in the round are the bounded repair turns of §2.3's third arm, and only on rows the gate blocked. A package that finds itself re-running O has misread the design; stop and report.

## 0a. Pins that move (2026-09-12)

- **Substrate is chosen by WP-17, not by this document.** Priority: a Go repo from the cell set with ≥ 20 readable post-cutoff keys and W ≥ 0.9; else Hobbes' own repository (Python, `hobbes_public` at a pinned SHA, M0's 28 keys re-scored). Both are acceptable; the reading differs only in §4.15's weight (the complement channel is testable on a holey world, weakly on Go). WP-17 reports both counts and the orchestrator applies the priority; if neither reaches 20, Max sets N.
- **The cutoff filter applies to a Go repo;** Hobbes' own repo is post-cutoff by construction (its history begins after Jul 2025). The recall scan runs on every row regardless.
- **Round 1's and round 2's keys are retired** except gitleaks' 3 readable post-cutoff keys, which may be appended to a Go draw if the draw is short.
- **The gate is a Hobbes command** (`hobbes gate`), versioned with the patch series, not a probe script. It outlives the round.
- Everything else in round 1 §0a (the clones read-only, branches `calvin-go/wp-N` → now `calvin-gate/wp-N`, worktrees from `main`, running Hobbes, kill by PID, no spend unless the block says so) is unchanged.

## 0b. Orchestrator's pins (2026-09-11)

Facts resolved by the orchestrator before WP-17 and WP-18, so no package re-derives them. Every package reads this section, §0a, and round 1's §0a with its own block.

**Where the evidence is.**
- **Round 2's units** (the schema a unit row follows here): `~/.hobbes/bench/calvin-go/wp-13/units.jsonl` — `key, sha, parent_sha, shape, date, gold_diff, generated_diff, files, A0/A1/A2, W, W_nontest, W_num, W_den, W_flag, touched, declare_holes, removed_symbols, parent_graph, parent_built_by, parent_all_contained, parent_tests, parent_tail…`; gold diffs `wp-13/gold/`, parent graphs `wp-13/graphs/`, templates `wp-16/` (rebuilt with live co-change, D-q). **gitleaks' 3 readable keys** (append-only): `ed65b65095eb`, `d22371873bd8`, `8d1f98c7967e`. Round 2's O sessions: `wp-16/`. The cutoff: `wp-11c/cutoff.json` (dated as WP-11c dated).
- **M0's 28 Python keys:** `~/.hobbes/bench/calvin/commits.txt` (one line, 28 short SHAs); M0's graphs `~/.hobbes/bench/calvin/graphs{,-laneb}/`, its gold verify `~/.hobbes/bench/calvin/verify-gold{,-import}/`; the design `docs/calvin/calvin-potential.md`. Hobbes' first commit is 2026-08-24.
- **The Go repos in the cell set** (clones read-only; a package clones from them into its own `~/.hobbes/bench/calvin-gate/<wp>/` directory):

  | repo | clone | history | pin (the cell's SHA, the upper bound) | non-merge commits ≥ 2025-08-01 | of them touching `.go` |
  |---|---|---|---|---|---|
  | quic-go | `~/.hobbes/bench/extract-test-20260902/C/quic-go` | full (7,201) | `c2877d14c138` (quic-go-go-2026-09-02) | 332 | 242 |
  | cobra | `~/.hobbes/bench/comparative/repos/cobra` | full (1,106) | `adbc8813901b` (cobra-tests-hobbes-2026-09-09) | 17 | 9 |
  | fzf | `~/.hobbes/bench/oracle/repos/fzf` | **shallow, 1 commit** | `f7ae439ff5b2` (fzf-go-2026-08-27) | — | — |
  | toml | `~/.hobbes/bench/oracle/repos/toml` | **shallow, 1 commit** | `d733fc535e4a` (toml-go-2026-08-27) | — | — |
  | mux | `~/.hobbes/bench/oracle/repos/mux` | shallow, 1 commit | `db9d1d0073d2`, dated 2024-05-31 | 0 by construction | — |
  | gitleaks | `~/.hobbes/bench/comparative/repos/gitleaks` | full | `8ad8470` | exhausted (round 2) | 3 readable, append-only |

  Not in the set: syft (its keys OOM on this box, no graded cell), dagger's Go root (no cell; waits on a bigger box). Hobbes' own Go is not a separate candidate; the fallback is Hobbes' own repo, Python. fzf and toml can be counted only from a full-history clone fetched from upstream (a public fetch, not spend) into the package's directory, bounded above by the cell's SHA.

**WP-17's order of work** (the orchestrator's reading of "for each Go repo", so no ingest is spent on a repo that cannot reach 20):
1. For every Go repo above: the candidate pool under round 1's exclusions and the cutoff. Its size is an upper bound on readable keys. A repo whose pool cannot reach 20 (cobra: ≤ 9, even with gitleaks' 3 appended) is reported with its pool and not calibrated.
2. Calibrate by pool size, largest first (expected: quic-go, then fzf, then toml). Rank the pool deterministically (seed `calvin-gate-wp-17:<repo>`), then ingest contained and verify gold in rank order until 20 readable keys or the pool is spent. Report tried against readable, and the shape counts. The first repo to reach 20 at W ≥ 0.9 stops the Go branch.
3. Hobbes' own repo: all 28 of M0's keys re-scored at their parents under the round-2 metric. This is the fallback, and §0a asks for its count whatever the Go branch reads. Work in a clone of this repo under the package's directory, never the main checkout. Re-ingest a parent unless its graph is already stamped 0.1.17-beta.
4. **The Python verifier.** `harness.score` carries `vacuous` and `gold_tests` without a language branch. WP-17 confirms that Python rows carry both. Where one does not, it names the seam and changes no code.

**The unit's write partition** is template v2's `constraints.write_partition` at A2, built with live co-change (D-q), per unit. It is the partition round 2 measured O's writes against, and WP-17 stores it in `units.jsonl` as `partition`. It is a file list, so §2.2's "every touched file and span" is read **at file grain** this round; a span-grain partition is not in the template, stated. The partition is the gate's input and never O's.

**The blind-spot map** — one schema, pinned here because WP-17 writes it and WP-18 reads it in parallel. The field is `blind_spot_map` on each unit row, and the gate accepts the same object as a file:

```json
{"partition": ["path", "..."],
 "files":   [{"path": "p", "captured": true, "reason": null, "detail": ""}],
 "symbols": [{"id": "sym", "path": "p", "start": 1, "end": 9, "captured": false, "reason": "laneb-miss", "detail": "…"}],
 "sites":   [{"path": "p", "line": 7, "class": "attr-call", "reason": "dynamic-dispatch", "detail": "C-2"}],
 "partition_lines": 0, "uncaptured_lines": 0, "fraction_uncaptured": 0.0,
 "source": {"graph": "path", "built_by": "hobbes 0.1.17-beta @ sha"}}
```

- `reason` ∈ `uncaptured-file | dynamic-dispatch | laneb-miss | oracle-miss:<class>`.
- `detail` names the tail class or the C-n entry behind the reason.
- `sites` lists only the unresolved call sites in partition files, read from the parent graph's tail — the same data `list_blind_spots` serves.
- The oracle cell's miss classes (for Go: function values, closures, interface dispatch) map onto `oracle-miss:<class>`.
- `files` and `symbols` cover every partition file and every symbol in them.

**The gate's lookup rule is WP-18's to state.** The expected rule: a reference on an added line takes its site from the parent span the hunk sits in — the enclosing symbol, else the file. A new file outside capture is `uncaptured-file`.

**The gate's inputs.** `hobbes gate --diff <patch> --parent <sha>` plus the repo, the parent graph, the partition and the map, all passed as files. The gate derives nothing from the unit on its own, and its record hashes every input.

**Blocking classes:**
- Block (§6): `invented`, `near-miss`, `arity`, `undeclared-type`, `import-outside`, `unimported`, `malformed`, and `partition`.
- Advisory: `unknown`.
- Grounder v3 also has a NULL class `new`. It is not in §6's list. WP-18 states what `new` means at the gate and routes it to the orchestrator; it neither blocks nor is dropped silently.

**Languages.**
- The substrate is chosen in parallel with the gate, so the gate runs over Go and Python diffs.
- **Every blocking class must fire on Go.** Grounder v3's world and signature classes read as Go-only. On Python, WP-18's report states which classes fire.
- If WP-17 picks Python and a class cannot fire there, the orchestrator routes the gap before WP-19.

**O at A0.** `o-units --tier A0`. WP-18 checks that at A0, O's task text and session manifest carry no path or symbol from gold or the template, and reports what the manifest carries. If it carries the partition, a flag withholds it.

**Code, version, register.** WP-18 alone writes code:
- **Worktree:** `git worktree add ~/.hobbes/bench/calvin-gate/wp-18/worktree -b calvin-gate/wp-18 main`, base checked as an ancestor of `main`. A worktree lacks the gitignored build outputs (`uv sync` in `pipeline/`; `npm ci` in `scip/` and `tsextract/` before the Node-helper tests).
- **Tests** go in the same commit as the code.
- **The same commit, on the branch:**
  - the architecture's derive section amended if it lists the derive commands;
  - the gate's concessions as C-n entries from **C-121** (the `unknown` advisory, the file-grain partition, the map's grain);
  - the `CHANGELOG.md` entry.
- **The orchestrator merges** after the exit, with the patch bump to **0.1.18-beta** (ADR-103's third amendment: 0.1.x patch by patch), then rebuilds the image (C-65).
- **The design's ADR** takes its number on Max's *accepted* (ADR-106 is held for M0-Go).

**No spend in WP-17 … WP-20:** no endpoint call, no Modal; no key file is read.

**Runs and reports.**
- A package never ends its turn to wait on a detached run. If it must detach and has nothing else to do, it ends with the line `PARKED pid=<pid> log=<path>`; the orchestrator watches the PID and resumes it (the handoff's sub-agent note).
- Kill by PID.
- Artifacts go under `~/.hobbes/bench/calvin-gate/<wp>/`.
- The report is ≤ 40 lines, returned as the final reply; the orchestrator saves it as `report.md` if the package could not.

---

## 1. Why this round, stated from the record

Two rounds, $22, the same twenty-eight Go keys and eight fresh ones, three protocol versions and three grounder versions. What the record supports:

- **The linker is clean.** Across every run of both rounds: 0 mis-bound references, every NULL at the right site, poison 50/50, gold byte-equal, ~2,000 sparse-real references resolved per run with 0 sparse NULL. Grounder v3 adds arity and undeclared-type and raised them on 3 of round 1's 7 "right world, not compiled" declarations.
- **The template did not carry the generation.** Round 2 at protocol v0.6: full bodies rendered, build row in the loop, budget unbound, and the filler returned the bodies unchanged on 5 of 8 keys. O, on the same keys and model, oriented for 10–26 turns and then edited, passing 2 of 3 readable keys.
- **O makes world errors the gate is for.** Round 1 audited: 2 of O's 5 diffs write outside the write partition; round 2: a compiling invented name (`utils.Alphanumeric`) that only the build row caught. O's diffs ground at 0 NULL in the symbols they use; the errors are in placement and in names the compiler happens to accept or the tests happen not to reach.
- **The pass metric now runs tests.** 19 of round 1's 31 pass rows were vacuous; verify distinguishes pass, vacuous, `gold_tests`. A key that cannot read pass is known before spend.
- **Gitleaks is exhausted:** 8 post-cutoff keys, 3 readable.

**Decision.** Keep the world; move the agent. The doer is the frontier agent loop, which already does retrieval and intent; Hobbes' contribution is the world as a constraint and the linker on the output. This round measures the linker as a gate on the agent's finished diff: what it blocks, what it never falsely blocks, whether one bounded repair against its report raises pass, and — on a holey world — whether the stated complement lets it say *unknown* instead of *invented*.

**What the round is.** The immediate floor. It needs no protocol, no template arm, and one O session per key. Its control (the gate clears every gold) is already known to hold. It also ships: `hobbes gate` on any agent's diff is usable the day the round closes, and its class counts are the first written spec of what a world-aware doer would have to avoid.

## 2. Design

### 2.1 Units — readable keys on the chosen substrate

A key enters only if gold reads pass under the round-2 metric at its parent, contained, on the current patch. Round 1's exclusions apply; on a Go repo the add-a-rule-class cap (≤ 5 of 20) applies; shapes stratified and reported (single-file, multi-file, new-symbol, new-file). Task text is **A0** (the commit message as written): O reads the repo itself, so no anchoring is given, and the product condition is measured from the first row. W per unit, and — new — **the blind-spot map per unit**: captured and uncaptured lines of the write partition with the reason for each uncaptured span.

### 2.2 The gate — `hobbes gate --diff <patch> --parent <sha>`

One deterministic pass, no model. Over the diff at its parent:

1. **grounder v3** on every reference in the added and changed lines: NULL by class (invented, near-miss, arity, undeclared-type, import-outside, unimported, malformed), density beside each;
2. **the complement split:** each NULL site is looked up in the blind-spot map; captured → the class stands (invented etc.); blind spot → **unknown**, with the span's reason;
3. **the partition check:** every touched file and span against the unit's write partition (`in_partition: false` is a block, at any HSR — round 2's stricter parse);
4. **the verdict:** *clear* if no blocking class fires; *blocked* with the class list otherwise. *unknown* is reported, never blocks in this round (C-7, advisory), so §4.15 can measure it.

Output is a record beside the diff, stamped with the grounder and gate versions and the input hashes; byte-identical on rerun.

### 2.3 Arms — one O session, three readings

- **O** — the agent as in rounds 1–2 (manifest, exec and file tools, knowledge tools withheld, 30-turn / 1M-token cap; Haiku 4.5 at model default). One session per key. Its final diff is verified as now.
- **O+gate** — the same diff, gated post hoc. A *blocked* row is scored as blocked (no diff ships); a *clear* row keeps O's verdict. No model call.
- **O+gate+repair** — on blocked rows only, O's session resumes for **one** bounded turn with the gate's report as the message (classes, sites, the partition it left, the sibling form where a declaration is involved), then the diff is gated and verified again. Clear rows are identical to O+gate. Model calls: one per blocked row.

Every arm is computed over the same session, so the only difference between them is the gate and the one repair.

### 2.4 Controls, run before spend

- **Gold control:** the gate clears every gold diff at its parent (expected N of N; any block is a G defect that stops the round).
- **Seeded control** (the seeded policy oracle in miniature): for each key, four seeded variants of the gold diff — (i) one reference renamed to a sibling-shaped invented name, (ii) one hunk moved outside the write partition, (iii) one call's argument count changed, (iv) one reference retargeted into a blind spot of the unit's map (skipped on a unit with no blind spot). Expected: (i)–(iii) blocked with the right class, N of N each; (iv) clear with one *unknown* reported. Any miss is a G defect.
- **Determinism:** gold and seeded controls byte-identical on rerun.

### 2.5 The metric

Per row: verdict (pass | fail | vacuous | blocked), `gold_tests`, J, NULL by class with the invented/unknown split, partition writes, recall, turns, turns-to-first-edit, $, $/pass (repair turns charged to the third arm only).

---

## 3. Work packages — the DAG

**{WP-17, WP-18} in parallel → WP-19 (controls) → WP-20 (spend gate) → WP-21.** Every package writes under `~/.hobbes/bench/calvin-gate/<wp-id>/` and a `report.md`; every row carries the package id that produced it.

### WP-17 — the substrate draw (no spend)

- **Reads:** §0a, §0b, §2.1; the cell set (`docs/oracle/cells/`, `~/.hobbes/bench/comparative/`); the cutoff pin; `calvin_probe.py` (unit derivation, ingest); M0's units for the 28 Python keys; verify at 0.1.17-beta.
- **Does:** (a) For each Go repo in the cell set: post-cutoff commits under round 1's exclusions; ingest each candidate's parent contained; gold through verify; count readable keys; W. (b) Hobbes' own repo: re-score M0's 28 keys under the round-2 metric at their parents; count readable; W. (c) Apply the §0a priority; draw N = 20 (or report the shortfall); A0 task text; the blind-spot map per unit.
- **Writes:** `substrates.md` (repo → post-cutoff, readable, W); `units.jsonl` (key, parent, gold, shape, A0, W, partition, blind-spot map); `ingests.json`.
- **Exit:** a substrate chosen by the rule, or the shortfall stated for Max; every drawn key readable; every parent ingested; the map on every unit.
- **Report:** the substrate table; shape counts; W and blind-spot fraction per unit; keys excluded and why.

### WP-18 — `hobbes gate` (no spend) — depends on nothing

- **Reads:** §0b, §2.2; `ground.py` (v3) and its tests; the partition code; the O drivers' record format; the oracle lane's miss classes for the blind-spot reasons.
- **Does:** the command; the complement split against a unit's blind-spot map; the partition check at the stricter parse; the stamped record; `o-units` and the Python driver gain `--gate` (post-hoc) and `--gate-repair` (one bounded turn on blocked rows, the report as the message).
- **Writes:** code on `calvin-gate/wp-18`, tests in the same commit; the record schema.
- **Exit:** unit tests: each class fires on a synthetic diff; the split routes a NULL in a synthetic blind spot to *unknown*; the partition check blocks a synthetic outside write; byte-identical on rerun; pytest green.
- **Report:** the command as built; the schema; the repair message's shape; defects.

### WP-19 — controls (no spend) — depends on WP-17, WP-18

- **Reads:** §2.4; `units.jsonl`; the gate.
- **Does:** gold control on every key; the four seeded variants per key and the gate over each; determinism reruns.
- **Writes:** `gold-control/`, `seeded/` (per key, per variant: the variant, the gate record), `controls.md`.
- **Exit:** gold N/N clear; seeded (i)–(iii) N/N blocked with the right class, (iv) clear with one *unknown* on every unit that has a blind spot; byte-identical reruns. Any miss is a G defect: fix in WP-18, renumber, rerun.
- **Report:** the control table; defects; the blind-spot count that (iv) could use.

### WP-20 — estimate and gate (no spend) — depends on WP-19

- **Reads:** the reports; §9.
- **Does:** per-key estimate for one O session at Haiku 4.5 list from round 1's and round 2's O actuals on the chosen substrate's language; the repair-turn cost bound (one turn × the expected block count, taken as 40% of keys until measured); the ceiling request.
- **Writes:** `estimate.md`.
- **Exit:** presented to Max. Nothing below starts without the word.

### WP-21 — the run (spend) — depends on WP-20's word

- **Reads:** §2.3, §2.5, §4, §5; `units.jsonl`; the gate; the reports.
- **Does:** O once on N keys; the gate post hoc on every diff; one repair turn on every blocked row; verify on every diff, before and after repair; the §4 instruments; §5's reading selected in writing; rows attributed before any aggregate.
- **Writes:** `rows.json`; a cell page `cells/calvin-m0-gate-<date>.md` (per key: O's row, the gate record, the repair row); §10 here.
- **Exit:** every row attributed; the reading written; spend stated. **Stop rule:** after 10 keys, if O's actual exceeds 2× the per-key estimate; hard cap = the ceiling.
- **Report:** the three-arm table; blocks by class with the invented/unknown split; gold and seeded controls restated; pass before and after repair on blocked rows; $/pass; the reading; the §7 next step; spend.

---

## 4. Instruments, with attribution

Paired bootstrap over units, 5,000 resamples, seed 0; per shape.

### 4.14 What the gate blocks — G, O, U

| result shape | implicates | check | residual |
|---|---|---|---|
| blocks on ≥ 4 of 20 rows, 0 false blocks on gold, classes match the seeded controls | — | the blocked diffs, read by hand: would they have shipped an error | the linker adds value as an aid; the class counts are Calvin's first spec |
| blocks 0–1 of 20 | O at this scale, or U (keys too small) | O's turns, J, shapes | no floor here; the gate's value is on harder keys or a stronger filler (§7) |
| any block on gold | G | the class, the site | defect; the round stops until fixed |
| blocks mostly partition | O (placement) | in vs out at gold's file | the aid is scoping, not naming; O+world (§7) is the next arm |

### 4.15 The complement channel — G, W

| result shape | implicates | check | residual |
|---|---|---|---|
| *unknown* sites are real symbols at rate ≥ 0.8 (Go: the compiler key; Python: the executed key where covered, else by hand) | — | the map's reasons | the stated complement lets the gate say "I can't see" instead of "you invented"; the honesty property is measurable |
| *unknown* sites are mostly invented | W (the map is too coarse) or G | which reason class | tighten the map's grain; not a gate defect |
| no *unknown* at all (Go) | — | blind-spot fraction | expected on a dense world; §4.15 is weak here and says so |

### 4.16 Repair against the report — O, the message

| result shape | implicates | check | residual |
|---|---|---|---|
| blocked rows: pass rises after one repair turn | — | verdict before/after | the gate helps outcome, not only safety |
| blocked rows: gate clears but pass does not rise | O | what the repair changed | the gate is a detector; still shippable as one |
| repair re-blocks | O or the message | the second record | the report's shape; §7 |

### 4.17 $/pass and turns

Per arm; turns-to-first-edit beside it. A gate that raises pass at ≤ +1 turn per blocked row is the product number.

## 5. Preregistered readings

Written before WP-20.

- **Gate blocks ≥ 4 of 20 with 0 false blocks, seeded controls clean, and repair raises pass on blocked rows** → the floor exists: the linker is a measurable aid on real agent output. `hobbes gate` ships; the class counts go on the benchmark page and become Calvin's first spec; §7 step 1 next.
- **Gate blocks ≥ 4 of 20 with 0 false blocks, repair does not raise pass** → the floor exists as a safety property, not a helper. Ships as a detector; the repair message is the next thing to design, not the gate.
- **Gate blocks 0–1 of 20** → O on this substrate at Haiku scale does not make the errors the gate catches, or the keys are too small. Not a refutation of the honesty property (the controls hold), but no floor. Next: multi-file and new-symbol keys only, or one run with a stronger filler for the block rate alone.
- **Any false block on gold or any seeded miss** → G defect; nothing else is read until it is fixed.
- **On a holey world, *unknown* sites are real at ≥ 0.8** → the complement channel works; recorded as a Hobbes result whatever the block rate.
- **Blocks are mostly partition** → scoping, not naming, is what the agent lacks; O+world is the next arm.

## 6. Constraints to open on acceptance

- One substrate (WP-17's choice); A0 task text; readable keys only.
- One O session per key; arms differ only by the gate and one repair turn.
- *unknown* is advisory this round; the blocking classes are invented, near-miss, arity, undeclared-type, import-outside, unimported, malformed, partition.
- Haiku 4.5, model-default sampling; O's cap as rounds 1–2 (30 turns / 1M tokens).
- The gate is post hoc; O never sees the world during its session (that is O+world, §7).
- No security layer beyond the gate itself (§8).

## 7. Next, in order — only if the floor holds

1. **O+world:** O's reads and writes bounded by the unit's partition and the template's rendered scope; `hobbes ground` as a tool during the session; the gate at the end. Measures scoping.
2. **unknown becomes blocking**, read against §4.15's rate.
3. **The other substrate** (Go if Python was chosen; Python if Go), so the complement channel and the dense-world block rate are both on the page.
4. **A stronger filler** once, for the block rate and $/pass, same arms.
5. **Calvin model items**, now specified by the class counts, not by a charter.

## 8. Deferred

Round 1 §8 stands (effect manifest, sink reachability, ledger, isolation, NULL blocking at policy). The seeded control (§2.4) is the seeded policy oracle at its smallest; its four classes grow with the manifest when that arrives.

## 9. Cost

- **WP-17 … WP-20:** no spend. WP-17's Go branch ingests candidate parents contained (minutes each); its Python branch re-scores 28 keys locally.
- **WP-21 at Haiku 4.5 list:** O once on 20 keys — round 1 read $0.66 per key at 30 turns on Go, round 2 $0.34; M0's Python O read $2.5–5.2 per key on Sonnet 5, so on Haiku expect ≈ $0.5–1.0. O ≈ $7–14. Repair turns: one per blocked row, ≈ $0.05–0.10 each, ≤ $1. **Expected $8–15.**
- **Ceiling to state at WP-20: $15.** Drop order: N to 15 keys, then 12. Never drop the controls.
- **GPU:** none.

## 10. Results

(empty until WP-19's controls; WP-21 appends beneath)

**Decisions and gate record** (Max, through the orchestrator; dated):

- 2026-09-11 — the design recorded in the tree (this file) with the orchestrator's pins (§0b); WP-17 and WP-18 launched in parallel (no spend).
- 2026-09-11 — **WP-17, mid-package — the Go branch stops at fzf.**
  - **Pools after exclusions:** fzf 186 is larger than quic-go's 154, so fzf was calibrated first, as §0b's pool-size order requires. It reached 20 readable keys of 23 tried in rank order, at W = 1.0. quic-go was not calibrated. toml (13) and cobra (0) cannot reach 20.
  - **The rank-order draw held no multi-file or new-file key** (14 single-file, 6 new-symbol). All 22 multi-file and new-file alternates calibrated readable.
  - **Orchestrator's pin — the draw is stratified by shape,** as §2.1 and round 1's WP-0 convention (a seeded shuffle per shape, first five) require:
    - multi-file 5, new-symbol 5, new-file 3 (every readable new-file key in the pool);
    - single-file 7 (5, plus the 2 slots new-file cannot fill, given to the largest pool);
    - each shape taken in WP-17's seeded rank order within that shape.
  - **Why:** the partition check (§4.14) needs multi-file keys. Max may override the quotas.
- 2026-09-11 — **WP-17's redraw.**
  - **Every stratum filled from keys already calibrated**, with no new ingest: 7 single-file, 5 new-symbol, 5 multi-file, 3 new-file.
  - **Gold** reads pass on all 20, and W is 1.0 on all 20.
  - **Files:** `units.jsonl` holds the stratified 20; the other 22 readable keys are in `units-alternates.jsonl`; the rank-order draw is kept as `units.rankorder.jsonl`.
  - **Checked by the orchestrator from `units.jsonl`:**
    - 11 units have a blind-spot fraction of 0.0; the other 9 range from 0.0028 to 0.0221, and each of those 9 has uncaptured symbols (2–13 per unit). The package's reply said 12 and 8.
    - No unit has an uncaptured file, so seeded variant (iv) can run on 9 units.
    - Partition sizes run from 3 to 24 files, since the template's partition includes co-change files. The partition check is therefore wider than gold's own files; this is stated for §4.14's reading.
  - **The map's grain.** The parent graph keeps unresolved call sites only as per-file counts by class, so each site row carries `line: null` and a count.
    - **Orchestrator's pin to WP-18:** a site row with no line never routes a NULL to *unknown*. Only an uncaptured file, an uncaptured symbol span, or a site row that has a line can do that.
    - **Why:** otherwise one unresolved attr-call in a file would turn every invented name in that file into advisory *unknown*.
- 2026-09-11 — **WP-18 reported: `hobbes gate` is built** (`calvin-gate/wp-18` @ `b174401`).
  - **Tests:** each of the 8 blocking classes fires alone on a synthetic Go diff (8/8). On Python, `invented`, `near-miss`, `malformed` and `partition` fire; the world and signature classes are Go-only.
  - **The line-less site pin is built and tested.**
  - **Determinism:** byte-identical reruns, including on the 20 fzf golds.
  - **pytest:** 1,348, green.
  - Report: `~/.hobbes/bench/calvin-gate/wp-18/report.md`, saved by the orchestrator.
- **D-s** (G; found by WP-18, ahead of WP-19). The gold control reads **9 of 20** at the pinned partition, under both `exempt` and `strict`, and every one of the 11 blocks is `partition`. Two kinds of write cause them:
  - **Non-code files:** gold writes CHANGELOG.md, `man/man1/fzf.1`, a Makefile, fzf's Ruby integration tests, and `.s` files. No lane-A provider reads these.
  - **New Go files:** on the 3 new-file keys, gold creates Go files in a partition file's own package.

  **Orchestrator's fix: the partition rule `reach`,** which becomes the gate's default before merge.
  - Under `reach`, a write to a file no lane-A provider reads is listed (`reach: "not-code"`) and never blocks: it is beyond the graph, not outside the partition.
  - A code file created beside a partition file is listed (`beside-partition`): a template's partition cannot name a file that does not exist yet.
  - A write into an **existing** code file outside the partition still blocks, which is seeded variant (ii)'s shape.
  - **Result:** gold 20/20 clear at `reach`. The looser check is stated for §4.14.
- 2026-09-11 — **Accepted as WP-18 built them** (orchestrator):
  - **The complement split is narrower than §2.2.** Only `invented` and `near-miss` route to *unknown*. `arity`, `undeclared-type`, `import-outside` and `unimported` are read from source at the SHA, so a blind spot in the graph does not excuse them.
  - **`new`** cannot arise at the gate. If a `new` row ever appears, it is listed, counted, marked `route: true`, and never blocks.
  - **The repair turn** resumes the recorded session through `loop.py --resume-transcript` with `--max-turns 1`. Four seams for a faithful resume go to Max at WP-20:
    - a session killed by timeout has no transcript;
    - the loop's per-turn state is rebuilt from the transcript, not recorded;
    - files O left untracked are not in the harvested commit;
    - the repair runs this checkout's `loop.py`, not the recorded one.
  - **O at A0.** The task text is the commit message, and none of round 2's A0 texts named a gold file. The plan manifest `hobbes plan` derives from that text named gold files on 3 of 8 of round 2's keys, and the plan refused on 3 of 8.
    - O keeps the manifest, as rounds 1–2 did. `o-units --withhold-manifest` is built and off by default.
    - **Max chooses at WP-20.**
- **D-r** (instrument; open; found by WP-17 on Hobbes' own repo; not on this round's substrate). One Hobbes key, `29e926a27140`, reads gold `fail`. Gold's own test asserts that `built_by()["checkout"]` names the checkout. Inside the verify container that value is the fallback `built_by()` uses when `git` fails, and the verify worktree is a `git clone --shared` (the arrangement the harness already works around for Go's `-buildvcs`). The key is excluded, with this caveat, from the Python count. Which `git` call fails is not yet confirmed.
