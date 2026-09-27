"""**E1's readings**, written before the run and computed from the rows afterwards (§6, E1's card).

`report(run_dir)` reads a run directory and returns the figures the experiment exists to produce. It is a
reader and nothing else: **it computes nothing a row does not hold**, and a file that is not there is
**named in `missing`** rather than read as a zero — a run whose grading never happened and a run in which
nothing passed are two different results, and a report that cannot tell them apart is worse than none.

**Four figures per arm** (E1-d), each from round 0:

| figure | from |
|---|---|
| **pass@1** | the greedy sample (`sample` 0) |
| **pass@1(sampled)** | the mean pass rate over the *k* drawn samples |
| **pass@k** | the unbiased estimator `1 − C(n−c, k)/C(n, k)`, per cell and then averaged; at `n = k` it is any-pass |
| **per round** | for the iterate arms only: the share of chains that have passed by the end of each round, cumulative |

**Nothing is pooled that the card says to keep apart.** Every figure is broken down by ISA and by type,
SIMD accuracy being known to fall steeply by ISA (§12.2); `int8`, `uint8` and `bit1` each keep their own
row *and* are summed into a `low-bit` row, since no work in §12 grades quantised or binary kernels.
**Wrappers are a section of their own** and are never added to the real bodies: a one-statement wrapper is
not the task the experiment is about, and a pass rate that mixes the two is a number about the lattice's
shape rather than about the model.

Beside each figure go the class counts (`no-body`, `compile`, `invented`, `not-installed`, `wrong`, `edge`,
`pass`), G-hsr's invented names by bucket — G-hsr's own three and **`param`** (`e1.PARAM`), the runner's
fourth, which is a name the model renamed a parameter to and never an invented API, and is therefore
counted on a line of its own and never toward `intrinsic` — the G-reg rate **over the bodies that
compiled** — a body that never compiled has no init function to have got right — and the same pass rates
split by the cell's G-mem label, because §8 binds every number here to carry its G-mem reading beside it.
A probe under `gmem`'s evidence floor reads `no-evidence` in that split, never `memorised`.

Tokens, seconds and cost are the run's own `calls.jsonl` and are not re-derived from the rows, and
`max_tokens` is `meta.json`'s: a completion that stopped at the limit is a `no-body` about the limit and
not about the model, so the number the run asked at stands beside the figures it produced.

**E4's readings sit beside E1's** (:func:`e4_report`), because an E4 run's rows are E1's rows: a unit
stands where a cell does. Four things differ, and each is a section of its own rather than a pooling.
The rows are split **by unit kind** — cell, helper, init — since a `static inline` helper and a kernel are
not the same task, exactly as E1 keeps wrappers apart. A helper **no cell's gold body reaches** is
reported apart as :data:`UNEXERCISED`: it compiled and no slot ran it, so it has no pass rate to average
into the others, and a unit is counted there whenever *any* of its rows says so — the empty slot union is
a fact about the unit, not about a body. The **file-level** rows (`file_level.jsonl`) are printed as they
are, with the comparisons `e4.COMPARISONS` registers — `S-2 − S-0` and `S-5 − S-3` — paired by unit, all
computed from the rows. E4-f's two are over **every** unit; D-11's `S-2h` against `S-2` is over the
**helper** units, which is where the two arms differ at all.

**A comparison registered on one kind is printed twice**, and the second printing is a description. S-2h
sends a cell and the init exactly S-2's bytes (`e4.context`), so the same pair over the **cells** is the
sampler's own noise under two seeds and nothing else — which is what the helper reading has to be larger
than to say anything. It is printed beside it, labelled `described` (:data:`DESCRIBED_KIND`), and is never
read as a result.

And **S-2o is described, not tested** (E4-c): it is in no registered comparison, so what the report owes a
reader is what the arm actually carried. :func:`_own_shots` counts it off the run's own
`requests.jsonl` — how many cells carried 0, 1 or 2 own-pass shots, and **why each missing one was
missing** (`later-in-order`, `neighbour-failed`, `no-neighbour`, or the unit having no axis at all). It is
printed beside the arms and never turned into a p.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from . import e4 as e4_of
from .e1 import CALLS, GMEM, ITERATE, META, REQUESTS, ROWS

__all__ = [
    "BODY_KINDS",
    "COMPILED",
    "DESCRIBED_KIND",
    "LOW_BIT",
    "UNEXERCISED",
    "e4_render",
    "e4_report",
    "e4_units",
    "figures",
    "pass_at_k",
    "render",
    "report",
]

#: The kinds that are the experiment's result, and the kind reported apart.
BODY_KINDS = ("body", "impl")
WRAPPER_KINDS = ("wrapper",)

#: The types that are also summed into one row: §12 grades none of them anywhere.
LOW_BIT = ("int8", "uint8", "bit1")

#: The classes a body reached only by compiling. `no-body`, `compile` and `invented` did not, so G-reg —
#: which is a fact about the file the body went into — is not read over them.
COMPILED = ("not-installed", "wrong", "edge", "pass")

#: The label a cell whose probe had nothing to continue carries: not a G-mem reading, and never folded
#: into `unseen` (`gmem.run` marks those rows `evidence: False`).
NO_EVIDENCE = "no-evidence"

#: The kind a comparison registered on one kind is **also** read over, described: S-2h sends a cell the
#: same bytes S-2 does, so that reading is two seeds and nothing else — the noise the helper reading has to
#: stand above. It is a description and never a result.
DESCRIBED_KIND = "cell"

#: `grade.UNEXERCISED`, repeated rather than imported: `grade` pulls in the compiler and the differential,
#: and a report is read on a box that has neither. The string is the seam, and `test_grade.py` holds the
#: two together.
UNEXERCISED = "unexercised"


def pass_at_k(n: int, c: int, k: int) -> float | None:
    """The unbiased pass@k estimator `1 − C(n−c, k)/C(n, k)` for *c* passes in *n* samples.

    `None` when *n* is under *k*: with fewer samples than the figure is named for there is no estimate,
    and returning the any-pass rate under a pass@k heading would be a different number wearing this one's
    name. At `n = k` the estimator is exactly any-pass, which is the shape E1 runs at.
    """
    if n < k or k <= 0:
        return None
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def report(run_dir: Path | str) -> dict:
    """Every figure this run's rows support, per section and per arm, plus what was missing to read."""
    run_dir = Path(run_dir)
    missing: list[str] = []
    record = _json(run_dir / META, missing) or {}
    rows = _jsonl(run_dir / ROWS, missing)
    probes = _jsonl(run_dir / GMEM, missing)
    calls = _jsonl(run_dir / CALLS, missing)

    k = int(record.get("k") or 0)
    iterate = tuple(record.get("iterate") or ITERATE)
    arms = list(record.get("arms") or sorted({row["arm"] for row in rows if row.get("arm")}))
    labels = _labels(probes)

    return {
        "run": run_dir.name,
        "model": record.get("model"),
        "k": k,
        "max_tokens": (record.get("params") or {}).get("max_tokens"),
        "rounds": record.get("rounds"),
        "iterate": list(iterate),
        "p12": record.get("p12"),
        "target_sha": record.get("target_sha"),
        "missing": missing,
        "sections": {
            "bodies": _section([row for row in rows if row.get("kind") in BODY_KINDS], arms, k, iterate, labels),
            "wrappers": _section([row for row in rows if row.get("kind") in WRAPPER_KINDS], arms, k, iterate, labels),
        },
        "gmem": _gmem(probes),
        "totals": _totals(calls),
    }


