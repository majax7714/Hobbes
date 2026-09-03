"""Test-time training on the derived layer (ADR-099, `docs/olmo3-ttt-validation.md`).

The experiment asks whether the derived layer does more when it is
loaded into a model's **weights** for a session — a few hundred LoRA
steps over renderings of ``.hobbes/derived/`` at one SHA — than when
the same material is put in the prompt. Everything in this package is
the *deterministic* half of that: the corpus the adapter is trained on
is a rendering of artifacts Hobbes already has, produced with no model
in the loop, byte-identical from the same SHA (P1, P5). Training and
serving live outside the package (``pipeline/scripts/modal_ttt.py``),
because they need a GPU and are nondeterministic in a way this package
must not be.

- :mod:`hobbes.ttt.corpus` — ``hobbes derive-corpus``: symbol cards,
  module-doc chunks, and navigation QA pairs in six families, split by
  symbol so an evaluated symbol never appears in a training pair.
"""
