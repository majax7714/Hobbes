# TTT cell — Hobbes @ `ebdf7a5` · Olmo-3-7B-Instruct · the review follow-ups (2026-09-03, second record)

**Experiment:** ADR-099, `docs/olmo3-ttt-validation.md`; the ten
follow-ups Max set after reading the first record, preregistered in
`benchmark-hypotheses.md` § Follow-ups **before** any of them ran.
**Sits beside** `hobbes-olmo3-7b-2026-09-03.md`, which is not edited:
every number there stands under the scorer and the reporting it names;
this record carries the re-scored, re-split and newly measured numbers
with their versions. **Every arm is *model + prompt* under P12.**
Numbers are recorded; the reading is in the hypotheses doc and
`olmo3-ttt-results.md` §10.

Setup, corpus, adapter and units are the first record's unless a row
says otherwise. Units file `hobbes-cond.jsonl` (147 units, the
`message` prompts byte-identical to the first run's, plus the `none`,
`subject` and `task` chats); the 28 hand-written task proposals are
`bench/ttt/proposals-hobbes-ebdf7a5.jsonl`.

## Item 1 — A2's NLL gain by C-84 population (lookup; `report-olmo-hobbes-split.json`, `scripts/ttt_report.py --arm/--compare`)

Mean per-token NLL, paired by unit, seeded bootstrap (5,000). C = the
shuffled-answers control adapter; A2_100 = the 100-step adapter.

| comparison | all (147) | context-known (55) | no-known-file (92) |
|---|---|---|---|
| A2−A0 | −0.2964 [−0.3153, −0.2782] 147/147 | −0.3679 [−0.3952, −0.3405] 55/55 | −0.2537 [−0.2759, −0.2333] 92/92 |
| C−A0 | −0.2184 [−0.2400, −0.1976] 143/147 | −0.3048 [−0.3355, −0.2750] 55/55 | −0.1667 [−0.1912, −0.1435] 88/92 |
| **A2−C** (true − control) | −0.0781 [−0.0863, −0.0702] 140/147 | −0.0630 [−0.0756, −0.0507] 50/55 | **−0.0870** [−0.0973, −0.0768] 90/92 |
| A3−A2 | +0.0006 p 0.72 | −0.0027 p 0.35 | +0.0025 p 0.11 |
| A1−A0 | +0.0017 p 0.56 | −0.0090 p 0.038 | +0.0080 p 0.011 |
| A2_100−A0 | −0.3015 147/147 | −0.3420 55/55 | −0.2772 92/92 |
| A2−A2_100 (300 vs 100) | +0.0051 p 0.13 | −0.0259 p <0.0002 (38/55) | +0.0236 p <0.0002 (20/92) |

fastapi (`report-olmo-fastapi-split.json`, 68 units: 63 known, 5 new):
A2−A0 −0.2226 (68/68) / −0.2156 (63/63) / −0.3108 (5/5); A1−A0 and
A3−A2 null in every population.

None of the three preregistered shapes: A2−A0 on new-file units
(−0.254) is not the control's (−0.167); the true adapter's margin over
the control is *larger* on files the graph holds nothing about (−0.087)
than on files it knows (−0.063); and every adapter gains more on known
files than new. So the true−control margin is not "the graph being
right about this unit's file" — on 92 units there is nothing for it to
be right about — and −0.218 is not a clean vocabulary estimate: a
deranged corpus trains a worse adapter than a coherent one, on files
neither has seen. Registered as C-86. One thing not preregistered: 300
vs 100 steps splits by population — 300 is better on known files and
worse on new ones, net zero.

## Item 2 — the NLL conditioning

**(a) What the first run scored, stated.** System: "You are a
single-use software engineer working in hobbes at commit `<sha12>`."
User: `## Task`, the commit's subject line, a blank line, the commit
body up to 1,200 characters (trailers stripped), a blank line, "In
`<path>`.", then (A1/A3 only) the "What Hobbes can see / cannot
confirm" block, then "Write the unified diff that implements the task.
Output only the diff." Assistant: the gold diff — the only tokens the
loss reads. That is a **message** conditioning (commit subject + body +
target path), not file-context-only; the first write-up did not say so
(C-87, a reporting defect).

**(b) The same metric under four conditionings** — `none` (the path
line alone), `subject` (the commit's first line + path), `message` (as
above), `task` (a hand-written proposal in a task's words + path; 147
of 147 units carry one, by commit; fastapi's two DeepSWE units carry
their instruction). Runs `nllcond-*.json`, `modal_ttt.py nll
--conditioning message,none,subject,task`.

Runs `nllcond-olmo-hobbes-{base,300,control}.json` (every unit scored
under all eight prompts in one pass; the `message` rows reproduce the
first run to five decimals); reports `report-olmo-hobbes-cond-*.json`.
Mean per-token NLL over 147 units, paired, 5,000 resamples:

| conditioning | A0 | A2−A0 | A1−A0 | A3−A2 | A2−C (control) |
|---|---|---|---|---|---|
| none (path only) | 2.4992 | **−0.2444** [−0.2598, −0.2292] 147/147 | −0.0030 p 0.40 | −0.0156 [−0.0194, −0.0122] 123/147 | −0.0703 139/147 |
| subject | 2.4665 | −0.2801 [−0.2977, −0.2623] 147/147 | +0.0045 p 0.14 | −0.0067 [−0.0098, −0.0036] 98/147 | −0.0762 142/147 |
| message (the first run) | 2.3940 | −0.2964 [−0.3153, −0.2782] 147/147 | +0.0017 p 0.56 | +0.0006 p 0.72 | −0.0781 140/147 |
| task (hand-written proposal) | 2.4485 | **−0.2986** [−0.3182, −0.2797] 147/147 | **−0.0083** [−0.0130, −0.0039] 89/147 | **−0.0078** [−0.0110, −0.0047] 99/147 | −0.0781 143/147 |

Context-known units (55) under `task`: A1−A0 −0.0148 (39/55, p
<0.0002), A3−A2 −0.0107 (40/55). fastapi, 68 git units: `none` A2−A0
−0.2443 (68/68), `subject` −0.2227 (68/68), A1−A0 and A3−A2 null under
both; fastapi's two DeepSWE units under `task`: A2−A0 −0.0595 (2/2),
A1−A0 −0.0058 (2/2) — n = 2, recorded, not read.

The conditioning moves the base by a tenth of a nat (2.50 with the path
alone, 2.39 with the commit message) and moves the adapter's gain the
other way: the adapter is worth −0.244 with *no* task statement at all
and −0.299 with one. Nothing shrinks as the conditioning tightens. The
prompted block is null under `none`, `subject` and `message` and
becomes real under `task` (−0.008, 89/147) — the same −0.008 on top of
the adapter (A3−A2, 99/147). That is the preregistered second shape:
the adapter holds repo language, the task statement supplies binding,
the block adds a little under a real task, and the three are separable.
Under `task`, H-TTT-5's NLL kill criterion (combined arm not better
than the best single arm) is **not met** — by 0.008 nats, forty times
smaller than the adapter's own effect; under `message` it was. The
true−control margin (C-86) is the same 0.07–0.08 under every
conditioning.

## Item 3 — the shuffled control's cards (lookup, then a second control)

**Lookup.** `--control shuffled` deranged assistant turns within each
(kind, family) group — QA answers *and* card bodies. A card body opens
with its own `symbol:` line and carries its own true `called by` /
`calls` / `tests` lines, so under the wrong "Describe `X`" question the
corpus still stated every true edge of the graph, once, in card form.
Only the QA relations were wrong. The −0.078 (true − control) of the
first record is therefore a lower bound on what the graph's relations
are worth in the weights.

**`--control shuffled-all`** (corpus hash `f654d44965290321`, 13,688
records): QA deranged as before, and each card's `called by:`, `calls:`
and `tests:` lines deranged independently across the cards of the same
module (headers kept; 18 single-card modules left alone; positionally,
1,255 / 712 / 1,605 of 2,454 lines land on identical text such as "none
recorded" — inherent to permuting within a module, so the control keeps
the module's *shape* and breaks every specific edge). One adapter, 300
steps, seed 0, same recipe.

Adapter `adapters/allenai-olmo-3-7b-instruct/hobbes/ebdf7a510eff/047bc3b4ac33`
(617 s, 0.351 epochs, last loss 0.567 — higher than the true adapter's
0.09: a card whose lines contradict its QA is harder to fit). NLL over
the 147 units (`nll-olmo-hobbes-shuffled-all.json`,
`report-olmo-hobbes-shuffled-all.json`):

| comparison | all (147) | context-known (55) | no-known-file (92) |
|---|---|---|---|
| shuffled-all − A0 | −0.2256 [−0.2475, −0.2045] 143/147 | −0.3116 55/55 | −0.1741 88/92 |
| **true − shuffled-all** | **−0.0709** [−0.0789, −0.0633] 140/147 | −0.0563 51/55 | −0.0796 89/92 |
| shuffled − shuffled-all | +0.0072 [+0.0035, +0.0109] p 0.0004 | +0.0067 p 0.024 | +0.0075 p 0.0008 |
| shuffled-all aided − bare | +0.0004 p 0.79 | −0.0034 p 0.10 | +0.0027 p 0.12 |

True − shuffled-all is −0.071 against −0.078 over the first control:
the two intervals overlap, so the true edges the first control kept
inside its cards bought it nothing on this metric, and by the
preregistered reading the card rendering adds nothing beyond the QA
for NLL. The second control is in fact slightly *better* than the
first (by 0.007), which is the C-86 point again: the margin is a bound
on corpus coherence, not the graph's worth. Held-out navigation under
this control: below, with the phase-2 arms.

## Item 7 — the defines scorer audit (no GPU; `scripts/ttt_rescore.py --audit`)

The 89 A1 (base + card) defines failures under scorer v1, classified:

| class | n |
|---|---|
| right path, wrong format (`proxy.go` for `go/internal/proxy/proxy.go`) | **59** |
| no path named | 25 |
| ambiguous basename (`main.go`: two known files) | 3 |
| wrong path | 2 |

**Scorer v2** (`hobbes.ttt.score.SCORER_VERSION = 2`): a reply names
the truth path when the full path appears, or when a path-shaped token
(basename or partial path; `@sha`, `:line`, backticks and bold stripped)
is a `/`-boundary suffix of **exactly one** known path and that path is
the truth. An ambiguous suffix scores 0 — the reply did not identify the
file. Only *defines* changes; every other family is identical to four
decimals. Every navigation run re-scored from its stored replies into
`*-v2.json` (old files untouched; `scorer_version` and `rescored_from`
in the new ones).

| arm | defines v1 → v2 | callers | callees | tests | impact | absent FA | nav (has-truth) v1 → v2 |
|---|---|---|---|---|---|---|---|
| A0 base | 0.013 → **0.290** | 0.062 | 0.005 | 0.000 | 0.033 | 0.980 | 0.021 → 0.108 |
| A1 base + card | 0.773 → **0.924** | 0.678 | 0.760 | 0.791 | 0.135 | 0.896 | 0.564 → 0.611 |
| A2 adapter | 0.985 → 0.985 | 0.103 | 0.206 | 0.521 | 0.301 | 0.224 | 0.496 → 0.496 |
| A3 adapter + card | 1.000 → 1.000 | 0.791 | 0.810 | 0.370 | 0.095 | 0.224 | 0.608 → 0.608 |

Training sample: A0 defines 0.024 → 0.301, A2 0.992 → 0.992. Two
things the numbers carry: A1 lands at 0.924, under the preregistered
0.95 line (the residual is the 25 replies naming no path, 3 ambiguous, 2
wrong); and v2 lifts the **base** to 0.29 because it guesses the
basename from the id's module segment (`deepswe_familiarity.ask` →
`deepswe_familiarity.py`; 68 Python, 43 Go, 3 web hits) and the basename
is unique — a correct identification of the file by convention, not by
knowledge. The A2−A0 defines delta is +0.70 under v2, not +0.97. Runs
`navreport-hobbes-{all,vsA1,train}-v2.json`.

