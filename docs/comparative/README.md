# The comparative programme — Hobbes beside other code-graph tools, graded by the same compilers

**2026-09-09 (ADR-101, ADR-102).** This directory is the presentable
claim. It is built on one rule: **the comparison uses the oracle
lane, not a scoreboard.** The lane (`bench/oracle/`, ADR-089) grades
call edges against answer keys Hobbes does not control — x/tools RTA
for Go, `tsc` for TypeScript, CPython's `sys.monitoring` for Python,
rustc's MIR for Rust, javac with CHA for Java, clang's front end for C
and C++ (ADR-110, ADR-113) — and it does not care
who produced the edges. So the benchmark is: same repos, same
commits, same compiler answer keys, every tool's graph put through
them. A bar chart of self-reported "accuracy" with Hobbes on top is the
shape P8 exists to prevent, and it is out of scope by name.

What is here:

| file | what |
|---|---|
| [`field.md`](field.md) | One row per tool with a graph over a repo, agent-facing tools and public source — ten rows, every cell what the tool's own docs say, with the link, or *unstated*. §3 records numbers tools publish on other bases, compared nowhere. |
| [`tables.md`](tables.md) | **Generated** from the cell records: the standing Hobbes cells, and each foreign cell beside the Hobbes cell on the same key. Do not edit; regenerate. |
| [`graphics/one-number.svg`](graphics/one-number.svg) | The one number: 0 falsely confirmed of N seeded wrong edges across K compiler-graded cells, N and K summed from the poison lines, the exceptions printed. |
| [`graphics/precision-recall.svg`](graphics/precision-recall.svg) | One dot per cell, precision-against-oracle against recall, language as the panel, trace cells in their own panel, foreign cells in the same one-colour-per-tool markers as `same-key.svg`; hover for the miss classes. |
| [`graphics/same-key.svg`](graphics/same-key.svg) | **The comparison.** One row per cell that has a foreign graph on the same key: three markers on the precision axis and three on the recall axis, one colour per tool (blue dot Hobbes, orange square CodeGraphContext, green diamond repowise), grouped by language, repowise-bench's draws as their own band. Read across a row, never down a column. |
| [`graphics/date-fns-before-after.svg`](graphics/date-fns-before-after.svg) | Before / after on one repo, as the per-directory capture view that named the fix (C-74, C-90). |
| [`data/`](data/) | What the graphics are rendered from: `cells.json` (parsed from `docs/oracle/cells/`), `date-fns-capture.json` (parsed from two `graph.json` artifacts). |
| `docs/oracle/cells/<tool>-<repo>-<date>.md` | The foreign cells, one per tool × repo, in the same record format as a Hobbes cell: the loop and draws 2026-09-09, the C cells 2026-09-14, the C++ cells 2026-09-15. |

