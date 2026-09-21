# Oracle grading — precision and recall for the call graph against answer keys we do not control

**Status: phase 1 built and run (O1–O4, 2026-08-25; the dagger root
waits on a bigger box); phase 2 built and run the same day — O6 (§6,
this repo's Python zone under its suite; xarray not run: no workspace on
the box) and O7 (§7, `rust_proj` and dagger's `sdk/rust`; Rupta and the
trace lane not attempted); O8 (§7b, javac with CHA, 2026-08-29,
ADR-096) and O9 (§7c, clang's front end, 2026-09-12, ADR-110) built and
run since, contained. Every compiler-graded cell is at 100% except
quic-go's 99.6% lower bound. Cell records in `docs/oracle/cells/`; the
harness README carries the Python and Rust conventions.** This document is the context for the
build session(s) that implement it. **Owner:** Max. **Scope:** bench tooling only
— no product change. Reads with: architecture §3.8 (the claim table),
`extraction-evidence.md` (the evidence log), `docs/constraints/`,
ADR-048/049/050 (dagger), ADR-037/040 (the existing hand-checks). Decisions
D-O1–D-O6 (§12) are carried in ADR-089.

*Revision note.* The first draft declared Python and Rust oracle-less,
inherited from a competitor's framing. A search (2026-08-25) falsified
that: runtime-trace oracles are the research-standard ground truth for
dynamic languages, Rust admits a compiler-authoritative partial oracle plus
an independent research analyzer, and a directly relevant
execution-verified benchmark (TraceEval) shipped in 2026. §2 now carries an
oracle taxonomy, §6–§7 the new lanes, and §15 the provenance.

## 1. Why this exists

Hobbes' headline extraction metric — capture % of detected call sites — is
neither precision nor recall. The denominator is sites Hobbes detected (a
floor by design), and a resolved site is not a verified-correct binding.
The evidence base for correctness is currently:

- **Hand-checks, small-n, self-selected.** Go 20/20, Rust 33/33, kbet
  20/20, private-repo-A's full JS edge set — all 100%, but at n=20 the
  exact 95% lower bound on true precision is ~83%, at n=33 ~89%. Every
  check so far is consistent with anything from ~85% up. The samples also
  have no documented selection procedure.
- **Lane agreement**, which is real machinery (36,703 dual-resolved sites
  on dagger, 258 disagreements, decomposed) but is two of our own methods
  agreeing. Shared blind spots are invisible to it, and it covers only
  dual-resolved sites.
- **The largest measurement is the least verified.** dagger (265k sites,
  161k edges) carries zero graded edges, documented deliberately.
- **Downstream validation is uncounted.** Inspecting agent-loop prompts
  against benchmark assignments, and field use as an edge tool, have
  surfaced no wrong edge — but neither has a denominator, a selection
  rule, or a log. That is anecdote, and it stays out of the evidence file
  until §13 gives it a countable form.

The fix is **an answer key we do not control.** This gives us, for the
first time:

- **Precision at scale** — every edge graded, not 20.
- **Recall** — a number Hobbes has never had in any form: of the true call
  graph (or a well-defined executed slice of it), how much did we find.
- **A graded dagger** — the scale evidence and the accuracy evidence
  finally coincide in one repo.

## 2. Oracle taxonomy and scope

An **oracle** here means: an edge source that is (a) independent of
Hobbes' machinery, (b) grounded in something authoritative about the
language, and (c) regenerable by anyone with the toolchain. Three kinds
qualify, with different grading semantics:

- **Resolution oracles** — the language's own checker resolves each call
  site. TypeScript via `tsc`; Rust's static/generic dispatch via
  monomorphized MIR. Authoritative per site; can confirm and contradict.
- **Reachability oracles** — the language's own toolchain computes a
  whole-program call graph from roots. Go via
  `golang.org/x/tools/go/callgraph/rta`. Confirms, contradicts (with the
  unsoundness caveat, §3 rule 4), and yields recall.
- **Runtime-trace oracles** — the interpreter/instrumented binary records
  edges actually taken while running the test suite. Python via
  `sys.monitoring` (PEP 669); optionally Rust via instrumented builds. The
  runtime is the ultimate authority, but asymmetric: an observed edge is a
  fact, an unobserved edge is not a falsehood. Confirms and establishes
  definite misses; never contradicts (§3.1). This is the research-standard
  ground-truth method for dynamic languages — the Jarvis/PyCG ground
  truths, DyPyBench, and TraceEval are all built this way.

**Not oracles, ever:** peer static analyzers (PyCG, Jarvis, Scalpel for
Python). They are competitors with their own error profiles — the
literature has them disagreeing with each other by tens of points — and
grading against one is grading against a peer, the failure mode the whole
lane exists to escape. One partial exception in §7: Rupta may run as a
labelled **reference lane** (independent, serious, but not authoritative),
whose disagreements feed triage, never a precision-against-oracle number.

**Independence trap, named once:** anything Pyright-derived is not an
oracle for Hobbes — lane B's `scip-python` is built on Pyright, so a
"Pyright oracle" would grade lane B with its own engine.

**Scope:**

- **Phase 1 (this build):** Go (RTA), TypeScript (`tsc`). Unchanged from
  the first draft.
- **Phase 2 (designed here, built after O4):** Python runtime-trace oracle
  (§6); Rust MIR resolution oracle, optional Rupta reference lane, optional
  trace lane (§7).
- **Out of scope, still:** HCL / cross-layer edges (different grain; stays
  hand-verified); JS-without-types (`tsc` under `allowJs` collapses; grade
  TS zones only and say so).
- Hand-grading remains the method for what no oracle reaches — unexecuted
  Python/Rust paths, HCL — per the §11 protocol-upgrade note. Misses are
  kept by class, per cell, in `docs/oracle/oracle-misses.md`; the harness's
  and oracles' own defects in `docs/oracle/oracle-defects.md`.

## 3. Metrics and definitions

**Edge grain:** a graded edge is *(call-site position, callee declaration
identity)*. This matches Hobbes' own grain (site → declaration) and the
oracle's (Go `callgraph.Edge` carries `Site`; `tsc` resolves per call
expression; `sys.monitoring` CALL events carry the instruction offset).

Per cell, four buckets over Hobbes' emitted edges (resolution and
reachability oracles):

- **Confirmed** — the oracle has the same (site, target).
- **Contradicted** — the oracle resolved that site and Hobbes' target is
  not among its targets.
- **Oracle-silent** — the oracle could not speak about that site
  (unresolvable, un-analyzed under the build config, dynamic beyond its
  model). Charged to nobody, reported at full size.
- **(Recall side) Missed** — oracle (site, target) pairs Hobbes did not
  emit.

**Metrics:**

- `precision-against-oracle = confirmed / (confirmed + contradicted)` —
  the name matters; see the unsoundness rule below. **Quoted as a lower
  bound** (A-8, 2026-08-27): most contradictions triage to the oracle
  being wrong at its own grain, so the figure is bounded below by
  construction. Each cell record carries the triage ratio
  `oracle-wrong : hobbes-wrong : untriaged` over its contradicted rows
  as a quoted number.
- `recall = confirmed oracle pairs / all oracle pairs`.
- `recall-collapsed` (Max, 2026-09-10; ADR-089 amended) — printed on
  every resolution or reachability cell beside the line above: the same
  in-repo pairs at **(site line, target file, target name as the key
  spells it)** grain, hit by a confirmed edge at the target's exact
  position on its line. Two things fold and nothing else: a symbol's
  overload signatures (a `tsc` key lists one pair each, §5) and repeats
  of one callee on one line (the standing line counts one pair per
  site; one Hobbes edge hits them together) — so the number can sit
  below the standing one where such repeats carry the hits
  (spring-petclinic 98.3% beside 98.4%). It requires the key to spell one
  name per declaration: `tsc`'s checker-qualified name, go-rta's and
  rustc-mir's package-qualified one, javac's owner-qualified one since
  H-23. **The per-signature line is the standing grade everywhere** —
  the records' headline, the graphics' input, the claim page's number;
  the collapsed line explains the gap on a `tsc` key and is never quoted
  in its place. `shape/bucket.py` computes the same identity from the
  same rows and prints whether the two programs agree.

**Rules, each a constraint candidate (§11):**

1. **The pair is always reported together.** Precision or recall alone is
   trivially gamed and never quoted solo.
2. **Recall is never pooled or compared across cells.** It is driven by
   how many roots/entry points the oracle had (or what the tests covered),
   not tool quality. Every cell reports its root count — or its coverage —
   next to its recall.
3. **Oracle-silent is charged to nobody and its size is printed** — a cell
   where the oracle is silent on 40% of sites is a different kind of
   evidence than one where it speaks on 99%.
4. **A contradicted edge is very strong evidence, not proof.** RTA is
   unsound under reflection, `go:linkname`, plugins, cgo; `tsc` under
   `any`-typed and element-access calls. A genuinely dynamic edge can land
   in the contradicted bucket. Hence the metric's name.

**Grading by confidence tier.** Hobbes edges carry tiers (semantic /
syntactic / dynamic). Grade each tier separately in every cell. The
expectation to pre-register (§10): contradictions concentrate in the
syntactic-fallback tier — this run prices the C-7/C-8 fallback floor
instead of estimating it from lane disagreement.

### 3.1 Trace-oracle semantics (asymmetric)

A trace oracle replaces the buckets above:

- **Confirmed** — Hobbes' (site, target) was observed at runtime.
- **Missed** — an observed (site, target) is absent from Hobbes' graph. A
  definite recall failure: the program did it and we did not draw it.
- **Unobserved** — a Hobbes edge never exercised. Charged to nobody: the
  site may be uncovered, or covered but that branch/receiver never taken.
- **Suspect** — a Hobbes edge at a site that *did* execute, where every
  observed resolution went elsewhere. Triage queue, never
  auto-contradicted — a different input could still take Hobbes' target.

**Metrics:** `recall-against-executed = confirmed observed pairs / all
observed pairs` (exact, over a stated denominator); **confirmation rate**
over Hobbes edges (a coverage-limited signal, not precision). Constraint
candidate: *runtime-observed edges are facts; runtime absence is never
falsity.* Every trace cell reports its **coverage line** — fraction of
Hobbes sites the trace spoke about, plus suite line coverage — and the
union-of-runs count (nondeterministic suites: union over N runs, N
stated).

## 4. The Go oracle

**Build.** Per module: `packages.Load` (`NeedDeps | NeedTypes | NeedSyntax
| NeedTypesInfo`) → `ssautil.AllPackages` → build SSA →
`rta.Analyze(roots)`.

**Roots.** RTA needs entry points. Roots = `main` functions plus test
binaries (`_test` mains). A library module is analyzed through its test
binaries only — that is a different question than analyzing a binary, so
a cell states which it was. Report the root count in every cell (rule 2
depends on it).

**Monorepo handling.** One cell per Go module (dagger: 25). The replaced
`./sdk/go` is inside the loaded program, so the 7,322 semantic
core/integration → sdk/go edges from ADR-049 — the C-33 lift — get graded,
not just counted.

**Normalization (the real work):**

- **Synthetic functions.** SSA emits wrappers, thunks, and bound-method
  closures that exist in the call graph but not in source. Unwrap every
  synthetic node to its source declaration before matching
  (`ssa.Function.Origin()` / wrapper unwinding). An edge through a wrapper
  matches if the unwrapped endpoints match.
- **Generics.** Instantiations collapse to the source declaration
  (`Origin()`); multiple instances of one generic function are one
  declaration identity.
- **Closures / anonymous functions.** Matched by declaration position, not
  name — Hobbes and SSA name them differently.
- **`init` and package-level var initializers.** Decide once whether they
  are in or out of the graded set; either is fine, silently mixing is not.
- **Build tags.** One run under the default tag set per platform of the
  measurement box. Sites excluded by tags are oracle-silent. Report the
  tag set. (This is the known lane-disagreement bucket — 126 of dagger's
  138 — now graded instead of noted.)

**Positions.** `token.Position` from the loaded FileSet, normalized to
repo-relative paths. Column conventions differ between Hobbes lanes and Go
tokens — define the tolerance explicitly (same file + same line +
declaration-span overlap), and log every match that needed tolerance.

## 5. The TypeScript oracle

**Build.** Per TS zone: `ts.createProgram` from the zone's own tsconfig,
resolving against the provisioned `node_modules` trees already built for
ADR-050 (`~/.hobbes/cache/npm`). Zones declined at ingest for C-34 (no
lockfile) are declined here too, with the same reason string — the oracle
grades what the product indexed, under the same environment.

**Per call site** (`CallExpression`, `NewExpression`,
`TaggedTemplateExpression`, decorators): `checker.getResolvedSignature(node)`
→ `signature.getDeclaration()` → declaration position. No resolved
signature, or a signature with no declaration (synthetic union apply,
`any`) → oracle-silent.

**Overloads.** Hobbes' target is correct if it is *any* declaration of the
resolved symbol (overload set membership), not only the exact overload
`tsc` picked. Stricter is defensible; pick one, state it, keep it.
On the recall side the same rule lists every signature of the resolved
symbol as a pair at the site, so Hobbes' one edge confirms one and the
siblings count as misses (cheerio 1,972 of 3,249 misses; zod 4,442 of
12,038 — the callee-shape bucket, `oracle-misses.md`); §3's
`recall-collapsed` line prices that grain beside the standing number.

**Position convention.** Define the oracle's declaration position rule
explicitly (identifier start, 1-based line). This is the same ambiguity
behind the 131 decorator line-convention off-by-ones in lane disagreement
— the oracle lane is where that convention gets written down once and both
product lanes get measured against it.