## Item 8 — the trained prior overrides the text (no GPU; `scripts/ttt_override_probe.py`, v2 runs)

Over the has-truth items of a family, an *override* is a zero-score
reply that names nothing; each is joined to its symbol's module and to
how often that module's training answers in the family were "none
recorded" (∅). A module is ∅-heavy at ≥ 0.5.

| arm | family | has-truth | overrides | from ∅-heavy modules | ∅-density behind overrides / behind hits | overrides that refuse | family's training ∅ share |
|---|---|---|---|---|---|---|---|
| A1 base + card | tests | 102 | 8 | 1 | 0.24 / 0.25 | 0 | 0.63 |
| **A3 adapter + card** | **tests** | 102 | **61** | 17 | 0.31 / 0.18 | **61** | 0.63 |
| A1 | callers | 112 | 10 | 6 | 0.54 / 0.23 | 7 | 0.55 |
| A3 | callers | 112 | 17 | **13** | **0.70** / 0.22 | 17 | 0.55 |
| A1 | callees | 256 | 21 | 8 | 0.37 / 0.27 | 7 | 0.33 |
| A3 | callees | 256 | 30 | 17 | 0.49 / 0.25 | 17 | 0.33 |
| A1 | impact | 393 | 139 | 0 | – | 45 | 0.00 |
| A3 | impact | 393 | 21 | 0 | – | 18 | 0.00 |

All 61 tests overrides are the training template verbatim ("No test
reaches `X` at ebdf7a510eff") with the tests listed on the card in
front of the model. For **tests** the tilt toward ∅-heavy modules is
mild (0.31 vs 0.18; 17 of 61): the prior is family-wide — 63% of every
tests answer the adapter saw was "none". For **callers** and
**callees** the overrides *do* track the module: 13 of 17 caller
overrides come from modules where ≥ 50% of the training answers were
"none" (density 0.70 behind overrides vs 0.22 behind hits). Impact is a
different shape: A3 refuses less than A1 (21 vs 139) and fails by
naming wrong modules instead. Registered as C-88.

## Item 10 — the version-aware probe (offline re-score of the stored replies; `scripts/ttt_probe.py rescore --tags 100`)

The probe's files part re-scored against the union of trees across the
repo's tagged releases (100 newest tags; the underscore rename in httpx
predates its 30 newest) and with generic names dropped. Qwen's stored
replies were complete (0/5 rows truncated); Olmo's 160-char heads were
cut on 2–5 of 5 rows per repo, so its rows are re-asked when the serve
is up (below). Temperature 0, so a re-ask reproduces the reply.

| model | repo | score at SHA | stoplisted | any version | best tag | cell |
|---|---|---|---|---|---|---|
| Qwen2.5-Coder-7B | hobbes | 0.202 | 0.136 | 0.202 | (no tags) | neither |
| Qwen2.5-Coder-7B | **httpx** | 0.203 | 0.196 | **0.247** | 0.28.1 (×4), 0.9.3 | neither |
| Qwen2.5-Coder-7B | fastapi | 0.155 | 0.155 | 0.155 | – | neither |
| Qwen2.5-Coder-7B | textual | 0.111 | 0.111 | 0.111 | – | U |
| Olmo-3-7B (heads) | hobbes | 0.044 | 0.044 | 0.044 | (no tags) | U |
| Olmo-3-7B (heads) | httpx | 0.091 | 0.080 | 0.091 | 0.28.1 | U |
| Olmo-3-7B (heads) | fastapi | 0.129 | 0.129 | 0.129 | – | U |
| Olmo-3-7B (heads) | textual | 0.021 | 0.021 | 0.021 | – | U |

