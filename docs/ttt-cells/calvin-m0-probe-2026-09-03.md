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

## Addendum 2026-09-04 — step 0's other half: the contained lane-B ingest per parent

`calvin_probe.py ingest --lane-b` over the same 28 parents, from Hobbes
`8add0a0`, the full contained ingest (ADR-092: every lane B step in
`hobbes-session:local`, `--network none` for every index step; the
clone venv-less as the TTT base ingest was, C-85). Graphs under
`~/.hobbes/bench/calvin/graphs-laneb/` (188 MB, regenerable).

| | |
|---|---|
| parents ingested | 28 of 28, exit 0 each |
| wall time, total | 698 s (11.6 min) |
| wall time per parent, min / median / max | 20 s / 24 s / 37 s |
| symbol edges over the 28 graphs | 176,824 — **176,796 semantic**, 28 syntactic |
| `containment.all_contained` | true on every graph; no escape hatch |
| degradations, every graph | the standing C-28 dup-namespace records (Go packages, cargo targets); C-85 (no venv: third-party Python edges absent, not nonexistent); `bench/oracle/java` below no build file |

**§4.1 and §4.2 re-run on the semantic ledgers: every number identical
to the lane-A rows above** — 458 / 103 / 119 hunks, median ceiling
0.71, anchors 0.21 / 0.25, 182 unresolved terms with 118 new, 73
unreached gold files of which 64 never named. Expected: both
instruments read spans, paths and names, which are lane A's; lane B
changes what a reference *resolves to*, which the grounder (step 3)
is the first instrument to consume. §7.1's per-parent cost on this
repo is therefore ~24 s contained, not the ~2 s lane-A figure, and
the ledger step 3 will ground against is the one the charter §6 asks
for (semantic-tier resolution, so "exists" is not a guess).

## Addendum 2026-09-04 (afternoon) — step 1: the hole schema and one hand-written template

**Built:** `hobbes.derive.holes` (the hole language v0 — `HOLE_TYPES`,
`FILL_SHAPES`, `validate_template`, `validate_fill`, `validate_fills`,
`render`; `TEMPLATE_VERSION = 0`) and one template written by hand for
the §9b unit `c59916fe2222` ("Add a --no-tests flag to `oracle go-rta`
…", two files, four hunks) at its parent `19bddc9230fb`:
`bench/calvin/templates/c59916fe2222.template.json`, its rendered
fillable form `….template.md` (1,021 lines, the current code of every
span read from git at the parent), and `….fills-gold.json` — the gold
diff expressed as fills, spans cut from the **child** commit's own
ledger (`graphs-laneb/5549ea00aad5.json` is the graph *at*
`c59916fe2222`), nothing typed. `tests/test_holes.py` (7) holds the
schema, the render, the template's facts against the ledger (every
symbol hole on a symbol span, no region overlapping one, the cited
edges semantic, the nine reaching tests) and the exit criterion: **the
gold fills validate against the template with nothing missing.**

**What the template holds (53 holes).**

| type | n | of which |
|---|---|---|
| `UNRESOLVED` | 1 | four terms: `go-rta` → refers (`main.runGoRTA`; nearest name `gorta` at distance 1), `no-tests` → new, `non-test` / `H-9.` → not-code — answered by hand as round 1 |
| `ANCHOR_CONFIRM` | 4 | the four bare-word lexical seeds (`root`, `load`, `test`, `packages` → `web/src/main`, `policy/load`, `knowledge`, `graphModel`), all answered *no* — the probe's 141 wrong-file anchors, seen at one unit |
| `SIGNATURE` / `BODY` | 2 / 2 | `gorta.Options` (37–41), `gorta.Run` (47–215) |
| `CALLER_UPDATE` | 8 | `main.runGoRTA` (in partition); six `gorta_test` callers (guarding tests, in partition); `grade_test.cell` **closed: partition** |
| `TEST_EXPECTATION` | 9 | every test the testmap says reaches `gorta.Run` (six in `gorta_test`, three in `grade_test`) |
| `MODULE_REGION` | 18 | head / imports / gaps of both files — no tail (both end on a symbol) |
| `COCHANGE_TOUCH` | 7 | partners at ≥ 2 co-commits in 200 (`grade.go`, `grade_test.go`, `export.go`, `run-cell.sh`, `README.md`, `edges.go`, `export_test.go`) |
| `NEW_SYMBOL` | 1 | for `no-tests`; the gold answer is `{"covered_by": ["h2", "h5"]}` — a field and a local, not a top-level symbol |
| `FREEFORM` | 1 | gold answer `"none"` |

