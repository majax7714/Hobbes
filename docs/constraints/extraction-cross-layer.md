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

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-73 — A directory symlink inside the repo was walked as a second copy of its target — *lifted 2026-09-03*
- **Was:** every language's discovery walk (`discover.iter_python_files`,
  `gosource.iter_go_files`, `javasource`, `rustsource`, `tssource`,
  `terraform`, the manifest walks) used `iterdir()` and never tested
  `is_symlink()`. serde's `serde/src/core -> ../../serde_core/src` (a
  git symlink, mode 120000, which `#[path = "core/crate_root.rs"]`
  compiles into the `serde` crate) yielded 19 modules, 516 symbols and
  1,356 call sites twice — under `serde_core/src/…` with lane B's
  evidence and under `serde/src/core/…` with none, so the copy was a
  lane-B-less zone at `resolved 0` and the fallback's wrong answers
  (C-72) became edges there; the summary's counts included the
  duplicates. A link to an ancestor would have looped the walk. *Partial*
  while it stood: the copy's rows showed `resolved 0` and nothing said
  why.
- **Lifted by — the technique:** `discover.linked_copy_target` — a
  directory symlink whose resolved target lies **inside the repo** is a
  second copy of a tree the walk reaches at its real path, and every
  walk asks `is_linked_copy` before descending, so the tree is walked
  **once, at its target**. The ingest records each such link once
  (`linked_copies`; `extraction_errors`, stage `discover`, path = the
  link, naming the target and C-73), so the ids a reader expects under
  the link are explained rather than silently absent. A link whose
  target is *outside* the repo is the only copy Hobbes will see and is
  walked as before. Lane B's staging copies discovered files, so it
  never saw the copy; its occurrences already landed at the target
  (`serde_core/src/…`), which is why nothing semantic is lost. Tests:
  `TestLinkedCopies` (four: once-at-target, outside-link walked,
  ancestor link does not loop, every language walk + the record).
- **Residual edge cases:** the crate that compiles those files under
  the link's path (`serde`) has no module of its own for them — the
  target's module ids are the only ones, which is the choice this entry
  made explicit ("whether the copy should be a module is a real
  question"): one tree, one id. `tsextract` skips *every* symlink on
  its own walk (outside-repo targets included), so a TS repo whose only
  copy sits behind a link is lane-A-less there — unchanged by this
  lift, and not yet met on a real repo. File symlinks are followed as
  before.
- **Source:** the four-repo extraction test of 2026-09-02 (agent D,
  serde-rs/serde); lifted 2026-09-03.
