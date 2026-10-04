# Extraction — Rust

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-28 — A symbol defined in two files is unattributed, not guessed
- **Cannot tell you:** which file a reference lands in, when the symbol's
  moniker is emitted as a definition by more than one file. Rust: every
  cargo target of a package gets the same `crate/`, `main().`, `tests/`
  monikers. Go: a package's namespace is declared in **every one of its
  files** (`package proxy` in each). References to such symbols produce
  no edge at all.
- **Because:** the decode's definitions map can hold one file per
  moniker, and first-wins fabricates edges: `decode()` therefore drops
  any moniker defined in more than one document and lets its references
  fall to `external_refs`, unattributed rather than guessed. *(This
  entry was first written for cargo targets only — the ADR-037 lesson
  that a register entry can be wrong by being too specific, caught the
  same day this time: the V2.M7 verification re-ingested the dogfood
  repo and the drop removed two Go module edges that had been **false
  since V2.M5** — `hobbes-proxy/main → internal/proxy/knowledge` and
  `hobbes-web/main → internal/web/artifacts`, both semantic-tier
  attributions of a duplicated package namespace to an arbitrary
  same-named file in the wrong package. Zero symbol edges changed for
  any language; the real member-level edges all survive.)*
- **Bites at:** module edges whose only evidence is a reference to a
  duplicated symbol — a bare `use mylib;` with no call behind it, a Go
  package qualifier. The function and type monikers that carry the call
  graph are unique, so edges are still raised wherever a real call
  resolves.
- **You find out:** **surfaced** — the `scip-decode` degradation record
  counts the dropped symbols and names a sample, landing in
  `extraction_errors` and the ingest WARNING like every other decode
  degradation. Since ADR-091 (D7) the record's `path` is the defining
  files' common directory and its wording is per lane, so a unit brief
  carries it only when its interior lies there — the whole-repo `"."`
  had put a Python tutorial's duplicate, in Rust's words, into every
  sklearn brief.
- **Provider (P9):** inherited from `rust-analyzer` **1.97.1** and
  `scip-go` **0.2.7** alike. An upstream release that scoped these
  monikers per target/file would make the drop a no-op.
- **Folds in:** C-137 (2026-09-13) — scip-clang's file-`static`s of one
  signature, with C's own-file recovery (ADR-109).
- **Source:** ADR-040, V2.M7 spike; generalised by the V2.M7
  verification (2026-08-15).

### C-29 — Ingesting a Rust repo executes that repo's code — *narrowed 2026-08-27 (ADR-092); Java face registered as C-66 (ADR-096), C's as C-136 (ADR-109)*
- **Cannot tell you:** nothing — this entry registers something Hobbes
  *does*, not something it misses: `hobbes ingest` on a Rust repo runs
  that repo's `build.rs` and proc macros, because rust-analyzer's loader
  compiles and executes them to expand the code it indexes. **Since
  ADR-092 that execution happens inside the ingest container** — the
  sandbox image with no network, the Hobbes cache as its one writable
  mount — never on the host; on a box without containment the provider
  refuses (C-64). The one other lane B step that executes repo-provided
  code, the venv listing, is contained the same way.
- **Because:** running the indexer as its ecosystem ships it is the §3.2
  trade, and rust-analyzer without build scripts and proc-macro expansion
  cannot resolve the derive- and macro-generated code that real Rust is
  made of. All writes stay in the staging tree and the user-global cargo
  registry (verified on the spike); the execution itself is the fact.
- **Bites at:** security posture, now bounded: ingesting an untrusted
  Rust repo still runs it, but inside a process boundary whose reach is
  the stage and the Hobbes cache — not the same trust decision as
  opening it in an editor any more. What the entry still concedes is
  that the code *runs*, and that the container is the boundary (rootless
  podman: a user namespace, no network, fixed mounts).
- **You find out:** **surfaced** — a `NOTE:` line on stderr every time
  the rust lane runs, not only the first, naming the container: the
  posture fact does not wear off. (`extract_scip_rust`, printed before
  the indexer starts.) Disclosure is not containment; the containment is
  `containment.PROFILES["index-rust"]` and the canary test.
- **Provider (P9):** inherited from `rust-analyzer` **1.97.1**. Upstream
  knobs exist to disable build scripts and proc macros, at the price of
  gutting resolution for macro-heavy code; a future release that
  sandboxes expansion would soften this entry without Hobbes changing.
- **Source:** ADR-040, finding 6.