Qwen's httpx reads 0.247 against any tagged release, best at 0.28.1 —
the version it names — and nothing crosses 0.5: no memorised cell at
7B, and the probe now sees the shift it was blind to. Qwen's 0.20 on
Hobbes falls to 0.14 without `README.md`/`LICENSE`/`__init__.py`.
Records `probe-{olmo,qwen}-*-v2.json`.

## Item 6 — a second and a third seed for the 300-step adapter

Seed 1: adapter `…/2615369b529f` (597 s, last loss 0.217); seed 2:
appended below. NLL over the 147 units, paired
(`nll-olmo-hobbes-300s1.json`, `report-olmo-hobbes-seed1.json`):

| comparison | all (147) | context-known (55) | no-known-file (92) |
|---|---|---|---|
| seed 1 − A0 | −0.2776 [−0.2970, −0.2591] 146/147 | −0.3472 55/55 | −0.2361 91/92 |
| seed 1 − control | −0.0593 [−0.0680, −0.0506] 130/147 | −0.0424 46/55 | −0.0694 84/92 |
| **seed 1 − seed 0** | **+0.0188** [+0.0136, +0.0239] 37/147 | +0.0207 11/55 | +0.0176 26/92 |
| seed 1 aided − bare | +0.0006 p 0.73 | −0.0032 p 0.31 | +0.0029 p 0.11 |

Seed-to-seed |Δ| beside the bootstrap CI half-width of the primary:

| metric | seed 0 | seed 1 | \|Δ\| | CI half-width (seed 0) | verdict |
|---|---|---|---|---|---|
| A2−A0 | −0.2964 | −0.2776 | 0.019 | 0.019 | at the edge |
| true − control | −0.0781 | −0.0593 | 0.019 | 0.008 | **exceeds** |
| A3−A2 | +0.0006 | +0.0006 | 0.000 | 0.003 | inside |

By the preregistered rule the NLL comparisons' intervals are
relabelled **unit-only** (they measure unit variance, not
adapter-training variance; a second-seed adapter moves the true−control
margin by more than twice its half-width) and a third seed was queued
and run. Seed 2: adapter `…/fe7318f636eb` (711 s, last loss 0.261),
`nll-olmo-hobbes-300s2.json`, `report-olmo-hobbes-seed2.json`:

| comparison | all (147) |
|---|---|
| seed 2 − A0 | −0.2650 [−0.2849, −0.2462] 145/147 |
| seed 2 − control | −0.0466 [−0.0543, −0.0395] 129/147 |
| seed 2 − seed 0 | +0.0314 [+0.0270, +0.0358] 14/147 |
| seed 2 − seed 1 | +0.0127 [+0.0081, +0.0172] 47/147 |
| seed 2 aided − bare | −0.0012 p 0.40 |

Three seeds: A2−A0 = −0.296 / −0.278 / −0.265 (mean −0.280, range
0.031); true − control = −0.078 / −0.059 / −0.047 (mean −0.061, range
0.031). The seed range is 1.6× the unit bootstrap's full width on
A2−A0 and 4× on true−control; every "a quarter is the graph"-shaped
number in the first record should be read with ±0.015 of adapter
variance on top of its interval. A3−A2 is null under every seed. The
held-out navigation for seeds 1 and 2 is appended with the phase-1 and
phase-2 arms below.

## Item 9 — the primary cell: HSR, RFE, `manifest_ignore` over 50 derived units (`hobbes.ttt.cell`, `scripts/ttt_cell.py`; `~/.hobbes/bench/ttt/cell-hobbes/`)

**Units.** `hobbes plan` over the 28 hand-written proposals on the
worktree at `ebdf7a5`, seeded by the commit's files the base graph
holds (lexically otherwise), at most two units per proposal: **50
derived units from 26 proposals** (two refused by the planner: the
README-only commit matched no node; one seeded only on hubs — ADR-093's
refusal, recorded). Mean 1.9 interior paths and 7.6k characters of
manifest per unit; every unit has an editable path.

**Arms.** One agent per unit on a fresh checkout of the base: the owned
loop, **file tools only** (no exec in any arm: repo code never runs,
policy identical), 30 turns, 1,536 tokens per turn, temperature 0.2,
the tool schemas in the system prompt and the model's
`<function_calls>` read from its text. A0/A2 see the proposal; A1/A3
the proposal plus the unit's manifest (`render_context`: interior,
guarding tests, contracts, neighborhood, complement). An unaided arm's
prompt is the same for every unit of a proposal, so it ran once per
proposal (26 sessions) and was scored per unit; the aided arms ran 50
each. Base and adapter (300 steps, seed 0) on one A100 serve at a 32k
window. **Every arm is *model + prompt* (P12).** 152 sessions, 18
minutes wall.

| arm | sessions | mean turns | text calls | answered / repeat-stall / turn budget / error |
|---|---|---|---|---|
| A0 base | 26 | 8.3 | 173 | 26 / 0 / 0 / 0 |
| A1 base + manifest | 50 | 7.2 | 298 | 50 / 0 / 0 / 0 |
| A2 adapter | 26 | 14.6 | 352 | 15 / **8** / 3 / 0 |
| A3 adapter + manifest | 50 | 9.5 | 360 | 47 / 0 / 2 / 1 |

