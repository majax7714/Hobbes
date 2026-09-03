"""Laying NLL runs against H-TTT-1 (ADR-099 §4.3): four arms, paired by unit.

An NLL run (``modal_ttt.py nll``) scores every unit under its bare and
its aided prompt, with or without an adapter. Two runs — base and
adapter — give the four arms:

| arm | adapter | prompt |
|---|---|---|
| A0 | no  | bare  |
| A1 | no  | aided |
| A2 | yes | bare  |
| A3 | yes | aided |

Every comparison is **paired by unit** and reported with a paired
bootstrap over units (seeded, so the report is reproducible): the mean
difference, its 95% interval, and the two-sided bootstrap *p* — the
number the kill criterion reads. The table is split by the C-84
population (units whose file the base graph knew, and the rest),
because for the rest A1 and A0 differ by boilerplate alone.

Computes; interprets nothing — the kill criterion is applied by the
reader against the printed numbers.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

ARMS = {"A0": (False, "bare"), "A1": (False, "aided"), "A2": (True, "bare"), "A3": (True, "aided")}
#: The design's primary comparison, then the rest, worst-case last.
COMPARISONS = (("A2", "A1"), ("A1", "A0"), ("A2", "A0"), ("A3", "A1"), ("A3", "A2"))


@dataclass
class Paired:
    n: int
    mean_a: float
    mean_b: float
    delta: float          # mean(a − b); negative means arm a is lower (better)
    ci_low: float
    ci_high: float
    p: float              # two-sided paired bootstrap
    wins: int             # units where a < b (lower NLL)
    higher: int = 0       # units where a > b (higher score)


def arm_table(base_run: dict | None, adapter_run: dict | None) -> dict[str, dict[str, float]]:
    """``arm -> unit id -> mean NLL`` from the two runs (either may be absent)."""
    out: dict[str, dict[str, float]] = {}
    for arm, (with_adapter, prompt) in ARMS.items():
        run = adapter_run if with_adapter else base_run
        if run is None:
            continue
        out[arm] = {r["unit"]: r["nll_mean"] for r in run.get("rows", [])
                    if r.get("prompt") == prompt and not r.get("skipped")}
    return out


def paired(a: dict[str, float], b: dict[str, float], units: list[str] | None = None,
           resamples: int = 5_000, seed: int = 0) -> Paired | None:
    """Paired bootstrap of mean(a − b) over the units both arms scored."""
    ids = sorted(set(a) & set(b) & (set(units) if units is not None else set(a)))
    if not ids:
        return None
    diffs = [a[i] - b[i] for i in ids]
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(resamples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    observed = sum(diffs) / n
    # Two-sided p: the bootstrap distribution's mass on the far side of zero, doubled.
    tail = min(sum(1 for m in means if m >= 0), sum(1 for m in means if m <= 0)) / resamples
    return Paired(n=n, mean_a=statistics.mean(a[i] for i in ids), mean_b=statistics.mean(b[i] for i in ids),
                  delta=observed, ci_low=means[int(0.025 * resamples)], ci_high=means[int(0.975 * resamples) - 1],
                  p=min(1.0, 2 * tail), wins=sum(1 for d in diffs if d < 0), higher=sum(1 for d in diffs if d > 0))


def report(base_run: dict | None, adapter_run: dict | None, known: set[str] | None = None,
           resamples: int = 5_000, seed: int = 0) -> dict:
    """Every comparison over all units and, when *known* is given, over
    the C-84 split; returns a serialisable dict."""
    table = arm_table(base_run, adapter_run)
    all_ids = sorted(set().union(*table.values())) if table else []
    populations = {"all": all_ids}
    if known is not None:
        populations["context-known"] = [i for i in all_ids if i in known]
        populations["no-known-file"] = [i for i in all_ids if i not in known]
    out: dict = {"arms": {arm: {"n": len(v), "mean": round(statistics.mean(v.values()), 5) if v else None}
                          for arm, v in table.items()},
                 "populations": {k: len(v) for k, v in populations.items()}, "comparisons": {}}
    for pop, ids in populations.items():
        for a, b in COMPARISONS:
            if a in table and b in table:
                p = paired(table[a], table[b], ids, resamples, seed)
                if p is not None:
                    out["comparisons"][f"{pop}:{a}-{b}"] = p.__dict__
    return out


def format_report(rep: dict) -> str:
    lines = ["arm   n     mean NLL"]
    for arm, row in rep["arms"].items():
        lines.append(f"{arm:4} {row['n']:4d}   {row['mean'] if row['mean'] is not None else '-'}")
    lines.append("")
    lines.append("comparison                  n   mean a    mean b    Δ(a−b)     95% CI                 p      a<b")
    for key, p in rep["comparisons"].items():
        lines.append(f"{key:26} {p['n']:4d}  {p['mean_a']:.4f}   {p['mean_b']:.4f}   {p['delta']:+.4f}   "
                     f"[{p['ci_low']:+.4f}, {p['ci_high']:+.4f}]   {p['p']:.4f}  {p['wins']}/{p['n']}")
    lines.append("")
    lines.append("Δ < 0 means arm a's gold-diff NLL is lower. H-TTT-1's kill criterion reads A2−A0 on ≥ 40 units "
                 "(p < 0.05, paired bootstrap); the primary comparison is A2−A1. Populations follow C-84.")
    return "\n".join(lines)


# ---------------------------------------------------------------- navigation

def nav_table(runs: dict[str, dict]) -> dict[str, dict[str, dict[str, float]]]:
    """``arm -> family -> item key -> score`` from `ttt_probe.py nav` outputs."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    for arm, run in runs.items():
        for r in run.get("rows", []):
            out.setdefault(arm, {}).setdefault(r["family"], {})[f"{r['family']}\n{r['symbol']}"] = r["score"]
    return out


