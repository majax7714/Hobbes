"""The benchmark harness — ``hobbes bench`` (ADR-055).

ADR-052 named the verification method for the derivation programme:
run Hobbes **as a harness** over a known software-engineering
benchmark (SWE-bench-class — issue in, patch out, the benchmark's own
hidden tests decide) against the same models run **pure** on the same
instances, and let the error stream drive the adjustment. The three
hypotheses it bears on are preregistered in
``docs/benchmark-hypotheses.md``; this package is the machinery that
produces the numbers those hypotheses are decided by, and nothing in
it interprets a result.

The pieces, in pipeline order:

- :mod:`hobbes.bench.instances` — the instance schema (SWE-bench's,
  read from a local JSONL export), the **instance protocol** (a
  contamination cutoff on ``created_at``, repo and id filters, a
  limit — every drop counted and named), and the **depth** proxy H2
  buckets on (files the gold patch touches — declared a proxy).
- :mod:`hobbes.bench.workspace` — a checkout of the instance's repo at
  its base commit, from a bare mirror cached under
  ``~/.hobbes/cache/bench/``; the candidate patch is ``git diff`` from
  that commit, ``.hobbes/`` excluded.
- :mod:`hobbes.bench.arms` — the two arms. **Harness**: ``ingest`` →
  ``plan`` (the issue text is the proposal; lexical seeds, C-36 — an
  instance that seeds nothing is a recorded harness failure, never
  dropped) → ``run`` (ADR-054) → patch. **Pure**: Claude Code on the
  same checkout with its own tools and no Hobbes, the issue text as
  the prompt → patch.
- :mod:`hobbes.bench.accounting` — tokens, cost, wall time and turns
  from Claude Code's JSON result envelope, per arm; a term that was
  not observed is recorded as unobserved, never imputed.
- :mod:`hobbes.bench.verdict` — the benchmark's own evaluation
  (``swebench.harness.run_evaluation``, pinned) run as a subprocess
  over the predictions; its report is the verdict. Hobbes does not
  reimplement per-repo test semantics: the benchmark's limits are
  ours (P9) and the entry says so.
- :mod:`hobbes.bench.results` — one record per (instance, arm, model)
  in ``records.jsonl``, and the report that lays the records against
  H1 (solve rate by model, pure vs harnessed, gap closed), H2 (solve
  rate by depth bucket, slope) and H3 (tokens / cost / wall **per
  solved instance**).

Everything is quota-free to exercise: the test suite drives both arms
with stand-ins (a fake ``claude`` that edits a file and prints an
envelope, the ADR-054 stand-in session, a fake evaluator that writes a
report). Live runs spend the model's quota and are the owner's call.
"""

from hobbes.bench.instances import Instance, Selection, load_instances, select  # noqa: F401