**Scores** (per unit; HSR over the units whose agent emitted a judged
reference; RFE precision over units with a non-empty patch; paired
bootstrap over units, 5,000 resamples):

| arm | HSR | n | RFE Jaccard | precision | recall | `manifest_ignore` | applies (non-empty patch) | references (hallucinated / in-graph / unverifiable / own) |
|---|---|---|---|---|---|---|---|---|
| A0 | **1.000** | 23 | 0.000 | 0.000 | 0.000 | – | 0.42 | 148 (95 / 0 / 15 / 38) |
| A1 | 0.820 | 31 | **0.411** | 0.951 | 0.412 | 0.06 | 0.54 | 397 (261 / 77 / 10 / 49) |
| A2 | 0.923 | 32 | **0.007** | 0.012 | 0.010 | – | 0.84 | 7,167 (2,236 / 165 / 151 / 4,615) |
| A3 | 0.799 | 27 | 0.431 | 0.819 | 0.545 | 0.02 | 0.68 | 1,270 (521 / 317 / 14 / 418) |

| comparison | metric | n | Δ | 95% CI | p | a>b / a<b |
|---|---|---|---|---|---|---|
| **A2−A1** | HSR | 20 | **+0.112** | [−0.049, +0.287] | 0.18 | 7 / 5 |
| A2−A0 | HSR | 19 | −0.119 | [−0.213, −0.036] | 0.002 | 0 / 6 |
| A1−A0 | HSR | 15 | −0.255 | [−0.462, −0.073] | 0.001 | 0 / 6 |
| A3−A1 | HSR | 18 | −0.068 | [−0.229, +0.074] | 0.37 | 5 / 6 |
| A3−A2 | HSR | 16 | −0.201 | [−0.399, −0.020] | 0.028 | 3 / 8 |
| **A2−A1** | RFE Jaccard | 50 | **−0.404** | [−0.533, −0.278] | <0.0002 | 1 / 26 |
| A2−A0 | RFE Jaccard | 50 | +0.007 | [0, +0.020] | 0.73 | 1 / 0 |
| A1−A0 | RFE Jaccard | 50 | +0.411 | [+0.288, +0.537] | <0.0002 | 26 / 0 |
| A3−A1 | RFE Jaccard | 50 | +0.021 | [−0.113, +0.152] | 0.76 | 15 / 10 |
| A3−A1 | RFE recall | 50 | +0.133 | [−0.016, +0.280] | 0.083 | 15 / 8 |
| A3−A2 | RFE Jaccard | 50 | +0.425 | [+0.307, +0.549] | <0.0002 | 34 / 0 |
| A3−A1 | manifest_ignore | 50 | −0.040 | [−0.100, 0] | 0.25 | 0 / 2 |
| A2−A1 | applies | 50 | +0.300 | [+0.120, +0.480] | 0.002 | 20 / 5 |

**What the transcripts show.** The base without a manifest does not
know where anything is: it asks the user for file paths, writes
nothing in 29 of 50, and every name it does emit is invented (HSR
1.00). The manifest is what lets a 7B find the files at all (Jaccard
0.41, precision 0.95: it edits what the manifest lists and little
else). The **adapter alone** finds nothing either (Jaccard 0.007) — it
writes *more* than any arm (a patch in 42 of 50, 7,167 references,
4,615 of them names its own edits define) into paths that do not exist
and look like this repo's: `pipeline/oracle/agent.py`,
`scip-java/src/scip/java.py`, `pipeline/src/main/java/org/scip/…`;
eight of its 26 sessions were stopped by the loop for repeating the
same call, three ran out of turns. Repo language without repo
structure, at the agent grain: the first record's "no symbol-grain
edge in the weights" made concrete. Under the manifest the adapter
edits the right files (0.43, precision 0.82 — lower than the base's
0.95: it still strays) and reaches more of the interior (recall 0.55 vs
0.41, p 0.08), and its HSR is the lowest of the four (0.80) without
being different from A1's (p 0.37). `manifest_ignore` is rare in both
aided arms (3 and 1 units) — the tests collapse of item 8 did not show
up as denials here; it showed up as the adapter arm's confabulated
paths instead.

**Against the preregistered readings.** HSR(TTT) ≥ HSR(prompted)
(+0.11, inside its CI): **H-TTT-2 is killed** on the unseen cell.
RFE(TTT) is 0.40 *below* RFE(prompted): **H-TTT-3 is killed**. The
combined arm is not better than the best single arm on HSR or Jaccard
(recall +0.13, p 0.08): H-TTT-5 not survived on the agent metrics
either. The design §8 row that fits is the second — *A1 > A2, A3 ≈
A1: structure must be live in attention* — and the review's extra row
(A2 lower HSR but higher manifest_ignore) did not occur: A2's HSR is
higher and it never saw a manifest to ignore.

**Defect register (the ADR-085 precedent: harness defects before model
findings).**
- **D-1** — no arm can execute, and the scorer does not run the
  guarding tests either; *applies* is "a non-empty patch", nothing
  more. Solve rate in the design's sense is not measured.