**Readings the hand-writing produced (each a step-2 rule or a design
amendment, all carried into `calvin-potential.md`):**

1. **Anchors for this task come from the literal, not the identifier.**
   The backticked `oracle go-rta` matches no node id or basename; as a
   literal it sits in `main.usage`'s text (main.go:45), and `go-rta`
   as a literal sits in `main.main`, `main.runGoRTA` and `gorta.Run`
   (gorta.go:195). One hop of the structure pass from `runGoRTA`'s
   callees then reaches `gorta.Options` and `gorta.Run` — both gold
   files covered. Whether matcher 5 (literal search) applies to a
   backticked non-identifier is a rule step 2 must decide; the
   template records the anchor as `literal` and says so.
2. **Holes ≫ hunks at this stage (§4.7): 47 open holes for 4 hunks.**
   18 regions, 9 test expectations, 8 caller updates and 7 co-change
   partners are each one question the gold answers "unchanged"; the
   pattern fill is what makes the form answerable, so `MODULE_REGION`,
   `TEST_EXPECTATION` and `COCHANGE_TOUCH` take it alongside
   `CALLER_UPDATE`. The design's prune ("regions on untouched files")
   does not fire here — both files are touched — so the region count
   is the real cost of the rule, 18 for two Go files.
3. **`NEW_SYMBOL` needs a `covered_by` answer.** The new thing the
   task names (`no-tests`) is a struct field and a flag local, not a
   new top-level symbol; without `covered_by` the hole could only be
   answered wrongly. This is the shape §4.3's `new` class will take
   most often on this unit set, and it is what §4.2's fourth row
   ("does the NEW_SYMBOL fill then land in the right file/region")
   must score: *covered by the right holes* is a placement answer.
4. **`FREEFORM` needs `"none"`.** A reader with nothing to add must be
   able to close the hole.
5. **A SIGNATURE hole on a `type` is a one-line span of a struct
   header;** the field list is the BODY. The gold changes the body
   (adds `NoTests bool`) and leaves the signature unchanged, so the
   pruning rule "SIGNATURE = unchanged closes the CALLER_UPDATEs"
   would have closed `h5` — wrongly, since the caller *does* change
   to pass the new field. **The rule holds for functions and is wrong
   for types:** a type's callers change when its fields do. Step 2's
   pruning must scope that rule to function signatures.

The v0 schema, the template and the gold fills are step 3's first
grounder input: 3 hand-checked fills, 4 pattern fills, one
`covered_by`, one `"none"` → the expected output is the gold diff at
the parent with HSR 0 and NULL 0.

## Addendum 2026-09-04 (evening) — step 2: `hobbes template` over the 28 proposals at their parents

**Built:** `hobbes.derive.template` (`Ledger`, `anchor_pass`,
`structure_pass`, `build_template`, `apply_round1`, `prune`,
`score_coverage`, `score_anchors`), the `hobbes template` subcommand,
`calvin_probe.py templates` (the batch: build, rebuild, compare bytes,
score) and `tests/test_template.py` (10, on a synthetic ledger over a
temporary git repo). Templates under `~/.hobbes/bench/calvin/templates/`
(regenerable).

**Exit criterion:** 28 of 28 templates regenerate **byte-identical** at
the parent (`template_hash` equal on rebuild); build wall 1.4 s for all
28 (mean 0.05 s; the co-change window is the cost, ~1 s per parent).
The 50 cell units share 28 `(parent, task)` keys, so 28 templates;
the scores below are unit-weighted over the 50 as the probe's were.

**§4.1 — actual template coverage, no orchestrator round (680 hunks).**

| bucket | hunks | |
|---|---|---|
| symbol span (SIGNATURE / BODY / CALLER_UPDATE / TEST_EXPECTATION) | 27 | 4% |
| module region | 2 | 0% |
| new file | 44 | 6% |
| outside all | 607 | **89%** |

