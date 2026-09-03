"""Build gold-diff units for the NLL measurement (ADR-099 §4.3).

    uv run scripts/ttt_units.py git <repo> <base> --graph <ingested-at-base> --out units.jsonl
                                [--head HEAD] [--prefix P ...] [--max-lines 120] [--min-lines 3] [--name NAME]
                                [--tasks proposals.jsonl]
    uv run scripts/ttt_units.py deepswe <task-dir> ... --graph <ingested-clone> --out units.jsonl [--name NAME]

``--graph`` is a checkout ingested at the units' base SHA; the A1 context
block is derived from its graph and test map. ``--tasks`` attaches
hand-written proposals to git units by commit (the ``task``
conditioning, review item 2). Prints one line per unit and a count;
writes JSONL with every NLL prompt the unit can carry. Computes; does
not interpret.
"""
import argparse
import sys
from pathlib import Path

from hobbes import artifacts
from hobbes.ttt.units import (UnitError, attach_context, attach_tasks, read_tasks, unit_from_deepswe,
                              units_from_git, write_units)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    g = sub.add_parser("git"); g.add_argument("repo", type=Path); g.add_argument("base"); g.add_argument("--head", default="HEAD")
    g.add_argument("--prefix", action="append", default=[]); g.add_argument("--max-lines", type=int, default=120)
    g.add_argument("--min-lines", type=int, default=3)
    g.add_argument("--tasks", type=Path, help="JSONL of {commit, task}: hand-written proposals attached by commit")
    d = sub.add_parser("deepswe"); d.add_argument("tasks", type=Path, nargs="+")
    for p in (g, d):
        p.add_argument("--graph", type=Path, required=True, help="a checkout ingested at the base SHA")
        p.add_argument("--out", type=Path, required=True); p.add_argument("--name")
    a = ap.parse_args(argv)
    try:
        if a.mode == "git":
            units = units_from_git(a.repo, a.base, a.head, name=a.name, prefixes=tuple(a.prefix),
                                   max_lines=a.max_lines, min_lines=a.min_lines)
        else:
            units = [unit_from_deepswe(t, a.name) for t in a.tasks]
        graph, tests = artifacts.load_graph(a.graph), artifacts.load_tests(a.graph)
    except (UnitError, artifacts.ArtifactError) as exc:
        print(f"ttt_units: {exc}", file=sys.stderr)
        return 2
    graph_sha = graph.get("sha", "")
    for u in units:
        if u.sha and graph_sha and not graph_sha.startswith(u.sha[:7]) and not u.sha.startswith(graph_sha[:7]):
            u.notes.append(f"graph is at {graph_sha[:12]}, unit base is {u.sha[:12]}")
    attach_context(units, graph, tests)
    if a.mode == "git" and a.tasks:
        got = attach_tasks(units, read_tasks(a.tasks))
        print(f"tasks: {got}/{len(units)} unit(s) carry a hand-written proposal from {a.tasks}")
    write_units(units, a.out)
    for u in units:
        note = f"  [{'; '.join(u.notes)}]" if u.notes else ""
        print(f"{u.id[:60]:60} {u.diff_lines:4d} lines  {len(u.context):5d} ctx chars{note}")
    print(f"{len(units)} unit(s) → {a.out}; graph @ {graph_sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
