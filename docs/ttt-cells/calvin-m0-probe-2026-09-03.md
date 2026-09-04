# Calvin M0 — the pre-run probes (2026-09-03, night): coverage ceiling and anchor pass, base graph vs. parent graphs

**Experiment:** `docs/calvin-potential.md` (M0, then at its v1 — see
*What v1 got wrong* below); the charter is `docs/calvin-charter.md`.
**What this is:** the two instruments that need no orchestrator
(§4.1 template coverage, §4.2 anchor pass at file grain), run first
against the one release-SHA graph the TTT cell used and then against a
lane-A graph ingested at each unit commit's **parent**. These are
**one-off probes, not cell records**: file grain for anchors, no scorer
version pinned, and hunk placement uses the diff's post-image line
numbers against parent spans (slightly generous for hunks that insert
lines). They are what §0 of the design quotes; they were re-run on
2026-09-04 from the in-tree script and reproduced to the digit.

**Provenance.** Run in a Claude Code session of 2026-09-03 (21:06–21:37
local) at Hobbes `33fec69`, from a scratchpad that has since been
copied to `~/.hobbes/bench/calvin/` (`probe.py`, `probe2.py`,
`ingest-parents.sh`, `commits.txt`, `graphs/`, and the v1 design text
as `calvin-m0-socket-v1.md`). The in-tree form is
`pipeline/scripts/calvin_probe.py` (`ingest | probe | anchors`), the
same logic with paths parameterised; `tests/test_calvin_probe.py`
holds its pure pieces. Units: the 50 cell units
(`~/.hobbes/bench/ttt/cell-hobbes/units.jsonl`) with their gold diffs
from the 147-row `units/hobbes.jsonl`; the 28 proposals
`bench/ttt/proposals-hobbes-ebdf7a5.jsonl`. **Lane A only**
(`HOBBES_SCIP=0`): spans, paths and names are lane A's, so lane B adds
nothing to these two instruments. Every parent graph stamps
`built_by.sha = 33fec69`, schema 4, `containment.all_contained`. The
graphs are regenerable (~2 s each) and are not committed.

## The 28 unit commits and their parents

| commit | parent | commit | parent |
|---|---|---|---|
| `00e5aeeaa3e2` | `d40c99899647` | `6511f40b6674` | `8c0389ad2d58` |
| `0197636f873d` | `93610cc94e4a` | `84ed59a8e00a` | `4b3fd33b0659` |
| `0fd999018e69` | `00e5aeeaa3e2` | `8c21d5acc5b1` | `8dc41bfefe2a` |
| `11e4c9df756f` | `3114f998ac2b` | `8fd57bb7a5f0` | `6409bd42d83d` |
| `19bddc9230fb` | `3604a4bc35e5` | `9c474c6eeb11` | `e499500e8646` |
| `27ee019c7767` | `742ebd3da7ba` | `b53fedc39b42` | `8807cb30002c` |
| `29e926a27140` | `ee4d95248cf6` | `b8afd416b460` | `d6cccf422076` |
| `3234b3636613` | `5549ea00aad5` | `c40885a61c4f` | `b8afd416b460` |
| `3604a4bc35e5` | `c72398ec75ae` | `c59916fe2222` | `19bddc9230fb` |
| `3bd891728d63` | `3c0e7c0ff2ca` | `c72398ec75ae` | `b53fedc39b42` |
| `4b3fd33b0659` | `74939a4babf1` | `c85090be5076` | `6511f40b6674` |
| `5549ea00aad5` | `c59916fe2222` | `cd01d0528800` | `c40885a61c4f` |
| `557d1ce3f0a6` | `1241aa6ecbea` | `d5098356edf2` | `138f0915e20c` |
| `6409bd42d83d` | `e61042686b34` | `ee4d95248cf6` | `8c21d5acc5b1` |

28 distinct parents, one lane-A ingest each; several unit commits are
each other's parents, so a parent graph is sometimes another unit's
commit. The design's per-parent ingest cost (§7.1) is 28 ingests at
~2 s lane-A-only on this repo; a semantic ingest per parent is the
cost step 0 of §8 still has to measure.

## §4.1 — template-coverage ceiling, 680 gold-diff hunks over the 50 units

| | base graph (`ebdf7a5`) | parent graphs |
|---|---|---|
| hunks in files the graph lacks | 378 (56%) | 119 (18%) |
| · of those, code files | 283 | 24 |
| · of those code hunks, in a file the commit itself creates | 24 | 24 |
| · non-code (docs 35, `.sh` 32, `.json` 16, `.mod` 6, `.toml` 4, `.gradle` 2) | 95 | 95 |
| inside a symbol span | 234 (34%) | 458 (67%) |
| known file, outside every symbol span | 68 (10%) | 103 (15%) |
| per-unit ceiling, median | 0.11 | 0.71 |
| units with zero coverable hunks | 22 of 50 | 4 of 50 |
| units at or above 0.5 | 21 | 42 |
| **code hunks only (585):** inside a span | 40% | **78%** |
| **code hunks only:** absent code file | 48% | **4%** |
| **code hunks only:** known file, outside every span | 12% | **18%** |