def _labels(probes: list[dict]) -> dict[str, str]:
    """Each cell's G-mem label, with a probe that had nothing to continue named rather than scored."""
    return {
        probe["cell"]: (probe["label"] if probe.get("evidence") else NO_EVIDENCE)
        for probe in probes
        if probe.get("cell")
    }


def _section(rows: list[dict], arms: list[str], k: int, iterate: tuple[str, ...], labels: dict[str, str]) -> dict:
    """One section — real bodies, or wrappers — arm by arm. The two are never added together."""
    return {
        "rows": len(rows),
        "cells": len({row["cell"] for row in rows}),
        "arms": {
            arm: _arm([row for row in rows if row.get("arm") == arm], k, arm in iterate, labels)
            for arm in arms
            if any(row.get("arm") == arm for row in rows)
        },
    }


def _arm(rows: list[dict], k: int, iterating: bool, labels: dict[str, str]) -> dict:
    """One arm: the whole of it, then by ISA, then by type with the `low-bit` row beside its members."""
    first = [row for row in rows if row.get("round") == 0]
    types = sorted({row["type"] for row in first})
    by_type = {name: figures([row for row in first if row["type"] == name], k, labels) for name in types}
    low = [row for row in first if row["type"] in LOW_BIT]
    if low:
        by_type["low-bit"] = figures(low, k, labels)
    return {
        "cells": len({row["cell"] for row in first}),
        "overall": figures(first, k, labels),
        "by_isa": {
            isa: figures([row for row in first if row["isa"] == isa], k, labels)
            for isa in sorted({row["isa"] for row in first})
        },
        "by_type": by_type,
        "rounds": _rounds(rows) if iterating else None,
    }


