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
