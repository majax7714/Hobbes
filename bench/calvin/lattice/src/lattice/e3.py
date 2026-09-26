"""**E3's reading** (`calvin-experiments.md` §6, "E3's card, revised"): two runs of one plan, one adapter apart.

E2 asked what renaming cost, and read one original run against its shadows. E3 asks what **training**
bought, and the shape is the same reader over two run directories — except that here the two runs differ
in the *weights that answered*, not in the bytes that were sent. So this module refuses far more than
:mod:`lattice.compare` does: the plan must be the same plan (the cells, the arms, `k`, the sampling
parameters, the model, the shadow, the stated-task sentence and the target's SHA), and the **adapter is
the one thing allowed to differ**. E3's two comparisons are adapter against *shuffled adapter* and, where
the base is the question, adapter against base, so each is a pair of runs this function will take.

**Two registered comparisons, and everything else described** (the card's point 1). The training task is
"given the neighbours, write the member", which C-2 carries and C-0 does not, so the two readings are
registered separately and before the run:

| comparison | arm | asks |
|---|---|---|
| **E3-use** | C-2 | does training make the model better at *using* examples? |
| **E3-weights** | C-0 | did the pattern move into the weights? |

:data:`REGISTERED` is that table and :func:`render` marks those two arms as findings — **in the `bodies`
section only** (:data:`REGISTERED_SECTION`). The card's floor was computed over the real bodies, and a
wrapper is not the task a body is (`paired.py`), so the wrapper section's C-2 is printed beside them and
described rather than read. Every other arm the runs share — C-3, C-4, the stated-task opaque arm — is
printed exactly as it came and is a description, not a result.

**The primary figure is pass@1(sampled)** (:data:`PRIMARY`, the card's point 2). At 63 bodies one cell is
0.016 of a greedy rate and renaming alone moved 12 to 17 of them, so a greedy gap needs about nine net
cells to reach p < 0.05; the sampled rate is the sensitive one, and E3 draws `k = 10` to steady it. All
three of :func:`lattice.paired.paired`'s tests are printed, and the arm's line says which of them the
card registered, because a reader who takes whichever p is smallest has made a different comparison.

**It reads runs, never targets or weights.** The figures come from `rows.jsonl` through
:mod:`lattice.paired`, and the adapters' identities from each `meta.json`'s `adapter` block — the path on
the volume and the manifest's own `corpus_hash`, `recipe_hash`, `steps` and `repo`. Nothing here loads a
model, and a run whose `rows.jsonl` is not there is named in `missing` rather than read as a floor.

:class:`lattice.compare.NotComparable` is the refusal, the same type E2's reading raises: "these two runs
are not one variable apart" is one guarantee, and one type is what a caller catches for it.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import paired as paired_of
from .compare import NotComparable
from .e1 import META, ROWS

__all__ = ["PRIMARY", "REGISTERED", "REGISTERED_SECTION", "SAME", "NotComparable", "compare", "render"]

#: What two runs must agree on before the difference between them is the adapter. **The arms and the
#: cells are here**, unlike E2's :data:`lattice.compare.SAME`: E2 compares a five-arm original with a
#: two-arm shadow on what they share, and E3's two runs are the same plan answered twice.
SAME = (
    "model",
    "k",
    "params",
    "arms",
    "cells",
    "shadow",
    "stated_task",
    "stated_task_sha256",
    "target_sha",
)

#: The two comparisons the card registered, by the arm each is read on (its point 1).
REGISTERED = {"C-2": "E3-use", "C-0": "E3-weights"}

#: The section they are read in. The card's noise floor is 63 **real bodies**, and a wrapper's one call
#: is not the task a body is, so the wrapper rows of the same two arms are described beside them.
REGISTERED_SECTION = "bodies"

#: The figure those two are read on, with the paired sign-flip test beside it (its point 2).
PRIMARY = "pass_at_1_sampled"

#: The fields whose order is not part of the plan: two plans that list them differently are one plan.
_SORTED = ("arms", "cells")


def compare(a: Path | str, b: Path | str) -> dict:
    """Run *b* against run *a*, paired by cell, per section and per arm — plus which adapter each served.

    The delta is *b* − *a*, so the adapter run goes second: `compare(shuffled, adapter)` reads E3-use and
    E3-weights the way the card writes them. Two runs that differ in anything but the adapter are
    :class:`NotComparable` and nothing is computed.
    """
    a, b = Path(a), Path(b)
    first, second = _meta(a), _meta(b)
    _comparable(a, first, b, second)

    k = int(first.get("k") or 0)
    before, after = paired_of.cells(a), paired_of.cells(b)
    return {
        "a": _side(a, first),
        "b": _side(b, second),
        "k": k,
        "registered": dict(REGISTERED),
        "registered_section": REGISTERED_SECTION,
        "primary": PRIMARY,
        "paired": {
            name: {
                arm: paired_of.paired(before[name][arm], after[name][arm], k)
                for arm in before[name]
                if arm in after[name]
            }
            for name in before
            if before[name] and after[name]
        },
    }


def _meta(run_dir: Path) -> dict:
    """A run's `meta.json`. A run without one cannot be held to anything, so it is refused."""
    path = run_dir / META
    if not path.exists():
        raise NotComparable(f"{run_dir.name} has no {META}, so there is nothing to check it against")
    return json.loads(path.read_text(encoding="utf-8"))