**External targets.** Calls resolving into `node_modules` declarations:
graded if Hobbes emitted an edge for the site (its external-origin
classification vs `tsc`'s resolution is checkable), oracle-silent for
recall purposes if we scope recall to in-repo targets. Decide in D-O3.

## 6. The Python runtime-trace oracle (phase 2)

**Why traces and not a static oracle.** No sound static call-graph oracle
exists for Python — that part of the original claim held. But the
research-standard ground truth is exactly a runtime trace: the
Jarvis/PyCG ground truths were built from `python -m trace` call traces
(plus manual augmentation), DyPyBench compares static graphs against
DynaPyt dynamic graphs, and TraceEval (2026) builds an entire
execution-verified multi-language corpus on tracer validation. The
interpreter is an authority we do not control and cannot tune.

**Mechanism.** `sys.monitoring` (PEP 669, CPython 3.12+, low overhead):
register for `CALL` events, record (caller code object, instruction
offset, callee code object), map offsets to positions via
`co_positions()`, callee code objects to declaration positions via
`co_filename`/`co_qualname`/`co_firstlineno`. This yields **site grain**,
which `python -m trace` (function grain only) cannot. Run the target's own
test suite under the monitor.

**Filtering**, per the literature's protocol: drop interpreter-internal
frames (`_frozen_importlib`, site machinery), frames outside the repo, and
C-extension callees (no Python declaration to match — count them, report
them as a trace-silent class). Import-time module-body execution: decide
once whether module-level calls are in the graded set; state it.

**Semantics:** §3.1 applies — confirmed / missed / unobserved / suspect,
recall-against-executed, mandatory coverage line, union over N runs.

**Where it runs (ADR-092 phase 2):** inside the sandbox image — the
suite is repo-authored code. The tree is an overlay at its host path,
the interpreter is the cell's venv python with its install chain mounted
ro, no network. The export records `containment`; a box without the
image refuses the cell rather than running the suite on the host.

**What this buys against current evidence:** the SWE-bench workspaces'
Python capture (53–72%) has zero edge-accuracy evidence; a trace cell on
one of them converts suite-covered edges into exact recall and a confirmed
set, at the scale of a real repo, without six person-months of manual
augmentation (which is what full static ground truth cost the Jarvis
authors — we do not attempt it; we scope to the executed slice and say
so, per P11).

## 7. The Rust oracle (phase 2)

**Primary: MIR resolution oracle** — the compiler as authority on static
dispatch. After monomorphization, `rustc` has resolved every static and
generic call; `dyn Trait` and fn-pointer calls are explicitly marked
(virtual/indirect call terminators). A small rustc driver (nightly,
pinned) walks the resolved calls at MIR level — the approach prior art
like `rust-callgraph` takes — emitting (site position, callee
declaration) for resolved calls and marking dynamic sites oracle-silent.
Contradiction-capable on the static portion, exactly like `tsc` on typed
calls. Generic instantiations collapse to the origin declaration, matching
§4's Go rule.

**Rejected for this purpose:** LLVM-IR-level tools (`cargo-call-stack`):
post-optimization graphs lose source grain — inlining erases the exact
edges Hobbes draws — and the tool is embedded-focused, fat-LTO-bound, and
nightly-fragile. Wrong layer for a source-grain grader.

**Reference lane, optional:** Rupta (rustanlys/rupta; CC'24, CGO'25) — the
first context-sensitive pointer analysis for Rust, on MIR, built for call
graph construction, open source, independent of us. It covers what the MIR
oracle cannot (`dyn` dispatch via points-to), but it is a research
analyzer with its own trade-offs, not an authority. If run: its output is
labelled *reference*, disagreements feed triage, and no
precision-against-oracle number is ever computed against it. It is also
nightly-pinned; expect toolchain friction and time-box it.

**Trace lane, optional:** `uftrace` supports Rust (instrumented builds via
`-pg`/`-fpatchable-function-entry`, or dynamic prologue patching); run the
crate's tests, §3.1 semantics. Build config differs from release — fine,
because Hobbes measures source grain and an edge inlined away in release
still exists in source semantics; the cell states the build flags.

**Where it runs (ADR-092 phase 2):** inside the sandbox image — `cargo
check` runs the crate's build scripts and proc macros. The pinned
nightly's sysroot and the driver are mounted ro at their host paths;
`cargo fetch` reaches the registry from a separate container, the check
has no network. Regraded on `rust_proj` as a numeric no-op
(`oracle/cells/rust_proj-2026-08-28.md`).

**Pilot cell:** `rust_proj` — 33 edges, currently 100% hand-checked
(ADR-040), all-semantic. The MIR oracle must confirm all 33; any
divergence is a harness finding first. Then dagger's rust (8,595 sites) as
the scale cell.

## 7b. The Java oracle (O8, ADR-096)

**Primary: javac resolution oracle, with CHA for the virtual sites.**
The compiler's own front end is the authority on what a call site
*names*: a javac `Plugin` (`bench/oracle/java`, no dependency beyond
the JDK) rides the repo's own build — injected through a wrapping
`javac` under Maven (`-Dmaven.compiler.executable`, the scip-java
trick) or an init script under Gradle — and after every compilation
unit's ANALYZE records what `Trees.getElement` resolved each method
invocation and `new` to. Grain is `tsc`'s: (site = the callee
identifier's line, target = the resolved declaration's name line).
Because Maven compiles main and test in separate javac runs and a
test's call into main resolves against a class file with no name line,
shards carry declarations *keyed* — `owner#name(erased, annotation-free
parameter types)` — and the Go merge (`internal/javac`) joins keys
across every shard of the build; a key no shard declares is external.
A target's *name* is the key's owner-qualified spelling
(`org.jsoup.nodes.Element.attr`, a nested class with its `$`, a
constructor `<init>`) — one name per declaration, since 2026-09-10
(H-23: the member-bare spelling folded same-named overrides of one
file under §3's collapsed identity). `oracle java-javac --merge-only
--carry <key>` re-merges a key from the shards a cell directory keeps,
without the build, for a spelling change like that one.

**Dispatch.** A virtual or interface call (mode `dynamic`) carries the
declared method as the site's `interface` — so Hobbes' edge to it
buckets *abstract*, never contradicted — and its targets are the
declared method plus the **CHA override set**: every declaration with
the same key suffix whose owner is a subtype of the declared owner, in
the hierarchy the shards record. Recall against that set is the size of
Java's dispatch hole (C-58's majority case) per cell; RTA was not built
(instantiation analysis over bytecode — SootUp/WALA — is the recorded
next step if the CHA number is not sharp enough). Static (constructor,
`static`, `private`, `final`, `super.m()`, a `final`/record owner) sites
have one target.

**Conventions.** `new T(..)` resolves to T's constructor — an *implicit*
one sits at the class line (javac synthesises it there), which is where
Hobbes' `calls` to the type lands. `new T() {..}` targets T's
constructor by erased arity (the anonymous class's synthetic one calls
it); Hobbes draws `uses` there by decision (ADR-096), so the pair is a
recorded miss class, not a contradiction. Sources under `target/` or
`build/` (annotation-processor output) are dropped and counted
(`excluded.generated`). Method references are not sites. Lambdas
attribute to the enclosing declaration.

**Where it runs (ADR-092 / C-66):** inside the sandbox image, with a
network — the build is the dependency resolution. The ingest lane split
this into a source-less networked resolve pass and an offline index pass
(ADR-097); the oracle keeps the single networked pass for now (bench
tooling), and the same two-pass shape applies when it is wanted. The plugin jar is built in the image once per cell
dir (`java-build`, no network).

**Pilot cell:** the `minijava` fixture — every pair hand-computed in
`internal/grade/java_test.go` (the overload, the constructor chain, the
implicit constructor, the interface call and its CHA override, the
anonymous member). Then jsoup (Maven library) and spring-petclinic
(Spring service), and two repos drawn at random (§9).

## 7c. The C oracle (O9, ADR-110)

**Primary: clang's front end, one translation unit at a time.**
`oracle c-clang` derives the build root's compile database the way the
ingest does (a carried database that rebases, CMake's export, bear over
`make -k`; ADR-109) and runs `clang -fsyntax-only -Xclang
-ast-dump=json` on every entry, contained and offline, in one container
(the derivation runs the repo's build logic).
- **Sites:** every `CallExpr` whose callee token is in the repo. A direct
  call (a `DeclRefExpr` to a `FunctionDecl`, under parentheses, casts
  and unary `*`/`&`) is `static`; any other callee is `dynamic`, with no
  targets.
- **Targets are definitions.** A `static` function resolves to its own
  unit's definition, an external one to the definition joined across
  units by name (javac's keyed merge).
  - Several definitions, and none in the caller's unit: `link-ambiguous`,
    no targets.
  - None, declared outside the repo or only implicitly (a builtin):
    external.
  - None, declared in the repo: `undefined`, no targets.
- **Macros.** A callee written in a macro argument sits where it was
  written. One written in a macro's body sits at the invocation line,
  mode `macro`: the Rust convention's C face. Hobbes draws a macro
  invocation to the `macro` symbol, which the export excludes before
  grading, so every call a macro's expansion makes is a `macro→…` pair
  Hobbes cannot confirm (C-131).
- **The reader.** The dump omits a location's `file` and `line` when they
  repeat the previous location's, so it is read as a stream in document
  order, never guessed. An object whose first key is `offset` is a
  location; `includedFrom` is not.
- **Independence.** Lane B's scip-clang is clang-based, so the key shares
  a front end with the lane it grades, as `tsc` and javac do. What it
  grades is Hobbes' own work above the front end: ADR-109's decode rules,
  the join and lane A's fallback.

**Pilot cells:** the `cclang` fixture (every pair hand-computed, its
dumps committed), then `minic`, then cJSON and one repo drawn at random
(§10.5).

## 7d. The C++ oracle (O10, ADR-113)

**Primary: clang's front end again, per translation unit, over the
same derived compile database.** `oracle c-clang --lang cpp` runs the
C oracle's contained step with each unit's front end chosen by its own
extension (`clang++` for `.cpp .cc .cxx .C .c++`, `clang` otherwise,
whatever `--lang` says: a mixed root is one root), and `export.Exts["cpp"]`
is the six C++ extensions plus `.h`. The C rules (§7c) carry over; C++
adds four site kinds and one merge key:
- **Sites.** `CallExpr` as C (its `DeclRefExpr` may name a
  `CXXMethodDecl`: a static or qualified member call, mode `static`).
  `CXXMemberCallExpr`: the callee is the `MemberExpr`'s
  `referencedMemberDecl`, resolved through a per-unit id table after
  the walk; mode `static`, or `virtual` where the declaration was
  *written* `virtual` — clang's dump prints the keyword only where the
  source does and carries no override information, so an override
  without the keyword reads `static`; the target is the declared
  method either way, and no class-hierarchy analysis is built (an
  override Hobbes drew instead is a contradiction to be measured, not
  excused). `CXXOperatorCallExpr`: mode `operator`, the operator
  function it names; a dependent operator in a template pattern
  (`UnresolvedLookupExpr`) is `dynamic`. `CXXConstructExpr` and
  `CXXTemporaryObjectExpr`: no callee; mode `constructor`; the target
  is the constructor of the expression's class (its type's last `::`
  component) whose signature equals the `ctorType`; an `isImplicit`
  constructor or destructor is never a target, and a construct site
  whose unit declares no constructor of that signature is dropped. A
  `CXXNewExpr` contains the construct site and is not one itself.
- **Declarations** carry `mangledName`, `kind` (function, method,
  constructor, destructor), the enclosing class, the signature type,
  `virtual`. A `FunctionTemplateDecl` is not a declaration; the pattern
  and each specialisation inside it are, at the template's line. A
  member function's `storageClass: "static"` is *not* internal linkage;
  an unnamed namespace's declarations are.
- **Merge across units by mangled name** where there is one — one
  entity per mangled name, overloads and a template's specialisations
  told apart, a header's inline method one target from every unit —
  and by C's name rules otherwise (`extern "C"`, `main`).
- **Coverage** adds `sites_virtual`, `sites_operator`,
  `sites_constructor` and `units_cpp` (units that ran under clang++)
  beside §7c's buckets; `lang_cpp: 1` marks a cell run as `--lang cpp`.
- **What Hobbes cannot draw there** (C-146): an operator applied by
  symbol and a named cast are not sites at lane A, so `operator` sites
  read as recall, never precision.
- **Fixture:** `bench/oracle/testdata/cppclang`, hand-keyed in
  `cpp_test.go` — 25 sites over 4 units: 15 static, 4 constructor, 2
  virtual, 2 dynamic, 1 operator, 1 macro, 0 tu-split; the overload
  pair on two lines, `p->area()` on the base's declaration, the implicit
  copy and default constructors never targets.

**Amended 2026-09-16 (H-28–H-31, ADR-113 §3's amendment).** fmt's
triage charged 18 false contradictions to the oracle. Three of the four
are rules and are corrected; the fourth stays open.

- **A member call's site is the `MemberExpr`'s `range.end`** — the
  member's own name token — and not its `range.begin`, which is the
  start of the object expression. A call whose object spans lines
  otherwise keys on a line the member is not on, so Hobbes' edge at
  the member's line reads as both a false contradiction and a false
  miss (H-28, RC-3).
- **A declaration with no mangled name is keyed `Class::Name`** where
  it has a class — a class template's pattern members — and by the bare
  name otherwise (`extern "C"`, `main`). Keyed by the bare name, two
  classes' same-named members merge into one declaration (H-29, RC-8).
- **A line the key left unresolved cannot contradict** (H-30, RC-4).
  Where any oracle site on a Hobbes edge's file and line **carries no
  targets** — a dependent call in a template pattern the key holds as
  `dynamic` — a non-confirmed edge on that line is **silent**
  (`line-unresolved`), never contradicted. The key's silence is its own
  state, not a verdict against Hobbes. This is the precision-side
  analogue of the trace oracle's `line-mixed`.

  **Its price is printed beside every grade** (ADR-124, 2026-09-17): the
  rule silences a wrong edge as readily as a right one, so the report
  adds `precision-strict` — confirmed / (confirmed + contradicted +
  `line-unresolved`) — on its own line under the standing precision
  whenever a row was silenced this way, for every tool alike. The
  renderer computes the same number from each record's silent map, and
  every quoted precision carries it where the two differ.

  **What this rule does not reach**, stated so it is not mistaken for
  more than it is: a call the key holds **nowhere at all**. There the
  line's sites are present and resolved, nothing on it carries an empty
  target list, and the rule does not fire — the edge still reads
  contradicted. That is H-31, and it is why §10.8's P36 expects its
  seven rows to survive the regrade.
- **Closed 2026-09-16** (it read *open* here until it was traced): H-31's `os.cc` half, a call in a macro argument nested in
  another's, which a probe of that shape did not reproduce. Its
  `decltype` half does reproduce — a call in an unevaluated operand
  yields no site — and is fixed only if the trace names a clean rule.

**The random draw, stated before it was made (2026-09-14).** The pool:
GitHub's `language:c++ stars:300..3000 pushed:>2026-03-01`, every
result (1,000), sorted by full name, shuffled with
`random.Random(20260914)`; the first taken that is not a fork or
archived, has a `CMakeLists.txt` or Makefile at its root, and derives
a compile database offline in the image. **Taken: Taywee/args at
`903b07df`**, the seventh; passed over, with reasons recorded in the
draw file: godot-orchestrator (a submodule a plain clone lacks),
scummvm (a Makefile that needs `./configure`), deepstream_reference_apps
(no build file at the root), libcuckoo (CMake exports 0 entries: tests
off by default, C-135's shape), Ros_Qt5_Gui_App (FetchContent from
github.com), TinyGSM (an ESP-IDF component). The chosen cell is
fmtlib/fmt at `3a0661d7` (52 entries offline, 44 under `test/`). Both
cells wait on ADR-113's unit 2.

## 8. The matcher

**Inputs:** (a) a Hobbes graph export per cell — every call edge with site
position, target declaration position, confidence tier; add an export
subcommand if the current dump lacks any field. (b) The oracle edge set,
same shape, tagged with its oracle kind (resolution / reachability /
trace) so the bucket semantics switch correctly.

**Pipeline:** normalize paths → normalize positions → build declaration
identities (file, span) with the tolerance rules of §4–§7 → set-match at
(site, target) grain → bucket per oracle kind → report.

**Report per cell:** confirmed / contradicted-or-suspect / silent counts
and rates, per tier; root count (Go) or coverage line (trace cells);
recall with miss decomposition — at minimum the buckets the field says
dominate: dynamic/interface dispatch, and dispatch-with-closure. Also emit
the raw contradicted/suspect rows (site, Hobbes target, oracle targets) —
those are the triage queue, and published rows are the difference between
a number and evidence.

**Triage protocol** for contradictions and suspects: read the site from
source. Verdicts: **hobbes-wrong** (a real extraction defect → issue
filed), **oracle-unsound** (reflection/linkname/`any` — logged, not
charged), **not-exercised** (trace suspect whose target is plausible on an
untaken path — logged, charged to nobody), **match-defect** (normalization
bug → fix matcher, rerun cell). A cell's number is only final after its
triage is complete or a sampled triage is documented as sampled.

**Languages** (per the split-by-focus rule, D1): the Go oracle extractor
must be Go (`x/tools` is Go-only); the TS oracle extractor must be
TypeScript (compiler API); the Python tracer must be Python
(`sys.monitoring`); the Rust MIR driver must be Rust (rustc APIs). The
matcher/reporter is shared and language-neutral — Go or Python, whichever
the export tooling already leans toward; keep it one binary/script with
cells as data, not per-cell scripts.

## 9. Cells and order

| Milestone | Cell | Why / exit |
|---|---|---|
| **O1** | `minigo` + `twomod` fixtures | Truth is hand-computable. Harness self-test: matcher must land exactly (every fixture edge confirmed, zero tolerance surprises) before any real cell. Exit: fixture grading in the test suite. (`twomod` — a two-module Go fixture — does not exist yet; O1 adds it.) |
| **O2** | hobbes repo, Go zone | First real cell. Small (3,707 sites), familiar. *(Done 2026-08-25. The ADR-037 20/20 could not serve as a cross-check — its edges were never named — and was retired in favour of the oracle.)* Triage protocol shakedown. |
| **O3** | kbet TS zones | The provisioned-deps happy path. *(Done 2026-08-25: 630/630 against the zone's own `tsc`; the V2.M3 20/20 retired alongside Go's.)* |
| **O4** | dagger Go modules | The payoff: 237k sites graded, per-module cells, C-33's join graded, the 126 build-tag disagreements priced. |
| **O5** (optional) | dagger `sdk/typescript` | The 70.3% zone under the provisioned cache. |
| **O6** (phase 2) | Python trace cells: hobbes' own Python zone under its suite (dogfood), then one SWE-bench workspace with strong coverage and clean ingest (xarray) | First trace-oracle cells; minipy-style fixture self-test first if one exists, else add one. Exit: coverage line + recall-against-executed on the record. |
| **O7** (phase 2) | Rust: `rust_proj` MIR oracle (must confirm ADR-040's 33/33), then dagger rust | Compiler-authority grading for the language with the thinnest evidence base. Rupta/trace lanes only if time-boxed setup succeeds. |
| **O9** | C: the `cclang` fixture and `minic`, then DaveGamble/cJSON and one repo drawn at random (ADR-110) | clang's front end as the resolution oracle; C's first §3.8 row, per cell. Exit: §10.5 graded |
| **O10** | C++: the `cppclang` fixture and `minicpp`, then fmtlib/fmt and one repo drawn at random (Taywee/args; ADR-113) | the C oracle's C++ face (§7d): member, operator, constructor and virtual sites, declarations keyed by mangled name; C++'s first §3.8 row, per cell. Built 2026-09-14 (`a848`); the cells wait on lane B |

Each cell's runtime and machine cost gets logged — the harness is only
useful if rerunning a cell is cheap enough to do after every resolver
change.

## 10. Pre-registration

Before O2 spends anything, commit (own commit, before the run)
predictions:

- A precision-against-oracle band per language (state one; the honest
  prior from the hand-checks is "somewhere above ~85%").
- Where misses concentrate (predict: interface dispatch dominates the
  recall gap).
- Which tier carries the contradictions (predict: syntactic fallback).
- For O4: whether the 126 build-tag lane disagreements grade as
  oracle-silent or contradicted.
- Before O6: a recall-against-executed band for Python, and a predicted
  suspect rate.

Grade the predictions in the evidence file, including the ones that miss.
This is also the dry run for the habit the harness benchmark will need.

**The predictions as committed** follow, folded in from
`docs/oracle-preregistration.md` on 2026-09-09 with the text unchanged,
its own header first. Phase 1 (P1–P9) was committed before O2, phase 2
(P10–P16) before O6/O7; no pre-registration was written for the
seven-repo loop of 2026-08-27, and the evidence log says so.

**Committed 2026-08-25, before O2 ran.** Each prediction is graded in
`extraction-evidence.md` when its cell lands, including the ones that
miss. This is the dry run for the habit the harness benchmark needs:
numbers written down before the run, so results cannot re-scope them.

### 10.1 Priors

Every hand-check to date is 100% at n=20–33 (95% lower bound ~83–89%).
Lane agreement on this repo is 0 disagreements at 3,085 sites; on dagger
258 of 36,703, 126 of them build-tag and 131 line-convention. The O1
fixtures showed the semantic lane draws **no edge at all** for an
interface-method call.

### 10.2 Predictions

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P1 | O2 (this repo, `go/`) | precision-against-oracle for **semantic** edges ≥ 95% | met if the semantic-tier number, after triage removes match-defects only, is ≥ 95% |
| P2 | O2 | contradictions concentrate in the **syntactic** tier: syntactic precision < semantic precision, and ≥ half of all contradicted rows are syntactic (this repo's graph carries only 3 syntactic edges, so this may be undecidable — recorded as such if so) | met if both hold; undecidable if syntactic edges < 10 |
| P3 | O2 | recall gap is dominated by **dynamic dispatch**: `dynamic` + `dynamic-closure` ≥ 60% of misses | met if the miss decomposition says so |
| P4 | O2 | in-repo recall between **60% and 85%** at the cell's root count (binaries + test mains) | met if in band |
| P5 | O2 | oracle-silent ≤ 15% of Hobbes edges, `unreachable` the largest silent reason (test-only helpers and unused exported functions) | met if both hold |
| P6 | O2 | the ADR-037 hand-check cannot be reproduced by identity (its 20 edges were never listed); the whole semantic set stands in for it | recorded as a finding regardless |
| P7 | O3 (kbet TS) | precision-against-oracle ≥ 95% semantic; overload-set membership needed for ≥ 1 confirmed edge | graded at O3 |
| P8 | O4 (dagger Go) | the 126 build-tag lane disagreements grade **oracle-silent (`not-loaded`)**, not contradicted | graded at O4 |
| P9 | O4 | precision-against-oracle for the 7,322 core/integration → `sdk/go` edges (C-33's lift) ≥ 95% | graded at O4 |

### 10.3 What would falsify the lane's usefulness

If O2 produces a contradiction rate above ~10% that triage attributes
mostly to **match-defect**, the conventions (D-O4) are wrong and the
lane is measuring its own normalisation; fix before any real number is
quoted. If triage attributes them mostly to **oracle-unsound**, RTA is
the wrong oracle for this code shape and VTA (D-O1's optional arm)
runs next.

### 10.4 Phase 2 — committed 2026-08-25, before O6 / O7 ran

Priors: Python has **no edge-accuracy evidence at all** beyond lane
agreement (1,789 sites / 0 disagreements on this repo) and the M5
narrative sample; the SWE-bench workspaces' 53–72% capture is a
detection number, not an accuracy one. Rust has ADR-040's 33/33
hand-check on `rust_proj` (95% lower bound ~89%). The phase-1 lesson
(H-3, H-5, H-6, H-7): the first pass of a new oracle is usually the
oracle being right at a different grain, so every phase-2 prediction is
graded **after** match-defect triage, never on the first pass.

O6's first cell is this repo's Python zone (`pipeline/`, under its own
pytest suite, `HOBBES_SCIP=0` as the suite runs by default); xarray was
in the design but **no SWE-bench workspace exists on this box any
more**, so that cell is recorded *not run* rather than predicted.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P10 | O6 (this repo, `pipeline/`) | **recall-against-executed** over in-repo observed pairs to *named* declarations (functions, methods, classes) ≥ 90%; over *all* observed in-repo pairs (nested functions, lambdas included) between **70% and 92%** | met if both hold after match-defect triage |
| P11 | O6 | the **suspect rate** (suspect / (confirmed + suspect)) ≤ 2%, and triage attributes the suspects mostly to *not-exercised* or *match-defect* (decorators, `functools.wraps` wrappers, `__call__`), not *hobbes-wrong* | met if the rate holds and ≥ half the triaged suspects are not hobbes-wrong |
| P12 | O6 | the suite exercises ≥ 60% of Hobbes' call sites under `pipeline/src`; the unobserved bucket is dominated by `line-not-called` (never executed), not `line-mixed` (executed, but only C or out-of-repo callees seen there) | met if both hold |
| P13 | O6 | misses concentrate in **closures**: pairs whose target is a nested function or lambda (`observed→closure`) ≥ 50% of all in-repo misses; the runner-up is calls dispatched through a callable object or bound value Hobbes cannot name statically | met if the miss decomposition says so |
| P14 | O6 | at least one **harness defect** in the oracle-right-at-a-different-grain class (decorator line vs identifier line, wrapper vs wrapped) is found by the miniapp fixture or the first triage, before any number is quoted | recorded as a finding regardless |
| P15 | O7 (`rust_proj`) | the MIR resolution oracle **confirms all 33** of ADR-040's hand-checked edges; any divergence is a harness finding first (design §7) | met if 33/33 after match-defect triage |
| P16 | O7 (`rust_proj`, then dagger's Rust if the driver holds) | precision-against-oracle ≥ 95% on the semantic tier; misses concentrate in **trait dispatch** (`dyn` and generic-bound calls, oracle-silent or dynamic) and closures, ≥ 60% of misses | graded per cell reached; dagger rust is recorded *not reached* if the driver does not get there |

**What would falsify phase 2's usefulness.** If O6's coverage line is
below ~30% of Hobbes' sites, the executed slice is too thin for any
recall claim and the cell is recorded as a coverage measurement only.
If O7's driver cannot be pinned to a nightly that builds `rustc_private`
on this box inside the time box, the Rust lane is recorded *not built*
with the toolchain reason, and ADR-040's hand-check stays the only Rust
evidence — said so, in the row.

### 10.5 C — committed 2026-09-12, before O9 ran

**Priors.** C has no graded edge.
- Thirteen lane-A and lane-B edges were hand-checked at review
  (ADR-108/109), all right.
- Lane agreement on cJSON is 1,717 sites and 0 disagreements. That is
  two of Hobbes' own methods, one of them the name fallback.
- cJSON's ingest at 0.2.4-beta draws 1,713 gradeable call-evidence lines
  to functions (1,188 semantic, 525 syntactic), and 1,821 to macros,
  which the export excludes.

The phase-1/2 lesson stands: the first pass of a new oracle is usually
the oracle at another grain, so every prediction is graded after
match-defect triage.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P17 | O9 (`cclang`, `minic`) | the oracle lands the fixture's hand-computed truth exactly: 17 in-repo pairs, 1 external, 3 dynamic sites, one site each `link-ambiguous`, `undefined` and `tu-split`, and `orphan.c` not loaded. On `minic`, 0 contradicted, with `tests/test_util.c` silent as not-loaded (make's default target does not build it) | met if the fixture test passes as written and minic's report says both |
| P18 | O9 (cJSON) | precision-against-oracle on the **semantic** tier is **100%**, 0 hobbes-wrong | met after match-defect triage |
| P19 | O9 (cJSON) | syntactic precision ≥ 95%, and any contradiction is syntactic (the rank-3 name rule, C-130) | met if both hold; undecidable if fewer than 10 syntactic edges are judged |
| P20 | O9 (cJSON) | the recall gap is dominated by macro expansions: `macro→*` pairs are ≥ 50% of in-repo misses (Unity's `TEST_ASSERT_*` expand to `UnityAssert*` calls) | met if the miss decomposition says so |
| P21 | O9 (cJSON) | recall over `static→*` pairs ≥ 90% | met if in band |
| P22 | O9 (cJSON) | the silent bucket is dominated by `not-loaded`: files cJSON's CMake build does not compile (Unity's own tests and examples, `fuzzing/`) | met if `not-loaded` is the largest silent reason |
| P23 | O9 (random draw) | semantic precision ≥ 99% with 0 hobbes-wrong after triage; recall over `static→*` pairs ≥ 80% | graded at the draw |
| P24 | O9 (every cell) | poison check PASS, 0 falsely confirmed | met per cell |
| P25 | O9 | at least one harness defect in the oracle-at-another-grain class is found by the fixture, `minic` or the first triage before any number is quoted (P14's habit) | recorded as a finding regardless |

**The random draw, stated before it is made.**
- The pool: GitHub's `language:c stars:300..3000 pushed:>2026-03-01`,
  every result the search API returns (at most 1,000), sorted by full
  name, shuffled with `random.Random(20260912)`.
- The first repo taken that is not a fork or archived, has a
  `CMakeLists.txt` or a Makefile at its root, and whose ingest and oracle
  both derive a compile database offline in the image.
- Every repo passed over is recorded with its reason. One that cannot
  finish on this box is recorded, and the next is taken.

**What would falsify O9's usefulness.** A contradiction rate above ~5%
that triage attributes mostly to match-defect means the conventions
(the macro rule, the definition join) are wrong; they are fixed before
any number is quoted. A draw whose compile database cannot be derived
is C-135 measured, not a cell.

### 10.6 C++ — written 2026-09-15, before args ran (fmt already graded)

**Stated first: fmt was graded before this section existed.** ADR-113
named the two cells, and no prediction was committed for either. The
fmt cell ran on 2026-09-15 at 0.2.21-beta before that gap was seen, so
its numbers stand in its record as measured, never as predictions met or
missed. This section was written after reading fmt's first grade and
before Taywee/args ran, and its args predictions carry what fmt showed.

**Priors.**
- `cppclang` lands its 25 hand-keyed sites (`cpp_test.go`, `a848`).
  `minicpp`'s lane B matched scip-clang at 8 of 8 compared sites
  (ADR-113 §2).
- fmt's first grade, before triage: precision-against-oracle 96.1%
  (3,439/3,577), the semantic tier 3,331/3,395 and the syntactic
  108/182; recall 15.5%.
- The first read of fmt's 138 contradictions names three Hobbes
  mechanisms:
  - C's one-target-per-site rule keeping the smallest line where a
    site's references name several overloads of one file (40 semantic
    rows);
  - C's own-file rule meeting class-template specialisations that share
    a moniker across files (4);
  - lane A's name fallback reaching a namespace member (`test::close`)
    at a site where lane B's index carries no occurrence, so the
    external veto has nothing to fire on.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P26 | O10 (`cppclang`) | the fixture lands its hand-keyed truth exactly | met if `cpp_test.go` passes as written. It did at `a848`, before this section: recorded, not predicted |
| P27 | O10 (args, the draw) | semantic precision ≥ 98% and below 100%: `args.hxx` is one template-heavy header, so the smallest-line collapse over overloads appears there too, and ≥ 50% of the semantic contradictions are a later overload of the same name in the same file | graded after triage |
| P28 | O10 (args) | every syntactic contradiction sits at a site where lane B carries no occurrence of that name | met if the join's inputs say so row by row |
| P29 | O10 (args) | recall is dominated by `static→method` and `static→constructor` misses (C-145, C-146, the implicit-construction guard): together ≥ 60% of misses | met if the miss decomposition says so |
| P30 | O10 (every C++ cell) | poison check PASS, 0 falsely confirmed | met per cell |
| P31 | O10 | at least one defect of the oracle-at-another-grain class is found in args' first triage before its numbers are quoted (P14's habit) | recorded regardless |

**What the row rests on.** A mechanism the triage charges to Hobbes on
the semantic tier is registered in the same commit as its cell. Whether
it is fixed before the §3.8 row lands, or the row states it, is the
lead's call.

### 10.7 Foreign C++ cells — written 2026-09-15, before either tool ran on C++

The foreign C cells (2026-09-14) were graded with no section here.
These four are written first. Both tools run as the C cells ran them:
- CodeGraphContext 0.6.13 on its default tree-sitter path. Its
  optional SCIP path for C/C++ is not enabled, as on C.
- repowise 0.49.0 with `--no-prose`.

Both go through converter@3, on fmt and args at the standing cells'
commits, and are graded by those cells' stored clang keys with
`grade-foreign.sh --lang cpp`.

**Priors.**
- Both tools resolve a call by name and scope, not by type
  (`field.md` §1). On C, where a name has one definition per link,
  CodeGraphContext read 1,179/1,179 on cJSON and repowise 1,073/1,075.
- C++ gives one name many declarations: overloads, same-named members
  of other classes, a template's specialisations. Hobbes' own first
  grade of fmt had 36 overload-collapse rows and 74 name-fallback rows
  before ADR-113 §2's third amendment.
- Hobbes' standing grades: fmt 3,254/3,282 (99.1%), recall 14.5%; args
  1,995/1,995, recall 56.4%. fmt's recall is low by construction. Hobbes
  abstains where lane B lists several candidates (C-151), draws nothing
  by name in a file lane B compiled (C-152), and loses definitions to
  parse errors (C-145). A name resolver guesses at those sites.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P32 | all four | poison check PASS, 0 falsely confirmed | met per cell |
| P33 | all four | each tool's precision-against-oracle is below Hobbes' standing grade on the same key | met per cell |
| P34 | all four | at least half the contradictions read have the name-match-wrong-owner shape: the tool's callee shares its short name with one of the oracle's targets at the site | graded on the rows read: every row where a cell has ≤ 60, otherwise a seeded random sample of 20, the ratio quoted as sampled (A-8) |
| P35 | fmt | at least one tool's recall is above Hobbes' 14.5% | met if the report's recall line says so. If met, fmt is the first row where a tool's marker is ahead of Hobbes' on either axis, and the claim page says so |

args' recall is recorded, not predicted. If P33 fails on a cell, the
claim page's list of ties gains it.

**Graded 2026-09-15**, on the records at converter@4. The first grade,
at @3, is kept beside each cell. The triage that moved it is ADR-101's
2026-09-15 amendment.
- P32 **met** on the three cells with graded edges. Undecidable on
  CodeGraphContext's args cell, which graded nothing: its parser reads
  no `.hxx` or `.cxx` file.
- P33 **met** on the three: CodeGraphContext fmt 86.6%, repowise fmt
  45.2% and repowise args 87.0%, against Hobbes' 99.1% and 100%.
  Undecidable on CodeGraphContext's args.
- P34 **met** on the three, on the rows read: 17, 14 and 19 of 20 have
  the name-match-wrong-owner shape. The rest are the key's open defects
  (H-29 and H-30: 3 rows on CodeGraphContext's fmt, 1 on repowise's
  args) and 6 constructions repowise drew to a type or a `using` alias
  on fmt.
- P35 **missed**: on fmt, CodeGraphContext's recall is 11.8% and
  repowise's 13.9%, both below Hobbes' 14.5%. On neither C++ row is a
  tool's marker ahead of Hobbes' on either axis.
- args' recall, recorded: repowise 23.3% and CodeGraphContext 0.0%,
  against Hobbes' 56.4%.

### 10.8 The regrade after O10's defect fixes — written 2026-09-16, before the fix

H-28, H-29 and H-30 are fixed under ADR-113 §3's 2026-09-16 amendment
and §7d's. This section is written before any of them lands, because a
fix to the *oracle* moves the key every standing grade was measured
against, and a regrade with no stated direction is the shape a
flattering patch takes (§11).

**What moves what.**
- **H-28 and H-29 change the key** (a shard's positions and its join
  spelling), so **fmt and args are re-run**, not re-merged: the reader
  streams clang's dump and keeps no raw copy, so `--merge-only` cannot
  serve as it did for Java's H-23.
- **H-30 changes the matcher**, which is language-neutral: it can move
  a row on *any* stored cell where a Hobbes edge sits on a line the key
  left unresolved. **Every stored cell is therefore re-graded from its
  saved key** — no oracle re-run, `oracle grade --poison` against the
  stored `oracle.json`.

**Priors.** fmt stands at 3,254/3,282 (99.1%), its 28 contradictions
triaged 10 provider (C-153) : 18 oracle (H-28 1, H-29 5, H-30 5,
H-31 7). args stands at 1,995/1,995 (100%), recall 56.4%.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P36 | O10 (fmt) | contradicted 28 → 17, and the 17 are C-153's 10 plus H-31's 7, row for row against the stored `contradicted.tsv` | met if the row sets match exactly; any other row moving is a finding to triage before the number is quoted |
| P37 | O10 (fmt) | confirmed rises by exactly 6 — H-28's 1 and H-29's 5, which were Hobbes' edges at the right declaration all along — and **no** previously confirmed edge is lost | met on the before/after sets; a lost confirmation is a regression, not a result |
| P38 | O10 (fmt) | precision-against-oracle 99.1% → 99.4–99.6% | met if the reported figure lands in the range; stated signed either way |
| P39 | O10 (args) | precision stays 100% and no contradiction appears: a position fix can only move a site to where Hobbes already holds it | met per the report |
| P40 | O10 (both) | recall falls on neither cell | met per the report; fmt's may rise slightly as 6 pairs re-key |
| P41 | O10 (`cppclang`) | the 25 hand-keyed sites stand unchanged — every member call in the fixture is written on one line — and the unit **adds** a multi-line member chain and a two-template collision, each hand-keyed | met if `cpp_test.go` passes with the existing 25 untouched; if any of the 25 moves, it is a multi-line chain and its new line is stated per site |
| P42 | every non-C++ stored cell | the matcher change moves only rows contradicted at a line the key left unresolved; precision falls on no cell | met per regrade; every cell that moves is listed before → after, signed |
| P43 | all cells | poison check PASS, 0 falsely confirmed | met per cell |
| P44 | the 52 foreign cells (ADR-101) | the same matcher grades them, so H-30 can move a foreign row too: precision moves only where a row sat on a line its key left unresolved, and no foreign row moves for any other reason | met per cell; every cell that moves is listed before → after, signed, as a Hobbes cell is |
| P45 | the four foreign **C++** cells | regraded against the **new** key, not the old one, and their direction stated signed | met if each record names the regenerated key; the comparative page may not compare a tool against a key Hobbes has stopped using |

**Scope, stated once.** Three tiers, and every one of them holds the
Hobbes side fixed so that only the key or the matcher moves:
- **fmt and args** — `oracle c-clang` re-run (contained, as the cells
  ran: ~330 s each), graded against each cell's standing
  `*-regrade/hobbes.json`, never `*-cell/`'s superseded first grade;
- **38 of the 44 own cells** — stored `hobbes.json` × stored key, no
  ingest and no oracle re-run. The other 6 rows are keys with no Hobbes
  export beside them and are named as not covered;
- **52 foreign cells** — `grade-foreign.sh` over each stored
  `edges.json` and the key its record names; the four C++ ones against
  the new key (P45).

The comparative graphics are read from the cell records, so any row
that moves is re-rendered and ADR-102's drift test
(`TestGraphicsMatchTheCellRecords`) is green before the commit.

**H-31 is not predicted.** Its `decltype` half reproduces and its
`os.cc` half does not; it stays open in the log unless its trace names
a rule, and its 7 rows are expected to survive the regrade (P36).

**Traced 2026-09-16, after the regrade, and it was two defects on
opposite sides.** The first probe missed because the synthetic never
spliced a *qualifier*; fmt's `#define FMT_SYSTEM(call) ::call` does, and
clang then spells the callee's `range.begin` in the macro body while its
`range.end` is the author's name token. So the six `os.cc` calls are
keyed at `include/fmt/os.h:57` and `:62` — confirmed on the key itself —
and are the oracle's, with the rule in ADR-113 §3's amendment (root
RC-2). **The seventh was never the oracle's:** `compile-test.cc:127` is
`decltype(fmt::arg(…))`, an unevaluated operand the compiler never
calls, so clang is right to emit no site and Hobbes is wrong to draw the
edge — registered **C-155**, and fmt's triage ratio corrected from
`hobbes-wrong 4 : oracle-wrong 7` to **5 : 6**. P36's count stands; its
attribution of all seven to the oracle does not.

### 10.9 The C++ cells re-run after H-31's fix — written 2026-09-16, before the regrade

H-31's oracle half landed as `db20845` (ADR-113 §3's "as built" rule: a
callee whose qualifier a macro body supplied is keyed at the author's own
name token). That **changes the key again**, so the same discipline as
§10.8 applies and the predictions go down first.

