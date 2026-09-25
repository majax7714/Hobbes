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
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from .e1 import CALLS, GMEM, ITERATE, META, ROWS

__all__ = ["BODY_KINDS", "COMPILED", "LOW_BIT", "figures", "pass_at_k", "render", "report"]

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
