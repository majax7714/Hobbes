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

Fixture repos (`miniapp`, `minits`, `minigo`, `minirust`,
`canary-rust`, the twomod scratch fixture) are exercised by the test
suite on every run and are not logged here — this file is for real
repos.

**Last full pass: 2026-08-28** (every section re-read against the
tree and the cell records; the SWE-bench D7 row corrected). Sections:
hobbes (dogfood) · the seven-repo loop of 2026-08-27 · kbet ·
rust_proj · dagger · psf/requests · the SWE-bench workspaces. The
**containment scope** (ADR-092, P11) applies file-wide: rows dated
2026-08-27/28 that say so ran under the sandbox image; every other row
is a host run.

---

*Retired from the base 2026-08-25 (Max): test-repo-A (a test
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
| 2026-08-28 (**O2 regraded contained**, after the Go scope veto; [cell](oracle-cells/hobbes-go-2026-08-28.md)) | **1,283/1,283 confirmed, 0 contradicted, 1 silent — precision-against-oracle 100%** (from 99.8%): the three syntactic contradictions (`run := func` bound to `main.run`, the fzf shape's first sighting) are gone; recall 87.5% (1,285/1,468) at 20 roots, misses C-58 unchanged. 501 s with the six-language ingest |
| 2026-08-28 (**O6 contained vs host, same tree**, 1 run, containment-sensitive tests deselected; [cell](oracle-cells/hobbes-py-2026-08-28.md)) | 3,633 edges — contained **3,311 confirmed, 5 suspect, 317 unobserved**, recall-against-executed **86.1%** (3,311/3,846); host 3,319 / 5 / 309, 86.1%. Suspects and every miss class identical; the 8-edge residue is one test that probes for a container runtime. Misses: closures 361, functions 88, lambdas 73, methods 13 (C-58) |
| 2026-08-27 (**ADR-092 phase 1 — lane B contained**) | The whole repo ingested with every lane B step inside `hobbes-session:local` (Pyright with `pipeline/.venv` + uv's interpreter mounted ro; TS with three repo `node_modules` ro; Go after a `go mod download` fetch; Rust after `cargo fetch`, offline index). **Byte-identical to the host run of the same dirty tree**: 378 nodes, 3,140 symbols, 1,457 module edges, 6,478 symbol edges (4,444 semantic calls, 2,033 semantic uses, 1 syntactic call), same `dependency_coverage` (py 6/6, ts 6/9), same `extraction_errors` modulo the 13 C-64 disclosures the host run carries. Two contained runs identical to each other. First contained build (rustup `minimal` without `rust-src`) was *not* a no-op — 11 Rust semantic calls fell to syntactic, 3 vs 30 external refs — caught by this diff, fixed in the image |
| 2026-08-25 (**O6 regraded after ADR-090**, same suite, 1 run) | 3,495 edges — **3,302 confirmed, 4 suspect (all semantic, not-exercised), 189 unobserved**; the syntactic tier's six wrong edges are gone (the scope veto), no executed syntactic edge remains; recall-against-executed **86.3% (3,302/3,828)**, confirmation rate 94.5%, suspect rate 0.1%. `below-floor` on this repo: go 3, python 35, ts/js 10 sites |
| 2026-08-25 (**oracle lane O6**, ADR-089 phase 2) | **Python zone trace-graded against the interpreter** (`bench/oracle`, [cell record](oracle-cells/hobbes-py-2026-08-25.md)): the suite (907 tests, 2 runs) under `sys.monitoring`; 3,490 Hobbes call edges — **3,291 confirmed, 10 suspect, 189 unobserved** (147 never called, 39 in never-imported scripts, 3 mixed); confirmation rate **94.3%** (coverage-limited, not precision — C-60); suspect rate 0.3%. **Recall-against-executed 86.2% (3,291/3,816 observed in-repo pairs)**, **96.9% on named declarations** (classes 307/307, functions 2,657/2,745, methods 234/247); closures 93/441 and lambdas 0/76 (C-58). Coverage line: 2,971/3,149 Hobbes sites spoken about, 113/129 files loaded, 1,668/2,048 declarations started. Triage: 4 semantic suspects *not-exercised*, 6 syntactic suspects *hobbes-wrong* (a fixture parameter name-matched to the fixture function — the C-7 floor, 6/6 on the executed slice). **Not hand-checked.** |
| 2026-08-25 (**oracle lane O2**, ADR-089) | **Go zone compiler-graded against RTA** (`bench/oracle`, [cell record](oracle-cells/hobbes-go-2026-08-25.md)): 1,282 Hobbes call edges — **1,278 confirmed, 3 contradicted, 1 oracle-silent**; precision-against-oracle **99.8%** overall, **100% on the semantic tier (1,278/1,278)**, **0/3 on the syntactic tier**. Recall **87.5% (1,280/1,463 in-repo oracle pairs) at 20 roots** — static calls **1,280/1,280**, calls into closures 0/37, dynamic dispatch 0/8, and 0/138 `func()`-value pairs RTA over-approximates (denominator is an upper bound). 12,003 external oracle pairs out of the denominator (D-O3). Line-grain tolerance on 438 edges |
| 2026-08-18 (ADR-050) | ts/js **61.6% → 67.0%** — the per-file `node_modules` links fixed the tsconfig-less root zone (`tsextract` 27.7% → 58.8%, its 131 `external-origin` sites now resolving). go/python/rust unchanged |
| 2026-08-18 | 265 nodes, 915 module edges, 2,063 symbols, 4,207 call edges. Capture: go **89.2%** of 3,707 · python **88.3%** of 4,862 · rust **100%** of 18 · ts/js **61.6%** of 2,417. Unclassified residue: 0 python, 0 go (ADR-046), ~99 ts/js (the known fleet residue — helper/scip JS zones). Stable across the ADR-048/049 changes |
| 2026-08-16 (V2.M7 exit) | 3,085 sites, lanes **0 disagreements** across six languages |
| 2026-08-15 (V2.M3 exit) | lanes: 1,789 sites compared, **0 disagree** |

**Containment scope (ADR-092, P11):** the rows dated 2026-08-27/28 are
the only ones produced under the sandbox image; every earlier row and
every other repo's cells below were host runs. They are not re-earned
by containment, and the contained toolchain is not assumed equal to the
host's until a cell proves it (it differed once already: `rust-src`).
From here a record without `containment` is a host-run record.

**Verified:** Go — **compiler-graded 2026-08-25 and 2026-08-28**: every semantic call
edge in `go/` confirmed by RTA (1,278/1,278; 1,283/1,283 on the contained regrade), the 3 syntactic-tier
edges contradicted on 2026-08-25 and gone after the Go scope veto; not hand-checked beyond triage. Triage of the
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
**Verified:** Python — **trace-graded 2026-08-25 and 2026-08-28** (O6):
every executed semantic edge confirmed by the interpreter on the
2026-08-25 regrade (0 wrong on the executed slice, 4 not-exercised
suspects); on 2026-08-28's contained cell 5 suspects, the same five on
both sides, untriaged; recall 86% against what the suite ran, 97% on
named declarations — a coverage-limited claim, never precision (C-60).
TS — **not oracle-graded on this repo**: `web/` and the helper zones
rest on lane agreement only (0 disagreements at V2.M7); the TS
evidence is kbet, ajv and cheerio below. Rust — this repo's Rust is
fixtures and `bench/oracle/rust`; not graded here (rust_proj, memchr,
dagger `sdk/rust` carry Rust). HCL — the pack's edges, no oracle.
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
**missed**: after H-16 no closure miss remains, and 47 of dagger's 69
are calls into or from code a macro or derive wrote (25 derived
`clone`, 7 builder setters, 15 inside proc-macro tokens); dispatch
through extension traits is 17, and 5 are a raw-identifier method and
a `Deref`. Two of seven missed, both about *where the misses would be*: on
Python the prior was right, on Rust the generated-code class was not in
anyone's prior.

## The nine registered-not-fixed entries, lifted — 2026-09-03 (evening, contained)

Max's direction: tackle the extraction constraints, easiest first, the
TTT items left on the table. All nine of the 2026-09-02 findings
(C-72–C-80) and C-85 were lifted in four commits, each with its tests
and its register entry; the measurements below are the evidence for
the three that changed what a graph holds.

| Cell | What changed | Numbers |
|---|---|---|
| **this repo** @ 5562271 (re-ingested contained after C-72/C-80; the prior artifact was built at 00e5aee, so the deltas include two days of code) | C-80 records expression-receiver calls as sites; C-72 tightens the Rust fallback | 449 nodes / 3,784 symbols / **5,173 semantic + 15 syntactic `calls` + 2,285 `uses`**; **1,433 `<expr>.m()` sites** now detected (127 with a `calls` edge at the line, the rest external or `attr-call`); Python capture **81.7% of 14,352** (the denominator grew by the new sites; `attr-call` 1,660); six of the seven `uses` edges that vanished became `calls`; lanes **5,937 sites / 0 disagree**, `module edges compared: 484 (lane B produced 640)` — the C-75 line; Rust `path-call` 4, unchanged; one new syntactic edge, in a script lane B does not cover |
| **miniapp fixture, no venv** (a copy, `git init`, ingested from this checkout — the first attempt ran `uv run` *inside* the copy and uv created a venv there; ADR-094's lesson in a new shape) | C-85 | **before:** `capture [python]: 0.0% of 19`, the record blaming the helper, scip-python's stack ending at `main-impl.ts:47`; **after:** **68.4% of 19** (the same as with a venv), two records — C-79 (no manifest declares dependencies) and C-85 (no venv found; the one-command fix) |
| **the four 2026-09-02 clones, re-ingested contained** (`~/.hobbes/bench/extract-test-20260902/`, same commits; the pre-fix `graph.json` of each kept for the diff) | all ten lifts, then C-89 | **peft** (Python): 9,148 `calls` (8,976 semantic) + 5,868 `uses` for 8,899 + 6,117 before — **249 `uses` edges became `calls`, all 249** (C-80); `PeftModel.save_pretrained` now **232 callers, 0 "non-calling references"**; `dependency_coverage` present, **13 of 52** from `requirements.txt` (C-79; the `scip-resolve` record fires); capture 68.3% of 45,593 (68.3% of 41,950 before — the same fraction over 3,643 more sites); lanes 4,281 / 0, unchanged. **date-fns** (TS, pnpm workspace): **capture 0.1% → 79.7% of 24,827**; `calls` 3 semantic + 2,255 syntactic → **2,205 semantic + 56 syntactic**, `uses` 4 → 3,398; 13 of 15 zones index, then **15 of 15** once C-90 stages the configs a tsconfig names and replaces the solution-style root (**capture 80.1%**, no `scip-typescript` record); eleven `scip-resolve` records at their zones (C-74); lanes 7 / 0 → 7,586 / **54**, all one shape — the overload line (C-89) — → **7,586 / 0** after the tsextract fix, **7,601 / 0** after C-90, below-floor 254 → 219; `module edges compared: 5394 (lane B produced 5360)` (C-75). **quic-go** (Go): the **four `http-go` C-5 records gone** (C-78), everything else byte-for-byte the same counts (capture 86.8% of 41,963; lanes 6,743 / 17, the ADR-098 residue). **serde** (Rust): the symlinked copy gone (`serde/src/core` 19 modules → 0, plus a second link `serde_derive_internals/src` the test had not noticed) with two `discover` records (C-73); 248 → 219 nodes, 3,084 → 2,350 symbols, 13,028 → 10,571 sites; syntactic `calls` 81 → 28 (the 53 that lived only in the copy, the 3 wrong among them); **lanes 910 / 3 → 721 / 0** (C-72); capture 80.0% → **88.2%** |
| **synthetic pnpm-style workspace** (`pkgs/core/tsconfig.json` extends `@x/dev/tsconfig.base.json` via `node_modules/@x/dev -> ../../../dev`, committed as a symlink) | C-74 | **with the fix:** zone `pkgs/core` indexed contained, `b → a` a **semantic `calls` edge**, capture 100% of 1, the `scip-resolve` record at `pkgs/core` (not `.`); **control** (`workspace_link_targets` stubbed to `[]`): `error TS6053: File '@x/dev/tsconfig.base.json' not found`, capture 0.0% — date-fns's failure exactly, now recorded as *"the typescript indexer exited inside the container (the helper ran…)"* |

**Verified:** the two small cells by reading every edge (one each) and
the full summary; this repo by the lane self-test (0 disagreements at
5,937 dual-resolved sites) and by the `uses`→`calls` list (seven
edges, six converted, one a function that was renamed between the two
SHAs); the four clones by the lane self-test on each (0 / 0 / 17 / 0
disagreements, the 17 quic-go's known residue) and by the per-finding
diff against the pre-fix artifact named in the row. Not hand-sampled
at the edge level beyond that — the 2026-09-02 rows remain the
hand-checked record, and the semantic edges those samples confirmed
are unchanged in kind. Containment `all_contained: true` and `built_by` this
checkout on all three; the image rebuilt for C-77 and C-80's gloss
(C-65) before the runs.

## Four random repos — the 2026-09-02 extraction test (agents, contained, hand-sampled)

Max's direction: four agents, one language each, a random public repo
drawn from a seeded GitHub sample (excluding every repo above), the
knowledge piece exercised end to end — init, contained ingest, `hobbes
lanes`, a determinism re-ingest, a 15-edge hand sample, the six
knowledge tools, an honesty cross-check — and a stop rule on any
architectural error. Two stopped at `hobbes lanes`. Reports (commands,
verbatim logs, edge tables) were session scratch; the findings are
ADR-098 and C-71–C-80. **Not oracle-graded** except where a row says
so; every row below is a *hand sample* (P11: it licenses the machinery
on that repo, not the language).

| Repo | Lang | Draw | Numbers |
|---|---|---|---|
| **huggingface/peft** @ 3d881e97 (450 files) | Python | seed 20260903, index 402 (two smaller draws rejected) | 67 s contained (`python-env`, `index-python`), 572 nodes / 6,033 symbols / 8,899 `calls` + 6,117 `uses`; capture **68.3%** of 41,950 sites (attr-call 8,307 the remainder); lanes **4,281 sites / 0 disagree**; two ingests **byte-identical**; **15/15 sampled edges confirmed** (12 semantic, 3 syntactic; one at static grain on a union receiver); knowledge tools consistent with `graph.json` (183 + 49 for `save_pretrained`, 350, 3; `tests_guarding` 1,151 / 584) — findings C-77 (`below-floor` missing from the tool), C-79 (no `dependency_coverage` for a `setup.py` repo), C-80 (`super().m()` glossed as not a call) |
| **date-fns/date-fns** @ 18cbd436 (1,596 TS files, pnpm workspace) | TS/JS | seed 20260904, index 143 (three larger draws skipped) | 19 s, 15 `index-typescript` steps contained — **lane B lost on every workspace zone** (C-74: the `@date-fns/dev` link dangles in the container; the same scip-typescript indexes it on the host in 10 s); 3 semantic + 2,255 syntactic `calls`, capture 0.1% of 24,827; lanes exit 0 at 7 sites (C-75: the 200 "lane B only" module edges are the fallback's); **byte-identical** re-ingest; **15/15 confirmed** (all 3 semantic + 12 syntactic, none an ADR-090 shape); `who_calls` 398 / 192 / 84 = `graph.json`, host and image answers byte-identical |
| **quic-go/quic-go** @ c2877d14 (445 files) | Go | seed 20260905, index 367 (three draws rejected) | 15 s contained (`fetch-go` + `index-go` ×3 modules), 538 nodes / 5,643 symbols / 10,961 semantic + 6 syntactic `calls`, capture **86.8%** of 41,963; **stopped**: lanes exit 1 with **29 of 6,772** — 17 C-70 (`jsontext.String(x.String())`), **12 build-tag alternates** (`setDF`, `newConn`, `isECNEnabled`, `getCurveID`…) and **2 of 6 syntactic edges wrong** by the same mechanism → **fixed the same day (ADR-098, C-71)**: re-ingested, the two edges replaced by the right ones, every other edge identical, **17 disagreements, all C-70**, eight dark constrained files named by the new record. Also C-78 (four false `http-go` C-5 records from `windows.Handle(fd)`) |
| **serde-rs/serde** @ a874a1b1 (208 files, 5-crate workspace) | Rust | seed 20260906, index 233 (three draws rejected) | 12 s contained (`fetch-rust`, `index-rust`; C-29 disclosed), 248 nodes / 3,084 symbols / 1,476 semantic + 81 syntactic `calls` + 2,804 `uses`, capture 80.0% of 13,028; `dependency_coverage` 11/12 (`libc`); **stopped**: lanes exit 1 with **3 of 910** — `Option::<T>::deserialize` and `Expected::fmt` bound by last segment (C-72); semantic right at all three; **all 81 syntactic edges hand-checked: 78 confirmed, 3 wrong**, the wrong ones emitted only in the `serde/src/core -> ../../serde_core/src` symlink copy that has no lane B (C-73; 19 modules / 1,356 sites counted twice); C-76 (summary "4361 call edges" for 1,557 `calls`) |

**Verified:** peft and date-fns 15/15 each by hand at the cited lines
(caller binding + target declaration opened); serde every syntactic
`calls` edge (81) by hand; quic-go the six syntactic edges by hand, two
wrong before ADR-098 and none after. **No semantic-tier edge was found
wrong on any of the four.** One is oracle-graded, after the fix:
**quic-go against Go RTA at 5 binary roots** (`--no-tests` — the full
test program was OOM-killed on this box twice, the dagger-root shape,
H-9; [cell](oracle-cells/quic-go-go-2026-09-02.md)): **3,766
confirmed, 15 contradicted, 1 abstract, 13,551 silent** (13,345
`not-loaded` — test files and the packages only tests reach);
precision-against-oracle 99.6% lower bound, **all 15 contradictions
oracle-grain** (the test build's `wrappedConn` methods shadowing the
embedded `*Conn`'s — scip-go indexes the test build, the oracle did not
load it), 0 hobbes-wrong; recall 47.5%, `static→named` 99.6%; poison
PASS, 0 falsely confirmed of 17,333. Both
determinism checks (peft, date-fns) byte-identical; containment stamp
`all_contained: true`, `built_by` this checkout, on all four; nothing
written into any clone outside `.hobbes/` and init's `.gitignore` line.

## Seven public repos — the 2026-08-27 grading loop (triaged and regraded 2026-08-28)

BurntSushi/toml, gorilla/mux, junegunn/fzf (Go, RTA); BurntSushi/memchr (Rust, MIR); ajv-validator/ajv, cheeriojs/cheerio (TS, the zone's `tsc`); pallets/click (Python, trace). Cells in `docs/oracle-cells/*-2026-08-27.md` with their regrade sections; the loop table in `docs/oracle-misses.md`.

| Date | Numbers |
|---|---|
| 2026-08-28 (regrades after triage) | **Every compiler-graded cell at 100% precision-against-oracle**: toml 1,039/1,039 · fzf 2,832/2,832 (was 97.0%) · mux 1,221/1,221 (3 abstract) · memchr 921/921 (was 99.2%) · cheerio 2,102/2,102 (44 abstract; was 97.9%) · ajv 1,375/1,378 (3 hobbes-wrong by tier, unfixed). click: 1,699 confirmed, 18 suspect (1.0%), recall-against-executed 37.0%. Recall: toml 71.9%, fzf 40.8%, mux 82.6%, memchr 80.7%, ajv 62.0%, cheerio 36.1% — the misses C-58's closure/interface classes and Rust's macro face throughout |

**No pre-registration was written for this loop** (`oracle-preregistration.md` stops at phase 2): its numbers are post hoc and are read as such — the loop tested the *method* (a cell per repo, triage by the review's rules) rather than a prediction. Per-repo capture lines, roots and runtimes are in each cell record.

**Verified:** the four fixes the loop produced — the Go scope veto (fzf: 87 wrong syntactic edges), the Rust constructor rule (memchr: 7), the func-value abstract bucket (mux + cheerio: 47 false contradictions), the `@overload` anchor (click: 67 false suspects) — each kept every confirmed edge of its cell and moved no recall number. **Containment scope (P11):** fzf, memchr, mux, cheerio, click regraded under the sandbox image; toml and ajv are host-run records (not re-run: nothing moved on them).

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
plus 1 IIFE and 1 `let`-bound accessor called before assignment
(893), and the 3 declared misses above (1 function, 2 function-valued
variables) — 896.
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
| 2026-08-28 (**O7 regraded contained**, ADR-092 phase 2; [cell](oracle-cells/rust_proj-2026-08-28.md)) | `oracle.json` and `report.json` **byte-identical** to the 2026-08-25 cell modulo the `containment` field: 17/17 confirmed, recall 81.0% (17/21), the 4 `macro→function` misses; the ingest contained too (rust-analyzer 1.97.1 + rust-src in the image). 15 s |
| 2026-08-25 (**oracle lane O7**, ADR-089 phase 2) | **Compiler-graded against rustc's MIR** ([cell record](oracle-cells/rust_proj-2026-08-25.md)): **17/17 call edges confirmed**, 0 contradicted; recall 17/21 in-repo pairs over every resolved site — the 4 misses are calls criterion's `criterion_group!`/`criterion_main!` bodies make (`macro→function`). ADR-040's "33" reconciled: 17 `calls` + 16 `uses` symbol edges |
| 2026-08-16 (V2.M7 exit) | 33 call edges, **all semantic**; lanes clean at 17 sites |

**Verified:** the 17 call edges — **compiler-graded 2026-08-25 (O7)**,
17/17 confirmed by rustc's own resolution; the 2026-08-16 33/33
hand-check (ADR-040, the P7 proof) counted calls and uses together and
is superseded by the oracle for the calls. Rust's evidence base is now
this crate, memchr (the loop section) and dagger's `sdk/rust` (below),
all compiler-graded; this crate is the one Rust cell re-earned under
containment.

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
| 5th — **oracle lane O4 (ADR-089), 2026-08-25**, ingest f3cc3eb3 | **Compiler-graded, 19 Go modules** ([cell record](oracle-cells/dagger-go-2026-08-25.md)): 10,512 Hobbes call edges — **9,816 confirmed, 40 contradicted, 656 oracle-silent (all unreachable from any root)**; precision-against-oracle **99.6%**; 9,855 of 10,715 in-repo oracle pairs drawn across 24 roots (per-cell recalls 89–100%, never pooled); static calls to named declarations **9,854/9,889**. All 40 contradictions are **type conversions drawn as calls** (`dagger.JSON("0")` → `calls` to `type JSON`; 37 semantic, 3 syntactic) — the lane's first wrong edges in the semantic tier, a product defect for W1. Named misses: 16 recursion (**C-59**, dropped by design), 11 method-expression / generic-instantiation calls, 4 chain continuations (no site), 4 calls on an assignment's left side (drawn as `uses`); the rest C-58 (577 closures, 192 interface dispatches, 16 function-table, and 40 `func-value→closure` pairs RTA over-approximates — 860 misses in all, 825 after W1). Four modules not gradeable (docs: undeclarable deps; recorder/recorder2: generated package absent; e2e/helm/dagger: nothing to root at). **The root module does not fit this box as one program** (OOM at ~21 GB, H-9); graded by package subtree — see the cell record |
| 4th — after dependency provisioning (ADR-050) | ts/js **18.8% → 27.9%**; `sdk/typescript` **63.7% → 70.3%**; the docs zone indexes instead of failing (docs/versioned_docs 0% → 4.5% — the residue is example snippets importing `@dagger.io/dagger`, which no package.json declares: undeclarable, not unprovisioned). 8 lockfile-pinned trees provisioned into `~/.hobbes/cache/npm` (~833 MB, docusaurus dominating); every declined zone carries its C-34 reason (`no lockfile`). Lanes: 36,703 dual-resolved, 258 disagree — the +120 are all the TS decorator line-convention off-by-one (131 total, same declaration both sides; noted in future_additions), Go's 126 unchanged, **1** genuinely new |
| 3rd — after the cross-unit join (ADR-049) | go **85.6%** of 237,728 — cannot-resolve 20,501 → **5,571** (attr-call 4,655, unclassified 219); `core/integration [go]` **59.3% → 96.3%** (cannot-resolve 14,902 → 396). **161,184 call edges (+8,014 semantic)**, 24,723 module edges; **7,322** semantic `core/integration → sdk/go` edges (the `replace`d SDK, C-33's exact case). Two `scip-merge` abstentions reported (42 anonymous-TS-zone monikers, 7 generated Go testdata modules — C-28's rule across units, exactness holding). Lanes: 36,440 dual-resolved, **still 138 disagree — zero added by the join**. python/rust/ts unchanged, as they should be |
| 2nd — after wrapped-chain + per-unit degradation (ADR-048) | go **79.3%** of 237,728 (unclassified **359**, was 9,131) · python **89.1%** of 6,382 · rust **94.2%** of 8,595 · ts/js **18.8%** of 12,503 (`sdk/typescript` **63.7%**, was 0 — the docs zone now fails alone). 4,872 nodes, 24,452 module edges, 153,170 call edges. Lanes: 36,439 dual-resolved sites, **138 disagree (0.38%)** — 126 Go (fallback vs build tags/interface dispatch: C-7/C-8's floor measured), 11 a TS decorator line-convention off-by-one, both lanes citing the same declaration |
| 1st — baseline | go 79.3% (unclassified 9,131 — wrapped fluent chains) · ts/js **0.0%** (one broken docs zone zeroed all 84 zones) · python 89.1% · rust 94.2%. Found C-33: zero semantic edges from the root module into the `replace`d `./sdk/go` |

**Verified:** **no hand-checked edges** — documented deliberately
(Max: "leaving edge verification is fine as long as its documented").
What dagger evidences is the honesty machinery and the monorepo
structural fixes at scale, plus the two-module fixture's 0% → 100%
flip (`semantic`/`calls`) proving the C-33 lift's mechanism exactly.
Before O4 no §3.8 row existed for dagger and none was licensed; O4 licenses one — for the 19 graded Go modules, at the grain measured, and nothing wider. Every dagger run above is a **host-run record** (pre-ADR-092); a re-ingest under containment has not been made (its Go root needs a bigger box, H-9; its `sdk/rust` and `sdk/typescript` cells are the candidates when one is).

## Java — the four cells of 2026-08-29 (ADR-096, oracle lane O8)

The sixth language, built and graded in one session. Four repos: two
chosen for shape (a Maven library, a Spring service) and **two drawn at
random** from a seeded sample of GitHub's `language:java stars:300..3000
pushed:>2026-03-01` (seed 20260829) — the first time a Hobbes language
has been measured on repos nobody picked. All four contained (ADR-092);
cell records in [`oracle-cells/`](oracle-cells/).

| Repo | Files | Graph | Cell |
|---|---|---|---|
| **jhy/jsoup** `7860d088` (Maven library) | 197 | 250 nodes, 4,588 symbols, 12,665 call edges (12,663 semantic), 1,716 tests; capture 99.8% of 30,035 sites; lanes 3,417 / **0** | **18,627/18,627 confirmed, 0 contradicted — 100.0%**; recall 76.2% (18,767/24,630); [record](oracle-cells/jsoup-java-2026-08-29.md) |
| **spring-projects/spring-petclinic** `818c4136` (Spring service) | 50 | 130 nodes, 240 symbols, 296 call edges (all semantic), 76 tests; capture 100.0% of 1,607 sites; lanes 36 / **0** | **356/356 — 100.0%**; recall 98.4% (367/373); [record](oracle-cells/petclinic-java-2026-08-29.md) |
| **spring-data-elasticsearch** `cc7bd2b7` (**random draw 1**) | 739 | 944 nodes, 9,058 symbols, 12,832 call edges (all semantic), 1,341 tests; capture 100.0% of 33,559 sites (3 unresolved in the repo); lanes 3,908 / **2** | **16,050/16,050 — 100.0%**; recall 66.4% (16,238/24,452); [record](oracle-cells/spring-data-elasticsearch-java-2026-08-29.md) |
| **Legend-of-Dragoon-Modding/Severed-Chains** `3841686e` (**random draw 2**) | 1,254 | 1,344 nodes, 9,898 symbols, 3,955 call edges — **0 semantic**; lane B failed (C-67) | **10,154/10,154 syntactic edges confirmed, 0 contradicted — 100.0%**; recall **23.5%** (12,803/54,520); [record](oracle-cells/severed-chains-java-2026-08-29.md) |

**Verified:** **no hand-checked edges on any of the four** — every number
is compiler-graded against javac's own resolution (the `minijava`
fixture's eighteen pairs are hand-computed, in `internal/grade/java_test.go`).
Poison check PASS on all four, **0 falsely confirmed** in 45,187 seeded
wrong edges.

**What the four say, and what they do not.** Precision is 100% on every
cell, including the one with no semantic lane — the abstention rules
lane A was given (arity filtering, stopping at a type that declares
supertypes, declining an overload set outright) hold on 1,254 files of
code the resolver had never seen. Recall is the honest half: 66–98%
where lane B runs, **23.5% where it does not**, and `interface→method`
— C-58's Java face, graded against the CHA override set — is 84–91% of
every cell's misses. Java's dispatch hole is now a number per repo
rather than a prediction. What no cell covers: Android, Bazel, a
Kotlin-mixed tree, annotation-processor-heavy generation, or a private
registry — the sample is four ordinary Maven/Gradle repos, and C-67
already names the shape of the ones that fail.

**Three defects the cells produced**, all fixed in the same session:
two oracle-side (H-20 annotation-bearing keys, H-21 javac's synthetic
constructors — together 871 false contradictions before the fix) and
one product-side pair (44 `unclassified` sites on jsoup, every one an
enum-constant-body helper, now `local-binding`; a trailing comment
counted as a constructor argument on spring-data-elasticsearch, now
skipped — lane disagreements 3 → 2).

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
| scikit-learn (25102) | 1,052 nodes, 31,523 call edges; python **53.0%** of 82,674; 1 degradation — the duplicate-symbol row (defect D7, `adr085-validation-run.md`; **corrected by ADR-091**: the duplicate was *in-repo* — `doc/tutorial/text_analytics/{skeletons,solutions}/` — a legitimate C-28 record, not foreign environment residue; the defect was its Rust wording and `path: "."`, both fixed) |
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
