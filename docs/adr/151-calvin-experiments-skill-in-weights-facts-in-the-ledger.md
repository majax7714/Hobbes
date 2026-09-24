# ADR-151 — The Calvin experiments: skill in the weights, facts in the ledger; the design is `calvin-experiments.md`

**Date:** 2026-09-24 · **Status:** accepted (Max, 2026-09-24: "good to go with recommended routes", then
"good to go" for E0 after the literature pass) · **Owner:** Max · **Design:**
[`calvin/calvin-experiments.md`](../calvin/calvin-experiments.md), which is this ADR's body in ADR-099's
pattern · **Amends:** the charter ([`calvin-charter.md`](../calvin/calvin-charter.md), its 2026-09-24
amendment)

Bench work, not the layer: nothing here moves `VERSION` (ADR-103). Registers no constraint.

## Context

Max, 2026-09-24: *"our goal is to build a model which can program in a certain language … for now
lets focus on just a model which can make sqlite vector … it can have a teacher model telling the
functions and parts."* The records already hold half an answer. ADR-099 put the derived layer into a
7B's weights. At 300 steps the weights took the repo's regularities and none of its edges. At 3,000
steps the edges went in and the language gain left. The charter (§7) says facts do not live in
Calvin. The keyed rounds (ADR-107 §1) lost their first runs to their own instruments. Atlas-0 showed
the standard block inventing names made of known stems.

## Decision

1. **The rule.** A model in this programme may learn the language and its patterns. It never
   learns the target's facts: those come from the ledger at the SHA every time. The charter is
   amended to say so (D-1, route a).
2. **The target is sqlite-vector** (`0c2223a`), whose oracle cell reads 100/100, so the graph can
   grade what a model writes. The first unit of work is its SIMD kernel lattice: 31 names × 6 ISAs,
   with `distance-cpu.c` as a numeric reference. Three ISAs (SSE2, AVX2, AVX-512) run natively on
   this box, and NEON and RVV are left (D-4).
3. **The general model is an open model and a parser** (D-2 as amended). It turns a request into
   the task format, whose fields the graph fills wherever it can. It writes nothing large. Claude
   appears only as a priced comparison arm, and no Claude output trains anything.
4. **The order is E0 → E1 → the branch E1 selects** (D-3). E0 builds and self-tests the instruments
   with no spend. E1 runs at a $10 ceiling, with its first unit priced before the rest runs.
5. **The literature pass shaped the design** (§12 of the design): E1 has an iterate arm and
   per-ISA reports, E2 has two rename shadows, G-hsr has a failure class, and E3 trains only on
   validated, fact-complete examples.
6. **Every build and run of target code is in the image** (ADR-092, C-64). **No dispatched session
   is training data** (ADR-107). **Spend waits for Max** to name the run and its ceiling.

## Consequences

- `bench/calvin/lattice/` is a new bench project (stdlib, its own pytest, like `bench/atlas0/`). Its
  real-source fixture is the target's kernel files, trimmed by a script to the float32, int8 and
  1-bit rows, verbatim otherwise, and pinned at `0c2223a` with the target's Apache-2.0 licence.
- The kernels are reached through `dispatch_distance_table` after the ISA's own init, not by name.
  AVX-512's `bit1_distance_hamming_avx512` is `static`, and each `_impl` is `static inline`, so a
  harness that calls by name cannot reach them. The table is also what the extension ships.
- E0 is built through `hobbes dispatch` like any other work, and its sessions stay evaluation rows.
  The real target's acceptance (93 cells, gold passes, seeded wrong bodies fail with the right class)
  runs on the host in the image before a unit merges. The session cannot see the target's clone.
- A claim this programme makes is the pair's and the target's (charter §7), never "the model can
  program in C", until the shadows and a second target agree.