def figures(rows: list[dict], k: int, labels: dict[str, str]) -> dict:
    """The four readings and what stands beside them, over one group of round-0 rows."""
    cells = sorted({row["cell"] for row in rows})
    greedy = {row["cell"]: row for row in rows if row.get("sample") == 0}
    drawn: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("sample", 0) > 0:
            drawn.setdefault(row["cell"], []).append(row)

    estimates = [
        value
        for cell in cells
        if (value := pass_at_k(len(drawn.get(cell, [])), _passes(drawn.get(cell, [])), k)) is not None
    ]
    return {
        "cells": len(cells),
        "rows": len(rows),
        "pass_at_1": _mean([1.0 if greedy[cell].get("class") == "pass" else 0.0 for cell in cells if cell in greedy]),
        "pass_at_1_sampled": _mean(
            [_passes(drawn[cell]) / len(drawn[cell]) for cell in cells if drawn.get(cell)]
        ),
        "pass_at_k": _mean(estimates),
        "pass_at_k_cells": len(estimates),
        "classes": dict(sorted(Counter(row.get("class") or "ungraded" for row in rows).items())),
        "invented": _invented(rows),
        "reg": _reg(rows),
        "gmem": _split(rows, cells, greedy, drawn, labels),
    }


def _split(rows, cells, greedy, drawn, labels) -> dict:
    """The same pass rates, split by the cell's G-mem label: every number carries its reading (§8)."""
    split: dict[str, dict] = {}
    for label in sorted({labels.get(cell, NO_EVIDENCE) for cell in cells}):
        named = [cell for cell in cells if labels.get(cell, NO_EVIDENCE) == label]
        split[label] = {
            "cells": len(named),
            "pass_at_1": _mean(
                [1.0 if greedy[cell].get("class") == "pass" else 0.0 for cell in named if cell in greedy]
            ),
            "pass_at_1_sampled": _mean(
                [_passes(drawn[cell]) / len(drawn[cell]) for cell in named if drawn.get(cell)]
            ),
        }
    return split


def _rounds(rows: list[dict]) -> list[dict]:
    """The iterate arm's cumulative pass rate after each round, over every chain — greedy and sampled.

    A chain is one (cell, sample). It has no rows after the round it passed in, which is why the figure is
    cumulative: the share that *have* passed by the end of round *r*, so round 0's figure is the one-shot
    result and stays visible beside the rest (E1-e).
    """
    chains = {(row["cell"], row["sample"]) for row in rows if row.get("round") == 0}
    if not chains:
        return []
    passed: set[tuple] = set()
    out = []
    for round_ in range(0, max(row.get("round", 0) for row in rows) + 1):
        at = [row for row in rows if row.get("round") == round_]
        passed |= {(row["cell"], row["sample"]) for row in at if row.get("class") == "pass"}
        out.append(
            {
                "round": round_,
                "chains": len(chains),
                "answered": len(at),
                "passed": len(passed),
                "rate": round(len(passed) / len(chains), 6),
                "classes": dict(sorted(Counter(row.get("class") or "ungraded" for row in at).items())),
            }
        )
    return out


def _passes(rows: list[dict]) -> int:
    return sum(1 for row in rows if row.get("class") == "pass")


def _invented(rows: list[dict]) -> dict:
    """G-hsr's names that resolve nowhere, by bucket then by name, with how often each was written."""
    buckets: dict[str, Counter] = {}
    for row in rows:
        for name in row.get("invented") or []:
            buckets.setdefault(name.get("bucket") or "other", Counter())[name["name"]] += 1
    return {bucket: dict(sorted(counts.items())) for bucket, counts in sorted(buckets.items())}


