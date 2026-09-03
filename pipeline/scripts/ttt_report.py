"""Lay NLL runs against H-TTT-1 (ADR-099 §4.3).

    uv run scripts/ttt_report.py <units.jsonl> <base-run.json> [<adapter-run.json>] [--out report.json] [--resamples 5000]
    uv run scripts/ttt_report.py <units.jsonl> --arm A0=base.json:bare --arm A2=adapter.json:bare --arm C=control.json:bare \
                                 [--compare A2-A0 --compare A2-C …] [--out report.json]

The positional form is the four fixed arms of two runs; the named form
takes any number of ``NAME=run.json:prompt`` arms (``prompt`` is
``bare`` or ``aided``) and compares the pairs named by ``--compare``
(every ordered pair, in the order given, when none is). Every comparison
is paired by unit, bootstrapped with a seed, and split by the C-84
population (units whose file the base graph knew vs the rest). Prints
the table; writes JSON. Computes; does not interpret.
"""
import argparse
import json
import sys
from pathlib import Path

from hobbes.ttt.report import arm_from_run, format_report, report, report_arms
from hobbes.ttt.units import read_units


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("units", type=Path); ap.add_argument("base", type=Path, nargs="?"); ap.add_argument("adapter", type=Path, nargs="?")
    ap.add_argument("--arm", action="append", default=[], metavar="NAME=run.json:prompt")
    ap.add_argument("--compare", action="append", default=[], metavar="A-B")
    ap.add_argument("--out", type=Path); ap.add_argument("--resamples", type=int, default=5000); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    known = {u["id"] for u in read_units(a.units) if not any("not in the graph" in n for n in u.get("notes", []))}
    if a.arm:
        arms, sources = {}, {}
        for spec in a.arm:
            name, _, rest = spec.partition("=")
            path, _, prompt = rest.rpartition(":")
            if not name or not path or prompt not in ("bare", "aided"):
                ap.error(f"--arm wants NAME=run.json:bare|aided, got {spec!r}")
            run = json.loads(Path(path).read_text())
            arms[name] = arm_from_run(run, prompt)
            sources[name] = {"run": path, "prompt": prompt, "model": run.get("model"), "adapter": run.get("adapter")}
        names = list(arms)
        pairs = [tuple(c.split("-", 1)) for c in a.compare] or [(x, y) for x in names for y in names if x != y]
        for x, y in pairs:
            if x not in arms or y not in arms:
                ap.error(f"--compare names an arm not given: {x}-{y}")
        rep = report_arms(arms, pairs, known, a.resamples, a.seed)
        rep["inputs"] = {"units": str(a.units), "arms": sources}
    else:
        if a.base is None:
            ap.error("a base run or --arm is required")
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
