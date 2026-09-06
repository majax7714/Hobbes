"""``atlas0 report``: the tables of §6.1–§6.6 over a directory of cells (steps 5–6).

A cell is ``<runs>/<block>-<arm>-s<seed>/`` as ``atlas0.train.run``
writes it. Cells are grouped by (block, arm) and every number is
reported as mean and spread (min–max) across the seeds present, so
that §6.6's gate can be applied: a difference between blocks smaller
than the spread within either is *not separable at n seeds*. Nothing
here interprets a number; the atlas entry is written by a person from
these tables.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .acts import COLUMNS

_CELL = re.compile(r"^(B[123])-(none|phrase|lived|lived\+phrase)-s(\d+)$")

ROWS = ("dense-real", "sparse-real", "mid", "module-infer",
        "absent-near/trained", "absent-near/held-out", "absent-far/trained", "absent-far/held-out")
# v1 relation-absence: the secondary rows by whether the symbol has the relation.
SECONDARY_ROWS = ("dense-real/with", "dense-real/without", "mid/with", "mid/without", "sparse-real/with", "sparse-real/without",
                  "absent-near/trained", "absent-near/held-out", "absent-far/trained", "absent-far/held-out")


def load_cells(runs: Path) -> list[dict]:
    cells = []
    for d in sorted(runs.iterdir()):
        m = _CELL.match(d.name)
        if not m or not (d / "report.json").exists():
            continue
        cells.append({"block": m.group(1), "arm": m.group(2), "seed": int(m.group(3)),
                      "manifest": json.loads((d / "manifest.json").read_text()),
                      "report": json.loads((d / "report.json").read_text())})
    return cells


def _shares(matrix: dict, row: str) -> dict[str, float]:
    r = matrix["rows"].get(row)
    if not r:
        return {}
    n = sum(r.values())
    out = {c: r[c] / n for c in COLUMNS}
    e = matrix["extra"][row]
    wrong = r["ANSWER-wrong"]
    out["sibling-share-of-wrong"] = e.get("wrong-sibling", 0) / wrong if wrong else 0.0
    return out


def cell_measures(cell: dict) -> dict[str, float]:
    """One flat dict of the numbers a cell contributes to every table."""
    rep = cell["report"]
    prim = rep["confusion"]["primary"]
    out: dict[str, float] = {}
    for row in ROWS:
        for c, v in _shares(prim, row).items():
            out[f"{row}|{c}"] = v
    out["probe|best_test"] = rep["probe"]["best_test"]
    out["probe|chance"] = rep["probe"]["chance"]
    out["probe|best_layer"] = rep["probe"]["best_layer"]
    au = rep["authority"]
    for k in ("mi_act_probed", "mi_act_true", "mi_act_entropy", "mi_probed_true"):
        out[f"authority|{k}"] = au[k]
    for k, v in rep["inversion"].items():
        out[f"inversion|{k}|gold"] = v["gold"]
        out[f"inversion|{k}|context"] = v["context"]
    for d, c in rep["sparse_by_nearest_dense_distance"].items():
        n = c.get("n", 0)
        if n:
            out[f"sparse_by_distance|{d}|correct"] = c.get("ANSWER-correct", 0) / n
            out[f"sparse_by_distance|{d}|n"] = n
    for kind, m in rep.get("secondary_by_kind", {}).items():
        for row in m["rows"]:
            s = _shares(m, row)
            out[f"secondary|{kind}|{row}|ANSWER-correct"] = s["ANSWER-correct"]
            out[f"secondary|{kind}|{row}|UNDEFINED"] = s["UNDEFINED"]
            out[f"secondary|{kind}|{row}|n"] = m["extra"][row]["n"]
    # v1 hold-out: the primary items in a seen phrasing, beside the held-out one above.
    if "primary_seen" in rep["confusion"]:
        for row in ROWS:
            for c, v in _shares(rep["confusion"]["primary_seen"], row).items():
                out[f"primary_seen|{row}|{c}"] = v
    man = cell["manifest"]
    out["train|dense_final"] = man["final"]["dense_correct"]
    out["train|tokens_per_s"] = man["tokens_per_s"]
    out["train|cost_usd_assumed"] = man.get("container", {}).get("cost_usd_assumed", 0.0)
    return out


def curve(cells: list[dict]) -> dict:
    """§6.4 over the checkpoints: per group and step, the mean context and gold
    rates of every inversion variant the checkpoints read (``quick_eval``)."""
    groups: dict[str, dict[int, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for c in cells:
        g = f"{c['block']}/{c['arm']}"
        for ck in c["manifest"].get("checkpoints", []):
            for variant, v in ck.get("inversion", {}).items():
                groups[g][ck["step"]][f"{variant}|gold"].append(v["gold"])
                if v.get("context") is not None:
                    groups[g][ck["step"]][f"{variant}|context"].append(v["context"])
            groups[g][ck["step"]]["dense_correct"].append(ck.get("dense_correct") or 0.0)
    return {g: {step: {k: round(sum(v) / len(v), 4) for k, v in ks.items()} for step, ks in sorted(steps.items())}
            for g, steps in groups.items()}


def aggregate(cells: list[dict]) -> dict:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cells:
        groups[(c["block"], c["arm"])].append(cell_measures(c))
    out = {}
    for (block, arm), ms in sorted(groups.items()):
        keys = sorted(set().union(*(m.keys() for m in ms)))
        agg = {}
        for k in keys:
            vals = [m[k] for m in ms if k in m]
            agg[k] = {"mean": round(sum(vals) / len(vals), 4), "min": round(min(vals), 4), "max": round(max(vals), 4), "n": len(vals)}
        out[f"{block}/{arm}"] = agg
    return out


def separable(agg: dict, key: str, a: str, b: str) -> dict | None:
    """§6.6: is the difference between groups ``a`` and ``b`` on ``key`` outside both spreads?"""
    if a not in agg or b not in agg or key not in agg[a] or key not in agg[b]:
        return None
    x, y = agg[a][key], agg[b][key]
    diff = abs(x["mean"] - y["mean"])
    spread = max(x["max"] - x["min"], y["max"] - y["min"])
    return {"diff": round(diff, 4), "spread": round(spread, 4), "separable": diff > spread and min(x["n"], y["n"]) > 1,
            "seeds": min(x["n"], y["n"])}


def _fmt(v: dict | None) -> str:
    if v is None:
        return "—"
    if v["n"] == 1:
        return f"{v['mean']:.2f}"
    return f"{v['mean']:.2f} [{v['min']:.2f}–{v['max']:.2f}]"


def render(agg: dict) -> str:
    """Markdown: the §6.1 matrix per group, then the §6.2–6.5 summary rows."""
    groups = list(agg)
    lines = []
    lines.append("## §6.1 act × class (share of the row; mean [min–max] over seeds)\n")
    for g in groups:
        a = agg[g]
        n = next(iter(a.values()))["n"]
        lines.append(f"### {g} — {n} seed(s)\n")
        lines.append("| row | ANSWER-correct | ANSWER-wrong | sibling share of wrong | CANDIDATES | UNDEFINED | UNKNOWN | malformed |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for row in ROWS:
            if f"{row}|ANSWER-correct" not in a:
                continue
            cand = a.get(f"{row}|CANDIDATES-with", {"mean": 0, "min": 0, "max": 0, "n": n})
            lines.append(f"| {row} | {_fmt(a.get(f'{row}|ANSWER-correct'))} | {_fmt(a.get(f'{row}|ANSWER-wrong'))} | "
                         f"{_fmt(a.get(f'{row}|sibling-share-of-wrong'))} | {_fmt(cand)} | {_fmt(a.get(f'{row}|UNDEFINED'))} | "
                         f"{_fmt(a.get(f'{row}|UNKNOWN'))} | {_fmt(a.get(f'{row}|malformed'))} |")
        lines.append("")
    lines.append("## §6.2–6.3 probe and authority\n")
    lines.append("| group | probe test | chance | best layer | MI(act;probed) | MI(act;true) | MI(act;entropy) | MI(probed;true) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for g in groups:
        a = agg[g]
        lines.append(f"| {g} | {_fmt(a.get('probe|best_test'))} | {_fmt(a.get('probe|chance'))} | {_fmt(a.get('probe|best_layer'))} | "
                     f"{_fmt(a.get('authority|mi_act_probed'))} | {_fmt(a.get('authority|mi_act_true'))} | "
                     f"{_fmt(a.get('authority|mi_act_entropy'))} | {_fmt(a.get('authority|mi_probed_true'))} |")
    lines.append("\n## §6.4 inversion (final checkpoint; gold = answered the parametric value, context = answered the context's value)\n")
    lines.append("| group | C+S none gold | C+S support gold | C+S conflict gold | C+S conflict context | C-only support gold | C-only conflict context |")
    lines.append("|---|---|---|---|---|---|---|")
    for g in groups:
        a = agg[g]
        f = lambda k: _fmt(a.get(f"inversion|{k}"))
        lines.append(f"| {g} | {f('C+S/none|gold')} | {f('C+S/support|gold')} | {f('C+S/conflict|gold')} | {f('C+S/conflict|context')} | "
                     f"{f('C-only/support|gold')} | {f('C-only/conflict|context')} |")
    lines.append("\n## §6.5 sparse-real accuracy by stem distance to the nearest dense-real; module inference\n")
    lines.append("| group | d=1 | d=2 | d=3 | d=4 | module-infer correct |")
    lines.append("|---|---|---|---|---|---|")
    for g in groups:
        a = agg[g]
        f = lambda d: _fmt(a.get(f"sparse_by_distance|{d}|correct"))
        lines.append(f"| {g} | {f(1)} | {f(2)} | {f(3)} | {f(4)} | {_fmt(a.get('module-infer|ANSWER-correct'))} |")
    sec = sorted({k.split("|")[1] for g in groups for k in agg[g] if k.startswith("secondary|")})
    sec_rows = [r for r in SECONDARY_ROWS if any(f"secondary|{k}|{r}|n" in agg[g] for g in groups for k in sec)]
    if sec_rows and any("/with" in r or "/without" in r for r in sec_rows):
        lines.append("\n## secondary queries by relation (v1 relation absence): ANSWER-correct / UNDEFINED share of the row\n")
        lines.append("| group | kind | " + " | ".join(sec_rows) + " |")
        lines.append("|---|---|" + "---|" * len(sec_rows))
        for g in groups:
            a = agg[g]
            for kind in sec:
                cells_ = []
                for r in sec_rows:
                    ac, un = a.get(f"secondary|{kind}|{r}|ANSWER-correct"), a.get(f"secondary|{kind}|{r}|UNDEFINED")
                    cells_.append("—" if ac is None else f"{_fmt(ac)} / {_fmt(un)}")
                lines.append(f"| {g} | {kind} | " + " | ".join(cells_) + " |")
    if any(k.startswith("primary_seen|") for g in groups for k in agg[g]):
        lines.append("\n## held-out query phrasing (primary) against a seen one (primary_seen): ANSWER-correct / UNDEFINED\n")
        rows = [r for r in ROWS if any(f"primary_seen|{r}|ANSWER-correct" in agg[g] for g in groups)]
        lines.append("| group | phrasing | " + " | ".join(rows) + " |")
        lines.append("|---|---|" + "---|" * len(rows))
        for g in groups:
            a = agg[g]
            for label, prefix in (("held-out", ""), ("seen", "primary_seen|")):
                lines.append(f"| {g} | {label} | " + " | ".join(
                    f"{_fmt(a.get(f'{prefix}{r}|ANSWER-correct'))} / {_fmt(a.get(f'{prefix}{r}|UNDEFINED'))}" for r in rows) + " |")
    lines.append("\n## training\n")
    lines.append("| group | held-out dense at the end | tokens/s | cost (assumed $) |")
    lines.append("|---|---|---|---|")
    for g in groups:
        a = agg[g]
        lines.append(f"| {g} | {_fmt(a.get('train|dense_final'))} | {_fmt(a.get('train|tokens_per_s'))} | {_fmt(a.get('train|cost_usd_assumed'))} |")
    return "\n".join(lines) + "\n"


def render_curve(cv: dict) -> str:
    """§6.4 across checkpoints: one table per group, a column per step."""
    lines = ["## §6.4 inversion curve over checkpoints (mean over seeds)\n"]
    for g, steps in cv.items():
        keys = ["dense_correct", "C+S/support|gold", "C+S/conflict|gold", "C+S/conflict|context", "C-only/support|gold",
                "C-only/conflict|context"]
        cols = list(steps)
        lines.append(f"### {g}\n")
        lines.append("| measure | " + " | ".join(str(c) for c in cols) + " |")
        lines.append("|---|" + "---|" * len(cols))
        for k in keys:
            vals = [steps[c].get(k) for c in cols]
            if all(v is None for v in vals):
                continue
            lines.append(f"| {k} | " + " | ".join("—" if v is None else f"{v:.2f}" for v in vals) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def gate(agg: dict, keys: tuple[str, ...] = ("sparse-real|ANSWER-correct", "sparse-real|UNDEFINED",
                                             "absent-near/held-out|UNDEFINED", "absent-far/held-out|UNDEFINED",
                                             "absent-near/held-out|sibling-share-of-wrong", "probe|best_test",
                                             "authority|mi_act_probed")) -> list[dict]:
    """§6.6 over the primary comparisons: B1 vs B3 and B2 vs B3 within each arm, on the named keys."""
    out = []
    arms = sorted({g.split("/")[1] for g in agg})
    for arm in arms:
        for a, b in (("B1", "B3"), ("B2", "B3"), ("B1", "B2")):
            for k in keys:
                s = separable(agg, k, f"{a}/{arm}", f"{b}/{arm}")
                if s:
                    out.append({"arm": arm, "pair": f"{a} vs {b}", "key": k, **s})
    return out