def _reg(rows: list[dict]) -> dict:
    """G-reg over the bodies that compiled. A body that did not has no build for the question to be about."""
    compiled = [row for row in rows if row.get("class") in COMPILED]
    held = sum(1 for row in compiled if row.get("reg") is True)
    return {"compiled": len(compiled), "held": held, "rate": _mean([1.0 if row.get("reg") else 0.0 for row in compiled])}


def _gmem(probes: list[dict]) -> dict | None:
    """How the cells fell out by label, and how many probes carried no evidence at all."""
    if not probes:
        return None
    return {
        "probes": len(probes),
        "labels": dict(sorted(Counter(
            probe["label"] if probe.get("evidence") else NO_EVIDENCE for probe in probes
        ).items())),
    }


def _totals(calls: list[dict]) -> dict | None:
    """The run's own spend, read from `calls.jsonl` and never re-derived from the rows."""
    if not calls:
        return None
    return {
        "calls": len(calls),
        "requests": sum(int(call.get("requests") or 0) for call in calls),
        "tokens_in": sum(int(call.get("tokens_in") or 0) for call in calls),
        "tokens_out": sum(int(call.get("tokens_out") or 0) for call in calls),
        "seconds": round(sum(float(call.get("seconds") or 0.0) for call in calls), 3),
        "cost": round(sum(float(call.get("cost") or 0.0) for call in calls), 6),
        "estimated": sum(1 for call in calls if call.get("cost_source") == "estimated"),
    }


def _mean(values: list[float]) -> float | None:
    """The mean, or `None` where there was nothing to take it over — never 0.0, which is a result."""
    return round(sum(values) / len(values), 6) if values else None


def _json(path: Path, missing: list[str]) -> dict | None:
    if not path.exists():
        missing.append(path.name)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path, missing: list[str]) -> list[dict]:
    if not path.exists():
        missing.append(path.name)
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# MARK: - E4's readings -


def e4_report(run_dir: Path | str) -> dict:
    """Every figure an E4 run's rows support: per arm, per unit kind, the file level, the comparisons.

    A reader and nothing else, as :func:`report` is: a file that is not there is named in `missing` and
    never read as a zero. The registered comparisons are paired **by unit** — `paired.paired` takes a
    unit where it takes a cell — and one whose arms a run has no rows for reads `missing`.
    """
    run_dir = Path(run_dir)
    missing: list[str] = []
    record = _json(run_dir / META, missing) or {}
    rows = _jsonl(run_dir / ROWS, missing)
    calls = _jsonl(run_dir / CALLS, missing)
    levels = _jsonl(run_dir / e4_of.FILE_LEVEL, missing)
    # the requests, because S-2o's own-shot counts are a fact about what was *sent* and no row holds it.
    # `parser.jsonl` is not read here: `meta.json`'s own `parser` block names the model and the digest of
    # the fields the plan was built from, and a run that asked for no S-5 is missing nothing by not having one
    requests = _jsonl(run_dir / REQUESTS, missing)

    k = int(record.get("k") or 0)
    arms = list(record.get("arms") or sorted({row["arm"] for row in rows if row.get("arm")}))
    first = [row for row in rows if row.get("round") == 0 and row.get("arm")]

    return {
        "run": run_dir.name,
        "model": record.get("model"),
        "k": k,
        "max_tokens": (record.get("params") or {}).get("max_tokens"),
        "rung": record.get("rung"),
        "isa": record.get("isa"),
        "file": record.get("file"),
        "p12": record.get("p12"),
        "decomposition": record.get("decomposition"),
        "cycles": record.get("cycles") or [],
        "waves": record.get("waves") or [],
        "parser": record.get("parser"),
        "units": len(record.get("units") or []),
        "target_sha": record.get("target_sha"),
        "missing": missing,
        "arms": {
            arm: _e4_arm([row for row in first if row["arm"] == arm], k)
            for arm in arms
            if any(row["arm"] == arm for row in first)
        },
        "file_level": levels,
        "comparisons": _e4_comparisons(first, k),
        "own_shots": _own_shots(requests),
        "totals": _totals(calls),
    }


