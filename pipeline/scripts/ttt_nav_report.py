"""Lay held-out navigation runs against each other (ADR-099 §4.5).

    uv run scripts/ttt_nav_report.py A0=nav-A0.json A2=nav-A2.json [A1=… A3=…] [--baseline A0] [--out report.json]

Per-arm, per-family mean scores, the absent family's false-acceptance
rate, and every arm paired against the baseline over the same held-out
items with a seeded bootstrap. Computes; does not interpret.
"""
import argparse
import json
import sys
from pathlib import Path

from hobbes.ttt.report import format_nav_report, nav_report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="ARM=path.json")
    ap.add_argument("--baseline", default="A0"); ap.add_argument("--out", type=Path)
    ap.add_argument("--resamples", type=int, default=5000); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    runs = {}
    for spec in a.runs:
        arm, _, path = spec.partition("=")
        runs[arm] = json.loads(Path(path).read_text())
    rep = nav_report(runs, a.baseline, a.resamples, a.seed)
    rep["inputs"] = {arm: {"model": r.get("model"), "context": r.get("context"), "repo": r.get("repo")} for arm, r in runs.items()}
    print(format_nav_report(rep))
    if a.out:
        a.out.write_text(json.dumps(rep, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
