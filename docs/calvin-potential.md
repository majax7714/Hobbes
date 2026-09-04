# Calvin potential — M0, the shape of the residual before Calvin exists

**Status:** proposed → ready (2026-09-04) — no run cleared; steps 0–3 of §8 spend no orchestrator calls · **Type:** pipeline experiment (preregistered readings, attribution-first) · **Compute:** orchestrator via a remote OpenAI-compatible endpoint; exec local under Podman. No Modal in M0.
**Depends on:** the Python derive package (graph @ SHA, tiers, plan derivation, impact, write partitions, testmap, co-change), the owned agent loop (`pipeline/src/hobbes/agent/loop.py`, OpenAI-compatible chat completions), the local policy engine + Podman sandbox, and the 50 derived units and 28 proposals of ADR-099 §9b (`bench/ttt/proposals-hobbes-ebdf7a5.jsonl`; the cell record `ttt-cells/hobbes-olmo3-7b-2026-09-03-review.md`).
**Supersedes:** v1 of this document. Changes are marked **[v2]** and listed in §11.
**Charter:** [`calvin-charter.md`](calvin-charter.md) — unchanged; this document is the first experiment under it.
**Pre-run probes:** [`ttt-cells/calvin-m0-probe-2026-09-03.md`](ttt-cells/calvin-m0-probe-2026-09-03.md) — the two no-orchestrator instruments run at the base graph and at each unit's parent, the v1 assessment (V-1–V-8) that produced this v2, and the 28 parent SHAs; `pipeline/scripts/calvin_probe.py` reproduces every number.
**ADR:** none yet. When Max moves this from *ready* to *accepted* it takes the next number (100) in ADR-099's pattern, this doc as its body.

> **Where v1 lives (2026-09-04).** v1 was never a document in this
> tree; it was assessed and probed in a session of 2026-09-03 (night)
> and its findings became this v2. The probe record above carries the
> numbers §0 quotes, reproduced from the in-tree script on 2026-09-04;
> the v1 text and the parent graphs are preserved outside the tree
> under `~/.hobbes/bench/calvin/`. The charter's own companion-doc line
> still names `calvin-m0-socket.md`, the v1 title.

**Terms used below.** *HSR* — hallucinated-symbol rate, references to symbols not in the graph over all symbol references (`olmo3-ttt-validation.md` §4). *RFE* — right-files-edited: Jaccard between the files an agent modified and the unit's impact set, with precision and recall reported beside it (same section; precision is a harness check, ADR-077). *NULL* — a fill identifier the grounder could not resolve exactly against the graph at the parent SHA. *Gensym* — a symbol the diff itself declares earlier, resolvable within the same diff. *Hole* — a slot in the template the orchestrator fills; *fill* — its content. *Hunk* — one contiguous change block of the gold diff.

---

## 0. What M0 is for

Calvin (charter §1) grounds an orchestrator's intended change against the repo at a SHA. Its scope is a residual: whatever structure cannot derive and the orchestrator cannot ground. M0 measures the shape of that residual before Calvin exists, by running the pipeline with Calvin's slot filled by a deterministic stub. The assumption under test:

> Most of a real task is structure Hobbes can derive deterministically from anchors in the task, and the orchestrator's fills into that structure are noisy in ways a grounder can catch.