def _e4_arm(rows: list[dict], k: int) -> dict:
    """One arm: the units it answered, split by kind, with the unexercised ones counted apart."""
    apart = {row["cell"] for row in rows if row.get("class") == UNEXERCISED}
    graded = [row for row in rows if row["cell"] not in apart]
    kinds = {
        kind: figures([row for row in graded if row.get("kind") == kind], k, {})
        for kind in e4_of.KINDS
        if any(row.get("kind") == kind for row in graded)
    }
    return {
        "units": len({row["cell"] for row in rows}),
        "by_kind": kinds,
        "unexercised": {
            "units": len(apart),
            "names": sorted(apart),
            "rows": sum(1 for row in rows if row["cell"] in apart),
            "classes": dict(sorted(Counter(row.get("class") or "ungraded" for row in rows if row["cell"] in apart).items())),
        },
    }


def e4_units(rows: list[dict], kind: str | None = None) -> dict[str, dict[str, dict]]:
    """`arm -> unit -> {"greedy", "drawn"}` over E4 rows: `paired.paired`'s own shape, by unit.

    *kind* keeps one of :data:`lattice.e4.KINDS` and `None` keeps every unit. Which rows to hand in is the
    caller's (the report's figures are round 0 with an arm), so that this says nothing about which rows a
    reading is over and `compare.e4_compare` can read the same shape off another run's rows.
    """
    by_arm: dict[str, dict[str, dict]] = {}
    for row in rows:
        if kind is not None and row.get("kind") != kind:
            continue
        unit = by_arm.setdefault(row["arm"], {}).setdefault(row["cell"], {"greedy": None, "drawn": []})
        passed = row.get("class") == "pass"
        if row.get("sample") == 0:
            unit["greedy"] = passed
        else:
            unit["drawn"].append(passed)
    return by_arm


def _e4_comparisons(rows: list[dict], k: int) -> dict:
    """Every registered comparison, paired by unit, or the reason there is no number yet.

    A comparison scoped to a kind is read over that kind **and** printed a second time over
    :data:`DESCRIBED_KIND` as the noise read, which is a description and is labelled one.
    """
    found: dict[str, dict] = {}
    for first, second, kind in e4_of.COMPARISONS:
        found[_comparison_label(first, second, kind, registered=True)] = _paired_units(
            rows, first, second, kind, k
        )
        if kind is not None:
            found[_comparison_label(first, second, DESCRIBED_KIND, registered=False)] = _paired_units(
                rows, first, second, DESCRIBED_KIND, k
            )
    return found


def _comparison_label(first: str, second: str, kind: str | None, registered: bool) -> str:
    """One comparison's line: the delta's direction, the units it is over, and whether it was registered.

    The described label may say *identical prompts* because that is what a kind-scoped comparison is: its
    two arms differ on the scoped kind and nowhere else (D-11's S-2h is S-2 for a cell and for the init,
    which `test_e4.py` holds byte for byte), so every other kind's pair is two seeds of one prompt.
    """
    if kind is None:
        return f"{second} − {first}"
    if registered:
        return f"{second} − {first} ({kind} units, registered)"
    return f"{second} − {first} ({kind} units, described: identical prompts under two seeds)"


def _paired_units(rows: list[dict], first: str, second: str, kind: str | None, k: int) -> dict:
    """One comparison's three tests over the units of *kind*, or which arm the run has no rows for."""
    # `paired` reads this module's section kinds, so the two may not import each other at the top
    from . import paired as paired_of

    by_arm = e4_units(rows, kind)
    for arm in (first, second):
        if arm not in by_arm:
            return {"missing": f"the run has no{'' if kind is None else f' {kind} unit'} rows for {arm}"}
    return paired_of.paired(by_arm[first], by_arm[second], k)


