# Session handoff — the single resume point

**Rewritten 2026-08-28 (ADR-092 built in full; the seven-cell triage
done; D5/D6 closed by ADR-093 — the harness worklist is empty).** The one
authoritative resume doc. Read this, then **`docs/adr/092-ingest-containment.md`**
(the containment programme's four phases — the active track), then
`docs/adr085-validation-run.md` (the harness worklist, held) and the
recent `docs/BUILDLOG.md` entries. History lives in the BUILDLOG; this
doc is forward-looking and is rewritten, never appended into a pile.

## THE ACTIVE TRACK — ADR-092, containment of whatever executes repo code

Max's direction (2026-08-27): an architecture review found the sandbox
boundary covered agent sessions but not extraction or the oracle lane —
the layers that execute repo-authored code *by design* ran on the host.
Theoretical against our own repos; live the day a foreign public repo
is ingested. **Triage of the seven untriaged oracle cells is on hold
until this lands.** One phase active at a time.

- **Phase 1 — ingest containers: BUILT (this session).** Every lane B
  step runs in `hobbes-session:local` through
  `pipeline/src/hobbes/extract/containment.py` (a pure planner, the
  `go/internal/sandbox` shape): cache root rw at its host path, the
  `scip/` helper and every symlink target ro at their host paths (hop
  by hop, unresolved), `--network none` for index steps, separate
  *fetch* containers (`npm ci`, `cargo fetch`, `go mod download`) for
  the registry. Executing steps (`index-rust`, `python-env`) **refuse**
  without containment (`ContainmentRefusal`, named first by every
  general catch); the others run on the host and say so (C-64).
  Canary: `tests/fixtures/canary-rust`. Image: ubuntu 24.04 + pinned
  node/Go/scip-go/rustup 1.97.1 (rust-analyzer **and rust-src** —
  without the sysroot source the contained Rust lane silently lost its
  semantic tier; caught by the contained-vs-host diff). Measured no-op
  on this repo: see the BUILDLOG entry.
- **Phase 2 — oracle containers: BUILT (2026-08-28).** O6/O7 in the
  same image through `bench/oracle/internal/contain`, the verifier's
  mount shape verbatim. rust_proj regraded byte-identical; this repo's
  Python zone contained vs host identical in suspects and misses with
  an explained 8-edge residue (one environment-probing test). Records:
  `oracle-cells/{rust_proj,hobbes-py}-2026-08-28.md`. Max ratified the
  phase-1 decisions (venv listing strict).
- **Phase 3 — guarantee wiring: BUILT (2026-08-28).** `hobbes ingest
  --uncontained`; the `containment` stamp in `graph.json`; the summary
  and `list_blind_spots` name an uncontained artifact (C-64); P4's
  gloss extended.
- **Phase 4 — the reshaping: LANDED (2026-08-28).** Architecture "Where
  this is going" states the two layers and the P11 scope;
  `proxy.KnowledgeOnlyBanner` prints them at `serve --knowledge-only`.

**ADR-092 reviewed by Max (2026-08-28): all good.** One scoping he
added, now in the ADR, C-64 and the evidence log (P11): containment is
verified only on the runs made under it — this repo, rust_proj, the
fixtures. Every earlier cell and graph was a host run and is not
re-earned; the contained toolchain differed from the host's once
already (`rust-src`) and more of that is expected. From here every cell
runs contained, its record carries `containment`, and a record without
it is a host-run record.

**The seven-cell triage is DONE and the drift audit discharged (2026-08-28, BUILDLOG — 41 fixes; this repo's Go cell regraded to 100% contained).** Four fixes
(Go scope veto, Rust constructor rule, func-value abstract bucket,
`@overload` anchor); every compiler-graded cell at 100%; ajv's 3
union-member rows the one open sighting (n=1).

**ADR-094 (2026-08-28):** a stale `hobbes` symlink into an older
checkout ran lane B on the host (canary sentinel proved it). Now
`.mcp.json` → `sandbox/knowledge-serve` runs the image's proxy in a
read-only offline container; artifacts carry `built_by`; the proxy
prints its build. **Rebuild the image after rebuilding the proxy**
(C-65). Max still holds the PATH fix on his box (`~/.local/bin/hobbes`
→ `~/hobbes/...`). The ingest-in-sandbox half is parked
(`future_additions.md`).

**D5 and D6 are closed (ADR-093, 2026-08-28, Max reopened them):**
under `strict` a planner that names nothing resolvable is re-planned
once, then a plan error (`lexical-fallback` is the third strict
status); a lexical seed on a hub is context, not work
(`seeds_context`). Validated with no model; 960 pytest green plus the
known environmental failure. **Next:** the removal A/B on a cleared 7B
run (now un-confounded on the D5 axis; still needs n for O4's planner
variance); collaborator setup (`docs/workstreams.md`).

**Three embedded calls for Max to ratify** (ADR-092 §"Decisions"):
contain-all lane B vs executing-only; symlink targets mounted at
identical paths vs link rewriting; one image extended vs a slim ingest
image. A fourth from the build: network by phase separation (fetch
containers) rather than route filtering, which rootless podman cannot
do. Each independent.

**Practical notes for the next session:** the image must be built on
the box (`sandbox/README.md`); `podman build` takes ~4 min. The
`lane_b`-marked tests skip without it. The pre-existing environmental
failure `test_venv_environment_lists_the_venvs_own_distributions` now
runs contained and still fails on its own assertion (the fixture venv
holds only `pip`) — untouched. The uncontained escape hatch **executes
the canary fixture's build script on the host** when this repo is
ingested with it set; that is the disclosure working, not a bug.

## STANDING POLICY (Max) — read before doing anything

1. **Experiments are PARKED again (2026-08-24).** The one cleared run
   (the ADR-085 validation pair) has happened. No further run of any
   size without a fresh, explicit go from Max. The mechanical half of
   the restructure is done (ADR-091) and D5/D6 are closed (ADR-093);
   the register is fully discharged.
2. **The 7B is the instrument, by speed not capability.** Validate
   every mapping/architecture change on the 7B or with no model at all
   (replay over stored specs/handoffs) first. The compute-economics
   gate (Max, 2026-08-22; BUILDLOG): ≥15 min of evaluation before any
   run over 30 min; state the GPU-hours first.
3. **P12 (ADR-082): a Hobbes test decomposes, or it is not a Hobbes
   test.** Since ADR-086 the machinery enforces the label: an aided run
   is recorded `arm=model+prompt` on every path.
4. **The 27B is untouched** until the mapping fixes are built and
   validated on the 7B, and only on a decontaminated set.

## WHERE THE PROGRAMME STANDS (2026-08-24)

- **ADR-085 is built and demonstrated once end to end** (sphinx:
  planner re-plan → owned requirements → proposal-free brief →
  coverage held). The E-numbers: 7B planner wrote `requirements:` 0/5
  first-attempt, 3/5 after the one strict re-plan; the lexical
  fallback bypassed coverage on the other 2 (defect D5).
- **The removal A/B produced no usable signal** — confounded by D5 and
  by planner-path variance across identical greedy runs (O4). Re-run
  after the restructure, on the D5 fix, with n big enough to split the
  variance out.
- **0/5 solved, both passes** — recorded, and not the measure; the 7B
  failure mode remains implementer execution (hallucinated anchors,
  requirement-descriptions rendered as code), not refusal.
- **The run was judged on machinery behavior and it mostly held**:
  strict stopped nothing incorrectly, the re-plan recovered every
  usable planner, fast honest failure worked (sphinx implement 37 s).

## THE RESTRUCTURE WORKLIST — `docs/adr085-validation-run.md`

Eight defects. **Fixed 2026-08-27 in ADR-091**, all in
`agent/loop.py` unless stated, validated by the hermetic loop tests
(no model):

- **D1** one fit per elide cycle — the reported input count is a lower
  bound; a second overflow elides.
- **D2** mutating and short (< 2× placeholder) results are never elided.
- **D3** an elided read revokes the path's edit ticket until re-read
  (the repeat guard forgets the elided call too).
- **D4** read + edit of one path in one turn is refused.
- **D7** the duplicate-symbol record is scoped to its files' common
  directory and worded per lane (`scip/index.mjs`, `scipsource.py`).
  *Correction:* the sklearn residue was in-repo (skeletons/ and
  solutions/ of a tutorial), not foreign — the C-28 drop was right.
- **D8** an implementer that edits and ends in prose gets one
  `NUDGE_HANDOFF`; every unit record carries `handoff: handoff |
  reflection-only | missing`.

**Fixed 2026-08-28 in ADR-093** (`run/stages.py`, `run/coverage.py`,
`derive/impact.py`, `derive/partition.py`, `derive/changespec.py`):

- **D5** a rambling planner gets the one re-plan (`fallback_note`),
  then `strict` raises `PlanCoverageError(lexical-fallback)` with the
  record written; `assign` runs on the lexical seeds and says so.
- **D6** `ImpactSet.seeds_lexical` → `unit_modules` drops a lexical
  seed that is a hub; `seeds_context` in the spec; every-seed-a-hub is
  a `SeedError`.

The removal A/B is still to be re-run (needs a larger n); nothing has
run on the 7B since the validation pair. Observations that are
findings, not defects (knowledge tools unused at the 7B rung — derived
context is push-only there; requirement-text rendered as code; O4
planner variance) are in the same file.

## A SECOND, CLEARED TRACK — the oracle-grading lane (2026-08-25): both phases done

Max cleared ADR-089 with every recommendation (D-O1–D-O6). **Phase 1
(O1–O4) and phase 2 (O6, O7) are built and run, all on 2026-08-25.**
The harness is `bench/oracle/` — one binary (`export | go-rta |
py-trace | rust-mir | grade`), the TS oracle in `ts/`, the Python
tracer in `py/`, the Rust MIR driver in `rust/` (nightly with
`rustc-dev`; `cargo +nightly build --release` once), `run-cell.sh` for
any of the four languages; five fixtures are the self-tests. Records:
`docs/oracle-cells/` (one per cell), `docs/oracle-misses.md` (what
hurts most, by class), `docs/oracle-defects.md` (H-1..H-16 — the
harness's own errors, most of them false verdicts against Hobbes caught
by fixtures or triage), `docs/oracle-preregistration.md` graded in
`extraction-evidence.md`.

**Where the numbers stand.** Every semantic tier graded is 100%: Go
(this repo 1,278; dagger 19 modules 9,851), TS (kbet 630), Rust
(rust_proj 17; dagger `sdk/rust` 3,592 after ADR-090); Python is trace-graded (C-60:
3,291/3,490 confirmed, 0 wrong on the executed semantic slice,
recall-against-executed 86.2% / 96.9% named). The syntactic fallback is
priced everywhere it was reached (C-7): 0/3 Go, 6/6 Python, 12/30 Rust
wrong. The misses are **C-58** on every language — closures,
function values, interface/extension-trait dispatch (70–81% of misses)
— plus Rust's generated-code class (derives, builders, proc-macro
tokens: 46 of dagger's 69).

**Defenses (2026-08-25, Max):** every cell record carries a signed
direction-of-fix line on regrade, and every cell runs the poison check
(`grade --poison`: seeded wrong edges, 0 falsely confirmed on every
stored cell). private-repo-A and qwen-pathology are out of the base.

**Open on the lane, none blocking:** O5 (dagger `sdk/typescript`);
xarray under a trace when a SWE-bench workspace exists again; the dagger
Go root on a ≥32 GB box (H-9; P8/P9); Rupta as a time-boxed reference
lane (C-61 says what it may and may not produce); H-11 cosmetic.
**W1 from the lane — done (ADR-090):** the two syntactic-fallback
name-match shapes are vetoed (a bare name bound in a spanning scope
never resolves to a module-level namesake; a Rust bang binds only to a
macro) and C-58 is surfaced *partial* as the `below-floor` tail class
(`floored` on the coverage row; `list_blind_spots` marks it
not-modelled). O6 regraded: 0 wrong edges on the executed slice, 4
not-exercised suspects. dagger `sdk/rust` regraded after re-ingest: **3,592/3,592, 0
contradictions** — every compiler-graded cell on every language is now
at 100% on every tier it was reached on. dagger's re-ingest sizes
`below-floor` at go 4,114 / ts 247 / python 117 / rust 102. Cell outputs:
`~/.hobbes/bench/oracle/{hobbes-py,rust_proj,dagger-rust,dagger,dagger-before}/`.

## DONE 2026-08-28 — the 2026-08-27 grading loop, triaged (kept for the record)

Seven cell records in `docs/oracle-cells/*-2026-08-27.md` (toml, click,
memchr, mux, fzf, ajv, cheerio), written by single-purpose agents,
numbers verbatim, **not yet triaged** into `oracle-misses.md` /
`extraction-evidence.md`. `docs/oracle-defect-review.md` is now the
method: a new H-entry is assigned to a root in its seen tally in the
same commit; every cell record quotes its triage ratio (A-8).
Two things a triage session will meet first: fzf's 87 contradicted
edges are all the syntactic fallback binding a call to a package-level
function that a local `func` literal shadows (the ADR-090 veto's Go
shape, not yet vetoed there); mux's 3 contradicted are calls through a
package-level func variable; cheerio's 36 are a spec-local `parse`
shadowing `src/parse.ts` (the same shadowing shape, in TS); ajv's 3
are an `If` override vs the base method. **H-17 is closed** (A-4/5/6);
what it left is **C-63** — lane A does not count `obj[key]()` as a
call site at all (unsurfaced, product side), the one new product
finding of the day. Open on the review: A-7 optional, A-9 parked.

## HOW TO INSPECT / MEASURE (no GPU)

- The pair's records: `~/.hobbes/bench/adr085-validate-7b{,-control}/`
  (`records.jsonl`, `detail.coverage`, `detail.stages`); per-unit
  sessions under `~/.hobbes/sessions/<task>-<unit>/` (`brief.md`,
  `transcript.jsonl`, `calls.jsonl` — the D1 grind is visible in
  sklearn-A's u1/u5 rows).
- Coverage replay (no model): `hobbes.run.coverage.imperatives_unmentioned`
  over stored handoffs; `scripts/brief_sizes.py` for rendered-context
  size; re-derive stored specs with `derive_plan(..., lexical=False)`.
- The D1 arithmetic reproduces without GPU: the overflow message's
  input count is `window − max_tokens + 1`; simulate the fit loop.

## IF/WHEN A RUN IS CLEARED AGAIN (reference only — parked)

Same shape as the validation pair: warm the endpoint (short-timeout
`/models` loop; Modal cold start ~10 min), then `hobbes bench run
verified.jsonl --secrets secrets.txt --id <ids> --arm harness --runtime
openai --llm-base-url <7B URL> --model Qwen/Qwen2.5-Coder-7B-Instruct
--session-bin go/bin/hobbes-session --out ~/.hobbes/bench/<name>
--stages plan,implement,verify --coverage strict --max-units 10
--max-turns 40 --max-tokens 1536 --parallel auto --evaluate
--human-first spawn` (+ `--proposal-in-brief` for the control arm
only). Evaluator on the local rootless-podman socket (`systemctl --user
start podman.socket`; never `--eval-modal`, C-50). State GPU-hours
first.

## Housekeeping

- Commit to `main`; never `git push` (Max publishes). One ADR per design
  decision; one BUILDLOG entry per session; every concession a `C-n` in
  the right segment file under `docs/constraints/`. Rewrite this doc; do not append to it.
