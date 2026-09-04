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
- **Source:** ADR-040, V2.M7 spike; generalised by the V2.M7
  verification (2026-08-15).

### C-29 — Ingesting a Rust repo executes that repo's code — *narrowed 2026-08-27 (ADR-092); Java face registered as C-66 (ADR-096)*
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

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

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