def _own_shots(requests: list[dict]) -> dict | None:
    """What S-2o carried, off the run's own requests: the own-shot counts, and why each missing one was.

    Greedy requests only, because every sample of one unit shares that unit's shots — the shot is the
    neighbour's greedy body, not one per draw — so counting the drawn requests too would multiply every
    figure here by `k + 1` and say nothing more. `None` where the run has no S-2o request at all: a run
    that did not carry the arm has no counts to read, which is not the same as carrying none.
    """
    greedy = [
        request
        for request in requests
        if request.get("arm") in e4_of.OWN_ARMS and request.get("sample") == 0 and request.get("round") == 0
    ]
    if not greedy:
        return None
    cells = [request for request in greedy if request.get("kind") == "cell"]
    carried = Counter(len(request.get("own") or []) for request in cells)
    reasons = Counter(
        note.get("reason") for request in greedy for note in (request.get("own_notes") or [])
    )
    return {
        "units": len(greedy),
        "cells": len(cells),
        "carried": {str(count): carried.get(count, 0) for count in range(0, len(e4_of.OWN_AXES) + 1)},
        "missing": dict(sorted(reasons.items())),
    }


def e4_render(found: dict) -> str:
    """E4's report as a table: one block per arm, the file level, then the registered comparisons."""
    # the same import rule as above, and for the same reason
    from . import paired as paired_of

    decomposition = found.get("decomposition") or {}
    lines = [
        f"E4 {found['run']} — {found.get('model') or 'no model recorded'} "
        f"({found.get('rung')} on {found.get('file') or found.get('isa')}, k={found.get('k')}, "
        f"max_tokens={found.get('max_tokens') or '?'}, P12 {found.get('p12')})",
        f"units: {found.get('units')}; largest prompt {decomposition.get('largest_prompt_chars')} chars "
        f"against the file's {decomposition.get('file_chars')} "
        f"({'every window smaller' if decomposition.get('every_window_smaller') else 'NOT every window smaller'})",
    ]
    if found.get("target_sha"):
        lines.append(f"target {found['target_sha'][:12]}")
    if found.get("parser"):
        block = found["parser"]
        lines.append(
            f"parser: {block['parsed']} of {block['units']} unit(s) parsed by "
            f"{block.get('model') or ', '.join(block.get('models') or ())} ({(block.get('sha256') or '')[:12]})"
        )
    for cycle in found.get("cycles") or []:
        lines.append(f"cycle, one group in file order: {', '.join(cycle)}")
    if found["missing"]:
        lines.append(f"missing, not read as zero: {', '.join(found['missing'])}")

    lines.append("")
    if not found["arms"]:
        lines.append("(no rows)")
    else:
        lines.append(f"  {'arm':<8}{'kind':<14}{'units':>6}{'pass@1':>9}{'pass@1(s)':>11}{'pass@k':>9}  classes")
    for arm, data in found["arms"].items():
        for kind, figure in data["by_kind"].items():
            lines.append(_figure_line(arm, kind, figure))
        apart = data["unexercised"]
        if apart["units"]:
            lines.append(
                f"  {'':<8}{UNEXERCISED:<14}{apart['units']:>6}"
                f"{'-':>9}{'-':>11}{'-':>9}  apart: {', '.join(apart['names'])}"
            )

    if found["file_level"]:
        lines.append("")
        lines.append("file level (greedy bodies where the unit passed, gold elsewhere):")
        for row in found["file_level"]:
            lines.append(
                f"  {row['arm']:<8}{row['units_passed']:>3} of {row['units']:<4}"
                f"  {row.get('class') or '-':<14}G-diff {'pass' if row.get('diff_pass') else 'fail'}"
                f"  G-reg {'pass' if row.get('reg') else 'fail'}  → {row.get('written') or '-'}"
            )

    own = found.get("own_shots")
    if own:
        lines.append("")
        lines.append(
            f"{', '.join(e4_of.OWN_ARMS)}, described and not tested — the student's own passed bodies as "
            f"shots, over {own['cells']} cell(s)"
            + (f" in {len(found.get('waves') or ())} wave(s)" if found.get("waves") else "")
            + ":"
        )
        for count in sorted(own["carried"], reverse=True):
            lines.append(f"  cells carrying {count} own shot(s): {own['carried'][count]}")
        lines.append(
            # by reason and not by axis, because one of the reasons is the unit having no axis at all
            "  no own shot, by reason: "
            + (", ".join(f"{reason} {n}" for reason, n in own["missing"].items()) or "none missing")
        )

    lines.append("")
    lines.append(
        "comparisons, paired by unit (exact, two-sided, uncorrected); each line says which units it is "
        "over and whether it was registered:"
    )
    for label, tests in found["comparisons"].items():
        if "missing" in tests:
            lines.append(f"    {label}  — {tests['missing']}")
            continue
        lines += paired_of.render_pair(label, tests)

    if found["totals"]:
        totals = found["totals"]
        lines.append("")
        lines.append(
            f"spend: {totals['calls']} call(s), {totals['requests']} request(s), "
            f"{totals['tokens_in']} in / {totals['tokens_out']} out, {totals['seconds']}s, "
            f"${totals['cost']:.4f}" + (f" ({totals['estimated']} estimated)" if totals["estimated"] else "")
        )
    return "\n".join(lines)


