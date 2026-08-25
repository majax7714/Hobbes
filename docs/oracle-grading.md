# Oracle grading — precision and recall for the call graph against answer keys we do not control

**Status: phase 1 built and run (O1–O4, 2026-08-25; the dagger root
waits on a bigger box); phase 2 (§6 Python traces, §7 Rust MIR) is the
next section's work — unbuilt.** This document is the context for the
build session(s) that implement it. **Owner:** Max. **Scope:** bench tooling only
— no product change. Reads with: architecture §3.8 (the claim table),
`extraction-evidence.md` (the evidence log), `docs/constraints/`,
ADR-048/049/050 (dagger), ADR-037/040 (the existing hand-checks). Decisions
D-O1–D-O6 (§12) are carried in ADR-089.

*Revision note.* The first draft declared Python and Rust oracle-less,
inherited from a competitor's framing. A search (2026-08-25) falsified
that: runtime-trace oracles are the research-standard ground truth for
dynamic languages, Rust admits a compiler-authoritative partial oracle plus
an independent research analyzer, and a directly relevant
execution-verified benchmark (TraceEval) shipped in 2026. §2 now carries an
oracle taxonomy, §6–§7 the new lanes, and §15 the provenance.

## 1. Why this exists

Hobbes' headline extraction metric — capture % of detected call sites — is
neither precision nor recall. The denominator is sites Hobbes detected (a
floor by design), and a resolved site is not a verified-correct binding.
The evidence base for correctness is currently:

- **Hand-checks, small-n, self-selected.** Go 20/20, Rust 33/33, kbet
  20/20, private-repo-A's full JS edge set — all 100%, but at n=20 the
  exact 95% lower bound on true precision is ~83%, at n=33 ~89%. Every
  check so far is consistent with anything from ~85% up. The samples also
  have no documented selection procedure.
- **Lane agreement**, which is real machinery (36,703 dual-resolved sites
  on dagger, 258 disagreements, decomposed) but is two of our own methods
  agreeing. Shared blind spots are invisible to it, and it covers only
  dual-resolved sites.
- **The largest measurement is the least verified.** dagger (265k sites,
  161k edges) carries zero graded edges, documented deliberately.
- **Downstream validation is uncounted.** Inspecting agent-loop prompts
  against benchmark assignments, and field use as an edge tool, have
  surfaced no wrong edge — but neither has a denominator, a selection
  rule, or a log. That is anecdote, and it stays out of the evidence file
  until §13 gives it a countable form.

The fix is **an answer key we do not control.** This gives us, for the
first time:

- **Precision at scale** — every edge graded, not 20.
- **Recall** — a number Hobbes has never had in any form: of the true call
  graph (or a well-defined executed slice of it), how much did we find.
- **A graded dagger** — the scale evidence and the accuracy evidence
  finally coincide in one repo.

## 2. Oracle taxonomy and scope

An **oracle** here means: an edge source that is (a) independent of
Hobbes' machinery, (b) grounded in something authoritative about the
language, and (c) regenerable by anyone with the toolchain. Three kinds
qualify, with different grading semantics:

- **Resolution oracles** — the language's own checker resolves each call
  site. TypeScript via `tsc`; Rust's static/generic dispatch via
  monomorphized MIR. Authoritative per site; can confirm and contradict.
- **Reachability oracles** — the language's own toolchain computes a
  whole-program call graph from roots. Go via
  `golang.org/x/tools/go/callgraph/rta`. Confirms, contradicts (with the
  unsoundness caveat, §3 rule 4), and yields recall.
- **Runtime-trace oracles** — the interpreter/instrumented binary records
  edges actually taken while running the test suite. Python via
  `sys.monitoring` (PEP 669); optionally Rust via instrumented builds. The
  runtime is the ultimate authority, but asymmetric: an observed edge is a
  fact, an unobserved edge is not a falsehood. Confirms and establishes
  definite misses; never contradicts (§3.1). This is the research-standard
  ground-truth method for dynamic languages — the Jarvis/PyCG ground
  truths, DyPyBench, and TraceEval are all built this way.

**Not oracles, ever:** peer static analyzers (PyCG, Jarvis, Scalpel for
Python). They are competitors with their own error profiles — the
literature has them disagreeing with each other by tens of points — and
grading against one is grading against a peer, the failure mode the whole
lane exists to escape. One partial exception in §7: Rupta may run as a
labelled **reference lane** (independent, serious, but not authoritative),
whose disagreements feed triage, never a precision-against-oracle number.

