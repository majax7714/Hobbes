# The system's own claims

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-31 — "Supported" is a verified sample, not the language
- **Cannot tell you:** that ingesting *your* repo in a supported language
  will hold to the accuracy measured on the repos in architecture §3.8.
  The verification base is asymmetric by an order of magnitude: Python
  and TS/JS were proven across multiple repos of different shapes; **Go
  on exactly one repo — this one, a shape its own builders chose**;
  **Rust on one small repo**, 33 hand-checked symbol edges (17 calls, 16 uses) plus a fixture — since 2026-08-25/28 the Rust calls are compiler-graded on rust_proj, memchr and dagger `sdk/rust` instead.
- **Because:** hand-verification is per-repo work, and a language's long
  tail — frameworks, macro styles, build layouts, dynamic idioms — is in
  no sample. The machinery being shared (P7: zero builder lines per
  language) is precisely what lets a thin sample *look* like broad
  coverage: the sixth language ingests as smoothly as the first,
  whatever the graph then misses.
- **Bites at:** the decision to trust a graph on the first repo of a
  shape Hobbes has never seen; every sentence of the form "Hobbes covers
  X".
- **You find out:** **surfaced** (2026-08-21, ADR-053 — the candidate
  surfacing applied). §3.8's table is pinned in
  `extract/verification.py` and stamped into `graph.json` as
  `verification_base`, keyed by the artifact's own language names; the
  test suite reads §3.8 and fails if the two tables drift. Three places
  state it where a language list is read as a capability list: the
  ingest summary prints `verification base: go 1 repo, python 3 repos,
  … — a sample, not the language` directly under the language list and
  spells out every single-repo or unverified row; the surface's
  language badges carry `· N repos` with the §3.8 row as tooltip and
  badge single-repo languages in the stale colour, not as peers; and
  `list_blind_spots` prints the rows before any percentage. A language
  the table does not know is stamped `not verified on any repo`, never
  omitted. **What stays conceded** — and is now the entry's whole
  content: the systematic blind spot a thin sample never exercised
  still degrades nothing at runtime. The surfacing tells you how thin
  the base is; it cannot tell you what the base missed.
- **Source:** ADR-044; the owner's directive, 2026-08-16 — a coverage
  claim beyond its evidence is dishonest even when the machinery behind
  it is proven. Surfacing: ADR-053.

---

### C-60 — A runtime trace confirms; its silence is never a contradiction
- **Cannot tell you:** that a Python call edge is *wrong*. The oracle
  lane's Python answer key is the interpreter running the repo's own
  test suite (`sys.monitoring`, design §3.1): an observed (site, target)
  is a fact, and an edge the suite never exercised — 189 of 3,490 on
  this repo — is charged to nobody. An edge at a line that *did* execute
  with every observed callee elsewhere is **suspect**, a triage queue,
  never a contradiction: another input could still take Hobbes' target
  (4 of this repo's 10 suspects were exactly that — monkeypatched
  functions and the untaken branch of a one-line conditional).
- **Because:** runtime absence is coverage, not falsity. Python has no
  sound static oracle; the trace is the field's ground truth and it is
  asymmetric by nature. So a trace cell carries no precision number at
  all — a **confirmation rate** (coverage-limited) and
  **recall-against-executed** over a stated denominator, with a
  mandatory coverage line (sites spoken about, files loaded,
  declarations started, run count N).
- **Bites at:** every reading of a Python edge number in §3.8 and the
  evidence file. "94.3% confirmed" is not "94.3% precise" and the
  remaining 5.7% is not wrong; "86.2% recall" is recall of the executed
  slice, and a suite that covers less would report less about the same
  graph.
- **You find out:** **surfaced** (2026-08-25). `oracle grade` prints no
  precision line for a trace cell — the confirmation rate is labelled
  *coverage-limited, not precision*, the suspect line says *never
  contradicted*, and recall is printed with its run count and the
  coverage line on the same screen; the evidence rows say
  *trace-graded* and never *hand-checked*.
- **Source:** ADR-089 (D-O5), design §3.1; the first trace cell,
  2026-08-25.