def nav_report(runs: dict[str, dict], baseline: str = "A0", resamples: int = 5_000, seed: int = 0) -> dict:
    """Per-arm, per-family mean scores; the absent family's false-acceptance
    rate; and every other arm paired against *baseline* per family and
    over all navigation (non-absent) items. Same bootstrap as the NLL
    report, over items instead of units."""
    table = nav_table(runs)
    families = sorted({f for arm in table.values() for f in arm})
    out: dict = {"arms": {}, "comparisons": {}}
    for arm, fams in table.items():
        row = {f: {"n": len(v), "mean": round(statistics.mean(v.values()), 4)} for f, v in fams.items()}
        nav = [s for f, v in fams.items() if f != "absent" for s in v.values()]
        row["navigation"] = {"n": len(nav), "mean": round(statistics.mean(nav), 4) if nav else None}
        if "absent" in fams:
            row["absent_false_acceptance"] = round(1 - statistics.mean(fams["absent"].values()), 4)
        out["arms"][arm] = row
    if baseline not in table:
        return out
    for arm in table:
        if arm == baseline:
            continue
        for fam in families + ["navigation"]:
            if fam == "navigation":
                a = {k: s for f, v in table[arm].items() if f != "absent" for k, s in v.items()}
                b = {k: s for f, v in table[baseline].items() if f != "absent" for k, s in v.items()}
            else:
                a, b = table[arm].get(fam, {}), table[baseline].get(fam, {})
            p = paired(a, b, None, resamples, seed)
            if p is not None:
                out["comparisons"][f"{arm}-{baseline}:{fam}"] = p.__dict__
    return out


def format_nav_report(rep: dict) -> str:
    fams = sorted({f for row in rep["arms"].values() for f in row if f not in ("navigation", "absent_false_acceptance")})
    lines = ["arm   " + "".join(f"{f:>10}" for f in fams) + f"{'nav':>10}{'absent FA':>11}"]
    for arm, row in rep["arms"].items():
        cells = "".join(f"{row[f]['mean']:>10.3f}" if f in row else f"{'-':>10}" for f in fams)
        nav = row["navigation"]["mean"]
        fa = row.get("absent_false_acceptance")
        lines.append(f"{arm:5} {cells}{(nav if nav is not None else 0):>10.3f}{(fa if fa is not None else float('nan')):>11.3f}")
    lines.append("")
    lines.append("comparison                   n    Δ(a−b)     95% CI                 p      a>b   a<b")
    for key, p in rep["comparisons"].items():
        lines.append(f"{key:28} {p['n']:5d}  {p['delta']:+.4f}   [{p['ci_low']:+.4f}, {p['ci_high']:+.4f}]   "
                     f"{p['p']:.4f}  {p['higher']:4d}  {p['wins']:4d}")
    lines.append("")
    lines.append("Scores: F1 over what a reply names (defines: the path; absent: a refusal; 'none recorded': naming nothing else). "
                 "Δ > 0 means arm a scores higher. absent FA = false-acceptance rate on distractors (ADR-099 §4.5).")
    return "\n".join(lines)
