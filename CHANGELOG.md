# Changelog — the Hobbes layer

One entry per version of the Hobbes layer (ADR-103): what changed in
the product, in plain words, with the ADRs and constraints it rests on.
The experiments under `bench/` and the records under `docs/` are
internal testing and do not appear here except where a finding became
a fix. The session-by-session history is `docs/BUILDLOG.md`; the
running architecture is `docs/hobbes-architecture.md`. The number line
is Max's: after the next version the layer moves to **0.11.0-beta**,
not 0.2.0 (ADR-103 amendment, 2026-09-10); tags are his call each time
(0.1.9-beta untagged; the last tag is `v0.1.8-beta`).

## 0.1.9-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes refuses to stage and what it says
(C-66).** The Java resolve pass's stage (ADR-097) was meant to hold no
source the build compiles; the walk that built it copied `.mvn/`,
`gradle/` and `buildSrc/` whole, past both the JVM-suffix filter and
the pruning, so a source hidden under `.mvn/` or `gradle/` reached the
networked pass — found by the 2026-09-10 baseline review
(`docs/reviews/2026-09-10-baseline.md`). One walk and one rule now:
lane A's pruning in every directory, `.mvn/` the one dot-directory
entered, a JVM source left out wherever it sits except below
`buildSrc/`, whose sources are the build logic itself (the one
exception, unchanged). The ingest notice says so: "a networked pass
whose stage holds no application source (build logic under buildSrc/
excepted)".

- Tested at three levels: the file list, the resolve plan's stage, and
  the contained canary, which now plants `.mvn/Hidden.java` and reports
  the resolve pass through a sentinel in the Maven cache — the fourth
  probe's `Phoned` could never see that pass, whose stage is discarded
  before the index runs. Shown to fire under the old walk.
- `buildSrc/build/` and `buildSrc/.gradle/` no longer ride either.
- Bench tooling beside it (unversioned): the callee-shape bucket's
  identity fixed (H-22) and the two cells re-measured.
- Register: C-66 surfaced again; 101 entries, 75 active, 24 lifted, 2
  superseded.

## 0.1.8-beta — 2026-09-10 (the versioned baseline)

**Patch: a change in what Hobbes draws (C-101).** The Java resolve
pass's stage (ADR-097) held "no source", where source meant `.java`; a
Maven build with Kotlin sources compiled them against Java that was not
on the stage, failed, and the unit fell to lane A's syntactic tier —
surfaced by the degradation record, found when every Hobbes cell was
regraded on one build for the comparative graphics (Max, 2026-09-10).
The stage now holds no JVM source the build compiles (`.java`, `.kt`,
`.scala`, `.groovy`; `buildSrc/` stays), and the Maven resolve pass runs
the repo's `mvnw` when it ships one — scip-java's index pass runs that
wrapper, and only the networked pass can fetch its distribution into
the cache (petclinic had passed on a warm cache alone); `MAVEN_USER_HOME`
names that cache, since the Java wrapper ignores `$HOME`.