**[v2]** Two pre-run measurements already shape the design (the probe record; lane A at each unit's parent, 50 units, 680 hunks). First, on the §9b units **18% of code hunks fall outside every symbol span** (103 of 585) — module-level code the structure pass did not cover. That is the largest H-s residual and it is cheap to close (§2.1, `MODULE_REGION`). Second, at the anchor stage **118 of 182 unresolved terms are symbols the diff creates**, not near-misses of symbols that exist. If that holds through the fill stage, the dominant residual is new-thing placement, not fuzzy matching, and the door order in §9 is stated accordingly now rather than after. The same probes are why units are re-based at the parent (§3.1): at the release SHA, 56% of hunks fall in files the graph lacks; at the parent, 4% of code hunks do, and all of those are files the commit itself creates.

---

## 1. Principle: attribution before verdict

Unchanged from v1. **No kill criteria for Calvin.** Every instrument carries an attribution table; every unit gets a row with attribution before any aggregate is written. Components:

| id | component | owns |
|---|---|---|
| **H-a** | Hobbes anchor pass | finding what in the task names repo structure; classifying what it cannot find |
| **H-s** | Hobbes structure pass | expanding anchors into holes: symbol spans, **[v2]** module regions, callers, tests, partners, impact |
| **O** | orchestrator fill | the content of holes; anchor naming when H-a finds nothing; **[v2]** classifying unresolved terms |
| **G** | grounder v0 (the stub) | resolving fills to symbols or NULL, placing them in spans |
| **X** | harness / sandbox / policy | exec, tests, containment, the adapter, tool-call parsing |
| **U** | the unit set | what these tasks are shaped like at their parent commit |

The only stops are harness defects (X), where continuing produces numbers about the wrong thing — the ADR-085 precedent, and §9b's own.

---

## 2. Components

### 2.1 `hobbes template` — Python, in the derive package [v2]

Python, not Go: everything M0 calls — graph load, tiers, plan's expansion, impact, write partitions, testmap, co-change — lives in the Python derive package (`pipeline/src/hobbes/derive/`). Go holds the six read-only knowledge tools and nothing that derives; a Go template generator would mean reimplementing derivation. The template is still a derived artifact: keyed `(parent_sha, task_hash, template_version)`, regenerable, hashed.

**Input:** task text, repo, parent SHA (§3). **Output:** `template.json`.

**Anchor pass (H-a).** Match task text against the graph at the parent SHA, in order, recording the matcher:

1. fenced / backticked identifiers → exact node id or basename
2. file paths → exact, then `/`-boundary suffix
3. test ids (`path::name`) → testmap
4. stack-trace lines → `file:line` inside a known span
5. error strings → literal search in source at the SHA
6. bare identifiers matching exactly one node name

**[v2] Unresolved terms are an output, not a failure.** Every identifier-shaped token in the task that matches nothing is emitted in an `UNRESOLVED` block with its nearest graph names by edit distance (recorded, not used). The pre-run probe says most of these are names the change will create. The template cannot know that without the gold diff, so the first fill asks the orchestrator to classify each unresolved term:

| class | meaning | effect on the template |
|---|---|---|
| `new` | the change creates this | opens a `NEW_SYMBOL` hole |
| `refers` | this is an existing symbol under another name | opens an `ANCHOR_CONFIRM` hole with the candidates |
| `not-code` | prose, not an identifier | dropped |

Zero resolved anchors and zero unresolved terms → a single `ANCHOR` hole; the orchestrator names symbols and files; H-s runs on those.

**Structure pass (H-s).** For each resolved anchor: definition span, write partition, callers and callees with tier, tests via testmap, co-change partners, impact frontier under the policy hop limit, lane-B types where present.

**[v2] Module-level span rule.** For every file the structure pass touches (definition files, caller files, co-change partners), emit `MODULE_REGION` holes for the code that is not inside any symbol span: the import block, and each gap between consecutive symbol spans, plus head and tail. Each region is one hole with span `file:line-line`, kind `imports | gap | head | tail`, and the symbols it sits between as provenance. A hunk that falls in a gap maps to the gap's hole. Expected to lift coverage by most of the 18%; measured in §4.1.

**Hole language v0.**

| type | asks for | fill schema |
|---|---|---|
| `ANCHOR` | which symbols/files this concerns | names |
| `ANCHOR_CONFIRM` | is this the right site / the right existing symbol | yes/no, alternative |
| `UNRESOLVED` **[v2]** | classify these terms | `{term: new / refers / not-code}` |
| `SIGNATURE` | new signature or unchanged | signature or `unchanged` |
| `BODY` | code for this symbol span | code |
| `MODULE_REGION` **[v2]** | code for this module-level region, if any | code or `unchanged` |
| `CALLER_UPDATE` | does this caller change; how | `{decision, reason, body?}` |
| `TEST_EXPECTATION` | what this test should now expect | prose + optional code |
| `COCHANGE_TOUCH` | is this partner touched; why | `{decision, reason, body?}` |
| `NEW_SYMBOL` | name, file, position, body for something the graph lacks | `{name, file, after_symbol? / region?, body}` — or **[step 1]** `{covered_by: [hole ids]}` when the new thing is a field or a local inside another hole's fill |
| `FREEFORM` | anything the template did not anticipate | code + target span — or **[step 1]** `"none"` |

Every hole: `id`, `type`, `span` (or null), `constraints` (write partition, type if known), `provenance` (anchor, edge, tier; for regions, the bracketing symbols), `fill_schema`.

**v0 rules the generator holds (step 2, the probe record's third addendum):** a literal hit outside every symbol span anchors nothing; a literal in more than `LITERAL_MAX_NODES` (12) symbols is too common and goes to the unresolved block with its count; a bare-identifier anchor builds structure only once confirmed; a literal inside a test symbol is a reaching test; a type an anchored symbol uses in an interior file is interior, and a type's users are its callers; regions for interior files only, `imports` folded into `head`; a code-shaped token naming a directory anchors the modules directly in it; an unbound backticked word is unresolved whatever its shape.

**Pruning rules v0** (structural, after fills, before grounding): `SIGNATURE = unchanged` closes that anchor's `CALLER_UPDATE`s — **[step 1] for function signatures only**: a type's callers change when its fields do, and the hand-written unit's gold leaves `type Options` signature-unchanged while its one caller changes; a caller outside the write partition is closed with reason `partition`; `MODULE_REGION = unchanged` is dropped from the diff. Pattern fills accepted (`CALLER_UPDATE: all unchanged`) and expanded by Hobbes — **[step 1]** also for `MODULE_REGION`, `TEST_EXPECTATION` and `COCHANGE_TOUCH`, since a two-file template carries 18 regions, 9 test expectations and 7 partners for 4 hunks (the probe record's step-1 addendum). The schema is `hobbes.derive.holes` (v0), the hand-written template `bench/calvin/templates/c59916fe2222.template.{json,md}` with its gold fills beside it.

### 2.2 Orchestrator adapter — Python, new [v2]

Pier is not installed and the owned loop speaks OpenAI-compatible chat completions only, so the adapter is written for that surface and nothing else: one endpoint URL, one model id, one versioned system prompt, JSON-schema-validated fills. Claude runs through a compatible gateway; Codex or an OpenAI model runs natively. Whichever is chosen is held constant for the run and recorded with date.

The adapter: renders the template to the prompt, receives fills, validates each against its hole's `fill_schema`, returns malformed fills once for repair, records every exchange (request, response, latency, tokens). It supports exactly one loop: the grounder's NULL list becomes a second, narrower template.

**[step 4]** Built as `hobbes.derive.adapter` (`run_t`, `calvin_probe.py t`), on the owned loop's `Endpoint`. Run against `claude-sonnet-5` through Anthropic's OpenAI-compatible endpoint (Max: a cheaper model than the frontier tier; the key line `anthropic_key`). Sonnet 5 rejects the `temperature` field, so §3.3's "temperature 0 where the endpoint honors it" reads *not honored*: the same prompt confirmed 9 anchors in one pass and 1 in the next. Protocol v0.1, from the first pass (the probe record's fifth addendum): round 1 asks only the round-1 holes on a view; when it leaves no anchor the rebuild opens an `ANCHOR` hole and a second round-1 pass asks it; every answered round-1 hole is carried into the round-2 template as *filled*; a caller or test is rendered as its signature line and call site, a "yes" without a body is valid and fetches its span in a follow-up (round 2b); the system prompt (v1) asks for `patterns` first and only the changed holes under `fills`; a rendered template over a declared budget (300k chars) is asked in chunks by file; a reply cut at the output cap is repaired with that said. What the two passes measured is in the record; the two readings that go to step 6 are the anchorless task (the orchestrator, asked which symbols the task concerns, echoes the task's prose — H-a needs Hobbes-side candidates in the `ANCHOR` hole) and the module anchor (a confirmed bare word naming a module opens every symbol of the module as a body hole: 247 and 690 holes, 140k-token chunks, and an orchestrator that then changes nothing — §4.7's "holes ≫ hunks" row, H-s).

