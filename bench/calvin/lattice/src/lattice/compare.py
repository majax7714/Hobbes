"""**E2's reading** (`calvin-experiments.md` §6, the E2 card): an original run against its shadows.

E2 asks whether E1's score survives names the base model has never read. The answer is a *difference*
between two runs that differ in one thing, so this module computes nothing about a model and everything
about two directories: per arm, what each run scored and what the shadow cost; per cell, which greedy
answers flipped, each way.

**It reads runs, never targets.** The figures come from :func:`report.report`, which computes nothing a
row does not hold, and the flips come from `rows.jsonl`. Neither the target nor the shadow is opened —
by the time a run is compared, the only evidence left is what the run wrote down.

**Two runs that differ in more than the names are refused** (:class:`NotComparable`, its own type under
P10). The model, `k`, the sampling parameters and the cells planned must be equal: the gap between the
original and the descriptive shadow is read as *what renaming cost*, and it only reads that way when
renaming is the one thing that moved. The arms need not match — the reading is over the arms both runs
ran, which is how a two-arm shadow run (E2-a: C-2 and C-3) is compared with E1's five-arm original.

A shadow run is named by its `meta.json`'s `shadow.style` — `descriptive`, then `opaque`, which is the
order the two gaps are read in: descriptive − original is the memorised share, and opaque − descriptive
is what meaning in the names was worth. A run with no shadow block keeps its directory's name and the
reader can see that it never said which shadow it is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from . import report as report_of
from .e1 import META, ROWS

__all__ = ["SAME", "NotComparable", "compare", "flips", "render"]

#: What two runs must agree on before a delta between them is one variable. The arms are deliberately
#: not here: a shadow run of two arms against an original of five is compared on the two they share.
SAME = ("model", "k", "params")


class NotComparable(Exception):
    """Two runs differ in more than their names, so no delta was computed.

    Its own type (P10, ADR-036): a general "the report failed" handler must not absorb it. A delta
    between a run at `k = 5` and a run at `k = 1`, or over different cells, is a number with no reading,
    and printing it under E2's heading would be worse than printing nothing.
    """


def compare(original: Path | str, shadows: Sequence[Path | str]) -> dict:
    """One original run against each shadow run: the arm figures, their deltas, and the greedy flips."""
    original = Path(original)
    base_meta = _meta(original)
    base = report_of.report(original)
    base_greedy = _greedy(original)

    found = {
        "original": {
            "run": original.name,
            "model": base.get("model"),
            "k": base.get("k"),
            "cells": list(base_meta.get("cells") or []),
            "target_sha": base.get("target_sha"),
            "missing": base["missing"],
            "sections": {
                name: {arm: _figures(data["overall"]) for arm, data in (section.get("arms") or {}).items()}
                for name, section in base["sections"].items()
            },
        },
        "shadows": [],
    }
    for where in shadows:
        where = Path(where)
        other_meta = _meta(where)
        _comparable(original, base_meta, where, other_meta)
        other = report_of.report(where)
        found["shadows"].append(
            {
                "run": where.name,
                "style": (other_meta.get("shadow") or {}).get("style"),
                "map_sha256": (other_meta.get("shadow") or {}).get("map_sha256"),
                "missing": other["missing"],
                "sections": {
                    name: _section(base["sections"].get(name) or {}, other["sections"].get(name) or {})
                    for name in base["sections"]
                },
                "flips": flips(base_greedy, _greedy(where)),
            }
        )
    return found


def _comparable(base_dir: Path, base: dict, other_dir: Path, other: dict) -> None:
    """Refuse unless the two runs differ only in their names (and, allowably, in their arms)."""
    for field in SAME:
        if base.get(field) != other.get(field):
            raise NotComparable(
                f"{other_dir.name} has {field} {other.get(field)!r} and {base_dir.name} has "
                f"{base.get(field)!r}; the delta would not be one variable, so nothing was compared"
            )
    if sorted(base.get("cells") or []) != sorted(other.get("cells") or []):
        raise NotComparable(
            f"{other_dir.name} and {base_dir.name} were planned over different cells "
            f"({len(other.get('cells') or [])} against {len(base.get('cells') or [])}); "
            "the delta would not be one variable, so nothing was compared"
        )


#: The figures carried per arm. `pass_at_k` is pass@5 at E1's and E2's shape (`k = 5`, `n = k`).
FIGURES = ("pass_at_1", "pass_at_1_sampled", "pass_at_k")


def _section(base: dict, other: dict) -> dict:
    """One of the report's sections — real bodies, or wrappers — over the arms both runs ran."""
    arms = [arm for arm in (base.get("arms") or {}) if arm in (other.get("arms") or {})]
    return {
        arm: {
            "original": _figures(base["arms"][arm]["overall"]),
            "shadow": _figures(other["arms"][arm]["overall"]),
            "delta": {
                figure: _delta(other["arms"][arm]["overall"].get(figure), base["arms"][arm]["overall"].get(figure))
                for figure in FIGURES
            },
        }
        for arm in arms
    }