- spring-data-elasticsearch: the resolve pass succeeds again; the cell
  is regraded semantic (its record's 2026-09-10 block).
- **Every Hobbes oracle cell regraded on this build** against its
  standing key — the comparative graphics and `docs/comparative/tables.md`
  now state the Hobbes version per cell (`bench/oracle/report/render.py`
  reads it from the record's last regrade heading).
- Register: C-101 registered and lifted; 101 entries, 75 active, 24
  lifted, 2 superseded.

## 0.1.7-beta — 2026-09-10 (later still)

**Patch: a change in what Hobbes draws (C-100).** TypeScript's ESM- and
CJS-flavoured sources, `.mts` and `.cts`, are discovered: they were on
neither lane A's extension list nor the helper's, so such a file was
not a module, its calls were not counted, and scip-typescript's index of
it (the file is in the tsconfig's program) had nothing to join to —
absent without a degradation record. Found by the callee-shape bucket
of cheerio's miss set (`docs/oracle/oracle-misses.md`), which answered
Max's question about the recall gap between a `tsc` key and a
`tsc`-based indexer: at symbol grain the indexer emits 98.8–100% of the
function declarations the key names; the gap is the key's overload
grain (one pair per signature) and targets below the symbol floor.

- cheerio (the zone's own `tsc` 6.0.3): 2,682 → 2,688 edges, 2,622 →
  2,628 confirmed, 0 contradicted; the six `scripts/fetch-sponsors.mts`
  rows recovered; every function-declaration target on the cell drawn
  (1,911/1,911 collapsed pairs). zod does not move (no such file).
- Both lanes: `tsextract/extract.mjs`, `hobbes.extract.tssource`,
  `hobbes.extract.tail`; the grounder, the agent policy's test-command
  map and the harness's vitest rule take the same two extensions.
- Register: C-100 registered and lifted; 100 entries, 75 active, 23
  lifted, 2 superseded.

## 0.1.6-beta — 2026-09-10 (later)

**Patch: a change in what Hobbes draws (the C-98 lane asymmetry
closed).** 0.1.5-beta left the two lanes reading a solution-style
`tsconfig.json` differently: lane A typed a file by the referenced
project that includes it, lane B still indexed the zone under a
generated config written over the solution file (C-90's technique).
Now lane B asks the TS helper for the same zone map (`--zones`, the
compiler's own reading) and passes scip-typescript the referenced
projects that claim the zone's files, each under its own config, plus
a generated config for the files none claims — written *beside* the
solution file, which stays intact for any project that `extends` it.
One rule, one implementation, both lanes; if the helper's map is
unavailable the zone falls back to the old shape and the ingest says
so.

- hono: 768/768 unchanged, one edge moved from the syntactic to the
  semantic tier (727 semantic confirmed), lane agreement 4,332 →
  4,336 both-resolved sites with the same one line-grain disagreement;
  lane B produces 9 fewer module edges (1,483 → 1,474): a file no
  referenced project claims is its own program now, in both lanes, so
  its references into a claimed project's files take the cross-program
  shape C-12 registers.
- **ADR-105:** a lane B provider is a pinned batch program with a
  stated version and a tier stamp, never a language server — P13,
  stated in §3.2 and in §3.7's first step for the next language. No
  code moves.



**Patch: a change in what Hobbes draws (C-98 lifted).** Under a
solution-style `tsconfig.json` — `files: []` and project `references`,
hono's root, any `tsc -b` monorepo — the TS helper built the zone's
project from the solution file, which carries no compiler options: the
checker ran at its ES5 defaults, `Array.flat` was unknown, a receiver
reached through a newer lib was `any`, and every lane-A observation that
needs the type was absent — callee, origin and ADR-104's abstention
alike. The helper now resolves a file under a solution config to the
referenced project whose inputs include it, by the compiler's own
reading of the configs (references followed transitively inside the
repo, the first named claimant wins) — the lane-A analogue of C-90's
rule. A file no referenced project claims runs under the default
options and the ingest says so (`tsconfig-unclaimed`, one degradation
line per solution config, the files sampled).

- hono regraded against its standing key: 767/768 → **768/768
  (100.0%)**, 0 contradicted; 15 sites on `src/` are typed now and
  abstained as `union-member` (C-97). The claim page's one named
  exception is quic-go.
- Found on the way and fixed in both lanes (**C-99**, registered and
  lifted): a tsconfig with `references` and *neither* `files` nor
  `include` was taken for a solution config — the compiler's default
  include is then the whole directory, so hono's six
  `runtime-tests/*/tsconfig.json` zones had been indexed under the
  generated config instead of their own options.
- Facts schema unchanged (v5); `errors` gains a stage. Lane agreement
  on hono unchanged.

## 0.1.4-beta — 2026-09-09

**Patch: a change in what Hobbes draws (ADR-104).** A member call on a
union-typed receiver whose members do not share one declaration of that
member — `n: A | B`, both overriding, `n.render()` — no longer draws an
edge to the first member's method. scip-typescript and lane A's own
checker both named that member at semantic certainty, and the compiler
names a member too; none of them is the static answer, which is "one of
these". The TS helper (facts v5) types the receiver and abstains, the
evidence join vetoes lane B's occurrence at that site, and the tail
counts the site under a new class, **`union-member`** (TS/JS only;
`list_blind_spots` and the ingest summary gloss it). Registered as
**C-97**; C-58 gains its TypeScript face.

- ajv regraded against its standing key: 1,375/1,378 → **1,410/1,410**,
  now contained; hono 767/774 → **767/768**. The row left on hono is a
  site lane A cannot type at all: its root `tsconfig.json` is a
  solution-style config that leaves the helper's checker with no
  compiler options — registered as **C-98**, not yet lifted.
- The fixture `minits/src/union.ts` holds the shape; the proxy's tail
  glossary carries the class (image rebuilt).

## 0.1.3-beta — 2026-09-09

The first stated version, so this entry says what 0.1.3-beta *is*
rather than what changed. *beta*: graded, not stable — the schema and
the tool surface still move (ADR-103 §5).

**The knowledge layer** — a complete deployment on its own (ADR-092
phase 4): `hobbes ingest` builds `.hobbes/derived/` from a repo on
disk with no model, and `hobbes-proxy serve --knowledge-only` serves
six read-only tools over it from the sandbox image (ADR-087/094).

- Six languages, each a tree-sitter syntax provider joined by one
  range join to a pinned SCIP indexer: Python, TypeScript/JavaScript,
  Go, Rust, Java, plus Terraform/HCL structure (architecture §3.8).
- Every edge carries a tier (`semantic` / `syntactic`) and its evidence
  line; every site nothing resolved is counted and classed, never
  drawn (ADR-045/047).
- Everything that executes repo-authored code runs in the one sandbox
  image; `--uncontained` is disclosed and stamped (ADR-092, C-64).
- The constraint register: 96 entries, 74 active, each naming where a
  user meets the limit (`docs/constraints/`).
- Compiler-graded by the oracle lane: 0 falsely confirmed of 99,824
  seeded wrong edges across 19 cells; every compiler-graded cell at
  100% precision-against-oracle except three named ones
  (`docs/comparative/`, ADR-089/101).
- Every artifact and every knowledge answer states which Hobbes
  built it: now version and commit (ADR-094, ADR-103).

**The agentic layer** — sessions in rootless Podman under a Go policy
chain (deny overrides allow; allow | deny | escalate), the tool proxy
and flight recorder, `hobbes plan` / `hobbes run` deriving per-unit
context and policy from the graph (ADR-051/054), `hobbes review` at
the concept level with compiled invariants, `hobbes verify` (ADR-100).
Under test; no benchmark claim earned (architecture §6.2).

**Not in the version:** the oracle lane and its foreign converters,
the benchmark harness, Calvin, the test-time-training and Atlas-0
instruments — `bench/`, internal testing.
