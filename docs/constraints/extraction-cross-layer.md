# Extraction — cross-layer

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-15 — A node-id collision across languages drops a file from the graph
- **Cannot tell you:** anything about the losing file — a repo-root
  `widget.py` and `widget.ts` both want the id `widget`, and merge order
  decides: Python is the base graph, then TS, then Go (V2.M5), then Rust
  (V2.M7), then the pack layer's nodes, `tf:` among them, last (V2.M4).
- **Because:** ids are path-derived per layer and are not namespaced on
  collision. Fixing it properly means rewriting ids across a whole layer's
  nodes, edges, symbols, tests and routes.
- **Bites at:** the graph's completeness, by an accident of pipeline order.
- **You find out:** **surfaced** — one `extraction_errors` record per
  collision, naming both paths and the fix, plus an ingest WARNING. It was
  data loss decided by ordering *in silence* before M8 review.
- **Source:** M8 review, `future_additions.md` → cross-language namespacing.

### C-73 — A directory symlink inside the repo is walked as a second copy of its target
- **Cannot tell you:** that two module ids are one source tree. serde's
  `serde/src/core -> ../../serde_core/src` (a git symlink, mode
  120000, which `#[path = "core/crate_root.rs"]` compiles into the
  `serde` crate) yields 19 modules, 516 symbols and 1,356 call sites
  twice — under `serde_core/src/…` with lane B's evidence and under
  `serde/src/core/…` with none, so the copy is a lane-B-less zone at
  `resolved 0` and the fallback's wrong answers (C-72) become edges
  there. The summary's node, symbol and site counts include the
  duplicates; `serde/src` reads `49.4% of 2726 sites` and is mostly the
  copy.
- **Because:** every language's discovery walk (`discover.iter_*`,
  `gosource.iter_go_files`, …) uses `iterdir()` and does not test
  `is_symlink()`; the staging copy lane B indexes resolves the link the
  build's way (one crate, one path), so its occurrences land on one
  side only. Whether the copy *should* be a module is a real question
  — the crate does compile those files under that path — which is why
  this is registered rather than pruned: dropping links would lose a
  repo that keeps its only copy behind one.
- **Bites at:** Rust crates sharing sources by `#[path]` through links;
  monorepos symlinking a shared directory into several packages;
  `docs/` trees linking `examples/`. Counts inflate, and the copy's
  edges are the floor's.
- **You find out:** **partial** — the copy's rows show `resolved 0`
  and the by-directory line ranks it, but nothing says *why*, and
  nothing says the two ids are one tree. Candidate surfacing: record
  each symlinked directory at discovery as a degradation record naming
  the target, and either alias the copy's ids to the target's or mark
  its rows `linked-copy` so the summary can exclude them from the
  denominator.
- **Source:** the four-repo extraction test of 2026-09-02 (agent D,
  serde-rs/serde). Registered, not fixed.
