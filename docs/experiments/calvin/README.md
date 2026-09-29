# Calvin — a model that can only code, on purpose

**Thesis** (Max, 2026-09-28; deliberately looser than the mapped-agents thesis): a model with constrained
input and only the ability to code, perhaps in a single language (C for now), is more efficient and
better aligned per task. It shares the mapped-agents programme's root, which is to reduce the room for
chaos. Mapped agents shrink the task and the context; Calvin shrinks the model's input and its
capability. The role Calvin is for is in [`../../calvin/calvin-charter.md`](../../calvin/calvin-charter.md).

**Status:** **closed for now** (2026-09-28). D-16's rule, written before its calls, found no positive
result. This is a pause, not an end (Max: "close for now, not close calvin completely"): Max next
reassesses the programme or turns to another piece of Hobbes. Index: [`../README.md`](../README.md).

## The lower bound: Calvin as a product today

The keyed rounds (M0, M0-Go, M0-Gate, 2026-09-03 to 09-11) measured Calvin as an experiment and were
closed as an approach on 2026-09-12 (ADR-107). **What they produced is the accepted lower bound for
Calvin as a product:**
- a frontier agent does the work;
- `hobbes gate` (the linker on a finished diff) judges the result;
- `hobbes dispatch` runs it in `hobbes-session` behind an egress allowlist.

The gate cleared every gold diff and blocked every seeded error with the right class. On 10 live keys it
had 0 false blocks (CV-4). The harness passed its validation rule on 2026-09-17: 40 sessions, at least 3
areas, and no unresolved false block. It stays the way work is done ([`../../calvin/`](../../calvin/README.md);
the tracker reads 90 of 40, with three false blocks still open, the decorator case). Anything a Calvin
model does is measured against this floor. The harness makes no keyed or arm comparison
(`calvin-harness.md` §4).

## What is here

| file | what it is |
|---|---|
| [`calvin-experiments.md`](calvin-experiments.md) | The lattice programme (ADR-151): design, E0–E4 and D-11–D-15 records, decisions D-1–D-16, and the closing summary ("Where the programme stands") |
| [`keyed-rounds/`](keyed-rounds/) | M0 ([`calvin-potential.md`](keyed-rounds/calvin-potential.md)), M0-Go rounds 1–2, M0-Gate, and their cells: history, and the lower bound's evidence |
| [`atlas0/atlas-0.md`](atlas0/atlas-0.md) | Atlas-0: whether a small block's act can tell a sparse-real referent from an absent one (held) |

Tooling: `bench/calvin/lattice/` (the `lattice` package; E0–E4 and D-11–D-15), `bench/calvin/e3-draw/`,
`bench/calvin/templates/` (the M0 gold fills), `bench/atlas0/`, `pipeline/scripts/calvin_probe.py`
(the keyed rounds' driver). The run records are off-tree under `~/.hobbes/bench/calvin-lattice/`,
`calvin-go/` and so on, each with its `PREREG.md`.

## Observed register

Each entry states what was seen, its source, and how far it reaches. `exp` is
[`calvin-experiments.md`](calvin-experiments.md) §6, and `atl` is [`atlas0/atlas-0.md`](atlas0/atlas-0.md).

### The keyed rounds (stock models filling templates; the lower bound)

- **CV-1 — A template arm set no floor over a frontier agent in Go.** Across three re-tests the residual
  moved: NULL new → declared in the wrong world → declared in the right world, not compiled (at WP-8,
  the loop closed 9 of 11 NULLs and 0 of 9 built; at WP-10, 0 of 7 built). The audited T pass was
  0.075 / 0.10 / 0.05. [`calvin-m0-go.md`](keyed-rounds/calvin-m0-go.md) §10 and WP-12; 2026-09-11; Haiku
  4.5 on gitleaks. **Established** for A2, gitleaks and Haiku. On the three recall-free keys, T and O
  cannot be told apart.
- **CV-2 — Shown a body whole, the template filler declined to act.** It returned holes byte-identical
  to the parent (10 of 16 rows were empty diffs) and passed 0 of 3 readable keys, with budget to spare.
  [`calvin-m0-go-r2.md`](keyed-rounds/calvin-m0-go-r2.md) §10, WP-16. **Established.** *The source
  corrects itself:* O − T is +0.333 (n = 3), not +0.667, because one of O's passes read its own key.
- **CV-3 — Grounded in a real repo, the filler resolves sparse-real references and invents absent ones
  as sibling-shaped names.** Sparse-real references were resolved 1,940 / 2,352 / 1,943 times, with 0
  sparse NULLs. `calvin-m0-go.md` §10. **Established** for that repo and model.
- **CV-4 — The gate is a safety property, not a helper.** It blocked 2 of 10 live diffs with 0 false
  blocks and cleared gold 20/20, and the repair turn raised no pass (0.0). [`calvin-m0-gate.md`](keyed-rounds/calvin-m0-gate.md)
  §10, WP-21; Haiku 4.5 on fzf; $5.03. **Provisional on n = 10** (block rate 0.2, interval [0.0, 0.5]).
- **CV-5 — Every round's instrument flattered the agent until audited.**
  - 19 of round 1's 31 passes were vacuous.
  - Five O sessions read their own key's history (D-x, fixed in 0.1.20-beta; the network channel is
    C-124).
  - Every O session hit the 30-turn cap.

  `calvin-m0-go-r2.md` WP-12; `calvin-m0-gate.md` §10. **Established.**
