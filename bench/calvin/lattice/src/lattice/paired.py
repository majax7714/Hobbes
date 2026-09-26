"""**The noise floor**: is a gap between two arms, or two runs, more than the cells it rests on?

E1 and E2 read their results as differences over 63 real bodies, where one cell is 0.016 of a pass
rate. Several of the readings are two to six cells, so a difference needs a test beside it before it is
read. Both runs grade the *same cells*, so the test is **paired by cell**: a cell that passed on both
sides, or on neither, says nothing about the gap, and only the cells that moved do.

**Three tests, one per figure the report prints**, all exact and all deterministic (no random draw, so
the same rows give the same p twice):

| figure | per cell | test |
|---|---|---|
| **pass@1** | did the greedy sample pass | exact McNemar: the lost and gained cells against a fair coin |
| **pass@k** | did any of the *k* drawn samples pass (the estimator at `n = k`) | exact McNemar, the same way |
| **pass@1(sampled)** | the drawn samples' pass rate | exact sign-flip over the per-cell differences |

The sign-flip test asks how often a sum of the per-cell differences at least this far from zero would
come out if each cell's difference were equally likely to have either sign. It is computed exactly, by
counting over the integer numerators — every cell's rate is a count of passes over its samples — so it
has no seed and no Monte Carlo error.

**What a p here is and is not.** It is two-sided and per comparison, **uncorrected** for how many
comparisons a reading makes; a reader who looks at five arms and three figures has made fifteen, and says
which one the card named before the run. It is about *these cells* under *this model and seed*: a second
target or a second base is a different question, which this module does not answer. A cell only one side
answered is left out and counted in `unpaired`, never read as a fail.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

from .e1 import ROWS
from .report import BODY_KINDS, WRAPPER_KINDS

__all__ = ["SECTIONS", "arms", "cells", "mcnemar", "paired", "render_pair", "sign_flip"]

#: The report's two sections, which are never pooled: a wrapper is not the task a body is.
SECTIONS = {"bodies": BODY_KINDS, "wrappers": WRAPPER_KINDS}


def mcnemar(lost: int, gained: int) -> float:
    """The exact two-sided McNemar p for *lost* and *gained* discordant cells.

    Under the null each moved cell is a fair coin, so the p is twice the smaller tail of
    `Binomial(lost + gained, 1/2)`, capped at 1. No moved cell is no evidence either way: p = 1.
    """
    moved = lost + gained
    if moved == 0:
        return 1.0
    tail = sum(math.comb(moved, i) for i in range(min(lost, gained) + 1))
    return min(1.0, 2 * tail / 2**moved)


def sign_flip(differences: list[Fraction]) -> float:
    """The exact two-sided sign-flip p for per-cell differences, counted over integer numerators.

    Every difference is scaled by the common denominator into an integer, and the null distribution of
    their signed sum is counted exactly over all `2^n` sign patterns. A difference of zero contributes
    nothing and is kept (it doubles every count, which cancels). No differences: p = 1.
    """
    if not differences:
        return 1.0
    scale = math.lcm(*(d.denominator for d in differences))
    steps = [abs(int(d * scale)) for d in differences]
    observed = abs(sum(int(d * scale) for d in differences))
    counts = {0: 1}
    for step in steps:
        grown: dict[int, int] = {}
        for total, ways in counts.items():
            for signed in (total + step, total - step):
                grown[signed] = grown.get(signed, 0) + ways
        counts = grown
    extreme = sum(ways for total, ways in counts.items() if abs(total) >= observed)
    return min(1.0, extreme / 2 ** len(steps))


def cells(run_dir: Path | str) -> dict[str, dict[str, dict[str, dict]]]:
    """`section -> arm -> cell -> {"greedy": bool, "drawn": [bool, …]}` over a run's round-0 rows.

    Round 0 only, as the report's figures are: an iterate round is the model reading its own feedback,
    which is a different measure. A run with no `rows.jsonl` has no cells, and a caller says it is missing.
    """
    path = Path(run_dir) / ROWS
    found: dict[str, dict[str, dict[str, dict]]] = {name: {} for name in SECTIONS}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("round") != 0 or not row.get("arm"):
            continue
        section = next((name for name, kinds in SECTIONS.items() if row.get("kind") in kinds), None)
        if section is None:
            continue
        cell = found[section].setdefault(row["arm"], {}).setdefault(row["cell"], {"greedy": None, "drawn": []})
        passed = row.get("class") == "pass"
        if row.get("sample") == 0:
            cell["greedy"] = passed
        else:
            cell["drawn"].append(passed)
    return found


def paired(before: dict[str, dict], after: dict[str, dict], k: int) -> dict:
    """The three paired tests of *after* against *before*, each `{cells, …, p}`; the delta is after − before.

    *before* and *after* are one arm's `cell -> {"greedy", "drawn"}` from :func:`cells`. pass@k is read
    only where both sides drew exactly *k* samples — the estimator at `n = k` is any-pass, and at any other
    `n` it is not, so such a cell is left out of that test rather than read another way.
    """
    shared = sorted(set(before) & set(after))
    unpaired = len(set(before) ^ set(after))

    greedy = [c for c in shared if before[c]["greedy"] is not None and after[c]["greedy"] is not None]
    anypass = [c for c in shared if len(before[c]["drawn"]) == k == len(after[c]["drawn"]) and k > 0]
    sampled = [c for c in shared if before[c]["drawn"] and after[c]["drawn"]]

    rate = lambda drawn: Fraction(sum(drawn), len(drawn))  # noqa: E731 — one line, used twice below
    differences = [rate(after[c]["drawn"]) - rate(before[c]["drawn"]) for c in sampled]
    return {
        "unpaired": unpaired,
        "pass_at_1": _discordant(greedy, lambda c: before[c]["greedy"], lambda c: after[c]["greedy"]),
        "pass_at_k": _discordant(anypass, lambda c: any(before[c]["drawn"]), lambda c: any(after[c]["drawn"])),
        "pass_at_1_sampled": {
            "cells": len(sampled),
            "delta": round(float(sum(differences) / len(differences)), 6) if differences else None,
            "moved": sum(1 for d in differences if d),
            "p": round(sign_flip(differences), 6),
        },
    }


def _discordant(shared: list[str], was, now) -> dict:
    """One binary figure's paired table: both, neither, lost, gained, the delta and McNemar's p."""
    lost = sum(1 for c in shared if was(c) and not now(c))
    gained = sum(1 for c in shared if now(c) and not was(c))
    return {
        "cells": len(shared),
        "both": sum(1 for c in shared if was(c) and now(c)),
        "neither": sum(1 for c in shared if not was(c) and not now(c)),
        "lost": lost,
        "gained": gained,
        "delta": round((gained - lost) / len(shared), 6) if shared else None,
        "p": round(mcnemar(lost, gained), 6),
    }


def arms(run_dir: Path | str, first: str, second: str, k: int) -> dict:
    """Within one run, arm *second* against arm *first*, per section: E1's C-2 against C-4, say.

    Two arms of one run answer the same cells under the same model, seeds and parameters, so the pair
    differs in the context only. A section in which either arm did not run is left out, not zeroed.
    """
    found = cells(run_dir)
    return {
        name: paired(arms_[first], arms_[second], k)
        for name, arms_ in found.items()
        if first in arms_ and second in arms_
    }


def render_pair(label: str, tests: dict) -> list[str]:
    """One comparison's three tests as table lines, under *label*."""
    lines = [f"    {label}  (unpaired {tests['unpaired']})"]
    for figure in ("pass_at_1", "pass_at_k"):
        test = tests[figure]
        lines.append(
            f"      {figure:<18}{_signed(test['delta']):>8}  lost {test['lost']:>3}  gained {test['gained']:>3}"
            f"  of {test['cells']:>3}  p {test['p']:.4f}"
        )
    test = tests["pass_at_1_sampled"]
    lines.append(
        f"      {'pass_at_1_sampled':<18}{_signed(test['delta']):>8}  moved {test['moved']:>3}"
        f"            of {test['cells']:>3}  p {test['p']:.4f}"
    )
    return lines


def _signed(value: float | None) -> str:
    """A delta carries its sign; one there was nothing to compute reads `-`, never `+0.00`."""
    return "-" if value is None else f"{value:+.3f}"
