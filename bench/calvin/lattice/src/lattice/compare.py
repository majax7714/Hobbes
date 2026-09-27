"""**E2's reading** (`calvin-experiments.md` §6, the E2 card): an original run against its shadows.

E2 asks whether E1's score survives names the base model has never read. The answer is a *difference*
between two runs that differ in one thing, so this module computes nothing about a model and everything
about two directories: per arm, what each run scored and what the shadow cost; per cell, which greedy
answers flipped, each way; and per arm, **the paired tests** (:mod:`lattice.paired`) that say whether a
delta is more than the cells it rests on.

**It reads runs, never targets.** The figures come from :func:`report.report`, which computes nothing a
row does not hold, and the flips come from `rows.jsonl`. Neither the target nor the shadow is opened —
by the time a run is compared, the only evidence left is what the run wrote down.

**Two runs that differ in more than the names are refused** (:class:`NotComparable`, its own type under
P10). The model, `k`, the sampling parameters and the cells planned must be equal: the gap between the
original and the descriptive shadow is read as *what renaming cost*, and it only reads that way when
renaming is the one thing that moved. The arms need not match — the reading is over the arms both runs
ran, which is how a two-arm shadow run (E2-a: C-2 and C-3) is compared with E1's five-arm original.

**E4's two cross-run readings live here too** (D-11 a), for the same reason E2's do: they are readers over
run directories, and the thing that differs between the two runs is what each of them refuses to let vary.

- :func:`e4_compare` is **one file's two runs, one model apart** — the 7B against the 32B (E4-e's ceiling
  arm). It refuses unless the two agree on the ISA, the file, the target's SHA, the units, `k` and the
  sampling parameters, and it reads the arms they share, per arm and per unit kind. **Everything it prints
  is described**: a bigger model is a price, not a registered test, and no comparison on `e4.COMPARISONS`
  is between two models.
- :func:`e4_pool` is **one registered comparison pooled over several files' runs** — `S-2h − S-2` on the
  helper units of avx2, sse2 and avx512 at once. A unit is keyed `<isa>/<unit>` because `hsum256_ps` and
  `hsum512_ps` are two units and one name would pool them into one; a run list naming one ISA twice is
  refused, since that pools a file's units with themselves; and the runs must share the model, `k` and the
  params, because a pooled figure over two models is a number about neither.

A shadow run is named by its `meta.json`'s `shadow.style` — `descriptive`, then `opaque`, which is the
order the two gaps are read in: descriptive − original is what renaming to equally meaningful names cost,
and opaque − descriptive is, on sqlite-vector's lattice, the loss of the task statement as much as of the
names (E2's record, `calvin-experiments.md` §6: the hole's name was the only place it was said). A run with no shadow block keeps its directory's name and the
reader can see that it never said which shadow it is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from . import e4 as e4_of
from . import paired as paired_of
from . import report as report_of
from .e1 import META, ROWS

__all__ = [
    "E4_POOL_SAME",
    "E4_SAME",
    "SAME",
    "NotComparable",
    "compare",
    "e4_compare",
    "e4_pool",
    "flips",
    "render",
    "render_e4_compare",
    "render_e4_pool",
]

#: What two runs must agree on before a delta between them is one variable. The arms are deliberately
#: not here: a shadow run of two arms against an original of five is compared on the two they share.
SAME = ("model", "k", "params")

#: What two E4 runs must agree on before the difference between them is the **model**: one file, at one
#: commit, planned over one set of units, drawn the same number of times at the same settings. `model` is
#: deliberately absent — it is the variable — and so are the arms, which are read as the two share them.
E4_SAME = ("isa", "file", "target_sha", "units", "k", "params")

#: What the runs of one pool must agree on. The **file is what varies** here — that is what pooling is — so
#: the ISA and the file are not in the list; the model, `k` and the params are, because a figure pooled
#: over two models or two sample counts is a number about neither.
E4_POOL_SAME = ("model", "k", "params")


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
    base_cells = paired_of.cells(original)
    k = int(base_meta.get("k") or 0)

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
                "paired": _paired(base_cells, paired_of.cells(where), k),
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


def _paired(base: dict, other: dict, k: int) -> dict:
    """Per section, per arm both runs ran: the shadow against the original, paired by cell."""
    return {
        name: {
            arm: paired_of.paired(base[name][arm], other[name][arm], k)
            for arm in base[name]
            if arm in other[name]
        }
        for name in base
        if base[name] and other[name]
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
        for name, arms in shadow["paired"].items():
            lines.append(f"  paired, {name} (shadow − original, exact, two-sided, uncorrected):")
            for arm, tests in arms.items():
                lines.extend(paired_of.render_pair(arm, tests))
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


# MARK: - E4: one file's two runs, one model apart -


def e4_compare(a: Path | str, b: Path | str) -> dict:
    """Run *b* against run *a* over one held-out file, paired by unit, per arm and per unit kind.

    The delta is *b* − *a*, so the larger model goes second: `e4_compare(<7B run>, <32B run>)` reads what
    model size bought. The two must be one file's run twice (:data:`E4_SAME`) with the **model** the one
    thing allowed to differ; anything else is :class:`NotComparable` and nothing is computed.

    **Every figure here is described** and none of them is registered: `e4.COMPARISONS` is a list of
    comparisons between two *contexts* at one model, and a second model is a price. :func:`render_e4_compare`
    says so on its own heading.
    """
    a, b = Path(a), Path(b)
    first, second = _meta(a), _meta(b)
    _e4_comparable(a, first, b, second)

    k = int(first.get("k") or 0)
    rows_a, rows_b = _e4_rows(a), _e4_rows(b)
    before = {kind: report_of.e4_units(rows_a, kind) for kind in e4_of.KINDS}
    after = {kind: report_of.e4_units(rows_b, kind) for kind in e4_of.KINDS}
    arms = [arm for arm in _e4_arms(first, rows_a) if arm in _e4_arms(second, rows_b)]

    found: dict[str, dict] = {}
    for arm in arms:
        tests = {
            kind: paired_of.paired(before[kind][arm], after[kind][arm], k)
            for kind in e4_of.KINDS
            if arm in before[kind] and arm in after[kind]
        }
        if tests:
            found[arm] = tests
    return {
        "a": _e4_side(a, first, rows_a),
        "b": _e4_side(b, second, rows_b),
        "k": k,
        "isa": first.get("isa"),
        "file": first.get("file"),
        "arms": arms,
        # on the record, because a reader who meets a p here must not take it for one of E4's own
        "described": True,
        "paired": found,
    }


def _e4_comparable(a: Path, first: dict, b: Path, second: dict) -> None:
    """Refuse unless the two runs are one file's plan answered twice, the model aside."""
    for field in E4_SAME:
        mine, theirs = _e4_field(first, field), _e4_field(second, field)
        if mine == theirs:
            continue
        # the units are a long list, so that one is said as a count: the refusal has to be readable
        said = (
            f"units: {len(theirs)} of them and {a.name} has {len(mine)}"
            if field == "units"
            else f"{field} {theirs!r} and {a.name} has {mine!r}"
        )
        raise NotComparable(
            f"{b.name} has {said}; `e4 compare` reads the model as the one difference between two runs "
            "of one file, so nothing was compared"
        )


