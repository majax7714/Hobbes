# Extraction evidence — the repos Hobbes has been tested against

**Why this file exists (Max, 2026-08-18):** "carry a repos tested with
stats doc somewhere in the repo for honesty and proof." The plan is that
once extraction is properly validated, most development moves off of
testing and Hobbes work becomes last-commit additions — which makes the
extraction layer's evidence base the thing everything else stands on,
and an unwritten evidence base is a claim, not a proof.

**How to read this file.** One section per repo, newest results first
within it. Every number is **of detected call sites** (C-1/C-4/C-5 are
in no denominator here — the count is a floor, never "of the repo").
A row licenses exactly what it measured (P11): "ingested cleanly at
265k sites" is evidence about the machinery at scale, **not**
hand-verified edge accuracy — and rows say explicitly which they carry.
**Leaving edge verification out is fine as long as it is documented**
(Max, same direction), so the *Verified* line is mandatory in every
section, including when its content is "none". Architecture §3.8
remains the *claim* table — what "supported" means; this file is the
*evidence log* behind and beyond it. Update it **in the same commit**
as the test session that produced the numbers.

Fixture repos (`miniapp`, `minits`, `minigo`, `minirust`, the twomod
scratch fixture) are exercised by the test suite on every run and are
not logged here — this file is for real repos.

---

