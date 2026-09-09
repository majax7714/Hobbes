# The comparative programme — Hobbes beside other code-graph tools, graded by the same compilers

**2026-09-09 (ADR-101, ADR-102).** This directory is the presentable
claim. It is built on one rule: **the comparison uses the oracle
lane, not a scoreboard.** The lane (`bench/oracle/`, ADR-089) grades
call edges against answer keys Hobbes does not control — x/tools RTA
for Go, `tsc` for TypeScript, CPython's `sys.monitoring` for Python,
rustc's MIR for Rust, javac with CHA for Java — and it does not care
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
| [`graphics/precision-recall.svg`](graphics/precision-recall.svg) | One dot per cell, precision-against-oracle against recall, language as the panel, trace cells in their own panel, foreign cells as hollow squares; hover for the miss classes. |
| [`graphics/date-fns-before-after.svg`](graphics/date-fns-before-after.svg) | Before / after on one repo, as the per-directory capture view that named the fix (C-74, C-90). |
| [`data/`](data/) | What the graphics are rendered from: `cells.json` (parsed from `docs/oracle-cells/`), `date-fns-capture.json` (parsed from two `graph.json` artifacts). |
| `docs/oracle-cells/<tool>-<repo>-2026-09-09.md` | The foreign cells, one per tool × repo, in the same record format as a Hobbes cell. |

Everything numeric renders from the records by
`bench/oracle/report/render.py`; `render.py check` (run by the oracle
lane's Go suite) fails when a picture drifts from its cells.

## The claim, in the words the evidence licenses

1. **Hobbes draws nothing the compiler contradicts, on every
   compiler-graded cell, with two named exceptions.** Every
   compiler-graded semantic cell is at 100% precision-against-oracle
   except ajv (1,375/1,378 — one union-member shape, n=1, unfixed) and
   quic-go (3,766/3,781, a 99.6% lower bound; all fifteen are the test
   build's shadowing methods, 0 hobbes-wrong). Precision-against-oracle
   is a **lower bound**: contradictions mostly triage to the oracle's
   own grain, and every record quotes its triage ratio (A-8).
2. **The grader says no.** Every cell grades a poisoned twin of its
   own export — each edge re-targeted to a declaration the oracle never
   resolved that site to — and the one-number graphic prints the sum:
   0 falsely confirmed, with N and K beside it and the cells not in the
   sum named.
3. **Here is how much Hobbes does not draw, and what it is.** Recall
   runs from 23.5% (Severed-Chains — no semantic lane, the syntactic
   floor measured) to 98.4% (spring-petclinic) across the
   compiler-graded cells, stated as a range and never averaged: each
   cell's denominator is its own roots or its resolved sites (C-62).
   The misses are one register entry, C-58 — closures, interface
   dispatch, function values, code macros and derives wrote — tabled
   per cell in `docs/oracle-misses.md`.
4. **Other tools' graphs, same keys.** CodeGraphContext 0.6.13 and
   repowise 0.49.0 were run as their READMEs document on the thirteen
   repos with keys on disk — the seven-repo loop of 2026-08-27 plus the
   random draws (quic-go, spring-data-elasticsearch, Severed-Chains)
   and the two Rust and Python cells — converted through a per-tool
   adapter with a hand-read fixture, and graded with the same matcher
   and the same poison check. Their numbers are in `tables.md` beside
   the Hobbes cell on the same key and in the scatter as hollow
   squares. They are theirs **at our grain**: the converter is Hobbes'
   and a misread is Hobbes' defect (C-94); the matcher's tolerances were
   tuned on Hobbes' output (C-95); every competitor cell is host-run
   (C-96); and their contradictions are printed **untriaged** — a
   lower bound on their precision exactly as ours is on ours.

## What is not claimed

- Nothing from H1–H3, SWE-bench, DeepSWE, the test-time-training
  experiment or Calvin. Those are unearned as claims (architecture
  §6.2, `benchmark-hypotheses.md`), and a skeptic replicating one
  would undo what the oracle numbers buy.
- No "Hobbes covers language X". Every graphic and every table row
  names its cell (P11).
- No pooled recall, ever. Per cell, per root count. dagger's nineteen
  modules are nineteen dots.
- No comparison with a number a tool publishes on another basis.
  repowise's hand-graded 84.8% and its own compiler-graded table (five
  tools, seven cells, on cobra / gitleaks / syft / zod / hono against
  Go RTA and `tsc`) are recorded in `field.md` §3 with their basis and
  put beside nothing here. That table is the same method on other
  repos; Hobbes on their draws, or their artifacts under our matcher,
  is the parked next 1-1 (ADR-101, consequences).

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
`oracle py-trace`). The edge file's shape and the rules a foreign graph
is read under are in `bench/oracle/README.md` § *Grading a graph
Hobbes did not build*. If they can grade themselves, the objection
dies; if the entry point were not public, it would stand.

## Regenerating

```sh
python3 bench/oracle/report/render.py cells      # docs/oracle-cells/*.md → data/cells.json
python3 bench/oracle/report/render.py render     # data/ → graphics/*.svg + tables.md
python3 bench/oracle/report/render.py check      # exit 1 on drift (the Go test runs this)
python3 bench/oracle/report/foreign_record.py --cell ~/.hobbes/bench/comparative/<tool>-<repo> ...   # a foreign cell's record from its artifacts
```

A new cell needs one row in `bench/oracle/report/cells.meta.json`
(language, where it ran, how the repo was chosen, a label — no
numbers), or `cells` refuses with the record's name.
