"""Records and the report (ADR-055).

One record per (instance, arm, model) in ``records.jsonl`` under the
run directory — instance facts (repo, created_at, the depth proxy),
the arm's outcome and patch shape, the meter, the verdict once the
evaluator has spoken, and for the harness arm the plan and run
summaries (the error stream). The report lays the records against
the three preregistered hypotheses and **computes, never interprets**:
it prints the rates, slopes, and per-solved costs with their sample
sizes and every unobserved term named, and leaves the reading to the
results section of ``docs/benchmark-hypotheses.md``.

Records with no verdict yet are excluded from every rate and counted
as such — a rate over unjudged patches would be a rate of "produced
something", which is not what any hypothesis asks.

**The planner hit (ADR-059, harness restructure phase 3).** A staged
harness record also carries, computed *here* from the instance's gold
patch after the arm has finished and never shown to any session,
whether the planner's named files reach a gold file. It is the first
number that says whether the generative layer above the lexical seeds
worked, independent of the solve — and it is a proxy: the gold patch
is one solution, not the only one (C-49).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from hobbes.bench.accounting import Usage
from hobbes.bench.arms import ArmResult
from hobbes.bench.instances import COMPLEX_BANDS, DEPTH_BUCKETS, DIFFICULTY_BANDS, Instance

RECORDS = "records.jsonl"


@dataclass
class Record:
    instance_id: str
    repo: str
    created_at: str
    depth: int
    depth_bucket: str
    arm: str
    model: str
    outcome: str
    patch_bytes: int
    patch_files: list[str]
    usage: dict
    verdict: str | None = None
    error: str = ""
    detail: dict = field(default_factory=dict)

    @property
    def solved(self) -> bool | None:
        return None if self.verdict in (None, "unjudged") else self.verdict == "resolved"

    def to_dict(self) -> dict:
        return asdict(self)


def planner_hit(planner_paths: list[str], gold_files: list[str]) -> dict:
    """``planner_paths ∩ gold_files`` — exact path, or a gold path ending
    in the named one (a planner may name ``app/core.py`` for
    ``src/app/core.py``). Counts are stated beside the rate so a single
    gold file cannot read as a strong result."""
    named = [p.strip("/") for p in planner_paths if p.strip("/")]
    hits = sorted({g for g in gold_files for n in named if g == n or g.endswith("/" + n)})
    return {"gold_files": sorted(gold_files), "hit_files": hits,
            "hit": bool(hits), "gold": len(gold_files), "hits": len(hits),
            "recall": round(len(hits) / len(gold_files), 4) if gold_files else None,
            "named": len(named)}


def make_record(instance: Instance, result: ArmResult) -> Record:
    detail = dict(result.detail)
    if result.arm == "harness" and "planner" in detail:
        # Post-hoc, from the gold patch the arm never saw (C-49).
        detail["planner"] = {**detail["planner"],
                             **planner_hit(detail["planner"].get("paths", []), instance.gold_files)}
    return Record(
        instance_id=instance.instance_id, repo=instance.repo, created_at=instance.created_at,
        depth=instance.depth, depth_bucket=instance.depth_bucket,
        arm=result.arm, model=result.model, outcome=result.outcome,
        patch_bytes=len(result.patch.encode()), patch_files=result.patch_files,
        usage=result.usage.to_dict(), error=result.error, detail=detail,
    )


def append(run_dir: Path, record: Record) -> None:
    path = Path(run_dir) / RECORDS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def load(run_dir: Path) -> list[Record]:
    path = Path(run_dir) / RECORDS
    if not path.is_file():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            out.append(Record(**json.loads(line)))
    return out


def rewrite(run_dir: Path, records: list[Record]) -> None:
    path = Path(run_dir) / RECORDS
    path.write_text("".join(json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in records))


def _rate(records: list[Record]) -> dict:
    judged = [r for r in records if r.solved is not None]
    solved = sum(1 for r in judged if r.solved)
    return {
        "n": len(records), "judged": len(judged), "solved": solved,
        "rate": round(solved / len(judged), 4) if judged else None,
    }


def _per_solved(records: list[Record]) -> dict:
    """H3's quantity: mean meter per *solved* instance, over the solved
    records whose term was observed; the unobserved count is stated."""
    solved = [r for r in records if r.solved]
    out: dict = {"solved": len(solved)}
    for term, key in (("tokens", "total_tokens"), ("cost_usd", "cost_usd"), ("wall_seconds", "wall_seconds")):
        values = [r.usage.get(key) for r in solved]
        seen = [v for v in values if v is not None]
        out[term] = {
            "mean": round(sum(seen) / len(seen), 3) if seen else None,
            "observed": len(seen), "unobserved": len(values) - len(seen),
        }
    return out


def report(records: list[Record]) -> dict:
    """The numbers the hypotheses are decided by, by arm and model."""
    groups: dict[tuple[str, str], list[Record]] = {}
    for r in records:
        groups.setdefault((r.arm, r.model), []).append(r)
    models = sorted({m for _, m in groups})

    h1 = {}
    for model in models:
        pure = _rate(groups.get(("pure", model), []))
        harness = _rate(groups.get(("harness", model), []))
        h1[model] = {"pure": pure, "harness": harness,
                     "delta": round(harness["rate"] - pure["rate"], 4)
                     if pure["rate"] is not None and harness["rate"] is not None else None}
    pure_rates = {m: h1[m]["pure"]["rate"] for m in models if h1[m]["pure"]["rate"] is not None}
    best_pure = max(pure_rates, key=pure_rates.get) if pure_rates else None
    for model in models:
        gap = None
        if best_pure and model != best_pure and h1[model]["harness"]["rate"] is not None \
                and h1[model]["pure"]["rate"] is not None:
            span = pure_rates[best_pure] - h1[model]["pure"]["rate"]
            gap = round((h1[model]["harness"]["rate"] - h1[model]["pure"]["rate"]) / span, 4) if span > 0 else None
        h1[model]["gap_closed_vs"] = best_pure
        h1[model]["gap_closed"] = gap

    # H2's axis: the rated bands when the records carry them, else the proxy.
    rated = any(r.depth_bucket in DIFFICULTY_BANDS for r in records)
    names = list(DIFFICULTY_BANDS) if rated else [n for n, _, _ in DEPTH_BUCKETS]
    h2 = {}
    for (arm, model), rs in sorted(groups.items()):
        buckets = {name: _rate([r for r in rs if r.depth_bucket == name]) for name in names}
        present = [buckets[n]["rate"] for n in names if buckets[n]["rate"] is not None]
        h2[f"{arm}/{model}"] = {
            "buckets": buckets,
            "slope": round(present[-1] - present[0], 4) if len(present) >= 2 else None,
            "complex": _rate([r for r in rs if r.depth_bucket in COMPLEX_BANDS]) if rated else None,
        }

    h3 = {f"{arm}/{model}": _per_solved(rs) for (arm, model), rs in sorted(groups.items())}

    planner = {}
    for (arm, model), rs in sorted(groups.items()):
        if arm != "harness" or not any(r.detail.get("seed_source") for r in rs):
            continue
        planner[f"{arm}/{model}"] = _planner_split(rs)

    outcomes: dict[str, dict[str, int]] = {}
    for (arm, model), rs in groups.items():
        counts = outcomes.setdefault(f"{arm}/{model}", {})
        for r in rs:
            counts[r.outcome] = counts.get(r.outcome, 0) + 1
    unjudged = sum(1 for r in records if r.solved is None)
    return {
        "records": len(records), "unjudged": unjudged, "models": models,
        "H1": h1, "H2": h2, "H3": h3, "planner": planner, "outcomes": outcomes,
        "notes": [
            "rates are over judged records only; unjudged records are counted, not rated",
            "depth is the rated difficulty band where the dataset has one, else the gold-patch file count — a proxy (H2)",
            "the owner's bar (H1, rung form): harnessed rung N ≈ pure rung N+1 on the complex multi-step set",
            "H3 means are per solved instance over records whose term was observed; "
            "unobserved counts are stated, never imputed",
            "contamination is bounded by the selection's cutoff, not proven (C-39)",
            "planner hit = the planner's named files reach a gold-patch file, computed after the arm "
            "from the gold patch no session saw; the gold patch is one solution, not the only one (C-49)",
            "an aided implement run is recorded arm=model+prompt, never harness — one agent, the whole "
            "task (P12, ADR-082); it enters no H1 harness slot",
            "the verdict is the pinned swebench evaluator's — its limits are ours (P9)",
        ],
    }


def _planner_split(records: list[Record]) -> dict:
    """The staged harness arm by ``seed_source``, with the planner hit
    beside the solve rate: did the unlock work, independent of the
    verdict? Records with no planner stage (no stage loop, or an arm
    that failed before it) are counted under ``none``."""
    by_source: dict[str, list[Record]] = {}
    for r in records:
        by_source.setdefault(r.detail.get("seed_source") or "none", []).append(r)
    out: dict = {"by_seed_source": {}}
    for source, rs in sorted(by_source.items()):
        with_gold = [r for r in rs if r.detail.get("planner", {}).get("gold")]
        hit = sum(1 for r in with_gold if r.detail["planner"].get("hit"))
        recalls = [r.detail["planner"]["recall"] for r in with_gold if r.detail["planner"].get("recall") is not None]
        out["by_seed_source"][source] = {
            **_rate(rs),
            "planner_hit": hit, "planner_checked": len(with_gold),
            "planner_hit_rate": round(hit / len(with_gold), 4) if with_gold else None,
            "planner_recall_mean": round(sum(recalls) / len(recalls), 4) if recalls else None,
        }
    checked = [r for r in records if r.detail.get("planner", {}).get("gold")]
    hits = sum(1 for r in checked if r.detail["planner"].get("hit"))
    out["planner_hit"] = hits
    out["planner_checked"] = len(checked)
    out["planner_hit_rate"] = round(hits / len(checked), 4) if checked else None
    # Coverage (ADR-085): how the planner's requirement decomposition
    # fared per record, and how many imperatives the lexical precursor
    # flagged — the gap measured, not judged (C-57).
    statuses: dict[str, int] = {}
    unmentioned = 0
    for r in records:
        cov = r.detail.get("coverage") or {}
        if cov.get("status"):
            statuses[cov["status"]] = statuses.get(cov["status"], 0) + 1
        unmentioned += len(r.detail.get("planner", {}).get("imperatives_unmentioned", []) or [])
    out["coverage"] = statuses
    out["imperatives_unmentioned"] = unmentioned
    out["brief_task"] = {}
    for r in records:
        bt = r.detail.get("brief_task")
        if bt:
            out["brief_task"][bt] = out["brief_task"].get(bt, 0) + 1
    return out


def _pct(rate: float | None) -> str:
    return "—" if rate is None else f"{100 * rate:.1f}%"


def format_report(doc: dict) -> str:
    lines = [f"benchmark report: {doc['records']} records, {doc['unjudged']} unjudged"]
    lines.append("")
    lines.append("H1 — solve rate, pure vs harnessed, same model")
    lines.append("  model | pure (solved/judged) | harness (solved/judged) | delta | gap closed vs best pure")
    for model, row in doc["H1"].items():
        p, h = row["pure"], row["harness"]
        gap = "—" if row["gap_closed"] is None else f"{100 * row['gap_closed']:.0f}% of {row['gap_closed_vs']}"
        delta = "—" if row["delta"] is None else f"{100 * row['delta']:+.1f} pts"
        lines.append(f"  {model} | {_pct(p['rate'])} ({p['solved']}/{p['judged']}) | "
                     f"{_pct(h['rate'])} ({h['solved']}/{h['judged']}) | {delta} | {gap}")
    lines.append("")
    rated = any(row.get("complex") is not None for row in doc["H2"].values())
    lines.append("H2 — solve rate by depth (" + ("rated difficulty" if rated else "gold-patch files, a proxy")
                 + "); slope = deepest bucket − shallowest")
    for key, row in doc["H2"].items():
        cells = ", ".join(f"{b} {_pct(v['rate'])} ({v['solved']}/{v['judged']})" for b, v in row["buckets"].items())
        slope = "—" if row["slope"] is None else f"{100 * row['slope']:+.1f} pts"
        extra = ""
        if row.get("complex"):
            c = row["complex"]
            extra = f"; complex multi-step {_pct(c['rate'])} ({c['solved']}/{c['judged']})"
        lines.append(f"  {key}: {cells}; slope {slope}{extra}")
    lines.append("")
    lines.append("H3 — per solved instance (means over observed terms)")
    for key, row in doc["H3"].items():
        parts = []
        for term in ("tokens", "cost_usd", "wall_seconds"):
            t = row[term]
            value = "unobserved" if t["mean"] is None else f"{t['mean']:g}"
            miss = f" ({t['unobserved']} unobserved)" if t["unobserved"] else ""
            parts.append(f"{term} {value}{miss}")
        lines.append(f"  {key}: solved {row['solved']}; " + "; ".join(parts))
    if doc.get("planner"):
        lines.append("")
        lines.append("planner (staged harness, ADR-059) — by seed_source; hit = named files reach a gold file")
        lines.append("  arm/model | seed_source | solved/judged (n) | planner hit (checked) | mean gold recall")
        for key, row in doc["planner"].items():
            for source, cell in row["by_seed_source"].items():
                hit = "—" if cell["planner_hit_rate"] is None else \
                    f"{_pct(cell['planner_hit_rate'])} ({cell['planner_hit']}/{cell['planner_checked']})"
                recall = "—" if cell["planner_recall_mean"] is None else f"{100 * cell['planner_recall_mean']:.0f}%"
                lines.append(f"  {key} | {source} | {_pct(cell['rate'])} ({cell['solved']}/{cell['judged']}) "
                             f"(n={cell['n']}) | {hit} | {recall}")
            total = "—" if row["planner_hit_rate"] is None else \
                f"{_pct(row['planner_hit_rate'])} ({row['planner_hit']}/{row['planner_checked']})"
            lines.append(f"  {key} | all | planner hit {total}")
            if row.get("coverage"):
                lines.append(f"  {key} | coverage (ADR-085): "
                             + ", ".join(f"{k} {v}" for k, v in sorted(row["coverage"].items()))
                             + f"; brief task: " + (", ".join(f"{k} {v}" for k, v in sorted(row["brief_task"].items())) or "—")
                             + f"; proposal imperatives the handoff never mentioned: {row['imperatives_unmentioned']} (lexical, C-57)")
    lines.append("")
    lines.append("outcomes (the error stream)")
    for key, counts in doc["outcomes"].items():
        lines.append(f"  {key}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    lines.append("")
    lines += [f"note: {n}" for n in doc["notes"]]
    return "\n".join(lines)