**Scope.** fmt and args re-run contained, graded against their standing
exports; **and the four foreign C++ cells re-graded against the new
key**, because §10.8's P45 numbers were measured against the key this fix
supersedes. No other cell is touched: the rule needs a macro body to
supply a qualifier, which is a C/C++ shape, and `internal/grade` is
unchanged.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P46 | O10 (fmt) | the six `os.cc` rows move from contradicted to **confirmed**, not to silent: the key will hold a site at each use site, and in `posix-mock-test`'s unit its target is the mock Hobbes draws (`FMT_SYSTEM(call)` is `test::call` there). Contradicted 11 → **5**, confirmed 3,263 → **3,269**, precision 99.7% → **99.8%** | met if the six named rows are confirmed row for row; any of them landing silent is a finding to read, not a result |
| P47 | O10 (fmt) | the 5 left are C-153's 4 and C-155's 1 (`compile-test.cc:127`), and the triage ratio becomes `hobbes-wrong 5 : oracle-wrong 0` | met on the row sets |
| P48 | O10 (fmt) | coverage moves without judgment moving: `sites_macro` falls and `sites_static` rises by the same count, and the `macro→*` miss classes shed what `static→*` gains — the mode follows the repositioned site | recorded either way; a judgment change here would mean the rule reaches further than the fixture says |
| P49 | O10 (args) | unchanged — no `FMT_SYSTEM`-shaped macro in that repo | met per the report |
| P50 | the four foreign C++ cells | each moves only where the key moved: a tool's edge at a use site can now confirm where the key previously held nothing there. **Every one of them is expected to rise**, as they did under H-30 | met per cell, each listed before → after, signed |
| P51 | all cells re-run | poison PASS, 0 falsely confirmed | met per cell |

**Recall is not predicted** beyond "it does not fall": the six calls
re-key onto lines that already carry pairs, and the collapsed line reads
site-line grain, so the direction is not obvious enough to claim in
advance.

**Graded 2026-09-16**, after `db20845`. Both keys re-run contained (fmt
302 s, args 315 s) against the same standing exports, so the Hobbes side
is identical row for row and only the key moved.

- **P46 — met, in its strong form.** The six `os.cc` rows are
  **confirmed**, checked individually and not inferred from the
  contradicted count: 176, 222, 274, 282, 300 and 310 each now key at
  the use site, and in `posix-mock-test`'s unit the target is the mock
  Hobbes draws. Contradicted 11 → **5**, confirmed 3,263 → **3,269**,
  precision 99.7% → **99.85%** (3,269/3,274).