- **CV-6 — M0 in Python** (Sonnet 5, 4 keys, 2026-09-04): T beat O on the one key both solved, and T was
  honest where its anchors failed. [`calvin-potential.md`](keyed-rounds/calvin-potential.md) §10.
  **Superseded** ("nothing here moves a standing").

### Atlas-0 (30M synthetic blocks; nothing about real models, code or Calvin, *atl* §10)

- **CV-7 — A standard block invents from sand.** It answers every absent name (1.00), and a name one
  stem from a real symbol takes that symbol's module: 30% [0.24–0.37], against 2.5% by chance. *atl*
  steps 5–6; 5 seeds; $7.04. **Established** (memorisation regime).
- **CV-8 — Taught to refuse, B1 refuses sparse-real and absent names together** (Kang's conflation). It
  refuses sparse-real between a quarter and two thirds, depending on the run. *atl* v0 and v1.
  **Established direction; the rate varies by run.**
- **CV-9 — Relation-absence (B2, v1) is the first act that tells sparse from absent, and it does not
  travel.** On `calls`, B2 refuses the empty relation 1.00 and the filled one 0.00, but held-out absent
  names 0.00. *atl* v1 "lived world"; $4.41. **Established.** Existence-absence as a state is unshown in
  every block.
- **CV-10 — Typed attention (B4) collapses to one identity operator,** so typing has to be given, not
  learned, at this scale. The sibling pull lives in the input map. *atl* 2026-09-07; λ sweep and 30-cell
  grid; Atlas-0 in all $22.28 assumed of $25. **Established at λ = 0.** Abstention could not be read at this T.
- *atl* also withdraws its "facts live under the trained question" line: an eval prompt carried an
  untrained word. Check eval prompts against the training vocabulary.

### The lattice (sqlite-vector @ `0c2223a`, one scalar reference; no claim about "C" until a second target agrees, *exp* §10)

- **CV-11 — The instruments hold.** Seeded mutants grade 465 of 465 as expected, and both shadows pass
  1,447 of 1,447. The target's own f16/bf16 kernels disagree with its scalar kernel on inf/NaN (77 cases).
  *exp* "E0's record". **Established.**
- **CV-12 — Pattern in context works beyond volume.** C-2 − C-4 is +0.24 at pass@1 (3 / 18, p 0.0015)
  and +0.33 at pass@5; 8 of 28 cells more than 30% from their nearest shot still passed. *exp* "E1's
  record"; Qwen2.5-Coder-7B. **Established.** It does not hold for Olmo (+0.03, p 0.50; about 80%
  `invented`).
- **CV-13 — Facts alone are null.** C-1 − C-0 is −0.03 (p 0.50). Facts beside pattern are suggestive
  only: C-3 − C-2 is +0.10 (p 0.18). *exp* "E1's record". **The C-1 null is established; C-3 is
  provisional.**
- **CV-14 — Descriptive renames cost nothing measurable; opaque renames remove the task statement.**
  Descriptive C-2 is −0.08 (p 0.27). Opaque C-2 is −0.24 (p 0.0007), and 30 of 49 opaque wrong bodies
  are nearest a sibling metric's gold. *exp* "E2's record". **Established.** The card's "name-reading"
  reading does not hold as worded.
