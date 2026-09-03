"""Lay NLL runs against H-TTT-1 (ADR-099 §4.3).

    uv run scripts/ttt_report.py <units.jsonl> <base-run.json> [<adapter-run.json>] [--out report.json] [--resamples 5000]

Four arms paired by unit, a seeded paired bootstrap per comparison, and
the C-84 split (units whose file the base graph knew vs the rest). Prints
the table; writes JSON. Computes; does not interpret.
"""
import argparse
import json
import sys
from pathlib import Path

from hobbes.ttt.report import format_report, report
from hobbes.ttt.units import read_units


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("units", type=Path); ap.add_argument("base", type=Path); ap.add_argument("adapter", type=Path, nargs="?")
    ap.add_argument("--out", type=Path); ap.add_argument("--resamples", type=int, default=5000); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    known = {u["id"] for u in read_units(a.units) if not any("not in the graph" in n for n in u.get("notes", []))}
    base = json.loads(a.base.read_text())
    adapter = json.loads(a.adapter.read_text()) if a.adapter else None
    rep = report(base, adapter, known, a.resamples, a.seed)
    rep["inputs"] = {"units": str(a.units), "base": str(a.base), "adapter": str(a.adapter) if a.adapter else None,
                     "base_model": base.get("model"), "adapter_path": (adapter or {}).get("adapter"),
                     "gpu": base.get("gpu"), "versions": base.get("versions")}
    print(format_report(rep))
    if a.out:
        a.out.write_text(json.dumps(rep, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
