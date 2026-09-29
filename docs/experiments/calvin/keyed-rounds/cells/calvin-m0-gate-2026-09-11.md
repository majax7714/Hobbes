# Calvin M0-Gate cell — fzf, 10 keys · 2026-09-11 · WP-21

**Build:** Hobbes 0.1.20-beta (`05246b6`; the image rebuilt after it). `hobbes gate` v2, grounder v3, partition rule `reach`.
**Arm O:** `o-units --tier A0 --withhold-manifest`: the commit message alone, with no manifest. Knowledge tools are withheld. Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) at the model's default sampling. Limits: 30 turns, a 1M-token budget, 4,096 output tokens per call. One session per key, each launched from a repo cut at the key's parent (D-x).
**O+gate:** the gate runs post hoc, with the unit's partition and blind-spot map. **O+gate+repair:** one bounded turn on each blocked row, resumed from O's transcript, with the gate's report as the message.
**Substrate:** fzf, pin `f7ae439ff5b2`, W = 1.0 on every key. The keys are WP-17's stratified draw, taken in `wp-20/estimate.md`'s order.
**Records:** `~/.hobbes/bench/calvin-gate/wp-21/`. The files are `rows.json`, `rows.jsonl`, `repair-rows.jsonl`, `analysis.json`, `attributions.json`, plus each session's `.o.diff`, `.gate.json`, `.verify.json` and `.session.log`, and `sessions/<id>/<id>/`. The leak scanner is `scripts/leak_scan.py`. Every row carries `"wp": "wp-21"`.
**The reading is provisional on n = 10.**

## Summary

| arm | pass | fail | blocked | empty | $ | $/pass |
|---|---|---|---|---|---|---|
| O | 7 | 1 | — | 2 | 4.6491 | 0.664 |
| O+gate | 6 | 0 | 2 | 2 | 4.6491 | 0.775 |
| O+gate+repair | 6 | 0 | 2 | 2 | 4.7279 | 0.788 |

- **Blocks:** 2 of 10: `partition` 1 and `unimported` 1. Invented 0, *unknown* 0.
- **Pass on the blocked rows:** 1 of 2 at O, 0 of 2 at O+gate, 0 of 2 at O+gate+repair. Both repair turns made no edit; they read `blocked-unchanged` (D-y).
- **Bootstrap** (paired, 5,000 resamples, seed 0):
  - pass: O 0.7 [0.4, 1.0]; O+gate 0.6 [0.3, 0.9];
  - gate − O: −0.1 [−0.3, 0.0];
  - block rate: 0.2 [0.0, 0.5].
- **Turns:** every session hit the 30-turn cap. Turns-to-first-edit on the 8 sessions that edited: 13–21.
- **Spend:**

  | | $ |
  |---|---|
  | O, clean keys | 4.6491 |
  | Repair turns | 0.0788 |
  | Copied session (out of every aggregate) | 0.3004 |
  | **Total, of the $11 cap** | **5.0282** |

- **Controls** (restated; they were not re-run at 0.1.20-beta, whose diff touched the harness and the driver, not the gate):
  - **WP-19** (0.1.18-beta, gate v1): gold 20/20 clear; (i) `[invented]` 20/20; (ii) `[partition]` 20/20; (iii) `[arity]` 20/20; (iv) 9/9 clear with one *unknown* each (`laneb-miss`); 89/89 byte-identical.
  - **WP-18b rerun** (0.1.19-beta, gate v2): the same counts; only the message fields and the hash differ.
- **Leak scan:**
  - 0 later commits named in any tool result, 0 network fetches, 0 reads outside `/work`, on every row.
  - One regex match, on `01cb38a5fb11`, was read by hand: a local Unix-socket scratch program in `/tmp`, a false positive.

## Per key (O's row · the gate record · the repair row)

**1. `d32458084014` (single-file). Fix the AWK tokenizer to treat newline as whitespace.**
- **O:** pass. Verify: 61 pass-to-pass, 0 regressions. `gold_tests` pass. J 0.67; recall 0.0 (gold) / 0.0 (upstream). 30 turns (the cap); first edit at turn 16. $0.3902.
  - O's own fix treats 10 and 13 as whitespace, with its own test, and leaves a scratch test file behind.
  - Its history reads stay within the parent's ancestry.
- **Gate:** clear. 0 NULL, 0 *unknown*.
- **Copied session** `calvin-o-d32458084014-20260911T192310` (0.1.19-beta, before D-x): `git show d3245808` at turn 8; its 12 changed lines equal gold's. $0.3004, `verdict: copied`, out of every aggregate.

**2. `7b16e44f5343` (multi-file). Rune slices alias the text.**
- **O:** pass. Verify: 95 pass-to-pass, 0 regressions. `gold_tests` pass. J 0.5; recall 0.0 / 0.0. 30 turns; first edit at turn 19. $0.3186.
  - O copies `ToRunes()` before mutating (make + copy; gold uses append) and adds aliasing comments to `chars.go`.
- **Gate:** clear.

