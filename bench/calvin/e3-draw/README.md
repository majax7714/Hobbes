# E3's C lattice draw — the scripts as they ran (2026-09-26)

A record, not a package. These are the driver scripts of E3's draw (`docs/calvin/calvin-experiments.md` §6,
"E3's pool — the C lattice draw's record"; D-5), copied unchanged from the driver directory
`~/.hobbes/bench/calvin-lattice/e3/draw/` (and `count.py` from `../family-count/`). Their paths (`HERE`,
`repos/`, `pool.json`) are that directory's. The clones, ingests and outputs stay there.

- `DRAW-RULE.md` — the rule, committed by hash before the draw (sha256 `f4b6e2abf25b2035…`, `b273b13`).
- `draw.py` — the pool: 70 GitHub searches, the union, the seeded order.
- `gate.py` — gates 1–4 and 6, and the ISA tokeniser and list the rule fixes.
- `count.py` — the member set, the thin filter, the loose groups and the registered body-shape rule.
- `measure.py` — ISA families, the body-shape rule with its pair cap, validation reach, two-axis share, and the
  precision sample.
- `dedupe.py` — cross-repo duplicates by normalised body hash.

E3's corpus (`bench/calvin/lattice`, the corpus unit) reproduces the union and the dedupe from these, and its
tests hold the port to them.