def _e4_field(record: dict, field: str) -> object:
    """One field as the comparison reads it. The units are their **names**: the order is the plan's."""
    if field == "units":
        return sorted(row.get("name") or "" for row in record.get("units") or [])
    return record.get(field)


def _e4_rows(run_dir: Path) -> list[dict]:
    """A run's round-0 rows that carry an arm — the rows every E4 figure is read from, and no others."""
    path = run_dir / ROWS
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if row.get("round") == 0 and row.get("arm")]


def _e4_arms(record: dict, rows: list[dict]) -> list[str]:
    """The arms a run answered: its plan's, in its plan's order, and otherwise the rows' own."""
    planned = list(record.get("arms") or [])
    answered = {row["arm"] for row in rows}
    return [arm for arm in planned if arm in answered] or sorted(answered)


def _e4_side(run_dir: Path, record: dict, rows: list[dict]) -> dict:
    """One run as the reading names it: which model, over which file, and what it did not write."""
    return {
        "run": run_dir.name,
        "model": record.get("model"),
        "k": record.get("k"),
        "isa": record.get("isa"),
        "file": record.get("file"),
        "units": len(record.get("units") or []),
        "arms": _e4_arms(record, rows),
        "target_sha": record.get("target_sha"),
        "missing": [] if (run_dir / ROWS).exists() else [ROWS],
    }


# MARK: - E4: one registered comparison, pooled over several files -


