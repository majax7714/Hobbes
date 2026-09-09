"""Atlas-0 — sparse is not absent (`docs/atlas0/atlas-0.md`).

A synthetic-world experiment on the transformer block itself: does the
block's *act* separate a referent it has seen once or twice (sparse-real)
from one that does not exist (absent), and under which training does
absence become a state rather than a phrase. Nothing here ships; the
output is an atlas entry per block.

This package is the model-free half — steps 1 and 2 of the design's
order of work — and is deterministic end to end:

- :mod:`atlas0.names` — the stem vocabulary every name is made of, and
  stem-level edit distance (names are made of sand: an absent name is a
  recombination of the same pieces as a real one).
- :mod:`atlas0.world` — ``atlas0 gen``: the authored graph (modules,
  symbols, tests; ``defined_in`` / ``calls`` / ``reached_by``), the four
  classes with their mention budgets, written absences, the queries with
  their act targets, and one corpus per arm — byte-identical per seed.
- :mod:`atlas0.check` — ``atlas0 check``: the step-1 exit criteria read
  back from the written files, not from the generator's bookkeeping.
- :mod:`atlas0.acts` — the act vocabulary, the scorer that reads one act
  off a model's output line, and the act × class confusion matrix (§6.1).
- :mod:`atlas0.tokens` — the entity tokenizer: how a name enters each
  block (B1 stems, B2/B3 one dedicated token), the one structural input
  the experiment gives the model (§7).
- :mod:`atlas0.refmodel` — a random-init GPT-shaped forward pass in
  numpy, used to exercise the probe pipeline before any training (§8
  step 2's exit); not the training block.
- :mod:`atlas0.probe` — the linear class probe per layer and the
  authority tables (§6.2, §6.3).

Training (steps 3–4) lives outside this package; it needs a GPU and
torch, and it is the part that is not deterministic in the way this
package must be.
"""

import os as _os

# The reference model's matrices are small (a prompt is ~15 tokens); a
# multi-threaded BLAS spends its time synchronising on them — 15× slower
# than one thread on a 12-core box. Parallelism is across items, by
# process (``atlas0 probe-check --workers``). A caller's own setting wins.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_var, "1")

__all__ = ["names", "world", "check", "acts", "tokens", "refmodel", "probe"]
