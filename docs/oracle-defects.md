# Oracle lane — the defect record

**What this is.** The oracle grades Hobbes; nothing grades the oracle
except the fixtures and triage. So every defect found in the harness or
an oracle extractor is logged here — what it looked like, what it was,
how it was fixed, and **what it would have cost had it gone unnoticed**
(Max, 2026-08-25: "always honest"). A harness that only records
Hobbes' errors is a harness that flatters itself. Updated in the same
commit as the fix; a defect found but not yet fixed stays here as open.

| # | Date / cell | Looked like | Was | Fix | Cost if unnoticed |
|---|---|---|---|---|---|
| H-1 | 2026-08-25, O1 `minigo` | No test function reachable; the `lib` cell of `twomod` had **no sites at all** | RTA rooted at `main` only; the synthesized test main's table of `Test*` functions is address-taken in its `init`, which `main` never calls | Root at `init` as well as `main` for every main package (as `x/tools`' own `callgraph` does) | Every library module would have graded empty — "no roots" reads as "nothing to grade", and O4's 25 dagger modules are mostly libraries |
| H-2 | 2026-08-25, O1 `twomod` | The `app` cell reported a site in `lib/` | Sites were scoped to the repo, not the cell's module; a replaced sibling module is inside the loaded program | Sites and loaded files limited to the module directory; targets may land anywhere | Cross-cell double counting and spurious `not-loaded` silences on every multi-module repo |
| H-3 | 2026-08-25, O2 `hobbes go/` | 2 contradictions: `sortedKeys(...)` at `knowledge.go:786/819` graded as a call to `sort.Strings` | The synthetic-function unwinder treated a **generic instantiation** as a wrapper and followed into its body, attributing the callee's callees to the caller's site | Instantiations (`Origin() != nil`) are source functions; fold to origin, never unwind | Every call to a generic function would have contradicted Hobbes' correct edge — a false "hobbes-wrong" verdict that scales with how generic the codebase is (dagger's `sdk/go` is) |
| H-4 | 2026-08-25, O2 | Recall 87.5% with 138 of 183 misses at 10 sites, all `defer cancel()`-shaped | Not a bug but an unreported property: a reachability oracle resolves a `func()` value to **every** reachable `func()`, so the recall denominator was an upper bound nobody stated | Recall split by class; `func-value→*` under RTA printed as *inflated*; the static number is the tight one | A recall number quoted without its inflation would have understated Hobbes by up to ~10 points on this cell and been compared across cells (rule 2 violated silently) |
| H-5 | 2026-08-25, O3 kbet | **119 contradictions (precision 81%)**, every one a `useAuthStore()`-shaped call graded against zustand's `react.d.mts:19` | `tsc`'s declaration for a call through a `const` of callable type is the **anonymous call signature** in the type, while Hobbes and scip bind the callee to the variable. The oracle's grain, not Hobbes' error | The binding rule (D-O4): behind an anonymous signature the callee's identity is its binding; the oracle lists the binding and not the signature | 119 false "hobbes-wrong" verdicts — every React hook, store, and callback call in every TS zone; the lane would have reported TS precision at ~80% and been believed |
| H-6 | 2026-08-25, O3 kbet | A miss whose target name was a **file path** (`autoUpdate.test.ts:43`) | A dynamic `import()` resolved to a source file, which the oracle listed as a call target | Source-file declarations are not targets | One spurious miss per dynamic import; small, but a class of pair that is not a call |
| H-7 | 2026-08-25, O3 kbet | 826 misses classed `closure`, 84% of all | `const [x, setX] = useState()` bindings were classed as closures because they are declared inside a function; the binding is a *value*, not a function literal | `local-binding` split from `closure`; TS sites given a mode from the binding's shape so Go and TS classes read alike | The miss record's headline ("closures hurt most") would have been wrong about *what* is missing — state setters, which no reader wants as edges, would have been counted as lost architecture |
| H-8 | 2026-08-25, O3 kbet | Caller names in the triage rows were whole arrow-function bodies | Cosmetic: anonymous callers printed their source text | `<anonymous>` | None to the numbers; triage rows unreadable |

**Pattern so far.** Six of eight are the oracle being *right at a
different grain* than Hobbes (H-3, H-5, H-6, H-7) or *silent in a way
that reads as a result* (H-1, H-4). Neither shape produces a Hobbes
error — both produce a **false verdict against Hobbes**, and the only
thing that caught them was a fixture with hand-computable truth (H-1,
H-2, H-3 via `testdata/generic`) or triage of the contradicted rows
(H-5, H-6). That is the argument for never quoting a cell's number
before its triage is complete (design §8), restated as evidence.

**Open:** none.
