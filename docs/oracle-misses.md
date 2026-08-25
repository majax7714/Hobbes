# Oracle lane — the miss record

**What this is.** Every oracle-graded cell's misses, by class, kept so
the question "what hurts the most, percentage-wise" has a standing
answer and the classes sharpen as cells accumulate (Max, 2026-08-25).
A *miss* is an oracle (site, target) pair Hobbes did not emit. Classes
are *how the call is made* × *what it reaches*; the class key is what
`oracle grade` prints. Percentages are of the cell's **honest** misses
— pairs a reachability oracle over-approximates (`func-value→*` under
RTA: every reachable function of the signature is a candidate) are
listed but marked inflated and kept out of the honest total, because
their denominator is an upper bound no run takes. Updated in the same
commit as the cell.

## Classes

| class | the call | what Hobbes does today | constraint |
|---|---|---|---|
| `static→named` | direct call of a declared function or method | drawn (the semantic lane's whole job) | — |
| `static→closure` | call of a closure bound to a local name (`run := func(...)`; `run(...)`) | **no edge** — closures are not graph symbols; lane A may name-match the local to a package function instead (a wrong edge) | C-58, C-7 |
| `interface→named` | invoke through an interface method | **no edge** — resolves to the interface method, which C-9's filter drops; no dispatch analysis | C-58 |
| `interface→closure` | invoke reaching a closure (function-typed interface) | no edge | C-58 |
| `func-value→named` | call of a function value reaching a declared function (a map of methods, a callback parameter) | **no edge** | C-58 |
| `func-value→closure` | call of a function value reaching a closure (`defer cancel()`, goroutine bodies) | no edge; under RTA the pair count is inflated | C-58 |

## Cells

### hobbes repo, `go` — 2026-08-25 (O2, RTA, 20 roots)

1,463 in-repo oracle pairs; 1,280 confirmed; **45 honest misses**,
138 inflated.

| class | hits / pairs | misses | % of honest misses |
|---|---|---|---|
| `static→named` | 1,280 / 1,280 | 0 | 0% |
| `static→closure` | 0 / 37 | 37 | **82.2%** |
| `func-value→named` | 0 / 6 | 6 | 13.3% — one site: `proxy.answer`'s map of the six `Store` methods (`internal/proxy/knowledge.go:141`) |
| `interface→named` | 0 / 2 | 2 | 4.4% — `io.Closer`-style `Close` on the recorder (`cmd/hobbes-web/main_test.go:106,131`) |
| `func-value→closure` (inflated) | 0 / 138 | 138 | — (10 sites; `defer cancel()` and goroutine bodies resolving to every `func()` in the program) |

**What hurts most here: calls into closures**, four-fifths of the
honest misses — and the same mechanism produced the cell's only wrong
edges (lane A binding a local closure name to a package function of
the same name, 3 syntactic contradictions). Interface dispatch, the
pre-registered favourite, is 2 of 45 in this codebase; the Go here is
shaped around concrete types and function tables, not interfaces, so
this ranking is a fact about *this repo* until dagger (O4) says
otherwise.

**Better classification wanted (open):** `static→closure` conflates a
closure called in the function that made it (the test helper shape)
with one stored and called later; and `func-value→named` at one site
with six candidates is a *table dispatch* the oracle counts as six
misses when Hobbes would need one `dispatch` edge to a table. Both
sub-classes need a marker the oracle does not carry yet (whether the
callee value was defined in the caller; whether the value came from a
composite literal). Add when a cell makes them matter.
