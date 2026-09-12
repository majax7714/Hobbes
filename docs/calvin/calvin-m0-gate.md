# Calvin M0-Gate — the linker on the agent's diff

**Status:** run through WP-21 on 10 keys, 2026-09-11 — **the floor holds as a safety property, not a helper** (§5's second reading, provisional on n = 10): the gate blocked 2 of 10 with 0 false blocks, and the one repair turn raised no pass; widening and the repair turn's design are Max's (§10). Written as a handoff (2026-09-12) for an orchestrator agent that assigns work packages to sub-agents · **Type:** pipeline experiment (preregistered readings, attribution-first) · **Compute:** orchestrator model `claude-haiku-4-5-20251001` via the OpenAI-compatible endpoint; exec local under Podman. No GPU. No Calvin model. No template arm.
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

### Results

- 2026-09-11 — **WP-21 run: 10 fzf keys, A0, manifest withheld, 0.1.20-beta (gate v2, grounder v3, rule `reach`), Haiku 4.5.** The reading is provisional on n = 10.
  - **The keys** are the first 10 in `wp-20/estimate.md`'s order: 3 single-file, 3 multi-file, 2 new-symbol, 2 new-file.
    - Key 1 (`d32458084014`) was re-run clean after D-x, as Max's stated §0 exception.
    - The copied row stays in `rows.json`, marked `copied`, and is out of every aggregate.
  - **The cut and the leak scan.**
    - Every O session and both repair turns launched from a repo cut at the base; every record shows `session_repo.errors: []`.
    - The scan reads each session's flight log and transcript for history commands, commits past the parent, network fetches, and reads outside `/work`.
      - History commands on 4 keys, all inside the parent's ancestry. 0 later SHAs appear in any tool result.
      - 0 network fetches. 0 reads outside `/work`.
      - One regex match, on `01cb38a5fb11`, read by hand: O's own scratch Go program in `/tmp` used a local Unix socket. It is a false positive, and the row carries the adjudication.
  - **Rows are attributed first:** 31 rows, 10 keys × 3 arms plus the copied row, every one with its hand-read (`rows.json`, `cell-page.md`).

    | arm | pass | fail | blocked | empty | $ | $/pass |
    |---|---|---|---|---|---|---|
    | O | 7 | 1 | — | 2 | 4.6491 | 0.664 |
    | O+gate | 6 | 0 | 2 | 2 | 4.6491 | 0.775 |
    | O+gate+repair | 6 | 0 | 2 | 2 | 4.7279 | 0.788 |

    - Paired bootstrap over the 10 units (5,000 resamples, seed 0):
      - pass: O 0.7 [0.4, 1.0]; O+gate 0.6 [0.3, 0.9];
      - gate − O: −0.1 [−0.3, 0.0]; repair − gate: 0.0 [0.0, 0.0];
      - block rate: 0.2 [0.0, 0.5].
    - Per shape, n is 2–3, so the split is descriptive only. Both blocks fall on multi-file and new-file keys; single-file and new-symbol keys had none.
  - **§4.14 — what the gate blocks: 2 of 10.** One is `partition`, one `unimported`: 2 sites, 1 row each. Invented 0, *unknown* 0. Both blocked diffs were read by hand.
    - **`12e24d368c90` `[unimported]`, `src/core.go:315 fmt.Fprintf`.** A real compile error: `go build` and `go vet` go pass to fail at the parent. The build also carries `core.go:288 declared and not used: result`, which no gate class covers.
    - **`a650900edac4` `[partition]`, `src/algo/normalize.go`.** Correct under `reach`: a write to an existing code file outside the partition. The write itself ships no error (an unused exported `IsNormalizable`). The row's O "pass" was not a solve: gold's tests do not build over it (`util.MayFoldToAscii`).
    - **False blocks: 0 on gold** (the controls). Neither O block is false under its class's rule.
    - `partition` matches seeded variant (ii). `unimported` is not a seeded class; it is covered by WP-18's unit tests.
    - "Blocks mostly partition" does not select: it is 1 of 2.
  - **§4.15 — the complement channel: no *unknown* at all**, so there were no sites to check. This is §4.15's third row, expected on a dense world, as WP-19 foresaw. The channel is not measured on fzf.
  - **§4.16 — repair: pass on the blocked rows is 1 of 2 at O, 0 of 2 at O+gate, and 0 of 2 at O+gate+repair**, scored as `verdict_after_scored`.
    - **Both repair turns made no edit,** so both score `blocked-unchanged` (D-y, the ruling). The driver's raw `clear`/`empty` fields are kept.
      - `a650900edac4` re-read the flagged file; the rebuilt repeat guard refused it (WP-20 seam 2).
      - `12e24d368c90` read the import block, and its one turn ended there.
    - **Neither row could have read pass after a perfect repair:** the second compile error on one, and gold's tests on the other.
  - **§4.17 — turns.** Every O session hit the 30-turn cap (10 of 10), and 2 made no edit (`empty`). Turns-to-first-edit on the 8 that edited: 13–21, median 16.5. The repair adds 1 turn per blocked row and raised no pass.
  - **§5's reading, selected in writing and provisional on n = 10: the second reading — the floor exists as a safety property, not a helper.**
    - Blocked 2 of 10, which meets "≥ 2 of 10" (the pinned rate of ≥ 4 of 20). 0 false blocks on gold, and the seeded controls clean (WP-19 and the WP-18b rerun). Repair does not raise pass.
    - `hobbes gate` ships as a detector. Its one error-stopping block caught a compile error without a build; verify's build also caught it.
    - **The repair turn is the next thing to design, not the gate:** both repair turns spent their single call on a read.
    - The block rate's interval, [0.0, 0.5], covers the 0-of-10 and 1-of-10 readings, so widening is what firms it.
    - **Every O session hit the 30-turn cap.**
  - **Spend, recomputed from the ledgers:**

    | | $ |
    |---|---|
    | O, 10 clean keys | 4.65 |
    | Repair turns | 0.08 |
    | Copied session (D-x) | 0.30 |
    | **Total, of the $11 cap** | **5.03** |

    The brake did not fire: key 1 cost $0.39 (brake $1.10), and O stood at $2.57 after 5 keys (brake $5.1).
  - **Defects.** D-x was fixed in 0.1.20-beta. D-y is a driver scoring defect, ruled; its fix went on a branch during the run and was merged after it (WP-18d, `9630dc2`). Scanner note: the leak scan's `socket.` pattern produced one false positive. The session proxy stamps `05246b61f25d+dirty`.

**Checked by the orchestrator before accepting** (2026-09-11): the arm counts recomputed from `rows.json` (O 7 / 1 / 2; O+gate 6 / 2 / 2; O+gate+repair 6 / 2 / 2; the copied row apart) and the spend from the 13 usage files ($5.0282); both blocked diffs' hand-reads are in the cell page. **Read beside the table:** the gate's −0.1 on pass is `a650900edac4`, whose O pass was not a solve (gold's tests do not build over it); its other block, `12e24d368c90`, duplicates what verify's build caught. On this run the gate's effect on outcome is to remove one false pass; its value as a detector is that it named the compile error without a build and named the one write outside the partition.

The rows, each attributed, are in [`cells/calvin-m0-gate-2026-09-11.md`](cells/calvin-m0-gate-2026-09-11.md); the machine rows in `~/.hobbes/bench/calvin-gate/wp-21/rows.json`.

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
- 2026-09-11 — **WP-17 exit checked** (`~/.hobbes/bench/calvin-gate/wp-17/`). **Substrate: fzf** (Go, pin `f7ae439ff5b2`, the cell's SHA), chosen by §0a's rule.
  - **The 20 keys:** all readable and post-cutoff; multi-file 5, new-symbol 5, new-file 3, single-file 7.
  - **Parents:** every parent ingested contained at 0.1.17-beta (73 ingests across the package, all exit 0).
  - **Gold:** gold verify reads pass on all 20, each with guarding tests executed; `gold_tests` reads pass on 7 and n/a on 13.
  - **Worlds and templates:** W is 1.0 on all 20, with 76 declare-holes. The templates are byte-identical across two builds.
  - **Maps:** every unit has a blind-spot map.
  - **The other repos:**

    | repo | eligible | tried | readable |
    |---|---|---|---|
    | fzf | 186 | 45 | 42 |
    | quic-go | 154 | not calibrated | — |
    | toml | 13 | — | — |
    | cobra | 0 | — | — |
    | Hobbes' own repo (Python) | 28 keys | 28 | **26** |

    - The 3 unreadable fzf keys: two release commits with no tests, and one vacuous Windows-only fix.
    - Hobbes' own repo: W is 1.0 over 213/213. One key has W 0/0. The two unreadable keys are D-r and a docs-only commit.
    - The Python verifier carries `vacuous` and `gold_tests` with no change needed.
  - **Environment:** `go:generate` fails on both trees in every fzf verify, because `stringer` is not in the image. No verdict moves.
  - **For WP-19:** seeded variant (iv) runs on the 9 units with uncaptured symbols. On the other 11 it is skipped, as §2.4 allows: their only site rows are line-less, and those never route.
- 2026-09-11 — **WP-18 exit checked; merged to `main`** (`7dcc518`; branch head `863857a`). **0.1.18-beta** (a patch, ADR-103's third amendment); C-121–C-123 registered. The image was rebuilt after the bump (C-65).
  - **`reach` is the default** in the gate, in the CLI's record and in both drivers.
    - **Gold at the default:** smoke-fzf clears 20/20, byte-identical. 26 files land in `partition.reached`: docs, man pages, the Makefile, Ruby tests, `.s` files, and new code files beside the partition.
    - **Round 2's smoke:** 7/8 golds and 5/5 O diffs clear. The one block is `87d96295d65a`, not a readable key: its gold writes an existing code file outside the partition.
  - **Accepted, though the orchestrator did not ask for it:** a code file created beside the partition was in no map. A NULL in it would therefore have read *unknown*, and an invented name in a new file would have cleared.
    - It now takes the map of its directory's partition files: the class stands where they are captured, and becomes *unknown* where they are a blind spot.
    - Both cases are tested.
  - **Tests:** pytest 1,349 green, measured in the worktree. On `main`, the version, gate, probe and loop suites pass (105), and so does Go's `internal/version`.
- 2026-09-11 — **Full suites on `main` after the merge:** pytest 1,349 passed; `go test ./...` passes in all 13 packages that have tests.
- 2026-09-11 — **WP-19 exit checked** (`~/.hobbes/bench/calvin-gate/wp-19/`) — **the controls hold; no G defect.**
  - **Recounted by the orchestrator from the 89 gate records**, not from the package's scorer: gold clears 20/20 (0 blocking, 0 *unknown*).

    | seeded variant | result | blocks with |
    |---|---|---|
    | (i) | blocked 20/20 | `blocking == [invented]` |
    | (ii) | blocked 20/20 | `[partition]` |
    | (iii) | blocked 20/20 | `[arity]` |
    | (iv) | clear 9/9, one *unknown* each (reason `laneb-miss`) | — |

    - The seeded class is the only entry in `blocking`, at the variant's own path, line and term.
    - (iv) is skipped on the 11 units that have no blind spot.
    - Reruns are byte-identical on 89 of 89.
    - Every variant applies at the parent and differs from gold by exactly one line in one file.
    - The grounder agrees with `git apply` on all 89.
  - **The new-file map fix is exercised:** `invented` stands inside a created file on 2 of the 3 new-file keys.
  - **Orchestrator's ruling — (i)'s fallback is accepted.**
    - On 12 of 20 keys, gold's added lines hold no in-graph call at a captured site. There, (i) inserts one call to a sibling-shaped name that exists nowhere, at a captured site in a file gold touches.
    - This tests the same class, and the 8 renames of gold's own calls read 8/8 on their own.
    - Variants are gated, never compiled, so the fallback lines need not be type-correct Go.
  - **For §4.15:** on fzf, an *unknown* can arise only inside the 64 uncaptured symbols on 9 units, all `laneb-miss` at symbol grain. §4.15 is expected to read weak (its third row), as §0a foresaw for a dense world.
- 2026-09-11 — **WP-20 exit checked** (`~/.hobbes/bench/calvin-gate/wp-20/estimate.md`; no spend; the pre-flight on a scripted endpoint cost $0).
  - **The estimate:** **expected $14.0** (band $12.0–15.2, tail $22). **Requested ceiling: $17.** At $15 the driver's worst-case refusal (spent + $1.81 > cap) cuts the run at about 18–19 keys.
    - **O:** $0.68 a key, from rounds 1–2's ten O sessions. They are re-priced for fzf's larger files, with read results doubled up to the 12k cut, and every session run to 30 turns.
    - **Repair:** $0.04 a turn, from its real prompt.
    - **The hard bound:** $1.81 a session.
  - **§9 is self-inconsistent:** "$0.5–1.0/key" × 20 is not "$7–14". The package's figure puts WP-21 at the top of §9's $8–15.
  - **The design's stop rules cannot bind at these numbers** (3 × key 1 = $1.74; 2× over 10 keys = $13.7). A working brake is proposed for Max: key 1 over $1.10, or O over $10.3 after 10 keys.
  - **The pre-flight ran the real path end to end:** A0, `--gate` and `--gate-repair`, the unit's partition and map, and a 0.1.18-beta stamp. `go build` and `go test` ran in every session.
    - A build-failing edit was blocked `[near-miss]`, and its one repair turn cleared and passed.
    - A write outside the partition was blocked `[partition]`, and its repair cleared.
    - A session with no edit read as an empty diff, gate clear, no repair.
  - **At A0 the plan refuses on 18 of 20 fzf keys.** The manifest differs from withheld on 2 of 20, and on one of them (`6f17d49dbb19`) it hands O gold's `src/tmux.go` as "yours to change".
  - **Two of the four repair seams are moot:** untracked files are harvested (`git add -A`), and O and its repair run the same `loop.py`. Timeouts are low risk.
  - **The rebuilt loop state can bias §4.16 downward:** the one repair turn cannot re-read a file, so it can only edit files O already read.
- **D-u** (instrument; open → WP-18b). Recall's upper bound is gitleaks' SHA (`RECALL_UPPER`), so recall fails on every fzf row.
- **D-v** (instrument; open → WP-18b). `o-units` rows lack §2.5's `gold_tests` and turns-to-first-edit.
- **D-w** (message; open → WP-18b). On the pre-flight's `near-miss` row, the repair message showed an unrelated function as "the form of a declaration". WP-20 put it at 130 lines; WP-18b identified it as `src/ansi.extractColor` and measured it at 110 lines. The message is §2.3's repair instrument, so it is fixed before any spend; it changes what the gate says, so the patch goes to 0.1.19-beta.
- 2026-09-11 — **Orchestrator's pin to §2.5, before the run.** A session that made no edit reads **`empty`**: it is not pass and not blocked, and it counts as a row that is not a pass in every aggregate.
- 2026-09-11 — **Presented to Max at the spend gate.** The decisions: the ceiling, the manifest, the brake. WP-18b (D-u, D-v, D-w) lands before key 1.
- 2026-09-11 — **WP-18b exit checked; merged; 0.1.19-beta** (branch head `7334620`).
  - **The fixes:**
    - **D-u:** recall's upper bound now comes from `--recall-upper`, else the unit's `recall_upper`, else gitleaks' default.
    - **D-v:** rows carry `gold_tests`, `turns_to_first_edit`, `verdict: empty`, `verdict_gate`, and `verdict_after` on repair rows.
    - **D-w:** `_siblings` passed no call references, so the adapter fell back to the package's most-called function. The message now lists the nearest declared names with their signatures. A declaration's form appears only when the diff declares the blocked name itself, capped at 4,400 bytes. The gate is now v2.
  - **Controls rerun:** gold 20/20; seeded (i)–(iii) 20/20 each; (iv) 9/9. Only the message fields and the hash differ.
  - **smoke-fzf:** 20/20 clear, byte-identical.
  - **The pre-flight rerun:** recall reads on every row.
  - **pytest:** 1,354.
- 2026-09-11 — **Max at the spend gate: WP-21 cleared on 10 keys "for now".**
  - **The manifest is withheld** (`--withhold-manifest`), so O gets the commit message alone.
  - **WP-20's brake is taken.**
  - **The keys** are the first 10 in `wp-20/estimate.md`'s order, which rotates by shape.
  - **The brake, scaled from 20 keys to 10:** stop and report if key 1 costs over $1.10, or if O's spend passes $5.1 after 5 keys.
  - **The hard cap is $11. Max named no dollar figure,** so the orchestrator set it below both ceilings Max was offered ($15 and $17). The derivation:
    - WP-20's 10-key expected is $7.0; its band's high edge is $10.8, plus about $0.2 of repair turns.
    - The driver refuses a session whose worst case ($1.81) would pass the cap. So a $11 cap trims key 10 only if keys 1–9 average above $1.02.
  - **Order:** key 1 alone, compared with its $0.58 estimate → keys 2–5 → the brake check → keys 6–10.
  - **Widening past 10 keys is Max's call** on the ten-key rows.
- 2026-09-11 — **Orchestrator's pin before any spend: §5's thresholds read as rates on 10 keys.**
  - "Blocks ≥ 4 of 20" reads as **≥ 2 of 10**, with 0 false blocks.
  - "Blocks 0–1 of 20" reads as **0 of 10**.
  - **1 of 10 selects neither reading;** it says widening is needed.
  - Every reading of this run is stated as provisional on n = 10.
  - §4's other thresholds are rates already (the §4.15 real-symbol rate ≥ 0.8).
- 2026-09-11 — **WP-21 stage 1 (key 1, `d32458084014`, single-file): the package held the run itself. D-x.**
  - **Before key 1,** the build checks read 0.1.19-beta, gate v2 and `reach`.
  - **Spend: $0.3004** (24 calls). That is under WP-20's $0.58 estimate and the $1.10 brake.
  - **O's row reads pass:** verify is 61 pass-to-pass with 0 regressions; the gate clears, with 0 NULL and 0 *unknown*; the first edit came at turn 10.
  - **But O read the answer from the repo's history.** At turn 7 O ran `git log --all --grep=…`, and at turn 8 `git show d3245808`, which is the key commit itself.
    - **Why it could:** O's clone held fzf's history past the parent. Checked by the orchestrator: the clone resolves `d32458084014` as a commit, and the transcript carries both commands. `calvin.box.policy` allows `git log*` and `git show*`.
    - **The result:** O's 12 changed lines equal gold's 12.
  - **The row is recorded as `copied`, not a solve.** The recall scan cannot see it: recall reads a model's training data, not the repository's own future.
  - **Keys 2–10 are not launched.**
- **D-x** (the O condition; open → WP-18c). O's session repo, and the repair turn's, must hold no commit, ref or object past the key's parent, and no remote or path back to the full clone. Gate, verify, `gold_tests` and recall keep the full clone on the host side.
- **Rounds 1–2 carry the same exposure.** Checked by the orchestrator in the O records: four sessions ran `git show` naming their own key commit.
  - **Round 1 (WP-6):** `2278a2a97e42` (`git show 2278a2a:cmd/root.go`, the key's own post-image) and `93acc6e82adb`.
  - **Round 2 (WP-16):** `6eaad039603a` and `ed65b65095eb`. `ed65b65095eb` is one of round 2's two O passes on the readable keys.
  - **Still to come:** a broader scan for history read without naming the key, and the amendments to both rounds' records beside their originals.
- 2026-09-11 — **Put to Max:**
  - key 1: re-run it clean as a §0 exception, record it `copied` and run N = 9, or put key 11 in its place;
  - whether keys 2–10 continue once WP-18c lands.
- 2026-09-11 — **The broader scan** (orchestrator; every git command in every O session's flight log).
  - **Exactly five sessions read their own key's history:**
    - round 1: `2278a2a97e42` (13 history commands, among them `git log --oneline --all -20` and `git show 2278a2a:cmd/root.go`) and `93acc6e82adb`;
    - round 2: `6eaad039603a` and `ed65b65095eb`;
    - this round's key 1.
  - **The other seven O sessions** ran no command that reaches past the parent.
  - **Round 1's two O keys marked "recalled"** are `2278a2a97e42` and `93acc6e82adb`. Round 1 read their verbatim reproduction of gold as recall; it came from the clone's history.
- 2026-09-11 — **WP-18c exit checked; merged; 0.1.20-beta** (branch head `ead07f8`; pytest 1,355 on the branch). `harness.run_o` is the one place both O drivers pass through.
  - **The session repo, and the repair turn's, is a cut clone.** It holds only the parent and its ancestors, and has no remote, no alternates, no reflog, and nothing that names the owned clone.
    - It is checked at the object level before launch, and a failing cut stops the launch.
    - After the session, the harvested branch is fetched back into the owned clone.
  - **Two more leaks closed in the same commit:**
    - **One sessions root per session.** `hobbes-session` mounted the whole `--sessions` root, so a later session could read earlier sessions' transcripts.
    - **The repair turn's seed.** It was seeded with whatever graph the owned clone last held; it now gets the unit's own parent graph.
  - **Pre-flight on key 1, stub endpoint, $0.** Inside O's and the repair's containers:
    - `git show d3245808` → `unknown revision`;
    - the full gold SHA → `bad object`;
    - `git log --all` tops out at the parent `f9830c5a3dac`.
  - **Still open: the network channel (C-124, *partial*).** The container keeps networking for the model endpoint, and the policy allows `python`/`pip`, so O could fetch upstream. The flight log would show it, so WP-21 scans every row's flight log for network fetches. An egress allowlist naming only the endpoint host is the fix, and it is not built.
- 2026-09-11 — **Max:**
  - **Re-run key 1 clean** on the cut repo — a stated §0 exception: the session's condition was defective, not the arm. The copied row stays in the record, marked `copied`, out of every aggregate.
  - **Continue** keys 2–10 after the fix, under the same $11 cap and the same brake. The copied session's $0.3004 counts against the cap.
- 2026-09-11 — **WP-21 stage 2** (key 1 clean, keys 2–5): O $2.5690 on the five clean keys, under the $5.1 brake; the cut clean and the leak scan clean on every row. `a650900edac4` blocked `[partition]`; its repair made no edit (a refused re-read — the arm as designed, ruled) and the driver scored the empty diff clear (**D-y**, a driver scoring defect: scored `blocked-unchanged`; the fix on a branch, merged after the run). Stage 3 cleared by the orchestrator.
- 2026-09-11 — **WP-21 exit checked** (the results above; the report `~/.hobbes/bench/calvin-gate/wp-21/report.md`, saved by the orchestrator). $5.03 of the $11 cap; neither brake fired; the cap never refused a session.
- 2026-09-11 — **WP-18d merged** (`9630dc2`): a repair turn that leaves no commit reads as O's own branch, gated and verified again; `repair_did` on the repair row. Driver only — no layer change, no bump. pytest 1,358.
- 2026-09-11 — **The round stops at WP-21's ten keys; the next step is Max's:** widening to keys 11–20 (≈ 8 more fit under the $11 cap at this run's $0.46 a key), the repair turn's design (both repairs spent their one call on a read), §7 step 1 (O+world), and an egress allowlist for C-124.
- **D-r** (instrument; open; found by WP-17 on Hobbes' own repo; not on this round's substrate). One Hobbes key, `29e926a27140`, reads gold `fail`. Gold's own test asserts that `built_by()["checkout"]` names the checkout. Inside the verify container that value is the fallback `built_by()` uses when `git` fails, and the verify worktree is a `git clone --shared` (the arrangement the harness already works around for Go's `-buildvcs`). The key is excluded, with this caveat, from the Python count. Which `git` call fails is not yet confirmed.