### 2.3 Grounder v0 — Python, in the derive package [v2]

Calvin's slot with the residual set to zero. Deterministic; no model.

- Lane-A tokenization of each fill; every identifier resolved against the graph at the parent SHA plus gensyms declared earlier in the same diff. **Exact match or NULL.** No fuzzy matching, no basename fallback: v0 measures how often exactness fails, which is the residual.
- Placement: `BODY` and `MODULE_REGION` fills replace or insert within their span; `NEW_SYMBOL` fills go after `after_symbol` if given, else into the named region, else end of file — record which.
- Output: diff, NULL list (fill, term, nearest graph names — recorded, not used, and **[v2]** the NULL's class as the orchestrator declared it, if it was an `UNRESOLVED` term), read-trace.
- HSR on the diff is zero by construction; measured anyway (§4.6).

**[step 3]** Built as `hobbes.derive.ground` (`hobbes ground`). What "identifier" means in v0, settled by the gold run: the **call sites** lane A's providers extract from the post-image (tree-sitter for Python and Go; the `tsextract` helper for TS/JS on a scratch tree carrying the files its relative imports name), resolved in the edited ranges only. What is *not* a NULL is exactly what lane A itself does not resolve to a symbol and says so — a builtin (the tail view's pinned lists; a JS list pinned for the grounder, Node v24.18.0's callable globals), a local binding in scope (ADR-046), a method on a local or expression receiver (C-63/C-80), a name reached through an import that is not a repo module (external), a member on a package-level value — each its own class in the record, so HSR's denominator (in-graph + NULL) is legible. Two exact rules the gold diffs forced: a from-import that a package `__init__` re-exports is followed one hop (≤ 3) to the declaring module, and a member on a module-level value (`v.VERIFICATION_BASE.items()`) is an abstention, not a NULL. Each NULL is classed by §4.3's rule: `new` when a fill declared it, `near-miss` when the exact name exists in another module or a graph name is within edit distance 3, else `invented`. Rust and Java fills are placed but not grounded; type references, decorators and composite literals are not call sites (C-91). A `FREEFORM` fill may be a list — one `{code, span}` per change block, which is how a raw diff is handed in (charter §4.1) — and a span with `end = start − 1` is an insertion point (`{1, 0}` on an absent path creates the file). Placement refuses overlap; an open hole with no fill is reported `unfilled` (I4). The pruning rules run before placement; a fill for a closed hole is ignored and reported. The record is `(diff, edits with placement, every reference with its class, NULL list, gensyms, read-trace, output hash)`, keyed `(parent_sha, task_hash, template_version, grounder_version)`.

### 2.4 Sandbox — local, Podman [v2]

No Modal sandbox with policy exists, and writing the ADR to carry the policy engine into a Modal image is a separate piece of work that M0 does not wait on. Exec runs on the box under Podman with the existing policy engine below the model, containment stamp checked, tests from the testmap. The orchestrator is the only remote call in the pipeline.

---

## 3. The run

### 3.1 Units, re-based at the parent [v2]

Each unit's ledger is the graph at its commit's **parent**, and its gold diff is the commit. Without this, coverage measures C-84 (files the release-SHA graph lacked because they were created later in history) instead of the residual. With it, files created before the commit are in the graph; only files the commit itself creates remain outside, and those are exactly the `NEW_SYMBOL` class the probe already flagged.

Cost: one ingest per distinct parent. Units sharing a parent share an ingest; cache by SHA. Report ingest count and wall-clock.

- **This repo:** the 50 derived units from §9b, each re-derived at its parent. Templates, coverage, and all instruments are computed there.
- **fastapi:** two DeepSWE units. **[v2]** That is a smoke test, not a set, and it is reported as one — a per-unit row each, no aggregate, no bootstrap, no claim. Growing it (history hunks at parent, as the NLL units were made, with `plan` deriving units from commit message + touched files as anchors) is a follow-up if this repo's numbers make a second repo worth the ingest cost.

### 3.2 Arms

Same orchestrator model in every arm.

| arm | what runs |
|---|---|
| **O** | orchestrator alone with the ADR-077 manifest, run on the same local harness with exec |
| **T** | template → fills → grounder v0 → local sandbox. One pass |
| **T-loop** | T plus one NULL round-trip |

### 3.3 Held constant

Model, endpoint, system prompt, sandbox, policy, testmap, parent SHA per unit, unit set. Temperature 0 where the endpoint honors it. One run per (unit, arm); variance is across units.

### 3.4 Cost

Orchestrator API only, plus local box time. Roughly 50 units × 3 arms × a few calls. Stated before any run per the standing policy; the run itself waits on Max's word.

---

## 4. Instruments, with attribution

Per unit, aggregated with paired bootstrap over units (5,000 resamples, seed 0) on this repo only; fastapi rows reported raw. Scorer versions as ADR-099 unless noted (the v2 reference extractor of the review record's D-3).

### 4.1 Template coverage — H-a, H-s, U

Fraction of gold-diff hunks whose lines fall inside a template span. **[v2]** Reported in four buckets: *symbol span*, *module region*, *new file* (the commit creates the file → coverable only by `NEW_SYMBOL`), *outside all*.

| result shape | implicates | check before believing | residual |
|---|---|---|---|
| module-region bucket absorbs most of the former 18% | H-s rule works | confirm the remaining *outside all* is < 5% | none; rule stays |
| *outside all* remains large | H-s | what is the code — decorators? nested defs? multi-symbol spans? | span rule gap; fix, not residual |
| *new file* is large | U, and the probe's finding | count files the commit creates vs. files the parent graph lacks for other reasons | new-thing placement residual in that proportion — Calvin's planner (M1′) |
| uncovered hunks are in files no anchor reached | H-a | which matcher would have caught it | matcher gap |
| high across buckets | — | check units are not trivial (single-hunk) | the socket fits |

### 4.2 Anchor precision and recall; unresolved-term classification — H-a, O [v2]

Anchors found vs. symbols the gold diff touches, per matcher. Plus, for the `UNRESOLVED` block: the orchestrator's class for each term vs. the truth from the gold diff (`new` if the diff declares it; `refers` if it resolves to a symbol the diff touches; else `not-code`).

| result shape | implicates | check | residual |
|---|---|---|---|
| high precision, low recall | H-a | which matcher | matcher gap |
| low precision on near-exact matches | H-a or U | inspect alternatives | fuzzy-name residual if ambiguity is real |
| unresolved terms are mostly `new` and the orchestrator classifies them correctly | U shape confirmed; O can name what it creates | does the `NEW_SYMBOL` fill then land in the right file/region? (§4.3 `new` class) | placement, not naming, is the residual |
| orchestrator misclassifies `new` as `refers` (or vice versa) | O | is the candidate list misleading it? | protocol: candidates for `refers` should carry structure (module, arity), not just edit distance — a Calvin job |
| orchestrator `ANCHOR` fills beat H-a on anchorless tasks | O | how often H-a found nothing vs. wrong | anchor pass may belong to O for prose-heavy tasks; H-s still runs on O's anchors |

### 4.3 NULL rate by hole type and class — O, G, U

For every fill: identifiers total / resolved / NULL, by hole type. Each NULL classed: *near-miss* (edit distance ≤ 3 or same basename elsewhere), *sibling* (same module, matching arity), *new* (declared new, or should have been), *stale* (existed at another SHA), *invented*.

| result shape | implicates | check | residual |
|---|---|---|---|
| **[v2]** `new` dominates, consistent with the anchor-stage probe | U shape; O knows what it creates but not where | for each: did the `NEW_SYMBOL` fill name a file and region? did the region exist? did tests reach the placed code? | new-thing placement is the residual. **M1′ before M1.** |
| near-miss / sibling dominate | O noise a grounder can catch | are they closable by a rule (case, basename)? | what remains after rules is the fuzzy-match residual — M1 |
| stale dominates | O memorized another version | cross with the memorization probe (ADR-099 §6) | contamination made visible per fill; not Calvin's |
| invented dominates | O | does arm O do this too (HSR)? | stays NULL; orchestrator's to fix |
| near zero | O clean here | fastapi smoke rows agree? | pointer decoder is most of Calvin |

### 4.4 T-loop minus T — O, G

NULLs closed after one round-trip, by class.

| result shape | implicates | check | residual |
|---|---|---|---|
| near-miss NULLs close | O self-corrects given an exact report | nearest name or right name? | fuzzy residual shrinks to what O gets wrong even when told |
| `new` NULLs close by the orchestrator naming a file and region in the loop | O can place when asked directly | is the placement the same as gold's? in-partition? | if placement matches gold often, M1′ may be a protocol (ask earlier) more than a model |
| NULLs close by defining symbols in the wrong place | O routing around | count; check partitions | NULL must be blocking at policy; register |
| NULLs do not close | O cannot resolve from the report | what did the report lack | candidate ranking by structure — Calvin |

### 4.5 Solve rate and RFE — X, then everything

Behaviour verifier; RFE J/P/R against the unit's impact set at the parent.

| result shape | implicates | check | residual |
|---|---|---|---|
| T < O | first X | §9b's five defects (D-1 no exec, D-2 tool-call parsing, D-3 the extractor, D-4 the denominator, D-5 shared runs) — any live? does the diff apply? | only after X is clean: compare per unit, which hole type was wrong |
| T ≈ O | U or H-s | split by files-touched | inversion helps on multi-file or not at all |
| T > O on RFE, not solve | G or O | look at `BODY` / `MODULE_REGION` fills | placement or body residual |
| T > O on both | — | O also ran with exec? | proceed |

RFE precision in T ≥ manifest precision by construction; lower is a G bug.

### 4.6 HSR in T — G

Must be zero. Nonzero: fix and rerun; do not report.

### 4.7 Holes per task, round-trips, tokens — H-s, O

Holes generated / after pruning / filled / pattern-filled; tokens and wall-clock T vs O. **[v2]** `MODULE_REGION` counted separately so its cost is visible.

| result shape | implicates | check | residual |
|---|---|---|---|
| holes ≫ hunks | H-s | which type inflates; regions on untouched files? | prune regions to files with at least one other hole; pattern fills |
| T tokens > O with no gain | H-s | split by files-touched | short-circuit single-file units to arm O |

### 4.8 Read-trace utility — G, reviewer

Recorded, not scored. Ten units by hand: does the trace show callers read before a signature change? Note if v0's fixed order makes it trivial.

---

## 5. Per-task record

One row per unit per arm in `ttt-cells/calvin-m0-<repo>-<date>.md`:

```
unit | parent_sha | arm | anchors (found/gold, matcher) | unresolved (n, class agreement) |
coverage (symbol/region/newfile/outside) | holes (gen/pruned/filled) |
NULLs (n, by class) | loop-closed (by class) | applies? | tests pass? | RFE J/P/R | HSR |
attribution: {H-a, H-s, O, G, X, U} → one line each, or "clean"
```

Attribution is filled per unit **before** any aggregate is written.

---

## 6. What M0 emits

Per unit in T: `(template, fills, grounded diff, NULL list with classes, read-trace, sandbox verdict)`, keyed `(parent_sha, task_hash, template_version, model_id)`. Every field has deterministic ground truth except the fills, and the fills are labeled by what the grounder and sandbox did with them. **[v2]** With the parent re-base, the `new` class in these tuples has gold placement — the commit shows where the new symbol actually went. That is M1′'s training signal, produced for free.

---

## 7. Constraints to open on acceptance

Each becomes a `C-n` in `constraints/verification-benchmark-harness.md` in the commit that moves this document to *accepted* (P8); listed here so the register entry is written from the design, not reconstructed after.

1. **Per-parent ingest cost.** One graph per distinct parent commit. Cached by SHA; count reported. If ingest dominates wall-clock, that is a Hobbes cost to register, not an M0 finding. Measured on this repo: 28 contained ingests in 698 s, median 24 s (the probe record's addendum).
2. **Exact-match grounding is deliberately worse than product.** No basename fallback, so NULL measures orchestrator noise. Rules are M1's first content.
3. **One orchestrator, one endpoint shape.** OpenAI-compatible only; Claude via gateway. The NULL distribution may be model-specific; a second model is a follow-up.
4. **Local sandbox only.** The policy engine runs on the box. Carrying it into a Modal image is its own ADR; M0 does not depend on it.
5. **fastapi is a smoke test.** Two units, raw rows, no aggregate.
6. **Lane-A-only languages excluded**, as in ADR-099.
7. **NULL is advisory in M0**, so §4.4 can measure routing-around. Blocking at policy is a design change recorded after measurement.
8. **Module regions are coarse.** A gap between two symbols is one hole even if it holds three unrelated statements. Finer regions are a v1 rule if coverage or placement says so.

---

## 8. Order of work

Step-gated, as ADR-099's was. Steps 0–3 produce instruments with no orchestrator involved: coverage, anchor recall, and the grounder's correctness on gold are known before the first API call. Steps 0–2 and the §4.1/§4.2 readings, ceiling and actual, are in hand (the probe record); the anchor rows there are a floor, since the resolver probed lacks the test-id, stack-trace and error-string matchers step 2 adds.

0. **Parent re-base.** For each of the 50 units: parent SHA, ingest at parent (cached), gold diff = commit. *Exit:* 50 `(parent_sha, gold diff)` pairs; ingest count and time recorded. **Done (the probe record and its 2026-09-04 addendum):** the 28 parents are named; a contained lane-B graph exists for each (`calvin_probe.py ingest --lane-b`, 28 ingests, 698 s, median 24 s, 176,796 of 176,824 symbol edges semantic); both no-orchestrator instruments computed on the lane-A graphs and re-run identical on the semantic ones. The ledger step 3 grounds against is the semantic one (charter §6).
1. **Hole schema** incl. `UNRESOLVED` and `MODULE_REGION`. *Exit:* one hand-written template for a §9b unit that a reader can fill without instructions. **Done 2026-09-04:** `hobbes.derive.holes` (v0) and the template for `c59916fe2222` at its parent — 53 holes, every type but `ANCHOR`, the fillable render, and the gold diff as fills validating with nothing missing (`tests/test_holes.py`); five readings for step 2 in the probe record's addendum, three of them amendments to §2.1 above.
2. **`hobbes template` in derive:** anchor pass with unresolved block, structure pass with module regions, pruning. *Exit:* templates for all 50 regenerate byte-identically at the parent; anchor P/R and coverage buckets (§4.1, §4.2) computed against gold before any orchestrator call. **Done 2026-09-04:** `hobbes.derive.template` + `hobbes template`; 28 of 28 (the 50 units share 28 keys) byte-identical; **actual coverage before any orchestrator round: symbol 4%, region 0%, new file 6%, outside 89% — 596 of the 636 non-new hunks are in files no anchor reached (H-a), 11 H-s; 20 of 28 templates carry no structure until round 1.** Anchors at file grain 0.19 / 0.22; the literal matcher precise (13/16), the bare-identifier matcher 16% and six `ANCHOR_CONFIRM`s per task. Eight v0 rules and the literal cap (`LITERAL_MAX_NODES = 12`) in the probe record's third addendum.
3. **Grounder v0 in derive.** *Exit:* the 50 gold diffs fed in as fills → HSR = 0, NULL = 0 except terms the diff declares (which must resolve as gensyms), diffs re-apply cleanly at the parent. **Done 2026-09-04 (night):** `hobbes.derive.ground` + `hobbes ground` + `calvin_probe.py ground`; the 28 commits (the 50 units' gold, §3.1: *the commit*) expressed as fills by `fills_from_diff` and grounded at the parent — **28 of 28 identical on rerun, 28 of 28 apply, 28 of 28 post-images equal the commit byte for byte; 3,760 call sites in the edited ranges, 274 in-graph, 417 gensyms, 0 NULL, HSR 0.** Six grounder defects surfaced by the gold run and fixed before the reading (the rule: a NULL on gold is Calvin's defect) and a poison control (25 near-miss and 25 invented perturbations → exactly one NULL each, right class) in the probe record's fourth addendum. On the cell's size-bounded rows instead of the commits, 29 NULLs — every one a symbol in a file the rows omit — which is I2 doing its job on a partial diff.
4. **Orchestrator adapter.** *Exit:* five units through T by hand against the chosen endpoint; fills validated; exchanges recorded; the `UNRESOLVED` classification round works. **Done 2026-09-04 (Max's word; `claude-sonnet-5`):** five units, two passes (protocol v0 then v0.1), every exchange recorded, every final document valid (two truncation repairs), the `UNRESOLVED` round answered on all five (15 of 24 terms agree with the gold rule; the orchestrator over-declares `new` for prose). The hand unit went end to end in both passes: the gold change in substance, 4 edits, applies at the parent, exactly the two gold files, 0 NULL — 2 exchanges, 69k tokens, 2 minutes. The other four did not: an anchorless task, a module-anchor explosion, and new-file placement flat where the gold nests (§9's M1′ residual, as preregistered). Cost: pass 1 2.20M input tokens (≈ $8 at list — the module explosion), pass 2 380k (≈ $2.3). Per-unit rows and readings in the record's fifth addendum.
5. **Local harness wiring.** Podman exec + policy + testmap for T and O. *Exit:* §9b's five defects checked off or re-registered; O reruns with exec on the same box.
6. **Full run, three arms, this repo; fastapi smoke rows.** *Exit:* per-task rows complete with attribution before any aggregate.
7. **Write-up** into §10 here and `benchmark-hypotheses.md`, readings per §4.

Step 4 is the first orchestrator spend and step 6 the run; neither starts without Max's word (standing policy).

---

## 9. What follows, as the results point [v2 — order changed]

Preregistered now, because the anchor-stage probe already leans one way:

- **If `new` dominates the fill-stage NULLs** (as 118/182 suggests it will) → **M1′ first: the placement planner.** Given a `NEW_SYMBOL` fill with a name and a body, choose file and region using module shape — the generalization the 3,000-step adapter showed on never-seen symbols (`olmo3-ttt-results.md` §9) and the manifest cannot supply. Trained on §6 tuples, which now carry gold placement. Measured against the `new`-class NULL rate and against placement-matches-gold.
- **If near-miss/sibling dominate and don't close in the loop** → **M1:** grounder + a ranker over graph-neighborhood candidates.
- **If `new` NULLs close in the loop with placement matching gold** → the planner is a protocol change (ask for placement in the first fill) before it is a model; do that first and re-measure.
- **`BODY` fills ground but tests fail on placement within span** → **M2:** pointer decoder with gensym binding.
- **Everything grounds, T > O** → the socket is the product for now.
- **M3** (the split machine) only if M2's remaining errors are parametric priors overriding the ledger. M0 cannot see that.

---

## 10. Results

*(appended when they land — per-unit rows first, then aggregates)*

---

## 11. Changes from v1

Each item answers a finding of the 2026-09-03 assessment, V-1–V-8 in the probe record.

1. Template and grounder in Python (derive package); Go reserved for the read-only tools.
2. Units re-based at the commit's parent; C-84 becomes the *new file* coverage bucket rather than the whole measurement.
3. Local Podman sandbox; no Modal in M0; Modal-policy ADR deferred.
4. Orchestrator adapter written new for OpenAI-compatible chat completions; Pier not assumed.
5. `MODULE_REGION` holes added to the structure pass for the 18% of hunks outside symbol spans.
6. `UNRESOLVED` block and classification round added to the anchor pass; new-name class tracked from anchor stage through fill stage.
7. fastapi reported as a smoke test (two units), not a replication set.
8. Door order preregistered: M1′ (placement planner) before M1 (ranker) if the `new` class dominates through the fill stage.