- **P47 — met.** The five left are exactly C-155's one
  (`compile-test.cc:127`) and C-153's four (`format-test.cc:689`, 690,
  692, 696). **fmt's triage ratio is now `hobbes-wrong 5 : oracle-wrong
  0`:** every contradiction left on that cell is ours.
- **P48 — recorded, as predicted.** `sites_macro` 2,771 → 2,761 and
  `sites_static` 30,765 → 30,776; the `macro→*` miss classes shed what
  `static→*` gained. No judgment moved with it.
- **P49 — met, in its strong form.** args' edge set is identical and
  **no row changed bucket at all** — checked as a set, not by totals.
  100.0% (1,995/1,995), recall 56.4%, collapsed 63.1%, poison 1,938 /
  62.
- **P50 — MISSED.** I predicted all four foreign C++ cells would rise
  "as they did under H-30". Three did not move at all
  (CodeGraphContext fmt 95.71%, CodeGraphContext args still grading
  nothing, repowise args 90.15%) and the fourth moved by a single row
  (repowise fmt 47.96% → 47.97%). **The cause, which the prediction
  should have seen:** H-30 forgave *guesses on lines the key left
  unresolved*, which a name resolver makes constantly, so it lifted
  every tool. H-31 moves *sites*, which helps a tool only where it had
  already drawn an edge at the corrected position — and at fmt's
  `os.cc` use sites the tools drew nothing. A fix to the key's
  **position** is not the same kind of event as a fix to the matcher's
  **silence**, and P50 treated them alike.
- **P51 — met.** Poison PASS on every cell run, 0 falsely confirmed
  (fmt 2,642 / 883, args 1,938 / 62).
- **Recall did not fall:** fmt 14.5% (7,328/50,524 → 7,334/50,525),
  args 56.4% unchanged.

**Both of fmt's figures stand, and both belong in the record.** As
reported: **99.85%**. Judged as the pre-H-30 grade judged — adding back
the six C-153 rows H-30 silences — **99.66%** (3,269/3,280). The gap is
C-155 and C-153's remainder, which are ours, not the oracle's.

**Graded 2026-09-16**, after H-28/H-29 (`eec8141`) and H-30 (`f747aef`).
Both C++ cells were re-run contained against their standing Hobbes
export, so the Hobbes side is identical row for row (fmt 3,525 edges,
args 2,000 — checked as sets, not counts) and only the key and the
matcher moved.

- **P36 — MISSED.** Predicted contradicted 28 → 17, the survivors being
  C-153's 10 and H-31's 7. Actual: **11**. H-31's 7 survive exactly as
  predicted (the six `os.cc` rows and `compile-test.cc:127`), but only
  **4** of C-153's 10 do. The other 6 were silenced by H-30, which the
  prediction did not anticipate.
- **P37 — MISSED.** Predicted confirmed +6 exactly (H-28's 1, H-29's 5)
  with none lost. Actual **+9**, none lost: 4 came from the contradicted
  set (H-28 ×1, H-29 ×3) and 5 from `silent/unreachable`, where H-28's
  member-token repositioning moved a site onto the line Hobbes already
  drew (all five in `gmock-gtest-all.cc`). The prediction counted only
  the contradicted set and forgot that a position fix also reaches rows
  the key had never matched.
- **P38 — MISSED.** Predicted 99.4–99.6%; actual **99.7%** (3,263/3,274),
  just above the range, for the reasons P36 and P37 name.
- **P39 — met.** args stays 100.0% (1,995/1,995) with no contradiction;
  its graded rows did not move at all, though its *poison* line did
  (below).
- **P40 — met.** Recall fell on neither cell: fmt 14.5% → 14.5%
  (7,319/50,569 → 7,328/50,524), args 56.4% → 56.4%.
- **P41 — met.** `cppclang`'s 25 hand-keyed sites stand at their lines;
  seven member-call **columns** moved onto the member token, which D-O4
  carries outside the match.
- **P42 — met.** All 38 own cells with a stored pair: nothing moved at
  all, `line-unresolved` 0 on every one, precision fell nowhere. H-30 is
  inert outside C++ on the standing corpus. The other 6 rows are keys
  with no stored Hobbes export and are not covered.
- **P43 — met.** Poison PASS with 0 falsely confirmed on every cell run
  (fmt, args, and all 44 foreign).
- **P44 — met.** 13 of 44 foreign cells moved, every one purely
  contradicted → silent, with the contradicted fall equal to the silent
  rise equal to that cell's `line-unresolved`, confirmed unchanged
  throughout; no foreign row moved for any other reason.
- **P45 — met.** The four foreign C++ cells were regraded against the
  **new** key: CodeGraphContext fmt 95.71%, repowise fmt 47.96%,
  repowise args 90.15%, CodeGraphContext args still grading nothing.

**What the headline does not say, stated here because it runs against
our own interest.** Of the 17 rows that left fmt's contradicted bucket,
**6 are C-153's** — scip-clang naming the wrong declaration in a
template, where Hobbes' edge is genuinely wrong. They are now
*unjudged*, not fixed: the same line carries a dependent call the key
left unresolved, so H-30 declines to judge it. Precision therefore
reads 99.7% where the like-for-like figure, judging the rows the
standing grade judged, is **99.48%** (3,263/3,280). Both numbers belong
in the cell record, and C-153's own entry now reads 4 judged : 6
unjudged rather than 10 judged. Whether the lane should print a
"judged-as-before" companion on any cell with `line-unresolved > 0` is
a reporting decision for the lead, not something a regrade may settle
for itself.

**The same trade shows on the poison instrument.** On a line the key
left unresolved the matcher declines to judge, so it also declines to
*refuse* a poisoned edge there: fmt's poison went 3,282 refused / 243
unjudged to 2,643 / 882, and args' grade did not move at all while its
poison went 1,995 / 5 to 1,938 / 62 — the regenerated key repositions
member-call sites, so the twins land differently. Every cell still
passes with 0 falsely confirmed, which is how P43 is worded, but the
instrument covers fewer sites than it did.

### 10.10 C-155 lifted at lane A — written 2026-09-16, before the regrade

ADR-121: lane A records no C++ call site under `sizeof`, `alignof`,
`decltype`, the `noexcept` operator or a requires-expression, and
`noexcept`/`typeid` in call position record no site of their own;
`typeid`'s operand keeps its sites. Measured before writing this: fmt has
49 lane A sites under those shapes (all `decltype`), of which exactly one
draws a graded edge — `compile-test.cc:127`, C-155's row; args has 7
(all `decltype`), none drawing an edge. The oracle's own half (H-32: the
key holds a site under `sizeof`, `noexcept` and `typeid`) has no
instance on either cell, so its fix moves neither key.

**Scope.** The Hobbes side only: fmt and args re-ingested at the new
version and re-exported, then graded against their **standing** keys
(`regrade-out/h31/{fmt,args}/oracle.json`), so the key is identical and
only the export moves. The foreign cells are untouched (their side did
not change). After the oracle unit lands, both keys are re-run
contained and diffed site for site against the standing ones.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P52 | O10 (fmt) | edges 3,525 → **3,524**: the one `arg` edge at `compile-test.cc:127` is gone and no other row changes bucket; contradicted 5 → **4** (C-153's four, row for row), confirmed 3,269 unchanged, precision 99.85% → **99.88%** (3,269/3,273); like-for-like 99.66% → **99.69%** (3,269/3,279) | met if the removed row is exactly that one and the rest of the export is identical as a set; a second moved row is a finding to read |
| P53 | O10 (fmt) | recall unchanged, 7,334/50,525: the removed edge was never a key pair | met per the report |
| P54 | O10 (fmt) | coverage on the Hobbes side: 49 fewer C++ call sites in the ingest's rows, the key's `sites_*` untouched | recorded; the count is the measurement's, and a different number means the walk's ancestor rule reaches somewhere the count did not |
| P55 | O10 (args) | identical row for row — 2,000 edges, 1,995/1,995, 5 silent — since none of its 7 sites drew an edge | met if the export is identical as a set |
| P56 | both, after the oracle unit | the re-run keys are identical site for site to the standing ones; the fixture `uneval.cpp` is the only place H-32 shows | met per the diff; a moved site is a sighting for RC-11 |

Poison PASS on both, 0 falsely confirmed (the usual P51 clause).

**Graded 2026-09-16**, after `86b826a` (0.2.33-beta). Both clones
re-ingested at the new tree (lane B on, contained) and re-exported; the
keys are the standing ones, unchanged. Outputs in
`~/.hobbes/bench/uneval-drivers/regrade/{fmt,args}/`.

- **P52 — met on the judgement, MISSED on the count.** Contradicted 5 →
  **4**, the four C-153 rows exactly (`format-test.cc:689`, 690, 692,
  696); confirmed 3,269 unchanged; precision **99.88%** (3,269/3,273);
  like-for-like **99.69%** (3,269/3,279). But the export is **3,499**
  rows, not 3,524: 26 removed, 0 added, every removed row read — the
  contradiction and **25 oracle-silent edges**, all at `decltype`
  operands (`unreachable` 65 → 42, `no-targets` 119 → 117). The
  pre-measurement had skipped the 25 headers C++ claims and matched
  targets by bare name, so it saw 1 edge where there were 26 (ADR-121's
  dated correction). The versions between the standing export
  (0.2.21-beta) and this one contributed nothing else: 0 rows added,
  none removed outside the rule.
- **P53 — met.** Recall 14.5% (7,334/50,525), unchanged to the pair;
  collapsed 12.4%.
- **P54 — MISSED, same cause.** 299 lane A sites gone, not 49 (294
  `decltype`, 5 `sizeof`; 183 in headers, 116 under `test/`), measured
  by running the old and the new walk over the provider's own file list.
  The key's `sites_*` are untouched, as predicted.
- **P55 — met, in its strong form.** args' export is identical as a set
  (2,000 rows), 1,995/1,995, 5 silent, recall 56.4%, collapsed 63.1%.
- **P56 — MISSED on the premise, met on the judgement.** After the
  oracle unit (`fffadbd`) both keys re-ran contained (fmt 355 s, args
  363 s; `~/.hobbes/bench/uneval-drivers/keys/`). args' key is identical
  site for site (5,101). fmt's key lost **6 sites** (36,018 → 36,012),
  every one read: `core.h:915` `sizeof(isalpha('x', loc))` (two
  entries, the dynamic and the static), `os.h:380` `sizeof(data()[0])`,
  `gmock-gtest-all.cc:3252` `sizeof(needle[0])`, `gtest.h:4352` and
  `:4359` `sizeof(test<T>(…))` — all `sizeof` operands, which the
  prediction said fmt had none of, written before ADR-121's corrected
  count found 5 lane A sites under `sizeof` there. `sites_unevaluated`
  reads 153 on fmt (a per-unit sum) and 0 on args. **No judgement
  moved:** the standing export against the new key is 3,269/3,274 as
  against the old; the fresh 0.2.33-beta export against the new key is
  **3,269/3,273 (99.88%)**, recall 7,333/50,524, poison PASS 2,642 /
  857, 0 falsely confirmed. The fixture is not the only place H-32
  shows after all, but nowhere it shows did Hobbes draw an edge.
- Poison PASS on both, 0 falsely confirmed: fmt 3,499 seeded, 2,641
  refused / 858 unjudged; args 2,000 seeded, 1,938 / 62.

**The lesson, for the next lift:** a count taken before a decision must
use the provider's file list, not a walk of its own, and must match
graded rows by position, not by name. Both are one line each; the
prediction that carried them was wrong by a factor of six on sites and
twenty-six on edges, in the direction that made the change look
smaller than it was.

### 10.11 C-153's rule measured — written 2026-09-17, before any rule is run

ADR-125. Two candidate rules over C++ semantic `calls` edges, read on the
**standing** exports against the **standing** keys, no ingest and no key
re-run: fmt `~/.hobbes/bench/uneval-drivers/regrade/fmt/hobbes.json`
against `keys/fmt/oracle.json`; args `regrade/args/hobbes.json` against
`keys/args/oracle.json` (the same directory). *R-qual*: the callee is written with a
qualifier carrying template arguments and the resolved declaration's
owner carries different ones (or none where the text names a
specialisation). *R-self*: the edge's target is its own caller. What was
known before writing: C-153's ten fmt rows by site (the four
`test_format<0>::format` contradictions at `format-test.cc:689/690/692/696`;
six `line-unresolved` rows at `compile-test.cc:37`, `:62`,
`format-test.cc:1910`, `std.h:698`, `:714`, `:726`). No rule has been run
over any export.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P57 | fmt | R-qual matches the four `test_format<0>` rows and the four self rows (`compile-test.cc:37`, `:62`, `format-test.cc:1910`, `std.h:698`), and not the two `format_as` rows | met if all eight and neither `format_as` row; each miss read against the source |
| P58 | fmt, args | R-qual's cost: ≤ 5 confirmed edges on fmt, 0 on args | met per the rows; every matched confirmed edge read |
| P59 | fmt | R-self matches the four self rows **and** at least one confirmed edge (a real recursion), so R-self is not safe alone | met if both |
| P60 | args | neither rule matches a contradicted or `line-unresolved` row (args has none of C-153's) | met per the rows |

**Decision rule (ADR-125 §3, fixed here):** R-qual is built as an
abstention only if, on each cell, its matched confirmed edges ≤ its
matched wrong edges (contradicted, plus the `line-unresolved` rows among
C-153's ten). Matched edges in any other silent bucket are read and
reported, and count on neither side. The surfacing of ADR-125 §4 is built
whatever this reads.

**Graded 2026-09-17**, `~/.hobbes/bench/c153-rule/measure.py` over the
standing grades' rows (`uneval-drivers/keys/{fmt,args}/final-report.json`,
3,499 and 2,000 edges) and the clones at `3a0661d7` and `903b07d`; outputs
`fmt.json`, `args.json` beside it. The rule as implemented, stated so it
is not mistaken for more: every call-shaped occurrence of the callee's
name on the site line must be written qualified as `Q<args>::name`, `Q`
the resolved owner's base name, and every one's arguments (whitespace
removed) must differ from the owner's; an unqualified occurrence on the
line, a different `Q`, or an owner whose arguments cannot be read stops
it.

- **P57 — met.** R-qual matches exactly the eight: `format-test.cc:689`,
  `:690`, `:692`, `:696` (written `test_format<20>`, `<20>`, `<21>`,
  `<max_packed_args>`, resolved `test_format<0>`), and `compile-test.cc:37`
  (`formatter<int>` → `formatter<type_with_get>`), `:62` (`formatter<const
  char*>` → `formatter<test_formattable>`), `format-test.cc:1910`
  (`formatter<int>` → `formatter<Answer>`), `std.h:698`
  (`formatter<std::exception>` → `formatter<std::exception_ptr>`). Neither
  `format_as` row.
- **P58 — met.** Confirmed edges removed: **0** on fmt, **0** on args.
- **P59 — met.** R-self matches the four self rows and **3 confirmed
  recursions** on fmt (`chrono.h:943` `pow10`, two in gtest), plus 2
  `no-targets` rows read as gmock recursions.
- **P60 — met.** On args R-qual matches nothing; R-self matches **10
  confirmed recursions** and no wrong row.

**The decision rule reads:** R-qual removes 0 right and 8 wrong on fmt, 0
and 0 on args — **built** (ADR-125 §3). R-self removes 3 right against 4
wrong on fmt but **10 right against 0 wrong on args — not built.** The
residual R-qual carries into C-153 when built: a written argument that is
an alias or a default the owner spells differently (`formatter<int>` for
`formatter<int, char>`) would make it remove a right edge; 0 such on
these two cells, and the build's tests pin the shape.

**Amended the same day, before the build (ADR-125's amendment):** R-qual
fires only when the resolved owner is an explicit full specialisation
(`template <>`) — an owner without arguments (the primary template) or a
partial specialisation would have removed right edges on other repos.
All eight matched owners are full specialisations, so the grade above
stands unchanged.

**The build's regrade, predicted before the ingest (2026-09-17, after
`S-20260917T132019Z-145d`):**

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P66 | fmt | the export loses exactly the 8 rows, 3,499 → **3,491**; contradicted 4 → **0**; `line-unresolved` 13 → **9**; confirmed 3,269 unchanged; precision **100%** (3,269/3,269), strict **99.73%** (3,269/3,278); the tail counts **8** `qualifier-mismatch` sites | met if the removed rows are exactly the eight, as a set |
| P67 | args | export identical as a set (2,000 rows), 0 `qualifier-mismatch` | met per the diff |
| P68 | this repo | 0 `qualifier-mismatch`; `graph.json` identical to the pre-merge ingest apart from its stamp | met per the diff |

**Graded 2026-09-17** (`~/.hobbes/bench/c153-rule/regrade/`, ingest at
`c53dc5d`, the standing re-run keys):

- **P66 — MISSED on the count, met on the direction.** fmt's export went
  3,499 → **3,493**. Six rows were removed, none added, and every removed
  row is one of the eight: `format-test.cc:689/690/692/696`,
  `format-test.cc:1910` and `std.h:698`. Results:
  - contradicted 4 → **0**, confirmed 3,269, precision **100%**
    (3,269/3,269);
  - `line-unresolved` 13 → **11**, strict **99.7%** (3,269/3,280);
  - `qualifier-mismatch` **6**, poison PASS (2,638 refused / 855
    unjudged, 0 falsely confirmed).
  
  **`compile-test.cc:37` and `:62` still draw.** Both specialisations
  are written after `FMT_BEGIN_NAMESPACE`, a macro tree-sitter cannot
  read (C-145). The parse puts `template <>` into an ERROR node before a
  bare `struct formatter<X> : formatter<Y> {..}`, so lane A never saw a
  `template_declaration` and did not record the full specialisation. The
  rule fired less than predicted, never more.
- **P67 — met.** args is identical as a set (2,000 rows), 1,995/1,995,
  `qualifier-mismatch` 0.

**P69, predicted before the fix:**

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P69 | fmt, args | lane A also records a class as an explicit full specialisation when its name carries arguments and the node before it is an ERROR node ending in exactly the tokens `template` `<` `>` (the header the macro parse lost). fmt's export then loses the remaining two rows (3,493 → **3,491**), `line-unresolved` 11 → **9**, strict **99.73%** (3,269/3,278), `qualifier-mismatch` **8**; args is unchanged | met if exactly those two rows go, as a set |

### 10.12 Reach through dispatch, measured — written 2026-09-17, before anything is expanded

ADR-126. For each Hobbes `calls` edge whose target has `implements`
edges into it, the pairs (call site → each override, `implements`
followed transitively). Nothing is drawn; the pairs are computed from
`graph.json`. jsoup is re-ingested at the current version, contained
(the stored graphs predate ADR-120), and read against the standing jsoup
javac key; click's pairs against the standing click trace; args' stored
graph (0.2.32-beta or later, 178 `implements` edges) as the control.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P61 | jsoup | set precision: ≥ 95% of expanded pairs are in the key's CHA target set at the site | met per the pairs; every pair outside the set read to at least a sample of 20 (seeded) |
| P62 | jsoup | set recall: the expanded pairs cover ≥ 80% of the CHA targets at the sites that have a Hobbes base edge | met per the pairs |
| P63 | jsoup | fan-out: median overrides per expanded call ≥ 2, maximum > 20 | recorded |
| P64 | click | observed share: ≤ 30% of expanded pairs appear in the trace; none is counted as a contradiction | met per the pairs; fewer than 20 pairs is reported as too small to read |
| P65 | args | every expanded pair is unjudged by construction (the key names the declared method only) and is reported, not graded | met if the script grades none |

Go, TS and Rust are recorded as not measurable (ADR-126's table). The
measurement decides the wording of any surface and whether it is worth
building; it cannot make a pair a proven edge, and a CHA confirmation is
reported as agreement with the hierarchy, never as reach.

**Graded 2026-09-17** with `~/.hobbes/bench/dispatch-reach/measure.py`
(outputs `jsoup.json`, `click.json`, `args.json` beside it). jsoup and
click were re-ingested at 0.2.35-beta, contained, at the keys' commits
(`7860d088`, `36baa15f`). args came from its stored graph. Only
method-level `implements` edges were followed.

- **P61 — met on the count; the read found what the count hides.**
  - jsoup has 1,530 call sites with overrides and 2,944 pairs. 2,837 are
    in the CHA set (**96.4%** of all pairs), 1 is outside it, and 106 had
    no dispatch site to judge them against. Over judged pairs alone the
    figure is 99.96%, but that quotient leaves out the 106, and they are
    the finding.
  - **All 106 sit where javac resolved the call statically to the base
    method:** `super.clone()` at `CDataNode.java:37` and
    `Document.java:287`, plus the other `super.`, private and final
    shapes. No dispatch happens there, so every override those pairs
    list is wrong, including the caller itself (`CDataNode.clone` for
    its own `super.clone()`). A naive expansion is therefore wrong on
    3.6% of jsoup's pairs.
  - The one outside pair is the key's grain, not a wrong pair:
    `this.set(..)` at `Nodes.java:342` reaches `Elements.set(int,
    Element)`, which overrides `Nodes<T>.set(int, T)` through a bridge
    method. The CHA set compares erased parameters, so it leaves that
    override out.
- **P62 — met.** Set recall is **97.4%** (2,837 of the 2,913 CHA targets
  at the expanded sites).
- **P63 — MISSED on the median, met on the maximum.** The median fan-out
  is **1**, not ≥ 2: most overridden jsoup methods have one override.
  The maximum is **41**.
- **P64 — met.** Of click's 360 pairs over 128 call sites, 99 were
  observed (**27.5%**) and 261 unobserved, none counted as wrong. The
  maximum fan-out is 27.
- **P65 — met.** args has 353 pairs over 99 call sites, all unjudged by
  construction. The median fan-out is 2 and the maximum 15.

**What this says for ADR-126 §3.** The override set is accurate (C-58's
set, ADR-120). **Expanding every call to a base method with overrides is
not:** a call the language does not dispatch has to be excluded by its
syntax before any pair is listed. That covers Java `super.` calls,
private, static and final methods, Python `super().` calls, and C++
calls qualified with a class name. On jsoup that excluded shape was 3.6%
of all pairs. Any surface built on this measurement names the exclusion
and its measured share, and says that the key can confirm the set but
never the reach.

### 10.13 A definition lane A lost, read from the index — written 2026-09-17, before the rule is built

ADR-129. **What was and was not pre-registered, plainly.** The mint rule
was *fitted on fmt*: a scratch probe graded a naive rule's export against
the standing key (98.2%, 123 contradicted), the rows were read, and two
of lane A's own symbol rules were added (definitions only; no `term`).
fmt's probe figures are therefore measurements, never predictions met.
**args was held out:** the rule was frozen and P70–P73 written to
`~/.hobbes/bench/c145-recovery/PREREG-args.md` before the args probe ran.

| # | Cell | Prediction (before the args probe) | Result |
|---|---|---|---|
| P70 | args | minted call edges: 0 contradicted | **met** — 67 added, 67 confirmed |
| P71 | args | recall 56.4% → between 56.4% and 66% | **met** — 58.6% (2,086/3,561) |
| P72 | args | no standing confirmed edge lost | **met** — 1,995 → 2,062 |
| P73 | args | strict precision ≥ 99.5% | **met** — 100%, no unjudged row |

The probe's exports were synthetic: standing export rows plus one row per
mintable fact. The predictions below are for the **built** rule, a fresh
contained ingest of each cell at the change, exported and graded with
`oracle grade --poison` against the stored keys (fmt and args:
`~/.hobbes/bench/uneval-drivers/keys/`; cJSON and sqlite-vector:
`~/.hobbes/bench/oracle/<cell>/oracle.json`). Written before any of it is
built.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P74 | fmt | contradicted 0; confirmed 6,533 ± 15 | per the report; every contradicted row read and named hobbes-wrong, provider (C-153) or oracle-grain |
| P75 | fmt | recall 29.1% ± 0.2 points; collapsed 24.9% ± 0.3 | per the report |
| P76 | fmt | strict precision between 98.9% and 99.2% (62 ± 8 line-unresolved rows); every new unjudged row read by hand, and any that is C-153's shape counted in the cell record | per the report and the read |
| P77 | fmt | no standing confirmed edge lost: the standing export's confirmed rows are a subset of the fresh one's | set comparison, as `grade-cell.sh` does |
| P78 | args | 2,062 ± 3 confirmed, 0 contradicted, recall 58.6% ± 0.1 | per the report |
| P79 | cJSON, sqlite-vector | 0 symbols minted; both exports identical to the standing ones as sets | set comparison |
| P80 | fmt | symbols minted 622 ± 10; `uses` edges gained from minted types > 0 and no `calls` edge to a minted type | read from `graph.json` |
| P81 | every cell | poison PASS, 0 falsely confirmed | per the report |

A miss on P74, P77 or P79 is a finding against the rule and is fixed
before the version moves. A miss in the flattering direction is recorded
as a miss.

**Results (2026-09-17, 0.2.41-beta; the cell records carry the blocks).**
- **P74 — missed on the count, met on the contradictions.** 6,510
  confirmed at 0 contradicted, under the 6,518–6,548 band. The built
  rule first read 6,527; the regrade then found two shapes the probe
  could not see (below), and the `anonymous` refusal gave up 17 confirmed
  edges onto members of unnamed structs. The unflattering direction, by
  a rule added after the prediction.
- **P75 — met.** 29.1% (14,679/50,524); collapsed 24.8%.
- **P76 — not graded as written** (§10.14 replaced it before anything
  was built). For the record, the mint alone read 62 rows and 99.06%,
  inside the band.
- **P77 — met.** 0 standing confirmed rows lost, on every cell.
- **P78 — met.** args 2,062 confirmed, 0 contradicted, 58.6%.
- **P79 — missed on the symbols, met on the exports.** The first built
  rule minted 11 symbols on cJSON and 10 on sqlite-vector where 0 were
  predicted; both exports were identical to the standing ones. **The
  cause is the probe's, and it is the finding:** it counted only lost
  definitions that some below-floor *call* targets, and the rule mints
  every lost definition. Reading the 21 found every one to be either an
  unnamed struct under scip-clang's invented name
  (`$anonymous_type_9456…_0`) or a type lane A already names at another
  line (`typedef struct cJSON {…} cJSON;`) — invisible to a call-edge
  grade, and wrong as nodes. Two refusals (`anonymous`,
  `lane-a-has-type`) were added with tests before the version moved, as
  this section required; cJSON then mints 1 named enum and sqlite-vector
  3 named structs, each read as a real lost definition.
- **P80 — missed.** 1,690 symbols, not 622 ± 10 — the same cause; the
  second half met (5,661 `uses` onto minted types, 0 `calls`). A seeded
  sample of 25 minted symbols on fmt read as real definitions with
  bodies, all 25.
- **P81 — met** on all four cells.

### 10.14 R-arity — written 2026-09-17, before either rule is built

ADR-130. ADR-129 §6's hand read of the 53 rows its mint leaves unjudged
on fmt found 34 wrong edges, and a 35th among the `no-targets` rows:
`copy<Char>(begin, end, out)` drawn to the two-parameter `copy` at
`format.h:549` (C-153, surfaced by the mint). The too-many-arguments rule
was measured over the probe export with a regex reader (`arity.py`); the
built rule reads lane A's parse. ADR-129 and ADR-130 ship together, so
**§10.13's P76 (the mint alone: strict 98.9–99.2%) is never graded as
written**: it is replaced by P83 here, before anything is built, and P74's
confirmed count stands with the five local-to-function edges ADR-129's
amendment gave up inside its band. Every other §10.13 row stands.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P82 | fmt, args | **0 confirmed edges withheld by R-arity**: every `arity-mismatch` site, joined to the mint-only export's grade, is unjudged or contradicted there, never confirmed | the sites listed from the ingest, joined by (site, target) to a grade of the same tree with the rule disabled by a scratch wrapper that clears every fact's `argc` before `project` (`~/.hobbes/bench/c145-recovery/`, as the step-0 probe wrapped it); no product seam |
| P83 | fmt | `line-unresolved` 27 ± 5; strict precision 99.5–99.7% | per the report |
| P84 | fmt | R-arity fires on ≥ 38 graded sites: the 35 `copy` rows, `holds_alternative` ×2, `any_cast` ×2, `scan.h:466` — each of those 40 named rows withheld; any the built reader misses is listed with why | the 40 rows checked by name against the fresh export |
| P85 | args, cJSON, sqlite-vector | R-arity fires nowhere graded; the C cells' tails gain no class | per the ingest |
| P86 | fmt | every row R-arity withholds beyond the 40 is read by hand; ≥ 90% are wrong edges, the rest named as the rule's cost | the read, in the cell record |

A miss on P82 is a finding against the rule and is fixed before the
version moves.

**Results (2026-09-17, 0.2.41-beta).**
- **P82 — met.** fmt: the rule withholds 40 graded rows; in the grade of
  the same tree with the rule disabled they are 35 `line-unresolved` and
  5 `no-targets`, **0 confirmed**. args: nothing withheld.
- **P83 — met.** `line-unresolved` 27; strict 99.59% (6,510/6,537).
- **P84 — met.** All 40 named rows withheld, none missed.
- **P85 — met.** R-arity fires nowhere on args, cJSON or sqlite-vector.
- **P86 — met.** One site beyond the 40, below row grain:
  `chrono.h:330`, where the join paired `std::begin(out.buf)` with fmt's
  zero-parameter `begin` on a line that also holds `in.begin()` (C-70's
  shape). A wrong pairing, rightly withheld; no row moved.
- **What neither rule reaches, found by the read:** of the 19 unjudged
  rows the mint leaves, one is wrong at the right arity
  (`format.h:2387`, `write` drawn to itself) — C-153's entry names it.

### 10.15 Operators at the token, outside a template — written 2026-09-17, before the rule is built

ADR-131. Step 0 (`~/.hobbes/bench/c146-operators/`) wrote the export the
rule would produce from fmt's cached index and graded it against the
stored key; nothing was drawn. The rule was fitted on fmt, so **args was
held out**: its predictions were written to `PREREG-args.md` before any
script read its facts, key or clone, with `simulate.py` frozen by hash.
That scratch file numbered them P85–P89, numbers §10.14 had already
used; they are P87–P91 here, unchanged in wording.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P87 | args (held out, probe) | 0 contradicted among the added rows | the probe export, graded |
| P88 | args (held out, probe) | 0 new `line-unresolved` rows | per the report |
| P89 | args (held out, probe) | at most 2 added rows in any silent bucket | per the report |
| P90 | args (held out, probe) | 5–120 added edges; recall up by less than 3 points | per the report |
| P91 | args (held out, probe) | the operator-arity check fires on 0 rows outside a template | the probe's count |

**Held-out results (2026-09-17, run once).** P87, P88, P89, P91 met: +136
edges, 136 confirmed, 0 contradicted, 0 silent, 0 arity rows. **P90
missed**: 136 edges, not ≤ 120; recall 58.6% → 62.5%, +3.9 points, not
< 3 — args' tests compare and dereference its flag types by operator
more than I guessed.

For the built rule, written before the unit is dispatched:

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P92 | fmt | confirmed 6,510 → 6,901 ± 5, **0 contradicted**; recall 30.1% | stored key, `--poison` |
| P93 | fmt | `line-unresolved` stays 27; strict 99.6% (not below 99.59%) | per the report |
| P94 | args | confirmed 2,062 → 2,198 ± 3, 0 contradicted; recall 62.5% | stored key |
| P95 | cJSON, sqlite-vector | exports identical, row for row | the export compared as a set |
| P96 | fmt, args | every added row is one the probe's `token-plain` export holds; any other is read by hand and named | the two exports compared as sets |
| P97 | fmt | no `calls` edge added from a token inside a template: `operators.in_template` counts them and the export holds none | the ingest's block against the export |

A contradicted row, or a new `line-unresolved` one, is a finding against
the rule and is fixed before the version moves.

**Results (2026-09-17, 0.2.42-beta; unit `d1b9`, stored keys, contained).**
- **P92 — met.** fmt 6,901/6,901, 0 contradicted; recall 30.1%
  (15,228/50,524), collapsed 24.8% → 26.1%.
- **P93 — met.** `line-unresolved` 27; strict 99.61% (6,901/6,928).
- **P94 — met.** args 2,198/2,198, 0 contradicted; recall 62.5%
  (2,226/3,561), collapsed 69.5%.
- **P95 — met.** cJSON 1,713 rows and sqlite-vector 19,744, identical;
  neither graph has an `operators` block.
- **P96 — met.** No row outside the probe's export on either cell. One
  probe row is not drawn: `gtest.h:11685`, an `operator=` declaration
  inside an ERROR node, which the built rule does not record (the probe
  had it `unreachable`, never confirmed).
- **P97 — met.** fmt: 551 tokens drawn (392 new export rows once a
  line's repeats fold), 437 references inside a template left as `uses`;
  args 140 and 40.
- Signed direction of fix: fmt confirmed +391, contradicted ±0,
  unjudged-line ±0, recall +1.0 point; args confirmed +136, recall +3.9.

### 10.16 A dependent operator's reference draws nothing — written 2026-09-17, before the unit is dispatched

ADR-131's amendment. `uses` is graded by no key, and both C++ cells were
read by the scratch wrapper that measured the route
(`~/.hobbes/bench/c153-operator-uses/`), so nothing here is held out:
P98 and P99 say the graded export must not move, P100 and P101 that the
build equals the probe. The exports had not been run on the probe's
graphs when this was written.

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P98 | fmt, args | exports identical to 0.2.42-beta's, row for row: 6,901/6,901 and 2,198/2,198, 0 contradicted, `line-unresolved` 27 on fmt | stored key, `--poison`; the exports compared as sets |
| P99 | cJSON, sqlite-vector | exports identical, row for row; no `operators` block | the export compared as a set |
| P100 | fmt, args | symbol edges: fmt −156, args −24, every one a `uses`, none added; module edges: exactly `test/scan.h → include/fmt/format.h` and `args.hxx → test/test_common.hxx` go; nodes and symbols unmoved | the built graph against the probe's and against 0.2.42-beta's |
| P101 | fmt, args | `operators` reads `drawn` 551 / 140 and `in_template` 437 / 40, as before — the second now the number withheld | the ingest's block |

A `calls` row that moves, or an edge lost that is not a `uses` at an
operator token inside a template, is a finding against the build and is
fixed before the version moves.

**Results (2026-09-17, 0.2.43-beta; unit `4033`, stored keys, contained;
`~/.hobbes/bench/c153-operator-uses/final/`).**
- **P98 — met.** fmt 7,331 export rows and args 2,203, identical to
  0.2.42-beta's as sets; fmt 6,901/6,901, 0 contradicted,
  `line-unresolved` 27, strict 99.61%; args 2,198/2,198. Poison PASS on
  both, 0 falsely confirmed.
- **P99 — met.** cJSON 1,713 rows and sqlite-vector 19,744, identical;
  neither graph has an `operators` block.
- **P100 — met.** fmt −156 symbol edges and args −24, every one a `uses`,
  none added; the two named module edges went and no other; nodes and
  symbols unmoved. Against the probe's graphs: 0 edges differ on either
  cell, evidence included.
- **P101 — met.** `operators` reads 551 / 437 on fmt and 140 / 40 on args.
- Signed direction of fix: every graded number ±0 on all four cells;
  `uses` symbol edges fmt −156, args −24; module edges −1 and −1, both
  read by hand as wrong.

### 10.17 Constructions at the token, outside a template — written 2026-09-17, before the unit is dispatched

ADR-132. The misses were classed on fmt with args held out
(`~/.hobbes/bench/cpp-constructions/PREREG-args.md`: 3 of 5 met — the
largest class and the dominant shape were both guessed wrong), and the
rule's export was fitted on fmt with args held out on the precision side
(`PREREG-args-sim.md`: P-s1–P-s4 met, 369 added rows all confirmed;
P-s5 half missed, 16 untokened rows where ≤ 15 was predicted). Both
files carry the frozen scripts' hashes. For the built rule:

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P102 | fmt | confirmed 6,901 → 7,012 ± 3, **0 contradicted**; recall 30.4% | stored key, `--poison` |
| P103 | fmt | `line-unresolved` stays 27; `unreachable` 43 → 67 ± 2, every new one a row the probe's hand read called right; strict 99.62%, not below 99.61% | per the report |
| P104 | args | confirmed 2,198 → 2,567 ± 3, 0 contradicted, no new silent row; recall 72.9% | stored key |
| P105 | cJSON, sqlite-vector | exports identical, row for row; no `constructions` block | the export compared as a set |
| P106 | fmt, args | every added row is one the probe's `token-plain` export holds (`fmt-sim2`, `args-sim2`); any other is read by hand and named | the two exports compared as sets |
| P107 | fmt, args | no `calls` edge from a token inside a template; `constructions.in_template` reads 44 ± 3 on fmt and 1 on args, and each stays a `uses` edge | the ingest's block against the export and the graph |

A contradicted row, or a new `line-unresolved` one, is a finding against
the rule and is fixed before the version moves.

**Results (2026-09-17, 0.2.44-beta; unit `4834`, stored keys, contained;
`~/.hobbes/bench/cpp-constructions/final/`).**
- **P102 — missed on the count, met on 0 contradicted.** fmt 6,993/6,993,
  not 7,012 ± 3; recall 30.3% (15,320/50,524), not 30.4%. 19 of the
  probe's rows are not drawn, one cause: the type is named through a
  using-declaration (`using fmt::detail::bigint;` ×14, `using fmt::file;`
  ×5), lane A's existing construct site takes the line's nearer
  same-named reference — the using-declaration, below the floor — and
  the join's claim is by `(file, line, name)`, so the constructor's
  reference never reaches the rule. The probe did not model the claim.
  Draws less; C-162 registers it.
- **P103 — met.** `line-unresolved` 27; `unreachable` 43 → 67, the 24 the
  probe's hand read called right; strict 99.62% (6,993/7,020).
- **P104 — met.** args 2,567/2,567, 0 contradicted, silent 5 → 5; recall
  72.9% (2,595/3,561).
- **P105 — met.** cJSON 1,713 rows and sqlite-vector 19,744, identical;
  neither graph has a `constructions` block.
- **P106 — met.** No row outside the probe's export on either cell; args
  is the probe's export exactly.
- **P107 — met.** fmt 120 drawn and 44 inside a template; args 369 and 1;
  no `calls` edge from a token inside a template. In the graph a `uses`
  becomes a `calls` between the same ends (fmt −86 / +85, args −156 /
  +155); no module edge moved.
- Signed direction of fix: fmt confirmed +92, contradicted ±0,
  unjudged-line ±0, `unreachable` +24 (read right), recall +0.2 points;
  args confirmed +369, recall +10.4 points.

### 10.18 The join's claim by position — written 2026-09-18, before the regrade ran (unit `3569` merged at `83cde1b`)

ADR-133. Every language shares the rule, so every stored-key cell is
regraded: 44 cells over 25 clones, each clone ingested by the tree before
the unit (`8738fc2`) and by main, graded against the stored key
(`~/.hobbes/bench/join-claim/regrade.sh`, `PREREG-regrade.md`,
`compare.py`). The two hobbes cells are left out: their clone, a worktree
at an old sha, is gone. The simulation before the build
(`PREREG-sim.md`, eight cells, P-j1–P-j6) met all six.

- **P108 — met.** fmt 6,993 → **7,012** confirmed, 0 contradicted; the
  export gains 19 rows and loses none. The number is ADR-132's P102.
- **P109 — met.** Every other cell: the export row-identical, every
  graded number ±0 (43 cells).
- **P110 — met.** No symbol or module edge removed on any clone; nodes
  and symbols unmoved.
- **P111 — met.** 1,796 symbol edges added across the 25 clones: 1,785
  `uses` and fmt's 11 `calls` (Severed-Chains 634, spring-data-
  elasticsearch 411, jsoup 363, zod 244, kbet 51, dagger 32, spring-
  petclinic 23, fmt 20, quic-go 9, click 6, memchr 3; none on the other
  fourteen).
- **P112 — met.** Poison passes on every cell, both arms.
- **P113 — met.** Two module edges added, none on a Java clone, both read
  by hand and true: quic-go `http3/body → interface` (`func (r *body)
  StreamID() quic.StreamID { return r.str.StreamID() }` — the return
  type, hidden by the method call's claim) and dagger `core/schema/util →
  dagql/introspection/query` (`dag.Query(ctx, introspection.Query, nil)`
  — the constant, hidden by the call's).
- What no key judges: a `uses` edge is not exported, so the 1,785 are
  held by the hand read of step 0's sample and by their shape, not by a
  grade.
- Signed direction of fix: fmt confirmed +19, contradicted ±0, strict
  99.62% → 99.62% (7,012/7,039), recall +0.1 point (30.3% → 30.4%);
  every other cell ±0.

### 10.19 A minted definition's extent — written 2026-09-18, before the unit is dispatched (unit `368a`; results below)

ADR-134, route (a). **This section is not a grade.** Every C and C++ key
is a resolution key — it judges `(site, target)` and never reads an
edge's `from` — so no graded number can move, and the first prediction
is that none does. The check on the rule is the key's own caller names
(`sites[].caller`, clang's enclosing function), read by a driver
(`~/.hobbes/bench/c145-extent/probe.py`) before and after on the same
clones, with its three naming equivalences. The simulation
(`simulate_r3.py`: `simulate.py` with refusal 3) is where the numbers
below come from.

- **P114.** Every graded number on the four C and C++ cells ±0, the
  export identical in `(site, target)`: fmt 7,012 confirmed, 0
  contradicted, strict 99.62%, 30.4%; args 2,567, 0, 72.9%; cJSON and
  sqlite-vector as stored. Poison passes on each.
- **P115.** Extents on fmt: **1,346 read; refused 34
  `conditional-inside`, 19 `holds-a-definition`, 0 `runs-off`.** args:
  66 read, none refused.
- **P116.** The probe on fmt (8,123 `calls` evidence rows in key files):
  lost callers **1,436 → 165 ± 5**; agreeing **6,392 → 7,610 ± 5**;
  lambda-inside 97 → 120; the "wrong caller" class 75 → 105, the 30
  added being the spellings ADR-134 read by hand (24 friend functions
  defined in a class, 5 methods of a nested specialisation and 1 lambda's
  class-qualified `operator()`, less what refusal 3 removed; the probe
  does not know these spellings) — C-164's 73 stay 73.
  args: lost **15 → 0**, agreeing 2,476 → 2,489, wrong-class 4 → 6 (two
  lambdas the probe's lambda test misses).
- **P117.** No row whose caller agreed with the key before differs from
  it after, on either cell.
- **P118.** On fmt and args: node, module-edge and symbol counts
  unmoved; no symbol differs but a minted function's or method's
  `end_line`; `calls` and `uses` symbol edges change only in `from`
  (module → a minted symbol, or a lane A symbol that starts before the
  extent → the minted one).
- **P119.** cJSON and sqlite-vector mint no function with a lost
  caller: their symbol edges are identical. A non-C clone (click) is
  byte-identical but for the version stamp.
- **P120 (direction only).** On fmt, no symbol's test reach shrinks, and
  the tests reaching through a minted function grow; the count is
  recorded, not predicted.

**Results (2026-09-18; unit `368a` merged, then the developer's fix on
it; `~/.hobbes/bench/c145-extent/regrade.sh`, `compare.py`, `regrade/`).**
Before is each clone's graph as ADR-133's code built it (`83cde1b`);
after is the same clone ingested by the branch with the fix. The first
run through the real ingest moved **2 rows of 16 on args**: the brief
said a file-scope site carries an empty scope, and lane A's C and C++
sites carry the module's id, which the projection reads as the caller.
The fix reads a module-id scope as the module; a second run found 56 fmt
rows on a one-line body's own line (`int f() { return g(); }`) unmoved,
and the mint now marks a read extent on the symbol (`extent: "braces"`)
so a body of one line re-homes and a refusal does not. The numbers below
are the third run's.

- **P114 — met.** fmt 7,012/7,012, 0 contradicted, strict 99.62%
  (7,012/7,039), 30.4%; args 2,567/2,567, 72.9%; cJSON 1,188/1,188,
  62.0%; sqlite-vector 851/851, 100.0%. Every export row-identical
  (removed 0, added 0); poison passes on each, both arms.
- **P115 — met exactly.** fmt 1,346 read; 34 `conditional-inside`, 19
  `holds-a-definition`, 0 `runs-off`, 0 `no-body`. args 66 read, none
  refused.
- **P116 — met on three counts, missed on two, and the misses are the
  prediction's arithmetic.** fmt agreeing **6,392 → 7,610** (predicted
  7,610) and the wrong-caller class **75 → 105** (predicted 105: the 30
  spellings; C-164's 73 unmoved); `calls` rows moved from a module
  **1,290**, the simulation's number. **Lost 1,436 → 188, not 165**, and
  lambda 97 → 97, not 120: the simulation's 23 lambda rows and 19
  unjudged rows were never in the probe's lost class (it classes a bare
  `operator()` as lambda and a line without a key site as such, whatever
  Hobbes says), so they could not leave it — 1,436 − 1,218 − 30 = 188.
  The 188: 111 under a refused extent, 63 under a definition nothing
  names, 11 where lane A lost a function's end, 3 lambdas. args: lost
  **15 → 0**, agreeing 2,476 → 2,489, wrong-class 4 → 6 — as predicted.
- **P117 — met.** No row that agreed with the key before is lost or
  wrong after, on either cell.
- **P118 — met but for four rows.** Nodes, module edges and symbol
  counts unmoved on all five clones; the only symbols that differ are
  minted functions and methods (fmt 1,346, args 66), in `end_line` and
  the `extent` mark — the mark is this build's, not in the prediction.
  Every changed `from` is a minted symbol's: fmt 1,290 `calls` and 668
  `uses` from a module, 92 `uses` from a lane A type that starts before
  the extent (a class → its own method; eight read by hand). **Not
  predicted:** two `uses` rows on fmt vanish (`NativeArray::InitCopy`
  and `InitRef` referenced on their own definition's line — a self-edge
  now, dropped as every self-edge is) and two appear on args
  (`Command::SelectedCommand` → `Command`, a self-edge of the class
  before).
- **P119 — met.** cJSON, sqlite-vector and click: symbols, edges,
  evidence rows and test reach identical.
- **P120 — met.** fmt: no test lost a symbol; 208 of 649 tests gained,
  reach pairs **3,183 → 6,131**.
- What no key judges: the 760 re-homed `uses` rows and the 19 + 23 rows
  the key cannot speak to stand on the extents the 1,218 judged rows
  share with them, not on a grade of their own.

### 10.20 A lane A symbol the index contradicts — written 2026-09-18, before the unit is dispatched

ADR-135, route (a). **Not a grade**, for §10.19's reason: no key reads a
caller. On fmt no edge runs *into* any of the 18 symbols R1 refuses
(read off the 0.2.46-beta graph: 37 `calls`, 38 `uses` and 1
`implements` evidence rows run out of them, none in), so no `(site,
target)` row can move. The check is §10.19's probe, before and after on
the same clones; the numbers are `~/.hobbes/bench/c164-wrong-callers/
simulate.py`'s, which took the first whole-word spelling of the name on
the symbol's line where the built rule reads lane A's own column.

- **P121.** Every graded number on the four C and C++ cells ±0, the
  export row-identical: fmt 7,012 confirmed, 0 contradicted, strict
  99.62%, 30.4%; args 2,567, 72.9%; cJSON 1,188; sqlite-vector 851.
  Poison passes on each.
- **P122.** fmt: R1 refuses **18** symbols (13 at a macro reference, 5 at
  a `term`'s); R2 re-reads **1** extent (`gtest-extra-test.cc:201`, 292 →
  210; the `GMOCK_DEFINE…` symbol is R1's first). args, cJSON,
  sqlite-vector: 0 and 0.
- **P123.** The probe on fmt (8,123 rows): wrong-caller **105 → 32**,
  agreeing **7,610 → 7,625 ± 2**, lost **188 → 246 ± 2**. args unmoved
  (2,489 / 6 / 72).
- **P124.** No row whose caller agreed with the key before differs from
  it after, on either cell.
- **P125.** fmt's minted extents: `holds-a-definition` **19 → 13**, read
  1,346 → 1,352. Symbols newly minted on a line a refused symbol
  vacated: recorded, not predicted (the mint's own refusals decide; 0 to
  3 expected).
- **P126.** args, cJSON and sqlite-vector: no symbol added or removed, no
  edge differs; a C++ symbol gains its name column and nothing else. A
  non-C clone (click) is byte-identical but for the version stamp.
- **P127 (direction only).** On fmt one test's reach shrinks
  (`gtest_extra_test.expect_throw_no_unreachable_code_warning`, to its
  own body's) and no other test loses a symbol; the one `implements` row
  out of a refused symbol is recorded, not predicted.

**Results (2026-09-18; unit `c2cc`, the branch's code before the merge;
`~/.hobbes/bench/c164-wrong-callers/regrade.sh`, `regrade/`).** Before is
each clone's graph at 0.2.46-beta's code; after is the same clone
ingested by the branch.

- **P121 — met.** fmt 7,012/7,012, 0 contradicted, strict 99.62%, 30.4%;
  args 2,567/2,567, 72.9%; cJSON 1,188/1,188; sqlite-vector 851/851.
  Every export row-identical (removed 0, added 0); poison passes on
  each, both arms.
- **P122 — met exactly.** fmt 18 refused (13 `macro`, 5 `term`), 1
  extent re-read (292 → 210), none refused or kept; the block is absent
  on args, cJSON, sqlite-vector and click.
- **P123 — wrong-caller met exactly (105 → 32); agree and lost each
  missed by one row beyond ± 2:** agree 7,628 (7,625 ± 2), lost 243
  (246 ± 2). With the misnamed symbol gone the mint named two true
  definitions on the vacated lines, which the simulation did not model;
  they carry 3 rows. 18 wrong rows now right, 55 lost. args unmoved.
- **P124 — met.** No row bad after that was not bad before, either cell.
- **P125 — `holds-a-definition` met (19 → 13); read 1,354, not 1,352** —
  the two new mints (`FunctionMocker::~FunctionMocker`, gmock.h:9705;
  `basic_scan_arg::basic_scan_arg~b10`, scan.h:292), each with a brace
  extent. Recorded as predicted-to-be-recorded: 2, inside 0 to 3.
- **P126 — met.** args: 566 symbols differ, each in `name_col` alone; no
  id gone or new, no edge differs. cJSON, sqlite-vector: no symbol
  differs. click identical but the stamp.
- **P127 — met.** One test lost symbols —
  `gtest_extra_test.expect_throw_no_unreachable_code_warning`, three
  (`basic_format_arg::visit`, `data`, `detail::to_unsigned`), reach
  pairs 6,131 → 6,101 — and none other. The `implements` row was
  re-placed (1 removed, 1 added). 393 evidence rows changed `from`: 317
  the swallowed tests' (to the module), the rest R1's.

### 10.21 The mint at a line R1 vacated — written 2026-09-18, before the unit is dispatched

ADR-136, route (a). **Not a grade**, for §10.19's reason, and on the
graded cells not even a change: R1 removes nothing in a clean file on
any of them. The numbers are `~/.hobbes/bench/scummvm-scale/vacated.py`'s,
which walked the mint's refusals other than `clean-file` at each
vacated line but did not run the extent's second pass.

- **P128.** fmt, args, cJSON, sqlite-vector: every graded number ±0, the
  export row-identical, and the graph identical but for the version
  stamp and `minted.vacated`, which reads 0 symbols in 0 files on each
  (fmt's 18 removals are all in lossy files). click byte-identical but
  for the stamp.
- **P129.** ScummVM (`c54b79a6`, warm caches): `minted.vacated` reads
  **260 symbols in 19 files**; `minted.symbols` 4,510 → **4,770**;
  `clean-file` 185,538 → **185,278**; `lane_a_contradicted` unchanged
  (401 refused, 2 extents read, 7,548 facts re-scoped). No other mint
  refusal count moves.
- **P130.** Extents read 3,084 → **3,329 ± 8** (the lossy half's rate,
  131 of 137); `rehomed` rises from 49,207 (direction only).
- **P131.** No symbol of the before graph is absent after, and no symbol
  edge of the before graph is absent after; edges are only added (calls
  into the 260, and calls out of their bodies).
- **P132.** A sample of 30 of the 260, drawn by a fixed stride over the
  sorted list, read against the source: each minted qualname is the
  function the source defines on that line. One wrong name fails it.
- **P133.** The second ScummVM ingest is byte-identical to the first.

**Results (2026-09-18; unit `e78d`, the branch's code before the merge;
`~/.hobbes/bench/c164-wrong-callers/regrade.sh` with
`OUT=~/.hobbes/bench/scummvm-scale/regrade`, and ScummVM's ingests
beside it).**

- **P128 — met.** fmt 7,012/7,012, strict 99.62%, 30.4%; args
  2,567/2,567, 72.9%; cJSON 1,188/1,188; sqlite-vector 851/851; every
  export row-identical, no symbol, edge, evidence row or test reach
  differing, poison passing on both arms; `minted.vacated` 0 and 0 on
  each. click identical.
- **P129 — met exactly.** 260 symbols in 19 files; `minted.symbols`
  4,770; `clean-file` 185,278; `lane_a_contradicted` unchanged; no other
  refusal count moved.
- **P130 — missed by two.** Extents read **3,339**, not 3,329 ± 8: 255
  of the 260 took a brace extent (the other 5 `conditional-inside`,
  103 → 108), a better rate than the lossy half's 131 of 137 the
  prediction borrowed. `rehomed` 49,207 → 51,981.
- **P131 — met for symbols, and missed as written for edges.** No symbol
  gone, 260 new. **289 symbol edges of the before graph are absent** —
  the prediction forgot that a re-homed fact changes its edge's `from`:
  278 ran from a module and 11 from the class enclosing an in-class
  generator macro (`EffectDisplayPrototype`), and each one's evidence is
  now under the minted definition written around it. At the evidence
  level nothing left: 1,901,620 rows → 1,902,209, **gone 0**, new 589.
  1,639 symbol edges added (1,200 `uses`, 439 `calls`): 1,123 out of a
  new symbol, 520 into one, none touching neither. Module edges
  unmoved.
- **P132 — met.** 30 of 30 (`sample.py`, stride 8 over the sorted 260):
  `DECLARE_COMMAND_OPCODE(drop)` is
  `Parallaction::CommandExec_br::cmdOp_drop`, `APPFUNCV(AutoMap::
  cmdAutoMapHome)` is `Saga2::AutoMap::cmdAutoMapHome`,
  `SPECIALSPELL(DeathSpell)` is `Saga2::DeathSpell`, `void strlib_open()`
  under `#define strlib_open lua_strlibopen` is `Grim::lua_strlibopen`.