Everything numeric renders from the records by
`bench/oracle/report/render.py`; `render.py check` (run by the oracle
lane's Go suite) fails when a picture drifts from its cells.

**The versioned baseline (2026-09-10, Max's direction).** Every Hobbes
cell on this page was re-ingested on one build — **Hobbes 0.1.10-beta**
(ADR-103; first at 0.1.8-beta the same day, then again at 0.1.10-beta
after the Gradle attach route landed, every cell holding to the digit
but Severed-Chains, which gained its semantic lane) — and regraded
against its standing key, contained (the dagger modules, kbet and toml
for the first time at 0.1.8-beta); the foreign cells were not
regraded, since the tools did not change. The renderer reads
the version from each record's last regrade heading and prints it in
`tables.md` and on the graphics, so the page can say which Hobbes it
describes. The records distinguish changes from growth or refreshed keys
(this repo's two dogfood cells and click) from changed silent-edge
counts (hono, memchr and quic-go); each record's 2026-09-10 block
says what moved and why. One cell,
spring-data-elasticsearch, failed its first run under ADR-097's two
passes and exposed C-101 (the Java resolve stage held Kotlin sources;
the Maven wrapper's distribution was not cached for the offline pass),
fixed the same session and regraded 16,050/16,050.

**Since the baseline (2026-09-12).** C joined as the sixth
compiler-graded language at 0.2.4/0.2.5-beta (ADR-109/110): cJSON,
sqlite-vector and the minic fixture, graded against clang's own front
end. At 0.2.8-beta, ADR-111's acceptance regrade re-ingested every
cell with a stored key, 44 of them, contained, and graded each against
its standing key. A pre-veto pass reproduced every stored number first,
and afterwards no confirmed count moved anywhere. Only sqlite-vector's
grade changed (851/854 → 851/851), so only its record carries a
0.2.8-beta block, and the others' standing grades still read their
earlier version. That is why the graphics name several versions.

**C++, 2026-09-15.** C++ joined as the seventh compiler-graded language
(ADR-113, O10): fmt (chosen for shape) and Taywee/args (drawn at
random), graded against clang's front end at 0.2.21-beta and regraded at
0.2.22-beta after ADR-113 §2's third amendment, so their standing grades
name a fourth version. Both tools were graded on them the same day,
pre-registered first (`oracle-grading.md` §10.7), so each is a row of
`same-key.svg` (item 4 below).

## The claim, in the words the evidence licenses

1. **Hobbes draws nothing the compiler contradicts, on every
   compiler-graded cell, with two named exceptions.** Every
   compiler-graded semantic cell is at 100% precision-against-oracle
   except quic-go (3,766/3,781, a 99.6% lower bound; all
   fifteen are the test build's shadowing methods, 0 hobbes-wrong) and
   C++'s fmt (3,263/3,274, 99.7% after the 2026-09-16 regrade: 7 are
   the oracle's grain — H-31 alone, still open; 4 are hobbes-wrong,
   scip-clang naming a single wrong candidate that Hobbes draws, a
   provider's error owned as Hobbes' own, C-153). **That 99.7% is
   flattered by the fix that produced it, and the record says so:**
   H-28 and H-29 were the oracle's own errors and are fixed, but H-30's
   silence rule also withdrew judgement from 6 further C-153 rows, which
   are still wrong and now simply unjudged. Judging the rows the
   previous grade judged, fmt is **99.48%** (3,263/3,280). Both numbers
   are in the cell record.
   The two TypeScript cells that were exceptions closed by fixes, not
   by re-grading: ajv's three rows and six of hono's seven were one
   member call on a union-typed receiver drawn to the first member's
   method, closed by abstention (ADR-104, C-97 — ajv 1,375/1,378 →
   1,410/1,410 on 2026-09-09); hono's seventh was that shape at a site
   lane A could not type under hono's solution-style root tsconfig,
   closed when the helper learned to type a file by the referenced
   project that includes it (C-98 lifted, 768/768 on 2026-09-10).
   gitleaks' one syntactic contradiction (a stdlib import matched to
   the repo's same-named package) was fixed and regraded the same day,
   signed in its records. Precision-against-oracle
   is a **lower bound**: contradictions mostly triage to the oracle's
   own grain, and every record quotes its triage ratio (A-8).
2. **The grader says no.** Every cell grades a poisoned twin of its
   own export — each edge re-targeted to a declaration the oracle never
   resolved that site to — and the one-number graphic prints the sum:
   0 falsely confirmed, with N and K beside it and the cells not in the
   sum named.
3. **Here is how much Hobbes does not draw, and what it is.** Recall
   runs from 14.5% (C++'s fmt, over every resolved site) to 100.0% (the best of dagger's
   nineteen Go modules, each its own cell with its own root count, and
   C's sqlite-vector over its 1,091 resolved sites) across the
   compiler-graded cells, stated as a range and never averaged: each
   cell's denominator is its own roots or its resolved sites (C-62).
   The syntactic floor alone was measured once — Severed-Chains at
   23.5%, no semantic lane — and that cell reads 60.8% since
   0.1.10-beta, when the Gradle attach route gave it one.
   The misses are one register entry, C-58 — closures, interface
   dispatch, function values, code macros and derives wrote — tabled
   per cell in `docs/oracle/oracle-misses.md`. C++'s are tabled in its
   two records: constructions, the member calls and overload sets lane
   B leaves unsettled (C-143, C-151), and macro-heavy parses (C-145).
4. **Other tools' graphs, same keys.** CodeGraphContext 0.6.13 and
   repowise 0.49.0 were run as their READMEs document on the thirteen
   repos with keys on disk — the seven-repo loop of 2026-08-27 plus the
   random draws (quic-go, spring-data-elasticsearch, Severed-Chains)
   and the two Rust and Python cells — converted through a per-tool
   adapter with a hand-read fixture, and graded with the same matcher
   and the same poison check. Their numbers are in `tables.md` beside
   the Hobbes cell on the same key and in the scatter in the tool's
   own colour and shape. They are theirs **at our grain**: the converter is Hobbes'
   and a misread is Hobbes' defect (C-94); the matcher's tolerances were
   tuned on Hobbes' output (C-95); every competitor cell is host-run
   (C-96); and their contradictions are a lower bound on their
   precision exactly as ours is on ours — a 40-row random sample (five
   per tool per language) was read by hand: tool-wrong 39, oracle-grain
   1, converter-defect 0 *after* the sample found the converter's Java
   annotation-line defect (C-94) and the Java cells were regraded with
   signed direction lines. The rest of each cell's contradictions are
   untriaged and the records say so. **C, 2026-09-14:** both tools on
   the two C cells (cJSON, sqlite-vector) under the clang keys, once
   `oracle import` took `--lang c`. The first grade found repowise
   storing a function-like macro as `function`, so 562 of its 564
   cJSON contradictions and all 99 on sqlite-vector were edges to a
   `#define` graded against the callee clang saw in the expansion,
   where Hobbes' own macro edges are excluded because its graph says
   `macro` (C-95's C face). The converters now read a `#define` at
   the declared line as `macro` (converter@3, ADR-101's amendment of
   the same day), and the cells were regraded with signed direction
   lines, the first grade kept beside each: CodeGraphContext
   1,179/1,179 and 851/863 (nothing moved — it stored no edge to a
   `#define`); repowise 1,073/1,075 and 780/780. What is left is read
   in full: repowise's two are `setUp`/`tearDown` declared in a dead
   `#if` arm; CodeGraphContext's twelve on sqlite-vector are nine API
   names drawn into the vendored amalgamation the build never
   compiles with the extension and the three `strcasestr` shim rows
   Hobbes' own syntactic tier once drew (C-138). **C++, 2026-09-15:**
   both tools on the two C++ cells (fmt, args), pre-registered first
   (`oracle-grading.md` §10.7, P32–P35).
   - **CodeGraphContext reads no `.cc`, `.cxx` or `.hxx` file** (its
     parser table). So it graded nothing on args, and on fmt only the
     headers: 847/885 (**95.7%**), recall 11.8% — 844/975 (86.6%) as
     first run on 2026-09-15.
   - **repowise:** fmt 2,410/5,025 (**48.0%**, was 45.2%), recall 13.9%;
     args 815/904 (**90.2%**, was 87.0%), recall 23.3%.
   - **Hobbes, same keys:** fmt 3,263/3,274 (**99.7%**; 99.48% judging
     the rows the previous grade judged), recall 14.5%; args
     1,995/1,995, recall 56.4%.

   **Why every tool's number rose on 2026-09-16, and Hobbes' barely
   moved.** The oracle's own H-30 defect was fixed that day: a line the
   key left unresolved can no longer contradict anyone. Hobbes abstains
   where lane B is silent, so it draws almost nothing on such lines and
   13 of 44 foreign cells moved while **none** of Hobbes' 38 non-C++
   cells did; a name resolver guesses there, and the rule forgives
   exactly those guesses. The gap narrows for that reason, not because
   either tool improved — and it narrows on our own initiative, from a
   defect found in our grader and fixed against our own interest. Each
   moved cell record carries its signed before → after line.

   The seeded triage sample (60 rows) found two converter defects
   first, both Hobbes' (C-94): a `#  define` written with spaces, and a
   declaration head split over lines. converter@4 reads both (ADR-101's
   2026-09-15 amendment), and the cells were regraded with signed
   direction lines (repowise's fmt 42.3% → 45.2%). At @4 the sample
   reads tool-wrong 56, oracle-grain 4 (H-29 and H-30, then open in the
   key and both fixed on 2026-09-16, so those four rows would be graded
   differently today — the sample's ratio is as of its date),
   converter-defect 0. The tools' C++ errors are one shape above all: a
   call drawn by its short name to another declaration of that name —
   another class's member, the other overload, `std::end` drawn to a
   repo member `end()`.

## The 1-1 on repowise's draws

repowise-bench's G4 experiment pins five repos (cobra, gitleaks, syft,
zod, hono) and grades five tools against Go RTA and `tsc` at function
grain. Those pins were cloned, Hobbes ingested them contained, our keys
were built on this box (`oracle go-rta` with and without test packages
where the experiment has both cells; `ts/tsc-oracle.mjs` on zod's root
and hono's `tsconfig.build.json`), and both tools were run on the same
clones — so `tables.md` § *The 1-1 on repowise's draws* and the last
band of `graphics/same-key.svg` are three graphs on one key per cell: cobra (with tests), gitleaks (with and without
tests), zod, hono. **syft has no key on this box**: RTA over its
no-tests program was killed by the kernel at 18.7 GB and the with-tests
program at 19 GB (the H-9 shape, as quic-go's full program and dagger's
root were); the cell waits on a bigger box and is a row that says so,
not a skipped row. It is a 1-1 among the three; it is **not** a
comparison with repowise-bench's published numbers, whose key grain,
matcher and adapters are theirs. Each record says what Hobbes' own
ingest conceded on that repo (zod's pnpm workspace and hono's bun
lockfile are not provisioned — C-23, C-34 — so lane B was partial there
and the record quotes the capture line).

## What is not claimed

- Nothing from H1–H3, SWE-bench, DeepSWE, the test-time-training
  experiment or Calvin. Those are unearned as claims (architecture
  §6.2, `benchmark-hypotheses.md`), and a skeptic replicating one
  would undo what the oracle numbers buy.
- No "Hobbes covers language X". Every graphic and every table row
  names its cell (P11).
- No pooled recall, ever. Per cell, per root count. dagger's nineteen
  modules are nineteen dots.
- No collapsed recall as the number. Since 2026-09-10 every record
  carries a second line, `recall-collapsed` (the callee-shape bucket's
  identity, ADR-089 amended), which explains the gap on a `tsc` key;
  the graphics and this page read the per-signature line.
- No comparison with a number a tool publishes on another basis.
  repowise's hand-graded 84.8% and its own compiler-graded table (five
  tools, seven cells, on cobra / gitleaks / syft / zod / hono against
  Go RTA and `tsc`) are recorded in `field.md` §3 with their basis and
  put beside nothing here. That table is the same method on other
  repos; Hobbes on their draws under our key is the section above;
  their artifacts under our matcher would need edge files they do not
  publish (their experiment directory holds summaries).

## The objection, and the answer

"You wrote the grader." True. The answer is shipped, not argued: the
cell records, the poison lines on every one, the converter fixtures
read by hand, and one command a third party runs to grade their own
graph against the same key:

```sh
bench/oracle/grade-foreign.sh <your-edges.json> <oracle.json> <out-dir> --lang go
```

`<oracle.json>` is regenerated from the repo at the commit every cell
record names, with the oracle version it names (`oracle go-rta`,
`ts/tsc-oracle.mjs`, `oracle rust-mir`, `oracle java-javac`,
`oracle c-clang`, `oracle py-trace`). The edge file's shape and the rules a foreign graph
is read under are in `bench/oracle/README.md` § *Grading a graph
Hobbes did not build*. If they can grade themselves, the objection
dies; if the entry point were not public, it would stand.

## Regenerating

```sh
python3 bench/oracle/report/render.py cells      # docs/oracle/cells/*.md → data/cells.json
python3 bench/oracle/report/render.py render     # data/ → graphics/*.svg + tables.md
python3 bench/oracle/report/render.py check      # exit 1 on drift (the Go test runs this)
python3 bench/oracle/report/foreign_record.py --cell ~/.hobbes/bench/comparative/<tool>-<repo> ...   # a foreign cell's record from its artifacts
```

A new cell needs one row in `bench/oracle/report/cells.meta.json`
(language, where it ran, how the repo was chosen, a label — no
numbers), or `cells` refuses with the record's name.
