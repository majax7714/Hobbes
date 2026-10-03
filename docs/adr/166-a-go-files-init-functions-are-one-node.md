# ADR-166 — A Go file's `init` functions are one node, and a fact inside a later one is the node's

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: route **1** of three, "map each later `init`
into the node") and **built** (0.2.92-beta) · **Owner:** Max · **Source:** the duplicate-qualname
measurement (`~/.hobbes/bench/dup-qualnames-2026-10-02/RESULTS.md`), this ADR's probe and regrade
(`~/.hobbes/bench/c183-go-inits/`).

Extends ADR-155 (a later def's lines join the enclosing lookup) from Python to Go's `init`, and only to
it. Registers **C-183** (surfaced). Draws no new edge; it moves where a fact is filed.

## What is wrong

Go lets a file declare any number of package-level `func init()` and runs every one, in order, before
`main`. No code can name or call an `init`. Lane A's id is `<module>.<qualname>` (ADR-021) with one module
per file, so every `init` in a file mints `<module>.init`; the node is the first def.

A lane B `uses` fact carries no lane A scope; the projection files it by the enclosing lines, and a later
`init` encloses nothing the index knows. So a use written inside a later `init` was filed under the
**module**. On dagger, `internal/cmd/dagger/main.go` writes `init` at 103–109 and at 143–245 (the second
groups the commands: `agentCmd.GroupID = "daily"`). The probe on the stored graph read, inside 143–245:
68 lane B `uses` under `internal/cmd/dagger/main`, and 7 lane B `calls` already under
`internal/cmd/dagger/main.init`.

## Measured

| cell | files with two or more `init` | lane B `uses` in a later `init`, filed under the module | `calls` there |
|---|---:|---:|---:|
| dagger | 22 | 89 | 7 (already the node's) |
| fzf, mux, toml, cobra, quic-go | 0 | 0 | 0 |
| this repo | 0 before the fixture | 0 | 0 |

## The decision (Max: route 1)

1. **Lane A lists a file's `init` defs** where it writes two or more: `gosource.init_spans`, keyed by
   `<module>.init`, every def's `(line, end_line)`. A method named `init` has a receiver and its own
   qualname, and is not listed. The bundle carries `init_spans`.
2. **The later defs join ADR-155's later defs** (read off the settled symbols, so "later" is every def
   but the node's). They join the enclosing lookup only: a fact written inside a later `init` is the
   node's. Nothing can resolve *onto* an `init`, so the start lookup needs nothing.
3. **One `go-inits` degradation record per ingest** with such a file, naming C-183, with examples and the
   later defs' lines. `list_blind_spots` and the ingest summary show it.

**Why this and not a refusal.** C-180 refuses because a later Rust impl def is a *different function* that
a caller can reach; filing its facts under the first def drew a recursion that does not exist. Every
`init` in a file is unreachable by name and runs on the same occasion (package initialisation), so "the
file's `init`" is a true source for each fact, and the evidence line tells the defs apart. The calls in a
later `init` were already filed this way.

## Alternatives considered

- **Refuse, as C-180 does** (route 2). Honest, but it draws less than the index proves: dagger would lose
  the 89 uses and the 7 calls, and nothing about the edge is false.
- **Distinct ids, `init~2`** (route 3, Java's overload suffix). It changes symbol ids for a distinction no
  caller can use.
- **Leave the uses under the module.** True but too broad, and unregistered: no tool named it.

## Built (0.2.92-beta)

`extract/gosource.py` (`init_spans`, the bundle key), `extract/__init__.py` (the later inits merged into
`later_defs` before the projection, `_go_init_record`). Tests: `test_go_inits.py` (the spans and the
method near miss, the projection with and without the spans, lane A alone on the `minigoinit` fixture,
lane B's answer hand-built, and the `lane_b` ingest with scip-go on the host). The fixture is dagger's
first `init` verbatim and a second written in its shape.

**Regrade** (`~/.hobbes/bench/c183-go-inits/`: `before/dagger-graph.json`, the stored graph from the
0.2.89-beta session; `after-dagger-graph.json`; `compare.py`): dagger re-ingested contained. Go-file evidence
rows 219,419 before and after; exactly **89 moved**, each from its module to `<module>.init` at the same
path, line, lane, type and target, and nothing else moved; Go symbols identical; one `go-inits` record names
22 files. No `calls` row moved, so the dagger call grade cannot move and was not re-run. The before graph
predates 0.2.89/0.2.90, which moved only Rust and Python, so only Go-file evidence is compared.