### C-61 — A peer analyzer is a reference, never an oracle
- **Cannot tell you:** a precision-against-oracle number for anything
  graded against another static analyzer — PyCG, Jarvis, Scalpel for
  Python; Rupta for Rust; anything Pyright-derived for lane B, which is
  built on Pyright. Where such a lane runs it is labelled *reference*,
  its disagreements feed triage, and no precision or recall is computed
  against it.
- **Because:** the lane exists to escape grading Hobbes with a peer's
  error profile — the literature has the Python peers disagreeing with
  each other by tens of points, and a Pyright oracle would grade lane B
  with its own engine. Only a language's own toolchain (RTA, `tsc`,
  rustc's MIR) or its interpreter qualifies (design §2).
- **Bites at:** the temptation, when the compiler is silent (dynamic
  dispatch, `dyn`, generic bounds), to fill the gap with a stronger
  analyzer and quote the result as accuracy.
- **You find out:** **surfaced** by construction — the harness has no
  reference-lane input (Rupta was not run in phase 2; if it is, its
  export is a separate kind the grader refuses to bucket); the design
  and this entry say so.
- **Source:** ADR-089 (D-O6), design §2 and §7.

### C-62 — An oracle number is a pair with a denominator, per cell, and a contradiction is evidence
- **Cannot tell you:** "Hobbes' call-graph precision" or "recall" as one
  number. The four rules of design §3, registered late (phase 1 quoted
  them in every cell but never filed them): **the pair is always
  reported together**; **recall is never pooled or compared across
  cells** — it is driven by the roots the oracle had or the suite's
  coverage, so every recall prints its root count or coverage line;
  **oracle-silent is charged to nobody and its size is printed**; and
  **a contradicted edge is very strong evidence, not proof** — RTA is
  unsound under reflection and `go:linkname`, `tsc` under `any`, rustc
  under proc-macro tokens it never sees.
- **Because:** precision or recall alone is trivially gamed; a pooled
  recall averages a binary's roots with a library's test mains; a
  silent cell reads as a result; and an oracle's own grain produced the
  lane's first six "defects" (H-1..H-7), every one a false verdict
  against Hobbes.
- **Bites at:** every summary sentence — §3.8, the README, a
  collaborator's slide. The per-cell numbers stand; the aggregate does
  not exist.
- **You find out:** **surfaced** (2026-08-25). `oracle grade` prints
  the pair, the silent size and the root count / coverage line together
  and refuses to compute a pooled figure; `docs/oracle-cells/` keeps
  one record per cell; the evidence file's rows are per cell.
- **Source:** ADR-089, design §3 and §11.

### C-65 — The knowledge proxy is pinned to the image, not to the checkout; the hatch runs a host binary
- **Cannot tell you:** that the tools answering are built from the
  code you are reading. `.mcp.json` runs `sandbox/knowledge-serve`,
  which starts the proxy **inside** `hobbes-session:local` (ADR-094):
  the binary is whatever the image `COPY`'d at its last build. A
  rebuilt proxy with a stale image answers with the old code — the
  first smoke test of ADR-094 did exactly that (an image from 00:14,
  no phase-4 banner). And `HOBBES_KNOWLEDGE_HOST=1` runs this
  checkout's `go/bin/hobbes-proxy` on the host instead, which is the
  PATH-shaped risk the move removed.
- **Because:** pinning to the image is the point — the 2026-08-28
  incident was a symlink into an older checkout running lane B on the
  host with pre-ADR-092 code; a build the host resolves by name is
  the thing that cannot be trusted. The image is rebuilt by hand, so
  its age is a fact to state, not one to hide.
- **Bites at:** every session started after a proxy change without an
  image rebuild; any box without podman, where the launcher refuses
  and the hatch is the only way to the tools.
- **You find out:** **surfaced** (2026-08-28). `hobbes-proxy serve`
  prints `build <vcs.revision>[+dirty]` at start; every answer opens
  with `built by hobbes @ <sha> from <checkout>` from the artifact's
  `built_by` stamp, so a mismatch between the two is on the first
  line; the launcher refuses without the image naming the fix; the
  hatch announces itself on stderr as `HOST`.