- **D-2** — the first run died in every session on vLLM's "auto tool
  choice requires a parser" 400: the serve has no parser for Olmo 3's
  `<function_calls>` syntax. Fixed by sending the schemas in the system
  prompt and reading the calls from the text (`loop.py --tool-choice
  none`); the base model then wrote Python-quoted arguments the
  JSON-only parser refused, fixed the same way. Both fixes are in the
  loop with tests; the 200 failed rows were discarded before the run.
- **D-3** — the first scoring counted capitalised words, short
  acronyms, dunders and URL fragments as symbol references (HSR 0.87 /
  0.91 / 0.94 / 0.80); the extractor was tightened and every row
  re-scored offline (`scores-extractor-v1.jsonl` kept beside). The
  v2 numbers are the ones above.
- **D-4** — HSR's denominator is small (15–32 units per comparison):
  half the sessions emit no judged reference, and the reference
  extractor is a regex over emitted code, not the lane-A walk the
  design names (§4.1) — a simplification, registered.
- **D-5** — the unaided arms' 26 sessions are scored against 50 units
  (shared runs, paired by unit), so their bootstrap rows are correlated
  within a proposal.

## Item 4 — abstention under instruction: A1r and A3r (`nav-olmo-hobbes-A{1,3}r.json`, template `7fa1cc2ac118bae3`, scorer v2; `navreport-hobbes-refuse.json`)

The card prompt plus, verbatim: "If the symbol is not listed in the
derived context above, reply that it is not defined in this repo at
this SHA. Do not guess a file." All 2,270 held-out items, the 393
distractors included. Baseline for the deltas: A1 (the card without
the instruction), v2 scorer.

| arm | absent (refusal) | **absent FA** | defines | callers | callees | tests | impact | nav (has-truth) |
|---|---|---|---|---|---|---|---|---|
| A1 base + card | 0.104 | 0.896 | 0.924 | 0.678 | 0.760 | 0.791 | 0.135 | 0.611 |
| **A1r base + card + instruction** | **1.000** | **0.000** | 0.878 | 0.538 | 0.732 | 0.772 | 0.045 | 0.549 |
| A2 adapter | 0.776 | 0.224 | 0.985 | 0.103 | 0.206 | 0.521 | 0.301 | 0.496 |
| A3 adapter + card | 0.776 | 0.224 | 1.000 | 0.791 | 0.810 | 0.370 | 0.095 | 0.608 |
| **A3r adapter + card + instruction** | 0.776 | **0.224** | **0.331** | **0.190** | 0.771 | 0.181 | 0.041 | **0.305** |

| comparison | family | n | Δ | 95% CI | p | a>b / a<b |
|---|---|---|---|---|---|---|
| A1r−A1 | absent | 393 | +0.896 | [+0.865, +0.926] | <0.0002 | 352 / 0 |
| A1r−A1 | callers | 112 | −0.140 | [−0.224, −0.061] | 0.0004 | 13 / 29 |
| A1r−A1 | defines | 393 | −0.046 | [−0.087, −0.005] | 0.033 | 25 / 43 |
| A1r−A1 | impact | 393 | −0.089 | [−0.103, −0.076] | <0.0002 | 25 / 155 |
| A1r−A1 | callees | 256 | −0.028 | p 0.19 | | |
| A1r−A1 | tests | 102 | −0.019 | p 0.62 | | |
| A1r−A1 | navigation | 1,256 | −0.062 | [−0.081, −0.043] | <0.0002 | 110 / 306 |
| A3r−A1 | absent | 393 | +0.672 | (identical to A3−A1: the instruction moved nothing) | | |
| A3r−A1 | defines | 393 | −0.593 | [−0.644, −0.539] | <0.0002 | 7 / 240 |
| A3r−A1 | callers | 112 | −0.488 | [−0.584, −0.387] | <0.0002 | 7 / 72 |
| A3r−A1 | tests | 102 | −0.610 | [−0.711, −0.500] | <0.0002 | 7 / 73 |
| A3r−A1 | navigation | 1,256 | −0.306 | [−0.334, −0.277] | <0.0002 | 134 / 576 |

**The base under the instruction refuses every distractor** (false
acceptance 0.896 → 0.000, 352 of 393 items better, none worse) and
pays 0.06 on the has-truth families — mostly callers (−0.14) and
impact (−0.09), the families where the card says least; defines,
callees and tests are within noise. Preregistered reading one, by a
wide margin: the adapter's abstention (0.98 → 0.22) is *less* than an
instruction buys (0.90 → 0.00), so "mid-train for abstention" weakens
to "instruct for abstention" — the design's §3.2(c) rationale is
amended with a dated note.

**The adapter under the instruction is the other half.** Its false
acceptance does not move (0.224 either way: the 22% of distractors it
accepts, it accepts against an instruction too — the habit in the
weights neither improves nor obeys), and the instruction collapses its
has-truth answers: defines 1.00 → 0.33, callers 0.79 → 0.19, tests
0.37 → 0.18. It reads "if the symbol is not listed … say it is not
defined" and says so for symbols that *are* listed on the card in
front of it — the same shape as the tests collapse (item 8, C-88): a
trained prior over the live text, now triggered by an instruction the
base follows correctly. `absent`'s refusal rate is the same in A2, A3
and A3r to three decimals (0.776): whatever the adapter does on a
distractor, it decided in the weights.