# MARK: - the table -


def render(found: dict) -> str:
    """The report as a table: one block per section, one row per arm, then its ISA and type breakdowns."""
    lines = [
        f"E1 {found['run']} — {found.get('model') or 'no model recorded'} "
        f"(k={found.get('k')}, max_tokens={found.get('max_tokens') or '?'}, "
        f"rounds={found.get('rounds')}, P12 {found.get('p12')})"
    ]
    if found.get("target_sha"):
        lines.append(f"target {found['target_sha'][:12]}")
    if found["missing"]:
        lines.append(f"missing, not read as zero: {', '.join(found['missing'])}")

    for name, section in found["sections"].items():
        lines.append("")
        lines.append(f"{name}: {section['cells']} cell(s), {section['rows']} row(s)")
        if not section["arms"]:
            lines.append("  (no rows)")
            continue
        lines.append(f"  {'arm':<8}{'group':<14}{'cells':>6}{'pass@1':>9}{'pass@1(s)':>11}{'pass@k':>9}  classes")
        for arm, data in section["arms"].items():
            lines.append(_figure_line(arm, "all", data["overall"]))
            for isa, figure in data["by_isa"].items():
                lines.append(_figure_line("", f"isa {isa}", figure))
            for type_, figure in data["by_type"].items():
                lines.append(_figure_line("", f"type {type_}", figure))
            for label, split in data["overall"]["gmem"].items():
                lines.append(
                    f"  {'':<8}{'gmem ' + label:<14}{split['cells']:>6}"
                    f"{_number(split['pass_at_1']):>9}{_number(split['pass_at_1_sampled']):>11}{'':>9}"
                )
            if data["overall"]["invented"]:
                for bucket, names in data["overall"]["invented"].items():
                    written = ", ".join(f"{n}×{c}" for n, c in names.items())
                    lines.append(f"  {'':<8}invented {bucket}: {written}")
            reg = data["overall"]["reg"]
            lines.append(f"  {'':<8}G-reg: {reg['held']} of {reg['compiled']} compiled ({_number(reg['rate'])})")
            for entry in data["rounds"] or []:
                lines.append(
                    f"  {'':<8}round {entry['round']}: {entry['passed']} of {entry['chains']} chain(s) "
                    f"passed ({_number(entry['rate'])}), {entry['answered']} answered"
                )

    if found["gmem"]:
        lines.append("")
        lines.append(
            "G-mem: " + ", ".join(f"{label} {count}" for label, count in found["gmem"]["labels"].items())
            + f" over {found['gmem']['probes']} probe(s)"
        )
    if found["totals"]:
        totals = found["totals"]
        lines.append(
            f"spend: {totals['calls']} call(s), {totals['requests']} request(s), "
            f"{totals['tokens_in']} in / {totals['tokens_out']} out, {totals['seconds']}s, "
            f"${totals['cost']:.4f}" + (f" ({totals['estimated']} estimated)" if totals["estimated"] else "")
        )
    return "\n".join(lines)


def _figure_line(arm: str, group: str, figure: dict) -> str:
    classes = " ".join(f"{name}={count}" for name, count in figure["classes"].items())
    return (
        f"  {arm:<8}{group:<14}{figure['cells']:>6}{_number(figure['pass_at_1']):>9}"
        f"{_number(figure['pass_at_1_sampled']):>11}{_number(figure['pass_at_k']):>9}  {classes}"
    )


def _number(value: float | None) -> str:
    """A figure there was nothing to compute reads `-`, never `0.00`."""
    return "-" if value is None else f"{value:.2f}"