*Retired from the base 2026-08-25 (Max): private-repo-A (a private
Python + JS + Terraform repo) and qwen-pathology (Python) — a handful of
hand-checked edges each, too little weight to carry a row and confusing
beside compiler-graded cells. Their sections are gone; the rules they
produced (the tail's `import-binding` class, the C-27 venv check, the
HCL pack's `packages` edge) keep their citations in code and register.*

## hobbes (this repo — dogfood, continuous)

Six languages in its own graph (`go, hcl, javascript, python, rust,
typescript`). Re-ingested every session; the suite's degraded path
(lane B off) runs on every test invocation.

| Date | Numbers |
|---|---|
| 2026-08-25 (**O6 regraded after ADR-090**, same suite, 1 run) | 3,495 edges — **3,302 confirmed, 4 suspect (all semantic, not-exercised), 189 unobserved**; the syntactic tier's six wrong edges are gone (the scope veto), no executed syntactic edge remains; recall-against-executed **86.3% (3,302/3,828)**, confirmation rate 94.5%, suspect rate 0.1%. `below-floor` on this repo: go 3, python 35, ts/js 10 sites |
| 2026-08-25 (**oracle lane O6**, ADR-089 phase 2) | **Python zone trace-graded against the interpreter** (`bench/oracle`, [cell record](oracle-cells/hobbes-py-2026-08-25.md)): the suite (907 tests, 2 runs) under `sys.monitoring`; 3,490 Hobbes call edges — **3,291 confirmed, 10 suspect, 189 unobserved** (147 never called, 39 in never-imported scripts, 3 mixed); confirmation rate **94.3%** (coverage-limited, not precision — C-60); suspect rate 0.3%. **Recall-against-executed 86.2% (3,291/3,816 observed in-repo pairs)**, **96.9% on named declarations** (classes 307/307, functions 2,657/2,745, methods 234/247); closures 93/441 and lambdas 0/76 (C-58). Coverage line: 2,971/3,149 Hobbes sites spoken about, 113/129 files loaded, 1,668/2,048 declarations started. Triage: 4 semantic suspects *not-exercised*, 6 syntactic suspects *hobbes-wrong* (a fixture parameter name-matched to the fixture function — the C-7 floor, 6/6 on the executed slice). **Not hand-checked.** |
| 2026-08-25 (**oracle lane O2**, ADR-089) | **Go zone compiler-graded against RTA** (`bench/oracle`, [cell record](oracle-cells/hobbes-go-2026-08-25.md)): 1,282 Hobbes call edges — **1,278 confirmed, 3 contradicted, 1 oracle-silent**; precision-against-oracle **99.8%** overall, **100% on the semantic tier (1,278/1,278)**, **0/3 on the syntactic tier**. Recall **87.5% (1,280/1,463 in-repo oracle pairs) at 20 roots** — static calls **1,280/1,280**, calls into closures 0/37, dynamic dispatch 0/8, and 0/138 `func()`-value pairs RTA over-approximates (denominator is an upper bound). 12,003 external oracle pairs out of the denominator (D-O3). Line-grain tolerance on 438 edges |
| 2026-08-18 (ADR-050) | ts/js **61.6% → 67.0%** — the per-file `node_modules` links fixed the tsconfig-less root zone (`tsextract` 27.7% → 58.8%, its 131 `external-origin` sites now resolving). go/python/rust unchanged |
| 2026-08-18 | 265 nodes, 915 module edges, 2,063 symbols, 4,207 call edges. Capture: go **89.2%** of 3,707 · python **88.3%** of 4,862 · rust **100%** of 18 · ts/js **61.6%** of 2,417. Unclassified residue: 0 python, 0 go (ADR-046), ~99 ts/js (the known fleet residue — helper/scip JS zones). Stable across the ADR-048/049 changes |
| 2026-08-16 (V2.M7 exit) | 3,085 sites, lanes **0 disagreements** across six languages |
| 2026-08-15 (V2.M3 exit) | lanes: 1,789 sites compared, **0 disagree** |

**Verified:** Go — **compiler-graded 2026-08-25**: every semantic call
edge in `go/` confirmed by RTA (1,278/1,278), the 3 syntactic-tier
edges contradicted; not hand-checked beyond triage. Triage of the
three: all **hobbes-wrong** — lane A's name fallback (C-7) bound the
test helper's local closure `run := func(...)` at
`cmd/hobbes-session/main_test.go:55/57/58` to the package function
`run` (`main.go:90`); the semantic lane had no target for a closure
(C-58). Two further contradictions in the first pass were a
**match-defect** (the oracle unwound a generic instantiation into its
body, grading `sortedKeys[string]` as `sort.Strings`), fixed with a
regression fixture before the number above was taken. The one silent
edge (`web/server.go:122 → Server.Handler`) sits in `ServeHTTP`,
reachable only through net/http's interface — RTA never reached it.
The 45 non-inflated misses are all **C-58** (interface / function-value
dispatch and calls into closures draw no edge). The V2.M5 hand-check —
Go 20/20 call edges (ADR-037) — is **retired** (Max, 2026-08-25): a
rough check whose edges were never named, so it cannot be reproduced
(prediction P6); the oracle is the Go evidence from here, and
hand-checks return later with a selection rule (design §11). Misses by
class: `docs/oracle-misses.md`.
Earlier:
10/10 sampled narrative claims resolve (M5); the M8 exit check's
invariant regression replay (`hobbes review ace9a08..cdbc085`, exit 1).

**Pre-registration graded (`docs/oracle-preregistration.md`, O2):**
P1 semantic precision ≥ 95% — **met** (100%). P2 contradictions in the
syntactic tier — **met** (3 of 3; the tier is 3 edges, so the
concentration claim is met on a tiny base and recorded as such).
P3 misses dominated by dynamic dispatch — **met on the inflated count**
(146 of 183 pairs are `dynamic*`), **missed on the honest count**: of
the 45 non-inflated misses, 37 are calls into *closures* at static
sites and 8 are dynamic — closures, not dispatch, dominate; the
prediction did not anticipate that Hobbes has no closure symbols at
all. P4 recall 60–85% — **missed high**: 87.5% overall, and 100% on
static sites — the graph is more complete on static calls than the
prior allowed. P5 silent ≤ 15% with `unreachable` largest — **met**
(1 edge, unreachable). P6 ADR-037's 20 not reproducible — **confirmed**.
**O4 (dagger):** P8 — the 126 build-tag lane disagreements grade
`not-loaded` — **not graded**: those sites are in the root module
(engine, platform-specific files), which does not fit this box as one
program (H-9); across the 19 graded modules the `not-loaded` bucket is
empty, which says nothing about P8. P9 — C-33's 7,322 core/integration
→ sdk/go edges ≥ 95% — **not graded** for the same reason: the
`./core/integration/...` subtree cell was OOM-killed at 24.4 GB after
20 minutes. Both stand until a larger box (or a streaming SSA build)
runs the root; the design's payoff line for O4 is **not earned** and
is not claimed. What O4 *did* earn: 19 modules at 99.6% precision
with every contradiction one nameable product defect.
**O3 (kbet):** P7 semantic precision ≥ 95% — **met** (100%; the
first-pass 81% was the oracle's grain, D-O4 now says so); overload-set
membership needed for ≥ 1 confirmed edge — **not testable as stated**:
no in-repo overloaded function is called in the zone; the rule that
*did* decide 119 edges was the binding rule, which P7 did not
anticipate.

**Pre-registration graded, phase 2 (`docs/oracle-preregistration.md`,
O6/O7):** P10 recall-against-executed ≥ 90% named / 70–92% overall —
**met** (96.9% / 86.2%). P11 suspect rate ≤ 2% — **met** (0.3%);
"mostly not hobbes-wrong" — **missed**: 6 of 10 are hobbes-wrong, and
all six are the syntactic tier, the same tier-concentration phase 1
predicted for Go (P2); the semantic tier had none. P12 ≥ 60% of sites
exercised, `line-not-called` dominant — **met** (94.3%; 147 vs 3).
P13 closures ≥ 50% of misses, function values the runner-up — **met**
(80.8% with lambdas; the runner-up is the packs' and argparse's
function-valued fields, 64 of the 88 function misses). P14 a
harness defect in the different-grain class before any number — **met
five times over** (H-12 the package nodes, H-13 the test harness's
generated calls, H-14 the coverage count, H-15 foreign macro bodies,
H-16 `.await`'s poll of async bodies; every one found by the fixture or
the first triage). P15 the MIR oracle confirms ADR-040's 33 — **met on
every call edge**: the 33 were 17 `calls` + 16 `uses`, and the compiler
confirms 17/17. P16 precision ≥ 95% semantic — **met** (100% on both
Rust cells); misses concentrated in trait dispatch and closures —
**missed**: after H-16 no closure miss remains, and 46 of dagger's 69
are calls into or from code a macro or derive wrote (derived `clone`,
builder setters, proc-macro tokens); dispatch through extension traits
is 17. Two of seven missed, both about *where the misses would be*: on
Python the prior was right, on Rust the generated-code class was not in
anyone's prior.

## kbet (`~/projects/kbet` — real Vite+React TS app; throwaway tier)

| Date | Numbers |
|---|---|
| 2026-08-18 (ADR-050) | ts/js **72.1%** of 4,807 — its per-package tsconfig + installed tree was already the handled shape; residue is 462 `external-origin` (third-party calls) + 24 attr-call, 3 unclassified |
| 2026-08-16 | tail: 61% below-floor locals; **9 of 1,339** sites unclassifiable |
| 2026-08-15 (V2.M3/C-24) | **231 semantic TS call edges**; 12 test→component render edges, all semantic; 108/174 tests reach a component; lanes 359 sites, **0 disagree** |
| 2026-08-11 (M6) | 104 nodes, 174 tests |

**Verified:** TS — **compiler-graded 2026-08-25 (oracle lane O3,
[cell record](oracle-cells/kbet-ts-2026-08-25.md))**: all 630 call
edges of the `betchat/frontend` zone **confirmed by the zone's own
`tsc` 5.9.3** (626 semantic + 4 syntactic), 0 contradicted, 0 silent —
precision-against-oracle **100%**. Recall over every resolved site:
**41.4% (633/1,529 in-repo oracle pairs)** — but the recall on
*declared* callees is 633/637: functions 483/484, module-level
variables 23/23 (+119/121 called through a function-valued variable),
classes 8/8. The 896 misses are three classes, all C-58 / C-32:
**625 local bindings** (`setError(...)`: a `useState` setter or a
callback held in a local — the value, not the function, is what is
named; C-32's *seen and not modelled by design*), **195 closures**
(handlers declared inside components), **71 store members** reached
through an interface property signature (`ChatState.addMessage`),
plus 1 IIFE and 1 `let`-bound accessor called before assignment.
First pass graded 119 contradictions; triage: **all match-defect** —
the oracle's declaration for `useAuthStore()` was zustand's anonymous
call signature, not the binding; the binding rule (D-O4, harness README)
fixed the grain and the oracle now lists the callee's binding. One more
oracle defect found the same way: a dynamic `import()` listed as a
call target (a module, not a declaration) — dropped. Not hand-checked
beyond triage. The V2.M3 20/20 hand-check is **retired** on the same
grounds as Go's (edges never named); earlier: 20/20 edges + 10/10 test
mappings at M6.

## rust_proj (`~/rust_proj` — small Rust crate)

| Date | Numbers |
|---|---|
| 2026-08-25 (**oracle lane O7**, ADR-089 phase 2) | **Compiler-graded against rustc's MIR** ([cell record](oracle-cells/rust_proj-2026-08-25.md)): **17/17 call edges confirmed**, 0 contradicted; recall 17/21 in-repo pairs over every resolved site — the 4 misses are calls criterion's `criterion_group!`/`criterion_main!` bodies make (`macro→function`). ADR-040's "33" reconciled: 17 `calls` + 16 `uses` symbol edges |
| 2026-08-16 (V2.M7 exit) | 33 call edges, **all semantic**; lanes clean at 17 sites |

**Verified:** the 17 call edges — **compiler-graded 2026-08-25 (O7)**,
17/17 confirmed by rustc's own resolution; the 2026-08-16 33/33
hand-check (ADR-040, the P7 proof) counted calls and uses together and
is superseded by the oracle for the calls. Rust's evidence base is now
this crate plus dagger's `sdk/rust` (below), both compiler-graded.

## dagger (`~/dagger` — the Dagger automation engine; ~460 MB)

The first deep-extraction target (2026-08-18, ADR-048/049): four graph
languages, **84 TS zones, 25 Go modules, ~265,000 detected call
sites** — ~50× the largest prior measurement. Its role is scale and
monorepo structure, and it earned three fixes and one lifted
constraint in two days.

| Run | Numbers |
|---|---|
| 8th — **`sdk/rust` regraded after ADR-090**, re-ingested at f3cc3eb3 the same day | **3,592 confirmed, 0 contradicted, 6 silent — precision-against-oracle 100%** (from 99.7%); the twelve `format!`→`fn format` edges are gone (the macro veto); recall unchanged at 3,593/3,662. The re-ingest also names `below-floor` on dagger: go 4,114, ts/js 247, python 117, rust 102 sites — C-58 sized on the artifact itself, per file |
| 7th — **oracle lane O7 (Rust), 2026-08-25**, same ingest f3cc3eb3 | **`sdk/rust` compiler-graded against rustc's MIR** ([cell record](oracle-cells/dagger-rust-2026-08-25.md)): 3 crates, 15 targets, 17 s. 3,610 Hobbes call edges — **3,592 confirmed, 12 contradicted, 6 oracle-silent**; precision-against-oracle **99.7%**, **semantic tier 3,574/3,574 = 100%**; the 12 contradictions are all syntactic — lane A binding `format!(...)` invocations to a `fn format` in the same file (hobbes-wrong; the C-7 floor at 12/30 on this crate). **Recall 98.1% (3,593/3,662 in-repo pairs)** over every resolved site: methods 3,354/3,384, functions 239/253; the 69 misses are extension-trait methods on foreign types, `derive_builder` setters, derived `clone` targets and calls inside `quote!` tokens — code a macro or derive wrote, not dispatch (`docs/oracle-misses.md`). 20,561 compiler-written sites (test harness, derives, `.await`) excluded by rule; the first pass counted `.await`'s async bodies as 649 closure misses (H-16) |
| 6th — **after the W1 fixes, same day**, re-ingested at f3cc3eb3 | Same 19 modules, same 24 roots ([before/after](oracle-cells/dagger-go-2026-08-25.md)): **9,851 confirmed, 0 contradicted, 656 silent** — precision-against-oracle **100%** (from 99.6%), 9,890/10,715 in-repo pairs drawn (from 9,855), **static named calls 9,889/9,889** (from 9,854/9,889). The 40 contradictions and 35 named misses were five product defects, each now with a test on the `goshapes` fixture: conversions drawn as calls; a method named like a type in its package dropped as a conversion (chain, LHS and method-expression calls — one bug); generic instantiation calls with no site; self-calls dropped (C-59, lifted); typed `var`/`const` specs named by their type, minting 58 phantom `string` symbols that lane A's fallback then bound `string(x)` to. What remains is C-58 |
| 5th — **oracle lane O4 (ADR-089), 2026-08-25**, ingest f3cc3eb3 | **Compiler-graded, 19 Go modules** ([cell record](oracle-cells/dagger-go-2026-08-25.md)): 10,512 Hobbes call edges — **9,816 confirmed, 40 contradicted, 656 oracle-silent (all unreachable from any root)**; precision-against-oracle **99.6%**; 9,855 of 10,715 in-repo oracle pairs drawn across 24 roots (per-cell recalls 89–100%, never pooled); static calls to named declarations **9,854/9,889**. All 40 contradictions are **type conversions drawn as calls** (`dagger.JSON("0")` → `calls` to `type JSON`; 37 semantic, 3 syntactic) — the lane's first wrong edges in the semantic tier, a product defect for W1. Named misses: 16 recursion (**C-59**, dropped by design), 11 method-expression / generic-instantiation calls, 4 chain continuations (no site), 4 calls on an assignment's left side (drawn as `uses`); the rest C-58 (577 closures, 192 interface dispatches, 16 function-table). Four modules not gradeable (docs: undeclarable deps; recorder/recorder2: generated package absent; e2e/helm/dagger: nothing to root at). **The root module does not fit this box as one program** (OOM at ~21 GB, H-9); graded by package subtree — see the cell record |
| 4th — after dependency provisioning (ADR-050) | ts/js **18.8% → 27.9%**; `sdk/typescript` **63.7% → 70.3%**; the docs zone indexes instead of failing (docs/versioned_docs 0% → 4.5% — the residue is example snippets importing `@dagger.io/dagger`, which no package.json declares: undeclarable, not unprovisioned). 8 lockfile-pinned trees provisioned into `~/.hobbes/cache/npm` (~833 MB, docusaurus dominating); every declined zone carries its C-34 reason (`no lockfile`). Lanes: 36,703 dual-resolved, 258 disagree — the +120 are all the TS decorator line-convention off-by-one (131 total, same declaration both sides; noted in future_additions), Go's 126 unchanged, **1** genuinely new |
| 3rd — after the cross-unit join (ADR-049) | go **85.6%** of 237,728 — cannot-resolve 20,501 → **5,571** (attr-call 4,655, unclassified 219); `core/integration [go]` **59.3% → 96.3%** (cannot-resolve 14,902 → 396). **161,184 call edges (+8,014 semantic)**, 24,723 module edges; **7,322** semantic `core/integration → sdk/go` edges (the `replace`d SDK, C-33's exact case). Two `scip-merge` abstentions reported (42 anonymous-TS-zone monikers, 7 generated Go testdata modules — C-28's rule across units, exactness holding). Lanes: 36,440 dual-resolved, **still 138 disagree — zero added by the join**. python/rust/ts unchanged, as they should be |
| 2nd — after wrapped-chain + per-unit degradation (ADR-048) | go **79.3%** of 237,728 (unclassified **359**, was 9,131) · python **89.1%** of 6,382 · rust **94.2%** of 8,595 · ts/js **18.8%** of 12,503 (`sdk/typescript` **63.7%**, was 0 — the docs zone now fails alone). 4,872 nodes, 24,452 module edges, 153,170 call edges. Lanes: 36,439 dual-resolved sites, **138 disagree (0.38%)** — 126 Go (fallback vs build tags/interface dispatch: C-7/C-8's floor measured), 11 a TS decorator line-convention off-by-one, both lanes citing the same declaration |
| 1st — baseline | go 79.3% (unclassified 9,131 — wrapped fluent chains) · ts/js **0.0%** (one broken docs zone zeroed all 84 zones) · python 89.1% · rust 94.2%. Found C-33: zero semantic edges from the root module into the `replace`d `./sdk/go` |

**Verified:** **no hand-checked edges** — documented deliberately
(Max: "leaving edge verification is fine as long as its documented").
What dagger evidences is the honesty machinery and the monorepo
structural fixes at scale, plus the two-module fixture's 0% → 100%
flip (`semantic`/`calls`) proving the C-33 lift's mechanism exactly.
Before O4 no §3.8 row existed for dagger and none was licensed; O4 licenses one — for the 19 graded Go modules, at the grain measured, and nothing wider.

## psf/requests (SWE-bench Verified checkouts — eight base commits, ADR-055)

| Date | Numbers |
|---|---|
| 2026-08-21 | eight instance checkouts (2013–2022 base commits), lane A only (`HOBBES_SCIP=0`), 93–155 nodes each; used for the C-36 seed probe — 8/8 issues seed lexically, 4/8 seed sets touch the gold-patch file |

**Verified:** none — the role was the seed probe, not edge accuracy; no
call edge was hand-checked (documented, not claimed).

## SWE-bench workspaces (the derivation programme, 2026-08-21 → 24)

The benchmark harness's ingest targets — large, real Python repos at
old base commits, each a fresh workspace clone (`~/.hobbes/bench/*/work/`).
Their role is derivation input (ids, paths, spans, co-change), not edge
accuracy, and the Verified line is scoped to exactly that. Numbers from
the 2026-08-24 validation pair's workspaces (full ingest; lane B where
the helper ran):

| Repo (instance) | Numbers |
|---|---|
| django (11400) | 2,829 nodes, 70,066 call edges; python **53.7%** of 123,389 sites; js/ts 20.0% of 9,281 (lockfile-less zones declined by name, C-34); 3 degradations reported |
| scikit-learn (25102) | 1,052 nodes, 31,523 call edges; python **53.0%** of 82,674; 1 degradation — the environment-residue row (defect D7, `adr085-validation-run.md`): a scip-decode dup report naming a package from the box's python env, zero graph nodes/edges from it |
| xarray (3993) | 237 nodes, 13,897 call edges; python **68.8%** of 30,725; no degradations |
| sphinx (8548) | 733 nodes, 11,041 call edges; python **72.1%** of 24,405 |
| sympy (13852) | 1,309 nodes, 28,840 call edges; **lane B did not run** — the workspace's scip helper env errored and the P6 degradation is on the record; the 0.0% capture of 607,906 sites recorded under it is the degraded-path figure, not a resolution measurement |
| astropy (13398, 13579) | 2026-08-22 phase-4 probes + full stages; unit interiors vs gold checked by hand (BUILDLOG) |

**Verified:** declaration sites and spans hand-checked during the deep
reads of the 27B pairs and the sympy 7B failure — django, xarray,
scikit-learn, sphinx, sympy: every span and declaration site checked
landed exactly (BUILDLOG seventy-fourth–seventy-sixth, the P12
inspection's "extraction is accurate and load-bearing" finding);
astropy unit interiors vs gold hand-checked at phase 4. **No call edge
was hand-checked in these repos** — the §3.8 Python row is extended at
span/declaration grain only, and licenses nothing about edge accuracy
here.