### C-30 — Rust third-party semantics need a fetchable crate registry
- **Cannot tell you:** where a call into a third-party crate goes, when
  the crate's sources are not already in `~/.cargo/registry` and the box
  cannot fetch them — the first ingest of a dependency-heavy repo
  downloads its tree (51 MB for the spike repo's single dev-dependency).
- **Because:** cargo resolves and fetches dependency sources at index
  time. The registry is user-global, which is why Rust needs none of
  ADR-032's symlink machinery — and why an offline box or a cold cache
  degrades resolution instead of erroring.
- **Bites at:** third-party `uses`/`calls` edges, and ingest latency on
  first contact with a new dependency set. In-repo edges survive: they
  resolve from the staged sources alone.
- **You find out:** **surfaced** — `dependency_coverage` counts plus the
  ingest WARNING below the resolve floor, the same mechanism as C-23 and
  C-27, now covering its fourth language.
- **Provider (P9):** inherited from `rust-analyzer` **1.97.1** and the
  cargo toolchain it drives.
- **Source:** ADR-040, finding 6. The Rust sibling of C-23/C-27.

### C-157 — rust-analyzer's SCIP export states no override set: no `implements` edge for Rust
- **Cannot tell you:** which type implements which trait, or which
  method of an `impl Trait for T` block overrides which trait method.
  No `implements` edge is drawn for Rust (ADR-120), and `who_calls` on
  a trait method lists no implementor under "implemented or overridden
  by" — the heading every other lane B language answers.
- **Because:** rust-analyzer's `scip` command writes no
  `SymbolInformation.relationships` at all — measured 2026-09-16 on
  this repo's three cargo roots (202 symbol informations, 0
  relationships) against the five other indexers, every one of which
  states `is_implementation` pairs (ADR-120's table). Lane A could
  state the type-to-trait half from an `impl` block's syntax at
  syntactic tier; the method-to-trait-method half needs the trait
  resolved, which is lane B's job. Neither is built: a half-drawn set
  from one lane would read as the whole.
- **Bites at:** `who_calls` on a trait method, `graph_neighborhood`,
  `hobbes plan`'s impact through `implements` edges, and whatever
  ADR-120 §7's expansion of a call into its overrides comes to rest on
  — Rust would be the language it cannot reach.
- **You find out:** **surfaced** — every Rust lane B run appends a
  degradation record naming this entry ("rust-analyzer's SCIP export
  carries no `relationships` …, C-157"), printed as a WARNING by the
  ingest and listed by `list_blind_spots`, so a Rust root's silence
  reads as the provider's, not as a repo with no traits.
- **Provider (P9):** inherited from `rust-analyzer` **1.97.1**
  (8bab26f, 2026-07-14), its native SCIP export. Ends on an upstream
  release that writes the field; the helper reads it already.
- **Source:** ADR-120, the relationships measurement of 2026-09-16
  (`~/.hobbes/bench/relationships-probe/measure-this-repo.txt`).

### C-182 — A cfg twin is one node, at its first arm unless lane B defined exactly one — *registered 2026-10-03 (0.2.89-beta, ADR-165); its residual refused or named since 0.2.95-beta; narrowed 2026-10-04 (0.2.116-beta, ADR-165's second amendment): the node sits at the arm lane B defined, and lane B's references inside an uncompiled arm are refused*
- **Cannot tell you:** which arm of a Rust item written under two or more
  `#[cfg(…)]` arms the build compiles, unless lane B says so. A cfg twin
  is a qualname with two or more defs in one file, each gated by a `cfg`
  (on the item or an enclosing `mod`/`impl`), all of one kind and one impl
  header. Every arm mints the same id. **Since 0.2.116-beta** the node sits
  at the arm holding lane B's definition where exactly one arm holds one
  (rust-analyzer defines items only in compiled code); with lane B silent on
  the file, or no single defined arm, it sits at the **first** arm's line
  even where the build compiles another (`cow.rs`'s `width`). Lane A reads
  no features, so it files **every** arm's calls under the node
  (syntactic). Lane B *defines* only in the compiled arm but still writes
  *references* inside the others, resolved against the compiled arm's
  scope (leaf: `self.cipher` read as the module `aead`); before 0.2.116-beta
  23 such `semantic` `uses` edges were drawn on leaf, and since then every
  reference inside the widest uncompiled `cfg`-gated region holding no lane
  B definition is refused and counted. A callee only an inactive arm calls
  is drawn at `syntactic` alone. A call lane B resolves onto any arm
  draws to the node (since 0.2.89-beta; before, onto a later arm it drew
  nothing and was tailed `below-floor`, the wrong cause). Where lane A's
  guess names one arm and lane B's answer another, `hobbes lanes` lists
  the row as `cfg-twin` and does not fail on it (exit 3, ADR-123).
- **Residual:** a qualname repeated in one file that is **not** a twin by
  that rule. Two kinds (Rust's type and value namespaces allow `struct B`
  beside `const B`) are two items: refused at the later def from
  0.2.95-beta, and since 0.2.106-beta (ADR-174) the later one is its own
  node, `B~2`. One header and one kind with
  no `cfg` on some arm — which no crate that compiles can write; memchr's
  `benchmarks/haystacks` std copy writes it freely (147 ids) — is neither
  refused nor mapped: its node is the first def, a fact written inside a
  later def is filed under it, and a call lane B resolves onto a later def
  is `below-floor`. A `rust-repeats` record names these ids.
- **Because:** the id is built from the item's path, which `cfg` does not
  change, and lane A does not read the build's feature set. Telling the
  arms apart (reading `cargo metadata`'s features) is the prevention, and
  it changes symbol ids.
- **Bites at:** the twin's line in `who_calls`, `graph_neighborhood` and
  `get_module_doc` (it is the first arm's); its callees (every arm's, at
  syntactic tier where lane B did not compile the arm); `hobbes lanes`.
  Measured 2026-10-03: memchr 9 twins (4 in `haystacks`; std's own
  `cfg(test)` pairs), none of whose later arms is a lane B answer, so its
  graph is byte-identical; dagger `sdk/rust` and rust_proj 0; this repo 2
  (`minirustimpl`). **First graded cost, 2026-10-03 (eycorsican/leaf, a random
  draw, `oracle-grading.md` §10.49):** `crypto.rs` writes `mod aead` under
  `openssl-aead` and under aws-lc/ring; the build compiles the second arm,
  the node sits at the first, and 44 `semantic` call edges lane B resolved
  onto the compiled arm point at uncompiled lines (`AeadCipher.new` 65,
  compiled 235). The key contradicts all 44: 97.3% where every other Rust
  cell reads 100%. The edges name the right item; their line is wrong.
  **Since 0.2.116-beta** the node is at 235 and leaf reads 1,634 confirmed,
  0 contradicted; 45 lane B references in three files' uncompiled arms are
  refused (`~/.hobbes/bench/c182-compiled-arm-2026-10-04/`).
- **You find out:** surfaced — every ingest with a twin writes one
  `rust-cfg-twins` degradation record (the count, how many sit at the arm
  lane B defined, the lane B references refused in uncompiled arms and in
  how many files, examples with their def lines, this entry), shown by `list_blind_spots` and the ingest summary;
  `hobbes lanes` cites this entry beside the `cfg-twin` count. Since
  0.2.95-beta a `rust-repeats` record names the residual's ids, their
  files and def lines, and a refused two-kinds id is counted in the
  `rust-qualnames` record and the tail's `shared-qualname`.
- **Source:** ADR-165; CI run 37127474375; the measurement and regrade
  `~/.hobbes/bench/c182-rust-cfg-twins/`.

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-180 — Two impl blocks that named one type shared one symbol id: a later def had no node — *registered 2026-10-02 (0.2.87-beta, ADR-163); lifted 2026-10-03 (0.2.106-beta, ADR-174)*
- **Was:** lane A names an impl block's items after its first type identifier, so `impl Pointer for
  *const T` and `impl Pointer for *mut T` both minted `T.distance`, `impl From<&str> for Id` and `impl
  From<String> for Id` both `Id.from`, and a trait impl and the inherent impl of one type shared every name
  both declared (`Client.describe`). The node was the first def. Before ADR-163 a later def's facts were
  filed under it (memchr's `ext.rs:33` drew `T.distance calls T.distance`, a recursion that does not exist,
  at `semantic`; dagger's `gen.rs` merged 229 calls into the inherent methods' nodes); from ADR-163 they
  were refused and tailed `shared-qualname`, and a later def's callers and callees were absent. Measured
  2026-10-02: memchr 169 such ids (167 in `benchmarks/haystacks`), dagger's `sdk/rust` 104 (102 in
  `gen.rs`). Since 0.2.95-beta an id of two kinds (`struct B` beside `const B`) was refused the same way.
- **Lifted by — the technique:** per file, the defs of one qualname are grouped by `(impl header, kind)` in
  source order; the first group keeps the id and the n-th is `qualname~n` (Max: "Ordinal ~n", the scheme
  Java's and C++'s overloads use). Lane B joins by line, so each def's facts are its own: memchr's `*mut T`
  `distance` now calls the `*const T` one. The fallback still counts `Type::name` by the qualname before
  its ordinal and abstains where two blocks declare it (C-72). ADR-163's refusal, the `shared-qualname` tail
  class and the `rust-qualnames` record stay as a guard that finds nothing.
- **Residual edge cases:** the id says the def's order, not its impl block; its line and the block's header
  say which. A def added above another in the file renumbers what follows. Defs that share a header and a
  kind are still one id: a cfg twin is the node's (C-182), and an ungated same-header repeat is filed under
  the first and named (C-182's residual).
- **Source:** ADR-163; ADR-174; `~/.hobbes/bench/dup-qualnames-2026-10-02/`,
  `~/.hobbes/bench/c180-rust-impl-qualnames/`, `~/.hobbes/bench/c180-ordinal-2026-10-03/`.

### C-72 — Lane A's Rust fallback bound a path-qualified call by its last segment — *lifted 2026-09-03*
- **Was:** the fallback resolved `Option::<T>::deserialize(d)` by the
  bare name `deserialize` to the first same-file namesake — serde:
  `impl Deserialize for ()`'s method — and `Expected::fmt(self, f)`
  inside `impl Display for dyn Expected { fn fmt }` to the enclosing
  `fmt` itself, a self-loop. Two mechanisms, reproduced on a probe
  crate 2026-09-03: the generic path's head is a `type_identifier`,
  so `_qualifier_segments` read `[]` and the call fell into the
  bare-name lookup, which hit an `impl` method; and a trait head is a
  `type` in the symbol table, so `Trait::method` resolved to whatever
  `impl X for dyn Trait` had put under `Trait.method`. serde: 3 wrong
  `syntactic` edges of 81 (the other 78 confirmed by hand), visible
  only through C-73's lane-B-less copy; 3 of 910 dual-resolved sites
  as lane disagreements. *Partial* while it stood.
- **Lifted by — the technique:** ADR-098's rule in Rust's shape — when
  the head does not single out a declaration, abstain. Four rules in
  `_call_fallback`: (1) a call written with a `::` path (`qualified`,
  recorded by the grammar walk and by the token-tree walk from the
  `::` token before the name) is never looked up as a bare name, even
  when its path could not be read; (2) a bare name never binds to a
  `method` — Rust needs a path or a receiver to reach one; (3) a head
  that is a `trait` in the file (`RustFile.traits`, kept beside the
  symbol table) is dispatch and is left to lane B; (4) `Type::name`
  with more than one declaration under that qualname in the file (two
  `impl X for Type { fn fmt }` blocks) is an overload set. Sites the
  rules refuse land in the tail's `path-call` class (the source text
  shows `::` before the name), which is where the entry said they
  belonged. Tests: `TestPathQualifiedCallsBindByTheirHead` (three: the
  generic path and the bare-to-method case, the trait head and the
  overload set with a real `Local::make` still resolving, the same
  shapes inside a macro body).
- **A second face, found and fixed 2026-10-03 (0.2.112-beta):** a
  method call written with a turbofish, `world.reserve::<T>(1)`, parses
  as a `generic_function` around the `field_expression`; it was not
  read as a value's method, so the bare-name lookup bound it to a
  same-file free fn (hecs `tests/tests.rs`: three `#[test]` fns named
  `reserve` and `query_one`, 3 wrong `syntactic` edges where lane B did
  not answer; with lane B they were `hobbes lanes` rows, exit 1). Now
  `_is_dotted` sees through the turbofish and the call stays lane B's.
  Test: `test_a_turbofish_method_call_is_a_values_method`.
- **Residual edge cases:** `Type::assoc()` where the type is declared
  in another file is unchanged (it resolved through `mod_map` before,
  and still does, only for a unique qualname); a trait declared in
  another file is not in this file's `traits`, so `other::Trait::m(..)`
  walks the path and abstains at the trait's file only if the walk
  reaches it. The trait declaration's own method signatures are not
  symbols (C-9), so nothing can bind to them either way. `impl
  Deserialize for ()` still puts its method under a bare qualname
  (C-9's floor for a type with no name); rule (2) keeps bare calls off
  it, and a path never reaches `()`.
- **Source:** the four-repo extraction test of 2026-09-02 (agent D,
  serde-rs/serde); lifted 2026-09-03.