## Item 6, continued — seed 1 on the held-out navigation set (`nav-olmo-hobbes-300s1.json`, `navreport-heldout-seeds.json`, v2)

| arm | absent FA | defines | callers | callees | tests | impact | nav |
|---|---|---|---|---|---|---|---|
| seed 0 | 0.224 | 0.985 | 0.103 | 0.206 | 0.521 | 0.301 | 0.496 |
| seed 1 | 0.224 | 0.977 | 0.109 | 0.222 | **0.359** | 0.272 | 0.475 |

Seed 1 − seed 0: tests −0.162 [−0.249, −0.076] (4/22, p 0.0004),
impact −0.029 (p 0.0004), navigation −0.021 (p 0.002); callers,
callees, defines within noise; the absent family **identical item for
item** (Δ 0.000, 0/0) — which distractors an adapter refuses is decided
by the distractor, not the seed. The tests family's seed-to-seed range
(0.16) is larger than its bootstrap half-width (≈0.10): the held-out
tests number is unit-and-seed, like the NLL.

## Item 10, continued — the Olmo probes re-asked with full replies (`probe-olmo-*-v2run.json`, scorer v2, `--tags 100`)

| repo | at SHA | stoplisted | any version | best tag | cell (v2) |
|---|---|---|---|---|---|
| hobbes | 0.156 | 0.156 | 0.156 | (no tags) | neither |
| httpx | 0.091 | 0.080 | 0.091 | 0.28.1 | U |
| fastapi | 0.107 | 0.107 | 0.107 | – | U |
| textual | 0.057 | 0.057 | 0.057 | – | U |

The replies are the temperature-0 ones the heads were cut from; the
files and definitions parts reproduce (files-P 0.10 / 0.13 / 0.00 /
0.00). What moved is the navigation part under scorer v2: on this
repo the base's basename convention (item 7) lifts it from 0.03 to
0.37, and the probe score from 0.044 to **0.156** — over the 0.15 line
by 0.006, so under v2 this repo reads "neither", not U. The first
record's U was a v1 label; the gate's lines were set against v1 and
have not been re-derived. Nothing crosses 0.5 for any repo against any
version; the conclusion of §6 stands, and the label is recorded as
scorer-dependent (C-83).

## Item 5 — the step sweep past one epoch, with paraphrases: gold-diff NLL (the 10,000-step point held for Max)

Same recipe, seed 0; the paraphrase corpus `1694f4a904ed3dc6` (47,390
records: every training QA fact in four question and answer phrasings,
eval set unchanged). Manifests `adapter-olmo-hobbes-{100,300,1000,3000,k4-3000}-manifest.json`;
NLL runs `nll-olmo-hobbes-*.json`; reports `report-olmo-hobbes-{100,1000,3000,k4-3000}.json`.

| adapter | steps | epochs (records) | exposures per fact | A100 wall | last loss | **NLL** | Δ vs A0 | a<b | Δ vs 300 |
|---|---|---|---|---|---|---|---|---|---|
| 100 | 100 | 0.12 | 0.12 | 210 s | 0.24 | **2.0925** | −0.3015 [−0.3176, −0.2858] | 147/147 | −0.0051 p 0.13 |
| 300 (the first record) | 300 | 0.35 | 0.35 | 667 s | 0.09 | 2.0975 | −0.2964 [−0.3153, −0.2782] | 147/147 | – |
| 1,000 | 1,000 | 1.17 | 1.17 | 2,057 s | 0.12 | 2.1965 | −0.1975 [−0.2188, −0.1769] | 143/147 | **+0.0989** [+0.0924, +0.1057], 3/147 |
| 3,000 | 3,000 | 3.51 | 3.51 | 6,095 s | 0.01 | **2.4098** | **+0.0158** [−0.0080, +0.0389] p 0.19 | 56/147 | +0.3122, 0/147 |
| 3,000 × 4 paraphrases | 3,000 | 1.01 | 4.05 | 5,637 s | 0.02 | 2.3200 | −0.0739 [−0.0976, −0.0511] | 99/147 | +0.2225, 3/147 |
| shuffled control, 300 | 300 | 0.35 | 0.35 | – | – | 2.1756 | −0.2184 | 143/147 | +0.0781 |

The 1,000-step adapter is worse than the shuffled control (+0.021,
56/147 better); the 3,000-step adapter is no better than the base at
all, and 0.31 worse than 300 steps on every unit; with paraphrases,
3,000 steps is 0.09 better than without (144/147) and still 0.22
behind 300. The prompted block is null on every point (A3−A2: +0.001
p 0.59 at 1,000; +0.002 p 0.43 at 3,000; +0.008, 60/147, at K4). By
fact exposures the curve is −0.30 at 0.1–0.35, −0.20 at 1.2, +0.02 at
3.5 single-template and −0.07 at 4 with four phrasings: the loss gain
is a sub-epoch effect that a corpus of templated answers destroys once
each fact has been seen — a first, sharp reading of "how many steps to
load a repo": for the gold-diff loss, fewer than a hundred. The 300 vs
100 split by population (item 1) already pointed here. What the
navigation arms say at the same points is below.

