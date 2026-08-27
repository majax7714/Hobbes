# The ADR-085 validation run (2026-08-24) — record and defect register

> **Status (2026-08-27): D1–D4, D7, D8 fixed (ADR-091); D5 and D6 held
> by Max — the harness's shape is not the current focus, and they stay
> documented below.** The run itself is still stubbed, not concluded:
> the numbers are recorded and the removal A/B has not been re-run. Nothing in this run's solve column is a capability
> claim; the run was judged on the machinery's behavior (ADR-084 §
> measurement), and one instance's implement stage is explicitly
> contaminated by harness defect D2/D3 below.

Two passes over the same five Verified instances (django-11400,
xarray-3993, sklearn-25102, sphinx-8548, sympy-13852), 7B
(Qwen2.5-Coder-7B-Instruct on Modal A10G), harness arm only, staged
plan → implement → verify, `--coverage strict`, local podman
evaluation. **A** = ADR-085 default (requirements brief);
**B** = `--proposal-in-brief` (the removal test's control). Records:
`~/.hobbes/bench/adr085-validate-7b{,-control}/`.

## Run A — what the machinery did

| instance | seed source | brief | replanned | outcome / verdict |
|---|---|---|---|---|
| django-11400 | lexical-fallback | proposal | — | patch / unresolved |
| xarray-3993 | planner | requirements | yes | empty-patch |
| sklearn-25102 | lexical-fallback | proposal | — | patch (contaminated, D2/D3) / unresolved |
| sphinx-8548 | planner | requirements | yes | empty-patch |
| sympy-13852 | planner | requirements | yes | patch / unresolved |

**The E-measurement (ADR-084's asked number):** the 7B planner wrote
`requirements:` **0/5 on the first attempt** and **3/5 after the one
strict re-plan** — the re-plan recovered every case where the planner
produced a usable handoff at all. The other 2/5 fell to lexical
fallback, which **bypasses the coverage guarantee entirely** (D5).
0/5 solved; solve rate was explicitly not this run's measure.

**First observed end-to-end ADR-085 success (sphinx):** planner-1
named the right file with zero requirements → strict re-spawned the
planner once → planner-2 wrote R1–R3 with owning files → coverage
assigned all three to U1 → the implementer brief carried `## Your
task` and no proposal. The machinery held its guarantee.

## Run B — control (`--proposal-in-brief`, same instances)

| instance | seed source | replanned | outcome / verdict | planner hit |
|---|---|---|---|---|
| django-11400 | lexical-fallback | — | empty-patch | 0/3 |
| xarray-3993 | planner | no | empty-patch | 2/2 |
| sklearn-25102 | lexical-fallback | — | patch / unresolved | 0/2 |
| sphinx-8548 | planner | yes | empty-patch | 1/2 |
| sympy-13852 | lexical-fallback | — | empty-patch | 0/1 |

313 completions, **zero** fit-400s and zero elisions — D1/D2/D3 fire
only under window saturation, which B never reached.

**The A/B reading, honestly: no usable removal-test signal at n=5,
and the comparison is confounded twice.** First by **D5**: the
fallback instances (django and sklearn in both passes, sympy in B)
carried proposal-briefs in *both* arms, so they are not
control-vs-treatment pairs at all. Second by **planner-path variance
(observation O4)**: sympy's planner produced a usable handoff in A and
fell to fallback in B — at temperature 0 — so even the seed path is
not reproducible run-to-run (vLLM batching nondeterminism is the
suspected source). The only clean matched pairs are xarray and sphinx
(planner path both passes): both empty-patch in both arms — the
implementer failed identically with and without the proposal, which
says the binding constraint on those two is implementer execution
(the known 7B failure mode ii), not brief composition. A patch-count
comparison (A: 3 patches / B: 1) over the confounded set should not
be quoted as a removal-test result. The removal A/B needs to be
re-run after the restructure, on the D5 fix, with enough instances
that planner-path variance can be split out.

- **O4 (new observation):** the planner stage's outcome varies across
  identical greedy runs (sympy: planner in A, fallback in B). Any
  per-instance A/B on the planner path needs either seed pinning or
  n large enough to absorb the variance.

## Defect register — every bug this run found, with its proposed change

Ordered by severity. "Owner" is the file the change lands in. None are
fixed yet — the restructure session picks these up.

**D1 — The window-fit loop storms the endpoint with 400s.** *Fixed, ADR-091.*
*Observed:* one sklearn call recorded 450 fit retries; ~929 absorbed
400s against 235 successful completions across the run — Modal's 4xx
alarm. *Cause:* this vLLM build's overflow error reports "at least N
input tokens" where N = `window − max_tokens + 1` — a lower bound, not
the prompt size — so `room = window − N − 16` shrinks by exactly 17
tokens per retry: ~75 consecutive 400s per elide cycle (arithmetic
verified by simulation and a controlled reproduction against the
endpoint). *Proposed change:* one fit attempt per elide cycle — treat
the reported input count as a lower bound; if the refit overflows
again, elide immediately. Bounds worst-case 400s per call at
~elidable-results, preserves the single-retry behavior on endpoints
that report true sizes. *Owner:* `pipeline/src/hobbes/agent/loop.py`
(`Endpoint.chat`).

**D2 — Elision deletes action memory for a ~10-token saving.** *Fixed, ADR-091.*
*Observed:* sklearn u1's elisions consumed its four failed-edit error
results (89–112 chars each — barely longer than the placeholder), after
which the model repeated the identical four failed edits. *Proposed
change:* `elide_oldest_tool_result` skips results from
`MUTATING_TOOLS` and any result shorter than ~2× the placeholder —
eliding them saves nothing and deletes the record of what was already
tried. *Owner:* `agent/loop.py` (`elide_oldest_tool_result`).

**D3 — The read-before-overwrite ticket survives elision of the read
(P10 shape).** *Fixed, ADR-091.* *Observed:* sklearn u1 read `_array_api.py` (turn 9),
the read's content was elided (turn 10), then `write_file` replaced
the whole file with a 28-byte placeholder stub — permitted because the
path counted as read. The general mechanism (window fitting) hollowed
out the specific guarantee's premise (ADR-064). *Proposed change:*
eliding a `read_file`/`search_file` result for path P invalidates P's
read ticket; the next write/edit on P refuses until P is re-read.
*Owner:* `agent/loop.py` (the read-tracking set + elide hook).

**D4 — Same-turn batching defeats read-before-edit's spirit.** *Fixed, ADR-091.*
*Observed:* sphinx u1 batched `read_file` + `edit_file` + pytest +
`git commit` in one turn; execution order satisfied ADR-067's letter,
but the edit's anchor was authored before the model saw a byte of the
read — and was pure hallucination (`self.env.cache.get((namespace,
attrname))` occurs nowhere in the file; the model rendered requirement
R2's *description* as if it were existing code). *Proposed change:*
refuse `edit_file`/`write_file` on a path whose first read happened in
the same assistant turn; the error says "read landed this turn — copy
your anchor from the result and edit next turn." *Owner:*
`agent/loop.py` (tool dispatch).

**D5 — The lexical fallback bypasses the ADR-085 coverage guarantee.** *Held (Max, 2026-08-27).*
*Observed:* django and sklearn (planner rambled → lexical seeds) got
proposal-briefs with no requirements and no coverage check — the
pre-ADR-085 shape, inside a `--coverage strict` run. *Proposed change
(needs Max's shape call at the restructure):* under `strict`, a
planner fallback is itself a plan error (coverage cannot be
guaranteed), or at minimum the record carries `coverage: {status:
bypassed-fallback}` so the bypass is a counted outcome rather than
silence. *Owner:* `pipeline/src/hobbes/run/stages.py` +
`run/coverage.py`.

**D6 — A generic one-word lexical seed selects a hub as work.** *Held (Max, 2026-08-27).*
*Observed:* the token `astype` in sklearn's issue seeded
`sklearn.utils._array_api`; seed-always-work overrides ADR-083's hub
exclusion, so the unit's interior was a module reached by 2,543
guarding tests. *Proposed change:* the parked C-36 seed adjustments
(weigh generic one-word seeds below identifier-shaped ones; dotted
suffix already done), and consider requiring an identifier-shaped or
multi-token match before a lexical seed may override the hub
exclusion. *Owner:* `pipeline/src/hobbes/derive/impact.py`; decision
interacts with ADR-083, so it belongs to the restructure.

**D7 — Foreign environment residue rides every brief's complement.** *Fixed, ADR-091 — with a correction: the residue was not foreign.*
*Observed:* sklearn's `extraction_errors` carries a scip-decode
dup-symbol row naming `exercise_01_language_train_model` — a package
from the box's discoverable python environment, not from sklearn
(zero graph nodes/edges from it; the C-28 drop worked) — and the row
was rendered verbatim into every unit brief, with Rust-flavored
wording ("cargo targets sharing a name") on a Python decode.
*Proposed change:* scope the dup-symbol report to in-repo monikers
(or mark environment-origin rows as provider-environment and keep
them out of unit briefs), and make the explanation wording per-lane.
*Owner:* `scip/index.mjs` (report) + `extract/scipsource.py`
(degradation text); small surfacing note against C-28.
*Correction (2026-08-27):* the diagnosis was wrong. The row's module is
in sklearn's own tree twice — `doc/tutorial/text_analytics/skeletons/`
and `…/solutions/` both hold `exercise_01_language_train_model.py` — a
legitimate in-repo C-28 duplicate, not environment residue (the C-28
drop was right). What was defective: the Rust wording on a Python
decode, and `path: "."`, which the brief filter reads as "every unit".
ADR-091 scopes the record to the files' common directory and words it
per lane.

**D8 — A prose "reflection" is not a handoff.** *Fixed, ADR-091.* *Observed:* sphinx u1
ended with prose beginning "let's reflect…" and never called the
`reflect` tool; no handoff reached the orchestrator. The nudge for
this shape exists only for read-only roles. *Proposed change:* an
implementer exiting without any `reflect` call gets the one bounded
nudge (mirroring `NUDGE_READ_ONLY`), and the harvest records
`handoff: missing` explicitly. *Owner:* `agent/loop.py` +
`run/stages.py`.

## Observations that are findings, not defects

- **The knowledge tools went unused at this rung.** sklearn u1's
  flight log is seven pytest execs and nothing else; no session
  called `tests_guarding`, `graph_neighborhood`, or
  `list_blind_spots`. For the 7B, derived context is push-only — the
  brief is the entire delivery surface. A restructure input, not a
  bug.
- **The 7B renders a requirement's description as existing code**
  (sphinx D4's anchor). Brief wording may mitigate ("the requirement
  describes the goal state, not current code"), but it is primarily a
  model-capability observation consistent with the BUILDLOG
  seventy-fifth/seventy-sixth reading.
- **Fast honest failure worked**: sphinx's implement cost 37 s and
  exited cleanly on the repeat guard — the discipline held; no thrash.

## Standing state

Experiments return to **parked** after pass B. D1–D4, D7 and D8 are
fixed in ADR-091 (2026-08-27), validated with no model; D5–D6 are held
by Max. The removal A/B is still to be re-run after those.
