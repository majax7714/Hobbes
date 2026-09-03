"""Rescore a stored navigation run with the current scorer (ADR-099 §4.5).

    uv run scripts/ttt_rescore.py <corpus-dir> <run.json> --out <new.json> [--repo <repo>] [--audit]

A `ttt_probe.py nav` run keeps every reply, so a scorer change can be
applied without asking the model again: each row's evaluation record is
rebuilt from the corpus (``eval.jsonl``, or ``train.jsonl`` when the run
asked training items) by (family, symbol), the reply is rescored, and a
**new** file is written carrying ``scorer_version`` and
``rescored_from`` — the input is never overwritten, so the old numbers
stay where the old record cites them. ``--audit`` prints why each
*defines* reply the old scorer failed was failed
(`hobbes.ttt.score.classify_defines_failure`). Computes; does not interpret.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from hobbes import artifacts
from hobbes.ttt.score import SCORER_VERSION, classify_defines_failure, known_names, score_reply, summarise


def records_by_key(corpus_dir: Path, items: str) -> dict[tuple[str, str], dict]:
    """``(family, symbol) -> record`` for the evaluation or the training questions (first wins)."""
    out: dict[tuple[str, str], dict] = {}
    for line in (corpus_dir / ("train.jsonl" if items == "train" else "eval.jsonl")).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("kind") == "qa":
                out.setdefault((r["family"], r["symbol"]), r)
    return out


def rescore(run: dict, records: dict[tuple[str, str], dict], known: set[str], source: str) -> dict:
    """The run with every row rescored; rows without a record are kept and counted."""
    rows, missing = [], 0
    for row in run.get("rows", []):
        rec = records.get((row["family"], row["symbol"]))
        if rec is None:
            missing += 1
            rows.append(row)
            continue
        rows.append({"family": row["family"], "symbol": row["symbol"], **score_reply(rec, row.get("reply", ""), known),
                     "reply": row.get("reply", "")})
    out = {k: v for k, v in run.items() if k not in ("rows", "n", "families", "navigation_mean", "absent_false_acceptance")}
    out.update({"rows": rows, **summarise(rows), "scorer_version": SCORER_VERSION, "rescored_from": source,
                "rows_without_record": missing,
                "previous": {"scorer_version": run.get("scorer_version", 1), "families": run.get("families"),
                             "navigation_mean": run.get("navigation_mean"),
                             "absent_false_acceptance": run.get("absent_false_acceptance")}})
    return out


def audit(run: dict, records: dict[tuple[str, str], dict], known: set[str]) -> Counter:
    counts: Counter = Counter()
    for row in run.get("rows", []):
        if row["family"] == "defines" and row["score"] < 1:
            rec = records.get(("defines", row["symbol"]))
            counts[classify_defines_failure(rec, row.get("reply", ""), known) if rec else "no record"] += 1
    return counts


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", type=Path); ap.add_argument("run", type=Path)
    ap.add_argument("--out", type=Path); ap.add_argument("--repo", type=Path, help="the ingested repo (default: the corpus dir's repo)")
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args(argv)
    if a.out and a.out.resolve() == a.run.resolve():
        ap.error("--out must not be the input: a rescore is a new record")
    repo = a.repo or a.corpus.resolve().parents[2]
    known = known_names(artifacts.load_graph(repo))
    run = json.loads(a.run.read_text())
    records = records_by_key(a.corpus, run.get("items", "eval"))
    if a.audit:
        counts = audit(run, records, known)
        print(f"defines failures under scorer v{run.get('scorer_version', 1)}: {sum(counts.values())}")
        for reason, n in counts.most_common():
            print(f"  {n:4d}  {reason}")
    out = rescore(run, records, known, str(a.run))
    print(f"scorer v{SCORER_VERSION}:", json.dumps({k: out[k] for k in ("n", "families", "navigation_mean", "absent_false_acceptance") if k in out}))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