### Item 5, navigation — the same adapters on the 600-question training sample and the 2,270-item held-out set (scorer v2; `navtrain-olmo-hobbes-*.json`, `nav-olmo-hobbes-*.json`, `navreport-{train,heldout}-{100,1000,3000,k4}.json`)

**Training sample** (edges the adapter was shown; the decisive table):

| adapter | exposures | absent FA | defines | **callers** | callees | tests | impact | nav (has-truth) |
|---|---|---|---|---|---|---|---|---|
| base | 0 | 0.992 | 0.301 | 0.092 | 0.000 | 0.000 | 0.115 | 0.143 |
| 100 | 0.12 | 0.373 | 0.935 | 0.099 | 0.016 | 0.031 | 0.186 | 0.415 |
| 300 | 0.35 | 0.373 | 0.992 | 0.152 | 0.208 | 0.515 | 0.365 | 0.583 |
| 1,000 | 1.17 | 0.373 | 1.000 | **0.329** | 0.509 | 0.718 | 0.572 | 0.723 |
| 3,000 | 3.51 | 0.373 | 1.000 | **0.950** | 0.895 | 0.945 | 0.818 | 0.952 |
| 3,000 × 4 paraphrases | 4.05 | 0.373 | 1.000 | 0.858 | 0.738 | 0.857 | 0.831 | 0.890 |

Paired, callers on trained symbols (n 47): 300 − 100 +0.053 (p 0.03);
1,000 − 300 **+0.177** [+0.091, +0.278] 13/0; 3,000 − 1,000
**+0.621** [+0.494, +0.739] 36/1; paraphrases − 3,000 −0.092 (p 0.06,
4/9). Callees (n 62): +0.19, +0.30, +0.39 over the same steps;
paraphrases −0.16 (1/13). Tests (n 55): +0.48, +0.20, +0.23. Impact
(n 14): +0.18, +0.21, +0.25. The absent family is **identical at
every point** (0.373, Δ 0.000 item for item, from 100 steps on).

**Held-out set** (symbols whose every training mention was removed):

| adapter | absent FA | defines | callers | callees | tests | impact | nav (has-truth) |
|---|---|---|---|---|---|---|---|
| base | 0.980 | 0.290 | 0.062 | 0.005 | 0.000 | 0.033 | 0.108 |
| 100 | 0.224 | 0.926 | 0.054 | 0.018 | 0.089 | 0.122 | 0.344 |
| 300 | 0.224 | 0.985 | 0.103 | 0.206 | 0.521 | 0.301 | 0.496 |
| 1,000 | 0.224 | 0.998 | 0.194 | 0.437 | 0.584 | 0.350 | 0.576 |
| 3,000 | 0.224 | 0.998 | **0.266** | 0.524 | 0.749 | **0.664** | 0.711 |
| 3,000 × 4 paraphrases | 0.224 | 0.998 | 0.230 | 0.527 | 0.692 | 0.660 | 0.703 |

Paired, held-out: callers 1,000 − 300 +0.091 [+0.042, +0.146] 22/4;
3,000 − 1,000 +0.072 [+0.022, +0.129] 25/12; paraphrases − 3,000
−0.036 (p 0.16). Callees +0.231 then +0.088; impact +0.049 then
**+0.313** (344/36); tests +0.063 (p 0.08) then +0.166 (25/10).
Paraphrases vs single-template at 3,000 steps: every held-out family
within noise (navigation −0.009, p 0.18).

**Reading, against the preregistration.** The first shape, and
sooner than it was written: callers-on-trained *rises with steps* —
0.10, 0.15, 0.33, **0.95** — and crosses the 0.5 line at 3,000 steps,
not 10,000; edges enter the weights with exposure, and a corpus of one
template per fact is enough (paraphrases at the same step count are
slightly *worse* on trained edges and the same on held-out ones — the
second shape did not occur). The order of entry is legible: abstention
and the file mapping by 100 steps (a template fit), the module-grain
regularities (tests, callees, impact) by 300–1,000, the symbol-grain
edges (callers) between 1,000 and 3,000 — i.e. past one epoch, exactly
where the first record stopped. The held-out row says what generalises:
impact 0.30 → 0.66 and tests 0.52 → 0.75 (module-grain, inherited from
siblings), callees to 0.52, callers to 0.27 — a symbol never seen gets
a quarter of its callers right, from the reverse edges of its siblings
and the module's shape, not from its own card. Callers stays below
callees on trained symbols at every point but the last (0.10 / 0.02 at
100 is the exception where both are floor): reversal-shaped, noted and
left.

**And the gold-diff loss went the other way over the same steps**
(the NLL table above): −0.30 at 100–300, −0.20 at 1,000, +0.02 at
3,000. The two metrics are anti-correlated in step count. What the
first record read as "the weights hold no symbol-grain edge at 300
steps" was true and was a statement about 300 steps; what it read as
the adapter's NLL gain being *about* the graph was the part that does
not survive — the NLL gain is a sub-epoch language effect that is gone
by the time the graph is in. A repo can be loaded into a 7B's LoRA in
about 3,000 steps (1.7 A100-hours here) at the cost of every nat the
adapter had bought on the diff. Which of the two an agent needs is the
primary cell's question (item 9: at 300 steps, neither the loss gain
nor the regularities found the files). The 3,000-step adapter has not
been run through the cell — held with the 10,000-step point.