- **P133 — met.** Byte-identical.

### 10.22 JavaScript — written 2026-09-19, before any JavaScript cell is ingested or graded (ADR-140 step 4)

JavaScript has no graded edge (C-165): every TS/JS cell was a TypeScript
program. ADR-140 step 3 gave the TS oracle `--no-tsconfig` (unit `a25f`),
and H-33's fix (unit `9e00`) made a call through a parameter read
`func-value→parameter`. Nothing below has been ingested.

**Priors.**
- `minijs` (the oracle's fixture): tsc resolves every CommonJS shape —
  `exports.double = function`, `Counter.prototype.inc = function`, the
  destructured `require` — and `new Greeter()` of a class with no
  declared constructor is silent.
- Hobbes on a scratch copy of `minijs` (0.2.53-beta, read by hand, not
  graded): 7 `calls` edges, all semantic, each to the declaration tsc
  names. Nothing is drawn for `math.double(2)`, `c.inc()` or `new
  Counter(1)`: a function assigned to a property (`exports.x =`,
  `X.prototype.y =`) is not a lane A symbol, so a call into it is below
  the floor (C-9, C-58), and a call written inside such a function is
  attributed to the module.
- The shape counts (regex over non-test sources, a rough read): Express
  defines about 81 of its ~153 library functions as `x.y = function`;
  Preact and xmpp.js define theirs mostly as declarations and class
  members (15 and 4 property-assigned).
- **`jsconfig.json` is read by neither lane** (both key zones on
  `tsconfig.json`). Measured on Preact's zone-less files, key only
  (`~/.hobbes/bench/js-cells/jsconfig-probe/`): of 22,804 call sites,
  22,682 resolve to the same in-repo targets under the ingest's generated
  options and under Preact's `jsconfig.json` (which maps `preact` onto
  the repo); 59 resolve only under the generated options, 17 only under
  the jsconfig, 9 to different targets, and 35 exist in one program only.

