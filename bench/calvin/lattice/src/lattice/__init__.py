"""The Calvin experiments' E0 instruments (ADR-151; `docs/calvin/calvin-experiments.md` §5–§6).

sqlite-vector's SIMD kernel files each hand-write the same distance functions, one file per ISA. This package maps that
lattice, punches holes in it, and grades what a model writes into a hole. Bench tooling: never product, never versioned
(ADR-103). Anything that executes the target's code runs in the sandbox image (ADR-092, C-64).
"""