**Independence trap, named once:** anything Pyright-derived is not an
oracle for Hobbes — lane B's `scip-python` is built on Pyright, so a
"Pyright oracle" would grade lane B with its own engine.

**Scope:**

- **Phase 1 (this build):** Go (RTA), TypeScript (`tsc`). Unchanged from
  the first draft.
- **Phase 2 (designed here, built after O4):** Python runtime-trace oracle
  (§6); Rust MIR resolution oracle, optional Rupta reference lane, optional
  trace lane (§7).
- **Out of scope, still:** HCL / cross-layer edges (different grain; stays
  hand-verified); JS-without-types (`tsc` under `allowJs` collapses; grade
  TS zones only and say so).
- Hand-grading remains the method for what no oracle reaches — unexecuted
  Python/Rust paths, HCL — per the §11 protocol-upgrade note. Misses are
  kept by class, per cell, in `docs/oracle-misses.md`; the harness's
  and oracles' own defects in `docs/oracle-defects.md`.

## 3. Metrics and definitions

**Edge grain:** a graded edge is *(call-site position, callee declaration
identity)*. This matches Hobbes' own grain (site → declaration) and the
oracle's (Go `callgraph.Edge` carries `Site`; `tsc` resolves per call
expression; `sys.monitoring` CALL events carry the instruction offset).

Per cell, four buckets over Hobbes' emitted edges (resolution and
reachability oracles):

- **Confirmed** — the oracle has the same (site, target).
- **Contradicted** — the oracle resolved that site and Hobbes' target is
  not among its targets.
- **Oracle-silent** — the oracle could not speak about that site
  (unresolvable, un-analyzed under the build config, dynamic beyond its
  model). Charged to nobody, reported at full size.
- **(Recall side) Missed** — oracle (site, target) pairs Hobbes did not
  emit.

**Metrics:**

- `precision-against-oracle = confirmed / (confirmed + contradicted)` —
  the name matters; see the unsoundness rule below.
- `recall = confirmed oracle pairs / all oracle pairs`.

**Rules, each a constraint candidate (§11):**

1. **The pair is always reported together.** Precision or recall alone is
   trivially gamed and never quoted solo.
2. **Recall is never pooled or compared across cells.** It is driven by
   how many roots/entry points the oracle had (or what the tests covered),
   not tool quality. Every cell reports its root count — or its coverage —
   next to its recall.
3. **Oracle-silent is charged to nobody and its size is printed** — a cell
   where the oracle is silent on 40% of sites is a different kind of
   evidence than one where it speaks on 99%.
4. **A contradicted edge is very strong evidence, not proof.** RTA is
   unsound under reflection, `go:linkname`, plugins, cgo; `tsc` under
   `any`-typed and element-access calls. A genuinely dynamic edge can land
   in the contradicted bucket. Hence the metric's name.

**Grading by confidence tier.** Hobbes edges carry tiers (semantic /
syntactic / dynamic). Grade each tier separately in every cell. The
expectation to pre-register (§10): contradictions concentrate in the
syntactic-fallback tier — this run prices the C-7/C-8 fallback floor
instead of estimating it from lane disagreement.

### 3.1 Trace-oracle semantics (asymmetric)

A trace oracle replaces the buckets above:

- **Confirmed** — Hobbes' (site, target) was observed at runtime.
- **Missed** — an observed (site, target) is absent from Hobbes' graph. A
  definite recall failure: the program did it and we did not draw it.
- **Unobserved** — a Hobbes edge never exercised. Charged to nobody: the
  site may be uncovered, or covered but that branch/receiver never taken.
- **Suspect** — a Hobbes edge at a site that *did* execute, where every
  observed resolution went elsewhere. Triage queue, never
  auto-contradicted — a different input could still take Hobbes' target.

**Metrics:** `recall-against-executed = confirmed observed pairs / all
observed pairs` (exact, over a stated denominator); **confirmation rate**
over Hobbes edges (a coverage-limited signal, not precision). Constraint
candidate: *runtime-observed edges are facts; runtime absence is never
falsity.* Every trace cell reports its **coverage line** — fraction of
Hobbes sites the trace spoke about, plus suite line coverage — and the
union-of-runs count (nondeterministic suites: union over N runs, N
stated).

## 4. The Go oracle

