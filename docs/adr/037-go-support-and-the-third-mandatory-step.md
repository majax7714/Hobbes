# ADR-037 — Go support, and the checklist's missing third step

**Status:** accepted (2026-08-15)

**Milestone:** V2.M5. Amends the architecture's **§3.7** (the add-a-language
checklist) and generalises **C-6**. Evidence is reproducible via
`scip/spike-go.mjs`.

## Context

§3.7 says adding a language is:

1. Register the indexer (command, version pin, config rule).
2. *Optional:* enrichment pack(s) for its frameworks.
3. *Optional:* lane A grammar for structure/routes/tests **if richer syntax
   passes are wanted**.

V2.M5's exit criterion was written to test exactly that: *a Go repo ingests
with zero builder changes — the checklist was literally sufficient, and the
diff proves it.* Before building anything, the spike ran `scip-go` over this
repo's own Go tree (24 packages, 51 documents, 18,682 occurrences, **0.27s**)
and asked what the indexer actually provides.

## What the spike found

**1. `syntax_kind` is unset for 100% of 18,682 occurrences.** This is the
same field, and the same zero, that ADR-029 measured for `scip-python`
(0 of 8,575). Two independent indexers, two different implementations, both
leaving optional the one field that separates *a call* from *a type
annotation* from *a variable mention*.

That is the finding that decides this milestone. C-6 was registered as a
`scip-python` limitation. **It is not: it is the state of SCIP indexers
generally**, and the architecture had been treating lane A's call-site
detection as a Python/TypeScript implementation detail rather than as a
permanent requirement of every language.

**2. `--module-version` defaults to the git revision** (`7187f6c332a3` on
the run that found it). ADR-027's Decision 1 was written about
`scip-python`'s `--project-version`; the same trap, under a different flag
name, is in `scip-go`. Every node id would change on every commit.

**3. 27.9% of definitions are graph-worthy** (937 of 3,364), against ~14%
for `scip-python`. The descriptor filter is still needed and is less brutal
here — Go has no comprehensions and fewer synthetic locals.

**4. Monikers are legible and carry the package path**:
`scip-go gomod github.com/majax7714/Hobbes/go 0 \`.../internal/policy\`/Merge.`
The package is delimited by backticks, so it is extractable without
guessing.

**5. Documents can escape the repo root.** The index contains
`../../.cache/go-build/f1/f12bb51…-d` — the Go build cache. A join that
trusts `relative_path` would attribute occurrences to files outside the
repo, inventing nodes for paths the user has never seen.

**6. Third-party and stdlib both resolve** — `github.com/golang/go/src`
(4,952 occurrences), `modelcontextprotocol/go-sdk` (214), `gopkg.in/yaml.v3`
(35). Go has **no C-23 analogue**: the module cache is present whenever
`go build` works, so there is no "dependencies not installed" degradation to
detect.

## Decision

**§3.7 gains a third mandatory step, and step 3 stops being optional.**
Adding a language requires **two providers, not one**:

1. Register the **indexer** (resolution): command, version pin, config rule.
2. Register a **syntax provider** (detection): a lane A grammar that finds
   call sites with file, line, column and terminal name.
3. *Optional:* enrichment pack(s) for its frameworks.

The reason is finding 1 and it is not going to change on an upgrade: SCIP
makes `syntax_kind` optional and no indexer we have measured populates it.
Without a syntax provider a language gets definitions and references but
**no `calls` edges at all** — every resolution lands as `uses`, `who_calls`
answers nothing, and test reach is empty, because reach is the closure over
call edges. That is not "a less rich graph"; it is a graph missing the
relation the whole system is built to answer.

**P7 survives, narrowed and stated honestly.** "Languages are configuration,
not integrations" still holds for the *builder*: the graph builder, the
join, the schema and the packs need no Go-specific code. What P7 cannot
promise is that a language costs *nothing* — it costs one grammar walk,
which is a bounded, mechanical, per-language job with three existing
examples. The claim that was wrong is "an indexer entry plus an optional
pack"; the claim that survives is "nothing in the core changes".

Concretely for Go:

- **Lane A** — `extract/gosource.py` on `tree-sitter-go`, following the
  `tssource.py` contract: package-directory module ids, top-level symbols,
  import edges, `os.Getenv` env-reads for the cross-layer join, and call
  sites with column and terminal name for the evidence IR.
- **Lane B** — `scip-go` 0.2.7 in the helper's `INDEXERS`, with
  `--module-version` pinned to a constant (finding 2) and **documents whose
  path escapes the repo root dropped** (finding 5).
- **A pack** — `http-go`, `net/http` route registrations, on the V2.M4
  interface.

## Consequences

- **C-6 is rewritten as a general provider limit**, not a `scip-python` one,
  and cites both measurements. Under P9 it names both providers and
  versions. It is *not* liftable by an upgrade of one indexer, since it
  would have to be fixed by all of them.
- **The M5 exit criterion is answered "no", with evidence.** The checklist
  was not literally sufficient, and the diff proves the opposite of what it
  was written to prove. That is a better outcome than a milestone that
  passes because nobody checked: the correction is cheap now and would be
  expensive at V2.M7, where Rust would have hit exactly the same wall.
- **V2.M7 (Rust) inherits a corrected checklist.** rust-analyzer's SCIP
  output must be checked for `syntax_kind` before assuming it needs no
  grammar — and on the evidence of two indexers, it will need one.
- The Go build cache appearing in the index is a reminder that
  `relative_path` is the indexer's word, not a fact. The repo-root filter
  belongs in the helper, where it protects every language at once rather
  than in each join.
