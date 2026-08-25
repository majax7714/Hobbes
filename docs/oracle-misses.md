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
| `func-value→local-binding` | call through a local that holds a value, not a function literal (`const [x, setX] = useState()`; `setX(...)`) | **no edge** — the binding is below the symbol floor; the site is *seen and not modelled by design* (C-32's `local-binding` class) | C-32, C-58 |
| `func-value→variable` | call through a module-level variable holding a function value (a `let` accessor assigned at runtime) | drawn when the variable is a graph symbol; missed when the value arrives later | C-58 |
| `interface→type-member` | call of a member declared only as an interface property signature (a zustand store's `ChatState.addMessage`) | **no edge** — interface members are not graph symbols (C-9) | C-58 |
| `static→anonymous-function` | an IIFE or a literal passed straight to a call | no edge | C-58 |

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

### kbet, `betchat/frontend` — 2026-08-25 (O3, the zone's `tsc` 5.9.3, resolution oracle)

1,529 in-repo oracle pairs over every resolved site; 633 confirmed;
**896 misses**, none inflated (a resolution oracle names one
declaration per site).

| class | hits / pairs | misses | % of misses |
|---|---|---|---|
| `static→function` | 483 / 484 | 1 | 0.1% |
| `static→variable` | 23 / 23 | 0 | 0% |
| `func-value→variable` | 119 / 121 | 2 | 0.2% — `getAuthStore?.()`, a `let` assigned at runtime (`api/axios.ts:19,30`) |
| `static→class` | 8 / 8 | 0 | 0% |
| `func-value→local-binding` | 0 / 625 | 625 | **69.8%** — `useState` setters and callbacks held in locals |
| `static→closure` | 0 / 195 | 195 | **21.8%** — handlers declared inside components (`handleAction`, `renderCompose`) |
| `interface→type-member` | 0 / 71 | 71 | 7.9% — store members through their interface (`ChatState.addMessage`, `WalletState.fetchBalance`) |
| `static→anonymous-function` | 0 / 1 | 1 | 0.1% — an IIFE (`test/setup.ts:4`) |
| `static→type-member` | 0 / 1 | 1 | 0.1% |

**What hurts most here: local bindings**, seven-tenths — and most of
those are React state setters, which no reader would want as call
edges; they are the tail C-32 already names as *by design*. The class
that actually loses architecture is the **store members through
interfaces** (71): `who_calls(addMessage)` answers nobody for the
zone's central state mutations. Closures (195) are the same story as
Go's. Everything Hobbes *declares* a symbol for it also draws: 633 of
637.

### dagger, 19 Go modules — 2026-08-25 (O4, RTA, 24 roots across the cells)

Per-cell rows in `oracle-cells/dagger-go-2026-08-25.md`; the sums
below are sizes, not a pooled rate. 10,715 in-repo oracle pairs; 9,855
drawn; **819 honest misses**, 41 inflated.

| class | hits / pairs | misses | % of honest misses |
|---|---|---|---|
| `static→named` | 9,854 / 9,889 | 35 | 4.3% — 16 recursion (**C-59**), 11 method expressions / generic instantiation calls, 4 chain continuations (no site at all), 4 calls on an assignment's left side (drawn as `uses`) |
| `static→closure` | 0 / 577 | 577 | **70.5%** |
| `interface→named` | 0 / 192 | 192 | **23.4%** — dagger modules dispatch through interfaces far more than this repo does |
| `func-value→named` | 0 / 16 | 16 | 2.0% |
| `func-value→closure` (inflated) | 1 / 41 | 40 | — |

**What hurts most here:** closures again, seven-tenths — but interface
dispatch is now a real second at 23%, where in this repo it was 4%:
the ranking moves with the codebase's style, which is why the record
is per cell. **What is new:** the four *named* shapes above are not
C-58 — they are direct calls Hobbes should draw and does not, and one
of them (chain continuations) is invisible to the capture number too.
And the cells' 40 contradictions are all one product defect, **a type
conversion drawn as a call**, which is a lie rather than a silence.

**Better classification wanted (open):** `static→closure` conflates a
closure called in the function that made it (the test helper shape)
with one stored and called later; `func-value→local-binding` conflates
a React state setter (never wanted as an edge) with a callback whose
provenance a reader *would* want; and `func-value→named` at one site
with six candidates is a *table dispatch* the oracle counts as six
misses when Hobbes would need one `dispatch` edge to a table. Both
sub-classes need a marker the oracle does not carry yet (whether the
callee value was defined in the caller; whether the value came from a
composite literal). Add when a cell makes them matter.