**The cells.** Each is graded against the program the ingest built for
it, with the environment lane B had.

| Cell | Repo @ sha | Why | Oracle's program | Environment (both sides) |
|---|---|---|---|---|
| O3-JS-1 | `expressjs/express` @ `9a34acf03cb8` | named: a CommonJS Node library (141 `.js`, no config of any kind) | `--no-tsconfig`, zone `.` | no lockfile: nothing provisioned (C-23) |
| O3-JS-2 | `preactjs/preact` @ `8101ff821690` | named: ESM with JSDoc types and JSX, a `jsconfig.json` with `paths` | `--no-tsconfig` over the ingest's root zone — the tree without `demo/`, `test/ts/` and `compat/test/ts/`, the three `tsconfig.json` zones, which the flag refuses; Hobbes edges there read `silent`/`not-loaded` | pnpm: nothing provisioned (C-23) |
| O3-JS-3 | `xmppjs/xmpp.js` @ `9cce6c14a7f1` | **the draw** (`~/.hobbes/bench/js-cells/DRAW-RULE.md`, written before it: `language:javascript stars:300..3000 pushed:>2026-03-01`, shuffled with `random.Random(20260919)`; five passed over, each with its reason in `draw-log.md`) — an ESM npm-workspaces monorepo, 171 files | `--no-tsconfig`, zone `.` | `package-lock.json`: the tree the ingest provisions, mounted for the oracle too |