def e4_pool(runs: Sequence[Path | str], first: str, second: str, kind: str | None = None) -> dict:
    """One arm pair over the pooled units of several files' runs, paired by `<isa>/<unit>`.

    The key carries the ISA because a unit name is a file's, not the target's: `hsum256_ps` and
    `hsum512_ps` are two units, and `S-2` and `S-2h` are asked of each. A run list naming one ISA twice is
    :class:`NotComparable` — it would pool one file's units with themselves — and so is a list whose runs
    do not share :data:`E4_POOL_SAME`.

    *kind* keeps one of `e4.KINDS`, which is how D-11's helper reading is pooled; `None` pools every unit.
    `registered` says whether the pair and the kind are on `e4.COMPARISONS`, so a reader can tell the
    pooled form of a registered comparison from a pooled description of something else.
    """
    paths = [Path(run) for run in runs]
    if not paths:
        raise NotComparable("no run was named, so there was nothing to pool")
    records = [(path, _meta(path)) for path in paths]

    seen: dict[str, Path] = {}
    for path, record in records:
        isa = record.get("isa")
        if isa in seen:
            raise NotComparable(
                f"{path.name} and {seen[isa].name} are both over {isa}; a pool is one run per instruction "
                "set, and two of them would put one file's units in twice, so nothing was pooled"
            )
        seen[isa] = path
    base_path, base = records[0]
    for path, record in records[1:]:
        for field in E4_POOL_SAME:
            if base.get(field) != record.get(field):
                raise NotComparable(
                    f"{path.name} has {field} {record.get(field)!r} and {base_path.name} has "
                    f"{base.get(field)!r}; a pooled figure would be about neither, so nothing was pooled"
                )

    k = int(base.get("k") or 0)
    before: dict[str, dict] = {}
    after: dict[str, dict] = {}
    counts: list[dict] = []
    for path, record in records:
        by_arm = report_of.e4_units(_e4_rows(path), kind)
        isa = record.get("isa") or path.name
        counts.append(
            {
                "run": path.name,
                "isa": isa,
                "file": record.get("file"),
                "units": {arm: len(by_arm.get(arm) or {}) for arm in (first, second)},
                # an arm a run has no row for contributes nothing and is named: its units then land in
                # the pooled reading's `unpaired`, which is not the same as a unit that failed
                "missing": [arm for arm in (first, second) if arm not in by_arm],
            }
        )
        for arm, into in ((first, before), (second, after)):
            for unit, value in (by_arm.get(arm) or {}).items():
                into[f"{isa}/{unit}"] = value

    return {
        "pair": [first, second],
        "kind": kind,
        "registered": (first, second, kind) in e4_of.COMPARISONS,
        "k": k,
        "model": base.get("model"),
        "runs": counts,
        "paired": paired_of.paired(before, after, k),
    }


# MARK: - E4's two tables -


def render_e4_compare(found: dict) -> str:
    """One file's two runs as a table: which model each side served, then the tests per arm and kind."""
    a, b = found["a"], found["b"]
    lines = [
        f"E4 {a['run']} → {b['run']} — {found.get('file') or found.get('isa')} "
        f"(k={found.get('k')}, {a['units']} unit(s), arms {', '.join(found['arms']) or 'none'})",
        f"  a {a['run']}: {a.get('model') or 'no model recorded'}",
        f"  b {b['run']}: {b.get('model') or 'no model recorded'}",
        "  every figure below is described: a second model is a price, not a registered comparison",
    ]
    for side in (a, b):
        if side["missing"]:
            lines.append(f"  {side['run']}: missing, not read as zero: {', '.join(side['missing'])}")
    for arm, kinds in found["paired"].items():
        lines.append(f"  paired, {arm} (b − a, exact, two-sided, uncorrected):")
        for kind, tests in kinds.items():
            lines.extend(paired_of.render_pair(f"{kind} units  described", tests))
    if not found["paired"]:
        lines.append("  (no arm both runs answered)")
    return "\n".join(lines)


def render_e4_pool(found: dict) -> str:
    """The pooled comparison as a table: which runs went in, how many units each gave, then the tests."""
    first, second = found["pair"]
    label = "registered" if found["registered"] else "described, not a registered comparison"
    lines = [
        f"E4 pooled {second} − {first} over {len(found['runs'])} run(s) — "
        f"{found.get('model') or 'no model recorded'} (k={found.get('k')}, "
        f"{found.get('kind') or 'every'} unit(s); {label})"
    ]
    for row in found["runs"]:
        counts = ", ".join(f"{arm} {count}" for arm, count in row["units"].items())
        lines.append(f"  {row['isa']:<8}{row['run']:<24}{counts}")
        if row["missing"]:
            lines.append(f"    missing, not read as zero: no rows for {', '.join(row['missing'])}")
    lines.append("  paired over <isa>/<unit> (exact, two-sided, uncorrected):")
    lines.extend(paired_of.render_pair(f"{second} − {first}", found["paired"]))
    return "\n".join(lines)