Multi-file units: 44 of 50.

**Reading (as recorded that night).** Against the base graph the run as
specified would mostly measure C-84: the units are commits after the
base, so the graph predates the files they create, and half the units
cannot be templated at all. Re-basing at the parent removes that door
almost entirely: the 24 code hunks still in absent files are all in
files the commit itself creates — the true `NEW_SYMBOL` residual, 4%
of code hunks. The residual that *grows* is H-s's: 103 hunks (18% of
code hunks) sit in a file the graph has but outside every symbol span
— imports, module-level constants, top-level statements. A
module-level span rule in the structure pass covers them; it is not a
Calvin job. That is `MODULE_REGION` in the v2 design (§2.1).

## §4.2 — anchor pass at file grain: the planner's exact-match seed resolver (`build_impact`, C-36) vs. the files the gold diff touches, 28 proposals

| | base graph | parent graphs |
|---|---|---|
| precision | 0.12 (17/137) | 0.21 (37/178) |
| recall | 0.12 (17/147) | 0.25 (37/147) |
| zero-anchor proposals | 1 | 0 |
| misses in files the graph lacks | 92 of 130 | 37 of 110 |
| unresolved code-shaped terms | 178 | 182 |

The breakdown behind the parent row (`anchors`):

| | n |
|---|---|
| seeds: explicit / code-shaped | 0 |
| seeds: lexical (proposal text alone) | 178 |
| wrong-file anchors, all lexical | 141 |
| gold files the parent graph has but no anchor reached | 73 |
| · the task text names the file or a symbol in it | 9 |
| · the task never names it | 64 |
| unresolved code-shaped terms | 182 |
| · appear in the gold diff's **added** lines (names the task asks to be created) | **118** |
| · not in the diff at all | 64 |

**Reading (as recorded that night).** Recall stays low after re-basing
because these proposals are prose that describes behaviour without
naming files: of the 73 reachable gold files no anchor reached, only 9
are named in the task at all. That is not a matcher gap; for this unit
set the anchor pass belongs to the orchestrator's `ANCHOR` hole (§4.2's
last row). Precision is low for the opposite reason: every anchor is a
bare-word lexical match, and 141 land on files the diff does not touch
— the noisy path C-36 registers, so M0's matcher order (backticked
identifiers and paths first) should be evaluated apart from the
bare-identifier rule. And the `new` class is visible before any
orchestrator runs: 118 of the 182 unresolved terms are symbols the diff
creates, which a graph at the parent cannot hold by definition. That
points at M1′ (where new things go) before M1 (fuzzy matching), and
the v2 design preregisters the door order that way (§9). Fuzzy-match
noise — what Calvin v0 was first proposed to catch — had not appeared
at this stage. This resolver lacks M0's test-id, stack-trace and
error-string matchers, so the anchor rows are a floor.

## What v1 got wrong — the assessment that produced v2

The same session assessed the v1 design against the tree before
probing. Its findings, each adjusted in v2 (§11):

| # | v1 assumed | the tree | v2 |
|---|---|---|---|
| V-1 | `hobbes template` in Go, "because `expand()` is there" | `expand()`, partitions, co-change, manifests are Python (`derive/`); Go holds only the six read-only knowledge tools | template in Python beside `derive/` (§2.1) |
| V-2 | grounder v0 in Go, "tokenize with lane A" | lane A is Python tree-sitter plus the Node helper; Go has no grammar and only `yaml.v3` + the MCP SDK | grounder in Python (§2.3) |
| V-3 | a Modal sandbox with policy below the model | the Modal scripts train adapters and serve vLLM; policy and containment are rootless Podman on this box | local Podman; the Modal-policy ADR deferred (§2.4, §7.4) |
| V-4 | the fill adapter inside the Pier harness | Pier is not installed in the pipeline environment; the owned loop speaks OpenAI-compatible chat completions only | adapter written new for that surface (§2.2) |
| V-5 | fastapi DeepSWE units as a second set | two units | a smoke test, raw rows, no aggregate (§3.1, §7.5) |
| V-6 | units at the release SHA `ebdf7a5` | coverage then measures C-84 (56% of hunks in files the graph lacks) | units re-based at the parent (§3.1); C-84 becomes the *new file* bucket |
| V-7 | (no module-level rule) | 18% of code hunks outside every span at the parent | `MODULE_REGION` holes (§2.1) |
| V-8 | `new` as one NULL class among five | 118/182 unresolved terms are new names at the anchor stage | `UNRESOLVED` classification round; M1′ before M1 (§9) |

What v1 assumed and the tree **has**: the graph at SHA with tiers and
spans (2,847 symbols at the base), plan derivation, the testmap (1,527
cases with reach), the 50 units and 28 proposals (probe values 0.044
this repo / 0.129 fastapi match the cell records), the §9b defect
register.
