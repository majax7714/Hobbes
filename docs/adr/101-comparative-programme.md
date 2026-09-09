# ADR-101 — The comparative programme: other tools' graphs graded by the oracle lane, not a scoreboard

**Date:** 2026-09-09 · **Status:** accepted — built, the adapter tested on a hand-read fixture, two tools graded on the loop repos · **Owner:** Max · **Source:** Max's brief of 2026-09-09 (a presentable claim without Hobbes saying something about itself it has not earned)

Amends architecture **§3.8** (the oracle lane's paragraph: a foreign
graph is graded by the same entry point). Registers **C-94, C-95,
C-96** (`docs/constraints/system-own-claims.md`). Companion:
ADR-102 (the graphics as regenerated artifacts).

## Context

Hobbes' docs have grown past what someone joining can take in on first
contact, and the owner wants a comparison against other code-graph
tools and a small set of graphics. The tension — a presentable claim
versus P8 (every concession registered) and P11 (coverage scoped to
evidence) — resolves one way: **the comparison uses the oracle lane,
not a scoreboard.** The lane grades call edges against answer keys
Hobbes does not control (x/tools RTA, `tsc`, CPython's
`sys.monitoring`, rustc's MIR, javac + CHA; ADR-089). It does not care
who produced the edges. A bar chart of self-reported "accuracy" with
Hobbes on top is the shape P8 exists to prevent, and it is out of
scope by name.

Two facts shaped the design. First, the lane's export
(`internal/export`) reads a Hobbes `graph.json`, and its matcher's
tolerances — line grain on the site, the overload-set rule, the
callee's binding, the function-valued-binding bucket, the Rust macro
exclusion (D-O4) — were tuned on Hobbes' output; two of them read
Hobbes-specific metadata (`target_kind`). Second, the field moved: the
August reading (`how-hobbes-differs.md`) found no competitor publishing
compiler-graded precision; on 2026-09-09 repowise's README publishes a
five-tool, seven-cell table against Go RTA and `tsc`
(`docs/comparative/field.md` §3). So a 1-1 cell is possible in
principle, and the rules for one have to be written down before the
first is made.

## Decision

1. **One entry point for a graph Hobbes did not build.** `oracle
   import` (`internal/foreign`) converts a minimal edge file —
   `{repo, sha, tool, version, converter, edges:[{site:"file:line",
   callee:"file:line", caller?, kind?, label?}]}` — into the lane's
   `HobbesExport`, so `oracle grade` takes it exactly as it takes a
   Hobbes export, poison check included. `bench/oracle/grade-foreign.sh
   <edges.json> <oracle.json> <out-dir>` is the one command a third
   party runs to grade their own graph against the same answer key;
   every cell record names the command that regenerates its key from
   the repo at the same commit.
2. **One converter per tool, under `bench/oracle/adapters/<tool>/`,
   with the tool's version pinned and a hand-read fixture.** The
   converter is the risk: a bad conversion grades as the tool's error.
   So each ships in two stages — `dump` (the tool's own storage, rows
   as stored, nothing interpreted) and `convert` (rows → the minimal
   shape, stdlib only) — and a Go test that converts a committed dump
   of the `minigo` fixture and compares it to a hand-read truth, then
   grades it against the fixture's RTA key and requires the poison
   twin refused. A malformed position refuses the whole file; a
   converter never drops an edge silently (**C-94**: a competitor's
   edge our conversion misreads is our defect, not theirs).
3. **Which tolerances apply to a foreign graph, and why.** Everything
   on the oracle's side applies to every graph alike — line grain on
   the site, any declaration of the resolved overload set, the callee's
   binding rule, the `interface` abstract bucket, oracle-silent charged
   to nobody. The two rules that read the Hobbes graph's own metadata
   fire only when the converter supplies it: a callee `kind` of a
   variable makes a call through a function value `abstract` (never
   contradicted), and `kind: macro` excludes the edge before grading.
   A tool that carries no kind gets neither, and its cell says so
   (**C-95**: the tolerances were tuned on Hobbes' output; a foreign
   graph is read at the grain its converter can state). The tool's own
   confidence label becomes the edge's tier, so the report's per-tier
   split reads the tool's ladder and nobody has to guess which of its
   edges it believed.
4. **The poison check runs on the foreign graph too.** A cell without
   a poison line is not a cell. The seeded twin of a converted file is
   built the same way (each edge re-targeted to a declaration the
   oracle never resolved that site to), and the record quotes the
   line.
5. **The repos are the seven-repo loop of 2026-08-27 and the random
   draws, at the same commits, against the keys already on disk.**
   Picking is the thing the random draws were meant to take away from
   us; a competitor cell inherits that property only by reusing the
   draws. A tool that cannot run on a repo is a cell that says so, not
   a skipped row. Each cell is run as the tool's README documents
   (its happy path, nothing custom), and records wall time, the tool's
   own reported errors, whether the run needed a network or executed
   the repo, and — because both tools run on the host — that it is
   **host-run** (**C-96**: a competitor cell is host-run unless the
   tool runs under the sandbox image; its ingest is the tool's
   process on this box).
6. **A 1-1 cell exists only when both sides have the same measure on
   the same repo at the same commit against the same answer key.**
   A number a tool publishes on another basis — hand-graded rows, its
   own repos, its own adapter's reading — is recorded in `field.md`
   with that basis and never put in a table beside an oracle number.
   Different denominators in one column is the lie the register was
   built to stop (C-62).
7. **Non-goals, restated.** No claim from H1–H3, SWE-bench, DeepSWE,
   TTT or Calvin (unearned; §6.2, `benchmark-hypotheses.md`). No
   "Hobbes covers language X" — every row names its cell (P11). No
   pooled recall — per cell, per root count, always. The video demo is
   a separate item.

## Consequences

- The objection "you wrote the grader" is answered by shipping, not
  arguing: the cell records, the poison lines, the converter fixtures,
  and `grade-foreign.sh`. If a third party can grade themselves against
  the same key, the objection dies; the keys are regenerable from the
  named commits with the named oracle versions.
- The first two competitor tools (CodeGraphContext 0.6.13, repowise
  0.49.0) graded on 2026-09-09 sit in `docs/oracle-cells/` in the
  existing record format, one file per tool × repo, and in the
  scatter as a second marker (ADR-102). Their numbers are theirs at
  our grain; the records state every place the grain could be theirs
  instead (C-94, C-95).
- repowise's own compiler-graded cells (cobra, gitleaks, syft, zod,
  hono; its adapters for four other tools) are the obvious next 1-1
  shape — Hobbes graded on *their* draws by *our* key, or their
  artifacts re-read by ours. Parked until Max names it; `field.md` §3
  records what they publish and on what basis.
- `hobbes.json` stays the file name of the converted graph in a
  foreign cell's directory because `grade` reads it by that name; the
  header inside says whose it is.
