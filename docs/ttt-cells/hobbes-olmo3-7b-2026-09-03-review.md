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

*(table appended when the passes land)*

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

*(NLL and held-out navigation rows appended when they land)*

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

## Items 4, 5, 6, 9 — *(appended when they land)*