Against the probe's *ceiling* at the parent (78% of code hunks inside
some symbol span with perfect anchors), the actual pass reaches 4%.
The door, by the design's own table (§4.1 row 4): of the 636 non-new
hunks, **596 are in files no anchor reached (H-a)**, 11 are in a
reached file outside every hole span (H-s), 29 are covered. **20 of the
28 templates carry no structure at all** — round-1 holes
(`ANCHOR_CONFIRM`, `UNRESOLVED`) and a `FREEFORM` only — because their
only anchors are bare identifiers, which v0 holds back from the
structure pass until confirmed. The gap is anchor discovery, not span
drawing; the probe said so at the file grain (64 of 73 reachable gold
files never named in the task) and step 2 says it at the hunk grain.

**§4.2 — anchor pass, per matcher.**

| matcher | anchors | in a gold file | on a gold symbol |
|---|---|---|---|
| backtick (exact id / unique name) | 1 | 0 | 0 |
| path (file, or a directory's modules) | 3 | 2 | 0 |
| literal (backticked non-identifier or quoted; capped) | 16 | 13 | 5 |
| bare-identifier (exactly one node carries the name) | 166 | 27 | 8 |

File grain: precision 32/172 = 0.19, recall 32/147 = 0.22. Symbol
grain: precision 13/154 = 0.08, recall 13/231 = 0.06. Zero-anchor
tasks 0 of 28; 117 unresolved code-shaped terms; 8 literals dropped
over the cap. The literal matcher is the precise one (13 of 16 in a
gold file); the bare-identifier matcher is 16% precise and costs 167
`ANCHOR_CONFIRM` questions across 28 tasks, about six per task.

**§4.7 — holes per template:** median 10, min 3, max 333 (the
knowledge-only-mode unit, `27ee019`, once `hobbes-proxy` anchored its
directory: 7 of 8 hunks covered). By type over 28: ANCHOR_CONFIRM 167,
SIGNATURE 99, BODY 99, CALLER_UPDATE 211, TEST_EXPECTATION 225,
MODULE_REGION 166, COCHANGE_TOUCH 71, UNRESOLVED 27, FREEFORM 28. The
generated template for the step-1 unit `c59916f` has 134 holes to the
hand-written 53 (the literal `go-rta` also anchors `main.main`, the
dispatcher, whose callees `runExport`/`runGrade`/`write`/`splitComma`
join the interior) and covers the same 4 of 4 hunks.

**Before the cap (recorded, the first run of the batch):** the single
backticked words `calls`, `uses`, `grade`, `export` are edge-type and
subcommand names that sit in 44–156 symbol spans each; three templates
exploded (3,594 / 3,124 / 1,938 holes, write partitions of 101 / 91 /
65 files) and, by coincidence, covered 14 gold hunks — the 10% symbol
figure of that run was those. `LITERAL_MAX_NODES = 12` (a declared
guess) drops such a literal to the unresolved block with its count in
the note; the max fell to 333 and the symbol figure to the honest 4%.

**v0 rules settled in this step (each in the module docstring):**

1. A literal hit outside every symbol span (a file's doc comment, a
   Markdown file) anchors nothing — the first run had anchored a whole
   module from its package comment and dragged twelve files in.
2. A bare-identifier anchor is a round-1 question; it joins the
   structure only when confirmed (`apply_round1`).
3. A literal hit inside a test symbol is a reaching test, not interior.
4. A type an *anchored* symbol `uses`, declared in an interior file, is
   interior (the struct a flag lands in); a type's users are its
   callers (`CALLER_UPDATE` on `uses` edges), and the signature-unchanged
   prune is for functions only (step 1's reading 5).
5. Regions for interior files only; `imports` folds into `head` (the
   graph carries no import line facts).
6. A code-shaped bare token that names a file or a directory is a
   `path` anchor: a directory names the modules directly in it.
7. A backticked word is code by the task's own declaration: unbound, it
   goes to the unresolved block whatever its shape; matched by a name
   exactly one node happens to carry (`export` → `secrets.export`), it
   builds structure *and* opens an `ANCHOR_CONFIRM`.
8. Scoring uses the diff's pre-image side: the parent is the pre-image,
   so the probe's "slightly generous" caveat is gone.

**What this settles for the run.** For this unit set the orchestrator's
round 1 is load-bearing: the anchor pass alone opens the code for 8 of
28 tasks. §3.2's arm T therefore measures H-a *plus* one round of
`ANCHOR`/`ANCHOR_CONFIRM`/`UNRESOLVED` answers before any structural
fill — and §4.2's last row ("orchestrator ANCHOR fills beat H-a on
anchorless tasks") is the reading to expect first. Step 3 (the grounder
on the gold fills) does not depend on this: its input is the template
plus fills, and for the 8 anchored tasks the templates exist.

## Addendum 2026-09-04 (night) — step 3: grounder v0 on the gold diffs

**Built:** `hobbes.derive.ground` (`edits_from_fills`, `apply_edits`,
`ground`, `fills_from_diff`, the per-language reference extraction and
the exact-or-NULL resolver with its read-trace), the `hobbes ground`
subcommand, `calvin_probe.py ground` (the batch: gold → fills → ground →
rerun → `git apply --check` at the parent → post-image against the
commit) and `tests/test_ground.py` (9, on a synthetic ledger over a
temporary git repo with Go, Python and JS). Ground records under
`~/.hobbes/bench/calvin/ground/` (the commits as gold) and
`ground-rows/` (the cell's rows as gold), each with `report.txt`.

**What "gold as fills" means here.** §3.1 says the unit's gold diff is
*the commit*; the cell's 147 rows are the commit's size-bounded,
non-binary subset (`ttt.units.units_from_git`: docs, large files and a
stray ELF under `fixtures/twomod` dropped), and step 2 scored coverage
on the rows. Step 3 uses the commits, because a grounder handed half a
commit says NULL for the other half — measured below, as it should.
`fills_from_diff` attributes every change block (a `-` run with the `+`
run that replaces it; a bare `+` run is an insertion point) to the open
hole whose span holds it — BODY before CALLER_UPDATE before
TEST_EXPECTATION before MODULE_REGION; a leading or trailing insertion
belongs to the span it opens, else the span it closes — and everything
else to one `FREEFORM` entry per block; a new file is one entry at
`{1, 0}`. A symbol whose first line is in a block gets a SIGNATURE fill,
then the pruning rules run, then attribution — so a gold edit inside a
hole a rule closed is counted, not hidden.

**Exit criterion — the 28 commits (the 50 units' keys) at their parents.**

| | |
|---|---|
| identical on rerun (output hash, trace) | 28 / 28 |
| `git apply --check` at the parent | 28 / 28 |
| post-image equals the commit, every file | 28 / 28 |
| ground wall, all 28 | 8.4 s |
| call sites in the edited ranges | 3,760 |
| in-graph / gensym | 274 / 417 |
| builtin / local / expr / external / unknown-receiver | 556 / 1,072 / 345 / 638 / 155 |
| not-code files / unsupported files | 290 / 13 (3 `.rs`, 10 `.java`) |
| **NULL** | **0** → HSR **0.0000** |
| unfilled / refused | 0 / 0 |
| read-trace rows | 3,458 |

By language: Python 1,577 sites (in-graph 153, gensym 235, builtin
322, local 430, expr 211, external 147, abstained 79); Go 1,416
(105 / 145 / 224 / 409 / 90 / 441 / 2); TS/JS 464 (16 / 37 / 10 / 233 /
44 / 50 / 74). The 155 abstentions (`unknown-receiver`, C-91): 77
Python members on an imported class or a class of the file that the
class does not declare (inherited, an attribute, or wrong — v0 cannot
tell), 74 JS members on a name a repo import binds, 2 Go members on a
package-level value, 1 Python module-level value's method, 1
`self.member` the class does not declare.

**Attribution of the 1,176 change blocks.** 28 inside an open hole
(11 BODY, 1 MODULE_REGION, 5 TEST_EXPECTATION holes filled), 1,040
`FREEFORM`, 108 new files, 1 binary skipped; 94 CALLER_UPDATEs closed
by an unchanged function signature; **2 blocks inside a closed hole**
— both `19bddc9`'s `h15`, the caller `main.write` → `runGoRTA` closed
because `write`'s signature is unchanged, edited by the task for its
own reason. The rule closes the *propagation* question (I4), not the
site; the grounder takes such an edit as `FREEFORM` and the count says
how often. 1,165 edits (1,148 of them `FREEFORM`), 1,140 outside the
write partition — step 2's 89% seen from the other side, advisory in
M0 and counted per edit.

**Six grounder defects the gold run surfaced, fixed before the reading**
(the design's rule: a NULL on gold is Calvin's defect, never a finding
about the task):

1. A pure-deletion block placed one empty line instead of none — six
   post-images off by a blank line.
2. The `tsextract` helper drops a relative import it cannot resolve on
   a scratch tree, so `classify`, `terminalName`, `dependencyCoverage`
   from `../index.mjs` read NULL; the files a post-image's relative
   imports name are now copied from the parent SHA beside it.
3. JS had no builtin list (the tail view's TS/JS classes come from the
   checker): `Number`, `setInterval`, `clearInterval` read NULL. A list
   pinned the way C-32's are — Node v24.18.0's callable globals.
4. `from hobbes.derive import derive_plan` — a package `__init__`
   re-export — read NULL though the symbol exists in `changespec`;
   followed one hop (≤ 3), the trace records `re-export`.
5. `v.VERIFICATION_BASE.items()` — a member on a module-level value,
   which the Python graph does not model — read NULL; a name bound at
   module level in the module's source is an abstention.
6. A relative import inside a package `__init__` resolved from the
   parent instead of the package (the synthetic test caught it; the
   rule now mirrors `graph.py`'s `_absolute_base`).

**Poison control** — is a zero honest? For each of 25 templates with a
bare in-graph call in a fill, the call renamed at one site to a name
two characters off, and separately to `zqxFrobnicate`: 25 of 25 →
exactly one NULL, class `near-miss`; 25 of 25 → exactly one NULL,
class `invented`. Three templates had no bare in-graph call to perturb.

**The rows as gold** (the cell's 147 rows): 1,191 sites, 29 NULL (22
near-miss, 7 invented), HSR 0.19 — `rustmir.Run`, `javac.Run`,
`contain.New`, `contain.Uncontained`, `IsRefusal`, `memberName`,
`scipsource.extract_scip_java`: every one a symbol declared in a file
of the same commit that the rows omit. Identical on rerun, applies and
matches the commit on the files fed. That is I2 on a partial input,
and it is the reading to expect from an orchestrator that edits a
caller and forgets the callee.

**What this settles for the run.** The grounder is not the door: with
fills that are right it places 1,165 edits over 28 commits exactly and
binds every call site or says why not. What it cannot see is
registered (C-91): call sites only, three languages, members on values
abstained. §4.3's classes are live and the control says the zero means
zero. Step 4 is the first orchestrator spend and waits on Max's word.

## Addendum 2026-09-04 (later) — step 4: the orchestrator adapter, five units through T by hand

**Cleared by Max** ("key is in secrets should be good to continue";
"lean toward a cheaper model"). Endpoint: Anthropic's OpenAI-compatible
`https://api.anthropic.com/v1`, model `claude-sonnet-5`, key from the
`anthropic_key` line via `HOBBES_LLM_API_KEY`, `max_tokens` 16,384, no
sampling field (**Sonnet 5 rejects `temperature`**, so §3.3's greedy
decoding is *not honored* on this model — see variance below). System
prompt v0 in pass 1, v1 in pass 2. Records under
`~/.hobbes/bench/calvin/t-pass1/` and `t/` (per unit: `.t.json` with
both templates, every round's fills, the ground record and the
instruments; `.exchanges.jsonl`; `.t.diff`).

**Built:** `hobbes.derive.adapter` (`Adapter.ask` — render, one
exchange, validate, one repair; `run_t` — round 1 on a view of the
round-1 holes, rebuild, carry the answers as filled holes, round 2,
the "yes" follow-up, prune, ground, one NULL round-trip on a narrowed
template; `chunk_by_file`; `score_unresolved`), `template.apply_round1`
taking `ANCHOR` fills, `calvin_probe.py t`, eight tests on a fake
endpoint. Units: `b8afd41` (lane-B containment; round-1-only
template), `6511f40` (Go call-edge fixes; round-1-only), `d509835`
(stand up the oracle lane; Python, structure), `11e4c9d` (poison
check; Go, 20 co-change partners), `c59916f` (the hand unit).

**Pass 1 (protocol v0)** — what the design as written does:

| unit | anchors r1→r2 | holes gen/pruned/filled | edits | applies | RFE vs gold J/P/R | tokens in/out | wall |
|---|---|---|---|---|---|---|---|
| b8afd41 | 6→0 | 2/0/1 | 0 | — | 0 | 3.4k / 0.2k | 5 s |
| 6511f40 | 8→3 | 348/48/25 | 0 | — | 0 | 571k / 22k | 232 s |
| d509835 | 5→1 | 23/5/21 | 0 | — | 0 | 20k / 7.8k | 85 s |
| 11e4c9d | 11→9 | 690/75/57 | 0 | — | 0 | **1,459k** / 34k | 372 s |
| c59916f | 5→2 | 132/36/113 | 5 | yes | **1.0 / 1.0 / 1.0** | 147k / 25k | 198 s |

2.20M input tokens, 89k output — about $8 at list. Three things broke
at once. (1) **Anchorless:** `b8afd41`'s six bare-word confirmations
were all refused (rightly), the rebuilt template held a `FREEFORM`
hole and no code, and "none" was the only honest answer — an empty
diff. (2) **Module anchors:** confirming a bare word that names a
*module* (`gosource`, `grade`) makes every symbol of the module
interior; the rebuilt templates ran to 348 and 690 holes with the whole
span under every caller and test, 614k and 1.5M characters. Sonnet 5
accepted 284k- and 728k-token prompts, hit the 16k output cap on the
first reply, and on repair answered `patterns: unchanged` for every
type — 0 edits. (3) **New things:** `d509835`'s orchestrator declared
ten prose terms `new`, then answered all ten `NEW_SYMBOL` holes
`covered_by` a `FREEFORM` it answered "none". The hand unit, whose
anchors are two literals, went end to end: the flag, the field,
`Tests: !o.NoTests`, a doc comment; 0 NULL; applies; exactly the two
gold files.

**Protocol v0.1** (in the tree; the design's §2.2 amended): when round
1 leaves no anchor the rebuild opens an `ANCHOR` hole and a second
round-1 pass asks it, refusals kept across passes; every answered
round-1 hole is carried into round 2 as *filled*; a caller or test is
rendered as its signature line plus the call site, a "yes" without a
body is valid and is shown its span in round 2b; the system prompt asks
for `patterns` first and the changed holes only, and says a new file is
a `NEW_SYMBOL` with a new path; a rendered template over 300k
characters is asked in chunks by file; a reply cut at the output cap
is repaired saying so.

**Pass 2 (protocol v0.1):**

| unit | anchors r1→r2 | unresolved agree | coverage sym/reg/new/out | holes gen/pruned/filled | edits | applies | RFE vs gold J/P/R | exch | tokens in/out | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| b8afd41 | 6→0 | 3/3 | 0/0/7/41 of 48 | 9/0/1 | 0 | — | 0 | 4 | 7.9k / 0.3k | 9 s |
| 6511f40 | 8→3 | 5/5 | 4/2/3/18 of 27 | 247/16/19 | 0 | — | 0 | 3 | 282k / 18k | 198 s |
| d509835 | 5→1 | 4/10 | 0/0/19/9 of 28 | 24/2/11 | 6 | yes | 0.11 / 0.5 / 0.12 | 3 | 21k / 26k | 234 s |
| 11e4c9d | 11→1 | 1/2 | 1/0/1/27 of 29 | 46/1/1 | 0 | — | 0 | 3 | 15k / 16k | 176 s |
| c59916f | 5→3 | 2/4 | 4/0/0/0 of 4 | 135/15/36 | 4 | yes | **1.0 / 1.0 / 1.0** | 2 | 55k / 15k | 118 s |

380k input, 75k output — about $2.3. NULL 0 on every unit in both
passes (the grounder found nothing to reject in what Sonnet wrote
against the spans it was shown; HSR 0 where there were call sites to
judge). Every final document valid; two truncation repairs (`6511f40`,
`d509835`), both recovered by patterns.

**Readings, by component:**

- **The socket works where the anchors are right (G, X clean).** The
  hand unit: 2 exchanges, 118 s, 69k tokens, the gold change in
  substance, 0 NULL, applies, right files 1.0. Both passes. This is
  arm T's existence proof on a real unit.
- **H-a on an anchorless task is not closed by asking the
  orchestrator.** Asked outright which symbols or files the task
  concerns, Sonnet answered `SCIP`, `read-only`, `repo-authored` — the
  task's own words; none binds. It has nothing else to say: it does
  not know the repo (charter §3, as designed). §4.2's last row
  ("orchestrator ANCHOR fills beat H-a on anchorless tasks") reads
  **false for this model**. The `ANCHOR` hole needs candidates from
  Hobbes — nearest names per term, the planner's lexical seeds (C-36),
  a file listing — for the orchestrator to *choose* among. Step 6's
  first protocol change.
- **A module anchor is too coarse (H-s).** A confirmed bare word
  naming a module opens every symbol in it as `SIGNATURE`/`BODY`;
  §4.7's "holes ≫ hunks" row fired at 247 and 690 holes and the
  orchestrator changed nothing under it. The residual is the design's
  own: a module anchor should open its symbols as `ANCHOR_CONFIRM`
  candidates (or regions), not bodies. Chunking bounds the call count,
  not one file's size (139k tokens for `gosource.go` alone).
- **New-thing placement is the residual, as preregistered (§9, M1′).**
  With the v1 prompt `d509835` wrote six new files and placed them
  flat under `bench/oracle/` (`grade.go`, `main.go`, `rta.go`) where
  the gold nests them (`cmd/oracle/`, `internal/gorta/`,
  `internal/grade/`): right files 3 of 6 (`README.md`, `go.mod`,
  `run-cell.sh`), applies, 0 NULL. Name and body the orchestrator
  has; *where* it does not.
- **`UNRESOLVED` classification over-declares `new`** for prose:
  `README`, `bench/oracle`, `go-rta`, `grade`, `oracle` all `new` on
  `d509835` (gold rule: not-code); 15 of 24 terms agree over the five.
  The gold rule (`unresolved_truth`: `new` if the diff declares it as
  a symbol, `refers` if it names a symbol in a touched file, else
  not-code) is itself approximate — `no-tests` is a flag string the
  diff does declare, classed not-code by the rule — so the agreement
  number is a floor.
- **Variance without greedy decoding.** `11e4c9d` confirmed 9 anchors
  in pass 1 and 1 in pass 2 from the same prompt; the design's "one
  run per (unit, arm)" then measures the model's sampling as much as
  the unit. For step 6 either a model that honors temperature 0 or
  repeated runs per unit.
- **The cell's impact sets are the wrong denominator for RFE.** The
  cell units' `paths` for `c59916f` are `web/src/lib/graphModel.ts`
  and its test — the release-SHA lexical mapping (C-55/C-84), nothing
  the commit touched — so RFE against the impact set reads 0 on a
  unit whose diff is exactly right. §4.5's RFE is reported against the
  gold files at the parent; the cell's mapping is a defect for its own
  register (D-6).
- **Cost shape.** Round 1 is cheap (2–3k tokens); round 2 costs what
  the structure pass opens: 55k tokens for the 135-hole hand unit, 140k
  for one exploded file. Sonnet 5 at list: the five units cost $2.3 in
  pass 2; a 50-unit, three-arm run at this shape is order $50–100
  before the module-anchor fix and less after. Haiku 4.5 would be a
  third of that; whether it fills as well is a step-6 question.

**Exit criterion:** met — five units through T against one endpoint,
fills validated (two repairs, every final document valid), every
exchange recorded (15 in pass 2, request and response in full), the
`UNRESOLVED` round answered on all five. Step 5 (the local harness:
Podman exec, policy, testmap for T and O) is next and needs no
orchestrator; step 6 waits on Max and on the two protocol changes above.