**Build.** Per module: `packages.Load` (`NeedDeps | NeedTypes | NeedSyntax
| NeedTypesInfo`) → `ssautil.AllPackages` → build SSA →
`rta.Analyze(roots)`.

**Roots.** RTA needs entry points. Roots = `main` functions plus test
binaries (`_test` mains). A library module is analyzed through its test
binaries only — that is a different question than analyzing a binary, so
a cell states which it was. Report the root count in every cell (rule 2
depends on it).

**Monorepo handling.** One cell per Go module (dagger: 25). The replaced
`./sdk/go` is inside the loaded program, so the 7,322 semantic
core/integration → sdk/go edges from ADR-049 — the C-33 lift — get graded,
not just counted.

**Normalization (the real work):**

- **Synthetic functions.** SSA emits wrappers, thunks, and bound-method
  closures that exist in the call graph but not in source. Unwrap every
  synthetic node to its source declaration before matching
  (`ssa.Function.Origin()` / wrapper unwinding). An edge through a wrapper
  matches if the unwrapped endpoints match.
- **Generics.** Instantiations collapse to the source declaration
  (`Origin()`); multiple instances of one generic function are one
  declaration identity.
- **Closures / anonymous functions.** Matched by declaration position, not
  name — Hobbes and SSA name them differently.
- **`init` and package-level var initializers.** Decide once whether they
  are in or out of the graded set; either is fine, silently mixing is not.
- **Build tags.** One run under the default tag set per platform of the
  measurement box. Sites excluded by tags are oracle-silent. Report the
  tag set. (This is the known lane-disagreement bucket — 126 of dagger's
  138 — now graded instead of noted.)

**Positions.** `token.Position` from the loaded FileSet, normalized to
repo-relative paths. Column conventions differ between Hobbes lanes and Go
tokens — define the tolerance explicitly (same file + same line +
declaration-span overlap), and log every match that needed tolerance.

## 5. The TypeScript oracle

**Build.** Per TS zone: `ts.createProgram` from the zone's own tsconfig,
resolving against the provisioned `node_modules` trees already built for
ADR-050 (`~/.hobbes/cache/npm`). Zones declined at ingest for C-34 (no
lockfile) are declined here too, with the same reason string — the oracle
grades what the product indexed, under the same environment.

**Per call site** (`CallExpression`, `NewExpression`,
`TaggedTemplateExpression`, decorators): `checker.getResolvedSignature(node)`
→ `signature.getDeclaration()` → declaration position. No resolved
signature, or a signature with no declaration (synthetic union apply,
`any`) → oracle-silent.

**Overloads.** Hobbes' target is correct if it is *any* declaration of the
resolved symbol (overload set membership), not only the exact overload
`tsc` picked. Stricter is defensible; pick one, state it, keep it.

**Position convention.** Define the oracle's declaration position rule
explicitly (identifier start, 1-based line). This is the same ambiguity
behind the 131 decorator line-convention off-by-ones in lane disagreement
— the oracle lane is where that convention gets written down once and both
product lanes get measured against it.