def _figures(overall: dict) -> dict:
    return {figure: overall.get(figure) for figure in ("cells", *FIGURES)}


def _delta(shadow: float | None, base: float | None) -> float | None:
    """Shadow minus original, or `None` where either side had nothing to compute — never 0.0."""
    if shadow is None or base is None:
        return None
    return round(shadow - base, 6)


def flips(before: dict, after: dict) -> dict:
    """Per arm, the greedy answers that changed: `lost` passed then failed, `gained` the other way.

    Greedy only (`sample` 0, round 0): a drawn sample flipping is the sampler, and the pair of rates
    beside these lists is where the drawn samples are read. A cell only one of the runs answered is in
    neither list — it is not a flip, it is a gap, and the arm's `cells` counts say so.
    """
    arms = sorted({arm for arm, _ in before} | {arm for arm, _ in after})
    found: dict[str, dict] = {}
    for arm in arms:
        shared = sorted(
            cell for (this_arm, cell) in before if this_arm == arm and (arm, cell) in after
        )
        lost = [cell for cell in shared if before[(arm, cell)] and not after[(arm, cell)]]
        gained = [cell for cell in shared if after[(arm, cell)] and not before[(arm, cell)]]
        if shared:
            found[arm] = {"cells": len(shared), "lost": lost, "gained": gained}
    return found


# MARK: - the two readers -


def _meta(run_dir: Path) -> dict:
    """A run's `meta.json`. A run without one cannot be held to anything, so it is refused."""
    path = run_dir / META
    if not path.exists():
        raise NotComparable(f"{run_dir.name} has no {META}, so there is nothing to check it against")
    return json.loads(path.read_text(encoding="utf-8"))


def _greedy(run_dir: Path) -> dict[tuple[str, str], bool]:
    """`(arm, cell) -> passed` over the greedy round-0 rows, which is what a flip is read from."""
    path = run_dir / ROWS
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        (row["arm"], row["cell"]): row.get("class") == "pass"
        for row in rows
        if row.get("round") == 0 and row.get("sample") == 0 and row.get("arm")
    }


# MARK: - the table -


def render(found: dict) -> str:
    """The comparison as a table: one block per shadow, one row per arm, then the flips."""
    base = found["original"]
    lines = [
        f"E2 {base['run']} — {base.get('model') or 'no model recorded'} "
        f"(k={base.get('k')}, {len(base.get('cells') or [])} cell(s))"
    ]
    if base["missing"]:
        lines.append(f"missing, not read as zero: {', '.join(base['missing'])}")
    for name, arms in base["sections"].items():
        if not arms:
            continue
        lines.append(f"  {name}:")
        lines.append(f"    {'arm':<8}{'pass@1':>9}{'pass@1(s)':>11}{'pass@k':>9}")
        for arm, figures in arms.items():
            lines.append(
                f"    {arm:<8}"
                + "".join(f"{_number(figures[figure]):>{width}}" for figure, width in zip(FIGURES, (9, 11, 9)))
            )

    for shadow in found["shadows"]:
        lines.append("")
        lines.append(f"{shadow.get('style') or shadow['run']} ({shadow['run']})")
        if shadow["missing"]:
            lines.append(f"  missing, not read as zero: {', '.join(shadow['missing'])}")
        for name, arms in shadow["sections"].items():
            if not arms:
                continue
            lines.append(f"  {name}:")
            lines.append(
                f"    {'arm':<8}{'pass@1':>9}{'Δ':>9}{'pass@1(s)':>11}{'Δ':>9}{'pass@k':>9}{'Δ':>9}"
            )
            for arm, figures in arms.items():
                lines.append(
                    f"    {arm:<8}"
                    + "".join(
                        f"{_number(figures['shadow'][figure]):>{width}}{_number(figures['delta'][figure], sign=True):>9}"
                        for figure, width in zip(FIGURES, (9, 11, 9))
                    )
                )
        for arm, flipped in shadow["flips"].items():
            lines.append(
                f"  flips {arm}: {len(flipped['lost'])} lost, {len(flipped['gained'])} gained "
                f"of {flipped['cells']} greedy cell(s)"
            )
            for cell in flipped["lost"]:
                lines.append(f"    lost   {cell}")
            for cell in flipped["gained"]:
                lines.append(f"    gained {cell}")
    return "\n".join(lines)


def _number(value: float | None, sign: bool = False) -> str:
    """A figure there was nothing to compute reads `-`, never `0.00`; a delta carries its sign."""
    if value is None:
        return "-"
    return f"{value:+.2f}" if sign else f"{value:.2f}"