def _comparable(a: Path, first: dict, b: Path, second: dict) -> None:
    """Refuse unless the two runs are one plan answered twice, the adapter aside."""
    for field in SAME:
        mine, theirs = _field(first, field), _field(second, field)
        if mine != theirs:
            raise NotComparable(
                f"{b.name} has {field} {theirs!r} and {a.name} has {mine!r}; E3 reads the adapter as the "
                "one difference between two runs of one plan, so nothing was compared"
            )


def _field(record: dict, field: str) -> object:
    """One field as the comparison reads it: a list whose order is not the plan's is sorted first."""
    value = record.get(field)
    if field == "stated_task":
        # an older plan has no such key at all, and "no sentence" is what that means
        return bool(value)
    if field in _SORTED:
        return sorted(value or [])
    return value


def _side(run_dir: Path, record: dict) -> dict:
    """One run as the reading names it: which weights, over which plan, and what it did not write."""
    return {
        "run": run_dir.name,
        "model": record.get("model"),
        "k": record.get("k"),
        "arms": list(record.get("arms") or []),
        "cells": len(record.get("cells") or []),
        "adapter": record.get("adapter"),
        "shadow": (record.get("shadow") or {}).get("style"),
        "stated_task": bool(record.get("stated_task")),
        "missing": [] if (run_dir / ROWS).exists() else [ROWS],
    }


# MARK: - the table -


def render(found: dict) -> str:
    """The comparison as a table: what each side served, then the paired tests per section and arm."""
    a, b = found["a"], found["b"]
    lines = [
        f"E3 {a['run']} → {b['run']} — {a.get('model') or 'no model recorded'} "
        f"(k={a.get('k')}, {a['cells']} cell(s), arms {', '.join(a['arms']) or 'none'})"
    ]
    for side, run in (("a", a), ("b", b)):
        lines.append(f"  {side} {run['run']}: {_weights(run['adapter'])}")
        if run["missing"]:
            lines.append(f"    missing, not read as zero: {', '.join(run['missing'])}")
    lines.append(
        f"  {a['shadow'] or 'the target itself'}, stated task: {'yes' if a['stated_task'] else 'no'}"
    )

    for name, arms in found["paired"].items():
        lines.append(f"  paired, {name} (b − a, exact, two-sided, uncorrected):")
        for arm, tests in arms.items():
            lines.extend(paired_of.render_pair(_label(name, arm), tests))
    return "\n".join(lines)


def _label(section: str, arm: str) -> str:
    """An arm's line: the comparison the card registered on it, or that it is described and not read."""
    registered = REGISTERED.get(arm) if section == REGISTERED_SECTION else None
    if registered is None:
        return f"{arm}  described, not a registered comparison"
    return f"{arm}  {registered} (registered; primary {PRIMARY})"


def _weights(adapter: dict | None) -> str:
    """Which weights answered a run: the base model, or the adapter by path and by what trained it."""
    if not adapter:
        return "the base model, no adapter"
    return (
        f"{adapter.get('path')} — repo {adapter.get('repo')}, corpus "
        f"{(adapter.get('corpus_hash') or '?')[:12]}, recipe {adapter.get('recipe_hash') or '?'}, "
        f"{adapter.get('steps')} step(s)"
    )