**External targets.** Calls resolving into `node_modules` declarations:
graded if Hobbes emitted an edge for the site (its external-origin
classification vs `tsc`'s resolution is checkable), oracle-silent for
recall purposes if we scope recall to in-repo targets. Decide in D-O3.

## 6. The Python runtime-trace oracle (phase 2)

**Why traces and not a static oracle.** No sound static call-graph oracle
exists for Python — that part of the original claim held. But the
research-standard ground truth is exactly a runtime trace: the
Jarvis/PyCG ground truths were built from `python -m trace` call traces
(plus manual augmentation), DyPyBench compares static graphs against
DynaPyt dynamic graphs, and TraceEval (2026) builds an entire
execution-verified multi-language corpus on tracer validation. The
interpreter is an authority we do not control and cannot tune.

**Mechanism.** `sys.monitoring` (PEP 669, CPython 3.12+, low overhead):
register for `CALL` events, record (caller code object, instruction
offset, callee code object), map offsets to positions via
`co_positions()`, callee code objects to declaration positions via
`co_filename`/`co_qualname`/`co_firstlineno`. This yields **site grain**,
which `python -m trace` (function grain only) cannot. Run the target's own
test suite under the monitor.

**Filtering**, per the literature's protocol: drop interpreter-internal
frames (`_frozen_importlib`, site machinery), frames outside the repo, and
C-extension callees (no Python declaration to match — count them, report
them as a trace-silent class). Import-time module-body execution: decide
once whether module-level calls are in the graded set; state it.

**Semantics:** §3.1 applies — confirmed / missed / unobserved / suspect,
recall-against-executed, mandatory coverage line, union over N runs.

**What this buys against current evidence:** the SWE-bench workspaces'
Python capture (53–72%) has zero edge-accuracy evidence; a trace cell on
one of them converts suite-covered edges into exact recall and a confirmed
set, at the scale of a real repo, without six person-months of manual
augmentation (which is what full static ground truth cost the Jarvis
authors — we do not attempt it; we scope to the executed slice and say
so, per P11).

## 7. The Rust oracle (phase 2)

**Primary: MIR resolution oracle** — the compiler as authority on static
dispatch. After monomorphization, `rustc` has resolved every static and
generic call; `dyn Trait` and fn-pointer calls are explicitly marked
(virtual/indirect call terminators). A small rustc driver (nightly,
pinned) walks the resolved calls at MIR level — the approach prior art
like `rust-callgraph` takes — emitting (site position, callee
declaration) for resolved calls and marking dynamic sites oracle-silent.
Contradiction-capable on the static portion, exactly like `tsc` on typed
calls. Generic instantiations collapse to the origin declaration, matching
§4's Go rule.

**Rejected for this purpose:** LLVM-IR-level tools (`cargo-call-stack`):
post-optimization graphs lose source grain — inlining erases the exact
edges Hobbes draws — and the tool is embedded-focused, fat-LTO-bound, and
nightly-fragile. Wrong layer for a source-grain grader.

**Reference lane, optional:** Rupta (rustanlys/rupta; CC'24, CGO'25) — the
first context-sensitive pointer analysis for Rust, on MIR, built for call
graph construction, open source, independent of us. It covers what the MIR
oracle cannot (`dyn` dispatch via points-to), but it is a research
analyzer with its own trade-offs, not an authority. If run: its output is
labelled *reference*, disagreements feed triage, and no
precision-against-oracle number is ever computed against it. It is also
nightly-pinned; expect toolchain friction and time-box it.

**Trace lane, optional:** `uftrace` supports Rust (instrumented builds via
`-pg`/`-fpatchable-function-entry`, or dynamic prologue patching); run the
crate's tests, §3.1 semantics. Build config differs from release — fine,
because Hobbes measures source grain and an edge inlined away in release
still exists in source semantics; the cell states the build flags.

**Pilot cell:** `rust_proj` — 33 edges, currently 100% hand-checked
(ADR-040), all-semantic. The MIR oracle must confirm all 33; any
divergence is a harness finding first. Then dagger's rust (8,595 sites) as
the scale cell.

## 8. The matcher

**Inputs:** (a) a Hobbes graph export per cell — every call edge with site
position, target declaration position, confidence tier; add an export
subcommand if the current dump lacks any field. (b) The oracle edge set,
same shape, tagged with its oracle kind (resolution / reachability /
trace) so the bucket semantics switch correctly.

**Pipeline:** normalize paths → normalize positions → build declaration
identities (file, span) with the tolerance rules of §4–§7 → set-match at
(site, target) grain → bucket per oracle kind → report.

**Report per cell:** confirmed / contradicted-or-suspect / silent counts
and rates, per tier; root count (Go) or coverage line (trace cells);
recall with miss decomposition — at minimum the buckets the field says
dominate: dynamic/interface dispatch, and dispatch-with-closure. Also emit
the raw contradicted/suspect rows (site, Hobbes target, oracle targets) —
those are the triage queue, and published rows are the difference between
a number and evidence.

**Triage protocol** for contradictions and suspects: read the site from
source. Verdicts: **hobbes-wrong** (a real extraction defect → issue
filed), **oracle-unsound** (reflection/linkname/`any` — logged, not
charged), **not-exercised** (trace suspect whose target is plausible on an
untaken path — logged, charged to nobody), **match-defect** (normalization
bug → fix matcher, rerun cell). A cell's number is only final after its
triage is complete or a sampled triage is documented as sampled.

**Languages** (per the split-by-focus rule, D1): the Go oracle extractor
must be Go (`x/tools` is Go-only); the TS oracle extractor must be
TypeScript (compiler API); the Python tracer must be Python
(`sys.monitoring`); the Rust MIR driver must be Rust (rustc APIs). The
matcher/reporter is shared and language-neutral — Go or Python, whichever
the export tooling already leans toward; keep it one binary/script with
cells as data, not per-cell scripts.

## 9. Cells and order

| Milestone | Cell | Why / exit |
|---|---|---|
| **O1** | `minigo` + `twomod` fixtures | Truth is hand-computable. Harness self-test: matcher must land exactly (every fixture edge confirmed, zero tolerance surprises) before any real cell. Exit: fixture grading in the test suite. (`twomod` — a two-module Go fixture — does not exist yet; O1 adds it.) |
| **O2** | hobbes repo, Go zone | First real cell. Small (3,707 sites), familiar. *(Done 2026-08-25. The ADR-037 20/20 could not serve as a cross-check — its edges were never named — and was retired in favour of the oracle.)* Triage protocol shakedown. |
| **O3** | kbet TS zones | The provisioned-deps happy path. *(Done 2026-08-25: 630/630 against the zone's own `tsc`; the V2.M3 20/20 retired alongside Go's.)* |
| **O4** | dagger Go modules | The payoff: 237k sites graded, per-module cells, C-33's join graded, the 126 build-tag disagreements priced. |
| **O5** (optional) | dagger `sdk/typescript` | The 70.3% zone under the provisioned cache. |
| **O6** (phase 2) | Python trace cells: hobbes' own Python zone under its suite (dogfood), then one SWE-bench workspace with strong coverage and clean ingest (xarray) | First trace-oracle cells; minipy-style fixture self-test first if one exists, else add one. Exit: coverage line + recall-against-executed on the record. |
| **O7** (phase 2) | Rust: `rust_proj` MIR oracle (must confirm ADR-040's 33/33), then dagger rust | Compiler-authority grading for the language with the thinnest evidence base. Rupta/trace lanes only if time-boxed setup succeeds. |

Each cell's runtime and machine cost gets logged — the harness is only
useful if rerunning a cell is cheap enough to do after every resolver
change.

## 10. Pre-registration

Before O2 spends anything, commit (own commit, before the run)
predictions:

- A precision-against-oracle band per language (state one; the honest
  prior from the hand-checks is "somewhere above ~85%").
- Where misses concentrate (predict: interface dispatch dominates the
  recall gap).
- Which tier carries the contradictions (predict: syntactic fallback).
- For O4: whether the 126 build-tag lane disagreements grade as
  oracle-silent or contradicted.
- Before O6: a recall-against-executed band for Python, and a predicted
  suspect rate.

Grade the predictions in the evidence file, including the ones that miss.
This is also the dry run for the habit the harness benchmark will need.

## 11. Evidence, claims, and register updates

- Rows land in `extraction-evidence.md`, same commit as the run, per the
  file's own rule. Oracle-graded is a **new kind of Verified content** —
  the line reads e.g. "compiler-graded: N edges, precision-against-oracle
  X%, recall Y% at R roots; not hand-checked beyond triage" or
  "trace-graded: recall-against-executed X% over E observed pairs at C%
  coverage". Never let an oracle row imply hand-verification, a trace row
  imply full recall, or vice versa.
- §3.8 gains rows only for what a run licenses (P11): per-cell,
  per-language, at the grain measured. An O4 result licenses a dagger-Go
  row, not a Go row; an O6 result licenses an executed-slice claim, not a
  repo claim.
- **Constraint candidates:** the four rules of §3, plus §3.1's
  trace-asymmetry rule (observed edges are facts; absence is never
  falsity) and the reference-lane rule (peer analyzers never produce a
  precision-against-oracle number). Register as `C-n` entries in the
  register's relevant segment (`docs/constraints/`) when the lane lands.
- ADR for the lane's existence and the D-O decisions below: ADR-089.
- **Follow-on, separate work:** upgrade the hand-grading protocol for what
  no oracle reaches — unexecuted Python/Rust paths, HCL — to
  stratified-by-resolution-strategy, seeded sampling with published
  per-row verdicts, n≥30 per cell. Not part of this build; noted so it
  isn't forgotten.

## 12. Decisions (pick before building)

Carried, with recommendations and status, in ADR-089.

- **D-O1 — Go algorithm.** RTA (recommended: the field-standard oracle
  choice, comparable to published numbers, fast enough to rerun) vs VTA
  (tighter oracle, stricter grading, slower) vs running both and reporting
  the band. Recommendation: RTA now, VTA as an optional second arm on O2
  only to measure how much the choice moves the number.
- **D-O2 — harness home.** `bench/oracle/` as its own module(s)
  (recommended: product stays pure, mirrors the product/evidence-repo
  separation) vs a `hobbes oracle` CLI subcommand.
- **D-O3 — dispatch and external scoring.** For a site where the oracle
  has multiple targets (interface dispatch): Hobbes' single target scores
  confirmed on set membership (recommended), and recall counts every
  oracle pair (which prices the dispatch ceiling honestly). External
  (`node_modules` / stdlib) targets: in or out of the recall denominator —
  recommended out for in-repo recall, with the external-confirmation rate
  reported separately.
- **D-O4 — position/overload conventions.** Write the declaration
  position rule and the overload rule (§5) into the harness README as
  normative; both product lanes get measured against them.
- **D-O5 — Python trace mechanics.** `sys.monitoring` at site grain
  (recommended) vs `python -m trace` at function grain vs adopting DynaPyt.
  Which suites: the repo's own tests (recommended — the environment Hobbes
  already provisions) vs authored drivers. Module-body calls in or out of
  the graded set.
- **D-O6 — Rust path.** MIR resolution oracle first (recommended: compiler
  authority, source grain, matches Hobbes' edge model) vs Rupta-first vs
  trace-first; whether Rupta ships as a reference lane in phase 2 at all
  or waits (recommended: time-box one setup attempt, drop without ceremony
  if the toolchain pin fights back).

## 13. Appendix — field-report tally

Field use ("no wrong edge encountered while using Hobbes as an edge tool")
becomes countable with a one-line log per incident, kept in
`extraction-evidence.md` under its own section: date, repo, site, verdict
(caught-real-edge / wrong-edge / inconclusive). **Floors only, never
rates** — no denominator exists for field use and none should be implied.
Same for benchmark-assignment prompt inspections going forward: if one is
worth doing, it is worth a line with a count. Uncounted inspection stays
out of the file entirely.

## 14. Definition of done

**Phase 1:** O1–O4 complete; O2/O3 cross-checks against the existing
hand-checks pass (any failure is a finding, triaged before proceeding).
Evidence rows written same-commit; §3.8 updated within license;
pre-registration graded and committed. Constraint candidates registered;
ADR written. Rerunning any cell is one command, and the O2 cell reruns in
the suite's tolerance for a post-resolver-change check.

**Phase 2** (tracked separately, not a gate on phase 1): O6–O7 with their
own pre-registrations; the trace-asymmetry and reference-lane constraints
registered before the first phase-2 row lands.

## 15. Appendix — oracle provenance (search of 2026-08-25)

What the search found, so the scope claims above carry their sources:

- **Go:** `golang.org/x/tools/go/callgraph/rta` (unchanged; also `vta` in
  the same package tree).
- **TypeScript:** `tsc` compiler API resolution (unchanged).
- **Python** — no sound static oracle confirmed, but static peers exist
  and disagree with each other by design: PyCG, Jarvis
  (pythonjarvis.github.io; arXiv 2305.05949 — its ground truth is
  trace-built plus 6 person-months of manual augmentation), PyPt, Scalpel,
  HeaderGen. Runtime-trace ground truth is the field standard: DyPyBench +
  DynaPyt (arXiv 2403.00539), `sys.monitoring` (PEP 669, 3.12+),
  `python -m trace` (function grain).
- **Rust:** Rupta — context-sensitive pointer analysis + call graph
  construction on MIR, open source (github.com/rustanlys/rupta; CC'24 doi
  10.1145/3640537.3641574, CGO'25 stack-filtering follow-up); the same
  papers name Rurta (RTA-style) and Ruscg (static-dispatch-only)
  baselines. `rust-callgraph` (heinzelotto) as prior art for the
  rustc-driver resolved-call walk. `cargo-call-stack` evaluated and
  rejected (LLVM-IR grain, embedded focus, fat-LTO, nightly-fragile).
  `uftrace` supports Rust and Python tracing.
- **TraceEval** (arXiv 2605.11006, 2026): execution-verified
  multi-language call-graph benchmark — 10,583 tracer-validated programs
  from 1,600+ repos, Python/JS/Java today, Go/Rust/TS tracers planned,
  pipeline released as a runnable artifact. Not built for grading
  extractors, but the tracer protocol and corpus are directly reusable as
  external cells later, and it is the precedent that execution-verification
  scales without manual ground-truth authoring.