| # | Cell | Prediction | Grading rule |
|---|---|---|---|
| P134 | every JS cell | precision-against-oracle **100%**, 0 hobbes-wrong, with its strict companion (ADR-124) stated | met after match-defect triage |
| P135 | every JS cell | any contradiction, if one appears, is on the syntactic tier (lane A's fallback where lane B is silent) | met if the tier split says so; undecidable at 0 contradictions |
| P136 | O3-JS-1 (Express) | recall over in-repo pairs **≤ 35%**, and the largest miss class is a call into a function assigned to a property — the oracle's `static→anonymous-function` | met if both hold |
| P137 | O3-JS-2, O3-JS-3 | recall over in-repo pairs **≥ 45%** (the TS cells' band, 45–72%) | met per cell |
| P138 | O3-JS-3 (xmpp.js) | a call across workspace packages (`@xmpp/*`) is resolved in both programs or in neither; the grade names which | recorded; a one-sided resolution is a finding |
| P139 | `minijs` | graded against a contained ingest of the fixture: 7 confirmed, 0 contradicted; recall 7 of 11 in-repo pairs; the misses `new Counter`, `c.inc()`, `math.double(2)` and `f("a")` (`func-value→parameter`) | met if the grade says exactly so |
| P140 | every JS cell | poison check PASS, 0 falsely confirmed | met per cell |
| P141 | the JS lane | at least one defect of the oracle-at-another-grain class is found in the first triage before any number is quoted (P14's habit; H-33 was found before this section, by the fixture) | recorded regardless |
| P142 | O3-JS-2 (Preact) | graded under the generated program only; the jsconfig difference above is stated beside the cell, never mixed into its numbers | met if the cell record keeps them apart |

**Results, final (2026-09-19, after H-34 and H-35's fix; merged
`d715849`; regraded contained with no re-ingest,
`~/.hobbes/bench/js-cells/regrade/h34/`).**

| Cell | Precision | Strict | Recall (in-repo) | Poison |
|---|---|---|---|---|
| `minijs` | 7/7 | 100% | 63.6% (7/11) | PASS |
| O3-JS-1 Express | **340/340** | 100% | 22.4% (340/1,520) | PASS, 0 falsely confirmed |
| O3-JS-2 Preact | **2,446/2,446** | 100% | 28.6% (2,632/9,211) | PASS (2,206 refused, 528 unjudged) |
| O3-JS-3 xmpp.js | **552/552** | 100% | 66.4% (558/840) | PASS |

- **P134 — met** on every cell: 100%, 0 hobbes-wrong; no strict gap
  (no line-unresolved row). **P135 — undecidable** (0 contradictions).
- **P136 — half-met** (Express): recall ≤ 35% held; the largest miss
  class is not property-assigned functions but one CommonJS re-export
  (652 of 1,180), registered as C-167.
- **P137 — met on xmpp.js (66.4%), missed on Preact (28.6%).** About
  6,300 of Preact's 6,579 misses sit in test files: in-body closures
  (`static→closure` 2,028), calls through the interface members its own
  `.d.ts` declares (`interface→type-member` 1,792, in-repo pairs only
  since H-34), hook setters in locals (`func-value→local-binding`
  1,557) and constructions (`static→class` 570, C-168).
- **P138 — met ("neither").** **P139 — met exactly.** **P140 — met.**
  **P141 — met**: H-34 and H-35 in Preact's first triage (and H-33
  before this section). **P142 — met**: the jsconfig difference is
  stated beside the cell (C-166), not in its numbers.
- The TS cells re-run with the same fix: kbet, ajv, cheerio, zod and
  hono row-identical; hono's in-repo pairs 1,403 → 1,408.
- **The cells are not yet in `docs/oracle/cells/`**, so the comparative
  graphics (ADR-102) do not include them; adding them is the lead's
  call.

**Regrade, 0.2.56-beta (ADR-141, C-167 narrowed; 2026-09-19).** Lane A
follows `module.exports = require("<literal>")` to the required module's
export; Express re-ingested contained at `c1d25fa` and graded against the
standing key (`js-cells/regrade/h34/express/oracle.json`): **992/992,
strict 100%, recall 65.3% (992/1,520)**, poison PASS — 289 semantic and
703 syntactic, the 652 new rows all syntactic (scip-typescript names
those sites with a leaked document-local, C-167's `Provider` line);
every earlier confirmed row kept. Pre-registered as ADR-141's probe
(`~/.hobbes/bench/c167-reexport/PREREG.md`, P1–P4 met): Preact, xmpp.js
and `minijs` row-identical on copies. P136's largest class is closed;
Express's misses are now calls through parameters (352 of 528).

**What the row rests on.** The JavaScript row of §3.8 names only the
cells graded here. A mechanism triage charges to Hobbes on the semantic
tier is registered in the same commit as its cell; whether it is fixed
before the row lands is the lead's call. Ignoring `jsconfig.json` is a
concession whichever way the cells come out: it is to be registered, and
whether the lanes should read it is a separate decision.

**Results, first pass (2026-09-19, 0.2.54-beta; every ingest with lane B
contained, the oracle in the image with no network; drivers and reports
`~/.hobbes/bench/js-cells/` — `grade.sh`, `cells/<cell>/`).** No cell
had a dependency tree on either side: Express has no lockfile, Preact's
is pnpm's, and xmpp.js's `npm ci` refused its own lockfile (out of sync
with `package.json` — the ingest said so, C-23).

- **P139 — met exactly.** `minijs`: 7/7 confirmed, 0 contradicted, recall
  7/11, the four predicted misses; poison PASS.
- **O3-JS-1 Express:** **340/340 (100%)**, 289 semantic and 51 syntactic,
  0 contradicted; poison PASS (198 refused, 142 unjudged); recall 22.4%
  (340/1,520). **P136 half-met:** recall ≤ 35% held, the class did not —
  the largest miss class is `static→function` (657), and **652 of those
  are one callee**: the tests' `express()`, which tsc resolves through
  `require('../')` → `index.js`'s `module.exports =
  require('./lib/express')` → `createApplication`. Hobbes draws nothing
  at those sites (3 `uses` and 2 syntactic `calls` reach
  `createApplication` in the whole graph); why lane B stops there is not
  yet traced. Property-assigned functions miss 46 (`static→anonymous-function`).
  `func-value→parameter` 352 (mocha's `done()` callbacks).
- **O3-JS-3 xmpp.js (the draw):** **552/552 (100%)**, 0 contradicted;
  poison PASS (361 refused, 191 unjudged); recall **66.4%** (558/840) —
  **P137 met.** `static→class` 104: `new X()` is drawn as `uses`, as in
  TS. **P138 met ("neither"):** without the workspace links no import of
  `@xmpp/*` resolves in either program — 0 cross-package pairs, 0 edges.
- **O3-JS-2 Preact: not quoted — two oracle defects found in its first
  triage (P141 met).** The first pass read 1,201 confirmed and 1,223
  contradicted. **1,220** are H-34 (the oracle keys an in-repo `.d.ts`
  declaration as external with an absolute path; Hobbes' edge names the
  same line of the same file) and **3** are H-35 (a JSDoc `@type` on a
  function makes the key name the type annotation's line). No row is
  charged to Hobbes. Poison PASS (2,206 refused, 0 falsely confirmed).
  Preact is regraded after both are fixed; P134–P137 and P142 for it
  wait on that.
- **P134 so far:** met on Express, xmpp.js and `minijs`. **P135:**
  undecidable there (0 contradictions). **P140:** met on every cell.
- **C-166 fires where it should:** Preact's ingest prints its
  `jsconfig.json` as not read, 241 files under the default options.
- **Two recall findings for Hobbes, registered and since closed:** a
  function reached through a CommonJS re-export of `module.exports` drew
  nothing (Express's 652 — C-167, drawn at 0.2.56-beta, ADR-141); a
  construction drew no call (C-168 — drawn at 0.2.57-beta, ADR-142, §10.23).
  The second entry's *shape* was wrong as first written, and §10.23 says how.

### 10.23 Constructions in TypeScript and JavaScript — written 2026-09-20, before any cell was re-ingested (ADR-142, C-168; unit `b444`)

**Pre-registered** in `~/.hobbes/bench/c168-construction/PREREG.md` before
any simulated export was graded; `RESULTS.md` beside it carries the run.

**Step 0, the misses by shape.** C-168's numbers were each cell's whole
`static→class` miss class, not the constructions in it. Read row by row:
xmpp.js 102 `new` + 2 `super`; **Preact 0 `new`** — 193 `super(…)` and 383
JSX tags (6 drawn); ajv 95 + 12; zod 101 + 9 dotted; hono 74 + 4; cheerio 5;
kbet 8 JSX, all 8 drawn; Express 0.

**What each lane says at a `new` token.** The index names `<constructor>`
at the constructor's own declaration line — inside the class the key names,
every time (xmpp.js 101/102, ajv 89/95, hono 67/74). Where the class
declares **none** it names the class itself while the key names the **base**
whose constructor runs (ajv 6, hono 5, zod 43). An ES5 constructor function
it names directly (Express 6, xmpp.js 23). Nothing at all: cheerio's 5,
`new this(…)`.

**The naive rule was refused on the evidence:** promoting today's `uses`
edges at a `new` would have drawn 3 confirmed and **55 contradicted**.

**The rule, simulated then built** (P1–P8; P7 missed on zod's count, +33
against +58 ± 8, because 719 of its 946 tokens carry no resolution at all —
its precision half held). The real cells at 0.2.57-beta, stored keys,
`-poison`:

| cell | before | after | recall | `ts_drawn` / `ts_named_class` |
|---|---|---|---|---|
| xmpp.js | 552/552 | **676/676** | 66.4% → **81.2%** | 124 / 21 |
| ajv | 1,410/1,410 | **1,499/1,499** | 63.5% → 67.5% | 319 / 6 |
| hono | 768/768 | **833/833** | 55.0% → 59.7% | 996 / 50 |
| zod | 9,731/9,731 | **9,872/9,872** | 45.1% → 45.8% | 142 / 192 |
| Express | 992/992 | **998/998** | 65.3% → 65.7% | 75 / 0 |
| Preact | 2,446/2,446 | **2,447/2,447** | 28.6% | 5 / 1 |
| cheerio | 2,628/2,628 | 2,628/2,628 | 45.1% | — |
| `minijs` | 7/7 | **8/8** | 63.6% → 72.7% | 1 / 1 |

**100% precision, 0 contradicted and poison PASS on every cell.** The
`static→class` miss class falls xmpp.js 104 → 3, ajv 107 → 18, hono 78 → 13,
zod 110 → 77; Preact's 570 do not move, which is what step 0 predicted.

### 10.24 A JavaScript cell with its dependency tree — written 2026-09-20, before the draw was walked (C-165)

**Pre-registered** in `~/.hobbes/bench/js-cells/c165/DRAW-RULE.md` before
any repo was cloned; `RESULTS.md` beside it carries the run.

**The draw.** §10.22's pool and order, resumed at position 7, with two
criteria added: a lockfile `detect_installer` provisions from
(`package-lock.json` or a v1 `yarn.lock`), and a non-empty `dependencies`.
A candidate whose install the ingest refuses is recorded and the next
taken. Walked 7–21: **9 hack-chat/main refused** (`uwuify-1.0.1.tgz` is
404 on the registry), **11 maptiler/tileserver-gl refused** (lockfile out
of sync with its manifest — xmpp.js's case), **21 cypress-io/github-action
taken** at `01e3b659a495` (77 JavaScript files, one zone, 177 packages).

**Stated first:** the cell is graded twice on one sha — *provisioned* (the
ingest's tree on both sides) and *withheld* (no lockfile, no tree on
either side) — and the arms are read beside each other. Known before the
run from cheerio, zod and hono: Hobbes exports no call edge whose target
is under `node_modules`, so no graded row can target a package; if the
provisioned rows are all in-repo, C-165's wording is past what any cell
can show and the entry is corrected, not only lifted.

| arm | rows | confirmed | contradicted | abstract | silent | recall (in-repo) | external oracle pairs | poison |
|---|---|---|---|---|---|---|---|---|
| provisioned | 154 | 154 | 0 | 0 | 0 | 89.0% (154/173) | 413 | PASS (148 refused, 6 unjudged) |
| withheld | 154 | 154 | 0 | 0 | 0 | 89.0% (154/173) | 173 | PASS (146 refused, 8 unjudged) |

**Read.** 100% precision, strict 100% (nothing abstract or silent), on
both arms; the rows are identical and so is the graph. The tree moved the
key's external pairs (+240) and `dependency_coverage` (0 → 14 of 22), and
no Hobbes edge: the 77 `imports → ext:<pkg>` module edges are the same in
both arms and no symbol edge targets a package. The prediction held, so
C-165 is corrected to the limit it is — a third-party call is stated at
module grain and no key grades it — and narrowed: one JavaScript cell of
four has met its tree. The cell is thin (76 `calls` edges at 154 sites)
and is recorded as thin. Counted beside it: `npm ci` refused three of the
four lockfile-bearing JavaScript repos the two draws met (C-23). Record:
`docs/oracle/cells/github-action-js-2026-09-20.md`.

### 10.25 A renamed callee matched at its own column — written 2026-09-20, before any cell was re-ingested (ADR-143)

**Pre-registered** in `~/.hobbes/bench/adr141-name-mismatch/` (`PREREG.md`
the count, `PREREG-sim.md` the rule) before any graded export; `RESULTS.md`
carries the count. The counter had to reproduce ADR-141's JavaScript counts
before a TypeScript number was read, and did once the match was by site and
target (the lanes name different callers at some sites).

**The count** (graphs of the 0.2.57-beta regrade): Express 2, Preact 5,
xmpp.js 41, ajv 5, cheerio 8, zod 0, hono 75 — 136 sites, 98 confirmed, 38
`not-loaded`, 0 contradicted. **The probe** (xmpp.js, hono): a resolution
onto lane A's own target sits at exactly the site's column 38 and 76 times,
5 columns off 4 times, and a resolution at the site's column never names
another definition.

**The rule, simulated then built** (P1–P5, all held), then each cell
re-ingested contained with the unit's code, stored keys, `-poison`:

| cell | tiers raised | rows | confirmed | semantic confirmed | syntactic confirmed | contradicted |
|---|---|---|---|---|---|---|
| xmpp.js | 38 | 676 → 676 | 676 → 676 | 624 → 662 | 52 → 14 | 0 |
| hono | 76 | 5,420 → 5,420 | 833 → 833 | 792 → 833 | 41 → 0 | 0 |
| ajv | 5 | 1,664 → 1,664 | 1,499 → 1,499 | 1,497 → 1,499 | 2 → 0 | 0 |
| cheerio | 8 | 2,688 → 2,688 | 2,628 → 2,628 | 2,620 → 2,628 | 8 → 0 | 0 |
| Express | 2 | 998 → 998 | 998 → 998 | 295 → 297 | 703 → 701 | 0 |
| Preact | 5 | 2,738 → 2,738 | 2,447 → 2,447 | 2,442 → 2,447 | 5 → 0 | 0 |
| zod | 0 | 9,921 → 9,921 | 9,872 → 9,872 | 8,815 | 1,057 | 0 |

Direction of the fix, signed: precision **0**, recall **0**, confirmed rows
**0** on every cell; tier `syntactic → semantic` **+134** rows in all (hono's
76 include 35 outside its graded zone). Poison PASS on every cell. Each
built export is row-identical, tiers included, to its simulation. **The
other languages** — cJSON, click, jsoup, memchr, fzf, fmt, args — ingested by
`main` and then by the unit: row-identical, no tier moved (the rule needs a
fallback and a resolution at one column naming one definition; none of those
cells holds the shape). The remainder is xmpp.js's 3 `time.date()` sites: the
occurrence at the callee's column is absent and the namespace's is 5 columns
away, so the rule declines, as it should.

### 10.26 C-168's remainder: `super(…)` and class-component JSX tags — a read, 2026-09-20; nothing drawn, nothing regraded

**The predictions were written first** (`~/.hobbes/bench/c168-remainder/PREREG.md`);
the graphs are the 0.2.59-beta code's, the keys the standing ones, the facts the
cells' cached streams (zod's an older rebased one — indicative).

**What the index says** (a fixture indexed in the image, `mini/`): scip-typescript
emits **no occurrence at a `super` token**, and at a JSX tag it names the
**class**, never `<constructor>`, whether the class declares one or not. So
ADR-142's condition — the index names the constructor at the token — can hold at
neither.

**Preact's 570 `static→class` rows are one target**, `src/index.d.ts:144`,
`abstract class Component`, which declares a constructor and is a Hobbes symbol
(1,241 of the cell's confirmed rows land in `.d.ts` symbols). The 193 `super`
rows: at `extends Component` the index names line **119**, the merged
`interface Component`, and the subclass is a test-body local. The 377 JSX rows:
the tag names such a local, and the facts carry no reference for one — lane B
names nothing at the token.

**A rule measured and not built — the walk.** From a `new` callee, or for
`super(…)` the enclosing class's `extends` token, take the index's reference at
the token's own column; a class that declares a constructor is the target; one
that declares none hops to its own `extends` token; an unresolved hop, a
non-class or a class with no base draws nothing.

| cell | `new` at a class with no own constructor | `super(…)` | contradicted |
|---|---|---|---|
| ajv | 6 (one or two hops) | 12 (6 direct, 6 by hops) | 0 |
| hono | 5 of 50 refused today | 3 | 0 |
| xmpp.js | 0 of 21 (every chain ends at an external `EventEmitter`) | 2 | 0 |
| zod | 76 of 192 | 0 | 0 |
| Preact | 0 | 0 — 193 only if a merged interface+class of one name is read as the class | 0 |

Every row the key judges is confirmed (P1, P2, P4 met). **P3 missed:** at least
80% of the `ts_named_class` refusals were predicted to walk to a confirmed row;
hono reads 5 of 50 and xmpp.js 0 of 21, because most chains end at an external
base or at a class with an implicit constructor, where the key names nothing
either. 107 of zod's `new` tokens name two definitions (v4's `interface X` beside
`const X = $constructor(…)`) and are refused. Max: route a — the entry corrected,
the walk not built. Drivers: `~/.hobbes/bench/c168-remainder/` (`classes.mjs`,
`walk.py` with `--merge` and `FACTS=`, `super_facts.py`, `laneb_at.py`, `mini/`,
`RESULTS.md`).

### 10.27 A larger JavaScript cell with its dependency tree — written 2026-09-20, before the draw was resumed (C-165)

**Pre-registered** in `~/.hobbes/bench/js-cells/c165/DRAW-RULE-2.md` before any
candidate past position 21 was seen; `RESULTS-2.md` beside it carries the run.
§10.24's cell was thin (76 `calls` edges), so one criterion was added and fixed
first: a candidate the ingest provisions is taken only if its graph holds **at
least 300 `calls` edges** and **at least half its declared packages resolve**.
Stop at position 80. **Predicted:** the two arms' Hobbes rows identical; the tree
moves only the key's external pairs and the dependency coverage.

**The draw.** Walked 22–41: **22 brunosimon/folio-2025 refused** (`npm ci`:
ERESOLVE); **26 lirantal/npq** provisioned and passed over (382 `calls`, 6 of 19
packages resolved); **36 Kong/insomnia-mockbin** provisioned and passed over (20
`calls`); **41 Blueturboguy07/cue taken** at `a27308ed2335` — 77 JavaScript
files, one zone, 478 `calls` edges, 7 of 12 packages resolved, 276 packages
installed. Hobbes 0.2.60-beta.

| arm | Hobbes rows | confirmed | contradicted | recall (in-repo) | external oracle pairs | poison |
|---|---|---|---|---|---|---|
| provisioned (tree on both sides) | 881 | 881 | 0 | 54.3% (892/1,644) | 5,198 | PASS — 863 refused, 18 unjudged, 0 confirmed |
| withheld (same sha, lockfile removed) | 881 | 881 | 0 | 54.2% (892/1,647) | 1,620 | PASS — 718 refused, 163 unjudged, 0 confirmed |

**The prediction held.** The 881 rows are identical by site, target, caller and
tier (all semantic), the graph is identical, and no row targets `node_modules`.
The tree moved `dependency_coverage` 0 → 7 of 12, the ingest's errors 4 → 2, and
the poison check's unjudged seeds 163 → 18: it sharpens the key, not the graph.
**Three key pairs differ, read one by one, none a Hobbes row:** two `toFile(…)`
calls bound from `OpenAI.toFile || require('openai/uploads').toFile`, and
`publik.newInstallId()` where `newInstallId: randomUUID` — with the tree the key
names the package's function, without it an in-repo binding; Hobbes draws
nothing at any of the three in either arm. That is C-165 as corrected, now on a
cell of a size to say it. Counted under C-23: `npm ci` has refused four of the
eight lockfile-bearing JavaScript candidates the two walks met.

**Seen, not traced:** 176 of the cell's 752 misses are one shape — a call through
`const m = require('../src/m')` to a member of `module.exports = { a, b, c() {…} }`
(674 of the 801 function pairs *are* drawn, so the shape is met and not always).
A recall read for a later session. Record: `cells/cue-js-2026-09-20.md`.

### 10.28 A shorthand property names what it names — written 2026-09-20, before any cell was re-ingested (ADR-144; unit `12ad`)

**Step 0** (`~/.hobbes/bench/cjs-namespace/`, `RESULTS.md`): §10.27's 176 untraced
misses on cue. 122 are `m.f()` on `const m = require('./m')` over `module.exports
= { f }`; what separates them from the drawn `const { f } = require(…); f()` is the
binding. At the member token scip-typescript names the exported literal's
**property** (`` src/`publik.js`/loadBuildConfig0: ``), a `meta` symbol the helper
kept no definition for, so the site was an in-repo `external_ref` and the function
got no reference. Modelled as the rule fires, unfiltered by the key: cue 124 and
xmpp.js 29 (`export default { … }`), all confirmed.

**The index, read raw in the image (`mini/`):** the literals are told apart
(`alpha0:` / `alpha1:`), and the property's one definition occurrence shares its
**exact range** with a reference to the function. A value property's reference is
at another range; a literal's method is a `local`.

**Simulated first** (`PREREG-sim.md`; a scratch worktree's helper, never merged),
then **regraded with the unit's code — every cell row-identical to its
simulation, tiers included:**

| cell | rows | added | contradicted | lost / re-tiered | recall |
|---|---|---|---|---|---|
| cue | 881 → 1,005 | 124 confirmed, `semantic` | 0 | 0 / 0 | 54.3% → **61.8%** (1,016/1,644) |
| xmpp.js | 676 → 705 | 29 confirmed, `semantic` | 0 | 0 / 0 | 81.2% → **84.6%** (711/840) |
| Express, github-action, Preact, ajv, cheerio, hono, zod | unchanged | 0 | 0 | 0 / 0 | unchanged |

Poison PASS on all nine. P1–P4 and P6 met. **P5 was wrong about where:** the new
`uses` edges (cue 114, github-action 2) sit at the *destructuring* `require` line,
whose pattern names the same properties — what an ESM import line already draws —
not at a value passed. Other languages (`lang-regrade.sh`, pre/post, the index
re-run: cache 0 hit): cJSON, click, jsoup, memchr, fzf, fmt, args **row-identical,
no tier moved**. Left: a value property (`delta: alpha`), refused and unmeasured;
a member written in a literal, no symbol (C-9/C-58; cue 49).

### 10.29 A call on the value a fixture constructs — `PREREG.md` written 2026-09-20 before the first simulation; this section written after the regrade (ADR-145; unit `1527`)

**Step 0** (`~/.hobbes/bench/c4-returned-value/`, `RESULTS.md`): of click's 665 missed
`observed→method` pairs, 419 sit at `p.m(…)` on a parameter in a test file and 381 are
`runner.*`. The index names the *parameter* at `runner`, emits nothing at `invoke`, and
names `CliRunner` at the fixture's `return CliRunner()` — a `semantic` edge the graph
already carries.

**Simulated first** (`simulate_real.py`: the fixture from ADR-137's own `injections`, the
class from the cell's cached index facts; in memory): click 383 drawn, **381 confirmed, 0
contradicted**, 2 on lines the key never ran; flask (held out, no trace key) 11 drawn,
read by hand, 11 right, 702 refused as not a construction; attrs and this repo 0 drawn.
P1–P4 held.

**Regraded with the unit's code** (`lang-regrade.sh`, pre/post, stored keys, `-poison`):

| cell | rows | added | contradicted / suspect | lost / re-tiered | recall |
|---|---|---|---|---|---|
| click | 2,065 → 2,447 | 382 `syntactic`: 381 confirmed, 1 unobserved | 0 / 0 new | 0 / 0 | 38.2% → **46.5%** (2,136/4,595) |
| cJSON, jsoup, memchr, fzf, fmt, args | unchanged | 0 | 0 | 0 / 0 | unchanged |

Poison PASS on all seven. The build draws one site fewer than the simulation: a
`runner.invoke` written inside a nested `def` of a click test (never run), which the rule
refuses and the probe's walk entered — the probe's defect, the build's refusal. A trace
key's confirmation rate is not a precision (§4): what it says here is that 381 of the 382
sites ran and every one that ran reached the drawn target. The rule mints no symbol.
Left in C-4: a fixture value that is not a construction, an inherited method.

### 10.30 A decorator is a call of what it names — `PREREG.md` written 2026-09-20 before the first count; this section written after the regrade (ADR-146; unit `f751`)

**Step 0** (`~/.hobbes/bench/py-nested-defs/`, `RESULTS.md`) set out to size Python's
nested defs as symbols and found they already are: a direct call to one is drawn
`semantic`. What the rows were instead: **0 of click's 2,447 edges sat on a decorator
line and 1,652 of its 2,459 missed pairs did** — lane A's walk skipped decorator
expressions, in no register entry (C-169). Of this repo's 642 closure misses, 590 are
`<genexpr>` frames: the interpreter's grain, not a call anyone wrote.

**Simulated first** on a scratch worktree (the walk alone, then the bare application),
then **regraded with the unit's code** on `main` (stored key `click-py-r2`, `-poison`):

| click | rows | confirmed / 4,595 | suspect | lane sites compared / disagreements |
|---|---|---|---|---|
| 0.2.64-beta | 2,447 | 2,136 (46.5%) | 18 | 830 / 2 |
| simulated, call-form decorators walked | 3,463 | 2,995 (65.2%) | 18 | 859 / 2 |
| simulated, + a bare decorator applied | 3,533 | 3,052 (66.4%) | 18 | 872 / 2 |
| **0.2.65-beta, built** | **3,533** | **3,052 (66.4%)** | **18, the same rows** | 872 / 2, the same two |

The built export is row-identical to the simulation's; 0 rows of 0.2.64-beta's lost;
poison PASS, 0 falsely confirmed. By class: `observed→function` 750 → 15 missed,
`observed→class` 149 → 37, `observed→method` 284 → 215; `observed→closure` 1,195
unmoved — 728 of them the factory's inner def, which this rule does not claim. Held out,
no trace key: flask 1,055 → 1,221 rows and attrs 1,637 → 1,757, every added row
`semantic`, none lost, no symbol, node or module edge moved. Signed direction of fix:
confirmed **+916**, suspect **±0**, rows lost **0**. A trace key's confirmation is not a
precision (§4): 1,086 rows were added, 916 ran and reached the drawn target, 170 sit on
lines the key never ran. Other languages were not regraded: the change is lane A's
Python walk alone. The review also fixed a digest defect the unit had copied (a trailing
comment read as the decorator's expression); no graded row moved on it.

### 10.31 A decorator factory's application — `PREREG-b.md` written 2026-09-20 before `probe_b.py`'s first run; this section written after the regrade (ADR-147; unit `db45`)

**Probed as worded** over the *built* 0.2.65-beta export (the join's real claim at the
decorator line, no stand-in): click 368 drawn, **304 confirmed, 0 contradicted**, 64 on
lines the key never ran; refused 491 (not every return one bare name — `command`,
`group`), 3 (factory decorated). flask 1 drawn, read by hand, right; 162 refused
(`Scaffold.route` under `@setupmethod`). attrs 0. P1–P3 held. The loose wording read 661
at 0 contradicted and was not taken (ADR-147: on `command`'s other path the site does not
call `decorator`).

**Regraded with the unit's code** on `main` (stored key `click-py-r2`, `-poison`):

| click | rows | confirmed / 4,595 | suspect | `observed→closure` |
|---|---|---|---|---|
| 0.2.65-beta | 3,533 | 3,052 (66.4%) | 18 | 32 / 1,227 |
| **0.2.66-beta** | **3,901** | **3,356 (73.0%)** | **18, the same rows** | **336 / 1,227** |

368 rows added, all `syntactic`, 0 lost, 0 re-tiered; poison PASS, 0 falsely confirmed.
Signed direction of fix: confirmed **+304**, suspect **±0**, rows lost **0**. The built
figures are the probe's exactly. A trace key's confirmation is not a precision (§4); what
it says is that every drawn site that ran reached the drawn def. Two factories carry 301
of the 304 rows (`option` 203, `argument` 98) — one repo's idiom, said plainly. The rule
mints no symbol. Other languages not regraded: Python only, after the projection. Left in
click's closure misses: 891 — a factory with another return path, a callback handed to a
runner, and 34 `<genexpr>` frames that are the key's grain (H-36, open).

### 10.32 H-36's regrade — a comprehension's frame entry is not a call (oracle side; 2026-09-20, unit `de0e`)

The defect and its fix are H-36's row in `oracle-defects.md`. The regrade isolates the
extractor: nothing about Hobbes differs between the arms.

| cell | method | in-repo pairs | confirmed | suspect | recall-against-executed | excluded `generated` (call events) |
|---|---|---|---|---|---|---|
| click @ `36baa15`, Hobbes 0.2.66-beta | key regenerated, same recipe and suite exits (`click-py-r2` → `click-py-r3`) | 4,595 → **4,561** (−34, every one `<genexpr>`) | 3,356 ±0 | 18 ±0 | 73.0% → **73.6%** | 26,090 |
| this repo `pipeline/` @ `2c915a8`, Hobbes 0.2.66-beta | one tree, one suite, traced by `oracle-pre` (`89b7f58`) and `oracle` | 9,535 → **8,612** (−923, every one `<genexpr>`; 0 added) | 8,162 ±0 | 26 ±0 | 85.6% → **94.8%** | 64,228 |
| codegraphcontext / repowise on click | stored converted graphs, both keys, one binary | as click | 1,298 ±0 / 1,703 ±0 | 146 ±0 / 406 ±0 | 28.2% → 28.5% / 37.1% → 37.3% | — |

Poison PASS on every arm. Signed direction of fix: **oracle-wrong 957 : hobbes-wrong 0**
on the moved rows; no confirmed, suspect or unobserved row moved anywhere. This repo's
cell is a fresh key (the 1c65190 clone is gone, §10's note), so its figures do not
continue the 0.1.10-beta row's — the pre arm is the like-for-like. What is left of its
450 misses: 195 functions (values in tables and records, C-58), 154 lambdas, 76 closures,
22 methods, 3 classes. The comparative tables and graphics were re-derived from the cell
records (`render.py cells`, `render`, `check`).

### 10.33 An optional-parentheses factory's guards, folded over the site's own arguments — `PREREG.md` written 2026-09-21 before `probe.py`'s first run; this section written after the regrade (ADR-148; unit `b4d4`)

**Probed as worded** over the built 0.2.66-beta export (`~/.hobbes/bench/py-optparens/`),
the new edges written into a copy of the export and graded by `oracle grade --poison` on
the standing key `click-py-r3`: 397 drawn (`command` 315, `Group.command` 75,
`Group.group` 7), **347 confirmed**, 47 on lines the key never ran, **3 suspect**; the
base regrade reproduced §10.32 exactly and no base row moved. The `method-positional`
refusal moved nothing (its 27 sites pass non-literal positionals, already `guard-unknown`).
attrs 18 drawn (`@attr.s(…)`, keyword-only; read by hand, right), flask 0 (decorated).
**P1 failed as pre-registered, and the 3 rows were read before anything was proposed:**
`tests/test_arguments.py:61`, `:614`, `tests/test_options.py:110` are `pytest.raises`
tests where the `@click.argument/option(…)` *below* `@click.command()` raises during its
own application, so `command()` ran (the key has it) and its `decorator` never did. The
edge is the code as written; the run never reached the application; a trace key buckets
it `suspect` (it cannot contradict). Max: route a, own the three rows (ADR-148).

**Regraded with the unit's code** (merged `78a2166`; click ingested from the unit's tree
with the review's fix, stored key `click-py-r3`, `--poison`):

| click | rows | confirmed / 4,561 | suspect | `observed→closure` |
|---|---|---|---|---|
| 0.2.66-beta | 3,901 | 3,356 (73.6%) | 18 | 336 / 1,195 |
| **0.2.67-beta** | **4,298** | **3,703 (81.2%)** | **21** (the 18, and the 3 read above) | **683 / 1,195** |

397 rows added, all `syntactic`, `via: decorator-factory-folded`, 0 lost, 0 re-tiered;
poison PASS (4,298 seeded, 0 falsely confirmed). Signed direction of fix: confirmed
**+347**, suspect **+3** (read, the code as written), rows lost **0**. **The built rows are
the probe's, row for row** (4,298 of 4,298 by site, target and bucket). The ingest's
block: 765 drawn, 397 folded; refused 67 `no-returned-def`, 27 `method-positional`,
3 `decorated`, 0 `guard-unknown`. Three factories carry every row — one repo's idiom,
said plainly; attrs' 18 are the second repo's. **Found at the review, before the
regrade:** the unit's first build folded nothing on click — a typed `*args: T` /
`**kwargs: T` is a `typed_parameter` wrapping the splat, read as an unnameable parameter,
and click annotates every factory; the unit's tests used untyped signatures. Fixed and
tested (`39815c0`). The rule mints no symbol. Other languages not regraded: Python only,
after the projection. Left in click's closure misses: 512 — callbacks reached through
attributes and parameters (values, C-58), `group()`'s `return command(…)`, a decorator
held in a variable, `make_pass_decorator` applied bare.

## 11. Evidence, claims, and register updates

- **A graph Hobbes did not build is graded by the same rules**
  (ADR-101): `oracle import` + `grade-foreign.sh`, one converter per
  tool under `bench/oracle/adapters/` with a hand-read fixture, the
  poison check run on the converted file, the cell record in the same
  format with the tool's own confidence labels as tiers and the
  untriaged contradiction count printed. The three comparative graphics
  are read from the cell records by `bench/oracle/report/render.py`
  and a drift test keeps them so (ADR-102).
- Rows land in `extraction-evidence.md`, same commit as the run, per the
  file's own rule. **A regrade after a fix carries a signed
  direction-of-fix line** in its cell record (README template): what
  the fix did to each headline number, before → after, signed — a
  resolved number with no stated direction is the shape a flattering
  patch takes.
- **Every cell runs the poison check** (`oracle grade --poison`): the
  Hobbes export is seeded with known-wrong edges (each confirmed edge
  re-targeted to another declaration the oracle never resolved that
  site to) and the report states how many the grader refused. The
  fixtures prove true edges confirm; this proves wrong ones do not — a
  matcher that falsely confirms is invisible to triage, which reads only
  the failure buckets. Oracle-graded is a **new kind of Verified content** —
  the line reads e.g. "compiler-graded: N edges, precision-against-oracle
  X%, recall Y% at R roots; not hand-checked beyond triage" or
  "trace-graded: recall-against-executed X% over E observed pairs at C%
  coverage". Never let an oracle row imply hand-verification, a trace row
  imply full recall, or vice versa.
- §3.8 gains rows only for what a run licenses (P11): per-cell,
  per-language, at the grain measured. An O4 result licenses a dagger-Go
  row, not a Go row; an O6 result licenses an executed-slice claim, not a
  repo claim.
- **Constraint candidates:** the four rules of §3, plus §3.1's
  trace-asymmetry rule (observed edges are facts; absence is never
  falsity) and the reference-lane rule (peer analyzers never produce a
  precision-against-oracle number). Register as `C-n` entries in the
  register's relevant segment (`docs/constraints/`) when the lane lands.
- ADR for the lane's existence and the D-O decisions below: ADR-089.
- **Follow-on, separate work:** upgrade the hand-grading protocol for what
  no oracle reaches — unexecuted Python/Rust paths, HCL — to
  stratified-by-resolution-strategy, seeded sampling with published
  per-row verdicts, n≥30 per cell. Not part of this build; noted so it
  isn't forgotten.

## 12. Decisions (pick before building)

Carried, with recommendations and status, in ADR-089.

- **D-O1 — Go algorithm.** RTA (recommended: the field-standard oracle
  choice, comparable to published numbers, fast enough to rerun) vs VTA
  (tighter oracle, stricter grading, slower) vs running both and reporting
  the band. Recommendation: RTA now, VTA as an optional second arm on O2
  only to measure how much the choice moves the number.
- **D-O2 — harness home.** `bench/oracle/` as its own module(s)
  (recommended: product stays pure, mirrors the product/evidence-repo
  separation) vs a `hobbes oracle` CLI subcommand.
- **D-O3 — dispatch and external scoring.** For a site where the oracle
  has multiple targets (interface dispatch): Hobbes' single target scores
  confirmed on set membership (recommended), and recall counts every
  oracle pair (which prices the dispatch ceiling honestly). External
  (`node_modules` / stdlib) targets: in or out of the recall denominator —
  recommended out for in-repo recall, with the external-confirmation rate
  reported separately.
- **D-O4 — position/overload conventions.** Write the declaration
  position rule and the overload rule (§5) into the harness README as
  normative; both product lanes get measured against them.
- **D-O5 — Python trace mechanics.** `sys.monitoring` at site grain
  (recommended) vs `python -m trace` at function grain vs adopting DynaPyt.
  Which suites: the repo's own tests (recommended — the environment Hobbes
  already provisions) vs authored drivers. Module-body calls in or out of
  the graded set.
- **D-O6 — Rust path.** MIR resolution oracle first (recommended: compiler
  authority, source grain, matches Hobbes' edge model) vs Rupta-first vs
  trace-first; whether Rupta ships as a reference lane in phase 2 at all
  or waits (recommended: time-box one setup attempt, drop without ceremony
  if the toolchain pin fights back).

## 13. Appendix — field-report tally

Field use ("no wrong edge encountered while using Hobbes as an edge tool")
becomes countable with a one-line log per incident, kept in
`extraction-evidence.md` under its own section: date, repo, site, verdict
(caught-real-edge / wrong-edge / inconclusive). **Floors only, never
rates** — no denominator exists for field use and none should be implied.
Same for benchmark-assignment prompt inspections going forward: if one is
worth doing, it is worth a line with a count. Uncounted inspection stays
out of the file entirely.

## 14. Definition of done

**Phase 1:** O1–O4 complete; O2/O3 cross-checks against the existing
hand-checks pass (any failure is a finding, triaged before proceeding).
Evidence rows written same-commit; §3.8 updated within license;
pre-registration graded and committed. Constraint candidates registered;
ADR written. Rerunning any cell is one command, and the O2 cell reruns in
the suite's tolerance for a post-resolver-change check.

**Phase 2** (tracked separately, not a gate on phase 1): O6–O7 with their
own pre-registrations; the trace-asymmetry and reference-lane constraints
registered before the first phase-2 row lands.

**O8 and O9** (Java, C) followed the same shape: each oracle's
pre-registration committed before it ran (§10.5 for C), and each cell
with §3.8 evidence in the same commit.

## 15. Appendix — oracle provenance (search of 2026-08-25)

What the search found, so the scope claims above carry their sources:

- **Go:** `golang.org/x/tools/go/callgraph/rta` (unchanged; also `vta` in
  the same package tree).
- **TypeScript:** `tsc` compiler API resolution (unchanged).
- **Python** — no sound static oracle confirmed, but static peers exist
  and disagree with each other by design: PyCG, Jarvis
  (pythonjarvis.github.io; arXiv 2305.05949 — its ground truth is
  trace-built plus 6 person-months of manual augmentation), PyPt, Scalpel,
  HeaderGen. Runtime-trace ground truth is the field standard: DyPyBench +
  DynaPyt (arXiv 2403.00539), `sys.monitoring` (PEP 669, 3.12+),
  `python -m trace` (function grain).
- **Rust:** Rupta — context-sensitive pointer analysis + call graph
  construction on MIR, open source (github.com/rustanlys/rupta; CC'24 doi
  10.1145/3640537.3641574, CGO'25 stack-filtering follow-up); the same
  papers name Rurta (RTA-style) and Ruscg (static-dispatch-only)
  baselines. `rust-callgraph` (heinzelotto) as prior art for the
  rustc-driver resolved-call walk. `cargo-call-stack` evaluated and
  rejected (LLVM-IR grain, embedded focus, fat-LTO, nightly-fragile).
  `uftrace` supports Rust and Python tracing.
- **TraceEval** (arXiv 2605.11006, 2026): execution-verified
  multi-language call-graph benchmark — 10,583 tracer-validated programs
  from 1,600+ repos, Python/JS/Java today, Go/Rust/TS tracers planned,
  pipeline released as a runnable artifact. Not built for grading
  extractors, but the tracer protocol and corpus are directly reusable as
  external cells later, and it is the precedent that execution-verification
  scales without manual ground-truth authoring.