- **CV-15 — Pattern training sharpens reading named neighbours; it does not install skill.** A 300-step
  LoRA gives +0.148 on C-2 (p 0.0002) and −0.006 on C-0 (p 0.44). On opaque names with the task stated
  it gives −0.025 (p 0.45). *exp* "E3's record"; about $5.55. **Established.** The registered +0.351 was
  against a degenerate shuffled control, and is superseded. 3,000 steps were not run.
- **CV-16 — The card's family rule and the ingested pool are unfit for training.** The rule groups 18 of
  63 target bodies, and the pool is two to three orders of magnitude short. A 40-repo C draw gave the
  corpus instead. *exp* "E3's card, revised" and "E3's pool". **Established.**
- **CV-17 — Decomposed (P12), the graph's ISA-axis shots lift a 7B that rebuilds whole files, and a 7B
  parser's fields hurt.** S-2 − S-0 is +0.258 / +0.263 / +0.211 (avx2 / sse2 / avx512, p ≤ 0.0003
  each). S-5 − S-3 is −0.173 / −0.158 / −0.073. *exp* "E4's record"; 127 units. **Established** at L1.
- **CV-18 — Helper shots by width family lift helpers, but not where a shot crosses an ISA's
  capability.** The pooled gain is +0.261 (p 0.0001), and sse2's is +0.000. The 32B adds +0.13 on cells
  and +0.30 on helpers over the 7B, at about $0.58 a file. *exp* "D-11's record". **Established**; the
  32B figure is a price, not a registered test.
- **CV-19 — Facts about intrinsic names do not steer either size.**

  | where the facts go | 7B | 32B |
  |---|---|---|
  | beside the shots | +0.011, p 0.59 (D-12) | +0.017, p 0.34 (D-15) |
  | in the retry loop | −0.001, p 1.0 (D-13) | +0.002, p 0.86 (D-15) |

  The student drops the name it was told about and invents another. The only fact a student acted on is
  a positive name mapping (the init). *exp* "D-12's record", "D-13's record" and "D-15's record".
  **Established null.**
- **CV-20 — No name-to-name positive fact reaches the gold.** Rule S answers 12.7% of 387 invented
  names, and 4.1% of those answers are the gold's. Two thirds of the invented names are sand, declared
  by no header; the rest need a composition. *exp* "D-14's probe"; no spend. **Established.**
- **CV-21 — A retry round buys +0.02 at the 7B and +0.04 at the 32B** (p ≤ 0.0002). *exp* D-13 and
  D-15. **Established.**

**Spend on record:** the lattice programme cost about $21.50 (E1 $6.59, E2 $1.89, E3 about $5.55, E4
about $1.25, D-11 about $2.11, D-12 about $0.67, D-13 about $0.32, D-15 about $3.08). Atlas-0 is $22.28 assumed
(of $25), and the keyed rounds are costed in their own records.

## Proposed or parked, not run

- **The lattice:** E5 (the pattern world), E6 (the compiler as teacher) and E7 ("make sqlite-vector")
  are parked.
  - E3's 3,000-step pair would cost about $36 and needs a token-true cap and a fair control.
  - The L2/L3 instrument, the frontier-parser arm, a second draw, and NEON/RVV.
  - D-15's route c, the comparison-family positive (about 1.8% of names), was not recommended.
  - The open ends of the closing summary: **a second target**, and **the composition class**, where no
    fact about names reaches.
- **Atlas-0, held:** the T that carries the abstention act (about $3.5–4), the grid's second run (about
  $3.8), T_v2, and a B4-given block (handoff § Atlas-0).
- **Superseded, not open:** the keyed rounds' held next steps (ADR-107).

## Instrument lessons that bind the next run

- **Estimates:** the runner's `max_tokens` estimate runs 3.5× to 6× high at round 0 and only 1.1× to 1.7×
  high on a 32B retry round. Hand estimates ran low (E2 35% over, E3's training about 5×).
- **Caps:** the money left sets Modal's timeout, so size each call so its timeout covers the estimate. A
  cut call is charged and returns nothing. Resume in place (`e4 run <dir>`), and keep paid output before
  parsing it.
- **Tests:** pair by cell, with sampled pass@1, a sign-flip test and k = 10. A greedy gap needs about a
  9-cell net to clear the noise. A retry needs a same-retry control (D-13). A control varies only its own
  variable (E3's did not). Probe a rule as it is worded.
- **Pre-register** each run, and write any closing rule before the calls (D-11 to D-16).
- **Keyed work:** a vacuous pass is not a pass. Cut the repo at the parent, and use post-cutoff keys.