**3. `3e751c4e8716` (new-symbol). A direct algo fast path.**
- **O:** pass. Verify: 60 pass-to-pass, 2 new tests pass, 0 regressions. `gold_tests` n/a. J 0.33; recall 0.0 / 0.0. 30 turns; first edit at turn 14. $0.6849.
  - `canUseFastPath` and `matchChunkFast` in `pattern.go` are O's own structure; gold's is `buildDirectAlgo`, plus `result.go`.
- **Gate:** clear.

**4. `a650900edac4` (new-file). Prefilter rune-mode input.**
- **O:** pass. Verify: 84 pass-to-pass, 0 regressions. **`gold_tests` build-fail** (`util.MayFoldToAscii` is undefined). J 0.11; recall 0.0 / 0.062. 30 turns; first edit at turn 17. $0.8806.
  - O flags normalizable runes in `util/chars.go` and adds an unused `IsNormalizable` to `src/algo/normalize.go`.
  - It does not implement the SIMD prefilter.
- **Gate: blocked `[partition]`, `src/algo/normalize.go`.** That is an existing code file outside the 15-file partition, and gold does not touch it.
  - Hand-read: correct under `reach`. The write itself ships no error; it is dead code in the wrong file.
  - The row's O pass is not a solve by gold's tests.
- **Repair** (`-repair1`): one call, $0.0442, a 406-character message naming the file.
  - O answered "I cannot edit normalize.go. Let me undo that change" and re-read the file, which the repeat guard refused (the rebuilt state, WP-20 seam 2). No edit.
  - **Scored blocked (`blocked-unchanged`).** The raw `gate_after` clear and `verdict_after` empty read an empty diff (D-y).

**5. `d1cea64a0ef3` (single-file). Allow combining `~` with a negative height.**
- **O:** pass. Verify: 41 pass-to-pass, 0 regressions. `gold_tests` n/a. J 0.5; recall n/a (0 lines added). 30 turns; first edit at turn 21. $0.2947.
  - O deletes the guard: gold's core code change, without its help and man-page text.
- **Gate:** clear.

**6. `01cb38a5fb11` (multi-file). `--listen` on Unix domain sockets.**
- **O:** pass. Verify: 5 pass-to-pass, 0 regressions. `gold_tests` n/a. J 0.2; recall 0.138 / 0.138. 30 turns; first edit at turn 13. $0.4050.
  - The socket support is in `server.go` only, keyed on a `/` or a leading `.`; gold keys on `.sock` and touches 5 files.
- **Gate:** clear.
- **Leak scan:** one match, adjudicated a false positive (a local scratch program).

**7. `74e98cac5cb7` (new-symbol). Fix `--preview-window follow` with wrapping (contd.).**
- **O:** **empty.** 30 turns, all reads, searches and test runs. O concluded the named methods already exist, and never edited. $0.3291.
- **Gate:** clear, on an empty diff. Scored empty in every arm.

**8. `6f17d49dbb19` (new-file). Support a zellij floating pane via `--popup`.**
- **O:** **empty.** 30 turns: it searched the history for the PR (inside the ancestry) and read `options.go`; it was still planning when the cap hit. $0.4100.
- **Gate:** clear, on an empty diff. Scored empty in every arm.

**9. `4b23aa45a89c` (single-file). Omit `FZF_CURRENT_ITEM` when the item holds a NUL byte.**
- **O:** pass. Verify: 26 pass-to-pass, 0 regressions. `gold_tests` n/a. J 1.0; recall 0.0 / 0.0. 30 turns; first edit at turn 16. $0.3554.
  - The same behaviour as gold, in O's own text, with a man-page note.
- **Gate:** clear.

**10. `12e24d368c90` (multi-file). Add a `--bench` flag.**
- **O:** **fail (build-fail).** `go build` and `go vet` go pass to fail. `gold_tests` n/a. J 1.0; recall 0.152 / 0.152. 30 turns; first edit at turn 20. $0.5806.
- **Gate: blocked `[unimported]`, `src/core.go:315 fmt.Fprintf`** (`fmt` is imported by no import of the file).
  - Hand-read: a real compile error, and the build agrees.
  - The build's second error, `core.go:288 declared and not used: result`, is in no gate class.
- **Repair:** one call, $0.0346. O read `core.go`'s import block (lines 1–15) to add `fmt`, and the turn ended there. No edit.
  - **Scored blocked (`blocked-unchanged`).**
  - Even a correct import would not have built, because of the second error.

## Reading (§5, provisional on n = 10)

**The floor exists as a safety property, not a helper.**
- The gate blocked 2 of 10 (≥ 2 of 10 is the pinned rate), with 0 false blocks on gold and the seeded controls clean. Repair does not raise pass: 0 of 2.
- `hobbes gate` ships as a detector.
- **The repair turn is what to design next:** both repair turns spent their single call on a read.
- **Weak or unmeasured here:**
  - §4.15: 0 *unknown*, a dense world.
  - The block rate's CI, [0.0, 0.5], overlaps the 0-of-10 and 1-of-10 readings.
- Every O session hit the 30-turn cap, and 2 of 10 made no edit.
