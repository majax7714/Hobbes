# ADR-071 — The shell is `exec`; human-first units in a benchmark; two small parser fixes

**Date:** 2026-08-22 · **Status:** accepted · **Amends:** ADR-058 (the
exec-repeat refusal), ADR-047/ADR-054 (human-first units, in benchmark
runs only), ADR-070 (`search_file`), ADR-066 (handoff parsing).

## Context

The ADR-070 verification run (`five-fresh-7b-adr070`, 0/5 both arms;
the read is in `benchmark-hypotheses.md`) was the first in which a 7B
session did the whole intended chain — sklearn U2: unread-edit refusal
→ `search_file` → `read_file` by line range → `edit_file` with the
anchor copied from the file → **edited**. The same trace then showed
the defect that has ended most harness sessions since ADR-058: its
`pytest` right after the edit was refused as *"already called … the
result has not changed"*. The proxy's MCP tool is named plain `exec`;
the loop's shell check was `name.endswith("__exec") or name == "bash"`.
So in every harness run the shell was a read-only tool — a test re-run
after an edit was a repeat, and "6 turns of refused repeated calls" is
how sessions ended.

Second, sympy: the bounded handoff (ADR-070) landed and hit the gold
file for the first time; the planner-seeded partition put that file in
a 1,783-site unit whose complement is 87 % unresolved; ADR-047's rule
parked it **human-first**, and the remaining six units were not named
(C-52). Zero implementers ran. Hobbes declined the task by its own
honesty rule in a benchmark with no human to hand it to — and in the
two earlier runs (lexical seeding, different partition) the same file's
owner had been parked too, so sympy was never attempted by its owner
in any run.

Third, two small things the same run surfaced: `search_file` on a path
that does not exist answered "(no matches)" — two pure arms took that
as confirmation of a hallucinated path; and a planner path ending a
sentence (`test_zeta_functions.py.`) went unresolved.

## Decision

- **`is_exec_tool(name)`**: `exec`, `…__exec`, or `bash`. The
  exec-repeat rule, `edited_since_exec`, and the mutating/productive
  accounting now apply to the harness shell as they always did to
  `bash`.
- **`hobbes bench run --human-first park|spawn`** (default `park`, no
  behaviour change): with `spawn`, a human-first unit is spawned with
  its write scope kept (`build_policy(human_first="spawn")` omits the
  commit/add denies), its brief still carries the complement, and the
  unit record says `human-first: spawned anyway (--human-first spawn,
  C-53) — <reason>`. The banner states which mode the run is in. This
  is the benchmark analogue of Max's D2 rule — *for benchmarks Hobbes
  runs alone, the manual gate is off* — and only the benchmark has it;
  `hobbes run` keeps parking. **C-53** registers the departure.
- `search_file` on a missing path is an **error** naming the path
  (and pointing at `list_files`).
- Handoff items lose trailing sentence punctuation (`.:;,`).
- A unit with zero detected sites is never human-first (the ratio is
  undefined; it used to divide by zero only under a test's
  monkeypatch, but the guard belongs in the code).

## Consequences

- The exec fix changes every future harness session's shape: a model
  can now run the same test before and after an edit. The three runs
  of 2026-08-22 all carry the defect; their "refused repeated calls"
  exits are partly it.
- `--human-first spawn` is recommended for the next benchmark run and
  is Max's to flip; either way the record shows the units and why.
- **Tests:** `test_the_proxy_exec_is_the_shell_under_every_name`,
  `TestHumanFirstInABenchmark` (park skips; spawn runs with the reason
  recorded), the missing-path search test, the handoff punctuation
  test, `build_policy(human_first="spawn")`. 857 pytest.