- **Source:** ADR-094.

### C-75 — `hobbes lanes` compares lane A's module edges against the join's, which include lane A's own fallback
- **Cannot tell you:** how many module edges lane B actually produced.
  `extract/__init__.py` passes the *projected* module edges — raised
  from `ev.join(syntax, resolutions, fallback=fallback)`, fallback
  included — as `lane_b_edges`. On date-fns (2026-09-02) every one of
  the 200 "lane B only" module edges is `tier: syntactic` with
  tree-sitter evidence, while lane B produced exactly one semantic
  import edge; the self-test still printed `module edges compared:
  5093` and `the lanes agree wherever both can answer`.
- **Because:** the join is the only producer of module-level symbol
  edges (§3.4) and the comparison reads its output as lane B's; the
  `if b` guard ("only meaningful when lane B ran at all") cannot fire,
  because the fallback alone makes `b` non-empty. No disagreement is
  hidden — the site comparison keys on resolutions and is unaffected —
  but the module-edge count is not lane B's and reads larger than it.
- **Bites at:** the module-edge half of `hobbes lanes` on any repo
  where lane B is thin (C-8, C-74): a self-test that reports agreement
  between lane A and lane A.
- **You find out:** **unsurfaced** — the line reads as a lane B count.
  Candidate fix: pass only edges with semantic evidence as lane B's,
  and print `module edges: lane B produced N` beside the comparison.
- **Source:** the four-repo extraction test of 2026-09-02 (agent B).
  Registered, not fixed.

### C-76 — The ingest summary's "call edges" counts every symbol edge
- **Cannot tell you:** the number of `calls` edges from the summary.
  `cli.py` prints `len(graph['symbol_edges'])` as `call edges`; serde
  (2026-09-02) printed **4,361** where 1,557 are `calls` and 2,804 are
  `uses` (SCIP references no call site claimed, ADR-029); peft printed
  15,016 for 8,899 calls. `graph.json` is correct; the label is not.
- **Because:** the line predates `uses` edges (V2.M3) and was never
  relabelled.
- **Bites at:** anyone reading the summary as a call-graph size — the
  first number a user sees, inflated by the `uses` share (serde: 2.8×).
- **You find out:** **unsurfaced** — the only entry in the register
  that makes a number read *larger* than the truth since C-11 was
  lifted; the property "every Hobbes number is a floor" (README) does
  not hold for this line. Candidate fix: one line — print `calls` and
  `uses` separately.
- **Source:** the four-repo extraction test of 2026-09-02 (agents A and
  D). Registered, not fixed — the lead chose registration over a fix
  this session.

### C-77 — `list_blind_spots` drops the `below-floor` class from its tail
- **Cannot tell you:** C-58's per-directory count through the agent
  surface. `go/internal/knowledge/knowledge.go`'s `tailMeanings` — the
  list every tail line, glossary and "classes this lane cannot report"
  note iterates — has no `below-floor` row; `notModelled` does. So the
  proxy prints *seen, not modelled by design* **without** the class
  (peft: 4,626 where the ingest summary says 5,417 including
  `below-floor 791`), never explains it, and never reports it missing.
  Host build and image build both.
- **Because:** ADR-090 added the class to `tail.py` and the CLI and
  named `list_blind_spots` as its surfacing; the proxy's table was
  not widened. The `tests_guarding` header also omits the `built by`
  half the other five tools print (ADR-094) — same family, cosmetic.
- **Bites at:** an agent reading the blind-spot view of a directory
  where interface/closure calls dominate — the hole C-58 exists to
  name is the one class the view omits; the by-design total reads
  lower, the percentage is unchanged (not inflated).
- **You find out:** **unsurfaced** at the tool. C-58's own status stays
  *partial*, now with this gap named. Candidate fix: one row in
  `tailMeanings` (and the image rebuild C-65 requires).
- **Source:** the four-repo extraction test of 2026-09-02 (agent A).
  Registered, not fixed.
